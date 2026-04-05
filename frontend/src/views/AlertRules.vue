<template>
  <div class="alert-rules-page">
    <!-- ── Page header ──────────────────────────────────────────────────── -->
    <div class="page-header">
      <div class="page-header-left">
        <h2>Alerts &amp; Rules</h2>
        <p class="text-muted">Proactive monitoring and alerting for your infrastructure</p>
      </div>
      <div class="page-header-right">
        <span v-if="activeTab === 'active'" class="refresh-countdown">
          Auto-refresh in {{ refreshCountdown }}s
        </span>
        <button class="btn btn-secondary" @click="refresh" :disabled="loading">
          <span class="btn-icon">&#8635;</span>
          {{ loading ? 'Refreshing...' : 'Refresh' }}
        </button>
        <button v-if="activeTab === 'rules'" class="btn btn-primary" @click="openCreateModal">
          + Create Rule
        </button>
      </div>
    </div>

    <!-- ── Tabs ─────────────────────────────────────────────────────────── -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
        <span v-if="tab.id === 'active' && activeAlerts.length > 0" class="tab-badge tab-badge-red">
          {{ activeAlerts.length }}
        </span>
        <span v-else-if="tab.id === 'rules'" class="tab-badge tab-badge-gray">
          {{ rules.length }}
        </span>
      </button>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- TAB: Active Alerts                                                 -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'active'" class="tab-content">
      <!-- Filters + bulk actions -->
      <div class="toolbar">
        <div class="toolbar-left">
          <select v-model="activeFilters.severity" class="filter-select" aria-label="Filter by severity">
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
          <select v-model="activeFilters.acked" class="filter-select" aria-label="Filter by acknowledgement status">
            <option value="">All statuses</option>
            <option value="unacked">Unacknowledged</option>
            <option value="acked">Acknowledged</option>
          </select>
        </div>
        <div class="toolbar-right">
          <button
            v-if="unackedAlerts.length > 0"
            class="btn btn-secondary btn-sm"
            @click="acknowledgeAll"
            :disabled="dismissingAll"
          >
            {{ dismissingAll ? 'Acknowledging...' : `Acknowledge All (${unackedAlerts.length})` }}
          </button>
        </div>
      </div>

      <div v-if="loadingActive" class="loading-state">
        <div class="spinner"></div>
        Loading active alerts...
      </div>

      <div v-else-if="filteredActiveAlerts.length === 0" class="empty-state">
        <div class="empty-icon">&#10003;</div>
        <div class="empty-title">No alerts match your filters</div>
        <div class="empty-sub">
          {{ activeAlerts.length === 0 ? 'Your infrastructure looks healthy.' : 'Try adjusting the filters above.' }}
        </div>
      </div>

      <div v-else class="alert-list">
        <div
          v-for="alert in filteredActiveAlerts"
          :key="alert.id"
          class="alert-item"
          :class="`alert-${alert.severity}`"
        >
          <div class="alert-severity-bar"></div>
          <div class="alert-content">
            <div class="alert-top">
              <span class="severity-badge" :class="`sev-${alert.severity}`">
                {{ alert.severity }}
              </span>
              <span class="alert-title">{{ alert.title }}</span>
              <span v-if="alert.acknowledged" class="ack-pill">Acknowledged</span>
            </div>
            <div class="alert-message">{{ alert.message }}</div>
            <div class="alert-meta">
              <span class="alert-time" :title="formatTimestampFull(alert.fired_at)">
                {{ relativeTime(alert.fired_at) }}
              </span>
              <span v-if="alert.rule_key" class="alert-key">{{ alert.rule_key }}</span>
              <span v-if="alert.acknowledged && alert.acknowledged_at" class="ack-time">
                Acked {{ relativeTime(alert.acknowledged_at) }}
              </span>
            </div>
          </div>
          <div class="alert-actions">
            <button
              v-if="!alert.acknowledged"
              class="btn btn-sm btn-secondary"
              @click="acknowledgeAlert(alert)"
              :disabled="alert._acking"
            >
              {{ alert._acking ? '...' : 'Acknowledge' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- TAB: Alert Rules                                                   -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'rules'" class="tab-content">
      <div v-if="loadingRules" class="loading-state">
        <div class="spinner"></div>
        Loading rules...
      </div>

      <div v-else-if="rules.length === 0" class="empty-state">
        <div class="empty-icon">&#9998;</div>
        <div class="empty-title">No alert rules configured</div>
        <div class="empty-sub">Click "Create Rule" to add your first custom alert rule.</div>
      </div>

      <div v-else class="rules-table-wrap">
        <table class="data-table">
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
              <td>
                <span class="type-badge">{{ ruleTypeLabel(rule.rule_type) }}</span>
              </td>
              <td>
                {{ rule.threshold != null ? rule.threshold + ruleThresholdUnit(rule.rule_type) : '—' }}
              </td>
              <td class="col-muted">{{ ruleScope(rule) }}</td>
              <td class="notif-cell">
                <span v-if="rule.notify_in_app" class="notif-badge notif-inapp" title="In-app">In-app</span>
                <span v-if="rule.notify_webhook" class="notif-badge notif-webhook" title="Webhook">Webhook</span>
                <span v-if="rule.notify_slack" class="notif-badge notif-slack" title="Slack">Slack</span>
                <span v-if="!rule.notify_in_app && !rule.notify_webhook && !rule.notify_slack" class="col-muted">None</span>
              </td>
              <td>{{ rule.cooldown_minutes }}m</td>
              <td class="col-muted">
                <span :title="rule.last_fired_at ? formatTimestampFull(rule.last_fired_at) : ''">
                  {{ rule.last_fired_at ? relativeTime(rule.last_fired_at) : 'Never' }}
                </span>
              </td>
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
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- TAB: Alert History                                                  -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'history'" class="tab-content">
      <!-- Filters -->
      <div class="toolbar">
        <div class="toolbar-left">
          <select v-model="historyFilters.days" @change="historyFilters.page = 1; loadHistory()" class="filter-select" aria-label="Filter by date range">
            <option :value="1">Last 24h</option>
            <option :value="3">Last 3 days</option>
            <option :value="7">Last 7 days</option>
            <option :value="14">Last 14 days</option>
            <option :value="30">Last 30 days</option>
          </select>
          <select v-model="historyFilters.severity" @change="historyFilters.page = 1; loadHistory()" class="filter-select" aria-label="Filter by severity">
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
          <input
            v-model="historyFilters.rule_key"
            @change="historyFilters.page = 1; loadHistory()"
            class="filter-input"
            placeholder="Filter by rule key..."
            aria-label="Filter by rule key"
          />
        </div>
        <div class="toolbar-right">
          <span class="total-label">{{ history.total }} events</span>
        </div>
      </div>

      <div v-if="loadingHistory" class="loading-state">
        <div class="spinner"></div>
        Loading history...
      </div>

      <div v-else-if="history.items.length === 0" class="empty-state">
        <div class="empty-icon">&#128200;</div>
        <div class="empty-title">No events in this range</div>
        <div class="empty-sub">Try expanding the date range or clearing severity filters.</div>
      </div>

      <div v-else>
        <table class="data-table">
          <thead>
            <tr>
              <th>Fired At</th>
              <th>Severity</th>
              <th>Title</th>
              <th>Rule</th>
              <th>Message</th>
              <th>Acknowledged</th>
              <th>Resolution</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in history.items" :key="event.id">
              <td class="col-time" :title="formatTimestampFull(event.fired_at)">
                {{ relativeTime(event.fired_at) }}
              </td>
              <td>
                <span class="severity-badge" :class="`sev-${event.severity}`">{{ event.severity }}</span>
              </td>
              <td class="col-title">{{ event.title }}</td>
              <td class="col-muted col-rule">{{ event.rule_key || '—' }}</td>
              <td class="col-message">{{ event.message }}</td>
              <td>
                <span v-if="event.acknowledged" class="badge badge-green">
                  Yes<span v-if="event.acknowledged_at" class="ack-detail"> — {{ relativeTime(event.acknowledged_at) }}</span>
                </span>
                <span v-else class="badge badge-red">No</span>
              </td>
              <td class="col-muted">
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
          <span class="page-info">
            Page {{ historyFilters.page }} of {{ Math.ceil(history.total / historyFilters.per_page) }}
          </span>
          <button
            class="btn btn-sm btn-secondary"
            :disabled="historyFilters.page * historyFilters.per_page >= history.total"
            @click="historyFilters.page++; loadHistory()"
          >
            Next
          </button>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- Create / Edit Rule Modal                                           -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div v-if="showRuleModal" class="modal-overlay" @click.self="closeModal" role="dialog" aria-modal="true" :aria-label="editingRule ? 'Edit Alert Rule' : 'Create Alert Rule'">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingRule ? 'Edit Alert Rule' : 'Create Alert Rule' }}</h3>
          <button class="modal-close" @click="closeModal" aria-label="Close dialog">&#215;</button>
        </div>

        <div class="modal-body">
          <!-- Rule name -->
          <div class="form-group">
            <label>Rule Name <span class="required">*</span></label>
            <input
              v-model="ruleForm.name"
              class="form-input"
              placeholder="e.g. High CPU on pve1"
            />
          </div>

          <!-- Rule type — radio cards -->
          <div class="form-group">
            <label>Rule Type <span class="required">*</span></label>
            <div class="rule-type-grid">
              <label
                v-for="rt in ruleTypes"
                :key="rt.value"
                class="rule-type-card"
                :class="{ selected: ruleForm.rule_type === rt.value }"
              >
                <input
                  type="radio"
                  :value="rt.value"
                  v-model="ruleForm.rule_type"
                  style="display:none"
                />
                <span class="rt-icon">{{ rt.icon }}</span>
                <span class="rt-label">{{ rt.label }}</span>
                <span class="rt-desc">{{ rt.desc }}</span>
              </label>
            </div>
          </div>

          <!-- Threshold (conditional) -->
          <div class="form-group" v-if="selectedRuleType && selectedRuleType.hasThreshold">
            <label>
              Threshold
              <span class="threshold-unit">{{ ruleThresholdUnit(ruleForm.rule_type) }}</span>
            </label>
            <input
              v-model.number="ruleForm.threshold"
              type="number"
              min="0"
              :max="selectedRuleType.thresholdMax || 100"
              step="1"
              class="form-input form-input-narrow"
              :placeholder="selectedRuleType.thresholdDefault || ''"
            />
          </div>

          <!-- Scope row -->
          <div class="form-row">
            <div class="form-group">
              <label>Host</label>
              <select v-model="ruleForm.host_id" class="form-input">
                <option :value="null">All hosts</option>
                <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>Node</label>
              <input
                v-model="ruleForm.node"
                class="form-input"
                placeholder="Leave blank for all nodes"
              />
            </div>
          </div>

          <!-- Cooldown -->
          <div class="form-group">
            <label>Cooldown (minutes)</label>
            <input
              v-model.number="ruleForm.cooldown_minutes"
              type="number"
              min="1"
              class="form-input form-input-narrow"
              placeholder="60"
            />
            <span class="form-hint">Minimum time between repeated alerts for the same condition.</span>
          </div>

          <!-- Notification channels -->
          <div class="form-section-label">Notification Channels</div>
          <div class="checkbox-row">
            <label class="checkbox-label">
              <input type="checkbox" v-model="ruleForm.notify_in_app" />
              <span class="notif-badge notif-inapp" style="margin-left:0.4rem">In-app</span>
            </label>
            <label class="checkbox-label">
              <input type="checkbox" v-model="ruleForm.notify_webhook" />
              <span class="notif-badge notif-webhook" style="margin-left:0.4rem">Webhook</span>
            </label>
            <label class="checkbox-label">
              <input type="checkbox" v-model="ruleForm.notify_slack" />
              <span class="notif-badge notif-slack" style="margin-left:0.4rem">Slack</span>
            </label>
          </div>

          <!-- Enabled toggle -->
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

const RULE_TYPES = [
  {
    value: 'node_cpu_high',
    label: 'Node CPU High',
    icon: '&#128200;',
    desc: 'CPU % threshold',
    hasThreshold: true,
    thresholdDefault: '90',
    thresholdMax: 100,
    unit: '%',
  },
  {
    value: 'node_mem_high',
    label: 'Node RAM High',
    icon: '&#129504;',
    desc: 'RAM % threshold',
    hasThreshold: true,
    thresholdDefault: '95',
    thresholdMax: 100,
    unit: '%',
  },
  {
    value: 'node_offline',
    label: 'Node Offline',
    icon: '&#128268;',
    desc: 'Node goes offline',
    hasThreshold: false,
    unit: '',
  },
  {
    value: 'node_disk_high',
    label: 'Node Disk High',
    icon: '&#128190;',
    desc: 'Disk usage %',
    hasThreshold: true,
    thresholdDefault: '85',
    thresholdMax: 100,
    unit: '%',
  },
  {
    value: 'vm_cpu_high',
    label: 'VM CPU High',
    icon: '&#9881;',
    desc: 'VM CPU % threshold',
    hasThreshold: true,
    thresholdDefault: '90',
    thresholdMax: 100,
    unit: '%',
  },
  {
    value: 'vm_down',
    label: 'VM Down',
    icon: '&#9888;',
    desc: 'VM unexpectedly stopped',
    hasThreshold: false,
    unit: '',
  },
  {
    value: 'storage_usage_high',
    label: 'Storage Usage',
    icon: '&#128452;',
    desc: 'Storage pool % full',
    hasThreshold: true,
    thresholdDefault: '85',
    thresholdMax: 100,
    unit: '%',
  },
  {
    value: 'backup_failed',
    label: 'Backup Failed',
    icon: '&#128196;',
    desc: 'Backup job failed',
    hasThreshold: false,
    unit: '',
  },
  {
    value: 'temperature_high',
    label: 'Temperature High',
    icon: '&#127777;',
    desc: 'Node temperature',
    hasThreshold: true,
    thresholdDefault: '75',
    thresholdMax: 200,
    unit: '°C',
  },
]

// Legacy rule type values supported by backend
const LEGACY_RULE_TYPES = [
  { value: 'storage_usage', label: 'Storage Usage', hasThreshold: true, unit: '%' },
  { value: 'node_cpu',      label: 'Node CPU',      hasThreshold: true, unit: '%' },
  { value: 'node_memory',   label: 'Node Memory',   hasThreshold: true, unit: '%' },
  { value: 'vm_stopped',    label: 'VM Stopped',    hasThreshold: false, unit: '' },
  { value: 'backup_failed', label: 'Backup Failed', hasThreshold: false, unit: '' },
  { value: 'login_failures',label: 'Login Failures',hasThreshold: true, unit: ' failures' },
]

const ALL_RULE_TYPES = [...RULE_TYPES, ...LEGACY_RULE_TYPES]

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
      activeTab: 'active',
      tabs: [
        { id: 'active',  label: 'Active Alerts' },
        { id: 'rules',   label: 'Alert Rules' },
        { id: 'history', label: 'Alert History' },
      ],

      loading: false,
      loadingActive: false,
      loadingRules: false,
      loadingHistory: false,
      dismissingAll: false,
      savingRule: false,

      activeAlerts: [],
      rules: [],
      hosts: [],

      activeFilters: {
        severity: '',
        acked: 'unacked',
      },

      history: { total: 0, items: [] },
      historyFilters: {
        days: 7,
        severity: '',
        rule_key: '',
        page: 1,
        per_page: 50,
      },

      showRuleModal: false,
      editingRule: null,
      ruleForm: { ...EMPTY_RULE_FORM },

      ruleTypes: RULE_TYPES,

      // Auto-refresh
      refreshInterval: null,
      countdownInterval: null,
      refreshCountdown: 30,
    }
  },

  computed: {
    filteredActiveAlerts() {
      return this.activeAlerts.filter(a => {
        if (this.activeFilters.severity && a.severity !== this.activeFilters.severity) return false
        if (this.activeFilters.acked === 'unacked' && a.acknowledged) return false
        if (this.activeFilters.acked === 'acked' && !a.acknowledged) return false
        return true
      })
    },
    unackedAlerts() {
      return this.activeAlerts.filter(a => !a.acknowledged)
    },
    selectedRuleType() {
      return RULE_TYPES.find(rt => rt.value === this.ruleForm.rule_type) || null
    },
  },

  watch: {
    activeTab(tab) {
      if (tab === 'history') this.loadHistory()
      if (tab === 'rules') this.loadRules()
    },
  },

  methods: {
    // ── Data loading ────────────────────────────────────────────────────

    async refresh() {
      this.loading = true
      const tasks = [this.loadActiveAlerts(), this.loadHosts()]
      if (this.activeTab === 'rules') tasks.push(this.loadRules())
      if (this.activeTab === 'history') tasks.push(this.loadHistory())
      try {
        await Promise.allSettled(tasks)
      } finally {
        this.loading = false
        this.resetCountdown()
      }
    },

    async loadActiveAlerts() {
      this.loadingActive = true
      try {
        const res = await api.alerts.getActive()
        // Preserve _acking flags
        const existing = {}
        this.activeAlerts.forEach(a => { existing[a.id] = a._acking })
        this.activeAlerts = (res.data || []).map(a => ({
          ...a,
          _acking: existing[a.id] || false,
        }))
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
          rule_key: this.historyFilters.rule_key || undefined,
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

    // ── Alert acknowledgement ───────────────────────────────────────────

    async acknowledgeAlert(alert) {
      alert._acking = true
      try {
        await api.alerts.acknowledgeEvent(alert.id)
        alert.acknowledged = true
        alert.acknowledged_at = new Date().toISOString()
      } catch (e) {
        console.warn('Failed to acknowledge alert:', e)
      } finally {
        alert._acking = false
      }
    },

    async acknowledgeAll() {
      if (!confirm(`Acknowledge all ${this.unackedAlerts.length} unacknowledged alerts?`)) return
      this.dismissingAll = true
      try {
        await api.alerts.dismissAll()
        const now = new Date().toISOString()
        this.activeAlerts.forEach(a => {
          a.acknowledged = true
          a.acknowledged_at = now
        })
      } catch (e) {
        console.warn('Failed to acknowledge all alerts:', e)
      } finally {
        this.dismissingAll = false
      }
    },

    // ── Rule actions ────────────────────────────────────────────────────

    async toggleRule(rule) {
      try {
        const res = await api.alerts.toggleRule(rule.id)
        rule.enabled = res.data.enabled
      } catch (e) {
        console.warn('Failed to toggle rule:', e)
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

    // ── Auto-refresh countdown ──────────────────────────────────────────

    resetCountdown() {
      this.refreshCountdown = 30
    },

    startCountdown() {
      if (this.countdownInterval) clearInterval(this.countdownInterval)
      this.countdownInterval = setInterval(() => {
        this.refreshCountdown--
        if (this.refreshCountdown <= 0) {
          this.refreshCountdown = 30
        }
      }, 1000)
    },

    // ── Helpers ─────────────────────────────────────────────────────────

    ruleTypeLabel(type) {
      const found = ALL_RULE_TYPES.find(rt => rt.value === type)
      return found ? found.label : type
    },

    ruleThresholdUnit(type) {
      const found = ALL_RULE_TYPES.find(rt => rt.value === type)
      return found ? (found.unit || '') : ''
    },

    ruleScope(rule) {
      const parts = []
      if (rule.host_id) {
        const host = this.hosts.find(h => h.id === rule.host_id)
        parts.push(host ? host.name : `Host ${rule.host_id}`)
      } else {
        parts.push('All hosts')
      }
      if (rule.node) parts.push(rule.node)
      return parts.join(' / ')
    },

    relativeTime(ts) {
      if (!ts) return '—'
      const d = new Date(ts)
      if (isNaN(d.getTime())) return ts
      const seconds = Math.floor((Date.now() - d.getTime()) / 1000)
      if (seconds < 60) return `${seconds}s ago`
      const minutes = Math.floor(seconds / 60)
      if (minutes < 60) return `${minutes}m ago`
      const hours = Math.floor(minutes / 60)
      if (hours < 24) return `${hours}h ago`
      const days = Math.floor(hours / 24)
      return `${days}d ago`
    },

    formatTimestampFull(ts) {
      if (!ts) return ''
      const d = new Date(ts)
      return isNaN(d.getTime()) ? ts : d.toLocaleString()
    },
  },

  async mounted() {
    await this.refresh()
    // Auto-refresh active alerts every 30s
    this.refreshInterval = setInterval(() => {
      this.loadActiveAlerts()
      this.resetCountdown()
    }, 30000)
    this.startCountdown()
  },

  beforeUnmount() {
    if (this.refreshInterval) clearInterval(this.refreshInterval)
    if (this.countdownInterval) clearInterval(this.countdownInterval)
  },
}
</script>

<style scoped>
/* ── Layout ────────────────────────────────────────────────────────────── */
.alert-rules-page {
  padding: 1.5rem;
  max-width: 1400px;
}

/* ── Page header ──────────────────────────────────────────────────────── */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1.25rem;
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
  color: var(--text-muted, #8fa3b8);
  font-size: 0.875rem;
  margin: 0;
}

.refresh-countdown {
  font-size: 0.78rem;
  color: var(--text-muted, #8fa3b8);
}

/* ── Tab bar ──────────────────────────────────────────────────────────── */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.08));
  margin-bottom: 1.25rem;
}

.tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 0.6rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-muted, #8fa3b8);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: color 0.15s, border-color 0.15s;
  margin-bottom: -1px;
}

.tab-btn:focus-visible {
  outline: 2px solid var(--accent-color, #3b82f6);
  outline-offset: 2px;
  border-radius: 3px;
}

.tab-btn:hover {
  color: var(--text-primary, #f1f5f9);
}

.tab-btn.active {
  color: #60a5fa;
  border-bottom-color: #3b82f6;
}

.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.1rem 0.4rem;
  border-radius: 0.8rem;
  font-size: 0.7rem;
  font-weight: 700;
  min-width: 1.2rem;
}

.tab-badge-red  { background: rgba(239,68,68,0.18);   color: #f87171; }
.tab-badge-gray { background: rgba(148,163,184,0.12); color: #94a3b8; }

/* ── Tab content wrapper ──────────────────────────────────────────────── */
.tab-content {
  background: var(--card-bg, #1e2a3a);
  border: 1px solid var(--border-color, rgba(255,255,255,0.08));
  border-radius: 0.625rem;
  overflow: hidden;
}

/* ── Toolbar ──────────────────────────────────────────────────────────── */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.06));
  flex-wrap: wrap;
  gap: 0.5rem;
  background: rgba(255,255,255,0.02);
}

.toolbar-left {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}

.toolbar-right {
  display: flex;
  gap: 0.5rem;
  align-items: center;
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

.filter-input {
  background: rgba(255,255,255,0.07);
  border: 1px solid var(--border-color, rgba(255,255,255,0.12));
  border-radius: 0.35rem;
  padding: 0.3rem 0.6rem;
  font-size: 0.8rem;
  color: var(--text-primary, #f1f5f9);
  width: 180px;
}

.filter-input:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 0;
  border-color: #3b82f6;
}

.filter-input:focus {
  border-color: #3b82f6;
}

.total-label {
  font-size: 0.8rem;
  color: var(--text-muted, #8fa3b8);
}

/* ── Loading / empty states ───────────────────────────────────────────── */
.loading-state {
  padding: 3rem 1.25rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  color: var(--text-muted, #8fa3b8);
  font-size: 0.875rem;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(255,255,255,0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  padding: 3rem 1.25rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
}

.empty-icon {
  font-size: 2rem;
  opacity: 0.4;
  margin-bottom: 0.25rem;
}

.empty-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
  opacity: 0.8;
}

.empty-sub {
  font-size: 0.82rem;
  color: var(--text-muted, #8fa3b8);
}

/* ── Active alert list ────────────────────────────────────────────────── */
.alert-list {
  padding: 0.75rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.alert-item {
  display: flex;
  align-items: stretch;
  border: 1px solid var(--border-color, rgba(255,255,255,0.07));
  border-radius: 0.5rem;
  overflow: hidden;
  background: rgba(255,255,255,0.02);
  transition: background 0.15s;
}

.alert-item:hover {
  background: rgba(255,255,255,0.04);
}

.alert-critical .alert-severity-bar { background: #ef4444; }
.alert-warning  .alert-severity-bar { background: #f59e0b; }
.alert-info     .alert-severity-bar { background: #3b82f6; }

.alert-severity-bar {
  width: 3px;
  flex-shrink: 0;
}

.alert-content {
  flex: 1;
  padding: 0.7rem 0.75rem;
  min-width: 0;
}

.alert-top {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.3rem;
}

.alert-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.ack-pill {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  background: rgba(34,197,94,0.12);
  color: #4ade80;
  border-radius: 0.3rem;
  font-size: 0.7rem;
  font-weight: 600;
}

.alert-message {
  font-size: 0.81rem;
  color: var(--text-muted, #9aabb8);
  line-height: 1.5;
  margin-bottom: 0.35rem;
  word-break: break-word;
}

.alert-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.73rem;
  color: var(--text-muted, #8fa3b8);
  flex-wrap: wrap;
}

.alert-key {
  font-family: monospace;
  background: rgba(255,255,255,0.05);
  padding: 0.05rem 0.3rem;
  border-radius: 0.2rem;
}

.ack-time {
  color: #4ade80;
  opacity: 0.8;
}

.alert-actions {
  padding: 0.65rem 0.75rem;
  display: flex;
  align-items: flex-start;
  flex-shrink: 0;
}

/* ── Shared data table ────────────────────────────────────────────────── */
.rules-table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.845rem;
}

.data-table th {
  padding: 0.6rem 1rem;
  text-align: left;
  font-size: 0.71rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #8fa3b8);
  background: rgba(255,255,255,0.03);
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.08));
  white-space: nowrap;
}

.data-table td {
  padding: 0.65rem 1rem;
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.05));
  color: var(--text-primary, #f1f5f9);
  vertical-align: middle;
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.data-table tbody tr:hover td {
  background: rgba(255,255,255,0.025);
}

.row-disabled td {
  opacity: 0.45;
}

.rule-name { font-weight: 500; }
.col-muted { color: var(--text-muted, #8fa3b8); font-size: 0.81rem; }
.col-time  { white-space: nowrap; }
.col-title { font-weight: 500; max-width: 240px; }
.col-message { max-width: 320px; font-size: 0.78rem; color: var(--text-muted, #9aabb8); word-break: break-word; }
.col-rule { font-family: monospace; font-size: 0.75rem; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── Type badge ───────────────────────────────────────────────────────── */
.type-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  background: rgba(59,130,246,0.12);
  color: #60a5fa;
  font-size: 0.73rem;
  font-weight: 500;
  white-space: nowrap;
}

/* ── Notification badges ──────────────────────────────────────────────── */
.notif-cell {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
  align-items: center;
}

.notif-badge {
  display: inline-block;
  padding: 0.12rem 0.4rem;
  border-radius: 0.25rem;
  font-size: 0.7rem;
  font-weight: 600;
}

.notif-inapp   { background: rgba(59,130,246,0.14); color: #60a5fa; }
.notif-webhook { background: rgba(139,92,246,0.14); color: #a78bfa; }
.notif-slack   { background: rgba(34,197,94,0.12);  color: #4ade80; }

/* ── Severity badge ───────────────────────────────────────────────────── */
.severity-badge {
  display: inline-block;
  padding: 0.12rem 0.42rem;
  border-radius: 0.25rem;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  white-space: nowrap;
}
.sev-critical { background: rgba(239,68,68,0.15);  color: #f87171; }
.sev-warning  { background: rgba(245,158,11,0.15); color: #fbbf24; }
.sev-info     { background: rgba(59,130,246,0.15); color: #60a5fa; }

/* ── General badges ───────────────────────────────────────────────────── */
.badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.3rem;
  font-size: 0.75rem;
  font-weight: 600;
}
.badge-green { background: rgba(34,197,94,0.12);  color: #4ade80; }
.badge-red   { background: rgba(239,68,68,0.12);  color: #f87171; }

.ack-detail { font-weight: 400; opacity: 0.75; font-size: 0.7rem; }

/* ── Pagination ───────────────────────────────────────────────────────── */
.pagination {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1.25rem;
  justify-content: center;
  border-top: 1px solid var(--border-color, rgba(255,255,255,0.06));
}

.page-info {
  font-size: 0.83rem;
  color: var(--text-muted, #8fa3b8);
}

/* ── Row actions ──────────────────────────────────────────────────────── */
.row-actions { display: flex; gap: 0.4rem; white-space: nowrap; }

/* ── Toggle switch ────────────────────────────────────────────────────── */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 38px;
  height: 20px;
  cursor: pointer;
}

.toggle-switch input { opacity: 0; width: 0; height: 0; }

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

.toggle-switch input:checked + .toggle-slider { background: #3b82f6; }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(18px); }

.toggle-switch input:focus-visible + .toggle-slider {
  outline: 2px solid var(--accent-color, #3b82f6);
  outline-offset: 2px;
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
  max-width: 680px;
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
  position: sticky;
  top: 0;
  background: var(--card-bg, #1e2a3a);
  z-index: 1;
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
  color: var(--text-muted, #8fa3b8);
  font-size: 1.4rem;
  cursor: pointer;
  padding: 0.2rem;
  line-height: 1;
  border-radius: 0.25rem;
}
.modal-close:hover { color: var(--text-primary, #f1f5f9); }
.modal-close:focus-visible {
  outline: 2px solid var(--accent-color, #3b82f6);
  outline-offset: 2px;
}

.modal-body {
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color, rgba(255,255,255,0.08));
  position: sticky;
  bottom: 0;
  background: var(--card-bg, #1e2a3a);
}

/* ── Rule type grid ───────────────────────────────────────────────────── */
.rule-type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.6rem;
}

.rule-type-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  padding: 0.75rem 0.5rem;
  border: 1px solid var(--border-color, rgba(255,255,255,0.1));
  border-radius: 0.5rem;
  cursor: pointer;
  text-align: center;
  transition: border-color 0.15s, background 0.15s;
  background: rgba(255,255,255,0.03);
  user-select: none;
}

.rule-type-card:hover {
  border-color: rgba(59,130,246,0.4);
  background: rgba(59,130,246,0.06);
}

.rule-type-card.selected {
  border-color: #3b82f6;
  background: rgba(59,130,246,0.12);
}

.rt-icon {
  font-size: 1.3rem;
  line-height: 1;
}

.rt-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
  line-height: 1.2;
}

.rt-desc {
  font-size: 0.68rem;
  color: var(--text-muted, #8fa3b8);
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
  color: var(--text-secondary, #94a3b8);
}

.required { color: #f87171; }

.threshold-unit {
  font-weight: 400;
  color: var(--text-muted, #8fa3b8);
  margin-left: 0.25rem;
}

.form-hint {
  font-size: 0.75rem;
  color: var(--text-muted, #8fa3b8);
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

.form-input:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 0;
  border-color: #3b82f6;
  background: rgba(255,255,255,0.1);
}

.form-input:focus {
  border-color: #3b82f6;
  background: rgba(255,255,255,0.1);
}

.form-input-narrow { max-width: 150px; }

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-section-label {
  font-size: 0.71rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, #8fa3b8);
  border-top: 1px solid var(--border-color, rgba(255,255,255,0.08));
  padding-top: 0.75rem;
}

.checkbox-row {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  align-items: center;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--text-primary, #f1f5f9);
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
  gap: 0.3rem;
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

.btn-danger { background: rgba(239,68,68,0.12); color: #f87171; border: 1px solid rgba(239,68,68,0.22); }
.btn-danger:hover:not(:disabled) { background: rgba(239,68,68,0.22); }

.btn-sm { padding: 0.3rem 0.7rem; font-size: 0.8rem; }

.btn-icon { font-size: 1rem; line-height: 1; }

/* ── Placeholder contrast ───────────────────────────────────────────── */
.filter-input::placeholder,
.form-input::placeholder {
  color: #8fa3b8;
  opacity: 1;
}

/* ── Select option dark mode fix ─────────────────────────────────────── */
select option {
  background: #1e2a3a;
  color: #f1f5f9;
}

/* ── Button focus-visible ────────────────────────────────────────────── */
.btn:focus-visible {
  outline: 2px solid var(--accent-color, #3b82f6);
  outline-offset: 2px;
}

.filter-select:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 0;
}
</style>
