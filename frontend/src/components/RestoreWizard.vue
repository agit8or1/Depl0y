<template>
  <div v-if="visible" class="rw-overlay" @click.self="onClose">
    <div class="rw-modal">
      <!-- Header -->
      <div class="rw-header">
        <div>
          <h3 class="rw-title">Restore Wizard</h3>
          <p class="rw-subtitle text-muted text-sm">{{ stepTitle }}</p>
        </div>
        <button @click="onClose" class="rw-close">×</button>
      </div>

      <!-- Step indicator -->
      <div class="rw-steps">
        <div
          v-for="(label, idx) in stepLabels"
          :key="idx"
          :class="['rw-step', idx + 1 === currentStep ? 'rw-step--active' : idx + 1 < currentStep ? 'rw-step--done' : '']"
        >
          <span class="rw-step-num">{{ idx + 1 }}</span>
          <span class="rw-step-label">{{ label }}</span>
        </div>
      </div>

      <!-- Body -->
      <div class="rw-body">

        <!-- ── Step 1: Source ───────────────────────────────────────── -->
        <div v-if="currentStep === 1">
          <div class="form-group">
            <label class="form-label">Backup Type</label>
            <div class="radio-group">
              <label class="radio-opt" :class="form.sourceType === 'pve' ? 'radio-opt--active' : ''">
                <input type="radio" v-model="form.sourceType" value="pve" />
                <span>Proxmox Storage (vzdump)</span>
              </label>
              <label class="radio-opt" :class="form.sourceType === 'pbs' ? 'radio-opt--active' : ''">
                <input type="radio" v-model="form.sourceType" value="pbs" />
                <span>Proxmox Backup Server (PBS)</span>
              </label>
            </div>
          </div>

          <!-- PVE backup source -->
          <template v-if="form.sourceType === 'pve'">
            <div class="form-group">
              <label class="form-label">Host <span class="req">*</span></label>
              <select v-model="form.hostId" class="form-control" @change="onSourceHostChange">
                <option value="">— Select host —</option>
                <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
              </select>
            </div>
            <div class="form-group" v-if="form.hostId">
              <label class="form-label">Node <span class="req">*</span></label>
              <select v-model="form.sourceNode" class="form-control" @change="onSourceNodeChange">
                <option value="">— Select node —</option>
                <option v-for="n in sourceNodes" :key="n.node" :value="n.node">{{ n.node }}</option>
              </select>
            </div>
            <div class="form-group" v-if="form.sourceNode">
              <label class="form-label">Storage <span class="req">*</span></label>
              <select v-model="form.sourceStorage" class="form-control" @change="loadBackupFiles">
                <option value="">— Select storage —</option>
                <option v-for="s in sourceStorages" :key="s.storage" :value="s.storage">
                  {{ s.storage }} ({{ s.type }})
                </option>
              </select>
            </div>
            <div class="form-group" v-if="form.sourceStorage">
              <label class="form-label">Backup File <span class="req">*</span></label>
              <div v-if="loadingFiles" class="loading-inline">Loading backups…</div>
              <div v-else-if="backupFiles.length === 0" class="text-muted text-sm">No backup files found.</div>
              <div v-else class="backup-file-list">
                <div
                  v-for="bf in backupFiles"
                  :key="bf.volid"
                  :class="['backup-file-item', form.backupFile === bf.volid ? 'backup-file-item--active' : '']"
                  @click="selectBackupFile(bf)"
                >
                  <div class="bf-main">
                    <span class="bf-name">{{ bf.volid.split('/').pop() }}</span>
                    <span class="badge" :class="bf.notes ? 'badge-info' : 'badge-secondary'">
                      VMID {{ bf.vmid || '?' }}
                    </span>
                    <span v-if="bf.format" class="badge badge-secondary">{{ bf.format }}</span>
                  </div>
                  <div class="bf-meta text-muted text-xs">
                    {{ bf.ctime ? new Date(bf.ctime * 1000).toLocaleString() : '—' }}
                    {{ bf.size ? ' · ' + fmtBytes(bf.size) : '' }}
                    <span v-if="bf.notes"> · {{ bf.notes }}</span>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- PBS source -->
          <template v-if="form.sourceType === 'pbs'">
            <div class="form-group">
              <label class="form-label">PBS Server <span class="req">*</span></label>
              <select v-model="form.pbsServerId" class="form-control" @change="onPbsServerChange">
                <option value="">— Select PBS server —</option>
                <option v-for="p in pbsServers" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div class="form-group" v-if="form.pbsServerId">
              <label class="form-label">Datastore <span class="req">*</span></label>
              <select v-model="form.pbsDatastore" class="form-control" @change="loadPbsGroups">
                <option value="">— Select datastore —</option>
                <option v-for="ds in pbsDatastores" :key="ds.store" :value="ds.store">{{ ds.store }}</option>
              </select>
            </div>
            <div class="form-group" v-if="form.pbsDatastore">
              <label class="form-label">Backup Group <span class="req">*</span></label>
              <div v-if="loadingFiles" class="loading-inline">Loading…</div>
              <select v-else v-model="form.pbsGroup" class="form-control" @change="loadPbsSnapshots">
                <option value="">— Select group —</option>
                <option v-for="g in pbsGroups" :key="g['backup-id']" :value="g['backup-id']">
                  {{ g['backup-type'] }}/{{ g['backup-id'] }} ({{ g['backup-count'] }} backups)
                </option>
              </select>
            </div>
            <div class="form-group" v-if="form.pbsGroup">
              <label class="form-label">Snapshot <span class="req">*</span></label>
              <select v-model="form.pbsSnapshot" class="form-control">
                <option value="">— Select snapshot —</option>
                <option v-for="s in pbsSnapshots" :key="s['backup-time']" :value="s['backup-time']">
                  {{ new Date(s['backup-time'] * 1000).toLocaleString() }}
                  {{ s.size ? ' · ' + fmtBytes(s.size) : '' }}
                </option>
              </select>
            </div>
          </template>

          <div v-if="step1Error" class="error-msg">{{ step1Error }}</div>
        </div>

        <!-- ── Step 2: Target ───────────────────────────────────────── -->
        <div v-if="currentStep === 2">
          <div class="form-group">
            <label class="form-label">Target Host <span class="req">*</span></label>
            <select v-model="form.targetHostId" class="form-control" @change="onTargetHostChange">
              <option value="">— Select host —</option>
              <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
            </select>
          </div>
          <div class="form-group" v-if="form.targetHostId">
            <label class="form-label">Target Node <span class="req">*</span></label>
            <select v-model="form.targetNode" class="form-control" @change="loadTargetStorages">
              <option value="">— Select node —</option>
              <option v-for="n in targetNodes" :key="n.node" :value="n.node">{{ n.node }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">VMID</label>
            <div class="input-with-hint">
              <input v-model.number="form.targetVmid" type="number" class="form-control" placeholder="Leave blank to auto-assign" />
              <button v-if="form.targetHostId" @click="autoAssignVmid" class="btn btn-outline btn-sm ml-1" :disabled="loadingNextId">
                {{ loadingNextId ? '…' : 'Next Free' }}
              </button>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">VM Name</label>
            <input v-model="form.targetName" class="form-control" placeholder="Optional name override" />
          </div>
          <div class="form-group" v-if="form.targetNode">
            <label class="form-label">Target Storage <span class="req">*</span></label>
            <select v-model="form.targetStorage" class="form-control">
              <option value="">— Select storage —</option>
              <option v-for="s in targetStorages" :key="s.storage" :value="s.storage">
                {{ s.storage }} ({{ s.type }}) — {{ fmtBytes(s.avail) }} free
              </option>
            </select>
          </div>
          <div v-if="form.sourceType === 'pbs'" class="form-group">
            <label class="form-label">Target PBS Datastore</label>
            <input v-model="form.pbsTargetDatastore" class="form-control" placeholder="Same as source" />
          </div>
          <div v-if="step2Error" class="error-msg">{{ step2Error }}</div>
        </div>

        <!-- ── Step 3: Options ─────────────────────────────────────── -->
        <div v-if="currentStep === 3">
          <div class="options-grid">
            <label class="toggle-row">
              <div class="toggle-info">
                <span class="toggle-title">Start VM after restore</span>
                <span class="toggle-desc text-muted text-xs">Automatically start the VM when restore completes</span>
              </div>
              <input type="checkbox" v-model="form.startAfter" class="toggle-input" />
            </label>

            <label class="toggle-row">
              <div class="toggle-info">
                <span class="toggle-title">Unique MAC addresses</span>
                <span class="toggle-desc text-muted text-xs">Re-generate NICs with new MAC addresses (avoids conflicts)</span>
              </div>
              <input type="checkbox" v-model="form.uniqueMac" class="toggle-input" />
            </label>

            <label class="toggle-row">
              <div class="toggle-info">
                <span class="toggle-title">Live restore</span>
                <span class="toggle-desc text-muted text-xs">Replace an existing running VM online (VMID must exist)</span>
              </div>
              <input type="checkbox" v-model="form.liveRestore" class="toggle-input" />
            </label>

            <template v-if="form.vmType === 'lxc'">
              <div class="form-group mt-2">
                <label class="form-label">New Hostname (LXC)</label>
                <input v-model="form.lxcHostname" class="form-control" placeholder="Leave blank to keep original" />
              </div>
              <div class="form-group">
                <label class="form-label">New Root Password (LXC)</label>
                <input v-model="form.lxcPassword" type="password" class="form-control" placeholder="Leave blank to keep original" />
              </div>
            </template>
          </div>
        </div>

        <!-- ── Step 4: Confirm & Execute ──────────────────────────── -->
        <div v-if="currentStep === 4">
          <div class="confirm-summary">
            <div class="summary-section">
              <h4 class="summary-title">Source</h4>
              <div class="summary-row"><span>Type</span><span>{{ form.sourceType === 'pve' ? 'Proxmox Storage' : 'PBS' }}</span></div>
              <div v-if="form.sourceType === 'pve'" class="summary-row">
                <span>File</span>
                <code>{{ form.backupFile || '—' }}</code>
              </div>
              <div v-if="form.sourceType === 'pbs'" class="summary-row">
                <span>Server / Datastore</span>
                <span>{{ pbsServerName }} / {{ form.pbsDatastore }}</span>
              </div>
            </div>

            <div class="summary-section">
              <h4 class="summary-title">Target</h4>
              <div class="summary-row"><span>Node</span><span>{{ form.targetNode }}</span></div>
              <div class="summary-row"><span>VMID</span><span>{{ form.targetVmid || 'auto' }}</span></div>
              <div class="summary-row" v-if="form.targetName"><span>Name</span><span>{{ form.targetName }}</span></div>
              <div class="summary-row"><span>Storage</span><span>{{ form.targetStorage }}</span></div>
            </div>

            <div class="summary-section">
              <h4 class="summary-title">Options</h4>
              <div class="summary-row"><span>Start after restore</span><span>{{ form.startAfter ? 'Yes' : 'No' }}</span></div>
              <div class="summary-row"><span>Unique MACs</span><span>{{ form.uniqueMac ? 'Yes' : 'No' }}</span></div>
              <div class="summary-row"><span>Live restore</span><span>{{ form.liveRestore ? 'Yes' : 'No' }}</span></div>
            </div>
          </div>

          <div class="warn-box mt-2">
            Restore may take several minutes depending on backup size. The VM will be overwritten if it already exists.
          </div>

          <div v-if="executeError" class="error-msg mt-2">{{ executeError }}</div>
        </div>

      </div>

      <!-- Footer -->
      <div class="rw-footer">
        <button v-if="currentStep > 1" @click="prevStep" class="btn btn-outline" :disabled="executing">
          Back
        </button>
        <span style="flex:1;" />
        <button
          v-if="currentStep < 4"
          @click="nextStep"
          class="btn btn-primary"
          :disabled="!canProceed"
        >
          Next
        </button>
        <button
          v-if="currentStep === 4"
          @click="executeRestore"
          class="btn btn-primary"
          :disabled="executing"
        >
          {{ executing ? 'Starting…' : 'Execute Restore' }}
        </button>
      </div>
    </div>
  </div>

  <!-- Task progress modal appears separately -->
  <TaskProgressModal
    :visible="!!taskUpid"
    :upid="taskUpid"
    :host-id="form.targetHostId"
    :node="form.targetNode"
    @close="onTaskClose"
    @success="onTaskSuccess"
  />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import api from '@/services/api'
import TaskProgressModal from '@/components/TaskProgressModal.vue'
import { useToast } from 'vue-toastification'

const props = defineProps({
  visible: { type: Boolean, default: false },
  // Optional pre-fill
  preHostId: { type: [Number, String], default: null },
  preNode: { type: String, default: '' },
  preVmid: { type: [Number, String], default: null },
})

const emit = defineEmits(['close', 'restored'])
const toast = useToast()

// ── State ─────────────────────────────────────────────────────────────────────

const currentStep = ref(1)
const stepLabels = ['Source', 'Target', 'Options', 'Confirm']

const form = ref({
  sourceType: 'pve',
  // PVE source
  hostId: '',
  sourceNode: '',
  sourceStorage: '',
  backupFile: '',
  backupVmid: null,
  vmType: 'qemu',
  // PBS source
  pbsServerId: '',
  pbsDatastore: '',
  pbsGroup: '',
  pbsSnapshot: '',
  pbsTargetDatastore: '',
  // Target
  targetHostId: '',
  targetNode: '',
  targetVmid: null,
  targetName: '',
  targetStorage: '',
  // Options
  startAfter: false,
  uniqueMac: true,
  liveRestore: false,
  lxcHostname: '',
  lxcPassword: '',
})

const hosts = ref([])
const sourceNodes = ref([])
const sourceStorages = ref([])
const targetNodes = ref([])
const targetStorages = ref([])
const backupFiles = ref([])
const pbsServers = ref([])
const pbsDatastores = ref([])
const pbsGroups = ref([])
const pbsSnapshots = ref([])

const loadingFiles = ref(false)
const loadingNextId = ref(false)
const executing = ref(false)

const step1Error = ref('')
const step2Error = ref('')
const executeError = ref('')
const taskUpid = ref(null)

// ── Computed ──────────────────────────────────────────────────────────────────

const stepTitle = computed(() => {
  const titles = [
    'Select the backup source and file',
    'Choose restore destination',
    'Configure restore options',
    'Review and execute',
  ]
  return titles[currentStep.value - 1] || ''
})

const pbsServerName = computed(() => {
  const s = pbsServers.value.find(p => p.id === form.value.pbsServerId)
  return s?.name || form.value.pbsServerId
})

const canProceed = computed(() => {
  if (currentStep.value === 1) {
    if (form.value.sourceType === 'pve') {
      return !!(form.value.hostId && form.value.sourceNode && form.value.sourceStorage && form.value.backupFile)
    } else {
      return !!(form.value.pbsServerId && form.value.pbsDatastore && form.value.pbsGroup && form.value.pbsSnapshot)
    }
  }
  if (currentStep.value === 2) {
    return !!(form.value.targetHostId && form.value.targetNode && form.value.targetStorage)
  }
  return true
})

// ── Init ──────────────────────────────────────────────────────────────────────

async function loadHosts() {
  try {
    const res = await api.proxmox.listHosts()
    hosts.value = res.data || []
    // Apply pre-fills
    if (props.preHostId) {
      form.value.hostId = Number(props.preHostId)
      form.value.targetHostId = Number(props.preHostId)
      await onSourceHostChange()
      await onTargetHostChange()
    }
  } catch (e) { /* ignore */ }
}

async function loadPbsServers() {
  try {
    const res = await api.pbs.list()
    pbsServers.value = res.data || []
  } catch (e) { /* ignore */ }
}

watch(() => props.visible, async (val) => {
  if (val) {
    currentStep.value = 1
    step1Error.value = ''
    step2Error.value = ''
    executeError.value = ''
    taskUpid.value = null
    await loadHosts()
    await loadPbsServers()
  }
})

// ── Source handlers ───────────────────────────────────────────────────────────

async function onSourceHostChange() {
  sourceNodes.value = []
  sourceStorages.value = []
  backupFiles.value = []
  if (!form.value.hostId) return
  try {
    const res = await api.proxmox.listNodes(form.value.hostId)
    sourceNodes.value = res.data || []
    if (props.preNode) form.value.sourceNode = props.preNode
  } catch (e) { /* ignore */ }
}

async function onSourceNodeChange() {
  sourceStorages.value = []
  backupFiles.value = []
  if (!form.value.hostId || !form.value.sourceNode) return
  try {
    const res = await api.pveNode.listStorage(form.value.hostId, form.value.sourceNode)
    // Filter to storages that can hold backups
    sourceStorages.value = (res.data || []).filter(s =>
      s.content && s.content.includes('backup')
    )
  } catch (e) { /* ignore */ }
}

async function loadBackupFiles() {
  backupFiles.value = []
  if (!form.value.hostId || !form.value.sourceNode || !form.value.sourceStorage) return
  loadingFiles.value = true
  try {
    const res = await api.pveNode.browseStorage(
      form.value.hostId,
      form.value.sourceNode,
      form.value.sourceStorage,
      { content: 'backup' }
    )
    backupFiles.value = (res.data || []).sort((a, b) => (b.ctime || 0) - (a.ctime || 0))
  } catch (e) { /* ignore */ } finally {
    loadingFiles.value = false
  }
}

function selectBackupFile(bf) {
  form.value.backupFile = bf.volid
  form.value.backupVmid = bf.vmid
  // Detect type: lxc or qemu from volid
  if (bf.volid && bf.volid.includes('lxc')) {
    form.value.vmType = 'lxc'
  } else {
    form.value.vmType = 'qemu'
  }
}

async function onPbsServerChange() {
  pbsDatastores.value = []
  pbsGroups.value = []
  pbsSnapshots.value = []
  if (!form.value.pbsServerId) return
  try {
    const res = await api.pbsMgmt.listDatastores(form.value.pbsServerId)
    pbsDatastores.value = res.data || []
  } catch (e) { /* ignore */ }
}

async function loadPbsGroups() {
  pbsGroups.value = []
  pbsSnapshots.value = []
  if (!form.value.pbsServerId || !form.value.pbsDatastore) return
  loadingFiles.value = true
  try {
    const res = await api.pbsMgmt.listGroups(form.value.pbsServerId, form.value.pbsDatastore)
    pbsGroups.value = res.data || []
  } catch (e) { /* ignore */ } finally {
    loadingFiles.value = false
  }
}

async function loadPbsSnapshots() {
  pbsSnapshots.value = []
  if (!form.value.pbsServerId || !form.value.pbsDatastore || !form.value.pbsGroup) return
  try {
    const res = await api.pbsMgmt.listSnapshots(form.value.pbsServerId, form.value.pbsDatastore, {
      'backup-id': form.value.pbsGroup,
    })
    pbsSnapshots.value = (res.data || []).sort((a, b) => b['backup-time'] - a['backup-time'])
  } catch (e) { /* ignore */ }
}

// ── Target handlers ───────────────────────────────────────────────────────────

async function onTargetHostChange() {
  targetNodes.value = []
  targetStorages.value = []
  if (!form.value.targetHostId) return
  try {
    const res = await api.proxmox.listNodes(form.value.targetHostId)
    targetNodes.value = res.data || []
  } catch (e) { /* ignore */ }
}

async function loadTargetStorages() {
  targetStorages.value = []
  if (!form.value.targetHostId || !form.value.targetNode) return
  try {
    const res = await api.pveNode.listStorage(form.value.targetHostId, form.value.targetNode)
    targetStorages.value = (res.data || []).filter(s => s.content && s.content.includes('images'))
  } catch (e) { /* ignore */ }
}

async function autoAssignVmid() {
  if (!form.value.targetHostId) return
  loadingNextId.value = true
  try {
    const res = await api.pveNode.nextId(form.value.targetHostId)
    form.value.targetVmid = res.data?.vmid
  } catch (e) { /* ignore */ } finally {
    loadingNextId.value = false
  }
}

// ── Navigation ────────────────────────────────────────────────────────────────

function nextStep() {
  step1Error.value = ''
  step2Error.value = ''
  if (currentStep.value < 4) currentStep.value++
}

function prevStep() {
  if (currentStep.value > 1) currentStep.value--
}

// ── Execute ───────────────────────────────────────────────────────────────────

async function executeRestore() {
  executing.value = true
  executeError.value = ''
  try {
    const vmid = form.value.targetVmid || null
    let upid

    if (form.value.sourceType === 'pve') {
      const payload = {
        archive: form.value.backupFile,
        storage: form.value.targetStorage,
      }
      if (form.value.startAfter) payload.start = 1
      if (form.value.uniqueMac) payload.unique = 1
      if (form.value.liveRestore) payload.live = 1
      if (form.value.targetName) payload.name = form.value.targetName

      if (form.value.vmType === 'lxc') {
        if (form.value.lxcHostname) payload.hostname = form.value.lxcHostname
        if (form.value.lxcPassword) payload.password = form.value.lxcPassword
        const res = await api.pveNode.restoreLxcBackup(
          form.value.targetHostId,
          form.value.targetNode,
          vmid || 0,
          payload
        )
        upid = res.data?.upid
      } else {
        const res = await api.pveNode.restoreBackup(
          form.value.targetHostId,
          form.value.targetNode,
          vmid || 0,
          payload
        )
        upid = res.data?.upid
      }
    } else {
      // PBS restore — use vzdump-compatible restore via PVE (PBS is mounted as storage)
      // The archive path for PBS is: pbsid:backup-type/backup-id/backup-time
      const snaptime = form.value.pbsSnapshot
      const backupId = form.value.pbsGroup
      const archivePath = `${form.value.pbsDatastore}:${backupId}/${snaptime}`
      const payload = {
        archive: archivePath,
        storage: form.value.targetStorage || form.value.pbsTargetDatastore,
      }
      if (form.value.startAfter) payload.start = 1
      if (form.value.uniqueMac) payload.unique = 1
      if (form.value.targetName) payload.name = form.value.targetName

      const res = await api.pveNode.restoreBackup(
        form.value.targetHostId,
        form.value.targetNode,
        vmid || 0,
        payload
      )
      upid = res.data?.upid
    }

    if (upid) {
      taskUpid.value = upid
      toast.success('Restore task started')
    } else {
      toast.success('Restore completed')
      emit('restored')
      emit('close')
    }
  } catch (e) {
    executeError.value = e.response?.data?.detail || String(e)
  } finally {
    executing.value = false
  }
}

function onTaskClose() {
  taskUpid.value = null
}

function onTaskSuccess() {
  taskUpid.value = null
  toast.success('Restore completed successfully')
  emit('restored')
  emit('close')
}

function onClose() {
  if (taskUpid.value) return // don't close while task is running
  emit('close')
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let v = bytes
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return v.toFixed(1) + ' ' + units[i]
}
</script>

<style scoped>
/* ── Overlay / Modal ───────────────────────────────────────── */
.rw-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1050;
}

.rw-modal {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  width: 620px;
  max-width: 96vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,.5);
}

/* ── Header ────────────────────────────────────────────────── */
.rw-header {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-shrink: 0;
}

.rw-title { margin: 0; font-size: 1.05rem; font-weight: 700; }
.rw-subtitle { margin: 0.2rem 0 0; }

.rw-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.rw-close:hover { color: var(--text-primary); }

/* ── Step indicator ────────────────────────────────────────── */
.rw-steps {
  display: flex;
  gap: 0;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
  overflow-x: auto;
}

.rw-step {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.rw-step--active {
  background: rgba(59,130,246,.15);
  color: #60a5fa;
}

.rw-step--done {
  color: #4ade80;
}

.rw-step-num {
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  background: var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 700;
  flex-shrink: 0;
}

.rw-step--active .rw-step-num { background: #3b82f6; color: #fff; }
.rw-step--done .rw-step-num   { background: #22c55e; color: #fff; }

/* ── Body ──────────────────────────────────────────────────── */
.rw-body {
  padding: 1.25rem;
  overflow-y: auto;
  flex: 1;
}

/* ── Footer ────────────────────────────────────────────────── */
.rw-footer {
  padding: 0.875rem 1.25rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}

/* ── Forms ─────────────────────────────────────────────────── */
.form-group { margin-bottom: 1rem; }
.form-label { display: block; margin-bottom: 0.35rem; font-size: 0.85rem; font-weight: 500; }
.req { color: #f87171; }

.form-control {
  width: 100%;
  padding: 0.45rem 0.75rem;
  background: var(--bg-tertiary, #0d0d1a);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  color: var(--text-primary);
  font-size: 0.875rem;
  box-sizing: border-box;
}

.radio-group {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.radio-opt {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.875rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.1s, border-color 0.1s;
}

.radio-opt--active {
  background: rgba(59,130,246,.12);
  border-color: rgba(59,130,246,.4);
  color: #60a5fa;
}

.radio-opt input { display: none; }

/* ── Backup file list ──────────────────────────────────────── */
.backup-file-list {
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}

.backup-file-item {
  padding: 0.6rem 0.875rem;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.1s;
}

.backup-file-item:last-child { border-bottom: none; }
.backup-file-item:hover { background: rgba(255,255,255,.04); }
.backup-file-item--active { background: rgba(59,130,246,.1); }

.bf-main {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.bf-name {
  font-family: monospace;
  font-size: 0.8rem;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bf-meta { margin-top: 0.15rem; }

/* ── Options grid ──────────────────────────────────────────── */
.options-grid {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: var(--bg-tertiary, rgba(255,255,255,.03));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: pointer;
  gap: 1rem;
}

.toggle-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.toggle-title { font-weight: 500; font-size: 0.875rem; }

.toggle-input {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}

/* ── Confirm summary ───────────────────────────────────────── */
.confirm-summary {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.summary-section {
  background: var(--bg-tertiary, rgba(255,255,255,.03));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
}

.summary-title {
  margin: 0;
  padding: 0.5rem 0.875rem;
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
}

.summary-row {
  display: flex;
  justify-content: space-between;
  padding: 0.4rem 0.875rem;
  font-size: 0.875rem;
  border-bottom: 1px solid rgba(255,255,255,.04);
}

.summary-row:last-child { border-bottom: none; }
.summary-row span:first-child { color: var(--text-secondary); }

/* ── Badges ────────────────────────────────────────────────── */
.badge {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  border-radius: 9999px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
}

.badge-info     { background: rgba(59,130,246,.15); color: #60a5fa; }
.badge-secondary{ background: rgba(148,163,184,.15); color: #94a3b8; }

/* ── Buttons ───────────────────────────────────────────────── */
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
}

.btn-primary { background: var(--primary-color, #3b82f6); color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-outline { background: transparent; border-color: var(--border-color); color: var(--text-primary); }
.btn-outline:hover { background: rgba(255,255,255,.05); }
.btn-outline:disabled { opacity: .5; cursor: not-allowed; }
.btn-sm { padding: 0.3rem 0.6rem; font-size: 0.8rem; }

/* ── Misc ──────────────────────────────────────────────────── */
.text-muted { color: var(--text-secondary); }
.text-sm    { font-size: 0.875rem; }
.text-xs    { font-size: 0.75rem; }
.mt-2       { margin-top: 0.75rem; }
.ml-1       { margin-left: 0.35rem; }

.input-with-hint { display: flex; align-items: center; }

.error-msg {
  background: rgba(239,68,68,.1);
  border: 1px solid rgba(239,68,68,.3);
  border-radius: 0.375rem;
  padding: 0.6rem 0.9rem;
  color: #f87171;
  font-size: 0.85rem;
}

.warn-box {
  background: rgba(234,179,8,.08);
  border: 1px solid rgba(234,179,8,.25);
  border-radius: 0.375rem;
  padding: 0.75rem 1rem;
  color: #facc15;
  font-size: 0.85rem;
}

.loading-inline {
  font-size: 0.85rem;
  color: var(--text-secondary);
  padding: 0.5rem 0;
}
</style>
