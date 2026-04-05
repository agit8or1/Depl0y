<template>
  <div class="integrations-view">
    <div class="page-header">
      <h1>Integrations</h1>
      <p class="subtitle">Configure external integrations, webhooks, and monitoring hooks</p>
    </div>

    <!-- Tab bar -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        {{ tab.label }}
      </button>
    </div>

    <!-- ── Slack Tab ── -->
    <div v-if="activeTab === 'slack'" class="tab-panel">
      <div class="section-card">
        <div class="section-header">
          <h2>Slack Integration</h2>
          <span class="badge" :class="slack.configured ? 'badge-green' : 'badge-gray'">
            {{ slack.configured ? 'Configured' : 'Not configured' }}
          </span>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label>Incoming Webhook URL</label>
            <input
              v-model="slack.webhook_url"
              type="password"
              placeholder="https://hooks.slack.com/services/..."
              class="form-input"
            />
            <p class="form-hint">
              Create one at <a href="https://api.slack.com/messaging/webhooks" target="_blank" rel="noopener">api.slack.com/messaging/webhooks</a>
            </p>
          </div>
          <div class="form-group">
            <label>Default Channel</label>
            <input
              v-model="slack.channel"
              type="text"
              placeholder="#alerts"
              class="form-input"
            />
          </div>
        </div>

        <div class="form-group">
          <label>Notify on events</label>
          <div class="checkbox-grid">
            <label v-for="ev in slackEventOptions" :key="ev.value" class="checkbox-item">
              <input type="checkbox" :value="ev.value" v-model="slack.events" />
              <span>{{ ev.label }}</span>
            </label>
          </div>
        </div>

        <!-- Message format preview -->
        <div class="preview-box">
          <div class="preview-label">Message format preview</div>
          <div class="preview-content">
            <div class="slack-preview">
              <span class="slack-icon">:arrow_forward:</span>
              <div class="slack-text">
                <strong>VM <em>101</em> on <code>pve1</code> started</strong> by
                <code>admin</code>
              </div>
            </div>
            <div class="slack-preview">
              <span class="slack-icon">:bust_in_silhouette:</span>
              <div class="slack-text">
                <strong>User <em>admin</em> logged in</strong> from
                <code>192.168.1.10</code>
              </div>
            </div>
          </div>
        </div>

        <div class="action-row">
          <button class="btn btn-secondary" :disabled="slackTesting" @click="testSlack">
            <span v-if="slackTesting">Testing...</span>
            <span v-else>Send test message</span>
          </button>
          <button class="btn btn-primary" :disabled="slackSaving" @click="saveSlack">
            <span v-if="slackSaving">Saving...</span>
            <span v-else>Save settings</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ── PagerDuty Tab ── -->
    <div v-if="activeTab === 'pagerduty'" class="tab-panel">
      <div class="section-card">
        <div class="section-header">
          <h2>PagerDuty Integration</h2>
          <span class="badge" :class="pagerduty.integration_key ? 'badge-green' : 'badge-gray'">
            {{ pagerduty.integration_key ? 'Configured' : 'Not configured' }}
          </span>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label>Integration Key (Events API v2)</label>
            <input
              v-model="pagerduty.integration_key"
              type="password"
              placeholder="xxxxxxxxxxxxxxxxxxxx"
              class="form-input"
            />
            <p class="form-hint">Found in your PagerDuty service's integrations tab.</p>
          </div>
          <div class="form-group">
            <label>Routing Key</label>
            <input
              v-model="pagerduty.routing_key"
              type="password"
              placeholder="Optional — for event orchestration"
              class="form-input"
            />
          </div>
        </div>

        <div class="form-group">
          <label>Alert on</label>
          <div class="checkbox-grid">
            <label class="checkbox-item">
              <input type="checkbox" v-model="pagerduty.alert_node_offline" />
              <span>Node offline</span>
            </label>
            <label class="checkbox-item">
              <input type="checkbox" v-model="pagerduty.alert_storage_critical" />
              <span>Storage &gt;90% full</span>
            </label>
            <label class="checkbox-item">
              <input type="checkbox" v-model="pagerduty.alert_backup_failure" />
              <span>Backup failure</span>
            </label>
          </div>
        </div>

        <div class="form-group">
          <label>Severity mapping</label>
          <div class="severity-grid">
            <div class="severity-row">
              <span class="severity-label">VM stopped</span>
              <select v-model="pagerduty.severity_vm_stopped" class="form-select">
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div class="severity-row">
              <span class="severity-label">Node offline</span>
              <select v-model="pagerduty.severity_node_offline" class="form-select">
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
        </div>

        <div class="action-row">
          <button class="btn btn-primary" :disabled="pdSaving" @click="savePagerDuty">
            <span v-if="pdSaving">Saving...</span>
            <span v-else>Save settings</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ── Monitoring / Grafana Tab ── -->
    <div v-if="activeTab === 'monitoring'" class="tab-panel">
      <div class="section-card">
        <h2>Prometheus Metrics</h2>
        <p class="info-text">
          Depl0y exposes a JSON metrics endpoint. Point Prometheus at it using the
          <code>json_exporter</code> sidecar, or scrape it with a custom job.
        </p>
        <div class="endpoint-box">
          <code>GET {{ apiBase }}/api/v1/system/metrics</code>
          <button class="btn-copy" @click="copyMetricsUrl">Copy</button>
        </div>
        <div class="metrics-sample">
          <pre>{{metricsExample}}</pre>
        </div>
      </div>

      <div class="section-card">
        <div class="section-header">
          <h2>InfluxDB Push</h2>
          <span class="badge" :class="influxdb.host ? 'badge-green' : 'badge-gray'">
            {{ influxdb.host ? 'Configured' : 'Not configured' }}
          </span>
        </div>
        <p class="info-text">Depl0y will push system metrics to InfluxDB at the configured interval.</p>

        <div class="form-grid">
          <div class="form-group">
            <label>InfluxDB Host</label>
            <input
              v-model="influxdb.host"
              type="text"
              placeholder="http://influxdb:8086"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label>Database / Bucket</label>
            <input
              v-model="influxdb.database"
              type="text"
              placeholder="depl0y"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label>Token</label>
            <input
              v-model="influxdb.token"
              type="password"
              placeholder="InfluxDB API token"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label>Push interval (seconds)</label>
            <input
              v-model.number="influxdb.interval_seconds"
              type="number"
              min="10"
              max="3600"
              class="form-input"
            />
          </div>
        </div>

        <div class="action-row">
          <button class="btn btn-primary" :disabled="influxSaving" @click="saveInfluxDB">
            <span v-if="influxSaving">Saving...</span>
            <span v-else>Save settings</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ── Custom Webhooks Tab ── -->
    <div v-if="activeTab === 'webhooks'" class="tab-panel">
      <div class="section-card">
        <div class="section-header">
          <h2>Custom Webhooks</h2>
          <button class="btn btn-primary btn-sm" @click="showWebhookForm = true">
            + Add webhook
          </button>
        </div>

        <!-- Add/Edit form -->
        <div v-if="showWebhookForm" class="webhook-form">
          <h3>{{ editingWebhook ? 'Edit' : 'New' }} Webhook</h3>
          <div class="form-grid">
            <div class="form-group">
              <label>Name</label>
              <input v-model="webhookForm.name" type="text" placeholder="My webhook" class="form-input" />
            </div>
            <div class="form-group">
              <label>URL</label>
              <input v-model="webhookForm.url" type="text" placeholder="https://example.com/hook" class="form-input" />
            </div>
            <div class="form-group">
              <label>Secret (optional, for HMAC-SHA256 signing)</label>
              <input v-model="webhookForm.secret" type="password" class="form-input" />
            </div>
          </div>
          <div class="form-group">
            <label>Events</label>
            <div class="checkbox-grid">
              <label v-for="ev in webhookEventOptions" :key="ev.value" class="checkbox-item">
                <input type="checkbox" :value="ev.value" v-model="webhookForm.events" />
                <span>{{ ev.label }}</span>
              </label>
            </div>
          </div>
          <div class="form-group">
            <label class="checkbox-item">
              <input type="checkbox" v-model="webhookForm.enabled" />
              <span>Enabled</span>
            </label>
          </div>
          <div class="action-row">
            <button class="btn btn-secondary" @click="cancelWebhookForm">Cancel</button>
            <button class="btn btn-primary" :disabled="webhookSaving" @click="saveWebhook">
              <span v-if="webhookSaving">Saving...</span>
              <span v-else>{{ editingWebhook ? 'Update' : 'Create' }}</span>
            </button>
          </div>
        </div>

        <!-- Webhook list -->
        <div v-if="webhooksLoading" class="loading-text">Loading webhooks...</div>
        <div v-else-if="webhooks.length === 0 && !showWebhookForm" class="empty-state">
          No webhooks configured. Click "+ Add webhook" to create one.
        </div>
        <div v-else class="webhook-list">
          <div v-for="hook in webhooks" :key="hook.id" class="webhook-item">
            <div class="webhook-header">
              <div class="webhook-name">
                <span class="status-dot" :class="hook.enabled ? 'dot-green' : 'dot-gray'"></span>
                <strong>{{ hook.name }}</strong>
              </div>
              <div class="webhook-actions">
                <button class="btn-icon" title="Test" @click="testWebhook(hook)">
                  ▶
                </button>
                <button class="btn-icon" title="Edit" @click="editWebhook(hook)">
                  ✏️
                </button>
                <button class="btn-icon btn-danger" title="Delete" @click="deleteWebhook(hook)">
                  🗑️
                </button>
              </div>
            </div>
            <div class="webhook-url">{{ hook.url }}</div>
            <div class="webhook-events">
              <span v-for="ev in hook.events" :key="ev" class="event-tag">{{ ev }}</span>
            </div>

            <!-- Delivery log -->
            <div v-if="hook.delivery_log && hook.delivery_log.length > 0" class="delivery-log">
              <div class="delivery-log-title">Recent deliveries</div>
              <div
                v-for="d in hook.delivery_log.slice(0, 5)"
                :key="d.id"
                class="delivery-row"
                :class="d.success ? 'delivery-ok' : 'delivery-fail'"
              >
                <span class="delivery-event">{{ d.event }}</span>
                <span class="delivery-code">HTTP {{ d.status_code || '—' }}</span>
                <span class="delivery-time">{{ formatDate(d.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── OIDC / SSO Tab ── -->
    <div v-if="activeTab === 'oidc'" class="tab-panel">
      <div class="section-card">
        <div class="section-header">
          <h2>OIDC / SSO</h2>
          <span class="badge badge-yellow">Configuration preview</span>
        </div>

        <div class="coming-soon-banner">
          <span class="cs-icon">🔐</span>
          <div>
            <strong>Full OIDC authentication flow is coming soon.</strong>
            <p>You can save your provider configuration here. The actual redirect-based login flow requires additional backend changes and is not yet active.</p>
          </div>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label>Provider / Issuer URL</label>
            <input
              v-model="oidc.provider_url"
              type="text"
              placeholder="https://accounts.google.com"
              class="form-input"
            />
            <p class="form-hint">The OpenID Connect discovery endpoint base URL.</p>
          </div>
          <div class="form-group">
            <label>Client ID</label>
            <input
              v-model="oidc.client_id"
              type="text"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label>Client Secret</label>
            <input
              v-model="oidc.client_secret"
              type="password"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label>Scopes</label>
            <input
              v-model="oidc.scopes"
              type="text"
              placeholder="openid email profile"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label>Callback URL</label>
            <input
              v-model="oidc.callback_url"
              type="text"
              :placeholder="`${apiBase}/auth/callback`"
              class="form-input"
            />
          </div>
        </div>

        <div class="form-group">
          <label class="checkbox-item">
            <input type="checkbox" v-model="oidc.enabled" />
            <span>Enable OIDC login button on login page (UI only for now)</span>
          </label>
        </div>

        <div class="action-row">
          <button class="btn btn-primary" :disabled="oidcSaving" @click="saveOIDC">
            <span v-if="oidcSaving">Saving...</span>
            <span v-else>Save configuration</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'Integrations',
  setup() {
    const toast = useToast()

    const activeTab = ref('slack')

    const tabs = [
      { id: 'slack',      label: 'Slack',           icon: '💬' },
      { id: 'pagerduty',  label: 'PagerDuty',        icon: '🔔' },
      { id: 'monitoring', label: 'Grafana / Metrics', icon: '📊' },
      { id: 'webhooks',   label: 'Custom Webhooks',   icon: '🔗' },
      { id: 'oidc',       label: 'OIDC / SSO',        icon: '🔐' },
    ]

    // ── Slack ──────────────────────────────────────────────────────────────
    const slack = ref({ webhook_url: '', channel: '', events: [], configured: false })
    const slackSaving = ref(false)
    const slackTesting = ref(false)

    const slackEventOptions = [
      { value: 'vm.started',      label: 'VM started' },
      { value: 'vm.stopped',      label: 'VM stopped' },
      { value: 'vm.shutdown',     label: 'VM shutdown' },
      { value: 'backup.complete', label: 'Backup complete' },
      { value: 'backup.failed',   label: 'Backup failed' },
      { value: 'user.login',      label: 'User login' },
      { value: 'task.failed',     label: 'Task failed' },
    ]

    const saveSlack = async () => {
      slackSaving.value = true
      try {
        await api.integrations.saveSlack({
          webhook_url: slack.value.webhook_url,
          channel: slack.value.channel,
          events: slack.value.events,
        })
        toast.success('Slack settings saved')
        await loadSettings()
      } catch (e) {
        toast.error('Failed to save Slack settings')
      } finally {
        slackSaving.value = false
      }
    }

    const testSlack = async () => {
      slackTesting.value = true
      try {
        await api.integrations.testSlack()
        toast.success('Test message sent to Slack!')
      } catch (e) {
        const msg = e.response?.data?.detail || 'Failed to send test message'
        toast.error(msg)
      } finally {
        slackTesting.value = false
      }
    }

    // ── PagerDuty ──────────────────────────────────────────────────────────
    const pagerduty = ref({
      integration_key: '',
      routing_key: '',
      alert_node_offline: true,
      alert_storage_critical: true,
      alert_backup_failure: true,
      severity_vm_stopped: 'warning',
      severity_node_offline: 'critical',
    })
    const pdSaving = ref(false)

    const savePagerDuty = async () => {
      pdSaving.value = true
      try {
        await api.integrations.savePagerDuty(pagerduty.value)
        toast.success('PagerDuty settings saved')
      } catch (e) {
        toast.error('Failed to save PagerDuty settings')
      } finally {
        pdSaving.value = false
      }
    }

    // ── InfluxDB ───────────────────────────────────────────────────────────
    const influxdb = ref({ host: '', database: '', token: '', interval_seconds: 60 })
    const influxSaving = ref(false)

    const saveInfluxDB = async () => {
      influxSaving.value = true
      try {
        await api.integrations.saveInfluxDB(influxdb.value)
        toast.success('InfluxDB settings saved')
      } catch (e) {
        toast.error('Failed to save InfluxDB settings')
      } finally {
        influxSaving.value = false
      }
    }

    const apiBase = computed(() => window.location.origin)

    const metricsExample = `{
  "depl0y_users_total": 5,
  "depl0y_proxmox_hosts_total": 2,
  "depl0y_api_keys_total": 3,
  "depl0y_requests_total": 14720,
  "depl0y_uptime_seconds": 86400
}`

    const copyMetricsUrl = () => {
      const url = `${window.location.origin}/api/v1/system/metrics`
      navigator.clipboard.writeText(url).then(() => toast.success('Copied!'))
    }

    // ── Webhooks ───────────────────────────────────────────────────────────
    const webhooks = ref([])
    const webhooksLoading = ref(false)
    const showWebhookForm = ref(false)
    const editingWebhook = ref(null)
    const webhookSaving = ref(false)

    const webhookFormDefaults = () => ({
      name: '',
      url: '',
      secret: '',
      events: [],
      enabled: true,
    })
    const webhookForm = ref(webhookFormDefaults())

    const webhookEventOptions = [
      { value: 'vm.started',      label: 'VM started' },
      { value: 'vm.stopped',      label: 'VM stopped' },
      { value: 'vm.shutdown',     label: 'VM shutdown' },
      { value: 'vm.create',       label: 'VM created' },
      { value: 'vm.delete',       label: 'VM deleted' },
      { value: 'vm.error',        label: 'VM error' },
      { value: 'backup.complete', label: 'Backup complete' },
      { value: 'backup.failed',   label: 'Backup failed' },
      { value: 'user.login',      label: 'User login' },
      { value: 'task.failed',     label: 'Task failed' },
    ]

    const loadWebhooks = async () => {
      webhooksLoading.value = true
      try {
        const r = await api.notifications.listWebhooks()
        webhooks.value = r.data.webhooks || []
      } catch (e) {
        toast.error('Failed to load webhooks')
      } finally {
        webhooksLoading.value = false
      }
    }

    const editWebhook = (hook) => {
      editingWebhook.value = hook
      webhookForm.value = {
        name: hook.name,
        url: hook.url,
        secret: '',
        events: [...(hook.events || [])],
        enabled: hook.enabled !== false,
      }
      showWebhookForm.value = true
    }

    const cancelWebhookForm = () => {
      showWebhookForm.value = false
      editingWebhook.value = null
      webhookForm.value = webhookFormDefaults()
    }

    const saveWebhook = async () => {
      if (!webhookForm.value.name || !webhookForm.value.url) {
        toast.error('Name and URL are required')
        return
      }
      webhookSaving.value = true
      try {
        if (editingWebhook.value) {
          await api.notifications.updateWebhook(editingWebhook.value.id, webhookForm.value)
          toast.success('Webhook updated')
        } else {
          await api.notifications.createWebhook(webhookForm.value)
          toast.success('Webhook created')
        }
        cancelWebhookForm()
        await loadWebhooks()
      } catch (e) {
        toast.error('Failed to save webhook')
      } finally {
        webhookSaving.value = false
      }
    }

    const testWebhook = async (hook) => {
      try {
        const r = await api.notifications.testWebhook(hook.id)
        if (r.data.success) {
          toast.success(`Test sent: HTTP ${r.data.response_code}`)
        } else {
          toast.warning(`Test sent but got HTTP ${r.data.response_code}`)
        }
        await loadWebhooks()
      } catch (e) {
        toast.error('Webhook test failed')
      }
    }

    const deleteWebhook = async (hook) => {
      if (!confirm(`Delete webhook "${hook.name}"?`)) return
      try {
        await api.notifications.deleteWebhook(hook.id)
        toast.success('Webhook deleted')
        await loadWebhooks()
      } catch (e) {
        toast.error('Failed to delete webhook')
      }
    }

    // ── OIDC ───────────────────────────────────────────────────────────────
    const oidc = ref({
      provider_url: '',
      client_id: '',
      client_secret: '',
      scopes: 'openid email profile',
      callback_url: '',
      enabled: false,
    })
    const oidcSaving = ref(false)

    const saveOIDC = async () => {
      oidcSaving.value = true
      try {
        await api.integrations.saveOIDC(oidc.value)
        toast.success('OIDC configuration saved')
      } catch (e) {
        toast.error('Failed to save OIDC configuration')
      } finally {
        oidcSaving.value = false
      }
    }

    // ── Load all settings ──────────────────────────────────────────────────
    const loadSettings = async () => {
      try {
        const r = await api.integrations.getAll()
        const d = r.data

        if (d.slack) {
          slack.value = {
            webhook_url: d.slack.webhook_url || '',
            channel: d.slack.channel || '',
            events: d.slack.events || [],
            configured: d.slack.configured || false,
          }
        }
        if (d.pagerduty && Object.keys(d.pagerduty).length > 0) {
          pagerduty.value = { ...pagerduty.value, ...d.pagerduty }
        }
        if (d.influxdb && Object.keys(d.influxdb).length > 0) {
          influxdb.value = { ...influxdb.value, ...d.influxdb }
        }
        if (d.oidc && Object.keys(d.oidc).length > 0) {
          oidc.value = { ...oidc.value, ...d.oidc }
        }
      } catch (e) {
        // Silently ignore — first load may fail if not yet configured
      }
    }

    const formatDate = (iso) => {
      if (!iso) return ''
      try {
        return new Date(iso).toLocaleString()
      } catch {
        return iso
      }
    }

    onMounted(async () => {
      await loadSettings()
      await loadWebhooks()
    })

    return {
      activeTab, tabs,
      // Slack
      slack, slackSaving, slackTesting, slackEventOptions, saveSlack, testSlack,
      // PagerDuty
      pagerduty, pdSaving, savePagerDuty,
      // InfluxDB
      influxdb, influxSaving, saveInfluxDB, apiBase, metricsExample, copyMetricsUrl,
      // Webhooks
      webhooks, webhooksLoading, showWebhookForm, editingWebhook,
      webhookForm, webhookSaving, webhookEventOptions,
      loadWebhooks, editWebhook, cancelWebhookForm, saveWebhook,
      testWebhook, deleteWebhook,
      // OIDC
      oidc, oidcSaving, saveOIDC,
      // Util
      formatDate,
    }
  }
}
</script>

<style scoped>
.integrations-view {
  padding: 1.5rem;
  max-width: 960px;
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
  color: var(--text-muted, #6b7280);
  margin: 0;
}

/* Tab bar */
.tab-bar {
  display: flex;
  gap: 0.25rem;
  border-bottom: 2px solid var(--border-color, #e5e7eb);
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.6rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  color: var(--text-muted, #6b7280);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: color 0.15s;
}

.tab-btn:hover {
  color: var(--text-primary, #111827);
}

.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.tab-icon {
  font-size: 1rem;
}

/* Cards */
.section-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.75rem;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.section-header h2 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
}

/* Badges */
.badge {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.badge-green  { background: #dcfce7; color: #166534; }
.badge-gray   { background: #f3f4f6; color: #6b7280; }
.badge-yellow { background: #fef9c3; color: #854d0e; }

/* Forms */
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary, #374151);
}

.form-input,
.form-select {
  border: 1px solid var(--border-color, #d1d5db);
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  background: var(--input-bg, #fff);
  color: var(--text-primary, #111827);
  width: 100%;
  box-sizing: border-box;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.form-hint {
  font-size: 0.75rem;
  color: var(--text-muted, #6b7280);
  margin: 0;
}

.form-hint a {
  color: #3b82f6;
}

/* Checkboxes */
.checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.5rem;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.checkbox-item input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}

/* Severity grid */
.severity-grid {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.severity-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.severity-label {
  min-width: 130px;
  font-size: 0.875rem;
}

/* Slack preview */
.preview-box {
  background: var(--code-bg, #f8fafc);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  padding: 1rem;
  margin-bottom: 1rem;
}

.preview-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #6b7280);
  margin-bottom: 0.75rem;
}

.slack-preview {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  margin-bottom: 0.5rem;
}

.slack-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

.slack-text {
  font-size: 0.875rem;
}

/* Buttons */
.action-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-top: 1rem;
  flex-wrap: wrap;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
}

.btn:disabled {
  opacity: 0.6;
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
  background: var(--btn-secondary-bg, #f3f4f6);
  color: var(--text-primary, #111827);
  border: 1px solid var(--border-color, #d1d5db);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--btn-secondary-hover, #e5e7eb);
}

.btn-sm {
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
}

/* Monitoring endpoints */
.endpoint-box {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: var(--code-bg, #f1f5f9);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  font-size: 0.85rem;
}

.endpoint-box code {
  flex: 1;
  word-break: break-all;
}

.btn-copy {
  background: none;
  border: 1px solid var(--border-color, #d1d5db);
  border-radius: 0.375rem;
  padding: 0.25rem 0.6rem;
  font-size: 0.75rem;
  cursor: pointer;
  white-space: nowrap;
}

.btn-copy:hover {
  background: var(--btn-secondary-hover, #e5e7eb);
}

.metrics-sample pre {
  background: var(--code-bg, #f8fafc);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  padding: 1rem;
  font-size: 0.8rem;
  overflow-x: auto;
  margin: 0;
}

.info-text {
  font-size: 0.875rem;
  color: var(--text-secondary, #374151);
  margin: 0 0 1rem;
}

/* Webhooks */
.webhook-form {
  background: var(--form-bg, #f9fafb);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  padding: 1rem;
  margin-bottom: 1.25rem;
}

.webhook-form h3 {
  font-size: 0.95rem;
  font-weight: 600;
  margin: 0 0 1rem;
}

.webhook-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.webhook-item {
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  padding: 0.875rem;
}

.webhook-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.375rem;
}

.webhook-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-green { background: #22c55e; }
.dot-gray  { background: #9ca3af; }

.webhook-actions {
  display: flex;
  gap: 0.25rem;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem 0.4rem;
  border-radius: 0.375rem;
  font-size: 0.85rem;
  transition: background 0.15s;
}

.btn-icon:hover {
  background: var(--btn-secondary-hover, #f3f4f6);
}

.btn-danger:hover {
  background: #fee2e2;
}

.webhook-url {
  font-size: 0.8rem;
  color: var(--text-muted, #6b7280);
  word-break: break-all;
  margin-bottom: 0.375rem;
}

.webhook-events {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-bottom: 0.5rem;
}

.event-tag {
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 500;
  padding: 0.1rem 0.5rem;
}

/* Delivery log */
.delivery-log {
  margin-top: 0.5rem;
  border-top: 1px solid var(--border-color, #f3f4f6);
  padding-top: 0.5rem;
}

.delivery-log-title {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #9ca3af);
  margin-bottom: 0.35rem;
}

.delivery-row {
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  padding: 0.15rem 0;
  color: var(--text-secondary, #374151);
}

.delivery-ok   { color: #166534; }
.delivery-fail { color: #b91c1c; }

.delivery-event { flex: 1; }
.delivery-code  { font-weight: 600; }
.delivery-time  { color: var(--text-muted, #9ca3af); }

/* Empty state */
.empty-state {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted, #9ca3af);
  font-size: 0.875rem;
}

.loading-text {
  text-align: center;
  padding: 1.5rem;
  color: var(--text-muted, #9ca3af);
  font-size: 0.875rem;
}

/* OIDC coming-soon banner */
.coming-soon-banner {
  display: flex;
  gap: 0.75rem;
  background: #fef9c3;
  border: 1px solid #fde047;
  border-radius: 0.5rem;
  padding: 0.875rem 1rem;
  margin-bottom: 1.5rem;
  align-items: flex-start;
}

.cs-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.coming-soon-banner strong {
  display: block;
  margin-bottom: 0.25rem;
  font-size: 0.9rem;
}

.coming-soon-banner p {
  font-size: 0.8rem;
  color: #713f12;
  margin: 0;
}
</style>
