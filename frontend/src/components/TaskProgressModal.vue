<template>
  <div v-if="visible" class="tpm-overlay" @click.self="onOverlayClick">
    <div class="tpm-modal" @click.stop>
      <div class="tpm-header">
        <div class="tpm-title-row">
          <h3 class="tpm-title">{{ taskLabel }}</h3>
          <span :class="['tpm-badge', statusBadgeClass]">{{ statusText }}</span>
        </div>
        <button @click="$emit('close')" class="tpm-close-btn">×</button>
      </div>

      <div class="tpm-body">
        <!-- UPID info -->
        <div class="tpm-meta">
          <span class="tpm-meta-label">Node:</span>
          <span class="tpm-meta-val">{{ node }}</span>
          <span class="tpm-meta-label ml-2">UPID:</span>
          <span class="tpm-meta-val tpm-upid" :title="upid">{{ shortUpid }}</span>
        </div>

        <!-- Log output -->
        <div class="tpm-log-wrap" ref="logWrapRef">
          <div v-if="logLines.length === 0 && !isDone" class="tpm-log-placeholder">
            Waiting for log output…
          </div>
          <div v-else class="tpm-log">
            <div v-for="(line, idx) in logLines" :key="idx" class="tpm-log-line">{{ line }}</div>
          </div>
        </div>

        <!-- Error message -->
        <div v-if="errorMsg" class="tpm-error-box">
          {{ errorMsg }}
        </div>
      </div>

      <div class="tpm-footer">
        <div v-if="!isDone" class="tpm-spinner-row">
          <span class="tpm-spinner"></span>
          <span class="tpm-spinner-text">Running…</span>
        </div>
        <button @click="$emit('close')" class="btn btn-outline btn-sm">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import api from '@/services/api'

const props = defineProps({
  upid: { type: String, default: '' },
  hostId: { type: [Number, String], default: null },
  node: { type: String, default: '' },
  visible: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'success', 'error'])

const logLines = ref([])
const taskStatus = ref(null)   // full status object from PVE
const errorMsg = ref('')
const isDone = ref(false)
let pollTimer = null
const logWrapRef = ref(null)

// ── Computed ──────────────────────────────────────────────────────────────────

const shortUpid = computed(() => {
  if (!props.upid) return ''
  // UPIDs are long — show last 30 chars
  return props.upid.length > 40 ? '…' + props.upid.slice(-38) : props.upid
})

const taskLabel = computed(() => {
  if (!props.upid) return 'Task Progress'
  // UPID format: UPID:node:pid:starttime:type:id:user@realm:
  const parts = props.upid.split(':')
  const type = parts[5] || ''
  const id   = parts[6] || ''
  if (type && id) return `Task: ${type} ${id}`
  if (type) return `Task: ${type}`
  return 'Task Progress'
})

const statusText = computed(() => {
  if (!taskStatus.value) return 'starting'
  const s = taskStatus.value.status
  if (s === 'stopped') {
    return taskStatus.value.exitstatus === 'OK' ? 'OK' : `Error: ${taskStatus.value.exitstatus}`
  }
  return s || 'running'
})

const statusBadgeClass = computed(() => {
  if (!taskStatus.value || taskStatus.value.status !== 'stopped') return 'tpm-badge--running'
  return taskStatus.value.exitstatus === 'OK' ? 'tpm-badge--ok' : 'tpm-badge--error'
})

// ── Polling ───────────────────────────────────────────────────────────────────

const scrollToBottom = async () => {
  await nextTick()
  if (logWrapRef.value) {
    logWrapRef.value.scrollTop = logWrapRef.value.scrollHeight
  }
}

const fetchLog = async () => {
  if (!props.upid || !props.hostId || !props.node) return
  try {
    const res = await api.pveNode.taskLog(props.hostId, props.node, props.upid)
    const lines = (res.data || []).map(entry => {
      // PVE returns [{n: linenum, t: text}, ...]
      if (typeof entry === 'object' && entry.t !== undefined) return entry.t
      return String(entry)
    })
    logLines.value = lines
    await scrollToBottom()
  } catch (e) {
    // non-fatal — log may not be available yet
  }
}

const pollStatus = async () => {
  if (!props.upid || !props.hostId || !props.node) return
  try {
    const res = await api.pveNode.taskStatus(props.hostId, props.node, props.upid)
    taskStatus.value = res.data || {}
    await fetchLog()

    if (taskStatus.value.status === 'stopped') {
      isDone.value = true
      stopPolling()
      if (taskStatus.value.exitstatus === 'OK') {
        emit('success')
      } else {
        const msg = taskStatus.value.exitstatus || 'Task failed'
        errorMsg.value = msg
        emit('error', msg)
      }
    }
  } catch (e) {
    console.warn('TaskProgressModal: poll failed', e)
  }
}

const startPolling = () => {
  if (pollTimer) return
  pollStatus() // immediate first poll
  pollTimer = setInterval(pollStatus, 2000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// ── Watchers ──────────────────────────────────────────────────────────────────

watch(() => props.visible, (val) => {
  if (val && props.upid) {
    // Reset state on open
    logLines.value = []
    taskStatus.value = null
    errorMsg.value = ''
    isDone.value = false
    startPolling()
  } else {
    stopPolling()
  }
}, { immediate: true })

watch(() => props.upid, (val) => {
  if (val && props.visible) {
    logLines.value = []
    taskStatus.value = null
    errorMsg.value = ''
    isDone.value = false
    stopPolling()
    startPolling()
  }
})

// ── Close logic ───────────────────────────────────────────────────────────────

const onOverlayClick = () => {
  // Only allow closing via the button; clicking overlay doesn't close
  // (task may still be running)
}

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.tpm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.tpm-modal {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  width: 680px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.tpm-header {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-shrink: 0;
}

.tpm-title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.tpm-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.tpm-close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
  flex-shrink: 0;
}

.tpm-close-btn:hover {
  color: var(--text-primary);
}

/* Status badge */
.tpm-badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.tpm-badge--running {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.tpm-badge--ok {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.tpm-badge--error {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

/* Body */
.tpm-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 1rem 1.25rem;
  gap: 0.75rem;
  min-height: 0;
}

.tpm-meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  flex-wrap: wrap;
}

.tpm-meta-label {
  color: var(--text-secondary);
  font-weight: 600;
}

.tpm-meta-val {
  color: var(--text-primary);
  font-family: monospace;
}

.tpm-upid {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ml-2 { margin-left: 0.75rem; }

/* Log area */
.tpm-log-wrap {
  flex: 1;
  min-height: 0;
  background: var(--bg-tertiary, #0d0d1a);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow-y: auto;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  max-height: 380px;
}

.tpm-log-placeholder {
  padding: 1rem;
  color: var(--text-secondary);
  font-style: italic;
}

.tpm-log {
  padding: 0.5rem 0.75rem;
}

.tpm-log-line {
  color: #d1d5db;
  white-space: pre-wrap;
  word-break: break-all;
}

.tpm-log-line:hover {
  background: rgba(255, 255, 255, 0.04);
}

/* Error box */
.tpm-error-box {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 0.375rem;
  padding: 0.75rem 1rem;
  color: #f87171;
  font-size: 0.875rem;
  flex-shrink: 0;
}

/* Footer */
.tpm-footer {
  padding: 0.875rem 1.25rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.tpm-spinner-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tpm-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary-color, #3b82f6);
  border-radius: 50%;
  animation: tpm-spin 0.7s linear infinite;
}

@keyframes tpm-spin {
  to { transform: rotate(360deg); }
}

.tpm-spinner-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

/* Button helpers (mirror app globals) */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.btn-outline {
  background: transparent;
  border-color: var(--border-color);
  color: var(--text-primary);
}

.btn-outline:hover {
  background: var(--bg-tertiary, rgba(255,255,255,0.06));
}

.btn-sm {
  padding: 0.3rem 0.75rem;
  font-size: 0.8rem;
}
</style>
