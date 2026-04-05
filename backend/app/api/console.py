"""
WebSocket proxy endpoints for Proxmox VNC (noVNC) and xterm.js terminal access.

Provides:
  GET  /ticket/{host_id}/{node}/{vmid}      — VNC ticket for QEMU VMs
  GET  /lxc-ticket/{host_id}/{node}/{ctid}  — terminal ticket for LXC containers
  WS   /ws/vm/{host_id}/{node}/{vmid}       — VNC proxy for QEMU VMs
  WS   /ws/lxc/{host_id}/{node}/{vmid}      — terminal proxy for LXC containers
  WS   /ws/node/{host_id}/{node}            — terminal proxy for node shell
"""
import asyncio
import logging
import ssl
import urllib.parse
from typing import Optional

import websockets
import websockets.exceptions
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.security import decode_token, decrypt_data
from app.models import ProxmoxHost, User
from app.services.proxmox import ProxmoxService
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ssl_context() -> ssl.SSLContext:
    """Return an SSL context that skips verification (Proxmox self-signed certs)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _get_db() -> Session:
    return SessionLocal()


async def _authenticate(token: Optional[str], db: Session) -> Optional[User]:
    """Validate JWT token and return the User, or None on failure."""
    if not token:
        return None
    payload = decode_token(token)
    if payload is None:
        return None
    username: Optional[str] = payload.get("sub")
    if not username:
        return None
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return None
    return user


def _get_host_or_none(db: Session, host_id: int) -> Optional[ProxmoxHost]:
    return db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()


def _build_auth_header(host: ProxmoxHost) -> dict:
    """Build the Authorization header for the outbound Proxmox WebSocket."""
    if host.api_token_id and host.api_token_secret:
        try:
            secret = decrypt_data(host.api_token_secret)
        except Exception:
            secret = host.api_token_secret
        return {"Authorization": f"PVEAPIToken={host.api_token_id}={secret}"}
    # Fallback: no token configured — caller should handle
    return {}


async def _relay(ws_client: WebSocket, ws_proxmox):
    """
    Bidirectionally relay bytes/text between the browser WebSocket and
    the outbound Proxmox WebSocket until either side closes.
    """
    async def client_to_proxmox():
        try:
            while True:
                data = await ws_client.receive_bytes()
                await ws_proxmox.send(data)
        except (WebSocketDisconnect, websockets.exceptions.ConnectionClosed):
            pass
        except Exception as exc:
            logger.debug("client→proxmox relay error: %s", exc)

    async def proxmox_to_client():
        try:
            async for message in ws_proxmox:
                if isinstance(message, bytes):
                    await ws_client.send_bytes(message)
                else:
                    await ws_client.send_text(message)
        except (WebSocketDisconnect, websockets.exceptions.ConnectionClosed):
            pass
        except Exception as exc:
            logger.debug("proxmox→client relay error: %s", exc)

    task1 = asyncio.create_task(client_to_proxmox())
    task2 = asyncio.create_task(proxmox_to_client())
    done, pending = await asyncio.wait(
        [task1, task2], return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# Ticket endpoints (REST)
# ---------------------------------------------------------------------------

@router.get("/ticket/{host_id}/{node}/{vmid}")
def get_vm_vnc_ticket(
    host_id: int,
    node: str,
    vmid: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Request a VNC ticket for a QEMU VM from Proxmox and return it so the
    frontend can display metadata (port, ticket) before opening the WebSocket.
    """
    host = _get_host_or_none(db, host_id)
    if host is None or not host.is_active:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    try:
        svc = ProxmoxService(host)
        result = svc.proxmox.nodes(node).qemu(vmid).vncproxy.post(websocket=1)
        return {
            "ticket": result.get("ticket"),
            "port": result.get("port"),
            "host": host.hostname,
        }
    except Exception as exc:
        logger.error("Failed to get VNC ticket for VM %s/%s/%s: %s", host_id, node, vmid, exc)
        raise HTTPException(status_code=502, detail=f"Failed to obtain VNC ticket: {exc}")


@router.get("/lxc-ticket/{host_id}/{node}/{ctid}")
def get_lxc_ticket(
    host_id: int,
    node: str,
    ctid: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Request a terminal ticket for an LXC container from Proxmox.
    """
    host = _get_host_or_none(db, host_id)
    if host is None or not host.is_active:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    try:
        svc = ProxmoxService(host)
        result = svc.proxmox.nodes(node).lxc(ctid).termproxy.post()
        return {
            "ticket": result.get("ticket"),
            "port": result.get("port"),
            "host": host.hostname,
        }
    except Exception as exc:
        logger.error("Failed to get terminal ticket for LXC %s/%s/%s: %s", host_id, node, ctid, exc)
        raise HTTPException(status_code=502, detail=f"Failed to obtain terminal ticket: {exc}")


# ---------------------------------------------------------------------------
# Endpoint: QEMU VM VNC proxy
# ---------------------------------------------------------------------------

@router.websocket("/ws/vm/{host_id}/{node}/{vmid}")
async def vm_vnc_proxy(
    websocket: WebSocket,
    host_id: int,
    node: str,
    vmid: int,
    token: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint that proxies VNC for a QEMU VM.

    The browser connects here; this handler authenticates the user, requests a
    VNC ticket from Proxmox, then opens a WebSocket to Proxmox and relays all
    traffic bidirectionally.
    """
    db = _get_db()
    try:
        user = await _authenticate(token, db)
        if user is None:
            await websocket.close(code=4401, reason="Unauthorized")
            return

        host = _get_host_or_none(db, host_id)
        if host is None or not host.is_active:
            await websocket.close(code=4404, reason="Proxmox host not found")
            return

        # Accept the browser WebSocket before doing any async Proxmox work
        await websocket.accept(subprotocol="binary")

        # Request a VNC ticket from Proxmox (synchronous proxmoxer call)
        try:
            svc = ProxmoxService(host)
            ticket_data = svc.proxmox.nodes(node).qemu(vmid).vncproxy.post(websocket=1)
            port = ticket_data["port"]
            vnc_ticket = ticket_data["ticket"]
        except Exception as exc:
            logger.error("Failed to get VNC ticket for VM %s/%s/%s: %s", host_id, node, vmid, exc)
            await websocket.close(code=4502, reason="Failed to obtain VNC ticket")
            return

        encoded_ticket = urllib.parse.quote(vnc_ticket, safe="")
        proxmox_url = (
            f"wss://{host.hostname}:{host.port}/api2/json/nodes/{node}"
            f"/vncwebsocket?port={port}&vncticket={encoded_ticket}"
        )
        auth_headers = _build_auth_header(host)
        ssl_ctx = _make_ssl_context()

        try:
            async with websockets.connect(
                proxmox_url,
                additional_headers=auth_headers,
                ssl=ssl_ctx,
                subprotocols=["binary"],
            ) as ws_proxmox:
                logger.info(
                    "VNC proxy opened: user=%s host=%s node=%s vmid=%s",
                    user.username, host.name, node, vmid,
                )
                await _relay(websocket, ws_proxmox)
        except Exception as exc:
            logger.error("VNC proxy connection failed: %s", exc)
            try:
                await websocket.close(code=4502, reason="Proxmox VNC connection failed")
            except Exception:
                pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint: LXC container terminal proxy
# ---------------------------------------------------------------------------

@router.websocket("/ws/lxc/{host_id}/{node}/{vmid}")
async def lxc_terminal_proxy(
    websocket: WebSocket,
    host_id: int,
    node: str,
    vmid: int,
    token: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint that proxies an xterm.js terminal for an LXC container.

    Uses Proxmox termproxy to obtain a ticket, then connects to the vncwebsocket
    endpoint and relays traffic.
    """
    db = _get_db()
    try:
        user = await _authenticate(token, db)
        if user is None:
            await websocket.close(code=4401, reason="Unauthorized")
            return

        host = _get_host_or_none(db, host_id)
        if host is None or not host.is_active:
            await websocket.close(code=4404, reason="Proxmox host not found")
            return

        await websocket.accept(subprotocol="binary")

        try:
            svc = ProxmoxService(host)
            ticket_data = svc.proxmox.nodes(node).lxc(vmid).termproxy.post()
            port = ticket_data["port"]
            term_ticket = ticket_data["ticket"]
        except Exception as exc:
            logger.error(
                "Failed to get term ticket for LXC %s/%s/%s: %s", host_id, node, vmid, exc
            )
            await websocket.close(code=4502, reason="Failed to obtain terminal ticket")
            return

        encoded_ticket = urllib.parse.quote(term_ticket, safe="")
        proxmox_url = (
            f"wss://{host.hostname}:{host.port}/api2/json/nodes/{node}"
            f"/lxc/{vmid}/vncwebsocket?port={port}&vncticket={encoded_ticket}"
        )
        auth_headers = _build_auth_header(host)
        ssl_ctx = _make_ssl_context()

        try:
            async with websockets.connect(
                proxmox_url,
                additional_headers=auth_headers,
                ssl=ssl_ctx,
                subprotocols=["binary"],
            ) as ws_proxmox:
                logger.info(
                    "LXC terminal proxy opened: user=%s host=%s node=%s vmid=%s",
                    user.username, host.name, node, vmid,
                )
                await _relay(websocket, ws_proxmox)
        except Exception as exc:
            logger.error("LXC terminal proxy connection failed: %s", exc)
            try:
                await websocket.close(code=4502, reason="Proxmox terminal connection failed")
            except Exception:
                pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint: Node shell terminal proxy
# ---------------------------------------------------------------------------

@router.websocket("/ws/node/{host_id}/{node}")
async def node_terminal_proxy(
    websocket: WebSocket,
    host_id: int,
    node: str,
    token: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint that proxies an xterm.js shell terminal for a Proxmox node.

    Uses Proxmox node termproxy to obtain a ticket, then connects to the node
    vncwebsocket endpoint and relays traffic.
    """
    db = _get_db()
    try:
        user = await _authenticate(token, db)
        if user is None:
            await websocket.close(code=4401, reason="Unauthorized")
            return

        host = _get_host_or_none(db, host_id)
        if host is None or not host.is_active:
            await websocket.close(code=4404, reason="Proxmox host not found")
            return

        await websocket.accept(subprotocol="binary")

        try:
            svc = ProxmoxService(host)
            ticket_data = svc.proxmox.nodes(node).termproxy.post()
            port = ticket_data["port"]
            term_ticket = ticket_data["ticket"]
        except Exception as exc:
            logger.error(
                "Failed to get term ticket for node %s/%s: %s", host_id, node, exc
            )
            await websocket.close(code=4502, reason="Failed to obtain terminal ticket")
            return

        encoded_ticket = urllib.parse.quote(term_ticket, safe="")
        proxmox_url = (
            f"wss://{host.hostname}:{host.port}/api2/json/nodes/{node}"
            f"/vncwebsocket?port={port}&vncticket={encoded_ticket}"
        )
        auth_headers = _build_auth_header(host)
        ssl_ctx = _make_ssl_context()

        try:
            async with websockets.connect(
                proxmox_url,
                additional_headers=auth_headers,
                ssl=ssl_ctx,
                subprotocols=["binary"],
            ) as ws_proxmox:
                logger.info(
                    "Node terminal proxy opened: user=%s host=%s node=%s",
                    user.username, host.name, node,
                )
                await _relay(websocket, ws_proxmox)
        except Exception as exc:
            logger.error("Node terminal proxy connection failed: %s", exc)
            try:
                await websocket.close(code=4502, reason="Proxmox terminal connection failed")
            except Exception:
                pass
    finally:
        db.close()
