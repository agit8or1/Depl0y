<template>
  <div class="templates-page">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">VM Templates</h2>
        <p class="page-subtitle">Clone and manage templates across all Proxmox hosts</p>
      </div>
      <div class="header-right">
        <input
          v-model="search"
          class="form-control search-input"
          placeholder="Search by name or VMID..."
        />
        <select v-model="selectedHostId" class="form-control host-select">
          <option value="">All Hosts</option>
          <option v-for="host in hosts" :key="host.id" :value="host.id">
            {{ host.name || host.host }}
          </option>
        </select>
        <button @click="loadTemplates" class="btn btn-outline" :disabled="loading">
          {{ loading ? 'Loading...' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div class="card">
      <div class="card-body p-0">
        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <span>Loading templates...</span>
        </div>
        <div v-else-if="filteredTemplates.length === 0" class="empty-state">
          <span class="empty-icon">📋</span>
          <p>No templates found{{ search ? ' matching your search' : '' }}.</p>
        </div>
        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>VMID</th>
                <th>Name</th>
                <th>Node</th>
                <th>Host</th>
                <th>Memory</th>
                <th>CPUs</th>
                <th>Disk</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tpl in filteredTemplates" :key="`${tpl.hostId}-${tpl.vmid}`">
                <td class="vmid-cell">{{ tpl.vmid }}</td>
                <td class="name-cell">{{ tpl.name || `VM ${tpl.vmid}` }}</td>
                <td class="mono">{{ tpl.node }}</td>
                <td class="mono">{{ tpl.hostName }}</td>
                <td>{{ tpl.maxmem ? formatMB(tpl.maxmem) + ' MB' : '—' }}</td>
                <td>{{ tpl.maxcpu ?? '—' }}</td>
                <td>{{ tpl.maxdisk ? formatGB(tpl.maxdisk) : '—' }}</td>
                <td><span class="badge badge-template">Template</span></td>
                <td class="actions-cell">
                  <button
                    class="btn btn-primary btn-sm"
                    @click="openCloneModal(tpl)"
                  >Clone</button>
                  <router-link
                    :to="`/proxmox/${tpl.hostId}/nodes/${tpl.node}/vms/${tpl.vmid}`"
                    class="btn btn-outline btn-sm"
                  >Details</router-link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Clone Modal -->
    <div v-if="showCloneModal" class="modal" @click.self="closeCloneModal">
      <div class="modal-content modal-sm" @click.stop>
        <div class="modal-header">
          <h3>Clone Template</h3>
          <button @click="closeCloneModal" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p class="text-sm text-muted mb-3">
            Cloning <strong>{{ cloneTarget?.name || `VM ${cloneTarget?.vmid}` }}</strong>
            (VMID {{ cloneTarget?.vmid }}) from node <strong>{{ cloneTarget?.node }}</strong>
          </p>

          <div class="form-group">
            <label class="form-label">New VM ID <span class="text-danger">*</span></label>
            <input
              v-model.number="cloneForm.newid"
              type="number"
              class="form-control"
              placeholder="e.g. 200"
            />
          </div>

          <div class="form-group">
            <label class="form-label">New Name <span class="text-danger">*</span></label>
            <input
              v-model="cloneForm.name"
              class="form-control"
              placeholder="new-vm-name"
            />
          </div>

          <div class="form-group">
            <label class="form-label">Target Node</label>
            <select v-model="cloneForm.target" class="form-control">
              <option value="">Same as template ({{ cloneTarget?.node }})</option>
              <option v-for="n in cloneNodes" :key="n.node" :value="n.node">
                {{ n.node }}
              </option>
            </select>
          </div>

          <div class="form-group checkbox-group">
            <label class="checkbox-label">
              <input v-model="cloneForm.full" type="checkbox" />
              Full clone (independent copy, not linked)
            </label>
          </div>

          <div class="form-group checkbox-group">
            <label class="checkbox-label">
              <input v-model="cloneForm.startAfterClone" type="checkbox" />
              Start VM after clone
            </label>
          </div>

          <div v-if="cloneError" class="alert alert-danger mt-2">{{ cloneError }}</div>

          <div class="flex gap-1 mt-3">
            <button
              @click="submitClone"
              class="btn btn-primary"
              :disabled="cloning || !cloneForm.newid || !cloneForm.name"
            >
              {{ cloning ? 'Cloning...' : 'Clone VM' }}
            </button>
            <button @click="closeCloneModal" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/services/api'

// ── State ────────────────────────────────────────────────────────────────────
const hosts = ref([])
const templates = ref([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const selectedHostId = ref('')

// Clone modal state
const showCloneModal = ref(false)
const cloneTarget = ref(null)
const cloneNodes = ref([])
const cloneForm = ref({
  newid: null,
  name: '',
  target: '',
  full: true,
  startAfterClone: false
})
const cloning = ref(false)
const cloneError = ref('')

// ── Computed ─────────────────────────────────────────────────────────────────
const filteredTemplates = computed(() => {
  let list = templates.value
  if (selectedHostId.value) {
    list = list.filter(t => String(t.hostId) === String(selectedHostId.value))
  }
  if (search.value.trim()) {
    const q = search.value.trim().toLowerCase()
    list = list.filter(t =>
      (t.name || '').toLowerCase().includes(q) ||
      String(t.vmid).includes(q)
    )
  }
  return list
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatMB(bytes) {
  return Math.round(bytes / 1024 / 1024)
}

function formatGB(bytes) {
  const gb = bytes / 1024 / 1024 / 1024
  return gb >= 1 ? `${gb.toFixed(0)} GB` : `${(bytes / 1024 / 1024).toFixed(0)} MB`
}

// ── Data Loading ──────────────────────────────────────────────────────────────
async function loadHosts() {
  try {
    const res = await api.proxmox.listHosts()
    hosts.value = res.data || []
  } catch (err) {
    error.value = 'Failed to load Proxmox hosts.'
    console.error(err)
  }
}

async function loadTemplates() {
  if (hosts.value.length === 0) return
  loading.value = true
  error.value = ''
  templates.value = []

  const results = []
  await Promise.allSettled(
    hosts.value.map(async (host) => {
      try {
        const res = await api.pveNode.clusterResources(host.id, 'vm')
        const items = (res.data || [])
          .filter(vm => vm.template === 1)
          .map(vm => ({
            ...vm,
            hostId: host.id,
            hostName: host.name || host.host
          }))
        results.push(...items)
      } catch (err) {
        console.warn(`Failed to load resources for host ${host.id}:`, err)
      }
    })
  )

  templates.value = results.sort((a, b) => {
    if (a.hostName !== b.hostName) return a.hostName.localeCompare(b.hostName)
    return a.vmid - b.vmid
  })
  loading.value = false
}

// ── Clone Modal ───────────────────────────────────────────────────────────────
async function openCloneModal(tpl) {
  cloneTarget.value = tpl
  cloneError.value = ''
  cloneNodes.value = []
  cloneForm.value = {
    newid: null,
    name: `${tpl.name || `vm${tpl.vmid}`}-clone`,
    target: '',
    full: true,
    startAfterClone: false
  }
  showCloneModal.value = true

  // Pre-fill next available ID
  try {
    const res = await api.pveNode.nextId(tpl.hostId)
    const next = res.data?.nextid ?? res.data
    if (next) cloneForm.value.newid = Number(next)
  } catch (err) {
    console.warn('Could not fetch next VM ID:', err)
  }

  // Load nodes for target selection
  try {
    const res = await api.proxmox.listNodes(tpl.hostId)
    cloneNodes.value = (res.data || []).filter(n => n.node !== tpl.node)
  } catch (err) {
    console.warn('Could not fetch nodes:', err)
  }
}

function closeCloneModal() {
  showCloneModal.value = false
  cloneTarget.value = null
  cloneError.value = ''
}

async function submitClone() {
  if (!cloneForm.value.newid || !cloneForm.value.name) return
  cloning.value = true
  cloneError.value = ''

  const { newid, name, target, full } = cloneForm.value
  const payload = {
    newid,
    name,
    full: full ? 1 : 0,
    ...(target ? { target } : {})
  }

  try {
    await api.pveVm.clone(
      cloneTarget.value.hostId,
      cloneTarget.value.node,
      cloneTarget.value.vmid,
      payload
    )
    closeCloneModal()
    // Optionally refresh list to reflect any newly created template entries
    await loadTemplates()
  } catch (err) {
    cloneError.value =
      err?.response?.data?.detail ||
      err?.response?.data?.message ||
      'Clone operation failed.'
  } finally {
    cloning.value = false
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadHosts()
  await loadTemplates()
})
</script>

<style scoped>
/* ── Layout ─────────────────────────────────────────────────────────────── */
.templates-page {
  padding: 1.5rem;
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.page-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0.25rem 0 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.search-input {
  width: 220px;
}

.host-select {
  width: 180px;
}

/* ── Card ───────────────────────────────────────────────────────────────── */
.card {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}

.card-body {
  padding: 1.5rem;
}

.p-0 {
  padding: 0;
}

/* ── States ─────────────────────────────────────────────────────────────── */
.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 4rem 2rem;
  color: var(--text-secondary);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon {
  font-size: 2.5rem;
}

/* ── Table ──────────────────────────────────────────────────────────────── */
.table-container {
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.table th {
  background: var(--background);
  color: var(--text-secondary);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}

.table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
  vertical-align: middle;
}

.table tbody tr:last-child td {
  border-bottom: none;
}

.table tbody tr:hover {
  background: rgba(255, 255, 255, 0.03);
}

.vmid-cell {
  font-family: monospace;
  font-weight: 600;
  color: var(--primary-color) !important;
}

.name-cell {
  font-weight: 500;
}

.mono {
  font-family: monospace;
  font-size: 0.8rem;
}

.actions-cell {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

/* ── Badge ──────────────────────────────────────────────────────────────── */
.badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.badge-template {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

/* ── Buttons ────────────────────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-sm {
  padding: 0.3rem 0.65rem;
  font-size: 0.8rem;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
  border-color: #2563eb;
}

.btn-outline {
  background: transparent;
  color: var(--text-primary);
  border-color: var(--border-color);
}

.btn-outline:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.07);
}

/* ── Form Controls ──────────────────────────────────────────────────────── */
.form-control {
  padding: 0.5rem 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 0.875rem;
  color: var(--text-primary);
  min-height: 36px;
  width: 100%;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.form-group {
  margin-bottom: 1rem;
}

.form-label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 0.4rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.checkbox-group {
  margin-bottom: 0.75rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--primary-color);
  cursor: pointer;
}

/* ── Modal ──────────────────────────────────────────────────────────────── */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  width: 100%;
  max-width: 520px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-sm {
  max-width: 440px;
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.4rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.btn-close:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: 1.5rem;
}

/* ── Alert ──────────────────────────────────────────────────────────────── */
.alert {
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
}

.alert-danger {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
}

/* ── Utilities ──────────────────────────────────────────────────────────── */
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.mt-2 { margin-top: 0.5rem; }
.mt-3 { margin-top: 1rem; }
.mb-3 { margin-bottom: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-danger { color: var(--danger-color, #ef4444); }
</style>
