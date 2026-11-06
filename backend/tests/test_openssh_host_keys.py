"""OpenSSH command-line calls (ssh/scp/ssh-copy-id) verify host keys like Paramiko does.

Runs the real `ssh` client against the disposable server from test_ssh_host_keys.
"""
import shutil
import subprocess

import paramiko
import pytest

from app.models.database import AuditLog, SshHostKey, SystemSettings
from app.services import ssh_trust
from app.services.ssh_trust import (
    HostKeyChangedError, HostKeyNotTrustedError, openssh_options, proxy_command_options, pve_hop_options,
)
from tests.test_ssh_host_keys import DisposableSSHServer, _restart_with, db, servers  # noqa: F401

pytestmark = pytest.mark.skipif(shutil.which("ssh") is None, reason="OpenSSH client not installed")


@pytest.fixture(autouse=True)
def _fresh_cache():
    ssh_trust._verified.clear()
    yield
    ssh_trust._verified.clear()


def _ssh(port, opts, cmd="true"):
    return subprocess.run(
        ["ssh", *opts, "-p", str(port), "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
         "-F", "/dev/null", "root@127.0.0.1", cmd],
        capture_output=True, text=True, timeout=30)


def _server(servers, key=None):  # noqa: F811
    return servers(key or paramiko.ECDSAKey.generate(), allow_none=True)


def test_first_contact_pins_key_and_ssh_runs_strict(db, servers):  # noqa: F811
    key = paramiko.ECDSAKey.generate()
    srv = _server(servers, key)
    opts = openssh_options("127.0.0.1", srv.port)
    assert "StrictHostKeyChecking=yes" in opts and "UpdateHostKeys=no" in opts
    p = _ssh(srv.port, opts, "echo hi")
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "ok"

    known = open(ssh_trust.KNOWN_HOSTS_FILE).read()
    assert f"[127.0.0.1]:{srv.port} {key.get_name()} {key.get_base64()}" in known
    assert db.query(SshHostKey).filter_by(status="approved").count() == 1


def test_changed_key_is_refused_before_ssh_runs(db, servers):  # noqa: F811
    srv = _server(servers)
    assert _ssh(srv.port, openssh_options("127.0.0.1", srv.port)).returncode == 0
    ssh_trust._verified.clear()

    impostor = _restart_with(servers, srv, paramiko.ECDSAKey.generate(), allow_none=True)
    with pytest.raises(HostKeyChangedError):
        openssh_options("127.0.0.1", impostor.port)
    assert impostor.auth_attempts == []
    assert db.query(SshHostKey).filter_by(status="pending").count() == 1
    assert db.query(AuditLog).filter(AuditLog.action == "ssh_host_key_changed_rejected").count() == 1


def test_ssh_itself_rejects_a_key_swapped_after_the_check(db, servers):  # noqa: F811
    """The pre-check is cached for a minute; ssh must still refuse on its own."""
    srv = _server(servers)
    opts = openssh_options("127.0.0.1", srv.port)
    assert _ssh(srv.port, opts).returncode == 0

    impostor = _restart_with(servers, srv, paramiko.ECDSAKey.generate(), allow_none=True)
    cached = openssh_options("127.0.0.1", impostor.port)   # skips the pre-check (cache)
    p = _ssh(impostor.port, cached)
    assert p.returncode == 255
    assert "Host key verification failed" in p.stderr or "IDENTIFICATION HAS CHANGED" in p.stderr
    assert impostor.auth_attempts == []


def test_unpinned_host_is_refused_by_ssh(db, servers):  # noqa: F811
    srv = _server(servers)
    p = _ssh(srv.port, ssh_trust._strict_options(ssh_trust.write_known_hosts()))
    assert p.returncode == 255 and srv.auth_attempts == []


def test_strict_policy_refuses_unknown_host(db, servers):  # noqa: F811
    db.add(SystemSettings(key=ssh_trust.POLICY_SETTING, value="strict"))
    db.commit()
    srv = _server(servers)
    with pytest.raises(HostKeyNotTrustedError):
        openssh_options("127.0.0.1", srv.port)
    [pending] = db.query(SshHostKey).filter_by(status="pending").all()
    ssh_trust.approve_host_key(db, pending, user_id=1)
    assert _ssh(srv.port, openssh_options("127.0.0.1", srv.port)).returncode == 0


def test_approved_rotation_is_used_by_ssh(db, servers):  # noqa: F811
    srv = _server(servers)
    assert _ssh(srv.port, openssh_options("127.0.0.1", srv.port)).returncode == 0
    ssh_trust._verified.clear()
    rotated = _restart_with(servers, srv, paramiko.ECDSAKey.generate(), allow_none=True)
    with pytest.raises(HostKeyChangedError):
        openssh_options("127.0.0.1", rotated.port)
    [pending] = db.query(SshHostKey).filter_by(status="pending").all()
    ssh_trust.approve_host_key(db, pending, user_id=1)
    assert _ssh(rotated.port, openssh_options("127.0.0.1", rotated.port)).returncode == 0


def test_unreachable_host_keys_are_read_via_the_jump_host(db, monkeypatch):  # noqa: F811
    key = paramiko.ECDSAKey.generate()

    def unreachable(*a, **kw):
        raise OSError("no route")
    monkeypatch.setattr(ssh_trust, "fetch_host_key", unreachable)
    calls = []
    monkeypatch.setattr(ssh_trust, "_keyscan_via", lambda jump, host, port: calls.append(jump) or [key])
    ssh_trust.ensure_host_key("10.9.9.9", scan_via="10.0.0.1")
    assert calls == ["10.0.0.1"]
    [row] = db.query(SshHostKey).filter_by(host="10.9.9.9").all()
    assert row.status == "approved" and row.fingerprint == ssh_trust.fingerprint(key)

    ssh_trust._verified.clear()
    monkeypatch.setattr(ssh_trust, "_keyscan_via", lambda *a: [paramiko.ECDSAKey.generate()])
    with pytest.raises(HostKeyChangedError):
        ssh_trust.ensure_host_key("10.9.9.9", scan_via="10.0.0.1")


def test_unreachable_host_without_jump_is_left_to_ssh(db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ssh_trust, "fetch_host_key", lambda *a, **kw: (_ for _ in ()).throw(OSError("down")))
    ssh_trust.ensure_host_key("10.9.9.8")   # no exception; ssh fails on its own (not in known_hosts)
    assert db.query(SshHostKey).count() == 0


def test_proxy_command_verifies_the_jump_host(db, servers, monkeypatch):  # noqa: F811
    seen = []
    monkeypatch.setattr(ssh_trust, "ensure_host_key", lambda h, p=22, scan_via=None: seen.append(h))
    [flag, value] = proxy_command_options("10.0.0.1")
    assert flag == "-o" and value.startswith("ProxyCommand=ssh ")
    assert "StrictHostKeyChecking=yes" in value and "-W %h:%p" in value and value.endswith("root@10.0.0.1")
    assert seen == ["10.0.0.1"]


def test_pve_hop_options_use_cluster_node_keys():
    opts = pve_hop_options("pve3")
    assert "HostKeyAlias=pve3" in opts
    assert "UserKnownHostsFile=/etc/pve/nodes/pve3/ssh_known_hosts" in opts
    assert "StrictHostKeyChecking=yes" in opts and "GlobalKnownHostsFile=none" in opts
    for bad in ("", "pve3;id", "pve 3", "../etc", "-oProxyCommand=x"):
        with pytest.raises(ValueError):
            pve_hop_options(bad)


def test_known_hosts_file_is_private(db, servers):  # noqa: F811
    import os
    import stat
    srv = _server(servers)
    openssh_options("127.0.0.1", srv.port)
    mode = stat.S_IMODE(os.stat(ssh_trust.KNOWN_HOSTS_FILE).st_mode)
    assert mode == 0o600


def _capture_runs(monkeypatch, module, rc=0):
    argvs = []

    def fake_run(argv, **kw):
        argvs.append(argv)
        return subprocess.CompletedProcess(argv, rc, stdout="out", stderr="err")
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    return argvs


def test_hazfs_verifies_node_and_jump(monkeypatch):
    from app.services import hazfs
    checked = []
    monkeypatch.setattr(ssh_trust, "ensure_host_key", lambda h, p=22, scan_via=None: checked.append((h, scan_via)))
    argvs = _capture_runs(monkeypatch, hazfs, rc=255)
    with pytest.raises(RuntimeError):
        hazfs.run_on_node("10.0.0.5", "true", jump="10.0.0.4")
    direct, via_jump = argvs
    assert "StrictHostKeyChecking=yes" in direct and direct[-2:] == ["root@10.0.0.5", "true"]
    assert any(a.startswith("ProxyCommand=ssh ") and "root@10.0.0.4" in a for a in via_jump)
    assert ("10.0.0.5", "10.0.0.4") in checked and ("10.0.0.4", None) in checked


def test_vm_import_ssh_is_verified(monkeypatch):
    from app.services import vm_import_service
    checked = []
    monkeypatch.setattr(ssh_trust, "ensure_host_key", lambda h, p=22, scan_via=None: checked.append(h))
    argvs = _capture_runs(monkeypatch, vm_import_service)
    vm_import_service._ssh_run("10.0.0.4", "qm list")
    assert checked == ["10.0.0.4"] and "StrictHostKeyChecking=yes" in argvs[0]


def test_changed_key_stops_the_command_from_running(monkeypatch):
    from app.services import vm_import_service

    def changed(h, p=22, scan_via=None):
        raise HostKeyChangedError("changed", h, p, "SHA256:x")
    monkeypatch.setattr(ssh_trust, "ensure_host_key", changed)
    argvs = _capture_runs(monkeypatch, vm_import_service)
    with pytest.raises(HostKeyChangedError):
        vm_import_service._ssh_run("10.0.0.4", "qm list")
    assert argvs == []
