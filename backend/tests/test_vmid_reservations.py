"""reserve_vmid(): concurrent deploys never get the same VMID."""
import threading
import time
import types

import app.services.vmid_reservations as vr


class FakePVE:
    """/cluster/nextid keeps answering the lowest unused VMID until a VM really exists."""

    def __init__(self, used):
        self.used = set(used)
        self.cluster = types.SimpleNamespace(
            nextid=types.SimpleNamespace(get=self._nextid),
            resources=types.SimpleNamespace(get=lambda type=None: [{"vmid": v} for v in sorted(self.used)]),
        )

    def _nextid(self):
        time.sleep(0.01)   # widen the race window
        v = 100
        while v in self.used:
            v += 1
        return v


def test_concurrent_reservations_are_unique():
    vr._held.clear()
    pve = FakePVE(used={100, 101, 103})
    got, barrier = [], threading.Barrier(20)

    def worker():
        barrier.wait()
        got.append(vr.reserve_vmid(pve))

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(got)) == 20
    assert not set(got) & {100, 101, 103}
    vr._held.clear()


def test_release_and_expiry_make_a_vmid_available_again():
    vr._held.clear()
    pve = FakePVE(used={100})
    a = vr.reserve_vmid(pve)
    assert vr.reserve_vmid(pve) == a + 1
    vr.release_vmid(a)
    assert vr.reserve_vmid(pve) == a
    vr._held.clear()
    vr.reserve_vmid(pve, ttl=-1)               # already expired
    assert vr.reserve_vmid(pve) == 101


def test_deploy_releases_its_vmid_even_when_it_fails(monkeypatch):
    from app.services.deployment import DeploymentService
    vr._held.clear()
    svc = DeploymentService(db=None)

    def failing_deploy(vm_id):
        svc._reserved_vmids.append(vr.reserve_vmid(FakePVE(used=set())))
        raise RuntimeError("boom")

    monkeypatch.setattr(svc, "_deploy_linux_vm", failing_deploy)
    try:
        svc.deploy_linux_vm(1)
    except RuntimeError:
        pass
    assert vr._held == {} and svc._reserved_vmids == []
