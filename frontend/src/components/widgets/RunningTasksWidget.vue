<template>
  <div class="running-tasks">
    <div class="rt-header">
      <span class="rt-count" :class="tasks.length > 0 ? 'has-tasks' : ''">
        <span v-if="tasks.length > 0" class="pulse-dot"></span>
        {{ tasks.length }} running
      </span>
      <router-link to="/tasks" class="rt-view-all">View all tasks →</router-link>
    </div>

    <div v-if="tasks.length === 0" class="rt-empty">
      <span class="rt-idle-icon">✓</span>
      No tasks running
    </div>

    <div v-else class="rt-list">
      <div v-for="task in tasks" :key="task.upid" class="rt-row">
        <div class="rt-row-top">
          <span class="rt-desc">{{ task.description || task.type }}</span>
          <span class="rt-elapsed">{{ elapsed(task.started_at) }}</span>
        </div>
        <div class="rt-row-meta">
          <span class="rt-badge">{{ task.type }}</span>
          <span class="rt-node">{{ task.node }}</span>
          <span v-if="task.vmid" class="rt-vmid">VM {{ task.vmid }}</span>
        </div>
        <div class="rt-progress-wrap">
          <div class="rt-progress-bar">
            <div class="rt-progress-fill" :style="{ width: (task.progress || 0) + '%' }"></div>
          </div>
          <span class="rt-pct">{{ task.progress != null ? task.progress + '%' : '…' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

export default {
  name: 'RunningTasksWidget',
  setup() {
    const tasks = ref([])
    let timer = null

    const fetch = async () => {
      try {
        const res = await api.tasks.getRunning()
        tasks.value = (res.data || []).sort((a, b) => (b.started_at || 0) - (a.started_at || 0))
      } catch { /* ignore */ }
    }

    const elapsed = (startedAt) => {
      if (!startedAt) return ''
      const secs = Math.floor(Date.now() / 1000 - startedAt)
      if (secs < 60) return `${secs}s`
      if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
      return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
    }

    onMounted(() => { fetch(); timer = setInterval(fetch, 5000) })
    onUnmounted(() => clearInterval(timer))

    return { tasks, elapsed }
  }
}
</script>

<style scoped>
.running-tasks { height: 100%; display: flex; flex-direction: column; gap: 0.5rem; }

.rt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.78rem;
}

.rt-count {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.rt-count.has-tasks { color: #3b82f6; }

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  animation: pulse 1.5s infinite;
  flex-shrink: 0;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.75); }
}

.rt-view-all {
  font-size: 0.72rem;
  color: var(--accent-color, #3b82f6);
  text-decoration: none;
  white-space: nowrap;
}
.rt-view-all:hover { text-decoration: underline; }

.rt-empty {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  color: var(--text-secondary);
  padding: 0.75rem 0;
}

.rt-idle-icon { color: #22c55e; font-size: 1rem; }

.rt-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  overflow-y: auto;
  max-height: 260px;
}

.rt-row {
  padding: 0.45rem 0.55rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.78rem;
}

.rt-row-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.rt-desc {
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rt-elapsed {
  font-size: 0.7rem;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}

.rt-row-meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.rt-badge {
  font-size: 0.62rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.1rem 0.35rem;
  border-radius: 0.2rem;
  background: rgba(59,130,246,0.15);
  color: #3b82f6;
}

.rt-node, .rt-vmid {
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.rt-progress-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.rt-progress-bar {
  flex: 1;
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
}

.rt-progress-fill {
  height: 100%;
  background: #3b82f6;
  border-radius: 2px;
  transition: width 0.5s ease;
  min-width: 4px;
}

.rt-pct {
  font-size: 0.65rem;
  color: var(--text-secondary);
  white-space: nowrap;
  min-width: 2.5rem;
  text-align: right;
}
</style>
