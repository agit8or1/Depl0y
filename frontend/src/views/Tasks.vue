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
        <button @click="exportCsv" class="btn btn-outline btn-sm" :disabled="displayedTasks.length === 0">
          Export CSV
        </button>
        <button @click="exportLog" class="btn btn-outline btn-sm" :disabled="tasks.length === 0">
          Export .txt
        </button>
      </div>
    </div>

    <!-- Tab bar -->
    <div class="tab-bar mb-2">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'depl0y' }"
        @click="activeTab = 'depl0y'"
      >
        Depl0y Tasks
        <span v-if="deplRunning.length" class="tab-badge badge-warning">{{ deplRunning.length }}</span>
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'proxmox' }"
        @click="activeTab = 'proxmox'"
      >
        All Proxmox Tasks
      </button>
    </div>

    <!-- ───────────── DEPL0Y TASKS TAB ───────────── -->
    <template v-if="activeTab === 'depl0y'">

      <!-- Running Depl0y tasks -->
      <div v-if="deplRunning.length" class="card mb-2">
        <div class="card-header">
          <h3>
            Running
            <span class="badge badge-warning ml-1">{{ deplRunning.length }}</span>
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
                <th>Description</th>
                <th>Progress</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="task in deplRunning"
                :key="task.upid"
                class="clickable-row"
                @click="openDeplDetail(task)"
              >
                <td class="text-sm">{{ formatTime(task.started_at) }}</td>
                <td class="text-sm">{{ task.node }}</td>
                <td class="text-sm">{{ task.vmid || '—' }}</td>
                <td class="text-sm">{{ task.description || task.task_type }}</td>
                <td class="text-sm" style="min-width:100px">
                  <div class="prog-track">
                    <div class="prog-fill" :style="{ width: `${task.progress || 0}%` }"></div>
                  </div>
                  <span class="text-xs text-muted">{{ task.progress || 0 }}%</span>
                </td>
                <td @click.stop>
                  <button
                    class="btn btn-danger btn-xs"
                    :disabled="stoppingDeplTask[task.upid]"
                    @click.stop="stopDeplTask(task)"
                  >
                    {{ stoppingDeplTask[task.upid] ? '...' : 'Stop' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Depl0y task history -->
      <div class="card">
        <div class="card-header">
          <h3>History (this session)</h3>
          <button @click="loadDeplHistory" class="btn btn-outline btn-sm">Refresh</button>
        </div>
        <div v-if="deplHistoryLoading" class="loading-spinner"></div>
        <div v-else-if="deplHistory.length === 0" class="empty-state">
          <div class="empty-icon-wrap">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <h4 class="empty-title">No completed Depl0y tasks</h4>
          <p class="empty-subtitle">Tasks initiated through Depl0y this session will appear here.</p>
        </div>
        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Started</th>
                <th>Finished</th>
                <th>Node</th>
                <th>VMID</th>
                <th>Description</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="task in deplHistory"
                :key="task.upid"
                class="clickable-row"
                @click="openDeplDetail(task)"
              >
                <td class="text-sm">{{ formatTime(task.started_at) }}</td>
                <td class="text-sm">{{ formatTime(task.finished_at) }}</td>
                <td class="text-sm">{{ task.node }}</td>
                <td class="text-sm">{{ task.vmid || '—' }}</td>
                <td class="text-sm">{{ task.description || task.task_type }}</td>
                <td>
                  <span :class="deplStatusClass(task.exit_status)">{{ task.exit_status || task.status }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </template>

    <!-- ───────────── ALL PROXMOX TASKS TAB ───────────── -->
    <template v-if="activeTab === 'proxmox'">

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
            <div class="form-group">
              <label class="form-label">Time Range</label>
              <select v-model="filterTimeRange" @change="onLocalFilter" class="form-control">
                <option value="">All time</option>
                <option value="1h">Last 1 hour</option>
                <option value="6h">Last 6 hours</option>
                <option value="24h">Last 24 hours</option>
                <option value="7d">Last 7 days</option>
              </select>
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
                <th>Duration</th>
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
                <td class="text-sm text-muted">{{ taskDuration(task) }}</td>
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

    </template>

    <!-- ── Proxmox Task Detail Modal ── -->
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

    <!-- ── Depl0y Task Detail Modal ── -->
    <div v-if="deplDetailTask" class="modal-backdrop" @click.self="deplDetailTask = null">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Depl0y Task Detail</h3>
          <button @click="deplDetailTask = null" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <div class="detail-meta text-sm mb-2">
            <div><strong>Description:</strong> {{ deplDetailTask.description || '—' }}</div>
            <div><strong>Type:</strong> {{ deplDetailTask.task_type }}</div>
            <div><strong>Node:</strong> {{ deplDetailTask.node }}</div>
            <div v-if="deplDetailTask.vmid"><strong>VMID:</strong> {{ deplDetailTask.vmid }}</div>
            <div>
              <strong>Status:</strong>
              <span :class="deplDetailTask.status === 'running' ? 'badge badge-warning' : deplStatusClass(deplDetailTask.exit_status)" style="margin-left:0.25rem">
                {{ deplDetailTask.status === 'running' ? 'running' : (deplDetailTask.exit_status || deplDetailTask.status) }}
              </span>
            </div>
            <div><strong>Started:</strong> {{ formatTime(deplDetailTask.started_at) }}</div>
            <div v-if="deplDetailTask.finished_at"><strong>Finished:</strong> {{ formatTime(deplDetailTask.finished_at) }}</div>
            <div v-if="deplDetailTask.progress !== undefined && deplDetailTask.status === 'running'">
              <strong>Progress:</strong> {{ deplDetailTask.progress }}%
              <div class="prog-track mt-1" style="max-width:240px">
                <div class="prog-fill" :style="{ width: `${deplDetailTask.progress || 0}%` }"></div>
              </div>
            </div>
            <div class="upid-line"><strong>UPID:</strong> <code>{{ deplDetailTask.upid }}</code></div>
          </div>

          <div class="log-header">
            <strong class="text-sm">Log Output</strong>
          </div>
          <div v-if="deplDetailLoading" class="text-muted text-sm mt-1">Loading log...</div>
          <pre v-else class="task-log">{{ deplDetailLog || 'No log output.' }}</pre>
          <div v-if="deplDetailTask.status === 'running'" class="text-sm text-muted mt-1">
            <span class="anim-pulse">Live — refreshing every 3s...</span>
          </div>
        </div>
        <div class="modal-footer">
          <button
            v-if="deplDetailTask.status === 'running'"
            class="btn btn-danger"
            :disabled="stoppingDeplTask[deplDetailTask.upid]"
            @click="stopDeplTask(deplDetailTask)"
          >
            {{ stoppingDeplTask[deplDetailTask.upid] ? 'Stopping...' : 'Stop Task' }}
          </button>
          <button @click="deplDetailTask = null" class="btn btn-outline">Close</button>
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
const DEPL_POLL_INTERVAL = 3000

export default {
  name: 'Tasks',
  setup() {
    const route = useRoute()
    const toast = useToast()

    // ── Tab state ──────────────────────────────────────────────────────────
    const activeTab = ref('depl0y')

    // ── Depl0y Tasks state ─────────────────────────────────────────────────
    const deplRunning = ref([])
    const deplHistory = ref([])
    const deplHistoryLoading = ref(false)
    const stoppingDeplTask = ref({})
    const deplDetailTask = ref(null)
    const deplDetailLog = ref('')
    const deplDetailLoading = ref(false)
    let deplDetailPollTimer = null
    let deplPollTimer = null

    async function loadDeplRunning() {
      try {
        const res = await api.tasks.getRunning()
        deplRunning.value = res.data || []
      } catch { /* ignore */ }
    }

    async function loadDeplHistory() {
      deplHistoryLoading.value = true
      try {
        const res = await api.tasks.getHistory({ limit: 100 })
        deplHistory.value = res.data || []
      } catch { /* ignore */ } finally {
        deplHistoryLoading.value = false
      }
    }

    function startDeplPoll() {
      if (deplPollTimer) return
      deplPollTimer = setInterval(loadDeplRunning, DEPL_POLL_INTERVAL)
    }

    function stopDeplPoll() {
      if (deplPollTimer) { clearInterval(deplPollTimer); deplPollTimer = null }
    }

    async function stopDeplTask(task) {
      stoppingDeplTask.value = { ...stoppingDeplTask.value, [task.upid]: true }
      try {
        await api.tasks.stop(task.host_id, task.node, task.upid)
        toast.success('Task stop requested')
        deplRunning.value = deplRunning.value.filter(t => t.upid !== task.upid)
        if (deplDetailTask.value?.upid === task.upid) deplDetailTask.value = null
      } catch (err) {
        toast.error('Stop failed: ' + (err?.response?.data?.detail || err?.message))
      } finally {
        stoppingDeplTask.value = { ...stoppingDeplTask.value, [task.upid]: false }
      }
    }

    async function openDeplDetail(task) {
      deplDetailTask.value = { ...task }
      deplDetailLog.value = ''
      deplDetailLoading.value = true

      if (deplDetailPollTimer) { clearInterval(deplDetailPollTimer); deplDetailPollTimer = null }

      await fetchDeplLog(task)

      if (task.status === 'running') {
        deplDetailPollTimer = setInterval(async () => {
          if (!deplDetailTask.value) { clearInterval(deplDetailPollTimer); return }
          await fetchDeplLog(deplDetailTask.value)
          // Also refresh status from running list
          const found = deplRunning.value.find(t => t.upid === deplDetailTask.value?.upid)
          if (found) {
            deplDetailTask.value = { ...found }
          } else if (deplDetailTask.value?.status === 'running') {
            // No longer in running list — completed
            deplDetailTask.value.status = 'done'
            clearInterval(deplDetailPollTimer)
          }
        }, DEPL_POLL_INTERVAL)
      }
    }

    async function fetchDeplLog(task) {
      try {
        const res = await api.tasks.getLog(task.host_id, task.node, task.upid)
        deplDetailLog.value = (res.data?.lines || []).join('\n')
      } catch {
        deplDetailLog.value = 'Failed to load log'
      } finally {
        deplDetailLoading.value = false
      }
    }

    function deplStatusClass(exitStatus) {
      if (exitStatus === 'OK') return 'badge badge-success'
      if (!exitStatus) return 'badge badge-warning'
      return 'badge badge-danger'
    }

    function formatTime(isoStr) {
      if (!isoStr) return '—'
      try { return new Date(isoStr).toLocaleString() } catch { return isoStr }
    }

    // ── Proxmox Tasks (existing) ───────────────────────────────────────────

    const hosts = ref([])
    const nodes = ref([])
    const tasks = ref([])
    const loading = ref(false)
    const loadingMore = ref(false)
    const hasMore = ref(false)
    const page = ref(0)

    // Persist Proxmox task filters
    const TASK_FILTER_KEY = 'depl0y_task_filter'
    function loadTaskFilter() {
      try { return JSON.parse(sessionStorage.getItem(TASK_FILTER_KEY) || '{}') } catch { return {} }
    }
    const savedTaskFilter = loadTaskFilter()

    const selectedHostId = ref(route.params.hostId || savedTaskFilter.hostId || '')
    const selectedNode = ref(savedTaskFilter.node || '')
    const filterType = ref(savedTaskFilter.type || '')
    const customType = ref(savedTaskFilter.customType || '')
    const filterVmid = ref(savedTaskFilter.vmid || null)
    const filterStatus = ref(savedTaskFilter.status || '')
    const filterTimeRange = ref(savedTaskFilter.timeRange || '')

    let runningPollTimer = null
    const RUNNING_POLL_INTERVAL = 3000

    const stoppingTask = ref({})

    const detailTask = ref(null)
    const detailLog = ref('')
    const detailLoading = ref(false)
    const detailTaskRunning = ref(false)
    let detailPollTimer = null

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
      const title = task.status === 'OK' ? `Task completed: ${task.type}` : `Task failed: ${task.type}`
      const body = [task.id && `VMID: ${task.id}`, task.node && `Node: ${task.node}`].filter(Boolean).join(' | ') || task.upid
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
        if (running.length === 0) { clearInterval(pollInterval); pollInterval = null }
      }, 5000)
    }

    const runningTasks = computed(() => tasks.value.filter(t => !t.status || t.status === 'running'))

    async function pollRunningTasks() {
      const running = tasks.value.filter(t => !t.status || t.status === 'running')
      for (const task of running) {
        try {
          const res = await api.pveNode.taskStatus(task._hostId, task._node || task.node, encodeURIComponent(task.upid))
          const status = res.data?.status
          if (status && status !== 'running') {
            task.status = status
            if (typeof Notification !== 'undefined' && Notification.permission === 'granted') sendTaskNotification(task)
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

    const effectiveType = computed(() => filterType.value === 'custom' ? customType.value : filterType.value)

    const displayedTasks = computed(() => {
      let list = tasks.value

      // Status filter
      if (filterStatus.value === 'running') {
        list = list.filter(t => !t.status || t.status === 'running')
      } else if (filterStatus.value === 'OK') {
        list = list.filter(t => t.status === 'OK')
      } else if (filterStatus.value === 'error') {
        list = list.filter(t => t.status && t.status !== 'OK' && t.status !== 'running')
      } else {
        list = list.filter(t => t.status && t.status !== 'running')
      }

      // Time range filter
      if (filterTimeRange.value) {
        const nowSec = Date.now() / 1000
        const rangeMap = { '1h': 3600, '6h': 21600, '24h': 86400, '7d': 604800 }
        const rangeSec = rangeMap[filterTimeRange.value]
        if (rangeSec) {
          list = list.filter(t => t.starttime && (nowSec - t.starttime) <= rangeSec)
        }
      }

      return list
    })

    // Task duration helper
    function taskDuration(task) {
      if (!task.starttime) return '—'
      const end = task.endtime || Math.floor(Date.now() / 1000)
      const secs = end - task.starttime
      if (secs < 60) return `${secs}s`
      if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
      return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
    }

    // CSV export for displayed tasks
    function exportCsv() {
      const headers = ['Start Time', 'End Time', 'Node', 'VMID', 'Type', 'Status', 'Duration', 'UPID']
      const rows = displayedTasks.value.map(t => {
        const start = t.starttime ? new Date(t.starttime * 1000).toISOString() : ''
        const end = t.endtime ? new Date(t.endtime * 1000).toISOString() : ''
        return [
          start, end, t.node || t._node || '', t.id || '', t.type || '',
          t.status || 'running', taskDuration(t), `"${(t.upid || '').replace(/"/g, '""')}"`
        ].join(',')
      })
      const csv = [headers.join(','), ...rows].join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `tasks-${Date.now()}.csv`
      a.click()
      URL.revokeObjectURL(url)
    }

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
          const results = await Promise.all(nodeList.map(n => loadTasksForHostNode(selectedHostId.value, n.node_name || n.node, 0).catch(() => [])))
          collected = results.flat().sort((a, b) => (b.starttime || 0) - (a.starttime || 0)).slice(0, PAGE_SIZE)
        } else {
          const results = await Promise.all(hosts.value.map(async h => {
            try {
              const nRes = await api.proxmox.listNodes(h.id)
              const nodeList = nRes.data || []
              const taskResults = await Promise.all(nodeList.map(n => loadTasksForHostNode(h.id, n.node_name || n.node, 0).catch(() => [])))
              return taskResults.flat()
            } catch { return [] }
          }))
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
    const onLocalFilter = () => { /* computed filter */ }

    async function stopTask(task) {
      stoppingTask.value = { ...stoppingTask.value, [task._key]: true }
      try {
        await api.pveNode.stopTask(task._hostId, task._node || task.node, encodeURIComponent(task.upid))
        toast.success(`Task ${task.type} stop requested`)
        task.status = 'stopped'
        if (detailTask.value?._key === task._key) detailTask.value.status = 'stopped'
      } catch (err) {
        toast.error('Stop failed: ' + (err?.response?.data?.detail || err?.message))
      } finally {
        stoppingTask.value = { ...stoppingTask.value, [task._key]: false }
      }
    }

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
          try {
            const res = await api.pveNode.taskStatus(detailTask.value._hostId, detailTask.value._node || detailTask.value.node, encodeURIComponent(detailTask.value.upid))
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

    // Switch tabs — load data for active tab
    watch(activeTab, async (tab) => {
      if (tab === 'depl0y') {
        await loadDeplRunning()
        await loadDeplHistory()
        startDeplPoll()
      } else {
        stopDeplPoll()
        await loadTasks(true)
        startRunningPoll()
      }
    })

    onMounted(async () => {
      await loadHosts()
      if (selectedHostId.value) await loadNodes()

      // Always load Depl0y tab first
      await loadDeplRunning()
      await loadDeplHistory()
      startDeplPoll()

      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        startTaskPolling()
      }
    })

    onUnmounted(() => {
      if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
      stopRunningPoll()
      stopDeplPoll()
      if (detailPollTimer) { clearInterval(detailPollTimer); detailPollTimer = null }
      if (deplDetailPollTimer) { clearInterval(deplDetailPollTimer); deplDetailPollTimer = null }
    })

    const clearFilters = () => {
      filterType.value = ''
      filterStatus.value = ''
      filterVmid.value = null
      customType.value = ''
      filterTimeRange.value = ''
      onFilterChange()
    }

    // Persist task filters on change
    watch([selectedHostId, selectedNode, filterType, customType, filterVmid, filterStatus, filterTimeRange], () => {
      sessionStorage.setItem(TASK_FILTER_KEY, JSON.stringify({
        hostId: selectedHostId.value,
        node: selectedNode.value,
        type: filterType.value,
        customType: customType.value,
        vmid: filterVmid.value,
        status: filterStatus.value,
        timeRange: filterTimeRange.value,
      }))
    })

    return {
      activeTab,
      // Depl0y tasks
      deplRunning, deplHistory, deplHistoryLoading, stoppingDeplTask,
      deplDetailTask, deplDetailLog, deplDetailLoading,
      stopDeplTask, openDeplDetail, loadDeplHistory, deplStatusClass, formatTime,
      // Proxmox tasks
      hosts, nodes, tasks, loading, loadingMore, hasMore,
      selectedHostId, selectedNode, filterType, customType, filterVmid, filterStatus, filterTimeRange,
      runningTasks, displayedTasks, stoppingTask,
      detailTask, detailLog, detailLoading, detailTaskRunning,
      loadTasks, loadMore, onHostChange, onFilterChange, onLocalFilter,
      statusBadgeClass,
      notifPermission, requestNotifPermission,
      openTaskDetail, stopTask, exportLog, exportTaskLog, exportCsv,
      taskDuration,
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

/* ── Tab bar ── */
.tab-bar {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1.1rem;
  border: none;
  background: transparent;
  color: var(--text-muted, #888);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s, border-color 0.15s;
  border-radius: 0;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  color: var(--primary-color, #3b82f6);
  border-bottom-color: var(--primary-color, #3b82f6);
}

.tab-badge {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 9999px;
  font-weight: 700;
}

/* ── Progress bars ── */
.prog-track {
  height: 5px;
  background: rgba(255,255,255,0.1);
  border-radius: 3px;
  overflow: hidden;
}

.prog-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 3px;
  transition: width 1s ease;
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

.form-group--btn { flex: 0 0 auto; }

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

.table-container { overflow-x: auto; }

.upid-cell {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.clickable-row { cursor: pointer; }
.clickable-row:hover { background: var(--bg-secondary); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.anim-pulse { animation: pulse 1.5s ease-in-out infinite; }

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

.btn-xs { padding: 0.15rem 0.4rem; font-size: 0.75rem; }
.btn-sm { padding: 0.25rem 0.5rem; font-size: 0.875rem; }

/* ── Modals ── */
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
