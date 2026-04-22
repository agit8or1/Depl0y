<template>
  <div class="time-sync-page">
    <!-- ── Header ─────────────────────────────────────────────────────────── -->
    <div class="page-header">
      <div class="page-header-left">
        <h2>Time Sync</h2>
        <p class="text-muted text-sm">Audit clock drift and NTP state across PVE nodes, PBS servers, and iDRAC/BMCs.</p>
      </div>
      <div class="page-header-right">
        <span v-if="generatedAt" class="text-xs text-muted generated-at">Last probe: {{ formatAgo(generatedAt) }}</span>
        <button class="btn btn-outline btn-sm" @click="openSettings" v-if="isAdmin">Settings</button>
        <button class="btn btn-outline btn-sm" @click="refresh(true)" :disabled="loading">
          {{ loading ? 'Probing...' : 'Refresh' }}
        </button>
        <button class="btn btn-primary btn-sm" @click="confirmFixAll" v-if="isAdmin" :disabled="fixing || driftingCount === 0">
          {{ fixing ? 'Fixing...' : `Fix All Drifting (${driftingCount})` }}
        </button>
      </div>
    </div>

    <!-- ── Summary tiles ──────────────────────────────────────────────────── -->
    <div class="summary-tiles">
      <div class="ts-tile">
        <div class="ts-tile__value">{{ summary.total || 0 }}</div>
        <div class="ts-tile__label">Total</div>
      </div>
      <div class="ts-tile ts-tile--ok">
        <div class="ts-tile__value">{{ summary.ok || 0 }}</div>
        <div class="ts-tile__label">In-sync</div>
      </div>
      <div class="ts-tile ts-tile--warn">
        <div class="ts-tile__value">{{ summary.drifting || 0 }}</div>
        <div class="ts-tile__label">Drifting</div>
      </div>
      <div class="ts-tile ts-tile--err">
        <div class="ts-tile__value">{{ summary.unreachable || 0 }}</div>
        <div class="ts-tile__label">Unreachable</div>
      </div>
      <div class="ts-tile ts-tile--ok">
        <div class="ts-tile__value">{{ summary.ntp_enabled_count || 0 }}</div>
        <div class="ts-tile__label">Has NTP</div>
      </div>
      <div class="ts-tile ts-tile--warn">
        <div class="ts-tile__value">{{ summary.ntp_disabled_count || 0 }}</div>
        <div class="ts-tile__label">No NTP</div>
      </div>
      <div class="ts-tile">
        <div class="ts-tile__value">{{ summary.ntp_unknown_count || 0 }}</div>
        <div class="ts-tile__label">NTP Unknown</div>
      </div>
    </div>

    <!-- ── Main table ─────────────────────────────────────────────────────── -->
    <div v-if="loading && targets.length === 0" class="loading-state">
      <div class="spinner"></div>
      <div>Loading time sync status...</div>
    </div>
    <div v-else-if="error" class="empty-state">
      <div class="empty-title">Failed to load time sync data</div>
      <div class="text-muted">{{ error }}</div>
    </div>
    <div v-else-if="targets.length === 0" class="empty-state">
      <div class="empty-title">No targets configured</div>
      <div class="text-muted">Add Proxmox hosts, PBS servers, or iDRACs/BMCs to begin auditing.</div>
    </div>

    <div v-else class="ts-table-wrap">
      <table class="ts-table">
        <thead>
          <tr>
            <th>Target</th>
            <th>Kind</th>
            <th>Address</th>
            <th>Local Time</th>
            <th>Drift</th>
            <th>NTP</th>
            <th>NTP Servers</th>
            <th v-if="isAdmin"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in targets" :key="`${t.kind}:${t.id}`">
            <td>
              <div class="font-bold">{{ t.label }}</div>
              <div v-if="t.error" class="error-inline" :title="t.error">{{ t.error }}</div>
            </td>
            <td>
              <span class="kind-pill" :class="`kind-pill--${t.kind}`">{{ kindLabel(t.kind) }}</span>
            </td>
            <td class="mono text-xs">{{ t.address || '—' }}</td>
            <td class="mono text-xs">
              <span v-if="t.reported_time_utc">{{ shortTime(t.reported_time_utc) }}</span>
              <span v-else class="text-muted">—</span>
              <div v-if="t.timezone" class="text-muted text-xs">{{ t.timezone }}</div>
            </td>
            <td>
              <span v-if="t.drift_seconds !== null && t.drift_seconds !== undefined"
                    class="drift-chip" :class="driftClass(t.drift_seconds)"
                    :title="`${t.drift_seconds >= 0 ? 'Ahead' : 'Behind'} deploy host`">
                {{ formatDrift(t.drift_seconds) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <span v-if="t.ntp_enabled === true" class="ntp-chip ntp-chip--ok">enabled</span>
              <span v-else-if="t.ntp_enabled === false" class="ntp-chip ntp-chip--err">disabled</span>
              <span v-else class="ntp-chip ntp-chip--unknown">unknown</span>
            </td>
            <td>
              <div v-if="t.ntp_servers && t.ntp_servers.length"
                   :title="t.ntp_servers.join(', ')" class="ntp-servers-cell mono text-xs">
                {{ truncateServers(t.ntp_servers) }}
              </div>
              <span v-else class="text-muted">—</span>
            </td>
            <td v-if="isAdmin" class="actions-cell">
              <button class="btn btn-outline btn-sm" @click="fixOne(t)" :disabled="fixing">Fix</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── Recent action log ───────────────────────────────────────────────── -->
    <div v-if="lastActions.length > 0" class="log-panel">
      <div class="log-panel-title">Last remediation result</div>
      <ul class="log-list">
        <li v-for="(entry, idx) in lastActions" :key="idx" :class="`log-entry log-entry--${entry.status}`">
          <span class="log-label">{{ entry.label || entry.target || `${entry.kind}:${entry.id}` }}</span>
          <span class="log-status">{{ entry.status }}</span>
          <span v-if="entry.error" class="log-err">{{ entry.error }}</span>
          <ul v-if="entry.actions && entry.actions.length" class="log-action-list">
            <li v-for="(a, i) in entry.actions" :key="i">{{ a }}</li>
          </ul>
        </li>
      </ul>
    </div>

    <!-- ── Settings modal ─────────────────────────────────────────────────── -->
    <div v-if="settingsOpen" class="modal-backdrop" @click.self="settingsOpen = false">
      <div class="modal">
        <div class="modal-header">
          <h3>Time Sync Settings</h3>
          <button class="modal-close" @click="settingsOpen = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Default NTP server</label>
            <input v-model="settingsForm.ntp_server" placeholder="pool.ntp.org" class="form-control" />
            <div class="text-xs text-muted">Used when you click Fix or Fix All.</div>
          </div>
          <div class="form-row">
            <label>Drift threshold (seconds)</label>
            <input v-model.number="settingsForm.drift_threshold_seconds" type="number" min="1" class="form-control" />
            <div class="text-xs text-muted">A target is flagged as drifting when |reported − deploy| exceeds this.</div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline btn-sm" @click="settingsOpen = false">Cancel</button>
          <button class="btn btn-primary btn-sm" @click="saveSettings" :disabled="settingsSaving">
            {{ settingsSaving ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'TimeSync',
  setup() {
    const auth = useAuthStore()
    const toast = useToast()

    const loading = ref(false)
    const fixing = ref(false)
    const error = ref(null)
    const generatedAt = ref(null)
    const targets = ref([])
    const summary = ref({})
    const threshold = ref(300)
    const lastActions = ref([])

    const settingsOpen = ref(false)
    const settingsSaving = ref(false)
    const settingsForm = ref({ ntp_server: 'pool.ntp.org', drift_threshold_seconds: 300 })

    const isAdmin = computed(() => auth.isAdmin)

    const driftingCount = computed(() => summary.value.drifting || 0)

    let refreshTimer = null

    async function refresh(force = false) {
      loading.value = true
      error.value = null
      try {
        const { data } = await api.get('/time-sync/status', { params: force ? { refresh: true } : {} })
        targets.value = data.targets || []
        summary.value = data.summary || {}
        generatedAt.value = data.generated_at
        threshold.value = data.drift_threshold_seconds || 300
      } catch (e) {
        error.value = e?.response?.data?.detail || e.message || 'Unknown error'
      } finally {
        loading.value = false
      }
    }

    async function loadSettings() {
      if (!isAdmin.value) return
      try {
        const { data } = await api.get('/time-sync/settings')
        settingsForm.value = {
          ntp_server: data.ntp_server || 'pool.ntp.org',
          drift_threshold_seconds: data.drift_threshold_seconds || 300,
        }
      } catch (e) {
        // silent — admins hitting fix without visiting settings is fine
      }
    }

    function openSettings() {
      settingsOpen.value = true
      loadSettings()
    }

    async function saveSettings() {
      settingsSaving.value = true
      try {
        const payload = {
          ntp_server: settingsForm.value.ntp_server,
          drift_threshold_seconds: Number(settingsForm.value.drift_threshold_seconds),
        }
        await api.put('/time-sync/settings', payload)
        toast.success('Time sync settings saved')
        settingsOpen.value = false
        refresh(true)
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Save failed')
      } finally {
        settingsSaving.value = false
      }
    }

    async function fixOne(t) {
      if (!confirm(`Enable NTP and restart time daemons on "${t.label}"?`)) return
      fixing.value = true
      try {
        const { data } = await api.post('/time-sync/fix', {
          targets: [{ kind: t.kind, id: t.id }],
          ntp_server: settingsForm.value.ntp_server || undefined,
        })
        lastActions.value = data.results || []
        if (data.status === 'ok') {
          toast.success(`Fixed ${t.label}`)
        } else if (data.status === 'partial') {
          toast.warning(`Partial fix applied to ${t.label}`)
        } else {
          toast.error(`Fix failed for ${t.label}`)
        }
        await refresh(true)
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Fix failed')
      } finally {
        fixing.value = false
      }
    }

    async function confirmFixAll() {
      if (driftingCount.value === 0) return
      const msg = `Apply NTP fix to ${driftingCount.value} drifting target(s)?`
      if (!confirm(msg)) return
      fixing.value = true
      try {
        const { data } = await api.post('/time-sync/fix-all', {
          ntp_server: settingsForm.value.ntp_server || undefined,
        })
        lastActions.value = data.results || []
        if (data.status === 'ok') toast.success(`Fixed ${data.succeeded}/${data.attempted} targets`)
        else if (data.status === 'partial') toast.warning(`Fixed ${data.succeeded}/${data.attempted} targets`)
        else if (data.status === 'noop') toast.info('Nothing to fix')
        else toast.error('Fix All failed')
        await refresh(true)
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Fix All failed')
      } finally {
        fixing.value = false
      }
    }

    // ── formatting helpers ──────────────────────────────────────────────────
    function kindLabel(k) {
      return ({
        pve_node: 'PVE Node',
        pbs: 'PBS',
        bmc_node: 'iDRAC (Node)',
        bmc_pbs: 'iDRAC (PBS)',
        bmc_standalone: 'BMC',
      })[k] || k
    }

    function formatDrift(s) {
      if (s === null || s === undefined) return '—'
      const sign = s >= 0 ? '+' : '-'
      const a = Math.abs(s)
      if (a < 1) return `${sign}${a.toFixed(2)}s`
      if (a < 60) return `${sign}${a.toFixed(1)}s`
      if (a < 3600) return `${sign}${(a / 60).toFixed(1)}m`
      if (a < 86400) return `${sign}${(a / 3600).toFixed(1)}h`
      return `${sign}${(a / 86400).toFixed(1)}d`
    }

    function driftClass(s) {
      const a = Math.abs(s || 0)
      if (a < 5) return 'drift-chip--ok'
      if (a < 60) return 'drift-chip--warn'
      return 'drift-chip--err'
    }

    function shortTime(iso) {
      try {
        const d = new Date(iso)
        return d.toLocaleString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
      } catch (_) { return iso }
    }

    function formatAgo(iso) {
      try {
        const d = new Date(iso)
        const s = Math.round((Date.now() - d.getTime()) / 1000)
        if (s < 60) return `${s}s ago`
        if (s < 3600) return `${Math.round(s / 60)}m ago`
        return `${Math.round(s / 3600)}h ago`
      } catch (_) { return iso }
    }

    function truncateServers(servers) {
      if (!Array.isArray(servers)) return ''
      if (servers.length === 0) return ''
      const first = servers[0]
      if (servers.length === 1) return first
      return `${first}, +${servers.length - 1} more`
    }

    onMounted(() => {
      loadSettings()
      refresh(false)
      refreshTimer = setInterval(() => refresh(false), 60000) // every 60s, cached server-side
    })

    onBeforeUnmount(() => {
      if (refreshTimer) clearInterval(refreshTimer)
    })

    return {
      loading, fixing, error, generatedAt, targets, summary, threshold, lastActions,
      settingsOpen, settingsSaving, settingsForm,
      isAdmin, driftingCount,
      refresh, openSettings, saveSettings, fixOne, confirmFixAll,
      kindLabel, formatDrift, driftClass, shortTime, formatAgo, truncateServers,
    }
  },
}
</script>

<style scoped>
.time-sync-page {
  padding: 1rem;
  color: var(--text-primary);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.page-header-left h2 { margin: 0 0 0.25rem 0; }
.page-header-right { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.generated-at { margin-right: 0.5rem; }

/* ── Tiles ── */
.summary-tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.ts-tile {
  min-width: 88px;
  padding: 0.5rem 0.9rem;
  background: var(--bg-card, var(--surface));
  border: 1px solid var(--border-color);
  border-radius: 0.4rem;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.ts-tile__value {
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.15;
  color: var(--text-primary);
}
.ts-tile__label {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin-top: 0.15rem;
}
.ts-tile--ok   { border-color: var(--color-success, #86efac); }
.ts-tile--ok   .ts-tile__value { color: var(--color-success, #16a34a); }
.ts-tile--warn { border-color: var(--color-warning, #fde68a); }
.ts-tile--warn .ts-tile__value { color: var(--color-warning, #d97706); }
.ts-tile--err  { border-color: var(--color-danger, #fca5a5); }
.ts-tile--err  .ts-tile__value { color: var(--color-danger, #dc2626); }

/* ── Table ── */
.ts-table-wrap {
  background: var(--bg-card, var(--surface));
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow-x: auto;
}
.ts-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.ts-table thead th {
  text-align: left;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--surface, transparent);
}
.ts-table tbody td {
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: top;
}
.ts-table tbody tr:last-child td { border-bottom: none; }

.kind-pill {
  display: inline-block;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 600;
  background: var(--surface);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}
.kind-pill--pve_node { border-color: #93c5fd; color: #1d4ed8; }
.kind-pill--pbs { border-color: #fcd34d; color: #92400e; }
.kind-pill--bmc_node,
.kind-pill--bmc_pbs,
.kind-pill--bmc_standalone { border-color: #a78bfa; color: #6d28d9; }

.drift-chip {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  font-family: monospace;
}
.drift-chip--ok   { background: rgba(22,163,74,0.12); color: #16a34a; }
.drift-chip--warn { background: rgba(217,119,6,0.15); color: #b45309; }
.drift-chip--err  { background: rgba(220,38,38,0.15); color: #b91c1c; }

.ntp-chip {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
}
.ntp-chip--ok   { background: rgba(22,163,74,0.15); color: #15803d; }
.ntp-chip--err  { background: rgba(220,38,38,0.15); color: #b91c1c; }
.ntp-chip--unknown { background: var(--surface); color: var(--text-secondary); border: 1px dashed var(--border-color); }

.ntp-servers-cell {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono { font-family: monospace; }
.error-inline {
  color: var(--color-danger, #dc2626);
  font-size: 0.7rem;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.text-xs { font-size: 0.72rem; }
.text-sm { font-size: 0.85rem; }
.text-muted { color: var(--text-secondary); }
.font-bold { font-weight: 600; }
.actions-cell { text-align: right; }

/* ── states ── */
.loading-state, .empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary);
}
.empty-title { font-weight: 600; color: var(--text-primary); margin-bottom: 0.3rem; }
.spinner {
  margin: 0 auto 0.6rem;
  width: 22px;
  height: 22px;
  border: 2px solid var(--border-color);
  border-top-color: var(--text-primary);
  border-radius: 50%;
  animation: ts-spin 0.8s linear infinite;
}
@keyframes ts-spin { to { transform: rotate(360deg); } }

/* ── log panel ── */
.log-panel {
  margin-top: 1rem;
  background: var(--bg-card, var(--surface));
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
}
.log-panel-title {
  font-weight: 600;
  margin-bottom: 0.4rem;
  font-size: 0.82rem;
  color: var(--text-primary);
}
.log-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.4rem; }
.log-entry {
  padding: 0.4rem 0.6rem;
  border-radius: 0.3rem;
  border: 1px solid var(--border-color);
  background: var(--surface, transparent);
}
.log-entry--ok { border-color: rgba(22,163,74,0.5); }
.log-entry--error { border-color: rgba(220,38,38,0.5); }
.log-label { font-weight: 600; margin-right: 0.5rem; color: var(--text-primary); }
.log-status {
  font-size: 0.7rem;
  padding: 0.05rem 0.35rem;
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-secondary);
}
.log-err { color: var(--color-danger, #dc2626); margin-left: 0.4rem; font-size: 0.8rem; }
.log-action-list {
  margin-top: 0.3rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
  font-family: monospace;
  padding-left: 1rem;
}

/* ── modal ── */
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal {
  background: var(--bg-card, var(--surface));
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0;
  max-width: 440px;
  width: 90%;
  color: var(--text-primary);
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.8rem 1rem;
  border-bottom: 1px solid var(--border-color);
}
.modal-header h3 { margin: 0; font-size: 1rem; }
.modal-close {
  background: none; border: none; font-size: 1.3rem; cursor: pointer;
  color: var(--text-secondary);
}
.modal-body { padding: 1rem; display: flex; flex-direction: column; gap: 0.9rem; }
.modal-footer {
  padding: 0.7rem 1rem;
  border-top: 1px solid var(--border-color);
  display: flex; justify-content: flex-end; gap: 0.5rem;
}
.form-row { display: flex; flex-direction: column; gap: 0.25rem; }
.form-row label { font-size: 0.75rem; font-weight: 600; color: var(--text-secondary); }
.form-control {
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.3rem;
  background: var(--surface);
  color: var(--text-primary);
  font-size: 0.85rem;
}
</style>
