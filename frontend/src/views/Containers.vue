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
        <!-- View Toggle -->
        <div class="view-toggle">
          <button
            @click="viewMode = 'table'"
            :class="['view-btn', viewMode === 'table' ? 'view-btn--active' : '']"
            title="Table view"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="1"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="9" x2="9" y2="21"/></svg>
          </button>
          <button
            @click="viewMode = 'grid'"
            :class="['view-btn', viewMode === 'grid' ? 'view-btn--active' : '']"
            title="Grid view"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
          </button>
        </div>
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

        <!-- Memory filter -->
        <div class="filter-group">
          <select v-model="memFilter" class="form-input filter-select" style="width:130px;">
            <option value="all">Any Memory</option>
            <option value="512">≥ 512 MB</option>
            <option value="1024">≥ 1 GB</option>
            <option value="2048">≥ 2 GB</option>
            <option value="4096">≥ 4 GB</option>
            <option value="8192">≥ 8 GB</option>
          </select>
        </div>

        <!-- Count summary -->
        <div class="filter-summary">
          <span class="count-badge">
            Showing {{ sortedContainers.length }} of {{ containers.length }} container{{ containers.length !== 1 ? 's' : '' }}
            <span
              class="count-running count-running--link"
              role="link"
              tabindex="0"
              :title="statusFilter === 'running' ? 'Clear running filter' : 'Filter to running containers'"
              @click="statusFilter = statusFilter === 'running' ? 'all' : 'running'"
              @keydown.enter="statusFilter = statusFilter === 'running' ? 'all' : 'running'"
              @keydown.space.prevent="statusFilter = statusFilter === 'running' ? 'all' : 'running'"
            >({{ runningCount }} running)</span>
          </span>
        </div>
      </div>
    </div>

    <!-- Bulk Actions Bar -->
    <div v-if="selectedIds.size > 0" class="bulk-bar card mb-2">
      <span class="bulk-count">{{ selectedIds.size }} selected</span>
      <div class="flex gap-1">
        <button @click="bulkAction('start')" class="btn btn-success btn-sm" :disabled="bulkActioning">Start All</button>
        <button @click="bulkAction('stop')" class="btn btn-outline btn-sm" :disabled="bulkActioning">Stop All</button>
        <button @click="bulkAction('reboot')" class="btn btn-outline btn-sm" :disabled="bulkActioning">Reboot All</button>
        <button @click="bulkSnapshot()" class="btn btn-outline btn-sm" :disabled="bulkActioning">Snapshot All</button>
        <button @click="selectedIds.clear()" class="btn btn-outline btn-sm">Clear</button>
      </div>
    </div>

    <!-- Critical error banner -->
    <div v-if="criticalError" class="error-banner mb-2">
      <div class="error-banner__icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      </div>
      <div class="error-banner__body">
        <strong>Failed to load containers</strong>
        <span class="error-banner__msg">{{ criticalError }}</span>
      </div>
      <button @click="loadAll(true)" class="btn btn-outline btn-sm error-banner__retry">Retry</button>
    </div>

    <!-- Partial failure warning (some hosts failed) -->
    <div v-if="failedHosts.length > 0 && !criticalError" class="warning-banner mb-2">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      <span>
        <strong>{{ failedHosts.length }} host{{ failedHosts.length !== 1 ? 's' : '' }} unreachable:</strong>
        {{ failedHosts.join(', ') }} — data shown may be incomplete.
      </span>
    </div>

    <!-- Timeout warning -->
    <div v-if="timeoutWarning" class="warning-banner mb-2">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      <span>Some requests are taking longer than expected. Data may be incomplete.</span>
      <button @click="timeoutWarning = false" class="btn-inline-close">×</button>
    </div>

    <!-- Loading skeleton -->
    <SkeletonLoader v-if="loading && containers.length === 0" type="table" :count="8" />

    <!-- Empty state: no containers at all -->
    <div v-else-if="!loading && !criticalError && containers.length === 0" class="card empty-state">
      <div class="empty-icon-wrap">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
      </div>
      <h4 class="empty-title">No containers found</h4>
      <p class="empty-subtitle">Make sure your Proxmox hosts are configured and reachable, then create an LXC container.</p>
      <router-link to="/create-lxc" class="btn btn-primary">+ Create LXC</router-link>
    </div>

    <!-- Empty state: filters match nothing -->
    <div v-else-if="!loading && sortedContainers.length === 0 && containers.length > 0" class="card empty-state">
      <div class="empty-icon-wrap">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      </div>
      <h4 class="empty-title">No containers match your filters</h4>
      <p class="empty-subtitle">Try adjusting the search query, status or node filters.</p>
      <button @click="clearFilters" class="btn btn-outline">Clear Filters</button>
    </div>

    <!-- Grid View -->
    <div v-if="!loading && sortedContainers.length > 0 && viewMode === 'grid'" class="ct-grid">
      <div
        v-for="ct in sortedContainers"
        :key="`${ct._hostId}-${ct._node}-${ct.vmid}`"
        class="ct-card"
        :class="{ 'ct-card--running': ct.status === 'running', 'ct-card--selected': selectedIds.has(ctKey(ct)) }"
      >
        <div class="ct-card__header">
          <input type="checkbox" :checked="selectedIds.has(ctKey(ct))" @change="toggleSelect(ct)" class="ct-card__check" />
          <span class="ct-card__os">{{ detectOs(ct.name || '').icon }}</span>
          <span class="ct-card__name" @click="openDetail(ct)" :title="ct.name || `CT ${ct.vmid}`">
            {{ ct.name || `CT ${ct.vmid}` }}
          </span>
          <span :class="statusBadgeClass(ct.status)" class="ct-card__badge">{{ ct.status }}</span>
        </div>
        <div class="ct-card__meta">
          <span class="ct-card__vmid">CT{{ ct.vmid }}</span>
          <span class="ct-card__node">{{ ct._node }}</span>
          <span class="ct-card__host">{{ ct._hostName }}</span>
        </div>
        <div class="ct-card__stats">
          <div class="ct-card__stat-row" v-if="ct.cpus">
            <span class="ct-card__stat-label">Cores</span>
            <span class="ct-card__stat-val">{{ ct.cpus }}</span>
          </div>
          <div class="ct-card__stat-row" v-if="ct.maxmem">
            <span class="ct-card__stat-label">RAM</span>
            <span class="ct-card__stat-val">{{ formatBytes(ct.maxmem) }}</span>
          </div>
          <div class="ct-card__stat-row" v-if="ct.maxdisk">
            <span class="ct-card__stat-label">Disk</span>
            <span class="ct-card__stat-val">{{ formatBytes(ct.maxdisk) }}</span>
          </div>
          <div class="ct-card__stat-row" v-if="ct._ip">
            <span class="ct-card__stat-label">IPv4</span>
            <span class="ct-card__stat-val ct-card__ip">{{ ct._ip }}</span>
          </div>
          <div class="ct-card__stat-row" v-if="ct.status === 'running' && ct.cpu != null">
            <span class="ct-card__stat-label">CPU</span>
            <span class="ct-card__stat-val">{{ (ct.cpu * 100).toFixed(1) }}%</span>
          </div>
          <div class="ct-card__stat-row" v-if="ct.status === 'running' && ct.uptime">
            <span class="ct-card__stat-label">Uptime</span>
            <span class="ct-card__stat-val">{{ formatUptime(ct.uptime) }}</span>
          </div>
        </div>
        <div v-if="ct.tags" class="ct-card__tags">
          <TagBadge v-for="tag in parseTags(ct.tags)" :key="tag" :tag="tag" small />
        </div>
        <div class="ct-card__actions">
          <button v-if="ct.status !== 'running'" @click="ctAction(ct, 'start')" class="btn btn-success btn-xs" :disabled="ct._actioning">Start</button>
          <button v-if="ct.status === 'running'" @click="ctAction(ct, 'stop')" class="btn btn-danger btn-xs" :disabled="ct._actioning">Stop</button>
          <button v-if="ct.status === 'running'" @click="ctAction(ct, 'reboot')" class="btn btn-outline btn-xs" :disabled="ct._actioning">Restart</button>
          <button @click="openDetail(ct)" class="btn btn-outline btn-xs">Details</button>
          <button @click="openConsole(ct)" class="btn btn-outline btn-xs">Console</button>
          <button @click="openShell(ct)" class="btn btn-outline btn-xs">Shell</button>
          <button @click="openSnapshotModal(ct)" class="btn btn-outline btn-xs">Snapshot</button>
        </div>
      </div>
    </div>

    <!-- Table -->
    <div v-else-if="!loading && sortedContainers.length > 0 && viewMode === 'table'" class="card">
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
              <th class="text-sm">OS</th>
              <th @click="toggleSort('status')" class="sortable-col">
                Status <span class="sort-icon">{{ sortIcon('status') }}</span>
              </th>
              <th @click="toggleSort('_node')" class="sortable-col">
                Node <span class="sort-icon">{{ sortIcon('_node') }}</span>
              </th>
              <th class="text-sm">Host</th>
              <th @click="toggleSort('cpus')" class="sortable-col">
                Cores <span class="sort-icon">{{ sortIcon('cpus') }}</span>
              </th>
              <th @click="toggleSort('cpu')" class="sortable-col">
                CPU% <span class="sort-icon">{{ sortIcon('cpu') }}</span>
              </th>
              <th @click="toggleSort('maxmem')" class="sortable-col">
                RAM <span class="sort-icon">{{ sortIcon('maxmem') }}</span>
              </th>
              <th @click="toggleSort('mem')" class="sortable-col">
                Mem Used <span class="sort-icon">{{ sortIcon('mem') }}</span>
              </th>
              <th @click="toggleSort('maxdisk')" class="sortable-col">
                Disk <span class="sort-icon">{{ sortIcon('maxdisk') }}</span>
              </th>
              <th class="text-sm">Tags</th>
              <th class="text-sm">IPv4</th>
              <th @click="toggleSort('uptime')" class="sortable-col">
                Uptime <span class="sort-icon">{{ sortIcon('uptime') }}</span>
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="sortedContainers.length === 0">
              <td colspan="16" class="text-muted text-center empty-row">
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

              <!-- OS -->
              <td class="os-col">
                <span
                  class="os-icon-badge"
                  :title="detectOs(ct.name || '').name"
                >{{ detectOs(ct.name || '').icon }}</span>
              </td>

              <!-- Status badge -->
              <td>
                <span :class="statusBadgeClass(ct.status)">{{ ct.status }}</span>
              </td>

              <!-- Node -->
              <td class="text-sm">{{ ct._node }}</td>

              <!-- Host -->
              <td class="text-sm">{{ ct._hostName }}</td>

              <!-- Cores -->
              <td class="text-sm text-center">
                <span v-if="ct.cpus">{{ ct.cpus }}</span>
                <span v-else class="text-muted">—</span>
              </td>

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

              <!-- RAM limit -->
              <td class="text-sm">
                <span v-if="ct.maxmem">{{ formatBytes(ct.maxmem) }}</span>
                <span v-else class="text-muted">—</span>
              </td>

              <!-- Memory used with inline bar -->
              <td class="stat-cell">
                <template v-if="ct.maxmem && ct.status === 'running'">
                  <div class="stat-bar-wrap">
                    <div class="stat-bar">
                      <div
                        class="stat-bar-fill"
                        :class="barClass((ct.mem / ct.maxmem) * 100)"
                        :style="{ width: Math.min((ct.mem / ct.maxmem) * 100, 100).toFixed(1) + '%' }"
                      ></div>
                    </div>
                    <span class="stat-bar-label">
                      {{ formatBytes(ct.mem) }}
                    </span>
                  </div>
                </template>
                <span v-else class="text-muted">—</span>
              </td>

              <!-- Disk size -->
              <td class="text-sm">
                <span v-if="ct.maxdisk">{{ formatBytes(ct.maxdisk) }}</span>
                <span v-else class="text-muted">—</span>
              </td>

              <!-- Tags -->
              <td>
                <div v-if="ct.tags" class="tags-row">
                  <TagBadge v-for="tag in parseTags(ct.tags)" :key="tag" :tag="tag" small />
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
                    v-if="ct.status === 'running'"
                    @click="ctAction(ct, 'reboot')"
                    class="btn btn-outline btn-xs"
                    :disabled="ct._actioning"
                    title="Restart"
                  >
                    <span v-if="ct._actioning && ct._pendingAction === 'reboot'">…</span>
                    <span v-else>Restart</span>
                  </button>
                  <button
                    @click="openDetail(ct)"
                    class="btn btn-outline btn-xs"
                    title="Details"
                  >
                    Details
                  </button>
                  <button
                    @click="openConsole(ct)"
                    class="btn btn-outline btn-xs"
                    title="Open Console (noVNC)"
                  >
                    Console
                  </button>
                  <button
                    @click="openShell(ct)"
                    class="btn btn-outline btn-xs btn-terminal"
                    title="Open Shell Terminal"
                  >
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:2px;"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
                    Shell
                  </button>
                  <button
                    @click="openSnapshotModal(ct)"
                    class="btn btn-outline btn-xs"
                    title="Create Snapshot"
                  >
                    Snapshot
                  </button>
                  <button
                    @click="deleteSingleContainer(ct)"
                    class="btn btn-danger btn-xs"
                    :disabled="ct._actioning || ct.status === 'running'"
                    title="Delete container (must be stopped)"
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Quick Snapshot Modal -->
    <div v-if="showSnapshotModal" class="modal" @click.self="showSnapshotModal = false">
      <div class="modal-content" style="max-width:440px;">
        <div class="modal-header">
          <h3>Create Snapshot — CT{{ snapshotTarget?.vmid }}</h3>
          <button @click="showSnapshotModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitSnapshot" class="modal-body">
          <div class="form-group">
            <label class="form-label">Snapshot Name</label>
            <input v-model="snapshotForm.snapname" class="form-control" placeholder="snap1" required />
          </div>
          <div class="form-group">
            <label class="form-label">Description (optional)</label>
            <input v-model="snapshotForm.description" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingSnapshot">
              {{ savingSnapshot ? 'Creating…' : 'Create' }}
            </button>
            <button type="button" @click="showSnapshotModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import { formatBytes, formatUptime } from '@/utils/proxmox'
import { detectOs } from '@/utils/osIcons'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import TagBadge from '@/components/TagBadge.vue'

const REFRESH_SECS = 30

export default {
  name: 'Containers',
  components: { SkeletonLoader, TagBadge },
  setup() {
    const toast = useToast()
    const router = useRouter()

    const containers = ref([])
    const hosts = ref([])
    const loading = ref(true)
    const bulkActioning = ref(false)
    const viewMode = ref('table')
    const criticalError = ref(null)
    const failedHosts = ref([])
    const timeoutWarning = ref(false)

    // Snapshot modal state
    const showSnapshotModal = ref(false)
    const snapshotTarget = ref(null)
    const snapshotForm = ref({ snapname: '', description: '' })
    const savingSnapshot = ref(false)

    // Persist filter state
    const CT_FILTER_KEY = 'depl0y_ct_filter'
    function loadCtFilter() {
      try { return JSON.parse(sessionStorage.getItem(CT_FILTER_KEY) || '{}') } catch { return {} }
    }
    const savedCtFilter = loadCtFilter()

    // Filters
    const searchQuery = ref(savedCtFilter.search || '')
    const statusFilter = ref(savedCtFilter.status || 'all')
    const hostFilter = ref(savedCtFilter.host || 'all')
    const nodeFilter = ref(savedCtFilter.node || 'all')
    const memFilter = ref(savedCtFilter.mem || 'all')

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

    const LOAD_TIMEOUT_MS = 10_000

    async function withTimeout(promise, ms) {
      let timer
      const timeout = new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('timeout')), ms)
      })
      try {
        const result = await Promise.race([promise, timeout])
        clearTimeout(timer)
        return result
      } catch (err) {
        clearTimeout(timer)
        throw err
      }
    }

    async function tryLoadAll() {
      const hostsRes = await api.proxmox.listHosts()
      hosts.value = hostsRes.data || []

      const localFailedHosts = []
      let timedOut = false

      const allCts = await Promise.all(
        hosts.value.map(async (host) => {
          try {
            const res = await withTimeout(
              api.pveNode.clusterResources(host.id, 'lxc'),
              LOAD_TIMEOUT_MS
            )
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
          } catch (err) {
            if (err.message === 'timeout') timedOut = true
            localFailedHosts.push(host.name || host.id)
            return []
          }
        })
      )

      failedHosts.value = localFailedHosts
      timeoutWarning.value = timedOut
      containers.value = allCts.flat().sort((a, b) => a.vmid - b.vmid)
    }

    const loadAll = async (manual = false) => {
      if (manual) countdown.value = REFRESH_SECS
      loading.value = true
      criticalError.value = null

      let lastErr = null
      const MAX_ATTEMPTS = 2
      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
        try {
          await tryLoadAll()
          lastErr = null
          break
        } catch (e) {
          lastErr = e
          if (attempt < MAX_ATTEMPTS) {
            // exponential backoff: 1s before retry
            await new Promise(r => setTimeout(r, 1000 * attempt))
          }
        }
      }

      if (lastErr) {
        console.error('Failed to load containers', lastErr)
        criticalError.value = lastErr.response?.data?.detail || lastErr.message || 'Unknown error'
        toast.error('Failed to load containers')
      }

      loading.value = false
    }

    const clearFilters = () => {
      searchQuery.value = ''
      statusFilter.value = 'all'
      hostFilter.value = 'all'
      nodeFilter.value = 'all'
      memFilter.value = 'all'
    }

    // ── Computed: unique nodes ────────────────────────────────────────────────

    const uniqueNodes = computed(() => {
      const nodes = new Set(containers.value.map(ct => ct._node).filter(Boolean))
      return [...nodes].sort()
    })

    // ── Filtered view ─────────────────────────────────────────────────────────

    // Persist filter changes to sessionStorage
    watch([searchQuery, statusFilter, hostFilter, nodeFilter, memFilter], () => {
      sessionStorage.setItem(CT_FILTER_KEY, JSON.stringify({
        search: searchQuery.value,
        status: statusFilter.value,
        host: hostFilter.value,
        node: nodeFilter.value,
        mem: memFilter.value,
      }))
    })

    const filteredContainers = computed(() => {
      const q = searchQuery.value.trim().toLowerCase()
      const minMemMb = memFilter.value !== 'all' ? parseInt(memFilter.value, 10) : 0
      return containers.value.filter(ct => {
        if (hostFilter.value !== 'all' && ct._hostId !== hostFilter.value) return false
        if (nodeFilter.value !== 'all' && ct._node !== nodeFilter.value) return false
        if (statusFilter.value !== 'all' && ct.status !== statusFilter.value) return false
        if (minMemMb > 0) {
          const maxMemMb = (ct.maxmem || 0) / (1024 * 1024)
          if (maxMemMb < minMemMb) return false
        }
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
        toast.error(`Failed to ${action} container ${ct.name || ct.vmid}`)
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

    const openConsole = (ct) => {
      router.push({
        path: `/console/${ct._node}/${ct.vmid}`,
        query: { type: 'lxc', hostId: ct._hostId },
      })
    }

    const openSnapshotModal = (ct) => {
      snapshotTarget.value = ct
      snapshotForm.value = { snapname: '', description: '' }
      showSnapshotModal.value = true
    }

    const submitSnapshot = async () => {
      if (!snapshotTarget.value || !snapshotForm.value.snapname) return
      savingSnapshot.value = true
      try {
        await api.pveNode.createContainerSnapshot(
          snapshotTarget.value._hostId,
          snapshotTarget.value._node,
          snapshotTarget.value.vmid,
          { snapname: snapshotForm.value.snapname, description: snapshotForm.value.description }
        )
        toast.success(`Snapshot "${snapshotForm.value.snapname}" created for CT${snapshotTarget.value.vmid}`)
        showSnapshotModal.value = false
      } catch (e) {
        toast.error('Failed to create snapshot')
      } finally {
        savingSnapshot.value = false
      }
    }

    const bulkSnapshot = async () => {
      const targets = sortedContainers.value.filter(ct => selectedIds.has(ctKey(ct)))
      if (!targets.length) return
      const snapname = prompt('Snapshot name for all selected containers:')
      if (!snapname) return
      if (!confirm(`Create snapshot "${snapname}" for ${targets.length} container(s)?`)) return
      bulkActioning.value = true
      const results = await Promise.allSettled(
        targets.map(ct =>
          api.pveNode.createContainerSnapshot(ct._hostId, ct._node, ct.vmid, { snapname })
        )
      )
      const failed = results.filter(r => r.status === 'rejected').length
      if (failed) toast.error(`${failed} snapshot(s) failed`)
      else toast.success(`Snapshot "${snapname}" created for ${targets.length} container(s)`)
      bulkActioning.value = false
      selectedIds.clear()
    }

    const deleteSingleContainer = async (ct) => {
      if (!confirm(`Permanently delete CT ${ct.vmid} (${ct.name || ''})? This cannot be undone.`)) return
      ct._actioning = true
      try {
        await api.pveNode.deleteContainer(ct._hostId, ct._node, ct.vmid)
        toast.success(`CT ${ct.vmid} deleted`)
        setTimeout(() => loadAll(), 2000)
      } catch (e) {
        toast.error(`Failed to delete CT ${ct.vmid}`)
      } finally {
        ct._actioning = false
      }
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
      viewMode,
      searchQuery,
      statusFilter,
      hostFilter,
      nodeFilter,
      memFilter,
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
      showSnapshotModal,
      snapshotTarget,
      snapshotForm,
      savingSnapshot,
      criticalError,
      failedHosts,
      timeoutWarning,
      formatBytes,
      formatUptime,
      statusBadgeClass,
      barClass,
      parseTags,
      loadAll,
      clearFilters,
      ctAction,
      openShell,
      openDetail,
      openConsole,
      openSnapshotModal,
      submitSnapshot,
      bulkSnapshot,
      deleteSingleContainer,
      ctKey,
      toggleSelect,
      toggleSelectAll,
      bulkAction,
      toggleSort,
      sortIcon,
      detectOs,
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
.count-running--link {
  cursor: pointer;
  padding: 0 0.25rem;
  border-radius: 3px;
  transition: background 0.15s, color 0.15s;
}
.count-running--link:hover {
  background: color-mix(in srgb, var(--accent, #6366f1) 15%, transparent);
  color: var(--text-primary);
}
.count-running--link:focus-visible {
  outline: 2px solid var(--accent, #6366f1);
  outline-offset: 2px;
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

.btn-terminal {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
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

/* ── OS column ─────────────────────────────────────────────────────────── */
.os-col { width: 36px; text-align: center; }
.os-icon-badge { font-size: 1.1rem; cursor: default; }

/* ── View toggle ─────────────────────────────────────────────────────────── */
.view-toggle {
  display: flex;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
}
.view-btn {
  padding: 0.3rem 0.6rem;
  background: var(--bg-primary);
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  transition: background 0.15s, color 0.15s;
}
.view-btn:hover { background: var(--bg-secondary); color: var(--text-primary); }
.view-btn--active { background: var(--primary-color); color: #fff; }
.view-btn + .view-btn { border-left: 1px solid var(--border-color); }

/* ── Grid view ────────────────────────────────────────────────────────────── */
.ct-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.ct-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  transition: box-shadow 0.15s, border-color 0.15s;
}
.ct-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.ct-card--running { border-left: 3px solid #22c55e; }
.ct-card--selected { background: rgba(59,130,246,0.06); border-color: var(--primary-color); }

.ct-card__header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: nowrap;
  overflow: hidden;
}
.ct-card__check { flex-shrink: 0; }
.ct-card__os { font-size: 1.1rem; flex-shrink: 0; }
.ct-card__name {
  flex: 1;
  font-weight: 600;
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  color: var(--primary-color);
}
.ct-card__name:hover { text-decoration: underline; }
.ct-card__badge { flex-shrink: 0; }

.ct-card__meta {
  display: flex;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}
.ct-card__vmid { font-family: monospace; }

.ct-card__stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem 0.75rem;
}
.ct-card__stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
}
.ct-card__stat-label { color: var(--text-muted); }
.ct-card__stat-val { font-weight: 500; }
.ct-card__ip { font-family: monospace; font-size: 0.75rem; }

.ct-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.ct-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.25rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-color);
}

/* ── Modal ────────────────────────────────────────────────────────────────── */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: var(--bg-primary);
  border-radius: 0.5rem;
  min-width: 320px;
  max-width: 90vw;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
}
.modal-header h3 { margin: 0; font-size: 1rem; font-weight: 600; }
.modal-body { padding: 1.25rem; }
.btn-close {
  background: none;
  border: none;
  font-size: 1.4rem;
  cursor: pointer;
  color: var(--text-muted);
  padding: 0 0.25rem;
  line-height: 1;
}
.btn-close:hover { color: var(--text-primary); }
.form-group { margin-bottom: 1rem; }
.form-label { display: block; font-size: 0.875rem; font-weight: 500; margin-bottom: 0.35rem; }
.form-control {
  width: 100%;
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.875rem;
}
.mt-2 { margin-top: 0.75rem; }

/* ── Error / Warning Banners ─────────────────────────────────────────────── */
.error-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.35);
  border-radius: 0.5rem;
  color: var(--text-primary);
}

.error-banner__icon { color: #ef4444; flex-shrink: 0; }

.error-banner__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.error-banner__msg {
  font-size: 0.825rem;
  color: var(--text-muted);
}

.error-banner__retry { margin-left: auto; flex-shrink: 0; }

.warning-banner {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.6rem 1rem;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: 0.5rem;
  font-size: 0.85rem;
  color: var(--text-primary);
}

.warning-banner svg { color: #f59e0b; flex-shrink: 0; }

.btn-inline-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.1rem;
  line-height: 1;
  color: var(--text-muted);
  padding: 0 0.2rem;
  margin-left: auto;
}
.btn-inline-close:hover { color: var(--text-primary); }
</style>
