<template>
  <div class="cluster-page">
    <!-- Breadcrumb -->
    <nav class="breadcrumb-nav" aria-label="breadcrumb">
      <router-link to="/proxmox" class="breadcrumb-crumb">All Hosts</router-link>
      <span class="breadcrumb-sep">›</span>
      <span class="breadcrumb-crumb breadcrumb-crumb--current">{{ clusterName || hostId }}</span>
    </nav>

    <div class="page-header mb-2">
      <div>
        <h2>{{ clusterName ? clusterName + ' — Cluster' : 'Cluster Overview' }}</h2>
        <p class="text-muted">{{ hostId }}</p>
      </div>
      <div class="flex gap-1 align-center">
        <button @click="fetchAll" class="btn btn-outline btn-sm" :disabled="loading">
          {{ loading ? 'Loading...' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div v-if="loading && !clusterStatus" class="loading-spinner"></div>

    <template v-else>
      <!-- ── Resource Summary Totals ─────────────────────────────────────── -->
      <div class="summary-totals mb-2">
        <div
          class="summary-card summary-card--link"
          role="link"
          tabindex="0"
          title="View node monitor"
          @click="$router.push('/node-monitor')"
          @keydown.enter="$router.push('/node-monitor')"
          @keydown.space.prevent="$router.push('/node-monitor')"
        >
          <div class="summary-card__value">{{ totalCpuCores }}</div>
          <div class="summary-card__label">Total CPU Cores</div>
        </div>
        <div
          class="summary-card summary-card--link"
          role="link"
          tabindex="0"
          title="View node monitor"
          @click="$router.push('/node-monitor')"
          @keydown.enter="$router.push('/node-monitor')"
          @keydown.space.prevent="$router.push('/node-monitor')"
        >
          <div class="summary-card__value">{{ totalRamGB }} GB</div>
          <div class="summary-card__label">Total RAM</div>
        </div>
        <div
          class="summary-card summary-card--link"
          role="link"
          tabindex="0"
          title="View all virtual machines"
          @click="$router.push('/vms')"
          @keydown.enter="$router.push('/vms')"
          @keydown.space.prevent="$router.push('/vms')"
        >
          <div class="summary-card__value">{{ totalVMs }}</div>
          <div class="summary-card__label">Total VMs</div>
        </div>
        <div
          class="summary-card summary-card--link"
          role="link"
          tabindex="0"
          title="View all containers"
          @click="$router.push('/containers')"
          @keydown.enter="$router.push('/containers')"
          @keydown.space.prevent="$router.push('/containers')"
        >
          <div class="summary-card__value">{{ totalLXC }}</div>
          <div class="summary-card__label">Total LXC</div>
        </div>
        <div
          class="summary-card summary-card--link"
          role="link"
          tabindex="0"
          title="View node monitor"
          @click="$router.push('/node-monitor')"
          @keydown.enter="$router.push('/node-monitor')"
          @keydown.space.prevent="$router.push('/node-monitor')"
        >
          <div class="summary-card__value">{{ clusterNodes.length }}</div>
          <div class="summary-card__label">Nodes</div>
        </div>
        <div
          class="summary-card summary-card--link"
          role="link"
          tabindex="0"
          title="View cluster status"
          @click="$router.push('/cluster')"
          @keydown.enter="$router.push('/cluster')"
          @keydown.space.prevent="$router.push('/cluster')"
        >
          <div class="summary-card__value">
            <span :class="clusterQuorate ? 'badge badge-success' : 'badge badge-danger'">
              {{ clusterQuorate ? 'Quorate' : 'No Quorum' }}
            </span>
          </div>
          <div class="summary-card__label">Quorum</div>
        </div>
      </div>

      <!-- ── Node Cards Grid ────────────────────────────────────────────── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Nodes</h3>
          <div class="flex gap-1 align-center">
            <span class="text-sm text-muted">Sort by:</span>
            <select v-model="nodeSort" class="form-control form-control-sm" style="width:auto">
              <option value="name">Name</option>
              <option value="cpu">CPU Usage</option>
              <option value="ram">RAM Usage</option>
            </select>
          </div>
        </div>

        <div v-if="sortedClusterNodes.length === 0" class="text-center text-muted" style="padding: 2rem;">
          <p>No nodes found in this cluster.</p>
        </div>

        <div v-else class="node-cards-grid">
          <div
            v-for="node in sortedClusterNodes"
            :key="node.name || node.id"
            class="node-card"
            :class="{ 'node-card--offline': !node.online }">

            <!-- Card header -->
            <div class="node-card__header">
              <div class="flex align-center gap-1">
                <span class="status-dot" :class="node.online ? 'status-dot--online' : 'status-dot--offline'"></span>
                <router-link
                  :to="`/proxmox/${hostId}/nodes/${node.name}`"
                  class="node-card__name">
                  {{ node.name }}
                </router-link>
                <span v-if="node.local" class="badge badge-info badge-xs">Master</span>
              </div>
              <span :class="['badge', node.online ? 'badge-success' : 'badge-danger']">
                {{ node.online ? 'Online' : 'Offline' }}
              </span>
            </div>

            <!-- Live stats (from nodeStats cache) -->
            <template v-if="getNodeStat(node.name)">
              <!-- CPU bar -->
              <div class="res-row">
                <span class="res-label">CPU</span>
                <div class="res-bar-wrap">
                  <div class="res-bar">
                    <div
                      class="res-bar-fill"
                      :class="pctClass(nodeCpuPct(node.name))"
                      :style="{ width: nodeCpuPct(node.name) + '%' }">
                    </div>
                  </div>
                  <span class="res-pct">{{ nodeCpuPct(node.name) }}%</span>
                </div>
              </div>

              <!-- RAM bar -->
              <div class="res-row">
                <span class="res-label">RAM</span>
                <div class="res-bar-wrap">
                  <div class="res-bar">
                    <div
                      class="res-bar-fill"
                      :class="pctClass(nodeRamPct(node.name))"
                      :style="{ width: nodeRamPct(node.name) + '%' }">
                    </div>
                  </div>
                  <span class="res-pct">{{ nodeRamPct(node.name) }}%</span>
                </div>
              </div>

              <!-- Disk bar -->
              <div class="res-row">
                <span class="res-label">Disk</span>
                <div class="res-bar-wrap">
                  <div class="res-bar">
                    <div
                      class="res-bar-fill"
                      :class="pctClass(nodeDiskPct(node.name))"
                      :style="{ width: nodeDiskPct(node.name) + '%' }">
                    </div>
                  </div>
                  <span class="res-pct">{{ nodeDiskPct(node.name) }}%</span>
                </div>
              </div>

              <!-- Counts + uptime -->
              <div class="node-card__meta">
                <span class="meta-item">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/></svg>
                  {{ getNodeStat(node.name).vmCount }} VMs
                </span>
                <span class="meta-item">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
                  {{ getNodeStat(node.name).lxcCount }} LXC
                </span>
                <span class="meta-item text-muted">
                  Up {{ formatUptime(getNodeStat(node.name).uptime) }}
                </span>
              </div>
            </template>

            <!-- Loading / offline placeholder -->
            <div v-else-if="loadingNodeStats" class="node-card__loading text-muted text-xs">
              Loading stats...
            </div>
            <div v-else class="node-card__loading text-muted text-xs">
              {{ node.online ? 'Stats unavailable' : 'Node offline' }}
            </div>

            <!-- Link to node detail -->
            <router-link
              :to="`/proxmox/${hostId}/nodes/${node.name}`"
              class="node-card__detail-link">
              Open Node
            </router-link>
          </div>
        </div>
      </div>

      <!-- ── Cluster-wide Running Tasks ─────────────────────────────────── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Running Cluster Tasks</h3>
          <button @click="fetchClusterTasks" class="btn btn-outline btn-sm" :disabled="loadingTasks">
            {{ loadingTasks ? 'Loading...' : 'Refresh' }}
          </button>
        </div>

        <div v-if="loadingTasks" class="loading-spinner"></div>
        <div v-else-if="runningTasks.length === 0" class="text-center text-muted" style="padding: 1.5rem;">
          No running tasks at this time.
        </div>
        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Node</th>
                <th>Type</th>
                <th>ID</th>
                <th>User</th>
                <th>Started</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in runningTasks" :key="task.upid">
                <td class="text-sm">{{ task.node || '—' }}</td>
                <td class="text-sm">{{ task.type }}</td>
                <td class="text-sm text-muted">{{ task.id || '—' }}</td>
                <td class="text-sm">{{ task.user || '—' }}</td>
                <td class="text-sm">{{ task.starttime ? new Date(task.starttime * 1000).toLocaleString() : '—' }}</td>
                <td>
                  <button
                    @click="stopTask(task)"
                    class="btn btn-danger btn-sm"
                    :disabled="stoppingTask[task.upid]">
                    {{ stoppingTask[task.upid] ? '...' : 'Stop' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── Cluster Status ─────────────────────────────────────────────── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Cluster Status</h3>
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

      <!-- ── Migration Settings ─────────────────────────────────────────── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Migration Settings</h3>
        </div>
        <div class="card-body" v-if="clusterOptions">
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Migration Type</span>
              <span class="info-value">{{ clusterOptions.migration?.type || (clusterOptions['migration-unsecure'] === 1 ? 'insecure' : 'secure') }}</span>
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

      <!-- ── HA Manager Status ──────────────────────────────────────────── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>HA Manager Status</h3>
        </div>
        <div class="card-body" v-if="haStatus">
          <div class="status-grid">
            <div class="status-item">
              <span class="status-label">Manager Status</span>
              <span :class="['badge', haStatus.master_node ? 'badge-success' : 'badge-warning']">
                {{ haStatus.master_node ? 'Active' : 'No Master' }}
              </span>
            </div>
            <div class="status-item">
              <span class="status-label">Quorum</span>
              <span :class="['badge', haQuorumOk ? 'badge-success' : 'badge-danger']">
                {{ haQuorumOk ? 'OK' : 'Degraded' }}
              </span>
            </div>
            <div class="status-item">
              <span class="status-label">Master Node</span>
              <span class="status-value">{{ haStatus.master_node || '—' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">Nodes Online</span>
              <span class="status-value">{{ haNodesOnline }} / {{ haNodesTotal }}</span>
            </div>
          </div>
        </div>
        <div v-else class="card-body text-muted text-center">
          <p>HA status not available or HA not configured.</p>
        </div>
      </div>

      <!-- ── Add Node / Cluster Join Instructions ───────────────────────── -->
      <div class="card">
        <div class="card-header">
          <h3>Add a Node to This Cluster</h3>
          <button @click="showJoinInfo = !showJoinInfo" class="btn btn-outline btn-sm">
            {{ showJoinInfo ? 'Hide' : 'Show' }} Instructions
          </button>
        </div>
        <transition name="slide-fade">
          <div v-if="showJoinInfo" class="card-body join-info">
            <p class="text-sm text-muted mb-1">
              To join an additional Proxmox node to this cluster, follow these steps on the <strong>new node</strong>:
            </p>

            <ol class="join-steps">
              <li>
                <strong>Prerequisites:</strong> The new node must be a fresh Proxmox VE install (no existing VMs/containers).
                Both nodes must be able to reach each other over the network.
              </li>
              <li>
                <strong>On the new node,</strong> open the Proxmox web UI at
                <code>https://&lt;new-node-ip&gt;:8006</code>,
                go to <em>Datacenter → Cluster → Join Cluster</em>, and paste the join information below.
              </li>
              <li>
                <strong>Get join information</strong> from this cluster's master node:
                <div v-if="joinInfo" class="join-token-block">
                  <pre class="join-token">{{ joinInfo }}</pre>
                  <button @click="copyJoinInfo" class="btn btn-outline btn-sm mt-1">Copy Join Info</button>
                </div>
                <div v-else class="flex gap-1 align-center mt-1">
                  <button @click="loadJoinInfo" class="btn btn-primary btn-sm" :disabled="loadingJoinInfo">
                    {{ loadingJoinInfo ? 'Loading...' : 'Fetch Join Info' }}
                  </button>
                  <span class="text-xs text-muted">Retrieves the cluster join token from the Proxmox API</span>
                </div>
              </li>
              <li>
                <strong>Alternatively,</strong> use the CLI on the master node:
                <pre class="join-cmd">pvecm add &lt;master-node-ip&gt;</pre>
              </li>
              <li>
                After joining, run <code>pvecm status</code> on any node to verify the new node has joined successfully.
              </li>
            </ol>

            <div class="info-note text-sm">
              <strong>Note:</strong> Proxmox clusters require all nodes to have synchronized time (NTP).
              Ensure <code>chrony</code> or <code>ntp</code> is running on all nodes before joining.
            </div>
          </div>
        </transition>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

function formatUptime(seconds) {
  if (!seconds) return '—'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

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

    // Node live stats keyed by node name
    const nodeStats = ref({})
    const loadingNodeStats = ref(false)

    // Cluster tasks
    const allTasksRaw = ref([])
    const loadingTasks = ref(false)
    const stoppingTask = ref({})

    // Node sort
    const nodeSort = ref('name')

    // Join info panel
    const showJoinInfo = ref(false)
    const joinInfo = ref(null)
    const loadingJoinInfo = ref(false)

    // ── HA status derived computed ─────────────────────────────────────────
    const haNodesTotal = computed(() => Object.keys(haStatus.value?.node_status || {}).length)
    const haNodesOnline = computed(() => Object.values(haStatus.value?.node_status || {}).filter(s => s === 'online').length)
    const haQuorumOk = computed(() => haNodesTotal.value > 0 && haNodesOnline.value === haNodesTotal.value)

    // ── Computed cluster-level data ────────────────────────────────────────
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

    // ── Node stat helpers ──────────────────────────────────────────────────
    const getNodeStat = (nodeName) => nodeStats.value[nodeName] || null

    const nodeCpuPct = (nodeName) => {
      const s = getNodeStat(nodeName)
      if (!s || s.cpu == null) return 0
      return Math.round(s.cpu * 100)
    }

    const nodeRamPct = (nodeName) => {
      const s = getNodeStat(nodeName)
      if (!s || !s.memory?.total) return 0
      return Math.round((s.memory.used / s.memory.total) * 100)
    }

    const nodeDiskPct = (nodeName) => {
      const s = getNodeStat(nodeName)
      if (!s || !s.rootfs?.total) return 0
      return Math.round((s.rootfs.used / s.rootfs.total) * 100)
    }

    const pctClass = (pct) => {
      if (pct >= 85) return 'fill-danger'
      if (pct >= 65) return 'fill-warning'
      return 'fill-ok'
    }

    // ── Summary totals ─────────────────────────────────────────────────────
    const totalCpuCores = computed(() => {
      let total = 0
      for (const stat of Object.values(nodeStats.value)) {
        if (stat.cpuCores) total += stat.cpuCores
      }
      return total || '—'
    })

    const totalRamGB = computed(() => {
      let total = 0
      for (const stat of Object.values(nodeStats.value)) {
        if (stat.memory?.total) total += stat.memory.total
      }
      if (!total) return '—'
      return Math.round(total / 1073741824)
    })

    const totalVMs = computed(() => {
      let total = 0
      for (const stat of Object.values(nodeStats.value)) {
        total += stat.vmCount || 0
      }
      return total
    })

    const totalLXC = computed(() => {
      let total = 0
      for (const stat of Object.values(nodeStats.value)) {
        total += stat.lxcCount || 0
      }
      return total
    })

    // ── Sorted node list ───────────────────────────────────────────────────
    const sortedClusterNodes = computed(() => {
      const nodes = [...clusterNodes.value]
      if (nodeSort.value === 'cpu') {
        nodes.sort((a, b) => nodeCpuPct(b.name) - nodeCpuPct(a.name))
      } else if (nodeSort.value === 'ram') {
        nodes.sort((a, b) => nodeRamPct(b.name) - nodeRamPct(a.name))
      } else {
        nodes.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
      }
      return nodes
    })

    // ── Running tasks (tasks with no endtime) ─────────────────────────────
    const runningTasks = computed(() => {
      return allTasksRaw.value.filter(t => !t.endtime)
    })

    // ── Fetch cluster status, options, HA ─────────────────────────────────
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

      // After fetching cluster status, load live node stats
      await fetchNodeStats()
      // Also load tasks
      await fetchClusterTasks()
    }

    // ── Fetch live node stats ──────────────────────────────────────────────
    const fetchNodeStats = async () => {
      const nodes = clusterNodes.value
      if (nodes.length === 0) return

      loadingNodeStats.value = true
      const tasks = nodes.map(async (node) => {
        if (!node.online || !node.name) return
        try {
          const [statusRes, vmsRes, lxcRes] = await Promise.allSettled([
            api.pveNode.nodeStatus(hostId.value, node.name),
            api.pveNode.nodeVms(hostId.value, node.name),
            api.pveNode.containers(hostId.value, node.name),
          ])
          const status = statusRes.status === 'fulfilled' ? statusRes.value.data : null
          const vms = vmsRes.status === 'fulfilled' ? (vmsRes.value.data || []) : []
          const lxcs = lxcRes.status === 'fulfilled' ? (lxcRes.value.data || []) : []
          nodeStats.value = {
            ...nodeStats.value,
            [node.name]: {
              cpu: status?.cpu ?? null,
              memory: status?.memory ?? null,
              rootfs: status?.rootfs ?? null,
              uptime: status?.uptime ?? null,
              cpuCores: status?.cpuinfo?.cpus ?? null,
              vmCount: Array.isArray(vms) ? vms.filter(v => (v.type === 'qemu' || !v.type) && !v.template).length : 0,
              lxcCount: Array.isArray(lxcs) ? lxcs.length : 0,
            }
          }
        } catch {
          // ignore per-node failures
        }
      })
      await Promise.allSettled(tasks)
      loadingNodeStats.value = false
    }

    // ── Fetch cluster-wide tasks ───────────────────────────────────────────
    const fetchClusterTasks = async () => {
      loadingTasks.value = true
      try {
        // Gather tasks from all online nodes
        const nodes = clusterNodes.value.filter(n => n.online && n.name)
        const collected = []
        await Promise.allSettled(nodes.map(async (node) => {
          try {
            const res = await api.pveNode.listTasks(hostId.value, node.name, { limit: 50 })
            const tasks = res.data || []
            tasks.forEach(t => collected.push({ ...t, node: node.name }))
          } catch { /* ignore per-node failures */ }
        }))
        // Sort by starttime desc
        collected.sort((a, b) => (b.starttime || 0) - (a.starttime || 0))
        allTasksRaw.value = collected
      } catch (err) {
        console.error('Failed to fetch cluster tasks:', err)
      } finally {
        loadingTasks.value = false
      }
    }

    // ── Stop a task ────────────────────────────────────────────────────────
    const stopTask = async (task) => {
      stoppingTask.value = { ...stoppingTask.value, [task.upid]: true }
      try {
        await api.pveNode.stopTask(hostId.value, task.node, task.upid)
        toast.success('Task stop requested')
        setTimeout(fetchClusterTasks, 1500)
      } catch (err) {
        toast.error('Failed to stop task: ' + (err?.response?.data?.detail || err.message))
      } finally {
        stoppingTask.value = { ...stoppingTask.value, [task.upid]: false }
      }
    }

    // ── Cluster join info ──────────────────────────────────────────────────
    const loadJoinInfo = async () => {
      loadingJoinInfo.value = true
      try {
        const res = await api.cluster.getJoinInfo(hostId.value)
        joinInfo.value = JSON.stringify(res.data, null, 2)
      } catch (err) {
        toast.error('Failed to fetch join info: ' + (err?.response?.data?.detail || err.message))
      } finally {
        loadingJoinInfo.value = false
      }
    }

    const copyJoinInfo = () => {
      if (!joinInfo.value) return
      navigator.clipboard.writeText(joinInfo.value).then(() => {
        toast.success('Join info copied to clipboard')
      }).catch(() => {
        toast.error('Failed to copy — try manually selecting the text')
      })
    }

    onMounted(() => {
      fetchAll()
    })

    return {
      hostId,
      loading,
      clusterStatus,
      clusterOptions,
      haStatus, haQuorumOk, haNodesOnline, haNodesTotal,
      clusterNodes,
      clusterName,
      clusterQuorate,
      clusterVersion,
      nodeStats,
      loadingNodeStats,
      nodeSort,
      sortedClusterNodes,
      getNodeStat,
      nodeCpuPct,
      nodeRamPct,
      nodeDiskPct,
      pctClass,
      totalCpuCores,
      totalRamGB,
      totalVMs,
      totalLXC,
      runningTasks,
      loadingTasks,
      stoppingTask,
      showJoinInfo,
      joinInfo,
      loadingJoinInfo,
      fetchAll,
      fetchClusterTasks,
      stopTask,
      loadJoinInfo,
      copyJoinInfo,
      formatUptime,
    }
  }
}
</script>

<style scoped>
/* ── Layout ────────────────────────────────────────────────────────────── */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.6rem;
  font-weight: 600;
  color: var(--text-primary);
}
.mb-2 { margin-bottom: 1rem; }
.mt-1 { margin-top: 0.5rem; }

/* ── Breadcrumb ────────────────────────────────────────────────────────── */
.breadcrumb-nav {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}
.breadcrumb-crumb {
  color: var(--text-secondary);
  text-decoration: none;
  transition: color 0.15s;
}
.breadcrumb-crumb:hover {
  color: var(--text-primary);
  text-decoration: underline;
}
.breadcrumb-crumb--current {
  color: var(--text-primary);
  font-weight: 500;
  cursor: default;
}
.breadcrumb-crumb--current:hover { text-decoration: none; }
.breadcrumb-sep {
  color: var(--text-muted);
  user-select: none;
}

/* ── Summary totals strip ──────────────────────────────────────────────── */
.summary-totals {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 0.75rem;
}
.summary-card {
  background: var(--card-bg, var(--background-alt));
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.9rem 1rem;
  text-align: center;
}
.summary-card__value {
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}
.summary-card__label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  margin-top: 0.3rem;
}
.summary-card--link {
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.summary-card--link:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 14px rgba(0,0,0,0.18);
  border-color: var(--accent, #6366f1);
}
.summary-card--link:focus-visible {
  outline: 2px solid var(--accent, #6366f1);
  outline-offset: 2px;
}

/* ── Node cards grid ───────────────────────────────────────────────────── */
.node-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
  padding: 1rem;
}
.node-card {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.875rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  transition: box-shadow 0.15s;
}
.node-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}
.node-card--offline {
  opacity: 0.65;
}
.node-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.node-card__name {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--text-primary);
  text-decoration: none;
}
.node-card__name:hover {
  text-decoration: underline;
}

/* Status dot */
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot--online { background: #22c55e; }
.status-dot--offline { background: #ef4444; }

/* Resource bars */
.res-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.res-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  width: 30px;
  flex-shrink: 0;
}
.res-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: 1;
}
.res-bar {
  flex: 1;
  height: 5px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}
.res-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}
.fill-ok { background: #22c55e; }
.fill-warning { background: #f59e0b; }
.fill-danger { background: #ef4444; }
.res-pct {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 30px;
  text-align: right;
}

/* Meta row */
.node-card__meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 0.2rem;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
}

.node-card__loading {
  font-size: 0.75rem;
  padding: 0.25rem 0;
}

.node-card__detail-link {
  display: inline-block;
  margin-top: 0.35rem;
  font-size: 0.75rem;
  color: var(--primary, #3b82f6);
  text-decoration: none;
  font-weight: 500;
  align-self: flex-start;
}
.node-card__detail-link:hover {
  text-decoration: underline;
}

/* Badge xs */
.badge-xs {
  font-size: 0.6rem;
  padding: 0.15em 0.45em;
}

/* ── Cluster status / info grids ───────────────────────────────────────── */
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

/* ── Join info section ─────────────────────────────────────────────────── */
.join-info {
  max-width: 720px;
}
.join-steps {
  padding-left: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  margin: 0.75rem 0;
  font-size: 0.875rem;
  color: var(--text-primary);
  line-height: 1.6;
}
.join-steps li {
  padding-left: 0.25rem;
}
.join-token-block {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.join-token {
  background: var(--code-bg, #1e1e2e);
  color: var(--code-text, #cdd6f4);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.75rem 1rem;
  font-size: 0.75rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
}
.join-cmd {
  background: var(--code-bg, #1e1e2e);
  color: var(--code-text, #cdd6f4);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  margin-top: 0.4rem;
  display: inline-block;
}
.info-note {
  background: rgba(59, 130, 246, 0.07);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 0.375rem;
  padding: 0.6rem 0.9rem;
  margin-top: 0.75rem;
  color: var(--text-primary);
}

/* ── Slide-fade transition ─────────────────────────────────────────────── */
.slide-fade-enter-active {
  transition: all 0.2s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.15s ease-in;
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* Utility */
.mb-1 { margin-bottom: 0.5rem; }
</style>
