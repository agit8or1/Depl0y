<template>
  <div class="disk-io-widget">
    <div v-if="loading" class="wi-empty">Loading disk I/O...</div>
    <div v-else-if="measuring" class="wi-empty">Measuring I/O rates… (ready in ~10s)</div>
    <div v-else-if="nodes.length === 0" class="wi-empty">No running VMs detected.</div>
    <div v-else class="node-list">
      <div v-for="n in nodes" :key="n.key" class="node-row">
        <div class="node-header">
          <span class="node-name">{{ n.label }}</span>
          <span class="node-host">{{ n.hostName }}</span>
        </div>
        <div class="io-bars">
          <div class="io-bar-row">
            <span class="io-label io-read">R</span>
            <div class="io-track">
              <div class="io-fill io-fill--read" :style="{ width: barPct(n.diskRead, n.maxRead) + '%' }"></div>
            </div>
            <span class="io-val">{{ fmtBps(n.diskRead) }}</span>
          </div>
          <div class="io-bar-row">
            <span class="io-label io-write">W</span>
            <div class="io-track">
              <div class="io-fill io-fill--write" :style="{ width: barPct(n.diskWrite, n.maxWrite) + '%' }"></div>
            </div>
            <span class="io-val">{{ fmtBps(n.diskWrite) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

function fmtBps(bytes) {
  if (!bytes || !isFinite(bytes)) return '0 B/s'
  if (bytes >= 1e9) return (bytes / 1e9).toFixed(1) + ' GB/s'
  if (bytes >= 1e6) return (bytes / 1e6).toFixed(1) + ' MB/s'
  if (bytes >= 1e3) return (bytes / 1e3).toFixed(0) + ' KB/s'
  return bytes.toFixed(0) + ' B/s'
}

export default {
  name: 'DiskThroughputWidget',
  setup() {
    const loading  = ref(true)
    const measuring = ref(false)
    const nodes    = ref([])
    let timer = null

    const barPct = (val, max) => (!max ? 0 : Math.min(100, (val / max) * 100))

    const fetchData = async () => {
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = (hostsRes.data || []).filter(h => h.is_active)
        if (!hosts.length) { loading.value = false; return }

        // Backend computes rates from its own persistent counter state
        const results = await Promise.allSettled(
          hosts.map(h => api.pveNode.diskIoRates(h.id))
        )

        const allNodes = []
        results.forEach((res, idx) => {
          if (res.status !== 'fulfilled') return
          const host = hosts[idx]
          ;(res.value.data || []).forEach(n => {
            allNodes.push({
              key:       `${host.id}::${n.node}`,
              label:     n.node,
              hostName:  host.name || host.hostname || '',
              diskRead:  n.read  || 0,
              diskWrite: n.write || 0,
            })
          })
        })

        if (!allNodes.length) {
          // Backend hasn't accumulated a delta yet
          if (nodes.value.length === 0) measuring.value = true
          loading.value = false
          return
        }

        measuring.value = false
        let maxRead = 0, maxWrite = 0
        allNodes.forEach(n => {
          if (n.diskRead  > maxRead)  maxRead  = n.diskRead
          if (n.diskWrite > maxWrite) maxWrite = n.diskWrite
        })
        allNodes.forEach(n => { n.maxRead = maxRead || 1; n.maxWrite = maxWrite || 1 })
        nodes.value = allNodes
      } catch {
        // keep existing data on error
      } finally {
        loading.value = false
      }
    }

    onMounted(() => { fetchData(); timer = setInterval(fetchData, 10000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, measuring, nodes, fmtBps, barPct }
  }
}
</script>

<style scoped>
.disk-io-widget { height: 100%; overflow: auto; }
.wi-empty { font-size: 0.8rem; color: var(--text-secondary); }

.node-list { display: flex; flex-direction: column; gap: 0.9rem; }
.node-row  { display: flex; flex-direction: column; gap: 0.3rem; }

.node-header {
  display: flex; align-items: baseline;
  justify-content: space-between; gap: 0.4rem;
}
.node-name {
  font-size: 0.78rem; font-weight: 600; color: var(--text-primary);
}
.node-host {
  font-size: 0.65rem; color: var(--text-secondary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 60%; text-align: right;
}

.io-bars { display: flex; flex-direction: column; gap: 0.2rem; }
.io-bar-row { display: flex; align-items: center; gap: 0.35rem; }

.io-label {
  font-size: 0.6rem; font-weight: 700; width: 12px;
  flex-shrink: 0; font-variant-numeric: tabular-nums;
}
.io-read  { color: #8b5cf6; }
.io-write { color: #ef4444; }

.io-track {
  flex: 1; height: 6px;
  background: var(--border-color, #374151);
  border-radius: 3px; overflow: hidden;
}
.io-fill {
  height: 100%; border-radius: 3px; transition: width 0.5s ease;
}
.io-fill--read  { background: #8b5cf6; }
.io-fill--write { background: #ef4444; }

.io-val {
  font-size: 0.62rem; font-variant-numeric: tabular-nums;
  color: var(--text-secondary); min-width: 56px;
  text-align: right; flex-shrink: 0;
}
</style>
