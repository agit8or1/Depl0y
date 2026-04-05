<template>
  <teleport to="body">
    <transition name="palette-fade">
      <div v-if="isOpen" class="palette-backdrop" @mousedown.self="close">
        <div
          class="palette-modal"
          role="dialog"
          aria-modal="true"
          aria-label="Command Palette"
        >

          <!-- Search input -->
          <div class="palette-input-row">
            <!-- Mode indicator badge -->
            <span v-if="mode === 'nav'" class="palette-mode-badge palette-mode-badge--nav">Nav</span>
            <span v-else-if="mode === 'action'" class="palette-mode-badge palette-mode-badge--action">Action</span>
            <svg v-else class="palette-search-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              ref="inputRef"
              v-model="query"
              class="palette-input"
              type="text"
              :placeholder="inputPlaceholder"
              autocomplete="off"
              spellcheck="false"
              @keydown="onKeydown"
            />
            <span v-if="loading" class="palette-spinner"></span>
            <button v-if="query" class="palette-clear" @click="query = ''" title="Clear">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
            <kbd class="palette-esc-hint">Esc</kbd>
          </div>

          <!-- Mode hints (shown when no query yet) -->
          <div v-if="!query" class="palette-mode-hints">
            <span class="mode-hint">Type <kbd>&gt;</kbd> for navigation</span>
            <span class="mode-hint">Type <kbd>!</kbd> for actions</span>
          </div>

          <!-- Results -->
          <div class="palette-results" ref="resultsRef">

            <!-- Empty state -->
            <template v-if="sections.length === 0 && trimmedQuery.length >= 1">
              <div class="palette-empty">No results for "{{ trimmedQuery }}"</div>
            </template>

            <!-- Default view (no query): recent pages + quick actions -->
            <template v-if="sections.length === 0 && !trimmedQuery">
              <!-- Recent pages -->
              <template v-if="recentPages.length">
                <div class="palette-section-label">Recent Pages</div>
                <div
                  v-for="(page, idx) in recentPages"
                  :key="'recent-' + page.path"
                  class="palette-item"
                  :class="{ 'palette-item--active': flatActiveIndex === idx }"
                  @mouseenter="flatActiveIndex = idx"
                  @mousedown.prevent="executeItem(page)"
                >
                  <span class="palette-item-icon palette-icon-recent">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                  </span>
                  <span class="palette-item-label">{{ page.label }}</span>
                  <span class="palette-item-path">{{ page.path }}</span>
                </div>
              </template>

              <!-- Quick actions -->
              <div class="palette-section-label">Quick Actions</div>
              <div
                v-for="(action, idx) in defaultActions"
                :key="action.id"
                class="palette-item"
                :class="{ 'palette-item--active': flatActiveIndex === (recentPages.length + idx) }"
                @mouseenter="flatActiveIndex = recentPages.length + idx"
                @mousedown.prevent="executeItem(action)"
              >
                <span class="palette-item-icon">{{ action.icon }}</span>
                <span class="palette-item-label">{{ action.label }}</span>
                <kbd v-if="action.shortcut" class="palette-shortcut">{{ action.shortcut }}</kbd>
              </div>
            </template>

            <!-- Filtered sections -->
            <template v-for="section in sections" :key="section.type">
              <div class="palette-section-label">{{ section.label }}</div>
              <div
                v-for="item in section.items"
                :key="item._flatIdx"
                class="palette-item"
                :class="{ 'palette-item--active': flatActiveIndex === item._flatIdx }"
                @mouseenter="flatActiveIndex = item._flatIdx"
                @mousedown.prevent="executeItem(item)"
              >
                <!-- VM / LXC item -->
                <template v-if="item._sectionType === 'vms' || item._sectionType === 'lxc'">
                  <span class="palette-status-dot" :class="statusDotClass(item.status)"></span>
                  <div class="palette-item-info">
                    <span class="palette-item-label">{{ item.name || item.id }}</span>
                    <span class="palette-item-meta">
                      <span v-if="item.vmid" class="meta-tag">ID {{ item.vmid }}</span>
                      <span v-if="item.node" class="meta-tag">{{ item.node }}</span>
                      <span class="meta-tag meta-tag--host">{{ item._hostName }}</span>
                    </span>
                  </div>
                  <span class="palette-badge" :class="statusBadgeClass(item.status)">{{ item.status || 'unknown' }}</span>
                </template>

                <!-- Node item -->
                <template v-else-if="item._sectionType === 'nodes'">
                  <span class="palette-item-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
                  </span>
                  <div class="palette-item-info">
                    <span class="palette-item-label">{{ item.node || item.name || item.id }}</span>
                    <span class="palette-item-meta">
                      <span v-if="item.cpu != null" class="meta-tag">CPU {{ Math.round((item.cpu || 0) * 100) }}%</span>
                      <span v-if="item.mem != null && item.maxmem != null" class="meta-tag">MEM {{ Math.round((item.mem / item.maxmem) * 100) }}%</span>
                      <span class="meta-tag meta-tag--host">{{ item._hostName }}</span>
                    </span>
                  </div>
                  <span class="palette-badge" :class="statusBadgeClass(item.status)">{{ item.status || 'unknown' }}</span>
                </template>

                <!-- Nav item -->
                <template v-else-if="item._sectionType === 'nav'">
                  <span class="palette-item-icon palette-icon-nav">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                  </span>
                  <span class="palette-item-label">{{ item.label }}</span>
                  <kbd v-if="item.shortcut" class="palette-shortcut">{{ item.shortcut }}</kbd>
                </template>

                <!-- Action item -->
                <template v-else-if="item._sectionType === 'cmd'">
                  <span class="palette-item-icon palette-icon-action">{{ item.icon }}</span>
                  <div class="palette-item-info">
                    <span class="palette-item-label">{{ item.label }}</span>
                    <span v-if="item.description" class="palette-item-desc">{{ item.description }}</span>
                  </div>
                  <span v-if="item.danger" class="palette-badge badge--danger">destructive</span>
                </template>

                <!-- Generic action/route item -->
                <template v-else>
                  <span class="palette-item-icon">{{ item.icon }}</span>
                  <span class="palette-item-label">{{ item.label }}</span>
                  <kbd v-if="item.shortcut" class="palette-shortcut">{{ item.shortcut }}</kbd>
                </template>
              </div>
            </template>
          </div>

          <!-- Footer -->
          <div class="palette-footer">
            <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
            <span><kbd>Enter</kbd> select</span>
            <span><kbd>Esc</kbd> close</span>
            <span class="palette-footer-sep"></span>
            <span class="palette-footer-hint"><kbd>&gt;</kbd> nav &nbsp; <kbd>!</kbd> actions</span>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useClusterStore } from '@/store/cluster'
import { useAuthStore } from '@/store/auth'
import api from '@/services/api'

// ── Static data ──────────────────────────────────────────────────────────────

const NAV_COMMANDS = [
  { id: 'nav-dashboard',   label: 'Go to Dashboard',        icon: '📊', route: '/',            shortcut: 'g d' },
  { id: 'nav-vms',         label: 'Go to Virtual Machines', icon: '🖥️', route: '/vms',         shortcut: 'g v' },
  { id: 'nav-containers',  label: 'Go to Containers',       icon: '📦', route: '/containers',  shortcut: null },
  { id: 'nav-proxmox',     label: 'Go to Proxmox Hosts',    icon: '🌐', route: '/proxmox',     shortcut: 'g n' },
  { id: 'nav-tasks',       label: 'Go to Tasks',            icon: '📋', route: '/tasks',       shortcut: 'g t' },
  { id: 'nav-backup',      label: 'Go to Backup',           icon: '💾', route: '/backup',      shortcut: 'g b' },
  { id: 'nav-settings',    label: 'Go to Settings',         icon: '⚙️',  route: '/settings',   shortcut: 'g s' },
  { id: 'nav-users',       label: 'Go to Users',            icon: '👥', route: '/users',       shortcut: null, adminOnly: true },
  { id: 'nav-alerts',      label: 'Go to Alerts',           icon: '🔔', route: '/alerts',      shortcut: null },
  { id: 'nav-security',    label: 'Go to Security',         icon: '🔒', route: '/security',    shortcut: null },
  { id: 'nav-network',     label: 'Go to Network',          icon: '🔌', route: '/network',     shortcut: null },
  { id: 'nav-audit',       label: 'Go to Audit Log',        icon: '🔍', route: '/audit-log',   shortcut: null },
  { id: 'nav-images',      label: 'Go to Images',           icon: '💿', route: '/images',      shortcut: null },
  { id: 'nav-templates',   label: 'Go to Templates',        icon: '📄', route: '/templates',   shortcut: null },
  { id: 'nav-datacenter',  label: 'Go to Datacenter',       icon: '🏢', route: '/datacenter',  shortcut: null },
]

const ACTION_COMMANDS = [
  {
    id: 'create-vm',
    label: 'Create VM',
    description: 'Provision a new virtual machine on Proxmox',
    icon: '➕',
    route: '/create-pve-vm',
  },
  {
    id: 'create-lxc',
    label: 'Create LXC Container',
    description: 'Provision a new LXC container',
    icon: '📦',
    route: '/create-lxc',
  },
  {
    id: 'deploy-vm',
    label: 'Deploy VM from Template',
    description: 'Deploy a pre-configured VM using cloud-init',
    icon: '🚀',
    route: '/deploy',
  },
  {
    id: 'add-host',
    label: 'Add Proxmox Host',
    description: 'Connect a new Proxmox host to Depl0y',
    icon: '🖧',
    route: '/proxmox',
  },
  {
    id: 'open-settings',
    label: 'Open Settings',
    description: 'Configure Depl0y system settings',
    icon: '⚙️',
    route: '/settings',
  },
  {
    id: 'toggle-theme',
    label: 'Toggle Dark / Light Theme',
    description: 'Switch the current UI colour theme',
    icon: '🌓',
    action: 'toggleTheme',
  },
  {
    id: 'clear-cache',
    label: 'Clear System Cache',
    description: 'Flush all backend API caches (POST /api/v1/system/cache/clear)',
    icon: '🧹',
    action: 'clearCache',
  },
  {
    id: 'snapshot-all',
    label: 'Snapshot All Running VMs',
    description: 'Create a snapshot for every running VM across all hosts',
    icon: '📸',
    action: 'snapshotAll',
    danger: false,
  },
  {
    id: 'system-health',
    label: 'View System Health',
    description: 'Open the Depl0y system health dashboard',
    icon: '💚',
    route: '/system-health',
  },
  {
    id: 'api-explorer',
    label: 'Open API Explorer',
    description: 'Browse the live OpenAPI explorer',
    icon: '⚡',
    route: '/api-explorer',
  },
]

// Default quick actions shown when palette has no query
const DEFAULT_ACTIONS = [
  { id: 'create-vm',    label: 'Create VM',                 icon: '➕', route: '/create-pve-vm' },
  { id: 'deploy-vm',    label: 'Deploy VM',                 icon: '🚀', route: '/deploy' },
  { id: 'add-host',     label: 'Add Proxmox Host',          icon: '🖧',  route: '/proxmox' },
  { id: 'open-settings',label: 'Open Settings',             icon: '⚙️',  route: '/settings' },
  { id: 'toggle-theme', label: 'Toggle Dark / Light Theme', icon: '🌓', action: 'toggleTheme' },
]

// ── localStorage: recent pages ───────────────────────────────────────────────

const RECENT_PAGES_KEY = 'depl0y_recent_pages'
const MAX_RECENT = 5

// Route → human-readable label mapping
const ROUTE_LABELS = {
  '/': 'Dashboard',
  '/vms': 'Virtual Machines',
  '/containers': 'Containers',
  '/proxmox': 'Proxmox Hosts',
  '/tasks': 'Tasks',
  '/backup': 'Backup',
  '/settings': 'Settings',
  '/users': 'User Management',
  '/alerts': 'Alerts',
  '/security': 'Security',
  '/network': 'Network',
  '/audit-log': 'Audit Log',
  '/images': 'Images',
  '/templates': 'Templates',
  '/datacenter': 'Datacenter',
  '/profile': 'My Profile',
  '/system-health': 'System Health',
  '/api-explorer': 'API Explorer',
}

function loadRecentPages() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_PAGES_KEY) || '[]')
  } catch {
    return []
  }
}

function saveRecentPage(path, label) {
  const entry = { path, label: label || ROUTE_LABELS[path] || path }
  let list = loadRecentPages().filter(p => p.path !== path)
  list.unshift(entry)
  list = list.slice(0, MAX_RECENT)
  localStorage.setItem(RECENT_PAGES_KEY, JSON.stringify(list))
}

// ── Fuzzy match helper ────────────────────────────────────────────────────────

function fuzzyMatch(str, term) {
  if (!str) return false
  const s = str.toLowerCase()
  const t = term.toLowerCase()
  if (s.includes(t)) return true
  // sequential character match
  let si = 0
  for (let i = 0; i < t.length; i++) {
    const idx = s.indexOf(t[i], si)
    if (idx === -1) return false
    si = idx + 1
  }
  return true
}

// ── Component ─────────────────────────────────────────────────────────────────

export default {
  name: 'CommandPalette',

  setup() {
    const router = useRouter()
    const route = useRoute()
    const clusterStore = useClusterStore()
    const authStore = useAuthStore()

    const isOpen = ref(false)
    const query = ref('')
    const loading = ref(false)
    const flatActiveIndex = ref(0)
    const inputRef = ref(null)
    const resultsRef = ref(null)
    const recentPages = ref(loadRecentPages())

    // ── Derived ───────────────────────────────────────────────────────────────

    const trimmedQuery = computed(() => query.value.trim())

    // Detect prefix mode: '>' = nav, '!' = action commands
    const mode = computed(() => {
      const q = trimmedQuery.value
      if (q.startsWith('>')) return 'nav'
      if (q.startsWith('!')) return 'action'
      return 'search'
    })

    // The actual filter term (stripped of prefix)
    const filterTerm = computed(() => {
      const q = trimmedQuery.value
      if (mode.value === 'nav' || mode.value === 'action') return q.slice(1).trim()
      return q
    })

    const inputPlaceholder = computed(() => {
      if (mode.value === 'nav') return 'Type to filter navigation...'
      if (mode.value === 'action') return 'Type to filter actions...'
      return 'Search VMs, nodes, or type > nav / ! action...'
    })

    const isAdmin = computed(() => authStore.isAdmin)

    const defaultActions = computed(() =>
      DEFAULT_ACTIONS.filter(a => !a.adminOnly || isAdmin.value)
    )

    // ── Open / Close ──────────────────────────────────────────────────────────

    const open = async () => {
      recentPages.value = loadRecentPages()
      isOpen.value = true
      query.value = ''
      flatActiveIndex.value = 0
      await nextTick()
      inputRef.value?.focus()
      // Kick off background resource fetch (non-blocking)
      loading.value = true
      clusterStore.fetchResources().finally(() => { loading.value = false })
    }

    const close = () => {
      isOpen.value = false
      query.value = ''
    }

    // ── Computed sections ─────────────────────────────────────────────────────

    const sections = computed(() => {
      const q = filterTerm.value
      const m = mode.value

      if (!q && m === 'search') return []  // no query, no filter → show default view

      const result = []
      let flatIdx = 0

      if (m === 'nav') {
        // Navigation commands only
        const matched = NAV_COMMANDS
          .filter(n => !n.adminOnly || isAdmin.value)
          .filter(n => !q || fuzzyMatch(n.label, q) || fuzzyMatch(n.route, q))
          .slice(0, 12)
          .map(n => ({ ...n, _sectionType: 'nav', _flatIdx: flatIdx++ }))
        if (matched.length) result.push({ type: 'nav', label: 'Navigate to', items: matched })
        return result
      }

      if (m === 'action') {
        // Action commands only
        const matched = ACTION_COMMANDS
          .filter(a => !q || fuzzyMatch(a.label, q) || fuzzyMatch(a.description || '', q))
          .slice(0, 10)
          .map(a => ({ ...a, _sectionType: 'cmd', _flatIdx: flatIdx++ }))
        if (matched.length) result.push({ type: 'cmd', label: 'Commands', items: matched })
        return result
      }

      // ── Full search mode ───────────────────────────────────────────────────

      // VMs
      const matchedVMs = clusterStore.vms
        .filter(vm => {
          const name = (vm.name || vm.id || '').toLowerCase()
          const vmid = String(vm.vmid || '')
          return fuzzyMatch(name, q) || vmid.includes(q.toLowerCase())
        })
        .slice(0, 8)
        .map(vm => ({ ...vm, _sectionType: 'vms', _flatIdx: flatIdx++ }))
      if (matchedVMs.length) result.push({ type: 'vms', label: 'Virtual Machines', items: matchedVMs })

      // LXC
      const matchedLXC = clusterStore.lxc
        .filter(ct => {
          const name = (ct.name || ct.id || '').toLowerCase()
          const vmid = String(ct.vmid || '')
          return fuzzyMatch(name, q) || vmid.includes(q.toLowerCase())
        })
        .slice(0, 5)
        .map(ct => ({ ...ct, _sectionType: 'lxc', _flatIdx: flatIdx++ }))
      if (matchedLXC.length) result.push({ type: 'lxc', label: 'Containers', items: matchedLXC })

      // Nodes
      const matchedNodes = clusterStore.nodes
        .filter(n => fuzzyMatch(n.node || n.name || n.id || '', q))
        .slice(0, 5)
        .map(n => ({ ...n, _sectionType: 'nodes', _flatIdx: flatIdx++ }))
      if (matchedNodes.length) result.push({ type: 'nodes', label: 'Nodes', items: matchedNodes })

      // Recent pages
      const matchedRecent = recentPages.value
        .filter(p => fuzzyMatch(p.label, q) || fuzzyMatch(p.path, q))
        .slice(0, 3)
        .map(p => ({ ...p, _sectionType: 'nav', icon: '🕐', _flatIdx: flatIdx++ }))
      if (matchedRecent.length) result.push({ type: 'recent', label: 'Recent Pages', items: matchedRecent })

      // Nav commands
      const matchedNav = NAV_COMMANDS
        .filter(n => !n.adminOnly || isAdmin.value)
        .filter(n => fuzzyMatch(n.label, q))
        .slice(0, 4)
        .map(n => ({ ...n, _sectionType: 'nav', _flatIdx: flatIdx++ }))

      // Action commands
      const matchedActions = ACTION_COMMANDS
        .filter(a => fuzzyMatch(a.label, q) || fuzzyMatch(a.description || '', q))
        .slice(0, 4)
        .map(a => ({ ...a, _sectionType: 'cmd', _flatIdx: flatIdx++ }))

      const combinedCommands = [...matchedNav, ...matchedActions]
      if (combinedCommands.length) result.push({ type: 'commands', label: 'Commands & Navigation', items: combinedCommands })

      return result
    })

    // Flat total for keyboard nav
    const flatTotal = computed(() => {
      if (!trimmedQuery.value) {
        return recentPages.value.length + defaultActions.value.length
      }
      return sections.value.reduce((sum, s) => sum + s.items.length, 0)
    })

    // ── Execute item ──────────────────────────────────────────────────────────

    const executeItem = async (item) => {
      const act = item.action

      if (act === 'toggleTheme') {
        toggleTheme()
        close()
        return
      }

      if (act === 'clearCache') {
        close()
        try {
          await api.system.clearCache()
          // Show success via toast if available
          import('@/services/api').then(() => {}).catch(() => {})
        } catch (e) {
          console.error('[CommandPalette] clearCache failed', e)
        }
        return
      }

      if (act === 'snapshotAll') {
        close()
        await triggerSnapshotAll()
        return
      }

      if (item.route) {
        router.push(item.route)
        close()
        return
      }

      if (item._sectionType === 'vms') {
        router.push(`/proxmox/${item._hostId}/nodes/${item.node}/vms/${item.vmid}`)
        close()
        return
      }

      if (item._sectionType === 'lxc') {
        router.push(`/proxmox/${item._hostId}/nodes/${item.node}/containers/${item.vmid}`)
        close()
        return
      }

      if (item._sectionType === 'nodes') {
        router.push(`/proxmox/${item._hostId}/nodes/${item.node}`)
        close()
        return
      }

      // Fallback: path from recent page item
      if (item.path) {
        router.push(item.path)
        close()
      }
    }

    const toggleTheme = () => {
      const root = document.documentElement
      const current = root.getAttribute('data-theme') || 'light'
      const next = current === 'light' ? 'dark' : 'light'
      root.setAttribute('data-theme', next)
      localStorage.setItem('depl0y_theme', next)
    }

    const triggerSnapshotAll = async () => {
      const runningVMs = clusterStore.vms.filter(vm => vm.status === 'running')
      if (!runningVMs.length) return

      const snapname = `auto-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}`
      const tasks = runningVMs.map(vm =>
        api.pveVm.createSnapshot(vm._hostId, vm.node, vm.vmid, {
          snapname,
          description: 'Bulk snapshot from command palette',
          vmstate: false,
        }).catch(err => console.warn(`[CommandPalette] snapshot failed for ${vm.vmid}:`, err))
      )
      await Promise.allSettled(tasks)
    }

    // ── Keyboard navigation ───────────────────────────────────────────────────

    const onKeydown = (e) => {
      const total = flatTotal.value

      if (e.key === 'Escape') {
        close()
        return
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        flatActiveIndex.value = total > 0 ? (flatActiveIndex.value + 1) % total : 0
        scrollActiveIntoView()
        return
      }

      if (e.key === 'ArrowUp') {
        e.preventDefault()
        flatActiveIndex.value = total > 0 ? (flatActiveIndex.value - 1 + total) % total : 0
        scrollActiveIntoView()
        return
      }

      if (e.key === 'Enter') {
        e.preventDefault()
        const idx = flatActiveIndex.value

        if (!trimmedQuery.value) {
          // Default view: recent pages first, then quick actions
          if (idx < recentPages.value.length) {
            executeItem(recentPages.value[idx])
          } else {
            const actionIdx = idx - recentPages.value.length
            const action = defaultActions.value[actionIdx]
            if (action) executeItem(action)
          }
          return
        }

        // Filtered sections
        for (const section of sections.value) {
          const item = section.items.find(i => i._flatIdx === idx)
          if (item) { executeItem(item); break }
        }
      }
    }

    const scrollActiveIntoView = () => {
      nextTick(() => {
        const el = resultsRef.value?.querySelector('.palette-item--active')
        el?.scrollIntoView({ block: 'nearest' })
      })
    }

    // Reset active index when query changes
    watch(query, () => { flatActiveIndex.value = 0 })

    // ── Track route changes for recent pages ──────────────────────────────────

    watch(
      () => route.fullPath,
      (newPath) => {
        // Skip auth/login paths
        if (newPath === '/login' || newPath.startsWith('/login')) return
        const label = ROUTE_LABELS[route.path] || route.meta?.title || route.path
        saveRecentPage(route.path, label)
      }
    )

    // ── Global shortcut listener ──────────────────────────────────────────────

    const onGlobalKeydown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        if (isOpen.value) close()
        else open()
      }
      if (e.key === 'Escape' && isOpen.value) {
        close()
      }
    }

    onMounted(() => window.addEventListener('keydown', onGlobalKeydown))
    onBeforeUnmount(() => window.removeEventListener('keydown', onGlobalKeydown))

    // ── Status helpers ────────────────────────────────────────────────────────

    const statusDotClass = (status) => {
      if (status === 'running' || status === 'online') return 'dot--running'
      if (status === 'stopped') return 'dot--stopped'
      if (status === 'paused') return 'dot--paused'
      return 'dot--unknown'
    }

    const statusBadgeClass = (status) => {
      if (status === 'running' || status === 'online') return 'badge--running'
      if (status === 'stopped') return 'badge--stopped'
      if (status === 'paused') return 'badge--paused'
      return 'badge--unknown'
    }

    return {
      isOpen,
      query,
      loading,
      flatActiveIndex,
      inputRef,
      resultsRef,
      sections,
      defaultActions,
      recentPages,
      trimmedQuery,
      mode,
      inputPlaceholder,
      open,
      close,
      onKeydown,
      executeItem,
      statusDotClass,
      statusBadgeClass,
    }
  }
}
</script>

<style scoped>
/* ── Backdrop ── */
.palette-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 10vh;
}

/* ── Modal ── */
.palette-modal {
  width: 640px;
  max-width: calc(100vw - 2rem);
  background: #151e2d;
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 16px;
  box-shadow: 0 32px 96px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(59, 130, 246, 0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  max-height: 72vh;
}

/* ── Input row ── */
.palette-input-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.875rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  flex-shrink: 0;
}

.palette-search-icon {
  color: rgba(255, 255, 255, 0.45);
  flex-shrink: 0;
}

/* Mode badge (Nav / Action) */
.palette-mode-badge {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-radius: 5px;
  padding: 2px 7px;
  flex-shrink: 0;
  line-height: 1.5;
}

.palette-mode-badge--nav {
  background: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.palette-mode-badge--action {
  background: rgba(168, 85, 247, 0.2);
  color: #d8b4fe;
  border: 1px solid rgba(168, 85, 247, 0.3);
}

.palette-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #fff;
  font-size: 1rem;
  padding: 0.2rem 0;
}

.palette-input::placeholder {
  color: rgba(255, 255, 255, 0.35);
}

.palette-clear {
  background: none;
  border: none;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.45);
  display: flex;
  align-items: center;
  border-radius: 4px;
  padding: 2px;
  transition: color 0.15s;
}

.palette-clear:hover {
  color: rgba(255, 255, 255, 0.85);
}

.palette-esc-hint {
  font-size: 0.68rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 4px;
  padding: 1px 6px;
  color: rgba(255, 255, 255, 0.45);
  white-space: nowrap;
  font-family: inherit;
}

/* ── Mode hints row ── */
.palette-mode-hints {
  display: flex;
  gap: 1.25rem;
  padding: 0.45rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-shrink: 0;
}

.mode-hint {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.38);
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.mode-hint kbd {
  font-size: 0.68rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  padding: 0 5px;
  color: rgba(255, 255, 255, 0.55);
  font-family: inherit;
  line-height: 1.5;
}

/* ── Spinner ── */
.palette-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.12);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Results ── */
.palette-results {
  flex: 1;
  overflow-y: auto;
  padding: 0.4rem 0 0.4rem;
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.12) transparent;
}

.palette-results::-webkit-scrollbar {
  width: 5px;
}
.palette-results::-webkit-scrollbar-track {
  background: transparent;
}
.palette-results::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.12);
  border-radius: 3px;
}

.palette-empty {
  padding: 2rem 1.25rem;
  text-align: center;
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.9rem;
}

/* ── Section label ── */
.palette-section-label {
  padding: 0.55rem 1rem 0.25rem;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(59, 130, 246, 0.75);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.palette-section-label:first-child {
  border-top: none;
}

/* ── Item ── */
.palette-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  cursor: pointer;
  transition: background 0.1s;
  min-height: 42px;
  border-radius: 0;
}

.palette-item:hover,
.palette-item--active {
  background: rgba(59, 130, 246, 0.1);
}

.palette-item-icon {
  font-size: 1rem;
  flex-shrink: 0;
  width: 22px;
  text-align: center;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.palette-icon-recent {
  color: rgba(255, 255, 255, 0.4);
}

.palette-icon-nav {
  color: rgba(59, 130, 246, 0.7);
}

.palette-icon-action {
  color: rgba(168, 85, 247, 0.85);
}

.palette-item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.palette-item-label {
  font-size: 0.9rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.92);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.palette-item-desc {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.palette-item-path {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.35);
  margin-left: auto;
  flex-shrink: 0;
  font-family: monospace;
}

.palette-item-meta {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
}

/* ── Status dot ── */
.palette-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot--running  { background: #4ade80; box-shadow: 0 0 5px rgba(74,222,128,0.5); }
.dot--stopped  { background: #f87171; }
.dot--paused   { background: #fbbf24; }
.dot--unknown  { background: rgba(255, 255, 255, 0.3); }

/* ── Meta tags ── */
.meta-tag {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.55);
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  padding: 0 5px;
  line-height: 1.7;
}

.meta-tag--host {
  color: rgba(147, 197, 253, 0.85);
}

/* ── Status badge ── */
.palette-badge {
  font-size: 0.65rem;
  font-weight: 600;
  border-radius: 10px;
  padding: 2px 8px;
  white-space: nowrap;
  flex-shrink: 0;
  text-transform: capitalize;
}

.badge--running { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.badge--stopped { background: rgba(239, 68, 68, 0.12); color: #f87171; }
.badge--paused  { background: rgba(251, 191, 36, 0.12); color: #fbbf24; }
.badge--unknown { background: rgba(255, 255, 255, 0.08); color: rgba(255, 255, 255, 0.5); }
.badge--danger  { background: rgba(239, 68, 68, 0.15); color: #fca5a5; }

/* ── Keyboard shortcut hint ── */
.palette-shortcut {
  font-size: 0.65rem;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  padding: 1px 6px;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
  flex-shrink: 0;
  font-family: inherit;
}

/* ── Footer ── */
.palette-footer {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.5rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.38);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.palette-footer kbd {
  background: rgba(255, 255, 255, 0.09);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 3px;
  padding: 1px 5px;
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.5);
  font-family: inherit;
}

.palette-footer-sep {
  flex: 1;
}

.palette-footer-hint {
  color: rgba(255, 255, 255, 0.28);
  font-size: 0.67rem;
}

.palette-footer-hint kbd {
  color: rgba(255, 255, 255, 0.4);
}

/* ── Transitions ── */
.palette-fade-enter-active,
.palette-fade-leave-active {
  transition: opacity 0.18s ease;
}
.palette-fade-enter-from,
.palette-fade-leave-to {
  opacity: 0;
}

.palette-fade-enter-active .palette-modal,
.palette-fade-leave-active .palette-modal {
  transition: transform 0.18s cubic-bezier(0.34, 1.5, 0.64, 1), opacity 0.18s ease;
}
.palette-fade-enter-from .palette-modal,
.palette-fade-leave-to .palette-modal {
  transform: translateY(-14px) scale(0.97);
  opacity: 0;
}

/* ── Mobile ── */
@media (max-width: 640px) {
  .palette-backdrop {
    padding-top: 0;
    align-items: flex-end;
  }

  .palette-modal {
    width: 100vw;
    max-width: 100vw;
    border-radius: 16px 16px 0 0;
    max-height: 85vh;
  }

  .palette-mode-hints {
    display: none;
  }
}
</style>
