"""ssh_address(): SSH goes to the LAN IP of the node serving the API, not the API hostname."""
import types

import app.services.host_ssh as hs


def _host(hid):
    return types.SimpleNamespace(id=hid, hostname="pve.example.net")


def _fake_service(status):
    class Svc:
        def __init__(self, host):
            self.proxmox = types.SimpleNamespace(cluster=types.SimpleNamespace(
                status=types.SimpleNamespace(get=status)))
    return Svc


def test_uses_local_node_ip(monkeypatch):
    import app.services.proxmox as px
    monkeypatch.setattr(px, "ProxmoxService", _fake_service(lambda: [
        {"type": "cluster", "name": "c"},
        {"type": "node", "name": "pve2", "ip": "10.0.0.5", "local": 0},
        {"type": "node", "name": "pve1", "ip": "10.0.0.4", "local": 1},
    ]))
    assert hs.ssh_address(_host(901)) == "10.0.0.4"


def test_falls_back_to_hostname_when_api_fails(monkeypatch):
    import app.services.proxmox as px
    def boom():
        raise RuntimeError("unreachable")
    monkeypatch.setattr(px, "ProxmoxService", _fake_service(boom))
    assert hs.ssh_address(_host(902)) == "pve.example.net"
