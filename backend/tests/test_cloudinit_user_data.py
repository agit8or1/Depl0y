"""build_deploy_user_data(): the cicustom snippet for cloud-image deploys."""
import yaml

from app.services.cloudinit import SSH_AUTH_DROPIN, UPGRADE_CMD, build_deploy_user_data


def _load(text):
    assert text.startswith("#cloud-config\n")
    return yaml.safe_load(text)


def test_ssh_ready_before_upgrade_and_hostname_set():
    d = _load(build_deploy_user_data("web1", "administrator", "pw"))
    assert d["hostname"] == "web1" and d["fqdn"] == "web1.local"
    assert d["packages"] == ["qemu-guest-agent", "openssh-server"]
    assert d["package_upgrade"] is False
    assert d["write_files"][0]["path"] == SSH_AUTH_DROPIN
    assert "PasswordAuthentication yes" in d["write_files"][0]["content"]
    run = d["runcmd"]
    assert run[0] == "systemctl enable --now qemu-guest-agent"
    assert run.index(UPGRADE_CMD) == len(run) - 1
    assert d["ssh_pwauth"] is True and d["users"][0]["lock_passwd"] is False


def test_password_with_yaml_special_characters_survives():
    pw = 'a#b: c"d\'e {x} - [y]'
    d = _load(build_deploy_user_data("h", "u", pw))
    assert d["chpasswd"]["list"] == f"u:{pw}\n"


def test_ssh_keys_and_extras_are_merged():
    extra = {
        "extra_packages": ["curl", "openssh-server"],
        "write_files": [{"path": "/opt/x.sh", "permissions": "0755", "encoding": "b64", "content": "ZWNobw=="}],
        "extra_runcmd": ["nohup bash /opt/x.sh &"],
    }
    d = _load(build_deploy_user_data("h", "u", "pw", ssh_keys="ssh-ed25519 AAA a\n\nssh-rsa BBB b\n", extra=extra))
    assert d["users"][0]["ssh_authorized_keys"] == ["ssh-ed25519 AAA a", "ssh-rsa BBB b"]
    assert d["packages"] == ["qemu-guest-agent", "openssh-server", "curl"]
    assert [w["path"] for w in d["write_files"]] == [SSH_AUTH_DROPIN, "/opt/x.sh"]
    # the extra commands run after the upgrade, as they did before (they may use apt)
    assert d["runcmd"][-2:] == [UPGRADE_CMD, "nohup bash /opt/x.sh &"]


def test_no_password_locks_the_account():
    d = _load(build_deploy_user_data("h", "u", None, ssh_keys="ssh-ed25519 AAA a"))
    assert "chpasswd" not in d and d["users"][0]["lock_passwd"] is True and d["ssh_pwauth"] is False


def test_never_restarts_ssh_socket_or_service():
    # Restarting ssh.socket/ssh while a socket-activated sshd listener runs (Ubuntu 24.04)
    # orphans the listener and leaves SSH broken for good. Only reload is allowed.
    from app.services.cloudinit import CloudInitService
    texts = [build_deploy_user_data("h", "u", "pw"), CloudInitService.generate_user_data("h", "u", "pw")]
    for text in texts:
        for cmd in yaml.safe_load(text)["runcmd"]:
            assert "restart ssh" not in cmd and "restart sshd" not in cmd and "start ssh " not in cmd, cmd
