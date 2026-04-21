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
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.security import decode_token, decrypt_data
from app.models import ProxmoxHost, User
from app.services.proxmox import ProxmoxService
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# SPICE .vv file format template
# ---------------------------------------------------------------------------

_SPICE_VV_TEMPLATE = """\
[virt-viewer]
type=spice
host={host}
port={port}
password={password}
tls-port={tls_port}
fullscreen=0
title={title}
enable-smartcard=0
enable-usb-autoshare=1
delete-this-file=1
usb-filter=-1,-1,-1,-1,0
toggle-fullscreen=shift+f11
release-cursor=shift+f12
"""

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


def _get_node_ip(svc, node: str, fallback_host: str) -> str:
    """
    Return the direct IP address for a Proxmox node so that VNC WebSocket
    connections go straight to the node rather than through the cluster VIP.
    The cluster VIP cannot proxy WebSocket streams cross-node (returns HTTP 500).
    """
    try:
        cluster_status = svc.proxmox.cluster.status.get()
        for entry in cluster_status:
            if entry.get("type") == "node" and entry.get("name") == node:
                ip = entry.get("ip")
                logger.debug("cluster_status node=%s entry=%s ip=%s", node, entry, ip)
                if ip:
                    return ip
        # Log all node entries to diagnose missing IP
        node_entries = [e for e in cluster_status if e.get("type") == "node"]
        logger.warning("_get_node_ip: node=%s not found with ip. nodes in cluster: %s", node, node_entries)
    except Exception as exc:
        logger.warning("_get_node_ip failed: %s", exc)
    return fallback_host


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
    frames_to_client = 0
    frames_to_proxmox = 0

    async def client_to_proxmox():
        nonlocal frames_to_proxmox
        try:
            while True:
                # Use receive() to handle both binary and text frames without crashing
                msg = await ws_client.receive()
                logger.debug("client→proxmox msg type=%s bytes=%s text=%s",
                             msg.get("type"), len(msg.get("bytes") or b""), bool(msg.get("text")))
                if msg["type"] == "websocket.disconnect":
                    logger.info("client→proxmox: browser disconnected (code=%s)", msg.get("code"))
                    break
                if "bytes" in msg and msg["bytes"] is not None:
                    await ws_proxmox.send(msg["bytes"])
                    frames_to_proxmox += 1
                elif "text" in msg and msg["text"] is not None:
                    await ws_proxmox.send(msg["text"])
                    frames_to_proxmox += 1
        except (WebSocketDisconnect, websockets.exceptions.ConnectionClosed) as exc:
            logger.info("client→proxmox: connection closed: %s", exc)
        except Exception as exc:
            logger.info("client→proxmox relay error: %s", exc)

    async def proxmox_to_client():
        nonlocal frames_to_client
        try:
            async for message in ws_proxmox:
                frames_to_client += 1
                if frames_to_client == 1:
                    preview = message[:20] if isinstance(message, bytes) else message[:20].encode()
                    logger.info("proxmox→client first frame: %d bytes, preview=%r", len(message), preview)
                if isinstance(message, bytes):
                    await ws_client.send_bytes(message)
                else:
                    await ws_client.send_text(message)
        except (WebSocketDisconnect, websockets.exceptions.ConnectionClosed) as exc:
            logger.info("proxmox→client: connection closed: %s", exc)
        except Exception as exc:
            logger.info("proxmox→client relay error: %s", exc)

    task1 = asyncio.create_task(client_to_proxmox())
    task2 = asyncio.create_task(proxmox_to_client())
    done, pending = await asyncio.wait(
        [task1, task2], return_when=asyncio.FIRST_COMPLETED
    )
    logger.info("relay done: frames_to_client=%d frames_to_proxmox=%d done_tasks=%d",
                frames_to_client, frames_to_proxmox, len(done))
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
# SPICE proxy endpoint (REST — returns .vv file)
# ---------------------------------------------------------------------------

@router.get("/spice/{host_id}/{node}/{vmid}", response_class=PlainTextResponse)
def get_vm_spice(
    host_id: int,
    node: str,
    vmid: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Request a SPICE connection file (.vv format) for a QEMU VM.

    Calls Proxmox spiceproxy, formats the returned parameters as a
    virt-viewer compatible .vv file, and returns it as plain text
    (the frontend downloads it directly).
    """
    host = _get_host_or_none(db, host_id)
    if host is None or not host.is_active:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    try:
        svc = ProxmoxService(host)
        # The Proxmox spiceproxy API requires a 'proxy' parameter — the address
        # the SPICE client should connect to.  We use the Proxmox host's own
        # hostname/IP as the proxy since Proxmox will redirect SPICE there.
        proxy_host = host.hostname or host.host or "localhost"
        result = svc.proxmox.nodes(node).qemu(vmid).spiceproxy.post(proxy=proxy_host)

        spice_host = result.get("host", proxy_host)
        port = result.get("port", "-1")
        tls_port = result.get("tls-port", "-1")
        password = result.get("password", "")
        title = f"VM {vmid} on {node}"

        vv_content = _SPICE_VV_TEMPLATE.format(
            host=spice_host,
            port=port,
            password=password,
            tls_port=tls_port,
            title=title,
        )

        return Response(
            content=vv_content,
            media_type="application/x-virt-viewer",
            headers={
                "Content-Disposition": f'attachment; filename="vm-{vmid}-spice.vv"'
            },
        )
    except Exception as exc:
        logger.error("Failed to get SPICE proxy for VM %s/%s/%s: %s", host_id, node, vmid, exc)
        raise HTTPException(status_code=502, detail=f"Failed to obtain SPICE connection: {exc}")


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
    ticket: Optional[str] = Query(default=None),
    port: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint that proxies VNC for a QEMU VM.

    The browser connects here; this handler authenticates the user, then opens
    a WebSocket to Proxmox and relays all traffic bidirectionally.

    If 'ticket' and 'port' query params are provided (pre-fetched by the frontend),
    they are used directly to avoid a second vncproxy call which would conflict
    with the first. Otherwise a fresh vncproxy call is made.
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

        svc = ProxmoxService(host)

        if ticket and port:
            # Reuse the ticket+port the frontend already fetched — avoids double vncproxy
            vnc_ticket = ticket
            vnc_port = port
        else:
            # Fallback: request a fresh VNC ticket from Proxmox
            try:
                ticket_data = svc.proxmox.nodes(node).qemu(vmid).vncproxy.post(websocket=1)
                vnc_port = ticket_data["port"]
                vnc_ticket = ticket_data["ticket"]
            except Exception as exc:
                logger.error("Failed to get VNC ticket for VM %s/%s/%s: %s", host_id, node, vmid, exc)
                await websocket.close(code=4502, reason="Failed to obtain VNC ticket")
                return

        encoded_ticket = urllib.parse.quote(vnc_ticket, safe="")
        # Use cluster VIP (host.hostname) — direct node IPs return empty response
        # for vncwebsocket connections; the cluster VIP correctly routes to all nodes.
        proxmox_url = (
            f"wss://{host.hostname}:{host.port}/api2/json/nodes/{node}"
            f"/qemu/{vmid}/vncwebsocket?port={vnc_port}&vncticket={encoded_ticket}"
        )
        auth_headers = _build_auth_header(host)
        logger.info(
            "VNC connecting: node=%s host=%s port=%s ticket_source=%s ticket_len=%d ticket_prefix=%s auth_keys=%s",
            node, host.hostname, vnc_port,
            "frontend" if (ticket and port) else "fresh",
            len(vnc_ticket),
            vnc_ticket[:20],
            list(auth_headers.keys()),
        )
        ssl_ctx = _make_ssl_context()

        # Log browser WebSocket headers for diagnosing proxy chain issues
        ws_headers = dict(websocket.scope.get("headers", []))
        logger.info(
            "VNC browser headers: key=%s proto=%s origin=%s extensions=%s client=%s",
            ws_headers.get(b"sec-websocket-key", b"(none)").decode("latin-1", errors="replace"),
            ws_headers.get(b"sec-websocket-protocol", b"(none)").decode("latin-1", errors="replace"),
            ws_headers.get(b"origin", b"(none)").decode("latin-1", errors="replace"),
            ws_headers.get(b"sec-websocket-extensions", b"(none)").decode("latin-1", errors="replace"),
            websocket.scope.get("client"),
        )

        try:
            async with websockets.connect(
                proxmox_url,
                additional_headers=auth_headers,
                ssl=ssl_ctx,
                subprotocols=["binary"],
            ) as ws_proxmox:
                logger.info(
                    "VNC proxy opened: user=%s host=%s node=%s vmid=%s subprotocol=%s",
                    user.username, host.name, node, vmid,
                    ws_proxmox.subprotocol,
                )
                # Accept the browser WebSocket AFTER the Proxmox connection is ready so
                # the browser receives RFB data immediately after the WS handshake.
                # Strip Sec-WebSocket-Extensions from scope headers before accepting so
                # uvicorn does NOT negotiate permessage-deflate compression. uvicorn 0.24
                # auto-negotiates this extension; NPM then strips it from the 101 response
                # before forwarding to Chrome. Chrome receives RSV1=1 compressed frames
                # without knowing compression was negotiated → protocol error → code 1006.
                websocket.scope["headers"] = [
                    (k, v) for k, v in websocket.scope.get("headers", [])
                    if k.lower() != b"sec-websocket-extensions"
                ]
                await websocket.accept(subprotocol=("binary" if "binary" in (websocket.scope.get("subprotocols") or []) else None))
                await _relay(websocket, ws_proxmox)
            logger.info("VNC relay ended cleanly: user=%s vmid=%s", user.username, vmid)
            try:
                await websocket.close(code=1000, reason="Session ended")
            except Exception:
                pass
        except websockets.exceptions.InvalidHandshake as exc:
            logger.error("VNC proxy handshake failed (bad ticket/port?): %s", exc)
            try:
                await websocket.close(code=4502, reason="Proxmox VNC handshake failed")
            except Exception:
                pass
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
                websocket.scope["headers"] = [
                    (k, v) for k, v in websocket.scope.get("headers", [])
                    if k.lower() != b"sec-websocket-extensions"
                ]
                await websocket.accept(subprotocol=("binary" if "binary" in (websocket.scope.get("subprotocols") or []) else None))
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
                websocket.scope["headers"] = [
                    (k, v) for k, v in websocket.scope.get("headers", [])
                    if k.lower() != b"sec-websocket-extensions"
                ]
                await websocket.accept(subprotocol=("binary" if "binary" in (websocket.scope.get("subprotocols") or []) else None))
                await _relay(websocket, ws_proxmox)
        except Exception as exc:
            logger.error("Node terminal proxy connection failed: %s", exc)
            try:
                await websocket.close(code=4502, reason="Proxmox terminal connection failed")
            except Exception:
                pass
    finally:
        db.close()
