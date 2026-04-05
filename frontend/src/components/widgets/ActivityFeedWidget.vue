<template>
  <div class="activity-feed">
    <div v-if="loading && items.length === 0" class="feed-loading">Loading activity...</div>
    <div v-else-if="items.length === 0" class="feed-empty">No activity yet.</div>
    <div v-else ref="listEl" class="feed-list">
      <transition-group name="feed-item" tag="div">
        <div
          v-for="item in visibleItems"
          :key="item.id"
          :class="['feed-entry', `feed-${item.icon}`]"
        >
          <div class="feed-avatar" :class="`avatar-${item.icon}`">
            {{ userInitials(item.user) }}
          </div>
          <div class="feed-body">
            <div class="feed-text">
              <span class="feed-user">{{ item.user }}</span>
              <span class="feed-action">{{ item.action }}</span>
              <span v-if="item.resource" class="feed-resource">{{ item.resource }}</span>
            </div>
            <div class="feed-meta">{{ timeAgo(item.time) }}</div>
          </div>
          <div class="feed-dot" :class="`dot-${item.icon}`"></div>
        </div>
      </transition-group>
    </div>
    <div v-if="canLoadMore" class="feed-more">
      <button class="feed-more-btn" @click="loadMore" :disabled="loading">
        {{ loading ? 'Loading...' : 'Load more' }}
      </button>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import api from '@/services/api'

export default {
  name: 'ActivityFeedWidget',
  setup() {
    const items = ref([])
    const loading = ref(false)
    const offset = ref(0)
    const limit = 20
    const hasMore = ref(true)
    const listEl = ref(null)
    let pollTimer = null
    let lastTopId = ref(null)

    const visibleItems = computed(() => items.value)
    const canLoadMore = computed(() => hasMore.value && items.value.length > 0)

    const userInitials = (user) => {
      if (!user) return '?'
      return user.slice(0, 2).toUpperCase()
    }

    const timeAgo = (iso) => {
      if (!iso) return ''
      const diff = Date.now() - new Date(iso).getTime()
      const s = Math.floor(diff / 1000)
      if (s < 60) return `${s}s ago`
      const m = Math.floor(s / 60)
      if (m < 60) return `${m}m ago`
      const h = Math.floor(m / 60)
      if (h < 24) return `${h}h ago`
      const d = Math.floor(h / 24)
      return `${d}d ago`
    }

    const fetchFeed = async (append = false) => {
      loading.value = true
      try {
        const res = await api.audit.feed({ limit, offset: append ? offset.value : 0 })
        const data = res.data || []
        if (append) {
          items.value = [...items.value, ...data]
          hasMore.value = data.length === limit
          offset.value += data.length
        } else {
          // Check if there are new items at the top
          const firstId = data[0]?.id
          const hadNewItems = lastTopId.value && firstId && firstId !== lastTopId.value
          items.value = data
          hasMore.value = data.length === limit
          offset.value = data.length
          lastTopId.value = firstId

          // Smooth scroll to top if new items arrived
          if (hadNewItems && listEl.value) {
            await nextTick()
            listEl.value.scrollTo({ top: 0, behavior: 'smooth' })
          }
        }
      } catch (e) {
        // silently ignore — widget is optional
      } finally {
        loading.value = false
      }
    }

    const loadMore = () => fetchFeed(true)

    onMounted(() => {
      fetchFeed()
      pollTimer = setInterval(() => fetchFeed(), 10000)
    })

    onUnmounted(() => clearInterval(pollTimer))

    return { items, loading, visibleItems, canLoadMore, listEl, userInitials, timeAgo, loadMore }
  }
}
</script>

<style scoped>
.activity-feed {
  display: flex;
  flex-direction: column;
  gap: 0;
  height: 100%;
  min-height: 0;
}

.feed-loading,
.feed-empty {
  font-size: 0.8rem;
  color: var(--text-secondary);
  padding: 0.5rem 0;
  text-align: center;
}

.feed-list {
  flex: 1;
  overflow-y: auto;
  max-height: 320px;
}

.feed-entry {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.55rem 0.25rem;
  border-bottom: 1px solid var(--border-color);
  position: relative;
}

.feed-entry:last-child {
  border-bottom: none;
}

.feed-avatar {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 700;
  flex-shrink: 0;
  color: #fff;
}

.avatar-create   { background: #22c55e; }
.avatar-delete   { background: #ef4444; }
.avatar-modify   { background: #3b82f6; }
.avatar-login    { background: #6b7280; }
.avatar-power    { background: #f59e0b; }
.avatar-backup   { background: #8b5cf6; }
.avatar-scan     { background: #06b6d4; }
.avatar-info     { background: #64748b; }

.feed-body {
  flex: 1;
  min-width: 0;
}

.feed-text {
  font-size: 0.8rem;
  color: var(--text-primary);
  line-height: 1.4;
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  align-items: baseline;
}

.feed-user {
  font-weight: 700;
  color: var(--text-primary);
}

.feed-action {
  color: var(--text-secondary);
}

.feed-resource {
  font-weight: 600;
  color: var(--primary-color);
  font-size: 0.75rem;
}

.feed-meta {
  font-size: 0.7rem;
  color: var(--text-secondary);
  margin-top: 0.15rem;
}

.feed-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 0.35rem;
}

.dot-create  { background: #22c55e; }
.dot-delete  { background: #ef4444; }
.dot-modify  { background: #3b82f6; }
.dot-login   { background: #6b7280; }
.dot-power   { background: #f59e0b; }
.dot-backup  { background: #8b5cf6; }
.dot-scan    { background: #06b6d4; }
.dot-info    { background: #64748b; }

.feed-more {
  padding: 0.5rem 0 0.25rem;
  text-align: center;
}

.feed-more-btn {
  background: none;
  border: 1px solid var(--border-color);
  color: var(--primary-color);
  font-size: 0.78rem;
  padding: 0.3rem 0.8rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 0.15s;
}

.feed-more-btn:hover:not(:disabled) {
  background: var(--primary-color);
  color: #fff;
}

.feed-more-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Transition */
.feed-item-enter-active {
  transition: all 0.3s ease;
}
.feed-item-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
