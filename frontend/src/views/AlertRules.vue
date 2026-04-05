<template>
  <div class="alert-rules-page">
    <div class="page-header">
      <div class="page-header-left">
        <h2>Alert Rules</h2>
        <p class="text-muted">Proactive monitoring and alerting for your infrastructure</p>
      </div>
      <div class="page-header-right">
        <button class="btn btn-secondary" @click="refresh" :disabled="loading">
          {{ loading ? 'Refreshing...' : 'Refresh' }}
        </button>
        <button class="btn btn-primary" @click="openCreateModal">
          + Create Rule
        </button>
      </div>
    </div>

    <!-- ── Active Alerts ─────────────────────────────────────────────────── -->
    <section class="section">
      <div class="section-header">
        <h3>Active Alerts</h3>
        <span class="badge" :class="activeAlerts.length > 0 ? 'badge-red' : 'badge-green'">
          {{ activeAlerts.length }}
        </span>
        <button
          v-if="activeAlerts.length > 0"
          class="btn btn-sm btn-secondary ml-auto"
          @click="dismissAll"
          :disabled="dismissingAll"
        >
          {{ dismissingAll ? 'Acknowledging...' : 'Acknowledge All' }}
        </button>
      </div>

      <div v-if="loadingActive" class="loading-row">Loading active alerts...</div>

      <div v-else-if="activeAlerts.length === 0" class="empty-state">
        No active alerts. Your infrastructure looks healthy.
      </div>

      <div v-else class="alert-list">
        <div
          v-for="alert in activeAlerts"
          :key="alert.id"
          class="alert-item"
          :class="`alert-${alert.severity}`"
        >
          <div class="alert-severity-bar"></div>
          <div class="alert-content">
            <div class="alert-title">
              <span class="severity-icon">{{ severityIcon(alert.severity) }}</span>
              {{ alert.title }}
            </div>
            <div class="alert-message">{{ alert.message }}</div>
            <div class="alert-meta">
              <span class="alert-time">{{ formatTimestamp(alert.fired_at) }}</span>
              <span v-if="alert.rule_key" class="alert-key">{{ alert.rule_key }}</span>
            </div>
          </div>
          <button class="btn btn-sm btn-ghost dismiss-btn" @click="dismiss(alert.id)">
            Dismiss
          </button>
        </div>
      </div>
    </section>

    <!-- ── Alert Rules ────────────────────────────────────────────────────── -->
    <section class="section">
      <div class="section-header">
        <h3>Alert Rules</h3>
        <span class="badge badge-gray">{{ rules.length }}</span>
      </div>

      <div v-if="loadingRules" class="loading-row">Loading rules...</div>

      <div v-else-if="rules.length === 0" class="empty-state">
        No custom alert rules configured. Click "Create Rule" to add one.
      </div>

      <div v-else class="rules-table-wrap">
        <table class="rules-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Threshold</th>
              <th>Scope</th>
              <th>Notifications</th>
              <th>Cooldown</th>
              <th>Last Fired</th>
              <th>Enabled</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rule in rules" :key="rule.id" :class="{ 'row-disabled': !rule.enabled }">
              <td class="rule-name">{{ rule.name }}</td>
              <td><span class="type-badge">{{ ruleTypeLabel(rule.rule_type) }}</span></td>
              <td>{{ rule.threshold != null ? rule.threshold + ruleThresholdUnit(rule.rule_type) : '—' }}</td>
              <td class="rule-scope">{{ ruleScope(rule) }}</td>
              <td class="notif-icons">
                <span v-if="rule.notify_in_app" title="In-app">🔔</span>
                <span v-if="rule.notify_webhook" title="Webhook">🔗</span>
                <span v-if="rule.notify_slack" title="Slack">💬</span>
              </td>
              <td>{{ rule.cooldown_minutes }}m</td>
              <td>{{ rule.last_fired_at ? formatTimestamp(rule.last_fired_at) : 'Never' }}</td>
              <td>
                <label class="toggle-switch" :title="rule.enabled ? 'Disable rule' : 'Enable rule'">
                  <input type="checkbox" :checked="rule.enabled" @change="toggleRule(rule)" />
                  <span class="toggle-slider"></span>
                </label>
              </td>
              <td class="row-actions">
                <button class="btn btn-sm btn-secondary" @click="openEditModal(rule)">Edit</button>
                <button class="btn btn-sm btn-danger" @click="deleteRule(rule)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ── Alert History ──────────────────────────────────────────────────── -->
    <section class="section">
      <div class="section-header">
        <h3>Alert History</h3>
        <div class="history-filters">
          <select v-model="historyFilters.days" @change="loadHistory" class="filter-select">
            <option :value="1">Last 24h</option>
            <option :value="3">Last 3 days</option>
            <option :value="7">Last 7 days</option>
            <option :value="30">Last 30 days</option>
          </select>
          <select v-model="historyFilters.severity" @change="loadHistory" class="filter-select">
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
        </div>
        <span class="total-label">{{ history.total }} total</span>
      </div>

      <div v-if="loadingHistory" class="loading-row">Loading history...</div>

      <div v-else-if="history.items.length === 0" class="empty-state">
        No alert events in the selected time range.
      </div>

      <div v-else>
        <table class="history-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Severity</th>
              <th>Title</th>
              <th>Message</th>
              <th>Acknowledged</th>
              <th>Resolution</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in history.items" :key="event.id">
              <td class="event-time">{{ formatTimestamp(event.fired_at) }}</td>
              <td>
                <span class="severity-badge" :class="`sev-${event.severity}`">
                  {{ event.severity }}
                </span>
              </td>
              <td class="event-title">{{ event.title }}</td>
              <td class="event-message">{{ event.message }}</td>
              <td>
                <span v-if="event.acknowledged" class="badge badge-green">Yes</span>
                <span v-else class="badge badge-red">No</span>
              </td>
              <td>
                {{ event.resolution_minutes != null ? event.resolution_minutes + 'm' : '—' }}
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination -->
        <div class="pagination" v-if="history.total > historyFilters.per_page">
          <button
            class="btn btn-sm btn-secondary"
            :disabled="historyFilters.page <= 1"
            @click="historyFilters.page--; loadHistory()"
          >
            Previous
          </button>
          <span>Page {{ historyFilters.page }}</span>
          <button
            class="btn btn-sm btn-secondary"
            :disabled="historyFilters.page * historyFilters.per_page >= history.total"
            @click="historyFilters.page++; loadHistory()"
          >
            Next
          </button>
        </div>
      </div>
    </section>

    <!-- ── Create / Edit Rule Modal ─────────────────────────────────────── -->
    <div v-if="showRuleModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingRule ? 'Edit Alert Rule' : 'Create Alert Rule' }}</h3>
          <button class="modal-close" @click="closeModal">×</button>
        </div>

        <div class="modal-body">
          <div class="form-group">
            <label>Rule Name *</label>
            <input v-model="ruleForm.name" class="form-input" placeholder="e.g. Storage warning on pve1" />
          </div>

          <div class="form-group">
            <label>Rule Type *</label>
            <select v-model="ruleForm.rule_type" class="form-input">
              <option value="">— Select type —</option>
              <option value="storage_usage">Storage Usage</option>
              <option value="node_cpu">Node CPU</option>
              <option value="node_memory">Node Memory</option>
              <option value="vm_stopped">VM Stopped</option>
              <option value="backup_failed">Backup Failed</option>
              <option value="login_failures">Login Failures</option>
            </select>
          </div>

          <div class="form-group" v-if="showThreshold">
            <label>Threshold {{ ruleThresholdUnit(ruleForm.rule_type) }}</label>
            <input
              v-model.number="ruleForm.threshold"
              type="number"
              min="0"
              max="100"
              step="1"
              class="form-input"
              :placeholder="thresholdPlaceholder"
            />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Scope — Host</label>
              <select v-model="ruleForm.host_id" class="form-input">
                <option :value="null">All hosts</option>
                <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>Scope — Node</label>
              <input
                v-model="ruleForm.node"
                class="form-input"
                placeholder="Leave blank for all nodes"
              />
            </div>
          </div>

          <div class="form-group">
            <label>Cooldown (minutes)</label>
            <input
              v-model.number="ruleForm.cooldown_minutes"
              type="number"
              min="1"
              class="form-input"
              placeholder="60"
            />
          </div>

          <div class="form-section-label">Notifications</div>
          <div class="checkbox-row">
            <label class="checkbox-label">
              <input type="checkbox" v-model="ruleForm.notify_in_app" />
              In-app notification
            </label>
            <label class="checkbox-label">
              <input type="checkbox" v-model="ruleForm.notify_webhook" />
              Webhook
            </label>
            <label class="checkbox-label">
              <input type="checkbox" v-model="ruleForm.notify_slack" />
              Slack
            </label>
          </div>

          <div class="form-group toggle-row">
            <label>Enabled</label>
            <label class="toggle-switch">
              <input type="checkbox" v-model="ruleForm.enabled" />
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeModal">Cancel</button>
          <button class="btn btn-primary" @click="saveRule" :disabled="savingRule">
            {{ savingRule ? 'Saving...' : (editingRule ? 'Update Rule' : 'Create Rule') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/services/api'

const EMPTY_RULE_FORM = {
  name: '',
  rule_type: '',
  threshold: null,
  host_id: null,
  node: '',
  enabled: true,
  notify_in_app: true,
  notify_webhook: false,
  notify_slack: false,
  cooldown_minutes: 60,
}

export default {
  name: 'AlertRules',

  data() {
    return {
      loading: false,
      loadingActive: false,
      loadingRules: false,
      loadingHistory: false,
      dismissingAll: false,
      savingRule: false,

      activeAlerts: [],
      rules: [],
      hosts: [],

      history: { total: 0, items: [] },
      historyFilters: {
        days: 7,
        severity: '',
        page: 1,
        per_page: 50,
      },

      showRuleModal: false,
      editingRule: null,
      ruleForm: { ...EMPTY_RULE_FORM },

      refreshInterval: null,
    }
  },

  computed: {
    showThreshold() {
      return ['storage_usage', 'node_cpu', 'node_memory', 'login_failures'].includes(this.ruleForm.rule_type)
    },
    thresholdPlaceholder() {
      const map = {
        storage_usage: '85',
        node_cpu: '90',
        node_memory: '95',
        login_failures: '5',
      }
      return map[this.ruleForm.rule_type] || ''
    },
  },

  methods: {
    async refresh() {
      this.loading = true
      try {
        await Promise.allSettled([
          this.loadActiveAlerts(),
          this.loadRules(),
          this.loadHistory(),
          this.loadHosts(),
        ])
      } finally {
        this.loading = false
      }
    },

    async loadActiveAlerts() {
      this.loadingActive = true
      try {
        const res = await api.alerts.getActive()
        this.activeAlerts = res.data || []
      } catch (e) {
        console.warn('Failed to load active alerts:', e)
      } finally {
        this.loadingActive = false
      }
    },

    async loadRules() {
      this.loadingRules = true
      try {
        const res = await api.alerts.listRules()
        this.rules = res.data || []
      } catch (e) {
        console.warn('Failed to load alert rules:', e)
      } finally {
        this.loadingRules = false
      }
    },

    async loadHistory() {
      this.loadingHistory = true
      try {
        const res = await api.alerts.getHistory({
          days: this.historyFilters.days,
          severity: this.historyFilters.severity || undefined,
          page: this.historyFilters.page,
          per_page: this.historyFilters.per_page,
        })
        this.history = res.data || { total: 0, items: [] }
      } catch (e) {
        console.warn('Failed to load alert history:', e)
      } finally {
        this.loadingHistory = false
      }
    },

    async loadHosts() {
      try {
        const res = await api.proxmox.listHosts()
        this.hosts = res.data?.items || res.data || []
      } catch (e) {
        console.warn('Failed to load hosts:', e)
      }
    },

    async dismiss(id) {
      try {
        await api.alerts.dismiss(id)
        this.activeAlerts = this.activeAlerts.filter(a => a.id !== id)
      } catch (e) {
        console.warn('Failed to dismiss alert:', e)
      }
    },

    async dismissAll() {
      if (!confirm('Acknowledge all active alerts?')) return
      this.dismissingAll = true
      try {
        await api.alerts.dismissAll()
        this.activeAlerts = []
      } catch (e) {
        console.warn('Failed to dismiss all alerts:', e)
      } finally {
        this.dismissingAll = false
      }
    },

    async toggleRule(rule) {
      try {
        const res = await api.alerts.toggleRule(rule.id)
        rule.enabled = res.data.enabled
      } catch (e) {
        console.warn('Failed to toggle rule:', e)
        // Revert optimistic UI by reloading
        await this.loadRules()
      }
    },

    async deleteRule(rule) {
      if (!confirm(`Delete alert rule "${rule.name}"?`)) return
      try {
        await api.alerts.deleteRule(rule.id)
        this.rules = this.rules.filter(r => r.id !== rule.id)
      } catch (e) {
        console.warn('Failed to delete rule:', e)
      }
    },

    openCreateModal() {
      this.editingRule = null
      this.ruleForm = { ...EMPTY_RULE_FORM }
      this.showRuleModal = true
    },

    openEditModal(rule) {
      this.editingRule = rule
      this.ruleForm = {
        name: rule.name,
        rule_type: rule.rule_type,
        threshold: rule.threshold,
        host_id: rule.host_id,
        node: rule.node || '',
        enabled: rule.enabled,
        notify_in_app: rule.notify_in_app,
        notify_webhook: rule.notify_webhook,
        notify_slack: rule.notify_slack,
        cooldown_minutes: rule.cooldown_minutes,
      }
      this.showRuleModal = true
    },

    closeModal() {
      this.showRuleModal = false
      this.editingRule = null
    },

    async saveRule() {
      if (!this.ruleForm.name.trim()) {
        alert('Rule name is required.')
        return
      }
      if (!this.ruleForm.rule_type) {
        alert('Rule type is required.')
        return
      }

      this.savingRule = true
      try {
        const payload = {
          ...this.ruleForm,
          node: this.ruleForm.node || null,
          threshold: this.ruleForm.threshold !== '' ? this.ruleForm.threshold : null,
        }

        if (this.editingRule) {
          const res = await api.alerts.updateRule(this.editingRule.id, payload)
          const idx = this.rules.findIndex(r => r.id === this.editingRule.id)
          if (idx !== -1) this.rules[idx] = res.data
        } else {
          const res = await api.alerts.createRule(payload)
          this.rules.push(res.data)
        }
        this.closeModal()
      } catch (e) {
        console.warn('Failed to save rule:', e)
      } finally {
        this.savingRule = false
      }
    },

    // ── Helpers ────────────────────────────────────────────────────────────

    ruleTypeLabel(type) {
      return {
        storage_usage: 'Storage Usage',
        node_cpu: 'Node CPU',
        node_memory: 'Node Memory',
        vm_stopped: 'VM Stopped',
        backup_failed: 'Backup Failed',
        login_failures: 'Login Failures',
      }[type] || type
    },

    ruleThresholdUnit(type) {
      return {
        storage_usage: '%',
        node_cpu: '%',
        node_memory: '%',
        login_failures: ' failures',
      }[type] || ''
    },

    ruleScope(rule) {
      const parts = []
      if (rule.host_id) parts.push(`Host ${rule.host_id}`)
      else parts.push('All hosts')
      if (rule.node) parts.push(rule.node)
      return parts.join(' / ')
    },

    severityIcon(severity) {
      return { critical: '🔴', warning: '🟡', info: '🔵' }[severity] || '⚪'
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
    // Auto-refresh active alerts every 30 seconds
    this.refreshInterval = setInterval(() => this.loadActiveAlerts(), 30000)
  },

  beforeUnmount() {
    if (this.refreshInterval) clearInterval(this.refreshInterval)
  },
}
</script>

<style scoped>
.alert-rules-page {
  padding: 1.5rem;
  max-width: 1400px;
}

/* ── Page header ──────────────────────────────────────────────────────── */
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
  gap: 0.75rem;
  align-items: center;
}

.text-muted {
  color: var(--text-muted, rgba(255,255,255,0.5));
  font-size: 0.875rem;
  margin: 0;
}

/* ── Sections ─────────────────────────────────────────────────────────── */
.section {
  background: var(--card-bg, #1e2a3a);
  border: 1px solid var(--border-color, rgba(255,255,255,0.08));
  border-radius: 0.625rem;
  margin-bottom: 1.5rem;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.08));
  flex-wrap: wrap;
}

.section-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.ml-auto { margin-left: auto; }
.total-label { font-size: 0.8rem; color: var(--text-muted, rgba(255,255,255,0.5)); margin-left: auto; }

.loading-row {
  padding: 1.5rem 1.25rem;
  color: var(--text-muted, rgba(255,255,255,0.5));
  font-size: 0.875rem;
}

.empty-state {
  padding: 2rem 1.25rem;
  text-align: center;
  color: var(--text-muted, rgba(255,255,255,0.5));
  font-size: 0.875rem;
}

/* ── Active alert list ────────────────────────────────────────────────── */
.alert-list {
  padding: 0.75rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  border: 1px solid var(--border-color, rgba(255,255,255,0.08));
  border-radius: 0.5rem;
  overflow: hidden;
  background: rgba(255,255,255,0.03);
}

.alert-critical .alert-severity-bar { background: #ef4444; width: 4px; flex-shrink: 0; min-height: 60px; }
.alert-warning  .alert-severity-bar { background: #f59e0b; width: 4px; flex-shrink: 0; min-height: 60px; }
.alert-info     .alert-severity-bar { background: #3b82f6; width: 4px; flex-shrink: 0; min-height: 60px; }

.alert-content {
  flex: 1;
  padding: 0.75rem 0.5rem;
  min-width: 0;
}

.alert-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.3rem;
}

.alert-message {
  font-size: 0.82rem;
  color: var(--text-muted, rgba(255,255,255,0.65));
  line-height: 1.5;
  margin-bottom: 0.4rem;
  word-break: break-word;
}

.alert-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-muted, rgba(255,255,255,0.4));
}

.dismiss-btn {
  margin: 0.75rem 0.75rem 0.75rem 0;
  flex-shrink: 0;
  align-self: flex-start;
}

/* ── Rules table ──────────────────────────────────────────────────────── */
.rules-table-wrap {
  overflow-x: auto;
}

.rules-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.rules-table th {
  padding: 0.6rem 1rem;
  text-align: left;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, rgba(255,255,255,0.45));
  background: rgba(255,255,255,0.03);
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.08));
}

.rules-table td {
  padding: 0.65rem 1rem;
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.05));
  color: var(--text-primary, #f1f5f9);
  vertical-align: middle;
}

.rules-table tbody tr:last-child td {
  border-bottom: none;
}

.rules-table tbody tr:hover td {
  background: rgba(255,255,255,0.03);
}

.row-disabled td {
  opacity: 0.5;
}

.rule-name { font-weight: 500; }

.type-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  background: rgba(59,130,246,0.12);
  color: #60a5fa;
  font-size: 0.75rem;
  font-weight: 500;
}

.rule-scope { font-size: 0.8rem; color: var(--text-muted, rgba(255,255,255,0.55)); }

.notif-icons { font-size: 1rem; }

.row-actions { display: flex; gap: 0.4rem; white-space: nowrap; }

/* ── History table ────────────────────────────────────────────────────── */
.history-filters {
  display: flex;
  gap: 0.5rem;
  margin-left: auto;
  align-items: center;
  flex-wrap: wrap;
}

.filter-select {
  background: rgba(255,255,255,0.07);
  border: 1px solid var(--border-color, rgba(255,255,255,0.12));
  border-radius: 0.35rem;
  padding: 0.3rem 0.6rem;
  font-size: 0.8rem;
  color: var(--text-primary, #f1f5f9);
  cursor: pointer;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.history-table th {
  padding: 0.6rem 1rem;
  text-align: left;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, rgba(255,255,255,0.45));
  background: rgba(255,255,255,0.03);
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.08));
}

.history-table td {
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.05));
  color: var(--text-primary, #f1f5f9);
  vertical-align: top;
}

.history-table tbody tr:last-child td {
  border-bottom: none;
}

.event-time { white-space: nowrap; font-size: 0.78rem; color: var(--text-muted, rgba(255,255,255,0.55)); }
.event-title { font-weight: 500; max-width: 250px; }
.event-message { max-width: 350px; font-size: 0.78rem; color: var(--text-muted, rgba(255,255,255,0.65)); word-break: break-word; }

.severity-badge {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  border-radius: 0.25rem;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
}
.sev-critical { background: rgba(239,68,68,0.15); color: #f87171; }
.sev-warning  { background: rgba(245,158,11,0.15); color: #fbbf24; }
.sev-info     { background: rgba(59,130,246,0.15);  color: #60a5fa; }

.pagination {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1.25rem;
  justify-content: center;
  font-size: 0.85rem;
  color: var(--text-muted, rgba(255,255,255,0.55));
}

/* ── Badges ───────────────────────────────────────────────────────────── */
.badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.3rem;
  font-size: 0.75rem;
  font-weight: 600;
}
.badge-green  { background: rgba(34,197,94,0.15);  color: #4ade80; }
.badge-red    { background: rgba(239,68,68,0.15);   color: #f87171; }
.badge-gray   { background: rgba(148,163,184,0.12); color: #94a3b8; }

/* ── Toggle switch ────────────────────────────────────────────────────── */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 38px;
  height: 20px;
  cursor: pointer;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,0.15);
  border-radius: 20px;
  transition: background 0.2s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  height: 14px;
  width: 14px;
  left: 3px;
  bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: transform 0.2s;
}

.toggle-switch input:checked + .toggle-slider {
  background: #3b82f6;
}

.toggle-switch input:checked + .toggle-slider::before {
  transform: translateX(18px);
}

/* ── Modal ─────────────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal {
  background: var(--card-bg, #1e2a3a);
  border: 1px solid var(--border-color, rgba(255,255,255,0.12));
  border-radius: 0.75rem;
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.08));
}

.modal-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.modal-close {
  background: none;
  border: none;
  color: var(--text-muted, rgba(255,255,255,0.5));
  font-size: 1.4rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.modal-close:hover { color: var(--text-primary, #f1f5f9); }

.modal-body {
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color, rgba(255,255,255,0.08));
}

/* ── Form ──────────────────────────────────────────────────────────────── */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-group label {
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--text-muted, rgba(255,255,255,0.7));
}

.form-input {
  background: rgba(255,255,255,0.07);
  border: 1px solid var(--border-color, rgba(255,255,255,0.12));
  border-radius: 0.4rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  color: var(--text-primary, #f1f5f9);
  width: 100%;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: #3b82f6;
  background: rgba(255,255,255,0.1);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-section-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, rgba(255,255,255,0.4));
  border-top: 1px solid var(--border-color, rgba(255,255,255,0.08));
  padding-top: 0.75rem;
  margin-top: 0.25rem;
}

.checkbox-row {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--text-primary, #f1f5f9);
  cursor: pointer;
}

.toggle-row {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

/* ── Buttons ───────────────────────────────────────────────────────────── */
.btn {
  padding: 0.45rem 1rem;
  border-radius: 0.4rem;
  border: none;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s, background 0.15s;
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }

.btn-secondary {
  background: rgba(255,255,255,0.1);
  color: var(--text-primary, #f1f5f9);
  border: 1px solid rgba(255,255,255,0.15);
}
.btn-secondary:hover:not(:disabled) { background: rgba(255,255,255,0.15); }

.btn-danger { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.25); }
.btn-danger:hover:not(:disabled) { background: rgba(239,68,68,0.25); }

.btn-ghost { background: none; color: var(--text-muted, rgba(255,255,255,0.55)); }
.btn-ghost:hover:not(:disabled) { color: var(--text-primary, #f1f5f9); background: rgba(255,255,255,0.07); }

.btn-sm { padding: 0.3rem 0.7rem; font-size: 0.8rem; }

/* ── select option dark mode fix ─────────────────────────────────────── */
select option {
  background: #1e2a3a;
  color: #f1f5f9;
}
</style>
