<template>
  <div class="recent-tasks">
    <SkeletonLoader v-if="loading" type="table" :count="3" />
    <div v-else-if="tasks.length === 0" class="we">No recent tasks.</div>
    <div v-else class="task-list">
      <div v-for="task in tasks" :key="task.upid" class="task-row">
        <div class="task-info">
          <span class="task-type">{{ task.type }}</span>
          <span class="task-node">{{ task.node }} · {{ task.hostName }}</span>
        </div>
        <div class="task-right">
          <span :class="['task-badge', taskClass(task.status)]">{{ task.status || 'running' }}</span>
          <span class="task-time">{{ fmtTime(task.starttime) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

export default {
  name: 'RecentTasksWidget',
  components: { SkeletonLoader },
  setup() {
    const loading = ref(true)
    const tasks = ref([])
    let timer = null

    const fetch = async () => {
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = (hostsRes.data || []).filter(h => h.is_active)
        if (!hosts.length) { loading.value = false; return }

        const resourceResults = await Promise.allSettled(
          hosts.map(h => api.pveNode.clusterResources(h.id))
        )
        const nodeTargets = []
        resourceResults.forEach((result, idx) => {
          const host = hosts[idx]
          if (result.status === 'fulfilled') {
            const items = result.value.data || []
            const nodeNames = items.filter(i => i.type === 'node').map(i => i.node)
            const names = nodeNames.length > 0 ? nodeNames : [host.host.split(':')[0].split('.')[0]]
            names.forEach(node => nodeTargets.push({ hostId: host.id, hostName: host.name, node }))
          }
        })

        const taskResults = await Promise.allSettled(
          nodeTargets.map(t => api.pveNode.listTasks(t.hostId, t.node, { limit: 5 }))
        )

        const all = []
        taskResults.forEach((result, idx) => {
          const target = nodeTargets[idx]
          if (result.status === 'fulfilled') {
            ;(result.value.data || []).forEach(task => {
              all.push({
                upid: task.upid,
                hostName: target.hostName,
                node: task.node || target.node,
                type: task.type,
                status: task.status,
                starttime: task.starttime
              })
            })
          }
        })
        all.sort((a, b) => (b.starttime || 0) - (a.starttime || 0))
        tasks.value = all.slice(0, 10)
      } catch (e) {
        // ignore
      } finally {
        loading.value = false
      }
    }

    const taskClass = (status) => {
      if (!status) return 'badge-running'
      const s = status.toLowerCase()
      if (s === 'ok') return 'badge-ok'
      if (s.includes('warn')) return 'badge-warn'
      if (s === 'error' || s.includes('fail')) return 'badge-error'
      return 'badge-running'
    }

    const fmtTime = (ts) => {
      if (!ts) return '—'
      return new Date(ts * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    }

    onMounted(() => { fetch(); timer = setInterval(fetch, 30000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, tasks, taskClass, fmtTime }
  }
}
</script>

<style scoped>
.recent-tasks { height: 100%; }
.wl, .we { font-size: 0.8rem; color: var(--text-secondary); padding: 0.5rem 0; }

.task-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.task-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.35rem 0.5rem;
  border-radius: 0.375rem;
  border: 1px solid var(--border-color);
  gap: 0.5rem;
  font-size: 0.8rem;
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}

.task-type {
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-node {
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.task-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.15rem;
  flex-shrink: 0;
}

.task-badge {
  font-size: 0.62rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.1rem 0.35rem;
  border-radius: 0.2rem;
}

.badge-ok      { background: rgba(34,197,94,0.15);  color: #22c55e; }
.badge-warn    { background: rgba(234,179,8,0.15);  color: #ca8a04; }
.badge-error   { background: rgba(239,68,68,0.12);  color: #ef4444; }
.badge-running { background: rgba(59,130,246,0.15); color: #3b82f6; }

.task-time {
  font-size: 0.68rem;
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
