<template>
  <div class="notif-bell" ref="bellContainer">
    <!-- Bell button -->
    <button class="bell-btn" @click="toggleDropdown" :class="{ active: open }" :aria-label="`Notifications${unreadCount ? ` (${unreadCount} unread)` : ''}`">
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
        <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
      </svg>
      <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
    </button>

    <!-- Dropdown panel -->
    <div v-if="open" class="notif-dropdown">
      <div class="notif-header">
        <span class="notif-title">Recent Tasks</span>
        <button v-if="notifications.length > 0" class="clear-btn" @click="clearAll">Clear all</button>
      </div>

      <div class="notif-body">
        <div v-if="notifications.length === 0" class="notif-empty">
          <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.3;margin-bottom:0.5rem;">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
          </svg>
          <span>No recent task completions</span>
        </div>

        <div
          v-for="n in notifications"
          :key="n.upid"
          class="notif-item"
        >
          <span class="notif-type-icon">{{ typeIcon(n.type) }}</span>
          <div class="notif-info">
            <span class="notif-desc">{{ n.desc }}</span>
            <span class="notif-meta">{{ n.node }} &middot; {{ timeAgo(n.endtime) }}</span>
          </div>
          <span class="notif-status" :class="n.status === 'OK' ? 'status-ok' : 'status-err'">
            {{ n.status }}
          </span>
        </div>
      </div>

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
import api from '@/services/api'

const STORAGE_KEY = 'depl0y_seen_tasks'
const MAX_SEEN = 500
const MAX_NOTIFICATIONS = 20
const POLL_INTERVAL = 30_000
const CACHE_TTL = 60_000
const TWENTY_FOUR_HOURS = 24 * 60 * 60

const hostsCache = { data: null, ts: 0 }

export default {
  name: 'NotificationBell',
  setup() {
    const open = ref(false)
    const notifications = ref([])   // completed tasks displayed in dropdown
    const unreadCount = ref(0)
    const bellContainer = ref(null)

    // ── Persistence ───────────────────────────────────────────────────────────
    const loadSeen = () => {
      try {
        return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'))
      } catch {
        return new Set()
      }
    }

    const saveSeen = (set) => {
      try {
        const arr = Array.from(set)
        // Trim to max 500 — keep the most recent (tail)
        const trimmed = arr.length > MAX_SEEN ? arr.slice(arr.length - MAX_SEEN) : arr
        localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
      } catch {
        // localStorage full — ignore
      }
    }

    // seenUpids: tasks we have already processed (notified or skipped because still running)
    // notifiedUpids: tasks we surfaced as a notification
    const seenUpids = loadSeen()

    // ── Helpers ───────────────────────────────────────────────────────────────
    const getHosts = async () => {
      const now = Date.now()
      if (hostsCache.data && now - hostsCache.ts < CACHE_TTL) return hostsCache.data
      const res = await api.proxmox.listHosts()
      hostsCache.data = Array.isArray(res.data) ? res.data : (res.data?.items || res.data?.results || [])
      hostsCache.ts = now
      return hostsCache.data
    }

    const typeIcon = (type) => {
      if (!type) return '⚙️'
      const t = type.toLowerCase()
      if (t.includes('start') || t === 'qmstart' || t === 'vzstart') return '▶️'
      if (t.includes('stop') || t === 'qmstop' || t === 'vzstop') return '⏹️'
      if (t.includes('create') || t.includes('clone')) return '✨'
      if (t.includes('destroy') || t.includes('delete')) return '🗑️'
      if (t.includes('migrate')) return '🔀'
      if (t.includes('backup') || t.includes('vzdump')) return '💾'
      if (t.includes('restore')) return '♻️'
      if (t.includes('snapshot')) return '📸'
      if (t.includes('resize')) return '📐'
      if (t.includes('update') || t.includes('upgrade')) return '⬆️'
      return '⚙️'
    }

    const timeAgo = (epochSecs) => {
      if (!epochSecs) return ''
      const diff = Math.floor(Date.now() / 1000) - epochSecs
      if (diff < 60) return 'just now'
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
      return `${Math.floor(diff / 86400)}d ago`
    }

    const taskDesc = (task) => {
      // upid: UPID:node:hex:hex:hex:type:id:user@realm:
      // type field is human-readable enough; combine with id
      const type = task.type || ''
      const id = task.id || ''
      if (id) return `${type} — ${id}`
      return type || task.upid || 'task'
    }

    // ── Poll ─────────────────────────────────────────────────────────────────
    const poll = async () => {
      try {
        const hosts = await getHosts()
        const now = Math.floor(Date.now() / 1000)
        const cutoff = now - TWENTY_FOUR_HOURS
        const newNotifs = []

        await Promise.allSettled(
          hosts.map(async (host) => {
            const hostId = host.id
            let nodes
            try {
              const res = await api.proxmox.listNodes(hostId)
              nodes = Array.isArray(res.data) ? res.data : (res.data?.items || res.data?.data || [])
            } catch {
              return
            }

            await Promise.allSettled(
              nodes.map(async (nodeObj) => {
                const node = nodeObj.node || nodeObj.name || nodeObj
                if (!node || typeof node !== 'string') return
                let tasks
                try {
                  const res = await api.pveNode.listTasks(hostId, node, { limit: 10 })
                  tasks = Array.isArray(res.data) ? res.data : (res.data?.data || res.data?.items || [])
                } catch {
                  return
                }

                for (const task of tasks) {
                  const upid = task.upid || task.UPID
                  if (!upid) continue
                  // Only tasks completed in the last 24 h
                  const endtime = task.endtime || task.end_time
                  if (!endtime || endtime < cutoff) continue
                  // Only finished tasks
                  const status = task.status
                  if (status !== 'OK' && status !== 'ERROR') continue
                  // Skip if already seen
                  if (seenUpids.has(upid)) continue

                  seenUpids.add(upid)
                  newNotifs.push({
                    upid,
                    type: task.type || '',
                    desc: taskDesc(task),
                    node,
                    hostId,
                    status,
                    endtime
                  })
                }
              })
            )
          })
        )

        if (newNotifs.length > 0) {
          // Newest first
          newNotifs.sort((a, b) => (b.endtime || 0) - (a.endtime || 0))
          notifications.value = [
            ...newNotifs,
            ...notifications.value
          ].slice(0, MAX_NOTIFICATIONS)
          unreadCount.value += newNotifs.length
        }

        saveSeen(seenUpids)
      } catch (err) {
        console.warn('[NotificationBell] poll error:', err)
      }
    }

    // ── Open / close ─────────────────────────────────────────────────────────
    const toggleDropdown = () => {
      open.value = !open.value
      if (open.value) {
        // Mark as read
        unreadCount.value = 0
      }
    }

    const clearAll = () => {
      notifications.value = []
      unreadCount.value = 0
    }

    // ── Click outside ─────────────────────────────────────────────────────────
    const onClickOutside = (e) => {
      if (bellContainer.value && !bellContainer.value.contains(e.target)) {
        open.value = false
      }
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────
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
      notifications,
      unreadCount,
      bellContainer,
      toggleDropdown,
      clearAll,
      typeIcon,
      timeAgo
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
  width: 380px;
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
  padding: 0.75rem 1rem 0.6rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  flex-shrink: 0;
}

.notif-title {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: rgba(59, 130, 246, 0.9);
}

.clear-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.65);
  padding: 0;
  transition: color 0.15s;
}

.clear-btn:hover {
  color: rgba(255, 255, 255, 0.8);
}

/* ── Body ── */
.notif-body {
  overflow-y: auto;
  max-height: 400px;
}

.notif-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.8rem;
  gap: 0.25rem;
  text-align: center;
}

/* ── Notification item ── */
.notif-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.55rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  transition: background 0.12s;
}

.notif-item:last-child {
  border-bottom: none;
}

.notif-item:hover {
  background: rgba(59, 130, 246, 0.08);
}

.notif-type-icon {
  font-size: 1rem;
  flex-shrink: 0;
  width: 22px;
  text-align: center;
}

.notif-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.notif-desc {
  font-size: 0.82rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.88);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notif-meta {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.6);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Status badges ── */
.notif-status {
  font-size: 0.68rem;
  font-weight: 700;
  border-radius: 10px;
  padding: 2px 8px;
  white-space: nowrap;
  flex-shrink: 0;
  letter-spacing: 0.02em;
}

.status-ok {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.status-err {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

/* ── Footer ── */
.notif-footer {
  padding: 0.6rem 1rem;
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
