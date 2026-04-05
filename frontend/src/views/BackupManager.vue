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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
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
  // Clean up empty fields
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

onMounted(async () => {
  await Promise.all([fetchSchedules(), fetchClusterNodes()])
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
