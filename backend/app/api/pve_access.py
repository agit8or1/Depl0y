"""Proxmox Users & Permissions management — dedicated access control router.

Endpoints mirror the Proxmox /access/* API tree and proxy through to the
configured Proxmox host identified by host_id.  All mutating operations
require admin privileges.
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Optional, List
from app.core.database import get_db
from app.models import ProxmoxHost
from app.api.auth import get_current_user, require_admin
from app.services.proxmox import ProxmoxService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_host(host_id: int, db: Session) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(
        ProxmoxHost.id == host_id,
        ProxmoxHost.is_active == True,
    ).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    return host


def _pve(host: ProxmoxHost):
    return ProxmoxService(host).proxmox


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/{host_id}/users")
def list_users(
    host_id: int,
    full: Optional[int] = 1,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """List all Proxmox users on the host (includes token counts when full=1)."""
    host = _get_host(host_id, db)
    try:
        params = {}
        if full is not None:
            params["full"] = full
        result = _pve(host).access.users.get(**params)
        return result or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/users")
def create_user(
    host_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Create a new Proxmox user.  Requires userid (user@realm) and password."""
    host = _get_host(host_id, db)
    try:
        _pve(host).access.users.post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/users/{userid:path}")
def update_user(
    host_id: int,
    userid: str,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Update an existing Proxmox user (name, email, enabled, expire, comment, groups)."""
    host = _get_host(host_id, db)
    try:
        _pve(host).access.users(userid).put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/users/{userid:path}")
def delete_user(
    host_id: int,
    userid: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Delete a Proxmox user."""
    host = _get_host(host_id, db)
    try:
        _pve(host).access.users(userid).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── User tokens ───────────────────────────────────────────────────────────────

@router.get("/{host_id}/users/{userid:path}/tokens")
def list_user_tokens(
    host_id: int,
    userid: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """List API tokens for a user."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.users(userid).token.get() or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/users/{userid:path}/tokens/{tokenid}")
def create_user_token(
    host_id: int,
    userid: str,
    tokenid: str,
    data: dict = Body(default={}),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Create an API token for a user.  Returns the token secret (shown once)."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.users(userid).token(tokenid).post(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/users/{userid:path}/tokens/{tokenid}")
def delete_user_token(
    host_id: int,
    userid: str,
    tokenid: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Revoke an API token."""
    host = _get_host(host_id, db)
    try:
        _pve(host).access.users(userid).token(tokenid).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Groups ────────────────────────────────────────────────────────────────────

@router.get("/{host_id}/groups")
def list_groups(
    host_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """List all Proxmox groups."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.groups.get() or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/groups/{groupid}")
def get_group(
    host_id: int,
    groupid: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Get a single group (includes member list)."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.groups(groupid).get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/groups")
def create_group(
    host_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Create a new Proxmox group."""
    host = _get_host(host_id, db)
    try:
        _pve(host).access.groups.post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/groups/{groupid}")
def update_group(
    host_id: int,
    groupid: str,
    data: dict = Body(default={}),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Update a group (comment etc.)."""
    host = _get_host(host_id, db)
    try:
        _pve(host).access.groups(groupid).put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/groups/{groupid}")
def delete_group(
    host_id: int,
    groupid: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Delete a Proxmox group."""
    host = _get_host(host_id, db)
    try:
        _pve(host).access.groups(groupid).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Roles ─────────────────────────────────────────────────────────────────────

@router.get("/{host_id}/roles")
def list_roles(
    host_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all Proxmox roles (built-in and custom)."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.roles.get() or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/roles")
def create_role(
    host_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Create a custom Proxmox role with the specified privilege set."""
    host = _get_host(host_id, db)
    try:
        _pve(host).access.roles.post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/roles/{roleid}")
def update_role(
    host_id: int,
    roleid: str,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Update the privilege set of a custom role."""
    host = _get_host(host_id, db)
    try:
        _pve(host).access.roles(roleid).put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/roles/{roleid}")
def delete_role(
    host_id: int,
    roleid: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Delete a custom role."""
    host = _get_host(host_id, db)
    try:
        _pve(host).access.roles(roleid).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── ACL ───────────────────────────────────────────────────────────────────────

@router.get("/{host_id}/acl")
def get_acl(
    host_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Return the full ACL tree (path / ugid / roleid / type / propagate)."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.acl.get() or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/acl")
def update_acl(
    host_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Add or remove an ACL entry.

    Required fields: path, roles, ugid.
    Set delete=1 to remove an existing entry.
    Set propagate=1 (default) to inherit permissions on sub-paths.
    """
    host = _get_host(host_id, db)
    try:
        _pve(host).access.acl.put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
