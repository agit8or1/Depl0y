<template>
  <div class="audit-log-view">
    <div class="page-header">
      <div class="header-left">
        <h1>Audit Log</h1>
        <p class="subtitle">Track all user actions and system events</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-outline" @click="showReportModal = true">Generate Report</button>
        <button class="btn btn-primary" @click="exportCSV">Export CSV</button>
      </div>
    </div>

    <!-- Statistics Panel (collapsible) -->
    <div class="collapsible-panel" :class="{ collapsed: statsCollapsed }">
      <button class="panel-toggle" @click="statsCollapsed = !statsCollapsed">
        <span class="panel-title">Statistics</span>
        <span class="toggle-icon">{{ statsCollapsed ? '▶' : '▼' }}</span>
      </button>
      <div v-if="!statsCollapsed" class="stats-panel">
        <div v-if="statsLoading" class="stats-loading">Loading statistics...</div>
        <div v-else-if="stats" class="stats-grid">
          <div class="stat-card">
            <div class="stat-value">{{ stats.total_count.toLocaleString() }}</div>
            <div class="stat-label">Total Events ({{ stats.period_days }}d)</div>
          </div>
          <div class="stat-card stat-card-danger">
            <div class="stat-value">{{ stats.failed_count.toLocaleString() }}</div>
            <div class="stat-label">Failed Events</div>
          </div>
          <div class="stat-card-wide">
            <div class="stat-section-title">Events by Day</div>
            <div class="mini-chart">
              <svg v-if="stats.events_by_day.length" :width="chartWidth" height="60" class="bar-chart-svg">
                <g v-for="(bar, i) in chartBars" :key="i">
                  <rect
                    :x="bar.x"
                    :y="60 - bar.h"
                    :width="bar.w - 1"
                    :height="bar.h"
                    fill="#3b82f6"
                    opacity="0.8"
                    rx="2"
                  />
                  <title>{{ bar.date }}: {{ bar.count }}</title>
                </g>
              </svg>
              <span v-else class="text-muted" style="font-size:0.8rem">No data</span>
            </div>
          </div>
          <div class="stat-card-list">
            <div class="stat-section-title">Top Users</div>
            <div v-for="u in stats.top_users" :key="u.username" class="stat-list-row">
              <span class="stat-list-label">{{ u.username }}</span>
              <span class="stat-list-val">{{ u.count }}</span>
            </div>
          </div>
          <div class="stat-card-list">
            <div class="stat-section-title">Top Actions</div>
            <div v-for="a in stats.top_actions" :key="a.action" class="stat-list-row">
              <span class="stat-list-label">{{ a.action }}</span>
              <span class="stat-list-val">{{ a.count }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Filter Panel (collapsible) -->
    <div class="collapsible-panel" :class="{ collapsed: filtersCollapsed }">
      <button class="panel-toggle" @click="filtersCollapsed = !filtersCollapsed">
        <span class="panel-title">
          Filters
          <span v-if="activeFilterCount > 0" class="filter-badge">{{ activeFilterCount }}</span>
        </span>
        <span class="toggle-icon">{{ filtersCollapsed ? '▶' : '▼' }}</span>
      </button>
      <div v-if="!filtersCollapsed" class="filter-panel">
        <div class="filter-row">
          <div class="filter-group">
            <label>From Date</label>
            <input v-model="filters.from_date" type="date" class="filter-input" @change="onFilterChange" />
          </div>
          <div class="filter-group">
            <label>To Date</label>
            <input v-model="filters.to_date" type="date" class="filter-input" @change="onFilterChange" />
          </div>
          <div class="filter-group">
            <label>IP Address</label>
            <input v-model="filters.ip_address" type="text" placeholder="Filter by IP..." class="filter-input" @input="debouncedFetch" />
          </div>
          <div class="filter-group">
            <label>Search Action</label>
            <input v-model="filters.action" type="text" placeholder="Filter by action..." class="filter-input" @input="debouncedFetch" />
          </div>
          <div class="filter-group">
            <label>User ID</label>
            <input v-model.number="filters.user_id" type="number" placeholder="User ID..." class="filter-input filter-input-sm" @input="debouncedFetch" />
          </div>
        </div>
        <div class="filter-row filter-row-checks">
          <div class="filter-group">
            <label>Resource Type</label>
            <div class="checkbox-group">
              <label v-for="rt in resourceTypes" :key="rt" class="check-label">
                <input type="checkbox" :value="rt" v-model="filters.resource_types" @change="onFilterChange" />
                {{ rt }}
              </label>
            </div>
          </div>
          <div class="filter-group">
            <label>Action Type</label>
            <div class="checkbox-group">
              <label v-for="at in actionTypeOptions" :key="at.value" class="check-label">
                <input type="checkbox" :value="at.value" v-model="filters.action_types" @change="onFilterChange" />
                {{ at.label }}
              </label>
            </div>
          </div>
          <div class="filter-group">
            <label>Status</label>
            <div class="radio-group">
              <label class="check-label"><input type="radio" v-model="filters.success" value="" @change="onFilterChange" /> All</label>
              <label class="check-label"><input type="radio" v-model="filters.success" value="true" @change="onFilterChange" /> Success</label>
              <label class="check-label"><input type="radio" v-model="filters.success" value="false" @change="onFilterChange" /> Failed</label>
            </div>
          </div>
          <div class="filter-group">
            <label>Per Page</label>
            <select v-model.number="perPage" class="filter-input filter-input-sm" @change="onPerPageChange">
              <option :value="50">50</option>
              <option :value="100">100</option>
              <option :value="200">200</option>
            </select>
          </div>
          <div class="filter-actions">
            <button class="btn btn-secondary" @click="resetFilters">Clear All</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading / Error -->
    <div v-if="loading" class="loading-state">
      <span class="spinner"></span> Loading audit logs...
    </div>
    <div v-else-if="error" class="error-state">
      {{ error }}
    </div>
    <div v-else-if="logs.length === 0" class="audit-empty-state">
      <div class="empty-icon-wrap">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
      </div>
      <h4 class="empty-title">No audit entries match your filters</h4>
      <p class="empty-subtitle">Try adjusting your date range, action, user ID or IP address filters.</p>
      <button class="btn btn-outline" @click="resetFilters">Reset Filters</button>
    </div>

    <!-- Table -->
    <div v-else class="table-wrapper">
      <table class="audit-table">
        <thead>
          <tr>
            <th class="col-expand"></th>
            <th>Timestamp</th>
            <th>User</th>
            <th>Action</th>
            <th>Resource Type</th>
            <th>Resource ID</th>
            <th>Method</th>
            <th>Path</th>
            <th>IP Address</th>
            <th>Status</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="log in logs" :key="log.id">
            <tr
              class="log-row"
              :class="[actionClass(log.action), log.success === false ? 'row-failed' : '']"
              @click="toggleRow(log.id)"
            >
              <td class="col-expand">
                <span class="expand-icon">{{ expandedRow === log.id ? '▼' : '▶' }}</span>
              </td>
              <td class="col-timestamp">{{ formatDate(log.created_at) }}</td>
              <td class="col-user">{{ log.username }}</td>
              <td class="col-action">
                <span class="action-badge" :class="actionClass(log.action)">
                  {{ log.action }}
                </span>
              </td>
              <td class="col-resource-type">{{ log.resource_type || '—' }}</td>
              <td class="col-resource-id">{{ log.resource_id != null ? log.resource_id : '—' }}</td>
              <td class="col-method">
                <span v-if="log.http_method" class="method-badge" :class="'method-' + (log.http_method || '').toLowerCase()">
                  {{ log.http_method }}
                </span>
                <span v-else class="muted">—</span>
              </td>
              <td class="col-path">
                <span class="path-text" :title="log.request_path">{{ truncatePath(log.request_path) }}</span>
              </td>
              <td class="col-ip">{{ log.ip_address || '—' }}</td>
              <td class="col-status">
                <span v-if="log.response_status" class="status-badge" :class="statusClass(log.response_status)">
                  {{ log.response_status }}
                </span>
                <span v-else-if="log.success === false" class="status-badge status-failed">FAIL</span>
                <span v-else class="muted">—</span>
              </td>
              <td class="col-duration">
                <span v-if="log.duration_ms != null">{{ log.duration_ms }}ms</span>
                <span v-else class="muted">—</span>
              </td>
            </tr>
            <!-- Expanded details row -->
            <tr v-if="expandedRow === log.id" class="expanded-row">
              <td colspan="11">
                <div class="expanded-content">
                  <div class="expanded-grid">
                    <div v-if="log.user_agent" class="expanded-section">
                      <strong>User Agent:</strong>
                      <span class="ua-text">{{ log.user_agent }}</span>
                    </div>
                    <div v-if="log.request_path" class="expanded-section">
                      <strong>Full Path:</strong>
                      <code>{{ log.request_path }}</code>
                    </div>
                    <div v-if="log.details" class="expanded-section expanded-section-full">
                      <strong>Details:</strong>
                      <pre class="details-json">{{ formatJSON(log.details) }}</pre>
                    </div>
                    <div v-if="log.request_body" class="expanded-section expanded-section-full">
                      <strong>Request Body:</strong>
                      <pre class="details-json">{{ formatJSON(log.request_body) }}</pre>
                    </div>
                    <div v-if="!log.details && !log.user_agent && !log.request_body" class="muted">
                      No additional details
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="logs.length === 0">
            <td colspan="11" class="empty-state">No audit log entries found.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="!loading && !error" class="pagination">
      <span class="pagination-info">
        Showing {{ total === 0 ? 0 : offset + 1 }}–{{ Math.min(offset + logs.length, total) }} of {{ total }} entries
      </span>
      <div class="pagination-controls">
        <button class="btn btn-secondary" :disabled="offset === 0" @click="prevPage">Previous</button>
        <span class="page-indicator">Page {{ currentPage }} of {{ totalPages }}</span>
        <button class="btn btn-secondary" :disabled="offset + perPage >= total" @click="nextPage">Next</button>
      </div>
    </div>

    <!-- Compliance Report Modal -->
    <div v-if="showReportModal" class="modal-overlay" @click.self="showReportModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Generate Compliance Report</h3>
          <button @click="showReportModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Date Range</label>
            <div class="date-range-row">
              <input v-model="report.from_date" type="date" class="form-control" />
              <span class="range-sep">to</span>
              <input v-model="report.to_date" type="date" class="form-control" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Include Sections</label>
            <div class="checkbox-group">
              <label class="check-label"><input type="checkbox" v-model="report.sections.logins" /> Login Events</label>
              <label class="check-label"><input type="checkbox" v-model="report.sections.vm_ops" /> VM Operations</label>
              <label class="check-label"><input type="checkbox" v-model="report.sections.user_changes" /> User Changes</label>
              <label class="check-label"><input type="checkbox" v-model="report.sections.security" /> Security Events</label>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Format</label>
            <div class="radio-group">
              <label class="check-label"><input type="radio" v-model="report.format" value="html" /> HTML (printable to PDF)</label>
              <label class="check-label"><input type="radio" v-model="report.format" value="csv" /> CSV</label>
            </div>
          </div>
          <div v-if="reportPreview" class="report-preview">
            <div class="stat-section-title">Preview</div>
            <div class="preview-counts">
              <div class="preview-row" v-for="(count, key) in reportPreview" :key="key">
                <span>{{ key }}</span><span>{{ count }} events</span>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="previewReport" class="btn btn-secondary" :disabled="reportLoading">
            {{ reportLoading ? 'Loading...' : 'Preview Counts' }}
          </button>
          <button @click="generateReport" class="btn btn-primary" :disabled="reportLoading">
            Generate
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/services/api'

export default {
  name: 'AuditLog',
  data() {
    return {
      logs: [],
      total: 0,
      loading: false,
      error: null,
      offset: 0,
      perPage: 100,
      expandedRow: null,
      debounceTimer: null,
      statsCollapsed: false,
      filtersCollapsed: false,
      stats: null,
      statsLoading: false,
      showReportModal: false,
      reportLoading: false,
      reportPreview: null,
      report: {
        from_date: '',
        to_date: '',
        format: 'html',
        sections: {
          logins: true,
          vm_ops: true,
          user_changes: true,
          security: true,
        },
      },
      filters: {
        action: '',
        user_id: null,
        from_date: '',
        to_date: '',
        ip_address: '',
        resource_types: [],
        action_types: [],
        success: '',
      },
      resourceTypes: ['vm', 'lxc', 'node', 'storage', 'user', 'system'],
      actionTypeOptions: [
        { value: 'login', label: 'Login' },
        { value: 'create', label: 'Create' },
        { value: 'modify', label: 'Modify' },
        { value: 'delete', label: 'Delete' },
        { value: 'power', label: 'Power' },
        { value: 'backup', label: 'Backup' },
      ],
      chartWidth: 300,
    }
  },
  computed: {
    currentPage() {
      return Math.floor(this.offset / this.perPage) + 1
    },
    totalPages() {
      return Math.max(1, Math.ceil(this.total / this.perPage))
    },
    activeFilterCount() {
      let c = 0
      if (this.filters.action) c++
      if (this.filters.user_id) c++
      if (this.filters.from_date) c++
      if (this.filters.to_date) c++
      if (this.filters.ip_address) c++
      if (this.filters.resource_types.length) c++
      if (this.filters.action_types.length) c++
      if (this.filters.success !== '') c++
      return c
    },
    chartBars() {
      if (!this.stats || !this.stats.events_by_day.length) return []
      const data = this.stats.events_by_day
      const maxCount = Math.max(...data.map(d => d.count), 1)
      const barW = Math.max(4, Math.floor(this.chartWidth / data.length))
      return data.map((d, i) => ({
        x: i * barW,
        y: 0,
        w: barW,
        h: Math.max(2, Math.round((d.count / maxCount) * 58)),
        date: d.date,
        count: d.count,
      }))
    },
  },
  mounted() {
    this.fetchLogs()
    this.fetchStats()
  },
  methods: {
    async fetchLogs() {
      this.loading = true
      this.error = null
      try {
        const params = {
          skip: this.offset,
          limit: this.perPage,
        }
        if (this.filters.action) params.action = this.filters.action
        if (this.filters.user_id) params.user_id = this.filters.user_id
        if (this.filters.from_date) params.from_date = this.filters.from_date
        if (this.filters.to_date) params.to_date = this.filters.to_date
        if (this.filters.ip_address) params.ip_address = this.filters.ip_address
        if (this.filters.resource_types.length === 1) params.resource_type = this.filters.resource_types[0]
        if (this.filters.success !== '') params.success = this.filters.success === 'true'
        // Action type multi-filter: use first selected for server, filter rest client-side
        if (this.filters.action_types.length === 1) {
          params.action = this.filters.action_types[0]
        }
        const response = await api.audit.list(params)
        let logs = response.data.logs || []
        // Client-side filtering for multi-select resource types
        if (this.filters.resource_types.length > 1) {
          logs = logs.filter(l => this.filters.resource_types.includes(l.resource_type))
        }
        // Client-side filtering for multi-select action types
        if (this.filters.action_types.length > 1) {
          logs = logs.filter(l => {
            const a = (l.action || '').toLowerCase()
            return this.filters.action_types.some(at => a.includes(at))
          })
        }
        this.logs = logs
        this.total = response.data.total
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to load audit logs'
      } finally {
        this.loading = false
      }
    },
    async fetchStats() {
      this.statsLoading = true
      try {
        const r = await api.audit.stats({ days: 30 })
        this.stats = r.data
        // Compute chart width based on days
        if (this.stats.events_by_day.length) {
          this.chartWidth = Math.min(600, Math.max(200, this.stats.events_by_day.length * 10))
        }
      } catch (e) {
        // Stats are non-critical
      } finally {
        this.statsLoading = false
      }
    },
    debouncedFetch() {
      clearTimeout(this.debounceTimer)
      this.debounceTimer = setTimeout(() => {
        this.offset = 0
        this.fetchLogs()
      }, 400)
    },
    onFilterChange() {
      this.offset = 0
      this.fetchLogs()
    },
    onPerPageChange() {
      this.offset = 0
      this.fetchLogs()
    },
    prevPage() {
      this.offset = Math.max(0, this.offset - this.perPage)
      this.fetchLogs()
    },
    nextPage() {
      this.offset += this.perPage
      this.fetchLogs()
    },
    resetFilters() {
      this.filters = {
        action: '', user_id: null, from_date: '', to_date: '',
        ip_address: '', resource_types: [], action_types: [], success: '',
      }
      this.offset = 0
      this.fetchLogs()
    },
    toggleRow(id) {
      this.expandedRow = this.expandedRow === id ? null : id
    },
    formatDate(iso) {
      if (!iso) return '—'
      return new Date(iso).toLocaleString()
    },
    actionClass(action) {
      if (!action) return 'action-other'
      const a = action.toLowerCase()
      if (a.includes('create') || a.includes('add') || a.includes('register') || a.includes('deploy')) return 'action-create'
      if (a.includes('delete') || a.includes('remove') || a.includes('destroy')) return 'action-delete'
      if (a.includes('update') || a.includes('edit') || a.includes('modify') || a.includes('change') || a === 'modify') return 'action-update'
      if (a.includes('login') || a.includes('logout') || a.includes('auth') || a.includes('token') || a.includes('password') || a.includes('2fa')) return 'action-login'
      if (a.includes('start') || a.includes('stop') || a.includes('reboot') || a.includes('shutdown') || a.includes('power')) return 'action-power'
      if (a.includes('backup') || a.includes('restore') || a.includes('snapshot')) return 'action-backup'
      return 'action-other'
    },
    statusClass(status) {
      if (!status) return ''
      if (status < 300) return 'status-ok'
      if (status < 400) return 'status-redirect'
      if (status < 500) return 'status-warn'
      return 'status-error'
    },
    truncatePath(path) {
      if (!path) return '—'
      return path.length > 45 ? '...' + path.slice(-42) : path
    },
    formatJSON(data) {
      if (!data) return ''
      if (typeof data === 'string') {
        try { return JSON.stringify(JSON.parse(data), null, 2) } catch { return data }
      }
      return JSON.stringify(data, null, 2)
    },
    exportCSV() {
      const headers = ['ID', 'Timestamp', 'User', 'Action', 'Resource Type', 'Resource ID',
        'Method', 'Path', 'IP Address', 'Status', 'Duration (ms)', 'Success', 'Details']
      const rows = this.logs.map(l => [
        l.id, l.created_at, l.username, l.action,
        l.resource_type || '', l.resource_id != null ? l.resource_id : '',
        l.http_method || '', l.request_path || '',
        l.ip_address || '', l.response_status || '',
        l.duration_ms != null ? l.duration_ms : '',
        l.success != null ? l.success : '',
        l.details ? JSON.stringify(l.details) : '',
      ])
      const csvContent = [headers, ...rows]
        .map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
        .join('\n')
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
    async previewReport() {
      this.reportLoading = true
      this.reportPreview = null
      try {
        const params = {}
        if (this.report.from_date) params.from_date = this.report.from_date
        if (this.report.to_date) params.to_date = this.report.to_date
        params.limit = 9999

        const r = await api.audit.list(params)
        const logs = r.data.logs || []

        const preview = {}
        if (this.report.sections.logins) {
          preview['Login Events'] = logs.filter(l => ['login', 'login_failed', 'logout'].includes(l.action)).length
        }
        if (this.report.sections.vm_ops) {
          preview['VM Operations'] = logs.filter(l => l.resource_type === 'vm' || l.resource_type === 'lxc').length
        }
        if (this.report.sections.user_changes) {
          preview['User Changes'] = logs.filter(l => ['user_created', 'user_deleted', 'user_updated', 'user_role_changed', 'password_change'].includes(l.action)).length
        }
        if (this.report.sections.security) {
          preview['Security Events'] = logs.filter(l => ['login_failed', '2fa_enabled', '2fa_disabled', 'api_key_created', 'api_key_revoked'].includes(l.action)).length
        }
        this.reportPreview = preview
      } catch (e) {
        // ignore
      } finally {
        this.reportLoading = false
      }
    },
    async generateReport() {
      this.reportLoading = true
      try {
        const params = { limit: 9999 }
        if (this.report.from_date) params.from_date = this.report.from_date
        if (this.report.to_date) params.to_date = this.report.to_date

        const r = await api.audit.list(params)
        const allLogs = r.data.logs || []

        if (this.report.format === 'csv') {
          // CSV export of all logs in range
          const headers = ['ID', 'Timestamp', 'User', 'Action', 'Resource Type', 'Resource ID',
            'Method', 'Path', 'IP Address', 'Status', 'Duration (ms)', 'Success']
          const rows = allLogs.map(l => [
            l.id, l.created_at, l.username, l.action,
            l.resource_type || '', l.resource_id != null ? l.resource_id : '',
            l.http_method || '', l.request_path || '',
            l.ip_address || '', l.response_status || '',
            l.duration_ms != null ? l.duration_ms : '',
            l.success != null ? l.success : '',
          ])
          const csv = [headers, ...rows]
            .map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
            .join('\n')
          const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `compliance-report-${new Date().toISOString().slice(0, 10)}.csv`
          a.click()
          URL.revokeObjectURL(url)
        } else {
          // HTML report
          const fromLabel = this.report.from_date || 'All time'
          const toLabel = this.report.to_date || 'Now'

          const loginLogs = allLogs.filter(l => ['login', 'login_failed', 'logout'].includes(l.action))
          const vmLogs = allLogs.filter(l => l.resource_type === 'vm' || l.resource_type === 'lxc')
          const userLogs = allLogs.filter(l => ['user_created', 'user_deleted', 'user_updated', 'user_role_changed', 'password_change'].includes(l.action))
          const secLogs = allLogs.filter(l => ['login_failed', '2fa_enabled', '2fa_disabled', 'api_key_created', 'api_key_revoked'].includes(l.action))

          const tableHTML = (logs) => {
            if (!logs.length) return '<p style="color:#6b7280">No events in this period.</p>'
            return `<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:1rem">
              <thead><tr style="background:#1e293b;color:#94a3b8">
                <th style="padding:6px 8px;text-align:left">Timestamp</th>
                <th style="padding:6px 8px;text-align:left">User</th>
                <th style="padding:6px 8px;text-align:left">Action</th>
                <th style="padding:6px 8px;text-align:left">Resource</th>
                <th style="padding:6px 8px;text-align:left">IP</th>
                <th style="padding:6px 8px;text-align:left">Status</th>
              </tr></thead>
              <tbody>
                ${logs.map((l, i) => `<tr style="background:${i % 2 === 0 ? '#0f172a' : '#1e293b'};color:#e2e8f0">
                  <td style="padding:5px 8px;white-space:nowrap">${new Date(l.created_at).toLocaleString()}</td>
                  <td style="padding:5px 8px">${l.username || '—'}</td>
                  <td style="padding:5px 8px"><span style="font-size:11px;font-weight:600">${l.action}</span></td>
                  <td style="padding:5px 8px">${l.resource_type || ''}${l.resource_id ? ' #' + l.resource_id : ''}</td>
                  <td style="padding:5px 8px;font-family:monospace;font-size:11px">${l.ip_address || '—'}</td>
                  <td style="padding:5px 8px;color:${l.success === false ? '#f87171' : '#4ade80'}">${l.success === false ? 'FAILED' : 'OK'}</td>
                </tr>`).join('')}
              </tbody>
            </table>`
          }

          const sections = []
          if (this.report.sections.logins) sections.push(`<h2 style="color:#60a5fa;border-bottom:1px solid #334155;padding-bottom:0.5rem">Login Events (${loginLogs.length})</h2>${tableHTML(loginLogs)}`)
          if (this.report.sections.vm_ops) sections.push(`<h2 style="color:#60a5fa;border-bottom:1px solid #334155;padding-bottom:0.5rem">VM Operations (${vmLogs.length})</h2>${tableHTML(vmLogs)}`)
          if (this.report.sections.user_changes) sections.push(`<h2 style="color:#60a5fa;border-bottom:1px solid #334155;padding-bottom:0.5rem">User Changes (${userLogs.length})</h2>${tableHTML(userLogs)}`)
          if (this.report.sections.security) sections.push(`<h2 style="color:#60a5fa;border-bottom:1px solid #334155;padding-bottom:0.5rem">Security Events (${secLogs.length})</h2>${tableHTML(secLogs)}`)

          const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Compliance Report — ${fromLabel} to ${toLabel}</title>
<style>
  body { background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; }
  @media print { body { background: white; color: black; } h1, h2 { color: #1e293b !important; } }
</style>
</head>
<body>
  <h1 style="color:#f1f5f9;margin-bottom:0.25rem">Compliance Report</h1>
  <p style="color:#64748b;margin-top:0">Period: ${fromLabel} &mdash; ${toLabel} &nbsp;&bull;&nbsp; Generated: ${new Date().toLocaleString()} &nbsp;&bull;&nbsp; Total events: ${allLogs.length}</p>
  <hr style="border-color:#334155;margin-bottom:1.5rem" />
  ${sections.join('<div style="margin-bottom:2rem"></div>')}
  <p style="color:#475569;font-size:12px;margin-top:2rem;border-top:1px solid #334155;padding-top:1rem">
    Generated by Depl0y Compliance Reporting &mdash; ${new Date().toISOString()}
  </p>
</body>
</html>`

          const blob = new Blob([html], { type: 'text/html;charset=utf-8;' })
          const url = URL.createObjectURL(blob)
          window.open(url, '_blank')
          setTimeout(() => URL.revokeObjectURL(url), 60000)
        }
        this.showReportModal = false
      } catch (e) {
        // ignore
      } finally {
        this.reportLoading = false
      }
    },
  },
}
</script>

<style scoped>
.audit-log-view {
  padding: 1.5rem;
  max-width: 1600px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.25rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.header-left h1 {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0 0 0.25rem;
}

.subtitle {
  color: #6b7280;
  margin: 0;
  font-size: 0.9rem;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

/* Collapsible panels */
.collapsible-panel {
  border: 1px solid #334155;
  border-radius: 8px;
  margin-bottom: 1rem;
  overflow: hidden;
}

.panel-toggle {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #1e293b;
  border: none;
  color: #e2e8f0;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 600;
  text-align: left;
}

.panel-toggle:hover {
  background: #263448;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.filter-badge {
  background: #3b82f6;
  color: white;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 9999px;
  line-height: 1.4;
}

.toggle-icon {
  font-size: 0.7rem;
  color: #6b7280;
}

/* Stats panel */
.stats-panel {
  background: #0f172a;
  padding: 1rem 1.25rem;
}

.stats-loading {
  color: #6b7280;
  padding: 0.5rem;
  font-size: 0.85rem;
}

.stats-grid {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: flex-start;
}

.stat-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  min-width: 120px;
  text-align: center;
}

.stat-card-danger {
  border-color: rgba(239, 68, 68, 0.3);
}

.stat-card-danger .stat-value {
  color: #f87171;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: #60a5fa;
}

.stat-label {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 0.2rem;
}

.stat-card-wide {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  flex: 1;
  min-width: 200px;
}

.stat-card-list {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  min-width: 150px;
}

.stat-section-title {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 0.5rem;
}

.mini-chart {
  display: flex;
  align-items: flex-end;
  height: 60px;
}

.bar-chart-svg {
  display: block;
}

.stat-list-row {
  display: flex;
  justify-content: space-between;
  padding: 0.2rem 0;
  font-size: 0.8rem;
  border-bottom: 1px solid #1e293b;
}

.stat-list-label {
  color: #94a3b8;
}

.stat-list-val {
  font-weight: 600;
  color: #e2e8f0;
}

/* Filter panel */
.filter-panel {
  background: #0f172a;
  padding: 1rem 1.25rem;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.filter-row:last-child {
  margin-bottom: 0;
}

.filter-row-checks {
  padding-top: 0.5rem;
  border-top: 1px solid #1e293b;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.filter-group label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.filter-input {
  padding: 0.45rem 0.75rem;
  border: 1px solid #334155;
  border-radius: 6px;
  background: #1e293b;
  color: #e2e8f0;
  font-size: 0.875rem;
  outline: none;
  min-width: 150px;
}

.filter-input-sm {
  min-width: 90px;
}

.filter-input:focus {
  border-color: #3b82f6;
}

.checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 0.8rem;
}

.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.check-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: #94a3b8;
  cursor: pointer;
  white-space: nowrap;
}

.check-label input {
  cursor: pointer;
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
  padding-bottom: 0.1rem;
}

/* Buttons */
.btn {
  padding: 0.45rem 1rem;
  border-radius: 6px;
  border: none;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-secondary {
  background: #334155;
  color: #e2e8f0;
}

.btn-secondary:hover:not(:disabled) {
  background: #475569;
}

.btn-outline {
  background: transparent;
  color: #94a3b8;
  border: 1px solid #334155;
}

.btn-outline:hover:not(:disabled) {
  background: #1e293b;
  color: #e2e8f0;
}

/* States */
.loading-state,
.error-state {
  text-align: center;
  padding: 3rem 1rem;
  color: #94a3b8;
  font-size: 0.95rem;
}

.error-state {
  color: #f87171;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #334155;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  vertical-align: middle;
  margin-right: 0.5rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Table */
.table-wrapper {
  overflow-x: auto;
  border: 1px solid #334155;
  border-radius: 8px;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.audit-table thead {
  background: #1e293b;
}

.audit-table th {
  padding: 0.65rem 0.75rem;
  text-align: left;
  font-weight: 600;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
  border-bottom: 1px solid #334155;
  white-space: nowrap;
}

.audit-table td {
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid #1a2234;
  color: #e2e8f0;
  vertical-align: middle;
}

.log-row {
  cursor: pointer;
  transition: background 0.12s;
}

.log-row:hover {
  background: rgba(59, 130, 246, 0.06);
}

.row-failed td {
  background: rgba(239, 68, 68, 0.04);
}

/* Left border accent */
.log-row.action-create td:first-child { border-left: 3px solid #22c55e; }
.log-row.action-delete td:first-child { border-left: 3px solid #ef4444; }
.log-row.action-update td:first-child { border-left: 3px solid #eab308; }
.log-row.action-login td:first-child  { border-left: 3px solid #3b82f6; }
.log-row.action-power td:first-child  { border-left: 3px solid #f97316; }
.log-row.action-backup td:first-child { border-left: 3px solid #8b5cf6; }
.log-row.action-other td:first-child  { border-left: 3px solid #6b7280; }

/* Action badge */
.action-badge {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.action-badge.action-create { background: rgba(34, 197, 94, 0.12); color: #4ade80; }
.action-badge.action-delete { background: rgba(239, 68, 68, 0.12); color: #f87171; }
.action-badge.action-update { background: rgba(234, 179, 8, 0.12);  color: #facc15; }
.action-badge.action-login  { background: rgba(59, 130, 246, 0.12); color: #60a5fa; }
.action-badge.action-power  { background: rgba(249, 115, 22, 0.12); color: #fb923c; }
.action-badge.action-backup { background: rgba(139, 92, 246, 0.12); color: #a78bfa; }
.action-badge.action-other  { background: rgba(107, 114, 128, 0.12);color: #9ca3af; }

/* Method badge */
.method-badge {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
}

.method-get    { background: rgba(34, 197, 94, 0.12);  color: #4ade80; }
.method-post   { background: rgba(59, 130, 246, 0.12); color: #60a5fa; }
.method-put    { background: rgba(234, 179, 8, 0.12);  color: #facc15; }
.method-patch  { background: rgba(249, 115, 22, 0.12); color: #fb923c; }
.method-delete { background: rgba(239, 68, 68, 0.12);  color: #f87171; }

/* Status badge */
.status-badge {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-size: 0.65rem;
  font-weight: 700;
  font-family: monospace;
}

.status-ok       { background: rgba(34, 197, 94, 0.12);  color: #4ade80; }
.status-redirect { background: rgba(59, 130, 246, 0.12); color: #60a5fa; }
.status-warn     { background: rgba(234, 179, 8, 0.12);  color: #facc15; }
.status-error    { background: rgba(239, 68, 68, 0.12);  color: #f87171; }
.status-failed   { background: rgba(239, 68, 68, 0.12);  color: #f87171; }

/* Column widths */
.col-expand       { width: 28px; padding-left: 0.5rem !important; }
.col-timestamp    { white-space: nowrap; min-width: 140px; }
.col-user         { min-width: 90px; }
.col-action       { min-width: 130px; }
.col-resource-type{ min-width: 80px; }
.col-resource-id  { min-width: 70px; text-align: center; }
.col-method       { min-width: 65px; text-align: center; }
.col-path         { max-width: 220px; overflow: hidden; }
.col-ip           { min-width: 105px; white-space: nowrap; font-family: monospace; font-size: 0.78rem; }
.col-status       { min-width: 60px; text-align: center; }
.col-duration     { min-width: 70px; text-align: right; color: #6b7280; font-size: 0.78rem; white-space: nowrap; }

.expand-icon { font-size: 0.6rem; color: #6b7280; }

.path-text {
  font-family: monospace;
  font-size: 0.75rem;
  color: #64748b;
}

.muted { color: #475569; }

.empty-state {
  text-align: center;
  color: #6b7280;
  padding: 2.5rem 1rem;
}

/* Expanded row */
.expanded-row td {
  background: #0a1122;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #334155;
}

.expanded-content { font-size: 0.85rem; }

.expanded-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.expanded-section {
  min-width: 250px;
}

.expanded-section-full {
  width: 100%;
  flex: 1 0 100%;
}

.expanded-section strong {
  color: #64748b;
  margin-right: 0.4rem;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.ua-text {
  font-size: 0.8rem;
  color: #94a3b8;
}

.details-json {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 0.65rem 1rem;
  font-size: 0.78rem;
  color: #a5f3fc;
  overflow-x: auto;
  margin-top: 0.35rem;
  max-height: 280px;
  overflow-y: auto;
  white-space: pre;
}

/* Pagination */
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.pagination-info {
  font-size: 0.875rem;
  color: #6b7280;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.page-indicator {
  font-size: 0.875rem;
  color: #94a3b8;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 10px;
  width: 90%;
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid #334155;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.05rem;
  color: #f1f5f9;
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #6b7280;
  line-height: 1;
  padding: 0;
}

.modal-close:hover { color: #e2e8f0; }

.modal-body { padding: 1.5rem; }

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid #334155;
}

.form-group { margin-bottom: 1.25rem; }

.form-label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.5rem;
}

.form-control {
  width: 100%;
  padding: 0.45rem 0.75rem;
  border: 1px solid #334155;
  border-radius: 6px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 0.875rem;
  outline: none;
  box-sizing: border-box;
}

.form-control:focus { border-color: #3b82f6; }

.date-range-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.range-sep {
  color: #6b7280;
  font-size: 0.85rem;
  white-space: nowrap;
}

.report-preview {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 0.75rem 1rem;
  margin-top: 0.5rem;
}

.preview-counts {
  margin-top: 0.5rem;
}

.preview-row {
  display: flex;
  justify-content: space-between;
  padding: 0.25rem 0;
  font-size: 0.85rem;
  border-bottom: 1px solid #1e293b;
  color: #94a3b8;
}

.preview-row span:last-child {
  font-weight: 600;
  color: #60a5fa;
}

/* ── Empty state ── */
.audit-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3.5rem 1.5rem;
  text-align: center;
}

.empty-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(255,255,255,0.04);
  border: 2px dashed rgba(255,255,255,0.12);
  color: #64748b;
}

.empty-title {
  font-size: 1rem;
  font-weight: 600;
  color: #e2e8f0;
  margin: 0;
}

.empty-subtitle {
  font-size: 0.875rem;
  color: #94a3b8;
  margin: 0;
  max-width: 400px;
}
</style>
