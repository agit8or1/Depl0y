#!/usr/bin/env python3
"""Interpret pip-audit / npm audit JSON so CI can tell three outcomes apart.

    audit_report.py pip <pip-audit.json> <scanner-exit-code>
    audit_report.py npm <npm-audit.json> <scanner-exit-code>

Exit status:
    0  scan completed, no vulnerabilities (other than accepted ones)
    1  scan completed and found vulnerabilities
    2  the scanner itself failed (no usable report: network, registry, parse error)

Advisories listed in scripts/security/audit-allowlist.json are reported as
"accepted" and do not fail the build until their `review_by` date has passed.
"""
import json
import pathlib
import sys
from datetime import date

ALLOWLIST = pathlib.Path(__file__).with_name("audit-allowlist.json")


def _allowlist():
    entries = json.loads(ALLOWLIST.read_text()) if ALLOWLIST.exists() else []
    today = date.today().isoformat()
    active, expired = {}, {}
    for e in entries:
        (active if e["review_by"] >= today else expired)[e["id"]] = e
    return active, expired


def _scanner_failure(tool, why):
    print(f"::error title={tool} scanner failure::{why}")
    print(f"RESULT: SCANNER FAILURE ({tool}) — this is not a vulnerability finding; the scan did not complete.")
    return 2


def _pip(report):
    found = []
    for dep in report.get("dependencies", []):
        for v in dep.get("vulns", []):
            found.append((v["id"], set(v.get("aliases") or []), f"{dep['name']} {dep['version']}",
                          ", ".join(v.get("fix_versions") or []) or "no fixed release"))
    skipped = [d["name"] for d in report.get("dependencies", []) if d.get("skip_reason")]
    return found, skipped


def _npm(report):
    if "error" in report:
        raise ValueError(report["error"].get("summary") or report["error"])
    found = []
    for name, v in (report.get("vulnerabilities") or {}).items():
        for via in v.get("via", []):
            if isinstance(via, dict):
                ghsa = (via.get("url") or "").rsplit("/", 1)[-1]
                fix = v.get("fixAvailable")
                fix_txt = "fix available" if fix else "no fix available"
                found.append((ghsa or via.get("title", "?"), set(), f"{name} ({via.get('range')}, {via.get('severity')})", fix_txt))
    return found, []


def main(argv):
    if len(argv) != 4 or argv[1] not in ("pip", "npm"):
        print(__doc__)
        return 2
    tool, path, code = argv[1], pathlib.Path(argv[2]), argv[3]
    try:
        report = json.loads(path.read_text())
        found, skipped = (_pip if tool == "pip" else _npm)(report)
    except FileNotFoundError:
        return _scanner_failure(tool, f"no report written (scanner exit code {code})")
    except (ValueError, KeyError, TypeError) as exc:
        return _scanner_failure(tool, f"unreadable report (scanner exit code {code}): {exc}")

    active, expired = _allowlist()
    failing, accepted, seen = [], [], set()
    for vid, aliases, pkg, fix in found:
        if (vid, pkg) in seen:  # pip-audit can list the same advisory twice
            continue
        seen.add((vid, pkg))
        ids = {vid} | aliases
        hit = next((active[i] for i in ids if i in active), None)
        (accepted if hit else failing).append((vid, pkg, fix, hit, next((expired[i] for i in ids if i in expired), None)))

    for vid, pkg, fix, hit, _ in accepted:
        print(f"ACCEPTED  {vid}  {pkg}  [{fix}]  until {hit['review_by']}: {hit['reason']}")
    for vid, pkg, fix, _, old in failing:
        note = f" (allowlist entry expired {old['review_by']} — review it)" if old else ""
        print(f"::error title={tool} vulnerability::{vid} in {pkg} [{fix}]{note}")
        print(f"VULNERABLE  {vid}  {pkg}  [{fix}]{note}")
    if skipped:
        print(f"note: {tool} could not check: {', '.join(skipped)}")

    if failing:
        print(f"RESULT: {len(failing)} VULNERABILITY FINDING(S) ({tool}).")
        return 1
    print(f"RESULT: scan completed, no unaccepted vulnerabilities ({tool}; {len(accepted)} accepted).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
