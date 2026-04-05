<template>
  <div class="alerts-widget">
    <div v-if="loading" class="wl">Loading alerts...</div>
    <div v-else-if="alerts.length === 0" class="we">
      <span class="we-icon">✅</span> No alerts. All systems nominal.
    </div>
    <div v-else class="alerts-list">
      <div
        v-for="(alert, i) in alerts"
        :key="i"
        :class="['alert-row', `alert-${alert.severity}`]"
      >
        <span class="alert-icon">{{ severityIcon(alert.severity) }}</span>
        <div class="alert-body">
          <span class="alert-title">{{ alert.title }}</span>
          <span class="alert-detail">{{ alert.detail }}</span>
        </div>
        <span :class="['alert-chip', `chip-${alert.severity}`]">{{ alert.severity }}</span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

export default {
  name: 'AlertsWidget',
  setup() {
    const loading = ref(true)
    const alerts = ref([])
    let timer = null

    const buildLocalAlerts = async () => {
      const result = []
      try {
        // Try the new alerts endpoint
        const res = await api.dashboard.getAlerts()
        const data = res.data?.alerts || res.data || []
        // Filter to non-info for brevity; show all
        result.push(...data)
      } catch (e) {
        // Fallback: compute from resources + tasks
        try {
          const resRes = await api.dashboard.getResources()
          const r = resRes.data
          if (r && r.total_disk_gb > 0) {
            const pct = (r.used_disk_gb / r.total_disk_gb) * 100
            if (pct > 85) result.push({ severity: 'warning', title: 'Storage above 85%', detail: `${pct.toFixed(1)}% used` })
          }
          if (r && r.total_memory_gb > 0) {
            const pct = (r.used_memory_gb / r.total_memory_gb) * 100
            if (pct > 90) result.push({ severity: 'warning', title: 'Memory above 90%', detail: `${pct.toFixed(1)}% used` })
          }
        } catch (e2) {}
      }
      alerts.value = result.filter(a => a.severity !== 'info').slice(0, 10)
      loading.value = false
    }

    const severityIcon = (s) => {
      switch (s) {
        case 'error':   return '🔴'
        case 'warning': return '⚠️'
        default:        return 'ℹ️'
      }
    }

    onMounted(() => { buildLocalAlerts(); timer = setInterval(buildLocalAlerts, 60000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, alerts, severityIcon }
  }
}
</script>

<style scoped>
.alerts-widget { height: 100%; }
.wl { font-size: 0.8rem; color: var(--text-secondary); }
.we { font-size: 0.82rem; color: var(--text-secondary); display: flex; align-items: center; gap: 0.4rem; padding: 0.25rem 0; }
.we-icon { font-size: 1rem; }

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.alert-row {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.45rem 0.55rem;
  border-radius: 0.375rem;
  border-left: 3px solid transparent;
  font-size: 0.8rem;
}

.alert-error   { border-left-color: #ef4444; background: rgba(239,68,68,0.05); }
.alert-warning { border-left-color: #f59e0b; background: rgba(245,158,11,0.05); }
.alert-info    { border-left-color: #3b82f6; background: rgba(59,130,246,0.05); }

.alert-icon { font-size: 0.9rem; flex-shrink: 0; margin-top: 0.05rem; }
.alert-body { flex: 1; display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; }
.alert-title { font-weight: 600; color: var(--text-primary); }
.alert-detail { color: var(--text-secondary); font-size: 0.72rem; }

.alert-chip {
  font-size: 0.6rem; font-weight: 700; text-transform: uppercase;
  padding: 0.1rem 0.35rem; border-radius: 0.2rem; flex-shrink: 0;
}
.chip-error   { background: rgba(239,68,68,0.12); color: #ef4444; }
.chip-warning { background: rgba(245,158,11,0.15); color: #b45309; }
.chip-info    { background: rgba(59,130,246,0.15); color: #3b82f6; }
</style>
