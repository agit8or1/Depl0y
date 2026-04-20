<template>
  <div class="ai-report-detail">
    <div class="page-header mb-2">
      <div class="page-header-left">
        <button class="btn btn-ghost btn-xs" @click="$router.push('/ai-reports')">&larr; Back to reports</button>
        <h1 class="page-title">{{ report?.title || 'Loading…' }}</h1>
        <p class="page-subtitle" v-if="report">
          <span class="tag">{{ report.report_type }}</span>
          <span class="dot">·</span>
          <span>{{ report.scope_type }}<span v-if="report.scope_ref"> / {{ report.scope_ref }}</span></span>
          <span class="dot">·</span>
          <span>{{ new Date(report.created_at).toLocaleString() }}</span>
          <span v-if="report.model_used" class="dot">·</span>
          <span v-if="report.model_used">model: <code>{{ report.model_used }}</code></span>
        </p>
      </div>
      <div class="page-header-actions" v-if="report && report.status !== 'running' && report.status !== 'queued'">
        <button class="btn btn-ghost btn-sm" @click="downloadMarkdown">Download MD</button>
        <button class="btn btn-ghost btn-sm" @click="downloadHtml">Download HTML</button>
        <button class="btn btn-outline btn-sm" @click="regenerate" :disabled="regenerating">Regenerate</button>
      </div>
    </div>

    <div v-if="loading" class="loading-state"><div class="spinner"></div><p>Loading report…</p></div>

    <div v-else-if="!report" class="empty-state">
      <div class="empty-icon">❓</div>
      <h3>Report not found</h3>
    </div>

    <div v-else>
      <div v-if="report.status === 'queued' || report.status === 'running'" class="notice notice-info">
        Report is {{ report.status }} — this page will auto-refresh.
      </div>
      <div v-if="report.status === 'complete_ai_failed'" class="notice notice-warn">
        AI narrative step failed — showing deterministic findings only.
        <div v-if="report.error_message" class="notice-detail">{{ report.error_message }}</div>
      </div>
      <div v-if="report.status === 'failed'" class="notice notice-critical">
        Generation failed: {{ report.error_message || 'unknown error' }}
      </div>

      <!-- Stat tiles -->
      <div class="stat-cards" v-if="report.status?.startsWith('complete')">
        <div class="stat-card">
          <div class="stat-card__value">{{ healthScore }}</div>
          <div class="stat-card__label">Health Score</div>
        </div>
        <div class="stat-card">
          <div class="stat-card__value">{{ monthlyCost }}</div>
          <div class="stat-card__label">Monthly Power Cost</div>
        </div>
        <div class="stat-card stat-card--critical">
          <div class="stat-card__value">{{ criticalCount }}</div>
          <div class="stat-card__label">Critical Issues</div>
        </div>
        <div class="stat-card">
          <div class="stat-card__value">{{ consolidationCount }}</div>
          <div class="stat-card__label">Consolidation Opportunities</div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs mb-2" v-if="report.status?.startsWith('complete')">
        <button class="tab-btn" v-for="t in tabs" :key="t.key" :class="{ 'tab-btn--active': activeTab === t.key }" @click="activeTab = t.key">{{ t.label }}</button>
      </div>

      <!-- Summary -->
      <div v-if="activeTab === 'summary'" class="tab-panel">
        <h2>Executive Summary</h2>
        <p v-if="narrative?.executive_summary">{{ narrative.executive_summary }}</p>
        <p v-else class="muted">No AI narrative generated. See the Findings tab for deterministic analysis.</p>

        <h2>Priority Actions</h2>
        <ol v-if="priorityActions.length">
          <li v-for="(a, i) in priorityActions" :key="i">{{ a }}</li>
        </ol>
        <p v-else class="muted">No priority actions.</p>

        <h2>Assumptions</h2>
        <ul v-if="mergedAssumptions.length">
          <li v-for="(a, i) in mergedAssumptions" :key="i">{{ a }}</li>
        </ul>
        <p v-else class="muted">None stated.</p>
      </div>

      <!-- Findings -->
      <div v-else-if="activeTab === 'findings'" class="tab-panel">
        <h2>Deterministic Findings</h2>
        <div v-if="!findings.length" class="muted">No findings.</div>
        <div v-else>
          <div v-for="(f, i) in findings" :key="i" class="finding-card" :class="`finding-card--${f.severity}`">
            <div class="finding-header">
              <span class="sev-chip" :class="`sev-${f.severity}`">{{ f.severity }}</span>
              <span class="rule-type">{{ f.rule_type }}</span>
              <span class="category">{{ f.category }}</span>
            </div>
            <h4>{{ f.title }}</h4>
            <p v-if="f.recommendation">{{ f.recommendation }}</p>
            <div v-if="f.affected_resources?.length" class="affected">
              <strong>Affected:</strong>
              <span v-for="r in f.affected_resources" :key="r" class="tag">{{ r }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Cost -->
      <div v-else-if="activeTab === 'cost'" class="tab-panel">
        <h2>Power & Cost</h2>
        <div v-if="costItems.length" class="muted">
          <p>These figures come from the cost section of the rendered report. Hover over source to see measurement origin.</p>
          <ul>
            <li v-for="(c, i) in costItems" :key="i">
              <strong>{{ c.title }}</strong> — {{ c.detail }}
            </li>
          </ul>
        </div>
        <p v-else class="muted">No AI cost commentary — see the full Raw HTML tab for the power table.</p>
      </div>

      <!-- Redundancy -->
      <div v-else-if="activeTab === 'redundancy'" class="tab-panel">
        <h2>Redundancy & Reliability</h2>
        <ul v-if="redundancyItems.length">
          <li v-for="(item, i) in redundancyItems" :key="i">
            <span class="sev-chip" :class="`sev-${item.severity || 'info'}`">{{ item.severity || 'info' }}</span>
            <strong>{{ item.title }}</strong> — {{ item.detail }}
          </li>
        </ul>
        <p v-else class="muted">No redundancy findings.</p>
      </div>

      <!-- Hardware -->
      <div v-else-if="activeTab === 'hardware'" class="tab-panel">
        <h2>Hardware Refresh Recommendations</h2>
        <ul v-if="hardwareItems.length">
          <li v-for="(h, i) in hardwareItems" :key="i">
            <strong>{{ h.title }}</strong> — {{ h.detail }}
          </li>
        </ul>
        <p v-else class="muted">No hardware refresh recommendations.</p>
      </div>

      <!-- Raw -->
      <div v-else-if="activeTab === 'raw'" class="tab-panel">
        <h2>Raw Rendered Report</h2>
        <div v-if="report.rendered_html" class="raw-html-frame" v-html="report.rendered_html"></div>
        <p v-else class="muted">Rendered content not available yet.</p>
      </div>

      <!-- Notes -->
      <div class="notes-section" v-if="report.status?.startsWith('complete')">
        <h3>Operator Notes</h3>
        <textarea v-model="notesDraft" class="form-input" rows="3" placeholder="Add notes to this report…"></textarea>
        <div class="notes-actions">
          <button class="btn btn-ghost btn-sm" @click="notesDraft = report.manual_notes || ''">Reset</button>
          <button class="btn btn-primary btn-sm" :disabled="notesDraft === (report.manual_notes || '')" @click="saveNotes">Save Notes</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'AIReportDetail',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const toast = useToast()

    const loading = ref(true)
    const report = ref(null)
    const regenerating = ref(false)
    const activeTab = ref('summary')
    const notesDraft = ref('')
    let pollTimer = null

    const tabs = [
      { key: 'summary', label: 'Summary' },
      { key: 'findings', label: 'Findings' },
      { key: 'cost', label: 'Cost' },
      { key: 'redundancy', label: 'Redundancy' },
      { key: 'hardware', label: 'Hardware' },
      { key: 'raw', label: 'Raw Evidence' },
    ]

    const narrative = computed(() => report.value?.ai_narrative || null)
    const findings = computed(() => report.value?.findings || [])
    const mergedAssumptions = computed(() => {
      const merged = [...(report.value?.assumptions || [])]
      if (narrative.value?.assumptions) merged.push(...narrative.value.assumptions)
      return merged
    })
    const priorityActions = computed(() => narrative.value?.priority_actions || [])
    const costItems = computed(() => narrative.value?.cost_efficiency_findings || [])
    const redundancyItems = computed(() => narrative.value?.redundancy_findings || [])
    const hardwareItems = computed(() => narrative.value?.hardware_refresh_recommendations || [])

    const criticalCount = computed(() => findings.value.filter(f => f.severity === 'critical').length)
    const warningCount = computed(() => findings.value.filter(f => f.severity === 'warning').length)
    const consolidationCount = computed(() => findings.value.filter(f => f.rule_type === 'node_underutilized' || f.rule_type === 'likely_oversized_vms').length)

    const healthScore = computed(() => {
      // Simple derived score: 100 - 15*critical - 5*warning, floored to 0.
      const base = 100 - criticalCount.value * 15 - warningCount.value * 5
      return Math.max(0, base)
    })
    const monthlyCost = computed(() => {
      // Parse the rendered markdown for the cluster cost (best-effort display).
      const md = report.value?.rendered_markdown || ''
      const m = md.match(/Cluster estimated monthly cost:\s*\*\*([^\*]+)\*\*/)
      return m ? m[1].trim() : '—'
    })

    const loadReport = async () => {
      try {
        const res = await api.aiReports.getReport(route.params.id)
        report.value = res.data
        notesDraft.value = res.data.manual_notes || ''
      } catch (e) {
        report.value = null
      } finally {
        loading.value = false
      }
    }

    const maybePoll = () => {
      if (!report.value) return
      if (report.value.status === 'queued' || report.value.status === 'running') {
        pollTimer = setTimeout(async () => {
          await loadReport()
          maybePoll()
        }, 3000)
      }
    }

    const regenerate = async () => {
      regenerating.value = true
      try {
        const res = await api.aiReports.regenerate(report.value.id)
        toast.success(`Regenerated as #${res.data.id}`)
        router.push(`/ai-reports/${res.data.id}`)
      } finally {
        regenerating.value = false
      }
    }

    const saveNotes = async () => {
      try {
        await api.aiReports.updateNotes(report.value.id, notesDraft.value)
        report.value.manual_notes = notesDraft.value
        toast.success('Notes saved')
      } catch (e) {}
    }

    const downloadMarkdown = async () => {
      const res = await api.aiReports.exportMarkdown(report.value.id)
      _download(res.data, `report-${report.value.id}.md`, 'text/markdown')
    }
    const downloadHtml = async () => {
      const res = await api.aiReports.exportHtml(report.value.id)
      _download(res.data, `report-${report.value.id}.html`, 'text/html')
    }
    const _download = (content, filename, mime) => {
      const blob = new Blob([content], { type: mime })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    }

    onMounted(async () => {
      await loadReport()
      maybePoll()
    })
    onUnmounted(() => { if (pollTimer) clearTimeout(pollTimer) })

    watch(() => route.params.id, async () => {
      loading.value = true
      await loadReport()
      maybePoll()
    })

    return {
      loading, report, regenerating, activeTab, notesDraft,
      tabs, narrative, findings, mergedAssumptions, priorityActions,
      costItems, redundancyItems, hardwareItems,
      criticalCount, warningCount, consolidationCount, healthScore, monthlyCost,
      regenerate, saveNotes, downloadMarkdown, downloadHtml,
    }
  },
}
</script>

<style scoped>
.ai-report-detail { padding: 1.25rem; }

.page-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  flex-wrap: wrap; gap: 1rem;
}
.page-title { font-size: 1.4rem; margin: 0.25rem 0 0; }
.page-subtitle { color: #6b7280; margin: 0.25rem 0 0; font-size: 0.85rem; display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.dot { color: #d1d5db; }
.tag {
  display: inline-block; padding: 0.1rem 0.4rem; border-radius: 3px;
  background: #eef2ff; color: #4338ca; font-size: 0.7rem; font-weight: 600; margin-left: 0.25rem;
}

.page-header-actions { display: flex; gap: 0.4rem; flex-wrap: wrap; }

.stat-cards {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem;
  margin-bottom: 1.25rem;
}
@media (max-width: 720px) { .stat-cards { grid-template-columns: repeat(2, 1fr); } }
.stat-card {
  background: white; padding: 1rem; border-radius: 6px;
  border: 1px solid #e5e7eb; text-align: center;
}
.stat-card__value { font-size: 1.75rem; font-weight: 700; color: #111827; }
.stat-card__label { font-size: 0.75rem; color: #6b7280; margin-top: 0.25rem; }
.stat-card--critical .stat-card__value { color: #b91c1c; }

.tabs { display: flex; gap: 0.5rem; border-bottom: 1px solid #e5e7eb; flex-wrap: wrap; }
.tab-btn {
  background: none; border: none; padding: 0.5rem 1rem; cursor: pointer;
  color: #6b7280; font-size: 0.9rem; border-bottom: 2px solid transparent;
}
.tab-btn:hover { color: #111827; }
.tab-btn--active { color: #2563eb; border-bottom-color: #2563eb; font-weight: 600; }

.tab-panel {
  background: white; padding: 1.25rem; border-radius: 6px;
  border: 1px solid #e5e7eb;
}
.tab-panel h2 { font-size: 1.05rem; margin: 0 0 0.75rem; color: #111827; }
.tab-panel h2:not(:first-child) { margin-top: 1.5rem; }
.tab-panel p { margin: 0 0 0.75rem; color: #374151; line-height: 1.5; }
.tab-panel ul, .tab-panel ol { padding-left: 1.25rem; color: #374151; }
.tab-panel li { margin: 0.35rem 0; }
.muted { color: #9ca3af; font-size: 0.9rem; }

.finding-card {
  background: #f9fafb; padding: 0.9rem; border-radius: 5px; margin-bottom: 0.6rem;
  border-left: 3px solid #9ca3af;
}
.finding-card--critical { border-left-color: #b91c1c; background: #fef2f2; }
.finding-card--warning { border-left-color: #b45309; background: #fffbeb; }
.finding-card--info { border-left-color: #1d4ed8; background: #eff6ff; }
.finding-card h4 { margin: 0.35rem 0; }

.finding-header { display: flex; gap: 0.5rem; align-items: center; font-size: 0.8rem; }
.rule-type { color: #6b7280; font-family: monospace; }
.category { color: #9ca3af; text-transform: uppercase; font-size: 0.7rem; font-weight: 600; }

.sev-chip {
  display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px;
  font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
}
.sev-critical { background: #fee2e2; color: #b91c1c; }
.sev-warning { background: #fef3c7; color: #b45309; }
.sev-info { background: #dbeafe; color: #1d4ed8; }

.affected { margin-top: 0.4rem; font-size: 0.8rem; color: #4b5563; }

.notice { padding: 0.7rem 1rem; border-radius: 5px; margin-bottom: 1rem; font-size: 0.9rem; }
.notice-info { background: #dbeafe; color: #1e40af; }
.notice-warn { background: #fef3c7; color: #b45309; }
.notice-critical { background: #fee2e2; color: #b91c1c; }
.notice-detail { font-size: 0.8rem; margin-top: 0.25rem; font-family: monospace; }

.raw-html-frame {
  background: white; padding: 1rem; border-radius: 4px;
  border: 1px solid #e5e7eb; max-height: 800px; overflow: auto;
}

.notes-section {
  margin-top: 1.5rem; padding: 1rem; background: white;
  border: 1px solid #e5e7eb; border-radius: 6px;
}
.notes-section h3 { margin: 0 0 0.6rem; font-size: 1rem; }
.notes-actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.6rem; }
.form-input { width: 100%; padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px; font-family: inherit; font-size: 0.9rem; }

.empty-state, .loading-state { text-align: center; padding: 3rem 1rem; color: #6b7280; }
.empty-icon { font-size: 2.5rem; margin-bottom: 0.5rem; }
.spinner {
  display: inline-block; width: 2.5rem; height: 2.5rem;
  border: 3px solid #e5e7eb; border-top-color: #3b82f6;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

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
