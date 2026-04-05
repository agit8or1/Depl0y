<template>
  <div class="container-detail-page">
    <!-- Header -->
    <div class="page-header mb-2">
      <div class="header-left">
        <router-link :to="`/proxmox/${hostId}/nodes/${node}`" class="back-link">← {{ node }}</router-link>
        <h2 class="ct-title">
          {{ config.hostname || `CT ${vmid}` }}
          <span class="badge badge-info ml-1">{{ vmid }}</span>
          <span :class="['badge', 'ml-1', getStatusBadge(currentStats.status || status)]">{{ currentStats.status || status }}</span>
          <span class="badge badge-info ml-1">CT/LXC</span>
        </h2>
      </div>
      <div class="header-actions flex gap-1 flex-wrap">
        <button @click="action('start')" class="btn btn-success btn-sm"
          :disabled="actioning || (currentStats.status || status) === 'running'">Start</button>
        <button @click="action('stop')" class="btn btn-outline btn-sm"
          :disabled="actioning || (currentStats.status || status) !== 'running'">Stop</button>
        <button @click="action('reboot')" class="btn btn-outline btn-sm"
          :disabled="actioning || (currentStats.status || status) !== 'running'">Reboot</button>
        <button @click="action('restart')" class="btn btn-outline btn-sm"
          :disabled="actioning || (currentStats.status || status) !== 'running'">Restart</button>
        <button @click="openTerminal" class="btn btn-outline btn-sm">Terminal</button>
        <button @click="deleteContainer" class="btn btn-danger btn-sm" :disabled="actioning">Delete</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-spinner"></div>

    <template v-else>
      <!-- Tabs -->
      <div class="tabs mb-2">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="switchTab(tab.id)"
          :class="['tab-btn', activeTab === tab.id ? 'tab-btn--active' : '']"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Overview Tab -->
      <div v-if="activeTab === 'overview'">
        <div class="stats-row mb-2">
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">CPU</div>
            <div class="stat-card-sm__value">{{ currentStats.cpu ? (currentStats.cpu * 100).toFixed(1) + '%' : '0%' }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">RAM</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.mem) }} / {{ formatBytes(currentStats.maxmem) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Uptime</div>
            <div class="stat-card-sm__value">{{ formatUptime(currentStats.uptime) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Disk Used</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.disk) }} / {{ formatBytes(currentStats.maxdisk) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Net In</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.netin) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Net Out</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.netout) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Disk Read</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.diskread) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Disk Write</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.diskwrite) }}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h3>Summary</h3></div>
          <div class="card-body">
            <div class="summary-grid">
              <div class="summary-item"><span class="summary-label">Hostname</span><span>{{ config.hostname || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">OS Type</span><span>{{ config.ostype || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Cores</span><span>{{ config.cores || config.cpus || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Memory</span><span>{{ config.memory ? config.memory + ' MB' : '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Swap</span><span>{{ config.swap !== undefined ? config.swap + ' MB' : '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Start on Boot</span><span>{{ config.onboot ? 'Yes' : 'No' }}</span></div>
              <div class="summary-item"><span class="summary-label">Root FS</span><span class="text-sm">{{ config.rootfs || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Template</span><span>{{ config.ostemplate || '—' }}</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Configuration Tab -->
      <div v-if="activeTab === 'config'">
        <div class="card">
          <div class="card-header">
            <h3>Container Configuration</h3>
            <div class="flex gap-1">
              <button v-if="!editMode" @click="enterEditMode" class="btn btn-outline btn-sm">Edit</button>
              <template v-else>
                <button @click="saveConfig" class="btn btn-primary btn-sm" :disabled="savingConfig">
                  {{ savingConfig ? 'Saving...' : 'Save' }}
                </button>
                <button @click="cancelEdit" class="btn btn-outline btn-sm">Cancel</button>
              </template>
            </div>
          </div>
          <div class="card-body">
            <div class="config-grid">
              <div class="form-group">
                <label class="form-label">Hostname</label>
                <input v-if="editMode" v-model="editConfig.hostname" class="form-control" />
                <div v-else class="config-value">{{ config.hostname || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Cores</label>
                <input v-if="editMode" v-model.number="editConfig.cores" type="number" min="1" class="form-control" />
                <div v-else class="config-value">{{ config.cores || config.cpus || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Memory (MB)</label>
                <input v-if="editMode" v-model.number="editConfig.memory" type="number" min="16" step="16" class="form-control" />
                <div v-else class="config-value">{{ config.memory ? config.memory + ' MB' : '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Swap (MB)</label>
                <input v-if="editMode" v-model.number="editConfig.swap" type="number" min="0" step="16" class="form-control" />
                <div v-else class="config-value">{{ config.swap !== undefined ? config.swap + ' MB' : '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Root Filesystem</label>
                <div class="config-value text-sm">{{ config.rootfs || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Startup</label>
                <input v-if="editMode" v-model="editConfig.startup" class="form-control" placeholder="order=1,up=10" />
                <div v-else class="config-value">{{ config.startup || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">
                  <input v-if="editMode" type="checkbox" v-model="editConfig.onboot" :true-value="1" :false-value="0" />
                  <input v-else type="checkbox" :checked="!!config.onboot" disabled />
                  Start on Boot
                </label>
              </div>
              <div class="form-group" style="grid-column: span 2;">
                <label class="form-label">Description</label>
                <textarea v-if="editMode" v-model="editConfig.description" class="form-control" rows="3"></textarea>
                <div v-else class="config-value" style="height: auto; min-height: 3rem; white-space: pre-wrap;">{{ config.description || '—' }}</div>
              </div>
            </div>

            <!-- Network Interfaces -->
            <div class="section-title mt-2 mb-1">Network Interfaces</div>
            <div v-if="parsedNets.length === 0" class="text-muted text-sm mb-2">No network interfaces configured.</div>
            <div v-else class="table-container mb-2">
              <table class="table">
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>Name</th>
                    <th>Bridge</th>
                    <th>IP</th>
                    <th>Gateway</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="net in parsedNets" :key="net.key">
                    <td><code>{{ net.key }}</code></td>
                    <td>{{ net.name || '—' }}</td>
                    <td>{{ net.bridge || '—' }}</td>
                    <td class="text-sm">{{ net.ip || '—' }}</td>
                    <td class="text-sm">{{ net.gw || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Full raw config -->
            <div class="section-title mt-2 mb-1">Full Configuration</div>
            <div class="raw-config-table">
              <div v-for="(val, key) in config" :key="key" class="raw-config-row">
                <span class="raw-config-key">{{ key }}</span>
                <span class="raw-config-val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Snapshots Tab -->
      <div v-if="activeTab === 'snapshots'">
        <div class="card">
          <div class="card-header">
            <h3>Snapshots</h3>
            <button @click="showSnapshotModal = true" class="btn btn-primary btn-sm">+ Create Snapshot</button>
          </div>

          <div v-if="loadingSnapshots" class="loading-spinner"></div>

          <div v-else-if="snapshots.length === 0" class="text-center text-muted" style="padding: 2rem;">
            <p>No snapshots found.</p>
          </div>

          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="snap in snapshots" :key="snap.name">
                  <td><strong>{{ snap.name }}</strong></td>
                  <td class="text-sm text-muted">{{ snap.description || '—' }}</td>
                  <td class="text-sm">{{ snap.snaptime ? formatDate(snap.snaptime) : '—' }}</td>
                  <td>
                    <div v-if="snap.name !== 'current'" class="flex gap-1">
                      <button @click="rollbackSnapshot(snap.name)" class="btn btn-outline btn-sm"
                        :disabled="actioning">Rollback</button>
                      <button @click="deleteSnapshot(snap.name)" class="btn btn-danger btn-sm"
                        :disabled="actioning">Delete</button>
                    </div>
                    <span v-else class="text-muted text-sm">current</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Terminal Tab -->
      <div v-if="activeTab === 'terminal'">
        <div class="card">
          <div class="card-header"><h3>Container Terminal</h3></div>
          <div class="card-body text-center" style="padding: 2rem;">
            <p class="text-muted mb-2">Open an interactive shell session for this LXC container.</p>
            <button @click="openTerminal" class="btn btn-primary">Open Terminal</button>
            <p class="text-muted text-sm mt-2">
              Navigates to the Depl0y terminal viewer
              (<code>/proxmox/{{ hostId }}/nodes/{{ node }}/terminal?lxc={{ vmid }}</code>)
            </p>
          </div>
        </div>
      </div>
    </template>

    <!-- Create Snapshot Modal -->
    <div v-if="showSnapshotModal" class="modal" @click="showSnapshotModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Snapshot</h3>
          <button @click="showSnapshotModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="createSnapshot" class="modal-body">
          <div class="form-group">
            <label class="form-label">Snapshot Name</label>
            <input v-model="newSnapshot.snapname" class="form-control" placeholder="snap1" required />
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <input v-model="newSnapshot.description" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingSnapshot">
              {{ savingSnapshot ? 'Creating...' : 'Create' }}
            </button>
            <button type="button" @click="showSnapshotModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'ContainerDetail',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const toast = useToast()
    const hostId = ref(route.params.hostId)
    const node = ref(route.params.node)
    const vmid = ref(route.params.vmid)
    const status = ref('unknown')
    const config = ref({})
    const editConfig = ref({})
    const currentStats = ref({})
    const snapshots = ref([])
    const loading = ref(true)
    const actioning = ref(false)
    const savingConfig = ref(false)
    const loadingSnapshots = ref(false)
    const showSnapshotModal = ref(false)
    const savingSnapshot = ref(false)
    const activeTab = ref('Overview')

    const newSnapshot = ref({ snapname: '', description: '' })


    const fetchAll = async () => {
      loading.value = true
      try {
        const [statusRes, configRes] = await Promise.all([
          api.pveNode.getContainerStatus(hostId.value, node.value, vmid.value),
          api.pveNode.getContainerConfig(hostId.value, node.value, vmid.value)
        ])
        currentStats.value = statusRes.data || {}
        status.value = currentStats.value.status || 'unknown'
        config.value = configRes.data || {}
        editConfig.value = {
          hostname: config.value.hostname || '',
          cores: config.value.cores || config.value.cpus || 1,
          memory: config.value.memory || 512,
          swap: config.value.swap !== undefined ? config.value.swap : 512,
          onboot: config.value.onboot || 0,
          description: config.value.description || ''
        }
      } catch (error) {
        console.error('Failed to fetch container info:', error)
        toast.error('Failed to load container information')
      } finally {
        loading.value = false
      }
    }

    const fetchSnapshots = async () => {
      loadingSnapshots.value = true
      try {
        const response = await api.pveNode.listContainerSnapshots(hostId.value, node.value, vmid.value)
        snapshots.value = (response.data || []).filter(s => s.name !== 'current').concat(
          (response.data || []).filter(s => s.name === 'current')
        )
      } catch (error) {
        console.error('Failed to fetch snapshots:', error)
      } finally {
        loadingSnapshots.value = false
      }
    }

    const action = async (act) => {
      actioning.value = true
      try {
        await api.pveNode.containerAction(hostId.value, node.value, vmid.value, `status/${act}`)
        toast.success(`Container ${act} initiated`)
        setTimeout(() => fetchAll(), 2000)
      } catch (error) {
        console.error(`Failed to ${act} container:`, error)
        toast.error(`Failed to ${act} container`)
      } finally {
        actioning.value = false
      }
    }

    const saveConfig = async () => {
      savingConfig.value = true
      try {
        const payload = { ...editConfig.value }
        await api.pveNode.updateContainerConfig(hostId.value, node.value, vmid.value, payload)
        toast.success('Configuration saved')
        await fetchAll()
      } catch (error) {
        console.error('Failed to save config:', error)
        toast.error('Failed to save configuration')
      } finally {
        savingConfig.value = false
      }
    }

    const createSnapshot = async () => {
      savingSnapshot.value = true
      try {
        await api.pveNode.createContainerSnapshot(hostId.value, node.value, vmid.value, newSnapshot.value)
        toast.success('Snapshot created')
        showSnapshotModal.value = false
        newSnapshot.value = { snapname: '', description: '' }
        await fetchSnapshots()
      } catch (error) {
        console.error('Failed to create snapshot:', error)
        toast.error('Failed to create snapshot')
      } finally {
        savingSnapshot.value = false
      }
    }

    const rollbackSnapshot = async (snapname) => {
      if (!confirm(`Roll back to snapshot "${snapname}"? Current state will be lost.`)) return
      try {
        await api.pveNode.rollbackContainerSnapshot(hostId.value, node.value, vmid.value, snapname)
        toast.success('Rollback initiated')
        await fetchAll()
      } catch (error) {
        console.error('Failed to rollback:', error)
        toast.error('Failed to rollback')
      }
    }

    const deleteSnapshot = async (snapname) => {
      if (!confirm(`Delete snapshot "${snapname}"?`)) return
      try {
        await api.pveNode.containerAction(hostId.value, node.value, vmid.value, `snapshots/${snapname}/delete`)
        toast.success('Snapshot deleted')
        await fetchSnapshots()
      } catch (error) {
        console.error('Failed to delete snapshot:', error)
        toast.error('Failed to delete snapshot')
      }
    }

    const deleteContainer = async () => {
      if (!confirm(`Permanently delete CT ${vmid.value}? This cannot be undone.`)) return
      actioning.value = true
      try {
        await api.pveNode.deleteContainer(hostId.value, node.value, vmid.value)
        toast.success('Container deleted')
        router.push('/vms')
      } catch (error) {
        console.error('Failed to delete container:', error)
        toast.error('Failed to delete container')
      } finally {
        actioning.value = false
      }
    }

    const openTerminal = () => {
      const url = `/proxmox/${hostId.value}/nodes/${node.value}/lxc/${vmid.value}/terminal`
      window.open(url, '_blank')
    }

    const getStatusBadge = (s) => {
      if (s === 'running') return 'badge-success'
      if (s === 'stopped') return 'badge-danger'
      if (s === 'suspended') return 'badge-warning'
      return 'badge-info'
    }

    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const gb = bytes / (1024 * 1024 * 1024)
      if (gb >= 1) return gb.toFixed(2) + ' GB'
      const mb = bytes / (1024 * 1024)
      return mb.toFixed(1) + ' MB'
    }

    const formatUptime = (seconds) => {
      if (!seconds) return '—'
      const days = Math.floor(seconds / 86400)
      const hours = Math.floor((seconds % 86400) / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)
      return `${days}d ${hours}h ${minutes}m`
    }

    const formatDate = (epoch) => {
      return new Date(epoch * 1000).toLocaleString()
    }

    onMounted(async () => {
      await fetchAll()
      fetchSnapshots()
    })

    return {
      hostId,
      node,
      vmid,
      status,
      config,
      editConfig,
      currentStats,
      snapshots,
      loading,
      actioning,
      savingConfig,
      loadingSnapshots,
      showSnapshotModal,
      savingSnapshot,
      activeTab,
      newSnapshot,
      action,
      saveConfig,
      createSnapshot,
      rollbackSnapshot,
      deleteSnapshot,
      deleteContainer,
      openTerminal,
      getStatusBadge,
      formatBytes,
      formatUptime,
      formatDate
    }
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-left h2 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
}

.mb-2 { margin-bottom: 1rem; }

.btn-sm {
  padding: 0.25rem 0.625rem;
  font-size: 0.875rem;
}

.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.75rem 1.5rem;
  cursor: pointer;
  font-size: 0.95rem;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}

.tab-btn:hover { color: var(--text-primary); }

.tab-active {
  color: var(--primary-color) !important;
  border-bottom-color: var(--primary-color) !important;
  font-weight: 600;
}

.tab-content {
  padding: 1.5rem;
}

.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.tab-header h3 { margin: 0; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.stat-card {
  padding: 1.25rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
}

.stat-card h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.stat-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}

.config-summary h4 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  font-weight: 600;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}

.summary-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.config-form {
  max-width: 600px;
  margin-bottom: 2rem;
}

.raw-config {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
}

.raw-config h4 {
  margin: 0 0 1rem 0;
}

.config-table {
  display: grid;
  gap: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
}

.config-row {
  display: grid;
  grid-template-columns: 200px 1fr;
  border-bottom: 1px solid var(--border-color);
}

.config-row:last-child { border-bottom: none; }

.config-key {
  padding: 0.5rem 0.75rem;
  background: var(--background);
  font-family: monospace;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-right: 1px solid var(--border-color);
}

.config-val {
  padding: 0.5rem 0.75rem;
  font-family: monospace;
  font-size: 0.875rem;
  color: var(--text-primary);
  word-break: break-all;
}

.text-muted { color: var(--text-secondary); }
.text-sm { font-size: 0.875rem; }

.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 0.5rem;
  max-width: 480px;
  width: 90%;
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
</style>
