<template>
  <div class="node-terminal-page">
    <!-- Toolbar -->
    <div class="terminal-toolbar">
      <div class="toolbar-left">
        <router-link :to="`/proxmox/${hostId}/nodes/${node}`" class="back-link">← {{ node }}</router-link>
        <span class="terminal-title">{{ pageTitle }}</span>
      </div>
      <div class="toolbar-center">
        <span :class="['status-badge', wsStatus]">{{ wsStatusLabel }}</span>
      </div>
      <div class="toolbar-right">
        <button v-if="wsStatus !== 'connected' && wsStatus !== 'connecting'" @click="connectTerminal" class="btn-toolbar btn-connect">
          Connect
        </button>
        <button v-if="wsStatus === 'connected' || wsStatus === 'connecting'" @click="disconnect" class="btn-toolbar btn-disconnect">
          Disconnect
        </button>
      </div>
    </div>

    <!-- Terminal area -->
    <div class="terminal-area" ref="terminalAreaRef">
      <!-- xterm container — loaded from CDN -->
      <div class="xterm-container" ref="xtermContainerRef" id="xterm-container"></div>

      <!-- Overlay shown when not connected and no xterm loaded yet -->
      <div v-if="showFallback" class="terminal-fallback">
        <div class="fallback-body">
          <div class="fallback-icon">&#9654;</div>
          <h3>{{ pageTitle }}</h3>
          <p class="hint">Press <strong>Connect</strong> to open a terminal session.</p>

          <div v-if="wsStatus === 'error'" class="error-box">
            <strong>Connection error:</strong> {{ errorMessage }}
          </div>

          <div v-if="wsStatus === 'disconnected' && disconnectMsg" class="disconnected-box">
            Session closed.
          </div>

          <div class="connection-info">
            <div class="info-row">
              <span class="info-key">WebSocket endpoint</span>
              <code class="info-val">{{ wsEndpoint }}</code>
            </div>
            <div class="info-row">
              <span class="info-key">Type</span>
              <code class="info-val">{{ lxcVmid ? `LXC container ${lxcVmid}` : `Node shell` }}</code>
            </div>
          </div>

          <div class="fallback-actions">
            <button @click="connectTerminal" class="btn-primary-lg" :disabled="wsStatus === 'connecting'">
              {{ wsStatus === 'connecting' ? 'Connecting…' : 'Connect' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const hostId = computed(() => route.params.hostId)
const node = computed(() => route.params.node)
const lxcVmid = computed(() => route.query.lxc || route.params.vmid || null)

const wsStatus = ref('idle')        // idle | connecting | connected | disconnected | error
const errorMessage = ref('')
const disconnectMsg = ref(false)
const showFallback = ref(true)
const xtermContainerRef = ref(null)
const terminalAreaRef = ref(null)

let term = null
let fitAddon = null
let ws = null
let resizeObserver = null

const pageTitle = computed(() => {
  if (lxcVmid.value) {
    return `CT ${lxcVmid.value} Shell — ${node.value}`
  }
  return `Node Shell — ${node.value}`
})

const wsStatusLabel = computed(() => {
  const map = {
    idle: 'Not connected',
    connecting: 'Connecting…',
    connected: 'Connected',
    disconnected: 'Disconnected',
    error: 'Error',
  }
  return map[wsStatus.value] || wsStatus.value
})

const wsEndpoint = computed(() => {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  if (lxcVmid.value) {
    return `${proto}//${location.host}/api/v1/pve-console/ws/lxc/${hostId.value}/${node.value}/${lxcVmid.value}`
  }
  return `${proto}//${location.host}/api/v1/pve-console/ws/node/${hostId.value}/${node.value}`
})

function buildWsUrl() {
  const token = localStorage.getItem('access_token') || ''
  return `${wsEndpoint.value}?token=${encodeURIComponent(token)}`
}

// ---- Dynamic CDN loader helpers ----
function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) { resolve(); return }
    const s = document.createElement('script')
    s.src = src
    s.onload = resolve
    s.onerror = reject
    document.head.appendChild(s)
  })
}

function loadLink(href) {
  return new Promise(resolve => {
    if (document.querySelector(`link[href="${href}"]`)) { resolve(); return }
    const l = document.createElement('link')
    l.rel = 'stylesheet'
    l.href = href
    l.onload = resolve
    document.head.appendChild(l)
  })
}

// ---- Terminal init ----
async function initXterm() {
  try {
    await Promise.all([
      loadLink('https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css'),
      loadScript('https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js'),
    ])
    await loadScript('https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js')

    const TerminalClass = window.Terminal
    const FitAddonClass = window.FitAddon?.FitAddon

    if (!TerminalClass) return false

    term = new TerminalClass({
      theme: {
        background: '#0d1117',
        foreground: '#c9d1d9',
        cursor: '#58a6ff',
        cursorAccent: '#0d1117',
        selection: 'rgba(88,166,255,0.25)',
        black: '#484f58',
        red: '#ff7b72',
        green: '#3fb950',
        yellow: '#d29922',
        blue: '#58a6ff',
        magenta: '#bc8cff',
        cyan: '#39c5cf',
        white: '#b1bac4',
        brightBlack: '#6e7681',
        brightRed: '#ffa198',
        brightGreen: '#56d364',
        brightYellow: '#e3b341',
        brightBlue: '#79c0ff',
        brightMagenta: '#d2a8ff',
        brightCyan: '#56d4dd',
        brightWhite: '#f0f6fc',
      },
      fontFamily: "'Fira Mono', 'Cascadia Code', 'Consolas', 'Courier New', monospace",
      fontSize: 14,
      lineHeight: 1.25,
      cursorBlink: true,
      scrollback: 5000,
      allowTransparency: false,
    })

    if (FitAddonClass) {
      fitAddon = new FitAddonClass()
      term.loadAddon(fitAddon)
    }

    if (xtermContainerRef.value) {
      term.open(xtermContainerRef.value)
      if (fitAddon) fitAddon.fit()

      resizeObserver = new ResizeObserver(() => {
        if (fitAddon) {
          fitAddon.fit()
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
          }
        }
      })
      resizeObserver.observe(xtermContainerRef.value)
    }

    return true
  } catch (e) {
    console.warn('xterm CDN load failed:', e)
    return false
  }
}

// ---- WebSocket ----
function connectWs() {
  wsStatus.value = 'connecting'
  disconnectMsg.value = false
  errorMessage.value = ''

  const url = buildWsUrl()
  ws = new WebSocket(url)
  ws.binaryType = 'arraybuffer'

  ws.onopen = () => {
    wsStatus.value = 'connected'
    if (term) {
      term.write('\r\n\x1b[32mConnected to ' + (lxcVmid.value ? `CT ${lxcVmid.value}` : `node ${node.value}`) + '\x1b[0m\r\n')
      // Send initial resize
      ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
    }
  }

  ws.onmessage = (event) => {
    if (!term) return
    if (typeof event.data === 'string') {
      term.write(event.data)
    } else if (event.data instanceof ArrayBuffer) {
      term.write(new Uint8Array(event.data))
    }
  }

  ws.onclose = () => {
    wsStatus.value = 'disconnected'
    disconnectMsg.value = true
    if (term) term.write('\r\n\x1b[31mSession closed.\x1b[0m\r\n')
  }

  ws.onerror = () => {
    wsStatus.value = 'error'
    errorMessage.value = 'WebSocket connection failed. Check that the backend is reachable and that you are authenticated.'
    if (term) term.write('\r\n\x1b[31mConnection error.\x1b[0m\r\n')
  }

  if (term) {
    term.onData(data => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(data)
      }
    })
  }
}

async function connectTerminal() {
  showFallback.value = false
  wsStatus.value = 'connecting'

  const xtermLoaded = await initXterm()

  if (!xtermLoaded || !term) {
    // xterm failed — show fallback with textarea approach
    showFallback.value = true
    wsStatus.value = 'error'
    errorMessage.value = 'Could not load xterm.js from CDN. Check your network connection.'
    return
  }

  connectWs()
}

function disconnect() {
  if (ws) {
    ws.close()
    ws = null
  }
  wsStatus.value = 'disconnected'
  showFallback.value = !term
}

onMounted(() => {
  // Auto-connect on mount
  connectTerminal()
})

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect()
  if (ws) { try { ws.close() } catch {} }
  if (term) { try { term.dispose() } catch {} }
})
</script>

<style scoped>
.node-terminal-page {
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
.terminal-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
  min-height: 48px;
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

.terminal-title {
  font-weight: 600;
  font-size: 0.9rem;
  color: #f0f6fc;
  font-family: 'Fira Mono', 'Consolas', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.toolbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.status-badge {
  padding: 0.2rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.status-badge.idle         { background: #21262d; color: #8b949e; border: 1px solid #30363d; }
.status-badge.connecting   { background: #3d2b00; color: #e3b341; border: 1px solid #6e4c00; }
.status-badge.connected    { background: #0d2d1a; color: #3fb950; border: 1px solid #1f6335; }
.status-badge.disconnected { background: #21262d; color: #8b949e; border: 1px solid #30363d; }
.status-badge.error        { background: #2d0d0d; color: #ff7b72; border: 1px solid #6e1212; }

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.btn-toolbar {
  padding: 0.3rem 0.9rem;
  border-radius: 5px;
  border: none;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 600;
  transition: opacity 0.15s;
}

.btn-toolbar:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-connect    { background: #238636; color: #fff; }
.btn-connect:hover:not(:disabled)    { background: #2ea043; }
.btn-disconnect { background: #da3633; color: #fff; }
.btn-disconnect:hover { background: #f85149; }

/* ---- Terminal area ---- */
.terminal-area {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #0d1117;
}

.xterm-container {
  width: 100%;
  height: 100%;
  padding: 4px;
  box-sizing: border-box;
}

.xterm-container :deep(.xterm) {
  height: 100%;
}

.xterm-container :deep(.xterm-viewport) {
  overflow-y: auto;
}

/* ---- Fallback overlay ---- */
.terminal-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0d1117;
  z-index: 10;
}

.fallback-body {
  max-width: 560px;
  width: 90%;
  text-align: center;
  padding: 2rem;
}

.fallback-icon {
  font-size: 3rem;
  color: #3fb950;
  margin-bottom: 1rem;
  line-height: 1;
}

.fallback-body h3 {
  margin: 0 0 0.75rem;
  font-size: 1.2rem;
  color: #f0f6fc;
  font-family: 'Fira Mono', monospace;
}

.hint {
  color: #8b949e;
  margin: 0 0 1.5rem;
  font-size: 0.9rem;
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

.disconnected-box {
  background: rgba(139,148,158,0.1);
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 0.75rem 1rem;
  color: #8b949e;
  font-size: 0.85rem;
  margin-bottom: 1.25rem;
}

.connection-info {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  text-align: left;
}

.info-row {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid #21262d;
}

.info-row:last-child { border-bottom: none; }

.info-key {
  font-size: 0.75rem;
  color: #8b949e;
  white-space: nowrap;
  min-width: 140px;
  flex-shrink: 0;
}

.info-val {
  font-size: 0.78rem;
  color: #58a6ff;
  font-family: 'Fira Mono', monospace;
  word-break: break-all;
}

.fallback-actions {
  display: flex;
  justify-content: center;
}

.btn-primary-lg {
  background: #238636;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 0.6rem 1.75rem;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-primary-lg:hover:not(:disabled) { background: #2ea043; }
.btn-primary-lg:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
