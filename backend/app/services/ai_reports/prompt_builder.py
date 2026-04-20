"""Build prompts + strict response schema for the AI report step.

The LLM is instructed to stick to evidence from the provided snapshot and to
mark every estimate as an estimate. Response must be strict JSON.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError


# ── Strict response schema (pydantic) ────────────────────────────────────────

class _TopRisk(BaseModel):
    title: str
    severity: str  # info/warning/critical
    detail: str = ""


class _Item(BaseModel):
    title: str
    detail: str = ""
    severity: str = "info"
    affected: List[str] = Field(default_factory=list)


class AINarrative(BaseModel):
    executive_summary: str
    top_risks: List[_TopRisk] = Field(default_factory=list)
    optimization_opportunities: List[_Item] = Field(default_factory=list)
    redundancy_findings: List[_Item] = Field(default_factory=list)
    cost_efficiency_findings: List[_Item] = Field(default_factory=list)
    hardware_refresh_recommendations: List[_Item] = Field(default_factory=list)
    utilization_flags: List[_Item] = Field(default_factory=list)
    priority_actions: List[str] = Field(default_factory=list)
    confidence_notes: str = ""
    assumptions: List[str] = Field(default_factory=list)


RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "top_risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
                    "detail": {"type": "string"},
                },
                "required": ["title", "severity"],
            },
        },
        "optimization_opportunities": {"type": "array"},
        "redundancy_findings": {"type": "array"},
        "cost_efficiency_findings": {"type": "array"},
        "hardware_refresh_recommendations": {"type": "array"},
        "utilization_flags": {"type": "array"},
        "priority_actions": {"type": "array", "items": {"type": "string"}},
        "confidence_notes": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["executive_summary"],
}


def _system_prompt() -> str:
    return (
        "You are an experienced infrastructure analyst reviewing a Proxmox-based private cloud.\n"
        "Rules for this response:\n"
        "- No hype, no marketing language, no emojis.\n"
        "- Only cite facts from the provided snapshot. If you need to estimate, label it as an estimate.\n"
        "- Never invent pricing, vendor quotes, SKUs, or hardware availability. Pricing is unknown.\n"
        "- Distinguish measured data (e.g. consumed_watts from BMC) from estimates (modeled watts).\n"
        "- Be conservative: prefer low/medium confidence over high unless the evidence is unambiguous.\n"
        "- Keep prose tight — operators prefer bullet points over paragraphs.\n"
        "- Respond ONLY in the strict JSON schema requested. No markdown fences, no extra commentary.\n"
    )


def _user_prompt(
    snapshot: Dict[str, Any],
    findings: List[Dict[str, Any]],
    cost_estimate: Dict[str, Any],
    hw_recs: List[Dict[str, Any]],
    report_type: str,
    user_goal: Optional[str],
) -> str:
    # Keep the payload focused — the schema tells the model what sections to fill.
    payload = {
        "report_type": report_type,
        "operator_goal": user_goal or "",
        "snapshot_summary": {
            "collected_at": snapshot.get("collected_at"),
            "host_count": len(snapshot.get("hosts", [])),
            "node_count": len(snapshot.get("nodes", [])),
            "vms_summary": snapshot.get("vms_summary", {}),
            "pbs_servers": [p.get("name") for p in snapshot.get("pbs_servers", [])],
            "aging_hardware": snapshot.get("aging_hardware", []),
            "data_freshness_seconds": snapshot.get("data_freshness_seconds", 0),
        },
        "nodes": [
            {
                "node_name": n["node_name"],
                "host_name": n.get("host_name"),
                "cpu_cores": n.get("cpu_cores"),
                "cpu_avg_24h": n.get("cpu_avg_24h"),
                "cpu_usage_now": n.get("cpu_usage"),
                "memory_pct": n.get("memory_pct"),
                "memory_avg_24h": n.get("memory_avg_24h"),
                "disk_pct": n.get("disk_pct"),
                "vm_count": n.get("vm_count"),
                "lxc_count": n.get("lxc_count"),
                "aging_hardware": n.get("aging_hardware"),
                "bmc": {
                    "model": (n.get("bmc") or {}).get("model"),
                    "health": (n.get("bmc") or {}).get("health"),
                    "consumed_watts": (n.get("bmc") or {}).get("consumed_watts"),
                    "max_temp_c": (n.get("bmc") or {}).get("max_temp_c"),
                },
            }
            for n in snapshot.get("nodes", [])
        ],
        "deterministic_findings": findings,
        "power_cost_estimate": {
            "rate_per_kwh": cost_estimate.get("rate_per_kwh"),
            "currency": cost_estimate.get("currency"),
            "cluster_monthly_cost": cost_estimate.get("cluster_monthly_cost"),
            "cluster_monthly_kwh": cost_estimate.get("cluster_monthly_kwh"),
            "per_node": [
                {
                    "node_name": n["node_name"],
                    "source": n["source"],
                    "chosen_watts": n["chosen_watts"],
                    "monthly_cost": n["monthly_cost"],
                    "utilization_pct": n["utilization_pct"],
                }
                for n in cost_estimate.get("nodes", [])
            ],
        },
        "hardware_refresh_hints": hw_recs,
    }

    return (
        "INFRASTRUCTURE SNAPSHOT AND ANALYSIS REQUEST\n\n"
        f"{json.dumps(payload, default=str, indent=2)}\n\n"
        "Produce a report that follows the strict response schema. Focus sections as follows:\n"
        f"- report_type = {report_type}\n"
        "- If a section has no evidence, return an empty array for it.\n"
        "- executive_summary must be 3-6 sentences.\n"
        "- priority_actions is a flat list of up to 5 next steps, ranked highest impact first.\n"
    )


def build(
    snapshot: Dict[str, Any],
    findings: List[Dict[str, Any]],
    cost_estimate: Dict[str, Any],
    hw_recs: List[Dict[str, Any]],
    report_type: str,
    user_goal: Optional[str] = None,
) -> Tuple[str, str, Dict[str, Any]]:
    """Return (system_prompt, user_prompt, response_schema)."""
    return _system_prompt(), _user_prompt(snapshot, findings, cost_estimate, hw_recs, report_type, user_goal), RESPONSE_SCHEMA


def validate_ai_response(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and coerce an AI response dict against AINarrative."""
    try:
        return AINarrative(**raw).model_dump()
    except ValidationError as exc:
        raise ValueError(f"AI response failed schema validation: {exc.errors()}") from exc
