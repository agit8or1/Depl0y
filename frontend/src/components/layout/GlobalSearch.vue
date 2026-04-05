<template>
  <div class="global-search" ref="searchContainer">
    <div class="search-input-wrapper">
      <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
      </svg>
      <input
        ref="inputRef"
        v-model="query"
        type="text"
        class="search-input"
        placeholder="Search VMs, containers, nodes..."
        autocomplete="off"
        spellcheck="false"
        @keydown="onKeydown"
        @focus="onFocus"
      />
      <button v-if="query" class="clear-btn" @click="clearSearch" title="Clear (Esc)">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
      <span v-if="loading" class="spinner"></span>
      <kbd v-if="!query && !loading" class="search-hint-kbd">Ctrl K</kbd>
    </div>

    <div v-if="showDropdown" class="search-dropdown">
      <!-- Recent searches (shown when no query) -->
      <template v-if="!query && recentSearches.length">
        <div class="result-group-label result-group-label--recent">
          Recent
          <button class="clear-recent-btn" @mousedown.prevent="clearRecentSearches">Clear</button>
        </div>
        <div
          v-for="(term, idx) in recentSearches"
          :key="'recent-' + idx"
          class="result-item result-item--recent"
          @mousedown.prevent="applyRecent(term)"
        >
          <span class="result-icon">🕐</span>
          <span class="result-name">{{ term }}</span>
        </div>
      </template>

      <!-- No results -->
      <div v-if="query && !loading && results.length === 0 && query.length >= 2" class="no-results">
        No results for "{{ query }}"
      </div>

      <!-- Result groups -->
      <template v-for="group in groupedResults" :key="group.type">
        <div class="result-group-label">
          <span class="group-type-icon">{{ group.icon }}</span>
          {{ group.label }}
        </div>
        <div
          v-for="(item, idx) in group.items"
          :key="item._key"
          class="result-item"
          :class="{ 'result-item--active': flatIndex(group.type, idx) === activeIndex }"
          @mouseenter="activeIndex = flatIndex(group.type, idx)"
          @mousedown.prevent="navigateTo(item)"
        >
          <span class="result-icon">{{ item._icon }}</span>
          <div class="result-info">
            <span class="result-name">{{ item.name || item.id }}</span>
            <span class="result-meta">
              <span v-if="item.vmid" class="meta-chip">ID {{ item.vmid }}</span>
              <span v-if="item.node && item.type !== 'node'" class="meta-chip">{{ item.node }}</span>
              <span class="meta-chip host-chip">{{ item._hostName }}</span>
            </span>
          </div>
          <span class="result-status" :class="statusClass(item.status)">{{ item.status || 'unknown' }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

const CACHE_TTL = 60_000 // 60 seconds
const hostsCache = { data: null, ts: 0 }
const resourcesCache = {} // keyed by hostId

const ICONS = { qemu: '🖥️', lxc: '📦', node: '🖧' }
const TYPE_ORDER = ['qemu', 'lxc', 'node']
const TYPE_LABELS = { qemu: 'Virtual Machines', lxc: 'Containers', node: 'Nodes' }
const TYPE_ICONS  = { qemu: '🖥️', lxc: '📦', node: '🌐' }
const MAX_RESULTS = 12
const RECENT_KEY  = 'depl0y_recent_searches'
const MAX_RECENT  = 5

function loadRecentSearches() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')
  } catch {
    return []
  }
}

function saveRecentSearch(term) {
  const trimmed = term.trim()
  if (!trimmed) return
  let list = loadRecentSearches().filter(t => t !== trimmed)
  list.unshift(trimmed)
  list = list.slice(0, MAX_RECENT)
  localStorage.setItem(RECENT_KEY, JSON.stringify(list))
}

export default {
  name: 'GlobalSearch',
  setup() {
    const router = useRouter()
    const query = ref('')
    const results = ref([])
    const loading = ref(false)
    const activeIndex = ref(-1)
    const showDropdown = ref(false)
    const searchContainer = ref(null)
    const inputRef = ref(null)
    const recentSearches = ref(loadRecentSearches())

    let debounceTimer = null

    // ── Caching helpers ──────────────────────────────────────────────────────
    const getHosts = async () => {
      const now = Date.now()
      if (hostsCache.data && now - hostsCache.ts < CACHE_TTL) return hostsCache.data
      const res = await api.proxmox.listHosts()
      hostsCache.data = res.data
      hostsCache.ts = now
      return hostsCache.data
    }

    const getResources = async (hostId) => {
      const now = Date.now()
      const entry = resourcesCache[hostId]
      if (entry && now - entry.ts < CACHE_TTL) return entry.data
      const res = await api.pveNode.clusterResources(hostId)
      resourcesCache[hostId] = { data: res.data, ts: now }
      return res.data
    }

    // ── Search logic ─────────────────────────────────────────────────────────
    const runSearch = async (q) => {
      if (q.length < 2) {
        results.value = []
        loading.value = false
        return
      }
      loading.value = true
      try {
        const hosts = await getHosts()
        const hostList = Array.isArray(hosts) ? hosts : (hosts.items || hosts.results || [])

        const term = q.toLowerCase()
        const allItems = []

        await Promise.allSettled(
          hostList.map(async (host) => {
            const hostId = host.id
            const hostName = host.name || host.hostname || `Host ${hostId}`
            let resources
            try {
              resources = await getResources(hostId)
            } catch {
              return
            }
            const list = Array.isArray(resources) ? resources : (resources.items || resources.data || [])
            for (const item of list) {
              const name = (item.name || item.id || '').toLowerCase()
              const vmid = String(item.vmid || '').toLowerCase()
              const node = (item.node || '').toLowerCase()
              if (name.includes(term) || vmid.includes(term) || node.includes(term)) {
                allItems.push({
                  ...item,
                  _hostId: hostId,
                  _hostName: hostName,
                  _icon: ICONS[item.type] || '🖧',
                  _key: `${hostId}-${item.type}-${item.id || item.vmid}`
                })
              }
            }
          })
        )

        // Sort by type order, then by name
        allItems.sort((a, b) => {
          const ta = TYPE_ORDER.indexOf(a.type)
          const tb = TYPE_ORDER.indexOf(b.type)
          if (ta !== tb) return (ta === -1 ? 99 : ta) - (tb === -1 ? 99 : tb)
          return (a.name || '').localeCompare(b.name || '')
        })

        results.value = allItems.slice(0, MAX_RESULTS)
      } catch (err) {
        console.error('[GlobalSearch] error:', err)
        results.value = []
      } finally {
        loading.value = false
      }
    }

    // ── Grouping ─────────────────────────────────────────────────────────────
    const groupedResults = computed(() => {
      const map = {}
      for (const item of results.value) {
        const t = item.type || 'unknown'
        if (!map[t]) map[t] = []
        map[t].push(item)
      }
      return TYPE_ORDER
        .filter(t => map[t] && map[t].length)
        .map(t => ({ type: t, label: TYPE_LABELS[t] || t, icon: TYPE_ICONS[t] || '', items: map[t] }))
    })

    // Flat index across all groups for keyboard nav
    const flatIndex = (groupType, itemIdx) => {
      let offset = 0
      for (const g of groupedResults.value) {
        if (g.type === groupType) return offset + itemIdx
        offset += g.items.length
      }
      return offset + itemIdx
    }

    const flatResults = computed(() => {
      const out = []
      for (const g of groupedResults.value) out.push(...g.items)
      return out
    })

    // ── Navigation ───────────────────────────────────────────────────────────
    const navigateTo = (item) => {
      const h = item._hostId
      const node = item.node
      const vmid = item.vmid

      let route = ''
      if (item.type === 'qemu') {
        route = `/proxmox/${h}/nodes/${node}/vms/${vmid}`
      } else if (item.type === 'lxc') {
        route = `/proxmox/${h}/nodes/${node}/containers/${vmid}`
      } else {
        route = `/proxmox/${h}/nodes/${node}`
      }

      // Persist the search term as a recent search
      if (query.value.trim()) {
        saveRecentSearch(query.value.trim())
        recentSearches.value = loadRecentSearches()
      }

      clearSearch()
      router.push(route)
    }

    const clearSearch = () => {
      query.value = ''
      results.value = []
      showDropdown.value = false
      activeIndex.value = -1
    }

    const clearRecentSearches = () => {
      localStorage.removeItem(RECENT_KEY)
      recentSearches.value = []
    }

    const applyRecent = (term) => {
      query.value = term
      inputRef.value?.focus()
    }

    // ── Keyboard ─────────────────────────────────────────────────────────────
    const onKeydown = (e) => {
      const total = flatResults.value.length
      if (e.key === 'Escape') {
        clearSearch()
        inputRef.value?.blur()
        return
      }
      if (!showDropdown.value || total === 0) return

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        activeIndex.value = (activeIndex.value + 1) % total
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        activeIndex.value = (activeIndex.value - 1 + total) % total
      } else if (e.key === 'Enter' && activeIndex.value >= 0) {
        e.preventDefault()
        const item = flatResults.value[activeIndex.value]
        if (item) navigateTo(item)
      }
    }

    const onFocus = () => {
      if (query.value.length >= 2 || recentSearches.value.length > 0) {
        showDropdown.value = true
      }
    }

    // ── Status badge ─────────────────────────────────────────────────────────
    const statusClass = (status) => {
      if (!status) return 'status--unknown'
      if (status === 'running') return 'status--running'
      if (status === 'stopped') return 'status--stopped'
      if (status === 'paused') return 'status--paused'
      if (status === 'online') return 'status--running'
      return 'status--unknown'
    }

    // ── Watchers ─────────────────────────────────────────────────────────────
    watch(query, (val) => {
      activeIndex.value = -1
      clearTimeout(debounceTimer)
      if (val.length < 2) {
        results.value = []
        // Keep dropdown open if we have recent searches and input is focused
        const hasFocus = document.activeElement === inputRef.value
        showDropdown.value = hasFocus && recentSearches.value.length > 0
        loading.value = false
        return
      }
      showDropdown.value = true
      loading.value = true
      debounceTimer = setTimeout(() => runSearch(val), 400)
    })

    // ── Click outside ─────────────────────────────────────────────────────────
    const onClickOutside = (e) => {
      if (searchContainer.value && !searchContainer.value.contains(e.target)) {
        showDropdown.value = false
      }
    }

    onMounted(() => document.addEventListener('mousedown', onClickOutside))
    onBeforeUnmount(() => {
      document.removeEventListener('mousedown', onClickOutside)
      clearTimeout(debounceTimer)
    })

    return {
      query,
      results,
      loading,
      activeIndex,
      showDropdown,
      searchContainer,
      inputRef,
      recentSearches,
      groupedResults,
      flatIndex,
      onKeydown,
      onFocus,
      navigateTo,
      clearSearch,
      clearRecentSearches,
      applyRecent,
      statusClass
    }
  }
}
</script>

<style scoped>
.global-search {
  position: relative;
  width: 420px;
  max-width: 100%;
}

/* ── Input wrapper ── */
.search-input-wrapper {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  padding: 0 0.75rem;
  gap: 0.5rem;
  transition: border-color 0.2s, background 0.2s;
}

.search-input-wrapper:focus-within {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(59, 130, 246, 0.7);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.search-icon {
  color: rgba(255, 255, 255, 0.65);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #fff;
  font-size: 0.875rem;
  padding: 0.6rem 0;
  min-width: 0;
}

.search-input::placeholder {
  color: rgba(255, 255, 255, 0.55);
}

.clear-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px;
  color: rgba(255, 255, 255, 0.65);
  display: flex;
  align-items: center;
  border-radius: 4px;
  transition: color 0.15s;
}

.clear-btn:hover {
  color: rgba(255, 255, 255, 0.9);
}

/* ── Spinner ── */
.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: rgba(59, 130, 246, 0.9);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Dropdown ── */
.search-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  background: #1e2a3a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
  z-index: 1000;
  overflow: hidden;
  max-height: 480px;
  overflow-y: auto;
}

.no-results {
  padding: 1rem 1.25rem;
  color: rgba(255, 255, 255, 0.65);
  font-size: 0.875rem;
  text-align: center;
}

/* ── Group label ── */
.result-group-label {
  padding: 0.5rem 1rem 0.25rem;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(59, 130, 246, 0.8);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.result-group-label:first-child {
  border-top: none;
}

/* ── Result item ── */
.result-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.55rem 1rem;
  cursor: pointer;
  transition: background 0.12s;
}

.result-item:hover,
.result-item--active {
  background: rgba(59, 130, 246, 0.12);
}

.result-icon {
  font-size: 1.1rem;
  flex-shrink: 0;
  width: 22px;
  text-align: center;
}

.result-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.result-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-meta {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.meta-chip {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.65);
  background: rgba(255, 255, 255, 0.09);
  border-radius: 4px;
  padding: 0 5px;
  line-height: 1.6;
}

.host-chip {
  color: rgba(147, 197, 253, 0.9);
}

/* ── Status badge ── */
.result-status {
  font-size: 0.7rem;
  font-weight: 600;
  border-radius: 10px;
  padding: 2px 8px;
  white-space: nowrap;
  flex-shrink: 0;
  text-transform: capitalize;
}

.status--running {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.status--stopped {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
}

.status--paused {
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
}

.status--unknown {
  background: rgba(255, 255, 255, 0.09);
  color: rgba(255, 255, 255, 0.65);
}

/* ── Ctrl K hint ── */
.search-hint-kbd {
  font-size: 0.68rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 4px;
  padding: 1px 6px;
  color: rgba(255, 255, 255, 0.45);
  white-space: nowrap;
  flex-shrink: 0;
  pointer-events: none;
  font-family: inherit;
}

/* ── Recent searches ── */
.result-group-label--recent {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.clear-recent-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.65rem;
  color: rgba(59, 130, 246, 0.75);
  padding: 0;
  transition: color 0.15s;
  text-transform: none;
  letter-spacing: normal;
  font-weight: 500;
}

.clear-recent-btn:hover {
  color: #60a5fa;
}

.result-item--recent {
  opacity: 0.85;
}

.result-item--recent:hover {
  opacity: 1;
}

/* ── Group icon ── */
.group-type-icon {
  margin-right: 0.3rem;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .global-search {
    width: 200px;
  }

  .search-input {
    font-size: 0.8rem;
  }

  .search-hint-kbd {
    display: none;
  }
}
</style>
