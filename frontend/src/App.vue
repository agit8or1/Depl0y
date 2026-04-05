<template>
  <div id="app" class="app-container">
    <!-- Overlay backdrop for mobile sidebar -->
    <transition name="fade">
      <div
        v-if="isAuthenticated && !isFullscreen && sidebarOpen && isMobile"
        class="sidebar-overlay"
        @click="sidebarOpen = false"
      />
    </transition>

    <Sidebar
      v-if="isAuthenticated && !isFullscreen"
      :is-open="sidebarOpen"
      @close="sidebarOpen = false"
    />
    <div class="main-content" :class="{ 'full-width': !isAuthenticated || isFullscreen }">
      <Header
        v-if="isAuthenticated && !isFullscreen"
        @toggle-sidebar="sidebarOpen = !sidebarOpen"
      />
      <main :class="isFullscreen ? 'content-fullscreen' : 'content'">
        <router-view />
      </main>
    </div>

    <!-- Global toast notifications -->
    <ToastContainer />

    <!-- Global: Command Palette (Ctrl+K) -->
    <CommandPalette v-if="isAuthenticated" />

    <!-- Global: Keyboard Shortcuts Help Modal (?) -->
    <transition name="fade">
      <div v-if="showShortcutsModal" class="shortcuts-backdrop" @click.self="showShortcutsModal = false">
        <div class="shortcuts-modal" role="dialog" aria-modal="true" aria-label="Keyboard Shortcuts">
          <div class="shortcuts-header">
            <h3 class="shortcuts-title">Keyboard Shortcuts</h3>
            <button class="shortcuts-close" @click="showShortcutsModal = false" aria-label="Close">&#x2715;</button>
          </div>
          <div class="shortcuts-grid">
            <div v-for="group in shortcutGroups" :key="group.label" class="shortcuts-group">
              <div class="shortcuts-group-label">{{ group.label }}</div>
              <div v-for="sc in group.shortcuts" :key="sc.keys" class="shortcuts-row">
                <div class="shortcuts-keys">
                  <kbd v-for="k in sc.keys.split('+')" :key="k">{{ k.trim() }}</kbd>
                </div>
                <span class="shortcuts-action">{{ sc.action }}</span>
              </div>
            </div>
          </div>
          <div class="shortcuts-footer">
            Press <kbd>Esc</kbd> or <kbd>?</kbd> to close
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useRoute, useRouter } from 'vue-router'
import Sidebar from '@/components/layout/Sidebar.vue'
import Header from '@/components/layout/Header.vue'
import CommandPalette from '@/components/CommandPalette.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const SHORTCUT_GROUPS = [
  {
    label: 'Global',
    shortcuts: [
      { keys: 'Ctrl + K', action: 'Open command palette' },
      { keys: '?',        action: 'Show keyboard shortcuts' },
      { keys: 'Esc',      action: 'Close palette / modal' },
    ]
  },
  {
    label: 'Navigation (press g, then key)',
    shortcuts: [
      { keys: 'g + d', action: 'Go to Dashboard' },
      { keys: 'g + v', action: 'Go to Virtual Machines' },
      { keys: 'g + t', action: 'Go to Tasks' },
      { keys: 'g + n', action: 'Go to Proxmox Hosts (Nodes)' },
      { keys: 'g + b', action: 'Go to Backup' },
      { keys: 'g + s', action: 'Go to Settings' },
    ]
  }
]

export default {
  name: 'App',
  components: {
    Sidebar,
    Header,
    CommandPalette,
    ToastContainer
  },
  setup() {
    const authStore = useAuthStore()
    const route = useRoute()
    const router = useRouter()

    const isAuthenticated = computed(() => authStore.isAuthenticated)
    const isFullscreen = computed(() => route.meta?.layout === 'fullscreen')

    const isMobile = ref(window.innerWidth <= 768)
    const sidebarOpen = ref(window.innerWidth > 768)
    const showShortcutsModal = ref(false)
    const shortcutGroups = SHORTCUT_GROUPS

    // ── g-chord state ────────────────────────────────────────────────────────
    let gChordPending = false
    let gChordTimer = null

    const gChordRoutes = {
      d: '/',
      v: '/vms',
      t: '/tasks',
      n: '/proxmox',
      b: '/backup',
      s: '/settings'
    }

    // ── Theme helpers ─────────────────────────────────────────────────────────
    const applyTheme = (theme) => {
      const root = document.documentElement
      if (theme === 'system') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
        root.setAttribute('data-theme', prefersDark ? 'dark' : 'light')
      } else {
        root.setAttribute('data-theme', theme)
      }
    }

    // ── Global keyboard handler ───────────────────────────────────────────────
    const onGlobalKeydown = (e) => {
      // Ignore when typing in an input / textarea / contenteditable
      const tag = document.activeElement?.tagName?.toLowerCase()
      const isEditing = tag === 'input' || tag === 'textarea' || tag === 'select' ||
                        document.activeElement?.isContentEditable

      // Ctrl+K / Cmd+K — handled by CommandPalette itself, skip here
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') return

      // Escape — close shortcuts modal
      if (e.key === 'Escape') {
        if (showShortcutsModal.value) {
          showShortcutsModal.value = false
          return
        }
      }

      // Skip shortcuts when in inputs (except Escape above)
      if (isEditing) {
        // Reset g-chord if user starts typing in an input
        gChordPending = false
        clearTimeout(gChordTimer)
        return
      }

      // ? — show shortcuts modal (when not editing, not in palette)
      if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        showShortcutsModal.value = !showShortcutsModal.value
        return
      }

      // g-chord: first press 'g', then a second key within 500ms
      if (gChordPending) {
        clearTimeout(gChordTimer)
        gChordPending = false
        const dest = gChordRoutes[e.key]
        if (dest) {
          e.preventDefault()
          router.push(dest)
        }
        return
      }

      if (e.key === 'g' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        gChordPending = true
        gChordTimer = setTimeout(() => { gChordPending = false }, 500)
      }
    }

    const handleResize = () => {
      const mobile = window.innerWidth <= 768
      isMobile.value = mobile
      if (!mobile) sidebarOpen.value = true
    }

    onMounted(() => {
      window.addEventListener('resize', handleResize)
      window.addEventListener('keydown', onGlobalKeydown)
      applyTheme(localStorage.getItem('depl0y_theme') || 'light')
    })

    onBeforeUnmount(() => {
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('keydown', onGlobalKeydown)
      clearTimeout(gChordTimer)
    })

    return {
      isAuthenticated,
      isFullscreen,
      sidebarOpen,
      isMobile,
      showShortcutsModal,
      shortcutGroups
    }
  }
}
</script>

<style scoped>
.app-container {
  display: flex;
  min-height: 100vh;
  background-color: var(--background);
}

.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 150;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: var(--sidebar-width);
  min-width: 0;
  transition: margin-left 0.3s ease;
}

.main-content.full-width {
  margin-left: 0;
}

.content {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
  overflow-x: hidden;
}

.content-fullscreen {
  flex: 1;
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ── Shortcuts modal ── */
.shortcuts-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(3px);
  z-index: 9998;
  display: flex;
  align-items: center;
  justify-content: center;
}

.shortcuts-modal {
  background: #1a2332;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.65);
  width: 540px;
  max-width: calc(100vw - 2rem);
  max-height: 80vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.shortcuts-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.shortcuts-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.shortcuts-close {
  background: none;
  border: none;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.55);
  font-size: 1.1rem;
  line-height: 1;
  border-radius: 4px;
  padding: 4px 6px;
  transition: color 0.15s, background 0.15s;
}

.shortcuts-close:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}

.shortcuts-grid {
  padding: 1rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.shortcuts-group-label {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(59, 130, 246, 0.8);
  margin-bottom: 0.5rem;
}

.shortcuts-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.3rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.shortcuts-row:last-child {
  border-bottom: none;
}

.shortcuts-keys {
  display: flex;
  gap: 0.2rem;
  flex-shrink: 0;
  min-width: 140px;
}

.shortcuts-keys kbd {
  font-size: 0.75rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 5px;
  padding: 2px 8px;
  color: rgba(255, 255, 255, 0.8);
  font-family: inherit;
  white-space: nowrap;
}

.shortcuts-action {
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.75);
}

.shortcuts-footer {
  padding: 0.75rem 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  text-align: center;
  flex-shrink: 0;
}

.shortcuts-footer kbd {
  font-size: 0.7rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 4px;
  padding: 1px 5px;
  color: rgba(255, 255, 255, 0.55);
  font-family: inherit;
}

@media (max-width: 768px) {
  .main-content {
    margin-left: 0;
  }

  .content {
    padding: 1rem;
  }

  .shortcuts-keys {
    min-width: 110px;
  }
}
</style>
