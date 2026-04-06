<template>
  <div class="disk-io">
    <div v-if="loading && nodes.length === 0" class="wl">Loading disk usage...</div>
    <div v-else-if="nodes.length === 0" class="we">No node data available.</div>
    <div v-else class="node-list">
      <div v-for="node in nodes" :key="node.key" class="node-row">
        <div class="node-header">
          <span class="node-name">{{ node.label }}</span>
          <div class="node-io">
            <span class="io-read">{{ fmtGB(node.diskUsed) }}</span>
            <span class="io-write">/ {{ fmtGB(node.diskTotal) }}</span>
          </div>
        </div>

        <!-- Usage bar -->
        <div class="usage-track">
          <div
            class="usage-fill"
            :style="{ width: usagePct(node) + '%' }"
            :class="usagePct(node) > 85 ? 'fill-red' : usagePct(node) > 65 ? 'fill-amber' : 'fill-blue'"
          ></div>
        </div>

        <div class="chart-legend">
          <span class="leg-read">Used</span>
          <span :class="usagePct(node) > 85 ? 'leg-warn' : 'leg-write'">{{ usagePct(node).toFixed(1) }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

function fmtGB (bytes) {
  if (!bytes) return '0 GB'
  const gb = bytes / (1024 ** 3)
  if (gb >= 1000) return (gb / 1024).toFixed(1) + ' TB'
  return gb.toFixed(1) + ' GB'
}

export default {
  name: 'DiskIOWidget',
  setup () {
    const loading = ref(true)
    const nodes = ref([])
    let timer = null

    const barH = 44
    const barW = 0 // unused but keep for compat

    const usagePct = (node) => {
      if (!node.diskTotal || node.diskTotal === 0) return 0
      return Math.min(100, (node.diskUsed / node.diskTotal) * 100)
    }

    const fetch = async () => {
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = (hostsRes.data || []).filter(h => h.is_active)
        if (!hosts.length) { loading.value = false; return }

        const nodeListResults = await Promise.allSettled(
          hosts.map(h => api.proxmox.listNodes(h.id))
        )

        const result = []
        nodeListResults.forEach((res) => {
          if (res.status !== 'fulfilled') return
          ;(res.value.data || []).forEach(n => {
            const name = n.node_name || n.node
            if (!name) return
            result.push({
              key: `${n.host_id}::${name}`,
              label: name,
              diskUsed: n.disk_used || 0,
              diskTotal: n.disk_total || 0,
            })
          })
        })

        nodes.value = result
      } catch (e) {
        // silently ignore
      } finally {
        loading.value = false
      }
    }

    onMounted(() => { fetch(); timer = setInterval(fetch, 30000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, nodes, fmtGB, usagePct, barH, barW }
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
  gap: 0.25rem;
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
  font-weight: 400;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.usage-track {
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: var(--border-color);
  overflow: hidden;
}

.usage-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.fill-blue  { background: var(--primary-color); }
.fill-amber { background: #f59e0b; }
.fill-red   { background: #ef4444; }

.chart-legend {
  display: flex;
  justify-content: space-between;
}

.leg-read {
  font-size: 0.62rem;
  color: var(--primary-color);
  font-weight: 600;
}

.leg-write {
  font-size: 0.62rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.leg-warn {
  font-size: 0.62rem;
  color: #ef4444;
  font-weight: 600;
}
</style>
