<template>
  <div class="node-monitor-page">
    <!-- Header -->
    <div class="monitor-header">
      <div class="monitor-header__left">
        <router-link
          v-if="hostId && node"
          :to="`/proxmox/${hostId}/nodes/${node}`"
          class="back-link"
        >← {{ node }}</router-link>
        <h2 class="monitor-title">
          Performance Monitor
          <span v-if="node" class="monitor-node-name">— {{ node }}</span>
          <span v-if="nodeStatus" :class="nodeStatus.status === 'online' ? 'badge badge-success ml-1' : 'badge badge-danger ml-1'">
            {{ nodeStatus.status }}
          </span>
        </h2>
        <div v-if="nodeStatus" class="monitor-meta text-sm text-muted">
          <span v-if="nodeStatus.uptime">Uptime: {{ formatUptime(nodeStatus.uptime) }}</span>
          <span v-if="nodeStatus.pveversion || nodeStatus['pve-manager-version']">
            PVE {{ nodeStatus.pveversion || nodeStatus['pve-manager-version'] }}
          </span>
        </div>
      </div>

      <div class="monitor-header__right">
        <!-- Time range selector -->
        <div class="time-range-selector">
          <button
            v-for="tr in timeRanges"
            :key="tr.value"
            :class="['tr-btn', timeframe === tr.value ? 'tr-btn--active' : '']"
            @click="setTimeframe(tr.value)"
          >{{ tr.label }}</button>
        </div>
        <!-- Auto-refresh indicator -->
        <div class="refresh-indicator text-sm text-muted">
          <span :class="['refresh-dot', autoRefreshing ? 'refresh-dot--active' : '']"></span>
          {{ autoRefreshLabel }}
        </div>
      </div>
    </div>

    <!-- Current Stats Cards -->
    <div v-if="nodeStatus" class="current-stats-row">
      <div class="stat-card">
        <div class="stat-card__label">CPU</div>
        <div class="stat-card__value" :style="{ color: cpuColor }">{{ nodeCpuPct }}%</div>
        <div class="stat-card__bar">
          <div class="stat-bar__fill" :style="{ width: nodeCpuPct + '%', background: cpuColor }"></div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">Memory</div>
        <div class="stat-card__value" :style="{ color: memColor }">{{ nodeMemPct }}%</div>
        <div class="stat-card__bar">
          <div class="stat-bar__fill" :style="{ width: nodeMemPct + '%', background: memColor }"></div>
        </div>
        <div class="stat-card__sub text-sm text-muted">
          {{ formatBytes(nodeStatus.memory?.used) }} / {{ formatBytes(nodeStatus.memory?.total) }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">Swap</div>
        <div class="stat-card__value">{{ nodeSwapPct }}%</div>
        <div class="stat-card__bar">
          <div class="stat-bar__fill" :style="{ width: nodeSwapPct + '%', background: '#f59e0b' }"></div>
        </div>
        <div class="stat-card__sub text-sm text-muted">
          {{ formatBytes(nodeStatus.swap?.used) }} / {{ formatBytes(nodeStatus.swap?.total) }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">Root Disk</div>
        <div class="stat-card__value">{{ nodeRootPct }}%</div>
        <div class="stat-card__bar">
          <div class="stat-bar__fill" :style="{ width: nodeRootPct + '%', background: '#8b5cf6' }"></div>
        </div>
        <div class="stat-card__sub text-sm text-muted">
          {{ formatBytes(nodeStatus.rootfs?.used) }} / {{ formatBytes(nodeStatus.rootfs?.total) }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">Load Avg</div>
        <div class="stat-card__value text-sm">{{ formatLoadAvg(nodeStatus.loadavg) }}</div>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading && !rrdData.length" class="loading-state">
      <div class="loading-spinner"></div>
      <div class="text-muted text-sm mt-2">Loading performance data...</div>
    </div>

    <!-- Charts Grid -->
    <div v-else class="charts-grid">
      <!-- CPU Usage -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">CPU Usage</span>
          <span class="chart-card__current" v-if="cpuData.length">
            {{ latestVal(cpuData).toFixed(1) }}%
          </span>
        </div>
        <div class="chart-body">
          <PerformanceCharts
            v-if="cpuData.length"
            :data="cpuData"
            label="CPU Usage"
            unit="%"
            color="#3b82f6"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="true"
          />
          <div v-else class="chart-empty text-muted text-sm">No data</div>
        </div>
      </div>

      <!-- Memory Usage -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">Memory Usage</span>
          <span class="chart-card__current" v-if="memData.length">
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
      </div>

      <!-- Network In -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">Network In</span>
          <span class="chart-card__current" v-if="netInData.length">
            {{ formatMBs(latestVal(netInData)) }}
          </span>
        </div>
        <div class="chart-body">
          <PerformanceCharts
            v-if="netInData.length"
            :data="netInData"
            label="Network In"
            unit="MB/s"
            color="#06b6d4"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="true"
          />
          <div v-else class="chart-empty text-muted text-sm">No data</div>
        </div>
      </div>

      <!-- Network Out -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">Network Out</span>
          <span class="chart-card__current" v-if="netOutData.length">
            {{ formatMBs(latestVal(netOutData)) }}
          </span>
        </div>
        <div class="chart-body">
          <PerformanceCharts
            v-if="netOutData.length"
            :data="netOutData"
            label="Network Out"
            unit="MB/s"
            color="#f59e0b"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="true"
          />
          <div v-else class="chart-empty text-muted text-sm">No data</div>
        </div>
      </div>

      <!-- Disk Read -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">Disk Read</span>
          <span class="chart-card__current" v-if="diskReadData.length">
            {{ formatMBs(latestVal(diskReadData)) }}
          </span>
        </div>
        <div class="chart-body">
          <PerformanceCharts
            v-if="diskReadData.length"
            :data="diskReadData"
            label="Disk Read"
            unit="MB/s"
            color="#8b5cf6"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="true"
          />
          <div v-else class="chart-empty text-muted text-sm">No data</div>
        </div>
      </div>

      <!-- Disk Write -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">Disk Write</span>
          <span class="chart-card__current" v-if="diskWriteData.length">
            {{ formatMBs(latestVal(diskWriteData)) }}
          </span>
        </div>
        <div class="chart-body">
          <PerformanceCharts
            v-if="diskWriteData.length"
            :data="diskWriteData"
            label="Disk Write"
            unit="MB/s"
            color="#ef4444"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="true"
          />
          <div v-else class="chart-empty text-muted text-sm">No data</div>
        </div>
      </div>

      <!-- Load Average -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">Load Average</span>
          <span class="chart-card__current" v-if="loadAvgData.length">
            {{ latestVal(loadAvgData).toFixed(2) }}
          </span>
        </div>
        <div class="chart-body">
          <PerformanceCharts
            v-if="loadAvgData.length"
            :data="loadAvgData"
            label="Load Average"
            unit=""
            color="#f97316"
            :height="chartHeight"
            :showGrid="true"
            :fillArea="true"
          />
          <div v-else class="chart-empty text-muted text-sm">No data</div>
        </div>
      </div>

      <!-- IO Wait -->
      <div class="chart-card card">
        <div class="chart-card__header">
          <span class="chart-card__title">IO Wait</span>
          <span class="chart-card__current" v-if="ioWaitData.length">
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
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { formatBytes, formatUptime } from '@/utils/proxmox'
import PerformanceCharts from '@/components/PerformanceCharts.vue'

const route = useRoute()

const hostId = computed(() => route.query.hostId)
const node = computed(() => route.query.node)

const timeRanges = [
  { label: '1h', value: 'hour' },
  { label: '6h', value: 'day' },
  { label: '24h', value: 'day' },
  { label: '3d', value: 'week' },
  { label: '1w', value: 'week' },
  { label: '1mo', value: 'month' },
]

// Map display label to Proxmox timeframe param
const timeframeLabelMap = {
  '1h': 'hour',
  '6h': 'day',
  '24h': 'day',
  '3d': 'week',
  '1w': 'week',
  '1mo': 'month',
}

const timeRangeLabels = ['1h', '6h', '24h', '3d', '1w', '1mo']
const selectedRange = ref('1h')
const timeframe = computed(() => timeframeLabelMap[selectedRange.value] || 'hour')

const loading = ref(false)
const rrdData = ref([])
const nodeStatus = ref(null)

const chartHeight = 130
const autoRefreshing = ref(false)

const autoRefreshLabel = computed(() => {
  if (selectedRange.value === '1h') return 'Auto-refresh: 30s'
  return 'Auto-refresh: 5m'
})

let refreshTimer = null

const setTimeframe = (val) => {
  selectedRange.value = val
  loadRrd()
  scheduleRefresh()
}

// ── Data derivation ────────────────────────────────────────────────────────────

const makeDataSeries = (field, transform) => computed(() =>
  rrdData.value
    .filter(d => d[field] != null && isFinite(d[field]))
    .map(d => ({
      time: d.time,
      value: transform ? transform(d) : d[field],
    }))
)

const cpuData = makeDataSeries('cpu', d => d.cpu * 100)
const memData = computed(() =>
  rrdData.value
    .filter(d => d.memtotal && d.memused != null)
    .map(d => ({ time: d.time, value: (d.memused / d.memtotal) * 100 }))
)
const netInData = makeDataSeries('netin', d => d.netin / 1e6)
const netOutData = makeDataSeries('netout', d => d.netout / 1e6)
const diskReadData = makeDataSeries('diskread', d => d.diskread / 1e6)
const diskWriteData = makeDataSeries('diskwrite', d => d.diskwrite / 1e6)
const loadAvgData = makeDataSeries('loadavg')
const ioWaitData = makeDataSeries('iowait', d => d.iowait * 100)

// ── Current stats ─────────────────────────────────────────────────────────────

const nodeCpuPct = computed(() => {
  if (!nodeStatus.value?.cpu) return 0
  const v = nodeStatus.value.cpu
  return parseFloat((v > 1 ? v : v * 100).toFixed(1))
})

const nodeMemPct = computed(() => {
  const m = nodeStatus.value?.memory
  if (!m?.total || !m?.used) return 0
  return parseFloat(((m.used / m.total) * 100).toFixed(1))
})

const nodeSwapPct = computed(() => {
  const s = nodeStatus.value?.swap
  if (!s?.total || !s?.used) return 0
  return parseFloat(((s.used / s.total) * 100).toFixed(1))
})

const nodeRootPct = computed(() => {
  const r = nodeStatus.value?.rootfs
  if (!r?.total || !r?.used) return 0
  return parseFloat(((r.used / r.total) * 100).toFixed(1))
})

const cpuColor = computed(() => {
  const p = nodeCpuPct.value
  if (p > 90) return '#ef4444'
  if (p > 70) return '#f59e0b'
  return '#3b82f6'
})

const memColor = computed(() => {
  const p = nodeMemPct.value
  if (p > 90) return '#ef4444'
  if (p > 75) return '#f59e0b'
  return '#10b981'
})

// ── Helpers ───────────────────────────────────────────────────────────────────

const latestVal = (series) => {
  if (!series.length) return 0
  return series[series.length - 1].value
}

const formatMBs = (v) => {
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

// ── Data loading ──────────────────────────────────────────────────────────────

const loadNodeStatus = async () => {
  if (!hostId.value || !node.value) return
  try {
    const res = await api.pveNode.nodeStatus(hostId.value, node.value)
    nodeStatus.value = res.data
  } catch (e) {
    console.warn('Node status failed', e)
  }
}

const loadRrd = async () => {
  if (!hostId.value || !node.value) return
  loading.value = true
  try {
    const res = await api.pveNode.nodeRrdData(hostId.value, node.value, {
      timeframe: timeframe.value,
      cf: 'AVERAGE'
    })
    rrdData.value = res.data || []
  } catch (e) {
    console.warn('RRD load failed', e)
    rrdData.value = []
  } finally {
    loading.value = false
  }
}

const scheduleRefresh = () => {
  if (refreshTimer) clearInterval(refreshTimer)
  const intervalMs = selectedRange.value === '1h' ? 30000 : 300000
  autoRefreshing.value = true
  refreshTimer = setInterval(async () => {
    await Promise.all([loadNodeStatus(), loadRrd()])
  }, intervalMs)
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await Promise.all([loadNodeStatus(), loadRrd()])
  scheduleRefresh()
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.node-monitor-page {
  padding: 0;
}

/* Header */
.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
}

.monitor-header__left {
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

.monitor-title {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
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

.monitor-header__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.5rem;
}

/* Time range selector */
.time-range-selector {
  display: flex;
  gap: 2px;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 3px;
}

.tr-btn {
  background: none;
  border: none;
  padding: 0.3rem 0.75rem;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--text-secondary);
  transition: all 0.15s;
  white-space: nowrap;
}

.tr-btn:hover {
  color: var(--text-primary);
  background: var(--background);
}

.tr-btn--active {
  background: var(--primary-color);
  color: white;
  font-weight: 600;
}

.refresh-indicator {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.refresh-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--border-color);
}

.refresh-dot--active {
  background: #10b981;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* Current stats row */
.current-stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
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
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.25rem;
}

.stat-card__value {
  font-size: 1.35rem;
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
  margin-bottom: 0.35rem;
}

.stat-bar__fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
  max-width: 100%;
}

.stat-card__sub {
  line-height: 1.2;
}

/* Loading state */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem 0;
}

/* Charts grid — 2 columns on desktop, 1 on mobile */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 900px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  overflow: hidden;
}

.chart-card__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 0.75rem 1rem 0.25rem;
}

.chart-card__title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.chart-card__current {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-secondary);
  font-family: monospace;
}

.chart-body {
  height: 130px;
  padding: 0.25rem 0.5rem 0.5rem;
  position: relative;
}

.chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

/* Badge/utility */
.ml-1 { margin-left: 0.25rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.mt-2 { margin-top: 0.75rem; }
</style>
