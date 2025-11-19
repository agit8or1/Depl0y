<template>
  <div class="proxmox-hosts-page">
    <!-- Page Header -->
    <div class="page-header mb-2">
      <h2>Proxmox Datacenters and Hosts</h2>
      <p class="text-muted">Manage your Proxmox clusters and hypervisor nodes</p>
    </div>

    <!-- Datacenters Section -->
    <div class="card mb-2">
      <div class="card-header">
        <h3>Datacenters</h3>
        <button @click="showAddModal = true" class="btn btn-primary">+ Add Datacenter</button>
      </div>

      <div v-if="loading" class="loading-spinner"></div>

      <div v-else-if="hosts.length === 0" class="text-center text-muted">
        <p>No Proxmox datacenters configured yet.</p>
        <p class="text-sm">Add a datacenter to start deploying VMs.</p>
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Datacenter Name</th>
              <th>Hostname</th>
              <th>Username</th>
              <th>Status</th>
              <th>Last Poll</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="host in hosts" :key="host.id">
              <td>{{ host.name }}</td>
              <td>{{ host.hostname }}:{{ host.port }}</td>
              <td>{{ host.username }}</td>
              <td>
                <span :class="['badge', host.is_active ? 'badge-success' : 'badge-danger']">
                  {{ host.is_active ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td>
                <span v-if="host.last_poll" class="text-sm">{{ formatDate(host.last_poll) }}</span>
                <span v-else class="text-muted text-sm">Never</span>
              </td>
              <td>
                <div class="flex gap-1">
                  <button @click="testConnection(host.id)" class="btn btn-outline btn-sm">Test</button>
                  <button @click="pollHost(host.id)" class="btn btn-outline btn-sm">Poll</button>
                  <button @click="deleteHost(host.id)" class="btn btn-danger btn-sm">Delete</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Cluster Nodes Section -->
    <div class="card">
      <div class="card-header">
        <h3>Cluster Nodes</h3>
        <button @click="refreshAllNodes" class="btn btn-outline">
          <span v-if="!loadingNodes">🔄 Refresh All</span>
          <span v-else>Loading...</span>
        </button>
      </div>

      <div v-if="loadingNodes" class="loading-spinner"></div>

      <div v-else-if="allNodes.length === 0" class="text-center text-muted">
        <p>No cluster nodes found.</p>
        <p class="text-sm">Poll your datacenters to discover nodes.</p>
      </div>

      <div v-else class="nodes-section">
        <div v-for="datacenter in datacentersWithNodes" :key="datacenter.id" class="datacenter-section">
          <h4 class="datacenter-title">{{ datacenter.name }}</h4>

          <div v-if="datacenter.nodes.length === 0" class="text-muted text-sm">
            No nodes discovered yet. Click "Poll" to discover nodes.
          </div>

          <div v-else class="nodes-grid">
            <div v-for="node in datacenter.nodes" :key="node.id" class="node-card">
              <div class="node-header">
                <h5>{{ node.node_name }}</h5>
                <span :class="['badge', node.status === 'online' ? 'badge-success' : 'badge-danger']">
                  {{ node.status || 'unknown' }}
                </span>
              </div>
              <div class="node-stats">
                <div class="stat">
                  <span class="stat-label">CPU:</span>
                  <span class="stat-value">{{ node.cpu_cores }} cores ({{ node.cpu_usage }}%)</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Memory:</span>
                  <span class="stat-value">{{ formatBytes(node.memory_used) }} / {{ formatBytes(node.memory_total) }}</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Disk:</span>
                  <span class="stat-value">{{ formatBytes(node.disk_used) }} / {{ formatBytes(node.disk_total) }}</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Uptime:</span>
                  <span class="stat-value">{{ formatUptime(node.uptime) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Datacenter Modal -->
    <div v-if="showAddModal" class="modal" @click="showAddModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Proxmox Datacenter</h3>
          <button @click="showAddModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="addHost" class="modal-body">
          <div class="form-group">
            <label class="form-label">Name</label>
            <input v-model="newHost.name" class="form-control" required />
          </div>

          <div class="form-group">
            <label class="form-label">Hostname/IP</label>
            <input v-model="newHost.hostname" class="form-control" required />
          </div>

          <div class="form-group">
            <label class="form-label">Port</label>
            <input v-model="newHost.port" type="number" class="form-control" />
          </div>

          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="newHost.username" class="form-control" required />
          </div>

          <div class="auth-section">
            <h5 class="section-subtitle">Authentication Method</h5>
            <p class="text-sm text-muted">Choose one authentication method below:</p>

            <div class="form-group">
              <label class="form-label">
                <input v-model="useApiToken" type="checkbox" />
                Use API Token (recommended for 2FA-enabled Proxmox)
              </label>
            </div>

            <div v-if="useApiToken" class="warning-box">
              <strong>⚠️ IMPORTANT: Privilege Separation</strong>
              <p>When creating your API token in Proxmox, you MUST <strong>UNCHECK</strong> the "Privilege Separation" option.</p>
              <p class="text-xs">Without this, the token won't have permissions to manage VMs.</p>
            </div>

            <div v-if="!useApiToken">
              <div class="form-group">
                <label class="form-label">Password</label>
                <input v-model="newHost.password" type="password" class="form-control" :required="!useApiToken" />
              </div>
            </div>

            <div v-else>
              <div class="form-group">
                <label class="form-label">API Token ID</label>
                <input v-model="newHost.api_token_id" class="form-control" placeholder="root@pam!mytoken or mytoken" :required="useApiToken" />
                <p class="text-xs text-muted mt-1">Full format: "root@pam!mytoken" or just "mytoken"</p>
              </div>

              <div class="form-group">
                <label class="form-label">API Token Secret</label>
                <input v-model="newHost.api_token_secret" type="password" class="form-control" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" :required="useApiToken" />
                <p class="text-xs text-muted mt-1">The UUID secret generated by Proxmox</p>
              </div>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              <input v-model="newHost.verify_ssl" type="checkbox" />
              Verify SSL Certificate
            </label>
          </div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? 'Adding...' : 'Add Host' }}
            </button>
            <button type="button" @click="showAddModal = false" class="btn btn-outline">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'ProxmoxHosts',
  setup() {
    const toast = useToast()
    const hosts = ref([])
    const allNodes = ref([])
    const loading = ref(false)
    const loadingNodes = ref(false)
    const saving = ref(false)
    const showAddModal = ref(false)
    const useApiToken = ref(false)

    const newHost = ref({
      name: '',
      hostname: '',
      port: 8006,
      username: 'root@pam',
      password: '',
      api_token_id: '',
      api_token_secret: '',
      verify_ssl: false
    })

    const fetchHosts = async () => {
      loading.value = true
      try {
        const response = await api.proxmox.listHosts()
        hosts.value = response.data
      } catch (error) {
        console.error('Failed to fetch hosts:', error)
      } finally {
        loading.value = false
      }
    }

    const addHost = async () => {
      saving.value = true
      try {
        // Clear unused auth fields based on method
        const hostData = { ...newHost.value }
        if (useApiToken.value) {
          delete hostData.password
        } else {
          delete hostData.api_token_id
          delete hostData.api_token_secret
        }

        await api.proxmox.createHost(hostData)
        toast.success('Proxmox host added successfully')
        showAddModal.value = false
        useApiToken.value = false
        newHost.value = {
          name: '',
          hostname: '',
          port: 8006,
          username: 'root@pam',
          password: '',
          api_token_id: '',
          api_token_secret: '',
          verify_ssl: false
        }
        await fetchHosts()
      } catch (error) {
        console.error('Failed to add host:', error)
      } finally {
        saving.value = false
      }
    }

    const testConnection = async (hostId) => {
      try {
        const response = await api.proxmox.testConnection(hostId)
        if (response.data.status === 'success') {
          toast.success('Connection successful!')
        } else {
          toast.error('Connection failed: ' + response.data.message)
        }
      } catch (error) {
        console.error('Failed to test connection:', error)
      }
    }

    const pollHost = async (hostId) => {
      try {
        await api.proxmox.pollHost(hostId)
        toast.success('Polling started')
        setTimeout(() => {
          fetchHosts()
          refreshAllNodes()
        }, 2000)
      } catch (error) {
        console.error('Failed to poll host:', error)
      }
    }

    const refreshAllNodes = async () => {
      loadingNodes.value = true
      try {
        const nodesPromises = hosts.value.map(host =>
          api.proxmox.listNodes(host.id).catch(err => {
            console.error(`Failed to fetch nodes for ${host.name}:`, err)
            return { data: [] }
          })
        )
        const results = await Promise.all(nodesPromises)

        // Flatten all nodes and add host_id reference
        allNodes.value = results.flatMap((result, index) =>
          result.data.map(node => ({
            ...node,
            host_id: hosts.value[index].id
          }))
        )
      } catch (error) {
        console.error('Failed to refresh nodes:', error)
      } finally {
        loadingNodes.value = false
      }
    }

    const datacentersWithNodes = computed(() => {
      return hosts.value.map(host => ({
        ...host,
        nodes: allNodes.value.filter(node => node.host_id === host.id)
      }))
    })

    const formatUptime = (seconds) => {
      if (!seconds) return 'N/A'
      const days = Math.floor(seconds / 86400)
      const hours = Math.floor((seconds % 86400) / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)
      return `${days}d ${hours}h ${minutes}m`
    }

    const deleteHost = async (hostId) => {
      if (!confirm('Are you sure you want to delete this Proxmox host?')) return

      try {
        await api.proxmox.deleteHost(hostId)
        toast.success('Host deleted')
        await fetchHosts()
      } catch (error) {
        console.error('Failed to delete host:', error)
      }
    }

    const formatDate = (dateString) => {
      return new Date(dateString).toLocaleString()
    }

    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const gb = bytes / (1024 * 1024 * 1024)
      return gb.toFixed(2) + ' GB'
    }

    onMounted(() => {
      fetchHosts().then(() => {
        refreshAllNodes()
      })
    })

    return {
      hosts,
      allNodes,
      loading,
      loadingNodes,
      saving,
      showAddModal,
      useApiToken,
      newHost,
      datacentersWithNodes,
      addHost,
      testConnection,
      pollHost,
      refreshAllNodes,
      deleteHost,
      formatDate,
      formatBytes,
      formatUptime
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.page-header .text-muted {
  font-size: 0.95rem;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.nodes-section {
  padding: 0;
}

.datacenter-section {
  margin-bottom: 2rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid var(--border-color);
}

.datacenter-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.datacenter-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--primary-color);
  padding-left: 0.5rem;
  border-left: 3px solid var(--primary-color);
}

.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 0.5rem;
  max-width: 600px;
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

.modal-header h3 {
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body {
  padding: 1.5rem;
}

.auth-section {
  margin: 1rem 0;
  padding: 1rem;
  background-color: var(--background);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
}

.section-subtitle {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
}

.warning-box {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 0.375rem;
  color: #856404;
}

.warning-box strong {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
}

.warning-box p {
  margin: 0.25rem 0;
  font-size: 0.875rem;
}


.nodes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.node-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  background: var(--background);
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.node-header h5 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
}

.node-stats {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.stat {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
}

.stat-label {
  color: var(--text-secondary);
  font-weight: 500;
}

.stat-value {
  color: var(--text-primary);
  font-family: monospace;
}
</style>
