"""Regenerate ai-report.html from the backend renderer (run from backend/):

    PYTHONPATH=. python ../frontend/tests/fixtures/make_ai_report_fixture.py

The narrative carries markup an LLM could plausibly emit, so the frontend
test checks the renderer output after DOMPurify, not a hand-written sample.
"""
import pathlib
from datetime import datetime

from app.services.ai_reports.renderer import render_html

HOSTILE = '<img src=x onerror="alert(1)"><script>alert(2)</script><a href="javascript:alert(3)">x</a> {{ constructor }}'

html = render_html(
    title="Cluster health " + HOSTILE,
    report_type="cluster_health",
    created_at=datetime(2026, 11, 6, 12, 0, 0),
    data_freshness_seconds=120,
    findings=[{"severity": "critical", "category": "performance", "title": "Node pve3 memory " + HOSTILE,
               "rule_type": "node_memory_high", "recommendation": "Move VMs",
               "affected_resources": ["pve3"]}],
    cost_estimate={"currency": "USD", "cluster_monthly_cost": 123.45, "cluster_monthly_kwh": 900.0,
                   "rate_per_kwh": 0.12, "nodes": [{"node_name": "pve3", "source": "redfish", "chosen_watts": 300, "utilization_pct": 40,
                                                    "monthly_kwh": 216, "monthly_cost": 25.92}]},
    hardware_recs=[{"node_name": "pve3", "current_model": "R720xd", "suggested_class": "R750",
                    "rationale": "Aging " + HOSTILE}],
    ai_narrative={"executive_summary": "Summary " + HOSTILE,
                  "priority_actions": ["Act " + HOSTILE]},
    assumptions=["Power at $0.12/kWh"],
    manual_notes="Notes " + HOSTILE,
    model_used="test-model",
)
out = pathlib.Path(__file__).with_name("ai-report.html")
out.write_text(html)
print(f"wrote {out} ({len(html)} bytes)")
