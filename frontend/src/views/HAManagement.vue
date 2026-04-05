<template>
  <div class="ha-management">
    <div class="page-header">
      <div>
        <h1>High Availability Management</h1>
        <p class="text-muted">Manage Proxmox HA resources and monitor cluster failover status</p>
      </div>
      <div class="header-actions">
        <button @click="reloadAll" class="btn btn-secondary" :disabled="loadingResources || loadingGroups || loadingStatus">
          Refresh
        </button>
      </div>
    </div>

    <!-- Host Selector -->
    <div class="card host-selector-card">
      <div class="host-selector-row">
        <label class="form-label">Proxmox Host</label>
        <select
          v-model="selectedHostId"
          class="form-control host-select"
          :disabled="loadingHosts"
          @change="onHostChange"
        >
          <option value="" disabled>{{ loadingHosts ? 'Loading hosts...' : 'Select a host...' }}</option>
          <option
            v-for="host in hosts"
            :key="host.id"
            :value="host.id"
          >
            {{ host.name }} — {{ host.address }}
          </option>
        </select>

        <!-- HA Status Badge -->
        <div v-if="selectedHostId && haManagerStatus" class="status-badge-wrap">
          <span class="status-label">HA Manager:</span>
          <span :class="['badge', haStatusBadgeClass]">{{ haManagerStatus }}</span>
        </div>
        <div v-else-if="selectedHostId && loadingStatus" class="status-badge-wrap">
          <span class="text-muted text-sm">Loading status...</span>
        </div>
        <div v-else-if="selectedHostId && statusError" class="status-badge-wrap">
          <span class="badge badge-danger">Status unavailable</span>
        </div>
      </div>
    </div>

    <!-- No host selected placeholder -->
    <div v-if="!selectedHostId" class="card empty-placeholder">
      <p class="text-muted">Select a Proxmox host above to view HA configuration.</p>
    </div>

    <template v-else>
      <!-- HA Resources Table -->
      <div class="card">
        <div class="card-header">
          <h2>HA Resources</h2>
          <button @click="showAddModal = true" class="btn btn-primary">+ Add Resource</button>
        </div>

        <div v-if="loadingResources" class="loading-state">Loading HA resources...</div>

        <div v-else-if="resourceError" class="error-banner">{{ resourceError }}</div>

        <div v-else-if="haResources.length === 0" class="empty-state">
          <p>No HA resources configured on this host.</p>
          <p class="text-sm text-muted">Add VMs to HA protection to enable automatic failover.</p>
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>SID (Resource ID)</th>
                <th>Type</th>
                <th>Group</th>
                <th>State</th>
                <th>Max Restart</th>
                <th>Max Relocate</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="resource in haResources" :key="resource.sid">
                <td><strong>{{ resource.sid }}</strong></td>
                <td>{{ resource.type || 'vm' }}</td>
                <td>{{ resource.group || '—' }}</td>
                <td>
                  <span :class="['badge', resourceStateBadge(resource.state)]">
                    {{ resource.state || 'unknown' }}
                  </span>
                </td>
                <td>{{ resource.max_restart ?? '—' }}</td>
                <td>{{ resource.max_relocate ?? '—' }}</td>
                <td>
                  <button
                    @click="confirmDelete(resource.sid)"
                    class="btn btn-danger btn-sm"
                    :disabled="deletingSid === resource.sid"
                  >
                    {{ deletingSid === resource.sid ? 'Removing...' : 'Remove' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- HA Groups Table -->
      <div class="card">
        <div class="card-header">
          <h2>HA Groups</h2>
        </div>

        <div v-if="loadingGroups" class="loading-state">Loading HA groups...</div>

        <div v-else-if="groupError" class="error-banner">{{ groupError }}</div>

        <div v-else-if="haGroups.length === 0" class="empty-state">
          <p>No HA groups defined on this host.</p>
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Group Name</th>
                <th>Nodes</th>
                <th>No Failback</th>
                <th>Restricted</th>
                <th>Comment</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="group in haGroups" :key="group.group">
                <td><strong>{{ group.group }}</strong></td>
                <td>{{ group.nodes || '—' }}</td>
                <td>
                  <span :class="['badge', group.nofailback ? 'badge-warning' : 'badge-secondary']">
                    {{ group.nofailback ? 'Yes' : 'No' }}
                  </span>
                </td>
                <td>
                  <span :class="['badge', group.restricted ? 'badge-warning' : 'badge-secondary']">
                    {{ group.restricted ? 'Yes' : 'No' }}
                  </span>
                </td>
                <td class="text-sm">{{ group.comment || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- Add Resource Modal -->
    <div v-if="showAddModal" class="modal" @click.self="showAddModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Add HA Resource</h3>
          <button @click="showAddModal = false" class="btn-close">&times;</button>
        </div>
        <form @submit.prevent="addResource" class="modal-body">
          <div class="form-group">
            <label class="form-label">Resource SID <span class="required">*</span></label>
            <input
              v-model="newResource.sid"
              class="form-control"
              placeholder="e.g. vm:100 or ct:200"
              required
            />
            <p class="field-hint">Format: <code>vm:&lt;vmid&gt;</code> or <code>ct:&lt;vmid&gt;</code></p>
          </div>

          <div class="form-group">
            <label class="form-label">HA Group</label>
            <select v-model="newResource.group" class="form-control">
              <option value="">— None —</option>
              <option v-for="g in haGroups" :key="g.group" :value="g.group">
                {{ g.group }}
              </option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Max Restart</label>
              <select v-model.number="newResource.max_restart" class="form-control">
                <option :value="0">0</option>
                <option :value="1">1</option>
                <option :value="2">2</option>
                <option :value="3">3</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Max Relocate</label>
              <select v-model.number="newResource.max_relocate" class="form-control">
                <option :value="0">0</option>
                <option :value="1">1</option>
                <option :value="2">2</option>
                <option :value="3">3</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="newResource.comment" class="form-control" placeholder="Optional description" />
          </div>

          <div class="modal-actions">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? 'Adding...' : 'Add Resource' }}
            </button>
            <button type="button" @click="showAddModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const toast = useToast()

// ── Hosts ─────────────────────────────────────────────────────────────────────
const hosts = ref([])
const loadingHosts = ref(false)
const selectedHostId = ref('')

const loadHosts = async () => {
  loadingHosts.value = true
  try {
    const response = await api.proxmox.listHosts({ params: { page_size: 100 } })
    hosts.value = response.data?.items ?? response.data ?? []
    // Auto-select first host if only one
    if (hosts.value.length === 1 && !selectedHostId.value) {
      selectedHostId.value = hosts.value[0].id
      reloadAll()
    }
  } catch (err) {
    console.error('Failed to load Proxmox hosts:', err)
    toast.error('Failed to load Proxmox hosts')
  } finally {
    loadingHosts.value = false
  }
}

const onHostChange = () => {
  reloadAll()
}

// ── HA Status ─────────────────────────────────────────────────────────────────
const haManagerStatus = ref('')
const loadingStatus = ref(false)
const statusError = ref(null)

const haStatusBadgeClass = computed(() => {
  const s = (haManagerStatus.value || '').toLowerCase()
  if (s === 'active') return 'badge-success'
  if (s === 'passive') return 'badge-info'
  if (s === 'disabled') return 'badge-secondary'
  return 'badge-warning'
})

const loadHaStatus = async () => {
  if (!selectedHostId.value) return
  loadingStatus.value = true
  statusError.value = null
  haManagerStatus.value = ''
  try {
    const response = await api.pveNode.haStatus(selectedHostId.value)
    // PVE returns an array of status objects; find the manager entry
    const data = response.data
    if (Array.isArray(data)) {
      const managerEntry = data.find(d => d.type === 'manager' || d.id === 'manager' || 'status' in d)
      haManagerStatus.value = managerEntry?.status ?? managerEntry?.state ?? data[0]?.status ?? 'unknown'
    } else if (data && typeof data === 'object') {
      haManagerStatus.value = data.status ?? data.manager_status ?? data.state ?? 'unknown'
    }
  } catch (err) {
    statusError.value = err.response?.data?.detail || 'Failed to load HA status'
    console.error('Failed to load HA status:', err)
  } finally {
    loadingStatus.value = false
  }
}

// ── HA Resources ──────────────────────────────────────────────────────────────
const haResources = ref([])
const loadingResources = ref(false)
const resourceError = ref(null)
const deletingSid = ref(null)

const loadHaResources = async () => {
  if (!selectedHostId.value) return
  loadingResources.value = true
  resourceError.value = null
  try {
    const response = await api.pveNode.listHaResources(selectedHostId.value)
    haResources.value = response.data ?? []
  } catch (err) {
    resourceError.value = err.response?.data?.detail || 'Failed to load HA resources'
    console.error('Failed to load HA resources:', err)
  } finally {
    loadingResources.value = false
  }
}

const resourceStateBadge = (state) => {
  const map = {
    started:  'badge-success',
    enabled:  'badge-success',
    running:  'badge-success',
    stopped:  'badge-danger',
    disabled: 'badge-secondary',
    error:    'badge-danger',
    fence:    'badge-danger',
    migrate:  'badge-info',
    relocate: 'badge-info',
  }
  return map[(state || '').toLowerCase()] || 'badge-secondary'
}

// ── HA Groups ─────────────────────────────────────────────────────────────────
const haGroups = ref([])
const loadingGroups = ref(false)
const groupError = ref(null)

const loadHaGroups = async () => {
  if (!selectedHostId.value) return
  loadingGroups.value = true
  groupError.value = null
  try {
    const response = await api.pveNode.listHaGroups(selectedHostId.value)
    haGroups.value = response.data ?? []
  } catch (err) {
    groupError.value = err.response?.data?.detail || 'Failed to load HA groups'
    console.error('Failed to load HA groups:', err)
  } finally {
    loadingGroups.value = false
  }
}

// ── Add Resource Modal ────────────────────────────────────────────────────────
const showAddModal = ref(false)
const saving = ref(false)
const newResource = ref({
  sid: '',
  group: '',
  max_restart: 1,
  max_relocate: 1,
  comment: ''
})

const resetNewResource = () => {
  newResource.value = { sid: '', group: '', max_restart: 1, max_relocate: 1, comment: '' }
}

const addResource = async () => {
  saving.value = true
  try {
    const payload = { ...newResource.value }
    // Strip empty optional fields
    Object.keys(payload).forEach(k => {
      if (payload[k] === '' || payload[k] === null || payload[k] === undefined) delete payload[k]
    })
    await api.pveNode.addHaResource(selectedHostId.value, payload)
    toast.success(`HA resource ${payload.sid} added`)
    showAddModal.value = false
    resetNewResource()
    await loadHaResources()
  } catch (err) {
    const msg = err.response?.data?.detail || 'Failed to add HA resource'
    toast.error(msg)
    console.error('Failed to add HA resource:', err)
  } finally {
    saving.value = false
  }
}

// ── Delete Resource ───────────────────────────────────────────────────────────
const confirmDelete = async (sid) => {
  if (!confirm(`Remove HA resource "${sid}" from protection?\n\nThe VM will no longer automatically failover.`)) return
  deletingSid.value = sid
  try {
    await api.pveNode.deleteHaResource(selectedHostId.value, sid)
    toast.success(`HA resource ${sid} removed`)
    await loadHaResources()
  } catch (err) {
    const msg = err.response?.data?.detail || 'Failed to remove HA resource'
    toast.error(msg)
    console.error('Failed to remove HA resource:', err)
  } finally {
    deletingSid.value = null
  }
}

// ── Reload All ────────────────────────────────────────────────────────────────
const reloadAll = () => {
  loadHaStatus()
  loadHaResources()
  loadHaGroups()
}

onMounted(() => {
  loadHosts()
})
</script>

<style scoped>
.ha-management {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* ── Page Header ── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0 0 0.375rem 0;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-shrink: 0;
}

/* ── Host Selector ── */
.host-selector-card {
  padding: 1rem 1.5rem !important;
}

.host-selector-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.host-selector-row .form-label {
  margin: 0;
  white-space: nowrap;
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.host-select {
  min-width: 280px;
  max-width: 420px;
}

.status-badge-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

/* ── Cards ── */
.card {
  background: var(--bg-card, #1e2130);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.5rem;
  padding: 1.5rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}

.card-header h2 {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

/* ── States ── */
.loading-state {
  text-align: center;
  padding: 2.5rem;
  color: var(--text-muted, #6b7280);
  font-size: 0.9rem;
}

.error-banner {
  padding: 0.875rem 1rem;
  background: rgba(220, 38, 38, 0.12);
  border: 1px solid rgba(220, 38, 38, 0.3);
  border-radius: 0.375rem;
  color: #f87171;
  font-size: 0.9rem;
}

.empty-state {
  text-align: center;
  padding: 2.5rem 1.5rem;
  color: var(--text-muted, #6b7280);
}

.empty-state p {
  margin: 0.375rem 0;
}

.empty-placeholder {
  text-align: center;
  padding: 3rem 1.5rem;
}

/* ── Table ── */
.table-container {
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table thead tr {
  border-bottom: 1px solid var(--border-color, #2d3348);
}

.table th {
  padding: 0.625rem 0.875rem;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #6b7280);
}

.table td {
  padding: 0.75rem 0.875rem;
  border-bottom: 1px solid var(--border-color, #2d3348);
  font-size: 0.9rem;
  color: var(--text-primary);
  vertical-align: middle;
}

.table tbody tr:last-child td {
  border-bottom: none;
}

.table tbody tr:hover {
  background: var(--bg-hover, rgba(255, 255, 255, 0.03));
}

/* ── Badges ── */
.badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-success  { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.badge-danger   { background: rgba(239, 68, 68, 0.15);  color: #f87171; }
.badge-warning  { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.badge-info     { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.badge-secondary { background: rgba(107, 114, 128, 0.2); color: #9ca3af; }

/* ── Buttons ── */
.btn {
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  border: none;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  transition: all 0.15s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #3b82f6;
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-secondary {
  background: var(--bg-secondary, #2d3348);
  color: var(--text-primary);
  border: 1px solid var(--border-color, #3d4568);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover, #363c55);
}

.btn-danger {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.25);
}

.btn-outline {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color, #3d4568);
}

.btn-outline:hover:not(:disabled) {
  background: var(--bg-hover, rgba(255, 255, 255, 0.05));
}

.btn-sm {
  padding: 0.25rem 0.625rem;
  font-size: 0.8rem;
}

/* ── Forms ── */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.required {
  color: #f87171;
}

.form-control {
  background: var(--bg-input, #151824);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
  color: var(--text-primary);
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.15s;
}

.form-control:focus {
  border-color: #3b82f6;
}

.form-control option {
  background: var(--bg-card, #1e2130);
}

.field-hint {
  font-size: 0.78rem;
  color: var(--text-muted, #6b7280);
  margin: 0;
}

.field-hint code {
  background: var(--bg-secondary, #2d3348);
  padding: 0.1rem 0.3rem;
  border-radius: 0.2rem;
  font-family: monospace;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

/* ── Modal ── */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card, #1e2130);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.5rem;
  width: 90%;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color, #2d3348);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  color: var(--text-muted, #6b7280);
  padding: 0 0.25rem;
  transition: color 0.15s;
}

.btn-close:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  padding-top: 0.5rem;
}

/* ── Utilities ── */
.text-muted {
  color: var(--text-muted, #6b7280);
}

.text-sm {
  font-size: 0.875rem;
}

@media (max-width: 640px) {
  .ha-management {
    padding: 1rem;
  }

  .host-selector-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .host-select {
    min-width: 100%;
    max-width: 100%;
  }

  .page-header {
    flex-direction: column;
    gap: 1rem;
  }

  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
