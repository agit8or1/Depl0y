<template>
  <div class="cluster-page">
    <div class="page-header mb-2">
      <h2>Cluster Overview</h2>
      <p class="text-muted">Read-only cluster status for host {{ hostId }}</p>
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <template v-else>
      <!-- Cluster Status -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Cluster Status</h3>
          <button @click="fetchAll" class="btn btn-outline">Refresh</button>
        </div>
        <div class="card-body" v-if="clusterStatus">
          <div class="status-grid">
            <div class="status-item">
              <span class="status-label">Cluster Name</span>
              <span class="status-value">{{ clusterName || '—' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">Quorum</span>
              <span :class="['badge', clusterQuorate ? 'badge-success' : 'badge-danger']">
                {{ clusterQuorate ? 'Quorate' : 'No Quorum' }}
              </span>
            </div>
            <div class="status-item">
              <span class="status-label">Nodes</span>
              <span class="status-value">{{ clusterNodes.length }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">Version</span>
              <span class="status-value">{{ clusterVersion || '—' }}</span>
            </div>
          </div>
        </div>
        <div v-else class="card-body text-muted text-center">
          <p>No cluster status available.</p>
        </div>
      </div>

      <!-- Nodes Table -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Cluster Nodes</h3>
        </div>

        <div v-if="clusterNodes.length === 0" class="text-center text-muted" style="padding: 2rem;">
          <p>No nodes found.</p>
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Online</th>
                <th>Local</th>
                <th>IP</th>
                <th>Votes</th>
                <th>Level</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="node in clusterNodes" :key="node.name || node.id">
                <td><strong>{{ node.name }}</strong></td>
                <td>
                  <span :class="['badge', node.online ? 'badge-success' : 'badge-danger']">
                    {{ node.online ? 'Online' : 'Offline' }}
                  </span>
                </td>
                <td>
                  <span v-if="node.local" class="badge badge-info">Master</span>
                  <span v-else class="text-muted text-sm">—</span>
                </td>
                <td class="text-sm">{{ node.ip || '—' }}</td>
                <td>{{ node.votes ?? '—' }}</td>
                <td>{{ node.level || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Cluster Options -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Migration Settings</h3>
        </div>
        <div class="card-body" v-if="clusterOptions">
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Migration Type</span>
              <span class="info-value">{{ clusterOptions.migration?.type || clusterOptions['migration-unsecure'] === 1 ? 'insecure' : 'secure' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Migration Network</span>
              <span class="info-value">{{ clusterOptions.migration?.network || clusterOptions.migration_network || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Console</span>
              <span class="info-value">{{ clusterOptions.console || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Email From</span>
              <span class="info-value">{{ clusterOptions.email_from || '—' }}</span>
            </div>
          </div>
        </div>
        <div v-else class="card-body text-muted text-center">
          <p>No cluster options available.</p>
        </div>
      </div>

      <!-- HA Manager Status -->
      <div class="card">
        <div class="card-header">
          <h3>HA Manager Status</h3>
        </div>
        <div class="card-body" v-if="haStatus">
          <div class="status-grid">
            <div class="status-item">
              <span class="status-label">Manager Status</span>
              <span :class="['badge', haStatus.manager_status === 'active' ? 'badge-success' : 'badge-warning']">
                {{ haStatus.manager_status || 'unknown' }}
              </span>
            </div>
            <div class="status-item">
              <span class="status-label">Quorum OK</span>
              <span :class="['badge', haStatus.quorum_ok ? 'badge-success' : 'badge-danger']">
                {{ haStatus.quorum_ok ? 'Yes' : 'No' }}
              </span>
            </div>
            <div class="status-item">
              <span class="status-label">Master Node</span>
              <span class="status-value">{{ haStatus.master_node || '—' }}</span>
            </div>
          </div>
        </div>
        <div v-else class="card-body text-muted text-center">
          <p>HA status not available or HA not configured.</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'Cluster',
  setup() {
    const route = useRoute()
    const toast = useToast()
    const hostId = ref(route.params.hostId)
    const loading = ref(false)
    const clusterStatus = ref(null)
    const clusterOptions = ref(null)
    const haStatus = ref(null)

    const clusterNodes = computed(() => {
      if (!clusterStatus.value) return []
      return (clusterStatus.value || []).filter(item => item.type === 'node')
    })

    const clusterName = computed(() => {
      if (!clusterStatus.value) return null
      const cluster = (clusterStatus.value || []).find(item => item.type === 'cluster')
      return cluster?.name
    })

    const clusterQuorate = computed(() => {
      if (!clusterStatus.value) return false
      const cluster = (clusterStatus.value || []).find(item => item.type === 'cluster')
      return cluster?.quorate === 1
    })

    const clusterVersion = computed(() => {
      if (!clusterStatus.value) return null
      const cluster = (clusterStatus.value || []).find(item => item.type === 'cluster')
      return cluster?.version
    })

    const fetchAll = async () => {
      loading.value = true
      try {
        const [statusRes, optionsRes, haRes] = await Promise.allSettled([
          api.pveNode.clusterStatus(hostId.value),
          api.pveNode.clusterOptions(hostId.value),
          api.pveNode.haStatus(hostId.value)
        ])

        if (statusRes.status === 'fulfilled') {
          clusterStatus.value = statusRes.value.data
        }
        if (optionsRes.status === 'fulfilled') {
          clusterOptions.value = optionsRes.value.data
        }
        if (haRes.status === 'fulfilled') {
          haStatus.value = haRes.value.data
        }
      } catch (error) {
        console.error('Failed to fetch cluster info:', error)
        toast.error('Failed to load cluster information')
      } finally {
        loading.value = false
      }
    }

    onMounted(() => {
      fetchAll()
    })

    return {
      hostId,
      loading,
      clusterStatus,
      clusterOptions,
      haStatus,
      clusterNodes,
      clusterName,
      clusterQuorate,
      clusterVersion,
      fetchAll
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

.mb-2 { margin-bottom: 1rem; }

.card-body {
  padding: 1.5rem;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1.5rem;
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.status-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.status-value {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
}

.info-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.info-value {
  font-size: 1rem;
  font-weight: 500;
  color: var(--text-primary);
}
</style>
