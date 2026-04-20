<template>
  <div class="ai-reports-view">
    <div class="page-header mb-2">
      <div class="page-header-left">
        <h1 class="page-title">🤖 AI Reports</h1>
        <p class="page-subtitle">Generate evidence-based infrastructure reports — combines deterministic rules with optional LLM narrative.</p>
      </div>
      <div class="page-header-actions">
        <button v-if="isAdmin" class="btn btn-outline btn-sm" @click="$router.push('/ai-reports/settings')">Settings</button>
        <button class="btn btn-primary btn-sm" @click="showGenerateModal = true">+ Generate Report</button>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs mb-2">
      <button class="tab-btn" :class="{ 'tab-btn--active': activeTab === 'reports' }" @click="activeTab = 'reports'">Reports</button>
      <button v-if="isAdmin" class="tab-btn" :class="{ 'tab-btn--active': activeTab === 'schedules' }" @click="activeTab = 'schedules'">Schedules</button>
    </div>

    <!-- Reports tab -->
    <div v-if="activeTab === 'reports'">
      <!-- Filters -->
      <div class="filter-bar mb-2">
        <select v-model="filters.report_type" @change="loadReports" class="filter-select">
          <option value="">All types</option>
          <option value="health">Health</option>
          <option value="optimization">Optimization</option>
          <option value="redundancy">Redundancy</option>
          <option value="power">Power</option>
          <option value="hardware">Hardware</option>
          <option value="capacity">Capacity</option>
          <option value="comprehensive">Comprehensive</option>
        </select>
        <select v-model="filters.scope_type" @change="loadReports" class="filter-select">
          <option value="">All scopes</option>
          <option value="global">Global</option>
          <option value="cluster">Cluster</option>
          <option value="node">Node</option>
        </select>
        <select v-model="filters.status" @change="loadReports" class="filter-select">
          <option value="">All statuses</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="complete">Complete</option>
          <option value="complete_ai_failed">Complete (AI failed)</option>
          <option value="failed">Failed</option>
        </select>
        <button class="btn btn-ghost btn-sm" @click="loadReports">Refresh</button>
      </div>

      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>Loading reports…</p>
      </div>
      <div v-else-if="reports.length === 0" class="empty-state">
        <div class="empty-icon">📄</div>
        <h3>No reports yet</h3>
        <p>Click "Generate Report" to create your first AI-assisted infrastructure report.</p>
      </div>
      <table v-else class="reports-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Type</th>
            <th>Scope</th>
            <th>Status</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in reports" :key="r.id">
            <td><strong>{{ r.title }}</strong></td>
            <td><span class="tag">{{ r.report_type }}</span></td>
            <td>{{ r.scope_type }}<span v-if="r.scope_ref"> / {{ r.scope_ref }}</span></td>
            <td><span class="status-chip" :class="statusClass(r.status)">{{ statusLabel(r.status) }}</span></td>
            <td :title="r.created_at">{{ relativeTime(r.created_at) }}</td>
            <td>
              <button class="btn btn-ghost btn-xs" @click="$router.push('/ai-reports/' + r.id)">View</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Schedules tab (admin) -->
    <div v-else-if="activeTab === 'schedules'">
      <div class="page-header-actions mb-2">
        <button class="btn btn-primary btn-sm" @click="showScheduleModal = true">+ New Schedule</button>
      </div>
      <div v-if="schedules.length === 0" class="empty-state">
        <div class="empty-icon">📅</div>
        <h3>No schedules configured</h3>
      </div>
      <table v-else class="reports-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Scope</th>
            <th>Cadence</th>
            <th>Next Run</th>
            <th>Enabled</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in schedules" :key="s.id">
            <td><strong>{{ s.name }}</strong></td>
            <td>{{ s.report_type }}</td>
            <td>{{ s.scope_type }}<span v-if="s.scope_ref"> / {{ s.scope_ref }}</span></td>
            <td>{{ s.cadence }}</td>
            <td>{{ formatDate(s.next_run_at) }}</td>
            <td>
              <input type="checkbox" :checked="s.enabled" @change="toggleSchedule(s)" />
            </td>
            <td>
              <button class="btn btn-ghost btn-xs" @click="deleteSchedule(s.id)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Generate modal -->
    <div v-if="showGenerateModal" class="modal-backdrop" @click.self="showGenerateModal = false">
      <div class="modal-card">
        <h3>Generate Report</h3>
        <div class="form-group">
          <label>Report Type</label>
          <select v-model="newReport.report_type" class="form-select">
            <option value="health">Health</option>
            <option value="optimization">Optimization</option>
            <option value="redundancy">Redundancy</option>
            <option value="power">Power / Cost</option>
            <option value="hardware">Hardware Refresh</option>
            <option value="capacity">Capacity</option>
            <option value="comprehensive">Comprehensive (all sections)</option>
          </select>
        </div>
        <div class="form-group">
          <label>Scope</label>
          <select v-model="newReport.scope_type" class="form-select">
            <option value="global">Global (all hosts)</option>
            <option value="cluster">Specific cluster / host</option>
            <option value="node">Specific node</option>
          </select>
        </div>
        <div v-if="newReport.scope_type !== 'global'" class="form-group">
          <label>Scope reference ({{ newReport.scope_type === 'cluster' ? 'host id' : 'node name' }})</label>
          <input v-model="newReport.scope_ref" class="form-input" />
        </div>
        <div class="form-group">
          <label>Custom goal (optional)</label>
          <textarea v-model="newReport.custom_prompt" class="form-input" rows="3" placeholder="e.g. 'Focus on reducing electricity cost over the next quarter'"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="showGenerateModal = false">Cancel</button>
          <button class="btn btn-primary" :disabled="generating" @click="generateReport">
            {{ generating ? 'Queuing…' : 'Generate' }}
          </button>
        </div>
      </div>
    </div>

    <!-- New schedule modal -->
    <div v-if="showScheduleModal" class="modal-backdrop" @click.self="showScheduleModal = false">
      <div class="modal-card">
        <h3>New Schedule</h3>
        <div class="form-group">
          <label>Name</label>
          <input v-model="newSchedule.name" class="form-input" placeholder="Weekly health report" />
        </div>
        <div class="form-group">
          <label>Report Type</label>
          <select v-model="newSchedule.report_type" class="form-select">
            <option value="health">Health</option>
            <option value="optimization">Optimization</option>
            <option value="redundancy">Redundancy</option>
            <option value="power">Power / Cost</option>
            <option value="hardware">Hardware Refresh</option>
            <option value="capacity">Capacity</option>
            <option value="comprehensive">Comprehensive</option>
          </select>
        </div>
        <div class="form-group">
          <label>Cadence</label>
          <select v-model="newSchedule.cadence" class="form-select">
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="showScheduleModal = false">Cancel</button>
          <button class="btn btn-primary" @click="createSchedule">Create</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import { useAuthStore } from '@/store/auth'
import api from '@/services/api'

export default {
  name: 'AIReports',
  setup() {
    const router = useRouter()
    const toast = useToast()
    const auth = useAuthStore()
    const isAdmin = computed(() => auth.isAdmin)

    const activeTab = ref('reports')
    const loading = ref(false)
    const reports = ref([])
    const schedules = ref([])
    const filters = reactive({ report_type: '', scope_type: '', status: '' })

    const showGenerateModal = ref(false)
    const showScheduleModal = ref(false)
    const generating = ref(false)
    const newReport = reactive({ report_type: 'health', scope_type: 'global', scope_ref: '', custom_prompt: '' })
    const newSchedule = reactive({ name: '', report_type: 'health', cadence: 'weekly', scope_type: 'global' })

    const loadReports = async () => {
      loading.value = true
      try {
        const params = {}
        if (filters.report_type) params.report_type = filters.report_type
        if (filters.scope_type) params.scope_type = filters.scope_type
        if (filters.status) params.status = filters.status
        const res = await api.aiReports.listReports(params)
        reports.value = res.data || []
      } catch (e) {
        // toast handled by interceptor
      } finally {
        loading.value = false
      }
    }

    const loadSchedules = async () => {
      if (!auth.isAdmin) return
      try {
        const res = await api.aiReports.listSchedules()
        schedules.value = res.data || []
      } catch (e) {}
    }

    const generateReport = async () => {
      if (!newReport.report_type) return
      generating.value = true
      try {
        const payload = { report_type: newReport.report_type, scope_type: newReport.scope_type }
        if (newReport.scope_ref) payload.scope_ref = newReport.scope_ref
        if (newReport.custom_prompt) payload.custom_prompt = newReport.custom_prompt
        const res = await api.aiReports.generateReport(payload)
        toast.success(`Report queued (#${res.data.id})`)
        showGenerateModal.value = false
        setTimeout(loadReports, 1500)
      } finally {
        generating.value = false
      }
    }

    const createSchedule = async () => {
      if (!newSchedule.name || !newSchedule.report_type) return
      try {
        await api.aiReports.createSchedule({
          name: newSchedule.name,
          report_type: newSchedule.report_type,
          scope_type: newSchedule.scope_type,
          cadence: newSchedule.cadence,
          enabled: true,
        })
        toast.success('Schedule created')
        showScheduleModal.value = false
        newSchedule.name = ''
        await loadSchedules()
      } catch (e) {}
    }

    const toggleSchedule = async (s) => {
      try {
        await api.aiReports.updateSchedule(s.id, { enabled: !s.enabled })
        await loadSchedules()
      } catch (e) {}
    }

    const deleteSchedule = async (id) => {
      if (!confirm('Delete this schedule?')) return
      try {
        await api.aiReports.deleteSchedule(id)
        await loadSchedules()
      } catch (e) {}
    }

    const statusClass = (s) => {
      if (s === 'complete') return 'chip-ok'
      if (s === 'complete_ai_failed') return 'chip-warn'
      if (s === 'failed') return 'chip-critical'
      if (s === 'running' || s === 'queued') return 'chip-info'
      return ''
    }
    const statusLabel = (s) => {
      if (s === 'complete_ai_failed') return 'partial (no AI)'
      return s
    }

    const relativeTime = (iso) => {
      if (!iso) return '—'
      const d = new Date(iso)
      const diff = (Date.now() - d.getTime()) / 1000
      if (diff < 60) return `${Math.floor(diff)}s ago`
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
      return d.toLocaleString()
    }

    const formatDate = (iso) => {
      if (!iso) return '—'
      return new Date(iso).toLocaleString()
    }

    onMounted(() => {
      loadReports()
      loadSchedules()
    })

    return {
      isAdmin, activeTab, loading, reports, schedules, filters,
      showGenerateModal, showScheduleModal, generating, newReport, newSchedule,
      loadReports, generateReport, createSchedule, toggleSchedule, deleteSchedule,
      statusClass, statusLabel, relativeTime, formatDate,
    }
  },
}
</script>

<style scoped>
.ai-reports-view { padding: 1.25rem; }
.page-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  flex-wrap: wrap; gap: 1rem;
}
.page-title { font-size: 1.5rem; margin: 0; }
.page-subtitle { color: #6b7280; margin: 0.25rem 0 0; font-size: 0.9rem; }
.page-header-actions { display: flex; gap: 0.5rem; }

.tabs { display: flex; gap: 0.5rem; border-bottom: 1px solid #e5e7eb; }
.tab-btn {
  background: none; border: none; padding: 0.5rem 1rem; cursor: pointer;
  color: #6b7280; font-size: 0.9rem; border-bottom: 2px solid transparent;
}
.tab-btn:hover { color: #111827; }
.tab-btn--active { color: #2563eb; border-bottom-color: #2563eb; font-weight: 600; }

.filter-bar { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
.filter-select {
  padding: 0.4rem 0.6rem; border: 1px solid #d1d5db; border-radius: 4px;
  background: white; font-size: 0.875rem;
}

.reports-table {
  width: 100%; border-collapse: collapse; background: white;
  border-radius: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  overflow: hidden;
}
.reports-table th, .reports-table td {
  padding: 0.7rem 0.9rem; border-bottom: 1px solid #e5e7eb;
  text-align: left; font-size: 0.875rem;
}
.reports-table th { background: #f9fafb; font-weight: 600; color: #374151; }

.tag {
  display: inline-block; padding: 0.1rem 0.4rem; border-radius: 3px;
  background: #eef2ff; color: #4338ca; font-size: 0.75rem; font-weight: 600;
}

.status-chip {
  display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px;
  font-size: 0.75rem; font-weight: 600;
}
.chip-ok { background: #dcfce7; color: #15803d; }
.chip-warn { background: #fef3c7; color: #b45309; }
.chip-critical { background: #fee2e2; color: #b91c1c; }
.chip-info { background: #dbeafe; color: #1d4ed8; }

.empty-state, .loading-state {
  text-align: center; padding: 3rem 1rem; color: #6b7280;
}
.empty-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }

.spinner {
  display: inline-block; width: 2.5rem; height: 2.5rem;
  border: 3px solid #e5e7eb; border-top-color: #3b82f6;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center; z-index: 500;
}
.modal-card {
  background: white; padding: 1.5rem; border-radius: 8px;
  max-width: 520px; width: 92%;
}
.modal-card h3 { margin: 0 0 1rem; }
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; font-size: 0.8rem; color: #374151; margin-bottom: 0.25rem; font-weight: 600; }
.form-input, .form-select {
  width: 100%; padding: 0.5rem 0.7rem; border: 1px solid #d1d5db;
  border-radius: 4px; font-size: 0.9rem;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1.5rem; }

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
