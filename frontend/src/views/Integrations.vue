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
          <p class="form-hint" style="margin-bottom: 0.5rem;">
            Choose which events will post a message to Slack. Deselect events you don't need to reduce noise.
          </p>
          <div class="event-toggle-grid">
            <div
              v-for="group in slackEventGroups"
              :key="group.label"
              class="event-group"
            >
              <div class="event-group-label">{{ group.label }}</div>
              <label
                v-for="ev in group.events"
                :key="ev.value"
                class="event-toggle-item"
              >
                <div class="event-toggle-row">
                  <span class="event-toggle-icon">{{ ev.icon }}</span>
                  <span class="event-toggle-name">{{ ev.label }}</span>
                  <span class="event-toggle-key">{{ ev.value }}</span>
                  <div class="toggle-switch" :class="{ 'toggle-switch-on': slack.events.includes(ev.value) }">
                    <input
                      type="checkbox"
                      :value="ev.value"
                      v-model="slack.events"
                      class="toggle-input"
                    />
                    <span class="toggle-thumb"></span>
                  </div>
                </div>
              </label>
            </div>
          </div>
        </div>

        <!-- Message format preview -->
        <div class="preview-box">
          <div class="preview-label">Message format preview</div>
          <div class="preview-content">
            <div class="slack-preview slack-preview-green">
              <span class="slack-bar"></span>
              <div class="slack-text">
                <strong>:arrow_forward: VM Started</strong>: <code>web-01</code> (VMID 101)<br/>
                Node: <code>pve1</code> on <strong>prod-cluster</strong> · by <code>admin</code>
              </div>
            </div>
            <div class="slack-preview slack-preview-red">
              <span class="slack-bar"></span>
              <div class="slack-text">
                <strong>:red_circle: [CRITICAL] High memory: pve2</strong><br/>
                Node 'pve2' has memory usage at 96.1% (threshold: 95%). Threshold: <code>95</code>
              </div>
            </div>
            <div class="slack-preview slack-preview-gray">
              <span class="slack-bar"></span>
              <div class="slack-text">
                <strong>:bust_in_silhouette:</strong> User <code>admin</code> logged in from <code>192.168.1.10</code>
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
          <span class="badge" :class="(pagerduty.integration_key || pagerduty.routing_key) ? 'badge-green' : 'badge-gray'">
            {{ (pagerduty.integration_key || pagerduty.routing_key) ? 'Configured' : 'Not configured' }}
          </span>
        </div>

        <p class="info-text">
          Depl0y will trigger PagerDuty incidents for critical alerts and resolve them automatically
          when the alert is acknowledged. Uses the <strong>Events API v2</strong>.
        </p>

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
              placeholder="For event orchestration (optional)"
              class="form-input"
            />
            <p class="form-hint">Use this instead of Integration Key for event orchestration rules.</p>
          </div>
        </div>

        <div class="form-group">
          <label>Trigger PagerDuty on</label>
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
            <label class="checkbox-item">
              <input type="checkbox" v-model="pagerduty.alert_high_memory" />
              <span>High memory (&gt;95%)</span>
            </label>
            <label class="checkbox-item">
              <input type="checkbox" v-model="pagerduty.alert_login_failures" />
              <span>Brute-force login attempts</span>
            </label>
          </div>
        </div>

        <div class="form-group">
          <label>Severity mapping</label>
          <p class="form-hint" style="margin-bottom: 0.5rem;">
            Map Depl0y alert categories to PagerDuty incident severity levels.
          </p>
          <div class="severity-grid">
            <div class="severity-row">
              <span class="severity-label severity-badge-critical">Critical alerts</span>
              <select v-model="pagerduty.severity_critical" class="form-select severity-select">
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
              <span class="severity-hint">→ PagerDuty severity</span>
            </div>
            <div class="severity-row">
              <span class="severity-label severity-badge-warning">Warning alerts</span>
              <select v-model="pagerduty.severity_warning" class="form-select severity-select">
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
              <span class="severity-hint">→ PagerDuty severity</span>
            </div>
            <div class="severity-row">
              <span class="severity-label">VM stopped (unexp.)</span>
              <select v-model="pagerduty.severity_vm_stopped" class="form-select severity-select">
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
              <span class="severity-hint">→ PagerDuty severity</span>
            </div>
            <div class="severity-row">
              <span class="severity-label">Node offline</span>
              <select v-model="pagerduty.severity_node_offline" class="form-select severity-select">
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
              <span class="severity-hint">→ PagerDuty severity</span>
            </div>
          </div>
        </div>

        <div class="action-row">
          <button
            class="btn btn-secondary"
            :disabled="pdTesting"
            @click="testPagerDuty"
          >
            <span v-if="pdTesting">Sending test...</span>
            <span v-else>Send test alert</span>
          </button>
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
          <button class="btn btn-primary btn-sm" @click="openCreateWebhook">
            + Add webhook
          </button>
        </div>

        <p class="info-text">
          Webhooks let external services receive real-time event notifications.
          Each delivery is signed with HMAC-SHA256 if a secret is configured.
          The event type is embedded in the signed payload body, so signatures cover the full envelope.
        </p>

        <!-- Webhook list table -->
        <div v-if="webhooksLoading" class="loading-text">Loading webhooks...</div>
        <div v-else-if="webhooks.length === 0" class="empty-state">
          <div class="empty-wh-icon">🔗</div>
          <strong>No webhooks configured</strong>
          <p>Click "+ Add webhook" to create your first webhook endpoint.</p>
        </div>
        <div v-else class="wh-table-wrap">
          <table class="wh-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>URL</th>
                <th>Events</th>
                <th>Status</th>
                <th>Last delivery</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="hook in webhooks" :key="hook.id">
                <td>
                  <span class="wh-name">{{ hook.name }}</span>
                </td>
                <td>
                  <span class="wh-url" :title="hook.url">{{ maskUrl(hook.url) }}</span>
                </td>
                <td>
                  <div class="event-tags-wrap">
                    <span v-for="ev in hook.events" :key="ev" class="event-tag">{{ ev }}</span>
                    <span v-if="!hook.events || hook.events.length === 0" class="no-events">—</span>
                  </div>
                </td>
                <td>
                  <button
                    class="toggle-btn"
                    :class="hook.enabled ? 'toggle-on' : 'toggle-off'"
                    @click="toggleWebhookEnabled(hook)"
                    :title="hook.enabled ? 'Click to disable' : 'Click to enable'"
                  >
                    <span class="toggle-dot"></span>
                    {{ hook.enabled ? 'Active' : 'Inactive' }}
                  </button>
                </td>
                <td>
                  <div v-if="hook.delivery_log && hook.delivery_log.length > 0" class="last-delivery">
                    <span
                      class="delivery-status-dot"
                      :class="hook.delivery_log[0].success ? 'ds-ok' : 'ds-fail'"
                    ></span>
                    <span class="delivery-code-sm">
                      {{ hook.delivery_log[0].success ? 'OK' : 'Failed' }}
                      {{ hook.delivery_log[0].status_code ? `· ${hook.delivery_log[0].status_code}` : '' }}
                    </span>
                    <span class="delivery-time-sm">{{ formatRelativeDate(hook.delivery_log[0].created_at) }}</span>
                  </div>
                  <span v-else class="no-deliveries">Never fired</span>
                </td>
                <td>
                  <div class="wh-action-btns">
                    <button
                      class="wh-btn wh-btn-test"
                      :disabled="testingWebhookId === hook.id"
                      @click="testWebhook(hook)"
                      title="Send test payload"
                    >
                      {{ testingWebhookId === hook.id ? '...' : '▶ Test' }}
                    </button>
                    <button
                      class="wh-btn wh-btn-log"
                      @click="openDeliveryLog(hook)"
                      title="View delivery log"
                    >
                      Log
                    </button>
                    <button
                      class="wh-btn wh-btn-edit"
                      @click="editWebhook(hook)"
                      title="Edit webhook"
                    >
                      Edit
                    </button>
                    <button
                      class="wh-btn wh-btn-delete"
                      @click="deleteWebhook(hook)"
                      title="Delete webhook"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ── Create/Edit Webhook Modal ── -->
    <Teleport to="body">
      <div v-if="showWebhookModal" class="modal-overlay" @click.self="cancelWebhookForm">
        <div class="modal-box modal-wide">
          <div class="modal-header">
            <h3>{{ editingWebhook ? 'Edit Webhook' : 'Create Webhook' }}</h3>
            <button class="modal-close" @click="cancelWebhookForm">✕</button>
          </div>
          <div class="modal-body">
            <div class="form-grid">
              <div class="form-group">
                <label>Name <span class="req">*</span></label>
                <input
                  v-model="webhookForm.name"
                  type="text"
                  placeholder="e.g. My Slack hook"
                  class="form-input"
                  autofocus
                />
              </div>
              <div class="form-group">
                <label>URL <span class="req">*</span></label>
                <input
                  v-model="webhookForm.url"
                  type="url"
                  placeholder="https://example.com/hook"
                  class="form-input"
                />
              </div>
              <div class="form-group">
                <label>Secret <span class="form-hint-inline">(optional — HMAC-SHA256 signing)</span></label>
                <input
                  v-model="webhookForm.secret"
                  type="password"
                  placeholder="Leave blank to keep existing"
                  class="form-input"
                  autocomplete="new-password"
                />
              </div>
            </div>

            <div class="form-group">
              <label>Events to subscribe <span class="req">*</span></label>
              <div class="wh-event-filter">
                <div
                  v-for="group in webhookEventGroups"
                  :key="group.label"
                  class="wh-event-group"
                >
                  <div class="wh-event-group-header">
                    <span class="wh-event-group-label">{{ group.label }}</span>
                    <button
                      type="button"
                      class="wh-group-toggle-btn"
                      @click="toggleEventGroup(group)"
                    >
                      {{ isGroupFullySelected(group) ? 'Deselect all' : 'Select all' }}
                    </button>
                  </div>
                  <div class="event-checkbox-grid">
                    <label
                      v-for="ev in group.events"
                      :key="ev.value"
                      class="event-checkbox-item"
                    >
                      <input type="checkbox" :value="ev.value" v-model="webhookForm.events" />
                      <span class="ev-label">
                        <span class="ev-icon">{{ ev.icon }}</span>
                        <span class="ev-name">{{ ev.label }}</span>
                        <span class="ev-key">{{ ev.value }}</span>
                      </span>
                    </label>
                  </div>
                </div>
              </div>
              <p v-if="webhookForm.events.length === 0" class="form-hint warn-hint">
                Select at least one event.
              </p>
              <p v-else class="form-hint">
                {{ webhookForm.events.length }} event{{ webhookForm.events.length !== 1 ? 's' : '' }} selected
              </p>
            </div>

            <div class="form-group">
              <label class="checkbox-item">
                <input type="checkbox" v-model="webhookForm.enabled" />
                <span>Enable this webhook immediately</span>
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="cancelWebhookForm">Cancel</button>
            <button class="btn btn-primary" :disabled="webhookSaving" @click="saveWebhook">
              <span v-if="webhookSaving">Saving...</span>
              <span v-else>{{ editingWebhook ? 'Update Webhook' : 'Create Webhook' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Delivery Log Modal ── -->
    <Teleport to="body">
      <div v-if="showDeliveryLogModal" class="modal-overlay" @click.self="showDeliveryLogModal = false">
        <div class="modal-box modal-wide">
          <div class="modal-header">
            <h3>Delivery Log — {{ deliveryLogHook?.name }}</h3>
            <button class="modal-close" @click="showDeliveryLogModal = false">✕</button>
          </div>
          <div class="modal-body">
            <div v-if="deliveryLogLoading" class="loading-text">Loading deliveries...</div>
            <div v-else-if="deliveryLog.length === 0" class="empty-state">
              No deliveries recorded yet.
            </div>
            <table v-else class="delivery-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Status</th>
                  <th>Code</th>
                  <th>Response preview</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="d in deliveryLog"
                  :key="d.id"
                  :class="d.success ? 'drow-ok' : 'drow-fail'"
                >
                  <td class="dl-time">{{ formatDate(d.created_at) }}</td>
                  <td><span class="event-tag">{{ d.event }}</span></td>
                  <td>
                    <span class="dl-status" :class="d.success ? 'status-ok' : 'status-fail'">
                      {{ d.success ? 'Success' : 'Failed' }}
                    </span>
                  </td>
                  <td class="dl-code">{{ d.status_code || '—' }}</td>
                  <td class="dl-response">
                    <span class="response-preview">{{ truncateResponse(d.response_body) }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showDeliveryLogModal = false">Close</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Test Result Modal ── -->
    <Teleport to="body">
      <div v-if="showTestResultModal" class="modal-overlay" @click.self="showTestResultModal = false">
        <div class="modal-box">
          <div class="modal-header">
            <h3>Test Result — {{ testResultHookName }}</h3>
            <button class="modal-close" @click="showTestResultModal = false">✕</button>
          </div>
          <div class="modal-body">
            <div class="test-result-banner" :class="testResult.success ? 'result-ok' : 'result-fail'">
              <span class="result-icon">{{ testResult.success ? '✓' : '✗' }}</span>
              <div>
                <strong>{{ testResult.success ? 'Test delivered successfully' : 'Delivery failed' }}</strong>
                <div class="result-code">
                  HTTP {{ testResult.response_code || 'N/A' }}
                </div>
              </div>
            </div>
            <div v-if="testResult.response_text" class="response-box">
              <div class="response-label">Response body</div>
              <pre class="response-pre">{{ testResult.response_text }}</pre>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showTestResultModal = false">Close</button>
          </div>
        </div>
      </div>
    </Teleport>

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
      { id: 'webhooks',   label: 'Webhooks',          icon: '🔗' },
      { id: 'oidc',       label: 'OIDC / SSO',        icon: '🔐' },
    ]

    // ── Slack ──────────────────────────────────────────────────────────────
    const slack = ref({ webhook_url: '', channel: '', events: [], configured: false })
    const slackSaving = ref(false)
    const slackTesting = ref(false)

    // Grouped event options for Slack — per-event toggles
    const slackEventGroups = [
      {
        label: 'VM Lifecycle',
        events: [
          { value: 'vm.start',    label: 'VM started',   icon: '▶' },
          { value: 'vm.stop',     label: 'VM stopped',   icon: '⏹' },
          { value: 'vm.shutdown', label: 'VM shutdown',  icon: '💤' },
          { value: 'vm.create',   label: 'VM created',   icon: '✨' },
          { value: 'vm.delete',   label: 'VM deleted',   icon: '🗑' },
          { value: 'vm.migrate',  label: 'VM migrated',  icon: '🚚' },
        ],
      },
      {
        label: 'Backups',
        events: [
          { value: 'backup.complete', label: 'Backup complete', icon: '✅' },
          { value: 'backup.failed',   label: 'Backup failed',   icon: '❌' },
        ],
      },
      {
        label: 'Alerts',
        events: [
          { value: 'alert.fired',    label: 'Alert fired',    icon: '🔴' },
          { value: 'alert.resolved', label: 'Alert resolved', icon: '🟢' },
        ],
      },
      {
        label: 'Authentication',
        events: [
          { value: 'user.login',        label: 'User login',        icon: '👤' },
          { value: 'user.login_failed', label: 'Failed login attempt', icon: '⚠' },
        ],
      },
      {
        label: 'Infrastructure',
        events: [
          { value: 'task.failed',  label: 'Task failed',   icon: '❌' },
          { value: 'node.offline', label: 'Node offline',  icon: '🔴' },
          { value: 'node.online',  label: 'Node online',   icon: '🟢' },
        ],
      },
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
      alert_high_memory: true,
      alert_login_failures: false,
      severity_critical: 'critical',
      severity_warning: 'warning',
      severity_vm_stopped: 'warning',
      severity_node_offline: 'critical',
    })
    const pdSaving = ref(false)
    const pdTesting = ref(false)

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

    const testPagerDuty = async () => {
      pdTesting.value = true
      try {
        await api.integrations.testPagerDuty()
        toast.success('Test PagerDuty alert sent!')
      } catch (e) {
        const msg = e.response?.data?.detail || 'Failed to send test alert'
        toast.error(msg)
      } finally {
        pdTesting.value = false
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
    const showWebhookModal = ref(false)
    const showWebhookForm = ref(false)  // kept for template compat
    const editingWebhook = ref(null)
    const webhookSaving = ref(false)
    const testingWebhookId = ref(null)

    // Delivery log modal
    const showDeliveryLogModal = ref(false)
    const deliveryLogHook = ref(null)
    const deliveryLog = ref([])
    const deliveryLogLoading = ref(false)

    // Test result modal
    const showTestResultModal = ref(false)
    const testResultHookName = ref('')
    const testResult = ref({ success: false, response_code: null, response_text: '' })

    const webhookFormDefaults = () => ({
      name: '',
      url: '',
      secret: '',
      events: [],
      enabled: true,
    })
    const webhookForm = ref(webhookFormDefaults())

    // Grouped event options for webhook event filter (multi-select checkboxes)
    const webhookEventGroups = [
      {
        label: 'VM Lifecycle',
        events: [
          { value: 'vm.start',    label: 'VM started',  icon: '▶' },
          { value: 'vm.stop',     label: 'VM stopped',  icon: '⏹' },
          { value: 'vm.create',   label: 'VM created',  icon: '✨' },
          { value: 'vm.delete',   label: 'VM deleted',  icon: '🗑' },
          { value: 'vm.migrate',  label: 'VM migrated', icon: '🚚' },
          { value: 'vm.shutdown', label: 'VM shutdown', icon: '💤' },
        ],
      },
      {
        label: 'Backups',
        events: [
          { value: 'backup.complete', label: 'Backup complete', icon: '✅' },
          { value: 'backup.failed',   label: 'Backup failed',   icon: '❌' },
        ],
      },
      {
        label: 'Alerts',
        events: [
          { value: 'alert.fired',    label: 'Alert fired',    icon: '🔴' },
          { value: 'alert.resolved', label: 'Alert resolved', icon: '🟢' },
        ],
      },
      {
        label: 'Authentication',
        events: [
          { value: 'user.login',        label: 'User login',        icon: '👤' },
          { value: 'user.login_failed', label: 'Login failed',      icon: '⚠' },
        ],
      },
      {
        label: 'Infrastructure',
        events: [
          { value: 'task.failed',  label: 'Task failed',  icon: '❌' },
          { value: 'node.offline', label: 'Node offline', icon: '🔴' },
          { value: 'node.online',  label: 'Node online',  icon: '🟢' },
        ],
      },
    ]

    // Flat list for backwards compat (used nowhere now but kept for safety)
    const webhookEventOptions = webhookEventGroups.flatMap(g => g.events)

    const isGroupFullySelected = (group) => {
      return group.events.every(ev => webhookForm.value.events.includes(ev.value))
    }

    const toggleEventGroup = (group) => {
      if (isGroupFullySelected(group)) {
        webhookForm.value.events = webhookForm.value.events.filter(
          v => !group.events.some(ev => ev.value === v)
        )
      } else {
        const toAdd = group.events.map(ev => ev.value).filter(
          v => !webhookForm.value.events.includes(v)
        )
        webhookForm.value.events = [...webhookForm.value.events, ...toAdd]
      }
    }

    const maskUrl = (url) => {
      if (!url) return ''
      try {
        const u = new URL(url)
        const host = u.hostname
        const path = u.pathname.length > 20 ? '...' + u.pathname.slice(-12) : u.pathname
        return `${u.protocol}//${host}${path}`
      } catch {
        return url.length > 50 ? url.slice(0, 47) + '...' : url
      }
    }

    const formatRelativeDate = (iso) => {
      if (!iso) return ''
      const diff = Date.now() - new Date(iso).getTime()
      const mins = Math.floor(diff / 60000)
      if (mins < 1) return 'just now'
      if (mins < 60) return `${mins}m ago`
      const hrs = Math.floor(mins / 60)
      if (hrs < 24) return `${hrs}h ago`
      return `${Math.floor(hrs / 24)}d ago`
    }

    const truncateResponse = (text) => {
      if (!text) return '—'
      return text.length > 80 ? text.slice(0, 80) + '…' : text
    }

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

    const openCreateWebhook = () => {
      editingWebhook.value = null
      webhookForm.value = webhookFormDefaults()
      showWebhookModal.value = true
      showWebhookForm.value = true
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
      showWebhookModal.value = true
      showWebhookForm.value = true
    }

    const cancelWebhookForm = () => {
      showWebhookModal.value = false
      showWebhookForm.value = false
      editingWebhook.value = null
      webhookForm.value = webhookFormDefaults()
    }

    const saveWebhook = async () => {
      if (!webhookForm.value.name || !webhookForm.value.url) {
        toast.error('Name and URL are required')
        return
      }
      if (webhookForm.value.events.length === 0) {
        toast.error('Select at least one event')
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

    const toggleWebhookEnabled = async (hook) => {
      const updated = { ...hook, enabled: !hook.enabled, secret: '' }
      try {
        await api.notifications.updateWebhook(hook.id, updated)
        hook.enabled = !hook.enabled
        toast.success(hook.enabled ? 'Webhook enabled' : 'Webhook disabled')
      } catch (e) {
        toast.error('Failed to update webhook')
      }
    }

    const testWebhook = async (hook) => {
      testingWebhookId.value = hook.id
      try {
        const r = await api.notifications.testWebhook(hook.id)
        testResultHookName.value = hook.name
        testResult.value = r.data
        showTestResultModal.value = true
        await loadWebhooks()
      } catch (e) {
        toast.error('Webhook test failed — check the URL is reachable')
      } finally {
        testingWebhookId.value = null
      }
    }

    const openDeliveryLog = async (hook) => {
      deliveryLogHook.value = hook
      showDeliveryLogModal.value = true
      deliveryLogLoading.value = true
      deliveryLog.value = []
      try {
        const r = await api.notifications.getWebhookDeliveries(hook.id)
        deliveryLog.value = r.data.deliveries || []
      } catch (e) {
        toast.error('Failed to load delivery log')
      } finally {
        deliveryLogLoading.value = false
      }
    }

    const deleteWebhook = async (hook) => {
      if (!confirm(`Delete webhook "${hook.name}"?\n\nThis will also remove all delivery history.`)) return
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
      slack, slackSaving, slackTesting, slackEventGroups, saveSlack, testSlack,
      // PagerDuty
      pagerduty, pdSaving, pdTesting, savePagerDuty, testPagerDuty,
      // InfluxDB
      influxdb, influxSaving, saveInfluxDB, apiBase, metricsExample, copyMetricsUrl,
      // Webhooks
      webhooks, webhooksLoading, showWebhookModal, showWebhookForm, editingWebhook,
      webhookForm, webhookSaving, webhookEventOptions, webhookEventGroups, testingWebhookId,
      isGroupFullySelected, toggleEventGroup,
      // Delivery log modal
      showDeliveryLogModal, deliveryLogHook, deliveryLog, deliveryLogLoading,
      // Test result modal
      showTestResultModal, testResultHookName, testResult,
      // Webhook methods
      loadWebhooks, openCreateWebhook, editWebhook, cancelWebhookForm, saveWebhook,
      toggleWebhookEnabled, testWebhook, openDeliveryLog, deleteWebhook,
      maskUrl, formatRelativeDate, truncateResponse,
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
  gap: 0.625rem;
}

.severity-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.severity-label {
  min-width: 150px;
  font-size: 0.875rem;
  color: var(--text-secondary, #374151);
}

.severity-badge-critical {
  background: #fee2e2;
  color: #b91c1c;
  padding: 0.15rem 0.5rem;
  border-radius: 0.375rem;
  font-size: 0.8rem;
  font-weight: 600;
}

.severity-badge-warning {
  background: #fef3c7;
  color: #92400e;
  padding: 0.15rem 0.5rem;
  border-radius: 0.375rem;
  font-size: 0.8rem;
  font-weight: 600;
}

.severity-hint {
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
}

.severity-select {
  width: auto;
  min-width: 110px;
}

/* ── Slack event toggles ── */
.event-toggle-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  padding: 0.875rem;
}

.event-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.event-group-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, #9ca3af);
  padding: 0 0 0.25rem;
  border-bottom: 1px solid var(--border-color, #f3f4f6);
  margin-bottom: 0.25rem;
}

.event-toggle-item {
  cursor: pointer;
}

.event-toggle-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.375rem;
  border-radius: 0.375rem;
  transition: background 0.1s;
}

.event-toggle-row:hover {
  background: var(--hover-bg, #f9fafb);
}

.event-toggle-icon {
  font-size: 0.875rem;
  width: 1.25rem;
  text-align: center;
  flex-shrink: 0;
}

.event-toggle-name {
  flex: 1;
  font-size: 0.875rem;
  color: var(--text-primary, #111827);
}

.event-toggle-key {
  font-size: 0.7rem;
  font-family: monospace;
  color: var(--text-muted, #9ca3af);
  background: var(--code-bg, #f3f4f6);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
}

/* Toggle switch */
.toggle-switch {
  position: relative;
  width: 2.25rem;
  height: 1.25rem;
  background: var(--border-color, #d1d5db);
  border-radius: 999px;
  flex-shrink: 0;
  transition: background 0.2s;
  cursor: pointer;
}

.toggle-switch-on {
  background: #3b82f6;
}

.toggle-input {
  position: absolute;
  opacity: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  cursor: pointer;
  z-index: 1;
}

.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 1rem;
  height: 1rem;
  background: #f8fafc;
  border-radius: 50%;
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
  transition: left 0.2s;
  pointer-events: none;
}

.toggle-switch-on .toggle-thumb {
  left: calc(100% - 1.125rem);
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
  gap: 0;
  align-items: flex-start;
  margin-bottom: 0.75rem;
  border-radius: 0.375rem;
  overflow: hidden;
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
}

.slack-bar {
  width: 4px;
  flex-shrink: 0;
  align-self: stretch;
}

.slack-preview-green .slack-bar  { background: #22c55e; }
.slack-preview-red .slack-bar    { background: #ef4444; }
.slack-preview-gray .slack-bar   { background: #9ca3af; }

.slack-text {
  font-size: 0.8125rem;
  padding: 0.5rem 0.75rem;
  line-height: 1.5;
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
.webhook-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.event-tag {
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 500;
  padding: 0.1rem 0.5rem;
}

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

/* ── Webhook Table ── */
.wh-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
}

.wh-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.wh-table thead th {
  background: var(--table-head-bg, #f9fafb);
  padding: 0.6rem 0.875rem;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted, #6b7280);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  white-space: nowrap;
}

.wh-table tbody tr {
  border-bottom: 1px solid var(--border-color, #f3f4f6);
  transition: background 0.1s;
}

.wh-table tbody tr:last-child {
  border-bottom: none;
}

.wh-table tbody tr:hover {
  background: var(--hover-bg, #f9fafb);
}

.wh-table td {
  padding: 0.75rem 0.875rem;
  vertical-align: middle;
}

.wh-name {
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.wh-url {
  font-size: 0.75rem;
  color: var(--text-muted, #6b7280);
  font-family: monospace;
  display: block;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-tags-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  max-width: 220px;
}

.no-events {
  color: var(--text-muted, #9ca3af);
}

/* Toggle button */
.toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border: none;
  border-radius: 999px;
  padding: 0.25rem 0.7rem;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.toggle-on {
  background: #d1fae5;
  color: #065f46;
}

.toggle-on:hover {
  background: #a7f3d0;
}

.toggle-off {
  background: #f3f4f6;
  color: #6b7280;
}

.toggle-off:hover {
  background: #e5e7eb;
}

.toggle-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

/* Last delivery */
.last-delivery {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.delivery-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ds-ok   { background: #10b981; }
.ds-fail { background: #ef4444; }

.delivery-code-sm {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary, #374151);
}

.delivery-time-sm {
  font-size: 0.7rem;
  color: var(--text-muted, #9ca3af);
}

.no-deliveries {
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
}

/* Webhook action buttons */
.wh-action-btns {
  display: flex;
  gap: 0.25rem;
  flex-wrap: nowrap;
}

.wh-btn {
  padding: 0.2rem 0.55rem;
  border-radius: 0.375rem;
  border: 1px solid transparent;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}

.wh-btn-test {
  background: #dbeafe;
  color: #1d4ed8;
  border-color: #bfdbfe;
}

.wh-btn-test:hover:not(:disabled) {
  background: #bfdbfe;
}

.wh-btn-test:disabled {
  opacity: 0.6;
  cursor: wait;
}

.wh-btn-log {
  background: #f3f4f6;
  color: #374151;
  border-color: #d1d5db;
}

.wh-btn-log:hover {
  background: #e5e7eb;
}

.wh-btn-edit {
  background: #f0fdf4;
  color: #166534;
  border-color: #bbf7d0;
}

.wh-btn-edit:hover {
  background: #dcfce7;
}

.wh-btn-delete {
  background: var(--card-bg, #fff);
  color: #dc2626;
  border-color: #fca5a5;
}

.wh-btn-delete:hover {
  background: #fee2e2;
}

/* Empty webhook state */
.empty-wh-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

/* ── Webhook event filter in modal ── */
.wh-event-filter {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  padding: 0.875rem;
  max-height: 380px;
  overflow-y: auto;
}

.wh-event-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.wh-event-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--border-color, #f3f4f6);
  margin-bottom: 0.25rem;
}

.wh-event-group-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, #9ca3af);
}

.wh-group-toggle-btn {
  background: none;
  border: none;
  font-size: 0.7rem;
  color: #3b82f6;
  cursor: pointer;
  padding: 0;
}

.wh-group-toggle-btn:hover {
  text-decoration: underline;
}

/* ── Modals ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-box {
  background: var(--card-bg, #fff);
  border-radius: 0.75rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-wide {
  max-width: 760px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  flex-shrink: 0;
}

.modal-header h3 {
  font-size: 1rem;
  font-weight: 700;
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  color: var(--text-muted, #9ca3af);
  padding: 0.2rem 0.4rem;
  border-radius: 0.375rem;
  line-height: 1;
  transition: background 0.15s, color 0.15s;
}

.modal-close:hover {
  background: #fee2e2;
  color: #dc2626;
}

.modal-body {
  padding: 1.25rem;
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.625rem;
  padding: 0.875rem 1.25rem;
  border-top: 1px solid var(--border-color, #e5e7eb);
  flex-shrink: 0;
}

/* Event checkbox grid in modal */
.event-checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.25rem;
}

.event-checkbox-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 0.375rem;
  transition: background 0.1s;
}

.event-checkbox-item:hover {
  background: var(--hover-bg, #f9fafb);
}

.event-checkbox-item input[type="checkbox"] {
  width: 0.875rem;
  height: 0.875rem;
  flex-shrink: 0;
  margin-top: 0.25rem;
}

.ev-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.ev-icon {
  font-size: 0.8rem;
  flex-shrink: 0;
}

.ev-name {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-primary, #111827);
}

.ev-key {
  font-size: 0.7rem;
  font-family: monospace;
  color: var(--text-muted, #9ca3af);
}

.form-hint-inline {
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--text-muted, #9ca3af);
}

.req {
  color: #ef4444;
  font-size: 0.75rem;
}

.warn-hint {
  color: #d97706;
}

/* Delivery log table */
.delivery-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.delivery-table thead th {
  background: var(--table-head-bg, #f9fafb);
  padding: 0.5rem 0.75rem;
  text-align: left;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #6b7280);
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}

.delivery-table tbody tr {
  border-bottom: 1px solid var(--border-color, #f3f4f6);
}

.delivery-table td {
  padding: 0.6rem 0.75rem;
  vertical-align: top;
}

.drow-ok td:first-child   { border-left: 3px solid #10b981; }
.drow-fail td:first-child { border-left: 3px solid #ef4444; }

.dl-time {
  white-space: nowrap;
  font-size: 0.75rem;
  color: var(--text-muted, #6b7280);
}

.dl-status {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
}

.status-ok   { background: #d1fae5; color: #065f46; }
.status-fail { background: #fee2e2; color: #b91c1c; }

.dl-code {
  font-weight: 700;
  font-family: monospace;
}

.dl-response {
  max-width: 220px;
}

.response-preview {
  font-size: 0.7rem;
  font-family: monospace;
  color: var(--text-secondary, #6b7280);
  word-break: break-all;
}

/* Test result modal */
.test-result-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.875rem;
  padding: 0.875rem 1rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.result-ok   { background: #d1fae5; color: #065f46; }
.result-fail { background: #fee2e2; color: #b91c1c; }

.result-icon {
  font-size: 1.25rem;
  font-weight: 700;
  flex-shrink: 0;
}

.result-code {
  font-size: 0.875rem;
  margin-top: 0.2rem;
  font-family: monospace;
  font-weight: 600;
}

.response-box {
  background: var(--code-bg, #f8fafc);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  padding: 0.75rem;
}

.response-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #9ca3af);
  margin-bottom: 0.5rem;
}

.response-pre {
  margin: 0;
  font-size: 0.8rem;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-primary, #111827);
  max-height: 200px;
  overflow-y: auto;
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
