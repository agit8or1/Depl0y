"""Top-level orchestration for AI-report generation."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.database import AuditLog, ReportRun, User
from . import ai_provider, data_collector, hardware_advisor, power_cost, prompt_builder, renderer, rules_engine

logger = logging.getLogger(__name__)


_VALID_REPORT_TYPES = {"health", "optimization", "redundancy", "power", "hardware", "capacity", "comprehensive"}
_VALID_SCOPE_TYPES = {"global", "cluster", "node"}


def _default_title(report_type: str, scope_type: str, scope_ref: Optional[str]) -> str:
    scope_label = scope_type if scope_type == "global" else f"{scope_type} {scope_ref or ''}".strip()
    return f"{report_type.capitalize()} Report — {scope_label}"


def _audit(db: Session, user_id: Optional[int], action: str, resource_id: Optional[int], details: Dict[str, Any]):
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type="ai_report",
            resource_id=resource_id,
            details=details,
            success=True,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()


def _run_generation(run_id: int, report_type: str, scope_type: str, scope_ref: Optional[str], user_goal: Optional[str]):
    """Blocking generation step — designed to be callable from a thread."""
    db = SessionLocal()
    try:
        run = db.query(ReportRun).filter(ReportRun.id == run_id).first()
        if not run:
            logger.error("ReportRun %d disappeared before generation", run_id)
            return
        run.status = "running"
        db.commit()

        snapshot = data_collector.collect_snapshot(db, scope_type=scope_type, scope_ref=scope_ref)
        findings = rules_engine.analyze(snapshot)
        cost_estimate = power_cost.estimate(db, snapshot)
        hw_recs = hardware_advisor.recommend(snapshot)

        assumptions: List[str] = [
            f"Electricity rate: {cost_estimate.get('currency', 'USD')} {cost_estimate.get('rate_per_kwh', 0):.3f} / kWh (from system settings).",
            "Power figures prefer BMC-measured watts when available; otherwise modeled from the node's idle/load profile.",
            "Pricing and vendor quotes are never included — work with your vendor for current figures.",
        ]

        ai_narrative: Optional[Dict[str, Any]] = None
        model_used: Optional[str] = None
        token_usage: Optional[Dict[str, Any]] = None
        ai_error: Optional[str] = None

        provider = ai_provider.get_active_provider(db)
        if provider is not None:
            try:
                sys_p, user_p, schema = prompt_builder.build(
                    snapshot, findings, cost_estimate, hw_recs, report_type, user_goal
                )
                model_used = ai_provider.get_active_model(db)
                ai_result = provider.generate_report(sys_p, user_p, schema, model=model_used)
                token_usage = ai_result.get("usage")
                validated = prompt_builder.validate_ai_response(ai_result["parsed"])
                ai_narrative = validated
            except Exception as exc:
                ai_error = f"{type(exc).__name__}: {exc}"
                logger.warning("AI narrative step failed: %s", ai_error)
        else:
            ai_error = "no-provider-configured"

        markdown = renderer.render_markdown(
            title=run.title,
            report_type=report_type,
            created_at=run.created_at,
            data_freshness_seconds=snapshot.get("data_freshness_seconds"),
            findings=findings,
            cost_estimate=cost_estimate,
            hardware_recs=hw_recs,
            ai_narrative=ai_narrative,
            assumptions=assumptions,
            manual_notes=run.manual_notes,
            model_used=model_used,
            error_message=ai_error if ai_narrative is None and ai_error and ai_error != "no-provider-configured" else None,
        )
        html = renderer.render_html(
            title=run.title,
            report_type=report_type,
            created_at=run.created_at,
            data_freshness_seconds=snapshot.get("data_freshness_seconds"),
            findings=findings,
            cost_estimate=cost_estimate,
            hardware_recs=hw_recs,
            ai_narrative=ai_narrative,
            assumptions=assumptions,
            manual_notes=run.manual_notes,
            model_used=model_used,
            error_message=ai_error if ai_narrative is None and ai_error and ai_error != "no-provider-configured" else None,
        )

        run.findings_json = json.dumps(findings)
        run.ai_narrative_json = json.dumps(ai_narrative) if ai_narrative is not None else None
        run.assumptions_json = json.dumps(assumptions)
        run.rendered_markdown = markdown
        run.rendered_html = html
        run.model_used = model_used
        run.token_usage_json = json.dumps(token_usage) if token_usage else None
        run.data_freshness_seconds = snapshot.get("data_freshness_seconds")
        if ai_narrative is None and ai_error not in (None, "no-provider-configured"):
            run.status = "complete_ai_failed"
            run.error_message = ai_error
        else:
            run.status = "complete"
            run.error_message = None
        run.completed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        logger.exception("Report generation crashed for run %d", run_id)
        try:
            run = db.query(ReportRun).filter(ReportRun.id == run_id).first()
            if run:
                run.status = "failed"
                run.error_message = f"{type(exc).__name__}: {exc}"
                run.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def generate_report(
    db: Session,
    *,
    user: Optional[User],
    report_type: str,
    scope_type: str = "global",
    scope_ref: Optional[str] = None,
    title: Optional[str] = None,
    user_goal: Optional[str] = None,
    run_async: bool = True,
) -> ReportRun:
    """Queue a report run. Returns the ReportRun row in `running` or `queued` state."""
    if report_type not in _VALID_REPORT_TYPES:
        raise ValueError(f"Unknown report_type: {report_type}")
    if scope_type not in _VALID_SCOPE_TYPES:
        raise ValueError(f"Unknown scope_type: {scope_type}")

    run = ReportRun(
        title=title or _default_title(report_type, scope_type, scope_ref),
        report_type=report_type,
        scope_type=scope_type,
        scope_ref=scope_ref,
        status="queued",
        created_by_user_id=user.id if user else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    _audit(db, user.id if user else None, "ai_report_create", run.id,
           {"report_type": report_type, "scope_type": scope_type, "scope_ref": scope_ref})

    if run_async:
        threading.Thread(
            target=_run_generation,
            args=(run.id, report_type, scope_type, scope_ref, user_goal),
            daemon=True,
        ).start()
    else:
        _run_generation(run.id, report_type, scope_type, scope_ref, user_goal)
        db.refresh(run)

    return run


def regenerate(db: Session, run_id: int, user: Optional[User], run_async: bool = True) -> Optional[ReportRun]:
    existing = db.query(ReportRun).filter(ReportRun.id == run_id).first()
    if not existing:
        return None
    new_run = generate_report(
        db,
        user=user,
        report_type=existing.report_type,
        scope_type=existing.scope_type,
        scope_ref=existing.scope_ref,
        title=existing.title,
        run_async=run_async,
    )
    _audit(db, user.id if user else None, "ai_report_regenerate", new_run.id,
           {"source_run_id": run_id})
    return new_run
