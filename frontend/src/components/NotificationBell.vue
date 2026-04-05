<template>
  <div class="notification-bell" ref="bellRef">
    <!-- Bell trigger button -->
    <button
      class="bell-btn"
      :class="{ active: open, has-unread: unreadCount > 0 }"
      :title="`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''} — Press N`"
      @click="toggle"
      @keydown.escape="close"
    >
      <svg class="bell-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
      </svg>
      <!-- Badge — always rendered, hidden when 0 -->
      <span
        class="bell-badge"
        :class="{ visible: unreadCount > 0, pulse: unreadCount > 0 }"
        aria-label="unread notifications"
      >
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </span>
    </button>

    <!-- Dropdown -->
    <Transition name="dropdown">
      <div v-if="open" class="bell-dropdown" @keydown.escape="close">
        <!-- Dropdown header -->
        <div class="dropdown-header">
          <span class="dropdown-title">Notifications</span>
          <div class="header-actions">
            <button
              v-if="unreadCount > 0"
              class="hdr-btn"
              :disabled="markingAll"
              @click="markAllRead"
              title="Mark all as read"
            >
              {{ markingAll ? '...' : 'Mark all read' }}
            </button>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="dropdown-loading">
          <div class="mini-spinner"></div>
          Loading...
        </div>

        <!-- Empty state -->
        <div v-else-if="notifications.length === 0" class="dropdown-empty">
          <svg class="empty-bell-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
          </svg>
          <p>All caught up!</p>
        </div>

        <!-- Notification items -->
        <div v-else class="dropdown-list">
          <div
            v-for="notif in notifications.slice(0, 8)"
            :key="notif.id"
            class="dropdown-item"
            :class="[`type-${notif.type}`, { unread: !notif.read }]"
            @click="onItemClick(notif)"
          >
            <!-- Type dot -->
            <span class="type-dot" :class="`dot-${notif.type}`"></span>

            <div class="item-content">
              <div class="item-title">{{ notif.title }}</div>
              <div class="item-message">{{ truncate(notif.message, 80) }}</div>
              <div class="item-time">{{ formatRelative(notif.created_at) }}</div>
            </div>

            <span v-if="!notif.read" class="unread-indicator" title="Unread"></span>
          </div>

          <!-- "and N more" hint -->
          <div v-if="notifications.length > 8" class="more-hint">
            +{{ notifications.length - 8 }} more in notification center
          </div>
        </div>

        <!-- Footer -->
        <div class="dropdown-footer">
          <router-link class="view-all-link" to="/notifications" @click="close">
            <svg viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd"/>
            </svg>
            View all notifications
          </router-link>
          <span class="footer-shortcut" title="Press N anywhere to open notifications">
            <kbd>N</kbd>
          </span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'NotificationBell',
  setup() {
    const toast = useToast()
    const router = useRouter()

    const open = ref(false)
    const notifications = ref([])
    const loading = ref(false)
    const markingAll = ref(false)
    const bellRef = ref(null)

    const unreadCount = computed(() => notifications.value.filter(n => !n.read).length)

    // ── Load ────────────────────────────────────────────────────────────────
    const load = async () => {
      loading.value = true
      try {
        const r = await api.notifications.list()
        notifications.value = r.data || []
      } catch {
        // silent
      } finally {
        loading.value = false
      }
    }

    // ── Actions ─────────────────────────────────────────────────────────────
    const toggle = () => {
      open.value = !open.value
      if (open.value) load()
    }

    const close = () => {
      open.value = false
    }

    const onItemClick = async (notif) => {
      if (!notif.read) {
        try {
          await api.notifications.markRead({ ids: [notif.id] })
          notif.read = true
        } catch {
          // silent
        }
      }
      if (notif.action_url) {
        if (notif.action_url.startsWith('/')) {
          router.push(notif.action_url)
        } else {
          window.open(notif.action_url, '_blank', 'noopener')
        }
      }
      close()
    }

    const markAllRead = async () => {
      markingAll.value = true
      try {
        await api.notifications.markRead({ all: true })
        notifications.value.forEach(n => { n.read = true })
      } catch {
        toast.error('Failed to mark notifications read')
      } finally {
        markingAll.value = false
      }
    }

    // ── Keyboard shortcut: N to toggle ──────────────────────────────────────
    const onKeydown = (e) => {
      // Don't trigger when typing in an input
      const tag = document.activeElement?.tagName?.toLowerCase()
      if (['input', 'textarea', 'select'].includes(tag)) return
      if (e.key === 'n' || e.key === 'N') {
        e.preventDefault()
        toggle()
      }
      if (e.key === 'Escape' && open.value) {
        close()
      }
    }

    // ── Click-outside to close ───────────────────────────────────────────────
    const onClickOutside = (e) => {
      if (bellRef.value && !bellRef.value.contains(e.target)) {
        close()
      }
    }

    // ── Formatters ────────────────────────────────────────────────────────────
    const formatRelative = (iso) => {
      if (!iso) return ''
      const diff = Date.now() - new Date(iso).getTime()
      const secs = Math.floor(diff / 1000)
      if (secs < 60) return 'Just now'
      const mins = Math.floor(secs / 60)
      if (mins < 60) return `${mins}m ago`
      const hrs = Math.floor(mins / 60)
      if (hrs < 24) return `${hrs}h ago`
      const days = Math.floor(hrs / 24)
      if (days < 7) return `${days}d ago`
      return new Date(iso).toLocaleDateString()
    }

    const truncate = (text, max) => {
      if (!text) return ''
      return text.length > max ? text.slice(0, max) + '…' : text
    }

    onMounted(() => {
      document.addEventListener('keydown', onKeydown)
      document.addEventListener('mousedown', onClickOutside)
      // Initial silent load for badge count
      load()
    })

    onBeforeUnmount(() => {
      document.removeEventListener('keydown', onKeydown)
      document.removeEventListener('mousedown', onClickOutside)
    })

    return {
      open,
      notifications,
      loading,
      markingAll,
      unreadCount,
      bellRef,
      toggle,
      close,
      onItemClick,
      markAllRead,
      formatRelative,
      truncate,
    }
  }
}
</script>

<style scoped>
.notification-bell {
  position: relative;
  display: inline-flex;
}

/* ── Bell button ── */
.bell-btn {
  position: relative;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.4rem;
  border-radius: 0.5rem;
  color: var(--text-muted, #6b7280);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
}

.bell-btn:hover,
.bell-btn.active {
  background: var(--btn-secondary-hover, #f3f4f6);
  color: var(--text-primary, #111827);
}

.bell-icon {
  width: 1.375rem;
  height: 1.375rem;
  display: block;
}

/* ── Badge ── */
.bell-badge {
  position: absolute;
  top: 0;
  right: 0;
  min-width: 1.1rem;
  height: 1.1rem;
  background: #ef4444;
  color: #fff;
  border-radius: 999px;
  font-size: 0.6rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.2rem;
  border: 2px solid var(--nav-bg, #fff);
  opacity: 0;
  transform: scale(0.6);
  transition: opacity 0.2s, transform 0.2s;
  pointer-events: none;
}

.bell-badge.visible {
  opacity: 1;
  transform: scale(1);
}

.bell-badge.pulse {
  animation: badge-pulse 2s ease-in-out infinite;
}

@keyframes badge-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
  50% { box-shadow: 0 0 0 4px rgba(239, 68, 68, 0); }
}

/* ── Dropdown ── */
.bell-dropdown {
  position: absolute;
  top: calc(100% + 0.5rem);
  right: 0;
  width: 340px;
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.75rem;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.12);
  z-index: 1000;
  overflow: hidden;
}

/* Transition */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.97);
}

/* Header */
.dropdown-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}

.dropdown-title {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--text-primary, #111827);
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.hdr-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.75rem;
  color: #3b82f6;
  padding: 0.1rem 0.3rem;
  border-radius: 0.25rem;
  transition: background 0.15s;
}

.hdr-btn:hover:not(:disabled) {
  background: #eff6ff;
}

.hdr-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Loading */
.dropdown-loading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1.5rem;
  justify-content: center;
  font-size: 0.8rem;
  color: var(--text-muted, #9ca3af);
}

.mini-spinner {
  width: 1rem;
  height: 1rem;
  border: 2px solid var(--border-color, #e5e7eb);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Empty */
.dropdown-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2rem;
  color: var(--text-muted, #9ca3af);
  font-size: 0.8rem;
}

.empty-bell-icon {
  width: 2.5rem;
  height: 2.5rem;
  opacity: 0.3;
}

.dropdown-empty p {
  margin: 0;
}

/* List */
.dropdown-list {
  max-height: 340px;
  overflow-y: auto;
}

.dropdown-item {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
  padding: 0.625rem 1rem;
  cursor: pointer;
  transition: background 0.1s;
  position: relative;
}

.dropdown-item:hover {
  background: var(--hover-bg, #f9fafb);
}

.dropdown-item.unread {
  background: var(--unread-bg, #eff6ff);
}

.dropdown-item.unread:hover {
  background: #dbeafe;
}

.type-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 0.35rem;
}

.dot-info    { background: #3b82f6; }
.dot-warning { background: #f59e0b; }
.dot-error   { background: #ef4444; }
.dot-success { background: #10b981; }

.item-content {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary, #111827);
  margin-bottom: 0.15rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-message {
  font-size: 0.75rem;
  color: var(--text-secondary, #6b7280);
  line-height: 1.4;
  margin-bottom: 0.2rem;
}

.item-time {
  font-size: 0.7rem;
  color: var(--text-muted, #9ca3af);
}

.unread-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  flex-shrink: 0;
  margin-top: 0.45rem;
}

.more-hint {
  text-align: center;
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
  padding: 0.5rem;
  border-top: 1px solid var(--border-color, #f3f4f6);
}

/* Footer */
.dropdown-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.625rem 1rem;
  border-top: 1px solid var(--border-color, #e5e7eb);
  background: var(--footer-bg, #f9fafb);
}

.view-all-link {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.8rem;
  font-weight: 500;
  color: #3b82f6;
  text-decoration: none;
  transition: color 0.15s;
}

.view-all-link:hover {
  color: #1d4ed8;
}

.view-all-link svg {
  width: 0.875rem;
  height: 0.875rem;
}

.footer-shortcut {
  font-size: 0.7rem;
  color: var(--text-muted, #9ca3af);
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

kbd {
  display: inline-block;
  padding: 0.1rem 0.3rem;
  font-size: 0.65rem;
  font-family: monospace;
  background: var(--code-bg, #f3f4f6);
  border: 1px solid var(--border-color, #d1d5db);
  border-radius: 0.25rem;
  color: var(--text-secondary, #374151);
}
</style>
