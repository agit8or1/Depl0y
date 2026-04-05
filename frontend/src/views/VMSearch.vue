<template>
  <div class="vm-search-page">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2>VM Search</h2>
        <p class="text-muted">Search and filter virtual machines across all hosts</p>
      </div>
      <div class="header-actions">
        <button @click="exportCsv" class="btn btn-outline btn-sm" :disabled="results.length === 0">
          Export CSV
        </button>
        <button
          v-if="selectedKeys.size > 0"
          class="btn btn-primary btn-sm"
          @click="goToBulkOps"
        >
          Bulk Ops ({{ selectedKeys.size }})
        </button>
      </div>
    </div>

    <div class="search-layout">
      <!-- Filter Sidebar -->
      <aside class="filter-sidebar card">
        <div class="sidebar-title">Filters</div>

        <!-- Status -->
        <div class="filter-section">
          <label class="filter-label">Status</label>
          <div class="radio-group">
            <label class="radio-opt"><input type="radio" v-model="filters.status" value="" /> All</label>
            <label class="radio-opt"><input type="radio" v-model="filters.status" value="running" /> Running</label>
            <label class="radio-opt"><input type="radio" v-model="filters.status" value="stopped" /> Stopped</label>
          </div>
        </div>

        <!-- Host -->
        <div class="filter-section">
          <label class="filter-label">Host</label>
          <select v-model="filters.host_id" class="form-input filter-select">
            <option value="">All Hosts</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name || h.hostname }}</option>
          </select>
        </div>

        <!-- Node -->
        <div class="filter-section">
          <label class="filter-label">Node</label>
          <input v-model="filters.node" class="form-input" placeholder="e.g. pve1" />
        </div>

        <!-- Tags -->
        <div class="filter-section">
          <label class="filter-label">Tags (comma-separated)</label>
          <input v-model="filters.tags" class="form-input" placeholder="e.g. prod,web" />
        </div>

        <!-- OS Type -->
        <div class="filter-section">
          <label class="filter-label">OS Type</label>
          <input v-model="filters.os_type" class="form-input" placeholder="e.g. l26, win10" />
        </div>

        <!-- CPU Range -->
        <div class="filter-section">
          <label class="filter-label">CPU Usage %</label>
          <div class="range-row">
            <input v-model.number="filters.min_cpu" class="form-input range-input" type="number" min="0" max="100" placeholder="Min" />
            <span class="range-sep">–</span>
            <input v-model.number="filters.max_cpu" class="form-input range-input" type="number" min="0" max="100" placeholder="Max" />
          </div>
        </div>

        <!-- RAM Range -->
        <div class="filter-section">
          <label class="filter-label">RAM (GB)</label>
          <div class="range-row">
            <input v-model.number="filters.min_ram_gb" class="form-input range-input" type="number" min="0" placeholder="Min" />
            <span class="range-sep">–</span>
            <input v-model.number="filters.max_ram_gb" class="form-input range-input" type="number" min="0" placeholder="Max" />
          </div>
        </div>

        <button @click="clearFilters" class="btn btn-outline btn-sm mt-2" style="width:100%;">Clear Filters</button>
      </aside>

      <!-- Main content -->
      <div class="search-main">
        <!-- Search Bar -->
        <div class="search-bar card">
          <div class="search-input-wrap">
            <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input
              v-model="searchQuery"
              type="text"
              class="search-input"
              placeholder="Search by name, VMID, node, host, tags…"
              @keyup.enter="runSearch"
            />
            <button v-if="searchQuery" @click="searchQuery = ''; runSearch()" class="clear-btn">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
            <button @click="runSearch" class="btn btn-primary btn-sm" :disabled="searching">
              {{ searching ? 'Searching…' : 'Search' }}
            </button>
          </div>
          <div class="search-meta text-sm text-muted" v-if="!searching && searched">
            {{ total }} result{{ total !== 1 ? 's' : '' }} found
            <span v-if="total > pageSize"> — showing {{ skip + 1 }}–{{ Math.min(skip + pageSize, total) }}</span>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="searching" class="loading-spinner mt-2"></div>

        <!-- Error -->
        <div v-else-if="error" class="card empty-state mt-2">
          <p class="text-danger">{{ error }}</p>
          <button @click="runSearch" class="btn btn-outline btn-sm mt-1">Retry</button>
        </div>

        <!-- No results -->
        <div v-else-if="searched && results.length === 0" class="card empty-state mt-2">
          <div class="empty-icon-wrap">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          </div>
          <h4 class="empty-title">No VMs match your search</h4>
          <p class="empty-subtitle">Try adjusting your query or filters.</p>
        </div>

        <!-- Results Table -->
        <div v-else-if="results.length > 0" class="card mt-2">
          <!-- Bulk action bar -->
          <div v-if="selectedKeys.size > 0" class="bulk-bar">
            <span class="bulk-count">{{ selectedKeys.size }} selected</span>
            <button @click="bulkStart" class="btn btn-primary btn-sm" :disabled="bulkRunning">Start</button>
            <button @click="bulkShutdown" class="btn btn-warning btn-sm" :disabled="bulkRunning">Shutdown</button>
            <button @click="bulkStop" class="btn btn-danger btn-sm" :disabled="bulkRunning">Stop</button>
            <button @click="selectedKeys.clear()" class="btn btn-outline btn-sm">Clear</button>
          </div>

          <div class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th class="cb-col">
                    <input type="checkbox" :checked="allSelected" :indeterminate.prop="someSelected && !allSelected" @change="toggleSelectAll" />
                  </th>
                  <th @click="toggleSort('vmid')" class="sortable-col">VMID <span class="sort-icon">{{ sortIcon('vmid') }}</span></th>
                  <th @click="toggleSort('name')" class="sortable-col">Name <span class="sort-icon">{{ sortIcon('name') }}</span></th>
                  <th @click="toggleSort('status')" class="sortable-col">Status <span class="sort-icon">{{ sortIcon('status') }}</span></th>
                  <th @click="toggleSort('node')" class="sortable-col">Node <span class="sort-icon">{{ sortIcon('node') }}</span></th>
                  <th @click="toggleSort('host_name')" class="sortable-col">Host <span class="sort-icon">{{ sortIcon('host_name') }}</span></th>
                  <th @click="toggleSort('cpu')" class="sortable-col">CPU% <span class="sort-icon">{{ sortIcon('cpu') }}</span></th>
                  <th @click="toggleSort('maxmem')" class="sortable-col">Memory <span class="sort-icon">{{ sortIcon('maxmem') }}</span></th>
                  <th>Tags</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="vm in sortedResults"
                  :key="vmKey(vm)"
                  :class="{ 'row-selected': selectedKeys.has(vmKey(vm)) }"
                >
                  <td class="cb-col"><input type="checkbox" :checked="selectedKeys.has(vmKey(vm))" @change="toggleSelect(vm)" /></td>
                  <td><strong>{{ vm.vmid }}</strong></td>
                  <td>
                    <a class="vm-link" @click="navigateTo(vm)" style="cursor:pointer">
                      <span v-html="highlight(vm.name || '(no name)')"></span>
                    </a>
                  </td>
                  <td>
                    <span :class="['badge', statusBadgeClass(vm.status)]">{{ vm.status }}</span>
                  </td>
                  <td class="text-sm">{{ vm.node }}</td>
                  <td class="text-sm">{{ vm.host_name }}</td>
                  <td class="text-sm">
                    <span v-if="vm.cpu != null">{{ (vm.cpu * 100).toFixed(1) }}%</span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="text-sm">
                    <span v-if="vm.maxmem">{{ formatBytes(vm.maxmem) }}</span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>
                    <div class="tags-row">
                      <span v-for="tag in parseTags(vm.tags)" :key="tag" class="tag-pill" :style="{ background: tagColor(tag) }">{{ tag }}</span>
                      <span v-if="!parseTags(vm.tags).length" class="text-muted">—</span>
                    </div>
                  </td>
                  <td>
                    <div class="action-btns">
                      <button v-if="vm.status !== 'running'" @click="vmAction(vm, 'start')" class="btn btn-primary btn-xs" :disabled="vm._busy">Start</button>
                      <button v-if="vm.status === 'running'" @click="vmAction(vm, 'shutdown')" class="btn btn-warning btn-xs" :disabled="vm._busy">Shutdown</button>
                      <button v-if="vm.status === 'running'" @click="vmAction(vm, 'stop')" class="btn btn-danger btn-xs" :disabled="vm._busy">Stop</button>
                      <button @click="navigateTo(vm)" class="btn btn-outline btn-xs">Details</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div v-if="total > pageSize" class="pagination-bar">
            <button @click="prevPage" class="btn btn-outline btn-sm" :disabled="skip === 0">Prev</button>
            <span class="page-info text-sm">Page {{ currentPage }} of {{ totalPages }}</span>
            <button @click="nextPage" class="btn btn-outline btn-sm" :disabled="skip + pageSize >= total">Next</button>
          </div>
        </div>

        <!-- Initial state -->
        <div v-else-if="!searched && !searching" class="card empty-state mt-2">
          <div class="empty-icon-wrap">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          </div>
          <h4 class="empty-title">Search your infrastructure</h4>
          <p class="empty-subtitle">Enter a search term above or use the filters to find VMs across all hosts.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

const PAGE_SIZE = 50

const TAG_PALETTE = [
  '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
  '#ef4444', '#06b6d4', '#84cc16', '#f97316',
]

export default {
  name: 'VMSearch',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const toast = useToast()

    const searchQuery = ref(route.query.q || '')
    const searching = ref(false)
    const searched = ref(false)
    const error = ref(null)
    const results = ref([])
    const total = ref(0)
    const skip = ref(0)
    const hosts = ref([])

    const filters = reactive({
      status: '',
      host_id: '',
      node: '',
      tags: '',
      os_type: '',
      min_cpu: null,
      max_cpu: null,
      min_ram_gb: null,
      max_ram_gb: null,
    })

    const sortKey = ref('name')
    const sortDir = ref('asc')
    const selectedKeys = reactive(new Set())
    const bulkRunning = ref(false)

    const pageSize = PAGE_SIZE

    const currentPage = computed(() => Math.floor(skip.value / PAGE_SIZE) + 1)
    const totalPages = computed(() => Math.ceil(total.value / PAGE_SIZE))

    const buildParams = () => {
      const p = { skip: skip.value, limit: PAGE_SIZE }
      if (searchQuery.value.trim()) p.q = searchQuery.value.trim()
      if (filters.status) p.status = filters.status
      if (filters.host_id) p.host_id = filters.host_id
      if (filters.node) p.node = filters.node
      if (filters.tags) p.tags = filters.tags
      if (filters.os_type) p.os_type = filters.os_type
      if (filters.min_cpu != null) p.min_cpu = filters.min_cpu
      if (filters.max_cpu != null) p.max_cpu = filters.max_cpu
      if (filters.min_ram_gb != null) p.min_ram_gb = filters.min_ram_gb
      if (filters.max_ram_gb != null) p.max_ram_gb = filters.max_ram_gb
      return p
    }

    const runSearch = async () => {
      searching.value = true
      error.value = null
      searched.value = true
      selectedKeys.clear()
      try {
        const res = await api.pveVm.search(buildParams())
        const data = res.data
        results.value = (data.vms || []).map(vm => ({ ...vm, _busy: false }))
        total.value = data.total || 0
        // Update URL
        router.replace({ query: { ...route.query, q: searchQuery.value || undefined } })
      } catch (e) {
        error.value = e.response?.data?.detail || e.message || 'Search failed'
        results.value = []
        total.value = 0
      } finally {
        searching.value = false
      }
    }

    const prevPage = () => {
      if (skip.value > 0) {
        skip.value = Math.max(0, skip.value - PAGE_SIZE)
        runSearch()
      }
    }

    const nextPage = () => {
      if (skip.value + PAGE_SIZE < total.value) {
        skip.value += PAGE_SIZE
        runSearch()
      }
    }

    // Sort
    const toggleSort = (key) => {
      if (sortKey.value === key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
      else { sortKey.value = key; sortDir.value = 'asc' }
    }
    const sortIcon = (key) => {
      if (sortKey.value !== key) return '↕'
      return sortDir.value === 'asc' ? '↑' : '↓'
    }

    const sortedResults = computed(() => {
      const list = [...results.value]
      list.sort((a, b) => {
        let av = a[sortKey.value] ?? ''
        let bv = b[sortKey.value] ?? ''
        if (typeof av === 'string') { av = av.toLowerCase(); bv = bv.toLowerCase() }
        if (av < bv) return sortDir.value === 'asc' ? -1 : 1
        if (av > bv) return sortDir.value === 'asc' ? 1 : -1
        return 0
      })
      return list
    })

    // Selection
    const vmKey = (vm) => `${vm.host_id}:${vm.node}:${vm.vmid}`

    const toggleSelect = (vm) => {
      const k = vmKey(vm)
      if (selectedKeys.has(k)) selectedKeys.delete(k)
      else selectedKeys.add(k)
    }

    const allSelected = computed(() =>
      results.value.length > 0 && results.value.every(vm => selectedKeys.has(vmKey(vm)))
    )
    const someSelected = computed(() =>
      results.value.some(vm => selectedKeys.has(vmKey(vm)))
    )
    const toggleSelectAll = () => {
      if (allSelected.value) results.value.forEach(vm => selectedKeys.delete(vmKey(vm)))
      else results.value.forEach(vm => selectedKeys.add(vmKey(vm)))
    }

    const selectedVms = computed(() => results.value.filter(vm => selectedKeys.has(vmKey(vm))))

    // Actions
    const navigateTo = (vm) => {
      router.push(`/proxmox/${vm.host_id}/nodes/${vm.node}/vms/${vm.vmid}`)
    }

    const vmAction = async (vm, action) => {
      vm._busy = true
      try {
        if (action === 'start') await api.pveVm.start(vm.host_id, vm.node, vm.vmid)
        else if (action === 'shutdown') await api.pveVm.shutdown(vm.host_id, vm.node, vm.vmid)
        else if (action === 'stop') await api.pveVm.stop(vm.host_id, vm.node, vm.vmid)
        toast.success(`VM ${vm.vmid}: ${action} initiated`)
        setTimeout(runSearch, 2000)
      } catch (e) {
        toast.error(`Failed to ${action} VM ${vm.vmid}`)
      } finally {
        vm._busy = false
      }
    }

    const bulkStart = async () => {
      bulkRunning.value = true
      for (const vm of selectedVms.value) {
        try { await api.pveVm.start(vm.host_id, vm.node, vm.vmid) } catch {}
      }
      bulkRunning.value = false
      toast.success('Start sent to selected VMs')
      setTimeout(runSearch, 2500)
    }

    const bulkShutdown = async () => {
      bulkRunning.value = true
      for (const vm of selectedVms.value) {
        try { await api.pveVm.shutdown(vm.host_id, vm.node, vm.vmid) } catch {}
      }
      bulkRunning.value = false
      toast.success('Shutdown sent to selected VMs')
      setTimeout(runSearch, 2500)
    }

    const bulkStop = async () => {
      if (!confirm(`Force-stop ${selectedVms.value.length} VMs?`)) return
      bulkRunning.value = true
      for (const vm of selectedVms.value) {
        try { await api.pveVm.stop(vm.host_id, vm.node, vm.vmid) } catch {}
      }
      bulkRunning.value = false
      toast.success('Stop sent to selected VMs')
      setTimeout(runSearch, 2500)
    }

    const goToBulkOps = () => {
      // pass selected VM keys to bulk-ops page via sessionStorage
      const vms = selectedVms.value.map(vm => ({
        hostId: vm.host_id, node: vm.node, vmid: vm.vmid, name: vm.name, status: vm.status
      }))
      sessionStorage.setItem('bulkOpsVMs', JSON.stringify(vms))
      router.push('/bulk-ops')
    }

    // Export CSV
    const exportCsv = () => {
      const headers = ['VMID', 'Name', 'Status', 'Node', 'Host', 'CPU%', 'Memory (GB)', 'Tags']
      const rows = results.value.map(vm => [
        vm.vmid,
        `"${(vm.name || '').replace(/"/g, '""')}"`,
        vm.status,
        vm.node,
        vm.host_name,
        vm.cpu != null ? (vm.cpu * 100).toFixed(1) : '',
        vm.maxmem ? ((vm.maxmem / (1024 ** 3)).toFixed(2)) : '',
        `"${(vm.tags || '').replace(/"/g, '""')}"`,
      ].join(','))
      const csv = [headers.join(','), ...rows].join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `vm-search-${Date.now()}.csv`
      a.click()
      URL.revokeObjectURL(url)
    }

    // Helpers
    const formatBytes = (bytes) => {
      if (!bytes) return '—'
      const gb = bytes / (1024 ** 3)
      return gb >= 1 ? gb.toFixed(1) + ' GB' : (bytes / (1024 ** 2)).toFixed(0) + ' MB'
    }

    const parseTags = (t) => {
      if (!t) return []
      return t.split(';').map(x => x.trim()).filter(Boolean)
    }

    const tagColor = (tag) => {
      let h = 0
      for (let i = 0; i < tag.length; i++) h = tag.charCodeAt(i) + ((h << 5) - h)
      return TAG_PALETTE[Math.abs(h) % TAG_PALETTE.length]
    }

    const statusBadgeClass = (s) => {
      if (s === 'running') return 'badge-success'
      if (s === 'stopped') return 'badge-danger'
      if (s === 'paused') return 'badge-warning'
      return 'badge-secondary'
    }

    const highlight = (text) => {
      const q = searchQuery.value.trim()
      if (!q || q.length < 2) return text
      const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      return text.replace(new RegExp(`(${escaped})`, 'gi'), '<mark>$1</mark>')
    }

    const clearFilters = () => {
      filters.status = ''
      filters.host_id = ''
      filters.node = ''
      filters.tags = ''
      filters.os_type = ''
      filters.min_cpu = null
      filters.max_cpu = null
      filters.min_ram_gb = null
      filters.max_ram_gb = null
      skip.value = 0
      runSearch()
    }

    // Load hosts for filter dropdown
    const loadHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = res.data || []
      } catch {}
    }

    onMounted(async () => {
      await loadHosts()
      if (searchQuery.value || Object.values(filters).some(v => v)) {
        runSearch()
      }
    })

    // Watch filter changes with debounce
    let filterTimer = null
    watch([() => filters.status, () => filters.host_id, () => filters.node, () => filters.tags,
           () => filters.os_type, () => filters.min_cpu, () => filters.max_cpu,
           () => filters.min_ram_gb, () => filters.max_ram_gb], () => {
      clearTimeout(filterTimer)
      filterTimer = setTimeout(() => { skip.value = 0; runSearch() }, 400)
    })

    return {
      searchQuery, searching, searched, error, results, total, skip, hosts,
      filters, sortKey, sortDir, selectedKeys, bulkRunning,
      pageSize, currentPage, totalPages,
      sortedResults, allSelected, someSelected,
      runSearch, prevPage, nextPage, clearFilters,
      toggleSort, sortIcon, vmKey, toggleSelect, toggleSelectAll,
      navigateTo, vmAction, bulkStart, bulkShutdown, bulkStop, goToBulkOps,
      exportCsv, formatBytes, parseTags, tagColor, statusBadgeClass, highlight,
    }
  }
}
</script>

<style scoped>
.vm-search-page { padding: 0; }

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

.header-actions { display: flex; gap: 0.5rem; align-items: center; }

/* Layout */
.search-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 768px) {
  .search-layout { grid-template-columns: 1fr; }
}

/* Sidebar */
.filter-sidebar {
  padding: 1rem;
  position: sticky;
  top: 1rem;
}

.sidebar-title {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.filter-section { margin-bottom: 1rem; }

.filter-label {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.35rem;
}

.form-input {
  width: 100%;
  padding: 0.35rem 0.5rem;
  font-size: 0.85rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background: var(--bg-primary, var(--background));
  color: var(--text-primary);
  box-sizing: border-box;
}

.filter-select { cursor: pointer; }

.radio-group { display: flex; flex-direction: column; gap: 0.3rem; }
.radio-opt {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  cursor: pointer;
  color: var(--text-primary);
}

.range-row { display: flex; align-items: center; gap: 0.35rem; }
.range-input { flex: 1; }
.range-sep { color: var(--text-muted); font-size: 0.85rem; }

/* Search bar */
.search-bar { padding: 0.75rem 1rem; }

.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.search-icon { color: var(--text-muted); flex-shrink: 0; }

.search-input {
  flex: 1;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.45rem 0.75rem;
  font-size: 0.9rem;
  background: var(--bg-primary, var(--background));
  color: var(--text-primary);
  outline: none;
}

.search-input:focus {
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
}

.clear-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  align-items: center;
}

.search-meta { margin-top: 0.25rem; }

/* Table */
.table-container { overflow-x: auto; }
.cb-col { width: 2rem; text-align: center; }
.row-selected td { background: rgba(59,130,246,0.06); }

.sortable-col { cursor: pointer; user-select: none; white-space: nowrap; }
.sortable-col:hover { color: var(--primary-color); }
.sort-icon { font-size: 0.75rem; color: var(--text-muted); margin-left: 0.2rem; }

.vm-link { color: var(--primary-color); font-weight: 500; }
.vm-link:hover { text-decoration: underline; }

.tags-row { display: flex; flex-wrap: wrap; gap: 0.25rem; }
.tag-pill {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 9999px;
  color: #fff;
  white-space: nowrap;
}

.action-btns { display: flex; gap: 0.3rem; flex-wrap: nowrap; }

.btn-xs { padding: 0.15rem 0.45rem; font-size: 0.75rem; line-height: 1.4; }

/* Bulk bar */
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--border-color);
  background: rgba(59,130,246,0.05);
}

.bulk-count { font-size: 0.85rem; font-weight: 600; color: var(--primary-color); }

/* Pagination */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-color);
}

.page-info { color: var(--text-muted); }

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1.5rem;
  text-align: center;
}

.empty-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--background);
  border: 2px dashed var(--border-color);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-title { font-size: 1rem; font-weight: 600; color: var(--text-primary); margin: 0; }
.empty-subtitle { font-size: 0.875rem; color: var(--text-secondary); margin: 0; max-width: 380px; }

/* Highlight */
:deep(mark) {
  background: rgba(251, 191, 36, 0.35);
  color: inherit;
  border-radius: 2px;
  padding: 0 1px;
}

.mt-2 { margin-top: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-muted); }
.text-danger { color: #ef4444; }
.mt-1 { margin-top: 0.25rem; }
.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.875rem; }
</style>
