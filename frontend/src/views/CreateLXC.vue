<template>
  <div class="create-lxc-page">
    <div class="card">
      <div class="card-header">
        <h3>Create LXC Container</h3>
        <p class="card-subtitle">Lightweight Linux container with shared host kernel.</p>
      </div>

      <!-- Tab Navigation -->
      <div class="lxc-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="['lxc-tab', { 'active': activeTab === tab.id }]"
          @click="activeTab = tab.id"
          type="button"
        >
          <span>{{ tab.icon }}</span>
          <span>{{ tab.label }}</span>
        </button>
      </div>

      <form @submit.prevent="createLXC" class="create-lxc-form">

        <!-- ==================== GENERAL TAB ==================== -->
        <div v-show="activeTab === 'general'" class="tab-content">
          <h4 class="section-title">General</h4>

          <!-- Host & Node -->
          <div class="form-section">
            <h5 class="subsection-title">Datacenter &amp; Node</h5>
            <div class="form-group">
              <label class="form-label">Proxmox Host *</label>
              <select v-model="selectedHostId" class="form-control" required @change="onHostChange">
                <option value="">Select host...</option>
                <option v-for="host in hosts" :key="host.id" :value="host.id">
                  {{ host.name }} ({{ host.hostname }}:{{ host.port }})
                </option>
              </select>
            </div>

            <div v-if="selectedHostId" class="form-group">
              <label class="form-label">Node *</label>
              <div v-if="loadingNodes" class="loading-message">
                <div class="loading-spinner"></div><p>Loading nodes...</p>
              </div>
              <select v-else v-model="selectedNode" class="form-control" required @change="onNodeChange">
                <option value="">Select node...</option>
                <option v-for="n in nodes" :key="n.node" :value="n.node">{{ n.node }}</option>
              </select>
            </div>
          </div>

          <!-- Container Identity -->
          <div v-if="selectedNode" class="form-section">
            <h5 class="subsection-title">Container Identity</h5>
            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">CT ID *</label>
                <input
                  v-model.number="formData.vmid"
                  type="number"
                  min="100"
                  max="999999999"
                  :class="['form-control', { 'input-error': fieldErrors.vmid }]"
                  required
                  placeholder="Auto-assigned"
                  @blur="fieldErrors.vmid = validate(formData.vmid, [rules.required, rules.vmId]) === true ? '' : validate(formData.vmid, [rules.required, rules.vmId])"
                />
                <small v-if="fieldErrors.vmid" class="form-error-text">{{ fieldErrors.vmid }}</small>
                <small v-else class="form-help">Container ID (100–999999999)</small>
              </div>
              <div class="form-group">
                <label class="form-label">Hostname *</label>
                <input
                  v-model="formData.hostname"
                  type="text"
                  :class="['form-control', { 'input-error': fieldErrors.hostname }]"
                  required
                  placeholder="my-container"
                  @blur="fieldErrors.hostname = validate(formData.hostname, [rules.required, rules.hostname]) === true ? '' : validate(formData.hostname, [rules.required, rules.hostname])"
                />
                <small v-if="fieldErrors.hostname" class="form-error-text">{{ fieldErrors.hostname }}</small>
                <small v-else class="form-help">Letters, numbers, hyphens only</small>
              </div>
              <div class="form-group">
                <label class="form-label">Root Password *</label>
                <input
                  v-model="formData.password"
                  type="password"
                  :class="['form-control', { 'input-error': fieldErrors.password }]"
                  required
                  autocomplete="new-password"
                  @blur="fieldErrors.password = validate(formData.password, [rules.required, rules.password(8)]) === true ? '' : validate(formData.password, [rules.required, rules.password(8)])"
                />
                <small v-if="fieldErrors.password" class="form-error-text">{{ fieldErrors.password }}</small>
                <small v-else class="form-help">Minimum 8 characters</small>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Description / Notes</label>
              <textarea v-model="formData.description" class="form-control" rows="2" placeholder="Optional description..."></textarea>
            </div>

            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">
                  <input type="checkbox" v-model="formData.unprivileged" style="margin-right:8px" />
                  Unprivileged Container
                </label>
                <div class="form-text">Recommended — runs as non-root on host</div>
              </div>
              <div class="form-group">
                <label class="form-label">
                  <input type="checkbox" v-model="formData.start" style="margin-right:8px" />
                  Start after create
                </label>
              </div>
              <div class="form-group">
                <label class="form-label">
                  <input type="checkbox" v-model="formData.onboot" style="margin-right:8px" />
                  Start at boot
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- ==================== TEMPLATE TAB ==================== -->
        <div v-show="activeTab === 'template'" class="tab-content">
          <h4 class="section-title">Template Selection</h4>

          <div v-if="!selectedNode" class="info-banner">
            Select a Proxmox host and node first (General tab).
          </div>

          <div v-else>
            <!-- Selected template summary card -->
            <div v-if="formData.ostemplate" class="selected-template-card">
              <div class="selected-template-icon">{{ selectedTemplateOs.icon }}</div>
              <div class="selected-template-info">
                <div class="selected-template-label">Selected Template</div>
                <div class="selected-template-name">{{ selectedTemplateDisplayName }}</div>
                <div class="selected-template-os" :style="{ color: selectedTemplateOs.color }">
                  {{ selectedTemplateOs.name }}
                </div>
              </div>
              <button type="button" class="btn btn-sm btn-outline" @click="formData.ostemplate = ''">
                Change
              </button>
            </div>

            <!-- Template library component -->
            <LXCTemplateLibrary
              :host-id="selectedHostId"
              :node="selectedNode"
              :storages="templateStorages"
              @select="onTemplateSelected"
            />
          </div>
        </div>

        <!-- ==================== STORAGE TAB ==================== -->
        <div v-show="activeTab === 'storage'" class="tab-content">
          <h4 class="section-title">Storage</h4>

          <div v-if="!selectedNode" class="info-banner">Select a host and node first.</div>

          <div v-else>
            <div v-if="loadingStorage" class="loading-message">
              <div class="loading-spinner"></div><p>Loading storage...</p>
            </div>

            <div v-else>
              <!-- Root disk -->
              <div class="form-section">
                <h5 class="subsection-title">Root Filesystem (rootfs)</h5>
                <div class="storage-cards">
                  <div
                    v-for="storage in diskStorageList"
                    :key="storage.storage"
                    :class="['storage-card', { 'selected': formData.storage === storage.storage, 'disabled': !storage.enabled || !storage.active }]"
                    @click="selectStorage(storage.storage)"
                  >
                    <div class="storage-header">
                      <h6>{{ storage.storage }}</h6>
                      <span class="badge badge-sm badge-info">{{ storage.type }}</span>
                    </div>
                    <div class="storage-info">
                      <div class="storage-bar">
                        <div class="storage-bar-fill" :style="{ width: getStorageUsagePercent(storage) + '%' }"></div>
                      </div>
                      <div class="storage-stats">
                        <span>{{ formatBytes(storage.available) }} free</span>
                        <span>{{ formatBytes(storage.total) }} total</span>
                      </div>
                    </div>
                    <div v-if="storage.shared" class="storage-badge"><span class="badge badge-success">Shared</span></div>
                  </div>
                </div>

                <div class="form-group" style="margin-top:1rem">
                  <label class="form-label">Root Disk Size (GB) *</label>
                  <input v-model.number="formData.rootfs_size" type="number" min="1" class="form-control" required />
                </div>
              </div>

              <!-- Additional mount points -->
              <div class="form-section">
                <div class="section-header-with-action">
                  <h5 class="subsection-title">Additional Mount Points</h5>
                  <button type="button" class="btn btn-sm btn-outline" @click="addMountPoint" :disabled="mountPoints.length >= 10">
                    + Add Mount Point
                  </button>
                </div>

                <div v-if="mountPoints.length === 0" class="text-muted" style="font-size:0.875rem">
                  No additional mount points. Click "Add Mount Point" to add one.
                </div>

                <div v-for="(mp, idx) in mountPoints" :key="idx" class="mount-point-row">
                  <div class="mount-point-header">
                    <span class="disk-label">mp{{ idx }}</span>
                    <button type="button" class="btn-icon-danger" @click="removeMountPoint(idx)">✕</button>
                  </div>
                  <div class="grid grid-cols-3 gap-2">
                    <div class="form-group">
                      <label class="form-label">Storage</label>
                      <select v-model="mp.storage" class="form-control">
                        <option v-for="s in diskStorageList" :key="s.storage" :value="s.storage">{{ s.storage }}</option>
                      </select>
                    </div>
                    <div class="form-group">
                      <label class="form-label">Size (GB)</label>
                      <input v-model.number="mp.size" type="number" min="1" class="form-control" />
                    </div>
                    <div class="form-group">
                      <label class="form-label">Mount Path</label>
                      <input v-model="mp.mountpoint" type="text" class="form-control" placeholder="/mnt/data" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ==================== RESOURCES TAB ==================== -->
        <div v-show="activeTab === 'resources'" class="tab-content">
          <h4 class="section-title">Resource Allocation</h4>

          <div class="form-section">
            <h5 class="subsection-title">CPU</h5>
            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">CPU Cores *</label>
                <input
                  v-model.number="formData.cores"
                  type="number"
                  min="1"
                  max="512"
                  :class="['form-control', { 'input-error': fieldErrors.cores }]"
                  required
                  @blur="fieldErrors.cores = validate(formData.cores, [rules.required, rules.intRange(1, 512)]) === true ? '' : validate(formData.cores, [rules.required, rules.intRange(1, 512)])"
                />
                <small v-if="fieldErrors.cores" class="form-error-text">{{ fieldErrors.cores }}</small>
              </div>
              <div class="form-group">
                <label class="form-label">CPU Limit (optional)</label>
                <input v-model.number="formData.cpulimit" type="number" min="0" max="128" class="form-control" placeholder="0 = no limit" />
                <small class="form-help">Max CPU usage (fractional cores)</small>
              </div>
              <div class="form-group">
                <label class="form-label">CPU Units (weight)</label>
                <input v-model.number="formData.cpuunits" type="number" min="8" max="500000" class="form-control" placeholder="1024" />
                <small class="form-help">Scheduler priority weight</small>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h5 class="subsection-title">Memory</h5>
            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">Memory (MB) *</label>
                <input
                  v-model.number="formData.memory"
                  type="number"
                  min="64"
                  step="64"
                  :class="['form-control', { 'input-error': fieldErrors.memory }]"
                  required
                  @blur="fieldErrors.memory = validate(formData.memory, [rules.required, rules.intRange(64, 4194304)]) === true ? '' : validate(formData.memory, [rules.required, rules.intRange(64, 4194304)])"
                />
                <small v-if="fieldErrors.memory" class="form-error-text">{{ fieldErrors.memory }}</small>
                <small v-else class="form-help">{{ (formData.memory / 1024).toFixed(1) }} GB</small>
              </div>
              <div class="form-group">
                <label class="form-label">Swap (MB)</label>
                <input v-model.number="formData.swap" type="number" min="0" step="64" class="form-control" />
              </div>
              <div class="form-group">
                <label class="form-label">Memory Shares</label>
                <input v-model.number="formData.shares" type="number" min="0" max="512000" class="form-control" placeholder="Default" />
                <small class="form-help">Scheduler weight (higher = priority)</small>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h5 class="subsection-title">Startup &amp; Shutdown</h5>
            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">Startup Order</label>
                <input v-model.number="formData.startup_order" type="number" min="0" class="form-control" placeholder="Default" />
                <small class="form-help">Lower starts first</small>
              </div>
              <div class="form-group">
                <label class="form-label">Startup Delay (sec)</label>
                <input v-model.number="formData.startup_up" type="number" min="0" class="form-control" placeholder="0" />
              </div>
              <div class="form-group">
                <label class="form-label">Shutdown Timeout (sec)</label>
                <input v-model.number="formData.startup_down" type="number" min="0" class="form-control" placeholder="60" />
              </div>
            </div>
          </div>
        </div>

        <!-- ==================== NETWORK TAB ==================== -->
        <div v-show="activeTab === 'network'" class="tab-content">
          <h4 class="section-title">Network</h4>

          <div v-if="!selectedNode" class="info-banner">Select a host and node first.</div>

          <div v-else>
            <!-- Bridge picker -->
            <div class="form-section">
              <h5 class="subsection-title">Available Bridges</h5>
              <div v-if="loadingNetwork" class="loading-message">
                <div class="loading-spinner"></div><p>Loading network...</p>
              </div>
              <div v-else class="network-cards">
                <div
                  v-for="net in bridgeList"
                  :key="net.iface"
                  :class="['network-card', { 'selected': netInterfaces[0] && netInterfaces[0].bridge === net.iface, 'disabled': !net.active }]"
                  @click="setDefaultBridge(net.iface)"
                >
                  <div class="network-header">
                    <h6>{{ net.iface }}</h6>
                    <span :class="['badge', 'badge-sm', net.active ? 'badge-success' : 'badge-danger']">{{ net.active ? 'Active' : 'Inactive' }}</span>
                  </div>
                  <div class="network-info">
                    <div v-if="net.address" class="text-xs"><strong>IP:</strong> {{ net.address }}</div>
                    <div v-if="net.bridge_ports" class="text-xs"><strong>Ports:</strong> {{ net.bridge_ports }}</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Network interfaces -->
            <div class="form-section">
              <div class="section-header-with-action">
                <h5 class="subsection-title">Network Interfaces</h5>
                <button type="button" class="btn btn-sm btn-outline" @click="addNetInterface" :disabled="netInterfaces.length >= 4">
                  + Add Interface
                </button>
              </div>

              <div v-for="(iface, idx) in netInterfaces" :key="idx" class="nic-row">
                <div class="nic-row-header">
                  <span class="nic-label">net{{ idx }} (eth{{ idx }})</span>
                  <button type="button" class="btn-icon-danger" v-if="idx > 0" @click="removeNetInterface(idx)">✕</button>
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <div class="form-group">
                    <label class="form-label">Bridge *</label>
                    <select v-model="iface.bridge" class="form-control">
                      <option v-for="b in bridgeList" :key="b.iface" :value="b.iface">{{ b.iface }}</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label">VLAN Tag (optional)</label>
                    <input v-model.number="iface.vlan" type="number" min="1" max="4094" class="form-control" placeholder="None" />
                  </div>
                </div>

                <div class="form-group">
                  <label class="form-label">
                    <input type="checkbox" v-model="iface.dhcp" style="margin-right:8px" />
                    Use DHCP
                  </label>
                </div>

                <div v-if="!iface.dhcp" class="grid grid-cols-2 gap-2">
                  <div class="form-group">
                    <label class="form-label">IP / CIDR *</label>
                    <input v-model="iface.ip_cidr" type="text" class="form-control" placeholder="192.168.1.100/24" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Gateway *</label>
                    <input v-model="iface.gateway" type="text" class="form-control" placeholder="192.168.1.1" />
                  </div>
                </div>
              </div>
            </div>

            <!-- DNS -->
            <div class="form-section">
              <h5 class="subsection-title">DNS</h5>
              <div class="grid grid-cols-2 gap-2">
                <div class="form-group">
                  <label class="form-label">DNS Nameservers</label>
                  <input v-model="formData.nameserver" type="text" class="form-control" placeholder="8.8.8.8 8.8.4.4" />
                  <small class="form-help">Space-separated list</small>
                </div>
                <div class="form-group">
                  <label class="form-label">Search Domain</label>
                  <input v-model="formData.searchdomain" type="text" class="form-control" placeholder="example.com" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ==================== FEATURES TAB ==================== -->
        <div v-show="activeTab === 'features'" class="tab-content">
          <h4 class="section-title">Container Features</h4>

          <div class="form-section">
            <h5 class="subsection-title">Kernel &amp; Filesystem Features</h5>
            <p class="feature-note">Some features require an unprivileged container. Enable only what is needed.</p>

            <div class="features-grid">
              <label v-for="feat in containerFeatures" :key="feat.key" class="feature-card">
                <input type="checkbox" v-model="formData.features[feat.key]" />
                <div class="feature-card-content">
                  <div class="feature-card-title">{{ feat.label }}</div>
                  <div class="feature-card-desc">{{ feat.desc }}</div>
                  <div v-if="feat.requiresPrivileged" class="feature-card-warning">⚠ Requires privileged container</div>
                </div>
              </label>
            </div>
          </div>

          <div class="form-section">
            <h5 class="subsection-title">Protection</h5>
            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="formData.protection" style="margin-right:8px" />
                Protection (prevent deletion)
              </label>
              <div class="form-text">Protect container from accidental removal</div>
            </div>
          </div>
        </div>

        <!-- ==================== CONFIRM TAB ==================== -->
        <div v-show="activeTab === 'confirm'" class="tab-content">
          <h4 class="section-title">Review &amp; Create</h4>

          <div class="summary-grid">
            <div class="summary-section">
              <h5 class="summary-section-title">General</h5>
              <table class="summary-table">
                <tr><td>CT ID</td><td>{{ formData.vmid || 'Auto' }}</td></tr>
                <tr><td>Hostname</td><td>{{ formData.hostname || '—' }}</td></tr>
                <tr><td>Unprivileged</td><td>{{ formData.unprivileged ? 'Yes' : 'No' }}</td></tr>
                <tr><td>Start at boot</td><td>{{ formData.onboot ? 'Yes' : 'No' }}</td></tr>
                <tr><td>Start after create</td><td>{{ formData.start ? 'Yes' : 'No' }}</td></tr>
              </table>
            </div>
            <div class="summary-section">
              <h5 class="summary-section-title">Template</h5>
              <table class="summary-table">
                <tr><td>Source</td><td>{{ templateSource === 'local' ? 'Local' : 'Library' }}</td></tr>
                <tr><td>Template</td><td>{{ formData.ostemplate || '—' }}</td></tr>
              </table>
            </div>
            <div class="summary-section">
              <h5 class="summary-section-title">Storage</h5>
              <table class="summary-table">
                <tr><td>Root disk</td><td>{{ formData.storage }}:{{ formData.rootfs_size }}GB</td></tr>
                <tr v-for="(mp, i) in mountPoints" :key="i">
                  <td>mp{{ i }}</td><td>{{ mp.storage }}:{{ mp.size }}GB → {{ mp.mountpoint }}</td>
                </tr>
              </table>
            </div>
            <div class="summary-section">
              <h5 class="summary-section-title">Resources</h5>
              <table class="summary-table">
                <tr><td>CPU</td><td>{{ formData.cores }} core(s){{ formData.cpulimit ? ', limit ' + formData.cpulimit : '' }}</td></tr>
                <tr><td>Memory</td><td>{{ formData.memory }} MB</td></tr>
                <tr><td>Swap</td><td>{{ formData.swap }} MB</td></tr>
              </table>
            </div>
            <div class="summary-section">
              <h5 class="summary-section-title">Network</h5>
              <table class="summary-table">
                <tr v-for="(iface, i) in netInterfaces" :key="i">
                  <td>net{{ i }}</td>
                  <td>{{ iface.bridge }}{{ iface.vlan ? ' tag=' + iface.vlan : '' }}
                    — {{ iface.dhcp ? 'DHCP' : iface.ip_cidr }}</td>
                </tr>
                <tr v-if="formData.nameserver"><td>DNS</td><td>{{ formData.nameserver }}</td></tr>
              </table>
            </div>
            <div class="summary-section">
              <h5 class="summary-section-title">Features</h5>
              <table class="summary-table">
                <tr v-for="feat in enabledFeatures" :key="feat">
                  <td>{{ feat }}</td><td>Enabled</td>
                </tr>
                <tr v-if="enabledFeatures.length === 0">
                  <td colspan="2" style="color:var(--text-secondary)">None</td>
                </tr>
              </table>
            </div>
          </div>

          <div class="form-actions">
            <button type="submit" class="btn btn-primary btn-lg" :disabled="creating || !selectedNode">
              <span v-if="creating"><span class="btn-spinner"></span>Creating Container...</span>
              <span v-else>Create LXC Container</span>
            </button>
            <router-link to="/containers" class="btn btn-outline">Cancel</router-link>
          </div>
        </div>

        <!-- Bottom nav -->
        <div class="tab-nav-footer">
          <button type="button" class="btn btn-outline" @click="prevTab" :disabled="tabIndex === 0">← Previous</button>
          <span class="tab-position">{{ tabIndex + 1 }} / {{ tabs.length }}</span>
          <button type="button" class="btn btn-outline" @click="nextTab" :disabled="tabIndex === tabs.length - 1">Next →</button>
        </div>

      </form>
    </div>
  </div>

  <!-- Progress Modal -->
  <Teleport to="body">
    <div v-show="showProgressModal" class="modal">
      <div class="modal-content progress-modal">
        <div class="modal-header">
          <h3>{{ progressStatus === 'error' ? 'Creation Failed' : 'Creating Container' }}</h3>
        </div>
        <div class="modal-body">
          <div class="progress-container">
            <div v-if="progressStatus === 'creating'" class="spinner-container"><div class="spinner"></div></div>
            <div v-else-if="progressStatus === 'done'" class="success-icon">✓</div>
            <div v-else-if="progressStatus === 'error'" class="error-icon">✕</div>
            <h4 class="progress-vm-name">{{ formData.hostname || 'Container' }}</h4>
            <div class="progress-steps"><div class="current-step">{{ progressMessage }}</div></div>
            <div v-if="progressError" class="progress-error"><strong>Error:</strong> {{ progressError }}</div>
          </div>
        </div>
        <div class="modal-footer">
          <button v-if="progressStatus === 'done' || progressStatus === 'error'" @click="closeProgressModal" class="btn btn-primary">
            {{ progressStatus === 'done' ? 'Go to Containers' : 'Close' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script>
import { useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import { detectOs, templateDisplayName } from '@/utils/osIcons'
import LXCTemplateLibrary from '@/components/LXCTemplateLibrary.vue'
import { rules, validate } from '@/utils/formValidation'

export default {
  name: 'CreateLXC',

  components: { LXCTemplateLibrary },

  data() {
    return {
      // Tabs
      tabs: [
        { id: 'general', label: 'General', icon: '⚙️' },
        { id: 'template', label: 'Template', icon: '📦' },
        { id: 'storage', label: 'Storage', icon: '💿' },
        { id: 'resources', label: 'Resources', icon: '📊' },
        { id: 'network', label: 'Network', icon: '🌐' },
        { id: 'features', label: 'Features', icon: '🔧' },
        { id: 'confirm', label: 'Confirm', icon: '✅' },
      ],
      activeTab: 'general',

      // State
      hosts: [],
      nodes: [],
      storageList: [],
      templates: [],
      networkList: [],
      selectedHostId: '',
      selectedNode: '',

      // Validation rules and per-field errors
      rules,
      fieldErrors: {
        vmid: '',
        hostname: '',
        password: '',
        memory: '',
        cores: '',
      },

      // Template selection
      templateSource: 'local', // 'local' | 'library'
      selectedLibraryTemplate: '',
      libraryTargetStorage: '',

      // Loading
      loadingNodes: false,
      loadingStorage: false,
      loadingNetwork: false,
      loadingTemplates: false,
      creating: false,

      // Progress modal
      showProgressModal: false,
      progressStatus: 'creating',
      progressMessage: 'Submitting request...',
      progressError: '',

      // Additional mount points
      mountPoints: [],

      // Network interfaces (net0, net1, ...)
      netInterfaces: [
        { bridge: '', vlan: null, dhcp: true, ip_cidr: '', gateway: '' }
      ],

      // Form payload
      formData: {
        vmid: null,
        hostname: '',
        password: '',
        description: '',
        unprivileged: true,
        start: true,
        onboot: false,
        ostemplate: '',
        storage: '',
        rootfs_size: 8,
        cores: 1,
        memory: 512,
        swap: 512,
        cpulimit: null,
        cpuunits: null,
        shares: null,
        startup_order: null,
        startup_up: null,
        startup_down: null,
        nameserver: '',
        searchdomain: '',
        protection: false,
        features: {
          fuse: false,
          keyctl: false,
          nesting: false,
          nfs: false,
          cifs: false,
          mknod: false,
        }
      },

      // LXC library templates
      lxcLibraryTemplates: [
        { id: 'alpine-3.19', icon: '🏔️', name: 'Alpine Linux', version: '3.19', desc: 'Ultra-minimal, ~5 MB. Great for microservices.' },
        { id: 'debian-12', icon: '🌀', name: 'Debian', version: '12 (Bookworm)', desc: 'Stable, widely compatible.' },
        { id: 'ubuntu-22.04', icon: '🟠', name: 'Ubuntu', version: '22.04 LTS', desc: 'Popular LTS, broad package support.' },
        { id: 'ubuntu-24.04', icon: '🟠', name: 'Ubuntu', version: '24.04 LTS', desc: 'Latest LTS release.' },
        { id: 'centos-stream-9', icon: '🎩', name: 'CentOS Stream', version: '9', desc: 'RHEL-compatible upstream.' },
        { id: 'rocky-9', icon: '🪨', name: 'Rocky Linux', version: '9', desc: 'RHEL-compatible community distro.' },
        { id: 'fedora-40', icon: '🎩', name: 'Fedora', version: '40', desc: 'Cutting-edge packages, Red Hat upstream.' },
        { id: 'archlinux', icon: '⚙️', name: 'Arch Linux', version: 'Rolling', desc: 'Rolling release, up-to-date packages.' },
        { id: 'opensuse-leap-15', icon: '🦎', name: 'openSUSE Leap', version: '15.6', desc: 'Stable SUSE-based distribution.' },
        { id: 'gentoo', icon: '🐉', name: 'Gentoo', version: 'Latest', desc: 'Source-based, highly optimized.' },
        { id: 'devuan-5', icon: '🌀', name: 'Devuan', version: '5 (Daedalus)', desc: 'Debian without systemd.' },
      ],

      containerFeatures: [
        { key: 'nesting', label: 'Nesting', desc: 'Allow running Docker or LXC inside the container.', requiresPrivileged: false },
        { key: 'keyctl', label: 'keyctl', desc: 'Allow use of the keyctl system call.', requiresPrivileged: false },
        { key: 'fuse', label: 'FUSE', desc: 'Allow FUSE filesystem mounts inside the container.', requiresPrivileged: false },
        { key: 'nfs', label: 'NFS', desc: 'Allow NFS mounts (requires nfsd kernel module).', requiresPrivileged: true },
        { key: 'cifs', label: 'SMB/CIFS', desc: 'Allow CIFS/SMB mounts inside the container.', requiresPrivileged: false },
        { key: 'mknod', label: 'mknod', desc: 'Allow mknod for privileged device creation.', requiresPrivileged: true },
      ],
    }
  },

  computed: {
    tabIndex() {
      return this.tabs.findIndex(t => t.id === this.activeTab)
    },

    selectedTemplateOs() {
      if (!this.formData.ostemplate) return { icon: '📦', name: '', color: '#555' }
      return detectOs(this.formData.ostemplate)
    },

    selectedTemplateDisplayName() {
      if (!this.formData.ostemplate) return ''
      return templateDisplayName(this.formData.ostemplate)
    },
    diskStorageList() {
      return [...this.storageList]
        .filter(s => s.content && (s.content.includes('rootdir') || s.content.includes('images')))
        .sort((a, b) => a.storage.localeCompare(b.storage, undefined, { numeric: true, sensitivity: 'base' }))
    },
    templateStorages() {
      return this.storageList.filter(s => s.content && s.content.includes('vztmpl'))
    },
    bridgeList() {
      return [...this.networkList]
        .filter(n => n.type === 'bridge' || n.iface?.startsWith('vmbr'))
        .sort((a, b) => a.iface.localeCompare(b.iface, undefined, { numeric: true, sensitivity: 'base' }))
    },
    enabledFeatures() {
      return Object.entries(this.formData.features).filter(([, v]) => v).map(([k]) => k)
    },
  },

  async mounted() {
    await this.loadHosts()
  },

  methods: {
    // Expose validate() to template inline expressions
    validate,

    prevTab() {
      if (this.tabIndex > 0) this.activeTab = this.tabs[this.tabIndex - 1].id
    },
    nextTab() {
      if (this.tabIndex < this.tabs.length - 1) this.activeTab = this.tabs[this.tabIndex + 1].id
    },

    async loadHosts() {
      try {
        const r = await api.proxmox.listHosts()
        this.hosts = r.data.filter(h => h.is_active)
      } catch (e) { console.error(e) }
    },

    async onHostChange() {
      this.selectedNode = ''
      this.nodes = []
      this.storageList = []
      this.networkList = []
      this.templates = []
      this.formData.storage = ''
      this.formData.ostemplate = ''
      this.formData.vmid = null
      this.netInterfaces = [{ bridge: '', vlan: null, dhcp: true, ip_cidr: '', gateway: '' }]
      if (!this.selectedHostId) return

      this.loadingNodes = true
      try {
        const [nodesResp, nextIdResp] = await Promise.all([
          api.proxmox.listNodes(this.selectedHostId),
          api.pveNode.nextId(this.selectedHostId)
        ])
        this.nodes = nodesResp.data.map(n => ({ node: n.node || n.node_name || n.name, ...n }))
        if (nextIdResp.data?.nextid) this.formData.vmid = parseInt(nextIdResp.data.nextid)
        else if (typeof nextIdResp.data === 'number') this.formData.vmid = nextIdResp.data
      } catch (e) {
        console.error(e)
      } finally {
        this.loadingNodes = false
      }
    },

    async onNodeChange() {
      this.storageList = []
      this.networkList = []
      this.templates = []
      this.formData.storage = ''
      this.formData.ostemplate = ''
      this.netInterfaces[0].bridge = ''
      if (!this.selectedNode) return
      await Promise.all([this.loadStorage(), this.loadNetwork()])
      await this.loadTemplates()
    },

    async loadStorage() {
      this.loadingStorage = true
      try {
        const r = await api.pveNode.listStorage(this.selectedHostId, this.selectedNode)
        const list = Array.isArray(r.data) ? r.data : (r.data.storage || [])
        this.storageList = list
        const diskStorages = list.filter(s => s.content && (s.content.includes('rootdir') || s.content.includes('images')))
          .sort((a, b) => a.storage.localeCompare(b.storage, undefined, { numeric: true, sensitivity: 'base' }))
        if (diskStorages.length > 0) {
          const first = diskStorages.find(s => s.enabled && s.active) || diskStorages[0]
          this.formData.storage = first.storage
        }
        // Set library template target
        const tmplStorages = list.filter(s => s.content?.includes('vztmpl'))
        if (tmplStorages.length > 0) this.libraryTargetStorage = tmplStorages[0].storage
      } catch (e) { console.error(e) } finally { this.loadingStorage = false }
    },

    async loadNetwork() {
      this.loadingNetwork = true
      try {
        const r = await api.pveNode.listNetwork(this.selectedHostId, this.selectedNode)
        const list = Array.isArray(r.data) ? r.data : (r.data.network || [])
        this.networkList = list
        const bridges = list.filter(n => n.type === 'bridge' || n.iface?.startsWith('vmbr'))
          .sort((a, b) => a.iface.localeCompare(b.iface, undefined, { numeric: true, sensitivity: 'base' }))
        if (bridges.length > 0) {
          const first = bridges.find(b => b.active) || bridges[0]
          this.netInterfaces[0].bridge = first.iface
        }
      } catch (e) { console.error(e) } finally { this.loadingNetwork = false }
    },

    async loadTemplates() {
      this.loadingTemplates = true
      try {
        const templateStorages = this.storageList.filter(s => s.content?.includes('vztmpl'))
        const all = []
        for (const stor of templateStorages) {
          try {
            const r = await api.pveNode.browseStorage(this.selectedHostId, this.selectedNode, stor.storage, { content: 'vztmpl' })
            const items = Array.isArray(r.data) ? r.data : (r.data.content || [])
            all.push(...items)
          } catch (e) { console.warn(`Cannot browse ${stor.storage}:`, e) }
        }
        this.templates = all
        if (all.length > 0) this.formData.ostemplate = all[0].volid
      } catch (e) { console.error(e) } finally { this.loadingTemplates = false }
    },

    selectStorage(name) {
      const s = this.storageList.find(s => s.storage === name)
      if (s && s.enabled && s.active) this.formData.storage = name
    },

    setDefaultBridge(iface) {
      if (this.netInterfaces.length > 0) this.netInterfaces[0].bridge = iface
    },

    selectLibraryTemplate(tmpl) {
      this.selectedLibraryTemplate = tmpl.id
      // Set a placeholder template name; actual download happens on Proxmox side
      this.formData.ostemplate = `${this.libraryTargetStorage || 'local'}:vztmpl/${tmpl.id}-amd64.tar.xz`
    },

    onTemplateSelected(tmpl) {
      if (!tmpl) {
        this.formData.ostemplate = ''
        return
      }
      this.formData.ostemplate = tmpl.volid
      // Auto-detect OS type for informational display (no separate os-type field to fill here)
    },

    addMountPoint() {
      this.mountPoints.push({ storage: this.formData.storage || '', size: 8, mountpoint: `/mnt/mp${this.mountPoints.length}` })
    },
    removeMountPoint(idx) { this.mountPoints.splice(idx, 1) },

    addNetInterface() {
      const defaultBridge = this.bridgeList[0]?.iface || ''
      this.netInterfaces.push({ bridge: defaultBridge, vlan: null, dhcp: true, ip_cidr: '', gateway: '' })
    },
    removeNetInterface(idx) { if (idx > 0) this.netInterfaces.splice(idx, 1) },

    getStorageUsagePercent(storage) {
      if (!storage.total || storage.total === 0) return 0
      return Math.round(((storage.total - (storage.available || 0)) / storage.total) * 100)
    },

    formatBytes(bytes) {
      if (!bytes) return '0 B'
      const gb = bytes / (1024 * 1024 * 1024)
      if (gb >= 1) return gb.toFixed(2) + ' GB'
      return (bytes / (1024 * 1024)).toFixed(0) + ' MB'
    },

    validateForm() {
      const errors = []

      // Reset per-field errors
      Object.keys(this.fieldErrors).forEach(k => { this.fieldErrors[k] = '' })

      if (!this.selectedHostId) errors.push('Proxmox host must be selected')
      if (!this.selectedNode) errors.push('Node must be selected')

      // CT ID
      const vmidErr = validate(this.formData.vmid, [rules.required, rules.vmId])
      if (vmidErr !== true) { this.fieldErrors.vmid = vmidErr; errors.push(`CT ID: ${vmidErr}`) }

      // Hostname
      const hostnameErr = validate(this.formData.hostname, [rules.required, rules.hostname])
      if (hostnameErr !== true) { this.fieldErrors.hostname = hostnameErr; errors.push(`Hostname: ${hostnameErr}`) }

      // Password
      const pwErr = validate(this.formData.password, [rules.required, rules.password(8)])
      if (pwErr !== true) { this.fieldErrors.password = pwErr; errors.push(`Password: ${pwErr}`) }

      // Memory
      const memErr = validate(this.formData.memory, [rules.required, rules.intRange(64, 4194304)])
      if (memErr !== true) { this.fieldErrors.memory = memErr; errors.push(`Memory: ${memErr}`) }

      // Cores
      const coresErr = validate(this.formData.cores, [rules.required, rules.intRange(1, 512)])
      if (coresErr !== true) { this.fieldErrors.cores = coresErr; errors.push(`CPU cores: ${coresErr}`) }

      if (!this.formData.ostemplate) errors.push('OS template must be selected')
      if (!this.formData.storage) errors.push('Root disk storage must be selected')

      this.netInterfaces.forEach((iface, i) => {
        if (!iface.bridge) errors.push(`net${i}: bridge must be selected`)
        if (!iface.dhcp) {
          const ipErr = validate(iface.ip_cidr, [rules.required, rules.ipOrCidr])
          if (ipErr !== true) errors.push(`net${i} IP/CIDR: ${ipErr}`)
          const gwErr = validate(iface.gateway, [rules.required, rules.ipAddress])
          if (gwErr !== true) errors.push(`net${i} Gateway: ${gwErr}`)
        }
      })

      return errors
    },

    buildPayload() {
      const rootfs = `${this.formData.storage}:${this.formData.rootfs_size}`

      // Build net strings
      const nets = {}
      this.netInterfaces.forEach((iface, i) => {
        let net = `name=eth${i},bridge=${iface.bridge}`
        if (iface.dhcp) net += ',ip=dhcp'
        else net += `,ip=${iface.ip_cidr},gw=${iface.gateway}`
        if (iface.vlan) net += `,tag=${iface.vlan}`
        nets[`net${i}`] = net
      })

      // Build mp strings
      const mps = {}
      this.mountPoints.forEach((mp, i) => {
        mps[`mp${i}`] = `${mp.storage}:${mp.size},mp=${mp.mountpoint}`
      })

      // Features string
      const featParts = Object.entries(this.formData.features)
        .filter(([, v]) => v)
        .map(([k]) => k)
      const featStr = featParts.join(',')

      const payload = {
        vmid: this.formData.vmid,
        hostname: this.formData.hostname,
        password: this.formData.password,
        description: this.formData.description || undefined,
        unprivileged: this.formData.unprivileged ? 1 : 0,
        start: this.formData.start ? 1 : 0,
        ostemplate: this.formData.ostemplate,
        rootfs,
        cores: this.formData.cores,
        memory: this.formData.memory,
        swap: this.formData.swap,
        ...nets,
        ...mps,
      }

      if (this.formData.cpulimit) payload.cpulimit = this.formData.cpulimit
      if (this.formData.cpuunits) payload.cpuunits = this.formData.cpuunits
      if (this.formData.nameserver) payload.nameserver = this.formData.nameserver
      if (this.formData.searchdomain) payload.searchdomain = this.formData.searchdomain
      if (this.formData.onboot) payload.onboot = 1
      if (this.formData.protection) payload.protection = 1
      if (featStr) payload.features = featStr

      // Startup config
      if (this.formData.startup_order !== null || this.formData.startup_up !== null || this.formData.startup_down !== null) {
        const parts = []
        if (this.formData.startup_order !== null) parts.push(`order=${this.formData.startup_order}`)
        if (this.formData.startup_up !== null) parts.push(`up=${this.formData.startup_up}`)
        if (this.formData.startup_down !== null) parts.push(`down=${this.formData.startup_down}`)
        if (parts.length) payload.startup = parts.join(',')
      }

      return payload
    },

    async createLXC() {
      const toast = useToast()
      const router = useRouter()

      const errors = this.validateForm()
      if (errors.length > 0) { errors.forEach(e => toast.error(e)); return }

      this.creating = true
      this.showProgressModal = true
      this.progressStatus = 'creating'
      this.progressMessage = 'Submitting container creation request...'
      this.progressError = ''

      try {
        const payload = this.buildPayload()
        console.log('Creating LXC with payload:', JSON.stringify(payload, null, 2))
        await api.pveNode.createLxc(this.selectedHostId, this.selectedNode, payload)
        this.progressStatus = 'done'
        this.progressMessage = `Container ${this.formData.hostname} (CT ${this.formData.vmid}) created successfully!`
        toast.success('LXC container created successfully!')
      } catch (error) {
        console.error('Failed to create LXC:', error)
        this.progressStatus = 'error'
        this.progressMessage = 'Container creation failed.'
        const detail = error.response?.data?.detail
        this.progressError = detail
          ? (Array.isArray(detail) ? detail.map(e => `${e.loc?.join('.')}: ${e.msg}`).join(', ') : String(detail))
          : 'An unexpected error occurred.'
      } finally {
        this.creating = false
      }
    },

    closeProgressModal() {
      this.showProgressModal = false
      if (this.progressStatus === 'done') {
        const router = useRouter()
        router.push(`/proxmox/${this.selectedHostId}/nodes/${this.selectedNode}`)
      }
    }
  }
}
</script>

<style scoped>
.create-lxc-page { max-width: 1100px; margin: 0 auto; }
.card-subtitle { color: var(--text-secondary); margin: 0.25rem 0 0; font-size: 0.9rem; }
.create-lxc-form { padding: 0 1.5rem 1.5rem; }

/* Tabs */
.lxc-tabs {
  display: flex;
  gap: 0.25rem;
  padding: 0 1.5rem;
  border-bottom: 2px solid var(--border-color);
  overflow-x: auto;
  scrollbar-width: none;
}
.lxc-tabs::-webkit-scrollbar { display: none; }
.lxc-tab {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.75rem 1rem;
  border: none;
  background: none;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  white-space: nowrap;
  transition: color 0.2s, border-color 0.2s;
}
.lxc-tab:hover { color: #14b8a6; }
.lxc-tab.active { color: #14b8a6; border-bottom-color: #14b8a6; }

/* Content */
.tab-content { padding-top: 1.5rem; min-height: 400px; }
.tab-nav-footer { display: flex; align-items: center; justify-content: space-between; padding: 1rem 0; border-top: 1px solid var(--border-color); margin-top: 2rem; }
.tab-position { color: var(--text-secondary); font-size: 0.875rem; }

/* Sections */
.form-section { margin-bottom: 1.75rem; padding-bottom: 1.75rem; border-bottom: 1px solid var(--border-color); }
.form-section:last-child { border-bottom: none; }
.section-title { font-size: 1.125rem; font-weight: 600; margin-bottom: 1.25rem; color: var(--text-primary); }
.subsection-title { font-size: 0.9375rem; font-weight: 600; color: var(--text-primary); margin: 0 0 0.875rem; }
.section-header-with-action { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.875rem; }

/* Info banner */
.info-banner { padding: 1rem 1.25rem; background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.2); border-radius: 0.5rem; color: var(--text-secondary); font-size: 0.9rem; }

/* Selected template summary card */
.selected-template-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
  margin-bottom: 1.25rem;
  border: 2px solid #14b8a6;
  border-radius: 0.5rem;
  background: rgba(20,184,166,0.06);
}
.selected-template-icon { font-size: 2rem; flex-shrink: 0; }
.selected-template-info { flex: 1; }
.selected-template-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin-bottom: 0.15rem; }
.selected-template-name { font-size: 0.9rem; font-weight: 600; color: var(--text-primary); word-break: break-all; }
.selected-template-os { font-size: 0.8rem; font-weight: 500; margin-top: 0.1rem; }

/* Library templates (legacy — still used by lxcLibraryTemplates fallback) */
.library-info { font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 1rem; }
.template-library-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.875rem; }
.template-lib-card {
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  display: flex;
  align-items: flex-start;
  gap: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--background);
  position: relative;
}
.template-lib-card:hover { border-color: #14b8a6; box-shadow: 0 4px 12px rgba(20,184,166,0.12); }
.template-lib-card.selected { border-color: #14b8a6; background: rgba(20,184,166,0.08); }
.template-lib-icon { font-size: 1.75rem; flex-shrink: 0; }
.template-lib-info h6 { margin: 0 0 0.1rem; font-size: 0.9rem; font-weight: 600; }
.template-lib-version { font-size: 0.75rem; color: #14b8a6; font-weight: 500; }
.template-lib-desc { font-size: 0.78rem; color: var(--text-secondary); margin-top: 0.25rem; }
.template-selected-badge { position: absolute; top: 0.5rem; right: 0.5rem; background: #14b8a6; color: white; font-size: 0.7rem; padding: 0.1rem 0.45rem; border-radius: 9999px; font-weight: 600; }

/* Storage */
.storage-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; margin: 0.5rem 0; }
.storage-card { border: 2px solid var(--border-color); border-radius: 0.5rem; padding: 1rem; cursor: pointer; transition: all 0.2s; background: var(--background); position: relative; }
.storage-card:hover { border-color: var(--primary-color); }
.storage-card.selected { border-color: var(--primary-color); background: linear-gradient(135deg,rgba(37,99,235,0.1),rgba(147,51,234,0.1)); }
.storage-card.disabled { opacity: 0.5; cursor: not-allowed; }
.storage-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.storage-header h6 { margin: 0; font-size: 1rem; font-weight: 600; }
.storage-bar { width: 100%; height: 8px; background: var(--border-color); border-radius: 4px; overflow: hidden; margin-bottom: 0.5rem; }
.storage-bar-fill { height: 100%; background: linear-gradient(90deg, var(--primary-color), var(--secondary-color)); }
.storage-stats { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary); }
.storage-badge { position: absolute; top: 0.5rem; right: 0.5rem; }

/* Mount points */
.mount-point-row { border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.875rem; margin-bottom: 0.875rem; }
.mount-point-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }

/* Network */
.network-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 0.875rem; margin-bottom: 1rem; }
.network-card { border: 2px solid var(--border-color); border-radius: 0.5rem; padding: 0.875rem; cursor: pointer; transition: all 0.2s; background: var(--background); }
.network-card:hover { border-color: #14b8a6; }
.network-card.selected { border-color: #14b8a6; background: rgba(20,184,166,0.08); }
.network-card.disabled { opacity: 0.5; cursor: not-allowed; }
.network-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.network-header h6 { margin: 0; font-size: 0.9rem; font-weight: 600; }
.network-info { font-size: 0.8rem; color: var(--text-secondary); }
.nic-row { border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; }
.nic-row-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border-color); }
.nic-label { font-family: monospace; font-size: 0.875rem; font-weight: 600; color: #14b8a6; }

/* Features */
.feature-note { font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1rem; }
.features-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 0.75rem; }
.feature-card { display: flex; align-items: flex-start; gap: 0.75rem; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.875rem; cursor: pointer; transition: border-color 0.2s; }
.feature-card:hover { border-color: #14b8a6; }
.feature-card input[type=checkbox] { margin-top: 0.15rem; flex-shrink: 0; }
.feature-card-title { font-weight: 600; font-size: 0.875rem; color: var(--text-primary); }
.feature-card-desc { font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.15rem; }
.feature-card-warning { font-size: 0.75rem; color: #f59e0b; margin-top: 0.25rem; }

/* Summary */
.summary-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.25rem; margin-bottom: 1.5rem; }
.summary-section { border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1rem; background: var(--background); }
.summary-section-title { font-size: 0.875rem; font-weight: 700; color: #14b8a6; margin: 0 0 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.summary-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
.summary-table tr { border-bottom: 1px solid var(--border-color); }
.summary-table tr:last-child { border-bottom: none; }
.summary-table td { padding: 0.3rem 0; }
.summary-table td:first-child { color: var(--text-secondary); width: 40%; }
.summary-table td:last-child { font-weight: 500; color: var(--text-primary); word-break: break-all; }

/* Misc */
.disk-label { font-family: monospace; font-size: 0.875rem; font-weight: 600; color: var(--primary-color); }
.btn-icon-danger { background: none; border: 1px solid #ef4444; color: #ef4444; border-radius: 0.25rem; padding: 0.2rem 0.5rem; cursor: pointer; font-size: 0.8rem; }
.btn-icon-danger:hover { background: #fee2e2; }
.loading-message { text-align: center; padding: 2rem; color: var(--text-secondary); }
.loading-spinner { width: 32px; height: 32px; border: 3px solid var(--border-color); border-top-color: #14b8a6; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 0.75rem; }
.badge-sm { padding: 0.125rem 0.5rem; font-size: 0.75rem; }
.form-actions { display: flex; gap: 1rem; align-items: center; padding-top: 1rem; }
.btn-lg { padding: 0.75rem 2rem; font-size: 1rem; }
.btn-sm { padding: 0.3rem 0.75rem; font-size: 0.8rem; }
.btn-spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.4); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 0.5rem; }
.form-help { display: block; margin-top: 0.25rem; font-size: 0.8rem; color: var(--text-secondary); }
.form-error-text { display: block; margin-top: 0.25rem; font-size: 0.78rem; color: #ef4444; }
.form-error-text::before { content: '⚠ '; }
.input-error { border-color: #ef4444 !important; box-shadow: 0 0 0 2px rgba(239,68,68,0.15) !important; }
.input-error:focus { border-color: #ef4444 !important; box-shadow: 0 0 0 3px rgba(239,68,68,0.2) !important; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Modal */
.modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.progress-modal { background: var(--card-bg, white); border-radius: 0.5rem; max-width: 500px; width: 90%; box-shadow: var(--shadow-lg); }
.modal-header { padding: 1.5rem; border-bottom: 1px solid var(--border-color); }
.modal-header h3 { margin: 0; font-size: 1.5rem; font-weight: 600; }
.modal-body { padding: 2rem 1.5rem; }
.modal-footer { padding: 1rem 1.5rem; border-top: 1px solid var(--border-color); display: flex; justify-content: flex-end; }
.progress-container { text-align: center; }
.spinner-container { margin: 0 auto 1.5rem; width: 64px; height: 64px; }
.spinner { width: 64px; height: 64px; border: 4px solid var(--border-color); border-top-color: #14b8a6; border-radius: 50%; animation: spin 1s linear infinite; }
.success-icon { width: 64px; height: 64px; line-height: 64px; margin: 0 auto 1.5rem; font-size: 3rem; color: #10b981; background: #d1fae5; border-radius: 50%; }
.error-icon { width: 64px; height: 64px; line-height: 64px; margin: 0 auto 1.5rem; font-size: 3rem; color: #ef4444; background: #fee2e2; border-radius: 50%; }
.progress-vm-name { font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem; }
.progress-steps { margin: 1.5rem 0; padding: 1.25rem; background: #f8fafc; border-radius: 0.5rem; border-left: 4px solid #14b8a6; }
.current-step { font-size: 1rem; font-weight: 500; color: #0d9488; line-height: 1.6; animation: pulse-text 2s ease-in-out infinite; }
@keyframes pulse-text { 0%,100%{opacity:1} 50%{opacity:0.7} }
.progress-error { margin-top: 1rem; padding: 1rem; background: #fee2e2; border: 1px solid #ef4444; border-radius: 0.375rem; color: #991b1b; text-align: left; }
</style>
