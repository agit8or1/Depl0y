<template>
  <div class="ci-editor-page">
    <div class="page-header">
      <div class="header-left">
        <router-link :to="backLink" class="btn btn-outline btn-sm back-btn">
          &larr; Back to VM
        </router-link>
        <div>
          <h2 class="page-title">Cloud-Init Configurator</h2>
          <p class="page-subtitle">
            <span class="mono">{{ node }} / {{ vmid }}</span>
            <span v-if="vmName"> &mdash; {{ vmName }}</span>
          </p>
        </div>
      </div>
    </div>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>

    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <span>Loading VM config...</span>
    </div>

    <div v-else class="editor-layout">
      <!-- Left: form -->
      <div class="editor-form">

        <!-- User Config -->
        <div class="section-card">
          <h3 class="section-title">User Configuration</h3>

          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="form.ciuser" class="form-control" placeholder="ubuntu" autocomplete="off" />
            <p class="hint-text">Default cloud-init user. Leave blank to keep OS default.</p>
          </div>

          <div class="form-group">
            <label class="form-label">Password</label>
            <div class="input-with-toggle">
              <input
                v-model="form.cipassword"
                :type="showPassword ? 'text' : 'password'"
                class="form-control"
                placeholder="Leave blank to keep existing"
                autocomplete="new-password"
              />
              <button class="toggle-vis-btn" @click="showPassword = !showPassword" type="button">
                {{ showPassword ? 'Hide' : 'Show' }}
              </button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              <input v-model="form.lockPasswd" type="checkbox" class="form-check-input" />
              Lock password login (SSH key only)
            </label>
          </div>

          <div class="form-group">
            <label class="form-label">SSH Public Keys</label>
            <textarea
              v-model="form.sshkeys"
              class="form-control mono-input"
              rows="5"
              placeholder="ssh-rsa AAAA...&#10;ssh-ed25519 AAAA..."
            ></textarea>
            <p class="hint-text">One key per line. These are injected into ~/.ssh/authorized_keys.</p>
          </div>
        </div>

        <!-- Network Config -->
        <div class="section-card">
          <h3 class="section-title">Network Configuration</h3>

          <div v-for="(iface, idx) in form.interfaces" :key="idx" class="iface-block">
            <div class="iface-header">
              <strong>Interface {{ idx }} (ipconfig{{ idx }})</strong>
              <button
                v-if="idx > 0"
                class="btn btn-danger btn-xs"
                @click="removeInterface(idx)"
                type="button"
              >Remove</button>
            </div>

            <div class="form-group">
              <label class="form-label">IP Mode</label>
              <div class="radio-group-inline">
                <label class="radio-label-inline">
                  <input type="radio" v-model="iface.mode" value="dhcp" />
                  DHCP
                </label>
                <label class="radio-label-inline">
                  <input type="radio" v-model="iface.mode" value="static" />
                  Static
                </label>
                <label class="radio-label-inline">
                  <input type="radio" v-model="iface.mode" value="none" />
                  None
                </label>
              </div>
            </div>

            <template v-if="iface.mode === 'static'">
              <div class="grid-2">
                <div class="form-group">
                  <label class="form-label">IP Address / CIDR</label>
                  <input v-model="iface.ip" class="form-control" placeholder="192.168.1.100/24" />
                </div>
                <div class="form-group">
                  <label class="form-label">Gateway</label>
                  <input v-model="iface.gw" class="form-control" placeholder="192.168.1.1" />
                </div>
              </div>

              <!-- IPv6 -->
              <div class="grid-2">
                <div class="form-group">
                  <label class="form-label">IPv6 Address / Prefix (optional)</label>
                  <input v-model="iface.ip6" class="form-control" placeholder="2001:db8::1/64" />
                </div>
                <div class="form-group">
                  <label class="form-label">IPv6 Gateway (optional)</label>
                  <input v-model="iface.gw6" class="form-control" placeholder="2001:db8::1" />
                </div>
              </div>
            </template>
          </div>

          <button
            v-if="form.interfaces.length < 4"
            class="btn btn-outline btn-sm mt-2"
            @click="addInterface"
            type="button"
          >+ Add Interface</button>
        </div>

        <!-- DNS Config -->
        <div class="section-card">
          <h3 class="section-title">DNS Configuration</h3>

          <div class="form-group">
            <label class="form-label">Search Domain</label>
            <input v-model="form.searchdomain" class="form-control" placeholder="example.com" />
          </div>

          <div class="form-group">
            <label class="form-label">Nameservers</label>
            <input v-model="form.nameserver" class="form-control" placeholder="8.8.8.8 8.8.4.4" />
            <p class="hint-text">Space-separated list of DNS servers.</p>
          </div>
        </div>

        <!-- Boot Options -->
        <div class="section-card">
          <h3 class="section-title">Boot Options</h3>

          <div class="form-group">
            <label class="form-label">
              <input v-model="form.ciupgrade" type="checkbox" class="form-check-input" />
              Upgrade packages on first boot
            </label>
            <p class="hint-text">Runs <code>apt upgrade</code> (or equivalent) on first boot.</p>
          </div>
        </div>

        <!-- Custom User-Data -->
        <div class="section-card">
          <h3 class="section-title">Custom User-Data YAML</h3>
          <p class="section-desc">
            Raw cloud-init user-data. Must start with <code>#cloud-config</code>.
            Stored via <code>cicustom</code> if a snippet storage is configured.
          </p>

          <div class="form-group">
            <label class="form-label">User-Data</label>
            <textarea
              v-model="form.customUserdata"
              class="form-control mono-input"
              rows="10"
              placeholder="#cloud-config&#10;packages:&#10;  - htop&#10;  - curl"
            ></textarea>
          </div>

          <div class="form-group" v-if="form.customUserdata">
            <label class="form-label">Snippet Storage (for cicustom)</label>
            <input v-model="form.snippetStorage" class="form-control" placeholder="local" />
            <p class="hint-text">Storage that supports snippets content. The YAML will be uploaded there.</p>
          </div>
        </div>

        <!-- Actions -->
        <div v-if="applyError" class="alert alert-danger mt-2">{{ applyError }}</div>
        <div v-if="applySuccess" class="alert alert-success mt-2">{{ applySuccess }}</div>

        <div class="action-bar">
          <button
            class="btn btn-primary"
            @click="applyConfig"
            :disabled="applying"
          >
            {{ applying ? 'Applying...' : 'Apply Configuration' }}
          </button>
          <button
            class="btn btn-warning"
            @click="regenerate"
            :disabled="regenerating"
            title="Force Proxmox to regenerate the cloud-init ISO drive"
          >
            {{ regenerating ? 'Regenerating...' : 'Regenerate Cloud-Init Disk' }}
          </button>
          <router-link :to="backLink" class="btn btn-outline">Cancel</router-link>
        </div>
      </div>

      <!-- Right: preview -->
      <div class="preview-panel">
        <div class="preview-header">
          <h3>YAML Preview</h3>
          <button class="btn btn-outline btn-xs" @click="copyPreview" type="button">
            {{ copied ? 'Copied!' : 'Copy' }}
          </button>
        </div>
        <pre class="preview-code">{{ previewYaml }}</pre>

        <div class="proxmox-params-section">
          <h4>Proxmox Parameters</h4>
          <table class="params-table">
            <tbody>
              <tr v-for="(val, key) in proxmoxParams" :key="key">
                <td class="param-key">{{ key }}</td>
                <td class="param-val">{{ val }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'

const route = useRoute()

const hostId = computed(() => route.query.hostId)
const node = computed(() => route.query.node)
const vmid = computed(() => route.query.vmid)

const backLink = computed(() =>
  `/proxmox/${hostId.value}/nodes/${node.value}/vms/${vmid.value}`
)

const vmName = ref('')
const loading = ref(true)
const loadError = ref('')
const applying = ref(false)
const regenerating = ref(false)
const applyError = ref('')
const applySuccess = ref('')
const showPassword = ref(false)
const copied = ref(false)

const form = ref({
  ciuser: '',
  cipassword: '',
  lockPasswd: false,
  sshkeys: '',
  interfaces: [{ mode: 'dhcp', ip: '', gw: '', ip6: '', gw6: '' }],
  searchdomain: '',
  nameserver: '',
  ciupgrade: false,
  customUserdata: '',
  snippetStorage: 'local',
})

// ── Load current config ────────────────────────────────────────────────────────

async function loadConfig() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await api.pveVm.getConfig(hostId.value, node.value, vmid.value)
    const cfg = res.data || {}
    vmName.value = cfg.name || ''
    form.value.ciuser = cfg.ciuser || ''
    // Never pre-fill password (security)
    form.value.cipassword = ''
    // SSH keys: proxmox stores URL-encoded
    form.value.sshkeys = cfg.sshkeys ? decodeURIComponent(cfg.sshkeys) : ''
    form.value.searchdomain = cfg.searchdomain || ''
    form.value.nameserver = cfg.nameserver || ''
    form.value.ciupgrade = cfg.ciupgrade === 1 || cfg.ciupgrade === true

    // Parse ipconfig0, ipconfig1, ...
    const ifaces = []
    for (let i = 0; i < 4; i++) {
      const raw = cfg[`ipconfig${i}`]
      if (!raw && i > 0) break
      if (!raw) {
        ifaces.push({ mode: 'dhcp', ip: '', gw: '', ip6: '', gw6: '' })
        break
      }
      ifaces.push(parseIpconfig(raw))
    }
    if (ifaces.length === 0) {
      ifaces.push({ mode: 'dhcp', ip: '', gw: '', ip6: '', gw6: '' })
    }
    form.value.interfaces = ifaces
  } catch (err) {
    loadError.value = err?.response?.data?.detail || 'Failed to load VM config.'
  } finally {
    loading.value = false
  }
}

function parseIpconfig(raw) {
  // Format: ip=192.168.1.1/24,gw=192.168.1.254 or dhcp or ip6=...,gw6=...
  const result = { mode: 'dhcp', ip: '', gw: '', ip6: '', gw6: '' }
  if (!raw) return result
  if (raw === 'dhcp') { result.mode = 'dhcp'; return result }
  if (raw === '') { result.mode = 'none'; return result }
  const parts = raw.split(',')
  let hasStatic = false
  for (const p of parts) {
    const [k, v] = p.split('=')
    if (k === 'ip' && v !== 'dhcp') { result.ip = v; hasStatic = true }
    else if (k === 'ip' && v === 'dhcp') { result.mode = 'dhcp' }
    else if (k === 'gw') { result.gw = v }
    else if (k === 'ip6' && v !== 'dhcp') { result.ip6 = v; hasStatic = true }
    else if (k === 'ip6' && v === 'dhcp') {} // ignore
    else if (k === 'gw6') { result.gw6 = v }
  }
  if (hasStatic) result.mode = 'static'
  return result
}

function buildIpconfig(iface) {
  if (iface.mode === 'none') return ''
  if (iface.mode === 'dhcp') return 'ip=dhcp'
  const parts = []
  if (iface.ip) parts.push(`ip=${iface.ip}`)
  if (iface.gw) parts.push(`gw=${iface.gw}`)
  if (iface.ip6) parts.push(`ip6=${iface.ip6}`)
  if (iface.gw6) parts.push(`gw6=${iface.gw6}`)
  return parts.join(',')
}

// ── Computed preview ─────────────────────────────────────────────────────────

const previewYaml = computed(() => {
  const lines = ['#cloud-config']
  if (form.value.ciuser) lines.push(`users:\n  - name: ${form.value.ciuser}`)
  if (form.value.lockPasswd) {
    lines.push('    lock_passwd: true')
  }
  if (form.value.sshkeys.trim()) {
    lines.push('    ssh_authorized_keys:')
    form.value.sshkeys.trim().split('\n').forEach(k => {
      if (k.trim()) lines.push(`      - ${k.trim()}`)
    })
  }
  if (form.value.ciupgrade) {
    lines.push('package_upgrade: true')
  }
  if (form.value.nameserver) {
    lines.push(`manage_resolv_conf: true\nresolv_conf:\n  nameservers:`)
    form.value.nameserver.split(/[\s,]+/).filter(Boolean).forEach(ns => {
      lines.push(`    - ${ns}`)
    })
    if (form.value.searchdomain) {
      lines.push(`  searchdomains:\n    - ${form.value.searchdomain}`)
    }
  }
  if (form.value.customUserdata.trim()) {
    lines.push('\n# --- Custom user-data ---')
    lines.push(form.value.customUserdata.trim())
  }
  return lines.join('\n')
})

const proxmoxParams = computed(() => {
  const params = {}
  if (form.value.ciuser) params.ciuser = form.value.ciuser
  if (form.value.cipassword) params.cipassword = '(hidden)'
  if (form.value.sshkeys.trim()) params.sshkeys = `${form.value.sshkeys.trim().split('\n').length} key(s)`
  form.value.interfaces.forEach((iface, idx) => {
    const val = buildIpconfig(iface)
    if (val) params[`ipconfig${idx}`] = val
  })
  if (form.value.nameserver) params.nameserver = form.value.nameserver
  if (form.value.searchdomain) params.searchdomain = form.value.searchdomain
  if (form.value.ciupgrade) params.ciupgrade = '1'
  return params
})

// ── Apply ────────────────────────────────────────────────────────────────────

async function applyConfig() {
  applying.value = true
  applyError.value = ''
  applySuccess.value = ''
  try {
    const payload = {}
    if (form.value.ciuser !== undefined) payload.ciuser = form.value.ciuser || null
    if (form.value.cipassword) payload.cipassword = form.value.cipassword
    if (form.value.sshkeys.trim()) payload.sshkeys = form.value.sshkeys.trim()
    form.value.interfaces.forEach((iface, idx) => {
      const val = buildIpconfig(iface)
      if (idx === 0) payload.ipconfig0 = val
      else if (val) payload[`ipconfig${idx}`] = val
    })
    if (form.value.nameserver) payload.nameserver = form.value.nameserver
    if (form.value.searchdomain) payload.searchdomain = form.value.searchdomain
    payload.ciupgrade = form.value.ciupgrade

    await api.pveVm.updateCloudInit(hostId.value, node.value, vmid.value, payload)
    applySuccess.value = 'Cloud-init configuration applied. Regenerate the cloud-init disk for changes to take effect on next boot.'
  } catch (err) {
    applyError.value = err?.response?.data?.detail || 'Failed to apply config.'
  } finally {
    applying.value = false
  }
}

async function regenerate() {
  regenerating.value = true
  applyError.value = ''
  applySuccess.value = ''
  try {
    await api.pveVm.regenerateCloudinit(hostId.value, node.value, vmid.value)
    applySuccess.value = 'Cloud-init disk regenerated successfully.'
  } catch (err) {
    applyError.value = err?.response?.data?.detail || 'Failed to regenerate cloud-init disk.'
  } finally {
    regenerating.value = false
  }
}

// ── Interface helpers ─────────────────────────────────────────────────────────

function addInterface() {
  form.value.interfaces.push({ mode: 'dhcp', ip: '', gw: '', ip6: '', gw6: '' })
}

function removeInterface(idx) {
  form.value.interfaces.splice(idx, 1)
}

// ── Copy preview ──────────────────────────────────────────────────────────────

async function copyPreview() {
  try {
    await navigator.clipboard.writeText(previewYaml.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {}
}

// ── Init ──────────────────────────────────────────────────────────────────────

onMounted(() => {
  if (hostId.value && node.value && vmid.value) {
    loadConfig()
  } else {
    loadError.value = 'Missing hostId, node, or vmid query parameters.'
    loading.value = false
  }
})
</script>

<style scoped>
.ci-editor-page {
  padding: 1.5rem;
  max-width: 1300px;
}

.page-header {
  margin-bottom: 1.5rem;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.back-btn {
  flex-shrink: 0;
}

.page-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.page-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0.2rem 0 0;
}

.mono {
  font-family: monospace;
}

/* ── Layout ─────────────────────────────────────────────────────────────── */
.editor-layout {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 1.5rem;
  align-items: start;
}

@media (max-width: 1100px) {
  .editor-layout {
    grid-template-columns: 1fr;
  }
}

.editor-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* ── Section Cards ──────────────────────────────────────────────────────── */
.section-card {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
}

.section-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 1rem;
  padding-bottom: 0.6rem;
  border-bottom: 1px solid var(--border-color);
}

.section-desc {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-bottom: 1rem;
}

/* ── Form controls ──────────────────────────────────────────────────────── */
.form-group {
  margin-bottom: 1rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-label {
  display: block;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.35rem;
}

.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 0.875rem;
  color: var(--text-primary);
  min-height: 36px;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.mono-input {
  font-family: monospace;
  font-size: 0.8rem;
}

.form-check-input {
  margin-right: 0.4rem;
  accent-color: var(--primary-color);
}

.hint-text {
  font-size: 0.775rem;
  color: var(--text-secondary);
  margin: 0.25rem 0 0;
}

.hint-text code {
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  padding: 0 3px;
  font-family: monospace;
  font-size: 0.78rem;
}

code {
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  padding: 0 3px;
  font-family: monospace;
  font-size: 0.82rem;
}

/* ── Password toggle ────────────────────────────────────────────────────── */
.input-with-toggle {
  display: flex;
  gap: 0.5rem;
}

.input-with-toggle .form-control {
  flex: 1;
}

.toggle-vis-btn {
  padding: 0.4rem 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  cursor: pointer;
  white-space: nowrap;
}

.toggle-vis-btn:hover {
  color: var(--text-primary);
  border-color: var(--primary-color);
}

/* ── Radio group ────────────────────────────────────────────────────────── */
.radio-group-inline {
  display: flex;
  gap: 1rem;
}

.radio-label-inline {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}

.radio-label-inline input[type="radio"] {
  accent-color: var(--primary-color);
}

/* ── Grid ───────────────────────────────────────────────────────────────── */
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

/* ── Interface block ────────────────────────────────────────────────────── */
.iface-block {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 0.85rem 1rem;
  margin-bottom: 0.75rem;
  background: rgba(255, 255, 255, 0.02);
}

.iface-block:last-of-type {
  margin-bottom: 0;
}

.iface-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  font-size: 0.875rem;
}

/* ── Buttons ────────────────────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.15s;
  white-space: nowrap;
  color: var(--text-primary);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-sm {
  padding: 0.35rem 0.75rem;
  font-size: 0.82rem;
}

.btn-xs {
  padding: 0.2rem 0.5rem;
  font-size: 0.75rem;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
  border-color: #2563eb;
}

.btn-outline {
  background: transparent;
  border-color: var(--border-color);
}

.btn-outline:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.06);
}

.btn-warning {
  background: rgba(234, 179, 8, 0.15);
  color: #fbbf24;
  border-color: rgba(234, 179, 8, 0.4);
}

.btn-warning:hover:not(:disabled) {
  background: rgba(234, 179, 8, 0.25);
}

.btn-danger {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.3);
}

.btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.25);
}

.action-bar {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.mt-2 { margin-top: 0.5rem; }

/* ── Alerts ─────────────────────────────────────────────────────────────── */
.alert {
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
}

.alert-danger {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.alert-success {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #34d399;
}

/* ── Loading ────────────────────────────────────────────────────────────── */
.loading-state {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 4rem 0;
  color: var(--text-secondary);
  justify-content: center;
}

.loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Preview Panel ──────────────────────────────────────────────────────── */
.preview-panel {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  position: sticky;
  top: 1.5rem;
  max-height: calc(100vh - 4rem);
  overflow-y: auto;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--background);
}

.preview-header h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-primary);
}

.preview-code {
  margin: 0;
  padding: 1rem;
  font-family: monospace;
  font-size: 0.78rem;
  line-height: 1.55;
  color: #a5f3fc;
  background: #0d1117;
  white-space: pre-wrap;
  word-break: break-all;
  border-bottom: 1px solid var(--border-color);
}

.proxmox-params-section {
  padding: 1rem;
}

.proxmox-params-section h4 {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 0.75rem;
}

.params-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}

.params-table td {
  padding: 0.3rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.param-key {
  font-family: monospace;
  color: #60a5fa;
  padding-right: 0.75rem;
  white-space: nowrap;
  font-weight: 600;
}

.param-val {
  font-family: monospace;
  color: var(--text-primary);
  word-break: break-all;
}
</style>
