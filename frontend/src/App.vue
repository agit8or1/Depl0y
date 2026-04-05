<template>
  <div id="app" class="app-container">

    <!-- Skip-to-content for keyboard users -->
    <a href="#main-content" class="skip-to-content">Skip to content</a>

    <!-- Page-level loading progress bar -->
    <div class="page-loading-bar" :class="{ 'page-loading-bar--active': pageLoading, 'page-loading-bar--done': pageLoadDone }"></div>

    <!-- Offline banner -->
    <transition name="slide-down">
      <div v-if="isOffline" class="offline-banner" role="alert">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.56 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>
        You are offline — some features may not work
      </div>
    </transition>

    <!-- Error boundary display -->
    <transition name="fade">
      <div v-if="appError" class="error-boundary-backdrop">
        <div class="error-boundary-box">
          <div class="error-boundary-icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
          <h3 class="error-boundary-title">An unexpected error occurred</h3>
          <p class="error-boundary-component" v-if="appError.component">
            In component: <code>{{ appError.component }}</code>
          </p>
          <p class="error-boundary-message">{{ appError.message }}</p>
          <details v-if="isDev && appError.stack" class="error-boundary-details">
            <summary>Stack trace</summary>
            <pre class="error-boundary-stack">{{ appError.stack }}</pre>
          </details>
          <div class="error-boundary-actions">
            <button class="btn btn-primary" @click="clearError">Dismiss</button>
            <button class="btn btn-outline" @click="reloadPage">Reload Page</button>
          </div>
        </div>
      </div>
    </transition>

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
    <div
      class="main-content"
      :class="{ 'full-width': !isAuthenticated || isFullscreen }"
      @touchstart.passive="onSwipeTouchStart"
      @touchmove.passive="onSwipeTouchMove"
      @touchend.passive="onSwipeTouchEnd"
    >
      <Header
        v-if="isAuthenticated && !isFullscreen"
        @toggle-sidebar="sidebarOpen = !sidebarOpen"
      />
      <main id="main-content" :class="isFullscreen ? 'content-fullscreen' : 'content'">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- Bottom navigation bar (mobile only) -->
    <nav v-if="isAuthenticated && !isFullscreen" class="bottom-nav" aria-label="Mobile navigation">
      <router-link to="/" class="bottom-nav-item" exact-active-class="bottom-nav-item--active">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
        <span>Dashboard</span>
      </router-link>
      <router-link to="/vms" class="bottom-nav-item" active-class="bottom-nav-item--active">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><polyline points="8 21 12 17 16 21"/></svg>
        <span>VMs</span>
      </router-link>
      <router-link to="/proxmox" class="bottom-nav-item" active-class="bottom-nav-item--active">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
        <span>Nodes</span>
      </router-link>
      <router-link to="/tasks" class="bottom-nav-item" active-class="bottom-nav-item--active">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
        <span>Tasks</span>
      </router-link>
      <router-link to="/settings" class="bottom-nav-item" active-class="bottom-nav-item--active">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        <span>Settings</span>
      </router-link>
    </nav>

    <!-- Global toast notifications -->
    <ToastContainer />

    <!-- Global: Command Palette (Ctrl+K) -->
    <CommandPalette v-if="isAuthenticated" />

    <!-- Global: Task progress bar (bottom-right, when tasks running) -->
    <GlobalTaskBar />

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
import { computed, ref, onMounted, onBeforeUnmount, getCurrentInstance } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useRoute, useRouter } from 'vue-router'
import Sidebar from '@/components/layout/Sidebar.vue'
import Header from '@/components/layout/Header.vue'
import CommandPalette from '@/components/CommandPalette.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import GlobalTaskBar from '@/components/GlobalTaskBar.vue'

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
    ToastContainer,
    GlobalTaskBar,
  },
  setup() {
    const authStore = useAuthStore()
    const route = useRoute()
    const router = useRouter()
    const instance = getCurrentInstance()

    const isAuthenticated = computed(() => authStore.isAuthenticated)
    const isFullscreen = computed(() => route.meta?.layout === 'fullscreen')
    const isDev = import.meta.env.DEV

    const isMobile = ref(window.innerWidth <= 768)
    const sidebarOpen = ref(window.innerWidth > 768)
    const showShortcutsModal = ref(false)
    const shortcutGroups = SHORTCUT_GROUPS

    // ── Page loading bar ──────────────────────────────────────────────────────
    const pageLoading = ref(false)
    const pageLoadDone = ref(false)
    let doneTimer = null

    router.beforeEach(() => {
      pageLoadDone.value = false
      pageLoading.value = true
      clearTimeout(doneTimer)
    })

    router.afterEach(() => {
      pageLoading.value = false
      pageLoadDone.value = true
      doneTimer = setTimeout(() => { pageLoadDone.value = false }, 500)
    })

    // ── Offline detection ─────────────────────────────────────────────────────
    const isOffline = ref(!navigator.onLine)
    const onOnline = () => { isOffline.value = false }
    const onOffline = () => { isOffline.value = true }

    // ── Error boundary ────────────────────────────────────────────────────────
    const appError = ref(null)

    const clearError = () => { appError.value = null }
    const reloadPage = () => { window.location.reload() }

    if (instance?.appContext?.app) {
      instance.appContext.app.config.errorHandler = (err, vm, info) => {
        console.error('[Vue Error]', err)
        appError.value = {
          message: err?.message || String(err),
          stack: err?.stack || null,
          component: vm?.$options?.name || vm?.__name || null,
          info,
        }
      }
    }

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

    // ── Appearance: apply all stored settings ─────────────────────────────────
    const applyAppearanceSettings = () => {
      const root = document.documentElement

      // Accent color
      const accentColor = localStorage.getItem('depl0y_accent_color')
      if (accentColor) {
        root.style.setProperty('--accent-color', accentColor)
        // Derive a slightly darker hover shade
        root.style.setProperty('--accent-hover', accentColor)
      }

      // Font size
      const fontSize = localStorage.getItem('depl0y_font_size') || 'medium'
      root.setAttribute('data-font-size', fontSize)
      const fontSizeMap = { small: '12px', medium: '14px', large: '16px' }
      root.style.setProperty('--font-size-base', fontSizeMap[fontSize] || '14px')

      // Sidebar width
      const sidebarWidth = localStorage.getItem('depl0y_sidebar_width')
      if (sidebarWidth) {
        root.style.setProperty('--sidebar-width', sidebarWidth + 'px')
      }

      // Sidebar compact mode
      const sidebarCompact = localStorage.getItem('depl0y_sidebar_compact') === 'true'
      root.setAttribute('data-sidebar-compact', String(sidebarCompact))

      // Table density
      const density = localStorage.getItem('depl0y_table_density') || 'comfortable'
      root.setAttribute('data-density', density)
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

    // ── Swipe-to-open sidebar ─────────────────────────────────────────────────
    let swipeStartX = 0
    let swipeStartY = 0
    const SWIPE_THRESHOLD = 60   // px horizontal travel needed
    const SWIPE_EDGE = 30        // px from left edge to trigger open gesture

    const onSwipeTouchStart = (e) => {
      const touch = e.touches[0]
      swipeStartX = touch.clientX
      swipeStartY = touch.clientY
    }

    const onSwipeTouchMove = () => {
      // intentionally left empty — tracking handled in touchend
    }

    const onSwipeTouchEnd = (e) => {
      if (!isMobile.value) return
      const touch = e.changedTouches[0]
      const dx = touch.clientX - swipeStartX
      const dy = touch.clientY - swipeStartY

      // Ignore mostly-vertical swipes
      if (Math.abs(dy) > Math.abs(dx)) return

      if (!sidebarOpen.value && dx > SWIPE_THRESHOLD && swipeStartX <= SWIPE_EDGE) {
        // Swipe right from left edge → open sidebar
        sidebarOpen.value = true
      } else if (sidebarOpen.value && dx < -SWIPE_THRESHOLD) {
        // Swipe left → close sidebar
        sidebarOpen.value = false
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
      window.addEventListener('online', onOnline)
      window.addEventListener('offline', onOffline)
      applyTheme(localStorage.getItem('depl0y_theme') || 'dark')
      applyAppearanceSettings()
    })

    onBeforeUnmount(() => {
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('keydown', onGlobalKeydown)
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
      clearTimeout(gChordTimer)
      clearTimeout(doneTimer)
    })

    return {
      isAuthenticated,
      isFullscreen,
      sidebarOpen,
      isMobile,
      showShortcutsModal,
      shortcutGroups,
      pageLoading,
      pageLoadDone,
      isOffline,
      appError,
      clearError,
      reloadPage,
      isDev,
      onSwipeTouchStart,
      onSwipeTouchMove,
      onSwipeTouchEnd,
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
  color: rgba(255, 255, 255, 0.75);
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
  color: rgba(59, 130, 246, 0.95);
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
  color: rgba(255, 255, 255, 0.65);
  text-align: center;
  flex-shrink: 0;
}

.shortcuts-footer kbd {
  font-size: 0.7rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 4px;
  padding: 1px 5px;
  color: rgba(255, 255, 255, 0.75);
  font-family: inherit;
}

@media (max-width: 768px) {
  .main-content {
    margin-left: 0;
  }

  .content {
    padding: 1rem;
    padding-bottom: 5rem; /* space for bottom nav */
  }

  .shortcuts-keys {
    min-width: 110px;
  }

  /* Shortcuts modal: full-screen friendly on mobile */
  .shortcuts-modal {
    width: calc(100vw - 1.5rem);
    max-height: 88vh;
    border-radius: 10px;
  }
}

/* ── Bottom navigation bar ── */
.bottom-nav {
  display: none; /* hidden on desktop */
}

@media (max-width: 768px) {
  .bottom-nav {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60px;
    background: var(--surface);
    border-top: 1px solid var(--border-color);
    box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.12);
    z-index: 120;
    padding-bottom: env(safe-area-inset-bottom, 0);
  }

  .bottom-nav-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    text-decoration: none;
    color: var(--text-muted);
    font-size: 0.65rem;
    font-weight: 500;
    padding: 6px 4px 4px;
    min-height: 44px;
    transition: color 0.15s;
    position: relative;
  }

  .bottom-nav-item svg {
    flex-shrink: 0;
  }

  .bottom-nav-item:hover {
    color: var(--primary-color);
  }

  .bottom-nav-item--active {
    color: var(--primary-color);
  }

  /* Active indicator: top underline */
  .bottom-nav-item--active::after {
    content: '';
    position: absolute;
    top: 0;
    left: 20%;
    right: 20%;
    height: 3px;
    background: var(--primary-color);
    border-radius: 0 0 3px 3px;
  }
}

/* ── Page transitions ── */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateX(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}

/* ── Page loading bar ── */
.page-loading-bar {
  position: fixed;
  top: 0;
  left: 0;
  height: 3px;
  width: 0%;
  background: linear-gradient(90deg, var(--primary-color), #60a5fa);
  z-index: 9999;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s ease;
  border-radius: 0 2px 2px 0;
  box-shadow: 0 0 8px rgba(59,130,246,0.6);
}

.page-loading-bar--active {
  opacity: 1;
  animation: page-loading-grow 2s ease-out forwards;
}

.page-loading-bar--done {
  width: 100% !important;
  opacity: 1;
  transition: width 0.15s ease, opacity 0.35s ease 0.1s;
}

@keyframes page-loading-grow {
  0%   { width: 0%; }
  20%  { width: 40%; }
  50%  { width: 65%; }
  80%  { width: 80%; }
  100% { width: 88%; }
}

/* ── Offline banner ── */
.offline-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9998;
  background: #1c1917;
  color: #fef3c7;
  padding: 0.55rem 1.25rem;
  font-size: 0.82rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  letter-spacing: 0.01em;
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.slide-down-enter-from,
.slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}

/* ── Error boundary ── */
.error-boundary-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.65);
  backdrop-filter: blur(4px);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.error-boundary-box {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  box-shadow: 0 24px 80px rgba(0,0,0,0.5);
  padding: 2rem;
  width: 100%;
  max-width: 520px;
  max-height: 80vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.error-boundary-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 68px;
  height: 68px;
  background: rgba(239,68,68,0.1);
  border-radius: 50%;
}

.error-boundary-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  text-align: center;
}

.error-boundary-component {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin: 0;
  text-align: center;
}

.error-boundary-component code {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 1px 6px;
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--primary-color);
}

.error-boundary-message {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
  text-align: center;
  word-break: break-word;
}

.error-boundary-details {
  width: 100%;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.error-boundary-details summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 0.25rem 0;
  user-select: none;
}

.error-boundary-stack {
  margin-top: 0.5rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 0.75rem;
  font-family: monospace;
  font-size: 0.72rem;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}

.error-boundary-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: center;
  flex-wrap: wrap;
}
</style>
