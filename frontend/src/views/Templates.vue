<template>
  <div class="templates-page">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">VM Templates</h2>
        <p class="page-subtitle">
          Clone and manage templates across all Proxmox hosts
          <span v-if="!loading && templates.length > 0" class="count-badge">
            {{ filteredTemplates.length }} template{{ filteredTemplates.length !== 1 ? 's' : '' }}
            across {{ uniqueHostCount }} host{{ uniqueHostCount !== 1 ? 's' : '' }}
          </span>
        </p>
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
        <select v-model="sortBy" class="form-control sort-select">
          <option value="name">Sort: Name</option>
          <option value="vmid">Sort: VMID</option>
          <option value="size">Sort: Size</option>
          <option value="node">Sort: Node</option>
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
          <span class="empty-icon">&#128203;</span>
          <p>No templates found{{ search ? ' matching your search' : '' }}.</p>
        </div>
        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>VMID</th>
                <th>Name</th>
                <th>OS</th>
                <th>Node</th>
                <th>Host</th>
                <th>Memory</th>
                <th>CPUs</th>
                <th>Disk</th>
                <th>Notes</th>
                <th>Clones</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tpl in filteredTemplates" :key="`${tpl.hostId}-${tpl.vmid}`">
                <td class="vmid-cell">{{ tpl.vmid }}</td>
                <td class="name-cell">
                  <span class="name-text">{{ tpl.name || `VM ${tpl.vmid}` }}</span>
                </td>
                <td>
                  <span class="os-badge" :class="`os-${detectOS(tpl.name)}`">
                    {{ detectOSLabel(tpl.name) }}
                  </span>
                </td>
                <td class="mono">{{ tpl.node }}</td>
                <td class="mono">{{ tpl.hostName }}</td>
                <td>
                  <span v-if="tpl.maxmem" class="meta-val">{{ formatMB(tpl.maxmem) }} MB</span>
                  <span v-else class="dim">—</span>
                </td>
                <td>
                  <span v-if="tpl.maxcpu" class="meta-val">{{ tpl.maxcpu }} vCPU</span>
                  <span v-else class="dim">—</span>
                </td>
                <td>
                  <span v-if="tpl.maxdisk" class="meta-val">{{ formatGB(tpl.maxdisk) }}</span>
                  <span v-else class="dim">—</span>
                </td>
                <td class="notes-cell">
                  <span v-if="tpl.description" class="notes-text" :title="tpl.description">
                    {{ truncate(tpl.description, 40) }}
                  </span>
                  <span v-else class="dim">—</span>
                </td>
                <td class="dim">N/A</td>
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
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Clone Template</h3>
          <button @click="closeCloneModal" class="btn-close">&times;</button>
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
            <label class="form-label">Clone Mode</label>
            <div class="radio-group">
              <label class="radio-label">
                <input v-model="cloneForm.full" type="radio" :value="true" />
                <span>
                  <strong>Full Clone</strong>
                  <span class="radio-hint">Independent copy — can be moved to any storage</span>
                </span>
              </label>
              <label class="radio-label">
                <input v-model="cloneForm.full" type="radio" :value="false" />
                <span>
                  <strong>Linked Clone</strong>
                  <span class="radio-hint">Shares base disk with template — faster, less space</span>
                </span>
              </label>
            </div>
            <div v-if="!cloneForm.full" class="info-note mt-2">
              Linked clones cannot be moved to different storage pools.
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Target Node</label>
            <select v-model="cloneForm.target" class="form-control" @change="onTargetNodeChange">
              <option value="">Same as template ({{ cloneTarget?.node }})</option>
              <option v-for="n in cloneNodes" :key="n.node" :value="n.node">
                {{ n.node }}
              </option>
            </select>
          </div>

          <!-- Storage selector — only for full clones -->
          <div v-if="cloneForm.full" class="form-group">
            <label class="form-label">Target Storage</label>
            <select v-model="cloneForm.storage" class="form-control" :disabled="loadingStorages">
              <option value="">Default storage</option>
              <option v-for="s in cloneStorages" :key="s.storage" :value="s.storage">
                {{ s.storage }}
                <template v-if="s.avail"> ({{ formatGB(s.avail) }} free)</template>
              </option>
            </select>
            <div v-if="loadingStorages" class="hint-text mt-1">Loading storages...</div>
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

    <!-- Success Toast -->
    <transition name="toast-fade">
      <div v-if="successToast.show" class="toast-success">
        <span>{{ successToast.message }}</span>
        <router-link
          v-if="successToast.vmLink"
          :to="successToast.vmLink"
          class="toast-link"
          @click="successToast.show = false"
        >Go to VM &rarr;</router-link>
        <button class="toast-close" @click="successToast.show = false">&times;</button>
      </div>
    </transition>
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
const sortBy = ref('name')

// Clone modal state
const showCloneModal = ref(false)
const cloneTarget = ref(null)
const cloneNodes = ref([])
const cloneStorages = ref([])
const loadingStorages = ref(false)
const cloneForm = ref({
  newid: null,
  name: '',
  target: '',
  storage: '',
  full: true,
  startAfterClone: false
})
const cloning = ref(false)
const cloneError = ref('')

// Success toast
const successToast = ref({ show: false, message: '', vmLink: '' })

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
  // Sort
  list = [...list].sort((a, b) => {
    if (sortBy.value === 'vmid') return a.vmid - b.vmid
    if (sortBy.value === 'size') return (b.maxdisk || 0) - (a.maxdisk || 0)
    if (sortBy.value === 'node') return a.node.localeCompare(b.node)
    // default: name
    const an = (a.name || `vm${a.vmid}`).toLowerCase()
    const bn = (b.name || `vm${b.vmid}`).toLowerCase()
    return an.localeCompare(bn)
  })
  return list
})

const uniqueHostCount = computed(() => {
  const ids = new Set(filteredTemplates.value.map(t => t.hostId))
  return ids.size
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatMB(bytes) {
  return Math.round(bytes / 1024 / 1024)
}

function formatGB(bytes) {
  const gb = bytes / 1024 / 1024 / 1024
  return gb >= 1 ? `${gb.toFixed(0)} GB` : `${(bytes / 1024 / 1024).toFixed(0)} MB`
}

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '…' : str
}

const OS_PATTERNS = [
  { key: 'ubuntu',  label: 'Ubuntu',  patterns: ['ubuntu'] },
  { key: 'debian',  label: 'Debian',  patterns: ['debian'] },
  { key: 'centos',  label: 'CentOS',  patterns: ['centos'] },
  { key: 'rhel',    label: 'RHEL',    patterns: ['rhel', 'redhat', 'red-hat'] },
  { key: 'rocky',   label: 'Rocky',   patterns: ['rocky'] },
  { key: 'alma',    label: 'AlmaLinux', patterns: ['alma'] },
  { key: 'fedora',  label: 'Fedora',  patterns: ['fedora'] },
  { key: 'suse',    label: 'SUSE',    patterns: ['suse', 'opensuse'] },
  { key: 'arch',    label: 'Arch',    patterns: ['arch'] },
  { key: 'windows', label: 'Windows', patterns: ['win', 'windows', 'server-20', 'w2k'] },
  { key: 'freebsd', label: 'FreeBSD', patterns: ['freebsd', 'bsd'] },
]

function detectOS(name) {
  if (!name) return 'unknown'
  const lower = (name || '').toLowerCase()
  for (const os of OS_PATTERNS) {
    if (os.patterns.some(p => lower.includes(p))) return os.key
  }
  return 'unknown'
}

function detectOSLabel(name) {
  if (!name) return 'Unknown'
  const lower = (name || '').toLowerCase()
  for (const os of OS_PATTERNS) {
    if (os.patterns.some(p => lower.includes(p))) return os.label
  }
  return 'Linux'
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

  templates.value = results
  loading.value = false
}

// ── Clone Modal ───────────────────────────────────────────────────────────────
async function openCloneModal(tpl) {
  cloneTarget.value = tpl
  cloneError.value = ''
  cloneNodes.value = []
  cloneStorages.value = []
  cloneForm.value = {
    newid: null,
    name: `${tpl.name || `vm${tpl.vmid}`}-clone`,
    target: '',
    storage: '',
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

  // Load storages for the template's own node (default target)
  await loadStoragesForNode(tpl.hostId, tpl.node)
}

async function loadStoragesForNode(hostId, node) {
  loadingStorages.value = true
  cloneStorages.value = []
  try {
    const res = await api.pveNode.listStorage(hostId, node)
    // Filter to storages that support disk images (content includes 'images')
    cloneStorages.value = (res.data || []).filter(s =>
      s.content && s.content.split(',').includes('images')
    )
  } catch (err) {
    console.warn('Could not fetch storages:', err)
  } finally {
    loadingStorages.value = false
  }
}

async function onTargetNodeChange() {
  const hostId = cloneTarget.value?.hostId
  const node = cloneForm.value.target || cloneTarget.value?.node
  cloneForm.value.storage = ''
  if (hostId && node) {
    await loadStoragesForNode(hostId, node)
  }
}

function closeCloneModal() {
  showCloneModal.value = false
  cloneTarget.value = null
  cloneError.value = ''
}

function showSuccessToast(newVmId, hostId, node) {
  successToast.value = {
    show: true,
    message: `VM ${newVmId} cloned successfully.`,
    vmLink: `/proxmox/${hostId}/nodes/${node}/vms/${newVmId}`
  }
  setTimeout(() => { successToast.value.show = false }, 8000)
}

async function submitClone() {
  if (!cloneForm.value.newid || !cloneForm.value.name) return
  cloning.value = true
  cloneError.value = ''

  const { newid, name, target, full, storage } = cloneForm.value
  const payload = {
    newid,
    name,
    full: full ? 1 : 0,
    ...(target ? { target } : {}),
    ...(full && storage ? { storage } : {})
  }

  const resolvedNode = target || cloneTarget.value.node

  try {
    await api.pveVm.clone(
      cloneTarget.value.hostId,
      cloneTarget.value.node,
      cloneTarget.value.vmid,
      payload
    )

    // Start VM after clone if requested
    if (cloneForm.value.startAfterClone) {
      try {
        await api.pveVm.start(cloneTarget.value.hostId, resolvedNode, newid)
      } catch (startErr) {
        console.warn('Could not start VM after clone:', startErr)
      }
    }

    const savedHostId = cloneTarget.value.hostId
    closeCloneModal()
    showSuccessToast(newid, savedHostId, resolvedNode)
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
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.count-badge {
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 12px;
  padding: 0.1rem 0.6rem;
  font-size: 0.75rem;
  font-weight: 600;
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

.sort-select {
  width: 150px;
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

.name-text {
  display: block;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono {
  font-family: monospace;
  font-size: 0.8rem;
}

.meta-val {
  font-size: 0.8rem;
  color: var(--text-primary);
}

.dim {
  color: var(--text-secondary);
  font-size: 0.8rem;
}

.notes-cell {
  max-width: 200px;
}

.notes-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
  cursor: help;
}

.actions-cell {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

/* ── OS Badges ──────────────────────────────────────────────────────────── */
.os-badge {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  background: rgba(100, 116, 139, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(100, 116, 139, 0.25);
  white-space: nowrap;
}

.os-ubuntu  { background: rgba(233, 84, 32, 0.12);  color: #f97316; border-color: rgba(249, 115, 22, 0.3); }
.os-debian  { background: rgba(167, 0, 51, 0.12);   color: #f472b6; border-color: rgba(244, 114, 182, 0.3); }
.os-centos  { background: rgba(156, 39, 176, 0.12); color: #c084fc; border-color: rgba(192, 132, 252, 0.3); }
.os-rhel    { background: rgba(220, 38, 38, 0.12);  color: #f87171; border-color: rgba(248, 113, 113, 0.3); }
.os-rocky   { background: rgba(20, 184, 166, 0.12); color: #2dd4bf; border-color: rgba(45, 212, 191, 0.3); }
.os-alma    { background: rgba(59, 130, 246, 0.12); color: #60a5fa; border-color: rgba(96, 165, 250, 0.3); }
.os-fedora  { background: rgba(37, 99, 235, 0.12);  color: #818cf8; border-color: rgba(129, 140, 248, 0.3); }
.os-suse    { background: rgba(132, 204, 22, 0.12); color: #a3e635; border-color: rgba(163, 230, 53, 0.3); }
.os-arch    { background: rgba(14, 165, 233, 0.12); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); }
.os-windows { background: rgba(0, 120, 212, 0.12);  color: #7dd3fc; border-color: rgba(125, 211, 252, 0.3); }
.os-freebsd { background: rgba(220, 38, 38, 0.10);  color: #fca5a5; border-color: rgba(252, 165, 165, 0.3); }

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

.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

/* ── Radio group (clone mode) ───────────────────────────────────────────── */
.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.radio-label {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
  transition: border-color 0.15s, background 0.15s;
}

.radio-label:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: var(--primary-color);
}

.radio-label input[type="radio"] {
  margin-top: 2px;
  accent-color: var(--primary-color);
  flex-shrink: 0;
}

.radio-label > span {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.radio-hint {
  font-size: 0.775rem;
  color: var(--text-secondary);
  font-weight: 400;
}

.info-note {
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.3);
  color: #fbbf24;
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
}

.hint-text {
  font-size: 0.775rem;
  color: var(--text-secondary);
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
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  background: var(--surface);
  z-index: 1;
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

/* ── Toast ──────────────────────────────────────────────────────────────── */
.toast-success {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.4);
  color: #34d399;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.875rem;
  z-index: 2000;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  max-width: 380px;
}

.toast-link {
  color: #6ee7b7;
  text-decoration: underline;
  font-weight: 600;
  white-space: nowrap;
}

.toast-link:hover {
  color: #a7f3d0;
}

.toast-close {
  background: none;
  border: none;
  color: #34d399;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  margin-left: auto;
  opacity: 0.7;
}

.toast-close:hover {
  opacity: 1;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(0.5rem);
}

/* ── Utilities ──────────────────────────────────────────────────────────── */
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.5rem; }
.mt-3 { margin-top: 1rem; }
.mb-3 { margin-bottom: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-danger { color: var(--danger-color, #ef4444); }
</style>
