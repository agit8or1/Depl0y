<template>
  <div class="storage-overview">
    <div v-if="loading" class="wl">Loading storage...</div>
    <div v-else-if="storages.length === 0" class="we">No storage data available.</div>
    <div v-else class="storage-list">
      <div v-for="s in storages" :key="s.label" class="stor-row">
        <div class="stor-header">
          <span class="stor-name">{{ s.label }}</span>
          <span class="stor-pct" :class="s.pct > 85 ? 'text-danger' : s.pct > 70 ? 'text-warn' : ''">{{ s.pct }}%</span>
        </div>
        <div class="stor-bar-wrap">
          <div class="stor-bar">
            <div
              class="stor-fill"
              :class="s.pct > 85 ? 'fill-danger' : s.pct > 70 ? 'fill-warn' : 'fill-ok'"
              :style="{ width: s.pct + '%' }"
            ></div>
          </div>
        </div>
        <div class="stor-vals">{{ s.used }} / {{ s.total }}</div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

const fmt = (bytes) => {
  if (!bytes) return '0 B'
  const gb = bytes / (1024 ** 3)
  if (gb >= 1) return gb.toFixed(1) + ' GB'
  const mb = bytes / (1024 ** 2)
  return mb.toFixed(0) + ' MB'
}

export default {
  name: 'StorageOverviewWidget',
  setup() {
    const loading = ref(true)
    const storages = ref([])
    let timer = null

    const fetch = async () => {
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = (hostsRes.data || []).filter(h => h.is_active)
        if (!hosts.length) { loading.value = false; return }

        const resourceResults = await Promise.allSettled(
          hosts.map(h => api.pveNode.clusterResources(h.id))
        )
        const storageMap = {}
        resourceResults.forEach((result) => {
          if (result.status === 'fulfilled') {
            ;(result.value.data || []).forEach(item => {
              if (item.type === 'storage') {
                const key = item.storage || item.id
                if (!storageMap[key]) {
                  storageMap[key] = { maxdisk: 0, disk: 0 }
                }
                storageMap[key].maxdisk += item.maxdisk || 0
                storageMap[key].disk += item.disk || 0
              }
            })
          }
        })
        storages.value = Object.entries(storageMap).map(([label, d]) => ({
          label,
          pct: d.maxdisk > 0 ? Math.round((d.disk / d.maxdisk) * 100) : 0,
          used: fmt(d.disk),
          total: fmt(d.maxdisk)
        })).sort((a, b) => b.pct - a.pct)
      } catch (e) {
        // Fallback from node data
        try {
          const res = await api.dashboard.getResources()
          const r = res.data
          if (r.total_disk_gb > 0) {
            storages.value = [{
              label: 'Cluster Total',
              pct: Math.round((r.used_disk_gb / r.total_disk_gb) * 100),
              used: r.used_disk_gb + ' GB',
              total: r.total_disk_gb + ' GB'
            }]
          }
        } catch (e2) {}
      }
      loading.value = false
    }

    onMounted(() => { fetch(); timer = setInterval(fetch, 60000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, storages }
  }
}
</script>

<style scoped>
.storage-overview { height: 100%; }
.wl, .we { font-size: 0.8rem; color: var(--text-secondary); }
.storage-list { display: flex; flex-direction: column; gap: 0.6rem; }
.stor-row { display: flex; flex-direction: column; gap: 0.2rem; }
.stor-header { display: flex; justify-content: space-between; align-items: baseline; }
.stor-name { font-size: 0.78rem; font-weight: 500; color: var(--text-primary); }
.stor-pct { font-size: 0.75rem; font-weight: 700; }
.text-danger { color: #ef4444; }
.text-warn   { color: #f59e0b; }
.stor-bar-wrap { width: 100%; }
.stor-bar { height: 0.4rem; background: var(--border-color); border-radius: 9999px; overflow: hidden; }
.stor-fill { height: 100%; border-radius: 9999px; transition: width 0.3s; }
.fill-ok     { background: var(--primary-color); }
.fill-warn   { background: #f59e0b; }
.fill-danger { background: #ef4444; }
.stor-vals { font-size: 0.68rem; color: var(--text-secondary); }
</style>
