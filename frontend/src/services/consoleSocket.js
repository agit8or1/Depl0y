// Console WebSocket URLs carry a single-use ticket (valid ~30 s, bound to the
// user and to this exact target), never the access token, so nothing reusable
// ends up in proxy or server access logs. Ask for a fresh URL on every
// (re)connect: a ticket works once.
import api from '@/services/api'

export async function consoleSocketUrl (kind, hostId, node, vmid = null, extraParams = {}) {
  const { data } = await api.pveConsole.wsTicket({
    kind,
    host_id: Number(hostId),
    node: String(node),
    vmid: vmid == null ? null : Number(vmid),
  })
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const segs = [hostId, node].concat(kind === 'node' ? [] : [vmid]).map(s => encodeURIComponent(String(s)))
  const qs = new URLSearchParams({ ws_ticket: data.ticket, ...extraParams })
  return `${proto}//${location.host}/api/v1/pve-console/ws/${kind}/${segs.join('/')}?${qs}`
}
