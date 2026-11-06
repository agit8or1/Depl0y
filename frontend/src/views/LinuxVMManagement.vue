<template>
  <div class="linux-vm-page">
    <div class="page-header">
      <h2>Linux VM Security</h2>
      <p class="text-muted">Push agents running on managed Linux VMs</p>
    </div>

    <!-- Enroll a VM: one-time install command bound to the chosen VM -->
    <div class="card">
      <div class="card-header">
        <h3>Enroll a VM</h3>
      </div>
      <div class="enroll-body">
        <p class="text-muted text-sm">
          Creates a single-use install command for one VM. It stops working once used, when it
          expires, or when you revoke it, and the agent is always tied to the VM you pick here.
        </p>
        <div class="enroll-form">
          <select v-model="enrollVmId" class="form-control">
            <option :value="null" disabled>Choose a VM…</option>
            <option v-for="vm in vms" :key="vm.id" :value="vm.id">{{ vm.name }}<template v-if="vm.ip_address"> ({{ vm.ip_address }})</template></option>
          </select>
          <select v-model.number="enrollTtl" class="form-control ttl">
            <option :value="15">Valid 15 min</option>
            <option :value="60">Valid 1 hour</option>
            <option :value="240">Valid 4 hours</option>
            <option :value="1440">Valid 24 hours</option>
          </select>
          <button class="btn btn-primary" :disabled="!enrollVmId || enrolling" @click="createEnrollment">
            {{ enrolling ? 'Creating…' : 'Create install command' }}
          </button>
        </div>
        <div v-if="newEnrollment" class="enroll-result">
          <p class="text-sm">
            Run this as root on <strong>{{ newEnrollment.vm_name }}</strong> before
            {{ formatDate(newEnrollment.expires_at + 'Z') }}. It is shown only once.
          </p>
          <div class="command-box">
            <code>{{ newEnrollment.install_command }}</code>
            <button class="btn btn-outline btn-sm" @click="copyText(newEnrollment.install_command)">Copy</button>
          </div>
        </div>
        <div v-if="pendingEnrollments.length" class="pending-list">
          <p class="text-sm"><strong>Unused install commands</strong></p>
          <ul>
            <li v-for="e in pendingEnrollments" :key="e.id" class="text-sm">
              {{ e.vm_name || `VM ${e.vm_id}` }}, expires {{ formatDate(e.expires_at + 'Z') }}
              <button class="btn btn-outline btn-sm" @click="revokeEnrollment(e)">Revoke</button>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-card card">
      <div class="loading-spinner"></div>
      <p>Loading agents...</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="agents.length === 0" class="card empty-state">
      <div class="empty-icon">🛡️</div>
      <h3>No Agents Registered</h3>
      <p class="text-muted">Install the Depl0y agent on a Linux VM to start receiving scan results.</p>
      <div class="info-box" style="margin-top: 1.5rem; text-align: left;">
        <p><strong>To install the agent on a VM:</strong></p>
        <ol class="text-sm" style="margin: 0.5rem 0 0 1.5rem;">
          <li>Choose the VM under <em>Enroll a VM</em> above and create an install command</li>
          <li>Run the command on that VM as root before it expires</li>
          <li>The agent registers itself and appears here</li>
        </ol>
      </div>
    </div>

    <!-- Agents table -->
    <div v-else class="card">
      <div class="card-header">
        <h3>Registered Agents ({{ agents.length }})</h3>
        <button @click="fetchAgents" class="btn btn-outline" :disabled="loading">
          Refresh
        </button>
      </div>

      <div class="agents-table-wrapper">
        <table class="agents-table">
          <thead>
            <tr>
              <th>Hostname</th>
              <th>OS</th>
              <th>Agent Version</th>
              <th>Status</th>
              <th>Last Seen</th>
              <th>Scans</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="agent in agents" :key="agent.id">
              <tr
                class="agent-row"
                :class="{ 'row-expanded': expandedAgent === agent.id }"
                @click="toggleExpand(agent.id)"
              >
                <td>
                  <strong>{{ agent.hostname || 'Unknown' }}</strong>
                </td>
                <td class="text-sm text-muted">{{ agent.os_info || '—' }}</td>
                <td class="text-sm">{{ agent.agent_version || '—' }}</td>
                <td>
                  <span :class="['badge', getStatusBadge(agent)]">
                    {{ getStatusLabel(agent) }}
                  </span>
                </td>
                <td class="text-sm text-muted">{{ formatDate(agent.last_seen) }}</td>
                <td class="text-sm">{{ agent.scan_count }}</td>
                <td @click.stop>
                  <div class="action-btns">
                    <button
                      @click="showInstallModal(agent)"
                      class="btn btn-sm btn-outline"
                      title="Install command"
                    >
                      Install
                    </button>
                    <button
                      @click="confirmDelete(agent)"
                      class="btn btn-sm btn-danger"
                      title="Remove agent"
                    >
                      Remove
                    </button>
                  </div>
                </td>
              </tr>

              <!-- Expanded scan results -->
              <tr v-if="expandedAgent === agent.id" class="scan-row">
                <td colspan="7">
                  <div class="scan-panel">
                    <div v-if="scansLoading[agent.id]" class="scan-loading">
                      <div class="loading-spinner"></div>
                      <span>Loading scans...</span>
                    </div>
                    <div v-else-if="!scans[agent.id] || scans[agent.id].length === 0" class="scan-empty">
                      No scan results yet.
                    </div>
                    <div v-else class="scan-results">
                      <div
                        v-for="scan in scans[agent.id]"
                        :key="scan.id"
                        :class="['scan-item', `scan-${scan.severity}`]"
                      >
                        <div class="scan-item-header">
                          <span :class="['badge', getSeverityBadge(scan.severity)]">
                            {{ scan.severity.toUpperCase() }}
                          </span>
                          <span class="scan-type">{{ formatScanType(scan.scan_type) }}</span>
                          <span class="scan-status badge badge-secondary">{{ scan.status }}</span>
                          <span class="scan-date text-sm text-muted">{{ formatDate(scan.scanned_at) }}</span>
                        </div>
                        <p v-if="scan.summary" class="scan-summary">{{ scan.summary }}</p>
                        <details v-if="scan.result_json" class="scan-details">
                          <summary class="text-sm">Raw results</summary>
                          <pre class="scan-json">{{ formatJson(scan.result_json) }}</pre>
                        </details>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Install Command Modal -->
    <div v-if="installModal.show" class="modal" @click="installModal.show = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Install Agent on {{ installModal.hostname }}</h3>
          <button @click="installModal.show = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p class="text-sm text-muted">Run this command as <strong>root</strong> on the target VM:</p>
          <div class="command-box">
            <code>{{ installModal.command }}</code>
            <button @click="copyInstallCommand" class="btn btn-sm btn-outline">
              {{ commandCopied ? 'Copied!' : 'Copy' }}
            </button>
          </div>
          <div class="info-box" style="margin-top: 1rem;">
            <p class="text-sm">The install script will:</p>
            <ul class="text-sm" style="margin: 0.5rem 0 0 1.5rem;">
              <li>Create <code>/opt/depl0y-agent/agent.py</code></li>
              <li>Install a systemd timer to run every 12 hours</li>
              <li>Run an initial scan immediately</li>
            </ul>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="installModal.show = false" class="btn btn-primary">Close</button>
        </div>
      </div>
    </div>

    <!-- Delete Confirm Modal -->
    <div v-if="deleteModal.show" class="modal" @click="deleteModal.show = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Remove Agent</h3>
          <button @click="deleteModal.show = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p>Remove agent registration for <strong>{{ deleteModal.hostname }}</strong>?</p>
          <p class="text-sm text-muted">
            This deletes all scan history. The agent service on the VM will no longer be able to report results.
          </p>
        </div>
        <div class="modal-footer">
          <button @click="deleteModal.show = false" class="btn btn-outline">Cancel</button>
          <button @click="deleteAgent" class="btn btn-danger" :disabled="deleteModal.loading">
            {{ deleteModal.loading ? 'Removing...' : 'Remove' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'LinuxVMManagement',
  setup() {
    const toast = useToast()
    const loading = ref(false)
    const agents = ref([])
    const expandedAgent = ref(null)
    const scans = ref({})
    const scansLoading = ref({})
    const commandCopied = ref(false)

    const installModal = ref({ show: false, command: '', hostname: '', agentId: null })
    const deleteModal = ref({ show: false, agentId: null, hostname: '', loading: false })

    const vms = ref([])
    const enrollVmId = ref(null)
    const enrollTtl = ref(60)
    const enrolling = ref(false)
    const newEnrollment = ref(null)
    const enrollments = ref([])
    const pendingEnrollments = computed(() => enrollments.value.filter(e => e.status === 'pending'))

    const fetchEnrollments = async () => {
      try {
        enrollments.value = (await api.vmAgent.listEnrollments()).data
      } catch { /* list is optional */ }
    }

    const fetchVms = async () => {
      try {
        // depl0y-managed VMs: enrollment binds to the depl0y VM record, not a Proxmox vmid.
        vms.value = (await api.vms.listManaged()).data
      } catch {
        vms.value = []
      }
    }

    const createEnrollment = async () => {
      enrolling.value = true
      try {
        newEnrollment.value = (await api.vmAgent.createEnrollment(enrollVmId.value, enrollTtl.value)).data
        await fetchEnrollments()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to create install command')
      } finally {
        enrolling.value = false
      }
    }

    const revokeEnrollment = async (e) => {
      try {
        await api.vmAgent.revokeEnrollment(e.id)
        if (newEnrollment.value?.id === e.id) newEnrollment.value = null
        await fetchEnrollments()
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Failed to revoke')
      }
    }

    const copyText = (text) => {
      navigator.clipboard.writeText(text)
      toast.success('Copied to clipboard')
    }

    const fetchAgents = async () => {
      loading.value = true
      try {
        const response = await api.vmAgent.list()
        agents.value = response.data
      } catch (error) {
        toast.error('Failed to load agents')
      } finally {
        loading.value = false
      }
    }

    const toggleExpand = async (agentId) => {
      if (expandedAgent.value === agentId) {
        expandedAgent.value = null
        return
      }
      expandedAgent.value = agentId
      if (!scans.value[agentId]) {
        scansLoading.value[agentId] = true
        try {
          const response = await api.vmAgent.getScans(agentId)
          scans.value[agentId] = response.data
        } catch {
          scans.value[agentId] = []
        } finally {
          scansLoading.value[agentId] = false
        }
      }
    }

    const showInstallModal = async (agent) => {
      try {
        const response = await api.vmAgent.getInstallCommand(agent.id)
        installModal.value = {
          show: true,
          command: response.data.command,
          hostname: agent.hostname || 'VM',
          agentId: agent.id
        }
      } catch {
        toast.error('Failed to get install command')
      }
    }

    const copyInstallCommand = () => {
      navigator.clipboard.writeText(installModal.value.command)
      commandCopied.value = true
      toast.success('Copied to clipboard')
      setTimeout(() => { commandCopied.value = false }, 2000)
    }

    const confirmDelete = (agent) => {
      deleteModal.value = {
        show: true,
        agentId: agent.id,
        hostname: agent.hostname || 'Unknown',
        loading: false
      }
    }

    const deleteAgent = async () => {
      deleteModal.value.loading = true
      try {
        await api.vmAgent.delete(deleteModal.value.agentId)
        toast.success('Agent removed')
        deleteModal.value.show = false
        agents.value = agents.value.filter(a => a.id !== deleteModal.value.agentId)
        if (expandedAgent.value === deleteModal.value.agentId) {
          expandedAgent.value = null
        }
      } catch {
        toast.error('Failed to remove agent')
      } finally {
        deleteModal.value.loading = false
      }
    }

    const getStatusBadge = (agent) => {
      if (!agent.last_seen) return 'badge-secondary'
      const diff = Date.now() - new Date(agent.last_seen).getTime()
      return diff < 13 * 60 * 60 * 1000 ? 'badge-success' : 'badge-warning'
    }

    const getStatusLabel = (agent) => {
      if (!agent.last_seen) return 'Never seen'
      const diff = Date.now() - new Date(agent.last_seen).getTime()
      return diff < 13 * 60 * 60 * 1000 ? 'Online' : 'Offline'
    }

    const getSeverityBadge = (severity) => {
      return { info: 'badge-info', warning: 'badge-warning', critical: 'badge-danger' }[severity] || 'badge-secondary'
    }

    const formatScanType = (type) => {
      return { os_updates: 'OS Updates', security: 'Security', dependencies: 'Dependencies', ai_analysis: 'AI Analysis' }[type] || type
    }

    const formatDate = (dt) => {
      if (!dt) return 'Never'
      return new Date(dt).toLocaleString()
    }

    const formatJson = (jsonStr) => {
      try { return JSON.stringify(JSON.parse(jsonStr), null, 2) } catch { return jsonStr }
    }

    onMounted(() => {
      fetchAgents()
      fetchVms()
      fetchEnrollments()
    })

    return {
      loading, agents, expandedAgent, scans, scansLoading, commandCopied,
      installModal, deleteModal,
      fetchAgents, toggleExpand, showInstallModal, copyInstallCommand,
      confirmDelete, deleteAgent,
      vms, enrollVmId, enrollTtl, enrolling, newEnrollment, pendingEnrollments,
      createEnrollment, revokeEnrollment, copyText,
      getStatusBadge, getStatusLabel, getSeverityBadge,
      formatScanType, formatDate, formatJson
    }
  }
}
</script>

<style scoped>
.enroll-body { padding: 1rem 1.25rem; display: flex; flex-direction: column; gap: 0.75rem; }
.enroll-form { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.enroll-form select { min-width: 14rem; max-width: 100%; }
.enroll-form .ttl { min-width: 9rem; }
.enroll-result .command-box { display: flex; gap: 0.5rem; align-items: flex-start; }
.enroll-result code { flex: 1; word-break: break-all; padding: 0.5rem; background: var(--bg-secondary, #f3f4f6); border-radius: 4px; font-size: 0.8rem; }
.pending-list ul { margin: 0.25rem 0 0 1.25rem; display: flex; flex-direction: column; gap: 0.25rem; }
.linux-vm-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
}

.loading-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 2rem;
}

.empty-state {
  text-align: center;
  padding: 3rem 2rem;
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.agents-table-wrapper {
  overflow-x: auto;
}

.agents-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.agents-table th {
  text-align: left;
  padding: 0.75rem 1rem;
  background: var(--background);
  border-bottom: 2px solid var(--border-color);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.agents-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: middle;
}

.agent-row {
  cursor: pointer;
  transition: background 0.15s;
}

.agent-row:hover {
  background: var(--background);
}

.row-expanded {
  background: rgba(59, 130, 246, 0.05);
}

.scan-row td {
  padding: 0;
  border-bottom: 2px solid var(--border-color);
}

.scan-panel {
  padding: 1.25rem 1.5rem;
  background: var(--background);
}

.scan-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 0;
}

.scan-empty {
  padding: 1rem 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.scan-results {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.scan-item {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  background: white;
}

.scan-item.scan-warning {
  border-left: 4px solid #f59e0b;
}

.scan-item.scan-critical {
  border-left: 4px solid #ef4444;
}

.scan-item.scan-info {
  border-left: 4px solid #3b82f6;
}

.scan-item-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.scan-type {
  font-weight: 600;
  font-size: 0.9rem;
}

.scan-date {
  margin-left: auto;
}

.scan-summary {
  margin: 0.25rem 0 0.5rem 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.scan-details {
  margin-top: 0.5rem;
}

.scan-details summary {
  cursor: pointer;
  color: var(--primary-color);
}

.scan-json {
  margin: 0.5rem 0 0 0;
  padding: 0.75rem;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 0.375rem;
  font-size: 0.8rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.action-btns {
  display: flex;
  gap: 0.5rem;
}

.badge-secondary {
  background: #94a3b8;
  color: white;
}

.badge-info {
  background: #3b82f6;
  color: white;
}

.command-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: #1e293b;
  padding: 1rem;
  border-radius: 0.375rem;
  margin: 1rem 0;
}

.command-box code {
  flex: 1;
  color: #10b981;
  font-family: monospace;
  font-size: 0.875rem;
  word-break: break-all;
}

.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 0.5rem;
  max-width: 640px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 { margin: 0; }

.btn-close {
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body { padding: 1.5rem; }

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.info-box {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(147, 51, 234, 0.1));
  border: 1px solid var(--primary-color);
  border-radius: 0.5rem;
  padding: 1rem 1.5rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
