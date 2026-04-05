<template>
  <div class="containers-page">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2>LXC Containers</h2>
        <p class="text-muted">All LXC containers across configured Proxmox hosts</p>
      </div>
      <div class="header-actions">
        <span class="refresh-countdown" v-if="!loading">Auto-refresh in {{ countdown }}s</span>
        <button @click="loadAll(true)" class="btn btn-outline btn-sm" :disabled="loading">
          {{ loading ? 'Refreshing…' : 'Refresh' }}
        </button>
      </div>
    </div>

    <!-- Filters Bar -->
    <div class="filters-bar card mb-2">
      <div class="filters-inner">
        <!-- Search -->
        <div class="filter-group">
          <input
            v-model="searchQuery"
            type="text"
            class="form-input filter-input"
            placeholder="Search by name or CT ID…"
          />
        </div>

        <!-- Status filter -->
        <div class="filter-group">
          <select v-model="statusFilter" class="form-input filter-select">
            <option value="all">All Statuses</option>
            <option value="running">Running</option>
            <option value="stopped">Stopped</option>
            <option value="paused">Paused</option>
          </select>
        </div>

        <!-- Host filter (shown when >1 host) -->
        <div class="filter-group" v-if="hosts.length > 1">
          <select v-model="hostFilter" class="form-input filter-select">
            <option value="all">All Hosts</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
          </select>
        </div>

        <!-- Count summary -->
        <div class="filter-summary">
          <span class="count-badge">
            {{ filteredContainers.length }} container{{ filteredContainers.length !== 1 ? 's' : '' }}
            <span class="count-running">({{ runningCount }} running)</span>
          </span>
        </div>
      </div>
    </div>

    <!-- Loading spinner -->
    <div v-if="loading && containers.length === 0" class="loading-spinner"></div>

    <!-- Table -->
    <div v-else class="card">
      <div class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>CT ID</th>
              <th>Hostname</th>
              <th>Status</th>
              <th>Node</th>
              <th>Host</th>
              <th>CPU%</th>
              <th>Memory</th>
              <th>IP Address</th>
              <th>Uptime</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="filteredContainers.length === 0">
              <td colspan="10" class="text-muted text-center empty-row">
                <template v-if="containers.length === 0">
                  No containers found. Make sure your Proxmox hosts are configured and reachable.
                </template>
                <template v-else>
                  No containers match the current filters.
                </template>
              </td>
            </tr>
            <tr
              v-for="ct in filteredContainers"
              :key="`${ct._hostId}-${ct._node}-${ct.vmid}`"
              :class="{ 'row-running': ct.status === 'running', 'row-stopped': ct.status === 'stopped' }"
            >
              <!-- CT ID -->
              <td class="vmid-cell">
                <span class="vmid-label">{{ ct.vmid }}</span>
              </td>

              <!-- Hostname -->
              <td>
                <span class="clickable-name" @click="openDetail(ct)">
                  {{ ct.name || `CT ${ct.vmid}` }}
                </span>
              </td>

              <!-- Status badge -->
              <td>
                <span :class="statusBadgeClass(ct.status)">{{ ct.status }}</span>
              </td>

              <!-- Node -->
              <td class="text-sm">{{ ct._node }}</td>

              <!-- Host -->
              <td class="text-sm">{{ ct._hostName }}</td>

              <!-- CPU% with inline bar -->
              <td class="stat-cell">
                <template v-if="ct.status === 'running' && ct.cpu != null">
                  <div class="stat-bar-wrap">
                    <div class="stat-bar">
                      <div
                        class="stat-bar-fill"
                        :class="barClass(ct.cpu * 100)"
                        :style="{ width: Math.min(ct.cpu * 100, 100).toFixed(1) + '%' }"
                      ></div>
                    </div>
                    <span class="stat-bar-label">{{ (ct.cpu * 100).toFixed(1) }}%</span>
                  </div>
                </template>
                <span v-else class="text-muted">—</span>
              </td>

              <!-- Memory with inline bar -->
              <td class="stat-cell">
                <template v-if="ct.maxmem">
                  <div class="stat-bar-wrap">
                    <div class="stat-bar">
                      <div
                        class="stat-bar-fill"
                        :class="barClass((ct.mem / ct.maxmem) * 100)"
                        :style="{ width: Math.min((ct.mem / ct.maxmem) * 100, 100).toFixed(1) + '%' }"
                      ></div>
                    </div>
                    <span class="stat-bar-label">
                      {{ formatBytes(ct.mem) }} / {{ formatBytes(ct.maxmem) }}
                    </span>
                  </div>
                </template>
                <span v-else class="text-muted">—</span>
              </td>

              <!-- IP Address -->
              <td class="text-sm ip-cell">
                <span v-if="ct._ip">{{ ct._ip }}</span>
                <span v-else class="text-muted">—</span>
              </td>

              <!-- Uptime -->
              <td class="text-sm">
                <template v-if="ct.status === 'running' && ct.uptime">
                  {{ formatUptime(ct.uptime) }}
                </template>
                <span v-else class="text-muted">—</span>
              </td>

              <!-- Actions -->
              <td>
                <div class="action-btns">
                  <button
                    v-if="ct.status !== 'running'"
                    @click="ctAction(ct, 'start')"
                    class="btn btn-success btn-xs"
                    :disabled="ct._actioning"
                    title="Start"
                  >
                    <span v-if="ct._actioning && ct._pendingAction === 'start'">…</span>
                    <span v-else>Start</span>
                  </button>
                  <button
                    v-if="ct.status === 'running'"
                    @click="ctAction(ct, 'stop')"
                    class="btn btn-danger btn-xs"
                    :disabled="ct._actioning"
                    title="Stop"
                  >
                    <span v-if="ct._actioning && ct._pendingAction === 'stop'">…</span>
                    <span v-else>Stop</span>
                  </button>
                  <button
                    @click="openDetail(ct)"
                    class="btn btn-outline btn-xs"
                    title="Details"
                  >
                    Details
                  </button>
                  <button
                    v-if="ct.status === 'running'"
                    @click="openShell(ct)"
                    class="btn btn-outline btn-xs"
                    title="Shell"
                  >
                    Shell
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import { formatBytes, formatUptime } from '@/utils/proxmox'

const REFRESH_SECS = 30

export default {
  name: 'Containers',
  setup() {
    const toast = useToast()
    const router = useRouter()

    const containers = ref([])
    const hosts = ref([])
    const loading = ref(true)

    // Filters
    const searchQuery = ref('')
    const statusFilter = ref('all')
    const hostFilter = ref('all')

    // Auto-refresh
    const countdown = ref(REFRESH_SECS)
    let refreshTimer = null
    let tickTimer = null

    // ── Helpers ──────────────────────────────────────────────────────────────

    function statusBadgeClass(status) {
      if (status === 'running') return 'badge badge-success'
      if (status === 'paused')  return 'badge badge-warning'
      return 'badge badge-secondary'
    }

    function barClass(pct) {
      if (pct >= 80) return 'bar-danger'
      if (pct >= 60) return 'bar-warning'
      return 'bar-success'
    }

    // Extract IP from Proxmox resource data.
    // The cluster resources endpoint may include 'ip' or we can parse 'netin'
    // fields; the most reliable field Proxmox exposes is `ip` on running CTs.
    function extractIp(ct) {
      if (ct.ip) return ct.ip
      // Some Proxmox versions expose the first interface IP directly
      if (ct.ipconfig0) {
        const m = ct.ipconfig0.match(/ip=([^,/]+)/)
        if (m) return m[1]
      }
      return null
    }

    // ── Data loading ─────────────────────────────────────────────────────────

    const loadAll = async (manual = false) => {
      if (manual) {
        countdown.value = REFRESH_SECS
      }
      loading.value = true
      try {
        const hostsRes = await api.proxmox.listHosts()
        hosts.value = hostsRes.data || []

        const allCts = await Promise.all(
          hosts.value.map(async (host) => {
            try {
              // Use clusterResources for lxc — returns all CTs across all nodes
              // with live cpu/mem/uptime fields in one call.
              const res = await api.pveNode.clusterResources(host.id, 'lxc')
              const items = res.data || []
              return items.map(ct => ({
                ...ct,
                _hostId: host.id,
                _hostName: host.name,
                _node: ct.node || ct._node || '',
                _ip: extractIp(ct),
                _actioning: false,
                _pendingAction: null,
              }))
            } catch {
              return []
            }
          })
        )

        containers.value = allCts.flat().sort((a, b) => a.vmid - b.vmid)
      } catch (e) {
        console.error('Failed to load containers', e)
        toast.error('Failed to load containers')
      } finally {
        loading.value = false
      }
    }

    // ── Filtered view ─────────────────────────────────────────────────────────

    const filteredContainers = computed(() => {
      const q = searchQuery.value.trim().toLowerCase()
      return containers.value.filter(ct => {
        // Host filter
        if (hostFilter.value !== 'all' && ct._hostId !== hostFilter.value) return false
        // Status filter
        if (statusFilter.value !== 'all' && ct.status !== statusFilter.value) return false
        // Search (name or vmid)
        if (q) {
          const name = (ct.name || '').toLowerCase()
          const vmid = String(ct.vmid)
          if (!name.includes(q) && !vmid.includes(q)) return false
        }
        return true
      })
    })

    const runningCount = computed(() =>
      containers.value.filter(c => c.status === 'running').length
    )

    // ── Actions ───────────────────────────────────────────────────────────────

    const ctAction = async (ct, action) => {
      ct._actioning = true
      ct._pendingAction = action
      try {
        await api.pveNode.ctAction(ct._hostId, ct._node, ct.vmid, action)
        toast.success(`Container ${ct.name || ct.vmid}: ${action} initiated`)
        // Reload after a short delay to pick up new status
        setTimeout(() => loadAll(), 3000)
      } catch (e) {
        console.error(e)
      } finally {
        ct._actioning = false
        ct._pendingAction = null
      }
    }

    const openShell = (ct) => {
      const route = router.resolve({
        name: 'ContainerTerminal',
        params: { hostId: ct._hostId, node: ct._node, vmid: ct.vmid },
      })
      window.open(route.href, '_blank')
    }

    const openDetail = (ct) => {
      router.push({
        name: 'LxcContainerDetail',
        params: { hostId: ct._hostId, node: ct._node, vmid: ct.vmid },
      })
    }

    // ── Auto-refresh ─────────────────────────────────────────────────────────

    const startTimers = () => {
      clearInterval(refreshTimer)
      clearInterval(tickTimer)
      countdown.value = REFRESH_SECS

      refreshTimer = setInterval(() => {
        if (document.visibilityState === 'hidden') return
        loadAll()
        countdown.value = REFRESH_SECS
      }, REFRESH_SECS * 1000)

      tickTimer = setInterval(() => {
        if (document.visibilityState === 'hidden') return
        if (countdown.value > 0) countdown.value--
      }, 1000)
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        loadAll()
        countdown.value = REFRESH_SECS
      }
    }

    onMounted(async () => {
      await loadAll()
      startTimers()
      document.addEventListener('visibilitychange', handleVisibilityChange)
    })

    onUnmounted(() => {
      clearInterval(refreshTimer)
      clearInterval(tickTimer)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    })

    return {
      containers,
      hosts,
      loading,
      searchQuery,
      statusFilter,
      hostFilter,
      countdown,
      filteredContainers,
      runningCount,
      formatBytes,
      formatUptime,
      statusBadgeClass,
      barClass,
      loadAll,
      ctAction,
      openShell,
      openDetail,
    }
  }
}
</script>

<style scoped>
.containers-page {
  padding: 0;
}

/* ── Page header ─────────────────────────────────────────────────────────── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.refresh-countdown {
  font-size: 0.75rem;
  color: var(--text-muted, #64748b);
}

/* ── Filters bar ─────────────────────────────────────────────────────────── */
.filters-bar {
  padding: 0.75rem 1rem;
}

.filters-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.filter-group {
  display: flex;
  align-items: center;
}

.filter-input,
.filter-select {
  height: 2rem;
  padding: 0 0.6rem;
  font-size: 0.85rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background: var(--bg-primary);
  color: var(--text-primary);
  min-width: 0;
}

.filter-input {
  width: 220px;
}

.filter-select {
  width: 150px;
}

.filter-summary {
  margin-left: auto;
}

.count-badge {
  font-size: 0.85rem;
  color: var(--text-primary);
  font-weight: 500;
}

.count-running {
  color: var(--text-muted);
  font-weight: 400;
  margin-left: 0.25rem;
}

/* ── Table ───────────────────────────────────────────────────────────────── */
.table-container {
  overflow-x: auto;
}

.empty-row {
  padding: 2rem 1rem;
}

.vmid-cell {
  white-space: nowrap;
}

.vmid-label {
  font-family: monospace;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.clickable-name {
  cursor: pointer;
  color: var(--primary-color);
  font-weight: 500;
}

.clickable-name:hover {
  text-decoration: underline;
  color: var(--text-primary);
}

.ip-cell {
  font-family: monospace;
  font-size: 0.8rem;
}

/* ── Status badges ───────────────────────────────────────────────────────── */
.badge-secondary {
  display: inline-flex;
  align-items: center;
  padding: 0.2em 0.55em;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 0.3rem;
  background: var(--border-color, #e2e8f0);
  color: var(--text-muted, #64748b);
}

.badge-warning {
  display: inline-flex;
  align-items: center;
  padding: 0.2em 0.55em;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 0.3rem;
  background: #fef3c7;
  color: #92400e;
}

/* ── Inline stat bars ────────────────────────────────────────────────────── */
.stat-cell {
  min-width: 140px;
}

.stat-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.stat-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
  min-width: 50px;
}

.stat-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.bar-success { background-color: #22c55e; }
.bar-warning { background-color: #f59e0b; }
.bar-danger  { background-color: #ef4444; }

.stat-bar-label {
  color: var(--text-primary);
  font-family: monospace;
  font-size: 0.75rem;
  white-space: nowrap;
}

/* ── Action buttons ──────────────────────────────────────────────────────── */
.action-btns {
  display: flex;
  gap: 0.35rem;
  flex-wrap: nowrap;
}

.btn-xs {
  padding: 0.2rem 0.5rem;
  font-size: 0.75rem;
  line-height: 1.4;
}

/* ── Row highlight ───────────────────────────────────────────────────────── */
.row-running td:first-child {
  border-left: 3px solid #22c55e;
}

.row-stopped td:first-child {
  border-left: 3px solid var(--border-color);
}

/* ── Utility ─────────────────────────────────────────────────────────────── */
.mb-2     { margin-bottom: 1rem; }
.text-sm  { font-size: 0.875rem; }
.text-muted { color: var(--text-muted); }
.text-center { text-align: center; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
</style>
