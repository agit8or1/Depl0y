<template>
  <div class="vm-management-page">
    <div class="page-header">
      <h2>VM Management</h2>
      <p class="text-muted">Updates, security scanning, monitoring, and AI tuning for your virtual machines</p>
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

        <div class="table-toolbar">
          <input v-model="search" class="search-input" placeholder="Search VMs, VMID, IP, OS..." />
          <span class="text-sm text-muted">{{ filteredVMs.length }} of {{ vms.length }} VMs</span>
        </div>

        <div v-if="loadingVMs" class="loading-row">
          <div class="loading-spinner"></div>
          <span>Loading VMs...</span>
        </div>

        <div v-else-if="vms.length === 0" class="empty-state">
          <p>No virtual machines found.</p>
        </div>

        <div v-else-if="filteredVMs.length === 0" class="empty-state">
          <p>No VMs match "{{ search }}"</p>
        </div>

        <div v-else class="table-wrapper">
          <table class="mgmt-table">
            <thead>
              <tr>
                <th class="th-sortable" @click="setSort('name')">VM <span class="sort-icon">{{ sortIcon('name') }}</span></th>
                <th>OS</th>
                <th class="th-sortable" @click="setSort('ip')">IP Address <span class="sort-icon">{{ sortIcon('ip') }}</span></th>
                <th class="th-sortable" @click="setSort('status')">Status <span class="sort-icon">{{ sortIcon('status') }}</span></th>
                <th>Last Update Check</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="vm in filteredVMs" :key="vm.vmid">
                <tr :class="{ 'row-expanded': expandedVM === vm.vmid }">
                  <td>
                    <div class="vm-name">
                      <strong>{{ vm.name }}</strong>
                      <span class="text-sm text-muted">VMID: {{ vm.vmid }}</span>
                    </div>
                  </td>
                  <td class="text-sm">{{ getManagedVM(vm.vmid)?.os_type || '—' }}</td>
                  <td class="text-sm mono">{{ getManagedVM(vm.vmid)?.ip_address || '—' }}</td>
                  <td>
                    <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
                  </td>
                  <td class="text-sm text-muted">{{ updateChecks[vm.vmid]?.checked_at ? formatDate(updateChecks[vm.vmid].checked_at) : 'Never' }}</td>
                  <td>
                    <div class="action-btns">
                      <button
                        @click="checkUpdates(vm)"
                        class="btn btn-sm btn-outline"
                        :disabled="updatingVM === vm.vmid || vm.status !== 'running' || !getManagedVM(vm.vmid)?.ip_address"
                        :title="!getManagedVM(vm.vmid) ? 'Not managed by Depl0y' : !getManagedVM(vm.vmid)?.ip_address ? 'No IP — set SSH credentials first' : vm.status !== 'running' ? 'VM must be running' : 'Check for updates'"
                      >
                        {{ updatingVM === vm.vmid && updateAction === 'check' ? '...' : 'Check' }}
                      </button>
                      <button
                        @click="installUpdates(vm)"
                        class="btn btn-sm btn-primary"
                        :disabled="updatingVM === vm.vmid || vm.status !== 'running' || !getManagedVM(vm.vmid)?.ip_address"
                        :title="!getManagedVM(vm.vmid) ? 'Not managed by Depl0y' : !getManagedVM(vm.vmid)?.ip_address ? 'No IP — set SSH credentials first' : vm.status !== 'running' ? 'VM must be running' : 'Install updates'"
                      >
                        {{ updatingVM === vm.vmid && updateAction === 'install' ? 'Installing...' : 'Update' }}
                      </button>
                      <button
                        @click="toggleHistory(vm.vmid)"
                        class="btn btn-sm btn-secondary"
                      >
                        History
                      </button>
                      <button
                        @click="openCredModal(vm)"
                        class="btn btn-sm btn-outline"
                        :disabled="!getManagedVM(vm.vmid)"
                        :title="!getManagedVM(vm.vmid) ? 'Not managed by Depl0y' : 'Edit SSH credentials'"
                      >
                        🔑
                      </button>
                    </div>
                  </td>
                </tr>

                <!-- Update check result -->
                <tr v-if="updateChecks[vm.vmid] && expandedVM !== vm.vmid" class="result-row">
                  <td colspan="6">
                    <div :class="['update-result', updateChecks[vm.vmid].updates_available > 0 ? 'has-updates' : 'up-to-date']">
                      <span v-if="updateChecks[vm.vmid].updates_available > 0">
                        ⚠️ <strong>{{ updateChecks[vm.vmid].updates_available }}</strong> update(s) available
                      </span>
                      <span v-else>✅ Up to date</span>
                    </div>
                  </td>
                </tr>

                <!-- Update history panel -->
                <tr v-if="expandedVM === vm.vmid" class="history-row">
                  <td colspan="6">
                    <div class="history-panel">
                      <div v-if="loadingHistory[vm.vmid]" class="loading-row">
                        <div class="loading-spinner"></div>
                        <span>Loading history...</span>
                      </div>
                      <div v-else-if="!updateHistory[vm.vmid] || updateHistory[vm.vmid].length === 0" class="history-empty">
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
                            <tr v-for="log in updateHistory[vm.vmid]" :key="log.id">
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

    <!-- SSH Credentials Modal -->
    <div v-if="credModal.show" class="modal-overlay" @click="credModal.show = false">
      <div class="cred-modal" @click.stop>
        <div class="cred-modal-header">
          <h3>SSH Credentials — {{ credModal.vm?.name }}</h3>
          <button @click="credModal.show = false" class="btn-close-sm">×</button>
        </div>
        <div class="cred-modal-body">
          <p class="cred-note">These credentials are used to SSH into the VM for update and security scan operations.</p>
          <div class="form-group">
            <label class="form-label">
              IP Address
              <span v-if="fetchingIP" class="fetching-ip">fetching from agent...</span>
            </label>
            <input v-model="credForm.ip_address" class="form-control" placeholder="192.168.1.100" autocomplete="off" :disabled="fetchingIP" />
          </div>
          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="credForm.username" class="form-control" placeholder="ubuntu" autocomplete="off" />
          </div>
          <form @submit.prevent>
            <div class="form-group">
              <label class="form-label">Password</label>
              <input v-model="credForm.password" type="password" class="form-control" placeholder="Leave blank to keep existing" autocomplete="new-password" />
            </div>
          </form>
          <label class="cred-save-row">
            <input type="checkbox" v-model="credForm.saveToDb" />
            <span>Save credentials (encrypted)</span>
            <span class="cred-save-hint">Uncheck to use for this session only</span>
          </label>
        </div>
        <div class="cred-modal-footer">
          <button @click="credModal.show = false" class="btn btn-outline">Cancel</button>
          <button @click="saveCredentials" class="btn btn-primary" :disabled="savingCreds">
            {{ savingCreds ? 'Saving...' : credForm.saveToDb ? 'Save' : 'Use for Session' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── SECURITY TAB ── -->
    <div v-if="activeTab === 'security'">
      <div class="card">
        <div class="card-header">
          <h3>Security &amp; Dependency Scan</h3>
          <span class="text-sm text-muted">SSH-based scan: OS security updates, open ports, failed login attempts, outdated packages</span>
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
                <th class="th-sortable" @click="setSort('name')">VM <span class="sort-icon">{{ sortIcon('name') }}</span></th>
                <th class="th-sortable" @click="setSort('ip')">IP Address <span class="sort-icon">{{ sortIcon('ip') }}</span></th>
                <th class="th-sortable" @click="setSort('status')">Status <span class="sort-icon">{{ sortIcon('status') }}</span></th>
                <th>Last Scan</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="vm in filteredVMs" :key="vm.vmid">
                <tr>
                  <td>
                    <div class="vm-name">
                      <strong>{{ vm.name }}</strong>
                      <span class="text-sm text-muted">VMID: {{ vm.vmid }}</span>
                    </div>
                  </td>
                  <td class="text-sm mono">{{ getManagedVM(vm.vmid)?.ip_address || '—' }}</td>
                  <td>
                    <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
                  </td>
                  <td class="text-sm text-muted">
                    <span v-if="scanResults[vm.vmid]">
                      <span :class="['badge', scanResults[vm.vmid].severity === 'critical' ? 'badge-danger' : scanResults[vm.vmid].severity === 'warning' ? 'badge-warning' : 'badge-success']">
                        {{ scanResults[vm.vmid].severity }}
                      </span>
                      &nbsp;{{ formatDate(scanResults[vm.vmid].scanned_at) }}
                    </span>
                    <span v-else>Never</span>
                  </td>
                  <td>
                    <button
                      @click="runScan(vm)"
                      class="btn btn-sm btn-outline"
                      :disabled="scanning === vm.vmid || vm.status !== 'running' || !getManagedVM(vm.vmid)?.ip_address"
                      :title="!getManagedVM(vm.vmid) ? 'Not managed by Depl0y' : !getManagedVM(vm.vmid)?.ip_address ? 'No IP — set SSH credentials first' : vm.status !== 'running' ? 'VM must be running' : 'Run security scan'"
                    >
                      {{ scanning === vm.vmid ? 'Scanning...' : 'Scan' }}
                    </button>
                    <button
                      v-if="scanResults[vm.vmid]"
                      @click="scanExpanded[vm.vmid] = !scanExpanded[vm.vmid]"
                      class="btn btn-sm btn-secondary"
                      style="margin-left: 0.4rem"
                    >
                      {{ scanExpanded[vm.vmid] ? 'Hide' : 'Details' }}
                    </button>
                  </td>
                </tr>

                <!-- Scan results panel -->
                <tr v-if="scanResults[vm.vmid] && scanExpanded[vm.vmid]" class="history-row">
                  <td colspan="5">
                    <div class="history-panel scan-panel">
                      <div class="scan-grid">
                        <!-- OS Updates -->
                        <div class="scan-card">
                          <div class="scan-card-title">OS Updates</div>
                          <div class="scan-stat" :class="scanResults[vm.vmid].os_updates?.security_updates > 0 ? 'scan-stat-warn' : 'scan-stat-ok'">
                            {{ scanResults[vm.vmid].os_updates?.security_updates ?? '—' }}
                            <span class="scan-stat-label">security</span>
                          </div>
                          <div class="scan-sub text-muted">{{ scanResults[vm.vmid].os_updates?.total_upgradable ?? 0 }} total upgradable</div>
                          <div v-if="scanResults[vm.vmid].os_updates?.security_packages?.length" class="scan-pkg-list">
                            <div v-for="pkg in scanResults[vm.vmid].os_updates.security_packages.slice(0,8)" :key="pkg" class="scan-pkg">{{ pkg }}</div>
                          </div>
                        </div>

                        <!-- Failed SSH -->
                        <div class="scan-card">
                          <div class="scan-card-title">Failed SSH Logins</div>
                          <div class="scan-stat" :class="scanResults[vm.vmid].failed_ssh_attempts > 100 ? 'scan-stat-crit' : scanResults[vm.vmid].failed_ssh_attempts > 10 ? 'scan-stat-warn' : 'scan-stat-ok'">
                            {{ scanResults[vm.vmid].failed_ssh_attempts ?? 0 }}
                          </div>
                          <div class="scan-sub text-muted">attempts in auth.log</div>
                        </div>

                        <!-- Open Ports -->
                        <div class="scan-card scan-card-wide">
                          <div class="scan-card-title">Open Listening Ports</div>
                          <div v-if="scanResults[vm.vmid].open_ports?.length" class="scan-ports">
                            <pre class="scan-pre">{{ scanResults[vm.vmid].open_ports.join('\n') }}</pre>
                          </div>
                          <div v-else class="text-muted text-sm">None detected</div>
                        </div>

                        <!-- Python outdated -->
                        <div class="scan-card">
                          <div class="scan-card-title">Outdated Python Packages</div>
                          <div class="scan-stat" :class="scanResults[vm.vmid].python_outdated?.count > 0 ? 'scan-stat-warn' : 'scan-stat-ok'">
                            {{ scanResults[vm.vmid].python_outdated?.count ?? 0 }}
                          </div>
                          <div v-if="scanResults[vm.vmid].python_outdated?.packages?.length" class="scan-pkg-list">
                            <div v-for="pkg in scanResults[vm.vmid].python_outdated.packages.slice(0,5)" :key="pkg" class="scan-pkg">{{ pkg }}</div>
                          </div>
                          <div v-else class="scan-sub text-muted">pip3 not found or all current</div>
                        </div>

                        <!-- npm outdated -->
                        <div class="scan-card">
                          <div class="scan-card-title">Outdated npm (global)</div>
                          <div class="scan-stat" :class="scanResults[vm.vmid].npm_outdated?.count > 0 ? 'scan-stat-warn' : 'scan-stat-ok'">
                            {{ scanResults[vm.vmid].npm_outdated?.count ?? 0 }}
                          </div>
                          <div v-if="scanResults[vm.vmid].npm_outdated?.packages?.length" class="scan-pkg-list">
                            <div v-for="pkg in scanResults[vm.vmid].npm_outdated.packages.slice(0,5)" :key="pkg" class="scan-pkg">{{ pkg }}</div>
                          </div>
                          <div v-else class="scan-sub text-muted">npm not found or all current</div>
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
          <div v-for="vm in vms" :key="vm.vmid" class="monitor-card">
            <div class="monitor-header">
              <div>
                <strong>{{ vm.name }}</strong>
                <span class="text-sm text-muted" v-if="getManagedVM(vm.vmid)?.os_type"> · {{ getManagedVM(vm.vmid).os_type }}</span>
              </div>
              <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
            </div>

            <div class="monitor-specs">
              <div class="spec-row">
                <span class="spec-label">VMID</span>
                <span class="spec-value mono">{{ vm.vmid }}</span>
              </div>
              <div class="spec-row">
                <span class="spec-label">Node</span>
                <span class="spec-value mono">{{ vm.node || '—' }}</span>
              </div>
              <div class="spec-row">
                <span class="spec-label">CPU</span>
                <span class="spec-value">{{ vm.cpus || '—' }} cores</span>
              </div>
              <div class="spec-row">
                <span class="spec-label">RAM</span>
                <span class="spec-value">{{ formatBytes(vm.maxmem) }}</span>
              </div>
              <div class="spec-row">
                <span class="spec-label">Disk</span>
                <span class="spec-value">{{ formatBytes(vm.maxdisk) }}</span>
              </div>
              <div class="spec-row">
                <span class="spec-label">IP</span>
                <span class="spec-value mono">{{ getManagedVM(vm.vmid)?.ip_address || '—' }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="monitor-note info-box" style="margin: 0 1rem 1rem; font-size: 0.8rem;">
          Live CPU/RAM usage metrics require the QEMU Guest Agent on each VM and are available in the Proxmox web UI.
          The <router-link to="/proxmox">Proxmox Hosts</router-link> page shows node-level resource usage.
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
          <div v-for="vm in llmVMs" :key="vm.vmid" class="llm-vm-card">
            <div class="llm-vm-header">
              <div>
                <strong>{{ vm.name }}</strong>
                <span class="text-sm text-muted"> · {{ getManagedVM(vm.vmid)?.ip_address || 'No IP' }}</span>
              </div>
              <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
            </div>
            <div class="llm-vm-specs text-sm text-muted">
              {{ vm.cpus || '—' }} CPU · {{ formatBytes(vm.maxmem) }} RAM · {{ formatBytes(vm.maxdisk) }} disk
            </div>
            <div class="llm-vm-actions">
              <button
                @click="runAITune(vm)"
                class="btn btn-primary"
                :disabled="tuningVM === vm.vmid || vm.status !== 'running' || !getManagedVM(vm.vmid)"
                :title="!getManagedVM(vm.vmid) ? 'Not managed by Depl0y' : ''"
              >
                <span v-if="tuningVM === vm.vmid">Analyzing...</span>
                <span v-else>Run AI Tune</span>
              </button>
            </div>

            <!-- Tuning results -->
            <div v-if="tuningResults[vm.vmid]" class="tuning-results">
              <div :class="['tuning-status', tuningResults[vm.vmid].error ? 'tuning-error' : 'tuning-success']">
                <span v-if="tuningResults[vm.vmid].error">
                  ❌ {{ tuningResults[vm.vmid].error }}
                </span>
                <span v-else>✅ Analysis complete</span>
              </div>
              <div v-if="tuningResults[vm.vmid].recommendations" class="tuning-recs">
                <h4>Recommendations</h4>
                <pre class="tuning-output">{{ tuningResults[vm.vmid].recommendations }}</pre>
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
    const vms = ref([])          // Proxmox live VMs (display)
    const managedVMs = ref([])   // Depl0y DB VMs (for update/credential operations)
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
    const credModal = ref({ show: false, vm: null })
    const credForm = ref({ ip_address: '', username: '', password: '', saveToDb: true })
    const savingCreds = ref(false)
    const fetchingIP = ref(false)
    const sessionCreds = ref({})   // vmid → { ip_address, username, password } for session-only creds
    const scanResults = ref({})    // vmid → scan result object
    const scanning = ref(null)     // vmid currently being scanned
    const scanExpanded = ref({})   // vmid → bool
    const search = ref('')
    const sortKey = ref('name')
    const sortDir = ref('asc')

    // Returns the DB-managed VM matching a Proxmox vmid (for update/SSH ops)
    // Uses Number() to safely compare regardless of whether vmid is string or integer
    const getManagedVM = (vmid) => {
      const id = Number(vmid)
      return managedVMs.value.find(m => Number(m.vmid) === id) || null
    }


    const setSort = (key) => {
      if (sortKey.value === key) {
        sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
      } else {
        sortKey.value = key
        sortDir.value = 'asc'
      }
    }

    const filteredVMs = computed(() => {
      const q = search.value.toLowerCase().trim()
      let list = q
        ? vms.value.filter(vm =>
            vm.name?.toLowerCase().includes(q) ||
            String(vm.vmid).includes(q) ||
            vm.node?.toLowerCase().includes(q) ||
            getManagedVM(vm.vmid)?.ip_address?.includes(q) ||
            getManagedVM(vm.vmid)?.os_type?.toLowerCase().includes(q)
          )
        : [...vms.value]

      list.sort((a, b) => {
        let av, bv
        if (sortKey.value === 'vmid') { av = Number(a.vmid); bv = Number(b.vmid) }
        else if (sortKey.value === 'ip') { av = getManagedVM(a.vmid)?.ip_address || ''; bv = getManagedVM(b.vmid)?.ip_address || '' }
        else if (sortKey.value === 'status') { av = a.status || ''; bv = b.status || '' }
        else { av = (a.name || '').toLowerCase(); bv = (b.name || '').toLowerCase() }
        if (av < bv) return sortDir.value === 'asc' ? -1 : 1
        if (av > bv) return sortDir.value === 'asc' ? 1 : -1
        return 0
      })
      return list
    })

    const sortIcon = (key) => {
      if (sortKey.value !== key) return '↕'
      return sortDir.value === 'asc' ? '↑' : '↓'
    }

    const tabs = computed(() => [
      { id: 'updates', label: 'Updates', icon: '🔄', badge: null },
      { id: 'security', label: 'Security Scan', icon: '🔒', badge: null },
      { id: 'monitoring', label: 'Monitoring', icon: '📊', badge: null },
      { id: 'ai-tuning', label: 'AI Tuning', icon: '🤖', badge: null },
    ])

    const llmVMs = computed(() =>
      vms.value.filter(vm =>
        vm.name?.toLowerCase().includes('llm') ||
        vm.name?.toLowerCase().includes('ollama') ||
        vm.name?.toLowerCase().includes('comfyui') ||
        vm.name?.toLowerCase().includes('stable-diffusion') ||
        vm.tags?.includes('llm')
      )
    )

    const loadVMs = async () => {
      loadingVMs.value = true
      try {
        const [proxmoxRes, managedRes] = await Promise.all([
          api.vms.list().catch(() => ({ data: [] })),
          api.vms.listManaged().catch(() => ({ data: [] }))
        ])
        vms.value = proxmoxRes.data || []
        managedVMs.value = managedRes.data || []
      } catch {
        toast.error('Failed to load VMs')
      } finally {
        loadingVMs.value = false
      }
    }

    const openCredModal = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      const sess = sessionCreds.value[vm.vmid]
      credModal.value = { show: true, vm, managed }
      credForm.value = {
        ip_address: managed?.ip_address || sess?.ip_address || '',
        username: managed?.username || sess?.username || '',
        password: '',
        saveToDb: true,
      }
      // If no IP stored anywhere and VM is running, auto-fetch from QEMU guest agent
      if (!credForm.value.ip_address && vm.status === 'running' && vm.node) {
        fetchingIP.value = true
        try {
          const res = await api.vms.getAgentIP(vm.node, vm.vmid)
          if (res.data?.ip_address) {
            credForm.value.ip_address = res.data.ip_address
          }
        } catch { /* agent not available or not running — field stays blank */ }
        finally { fetchingIP.value = false }
      }
    }

    const saveCredentials = async () => {
      const { vm, managed } = credModal.value
      const { ip_address, username, password, saveToDb } = credForm.value

      if (saveToDb) {
        if (!managed) {
          toast.error('This VM is not managed by Depl0y — uncheck "Save credentials" to use for this session only')
          return
        }
        savingCreds.value = true
        try {
          const payload = { ip_address, username }
          if (password) payload.password = password
          await api.vms.update(managed.id, payload)
          toast.success('Credentials saved (encrypted)')
          credModal.value.show = false
          await loadVMs()
        } catch {
          toast.error('Failed to save credentials')
        } finally {
          savingCreds.value = false
        }
      } else {
        // Session-only: store in memory, never sent to DB
        sessionCreds.value[vm.vmid] = {
          ip_address,
          username,
          password: password || undefined,
        }
        toast.success('Credentials stored for this session only')
        credModal.value.show = false
      }
    }

    const loadMonitoring = async () => {
      loadingMonitor.value = true
      await loadVMs()
      loadingMonitor.value = false
    }

    const getSessionCreds = (vmid) => {
      const s = sessionCreds.value[vmid]
      if (!s) return null
      return { ip_address: s.ip_address || undefined, username: s.username || undefined, password: s.password || undefined }
    }

    const checkUpdates = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      updatingVM.value = vm.vmid
      updateAction.value = 'check'
      try {
        const response = await api.updates.check(managed.id, getSessionCreds(vm.vmid))
        updateChecks.value[vm.vmid] = response.data
        toast.success(`Update check complete for ${vm.name}`)
      } catch {
        toast.error(`Failed to check updates for ${vm.name}`)
      } finally {
        updatingVM.value = null
        updateAction.value = null
      }
    }

    const installUpdates = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      updatingVM.value = vm.vmid
      updateAction.value = 'install'
      try {
        await api.updates.install(managed.id, getSessionCreds(vm.vmid))
        toast.success(`Update started for ${vm.name} — check history for progress`)
      } catch {
        toast.error(`Failed to start updates for ${vm.name}`)
      } finally {
        updatingVM.value = null
        updateAction.value = null
      }
    }

    const runScan = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      scanning.value = vm.vmid
      try {
        const response = await api.updates.scanSecurity(managed.id, getSessionCreds(vm.vmid))
        scanResults.value[vm.vmid] = response.data
        scanExpanded.value[vm.vmid] = true
        const sev = response.data.severity
        if (sev === 'critical') toast.error(`${vm.name}: critical security issues found`)
        else if (sev === 'warning') toast.warning(`${vm.name}: security warnings found`)
        else toast.success(`${vm.name}: scan complete — no critical issues`)
      } catch {
        toast.error(`Security scan failed for ${vm.name}`)
      } finally {
        scanning.value = null
      }
    }

    const toggleHistory = async (vmid) => {
      if (expandedVM.value === vmid) {
        expandedVM.value = null
        return
      }
      expandedVM.value = vmid
      const managed = getManagedVM(vmid)
      if (!managed) {
        updateHistory.value[vmid] = []
        return
      }
      if (!updateHistory.value[vmid]) {
        loadingHistory.value[vmid] = true
        try {
          const response = await api.updates.getHistory(managed.id)
          updateHistory.value[vmid] = response.data
        } catch {
          updateHistory.value[vmid] = []
        } finally {
          loadingHistory.value[vmid] = false
        }
      }
    }

    const runAITune = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      tuningVM.value = vm.vmid
      tuningResults.value[vm.vmid] = null
      try {
        const response = await api.vmAgent.runAITune(managed.id)
        tuningResults.value[vm.vmid] = response.data
        toast.success(`AI Tuning complete for ${vm.name}`)
      } catch (error) {
        tuningResults.value[vm.vmid] = {
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

    // For Proxmox live data (maxmem, maxdisk are in bytes)
    const formatBytes = (bytes) => {
      if (!bytes) return '—'
      const gb = bytes / (1024 * 1024 * 1024)
      if (gb >= 1) return `${gb.toFixed(1)} GB`
      return `${(bytes / (1024 * 1024)).toFixed(0)} MB`
    }

    // Legacy: for DB VMs that store memory in MB
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
      toggleHistory, runAITune, getManagedVM,
      runScan, scanResults, scanning, scanExpanded,
      getVMStatusBadge, formatDate, formatBytes, formatMB,
      credModal, credForm, savingCreds, fetchingIP, openCredModal, saveCredentials, sessionCreds,
      search, sortKey, sortDir, filteredVMs, setSort, sortIcon,
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

/* Toolbar */
.table-toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
}

.search-input {
  flex: 1;
  max-width: 320px;
  padding: 0.45rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  background: var(--card-bg, #fff);
  color: var(--text-primary);
  outline: none;
}

.search-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.15); }

/* Table */
.table-wrapper { overflow-x: auto; }

.th-sortable {
  cursor: pointer;
  user-select: none;
}
.th-sortable:hover { color: var(--text-primary); }

.sort-icon {
  font-size: 0.7rem;
  opacity: 0.6;
  margin-left: 0.2rem;
}

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

.monitor-specs { display: flex; flex-direction: column; gap: 0.4rem; }

.spec-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
}

.spec-label { color: var(--text-secondary); font-weight: 500; }

.spec-value { color: var(--text-primary); }

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

/* Credentials save row */
.cred-save-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
  margin-top: 0.25rem;
}

.cred-save-hint {
  color: var(--text-secondary);
  font-size: 0.75rem;
}

/* Security Scan */
.scan-panel { padding: 1rem 1.5rem; background: var(--background); }

.scan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
}

.scan-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.scan-card-wide { grid-column: span 2; }

.scan-card-title {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.scan-stat {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1;
  display: flex;
  align-items: baseline;
  gap: 0.3rem;
}

.scan-stat-label { font-size: 0.8rem; font-weight: 400; color: var(--text-secondary); }
.scan-stat-ok { color: #059669; }
.scan-stat-warn { color: #d97706; }
.scan-stat-crit { color: #dc2626; }

.scan-sub { font-size: 0.8rem; color: var(--text-secondary); }

.scan-pkg-list { display: flex; flex-direction: column; gap: 0.15rem; margin-top: 0.25rem; }
.scan-pkg { font-size: 0.75rem; font-family: monospace; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.scan-ports { overflow-x: auto; }
.scan-pre {
  font-size: 0.72rem;
  font-family: monospace;
  background: #1e293b;
  color: #e2e8f0;
  padding: 0.5rem 0.75rem;
  border-radius: 0.25rem;
  margin: 0;
  white-space: pre;
  overflow-x: auto;
  max-height: 160px;
  overflow-y: auto;
}

/* SSH Credentials Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.cred-modal {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  width: 90%;
  max-width: 440px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.2);
}

.cred-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
}

.cred-modal-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.btn-close-sm {
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 0 0.25rem;
  line-height: 1;
}

.cred-modal-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.fetching-ip {
  font-size: 0.75rem;
  color: #3b82f6;
  font-weight: 400;
  margin-left: 0.5rem;
}

.cred-note {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin: 0 0 0.25rem;
}

.cred-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid var(--border-color);
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
