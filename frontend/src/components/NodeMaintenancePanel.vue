<template>
  <div class="card mb-2 maint-panel">
    <div class="card-header">
      <h3>Maintenance: {{ node }}</h3>
      <div class="flex gap-1">
        <button class="btn btn-outline btn-sm" :disabled="loading || running" @click="loadPreview">
          {{ loading ? 'Checking…' : 'Preview again' }}
        </button>
        <button class="btn btn-outline btn-sm" @click="$emit('close')">Close</button>
      </div>
    </div>
    <div class="card-body">
      <p class="text-sm text-muted mb-2">
        Step 1 shows where each guest on <strong>{{ node }}</strong> would go, and why. Reading the plan
        changes nothing. Step 2 moves only the guests you pick, each to the node shown, and checks
        each one before and after its move.
      </p>

      <div v-if="error" class="text-danger mb-2">{{ error }}</div>
      <div v-if="loading && !plan" class="text-muted">Reading the cluster…</div>

      <template v-if="plan">
        <!-- Cluster checks -->
        <div class="checks mb-2">
          <div v-for="(c, i) in plan.checks" :key="i" :class="['check', 'check-' + c.status]">
            <span class="check-icon">{{ icon(c.status) }}</span>
            <strong>{{ c.title }}</strong>
            <span v-if="c.detail" class="text-muted"> — {{ c.detail }}</span>
          </div>
        </div>

        <!-- Summary -->
        <div class="summary mb-2">
          <span class="badge badge-success">{{ plan.summary.online }} online</span>
          <span class="badge badge-warning">{{ plan.summary.downtime }} need downtime</span>
          <span class="badge badge-danger">{{ plan.summary.blocked }} blocked</span>
          <span class="badge badge-info">{{ plan.summary.unknown }} unknown</span>
          <span class="text-sm text-muted">
            Running guests need {{ fmt(plan.summary.running_mem) }} RAM; the other nodes have
            {{ fmt(plan.summary.target_mem_available) }} free (after a 10% reserve).
          </span>
        </div>

        <!-- Per-guest plan -->
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th v-if="isAdmin"></th>
                <th>Guest</th>
                <th>Class</th>
                <th>Destination</th>
                <th>Reason</th>
                <th v-if="job">Result</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="g in plan.guests" :key="g.sid">
                <td v-if="isAdmin">
                  <input
                    v-if="g.class === 'online' || g.class === 'downtime'"
                    type="checkbox"
                    :checked="selected.has(g.sid)"
                    :disabled="running"
                    :title="g.class === 'downtime' ? 'This guest stops while it moves' : ''"
                    @change="toggle(g.sid)"
                  />
                </td>
                <td>
                  <span :class="['badge', g.vmtype === 'lxc' ? 'badge-warning' : 'badge-info']">
                    {{ g.vmtype === 'lxc' ? 'CT' : 'VM' }}
                  </span>
                  {{ g.vmid }} <span class="text-muted">{{ g.name }}</span>
                  <div class="text-xs text-muted">{{ g.status }}<span v-if="g.ha"> · HA</span><span v-if="g.template"> · template</span></div>
                </td>
                <td><span :class="['badge', classBadge(g.class)]">{{ classLabel(g) }}</span></td>
                <td>
                  <strong v-if="g.target">{{ g.target }}</strong>
                  <span v-else class="text-muted">—</span>
                  <div v-for="(d, s) in nonTrivialMap(g)" :key="s" class="text-xs text-muted">{{ s }} → {{ d }}</div>
                </td>
                <td class="reason">
                  {{ g.reason }}
                  <div v-for="(w, i) in g.warnings" :key="i" class="text-xs warn-line">⚠ {{ w }}</div>
                  <details v-if="g.class === 'blocked' && Object.keys(g.targets || {}).length" class="text-xs">
                    <summary>Why not other nodes</summary>
                    <div v-for="(probs, t) in g.targets" :key="t"><strong>{{ t }}:</strong> {{ probs.length ? probs.join('; ') : 'ok' }}</div>
                  </details>
                </td>
                <td v-if="job">
                  <span v-if="result(g.sid)" :class="['badge', resultBadge(result(g.sid).status)]">
                    {{ result(g.sid).status.replace('_', ' ') }}
                  </span>
                  <div v-if="result(g.sid)" class="text-xs text-muted">{{ result(g.sid).detail }}</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Permissions -->
        <div v-if="plan.permissions && plan.permissions.checked && !plan.permissions.execute.ok" class="text-sm text-danger mt-1">
          The Proxmox API token cannot carry out this plan. Missing:
          {{ missingPerms.join(', ') }}
        </div>

        <!-- Execute -->
        <div v-if="isAdmin" class="execute mt-2">
          <div v-if="selectedDowntime.length" class="downtime-confirm mb-1">
            <label>
              <input v-model="confirmDowntime" type="checkbox" :disabled="running" />
              I accept downtime for {{ selectedDowntime.join(', ') }}: these guests stop while they move.
            </label>
          </div>
          <div class="flex gap-1 align-center">
            <button class="btn btn-danger" :disabled="!canRun" @click="execute">
              {{ running ? 'Evacuating…' : `Move ${selected.size} guest${selected.size === 1 ? '' : 's'}` }}
            </button>
            <button v-if="running" class="btn btn-outline" :disabled="job && job.cancel_requested" @click="cancel">
              {{ job && job.cancel_requested ? 'Stopping after current move…' : 'Stop after current move' }}
            </button>
            <button v-if="job && !running && retryable.length" class="btn btn-outline" @click="selectRetry">
              Select {{ retryable.length }} to retry
            </button>
          </div>
          <p class="text-xs text-muted mt-1">{{ plan.power_note }}</p>
        </div>

        <!-- Job log -->
        <div v-if="job" class="job mt-2">
          <div class="mb-1">
            <strong>Job {{ job.status }}</strong>
            <span v-if="job.remaining_on_node && job.remaining_on_node.length" class="text-muted">
              · still on {{ node }}: {{ job.remaining_on_node.join(', ') }}
            </span>
            <span v-else-if="job.remaining_on_node" class="text-success"> · {{ node }} has no guests left</span>
          </div>
          <div class="job-log text-xs">
            <div v-for="(s, i) in job.steps" :key="i"><span class="text-muted">{{ s.time }}</span> {{ s.text }}</div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import { formatBytes } from '@/utils/proxmox'

const props = defineProps({
  hostId: { type: [String, Number], required: true },
  node: { type: String, required: true },
  isAdmin: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'finished'])
const toast = useToast()

const plan = ref(null)
const loading = ref(false)
const error = ref('')
const selected = ref(new Set())
const confirmDowntime = ref(false)
const job = ref(null)
let pollTimer = null

const running = computed(() => job.value && job.value.status === 'running')
const byClass = (cls) => (plan.value?.guests || []).filter(g => g.class === cls)
const selectedDowntime = computed(() => byClass('downtime').filter(g => selected.value.has(g.sid)).map(g => g.sid))
const missingPerms = computed(() => [...new Set((plan.value?.permissions?.execute?.missing || []).map(m => `${m.privilege} on ${m.path}`))])
const canRun = computed(() => plan.value && plan.value.executable && !running.value && selected.value.size > 0 &&
  (!selectedDowntime.value.length || confirmDowntime.value))
const retryable = computed(() => (job.value?.guests || [])
  .filter(r => ['failed', 'skipped', 'cancelled'].includes(r.status)).map(r => r.sid))

function fmt(b) { return formatBytes(b || 0) }
function icon(s) { return { ok: '✓', warn: '⚠', fail: '✕', info: 'ℹ' }[s] || '•' }
function classBadge(c) { return { online: 'badge-success', downtime: 'badge-warning', blocked: 'badge-danger' }[c] || 'badge-info' }
function classLabel(g) {
  if (g.class === 'online') return g.method === 'live' ? 'Movable online' : 'Movable (stopped)'
  if (g.class === 'downtime') return g.method === 'cold' ? 'Downtime: cold move' : 'Downtime: restart'
  if (g.class === 'blocked') return g.capacity ? 'Blocked: capacity' : 'Blocked'
  return 'Unknown'
}
function resultBadge(s) {
  if (['moved', 'already_moved'].includes(s)) return 'badge-success'
  if (s === 'deviated') return 'badge-info'
  if (s === 'moved_elsewhere') return 'badge-info'
  if (['failed'].includes(s)) return 'badge-danger'
  if (['skipped', 'cancelled'].includes(s)) return 'badge-warning'
  return 'badge-info'
}
function nonTrivialMap(g) {
  const out = {}
  for (const [s, d] of Object.entries(g.storage_map || {})) if (s !== d) out[s] = d
  return out
}
function result(sid) { return (job.value?.guests || []).find(r => r.sid === sid) }
function toggle(sid) {
  const s = new Set(selected.value)
  s.has(sid) ? s.delete(sid) : s.add(sid)
  selected.value = s
}

async function loadPreview() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.cluster.maintenancePreview(props.hostId, props.node)
    plan.value = res.data
    // Online moves are pre-selected; downtime is always an explicit choice.
    selected.value = new Set(res.data.guests.filter(g => g.class === 'online').map(g => g.sid))
    confirmDowntime.value = false
  } catch (err) {
    error.value = err?.response?.data?.detail || err?.message || 'Preview failed'
  } finally {
    loading.value = false
  }
}

async function execute() {
  const guests = [...selected.value]
  try {
    const res = await api.cluster.evacuateNode(props.hostId, props.node, {
      plan_id: plan.value.plan_id,
      guests,
      allow_downtime: selectedDowntime.value,
    })
    toast.info(`Evacuating ${res.data.guests.length} guest(s) from ${props.node}`)
    await poll(res.data.job_id)
  } catch (err) {
    toast.error('Evacuation refused: ' + (err?.response?.data?.detail || err?.message))
  }
}

async function poll(jobId) {
  clearTimeout(pollTimer)
  try {
    const res = await api.cluster.getEvacuation(props.hostId, jobId)
    job.value = res.data
    if (res.data.status === 'running') {
      pollTimer = setTimeout(() => poll(jobId), 3000)
    } else {
      const c = res.data.counts || {}
      const ok = (c.moved || 0) + (c.already_moved || 0) + (c.moved_elsewhere || 0)
      const msg = `Evacuation ${res.data.status}: ${ok} moved, ${c.failed || 0} failed, ${c.skipped || 0} skipped`
      res.data.status === 'done' ? toast.success(msg) : toast.warning(msg)
      emit('finished', res.data)
    }
  } catch (err) {
    pollTimer = setTimeout(() => poll(jobId), 5000)
  }
}

async function cancel() {
  if (!job.value) return
  try {
    await api.cluster.cancelEvacuation(props.hostId, job.value.id)
    job.value = { ...job.value, cancel_requested: true }
  } catch (err) {
    toast.error('Could not cancel: ' + (err?.response?.data?.detail || err?.message))
  }
}

async function selectRetry() {
  const wanted = new Set(retryable.value)
  await loadPreview()   // a retry uses a fresh plan; moved guests are no longer on the node
  selected.value = new Set((plan.value?.guests || []).filter(g => wanted.has(g.sid) && g.class === 'online').map(g => g.sid))
}

async function resumeRunningJob() {
  try {
    const res = await api.cluster.listEvacuations(props.hostId)
    const active = (res.data || []).find(j => j.node === props.node && j.status === 'running')
    if (active) poll(active.id)
  } catch (err) { /* nothing to resume */ }
}

watch(() => props.node, () => { job.value = null; loadPreview() })
onMounted(() => { loadPreview(); resumeRunningJob() })
onUnmounted(() => clearTimeout(pollTimer))
</script>

<style scoped>
.maint-panel .card-header { display: flex; justify-content: space-between; align-items: center; }
.checks { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.875rem; }
.check-icon { display: inline-block; width: 1.25rem; font-weight: 700; }
.check-ok .check-icon { color: var(--success, #16a34a); }
.check-warn .check-icon { color: var(--warning, #d97706); }
.check-fail .check-icon { color: var(--danger, #dc2626); }
.check-info .check-icon { color: var(--info, #2563eb); }
.summary { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
.table-wrap { overflow-x: auto; }
.reason { max-width: 32rem; font-size: 0.85rem; }
.warn-line { color: var(--warning, #b45309); }
.job-log { max-height: 14rem; overflow-y: auto; background: var(--bg-secondary); border: 1px solid var(--border-color);
  border-radius: 0.375rem; padding: 0.5rem; font-family: var(--font-mono, monospace); }
.text-xs { font-size: 0.75rem; }
.downtime-confirm { font-size: 0.875rem; }
</style>
