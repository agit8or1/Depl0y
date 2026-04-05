<template>
  <div class="net-traffic">
    <div v-if="loading && nodes.length === 0" class="wl">Loading network data...</div>
    <div v-else-if="nodes.length === 0" class="we">No node data available.</div>
    <div v-else class="node-list">
      <div v-for="node in nodes" :key="node.key" class="node-row">
        <div class="node-header">
          <span class="node-name">{{ node.label }}</span>
          <div class="node-io">
            <span class="io-in">
              <svg width="8" height="8" viewBox="0 0 8 8"><path d="M4 7V1M1 4l3-3 3 3" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
              {{ fmtBps(node.netin) }}
            </span>
            <span class="io-out">
              <svg width="8" height="8" viewBox="0 0 8 8"><path d="M4 1v6M1 4l3 3 3-3" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
              {{ fmtBps(node.netout) }}
            </span>
          </div>
        </div>

        <!-- Sparkline SVG -->
        <svg class="sparkline" viewBox="0 0 200 40" preserveAspectRatio="none">
          <!-- In (blue) -->
          <path
            v-if="node.histIn.length > 1"
            :d="sparkPath(node.histIn, 200, 40)"
            fill="none"
            stroke="var(--primary-color)"
            stroke-width="1.5"
            stroke-linejoin="round"
            stroke-linecap="round"
            opacity="0.85"
          />
          <!-- Out (green) -->
          <path
            v-if="node.histOut.length > 1"
            :d="sparkPath(node.histOut, 200, 40)"
            fill="none"
            stroke="#10b981"
            stroke-width="1.5"
            stroke-linejoin="round"
            stroke-linecap="round"
            opacity="0.85"
          />
          <!-- Area fill In -->
          <path
            v-if="node.histIn.length > 1"
            :d="sparkArea(node.histIn, 200, 40)"
            fill="var(--primary-color)"
            opacity="0.08"
          />
        </svg>

        <div class="spark-legend">
          <span class="leg-in">In</span>
          <span class="leg-out">Out</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

const HISTORY_LEN = 20

function fmtBps (bps) {
  if (!bps || bps === 0) return '0 B/s'
  if (bps >= 1e9) return (bps / 1e9).toFixed(1) + ' GB/s'
  if (bps >= 1e6) return (bps / 1e6).toFixed(1) + ' MB/s'
  if (bps >= 1e3) return (bps / 1e3).toFixed(0) + ' KB/s'
  return Math.round(bps) + ' B/s'
}

function sparkPath (data, W, H) {
  const max = Math.max(...data, 1)
  const step = W / (data.length - 1)
  return data.map((v, i) => {
    const x = i * step
    const y = H - (v / max) * (H - 4) - 2
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

function sparkArea (data, W, H) {
  const path = sparkPath(data, W, H)
  const lastX = (W).toFixed(1)
  return `${path} L${lastX},${H} L0,${H} Z`
}

export default {
  name: 'NetworkTrafficWidget',
  setup () {
    const loading = ref(true)
    // Map: key -> { key, label, netin, netout, histIn[], histOut[] }
    const nodesMap = ref({})
    const nodes = ref([])
    let timer = null

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
                netin: 0,
                netout: 0,
                histIn: Array(HISTORY_LEN).fill(0),
                histOut: Array(HISTORY_LEN).fill(0),
              }
            }
            const nd = nodesMap.value[key]
            nd.netin  = item.netin  || 0
            nd.netout = item.netout || 0
            pushHistory(nd.histIn,  nd.netin)
            pushHistory(nd.histOut, nd.netout)
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

    return { loading, nodes, fmtBps, sparkPath, sparkArea }
  }
}
</script>

<style scoped>
.net-traffic { height: 100%; }
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

.io-in {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--primary-color);
  font-variant-numeric: tabular-nums;
}

.io-out {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.68rem;
  font-weight: 600;
  color: #10b981;
  font-variant-numeric: tabular-nums;
}

.sparkline {
  width: 100%;
  height: 40px;
  display: block;
  border-radius: 0.25rem;
  background: var(--background);
  border: 1px solid var(--border-color);
}

.spark-legend {
  display: flex;
  gap: 0.75rem;
}

.leg-in {
  font-size: 0.62rem;
  color: var(--primary-color);
  font-weight: 600;
}

.leg-in::before {
  content: '—';
  margin-right: 0.2rem;
}

.leg-out {
  font-size: 0.62rem;
  color: #10b981;
  font-weight: 600;
}

.leg-out::before {
  content: '—';
  margin-right: 0.2rem;
}
</style>
