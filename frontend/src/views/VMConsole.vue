<template>
  <div class="vm-console-page">
    <div class="console-header">
      <div class="breadcrumb">
        <router-link to="/proxmox" class="breadcrumb-link">Proxmox Hosts</router-link>
        <span class="breadcrumb-sep">›</span>
        <router-link :to="`/proxmox/${hostId}/nodes/${node}`" class="breadcrumb-link">{{ node }}</router-link>
        <span class="breadcrumb-sep">›</span>
        <span>VM {{ vmid }} Console</span>
      </div>
      <h2>VM Console — VMID {{ vmid }}</h2>
    </div>

    <div class="card">
      <div class="card-header">
        <h3>Console Access</h3>
        <button @click="loadTicket" class="btn btn-primary" :disabled="loading">
          {{ loading ? 'Loading…' : 'Get VNC Info' }}
        </button>
      </div>
      <div class="card-body">
        <div v-if="error" class="alert alert-danger">{{ error }}</div>

        <div v-if="!ticketData && !loading" class="console-placeholder">
          <div class="console-icon">🖥️</div>
          <p>Click "Get VNC Info" to retrieve console access details.</p>
          <p class="text-muted text-sm">Console access uses the Proxmox VNC WebSocket proxy.</p>
        </div>

        <div v-if="loading" class="console-loading">
          <div class="spinner"></div>
          <p>Requesting VNC ticket from Proxmox…</p>
        </div>

        <div v-if="ticketData" class="ticket-info">
          <div class="info-grid">
            <div class="info-row">
              <span class="info-label">VNC Port</span>
              <span class="info-val">{{ ticketData.port }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">WebSocket Path</span>
              <span class="info-val ws-path">/api/v1/pve-console/ws/vm/{{ hostId }}/{{ node }}/{{ vmid }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Ticket</span>
              <span class="info-val ticket-val">{{ ticketData.ticket?.slice(0, 32) }}…</span>
            </div>
          </div>

          <div class="console-actions">
            <a
              :href="proxmoxConsoleUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="btn btn-success"
            >
              Open in Proxmox Web UI
            </a>
            <button @click="copyWsUrl" class="btn btn-secondary">Copy WS URL</button>
          </div>

          <div class="info-note">
            <strong>Note:</strong> Full in-browser VNC (noVNC) integration requires the
            <code>@novnc/novnc</code> package. For now, use the Proxmox Web UI link above
            for full console access. The WebSocket endpoint at
            <code>/api/v1/pve-console/ws/vm/…</code> is available for external VNC clients
            with JWT authentication.
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'

const route = useRoute()
const hostId = route.params.hostId
const node = route.params.node
const vmid = route.params.vmid

const loading = ref(false)
const error = ref('')
const ticketData = ref(null)
const hostInfo = ref(null)

const proxmoxConsoleUrl = computed(() => {
  if (!hostInfo.value) return '#'
  const h = hostInfo.value
  const port = h.port || 8006
  return `https://${h.host}:${port}/?console=kvm&novnc=1&vmid=${vmid}&node=${node}&resize=off`
})

async function loadTicket () {
  loading.value = true
  error.value = ''
  try {
    const [ticketRes, hostRes] = await Promise.all([
      api.pveVm.getVncTicket(hostId, node, vmid),
      api.proxmox.getHost(hostId)
    ])
    ticketData.value = ticketRes.data
    hostInfo.value = hostRes.data
  } catch (e) {
    error.value = e?.response?.data?.detail || e.message || 'Failed to get VNC ticket'
  } finally {
    loading.value = false
  }
}

function copyWsUrl () {
  const token = localStorage.getItem('access_token') || ''
  const url = `${location.protocol.replace('http', 'ws')}//${location.host}/api/v1/pve-console/ws/vm/${hostId}/${node}/${vmid}?token=${token}`
  navigator.clipboard.writeText(url).then(() => {
    alert('WebSocket URL copied to clipboard')
  })
}

onMounted(loadTicket)
</script>

<style scoped>
.vm-console-page {
  padding: 1.5rem;
}

.console-header {
  margin-bottom: 1.5rem;
}

.breadcrumb {
  font-size: 0.85rem;
  color: rgba(255,255,255,0.5);
  margin-bottom: 0.5rem;
}

.breadcrumb-link {
  color: #3b82f6;
  text-decoration: none;
}

.breadcrumb-link:hover { text-decoration: underline; }

.breadcrumb-sep {
  margin: 0 0.4rem;
}

.card {
  background: #1e2a3a;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.card-header h3 { margin: 0; font-size: 1rem; }

.card-body {
  padding: 1.5rem;
}

.console-placeholder {
  text-align: center;
  padding: 3rem 1rem;
  color: rgba(255,255,255,0.5);
}

.console-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.console-loading {
  text-align: center;
  padding: 2rem;
  color: rgba(255,255,255,0.7);
}

.spinner {
  width: 2rem;
  height: 2rem;
  border: 3px solid rgba(255,255,255,0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin { to { transform: rotate(360deg); } }

.info-grid {
  background: #0f1419;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.info-row {
  display: flex;
  align-items: baseline;
  padding: 0.4rem 0;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  gap: 1rem;
}

.info-row:last-child { border-bottom: none; }

.info-label {
  font-size: 0.8rem;
  color: rgba(255,255,255,0.5);
  min-width: 140px;
}

.info-val {
  font-family: monospace;
  font-size: 0.85rem;
  color: #e2e8f0;
  word-break: break-all;
}

.ws-path { color: #38bdf8; }

.ticket-val { color: rgba(255,255,255,0.6); }

.console-actions {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.info-note {
  background: rgba(59,130,246,0.1);
  border: 1px solid rgba(59,130,246,0.3);
  border-radius: 6px;
  padding: 1rem;
  font-size: 0.85rem;
  color: rgba(255,255,255,0.7);
  line-height: 1.6;
}

code {
  background: rgba(255,255,255,0.1);
  padding: 0.1em 0.4em;
  border-radius: 3px;
  font-family: monospace;
}

.alert-danger {
  background: rgba(239,68,68,0.15);
  border: 1px solid rgba(239,68,68,0.4);
  border-radius: 6px;
  padding: 0.75rem 1rem;
  color: #fca5a5;
  margin-bottom: 1rem;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  transition: opacity 0.2s;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }

.btn-success { background: #22c55e; color: white; }
.btn-success:hover { background: #16a34a; }

.btn-secondary { background: rgba(255,255,255,0.1); color: white; border: 1px solid rgba(255,255,255,0.2); }
.btn-secondary:hover { background: rgba(255,255,255,0.15); }

.text-muted { color: rgba(255,255,255,0.5); }
.text-sm { font-size: 0.85rem; }
</style>
