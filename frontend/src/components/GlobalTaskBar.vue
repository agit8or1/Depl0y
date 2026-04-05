<template>
  <transition name="taskbar-slide">
    <div v-if="isAuthenticated && hasTasks" class="global-task-bar" :class="{ expanded: isExpanded }">
      <!-- Collapsed pill -->
      <div class="taskbar-collapsed" @click="toggleExpanded">
        <span class="taskbar-spinner">
          <svg class="spin-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
          </svg>
        </span>
        <span class="taskbar-count">{{ runningTasks.length }} task{{ runningTasks.length !== 1 ? 's' : '' }} running</span>
        <span class="taskbar-toggle-icon">
          <svg :class="['chevron', { 'chevron-up': isExpanded }]" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </span>
      </div>

      <!-- Expanded task list -->
      <transition name="fade-height">
        <div v-if="isExpanded" class="taskbar-list">
          <div
            v-for="task in runningTasks"
            :key="task.upid"
            class="task-item"
            @click="openDetail(task)"
          >
            <div class="task-header">
              <span class="task-desc">{{ task.description || task.task_type || 'Task' }}</span>
              <div class="task-meta">
                <span class="task-badge">{{ task.node }}</span>
                <span v-if="task.vmid" class="task-badge">VM {{ task.vmid }}</span>
                <span class="task-time">{{ formatAge(task.started_at) }}</span>
              </div>
            </div>

            <!-- Progress bar -->
            <div class="task-progress-track">
              <div
                class="task-progress-fill"
                :style="{ width: `${task.progress || 0}%` }"
              ></div>
            </div>

            <!-- Log preview -->
            <div v-if="logPreviews[task.upid]" class="task-log-preview">
              <span
                v-for="(line, i) in logPreviews[task.upid]"
                :key="i"
                class="log-line"
              >{{ line }}</span>
            </div>

            <div class="task-actions" @click.stop>
              <button
                class="task-btn task-btn-stop"
                :disabled="stoppingTask[task.upid]"
                @click="stopTask(task)"
                title="Stop this task"
              >
                {{ stoppingTask[task.upid] ? '...' : 'Stop' }}
              </button>
              <button class="task-btn task-btn-detail" @click="openDetail(task)">
                Details
              </button>
            </div>
          </div>
        </div>
      </transition>

      <!-- Task detail modal -->
      <div v-if="detailTask" class="taskbar-modal-backdrop" @click.self="detailTask = null">
        <div class="taskbar-modal">
          <div class="taskbar-modal-header">
            <h3>Task Detail</h3>
            <button class="taskbar-modal-close" @click="detailTask = null">&times;</button>
          </div>
          <div class="taskbar-modal-body">
            <div class="detail-meta">
              <div><strong>Description:</strong> {{ detailTask.description || '—' }}</div>
              <div><strong>Type:</strong> {{ detailTask.task_type }}</div>
              <div><strong>Node:</strong> {{ detailTask.node }}</div>
              <div v-if="detailTask.vmid"><strong>VMID:</strong> {{ detailTask.vmid }}</div>
              <div>
                <strong>Status:</strong>
                <span class="badge badge-warning anim-pulse" style="margin-left:0.25rem">running</span>
              </div>
              <div><strong>Started:</strong> {{ formatTime(detailTask.started_at) }}</div>
              <div v-if="detailTask.progress !== undefined">
                <strong>Progress:</strong> {{ detailTask.progress }}%
              </div>
              <div class="upid-line"><strong>UPID:</strong> <code>{{ detailTask.upid }}</code></div>
            </div>

            <div class="log-header">
              <strong class="text-sm">Log Output</strong>
            </div>
            <div v-if="detailLoading" class="text-muted text-sm">Loading log...</div>
            <pre v-else class="task-log">{{ detailLog || 'No log output yet.' }}</pre>
            <div class="text-sm text-muted mt-1">
              <span class="anim-pulse">Live — refreshing every 3s...</span>
            </div>
          </div>
          <div class="taskbar-modal-footer">
            <button
              class="btn btn-danger"
              :disabled="stoppingTask[detailTask.upid]"
              @click="stopTask(detailTask)"
            >
              {{ stoppingTask[detailTask.upid] ? 'Stopping...' : 'Stop Task' }}
            </button>
            <button @click="detailTask = null" class="btn btn-outline">Close</button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

const POLL_INTERVAL = 3000
const LOG_POLL_INTERVAL = 3000

export default {
  name: 'GlobalTaskBar',
  setup() {
    const authStore = useAuthStore()
    const toast = useToast()

    const isAuthenticated = computed(() => authStore.isAuthenticated)
    const runningTasks = ref([])
    const isExpanded = ref(false)
    const stoppingTask = ref({})
    const logPreviews = ref({})   // upid → last 2 lines
    const detailTask = ref(null)
    const detailLog = ref('')
    const detailLoading = ref(false)

    const hasTasks = computed(() => runningTasks.value.length > 0)

    let pollTimer = null
    let detailPollTimer = null

    // ── Polling ──────────────────────────────────────────────────────────────

    async function fetchRunning() {
      if (!isAuthenticated.value) return
      try {
        const res = await api.tasks.getRunning()
        runningTasks.value = res.data || []
        // Fetch log previews for tasks shown in expanded bar
        if (isExpanded.value) {
          for (const task of runningTasks.value) {
            fetchLogPreview(task)
          }
        }
      } catch { /* ignore */ }
    }

    async function fetchLogPreview(task) {
      try {
        const res = await api.tasks.getLog(task.host_id, task.node, task.upid)
        const lines = res.data?.lines || []
        logPreviews.value[task.upid] = lines.slice(-2)
      } catch { /* ignore */ }
    }

    function startPolling() {
      if (pollTimer) return
      pollTimer = setInterval(fetchRunning, POLL_INTERVAL)
    }

    function stopPolling() {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    }

    watch(hasTasks, (has) => {
      if (has) startPolling()
      else { stopPolling(); isExpanded.value = false }
    })

    watch(isAuthenticated, (auth) => {
      if (auth) { fetchRunning(); startPolling() }
      else { stopPolling(); runningTasks.value = [] }
    })

    // ── Actions ───────────────────────────────────────────────────────────────

    function toggleExpanded() {
      isExpanded.value = !isExpanded.value
    }

    async function stopTask(task) {
      stoppingTask.value = { ...stoppingTask.value, [task.upid]: true }
      try {
        await api.tasks.stop(task.host_id, task.node, task.upid)
        toast.success(`Task stopped`)
        runningTasks.value = runningTasks.value.filter(t => t.upid !== task.upid)
        if (detailTask.value?.upid === task.upid) detailTask.value = null
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

      if (detailPollTimer) { clearInterval(detailPollTimer); detailPollTimer = null }

      await refreshDetailLog()

      detailPollTimer = setInterval(async () => {
        if (!detailTask.value) { clearInterval(detailPollTimer); return }
        await refreshDetailLog()
      }, LOG_POLL_INTERVAL)
    }

    async function refreshDetailLog() {
      if (!detailTask.value) return
      try {
        const res = await api.tasks.getLog(
          detailTask.value.host_id,
          detailTask.value.node,
          detailTask.value.upid
        )
        detailLog.value = (res.data?.lines || []).join('\n')
      } catch {
        detailLog.value = 'Failed to load log'
      } finally {
        detailLoading.value = false
      }
    }

    // ── Formatting ────────────────────────────────────────────────────────────

    function formatAge(isoStr) {
      if (!isoStr) return ''
      try {
        const diff = Date.now() - new Date(isoStr).getTime()
        const s = Math.floor(diff / 1000)
        if (s < 60) return `${s}s ago`
        if (s < 3600) return `${Math.floor(s / 60)}m ago`
        return `${Math.floor(s / 3600)}h ago`
      } catch {
        return ''
      }
    }

    function formatTime(isoStr) {
      if (!isoStr) return '—'
      try {
        return new Date(isoStr).toLocaleString()
      } catch {
        return isoStr
      }
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
      hasTasks,
      isExpanded,
      stoppingTask,
      logPreviews,
      detailTask,
      detailLog,
      detailLoading,
      toggleExpanded,
      stopTask,
      openDetail,
      formatAge,
      formatTime,
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
}

/* ── Collapsed pill header ── */
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

.taskbar-spinner {
  display: flex;
  align-items: center;
  color: #60a5fa;
}

.spin-icon {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.taskbar-count {
  font-size: 0.875rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  flex: 1;
}

.taskbar-toggle-icon {
  color: rgba(255, 255, 255, 0.45);
  display: flex;
  align-items: center;
}

.chevron {
  transition: transform 0.25s ease;
}

.chevron-up {
  transform: rotate(180deg);
}

/* ── Expanded list ── */
.taskbar-list {
  max-height: 360px;
  overflow-y: auto;
  padding: 0.5rem 0;
}

.task-item {
  padding: 0.75rem 1rem;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  transition: background 0.15s;
}

.task-item:last-child {
  border-bottom: none;
}

.task-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.task-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}

.task-desc {
  font-size: 0.8125rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  flex-shrink: 0;
}

.task-badge {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  font-size: 0.7rem;
  padding: 0.1rem 0.35rem;
  color: rgba(255, 255, 255, 0.65);
  white-space: nowrap;
}

.task-time {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
}

/* ── Progress bar ── */
.task-progress-track {
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  margin-bottom: 0.4rem;
  overflow: hidden;
}

.task-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 2px;
  transition: width 1s ease;
  animation: progress-pulse 2s ease-in-out infinite;
}

@keyframes progress-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* ── Log preview ── */
.task-log-preview {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin-bottom: 0.4rem;
}

.log-line {
  font-family: monospace;
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

/* ── Task actions ── */
.task-actions {
  display: flex;
  gap: 0.4rem;
  justify-content: flex-end;
}

.task-btn {
  font-size: 0.72rem;
  padding: 0.2rem 0.55rem;
  border-radius: 4px;
  border: 1px solid transparent;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.15s;
}

.task-btn-stop {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.4);
  color: #f87171;
}

.task-btn-stop:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.25);
}

.task-btn-stop:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.task-btn-detail {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.7);
}

.task-btn-detail:hover {
  background: rgba(255, 255, 255, 0.12);
}

/* ── Taskbar slide transition ── */
.taskbar-slide-enter-active,
.taskbar-slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.taskbar-slide-enter-from,
.taskbar-slide-leave-to {
  transform: translateY(20px);
  opacity: 0;
}

/* ── Fade-height transition for expanded list ── */
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
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.taskbar-modal {
  background: #1a2332;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  width: 640px;
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

.taskbar-modal-close:hover {
  color: rgba(255, 255, 255, 0.9);
}

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

.detail-meta {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.75);
  margin-bottom: 1rem;
}

.detail-meta strong {
  color: rgba(255, 255, 255, 0.9);
}

.upid-line code {
  font-size: 0.72rem;
  word-break: break-all;
  color: #60a5fa;
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
  font-size: 0.78rem;
  color: #9ca3af;
  background: #0f1419;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
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

.anim-pulse {
  animation: pulse 1.5s ease-in-out infinite;
}

.btn {
  padding: 0.4rem 0.9rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
}

.btn-danger {
  background: #ef4444;
  color: #fff;
  border-color: #ef4444;
}

.btn-danger:hover:not(:disabled) {
  background: #dc2626;
}

.btn-danger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-outline {
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  border-color: rgba(255, 255, 255, 0.2);
}

.btn-outline:hover {
  background: rgba(255, 255, 255, 0.07);
}

@media (max-width: 480px) {
  .global-task-bar {
    right: 0.75rem;
    left: 0.75rem;
    width: auto;
    max-width: none;
  }
}
</style>
