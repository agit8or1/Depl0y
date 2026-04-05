<template>
  <div class="notif-bell" ref="bellContainer">
    <!-- Bell button -->
    <button
      class="bell-btn"
      @click="toggleDropdown"
      :class="{ active: open }"
      :aria-label="`Notifications${unreadCount ? ` (${unreadCount} unread)` : ''}`"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
        <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
      </svg>
      <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
    </button>

    <!-- Dropdown panel -->
    <div v-if="open" class="notif-dropdown">
      <!-- Header -->
      <div class="notif-header">
        <span class="notif-title">Notifications</span>
        <div class="notif-header-actions">
          <button
            v-if="hasUnread"
            class="action-btn"
            @click="markAllRead"
            title="Mark all read"
          >
            Mark all read
          </button>
          <button
            v-if="notifications.length > 0"
            class="action-btn clear-btn"
            @click="clearAll"
            title="Clear all"
          >
            Clear all
          </button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="notif-tabs">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'all' }"
          @click="activeTab = 'all'"
        >
          All
          <span v-if="notifications.length > 0" class="tab-count">{{ notifications.length }}</span>
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'unread' }"
          @click="activeTab = 'unread'"
        >
          Unread
          <span v-if="unreadCount > 0" class="tab-count tab-count-unread">{{ unreadCount }}</span>
        </button>
      </div>

      <!-- Body -->
      <div class="notif-body">
        <div v-if="loading" class="notif-empty">
          <div class="notif-spinner"></div>
          <span>Loading...</span>
        </div>

        <div v-else-if="filteredNotifications.length === 0" class="notif-empty">
          <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.3;margin-bottom:0.5rem;">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
          </svg>
          <span>{{ activeTab === 'unread' ? 'No unread notifications' : 'No notifications' }}</span>
        </div>

        <div
          v-for="n in filteredNotifications"
          :key="n.id"
          class="notif-item"
          :class="{ unread: !n.read, clickable: !!n.action_url }"
          @click="handleNotifClick(n)"
        >
          <!-- Colored left border by type -->
          <div class="notif-type-bar" :class="`type-${n.type}`"></div>

          <div class="notif-item-content">
            <div class="notif-item-header">
              <span class="notif-item-title">{{ n.title }}</span>
              <span class="notif-item-time">{{ timeAgo(n.created_at) }}</span>
            </div>
            <p class="notif-item-message">{{ n.message }}</p>
            <div v-if="n.action_url" class="notif-item-link">
              <span>View &rarr;</span>
            </div>
          </div>

          <!-- Unread dot -->
          <div v-if="!n.read" class="unread-dot"></div>

          <!-- Delete button -->
          <button
            class="notif-delete-btn"
            @click.stop="deleteNotif(n.id)"
            title="Dismiss"
          >
            &times;
          </button>
        </div>
      </div>

      <!-- Footer -->
      <div class="notif-footer">
        <router-link to="/tasks" class="view-all-link" @click="open = false">
          View all tasks &rarr;
        </router-link>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

const POLL_INTERVAL = 30_000

export default {
  name: 'NotificationBell',
  setup() {
    const router = useRouter()
    const open = ref(false)
    const loading = ref(false)
    const notifications = ref([])
    const activeTab = ref('all')
    const bellContainer = ref(null)

    // ── Computed ───────────────────────────────────────────────────────────
    const unreadCount = computed(() => notifications.value.filter(n => !n.read).length)
    const hasUnread = computed(() => unreadCount.value > 0)

    const filteredNotifications = computed(() => {
      if (activeTab.value === 'unread') {
        return notifications.value.filter(n => !n.read)
      }
      return notifications.value
    })

    // ── Time formatting ───────────────────────────────────────────────────
    const timeAgo = (isoStr) => {
      if (!isoStr) return ''
      const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000)
      if (diff < 60) return 'just now'
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
      return `${Math.floor(diff / 86400)}d ago`
    }

    // ── Poll from backend ──────────────────────────────────────────────────
    const poll = async (showLoading = false) => {
      if (showLoading) loading.value = true
      try {
        const res = await api.notifications.list()
        notifications.value = Array.isArray(res.data) ? res.data : []
      } catch (err) {
        // Silently fail — user may not be authenticated yet
      } finally {
        if (showLoading) loading.value = false
      }
    }

    // ── Actions ───────────────────────────────────────────────────────────
    const markAllRead = async () => {
      try {
        await api.notifications.markRead({ all: true })
        notifications.value.forEach(n => { n.read = true })
      } catch (err) {
        console.warn('[NotificationBell] markAllRead error:', err)
      }
    }

    const clearAll = async () => {
      try {
        await api.notifications.deleteAll()
        notifications.value = []
      } catch (err) {
        console.warn('[NotificationBell] clearAll error:', err)
      }
    }

    const deleteNotif = async (id) => {
      try {
        await api.notifications.delete(id)
        notifications.value = notifications.value.filter(n => n.id !== id)
      } catch (err) {
        console.warn('[NotificationBell] deleteNotif error:', err)
      }
    }

    const handleNotifClick = async (notif) => {
      // Mark as read
      if (!notif.read) {
        try {
          await api.notifications.markRead({ ids: [notif.id] })
          const found = notifications.value.find(n => n.id === notif.id)
          if (found) found.read = true
        } catch (err) {
          // ignore
        }
      }
      // Navigate if action_url
      if (notif.action_url) {
        open.value = false
        if (notif.action_url.startsWith('http')) {
          window.open(notif.action_url, '_blank')
        } else {
          router.push(notif.action_url)
        }
      }
    }

    // ── Open / close ──────────────────────────────────────────────────────
    const toggleDropdown = () => {
      open.value = !open.value
      if (open.value) {
        poll(true)
      }
    }

    // ── Click outside ─────────────────────────────────────────────────────
    const onClickOutside = (e) => {
      if (bellContainer.value && !bellContainer.value.contains(e.target)) {
        open.value = false
      }
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────
    let pollTimer = null

    onMounted(() => {
      document.addEventListener('mousedown', onClickOutside)
      poll()
      pollTimer = setInterval(poll, POLL_INTERVAL)
    })

    onBeforeUnmount(() => {
      document.removeEventListener('mousedown', onClickOutside)
      if (pollTimer) clearInterval(pollTimer)
    })

    return {
      open,
      loading,
      notifications,
      unreadCount,
      hasUnread,
      activeTab,
      filteredNotifications,
      bellContainer,
      toggleDropdown,
      markAllRead,
      clearAll,
      deleteNotif,
      handleNotifClick,
      timeAgo,
    }
  }
}
</script>

<style scoped>
/* ── Wrapper ── */
.notif-bell {
  position: relative;
  flex-shrink: 0;
}

/* ── Bell button ── */
.bell-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.bell-btn:hover,
.bell-btn.active {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.35);
  color: #fff;
}

/* ── Badge ── */
.badge {
  position: absolute;
  top: -5px;
  right: -5px;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  background: #ef4444;
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  border: 2px solid #1a2332;
  pointer-events: none;
}

/* ── Dropdown ── */
.notif-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 400px;
  background: #1e2a3a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.55);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Header ── */
.notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  flex-shrink: 0;
  gap: 0.5rem;
}

.notif-title {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: rgba(59, 130, 246, 0.9);
  flex-shrink: 0;
}

.notif-header-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.action-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.55);
  padding: 2px 6px;
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
  white-space: nowrap;
}

.action-btn:hover {
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.07);
}

.clear-btn:hover {
  color: #f87171;
}

/* ── Tabs ── */
.notif-tabs {
  display: flex;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  flex-shrink: 0;
}

.tab-btn {
  flex: 1;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  padding: 0.45rem 0.5rem;
  transition: color 0.15s, border-color 0.15s;
  border-bottom: 2px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
}

.tab-btn:hover {
  color: rgba(255, 255, 255, 0.8);
}

.tab-btn.active {
  color: rgba(59, 130, 246, 0.95);
  border-bottom-color: rgba(59, 130, 246, 0.8);
}

.tab-count {
  font-size: 0.65rem;
  padding: 1px 5px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.6);
}

.tab-count-unread {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

/* ── Body ── */
.notif-body {
  overflow-y: auto;
  max-height: 380px;
}

/* Spinner */
.notif-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.15);
  border-top-color: rgba(59, 130, 246, 0.8);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-bottom: 0.5rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.notif-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.8rem;
  gap: 0.25rem;
  text-align: center;
}

/* ── Notification item ── */
.notif-item {
  position: relative;
  display: flex;
  align-items: stretch;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  transition: background 0.12s;
}

.notif-item:last-child {
  border-bottom: none;
}

.notif-item:hover {
  background: rgba(59, 130, 246, 0.06);
}

.notif-item.clickable {
  cursor: pointer;
}

.notif-item.unread {
  background: rgba(59, 130, 246, 0.04);
}

/* Type color bar */
.notif-type-bar {
  width: 3px;
  flex-shrink: 0;
  border-radius: 0;
}

.type-info    { background: #3b82f6; }
.type-success { background: #22c55e; }
.type-warning { background: #f59e0b; }
.type-error   { background: #ef4444; }

/* Content area */
.notif-item-content {
  flex: 1;
  padding: 0.55rem 0.75rem 0.55rem 0.65rem;
  min-width: 0;
}

.notif-item-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 2px;
}

.notif-item-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notif-item-time {
  font-size: 0.67rem;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
  flex-shrink: 0;
}

.notif-item-message {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.6);
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.notif-item-link {
  margin-top: 4px;
  font-size: 0.7rem;
  color: rgba(59, 130, 246, 0.8);
}

/* Unread dot */
.unread-dot {
  position: absolute;
  top: 50%;
  right: 28px;
  transform: translateY(-50%);
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3b82f6;
  flex-shrink: 0;
}

/* Delete button */
.notif-delete-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.25);
  padding: 0 10px;
  align-self: center;
  flex-shrink: 0;
  line-height: 1;
  transition: color 0.12s;
}

.notif-delete-btn:hover {
  color: rgba(239, 68, 68, 0.8);
}

/* ── Footer ── */
.notif-footer {
  padding: 0.55rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  flex-shrink: 0;
}

.view-all-link {
  font-size: 0.78rem;
  color: rgba(59, 130, 246, 0.85);
  text-decoration: none;
  transition: color 0.15s;
}

.view-all-link:hover {
  color: rgba(59, 130, 246, 1);
  text-decoration: underline;
}

/* ── Responsive ── */
@media (max-width: 480px) {
  .notif-dropdown {
    width: calc(100vw - 2rem);
    right: -0.5rem;
  }
}
</style>
