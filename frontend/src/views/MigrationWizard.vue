<template>
  <div class="migration-wizard-page">
    <!-- Header -->
    <div class="page-header mb-3">
      <div class="header-left">
        <router-link :to="backLink" class="back-link">← Back to VM</router-link>
        <h2 class="page-title">
          Migrate {{ vmType === 'lxc' ? 'Container' : 'VM' }}
          <span class="badge badge-info ml-1">{{ vmid }}</span>
        </h2>
      </div>
    </div>

    <!-- Step indicator -->
    <div class="wizard-steps mb-4">
      <div
        v-for="(stepLabel, idx) in stepLabels"
        :key="idx"
        :class="['wizard-step', currentStep === idx + 1 ? 'wizard-step--active' : '', currentStep > idx + 1 ? 'wizard-step--done' : '']"
      >
        <div class="wizard-step__circle">
          <span v-if="currentStep > idx + 1">&#10003;</span>
          <span v-else>{{ idx + 1 }}</span>
        </div>
        <span class="wizard-step__label">{{ stepLabel }}</span>
        <div v-if="idx < stepLabels.length - 1" class="wizard-step__connector"></div>
      </div>
    </div>

    <!-- Loading initial data -->
    <div v-if="loadingInit" class="loading-spinner"></div>

    <template v-else>

      <!-- ─── Step 1: Select Target ─── -->
      <div v-if="currentStep === 1" class="wizard-body card">
        <div class="card-header"><h3>Select Migration Target</h3></div>
        <div class="card-body">

          <!-- Source VM info card -->
          <div class="source-info-card mb-3">
            <h4 class="source-info-title">Source</h4>
            <div class="source-info-grid">
              <div class="source-info-item">
                <span class="source-info-label">VM Name</span>
                <span class="source-info-value">{{ vmName }}</span>
              </div>
              <div class="source-info-item">
                <span class="source-info-label">VMID</span>
                <span class="source-info-value">{{ vmid }}</span>
              </div>
              <div class="source-info-item">
                <span class="source-info-label">Node</span>
                <span class="source-info-value">{{ node }}</span>
              </div>
              <div class="source-info-item">
                <span class="source-info-label">Host</span>
                <span class="source-info-value">{{ hostLabel }}</span>
              </div>
              <div class="source-info-item">
                <span class="source-info-label">Status</span>
                <span :class="['badge', vmStatus === 'running' ? 'badge-success' : 'badge-secondary']">
                  {{ vmStatus || 'unknown' }}
                </span>
              </div>
              <div class="source-info-item">
                <span class="source-info-label">Type</span>
                <span class="source-info-value">{{ vmType === 'lxc' ? 'LXC Container' : 'QEMU VM' }}</span>
              </div>
            </div>
          </div>

          <!-- Target node selector -->
          <div class="form-group">
            <label class="form-label">Target Node <span class="text-danger">*</span></label>
            <div v-if="loadingNodes" class="text-muted text-sm">Loading nodes...</div>
            <select
              v-else
              v-model="form.targetNode"
              class="form-control"
              @change="onTargetNodeChange"
            >
              <option value="" disabled>Select target node...</option>
              <option
                v-for="n in availableNodes"
                :key="n.node"
                :value="n.node"
              >
                {{ n.node }} ({{ n.host_label }})
              </option>
            </select>
            <div v-if="availableNodes.length === 0 && !loadingNodes" class="form-hint text-danger">
              No other nodes available in this cluster.
            </div>
          </div>

          <!-- Target storage selector -->
          <div v-if="form.targetNode" class="form-group">
            <label class="form-label">
              Target Storage
              <span v-if="loadingStorage" class="text-muted text-sm ml-1">(loading...)</span>
            </label>
            <select
              v-if="!loadingStorage"
              v-model="form.targetStorage"
              class="form-control"
            >
              <option value="">Auto / Same as source</option>
              <option
                v-for="s in targetStorages"
                :key="s.storage"
                :value="s.storage"
              >
                {{ s.storage }} ({{ s.type }})
                {{ s.avail ? ' — ' + formatBytes(s.avail) + ' free' : '' }}
              </option>
            </select>
            <div v-if="!loadingStorage && targetStorages.length === 0" class="form-hint text-muted">
              No VM-capable storage found on {{ form.targetNode }}.
            </div>
          </div>

          <!-- Online migration toggle -->
          <div v-if="vmType !== 'lxc'" class="form-group">
            <label class="form-label checkbox-label">
              <input v-model="form.online" type="checkbox" :disabled="vmStatus !== 'running'" />
              Online Migration (live — VM stays running)
            </label>
            <div v-if="vmStatus !== 'running'" class="form-hint text-muted">
              Online migration is only available when the VM is running.
            </div>
            <div v-else-if="form.online" class="form-hint">
              The VM will remain running throughout the migration. Requires shared storage or local disk migration enabled.
            </div>
            <div v-else class="form-hint text-warning">
              The VM will be <strong>stopped</strong> before migration and restarted on the target node.
            </div>
          </div>

          <!-- With local disks toggle (QEMU only, online migration) -->
          <div v-if="vmType !== 'lxc'" class="form-group">
            <label class="form-label checkbox-label">
              <input v-model="form.withLocalDisks" type="checkbox" />
              Migrate with Local Disks
            </label>
            <div class="form-hint">
              Required when the VM has disks on local (non-shared) storage. Copies disk data to the target node.
            </div>
          </div>

          <!-- Bandwidth limit -->
          <div class="form-group">
            <label class="form-label">Bandwidth Limit (MB/s)</label>
            <input
              v-model.number="form.bwlimit"
              type="number"
              min="0"
              step="10"
              class="form-control form-control-narrow"
              placeholder="0 = unlimited"
            />
            <div class="form-hint">Set to 0 for unlimited bandwidth during migration.</div>
          </div>

          <div class="wizard-actions">
            <button
              class="btn btn-primary"
              :disabled="!form.targetNode || loadingNodes"
              @click="goToReview"
            >
              Next: Review
            </button>
            <router-link :to="backLink" class="btn btn-outline">Cancel</router-link>
          </div>
        </div>
      </div>

      <!-- ─── Step 2: Review ─── -->
      <div v-if="currentStep === 2" class="wizard-body card">
        <div class="card-header"><h3>Review Migration</h3></div>
        <div class="card-body">

          <!-- Summary table -->
          <table class="summary-table mb-3">
            <tbody>
              <tr>
                <td class="summary-key">Source</td>
                <td class="summary-val">
                  <strong>{{ node }}</strong> on {{ hostLabel }}
                </td>
              </tr>
              <tr>
                <td class="summary-key">Target Node</td>
                <td class="summary-val"><strong>{{ form.targetNode }}</strong></td>
              </tr>
              <tr>
                <td class="summary-key">Target Storage</td>
                <td class="summary-val">{{ form.targetStorage || 'Auto / Same as source' }}</td>
              </tr>
              <tr>
                <td class="summary-key">Mode</td>
                <td class="summary-val">
                  <span v-if="vmType === 'lxc'">Offline (LXC)</span>
                  <span v-else-if="form.online" class="text-success">Online (live migration)</span>
                  <span v-else class="text-warning">Offline (VM will stop)</span>
                </td>
              </tr>
              <tr v-if="vmType !== 'lxc'">
                <td class="summary-key">Local Disks</td>
                <td class="summary-val">{{ form.withLocalDisks ? 'Will be migrated' : 'Not migrated (shared storage assumed)' }}</td>
              </tr>
              <tr>
                <td class="summary-key">Bandwidth Limit</td>
                <td class="summary-val">{{ form.bwlimit > 0 ? form.bwlimit + ' MB/s' : 'Unlimited' }}</td>
              </tr>
              <tr>
                <td class="summary-key">Estimated Downtime</td>
                <td class="summary-val">
                  <span v-if="vmType === 'lxc'">Full downtime (LXC must stop)</span>
                  <span v-else-if="form.online">Minimal (brief network reconnect only)</span>
                  <span v-else>Full downtime until migrated and restarted</span>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- Warnings -->
          <div v-if="reviewWarnings.length > 0" class="warnings-box mb-3">
            <div class="warnings-box__title">Warnings</div>
            <ul class="warnings-list">
              <li v-for="(w, i) in reviewWarnings" :key="i">{{ w }}</li>
            </ul>
          </div>

          <!-- Confirm checkbox -->
          <div class="form-group mb-3">
            <label class="form-label checkbox-label confirm-check">
              <input v-model="confirmed" type="checkbox" />
              I understand this will migrate {{ vmType === 'lxc' ? 'container' : 'VM' }} {{ vmid }} from
              <strong>{{ node }}</strong> to <strong>{{ form.targetNode }}</strong>
              {{ form.online && vmType !== 'lxc' ? 'while it is running' : 'with possible downtime' }}.
            </label>
          </div>

          <div class="wizard-actions">
            <button class="btn btn-outline" @click="currentStep = 1">Back</button>
            <button
              class="btn btn-primary"
              :disabled="!confirmed || submitting"
              @click="startMigration"
            >
              {{ submitting ? 'Starting...' : 'Start Migration' }}
            </button>
            <router-link :to="backLink" class="btn btn-outline">Cancel</router-link>
          </div>
        </div>
      </div>

      <!-- ─── Step 3: Progress ─── -->
      <div v-if="currentStep === 3" class="wizard-body card">
        <div class="card-header">
          <h3>Migration Progress</h3>
        </div>
        <div class="card-body">

          <!-- Status badge -->
          <div class="migration-status mb-3">
            <span v-if="migrationDone && !migrationFailed" class="badge badge-success migration-status__badge">
              Migration Complete
            </span>
            <span v-else-if="migrationFailed" class="badge badge-danger migration-status__badge">
              Migration Failed
            </span>
            <span v-else class="badge badge-info migration-status__badge">
              Migrating...
            </span>
          </div>

          <!-- Progress bar -->
          <div class="progress-bar-wrap mb-3">
            <div
              :class="['progress-bar-fill', migrationFailed ? 'progress-bar-fill--error' : migrationDone ? 'progress-bar-fill--done' : 'progress-bar-fill--active']"
              :style="{ width: progressPct + '%' }"
            ></div>
          </div>

          <!-- UPID reference -->
          <div class="text-sm text-muted mb-2" v-if="migrateUpid">
            Task: <code>{{ migrateUpid }}</code>
          </div>

          <!-- Task log output -->
          <div class="task-log-wrap">
            <div v-if="logLines.length === 0 && !migrationDone && !migrationFailed" class="text-muted text-sm">
              Waiting for task output...
            </div>
            <div v-for="(line, idx) in logLines" :key="idx" :class="['log-line', line.t === 'err' ? 'log-line--err' : '']">
              {{ line.t }}: {{ line.msg }}
            </div>
          </div>

          <!-- Error message -->
          <div v-if="migrationFailed && errorMsg" class="alert-box alert-box--error mt-3">
            {{ errorMsg }}
          </div>

          <!-- Actions -->
          <div class="wizard-actions mt-3">
            <router-link
              v-if="migrationDone || migrationFailed"
              :to="targetVmLink"
              class="btn btn-primary"
            >
              Go to VM on {{ form.targetNode }}
            </router-link>
            <router-link :to="backLink" class="btn btn-outline">
              {{ migrationDone ? 'Back to Original' : 'Cancel / Back' }}
            </router-link>
          </div>
        </div>
      </div>

    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const route = useRoute()
const router = useRouter()
const toast = useToast()

// Route params
const hostId = computed(() => route.params.hostId)
const node = computed(() => route.params.node)
const vmid = computed(() => route.params.vmid)
const vmType = computed(() => route.query.type || 'qemu')  // 'qemu' or 'lxc'

// Step management
const stepLabels = ['Select Target', 'Review', 'Progress']
const currentStep = ref(1)

// Initialization
const loadingInit = ref(true)
const loadingNodes = ref(false)
const loadingStorage = ref(false)

// VM metadata
const vmName = ref('')
const vmStatus = ref('')
const hostLabel = ref('')

// Available nodes (all nodes across this host/cluster, excluding source)
const availableNodes = ref([])

// Target storage list
const targetStorages = ref([])

// Form state
const form = ref({
  targetNode: '',
  targetStorage: '',
  online: false,
  withLocalDisks: true,
  bwlimit: 0,
})

// Review step
const confirmed = ref(false)

// Progress step
const submitting = ref(false)
const migrateUpid = ref('')
const migrationDone = ref(false)
const migrationFailed = ref(false)
const errorMsg = ref('')
const logLines = ref([])
const progressPct = ref(0)
let pollInterval = null

// Navigation links
const backLink = computed(() => {
  if (vmType.value === 'lxc') {
    return `/proxmox/${hostId.value}/nodes/${node.value}/containers/${vmid.value}`
  }
  return `/proxmox/${hostId.value}/nodes/${node.value}/vms/${vmid.value}`
})

const targetVmLink = computed(() => {
  if (vmType.value === 'lxc') {
    return `/proxmox/${hostId.value}/nodes/${form.value.targetNode}/containers/${vmid.value}`
  }
  return `/proxmox/${hostId.value}/nodes/${form.value.targetNode}/vms/${vmid.value}`
})

// Format bytes helper
const formatBytes = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let val = bytes
  let unitIdx = 0
  while (val >= 1024 && unitIdx < units.length - 1) {
    val /= 1024
    unitIdx++
  }
  return val.toFixed(1) + ' ' + units[unitIdx]
}

// Review warnings
const reviewWarnings = computed(() => {
  const warnings = []
  if (vmStatus.value === 'running' && !form.value.online && vmType.value !== 'lxc') {
    warnings.push('VM is currently running. It will be stopped for migration and restarted on the target node.')
  }
  if (vmType.value !== 'lxc' && form.value.online && !form.value.withLocalDisks) {
    warnings.push('Online migration without local disk migration may fail if the VM has disks on local (non-shared) storage.')
  }
  if (vmType.value === 'lxc') {
    warnings.push('LXC containers must be stopped for migration. There will be downtime.')
  }
  return warnings
})

// Load initial VM info
const loadVmInfo = async () => {
  try {
    let res
    if (vmType.value === 'lxc') {
      res = await api.pveNode.getContainerStatus(hostId.value, node.value, vmid.value)
    } else {
      res = await api.pveVm.getStatus(hostId.value, node.value, vmid.value)
    }
    const data = res.data || {}
    vmStatus.value = data.status || 'unknown'
    vmName.value = data.name || `${vmType.value === 'lxc' ? 'CT' : 'VM'} ${vmid.value}`

    // Set default online mode based on status
    if (vmType.value !== 'lxc') {
      form.value.online = vmStatus.value === 'running'
    }
  } catch (e) {
    console.warn('Failed to load VM status', e)
  }
}

// Load host label
const loadHostLabel = async () => {
  try {
    const res = await api.proxmox.getHost(hostId.value)
    const h = res.data || {}
    hostLabel.value = h.name || h.hostname || `Host ${hostId.value}`
  } catch (e) {
    hostLabel.value = `Host ${hostId.value}`
  }
}

// Load cluster nodes (excluding current node)
const loadClusterNodes = async () => {
  loadingNodes.value = true
  try {
    const res = await api.pveNode.clusterResources(hostId.value)
    const all = (res.data || []).filter(r => r.type === 'node' && r.node !== node.value)
    const seen = new Set()
    const nodes = []
    for (const n of all) {
      if (!seen.has(n.node)) {
        seen.add(n.node)
        nodes.push({ node: n.node, host_label: hostLabel.value })
      }
    }
    availableNodes.value = nodes
  } catch (e) {
    console.warn('Failed to load cluster nodes', e)
    availableNodes.value = []
  } finally {
    loadingNodes.value = false
  }
}

// Load storage on target node
const loadTargetStorage = async (targetNode) => {
  if (!targetNode) return
  loadingStorage.value = true
  targetStorages.value = []
  try {
    const res = await api.pveNode.listStorage(hostId.value, targetNode)
    const all = res.data || []
    const vmCapableTypes = new Set(['dir', 'lvm', 'lvmthin', 'zfspool', 'zfs', 'nfs', 'cifs', 'rbd', 'cephfs'])
    targetStorages.value = all.filter(s => vmCapableTypes.has(s.type))
  } catch (e) {
    console.warn('Failed to load target storage', e)
    targetStorages.value = []
  } finally {
    loadingStorage.value = false
  }
}

const onTargetNodeChange = async () => {
  form.value.targetStorage = ''
  if (form.value.targetNode) {
    await loadTargetStorage(form.value.targetNode)
  }
}

const goToReview = () => {
  if (!form.value.targetNode) {
    toast.error('Please select a target node')
    return
  }
  confirmed.value = false
  currentStep.value = 2
}

// Start migration
const startMigration = async () => {
  if (!confirmed.value) return
  submitting.value = true
  logLines.value = []
  progressPct.value = 0
  migrationDone.value = false
  migrationFailed.value = false
  errorMsg.value = ''

  try {
    let res
    if (vmType.value === 'lxc') {
      const payload = { target: form.value.targetNode }
      if (form.value.bwlimit > 0) payload.bwlimit = form.value.bwlimit
      if (form.value.targetStorage) payload.targetstorage = form.value.targetStorage
      res = await api.pveNode.migrateLxc(hostId.value, node.value, vmid.value, payload)
    } else {
      const payload = {
        target: form.value.targetNode,
        online: form.value.online,
        with_local_disks: form.value.withLocalDisks,
      }
      if (form.value.bwlimit > 0) payload.bwlimit = form.value.bwlimit
      if (form.value.targetStorage) payload.targetstorage = form.value.targetStorage
      res = await api.pveVm.migrate(hostId.value, node.value, vmid.value, payload)
    }

    const upid = res.data?.upid || res.data
    migrateUpid.value = typeof upid === 'string' ? upid : ''
    currentStep.value = 3
    if (migrateUpid.value) {
      startPolling()
    } else {
      // Sync response — treat as done
      migrationDone.value = true
      progressPct.value = 100
      toast.success('Migration completed')
    }
  } catch (e) {
    toast.error('Failed to start migration')
    console.error(e)
  } finally {
    submitting.value = false
  }
}

// Poll task status
const startPolling = () => {
  pollInterval = setInterval(pollTask, 2000)
  // Immediate first poll
  pollTask()
}

const pollTask = async () => {
  if (!migrateUpid.value) return
  try {
    // Poll log for output
    const logRes = await api.tasks.getLog(hostId.value, node.value, migrateUpid.value)
    const lines = logRes.data || []
    logLines.value = Array.isArray(lines) ? lines : []

    // Estimate progress from log line count (heuristic)
    const lineCount = logLines.value.length
    if (!migrationDone.value && !migrationFailed.value) {
      progressPct.value = Math.min(90, lineCount * 2)
    }

    // Poll status
    const statusRes = await api.tasks.getStatus(hostId.value, node.value, migrateUpid.value)
    const taskData = statusRes.data || {}
    const status = taskData.status || ''

    if (status === 'stopped') {
      stopPolling()
      progressPct.value = 100
      const exitStatus = taskData.exitstatus || 'OK'
      if (exitStatus === 'OK') {
        migrationDone.value = true
        toast.success('Migration completed successfully')
      } else {
        migrationFailed.value = true
        errorMsg.value = exitStatus
        toast.error('Migration failed: ' + exitStatus)
      }
    }
  } catch (e) {
    console.warn('Task poll error', e)
  }
}

const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

// Lifecycle
onMounted(async () => {
  loadingInit.value = true
  try {
    await Promise.all([loadVmInfo(), loadHostLabel()])
    await loadClusterNodes()
  } finally {
    loadingInit.value = false
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.migration-wizard-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 1rem;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.page-title {
  font-size: 1.3rem;
  font-weight: 600;
  margin: 0.25rem 0 0;
}

.back-link {
  font-size: 0.85rem;
  color: var(--text-muted, #888);
  text-decoration: none;
  display: block;
  margin-bottom: 0.25rem;
}
.back-link:hover { text-decoration: underline; }

/* Step indicator */
.wizard-steps {
  display: flex;
  align-items: center;
  gap: 0;
  margin-bottom: 1.5rem;
}

.wizard-step {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.wizard-step__circle {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  border: 2px solid var(--border-color, #333);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  font-weight: 600;
  background: var(--card-bg, #1a1a1a);
  color: var(--text-muted, #888);
  flex-shrink: 0;
  transition: all 0.2s;
}

.wizard-step--active .wizard-step__circle {
  border-color: var(--primary-color, #3b82f6);
  color: var(--primary-color, #3b82f6);
  background: rgba(59, 130, 246, 0.1);
}

.wizard-step--done .wizard-step__circle {
  border-color: var(--success-color, #10b981);
  color: white;
  background: var(--success-color, #10b981);
}

.wizard-step__label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-muted, #888);
  white-space: nowrap;
}
.wizard-step--active .wizard-step__label { color: var(--text-primary, #e0e0e0); }
.wizard-step--done .wizard-step__label { color: var(--success-color, #10b981); }

.wizard-step__connector {
  flex: 1;
  height: 2px;
  background: var(--border-color, #333);
  margin: 0 0.5rem;
}

/* Source info card */
.source-info-card {
  background: var(--bg-secondary, #111);
  border: 1px solid var(--border-color, #333);
  border-radius: 6px;
  padding: 1rem;
}

.source-info-title {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #888);
  margin: 0 0 0.75rem;
}

.source-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.5rem 1rem;
}

.source-info-item {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.source-info-label {
  font-size: 0.75rem;
  color: var(--text-muted, #888);
}

.source-info-value {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary, #e0e0e0);
}

/* Summary table */
.summary-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.summary-table tr {
  border-bottom: 1px solid var(--border-color, #222);
}
.summary-table tr:last-child { border-bottom: none; }

.summary-key {
  padding: 0.6rem 1rem 0.6rem 0;
  color: var(--text-muted, #888);
  width: 160px;
  font-weight: 500;
  vertical-align: top;
}

.summary-val {
  padding: 0.6rem 0;
  color: var(--text-primary, #e0e0e0);
}

/* Warnings */
.warnings-box {
  background: rgba(234, 179, 8, 0.08);
  border: 1px solid rgba(234, 179, 8, 0.3);
  border-radius: 6px;
  padding: 0.75rem 1rem;
}

.warnings-box__title {
  font-size: 0.8rem;
  font-weight: 600;
  color: #f59e0b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.4rem;
}

.warnings-list {
  margin: 0;
  padding-left: 1.2rem;
  color: var(--text-primary, #e0e0e0);
  font-size: 0.875rem;
}

.warnings-list li + li { margin-top: 0.25rem; }

/* Confirm checkbox */
.confirm-check {
  font-size: 0.9rem;
  color: var(--text-primary, #e0e0e0);
  gap: 0.5rem;
  align-items: flex-start;
}

/* Progress */
.migration-status {
  text-align: center;
}

.migration-status__badge {
  font-size: 1rem;
  padding: 0.4rem 1.2rem;
}

.progress-bar-wrap {
  width: 100%;
  height: 8px;
  background: var(--bg-secondary, #111);
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid var(--border-color, #333);
}

.progress-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-bar-fill--active {
  background: var(--primary-color, #3b82f6);
  animation: pulse-bar 1.5s ease-in-out infinite;
}

.progress-bar-fill--done {
  background: var(--success-color, #10b981);
}

.progress-bar-fill--error {
  background: var(--danger-color, #ef4444);
}

@keyframes pulse-bar {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* Task log */
.task-log-wrap {
  background: var(--bg-secondary, #0a0a0a);
  border: 1px solid var(--border-color, #222);
  border-radius: 4px;
  padding: 0.75rem;
  max-height: 320px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  line-height: 1.6;
}

.log-line {
  color: var(--text-primary, #ccc);
}

.log-line--err {
  color: var(--danger-color, #ef4444);
}

/* Alert box */
.alert-box {
  border-radius: 6px;
  padding: 0.75rem 1rem;
  font-size: 0.875rem;
}

.alert-box--error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
}

/* Form helpers */
.form-control-narrow {
  max-width: 180px;
}

.form-hint {
  font-size: 0.8rem;
  color: var(--text-muted, #888);
  margin-top: 0.25rem;
}

.text-warning { color: #f59e0b; }
.text-success { color: #10b981; }

/* Wizard actions */
.wizard-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1.5rem;
  flex-wrap: wrap;
}

.wizard-body {
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Badge variants (in case not global) */
.badge-success { background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
.badge-danger  { background: rgba(239, 68, 68, 0.15);  color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }
.badge-secondary { background: rgba(107, 114, 128, 0.15); color: #9ca3af; border: 1px solid rgba(107, 114, 128, 0.3); }
</style>
