<template>
  <div class="card">
    <div class="card-header">
      <h3>SSH host keys</h3>
      <span class="adv-pill">Admin only</span>
    </div>
    <div class="card-body">
      <p class="text-muted text-sm">
        depl0y only connects over SSH to hosts whose server key is approved here. A different key is
        refused before any password is sent and listed as <strong>pending</strong>. Before approving
        one, compare its fingerprint with <code>ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub</code>
        (or the matching key type) run on the host itself. Every change is recorded in the audit log.
      </p>

      <div v-if="unconfirmed.length" class="first-use-callout" role="status">
        <p class="text-sm">
          <strong>{{ unconfirmed.length }} host key{{ unconfirmed.length === 1 ? ' was' : 's were' }} trusted on first connection</strong>
          and {{ unconfirmed.length === 1 ? 'has' : 'have' }} not been confirmed by an admin:
          {{ unconfirmed.map(k => k.host + (k.port !== 22 ? ':' + k.port : '')).join(', ') }}.
          Compare each fingerprint with the host, then click <strong>Confirm</strong> — or <strong>Forget</strong> it if it does not match.
        </p>
      </div>

      <div class="keys-toolbar">
        <label class="text-sm">
          Unknown hosts:
          <select v-model="policy" @change="savePolicy" :disabled="policyLoading" class="form-control form-control-sm">
            <option value="tofu">Trust the first key seen (TOFU)</option>
            <option value="strict">Refuse until an admin approves</option>
          </select>
        </label>
        <form class="scan-form" @submit.prevent="scan">
          <input v-model.trim="scanHost" class="form-control form-control-sm" placeholder="Host or IP" required maxlength="255" />
          <input v-model.number="scanPort" type="number" min="1" max="65535" class="form-control form-control-sm port" />
          <button class="btn btn-outline btn-sm" :disabled="scanning">{{ scanning ? 'Reading…' : 'Read key' }}</button>
        </form>
        <button class="btn btn-outline btn-sm" @click="load" :disabled="loading">Refresh</button>
      </div>

      <p v-if="!loading && !keys.length" class="text-muted text-sm">No SSH host keys recorded yet.</p>
      <div v-else class="keys-table-wrap">
        <table class="keys-table">
          <thead>
            <tr><th>Host</th><th>Key</th><th>Fingerprint</th><th>Status</th><th>Last seen</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="k in keys" :key="k.id" :class="{ 'row-pending': k.status === 'pending' || k.trusted_on_first_use }">
              <td>{{ k.host }}<span v-if="k.port !== 22" class="text-muted">:{{ k.port }}</span></td>
              <td class="text-sm">{{ k.key_type }}</td>
              <td><code class="fp">{{ k.fingerprint }}</code></td>
              <td>
                <span :class="['badge', k.status === 'approved' ? 'badge-success' : 'badge-warning']">{{ k.status }}</span>
                <div v-if="k.trusted_on_first_use" class="text-xs" title="Approved automatically on first connection; no admin has confirmed the fingerprint yet">
                  <span class="badge badge-warning">unconfirmed</span> trusted on first use {{ fmt(k.first_seen) }}
                </div>
              </td>
              <td class="text-sm">{{ fmt(k.last_seen) }}</td>
              <td class="actions">
                <button v-if="k.status === 'pending'" class="btn btn-primary btn-sm" @click="approve(k)">Approve</button>
                <button v-if="k.trusted_on_first_use" class="btn btn-primary btn-sm" @click="approve(k)">Confirm</button>
                <button class="btn btn-outline btn-sm" @click="remove(k)">{{ k.status === 'pending' ? 'Reject' : 'Forget' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'SshHostKeysPanel',
  setup() {
    const toast = useToast()
    const keys = ref([])
    const loading = ref(false)
    const policy = ref('tofu')
    const policyLoading = ref(false)
    const scanHost = ref('')
    const scanPort = ref(22)
    const scanning = ref(false)

    const errText = (e, fallback) => e.response?.data?.detail || fallback
    const fmt = (dt) => (dt ? new Date(dt + 'Z').toLocaleString() : '—')

    const load = async () => {
      loading.value = true
      try {
        const [k, p] = await Promise.all([api.sshHostKeys.list(), api.sshHostKeys.getPolicy()])
        keys.value = k.data
        policy.value = p.data.policy
      } catch (e) {
        toast.error(errText(e, 'Failed to load SSH host keys'))
      } finally {
        loading.value = false
      }
    }

    const savePolicy = async () => {
      policyLoading.value = true
      try {
        await api.sshHostKeys.setPolicy(policy.value)
        toast.success('SSH host key policy saved')
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
        const r = await api.sshHostKeys.scan(scanHost.value, scanPort.value || 22)
        toast.info(`Read ${r.data.key_type} key ${r.data.fingerprint} (${r.data.status})`)
        await load()
      } catch (e) {
        toast.error(errText(e, 'Could not read the host key'))
      } finally {
        scanning.value = false
      }
    }

    const unconfirmed = computed(() => keys.value.filter(k => k.trusted_on_first_use))

    const approve = async (k) => {
      const replaces = keys.value.some(o => o.host === k.host && o.port === k.port && o.status === 'approved' && o.id !== k.id)
      const msg = (k.trusted_on_first_use
        ? `Confirm the key trusted on first use for ${k.host}:${k.port}?`
        : `Approve this key for ${k.host}:${k.port}?`) +
        `\n\n${k.key_type} ${k.fingerprint}\n\n` +
        'Only approve it if this matches the fingerprint shown on the host itself.' +
        (replaces ? '\n\nThe currently approved key for this host will be removed.' : '')
      if (!window.confirm(msg)) return
      try {
        await api.sshHostKeys.approve(k.id)
        toast.success('Host key approved')
        await load()
      } catch (e) {
        toast.error(errText(e, 'Failed to approve key'))
      }
    }

    const remove = async (k) => {
      const msg = k.status === 'pending'
        ? `Reject the pending key ${k.fingerprint} for ${k.host}?`
        : `Forget the approved key for ${k.host}? The next connection will be treated as a new host.`
      if (!window.confirm(msg)) return
      try {
        await api.sshHostKeys.remove(k.id)
        await load()
      } catch (e) {
        toast.error(errText(e, 'Failed to remove key'))
      }
    }

    onMounted(load)
    return { keys, unconfirmed, loading, policy, policyLoading, scanHost, scanPort, scanning, load, savePolicy, scan, approve, remove, fmt }
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
.keys-table th, .keys-table td { padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--border-color, #e5e7eb); text-align: left; vertical-align: middle; }
.keys-table .fp { font-size: 0.75rem; word-break: break-all; }
.keys-table .actions { white-space: nowrap; display: flex; gap: 0.35rem; }
.row-pending { background: var(--warning-bg, rgba(234, 179, 8, 0.08)); }
.first-use-callout { border-left: 3px solid var(--warning-color, #d97706); background: var(--warning-bg, rgba(234, 179, 8, 0.08)); padding: 0.6rem 0.8rem; margin: 0.5rem 0 0.75rem; border-radius: 4px; }
.first-use-callout p { margin: 0; }
</style>
