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

    <!-- PVE Live stats row -->
    <div class="pve-live-header mb-1">
      <span class="pve-live-badge">PVE Live</span>
      <span class="pve-live-label">Live data from Proxmox cluster resources</span>
    </div>
    <div class="stats-row mb-2">
      <div class="stat-card card" :class="{ 'loading-card': pveLoading }">
        <div class="stat-icon">🖥️</div>
        <div class="stat-info">
          <p class="stat-value">
            <span v-if="pveLoading" class="loading-dot">—</span>
            <span v-else>{{ pveStats.totalVms }}</span>
          </p>
          <p class="stat-label">Total VMs</p>
        </div>
      </div>

      <div class="stat-card card" :class="{ 'loading-card': pveLoading }">
        <div class="stat-icon success">▶️</div>
        <div class="stat-info">
          <p class="stat-value">
            <span v-if="pveLoading" class="loading-dot">—</span>
            <span v-else>{{ pveStats.runningVms }}</span>
          </p>
          <p class="stat-label">Running VMs</p>
        </div>
      </div>

      <div class="stat-card card" :class="{ 'loading-card': pveLoading }">
        <div class="stat-icon">📦</div>
        <div class="stat-info">
          <p class="stat-value">
            <span v-if="pveLoading" class="loading-dot">—</span>
            <span v-else>{{ pveStats.totalLxc }}</span>
          </p>
          <p class="stat-label">LXC Containers</p>
        </div>
      </div>

      <div class="stat-card card" :class="{ 'loading-card': pveLoading }">
        <div class="stat-icon">🖧</div>
        <div class="stat-info">
          <p class="stat-value">
            <span v-if="pveLoading" class="loading-dot">—</span>
            <span v-else>{{ pveStats.totalNodes }}</span>
          </p>
          <p class="stat-label">Nodes</p>
        </div>
      </div>
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
          <router-link to="/deploy" class="action-button">
            <span class="action-icon">➕</span>
            <div>
              <p class="action-title">Deploy VM</p>
              <p class="action-desc">Create and deploy a new virtual machine</p>
            </div>
          </router-link>

          <router-link to="/create-lxc" class="action-button">
            <span class="action-icon">📦</span>
            <div>
              <p class="action-title">Create LXC</p>
              <p class="action-desc">Provision a new LXC container</p>
            </div>
          </router-link>

          <router-link to="/images" class="action-button">
            <span class="action-icon">🖼️</span>
            <div>
              <p class="action-title">Browse Images</p>
              <p class="action-desc">View and manage disk images</p>
            </div>
          </router-link>

          <router-link to="/tasks" class="action-button">
            <span class="action-icon">📋</span>
            <div>
              <p class="action-title">View Tasks</p>
              <p class="action-desc">Monitor running and recent tasks</p>
            </div>
          </router-link>

          <router-link to="/settings" class="action-button">
            <span class="action-icon">🔄</span>
            <div>
              <p class="action-title">Check Updates</p>
              <p class="action-desc">Review and apply system updates</p>
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

    <!-- Proxmox Hosts summary -->
    <div class="card mt-2">
      <div class="card-header">
        <h3>Proxmox Hosts</h3>
        <span class="pve-live-badge">PVE Live</span>
        <router-link to="/proxmox" class="hosts-manage-link">Manage</router-link>
      </div>
      <div v-if="hostsLoading" class="hosts-loading">
        Loading hosts...
      </div>
      <div v-else-if="proxmoxHosts.length === 0" class="hosts-empty">
        No Proxmox hosts configured.
        <router-link to="/proxmox">Add a host</router-link>
      </div>
      <table v-else class="hosts-table">
        <thead>
          <tr>
            <th>Host Name</th>
            <th>Address</th>
            <th>Nodes</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="host in proxmoxHosts" :key="host.id">
            <td class="host-name">{{ host.name }}</td>
            <td class="host-addr">{{ host.host }}</td>
            <td class="host-nodes">{{ hostNodeCounts[host.id] !== undefined ? hostNodeCounts[host.id] : '—' }}</td>
            <td>
              <span class="host-status-badge" :class="host.is_active ? 'status-active' : 'status-inactive'">
                {{ host.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td>
              <router-link to="/proxmox" class="host-link">View</router-link>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Cluster Health -->
    <div class="card mt-2">
      <div class="card-header">
        <h3>Cluster Health</h3>
        <span class="pve-live-badge">PVE Live</span>
      </div>
      <div v-if="clusterLoading" class="hosts-loading">Loading cluster status...</div>
      <div v-else-if="clusterHealthData.length === 0" class="hosts-empty">No cluster data available.</div>
      <div v-else class="cluster-panels">
        <div v-for="entry in clusterHealthData" :key="entry.hostId" class="cluster-panel">
          <div class="cluster-panel-header">
            <span class="cluster-host-name">{{ entry.hostName }}</span>
            <span v-if="entry.error" class="cluster-badge cluster-badge-error">Error</span>
            <span v-else-if="entry.standalone" class="cluster-badge cluster-badge-standalone">Standalone</span>
            <span v-else-if="entry.quorate" class="cluster-badge cluster-badge-ok">Quorate</span>
            <span v-else class="cluster-badge cluster-badge-danger">No Quorum</span>
          </div>
          <div v-if="entry.error" class="cluster-error-msg">{{ entry.error }}</div>
          <ul v-else class="cluster-members">
            <li v-for="node in entry.nodes" :key="node.name" class="cluster-member">
              <span class="cluster-dot" :class="node.online ? 'dot-online' : 'dot-offline'"></span>
              <span class="cluster-member-name">{{ node.name }}</span>
              <span class="cluster-member-status" :class="node.online ? 'text-online' : 'text-offline'">
                {{ node.online ? 'Online' : 'Offline' }}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Recent Tasks -->
    <div class="card mt-2">
      <div class="card-header">
        <h3>Recent Tasks</h3>
        <span class="pve-live-badge">PVE Live</span>
      </div>
      <div v-if="tasksLoading" class="hosts-loading">Loading recent tasks...</div>
      <div v-else-if="recentTasks.length === 0" class="hosts-empty">No recent tasks found.</div>
      <table v-else class="hosts-table">
        <thead>
          <tr>
            <th>Host</th>
            <th>Node</th>
            <th>Type</th>
            <th>Status</th>
            <th>Started</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in recentTasks" :key="task.upid">
            <td class="host-name">{{ task.hostName }}</td>
            <td>{{ task.node }}</td>
            <td>{{ task.type }}</td>
            <td>
              <span class="task-status-badge" :class="taskStatusClass(task.status)">
                {{ task.status || 'running' }}
              </span>
            </td>
            <td class="host-addr">{{ formatTaskTime(task.starttime) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="dashboard-footer">
      <span class="last-updated">Last updated: {{ lastUpdatedSeconds }}s ago</span>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
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

    // PVE Live state
    const pveLoading = ref(true)
    const pveStats = ref({
      totalVms: 0,
      runningVms: 0,
      totalLxc: 0,
      totalNodes: 0
    })

    // Proxmox Hosts summary state
    const hostsLoading = ref(true)
    const proxmoxHosts = ref([])
    const hostNodeCounts = ref({})

    // Cluster Health state
    const clusterLoading = ref(true)
    const clusterHealthData = ref([])

    // Recent Tasks state
    const tasksLoading = ref(true)
    const recentTasks = ref([])

    // Auto-refresh state
    const lastUpdatedSeconds = ref(0)
    let refreshInterval = null
    let tickInterval = null

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

    const fetchPveData = async () => {
      pveLoading.value = true
      try {
        // Load hosts first so we can query cluster resources per host
        const hostsResponse = await api.proxmox.listHosts()
        const hosts = hostsResponse.data || []
        proxmoxHosts.value = hosts
        hostsLoading.value = false

        if (hosts.length === 0) {
          pveLoading.value = false
          return
        }

        // Fetch cluster resources from all active hosts in parallel
        const activeHosts = hosts.filter(h => h.is_active)
        const resourceResults = await Promise.allSettled(
          activeHosts.map(h => api.pveNode.clusterResources(h.id))
        )

        let totalVms = 0
        let runningVms = 0
        let totalLxc = 0
        const nodeSet = new Set()
        const nodeCountMap = {}

        resourceResults.forEach((result, idx) => {
          const host = activeHosts[idx]
          if (result.status === 'fulfilled') {
            const items = result.value.data || []
            let hostNodeCount = 0
            items.forEach(item => {
              if (item.type === 'qemu') {
                totalVms++
                if (item.status === 'running') runningVms++
              } else if (item.type === 'lxc') {
                totalLxc++
              } else if (item.type === 'node') {
                nodeSet.add(`${host.id}:${item.node}`)
                hostNodeCount++
              }
            })
            nodeCountMap[host.id] = hostNodeCount
          }
        })

        // For inactive hosts, try to use cached node data via listNodes
        const inactiveHosts = hosts.filter(h => !h.is_active)
        const nodeResults = await Promise.allSettled(
          inactiveHosts.map(h => api.proxmox.listNodes(h.id))
        )
        nodeResults.forEach((result, idx) => {
          const host = inactiveHosts[idx]
          if (result.status === 'fulfilled') {
            const nodes = result.value.data || []
            nodeCountMap[host.id] = nodes.length
          } else {
            nodeCountMap[host.id] = 0
          }
        })

        hostNodeCounts.value = nodeCountMap
        pveStats.value = {
          totalVms,
          runningVms,
          totalLxc,
          totalNodes: nodeSet.size
        }
      } catch (error) {
        console.error('Failed to fetch PVE live data:', error)
        hostsLoading.value = false
      } finally {
        pveLoading.value = false
      }
    }

    const fetchClusterHealth = async () => {
      clusterLoading.value = true
      try {
        const hostsResponse = await api.proxmox.listHosts()
        const hosts = hostsResponse.data || []
        const activeHosts = hosts.filter(h => h.is_active)

        const results = await Promise.allSettled(
          activeHosts.map(h => api.pveNode.clusterStatus(h.id))
        )

        clusterHealthData.value = results.map((result, idx) => {
          const host = activeHosts[idx]
          if (result.status === 'rejected') {
            return {
              hostId: host.id,
              hostName: host.name,
              error: 'Failed to fetch cluster status',
              standalone: false,
              quorate: false,
              nodes: []
            }
          }

          const items = result.value.data || []
          // If no cluster items or all items are nodes with no cluster entry, treat as standalone
          const clusterEntry = items.find(i => i.type === 'cluster')
          const nodeItems = items.filter(i => i.type === 'node')

          if (!clusterEntry && nodeItems.length <= 1) {
            // Single-node standalone
            return {
              hostId: host.id,
              hostName: host.name,
              standalone: true,
              quorate: false,
              nodes: nodeItems.map(n => ({ name: n.name, online: n.online === 1 || n.online === true }))
            }
          }

          return {
            hostId: host.id,
            hostName: host.name,
            standalone: false,
            quorate: clusterEntry ? (clusterEntry.quorate === 1 || clusterEntry.quorate === true) : false,
            nodes: nodeItems.map(n => ({ name: n.name, online: n.online === 1 || n.online === true }))
          }
        })
      } catch (error) {
        console.error('Failed to fetch cluster health:', error)
      } finally {
        clusterLoading.value = false
      }
    }

    const fetchRecentTasks = async () => {
      tasksLoading.value = true
      try {
        const hostsResponse = await api.proxmox.listHosts()
        const hosts = hostsResponse.data || []
        const activeHosts = hosts.filter(h => h.is_active)

        // Get cluster resources to find node names per host
        const resourceResults = await Promise.allSettled(
          activeHosts.map(h => api.pveNode.clusterResources(h.id))
        )

        // Build list of { hostId, hostName, node } combos
        const nodeTargets = []
        resourceResults.forEach((result, idx) => {
          const host = activeHosts[idx]
          if (result.status === 'fulfilled') {
            const items = result.value.data || []
            const nodeNames = items.filter(i => i.type === 'node').map(i => i.node)
            // If no nodes found in resources, fall back to host name as node
            const names = nodeNames.length > 0 ? nodeNames : [host.host.split(':')[0].split('.')[0]]
            names.forEach(node => nodeTargets.push({ hostId: host.id, hostName: host.name, node }))
          }
        })

        // Fetch tasks for each node (limit 5 per node)
        const taskResults = await Promise.allSettled(
          nodeTargets.map(t => api.pveNode.listTasks(t.hostId, t.node, { limit: 5 }))
        )

        const allTasks = []
        taskResults.forEach((result, idx) => {
          const target = nodeTargets[idx]
          if (result.status === 'fulfilled') {
            const tasks = result.value.data || []
            tasks.forEach(task => {
              allTasks.push({
                upid: task.upid,
                hostName: target.hostName,
                node: task.node || target.node,
                type: task.type,
                status: task.status,
                starttime: task.starttime
              })
            })
          }
        })

        // Sort by starttime descending and take top 5 overall
        allTasks.sort((a, b) => (b.starttime || 0) - (a.starttime || 0))
        recentTasks.value = allTasks.slice(0, 5)
      } catch (error) {
        console.error('Failed to fetch recent tasks:', error)
      } finally {
        tasksLoading.value = false
      }
    }

    const taskStatusClass = (status) => {
      if (!status) return 'task-running'
      const s = status.toLowerCase()
      if (s === 'ok') return 'task-ok'
      if (s.includes('warn')) return 'task-warning'
      if (s === 'error' || s.includes('fail')) return 'task-error'
      return 'task-running'
    }

    const formatTaskTime = (ts) => {
      if (!ts) return '—'
      const d = new Date(ts * 1000)
      return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    }

    onMounted(() => {
      fetchData()
      fetchPveData()
      fetchClusterHealth()
      fetchRecentTasks()

      const intervalSecs = parseInt(localStorage.getItem('depl0y_refresh_interval') || '30', 10)
      const intervalMs = intervalSecs * 1000

      refreshInterval = setInterval(() => {
        fetchData()
        fetchPveData()
        fetchClusterHealth()
        fetchRecentTasks()
        lastUpdatedSeconds.value = 0
      }, intervalMs)

      tickInterval = setInterval(() => {
        lastUpdatedSeconds.value++
      }, 1000)
    })

    onUnmounted(() => {
      clearInterval(refreshInterval)
      clearInterval(tickInterval)
    })

    return {
      stats,
      resources,
      cpuPercentage,
      memoryPercentage,
      diskPercentage,
      pveLoading,
      pveStats,
      hostsLoading,
      proxmoxHosts,
      hostNodeCounts,
      clusterLoading,
      clusterHealthData,
      tasksLoading,
      recentTasks,
      taskStatusClass,
      formatTaskTime,
      lastUpdatedSeconds
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

.loading-card {
  opacity: 0.6;
}

.loading-dot {
  color: var(--text-secondary);
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

.pve-live-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.pve-live-badge {
  display: inline-block;
  background: var(--primary-color);
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
}

.pve-live-label {
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.mb-1 {
  margin-bottom: 0.4rem;
}

.mt-2 {
  margin-top: 0.75rem;
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
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
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

/* Proxmox Hosts summary table */
.card-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.card-header h3 {
  flex: 1;
}

.hosts-manage-link {
  font-size: 0.75rem;
  color: var(--primary-color);
  text-decoration: none;
  margin-left: auto;
}

.hosts-manage-link:hover {
  text-decoration: underline;
}

.hosts-loading,
.hosts-empty {
  font-size: 0.8rem;
  color: var(--text-secondary);
  padding: 0.5rem 0;
}

.hosts-empty a {
  color: var(--primary-color);
  text-decoration: none;
}

.hosts-empty a:hover {
  text-decoration: underline;
}

.hosts-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.hosts-table th {
  text-align: left;
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 0.7rem;
  padding: 0.35rem 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.hosts-table td {
  padding: 0.4rem 0.5rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
}

.hosts-table tbody tr:last-child td {
  border-bottom: none;
}

.hosts-table tbody tr:hover td {
  background-color: var(--background);
}

.host-name {
  font-weight: 600;
}

.host-addr {
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.host-nodes {
  text-align: center;
}

.host-status-badge {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.status-active {
  background-color: rgba(var(--secondary-color-rgb, 34, 197, 94), 0.15);
  color: var(--secondary-color);
}

.status-inactive {
  background-color: rgba(var(--danger-color-rgb, 239, 68, 68), 0.12);
  color: var(--danger-color);
}

.host-link {
  font-size: 0.75rem;
  color: var(--primary-color);
  text-decoration: none;
}

.host-link:hover {
  text-decoration: underline;
}

.dashboard-footer {
  margin-top: 0.75rem;
  text-align: right;
}

.last-updated {
  font-size: 0.7rem;
  color: var(--text-secondary);
}

/* Cluster Health */
.cluster-panels {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.cluster-panel {
  flex: 1;
  min-width: 160px;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.5rem 0.65rem;
}

.cluster-panel-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}

.cluster-host-name {
  font-weight: 600;
  font-size: 0.82rem;
  color: var(--text-primary);
  flex: 1;
}

.cluster-badge {
  font-size: 0.62rem;
  font-weight: 700;
  padding: 0.1rem 0.38rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.cluster-badge-ok {
  background-color: rgba(34, 197, 94, 0.15);
  color: var(--secondary-color, #22c55e);
}

.cluster-badge-danger {
  background-color: rgba(239, 68, 68, 0.12);
  color: var(--danger-color, #ef4444);
}

.cluster-badge-standalone {
  background-color: rgba(100, 116, 139, 0.15);
  color: var(--text-secondary);
}

.cluster-badge-error {
  background-color: rgba(239, 68, 68, 0.12);
  color: var(--danger-color, #ef4444);
}

.cluster-error-msg {
  font-size: 0.72rem;
  color: var(--danger-color, #ef4444);
}

.cluster-members {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.cluster-member {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.78rem;
}

.cluster-dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-online {
  background-color: var(--secondary-color, #22c55e);
}

.dot-offline {
  background-color: var(--danger-color, #ef4444);
}

.cluster-member-name {
  flex: 1;
  color: var(--text-primary);
}

.cluster-member-status {
  font-size: 0.7rem;
}

.text-online {
  color: var(--secondary-color, #22c55e);
}

.text-offline {
  color: var(--danger-color, #ef4444);
}

/* Recent Tasks */
.task-status-badge {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.task-ok {
  background-color: rgba(34, 197, 94, 0.15);
  color: var(--secondary-color, #22c55e);
}

.task-warning {
  background-color: rgba(234, 179, 8, 0.15);
  color: #ca8a04;
}

.task-error {
  background-color: rgba(239, 68, 68, 0.12);
  color: var(--danger-color, #ef4444);
}

.task-running {
  background-color: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}
</style>
