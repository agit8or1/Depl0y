<template>
  <div v-if="show" class="modal" @click.self="$emit('close')">
    <div class="modal-content modal-lg">
      <div class="modal-header">
        <h3>Cluster Management Wizard</h3>
        <button @click="$emit('close')" class="btn-close">&times;</button>
      </div>

      <div class="modal-body">
        <!-- ── Mode selector ────────────────────────────────────────────── -->
        <div v-if="wizardStep === 'mode'" class="step-content">
          <p class="step-description">
            This wizard helps you configure Proxmox clustering for host <strong>{{ hostName }}</strong>.
          </p>
          <div class="mode-cards">
            <div
              class="mode-card"
              :class="{ 'mode-card-selected': selectedMode === 'create' }"
              @click="selectedMode = 'create'"
            >
              <div class="mode-card-icon">+</div>
              <div class="mode-card-title">Create New Cluster</div>
              <div class="mode-card-desc">
                Convert this standalone node into the first node of a new Proxmox cluster.
                Other nodes can join afterwards.
              </div>
            </div>
            <div
              class="mode-card"
              :class="{ 'mode-card-selected': selectedMode === 'join' }"
              @click="selectedMode = 'join'"
            >
              <div class="mode-card-icon">&#8594;</div>
              <div class="mode-card-title">Join Existing Cluster</div>
              <div class="mode-card-desc">
                Join this node to a cluster that already exists on another Proxmox host.
              </div>
            </div>
          </div>

          <div class="step-actions">
            <button
              class="btn btn-primary"
              :disabled="!selectedMode"
              @click="goToStep(selectedMode === 'create' ? 'create-name' : 'join-master')"
            >
              Next
            </button>
            <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
          </div>
        </div>

        <!-- ── Create: cluster name ────────────────────────────────────── -->
        <div v-if="wizardStep === 'create-name'" class="step-content">
          <div class="step-header">
            <span class="step-badge">Create Cluster</span>
            <span class="step-number">Step 1 of 2</span>
          </div>
          <h4>Name Your Cluster</h4>
          <p class="step-description">
            Choose a name for the new Proxmox cluster. This name is permanent and used for corosync communication.
          </p>
          <div class="form-group">
            <label class="form-label">Cluster Name <span class="required">*</span></label>
            <input
              v-model="createClusterName"
              class="form-control"
              placeholder="e.g. pve-cluster"
              maxlength="15"
              pattern="[a-zA-Z0-9\-]+"
              title="Alphanumeric and hyphens only, max 15 chars"
              @input="validateClusterName"
            />
            <p class="field-hint">1–15 characters: letters, numbers, and hyphens only.</p>
            <p v-if="nameError" class="field-error">{{ nameError }}</p>
          </div>

          <div class="step-actions">
            <button class="btn btn-primary" :disabled="!createClusterName || !!nameError" @click="goToStep('create-confirm')">
              Next
            </button>
            <button class="btn btn-outline" @click="goToStep('mode')">Back</button>
          </div>
        </div>

        <!-- ── Create: confirm ─────────────────────────────────────────── -->
        <div v-if="wizardStep === 'create-confirm'" class="step-content">
          <div class="step-header">
            <span class="step-badge">Create Cluster</span>
            <span class="step-number">Step 2 of 2</span>
          </div>
          <h4>Confirm Cluster Creation</h4>

          <div class="confirm-box">
            <div class="confirm-row">
              <span class="confirm-label">Cluster Name</span>
              <span class="confirm-value">{{ createClusterName }}</span>
            </div>
            <div class="confirm-row">
              <span class="confirm-label">Host</span>
              <span class="confirm-value">{{ hostName }}</span>
            </div>
          </div>

          <div class="warning-box">
            <strong>Warning:</strong> Creating a cluster will restart corosync and pve-cluster services.
            This may briefly interrupt Proxmox management operations on this node.
          </div>

          <div v-if="operationResult" :class="['result-box', operationResult.success ? 'result-success' : 'result-error']">
            {{ operationResult.message }}
          </div>

          <div class="step-actions">
            <button
              class="btn btn-primary"
              :disabled="creating || !!operationResult?.success"
              @click="doCreateCluster"
            >
              {{ creating ? 'Creating...' : 'Create Cluster' }}
            </button>
            <button class="btn btn-outline" :disabled="creating" @click="goToStep('create-name')">Back</button>
          </div>
        </div>

        <!-- ── Join: enter master IP ───────────────────────────────────── -->
        <div v-if="wizardStep === 'join-master'" class="step-content">
          <div class="step-header">
            <span class="step-badge">Join Cluster</span>
            <span class="step-number">Step 1 of 4</span>
          </div>
          <h4>Master Node Address</h4>
          <p class="step-description">
            Enter the IP address or hostname of an existing cluster member (the master node).
          </p>
          <div class="form-group">
            <label class="form-label">Master Node IP / Hostname <span class="required">*</span></label>
            <input
              v-model="joinMasterIp"
              class="form-control"
              placeholder="192.168.1.10 or pve1.example.com"
            />
          </div>

          <div class="divider">
            <span>Authentication</span>
          </div>

          <div class="join-auth-toggle">
            <button
              :class="['auth-tab', joinAuthMode === 'password' ? 'auth-tab-active' : '']"
              @click="joinAuthMode = 'password'"
            >
              Root Password (auto-fetch)
            </button>
            <button
              :class="['auth-tab', joinAuthMode === 'manual' ? 'auth-tab-active' : '']"
              @click="joinAuthMode = 'manual'"
            >
              Manual Entry
            </button>
          </div>

          <div v-if="joinAuthMode === 'password'" class="form-group mt-sm">
            <label class="form-label">Root Password of Master Node <span class="required">*</span></label>
            <input
              v-model="joinMasterPassword"
              type="password"
              class="form-control"
              placeholder="root password for the master node"
            />
            <p class="field-hint">
              Used to retrieve join information via the Proxmox API. Not stored.
            </p>
          </div>

          <div v-if="joinAuthMode === 'manual'" class="manual-fields">
            <div class="form-group">
              <label class="form-label">TLS Fingerprint <span class="required">*</span></label>
              <input v-model="joinFingerprint" class="form-control" placeholder="SHA-256 fingerprint" />
            </div>
            <div class="form-group">
              <label class="form-label">Corosync Link Address</label>
              <input v-model="joinLink0" class="form-control" placeholder="Optional corosync link IP" />
            </div>
          </div>

          <div class="step-actions">
            <button
              class="btn btn-primary"
              :disabled="!joinMasterIp || (joinAuthMode === 'password' && !joinMasterPassword)"
              @click="fetchJoinInfo"
            >
              {{ fetchingJoinInfo ? 'Fetching...' : 'Next' }}
            </button>
            <button class="btn btn-outline" @click="goToStep('mode')">Back</button>
          </div>
        </div>

        <!-- ── Join: show detected info ────────────────────────────────── -->
        <div v-if="wizardStep === 'join-info'" class="step-content">
          <div class="step-header">
            <span class="step-badge">Join Cluster</span>
            <span class="step-number">Step 2 of 4</span>
          </div>
          <h4>Detected Cluster Information</h4>

          <div v-if="detectedClusterInfo" class="confirm-box">
            <div class="confirm-row">
              <span class="confirm-label">Cluster Name</span>
              <span class="confirm-value">{{ detectedClusterInfo.config?.cluster_name || detectedClusterInfo.totem?.cluster_name || '—' }}</span>
            </div>
            <div class="confirm-row">
              <span class="confirm-label">Master Node</span>
              <span class="confirm-value">{{ joinMasterIp }}</span>
            </div>
            <div v-if="detectedClusterInfo.nodelist && detectedClusterInfo.nodelist.length" class="confirm-row">
              <span class="confirm-label">Existing Nodes</span>
              <div class="confirm-value">
                <span
                  v-for="n in detectedClusterInfo.nodelist"
                  :key="n.name || n.ring0_addr"
                  class="node-chip"
                >
                  {{ n.name || n.ring0_addr }}
                </span>
              </div>
            </div>
            <div class="confirm-row">
              <span class="confirm-label">Fingerprint</span>
              <span class="confirm-value fingerprint">{{ detectedClusterInfo.fingerprint || joinFingerprint || '—' }}</span>
            </div>
          </div>

          <div v-if="joinInfoError" class="result-box result-error">
            {{ joinInfoError }}
            <br />
            <small>You can still proceed using manual entry.</small>
          </div>

          <div class="step-actions">
            <button class="btn btn-primary" @click="goToStep('join-confirm')">Looks Good — Next</button>
            <button class="btn btn-outline" @click="goToStep('join-master')">Back</button>
          </div>
        </div>

        <!-- ── Join: confirm ───────────────────────────────────────────── -->
        <div v-if="wizardStep === 'join-confirm'" class="step-content">
          <div class="step-header">
            <span class="step-badge">Join Cluster</span>
            <span class="step-number">Step 3 of 4</span>
          </div>
          <h4>Confirm — Join Cluster</h4>

          <div class="confirm-box">
            <div class="confirm-row">
              <span class="confirm-label">This Node</span>
              <span class="confirm-value">{{ hostName }}</span>
            </div>
            <div class="confirm-row">
              <span class="confirm-label">Master Node</span>
              <span class="confirm-value">{{ joinMasterIp }}</span>
            </div>
            <div v-if="joinFingerprint" class="confirm-row">
              <span class="confirm-label">Fingerprint</span>
              <span class="confirm-value fingerprint">{{ joinFingerprint }}</span>
            </div>
          </div>

          <div class="warning-box">
            <strong>Warning:</strong> Joining a cluster will restart <code>pve-cluster</code> and <code>corosync</code> services
            on this node. This operation takes approximately 30 seconds and will briefly interrupt management operations.
            Ensure no critical operations are running.
          </div>

          <div v-if="joinProgress" class="progress-box">
            <div class="progress-spinner"></div>
            <span>{{ joinProgress }}</span>
          </div>

          <div v-if="operationResult" :class="['result-box', operationResult.success ? 'result-success' : 'result-error']">
            {{ operationResult.message }}
          </div>

          <div class="step-actions">
            <button
              class="btn btn-primary btn-danger-confirm"
              :disabled="joining || !!operationResult?.success"
              @click="doJoinCluster"
            >
              {{ joining ? 'Joining...' : 'Join Cluster' }}
            </button>
            <button class="btn btn-outline" :disabled="joining" @click="goToStep('join-info')">Back</button>
          </div>
        </div>

        <!-- ── Join: verifying ─────────────────────────────────────────── -->
        <div v-if="wizardStep === 'join-verifying'" class="step-content">
          <div class="step-header">
            <span class="step-badge">Join Cluster</span>
            <span class="step-number">Step 4 of 4</span>
          </div>
          <h4>Verifying Cluster Join</h4>
          <p class="step-description">Waiting for this node to appear in the cluster...</p>

          <div v-if="!joinVerified && !joinVerifyFailed" class="progress-box">
            <div class="progress-spinner"></div>
            <span>Polling cluster status (attempt {{ verifyAttempts }} / {{ MAX_VERIFY_ATTEMPTS }})...</span>
          </div>

          <div v-if="joinVerified" class="result-box result-success">
            Node successfully joined the cluster! The node is now visible to all cluster members.
          </div>

          <div v-if="joinVerifyFailed" class="result-box result-error">
            Node not yet visible in the cluster after {{ MAX_VERIFY_ATTEMPTS }} attempts.
            Check that the join command completed successfully on the node and try refreshing manually.
          </div>

          <div class="step-actions">
            <button class="btn btn-primary" @click="$emit('close'); $emit('refreshCluster')">
              {{ joinVerified ? 'Done' : 'Close' }}
            </button>
            <button v-if="joinVerifyFailed" class="btn btn-outline" @click="startVerification">Retry</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const toast = useToast()

const props = defineProps({
  show: Boolean,
  hostId: [Number, String],
  hostName: String,
})

const emit = defineEmits(['close', 'refreshCluster'])

// ── Wizard state ──────────────────────────────────────────────────────────────
const wizardStep = ref('mode')
const selectedMode = ref('')

// Create cluster
const createClusterName = ref('')
const nameError = ref('')
const creating = ref(false)

// Join cluster
const joinMasterIp = ref('')
const joinMasterPassword = ref('')
const joinAuthMode = ref('password')  // 'password' | 'manual'
const joinFingerprint = ref('')
const joinLink0 = ref('')
const fetchingJoinInfo = ref(false)
const joinInfoError = ref('')
const detectedClusterInfo = ref(null)
const joining = ref(false)
const joinProgress = ref('')

// Verify
const joinVerified = ref(false)
const joinVerifyFailed = ref(false)
const verifyAttempts = ref(0)
const MAX_VERIFY_ATTEMPTS = 20
let verifyTimer = null

// Shared
const operationResult = ref(null)

// ── Navigation ────────────────────────────────────────────────────────────────
const goToStep = (step) => {
  wizardStep.value = step
  operationResult.value = null
  joinProgress.value = ''
}

// Reset when modal opens
watch(() => props.show, (val) => {
  if (val) {
    wizardStep.value = 'mode'
    selectedMode.value = ''
    createClusterName.value = ''
    nameError.value = ''
    creating.value = false
    joinMasterIp.value = ''
    joinMasterPassword.value = ''
    joinAuthMode.value = 'password'
    joinFingerprint.value = ''
    joinLink0.value = ''
    fetchingJoinInfo.value = false
    joinInfoError.value = ''
    detectedClusterInfo.value = null
    joining.value = false
    joinProgress.value = ''
    joinVerified.value = false
    joinVerifyFailed.value = false
    verifyAttempts.value = 0
    operationResult.value = null
    clearVerifyTimer()
  } else {
    clearVerifyTimer()
  }
})

const clearVerifyTimer = () => {
  if (verifyTimer) {
    clearInterval(verifyTimer)
    verifyTimer = null
  }
}

// ── Validation ────────────────────────────────────────────────────────────────
const validateClusterName = () => {
  const val = createClusterName.value
  if (!val) {
    nameError.value = ''
    return
  }
  if (val.length > 15) {
    nameError.value = 'Max 15 characters'
    return
  }
  if (!/^[a-zA-Z0-9\-]+$/.test(val)) {
    nameError.value = 'Only letters, numbers, and hyphens allowed'
    return
  }
  nameError.value = ''
}

// ── Create cluster ────────────────────────────────────────────────────────────
const doCreateCluster = async () => {
  creating.value = true
  operationResult.value = null
  try {
    await api.cluster.createCluster(props.hostId, { clustername: createClusterName.value })
    operationResult.value = {
      success: true,
      message: `Cluster "${createClusterName.value}" created successfully. Corosync services are restarting.`,
    }
    toast.success(`Cluster "${createClusterName.value}" created`)
    emit('refreshCluster')
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || 'Failed to create cluster'
    operationResult.value = { success: false, message: msg }
  } finally {
    creating.value = false
  }
}

// ── Fetch join info ───────────────────────────────────────────────────────────
const fetchJoinInfo = async () => {
  if (joinAuthMode.value === 'manual') {
    // Skip fetch, go directly to info step
    detectedClusterInfo.value = null
    goToStep('join-info')
    return
  }

  fetchingJoinInfo.value = true
  joinInfoError.value = ''
  detectedClusterInfo.value = null

  try {
    // Use the master node's API to get join info by calling our backend with the master's credentials
    // We query the cluster/config/join endpoint on the target host_id
    // The host_id here is the NODE WE WANT TO JOIN (not the master)
    // We pass hostname + password to the backend which calls the master
    const res = await api.cluster.getJoinInfo(props.hostId)
    detectedClusterInfo.value = res.data

    // Extract fingerprint if present
    if (res.data?.fingerprint) {
      joinFingerprint.value = res.data.fingerprint
    }

    goToStep('join-info')
  } catch (err) {
    // If we can't fetch join info, show what we have and let the user proceed
    joinInfoError.value = err.response?.data?.detail || 'Could not retrieve join info automatically. You can still proceed.'
    goToStep('join-info')
  } finally {
    fetchingJoinInfo.value = false
  }
}

// ── Join cluster ──────────────────────────────────────────────────────────────
const doJoinCluster = async () => {
  joining.value = true
  operationResult.value = null
  joinProgress.value = 'Sending join request to Proxmox...'

  try {
    const payload = {
      hostname: joinMasterIp.value,
      password: joinMasterPassword.value,
    }
    if (joinFingerprint.value) payload.fingerprint = joinFingerprint.value
    if (joinLink0.value) payload.link0 = joinLink0.value

    await api.cluster.joinCluster(props.hostId, payload)

    joinProgress.value = 'Join command sent. Cluster services are restarting...'
    toast.info('Join request submitted — verifying...')

    // Move to verification step
    goToStep('join-verifying')
    startVerification()
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || 'Failed to join cluster'
    operationResult.value = { success: false, message: msg }
    joinProgress.value = ''
  } finally {
    joining.value = false
  }
}

// ── Verification ──────────────────────────────────────────────────────────────
const startVerification = () => {
  clearVerifyTimer()
  joinVerified.value = false
  joinVerifyFailed.value = false
  verifyAttempts.value = 0

  verifyTimer = setInterval(async () => {
    verifyAttempts.value++
    try {
      const res = await api.cluster.getClusterStatus(props.hostId)
      const nodes = res.data?.nodes || []
      // If the cluster now has >1 node, join likely succeeded
      if (nodes.length > 1 || res.data?.node_count > 1) {
        joinVerified.value = true
        clearVerifyTimer()
        toast.success('Node successfully joined the cluster!')
        emit('refreshCluster')
        return
      }
    } catch {
      // Cluster service may be restarting — silently retry
    }

    if (verifyAttempts.value >= MAX_VERIFY_ATTEMPTS) {
      joinVerifyFailed.value = true
      clearVerifyTimer()
    }
  }, 5000)
}
</script>

<style scoped>
/* ── Modal ── */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.modal-content {
  background: var(--bg-card, #1e2130);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.5rem;
  width: 90%;
  max-width: 620px;
  max-height: 92vh;
  overflow-y: auto;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.55);
}

.modal-lg {
  max-width: 680px;
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

.btn-close:hover { color: var(--text-primary); }

.modal-body {
  padding: 1.5rem;
}

/* ── Step content ── */
.step-content {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.step-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.step-badge {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.step-number {
  font-size: 0.8rem;
  color: var(--text-muted, #6b7280);
}

.step-content h4 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-primary);
}

.step-description {
  color: var(--text-secondary, #9ca3af);
  font-size: 0.9rem;
  margin: 0;
  line-height: 1.5;
}

/* ── Mode cards ── */
.mode-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.mode-card {
  border: 2px solid var(--border-color, #2d3348);
  border-radius: 0.5rem;
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  background: var(--bg-secondary, #151824);
}

.mode-card:hover {
  border-color: #3b82f6;
}

.mode-card-selected {
  border-color: #3b82f6 !important;
  background: rgba(59, 130, 246, 0.08) !important;
}

.mode-card-icon {
  font-size: 1.5rem;
  color: #60a5fa;
  font-weight: 700;
  line-height: 1;
}

.mode-card-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.mode-card-desc {
  font-size: 0.8rem;
  color: var(--text-muted, #6b7280);
  line-height: 1.45;
}

/* ── Auth toggle ── */
.join-auth-toggle {
  display: flex;
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
  overflow: hidden;
}

.auth-tab {
  flex: 1;
  padding: 0.5rem 0.75rem;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--text-muted, #6b7280);
  transition: all 0.15s;
}

.auth-tab:hover { color: var(--text-primary); background: var(--bg-hover, rgba(255,255,255,0.04)); }

.auth-tab-active {
  background: rgba(59, 130, 246, 0.15) !important;
  color: #60a5fa !important;
  font-weight: 500;
}

/* ── Confirm box ── */
.confirm-box {
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
  overflow: hidden;
}

.confirm-row {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 0.625rem 1rem;
  border-bottom: 1px solid var(--border-color, #2d3348);
}

.confirm-row:last-child { border-bottom: none; }

.confirm-label {
  width: 130px;
  flex-shrink: 0;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #6b7280);
  padding-top: 2px;
}

.confirm-value {
  font-size: 0.9rem;
  color: var(--text-primary);
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.confirm-value.fingerprint {
  font-family: monospace;
  font-size: 0.78rem;
  word-break: break-all;
  color: var(--text-secondary, #9ca3af);
}

/* ── Node chips ── */
.node-chip {
  display: inline-flex;
  align-items: center;
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 0.25rem;
  padding: 0.15rem 0.45rem;
  font-size: 0.78rem;
  font-weight: 500;
}

/* ── Warnings / results ── */
.warning-box {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 0.375rem;
  padding: 0.875rem 1rem;
  font-size: 0.875rem;
  color: #fbbf24;
  line-height: 1.5;
}

.warning-box code {
  background: rgba(245, 158, 11, 0.15);
  padding: 0.1rem 0.3rem;
  border-radius: 0.2rem;
  font-family: monospace;
}

.result-box {
  padding: 0.875rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.9rem;
  line-height: 1.5;
}

.result-success {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #34d399;
}

.result-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
}

/* ── Progress ── */
.progress-box {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  background: var(--bg-secondary, #151824);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  color: var(--text-secondary, #9ca3af);
}

.progress-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-color, #2d3348);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Forms ── */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary, #9ca3af);
}

.required { color: #f87171; }

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

.form-control:focus { border-color: #3b82f6; }

.field-hint {
  font-size: 0.78rem;
  color: var(--text-muted, #6b7280);
  margin: 0;
}

.field-error {
  font-size: 0.78rem;
  color: #f87171;
  margin: 0;
}

.manual-fields {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

/* ── Divider ── */
.divider {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--text-muted, #6b7280);
  font-size: 0.78rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-color, #2d3348);
}

/* ── Step actions ── */
.step-actions {
  display: flex;
  gap: 0.75rem;
  padding-top: 0.25rem;
}

/* ── Buttons ── */
.btn {
  padding: 0.5rem 1.125rem;
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

.btn-primary:hover:not(:disabled) { background: #2563eb; }

.btn-danger-confirm {
  background: #ef4444 !important;
  color: #fff !important;
}

.btn-danger-confirm:hover:not(:disabled) { background: #dc2626 !important; }

.btn-outline {
  background: transparent;
  color: var(--text-secondary, #9ca3af);
  border: 1px solid var(--border-color, #3d4568);
}

.btn-outline:hover:not(:disabled) {
  background: var(--bg-hover, rgba(255, 255, 255, 0.05));
}

/* ── Utilities ── */
.mt-sm { margin-top: 0.5rem; }

@media (max-width: 540px) {
  .mode-cards { grid-template-columns: 1fr; }
  .modal-content { width: 97%; }
}
</style>
