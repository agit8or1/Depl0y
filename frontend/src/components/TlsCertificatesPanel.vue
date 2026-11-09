<template>
  <div class="card">
    <div class="card-header">
      <h3>TLS certificates</h3>
      <span class="adv-pill">Admin only</span>
    </div>
    <div class="card-body">
      <p class="text-muted text-sm">
        Proxmox, PBS, BMC and VMware hosts that aren't set to "verify SSL" are checked against the certificate
        approved here. A host with a publicly trusted certificate (for example Let's Encrypt) is marked
        <strong>CA</strong> and must keep presenting a trusted certificate, so renewals just work. Other hosts are
        <strong>pinned</strong> to one exact certificate; a different one is refused before any credentials are sent
        and listed as <strong>pending</strong>. Before approving one, compare its fingerprint with
        <code>openssl x509 -noout -fingerprint -sha256 -in /etc/pve/local/pveproxy-ssl.pem</code>
        (or <code>pve-ssl.pem</code>) on the node, or the certificate shown in the BMC's web UI.
      </p>

      <div class="keys-toolbar">
        <label class="text-sm">
          Unknown hosts:
          <select v-model="policy" @change="savePolicy" :disabled="policyLoading" class="form-control form-control-sm">
            <option value="tofu">Trust the first certificate seen (TOFU)</option>
            <option value="strict">Refuse until an admin approves</option>
          </select>
        </label>
        <form class="scan-form" @submit.prevent="scan">
          <input v-model.trim="scanHost" class="form-control form-control-sm" placeholder="Host or IP" required maxlength="255" />
          <input v-model.number="scanPort" type="number" min="1" max="65535" class="form-control form-control-sm port" />
          <button class="btn btn-outline btn-sm" :disabled="scanning">{{ scanning ? 'Reading…' : 'Read certificate' }}</button>
        </form>
        <button class="btn btn-outline btn-sm" @click="load" :disabled="loading">Refresh</button>
      </div>

      <p v-if="!loading && !certs.length" class="text-muted text-sm">No TLS certificates recorded yet.</p>
      <div v-else class="keys-table-wrap">
        <table class="keys-table">
          <thead>
            <tr><th>Host</th><th>Certificate</th><th>SHA-256 fingerprint</th><th>Status</th><th>Last seen</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="c in certs" :key="c.id" :class="{ 'row-pending': c.status === 'pending' }">
              <td>
                {{ c.host }}<span class="text-muted">:{{ c.port }}</span>
                <div v-for="u in c.used_by" :key="u" class="text-muted text-xs">{{ u }}</div>
              </td>
              <td class="text-sm">
                <div>{{ c.subject || '—' }}</div>
                <div class="text-muted text-xs">Issuer: {{ c.issuer || '—' }}</div>
                <div class="text-muted text-xs">Expires: {{ fmt(c.not_after) }}</div>
              </td>
              <td><code class="fp">{{ c.fingerprint }}</code></td>
              <td>
                <span :class="['badge', c.status === 'approved' ? 'badge-success' : 'badge-warning']">{{ c.status }}</span>
                <span v-if="c.status === 'approved'" class="text-muted text-xs"> · {{ c.mode === 'ca' ? 'CA' : 'pinned' }}</span>
                <span v-if="c.automatic" class="text-muted text-xs" title="Approved automatically (first use or CA-issued renewal)"> (automatic)</span>
              </td>
              <td class="text-sm">{{ fmt(c.last_seen) }}</td>
              <td class="actions">
                <button v-if="c.status === 'pending'" class="btn btn-primary btn-sm" @click="approve(c)">Approve</button>
                <button class="btn btn-outline btn-sm" @click="remove(c)">{{ c.status === 'pending' ? 'Reject' : 'Forget' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'TlsCertificatesPanel',
  setup() {
    const toast = useToast()
    const certs = ref([])
    const loading = ref(false)
    const policy = ref('tofu')
    const policyLoading = ref(false)
    const scanHost = ref('')
    const scanPort = ref(8006)
    const scanning = ref(false)

    const errText = (e, fallback) => e.response?.data?.detail || fallback
    const fmt = (dt) => (dt ? new Date(dt + 'Z').toLocaleString() : '—')

    const load = async () => {
      loading.value = true
      try {
        const [c, p] = await Promise.all([api.tlsCertificates.list(), api.tlsCertificates.getPolicy()])
        certs.value = c.data
        policy.value = p.data.policy
      } catch (e) {
        toast.error(errText(e, 'Failed to load TLS certificates'))
      } finally {
        loading.value = false
      }
    }

    const savePolicy = async () => {
      policyLoading.value = true
      try {
        await api.tlsCertificates.setPolicy(policy.value)
        toast.success('TLS certificate policy saved')
      } catch (e) {
        toast.error(errText(e, 'Failed to save policy'))
        await load()
      } finally {
        policyLoading.value = false
      }
    }

    const scan = async () => {
      scanning.value = true
      try {
        const r = await api.tlsCertificates.scan(scanHost.value, scanPort.value || 443)
        toast.info(`Read certificate ${r.data.fingerprint} (${r.data.status})`)
        await load()
      } catch (e) {
        toast.error(errText(e, 'Could not read the certificate'))
      } finally {
        scanning.value = false
      }
    }

    const approve = async (c) => {
      const replaces = certs.value.some(o => o.host === c.host && o.port === c.port && o.status === 'approved')
      const msg = `Pin this certificate for ${c.host}:${c.port}?\n\n${c.subject || ''}\nSHA-256 ${c.fingerprint}\n\n` +
        'Only approve it if this matches the fingerprint of the certificate on the host itself.' +
        (replaces ? '\n\nThe currently approved certificate for this host will be removed.' : '')
      if (!window.confirm(msg)) return
      try {
        await api.tlsCertificates.approve(c.id)
        toast.success('Certificate approved')
        await load()
      } catch (e) {
        toast.error(errText(e, 'Failed to approve certificate'))
      }
    }

    const remove = async (c) => {
      const msg = c.status === 'pending'
        ? `Reject the pending certificate ${c.fingerprint} for ${c.host}:${c.port}?`
        : `Forget the approved certificate for ${c.host}:${c.port}? The next connection will be treated as a new host.`
      if (!window.confirm(msg)) return
      try {
        await api.tlsCertificates.remove(c.id)
        await load()
      } catch (e) {
        toast.error(errText(e, 'Failed to remove certificate'))
      }
    }

    onMounted(load)
    return { certs, loading, policy, policyLoading, scanHost, scanPort, scanning, load, savePolicy, scan, approve, remove, fmt }
  }
}
</script>

<style scoped>
.keys-toolbar { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; margin: 0.75rem 0; }
.keys-toolbar label { display: flex; gap: 0.5rem; align-items: center; }
.scan-form { display: flex; gap: 0.4rem; align-items: center; }
.scan-form .port { width: 5.5rem; }
.keys-table-wrap { overflow-x: auto; }
.keys-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
.keys-table th, .keys-table td { padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--border-color, #e5e7eb); text-align: left; vertical-align: top; }
.keys-table .fp { font-size: 0.7rem; word-break: break-all; }
.keys-table .actions { white-space: nowrap; display: flex; gap: 0.35rem; }
.row-pending { background: var(--warning-bg, rgba(234, 179, 8, 0.08)); }
</style>
