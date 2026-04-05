<template>
  <div class="backup-manager-page">
    <div class="page-header mb-2">
      <h2>Backup Manager</h2>
      <p class="text-muted">Manage backup schedules and run manual backups for host {{ hostId }}</p>
    </div>

    <!-- Tabs -->
    <div class="tab-bar mb-2">
      <button
        :class="['tab-btn', activeTab === 'schedules' ? 'tab-btn--active' : '']"
        @click="activeTab = 'schedules'"
      >Schedules</button>
      <button
        :class="['tab-btn', activeTab === 'run' ? 'tab-btn--active' : '']"
        @click="activeTab = 'run'"
      >Run Backup</button>
      <button
        :class="['tab-btn', activeTab === 'restore' ? 'tab-btn--active' : '']"
        @click="activeTab = 'restore'; onRestoreTabOpen()"
      >Restore</button>
    </div>

    <!-- Schedules tab -->
    <div v-if="activeTab === 'schedules'">
      <div class="card">
        <div class="card-header">
          <h3>Backup Schedules</h3>
          <button @click="openCreateModal" class="btn btn-primary">+ New Schedule</button>
        </div>

        <div v-if="loadingSchedules" class="loading-spinner"></div>

        <div v-else-if="schedules.length === 0" class="text-center text-muted p-3">
          No backup schedules configured.
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Comment</th>
                <th>Schedule</th>
                <th>Node</th>
                <th>Storage</th>
                <th>VMs</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="sched in schedules" :key="sched.id">
                <td><strong>{{ sched.id }}</strong></td>
                <td>{{ sched.comment || '—' }}</td>
                <td><code class="cron-text">{{ sched.schedule || sched.dow || '—' }}</code></td>
                <td>{{ sched.node || 'all' }}</td>
                <td>{{ sched.storage || '—' }}</td>
                <td class="text-sm">{{ sched.vmid || 'all' }}</td>
                <td>
                  <div class="flex gap-1">
                    <button @click="openEditModal(sched)" class="btn btn-outline btn-sm">Edit</button>
                    <button @click="deleteSchedule(sched.id)" class="btn btn-danger btn-sm">Delete</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Run Backup tab -->
    <div v-if="activeTab === 'run'">
      <div class="card">
        <div class="card-header">
          <h3>Run Manual Backup</h3>
        </div>
        <div class="card-body">
          <div v-if="runResult" class="run-result">
            <p class="text-sm"><strong>Backup started. Task UPID:</strong></p>
            <code class="upid-code">{{ runResult }}</code>
            <button @click="runResult = null" class="btn btn-outline btn-sm mt-1">Dismiss</button>
          </div>

          <form @submit.prevent="runBackup">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Node <span class="required">*</span></label>
                <select v-model="runForm.node" class="form-control" required>
                  <option value="">Select node...</option>
                  <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">
                    {{ n.node || n.name }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Storage <span class="required">*</span></label>
                <input v-model="runForm.storage" class="form-control" placeholder="e.g. local" required />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">VM IDs</label>
              <input
                v-model="runForm.vmid"
                class="form-control"
                placeholder='Comma-separated IDs or "all" (e.g. 100,101,102)'
              />
              <div class="text-xs text-muted mt-1">Leave blank or enter "all" to back up all VMs.</div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Compression</label>
                <select v-model="runForm.compress" class="form-control">
                  <option value="zstd">zstd (recommended)</option>
                  <option value="lzo">lzo</option>
                  <option value="gzip">gzip</option>
                  <option value="0">none</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Mode</label>
                <select v-model="runForm.mode" class="form-control">
                  <option value="snapshot">snapshot</option>
                  <option value="suspend">suspend</option>
                  <option value="stop">stop</option>
                </select>
              </div>
            </div>

            <div class="flex gap-1 mt-2">
              <button type="submit" class="btn btn-primary" :disabled="running">
                {{ running ? 'Starting...' : 'Run Now' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Restore tab -->
    <div v-if="activeTab === 'restore'">
      <div class="card mb-2">
        <div class="card-header">
          <h3>Browse Backups</h3>
          <div class="flex gap-1">
            <select v-model="restoreFilter.node" class="form-control form-control-sm" @change="onRestoreNodeChange">
              <option value="">Select node...</option>
              <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">
                {{ n.node || n.name }}
              </option>
            </select>
            <select v-model="restoreFilter.storage" class="form-control form-control-sm" :disabled="!restoreFilter.node || loadingRestoreStorages" @change="fetchBackupFiles">
              <option value="">Select storage...</option>
              <option v-for="s in restoreStorages" :key="s.storage" :value="s.storage">
                {{ s.storage }}
              </option>
            </select>
            <button @click="fetchBackupFiles" class="btn btn-outline btn-sm" :disabled="!restoreFilter.node || !restoreFilter.storage || loadingBackupFiles">
              Refresh
            </button>
          </div>
        </div>

        <div v-if="loadingBackupFiles" class="loading-spinner"></div>

        <div v-else-if="!restoreFilter.node || !restoreFilter.storage" class="text-center text-muted p-3">
          Select a node and storage to browse backup files.
        </div>

        <div v-else-if="backupGroups.length === 0" class="text-center text-muted p-3">
          No backup files found in this storage.
        </div>

        <div v-else>
          <div v-for="group in backupGroups" :key="group.vmid" class="backup-group">
            <div class="backup-group-header">
              <span class="vmid-badge">VMID {{ group.vmid }}</span>
              <span class="text-muted text-sm ml-1">{{ group.backups.length }} backup{{ group.backups.length !== 1 ? 's' : '' }}</span>
            </div>
            <table class="table table-sm">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Format</th>
                  <th>Size</th>
                  <th>Volume ID</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="bk in group.backups" :key="bk.volid">
                  <td>{{ formatDate(bk.ctime) }}</td>
                  <td><code class="text-xs">{{ bk.format || '—' }}</code></td>
                  <td>{{ formatSize(bk.size) }}</td>
                  <td class="text-xs volid-cell">{{ bk.volid }}</td>
                  <td>
                    <button @click="openRestoreModal(bk, group.vmid)" class="btn btn-primary btn-sm">
                      Restore
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Create / Edit Schedule Modal -->
    <div v-if="scheduleModal.show" class="modal" @click="closeScheduleModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ scheduleModal.editing ? 'Edit Schedule' : 'Create Backup Schedule' }}</h3>
          <button @click="closeScheduleModal" class="btn-close">&#215;</button>
        </div>
        <form @submit.prevent="saveSchedule" class="modal-body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Node</label>
              <select v-model="scheduleForm.node" class="form-control">
                <option value="">All nodes</option>
                <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">
                  {{ n.node || n.name }}
                </option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Storage <span class="required">*</span></label>
              <input v-model="scheduleForm.storage" class="form-control" placeholder="e.g. local" required />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Schedule (cron) <span class="required">*</span></label>
            <input
              v-model="scheduleForm.schedule"
              class="form-control"
              placeholder="e.g. 0 2 * * *"
              required
            />
            <div class="text-xs text-muted mt-1">Standard cron format: minute hour day month weekday</div>
          </div>

          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="scheduleForm.comment" class="form-control" placeholder="Optional description" />
          </div>

          <div class="form-group">
            <label class="form-label">VM IDs</label>
            <input
              v-model="scheduleForm.vmid"
              class="form-control"
              placeholder='Comma-separated IDs or "all"'
            />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Compression</label>
              <select v-model="scheduleForm.compress" class="form-control">
                <option value="zstd">zstd</option>
                <option value="lzo">lzo</option>
                <option value="gzip">gzip</option>
                <option value="0">none</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Mode</label>
              <select v-model="scheduleForm.mode" class="form-control">
                <option value="snapshot">snapshot</option>
                <option value="suspend">suspend</option>
                <option value="stop">stop</option>
              </select>
            </div>
          </div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingSchedule">
              {{ savingSchedule ? 'Saving...' : (scheduleModal.editing ? 'Save Changes' : 'Create Schedule') }}
            </button>
            <button type="button" @click="closeScheduleModal" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Restore Modal -->
    <div v-if="restoreModal.show" class="modal" @click="closeRestoreModal">
      <div class="modal-content modal-content--wide" @click.stop>
        <div class="modal-header">
          <h3>Restore Backup</h3>
          <button @click="closeRestoreModal" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <!-- Source info -->
          <div class="restore-source-info mb-2">
            <div class="text-sm text-muted">Restoring from:</div>
            <code class="upid-code">{{ restoreModal.volid }}</code>
          </div>

          <!-- Task progress (shown after restore starts) -->
          <div v-if="restoreTask.upid" class="restore-progress mb-2">
            <div class="restore-progress-header">
              <strong>Restore Task</strong>
              <span :class="['task-status-badge', `task-status-badge--${restoreTask.status}`]">
                {{ restoreTask.status }}
              </span>
            </div>
            <code class="upid-code">{{ restoreTask.upid }}</code>
            <div v-if="restoreTask.status === 'running'" class="progress-bar-wrap mt-1">
              <div class="progress-bar progress-bar--animated"></div>
            </div>
            <div v-if="restoreTask.exitstatus && restoreTask.exitstatus !== 'OK'" class="text-sm text-danger mt-1">
              Exit status: {{ restoreTask.exitstatus }}
            </div>
            <div v-if="restoreTask.status === 'stopped' && restoreTask.exitstatus === 'OK'" class="text-sm text-success mt-1">
              Restore completed successfully.
            </div>
          </div>

          <!-- Restore form (hidden once task is running/done) -->
          <form v-if="!restoreTask.upid" @submit.prevent="submitRestore">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Target VM ID <span class="required">*</span></label>
                <input
                  v-model.number="restoreForm.vmid"
                  type="number"
                  class="form-control"
                  min="100"
                  max="999999999"
                  required
                />
                <div class="text-xs text-muted mt-1">The VM ID that will be created/overwritten.</div>
              </div>
              <div class="form-group">
                <label class="form-label">Target Node <span class="required">*</span></label>
                <select v-model="restoreForm.node" class="form-control" required @change="onRestoreFormNodeChange">
                  <option value="">Select node...</option>
                  <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">
                    {{ n.node || n.name }}
                  </option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Target Storage <span class="required">*</span></label>
                <select v-model="restoreForm.storage" class="form-control" required :disabled="loadingRestoreTargetStorages || !restoreForm.node">
                  <option value="">{{ loadingRestoreTargetStorages ? 'Loading...' : 'Select storage...' }}</option>
                  <option v-for="s in restoreTargetStorages" :key="s.storage" :value="s.storage">
                    {{ s.storage }}{{ s.type ? ` (${s.type})` : '' }}
                  </option>
                </select>
              </div>
              <div class="form-group form-group--center">
                <label class="form-label">&nbsp;</label>
                <label class="checkbox-label">
                  <input type="checkbox" v-model="restoreForm.start" />
                  <span>Start VM after restore</span>
                </label>
              </div>
            </div>

            <div class="flex gap-1 mt-2">
              <button type="submit" class="btn btn-primary" :disabled="restoringBackup">
                {{ restoringBackup ? 'Starting restore...' : 'Restore' }}
              </button>
              <button type="button" @click="closeRestoreModal" class="btn btn-outline">Cancel</button>
            </div>
          </form>

          <!-- Actions after task started -->
          <div v-if="restoreTask.upid" class="flex gap-1 mt-2">
            <button @click="closeRestoreModal" class="btn btn-outline">Close</button>
          </div>
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

const hostId = ref(route.params.hostId)

const activeTab = ref('schedules')

// Schedules
const schedules = ref([])
const loadingSchedules = ref(false)
const savingSchedule = ref(false)

const scheduleModal = ref({ show: false, editing: false, editId: null })
const emptyScheduleForm = () => ({
  node: '',
  storage: '',
  schedule: '0 2 * * *',
  comment: '',
  vmid: 'all',
  compress: 'zstd',
  mode: 'snapshot',
})
const scheduleForm = ref(emptyScheduleForm())

// Run backup
const clusterNodes = ref([])
const running = ref(false)
const runResult = ref(null)
const runForm = ref({
  node: '',
  storage: '',
  vmid: 'all',
  compress: 'zstd',
  mode: 'snapshot',
})

// Restore tab state
const restoreFilter = ref({ node: '', storage: '' })
const restoreStorages = ref([])
const loadingRestoreStorages = ref(false)
const backupFiles = ref([])
const loadingBackupFiles = ref(false)

// Restore modal state
const restoreModal = ref({ show: false, volid: '' })
const restoreForm = ref({ vmid: null, node: '', storage: '', start: false })
const restoringBackup = ref(false)
const restoreTargetStorages = ref([])
const loadingRestoreTargetStorages = ref(false)

// Restore task polling
const restoreTask = ref({ upid: null, status: null, exitstatus: null })
let restoreTaskPollTimer = null

// Computed: group backup files by VMID
const backupGroups = computed(() => {
  const groups = {}
  for (const bk of backupFiles.value) {
    // Parse vmid from volid: e.g. local:backup/vzdump-qemu-100-2024_01_15-03_00_01.vma.zst
    const vmid = parseVmidFromVolid(bk.volid) || bk.vmid || 'unknown'
    if (!groups[vmid]) groups[vmid] = { vmid, backups: [] }
    groups[vmid].backups.push(bk)
  }
  // Sort each group's backups by date descending
  return Object.values(groups)
    .sort((a, b) => String(a.vmid).localeCompare(String(b.vmid), undefined, { numeric: true }))
    .map(g => ({
      ...g,
      backups: [...g.backups].sort((a, b) => (b.ctime || 0) - (a.ctime || 0))
    }))
})

function parseVmidFromVolid(volid) {
  if (!volid) return null
  // vzdump-qemu-100-... or vzdump-lxc-100-...
  const m = volid.match(/vzdump-(?:qemu|lxc)-(\d+)-/)
  return m ? m[1] : null
}

function formatDate(ctime) {
  if (!ctime) return '—'
  return new Date(ctime * 1000).toLocaleString()
}

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = bytes
  let u = 0
  while (v >= 1024 && u < units.length - 1) { v /= 1024; u++ }
  return `${v.toFixed(1)} ${units[u]}`
}

// ── Schedules ────────────────────────────────────────────────────────────────

async function fetchSchedules() {
  loadingSchedules.value = true
  try {
    const res = await api.pveNode.listBackupSchedules(hostId.value)
    schedules.value = res.data || []
  } catch (err) {
    console.error('Failed to load backup schedules:', err)
    toast.error('Failed to load backup schedules')
  } finally {
    loadingSchedules.value = false
  }
}

async function fetchClusterNodes() {
  try {
    const res = await api.pveNode.clusterResources(hostId.value)
    const resources = res.data || []
    clusterNodes.value = resources.filter(r => r.type === 'node')
  } catch (err) {
    console.warn('Failed to load cluster nodes:', err)
  }
}

function openCreateModal() {
  scheduleForm.value = emptyScheduleForm()
  scheduleModal.value = { show: true, editing: false, editId: null }
}

function openEditModal(sched) {
  scheduleForm.value = {
    node: sched.node || '',
    storage: sched.storage || '',
    schedule: sched.schedule || sched.dow || '',
    comment: sched.comment || '',
    vmid: sched.vmid || 'all',
    compress: sched.compress || 'zstd',
    mode: sched.mode || 'snapshot',
  }
  scheduleModal.value = { show: true, editing: true, editId: sched.id }
}

function closeScheduleModal() {
  scheduleModal.value = { show: false, editing: false, editId: null }
}

async function saveSchedule() {
  savingSchedule.value = true
  const payload = { ...scheduleForm.value }
  Object.keys(payload).forEach(k => { if (payload[k] === '') delete payload[k] })

  try {
    if (scheduleModal.value.editing) {
      await api.pveNode.updateBackupSchedule(hostId.value, scheduleModal.value.editId, payload)
      toast.success('Schedule updated')
    } else {
      await api.pveNode.createBackupSchedule(hostId.value, payload)
      toast.success('Schedule created')
    }
    closeScheduleModal()
    await fetchSchedules()
  } catch (err) {
    console.error('Failed to save schedule:', err)
    toast.error('Failed to save schedule')
  } finally {
    savingSchedule.value = false
  }
}

async function deleteSchedule(id) {
  if (!confirm(`Delete backup schedule "${id}"? This cannot be undone.`)) return
  try {
    await api.pveNode.deleteBackupSchedule(hostId.value, id)
    toast.success('Schedule deleted')
    await fetchSchedules()
  } catch (err) {
    console.error('Failed to delete schedule:', err)
    toast.error('Failed to delete schedule')
  }
}

// ── Run Backup ───────────────────────────────────────────────────────────────

async function runBackup() {
  if (!runForm.value.node) {
    toast.error('Please select a node')
    return
  }
  running.value = true
  runResult.value = null
  try {
    const payload = { ...runForm.value }
    Object.keys(payload).forEach(k => { if (payload[k] === '' || payload[k] === null) delete payload[k] })
    const res = await api.pveNode.runBackup(hostId.value, runForm.value.node, payload)
    runResult.value = res.data?.upid || res.data || 'started'
    toast.success('Backup started')
  } catch (err) {
    console.error('Failed to start backup:', err)
    toast.error('Failed to start backup')
  } finally {
    running.value = false
  }
}

// ── Restore tab ──────────────────────────────────────────────────────────────

function onRestoreTabOpen() {
  // Pre-populate node list if not done yet; storages load on node selection
  if (restoreFilter.value.node && restoreStorages.value.length === 0) {
    fetchRestoreStorages(restoreFilter.value.node)
  }
}

async function onRestoreNodeChange() {
  restoreFilter.value.storage = ''
  restoreStorages.value = []
  backupFiles.value = []
  if (restoreFilter.value.node) {
    await fetchRestoreStorages(restoreFilter.value.node)
  }
}

async function fetchRestoreStorages(node) {
  loadingRestoreStorages.value = true
  try {
    const res = await api.pveNode.listStorage(hostId.value, node)
    restoreStorages.value = res.data || []
  } catch (err) {
    console.warn('Failed to load storages:', err)
  } finally {
    loadingRestoreStorages.value = false
  }
}

async function fetchBackupFiles() {
  if (!restoreFilter.value.node || !restoreFilter.value.storage) return
  loadingBackupFiles.value = true
  backupFiles.value = []
  try {
    const res = await api.pveNode.browseStorage(
      hostId.value,
      restoreFilter.value.node,
      restoreFilter.value.storage,
      { content: 'backup' }
    )
    backupFiles.value = res.data || []
  } catch (err) {
    console.error('Failed to browse backup storage:', err)
    toast.error('Failed to load backup files')
  } finally {
    loadingBackupFiles.value = false
  }
}

// ── Restore modal ─────────────────────────────────────────────────────────────

function openRestoreModal(backup, vmid) {
  restoreTask.value = { upid: null, status: null, exitstatus: null }
  restoreForm.value = {
    vmid: Number(vmid) || null,
    node: restoreFilter.value.node,
    storage: '',
    start: false,
  }
  restoreModal.value = { show: true, volid: backup.volid }
  // Load storages for the pre-selected node
  if (restoreForm.value.node) {
    fetchRestoreTargetStorages(restoreForm.value.node)
  }
}

function closeRestoreModal() {
  stopTaskPolling()
  restoreModal.value = { show: false, volid: '' }
  restoreTask.value = { upid: null, status: null, exitstatus: null }
}

async function onRestoreFormNodeChange() {
  restoreForm.value.storage = ''
  restoreTargetStorages.value = []
  if (restoreForm.value.node) {
    await fetchRestoreTargetStorages(restoreForm.value.node)
  }
}

async function fetchRestoreTargetStorages(node) {
  loadingRestoreTargetStorages.value = true
  try {
    const res = await api.pveNode.listStorage(hostId.value, node)
    restoreTargetStorages.value = res.data || []
  } catch (err) {
    console.warn('Failed to load target storages:', err)
  } finally {
    loadingRestoreTargetStorages.value = false
  }
}

async function submitRestore() {
  if (!restoreForm.value.node) { toast.error('Please select a target node'); return }
  if (!restoreForm.value.storage) { toast.error('Please select a target storage'); return }
  if (!restoreForm.value.vmid) { toast.error('Please enter a target VM ID'); return }

  restoringBackup.value = true
  try {
    const payload = {
      archive: restoreModal.value.volid,
      storage: restoreForm.value.storage,
      start: restoreForm.value.start ? 1 : 0,
    }
    const res = await api.pveNode.restoreBackup(
      hostId.value,
      restoreForm.value.node,
      restoreForm.value.vmid,
      payload
    )
    const upid = res.data?.upid || res.data
    toast.success('Restore task started')
    restoreTask.value = { upid, status: 'running', exitstatus: null }
    startTaskPolling(restoreForm.value.node, upid)
  } catch (err) {
    console.error('Failed to start restore:', err)
    toast.error('Failed to start restore')
  } finally {
    restoringBackup.value = false
  }
}

// ── Task polling ─────────────────────────────────────────────────────────────

function startTaskPolling(node, upid) {
  stopTaskPolling()
  restoreTaskPollTimer = setInterval(() => pollTaskStatus(node, upid), 3000)
  // Poll once immediately
  pollTaskStatus(node, upid)
}

function stopTaskPolling() {
  if (restoreTaskPollTimer) {
    clearInterval(restoreTaskPollTimer)
    restoreTaskPollTimer = null
  }
}

async function pollTaskStatus(node, upid) {
  try {
    const res = await api.pveNode.taskStatus(hostId.value, node, encodeURIComponent(upid))
    const data = res.data || {}
    restoreTask.value.status = data.status || 'unknown'
    restoreTask.value.exitstatus = data.exitstatus || null
    if (data.status === 'stopped') {
      stopTaskPolling()
      if (data.exitstatus === 'OK') {
        toast.success('Restore completed successfully')
      } else {
        toast.error(`Restore finished with status: ${data.exitstatus}`)
      }
    }
  } catch (err) {
    console.warn('Failed to poll task status:', err)
  }
}

onMounted(async () => {
  await Promise.all([fetchSchedules(), fetchClusterNodes()])
})

onUnmounted(() => {
  stopTaskPolling()
})
</script>

<style scoped>
.backup-manager-page {
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

.tab-bar {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 1.5rem;
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.6rem 1.25rem;
  cursor: pointer;
  color: var(--text-muted, #888);
  font-size: 0.9rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn--active {
  color: var(--primary-color, #6366f1);
  border-bottom-color: var(--primary-color, #6366f1);
  font-weight: 600;
}

.card-body {
  padding: 1.5rem;
}

.cron-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.required {
  color: #ef4444;
}

.run-result {
  padding: 1rem;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid #10b981;
  border-radius: 0.375rem;
  margin-bottom: 1.5rem;
}

.upid-code {
  display: block;
  padding: 0.5rem 0.75rem;
  background: var(--bg-secondary);
  border-radius: 0.375rem;
  font-size: 0.8rem;
  word-break: break-all;
  margin-top: 0.25rem;
  color: var(--text-primary);
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.form-control-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
  height: auto;
}

/* Restore tab */
.backup-group {
  border-top: 1px solid var(--border-color);
}

.backup-group:first-child {
  border-top: none;
}

.backup-group-header {
  padding: 0.6rem 1rem;
  background: var(--bg-secondary, rgba(255,255,255,0.03));
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.vmid-badge {
  background: var(--primary-color, #6366f1);
  color: #fff;
  border-radius: 0.25rem;
  padding: 0.1rem 0.45rem;
  font-size: 0.8rem;
  font-weight: 600;
}

.table-sm td,
.table-sm th {
  padding: 0.4rem 0.75rem;
  font-size: 0.875rem;
}

.volid-cell {
  color: var(--text-muted);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Restore modal */
.modal-content--wide {
  max-width: 720px;
}

.restore-source-info {
  padding: 0.75rem 1rem;
  background: var(--bg-secondary);
  border-radius: 0.375rem;
}

.restore-progress {
  padding: 1rem;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid var(--primary-color, #6366f1);
  border-radius: 0.375rem;
}

.restore-progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.task-status-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
}

.task-status-badge--running {
  background: rgba(180, 83, 9, 0.1);
  color: #b45309;
  border: 1px solid #d97706;
}

.task-status-badge--stopped {
  background: rgba(5, 150, 105, 0.12);
  color: #059669;
  border: 1px solid #059669;
}

.task-status-badge--unknown {
  background: rgba(107, 114, 128, 0.12);
  color: #4b5563;
  border: 1px solid #9ca3af;
}

.progress-bar-wrap {
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--primary-color, #6366f1);
}

.progress-bar--animated {
  width: 40%;
  animation: progress-slide 1.4s ease-in-out infinite;
}

@keyframes progress-slide {
  0%   { transform: translateX(-150%); }
  100% { transform: translateX(400%); }
}

.text-danger { color: #ef4444; }
.text-success { color: #059669; }

.form-group--center {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-primary);
  padding-bottom: 0.5rem;
}

.checkbox-label input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
  cursor: pointer;
}

.ml-1 { margin-left: 0.25rem; }
.mb-2 { margin-bottom: 1rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.75rem; }
.p-3 { padding: 1.5rem; }
.text-xs { font-size: 0.75rem; }
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
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.75rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body {
  padding: 1.5rem;
  color: var(--text-primary);
}

@media (max-width: 640px) {
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
