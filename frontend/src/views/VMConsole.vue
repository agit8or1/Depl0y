<template>
  <div class="vm-console-page">
    <!-- Toolbar -->
    <div class="console-toolbar">
      <div class="toolbar-left">
        <router-link :to="`/proxmox/${hostId}/nodes/${node}`" class="back-link">← {{ node }}</router-link>
        <div class="vm-info">
          <span class="vm-name">{{ vmName || `VM ${vmid}` }}</span>
          <span class="vm-id-badge">VMID {{ vmid }}</span>
          <span :class="['status-pill', vmStatus]">{{ vmStatus || 'unknown' }}</span>
          <span class="type-pill">QEMU</span>
        </div>
      </div>
      <div class="toolbar-center">
        <span :class="['conn-badge', connectionStatus]">{{ connStatusLabel }}</span>
      </div>
      <div class="toolbar-right">
        <button v-if="connectionStatus === 'connected'" @click="sendCtrlAltDel" class="btn-toolbar" title="Send Ctrl+Alt+Del">
          Ctrl+Alt+Del
        </button>
        <button @click="toggleFullscreen" class="btn-toolbar" title="Fullscreen">
          Fullscreen
        </button>
        <button v-if="connectionStatus !== 'connecting' && connectionStatus !== 'connected'" @click="connect" class="btn-toolbar btn-connect">
          Connect
        </button>
        <button v-if="connectionStatus === 'connected' || connectionStatus === 'connecting'" @click="disconnect" class="btn-toolbar btn-disconnect">
          Disconnect
        </button>
      </div>
    </div>

    <!-- Console canvas area -->
    <div class="console-area">
      <!-- noVNC canvas target -->
      <div id="novnc-screen" ref="canvasRef" class="novnc-screen"></div>

      <!-- Overlay: connecting -->
      <div v-if="connectionStatus === 'connecting'" class="overlay">
        <div class="spinner"></div>
        <p>Connecting to VM console…</p>
      </div>

      <!-- Overlay: idle / disconnected / error -->
      <div v-if="connectionStatus !== 'connecting' && connectionStatus !== 'connected'" class="overlay overlay-dark">
        <div class="overlay-content">
          <div class="console-icon">&#9654;</div>
          <h3>{{ vmName || `VM ${vmid}` }} — VNC Console</h3>
          <p class="subtitle">Node: <strong>{{ node }}</strong> &nbsp;|&nbsp; VMID: <strong>{{ vmid }}</strong></p>

          <div v-if="connectionStatus === 'error'" class="error-box">
            <strong>Error:</strong> {{ errorMessage }}
          </div>

          <div v-if="connectionStatus === 'disconnected' && !errorMessage" class="info-box">
            Console disconnected.
          </div>

          <!-- VNC info panel -->
          <div v-if="ticketData" class="info-panel">
            <div class="info-row">
              <span class="info-key">VNC Port</span>
              <code class="info-val">{{ ticketData.port }}</code>
            </div>
            <div class="info-row">
              <span class="info-key">WebSocket proxy</span>
              <code class="info-val">/api/v1/pve-console/ws/vm/{{ hostId }}/{{ node }}/{{ vmid }}</code>
            </div>
            <div class="info-row">
              <span class="info-key">Proxmox Web UI</span>
              <a v-if="proxmoxConsoleUrl !== '#'" :href="proxmoxConsoleUrl" target="_blank" rel="noopener" class="ext-link">
                Open in Proxmox &rarr;
              </a>
              <span v-else class="info-val muted">—</span>
            </div>
          </div>

          <div class="overlay-actions">
            <button @click="connect" class="btn-primary-lg" :disabled="loadingTicket">
              {{ loadingTicket ? 'Loading…' : (connectionStatus === 'disconnected' ? 'Reconnect' : 'Connect') }}
            </button>
            <button v-if="ticketData" @click="copyWsUrl" class="btn-secondary-lg">
              Copy WS URL
            </button>
            <a v-if="proxmoxConsoleUrl !== '#'" :href="proxmoxConsoleUrl" target="_blank" rel="noopener" class="btn-secondary-lg">
              Proxmox Web UI
            </a>
          </div>

          <p class="note">
            Full in-browser VNC is provided via noVNC loaded from CDN.
            If the connection fails, use the Proxmox Web UI link above.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import toast from '@/plugins/toast.js'

const route = useRoute()
const hostId = computed(() => route.params.hostId)
const node = computed(() => route.params.node)
const vmid = computed(() => route.params.vmid)

const connectionStatus = ref('idle')   // idle | connecting | connected | disconnected | error
const errorMessage = ref('')
const vmName = ref('')
const vmStatus = ref('')
const ticketData = ref(null)
const hostInfo = ref(null)
const loadingTicket = ref(false)
const canvasRef = ref(null)

let rfb = null

const connStatusLabel = computed(() => {
  const map = {
    idle: 'Not connected',
    connecting: 'Connecting…',
    connected: 'Connected',
    disconnected: 'Disconnected',
    error: 'Error',
  }
  return map[connectionStatus.value] || connectionStatus.value
})

const proxmoxConsoleUrl = computed(() => {
  if (!hostInfo.value) return '#'
  const h = hostInfo.value
  const hostname = h.hostname || h.host || ''
  const port = h.port || 8006
  const name = encodeURIComponent(vmName.value || `vm-${vmid.value}`)
  return `https://${hostname}:${port}/?console=kvm&novnc=1&vmid=${vmid.value}&vmname=${name}&node=${node.value}&resize=off&cmd=`
})

function buildWsUrl() {
  const token = localStorage.getItem('access_token') || ''
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/api/v1/pve-console/ws/vm/${hostId.value}/${node.value}/${vmid.value}?token=${encodeURIComponent(token)}`
}

async function fetchVmInfo() {
  try {
    const res = await api.pveVm.getStatus(hostId.value, node.value, vmid.value)
    vmName.value = res.data?.name || ''
    vmStatus.value = res.data?.status || ''
  } catch (e) {
    // non-fatal
  }
}

async function getTicketAndHost() {
  loadingTicket.value = true
  try {
    const [ticketRes, hostRes] = await Promise.all([
      api.pveVm.getVncTicket(hostId.value, node.value, vmid.value),
      api.proxmox.getHost(hostId.value),
    ])
    ticketData.value = ticketRes.data
    hostInfo.value = hostRes.data
    return true
  } catch (e) {
    errorMessage.value = e?.response?.data?.detail || e.message || 'Failed to get VNC ticket'
    connectionStatus.value = 'error'
    return false
  } finally {
    loadingTicket.value = false
  }
}

async function connect() {
  connectionStatus.value = 'connecting'
  errorMessage.value = ''

  const ok = await getTicketAndHost()
  if (!ok) return

  try {
    // Attempt to load noVNC from CDN
    const { default: RFB } = await import('https://cdn.jsdelivr.net/npm/@novnc/novnc@1.4.0/core/rfb.js')

    if (rfb) {
      try { rfb.disconnect() } catch {}
      rfb = null
    }

    const wsUrl = buildWsUrl()
    rfb = new RFB(canvasRef.value, wsUrl)
    rfb.viewOnly = false
    rfb.scaleViewport = true
    rfb.resizeSession = true

    rfb.addEventListener('connect', () => {
      connectionStatus.value = 'connected'
    })

    rfb.addEventListener('disconnect', (e) => {
      if (e.detail?.clean === false) {
        connectionStatus.value = 'error'
        errorMessage.value = 'Connection lost unexpectedly.'
      } else {
        connectionStatus.value = 'disconnected'
      }
    })

    rfb.addEventListener('desktopname', (e) => {
      if (e.detail?.name) vmName.value = e.detail.name
    })

  } catch (e) {
    toast.error(`noVNC failed to load or connect: ${e.message || 'unknown error'}`)
    connectionStatus.value = 'error'
    errorMessage.value = `noVNC failed to load or connect: ${e.message}. Use the Proxmox Web UI console instead.`
  }
}

function disconnect() {
  if (rfb) {
    try { rfb.disconnect() } catch {}
    rfb = null
  }
  connectionStatus.value = 'disconnected'
}

function sendCtrlAltDel() {
  if (rfb && connectionStatus.value === 'connected') {
    rfb.sendCtrlAltDel()
  }
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(err => {
      toast.error(`Fullscreen failed: ${err.message}`)
    })
  } else {
    document.exitFullscreen()
  }
}

function copyWsUrl() {
  const url = buildWsUrl()
  navigator.clipboard.writeText(url).then(() => {
    toast.success('WebSocket URL copied to clipboard')
  }).catch(() => {
    toast.error('Failed to copy to clipboard')
  })
}

onMounted(async () => {
  await fetchVmInfo()
  // Auto-connect on mount
  connect()
})

onBeforeUnmount(() => {
  if (rfb) {
    try { rfb.disconnect() } catch {}
    rfb = null
  }
})
</script>

<style scoped>
.vm-console-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-height: 100vh;
  background: #0d1117;
  color: #c9d1d9;
  overflow: hidden;
  font-family: system-ui, sans-serif;
}

/* ---- Toolbar ---- */
.console-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
  min-height: 50px;
  gap: 1rem;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 1rem;
  min-width: 0;
}

.back-link {
  color: #58a6ff;
  text-decoration: none;
  font-size: 0.8rem;
  white-space: nowrap;
  flex-shrink: 0;
}

.back-link:hover { text-decoration: underline; }

.vm-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.vm-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: #f0f6fc;
}

.vm-id-badge {
  background: #21262d;
  border: 1px solid #30363d;
  color: #8b949e;
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  font-size: 0.75rem;
  font-family: monospace;
}

.status-pill {
  padding: 0.1rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: capitalize;
  background: #21262d;
  color: #8b949e;
  border: 1px solid #30363d;
}

.status-pill.running  { background: #0d2d1a; color: #3fb950; border-color: #1f6335; }
.status-pill.stopped  { background: #2d0d0d; color: #ff7b72; border-color: #6e1212; }

.type-pill {
  background: #1c2a3a;
  border: 1px solid #1f4068;
  color: #58a6ff;
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  font-size: 0.7rem;
  font-weight: 600;
}

.toolbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.conn-badge {
  padding: 0.2rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.conn-badge.idle         { background: #21262d; color: #8b949e; border: 1px solid #30363d; }
.conn-badge.connecting   { background: #3d2b00; color: #e3b341; border: 1px solid #6e4c00; }
.conn-badge.connected    { background: #0d2d1a; color: #3fb950; border: 1px solid #1f6335; }
.conn-badge.disconnected { background: #21262d; color: #8b949e; border: 1px solid #30363d; }
.conn-badge.error        { background: #2d0d0d; color: #ff7b72; border: 1px solid #6e1212; }

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.btn-toolbar {
  padding: 0.3rem 0.85rem;
  border-radius: 5px;
  border: 1px solid #30363d;
  background: #21262d;
  color: #c9d1d9;
  cursor: pointer;
  font-size: 0.8rem;
  transition: background 0.15s;
}

.btn-toolbar:hover { background: #30363d; }
.btn-connect    { background: #238636; border-color: #2ea043; color: #fff; }
.btn-connect:hover { background: #2ea043; }
.btn-disconnect { background: #da3633; border-color: #f85149; color: #fff; }
.btn-disconnect:hover { background: #f85149; }

/* ---- Console area ---- */
.console-area {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #000;
}

.novnc-screen {
  width: 100%;
  height: 100%;
}

.novnc-screen :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
  object-fit: contain;
}

/* ---- Overlays ---- */
.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 0.75rem;
  color: #c9d1d9;
  font-size: 0.9rem;
  background: rgba(13,17,23,0.85);
  z-index: 5;
}

.overlay-dark {
  background: #0d1117;
}

.overlay-content {
  max-width: 560px;
  width: 90%;
  text-align: center;
}

.console-icon {
  font-size: 2.5rem;
  color: #3fb950;
  margin-bottom: 0.75rem;
  line-height: 1;
}

.overlay-content h3 {
  margin: 0 0 0.25rem;
  font-size: 1.2rem;
  color: #f0f6fc;
}

.subtitle {
  font-size: 0.85rem;
  color: #8b949e;
  margin: 0 0 1.25rem;
}

.error-box {
  background: rgba(255,123,114,0.1);
  border: 1px solid rgba(255,123,114,0.4);
  border-radius: 6px;
  padding: 0.75rem 1rem;
  color: #ff7b72;
  font-size: 0.85rem;
  margin-bottom: 1.25rem;
  text-align: left;
}

.info-box {
  background: rgba(139,148,158,0.1);
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 0.6rem 1rem;
  color: #8b949e;
  font-size: 0.85rem;
  margin-bottom: 1.25rem;
}

.info-panel {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 0.875rem;
  margin-bottom: 1.25rem;
  text-align: left;
}

.info-row {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.3rem 0;
  border-bottom: 1px solid #21262d;
}

.info-row:last-child { border-bottom: none; }

.info-key {
  font-size: 0.75rem;
  color: #8b949e;
  min-width: 130px;
  flex-shrink: 0;
}

.info-val {
  font-family: 'Fira Mono', monospace;
  font-size: 0.78rem;
  color: #58a6ff;
  word-break: break-all;
}

.info-val.muted { color: #8b949e; font-family: inherit; }

.ext-link {
  font-size: 0.8rem;
  color: #3fb950;
  text-decoration: none;
}

.ext-link:hover { text-decoration: underline; }

.overlay-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.btn-primary-lg {
  background: #238636;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 0.55rem 1.5rem;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

.btn-primary-lg:hover:not(:disabled) { background: #2ea043; }
.btn-primary-lg:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary-lg {
  background: #21262d;
  color: #c9d1d9;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 0.55rem 1.25rem;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.15s;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

.btn-secondary-lg:hover { background: #30363d; }

.note {
  font-size: 0.78rem;
  color: #9ca3af;
  line-height: 1.5;
  margin: 0;
}

/* ---- Connecting spinner ---- */
.spinner {
  width: 2.25rem;
  height: 2.25rem;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #58a6ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
