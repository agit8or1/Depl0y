<template>
  <div class="create-lxc-page">
    <div class="card">
      <div class="card-header">
        <h3>Create LXC Container</h3>
      </div>

      <form @submit.prevent="createLXC" class="create-lxc-form">

        <!-- Datacenter & Node Selection -->
        <div class="form-section">
          <h4 class="section-title">Datacenter &amp; Node Selection</h4>

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
              <div class="loading-spinner"></div>
              <p>Loading nodes...</p>
            </div>
            <select v-else v-model="selectedNode" class="form-control" required @change="onNodeChange">
              <option value="">Select node...</option>
              <option v-for="n in nodes" :key="n.node" :value="n.node">
                {{ n.node }}
              </option>
            </select>
          </div>
        </div>

        <!-- Basic Configuration -->
        <div v-if="selectedNode" class="form-section">
          <h4 class="section-title">Basic Configuration</h4>

          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">CT ID *</label>
              <input
                v-model.number="formData.vmid"
                type="number"
                min="100"
                class="form-control"
                required
                placeholder="Auto-assigned"
              />
              <small class="form-help">Container ID (min 100)</small>
            </div>

            <div class="form-group">
              <label class="form-label">Hostname *</label>
              <input
                v-model="formData.hostname"
                type="text"
                class="form-control"
                required
                placeholder="my-container"
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Root Password *</label>
            <input
              v-model="formData.password"
              type="password"
              class="form-control"
              required
              autocomplete="new-password"
              placeholder="Root password inside the container"
            />
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="formData.unprivileged" style="margin-right: 8px;" />
                Unprivileged Container
              </label>
              <div class="form-text">Recommended for security — runs as non-root on host</div>
            </div>

            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="formData.start" style="margin-right: 8px;" />
                Start after create
              </label>
              <div class="form-text">Automatically start container once created</div>
            </div>
          </div>
        </div>

        <!-- Template -->
        <div v-if="selectedNode" class="form-section">
          <h4 class="section-title">Template</h4>

          <div v-if="loadingTemplates" class="loading-message">
            <div class="loading-spinner"></div>
            <p>Loading templates...</p>
          </div>

          <div v-else-if="templates.length === 0" class="text-muted text-center">
            <p>No LXC templates found. Upload a template to a storage with <code>vztmpl</code> content.</p>
          </div>

          <div v-else class="form-group">
            <label class="form-label">OS Template *</label>
            <select v-model="formData.ostemplate" class="form-control" required>
              <option value="">Select template...</option>
              <option v-for="t in templates" :key="t.volid" :value="t.volid">
                {{ t.volid }}
              </option>
            </select>
            <small class="form-help">Templates found across storages with vztmpl content</small>
          </div>
        </div>

        <!-- Storage -->
        <div v-if="selectedNode" class="form-section">
          <h4 class="section-title">Storage</h4>

          <div v-if="loadingStorage" class="loading-message">
            <div class="loading-spinner"></div>
            <p>Loading storage pools...</p>
          </div>

          <div v-else-if="diskStorageList.length === 0" class="text-muted text-center">
            <p>No writable storage pools available on this node.</p>
          </div>

          <div v-else>
            <div class="form-group">
              <label class="form-label">Root Disk Storage *</label>
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
                  <div v-if="storage.shared" class="storage-badge">
                    <span class="badge badge-success">Shared</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Disk Size (GB) *</label>
              <input
                v-model.number="formData.rootfs_size"
                type="number"
                min="1"
                class="form-control"
                required
              />
            </div>
          </div>
        </div>

        <!-- Resource Allocation -->
        <div v-if="selectedNode" class="form-section">
          <h4 class="section-title">Resource Allocation</h4>

          <div class="grid grid-cols-4 gap-2">
            <div class="form-group">
              <label class="form-label">CPU Cores *</label>
              <input
                v-model.number="formData.cores"
                type="number"
                min="1"
                max="128"
                class="form-control"
                required
              />
            </div>

            <div class="form-group">
              <label class="form-label">Memory (MB) *</label>
              <input
                v-model.number="formData.memory"
                type="number"
                min="64"
                step="64"
                class="form-control"
                required
              />
            </div>

            <div class="form-group">
              <label class="form-label">Swap (MB)</label>
              <input
                v-model.number="formData.swap"
                type="number"
                min="0"
                step="64"
                class="form-control"
              />
            </div>

            <div class="form-group">
              <label class="form-label">CPU Limit (optional)</label>
              <input
                v-model.number="formData.cpulimit"
                type="number"
                min="0"
                max="128"
                class="form-control"
                placeholder="0 = unlimited"
              />
              <small class="form-help">0 = no limit</small>
            </div>
          </div>
        </div>

        <!-- Network -->
        <div v-if="selectedNode" class="form-section">
          <h4 class="section-title">Network Configuration</h4>

          <div v-if="loadingNetwork" class="loading-message">
            <div class="loading-spinner"></div>
            <p>Loading network interfaces...</p>
          </div>

          <div v-else-if="bridgeList.length === 0" class="text-muted text-center">
            <p>No network bridges found on this node.</p>
          </div>

          <div v-else>
            <div class="form-group">
              <label class="form-label">Network Bridge *</label>
              <div class="network-cards">
                <div
                  v-for="net in bridgeList"
                  :key="net.iface"
                  :class="['network-card', { 'selected': formData.net_bridge === net.iface, 'disabled': !net.active }]"
                  @click="selectBridge(net.iface)"
                >
                  <div class="network-header">
                    <h6>{{ net.iface }}</h6>
                    <span :class="['badge', 'badge-sm', net.active ? 'badge-success' : 'badge-danger']">
                      {{ net.active ? 'Active' : 'Inactive' }}
                    </span>
                  </div>
                  <div class="network-info">
                    <div v-if="net.address" class="text-xs">
                      <strong>IP:</strong> {{ net.address }}{{ net.netmask ? '/' + net.netmask : '' }}
                    </div>
                    <div v-if="net.bridge_ports" class="text-xs">
                      <strong>Ports:</strong> {{ net.bridge_ports }}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="useDHCP" style="margin-right: 8px;" />
                Use DHCP (automatic IP)
              </label>
            </div>

            <div v-if="!useDHCP" class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">IP Address / CIDR *</label>
                <input
                  v-model="formData.ip_cidr"
                  type="text"
                  class="form-control"
                  placeholder="192.168.1.100/24"
                />
                <small class="form-help">e.g. 192.168.1.100/24</small>
              </div>

              <div class="form-group">
                <label class="form-label">Gateway *</label>
                <input
                  v-model="formData.gateway"
                  type="text"
                  class="form-control"
                  placeholder="192.168.1.1"
                />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">VLAN Tag (optional)</label>
              <input
                v-model.number="formData.vlan"
                type="number"
                min="1"
                max="4094"
                class="form-control"
                placeholder="Leave empty for no VLAN"
              />
              <small class="form-help">VLAN ID 1–4094, or leave blank</small>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div v-if="selectedNode" class="form-actions">
          <button type="submit" class="btn btn-primary" :disabled="creating">
            {{ creating ? 'Creating Container...' : 'Create LXC Container' }}
          </button>
          <router-link to="/containers" class="btn btn-outline">
            Cancel
          </router-link>
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
            <div v-if="progressStatus === 'creating'" class="spinner-container">
              <div class="spinner"></div>
            </div>
            <div v-else-if="progressStatus === 'done'" class="success-icon">✓</div>
            <div v-else-if="progressStatus === 'error'" class="error-icon">✕</div>

            <h4 class="progress-vm-name">{{ formData.hostname || 'Container' }}</h4>

            <div class="progress-steps">
              <div class="current-step">{{ progressMessage }}</div>
            </div>

            <div v-if="progressError" class="progress-error">
              <strong>Error:</strong> {{ progressError }}
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button
            v-if="progressStatus === 'done' || progressStatus === 'error'"
            @click="closeProgressModal"
            class="btn btn-primary"
          >
            {{ progressStatus === 'done' ? 'Go to Node' : 'Close' }}
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

export default {
  name: 'CreateLXC',

  data() {
    return {
      // State
      hosts: [],
      nodes: [],
      storageList: [],
      templates: [],
      networkList: [],
      selectedHostId: '',
      selectedNode: '',
      useDHCP: true,

      // Loading flags
      loadingNodes: false,
      loadingStorage: false,
      loadingNetwork: false,
      loadingTemplates: false,
      creating: false,

      // Progress modal
      showProgressModal: false,
      progressStatus: 'creating', // 'creating' | 'done' | 'error'
      progressMessage: 'Submitting request...',
      progressError: '',

      // Form payload
      formData: {
        vmid: null,
        hostname: '',
        password: '',
        unprivileged: true,
        start: true,
        ostemplate: '',
        storage: '',
        rootfs_size: 8,
        cores: 1,
        memory: 512,
        swap: 512,
        cpulimit: null,
        net_bridge: '',
        ip_cidr: '',
        gateway: '',
        vlan: null,
      }
    }
  },

  computed: {
    diskStorageList() {
      return [...this.storageList]
        .filter(s => s.content && (
          s.content.includes('rootdir') || s.content.includes('images')
        ))
        .sort((a, b) => a.storage.localeCompare(b.storage, undefined, { numeric: true, sensitivity: 'base' }))
    },

    bridgeList() {
      return [...this.networkList]
        .filter(n => n.type === 'bridge' || n.iface?.startsWith('vmbr'))
        .sort((a, b) => a.iface.localeCompare(b.iface, undefined, { numeric: true, sensitivity: 'base' }))
    }
  },

  async mounted() {
    await this.loadHosts()
  },

  methods: {
    async loadHosts() {
      try {
        const response = await api.proxmox.listHosts()
        this.hosts = response.data.filter(h => h.is_active)
      } catch (error) {
        console.error('Failed to load hosts:', error)
      }
    },

    async onHostChange() {
      this.selectedNode = ''
      this.nodes = []
      this.storageList = []
      this.networkList = []
      this.templates = []
      this.formData.storage = ''
      this.formData.net_bridge = ''
      this.formData.ostemplate = ''
      this.formData.vmid = null

      if (!this.selectedHostId) return

      // Fetch next CT ID and nodes in parallel
      this.loadingNodes = true
      try {
        const [nodesResp, nextIdResp] = await Promise.all([
          api.proxmox.listNodes(this.selectedHostId),
          api.pveNode.nextId(this.selectedHostId)
        ])
        this.nodes = nodesResp.data.map(n => ({ node: n.node || n.node_name || n.name, ...n }))
        if (nextIdResp.data && nextIdResp.data.nextid) {
          this.formData.vmid = parseInt(nextIdResp.data.nextid)
        } else if (typeof nextIdResp.data === 'number') {
          this.formData.vmid = nextIdResp.data
        }
      } catch (error) {
        console.error('Failed to load nodes/nextid:', error)
        this.$toast?.error('Failed to load nodes.')
      } finally {
        this.loadingNodes = false
      }
    },

    async onNodeChange() {
      this.storageList = []
      this.networkList = []
      this.templates = []
      this.formData.storage = ''
      this.formData.net_bridge = ''
      this.formData.ostemplate = ''

      if (!this.selectedNode) return

      await Promise.all([
        this.loadStorage(),
        this.loadNetwork()
      ])
      // Load templates after storage is loaded (needs template storages)
      await this.loadTemplates()
    },

    async loadStorage() {
      this.loadingStorage = true
      try {
        const response = await api.pveNode.listStorage(this.selectedHostId, this.selectedNode)
        // listStorage returns array directly or nested
        const list = Array.isArray(response.data) ? response.data : (response.data.storage || [])
        this.storageList = list

        // Auto-select first disk storage
        const diskStorages = list.filter(s => s.content && (
          s.content.includes('rootdir') || s.content.includes('images')
        )).sort((a, b) => a.storage.localeCompare(b.storage, undefined, { numeric: true, sensitivity: 'base' }))

        if (diskStorages.length > 0) {
          const first = diskStorages.find(s => s.enabled && s.active) || diskStorages[0]
          this.formData.storage = first.storage
        }
      } catch (error) {
        console.error('Failed to load storage:', error)
      } finally {
        this.loadingStorage = false
      }
    },

    async loadNetwork() {
      this.loadingNetwork = true
      try {
        const response = await api.pveNode.listNetwork(this.selectedHostId, this.selectedNode)
        const list = Array.isArray(response.data) ? response.data : (response.data.network || [])
        this.networkList = list

        // Auto-select first active bridge
        const bridges = list
          .filter(n => n.type === 'bridge' || n.iface?.startsWith('vmbr'))
          .sort((a, b) => a.iface.localeCompare(b.iface, undefined, { numeric: true, sensitivity: 'base' }))

        if (bridges.length > 0) {
          const first = bridges.find(b => b.active) || bridges[0]
          this.formData.net_bridge = first.iface
        }
      } catch (error) {
        console.error('Failed to load network:', error)
      } finally {
        this.loadingNetwork = false
      }
    },

    async loadTemplates() {
      this.loadingTemplates = true
      try {
        // Find storages that have vztmpl content
        const templateStorages = this.storageList.filter(
          s => s.content && s.content.includes('vztmpl')
        )

        const allTemplates = []
        for (const stor of templateStorages) {
          try {
            const resp = await api.pveNode.browseStorage(
              this.selectedHostId,
              this.selectedNode,
              stor.storage,
              { content: 'vztmpl' }
            )
            const items = Array.isArray(resp.data) ? resp.data : (resp.data.content || [])
            allTemplates.push(...items)
          } catch (e) {
            console.warn(`Could not browse storage ${stor.storage}:`, e)
          }
        }

        this.templates = allTemplates

        // Auto-select first template
        if (allTemplates.length > 0) {
          this.formData.ostemplate = allTemplates[0].volid
        }
      } catch (error) {
        console.error('Failed to load templates:', error)
      } finally {
        this.loadingTemplates = false
      }
    },

    selectStorage(storageName) {
      const storage = this.storageList.find(s => s.storage === storageName)
      if (storage && storage.enabled && storage.active) {
        this.formData.storage = storageName
      }
    },

    selectBridge(bridgeName) {
      const bridge = this.networkList.find(n => n.iface === bridgeName)
      if (bridge && bridge.active) {
        this.formData.net_bridge = bridgeName
      }
    },

    getStorageUsagePercent(storage) {
      if (!storage.total || storage.total === 0) return 0
      return Math.round(((storage.total - (storage.available || 0)) / storage.total) * 100)
    },

    formatBytes(bytes) {
      if (!bytes) return '0 B'
      const gb = bytes / (1024 * 1024 * 1024)
      if (gb >= 1) return gb.toFixed(2) + ' GB'
      const mb = bytes / (1024 * 1024)
      return mb.toFixed(0) + ' MB'
    },

    validateForm() {
      const errors = []
      if (!this.selectedHostId) errors.push('Proxmox host must be selected')
      if (!this.selectedNode) errors.push('Node must be selected')
      if (!this.formData.vmid || this.formData.vmid < 100) errors.push('CT ID must be 100 or greater')
      if (!this.formData.hostname.trim()) errors.push('Hostname is required')
      if (!this.formData.password) errors.push('Root password is required')
      if (!this.formData.ostemplate) errors.push('OS template must be selected')
      if (!this.formData.storage) errors.push('Root disk storage must be selected')
      if (!this.formData.net_bridge) errors.push('Network bridge must be selected')
      if (!this.useDHCP) {
        if (!this.formData.ip_cidr.trim()) errors.push('IP address/CIDR is required when not using DHCP')
        if (!this.formData.gateway.trim()) errors.push('Gateway is required when not using DHCP')
      }
      return errors
    },

    buildPayload() {
      // Build the rootfs string: storage:size
      const rootfs = `${this.formData.storage}:${this.formData.rootfs_size}`

      // Build net0 string
      let net0 = `name=eth0,bridge=${this.formData.net_bridge}`
      if (this.useDHCP) {
        net0 += ',ip=dhcp'
      } else {
        net0 += `,ip=${this.formData.ip_cidr},gw=${this.formData.gateway}`
      }
      if (this.formData.vlan) {
        net0 += `,tag=${this.formData.vlan}`
      }

      const payload = {
        vmid: this.formData.vmid,
        hostname: this.formData.hostname,
        password: this.formData.password,
        unprivileged: this.formData.unprivileged ? 1 : 0,
        start: this.formData.start ? 1 : 0,
        ostemplate: this.formData.ostemplate,
        rootfs,
        cores: this.formData.cores,
        memory: this.formData.memory,
        swap: this.formData.swap,
        net0,
      }

      if (this.formData.cpulimit && this.formData.cpulimit > 0) {
        payload.cpulimit = this.formData.cpulimit
      }

      return payload
    },

    async createLXC() {
      const toast = useToast()
      const router = useRouter()

      const errors = this.validateForm()
      if (errors.length > 0) {
        errors.forEach(e => toast.error(e))
        return
      }

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
        if (detail) {
          this.progressError = Array.isArray(detail)
            ? detail.map(e => `${e.loc?.join('.')}: ${e.msg}`).join(', ')
            : String(detail)
        } else {
          this.progressError = 'An unexpected error occurred.'
        }
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
.create-lxc-form {
  padding: 1.5rem;
}

.form-section {
  margin-bottom: 2rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid var(--border-color);
}

.form-section:last-of-type {
  border-bottom: none;
}

.section-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.storage-cards, .network-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
  margin-top: 0.5rem;
  margin-bottom: 1rem;
}

.storage-card, .network-card {
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--background);
  position: relative;
}

.storage-card:hover, .network-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.storage-card.selected, .network-card.selected {
  border-color: var(--primary-color);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(147, 51, 234, 0.1));
}

.storage-card.disabled, .network-card.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.storage-header, .network-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.storage-header h6, .network-header h6 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.storage-bar {
  width: 100%;
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.storage-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
  transition: width 0.3s;
}

.storage-stats {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.storage-badge {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
}

.network-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.loading-message {
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 0.75rem;
}

.badge-sm {
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
}

.form-actions {
  display: flex;
  gap: 1rem;
  padding-top: 1rem;
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
  opacity: 0.8;
}

/* Progress Modal */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.progress-modal {
  background: white;
  border-radius: 0.5rem;
  max-width: 500px;
  width: 90%;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.modal-body {
  padding: 2rem 1.5rem;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
}

.progress-container {
  text-align: center;
}

.spinner-container {
  margin: 0 auto 1.5rem;
  width: 64px;
  height: 64px;
}

.spinner {
  width: 64px;
  height: 64px;
  border: 4px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.success-icon {
  width: 64px;
  height: 64px;
  line-height: 64px;
  margin: 0 auto 1.5rem;
  font-size: 3rem;
  color: #10b981;
  background: #d1fae5;
  border-radius: 50%;
}

.error-icon {
  width: 64px;
  height: 64px;
  line-height: 64px;
  margin: 0 auto 1.5rem;
  font-size: 3rem;
  color: #ef4444;
  background: #fee2e2;
  border-radius: 50%;
}

.progress-vm-name {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.progress-steps {
  margin: 1.5rem 0;
  padding: 1.25rem;
  background: #f8fafc;
  border-radius: 0.5rem;
  border-left: 4px solid #3b82f6;
}

.current-step {
  font-size: 1rem;
  font-weight: 500;
  color: #1e40af;
  line-height: 1.6;
  animation: pulse-text 2s ease-in-out infinite;
}

@keyframes pulse-text {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.progress-error {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #fee2e2;
  border: 1px solid #ef4444;
  border-radius: 0.375rem;
  color: #991b1b;
  text-align: left;
}

.progress-error strong {
  display: block;
  margin-bottom: 0.5rem;
}
</style>
