"""scripts/security/audit_report.py keeps "vulnerable" and "scanner failed" apart."""
import importlib.util
import json
import pathlib

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "security" / "audit_report.py"
spec = importlib.util.spec_from_file_location("audit_report", SCRIPT)
audit_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_report)


def _run(tmp_path, tool, report, code="1"):
    path = tmp_path / "r.json"
    if report is not None:
        path.write_text(report if isinstance(report, str) else json.dumps(report))
    return audit_report.main(["x", tool, str(path), code])


def _pip(*vulns):
    return {"dependencies": [{"name": "pkg", "version": "1.0", "vulns": list(vulns)}]}


def test_clean_scan_passes(tmp_path):
    assert _run(tmp_path, "pip", {"dependencies": [{"name": "pkg", "version": "1.0", "vulns": []}]}, "0") == 0
    assert _run(tmp_path, "npm", {"vulnerabilities": {}, "metadata": {}}, "0") == 0


def test_vulnerability_fails_with_1(tmp_path, capsys):
    assert _run(tmp_path, "pip", _pip({"id": "PYSEC-1", "aliases": [], "fix_versions": ["1.1"]})) == 1
    assert "VULNERABLE  PYSEC-1" in capsys.readouterr().out
    npm = {"vulnerabilities": {"x": {"via": [{"url": "https://github.com/advisories/GHSA-a", "range": "<2",
                                              "severity": "high", "title": "t"}], "fixAvailable": True}}}
    assert _run(tmp_path, "npm", npm) == 1


def test_scanner_failure_is_2_not_a_finding(tmp_path, capsys):
    assert _run(tmp_path, "pip", None) == 2
    assert _run(tmp_path, "pip", "not json") == 2
    assert _run(tmp_path, "npm", {"error": {"code": "ENOTFOUND", "summary": "registry unreachable"}}) == 2
    assert "SCANNER FAILURE" in capsys.readouterr().out


def test_allowlisted_advisory_is_accepted_until_review_date(tmp_path, monkeypatch):
    allow = tmp_path / "allow.json"
    monkeypatch.setattr(audit_report, "ALLOWLIST", allow)
    vuln = {"id": "PYSEC-9", "aliases": ["CVE-9"], "fix_versions": []}
    allow.write_text(json.dumps([{"id": "CVE-9", "reason": "mitigated", "review_by": "2999-01-01"}]))
    assert _run(tmp_path, "pip", _pip(vuln, vuln)) == 0
    allow.write_text(json.dumps([{"id": "CVE-9", "reason": "mitigated", "review_by": "2000-01-01"}]))
    assert _run(tmp_path, "pip", _pip(vuln)) == 1


def test_repo_allowlist_entries_have_reason_and_review_date():
    for e in json.loads((SCRIPT.parent / "audit-allowlist.json").read_text()):
        assert e["id"] and e["reason"] and len(e["review_by"]) == 10
