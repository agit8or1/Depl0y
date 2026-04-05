<template>
  <div class="replication-page">
    <div class="page-header mb-2">
      <div>
        <h2>Replication Manager</h2>
        <p class="text-muted">Manage VM replication jobs across cluster nodes</p>
      </div>
      <div class="header-actions">
        <select v-model="selectedHostId" @change="onHostChange" class="form-control host-select">
          <option value="">-- Select Host --</option>
          <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
        </select>
        <button v-if="selectedHostId" @click="openCreateModal" class="btn btn-primary">
          + New Replication Job
        </button>
        <button v-if="selectedHostId" @click="loadReplication" class="btn btn-outline btn-sm">
          Refresh
        </button>
      </div>
    </div>

    <!-- No host selected -->
    <div v-if="!selectedHostId" class="card">
      <div class="card-body text-muted text-center p-3">
        Select a Proxmox host to manage replication jobs.
      </div>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="card">
      <div class="loading-spinner"></div>
    </div>

    <!-- Empty state -->
    <div v-else-if="jobs.length === 0" class="card">
      <div class="card-body text-center text-muted p-3">
        No replication jobs configured.
        <br />
        <button class="btn btn-primary mt-2" @click="openCreateModal">Create First Job</button>
      </div>
    </div>

    <!-- Jobs table -->
    <div v-else class="card">
      <div class="card-header">
        <h3>Replication Jobs ({{ jobs.length }})</h3>
      </div>
      <div class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>VM / CT</th>
              <th>Source</th>
              <th>Target</th>
              <th>Schedule</th>
              <th>Last Sync</th>
              <th>Next Sync</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id">
              <td class="text-sm"><strong>{{ job.id }}</strong></td>
              <td class="text-sm">{{ job.guest || job.vmid || '—' }}</td>
              <td class="text-sm">{{ job.source || '—' }}</td>
              <td class="text-sm">{{ job.target || '—' }}</td>
              <td class="text-sm text-muted">{{ job.schedule || 'manual' }}</td>
              <td class="text-sm text-muted">
                {{ job.last_sync ? formatTime(job.last_sync) : '—' }}
              </td>
              <td class="text-sm text-muted">
                {{ job.next_sync ? formatTime(job.next_sync) : '—' }}
              </td>
              <td>
                <span :class="statusBadge(job)">{{ jobStatus(job) }}</span>
              </td>
              <td>
                <div class="action-btns">
                  <button
                    class="btn btn-outline btn-xs"
                    :disabled="forceSyncLoading[job.id]"
                    @click="forceSync(job)"
                    title="Force sync now"
                  >
                    {{ forceSyncLoading[job.id] ? '...' : 'Sync Now' }}
                  </button>
                  <button
                    class="btn btn-danger btn-xs"
                    @click="confirmDelete(job)"
                    title="Delete replication job"
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Running sync tasks -->
    <div v-if="syncTasks.length" class="card mt-2">
      <div class="card-header">
        <h3>Running Sync Tasks</h3>
        <button class="btn btn-outline btn-sm" @click="refreshSyncTasks">Refresh</button>
      </div>
      <div class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Node</th>
              <th>Started</th>
              <th>Status</th>
              <th>UPID</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in syncTasks" :key="t.upid">
              <td class="text-sm">{{ t.id || '—' }}</td>
              <td class="text-sm text-muted">{{ t._node || t.node }}</td>
              <td class="text-sm text-muted">{{ t.starttime ? formatTime(t.starttime) : '—' }}</td>
              <td>
                <span :class="taskBadge(t.status)">{{ t.status || 'running' }}</span>
              </td>
              <td class="text-xs text-muted upid-cell">{{ t.upid }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Create Job Modal -->
    <div v-if="showCreateModal" class="modal-backdrop" @click.self="closeModal">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Create Replication Job</h3>
          <button @click="closeModal" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Source VM / CT ID *</label>
            <select v-model="newJob.source_vmid" class="form-control">
              <option value="">-- Select VM/CT --</option>
              <option v-for="vm in clusterVms" :key="vm.vmid" :value="vm.vmid">
                {{ vm.vmid }} — {{ vm.name || 'unnamed' }} ({{ vm.node }}, {{ vm.type === 'lxc' ? 'CT' : 'VM' }})
              </option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Target Node *</label>
            <select v-model="newJob.target" class="form-control">
              <option value="">-- Select Target Node --</option>
              <option v-for="n in targetNodes" :key="n.name" :value="n.name">{{ n.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Schedule (cron syntax)</label>
            <input v-model="newJob.schedule" class="form-control" placeholder="*/15 * * * * (every 15 min)" />
            <span class="form-hint text-xs text-muted">Leave blank for manual-only. Examples: <code>*/15 * * * *</code>, <code>0 2 * * *</code></span>
          </div>
          <div class="form-group">
            <label class="form-label">Rate Limit (MB/s)</label>
            <input v-model.number="newJob.rate" type="number" class="form-control" placeholder="0 = unlimited" min="0" />
          </div>
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input type="checkbox" v-model="newJob.compress" class="form-check" />
              Enable compression
            </label>
          </div>
          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="newJob.comment" class="form-control" placeholder="Optional description" />
          </div>
          <div v-if="createError" class="text-danger text-sm mt-1">{{ createError }}</div>
        </div>
        <div class="modal-footer">
          <button @click="closeModal" class="btn btn-outline">Cancel</button>
          <button
            @click="createJob"
            class="btn btn-primary"
            :disabled="!newJob.source_vmid || !newJob.target || creating"
          >
            {{ creating ? 'Creating...' : 'Create Job' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="deleteTarget" class="modal-backdrop" @click.self="deleteTarget = null">
      <div class="modal-box modal-box--sm">
        <div class="modal-header">
          <h3>Delete Replication Job</h3>
          <button @click="deleteTarget = null" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <p class="text-sm">
            Are you sure you want to delete replication job <strong>{{ deleteTarget.id }}</strong>?
          </p>
          <p class="text-sm text-muted">This will stop replication for VM {{ deleteTarget.guest || deleteTarget.vmid }} to {{ deleteTarget.target }}.</p>
        </div>
        <div class="modal-footer">
          <button @click="deleteTarget = null" class="btn btn-outline">Cancel</button>
          <button @click="deleteJob" class="btn btn-danger" :disabled="deleting">
            {{ deleting ? 'Deleting...' : 'Delete' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Sync task progress modal -->
    <div v-if="activeSyncUpid" class="modal-backdrop" @click.self="activeSyncUpid = null">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Sync Task Progress</h3>
          <button @click="activeSyncUpid = null" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <p class="text-xs text-muted mb-1">UPID: {{ activeSyncUpid }}</p>
          <div v-if="syncTaskLog.length === 0 && syncTaskRunning" class="text-muted text-sm">
            Waiting for output...
          </div>
          <pre class="task-log">{{ syncTaskLog.join('\n') || 'No output yet.' }}</pre>
          <div v-if="!syncTaskRunning" class="text-sm mt-1">
            <span :class="syncTaskStatus === 'OK' ? 'text-success' : 'text-danger'">
              Task {{ syncTaskStatus || 'completed' }}
            </span>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="activeSyncUpid = null" class="btn btn-outline">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

const route = useRoute()
const toast = useToast()

const hosts = ref([])
const selectedHostId = ref(route.query.hostId ? Number(route.query.hostId) : '')
const jobs = ref([])
const loading = ref(false)
const clusterNodes = ref([])
const clusterVms = ref([])

// Force sync tracking
const forceSyncLoading = ref({})
const syncTasks = ref([])

// Create modal
const showCreateModal = ref(false)
const creating = ref(false)
const createError = ref('')
const newJob = ref({
  source_vmid: '',
  target: '',
  schedule: '',
  rate: 0,
  compress: true,
  comment: '',
})

// Delete modal
const deleteTarget = ref(null)
const deleting = ref(false)

// Sync progress
const activeSyncUpid = ref(null)
const activeSyncNode = ref(null)
const syncTaskLog = ref([])
const syncTaskRunning = ref(false)
const syncTaskStatus = ref('')
let syncPollTimer = null

const targetNodes = computed(() => {
  if (!newJob.value.source_vmid) return clusterNodes.value
  const vm = clusterVms.value.find(v => String(v.vmid) === String(newJob.value.source_vmid))
  if (!vm) return clusterNodes.value
  return clusterNodes.value.filter(n => n.name !== vm.node)
})

function formatTime(ts) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString()
}

function jobStatus(job) {
  if (job.error) return 'Error'
  if (!job.enabled && job.enabled !== undefined) return 'Disabled'
  if (job.state === 'error') return 'Error'
  if (job.state === 'replicating') return 'Running'
  return 'OK'
}

function statusBadge(job) {
  const s = jobStatus(job)
  if (s === 'Error') return 'badge badge-danger'
  if (s === 'Disabled') return 'badge badge-secondary'
  if (s === 'Running') return 'badge badge-info badge-pulse'
  return 'badge badge-success'
}

function taskBadge(status) {
  if (status === 'OK') return 'badge badge-success'
  if (!status || status === 'running') return 'badge badge-warning'
  return 'badge badge-danger'
}

async function loadHosts() {
  try {
    const res = await api.proxmox.listHosts()
    hosts.value = res.data || []
  } catch (e) {
    console.warn('Failed to load hosts', e)
  }
}

async function onHostChange() {
  if (!selectedHostId.value) return
  await Promise.all([loadReplication(), loadClusterData()])
}

async function loadClusterData() {
  if (!selectedHostId.value) return
  try {
    const [statusRes, resRes] = await Promise.all([
      api.pveNode.clusterStatus(selectedHostId.value),
      api.pveNode.clusterResources(selectedHostId.value),
    ])
    clusterNodes.value = (statusRes.data || []).filter(i => i.type === 'node')
    clusterVms.value = (resRes.data || []).filter(r => r.type === 'qemu' || r.type === 'lxc')
  } catch (e) {
    console.warn('Failed to load cluster data', e)
  }
}

async function loadReplication() {
  if (!selectedHostId.value) return
  loading.value = true
  try {
    const res = await api.cluster.listReplication(selectedHostId.value)
    jobs.value = res.data || []
  } catch (err) {
    toast.error('Failed to load replication jobs: ' + (err?.response?.data?.detail || err?.message))
  } finally {
    loading.value = false
  }
}

async function refreshSyncTasks() {
  if (!selectedHostId.value) return
  try {
    const res = await api.cluster.listTasks(selectedHostId.value, { typefilter: 'replicate', limit: 20 })
    syncTasks.value = (res.data || []).filter(t => !t.status || t.status === 'running')
  } catch { /* ignore */ }
}

function openCreateModal() {
  newJob.value = { source_vmid: '', target: '', schedule: '', rate: 0, compress: true, comment: '' }
  createError.value = ''
  showCreateModal.value = true
}

function closeModal() {
  showCreateModal.value = false
  createError.value = ''
}

async function createJob() {
  if (!newJob.value.source_vmid || !newJob.value.target) return
  creating.value = true
  createError.value = ''

  try {
    // Proxmox replication job id format: {vmid}-{target}-{increment}
    // POST /replication with: id, type=local, target, guest(vmid)
    const vm = clusterVms.value.find(v => String(v.vmid) === String(newJob.value.source_vmid))
    const jobData = {
      id: `${newJob.value.source_vmid}-${newJob.value.target}-0`,
      type: 'local',
      target: newJob.value.target,
      guest: parseInt(newJob.value.source_vmid),
    }
    if (newJob.value.schedule) jobData.schedule = newJob.value.schedule
    if (newJob.value.rate > 0) jobData.rate = newJob.value.rate
    if (newJob.value.compress) jobData.compress = 1
    if (newJob.value.comment) jobData.comment = newJob.value.comment

    await api.cluster.createReplication(selectedHostId.value, jobData)
    toast.success('Replication job created successfully')
    closeModal()
    await loadReplication()
  } catch (err) {
    createError.value = err?.response?.data?.detail || err?.message || 'Failed to create job'
  } finally {
    creating.value = false
  }
}

function confirmDelete(job) {
  deleteTarget.value = job
}

async function deleteJob() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await api.cluster.deleteReplication(selectedHostId.value, deleteTarget.value.id)
    toast.success(`Replication job ${deleteTarget.value.id} deleted`)
    deleteTarget.value = null
    await loadReplication()
  } catch (err) {
    toast.error('Failed to delete: ' + (err?.response?.data?.detail || err?.message))
  } finally {
    deleting.value = false
  }
}

async function forceSync(job) {
  forceSyncLoading.value = { ...forceSyncLoading.value, [job.id]: true }
  try {
    const res = await api.cluster.forceReplication(selectedHostId.value, job.id)
    const upid = res.data?.upid
    if (upid) {
      toast.success(`Sync task queued for job ${job.id}`)
      activeSyncUpid.value = upid
      activeSyncNode.value = job.source || clusterNodes.value[0]?.name
      startSyncPoll(upid, job.source || clusterNodes.value[0]?.name)
    } else {
      toast.success(`Sync triggered for job ${job.id}`)
    }
    await refreshSyncTasks()
  } catch (err) {
    toast.error('Force sync failed: ' + (err?.response?.data?.detail || err?.message))
  } finally {
    forceSyncLoading.value = { ...forceSyncLoading.value, [job.id]: false }
  }
}

function startSyncPoll(upid, node) {
  syncTaskLog.value = []
  syncTaskRunning.value = true
  syncTaskStatus.value = ''
  if (syncPollTimer) clearInterval(syncPollTimer)

  const fetchLog = async () => {
    if (!node || !upid) return
    try {
      const logRes = await api.pveNode.taskLog(selectedHostId.value, node, encodeURIComponent(upid))
      syncTaskLog.value = logRes.data?.lines || []
      const statusRes = await api.pveNode.taskStatus(selectedHostId.value, node, encodeURIComponent(upid))
      const s = statusRes.data?.status
      if (s && s !== 'running') {
        syncTaskStatus.value = s
        syncTaskRunning.value = false
        clearInterval(syncPollTimer)
        syncPollTimer = null
        await loadReplication()
      }
    } catch { /* ignore */ }
  }

  fetchLog()
  syncPollTimer = setInterval(fetchLog, 3000)
}

onMounted(async () => {
  await loadHosts()
  if (selectedHostId.value) {
    await Promise.all([loadReplication(), loadClusterData()])
    await refreshSyncTasks()
  }
})

onUnmounted(() => {
  if (syncPollTimer) clearInterval(syncPollTimer)
})
</script>

<style scoped>
.replication-page {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1rem;
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

.host-select {
  min-width: 180px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.card-body {
  padding: 1.25rem 1.5rem;
}

.table-container {
  overflow-x: auto;
}

.action-btns {
  display: flex;
  gap: 0.4rem;
}

.upid-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Badges */
.badge-secondary {
  background: #6b7280;
  color: white;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-info {
  background: #3b82f6;
  color: white;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

@keyframes badge-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.badge-pulse {
  animation: badge-pulse 1.5s ease-in-out infinite;
}

/* Modal */
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
  width: 540px;
  max-width: 95vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-box--sm {
  width: 380px;
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

/* Form */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.875rem;
}

.form-label {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-primary);
}

.form-hint {
  margin-top: 0.2rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.form-check {
  margin-right: 0.4rem;
}

/* Task log */
.task-log {
  background: #0f1419;
  color: #9ca3af;
  padding: 0.75rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.8rem;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
}

/* Buttons */
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

.text-success { color: #10b981; }
.text-danger { color: #ef4444; }
.text-muted { color: var(--text-muted, #888); }
.text-center { text-align: center; }
.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.mb-1 { margin-bottom: 0.25rem; }
.mb-2 { margin-bottom: 1rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.75rem; }
.p-3 { padding: 1.5rem; }
</style>
