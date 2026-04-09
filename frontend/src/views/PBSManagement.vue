<template>
  <div class="pbs-page">
    <div class="page-header mb-2">
      <div class="page-header-left">
        <h2>PBS Management</h2>
        <p class="text-muted">Manage Proxmox Backup Servers, datastores, and backup jobs</p>
      </div>
      <div class="page-header-actions">
        <span v-if="lastRefreshed" class="text-muted text-xs">
          Refreshed {{ lastRefreshedAgo }}
        </span>
        <button @click="refreshAll" class="btn btn-outline btn-sm" :disabled="loading">
          {{ loading ? 'Refreshing...' : '⟳ Refresh' }}
        </button>
        <button @click="openAddServerModal" class="btn btn-primary btn-sm">
          + Add PBS Server
        </button>
      </div>
    </div>

    <!-- Error banner -->
    <div v-if="globalError" class="error-banner mb-2">{{ globalError }}</div>

    <!-- No servers state -->
    <div v-if="!loading && servers.length === 0" class="empty-state card">
      <div class="empty-state-icon">🗄️</div>
      <h3>No PBS Servers Configured</h3>
      <p class="text-muted">Add a Proxmox Backup Server to start managing backups, datastores, and jobs.</p>
      <button @click="openAddServerModal" class="btn btn-primary mt-2">Add PBS Server</button>
    </div>

    <!-- Server cards (overview) -->
    <div v-if="servers.length > 0" class="server-grid mb-3">
      <div
        v-for="srv in servers"
        :key="srv.id"
        :class="['server-card', selectedServerId === srv.id ? 'server-card--active' : '']"
        @click="selectServer(srv)"
      >
        <div class="server-card-header">
          <div class="server-card-title">
            <span class="server-icon">🗄️</span>
            <div>
              <strong>{{ srv.name }}</strong>
              <div class="text-xs text-muted">{{ srv.hostname }}:{{ srv.port || 8007 }}</div>
            </div>
          </div>
          <div class="flex gap-1 align-center">
            <span :class="['status-dot', getServerStatus(srv)]"></span>
            <button
              @click.stop="confirmDeleteServer(srv)"
              class="btn btn-danger btn-xs"
              title="Remove server"
            >Remove</button>
          </div>
        </div>
        <div class="server-card-stats" v-if="serverStats[srv.id]">
          <div class="stat-pill">
            <span class="stat-label">Datastores</span>
            <span class="stat-value">{{ (serverStats[srv.id].datastores || []).length }}</span>
          </div>
          <div class="stat-pill">
            <span class="stat-label">Jobs</span>
            <span class="stat-value">{{ (serverStats[srv.id].jobs || []).length }}</span>
          </div>
          <div class="stat-pill">
            <span class="stat-label">Failed</span>
            <span :class="['stat-value', failedJobCount(srv.id) > 0 ? 'text-danger' : 'text-success']">
              {{ failedJobCount(srv.id) }}
            </span>
          </div>
        </div>
        <div v-else-if="loadingServerStats[srv.id]" class="text-xs text-muted mt-1">Loading stats...</div>
        <div v-else class="text-xs text-muted mt-1">Click to load details</div>
      </div>
    </div>

    <!-- Detail panel for selected server -->
    <template v-if="selectedServerId && servers.length > 0">
      <!-- Tabs -->
      <div class="tab-bar mb-2">
        <button
          :class="['tab-btn', activeTab === 'overview' ? 'tab-btn--active' : '']"
          @click="activeTab = 'overview'"
        >Overview</button>
        <button
          :class="['tab-btn', activeTab === 'datastores' ? 'tab-btn--active' : '']"
          @click="activeTab = 'datastores'; fetchDatastores()"
        >Datastores</button>
        <button
          :class="['tab-btn', activeTab === 'jobs' ? 'tab-btn--active' : '']"
          @click="activeTab = 'jobs'; fetchJobs()"
        >Backup Jobs</button>
        <button
          :class="['tab-btn', activeTab === 'tapes' ? 'tab-btn--active' : '']"
          @click="activeTab = 'tapes'; fetchTapes()"
        >Tapes</button>
        <button
          :class="['tab-btn', activeTab === 'tasks' ? 'tab-btn--active' : '']"
          @click="activeTab = 'tasks'; fetchRecentTasks()"
        >Recent Tasks</button>
      </div>

      <!-- ── Overview Tab ── -->
      <div v-if="activeTab === 'overview'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>Server Overview — {{ selectedServer.name }}</h3>
            <button @click="fetchServerOverview(selectedServerId)" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="loadingOverview" class="loading-spinner"></div>
          <div v-else-if="overviewData" class="overview-grid">
            <div class="overview-item">
              <span class="overview-label">Version</span>
              <span class="overview-value">{{ overviewData.version || '—' }}</span>
            </div>
            <div class="overview-item">
              <span class="overview-label">Hostname</span>
              <span class="overview-value">{{ overviewData.hostname || selectedServer.hostname }}</span>
            </div>
            <div class="overview-item">
              <span class="overview-label">Fingerprint</span>
              <span class="overview-value text-mono text-xs">{{ overviewData.fingerprint || '—' }}</span>
            </div>
            <div class="overview-item">
              <span class="overview-label">CPU Usage</span>
              <span class="overview-value">
                <span v-if="overviewData.cpu != null">{{ (overviewData.cpu * 100).toFixed(1) }}%</span>
                <span v-else>—</span>
              </span>
            </div>
            <div class="overview-item">
              <span class="overview-label">Memory</span>
              <span class="overview-value">
                <span v-if="overviewData.memory">
                  {{ formatBytes(overviewData.memory.used) }} / {{ formatBytes(overviewData.memory.total) }}
                </span>
                <span v-else>—</span>
              </span>
            </div>
            <div class="overview-item">
              <span class="overview-label">Uptime</span>
              <span class="overview-value">{{ formatUptime(overviewData.uptime) }}</span>
            </div>
          </div>
          <div v-else class="text-muted p-2 text-sm">Could not load server info.</div>
        </div>

        <!-- Recent backup job status cards -->
        <div class="card">
          <div class="card-header">
            <h3>Backup Job Status</h3>
          </div>
          <div v-if="loadingJobs" class="loading-spinner"></div>
          <div v-else-if="jobs.length === 0" class="text-muted p-2 text-sm">No backup jobs found.</div>
          <div v-else class="job-cards-grid">
            <div
              v-for="job in jobs"
              :key="job.id || job['job-id']"
              :class="['job-card', `job-card--${jobStatusClass(job)}`]"
            >
              <div class="job-card-header">
                <span class="job-icon">{{ jobStatusIcon(job) }}</span>
                <div class="job-card-info">
                  <strong class="text-sm">{{ job.id || job['job-id'] || 'Unknown' }}</strong>
                  <div class="text-xs text-muted">Store: {{ job.store || job.datastore || '—' }}</div>
                </div>
                <span :class="['job-status-badge', `job-status-badge--${jobStatusClass(job)}`]">
                  {{ jobStatusLabel(job) }}
                </span>
              </div>
              <div class="job-card-meta">
                <div class="text-xs text-muted">
                  Schedule: <code class="cron-text">{{ job.schedule || '—' }}</code>
                </div>
                <div class="text-xs text-muted">
                  Last run: {{ job['last-run-upid'] ? formatRelativeTime(job['last-run-endtime']) : 'Never' }}
                </div>
                <div class="text-xs text-muted" v-if="job['next-run']">
                  Next: {{ formatDate(job['next-run']) }}
                </div>
              </div>
              <div class="job-card-actions">
                <button
                  @click="triggerJob(job)"
                  class="btn btn-outline btn-xs"
                  :disabled="triggeringJob === (job.id || job['job-id'])"
                  title="Run this backup job now"
                >
                  {{ triggeringJob === (job.id || job['job-id']) ? 'Starting...' : '▶ Run Now' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Datastores Tab ── -->
      <div v-if="activeTab === 'datastores'">
        <div class="card">
          <div class="card-header">
            <h3>Datastores</h3>
            <button @click="fetchDatastores" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="loadingDatastores" class="loading-spinner"></div>
          <div v-else-if="datastores.length === 0" class="text-muted p-2 text-sm">No datastores found.</div>
          <div v-else class="ds-grid">
            <div v-for="ds in datastores" :key="ds.store || ds.name" class="ds-card">
              <div class="ds-card-header">
                <span class="ds-icon">💾</span>
                <div>
                  <strong>{{ ds.store || ds.name }}</strong>
                  <div v-if="ds.path" class="text-xs text-muted">{{ ds.path }}</div>
                </div>
              </div>
              <!-- Disk usage bar -->
              <div v-if="ds.used != null && ds.avail != null" class="ds-usage">
                <div class="ds-usage-bar-wrap">
                  <div
                    class="ds-usage-bar"
                    :style="{ width: dsUsagePercent(ds) + '%' }"
                    :class="dsUsageClass(ds)"
                  ></div>
                </div>
                <div class="ds-usage-labels">
                  <span class="text-xs">{{ formatBytes(ds.used) }} used</span>
                  <span class="text-xs text-muted">{{ formatBytes(ds.avail) }} free</span>
                </div>
              </div>
              <div class="ds-card-meta">
                <div class="text-xs text-muted" v-if="ds.total">Total: {{ formatBytes(ds.total) }}</div>
                <div class="text-xs text-muted" v-if="ds['gc-status']">
                  GC: {{ ds['gc-status']['last-run-endtime'] ? formatRelativeTime(ds['gc-status']['last-run-endtime']) : 'never' }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Backup Jobs Tab ── -->
      <div v-if="activeTab === 'jobs'">
        <div class="card">
          <div class="card-header">
            <h3>Backup Jobs</h3>
            <button @click="fetchJobs" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="loadingJobs" class="loading-spinner"></div>
          <div v-else-if="jobs.length === 0" class="text-muted p-2 text-sm">No backup jobs configured on this server.</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Datastore</th>
                  <th>Schedule</th>
                  <th>Mode</th>
                  <th>Last Run</th>
                  <th>Status</th>
                  <th>Next Run</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="job in jobs" :key="job.id || job['job-id']">
                  <td><strong>{{ job.id || job['job-id'] || '—' }}</strong></td>
                  <td>{{ job.store || job.datastore || '—' }}</td>
                  <td><code class="cron-text">{{ job.schedule || '—' }}</code></td>
                  <td>{{ job.mode || '—' }}</td>
                  <td class="text-sm text-muted">
                    {{ job['last-run-endtime'] ? formatRelativeTime(job['last-run-endtime']) : 'Never' }}
                  </td>
                  <td>
                    <span :class="['job-status-badge', `job-status-badge--${jobStatusClass(job)}`]">
                      {{ jobStatusLabel(job) }}
                    </span>
                  </td>
                  <td class="text-sm text-muted">
                    {{ job['next-run'] ? formatDate(job['next-run']) : '—' }}
                  </td>
                  <td>
                    <button
                      @click="triggerJob(job)"
                      class="btn btn-outline btn-sm"
                      :disabled="triggeringJob === (job.id || job['job-id'])"
                      title="Run this job now"
                    >
                      {{ triggeringJob === (job.id || job['job-id']) ? 'Starting...' : 'Run Now' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ── Tapes Tab ── -->
      <div v-if="activeTab === 'tapes'">
        <div class="card">
          <div class="card-header">
            <h3>Tape Media</h3>
            <button @click="fetchTapes" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="loadingTapes" class="loading-spinner"></div>
          <div v-else-if="tapeError" class="text-muted p-2 text-sm">{{ tapeError }}</div>
          <div v-else-if="tapes.length === 0" class="text-muted p-2 text-sm">
            No tapes found. Tape support requires a tape drive configured on the PBS server.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Media Set</th>
                  <th>Pool</th>
                  <th>Location</th>
                  <th>Status</th>
                  <th>Bytes Written</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tape in tapes" :key="tape.label">
                  <td><strong>{{ tape.label }}</strong></td>
                  <td class="text-sm text-muted">{{ tape['media-set-uuid'] || '—' }}</td>
                  <td>{{ tape.pool || '—' }}</td>
                  <td>{{ tape.location || '—' }}</td>
                  <td>
                    <span :class="['job-status-badge', tape.status === 'ok' ? 'job-status-badge--ok' : 'job-status-badge--unknown']">
                      {{ tape.status || 'unknown' }}
                    </span>
                  </td>
                  <td class="text-sm">{{ tape['bytes-written'] != null ? formatBytes(tape['bytes-written']) : '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ── Recent Tasks Tab ── -->
      <div v-if="activeTab === 'tasks'">
        <div class="card">
          <div class="card-header">
            <h3>Recent Tasks</h3>
            <button @click="fetchRecentTasks" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="loadingTasks" class="loading-spinner"></div>
          <div v-else-if="recentTasks.length === 0" class="text-muted p-2 text-sm">No recent tasks.</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Worker ID</th>
                  <th>Node</th>
                  <th>Start Time</th>
                  <th>Duration</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="task in recentTasks" :key="task.upid">
                  <td><strong>{{ task.type || task.worker_type || '—' }}</strong></td>
                  <td class="text-xs text-muted" style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" :title="task['worker-id'] || task.worker_id">
                    {{ task['worker-id'] || task.worker_id || '—' }}
                  </td>
                  <td>{{ task.node || '—' }}</td>
                  <td class="text-sm text-muted">{{ task.starttime ? formatDate(task.starttime) : '—' }}</td>
                  <td class="text-sm">{{ taskDuration(task) }}</td>
                  <td>
                    <span :class="['job-status-badge', taskStatusClass(task)]">
                      {{ task.status || task.exitstatus || 'running' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- Add PBS Server Modal -->
    <div v-if="addServerModal.show" class="modal" @click.self="closeAddServerModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add PBS Server</h3>
          <button @click="closeAddServerModal" class="btn-close">&#215;</button>
        </div>
        <form @submit.prevent="submitAddServer" class="modal-body">
          <div class="form-group">
            <label class="form-label">Name <span class="required">*</span></label>
            <input v-model="addServerForm.name" class="form-control" placeholder="e.g. pbs-main" required />
            <div class="text-xs text-muted mt-1">A friendly display name for this server.</div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Hostname / IP <span class="required">*</span></label>
              <input v-model="addServerForm.hostname" class="form-control" placeholder="pbs.example.com" required />
            </div>
            <div class="form-group">
              <label class="form-label">Port</label>
              <input
                v-model.number="addServerForm.port"
                type="number"
                class="form-control"
                min="1"
                max="65535"
                placeholder="8007"
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="addServerForm.username" class="form-control" placeholder="root@pam" />
            <div class="text-xs text-muted mt-1">Used for display only (auth uses API token).</div>
          </div>

          <div class="form-group">
            <label class="form-label">API Token ID <span class="required">*</span></label>
            <input
              v-model="addServerForm.api_token_id"
              class="form-control"
              placeholder="root@pam!mytoken"
              required
            />
            <div class="text-xs text-muted mt-1">Format: user@realm!tokenname</div>
          </div>

          <div class="form-group">
            <label class="form-label">API Token Secret <span class="required">*</span></label>
            <input
              v-model="addServerForm.api_token_secret"
              type="password"
              class="form-control"
              placeholder="Token secret value"
              required
            />
          </div>

          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="addServerForm.verify_ssl" />
              <span>Verify SSL Certificate</span>
            </label>
            <div class="text-xs text-muted mt-1">Uncheck for self-signed certificates (typical for PBS).</div>
          </div>

          <div v-if="addServerModal.error" class="error-banner mt-1">{{ addServerModal.error }}</div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="addServerModal.saving">
              {{ addServerModal.saving ? 'Adding...' : 'Add Server' }}
            </button>
            <button type="button" @click="closeAddServerModal" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Job trigger result toast-like banner -->
    <div v-if="jobRunResult" class="job-run-result">
      <span>{{ jobRunResult }}</span>
      <button @click="jobRunResult = null" class="btn-close-sm">&#215;</button>
    </div>
  </div>
</template>

<script>
import { axiosInstance as api } from '@/services/api'

const REFRESH_INTERVAL_MS = 30000

export default {
  name: 'PBSManagement',

  data() {
    return {
      loading: false,
      globalError: null,
      servers: [],
      selectedServerId: null,
      serverStats: {},
      loadingServerStats: {},

      activeTab: 'overview',

      // Overview tab
      loadingOverview: false,
      overviewData: null,

      // Datastores tab
      loadingDatastores: false,
      datastores: [],

      // Jobs tab
      loadingJobs: false,
      jobs: [],
      triggeringJob: null,
      jobRunResult: null,

      // Tapes tab
      loadingTapes: false,
      tapes: [],
      tapeError: null,

      // Recent Tasks tab
      loadingTasks: false,
      recentTasks: [],

      // Add server modal
      addServerModal: { show: false, saving: false, error: null },
      addServerForm: {
        name: '',
        hostname: '',
        port: 8007,
        username: 'root@pam',
        api_token_id: '',
        api_token_secret: '',
        verify_ssl: false,
      },

      lastRefreshed: null,
      _refreshTimer: null,
    }
  },

  computed: {
    selectedServer() {
      return this.servers.find(s => s.id === this.selectedServerId) || null
    },
    lastRefreshedAgo() {
      if (!this.lastRefreshed) return ''
      const secs = Math.floor((Date.now() - this.lastRefreshed) / 1000)
      if (secs < 60) return `${secs}s ago`
      return `${Math.floor(secs / 60)}m ago`
    },
  },

  methods: {
    // ── Server list ──────────────────────────────────────────────────────
    async fetchServers() {
      this.loading = true
      this.globalError = null
      try {
        const res = await api.get('/pbs-mgmt/')
        this.servers = res.data || []
        if (this.servers.length > 0 && !this.selectedServerId) {
          this.selectServer(this.servers[0])
        }
        this.lastRefreshed = Date.now()
        // Load stats for all servers
        this.servers.forEach(srv => this.fetchServerStats(srv.id))
      } catch (e) {
        this.globalError = e?.response?.data?.detail || 'Failed to load PBS servers.'
      } finally {
        this.loading = false
      }
    },

    async fetchServerStats(serverId) {
      this.$set ? this.$set(this.loadingServerStats, serverId, true) : (this.loadingServerStats[serverId] = true)
      try {
        const [dsRes, jobRes] = await Promise.allSettled([
          api.get(`/pbs-mgmt/${serverId}/datastores`),
          api.get(`/pbs-mgmt/${serverId}/jobs`),
        ])
        const stats = {
          datastores: dsRes.status === 'fulfilled' ? (dsRes.value.data || []) : [],
          jobs: jobRes.status === 'fulfilled' ? (jobRes.value.data || []) : [],
        }
        this.serverStats = { ...this.serverStats, [serverId]: stats }
      } catch {
        // non-critical
      } finally {
        this.loadingServerStats = { ...this.loadingServerStats, [serverId]: false }
      }
    },

    selectServer(srv) {
      this.selectedServerId = srv.id
      this.activeTab = 'overview'
      this.overviewData = null
      this.datastores = []
      this.jobs = []
      this.tapes = []
      this.recentTasks = []
      this.fetchServerOverview(srv.id)
      this.fetchJobs()
    },

    getServerStatus(srv) {
      const stats = this.serverStats[srv.id]
      if (!stats) return 'status-dot--unknown'
      return 'status-dot--ok'
    },

    failedJobCount(serverId) {
      const stats = this.serverStats[serverId]
      if (!stats) return 0
      return (stats.jobs || []).filter(j => this.jobStatusClass(j) === 'failed').length
    },

    // ── Overview ─────────────────────────────────────────────────────────
    async fetchServerOverview(serverId) {
      this.loadingOverview = true
      this.overviewData = null
      try {
        const res = await api.get(`/pbs-mgmt/${serverId}/overview`)
        this.overviewData = res.data || null
      } catch {
        this.overviewData = null
      } finally {
        this.loadingOverview = false
      }
    },

    // ── Datastores ───────────────────────────────────────────────────────
    async fetchDatastores() {
      if (!this.selectedServerId) return
      this.loadingDatastores = true
      try {
        const res = await api.get(`/pbs-mgmt/${this.selectedServerId}/datastores`)
        this.datastores = res.data || []
      } catch {
        this.datastores = []
      } finally {
        this.loadingDatastores = false
      }
    },

    dsUsagePercent(ds) {
      const total = ds.total || (ds.used + ds.avail)
      if (!total) return 0
      return Math.min(100, Math.round((ds.used / total) * 100))
    },

    dsUsageClass(ds) {
      const pct = this.dsUsagePercent(ds)
      if (pct >= 90) return 'ds-usage-bar--danger'
      if (pct >= 75) return 'ds-usage-bar--warning'
      return 'ds-usage-bar--ok'
    },

    // ── Jobs ─────────────────────────────────────────────────────────────
    async fetchJobs() {
      if (!this.selectedServerId) return
      this.loadingJobs = true
      try {
        const res = await api.get(`/pbs-mgmt/${this.selectedServerId}/jobs`)
        this.jobs = res.data || []
      } catch {
        this.jobs = []
      } finally {
        this.loadingJobs = false
      }
    },

    async triggerJob(job) {
      const jobId = job.id || job['job-id']
      if (!jobId || !this.selectedServerId) return
      this.triggeringJob = jobId
      try {
        await api.post(`/pbs-mgmt/${this.selectedServerId}/jobs/${jobId}/run`)
        this.jobRunResult = `Job "${jobId}" started successfully.`
        setTimeout(() => { if (this.jobRunResult) this.jobRunResult = null }, 6000)
      } catch (e) {
        this.jobRunResult = `Failed to start job "${jobId}": ${e?.response?.data?.detail || e.message}`
      } finally {
        this.triggeringJob = null
      }
    },

    jobStatusClass(job) {
      const status = job['last-run-state'] || job.status || ''
      if (!status || status === 'unknown' || !job['last-run-upid']) return 'unknown'
      if (status === 'ok' || status === 'OK') return 'ok'
      if (status === 'warning') return 'warning'
      return 'failed'
    },

    jobStatusLabel(job) {
      if (!job['last-run-upid']) return 'Never run'
      const s = job['last-run-state'] || job.status || 'unknown'
      return s
    },

    jobStatusIcon(job) {
      const cls = this.jobStatusClass(job)
      if (cls === 'ok') return '✅'
      if (cls === 'warning') return '⚠️'
      if (cls === 'failed') return '❌'
      return '⬜'
    },

    // ── Tapes ────────────────────────────────────────────────────────────
    async fetchTapes() {
      if (!this.selectedServerId) return
      this.loadingTapes = true
      this.tapeError = null
      try {
        const res = await api.get(`/pbs-mgmt/${this.selectedServerId}/tapes`)
        this.tapes = res.data || []
      } catch (e) {
        const status = e?.response?.status
        if (status === 404 || status === 501) {
          this.tapeError = 'Tape management is not available on this PBS server.'
        } else {
          this.tapeError = e?.response?.data?.detail || 'Failed to load tape information.'
        }
        this.tapes = []
      } finally {
        this.loadingTapes = false
      }
    },

    // ── Recent Tasks ─────────────────────────────────────────────────────
    async fetchRecentTasks() {
      if (!this.selectedServerId) return
      this.loadingTasks = true
      try {
        const res = await api.get(`/pbs-mgmt/${this.selectedServerId}/tasks`)
        this.recentTasks = (res.data || []).slice(0, 50)
      } catch {
        this.recentTasks = []
      } finally {
        this.loadingTasks = false
      }
    },

    taskStatusClass(task) {
      const s = task.status || task.exitstatus || ''
      if (!s || s === 'running' || s === 'RUNNING') return 'job-status-badge--running'
      if (s === 'OK' || s === 'ok') return 'job-status-badge--ok'
      if (s.toLowerCase().includes('warn')) return 'job-status-badge--warning'
      return 'job-status-badge--failed'
    },

    taskDuration(task) {
      if (!task.starttime || !task.endtime) return '—'
      const secs = task.endtime - task.starttime
      if (secs < 60) return `${secs}s`
      if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
      return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
    },

    // ── Add server modal ─────────────────────────────────────────────────
    openAddServerModal() {
      this.addServerForm = {
        name: '',
        hostname: '',
        port: 8007,
        username: 'root@pam',
        api_token_id: '',
        api_token_secret: '',
        verify_ssl: false,
      }
      this.addServerModal = { show: true, saving: false, error: null }
    },

    closeAddServerModal() {
      this.addServerModal = { show: false, saving: false, error: null }
    },

    async submitAddServer() {
      this.addServerModal.saving = true
      this.addServerModal.error = null
      try {
        await api.post('/pbs/', this.addServerForm)
        this.closeAddServerModal()
        await this.fetchServers()
      } catch (e) {
        this.addServerModal.error = e?.response?.data?.detail || 'Failed to add PBS server.'
      } finally {
        this.addServerModal.saving = false
      }
    },

    async confirmDeleteServer(srv) {
      if (!confirm(`Remove PBS server "${srv.name}"? This will not affect any data on the PBS server.`)) return
      try {
        await api.delete(`/pbs/${srv.id}`)
        if (this.selectedServerId === srv.id) {
          this.selectedServerId = null
        }
        await this.fetchServers()
      } catch (e) {
        this.globalError = e?.response?.data?.detail || 'Failed to remove server.'
      }
    },

    // ── Utilities ────────────────────────────────────────────────────────
    async refreshAll() {
      await this.fetchServers()
      if (this.selectedServerId) {
        if (this.activeTab === 'overview') this.fetchServerOverview(this.selectedServerId)
        if (this.activeTab === 'datastores') this.fetchDatastores()
        if (this.activeTab === 'jobs') this.fetchJobs()
        if (this.activeTab === 'tasks') this.fetchRecentTasks()
      }
    },

    formatBytes(bytes) {
      if (bytes == null || bytes === 0) return '0 B'
      const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + ' ' + units[i]
    },

    formatDate(ts) {
      if (!ts) return '—'
      const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
      return d.toLocaleString()
    },

    formatRelativeTime(ts) {
      if (!ts) return '—'
      const ms = typeof ts === 'number' ? ts * 1000 : new Date(ts).getTime()
      const diff = Date.now() - ms
      const secs = Math.floor(diff / 1000)
      if (secs < 60) return 'just now'
      if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
      if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
      return `${Math.floor(secs / 86400)}d ago`
    },

    formatUptime(secs) {
      if (!secs) return '—'
      const d = Math.floor(secs / 86400)
      const h = Math.floor((secs % 86400) / 3600)
      const m = Math.floor((secs % 3600) / 60)
      if (d > 0) return `${d}d ${h}h ${m}m`
      if (h > 0) return `${h}h ${m}m`
      return `${m}m`
    },
  },

  mounted() {
    this.fetchServers()
    this._refreshTimer = setInterval(() => {
      this.fetchServers()
      if (this.selectedServerId) {
        if (this.activeTab === 'overview') {
          this.fetchServerOverview(this.selectedServerId)
          this.fetchJobs()
        } else if (this.activeTab === 'datastores') {
          this.fetchDatastores()
        } else if (this.activeTab === 'jobs') {
          this.fetchJobs()
        } else if (this.activeTab === 'tasks') {
          this.fetchRecentTasks()
        }
      }
    }, REFRESH_INTERVAL_MS)
  },

  beforeUnmount() {
    clearInterval(this._refreshTimer)
  },
}
</script>

<style scoped>
/* ── Page layout ── */
.pbs-page {
  padding: 1.5rem;
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
}

.page-header-left h2 {
  margin: 0 0 0.25rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: #e2e8f0;
}

.page-header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

/* ── Cards/shared ── */
.card {
  background: #1a2332;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 0.5rem;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.9rem 1.1rem;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  gap: 0.75rem;
  flex-wrap: wrap;
}

.card-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #e2e8f0;
}

/* ── Empty state ── */
.empty-state {
  text-align: center;
  padding: 3rem 2rem;
}

.empty-state-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.empty-state h3 {
  margin: 0 0 0.5rem;
  color: #e2e8f0;
}

/* ── Server grid ── */
.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.server-card {
  background: #1a2332;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 0.5rem;
  padding: 1rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.server-card:hover {
  background: #1e2d42;
  border-color: rgba(59,130,246,0.4);
}

.server-card--active {
  border-color: #3b82f6 !important;
  background: #1e2d42 !important;
}

.server-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.server-card-title {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
}

.server-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.server-card-stats {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.stat-pill {
  background: rgba(255,255,255,0.05);
  border-radius: 0.3rem;
  padding: 0.2rem 0.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}

.stat-label {
  font-size: 0.65rem;
  text-transform: uppercase;
  color: #7a8fa8;
  letter-spacing: 0.04em;
}

.stat-value {
  font-size: 1rem;
  font-weight: 600;
  color: #e2e8f0;
}

/* ── Status dot ── */
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-block;
}

.status-dot--ok { background: #22c55e; }
.status-dot--unknown { background: #6b7280; }
.status-dot--error { background: #ef4444; }

/* ── Tabs ── */
.tab-bar {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  flex-wrap: wrap;
}

.tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #8a9ab8;
  padding: 0.55rem 1rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
}

.tab-btn:hover { color: #c0cfe4; }

.tab-btn--active {
  color: #60a5fa;
  border-bottom-color: #3b82f6;
  font-weight: 500;
}

/* ── Overview grid ── */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0;
}

.overview-item {
  padding: 0.85rem 1.1rem;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  border-right: 1px solid rgba(255,255,255,0.04);
}

.overview-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #7a8fa8;
  display: block;
  margin-bottom: 0.25rem;
}

.overview-value {
  font-size: 0.9rem;
  color: #e2e8f0;
  font-weight: 500;
  word-break: break-all;
}

/* ── Job cards grid ── */
.job-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.75rem;
  padding: 1rem;
}

.job-card {
  background: #0f1419;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 0.4rem;
  padding: 0.8rem;
  border-left: 3px solid #6b7280;
}

.job-card--ok    { border-left-color: #22c55e; }
.job-card--warning { border-left-color: #f59e0b; }
.job-card--failed  { border-left-color: #ef4444; }
.job-card--unknown { border-left-color: #6b7280; }

.job-card-header {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.job-icon { font-size: 1.1rem; flex-shrink: 0; }

.job-card-info { flex: 1; min-width: 0; }

.job-card-meta { margin-bottom: 0.6rem; }
.job-card-meta > div { margin-bottom: 0.15rem; }

.job-card-actions { display: flex; gap: 0.5rem; }

/* ── Status badges ── */
.job-status-badge {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 0.2rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
  flex-shrink: 0;
}

.job-status-badge--ok      { background: rgba(34,197,94,0.15);  color: #4ade80; }
.job-status-badge--warning { background: rgba(245,158,11,0.15); color: #fbbf24; }
.job-status-badge--failed  { background: rgba(239,68,68,0.15);  color: #f87171; }
.job-status-badge--unknown { background: rgba(107,114,128,0.15); color: #9ca3af; }
.job-status-badge--running { background: rgba(59,130,246,0.15); color: #60a5fa; }

/* ── Datastores grid ── */
.ds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.75rem;
  padding: 1rem;
}

.ds-card {
  background: #0f1419;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 0.4rem;
  padding: 1rem;
}

.ds-card-header {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  margin-bottom: 0.75rem;
}

.ds-icon { font-size: 1.4rem; flex-shrink: 0; }

.ds-usage { margin-bottom: 0.5rem; }

.ds-usage-bar-wrap {
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.3rem;
}

.ds-usage-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.ds-usage-bar--ok      { background: #22c55e; }
.ds-usage-bar--warning { background: #f59e0b; }
.ds-usage-bar--danger  { background: #ef4444; }

.ds-usage-labels {
  display: flex;
  justify-content: space-between;
}

.ds-card-meta > div { margin-bottom: 0.15rem; }

/* ── Table ── */
.table-container { overflow-x: auto; }

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.table th {
  text-align: left;
  padding: 0.6rem 0.9rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #7a8fa8;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  white-space: nowrap;
}

.table td {
  padding: 0.65rem 0.9rem;
  color: #c0cfe4;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  vertical-align: middle;
}

.table tbody tr:hover {
  background: rgba(255,255,255,0.03);
}

/* ── Buttons ── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.45rem 0.9rem;
  border-radius: 0.35rem;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: background 0.15s, opacity 0.15s;
  text-decoration: none;
  white-space: nowrap;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary  { background: #2563eb; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #1d4ed8; }

.btn-outline  { background: transparent; color: #c0cfe4; border: 1px solid rgba(255,255,255,0.2); }
.btn-outline:hover:not(:disabled) { background: rgba(255,255,255,0.07); }

.btn-danger   { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
.btn-danger:hover:not(:disabled) { background: rgba(239,68,68,0.25); }

.btn-sm  { padding: 0.3rem 0.65rem; font-size: 0.8rem; }
.btn-xs  { padding: 0.2rem 0.5rem;  font-size: 0.75rem; }

/* ── Modal ── */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 1rem;
}

.modal-content {
  background: #1a2332;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 0.5rem;
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.9rem 1.1rem;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.modal-header h3 { margin: 0; font-size: 1rem; color: #e2e8f0; }

.modal-body { padding: 1.1rem; }

.btn-close {
  background: none;
  border: none;
  color: #8a9ab8;
  font-size: 1.2rem;
  cursor: pointer;
  line-height: 1;
  padding: 0.1rem 0.3rem;
  border-radius: 0.2rem;
}
.btn-close:hover { color: #e2e8f0; background: rgba(255,255,255,0.07); }

/* ── Form controls ── */
.form-group { margin-bottom: 1rem; }

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.form-label {
  display: block;
  font-size: 0.8rem;
  font-weight: 500;
  color: #a0b0c8;
  margin-bottom: 0.3rem;
}

.required { color: #f87171; }

.form-control {
  width: 100%;
  background: #0f1419;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 0.3rem;
  color: #e2e8f0;
  padding: 0.45rem 0.7rem;
  font-size: 0.875rem;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  color: #c0cfe4;
  font-size: 0.875rem;
}

/* ── Error/result banners ── */
.error-banner {
  background: rgba(239,68,68,0.1);
  border: 1px solid rgba(239,68,68,0.3);
  color: #f87171;
  border-radius: 0.35rem;
  padding: 0.6rem 0.9rem;
  font-size: 0.875rem;
}

.job-run-result {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  background: #1e2d42;
  border: 1px solid rgba(59,130,246,0.4);
  border-radius: 0.4rem;
  color: #c0cfe4;
  padding: 0.65rem 1rem;
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  z-index: 1000;
  max-width: 420px;
}

.btn-close-sm {
  background: none;
  border: none;
  color: #7a8fa8;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0.1rem;
  flex-shrink: 0;
}
.btn-close-sm:hover { color: #e2e8f0; }

/* ── Utility ── */
.loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(255,255,255,0.08);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin: 1.5rem auto;
}

@keyframes spin { to { transform: rotate(360deg); } }

.cron-text {
  font-family: monospace;
  font-size: 0.8rem;
  background: rgba(255,255,255,0.06);
  padding: 0.1rem 0.35rem;
  border-radius: 0.2rem;
  color: #93c5fd;
}

.text-mono { font-family: monospace; }
.text-muted { color: #7a8fa8; }
.text-success { color: #4ade80; }
.text-danger  { color: #f87171; }
.text-sm  { font-size: 0.875rem; }
.text-xs  { font-size: 0.75rem; }
.text-center { text-align: center; }
.p-2  { padding: 0.75rem 1.1rem; }
.mt-1 { margin-top: 0.4rem; }
.mt-2 { margin-top: 0.9rem; }
.mb-2 { margin-bottom: 0.9rem; }
.mb-3 { margin-bottom: 1.25rem; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.align-center { align-items: center; }

@media (max-width: 640px) {
  .pbs-page { padding: 1rem; }
  .form-row { grid-template-columns: 1fr; }
  .server-grid { grid-template-columns: 1fr; }
  .job-cards-grid { grid-template-columns: 1fr; }
  .ds-grid { grid-template-columns: 1fr; }
}
</style>
