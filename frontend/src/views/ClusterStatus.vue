<template>
  <div class="cluster-status-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header-row">
        <div>
          <h2>Cluster Status</h2>
          <p class="text-muted">Cluster nodes, tasks, replication, and join/create management</p>
        </div>
        <div class="header-actions">
          <button @click="refreshAll" class="btn btn-outline" :disabled="anyLoading">
            {{ anyLoading ? 'Loading...' : 'Refresh' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Host Selector -->
    <div class="card host-selector-card">
      <div class="host-selector-row">
        <label class="form-label">Proxmox Host</label>
        <select
          v-model="selectedHostId"
          class="form-control host-select"
          :disabled="loadingHosts"
          @change="onHostChange"
        >
          <option value="" disabled>{{ loadingHosts ? 'Loading hosts...' : 'Select a host...' }}</option>
          <option v-for="host in hosts" :key="host.id" :value="host.id">
            {{ host.name }} — {{ host.address }}
          </option>
        </select>
      </div>
    </div>

    <!-- No host selected -->
    <div v-if="!selectedHostId" class="card empty-placeholder">
      <p class="text-muted">Select a Proxmox host above to view cluster information.</p>
    </div>

    <template v-else>
      <!-- Tabs -->
      <div class="tab-bar">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['tab-btn', activeTab === tab.key ? 'tab-active' : '']"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span v-if="tab.count !== undefined && tab.count > 0" class="tab-count">{{ tab.count }}</span>
        </button>
      </div>

      <!-- ─── Cluster Tab ─────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'cluster'" class="tab-content">

        <!-- Cluster Info Card -->
        <div class="card mb-2">
          <div class="card-header">
            <h3>Cluster Information</h3>
            <button @click="loadClusterStatus" class="btn btn-outline btn-sm" :disabled="loadingCluster">
              {{ loadingCluster ? 'Loading...' : 'Refresh' }}
            </button>
          </div>

          <div v-if="loadingCluster" class="loading-state">Loading cluster status...</div>
          <div v-else-if="clusterError" class="error-banner">{{ clusterError }}</div>

          <div v-else-if="clusterStatus" class="info-grid">
            <div class="info-item">
              <span class="info-label">Cluster Name</span>
              <span class="info-value">{{ clusterStatus.cluster?.name || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Quorum</span>
              <span :class="['badge', clusterStatus.quorate ? 'badge-success' : 'badge-danger']">
                {{ clusterStatus.quorate ? 'OK' : 'No Quorum' }}
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">Total Nodes</span>
              <span class="info-value">{{ clusterStatus.node_count }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Nodes Online</span>
              <span class="info-value">{{ onlineNodes.length }} / {{ clusterStatus.node_count }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Config Version</span>
              <span class="info-value">{{ clusterStatus.cluster?.version || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Transport</span>
              <span class="info-value">{{ clusterStatus.cluster?.transport || 'udpu' }}</span>
            </div>
          </div>
          <div v-else class="empty-state">
            <p class="text-muted">No cluster status available — this host may not be part of a cluster.</p>
          </div>
        </div>

        <!-- Nodes Table -->
        <div class="card mb-2">
          <div class="card-header">
            <h3>Nodes</h3>
          </div>

          <div v-if="loadingCluster" class="loading-state">Loading nodes...</div>

          <div v-else-if="clusterStatus?.nodes?.length === 0" class="empty-state">
            <p class="text-muted">No node information available.</p>
          </div>

          <div v-else-if="clusterStatus?.nodes" class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Type</th>
                  <th>Votes</th>
                  <th>Level</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="node in clusterStatus.nodes" :key="node.id || node.name">
                  <td>
                    <div class="node-name-cell">
                      <span :class="['node-dot', node.online ? 'dot-online' : 'dot-offline']"></span>
                      <strong>{{ node.name }}</strong>
                      <span v-if="node.local" class="badge badge-sm badge-info ml-1">local</span>
                    </div>
                  </td>
                  <td class="text-sm text-muted">{{ node.nodeid || node.id || '—' }}</td>
                  <td>
                    <span :class="['badge', node.online ? 'badge-success' : 'badge-danger']">
                      {{ node.online ? 'online' : 'offline' }}
                    </span>
                  </td>
                  <td class="text-sm">{{ node.type || 'node' }}</td>
                  <td class="text-sm">{{ node.votes ?? '—' }}</td>
                  <td class="text-sm">{{ node.level || '—' }}</td>
                  <td class="text-sm text-muted">{{ node.ip || node.addr || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Quorum Visualizer -->
        <div v-if="clusterStatus?.nodes?.length" class="card">
          <div class="card-header">
            <h3>Quorum Visualizer</h3>
          </div>
          <p class="text-sm text-muted mb-1">
            Quorum requires {{ Math.ceil((clusterStatus.node_count + 1) / 2) }} of
            {{ clusterStatus.node_count }} votes. Currently
            <strong>{{ onlineNodes.reduce((s, n) => s + (n.votes || 1), 0) }}</strong> votes online.
          </p>
          <div class="quorum-chips">
            <div
              v-for="node in clusterStatus.nodes"
              :key="node.name"
              :class="['quorum-chip', node.online ? 'quorum-chip-online' : 'quorum-chip-offline']"
            >
              <span :class="['quorum-chip-dot', node.online ? 'dot-online' : 'dot-offline']"></span>
              <div class="quorum-chip-info">
                <span class="quorum-chip-name">{{ node.name }}</span>
                <span class="quorum-chip-votes">{{ node.votes ?? 1 }} vote{{ (node.votes ?? 1) !== 1 ? 's' : '' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Tasks Tab ──────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'tasks'" class="tab-content">
        <div class="card">
          <div class="card-header">
            <h3>Cluster Tasks</h3>
            <div class="header-actions-row">
              <span v-if="tasksPolling" class="text-sm text-muted">Auto-refresh in {{ tasksCountdown }}s</span>
              <button @click="loadTasks" class="btn btn-outline btn-sm" :disabled="loadingTasks">
                {{ loadingTasks ? 'Loading...' : 'Refresh' }}
              </button>
            </div>
          </div>

          <!-- Filters -->
          <div class="filter-row">
            <select v-model="tasksTypeFilter" class="form-control form-control-sm">
              <option value="">All Types</option>
              <option value="qmstart">qmstart</option>
              <option value="qmstop">qmstop</option>
              <option value="qmmigrate">qmmigrate</option>
              <option value="vzmigrate">vzmigrate</option>
              <option value="vzdump">vzdump</option>
              <option value="qmclone">qmclone</option>
              <option value="qmcreate">qmcreate</option>
              <option value="qmdestroy">qmdestroy</option>
            </select>
            <select v-model="tasksLimit" class="form-control form-control-sm">
              <option :value="50">50 tasks</option>
              <option :value="100">100 tasks</option>
              <option :value="200">200 tasks</option>
            </select>
          </div>

          <div v-if="loadingTasks" class="loading-state">Loading cluster tasks...</div>
          <div v-else-if="tasksError" class="error-banner">{{ tasksError }}</div>
          <div v-else-if="tasks.length === 0" class="empty-state">
            <p class="text-muted">No tasks found.</p>
          </div>

          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Type</th>
                  <th>ID/VMID</th>
                  <th>Status</th>
                  <th>Started</th>
                  <th>Duration</th>
                  <th>User</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="task in tasks" :key="task.upid">
                  <td class="text-sm">{{ task._node || task.node || '—' }}</td>
                  <td>
                    <code class="code-badge">{{ task.type || '—' }}</code>
                  </td>
                  <td class="text-sm text-muted">{{ task.id || task.vmid || '—' }}</td>
                  <td>
                    <span :class="['badge', taskStatusClass(task.status)]">
                      {{ task.status || 'running' }}
                    </span>
                  </td>
                  <td class="text-sm">{{ formatDate(task.starttime) }}</td>
                  <td class="text-sm text-muted">{{ taskDuration(task) }}</td>
                  <td class="text-sm text-muted">{{ task.user || '—' }}</td>
                  <td>
                    <button
                      v-if="!task.status || task.status === 'running'"
                      class="btn btn-danger btn-sm"
                      :disabled="stoppingTask === task.upid"
                      @click="stopTask(task)"
                    >
                      {{ stoppingTask === task.upid ? '...' : 'Stop' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Replication Tab ────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'replication'" class="tab-content">
        <div class="card">
          <div class="card-header">
            <h3>Replication Jobs</h3>
            <div class="header-actions-row">
              <button @click="openCreateReplModal" class="btn btn-primary">+ Create Job</button>
              <button @click="loadReplication" class="btn btn-outline btn-sm" :disabled="loadingRepl">Refresh</button>
            </div>
          </div>

          <div v-if="loadingRepl" class="loading-state">Loading replication jobs...</div>
          <div v-else-if="replError" class="error-banner">{{ replError }}</div>
          <div v-else-if="replJobs.length === 0" class="empty-state">
            <p class="text-muted">No replication jobs configured on this host.</p>
            <p class="text-sm text-muted">Replication requires a Proxmox cluster with at least 2 nodes.</p>
          </div>

          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Source VM</th>
                  <th>Target</th>
                  <th>Schedule</th>
                  <th>Rate Limit</th>
                  <th>Last Sync</th>
                  <th>Next Sync</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="job in replJobs" :key="job.id">
                  <td><code class="code-badge">{{ job.id }}</code></td>
                  <td class="text-sm">
                    <span class="vm-sid-chip">{{ job.guest || job.source || job.vmid || '—' }}</span>
                  </td>
                  <td class="text-sm">
                    <span class="node-chip">{{ job.target }}</span>
                  </td>
                  <td class="text-sm text-muted">{{ job.schedule || '*/15' }}</td>
                  <td class="text-sm text-muted">{{ job.rate ? job.rate + ' MB/s' : '—' }}</td>
                  <td class="text-sm">{{ job.last_sync ? formatDate(job.last_sync) : '—' }}</td>
                  <td class="text-sm">{{ job.next_sync ? formatDate(job.next_sync) : '—' }}</td>
                  <td>
                    <span :class="['badge', replStatusClass(job)]">
                      {{ job.error ? 'error' : (job.fail_count ? 'warning' : 'ok') }}
                    </span>
                    <span v-if="job.fail_count" class="text-sm text-muted ml-1">
                      ({{ job.fail_count }} fail{{ job.fail_count !== 1 ? 's' : '' }})
                    </span>
                  </td>
                  <td>
                    <div class="action-row">
                      <button
                        class="btn btn-secondary btn-sm"
                        :disabled="syncingJob === job.id"
                        @click="forceSync(job)"
                        title="Force sync now"
                      >
                        {{ syncingJob === job.id ? '...' : 'Sync Now' }}
                      </button>
                      <button
                        class="btn btn-danger btn-sm"
                        :disabled="deletingJob === job.id"
                        @click="deleteReplJob(job)"
                      >
                        {{ deletingJob === job.id ? '...' : 'Delete' }}
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Join/Create Tab ───────────────────────────────────────────────── -->
      <div v-if="activeTab === 'join'" class="tab-content">
        <!-- Warning Banner -->
        <div class="warning-banner mb-2">
          <strong>Warning:</strong> Joining or creating a cluster will restart the
          <code>pve-cluster</code> service on this node (~30s downtime on this node).
          Ensure all VMs are migrated or stopped before proceeding.
        </div>

        <!-- Current cluster status -->
        <div v-if="clusterStatus?.cluster" class="card mb-2">
          <div class="card-header">
            <h3>Current Cluster Membership</h3>
          </div>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Cluster Name</span>
              <span class="info-value">{{ clusterStatus.cluster.name }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Node Count</span>
              <span class="info-value">{{ clusterStatus.node_count }}</span>
            </div>
          </div>
          <p class="text-sm text-muted mt-1">
            This host is already a member of a cluster. To join a different cluster, it must first be removed from the current one via the Proxmox CLI.
          </p>
        </div>

        <!-- Join Info (fingerprint + addresses for other nodes to join this cluster) -->
        <div v-if="clusterStatus?.cluster" class="card mb-2">
          <div class="card-header">
            <h3>Join Information</h3>
            <button @click="loadJoinInfo" class="btn btn-outline btn-sm" :disabled="loadingJoinInfo">
              {{ loadingJoinInfo ? 'Loading...' : 'Load' }}
            </button>
          </div>
          <div v-if="loadingJoinInfo" class="loading-state">Loading join info...</div>
          <div v-else-if="joinInfo">
            <div class="join-info-grid">
              <div class="form-group">
                <label class="form-label">Fingerprint</label>
                <div class="copy-field">
                  <code class="join-info-val">{{ joinInfo.fingerprint || '—' }}</code>
                  <button class="btn btn-outline btn-sm" @click="copyToClipboard(joinInfo.fingerprint)">Copy</button>
                </div>
              </div>
              <div v-for="(link, idx) in (joinInfo.links || [])" :key="idx" class="form-group">
                <label class="form-label">Link {{ idx }} Address</label>
                <code class="join-info-val">{{ link.address || link }}</code>
              </div>
            </div>
          </div>
          <p v-else class="text-sm text-muted p-1">Click Load to fetch join information for this cluster.</p>
        </div>

        <!-- Create Cluster (only when not in a cluster) -->
        <div v-if="!clusterStatus?.cluster" class="card mb-2">
          <div class="card-header">
            <h3>Create New Cluster</h3>
          </div>
          <form @submit.prevent="createCluster" class="form-body">
            <div class="form-group">
              <label class="form-label">Cluster Name <span class="required">*</span></label>
              <input
                v-model="createForm.clustername"
                class="form-control"
                placeholder="e.g. my-cluster"
                pattern="[a-zA-Z0-9\-_]+"
                title="Alphanumeric, dashes and underscores only"
                required
              />
              <p class="field-hint">Name must be unique across your network and consist of letters, numbers, dashes, or underscores.</p>
            </div>
            <div class="modal-actions">
              <button type="submit" class="btn btn-primary" :disabled="creatingCluster">
                {{ creatingCluster ? 'Creating...' : 'Create Cluster' }}
              </button>
            </div>
          </form>
        </div>

        <!-- Join Cluster (only when not in a cluster) -->
        <div v-if="!clusterStatus?.cluster" class="card">
          <div class="card-header">
            <h3>Join Existing Cluster</h3>
          </div>
          <form @submit.prevent="joinCluster" class="form-body">
            <div class="form-group">
              <label class="form-label">Master Node Hostname / IP <span class="required">*</span></label>
              <input
                v-model="joinForm.hostname"
                class="form-control"
                placeholder="192.168.1.10 or pve1.example.com"
                required
              />
              <p class="field-hint">IP or hostname of an existing cluster member node.</p>
            </div>

            <div class="form-group">
              <label class="form-label">Root Password <span class="required">*</span></label>
              <input
                v-model="joinForm.password"
                type="password"
                class="form-control"
                placeholder="root password of the master node"
                required
              />
            </div>

            <div class="form-group">
              <label class="form-label">Fingerprint</label>
              <input
                v-model="joinForm.fingerprint"
                class="form-control"
                placeholder="Auto-detected if left empty"
              />
              <p class="field-hint">TLS fingerprint from the master cluster's join info page.</p>
            </div>

            <div class="form-group">
              <label class="form-label">Ring 0 Address (Link 0)</label>
              <input
                v-model="joinForm.link0"
                class="form-control"
                placeholder="Local IP to use for corosync link 0"
              />
              <p class="field-hint">Leave empty to use the default interface IP.</p>
            </div>

            <div class="modal-actions">
              <button type="submit" class="btn btn-primary" :disabled="joiningCluster">
                {{ joiningCluster ? 'Joining...' : 'Join Cluster' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </template>

    <!-- ─── Create Replication Job Modal ───────────────────────────────────── -->
    <div v-if="showReplModal" class="modal" @click.self="showReplModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Create Replication Job</h3>
          <button @click="showReplModal = false" class="btn-close">&times;</button>
        </div>
        <form @submit.prevent="createReplJob" class="modal-body">
          <div class="form-group">
            <label class="form-label">Job ID <span class="required">*</span></label>
            <input
              v-model="newRepl.id"
              class="form-control"
              placeholder="e.g. 100-0 (vmid-jobnum)"
              required
            />
            <p class="field-hint">Format: <code>&lt;vmid&gt;-&lt;jobnum&gt;</code> e.g. <code>100-0</code></p>
          </div>

          <div class="form-group">
            <label class="form-label">Type</label>
            <select v-model="newRepl.type" class="form-control">
              <option value="local">local</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Source VM ID <span class="required">*</span></label>
            <input
              v-model.number="newRepl.guest"
              class="form-control"
              type="number"
              placeholder="e.g. 100"
              min="100"
              required
            />
          </div>

          <div class="form-group">
            <label class="form-label">Target Node <span class="required">*</span></label>
            <select v-model="newRepl.target" class="form-control" required>
              <option value="">— Select target node —</option>
              <option v-for="node in (clusterStatus?.nodes || [])" :key="node.name" :value="node.name">
                {{ node.name }}
              </option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Schedule</label>
              <input
                v-model="newRepl.schedule"
                class="form-control"
                placeholder="*/15"
              />
              <p class="field-hint">Cron-like schedule. <code>*/15</code> = every 15 min</p>
            </div>
            <div class="form-group">
              <label class="form-label">Rate Limit (MB/s)</label>
              <input
                v-model.number="newRepl.rate"
                class="form-control"
                type="number"
                placeholder="Unlimited"
                min="1"
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="newRepl.comment" class="form-control" placeholder="Optional description" />
          </div>

          <div class="modal-actions">
            <button type="submit" class="btn btn-primary" :disabled="savingRepl">
              {{ savingRepl ? 'Creating...' : 'Create Job' }}
            </button>
            <button type="button" @click="showReplModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const toast = useToast()

// ── Hosts ─────────────────────────────────────────────────────────────────────
const hosts = ref([])
const loadingHosts = ref(false)
const selectedHostId = ref('')

const loadHosts = async () => {
  loadingHosts.value = true
  try {
    const response = await api.proxmox.listHosts({ params: { page_size: 100 } })
    hosts.value = response.data?.items ?? response.data ?? []
    if (hosts.value.length === 1 && !selectedHostId.value) {
      selectedHostId.value = hosts.value[0].id
      refreshAll()
    }
  } catch (err) {
    console.error('Failed to load hosts:', err)
    toast.error('Failed to load Proxmox hosts')
  } finally {
    loadingHosts.value = false
  }
}

const onHostChange = () => {
  stopTasksPoller()
  refreshAll()
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
const activeTab = ref('cluster')
const tabs = computed(() => [
  { key: 'cluster', label: 'Cluster' },
  { key: 'tasks',   label: 'Tasks', count: tasks.value.filter(t => !t.status || t.status === 'running').length || undefined },
  { key: 'replication', label: 'Replication', count: replJobs.value.length || undefined },
  { key: 'join',    label: 'Join / Create' },
])

const anyLoading = computed(() =>
  loadingCluster.value || loadingTasks.value || loadingRepl.value
)

// ── Cluster Status ─────────────────────────────────────────────────────────────
const clusterStatus = ref(null)
const loadingCluster = ref(false)
const clusterError = ref(null)

const onlineNodes = computed(() =>
  (clusterStatus.value?.nodes || []).filter(n => n.online)
)

const loadClusterStatus = async () => {
  if (!selectedHostId.value) return
  loadingCluster.value = true
  clusterError.value = null
  try {
    const res = await api.cluster.getClusterStatus(selectedHostId.value)
    clusterStatus.value = res.data
  } catch (err) {
    clusterError.value = err.response?.data?.detail || 'Failed to load cluster status'
  } finally {
    loadingCluster.value = false
  }
}

// ── Tasks ──────────────────────────────────────────────────────────────────────
const tasks = ref([])
const loadingTasks = ref(false)
const tasksError = ref(null)
const tasksTypeFilter = ref('')
const tasksLimit = ref(100)
const stoppingTask = ref(null)

// Polling
let tasksPollerTimer = null
const tasksPolling = ref(false)
const tasksCountdown = ref(15)

const startTasksPoller = () => {
  stopTasksPoller()
  if (!selectedHostId.value) return
  tasksPolling.value = true
  tasksCountdown.value = 15
  const tick = setInterval(() => {
    tasksCountdown.value--
    if (tasksCountdown.value <= 0) {
      loadTasks()
      tasksCountdown.value = 15
    }
  }, 1000)
  tasksPollerTimer = tick
}

const stopTasksPoller = () => {
  tasksPolling.value = false
  if (tasksPollerTimer) { clearInterval(tasksPollerTimer); tasksPollerTimer = null }
}

const loadTasks = async () => {
  if (!selectedHostId.value) return
  loadingTasks.value = true
  tasksError.value = null
  try {
    const params = { limit: tasksLimit.value }
    if (tasksTypeFilter.value) params.typefilter = tasksTypeFilter.value
    const res = await api.cluster.listTasks(selectedHostId.value, params)
    tasks.value = Array.isArray(res.data) ? res.data : []
  } catch (err) {
    tasksError.value = err.response?.data?.detail || 'Failed to load tasks'
  } finally {
    loadingTasks.value = false
  }
}

const stopTask = async (task) => {
  if (!confirm(`Stop task ${task.type} (UPID: ${task.upid})?`)) return
  stoppingTask.value = task.upid
  try {
    const node = task._node || task.node
    await api.pveNode.stopTask(selectedHostId.value, node, encodeURIComponent(task.upid))
    toast.success('Task stop requested')
    await loadTasks()
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to stop task')
  } finally {
    stoppingTask.value = null
  }
}

watch([tasksTypeFilter, tasksLimit], () => {
  if (selectedHostId.value && activeTab.value === 'tasks') loadTasks()
})

// ── Replication ────────────────────────────────────────────────────────────────
const replJobs = ref([])
const loadingRepl = ref(false)
const replError = ref(null)
const syncingJob = ref(null)
const deletingJob = ref(null)

const loadReplication = async () => {
  if (!selectedHostId.value) return
  loadingRepl.value = true
  replError.value = null
  try {
    const res = await api.cluster.listReplication(selectedHostId.value)
    replJobs.value = Array.isArray(res.data) ? res.data : []
  } catch (err) {
    replError.value = err.response?.data?.detail || 'Failed to load replication jobs'
  } finally {
    loadingRepl.value = false
  }
}

const forceSync = async (job) => {
  syncingJob.value = job.id
  try {
    await api.cluster.forceReplication(selectedHostId.value, job.id)
    toast.success(`Replication sync started for job ${job.id}`)
    setTimeout(() => loadReplication(), 2000)
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to trigger sync')
  } finally {
    syncingJob.value = null
  }
}

const deleteReplJob = async (job) => {
  if (!confirm(`Delete replication job "${job.id}"?\n\nThis will stop replication for VM ${job.guest || job.vmid}.`)) return
  deletingJob.value = job.id
  try {
    await api.cluster.deleteReplication(selectedHostId.value, job.id)
    toast.success(`Replication job ${job.id} deleted`)
    await loadReplication()
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to delete replication job')
  } finally {
    deletingJob.value = null
  }
}

// Replication modal
const showReplModal = ref(false)
const savingRepl = ref(false)
const newRepl = ref({ id: '', type: 'local', guest: null, target: '', schedule: '*/15', rate: null, comment: '' })

const openCreateReplModal = () => {
  newRepl.value = { id: '', type: 'local', guest: null, target: '', schedule: '*/15', rate: null, comment: '' }
  showReplModal.value = true
}

const createReplJob = async () => {
  savingRepl.value = true
  try {
    const payload = { ...newRepl.value }
    Object.keys(payload).forEach(k => {
      if (payload[k] === '' || payload[k] === null || payload[k] === undefined) delete payload[k]
    })
    await api.cluster.createReplication(selectedHostId.value, payload)
    toast.success('Replication job created')
    showReplModal.value = false
    await loadReplication()
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to create replication job')
  } finally {
    savingRepl.value = false
  }
}

// ── Join / Create Cluster ─────────────────────────────────────────────────────
const joinInfo = ref(null)
const loadingJoinInfo = ref(false)

const loadJoinInfo = async () => {
  if (!selectedHostId.value) return
  loadingJoinInfo.value = true
  try {
    const res = await api.cluster.getJoinInfo(selectedHostId.value)
    joinInfo.value = res.data
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to load join info')
  } finally {
    loadingJoinInfo.value = false
  }
}

const createForm = ref({ clustername: '' })
const creatingCluster = ref(false)

const createCluster = async () => {
  if (!confirm(`Create cluster "${createForm.value.clustername}"? This will restart pve-cluster service.`)) return
  creatingCluster.value = true
  try {
    await api.cluster.createCluster(selectedHostId.value, { clustername: createForm.value.clustername })
    toast.success(`Cluster "${createForm.value.clustername}" created successfully`)
    createForm.value.clustername = ''
    await loadClusterStatus()
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to create cluster')
  } finally {
    creatingCluster.value = false
  }
}

const joinForm = ref({ hostname: '', password: '', fingerprint: '', link0: '' })
const joiningCluster = ref(false)

const joinCluster = async () => {
  if (!confirm(`Join cluster at ${joinForm.value.hostname}? This will restart pve-cluster service.`)) return
  joiningCluster.value = true
  try {
    const payload = { hostname: joinForm.value.hostname, password: joinForm.value.password }
    if (joinForm.value.fingerprint) payload.fingerprint = joinForm.value.fingerprint
    if (joinForm.value.link0) payload.link0 = joinForm.value.link0
    await api.cluster.joinCluster(selectedHostId.value, payload)
    toast.success('Successfully joined cluster')
    joinForm.value = { hostname: '', password: '', fingerprint: '', link0: '' }
    await loadClusterStatus()
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to join cluster')
  } finally {
    joiningCluster.value = false
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
const taskStatusClass = (status) => {
  if (!status || status === 'running') return 'badge-info'
  if (status === 'OK') return 'badge-success'
  if (status?.startsWith('WARN')) return 'badge-warning'
  return 'badge-danger'
}

const replStatusClass = (job) => {
  if (job.error) return 'badge-danger'
  if (job.fail_count) return 'badge-warning'
  return 'badge-success'
}

const formatDate = (val) => {
  if (!val) return '—'
  const d = typeof val === 'number' ? new Date(val * 1000) : new Date(val)
  return d.toLocaleString()
}

const taskDuration = (task) => {
  const start = task.starttime
  const end = task.endtime
  if (!start) return '—'
  const endTs = end || Math.floor(Date.now() / 1000)
  const diffSec = endTs - start
  if (diffSec < 60) return `${diffSec}s`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ${diffSec % 60}s`
  return `${Math.floor(diffSec / 3600)}h ${Math.floor((diffSec % 3600) / 60)}m`
}

const copyToClipboard = async (text) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  } catch {
    toast.error('Failed to copy')
  }
}

// ── Refresh All ────────────────────────────────────────────────────────────────
const refreshAll = () => {
  if (!selectedHostId.value) return
  loadClusterStatus()
  loadTasks()
  loadReplication()
  if (activeTab.value === 'tasks') startTasksPoller()
}

// Watch tab changes to start/stop poller
watch(activeTab, (tab) => {
  if (tab === 'tasks' && selectedHostId.value) {
    startTasksPoller()
  } else {
    stopTasksPoller()
  }
})

watch(selectedHostId, (val) => {
  if (val) refreshAll()
})

onMounted(() => {
  loadHosts()
})

onUnmounted(() => {
  stopTasksPoller()
})
</script>

<style scoped>
.cluster-status-page {
  padding-bottom: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* ── Page Header ── */
.page-header {
  margin-bottom: 0.25rem;
}

.page-header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.page-header h2 {
  margin: 0 0 0.35rem 0;
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

.header-actions-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* ── Host Selector ── */
.host-selector-card { padding: 1rem 1.5rem !important; }
.host-selector-row { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.host-selector-row .form-label { margin: 0; white-space: nowrap; font-weight: 600; font-size: 0.875rem; color: var(--text-secondary); flex-shrink: 0; }
.host-select { min-width: 280px; max-width: 420px; }

/* ── Tabs ── */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-color, #2d3348);
}

.tab-btn {
  padding: 0.625rem 1.25rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted, #6b7280);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: color 0.15s, border-color 0.15s;
  margin-bottom: -1px;
}

.tab-btn:hover { color: var(--text-primary); }
.tab-active { color: #3b82f6 !important; border-bottom-color: #3b82f6 !important; }

.tab-count {
  background: var(--bg-secondary, #2d3348);
  color: var(--text-muted, #9ca3af);
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 9999px;
  font-weight: 600;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* ── Cards ── */
.card {
  background: var(--bg-card, #1e2130);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.5rem;
  padding: 1.5rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}

.card-header h3 {
  font-size: 1.0rem;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

/* ── Info Grid ── */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  padding: 0.875rem 1rem;
  background: var(--bg-secondary, #151824);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
}

.info-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #6b7280);
}

.info-value {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── Node dot indicators ── */
.node-name-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.node-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-online  { background: #10b981; }
.dot-offline { background: #ef4444; }

/* ── Quorum Visualizer ── */
.quorum-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.quorum-chip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1rem;
  border-radius: 0.5rem;
  border: 1px solid;
  min-width: 140px;
}

.quorum-chip-online {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
}

.quorum-chip-offline {
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.2);
  opacity: 0.6;
}

.quorum-chip-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.quorum-chip-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.quorum-chip-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.quorum-chip-votes {
  font-size: 0.75rem;
  color: var(--text-muted, #6b7280);
}

/* ── Filter row ── */
.filter-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.form-control-sm {
  padding: 0.3rem 0.5rem;
  font-size: 0.825rem;
}

/* ── Table ── */
.table-container { overflow-x: auto; }

.table {
  width: 100%;
  border-collapse: collapse;
}

.table thead tr {
  border-bottom: 1px solid var(--border-color, #2d3348);
}

.table th {
  padding: 0.625rem 0.875rem;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #6b7280);
}

.table td {
  padding: 0.75rem 0.875rem;
  border-bottom: 1px solid var(--border-color, #2d3348);
  font-size: 0.9rem;
  color: var(--text-primary);
  vertical-align: middle;
}

.table tbody tr:last-child td { border-bottom: none; }
.table tbody tr:hover { background: var(--bg-hover, rgba(255, 255, 255, 0.03)); }

/* ── Node/VM chips ── */
.node-chip {
  display: inline-flex;
  align-items: center;
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 0.25rem;
  padding: 0.15rem 0.45rem;
  font-size: 0.78rem;
  font-weight: 500;
}

.vm-sid-chip {
  display: inline-flex;
  align-items: center;
  background: rgba(139, 92, 246, 0.12);
  color: #a78bfa;
  border: 1px solid rgba(139, 92, 246, 0.25);
  border-radius: 0.25rem;
  padding: 0.15rem 0.45rem;
  font-size: 0.78rem;
  font-weight: 500;
}

.code-badge {
  font-family: monospace;
  font-size: 0.8rem;
  background: var(--bg-secondary, #2d3348);
  padding: 0.1rem 0.35rem;
  border-radius: 0.2rem;
  color: var(--text-secondary);
}

/* ── Join Info ── */
.join-info-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.copy-field {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.join-info-val {
  font-family: monospace;
  font-size: 0.825rem;
  color: var(--text-secondary);
  word-break: break-all;
  background: var(--bg-secondary, #151824);
  padding: 0.35rem 0.5rem;
  border-radius: 0.25rem;
  flex: 1;
}

/* ── Form body ── */
.form-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* ── Warning Banner ── */
.warning-banner {
  padding: 0.875rem 1rem;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  color: #fbbf24;
}

.warning-banner code {
  background: rgba(245, 158, 11, 0.2);
  padding: 0.1rem 0.3rem;
  border-radius: 0.2rem;
  font-family: monospace;
}

/* ── Error/Empty/Loading states ── */
.error-banner { padding: 0.875rem 1rem; background: rgba(220, 38, 38, 0.12); border: 1px solid rgba(220, 38, 38, 0.3); border-radius: 0.375rem; color: #f87171; font-size: 0.9rem; }
.loading-state { text-align: center; padding: 2.5rem; color: var(--text-muted, #6b7280); font-size: 0.9rem; }
.empty-state { text-align: center; padding: 2.5rem 1.5rem; color: var(--text-muted, #6b7280); }
.empty-state p { margin: 0.375rem 0; }
.empty-placeholder { text-align: center; padding: 3rem 1.5rem; }

/* ── Action row ── */
.action-row { display: flex; gap: 0.375rem; }

/* ── Badges ── */
.badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
.badge-sm { padding: 0.1rem 0.4rem; font-size: 0.7rem; }
.badge-success  { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.badge-danger   { background: rgba(239, 68, 68, 0.15);  color: #f87171; }
.badge-warning  { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.badge-info     { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.badge-secondary { background: rgba(107, 114, 128, 0.2); color: #9ca3af; }

/* ── Buttons ── */
.btn { padding: 0.5rem 1rem; border-radius: 0.375rem; border: none; font-weight: 500; font-size: 0.875rem; cursor: pointer; display: inline-flex; align-items: center; gap: 0.375rem; transition: all 0.15s; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-secondary { background: var(--bg-secondary, #2d3348); color: var(--text-primary); border: 1px solid var(--border-color, #3d4568); }
.btn-secondary:hover:not(:disabled) { background: var(--bg-hover, #363c55); }
.btn-danger { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.btn-danger:hover:not(:disabled) { background: rgba(239, 68, 68, 0.25); }
.btn-outline { background: transparent; color: var(--text-secondary); border: 1px solid var(--border-color, #3d4568); }
.btn-outline:hover:not(:disabled) { background: var(--bg-hover, rgba(255, 255, 255, 0.05)); }
.btn-sm { padding: 0.25rem 0.625rem; font-size: 0.8rem; }
.btn-close { background: none; border: none; font-size: 1.5rem; line-height: 1; cursor: pointer; color: var(--text-muted, #6b7280); padding: 0 0.25rem; transition: color 0.15s; }
.btn-close:hover { color: var(--text-primary); }

/* ── Forms ── */
.form-group { display: flex; flex-direction: column; gap: 0.375rem; }
.form-label { font-size: 0.875rem; font-weight: 500; color: var(--text-secondary); }
.required { color: #f87171; }
.form-control { background: var(--bg-input, #151824); border: 1px solid var(--border-color, #2d3348); border-radius: 0.375rem; color: var(--text-primary); padding: 0.5rem 0.75rem; font-size: 0.9rem; outline: none; transition: border-color 0.15s; }
.form-control:focus { border-color: #3b82f6; }
.form-control option { background: var(--bg-card, #1e2130); }
.field-hint { font-size: 0.78rem; color: var(--text-muted, #6b7280); margin: 0; }
.field-hint code { background: var(--bg-secondary, #2d3348); padding: 0.1rem 0.3rem; border-radius: 0.2rem; font-family: monospace; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }

/* ── Modal ── */
.modal { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.6); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: var(--bg-card, #1e2130); border: 1px solid var(--border-color, #2d3348); border-radius: 0.5rem; width: 90%; max-width: 560px; max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5); }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--border-color, #2d3348); }
.modal-header h3 { margin: 0; font-size: 1.1rem; font-weight: 600; color: var(--text-primary); }
.modal-body { padding: 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
.modal-actions { display: flex; gap: 0.75rem; padding-top: 0.5rem; }

/* ── Utilities ── */
.text-muted { color: var(--text-muted, #6b7280); }
.text-sm { font-size: 0.875rem; }
.text-secondary { color: var(--text-secondary); }
.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }
.mt-1 { margin-top: 0.5rem; }
.ml-1 { margin-left: 0.25rem; }
.p-1 { padding: 0.75rem; }

@media (max-width: 640px) {
  .cluster-status-page { gap: 1rem; }
  .host-selector-row { flex-direction: column; align-items: flex-start; }
  .host-select { min-width: 100%; max-width: 100%; }
  .page-header-row { flex-direction: column; }
  .form-row { grid-template-columns: 1fr; }
  .quorum-chips { flex-direction: column; }
  .info-grid { grid-template-columns: 1fr 1fr; }
}
</style>
