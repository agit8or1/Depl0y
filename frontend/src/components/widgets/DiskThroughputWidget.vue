<template>
  <div class="disk-io-widget">
    <div v-if="loading && nodes.length === 0" class="wi-empty">Loading disk I/O...</div>
    <div v-else-if="measuring" class="wi-empty">Measuring I/O rates…</div>
    <div v-else-if="nodes.length === 0" class="wi-empty">No running VMs — start a VM to see disk I/O.</div>
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
  if (bytes == null || !isFinite(bytes) || bytes === 0) return '0 B/s'
  if (bytes >= 1e9) return (bytes / 1e9).toFixed(1) + ' GB/s'
  if (bytes >= 1e6) return (bytes / 1e6).toFixed(1) + ' MB/s'
  if (bytes >= 1e3) return (bytes / 1e3).toFixed(0) + ' KB/s'
  return bytes.toFixed(0) + ' B/s'
}

export default {
  name: 'DiskThroughputWidget',
  setup() {
    const loading = ref(true)
    const measuring = ref(false)
    const nodes = ref([])
    let timer = null
    // Track previous disk counter values per VM to compute rates
    let prevStats = {}  // vmKey -> { read, write, time }

    const barPct = (val, max) => {
      if (!max || max === 0) return 0
      return Math.min(100, (val / max) * 100)
    }

    const fetchData = async () => {
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = (hostsRes.data || []).filter(h => h.is_active)
        if (!hosts.length) { loading.value = false; return }

        const now = Date.now()
        const nodeAgg = {}  // nodeKey -> { key, label, hostName, diskRead, diskWrite }
        const nextStats = {}  // only keep entries for VMs seen this poll

        // Use nocache endpoint so each poll gets fresh Proxmox counters for accurate delta rates
        const resourceResults = await Promise.allSettled(
          hosts.map(h => api.pveNode.clusterResourcesFresh(h.id))
        )

        let seenVms = 0
        let hasAnyPrev = false

        resourceResults.forEach((res, hIdx) => {
          if (res.status !== 'fulfilled') return
          const host = hosts[hIdx]
          const items = (res.value.data || []).filter(
            r => (r.type === 'qemu' || r.type === 'lxc') && r.status === 'running'
          )

          items.forEach(vm => {
            seenVms++
            // Use String() to ensure consistent key type regardless of Proxmox response format
            const vmKey = `${host.id}::${vm.node}::${String(vm.vmid ?? vm.id ?? vm.name ?? '')}`
            const nodeKey = `${host.id}::${vm.node}`
            const prev = prevStats[vmKey]

            if (!nodeAgg[nodeKey]) {
              nodeAgg[nodeKey] = {
                key: nodeKey,
                label: vm.node || 'unknown',
                hostName: host.name || host.hostname || '',
                diskRead: 0,
                diskWrite: 0,
              }
            }

            if (prev && (now - prev.time) > 500) {
              hasAnyPrev = true
              const elapsed = (now - prev.time) / 1000
              nodeAgg[nodeKey].diskRead  += Math.max(0, ((vm.diskread  || 0) - prev.read))  / elapsed
              nodeAgg[nodeKey].diskWrite += Math.max(0, ((vm.diskwrite || 0) - prev.write)) / elapsed
            }

            nextStats[vmKey] = { read: vm.diskread || 0, write: vm.diskwrite || 0, time: now }
          })
        })

        // Replace prevStats with only currently-seen VMs to avoid stale keys
        prevStats = nextStats

        // Not enough data yet for a delta — only show "measuring" if no existing data
        if (!hasAnyPrev) {
          if (nodes.value.length === 0) measuring.value = true
          loading.value = false
          return
        }
        measuring.value = false

        const result = Object.values(nodeAgg)
        if (!result.length) { loading.value = false; return }

        let maxRead = 0, maxWrite = 0
        result.forEach(n => {
          if (n.diskRead > maxRead) maxRead = n.diskRead
          if (n.diskWrite > maxWrite) maxWrite = n.diskWrite
        })
        result.forEach(n => { n.maxRead = maxRead || 1; n.maxWrite = maxWrite || 1 })

        nodes.value = result.sort((a, b) => a.label.localeCompare(b.label))
      } catch {
        // silently ignore — keep existing nodes data on error
      } finally {
        loading.value = false
      }
    }

    // Poll every 15s; first real data appears after second poll (~15s) since delta needs two readings
    onMounted(() => { fetchData(); timer = setInterval(fetchData, 15000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, measuring, nodes, fmtBps, barPct }
  }
}
</script>

<style scoped>
.disk-io-widget { height: 100%; overflow: auto; }
.wi-empty { font-size: 0.8rem; color: var(--text-secondary); }

.node-list {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.node-row {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.node-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.4rem;
}

.node-name {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-primary);
}

.node-host {
  font-size: 0.65rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60%;
  text-align: right;
}

.io-bars {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.io-bar-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.io-label {
  font-size: 0.6rem;
  font-weight: 700;
  width: 12px;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.io-read { color: #8b5cf6; }
.io-write { color: #ef4444; }

.io-track {
  flex: 1;
  height: 6px;
  background: var(--border-color, #374151);
  border-radius: 3px;
  overflow: hidden;
}

.io-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.io-fill--read  { background: #8b5cf6; }
.io-fill--write { background: #ef4444; }

.io-val {
  font-size: 0.62rem;
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
  min-width: 56px;
  text-align: right;
  flex-shrink: 0;
}
</style>
