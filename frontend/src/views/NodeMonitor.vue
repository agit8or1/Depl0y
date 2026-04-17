<template>
  <div class="node-monitor-page">

    <!-- ── Header ──────────────────────────────────────────────────────────── -->
    <div class="monitor-header">
      <div class="monitor-header__left">
        <router-link
          v-if="resolvedHostId && resolvedNode"
          :to="`/proxmox/${resolvedHostId}/nodes/${resolvedNode}`"
          class="back-link"
        >← {{ resolvedNode || 'Node' }}</router-link>
        <div class="monitor-title-row">
          <h2 class="monitor-title">
            Performance Monitor
            <span v-if="resolvedNode" class="monitor-node-name">— {{ resolvedNode }}</span>
          </h2>
          <span
            v-if="nodeStatus"
            :class="nodeStatus.status === 'online' ? 'badge badge-success' : 'badge badge-danger'"
          >{{ nodeStatus.status }}</span>
        </div>
        <div v-if="nodeStatus" class="monitor-meta text-sm text-muted">
          <span v-if="nodeStatus.uptime">Uptime: {{ formatUptime(nodeStatus.uptime) }}</span>
          <span v-if="nodeStatus.pveversion || nodeStatus['pve-manager-version']">
            PVE {{ nodeStatus.pveversion || nodeStatus['pve-manager-version'] }}
          </span>
          <span v-if="nodeStatus.kversion || nodeStatus.kernel_version">
            Kernel: {{ nodeStatus.kversion || nodeStatus.kernel_version }}
          </span>
        </div>
      </div>

      <div class="monitor-header__right">
        <!-- Node selector -->
        <div class="node-selector-group" v-if="allNodes.length > 1">
          <label class="control-label">Node</label>
          <select v-model="selectedNodeKey" @change="onNodeChange" class="form-control form-control-sm">
            <option v-for="n in allNodes" :key="n.key" :value="n.key">
              {{ n.hostName }} / {{ n.node }}
            </option>
          </select>
        </div>

        <!-- Time range selector -->
        <div class="time-range-row">
          <label class="control-label">Range</label>
          <div class="time-range-selector">
            <button
              v-for="tr in timeRanges"
              :key="tr.label"
              :class="['tr-btn', selectedRange === tr.label ? 'tr-btn--active' : '']"
              @click="setRange(tr.label)"
            >{{ tr.label }}</button>
          </div>
        </div>

        <!-- Auto-refresh toggle + Export -->
        <div class="controls-row">
          <button
            :class="['btn btn-sm', autoRefresh ? 'btn-primary' : 'btn-outline']"
            @click="toggleAutoRefresh"
            :title="autoRefresh ? 'Auto-refresh ON (30s) — click to disable' : 'Enable auto-refresh (30s)'"
          >
            <span :class="['refresh-dot-sm', autoRefresh ? 'refresh-dot-sm--active' : '']"></span>
            {{ autoRefresh ? 'Live' : 'Paused' }}
          </button>
          <button class="btn btn-outline btn-sm" @click="refreshAll" :disabled="loading" title="Refresh now">
            {{ loading ? 'Loading...' : 'Refresh' }}
          </button>
          <button class="btn btn-outline btn-sm" @click="exportCSV" :disabled="!rrdData.length" title="Export all metrics as CSV">
            Export CSV
          </button>
        </div>
      </div>
    </div>

    <!-- ── Error state ─────────────────────────────────────────────────────── -->
    <div v-if="loadError" class="error-banner">
      {{ loadError }}
      <button class="btn btn-outline btn-sm ml-2" @click="refreshAll">Retry</button>
    </div>

    <!-- ── Current Stats Cards ─────────────────────────────────────────────── -->
    <div v-if="nodeStatus" class="current-stats-row">
      <div class="stat-card">
        <div class="stat-card__label">CPU</div>
        <div class="stat-card__value" :style="{ color: cpuColor }">{{ nodeCpuPct }}%</div>
        <div class="stat-card__bar">
          <div class="stat-bar__fill" :style="{ width: Math.min(nodeCpuPct, 100) + '%', background: cpuColor }"></div>
        </div>
        <div class="stat-card__sub text-xs text-muted" v-if="nodeStatus.cpuinfo?.cpus">
          {{ nodeStatus.cpuinfo.cpus }} CPUs
          <span v-if="nodeStatus.cpuinfo?.model"> &middot; {{ nodeStatus.cpuinfo.model }}</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">Memory</div>
        <div class="stat-card__value" :style="{ color: memColor }">{{ nodeMemPct }}%</div>
        <div class="stat-card__bar">
          <div class="stat-bar__fill" :style="{ width: Math.min(nodeMemPct, 100) + '%', background: memColor }"></div>
        </div>
        <div class="stat-card__sub text-xs text-muted">
          {{ formatBytes(nodeStatus.memory?.used) }} / {{ formatBytes(nodeStatus.memory?.total) }}
        </div>
      </div>
      <div class="stat-card" v-if="nodeStatus.swap?.total">
        <div class="stat-card__label">Swap</div>
        <div class="stat-card__value">{{ nodeSwapPct }}%</div>
        <div class="stat-card__bar">
          <div class="stat-bar__fill" :style="{ width: Math.min(nodeSwapPct, 100) + '%', background: '#f59e0b' }"></div>
        </div>
        <div class="stat-card__sub text-xs text-muted">
          {{ formatBytes(nodeStatus.swap?.used) }} / {{ formatBytes(nodeStatus.swap?.total) }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">Root Disk</div>
        <div class="stat-card__value" :style="{ color: diskColor }">{{ nodeRootPct }}%</div>
        <div class="stat-card__bar">
          <div class="stat-bar__fill" :style="{ width: Math.min(nodeRootPct, 100) + '%', background: diskColor }"></div>
        </div>
        <div class="stat-card__sub text-xs text-muted">
          {{ formatBytes(nodeStatus.rootfs?.used) }} / {{ formatBytes(nodeStatus.rootfs?.total) }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">Load Avg</div>
        <div class="stat-card__value text-sm">{{ formatLoadAvg(nodeStatus.loadavg) }}</div>
        <div class="stat-card__sub text-xs text-muted">1m / 5m / 15m</div>
      </div>
      <div class="stat-card" v-if="nodeStatus.cpuinfo?.sockets">
        <div class="stat-card__label">Topology</div>
        <div class="stat-card__value text-sm">{{ nodeStatus.cpuinfo.sockets }}S &times; {{ nodeStatus.cpuinfo.cores }}C</div>
        <div class="stat-card__sub text-xs text-muted">sockets &times; cores</div>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && !rrdData.length" class="loading-state">
      <div class="loading-spinner"></div>
      <div class="text-muted text-sm mt-2">Loading performance data...</div>
    </div>

    <!-- ── Charts Grid ────────────────────────────────────────────────────── -->
    <div v-else-if="rrdData.length" class="charts-grid">

      <!-- CPU Usage -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">CPU Usage</span>
          <span class="chart-card__badge" v-if="cpuData.length">
            {{ latestVal(cpuData).toFixed(1) }}%
          </span>
        </div>
        <div class="chart-body">
          <PerformanceCharts
            v-if="cpuData.length"
            :data="cpuData"
            label="CPU"
            unit="%"
            color="#3b82f6"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="true"
          />
          <div v-else class="chart-empty text-muted text-sm">No data</div>
        </div>
        <div class="chart-stats" v-if="cpuData.length">
          <span>Min <strong>{{ seriesStat(cpuData, 'min').toFixed(1) }}%</strong></span>
          <span>Avg <strong>{{ seriesStat(cpuData, 'avg').toFixed(1) }}%</strong></span>
          <span>Max <strong>{{ seriesStat(cpuData, 'max').toFixed(1) }}%</strong></span>
        </div>
      </div>

      <!-- Memory Usage -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">Memory Usage</span>
          <span class="chart-card__badge" v-if="memData.length">
            {{ latestVal(memData).toFixed(1) }}%
          </span>
        </div>
        <div class="chart-body">
          <PerformanceCharts
            v-if="memData.length"
            :data="memData"
            label="Memory"
            unit="%"
            color="#10b981"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="true"
          />
          <div v-else class="chart-empty text-muted text-sm">No data</div>
        </div>
        <div class="chart-stats" v-if="memData.length">
          <span>Min <strong>{{ seriesStat(memData, 'min').toFixed(1) }}%</strong></span>
          <span>Avg <strong>{{ seriesStat(memData, 'avg').toFixed(1) }}%</strong></span>
          <span>Max <strong>{{ seriesStat(memData, 'max').toFixed(1) }}%</strong></span>
        </div>
      </div>

      <!-- Network I/O — dual line -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">Network I/O</span>
          <span class="chart-card__badge" v-if="netInData.length || netOutData.length">
            <span style="color:#06b6d4">{{ formatMBs(latestVal(netInData)) }}</span>
            /
            <span style="color:#f59e0b">{{ formatMBs(latestVal(netOutData)) }}</span>
          </span>
        </div>
        <div class="chart-body">
          <MultiLineChart
            :series="netSeries"
            unit="MB/s"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="false"
            :formatValue="formatMBsVal"
          />
        </div>
        <div class="chart-stats" v-if="netInData.length || netOutData.length">
          <span style="color:#06b6d4">In avg <strong>{{ formatMBs(seriesStat(netInData, 'avg')) }}</strong></span>
          <span style="color:#f59e0b">Out avg <strong>{{ formatMBs(seriesStat(netOutData, 'avg')) }}</strong></span>
          <span>Peak <strong>{{ formatMBs(Math.max(seriesStat(netInData, 'max'), seriesStat(netOutData, 'max'))) }}</strong></span>
        </div>
      </div>

      <!-- Disk I/O — dual line (sampled from disk-io-rates, builds over time) -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">Disk I/O</span>
          <span class="chart-card__badge" v-if="diskReadData.length || diskWriteData.length">
            <span style="color:#8b5cf6">{{ formatMBs(latestVal(diskReadData)) }}</span>
            /
            <span style="color:#ef4444">{{ formatMBs(latestVal(diskWriteData)) }}</span>
          </span>
        </div>
        <div class="chart-body">
          <div v-if="diskIoHistory.length < 2" class="chart-empty text-muted text-sm">
            Collecting samples… (~10s)
          </div>
          <MultiLineChart
            v-else
            :series="diskSeries"
            unit="MB/s"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="false"
            :formatValue="formatMBsVal"
          />
        </div>
        <div class="chart-stats" v-if="diskReadData.length || diskWriteData.length">
          <span style="color:#8b5cf6">Read avg <strong>{{ formatMBs(seriesStat(diskReadData, 'avg')) }}</strong></span>
          <span style="color:#ef4444">Write avg <strong>{{ formatMBs(seriesStat(diskWriteData, 'avg')) }}</strong></span>
          <span>Peak <strong>{{ formatMBs(Math.max(seriesStat(diskReadData, 'max'), seriesStat(diskWriteData, 'max'))) }}</strong></span>
        </div>
      </div>

      <!-- Load Average — triple line -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">Load Average</span>
          <span class="chart-card__badge" v-if="loadAvgData.length">
            {{ latestVal(loadAvgData).toFixed(2) }}
          </span>
        </div>
        <div class="chart-body">
          <PerformanceCharts
            v-if="loadAvgData.length"
            :data="loadAvgData"
            label="Load Avg"
            unit=""
            color="#f97316"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="true"
          />
          <div v-else class="chart-empty text-muted text-sm">No data</div>
        </div>
        <div class="chart-stats" v-if="loadAvgData.length">
          <span>Min <strong>{{ seriesStat(loadAvgData, 'min').toFixed(2) }}</strong></span>
          <span>Avg <strong>{{ seriesStat(loadAvgData, 'avg').toFixed(2) }}</strong></span>
          <span>Max <strong>{{ seriesStat(loadAvgData, 'max').toFixed(2) }}</strong></span>
        </div>
      </div>

      <!-- IO Wait -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">IO Wait</span>
          <span class="chart-card__badge" v-if="ioWaitData.length">
            {{ latestVal(ioWaitData).toFixed(1) }}%
          </span>
        </div>
        <div class="chart-body">
          <PerformanceCharts
            v-if="ioWaitData.length"
            :data="ioWaitData"
            label="IO Wait"
            unit="%"
            color="#ec4899"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="true"
          />
          <div v-else class="chart-empty text-muted text-sm">No data</div>
        </div>
        <div class="chart-stats" v-if="ioWaitData.length">
          <span>Min <strong>{{ seriesStat(ioWaitData, 'min').toFixed(1) }}%</strong></span>
          <span>Avg <strong>{{ seriesStat(ioWaitData, 'avg').toFixed(1) }}%</strong></span>
          <span>Max <strong>{{ seriesStat(ioWaitData, 'max').toFixed(1) }}%</strong></span>
        </div>
      </div>
    </div>

    <!-- No data state -->
    <div v-else-if="!loading" class="no-data-state">
      <div class="text-muted text-sm">No performance data available for this node / time range.</div>
      <button class="btn btn-outline btn-sm mt-2" @click="refreshAll">Retry</button>
    </div>

    <!-- ── Storage Usage Section ───────────────────────────────────────────── -->
    <div v-if="storageList.length" class="section-block">
      <h3 class="section-title">Storage Usage</h3>
      <div class="storage-grid">
        <div
          v-for="stor in storageList"
          :key="stor.storage"
          class="storage-card card"
        >
          <div class="storage-card__header">
            <span class="storage-card__name">{{ stor.storage }}</span>
            <span class="storage-card__type text-xs text-muted">{{ stor.type }}</span>
          </div>
          <div class="storage-card__pct" :style="{ color: stor.pct > 90 ? '#ef4444' : stor.pct > 75 ? '#f59e0b' : '#10b981' }">
            {{ stor.pct.toFixed(1) }}%
          </div>
          <div class="stat-card__bar mt-1">
            <div
              class="stat-bar__fill"
              :style="{
                width: Math.min(stor.pct, 100) + '%',
                background: stor.pct > 90 ? '#ef4444' : stor.pct > 75 ? '#f59e0b' : '#10b981'
              }"
            ></div>
          </div>
          <div class="storage-card__detail text-xs text-muted mt-1">
            {{ formatBytes(stor.used) }} / {{ formatBytes(stor.total) }}
          </div>
          <div class="storage-card__avail text-xs text-muted">
            {{ formatBytes(stor.avail) }} free
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import { formatBytes, formatUptime } from '@/utils/proxmox'
import PerformanceCharts from '@/components/PerformanceCharts.vue'
import MultiLineChart from '@/components/MultiLineChart.vue'

const route = useRoute()
const router = useRouter()

// ── Resolve host / node from route params OR query params ──────────────────
const resolvedHostId = computed(() =>
  route.params.hostId || route.query.hostId || null
)
const resolvedNode = computed(() =>
  route.params.node || route.query.node || null
)

// ── All nodes (for node selector) ─────────────────────────────────────────
const allNodes = ref([])
const selectedNodeKey = ref('')
const hostsMap = ref({}) // hostId -> hostObj

const buildNodeKey = (hostId, node) => `${hostId}::${node}`

const onNodeChange = () => {
  const [hostId, node] = selectedNodeKey.value.split('::')
  // Navigate to the path-param version if we have it, otherwise query-param
  if (route.params.hostId) {
    router.push(`/monitor/${hostId}/${node}`)
  } else {
    router.push({ path: '/node-monitor', query: { hostId, node } })
  }
}

const loadAllNodes = async () => {
  try {
    const hostsRes = await api.proxmox.listHosts()
    const hosts = hostsRes.data?.items || hostsRes.data || []
    const nodes = []
    for (const host of hosts) {
      hostsMap.value[host.id] = host
      try {
        const nodesRes = await api.pveNode.clusterResources(host.id, 'node')
        const hostNodes = nodesRes.data || []
        hostNodes.forEach(n => {
          nodes.push({
            key: buildNodeKey(host.id, n.node),
            hostId: host.id,
            hostName: host.name || host.hostname,
            node: n.node,
          })
        })
      } catch {
        // skip unreachable hosts
      }
    }
    allNodes.value = nodes
    // Set current selection
    if (resolvedHostId.value && resolvedNode.value) {
      selectedNodeKey.value = buildNodeKey(resolvedHostId.value, resolvedNode.value)
    }
  } catch (e) {
    console.warn('Could not load all nodes for selector', e)
  }
}

// ── Time range ─────────────────────────────────────────────────────────────
const timeRanges = [
  { label: '1h', tf: 'hour' },
  { label: '6h', tf: 'day' },
  { label: '24h', tf: 'day' },
  { label: '3d', tf: 'week' },
  { label: '1w', tf: 'week' },
  { label: '1mo', tf: 'month' },
]
const selectedRange = ref('1h')
const timeframe = computed(() => {
  const tr = timeRanges.find(t => t.label === selectedRange.value)
  return tr ? tr.tf : 'hour'
})

const setRange = (label) => {
  selectedRange.value = label
  loadRrd()
}

// ── Auto-refresh ───────────────────────────────────────────────────────────
const autoRefresh = ref(true)
let refreshTimer = null

const scheduleRefresh = () => {
  clearRefresh()
  if (!autoRefresh.value) return
  const ms = 30000
  refreshTimer = setInterval(refreshAll, ms)
}

const clearRefresh = () => {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
}

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) scheduleRefresh()
  else clearRefresh()
}

// ── State ──────────────────────────────────────────────────────────────────
const loading = ref(false)
const loadError = ref(null)
const rrdData = ref([])
const nodeStatus = ref(null)
const storageList = ref([])

// Disk I/O — rolling history sampled from disk-io-rates endpoint
const diskIoHistory = ref([])   // [{time, read, write}]
const MAX_DISK_IO_SAMPLES = 120  // 20 minutes at 10s interval
let diskIoTimer = null

const loadDiskIoRate = async () => {
  if (!resolvedHostId.value || !resolvedNode.value) return
  try {
    const res = await api.pveNode.diskIoRates(resolvedHostId.value)
    const rates = res.data || []
    const node = rates.find(r => r.node === resolvedNode.value)
    if (node) {
      diskIoHistory.value.push({
        time: Math.floor(Date.now() / 1000),
        read: node.read || 0,
        write: node.write || 0,
      })
      if (diskIoHistory.value.length > MAX_DISK_IO_SAMPLES) {
        diskIoHistory.value = diskIoHistory.value.slice(-MAX_DISK_IO_SAMPLES)
      }
    }
  } catch { /* silent */ }
}

const startDiskIoPolling = () => {
  stopDiskIoPolling()
  loadDiskIoRate()
  diskIoTimer = setInterval(loadDiskIoRate, 10000)
}

const stopDiskIoPolling = () => {
  if (diskIoTimer) { clearInterval(diskIoTimer); diskIoTimer = null }
}

const chartHeight = 130

// ── Data loaders ───────────────────────────────────────────────────────────
const loadNodeStatus = async () => {
  if (!resolvedHostId.value || !resolvedNode.value) return
  try {
    const res = await api.pveNode.nodeStatus(resolvedHostId.value, resolvedNode.value)
    nodeStatus.value = res.data
  } catch (e) {
    console.warn('Node status failed', e)
  }
}

const loadRrd = async () => {
  if (!resolvedHostId.value || !resolvedNode.value) return
  loading.value = true
  loadError.value = null
  try {
    const res = await api.pveNode.nodeRrdData(resolvedHostId.value, resolvedNode.value, {
      timeframe: timeframe.value,
      cf: 'AVERAGE'
    })
    rrdData.value = res.data || []
  } catch (e) {
    console.warn('RRD load failed', e)
    loadError.value = 'Failed to load performance data. ' + (e?.response?.data?.detail || e?.message || '')
    rrdData.value = []
  } finally {
    loading.value = false
  }
}

const loadStorage = async () => {
  if (!resolvedHostId.value || !resolvedNode.value) return
  try {
    const res = await api.pveNode.listStorage(resolvedHostId.value, resolvedNode.value)
    const raw = res.data || []
    storageList.value = raw
      .filter(s => s.total && s.total > 0)
      .map(s => ({
        storage: s.storage,
        type: s.type || '—',
        total: s.total,
        used: s.used ?? (s.total - (s.avail ?? 0)),
        avail: s.avail ?? 0,
        pct: s.total ? ((s.used ?? (s.total - (s.avail ?? 0))) / s.total) * 100 : 0,
      }))
      .sort((a, b) => b.pct - a.pct)
  } catch (e) {
    console.warn('Storage load failed', e)
  }
}

const refreshAll = async () => {
  await Promise.all([loadNodeStatus(), loadRrd(), loadStorage()])
}

// ── Data series ────────────────────────────────────────────────────────────
const makeDataSeries = (field, transform) => computed(() =>
  rrdData.value
    .filter(d => d[field] != null && isFinite(d[field]))
    .map(d => ({ time: d.time, value: transform ? transform(d) : d[field] }))
)

const cpuData = makeDataSeries('cpu', d => d.cpu * 100)
const memData = computed(() =>
  rrdData.value
    .filter(d => d.memtotal && d.memused != null && isFinite(d.memused))
    .map(d => ({ time: d.time, value: (d.memused / d.memtotal) * 100 }))
)
const netInData = makeDataSeries('netin', d => d.netin / 1e6)
const netOutData = makeDataSeries('netout', d => d.netout / 1e6)
// Disk I/O from rolling rate history (not RRD — node RRD doesn't include diskread/write)
const diskReadData = computed(() =>
  diskIoHistory.value.map(d => ({ time: d.time, value: d.read / 1e6 }))
)
const diskWriteData = computed(() =>
  diskIoHistory.value.map(d => ({ time: d.time, value: d.write / 1e6 }))
)
const loadAvgData = makeDataSeries('loadavg')
const ioWaitData = makeDataSeries('iowait', d => d.iowait * 100)

// Multi-line series configs
const netSeries = computed(() => [
  { label: 'In', data: netInData.value, color: '#06b6d4' },
  { label: 'Out', data: netOutData.value, color: '#f59e0b' },
])

const diskSeries = computed(() => [
  { label: 'Read', data: diskReadData.value, color: '#8b5cf6' },
  { label: 'Write', data: diskWriteData.value, color: '#ef4444' },
])

// ── Current stat computeds ─────────────────────────────────────────────────
const nodeCpuPct = computed(() => {
  if (!nodeStatus.value?.cpu) return 0
  const v = nodeStatus.value.cpu
  return parseFloat((v > 1 ? v : v * 100).toFixed(1))
})
const nodeMemPct = computed(() => {
  const m = nodeStatus.value?.memory
  if (!m?.total || m?.used == null) return 0
  return parseFloat(((m.used / m.total) * 100).toFixed(1))
})
const nodeSwapPct = computed(() => {
  const s = nodeStatus.value?.swap
  if (!s?.total || !s?.used) return 0
  return parseFloat(((s.used / s.total) * 100).toFixed(1))
})
const nodeRootPct = computed(() => {
  const r = nodeStatus.value?.rootfs
  if (!r?.total || r?.used == null) return 0
  return parseFloat(((r.used / r.total) * 100).toFixed(1))
})

const cpuColor = computed(() => {
  const p = nodeCpuPct.value
  return p > 90 ? '#ef4444' : p > 70 ? '#f59e0b' : '#3b82f6'
})
const memColor = computed(() => {
  const p = nodeMemPct.value
  return p > 90 ? '#ef4444' : p > 75 ? '#f59e0b' : '#10b981'
})
const diskColor = computed(() => {
  const p = nodeRootPct.value
  return p > 90 ? '#ef4444' : p > 75 ? '#f59e0b' : '#8b5cf6'
})

const loadAvg1m = computed(() => {
  const la = nodeStatus.value?.loadavg
  if (!la) return '—'
  if (Array.isArray(la)) return parseFloat(la[0]).toFixed(2)
  return String(la)
})
const loadAvg5m = computed(() => {
  const la = nodeStatus.value?.loadavg
  if (!la || !Array.isArray(la)) return '—'
  return parseFloat(la[1] ?? la[0]).toFixed(2)
})
const loadAvg15m = computed(() => {
  const la = nodeStatus.value?.loadavg
  if (!la || !Array.isArray(la)) return '—'
  return parseFloat(la[2] ?? la[0]).toFixed(2)
})

const nodeHost = computed(() => {
  const h = hostsMap.value[resolvedHostId.value]
  return h?.hostname || h?.host || ''
})

// ── Helper functions ───────────────────────────────────────────────────────
const latestVal = (series) => {
  if (!series.length) return 0
  return series[series.length - 1].value
}

const seriesStat = (series, stat) => {
  if (!series.length) return 0
  const vals = series.map(d => d.value)
  if (stat === 'min') return Math.min(...vals)
  if (stat === 'max') return Math.max(...vals)
  if (stat === 'avg') return vals.reduce((a, b) => a + b, 0) / vals.length
  return 0
}

const formatMBs = (v) => {
  if (v == null || !isFinite(v)) return '—'
  if (v >= 1) return v.toFixed(2) + ' MB/s'
  if (v >= 0.001) return (v * 1000).toFixed(1) + ' KB/s'
  return (v * 1e6).toFixed(0) + ' B/s'
}

const formatMBsVal = (v) => {
  if (v == null || !isFinite(v)) return '—'
  if (v >= 1) return v.toFixed(2) + ' MB/s'
  if (v >= 0.001) return (v * 1000).toFixed(1) + ' KB/s'
  return (v * 1e6).toFixed(0) + ' B/s'
}

const formatLoadAvg = (la) => {
  if (!la) return '—'
  if (Array.isArray(la)) return la.slice(0, 3).map(v => parseFloat(v).toFixed(2)).join(' / ')
  return String(la)
}

// ── CSV Export ─────────────────────────────────────────────────────────────
const exportCSV = () => {
  if (!rrdData.value.length) return
  const headers = ['time', 'cpu_pct', 'mem_pct', 'netin_mbs', 'netout_mbs',
    'diskread_mbs', 'diskwrite_mbs', 'loadavg', 'iowait_pct']
  const rows = rrdData.value.map(d => {
    const t = d.time ? new Date(d.time * 1000).toISOString() : ''
    const cpu = d.cpu != null ? (d.cpu * 100).toFixed(2) : ''
    const mem = d.memtotal && d.memused != null ? ((d.memused / d.memtotal) * 100).toFixed(2) : ''
    const ni = d.netin != null ? (d.netin / 1e6).toFixed(4) : ''
    const no = d.netout != null ? (d.netout / 1e6).toFixed(4) : ''
    const dr = d.diskread != null ? (d.diskread / 1e6).toFixed(4) : ''
    const dw = d.diskwrite != null ? (d.diskwrite / 1e6).toFixed(4) : ''
    const la = d.loadavg != null ? d.loadavg : ''
    const iow = d.iowait != null ? (d.iowait * 100).toFixed(2) : ''
    return [t, cpu, mem, ni, no, dr, dw, la, iow].join(',')
  })
  const csv = [headers.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `node-${resolvedNode.value || 'monitor'}-${selectedRange.value}-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Lifecycle ──────────────────────────────────────────────────────────────
onMounted(async () => {
  if (resolvedHostId.value && resolvedNode.value) {
    selectedNodeKey.value = buildNodeKey(resolvedHostId.value, resolvedNode.value)
  }
  await refreshAll()
  loadAllNodes() // non-blocking background load
  scheduleRefresh()
  startDiskIoPolling()
})

onUnmounted(() => {
  clearRefresh()
  stopDiskIoPolling()
})

// Re-load when route params change (navigating between nodes)
watch([resolvedHostId, resolvedNode], async ([hid, node]) => {
  if (hid && node) {
    selectedNodeKey.value = buildNodeKey(hid, node)
    rrdData.value = []
    nodeStatus.value = null
    storageList.value = []
    diskIoHistory.value = []
    await refreshAll()
    clearRefresh()
    scheduleRefresh()
    startDiskIoPolling()
  }
})
</script>

<style scoped>
/* ── Page layout ─────────────────────────────────────────────────────────── */
.node-monitor-page {
  padding: 0;
}

/* ── Header ──────────────────────────────────────────────────────────────── */
.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
}

.monitor-header__left {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 0;
}

.back-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.8rem;
}
.back-link:hover { color: var(--text-primary); }

.monitor-title-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.monitor-title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.monitor-node-name {
  color: var(--text-secondary);
  font-weight: 400;
}

.monitor-meta {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

/* ── Header right ─────────────────────────────────────────────────────────── */
.monitor-header__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.6rem;
  flex-shrink: 0;
}

.node-selector-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.control-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.time-range-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.time-range-selector {
  display: flex;
  gap: 2px;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.4rem;
  padding: 2px;
}

.tr-btn {
  background: none;
  border: none;
  padding: 0.25rem 0.65rem;
  border-radius: 0.3rem;
  cursor: pointer;
  font-size: 0.78rem;
  color: var(--text-secondary);
  transition: all 0.15s;
  white-space: nowrap;
}
.tr-btn:hover { color: var(--text-primary); background: var(--background); }
.tr-btn--active { background: var(--primary-color); color: white; font-weight: 600; }

.controls-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.refresh-dot-sm {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  margin-right: 4px;
  opacity: 0.5;
}
.refresh-dot-sm--active {
  opacity: 1;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

/* ── Error banner ─────────────────────────────────────────────────────────── */
.error-banner {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
  border-radius: 0.4rem;
  padding: 0.6rem 1rem;
  font-size: 0.875rem;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

/* ── Current stats row ────────────────────────────────────────────────────── */
.current-stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(155px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.875rem 1rem;
  box-shadow: var(--shadow);
}

.stat-card__label {
  font-size: 0.68rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.25rem;
}

.stat-card__value {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
  margin-bottom: 0.4rem;
}

.stat-card__bar {
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 0.3rem;
}

.stat-bar__fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
}

.stat-card__sub {
  line-height: 1.3;
}

/* ── Loading ──────────────────────────────────────────────────────────────── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem 0;
}

/* ── Charts grid — 2 columns ──────────────────────────────────────────────── */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

@media (max-width: 900px) {
  .charts-grid { grid-template-columns: 1fr; }
}

.chart-card {
  overflow: hidden;
}

.chart-card__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 0.7rem 1rem 0.2rem;
}

.chart-card__title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.chart-card__badge {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-secondary);
  font-family: monospace;
}

.chart-body {
  height: 130px;
  padding: 0.2rem 0.5rem 0.2rem;
  position: relative;
}

.chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

/* Min/avg/max stats row */
.chart-stats {
  display: flex;
  justify-content: space-around;
  padding: 0.3rem 1rem 0.6rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
  border-top: 1px solid var(--border-color);
  margin-top: 0.2rem;
}

.chart-stats strong {
  color: var(--text-primary);
  font-family: monospace;
}

/* ── No data ──────────────────────────────────────────────────────────────── */
.no-data-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2rem;
  color: var(--text-secondary);
}

/* ── Section block ────────────────────────────────────────────────────────── */
.section-block {
  margin-top: 1.5rem;
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.75rem;
}

/* ── Storage grid ─────────────────────────────────────────────────────────── */
.storage-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.75rem;
}

.storage-card {
  padding: 0.875rem 1rem;
}

.storage-card__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.3rem;
}

.storage-card__name {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-primary);
}

.storage-card__type {
  font-family: monospace;
}

.storage-card__pct {
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1;
}

.storage-card__detail,
.storage-card__avail {
  line-height: 1.3;
}

/* ── Process notice ───────────────────────────────────────────────────────── */
.process-notice {
  display: flex;
  gap: 1rem;
  padding: 1.25rem;
  align-items: flex-start;
}

.process-notice__icon {
  font-size: 1.4rem;
  color: var(--text-secondary);
  flex-shrink: 0;
  line-height: 1;
}

.process-notice__content {
  flex: 1;
  min-width: 0;
}

.process-notice__actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.process-summary__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.6rem;
}

.proc-stat {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.4rem;
  padding: 0.5rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.proc-stat__label {
  font-size: 0.68rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.proc-stat__val {
  font-size: 0.9rem;
  font-weight: 700;
  font-family: monospace;
  color: var(--text-primary);
}

/* ── Utilities ────────────────────────────────────────────────────────────── */
.ml-2 { margin-left: 0.5rem; }
.mt-1 { margin-top: 0.35rem; }
.mt-2 { margin-top: 0.75rem; }
.mt-3 { margin-top: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.text-muted { color: var(--text-secondary); }
</style>
