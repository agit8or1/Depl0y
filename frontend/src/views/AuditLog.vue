<template>
  <div class="audit-log-view">
    <div class="page-header">
      <h1>Audit Log</h1>
      <p class="subtitle">Track all user actions and system events</p>
    </div>

    <!-- Filter Bar -->
    <div class="filter-bar">
      <div class="filter-group">
        <label>Search Action</label>
        <input
          v-model="filters.action"
          type="text"
          placeholder="Filter by action..."
          class="filter-input"
          @input="debouncedFetch"
        />
      </div>
      <div class="filter-group">
        <label>User ID</label>
        <input
          v-model.number="filters.user_id"
          type="number"
          placeholder="User ID..."
          class="filter-input filter-input-sm"
          @input="debouncedFetch"
        />
      </div>
      <div class="filter-group">
        <label>From</label>
        <input
          v-model="filters.from_date"
          type="date"
          class="filter-input filter-input-sm"
          @change="fetchLogs"
        />
      </div>
      <div class="filter-group">
        <label>To</label>
        <input
          v-model="filters.to_date"
          type="date"
          class="filter-input filter-input-sm"
          @change="fetchLogs"
        />
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
        <button class="btn btn-secondary" @click="resetFilters">Reset</button>
        <button class="btn btn-primary" @click="exportCSV">Export CSV</button>
      </div>
    </div>

    <!-- Loading / Error -->
    <div v-if="loading" class="loading-state">
      <span class="spinner"></span> Loading audit logs...
    </div>
    <div v-else-if="error" class="error-state">
      {{ error }}
    </div>

    <!-- Table -->
    <div v-else class="table-wrapper">
      <table class="audit-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>User</th>
            <th>Action</th>
            <th>Resource Type</th>
            <th>Resource ID</th>
            <th>IP Address</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="log in logs" :key="log.id">
            <tr
              class="log-row"
              :class="actionClass(log.action)"
              @click="toggleRow(log.id)"
            >
              <td class="col-timestamp">{{ formatDate(log.created_at) }}</td>
              <td class="col-user">{{ log.username }}</td>
              <td class="col-action">
                <span class="action-badge" :class="actionClass(log.action)">
                  {{ log.action }}
                </span>
              </td>
              <td class="col-resource-type">{{ log.resource_type || '—' }}</td>
              <td class="col-resource-id">{{ log.resource_id != null ? log.resource_id : '—' }}</td>
              <td class="col-ip">{{ log.ip_address || '—' }}</td>
              <td class="col-details">
                <span v-if="log.details" class="details-preview">
                  {{ detailsPreview(log.details) }}
                </span>
                <span v-else class="muted">—</span>
              </td>
            </tr>
            <!-- Expanded details row -->
            <tr v-if="expandedRow === log.id" class="expanded-row">
              <td colspan="7">
                <div class="expanded-content">
                  <div class="expanded-section" v-if="log.user_agent">
                    <strong>User Agent:</strong> {{ log.user_agent }}
                  </div>
                  <div class="expanded-section" v-if="log.details">
                    <strong>Details:</strong>
                    <pre class="details-json">{{ JSON.stringify(log.details, null, 2) }}</pre>
                  </div>
                  <div v-if="!log.details && !log.user_agent" class="muted">No additional details</div>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="logs.length === 0">
            <td colspan="7" class="empty-state">No audit log entries found.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="!loading && !error" class="pagination">
      <span class="pagination-info">
        Showing {{ offset + 1 }}–{{ Math.min(offset + logs.length, total) }} of {{ total }} entries
      </span>
      <div class="pagination-controls">
        <button
          class="btn btn-secondary"
          :disabled="offset === 0"
          @click="prevPage"
        >
          Previous
        </button>
        <span class="page-indicator">Page {{ currentPage }} of {{ totalPages }}</span>
        <button
          class="btn btn-secondary"
          :disabled="offset + perPage >= total"
          @click="nextPage"
        >
          Next
        </button>
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
      filters: {
        action: '',
        user_id: null,
        from_date: '',
        to_date: '',
      },
    }
  },
  computed: {
    currentPage() {
      return Math.floor(this.offset / this.perPage) + 1
    },
    totalPages() {
      return Math.max(1, Math.ceil(this.total / this.perPage))
    },
  },
  mounted() {
    this.fetchLogs()
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
        const response = await api.audit.list(params)
        let logs = response.data.logs || []
        // Client-side date filtering (backend doesn't have date range param)
        if (this.filters.from_date) {
          const from = new Date(this.filters.from_date)
          logs = logs.filter(l => new Date(l.created_at) >= from)
        }
        if (this.filters.to_date) {
          const to = new Date(this.filters.to_date)
          to.setHours(23, 59, 59, 999)
          logs = logs.filter(l => new Date(l.created_at) <= to)
        }
        this.logs = logs
        this.total = response.data.total
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to load audit logs'
      } finally {
        this.loading = false
      }
    },
    debouncedFetch() {
      clearTimeout(this.debounceTimer)
      this.debounceTimer = setTimeout(() => {
        this.offset = 0
        this.fetchLogs()
      }, 400)
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
      this.filters = { action: '', user_id: null, from_date: '', to_date: '' }
      this.offset = 0
      this.fetchLogs()
    },
    toggleRow(id) {
      this.expandedRow = this.expandedRow === id ? null : id
    },
    formatDate(iso) {
      if (!iso) return '—'
      const d = new Date(iso)
      return d.toLocaleString()
    },
    actionClass(action) {
      if (!action) return 'action-other'
      const a = action.toLowerCase()
      if (a.includes('create') || a.includes('add') || a.includes('register')) return 'action-create'
      if (a.includes('delete') || a.includes('remove') || a.includes('destroy')) return 'action-delete'
      if (a.includes('update') || a.includes('edit') || a.includes('modify') || a.includes('change')) return 'action-update'
      if (a.includes('login') || a.includes('logout') || a.includes('auth') || a.includes('token')) return 'action-login'
      return 'action-other'
    },
    detailsPreview(details) {
      if (!details) return ''
      if (typeof details === 'string') return details.slice(0, 60)
      const str = JSON.stringify(details)
      return str.length > 60 ? str.slice(0, 60) + '…' : str
    },
    exportCSV() {
      const headers = ['ID', 'Timestamp', 'User', 'Action', 'Resource Type', 'Resource ID', 'IP Address', 'Details']
      const rows = this.logs.map(l => [
        l.id,
        l.created_at,
        l.username,
        l.action,
        l.resource_type || '',
        l.resource_id != null ? l.resource_id : '',
        l.ip_address || '',
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
  },
}
</script>

<style scoped>
.audit-log-view {
  padding: 1.5rem;
  max-width: 1400px;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0 0 0.25rem;
}

.subtitle {
  color: #6b7280;
  margin: 0;
  font-size: 0.9rem;
}

/* Filter Bar */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin-bottom: 1.25rem;
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
  background: #0f172a;
  color: #e2e8f0;
  font-size: 0.875rem;
  outline: none;
  min-width: 160px;
}

.filter-input-sm {
  min-width: 110px;
}

.filter-input:focus {
  border-color: #3b82f6;
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
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
  font-size: 0.875rem;
}

.audit-table thead {
  background: #1e293b;
}

.audit-table th {
  padding: 0.75rem 1rem;
  text-align: left;
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
  border-bottom: 1px solid #334155;
  white-space: nowrap;
}

.audit-table td {
  padding: 0.65rem 1rem;
  border-bottom: 1px solid #1e293b;
  color: #e2e8f0;
  vertical-align: middle;
}

.log-row {
  cursor: pointer;
  transition: background 0.15s;
}

.log-row:hover {
  background: rgba(59, 130, 246, 0.07);
}

/* Row color coding by action */
.log-row.action-create td:first-child {
  border-left: 3px solid #22c55e;
}

.log-row.action-delete td:first-child {
  border-left: 3px solid #ef4444;
}

.log-row.action-update td:first-child {
  border-left: 3px solid #eab308;
}

.log-row.action-login td:first-child {
  border-left: 3px solid #3b82f6;
}

.log-row.action-other td:first-child {
  border-left: 3px solid #6b7280;
}

/* Action badge */
.action-badge {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.action-badge.action-create {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.action-badge.action-delete {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.action-badge.action-update {
  background: rgba(234, 179, 8, 0.15);
  color: #facc15;
}

.action-badge.action-login {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.action-badge.action-other {
  background: rgba(107, 114, 128, 0.15);
  color: #9ca3af;
}

/* Column widths */
.col-timestamp { white-space: nowrap; min-width: 155px; }
.col-user { min-width: 100px; }
.col-action { min-width: 120px; }
.col-resource-type { min-width: 110px; }
.col-resource-id { min-width: 90px; text-align: center; }
.col-ip { min-width: 115px; white-space: nowrap; }
.col-details { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.details-preview {
  color: #94a3b8;
  font-family: monospace;
  font-size: 0.8rem;
}

.muted {
  color: #475569;
}

.empty-state {
  text-align: center;
  color: #6b7280;
  padding: 2.5rem 1rem;
}

/* Expanded row */
.expanded-row td {
  background: #0f172a;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid #334155;
}

.expanded-content {
  font-size: 0.875rem;
}

.expanded-section {
  margin-bottom: 0.5rem;
}

.expanded-section strong {
  color: #94a3b8;
  margin-right: 0.5rem;
}

.details-json {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 0.75rem 1rem;
  font-size: 0.8rem;
  color: #a5f3fc;
  overflow-x: auto;
  margin-top: 0.4rem;
  max-height: 300px;
  overflow-y: auto;
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
</style>
