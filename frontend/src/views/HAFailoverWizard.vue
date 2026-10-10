<template>
  <div class="failover-wizard-page">
    <div class="page-header mb-3">
      <div class="header-left">
        <router-link to="/ha-management" class="back-link">← HA</router-link>
        <h2 class="page-title">Failover Wizard</h2>
        <p class="text-muted subtitle">
          Make a VM or container restart on another node automatically if its node fails.
          The settings are fixed to what works best; the wizard checks the guest and shows exactly what it will change.
        </p>
      </div>
    </div>

    <div class="wizard-steps mb-4">
      <div
        v-for="(label, idx) in stepLabels"
        :key="idx"
        :class="['wizard-step', step === idx + 1 ? 'wizard-step--active' : '', step > idx + 1 ? 'wizard-step--done' : '']"
      >
        <div class="wizard-step__circle">
          <span v-if="step > idx + 1">&#10003;</span>
          <span v-else>{{ idx + 1 }}</span>
        </div>
        <span class="wizard-step__label">{{ label }}</span>
        <div v-if="idx < stepLabels.length - 1" class="wizard-step__connector"></div>
      </div>
    </div>

    <!-- ─── Step 1: choose guest ─── -->
    <div v-if="step === 1" class="card wizard-body">
      <div class="card-header row-between">
        <h3>Choose a guest</h3>
        <div class="row-gap">
          <select v-model="hostId" class="form-control host-select" @change="loadGuests">
            <option value="">-- Select cluster --</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
          </select>
          <input v-model="filter" class="form-control filter" placeholder="Filter by name, ID or node" />
          <button v-if="hostId" class="btn btn-outline btn-sm" :disabled="loadingGuests" @click="loadGuests">Refresh</button>
        </div>
      </div>
      <div class="card-body">
        <div v-if="!hostId" class="text-muted">Select a cluster to see its guests.</div>
        <div v-else-if="loadingGuests" class="loading-row"><div class="loading-spinner"></div> Checking every guest…</div>
        <div v-else-if="guestsError" class="alert alert-danger">{{ guestsError }}</div>
        <template v-else>
          <div class="summary-row mb-2">
            <span v-for="(n, s) in stateCounts" :key="s" :class="['state-pill', 'state-' + s]">{{ stateLabels[s] }}: {{ n }}</span>
          </div>
          <div v-if="allBlockedByStorage" class="alert alert-info mb-2">
            None of these guests can fail over yet: their disks are on storage that only one node can reach.
            Failover needs shared storage (an NFS share, Ceph or iSCSI) or ZFS on at least two nodes.
            Once the cluster has one, the wizard can move a guest's disks there for you.
          </div>
          <table class="table guests-table">
            <thead>
              <tr><th>ID</th><th>Name</th><th>Node</th><th>Type</th><th>Status</th><th>Failover</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="g in filteredGuests" :key="g.vmid" class="clickable" @click="chooseGuest(g)">
                <td>{{ g.vmid }}</td>
                <td>{{ g.name }}</td>
                <td>{{ g.node }}</td>
                <td>{{ g.vmtype === 'lxc' ? 'CT' : 'VM' }}</td>
                <td>{{ g.status }}</td>
                <td><span :class="['state-pill', 'state-' + g.state]">{{ g.summary }}</span></td>
                <td class="text-right"><button class="btn btn-outline btn-sm">Check →</button></td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </div>

    <!-- ─── Step 2: readiness ─── -->
    <div v-if="step === 2" class="card wizard-body">
      <div class="card-header row-between">
        <h3>Readiness: {{ guestLabel }}</h3>
        <button class="btn btn-outline btn-sm" :disabled="loadingPlan" @click="loadPlan">Re-check</button>
      </div>
      <div class="card-body">
        <div v-if="loadingPlan" class="loading-row"><div class="loading-spinner"></div> Checking the guest and cluster…</div>
        <div v-else-if="planError" class="alert alert-danger">{{ planError }}</div>
        <template v-else-if="plan">
          <ul class="checks">
            <li v-for="(c, i) in plan.checks" :key="i" :class="['check', 'check-' + c.status]">
              <span class="check-icon">{{ checkIcons[c.status] }}</span>
              <div>
                <div class="check-title">{{ c.title }}</div>
                <div v-if="c.detail" class="check-detail">{{ c.detail }}</div>
              </div>
            </li>
          </ul>

          <div v-if="plan.already_protected" class="mt-3">
            <h4>Current HA setup</h4>
            <table class="table settings-table">
              <tr><th>HA resource</th><td>{{ plan.existing.resource.sid }} · state {{ plan.existing.resource.state }}</td></tr>
              <tr v-if="plan.existing.group"><th>HA group {{ plan.existing.group.group }}</th><td>nodes {{ plan.existing.group.nodes }}{{ plan.existing.group.restricted ? ' · restricted' : '' }}</td></tr>
              <tr v-for="r in plan.existing.rules" :key="r.rule"><th>Rule {{ r.rule }}</th><td>{{ r.type }} · nodes {{ r.nodes || '–' }}{{ r.strict ? ' · strict' : '' }}</td></tr>
              <tr v-for="j in plan.existing.replication" :key="j.id"><th>Replication {{ j.id }}</th><td>to {{ j.target }} · {{ j.schedule || '*/15' }}</td></tr>
            </table>
            <div class="actions-row">
              <button class="btn btn-outline" @click="backToList">Back</button>
              <button class="btn btn-danger" :disabled="starting" @click="removeFailover">Remove failover</button>
            </div>
          </div>

          <div v-else-if="plan.eligible" class="actions-row mt-3">
            <button class="btn btn-outline" @click="backToList">Back</button>
            <button class="btn btn-primary" @click="step = 3">Review plan →</button>
          </div>

          <div v-else-if="plan.move_options.length" class="mt-3">
            <h4>Move the disks to storage that supports failover</h4>
            <p class="text-muted">
              The disks are copied while the guest keeps running (VMs) and the old copies are deleted afterwards.
              Then failover is set up with the same fixed settings.
            </p>
            <label v-for="o in plan.move_options" :key="o.storage" class="move-option">
              <input v-model="moveStorage" type="radio" :value="o.storage" />
              <span>
                <strong>{{ o.storage }}</strong> ({{ o.type }}{{ o.shared ? ', shared' : ', ZFS: replicated every 2 minutes' }})
                · {{ fmtBytes(o.avail) }} free, needs {{ fmtBytes(o.needed) }} · also on {{ o.other_nodes.join(', ') }}
              </span>
            </label>
            <div class="actions-row">
              <button class="btn btn-outline" @click="backToList">Back</button>
              <button class="btn btn-primary" :disabled="!moveStorage" @click="step = 3">Review plan →</button>
            </div>
          </div>

          <div v-else class="actions-row mt-3">
            <button class="btn btn-outline" @click="backToList">Back</button>
          </div>
        </template>
      </div>
    </div>

    <!-- ─── Step 3: plan ─── -->
    <div v-if="step === 3 && plan" class="card wizard-body">
      <div class="card-header"><h3>Plan: {{ guestLabel }}</h3></div>
      <div class="card-body">
        <template v-if="moveStorage">
          <ol class="plan-actions">
            <li>Move all disks to <strong>{{ moveStorage }}</strong> ({{ fmtBytes(selectedMove.needed) }}), deleting the old copies</li>
            <li>Check the guest again and, if it is now eligible, set up failover:
              {{ selectedMove.shared ? 'HA with shared storage (no data loss)' : 'ZFS replication every 2 minutes plus HA' }},
              failing over to the node with the most free memory</li>
          </ol>
        </template>
        <template v-else>
          <table class="table settings-table mb-3">
            <tr><th>Protection</th><td>{{ plan.mode === 'shared' ? 'Shared storage: the failover node uses the same disks, no data loss' : 'ZFS replication every 2 minutes: up to about 2 minutes of changes can be lost' }}</td></tr>
            <tr><th>Runs on</th><td>{{ plan.node }} (preferred)</td></tr>
            <tr><th>Fails over to</th><td>{{ plan.target }}{{ planStrict ? ' (only these two nodes have the disks)' : ' (or any other node if both are down)' }}</td></tr>
            <tr><th>On failure</th><td>restart once on the same node, then move once to the failover node</td></tr>
            <tr><th>When {{ plan.node }} returns</th><td>move back to {{ plan.node }} automatically</td></tr>
            <tr><th>Node reboot / shutdown</th><td>{{ plan.settings.cluster_ha_option ? 'HA guests are migrated away first (cluster setting, applies to all HA guests)' : 'unchanged (the cluster already has an HA shutdown policy)' }}</td></tr>
          </table>
          <h4>Changes</h4>
          <ol class="plan-actions">
            <li v-for="(a, i) in plan.actions" :key="i">{{ a.label }}</li>
          </ol>
        </template>
        <div class="alert alert-warning mt-3">
          <strong>How failover works:</strong> Proxmox notices when a node stops responding, waits about a minute,
          and makes sure it is really down (the node resets itself through its watchdog) before starting the guest elsewhere.
          A node running HA guests that loses contact with the rest of the cluster for about a minute will reset itself,
          so keep the cluster network reliable. This keeps working when Depl0y itself is down.
        </div>
        <div class="actions-row">
          <button class="btn btn-outline" @click="step = 2">Back</button>
          <button class="btn btn-primary" :disabled="starting" @click="applyPlan">
            {{ moveStorage ? 'Move disks and enable failover' : 'Enable failover' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ─── Step 4: progress ─── -->
    <div v-if="step === 4" class="card wizard-body">
      <div class="card-header row-between">
        <h3>{{ job ? job.description : 'Starting…' }}</h3>
        <span v-if="job" :class="['state-pill', 'job-' + job.status]">{{ jobStatusLabel }}</span>
      </div>
      <div class="card-body">
        <ul v-if="job" class="job-steps">
          <li v-for="(s, i) in job.steps" :key="i">
            <span class="job-time">{{ s.time }}</span> {{ s.text }}
          </li>
          <li v-if="job.status === 'running'" class="text-muted"><span class="loading-spinner inline"></span> working…</li>
        </ul>
        <div v-if="job && job.error" class="alert alert-danger mt-2">{{ job.error }}</div>
        <div v-if="job && job.status !== 'running'" class="actions-row">
          <button class="btn btn-outline" @click="backToList">Back to guests</button>
          <router-link to="/ha-management" class="btn btn-primary">Open HA</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const route = useRoute()
const toast = useToast()

const stepLabels = ['Choose guest', 'Readiness', 'Plan', 'Apply']
const step = ref(1)
const hosts = ref([])
const hostId = ref(route.query.hostId ? Number(route.query.hostId) : '')
const guests = ref([])
const loadingGuests = ref(false)
const guestsError = ref('')
const filter = ref('')
const guest = ref(null)
const plan = ref(null)
const loadingPlan = ref(false)
const planError = ref('')
const moveStorage = ref('')
const starting = ref(false)
const job = ref(null)
let pollTimer = null

const checkIcons = { ok: '✓', warn: '!', fail: '✗', info: 'i' }
const stateLabels = { protected: 'Protected', ready: 'Ready', movable: 'Needs disk move', blocked: 'Cannot fail over', unknown: 'Unknown' }

const guestLabel = computed(() => guest.value
  ? `${guest.value.vmtype === 'lxc' ? 'CT' : 'VM'} ${guest.value.vmid}${guest.value.name ? ' (' + guest.value.name + ')' : ''} on ${guest.value.node}`
  : '')
const filteredGuests = computed(() => {
  const q = filter.value.trim().toLowerCase()
  if (!q) return guests.value
  return guests.value.filter(g => `${g.vmid} ${g.name} ${g.node}`.toLowerCase().includes(q))
})
const stateCounts = computed(() => {
  const counts = {}
  for (const g of guests.value) counts[g.state] = (counts[g.state] || 0) + 1
  return counts
})
const allBlockedByStorage = computed(() => guests.value.length > 0 &&
  guests.value.every(g => g.state === 'blocked' && g.summary === 'Disks are on node-local storage'))
const planStrict = computed(() => {
  const s = plan.value?.settings || {}
  return Boolean(s.rule ? s.rule.strict : s.group?.restricted)
})
const selectedMove = computed(() => plan.value?.move_options.find(o => o.storage === moveStorage.value) || {})
const jobStatusLabel = computed(() => ({ running: 'Running', done: 'Done', failed: 'Failed' }[job.value?.status] || ''))

function fmtBytes (b) {
  if (!b) return '0 B'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let i = 0
  while (b >= 1024 && i < units.length - 1) { b /= 1024; i++ }
  return `${b.toFixed(i >= 3 ? 1 : 0)} ${units[i]}`
}

function errText (e) {
  return e?.response?.data?.detail || e?.message || 'Request failed'
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

async function loadGuests () {
  if (!hostId.value) return
  loadingGuests.value = true
  guestsError.value = ''
  try {
    const res = await api.haWizard.guests(hostId.value)
    guests.value = res.data.guests
  } catch (e) {
    guestsError.value = errText(e)
  } finally {
    loadingGuests.value = false
  }
}

async function loadPlan () {
  loadingPlan.value = true
  planError.value = ''
  try {
    const g = guest.value
    const res = await api.haWizard.plan(hostId.value, g.node, g.vmtype, g.vmid)
    plan.value = res.data
    if (plan.value.name && guest.value) guest.value = { ...guest.value, name: plan.value.name }
    // Preselect the best move target (shared storage first, then most free space).
    if (!plan.value.move_options.some(o => o.storage === moveStorage.value)) {
      moveStorage.value = plan.value.move_options[0]?.storage || ''
    }
  } catch (e) {
    planError.value = errText(e)
  } finally {
    loadingPlan.value = false
  }
}

function chooseGuest (g) {
  guest.value = g
  plan.value = null
  moveStorage.value = ''
  step.value = 2
  loadPlan()
}

function backToList () {
  stopPolling()
  step.value = 1
  job.value = null
  loadGuests()
}

async function startJob (request) {
  starting.value = true
  try {
    const res = await request()
    job.value = null
    step.value = 4
    pollJob(res.data.job_id)
  } catch (e) {
    toast.error(errText(e))
  } finally {
    starting.value = false
  }
}

function applyPlan () {
  const g = guest.value
  const what = moveStorage.value
    ? `move the disks of ${guestLabel.value} to ${moveStorage.value} and enable failover`
    : `enable failover for ${guestLabel.value}`
  if (!confirm(`This will ${what}. Continue?`)) return
  startJob(() => api.haWizard.apply(hostId.value, g.node, g.vmtype, g.vmid,
    moveStorage.value ? { move_storage: moveStorage.value } : {}))
}

function removeFailover () {
  const g = guest.value
  if (!confirm(`Remove ${guestLabel.value} from HA? The guest keeps running but will no longer restart elsewhere if ${g.node} fails.`)) return
  startJob(() => api.haWizard.remove(hostId.value, g.node, g.vmtype, g.vmid))
}

function pollJob (jobId) {
  stopPolling()
  const tick = async () => {
    try {
      const res = await api.haWizard.job(jobId)
      job.value = res.data
      if (res.data.status === 'running') {
        pollTimer = setTimeout(tick, 2000)
      } else if (res.data.status === 'done') {
        toast.success(res.data.description + ': done')
      } else {
        toast.error(res.data.description + ': failed')
      }
    } catch (e) {
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
  if (!hostId.value) return
  const { node, vmid, type } = route.query
  if (node && vmid) {
    chooseGuest({ node, vmid: Number(vmid), vmtype: type === 'lxc' ? 'lxc' : 'qemu', name: route.query.name || '' })
  }
  loadGuests()
})
onUnmounted(stopPolling)
</script>

<style scoped>
.failover-wizard-page { padding: 1.5rem; max-width: 1200px; }
.mt-2 { margin-top: 0.75rem; }
.mt-3 { margin-top: 1.25rem; }
.mb-2 { margin-bottom: 0.75rem; }
.mb-3 { margin-bottom: 1.25rem; }
.mb-4 { margin-bottom: 1.75rem; }
.page-header { margin-bottom: 1.5rem; }
.wizard-body h4 { margin: 1.5rem 0 0.6rem; font-size: 1rem; }
.wizard-body .alert { margin-top: 1.25rem; }
.back-link { color: var(--primary-color, #3b82f6); text-decoration: none; font-size: 0.9rem; }
.back-link:hover { text-decoration: underline; }
.subtitle { max-width: 760px; margin-top: 0.25rem; }
.row-between { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
.row-gap { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.host-select { min-width: 200px; }
.filter { min-width: 220px; }
.loading-row { display: flex; align-items: center; gap: 0.75rem; color: var(--text-muted, #888); }
.loading-spinner.inline { display: inline-block; width: 0.9rem; height: 0.9rem; vertical-align: middle; }
.actions-row { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem; }
.text-right { text-align: right; }

/* Step indicator (same as MigrationWizard) */
.wizard-steps { display: flex; align-items: center; gap: 0; margin-bottom: 1.5rem; }
.wizard-step { display: flex; align-items: center; gap: 0.5rem; flex: 1; }
.wizard-step__circle {
  width: 2rem; height: 2rem; border-radius: 50%; border: 2px solid var(--border-color, #333);
  display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: 600;
  background: var(--card-bg, #1a1a1a); color: var(--text-muted, #888); flex-shrink: 0; transition: all 0.2s;
}
.wizard-step--active .wizard-step__circle { border-color: var(--primary-color, #3b82f6); color: var(--primary-color, #3b82f6); background: rgba(59, 130, 246, 0.1); }
.wizard-step--done .wizard-step__circle { border-color: var(--success-color, #10b981); color: white; background: var(--success-color, #10b981); }
.wizard-step__label { font-size: 0.85rem; font-weight: 500; color: var(--text-muted, #888); white-space: nowrap; }
.wizard-step--active .wizard-step__label { color: var(--text-primary, #e0e0e0); }
.wizard-step--done .wizard-step__label { color: var(--success-color, #10b981); }
.wizard-step__connector { flex: 1; height: 2px; background: var(--border-color, #333); margin: 0 0.5rem; }

/* Guest list */
.summary-row { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.guests-table tr.clickable { cursor: pointer; }
.guests-table tr.clickable:hover { background: rgba(59, 130, 246, 0.06); }
.state-pill { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px; font-size: 0.8rem; border: 1px solid var(--border-color, #333); white-space: nowrap; }
.state-protected, .job-done { color: var(--success-color, #10b981); border-color: var(--success-color, #10b981); }
.state-ready { color: var(--primary-color, #3b82f6); border-color: var(--primary-color, #3b82f6); }
.state-movable, .job-running { color: var(--warning-color, #f59e0b); border-color: var(--warning-color, #f59e0b); }
.state-blocked, .job-failed { color: var(--danger-color, #ef4444); border-color: var(--danger-color, #ef4444); }
.state-unknown { color: var(--text-muted, #888); }

/* Checks */
.checks { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.6rem; }
.check { display: flex; gap: 0.75rem; align-items: flex-start; padding: 0.6rem 0.75rem; border-radius: 6px; border: 1px solid var(--border-color, #333); }
.check-icon { width: 1.5rem; height: 1.5rem; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; font-size: 0.85rem; }
.check-ok .check-icon { background: var(--success-color, #10b981); color: white; }
.check-warn .check-icon { background: var(--warning-color, #f59e0b); color: white; }
.check-fail .check-icon { background: var(--danger-color, #ef4444); color: white; }
.check-info .check-icon { background: var(--primary-color, #3b82f6); color: white; }
.check-fail { border-color: var(--danger-color, #ef4444); }
.check-title { font-weight: 600; }
.check-detail { color: var(--text-muted, #888); font-size: 0.9rem; margin-top: 0.15rem; }

/* Plan */
.settings-table th { width: 220px; text-align: left; vertical-align: top; color: var(--text-muted, #888); font-weight: 500; }
.plan-actions { padding-left: 1.25rem; display: flex; flex-direction: column; gap: 0.35rem; }
.move-option { display: flex; gap: 0.6rem; align-items: flex-start; padding: 0.5rem 0; cursor: pointer; }

/* Progress */
.job-steps { list-style: none; padding: 0; margin: 0; font-family: var(--font-mono, monospace); font-size: 0.88rem; display: flex; flex-direction: column; gap: 0.3rem; }
.job-time { color: var(--text-muted, #888); margin-right: 0.5rem; }

@media (max-width: 720px) {
  .failover-wizard-page { padding: 1rem; }
  .wizard-step__label { display: none; }
  .guests-table th:nth-child(4), .guests-table td:nth-child(4),
  .guests-table th:nth-child(5), .guests-table td:nth-child(5) { display: none; }
  .settings-table th { width: auto; }
}
</style>
