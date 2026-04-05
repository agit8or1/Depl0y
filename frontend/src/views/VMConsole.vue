<template>
  <div :class="['vm-console-page', { 'compact-mode': compactMode }]">
    <!-- Toolbar -->
    <div class="console-toolbar" v-if="!compactMode">
      <!-- Row 1: Identity + status -->
      <div class="toolbar-row toolbar-row-top">
        <div class="toolbar-left">
          <router-link v-if="!standaloneMode" :to="`/proxmox/${hostId}/nodes/${node}`" class="back-link">← {{ node }}</router-link>
          <div class="vm-info">
            <span class="vm-name">{{ vmName || `VM ${vmid}` }}</span>
            <span class="vm-id-badge">VMID {{ vmid }}</span>
            <span :class="['status-pill', vmStatus]">{{ vmStatus || 'unknown' }}</span>
            <span class="type-pill">QEMU</span>
          </div>
        </div>
        <div class="toolbar-center">
          <!-- Tab switcher -->
          <div class="console-tabs">
            <button
              v-for="tab in consoleTabs"
              :key="tab.id"
              :class="['console-tab-btn', activeConsoleTab === tab.id ? 'console-tab-btn--active' : '']"
              @click="switchConsoleTab(tab.id)"
            >{{ tab.label }}</button>
          </div>
        </div>
        <div class="toolbar-right">
          <!-- VNC-specific controls -->
          <template v-if="activeConsoleTab === 'vnc'">
            <span :class="['conn-badge', connectionStatus]">{{ connStatusLabel }}</span>
            <span v-if="sessionTimer" class="session-timer">{{ sessionTimer }}</span>
            <span v-if="disconnectReason" class="disconnect-reason">{{ disconnectReason }}</span>
            <!-- Quality selector -->
            <select v-if="connectionStatus === 'connected'" v-model="qualityLevel" @change="applyQuality" class="select-toolbar" title="Quality">
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
            <!-- Scale mode -->
            <select v-if="connectionStatus === 'connected'" v-model="scaleMode" @change="applyScaleMode" class="select-toolbar" title="Scale Mode">
              <option value="remote">Remote Resize</option>
              <option value="local">Local Scale</option>
              <option value="fixed">Fixed Size</option>
            </select>
            <!-- Screenshot -->
            <button v-if="connectionStatus === 'connected'" @click="takeScreenshot" class="btn-toolbar" title="Screenshot (PNG)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="4"/></svg>
            </button>
            <!-- Fullscreen -->
            <button @click="toggleFullscreen" class="btn-toolbar" title="Toggle Fullscreen (F11)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>
            </button>
            <!-- Open in new tab -->
            <button @click="openNewTab" class="btn-toolbar" title="Open in new tab">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </button>
            <!-- Compact toggle -->
            <button @click="compactMode = true" class="btn-toolbar" title="Hide toolbar (F11)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="10" y1="14" x2="21" y2="3"/><line x1="3" y1="21" x2="14" y2="10"/></svg>
            </button>
            <button v-if="connectionStatus !== 'connecting' && connectionStatus !== 'connected'" @click="connect" class="btn-toolbar btn-connect">
              Connect
            </button>
            <button v-if="connectionStatus === 'connected' || connectionStatus === 'connecting'" @click="disconnect" class="btn-toolbar btn-disconnect">
              Disconnect
            </button>
          </template>

          <!-- Serial terminal controls -->
          <template v-if="activeConsoleTab === 'serial'">
            <span :class="['conn-badge', serialStatus]">{{ serialStatusLabel }}</span>
            <button v-if="serialStatus !== 'connected' && serialStatus !== 'connecting'" @click="connectSerial" class="btn-toolbar btn-connect">Connect</button>
            <button v-if="serialStatus === 'connected' || serialStatus === 'connecting'" @click="disconnectSerial" class="btn-toolbar btn-disconnect">Disconnect</button>
            <button @click="clearTerminal" class="btn-toolbar" title="Clear terminal output">Clear</button>
          </template>
        </div>
      </div>

      <!-- Row 2: Key shortcuts (VNC only, when connected) -->
      <div v-if="activeConsoleTab === 'vnc' && connectionStatus === 'connected'" class="toolbar-row toolbar-row-keys">
        <button @click="sendCtrlAltDel" class="btn-key" title="Send Ctrl+Alt+Del">Ctrl+Alt+Del</button>
        <button @click="sendCtrlC" class="btn-key" title="Send Ctrl+C">Ctrl+C</button>
        <button @click="openClipboardModal" class="btn-key" title="Paste text through VNC">Paste Text</button>

        <div class="dropdown-wrap">
          <button class="btn-key dropdown-trigger" @click="showFxMenu = !showFxMenu">Ctrl+Alt+Fx ▾</button>
          <div v-if="showFxMenu" class="dropdown-menu" @mouseleave="showFxMenu = false">
            <button v-for="n in 7" :key="n" @click="sendCtrlAltFn(n); showFxMenu = false" class="dropdown-item">
              Ctrl+Alt+F{{ n }}
            </button>
          </div>
        </div>

        <div class="dropdown-wrap">
          <button class="btn-key dropdown-trigger" @click="showSpecialMenu = !showSpecialMenu">Special Keys ▾</button>
          <div v-if="showSpecialMenu" class="dropdown-menu" @mouseleave="showSpecialMenu = false">
            <button v-for="key in specialKeys" :key="key.label" @click="sendSpecialKey(key.code); showSpecialMenu = false" class="dropdown-item">
              {{ key.label }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Compact mode restore bar -->
    <div v-if="compactMode" class="compact-bar">
      <span class="compact-info">{{ vmName || `VM ${vmid}` }} — {{ connStatusLabel }}</span>
      <button @click="compactMode = false" class="btn-compact-restore" title="Show toolbar (F11)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="10" y1="14" x2="21" y2="3"/><line x1="3" y1="21" x2="14" y2="10"/></svg>
        Restore Toolbar
      </button>
    </div>

    <!-- ====================== VNC TAB ====================== -->
    <div v-show="activeConsoleTab === 'vnc'" class="console-area">
      <div id="novnc-screen" ref="canvasRef" class="novnc-screen"></div>

      <!-- Connecting overlay -->
      <div v-if="connectionStatus === 'connecting'" class="overlay">
        <div class="spinner"></div>
        <p>Connecting to VM console…</p>
        <p v-if="reconnectAttempt > 0" class="reconnect-note">Reconnect attempt {{ reconnectAttempt }}…</p>
      </div>

      <!-- Idle/disconnected/error overlay -->
      <div v-if="connectionStatus !== 'connecting' && connectionStatus !== 'connected'" class="overlay overlay-dark">
        <div class="overlay-content">
          <div class="console-icon">&#9654;</div>
          <h3>{{ vmName || `VM ${vmid}` }} — VNC Console</h3>
          <p class="subtitle">Node: <strong>{{ node }}</strong> &nbsp;|&nbsp; VMID: <strong>{{ vmid }}</strong></p>

          <div v-if="connectionStatus === 'error'" class="error-box">
            <strong>Error:</strong> {{ errorMessage }}
          </div>
          <div v-if="disconnectReason && connectionStatus === 'disconnected'" class="info-box">
            {{ disconnectReason }}
          </div>
          <div v-if="connectionStatus === 'disconnected' && !disconnectReason" class="info-box">
            Console disconnected.
          </div>

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
            <button @click="openNewTab" class="btn-secondary-lg">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px;vertical-align:middle"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              Open in New Window
            </button>
            <button @click="switchConsoleTab('spice')" class="btn-secondary-lg">
              SPICE Download
            </button>
          </div>

          <p class="note">
            Full in-browser VNC is provided via noVNC loaded from CDN.
            If the connection fails, use the Proxmox Web UI link above or try SPICE.
          </p>
        </div>
      </div>
    </div>

    <!-- ====================== SERIAL TERMINAL TAB ====================== -->
    <div v-show="activeConsoleTab === 'serial'" class="serial-area">
      <!-- Connection overlay -->
      <div v-if="serialStatus === 'idle' || serialStatus === 'disconnected' || serialStatus === 'error'" class="serial-connect-overlay">
        <div class="overlay-content">
          <div class="console-icon" style="color:#58a6ff;">&#9646;&#9646;</div>
          <h3>{{ vmName || `VM ${vmid}` }} — Serial Terminal</h3>
          <p class="subtitle">Node: <strong>{{ node }}</strong> &nbsp;|&nbsp; VMID: <strong>{{ vmid }}</strong></p>

          <div v-if="serialStatus === 'error'" class="error-box">
            <strong>Error:</strong> {{ serialErrorMessage }}
          </div>
          <div v-if="serialStatus === 'disconnected'" class="info-box">
            Terminal disconnected.
          </div>

          <div class="info-panel" style="text-align:left;margin-bottom:1.25rem;">
            <div class="info-row">
              <span class="info-key">Endpoint</span>
              <code class="info-val">/api/v1/pve-console/ws/lxc/{{ hostId }}/{{ node }}/{{ vmid }}</code>
            </div>
            <div class="info-row">
              <span class="info-key">Note</span>
              <span class="info-val muted" style="font-size:0.75rem;">Serial terminal uses the Proxmox LXC/QEMU termproxy. VM must be running and have a serial port configured.</span>
            </div>
          </div>

          <div class="overlay-actions">
            <button @click="connectSerial" class="btn-primary-lg" :disabled="serialStatus === 'connecting'">
              {{ serialStatus === 'connecting' ? 'Connecting…' : (serialStatus === 'disconnected' ? 'Reconnect' : 'Connect') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Connecting indicator -->
      <div v-if="serialStatus === 'connecting'" class="serial-connecting-bar">
        <div class="spinner" style="width:1.25rem;height:1.25rem;border-width:2px;"></div>
        <span>Connecting to terminal…</span>
      </div>

      <!-- Terminal output -->
      <div class="terminal-wrap">
        <textarea
          ref="terminalRef"
          class="terminal-output"
          :value="terminalOutput"
          readonly
          spellcheck="false"
          autocomplete="off"
          placeholder="Terminal output will appear here when connected…"
        ></textarea>
        <!-- Input row -->
        <div class="terminal-input-row" v-if="serialStatus === 'connected'">
          <span class="terminal-prompt">$</span>
          <input
            ref="terminalInputRef"
            v-model="terminalInput"
            class="terminal-input"
            placeholder="Type command and press Enter…"
            spellcheck="false"
            autocomplete="off"
            @keydown.enter="sendTerminalInput"
            @keydown.up="navigateHistory(-1)"
            @keydown.down="navigateHistory(1)"
            @keydown.ctrl.c.prevent="sendSerialCtrlC"
          />
          <button @click="sendTerminalInput" class="btn-terminal-send" :disabled="!terminalInput.trim()">Send</button>
          <button @click="sendSerialCtrlC" class="btn-key" title="Send Ctrl+C">Ctrl+C</button>
        </div>
      </div>
    </div>

    <!-- ====================== SPICE TAB ====================== -->
    <div v-show="activeConsoleTab === 'spice'" class="spice-area">
      <div class="overlay-content" style="max-width:560px;margin:auto;padding-top:3rem;text-align:center;">
        <div class="console-icon" style="color:#e3b341;font-size:2.5rem;">&#9670;</div>
        <h3>{{ vmName || `VM ${vmid}` }} — SPICE Connection</h3>
        <p class="subtitle">Node: <strong>{{ node }}</strong> &nbsp;|&nbsp; VMID: <strong>{{ vmid }}</strong></p>

        <div class="info-panel" style="text-align:left;margin-bottom:1.5rem;">
          <div class="info-row">
            <span class="info-key">Protocol</span>
            <span class="info-val">SPICE (Simple Protocol for Independent Computing Environments)</span>
          </div>
          <div class="info-row">
            <span class="info-key">Client required</span>
            <a href="https://www.spice-space.org/download.html" target="_blank" rel="noopener" class="ext-link">
              virt-viewer / remote-viewer
            </a>
          </div>
          <div class="info-row">
            <span class="info-key">File format</span>
            <span class="info-val">.vv (virt-viewer connection file)</span>
          </div>
          <div class="info-row">
            <span class="info-key">Advantages</span>
            <span class="info-val muted" style="font-size:0.75rem;">Audio, USB redirect, clipboard, better performance than VNC on LAN</span>
          </div>
        </div>

        <div v-if="spiceError" class="error-box" style="margin-bottom:1.25rem;">
          <strong>Error:</strong> {{ spiceError }}
        </div>

        <div class="overlay-actions">
          <button @click="downloadSpice" class="btn-primary-lg" :disabled="spiceLoading">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:6px;vertical-align:middle"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            {{ spiceLoading ? 'Generating…' : 'Download .vv File' }}
          </button>
        </div>

        <p class="note" style="margin-top:1rem;">
          Download the .vv connection file and open it with virt-viewer or remote-viewer to start a SPICE session.
          The file contains a one-time password and expires shortly after download.
        </p>

        <div class="spice-install-hint">
          <strong>Install virt-viewer:</strong>
          <code class="spice-code">apt install virt-viewer</code>
          <span class="text-muted">or</span>
          <code class="spice-code">dnf install virt-viewer</code>
          <span class="text-muted">or</span>
          <a href="https://www.spice-space.org/download.html" target="_blank" rel="noopener" class="ext-link">Download for Windows/macOS</a>
        </div>
      </div>
    </div>

    <!-- Clipboard paste modal -->
    <div v-if="showClipboardModal" class="modal-overlay" @click.self="showClipboardModal = false">
      <div class="modal-box">
        <div class="modal-header">
          <h4>Paste Text to VM</h4>
          <button @click="showClipboardModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <p class="modal-hint">Type or paste text below. Click "Send" to type it into the VM via VNC.</p>
          <textarea v-model="clipboardText" class="clipboard-textarea" rows="6" placeholder="Paste or type text here…" autofocus></textarea>
        </div>
        <div class="modal-footer">
          <button @click="showClipboardModal = false" class="btn-secondary-lg">Cancel</button>
          <button @click="sendClipboardText" class="btn-primary-lg" :disabled="!clipboardText">Send to VM</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import toast from '@/plugins/toast.js'

const route = useRoute()
const hostId = computed(() => route.params.hostId || route.query.hostId)
const node = computed(() => route.params.node || route.query.node)
const vmid = computed(() => route.params.vmid || route.query.vmid)

// Standalone mode = opened via "open in new tab" without sidebar
const standaloneMode = computed(() => !!route.query.standalone)

// ── Console tab switcher ────────────────────────────────────────────────────
const consoleTabs = [
  { id: 'vnc', label: 'VNC Console' },
  { id: 'serial', label: 'Serial Terminal' },
  { id: 'spice', label: 'SPICE Download' },
]
const activeConsoleTab = ref('vnc')

function switchConsoleTab(tabId) {
  if (activeConsoleTab.value === tabId) return
  activeConsoleTab.value = tabId
  if (tabId === 'vnc' && connectionStatus.value === 'idle') {
    connect()
  }
}

// ── Shared VM info ──────────────────────────────────────────────────────────
const vmName = ref('')
const vmStatus = ref('')
const hostInfo = ref(null)

async function fetchVmInfo() {
  try {
    const res = await api.pveVm.getStatus(hostId.value, node.value, vmid.value)
    vmName.value = res.data?.name || ''
    vmStatus.value = res.data?.status || ''
  } catch (e) {
    // non-fatal
  }
}

// ── VNC state ───────────────────────────────────────────────────────────────
const connectionStatus = ref('idle')
const errorMessage = ref('')
const disconnectReason = ref('')
const ticketData = ref(null)
const loadingTicket = ref(false)
const canvasRef = ref(null)

// UI state
const compactMode = ref(false)
const showFxMenu = ref(false)
const showSpecialMenu = ref(false)
const showClipboardModal = ref(false)
const clipboardText = ref('')
const qualityLevel = ref('medium')
const scaleMode = ref('remote')

// Session timer
const sessionTimer = ref('')
let sessionStart = null
let sessionTimerInterval = null

// Auto-reconnect
const reconnectAttempt = ref(0)
let reconnectTimeout = null
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]
let userDisconnected = false

let rfb = null

const specialKeys = [
  { label: 'Print Screen', code: 0xFF61 },
  { label: 'Pause', code: 0xFF13 },
  { label: 'Scroll Lock', code: 0xFF14 },
  { label: 'Insert', code: 0xFF63 },
  { label: 'Delete', code: 0xFFFF },
  { label: 'Home', code: 0xFF50 },
  { label: 'End', code: 0xFF57 },
  { label: 'Page Up', code: 0xFF55 },
  { label: 'Page Down', code: 0xFF56 },
]

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
  userDisconnected = false
  connectionStatus.value = 'connecting'
  errorMessage.value = ''
  disconnectReason.value = ''

  const ok = await getTicketAndHost()
  if (!ok) return

  try {
    const { default: RFB } = await import('https://cdn.jsdelivr.net/npm/@novnc/novnc@1.4.0/core/rfb.js')

    if (rfb) {
      try { rfb.disconnect() } catch {}
      rfb = null
    }

    const wsUrl = buildWsUrl()
    rfb = new RFB(canvasRef.value, wsUrl)
    rfb.viewOnly = false
    applyScaleMode()

    rfb.addEventListener('connect', () => {
      connectionStatus.value = 'connected'
      reconnectAttempt.value = 0
      startSessionTimer()
    })

    rfb.addEventListener('disconnect', (e) => {
      stopSessionTimer()
      if (userDisconnected) {
        connectionStatus.value = 'disconnected'
        disconnectReason.value = 'Disconnected by user.'
        return
      }
      if (e.detail?.clean === false) {
        connectionStatus.value = 'error'
        errorMessage.value = 'Connection lost unexpectedly.'
        disconnectReason.value = 'Network error — connection dropped.'
        scheduleReconnect()
      } else {
        connectionStatus.value = 'disconnected'
        disconnectReason.value = 'Server closed the connection.'
        scheduleReconnect()
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

function scheduleReconnect() {
  if (userDisconnected) return
  const delay = RECONNECT_DELAYS[Math.min(reconnectAttempt.value, RECONNECT_DELAYS.length - 1)]
  reconnectAttempt.value++
  reconnectTimeout = setTimeout(() => {
    if (!userDisconnected) connect()
  }, delay)
}

function disconnect() {
  userDisconnected = true
  if (reconnectTimeout) { clearTimeout(reconnectTimeout); reconnectTimeout = null }
  reconnectAttempt.value = 0
  stopSessionTimer()
  if (rfb) {
    try { rfb.disconnect() } catch {}
    rfb = null
  }
  connectionStatus.value = 'disconnected'
  disconnectReason.value = 'Disconnected by user.'
}

function startSessionTimer() {
  sessionStart = Date.now()
  sessionTimerInterval = setInterval(() => {
    const secs = Math.floor((Date.now() - sessionStart) / 1000)
    const h = Math.floor(secs / 3600)
    const m = Math.floor((secs % 3600) / 60)
    const s = secs % 60
    sessionTimer.value = h > 0
      ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
      : `${m}:${String(s).padStart(2, '0')}`
  }, 1000)
}

function stopSessionTimer() {
  if (sessionTimerInterval) { clearInterval(sessionTimerInterval); sessionTimerInterval = null }
  sessionTimer.value = ''
}

// --- Key sending ---

function sendCtrlAltDel() {
  if (rfb && connectionStatus.value === 'connected') rfb.sendCtrlAltDel()
}

function sendCtrlC() {
  if (!rfb || connectionStatus.value !== 'connected') return
  rfb.sendKey(0xffe3, 'ControlLeft', true)
  rfb.sendKey(0x63, 'KeyC', true)
  rfb.sendKey(0x63, 'KeyC', false)
  rfb.sendKey(0xffe3, 'ControlLeft', false)
}

function sendCtrlAltFn(n) {
  if (!rfb || connectionStatus.value !== 'connected') return
  const fKeyCodes = [0xFFBE, 0xFFBF, 0xFFC0, 0xFFC1, 0xFFC2, 0xFFC3, 0xFFC4]
  const fCode = fKeyCodes[n - 1]
  rfb.sendKey(0xffe3, 'ControlLeft', true)
  rfb.sendKey(0xffe9, 'AltLeft', true)
  rfb.sendKey(fCode, `F${n}`, true)
  rfb.sendKey(fCode, `F${n}`, false)
  rfb.sendKey(0xffe9, 'AltLeft', false)
  rfb.sendKey(0xffe3, 'ControlLeft', false)
}

function sendSpecialKey(code) {
  if (!rfb || connectionStatus.value !== 'connected') return
  rfb.sendKey(code, null, true)
  rfb.sendKey(code, null, false)
}

function openClipboardModal() {
  clipboardText.value = ''
  showClipboardModal.value = true
  if (navigator.clipboard?.readText) {
    navigator.clipboard.readText().then(text => {
      clipboardText.value = text
    }).catch(() => {})
  }
}

function sendClipboardText() {
  if (!rfb || connectionStatus.value !== 'connected') return
  rfb.clipboardPasteFrom(clipboardText.value)
  showClipboardModal.value = false
  toast.success('Text sent to VM clipboard')
}

// --- Screenshot ---

function takeScreenshot() {
  const canvas = canvasRef.value?.querySelector('canvas')
  if (!canvas) { toast.error('No canvas found'); return }
  try {
    const url = canvas.toDataURL('image/png')
    const a = document.createElement('a')
    a.href = url
    a.download = `vm-${vmid.value}-${Date.now()}.png`
    a.click()
  } catch (e) {
    toast.error('Screenshot failed: ' + e.message)
  }
}

// --- Quality & Scale ---

function applyQuality() {
  if (!rfb) return
  const map = { low: 3, medium: 6, high: 9 }
  rfb.qualityLevel = map[qualityLevel.value] ?? 6
  rfb.compressionLevel = qualityLevel.value === 'low' ? 9 : qualityLevel.value === 'medium' ? 5 : 2
}

function applyScaleMode() {
  if (!rfb) return
  rfb.scaleViewport = scaleMode.value === 'local'
  rfb.resizeSession = scaleMode.value === 'remote'
}

// --- Fullscreen ---

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(err => {
      toast.error(`Fullscreen failed: ${err.message}`)
    })
  } else {
    document.exitFullscreen()
  }
}

// ── SPICE ──────────────────────────────────────────────────────────────────

const spiceLoading = ref(false)
const spiceError = ref('')

async function downloadSpice() {
  spiceLoading.value = true
  spiceError.value = ''
  try {
    const res = await api.pveConsole.downloadSpice(hostId.value, node.value, vmid.value)
    const blob = new Blob([res.data], { type: 'application/x-virt-viewer' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `vm-${vmid.value}-spice.vv`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('SPICE file downloaded — open with virt-viewer')
  } catch (e) {
    const msg = e?.response?.data?.detail || e.message || 'SPICE download failed'
    spiceError.value = msg
    toast.error('SPICE download failed: ' + msg)
  } finally {
    spiceLoading.value = false
  }
}

// ── Serial Terminal ─────────────────────────────────────────────────────────

const serialStatus = ref('idle')
const serialErrorMessage = ref('')
const terminalOutput = ref('')
const terminalInput = ref('')
const terminalRef = ref(null)
const terminalInputRef = ref(null)
const commandHistory = ref([])
let historyIndex = -1
let serialWs = null

const serialStatusLabel = computed(() => {
  const map = {
    idle: 'Not connected',
    connecting: 'Connecting…',
    connected: 'Connected',
    disconnected: 'Disconnected',
    error: 'Error',
  }
  return map[serialStatus.value] || serialStatus.value
})

function buildSerialWsUrl() {
  const token = localStorage.getItem('access_token') || ''
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  // Use the LXC terminal proxy endpoint — Proxmox uses the same termproxy for QEMU serial terminals
  return `${proto}//${location.host}/api/v1/pve-console/ws/lxc/${hostId.value}/${node.value}/${vmid.value}?token=${encodeURIComponent(token)}`
}

function appendToTerminal(text) {
  terminalOutput.value += text
  // Scroll to bottom
  nextTick(() => {
    if (terminalRef.value) {
      terminalRef.value.scrollTop = terminalRef.value.scrollHeight
    }
  })
}

function connectSerial() {
  if (serialWs) {
    try { serialWs.close() } catch {}
    serialWs = null
  }

  serialStatus.value = 'connecting'
  serialErrorMessage.value = ''

  const wsUrl = buildSerialWsUrl()

  try {
    serialWs = new WebSocket(wsUrl, ['binary'])

    serialWs.onopen = () => {
      serialStatus.value = 'connected'
      appendToTerminal('\r\n--- Terminal connected ---\r\n')
      nextTick(() => {
        if (terminalInputRef.value) terminalInputRef.value.focus()
      })
    }

    serialWs.onmessage = (event) => {
      if (event.data instanceof Blob) {
        const reader = new FileReader()
        reader.onload = () => {
          appendToTerminal(reader.result)
        }
        reader.readAsText(event.data)
      } else if (event.data instanceof ArrayBuffer) {
        const text = new TextDecoder().decode(event.data)
        appendToTerminal(text)
      } else {
        appendToTerminal(String(event.data))
      }
    }

    serialWs.onerror = () => {
      serialStatus.value = 'error'
      serialErrorMessage.value = 'WebSocket connection error. Ensure the VM is running and has serial console configured.'
      appendToTerminal('\r\n--- Connection error ---\r\n')
    }

    serialWs.onclose = (event) => {
      if (serialStatus.value === 'connected') {
        appendToTerminal(`\r\n--- Connection closed (code ${event.code}) ---\r\n`)
      }
      if (serialStatus.value !== 'error') {
        serialStatus.value = 'disconnected'
      }
      serialWs = null
    }
  } catch (e) {
    serialStatus.value = 'error'
    serialErrorMessage.value = e.message || 'Failed to open WebSocket'
  }
}

function disconnectSerial() {
  if (serialWs) {
    try { serialWs.close() } catch {}
    serialWs = null
  }
  serialStatus.value = 'disconnected'
  appendToTerminal('\r\n--- Disconnected by user ---\r\n')
}

function sendTerminalInput() {
  const text = terminalInput.value
  if (!text || serialStatus.value !== 'connected' || !serialWs) return

  commandHistory.value.unshift(text)
  if (commandHistory.value.length > 50) commandHistory.value.pop()
  historyIndex = -1

  // Show echo in terminal
  appendToTerminal(`${text}\r\n`)

  try {
    const encoder = new TextEncoder()
    serialWs.send(encoder.encode(text + '\n'))
  } catch (e) {
    appendToTerminal(`\r\n[Error sending: ${e.message}]\r\n`)
  }

  terminalInput.value = ''
}

function sendSerialCtrlC() {
  if (serialStatus.value !== 'connected' || !serialWs) return
  try {
    serialWs.send(new Uint8Array([0x03]))
    appendToTerminal('^C\r\n')
  } catch (e) {
    // ignore
  }
}

function navigateHistory(direction) {
  if (commandHistory.value.length === 0) return
  historyIndex = Math.max(-1, Math.min(commandHistory.value.length - 1, historyIndex + direction))
  terminalInput.value = historyIndex >= 0 ? commandHistory.value[historyIndex] : ''
}

function clearTerminal() {
  terminalOutput.value = ''
}

// ── Misc ───────────────────────────────────────────────────────────────────

function openNewTab() {
  const url = `/proxmox/${hostId.value}/nodes/${node.value}/console/${vmid.value}?standalone=1`
  window.open(url, '_blank')
}

function copyWsUrl() {
  const url = buildWsUrl()
  navigator.clipboard.writeText(url).then(() => {
    toast.success('WebSocket URL copied to clipboard')
  }).catch(() => {
    toast.error('Failed to copy to clipboard')
  })
}

// Keyboard handler for F11 compact toggle
function handleKeydown(e) {
  if (e.key === 'F11' && activeConsoleTab.value === 'vnc') {
    e.preventDefault()
    compactMode.value = !compactMode.value
  }
}

onMounted(async () => {
  await fetchVmInfo()
  connect()
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  userDisconnected = true
  if (reconnectTimeout) clearTimeout(reconnectTimeout)
  stopSessionTimer()
  document.removeEventListener('keydown', handleKeydown)
  if (rfb) {
    try { rfb.disconnect() } catch {}
    rfb = null
  }
  if (serialWs) {
    try { serialWs.close() } catch {}
    serialWs = null
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
  background: #161b22;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
}

.toolbar-row {
  display: flex;
  align-items: center;
  padding: 0.4rem 1rem;
  gap: 0.75rem;
}

.toolbar-row-top {
  justify-content: space-between;
  min-height: 46px;
  border-bottom: 1px solid #21262d;
}

.toolbar-row-keys {
  gap: 0.4rem;
  padding: 0.35rem 1rem;
  flex-wrap: wrap;
  background: #0d1117;
  border-top: 1px solid #21262d;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 1rem;
  min-width: 0;
  flex-shrink: 0;
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

/* ---- Console tab switcher ---- */
.toolbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}

.console-tabs {
  display: flex;
  gap: 0;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  overflow: hidden;
}

.console-tab-btn {
  padding: 0.3rem 0.9rem;
  background: transparent;
  border: none;
  border-right: 1px solid #30363d;
  color: #8b949e;
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
  white-space: nowrap;
}
.console-tab-btn:last-child { border-right: none; }
.console-tab-btn:hover { background: #21262d; color: #c9d1d9; }
.console-tab-btn--active {
  background: #1f4068;
  color: #58a6ff;
  font-weight: 600;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
  flex-wrap: wrap;
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

.session-timer {
  font-size: 0.75rem;
  font-family: monospace;
  color: #3fb950;
  background: #0d2d1a;
  border: 1px solid #1f6335;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
}

.disconnect-reason {
  font-size: 0.72rem;
  color: #e3b341;
}

.btn-toolbar {
  padding: 0.3rem 0.75rem;
  border-radius: 5px;
  border: 1px solid #30363d;
  background: #21262d;
  color: #c9d1d9;
  cursor: pointer;
  font-size: 0.78rem;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  transition: background 0.15s;
  white-space: nowrap;
}
.btn-toolbar:hover { background: #30363d; }
.btn-connect    { background: #238636; border-color: #2ea043; color: #fff; }
.btn-connect:hover { background: #2ea043; }
.btn-disconnect { background: #da3633; border-color: #f85149; color: #fff; }
.btn-disconnect:hover { background: #f85149; }

.select-toolbar {
  padding: 0.25rem 0.5rem;
  background: #21262d;
  border: 1px solid #30363d;
  color: #c9d1d9;
  border-radius: 5px;
  font-size: 0.78rem;
  cursor: pointer;
}

/* ---- Key shortcut bar ---- */
.btn-key {
  padding: 0.2rem 0.6rem;
  background: #21262d;
  border: 1px solid #30363d;
  color: #8b949e;
  border-radius: 4px;
  font-size: 0.72rem;
  cursor: pointer;
  transition: background 0.1s, color 0.1s;
  white-space: nowrap;
}
.btn-key:hover { background: #30363d; color: #c9d1d9; }

.dropdown-wrap { position: relative; }
.dropdown-trigger { cursor: pointer; }

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 100;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 6px;
  min-width: 140px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  padding: 0.25rem 0;
}

.dropdown-item {
  display: block;
  width: 100%;
  padding: 0.35rem 0.75rem;
  background: none;
  border: none;
  color: #c9d1d9;
  font-size: 0.8rem;
  text-align: left;
  cursor: pointer;
}
.dropdown-item:hover { background: #21262d; }

/* ---- Compact mode ---- */
.compact-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.25rem 1rem;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
}

.compact-info {
  font-size: 0.8rem;
  color: #8b949e;
}

.btn-compact-restore {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem;
  background: #21262d;
  border: 1px solid #30363d;
  color: #c9d1d9;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
}
.btn-compact-restore:hover { background: #30363d; }

.reconnect-note {
  font-size: 0.78rem;
  color: #e3b341;
}

/* ---- VNC Console area ---- */
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

.overlay-dark { background: #0d1117; }

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

/* ---- Spinner ---- */
.spinner {
  width: 2.25rem;
  height: 2.25rem;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #58a6ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ---- Serial Terminal area ---- */
.serial-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  background: #0d1117;
}

.serial-connect-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0d1117;
  z-index: 5;
  overflow-y: auto;
  padding: 1rem;
}

.serial-connecting-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  font-size: 0.82rem;
  color: #e3b341;
  flex-shrink: 0;
}

.terminal-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.terminal-output {
  flex: 1;
  width: 100%;
  box-sizing: border-box;
  background: #0d1117;
  color: #c9d1d9;
  font-family: 'Fira Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.82rem;
  line-height: 1.5;
  padding: 0.75rem 1rem;
  border: none;
  outline: none;
  resize: none;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.terminal-input-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: #161b22;
  border-top: 1px solid #30363d;
  flex-shrink: 0;
}

.terminal-prompt {
  color: #3fb950;
  font-family: monospace;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.terminal-input {
  flex: 1;
  background: transparent;
  border: none;
  border-bottom: 1px solid #30363d;
  color: #f0f6fc;
  font-family: 'Fira Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.82rem;
  outline: none;
  padding: 0.2rem 0;
}
.terminal-input::placeholder { color: #4d5566; }

.btn-terminal-send {
  padding: 0.25rem 0.75rem;
  background: #238636;
  border: none;
  border-radius: 4px;
  color: #fff;
  font-size: 0.78rem;
  cursor: pointer;
  flex-shrink: 0;
}
.btn-terminal-send:hover:not(:disabled) { background: #2ea043; }
.btn-terminal-send:disabled { opacity: 0.4; cursor: not-allowed; }

/* ---- SPICE area ---- */
.spice-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #0d1117;
  overflow-y: auto;
  padding: 2rem 1rem;
}

.spice-install-hint {
  margin-top: 1.5rem;
  padding: 0.75rem 1rem;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 6px;
  font-size: 0.8rem;
  color: #8b949e;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: center;
}

.spice-code {
  font-family: monospace;
  background: #0d1117;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  color: #58a6ff;
  font-size: 0.8rem;
}

/* ---- Clipboard modal ---- */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal-box {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 10px;
  width: 90%;
  max-width: 520px;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem 0.75rem;
  border-bottom: 1px solid #21262d;
}

.modal-header h4 {
  margin: 0;
  font-size: 1rem;
  color: #f0f6fc;
}

.modal-close {
  background: none;
  border: none;
  color: #8b949e;
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
  padding: 0;
}
.modal-close:hover { color: #f0f6fc; }

.modal-body { padding: 1rem 1.25rem; }

.modal-hint {
  font-size: 0.82rem;
  color: #8b949e;
  margin: 0 0 0.75rem;
}

.clipboard-textarea {
  width: 100%;
  box-sizing: border-box;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  color: #c9d1d9;
  font-family: 'Fira Mono', monospace;
  font-size: 0.85rem;
  padding: 0.6rem 0.75rem;
  resize: vertical;
}
.clipboard-textarea:focus { outline: none; border-color: #58a6ff; }

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem 1rem;
  border-top: 1px solid #21262d;
}
</style>
