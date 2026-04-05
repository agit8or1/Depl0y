<template>
  <div class="quick-stats-bar">
    <div v-if="loading" class="qs-loading">
      <div v-for="n in 6" :key="n" class="qs-skeleton"></div>
    </div>
    <div v-else class="qs-grid">
      <div v-for="kpi in kpis" :key="kpi.label" class="qs-kpi" :class="kpi.accent ? `accent-${kpi.accent}` : ''">
        <div class="qs-icon" :class="kpi.iconClass">
          <component :is="kpi.icon" />
        </div>
        <div class="qs-body">
          <span class="qs-value">
            {{ kpi.value }}<span v-if="kpi.unit" class="qs-unit">{{ kpi.unit }}</span>
          </span>
          <span class="qs-label">{{ kpi.label }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import api from '@/services/api'

// Inline SVG icon components
const IconVMs = { render () { return h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8' }, [h('rect', { x: 2, y: 3, width: 20, height: 14, rx: 2 }), h('line', { x1: 8, y1: 21, x2: 16, y2: 21 }), h('line', { x1: 12, y1: 17, x2: 12, y2: 21 })]) } }
const IconPlay = { render () { return h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8' }, [h('polygon', { points: '5 3 19 12 5 21 5 3' })]) } }
const IconBox = { render () { return h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8' }, [h('path', { d: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z' })]) } }
const IconCpu = { render () { return h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8' }, [h('rect', { x: 4, y: 4, width: 16, height: 16, rx: 2 }), h('rect', { x: 9, y: 9, width: 6, height: 6 }), h('line', { x1: 9, y1: 1, x2: 9, y2: 4 }), h('line', { x1: 15, y1: 1, x2: 15, y2: 4 }), h('line', { x1: 9, y1: 20, x2: 9, y2: 23 }), h('line', { x1: 15, y1: 20, x2: 15, y2: 23 }), h('line', { x1: 20, y1: 9, x2: 23, y2: 9 }), h('line', { x1: 20, y1: 14, x2: 23, y2: 14 }), h('line', { x1: 1, y1: 9, x2: 4, y2: 9 }), h('line', { x1: 1, y1: 14, x2: 4, y2: 14 })]) } }
const IconRam = { render () { return h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8' }, [h('path', { d: 'M6 19v-3M10 19v-3M14 19v-3M18 19v-3M8 11V9M16 11V9M3 5h18v10H3z' })]) } }
const IconDisk = { render () { return h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8' }, [h('ellipse', { cx: 12, cy: 5, rx: 9, ry: 3 }), h('path', { d: 'M21 12c0 1.66-4 3-9 3s-9-1.34-9-3' }), h('path', { d: 'M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5' })]) } }

function fmtGb (gb) {
  if (!gb && gb !== 0) return '—'
  if (gb >= 1024) return (gb / 1024).toFixed(1)
  return Math.round(gb)
}

function gbUnit (gb) {
  if (!gb && gb !== 0) return ''
  return gb >= 1024 ? ' TB' : ' GB'
}

export default {
  name: 'QuickStatsBar',
  components: { IconVMs, IconPlay, IconBox, IconCpu, IconRam, IconDisk },
  setup () {
    const loading = ref(true)
    const raw = ref({
      vm_count: 0,
      running_vms: 0,
      node_count: 0,
      storage_used_gb: 0,
    })
    const resources = ref({
      total_cpu_cores: 0,
      total_memory_gb: 0,
      total_disk_gb: 0,
      used_memory_gb: 0,
      used_disk_gb: 0,
    })

    let timer = null

    // Fetch container count separately (from cluster resources)
    const ctCount = ref(0)

    const kpis = computed(() => [
      {
        label: 'Total VMs',
        value: raw.value.vm_count,
        unit: '',
        icon: IconVMs,
        iconClass: 'icon-blue',
        accent: null,
      },
      {
        label: 'Running VMs',
        value: raw.value.running_vms,
        unit: '',
        icon: IconPlay,
        iconClass: 'icon-green',
        accent: 'green',
      },
      {
        label: 'Containers',
        value: ctCount.value,
        unit: '',
        icon: IconBox,
        iconClass: 'icon-purple',
        accent: null,
      },
      {
        label: 'CPU Cores',
        value: resources.value.total_cpu_cores,
        unit: '',
        icon: IconCpu,
        iconClass: 'icon-amber',
        accent: null,
      },
      {
        label: 'Total RAM',
        value: fmtGb(resources.value.total_memory_gb),
        unit: gbUnit(resources.value.total_memory_gb),
        icon: IconRam,
        iconClass: 'icon-cyan',
        accent: null,
      },
      {
        label: 'Storage Used',
        value: fmtGb(resources.value.used_disk_gb),
        unit: gbUnit(resources.value.used_disk_gb),
        icon: IconDisk,
        iconClass: 'icon-orange',
        accent: null,
      },
    ])

    const fetch = async () => {
      try {
        const [summaryRes, resourcesRes] = await Promise.allSettled([
          api.dashboard.getSummary(),
          api.dashboard.getResources(),
        ])

        if (summaryRes.status === 'fulfilled') {
          raw.value = summaryRes.value.data
        }
        if (resourcesRes.status === 'fulfilled') {
          resources.value = resourcesRes.value.data
        }

        // Try to count LXC containers from cluster resources
        try {
          const hostsRes = await api.proxmox.listHosts()
          const hosts = (hostsRes.data || []).filter(h => h.is_active)
          let ct = 0
          const clusterResults = await Promise.allSettled(
            hosts.map(h => api.pveNode.clusterResources(h.id))
          )
          clusterResults.forEach(r => {
            if (r.status === 'fulfilled') {
              ct += (r.value.data || []).filter(item => item.type === 'lxc').length
            }
          })
          ctCount.value = ct
        } catch (e) {
          // not critical
        }
      } catch (e) {
        // silently ignore
      } finally {
        loading.value = false
      }
    }

    onMounted(() => { fetch(); timer = setInterval(fetch, 30000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, kpis }
  }
}
</script>

<style scoped>
.quick-stats-bar {
  width: 100%;
}

/* Loading skeletons */
.qs-loading {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 0.5rem;
}

.qs-skeleton {
  height: 3.5rem;
  background: var(--border-color);
  border-radius: 0.5rem;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* KPI grid */
.qs-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 0.5rem;
}

.qs-kpi {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.65rem 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  transition: all 0.15s;
  min-width: 0;
}

.qs-kpi:hover {
  border-color: var(--primary-color);
  transform: translateY(-1px);
}

.accent-green { border-left: 3px solid #22c55e; }

.qs-icon {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  border-radius: 0.4rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-blue   { background: rgba(59, 130, 246, 0.12); color: #3b82f6; }
.icon-green  { background: rgba(34, 197, 94, 0.12);  color: #22c55e; }
.icon-purple { background: rgba(139, 92, 246, 0.12); color: #8b5cf6; }
.icon-amber  { background: rgba(245, 158, 11, 0.12); color: #f59e0b; }
.icon-cyan   { background: rgba(6, 182, 212, 0.12);  color: #06b6d4; }
.icon-orange { background: rgba(249, 115, 22, 0.12); color: #f97316; }

.qs-body {
  display: flex;
  flex-direction: column;
  gap: 0.05rem;
  min-width: 0;
  flex: 1;
}

.qs-value {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.qs-unit {
  font-size: 0.65rem;
  font-weight: 400;
  color: var(--text-secondary);
}

.qs-label {
  font-size: 0.65rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Responsive */
@media (max-width: 1200px) {
  .qs-grid,
  .qs-loading {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 640px) {
  .qs-grid,
  .qs-loading {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
