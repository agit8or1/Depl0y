"""Markdown + printable HTML rendering for report runs."""
from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any, Dict, List, Optional


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _sev_icon(sev: str) -> str:
    return {"critical": "[!!]", "warning": "[!]", "info": "[i]"}.get((sev or "info").lower(), "[i]")


def _fmt_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "unknown"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


# ── Markdown ─────────────────────────────────────────────────────────────────

def render_markdown(
    *,
    title: str,
    report_type: str,
    created_at: Optional[datetime],
    data_freshness_seconds: Optional[int],
    findings: List[Dict[str, Any]],
    cost_estimate: Dict[str, Any],
    hardware_recs: List[Dict[str, Any]],
    ai_narrative: Optional[Dict[str, Any]],
    assumptions: List[str],
    manual_notes: Optional[str] = None,
    model_used: Optional[str] = None,
    error_message: Optional[str] = None,
) -> str:
    out: List[str] = []
    out.append(f"# {title}")
    out.append("")
    out.append(f"*Report type: **{report_type}***  •  Generated: {_fmt_dt(created_at)}"
               + (f"  •  Model: `{model_used}`" if model_used else ""))
    if data_freshness_seconds is not None:
        out.append(f"*Data freshness: up to {data_freshness_seconds}s old*")
    out.append("")

    if error_message:
        out.append("> NOTE: The AI narrative step failed — this report contains only deterministic findings.")
        out.append(f"> Error: `{error_message}`")
        out.append("")

    # Executive Summary
    out.append("## Executive Summary")
    out.append("")
    if ai_narrative and ai_narrative.get("executive_summary"):
        out.append(ai_narrative["executive_summary"])
    else:
        crit = sum(1 for f in findings if f.get("severity") == "critical")
        warn = sum(1 for f in findings if f.get("severity") == "warning")
        out.append(
            f"Deterministic analysis found **{crit}** critical and **{warn}** warning findings across the infrastructure. "
            "AI narrative was not generated — see the Raw Findings section for the full list."
        )
    out.append("")

    # Top Risks
    out.append("## Top Risks")
    out.append("")
    if ai_narrative and ai_narrative.get("top_risks"):
        for r in ai_narrative["top_risks"]:
            out.append(f"- {_sev_icon(r.get('severity'))} **{r.get('title')}** — {r.get('detail', '')}")
    else:
        crits = [f for f in findings if f.get("severity") == "critical"]
        warns = [f for f in findings if f.get("severity") == "warning"]
        for f in crits + warns:
            out.append(f"- {_sev_icon(f.get('severity'))} **{f.get('title')}** — {f.get('recommendation', '')}")
    if not findings and not (ai_narrative and ai_narrative.get("top_risks")):
        out.append("- No significant risks detected.")
    out.append("")

    # Priority Actions
    out.append("## Priority Actions")
    out.append("")
    pa = _safe_list((ai_narrative or {}).get("priority_actions"))
    if pa:
        for i, a in enumerate(pa, 1):
            out.append(f"{i}. {a}")
    else:
        for i, f in enumerate(findings[:5], 1):
            out.append(f"{i}. {f.get('recommendation') or f.get('title')}")
    out.append("")

    # Optimization
    _section(out, "Optimization Opportunities", _safe_list((ai_narrative or {}).get("optimization_opportunities")),
             deterministic=[f for f in findings if f.get("category") == "performance"])

    # Redundancy
    _section(out, "Redundancy & Reliability", _safe_list((ai_narrative or {}).get("redundancy_findings")),
             deterministic=[f for f in findings if f.get("category") in ("redundancy", "backup", "reliability")])

    # Cost / Power
    out.append("## Power & Cost")
    out.append("")
    if cost_estimate.get("nodes"):
        cur = cost_estimate.get("currency", "USD")
        out.append(f"Cluster estimated monthly cost: **{cur} {cost_estimate.get('cluster_monthly_cost', 0):.2f}** "
                   f"({cost_estimate.get('cluster_monthly_kwh', 0):.1f} kWh @ {cost_estimate.get('rate_per_kwh', 0):.3f} / kWh).")
        out.append("")
        out.append("| Node | Source | Watts | Util % | Monthly kWh | Monthly Cost |")
        out.append("|------|--------|-------|--------|-------------|--------------|")
        for n in cost_estimate["nodes"]:
            out.append(
                f"| {n['node_name']} | {n['source']} | {n['chosen_watts']} | "
                f"{n['utilization_pct']} | {n['monthly_kwh']} | {cur} {n['monthly_cost']} |"
            )
        out.append("")
    else:
        out.append("No node power data available.")
        out.append("")
    for item in _safe_list((ai_narrative or {}).get("cost_efficiency_findings")):
        out.append(f"- {_sev_icon(item.get('severity'))} **{item.get('title')}** — {item.get('detail', '')}")
    out.append("")

    # Hardware Refresh
    out.append("## Hardware Refresh Recommendations")
    out.append("")
    ai_hw = _safe_list((ai_narrative or {}).get("hardware_refresh_recommendations"))
    if ai_hw:
        for item in ai_hw:
            out.append(f"- **{item.get('title')}** — {item.get('detail', '')}")
    for hw in hardware_recs:
        out.append(
            f"- **{hw['node_name']}** (currently `{hw.get('current_model', 'unknown')}`): "
            f"{hw['suggested_class']} — {hw['rationale']}"
        )
    if not ai_hw and not hardware_recs:
        out.append("- No aging hardware detected.")
    out.append("")

    # Utilization flags
    _section(out, "Utilization Flags", _safe_list((ai_narrative or {}).get("utilization_flags")),
             deterministic=[f for f in findings if f.get("rule_type") in ("node_underutilized", "likely_oversized_vms")])

    # Raw findings appendix
    out.append("## Raw Findings Appendix")
    out.append("")
    if findings:
        out.append("| Severity | Category | Rule | Title | Affected |")
        out.append("|----------|----------|------|-------|----------|")
        for f in findings:
            affected = ", ".join(f.get("affected_resources") or [])
            out.append(f"| {f.get('severity')} | {f.get('category')} | `{f.get('rule_type')}` | {f.get('title')} | {affected} |")
    else:
        out.append("No deterministic findings.")
    out.append("")

    # Assumptions
    out.append("## Assumptions")
    out.append("")
    merged = list(assumptions or [])
    merged += _safe_list((ai_narrative or {}).get("assumptions"))
    if merged:
        for a in merged:
            out.append(f"- {a}")
    else:
        out.append("- None stated.")
    out.append("")

    # Data freshness
    out.append("## Data Freshness")
    out.append("")
    out.append(f"- Max age of any source used in this report: **{data_freshness_seconds or 0} seconds**.")
    out.append("- BMC telemetry is refreshed every 2 minutes.")
    out.append("- Node metric snapshots are captured every 5 minutes.")
    out.append("")

    if manual_notes:
        out.append("## Operator Notes")
        out.append("")
        out.append(manual_notes)
        out.append("")

    return "\n".join(out)


def _section(out: List[str], heading: str, ai_items: List[Dict[str, Any]], deterministic: List[Dict[str, Any]]):
    out.append(f"## {heading}")
    out.append("")
    if ai_items:
        for item in ai_items:
            out.append(f"- {_sev_icon(item.get('severity'))} **{item.get('title')}** — {item.get('detail', '')}")
    if deterministic:
        for f in deterministic:
            out.append(f"- {_sev_icon(f.get('severity'))} **{f.get('title')}** — {f.get('recommendation', '')}")
    if not ai_items and not deterministic:
        out.append("- None.")
    out.append("")


# ── HTML ─────────────────────────────────────────────────────────────────────

_HTML_STYLE = """
body { font-family: 'Helvetica', 'Arial', sans-serif; color: #1f2937; max-width: 900px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }
h1 { font-size: 1.8rem; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }
h2 { font-size: 1.3rem; margin-top: 2rem; color: #111827; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.25rem; }
h3 { font-size: 1.1rem; color: #374151; }
code { background: #f3f4f6; padding: 0 0.25rem; border-radius: 3px; font-size: 0.9em; }
table { width: 100%; border-collapse: collapse; margin: 0.5rem 0; font-size: 0.9rem; }
th, td { border: 1px solid #d1d5db; padding: 0.4rem 0.6rem; text-align: left; }
th { background: #f9fafb; }
.sev-critical { color: #b91c1c; font-weight: 700; }
.sev-warning { color: #b45309; font-weight: 600; }
.sev-info { color: #1d4ed8; }
.meta { color: #6b7280; font-size: 0.85rem; margin: 0.25rem 0 1rem; }
.notice { background: #fef3c7; padding: 0.75rem; border-left: 4px solid #f59e0b; margin: 1rem 0; border-radius: 4px; }
.list { padding-left: 1.25rem; }
.list li { margin: 0.25rem 0; }
@media print {
  body { margin: 0; font-size: 11pt; }
  h2 { page-break-after: avoid; }
  table, .notice { page-break-inside: avoid; }
}
"""


def _esc(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def _sev_class(sev: str) -> str:
    return f"sev-{(sev or 'info').lower()}"


def render_html(
    *,
    title: str,
    report_type: str,
    created_at: Optional[datetime],
    data_freshness_seconds: Optional[int],
    findings: List[Dict[str, Any]],
    cost_estimate: Dict[str, Any],
    hardware_recs: List[Dict[str, Any]],
    ai_narrative: Optional[Dict[str, Any]],
    assumptions: List[str],
    manual_notes: Optional[str] = None,
    model_used: Optional[str] = None,
    error_message: Optional[str] = None,
) -> str:
    parts: List[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append(f"<html><head><meta charset='utf-8'><title>{_esc(title)}</title><style>{_HTML_STYLE}</style></head><body>")
    parts.append(f"<h1>{_esc(title)}</h1>")
    parts.append(
        f"<div class='meta'>Report type: <strong>{_esc(report_type)}</strong> &bull; "
        f"Generated: {_esc(_fmt_dt(created_at))}"
        + (f" &bull; Model: <code>{_esc(model_used)}</code>" if model_used else "")
        + "</div>"
    )
    if data_freshness_seconds is not None:
        parts.append(f"<div class='meta'>Data freshness: up to {int(data_freshness_seconds)}s old.</div>")

    if error_message:
        parts.append(f"<div class='notice'><strong>AI narrative unavailable.</strong> Deterministic findings only. Error: <code>{_esc(error_message)}</code></div>")

    # Executive Summary
    parts.append("<h2>Executive Summary</h2>")
    if ai_narrative and ai_narrative.get("executive_summary"):
        parts.append(f"<p>{_esc(ai_narrative['executive_summary'])}</p>")
    else:
        crit = sum(1 for f in findings if f.get("severity") == "critical")
        warn = sum(1 for f in findings if f.get("severity") == "warning")
        parts.append(f"<p>Deterministic analysis found <strong>{crit}</strong> critical and <strong>{warn}</strong> warning findings.</p>")

    # Top Risks
    parts.append("<h2>Top Risks</h2>")
    top = _safe_list((ai_narrative or {}).get("top_risks"))
    if not top:
        top = [
            {"title": f.get("title"), "severity": f.get("severity"), "detail": f.get("recommendation", "")}
            for f in findings if f.get("severity") in ("critical", "warning")
        ]
    if top:
        parts.append("<ul class='list'>")
        for r in top:
            parts.append(
                f"<li><span class='{_sev_class(r.get('severity'))}'>{_esc((r.get('severity') or 'info').upper())}</span> "
                f"<strong>{_esc(r.get('title'))}</strong> &mdash; {_esc(r.get('detail', ''))}</li>"
            )
        parts.append("</ul>")
    else:
        parts.append("<p>No significant risks detected.</p>")

    # Priority Actions
    parts.append("<h2>Priority Actions</h2>")
    pa = _safe_list((ai_narrative or {}).get("priority_actions"))
    if not pa:
        pa = [f.get("recommendation") or f.get("title") for f in findings[:5]]
    if pa:
        parts.append("<ol>")
        for a in pa:
            parts.append(f"<li>{_esc(a)}</li>")
        parts.append("</ol>")
    else:
        parts.append("<p>No immediate actions required.</p>")

    # Sections
    _html_section(parts, "Optimization Opportunities",
                  _safe_list((ai_narrative or {}).get("optimization_opportunities")),
                  [f for f in findings if f.get("category") == "performance"])
    _html_section(parts, "Redundancy & Reliability",
                  _safe_list((ai_narrative or {}).get("redundancy_findings")),
                  [f for f in findings if f.get("category") in ("redundancy", "backup", "reliability")])

    # Cost / Power
    parts.append("<h2>Power & Cost</h2>")
    if cost_estimate.get("nodes"):
        cur = cost_estimate.get("currency", "USD")
        parts.append(
            f"<p>Cluster estimated monthly cost: <strong>{_esc(cur)} {cost_estimate.get('cluster_monthly_cost', 0):.2f}</strong> "
            f"({cost_estimate.get('cluster_monthly_kwh', 0):.1f} kWh @ {cost_estimate.get('rate_per_kwh', 0):.3f} / kWh).</p>"
        )
        parts.append("<table><thead><tr><th>Node</th><th>Source</th><th>Watts</th><th>Util %</th><th>kWh / mo</th><th>Cost / mo</th></tr></thead><tbody>")
        for n in cost_estimate["nodes"]:
            parts.append(
                f"<tr><td>{_esc(n['node_name'])}</td><td>{_esc(n['source'])}</td>"
                f"<td>{n['chosen_watts']}</td><td>{n['utilization_pct']}</td>"
                f"<td>{n['monthly_kwh']}</td><td>{_esc(cur)} {n['monthly_cost']}</td></tr>"
            )
        parts.append("</tbody></table>")
    else:
        parts.append("<p>No node power data available.</p>")

    for item in _safe_list((ai_narrative or {}).get("cost_efficiency_findings")):
        parts.append(
            f"<p><span class='{_sev_class(item.get('severity'))}'>{_esc((item.get('severity') or 'info').upper())}</span> "
            f"<strong>{_esc(item.get('title'))}</strong> &mdash; {_esc(item.get('detail', ''))}</p>"
        )

    # Hardware Refresh
    parts.append("<h2>Hardware Refresh Recommendations</h2>")
    if hardware_recs:
        parts.append("<ul class='list'>")
        for hw in hardware_recs:
            parts.append(
                f"<li><strong>{_esc(hw['node_name'])}</strong> "
                f"(current: <code>{_esc(hw.get('current_model', 'unknown'))}</code>): "
                f"{_esc(hw['suggested_class'])} &mdash; {_esc(hw['rationale'])}</li>"
            )
        parts.append("</ul>")
    else:
        parts.append("<p>No aging hardware detected.</p>")

    _html_section(parts, "Utilization Flags",
                  _safe_list((ai_narrative or {}).get("utilization_flags")),
                  [f for f in findings if f.get("rule_type") in ("node_underutilized", "likely_oversized_vms")])

    # Raw findings
    parts.append("<h2>Raw Findings Appendix</h2>")
    if findings:
        parts.append("<table><thead><tr><th>Severity</th><th>Category</th><th>Rule</th><th>Title</th><th>Affected</th></tr></thead><tbody>")
        for f in findings:
            parts.append(
                f"<tr><td class='{_sev_class(f.get('severity'))}'>{_esc(f.get('severity'))}</td>"
                f"<td>{_esc(f.get('category'))}</td>"
                f"<td><code>{_esc(f.get('rule_type'))}</code></td>"
                f"<td>{_esc(f.get('title'))}</td>"
                f"<td>{_esc(', '.join(f.get('affected_resources') or []))}</td></tr>"
            )
        parts.append("</tbody></table>")
    else:
        parts.append("<p>No deterministic findings.</p>")

    # Assumptions
    parts.append("<h2>Assumptions</h2>")
    merged = list(assumptions or [])
    merged += _safe_list((ai_narrative or {}).get("assumptions"))
    if merged:
        parts.append("<ul class='list'>")
        for a in merged:
            parts.append(f"<li>{_esc(a)}</li>")
        parts.append("</ul>")
    else:
        parts.append("<p>None stated.</p>")

    # Data freshness
    parts.append("<h2>Data Freshness</h2>")
    parts.append(f"<p>Max age of any source used in this report: <strong>{int(data_freshness_seconds or 0)} seconds</strong>. "
                 "BMC telemetry refreshes every 2 minutes; node metric snapshots every 5 minutes.</p>")

    if manual_notes:
        parts.append("<h2>Operator Notes</h2>")
        parts.append(f"<pre style='white-space: pre-wrap;'>{_esc(manual_notes)}</pre>")

    parts.append("</body></html>")
    return "".join(parts)


def _html_section(parts: List[str], heading: str, ai_items: List[Dict[str, Any]], deterministic: List[Dict[str, Any]]):
    parts.append(f"<h2>{_esc(heading)}</h2>")
    items_rendered = False
    if ai_items or deterministic:
        parts.append("<ul class='list'>")
        for item in ai_items:
            parts.append(
                f"<li><span class='{_sev_class(item.get('severity'))}'>{_esc((item.get('severity') or 'info').upper())}</span> "
                f"<strong>{_esc(item.get('title'))}</strong> &mdash; {_esc(item.get('detail', ''))}</li>"
            )
            items_rendered = True
        for f in deterministic:
            parts.append(
                f"<li><span class='{_sev_class(f.get('severity'))}'>{_esc((f.get('severity') or 'info').upper())}</span> "
                f"<strong>{_esc(f.get('title'))}</strong> &mdash; {_esc(f.get('recommendation', ''))}</li>"
            )
            items_rendered = True
        parts.append("</ul>")
    if not items_rendered:
        parts.append("<p>None.</p>")
