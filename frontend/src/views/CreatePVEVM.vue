<template>
  <div class="create-pve-vm-page">
    <div class="card">
      <div class="card-header">
        <h3>Create VM (PVE Native)</h3>
        <p class="subtitle">Create a QEMU VM directly in Proxmox</p>
      </div>

      <!-- Step Indicator -->
      <div class="step-indicator">
        <div
          v-for="(label, idx) in ['Location & General', 'Hardware', 'Review & Create']"
          :key="idx"
          :class="['step', { active: currentStep === idx + 1, done: currentStep > idx + 1 }]"
          @click="currentStep > idx + 1 && (currentStep = idx + 1)"
        >
          <span class="step-num">{{ currentStep > idx + 1 ? '✓' : idx + 1 }}</span>
          <span class="step-label">{{ label }}</span>
        </div>
      </div>

      <!-- Step 1: Location & General -->
      <div v-if="currentStep === 1" class="step-body">
        <div class="form-section">
          <h4 class="section-title">Proxmox Location</h4>

          <div class="form-group">
            <label class="form-label">Host *</label>
            <select v-model="selectedHostId" class="form-control" @change="onHostChange">
              <option value="">Select a host...</option>
              <option v-for="h in hosts" :key="h.id" :value="h.id">
                {{ h.name }} ({{ h.hostname }})
              </option>
            </select>
          </div>

          <div v-if="selectedHostId" class="form-group">
            <label class="form-label">Node *</label>
            <div v-if="loadingNodes" class="loading-inline">
              <div class="loading-spinner-sm"></div> Loading nodes...
            </div>
            <select v-else v-model="selectedNode" class="form-control" @change="onNodeChange">
              <option value="">Select a node...</option>
              <option v-for="n in nodes" :key="n.node_name" :value="n.node_name">{{ n.node_name }}</option>
            </select>
          </div>
        </div>

        <div class="form-section">
          <h4 class="section-title">General Settings</h4>

          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">VM ID *</label>
              <div v-if="loadingNextId" class="loading-inline">
                <div class="loading-spinner-sm"></div> Fetching next ID...
              </div>
              <input
                v-else
                v-model.number="vmid"
                type="number"
                min="100"
                max="999999999"
                class="form-control"
                placeholder="e.g. 200"
              />
              <small class="form-help">Auto-filled from cluster next ID</small>
            </div>

            <div class="form-group">
              <label class="form-label">Name *</label>
              <input
                v-model="vmName"
                type="text"
                class="form-control"
                placeholder="e.g. my-vm"
              />
              <small class="form-help">Alphanumeric, hyphens allowed</small>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">OS Type *</label>
              <select v-model="osType" class="form-control">
                <option value="l26">Linux (6.x - 2.6 Kernel)</option>
                <option value="l24">Linux (2.4 Kernel)</option>
                <option value="win11">Windows 11/2022</option>
                <option value="win10">Windows 10/2019/2016</option>
                <option value="win8">Windows 8/2012</option>
                <option value="win7">Windows 7/2008</option>
                <option value="wxp">Windows XP/2003</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div class="form-group" style="display: flex; align-items: flex-end; padding-bottom: 0.25rem;">
              <label class="checkbox-label">
                <input type="checkbox" v-model="startAfterCreate" />
                <span>Start after creation</span>
              </label>
            </div>
          </div>
        </div>

        <div class="step-actions">
          <router-link to="/proxmox" class="btn btn-outline">Cancel</router-link>
          <button class="btn btn-primary" @click="goStep2" :disabled="!canGoStep2">
            Next: Hardware
          </button>
        </div>
      </div>

      <!-- Step 2: Hardware -->
      <div v-if="currentStep === 2" class="step-body">
        <div class="form-section">
          <h4 class="section-title">CPU & Memory</h4>
          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">CPU Cores *</label>
              <input v-model.number="cores" type="number" min="1" max="128" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Memory (MB) *</label>
              <input v-model.number="memory" type="number" min="256" step="256" class="form-control" />
            </div>
          </div>
        </div>

        <div class="form-section">
          <h4 class="section-title">Disk</h4>
          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">Disk Size (GB) *</label>
              <input v-model.number="diskSize" type="number" min="1" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Disk Storage *</label>
              <div v-if="loadingStorage" class="loading-inline">
                <div class="loading-spinner-sm"></div> Loading...
              </div>
              <select v-else v-model="diskStorage" class="form-control">
                <option value="">Select storage...</option>
                <option v-for="s in diskStorages" :key="s.storage" :value="s.storage">
                  {{ s.storage }} ({{ s.type }})
                </option>
              </select>
            </div>
          </div>
        </div>

        <div class="form-section">
          <h4 class="section-title">ISO Image</h4>
          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">ISO Storage</label>
              <div v-if="loadingStorage" class="loading-inline">
                <div class="loading-spinner-sm"></div> Loading...
              </div>
              <select v-else v-model="isoStorage" class="form-control" @change="onIsoStorageChange">
                <option value="">None (no ISO)</option>
                <option v-for="s in isoStorages" :key="s.storage" :value="s.storage">
                  {{ s.storage }} ({{ s.type }})
                </option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">ISO File</label>
              <div v-if="loadingIsos" class="loading-inline">
                <div class="loading-spinner-sm"></div> Loading ISOs...
              </div>
              <select v-else v-model="isoFile" class="form-control" :disabled="!isoStorage">
                <option value="">None</option>
                <option v-for="iso in isos" :key="iso.volid" :value="iso.volid">
                  {{ iso.volid.split('/').pop() }}
                </option>
              </select>
              <small class="form-help">{{ isoStorage ? '' : 'Select an ISO storage first' }}</small>
            </div>
          </div>
        </div>

        <div class="form-section">
          <h4 class="section-title">Network</h4>
          <div class="form-group">
            <label class="form-label">Network Bridge *</label>
            <div v-if="loadingNetwork" class="loading-inline">
              <div class="loading-spinner-sm"></div> Loading...
            </div>
            <select v-else v-model="bridge" class="form-control">
              <option value="">Select bridge...</option>
              <option v-for="net in bridges" :key="net.iface" :value="net.iface">
                {{ net.iface }}{{ net.address ? ' — ' + net.address : '' }}
              </option>
            </select>
          </div>
        </div>

        <div class="step-actions">
          <button class="btn btn-outline" @click="currentStep = 1">Back</button>
          <button class="btn btn-primary" @click="goStep3" :disabled="!canGoStep3">
            Next: Review
          </button>
        </div>
      </div>

      <!-- Step 3: Review & Create -->
      <div v-if="currentStep === 3" class="step-body">
        <div class="form-section">
          <h4 class="section-title">Review Configuration</h4>

          <div class="review-grid">
            <div class="review-group">
              <h5 class="review-group-title">Location</h5>
              <div class="review-row">
                <span class="review-label">Host</span>
                <span class="review-value">{{ hostName }}</span>
              </div>
              <div class="review-row">
                <span class="review-label">Node</span>
                <span class="review-value">{{ selectedNode }}</span>
              </div>
            </div>

            <div class="review-group">
              <h5 class="review-group-title">General</h5>
              <div class="review-row">
                <span class="review-label">VM ID</span>
                <span class="review-value">{{ vmid }}</span>
              </div>
              <div class="review-row">
                <span class="review-label">Name</span>
                <span class="review-value">{{ vmName }}</span>
              </div>
              <div class="review-row">
                <span class="review-label">OS Type</span>
                <span class="review-value">{{ osTypeLabel }}</span>
              </div>
              <div class="review-row">
                <span class="review-label">Start after create</span>
                <span class="review-value">{{ startAfterCreate ? 'Yes' : 'No' }}</span>
              </div>
            </div>

            <div class="review-group">
              <h5 class="review-group-title">Hardware</h5>
              <div class="review-row">
                <span class="review-label">CPU Cores</span>
                <span class="review-value">{{ cores }}</span>
              </div>
              <div class="review-row">
                <span class="review-label">Memory</span>
                <span class="review-value">{{ memory }} MB</span>
              </div>
              <div class="review-row">
                <span class="review-label">Disk</span>
                <span class="review-value">{{ diskSize }} GB on {{ diskStorage }}</span>
              </div>
              <div class="review-row">
                <span class="review-label">SCSI Controller</span>
                <span class="review-value">virtio-scsi-pci</span>
              </div>
            </div>

            <div class="review-group">
              <h5 class="review-group-title">ISO & Network</h5>
              <div class="review-row">
                <span class="review-label">ISO</span>
                <span class="review-value">{{ isoFile ? isoFile.split('/').pop() : 'None' }}</span>
              </div>
              <div class="review-row">
                <span class="review-label">ISO Storage</span>
                <span class="review-value">{{ isoStorage || 'N/A' }}</span>
              </div>
              <div class="review-row">
                <span class="review-label">Network Bridge</span>
                <span class="review-value">{{ bridge }}</span>
              </div>
              <div class="review-row">
                <span class="review-label">NIC Model</span>
                <span class="review-value">VirtIO</span>
              </div>
            </div>
          </div>

          <div v-if="createError" class="alert alert-danger">
            {{ createError }}
          </div>
        </div>

        <div class="step-actions">
          <button class="btn btn-outline" @click="currentStep = 2" :disabled="creating">Back</button>
          <button class="btn btn-primary" @click="submitCreate" :disabled="creating">
            <span v-if="creating">
              <span class="spinner-inline"></span> Creating VM...
            </span>
            <span v-else>Create VM</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/services/api'

const OS_TYPE_LABELS = {
  l26: 'Linux (6.x - 2.6 Kernel)',
  l24: 'Linux (2.4 Kernel)',
  win11: 'Windows 11/2022',
  win10: 'Windows 10/2019/2016',
  win8: 'Windows 8/2012',
  win7: 'Windows 7/2008',
  wxp: 'Windows XP/2003',
  other: 'Other',
}

export default {
  name: 'CreatePVEVM',

  data() {
    return {
      currentStep: 1,

      // Step 1
      hosts: [],
      selectedHostId: '',
      nodes: [],
      selectedNode: '',
      vmid: null,
      vmName: '',
      osType: 'l26',
      startAfterCreate: false,

      // Loading flags
      loadingNodes: false,
      loadingNextId: false,
      loadingStorage: false,
      loadingNetwork: false,
      loadingIsos: false,

      // Step 2
      cores: 2,
      memory: 2048,
      diskSize: 32,
      allStorages: [],
      diskStorage: '',
      isoStorage: '',
      isoFile: '',
      isos: [],
      allNetworks: [],
      bridge: '',

      // Step 3
      creating: false,
      createError: '',
    }
  },

  computed: {
    hostName() {
      const h = this.hosts.find(x => x.id === this.selectedHostId)
      return h ? h.name : ''
    },
    osTypeLabel() {
      return OS_TYPE_LABELS[this.osType] || this.osType
    },
    diskStorages() {
      return this.allStorages.filter(s => s.content && s.content.includes('images'))
    },
    isoStorages() {
      return this.allStorages.filter(s => s.content && s.content.includes('iso'))
    },
    bridges() {
      return this.allNetworks.filter(n => n.type === 'bridge')
    },
    canGoStep2() {
      return this.selectedHostId && this.selectedNode && this.vmid && this.vmName.trim()
    },
    canGoStep3() {
      return this.cores > 0 && this.memory >= 256 && this.diskSize > 0 && this.diskStorage && this.bridge
    },
  },

  methods: {
    async loadHosts() {
      try {
        const res = await api.proxmox.listHosts()
        this.hosts = (res.data || []).filter(h => h.is_active)
      } catch (e) {
        console.error('Failed to load hosts:', e)
      }
    },

    async onHostChange() {
      this.selectedNode = ''
      this.nodes = []
      this.vmid = null
      this.allStorages = []
      this.allNetworks = []
      this.diskStorage = ''
      this.isoStorage = ''
      this.isoFile = ''
      this.isos = []
      this.bridge = ''

      if (!this.selectedHostId) return

      this.loadingNodes = true
      try {
        const res = await api.proxmox.listNodes(this.selectedHostId)
        this.nodes = res.data || []
      } catch (e) {
        console.error('Failed to load nodes:', e)
      } finally {
        this.loadingNodes = false
      }
    },

    async onNodeChange() {
      this.vmid = null
      this.allStorages = []
      this.allNetworks = []
      this.diskStorage = ''
      this.isoStorage = ''
      this.isoFile = ''
      this.isos = []
      this.bridge = ''

      if (!this.selectedNode) return

      await Promise.all([this.loadNextId(), this.loadStorage(), this.loadNetwork()])
    },

    async loadNextId() {
      this.loadingNextId = true
      try {
        const res = await api.pveNode.nextId(this.selectedHostId)
        this.vmid = res.data?.nextid ?? res.data
      } catch (e) {
        console.error('Failed to fetch next VM ID:', e)
      } finally {
        this.loadingNextId = false
      }
    },

    async loadStorage() {
      this.loadingStorage = true
      try {
        const res = await api.pveNode.listStorage(this.selectedHostId, this.selectedNode)
        const storages = res.data?.data ?? res.data ?? []
        this.allStorages = storages

        // Auto-select first disk-capable storage
        const diskStore = storages.find(s => s.content && s.content.includes('images') && s.active !== false)
        if (diskStore) this.diskStorage = diskStore.storage

        // Auto-select first iso-capable storage
        const isoStore = storages.find(s => s.content && s.content.includes('iso') && s.active !== false)
        if (isoStore) this.isoStorage = isoStore.storage
      } catch (e) {
        console.error('Failed to load storage:', e)
      } finally {
        this.loadingStorage = false
      }
    },

    async loadNetwork() {
      this.loadingNetwork = true
      try {
        const res = await api.pveNode.listNetwork(this.selectedHostId, this.selectedNode)
        const networks = res.data?.data ?? res.data ?? []
        this.allNetworks = networks

        // Auto-select first bridge
        const firstBridge = networks.find(n => n.type === 'bridge')
        if (firstBridge) this.bridge = firstBridge.iface
      } catch (e) {
        console.error('Failed to load network:', e)
      } finally {
        this.loadingNetwork = false
      }
    },

    async onIsoStorageChange() {
      this.isoFile = ''
      this.isos = []
      if (!this.isoStorage) return

      this.loadingIsos = true
      try {
        const res = await api.pveNode.browseStorage(
          this.selectedHostId,
          this.selectedNode,
          this.isoStorage,
          { content: 'iso' }
        )
        const items = res.data?.data ?? res.data ?? []
        this.isos = items
      } catch (e) {
        console.error('Failed to load ISOs:', e)
      } finally {
        this.loadingIsos = false
      }
    },

    goStep2() {
      if (!this.canGoStep2) return
      this.currentStep = 2
    },

    goStep3() {
      if (!this.canGoStep3) return
      this.currentStep = 3
    },

    buildPayload() {
      const payload = {
        vmid: this.vmid,
        name: this.vmName.trim(),
        memory: this.memory,
        cores: this.cores,
        scsihw: 'virtio-scsi-pci',
        scsi0: `${this.diskStorage}:${this.diskSize}`,
        net0: `virtio,bridge=${this.bridge}`,
        ostype: this.osType,
        boot: 'order=scsi0;ide2',
        agent: 1,
        start: this.startAfterCreate ? 1 : 0,
      }

      if (this.isoStorage && this.isoFile) {
        // isoFile is already a full volid like "local:iso/debian.iso"
        // Proxmox expects ide2 as: <storage>:iso/<filename>,media=cdrom
        // But the volid from browseStorage is already the full reference
        payload.ide2 = `${this.isoFile},media=cdrom`
      } else {
        payload.ide2 = 'none,media=cdrom'
      }

      return payload
    },

    async submitCreate() {
      this.creating = true
      this.createError = ''
      try {
        const payload = this.buildPayload()
        await api.pveNode.createVm(this.selectedHostId, this.selectedNode, payload)
        this.$router.push(`/proxmox/${this.selectedHostId}/nodes/${this.selectedNode}/vms/${this.vmid}`)
      } catch (e) {
        console.error('Failed to create VM:', e)
        const detail = e.response?.data?.detail
        this.createError = typeof detail === 'string'
          ? detail
          : 'Failed to create VM. Check the console for details.'
      } finally {
        this.creating = false
      }
    },
  },

  mounted() {
    this.loadHosts()
  },
}
</script>

<style scoped>
.create-pve-vm-page {
  max-width: 900px;
  margin: 0 auto;
}

.card-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.card-header h3 {
  margin: 0 0 0.25rem 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.subtitle {
  margin: 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

/* Step indicator */
.step-indicator {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  background: var(--background-secondary, #1a2332);
}

.step {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 1rem 1.5rem;
  cursor: default;
  color: var(--text-secondary);
  font-size: 0.875rem;
  border-bottom: 3px solid transparent;
  transition: all 0.2s;
}

.step.done {
  cursor: pointer;
  color: #10b981;
  border-bottom-color: #10b981;
}

.step.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
  font-weight: 600;
}

.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  font-size: 0.8rem;
  font-weight: 700;
  background: rgba(255,255,255,0.08);
  flex-shrink: 0;
}

.step.active .step-num {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

.step.done .step-num {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

/* Body */
.step-body {
  padding: 1.5rem;
}

.form-section {
  margin-bottom: 2rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid var(--border-color);
}

.form-section:last-of-type {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 1rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 0.4rem;
}

.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background: var(--background);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
}

/* Loading states */
.loading-inline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
  padding: 0.5rem 0;
}

.loading-spinner-sm {
  width: 1rem;
  height: 1rem;
  border: 2px solid var(--border-color);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

.spinner-inline {
  display: inline-block;
  width: 0.875rem;
  height: 0.875rem;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 0.25rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Review */
.review-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.review-group {
  background: var(--background-secondary, rgba(255,255,255,0.03));
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
}

.review-group-title {
  font-size: 0.875rem;
  font-weight: 700;
  color: #3b82f6;
  margin: 0 0 0.75rem 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.review-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.875rem;
}

.review-row:last-child {
  border-bottom: none;
}

.review-label {
  color: var(--text-secondary);
  flex-shrink: 0;
  margin-right: 1rem;
}

.review-value {
  color: var(--text-primary);
  font-weight: 500;
  text-align: right;
  word-break: break-all;
}

/* Alert */
.alert-danger {
  margin-top: 1rem;
  padding: 0.875rem 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.4);
  border-radius: 0.375rem;
  color: #fca5a5;
  font-size: 0.875rem;
}

/* Actions */
.step-actions {
  display: flex;
  gap: 1rem;
  padding-top: 1.5rem;
  justify-content: flex-end;
}

/* Grid helpers */
.grid { display: grid; }
.grid-cols-2 { grid-template-columns: 1fr 1fr; }
.gap-2 { gap: 1rem; }

@media (max-width: 640px) {
  .grid-cols-2 {
    grid-template-columns: 1fr;
  }

  .step-label {
    display: none;
  }

  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>
