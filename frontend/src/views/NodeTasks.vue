<template>
  <div class="node-tasks-page">
    <div class="page-header mb-2">
      <div class="breadcrumb text-sm text-muted mb-1">
        Proxmox Hosts &rsaquo; Host {{ hostId }} &rsaquo; {{ node }} &rsaquo; Tasks
      </div>
      <h2>Node Tasks</h2>
      <p class="text-muted">Task history and running jobs on node <strong>{{ node }}</strong></p>
    </div>

    <!-- Filter bar -->
    <div class="card mb-2">
      <div class="card-body filters-bar">
        <div class="form-group filter-group">
          <label class="form-label">Status</label>
          <select v-model="statusFilter" @change="applyFilters" class="form-control">
            <option value="">All</option>
            <option value="running">Running</option>
            <option value="stopped">Stopped</option>
            <option value="error">Error</option>
          </select>
        </div>
        <div class="form-group filter-group">
          <label class="form-label">Type</label>
          <input
            v-model="typeFilter"
            @input="applyFilters"
            class="form-control"
            placeholder="e.g. vzdump, qmstart..."
          />
        </div>
        <div class="filter-actions">
          <button @click="loadTasks(true)" class="btn btn-outline btn-sm">Refresh</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <h3>Tasks</h3>
        <span class="text-sm text-muted">{{ tasks.length }} loaded</span>
      </div>

      <div v-if="loading && tasks.length === 0" class="loading-spinner"></div>

      <div v-else-if="tasks.length === 0" class="text-center text-muted p-3">
        No tasks found.
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>UPID</th>
              <th>Type</th>
              <th>Status</th>
              <th>Start Time</th>
              <th>End Time</th>
              <th>User</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="task in tasks" :key="task.upid">
              <tr
                :class="['task-row', expandedUpid === task.upid ? 'task-row--expanded' : '']"
                @click="toggleExpand(task)"
              >
                <td>
                  <code class="upid-text">{{ truncateUpid(task.upid) }}</code>
                </td>
                <td>{{ formatTaskType(task) }}</td>
                <td>
                  <span :class="['badge', statusBadge(task)]">
                    {{ task.status || (isRunning(task) ? 'running' : '—') }}
                  </span>
                </td>
                <td class="text-sm">{{ task.starttime ? formatTime(task.starttime) : '—' }}</td>
                <td class="text-sm">{{ task.endtime ? formatTime(task.endtime) : '—' }}</td>
                <td class="text-sm">{{ task.user || '—' }}</td>
                <td @click.stop>
                  <div class="flex gap-1">
                    <button @click="openLogModal(task)" class="btn btn-outline btn-sm">Log</button>
                    <button
                      v-if="isRunning(task)"
                      @click="stopTask(task)"
                      class="btn btn-danger btn-sm"
                    >Stop</button>
                  </div>
                </td>
              </tr>
              <!-- Inline expanded log row -->
              <tr v-if="expandedUpid === task.upid" class="log-row">
                <td colspan="7">
                  <div class="inline-log">
                    <div v-if="loadingLog" class="text-muted text-sm p-2">Loading log...</div>
                    <pre v-else class="log-pre">{{ logContent || '(no output)' }}</pre>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Load more -->
      <div class="load-more-bar">
        <button
          @click="loadMore"
          class="btn btn-outline btn-sm"
          :disabled="loading || !hasMore"
        >
          {{ loading ? 'Loading...' : hasMore ? 'Load More' : 'No more tasks' }}
        </button>
      </div>
    </div>

    <!-- Task log modal -->
    <div v-if="logModal.show" class="modal" @click="closeLogModal">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <div>
            <h3>Task Log</h3>
            <div class="text-sm text-muted">{{ logModal.task?.type }} &mdash; {{ logModal.task?.upid }}</div>
          </div>
          <button @click="closeLogModal" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <div class="task-status-bar" v-if="logModal.status">
            <span class="text-sm text-muted">Status:</span>
            <span :class="['badge', statusBadge(logModal.status)]">
              {{ logModal.status.status || logModal.status.exitstatus || 'unknown' }}
            </span>
            <span class="text-sm text-muted ml-1">
              Started: {{ logModal.status.starttime ? formatTime(logModal.status.starttime) : '—' }}
            </span>
          </div>
          <div v-if="loadingModalLog" class="text-muted text-sm p-2">Loading log...</div>
          <pre v-else class="log-pre log-pre--modal">{{ logModal.content || '(no output)' }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import { formatTaskType } from '@/utils/proxmox'

const route = useRoute()
const toast = useToast()

const hostId = ref(route.params.hostId)
const node = ref(route.params.node)

const tasks = ref([])
const loading = ref(false)
const statusFilter = ref('')
const typeFilter = ref('')
const pageStart = ref(0)
const PAGE_SIZE = 50
const hasMore = ref(true)

const expandedUpid = ref(null)
const loadingLog = ref(false)
const logContent = ref('')

const logModal = ref({ show: false, task: null, content: '', status: null })
const loadingModalLog = ref(false)

let autoRefreshTimer = null

function isRunning(task) {
  return !task.endtime || task.status === 'running'
}

function truncateUpid(upid) {
  if (!upid) return '—'
  if (upid.length <= 40) return upid
  return upid.slice(0, 20) + '...' + upid.slice(-12)
}

function formatTime(epoch) {
  if (!epoch) return '—'
  return new Date(epoch * 1000).toLocaleString()
}

function statusBadge(task) {
  const s = (task.status || task.exitstatus || '').toLowerCase()
  if (s === 'ok' || s === 'stopped') return 'badge-success'
  if (s === 'running') return 'badge-info'
  if (s === 'error' || s.startsWith('err')) return 'badge-danger'
  if (!task.endtime) return 'badge-info'
  return 'badge-warning'
}

async function loadTasks(reset = false) {
  if (reset) {
    tasks.value = []
    pageStart.value = 0
    hasMore.value = true
  }
  loading.value = true
  try {
    const params = {
      limit: PAGE_SIZE,
      start: pageStart.value,
    }
    if (statusFilter.value) params.statusfilter = statusFilter.value
    if (typeFilter.value) params.typefilter = typeFilter.value

    const res = await api.pveNode.listTasks(hostId.value, node.value, params)
    const incoming = res.data || []
    if (reset) {
      tasks.value = incoming
    } else {
      tasks.value = [...tasks.value, ...incoming]
    }
    hasMore.value = incoming.length === PAGE_SIZE
  } catch (err) {
    console.error('Failed to load tasks:', err)
    toast.error('Failed to load tasks')
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  loadTasks(true)
}

function loadMore() {
  pageStart.value += PAGE_SIZE
  loadTasks(false)
}

async function toggleExpand(task) {
  if (expandedUpid.value === task.upid) {
    expandedUpid.value = null
    logContent.value = ''
    return
  }
  expandedUpid.value = task.upid
  logContent.value = ''
  loadingLog.value = true
  try {
    const res = await api.pveNode.taskLog(hostId.value, node.value, encodeURIComponent(task.upid))
    const lines = res.data || []
    logContent.value = Array.isArray(lines)
      ? lines.map(l => l.t || l).join('\n')
      : String(lines)
  } catch (err) {
    logContent.value = 'Failed to load log.'
  } finally {
    loadingLog.value = false
  }
}

async function openLogModal(task) {
  logModal.value = { show: true, task, content: '', status: null }
  loadingModalLog.value = true
  try {
    const [logRes, statusRes] = await Promise.all([
      api.pveNode.taskLog(hostId.value, node.value, encodeURIComponent(task.upid)),
      api.pveNode.taskStatus(hostId.value, node.value, encodeURIComponent(task.upid)),
    ])
    const lines = logRes.data || []
    logModal.value.content = Array.isArray(lines)
      ? lines.map(l => l.t || l).join('\n')
      : String(lines)
    logModal.value.status = statusRes.data || null
  } catch (err) {
    logModal.value.content = 'Failed to load log.'
  } finally {
    loadingModalLog.value = false
  }
}

function closeLogModal() {
  logModal.value = { show: false, task: null, content: '', status: null }
}

async function stopTask(task) {
  if (!confirm(`Stop task ${task.type} (${truncateUpid(task.upid)})?`)) return
  try {
    await api.pveNode.stopTask(hostId.value, node.value, encodeURIComponent(task.upid))
    toast.success('Task stop requested')
    await loadTasks(true)
  } catch (err) {
    console.error('Failed to stop task:', err)
    toast.error('Failed to stop task')
  }
}

function startAutoRefresh() {
  autoRefreshTimer = setInterval(async () => {
    const hasRunning = tasks.value.some(t => isRunning(t))
    if (hasRunning) {
      await loadTasks(true)
    }
  }, 5000)
}

onMounted(() => {
  loadTasks(true)
  startAutoRefresh()
})

onBeforeUnmount(() => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
})
</script>

<style scoped>
.node-tasks-page {
  padding: 0;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.breadcrumb {
  margin-bottom: 0.25rem;
}

.card-body.filters-bar {
  padding: 1rem 1.5rem;
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  flex-wrap: wrap;
}

.filter-group {
  margin-bottom: 0;
  min-width: 180px;
}

.filter-actions {
  padding-bottom: 0.1rem;
}

.upid-text {
  font-size: 0.75rem;
  word-break: break-all;
  color: var(--text-secondary);
}

.task-row {
  cursor: pointer;
  transition: background 0.1s;
}

.task-row:hover {
  background: var(--bg-secondary);
}

.task-row--expanded {
  background: rgba(99, 102, 241, 0.08);
}

.log-row td {
  padding: 0;
  background: var(--bg-secondary);
}

.inline-log {
  max-height: 300px;
  overflow-y: auto;
}

.log-pre {
  margin: 0;
  padding: 1rem;
  font-size: 0.78rem;
  line-height: 1.5;
  color: #a6e3a1;
  background: #0d1117;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Courier New', Courier, monospace;
}

.log-pre--modal {
  max-height: 500px;
  overflow-y: auto;
  border-radius: 0.375rem;
}

.load-more-bar {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-color);
  text-align: center;
}

.task-status-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.mb-2 { margin-bottom: 1rem; }
.mt-1 { margin-top: 0.25rem; }
.ml-1 { margin-left: 0.5rem; }
.p-2 { padding: 0.5rem 1rem; }
.p-3 { padding: 1.5rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-muted, #888); }
.text-center { text-align: center; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }

.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card, #1a1a2e);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  max-width: 640px;
  width: 95%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-content.modal-large {
  max-width: 900px;
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.modal-header h3 {
  margin: 0 0 0.25rem 0;
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.75rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  flex-shrink: 0;
  margin-left: 1rem;
}

.modal-body {
  padding: 1.5rem;
  color: var(--text-primary);
}
</style>
