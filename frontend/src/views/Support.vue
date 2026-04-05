<template>
  <div class="support-page">
    <div class="page-header">
      <div class="breadcrumb">Support</div>
      <h1>Support &amp; Project Info</h1>
      <p class="text-muted">Depl0y is free and open source. Here's how you can help keep it going.</p>
    </div>

    <!-- Project Info Card -->
    <div class="card project-info-card">
      <div class="project-logo">
        <span class="logo-text">Depl0y</span>
        <span class="version-badge">v{{ version }}</span>
      </div>
      <div class="project-details">
        <div class="detail-row">
          <span class="detail-label">License</span>
          <span class="detail-value">MIT License — free to use, modify, and distribute</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Repository</span>
          <a href="https://github.com/agit8or1/Depl0y" target="_blank" rel="noopener noreferrer" class="detail-link">
            github.com/agit8or1/Depl0y
          </a>
        </div>
        <div class="detail-row">
          <span class="detail-label">Website</span>
          <a href="https://mspreboot.com" target="_blank" rel="noopener noreferrer" class="detail-link">
            mspreboot.com
          </a>
        </div>
        <div class="detail-row">
          <span class="detail-label">Stack</span>
          <span class="detail-value">FastAPI · Vue 3 · SQLite · Proxmox VE API</span>
        </div>
      </div>
      <div class="project-actions">
        <a href="https://github.com/agit8or1/Depl0y" target="_blank" rel="noopener noreferrer" class="btn btn-outline">
          View on GitHub
        </a>
        <a href="https://github.com/agit8or1/Depl0y/releases" target="_blank" rel="noopener noreferrer" class="btn btn-outline">
          Releases
        </a>
      </div>
    </div>

    <!-- Support Grid -->
    <div class="support-grid">
      <a href="https://github.com/sponsors/agit8or1" target="_blank" rel="noopener noreferrer" class="support-card sponsor-card">
        <div class="card-icon">&#10084;&#65039;</div>
        <h3>Sponsor the Project</h3>
        <p>Buy us a coffee via GitHub Sponsors. Every contribution helps fund continued development and new features.</p>
        <span class="card-link sponsor-link">Become a sponsor &rarr;</span>
      </a>

      <a href="https://github.com/agit8or1/Depl0y" target="_blank" rel="noopener noreferrer" class="support-card">
        <div class="card-icon">&#11088;</div>
        <h3>Star on GitHub</h3>
        <p>Give Depl0y a star on GitHub — it helps others discover the project and signals that people find it useful.</p>
        <span class="card-link">Star on GitHub &rarr;</span>
      </a>

      <a href="https://mspreboot.com" target="_blank" rel="noopener noreferrer" class="support-card">
        <div class="card-icon">&#127760;</div>
        <h3>Visit mspreboot.com</h3>
        <p>Check out the team behind Depl0y. See other projects, tools, and resources we build for sysadmins and homelabbers.</p>
        <span class="card-link">mspreboot.com &rarr;</span>
      </a>
    </div>

    <!-- Community / Bug Reports -->
    <div class="card contribute-card">
      <h3>Community &amp; Contributing</h3>
      <div class="contribute-grid">
        <div class="contribute-item">
          <div class="contribute-icon">&#128027;</div>
          <div>
            <h4>Report a Bug</h4>
            <p class="text-sm text-muted">Found an issue? Open a GitHub issue with reproduction steps, logs, and your Proxmox version. Check existing issues first to avoid duplicates.</p>
            <a href="https://github.com/agit8or1/Depl0y/issues/new?template=bug_report.md" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline">
              Open Bug Report
            </a>
          </div>
        </div>
        <div class="contribute-item">
          <div class="contribute-icon">&#128161;</div>
          <div>
            <h4>Request a Feature</h4>
            <p class="text-sm text-muted">Have an idea for a new feature or improvement? Start a GitHub Discussion to get community feedback before opening a PR.</p>
            <a href="https://github.com/agit8or1/Depl0y/discussions/new?category=ideas" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline">
              Start a Discussion
            </a>
          </div>
        </div>
        <div class="contribute-item">
          <div class="contribute-icon">&#128260;</div>
          <div>
            <h4>Contribute Code</h4>
            <p class="text-sm text-muted">Pull requests are welcome. Fork the repo, create a feature branch, write clean code, and open a PR against <code>main</code>. See CONTRIBUTING.md for guidelines.</p>
            <a href="https://github.com/agit8or1/Depl0y/fork" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline">
              Fork on GitHub
            </a>
          </div>
        </div>
        <div class="contribute-item">
          <div class="contribute-icon">&#128172;</div>
          <div>
            <h4>Browse Issues</h4>
            <p class="text-sm text-muted">Browse open issues to find good first issues, help answer questions, or triage existing reports to help the maintainers.</p>
            <a href="https://github.com/agit8or1/Depl0y/issues" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline">
              Browse Issues
            </a>
          </div>
        </div>
      </div>
    </div>

    <!-- Diagnostics (admin only) -->
    <div v-if="isAdmin" class="card diagnostics-card">
      <h3>Diagnostics <span class="admin-badge">Admin Only</span></h3>
      <p class="text-muted text-sm">Collect system information, check database integrity, and verify service health. Use these tools when troubleshooting issues.</p>

      <div class="diag-grid">
        <!-- Health Check -->
        <div class="diag-panel">
          <div class="diag-panel-header">
            <span class="diag-title">Service Health</span>
            <span v-if="healthStatus" :class="['health-badge', healthStatus.status === 'healthy' ? 'health-ok' : 'health-warn']">
              {{ healthStatus.status }}
            </span>
          </div>
          <p class="text-sm text-muted">Checks API and database connectivity.</p>
          <div v-if="healthStatus" class="health-details">
            <div class="health-row">
              <span>API</span>
              <span class="health-ok-text">OK</span>
            </div>
            <div class="health-row">
              <span>Database</span>
              <span :class="healthStatus.db === 'ok' ? 'health-ok-text' : 'health-err-text'">{{ healthStatus.db }}</span>
            </div>
          </div>
          <button class="btn btn-sm btn-outline mt-1" :disabled="healthLoading" @click="checkHealth">
            {{ healthLoading ? 'Checking...' : 'Run Health Check' }}
          </button>
        </div>

        <!-- DB Integrity -->
        <div class="diag-panel">
          <div class="diag-panel-header">
            <span class="diag-title">Database Integrity</span>
            <span v-if="dbCheckResult !== null" :class="['health-badge', dbCheckResult.ok ? 'health-ok' : 'health-warn']">
              {{ dbCheckResult.ok ? 'OK' : 'Issues Found' }}
            </span>
          </div>
          <p class="text-sm text-muted">Runs SQLite <code>PRAGMA integrity_check</code> to detect corruption.</p>
          <div v-if="dbCheckResult" class="db-results">
            <div v-for="(line, i) in dbCheckResult.results" :key="i" class="db-result-line">{{ line }}</div>
          </div>
          <button class="btn btn-sm btn-outline mt-1" :disabled="dbCheckLoading" @click="runDbCheck">
            {{ dbCheckLoading ? 'Checking...' : 'Check Integrity' }}
          </button>
        </div>

        <!-- Download Diagnostic Bundle -->
        <div class="diag-panel">
          <div class="diag-panel-header">
            <span class="diag-title">Diagnostic Bundle</span>
          </div>
          <p class="text-sm text-muted">Downloads a JSON file containing version info, DB stats, uptime, and the last 100 log lines. Useful for bug reports.</p>
          <div v-if="diagData" class="diag-summary">
            <div class="diag-row"><span>Version</span><span>{{ diagData.version }}</span></div>
            <div class="diag-row"><span>Users</span><span>{{ diagData.user_count }}</span></div>
            <div class="diag-row"><span>Hosts</span><span>{{ diagData.host_count }}</span></div>
            <div class="diag-row"><span>VMs (managed)</span><span>{{ diagData.vm_count }}</span></div>
            <div class="diag-row"><span>DB size</span><span>{{ formatBytes(diagData.db_size_bytes) }}</span></div>
            <div class="diag-row"><span>Uptime</span><span>{{ formatUptime(diagData.uptime_seconds) }}</span></div>
          </div>
          <button class="btn btn-sm btn-primary mt-1" :disabled="diagLoading" @click="downloadDiagnostics">
            {{ diagLoading ? 'Collecting...' : 'Download Bundle' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Changelog -->
    <div class="card changelog-card">
      <h3>Changelog</h3>
      <div class="changelog-list">
        <div class="changelog-entry">
          <div class="changelog-header">
            <span class="changelog-version">v1.7.0</span>
            <span class="changelog-date">2025-11</span>
            <span class="changelog-badge badge-primary">Current</span>
          </div>
          <ul class="changelog-items">
            <li>Full Proxmox VE management: VM control, LXC containers, node detail, storage browser</li>
            <li>noVNC graphical console and xterm.js node/container terminal</li>
            <li>VM disk resize, NIC management, snapshot create/restore/delete</li>
            <li>Per-VM and datacenter-level firewall rule management</li>
            <li>Proxmox Backup Server (PBS) datastore browsing and restore</li>
            <li>High Availability resource management (add, remove, monitor)</li>
            <li>VM template management — convert and clone in one click</li>
            <li>Cluster status and quorum monitoring on the Dashboard</li>
            <li>Global Ctrl+K search across all VMs, containers, nodes, and hosts</li>
            <li>Proxmox user and pool management</li>
          </ul>
        </div>

        <div class="changelog-entry">
          <div class="changelog-header">
            <span class="changelog-version">v1.6.2</span>
            <span class="changelog-date">2025-08</span>
          </div>
          <ul class="changelog-items">
            <li>LLM deployment wizard — deploy Ollama-backed VMs from a catalog in one click</li>
            <li>AI Tune panel: pull/delete models, conversation logging, RAG document ingestion</li>
            <li>iDRAC / iLO management integration for bare-metal power control</li>
            <li>Audit log viewer for all user actions with export support</li>
            <li>IP filtering and GeoIP middleware for access control</li>
            <li>Rate limiting middleware (configurable per-minute request cap)</li>
          </ul>
        </div>

        <div class="changelog-entry">
          <div class="changelog-header">
            <span class="changelog-version">v1.6.0</span>
            <span class="changelog-date">2025-05</span>
          </div>
          <ul class="changelog-items">
            <li>Cloud image fast-deploy (30-second VM provisioning via cloned templates)</li>
            <li>Multi-host Proxmox support — register and manage multiple PVE clusters</li>
            <li>Dashboard redesign with live PVE stats, cluster health, and quick VM search</li>
            <li>TOTP two-factor authentication for user accounts</li>
            <li>Role-based access control: admin, operator, viewer</li>
            <li>SMTP email notifications for task completion and alerts</li>
          </ul>
        </div>

        <div class="changelog-entry">
          <div class="changelog-header">
            <span class="changelog-version">v1.5.x</span>
            <span class="changelog-date">2025-02</span>
          </div>
          <ul class="changelog-items">
            <li>PBS (Proxmox Backup Server) integration for scheduled VM backups</li>
            <li>ISO image management with URL download and upload</li>
            <li>VM update manager — check and apply OS updates over SSH</li>
            <li>Security scan integration (unattended-upgrades, CVE check)</li>
            <li>API key management for programmatic access</li>
          </ul>
        </div>

        <div class="changelog-entry">
          <div class="changelog-header">
            <span class="changelog-version">v1.0.0</span>
            <span class="changelog-date">2024-10</span>
          </div>
          <ul class="changelog-items">
            <li>Initial release: single Proxmox host VM deployment via cloud-init</li>
            <li>User authentication with JWT tokens</li>
            <li>Basic VM start/stop/restart controls</li>
            <li>One-line installer for Ubuntu/Debian</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/store/auth'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'Support',
  setup() {
    const authStore = useAuthStore()
    const toast = useToast()

    const isAdmin = computed(() => authStore.isAdmin)
    const version = ref('1.7.0')

    // Health check
    const healthStatus = ref(null)
    const healthLoading = ref(false)

    // DB check
    const dbCheckResult = ref(null)
    const dbCheckLoading = ref(false)

    // Diagnostics bundle
    const diagData = ref(null)
    const diagLoading = ref(false)

    const fetchVersion = async () => {
      try {
        const resp = await api.system.getInfo()
        if (resp.data?.version) version.value = resp.data.version
      } catch (_) {}
    }

    const checkHealth = async () => {
      healthLoading.value = true
      try {
        const resp = await api.system.health()
        healthStatus.value = resp.data
      } catch (e) {
        healthStatus.value = { status: 'error', db: 'error' }
        toast.error('Health check failed')
      } finally {
        healthLoading.value = false
      }
    }

    const runDbCheck = async () => {
      dbCheckLoading.value = true
      try {
        const resp = await api.system.dbCheck()
        dbCheckResult.value = resp.data
        if (resp.data.ok) {
          toast.success('Database integrity: OK')
        } else {
          toast.warning('Database integrity check found issues')
        }
      } catch (e) {
        toast.error('DB check failed')
      } finally {
        dbCheckLoading.value = false
      }
    }

    const downloadDiagnostics = async () => {
      diagLoading.value = true
      try {
        const resp = await api.system.getDiagnostics()
        diagData.value = resp.data
        const blob = new Blob([JSON.stringify(resp.data, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
        a.download = `depl0y-diagnostics-${ts}.json`
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
        toast.success('Diagnostic bundle downloaded')
      } catch (e) {
        toast.error('Failed to collect diagnostics')
      } finally {
        diagLoading.value = false
      }
    }

    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      if (bytes < 1024) return `${bytes} B`
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    const formatUptime = (seconds) => {
      if (!seconds) return '—'
      const d = Math.floor(seconds / 86400)
      const h = Math.floor((seconds % 86400) / 3600)
      const m = Math.floor((seconds % 3600) / 60)
      if (d > 0) return `${d}d ${h}h ${m}m`
      if (h > 0) return `${h}h ${m}m`
      return `${m}m`
    }

    onMounted(() => {
      fetchVersion()
    })

    return {
      isAdmin,
      version,
      healthStatus,
      healthLoading,
      dbCheckResult,
      dbCheckLoading,
      diagData,
      diagLoading,
      checkHealth,
      runDbCheck,
      downloadDiagnostics,
      formatBytes,
      formatUptime,
    }
  }
}
</script>

<style scoped>
.support-page {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  max-width: 1100px;
  margin: 0 auto;
}

.breadcrumb {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.page-header h1 {
  font-size: 2rem;
  margin: 0 0 0.25rem 0;
  color: var(--text-primary);
}

/* Project Info Card */
.project-info-card {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 1.5rem 2rem;
  flex-wrap: wrap;
}

.project-logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.logo-text {
  font-size: 2rem;
  font-weight: 900;
  color: var(--primary-color);
  letter-spacing: -0.05em;
}

.version-badge {
  background: var(--primary-color);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 1rem;
}

.project-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.detail-row {
  display: flex;
  gap: 1rem;
  font-size: 0.875rem;
  align-items: baseline;
}

.detail-label {
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 90px;
  flex-shrink: 0;
}

.detail-value {
  color: var(--text-primary);
}

.detail-link {
  color: var(--primary-color);
  text-decoration: none;
}

.detail-link:hover {
  text-decoration: underline;
}

.project-actions {
  display: flex;
  gap: 0.75rem;
  flex-shrink: 0;
}

/* Support grid */
.support-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
}

.support-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1.75rem;
  background: var(--card-bg, white);
  border-radius: 0.75rem;
  border: 2px solid var(--border-color);
  box-shadow: var(--shadow-md);
  text-decoration: none;
  color: var(--text-primary);
  transition: all 0.2s;
}

.support-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.15);
  transform: translateY(-2px);
}

.sponsor-card:hover {
  border-color: #ec4899;
  box-shadow: 0 8px 24px rgba(236, 72, 153, 0.15);
}

.card-icon {
  font-size: 2.25rem;
  line-height: 1;
}

.support-card h3 {
  margin: 0;
  font-size: 1.15rem;
}

.support-card p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
  line-height: 1.55;
  flex: 1;
}

.card-link {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--primary-color);
}

.sponsor-link {
  color: #ec4899;
}

/* Contribute */
.contribute-card,
.changelog-card,
.diagnostics-card {
  padding: 1.75rem 2rem;
}

.contribute-card h3,
.changelog-card h3,
.diagnostics-card h3 {
  margin: 0 0 1.5rem 0;
  font-size: 1.15rem;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.admin-badge {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  background: #fef3c7;
  color: #92400e;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  letter-spacing: 0.04em;
}

.contribute-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.5rem;
}

.contribute-item {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.contribute-icon {
  font-size: 1.75rem;
  line-height: 1;
  flex-shrink: 0;
}

.contribute-item h4 {
  margin: 0 0 0.25rem 0;
  font-size: 1rem;
  color: var(--text-primary);
}

.contribute-item p {
  margin: 0 0 0.75rem 0;
}

/* Diagnostics */
.diag-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1.25rem;
}

.diag-panel {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.diag-panel-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.25rem;
}

.diag-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--text-primary);
  flex: 1;
}

.health-badge {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  letter-spacing: 0.04em;
}

.health-ok {
  background: rgba(34, 197, 94, 0.15);
  color: var(--secondary-color, #22c55e);
}

.health-warn {
  background: rgba(239, 68, 68, 0.12);
  color: var(--danger-color, #ef4444);
}

.health-details {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin: 0.25rem 0;
}

.health-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.health-ok-text {
  color: var(--secondary-color, #22c55e);
  font-weight: 600;
}

.health-err-text {
  color: var(--danger-color, #ef4444);
  font-weight: 600;
}

.db-results {
  margin: 0.25rem 0;
  max-height: 80px;
  overflow-y: auto;
}

.db-result-line {
  font-size: 0.78rem;
  font-family: monospace;
  color: var(--text-secondary);
  padding: 0.1rem 0;
}

.diag-summary {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  margin: 0.25rem 0;
}

.diag-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.diag-row span:last-child {
  font-weight: 600;
  color: var(--text-primary);
}

.mt-1 {
  margin-top: 0.5rem;
}

/* Changelog */
.changelog-list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.changelog-entry {
  border-left: 3px solid var(--border-color);
  padding-left: 1.25rem;
}

.changelog-entry:first-child {
  border-left-color: var(--primary-color);
}

.changelog-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.changelog-version {
  font-weight: 700;
  font-size: 1rem;
  color: var(--text-primary);
}

.changelog-date {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.changelog-badge {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  letter-spacing: 0.04em;
}

.badge-primary {
  background: #e0e7ff;
  color: #4338ca;
}

.changelog-items {
  list-style: disc;
  margin: 0;
  padding-left: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.changelog-items li {
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* Utility */
.text-muted {
  color: var(--text-secondary);
}

.text-sm {
  font-size: 0.875rem;
}

code {
  background: var(--background, #f9fafb);
  border: 1px solid var(--border-color);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
  font-size: 0.85em;
  font-family: monospace;
}

@media (max-width: 768px) {
  .project-info-card {
    flex-direction: column;
    align-items: flex-start;
  }

  .support-grid {
    grid-template-columns: 1fr;
  }

  .contribute-grid {
    grid-template-columns: 1fr;
  }

  .diag-grid {
    grid-template-columns: 1fr;
  }
}
</style>
