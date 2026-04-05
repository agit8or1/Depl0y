<template>
  <div class="node-detail-page">
    <div v-if="loadingInit" class="loading-spinner"></div>
    <div v-else-if="!nodeStatus" class="text-center text-muted mt-4">
      <p>Failed to load node information.</p>
      <button @click="loadAll" class="btn btn-outline mt-2">Retry</button>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="page-header mb-2">
        <div class="header-left">
          <router-link to="/proxmox" class="back-link">← Proxmox Hosts</router-link>
          <h2 class="node-title">
            {{ node }}
            <span :class="nodeStatus.status === 'online' ? 'badge badge-success ml-1' : 'badge badge-danger ml-1'">
              {{ nodeStatus.status || 'unknown' }}
            </span>
          </h2>
          <div class="header-meta flex gap-2 text-sm text-muted">
            <span v-if="nodeStatus.pveversion || nodeStatus['pve-manager-version']">
              PVE {{ nodeStatus.pveversion || nodeStatus['pve-manager-version'] }}
            </span>
            <span v-if="nodeStatus.kversion || nodeStatus.kernel_version">
              Kernel: {{ nodeStatus.kversion || nodeStatus.kernel_version }}
            </span>
            <span>Uptime: {{ formatUptime(nodeStatus.uptime) }}</span>
          </div>
        </div>
        <div class="header-stats flex gap-2">
          <div class="mini-stat">
            <span class="mini-stat__label">CPU</span>
            <span class="mini-stat__value">{{ nodeCpuPct }}%</span>
          </div>
          <div class="mini-stat">
            <span class="mini-stat__label">RAM</span>
            <span class="mini-stat__value">{{ nodeRamPct }}%</span>
          </div>
        </div>
      </div>

      <!-- Stats row -->
      <div class="stats-row mb-2">
        <div class="stat-card-sm">
          <div class="stat-card-sm__label">CPU Cores</div>
          <div class="stat-card-sm__value">{{ nodeStatus.cpuinfo?.cpus || nodeStatus.cpu_count || '—' }}</div>
        </div>
        <div class="stat-card-sm">
          <div class="stat-card-sm__label">RAM Used / Total</div>
          <div class="stat-card-sm__value">
            {{ formatBytes(nodeStatus.memory?.used) }} / {{ formatBytes(nodeStatus.memory?.total) }}
          </div>
        </div>
        <div class="stat-card-sm">
          <div class="stat-card-sm__label">Root Disk</div>
          <div class="stat-card-sm__value">{{ formatBytes(nodeStatus.rootfs?.used) }} / {{ formatBytes(nodeStatus.rootfs?.total) }}</div>
        </div>
        <div class="stat-card-sm">
          <div class="stat-card-sm__label">Load Avg</div>
          <div class="stat-card-sm__value">{{ formatLoadAvg(nodeStatus.loadavg) }}</div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs mb-2">
        <button v-for="tab in tabs" :key="tab.id"
          :class="['tab-btn', activeTab === tab.id ? 'tab-btn--active' : '']"
          @click="switchTab(tab.id)">{{ tab.label }}</button>
      </div>

      <!-- ─── Overview Tab ─── -->
      <div v-if="activeTab === 'overview'">
        <div class="flex gap-1 mb-2 align-center">
          <span class="text-sm text-muted">Timeframe:</span>
          <select v-model="rrdTimeframe" @change="loadRrd" class="form-control form-control-sm" style="width:auto">
            <option value="hour">Last Hour</option>
            <option value="day">Last Day</option>
            <option value="week">Last Week</option>
          </select>
        </div>
        <div class="charts-grid">
          <div class="card chart-card">
            <div class="card-header"><h4>CPU %</h4></div>
            <div class="chart-wrap">
              <Line v-if="cpuChartData" :data="cpuChartData" :options="lineChartOptions" />
              <div v-else class="text-muted text-center text-sm pt-2">Loading chart...</div>
            </div>
          </div>
          <div class="card chart-card">
            <div class="card-header"><h4>Memory %</h4></div>
            <div class="chart-wrap">
              <Line v-if="memChartData" :data="memChartData" :options="lineChartOptions" />
              <div v-else class="text-muted text-center text-sm pt-2">Loading chart...</div>
            </div>
          </div>
          <div class="card chart-card">
            <div class="card-header"><h4>Network I/O (bytes/s)</h4></div>
            <div class="chart-wrap">
              <Line v-if="netChartData" :data="netChartData" :options="bytesChartOptions" />
              <div v-else class="text-muted text-center text-sm pt-2">Loading chart...</div>
            </div>
          </div>
          <div class="card chart-card">
            <div class="card-header"><h4>Disk I/O (bytes/s)</h4></div>
            <div class="chart-wrap">
              <Line v-if="diskChartData" :data="diskChartData" :options="bytesChartOptions" />
              <div v-else class="text-muted text-center text-sm pt-2">Loading chart...</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── VMs & Containers Tab ─── -->
      <div v-if="activeTab === 'guests'">
        <div class="card">
          <div class="card-header">
            <h3>VMs &amp; Containers on {{ node }}</h3>
            <button @click="loadGuests" class="btn btn-outline btn-sm" :disabled="loadingGuests">
              {{ loadingGuests ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <div v-if="loadingGuests" class="loading-spinner"></div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>VMID</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>CPU</th>
                  <th>RAM</th>
                  <th>Disk Used</th>
                  <th>Uptime</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="guests.length === 0">
                  <td colspan="9" class="text-muted text-center">No guests found</td>
                </tr>
                <tr v-for="g in guests" :key="`${g.type}-${g.vmid}`"
                  class="clickable-row"
                  @click.stop="navigateToGuest(g)">
                  <td><strong>{{ g.vmid }}</strong></td>
                  <td>{{ g.name || '—' }}</td>
                  <td>
                    <span v-if="g.type === 'qemu'" class="badge badge-info">VM</span>
                    <span v-else class="badge badge-warning">CT</span>
                  </td>
                  <td>
                    <span :class="g.status === 'running' ? 'badge badge-success' : 'badge badge-danger'">
                      {{ g.status }}
                    </span>
                  </td>
                  <td>{{ g.cpu != null ? (g.cpu * 100).toFixed(1) + '%' : '—' }}</td>
                  <td class="text-sm">
                    {{ g.maxmem ? formatBytes(g.mem) + ' / ' + formatBytes(g.maxmem) : '—' }}
                  </td>
                  <td class="text-sm">
                    {{ g.maxdisk ? formatBytes(g.disk) + ' / ' + formatBytes(g.maxdisk) : '—' }}
                  </td>
                  <td class="text-sm">{{ formatUptime(g.uptime) }}</td>
                  <td @click.stop>
                    <div class="flex gap-1">
                      <button
                        v-if="g.status !== 'running'"
                        @click="guestAction(g, 'start')"
                        class="btn btn-success btn-sm"
                        :disabled="guestActioning[`${g.type}-${g.vmid}`]">
                        Start
                      </button>
                      <button
                        v-else
                        @click="guestAction(g, 'shutdown')"
                        class="btn btn-outline btn-sm"
                        :disabled="guestActioning[`${g.type}-${g.vmid}`]">
                        Stop
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Storage Tab ─── -->
      <div v-if="activeTab === 'storage'">
        <div class="card">
          <div class="card-header"><h3>Storage Pools</h3></div>
          <div v-if="loadingStorage" class="loading-spinner"></div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Content</th>
                  <th>Used</th>
                  <th>Available</th>
                  <th>Total</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="storageList.length === 0">
                  <td colspan="8" class="text-muted text-center">No storage found</td>
                </tr>
                <tr v-for="s in storageList" :key="s.storage" class="clickable-row" @click="browseStorage(s.storage)">
                  <td><strong>{{ s.storage }}</strong></td>
                  <td><span class="badge badge-info">{{ s.type }}</span></td>
                  <td class="text-sm">{{ (s.content || '').replace(/,/g, ', ') || '—' }}</td>
                  <td>
                    <div class="usage-bar-wrap">
                      <div class="usage-bar" :style="{ width: usagePct(s) + '%', background: usageColor(s) }"></div>
                    </div>
                    <span class="text-sm">{{ formatBytes(s.used) }}</span>
                  </td>
                  <td class="text-sm">{{ formatBytes(s.avail) }}</td>
                  <td class="text-sm">{{ formatBytes(s.total) }}</td>
                  <td>
                    <span v-if="s.active" class="badge badge-success">Active</span>
                    <span v-else class="badge badge-danger">Inactive</span>
                  </td>
                  <td @click.stop>
                    <button @click="browseStorage(s.storage)" class="btn btn-outline btn-sm">Browse</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Network Tab ─── -->
      <div v-if="activeTab === 'network'">
        <div class="card">
          <div class="card-header">
            <h3>Network Interfaces</h3>
            <button @click="applyNetwork" class="btn btn-outline btn-sm" :disabled="applyingNetwork">
              {{ applyingNetwork ? 'Applying...' : 'Apply Network Changes' }}
            </button>
          </div>
          <div v-if="loadingNetwork" class="loading-spinner"></div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Interface</th>
                  <th>Type</th>
                  <th>State</th>
                  <th>Address / Mask</th>
                  <th>Gateway</th>
                  <th>Bridge Ports</th>
                  <th>Autostart</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="networkIfaces.length === 0">
                  <td colspan="7" class="text-muted text-center">No interfaces found</td>
                </tr>
                <tr v-for="iface in networkIfaces" :key="iface.iface">
                  <td><code>{{ iface.iface }}</code></td>
                  <td>{{ iface.type }}</td>
                  <td>
                    <span :class="iface.active ? 'badge badge-success' : 'badge badge-danger'">
                      {{ iface.active ? 'UP' : 'DOWN' }}
                    </span>
                  </td>
                  <td class="text-sm">
                    <code v-if="iface.address">{{ iface.address }}{{ iface.netmask ? '/' + iface.netmask : '' }}</code>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="text-sm">{{ iface.gateway || '—' }}</td>
                  <td class="text-sm">{{ iface['bridge-ports'] || iface.slaves || '—' }}</td>
                  <td>
                    <span v-if="iface.autostart" class="badge badge-success">Yes</span>
                    <span v-else class="text-muted text-sm">No</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Tasks Tab ─── -->
      <div v-if="activeTab === 'tasks'">
        <div class="card">
          <div class="card-header">
            <h3>Recent Tasks</h3>
            <button @click="loadTasks" class="btn btn-outline btn-sm" :disabled="loadingTasks">
              {{ loadingTasks ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <div v-if="loadingTasks" class="loading-spinner"></div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Start Time</th>
                  <th>Type</th>
                  <th>ID</th>
                  <th>User</th>
                  <th>Status</th>
                  <th>Duration</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="tasks.length === 0">
                  <td colspan="7" class="text-muted text-center">No tasks found</td>
                </tr>
                <template v-for="task in tasks" :key="task.upid">
                  <tr :class="['clickable-row', task._expanded ? 'row-expanded' : '']"
                    @click="toggleTaskLog(task)">
                    <td class="text-sm">
                      {{ task.starttime ? new Date(task.starttime * 1000).toLocaleString() : '—' }}
                    </td>
                    <td class="text-sm">{{ task.type }}</td>
                    <td class="text-sm text-muted">{{ task.id || '—' }}</td>
                    <td class="text-sm">{{ task.user || '—' }}</td>
                    <td>
                      <span :class="taskBadgeClass(task.status)">{{ task.status || 'running' }}</span>
                    </td>
                    <td class="text-sm">{{ taskDuration(task) }}</td>
                    <td @click.stop>
                      <button
                        v-if="!task.endtime"
                        @click="stopTask(task)"
                        class="btn btn-danger btn-sm"
                        :disabled="task._stopping">
                        {{ task._stopping ? '...' : 'Stop' }}
                      </button>
                      <span v-else class="text-muted text-sm">{{ task._expanded ? '▲' : '▼' }}</span>
                    </td>
                  </tr>
                  <tr v-if="task._expanded" :key="task.upid + '-log'">
                    <td colspan="7" class="task-log-cell">
                      <div v-if="task._loadingLog" class="text-muted text-sm" style="padding: 0.75rem 1rem;">
                        Loading log...
                      </div>
                      <pre v-else class="task-log">{{ formatTaskLog(task._log) }}</pre>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Terminal Tab ─── -->
      <div v-if="activeTab === 'terminal'">
        <div class="card">
          <div class="card-header"><h3>Node Shell</h3></div>
          <div class="card-body text-center">
            <p class="text-muted mb-2">
              Open an interactive terminal session on node <strong>{{ node }}</strong>.
            </p>
            <button @click="openTerminal" class="btn btn-primary mb-2">Open Node Shell</button>
            <p class="text-sm text-muted mt-2">
              Terminal URL: <code>/proxmox/{{ hostId }}/nodes/{{ node }}/terminal</code>
            </p>
          </div>
        </div>
      </div>
    </template>

    <!-- Task Log Modal -->
    <div v-if="showTaskModal" class="modal" @click.self="showTaskModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>Task Log: {{ selectedTask?.type }} — {{ selectedTask?.id }}</h3>
          <button @click="showTaskModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="selectedTask?._loadingLog" class="loading-spinner"></div>
          <pre v-else class="task-log task-log-modal">{{ formatTaskLog(selectedTask?._log) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Tooltip, Legend, Title, Filler
} from 'chart.js'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import { formatBytes, formatUptime } from '@/utils/proxmox'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Title, Filler)

const route = useRoute()
const router = useRouter()
const toast = useToast()

const hostId = computed(() => route.params.hostId)
const node = computed(() => route.params.node)

// Core state
const nodeStatus = ref(null)
const loadingInit = ref(true)
const activeTab = ref('overview')

// RRD
const rrdData = ref(null)
const rrdTimeframe = ref('hour')

// Guests
const guests = ref([])
const loadingGuests = ref(false)
const guestActioning = ref({})

// Storage
const storageList = ref([])
const loadingStorage = ref(false)

// Network
const networkIfaces = ref([])
const loadingNetwork = ref(false)
const applyingNetwork = ref(false)

// Tasks
const tasks = ref([])
const loadingTasks = ref(false)
const showTaskModal = ref(false)
const selectedTask = ref(null)

// Polling
let pollInterval = null

const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'guests', label: 'VMs & Containers' },
  { id: 'storage', label: 'Storage' },
  { id: 'network', label: 'Network' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'terminal', label: 'Terminal' },
]

// ── Computed ──────────────────────────────────────────────────────────────────

const nodeCpuPct = computed(() => {
  if (!nodeStatus.value?.cpu) return 0
  const val = nodeStatus.value.cpu
  return val > 1 ? parseFloat(val.toFixed(1)) : parseFloat((val * 100).toFixed(1))
})

const nodeRamPct = computed(() => {
  const mem = nodeStatus.value?.memory
  if (!mem?.total || !mem?.used) return 0
  return parseFloat(((mem.used / mem.total) * 100).toFixed(1))
})

const makeLabels = (data) =>
  (data || []).map(d => d.time ? new Date(d.time * 1000).toLocaleTimeString() : '')

const cpuChartData = computed(() => {
  if (!rrdData.value?.length) return null
  return {
    labels: makeLabels(rrdData.value),
    datasets: [{
      label: 'CPU %',
      data: rrdData.value.map(d => d.cpu != null ? parseFloat((d.cpu * 100).toFixed(1)) : null),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.1)',
      fill: true, tension: 0.3, pointRadius: 0,
    }]
  }
})

const memChartData = computed(() => {
  if (!rrdData.value?.length) return null
  return {
    labels: makeLabels(rrdData.value),
    datasets: [{
      label: 'Memory %',
      data: rrdData.value.map(d => {
        if (d.memtotal && d.memused) return parseFloat(((d.memused / d.memtotal) * 100).toFixed(1))
        return null
      }),
      borderColor: '#10b981',
      backgroundColor: 'rgba(16,185,129,0.1)',
      fill: true, tension: 0.3, pointRadius: 0,
    }]
  }
})

const netChartData = computed(() => {
  if (!rrdData.value?.length) return null
  return {
    labels: makeLabels(rrdData.value),
    datasets: [
      {
        label: 'In (bytes/s)',
        data: rrdData.value.map(d => d.netin ?? null),
        borderColor: '#06b6d4',
        backgroundColor: 'rgba(6,182,212,0.05)',
        fill: false, tension: 0.3, pointRadius: 0,
      },
      {
        label: 'Out (bytes/s)',
        data: rrdData.value.map(d => d.netout ?? null),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.05)',
        fill: false, tension: 0.3, pointRadius: 0,
      },
    ]
  }
})

const diskChartData = computed(() => {
  if (!rrdData.value?.length) return null
  return {
    labels: makeLabels(rrdData.value),
    datasets: [
      {
        label: 'Read (bytes/s)',
        data: rrdData.value.map(d => d.diskread ?? null),
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139,92,246,0.05)',
        fill: false, tension: 0.3, pointRadius: 0,
      },
      {
        label: 'Write (bytes/s)',
        data: rrdData.value.map(d => d.diskwrite ?? null),
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239,68,68,0.05)',
        fill: false, tension: 0.3, pointRadius: 0,
      },
    ]
  }
})

const lineChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { maxTicksLimit: 8, color: '#9ca3af' }, grid: { color: '#374151' } },
    y: { min: 0, max: 100, ticks: { color: '#9ca3af', callback: v => v + '%' }, grid: { color: '#374151' } }
  }
}

const bytesChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: true, labels: { color: '#9ca3af', boxWidth: 12 } } },
  scales: {
    x: { ticks: { maxTicksLimit: 8, color: '#9ca3af' }, grid: { color: '#374151' } },
    y: { min: 0, ticks: { color: '#9ca3af', callback: v => formatBytes(v) + '/s' }, grid: { color: '#374151' } }
  }
}

// ── Data Loading ──────────────────────────────────────────────────────────────

const loadNodeStatus = async () => {
  const res = await api.pveNode.nodeStatus(hostId.value, node.value)
  nodeStatus.value = res.data
}

const loadRrd = async () => {
  try {
    const res = await api.pveNode.nodeRrdData(hostId.value, node.value, { timeframe: rrdTimeframe.value, cf: 'AVERAGE' })
    rrdData.value = res.data
  } catch (e) {
    console.warn('RRD failed', e)
  }
}

const loadGuests = async () => {
  loadingGuests.value = true
  try {
    const [vmRes, ctRes] = await Promise.all([
      api.pveNode.nodeVms(hostId.value, node.value).catch(() => ({ data: [] })),
      api.pveNode.listContainers(hostId.value, node.value).catch(() => ({ data: [] })),
    ])
    guests.value = [
      ...(vmRes.data || []).map(v => ({ ...v, type: 'qemu' })),
      ...(ctRes.data || []).map(c => ({ ...c, type: 'lxc' })),
    ].sort((a, b) => a.vmid - b.vmid)
  } catch (e) {
    console.warn('Guests load failed', e)
  } finally {
    loadingGuests.value = false
  }
}

const loadStorage = async () => {
  loadingStorage.value = true
  try {
    const res = await api.pveNode.listStorage(hostId.value, node.value)
    storageList.value = res.data || []
  } catch (e) {
    console.warn('Storage failed', e)
  } finally {
    loadingStorage.value = false
  }
}

const loadNetwork = async () => {
  loadingNetwork.value = true
  try {
    const res = await api.pveNode.listNetwork(hostId.value, node.value)
    networkIfaces.value = res.data || []
  } catch (e) {
    console.warn('Network failed', e)
  } finally {
    loadingNetwork.value = false
  }
}

const loadTasks = async () => {
  loadingTasks.value = true
  try {
    const res = await api.pveNode.listTasks(hostId.value, node.value, { limit: 50 })
    tasks.value = (res.data || []).map(t => ({
      ...t,
      _expanded: false,
      _log: null,
      _loadingLog: false,
      _stopping: false,
    }))
  } catch (e) {
    console.warn('Tasks failed', e)
  } finally {
    loadingTasks.value = false
  }
}

const loadAll = async () => {
  loadingInit.value = true
  try {
    await loadNodeStatus()
    await loadRrd()
  } catch (e) {
    console.error('Failed to load node detail', e)
  } finally {
    loadingInit.value = false
  }
}

// ── Tab Management ─────────────────────────────────────────────────────────────

const switchTab = (tab) => {
  activeTab.value = tab
  if (tab === 'guests') loadGuests()
  if (tab === 'storage') loadStorage()
  if (tab === 'network') loadNetwork()
  if (tab === 'tasks') loadTasks()
  if (tab === 'overview') { loadNodeStatus(); loadRrd() }
}

// ── Polling ────────────────────────────────────────────────────────────────────

const startPolling = () => {
  pollInterval = setInterval(() => {
    if (activeTab.value === 'overview') {
      loadNodeStatus()
    }
  }, 10000)
}

// ── Guest Actions ──────────────────────────────────────────────────────────────

const navigateToGuest = (guest) => {
  if (guest.type === 'qemu') {
    router.push(`/proxmox/${hostId.value}/nodes/${node.value}/vms/${guest.vmid}`)
  } else {
    router.push(`/proxmox/${hostId.value}/nodes/${node.value}/containers/${guest.vmid}`)
  }
}

const guestAction = async (guest, action) => {
  const key = `${guest.type}-${guest.vmid}`
  guestActioning.value[key] = true
  try {
    if (guest.type === 'qemu') {
      if (action === 'start') await api.pveVm.start(hostId.value, node.value, guest.vmid)
      else await api.pveVm.shutdown(hostId.value, node.value, guest.vmid)
    } else {
      await api.pveNode.containerAction(hostId.value, node.value, guest.vmid, action)
    }
    toast.success(`${guest.name || guest.vmid}: ${action} initiated`)
    setTimeout(loadGuests, 2000)
  } catch (e) {
    console.error(e)
  } finally {
    delete guestActioning.value[key]
  }
}

// ── Storage ────────────────────────────────────────────────────────────────────

const browseStorage = (storageName) => {
  router.push(`/proxmox/${hostId.value}/nodes/${node.value}/storage?storage=${storageName}`)
}

const usagePct = (s) => {
  if (!s.total || !s.used) return 0
  return Math.min(100, Math.round((s.used / s.total) * 100))
}

const usageColor = (s) => {
  const pct = usagePct(s)
  if (pct > 90) return '#dc2626'
  if (pct > 75) return '#f59e0b'
  return '#2563eb'
}

// ── Network ────────────────────────────────────────────────────────────────────

const applyNetwork = async () => {
  if (!confirm('Apply network configuration? This may briefly interrupt connectivity on this node.')) return
  applyingNetwork.value = true
  try {
    await api.pveNode.applyNetwork(hostId.value, node.value)
    toast.success('Network configuration applied')
    await loadNetwork()
  } catch (e) {
    console.error(e)
  } finally {
    applyingNetwork.value = false
  }
}

// ── Tasks ──────────────────────────────────────────────────────────────────────

const toggleTaskLog = async (task) => {
  task._expanded = !task._expanded
  if (task._expanded && !task._log) {
    task._loadingLog = true
    try {
      const res = await api.pveNode.taskLog(hostId.value, node.value, encodeURIComponent(task.upid))
      task._log = res.data || []
    } catch (e) {
      task._log = [{ t: 'Failed to load log: ' + (e.message || 'unknown error') }]
    } finally {
      task._loadingLog = false
    }
  }
}

const stopTask = async (task) => {
  if (!confirm(`Stop task ${task.type}?`)) return
  task._stopping = true
  try {
    await api.pveNode.stopTask(hostId.value, node.value, encodeURIComponent(task.upid))
    toast.success('Task stop requested')
    setTimeout(loadTasks, 1500)
  } catch (e) {
    console.error(e)
  } finally {
    task._stopping = false
  }
}

const formatTaskLog = (log) => {
  if (!log || !Array.isArray(log)) return 'No log data available.'
  return log.map(l => l.t || l.text || JSON.stringify(l)).join('\n')
}

const taskBadgeClass = (status) => {
  if (status === 'OK') return 'badge badge-success'
  if (!status || status === 'running') return 'badge badge-warning'
  return 'badge badge-danger'
}

const taskDuration = (task) => {
  if (!task.starttime) return '—'
  const end = task.endtime || Math.floor(Date.now() / 1000)
  const secs = end - task.starttime
  if (secs < 60) return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
  return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
}

// ── Terminal ───────────────────────────────────────────────────────────────────

const openTerminal = () => {
  router.push(`/proxmox/${hostId.value}/nodes/${node.value}/terminal`)
}

// ── Utilities ──────────────────────────────────────────────────────────────────

const formatLoadAvg = (loadavg) => {
  if (!loadavg) return '—'
  if (Array.isArray(loadavg)) return loadavg.map(v => parseFloat(v).toFixed(2)).join(', ')
  return String(loadavg)
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadAll()
  startPolling()
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<style scoped>
.node-detail-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.back-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
}

.back-link:hover {
  color: var(--text-primary);
}

.node-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-meta {
  flex-wrap: wrap;
}

.header-stats {
  align-items: center;
}

.mini-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.5rem 1rem;
  min-width: 70px;
}

.mini-stat__label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mini-stat__value {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
}

/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1.5rem;
  overflow-x: auto;
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.6rem 1.25rem;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.9rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
}

.tab-btn:hover { color: var(--text-primary); }

.tab-btn--active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

/* Stats row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card-sm {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  box-shadow: var(--shadow);
}

.stat-card-sm__label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.stat-card-sm__value {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Charts */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 900px) {
  .charts-grid { grid-template-columns: 1fr; }
}

.chart-card .card-header h4 {
  margin: 0;
  font-size: 0.9rem;
}

.chart-wrap {
  height: 200px;
  padding: 0.5rem;
}

.form-control-sm {
  padding: 0.2rem 0.5rem;
  font-size: 0.8rem;
}

/* Clickable rows */
.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background: var(--background);
}

.row-expanded {
  background: var(--background);
}

/* Usage bar */
.usage-bar-wrap {
  width: 100%;
  background: var(--border-color);
  border-radius: 4px;
  height: 6px;
  overflow: hidden;
  margin-bottom: 0.25rem;
}

.usage-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

/* Task log */
.task-log-cell {
  padding: 0;
  background: #0f1419;
}

.task-log {
  margin: 0;
  padding: 0.75rem 1rem;
  font-size: 0.8rem;
  color: #9ca3af;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
}

.task-log-modal {
  max-height: 60vh;
  background: #0f1419;
  border-radius: 0.375rem;
}

.table-container {
  overflow-x: auto;
}

.card-body {
  padding: 1.5rem;
}

/* Modal */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  max-width: 580px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.modal-content.modal-large {
  max-width: 800px;
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.modal-body {
  padding: 1.5rem;
}

/* Utilities */
.ml-1 { margin-left: 0.25rem; }
.mb-2 { margin-bottom: 1rem; }
.mt-2 { margin-top: 1rem; }
.mt-4 { margin-top: 2rem; }
.pt-2 { padding-top: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-center { text-align: center; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.gap-2 { gap: 1rem; }
.align-center { align-items: center; }

.btn-success {
  background-color: var(--secondary-color);
  color: white;
}

.btn-success:hover {
  background-color: #059669;
}

.badge-warning {
  background-color: #fef3c7;
  color: #92400e;
}
</style>
