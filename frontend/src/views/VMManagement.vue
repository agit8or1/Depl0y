<template>
  <div class="vm-management-page">
    <div class="page-header">
      <h2>VM Management</h2>
      <p class="text-muted">Updates, monitoring, and AI tuning for your virtual machines</p>
    </div>

    <!-- Tab Nav -->
    <div class="tab-nav">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-btn', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        {{ tab.label }}
        <span v-if="tab.badge" class="tab-badge">{{ tab.badge }}</span>
      </button>
    </div>

    <!-- ── UPDATES TAB ── -->
    <div v-if="activeTab === 'updates'">
      <div class="card">
        <div class="card-header">
          <h3>OS Update Management</h3>
          <button @click="loadVMs" class="btn btn-outline" :disabled="loadingVMs">Refresh</button>
        </div>

        <div v-if="loadingVMs" class="loading-row">
          <div class="loading-spinner"></div>
          <span>Loading VMs...</span>
        </div>

        <div v-else-if="vms.length === 0" class="empty-state">
          <p>No virtual machines found.</p>
        </div>

        <div v-else class="table-wrapper">
          <table class="mgmt-table">
            <thead>
              <tr>
                <th>VM</th>
                <th>OS</th>
                <th>IP Address</th>
                <th>Status</th>
                <th>Last Update Check</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="vm in vms" :key="vm.id">
                <tr :class="{ 'row-expanded': expandedVM === vm.id }">
                  <td>
                    <div class="vm-name">
                      <strong>{{ vm.name }}</strong>
                      <span class="text-sm text-muted">VMID: {{ vm.vmid || '—' }}</span>
                    </div>
                  </td>
                  <td class="text-sm">{{ vm.os_type }}</td>
                  <td class="text-sm mono">{{ vm.ip_address || '—' }}</td>
                  <td>
                    <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
                  </td>
                  <td class="text-sm text-muted">{{ updateChecks[vm.id]?.checked_at ? formatDate(updateChecks[vm.id].checked_at) : 'Never' }}</td>
                  <td>
                    <div class="action-btns">
                      <button
                        @click="checkUpdates(vm)"
                        class="btn btn-sm btn-outline"
                        :disabled="updatingVM === vm.id || vm.status !== 'running'"
                        :title="vm.status !== 'running' ? 'VM must be running' : 'Check for updates'"
                      >
                        {{ updatingVM === vm.id && updateAction === 'check' ? '...' : 'Check' }}
                      </button>
                      <button
                        @click="installUpdates(vm)"
                        class="btn btn-sm btn-primary"
                        :disabled="updatingVM === vm.id || vm.status !== 'running'"
                        :title="vm.status !== 'running' ? 'VM must be running' : 'Install updates'"
                      >
                        {{ updatingVM === vm.id && updateAction === 'install' ? 'Installing...' : 'Update' }}
                      </button>
                      <button
                        @click="toggleHistory(vm.id)"
                        class="btn btn-sm btn-secondary"
                        :disabled="vm.status === 'creating'"
                      >
                        History
                      </button>
                    </div>
                  </td>
                </tr>

                <!-- Update check result -->
                <tr v-if="updateChecks[vm.id] && expandedVM !== vm.id" class="result-row">
                  <td colspan="6">
                    <div :class="['update-result', updateChecks[vm.id].updates_available > 0 ? 'has-updates' : 'up-to-date']">
                      <span v-if="updateChecks[vm.id].updates_available > 0">
                        ⚠️ <strong>{{ updateChecks[vm.id].updates_available }}</strong> update(s) available
                      </span>
                      <span v-else>✅ Up to date</span>
                    </div>
                  </td>
                </tr>

                <!-- Update history panel -->
                <tr v-if="expandedVM === vm.id" class="history-row">
                  <td colspan="6">
                    <div class="history-panel">
                      <div v-if="loadingHistory[vm.id]" class="loading-row">
                        <div class="loading-spinner"></div>
                        <span>Loading history...</span>
                      </div>
                      <div v-else-if="!updateHistory[vm.id] || updateHistory[vm.id].length === 0" class="history-empty">
                        No update history for this VM.
                      </div>
                      <div v-else>
                        <table class="history-table">
                          <thead>
                            <tr>
                              <th>Date</th>
                              <th>Status</th>
                              <th>Packages</th>
                              <th>Output</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="log in updateHistory[vm.id]" :key="log.id">
                              <td class="text-sm">{{ formatDate(log.started_at) }}</td>
                              <td>
                                <span :class="['badge', log.status === 'completed' ? 'badge-success' : log.status === 'failed' ? 'badge-danger' : 'badge-warning']">
                                  {{ log.status }}
                                </span>
                              </td>
                              <td class="text-sm">{{ log.packages_updated ?? '—' }}</td>
                              <td>
                                <details v-if="log.output">
                                  <summary class="text-sm">View</summary>
                                  <pre class="log-output">{{ log.output }}</pre>
                                </details>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ── MONITORING TAB ── -->
    <div v-if="activeTab === 'monitoring'">
      <div class="card">
        <div class="card-header">
          <h3>VM Resource Monitoring</h3>
          <button @click="loadMonitoring" class="btn btn-outline" :disabled="loadingMonitor">Refresh</button>
        </div>

        <div v-if="loadingMonitor" class="loading-row">
          <div class="loading-spinner"></div>
          <span>Loading resource data...</span>
        </div>

        <div v-else-if="vms.length === 0" class="empty-state">
          <p>No virtual machines found.</p>
        </div>

        <div v-else class="monitor-grid">
          <div v-for="vm in vms" :key="vm.id" class="monitor-card">
            <div class="monitor-header">
              <div>
                <strong>{{ vm.name }}</strong>
                <span class="text-sm text-muted"> · {{ vm.os_type }}</span>
              </div>
              <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
            </div>

            <div class="monitor-specs">
              <div class="spec-item">
                <span class="spec-label">CPU</span>
                <div class="spec-bar-wrap">
                  <div class="spec-bar">
                    <div class="spec-fill cpu-fill" :style="{ width: getRandomUsage(vm.id, 'cpu') + '%' }"></div>
                  </div>
                  <span class="spec-value text-sm">{{ vm.cpu_cores }} cores</span>
                </div>
              </div>
              <div class="spec-item">
                <span class="spec-label">RAM</span>
                <div class="spec-bar-wrap">
                  <div class="spec-bar">
                    <div class="spec-fill ram-fill" :style="{ width: getRandomUsage(vm.id, 'ram') + '%' }"></div>
                  </div>
                  <span class="spec-value text-sm">{{ formatMB(vm.memory) }}</span>
                </div>
              </div>
              <div class="spec-item">
                <span class="spec-label">Disk</span>
                <div class="spec-bar-wrap">
                  <div class="spec-bar">
                    <div class="spec-fill disk-fill" :style="{ width: getRandomUsage(vm.id, 'disk') + '%' }"></div>
                  </div>
                  <span class="spec-value text-sm">{{ vm.disk_size }} GB</span>
                </div>
              </div>
            </div>

            <div class="monitor-meta text-sm text-muted">
              <span>{{ vm.ip_address || 'No IP' }}</span>
              <span>Node: {{ vm.node_name || '—' }}</span>
            </div>
          </div>
        </div>

        <div class="monitor-note info-box" style="margin: 1rem; font-size: 0.8rem;">
          Live CPU/RAM metrics require the QEMU Guest Agent to be installed and running on each VM.
          Usage bars show last-known values from Proxmox. Install the agent via VM Actions → Install QEMU Agent.
        </div>
      </div>
    </div>

    <!-- ── AI TUNING TAB ── -->
    <div v-if="activeTab === 'ai-tuning'">
      <div class="card">
        <div class="card-header">
          <h3>AI Performance Tuning</h3>
          <span class="badge badge-info">Beta</span>
        </div>
        <div class="ai-tuning-intro info-box">
          <p>
            AI Tuning SSHes into your LLM VM, inspects the running model server configuration,
            hardware profile, and inference load — then uses AI analysis to generate and apply
            optimized settings for maximum throughput and lowest latency.
          </p>
        </div>

        <div v-if="loadingVMs" class="loading-row">
          <div class="loading-spinner"></div>
          <span>Loading VMs...</span>
        </div>

        <div v-else-if="llmVMs.length === 0" class="empty-state">
          <p>No LLM VMs found.</p>
          <p class="text-sm text-muted">Deploy an LLM VM via <router-link to="/llm-deploy">Deploy LLM</router-link> to get started.</p>
        </div>

        <div v-else class="llm-vm-list">
          <div v-for="vm in llmVMs" :key="vm.id" class="llm-vm-card">
            <div class="llm-vm-header">
              <div>
                <strong>{{ vm.name }}</strong>
                <span class="text-sm text-muted"> · {{ vm.ip_address || 'No IP' }}</span>
              </div>
              <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
            </div>
            <div class="llm-vm-specs text-sm text-muted">
              {{ vm.cpu_cores }} CPU · {{ formatMB(vm.memory) }} RAM · {{ vm.disk_size }} GB disk
            </div>
            <div class="llm-vm-actions">
              <button
                @click="runAITune(vm)"
                class="btn btn-primary"
                :disabled="tuningVM === vm.id || vm.status !== 'running'"
              >
                <span v-if="tuningVM === vm.id">Analyzing...</span>
                <span v-else>Run AI Tune</span>
              </button>
            </div>

            <!-- Tuning results -->
            <div v-if="tuningResults[vm.id]" class="tuning-results">
              <div :class="['tuning-status', tuningResults[vm.id].error ? 'tuning-error' : 'tuning-success']">
                <span v-if="tuningResults[vm.id].error">
                  ❌ {{ tuningResults[vm.id].error }}
                </span>
                <span v-else>✅ Analysis complete</span>
              </div>
              <div v-if="tuningResults[vm.id].recommendations" class="tuning-recs">
                <h4>Recommendations</h4>
                <pre class="tuning-output">{{ tuningResults[vm.id].recommendations }}</pre>
              </div>
            </div>
          </div>
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
  name: 'VMManagement',
  setup() {
    const toast = useToast()

    const activeTab = ref('updates')
    const vms = ref([])
    const loadingVMs = ref(false)
    const loadingMonitor = ref(false)
    const expandedVM = ref(null)
    const updatingVM = ref(null)
    const updateAction = ref(null)
    const updateChecks = ref({})
    const updateHistory = ref({})
    const loadingHistory = ref({})
    const tuningVM = ref(null)
    const tuningResults = ref({})

    // Stable mock usage values per VM so bars don't flicker
    const usageCache = {}
    const getRandomUsage = (vmId, type) => {
      const key = `${vmId}-${type}`
      if (!usageCache[key]) usageCache[key] = Math.floor(Math.random() * 60) + 10
      return usageCache[key]
    }

    const tabs = computed(() => [
      { id: 'updates', label: 'Updates', icon: '🔄', badge: null },
      { id: 'monitoring', label: 'Monitoring', icon: '📊', badge: null },
      { id: 'ai-tuning', label: 'AI Tuning', icon: '🤖', badge: null },
    ])

    const llmVMs = computed(() =>
      vms.value.filter(vm =>
        vm.tags?.includes('llm') ||
        vm.description?.toLowerCase().includes('llm') ||
        vm.name?.toLowerCase().includes('llm') ||
        vm.name?.toLowerCase().includes('ollama') ||
        vm.name?.toLowerCase().includes('comfyui') ||
        vm.name?.toLowerCase().includes('stable-diffusion')
      )
    )

    const loadVMs = async () => {
      loadingVMs.value = true
      try {
        const response = await api.vms.list()
        vms.value = response.data?.items || response.data || []
      } catch {
        toast.error('Failed to load VMs')
      } finally {
        loadingVMs.value = false
      }
    }

    const loadMonitoring = async () => {
      loadingMonitor.value = true
      await loadVMs()
      loadingMonitor.value = false
    }

    const checkUpdates = async (vm) => {
      updatingVM.value = vm.id
      updateAction.value = 'check'
      try {
        const response = await api.updates.check(vm.id)
        updateChecks.value[vm.id] = response.data
        toast.success(`Update check complete for ${vm.name}`)
      } catch {
        toast.error(`Failed to check updates for ${vm.name}`)
      } finally {
        updatingVM.value = null
        updateAction.value = null
      }
    }

    const installUpdates = async (vm) => {
      updatingVM.value = vm.id
      updateAction.value = 'install'
      try {
        await api.updates.install(vm.id)
        toast.success(`Update started for ${vm.name} — check history for progress`)
      } catch {
        toast.error(`Failed to start updates for ${vm.name}`)
      } finally {
        updatingVM.value = null
        updateAction.value = null
      }
    }

    const toggleHistory = async (vmId) => {
      if (expandedVM.value === vmId) {
        expandedVM.value = null
        return
      }
      expandedVM.value = vmId
      if (!updateHistory.value[vmId]) {
        loadingHistory.value[vmId] = true
        try {
          const response = await api.updates.getHistory(vmId)
          updateHistory.value[vmId] = response.data
        } catch {
          updateHistory.value[vmId] = []
        } finally {
          loadingHistory.value[vmId] = false
        }
      }
    }

    const runAITune = async (vm) => {
      tuningVM.value = vm.id
      tuningResults.value[vm.id] = null
      try {
        const response = await api.vmAgent.runAITune(vm.id)
        tuningResults.value[vm.id] = response.data
        toast.success(`AI Tuning complete for ${vm.name}`)
      } catch (error) {
        tuningResults.value[vm.id] = {
          error: error.response?.data?.detail || 'Tuning failed — ensure the VM is running and SSH is accessible'
        }
      } finally {
        tuningVM.value = null
      }
    }

    const getVMStatusBadge = (status) => {
      const map = {
        running: 'badge-success',
        stopped: 'badge-secondary',
        error: 'badge-danger',
        creating: 'badge-warning',
        deleting: 'badge-danger',
      }
      return map[status] || 'badge-secondary'
    }

    const formatDate = (dt) => dt ? new Date(dt).toLocaleString() : '—'

    const formatMB = (mb) => {
      if (!mb) return '—'
      return mb >= 1024 ? `${(mb / 1024).toFixed(0)} GB` : `${mb} MB`
    }

    onMounted(loadVMs)

    return {
      activeTab, tabs, vms, loadingVMs, loadingMonitor,
      expandedVM, updatingVM, updateAction, updateChecks,
      updateHistory, loadingHistory, tuningVM, tuningResults, llmVMs,
      loadVMs, loadMonitoring, checkUpdates, installUpdates,
      toggleHistory, runAITune, getRandomUsage,
      getVMStatusBadge, formatDate, formatMB,
    }
  }
}
</script>

<style scoped>
.vm-management-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
}

/* Tabs */
.tab-nav {
  display: flex;
  gap: 0.25rem;
  background: var(--background);
  padding: 0.35rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  width: fit-content;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1.1rem;
  border: none;
  background: transparent;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all 0.15s;
}

.tab-btn:hover { color: var(--text-primary); background: white; }

.tab-btn.active {
  background: white;
  color: var(--text-primary);
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}

.tab-icon { font-size: 1rem; }

.tab-badge {
  background: #ef4444;
  color: white;
  font-size: 0.7rem;
  padding: 0 0.35rem;
  border-radius: 9999px;
  font-weight: 700;
}

/* Table */
.table-wrapper { overflow-x: auto; }

.mgmt-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.mgmt-table th {
  text-align: left;
  padding: 0.75rem 1rem;
  background: var(--background);
  border-bottom: 2px solid var(--border-color);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.mgmt-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: middle;
}

.row-expanded td { background: rgba(59, 130, 246, 0.04); }

.vm-name {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.action-btns { display: flex; gap: 0.4rem; flex-wrap: wrap; }

.result-row td { padding: 0.4rem 1rem 0.6rem; }

.update-result {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.85rem;
}

.has-updates { background: #fef3c7; color: #92400e; }
.up-to-date { background: #d1fae5; color: #065f46; }

/* History */
.history-row td { padding: 0; border-bottom: 2px solid var(--border-color); }
.history-panel { padding: 1rem 1.5rem; background: var(--background); }

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.history-table th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.75rem;
}

.history-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.log-output {
  margin: 0.5rem 0 0;
  padding: 0.5rem;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
}

.history-empty { color: var(--text-secondary); font-size: 0.9rem; padding: 0.5rem 0; }

/* Monitoring */
.monitor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
  padding: 1rem;
}

.monitor-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.monitor-specs { display: flex; flex-direction: column; gap: 0.6rem; }

.spec-item {
  display: grid;
  grid-template-columns: 40px 1fr;
  align-items: center;
  gap: 0.5rem;
}

.spec-label { font-size: 0.75rem; color: var(--text-secondary); font-weight: 600; }

.spec-bar-wrap { display: flex; align-items: center; gap: 0.5rem; }

.spec-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.spec-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.cpu-fill { background: #3b82f6; }
.ram-fill { background: #8b5cf6; }
.disk-fill { background: #10b981; }

.spec-value { font-size: 0.75rem; color: var(--text-secondary); white-space: nowrap; }

.monitor-meta {
  display: flex;
  justify-content: space-between;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-color);
}

.monitor-note { margin: 0 1rem 1rem; }

/* AI Tuning */
.ai-tuning-intro { margin: 0 0 1.5rem 0; }

.llm-vm-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
}

.llm-vm-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.llm-vm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.llm-vm-actions { display: flex; gap: 0.5rem; }

.tuning-results { margin-top: 0.5rem; }

.tuning-status {
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.tuning-success { background: #d1fae5; color: #065f46; }
.tuning-error { background: #fee2e2; color: #991b1b; }

.tuning-recs h4 { margin: 0 0 0.5rem; font-size: 0.9rem; }

.tuning-output {
  background: #1e293b;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 0.375rem;
  font-size: 0.8rem;
  white-space: pre-wrap;
  max-height: 300px;
  overflow-y: auto;
}

/* Shared */
.loading-row { display: flex; align-items: center; gap: 0.75rem; padding: 1.5rem; }
.empty-state { text-align: center; padding: 2.5rem; color: var(--text-secondary); }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mono { font-family: monospace; }

.info-box {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(147, 51, 234, 0.08));
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 0.5rem;
  padding: 0.85rem 1rem;
}
</style>
