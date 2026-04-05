<template>
  <div class="vmdetails-page">
    <!-- Loading -->
    <div v-if="loading" class="loading-spinner"></div>

    <!-- Error -->
    <div v-else-if="error" class="text-center text-muted mt-4">
      <p class="text-danger">{{ error }}</p>
      <button @click="fetchVM" class="btn btn-outline mt-2">Retry</button>
    </div>

    <template v-else-if="vm">
      <!-- Page Header -->
      <div class="page-header mb-2">
        <div class="header-left">
          <router-link to="/vms" class="back-link">← Back to Virtual Machines</router-link>
          <h2 class="vm-title">
            {{ vm.name || `VM ${vm.vmid}` }}
            <span class="badge badge-info ml-1">VMID {{ vm.vmid }}</span>
            <span :class="statusBadgeClass">{{ vm.status }}</span>
            <span v-if="vm.node" class="badge badge-info ml-1">{{ vm.node }}</span>
          </h2>
        </div>
        <div class="header-actions flex gap-1 flex-wrap">
          <button
            @click="doStart"
            class="btn btn-success btn-sm"
            :disabled="actioning || vm.status === 'running'"
          >
            {{ actioning && pendingAction === 'start' ? 'Starting...' : 'Start' }}
          </button>
          <button
            @click="doStop"
            class="btn btn-warning btn-sm"
            :disabled="actioning || vm.status !== 'running'"
          >
            {{ actioning && pendingAction === 'stop' ? 'Stopping...' : 'Stop' }}
          </button>
          <button
            @click="doRestart"
            class="btn btn-info btn-sm"
            :disabled="actioning || vm.status !== 'running'"
          >
            {{ actioning && pendingAction === 'restart' ? 'Restarting...' : 'Restart' }}
          </button>
          <button
            @click="doPowerOff"
            class="btn btn-danger btn-sm"
            :disabled="actioning || vm.status === 'stopped'"
          >
            {{ actioning && pendingAction === 'poweroff' ? 'Powering off...' : 'Power Off' }}
          </button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs mb-2">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="['tab-btn', activeTab === tab.id ? 'tab-btn--active' : '']"
          @click="activeTab = tab.id"
        >{{ tab.label }}</button>
      </div>

      <!-- Overview Tab -->
      <div v-if="activeTab === 'overview'">
        <!-- Quick stat cards -->
        <div class="stats-row mb-2">
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">CPU Cores</div>
            <div class="stat-card-sm__value">{{ vm.cpus || vm.cores || '—' }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Memory</div>
            <div class="stat-card-sm__value">{{ formatBytes(vm.maxmem || vm.memory_mb ? (vm.memory_mb * 1024 * 1024) : null) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Disk</div>
            <div class="stat-card-sm__value">{{ formatBytes(vm.maxdisk || vm.disk_gb ? (vm.disk_gb * 1024 * 1024 * 1024) : null) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Status</div>
            <div class="stat-card-sm__value">
              <span :class="statusBadgeClass">{{ vm.status }}</span>
            </div>
          </div>
        </div>

        <!-- Full detail grid -->
        <div class="card">
          <div class="card-header">
            <h3>VM Information</h3>
          </div>
          <div class="card-body">
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">Name</span>
                <span class="detail-value">{{ vm.name || '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">VMID</span>
                <span class="detail-value"><code>{{ vm.vmid || '—' }}</code></span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Node</span>
                <span class="detail-value">
                  <span v-if="vm.node" class="badge badge-info">{{ vm.node }}</span>
                  <span v-else>—</span>
                </span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Status</span>
                <span class="detail-value">
                  <span :class="statusBadgeClass">{{ vm.status }}</span>
                </span>
              </div>
              <div class="detail-item">
                <span class="detail-label">CPU Cores</span>
                <span class="detail-value">{{ vm.cpus || vm.cores || '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Memory</span>
                <span class="detail-value">{{ formatBytes(vm.maxmem) || (vm.memory_mb ? vm.memory_mb + ' MB' : '—') }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Disk Size</span>
                <span class="detail-value">{{ formatBytes(vm.maxdisk) || (vm.disk_gb ? vm.disk_gb + ' GB' : '—') }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">OS Type</span>
                <span class="detail-value">{{ vm.ostype || vm.os_type || '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">OS</span>
                <span class="detail-value">{{ vm.os || '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">IP Address</span>
                <span class="detail-value">{{ vm.ip_address || vm.ip || '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Template</span>
                <span class="detail-value">{{ vm.template || vm.template_name || '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Cloud Init</span>
                <span class="detail-value">
                  <span v-if="vm.cloud_init" class="badge badge-success">Yes</span>
                  <span v-else class="badge badge-secondary">No</span>
                </span>
              </div>
              <div class="detail-item">
                <span class="detail-label">SSH Username</span>
                <span class="detail-value">{{ vm.username || vm.ssh_user || '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Tags</span>
                <span class="detail-value">{{ vm.tags || '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Description</span>
                <span class="detail-value">{{ vm.description || '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Created</span>
                <span class="detail-value">{{ formatDate(vm.created_at || vm.created) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Updated</span>
                <span class="detail-value">{{ formatDate(vm.updated_at || vm.updated) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Depl0y ID</span>
                <span class="detail-value"><code>{{ vm.id || $route.params.id }}</code></span>
              </div>
              <div class="detail-item" v-if="vm.host_id">
                <span class="detail-label">Host ID</span>
                <span class="detail-value"><code>{{ vm.host_id }}</code></span>
              </div>
              <div v-for="(value, key) in extraFields" :key="key" class="detail-item">
                <span class="detail-label">{{ formatKey(key) }}</span>
                <span class="detail-value">{{ value }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Console Tab -->
      <div v-if="activeTab === 'console'">
        <div class="card">
          <div class="card-header">
            <h3>Console Access</h3>
          </div>
          <div class="card-body text-center">
            <div v-if="canOpenConsole">
              <p class="text-muted mb-2">Open a noVNC console session for this VM in a new browser tab.</p>
              <a
                :href="consoleRoute"
                target="_blank"
                class="btn btn-primary"
              >
                Open Console
              </a>
              <div class="text-sm text-muted mt-2">
                <p>Console URL: <code>{{ consoleRoute }}</code></p>
              </div>
            </div>
            <div v-else>
              <p class="text-muted mb-2">Console is not available for this VM.</p>
              <p class="text-sm text-muted">
                A Proxmox host ID, node name, and VMID are required to open a console session.
                This VM may be missing one or more of these values.
              </p>
              <div class="text-sm text-muted mt-2">
                <p>Host ID: <code>{{ vm.host_id || '—' }}</code></p>
                <p>Node: <code>{{ vm.node || '—' }}</code></p>
                <p>VMID: <code>{{ vm.vmid || '—' }}</code></p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const KNOWN_FIELDS = new Set([
  'id', 'name', 'vmid', 'node', 'status', 'cpus', 'cores', 'maxmem', 'maxdisk',
  'ostype', 'os_type', 'os', 'ip_address', 'ip', 'template', 'template_name',
  'cloud_init', 'username', 'ssh_user', 'tags', 'description',
  'created_at', 'created', 'updated_at', 'updated', 'host_id',
  'memory_mb', 'disk_gb',
])

export default {
  name: 'VMDetails',

  data() {
    return {
      vm: null,
      loading: false,
      error: null,
      actioning: false,
      pendingAction: null,
      activeTab: 'overview',
      tabs: [
        { id: 'overview', label: 'Overview' },
        { id: 'console', label: 'Console' },
      ],
    }
  },

  computed: {
    statusBadgeClass() {
      const s = (this.vm?.status || '').toLowerCase()
      if (s === 'running') return 'badge badge-success ml-1'
      if (s === 'stopped') return 'badge badge-danger ml-1'
      if (s === 'paused' || s === 'suspended') return 'badge badge-warning ml-1'
      return 'badge badge-info ml-1'
    },

    canOpenConsole() {
      return !!(this.vm?.host_id && this.vm?.node && this.vm?.vmid)
    },

    consoleRoute() {
      if (!this.canOpenConsole) return null
      return `/proxmox/${this.vm.host_id}/nodes/${this.vm.node}/console/${this.vm.vmid}`
    },

    extraFields() {
      if (!this.vm) return {}
      const result = {}
      for (const [key, value] of Object.entries(this.vm)) {
        if (!KNOWN_FIELDS.has(key) && value !== null && value !== undefined && value !== '') {
          result[key] = typeof value === 'object' ? JSON.stringify(value) : value
        }
      }
      return result
    },
  },

  methods: {
    async fetchVM() {
      this.loading = true
      this.error = null
      try {
        const id = this.$route.params.id
        const response = await api.vms.get(id)
        this.vm = response.data
      } catch (err) {
        console.error('Failed to fetch VM:', err)
        this.error = err.response?.data?.detail || 'Failed to load VM details.'
      } finally {
        this.loading = false
      }
    },

    async doStart() {
      if (this.actioning) return
      this.actioning = true
      this.pendingAction = 'start'
      try {
        await api.vms.startByVmid(this.vm.vmid, this.vm.node)
        useToast().success(`VM ${this.vm.vmid} started`)
        setTimeout(this.fetchVM, 1500)
      } catch (err) {
        console.error('Start failed:', err)
      } finally {
        this.actioning = false
        this.pendingAction = null
      }
    },

    async doStop() {
      if (this.actioning) return
      this.actioning = true
      this.pendingAction = 'stop'
      try {
        await api.vms.stopByVmid(this.vm.vmid, this.vm.node)
        useToast().success(`VM ${this.vm.vmid} stopped`)
        setTimeout(this.fetchVM, 1500)
      } catch (err) {
        console.error('Stop failed:', err)
      } finally {
        this.actioning = false
        this.pendingAction = null
      }
    },

    async doRestart() {
      if (this.actioning) return
      this.actioning = true
      this.pendingAction = 'restart'
      try {
        await api.vms.restartByVmid(this.vm.vmid, this.vm.node)
        useToast().success(`VM ${this.vm.vmid} restarting...`)
        setTimeout(this.fetchVM, 2000)
      } catch (err) {
        console.error('Restart failed:', err)
      } finally {
        this.actioning = false
        this.pendingAction = null
      }
    },

    async doPowerOff() {
      if (this.actioning) return
      if (!confirm(`Power off VM ${this.vm.vmid}? This is equivalent to pulling the power plug.`)) return
      this.actioning = true
      this.pendingAction = 'poweroff'
      try {
        await api.vms.powerOffByVmid(this.vm.vmid, this.vm.node)
        useToast().success(`VM ${this.vm.vmid} powered off`)
        setTimeout(this.fetchVM, 1500)
      } catch (err) {
        console.error('Power off failed:', err)
      } finally {
        this.actioning = false
        this.pendingAction = null
      }
    },

    formatBytes(bytes) {
      if (!bytes || bytes === 0) return '—'
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
    },

    formatDate(val) {
      if (!val) return '—'
      try {
        return new Date(val).toLocaleString()
      } catch {
        return val
      }
    },

    formatKey(key) {
      return key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase())
    },
  },

  mounted() {
    this.fetchVM()
  },
}
</script>

<style scoped>
.vmdetails-page {
  padding: 0;
}

/* Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.back-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
}

.back-link:hover {
  color: var(--text-primary);
}

.vm-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.header-actions {
  flex-wrap: wrap;
  align-items: flex-start;
  padding-top: 0.25rem;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1.5rem;
  overflow-x: auto;
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.6rem 1.25rem;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.9rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn--active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

/* Stat cards */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card-sm {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  box-shadow: var(--shadow);
}

.stat-card-sm__label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.stat-card-sm__value {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Detail grid */
.card-body {
  padding: 1.5rem;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0;
}

.detail-item {
  display: flex;
  flex-direction: column;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border-color);
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.2rem;
}

.detail-value {
  font-size: 0.9rem;
  color: var(--text-primary);
  font-weight: 500;
  word-break: break-word;
}

/* Console tab */
.text-center {
  text-align: center;
}

/* Buttons */
.btn-sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.875rem;
}

.btn-success {
  background-color: var(--secondary-color, #10b981);
  color: white;
}

.btn-success:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-warning {
  background-color: #d97706;
  color: white;
}

.btn-warning:hover:not(:disabled) {
  background-color: #b45309;
}

.btn-info {
  background-color: #0284c7;
  color: white;
}

.btn-info:hover:not(:disabled) {
  background-color: #0369a1;
}

.btn-secondary {
  background-color: var(--border-color);
  color: var(--text-primary);
}

/* Utilities */
.ml-1 { margin-left: 0.25rem; }
.mb-2 { margin-bottom: 1rem; }
.mt-2 { margin-top: 1rem; }
.mt-4 { margin-top: 2rem; }
.flex { display: flex; }
.flex-wrap { flex-wrap: wrap; }
.gap-1 { gap: 0.5rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-danger { color: var(--danger-color, #ef4444); }

@media (max-width: 700px) {
  .page-header {
    flex-direction: column;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }

  .stats-row {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
