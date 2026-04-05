<template>
  <div class="console-page">
    <!-- Toolbar -->
    <div class="console-toolbar">
      <div class="toolbar-left">
        <span class="vm-label">{{ vmName || `VM ${vmid}` }}</span>
        <span class="vm-id text-sm text-muted">VMID: {{ vmid }}</span>
      </div>
      <div class="toolbar-center">
        <span :class="['badge', connectionStatus === 'connected' ? 'badge-success' : connectionStatus === 'connecting' ? 'badge-warning' : 'badge-danger']">
          {{ connectionStatus }}
        </span>
      </div>
      <div class="toolbar-right flex gap-1">
        <button @click="sendCtrlAltDel" class="btn btn-outline btn-sm" :disabled="connectionStatus !== 'connected'">
          Ctrl+Alt+Del
        </button>
        <button @click="toggleFullscreen" class="btn btn-outline btn-sm">
          Fullscreen
        </button>
        <button @click="disconnect" class="btn btn-danger btn-sm">
          Disconnect
        </button>
      </div>
    </div>

    <!-- noVNC Canvas Container -->
    <div class="console-container">
      <div id="novnc-canvas" ref="canvasRef" class="novnc-canvas"></div>
      <div v-if="connectionStatus === 'connecting'" class="connecting-overlay">
        <div class="loading-spinner"></div>
        <p>Connecting to console...</p>
      </div>
      <div v-if="connectionStatus === 'disconnected'" class="disconnected-overlay">
        <p>Console disconnected.</p>
        <button @click="connect" class="btn btn-primary">Reconnect</button>
      </div>
      <div v-if="connectionStatus === 'error'" class="disconnected-overlay">
        <p class="text-danger">{{ errorMessage }}</p>
        <button @click="connect" class="btn btn-primary">Retry</button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'

export default {
  name: 'Console',
  setup() {
    const route = useRoute()
    const hostId = ref(route.params.hostId)
    const node = ref(route.params.node)
    const vmid = ref(route.params.vmid)
    const vmName = ref(null)
    const connectionStatus = ref('connecting')
    const errorMessage = ref('')
    const canvasRef = ref(null)
    let rfb = null

    const buildWsUrl = () => {
      const token = localStorage.getItem('access_token')
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      return `${proto}//${location.host}/api/v1/pve-console/ws/vm/${hostId.value}/${node.value}/${vmid.value}?token=${token}`
    }

    const connect = async () => {
      connectionStatus.value = 'connecting'
      errorMessage.value = ''
      try {
        // Dynamic import of noVNC from CDN
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
          connectionStatus.value = 'disconnected'
          if (e.detail?.clean === false) {
            errorMessage.value = 'Connection lost unexpectedly'
            connectionStatus.value = 'error'
          }
        })

        rfb.addEventListener('desktopname', (e) => {
          vmName.value = e.detail.name
        })

      } catch (error) {
        console.error('Failed to load noVNC or connect:', error)
        connectionStatus.value = 'error'
        errorMessage.value = error.message || 'Failed to initialize console'
      }
    }

    const disconnect = () => {
      if (rfb) {
        rfb.disconnect()
        rfb = null
      }
      connectionStatus.value = 'disconnected'
    }

    const sendCtrlAltDel = () => {
      if (rfb && connectionStatus.value === 'connected') {
        rfb.sendCtrlAltDel()
      }
    }

    const toggleFullscreen = () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => {
          console.error('Fullscreen error:', err)
        })
      } else {
        document.exitFullscreen()
      }
    }

    onMounted(() => {
      connect()
    })

    onBeforeUnmount(() => {
      if (rfb) {
        try { rfb.disconnect() } catch {}
        rfb = null
      }
    })

    return {
      hostId,
      node,
      vmid,
      vmName,
      connectionStatus,
      errorMessage,
      canvasRef,
      connect,
      disconnect,
      sendCtrlAltDel,
      toggleFullscreen
    }
  }
}
</script>

<style scoped>
.console-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #1a1a2e;
  color: #e0e0e0;
  overflow: hidden;
}

.console-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: #16213e;
  border-bottom: 1px solid #0f3460;
  flex-shrink: 0;
  gap: 1rem;
  min-height: 50px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.vm-label {
  font-weight: 600;
  font-size: 1rem;
  color: #e2e8f0;
}

.toolbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.console-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #000;
}

.novnc-canvas {
  width: 100%;
  height: 100%;
}

.novnc-canvas :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
  object-fit: contain;
}

.connecting-overlay,
.disconnected-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.75);
  color: #e2e8f0;
  gap: 1rem;
}

.text-muted { color: #94a3b8; }
.text-danger { color: #f87171; }

.btn-sm {
  padding: 0.25rem 0.75rem;
  font-size: 0.875rem;
}
</style>
