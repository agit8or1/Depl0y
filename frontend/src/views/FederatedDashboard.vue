<template>
  <div class="federation-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header-row">
        <div>
          <h2>Federation View</h2>
          <p class="text-muted">Unified cross-cluster overview across all registered Proxmox hosts</p>
        </div>
        <div class="header-actions">
          <span v-if="fetchedAt" class="text-muted text-sm">
            Updated {{ formatRelativeTime(fetchedAt) }}
          </span>
          <button @click="refresh" class="btn btn-outline" :disabled="loading">
            <span v-if="!loading">Refresh</span>
            <span v-else>Loading...</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading && !summary" class="loading-spinner"></div>

    <!-- No hosts state -->
    <div v-else-if="!loading && summary && summary.hosts.length === 0" class="empty-state card">
      <p class="text-muted">No Proxmox hosts registered yet.</p>
      <router-link to="/proxmox" class="btn btn-primary mt-1">Add Proxmox Host</router-link>
    </div>

    <template v-else-if="summary">
      <!-- Global Stats Bar -->
      <div class="global-stats-grid mb-2">
        <div class="stat-card">
          <div class="stat-value">{{ summary.total_vms }}</div>
          <div class="stat-label">Total VMs</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary.total_lxc }}</div>
          <div class="stat-label">Total LXC</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary.total_nodes }}</div>
          <div class="stat-label">Total Nodes</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary.online_hosts }} / {{ summary.hosts.length }}</div>
          <div class="stat-label">Hosts Online</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary.total_storage_used_gb }} GB</div>
          <div class="stat-label">Storage Used</div>
          <div class="stat-sub">of {{ summary.total_storage_total_gb }} GB</div>
        </div>
      </div>

      <!-- Per-Host Cards Grid -->
      <div class="section-title">Proxmox Clusters</div>
      <div class="hosts-grid mb-2">
        <div
          v-for="host in summary.hosts"
          :key="host.host_id"
          class="host-card"
          :class="{ 'host-card--offline': host.status === 'offline' }"
        >
          <!-- Card Header -->
          <div class="host-card-header">
            <div class="host-title-row">
              <h3 class="host-name">{{ host.host_name }}</h3>
              <span :class="['badge', statusBadgeClass(host.status)]">
                {{ host.status }}
              </span>
            </div>
            <div class="host-meta">
              <span class="text-muted text-sm">{{ host.api_url }}</span>
              <span v-if="host.cluster_name" class="cluster-name text-sm">
                Cluster: <strong>{{ host.cluster_name }}</strong>
              </span>
            </div>
          </div>

          <!-- Counts row -->
          <div class="host-counts">
            <div class="count-item">
              <span class="count-val">{{ host.node_count }}</span>
              <span class="count-lbl">Nodes</span>
            </div>
            <div class="count-item">
              <span class="count-val">{{ host.vm_count }}</span>
              <span class="count-lbl">VMs</span>
            </div>
            <div class="count-item">
              <span class="count-val">{{ host.lxc_count }}</span>
              <span class="count-lbl">LXC</span>
            </div>
            <div class="count-item">
              <span v-if="host.latency_ms != null" :class="['badge', 'badge-sm', latencyBadgeClass(host.latency_ms)]">
                {{ host.latency_ms }}ms
              </span>
              <span v-else class="count-lbl">—</span>
              <span class="count-lbl">Latency</span>
            </div>
          </div>

          <!-- Usage bars (only when online) -->
          <div v-if="host.status === 'online'" class="host-usage">
            <!-- CPU -->
            <div class="usage-row">
              <span class="usage-label">CPU</span>
              <div class="usage-bar-wrap">
                <div class="usage-bar">
                  <div
                    class="usage-bar-fill"
                    :class="barClass(host.cpu_usage_pct)"
                    :style="{ width: host.cpu_usage_pct + '%' }"
                  ></div>
                </div>
                <span class="usage-pct">{{ host.cpu_usage_pct }}%</span>
              </div>
            </div>
            <!-- Memory -->
            <div class="usage-row">
              <span class="usage-label">Memory</span>
              <div class="usage-bar-wrap">
                <div class="usage-bar">
                  <div
                    class="usage-bar-fill"
                    :class="barClass(host.memory_usage_pct)"
                    :style="{ width: host.memory_usage_pct + '%' }"
                  ></div>
                </div>
                <span class="usage-pct">
                  {{ host.memory_usage_pct }}%
                  ({{ formatGB(host.memory_used_bytes) }} / {{ formatGB(host.memory_total_bytes) }} GB)
                </span>
              </div>
            </div>
            <!-- Storage -->
            <div class="usage-row">
              <span class="usage-label">Storage</span>
              <div class="usage-bar-wrap">
                <div class="usage-bar">
                  <div
                    class="usage-bar-fill"
                    :class="barClass(storageUsedPct(host))"
                    :style="{ width: storageUsedPct(host) + '%' }"
                  ></div>
                </div>
                <span class="usage-pct">
                  {{ host.storage_used_gb }} / {{ host.storage_total_gb }} GB
                </span>
              </div>
            </div>
          </div>

          <!-- Cluster health badge -->
          <div class="host-card-footer">
            <span :class="['badge', healthBadgeClass(host.cluster_health)]">
              {{ (host.cluster_health || 'unknown').toUpperCase() }}
            </span>
            <div class="quick-links">
              <router-link :to="`/proxmox/${host.host_id}/cluster`" class="link-btn">Cluster</router-link>
              <router-link :to="`/vms?host=${host.host_id}`" class="link-btn">VMs</router-link>
              <router-link :to="`/proxmox`" class="link-btn">Nodes</router-link>
            </div>
          </div>
        </div>
      </div>

      <!-- Cross-Host VM Search -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Cross-Host VM Search</h3>
        </div>
        <div class="search-bar">
          <input
            v-model="vmSearchQuery"
            @input="onVmSearchInput"
            class="form-control"
            placeholder="Search VMs across all hosts by name or ID..."
          />
        </div>

        <div v-if="vmSearchLoading" class="loading-spinner"></div>

        <div v-else-if="vmSearchQuery.length >= 2 && vmSearchResults.length === 0" class="text-center text-muted p-2">
          No VMs found matching "{{ vmSearchQuery }}"
        </div>

        <div v-else-if="vmSearchResults.length > 0" class="search-results">
          <div v-for="group in vmSearchResults" :key="group.host_id" class="search-group">
            <div class="search-group-header">{{ group.host_name }}</div>
            <div class="search-group-items">
              <div
                v-for="vm in group.vms"
                :key="`${group.host_id}-${vm.vmid}`"
                class="search-result-item"
                @click="navigateToVm(group.host_id, vm)"
              >
                <span class="vm-name">{{ vm.name || '(no name)' }}</span>
                <span class="vm-meta text-sm text-muted">
                  ID: {{ vm.vmid }} &bull; {{ vm.node }} &bull;
                  <span :class="['badge', 'badge-sm', vm.status === 'running' ? 'badge-success' : 'badge-secondary']">
                    {{ vm.status }}
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Cross-Host Recent Tasks -->
      <div class="card">
        <div class="card-header">
          <h3>Recent Tasks (All Hosts)</h3>
          <button @click="fetchRecentTasks" class="btn btn-outline btn-sm" :disabled="tasksLoading">
            {{ tasksLoading ? 'Loading...' : 'Refresh' }}
          </button>
        </div>

        <div v-if="tasksLoading" class="loading-spinner"></div>

        <div v-else-if="recentTasks.length === 0" class="text-center text-muted p-2">
          No recent tasks found.
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Host</th>
                <th>Task</th>
                <th>Node</th>
                <th>Status</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in recentTasks" :key="`${task.host_id}-${task.upid}`">
                <td class="text-sm">{{ task.host_name }}</td>
                <td class="text-sm">{{ task.type || task.upid }}</td>
                <td class="text-sm">{{ task.node }}</td>
                <td>
                  <span :class="['badge', taskStatusClass(task.status)]">
                    {{ task.status || 'running' }}
                  </span>
                </td>
                <td class="text-sm">{{ formatDate(task.starttime) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

export default {
  name: 'FederatedDashboard',
  setup() {
    const router = useRouter()

    const loading = ref(false)
    const summary = ref(null)
    const fetchedAt = ref(null)

    // VM Search
    const vmSearchQuery = ref('')
    const vmSearchResults = ref([])
    const vmSearchLoading = ref(false)
    let vmSearchTimer = null

    // Tasks
    const recentTasks = ref([])
    const tasksLoading = ref(false)

    const fetchSummary = async () => {
      loading.value = true
      try {
        const response = await api.proxmox.getFederationSummary()
        summary.value = response.data
        fetchedAt.value = response.data.fetched_at
      } catch (error) {
        console.error('Failed to fetch federation summary:', error)
      } finally {
        loading.value = false
      }
    }

    const refresh = () => {
      fetchSummary()
      if (recentTasks.value.length > 0 || tasksLoading.value) {
        fetchRecentTasks()
      }
    }

    // Cross-host VM search
    const onVmSearchInput = () => {
      clearTimeout(vmSearchTimer)
      if (vmSearchQuery.value.length < 2) {
        vmSearchResults.value = []
        return
      }
      vmSearchTimer = setTimeout(() => {
        runVmSearch()
      }, 350)
    }

    const runVmSearch = async () => {
      if (!summary.value || summary.value.hosts.length === 0) return
      vmSearchLoading.value = true
      vmSearchResults.value = []
      const q = vmSearchQuery.value.toLowerCase()

      const onlineHosts = summary.value.hosts.filter(h => h.status === 'online')

      const searchTasks = onlineHosts.map(async (host) => {
        try {
          // Use cluster/resources to get all VMs for the host
          const res = await api.pveNode.clusterResources(host.host_id, 'qemu')
          const vms = Array.isArray(res.data) ? res.data : []
          const matched = vms.filter(vm => {
            const nameMatch = (vm.name || '').toLowerCase().includes(q)
            const idMatch = String(vm.vmid || '').includes(q)
            return nameMatch || idMatch
          })
          if (matched.length > 0) {
            return { host_id: host.host_id, host_name: host.host_name, vms: matched }
          }
        } catch (e) {
          console.warn(`VM search failed for host ${host.host_name}:`, e)
        }
        return null
      })

      const results = await Promise.allSettled(searchTasks)
      vmSearchResults.value = results
        .filter(r => r.status === 'fulfilled' && r.value !== null)
        .map(r => r.value)
      vmSearchLoading.value = false
    }

    const navigateToVm = (hostId, vm) => {
      router.push(`/proxmox/${hostId}/nodes/${vm.node}/vms/${vm.vmid}`)
    }

    // Cross-host tasks
    const fetchRecentTasks = async () => {
      if (!summary.value) return
      tasksLoading.value = true
      recentTasks.value = []

      const onlineHosts = summary.value.hosts.filter(h => h.status === 'online')

      const taskFetches = onlineHosts.map(async (host) => {
        try {
          // Get nodes for this host from the cluster status so we know which nodes to query
          const nodesRes = await api.proxmox.listNodes(host.host_id)
          const nodes = Array.isArray(nodesRes.data) ? nodesRes.data : []
          const nodeTasks = await Promise.allSettled(
            nodes.map(node =>
              api.pveNode.listTasks(host.host_id, node.node_name, { limit: 10 })
                .then(r => (Array.isArray(r.data) ? r.data : []).map(t => ({
                  ...t,
                  host_id: host.host_id,
                  host_name: host.host_name,
                  node: node.node_name,
                })))
            )
          )
          return nodeTasks
            .filter(r => r.status === 'fulfilled')
            .flatMap(r => r.value)
        } catch (e) {
          console.warn(`Task fetch failed for host ${host.host_name}:`, e)
          return []
        }
      })

      const all = await Promise.allSettled(taskFetches)
      const merged = all
        .filter(r => r.status === 'fulfilled')
        .flatMap(r => r.value)

      // Sort by starttime descending
      merged.sort((a, b) => (b.starttime || 0) - (a.starttime || 0))

      recentTasks.value = merged.slice(0, 50)
      tasksLoading.value = false
    }

    // Helpers
    const statusBadgeClass = (status) => {
      if (status === 'online') return 'badge-success'
      if (status === 'degraded') return 'badge-warning'
      return 'badge-danger'
    }

    const healthBadgeClass = (health) => {
      if (health === 'healthy') return 'badge-success'
      if (health === 'degraded') return 'badge-danger'
      return 'badge-secondary'
    }

    const latencyBadgeClass = (ms) => {
      if (ms == null) return 'badge-secondary'
      if (ms < 100) return 'badge-success'
      if (ms < 500) return 'badge-warning'
      return 'badge-danger'
    }

    const barClass = (pct) => {
      if (pct >= 80) return 'bar-danger'
      if (pct >= 60) return 'bar-warning'
      return 'bar-success'
    }

    const storageUsedPct = (host) => {
      if (!host.storage_total_gb) return 0
      return Math.round((host.storage_used_gb / host.storage_total_gb) * 100)
    }

    const formatGB = (bytes) => {
      if (!bytes) return '0'
      return (bytes / (1024 ** 3)).toFixed(1)
    }

    const formatDate = (val) => {
      if (!val) return '—'
      // Proxmox task starttimes are Unix timestamps (numbers)
      const d = typeof val === 'number' ? new Date(val * 1000) : new Date(val)
      return d.toLocaleString()
    }

    const formatRelativeTime = (isoStr) => {
      if (!isoStr) return ''
      const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000)
      if (diff < 10) return 'just now'
      if (diff < 60) return `${diff}s ago`
      return `${Math.floor(diff / 60)}m ago`
    }

    const taskStatusClass = (status) => {
      if (!status || status === 'running') return 'badge-info'
      if (status === 'OK') return 'badge-success'
      if (status.startsWith('WARN')) return 'badge-warning'
      return 'badge-danger'
    }

    onMounted(() => {
      fetchSummary().then(() => {
        fetchRecentTasks()
      })
    })

    return {
      loading,
      summary,
      fetchedAt,
      vmSearchQuery,
      vmSearchResults,
      vmSearchLoading,
      recentTasks,
      tasksLoading,
      refresh,
      onVmSearchInput,
      navigateToVm,
      fetchRecentTasks,
      statusBadgeClass,
      healthBadgeClass,
      latencyBadgeClass,
      barClass,
      storageUsedPct,
      formatGB,
      formatDate,
      formatRelativeTime,
      taskStatusClass,
    }
  }
}
</script>

<style scoped>
.federation-page {
  padding-bottom: 2rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}

/* Global stats bar */
.global-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem;
}

.stat-card {
  background: var(--card-background, #fff);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem 1rem;
  text-align: center;
  box-shadow: var(--shadow-sm, none);
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--primary-color, #3b82f6);
  line-height: 1;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.stat-sub {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.1rem;
}

/* Section title */
.section-title {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

/* Hosts grid */
.hosts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1rem;
}

.host-card {
  background: var(--card-background, #fff);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem;
  box-shadow: var(--shadow-sm, none);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.host-card--offline {
  opacity: 0.65;
}

.host-card-header {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.host-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.host-name {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.host-meta {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.cluster-name {
  color: var(--text-secondary);
}

/* Counts row */
.host-counts {
  display: flex;
  gap: 1.25rem;
  flex-wrap: wrap;
}

.count-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
}

.count-val {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.count-lbl {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.badge-sm {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
}

/* Usage bars */
.host-usage {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.usage-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
}

.usage-label {
  width: 4.5rem;
  flex-shrink: 0;
  color: var(--text-secondary);
  font-weight: 500;
}

.usage-bar-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
}

.usage-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
  min-width: 0;
}

.usage-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.bar-success { background-color: #22c55e; }
.bar-warning { background-color: #f59e0b; }
.bar-danger  { background-color: #ef4444; }

.usage-pct {
  font-size: 0.75rem;
  color: var(--text-primary);
  font-family: monospace;
  white-space: nowrap;
}

/* Card footer */
.host-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-color);
}

.quick-links {
  display: flex;
  gap: 0.5rem;
}

.link-btn {
  font-size: 0.8rem;
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.25rem;
  color: var(--primary-color, #3b82f6);
  text-decoration: none;
  transition: background 0.15s;
}

.link-btn:hover {
  background: var(--border-color);
}

/* VM Search */
.search-bar {
  padding: 1rem;
  border-bottom: 1px solid var(--border-color);
}

.search-results {
  padding: 0.5rem 0;
}

.search-group {
  margin-bottom: 0.5rem;
}

.search-group-header {
  padding: 0.5rem 1rem;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
  background: var(--background, #f9fafb);
}

.search-group-items {
  padding: 0 0.5rem;
}

.search-result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 0.75rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background 0.15s;
  gap: 0.5rem;
}

.search-result-item:hover {
  background: var(--border-color);
}

.vm-name {
  font-weight: 500;
  color: var(--text-primary);
}

.vm-meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

/* Empty / padding helpers */
.empty-state {
  text-align: center;
  padding: 3rem 1rem;
}

.p-2 {
  padding: 1.5rem;
}

.mt-1 {
  margin-top: 0.5rem;
}

/* Badge variants used here */
.badge-info {
  background-color: #3b82f6;
  color: #fff;
}

.badge-warning {
  background-color: #f59e0b;
  color: #fff;
}

.badge-secondary {
  background-color: var(--text-secondary, #6b7280);
  color: #fff;
}

.badge-danger {
  background-color: #ef4444;
  color: #fff;
}
</style>
