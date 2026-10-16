<template>
  <div class="hazfs-wizard-page">
    <div class="page-header">
      <div class="header-left">
        <router-link to="/ha-management" class="back-link">← HA</router-link>
        <h2 class="page-title">HA-ZFS Wizard</h2>
        <p class="text-muted subtitle">
          Checks the replicated ZFS storage (<code>ha-zfs</code>) that lets guests fail over without shared storage,
          and suggests changes: pool sizes for the guests and replicas each node would hold, quotas that keep a pool
          from filling its thin pool, boot ordering, the ZFS memory cap and leftover volumes. Nothing changes until
          you pick suggestions and apply them.
        </p>
      </div>
      <div class="row-gap">
        <select v-model="hostId" class="form-control host-select" :disabled="surveying || running" @change="survey()">
          <option value="">-- Select cluster --</option>
          <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
        </select>
        <button v-if="hostId" class="btn btn-outline" :disabled="surveying || running" @click="survey()">
          {{ result ? 'Check again' : 'Check cluster' }}
        </button>
      </div>
    </div>

    <div v-if="!hostId" class="card"><div class="card-body text-muted">Select a cluster to check its ZFS storage.</div></div>
    <div v-else-if="surveying" class="card">
      <div class="card-body loading-row"><div class="loading-spinner"></div> Reading every node's LVM and ZFS over SSH…</div>
    </div>
    <div v-else-if="error" class="alert alert-danger">{{ error }}</div>

    <!-- Job -->
    <div v-if="job || running" class="card mb-3">
      <div class="card-header row-between">
        <h3>{{ job ? job.description : 'Starting…' }}</h3>
        <span v-if="job" :class="['state-pill', { ok: job.status === 'done', bad: job.status === 'failed', warn: job.status === 'running' }]">
          {{ { running: 'Running', done: 'Done', failed: 'Failed' }[job.status] }}
        </span>
      </div>
      <div class="card-body">
        <ul v-if="job" class="job-steps">
          <li v-for="(s, i) in job.steps" :key="i"><span class="job-time">{{ s.time }}</span> {{ s.text }}</li>
          <li v-if="job.status === 'running'" class="text-muted"><span class="loading-spinner inline"></span> working…</li>
        </ul>
        <div v-if="job && job.error" class="alert alert-danger mt-2">{{ job.error }}</div>
        <div v-if="job && job.status !== 'running'" class="actions-row">
          <button class="btn btn-primary" :disabled="surveying" @click="survey()">Check again</button>
        </div>
      </div>
    </div>

    <template v-if="result && !surveying">
      <!-- Nodes -->
      <div class="card mb-3">
        <div class="card-header row-between">
          <h3>Nodes</h3>
          <span class="text-muted small">
            Storage <code>ha-zfs</code>:
            {{ result.storage.exists ? 'on ' + (result.storage.nodes.join(', ') || 'all nodes') : 'not created yet' }}
          </span>
        </div>
        <div class="card-body table-wrap">
          <table class="table nodes-table">
            <thead>
              <tr>
                <th>Node</th><th>Pool</th><th>Used</th><th>Quota</th><th>Underlying storage</th>
                <th>Would hold</th><th>ZFS cache cap</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="n in result.nodes" :key="n.node">
                <td><strong>{{ n.node }}</strong></td>
                <template v-if="n.error">
                  <td colspan="6" class="text-danger">{{ n.error }}</td>
                </template>
                <template v-else>
                  <td>
                    <span v-if="n.pool" :class="['state-pill', n.pool.health === 'ONLINE' ? 'ok' : 'bad']">
                      {{ fmtBytes(n.pool.size) }} · {{ n.pool.health }}
                    </span>
                    <span v-else class="text-muted">none</span>
                  </td>
                  <td>{{ n.pool ? fmtBytes(n.pool.used) : '–' }}</td>
                  <td>{{ n.pool ? (n.pool.quota ? fmtBytes(n.pool.quota) : 'none') : '–' }}</td>
                  <td>
                    <template v-if="n.backing && n.backing.kind === 'thin'">
                      thin pool {{ n.backing.vg }}/{{ n.backing.thin_pool }}:
                      {{ n.backing.data_percent.toFixed(0) }}% of {{ fmtBytes(n.backing.size) }} used
                    </template>
                    <template v-else-if="n.backing">
                      {{ n.backing.vg }}: {{ fmtBytes(n.backing.free) }} free of {{ fmtBytes(n.backing.size) }}
                    </template>
                    <span v-else class="text-muted">–</span>
                  </td>
                  <td>
                    <template v-if="n.plan">
                      {{ n.plan.guests }} guest{{ n.plan.guests === 1 ? '' : 's' }} +
                      {{ n.plan.replicas }} replica{{ n.plan.replicas === 1 ? '' : 's' }}
                      <div class="text-muted small">about {{ fmtBytes(n.plan.needed) }}</div>
                    </template>
                    <span v-else class="text-muted">–</span>
                  </td>
                  <td>{{ n.arc_max ? fmtBytes(n.arc_max) : (n.pool ? 'none' : '–') }}</td>
                </template>
              </tr>
            </tbody>
          </table>
          <p class="text-muted small mt-1">
            "Would hold" assumes every guest that can fail over through ZFS is moved into the pool on its node and
            replicated to the node the Failover Wizard would pick (most free memory, with room for it).
          </p>
        </div>
      </div>

      <!-- Suggestions -->
      <div class="card mb-3">
        <div class="card-header row-between">
          <h3>Suggested changes</h3>
          <div v-if="result.suggestions.length" class="row-gap">
            <button class="btn btn-outline btn-sm" :disabled="running" @click="selectSafe">Select all safe</button>
            <button class="btn btn-outline btn-sm" :disabled="running" @click="selected = []">Select none</button>
          </div>
        </div>
        <div class="card-body">
          <div v-if="!result.suggestions.length" class="alert alert-success">
            Nothing to change: the ZFS storage is set up the way the wizard recommends.
          </div>
          <div v-for="group in groups" :key="group.kind" class="sugg-group">
            <h4>{{ group.label }}</h4>
            <label v-for="s in group.items" :key="s.id"
                   :class="['sugg', { 'sugg--on': selected.includes(s.id), 'sugg--danger': s.impact === 'destructive' }]">
              <input v-model="selected" type="checkbox" :value="s.id" :disabled="running" />
              <div>
                <div class="sugg-title">
                  {{ s.title }}
                  <span v-if="s.impact === 'destructive'" class="state-pill bad">deletes data</span>
                </div>
                <div class="sugg-detail">{{ s.detail }}</div>
              </div>
            </label>
          </div>
          <div v-if="result.suggestions.length" class="actions-row">
            <span class="text-muted small">{{ selected.length }} selected</span>
            <button class="btn btn-primary" :disabled="!selected.length || running || result.busy" @click="apply">
              Apply selected
            </button>
          </div>
        </div>
      </div>

      <!-- Notes -->
      <div v-if="result.notes.length" class="card">
        <div class="card-header"><h3>Notes</h3></div>
        <div class="card-body">
          <ul class="notes">
            <li v-for="(n, i) in result.notes" :key="i" :class="['note', 'note-' + n.level]">
              <span class="note-icon">{{ n.level === 'warn' ? '!' : 'i' }}</span>
              <span>{{ n.text }}</span>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const route = useRoute()
const toast = useToast()

const hosts = ref([])
const hostId = ref(route.query.hostId ? Number(route.query.hostId) : '')
const result = ref(null)
const surveying = ref(false)
const error = ref('')
const selected = ref([])
const job = ref(null)
const running = ref(false)
let pollTimer = null

const groupLabels = {
  setup: 'Set up the pool on more nodes',
  storage_create: 'Storage',
  storage_node: 'Storage',
  remove_volume: 'Unused volumes (frees space)',
  grow: 'Pool size',
  quota: 'Protect thin pools',
  autotrim: 'Protect thin pools',
  dropin: 'Boot order',
  arc: 'Memory'
}

const groups = computed(() => {
  const out = []
  for (const s of result.value?.suggestions || []) {
    const label = groupLabels[s.kind] || s.kind
    let g = out.find(x => x.label === label)
    if (!g) { g = { kind: s.kind, label, items: [] }; out.push(g) }
    g.items.push(s)
  }
  return out
})

function fmtBytes (b) {
  if (!b) return '0 B'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let i = 0
  while (b >= 1024 && i < units.length - 1) { b /= 1024; i++ }
  return `${b.toFixed(i >= 4 ? 1 : 0)} ${units[i]}`
}

function errText (e) {
  return e?.response?.data?.detail || e?.message || 'Request failed'
}

function selectSafe () {
  selected.value = (result.value?.suggestions || []).filter(s => s.impact !== 'destructive').map(s => s.id)
}

async function loadHosts () {
  try {
    const res = await api.proxmox.listHosts()
    hosts.value = res.data || []
    if (!hostId.value && hosts.value.length === 1) hostId.value = hosts.value[0].id
  } catch (e) {
    toast.error('Could not load clusters: ' + errText(e))
  }
}

async function survey (keepJob = false) {
  if (!hostId.value) return
  if (keepJob !== true) { stopPolling(); job.value = null }
  surveying.value = true
  error.value = ''
  try {
    const res = await api.haZfsWizard.survey(hostId.value)
    result.value = res.data
    selectSafe()
  } catch (e) {
    result.value = null
    error.value = errText(e)
  } finally {
    surveying.value = false
  }
}

async function apply () {
  const chosen = result.value.suggestions.filter(s => selected.value.includes(s.id))
  const destructive = chosen.filter(s => s.impact === 'destructive')
  let text = 'Apply these changes?\n\n' + chosen.map(s => '• ' + s.title).join('\n')
  if (destructive.length) {
    text += `\n\n${destructive.length} of them DELETE volumes. That cannot be undone.`
  }
  if (!confirm(text)) return
  running.value = true
  try {
    const res = await api.haZfsWizard.apply(hostId.value, chosen.map(s => ({ id: s.id, fingerprint: s.fingerprint })))
    pollJob(res.data.job_id)
  } catch (e) {
    running.value = false
    toast.error(errText(e))
  }
}

function pollJob (jobId) {
  stopPolling()
  const tick = async () => {
    try {
      const res = await api.haWizard.job(jobId)
      job.value = res.data
      if (res.data.status === 'running') {
        pollTimer = setTimeout(tick, 2000)
        return
      }
      running.value = false
      if (res.data.status === 'done') toast.success(res.data.description + ': done')
      else toast.error(res.data.description + ': failed')
      survey(true)   // the old survey is used up; show the cluster as it is now
    } catch (e) {
      running.value = false
      toast.error('Lost track of the job: ' + errText(e))
    }
  }
  tick()
}

function stopPolling () {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
}

onMounted(async () => {
  await loadHosts()
  if (hostId.value) survey()
})
onUnmounted(stopPolling)
</script>

<style scoped>
.hazfs-wizard-page { padding: 1.5rem; max-width: 1300px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.back-link { color: var(--primary-color, #3b82f6); text-decoration: none; font-size: 0.9rem; }
.back-link:hover { text-decoration: underline; }
.subtitle { max-width: 820px; margin-top: 0.25rem; }
.row-between { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
.row-gap { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.host-select { min-width: 200px; }
.mb-3 { margin-bottom: 1.25rem; }
.mt-1 { margin-top: 0.5rem; }
.mt-2 { margin-top: 0.75rem; }
.small { font-size: 0.85rem; }
.loading-row { display: flex; align-items: center; gap: 0.75rem; color: var(--text-muted, #888); }
.loading-spinner.inline { display: inline-block; width: 0.9rem; height: 0.9rem; vertical-align: middle; }
.actions-row { display: flex; justify-content: flex-end; align-items: center; gap: 0.75rem; margin-top: 1rem; }
.table-wrap { overflow-x: auto; }
.nodes-table td, .nodes-table th { white-space: nowrap; }
.text-danger { color: var(--danger-color, #ef4444); }

.state-pill { display: inline-block; padding: 0.1rem 0.55rem; border-radius: 999px; font-size: 0.8rem; border: 1px solid var(--border-color, #333); white-space: nowrap; }
.state-pill.ok { color: var(--success-color, #10b981); border-color: var(--success-color, #10b981); }
.state-pill.warn { color: var(--warning-color, #f59e0b); border-color: var(--warning-color, #f59e0b); }
.state-pill.bad { color: var(--danger-color, #ef4444); border-color: var(--danger-color, #ef4444); }

.sugg-group h4 { margin: 1.25rem 0 0.5rem; font-size: 0.95rem; color: var(--text-muted, #888); font-weight: 600; }
.sugg-group:first-child h4 { margin-top: 0; }
.sugg { display: flex; gap: 0.75rem; align-items: flex-start; padding: 0.65rem 0.8rem; border: 1px solid var(--border-color, #333); border-radius: 6px; margin-bottom: 0.5rem; cursor: pointer; }
.sugg input { margin-top: 0.25rem; flex-shrink: 0; }
.sugg--on { border-color: var(--primary-color, #3b82f6); background: rgba(59, 130, 246, 0.06); }
.sugg--danger.sugg--on { border-color: var(--danger-color, #ef4444); background: rgba(239, 68, 68, 0.06); }
.sugg-title { font-weight: 600; display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.sugg-detail { color: var(--text-muted, #888); font-size: 0.9rem; margin-top: 0.2rem; }

.notes { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.note { display: flex; gap: 0.6rem; align-items: flex-start; font-size: 0.92rem; }
.note-icon { width: 1.3rem; height: 1.3rem; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; font-size: 0.8rem; color: white; background: var(--primary-color, #3b82f6); }
.note-warn .note-icon { background: var(--warning-color, #f59e0b); }

.job-steps { list-style: none; padding: 0; margin: 0; font-family: var(--font-mono, monospace); font-size: 0.88rem; display: flex; flex-direction: column; gap: 0.3rem; }
.job-time { color: var(--text-muted, #888); margin-right: 0.5rem; }

@media (max-width: 720px) {
  .hazfs-wizard-page { padding: 1rem; }
}
</style>
