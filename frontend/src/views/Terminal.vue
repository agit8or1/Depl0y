<template>
  <div class="terminal-page">
    <!-- Toolbar -->
    <div class="terminal-toolbar">
      <div class="toolbar-left">
        <span class="terminal-title">{{ pageTitle }}</span>
      </div>
      <div class="toolbar-center">
        <span :class="['badge', wsStatus === 'connected' ? 'badge-success' : wsStatus === 'connecting' ? 'badge-warning' : 'badge-danger']">
          {{ wsStatus }}
        </span>
      </div>
      <div class="toolbar-right">
        <button @click="disconnect" class="btn btn-danger btn-sm">Disconnect</button>
      </div>
    </div>

    <!-- Terminal Container -->
    <div class="terminal-container" ref="terminalContainer" id="terminal-container"></div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'

export default {
  name: 'Terminal',
  setup() {
    const route = useRoute()
    const hostId = ref(route.params.hostId)
    const node = ref(route.params.node)
    const vmid = ref(route.params.vmid || null)
    const wsStatus = ref('connecting')
    const terminalContainer = ref(null)
    let term = null
    let fitAddon = null
    let ws = null
    let resizeObserver = null

    const pageTitle = computed(() => {
      if (vmid.value) {
        return `CT ${vmid.value} Terminal — ${node.value}`
      }
      return `Node Shell — ${node.value}`
    })

    const buildWsUrl = () => {
      const token = localStorage.getItem('access_token')
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = location.host
      if (vmid.value) {
        return `${proto}//${host}/api/v1/pve-console/ws/lxc/${hostId.value}/${node.value}/${vmid.value}?token=${token}`
      }
      return `${proto}//${host}/api/v1/pve-console/ws/node/${hostId.value}/${node.value}?token=${token}`
    }

    const loadScript = (src) => new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) { resolve(); return }
      const s = document.createElement('script')
      s.src = src
      s.onload = resolve
      s.onerror = reject
      document.head.appendChild(s)
    })

    const loadLink = (href) => new Promise((resolve) => {
      if (document.querySelector(`link[href="${href}"]`)) { resolve(); return }
      const l = document.createElement('link')
      l.rel = 'stylesheet'
      l.href = href
      l.onload = resolve
      document.head.appendChild(l)
    })

    const initTerminal = async () => {
      // Load xterm.js from CDN
      await Promise.all([
        loadLink('https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css'),
        loadScript('https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js')
      ])
      await loadScript('https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js')

      const Terminal = window.Terminal
      const FitAddon = window.FitAddon?.FitAddon

      term = new Terminal({
        theme: {
          background: '#0f172a',
          foreground: '#e2e8f0',
          cursor: '#38bdf8',
          cursorAccent: '#0f172a',
          selection: 'rgba(56, 189, 248, 0.3)',
          black: '#1e293b',
          red: '#f87171',
          green: '#4ade80',
          yellow: '#fbbf24',
          blue: '#60a5fa',
          magenta: '#c084fc',
          cyan: '#22d3ee',
          white: '#e2e8f0'
        },
        fontFamily: "'Fira Mono', 'Consolas', 'Courier New', monospace",
        fontSize: 14,
        lineHeight: 1.2,
        cursorBlink: true,
        scrollback: 5000
      })

      if (FitAddon) {
        fitAddon = new FitAddon()
        term.loadAddon(fitAddon)
      }

      term.open(terminalContainer.value)

      if (fitAddon) {
        fitAddon.fit()
      }

      // Connect WebSocket
      connectWs()

      // Handle resize
      if (fitAddon) {
        resizeObserver = new ResizeObserver(() => {
          fitAddon.fit()
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
          }
        })
        resizeObserver.observe(terminalContainer.value)
      }
    }

    const connectWs = () => {
      wsStatus.value = 'connecting'
      const url = buildWsUrl()

      ws = new WebSocket(url)

      ws.onopen = () => {
        wsStatus.value = 'connected'
        term.write('\r\n\x1b[32mConnected.\x1b[0m\r\n')
        // Send initial resize
        if (term && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
        }
      }

      ws.onmessage = (event) => {
        if (term) {
          if (typeof event.data === 'string') {
            term.write(event.data)
          } else {
            const reader = new FileReader()
            reader.onload = () => term.write(new Uint8Array(reader.result))
            reader.readAsArrayBuffer(event.data)
          }
        }
      }

      ws.onclose = () => {
        wsStatus.value = 'disconnected'
        if (term) {
          term.write('\r\n\x1b[31mConnection closed.\x1b[0m\r\n')
        }
      }

      ws.onerror = () => {
        wsStatus.value = 'error'
        if (term) {
          term.write('\r\n\x1b[31mConnection error.\x1b[0m\r\n')
        }
      }

      if (term) {
        term.onData((data) => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(data)
          }
        })
      }
    }

    const disconnect = () => {
      if (ws) {
        ws.close()
        ws = null
      }
      wsStatus.value = 'disconnected'
    }

    onMounted(() => {
      initTerminal()
    })

    onBeforeUnmount(() => {
      if (resizeObserver) resizeObserver.disconnect()
      if (ws) { try { ws.close() } catch {} }
      if (term) { try { term.dispose() } catch {} }
    })

    return {
      pageTitle,
      wsStatus,
      terminalContainer,
      disconnect
    }
  }
}
</script>

<style scoped>
.terminal-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0f172a;
  color: #e2e8f0;
  overflow: hidden;
}

.terminal-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
  min-height: 50px;
  gap: 1rem;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.terminal-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: #e2e8f0;
  font-family: 'Fira Mono', monospace;
}

.toolbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.terminal-container {
  flex: 1;
  overflow: hidden;
  padding: 0.5rem;
}

.terminal-container :deep(.xterm) {
  height: 100%;
}

.terminal-container :deep(.xterm-viewport) {
  overflow-y: auto;
}

.btn-sm {
  padding: 0.25rem 0.75rem;
  font-size: 0.875rem;
}
</style>
