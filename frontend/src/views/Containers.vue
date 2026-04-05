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
        <router-link to="/create-lxc" class="btn btn-primary btn-sm">+ Create LXC</router-link>
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

        <!-- Host filter -->
        <div class="filter-group" v-if="hosts.length > 1">
          <select v-model="hostFilter" class="form-input filter-select">
            <option value="all">All Hosts</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
          </select>
        </div>

        <!-- Node filter -->
        <div class="filter-group" v-if="uniqueNodes.length > 1">
          <select v-model="nodeFilter" class="form-input filter-select">
            <option value="all">All Nodes</option>
            <option v-for="n in uniqueNodes" :key="n" :value="n">{{ n }}</option>
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

    <!-- Bulk Actions Bar -->
    <div v-if="selectedIds.size > 0" class="bulk-bar card mb-2">
      <span class="bulk-count">{{ selectedIds.size }} selected</span>
      <div class="flex gap-1">
        <button @click="bulkAction('start')" class="btn btn-success btn-sm" :disabled="bulkActioning">Start</button>
        <button @click="bulkAction('stop')" class="btn btn-outline btn-sm" :disabled="bulkActioning">Stop</button>
        <button @click="bulkAction('reboot')" class="btn btn-outline btn-sm" :disabled="bulkActioning">Reboot</button>
        <button @click="selectedIds.clear()" class="btn btn-outline btn-sm">Clear</button>
      </div>
    </div>

    <!-- Loading spinner -->
    <div v-if="loading && containers.length === 0" class="loading-spinner"></div>

    <!-- Empty state: no containers at all -->
    <div v-else-if="!loading && containers.length === 0" class="card empty-state">
      <div class="empty-icon-wrap">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
      </div>
      <h4 class="empty-title">No containers found</h4>
      <p class="empty-subtitle">Make sure your Proxmox hosts are configured and reachable, then create an LXC container.</p>
      <router-link to="/create-lxc" class="btn btn-primary">+ Create LXC</router-link>
    </div>

    <!-- Empty state: filters match nothing -->
    <div v-else-if="!loading && sortedContainers.length === 0" class="card empty-state">
      <div class="empty-icon-wrap">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      </div>
      <h4 class="empty-title">No containers match your filters</h4>
      <p class="empty-subtitle">Try adjusting the search query, status or node filters.</p>
    </div>

    <!-- Table -->
    <div v-else class="card">
      <div class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th style="width:36px;">
                <input type="checkbox" @change="toggleSelectAll" :checked="allSelected" :indeterminate="someSelected" />
              </th>
              <th @click="toggleSort('vmid')" class="sortable-col">
                CT ID <span class="sort-icon">{{ sortIcon('vmid') }}</span>
              </th>
              <th @click="toggleSort('name')" class="sortable-col">
                Hostname <span class="sort-icon">{{ sortIcon('name') }}</span>
              </th>
              <th @click="toggleSort('status')" class="sortable-col">
                Status <span class="sort-icon">{{ sortIcon('status') }}</span>
              </th>
              <th @click="toggleSort('_node')" class="sortable-col">
                Node <span class="sort-icon">{{ sortIcon('_node') }}</span>
              </th>
              <th class="text-sm">Host</th>
              <th @click="toggleSort('cpu')" class="sortable-col">
                CPU% <span class="sort-icon">{{ sortIcon('cpu') }}</span>
              </th>
              <th @click="toggleSort('mem')" class="sortable-col">
                Memory <span class="sort-icon">{{ sortIcon('mem') }}</span>
              </th>
              <th class="text-sm">Tags</th>
              <th class="text-sm">IP Address</th>
              <th @click="toggleSort('uptime')" class="sortable-col">
                Uptime <span class="sort-icon">{{ sortIcon('uptime') }}</span>
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="sortedContainers.length === 0">
              <td colspan="12" class="text-muted text-center empty-row">
                <template v-if="containers.length === 0">
                  No containers found. Make sure your Proxmox hosts are configured and reachable.
                </template>
                <template v-else>
                  No containers match the current filters.
                </template>
              </td>
            </tr>
            <tr
              v-for="ct in sortedContainers"
              :key="`${ct._hostId}-${ct._node}-${ct.vmid}`"
              :class="{ 'row-running': ct.status === 'running', 'row-stopped': ct.status === 'stopped', 'row-selected': selectedIds.has(ctKey(ct)) }"
            >
              <!-- Checkbox -->
              <td>
                <input type="checkbox"
                  :checked="selectedIds.has(ctKey(ct))"
                  @change="toggleSelect(ct)"
                />
              </td>

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

              <!-- Tags -->
              <td>
                <div v-if="ct.tags" class="tags-row">
                  <span v-for="tag in parseTags(ct.tags)" :key="tag" class="tag-pill">{{ tag }}</span>
                </div>
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
import { ref, computed, onMounted, onUnmounted, reactive } from 'vue'
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
    const bulkActioning = ref(false)

    // Filters
    const searchQuery = ref('')
    const statusFilter = ref('all')
    const hostFilter = ref('all')
    const nodeFilter = ref('all')

    // Selection
    const selectedIds = reactive(new Set())

    // Sort
    const sortKey = ref('vmid')
    const sortDir = ref('asc')

    // Auto-refresh
    const countdown = ref(REFRESH_SECS)
    let refreshTimer = null
    let tickTimer = null

    // ── Helpers ──────────────────────────────────────────────────────────────

    const ctKey = (ct) => `${ct._hostId}:${ct._node}:${ct.vmid}`

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

    function extractIp(ct) {
      if (ct.ip) return ct.ip
      if (ct.ipconfig0) {
        const m = ct.ipconfig0.match(/ip=([^,/]+)/)
        if (m) return m[1]
      }
      return null
    }

    function parseTags(tags) {
      if (!tags) return []
      return tags.split(';').map(t => t.trim()).filter(Boolean)
    }

    // ── Sort helpers ──────────────────────────────────────────────────────────

    const toggleSort = (key) => {
      if (sortKey.value === key) {
        sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
      } else {
        sortKey.value = key
        sortDir.value = 'asc'
      }
    }

    const sortIcon = (key) => {
      if (sortKey.value !== key) return '↕'
      return sortDir.value === 'asc' ? '↑' : '↓'
    }

    // ── Data loading ─────────────────────────────────────────────────────────

    const loadAll = async (manual = false) => {
      if (manual) countdown.value = REFRESH_SECS
      loading.value = true
      try {
        const hostsRes = await api.proxmox.listHosts()
        hosts.value = hostsRes.data || []

        const allCts = await Promise.all(
          hosts.value.map(async (host) => {
            try {
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

    // ── Computed: unique nodes ────────────────────────────────────────────────

    const uniqueNodes = computed(() => {
      const nodes = new Set(containers.value.map(ct => ct._node).filter(Boolean))
      return [...nodes].sort()
    })

    // ── Filtered view ─────────────────────────────────────────────────────────

    const filteredContainers = computed(() => {
      const q = searchQuery.value.trim().toLowerCase()
      return containers.value.filter(ct => {
        if (hostFilter.value !== 'all' && ct._hostId !== hostFilter.value) return false
        if (nodeFilter.value !== 'all' && ct._node !== nodeFilter.value) return false
        if (statusFilter.value !== 'all' && ct.status !== statusFilter.value) return false
        if (q) {
          const name = (ct.name || '').toLowerCase()
          const vmid = String(ct.vmid)
          if (!name.includes(q) && !vmid.includes(q)) return false
        }
        return true
      })
    })

    const sortedContainers = computed(() => {
      const list = [...filteredContainers.value]
      list.sort((a, b) => {
        let aVal = a[sortKey.value]
        let bVal = b[sortKey.value]
        if (aVal == null) aVal = ''
        if (bVal == null) bVal = ''
        if (typeof aVal === 'string') aVal = aVal.toLowerCase()
        if (typeof bVal === 'string') bVal = bVal.toLowerCase()
        if (aVal < bVal) return sortDir.value === 'asc' ? -1 : 1
        if (aVal > bVal) return sortDir.value === 'asc' ? 1 : -1
        return 0
      })
      return list
    })

    const runningCount = computed(() =>
      containers.value.filter(c => c.status === 'running').length
    )

    // ── Selection ─────────────────────────────────────────────────────────────

    const allSelected = computed(() =>
      sortedContainers.value.length > 0 && sortedContainers.value.every(ct => selectedIds.has(ctKey(ct)))
    )

    const someSelected = computed(() =>
      sortedContainers.value.some(ct => selectedIds.has(ctKey(ct))) && !allSelected.value
    )

    const toggleSelect = (ct) => {
      const k = ctKey(ct)
      if (selectedIds.has(k)) selectedIds.delete(k)
      else selectedIds.add(k)
    }

    const toggleSelectAll = () => {
      if (allSelected.value) {
        sortedContainers.value.forEach(ct => selectedIds.delete(ctKey(ct)))
      } else {
        sortedContainers.value.forEach(ct => selectedIds.add(ctKey(ct)))
      }
    }

    // ── Bulk Actions ──────────────────────────────────────────────────────────

    const bulkAction = async (action) => {
      const targets = sortedContainers.value.filter(ct => selectedIds.has(ctKey(ct)))
      if (!targets.length) return
      if (!confirm(`${action} ${targets.length} container(s)?`)) return
      bulkActioning.value = true
      const results = await Promise.allSettled(
        targets.map(ct =>
          api.pveNode.ctAction(ct._hostId, ct._node, ct.vmid, action)
        )
      )
      const failed = results.filter(r => r.status === 'rejected').length
      if (failed) toast.error(`${failed} action(s) failed`)
      else toast.success(`${action} sent to ${targets.length} container(s)`)
      bulkActioning.value = false
      selectedIds.clear()
      setTimeout(() => loadAll(), 3000)
    }

    // ── Single actions ────────────────────────────────────────────────────────

    const ctAction = async (ct, action) => {
      ct._actioning = true
      ct._pendingAction = action
      try {
        await api.pveNode.ctAction(ct._hostId, ct._node, ct.vmid, action)
        toast.success(`Container ${ct.name || ct.vmid}: ${action} initiated`)
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
      nodeFilter,
      uniqueNodes,
      countdown,
      filteredContainers,
      sortedContainers,
      runningCount,
      selectedIds,
      allSelected,
      someSelected,
      bulkActioning,
      sortKey,
      sortDir,
      formatBytes,
      formatUptime,
      statusBadgeClass,
      barClass,
      parseTags,
      loadAll,
      ctAction,
      openShell,
      openDetail,
      ctKey,
      toggleSelect,
      toggleSelectAll,
      bulkAction,
      toggleSort,
      sortIcon,
    }
  }
}
</script>

<style scoped>
.containers-page { padding: 0; }

/* ── Page header ─────────────────────────────────────────────────────────── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 0.75rem;
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
  flex-wrap: wrap;
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

.filter-input { width: 220px; }
.filter-select { width: 150px; }

.filter-summary { margin-left: auto; }

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

/* ── Bulk bar ────────────────────────────────────────────────────────────── */
.bulk-bar {
  padding: 0.6rem 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  background: var(--bg-secondary);
}

.bulk-count {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--primary-color);
}

/* ── Table ───────────────────────────────────────────────────────────────── */
.table-container { overflow-x: auto; }

.empty-row { padding: 2rem 1rem; }

.vmid-cell { white-space: nowrap; }
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

.sortable-col {
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}
.sortable-col:hover { color: var(--primary-color); }
.sort-icon { font-size: 0.75rem; color: var(--text-muted); margin-left: 0.2rem; }

/* ── Tags ────────────────────────────────────────────────────────────────── */
.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.tag-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.1em 0.5em;
  font-size: 0.7rem;
  font-weight: 500;
  border-radius: 9999px;
  background: var(--primary-color, #3b82f6);
  color: white;
  white-space: nowrap;
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
.stat-cell { min-width: 140px; }

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
.row-running td:first-child { border-left: 3px solid #22c55e; }
.row-stopped td:first-child { border-left: 3px solid var(--border-color); }
.row-selected { background: rgba(59, 130, 246, 0.06); }

/* ── Utility ─────────────────────────────────────────────────────────────── */
.mb-2     { margin-bottom: 1rem; }
.text-sm  { font-size: 0.875rem; }
.text-muted { color: var(--text-muted); }
.text-center { text-align: center; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.875rem; }

/* ── Empty state ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3.5rem 1.5rem;
  text-align: center;
}

.empty-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--background);
  border: 2px dashed var(--border-color);
  color: var(--text-muted);
}

.empty-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.empty-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
  max-width: 400px;
}
</style>
