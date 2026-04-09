<template>
  <div class="analysis-view">
    <div class="page-header">
      <div class="page-header-left">
        <h1 class="page-title">🔬 Infrastructure Analysis</h1>
        <p class="page-subtitle">Optimization suggestions based on your current infrastructure state</p>
      </div>
      <div class="page-header-actions">
        <button class="btn btn-outline btn-sm" @click="runAnalysis" :disabled="running">
          <span v-if="running">⏳ Analyzing…</span>
          <span v-else>▶ Run Now</span>
        </button>
        <button v-if="activeRecs.length" class="btn btn-ghost btn-sm" @click="dismissAll()">
          Dismiss All
        </button>
      </div>
    </div>

    <!-- Summary bar -->
    <div class="summary-bar" v-if="!loading">
      <div
        v-for="cat in categories"
        :key="cat.key"
        class="summary-chip"
        :class="{ 'summary-chip--active': filterCategory === cat.key }"
        @click="toggleCategory(cat.key)"
      >
        <span class="summary-chip-icon">{{ cat.icon }}</span>
        <span class="summary-chip-label">{{ cat.label }}</span>
        <span class="summary-chip-count" :class="severityClass(catSeverity(cat.key))">
          {{ catCount(cat.key) }}
        </span>
      </div>
      <div class="summary-chip summary-chip--total" @click="filterCategory = null">
        <span class="summary-chip-label">All</span>
        <span class="summary-chip-count">{{ activeRecs.length }}</span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading recommendations…</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="filteredRecs.length === 0" class="empty-state">
      <div class="empty-icon">✅</div>
      <h3>{{ filterCategory ? 'No issues in this category' : 'Everything looks good!' }}</h3>
      <p v-if="!filterCategory">No recommendations at this time. Run an analysis to refresh.</p>
      <p v-else>No active recommendations in <strong>{{ categoryLabel(filterCategory) }}</strong>.</p>
      <button class="btn btn-primary btn-sm mt-2" @click="runAnalysis" :disabled="running">
        {{ running ? 'Analyzing…' : 'Run Analysis' }}
      </button>
    </div>

    <!-- Recommendation cards grouped by category -->
    <div v-else class="rec-groups">
      <div
        v-for="cat in visibleCategories"
        :key="cat.key"
        class="rec-group"
      >
        <div class="rec-group-header">
          <span>{{ cat.icon }} {{ cat.label }}</span>
          <span class="rec-group-count">{{ groupedRecs[cat.key]?.length || 0 }}</span>
        </div>
        <div class="rec-list">
          <div
            v-for="rec in groupedRecs[cat.key]"
            :key="rec.id"
            class="rec-card"
            :class="`rec-card--${rec.severity}`"
          >
            <div class="rec-card-header">
              <span class="rec-severity-badge" :class="`badge--${rec.severity}`">
                {{ severityIcon(rec.severity) }} {{ rec.severity }}
              </span>
              <span class="rec-rule-type">{{ formatRuleType(rec.rule_type) }}</span>
              <button class="rec-dismiss-btn" @click="dismiss(rec.id)" title="Dismiss">✕</button>
            </div>

            <h3 class="rec-title">{{ rec.title }}</h3>

            <div class="rec-context" v-if="rec.node || rec.vm_name || rec.resource_label">
              <span v-if="rec.vm_name" class="rec-context-chip">🖥️ {{ rec.vm_name }}<span v-if="rec.vmid" class="rec-vmid"> ({{ rec.vmid }})</span></span>
              <span v-if="rec.node" class="rec-context-chip">📡 {{ rec.node }}</span>
              <span v-if="rec.resource_label" class="rec-context-chip">🗄️ {{ rec.resource_label }}</span>
            </div>

            <p class="rec-detail">{{ rec.detail }}</p>

            <div class="rec-metric" v-if="rec.metric_value !== null && rec.metric_value !== undefined">
              <span class="rec-metric-label">Current:</span>
              <span class="rec-metric-value">{{ rec.metric_value }}{{ rec.metric_unit }}</span>
              <span v-if="rec.threshold" class="rec-metric-threshold">
                / threshold {{ rec.threshold }}{{ rec.metric_unit }}
              </span>
            </div>

            <div class="rec-suggestion" v-if="rec.suggestion">
              <span class="rec-suggestion-icon">💡</span>
              <span>{{ rec.suggestion }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Dismissed section toggle -->
    <div class="dismissed-toggle" v-if="!loading">
      <button class="btn btn-ghost btn-xs" @click="showDismissed = !showDismissed">
        {{ showDismissed ? '▲ Hide dismissed' : `▼ Show dismissed (${dismissedRecs.length})` }}
      </button>
    </div>

    <div v-if="showDismissed && dismissedRecs.length" class="rec-list dismissed-list">
      <div
        v-for="rec in dismissedRecs"
        :key="rec.id"
        class="rec-card rec-card--dismissed"
      >
        <div class="rec-card-header">
          <span class="rec-severity-badge badge--dismissed">dismissed</span>
          <span class="rec-rule-type">{{ formatRuleType(rec.rule_type) }}</span>
        </div>
        <h3 class="rec-title">{{ rec.title }}</h3>
        <p class="rec-dismissed-at" v-if="rec.dismissed_at">
          Dismissed {{ formatDate(rec.dismissed_at) }}
        </p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const CATEGORIES = [
  { key: 'performance', label: 'Performance', icon: '⚡' },
  { key: 'reliability', label: 'Reliability', icon: '🛡️' },
  { key: 'storage', label: 'Storage', icon: '🗄️' },
  { key: 'configuration', label: 'Configuration', icon: '⚙️' },
]

const RULE_TYPE_LABELS = {
  node_high_cpu: 'High CPU',
  node_high_memory: 'High Memory',
  node_underutilized: 'Underutilized Node',
  cluster_imbalanced: 'Cluster Imbalance',
  vm_stopped: 'VM Powered Off',
  vm_oversized_cpu: 'Oversized CPU',
  vm_oversized_memory: 'Excess RAM',
  vm_no_backup: 'No Recent Backup',
  vm_old_snapshot: 'Old Snapshot',
  storage_high_usage: 'High Storage Usage',
}

export default {
  name: 'Analysis',
  setup() {
    const toast = useToast()
    const loading = ref(true)
    const running = ref(false)
    const recs = ref([])
    const filterCategory = ref(null)
    const showDismissed = ref(false)

    const activeRecs = computed(() => recs.value.filter(r => !r.dismissed))
    const dismissedRecs = computed(() => recs.value.filter(r => r.dismissed))

    const filteredRecs = computed(() => {
      let list = activeRecs.value
      if (filterCategory.value) list = list.filter(r => r.category === filterCategory.value)
      return list
    })

    const groupedRecs = computed(() => {
      const groups = {}
      for (const rec of filteredRecs.value) {
        if (!groups[rec.category]) groups[rec.category] = []
        groups[rec.category].push(rec)
      }
      return groups
    })

    const visibleCategories = computed(() =>
      CATEGORIES.filter(c => groupedRecs.value[c.key]?.length > 0)
    )

    const categories = CATEGORIES

    function catCount(cat) {
      return activeRecs.value.filter(r => r.category === cat).length
    }

    function catSeverity(cat) {
      const list = activeRecs.value.filter(r => r.category === cat)
      if (list.some(r => r.severity === 'critical')) return 'critical'
      if (list.some(r => r.severity === 'warning')) return 'warning'
      return 'info'
    }

    function severityClass(sev) {
      return `count--${sev}`
    }

    function severityIcon(sev) {
      return { critical: '🔴', warning: '⚠️', info: 'ℹ️' }[sev] || 'ℹ️'
    }

    function categoryLabel(key) {
      return CATEGORIES.find(c => c.key === key)?.label || key
    }

    function toggleCategory(cat) {
      filterCategory.value = filterCategory.value === cat ? null : cat
    }

    function formatRuleType(rt) {
      return RULE_TYPE_LABELS[rt] || rt.replace(/_/g, ' ')
    }

    function formatDate(iso) {
      if (!iso) return ''
      return new Date(iso).toLocaleString()
    }

    async function load() {
      try {
        loading.value = true
        const [activeRes, dismissedRes] = await Promise.all([
          api.analysis.getRecommendations(),
          api.analysis.getRecommendations({ include_dismissed: true }),
        ])
        // Merge: active + dismissed that aren't in active
        const activeIds = new Set((activeRes.data || []).map(r => r.id))
        const dismissed = (dismissedRes.data || []).filter(r => !activeIds.has(r.id))
        recs.value = [...(activeRes.data || []), ...dismissed]
      } catch (e) {
        toast.error('Failed to load recommendations')
      } finally {
        loading.value = false
      }
    }

    async function runAnalysis() {
      running.value = true
      try {
        await api.analysis.run()
        toast.info('Analysis started — refreshing in 5s…')
        setTimeout(load, 5000)
      } catch (e) {
        toast.error('Failed to start analysis')
      } finally {
        running.value = false
      }
    }

    async function dismiss(id) {
      try {
        await api.analysis.dismiss(id)
        const rec = recs.value.find(r => r.id === id)
        if (rec) {
          rec.dismissed = true
          rec.dismissed_at = new Date().toISOString()
        }
        toast.success('Recommendation dismissed')
      } catch (e) {
        toast.error('Failed to dismiss recommendation')
      }
    }

    async function dismissAll(cat = null) {
      try {
        await api.analysis.dismissAll(cat)
        activeRecs.value.forEach(r => {
          if (!cat || r.category === cat) {
            r.dismissed = true
            r.dismissed_at = new Date().toISOString()
          }
        })
        toast.success('Dismissed')
      } catch (e) {
        toast.error('Failed to dismiss')
      }
    }

    onMounted(load)

    return {
      loading, running, recs, filterCategory, showDismissed,
      activeRecs, dismissedRecs, filteredRecs, groupedRecs, visibleCategories,
      categories,
      catCount, catSeverity, severityClass, severityIcon, categoryLabel,
      toggleCategory, formatRuleType, formatDate,
      load, runAnalysis, dismiss, dismissAll,
    }
  }
}
</script>

<style scoped>
.analysis-view {
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.25rem;
}

.page-subtitle {
  color: var(--text-secondary);
  margin: 0;
  font-size: 0.875rem;
}

.page-header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

/* Summary bar */
.summary-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.summary-chip {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.75rem;
  border-radius: 2rem;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s, border-color 0.15s;
  user-select: none;
}

.summary-chip:hover {
  border-color: var(--accent-primary);
}

.summary-chip--active {
  border-color: var(--accent-primary);
  background: color-mix(in srgb, var(--accent-primary) 12%, transparent);
}

.summary-chip--total {
  margin-left: auto;
}

.summary-chip-count {
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 0.75rem;
  font-size: 0.8rem;
  background: var(--bg-tertiary);
}

.count--critical { background: rgba(239,68,68,0.2); color: #ef4444; }
.count--warning  { background: rgba(245,158,11,0.2); color: #f59e0b; }
.count--info     { background: rgba(59,130,246,0.2); color: #3b82f6; }

/* Loading / empty */
.loading-state, .empty-state {
  text-align: center;
  padding: 4rem 2rem;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 0.75rem;
}

.spinner {
  width: 2rem;
  height: 2rem;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Groups */
.rec-groups { display: flex; flex-direction: column; gap: 1.5rem; }

.rec-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--text-primary);
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.rec-group-count {
  background: var(--bg-tertiary);
  border-radius: 1rem;
  padding: 0.1rem 0.5rem;
  font-size: 0.8rem;
}

.rec-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 1rem;
}

/* Rec card */
.rec-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  position: relative;
}

.rec-card--critical { border-left: 3px solid #ef4444; }
.rec-card--warning  { border-left: 3px solid #f59e0b; }
.rec-card--info     { border-left: 3px solid #3b82f6; }
.rec-card--dismissed { opacity: 0.5; }

.rec-card-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.rec-severity-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.badge--critical { background: rgba(239,68,68,0.15); color: #ef4444; }
.badge--warning  { background: rgba(245,158,11,0.15); color: #f59e0b; }
.badge--info     { background: rgba(59,130,246,0.15); color: #3b82f6; }
.badge--dismissed { background: var(--bg-tertiary); color: var(--text-secondary); }

.rec-rule-type {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-left: auto;
}

.rec-dismiss-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.1rem 0.3rem;
  border-radius: 0.25rem;
  line-height: 1;
}
.rec-dismiss-btn:hover { background: var(--bg-tertiary); color: var(--text-primary); }

.rec-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.rec-context {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.rec-context-chip {
  font-size: 0.75rem;
  background: var(--bg-tertiary);
  padding: 0.15rem 0.5rem;
  border-radius: 0.5rem;
  color: var(--text-secondary);
}

.rec-vmid {
  opacity: 0.7;
}

.rec-detail {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.rec-metric {
  font-size: 0.8rem;
  color: var(--text-secondary);
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

.rec-metric-value {
  font-weight: 700;
  color: var(--text-primary);
}

.rec-suggestion {
  display: flex;
  gap: 0.5rem;
  font-size: 0.82rem;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--accent-primary) 6%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent-primary) 20%, transparent);
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  line-height: 1.5;
}

.rec-suggestion-icon { flex-shrink: 0; }

.rec-dismissed-at {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin: 0;
}

/* Dismissed toggle */
.dismissed-toggle {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
  text-align: center;
}

.dismissed-list {
  margin-top: 1rem;
}

/* Buttons */
.btn { display: inline-flex; align-items: center; gap: 0.4rem; border-radius: 0.5rem; font-size: 0.875rem; font-weight: 500; cursor: pointer; border: 1px solid transparent; padding: 0.4rem 0.875rem; transition: background 0.15s, border-color 0.15s; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--accent-primary); color: #fff; border-color: var(--accent-primary); }
.btn-outline { background: transparent; border-color: var(--border-color); color: var(--text-primary); }
.btn-outline:hover:not(:disabled) { border-color: var(--accent-primary); }
.btn-ghost { background: transparent; color: var(--text-secondary); }
.btn-ghost:hover:not(:disabled) { background: var(--bg-tertiary); }
.btn-sm { font-size: 0.8rem; padding: 0.3rem 0.7rem; }
.btn-xs { font-size: 0.75rem; padding: 0.2rem 0.5rem; }
.mt-2 { margin-top: 0.5rem; }
</style>
