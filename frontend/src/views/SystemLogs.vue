<template>
  <div class="system-logs-view">
    <div class="page-header">
      <h1 class="page-title">
        <span class="title-icon">📜</span>
        System Logs
      </h1>
      <p class="page-subtitle">View backend service logs and system update history</p>
    </div>

    <!-- Tab bar -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ── Backend Logs ─────────────────────────────────────────── -->
    <div v-if="activeTab === 'backend'" class="tab-content">
      <div class="toolbar">
        <div class="toolbar-left">
          <!-- Line count -->
          <label class="toolbar-label">Lines</label>
          <select v-model="backendLines" class="select-input" @change="fetchBackendLogs">
            <option :value="50">Last 50</option>
            <option :value="100">Last 100</option>
            <option :value="500">Last 500</option>
            <option :value="1000">Last 1000</option>
          </select>

          <!-- Level filter -->
          <label class="toolbar-label">Level</label>
          <select v-model="levelFilter" class="select-input">
            <option value="ALL">ALL</option>
            <option value="ERROR">ERROR</option>
            <option value="WARNING">WARNING</option>
            <option value="INFO">INFO</option>
            <option value="DEBUG">DEBUG</option>
          </select>

          <!-- Keyword search -->
          <input
            v-model="searchKeyword"
            type="text"
            class="search-input"
            placeholder="Filter keyword…"
          />
        </div>

        <div class="toolbar-right">
          <!-- Auto-refresh toggle -->
          <button
            class="btn"
            :class="autoRefresh ? 'btn-active' : 'btn-ghost'"
            @click="toggleAutoRefresh"
          >
            <span>{{ autoRefresh ? '⏸ Auto-refresh ON' : '▶ Auto-refresh OFF' }}</span>
          </button>

          <!-- Auto-scroll toggle -->
          <button
            class="btn btn-ghost"
            :class="{ 'btn-active': autoScroll }"
            @click="autoScroll = !autoScroll"
          >
            {{ autoScroll ? '⬇ Auto-scroll ON' : '⬇ Auto-scroll OFF' }}
          </button>

          <!-- Refresh -->
          <button class="btn btn-ghost" :disabled="backendLoading" @click="fetchBackendLogs">
            <span v-if="backendLoading">Loading…</span>
            <span v-else>↻ Refresh</span>
          </button>

          <!-- Download -->
          <button class="btn btn-ghost" @click="downloadLogs('backend')">⬇ Download</button>

          <!-- Clear display -->
          <button class="btn btn-ghost" @click="clearDisplay('backend')">✕ Clear</button>
        </div>
      </div>

      <!-- Status bar -->
      <div class="status-bar">
        <span class="status-info">
          {{ filteredBackendLines.length }} / {{ backendRawLines.length }} lines
          <span v-if="autoRefresh" class="refresh-indicator"> · refreshing in {{ refreshCountdown }}s</span>
        </span>
        <span v-if="backendError" class="status-error">{{ backendError }}</span>
        <span v-if="backendLastFetched" class="status-info">Last updated: {{ backendLastFetched }}</span>
      </div>

      <!-- Log area -->
      <div ref="backendLogArea" class="log-area">
        <div v-if="backendLoading && backendRawLines.length === 0" class="log-placeholder">
          Loading logs…
        </div>
        <div v-else-if="filteredBackendLines.length === 0 && !backendLoading" class="log-placeholder">
          No log lines match the current filters.
        </div>
        <div
          v-for="(line, idx) in filteredBackendLines"
          :key="idx"
          class="log-line"
          :class="lineClass(line)"
        >{{ line }}</div>
      </div>
    </div>

    <!-- ── Update Log ───────────────────────────────────────────── -->
    <div v-if="activeTab === 'updates'" class="tab-content">
      <div class="toolbar">
        <div class="toolbar-left">
          <span class="toolbar-label">System update output log</span>
        </div>
        <div class="toolbar-right">
          <button class="btn btn-ghost" :disabled="updateLoading" @click="fetchUpdateLog">
            <span v-if="updateLoading">Loading…</span>
            <span v-else>↻ Refresh</span>
          </button>
          <button class="btn btn-ghost" @click="downloadLogs('updates')">⬇ Download</button>
          <button class="btn btn-ghost" @click="clearDisplay('updates')">✕ Clear</button>
        </div>
      </div>

      <div class="status-bar">
        <span v-if="updateError" class="status-error">{{ updateError }}</span>
        <span v-else-if="updateRawLines.length" class="status-info">{{ updateRawLines.length }} lines</span>
      </div>

      <div ref="updateLogArea" class="log-area">
        <div v-if="updateLoading && updateRawLines.length === 0" class="log-placeholder">
          Loading update log…
        </div>
        <div v-else-if="updateRawLines.length === 0 && !updateLoading" class="log-placeholder">
          No update log available.
        </div>
        <div
          v-for="(line, idx) in updateRawLines"
          :key="idx"
          class="log-line"
          :class="lineClass(line)"
        >{{ line }}</div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/services/api'

export default {
  name: 'SystemLogs',

  data() {
    return {
      activeTab: 'backend',
      tabs: [
        { key: 'backend', label: 'Backend Logs' },
        { key: 'updates', label: 'Update Log' }
      ],

      // Backend Logs state
      backendRawLines: [],
      backendLines: 100,
      levelFilter: 'ALL',
      searchKeyword: '',
      backendLoading: false,
      backendError: null,
      backendLastFetched: null,
      autoRefresh: false,
      autoScroll: true,
      refreshCountdown: 5,
      _refreshTimer: null,
      _countdownTimer: null,

      // Update Log state
      updateRawLines: [],
      updateLoading: false,
      updateError: null
    }
  },

  computed: {
    filteredBackendLines() {
      let lines = this.backendRawLines

      // Level filter
      if (this.levelFilter !== 'ALL') {
        const lvl = this.levelFilter
        lines = lines.filter(l => l.toUpperCase().includes(lvl))
      }

      // Keyword filter
      if (this.searchKeyword.trim()) {
        const kw = this.searchKeyword.trim().toLowerCase()
        lines = lines.filter(l => l.toLowerCase().includes(kw))
      }

      return lines
    }
  },

  methods: {
    switchTab(key) {
      this.activeTab = key
      if (key === 'backend' && this.backendRawLines.length === 0) {
        this.fetchBackendLogs()
      } else if (key === 'updates' && this.updateRawLines.length === 0) {
        this.fetchUpdateLog()
      }
    },

    lineClass(line) {
      const u = line.toUpperCase()
      if (u.includes('ERROR') || u.includes('CRITICAL') || u.includes('FATAL')) return 'level-error'
      if (u.includes('WARNING') || u.includes('WARN')) return 'level-warning'
      if (u.includes('DEBUG')) return 'level-debug'
      return 'level-info'
    },

    async fetchBackendLogs() {
      this.backendLoading = true
      this.backendError = null
      try {
        const res = await api.logs.getBackendLogs(this.backendLines)
        const raw = res.data.logs
        if (typeof raw === 'string') {
          this.backendRawLines = raw.split('\n').filter(l => l.length > 0)
        } else if (Array.isArray(raw)) {
          this.backendRawLines = raw.filter(l => l.length > 0)
        } else {
          this.backendRawLines = []
        }
        this.backendLastFetched = new Date().toLocaleTimeString()
        this.$nextTick(() => this.scrollToBottom('backend'))
      } catch (err) {
        this.backendError = err.response?.data?.detail || err.message || 'Failed to fetch logs'
      } finally {
        this.backendLoading = false
      }
    },

    async fetchUpdateLog() {
      this.updateLoading = true
      this.updateError = null
      try {
        const res = await api.systemUpdates.log()
        const raw = res.data
        if (typeof raw === 'string') {
          this.updateRawLines = raw.split('\n').filter(l => l.length > 0)
        } else if (raw && typeof raw.log === 'string') {
          this.updateRawLines = raw.log.split('\n').filter(l => l.length > 0)
        } else if (raw && typeof raw.output === 'string') {
          this.updateRawLines = raw.output.split('\n').filter(l => l.length > 0)
        } else if (Array.isArray(raw)) {
          this.updateRawLines = raw.map(String).filter(l => l.length > 0)
        } else {
          this.updateRawLines = []
        }
        this.$nextTick(() => this.scrollToBottom('updates'))
      } catch (err) {
        this.updateError = err.response?.data?.detail || err.message || 'No update log available'
      } finally {
        this.updateLoading = false
      }
    },

    scrollToBottom(tab) {
      if (!this.autoScroll) return
      const ref = tab === 'backend' ? this.$refs.backendLogArea : this.$refs.updateLogArea
      if (ref) {
        ref.scrollTop = ref.scrollHeight
      }
    },

    toggleAutoRefresh() {
      this.autoRefresh = !this.autoRefresh
      if (this.autoRefresh) {
        this.startAutoRefresh()
      } else {
        this.stopAutoRefresh()
      }
    },

    startAutoRefresh() {
      this.refreshCountdown = 5
      this._countdownTimer = setInterval(() => {
        this.refreshCountdown -= 1
        if (this.refreshCountdown <= 0) {
          this.refreshCountdown = 5
        }
      }, 1000)
      this._refreshTimer = setInterval(() => {
        if (this.activeTab === 'backend') {
          this.fetchBackendLogs()
        }
      }, 5000)
    },

    stopAutoRefresh() {
      if (this._refreshTimer) {
        clearInterval(this._refreshTimer)
        this._refreshTimer = null
      }
      if (this._countdownTimer) {
        clearInterval(this._countdownTimer)
        this._countdownTimer = null
      }
      this.refreshCountdown = 5
    },

    clearDisplay(tab) {
      if (tab === 'backend') {
        this.backendRawLines = []
        this.backendLastFetched = null
        this.backendError = null
      } else if (tab === 'updates') {
        this.updateRawLines = []
        this.updateError = null
      }
    },

    downloadLogs(tab) {
      let content = ''
      let filename = ''
      if (tab === 'backend') {
        content = this.filteredBackendLines.join('\n')
        filename = `depl0y-backend-logs-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`
      } else {
        content = this.updateRawLines.join('\n')
        filename = `depl0y-update-log-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`
      }
      const blob = new Blob([content], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    }
  },

  mounted() {
    this.fetchBackendLogs()
  },

  beforeUnmount() {
    this.stopAutoRefresh()
  }
}
</script>

<style scoped>
.system-logs-view {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 4rem);
  box-sizing: border-box;
}

/* ── Page Header ─────────────────────────────────────────── */
.page-header {
  margin-bottom: 1.5rem;
}

.page-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary, #f1f5f9);
  margin: 0 0 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.title-icon {
  font-size: 1.5rem;
}

.page-subtitle {
  color: var(--text-muted, #94a3b8);
  margin: 0;
  font-size: 0.9rem;
}

/* ── Tabs ────────────────────────────────────────────────── */
.tab-bar {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1rem;
  border-bottom: 2px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 0;
}

.tab-btn {
  padding: 0.5rem 1.25rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted, #94a3b8);
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  margin-bottom: -2px;
  transition: color 0.2s, border-color 0.2s;
}

.tab-btn:hover {
  color: var(--text-primary, #f1f5f9);
}

.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

/* ── Tab content ─────────────────────────────────────────── */
.tab-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

/* ── Toolbar ─────────────────────────────────────────────── */
.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  justify-content: space-between;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.toolbar-label {
  font-size: 0.8rem;
  color: var(--text-muted, #94a3b8);
  white-space: nowrap;
}

.select-input {
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text-primary, #f1f5f9);
  border-radius: 6px;
  padding: 0.35rem 0.6rem;
  font-size: 0.85rem;
  cursor: pointer;
}

.select-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.search-input {
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text-primary, #f1f5f9);
  border-radius: 6px;
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
  width: 200px;
}

.search-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.search-input::placeholder {
  color: #4b5563;
}

/* ── Buttons ─────────────────────────────────────────────── */
.btn {
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 500;
  transition: all 0.2s;
  white-space: nowrap;
}

.btn-ghost {
  background: transparent;
  color: var(--text-muted, #94a3b8);
}

.btn-ghost:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.07);
  color: var(--text-primary, #f1f5f9);
}

.btn-active {
  background: rgba(59, 130, 246, 0.15);
  border-color: #3b82f6;
  color: #60a5fa;
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* ── Status bar ──────────────────────────────────────────── */
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  font-size: 0.78rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.status-info {
  color: var(--text-muted, #64748b);
}

.status-error {
  color: #f87171;
}

.refresh-indicator {
  color: #60a5fa;
}

/* ── Log area ────────────────────────────────────────────── */
.log-area {
  flex: 1;
  overflow-y: auto;
  background: #0d1117;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  font-family: 'JetBrains Mono', 'Fira Mono', 'Cascadia Code', 'Consolas', 'Courier New', monospace;
  font-size: 0.8rem;
  line-height: 1.6;
  min-height: 200px;
}

.log-placeholder {
  color: #4b5563;
  text-align: center;
  padding: 3rem 0;
  font-family: inherit;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
  padding: 0.05rem 0;
  transition: background 0.1s;
}

.log-line:hover {
  background: rgba(255, 255, 255, 0.04);
  border-radius: 3px;
}

/* Log level colours */
.level-error {
  color: #f87171;
}

.level-warning {
  color: #fbbf24;
}

.level-info {
  color: #e2e8f0;
}

.level-debug {
  color: #6b7280;
}

/* ── Scrollbar ───────────────────────────────────────────── */
.log-area::-webkit-scrollbar {
  width: 6px;
}

.log-area::-webkit-scrollbar-track {
  background: transparent;
}

.log-area::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 3px;
}

.log-area::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.22);
}

/* ── Responsive ──────────────────────────────────────────── */
@media (max-width: 768px) {
  .system-logs-view {
    padding: 1rem;
  }

  .toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .search-input {
    width: 100%;
  }
}
</style>
