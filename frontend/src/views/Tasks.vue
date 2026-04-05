<template>
  <div class="tasks-page">
    <div class="page-header mb-2">
      <div>
        <h2>Task Log</h2>
        <p class="text-muted">Proxmox task history across nodes</p>
      </div>
      <div class="header-actions">
        <button
          v-if="notifPermission !== 'granted'"
          @click="requestNotifPermission"
          class="btn btn-outline btn-sm"
        >
          Enable Notifications
        </button>
        <span v-else class="text-xs text-muted">Notifications On</span>
        <button @click="exportLog" class="btn btn-outline btn-sm" :disabled="tasks.length === 0">
          Export .txt
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="card mb-2">
      <div class="card-body">
        <div class="filters-row">
          <div class="form-group">
            <label class="form-label">Host</label>
            <select v-model="selectedHostId" @change="onHostChange" class="form-control">
              <option value="">All Hosts</option>
              <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Node</label>
            <select v-model="selectedNode" @change="onFilterChange" class="form-control" :disabled="!selectedHostId">
              <option value="">All Nodes</option>
              <option v-for="n in nodes" :key="n.node_name || n.node" :value="n.node_name || n.node">{{ n.node_name || n.node }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Type</label>
            <select v-model="filterType" @change="onFilterChange" class="form-control">
              <option value="">All Types</option>
              <option value="qmigrate">Migration</option>
              <option value="vzdump">Backup</option>
              <option value="qmcreate">Create VM</option>
              <option value="qmdestroy">Delete VM</option>
              <option value="qmstart">Start VM</option>
              <option value="qmstop">Stop VM</option>
              <option value="replicate">Replication</option>
              <option value="custom">Custom...</option>
            </select>
          </div>
          <div v-if="filterType === 'custom'" class="form-group">
            <label class="form-label">Custom Type</label>
            <input v-model="customType" @input="onFilterChange" class="form-control" placeholder="qmstart, vzdump..." />
          </div>
          <div class="form-group">
            <label class="form-label">Status</label>
            <select v-model="filterStatus" @change="onLocalFilter" class="form-control">
              <option value="">All</option>
              <option value="running">Running</option>
              <option value="OK">OK</option>
              <option value="error">Error</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">VMID</label>
            <input v-model.number="filterVmid" @input="onFilterChange" type="number" class="form-control" placeholder="100" />
          </div>
          <div class="form-group form-group--btn">
            <button @click="loadTasks(true)" class="btn btn-outline btn-sm">Refresh</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Running Tasks (top section, auto-refresh 3s) -->
    <div v-if="runningTasks.length" class="card mb-2">
      <div class="card-header">
        <h3>
          Running Tasks
          <span class="badge badge-warning ml-1">{{ runningTasks.length }}</span>
        </h3>
        <span class="text-xs text-muted">Auto-refresh every 3s</span>
      </div>
      <div class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Started</th>
              <th>Node</th>
              <th>VMID</th>
              <th>Type</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="task in runningTasks"
              :key="task._key"
              class="clickable-row"
              @click="openTaskDetail(task)"
            >
              <td class="text-sm">{{ task.starttime ? new Date(task.starttime * 1000).toLocaleString() : '—' }}</td>
              <td class="text-sm">{{ task.node || task._node }}</td>
              <td class="text-sm">{{ task.id || '—' }}</td>
              <td class="text-sm">{{ task.type }}</td>
              <td>
                <span class="badge badge-warning anim-pulse">running</span>
              </td>
              <td @click.stop>
                <button
                  class="btn btn-danger btn-xs"
                  :disabled="stoppingTask[task._key]"
                  @click.stop="stopTask(task)"
                  title="Stop this task"
                >
                  {{ stoppingTask[task._key] ? '...' : 'Stop' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Main Tasks Table -->
    <div class="card">
      <div class="card-header">
        <h3>Task History</h3>
      </div>
      <div v-if="loading" class="loading-spinner"></div>
      <div v-else-if="displayedTasks.length === 0" class="empty-state">
        <div class="empty-icon-wrap">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
        </div>
        <h4 class="empty-title">No tasks to show</h4>
        <p class="empty-subtitle">No Proxmox tasks match your current filters. Try selecting a different host, node or status.</p>
        <button @click="clearFilters" class="btn btn-outline">Clear Filters</button>
      </div>
      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Start Time</th>
              <th>Node</th>
              <th>VMID</th>
              <th>Type</th>
              <th>Status</th>
              <th>UPID</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="task in displayedTasks"
              :key="task._key"
              class="clickable-row"
              @click="openTaskDetail(task)"
            >
              <td class="text-sm">{{ task.starttime ? new Date(task.starttime * 1000).toLocaleString() : '—' }}</td>
              <td class="text-sm">{{ task.node || task._node }}</td>
              <td class="text-sm">{{ task.id || '—' }}</td>
              <td class="text-sm">{{ task.type }}</td>
              <td>
                <span :class="statusBadgeClass(task.status)">{{ task.status || 'running' }}</span>
              </td>
              <td class="text-sm text-muted upid-cell">{{ task.upid }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!loading && hasMore" class="text-center" style="padding:1rem">
        <button @click="loadMore" class="btn btn-outline" :disabled="loadingMore">
          {{ loadingMore ? 'Loading...' : 'Load More' }}
        </button>
      </div>
    </div>

    <!-- Task Detail Modal -->
    <div v-if="detailTask" class="modal-backdrop" @click.self="detailTask = null">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Task Detail</h3>
          <button @click="detailTask = null" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <div class="detail-meta text-sm mb-2">
            <div><strong>Type:</strong> {{ detailTask.type }}</div>
            <div><strong>Node:</strong> {{ detailTask.node || detailTask._node }}</div>
            <div v-if="detailTask.id"><strong>VMID:</strong> {{ detailTask.id }}</div>
            <div><strong>Status:</strong>
              <span :class="statusBadgeClass(detailTask.status)" style="margin-left:0.25rem">{{ detailTask.status || 'running' }}</span>
            </div>
            <div><strong>Started:</strong> {{ detailTask.starttime ? new Date(detailTask.starttime * 1000).toLocaleString() : '—' }}</div>
            <div v-if="detailTask.endtime"><strong>Ended:</strong> {{ new Date(detailTask.endtime * 1000).toLocaleString() }}</div>
            <div class="upid-line"><strong>UPID:</strong> <code>{{ detailTask.upid }}</code></div>
          </div>

          <div class="log-header">
            <strong class="text-sm">Log Output</strong>
            <button class="btn btn-outline btn-xs" @click="exportTaskLog">Export Log</button>
          </div>

          <div v-if="detailLoading" class="text-muted text-sm mt-1">Loading log...</div>
          <pre v-else class="task-log">{{ detailLog || 'No log output.' }}</pre>

          <div v-if="detailTaskRunning" class="text-sm text-muted mt-1">
            <span class="anim-pulse">Live — refreshing every 3s...</span>
          </div>
        </div>
        <div class="modal-footer">
          <button
            v-if="!detailTask.status || detailTask.status === 'running'"
            class="btn btn-danger"
            :disabled="stoppingTask[detailTask._key]"
            @click="stopTask(detailTask)"
          >
            {{ stoppingTask[detailTask._key] ? 'Stopping...' : 'Stop Task' }}
          </button>
          <button @click="detailTask = null" class="btn btn-outline">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

const PAGE_SIZE = 50

export default {
  name: 'Tasks',
  setup() {
    const route = useRoute()
    const toast = useToast()

    const hosts = ref([])
    const nodes = ref([])
    const tasks = ref([])
    const loading = ref(false)
    const loadingMore = ref(false)
    const hasMore = ref(false)
    const page = ref(0)

    const selectedHostId = ref(route.params.hostId || '')
    const selectedNode = ref('')
    const filterType = ref('')
    const customType = ref('')
    const filterVmid = ref(null)
    const filterStatus = ref('')

    // Running tasks section (auto-refresh 3s)
    let runningPollTimer = null
    const RUNNING_POLL_INTERVAL = 3000

    // Stop task
    const stoppingTask = ref({})

    // Task detail modal
    const detailTask = ref(null)
    const detailLog = ref('')
    const detailLoading = ref(false)
    const detailTaskRunning = ref(false)
    let detailPollTimer = null

    // ===== Browser Notifications =====
    const notifPermission = ref(typeof Notification !== 'undefined' ? Notification.permission : 'denied')

    const requestNotifPermission = async () => {
      if (typeof Notification === 'undefined') return
      const result = await Notification.requestPermission()
      notifPermission.value = result
      if (result === 'granted') {
        const hasRunning = tasks.value.some(t => !t.status || t.status === 'running')
        if (hasRunning) startTaskPolling()
      }
    }

    const sendTaskNotification = (task) => {
      if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
      const title = task.status === 'OK'
        ? `Task completed: ${task.type}`
        : `Task failed: ${task.type}`
      const body = [task.id && `VMID: ${task.id}`, task.node && `Node: ${task.node}`]
        .filter(Boolean).join(' | ') || task.upid
      new Notification(title, { body, icon: '/favicon.ico' })
    }

    const runningTaskKeys = new Set()
    let pollInterval = null

    const startTaskPolling = () => {
      if (pollInterval) return
      pollInterval = setInterval(async () => {
        if (Notification.permission !== 'granted') return
        const running = tasks.value.filter(t => !t.status || t.status === 'running')
        for (const task of running) {
          if (!runningTaskKeys.has(task._key)) runningTaskKeys.add(task._key)
        }
        for (const task of running) {
          try {
            const res = await api.pveNode.taskStatus(task._hostId, task._node || task.node, encodeURIComponent(task.upid))
            const status = res.data?.status
            if (status && status !== 'running') {
              task.status = status
              runningTaskKeys.delete(task._key)
              sendTaskNotification(task)
            }
          } catch (e) { /* ignore */ }
        }
        if (running.length === 0) {
          clearInterval(pollInterval)
          pollInterval = null
        }
      }, 5000)
    }

    // ─── Running tasks section ────────────────────────────────────────────────

    const runningTasks = computed(() => {
      return tasks.value.filter(t => !t.status || t.status === 'running')
    })

    async function pollRunningTasks() {
      const running = tasks.value.filter(t => !t.status || t.status === 'running')
      for (const task of running) {
        try {
          const res = await api.pveNode.taskStatus(task._hostId, task._node || task.node, encodeURIComponent(task.upid))
          const status = res.data?.status
          if (status && status !== 'running') {
            task.status = status
            if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
              sendTaskNotification(task)
            }
          }
        } catch { /* ignore */ }
      }
    }

    function startRunningPoll() {
      if (runningPollTimer) return
      runningPollTimer = setInterval(pollRunningTasks, RUNNING_POLL_INTERVAL)
    }

    function stopRunningPoll() {
      if (runningPollTimer) { clearInterval(runningPollTimer); runningPollTimer = null }
    }

    // ─── Filters ──────────────────────────────────────────────────────────────

    const effectiveType = computed(() => {
      if (filterType.value === 'custom') return customType.value
      return filterType.value
    })

    const displayedTasks = computed(() => {
      let list = tasks.value.filter(t => t.status || t.status === undefined) // exclude pure running (shown above)
      if (filterStatus.value === 'running') {
        list = tasks.value.filter(t => !t.status || t.status === 'running')
      } else if (filterStatus.value === 'OK') {
        list = tasks.value.filter(t => t.status === 'OK')
      } else if (filterStatus.value === 'error') {
        list = tasks.value.filter(t => t.status && t.status !== 'OK' && t.status !== 'running')
      } else {
        list = tasks.value.filter(t => t.status && t.status !== 'running')
      }
      return list
    })

    // ─── Data loading ─────────────────────────────────────────────────────────

    const loadHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = res.data || []
      } catch (e) { console.warn('Failed to load hosts', e) }
    }

    const loadNodes = async () => {
      nodes.value = []
      if (!selectedHostId.value) return
      try {
        const res = await api.proxmox.listNodes(selectedHostId.value)
        nodes.value = res.data || []
      } catch (e) { console.warn('Failed to load nodes', e) }
    }

    const buildParams = (start = 0) => {
      const p = { limit: PAGE_SIZE, start }
      if (effectiveType.value) p.typefilter = effectiveType.value
      if (filterVmid.value) p.vmid = filterVmid.value
      return p
    }

    const loadTasksForHostNode = async (hostId, nodeName, start = 0) => {
      const res = await api.pveNode.tasks(hostId, nodeName, buildParams(start))
      return (res.data || []).map((t, i) => ({
        ...t,
        _key: `${hostId}-${nodeName}-${t.upid || i}`,
        _hostId: hostId,
        _node: nodeName,
        _expanded: false,
        _log: null,
        _loadingLog: false,
      }))
    }

    const loadTasks = async (reset = true) => {
      if (reset) { page.value = 0; tasks.value = [] }
      loading.value = true
      try {
        let collected = []

        if (selectedHostId.value && selectedNode.value) {
          collected = await loadTasksForHostNode(selectedHostId.value, selectedNode.value, page.value * PAGE_SIZE)
        } else if (selectedHostId.value) {
          const nodeList = nodes.value.length ? nodes.value : await api.proxmox.listNodes(selectedHostId.value).then(r => r.data || [])
          const results = await Promise.all(
            nodeList.map(n => loadTasksForHostNode(selectedHostId.value, n.node_name || n.node, 0).catch(() => []))
          )
          collected = results.flat().sort((a, b) => (b.starttime || 0) - (a.starttime || 0)).slice(0, PAGE_SIZE)
        } else {
          const results = await Promise.all(
            hosts.value.map(async h => {
              try {
                const nRes = await api.proxmox.listNodes(h.id)
                const nodeList = nRes.data || []
                const taskResults = await Promise.all(
                  nodeList.map(n => loadTasksForHostNode(h.id, n.node_name || n.node, 0).catch(() => []))
                )
                return taskResults.flat()
              } catch { return [] }
            })
          )
          collected = results.flat().sort((a, b) => (b.starttime || 0) - (a.starttime || 0)).slice(0, PAGE_SIZE)
        }

        if (reset) { tasks.value = collected } else { tasks.value = [...tasks.value, ...collected] }
        hasMore.value = collected.length === PAGE_SIZE
      } catch (e) {
        console.error('Failed to load tasks', e)
      } finally {
        loading.value = false
      }

      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        const hasRunning = tasks.value.some(t => !t.status || t.status === 'running')
        if (hasRunning) startTaskPolling()
      }
    }

    const loadMore = async () => {
      page.value++
      loadingMore.value = true
      try {
        if (selectedHostId.value && selectedNode.value) {
          const more = await loadTasksForHostNode(selectedHostId.value, selectedNode.value, page.value * PAGE_SIZE)
          tasks.value = [...tasks.value, ...more]
          hasMore.value = more.length === PAGE_SIZE
        }
      } catch (e) { console.error(e) } finally { loadingMore.value = false }
    }

    const onHostChange = async () => {
      selectedNode.value = ''
      await loadNodes()
      await loadTasks(true)
    }

    const onFilterChange = () => { loadTasks(true) }
    const onLocalFilter = () => { /* computed filter — no reload needed */ }

    // ─── Stop task ────────────────────────────────────────────────────────────

    async function stopTask(task) {
      stoppingTask.value = { ...stoppingTask.value, [task._key]: true }
      try {
        await api.pveNode.stopTask(task._hostId, task._node || task.node, encodeURIComponent(task.upid))
        toast.success(`Task ${task.type} stop requested`)
        // Mark as stopped locally
        task.status = 'stopped'
        if (detailTask.value?._key === task._key) detailTask.value.status = 'stopped'
      } catch (err) {
        toast.error('Stop failed: ' + (err?.response?.data?.detail || err?.message))
      } finally {
        stoppingTask.value = { ...stoppingTask.value, [task._key]: false }
      }
    }

    // ─── Task detail modal ────────────────────────────────────────────────────

    async function openTaskDetail(task) {
      detailTask.value = task
      detailLog.value = ''
      detailLoading.value = true
      detailTaskRunning.value = !task.status || task.status === 'running'

      if (detailPollTimer) { clearInterval(detailPollTimer); detailPollTimer = null }

      await fetchDetailLog(task)

      if (detailTaskRunning.value) {
        detailPollTimer = setInterval(async () => {
          if (!detailTask.value) { clearInterval(detailPollTimer); return }
          await fetchDetailLog(detailTask.value)
          // Check if still running
          try {
            const res = await api.pveNode.taskStatus(
              detailTask.value._hostId,
              detailTask.value._node || detailTask.value.node,
              encodeURIComponent(detailTask.value.upid)
            )
            const s = res.data?.status
            if (s && s !== 'running') {
              detailTask.value.status = s
              detailTaskRunning.value = false
              clearInterval(detailPollTimer)
              detailPollTimer = null
            }
          } catch { /* ignore */ }
        }, 3000)
      }
    }

    async function fetchDetailLog(task) {
      try {
        const res = await api.pveNode.taskLog(task._hostId, task._node || task.node, encodeURIComponent(task.upid))
        detailLog.value = (res.data?.lines || res.data || []).join('\n')
      } catch (e) {
        detailLog.value = 'Failed to load log'
      } finally {
        detailLoading.value = false
      }
    }

    // ─── Export ───────────────────────────────────────────────────────────────

    function exportLog() {
      const lines = tasks.value.map(t => {
        const time = t.starttime ? new Date(t.starttime * 1000).toISOString() : 'unknown'
        return `[${time}] node=${t.node || t._node} type=${t.type} vmid=${t.id || ''} status=${t.status || 'running'} upid=${t.upid}`
      })
      const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `depl0y-tasks-${Date.now()}.txt`
      a.click()
      URL.revokeObjectURL(url)
    }

    function exportTaskLog() {
      if (!detailLog.value) return
      const blob = new Blob([detailLog.value], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `task-${detailTask.value?.type || 'log'}-${Date.now()}.txt`
      a.click()
      URL.revokeObjectURL(url)
    }

    const statusBadgeClass = (status) => {
      if (status === 'OK') return 'badge badge-success'
      if (!status || status === 'running') return 'badge badge-warning'
      return 'badge badge-danger'
    }

    onMounted(async () => {
      await loadHosts()
      if (selectedHostId.value) await loadNodes()
      await loadTasks(true)
      startRunningPoll()
      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        startTaskPolling()
      }
    })

    onUnmounted(() => {
      if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
      stopRunningPoll()
      if (detailPollTimer) { clearInterval(detailPollTimer); detailPollTimer = null }
    })

    const clearFilters = () => {
      filterType.value = ''
      filterStatus.value = ''
      filterVmid.value = null
      customType.value = ''
      onFilterChange()
    }

    return {
      hosts, nodes, tasks, loading, loadingMore, hasMore,
      selectedHostId, selectedNode, filterType, customType, filterVmid, filterStatus,
      runningTasks, displayedTasks, stoppingTask,
      detailTask, detailLog, detailLoading, detailTaskRunning,
      loadTasks, loadMore, onHostChange, onFilterChange, onLocalFilter,
      statusBadgeClass,
      notifPermission, requestNotifPermission,
      openTaskDetail, stopTask, exportLog, exportTaskLog,
      clearFilters,
    }
  }
}
</script>

<style scoped>
.tasks-page {
  padding: 0;
}

.page-header {
  margin-bottom: 1.5rem;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.card-body {
  padding: 1rem;
}

.filters-row {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: flex-end;
}

.filters-row .form-group {
  flex: 1;
  min-width: 140px;
  margin-bottom: 0;
}

.form-group--btn {
  flex: 0 0 auto;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.form-label {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-primary);
}

.table-container {
  overflow-x: auto;
}

.upid-cell {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background: var(--bg-secondary);
}

/* Animated badge for running */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.anim-pulse {
  animation: pulse 1.5s ease-in-out infinite;
}

/* Stop button */
.btn-danger {
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  font-weight: 500;
  padding: 0.25rem 0.6rem;
}
.btn-danger:hover { background: #dc2626; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-xs {
  padding: 0.15rem 0.4rem;
  font-size: 0.75rem;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

/* Task detail modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-box {
  background: var(--bg-primary, #1a2332);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  width: 680px;
  max-width: 95vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.modal-close {
  background: none;
  border: none;
  color: var(--text-muted, #888);
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
  padding: 0;
}

.modal-body {
  padding: 1.25rem;
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  padding: 1rem 1.25rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.detail-meta {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.upid-line code {
  font-size: 0.75rem;
  word-break: break-all;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.task-log {
  margin: 0;
  padding: 0.75rem 1rem;
  font-size: 0.8rem;
  color: #9ca3af;
  background: #0f1419;
  border-radius: 0.375rem;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 380px;
  overflow-y: auto;
}

.mb-2 { margin-bottom: 1rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.75rem; }
.ml-1 { margin-left: 0.5rem; }
.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.text-muted { color: var(--text-muted, #888); }
.text-center { text-align: center; }
.text-danger { color: #ef4444; }
.text-success { color: #10b981; }

.badge-warning {
  background-color: #d97706;
  color: #fff;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

/* ── Empty state ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1.5rem;
  text-align: center;
}

.empty-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--background);
  border: 2px dashed var(--border-color);
  color: var(--text-muted);
}

.empty-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.empty-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
  max-width: 400px;
}
</style>
