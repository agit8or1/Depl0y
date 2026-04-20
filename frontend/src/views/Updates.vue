<template>
  <div class="updates-page">
    <div class="page-header mb-2">
      <div class="page-header-left">
        <h2>System Updates</h2>
        <p class="text-muted">Pending package updates for PVE nodes and PBS servers.</p>
      </div>
      <div class="page-header-actions">
        <span v-if="lastRefreshed" class="text-muted text-xs">
          Refreshed {{ lastRefreshedAgo }}
        </span>
        <button @click="loadOverview" class="btn btn-outline btn-sm" :disabled="loading">
          {{ loading ? 'Loading…' : '⟳ Reload' }}
        </button>
      </div>
    </div>

    <div v-if="globalError" class="error-banner mb-2">{{ globalError }}</div>

    <div class="card">
      <div class="card-header">
        <h3>Hosts</h3>
      </div>
      <div v-if="loading && rows.length === 0" class="loading-wrapper">
        <div class="loading-spinner"></div>
      </div>
      <table v-else class="table">
        <thead>
          <tr>
            <th>Host</th>
            <th>Role</th>
            <th>Node</th>
            <th>Pending</th>
            <th>Last Checked</th>
            <th class="th-actions">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="rowKey(row)">
            <td>
              <strong>{{ row.host_name }}</strong>
            </td>
            <td>
              <span :class="['role-pill', row.role === 'PVE' ? 'role-pill--pve' : 'role-pill--pbs']">
                {{ row.role }}
              </span>
            </td>
            <td class="text-sm text-muted">{{ row.node || '—' }}</td>
            <td>
              <span v-if="row.error" class="badge badge-warning" :title="row.error">error</span>
              <button
                v-else-if="row.count > 0"
                @click="toggleExpand(row)"
                :class="['badge', expandedKey === rowKey(row) ? 'badge-primary' : 'badge-warning', 'badge-clickable']"
              >{{ row.count }} pending</button>
              <span v-else class="badge badge-success">up to date</span>
            </td>
            <td class="text-sm text-muted">
              <span v-if="row.last_checked">{{ formatTime(row.last_checked) }}</span>
              <span v-else>—</span>
            </td>
            <td class="th-actions">
              <button
                @click="refreshRow(row)"
                class="btn btn-outline btn-xs"
                :disabled="isRefreshing(row)"
                title="Run apt-get update on this host"
              >{{ isRefreshing(row) ? 'Refreshing…' : 'Refresh' }}</button>
              <button
                v-if="isAdmin"
                @click="confirmApply(row)"
                class="btn btn-warning btn-xs"
                :disabled="row.count === 0 || isApplying(row)"
                title="Apply all pending updates (apt-get dist-upgrade)"
              >{{ isApplying(row) ? 'Applying…' : 'Apply' }}</button>
            </td>
          </tr>
          <tr v-if="rows.length === 0 && !loading">
            <td colspan="6" class="text-center text-muted p-2">No hosts discovered.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Expanded update list -->
    <div v-if="expandedRow && (expandedRow.updates || []).length > 0" class="card mt-2">
      <div class="card-header">
        <h3>Pending updates on {{ expandedRow.host_name }}{{ expandedRow.node ? ' / ' + expandedRow.node : '' }}</h3>
        <button @click="expandedKey = null" class="btn btn-outline btn-xs">Close</button>
      </div>
      <table class="table table-compact">
        <thead>
          <tr>
            <th>Package</th>
            <th>Current</th>
            <th>Available</th>
            <th>Section</th>
            <th>Title</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in expandedRow.updates" :key="u.Package">
            <td class="font-mono text-sm">{{ u.Package }}</td>
            <td class="text-sm text-muted">{{ u.OldVersion || '—' }}</td>
            <td class="text-sm">{{ u.Version || '—' }}</td>
            <td class="text-sm text-muted">{{ u.Section || '—' }}</td>
            <td class="text-sm">{{ u.Title || '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Confirmation modal for apply -->
    <div v-if="applyConfirm.show" class="modal-backdrop" @click.self="applyConfirm.show = false">
      <div class="modal-content">
        <h3 class="mb-1">Apply updates?</h3>
        <p>
          This will run <code>apt-get dist-upgrade</code> on
          <strong>{{ applyConfirm.row?.host_name }}</strong>{{ applyConfirm.row?.node ? ' / ' + applyConfirm.row.node : '' }}.
          Kernel or service upgrades may require a reboot.
        </p>
        <p class="text-muted text-sm">
          {{ applyConfirm.row?.count || 0 }} package(s) will be upgraded.
          The task will appear in the running-tasks bar at the top.
        </p>
        <div class="flex gap-1 mt-2">
          <button @click="applyConfirm.show = false" class="btn btn-outline btn-sm">Cancel</button>
          <button @click="doApply" class="btn btn-warning btn-sm" :disabled="applyConfirm.running">
            {{ applyConfirm.running ? 'Starting…' : 'Apply Updates' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/services/api'
import { useAuthStore } from '@/store/auth'

export default {
  name: 'Updates',

  setup() {
    return { authStore: useAuthStore() }
  },

  data() {
    return {
      loading: false,
      globalError: null,
      rows: [],
      expandedKey: null,
      refreshing: {},
      applying: {},
      lastRefreshed: null,
      _refreshTimer: null,
      applyConfirm: { show: false, row: null, running: false },
    }
  },

  computed: {
    isAdmin() { return this.authStore?.isAdmin },
    expandedRow() {
      if (!this.expandedKey) return null
      return this.rows.find(r => this.rowKey(r) === this.expandedKey) || null
    },
    lastRefreshedAgo() {
      if (!this.lastRefreshed) return ''
      const secs = Math.floor((Date.now() - this.lastRefreshed) / 1000)
      if (secs < 60) return `${secs}s ago`
      return `${Math.floor(secs / 60)}m ago`
    },
  },

  methods: {
    rowKey(row) {
      return row.role === 'PVE'
        ? `pve:${row.host_id}:${row.node}`
        : `pbs:${row.server_id}`
    },

    async loadOverview() {
      this.loading = true
      this.globalError = null
      try {
        const res = await api.updates.overview()
        this.rows = (res.data?.items || []).sort((a, b) => {
          if (a.role !== b.role) return a.role === 'PVE' ? -1 : 1
          return (a.host_name || '').localeCompare(b.host_name || '')
        })
        this.lastRefreshed = Date.now()
      } catch (e) {
        this.globalError = e?.response?.data?.detail || 'Failed to load updates overview.'
      } finally {
        this.loading = false
      }
    },

    isRefreshing(row) { return !!this.refreshing[this.rowKey(row)] },
    isApplying(row)   { return !!this.applying[this.rowKey(row)] },

    toggleExpand(row) {
      const k = this.rowKey(row)
      this.expandedKey = this.expandedKey === k ? null : k
    },

    async refreshRow(row) {
      const k = this.rowKey(row)
      this.refreshing = { ...this.refreshing, [k]: true }
      try {
        let upid = null
        if (row.role === 'PVE') {
          const res = await api.updates.refreshPveUpdates(row.host_id, row.node)
          upid = res.data?.upid
        } else {
          const res = await api.updates.refreshPbsUpdates(row.server_id)
          upid = res.data?.upid
        }
        if (upid) {
          await this.waitForTask(row, upid, 60)
        }
        // Refresh the list after the apt-get update finishes
        await this.reloadRow(row)
      } catch (e) {
        this.globalError = e?.response?.data?.detail || 'Refresh failed.'
      } finally {
        this.refreshing = { ...this.refreshing, [k]: false }
      }
    },

    async reloadRow(row) {
      try {
        let data
        if (row.role === 'PVE') {
          const res = await api.updates.listPveUpdates(row.host_id, row.node)
          data = res.data
        } else {
          const res = await api.updates.listPbsUpdates(row.server_id)
          data = res.data
        }
        Object.assign(row, {
          count: data.count,
          updates: data.updates,
          last_checked: data.last_checked || Math.floor(Date.now() / 1000),
          error: data.error || null,
        })
      } catch (e) {
        // keep prior values
      }
    },

    async waitForTask(row, upid, maxPolls = 60) {
      for (let i = 0; i < maxPolls; i++) {
        try {
          const res = row.role === 'PVE'
            ? await api.updates.pveTaskStatus(row.host_id, row.node, upid)
            : await api.updates.pbsTaskStatus(row.server_id, upid)
          const status = (res.data?.status || '').toLowerCase()
          if (status && status !== 'running' && status !== 'queued') return
        } catch (e) {
          // ignore transient poll errors
        }
        await new Promise(r => setTimeout(r, 2000))
      }
    },

    confirmApply(row) {
      this.applyConfirm = { show: true, row, running: false }
    },

    async doApply() {
      const row = this.applyConfirm.row
      if (!row) return
      this.applyConfirm.running = true
      const k = this.rowKey(row)
      this.applying = { ...this.applying, [k]: true }
      try {
        if (row.role === 'PVE') {
          await api.updates.applyPveUpdates(row.host_id, row.node)
        } else {
          await api.updates.applyPbsUpdates(row.server_id)
        }
        this.applyConfirm.show = false
      } catch (e) {
        this.globalError = e?.response?.data?.detail || 'Apply failed.'
      } finally {
        this.applyConfirm.running = false
        this.applying = { ...this.applying, [k]: false }
      }
    },

    formatTime(ts) {
      if (!ts) return '—'
      const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
      return d.toLocaleString()
    },
  },

  mounted() {
    this.loadOverview()
    this._refreshTimer = setInterval(() => this.loadOverview(), 60000)
  },

  beforeUnmount() {
    clearInterval(this._refreshTimer)
  },
}
</script>

<style scoped>
.updates-page {
  padding: 1.5rem;
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.page-header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
  color: var(--text-primary);
}

.card-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table thead th {
  text-align: left;
  padding: 0.6rem 1rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
  background: var(--surface);
}

.table tbody td {
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: middle;
}

.table tbody tr:last-child td {
  border-bottom: none;
}

.table.table-compact tbody td,
.table.table-compact thead th { padding: 0.4rem 0.75rem; }

.th-actions {
  text-align: right;
  white-space: nowrap;
}
.th-actions .btn { margin-left: 0.25rem; }

.role-pill {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 0.25rem;
  letter-spacing: 0.04em;
}
.role-pill--pve { background: rgba(59,130,246,0.15); color: #60a5fa; }
.role-pill--pbs { background: rgba(168,85,247,0.15); color: #c084fc; }

.badge-clickable {
  cursor: pointer;
  border: none;
}

.error-banner {
  background: rgba(239,68,68,0.1);
  border: 1px solid rgba(239,68,68,0.3);
  color: #f87171;
  border-radius: 0.35rem;
  padding: 0.6rem 0.9rem;
  font-size: 0.875rem;
}

.loading-wrapper { padding: 1.5rem; }

.loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid color-mix(in srgb, var(--text-secondary) 20%, transparent);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin: 0 auto;
}

@keyframes spin { to { transform: rotate(360deg); } }

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1200;
}

.modal-content {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem 1.5rem;
  min-width: 360px;
  max-width: 540px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}

.modal-content code {
  background: color-mix(in srgb, var(--text-secondary) 15%, transparent);
  padding: 0 0.3rem;
  border-radius: 0.2rem;
  font-size: 0.85em;
}

.mt-1 { margin-top: 0.4rem; }
.mt-2 { margin-top: 0.9rem; }
.mb-1 { margin-bottom: 0.4rem; }
.mb-2 { margin-bottom: 0.9rem; }
.text-sm  { font-size: 0.875rem; }
.text-xs  { font-size: 0.75rem; }
.text-center { text-align: center; }
.p-2 { padding: 0.75rem 1.1rem; }
.gap-1 { gap: 0.5rem; }
.flex { display: flex; }
.font-mono { font-family: ui-monospace, Menlo, Consolas, monospace; }
</style>
