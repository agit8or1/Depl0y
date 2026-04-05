<template>
  <transition name="wizard-fade">
    <div v-if="modelValue" class="wizard-overlay" @click.self="maybeClose">
      <div class="wizard-modal" role="dialog" aria-modal="true" aria-label="Add Proxmox Host">

        <!-- Header -->
        <div class="wizard-header">
          <div class="wizard-title-row">
            <h2 class="wizard-title">Add Proxmox Host</h2>
            <button class="wizard-close" @click="maybeClose" aria-label="Close">&times;</button>
          </div>
          <!-- Step indicator -->
          <div class="step-track">
            <div
              v-for="(s, idx) in steps"
              :key="idx"
              :class="['step-dot', {
                'step-done': idx < currentStep,
                'step-active': idx === currentStep,
              }]"
              @click="idx < currentStep && goToStep(idx)"
              :title="s.label"
            >
              <span v-if="idx < currentStep" class="step-check">&#10003;</span>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <div class="step-line" :style="{ width: stepLineWidth }"></div>
          </div>
          <div class="step-labels">
            <span v-for="(s, idx) in steps" :key="idx" :class="['step-label', { 'step-label-active': idx === currentStep }]">
              {{ s.label }}
            </span>
          </div>
        </div>

        <!-- Body -->
        <div class="wizard-body">

          <!-- ── Step 0: Connection ── -->
          <div v-if="currentStep === 0" class="step-content">
            <p class="step-intro">Enter your Proxmox API URL and authentication credentials.</p>

            <div class="form-group">
              <label class="form-label">Host Name <span class="req">*</span></label>
              <input
                v-model="form.name"
                class="form-control"
                placeholder="e.g. Production Cluster"
                autocomplete="off"
              />
              <p class="form-hint">A friendly label for this datacenter in Depl0y</p>
            </div>

            <div class="form-group">
              <label class="form-label">API URL <span class="req">*</span></label>
              <input
                v-model="form.api_url"
                class="form-control"
                placeholder="pve.example.com  or  https://192.168.1.10:8006"
                autocomplete="off"
                @blur="normalizeUrl"
              />
              <p class="form-hint">Auto-adds https:// prefix and :8006 port if omitted</p>
            </div>

            <!-- Auth method toggle -->
            <div class="auth-toggle">
              <button
                :class="['toggle-btn', form.auth_method === 'token' ? 'toggle-active' : '']"
                @click="form.auth_method = 'token'"
                type="button"
              >
                API Token <span class="badge badge-success badge-xs">Recommended</span>
              </button>
              <button
                :class="['toggle-btn', form.auth_method === 'password' ? 'toggle-active' : '']"
                @click="form.auth_method = 'password'"
                type="button"
              >
                Password
              </button>
            </div>

            <div v-if="form.auth_method === 'token'" class="auth-fields">
              <div class="privilege-warning">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                <div>
                  <strong>Important:</strong> When creating your API token in Proxmox, you must
                  <strong>UNCHECK</strong> "Privilege Separation" — otherwise the token won't
                  have VM management permissions.
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">User ID <span class="req">*</span></label>
                <input v-model="form.username" class="form-control" placeholder="root@pam" autocomplete="off" />
              </div>
              <div class="form-group">
                <label class="form-label">Token ID <span class="req">*</span></label>
                <input v-model="form.token_name" class="form-control" placeholder="depl0y  or  root@pam!depl0y" autocomplete="off" />
                <p class="form-hint">Just the token name, or the full "user@realm!tokenname" format</p>
              </div>
              <div class="form-group">
                <label class="form-label">Token Secret <span class="req">*</span></label>
                <input v-model="form.token_value" type="password" class="form-control" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" autocomplete="new-password" />
              </div>
            </div>

            <div v-else class="auth-fields">
              <div class="password-warning">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                Password auth is less secure than API tokens. If Proxmox has 2FA enabled, use API Token instead.
              </div>
              <div class="form-group">
                <label class="form-label">Username <span class="req">*</span></label>
                <input v-model="form.username" class="form-control" placeholder="root@pam" autocomplete="off" />
              </div>
              <div class="form-group">
                <label class="form-label">Password <span class="req">*</span></label>
                <input v-model="form.password" type="password" class="form-control" autocomplete="new-password" />
              </div>
            </div>

            <div class="ssl-row">
              <label class="toggle-label">
                <span class="toggle-switch" :class="{ 'toggle-on': form.verify_ssl }" @click="form.verify_ssl = !form.verify_ssl">
                  <span class="toggle-thumb"></span>
                </span>
                <span>Verify SSL Certificate</span>
              </label>
              <span v-if="!form.verify_ssl" class="ssl-hint">SSL verification is off — self-signed certs are accepted</span>
            </div>

            <!-- Test connection -->
            <div class="test-row">
              <button
                class="btn btn-outline"
                :disabled="testing || !canTest"
                @click="testConnection"
                type="button"
              >
                <span v-if="testing" class="spinner-inline"></span>
                {{ testing ? 'Testing...' : 'Test Connection' }}
              </button>

              <div v-if="testResult" :class="['test-result', testResult.success ? 'test-ok' : 'test-fail']">
                <svg v-if="testResult.success" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                <span v-if="testResult.success">Connected — Proxmox {{ testResult.proxmox_version }}</span>
                <span v-else>{{ testResult.error }}</span>
              </div>
            </div>
          </div>

          <!-- ── Step 1: Verify Cluster ── -->
          <div v-if="currentStep === 1" class="step-content">
            <div v-if="!testResult || !testResult.success" class="cluster-no-data">
              <p>No connection data available. Go back to Step 1 and test your connection first.</p>
            </div>

            <div v-else>
              <div class="cluster-summary-cards">
                <div class="summary-card">
                  <span class="summary-label">Cluster Name</span>
                  <span class="summary-value">{{ testResult.cluster_name || '(standalone)' }}</span>
                </div>
                <div class="summary-card">
                  <span class="summary-label">Node Count</span>
                  <span class="summary-value">{{ testResult.node_count }}</span>
                </div>
                <div class="summary-card">
                  <span class="summary-label">Proxmox Version</span>
                  <span class="summary-value">{{ testResult.proxmox_version }}</span>
                </div>
              </div>

              <div v-if="testResult.node_count === 1" class="info-banner">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                This is a standalone (single-node) installation — not a cluster.
              </div>

              <div v-if="testResult.nodes && testResult.nodes.length > 0" class="node-list">
                <h4 class="section-heading">Cluster Nodes</h4>
                <div class="node-chips">
                  <div
                    v-for="node in testResult.nodes"
                    :key="node.name"
                    :class="['node-chip', node.online ? 'chip-online' : 'chip-offline']"
                  >
                    <span class="chip-dot"></span>
                    <span class="chip-name">{{ node.name }}</span>
                    <span class="chip-status">{{ node.online ? 'online' : 'offline' }}</span>
                    <span v-if="node.local" class="chip-local">local</span>
                  </div>
                </div>
              </div>

              <div v-if="testResult.nodes && testResult.nodes.some(n => !n.online)" class="warn-banner">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                One or more cluster nodes are offline. The cluster may be degraded.
              </div>
            </div>
          </div>

          <!-- ── Step 2: Configure Defaults ── -->
          <div v-if="currentStep === 2" class="step-content">
            <p class="step-intro">Set default storage pools, networking, and monitoring options for this datacenter.</p>

            <div class="form-group">
              <label class="form-label">Default VM Storage</label>
              <select v-model="form.default_storage" class="form-control">
                <option value="">— None selected —</option>
                <option v-for="s in vmStorages" :key="s.storage" :value="s.storage">
                  {{ s.storage }} ({{ s.type }})
                </option>
              </select>
              <p class="form-hint">Used as the default disk storage when deploying new VMs</p>
            </div>

            <div class="form-group">
              <label class="form-label">Default ISO Storage</label>
              <select v-model="form.default_iso_storage" class="form-control">
                <option value="">— None selected —</option>
                <option v-for="s in isoStorages" :key="s.storage" :value="s.storage">
                  {{ s.storage }} ({{ s.type }})
                </option>
              </select>
              <p class="form-hint">Where ISO images are stored for VM installation</p>
            </div>

            <div class="form-group">
              <label class="form-label">Default Network Bridge</label>
              <select v-model="form.default_bridge" class="form-control">
                <option value="">— None selected —</option>
                <option v-for="n in networkBridges" :key="n.iface" :value="n.iface">
                  {{ n.iface }}{{ n.comments ? ' — ' + n.comments : '' }}
                </option>
              </select>
              <p class="form-hint">Default bridge for VM network interfaces</p>
            </div>

            <div class="form-group">
              <label class="form-label">Enable Monitoring</label>
              <div class="monitor-row">
                <label class="toggle-label">
                  <span class="toggle-switch" :class="{ 'toggle-on': form.monitoring_enabled }" @click="form.monitoring_enabled = !form.monitoring_enabled">
                    <span class="toggle-thumb"></span>
                  </span>
                  <span>Poll this host for resource usage</span>
                </label>
              </div>
            </div>

            <div v-if="form.monitoring_enabled" class="form-group">
              <label class="form-label">Poll Interval</label>
              <div class="poll-options">
                <label v-for="opt in pollOptions" :key="opt.value" class="poll-option">
                  <input type="radio" :value="opt.value" v-model="form.poll_interval" />
                  {{ opt.label }}
                </label>
              </div>
            </div>

            <div v-if="!testResult || !testResult.storages || testResult.storages.length === 0" class="info-banner">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              Storage and network info not detected — go back and test your connection to auto-populate these options. You can also configure this later.
            </div>
          </div>

          <!-- ── Step 3: iDRAC / BMC Setup ── -->
          <div v-if="currentStep === 3" class="step-content">
            <p class="step-intro">Optionally configure out-of-band BMC management (Dell iDRAC, HPE iLO) for hardware control such as remote power, sensor data, and event logs.</p>

            <div class="form-group">
              <label class="toggle-label bmc-toggle">
                <span class="toggle-switch" :class="{ 'toggle-on': form.has_bmc }" @click="form.has_bmc = !form.has_bmc">
                  <span class="toggle-thumb"></span>
                </span>
                <span>This cluster has BMC / iDRAC / iLO hardware management</span>
              </label>
            </div>

            <div v-if="form.has_bmc" class="bmc-fields">
              <div class="form-group">
                <label class="form-label">BMC Type</label>
                <select v-model="form.idrac_type" class="form-control">
                  <option value="">Select type...</option>
                  <option value="idrac">Dell iDRAC</option>
                  <option value="ilo">HPE iLO</option>
                </select>
              </div>
              <div v-if="form.idrac_type">
                <div class="form-group">
                  <label class="form-label">BMC Hostname / IP</label>
                  <input v-model="form.idrac_hostname" class="form-control" placeholder="192.168.1.10 or idrac.server.local" autocomplete="off" />
                </div>
                <div class="form-row-2">
                  <div class="form-group">
                    <label class="form-label">BMC Port</label>
                    <input v-model.number="form.idrac_port" type="number" class="form-control" placeholder="443" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Interface</label>
                    <select v-model="form.idrac_use_ssh" class="form-control">
                      <option :value="false">HTTPS / Redfish</option>
                      <option :value="true">SSH</option>
                    </select>
                  </div>
                </div>
                <div class="form-group">
                  <label class="form-label">BMC Username</label>
                  <input v-model="form.idrac_username" class="form-control" placeholder="root or administrator" autocomplete="off" />
                </div>
                <div class="form-group">
                  <label class="form-label">BMC Password</label>
                  <input v-model="form.idrac_password" type="password" class="form-control" autocomplete="new-password" />
                </div>
              </div>
            </div>

            <div v-if="!form.has_bmc" class="skip-note">
              You can configure BMC settings later from the Proxmox Hosts page.
            </div>
          </div>

          <!-- ── Step 4: Review & Add ── -->
          <div v-if="currentStep === 4" class="step-content">
            <div v-if="addSuccess" class="success-panel">
              <div class="success-icon">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              </div>
              <h3 class="success-title">Host Added Successfully!</h3>
              <p class="success-sub">Your Proxmox datacenter has been added to Depl0y.</p>
              <div class="success-actions">
                <button class="btn btn-primary" @click="goDashboard">Go to Dashboard</button>
                <button class="btn btn-outline" @click="addAnother">Add Another</button>
              </div>
            </div>

            <div v-else>
              <h4 class="section-heading">Review Your Configuration</h4>

              <div class="review-table">
                <div class="review-row">
                  <span class="review-label">Host Name</span>
                  <span class="review-value">{{ form.name || '(not set)' }}</span>
                </div>
                <div class="review-row">
                  <span class="review-label">API URL</span>
                  <span class="review-value">{{ form.api_url }}</span>
                </div>
                <div class="review-row">
                  <span class="review-label">Authentication</span>
                  <span class="review-value">
                    {{ form.auth_method === 'token' ? 'API Token' : 'Password' }}
                    ({{ form.username }})
                  </span>
                </div>
                <div class="review-row">
                  <span class="review-label">SSL Verification</span>
                  <span class="review-value">{{ form.verify_ssl ? 'Enabled' : 'Disabled' }}</span>
                </div>
                <div v-if="testResult && testResult.success" class="review-row">
                  <span class="review-label">Cluster</span>
                  <span class="review-value">{{ testResult.cluster_name || 'Standalone' }} ({{ testResult.node_count }} node{{ testResult.node_count !== 1 ? 's' : '' }})</span>
                </div>
                <div v-if="form.default_storage" class="review-row">
                  <span class="review-label">Default VM Storage</span>
                  <span class="review-value">{{ form.default_storage }}</span>
                </div>
                <div v-if="form.default_iso_storage" class="review-row">
                  <span class="review-label">Default ISO Storage</span>
                  <span class="review-value">{{ form.default_iso_storage }}</span>
                </div>
                <div v-if="form.default_bridge" class="review-row">
                  <span class="review-label">Default Bridge</span>
                  <span class="review-value">{{ form.default_bridge }}</span>
                </div>
                <div class="review-row">
                  <span class="review-label">Monitoring</span>
                  <span class="review-value">{{ form.monitoring_enabled ? 'Enabled (' + pollLabel + ')' : 'Disabled' }}</span>
                </div>
                <div v-if="form.has_bmc && form.idrac_type" class="review-row">
                  <span class="review-label">BMC / iDRAC</span>
                  <span class="review-value">{{ form.idrac_type.toUpperCase() }} @ {{ form.idrac_hostname }}</span>
                </div>
              </div>

              <div v-if="addError" class="error-banner mt-1">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                {{ addError }}
              </div>
            </div>
          </div>

        </div>

        <!-- Footer -->
        <div class="wizard-footer" v-if="!addSuccess">
          <button
            v-if="currentStep > 0"
            class="btn btn-outline"
            @click="prevStep"
            :disabled="adding"
          >
            Back
          </button>
          <div class="footer-right">
            <button
              v-if="currentStep < steps.length - 1"
              class="btn btn-primary"
              @click="nextStep"
              :disabled="!canAdvance"
            >
              Next
            </button>
            <button
              v-if="currentStep === steps.length - 1"
              class="btn btn-primary"
              @click="submitHost"
              :disabled="adding || !canSubmit"
            >
              <span v-if="adding" class="spinner-inline"></span>
              {{ adding ? 'Adding Host...' : 'Add Host' }}
            </button>
          </div>
        </div>

      </div>
    </div>
  </transition>
</template>

<script>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'AddHostWizard',
  props: {
    modelValue: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update:modelValue', 'host-added'],

  setup(props, { emit }) {
    const toast = useToast()
    const router = useRouter()

    const steps = [
      { label: 'Connection' },
      { label: 'Verify Cluster' },
      { label: 'Defaults' },
      { label: 'BMC / iDRAC' },
      { label: 'Review & Add' },
    ]

    const currentStep = ref(0)
    const testing = ref(false)
    const adding = ref(false)
    const testResult = ref(null)
    const addError = ref(null)
    const addSuccess = ref(false)

    const pollOptions = [
      { value: 30, label: '30 seconds' },
      { value: 60, label: '1 minute' },
      { value: 300, label: '5 minutes' },
    ]

    const form = ref({
      name: '',
      api_url: '',
      auth_method: 'token',
      username: 'root@pam',
      token_name: '',
      token_value: '',
      password: '',
      verify_ssl: false,
      // step 2
      default_storage: '',
      default_iso_storage: '',
      default_bridge: '',
      monitoring_enabled: true,
      poll_interval: 60,
      // step 3
      has_bmc: false,
      idrac_type: '',
      idrac_hostname: '',
      idrac_port: 443,
      idrac_username: '',
      idrac_password: '',
      idrac_use_ssh: false,
    })

    // URL normalisation
    const normalizeUrl = () => {
      let url = form.value.api_url.trim()
      if (!url) return
      if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url
      }
      // Add port 8006 if no port present (and URL ends without a path)
      try {
        const parsed = new URL(url)
        if (!parsed.port) {
          parsed.port = '8006'
        }
        url = parsed.origin  // strip any trailing path
      } catch (e) {
        // leave as-is
      }
      form.value.api_url = url
    }

    // Storage / network helpers
    const vmStorages = computed(() => {
      if (!testResult.value || !testResult.value.storages) return []
      return testResult.value.storages.filter(s => {
        const content = s.content || ''
        return content.includes('images') || content.includes('rootdir') || content === ''
      })
    })

    const isoStorages = computed(() => {
      if (!testResult.value || !testResult.value.storages) return []
      return testResult.value.storages.filter(s => {
        const content = s.content || ''
        return content.includes('iso') || content === ''
      })
    })

    const networkBridges = computed(() => {
      if (!testResult.value || !testResult.value.networks) return []
      return testResult.value.networks
    })

    const pollLabel = computed(() => {
      const opt = pollOptions.find(o => o.value === form.value.poll_interval)
      return opt ? opt.label : form.value.poll_interval + 's'
    })

    // Validation
    const canTest = computed(() => {
      if (!form.value.api_url || !form.value.username) return false
      if (form.value.auth_method === 'token') {
        return !!(form.value.token_name && form.value.token_value)
      }
      return !!form.value.password
    })

    const canAdvance = computed(() => {
      if (currentStep.value === 0) {
        return !!(form.value.name && form.value.api_url && testResult.value && testResult.value.success)
      }
      return true
    })

    const canSubmit = computed(() => {
      return !!(form.value.name && form.value.api_url)
    })

    // Step progress line width
    const stepLineWidth = computed(() => {
      const pct = (currentStep.value / (steps.length - 1)) * 100
      return pct + '%'
    })

    // Navigation
    const goToStep = (idx) => {
      currentStep.value = idx
    }

    const nextStep = () => {
      if (currentStep.value < steps.length - 1) {
        currentStep.value++
      }
    }

    const prevStep = () => {
      if (currentStep.value > 0) {
        currentStep.value--
      }
    }

    const maybeClose = () => {
      if (adding.value) return
      emit('update:modelValue', false)
    }

    // Test connection
    const testConnection = async () => {
      normalizeUrl()
      testing.value = true
      testResult.value = null

      try {
        const payload = {
          api_url: form.value.api_url,
          username: form.value.username,
          verify_ssl: form.value.verify_ssl,
        }
        if (form.value.auth_method === 'token') {
          payload.token_name = form.value.token_name
          payload.token_value = form.value.token_value
        } else {
          payload.password = form.value.password
        }

        const response = await api.proxmox.testNewConnection(payload)
        testResult.value = response.data
      } catch (err) {
        testResult.value = {
          success: false,
          error: err.response?.data?.error || err.response?.data?.detail || 'Connection test failed',
        }
      } finally {
        testing.value = false
      }
    }

    // Submit host
    const submitHost = async () => {
      adding.value = true
      addError.value = null

      try {
        // Parse hostname + port from api_url
        normalizeUrl()
        let hostname = ''
        let port = 8006
        try {
          const parsed = new URL(form.value.api_url)
          hostname = parsed.hostname
          port = parseInt(parsed.port) || 8006
        } catch (e) {
          hostname = form.value.api_url
        }

        const payload = {
          name: form.value.name,
          hostname,
          port,
          username: form.value.username,
          verify_ssl: form.value.verify_ssl,
        }

        if (form.value.auth_method === 'token') {
          // Store token as full format if not already
          let tokenId = form.value.token_name
          if (!tokenId.includes('!') && !tokenId.includes('@')) {
            tokenId = `${form.value.username}!${tokenId}`
          }
          payload.api_token_id = tokenId
          payload.api_token_secret = form.value.token_value
        } else {
          payload.password = form.value.password
        }

        // BMC/iDRAC
        if (form.value.has_bmc && form.value.idrac_type) {
          payload.idrac_type = form.value.idrac_type
          payload.idrac_hostname = form.value.idrac_hostname
          payload.idrac_port = form.value.idrac_port
          payload.idrac_username = form.value.idrac_username
          payload.idrac_password = form.value.idrac_password
          payload.idrac_use_ssh = form.value.idrac_use_ssh
        }

        await api.proxmox.createHost(payload)

        addSuccess.value = true
        toast.success('Proxmox host added successfully!')
        emit('host-added')
      } catch (err) {
        const detail = err.response?.data?.detail
        addError.value = typeof detail === 'string' ? detail : 'Failed to add host. Check the console for details.'
      } finally {
        adding.value = false
      }
    }

    const goDashboard = () => {
      emit('update:modelValue', false)
      router.push('/')
    }

    const addAnother = () => {
      // Reset wizard state
      currentStep.value = 0
      testResult.value = null
      addError.value = null
      addSuccess.value = false
      form.value = {
        name: '',
        api_url: '',
        auth_method: 'token',
        username: 'root@pam',
        token_name: '',
        token_value: '',
        password: '',
        verify_ssl: false,
        default_storage: '',
        default_iso_storage: '',
        default_bridge: '',
        monitoring_enabled: true,
        poll_interval: 60,
        has_bmc: false,
        idrac_type: '',
        idrac_hostname: '',
        idrac_port: 443,
        idrac_username: '',
        idrac_password: '',
        idrac_use_ssh: false,
      }
    }

    // Reset when modal opens
    watch(() => props.modelValue, (val) => {
      if (val) {
        addSuccess.value = false
        addError.value = null
      }
    })

    return {
      steps,
      currentStep,
      form,
      testing,
      adding,
      testResult,
      addError,
      addSuccess,
      pollOptions,
      pollLabel,
      canTest,
      canAdvance,
      canSubmit,
      stepLineWidth,
      vmStorages,
      isoStorages,
      networkBridges,
      normalizeUrl,
      testConnection,
      submitHost,
      nextStep,
      prevStep,
      goToStep,
      maybeClose,
      goDashboard,
      addAnother,
    }
  }
}
</script>

<style scoped>
/* ── Overlay & modal ───────────────────────────────────────────────────────── */
.wizard-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.wizard-modal {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
  width: 100%;
  max-width: 640px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Header ────────────────────────────────────────────────────────────────── */
.wizard-header {
  padding: 1.25rem 1.5rem 0;
  border-bottom: 1px solid var(--border-color);
  background: var(--background);
  flex-shrink: 0;
}

.wizard-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.wizard-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

.wizard-close {
  background: none;
  border: none;
  font-size: 1.4rem;
  color: var(--text-secondary);
  cursor: pointer;
  line-height: 1;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  transition: background 0.15s, color 0.15s;
}
.wizard-close:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

/* ── Step track ─────────────────────────────────────────────────────────────── */
.step-track {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  padding: 0 0.25rem;
  margin-bottom: 0.4rem;
}

.step-line {
  position: absolute;
  left: 0.25rem;
  top: 50%;
  transform: translateY(-50%);
  height: 3px;
  background: var(--primary-color);
  border-radius: 2px;
  transition: width 0.35s ease;
  z-index: 0;
}

/* background line */
.step-track::before {
  content: '';
  position: absolute;
  left: 0.25rem;
  right: 0.25rem;
  top: 50%;
  transform: translateY(-50%);
  height: 3px;
  background: var(--border-color);
  border-radius: 2px;
}

.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid var(--border-color);
  background: var(--surface);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-secondary);
  position: relative;
  z-index: 1;
  transition: all 0.2s;
  cursor: default;
  flex-shrink: 0;
}

.step-active {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: #fff;
  transform: scale(1.1);
}

.step-done {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: #fff;
  cursor: pointer;
}

.step-done:hover {
  opacity: 0.85;
}

.step-check {
  font-size: 0.85rem;
}

.step-labels {
  display: flex;
  justify-content: space-between;
  padding: 0 0;
  margin-bottom: 0.75rem;
}

.step-label {
  font-size: 0.65rem;
  color: var(--text-secondary);
  text-align: center;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-label-active {
  color: var(--primary-color);
  font-weight: 600;
}

/* ── Body ───────────────────────────────────────────────────────────────────── */
.wizard-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.step-intro {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-bottom: 1.25rem;
}

/* ── Form elements ──────────────────────────────────────────────────────────── */
.form-group {
  margin-bottom: 1rem;
}

.form-label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.3rem;
}

.req {
  color: #ef4444;
}

.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color 0.15s, box-shadow 0.15s;
  box-sizing: border-box;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.form-hint {
  font-size: 0.72rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
  margin-bottom: 0;
}

.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

/* ── Auth toggle ────────────────────────────────────────────────────────────── */
.auth-toggle {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.25rem;
}

.toggle-btn {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: none;
  background: none;
  border-radius: 0.35rem;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: all 0.15s;
}

.toggle-active {
  background: var(--primary-color);
  color: #fff;
}

.auth-fields {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ── Badges ──────────────────────────────────────────────────────────────────── */
.badge-xs {
  font-size: 0.6rem;
  padding: 0.1rem 0.35rem;
  border-radius: 9999px;
}

.badge-success {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

/* ── Warnings & banners ──────────────────────────────────────────────────────── */
.privilege-warning {
  display: flex;
  gap: 0.6rem;
  align-items: flex-start;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 0.375rem;
  padding: 0.75rem 1rem;
  font-size: 0.8rem;
  color: #b45309;
  margin-bottom: 1rem;
  line-height: 1.5;
}

.privilege-warning svg {
  flex-shrink: 0;
  margin-top: 2px;
  stroke: #d97706;
}

.password-warning {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 0.375rem;
  padding: 0.6rem 0.9rem;
  font-size: 0.78rem;
  color: #dc2626;
  margin-bottom: 1rem;
}

.password-warning svg {
  flex-shrink: 0;
  margin-top: 2px;
  stroke: #ef4444;
}

.info-banner {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 0.375rem;
  padding: 0.65rem 0.9rem;
  font-size: 0.8rem;
  color: #3b82f6;
  margin-top: 0.5rem;
}

.info-banner svg {
  flex-shrink: 0;
  margin-top: 2px;
  stroke: #3b82f6;
}

.warn-banner {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: 0.375rem;
  padding: 0.65rem 0.9rem;
  font-size: 0.8rem;
  color: #d97706;
  margin-top: 0.75rem;
}

.warn-banner svg {
  flex-shrink: 0;
  margin-top: 2px;
  stroke: #d97706;
}

.error-banner {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 0.375rem;
  padding: 0.65rem 0.9rem;
  font-size: 0.8rem;
  color: #dc2626;
}

.error-banner svg {
  flex-shrink: 0;
  margin-top: 2px;
  stroke: #ef4444;
}

.mt-1 { margin-top: 1rem; }

/* ── SSL toggle ─────────────────────────────────────────────────────────────── */
.ssl-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.ssl-hint {
  font-size: 0.72rem;
  color: var(--text-secondary);
}

/* ── Toggle switch ──────────────────────────────────────────────────────────── */
.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
  user-select: none;
}

.toggle-switch {
  position: relative;
  width: 36px;
  height: 20px;
  background: var(--border-color);
  border-radius: 10px;
  transition: background 0.2s;
  flex-shrink: 0;
}

.toggle-on {
  background: var(--primary-color);
}

.toggle-thumb {
  position: absolute;
  left: 2px;
  top: 2px;
  width: 16px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  transition: left 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.25);
}

.toggle-on .toggle-thumb {
  left: 18px;
}

/* ── Test row ────────────────────────────────────────────────────────────────── */
.test-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 0.25rem;
  margin-bottom: 0.5rem;
}

.test-result {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  font-weight: 500;
}

.test-ok { color: #22c55e; }
.test-ok svg { stroke: #22c55e; }

.test-fail { color: #ef4444; }
.test-fail svg { stroke: #ef4444; }

/* ── Cluster summary ─────────────────────────────────────────────────────────── */
.cluster-summary-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.summary-card {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.summary-label {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.summary-value {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.cluster-no-data {
  color: var(--text-secondary);
  font-size: 0.875rem;
  text-align: center;
  padding: 2rem;
}

/* ── Node chips ──────────────────────────────────────────────────────────────── */
.section-heading {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  margin: 0 0 0.6rem 0;
}

.node-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.node-chip {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.75rem;
  border-radius: 9999px;
  border: 1px solid var(--border-color);
  font-size: 0.8rem;
  background: var(--background);
}

.chip-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.chip-online .chip-dot { background: #22c55e; }
.chip-offline .chip-dot { background: #ef4444; }

.chip-name {
  font-weight: 600;
  color: var(--text-primary);
}

.chip-status {
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.chip-local {
  font-size: 0.65rem;
  background: rgba(59, 130, 246, 0.12);
  color: #3b82f6;
  border-radius: 9999px;
  padding: 0.05rem 0.35rem;
  font-weight: 600;
}

/* ── Poll options ────────────────────────────────────────────────────────────── */
.poll-options {
  display: flex;
  gap: 1.25rem;
}

.poll-option {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}

.monitor-row {
  margin-top: 0.35rem;
}

/* ── BMC ─────────────────────────────────────────────────────────────────────── */
.bmc-toggle {
  font-size: 0.9rem;
}

.bmc-fields {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  margin-top: 0.75rem;
}

.skip-note {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-top: 1rem;
  font-style: italic;
}

/* ── Review table ────────────────────────────────────────────────────────────── */
.review-table {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
}

.review-row {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.85rem;
}

.review-row:last-child {
  border-bottom: none;
}

.review-label {
  width: 160px;
  flex-shrink: 0;
  font-weight: 600;
  color: var(--text-secondary);
}

.review-value {
  color: var(--text-primary);
  word-break: break-all;
}

/* ── Success ─────────────────────────────────────────────────────────────────── */
.success-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem 1rem;
  text-align: center;
}

.success-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
}

.success-title {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.success-sub {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin: 0;
}

.success-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 0.5rem;
}

/* ── Footer ──────────────────────────────────────────────────────────────────── */
.wizard-footer {
  padding: 0.85rem 1.5rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  background: var(--background);
}

.footer-right {
  display: flex;
  gap: 0.5rem;
  margin-left: auto;
}

/* ── Spinner ─────────────────────────────────────────────────────────────────── */
.spinner-inline {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-right: 0.35rem;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Transition ──────────────────────────────────────────────────────────────── */
.wizard-fade-enter-active,
.wizard-fade-leave-active {
  transition: opacity 0.2s ease;
}
.wizard-fade-enter-from,
.wizard-fade-leave-to {
  opacity: 0;
}

/* ── Buttons ─────────────────────────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.5rem 1.1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--primary-color);
  color: #fff;
  border-color: var(--primary-color);
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-outline {
  background: transparent;
  color: var(--text-primary);
  border-color: var(--border-color);
}

.btn-outline:hover:not(:disabled) {
  background: var(--background);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

/* ── Responsive ──────────────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .wizard-modal {
    max-height: 95vh;
    border-radius: 0.75rem;
  }

  .cluster-summary-cards {
    grid-template-columns: 1fr;
  }

  .form-row-2 {
    grid-template-columns: 1fr;
  }

  .step-labels {
    display: none;
  }
}
</style>
