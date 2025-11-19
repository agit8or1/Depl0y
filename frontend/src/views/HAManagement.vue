<template>
  <div class="ha-management">
    <div class="page-header">
      <div>
        <h1>High Availability Management</h1>
        <p class="subtitle">Manage Proxmox HA groups and resources</p>
      </div>
      <button @click="showWizard = true" class="btn btn-primary btn-wizard">
        <span class="icon">✨</span> Setup Wizard
      </button>
    </div>

    <div class="ha-content">
      <!-- HA Groups Section -->
      <div class="card">
        <div class="card-header">
          <h2>HA Groups</h2>
          <button @click="loadHAGroups" class="btn btn-secondary">
            <span class="icon">🔄</span> Refresh
          </button>
        </div>

        <div v-if="loading" class="loading">Loading HA groups...</div>

        <div v-else-if="error" class="error-message">
          {{ error }}
        </div>

        <div v-else-if="haGroups.length === 0" class="empty-state">
          <p>No HA groups configured</p>
          <p class="help-text">HA groups define which nodes VMs can fail over to</p>
        </div>

        <div v-else class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Group ID</th>
                <th>Nodes</th>
                <th>Restricted</th>
                <th>No Failback</th>
                <th>Comment</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="group in haGroups" :key="group.group">
                <td><strong>{{ group.group }}</strong></td>
                <td>{{ group.nodes }}</td>
                <td>{{ group.restricted ? 'Yes' : 'No' }}</td>
                <td>{{ group.nofailback ? 'Yes' : 'No' }}</td>
                <td>{{ group.comment || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- HA Resources Section -->
      <div class="card">
        <div class="card-header">
          <h2>HA Resources</h2>
          <button @click="loadHAResources" class="btn btn-secondary">
            <span class="icon">🔄</span> Refresh
          </button>
        </div>

        <div v-if="loadingResources" class="loading">Loading HA resources...</div>

        <div v-else-if="resourceError" class="error-message">
          {{ resourceError }}
        </div>

        <div v-else-if="haResources.length === 0" class="empty-state">
          <p>No HA resources configured</p>
          <p class="help-text">Add VMs to HA protection to enable automatic failover</p>
        </div>

        <div v-else class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Resource ID</th>
                <th>Type</th>
                <th>Group</th>
                <th>State</th>
                <th>Max Restart</th>
                <th>Max Relocate</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="resource in haResources" :key="resource.sid">
                <td><strong>{{ resource.sid }}</strong></td>
                <td>{{ resource.type || 'VM' }}</td>
                <td>{{ resource.group || '-' }}</td>
                <td>
                  <span :class="['badge', getStatusClass(resource.state)]">
                    {{ resource.state }}
                  </span>
                </td>
                <td>{{ resource.max_restart }}</td>
                <td>{{ resource.max_relocate }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- HA Status Section -->
      <div class="card">
        <div class="card-header">
          <h2>HA Status</h2>
          <button @click="loadHAStatus" class="btn btn-secondary">
            <span class="icon">🔄</span> Refresh
          </button>
        </div>

        <div v-if="loadingStatus" class="loading">Loading HA status...</div>

        <div v-else-if="statusError" class="error-message">
          {{ statusError }}
        </div>

        <div v-else class="status-grid">
          <div class="status-item">
            <div class="status-label">Manager Status</div>
            <div class="status-value">
              <span :class="['badge', haStatus.manager_status === 'active' ? 'badge-success' : 'badge-error']">
                {{ haStatus.manager_status || 'Unknown' }}
              </span>
            </div>
          </div>

          <div class="status-item">
            <div class="status-label">Quorum</div>
            <div class="status-value">
              <span :class="['badge', haStatus.quorum ? 'badge-success' : 'badge-error']">
                {{ haStatus.quorum ? 'OK' : 'Lost' }}
              </span>
            </div>
          </div>

          <div class="status-item">
            <div class="status-label">Total Resources</div>
            <div class="status-value">{{ haResources.length }}</div>
          </div>

          <div class="status-item">
            <div class="status-label">Total Groups</div>
            <div class="status-value">{{ haGroups.length }}</div>
          </div>
        </div>
      </div>

      <!-- Help Section -->
      <div class="card help-card">
        <h3>About High Availability</h3>
        <p>
          Proxmox HA allows automatic failover of VMs between cluster nodes. When a node fails,
          VMs are automatically restarted on other available nodes in the HA group.
        </p>
        <ul>
          <li><strong>HA Groups:</strong> Define which nodes VMs can run on</li>
          <li><strong>HA Resources:</strong> VMs that are protected by HA</li>
          <li><strong>Manager Status:</strong> Shows if the HA manager service is running</li>
        </ul>
        <p class="help-text">
          Configure HA groups and resources using the Proxmox web interface or command line.
          This page provides read-only monitoring of your HA configuration.
        </p>
      </div>
    </div>

    <!-- HA Setup Wizard -->
    <HAWizard
      :isOpen="showWizard"
      @close="showWizard = false"
      @complete="onWizardComplete"
    />
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import HAWizard from '@/components/HAWizard.vue'

export default {
  name: 'HAManagement',
  components: {
    HAWizard
  },
  setup() {
    const haGroups = ref([])
    const haResources = ref([])
    const haStatus = ref({})
    const loading = ref(false)
    const loadingResources = ref(false)
    const loadingStatus = ref(false)
    const error = ref(null)
    const resourceError = ref(null)
    const statusError = ref(null)
    const showWizard = ref(false)

    const loadHAGroups = async () => {
      loading.value = true
      error.value = null
      try {
        const response = await api.ha.listGroups()
        haGroups.value = response.data.groups || []
      } catch (err) {
        error.value = err.response?.data?.detail || 'Failed to load HA groups'
        console.error('Error loading HA groups:', err)
      } finally {
        loading.value = false
      }
    }

    const loadHAResources = async () => {
      loadingResources.value = true
      resourceError.value = null
      try {
        const response = await api.ha.listResources()
        haResources.value = response.data.resources || []
      } catch (err) {
        resourceError.value = err.response?.data?.detail || 'Failed to load HA resources'
        console.error('Error loading HA resources:', err)
      } finally {
        loadingResources.value = false
      }
    }

    const loadHAStatus = async () => {
      loadingStatus.value = true
      statusError.value = null
      try {
        const response = await api.ha.checkStatus()
        haStatus.value = response.data || {}
      } catch (err) {
        statusError.value = err.response?.data?.detail || 'Failed to load HA status'
        console.error('Error loading HA status:', err)
      } finally {
        loadingStatus.value = false
      }
    }

    const getStatusClass = (state) => {
      const statusMap = {
        'started': 'badge-success',
        'stopped': 'badge-error',
        'enabled': 'badge-success',
        'disabled': 'badge-warning'
      }
      return statusMap[state] || 'badge-secondary'
    }

    const onWizardComplete = () => {
      // Reload data after wizard completes
      loadHAGroups()
      loadHAResources()
      loadHAStatus()
    }

    onMounted(() => {
      loadHAGroups()
      loadHAResources()
      loadHAStatus()
    })

    return {
      haGroups,
      haResources,
      haStatus,
      loading,
      loadingResources,
      loadingStatus,
      error,
      resourceError,
      statusError,
      showWizard,
      loadHAGroups,
      loadHAResources,
      loadHAStatus,
      getStatusClass,
      onWizardComplete
    }
  }
}
</script>

<style scoped>
.ha-management {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: #6b7280;
  margin: 0;
}

.btn-wizard {
  white-space: nowrap;
  font-size: 1rem;
  padding: 0.75rem 1.5rem;
}

.btn-primary {
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-primary:hover {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.ha-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.card {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.card-header h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #6b7280;
}

.error-message {
  padding: 1rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #dc2626;
}

.empty-state {
  text-align: center;
  padding: 3rem 2rem;
  color: #6b7280;
}

.empty-state p {
  margin: 0.5rem 0;
}

.help-text {
  font-size: 0.875rem;
  color: #9ca3af;
}

.table-responsive {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table thead {
  background: #f9fafb;
}

.data-table th,
.data-table td {
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
}

.data-table th {
  font-weight: 600;
  font-size: 0.875rem;
  color: #6b7280;
  text-transform: uppercase;
}

.data-table tbody tr:hover {
  background: #f9fafb;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.badge-success {
  background: #d1fae5;
  color: #065f46;
}

.badge-error {
  background: #fee2e2;
  color: #991b1b;
}

.badge-warning {
  background: #fef3c7;
  color: #92400e;
}

.badge-secondary {
  background: #e5e7eb;
  color: #4b5563;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
}

.status-item {
  text-align: center;
}

.status-label {
  font-size: 0.875rem;
  color: #6b7280;
  margin-bottom: 0.5rem;
}

.status-value {
  font-size: 1.5rem;
  font-weight: 600;
}

.help-card {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
}

.help-card h3 {
  margin-top: 0;
  color: #075985;
}

.help-card ul {
  margin: 1rem 0;
  padding-left: 1.5rem;
}

.help-card li {
  margin: 0.5rem 0;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: none;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s;
}

.btn-secondary {
  background: #f3f4f6;
  color: #374151;
}

.btn-secondary:hover {
  background: #e5e7eb;
}

.icon {
  font-size: 1rem;
}
</style>
