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
        <span v-if="sessionTimer" class="session-timer">{{ sessionTimer }}</span>
        <span v-if="bytesReceived > 0" class="bytes-badge">{{ formatBytes(bytesReceived) }} rx</span>
      </div>
      <div class="toolbar-right">
        <!-- Font size -->
        <div class="font-ctrl" v-if="term">
          <button @click="adjustFontSize(-1)" class="btn-icon" title="Decrease font size (Ctrl+-)">A−</button>
          <span class="font-size-label">{{ fontSize }}px</span>
          <button @click="adjustFontSize(1)" class="btn-icon" title="Increase font size (Ctrl+=)">A+</button>
        </div>

        <!-- Theme selector -->
        <select v-if="term" v-model="activeTheme" @change="applyTheme" class="select-toolbar" title="Color theme">
          <option value="dark">Dark</option>
          <option value="light">Light</option>
          <option value="solarized">Solarized</option>
          <option value="monokai">Monokai</option>
        </select>

        <!-- Download session log -->
        <button v-if="sessionLog.length > 0" @click="downloadLog" class="btn-toolbar" title="Download session log (.txt)">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Log
        </button>

        <!-- Copy selection -->
        <button v-if="term" @click="copySelection" class="btn-toolbar" title="Copy selected text">Copy</button>

        <!-- Paste from clipboard -->
        <button v-if="wsStatus === 'connected'" @click="pasteFromClipboard" class="btn-toolbar" title="Paste from clipboard">Paste</button>

        <button v-if="wsStatus !== 'connected' && wsStatus !== 'connecting'" @click="connectTerminal" class="btn-toolbar btn-connect">
          Connect
        </button>
        <button v-if="wsStatus === 'connected'" @click="reconnect" class="btn-toolbar btn-reconnect">
          Reconnect
        </button>
        <button v-if="wsStatus === 'connected' || wsStatus === 'connecting'" @click="disconnect" class="btn-toolbar btn-disconnect">
          Disconnect
        </button>
      </div>
    </div>

    <!-- Terminal area -->
    <div class="terminal-area" ref="terminalAreaRef">
      <div class="xterm-container" ref="xtermContainerRef" id="xterm-container"
        @contextmenu.prevent="showContextMenu($event)"></div>

      <!-- Fallback overlay -->
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

      <!-- Right-click context menu -->
      <div v-if="contextMenu.show" class="context-menu"
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
        @mouseleave="contextMenu.show = false">
        <button class="context-item" @click="copySelection(); contextMenu.show = false">Copy</button>
        <button class="context-item" @click="pasteFromClipboard(); contextMenu.show = false">Paste</button>
        <div class="context-divider"></div>
        <button class="context-item" @click="adjustFontSize(1); contextMenu.show = false">Larger Font</button>
        <button class="context-item" @click="adjustFontSize(-1); contextMenu.show = false">Smaller Font</button>
        <div class="context-divider"></div>
        <button class="context-item" @click="downloadLog(); contextMenu.show = false">Download Log</button>
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

const wsStatus = ref('idle')
const errorMessage = ref('')
const disconnectMsg = ref(false)
const showFallback = ref(true)
const xtermContainerRef = ref(null)
const terminalAreaRef = ref(null)

let term = null
let fitAddon = null
let ws = null
let resizeObserver = null

// Session tracking
const sessionTimer = ref('')
const bytesReceived = ref(0)
let sessionStart = null
let sessionTimerInterval = null

// Session log (plain text, ANSI stripped)
const sessionLog = ref([])

// Font size
const fontSize = ref(14)

// Theme
const activeTheme = ref('dark')

// Context menu
const contextMenu = ref({ show: false, x: 0, y: 0 })

const themes = {
  dark: {
    background: '#0d1117',
    foreground: '#c9d1d9',
    cursor: '#58a6ff',
    cursorAccent: '#0d1117',
    selectionBackground: 'rgba(88,166,255,0.25)',
    black: '#484f58', red: '#ff7b72', green: '#3fb950', yellow: '#d29922',
    blue: '#58a6ff', magenta: '#bc8cff', cyan: '#39c5cf', white: '#b1bac4',
    brightBlack: '#6e7681', brightRed: '#ffa198', brightGreen: '#56d364',
    brightYellow: '#e3b341', brightBlue: '#79c0ff', brightMagenta: '#d2a8ff',
    brightCyan: '#56d4dd', brightWhite: '#f0f6fc',
  },
  light: {
    background: '#f8f8f8',
    foreground: '#24292e',
    cursor: '#0366d6',
    cursorAccent: '#f8f8f8',
    selectionBackground: 'rgba(3,102,214,0.15)',
    black: '#24292e', red: '#d73a49', green: '#22863a', yellow: '#b08800',
    blue: '#0366d6', magenta: '#6f42c1', cyan: '#1b7c83', white: '#6a737d',
    brightBlack: '#586069', brightRed: '#cb2431', brightGreen: '#28a745',
    brightYellow: '#dbab09', brightBlue: '#2188ff', brightMagenta: '#8a63d2',
    brightCyan: '#3192aa', brightWhite: '#e1e4e8',
  },
  solarized: {
    background: '#002b36',
    foreground: '#839496',
    cursor: '#839496',
    cursorAccent: '#002b36',
    selectionBackground: 'rgba(131,148,150,0.3)',
    black: '#073642', red: '#dc322f', green: '#859900', yellow: '#b58900',
    blue: '#268bd2', magenta: '#d33682', cyan: '#2aa198', white: '#eee8d5',
    brightBlack: '#002b36', brightRed: '#cb4b16', brightGreen: '#586e75',
    brightYellow: '#657b83', brightBlue: '#839496', brightMagenta: '#6c71c4',
    brightCyan: '#93a1a1', brightWhite: '#fdf6e3',
  },
  monokai: {
    background: '#272822',
    foreground: '#f8f8f2',
    cursor: '#f8f8f2',
    cursorAccent: '#272822',
    selectionBackground: 'rgba(248,248,242,0.2)',
    black: '#272822', red: '#f92672', green: '#a6e22e', yellow: '#f4bf75',
    blue: '#66d9e8', magenta: '#ae81ff', cyan: '#a1efe4', white: '#f8f8f2',
    brightBlack: '#75715e', brightRed: '#f92672', brightGreen: '#a6e22e',
    brightYellow: '#f4bf75', brightBlue: '#66d9e8', brightMagenta: '#ae81ff',
    brightCyan: '#a1efe4', brightWhite: '#f9f8f5',
  },
}

const pageTitle = computed(() => {
  if (lxcVmid.value) return `CT ${lxcVmid.value} Shell — ${node.value}`
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

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

// ---- Dynamic CDN loaders ----
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
      theme: themes[activeTheme.value],
      fontFamily: "'Fira Mono', 'Cascadia Code', 'Consolas', 'Courier New', monospace",
      fontSize: fontSize.value,
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

// ---- Theme apply ----
function applyTheme() {
  if (!term) return
  term.options.theme = themes[activeTheme.value]
}

// ---- Font size ----
function adjustFontSize(delta) {
  fontSize.value = Math.max(8, Math.min(32, fontSize.value + delta))
  if (term) {
    term.options.fontSize = fontSize.value
    if (fitAddon) fitAddon.fit()
  }
}

// ---- Copy / Paste ----
function copySelection() {
  if (!term) return
  const sel = term.getSelection()
  if (sel) {
    navigator.clipboard.writeText(sel).catch(() => {})
  }
}

function pasteFromClipboard() {
  if (!term || !ws || ws.readyState !== WebSocket.OPEN) return
  navigator.clipboard.readText().then(text => {
    if (text) ws.send(text)
  }).catch(() => {})
}

// ---- Context menu ----
function showContextMenu(e) {
  contextMenu.value = { show: true, x: e.offsetX, y: e.offsetY }
}

// ---- Download session log ----
function downloadLog() {
  const text = sessionLog.value.join('')
  const blob = new Blob([text], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const name = lxcVmid.value ? `ct-${lxcVmid.value}-${node.value}` : `node-${node.value}`
  a.download = `session-${name}-${Date.now()}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

// ---- Session timer ----
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

// ---- WebSocket ----
function connectWs() {
  wsStatus.value = 'connecting'
  disconnectMsg.value = false
  errorMessage.value = ''
  bytesReceived.value = 0
  sessionLog.value = []

  const url = buildWsUrl()
  ws = new WebSocket(url)
  ws.binaryType = 'arraybuffer'

  ws.onopen = () => {
    wsStatus.value = 'connected'
    startSessionTimer()
    if (term) {
      term.write('\r\n\x1b[32mConnected to ' + (lxcVmid.value ? `CT ${lxcVmid.value}` : `node ${node.value}`) + '\x1b[0m\r\n')
      ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
    }
  }

  ws.onmessage = (event) => {
    if (!term) return
    let data
    if (typeof event.data === 'string') {
      data = event.data
      bytesReceived.value += data.length
      term.write(data)
      sessionLog.value.push(data)
    } else if (event.data instanceof ArrayBuffer) {
      const uint8 = new Uint8Array(event.data)
      bytesReceived.value += uint8.length
      term.write(uint8)
      // Store as text for the log
      try { sessionLog.value.push(new TextDecoder().decode(uint8)) } catch {}
    }
  }

  ws.onclose = (e) => {
    stopSessionTimer()
    wsStatus.value = 'disconnected'
    disconnectMsg.value = true
    if (term) {
      const reason = e.reason ? ` (${e.reason})` : ''
      term.write(`\r\n\x1b[31mSession closed${reason}.\x1b[0m\r\n`)
    }
  }

  ws.onerror = () => {
    stopSessionTimer()
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
    showFallback.value = true
    wsStatus.value = 'error'
    errorMessage.value = 'Could not load xterm.js from CDN. Check your network connection.'
    return
  }

  connectWs()
}

function disconnect() {
  stopSessionTimer()
  if (ws) {
    ws.close()
    ws = null
  }
  wsStatus.value = 'disconnected'
  showFallback.value = !term
}

function reconnect() {
  if (ws) {
    try { ws.close() } catch {}
    ws = null
  }
  stopSessionTimer()
  // Reuse existing term if available, just open a new WS
  if (term) {
    term.write('\r\n\x1b[33mReconnecting…\x1b[0m\r\n')
    connectWs()
  } else {
    connectTerminal()
  }
}

// Keyboard shortcuts: Ctrl+= / Ctrl+-
function handleKeydown(e) {
  if (e.ctrlKey && (e.key === '=' || e.key === '+')) {
    e.preventDefault()
    adjustFontSize(1)
  } else if (e.ctrlKey && e.key === '-') {
    e.preventDefault()
    adjustFontSize(-1)
  }
}

onMounted(() => {
  connectTerminal()
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  stopSessionTimer()
  document.removeEventListener('keydown', handleKeydown)
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
  padding: 0.45rem 1rem;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
  min-height: 48px;
  gap: 1rem;
  flex-wrap: wrap;
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
  align-items: center;
  gap: 0.6rem;
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

.session-timer {
  font-size: 0.72rem;
  font-family: monospace;
  color: #3fb950;
  background: #0d2d1a;
  border: 1px solid #1f6335;
  padding: 0.12rem 0.45rem;
  border-radius: 4px;
}

.bytes-badge {
  font-size: 0.7rem;
  font-family: monospace;
  color: #8b949e;
  background: #21262d;
  border: 1px solid #30363d;
  padding: 0.12rem 0.45rem;
  border-radius: 4px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.btn-toolbar {
  padding: 0.28rem 0.7rem;
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
.btn-toolbar:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-connect    { background: #238636; border-color: #2ea043; color: #fff; }
.btn-connect:hover:not(:disabled) { background: #2ea043; }
.btn-disconnect { background: #da3633; border-color: #f85149; color: #fff; }
.btn-disconnect:hover { background: #f85149; }
.btn-reconnect  { background: #9e6a03; border-color: #bb8009; color: #fff; }
.btn-reconnect:hover { background: #bb8009; }

.btn-icon {
  padding: 0.2rem 0.45rem;
  background: #21262d;
  border: 1px solid #30363d;
  color: #8b949e;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
  font-weight: 700;
}
.btn-icon:hover { background: #30363d; color: #f0f6fc; }

.font-ctrl {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.font-size-label {
  font-size: 0.72rem;
  color: #8b949e;
  min-width: 30px;
  text-align: center;
  font-family: monospace;
}

.select-toolbar {
  padding: 0.25rem 0.5rem;
  background: #21262d;
  border: 1px solid #30363d;
  color: #c9d1d9;
  border-radius: 5px;
  font-size: 0.78rem;
  cursor: pointer;
}

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

/* ---- Context menu ---- */
.context-menu {
  position: absolute;
  z-index: 100;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  min-width: 140px;
  padding: 0.25rem 0;
}

.context-item {
  display: block;
  width: 100%;
  padding: 0.35rem 0.85rem;
  background: none;
  border: none;
  color: #c9d1d9;
  font-size: 0.82rem;
  text-align: left;
  cursor: pointer;
}
.context-item:hover { background: #21262d; }

.context-divider {
  height: 1px;
  background: #30363d;
  margin: 0.25rem 0;
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
