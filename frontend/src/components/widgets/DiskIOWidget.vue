<template>
  <div class="disk-io">
    <div v-if="loading && nodes.length === 0" class="wl">Loading disk I/O...</div>
    <div v-else-if="nodes.length === 0" class="we">No node data available.</div>
    <div v-else class="node-list">
      <div v-for="node in nodes" :key="node.key" class="node-row">
        <div class="node-header">
          <span class="node-name">{{ node.label }}</span>
          <div class="node-io">
            <span class="io-read">R {{ fmtBps(node.diskread) }}</span>
            <span class="io-write">W {{ fmtBps(node.diskwrite) }}</span>
          </div>
        </div>

        <!-- Bar chart: last N samples as horizontal bars -->
        <div class="bar-chart">
          <svg :viewBox="`0 0 200 ${barH}`" preserveAspectRatio="none" class="bar-svg">
            <!-- Read bars (blue) -->
            <rect
              v-for="(v, i) in node.histRead"
              :key="'r'+i"
              :x="barX(i)"
              :y="barY(v, node.maxVal)"
              :width="barW - 1"
              :height="barHeight(v, node.maxVal)"
              fill="var(--primary-color)"
              opacity="0.75"
              rx="1"
            />
            <!-- Write bars (amber) -->
            <rect
              v-for="(v, i) in node.histWrite"
              :key="'w'+i"
              :x="barX(i) + barW / 2"
              :y="barY(v, node.maxVal)"
              :width="barW / 2 - 1"
              :height="barHeight(v, node.maxVal)"
              fill="#f59e0b"
              opacity="0.75"
              rx="1"
            />
          </svg>
        </div>

        <div class="chart-legend">
          <span class="leg-read">Read</span>
          <span class="leg-write">Write</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

const HISTORY_LEN = 16
const BAR_H = 44

function fmtBps (bps) {
  if (!bps || bps === 0) return '0 B/s'
  if (bps >= 1e9) return (bps / 1e9).toFixed(1) + ' GB/s'
  if (bps >= 1e6) return (bps / 1e6).toFixed(1) + ' MB/s'
  if (bps >= 1e3) return (bps / 1e3).toFixed(0) + ' KB/s'
  return Math.round(bps) + ' B/s'
}

export default {
  name: 'DiskIOWidget',
  setup () {
    const loading = ref(true)
    const nodesMap = ref({})
    const nodes = ref([])
    let timer = null

    const barW = 200 / HISTORY_LEN
    const barH = BAR_H

    const barX  = (i) => i * barW
    const barY  = (v, max) => max > 0 ? (BAR_H - (v / max) * (BAR_H - 4) - 2) : BAR_H - 2
    const barHeight = (v, max) => max > 0 ? Math.max(2, (v / max) * (BAR_H - 4)) : 2

    const pushHistory = (arr, val) => {
      arr.push(val)
      if (arr.length > HISTORY_LEN) arr.shift()
    }

    const fetch = async () => {
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = (hostsRes.data || []).filter(h => h.is_active)
        if (!hosts.length) { loading.value = false; return }

        const results = await Promise.allSettled(
          hosts.map(h => api.pveNode.clusterResources(h.id))
        )

        results.forEach((result, hIdx) => {
          if (result.status !== 'fulfilled') return
          const host = hosts[hIdx]
          ;(result.value.data || []).forEach(item => {
            if (item.type !== 'node') return
            const key = `${host.id}::${item.node}`
            if (!nodesMap.value[key]) {
              nodesMap.value[key] = {
                key,
                label: item.node,
                diskread: 0,
                diskwrite: 0,
                histRead:  Array(HISTORY_LEN).fill(0),
                histWrite: Array(HISTORY_LEN).fill(0),
                maxVal: 1,
              }
            }
            const nd = nodesMap.value[key]
            nd.diskread  = item.diskread  || 0
            nd.diskwrite = item.diskwrite || 0
            pushHistory(nd.histRead,  nd.diskread)
            pushHistory(nd.histWrite, nd.diskwrite)
            nd.maxVal = Math.max(...nd.histRead, ...nd.histWrite, 1)
          })
        })

        nodes.value = Object.values(nodesMap.value)
      } catch (e) {
        // silently ignore
      } finally {
        loading.value = false
      }
    }

    onMounted(() => { fetch(); timer = setInterval(fetch, 10000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, nodes, fmtBps, barW, barH, barX, barY, barHeight }
  }
}
</script>

<style scoped>
.disk-io { height: 100%; }
.wl, .we { font-size: 0.8rem; color: var(--text-secondary); }

.node-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.node-row {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.node-name {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-io {
  display: flex;
  gap: 0.6rem;
  flex-shrink: 0;
}

.io-read {
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--primary-color);
  font-variant-numeric: tabular-nums;
}

.io-write {
  font-size: 0.68rem;
  font-weight: 600;
  color: #f59e0b;
  font-variant-numeric: tabular-nums;
}

.bar-chart {
  width: 100%;
  border-radius: 0.25rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.bar-svg {
  width: 100%;
  height: 44px;
  display: block;
}

.chart-legend {
  display: flex;
  gap: 0.75rem;
}

.leg-read {
  font-size: 0.62rem;
  color: var(--primary-color);
  font-weight: 600;
}

.leg-read::before {
  content: '■';
  margin-right: 0.2rem;
  font-size: 0.5rem;
}

.leg-write {
  font-size: 0.62rem;
  color: #f59e0b;
  font-weight: 600;
}

.leg-write::before {
  content: '■';
  margin-right: 0.2rem;
  font-size: 0.5rem;
}
</style>
