<template>
  <div class="dashboard">
    <div class="stats-row mb-2">
      <router-link to="/vms" class="stat-card card">
        <div class="stat-icon">🖥️</div>
        <div class="stat-info">
          <p class="stat-value">{{ stats.total_vms }}</p>
          <p class="stat-label">VMs</p>
        </div>
      </router-link>

      <router-link to="/vms?status=running" class="stat-card card">
        <div class="stat-icon success">▶️</div>
        <div class="stat-info">
          <p class="stat-value">{{ stats.running_vms }}</p>
          <p class="stat-label">Running</p>
        </div>
      </router-link>

      <router-link to="/vms?status=stopped" class="stat-card card">
        <div class="stat-icon danger">⏹️</div>
        <div class="stat-info">
          <p class="stat-value">{{ stats.stopped_vms }}</p>
          <p class="stat-label">Stopped</p>
        </div>
      </router-link>

      <router-link to="/proxmox" class="stat-card card">
        <div class="stat-icon">🏢</div>
        <div class="stat-info">
          <p class="stat-value">{{ stats.datacenters }}</p>
          <p class="stat-label">Datacenters</p>
        </div>
      </router-link>

      <router-link to="/proxmox" class="stat-card card">
        <div class="stat-icon">🖧</div>
        <div class="stat-info">
          <p class="stat-value">{{ stats.total_nodes }}</p>
          <p class="stat-label">Nodes</p>
        </div>
      </router-link>
    </div>

    <div class="grid grid-cols-2 gap-2">
      <div class="card">
        <div class="card-header">
          <h3>Resource Usage</h3>
        </div>
        <div v-if="resources" class="resources">
          <div class="resource-item">
            <span class="resource-label">CPU Cores</span>
            <div class="resource-bar">
              <div class="resource-fill" :style="{ width: cpuPercentage + '%' }"></div>
            </div>
            <span class="resource-value">
              {{ resources.used_cpu_cores }} / {{ resources.total_cpu_cores }}
            </span>
          </div>

          <div class="resource-item">
            <span class="resource-label">Memory</span>
            <div class="resource-bar">
              <div class="resource-fill" :style="{ width: memoryPercentage + '%' }"></div>
            </div>
            <span class="resource-value">
              {{ resources.used_memory_gb }}GB / {{ resources.total_memory_gb }}GB
            </span>
          </div>

          <div class="resource-item">
            <span class="resource-label">Disk</span>
            <div class="resource-bar">
              <div class="resource-fill" :style="{ width: diskPercentage + '%' }"></div>
            </div>
            <span class="resource-value">
              {{ resources.used_disk_gb }}GB / {{ resources.total_disk_gb }}GB
            </span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3>Quick Actions</h3>
        </div>
        <div class="quick-actions">
          <router-link to="/vms/create" class="action-button">
            <span class="action-icon">➕</span>
            <div>
              <p class="action-title">Deploy New VM</p>
              <p class="action-desc">Create and deploy a new virtual machine</p>
            </div>
          </router-link>

          <router-link to="/proxmox" class="action-button">
            <span class="action-icon">🌐</span>
            <div>
              <p class="action-title">Manage Hosts</p>
              <p class="action-desc">Configure Proxmox hosts</p>
            </div>
          </router-link>

          <router-link to="/isos" class="action-button">
            <span class="action-icon">💿</span>
            <div>
              <p class="action-title">Upload ISO</p>
              <p class="action-desc">Add new ISO images</p>
            </div>
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'

export default {
  name: 'Dashboard',
  setup() {
    const stats = ref({
      total_vms: 0,
      running_vms: 0,
      stopped_vms: 0,
      paused_vms: 0,
      datacenters: 0,
      total_nodes: 0
    })

    const resources = ref(null)

    const cpuPercentage = computed(() => {
      if (!resources.value) return 0
      return Math.round(
        (resources.value.used_cpu_cores / resources.value.total_cpu_cores) * 100
      )
    })

    const memoryPercentage = computed(() => {
      if (!resources.value) return 0
      return Math.round(
        (resources.value.used_memory_gb / resources.value.total_memory_gb) * 100
      )
    })

    const diskPercentage = computed(() => {
      if (!resources.value) return 0
      return Math.round(
        (resources.value.used_disk_gb / resources.value.total_disk_gb) * 100
      )
    })

    const fetchData = async () => {
      try {
        const [statsResponse, resourcesResponse] = await Promise.all([
          api.dashboard.getStats(),
          api.dashboard.getResources()
        ])

        stats.value = statsResponse.data
        resources.value = resourcesResponse.data
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      }
    }

    onMounted(() => {
      fetchData()
    })

    return {
      stats,
      resources,
      cpuPercentage,
      memoryPercentage,
      diskPercentage
    }
  }
}
</script>

<style scoped>
.stats-row {
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem !important;
  flex: 1;
  min-width: 0;
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  border-color: var(--primary-color);
}

.stat-card:active {
  transform: translateY(0);
}

.stat-icon {
  font-size: 1.5rem;
  opacity: 0.8;
  flex-shrink: 0;
}

.stat-icon.success {
  color: var(--secondary-color);
}

.stat-icon.danger {
  color: var(--danger-color);
}

.stat-info {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  white-space: nowrap;
}

.stat-label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  margin: 0;
  white-space: nowrap;
}

.resources {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.resource-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.resource-label {
  font-weight: 500;
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.resource-bar {
  height: 0.375rem;
  background-color: var(--background);
  border-radius: 9999px;
  overflow: hidden;
}

.resource-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
  transition: width 0.3s ease;
}

.resource-value {
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.action-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  text-decoration: none;
  transition: all 0.2s;
}

.action-button:hover {
  background-color: var(--background);
  border-color: var(--primary-color);
}

.action-icon {
  font-size: 1.25rem;
}

.action-title {
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  font-size: 0.85rem;
}

.action-desc {
  font-size: 0.7rem;
  color: var(--text-secondary);
  margin: 0;
}
</style>
