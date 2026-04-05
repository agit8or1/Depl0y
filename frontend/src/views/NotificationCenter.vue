<template>
  <div class="notification-center">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header-left">
        <h1>Notifications</h1>
        <p class="subtitle">Your in-app notification history</p>
      </div>
      <div class="page-header-right">
        <button
          class="btn btn-secondary"
          :disabled="markingAll || notifications.length === 0"
          @click="markAllRead"
        >
          <svg class="btn-icon-svg" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
          </svg>
          {{ markingAll ? 'Marking...' : 'Mark all read' }}
        </button>
        <button
          class="btn btn-danger-outline"
          :disabled="deletingRead || readCount === 0"
          @click="deleteReadNotifications"
        >
          <svg class="btn-icon-svg" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          {{ deletingRead ? 'Deleting...' : `Delete read (${readCount})` }}
        </button>
      </div>
    </div>

    <!-- Filter Tabs -->
    <div class="filter-tabs">
      <button
        v-for="tab in filterTabs"
        :key="tab.id"
        class="filter-tab"
        :class="{ active: activeFilter === tab.id }"
        @click="activeFilter = tab.id"
      >
        {{ tab.label }}
        <span v-if="tab.count !== null" class="tab-count" :class="tab.countClass">
          {{ tab.count }}
        </span>
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>Loading notifications...</span>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredNotifications.length === 0" class="empty-state">
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"/>
        </svg>
      </div>
      <h3>No notifications</h3>
      <p v-if="activeFilter === 'all'">You're all caught up! No notifications yet.</p>
      <p v-else>No {{ activeFilter }} notifications.</p>
    </div>

    <!-- Notification List -->
    <div v-else class="notification-list">
      <div
        v-for="notif in paginatedNotifications"
        :key="notif.id"
        class="notification-item"
        :class="[`type-${notif.type}`, { unread: !notif.read }]"
        @click="markSingleRead(notif)"
      >
        <!-- Type Icon -->
        <div class="notif-icon-wrap" :class="`icon-${notif.type}`">
          <svg v-if="notif.type === 'error'" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
          </svg>
          <svg v-else-if="notif.type === 'warning'" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          <svg v-else-if="notif.type === 'success'" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
          </svg>
          <svg v-else viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
          </svg>
        </div>

        <!-- Content -->
        <div class="notif-content">
          <div class="notif-header-row">
            <span class="notif-title">{{ notif.title }}</span>
            <span class="unread-dot" v-if="!notif.read"></span>
          </div>
          <p class="notif-message">{{ notif.message }}</p>
          <div class="notif-meta">
            <span class="notif-time" :title="formatAbsolute(notif.created_at)">
              {{ formatRelative(notif.created_at) }}
            </span>
            <span class="notif-type-badge" :class="`badge-${notif.type}`">
              {{ notif.type }}
            </span>
            <a
              v-if="notif.action_url"
              :href="notif.action_url"
              class="notif-action-link"
              @click.stop
            >
              View details
            </a>
          </div>
        </div>

        <!-- Delete button -->
        <button
          class="notif-delete-btn"
          title="Delete notification"
          @click.stop="deleteSingle(notif)"
        >
          <svg viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Load More -->
    <div v-if="hasMore && !loading" class="load-more-row">
      <button class="btn btn-secondary" @click="loadMore" :disabled="loadingMore">
        {{ loadingMore ? 'Loading...' : `Load more (${filteredNotifications.length - displayLimit} remaining)` }}
      </button>
    </div>

    <!-- Stats footer -->
    <div v-if="!loading && notifications.length > 0" class="stats-footer">
      <span>{{ unreadCount }} unread</span>
      <span class="sep">·</span>
      <span>{{ notifications.length }} total loaded</span>
      <span class="sep">·</span>
      <span class="shortcut-hint">Press <kbd>N</kbd> to open notification bell</span>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'NotificationCenter',
  setup() {
    const toast = useToast()

    const notifications = ref([])
    const loading = ref(true)
    const markingAll = ref(false)
    const deletingRead = ref(false)
    const loadingMore = ref(false)
    const activeFilter = ref('all')
    const displayLimit = ref(25)

    // ── Filter tabs ────────────────────────────────────────────────────────
    const filterTabs = computed(() => [
      {
        id: 'all',
        label: 'All',
        count: notifications.value.length,
        countClass: '',
      },
      {
        id: 'unread',
        label: 'Unread',
        count: unreadCount.value,
        countClass: unreadCount.value > 0 ? 'count-blue' : '',
      },
      {
        id: 'info',
        label: 'Info',
        count: notifications.value.filter(n => n.type === 'info').length,
        countClass: '',
      },
      {
        id: 'warning',
        label: 'Warning',
        count: notifications.value.filter(n => n.type === 'warning').length,
        countClass: notifications.value.filter(n => n.type === 'warning').length > 0 ? 'count-yellow' : '',
      },
      {
        id: 'error',
        label: 'Error',
        count: notifications.value.filter(n => n.type === 'error').length,
        countClass: notifications.value.filter(n => n.type === 'error').length > 0 ? 'count-red' : '',
      },
      {
        id: 'success',
        label: 'Success',
        count: notifications.value.filter(n => n.type === 'success').length,
        countClass: '',
      },
    ])

    const unreadCount = computed(() => notifications.value.filter(n => !n.read).length)
    const readCount = computed(() => notifications.value.filter(n => n.read).length)

    const filteredNotifications = computed(() => {
      if (activeFilter.value === 'all') return notifications.value
      if (activeFilter.value === 'unread') return notifications.value.filter(n => !n.read)
      return notifications.value.filter(n => n.type === activeFilter.value)
    })

    const paginatedNotifications = computed(() =>
      filteredNotifications.value.slice(0, displayLimit.value)
    )

    const hasMore = computed(() =>
      filteredNotifications.value.length > displayLimit.value
    )

    // ── Data loading ───────────────────────────────────────────────────────
    const loadNotifications = async () => {
      loading.value = true
      try {
        const r = await api.notifications.list()
        notifications.value = r.data || []
      } catch (e) {
        toast.error('Failed to load notifications')
      } finally {
        loading.value = false
      }
    }

    const loadMore = () => {
      loadingMore.value = true
      setTimeout(() => {
        displayLimit.value += 25
        loadingMore.value = false
      }, 200)
    }

    // ── Actions ────────────────────────────────────────────────────────────
    const markSingleRead = async (notif) => {
      if (notif.read) return
      try {
        await api.notifications.markRead({ ids: [notif.id] })
        notif.read = true
      } catch (e) {
        // silent — non-critical
      }
    }

    const markAllRead = async () => {
      const unread = notifications.value.filter(n => !n.read)
      if (unread.length === 0) return
      markingAll.value = true
      try {
        await api.notifications.markRead({ all: true })
        notifications.value.forEach(n => { n.read = true })
        toast.success('All notifications marked as read')
      } catch (e) {
        toast.error('Failed to mark notifications read')
      } finally {
        markingAll.value = false
      }
    }

    const deleteSingle = async (notif) => {
      try {
        await api.notifications.delete(notif.id)
        notifications.value = notifications.value.filter(n => n.id !== notif.id)
      } catch (e) {
        toast.error('Failed to delete notification')
      }
    }

    const deleteReadNotifications = async () => {
      const readItems = notifications.value.filter(n => n.read)
      if (readItems.length === 0) return
      deletingRead.value = true
      try {
        await Promise.all(readItems.map(n => api.notifications.delete(n.id)))
        notifications.value = notifications.value.filter(n => !n.read)
        toast.success(`Deleted ${readItems.length} read notification${readItems.length !== 1 ? 's' : ''}`)
      } catch (e) {
        toast.error('Failed to delete notifications')
        await loadNotifications()
      } finally {
        deletingRead.value = false
      }
    }

    // ── Formatters ─────────────────────────────────────────────────────────
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

    const formatAbsolute = (iso) => {
      if (!iso) return ''
      return new Date(iso).toLocaleString()
    }

    onMounted(loadNotifications)

    return {
      notifications,
      loading,
      markingAll,
      deletingRead,
      loadingMore,
      activeFilter,
      displayLimit,
      filterTabs,
      unreadCount,
      readCount,
      filteredNotifications,
      paginatedNotifications,
      hasMore,
      loadMore,
      markSingleRead,
      markAllRead,
      deleteSingle,
      deleteReadNotifications,
      formatRelative,
      formatAbsolute,
    }
  }
}
</script>

<style scoped>
.notification-center {
  padding: 1.5rem;
  max-width: 800px;
}

/* ── Header ── */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.page-header-left h1 {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0 0 0.25rem;
}

.subtitle {
  color: var(--text-muted, #6b7280);
  margin: 0;
  font-size: 0.875rem;
}

.page-header-right {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

/* ── Buttons ── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.9rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--btn-secondary-bg, #f3f4f6);
  color: var(--text-primary, #111827);
  border-color: var(--border-color, #d1d5db);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--btn-secondary-hover, #e5e7eb);
}

.btn-danger-outline {
  background: transparent;
  color: #dc2626;
  border-color: #fca5a5;
}

.btn-danger-outline:hover:not(:disabled) {
  background: #fee2e2;
}

.btn-icon-svg {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}

/* ── Filter Tabs ── */
.filter-tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 2px solid var(--border-color, #e5e7eb);
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
}

.filter-tab {
  background: none;
  border: none;
  padding: 0.55rem 0.875rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  color: var(--text-muted, #6b7280);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: color 0.15s;
}

.filter-tab:hover {
  color: var(--text-primary, #111827);
}

.filter-tab.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.tab-count {
  font-size: 0.7rem;
  font-weight: 700;
  background: var(--badge-bg, #f3f4f6);
  color: var(--text-muted, #6b7280);
  border-radius: 999px;
  padding: 0.1rem 0.45rem;
  min-width: 1.2rem;
  text-align: center;
}

.count-blue   { background: #dbeafe; color: #1d4ed8; }
.count-yellow { background: #fef9c3; color: #92400e; }
.count-red    { background: #fee2e2; color: #b91c1c; }

/* ── Loading / Empty ── */
.loading-state {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 3rem;
  justify-content: center;
  color: var(--text-muted, #6b7280);
}

.spinner {
  width: 1.25rem;
  height: 1.25rem;
  border: 2px solid var(--border-color, #e5e7eb);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: 4rem 2rem;
  color: var(--text-muted, #9ca3af);
}

.empty-icon {
  width: 3rem;
  height: 3rem;
  margin: 0 auto 1rem;
  opacity: 0.4;
}

.empty-icon svg {
  width: 100%;
  height: 100%;
}

.empty-state h3 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
  color: var(--text-secondary, #6b7280);
}

.empty-state p {
  margin: 0;
  font-size: 0.875rem;
}

/* ── Notification List ── */
.notification-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  gap: 0.875rem;
  padding: 0.875rem 1rem;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.625rem;
  background: var(--card-bg, #fff);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  position: relative;
}

.notification-item:hover {
  border-color: #93c5fd;
  box-shadow: 0 1px 4px rgba(59, 130, 246, 0.08);
}

.notification-item.unread {
  background: var(--unread-bg, #eff6ff);
  border-color: #bfdbfe;
}

.notification-item.unread:hover {
  border-color: #93c5fd;
}

/* Type left border accent */
.notification-item.type-error   { border-left: 3px solid #ef4444; }
.notification-item.type-warning { border-left: 3px solid #f59e0b; }
.notification-item.type-success { border-left: 3px solid #10b981; }
.notification-item.type-info    { border-left: 3px solid #3b82f6; }

/* Icon wrapper */
.notif-icon-wrap {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.notif-icon-wrap svg {
  width: 1.1rem;
  height: 1.1rem;
}

.icon-error   { background: #fee2e2; color: #dc2626; }
.icon-warning { background: #fef3c7; color: #d97706; }
.icon-success { background: #d1fae5; color: #059669; }
.icon-info    { background: #dbeafe; color: #2563eb; }

/* Content */
.notif-content {
  flex: 1;
  min-width: 0;
}

.notif-header-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.2rem;
}

.notif-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary, #111827);
  flex: 1;
}

.unread-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  flex-shrink: 0;
}

.notif-message {
  font-size: 0.8125rem;
  color: var(--text-secondary, #4b5563);
  margin: 0 0 0.4rem;
  line-height: 1.5;
}

.notif-meta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.notif-time {
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
}

.notif-type-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
}

.badge-info    { background: #dbeafe; color: #1d4ed8; }
.badge-warning { background: #fef9c3; color: #92400e; }
.badge-error   { background: #fee2e2; color: #b91c1c; }
.badge-success { background: #d1fae5; color: #065f46; }

.notif-action-link {
  font-size: 0.75rem;
  color: #3b82f6;
  text-decoration: none;
}

.notif-action-link:hover {
  text-decoration: underline;
}

/* Delete button */
.notif-delete-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 0.375rem;
  color: var(--text-muted, #9ca3af);
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s, color 0.15s;
}

.notification-item:hover .notif-delete-btn {
  opacity: 1;
}

.notif-delete-btn:hover {
  background: #fee2e2;
  color: #dc2626;
}

.notif-delete-btn svg {
  width: 0.875rem;
  height: 0.875rem;
  display: block;
}

/* ── Load More ── */
.load-more-row {
  display: flex;
  justify-content: center;
  padding: 1rem 0;
}

/* ── Stats footer ── */
.stats-footer {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 0 0.5rem;
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
  flex-wrap: wrap;
}

.sep {
  color: var(--border-color, #d1d5db);
}

.shortcut-hint {
  margin-left: auto;
}

kbd {
  display: inline-block;
  padding: 0.1rem 0.3rem;
  font-size: 0.7rem;
  font-family: monospace;
  background: var(--code-bg, #f3f4f6);
  border: 1px solid var(--border-color, #d1d5db);
  border-radius: 0.25rem;
  color: var(--text-secondary, #374151);
}
</style>
