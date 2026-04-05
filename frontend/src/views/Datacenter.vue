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

      <!-- ── Section 4: Network Overview ── -->
      <div class="card mb-2">
        <div
          class="card-header collapsible-header"
          @click="networkExpanded = !networkExpanded"
          style="cursor: pointer;"
        >
          <h3>Network Overview</h3>
          <div class="collapsible-header-right">
            <span v-if="networkLoading" class="text-muted text-sm">Loading…</span>
            <span class="collapse-chevron" :class="{ 'chevron-open': networkExpanded }">&#9660;</span>
          </div>
        </div>

        <template v-if="networkExpanded">
          <div v-if="networkLoading && networkData.length === 0" class="loading-spinner"></div>

          <div v-else-if="networkData.length === 0" class="text-center text-muted p-3">
            No network data available.
          </div>

          <div v-else class="network-overview-body">
            <!-- Per host -->
            <div
              v-for="hostGroup in networkData"
              :key="hostGroup.hostId"
              class="network-host-group"
            >
              <div class="network-host-title">
                {{ hostGroup.hostName }}
              </div>

              <!-- Per node -->
              <div
                v-for="nodeGroup in hostGroup.nodes"
                :key="nodeGroup.node"
                class="network-node-group"
              >
                <div class="network-node-title text-sm">
                  Node: <strong>{{ nodeGroup.node }}</strong>
                </div>

                <div v-if="nodeGroup.ifaces.length === 0" class="text-muted text-sm pl-2">
                  No interfaces found.
                </div>

                <template v-else>
                  <!-- Physical / uplink bridges -->
                  <div
                    v-if="nodeGroup.physicalBridges.length > 0"
                    class="network-iface-group"
                  >
                    <div class="network-iface-group-label text-xs text-muted">Physical Bridges</div>
                    <table class="table network-table">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Type</th>
                          <th>Address / CIDR</th>
                          <th>Ports / Slaves</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="iface in nodeGroup.physicalBridges" :key="iface.iface">
                          <td class="iface-name">{{ iface.iface }}</td>
                          <td class="text-sm text-muted">{{ iface.type || '—' }}</td>
                          <td class="font-mono text-sm">{{ ifaceAddress(iface) }}</td>
                          <td class="text-sm text-muted">{{ ifaceSlaves(iface) }}</td>
                          <td>
                            <span :class="['badge', ifaceUp(iface) ? 'badge-success' : 'badge-danger']">
                              {{ ifaceUp(iface) ? 'UP' : 'DOWN' }}
                            </span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <!-- VLAN bridges -->
                  <div
                    v-if="nodeGroup.vlanBridges.length > 0"
                    class="network-iface-group"
                  >
                    <div class="network-iface-group-label text-xs text-muted">VLAN Bridges</div>
                    <table class="table network-table">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Type</th>
                          <th>Address / CIDR</th>
                          <th>Ports / Slaves</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="iface in nodeGroup.vlanBridges" :key="iface.iface">
                          <td class="iface-name">{{ iface.iface }}</td>
                          <td class="text-sm text-muted">{{ iface.type || '—' }}</td>
                          <td class="font-mono text-sm">{{ ifaceAddress(iface) }}</td>
                          <td class="text-sm text-muted">{{ ifaceSlaves(iface) }}</td>
                          <td>
                            <span :class="['badge', ifaceUp(iface) ? 'badge-success' : 'badge-danger']">
                              {{ ifaceUp(iface) ? 'UP' : 'DOWN' }}
                            </span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- ── Section 5: Storage Overview ── -->
      <div class="card mb-2">
        <div
          class="card-header collapsible-header"
          @click="storageExpanded = !storageExpanded"
          style="cursor: pointer;"
        >
          <h3>Storage Overview</h3>
          <div class="collapsible-header-right">
            <span v-if="storageLoading" class="text-muted text-sm">Loading…</span>
            <span class="collapse-chevron" :class="{ 'chevron-open': storageExpanded }">&#9660;</span>
          </div>
        </div>

        <template v-if="storageExpanded">
          <div v-if="storageLoading && storageData.length === 0" class="loading-spinner"></div>

          <div v-else-if="storageData.length === 0" class="text-center text-muted p-3">
            No storage data available.
          </div>

          <div v-else class="storage-overview-body">
            <div
              v-for="hostGroup in storageData"
              :key="hostGroup.hostId"
              class="storage-host-group"
            >
              <div class="storage-host-title">{{ hostGroup.hostName }}</div>

              <div
                v-for="nodeGroup in hostGroup.nodes"
                :key="nodeGroup.node"
                class="storage-node-group"
              >
                <div class="storage-node-title text-sm">
                  Node: <strong>{{ nodeGroup.node }}</strong>
                </div>

                <div v-if="nodeGroup.pools.length === 0" class="text-muted text-sm pl-2">
                  No storage pools found.
                </div>

                <div v-else class="table-container">
                  <table class="table storage-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Total</th>
                        <th>Used</th>
                        <th>Available</th>
                        <th style="min-width: 140px;">Usage</th>
                        <th>Shared</th>
                        <th>Content</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="pool in nodeGroup.pools" :key="pool.storage">
                        <td class="storage-name">{{ pool.storage }}</td>
                        <td class="text-sm text-muted">{{ pool.type || '—' }}</td>
                        <td class="text-sm font-mono">{{ pool.total ? formatBytes(pool.total) : '—' }}</td>
                        <td class="text-sm font-mono">{{ pool.used != null ? formatBytes(pool.used) : '—' }}</td>
                        <td class="text-sm font-mono">{{ pool.avail != null ? formatBytes(pool.avail) : '—' }}</td>
                        <td>
                          <div class="storage-bar-wrap">
                            <div class="storage-bar">
                              <div
                                class="storage-bar-fill"
                                :class="storageBarClass(pool.used, pool.total)"
                                :style="{ width: storageUsagePct(pool.used, pool.total) + '%' }"
                              ></div>
                            </div>
                            <span class="storage-bar-label">{{ storageUsagePct(pool.used, pool.total) }}%</span>
                          </div>
                        </td>
                        <td>
                          <span v-if="pool.shared" class="badge badge-info">Yes</span>
                          <span v-else class="text-muted text-sm">No</span>
                        </td>
                        <td>
                          <div class="content-pills">
                            <span
                              v-for="ct in (pool.content || '').split(',')"
                              :key="ct"
                              class="content-pill"
                            >{{ ct.trim() }}</span>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- ── Section 6: All Resources table ── -->
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
                <!-- Type with icon -->
                <td>
                  <span class="type-icon">{{ r.type === 'lxc' ? '📦' : '🖥️' }}</span>
                  <span :class="['badge', r.type === 'lxc' ? 'badge-warning' : 'badge-info']">
                    {{ r.type === 'lxc' ? 'LXC' : 'VM' }}
                  </span>
                </td>
                <td>{{ r.name || '—' }}</td>
                <!-- Tags -->
                <td>
                  <div class="tags-cell">
                    <template v-if="r.tags && r.tags.trim()">
                      <span
                        v-for="tag in parseTags(r.tags)"
                        :key="tag"
                        class="tag-pill"
                      >{{ tag }}</span>
                    </template>
                    <span v-else class="text-muted">—</span>
                  </div>
                </td>
                <td><strong>{{ r.vmid || '—' }}</strong></td>
                <td>
                  <span :class="['badge', r.status === 'running' ? 'badge-success' : 'badge-danger']">
                    {{ r.status || '—' }}
                  </span>
                </td>
                <td>{{ r.cpu != null ? (r.cpu * 100).toFixed(1) + '%' : '—' }}</td>
                <td>{{ r.mem != null ? formatBytes(r.mem) : '—' }}</td>
                <td>{{ r.uptime != null ? formatUptime(r.uptime) : '—' }}</td>
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

// Network overview state
const networkData = ref([])   // [{ hostId, hostName, nodes: [{ node, ifaces, physicalBridges, vlanBridges }] }]
const networkLoading = ref(false)
const networkExpanded = ref(false)

// Storage overview state
const storageData = ref([])   // [{ hostId, hostName, nodes: [{ node, pools }] }]
const storageLoading = ref(false)
const storageExpanded = ref(false)

// Filters
const filterHost = ref('')
const filterType = ref('')
const filterStatus = ref('')
const searchQuery = ref('')

// Sort
const sortKey = ref('name')
const sortDesc = ref(false)

const columns = [
  { key: 'type',      label: 'Type' },
  { key: 'name',      label: 'Name' },
  { key: 'tags',      label: 'Tags' },
  { key: 'vmid',      label: 'VMID' },
  { key: 'status',    label: 'Status' },
  { key: 'cpu',       label: 'CPU %' },
  { key: 'mem',       label: 'Memory' },
  { key: 'uptime',    label: 'Uptime' },
  { key: 'node',      label: 'Node' },
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
    router.push(`/proxmox/${r._hostId}/nodes/${r.node}/lxc/${r.vmid}`)
  } else {
    router.push(`/proxmox/${r._hostId}/nodes/${r.node}/vms/${r.vmid}`)
  }
}

function parseTags(tagsStr) {
  if (!tagsStr || !tagsStr.trim()) return []
  // Proxmox tags are semicolon-separated
  return tagsStr.split(/[;,]/).map(t => t.trim()).filter(Boolean)
}

function formatUptime(seconds) {
  if (!seconds || seconds <= 0) return '—'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

// ── Network helpers ────────────────────────────────────────────────────────
function ifaceAddress(iface) {
  if (iface.cidr) return iface.cidr
  if (iface.address && iface.netmask) return `${iface.address}/${iface.netmask}`
  if (iface.address) return iface.address
  return '—'
}

function ifaceSlaves(iface) {
  // bridge_ports for bridges, slaves for bonds
  const s = iface.bridge_ports || iface.slaves || iface.ovs_ports || ''
  return s || '—'
}

function ifaceUp(iface) {
  if (iface.active != null) return iface.active === 1 || iface.active === true
  if (iface.autostart != null) return iface.autostart === 1 || iface.autostart === true
  return false
}

function isVlanBridge(iface) {
  // VLAN-aware bridges or interfaces with a VLAN id or named vlanXXX / vmbrXXX.XXX
  if (iface.bridge_vlan_aware) return true
  if (iface.vlan_id != null) return true
  if (/\.\d+$/.test(iface.iface || '')) return true
  if (/^vlan\d+$/i.test(iface.iface || '')) return true
  return false
}

// ── Storage helpers ────────────────────────────────────────────────────────
function storageUsagePct(used, total) {
  if (!total || total === 0) return 0
  return Math.min(100, Math.round((used / total) * 100))
}

function storageBarClass(used, total) {
  const pct = storageUsagePct(used, total)
  if (pct > 85) return 'fill--danger'
  if (pct >= 70) return 'fill--warning'
  return 'fill--ok'
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
  if (networkExpanded.value) await fetchNetworkData()
  if (storageExpanded.value) await fetchStorageData()
}

// ── Network data loading ───────────────────────────────────────────────────
async function fetchNetworkData() {
  networkLoading.value = true
  try {
    const hostList = hosts.value.length > 0 ? hosts.value : (await api.proxmox.listHosts()).data || []

    const hostResults = await Promise.allSettled(
      hostList.map(async host => {
        // Collect node names from allResources
        const nodeNames = [
          ...new Set(
            allResources.value
              .filter(r => r._hostId === host.id && r.type === 'node')
              .map(r => r.node)
              .filter(Boolean)
          )
        ]

        const nodeGroups = await Promise.allSettled(
          nodeNames.map(async nodeName => {
            try {
              const res = await api.pveNode.listNetwork(host.id, nodeName)
              const ifaces = (res.data || []).filter(
                i => i.type === 'bridge' || i.type === 'OVSBridge' || i.type === 'bond' || i.type === 'eth' || i.type === 'vlan'
              )
              const physicalBridges = ifaces.filter(i => !isVlanBridge(i))
              const vlanBridges = ifaces.filter(i => isVlanBridge(i))
              return { node: nodeName, ifaces, physicalBridges, vlanBridges }
            } catch {
              return { node: nodeName, ifaces: [], physicalBridges: [], vlanBridges: [] }
            }
          })
        )

        return {
          hostId: host.id,
          hostName: host.name || host.hostname || `Host ${host.id}`,
          nodes: nodeGroups
            .filter(r => r.status === 'fulfilled')
            .map(r => r.value),
        }
      })
    )

    networkData.value = hostResults
      .filter(r => r.status === 'fulfilled')
      .map(r => r.value)
      .filter(h => h.nodes.length > 0)
  } catch (err) {
    console.error('Failed to load network data:', err)
  } finally {
    networkLoading.value = false
  }
}

// ── Storage data loading ───────────────────────────────────────────────────
async function fetchStorageData() {
  storageLoading.value = true
  try {
    const hostList = hosts.value.length > 0 ? hosts.value : (await api.proxmox.listHosts()).data || []

    const hostResults = await Promise.allSettled(
      hostList.map(async host => {
        const nodeNames = [
          ...new Set(
            allResources.value
              .filter(r => r._hostId === host.id && r.type === 'node')
              .map(r => r.node)
              .filter(Boolean)
          )
        ]

        const nodeGroups = await Promise.allSettled(
          nodeNames.map(async nodeName => {
            try {
              const res = await api.pveNode.listStorage(host.id, nodeName)
              const pools = res.data || []
              return { node: nodeName, pools }
            } catch {
              return { node: nodeName, pools: [] }
            }
          })
        )

        return {
          hostId: host.id,
          hostName: host.name || host.hostname || `Host ${host.id}`,
          nodes: nodeGroups
            .filter(r => r.status === 'fulfilled')
            .map(r => r.value),
        }
      })
    )

    storageData.value = hostResults
      .filter(r => r.status === 'fulfilled')
      .map(r => r.value)
      .filter(h => h.nodes.length > 0)
  } catch (err) {
    console.error('Failed to load storage data:', err)
  } finally {
    storageLoading.value = false
  }
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

// ── Watchers for lazy-load of collapsible sections ─────────────────────────
import { watch } from 'vue'

watch(networkExpanded, (val) => {
  if (val && networkData.value.length === 0) fetchNetworkData()
})

watch(storageExpanded, (val) => {
  if (val && storageData.value.length === 0) fetchStorageData()
})

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

/* ── Type icon ───────────────────────────────────────────────────────────── */
.type-icon {
  margin-right: 0.3rem;
  font-size: 0.9rem;
}

/* ── Tag pills ───────────────────────────────────────────────────────────── */
.tags-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem;
}

.tag-pill {
  display: inline-block;
  padding: 0.1rem 0.45rem;
  font-size: 0.68rem;
  font-weight: 500;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent, #6366f1) 18%, transparent);
  color: var(--accent, #6366f1);
  border: 1px solid color-mix(in srgb, var(--accent, #6366f1) 35%, transparent);
  white-space: nowrap;
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

/* ── Collapsible card header ─────────────────────────────────────────────── */
.collapsible-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.collapsible-header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.collapse-chevron {
  font-size: 0.75rem;
  color: var(--text-muted, #888);
  transition: transform 0.2s ease;
  display: inline-block;
  transform: rotate(-90deg);
}

.collapse-chevron.chevron-open {
  transform: rotate(0deg);
}

/* ── Network overview ────────────────────────────────────────────────────── */
.network-overview-body {
  padding: 0.75rem 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.network-host-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.network-host-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-primary);
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--border-color);
}

.network-node-group {
  padding-left: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.network-node-title {
  color: var(--text-muted, #888);
  margin-bottom: 0.25rem;
}

.network-iface-group {
  margin-top: 0.25rem;
}

.network-iface-group-label {
  margin-bottom: 0.3rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.network-table {
  font-size: 0.85rem;
}

.iface-name {
  font-weight: 600;
  font-family: monospace;
  color: var(--text-primary);
}

.font-mono {
  font-family: monospace;
}

/* ── Storage overview ────────────────────────────────────────────────────── */
.storage-overview-body {
  padding: 0.75rem 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.storage-host-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.storage-host-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-primary);
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--border-color);
}

.storage-node-group {
  padding-left: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.storage-node-title {
  color: var(--text-muted, #888);
  margin-bottom: 0.25rem;
}

.storage-table {
  font-size: 0.85rem;
}

.storage-name {
  font-weight: 600;
  font-family: monospace;
  color: var(--text-primary);
}

.storage-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 120px;
}

.storage-bar {
  flex: 1;
  height: 7px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.storage-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.35s ease;
}

.storage-bar-label {
  font-size: 0.72rem;
  font-family: monospace;
  color: var(--text-primary);
  white-space: nowrap;
  min-width: 2.75rem;
  text-align: right;
}

.content-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem;
}

.content-pill {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  font-size: 0.68rem;
  border-radius: 4px;
  background: var(--bg-secondary, #2a2a3e);
  color: var(--text-muted, #888);
  white-space: nowrap;
}

/* ── Utilities ───────────────────────────────────────────────────────────── */
.mb-1  { margin-bottom: 0.5rem; }
.mb-2  { margin-bottom: 1rem; }
.p-3   { padding: 1.5rem; }
.pl-2  { padding-left: 0.5rem; }
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
