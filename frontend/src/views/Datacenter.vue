<template>
  <div class="datacenter-page">
    <div class="page-header mb-2">
      <div class="page-header-left">
        <h2>Datacenter</h2>
        <p class="text-muted">Aggregate view across all Proxmox hosts</p>
      </div>
      <button @click="refresh" class="btn btn-outline btn-sm" :disabled="loading">
        <span v-if="loading">Loading...</span>
        <span v-else>Refresh</span>
      </button>
    </div>

    <!-- Global loading indicator -->
    <div v-if="loading && hosts.length === 0" class="loading-spinner"></div>

    <!-- Error state -->
    <div v-else-if="loadError" class="card mb-2">
      <div class="card-body text-center text-muted p-3">
        Failed to load datacenter data. Check your Proxmox host connections.
      </div>
    </div>

    <template v-else>
      <!-- ── Section 1: Summary stat cards ── -->
      <div class="stat-row mb-2">
        <div class="stat-card">
          <div class="stat-value">{{ summary.totalHosts }}</div>
          <div class="stat-label">Hosts</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary.totalNodes }}</div>
          <div class="stat-label">Nodes</div>
        </div>
        <div class="stat-card stat-card--split">
          <div>
            <div class="stat-value stat-value--green">{{ summary.vmsRunning }}</div>
            <div class="stat-label">VMs Running</div>
          </div>
          <div class="stat-divider">/</div>
          <div>
            <div class="stat-value">{{ summary.vmsTotal }}</div>
            <div class="stat-label">VMs Total</div>
          </div>
        </div>
        <div class="stat-card stat-card--split">
          <div>
            <div class="stat-value stat-value--green">{{ summary.lxcRunning }}</div>
            <div class="stat-label">LXC Running</div>
          </div>
          <div class="stat-divider">/</div>
          <div>
            <div class="stat-value">{{ summary.lxcTotal }}</div>
            <div class="stat-label">LXC Total</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary.totalCpuCores }}</div>
          <div class="stat-label">CPU Cores</div>
        </div>
        <div class="stat-card">
          <div class="stat-value-sm">
            {{ formatBytes(summary.memUsed) }}
            <span class="stat-value-sep">/</span>
            {{ formatBytes(summary.memTotal) }}
          </div>
          <div class="stat-label">RAM Used / Total</div>
        </div>
      </div>

      <!-- ── Section 2: Per-host panels ── -->
      <div class="section-title mb-1">Hosts</div>
      <div v-if="hostPanels.length === 0" class="card mb-2">
        <div class="card-body text-center text-muted p-3">No hosts configured.</div>
      </div>
      <div v-else class="host-grid mb-2">
        <div
          v-for="panel in hostPanels"
          :key="panel.hostId"
          class="card host-card"
        >
          <div class="host-card-header">
            <div class="host-name-row">
              <span class="host-name">{{ panel.name }}</span>
              <span :class="['badge', panel.online ? 'badge-success' : 'badge-danger']">
                {{ panel.online ? 'Online' : 'Offline' }}
              </span>
            </div>
            <div class="host-addr text-sm text-muted">{{ panel.address }}</div>
          </div>

          <div class="host-card-body">
            <!-- CPU bar -->
            <div class="resource-row">
              <div class="resource-label text-sm">
                CPU
                <span class="text-muted text-xs">({{ panel.cpuPct }}%)</span>
              </div>
              <div class="mini-bar-wrap">
                <div
                  class="mini-bar-fill"
                  :class="barClass(panel.cpuRatio)"
                  :style="{ width: panel.cpuPct + '%' }"
                ></div>
              </div>
            </div>

            <!-- RAM bar -->
            <div class="resource-row">
              <div class="resource-label text-sm">
                RAM
                <span class="text-muted text-xs">
                  ({{ formatBytesGb(panel.memUsed) }} / {{ formatBytesGb(panel.memTotal) }} GB)
                </span>
              </div>
              <div class="mini-bar-wrap">
                <div
                  class="mini-bar-fill"
                  :class="barClass(panel.memRatio)"
                  :style="{ width: panel.memPct + '%' }"
                ></div>
              </div>
            </div>

            <!-- Counts row -->
            <div class="host-counts text-sm">
              <div class="host-count-item">
                <span class="count-label text-muted">VMs</span>
                <span class="count-value">
                  <span class="text-green">{{ panel.vmsRunning }}</span>
                  <span class="text-muted"> / {{ panel.vmsTotal }}</span>
                </span>
              </div>
              <div class="host-count-item">
                <span class="count-label text-muted">LXC</span>
                <span class="count-value">
                  <span class="text-green">{{ panel.lxcRunning }}</span>
                  <span class="text-muted"> / {{ panel.lxcTotal }}</span>
                </span>
              </div>
              <div class="host-count-item">
                <span class="count-label text-muted">Nodes</span>
                <span class="count-value">{{ panel.nodeCount }}</span>
              </div>
            </div>
          </div>

          <div class="host-card-footer">
            <router-link :to="`/proxmox/${panel.hostId}/cluster`" class="btn btn-outline btn-sm">
              View Cluster &rarr;
            </router-link>
          </div>
        </div>
      </div>

      <!-- ── Section 3: Top VMs by Resource Usage ── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Top VMs by Resource Usage</h3>
          <span v-if="!topVmsLoading" class="top-vms-refresh-label">
            Auto-refresh in {{ topVmsCountdown }}s
          </span>
          <button @click="fetchTopVms" class="btn btn-outline btn-sm" :disabled="topVmsLoading">
            {{ topVmsLoading ? 'Loading…' : 'Refresh' }}
          </button>
        </div>

        <div v-if="topVmsLoading && topVms.length === 0" class="loading-spinner"></div>

        <div v-else-if="topVms.length === 0" class="text-center text-muted p-3">
          No running VMs found across all hosts.
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>VMID</th>
                <th>Node</th>
                <th>Host</th>
                <th>CPU %</th>
                <th>MEM %</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="vm in topVms"
                :key="`${vm._hostId}-${vm.node}-${vm.vmid}`"
                class="resource-row-link"
                @click="navigateToResource(vm)"
              >
                <td>{{ vm.name || '—' }}</td>
                <td><strong>{{ vm.vmid }}</strong></td>
                <td>{{ vm.node || '—' }}</td>
                <td class="text-sm text-muted">{{ vm._hostName || '—' }}</td>
                <td>
                  <div class="top-vm-bar-wrap">
                    <div class="top-vm-bar">
                      <div
                        class="top-vm-bar-fill"
                        :class="topVmCpuClass(vm.cpu)"
                        :style="{ width: topVmCpuPct(vm.cpu) + '%' }"
                      ></div>
                    </div>
                    <span class="top-vm-bar-label">{{ topVmCpuPct(vm.cpu) }}%</span>
                  </div>
                </td>
                <td>
                  <div class="top-vm-bar-wrap">
                    <div class="top-vm-bar">
                      <div
                        class="top-vm-bar-fill"
                        :class="topVmMemClass(vm.mem, vm.maxmem)"
                        :style="{ width: topVmMemPct(vm.mem, vm.maxmem) + '%' }"
                      ></div>
                    </div>
                    <span class="top-vm-bar-label">{{ topVmMemPct(vm.mem, vm.maxmem) }}%</span>
                  </div>
                </td>
                <td>
                  <span :class="['badge', vm.status === 'running' ? 'badge-success' : 'badge-danger']">
                    {{ vm.status || '—' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── Section 4: Resource distribution table ── -->
      <div class="card">
        <div class="card-header">
          <h3>All Resources</h3>
          <div class="table-filters flex gap-1 align-center flex-wrap">
            <select v-model="filterHost" class="form-control filter-select">
              <option value="">All Hosts</option>
              <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
            </select>
            <select v-model="filterType" class="form-control filter-select">
              <option value="">All Types</option>
              <option value="qemu">VM</option>
              <option value="lxc">LXC</option>
            </select>
            <select v-model="filterStatus" class="form-control filter-select">
              <option value="">All Status</option>
              <option value="running">Running</option>
              <option value="stopped">Stopped</option>
            </select>
            <input
              v-model="searchQuery"
              class="form-control search-input"
              placeholder="Search name or VMID..."
            />
          </div>
        </div>

        <div v-if="loading && allResources.length === 0" class="loading-spinner"></div>

        <div v-else-if="filteredResources.length === 0" class="text-center text-muted p-3">
          No resources match the current filters.
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th
                  v-for="col in columns"
                  :key="col.key"
                  :class="['sortable-th', sortKey === col.key ? 'sort-active' : '']"
                  @click="setSort(col.key)"
                >
                  {{ col.label }}
                  <span class="sort-icon">
                    {{ sortKey === col.key ? (sortDesc ? '▼' : '▲') : '⇅' }}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in filteredResources"
                :key="`${r._hostId}-${r.id}`"
                class="resource-row-link"
                @click="navigateToResource(r)"
              >
                <td>{{ r.name || '—' }}</td>
                <td><strong>{{ r.vmid || '—' }}</strong></td>
                <td>
                  <span :class="['badge', r.type === 'lxc' ? 'badge-warning' : 'badge-info']">
                    {{ r.type === 'lxc' ? 'LXC' : 'VM' }}
                  </span>
                </td>
                <td>
                  <span :class="['badge', r.status === 'running' ? 'badge-success' : 'badge-danger']">
                    {{ r.status || '—' }}
                  </span>
                </td>
                <td>{{ r.cpu != null ? (r.cpu * 100).toFixed(1) + '%' : '—' }}</td>
                <td>{{ r.mem != null ? formatBytes(r.mem) : '—' }}</td>
                <td>{{ r.node || '—' }}</td>
                <td>{{ r._hostName || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import { formatBytes } from '@/utils/proxmox'

const router = useRouter()
const toast = useToast()

// ── State ──────────────────────────────────────────────────────────────────
const hosts = ref([])
const allResources = ref([])  // flat list: each item has _hostId, _hostName injected
const loading = ref(false)
const loadError = ref(false)

// Top VMs state
const topVms = ref([])
const topVmsLoading = ref(false)
const topVmsCountdown = ref(30)
let topVmsInterval = null
let topVmsTickInterval = null

// Filters
const filterHost = ref('')
const filterType = ref('')
const filterStatus = ref('')
const searchQuery = ref('')

// Sort
const sortKey = ref('name')
const sortDesc = ref(false)

const columns = [
  { key: 'name',     label: 'Name' },
  { key: 'vmid',     label: 'VMID' },
  { key: 'type',     label: 'Type' },
  { key: 'status',   label: 'Status' },
  { key: 'cpu',      label: 'CPU %' },
  { key: 'mem',      label: 'Memory' },
  { key: 'node',     label: 'Node' },
  { key: '_hostName', label: 'Host' },
]

// ── Computed summary ───────────────────────────────────────────────────────
const summary = computed(() => {
  const vmTypes = allResources.value.filter(r => r.type === 'qemu' || r.type === 'lxc')

  let vmsTotal = 0, vmsRunning = 0
  let lxcTotal = 0, lxcRunning = 0
  let memUsed = 0, memTotal = 0
  let cpuCores = 0

  for (const r of vmTypes) {
    if (r.type === 'qemu') {
      vmsTotal++
      if (r.status === 'running') vmsRunning++
    } else {
      lxcTotal++
      if (r.status === 'running') lxcRunning++
    }
    memUsed += r.mem || 0
    memTotal += r.maxmem || 0
    cpuCores += r.maxcpu || 0
  }

  const nodeItems = allResources.value.filter(r => r.type === 'node')
  const totalNodes = nodeItems.length

  return {
    totalHosts: hosts.value.length,
    totalNodes,
    vmsTotal,
    vmsRunning,
    lxcTotal,
    lxcRunning,
    memUsed,
    memTotal,
    totalCpuCores: cpuCores,
  }
})

// ── Per-host panels ────────────────────────────────────────────────────────
const hostPanels = computed(() => {
  return hosts.value.map(host => {
    const resources = allResources.value.filter(r => r._hostId === host.id)

    let vmsTotal = 0, vmsRunning = 0
    let lxcTotal = 0, lxcRunning = 0
    let memUsed = 0, memTotal = 0
    let cpuUsed = 0, cpuCores = 0
    let nodeCount = 0

    for (const r of resources) {
      if (r.type === 'qemu') {
        vmsTotal++
        if (r.status === 'running') {
          vmsRunning++
          cpuUsed += (r.cpu || 0) * (r.maxcpu || 1)
        }
        cpuCores += r.maxcpu || 0
        memUsed += r.mem || 0
        memTotal += r.maxmem || 0
      } else if (r.type === 'lxc') {
        lxcTotal++
        if (r.status === 'running') {
          lxcRunning++
          cpuUsed += (r.cpu || 0) * (r.maxcpu || 1)
        }
        cpuCores += r.maxcpu || 0
        memUsed += r.mem || 0
        memTotal += r.maxmem || 0
      } else if (r.type === 'node') {
        nodeCount++
      }
    }

    const cpuRatio = cpuCores > 0 ? Math.min(1, cpuUsed / cpuCores) : 0
    const memRatio = memTotal > 0 ? Math.min(1, memUsed / memTotal) : 0

    return {
      hostId: host.id,
      name: host.name || host.hostname || `Host ${host.id}`,
      address: host.address || host.host || '',
      online: host.status === 'online' || host.connected === true || resources.length > 0,
      vmsTotal,
      vmsRunning,
      lxcTotal,
      lxcRunning,
      nodeCount,
      memUsed,
      memTotal,
      cpuRatio,
      memRatio,
      cpuPct: Math.round(cpuRatio * 100),
      memPct: Math.round(memRatio * 100),
    }
  })
})

// ── Filtered + sorted resource table ──────────────────────────────────────
const filteredResources = computed(() => {
  let list = allResources.value.filter(r => r.type === 'qemu' || r.type === 'lxc')

  if (filterHost.value) {
    list = list.filter(r => String(r._hostId) === String(filterHost.value))
  }
  if (filterType.value) {
    list = list.filter(r => r.type === filterType.value)
  }
  if (filterStatus.value) {
    list = list.filter(r => r.status === filterStatus.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(r =>
      (r.name || '').toLowerCase().includes(q) ||
      String(r.vmid || '').includes(q)
    )
  }

  // Sort
  const key = sortKey.value
  list = [...list].sort((a, b) => {
    let av = a[key] ?? ''
    let bv = b[key] ?? ''
    if (typeof av === 'string') av = av.toLowerCase()
    if (typeof bv === 'string') bv = bv.toLowerCase()
    if (av < bv) return sortDesc.value ? 1 : -1
    if (av > bv) return sortDesc.value ? -1 : 1
    return 0
  })

  return list
})

// ── Helpers ────────────────────────────────────────────────────────────────
function barClass(ratio) {
  if (ratio >= 0.9) return 'fill--danger'
  if (ratio >= 0.75) return 'fill--warning'
  return 'fill--ok'
}

function formatBytesGb(bytes) {
  if (!bytes) return '0'
  return (bytes / 1073741824).toFixed(1)
}

function setSort(key) {
  if (sortKey.value === key) {
    sortDesc.value = !sortDesc.value
  } else {
    sortKey.value = key
    sortDesc.value = false
  }
}

function navigateToResource(r) {
  if (!r.vmid || !r.node || !r._hostId) return
  if (r.type === 'lxc') {
    router.push(`/proxmox/${r._hostId}/nodes/${r.node}/containers/${r.vmid}`)
  } else {
    router.push(`/proxmox/${r._hostId}/nodes/${r.node}/vms/${r.vmid}`)
  }
}

// ── Data loading ───────────────────────────────────────────────────────────
async function fetchAll() {
  loading.value = true
  loadError.value = false

  try {
    // 1. Fetch host list
    const hostsRes = await api.proxmox.listHosts()
    const hostList = hostsRes.data || []
    hosts.value = hostList

    if (hostList.length === 0) {
      allResources.value = []
      return
    }

    // 2. Fetch cluster resources for each host in parallel
    const results = await Promise.allSettled(
      hostList.map(host =>
        api.pveNode.clusterResources(host.id).then(res => ({
          hostId: host.id,
          hostName: host.name || host.hostname || `Host ${host.id}`,
          resources: res.data || [],
        }))
      )
    )

    const flat = []
    for (const result of results) {
      if (result.status === 'fulfilled') {
        const { hostId, hostName, resources } = result.value
        for (const r of resources) {
          flat.push({ ...r, _hostId: hostId, _hostName: hostName })
        }
      }
      // silently skip failed hosts — they show as offline in the panel
    }

    allResources.value = flat
  } catch (err) {
    console.error('Failed to load datacenter data:', err)
    loadError.value = true
    toast.error('Failed to load datacenter data')
  } finally {
    loading.value = false
  }
}

async function refresh() {
  await fetchAll()
}

// ── Top VMs helpers ─────────────────────────────────────────────────────────
function topVmCpuPct(cpu) {
  if (cpu == null) return 0
  return Math.round(cpu * 100)
}
function topVmCpuClass(cpu) {
  const pct = topVmCpuPct(cpu)
  if (pct >= 80) return 'fill--danger'
  if (pct >= 60) return 'fill--warning'
  return 'fill--ok'
}
function topVmMemPct(mem, maxmem) {
  if (!mem || !maxmem) return 0
  return Math.round((mem / maxmem) * 100)
}
function topVmMemClass(mem, maxmem) {
  const pct = topVmMemPct(mem, maxmem)
  if (pct >= 80) return 'fill--danger'
  if (pct >= 60) return 'fill--warning'
  return 'fill--ok'
}

async function fetchTopVms() {
  topVmsLoading.value = true
  topVmsCountdown.value = 30
  try {
    // Use already-loaded hosts if available, otherwise fetch
    const hostList = hosts.value.length > 0 ? hosts.value : (await api.proxmox.listHosts()).data || []

    const results = await Promise.allSettled(
      hostList.map(host =>
        api.pveNode.clusterResources(host.id, 'vm').then(res => ({
          hostId: host.id,
          hostName: host.name || host.hostname || `Host ${host.id}`,
          resources: res.data || [],
        }))
      )
    )

    const vms = []
    for (const result of results) {
      if (result.status === 'fulfilled') {
        const { hostId, hostName, resources } = result.value
        for (const r of resources) {
          if (r.type === 'qemu') {
            vms.push({ ...r, _hostId: hostId, _hostName: hostName })
          }
        }
      }
    }

    // Sort by CPU usage descending, take top 10
    vms.sort((a, b) => (b.cpu || 0) - (a.cpu || 0))
    topVms.value = vms.slice(0, 10)
  } catch (err) {
    console.error('Failed to fetch top VMs:', err)
  } finally {
    topVmsLoading.value = false
  }
}

onMounted(() => {
  fetchAll()
  fetchTopVms()

  // Auto-refresh Top VMs every 30 seconds
  topVmsInterval = setInterval(() => {
    if (document.visibilityState !== 'hidden') fetchTopVms()
    topVmsCountdown.value = 30
  }, 30000)

  topVmsTickInterval = setInterval(() => {
    if (document.visibilityState !== 'hidden' && topVmsCountdown.value > 0) {
      topVmsCountdown.value--
    }
  }, 1000)
})

onUnmounted(() => {
  clearInterval(topVmsInterval)
  clearInterval(topVmsTickInterval)
})
</script>

<style scoped>
.datacenter-page {
  padding: 0;
}

/* ── Page header ─────────────────────────────────────────────────────────── */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.page-header-left h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── Summary stat row ────────────────────────────────────────────────────── */
.stat-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.stat-card {
  flex: 1 1 120px;
  min-width: 100px;
  background: var(--bg-card, #1e1e2e);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  text-align: center;
}

.stat-card--split {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  text-align: center;
}

.stat-divider {
  font-size: 1.5rem;
  color: var(--text-muted, #888);
  line-height: 1;
  align-self: flex-start;
  margin-top: 0.25rem;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
  margin-bottom: 0.25rem;
}

.stat-value--green {
  color: #10b981;
}

.stat-value-sm {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.3;
  margin-bottom: 0.25rem;
}

.stat-value-sep {
  color: var(--text-muted, #888);
  margin: 0 0.15rem;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-muted, #888);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

/* ── Section title ───────────────────────────────────────────────────────── */
.section-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, #888);
  margin-bottom: 0.5rem;
}

/* ── Host grid ───────────────────────────────────────────────────────────── */
.host-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.host-card {
  display: flex;
  flex-direction: column;
}

.host-card-header {
  padding: 1rem 1.25rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.host-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.2rem;
}

.host-name {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.host-addr {
  margin-top: 0.1rem;
}

.host-card-body {
  padding: 0.875rem 1.25rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.host-card-footer {
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
}

/* ── Resource bars (shared with ClusterOverview style) ───────────────────── */
.resource-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.resource-label {
  min-width: 130px;
  color: var(--text-primary);
  white-space: nowrap;
}

.mini-bar-wrap {
  flex: 1;
  height: 7px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.mini-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.35s ease;
}

.fill--ok      { background: #10b981; }
.fill--warning { background: #f59e0b; }
.fill--danger  { background: #ef4444; }

/* ── Host counts row ─────────────────────────────────────────────────────── */
.host-counts {
  display: flex;
  gap: 1rem;
  margin-top: 0.25rem;
}

.host-count-item {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.count-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.count-value {
  font-weight: 600;
  color: var(--text-primary);
}

.text-green { color: #10b981; }

/* ── Resource table ──────────────────────────────────────────────────────── */
.table-filters {
  flex-wrap: wrap;
}

.filter-select {
  padding: 0.3rem 0.5rem;
  font-size: 0.875rem;
  min-width: 110px;
}

.search-input {
  max-width: 200px;
  padding: 0.3rem 0.6rem;
  font-size: 0.875rem;
}

.sortable-th {
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.sortable-th:hover {
  color: var(--text-primary);
}

.sort-active {
  color: var(--accent, #6366f1);
}

.sort-icon {
  margin-left: 0.3rem;
  font-size: 0.7rem;
  opacity: 0.7;
}

.resource-row-link {
  cursor: pointer;
  transition: background 0.1s;
}

.resource-row-link:hover {
  background: var(--bg-secondary);
}

/* ── Top VMs table ───────────────────────────────────────────────────────── */
.top-vms-refresh-label {
  font-size: 0.75rem;
  color: var(--text-muted, #888);
  margin-right: 0.5rem;
}

.top-vm-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 100px;
}

.top-vm-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.top-vm-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.35s ease;
}

.top-vm-bar-label {
  font-size: 0.72rem;
  font-family: monospace;
  color: var(--text-primary);
  white-space: nowrap;
  min-width: 2.5rem;
  text-align: right;
}

/* ── Utilities ───────────────────────────────────────────────────────────── */
.mb-1  { margin-bottom: 0.5rem; }
.mb-2  { margin-bottom: 1rem; }
.p-3   { padding: 1.5rem; }
.text-xs { font-size: 0.75rem; }
.text-sm { font-size: 0.875rem; }
.text-muted  { color: var(--text-muted, #888); }
.text-center { text-align: center; }
.flex        { display: flex; }
.gap-1       { gap: 0.5rem; }
.align-center { align-items: center; }
.flex-wrap   { flex-wrap: wrap; }

/* ── Card sub-elements (mirrors global card styles) ──────────────────────── */
.card-body {
  padding: 1.25rem 1.5rem;
}

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 900px) {
  .stat-row {
    grid-template-columns: repeat(3, 1fr);
  }

  .host-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 600px) {
  .stat-card {
    flex: 1 1 40%;
  }

  .table-filters {
    flex-direction: column;
    align-items: flex-start;
  }

  .filter-select,
  .search-input {
    width: 100%;
    max-width: none;
  }
}
</style>
