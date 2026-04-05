<template>
  <div class="system-info">
    <div v-if="loading" class="wl">Loading system info...</div>
    <div v-else class="info-list">
      <div v-for="item in infoItems" :key="item.label" class="info-row">
        <span class="info-label">{{ item.label }}</span>
        <span class="info-val">{{ item.value }}</span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

const fmtUptime = (s) => {
  if (!s) return '—'
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

const fmtBytes = (b) => {
  if (!b) return '0 B'
  const kb = b / 1024
  if (kb < 1024) return kb.toFixed(1) + ' KB'
  return (kb / 1024).toFixed(2) + ' MB'
}

export default {
  name: 'SystemInfoWidget',
  setup() {
    const loading = ref(true)
    const data = ref({})
    let timer = null

    const infoItems = computed(() => {
      const d = data.value
      return [
        { label: 'Version',    value: d.version || '—' },
        { label: 'App Name',   value: d.app_name || 'Depl0y' },
        { label: 'Status',     value: d.status || '—' },
        { label: 'Uptime',     value: fmtUptime(d.uptime_seconds) },
        { label: 'DB Size',    value: fmtBytes(d.db_size_bytes) },
        { label: 'Users',      value: d.user_count ?? '—' },
        { label: 'VMs (DB)',   value: d.vm_count ?? '—' },
        { label: 'Hosts',      value: d.host_count ?? '—' },
      ]
    })

    const fetch = async () => {
      try {
        const [infoRes, diagRes] = await Promise.allSettled([
          api.system.getInfo(),
          api.system.getDiagnostics()
        ])
        const info = infoRes.status === 'fulfilled' ? infoRes.value.data : {}
        const diag = diagRes.status === 'fulfilled' ? diagRes.value.data : {}
        data.value = { ...info, ...diag }
      } catch (e) {}
      loading.value = false
    }

    onMounted(() => { fetch(); timer = setInterval(fetch, 120000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, infoItems }
  }
}
</script>

<style scoped>
.system-info { height: 100%; }
.wl { font-size: 0.8rem; color: var(--text-secondary); }
.info-list { display: flex; flex-direction: column; gap: 0.35rem; }
.info-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.3rem 0; border-bottom: 1px solid var(--border-color); font-size: 0.82rem;
}
.info-row:last-child { border-bottom: none; }
.info-label { color: var(--text-secondary); font-weight: 500; }
.info-val   { color: var(--text-primary);   font-weight: 600; font-size: 0.8rem; }
</style>
