<template>
  <div class="system-health-page">
    <div class="page-header">
      <div class="page-header-left">
        <h2>System Health</h2>
        <p class="text-muted">Live monitoring of Depl0y platform components</p>
      </div>
      <div class="page-header-right">
        <span class="last-refresh" v-if="lastRefresh">
          Last updated: {{ formatTime(lastRefresh) }}
        </span>
        <button class="btn btn-secondary" @click="refresh" :disabled="refreshing">
          {{ refreshing ? 'Refreshing...' : 'Refresh Now' }}
        </button>
      </div>
    </div>

    <div v-if="initialLoading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>Loading system health data...</p>
    </div>

    <div v-else class="health-grid">

      <!-- 0. Live Alerts Panel (full-width) -->
      <div class="card health-card alerts-panel">
        <div class="card-header">
          <span class="card-icon">🚨</span>
          <h3>Live Alerts</h3>
          <span
            class="badge ml-2"
            :class="activeAlerts.length > 0 ? 'badge-red' : 'badge-green'"
          >
            {{ activeAlerts.length }}
          </span>
          <div class="ml-auto header-actions">
            <router-link to="/alerts" class="btn btn-sm btn-secondary">
              Configure Rules
            </router-link>
            <button
              v-if="activeAlerts.length > 0"
              class="btn btn-sm btn-secondary"
              @click="acknowledgeAllAlerts"
              :disabled="acknowledgingAlerts"
            >
              {{ acknowledgingAlerts ? 'Acknowledging...' : 'Acknowledge All' }}
            </button>
          </div>
        </div>
        <div class="card-body">
          <div v-if="loadingAlerts" class="text-muted">Loading alerts...</div>
          <div v-else-if="activeAlerts.length === 0" class="empty-state">
            No active alerts — infrastructure looks healthy.
          </div>
          <div v-else class="active-alert-list">
            <div
              v-for="alert in activeAlerts.slice(0, 5)"
              :key="alert.id"
              class="active-alert-row"
              :class="`sev-bg-${alert.severity}`"
            >
              <span class="alert-sev-dot" :class="`dot-${alert.severity}`"></span>
              <div class="alert-row-content">
                <span class="alert-row-title">{{ alert.title }}</span>
                <span class="alert-row-time text-muted">{{ formatTimestamp(alert.fired_at) }}</span>
              </div>
              <button class="btn btn-sm btn-ghost" @click="dismissAlert(alert.id)">×</button>
            </div>
            <div v-if="activeAlerts.length > 5" class="more-alerts text-muted">
              + {{ activeAlerts.length - 5 }} more —
              <router-link to="/alerts" class="link">view all</router-link>
            </div>
          </div>

          <!-- Sparkline: alerts per day, last 7 days -->
          <div class="sparkline-section" v-if="sparkline.labels.length > 0">
            <div class="sparkline-label">Alert frequency — last 7 days</div>
            <div class="sparkline-bars">
              <div
                v-for="(cnt, idx) in sparkline.counts"
                :key="idx"
                class="spark-bar-wrap"
                :title="`${sparkline.labels[idx]}: ${cnt} alert${cnt !== 1 ? 's' : ''}`"
              >
                <div
                  class="spark-bar"
                  :style="{ height: sparkBarHeight(cnt) + 'px' }"
                  :class="cnt > 0 ? 'spark-bar-active' : 'spark-bar-empty'"
                ></div>
                <div class="spark-day-label">{{ sparkDayLabel(sparkline.labels[idx]) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 1. System Info Card -->
      <div class="card health-card">
        <div class="card-header">
          <span class="card-icon">🖥️</span>
          <h3>System Info</h3>
          <span class="status-dot" :class="systemInfo.status === 'running' ? 'dot-green' : 'dot-red'"></span>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="info-label">App Name</span>
            <span class="info-value">{{ systemInfo.app_name || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Version</span>
            <span class="info-value badge badge-blue">v{{ systemInfo.version || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Status</span>
            <span class="info-value">
              <span class="badge" :class="systemInfo.status === 'running' ? 'badge-green' : 'badge-red'">
                {{ systemInfo.status || 'unknown' }}
              </span>
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">Uptime</span>
            <span class="info-value">{{ uptimeFormatted }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Hostname</span>
            <span class="info-value mono">{{ systemInfo.hostname || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Python</span>
            <span class="info-value mono">{{ systemInfo.python_version || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">FastAPI</span>
            <span class="info-value mono">{{ systemInfo.fastapi_version || '—' }}</span>
          </div>
          <!-- Backend process metrics from /system/metrics -->
          <template v-if="systemMetrics && (systemMetrics.cpu_percent !== undefined || systemMetrics.memory_mb !== undefined)">
            <div class="section-divider">Process Metrics</div>
            <div class="info-row" v-if="systemMetrics.cpu_percent !== undefined">
              <span class="info-label">Process CPU</span>
              <span class="info-value">
                <span :class="['badge', systemMetrics.cpu_percent > 80 ? 'badge-orange' : 'badge-gray']">
                  {{ systemMetrics.cpu_percent.toFixed(1) }}%
                </span>
              </span>
            </div>
            <div class="info-row" v-if="systemMetrics.memory_mb !== undefined">
              <span class="info-label">Process RAM</span>
              <span class="info-value">{{ systemMetrics.memory_mb.toFixed(0) }} MB</span>
            </div>
            <div class="info-row" v-if="systemMetrics.open_files !== undefined">
              <span class="info-label">Open Files</span>
              <span class="info-value">{{ systemMetrics.open_files }}</span>
            </div>
            <div class="info-row" v-if="systemMetrics.threads !== undefined">
              <span class="info-label">Threads</span>
              <span class="info-value">{{ systemMetrics.threads }}</span>
            </div>
          </template>
          <!-- Health check status -->
          <template v-if="systemHealth && systemHealth.checks">
            <div class="section-divider">Health Checks</div>
            <div class="info-row" v-for="(val, key) in systemHealth.checks" :key="key">
              <span class="info-label">{{ key }}</span>
              <span class="info-value">
                <span :class="['badge', val === true || val === 'ok' || val === 'healthy' ? 'badge-green' : 'badge-red']">
                  {{ val === true ? 'OK' : val === false ? 'Fail' : val }}
                </span>
              </span>
            </div>
          </template>
        </div>
      </div>

      <!-- 2. Database Stats Card -->
      <div class="card health-card">
        <div class="card-header">
          <span class="card-icon">🗄️</span>
          <h3>Database</h3>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="info-label">File Size</span>
            <span class="info-value">{{ dbStats.size_formatted || '—' }}</span>
          </div>
          <div class="section-divider">Table Row Counts</div>
          <div class="info-row" v-for="table in dbTables" :key="table.key">
            <span class="info-label">{{ table.label }}</span>
            <span class="info-value">
              <span v-if="dbStats.tables">{{ dbStats.tables[table.key] ?? '—' }}</span>
              <span v-else class="text-muted">—</span>
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">Last Backup</span>
            <span class="info-value text-muted">{{ dbStats.last_backup || 'Not configured' }}</span>
          </div>
        </div>
      </div>

      <!-- 3. Proxmox Connections Card -->
      <div class="card health-card">
        <div class="card-header">
          <span class="card-icon">🌐</span>
          <h3>Proxmox Connections</h3>
          <button
            class="btn btn-sm btn-secondary ml-auto"
            @click="testAllConnections"
            :disabled="testingAll"
          >
            {{ testingAll ? 'Testing...' : 'Test All' }}
          </button>
        </div>
        <div class="card-body">
          <div v-if="proxmoxHosts.length === 0" class="empty-state">
            No Proxmox hosts configured.
          </div>
          <div
            v-for="host in proxmoxHosts"
            :key="host.id"
            class="host-row"
          >
            <div class="host-row-header">
              <span class="host-name">{{ host.name }}</span>
              <span
                class="badge"
                :class="hostStatus[host.id] === null ? 'badge-gray' : hostStatus[host.id] ? 'badge-green' : 'badge-red'"
              >
                {{ hostStatus[host.id] === null ? 'Pending' : hostStatus[host.id] ? 'Connected' : 'Failed' }}
              </span>
            </div>
            <div class="host-meta">
              <span>{{ host.host }}</span>
              <span v-if="host.node_count !== undefined">{{ host.node_count }} node{{ host.node_count !== 1 ? 's' : '' }}</span>
              <span v-if="host.vm_count !== undefined">{{ host.vm_count }} VMs</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 4. Update Status Card -->
      <div class="card health-card">
        <div class="card-header">
          <span class="card-icon">🔄</span>
          <h3>Update Status</h3>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="info-label">Current Version</span>
            <span class="info-value badge badge-blue">v{{ systemInfo.version || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Update Available</span>
            <span class="info-value">
              <span v-if="updateStatus.loading" class="text-muted">Checking...</span>
              <span v-else-if="updateStatus.available" class="badge badge-orange">Yes — v{{ updateStatus.latest_version }}</span>
              <span v-else-if="updateStatus.checked" class="badge badge-green">Up to date</span>
              <span v-else class="text-muted">Not checked</span>
            </span>
          </div>
          <div class="info-row" v-if="updateStatus.last_check">
            <span class="info-label">Last Checked</span>
            <span class="info-value">{{ formatTimestamp(updateStatus.last_check) }}</span>
          </div>
          <div class="info-row" v-if="updateStatus.message">
            <span class="info-label">Message</span>
            <span class="info-value text-muted">{{ updateStatus.message }}</span>
          </div>
          <div class="card-actions">
            <button
              class="btn btn-sm btn-secondary"
              @click="checkUpdates"
              :disabled="updateStatus.loading"
            >
              {{ updateStatus.loading ? 'Checking...' : 'Check Now' }}
            </button>
            <button
              v-if="updateStatus.available"
              class="btn btn-sm btn-primary"
              @click="applyUpdates"
              :disabled="updateStatus.applying"
            >
              {{ updateStatus.applying ? 'Applying...' : 'Apply Update' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 5. Security Overview Card -->
      <div class="card health-card">
        <div class="card-header">
          <span class="card-icon">🔒</span>
          <h3>Security Overview</h3>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="info-label">Active Lockouts</span>
            <span class="info-value">
              <span
                class="badge"
                :class="security.lockout_count > 0 ? 'badge-red' : 'badge-green'"
              >
                {{ security.lockout_count ?? '—' }}
              </span>
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">Failed Logins (24h)</span>
            <span class="info-value">
              <span
                class="badge"
                :class="security.failed_logins_24h > 10 ? 'badge-orange' : 'badge-gray'"
              >
                {{ security.failed_logins_24h ?? '—' }}
              </span>
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">GeoIP Rules</span>
            <span class="info-value">{{ security.geoip_count ?? '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">IP Bans / Allows</span>
            <span class="info-value">{{ security.ip_list_count ?? '—' }}</span>
          </div>
          <div class="card-actions" v-if="security.lockout_count > 0">
            <router-link to="/security" class="btn btn-sm btn-secondary">
              Manage Lockouts
            </router-link>
          </div>
        </div>
      </div>

      <!-- 6. Active Users Card -->
      <div class="card health-card">
        <div class="card-header">
          <span class="card-icon">👥</span>
          <h3>Users</h3>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="info-label">Total Users</span>
            <span class="info-value">{{ userStats.total ?? '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Active</span>
            <span class="info-value badge badge-green">{{ userStats.active ?? '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Inactive</span>
            <span class="info-value badge badge-gray">{{ userStats.inactive ?? '—' }}</span>
          </div>
          <div class="section-divider">By Role</div>
          <div class="info-row">
            <span class="info-label">Admins</span>
            <span class="info-value">{{ userStats.admins ?? '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Operators</span>
            <span class="info-value">{{ userStats.operators ?? '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Viewers</span>
            <span class="info-value">{{ userStats.viewers ?? '—' }}</span>
          </div>
          <div class="section-divider">Recent Activity</div>
          <div
            v-for="user in userStats.recent_logins"
            :key="user.username"
            class="user-row"
          >
            <span class="user-name">{{ user.username }}</span>
            <span class="user-last-login text-muted">{{ formatTimestamp(user.last_login) }}</span>
          </div>
          <div v-if="!userStats.recent_logins || userStats.recent_logins.length === 0" class="text-muted">
            No recent login data.
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/services/api'

export default {
  name: 'SystemHealth',

  data() {
    return {
      initialLoading: true,
      refreshing: false,
      lastRefresh: null,
      refreshInterval: null,

      systemInfo: {},
      uptimeSeconds: null,
      systemHealth: {},   // from /system/health
      systemMetrics: {},  // from /system/metrics

      dbStats: {},
      dbTables: [
        { key: 'users', label: 'Users' },
        { key: 'proxmox_hosts', label: 'Proxmox Hosts' },
        { key: 'vms', label: 'VMs (managed)' },
        { key: 'virtual_machines', label: 'Virtual Machines' },
        { key: 'audit_logs', label: 'Audit Logs' },
      ],

      // Alerts
      activeAlerts: [],
      loadingAlerts: false,
      acknowledgingAlerts: false,
      sparkline: { labels: [], counts: [] },

      proxmoxHosts: [],
      hostStatus: {},
      testingAll: false,

      updateStatus: {
        loading: false,
        applying: false,
        checked: false,
        available: false,
        latest_version: null,
        last_check: null,
        message: null,
      },

      security: {},
      userStats: {},
    }
  },

  computed: {
    uptimeFormatted() {
      if (this.uptimeSeconds === null || this.uptimeSeconds === undefined) return '—'
      const s = Math.floor(this.uptimeSeconds)
      const days = Math.floor(s / 86400)
      const hours = Math.floor((s % 86400) / 3600)
      const minutes = Math.floor((s % 3600) / 60)
      const parts = []
      if (days > 0) parts.push(`${days}d`)
      if (hours > 0) parts.push(`${hours}h`)
      parts.push(`${minutes}m`)
      return parts.join(' ')
    }
  },

  methods: {
    async refresh() {
      if (this.refreshing) return
      this.refreshing = true
      try {
        await Promise.allSettled([
          this.loadSystemInfo(),
          this.loadProxmoxHosts(),
          this.loadSecurity(),
          this.loadUsers(),
          this.loadActiveAlerts(),
          this.loadSparkline(),
        ])
        this.lastRefresh = new Date()
      } finally {
        this.refreshing = false
      }
    },

    async loadSystemInfo() {
      try {
        const [infoRes, healthRes, metricsRes] = await Promise.allSettled([
          api.system.getInfo(),
          api.system.health(),
          api.system.getMetrics(),
        ])

        if (infoRes.status === 'fulfilled') {
          const d = infoRes.value.data || {}
          this.systemInfo = d
          if (d.uptime_seconds !== undefined) this.uptimeSeconds = d.uptime_seconds
          if (d.db) this.dbStats = d.db
        }

        if (healthRes.status === 'fulfilled') {
          this.systemHealth = healthRes.value.data || {}
          // Merge health fields into systemInfo if not already present
          const h = this.systemHealth
          if (h.status && !this.systemInfo.status) this.systemInfo = { ...this.systemInfo, status: h.status }
          if (h.uptime_seconds !== undefined && this.uptimeSeconds === null) this.uptimeSeconds = h.uptime_seconds
        }

        if (metricsRes.status === 'fulfilled') {
          this.systemMetrics = metricsRes.value.data || {}
          // db stats may come from metrics
          if (this.systemMetrics.db && Object.keys(this.dbStats).length === 0) {
            this.dbStats = this.systemMetrics.db
          }
        }
      } catch (e) {
        console.warn('Failed to load system info:', e)
      }
    },

    async loadProxmoxHosts() {
      try {
        const res = await api.proxmox.listHosts()
        const hosts = res.data?.items || res.data || []
        this.proxmoxHosts = Array.isArray(hosts) ? hosts : []
        // initialise all statuses to null (pending)
        const statusMap = {}
        this.proxmoxHosts.forEach(h => { statusMap[h.id] = null })
        this.hostStatus = statusMap
      } catch (e) {
        console.warn('Failed to load Proxmox hosts:', e)
      }
    },

    async testAllConnections() {
      if (this.testingAll) return
      this.testingAll = true
      try {
        await Promise.allSettled(
          this.proxmoxHosts.map(host => this.testConnection(host.id))
        )
      } finally {
        this.testingAll = false
      }
    },

    async testConnection(id) {
      try {
        const res = await api.proxmox.testConnection(id)
        this.hostStatus[id] = res.data?.success !== false
      } catch {
        this.hostStatus[id] = false
      }
    },

    async checkUpdates() {
      this.updateStatus.loading = true
      try {
        const res = await api.systemUpdates.check()
        const d = res.data || {}
        this.updateStatus.checked = true
        this.updateStatus.available = d.update_available || d.available || false
        this.updateStatus.latest_version = d.latest_version || d.version || null
        this.updateStatus.last_check = d.checked_at || new Date().toISOString()
        this.updateStatus.message = d.message || null
      } catch (e) {
        this.updateStatus.message = 'Failed to check for updates.'
        console.warn('Update check failed:', e)
      } finally {
        this.updateStatus.loading = false
      }
    },

    async applyUpdates() {
      if (!confirm('Apply the available update? The service may restart.')) return
      this.updateStatus.applying = true
      try {
        await api.systemUpdates.apply()
        this.updateStatus.message = 'Update applied. Service may restart shortly.'
        this.updateStatus.available = false
      } catch (e) {
        console.warn('Update apply failed:', e)
      } finally {
        this.updateStatus.applying = false
      }
    },

    async loadSecurity() {
      try {
        const [lockoutsRes, failedRes, geoRes, ipRes] = await Promise.allSettled([
          api.security.getLockouts(),
          api.security.getFailedLogins(200),
          api.security.getGeoIPRules(),
          api.security.getIPList(),
        ])

        // Lockouts
        if (lockoutsRes.status === 'fulfilled') {
          const data = lockoutsRes.value.data
          this.security.lockout_count = Array.isArray(data) ? data.length : (data?.count ?? 0)
        }

        // Failed logins in last 24h
        if (failedRes.status === 'fulfilled') {
          const entries = Array.isArray(failedRes.value.data) ? failedRes.value.data : []
          const cutoff = Date.now() - 24 * 60 * 60 * 1000
          this.security.failed_logins_24h = entries.filter(e => {
            const ts = new Date(e.timestamp || e.created_at || 0).getTime()
            return ts >= cutoff
          }).length
        }

        // GeoIP
        if (geoRes.status === 'fulfilled') {
          const data = geoRes.value.data
          this.security.geoip_count = Array.isArray(data) ? data.length : (data?.count ?? 0)
        }

        // IP list
        if (ipRes.status === 'fulfilled') {
          const data = ipRes.value.data
          this.security.ip_list_count = Array.isArray(data) ? data.length : (data?.count ?? 0)
        }

        // trigger reactivity
        this.security = { ...this.security }
      } catch (e) {
        console.warn('Failed to load security data:', e)
      }
    },

    async loadUsers() {
      try {
        const res = await api.users.list({ limit: 200 })
        const users = res.data?.items || res.data || []
        const list = Array.isArray(users) ? users : []

        const stats = {
          total: list.length,
          active: list.filter(u => u.is_active !== false).length,
          inactive: list.filter(u => u.is_active === false).length,
          admins: list.filter(u => u.role === 'admin').length,
          operators: list.filter(u => u.role === 'operator').length,
          viewers: list.filter(u => u.role === 'viewer').length,
          recent_logins: list
            .filter(u => u.last_login)
            .sort((a, b) => new Date(b.last_login) - new Date(a.last_login))
            .slice(0, 5)
            .map(u => ({ username: u.username, last_login: u.last_login }))
        }
        this.userStats = stats
      } catch (e) {
        console.warn('Failed to load users:', e)
      }
    },

    async loadActiveAlerts() {
      this.loadingAlerts = true
      try {
        const res = await api.alerts.getActive()
        this.activeAlerts = res.data || []
      } catch (e) {
        // Silently ignore — alert engine may not be firing yet
      } finally {
        this.loadingAlerts = false
      }
    },

    async loadSparkline() {
      try {
        const res = await api.alerts.getSparkline(7)
        this.sparkline = res.data || { labels: [], counts: [] }
      } catch (e) {
        // ignore
      }
    },

    async dismissAlert(id) {
      try {
        await api.alerts.dismiss(id)
        this.activeAlerts = this.activeAlerts.filter(a => a.id !== id)
      } catch (e) {
        console.warn('Failed to dismiss alert:', e)
      }
    },

    async acknowledgeAllAlerts() {
      if (!confirm('Acknowledge all active alerts?')) return
      this.acknowledgingAlerts = true
      try {
        await api.alerts.dismissAll()
        this.activeAlerts = []
      } catch (e) {
        console.warn('Failed to acknowledge all alerts:', e)
      } finally {
        this.acknowledgingAlerts = false
      }
    },

    sparkBarHeight(cnt) {
      const max = Math.max(...(this.sparkline.counts || [1]), 1)
      return Math.max(4, Math.round((cnt / max) * 40))
    },

    sparkDayLabel(isoDate) {
      if (!isoDate) return ''
      const d = new Date(isoDate)
      return d.toLocaleDateString(undefined, { weekday: 'short' })
    },

    formatTime(date) {
      if (!date) return '—'
      return date.toLocaleTimeString()
    },

    formatTimestamp(ts) {
      if (!ts) return '—'
      const d = new Date(ts)
      if (isNaN(d.getTime())) return ts
      return d.toLocaleString()
    },
  },

  async mounted() {
    await this.refresh()
    this.initialLoading = false
    // Auto-refresh every 60 seconds
    this.refreshInterval = setInterval(() => this.refresh(), 60000)
  },

  beforeUnmount() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval)
    }
  }
}
</script>

<style scoped>
.system-health-page {
  padding: 1.5rem;
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.page-header h2 {
  margin: 0 0 0.25rem;
  font-size: 1.5rem;
  color: var(--text-primary, #f1f5f9);
}

.page-header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.last-refresh {
  font-size: 0.8rem;
  color: var(--text-muted, rgba(255,255,255,0.5));
}

.text-muted {
  color: var(--text-muted, rgba(255,255,255,0.5));
}

/* Grid layout */
.health-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.25rem;
}

@media (max-width: 1100px) {
  .health-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 650px) {
  .health-grid {
    grid-template-columns: 1fr;
  }
}

/* Cards */
.health-card {
  background: var(--card-bg, #1e2a3a);
  border: 1px solid var(--border-color, rgba(255,255,255,0.08));
  border-radius: 0.625rem;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.08));
}

.card-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
  flex: 1;
}

.card-icon {
  font-size: 1.2rem;
}

.card-body {
  padding: 1rem 1.25rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.card-actions {
  margin-top: 0.75rem;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

/* Status dot */
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-green { background: #22c55e; box-shadow: 0 0 6px #22c55e80; }
.dot-red   { background: #ef4444; box-shadow: 0 0 6px #ef444480; }

/* Info rows */
.info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  min-height: 1.75rem;
}

.info-label {
  font-size: 0.82rem;
  color: var(--text-muted, rgba(255,255,255,0.55));
  white-space: nowrap;
}

.info-value {
  font-size: 0.875rem;
  color: var(--text-primary, #f1f5f9);
  text-align: right;
}

.mono {
  font-family: monospace;
  font-size: 0.8rem;
}

/* Section divider */
.section-divider {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, rgba(255,255,255,0.4));
  margin-top: 0.5rem;
  margin-bottom: 0.25rem;
  border-top: 1px solid var(--border-color, rgba(255,255,255,0.08));
  padding-top: 0.5rem;
}

/* Badges */
.badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.3rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-green  { background: rgba(34,197,94,0.15);  color: #4ade80; }
.badge-red    { background: rgba(239,68,68,0.15);   color: #f87171; }
.badge-orange { background: rgba(249,115,22,0.15);  color: #fb923c; }
.badge-blue   { background: rgba(59,130,246,0.15);  color: #60a5fa; }
.badge-gray   { background: rgba(148,163,184,0.12); color: #94a3b8; }

/* Proxmox host rows */
.host-row {
  border: 1px solid var(--border-color, rgba(255,255,255,0.08));
  border-radius: 0.4rem;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
}

.host-row-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.2rem;
}

.host-name {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-primary, #f1f5f9);
}

.host-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.78rem;
  color: var(--text-muted, rgba(255,255,255,0.5));
}

/* User rows */
.user-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.2rem 0;
}

.user-name {
  font-size: 0.85rem;
  color: var(--text-primary, #f1f5f9);
}

.user-last-login {
  font-size: 0.78rem;
}

/* Loading */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  gap: 1rem;
  color: var(--text-muted, rgba(255,255,255,0.5));
}

.loading-spinner {
  width: 2rem;
  height: 2rem;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Empty state */
.empty-state {
  color: var(--text-muted, rgba(255,255,255,0.5));
  font-size: 0.875rem;
  padding: 0.5rem 0;
}

/* Buttons */
.btn {
  padding: 0.45rem 1rem;
  border-radius: 0.4rem;
  border: none;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s, background 0.15s;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #3b82f6;
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-secondary {
  background: rgba(255,255,255,0.1);
  color: var(--text-primary, #f1f5f9);
  border: 1px solid rgba(255,255,255,0.15);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(255,255,255,0.15);
}

.btn-sm {
  padding: 0.3rem 0.7rem;
  font-size: 0.8rem;
}

.ml-auto {
  margin-left: auto;
}

.mb-2 {
  margin-bottom: 0.5rem;
}

/* Alerts panel — full-width card */
.alerts-panel {
  grid-column: 1 / -1;
}

.ml-2 { margin-left: 0.5rem; }

.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

/* Active alert rows */
.active-alert-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

.active-alert-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0.6rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border-color, rgba(255,255,255,0.08));
}

.sev-bg-critical { border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.06); }
.sev-bg-warning  { border-color: rgba(245,158,11,0.3); background: rgba(245,158,11,0.06); }
.sev-bg-info     { border-color: rgba(59,130,246,0.3);  background: rgba(59,130,246,0.06);  }

.alert-sev-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-critical { background: #ef4444; box-shadow: 0 0 5px #ef444480; }
.dot-warning  { background: #f59e0b; box-shadow: 0 0 5px #f59e0b80; }
.dot-info     { background: #3b82f6; box-shadow: 0 0 5px #3b82f680; }

.alert-row-content {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.alert-row-title {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary, #f1f5f9);
}

.alert-row-time {
  font-size: 0.75rem;
  white-space: nowrap;
}

.more-alerts {
  font-size: 0.8rem;
  padding: 0.25rem 0;
}

.link {
  color: #60a5fa;
  text-decoration: underline;
  cursor: pointer;
}

/* Sparkline */
.sparkline-section {
  border-top: 1px solid var(--border-color, rgba(255,255,255,0.08));
  padding-top: 0.75rem;
  margin-top: 0.5rem;
}

.sparkline-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
  color: var(--text-muted, rgba(255,255,255,0.4));
  margin-bottom: 0.5rem;
}

.sparkline-bars {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 56px;
}

.spark-bar-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.spark-bar {
  width: 100%;
  border-radius: 3px 3px 0 0;
  min-height: 4px;
  transition: height 0.3s;
}

.spark-bar-active { background: #3b82f6; }
.spark-bar-empty  { background: rgba(255,255,255,0.1); }

.spark-day-label {
  font-size: 0.65rem;
  color: var(--text-muted, rgba(255,255,255,0.4));
  text-align: center;
}
</style>
