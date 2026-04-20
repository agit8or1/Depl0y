"""Electricity cost estimator.

Prefers measured consumed_watts from BMC cache when present. Falls back to
idle+load linear model driven by NodePowerProfile rows (or cluster default).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.database import NodePowerProfile, PowerCostSettings

logger = logging.getLogger(__name__)


def _get_default_profile(db: Session) -> NodePowerProfile:
    row = db.query(NodePowerProfile).filter(NodePowerProfile.node_id.is_(None)).first()
    if row:
        return row
    row = NodePowerProfile(node_id=None, idle_watts=120, load_watts=350)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _get_profile_for_node(db: Session, node_id: int) -> NodePowerProfile:
    row = db.query(NodePowerProfile).filter(NodePowerProfile.node_id == node_id).first()
    if row:
        return row
    return _get_default_profile(db)


def _get_cost_settings(db: Session) -> PowerCostSettings:
    row = db.query(PowerCostSettings).filter(PowerCostSettings.id == 1).first()
    if row:
        return row
    row = PowerCostSettings(id=1, electricity_rate_per_kwh=0.12, currency="USD")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def estimate(db: Session, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Return per-node and cluster-level cost estimate.

    Each node entry: watts_measured, watts_estimated, chosen_watts, source,
    monthly_kwh, monthly_cost.
    """
    settings = _get_cost_settings(db)
    rate = float(settings.electricity_rate_per_kwh or 0.12)
    currency = settings.currency or "USD"

    nodes_out: List[Dict[str, Any]] = []
    total_monthly_cost = 0.0
    total_monthly_kwh = 0.0
    total_watts = 0.0

    for node in snapshot.get("nodes", []):
        profile = _get_profile_for_node(db, node["id"])
        cpu = node.get("cpu_avg_24h") if node.get("cpu_avg_24h") is not None else node.get("cpu_usage")
        util = float(cpu or 0) / 100.0
        util = max(0.0, min(1.0, util))
        watts_est = profile.idle_watts + util * (profile.load_watts - profile.idle_watts)

        bmc = node.get("bmc") or {}
        watts_measured = bmc.get("consumed_watts")

        chosen = float(watts_measured) if watts_measured else float(watts_est)
        source = "measured" if watts_measured else "estimated"

        monthly_kwh = chosen * 24.0 * 30.0 / 1000.0
        monthly_cost = monthly_kwh * rate

        nodes_out.append({
            "node_id": node["id"],
            "node_name": node["node_name"],
            "host_name": node.get("host_name"),
            "watts_measured": watts_measured,
            "watts_estimated": round(watts_est, 1),
            "chosen_watts": round(chosen, 1),
            "source": source,
            "idle_watts": profile.idle_watts,
            "load_watts": profile.load_watts,
            "utilization_pct": round(util * 100.0, 1),
            "monthly_kwh": round(monthly_kwh, 1),
            "monthly_cost": round(monthly_cost, 2),
        })
        total_monthly_cost += monthly_cost
        total_monthly_kwh += monthly_kwh
        total_watts += chosen

    return {
        "rate_per_kwh": rate,
        "currency": currency,
        "nodes": nodes_out,
        "cluster_total_watts": round(total_watts, 1),
        "cluster_monthly_kwh": round(total_monthly_kwh, 1),
        "cluster_monthly_cost": round(total_monthly_cost, 2),
        "cluster_annual_cost": round(total_monthly_cost * 12.0, 2),
    }
