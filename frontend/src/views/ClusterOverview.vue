<template>
  <div class="cluster-overview-page">
    <div class="page-header mb-2">
      <h2>Cluster Overview</h2>
      <p class="text-muted">Status and resources for Proxmox host {{ hostId }}</p>
    </div>

    <!-- Cluster status + node list -->
    <div class="summary-grid mb-2">
      <!-- Cluster status card -->
      <div class="card">
        <div class="card-header">
          <h3>Cluster Status</h3>
          <button @click="refresh" class="btn btn-outline btn-sm">Refresh</button>
        </div>
        <div v-if="loadingStatus" class="loading-spinner"></div>
        <div v-else class="card-body">
          <div v-if="clusterNodes.length === 0" class="text-muted text-sm">No cluster data.</div>
          <div v-else class="node-list">
            <div v-for="item in clusterNodes" :key="item.name || item.id" class="node-card">
              <div class="node-card-header">
                <span class="node-name">{{ item.name }}</span>
                <span :class="['badge', item.online ? 'badge-success' : 'badge-danger']">
                  {{ item.online ? 'Online' : 'Offline' }}
                </span>
              </div>
              <div class="node-card-meta text-sm text-muted">
                <span v-if="item.level">Level: {{ item.level }}</span>
                <span v-if="item.quorate !== undefined" class="ml-1">
                  Quorate: <strong>{{ item.quorate ? 'Yes' : 'No' }}</strong>
                </span>
                <span v-if="item.nodeid !== undefined" class="ml-1">
                  Node ID: {{ item.nodeid }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Resource summary card -->
      <div class="card">
        <div class="card-header">
          <h3>Resource Summary</h3>
        </div>
        <div v-if="loadingResources" class="loading-spinner"></div>
        <div v-else class="card-body">
          <div class="summary-stats">
            <div class="stat-item">
              <div class="stat-value">{{ summary.vmsTotal }}</div>
              <div class="stat-label">Total VMs</div>
            </div>
            <div class="stat-item stat-item--green">
              <div class="stat-value">{{ summary.vmsRunning }}</div>
              <div class="stat-label">Running VMs</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ summary.ctsTotal }}</div>
              <div class="stat-label">Total CTs</div>
            </div>
            <div class="stat-item stat-item--green">
              <div class="stat-value">{{ summary.ctsRunning }}</div>
              <div class="stat-label">Running CTs</div>
            </div>
          </div>
          <div class="resource-bars">
            <div class="resource-row">
              <div class="resource-label text-sm">
                CPU: {{ summary.cpuUsed.toFixed(1) }} / {{ summary.cpuTotal }} cores
              </div>
              <div class="mini-bar-wrap">
                <div
                  class="mini-bar-fill"
                  :class="barClass(summary.cpuTotal ? summary.cpuUsed / summary.cpuTotal : 0)"
                  :style="{ width: cpuPct + '%' }"
                ></div>
              </div>
              <div class="text-xs text-muted">{{ cpuPct }}%</div>
            </div>
            <div class="resource-row">
              <div class="resource-label text-sm">
                RAM: {{ formatBytes(summary.memUsed) }} / {{ formatBytes(summary.memTotal) }}
              </div>
              <div class="mini-bar-wrap">
                <div
                  class="mini-bar-fill"
                  :class="barClass(summary.memTotal ? summary.memUsed / summary.memTotal : 0)"
                  :style="{ width: memPct + '%' }"
                ></div>
              </div>
              <div class="text-xs text-muted">{{ memPct }}%</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Resource table -->
    <div class="card mb-2">
      <div class="card-header">
        <h3>All Resources</h3>
        <div class="flex gap-1 align-center">
          <input
            v-model="resourceSearch"
            class="form-control search-input"
            placeholder="Search by name or VMID..."
          />
        </div>
      </div>

      <div v-if="loadingResources" class="loading-spinner"></div>

      <div v-else-if="filteredResources.length === 0" class="text-center text-muted p-3">
        No resources found.
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>VMID</th>
              <th>Name</th>
              <th>Node</th>
              <th>Type</th>
              <th>Status</th>
              <th>CPU %</th>
              <th>RAM</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in filteredResources"
              :key="r.id || r.vmid"
              class="resource-row-link"
              @click="navigateToResource(r)"
            >
              <td><strong>{{ r.vmid || '—' }}</strong></td>
              <td>{{ r.name || '—' }}</td>
              <td>{{ r.node || '—' }}</td>
              <td>
                <span :class="['badge', r.type === 'lxc' ? 'badge-warning' : 'badge-info']">
                  {{ r.type === 'lxc' ? 'CT' : 'VM' }}
                </span>
              </td>
              <td>
                <span :class="['badge', r.status === 'running' ? 'badge-success' : 'badge-danger']">
                  {{ r.status || '—' }}
                </span>
              </td>
              <td>{{ r.cpu != null ? (r.cpu * 100).toFixed(1) + '%' : '—' }}</td>
              <td>{{ r.mem != null ? formatBytes(r.mem) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Cluster Firewall Rules -->
    <div class="card">
      <div class="card-header">
        <h3>Cluster Firewall Rules</h3>
      </div>
      <div v-if="loadingFirewall" class="loading-spinner"></div>
      <div v-else-if="firewallRules.length === 0" class="text-center text-muted p-3">
        No cluster firewall rules configured.
      </div>
      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Pos</th>
              <th>Direction</th>
              <th>Action</th>
              <th>Protocol</th>
              <th>Source</th>
              <th>Destination</th>
              <th>Ports</th>
              <th>Comment</th>
              <th>Enabled</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(rule, idx) in firewallRules" :key="rule.pos ?? idx">
              <td><strong>{{ rule.pos ?? idx }}</strong></td>
              <td>
                <span :class="['badge', rule.type === 'out' ? 'badge-warning' : 'badge-info']">
                  {{ (rule.type || 'in').toUpperCase() }}
                </span>
              </td>
              <td>
                <span :class="['badge', actionBadge(rule.action)]">{{ rule.action || '—' }}</span>
              </td>
              <td>{{ rule.proto || 'any' }}</td>
              <td class="text-sm">{{ rule.source || '—' }}</td>
              <td class="text-sm">{{ rule.dest || '—' }}</td>
              <td class="text-sm">
                <span v-if="rule.dport || rule.sport">
                  <span v-if="rule.dport">dst:{{ rule.dport }}</span>
                  <span v-if="rule.sport"> src:{{ rule.sport }}</span>
                </span>
                <span v-else>—</span>
              </td>
              <td class="text-sm">{{ rule.comment || '—' }}</td>
              <td>
                <span :class="['badge', rule.enable == 1 || rule.enable === true ? 'badge-success' : 'badge-danger']">
                  {{ rule.enable == 1 || rule.enable === true ? 'Yes' : 'No' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import { formatBytes } from '@/utils/proxmox'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const hostId = ref(route.params.hostId)

const clusterNodes = ref([])
const loadingStatus = ref(false)

const allResources = ref([])
const loadingResources = ref(false)
const resourceSearch = ref('')

const firewallRules = ref([])
const loadingFirewall = ref(false)

const summary = ref({
  vmsTotal: 0,
  vmsRunning: 0,
  ctsTotal: 0,
  ctsRunning: 0,
  cpuUsed: 0,
  cpuTotal: 0,
  memUsed: 0,
  memTotal: 0,
})

const cpuPct = computed(() => {
  if (!summary.value.cpuTotal) return 0
  return Math.min(100, Math.round((summary.value.cpuUsed / summary.value.cpuTotal) * 100))
})

const memPct = computed(() => {
  if (!summary.value.memTotal) return 0
  return Math.min(100, Math.round((summary.value.memUsed / summary.value.memTotal) * 100))
})

const filteredResources = computed(() => {
  const q = resourceSearch.value.trim().toLowerCase()
  const vmsCts = allResources.value.filter(r => r.type === 'qemu' || r.type === 'lxc')
  if (!q) return vmsCts
  return vmsCts.filter(r =>
    (r.name || '').toLowerCase().includes(q) ||
    String(r.vmid || '').includes(q) ||
    (r.node || '').toLowerCase().includes(q)
  )
})

function barClass(ratio) {
  if (ratio >= 0.9) return 'fill--danger'
  if (ratio >= 0.75) return 'fill--warning'
  return 'fill--ok'
}

function actionBadge(action) {
  const map = { ACCEPT: 'badge-success', DROP: 'badge-danger', REJECT: 'badge-warning' }
  return map[action] || 'badge-info'
}

function navigateToResource(r) {
  if (!r.vmid || !r.node) return
  if (r.type === 'lxc') {
    router.push(`/proxmox/${hostId.value}/nodes/${r.node}/containers/${r.vmid}`)
  } else {
    router.push(`/proxmox/${hostId.value}/nodes/${r.node}/vms/${r.vmid}`)
  }
}

async function fetchClusterStatus() {
  loadingStatus.value = true
  try {
    const res = await api.pveNode.clusterStatus(hostId.value)
    const items = res.data || []
    clusterNodes.value = items.filter(i => i.type === 'node')
  } catch (err) {
    console.error('Failed to load cluster status:', err)
    toast.error('Failed to load cluster status')
  } finally {
    loadingStatus.value = false
  }
}

async function fetchResources() {
  loadingResources.value = true
  try {
    const res = await api.pveNode.clusterResources(hostId.value)
    const resources = res.data || []
    allResources.value = resources

    // Build summary
    let vmsTotal = 0, vmsRunning = 0, ctsTotal = 0, ctsRunning = 0
    let cpuUsed = 0, cpuTotal = 0, memUsed = 0, memTotal = 0

    for (const r of resources) {
      if (r.type === 'qemu') {
        vmsTotal++
        if (r.status === 'running') {
          vmsRunning++
          cpuUsed += (r.cpu || 0) * (r.maxcpu || 1)
        }
        cpuTotal += r.maxcpu || 0
        memUsed += r.mem || 0
        memTotal += r.maxmem || 0
      } else if (r.type === 'lxc') {
        ctsTotal++
        if (r.status === 'running') {
          ctsRunning++
          cpuUsed += (r.cpu || 0) * (r.maxcpu || 1)
        }
        cpuTotal += r.maxcpu || 0
        memUsed += r.mem || 0
        memTotal += r.maxmem || 0
      }
    }

    summary.value = { vmsTotal, vmsRunning, ctsTotal, ctsRunning, cpuUsed, cpuTotal, memUsed, memTotal }
  } catch (err) {
    console.error('Failed to load cluster resources:', err)
    toast.error('Failed to load cluster resources')
  } finally {
    loadingResources.value = false
  }
}

async function fetchFirewallRules() {
  loadingFirewall.value = true
  try {
    const res = await api.pveNode.getClusterFirewallRules(hostId.value)
    firewallRules.value = res.data || []
  } catch (err) {
    console.error('Failed to load firewall rules:', err)
  } finally {
    loadingFirewall.value = false
  }
}

async function refresh() {
  await Promise.all([fetchClusterStatus(), fetchResources(), fetchFirewallRules()])
}

onMounted(refresh)
</script>

<style scoped>
.cluster-overview-page {
  padding: 0;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  align-items: start;
}

.card-body {
  padding: 1.25rem 1.5rem;
}

.node-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.node-card {
  padding: 0.625rem 0.875rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background: var(--bg-secondary);
}

.node-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.25rem;
}

.node-name {
  font-weight: 600;
  color: var(--text-primary);
}

.node-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.stat-item {
  text-align: center;
  padding: 0.75rem;
  background: var(--bg-secondary);
  border-radius: 0.375rem;
  border: 1px solid var(--border-color);
}

.stat-item--green .stat-value {
  color: #10b981;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-muted, #888);
}

.resource-bars {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.resource-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.resource-label {
  min-width: 180px;
  color: var(--text-primary);
}

.mini-bar-wrap {
  flex: 1;
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.mini-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.fill--ok { background: #10b981; }
.fill--warning { background: #f59e0b; }
.fill--danger { background: #ef4444; }

.search-input {
  max-width: 260px;
  padding: 0.3rem 0.6rem;
  font-size: 0.875rem;
}

.resource-row-link {
  cursor: pointer;
  transition: background 0.1s;
}

.resource-row-link:hover {
  background: var(--bg-secondary);
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.mb-2 { margin-bottom: 1rem; }
.ml-1 { margin-left: 0.5rem; }
.mt-1 { margin-top: 0.25rem; }
.p-3 { padding: 1.5rem; }
.text-xs { font-size: 0.75rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-muted, #888); }
.text-center { text-align: center; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.align-center { align-items: center; }

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .summary-stats {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 500px) {
  .summary-stats {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
