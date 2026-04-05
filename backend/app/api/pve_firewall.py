"""PVE Firewall — IPSets, Aliases, cluster-level firewall helpers"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import ProxmoxHost
from app.api.auth import get_current_user, require_operator, require_admin
from app.services.proxmox import ProxmoxService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_host(host_id: int, db: Session) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id, ProxmoxHost.is_active == True).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    return host


def _pve(host: ProxmoxHost):
    return ProxmoxService(host).proxmox


# ── IPSets ────────────────────────────────────────────────────────────────────

@router.get("/{host_id}/ipsets")
def list_ipsets(host_id: int, db: Session = Depends(get_db),
                current_user=Depends(get_current_user)):
    """List all cluster-level IP sets."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.firewall.ipset.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/ipsets")
def create_ipset(host_id: int, data: dict, db: Session = Depends(get_db),
                 current_user=Depends(require_admin)):
    """Create a new IP set."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.ipset.post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/ipsets/{name}")
def delete_ipset(host_id: int, name: str, db: Session = Depends(get_db),
                 current_user=Depends(require_admin)):
    """Delete an IP set (must be empty first)."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.ipset(name).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/ipsets/{name}")
def list_ipset_entries(host_id: int, name: str, db: Session = Depends(get_db),
                       current_user=Depends(get_current_user)):
    """List CIDRs in an IP set."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.firewall.ipset(name).get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/ipsets/{name}")
def add_ipset_entry(host_id: int, name: str, data: dict, db: Session = Depends(get_db),
                    current_user=Depends(require_admin)):
    """Add a CIDR to an IP set."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.ipset(name).post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/ipsets/{name}/{cidr}")
def remove_ipset_entry(host_id: int, name: str, cidr: str, db: Session = Depends(get_db),
                       current_user=Depends(require_admin)):
    """Remove a CIDR from an IP set."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.ipset(name)(cidr).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Aliases ───────────────────────────────────────────────────────────────────

@router.get("/{host_id}/aliases")
def list_aliases(host_id: int, db: Session = Depends(get_db),
                 current_user=Depends(get_current_user)):
    """List all cluster-level aliases."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.firewall.aliases.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/aliases")
def create_alias(host_id: int, data: dict, db: Session = Depends(get_db),
                 current_user=Depends(require_admin)):
    """Create a new alias."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.aliases.post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/aliases/{name}")
def update_alias(host_id: int, name: str, data: dict, db: Session = Depends(get_db),
                 current_user=Depends(require_admin)):
    """Update an alias."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.aliases(name).put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/aliases/{name}")
def delete_alias(host_id: int, name: str, db: Session = Depends(get_db),
                 current_user=Depends(require_admin)):
    """Delete an alias."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.aliases(name).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Cluster firewall rule update (enable/disable, reorder) ───────────────────

@router.put("/{host_id}/cluster/firewall/rules/{pos}")
def update_cluster_firewall_rule(host_id: int, pos: int, data: dict,
                                  db: Session = Depends(get_db),
                                  current_user=Depends(require_admin)):
    """Update a cluster firewall rule (e.g. enable/disable or change position)."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.rules(pos).put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Cluster firewall options ──────────────────────────────────────────────────

@router.get("/{host_id}/cluster/firewall/options")
def get_cluster_firewall_options(host_id: int, db: Session = Depends(get_db),
                                  current_user=Depends(get_current_user)):
    """Get cluster-level firewall options."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.firewall.options.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/cluster/firewall/options")
def set_cluster_firewall_options(host_id: int, data: dict,
                                  db: Session = Depends(get_db),
                                  current_user=Depends(require_admin)):
    """Set cluster-level firewall options."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.options.put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Security Groups ───────────────────────────────────────────────────────────

@router.get("/{host_id}/security-groups")
def list_security_groups(host_id: int, db: Session = Depends(get_db),
                          current_user=Depends(get_current_user)):
    """List all cluster-level security groups."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.firewall.groups.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/security-groups")
def create_security_group(host_id: int, data: dict, db: Session = Depends(get_db),
                           current_user=Depends(require_admin)):
    """Create a new security group."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.groups.post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/security-groups/{name}")
def delete_security_group(host_id: int, name: str, db: Session = Depends(get_db),
                           current_user=Depends(require_admin)):
    """Delete a security group."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.groups(name).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/security-groups/{name}")
def list_security_group_rules(host_id: int, name: str, db: Session = Depends(get_db),
                               current_user=Depends(get_current_user)):
    """List rules in a security group."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.firewall.groups(name).get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/security-groups/{name}")
def add_security_group_rule(host_id: int, name: str, data: dict,
                             db: Session = Depends(get_db),
                             current_user=Depends(require_admin)):
    """Add a rule to a security group."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.groups(name).post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/security-groups/{name}/{pos}")
def update_security_group_rule(host_id: int, name: str, pos: int, data: dict,
                                db: Session = Depends(get_db),
                                current_user=Depends(require_admin)):
    """Update a rule in a security group."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.groups(name)(pos).put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/security-groups/{name}/{pos}")
def delete_security_group_rule(host_id: int, name: str, pos: int,
                                db: Session = Depends(get_db),
                                current_user=Depends(require_admin)):
    """Delete a rule from a security group."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.groups(name)(pos).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Node-level firewall ───────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/firewall/rules")
def list_node_firewall_rules(host_id: int, node: str, db: Session = Depends(get_db),
                              current_user=Depends(get_current_user)):
    """List firewall rules for a specific node."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).firewall.rules.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/firewall/rules")
def add_node_firewall_rule(host_id: int, node: str, data: dict,
                            db: Session = Depends(get_db),
                            current_user=Depends(require_admin)):
    """Add a firewall rule to a node."""
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).firewall.rules.post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/nodes/{node}/firewall/rules/{pos}")
def update_node_firewall_rule(host_id: int, node: str, pos: int, data: dict,
                               db: Session = Depends(get_db),
                               current_user=Depends(require_admin)):
    """Update a node firewall rule."""
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).firewall.rules(pos).put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/nodes/{node}/firewall/rules/{pos}")
def delete_node_firewall_rule(host_id: int, node: str, pos: int,
                               db: Session = Depends(get_db),
                               current_user=Depends(require_admin)):
    """Delete a node firewall rule."""
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).firewall.rules(pos).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/firewall/options")
def get_node_firewall_options(host_id: int, node: str, db: Session = Depends(get_db),
                               current_user=Depends(get_current_user)):
    """Get node firewall options."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).firewall.options.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/nodes/{node}/firewall/options")
def set_node_firewall_options(host_id: int, node: str, data: dict,
                               db: Session = Depends(get_db),
                               current_user=Depends(require_admin)):
    """Set node firewall options (enable/disable, policies)."""
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).firewall.options.put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
