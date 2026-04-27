<template>
  <div class="tasks-page">
    <div class="page-header mb-2">
      <div>
        <h2>Task Log</h2>
        <p class="text-muted">Proxmox task history and running jobs across all nodes</p>
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

    <!-- ───────────── RUNNING TASKS (always visible) ───────────── -->
    <div class="mb-2">
      <div class="section-header mb-1">
        <h3 class="section-title">
          Running Tasks
          <span v-if="deplRunning.length" class="badge badge-warning ml-1">{{ deplRunning.length }}</span>
        </h3>
        <span class="refresh-countdown text-xs text-muted">
          Refresh in {{ refreshCountdown }}s
        </span>
      </div>

      <div v-if="deplRunning.length === 0" class="card">
        <div class="empty-state empty-state--compact">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          <p class="text-muted text-sm">No tasks running</p>
        </div>
      </div>

      <div v-else class="running-cards">
        <div
          v-for="task in deplRunning"
          :key="task.upid"
          class="task-card"
          @click="openDeplDetail(task)"
        >
          <div class="task-card-header">
            <div class="task-card-icon" :class="taskTypeColorClass(task.task_type || task.type)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" v-html="taskTypeIcon(task.task_type || task.type)"></svg>
            </div>
            <div class="task-card-info">
              <div class="task-card-desc">{{ task.description || task.task_type || task.type || 'Task' }}</div>
              <div class="task-card-meta">
                <span class="task-meta-badge">{{ task.node }}</span>
                <span v-if="task.vmid || task.id" class="task-meta-badge">VM {{ task.vmid || task.id }}</span>
                <span v-if="task.started_at || task.starttime" class="task-meta-elapsed">{{ deplElapsed(task) }}</span>
              </div>
            </div>
            <div class="task-card-actions" @click.stop>
              <button
                class="btn btn-danger btn-xs"
                :disabled="stoppingDeplTask[task.upid]"
                @click.stop="stopDeplTask(task)"
              >
                {{ stoppingDeplTask[task.upid] ? '...' : 'Stop' }}
              </button>
            </div>
          </div>

          <!-- Progress bar -->
          <div class="task-card-progress">
            <div class="prog-track">
              <div class="prog-fill prog-fill--indeterminate"></div>
            </div>
            <span class="prog-label text-xs text-muted">running</span>
          </div>
        </div>
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

      <!-- Depl0y Task History -->
      <div class="card">
        <div class="card-header">
          <h3>History <span class="text-muted text-sm">(this session)</span></h3>
          <button @click="loadDeplHistory" class="btn btn-outline btn-sm">Refresh</button>
        </div>

        <!-- Search bar for history -->
        <div v-if="deplHistory.length > 0" class="history-search-bar">
          <input
            v-model="deplSearchQuery"
            class="form-control form-control-sm"
            placeholder="Search by UPID, description, type…"
          />
        </div>

        <SkeletonLoader v-if="deplHistoryLoading" type="table" :count="5" />
        <div v-else-if="deplHistoryFiltered.length === 0" class="empty-state">
          <div class="empty-icon-wrap">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <h4 class="empty-title">{{ deplSearchQuery ? 'No matching tasks' : 'No completed Depl0y tasks' }}</h4>
          <p class="empty-subtitle">
            {{ deplSearchQuery ? 'Try a different search term.' : 'Tasks initiated through Depl0y this session will appear here.' }}
          </p>
        </div>
        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Description</th>
                <th>Node</th>
                <th>VMID</th>
                <th>Started</th>
                <th>Duration</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="task in deplHistoryFiltered" :key="task.upid">
                <tr
                  class="clickable-row"
                  :class="{ 'row-expanded': expandedDeplRows.has(task.upid) }"
                  @click="toggleDeplRowExpand(task)"
                >
                  <td class="text-sm">
                    <span class="type-chip" :class="taskTypeColorClass(task.task_type)">{{ task.task_type }}</span>
                  </td>
                  <td class="text-sm">{{ task.description || '—' }}</td>
                  <td class="text-sm">{{ task.node }}</td>
                  <td class="text-sm">{{ task.vmid || '—' }}</td>
                  <td class="text-sm text-muted">{{ formatTime(task.started_at) }}</td>
                  <td class="text-sm text-muted">{{ deplDuration(task) }}</td>
                  <td>
                    <span :class="deplStatusClass(task.exit_status)">{{ task.exit_status || task.status }}</span>
                  </td>
                </tr>
                <!-- Expanded log row -->
                <tr v-if="expandedDeplRows.has(task.upid)" class="log-expand-row">
                  <td colspan="7">
                    <div class="log-expand-panel">
                      <div class="log-expand-header">
                        <span class="text-xs text-muted">UPID: <code>{{ task.upid }}</code></span>
                        <div class="log-expand-actions">
                          <button class="btn btn-outline btn-xs" @click.stop="openDeplDetail(task)">
                            Full Detail
                          </button>
                        </div>
                      </div>
                      <div v-if="expandedDeplLogs[task.upid] === undefined" class="text-xs text-muted">Loading log...</div>
                      <pre v-else class="task-log task-log--compact">{{ expandedDeplLogs[task.upid] || 'No log output.' }}</pre>
                    </div>
                  </td>
                </tr>
              </template>
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
            <div class="form-group">
              <label class="form-label">Search</label>
              <input v-model="pveSearch" @input="onLocalFilter" class="form-control" placeholder="UPID or type…" />
            </div>
            <div class="form-group form-group--btn">
              <button @click="loadTasks(true)" class="btn btn-outline btn-sm">Refresh</button>
              <button @click="clearFilters" class="btn btn-outline btn-sm">Clear</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Task History Table -->
      <div class="card">
        <div class="card-header">
          <h3>Task History</h3>
          <span class="text-xs text-muted">{{ displayedTasks.length }} tasks</span>
        </div>
        <SkeletonLoader v-if="loading" type="table" :count="8" />
        <div v-else-if="displayedTasks.length === 0" class="empty-state">
          <div class="empty-icon-wrap">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
          </div>
          <h4 class="empty-title">No tasks to show</h4>
          <p class="empty-subtitle">No Proxmox tasks match your current filters.</p>
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
                <th class="upid-col">UPID</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="task in displayedTasks" :key="task._key">
                <tr
                  class="clickable-row"
                  :class="{ 'row-expanded': expandedPveRows.has(task._key) }"
                  @click="togglePveRowExpand(task)"
                >
                  <td class="text-sm">{{ task.starttime ? new Date(task.starttime * 1000).toLocaleString() : '—' }}</td>
                  <td class="text-sm">{{ task.node || task._node }}</td>
                  <td class="text-sm">{{ task.id || '—' }}</td>
                  <td class="text-sm">
                    <span class="type-chip" :class="taskTypeColorClass(task.type)">{{ task.type }}</span>
                  </td>
                  <td>
                    <span :class="pveStatusBadgeClass(task.status)">{{ task.status || 'running' }}</span>
                  </td>
                  <td class="text-sm text-muted">{{ taskDuration(task) }}</td>
                  <td class="text-sm text-muted upid-cell">{{ task.upid }}</td>
                  <td>
                    <button
                      class="btn btn-outline btn-xs"
                      @click.stop="openTaskDetail(task)"
                    >Detail</button>
                  </td>
                </tr>
                <!-- Expanded inline log -->
                <tr v-if="expandedPveRows.has(task._key)" class="log-expand-row">
                  <td colspan="8">
                    <div class="log-expand-panel">
                      <div class="log-expand-header">
                        <span class="text-xs text-muted">UPID: <code>{{ task.upid }}</code></span>
                        <div class="log-expand-actions">
                          <button class="btn btn-outline btn-xs" @click.stop="openTaskDetail(task)">
                            Full Detail
                          </button>
                        </div>
                      </div>
                      <div v-if="expandedPveLogs[task._key] === undefined" class="text-xs text-muted">Loading log...</div>
                      <pre v-else class="task-log task-log--compact">{{ expandedPveLogs[task._key] || 'No log output.' }}</pre>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <div v-if="!loading && hasMore" class="text-center load-more-bar">
          <button @click="loadMore" class="btn btn-outline" :disabled="loadingMore">
            {{ loadingMore ? 'Loading...' : 'Load More' }}
          </button>
        </div>
      </div>

    </template>

    <!-- ── Proxmox Task Detail Modal ── -->
    <Teleport to="body">
      <div v-if="detailTask" class="modal-backdrop" @click.self="closeDetail">
        <div class="modal-box">
          <div class="modal-header">
            <h3>
              <span class="type-chip" :class="taskTypeColorClass(detailTask.type)" style="margin-right:0.5rem">{{ detailTask.type }}</span>
              Task Detail
            </h3>
            <button @click="closeDetail" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <!-- Metadata grid -->
            <div class="detail-grid mb-2">
              <div class="detail-kv"><span class="detail-key">Type</span><span class="detail-val">{{ detailTask.type }}</span></div>
              <div class="detail-kv"><span class="detail-key">Node</span><span class="detail-val">{{ detailTask.node || detailTask._node }}</span></div>
              <div v-if="detailTask.id" class="detail-kv"><span class="detail-key">VMID</span><span class="detail-val">{{ detailTask.id }}</span></div>
              <div class="detail-kv">
                <span class="detail-key">Status</span>
                <span :class="pveStatusBadgeClass(detailTask.status)" style="margin-left:0">{{ detailTask.status || 'running' }}</span>
              </div>
              <div class="detail-kv"><span class="detail-key">Started</span><span class="detail-val">{{ detailTask.starttime ? new Date(detailTask.starttime * 1000).toLocaleString() : '—' }}</span></div>
              <div v-if="detailTask.endtime" class="detail-kv"><span class="detail-key">Ended</span><span class="detail-val">{{ new Date(detailTask.endtime * 1000).toLocaleString() }}</span></div>
              <div v-if="detailTask.pid" class="detail-kv"><span class="detail-key">PID</span><span class="detail-val">{{ detailTask.pid }}</span></div>
              <div v-if="detailTask.pstart" class="detail-kv"><span class="detail-key">pstart</span><span class="detail-val">{{ detailTask.pstart }}</span></div>
              <div v-if="detailTask.user" class="detail-kv"><span class="detail-key">User</span><span class="detail-val">{{ detailTask.user }}</span></div>
              <div class="detail-kv detail-kv--full">
                <span class="detail-key">UPID</span>
                <code class="detail-upid">{{ detailTask.upid }}</code>
              </div>
            </div>

            <div class="log-header">
              <strong class="text-sm">Log Output</strong>
              <div style="display:flex;gap:0.4rem">
                <button class="btn btn-outline btn-xs" @click="copyDetailLog" :disabled="!detailLog">
                  {{ logCopied ? 'Copied!' : 'Copy' }}
                </button>
                <button class="btn btn-outline btn-xs" @click="exportTaskLog" :disabled="!detailLog">Export</button>
              </div>
            </div>

            <div v-if="detailLoading" class="text-muted text-sm mt-1">Loading log...</div>
            <pre v-else ref="detailLogEl" class="task-log">{{ detailLog || 'No log output.' }}</pre>

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
            <button @click="closeDetail" class="btn btn-outline">Close</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Depl0y Task Detail Modal ── -->
    <Teleport to="body">
      <div v-if="deplDetailTask" class="modal-backdrop" @click.self="deplDetailTask = null">
        <div class="modal-box">
          <div class="modal-header">
            <h3>
              <span class="type-chip" :class="taskTypeColorClass(deplDetailTask.task_type)" style="margin-right:0.5rem">{{ deplDetailTask.task_type }}</span>
              Depl0y Task Detail
            </h3>
            <button @click="deplDetailTask = null" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <!-- Metadata grid -->
            <div class="detail-grid mb-2">
              <div class="detail-kv detail-kv--full"><span class="detail-key">Description</span><span class="detail-val">{{ deplDetailTask.description || '—' }}</span></div>
              <div class="detail-kv"><span class="detail-key">Type</span><span class="detail-val">{{ deplDetailTask.task_type }}</span></div>
              <div class="detail-kv"><span class="detail-key">Node</span><span class="detail-val">{{ deplDetailTask.node }}</span></div>
              <div v-if="deplDetailTask.vmid" class="detail-kv"><span class="detail-key">VMID</span><span class="detail-val">{{ deplDetailTask.vmid }}</span></div>
              <div class="detail-kv">
                <span class="detail-key">Status</span>
                <span :class="deplDetailTask.status === 'running' ? 'badge badge-warning' : deplStatusClass(deplDetailTask.exit_status)" style="margin-left:0">
                  {{ deplDetailTask.status === 'running' ? 'running' : (deplDetailTask.exit_status || deplDetailTask.status) }}
                </span>
              </div>
              <div class="detail-kv"><span class="detail-key">Started</span><span class="detail-val">{{ formatTime(deplDetailTask.started_at) }}</span></div>
              <div v-if="deplDetailTask.finished_at" class="detail-kv"><span class="detail-key">Finished</span><span class="detail-val">{{ formatTime(deplDetailTask.finished_at) }}</span></div>
              <div class="detail-kv detail-kv--full">
                <span class="detail-key">UPID</span>
                <code class="detail-upid">{{ deplDetailTask.upid }}</code>
              </div>
            </div>

            <div v-if="deplDetailTask.progress !== undefined && deplDetailTask.status === 'running'" class="mb-2">
              <div class="prog-track">
                <div class="prog-fill" :style="{ width: `${deplDetailTask.progress || 0}%` }"></div>
              </div>
              <span class="text-xs text-muted">{{ deplDetailTask.progress }}%</span>
            </div>

            <div class="log-header">
              <strong class="text-sm">Log Output</strong>
              <div style="display:flex;gap:0.4rem">
                <button class="btn btn-outline btn-xs" @click="copyDeplLog" :disabled="!deplDetailLog">
                  {{ deplLogCopied ? 'Copied!' : 'Copy' }}
                </button>
              </div>
            </div>
            <div v-if="deplDetailLoading" class="text-muted text-sm mt-1">Loading log...</div>
            <pre v-else ref="deplLogEl" class="task-log">{{ deplDetailLog || 'No log output.' }}</pre>
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
    </Teleport>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

const PAGE_SIZE = 50
const DEPL_POLL_INTERVAL = 5000   // 5s refresh for Depl0y running tasks
const RUNNING_POLL_INTERVAL = 5000
const LIVE_RUNNING_INTERVAL = 5000  // 5s live Proxmox running task poll

export default {
  name: 'Tasks',
  components: { SkeletonLoader },
  setup() {
    const route = useRoute()
    const toast = useToast()

    // ── Tab state ──────────────────────────────────────────────────────────
    const activeTab = ref('depl0y')

    // ── Countdown timer ────────────────────────────────────────────────────
    const refreshCountdown = ref(5)
    let countdownTimer = null

    function startCountdown() {
      if (countdownTimer) return
      refreshCountdown.value = 5
      countdownTimer = setInterval(() => {
        refreshCountdown.value -= 1
        if (refreshCountdown.value <= 0) refreshCountdown.value = 5
      }, 1000)
    }

    function stopCountdown() {
      if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
    }

    // ── Depl0y Tasks state ─────────────────────────────────────────────────
    const deplRunning = ref([])
    const deplHistory = ref([])
    const deplHistoryLoading = ref(false)
    const deplSearchQuery = ref('')
    const stoppingDeplTask = ref({})
    const deplDetailTask = ref(null)
    const deplDetailLog = ref('')
    const deplDetailLoading = ref(false)
    const deplLogCopied = ref(false)
    const expandedDeplRows = ref(new Set())
    const expandedDeplLogs = ref({})
    const deplLogEl = ref(null)
    let deplDetailPollTimer = null
    let deplPollTimer = null

    const deplHistoryFiltered = computed(() => {
      const q = deplSearchQuery.value.trim().toLowerCase()
      if (!q) return deplHistory.value
      return deplHistory.value.filter(t =>
        (t.upid || '').toLowerCase().includes(q) ||
        (t.description || '').toLowerCase().includes(q) ||
        (t.task_type || '').toLowerCase().includes(q) ||
        (t.node || '').toLowerCase().includes(q)
      )
    })

    async function loadDeplRunning() {
      try {
        const res = await api.tasks.getRunning()
        deplRunning.value = res.data || []
      } catch { /* ignore */ }
    }

    async function loadDeplHistory() {
      deplHistoryLoading.value = true
      try {
        const res = await api.tasks.getHistory({ limit: 200 })
        deplHistory.value = res.data || []
      } catch { /* ignore */ } finally {
        deplHistoryLoading.value = false
      }
    }

    function startDeplPoll() {
      if (deplPollTimer) return
      startCountdown()
      deplPollTimer = setInterval(loadDeplRunning, DEPL_POLL_INTERVAL)
    }

    function stopDeplPoll() {
      stopCountdown()
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

    async function toggleDeplRowExpand(task) {
      const upid = task.upid
      const newSet = new Set(expandedDeplRows.value)
      if (newSet.has(upid)) {
        newSet.delete(upid)
        expandedDeplRows.value = newSet
      } else {
        newSet.add(upid)
        expandedDeplRows.value = newSet
        if (expandedDeplLogs.value[upid] === undefined) {
          expandedDeplLogs.value = { ...expandedDeplLogs.value, [upid]: undefined }
          try {
            const res = await api.tasks.getLog(task.host_id, task.node, task.upid)
            expandedDeplLogs.value = { ...expandedDeplLogs.value, [upid]: (res.data?.lines || []).join('\n') }
          } catch {
            expandedDeplLogs.value = { ...expandedDeplLogs.value, [upid]: 'Failed to load log.' }
          }
        }
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
          const found = deplRunning.value.find(t => t.upid === deplDetailTask.value?.upid)
          if (found) {
            deplDetailTask.value = { ...found }
          } else if (deplDetailTask.value?.status === 'running') {
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

    async function copyDeplLog() {
      try {
        await navigator.clipboard.writeText(deplDetailLog.value)
        deplLogCopied.value = true
        setTimeout(() => { deplLogCopied.value = false }, 2000)
      } catch { /* ignore */ }
    }

    function deplStatusClass(exitStatus) {
      if (exitStatus === 'OK') return 'badge badge-success'
      if (!exitStatus) return 'badge badge-warning'
      return 'badge badge-danger'
    }

    // Coerce mixed timestamp formats (ISO string, Unix seconds, Unix ms) to a Date.
    // PVE/PBS return starttime as Unix seconds; depl0y-tracked tasks use ISO strings.
    function _toDate(t) {
      if (t == null) return null
      if (t instanceof Date) return t
      if (typeof t === 'number') return new Date(t < 1e12 ? t * 1000 : t)
      if (typeof t === 'string') {
        if (/^\d+(\.\d+)?$/.test(t)) {
          const n = Number(t)
          return new Date(n < 1e12 ? n * 1000 : n)
        }
        return new Date(t)
      }
      return null
    }

    function _fmtDur(secs) {
      if (secs == null || !isFinite(secs) || secs < 0) return ''
      const s = Math.floor(secs)
      if (s < 60) return `${s}s`
      const m = Math.floor(s / 60)
      if (m < 60) return `${m}m ${s % 60}s`
      const h = Math.floor(m / 60)
      if (h < 24) return `${h}h ${m % 60}m`
      const d = Math.floor(h / 24)
      return `${d}d ${h % 24}h ${m % 60}m`
    }

    function deplElapsed(task) {
      const d = _toDate(task.started_at)
      if (!d || isNaN(d.getTime())) return ''
      return _fmtDur((Date.now() - d.getTime()) / 1000)
    }

    function deplDuration(task) {
      const start = _toDate(task.started_at)
      if (!start || isNaN(start.getTime())) return '—'
      const endDate = _toDate(task.finished_at)
      const end = endDate && !isNaN(endDate.getTime()) ? endDate.getTime() : Date.now()
      return _fmtDur((end - start.getTime()) / 1000) || '—'
    }

    function formatTime(t) {
      const d = _toDate(t)
      if (!d || isNaN(d.getTime())) return '—'
      return d.toLocaleString()
    }

    function formatAge(t) {
      const d = _toDate(t)
      if (!d || isNaN(d.getTime())) return ''
      const dur = _fmtDur((Date.now() - d.getTime()) / 1000)
      return dur ? `${dur} ago` : ''
    }

    // ── Proxmox Tasks ──────────────────────────────────────────────────────

    const hosts = ref([])
    const nodes = ref([])
    const tasks = ref([])
    const loading = ref(false)
    const loadingMore = ref(false)
    const hasMore = ref(false)
    const page = ref(0)
    const pveSearch = ref('')

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
    let liveRunningTimer = null
    const liveRunning = ref([])   // live running tasks polled directly from Proxmox
    const stoppingTask = ref({})
    const detailTask = ref(null)
    const detailLog = ref('')
    const detailLoading = ref(false)
    const detailTaskRunning = ref(false)
    const logCopied = ref(false)
    const detailLogEl = ref(null)
    const expandedPveRows = ref(new Set())
    const expandedPveLogs = ref({})
    let detailPollTimer = null

    const notifPermission = ref(typeof Notification !== 'undefined' ? Notification.permission : 'denied')

    const requestNotifPermission = async () => {
      if (typeof Notification === 'undefined') return
      const result = await Notification.requestPermission()
      notifPermission.value = result
    }

    const sendTaskNotification = (task) => {
      if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
      const title = task.status === 'OK' ? `Task completed: ${task.type}` : `Task failed: ${task.type}`
      const body = [task.id && `VMID: ${task.id}`, task.node && `Node: ${task.node}`].filter(Boolean).join(' | ') || task.upid
      new Notification(title, { body, icon: '/favicon.ico' })
    }

    // runningTasks shows liveRunning (from direct Proxmox poll) merged with
    // any tasks already in tasks.value that are still marked running.
    const runningTasks = computed(() => {
      const liveKeys = new Set(liveRunning.value.map(t => t.upid))
      // Include tasks from liveRunning + tasks.value that are running but not yet in liveRunning
      const fromHistory = tasks.value.filter(t => (!t.status || t.status === 'running') && !liveKeys.has(t.upid))
      return [...liveRunning.value, ...fromHistory]
    })

    async function fetchLivePveRunning() {
      // Query Proxmox directly for currently-running tasks across all visible hosts
      const collected = []
      const hostsToQuery = hosts.value.length ? hosts.value : []
      for (const h of hostsToQuery) {
        try {
          const nodeList = nodes.value.length && selectedHostId.value === h.id
            ? nodes.value
            : (await api.proxmox.listNodes(h.id).catch(() => ({ data: [] }))).data || []
          for (const n of nodeList) {
            const nodeName = n.node_name || n.node
            try {
              const res = await api.pveNode.tasks(h.id, nodeName, { limit: 100 })
              for (const t of (res.data || [])) {
                // Only include tasks that are currently running (empty status = running in Proxmox)
                if (!t.status || t.status === 'running') {
                  collected.push({
                    ...t,
                    _key: `${h.id}-${nodeName}-${t.upid}`,
                    _hostId: h.id,
                    _node: nodeName,
                  })
                }
              }
            } catch { /* ignore per-node error */ }
          }
        } catch { /* ignore per-host error */ }
      }
      liveRunning.value = collected
    }

    async function pollRunningTasks() {
      // Also update status in tasks.value for completed notification
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

    function startLiveRunningPoll() {
      if (liveRunningTimer) return
      fetchLivePveRunning()
      liveRunningTimer = setInterval(fetchLivePveRunning, LIVE_RUNNING_INTERVAL)
    }

    function stopLiveRunningPoll() {
      if (liveRunningTimer) { clearInterval(liveRunningTimer); liveRunningTimer = null }
      liveRunning.value = []
    }

    const effectiveType = computed(() => filterType.value === 'custom' ? customType.value : filterType.value)

    const displayedTasks = computed(() => {
      let list = tasks.value

      if (filterStatus.value === 'running') {
        list = list.filter(t => !t.status || t.status === 'running')
      } else if (filterStatus.value === 'OK') {
        list = list.filter(t => t.status === 'OK')
      } else if (filterStatus.value === 'error') {
        list = list.filter(t => t.status && t.status !== 'OK' && t.status !== 'running')
      } else {
        list = list.filter(t => t.status && t.status !== 'running')
      }

      if (filterTimeRange.value) {
        const nowSec = Date.now() / 1000
        const rangeMap = { '1h': 3600, '6h': 21600, '24h': 86400, '7d': 604800 }
        const rangeSec = rangeMap[filterTimeRange.value]
        if (rangeSec) list = list.filter(t => t.starttime && (nowSec - t.starttime) <= rangeSec)
      }

      if (pveSearch.value.trim()) {
        const q = pveSearch.value.trim().toLowerCase()
        list = list.filter(t =>
          (t.upid || '').toLowerCase().includes(q) ||
          (t.type || '').toLowerCase().includes(q) ||
          (t.id || '').toString().includes(q)
        )
      }

      return list
    })

    function taskDuration(task) {
      if (!task.starttime) return '—'
      const end = task.endtime || Math.floor(Date.now() / 1000)
      const secs = end - task.starttime
      if (secs < 60) return `${secs}s`
      if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
      return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
    }

    function pveElapsed(task) {
      if (!task.starttime) return ''
      const secs = Math.floor(Date.now() / 1000) - task.starttime
      if (secs < 60) return `${secs}s`
      if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
      return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
    }

    async function togglePveRowExpand(task) {
      const key = task._key
      const newSet = new Set(expandedPveRows.value)
      if (newSet.has(key)) {
        newSet.delete(key)
        expandedPveRows.value = newSet
      } else {
        newSet.add(key)
        expandedPveRows.value = newSet
        if (expandedPveLogs.value[key] === undefined) {
          expandedPveLogs.value = { ...expandedPveLogs.value, [key]: undefined }
          try {
            const res = await api.pveNode.taskLog(task._hostId, task._node || task.node, encodeURIComponent(task.upid))
            expandedPveLogs.value = { ...expandedPveLogs.value, [key]: (res.data?.lines || res.data || []).join('\n') }
          } catch {
            expandedPveLogs.value = { ...expandedPveLogs.value, [key]: 'Failed to load log.' }
          }
        }
      }
    }

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
    const onLocalFilter = () => { /* computed filter handles this */ }

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

    function closeDetail() {
      detailTask.value = null
      if (detailPollTimer) { clearInterval(detailPollTimer); detailPollTimer = null }
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

    async function copyDetailLog() {
      try {
        await navigator.clipboard.writeText(detailLog.value)
        logCopied.value = true
        setTimeout(() => { logCopied.value = false }, 2000)
      } catch { /* ignore */ }
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

    function pveStatusBadgeClass(status) {
      if (status === 'OK') return 'badge badge-success'
      if (!status || status === 'running') return 'badge badge-warning'
      return 'badge badge-danger'
    }

    // ── Task type helpers ──────────────────────────────────────────────────

    const TYPE_COLORS = {
      qmigrate: 'type-blue',
      vzdump: 'type-purple',
      qmcreate: 'type-green',
      qmdestroy: 'type-red',
      qmstart: 'type-teal',
      qmstop: 'type-orange',
      replicate: 'type-cyan',
      'vm-deploy': 'type-green',
      'vm-clone': 'type-blue',
      'vm-destroy': 'type-red',
    }

    function taskTypeColorClass(type) {
      return TYPE_COLORS[type] || 'type-gray'
    }

    const TYPE_ICONS = {
      qmigrate: '<path d="M5 12h14M12 5l7 7-7 7"/>',
      vzdump: '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
      qmcreate: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>',
      qmdestroy: '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',
      qmstart: '<polygon points="5 3 19 12 5 21 5 3"/>',
      qmstop: '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>',
      replicate: '<polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 014-4h14M7 23l-4-4 4-4"/><path d="M21 13v2a4 4 0 01-4 4H3"/>',
    }

    function taskTypeIcon(type) {
      return TYPE_ICONS[type] || '<circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"/>'
    }

    const clearFilters = () => {
      filterType.value = ''
      filterStatus.value = ''
      filterVmid.value = null
      customType.value = ''
      filterTimeRange.value = ''
      pveSearch.value = ''
      onFilterChange()
    }

    watch(activeTab, async (tab) => {
      if (tab === 'depl0y') {
        stopRunningPoll()
        stopLiveRunningPoll()
        await loadDeplHistory()
        // deplRunning poll keeps running regardless of tab (started in onMounted)
      } else {
        await loadTasks(true)
        startRunningPoll()
        startLiveRunningPoll()
      }
    })

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

    onMounted(async () => {
      await loadHosts()
      if (selectedHostId.value) await loadNodes()
      await loadDeplRunning()
      await loadDeplHistory()
      startDeplPoll()
    })

    onUnmounted(() => {
      stopRunningPoll()
      stopLiveRunningPoll()
      stopDeplPoll()
      stopCountdown()
      if (detailPollTimer) { clearInterval(detailPollTimer); detailPollTimer = null }
      if (deplDetailPollTimer) { clearInterval(deplDetailPollTimer); deplDetailPollTimer = null }
    })

    return {
      activeTab,
      refreshCountdown,
      // Depl0y tasks
      deplRunning, deplHistory, deplHistoryLoading, deplSearchQuery, deplHistoryFiltered,
      stoppingDeplTask, deplDetailTask, deplDetailLog, deplDetailLoading, deplLogCopied,
      expandedDeplRows, expandedDeplLogs, deplLogEl,
      stopDeplTask, openDeplDetail, loadDeplHistory, deplStatusClass, formatTime, formatAge,
      deplElapsed, deplDuration, toggleDeplRowExpand, copyDeplLog,
      // Proxmox tasks
      hosts, nodes, tasks, loading, loadingMore, hasMore,
      selectedHostId, selectedNode, filterType, customType, filterVmid, filterStatus, filterTimeRange,
      pveSearch,
      runningTasks, liveRunning, displayedTasks, stoppingTask,
      detailTask, detailLog, detailLoading, detailTaskRunning, logCopied, detailLogEl,
      expandedPveRows, expandedPveLogs,
      loadTasks, loadMore, onHostChange, onFilterChange, onLocalFilter,
      pveStatusBadgeClass,
      notifPermission, requestNotifPermission,
      openTaskDetail, closeDetail, stopTask, exportLog, exportTaskLog, exportCsv,
      taskDuration, pveElapsed,
      clearFilters,
      taskTypeColorClass, taskTypeIcon,
      copyDetailLog,
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

.tab-btn:hover { color: var(--text-primary); }

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

/* ── Section header ── */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.refresh-countdown {
  font-variant-numeric: tabular-nums;
}

/* ── Running task cards ── */
.running-cards {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}

.task-card {
  background: var(--bg-secondary, #1e2d40);
  border: 1px solid var(--border-color, rgba(255,255,255,0.1));
  border-radius: 0.5rem;
  padding: 0.875rem 1rem;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.task-card:hover {
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 1px var(--primary-color, #3b82f6);
}

.task-card-header {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  margin-bottom: 0.6rem;
}

.task-card-icon {
  width: 32px;
  height: 32px;
  border-radius: 0.375rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.task-card-info {
  flex: 1;
  min-width: 0;
}

.task-card-desc {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-card-meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.25rem;
  flex-wrap: wrap;
}

.task-meta-badge {
  background: rgba(255,255,255,0.08);
  border-radius: 4px;
  font-size: 0.7rem;
  padding: 0.1rem 0.35rem;
  color: var(--text-muted, #888);
  white-space: nowrap;
}

.task-meta-time {
  font-size: 0.7rem;
  color: var(--text-muted, #888);
}

.task-meta-elapsed {
  font-size: 0.7rem;
  color: var(--primary-color, #3b82f6);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  margin-left: auto;
}

.task-card-badge { flex-shrink: 0; }

.task-card-actions {
  flex-shrink: 0;
  display: flex;
  gap: 0.35rem;
  align-items: flex-start;
}

/* ── Progress bars ── */
.task-card-progress {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.task-card-progress .prog-track { flex: 1; }

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

.prog-fill--animated {
  animation: progress-pulse 2s ease-in-out infinite;
}

@keyframes progress-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

.prog-fill--indeterminate {
  width: 35%;
  animation: prog-slide 1.6s ease-in-out infinite;
}

@keyframes prog-slide {
  0%   { margin-left: 0%; width: 30%; }
  50%  { margin-left: 55%; width: 35%; }
  100% { margin-left: 0%; width: 30%; }
}

.prog-label { flex-shrink: 0; min-width: 30px; text-align: right; }

/* ── Type chips ── */
.type-chip {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  text-transform: lowercase;
}

.type-blue   { background: rgba(59,130,246,0.15); color: #60a5fa; }
.type-purple { background: rgba(139,92,246,0.15); color: #a78bfa; }
.type-green  { background: rgba(16,185,129,0.15); color: #34d399; }
.type-red    { background: rgba(239,68,68,0.15);  color: #f87171; }
.type-teal   { background: rgba(20,184,166,0.15); color: #2dd4bf; }
.type-orange { background: rgba(245,158,11,0.15); color: #fbbf24; }
.type-cyan   { background: rgba(6,182,212,0.15);  color: #22d3ee; }
.type-gray   { background: rgba(255,255,255,0.08); color: var(--text-muted, #888); }

/* Card icon background matches chip color */
.type-blue   .task-card-icon, .task-card-icon.type-blue   { background: rgba(59,130,246,0.15); color: #60a5fa; }
.type-purple .task-card-icon, .task-card-icon.type-purple { background: rgba(139,92,246,0.15); color: #a78bfa; }
.type-green  .task-card-icon, .task-card-icon.type-green  { background: rgba(16,185,129,0.15); color: #34d399; }
.type-red    .task-card-icon, .task-card-icon.type-red    { background: rgba(239,68,68,0.15);  color: #f87171; }
.type-teal   .task-card-icon, .task-card-icon.type-teal   { background: rgba(20,184,166,0.15); color: #2dd4bf; }
.type-orange .task-card-icon, .task-card-icon.type-orange { background: rgba(245,158,11,0.15); color: #fbbf24; }
.type-cyan   .task-card-icon, .task-card-icon.type-cyan   { background: rgba(6,182,212,0.15);  color: #22d3ee; }
.type-gray   .task-card-icon, .task-card-icon.type-gray   { background: rgba(255,255,255,0.08); color: var(--text-muted, #888); }

/* ── History search ── */
.history-search-bar {
  padding: 0.75rem 1rem 0;
}

.form-control-sm {
  padding: 0.3rem 0.65rem;
  font-size: 0.875rem;
  width: 100%;
  max-width: 380px;
}

/* ── Expandable rows ── */
.row-expanded {
  background: var(--bg-secondary, rgba(255,255,255,0.03)) !important;
}

.log-expand-row {
  background: var(--bg-secondary, rgba(0,0,0,0.15));
}

.log-expand-panel {
  padding: 0.75rem 1rem;
}

.log-expand-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.log-expand-actions { display: flex; gap: 0.35rem; }

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
  font-family: 'Fira Mono', 'Cascadia Code', 'Consolas', monospace;
}

.task-log--compact {
  max-height: 160px;
  font-size: 0.72rem;
}

/* ── Filters ── */
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.card-body { padding: 1rem; }

.filters-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  align-items: flex-end;
}

.filters-row .form-group {
  flex: 1;
  min-width: 130px;
  margin-bottom: 0;
}

.form-group--btn { flex: 0 0 auto; display: flex; gap: 0.35rem; align-items: flex-end; }

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

/* ── Table ── */
.table-container { overflow-x: auto; }

.upid-cell, .upid-col {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.clickable-row { cursor: pointer; }
.clickable-row:hover { background: var(--bg-secondary, rgba(255,255,255,0.02)); }

.load-more-bar { padding: 1rem; }

/* ── Animations ── */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.anim-pulse { animation: pulse 1.5s ease-in-out infinite; }

/* ── Buttons ── */
.btn-danger {
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  font-weight: 500;
  padding: 0.25rem 0.6rem;
}
.btn-danger:hover:not(:disabled) { background: #dc2626; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-xs { padding: 0.15rem 0.4rem; font-size: 0.75rem; }
.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.875rem; }

/* ── Modals ── */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1050;
}

.modal-box {
  background: var(--bg-primary, #1a2332);
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  width: 700px;
  max-width: 95vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 60px rgba(0,0,0,0.5);
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
  display: flex;
  align-items: center;
}

.modal-close {
  background: none;
  border: none;
  color: var(--text-muted, #888);
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
  padding: 0;
  transition: color 0.15s;
}

.modal-close:hover { color: var(--text-primary); }

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

/* ── Detail grid ── */
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.5rem 1rem;
}

.detail-kv {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.detail-kv--full {
  grid-column: 1 / -1;
}

.detail-key {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted, #888);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.detail-val {
  font-size: 0.875rem;
  color: var(--text-primary);
}

.detail-upid {
  font-size: 0.72rem;
  color: #60a5fa;
  word-break: break-all;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

/* ── Empty states ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1.5rem;
  text-align: center;
}

.empty-state--compact {
  padding: 1.5rem;
  flex-direction: row;
  gap: 0.75rem;
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

/* ── Spacing helpers ── */
.mb-1 { margin-bottom: 0.5rem; }
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
</style>
