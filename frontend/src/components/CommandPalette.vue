<template>
  <teleport to="body">
    <transition name="palette-fade">
      <div v-if="isOpen" class="palette-backdrop" @mousedown.self="close">
        <div class="palette-modal" role="dialog" aria-modal="true" aria-label="Command Palette">

          <!-- Search input -->
          <div class="palette-input-row">
            <svg class="palette-search-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              ref="inputRef"
              v-model="query"
              class="palette-input"
              type="text"
              placeholder="Search VMs, nodes, or run a command..."
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

          <!-- Results -->
          <div class="palette-results" ref="resultsRef">
            <template v-if="sections.length === 0 && query.length >= 1">
              <div class="palette-empty">No results for "{{ query }}"</div>
            </template>

            <template v-if="sections.length === 0 && query.length === 0">
              <!-- Show all actions when no query -->
              <div class="palette-section-label">Actions</div>
              <div
                v-for="(action, idx) in allActions"
                :key="action.id"
                class="palette-item"
                :class="{ 'palette-item--active': flatActiveIndex === idx }"
                @mouseenter="flatActiveIndex = idx"
                @mousedown.prevent="executeItem(action)"
              >
                <span class="palette-item-icon">{{ action.icon }}</span>
                <span class="palette-item-label">{{ action.label }}</span>
                <kbd v-if="action.shortcut" class="palette-shortcut">{{ action.shortcut }}</kbd>
              </div>
            </template>

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
                  <span class="palette-item-icon">&#127760;</span>
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

                <!-- Action / Nav item -->
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
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useClusterStore } from '@/store/cluster'

const ALL_ACTIONS = [
  { id: 'create-vm',      label: 'Create VM',           icon: '➕', route: '/create-pve-vm', shortcut: null },
  { id: 'create-lxc',     label: 'Create LXC',          icon: '📦', route: '/create-lxc', shortcut: null },
  { id: 'deploy-vm',      label: 'Deploy VM',           icon: '🚀', route: '/deploy', shortcut: null },
  { id: 'dashboard',      label: 'View Dashboard',      icon: '📊', route: '/', shortcut: 'g d' },
  { id: 'tasks',          label: 'View Tasks',          icon: '📋', route: '/tasks', shortcut: 'g t' },
  { id: 'api-explorer',   label: 'Open API Explorer',   icon: '⚡', route: '/api-explorer', shortcut: null },
  { id: 'system-health',  label: 'View System Health',  icon: '💚', route: '/system-health', shortcut: null },
  { id: 'toggle-theme',   label: 'Toggle Dark/Light Theme', icon: '🌓', action: 'toggleTheme', shortcut: null },
]

const NAV_LINKS = [
  { id: 'nav-datacenter',    label: 'Go to Datacenter',       icon: '🏢', route: '/datacenter' },
  { id: 'nav-vms',           label: 'Go to Virtual Machines', icon: '🖥️', route: '/vms', shortcut: 'g v' },
  { id: 'nav-containers',    label: 'Go to Containers',       icon: '📦', route: '/containers' },
  { id: 'nav-proxmox',       label: 'Go to Proxmox Hosts',    icon: '🌐', route: '/proxmox', shortcut: 'g n' },
  { id: 'nav-backup',        label: 'Go to Backup',           icon: '💾', route: '/backup', shortcut: 'g b' },
  { id: 'nav-images',        label: 'Go to Images',           icon: '💿', route: '/images' },
  { id: 'nav-settings',      label: 'Go to Settings',         icon: '⚙️', route: '/settings', shortcut: 'g s' },
  { id: 'nav-users',         label: 'Go to Users',            icon: '👥', route: '/users' },
  { id: 'nav-audit',         label: 'Go to Audit Log',        icon: '🔍', route: '/audit-log' },
  { id: 'nav-network',       label: 'Go to Network',          icon: '🔌', route: '/network' },
  { id: 'nav-security',      label: 'Go to Security',         icon: '🔒', route: '/security' },
  { id: 'nav-templates',     label: 'Go to Templates',        icon: '📄', route: '/templates' },
]

const ALL_PALETTE_ITEMS = [...ALL_ACTIONS, ...NAV_LINKS]

function fuzzyMatch(str, term) {
  const s = str.toLowerCase()
  const t = term.toLowerCase()
  if (s.includes(t)) return true
  // simple sequential char match for fuzzy
  let si = 0
  for (let i = 0; i < t.length; i++) {
    const idx = s.indexOf(t[i], si)
    if (idx === -1) return false
    si = idx + 1
  }
  return true
}

export default {
  name: 'CommandPalette',
  setup() {
    const router = useRouter()
    const clusterStore = useClusterStore()

    const isOpen = ref(false)
    const query = ref('')
    const loading = ref(false)
    const flatActiveIndex = ref(0)
    const inputRef = ref(null)
    const resultsRef = ref(null)

    // ── Open / Close ──────────────────────────────────────────────────────────
    const open = async () => {
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
      const q = query.value.trim()
      if (!q) return []

      const result = []
      let flatIdx = 0

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
        .filter(n => {
          const name = (n.node || n.name || n.id || '').toLowerCase()
          return fuzzyMatch(name, q)
        })
        .slice(0, 5)
        .map(n => ({ ...n, _sectionType: 'nodes', _flatIdx: flatIdx++ }))

      if (matchedNodes.length) result.push({ type: 'nodes', label: 'Nodes', items: matchedNodes })

      // Actions
      const matchedActions = ALL_PALETTE_ITEMS
        .filter(a => fuzzyMatch(a.label, q))
        .slice(0, 6)
        .map(a => ({ ...a, _sectionType: 'action', _flatIdx: flatIdx++ }))

      if (matchedActions.length) result.push({ type: 'actions', label: 'Actions & Navigation', items: matchedActions })

      return result
    })

    // Flat total for keyboard nav
    const flatTotal = computed(() => {
      if (query.value.trim() === '') return allActions.value.length
      return sections.value.reduce((sum, s) => sum + s.items.length, 0)
    })

    const allActions = computed(() => ALL_PALETTE_ITEMS.map((a, i) => ({ ...a, _flatIdx: i })))

    // ── Execute item ──────────────────────────────────────────────────────────
    const executeItem = (item) => {
      if (item.action === 'toggleTheme') {
        toggleTheme()
      } else if (item.route) {
        router.push(item.route)
      } else if (item._sectionType === 'vms') {
        router.push(`/proxmox/${item._hostId}/nodes/${item.node}/vms/${item.vmid}`)
      } else if (item._sectionType === 'lxc') {
        router.push(`/proxmox/${item._hostId}/nodes/${item.node}/containers/${item.vmid}`)
      } else if (item._sectionType === 'nodes') {
        router.push(`/proxmox/${item._hostId}/nodes/${item.node}`)
      }
      close()
    }

    const toggleTheme = () => {
      const root = document.documentElement
      const current = root.getAttribute('data-theme') || 'light'
      const next = current === 'light' ? 'dark' : 'light'
      root.setAttribute('data-theme', next)
      localStorage.setItem('depl0y_theme', next)
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
        flatActiveIndex.value = (flatActiveIndex.value + 1) % total
        scrollActiveIntoView()
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        flatActiveIndex.value = (flatActiveIndex.value - 1 + total) % total
        scrollActiveIntoView()
      } else if (e.key === 'Enter') {
        e.preventDefault()
        const idx = flatActiveIndex.value
        if (query.value.trim() === '') {
          // no query — from allActions list
          const item = allActions.value[idx]
          if (item) executeItem(item)
        } else {
          // find across sections
          for (const section of sections.value) {
            const item = section.items.find(i => i._flatIdx === idx)
            if (item) { executeItem(item); break }
          }
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
      allActions,
      open,
      close,
      onKeydown,
      executeItem,
      statusDotClass,
      statusBadgeClass
    }
  }
}
</script>

<style scoped>
/* ── Backdrop ── */
.palette-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(3px);
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
}

/* ── Modal ── */
.palette-modal {
  width: 600px;
  max-width: calc(100vw - 2rem);
  background: #1a2332;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  max-height: 70vh;
}

/* ── Input row ── */
.palette-input-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.palette-search-icon {
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
}

.palette-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #fff;
  font-size: 1rem;
  padding: 0.25rem 0;
}

.palette-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.palette-clear {
  background: none;
  border: none;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.5);
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
  font-size: 0.7rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  padding: 1px 6px;
  color: rgba(255, 255, 255, 0.55);
  white-space: nowrap;
}

/* ── Spinner ── */
.palette-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.15);
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
  padding: 0.5rem 0;
}

.palette-empty {
  padding: 2rem 1.25rem;
  text-align: center;
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.9rem;
}

/* ── Section label ── */
.palette-section-label {
  padding: 0.5rem 1rem 0.3rem;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(59, 130, 246, 0.8);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
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
  min-height: 44px;
}

.palette-item:hover,
.palette-item--active {
  background: rgba(59, 130, 246, 0.12);
}

.palette-item-icon {
  font-size: 1.1rem;
  flex-shrink: 0;
  width: 24px;
  text-align: center;
  line-height: 1;
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
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

.dot--running  { background: #4ade80; }
.dot--stopped  { background: #f87171; }
.dot--paused   { background: #fbbf24; }
.dot--unknown  { background: rgba(255, 255, 255, 0.35); }

/* ── Meta tags ── */
.meta-tag {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.09);
  border-radius: 4px;
  padding: 0 5px;
  line-height: 1.7;
}

.meta-tag--host {
  color: rgba(147, 197, 253, 0.9);
}

/* ── Status badge ── */
.palette-badge {
  font-size: 0.68rem;
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
.badge--unknown { background: rgba(255, 255, 255, 0.09); color: rgba(255, 255, 255, 0.6); }

/* ── Keyboard shortcut hint ── */
.palette-shortcut {
  font-size: 0.68rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 4px;
  padding: 1px 6px;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
  flex-shrink: 0;
  font-family: inherit;
}

/* ── Footer ── */
.palette-footer {
  display: flex;
  gap: 1.25rem;
  padding: 0.5rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.45);
  flex-shrink: 0;
}

.palette-footer kbd {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  padding: 1px 5px;
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.6);
  font-family: inherit;
}

/* ── Transitions ── */
.palette-fade-enter-active,
.palette-fade-leave-active {
  transition: opacity 0.15s ease;
}
.palette-fade-enter-from,
.palette-fade-leave-to {
  opacity: 0;
}

.palette-fade-enter-active .palette-modal,
.palette-fade-leave-active .palette-modal {
  transition: transform 0.15s ease, opacity 0.15s ease;
}
.palette-fade-enter-from .palette-modal,
.palette-fade-leave-to .palette-modal {
  transform: translateY(-12px) scale(0.97);
  opacity: 0;
}
</style>
