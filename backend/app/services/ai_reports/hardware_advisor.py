"""Heuristic hardware-refresh advisor.

No external pricing — it produces conservative replacement-class suggestions
for aging gear based on the model name. All output is clearly labeled as a
suggestion, never a quote.
"""
from __future__ import annotations

from typing import Any, Dict, List


_REFRESH_MAP = {
    "R410": ("Dell PowerEdge R660 or R760 class",
             "1U mid-gen replacement — Intel Xeon 5th-gen or AMD EPYC, DDR5, NVMe."),
    "R420": ("Dell PowerEdge R660 class (or R760 for density)",
             "Similar 1U/2U footprint with 2-3x perf/watt and modern OOB (iDRAC 9/10)."),
    "R510": ("Dell PowerEdge R760xd or R750xd class",
             "Dense storage node replacement with 2.5\"/3.5\" NVMe options."),
    "R520": ("Dell PowerEdge R760 class",
             "2U replacement; DDR5 and PCIe 5.0 for 25/100 GbE networking."),
    "R610": ("Dell PowerEdge R660",
             "1U compute node refresh; Intel Xeon 5th-gen Emerald Rapids."),
    "R620": ("Dell PowerEdge R660 or R6615 (AMD)",
             "Modern 1U — drops from ~600W idle capacity to ~300W for similar workloads."),
    "R710": ("Dell PowerEdge R760 class",
             "2U refresh — NVMe-first, DDR5. End-of-vendor-support gear."),
    "R720": ("Dell PowerEdge R760 or R7615 (AMD EPYC for density)",
             "12G → 16G refresh gives roughly 2-3x RAM density and 40-60% lower watts/VM."),
}


def recommend(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for node in snapshot.get("nodes", []):
        model_str = ((node.get("bmc") or {}).get("model") or "").upper()
        for hint, (suggested, rationale) in _REFRESH_MAP.items():
            if hint in model_str:
                key = (node["node_name"], hint)
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "node_name": node["node_name"],
                    "host_name": node.get("host_name"),
                    "current_model": (node.get("bmc") or {}).get("model"),
                    "suggested_class": suggested,
                    "rationale": rationale,
                    "priority": "medium",
                    "confidence": "medium",
                    "notes": "No live pricing included — work with your vendor for current quotes.",
                })
                break
    return out
