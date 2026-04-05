<template>
  <div class="node-status-grid">
    <div v-if="loading && nodes.length === 0" class="wl">Loading nodes...</div>
    <div v-else-if="nodes.length === 0" class="we">No nodes found.</div>
    <div v-else class="grid">
      <div
        v-for="node in nodes"
        :key="node.key"
        class="node-card"
        :class="statusClass(node)"
        @click="navigate(node)"
        :title="`${node.label} — click to view`"
      >
        <!-- Status indicator dot -->
        <div class="status-dot" :class="`dot-${node.status}`"></div>

        <div class="card-content">
          <div class="card-top">
            <span class="node-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <rect x="2" y="3" width="20" height="14" rx="2"/>
                <line x1="8" y1="21" x2="16" y2="21"/>
                <line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
            </span>
            <span class="node-label">{{ node.label }}</span>
          </div>

          <!-- CPU / RAM bars -->
          <div class="mini-bars" v-if="node.status === 'online'">
            <div class="mini-bar-row">
              <span class="mini-lbl">CPU</span>
              <div class="mini-track">
                <div
                  class="mini-fill"
                  :class="node.cpu > 85 ? 'fill-danger' : node.cpu > 70 ? 'fill-warn' : 'fill-ok'"
                  :style="{ width: node.cpu + '%' }"
                ></div>
              </div>
              <span class="mini-pct">{{ node.cpu }}%</span>
            </div>
            <div class="mini-bar-row">
              <span class="mini-lbl">RAM</span>
              <div class="mini-track">
                <div
                  class="mini-fill"
                  :class="node.ram > 85 ? 'fill-danger' : node.ram > 70 ? 'fill-warn' : 'fill-ok'"
                  :style="{ width: node.ram + '%' }"
                ></div>
              </div>
              <span class="mini-pct">{{ node.ram }}%</span>
            </div>
          </div>

          <div class="card-footer">
            <span class="status-badge" :class="`badge-${node.status}`">{{ node.status }}</span>
            <span class="uplink-badge" v-if="node.uplink" title="Uplink">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/>
                <path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><circle cx="12" cy="20" r="1" fill="currentColor"/>
              </svg>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

export default {
  name: 'NodeStatusGrid',
  setup () {
    const router = useRouter()
    const loading = ref(true)
    const nodes = ref([])
    let timer = null

    const statusClass = (node) => `card-${node.status}`

    const navigate = (node) => {
      router.push(`/proxmox/${node.hostId}/nodes/${node.nodeName}`)
    }

    const fetch = async () => {
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = (hostsRes.data || []).filter(h => h.is_active)
        if (!hosts.length) { loading.value = false; return }

        const results = await Promise.allSettled(
          hosts.map(h => api.pveNode.clusterResources(h.id))
        )

        const acc = []
        results.forEach((result, hIdx) => {
          if (result.status !== 'fulfilled') return
          const host = hosts[hIdx]
          ;(result.value.data || []).forEach(item => {
            if (item.type !== 'node') return
            const memPct = item.maxmem > 0
              ? Math.round((item.mem / item.maxmem) * 100)
              : 0
            const cpuPct = Math.round((item.cpu || 0) * 100)
            acc.push({
              key:      `${host.id}::${item.node}`,
              label:    item.node,
              nodeName: item.node,
              hostId:   host.id,
              status:   item.status === 'online' ? 'online' : 'offline',
              cpu:      cpuPct,
              ram:      memPct,
              uplink:   true, // node is reachable via Proxmox API = uplink up
            })
          })
        })
        nodes.value = acc
      } catch (e) {
        // silently ignore
      } finally {
        loading.value = false
      }
    }

    onMounted(() => { fetch(); timer = setInterval(fetch, 30000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, nodes, statusClass, navigate }
  }
}
</script>

<style scoped>
.node-status-grid { height: 100%; }
.wl, .we { font-size: 0.8rem; color: var(--text-secondary); }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.5rem;
}

.node-card {
  position: relative;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.6rem 0.55rem 0.5rem;
  cursor: pointer;
  transition: all 0.15s;
  overflow: hidden;
}

.node-card:hover {
  border-color: var(--primary-color);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.card-online  { border-left: 3px solid #22c55e; }
.card-offline { border-left: 3px solid #ef4444; opacity: 0.7; }
.card-maintenance { border-left: 3px solid #f59e0b; }

/* Top-right status dot */
.status-dot {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
}

.dot-online  { background: #22c55e; box-shadow: 0 0 4px rgba(34, 197, 94, 0.6); }
.dot-offline { background: #ef4444; }
.dot-maintenance { background: #f59e0b; }

.card-content {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  min-width: 0;
}

.node-icon {
  color: var(--text-secondary);
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.node-label {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Mini bars */
.mini-bars {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.mini-bar-row {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.mini-lbl {
  font-size: 0.6rem;
  color: var(--text-secondary);
  width: 1.8rem;
  flex-shrink: 0;
}

.mini-track {
  flex: 1;
  height: 0.3rem;
  background: var(--border-color);
  border-radius: 9999px;
  overflow: hidden;
}

.mini-fill {
  height: 100%;
  border-radius: 9999px;
  transition: width 0.3s;
}

.fill-ok     { background: linear-gradient(90deg, var(--primary-color), #22c55e); }
.fill-warn   { background: #f59e0b; }
.fill-danger { background: #ef4444; }

.mini-pct {
  font-size: 0.6rem;
  color: var(--text-secondary);
  width: 1.8rem;
  text-align: right;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

/* Footer */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.25rem;
}

.status-badge {
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.1rem 0.3rem;
  border-radius: 9999px;
  letter-spacing: 0.03em;
}

.badge-online  { background: rgba(34, 197, 94, 0.12); color: #22c55e; }
.badge-offline { background: rgba(239, 68, 68, 0.12); color: #ef4444; }
.badge-maintenance { background: rgba(245, 158, 11, 0.12); color: #f59e0b; }

.uplink-badge {
  color: #22c55e;
  display: flex;
  align-items: center;
}
</style>
