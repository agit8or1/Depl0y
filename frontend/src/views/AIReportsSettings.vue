<template>
  <div class="ai-settings-view">
    <div class="page-header mb-2">
      <div class="page-header-left">
        <button class="btn btn-ghost btn-xs" @click="$router.push('/ai-reports')">&larr; Back</button>
        <h1 class="page-title">AI Reports Settings</h1>
        <p class="page-subtitle">Admin-only: API provider, model choice, electricity rate, per-node power profiles.</p>
      </div>
    </div>

    <div class="grid">
      <!-- Provider -->
      <div class="panel">
        <h2>OpenAI Provider</h2>
        <div v-if="settings">
          <div class="form-row">
            <label>Status</label>
            <div>
              <span v-if="settings.has_key" class="chip chip-ok">Key stored</span>
              <span v-else class="chip chip-warn">Key not set</span>
              <span v-if="settings.enabled" class="chip chip-info">Enabled</span>
              <span v-else class="chip">Disabled</span>
              <span v-if="settings.last_test_at" class="chip" :class="settings.last_test_ok ? 'chip-ok' : 'chip-critical'">
                Last test: {{ formatDate(settings.last_test_at) }}
                ({{ settings.last_test_ok ? 'ok' : 'fail' }})
              </span>
            </div>
          </div>

          <div class="form-row">
            <label>API Key (write-only)</label>
            <input v-model="keyDraft" type="password" placeholder="sk-..." class="form-input" autocomplete="off" />
            <small class="hint">Stored encrypted. Leave blank to keep the existing key.</small>
          </div>

          <div class="form-row">
            <label>Model</label>
            <select v-model="modelDraft" class="form-select">
              <option value="gpt-4o-mini">gpt-4o-mini (fast / cheap)</option>
              <option value="gpt-4o">gpt-4o</option>
              <option value="gpt-4-turbo">gpt-4-turbo</option>
            </select>
          </div>

          <div class="form-row">
            <label>
              <input type="checkbox" v-model="enabledDraft" />
              Enable AI narrative step
            </label>
          </div>

          <div class="actions">
            <button class="btn btn-outline btn-sm" :disabled="testing || !settings.has_key" @click="testConnection">
              {{ testing ? 'Testing…' : 'Test Connection' }}
            </button>
            <button class="btn btn-primary btn-sm" :disabled="saving" @click="saveSettings">
              {{ saving ? 'Saving…' : 'Save' }}
            </button>
          </div>
        </div>
        <div v-else class="loading-state"><div class="spinner"></div></div>
      </div>

      <!-- Power -->
      <div class="panel">
        <h2>Electricity Rate & Currency</h2>
        <div v-if="power">
          <div class="form-row">
            <label>Rate per kWh</label>
            <input v-model.number="powerDraft.electricity_rate_per_kwh" type="number" step="0.001" min="0" max="5" class="form-input" />
          </div>
          <div class="form-row">
            <label>Currency</label>
            <input v-model="powerDraft.currency" maxlength="10" class="form-input" />
          </div>
          <div class="actions">
            <button class="btn btn-primary btn-sm" @click="savePower">Save</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Node power profiles -->
    <div class="panel full">
      <h2>Per-Node Power Profiles</h2>
      <p class="hint">Idle/load wattage estimates used when BMC-measured watts aren't available. The row with no node_id is the cluster default.</p>
      <table class="profiles-table">
        <thead>
          <tr>
            <th>Node ID</th>
            <th>Node</th>
            <th>Idle watts</th>
            <th>Load watts</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(p, i) in powerDraft.node_profiles" :key="i">
            <td>{{ p.node_id === null ? '— (default)' : p.node_id }}</td>
            <td>{{ p.is_default ? 'All nodes (fallback)' : p.node_name || '' }}</td>
            <td><input v-model.number="p.idle_watts" type="number" min="30" max="2000" class="form-input sm" /></td>
            <td><input v-model.number="p.load_watts" type="number" min="60" max="3000" class="form-input sm" /></td>
          </tr>
        </tbody>
      </table>
      <div class="actions">
        <button class="btn btn-primary btn-sm" @click="savePower">Save Profiles</button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'AIReportsSettings',
  setup() {
    const toast = useToast()

    const settings = ref(null)
    const power = ref(null)
    const keyDraft = ref('')
    const modelDraft = ref('gpt-4o-mini')
    const enabledDraft = ref(true)
    const saving = ref(false)
    const testing = ref(false)
    const powerDraft = reactive({ electricity_rate_per_kwh: 0.12, currency: 'USD', node_profiles: [] })

    const loadSettings = async () => {
      const res = await api.aiReports.getSettings()
      settings.value = res.data
      modelDraft.value = res.data.model || 'gpt-4o-mini'
      enabledDraft.value = !!res.data.enabled
    }
    const loadPower = async () => {
      const res = await api.aiReports.getPowerSettings()
      power.value = res.data
      powerDraft.electricity_rate_per_kwh = res.data.electricity_rate_per_kwh
      powerDraft.currency = res.data.currency
      powerDraft.node_profiles = res.data.node_profiles
    }

    const saveSettings = async () => {
      saving.value = true
      try {
        const payload = { model: modelDraft.value, enabled: enabledDraft.value }
        if (keyDraft.value && keyDraft.value.trim()) payload.api_key = keyDraft.value.trim()
        await api.aiReports.updateSettings(payload)
        keyDraft.value = ''
        toast.success('Settings saved')
        await loadSettings()
      } finally {
        saving.value = false
      }
    }

    const testConnection = async () => {
      testing.value = true
      try {
        const res = await api.aiReports.testSettings()
        if (res.data.ok) {
          toast.success('OpenAI connection OK')
        } else {
          toast.error('Connection failed — check key and model')
        }
        await loadSettings()
      } finally {
        testing.value = false
      }
    }

    const savePower = async () => {
      try {
        await api.aiReports.updatePowerSettings({
          electricity_rate_per_kwh: powerDraft.electricity_rate_per_kwh,
          currency: powerDraft.currency,
          node_profiles: powerDraft.node_profiles.map(p => ({
            node_id: p.node_id,
            idle_watts: p.idle_watts,
            load_watts: p.load_watts,
          })),
        })
        toast.success('Power settings saved')
        await loadPower()
      } catch (e) {}
    }

    const formatDate = (iso) => iso ? new Date(iso).toLocaleString() : '—'

    onMounted(async () => {
      await Promise.all([loadSettings(), loadPower()])
    })

    return {
      settings, power, keyDraft, modelDraft, enabledDraft,
      saving, testing, powerDraft,
      saveSettings, savePower, testConnection, formatDate,
    }
  },
}
</script>

<style scoped>
.ai-settings-view { padding: 1.25rem; }
.page-title { font-size: 1.4rem; margin: 0.25rem 0 0; }
.page-subtitle { color: #6b7280; margin: 0.25rem 0 1rem; font-size: 0.9rem; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }
.panel {
  background: white; padding: 1.25rem; border-radius: 6px;
  border: 1px solid #e5e7eb; margin-bottom: 1rem;
}
.panel.full { grid-column: 1 / -1; }
.panel h2 { font-size: 1.05rem; margin: 0 0 1rem; }

.form-row { margin-bottom: 1rem; }
.form-row label { display: block; font-size: 0.8rem; color: #374151; margin-bottom: 0.25rem; font-weight: 600; }
.hint { color: #9ca3af; font-size: 0.75rem; display: block; margin-top: 0.25rem; }
.form-input, .form-select {
  width: 100%; padding: 0.5rem 0.7rem; border: 1px solid #d1d5db;
  border-radius: 4px; font-size: 0.9rem;
}
.form-input.sm { width: 100px; padding: 0.3rem 0.5rem; }

.actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.5rem; }

.profiles-table { width: 100%; border-collapse: collapse; margin: 0.5rem 0; }
.profiles-table th, .profiles-table td {
  padding: 0.5rem 0.7rem; border-bottom: 1px solid #e5e7eb;
  text-align: left; font-size: 0.85rem;
}

.chip {
  display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px;
  font-size: 0.75rem; font-weight: 600; margin-right: 0.4rem;
  background: #f3f4f6; color: #4b5563;
}
.chip-ok { background: #dcfce7; color: #15803d; }
.chip-warn { background: #fef3c7; color: #b45309; }
.chip-info { background: #dbeafe; color: #1d4ed8; }
.chip-critical { background: #fee2e2; color: #b91c1c; }

.spinner {
  display: inline-block; width: 2rem; height: 2rem;
  border: 3px solid #e5e7eb; border-top-color: #3b82f6;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-state { text-align: center; padding: 2rem 1rem; color: #6b7280; }

.mb-2 { margin-bottom: 1rem; }
.btn { padding: 0.45rem 0.85rem; border-radius: 4px; cursor: pointer; border: 1px solid transparent; font-size: 0.85rem; }
.btn-primary { background: #2563eb; color: white; }
.btn-primary:hover { background: #1d4ed8; }
.btn-outline { background: white; color: #2563eb; border-color: #c7d2fe; }
.btn-ghost { background: transparent; color: #374151; }
.btn-ghost:hover { background: #f3f4f6; }
.btn-xs { padding: 0.25rem 0.6rem; font-size: 0.75rem; }
.btn-sm { padding: 0.35rem 0.75rem; font-size: 0.8rem; }
.btn:disabled { opacity: 0.55; cursor: not-allowed; }
</style>
