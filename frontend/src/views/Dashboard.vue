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

        <!-- Quick VM Search -->
        <div class="quick-search-wrap">
          <div class="quick-search-input-row">
            <span class="quick-search-icon">🔍</span>
            <input
              v-model="vmSearchQuery"
              type="text"
              class="quick-search-input"
              placeholder="Search VMs by name or VMID..."
              @keyup.escape="vmSearchQuery = ''"
            />
            <button v-if="vmSearchQuery" class="quick-search-clear" @click="vmSearchQuery = ''">×</button>
          </div>
          <div v-if="vmSearchQuery.trim() && vmSearchResults.length > 0" class="quick-search-results">
            <div
              v-for="vm in vmSearchResults"
              :key="`${vm.hostId}-${vm.node}-${vm.vmid}`"
              class="quick-search-result-item"
              @click="navigateToVM(vm)"
            >
              <span class="qsr-vmid">{{ vm.vmid }}</span>
              <span class="qsr-name">{{ vm.name || '(no name)' }}</span>
              <span :class="['qsr-status', vm.status === 'running' ? 'qsr-running' : vm.status === 'stopped' ? 'qsr-stopped' : 'qsr-other']">
                {{ vm.status }}
              </span>
              <span class="qsr-node">{{ vm.node }}</span>
            </div>
          </div>
          <div v-else-if="vmSearchQuery.trim() && vmSearchResults.length === 0 && !pveLoading" class="quick-search-empty">
            No VMs found matching "{{ vmSearchQuery }}"
          </div>
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

    <!-- Sparkline Resource Trends + Top Consumers row -->
    <div class="grid grid-cols-2 gap-2 mt-2">
      <!-- Sparkline trends -->
      <div class="card">
        <div class="card-header">
          <h3>Resource Trends</h3>
          <span class="pve-live-badge">Last Hour</span>
        </div>
        <div v-if="sparkLoading" class="hosts-loading">Loading trend data...</div>
        <div v-else-if="sparkLines.cpu.length === 0" class="hosts-empty">No trend data available. Requires an active Proxmox host.</div>
        <div v-else class="sparklines-wrap">
          <div class="sparkline-row">
            <span class="spark-label">CPU</span>
            <svg class="sparkline-svg" viewBox="0 0 200 40" preserveAspectRatio="none">
              <polyline
                :points="buildSparkPoints(sparkLines.cpu, 200, 40)"
                fill="none"
                stroke="var(--primary-color)"
                stroke-width="1.5"
              />
              <polyline
                :points="buildSparkFill(sparkLines.cpu, 200, 40)"
                fill="rgba(59,130,246,0.12)"
                stroke="none"
              />
            </svg>
            <span class="spark-val">{{ sparkLines.cpu.length ? (sparkLines.cpu[sparkLines.cpu.length-1]*100).toFixed(1) + '%' : '—' }}</span>
          </div>
          <div class="sparkline-row">
            <span class="spark-label">Memory</span>
            <svg class="sparkline-svg" viewBox="0 0 200 40" preserveAspectRatio="none">
              <polyline
                :points="buildSparkPoints(sparkLines.mem, 200, 40)"
                fill="none"
                stroke="#10b981"
                stroke-width="1.5"
              />
              <polyline
                :points="buildSparkFill(sparkLines.mem, 200, 40)"
                fill="rgba(16,185,129,0.12)"
                stroke="none"
              />
            </svg>
            <span class="spark-val">{{ sparkLines.mem.length ? (sparkLines.mem[sparkLines.mem.length-1]*100).toFixed(1) + '%' : '—' }}</span>
          </div>
          <div class="sparkline-row" v-if="sparkLines.net.length">
            <span class="spark-label">Net (in)</span>
            <svg class="sparkline-svg" viewBox="0 0 200 40" preserveAspectRatio="none">
              <polyline
                :points="buildSparkPoints(sparkLines.net, 200, 40)"
                fill="none"
                stroke="#f59e0b"
                stroke-width="1.5"
              />
              <polyline
                :points="buildSparkFill(sparkLines.net, 200, 40)"
                fill="rgba(245,158,11,0.12)"
                stroke="none"
              />
            </svg>
            <span class="spark-val">{{ formatNetRate(sparkLines.net[sparkLines.net.length-1]) }}</span>
          </div>
        </div>
      </div>

      <!-- Top 5 CPU consumers -->
      <div class="card">
        <div class="card-header">
          <h3>Top Resource Consumers</h3>
          <span class="pve-live-badge">PVE Live</span>
        </div>
        <div v-if="pveLoading" class="hosts-loading">Loading...</div>
        <div v-else-if="topConsumers.length === 0" class="hosts-empty">No running VMs found.</div>
        <div v-else class="consumers-list">
          <div
            v-for="vm in topConsumers"
            :key="`${vm.hostId}-${vm.node}-${vm.vmid}`"
            class="consumer-item"
            @click="navigateToVM(vm)"
          >
            <div class="consumer-name">
              <span class="consumer-id">{{ vm.vmid }}</span>
              <span class="consumer-vmname">{{ vm.name || '(no name)' }}</span>
              <span class="consumer-node">{{ vm.node }}</span>
            </div>
            <div class="consumer-bars">
              <div class="cbar-row">
                <span class="cbar-label">CPU</span>
                <div class="cbar-track"><div class="cbar-fill cbar-cpu" :style="{ width: Math.min(100, (vm.cpu || 0)*100).toFixed(1) + '%' }"></div></div>
                <span class="cbar-pct">{{ ((vm.cpu || 0)*100).toFixed(1) }}%</span>
              </div>
              <div class="cbar-row">
                <span class="cbar-label">Mem</span>
                <div class="cbar-track"><div class="cbar-fill cbar-mem" :style="{ width: vm.memPct.toFixed(1) + '%' }"></div></div>
                <span class="cbar-pct">{{ vm.memPct.toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Alerts Panel -->
    <div class="card mt-2" v-if="alerts.length > 0 || alertsChecked">
      <div class="card-header">
        <h3>Alerts</h3>
        <span class="pve-live-badge">PVE Live</span>
      </div>
      <div v-if="alerts.length === 0" class="hosts-empty">No alerts. All systems nominal.</div>
      <div v-else class="alerts-list">
        <div
          v-for="(alert, i) in alerts"
          :key="i"
          class="alert-item"
          :class="'alert-' + alert.severity"
        >
          <span class="alert-icon">{{ alert.icon }}</span>
          <div class="alert-body">
            <span class="alert-title">{{ alert.title }}</span>
            <span class="alert-detail">{{ alert.detail }}</span>
          </div>
          <span class="alert-badge" :class="'alert-badge-' + alert.severity">{{ alert.severity }}</span>
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
import { useRouter } from 'vue-router'
import api from '@/services/api'

export default {
  name: 'Dashboard',
  setup() {
    const router = useRouter()

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

    // Quick VM search state
    const vmSearchQuery = ref('')
    const allVmList = ref([])

    const vmSearchResults = computed(() => {
      const q = vmSearchQuery.value.trim().toLowerCase()
      if (!q) return []
      return allVmList.value.filter(vm =>
        (vm.name || '').toLowerCase().includes(q) ||
        String(vm.vmid).includes(q)
      ).slice(0, 8)
    })

    const navigateToVM = (vm) => {
      vmSearchQuery.value = ''
      router.push(`/proxmox/${vm.hostId}/nodes/${vm.node}/vms/${vm.vmid}`)
    }

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

        const vmListAccum = []
        resourceResults.forEach((result, idx) => {
          const host = activeHosts[idx]
          if (result.status === 'fulfilled') {
            const items = result.value.data || []
            let hostNodeCount = 0
            items.forEach(item => {
              if (item.type === 'qemu') {
                totalVms++
                if (item.status === 'running') runningVms++
                vmListAccum.push({
                  hostId: host.id,
                  node: item.node,
                  vmid: item.vmid,
                  name: item.name,
                  status: item.status || 'unknown',
                  cpu: item.cpu || 0,
                  mem: item.mem || 0,
                  maxmem: item.maxmem || 0,
                })
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
        allVmList.value = vmListAccum

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

    // ── Sparklines ────────────────────────────────────────────────────────────
    const sparkLoading = ref(false)
    const sparkLines = ref({ cpu: [], mem: [], net: [] })

    const buildSparkPoints = (data, w, h) => {
      if (!data || data.length < 2) return ''
      const max = Math.max(...data, 0.001)
      return data.map((v, i) => {
        const x = (i / (data.length - 1)) * w
        const y = h - (v / max) * (h - 4) - 2
        return `${x.toFixed(1)},${y.toFixed(1)}`
      }).join(' ')
    }

    const buildSparkFill = (data, w, h) => {
      if (!data || data.length < 2) return ''
      const pts = buildSparkPoints(data, w, h)
      return `${pts} ${w},${h} 0,${h}`
    }

    const formatNetRate = (bps) => {
      if (!bps) return '0 B/s'
      if (bps < 1024) return `${bps.toFixed(0)} B/s`
      if (bps < 1024 * 1024) return `${(bps / 1024).toFixed(1)} KB/s`
      return `${(bps / (1024 * 1024)).toFixed(1)} MB/s`
    }

    const fetchSparklines = async () => {
      sparkLoading.value = true
      try {
        const hostsResp = await api.proxmox.listHosts()
        const hosts = hostsResp.data || []
        const active = hosts.filter(h => h.is_active)
        if (!active.length) return

        // Get first active host's nodes and fetch RRD for the first node
        const resourcesResp = await api.pveNode.clusterResources(active[0].id)
        const nodes = (resourcesResp.data || []).filter(i => i.type === 'node').map(i => i.node)
        if (!nodes.length) return

        const rrdResp = await api.pveNode.nodeRrdData(active[0].id, nodes[0], { timeframe: 'hour', cf: 'AVERAGE' })
        const rows = rrdResp.data || []
        if (!rows.length) return

        sparkLines.value = {
          cpu: rows.map(r => r.cpu || 0),
          mem: rows.map(r => (r.memused && r.memtotal) ? r.memused / r.memtotal : 0),
          net: rows.map(r => r.netin || 0),
        }
      } catch (e) {
        // silently ignore — sparklines are optional
      } finally {
        sparkLoading.value = false
      }
    }

    // ── Top Consumers ─────────────────────────────────────────────────────────
    const topConsumers = computed(() => {
      return allVmList.value
        .filter(vm => vm.status === 'running' && (vm.cpu > 0 || vm.maxmem > 0))
        .map(vm => ({
          ...vm,
          memPct: vm.maxmem > 0 ? (vm.mem / vm.maxmem) * 100 : 0
        }))
        .sort((a, b) => (b.cpu || 0) - (a.cpu || 0))
        .slice(0, 5)
    })

    // ── Alerts ────────────────────────────────────────────────────────────────
    const alerts = ref([])
    const alertsChecked = ref(false)

    const buildAlerts = () => {
      const result = []

      // Failed tasks
      recentTasks.value.forEach(task => {
        if (task.status && (task.status.toLowerCase() === 'error' || task.status.toLowerCase().includes('fail'))) {
          result.push({
            severity: 'error',
            icon: '&#9888;&#65039;',
            title: `Task failed: ${task.type}`,
            detail: `Node: ${task.node} on ${task.hostName} — started ${formatTaskTime(task.starttime)}`
          })
        }
      })

      // Stopped VMs that were in the list before (simple heuristic: any stopped non-template VM)
      allVmList.value.forEach(vm => {
        if (vm.status === 'stopped' && vm.name) {
          // Only alert if VM had recent stop (uptime was non-zero last time — we use a local map)
          // Since we don't have historical state, just surface all stopped VMs as info
        }
      })

      // Storage over 85% — check from resources if available
      if (resources.value) {
        const diskPct = resources.value.total_disk_gb > 0
          ? (resources.value.used_disk_gb / resources.value.total_disk_gb) * 100
          : 0
        if (diskPct > 85) {
          result.push({
            severity: 'warning',
            icon: '&#128190;',
            title: 'Storage usage above 85%',
            detail: `${resources.value.used_disk_gb} GB used of ${resources.value.total_disk_gb} GB (${diskPct.toFixed(1)}%)`
          })
        }
        const memPct = resources.value.total_memory_gb > 0
          ? (resources.value.used_memory_gb / resources.value.total_memory_gb) * 100
          : 0
        if (memPct > 90) {
          result.push({
            severity: 'warning',
            icon: '&#129778;',
            title: 'Memory usage above 90%',
            detail: `${resources.value.used_memory_gb} GB used of ${resources.value.total_memory_gb} GB (${memPct.toFixed(1)}%)`
          })
        }
      }

      // Offline cluster nodes
      clusterHealthData.value.forEach(entry => {
        if (entry.error) {
          result.push({
            severity: 'error',
            icon: '&#127970;',
            title: `Host unreachable: ${entry.hostName}`,
            detail: entry.error
          })
        }
        entry.nodes && entry.nodes.forEach(n => {
          if (!n.online) {
            result.push({
              severity: 'error',
              icon: '&#128293;',
              title: `Node offline: ${n.name}`,
              detail: `Host: ${entry.hostName}`
            })
          }
        })
      })

      alerts.value = result
      alertsChecked.value = true
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

    onMounted(async () => {
      fetchData()
      await fetchPveData()
      fetchClusterHealth().then(() => buildAlerts())
      fetchRecentTasks().then(() => buildAlerts())
      fetchSparklines()

      const intervalSecs = parseInt(localStorage.getItem('depl0y_refresh_interval') || '30', 10)
      const intervalMs = intervalSecs * 1000

      refreshInterval = setInterval(async () => {
        fetchData()
        await fetchPveData()
        fetchClusterHealth().then(() => buildAlerts())
        fetchRecentTasks().then(() => buildAlerts())
        fetchSparklines()
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
      lastUpdatedSeconds,
      // quick VM search
      vmSearchQuery,
      vmSearchResults,
      navigateToVM,
      // sparklines
      sparkLoading,
      sparkLines,
      buildSparkPoints,
      buildSparkFill,
      formatNetRate,
      // top consumers
      topConsumers,
      // alerts
      alerts,
      alertsChecked,
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

/* ── Quick VM Search ─────────────────────────────────────────────────────── */
.quick-search-wrap {
  padding: 0.6rem 0.75rem 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.quick-search-input-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.3rem 0.5rem;
  transition: border-color 0.15s;
}

.quick-search-input-row:focus-within {
  border-color: var(--primary-color);
}

.quick-search-icon {
  font-size: 0.85rem;
  flex-shrink: 0;
  opacity: 0.6;
}

.quick-search-input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.85rem;
  outline: none;
  min-width: 0;
}

.quick-search-input::placeholder {
  color: var(--text-secondary);
}

.quick-search-clear {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.1rem;
  flex-shrink: 0;
}

.quick-search-clear:hover {
  color: var(--text-primary);
}

.quick-search-results {
  margin-top: 0.4rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
  max-height: 240px;
  overflow-y: auto;
}

.quick-search-result-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.6rem;
  cursor: pointer;
  font-size: 0.82rem;
  transition: background 0.1s;
  border-bottom: 1px solid var(--border-color);
}

.quick-search-result-item:last-child {
  border-bottom: none;
}

.quick-search-result-item:hover {
  background: var(--background);
}

.qsr-vmid {
  font-weight: 700;
  color: var(--text-secondary);
  min-width: 2.5rem;
  font-size: 0.75rem;
}

.qsr-name {
  flex: 1;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.qsr-status {
  font-size: 0.68rem;
  font-weight: 600;
  padding: 0.1rem 0.35rem;
  border-radius: 9999px;
  white-space: nowrap;
  text-transform: lowercase;
}

.qsr-running {
  background-color: rgba(34, 197, 94, 0.15);
  color: var(--secondary-color, #22c55e);
}

.qsr-stopped {
  background-color: rgba(239, 68, 68, 0.12);
  color: var(--danger-color, #ef4444);
}

.qsr-other {
  background-color: rgba(100, 116, 139, 0.15);
  color: var(--text-secondary);
}

.qsr-node {
  font-size: 0.72rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.quick-search-empty {
  margin-top: 0.4rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
  padding: 0.25rem 0.1rem;
}

/* ── Sparklines ─────────────────────────────────────────────────────────── */
.sparklines-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.25rem 0;
}

.sparkline-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.spark-label {
  font-size: 0.72rem;
  color: var(--text-secondary);
  font-weight: 600;
  width: 3.5rem;
  flex-shrink: 0;
}

.sparkline-svg {
  flex: 1;
  height: 36px;
  display: block;
}

.spark-val {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-primary);
  width: 4rem;
  text-align: right;
  flex-shrink: 0;
}

/* ── Top Consumers ─────────────────────────────────────────────────────── */
.consumers-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.consumer-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.45rem 0.5rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background 0.1s;
}

.consumer-item:hover {
  background: var(--background);
}

.consumer-name {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
  flex: 0 0 40%;
}

.consumer-id {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.consumer-vmname {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.consumer-node {
  font-size: 0.68rem;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.consumer-bars {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.cbar-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.cbar-label {
  font-size: 0.65rem;
  color: var(--text-secondary);
  width: 2rem;
  flex-shrink: 0;
}

.cbar-track {
  flex: 1;
  height: 0.3rem;
  background: var(--border-color);
  border-radius: 9999px;
  overflow: hidden;
}

.cbar-fill {
  height: 100%;
  border-radius: 9999px;
  transition: width 0.3s;
}

.cbar-cpu {
  background: var(--primary-color);
}

.cbar-mem {
  background: #10b981;
}

.cbar-pct {
  font-size: 0.65rem;
  color: var(--text-secondary);
  width: 2.5rem;
  text-align: right;
  flex-shrink: 0;
}

/* ── Alerts ─────────────────────────────────────────────────────────────── */
.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.5rem 0.65rem;
  border-radius: 0.375rem;
  font-size: 0.82rem;
  border-left: 3px solid transparent;
}

.alert-error {
  border-left-color: var(--danger-color, #ef4444);
  background: rgba(239, 68, 68, 0.05);
}

.alert-warning {
  border-left-color: #f59e0b;
  background: rgba(245, 158, 11, 0.05);
}

.alert-info {
  border-left-color: var(--primary-color);
  background: rgba(59, 130, 246, 0.05);
}

.alert-icon {
  font-size: 1rem;
  flex-shrink: 0;
  margin-top: 0.05rem;
}

.alert-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.alert-title {
  font-weight: 600;
  color: var(--text-primary);
}

.alert-detail {
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.alert-badge {
  font-size: 0.62rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.alert-badge-error {
  background: rgba(239, 68, 68, 0.12);
  color: var(--danger-color, #ef4444);
}

.alert-badge-warning {
  background: rgba(245, 158, 11, 0.15);
  color: #b45309;
}

.alert-badge-info {
  background: rgba(59, 130, 246, 0.15);
  color: var(--primary-color);
}
</style>
