<template>
  <transition name="taskbar-slide">
    <div v-if="isAuthenticated && (hasTasks || completedTasks.length > 0)" class="global-task-bar" :class="{ expanded: isExpanded, 'has-running': hasTasks }">

      <!-- Collapsed pill -->
      <div class="taskbar-collapsed" @click="toggleExpanded">
        <!-- Pulsing ring when tasks are running -->
        <span class="taskbar-spinner" :class="{ 'spinner-pulse': hasTasks }">
          <svg v-if="hasTasks" class="spin-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </span>

        <span class="taskbar-label">
          <span v-if="hasTasks" class="taskbar-count">
            <span class="taskbar-badge">{{ runningTasks.length }}</span>
            task{{ runningTasks.length !== 1 ? 's' : '' }} running
          </span>
          <span v-else class="taskbar-count taskbar-count--done">
            {{ completedTasks.length }} completed
          </span>
        </span>

        <!-- Running indicator dots -->
        <span v-if="hasTasks" class="taskbar-dots" aria-hidden="true">
          <span class="dot dot-1"></span>
          <span class="dot dot-2"></span>
          <span class="dot dot-3"></span>
        </span>

        <span class="taskbar-toggle-icon">
          <svg :class="['chevron', { 'chevron-up': isExpanded }]" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </span>
      </div>

      <!-- Expanded panel -->
      <transition name="fade-height">
        <div v-if="isExpanded" class="taskbar-panel">

          <!-- Running tasks section -->
          <div v-if="runningTasks.length > 0" class="taskbar-section">
            <div class="taskbar-section-header">
              <span class="section-label">Running</span>
              <span class="section-count badge-running">{{ runningTasks.length }}</span>
            </div>

            <div
              v-for="task in runningTasks"
              :key="task.upid"
              class="task-item"
              @click="openDetail(task)"
            >
              <div class="task-row-main">
                <div class="task-type-icon" :class="taskTypeClass(task.task_type)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" v-html="taskTypeIcon(task.task_type)"></svg>
                </div>
                <div class="task-info">
                  <span class="task-desc">{{ task.description || task.task_type || 'Task' }}</span>
                  <span class="task-sub">
                    <span class="task-node">{{ task.node }}</span>
                    <span v-if="task.vmid" class="task-vmid">VM {{ task.vmid }}</span>
                    <span class="task-elapsed">{{ formatElapsed(task.started_at) }}</span>
                  </span>
                </div>
                <div class="task-item-actions" @click.stop>
                  <button
                    v-if="task.source !== 'pbs'"
                    class="task-btn task-btn-stop"
                    :disabled="stoppingTask[task.upid]"
                    @click="stopTask(task)"
                    title="Stop task"
                  >
                    {{ stoppingTask[task.upid] ? '…' : 'Stop' }}
                  </button>
                  <button class="task-btn task-btn-detail" @click="openDetail(task)">
                    Detail
                  </button>
                </div>
              </div>

              <!-- Progress bar -->
              <div v-if="task.progress != null" class="task-prog-track">
                <div class="task-prog-fill" :style="{ width: `${task.progress}%` }"></div>
              </div>

              <!-- Log preview -->
              <div v-if="logPreviews[task.upid]?.length" class="task-log-preview">
                <span
                  v-for="(line, i) in logPreviews[task.upid]"
                  :key="i"
                  class="log-preview-line"
                >{{ line }}</span>
              </div>
            </div>
          </div>

          <!-- Completed tasks section -->
          <div v-if="completedTasks.length > 0" class="taskbar-section">
            <div class="taskbar-section-header">
              <span class="section-label">Recent</span>
              <button class="dismiss-all-btn" @click.stop="dismissAllCompleted">Dismiss all</button>
            </div>

            <div
              v-for="task in completedTasks"
              :key="task.upid"
              class="task-item task-item--completed"
            >
              <div class="task-row-main">
                <div class="task-status-dot" :class="taskDotClass(task.exit_status)"></div>
                <div class="task-info">
                  <span class="task-desc">{{ task.description || task.task_type || 'Task' }}</span>
                  <span class="task-sub">
                    <span class="task-node">{{ task.node }}</span>
                    <span v-if="task.vmid" class="task-vmid">VM {{ task.vmid }}</span>
                    <span :class="statusBadgeMini(task.exit_status)">{{ task.exit_status || task.status }}</span>
                  </span>
                </div>
                <button
                  class="task-dismiss-btn"
                  @click.stop="dismissTask(task.upid)"
                  title="Dismiss"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="taskbar-footer">
            <router-link to="/tasks" class="view-all-link" @click="isExpanded = false">
              View all tasks
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </router-link>
          </div>
        </div>
      </transition>

      <!-- Task detail modal -->
      <Teleport to="body">
        <div v-if="detailTask" class="taskbar-modal-backdrop" @click.self="closeDetail">
          <div class="taskbar-modal">
            <div class="taskbar-modal-header">
              <h3>Task Detail</h3>
              <button class="taskbar-modal-close" @click="closeDetail">&times;</button>
            </div>
            <div class="taskbar-modal-body">

              <!-- Metadata grid -->
              <div class="detail-grid">
                <div class="detail-kv detail-kv--full">
                  <span class="detail-key">Description</span>
                  <span class="detail-val">{{ detailTask.description || '—' }}</span>
                </div>
                <div class="detail-kv">
                  <span class="detail-key">Type</span>
                  <span class="detail-val">{{ detailTask.task_type }}</span>
                </div>
                <div class="detail-kv">
                  <span class="detail-key">Node</span>
                  <span class="detail-val">{{ detailTask.node }}</span>
                </div>
                <div v-if="detailTask.vmid" class="detail-kv">
                  <span class="detail-key">VMID</span>
                  <span class="detail-val">{{ detailTask.vmid }}</span>
                </div>
                <div class="detail-kv">
                  <span class="detail-key">Status</span>
                  <span class="badge badge-warning anim-pulse" style="width:fit-content">running</span>
                </div>
                <div class="detail-kv">
                  <span class="detail-key">Started</span>
                  <span class="detail-val">{{ formatTime(detailTask.started_at) }}</span>
                </div>
                <div class="detail-kv">
                  <span class="detail-key">Elapsed</span>
                  <span class="detail-val">{{ formatElapsed(detailTask.started_at) || '—' }}</span>
                </div>
                <div v-if="detailTask.progress != null" class="detail-kv">
                  <span class="detail-key">Progress</span>
                  <span class="detail-val">{{ Number(detailTask.progress).toFixed(1) }}%</span>
                </div>
                <div v-if="formatEta(detailTask)" class="detail-kv">
                  <span class="detail-key">ETA</span>
                  <span class="detail-val">{{ formatEta(detailTask) }}</span>
                </div>
                <div class="detail-kv detail-kv--full">
                  <span class="detail-key">UPID</span>
                  <code class="detail-upid">{{ detailTask.upid }}</code>
                </div>
              </div>

              <div class="log-header">
                <strong class="text-sm">Log Output</strong>
                <div style="display:flex;gap:0.4rem">
                  <button class="btn btn-outline btn-xs" @click="copyLog" :disabled="!detailLog">
                    {{ logCopied ? 'Copied!' : 'Copy' }}
                  </button>
                </div>
              </div>
              <div v-if="detailLoading" class="text-muted text-sm">Loading log...</div>
              <pre v-else class="task-log">{{ detailLog || 'No log output yet.' }}</pre>
              <div class="text-sm text-muted mt-1">
                <span class="anim-pulse">Live — refreshing every 3s...</span>
              </div>
            </div>
            <div class="taskbar-modal-footer">
              <router-link to="/tasks" class="btn btn-outline" @click="closeDetail">
                View All Tasks
              </router-link>
              <button
                v-if="detailTask.source !== 'pbs'"
                class="btn btn-danger"
                :disabled="stoppingTask[detailTask.upid]"
                @click="stopTask(detailTask)"
              >
                {{ stoppingTask[detailTask.upid] ? 'Stopping...' : 'Stop Task' }}
              </button>
              <button @click="closeDetail" class="btn btn-outline">Close</button>
            </div>
          </div>
        </div>
      </Teleport>
    </div>
  </transition>
</template>

<script>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

const POLL_INTERVAL = 5000
const LOG_POLL_INTERVAL = 3000

export default {
  name: 'GlobalTaskBar',
  setup() {
    const authStore = useAuthStore()
    const toast = useToast()

    const isAuthenticated = computed(() => authStore.isAuthenticated)
    const runningTasks = ref([])
    const completedTasks = ref([])    // recently finished, can be dismissed
    const dismissedUpids = ref(new Set())
    const isExpanded = ref(false)
    const stoppingTask = ref({})
    const logPreviews = ref({})
    const detailTask = ref(null)
    const detailLog = ref('')
    const detailLoading = ref(false)
    const logCopied = ref(false)

    const hasTasks = computed(() => runningTasks.value.length > 0)

    let pollTimer = null
    let detailPollTimer = null
    let prevUpids = new Set()

    // ── Polling ──────────────────────────────────────────────────────────────

    async function fetchRunning() {
      if (!isAuthenticated.value) return
      try {
        const res = await api.tasks.getRunning()
        const incoming = res.data || []
        const incomingUpids = new Set(incoming.map(t => t.upid))

        // Detect newly completed tasks (were running, now gone from running list)
        for (const upid of prevUpids) {
          if (!incomingUpids.has(upid) && !dismissedUpids.value.has(upid)) {
            // Find the task data from the previous list
            const prev = runningTasks.value.find(t => t.upid === upid)
            if (prev) {
              // Try to get final status
              try {
                const res2 = await api.tasks.getHistory({ limit: 20 })
                const hist = (res2.data || []).find(t => t.upid === upid)
                completedTasks.value = [
                  { ...(hist || prev), exit_status: hist?.exit_status || 'OK' },
                  ...completedTasks.value.slice(0, 4)   // keep last 5 completed
                ]
              } catch {
                completedTasks.value = [
                  { ...prev, exit_status: 'OK' },
                  ...completedTasks.value.slice(0, 4)
                ]
              }
            }
          }
        }

        prevUpids = incomingUpids
        runningTasks.value = incoming

        // Fetch log previews for tasks in expanded bar
        if (isExpanded.value) {
          for (const task of incoming) {
            fetchLogPreview(task)
          }
        }
      } catch { /* ignore */ }
    }

    async function fetchLogLines(task) {
      // PBS-sourced tasks have host_id=null and a server_id pointing at the PBS
      // record — they need the PBS task log endpoint, not the PVE one. PBS
      // returns a flat list of strings; PVE wraps in { lines: [...] }.
      if (task.source === 'pbs' && task.server_id != null) {
        const res = await api.pbsManagement.getTaskLog(task.server_id, task.upid)
        return Array.isArray(res.data) ? res.data : (res.data?.lines || [])
      }
      const res = await api.tasks.getLog(task.host_id, task.node, task.upid)
      return res.data?.lines || []
    }

    async function fetchLogPreview(task) {
      try {
        const lines = (await fetchLogLines(task)).filter(l => (l || '').trim())
        logPreviews.value = { ...logPreviews.value, [task.upid]: lines.slice(-2) }
      } catch { /* ignore */ }
    }

    function startPolling() {
      if (pollTimer) return
      pollTimer = setInterval(fetchRunning, POLL_INTERVAL)
    }

    function stopPolling() {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    }

    watch(isAuthenticated, (auth) => {
      if (auth) { fetchRunning(); startPolling() }
      else { stopPolling(); runningTasks.value = [] }
    })

    watch(hasTasks, (has) => {
      if (!has && completedTasks.value.length === 0) {
        isExpanded.value = false
      }
    })

    // ── Actions ───────────────────────────────────────────────────────────────

    function toggleExpanded() {
      isExpanded.value = !isExpanded.value
      if (isExpanded.value && runningTasks.value.length > 0) {
        for (const task of runningTasks.value) fetchLogPreview(task)
      }
    }

    function dismissTask(upid) {
      dismissedUpids.value.add(upid)
      completedTasks.value = completedTasks.value.filter(t => t.upid !== upid)
    }

    function dismissAllCompleted() {
      for (const t of completedTasks.value) dismissedUpids.value.add(t.upid)
      completedTasks.value = []
    }

    async function stopTask(task) {
      stoppingTask.value = { ...stoppingTask.value, [task.upid]: true }
      try {
        await api.tasks.stop(task.host_id, task.node, task.upid)
        toast.success('Task stopped')
        runningTasks.value = runningTasks.value.filter(t => t.upid !== task.upid)
        if (detailTask.value?.upid === task.upid) closeDetail()
      } catch (err) {
        toast.error('Stop failed: ' + (err?.response?.data?.detail || err?.message))
      } finally {
        stoppingTask.value = { ...stoppingTask.value, [task.upid]: false }
      }
    }

    async function openDetail(task) {
      detailTask.value = { ...task }
      detailLog.value = ''
      detailLoading.value = true
      logCopied.value = false

      if (detailPollTimer) { clearInterval(detailPollTimer); detailPollTimer = null }

      await refreshDetailLog()

      detailPollTimer = setInterval(async () => {
        if (!detailTask.value) { clearInterval(detailPollTimer); return }
        await refreshDetailLog()
        // Sync progress from running list
        const live = runningTasks.value.find(t => t.upid === detailTask.value?.upid)
        if (live) {
          detailTask.value = { ...live }
        }
      }, LOG_POLL_INTERVAL)
    }

    function closeDetail() {
      detailTask.value = null
      if (detailPollTimer) { clearInterval(detailPollTimer); detailPollTimer = null }
    }

    async function refreshDetailLog() {
      if (!detailTask.value) return
      try {
        const lines = await fetchLogLines(detailTask.value)
        detailLog.value = lines.join('\n')
      } catch {
        detailLog.value = 'Failed to load log'
      } finally {
        detailLoading.value = false
      }
    }

    async function copyLog() {
      try {
        await navigator.clipboard.writeText(detailLog.value)
        logCopied.value = true
        setTimeout(() => { logCopied.value = false }, 2000)
      } catch { /* ignore */ }
    }

    // ── Formatting ────────────────────────────────────────────────────────────

    // Coerce a timestamp to a Date. Accepts ISO strings, JS Date, Unix seconds,
    // Unix milliseconds, or numeric strings. Unix seconds are detected as
    // values < 1e12 (anything ≥ that is treated as ms).
    function toDate(t) {
      if (t == null) return null
      if (t instanceof Date) return t
      if (typeof t === 'number') return new Date(t < 1e12 ? t * 1000 : t)
      if (typeof t === 'string') {
        const n = Number(t)
        if (!Number.isNaN(n) && /^\d+(\.\d+)?$/.test(t)) {
          return new Date(n < 1e12 ? n * 1000 : n)
        }
        return new Date(t)
      }
      return null
    }

    function formatDuration(secs) {
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

    function formatElapsed(t) {
      const d = toDate(t)
      if (!d || isNaN(d.getTime())) return ''
      return formatDuration((Date.now() - d.getTime()) / 1000)
    }

    function formatTime(t) {
      const d = toDate(t)
      if (!d || isNaN(d.getTime())) return '—'
      return d.toLocaleString()
    }

    function formatEta(task) {
      const d = toDate(task?.started_at)
      const p = Number(task?.progress)
      if (!d || isNaN(d.getTime()) || !isFinite(p) || p <= 0 || p >= 100) return ''
      const elapsed = (Date.now() - d.getTime()) / 1000
      if (elapsed <= 0) return ''
      const remaining = elapsed * (100 - p) / p
      return formatDuration(remaining)
    }

    // ── Type helpers ──────────────────────────────────────────────────────────

    const TYPE_CLASSES = {
      qmigrate: 'type-blue',
      vzdump: 'type-purple',
      qmcreate: 'type-green',
      qmdestroy: 'type-red',
      qmstart: 'type-teal',
      qmstop: 'type-orange',
      replicate: 'type-cyan',
    }

    function taskTypeClass(type) {
      return TYPE_CLASSES[type] || 'type-gray'
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

    function taskDotClass(exitStatus) {
      if (exitStatus === 'OK') return 'dot-success'
      if (!exitStatus) return 'dot-warning'
      return 'dot-error'
    }

    function statusBadgeMini(exitStatus) {
      if (exitStatus === 'OK') return 'mini-badge mini-badge--ok'
      if (!exitStatus) return 'mini-badge mini-badge--warn'
      return 'mini-badge mini-badge--err'
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    onMounted(() => {
      if (isAuthenticated.value) {
        fetchRunning()
        startPolling()
      }
    })

    onUnmounted(() => {
      stopPolling()
      if (detailPollTimer) { clearInterval(detailPollTimer); detailPollTimer = null }
    })

    return {
      isAuthenticated,
      runningTasks,
      completedTasks,
      hasTasks,
      isExpanded,
      stoppingTask,
      logPreviews,
      detailTask,
      detailLog,
      detailLoading,
      logCopied,
      toggleExpanded,
      dismissTask,
      dismissAllCompleted,
      stopTask,
      openDetail,
      closeDetail,
      copyLog,
      formatElapsed,
      formatTime,
      formatEta,
      taskTypeClass,
      taskTypeIcon,
      taskDotClass,
      statusBadgeMini,
    }
  }
}
</script>

<style scoped>
/* ── Bar container ── */
.global-task-bar {
  position: fixed;
  bottom: 1.25rem;
  right: 1.5rem;
  z-index: 900;
  max-width: 420px;
  width: 420px;
  background: #1a2332;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45);
  overflow: hidden;
  transition: border-color 0.3s;
}

.global-task-bar.has-running {
  border-color: rgba(59, 130, 246, 0.35);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(59, 130, 246, 0.15);
}

/* ── Collapsed pill ── */
.taskbar-collapsed {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1rem;
  cursor: pointer;
  user-select: none;
  background: linear-gradient(135deg, #1e3a5f 0%, #1a2332 100%);
  border-bottom: 1px solid transparent;
  transition: background 0.2s;
}

.taskbar-collapsed:hover {
  background: linear-gradient(135deg, #25487a 0%, #1f2d42 100%);
}

.global-task-bar.expanded .taskbar-collapsed {
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

/* ── Spinner / status icon ── */
.taskbar-spinner {
  display: flex;
  align-items: center;
  color: #60a5fa;
  position: relative;
  flex-shrink: 0;
}

.spin-icon {
  animation: spin 1.2s linear infinite;
}

.spinner-pulse::before {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 2px solid rgba(59, 130, 246, 0.4);
  animation: ring-pulse 2s ease-in-out infinite;
}

@keyframes ring-pulse {
  0%, 100% { transform: scale(1); opacity: 0.6; }
  50% { transform: scale(1.4); opacity: 0; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ── Label ── */
.taskbar-label { flex: 1; }

.taskbar-count {
  font-size: 0.875rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.taskbar-count--done {
  color: rgba(255, 255, 255, 0.55);
}

.taskbar-badge {
  background: #3b82f6;
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.05rem 0.4rem;
  border-radius: 9999px;
  min-width: 18px;
  text-align: center;
  line-height: 1.4;
}

/* ── Animated dots ── */
.taskbar-dots {
  display: flex;
  align-items: center;
  gap: 3px;
}

.dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(59, 130, 246, 0.7);
  animation: dot-bounce 1.4s ease-in-out infinite;
}

.dot-2 { animation-delay: 0.2s; }
.dot-3 { animation-delay: 0.4s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.taskbar-toggle-icon {
  color: rgba(255, 255, 255, 0.45);
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.chevron {
  transition: transform 0.25s ease;
}

.chevron-up {
  transform: rotate(180deg);
}

/* ── Expanded panel ── */
.taskbar-panel {
  max-height: 420px;
  overflow-y: auto;
}

/* Custom scrollbar */
.taskbar-panel::-webkit-scrollbar { width: 4px; }
.taskbar-panel::-webkit-scrollbar-track { background: transparent; }
.taskbar-panel::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 2px; }

/* ── Section ── */
.taskbar-section {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.taskbar-section:last-of-type {
  border-bottom: none;
}

.taskbar-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem 0.25rem;
}

.section-label {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: rgba(255, 255, 255, 0.35);
}

.section-count {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 9999px;
}

.badge-running {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

.dismiss-all-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.35);
  font-size: 0.72rem;
  cursor: pointer;
  padding: 0;
  transition: color 0.15s;
}

.dismiss-all-btn:hover { color: rgba(255, 255, 255, 0.7); }

/* ── Task item ── */
.task-item {
  padding: 0.6rem 1rem;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  transition: background 0.15s;
}

.task-item:last-child { border-bottom: none; }

.task-item:hover { background: rgba(255, 255, 255, 0.035); }

.task-item--completed {
  opacity: 0.75;
}

.task-item--completed:hover { opacity: 1; }

.task-row-main {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.3rem;
}

/* ── Type icon ── */
.task-type-icon {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.type-blue   { background: rgba(59,130,246,0.15); color: #60a5fa; }
.type-purple { background: rgba(139,92,246,0.15); color: #a78bfa; }
.type-green  { background: rgba(16,185,129,0.15); color: #34d399; }
.type-red    { background: rgba(239,68,68,0.15);  color: #f87171; }
.type-teal   { background: rgba(20,184,166,0.15); color: #2dd4bf; }
.type-orange { background: rgba(245,158,11,0.15); color: #fbbf24; }
.type-cyan   { background: rgba(6,182,212,0.15);  color: #22d3ee; }
.type-gray   { background: rgba(255,255,255,0.07); color: rgba(255,255,255,0.45); }

/* ── Status dot (completed tasks) ── */
.task-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin: 0 7px;
}

.dot-success { background: #10b981; }
.dot-warning { background: #f59e0b; }
.dot-error   { background: #ef4444; }

/* ── Task info ── */
.task-info {
  flex: 1;
  min-width: 0;
}

.task-desc {
  display: block;
  font-size: 0.8125rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-sub {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
  margin-top: 0.1rem;
}

.task-node {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.07);
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
}

.task-vmid {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.35);
}

.task-elapsed {
  font-size: 0.68rem;
  color: #60a5fa;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  margin-left: auto;
}

/* ── Mini badges ── */
.mini-badge {
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.05rem 0.35rem;
  border-radius: 3px;
}

.mini-badge--ok  { background: rgba(16,185,129,0.2); color: #34d399; }
.mini-badge--warn { background: rgba(245,158,11,0.2); color: #fbbf24; }
.mini-badge--err { background: rgba(239,68,68,0.2); color: #f87171; }

/* ── Item actions ── */
.task-item-actions {
  display: flex;
  gap: 0.3rem;
  flex-shrink: 0;
}

.task-btn {
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  border: 1px solid transparent;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.15s;
  white-space: nowrap;
}

.task-btn-stop {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.35);
  color: #f87171;
}

.task-btn-stop:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.22);
}

.task-btn-stop:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.task-btn-detail {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.6);
}

.task-btn-detail:hover {
  background: rgba(255, 255, 255, 0.12);
}

/* ── Dismiss button ── */
.task-dismiss-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.3);
  cursor: pointer;
  padding: 0.2rem;
  border-radius: 3px;
  display: flex;
  align-items: center;
  transition: color 0.15s, background 0.15s;
  flex-shrink: 0;
}

.task-dismiss-btn:hover {
  color: rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.08);
}

/* ── Progress bar ── */
.task-prog-track {
  height: 3px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
  margin: 0.2rem 0;
  overflow: hidden;
}

.task-prog-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 2px;
  transition: width 1s ease;
  animation: prog-pulse 2s ease-in-out infinite;
}

@keyframes prog-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

/* ── Log preview ── */
.task-log-preview {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin-top: 0.2rem;
}

.log-preview-line {
  font-family: 'Fira Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.66rem;
  color: rgba(255, 255, 255, 0.35);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

/* ── Footer ── */
.taskbar-footer {
  padding: 0.6rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.view-all-link {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: #60a5fa;
  text-decoration: none;
  transition: color 0.15s;
}

.view-all-link:hover { color: #93c5fd; }

/* ── Slide transition ── */
.taskbar-slide-enter-active,
.taskbar-slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.taskbar-slide-enter-from,
.taskbar-slide-leave-to {
  transform: translateY(20px);
  opacity: 0;
}

/* ── Fade-height transition ── */
.fade-height-enter-active,
.fade-height-leave-active {
  transition: opacity 0.2s ease;
}

.fade-height-enter-from,
.fade-height-leave-to {
  opacity: 0;
}

/* ── Task detail modal ── */
.taskbar-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.taskbar-modal {
  background: #1a2332;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  width: 660px;
  max-width: 95vw;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6);
}

.taskbar-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.taskbar-modal-header h3 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.taskbar-modal-close {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.5);
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
  padding: 0;
  transition: color 0.15s;
}

.taskbar-modal-close:hover { color: rgba(255, 255, 255, 0.9); }

.taskbar-modal-body {
  padding: 1.25rem;
  overflow-y: auto;
  flex: 1;
}

.taskbar-modal-footer {
  padding: 0.875rem 1.25rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

/* ── Detail grid ── */
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.65rem 1.25rem;
  margin-bottom: 1.25rem;
}

.detail-kv {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.detail-kv--full { grid-column: 1 / -1; }

.detail-key {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.35);
}

.detail-val {
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.8);
}

.detail-upid {
  font-size: 0.7rem;
  color: #60a5fa;
  word-break: break-all;
  font-family: 'Fira Mono', monospace;
}

/* ── Log ── */
.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.task-log {
  margin: 0;
  padding: 0.75rem 1rem;
  font-size: 0.78rem;
  color: #9ca3af;
  background: #0f1419;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 280px;
  overflow-y: auto;
  font-family: 'Fira Mono', 'Cascadia Code', 'Consolas', monospace;
}

/* ── Shared helpers ── */
.text-sm { font-size: 0.875rem; }
.text-muted { color: rgba(255, 255, 255, 0.45); }
.mt-1 { margin-top: 0.25rem; }

.badge-warning {
  background: #d97706;
  color: #fff;
  padding: 0.1rem 0.45rem;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.anim-pulse { animation: pulse 1.5s ease-in-out infinite; }

/* ── Buttons ── */
.btn {
  padding: 0.4rem 0.9rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

.btn-xs { padding: 0.15rem 0.4rem; font-size: 0.75rem; }

.btn-danger {
  background: #ef4444;
  color: #fff;
  border-color: #ef4444;
}

.btn-danger:hover:not(:disabled) { background: #dc2626; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-outline {
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  border-color: rgba(255, 255, 255, 0.2);
}

.btn-outline:hover { background: rgba(255, 255, 255, 0.07); }

@media (max-width: 480px) {
  .global-task-bar {
    right: 0.75rem;
    left: 0.75rem;
    width: auto;
    max-width: none;
  }
}
</style>
