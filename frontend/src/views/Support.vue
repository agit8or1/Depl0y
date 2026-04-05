<template>
  <div class="support-page">

    <!-- Page header -->
    <div class="page-header">
      <h1 class="page-title">Support</h1>
      <p class="page-subtitle">Resources, diagnostics, and community links for Depl0y v{{ version }}</p>
    </div>

    <!-- Quick Help Cards -->
    <div class="quick-help-grid">
      <a
        v-for="card in quickHelpCards"
        :key="card.title"
        :href="card.href"
        target="_blank"
        rel="noopener noreferrer"
        class="quick-card"
        :style="{ '--card-accent': card.accent }"
      >
        <div class="quick-card-icon" v-html="card.icon"></div>
        <div class="quick-card-body">
          <div class="quick-card-title">{{ card.title }}</div>
          <div class="quick-card-desc">{{ card.desc }}</div>
        </div>
        <svg class="quick-card-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
      </a>
    </div>

    <!-- Diagnostic Info (admin only) -->
    <div v-if="isAdmin" class="card diag-card">
      <div class="card-header-row">
        <div class="card-header-left">
          <h3>Diagnostic Information</h3>
          <span class="admin-pill">Admin only</span>
        </div>
        <div class="card-header-actions">
          <button class="btn-outline-sm" @click="fetchDiagnostics" :disabled="diagLoading">
            {{ diagLoading ? 'Loading...' : 'Refresh' }}
          </button>
          <button class="btn-primary-sm" @click="copyDiagnostics" :disabled="!diagData || copyingDiag">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            {{ copyingDiag ? 'Copied!' : 'Copy Diagnostics' }}
          </button>
        </div>
      </div>
      <p class="card-desc">Collect system information formatted for bug reports. Includes version, DB stats, uptime and recent logs.</p>

      <div v-if="diagLoading && !diagData" class="diag-loading">
        <div class="loading-spinner-sm"></div>
        Collecting diagnostics...
      </div>

      <div v-else-if="diagData" class="diag-body">
        <div class="diag-meta-grid">
          <div class="diag-meta-item">
            <span class="diag-meta-label">Version</span>
            <span class="diag-meta-value">{{ diagData.version }}</span>
          </div>
          <div class="diag-meta-item">
            <span class="diag-meta-label">DB Size</span>
            <span class="diag-meta-value">{{ formatBytes(diagData.db_size_bytes) }}</span>
          </div>
          <div class="diag-meta-item">
            <span class="diag-meta-label">Users</span>
            <span class="diag-meta-value">{{ diagData.user_count }}</span>
          </div>
          <div class="diag-meta-item">
            <span class="diag-meta-label">Hosts</span>
            <span class="diag-meta-value">{{ diagData.host_count }}</span>
          </div>
          <div class="diag-meta-item">
            <span class="diag-meta-label">VMs (managed)</span>
            <span class="diag-meta-value">{{ diagData.vm_count }}</span>
          </div>
          <div class="diag-meta-item">
            <span class="diag-meta-label">Uptime</span>
            <span class="diag-meta-value">{{ formatUptime(diagData.uptime_seconds) }}</span>
          </div>
        </div>

        <div class="diag-logs-section">
          <div class="diag-logs-header" @click="showLogs = !showLogs">
            <span class="diag-logs-title">Recent Logs ({{ diagData.last_100_log_lines?.length || 0 }} lines)</span>
            <svg :class="['chevron', showLogs ? 'chevron-open' : '']" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
          </div>
          <transition name="collapse">
            <div v-if="showLogs && diagData.last_100_log_lines" class="diag-logs-body">
              <pre class="diag-logs-pre">{{ diagData.last_100_log_lines.join('\n') }}</pre>
            </div>
          </transition>
        </div>
      </div>

      <div v-else class="diag-empty">
        <p>Click <strong>Refresh</strong> to load diagnostic information.</p>
      </div>

      <!-- Health checks summary -->
      <div v-if="healthData" class="health-summary">
        <div class="health-summary-title">Service Health</div>
        <div class="health-checks-row">
          <div
            v-for="(val, key) in healthData.checks"
            :key="key"
            :class="['health-chip', getHealthClass(key, val)]"
          >
            <span class="health-chip-key">{{ key }}</span>
            <span class="health-chip-val">{{ val }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- FAQ Accordion -->
    <div class="card faq-card">
      <h3 class="section-title-bar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        Frequently Asked Questions
      </h3>
      <div class="faq-list">
        <div
          v-for="faq in faqs"
          :key="faq.q"
          class="faq-item"
          :class="{ 'faq-open': openFaqs.has(faq.q) }"
        >
          <div class="faq-question" @click="toggleFaq(faq.q)">
            <span>{{ faq.q }}</span>
            <svg :class="['chevron', openFaqs.has(faq.q) ? 'chevron-open' : '']" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
          </div>
          <transition name="collapse">
            <div v-if="openFaqs.has(faq.q)" class="faq-answer" v-html="faq.a"></div>
          </transition>
        </div>
      </div>
    </div>

    <!-- Community Links -->
    <div class="card community-card">
      <h3 class="section-title-bar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        Community
      </h3>
      <div class="community-grid">
        <a
          v-for="link in communityLinks"
          :key="link.label"
          :href="link.href"
          target="_blank"
          rel="noopener noreferrer"
          class="community-link-card"
        >
          <div class="community-link-icon" v-html="link.icon"></div>
          <div>
            <div class="community-link-label">{{ link.label }}</div>
            <div class="community-link-desc">{{ link.desc }}</div>
          </div>
        </a>
      </div>
    </div>

    <!-- Submit Feedback -->
    <div class="card feedback-card">
      <h3 class="section-title-bar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        Submit Feedback
      </h3>
      <p class="feedback-intro">
        Fill in the form below and we'll open a pre-filled GitHub issue in a new tab.
        You'll still need to review and submit it on GitHub.
      </p>
      <form class="feedback-form" @submit.prevent="submitFeedback">
        <div class="feedback-row">
          <div class="form-field">
            <label class="form-label">Type</label>
            <div class="feedback-type-btns">
              <button
                v-for="t in feedbackTypes"
                :key="t.value"
                type="button"
                :class="['type-btn', feedbackForm.type === t.value ? 'type-btn-active' : '']"
                @click="feedbackForm.type = t.value"
              >{{ t.label }}</button>
            </div>
          </div>
        </div>
        <div class="form-field">
          <label class="form-label">Title <span class="req">*</span></label>
          <input
            v-model="feedbackForm.title"
            class="form-input"
            placeholder="Brief summary of your feedback"
            maxlength="120"
            required
          />
        </div>
        <div class="form-field">
          <label class="form-label">Description <span class="req">*</span></label>
          <textarea
            v-model="feedbackForm.body"
            class="form-textarea"
            rows="5"
            placeholder="Describe the issue or feature request in detail. For bugs, include steps to reproduce, expected vs actual behavior, and your environment."
            required
          ></textarea>
        </div>
        <div class="form-field">
          <label class="form-label">Depl0y Version</label>
          <input v-model="feedbackForm.versionTag" class="form-input" readonly />
        </div>
        <div v-if="feedbackError" class="feedback-error">{{ feedbackError }}</div>
        <div class="feedback-actions">
          <button type="submit" class="btn-submit-feedback">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
            Open as GitHub Issue
          </button>
          <span class="feedback-note">Opens a new tab — you'll review and submit on GitHub.</span>
        </div>
      </form>
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
    const version = ref('1.8.0')

    // ── Quick help cards ────────────────────────────────────────────────────
    const quickHelpCards = [
      {
        title: 'Documentation',
        desc: 'Guides, API reference and setup instructions on the GitHub wiki.',
        href: 'https://github.com/agit8or1/Depl0y/wiki',
        accent: '#3b82f6',
        icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
      },
      {
        title: 'GitHub Issues',
        desc: 'Report bugs or track known issues on the public issue tracker.',
        href: 'https://github.com/agit8or1/Depl0y/issues',
        accent: '#ef4444',
        icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
      },
      {
        title: 'Discussions',
        desc: 'Ask questions and share ideas in the GitHub Discussions forum.',
        href: 'https://github.com/agit8or1/Depl0y/discussions',
        accent: '#10b981',
        icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
      },
      {
        title: 'Changelog',
        desc: 'See what\'s new in every release — features, fixes and improvements.',
        href: 'https://github.com/agit8or1/Depl0y/releases',
        accent: '#8b5cf6',
        icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
      },
      {
        title: 'Sponsor',
        desc: 'Support continued development via GitHub Sponsors. Every contribution helps.',
        href: 'https://github.com/sponsors/agit8or1',
        accent: '#ec4899',
        icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>',
      },
      {
        title: 'Star on GitHub',
        desc: 'Give Depl0y a star — it helps others discover the project.',
        href: 'https://github.com/agit8or1/Depl0y',
        accent: '#f59e0b',
        icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>',
      },
    ]

    // ── Diagnostics ─────────────────────────────────────────────────────────
    const diagData = ref(null)
    const diagLoading = ref(false)
    const copyingDiag = ref(false)
    const showLogs = ref(false)
    const healthData = ref(null)

    const fetchDiagnostics = async () => {
      diagLoading.value = true
      try {
        const [diagRes, healthRes] = await Promise.all([
          api.system.getDiagnostics(),
          api.system.health(),
        ])
        diagData.value = diagRes.data
        healthData.value = healthRes.data
      } catch (e) {
        toast.error('Failed to load diagnostics')
      } finally {
        diagLoading.value = false
      }
    }

    const copyDiagnostics = async () => {
      if (!diagData.value) return
      const report = [
        `## Depl0y Diagnostic Report`,
        `Generated: ${new Date().toISOString()}`,
        ``,
        `**Version:** ${diagData.value.version}`,
        `**App:** ${diagData.value.app_name}`,
        `**DB Path:** ${diagData.value.db_path}`,
        `**DB Size:** ${formatBytes(diagData.value.db_size_bytes)}`,
        `**Users:** ${diagData.value.user_count}`,
        `**Hosts:** ${diagData.value.host_count}`,
        `**VMs (managed):** ${diagData.value.vm_count}`,
        `**Uptime:** ${formatUptime(diagData.value.uptime_seconds)}`,
        ``,
        `### Service Health`,
        ...(healthData.value ? Object.entries(healthData.value.checks).map(([k, v]) => `- ${k}: ${v}`) : []),
        ``,
        `### Last 100 Log Lines`,
        '```',
        ...(diagData.value.last_100_log_lines?.slice(-50) || []),
        '```',
      ].join('\n')

      try {
        await navigator.clipboard.writeText(report)
        copyingDiag.value = true
        toast.success('Diagnostics copied to clipboard')
        setTimeout(() => { copyingDiag.value = false }, 2500)
      } catch {
        toast.error('Could not copy to clipboard')
      }
    }

    const getHealthClass = (key, val) => {
      if (key === 'db') return val === 'ok' ? 'chip-ok' : 'chip-err'
      if (key === 'smtp') return val === 'configured' ? 'chip-ok' : 'chip-warn'
      if (key === 'encryption') return val === 'ok' ? 'chip-ok' : 'chip-err'
      if (key === 'hosts') return Number(val) > 0 ? 'chip-ok' : 'chip-warn'
      if (key === 'disk_free_gb') return Number(val) > 1 ? 'chip-ok' : 'chip-warn'
      return 'chip-neutral'
    }

    // ── FAQ ─────────────────────────────────────────────────────────────────
    const openFaqs = ref(new Set())
    const toggleFaq = (q) => {
      const s = new Set(openFaqs.value)
      if (s.has(q)) s.delete(q)
      else s.add(q)
      openFaqs.value = s
    }

    const faqs = [
      {
        q: 'How do I add a Proxmox host?',
        a: 'Go to <strong>Proxmox Hosts</strong> in the sidebar and click <strong>Add Host</strong>. Enter the Proxmox hostname/IP, API port (default 8006), and either a username/password or an API token. Depl0y stores credentials encrypted using AES-256.',
      },
      {
        q: 'What Proxmox VE versions are supported?',
        a: 'Depl0y is tested against <strong>Proxmox VE 7.x and 8.x</strong>. Most features work with any version that implements the standard Proxmox REST API. Some newer features (SDN, Proxmox Backup Server v3) require PVE 8.',
      },
      {
        q: 'Why do cloud image deployments take 5–10 minutes the first time?',
        a: 'The first deployment per cloud image must download the image (~500 MB–2 GB), convert it to qcow2 format, and create a reusable template. All subsequent VMs based on the same image are instant clones (~30 seconds).',
      },
      {
        q: 'How do I enable Two-Factor Authentication?',
        a: 'Go to <strong>Settings → User Profile</strong> and click <strong>Enable 2FA</strong>. Scan the QR code with any TOTP app (Google Authenticator, Authy, Bitwarden), verify the 6-digit code, and 2FA is active on your next login.',
      },
      {
        q: 'Can I manage multiple independent Proxmox clusters?',
        a: 'Yes. Add each cluster\'s primary node as a separate Proxmox Host. Depl0y will automatically discover nodes within each cluster. You can have as many registered hosts as needed and switch between them in the sidebar.',
      },
      {
        q: 'How do I reset a forgotten admin password?',
        a: 'Connect to the server running Depl0y and run:<br><code>cd /opt/depl0y &amp;&amp; python3 -m app.scripts.reset_password --username admin --password NewPassword123</code><br>Then restart the service: <code>systemctl restart depl0y-backend</code>',
      },
      {
        q: 'What does the ENCRYPTION_KEY do?',
        a: 'Depl0y uses a Fernet (AES-128-CBC + HMAC-SHA256) encryption key to encrypt Proxmox API credentials stored in the database. If you lose this key, stored credentials cannot be decrypted. Back up <code>/etc/depl0y/config.env</code>.',
      },
      {
        q: 'How do I update Depl0y?',
        a: 'Go to <strong>Settings → System Updates</strong> and click <strong>Check for Updates</strong>. If an update is available, click <strong>Install Update</strong>. Depl0y will pull the latest code from GitHub and restart automatically. You can also update manually via git pull on the server.',
      },
      {
        q: 'Where are the backend logs?',
        a: 'Live logs are viewable in <strong>Settings → Backend Logs</strong>. On the server, logs are written to the path configured in <code>LOG_FILE</code> (see <code>/etc/depl0y/config.env</code>). You can also run <code>journalctl -u depl0y-backend -f</code> for real-time systemd output.',
      },
      {
        q: 'How do I report a security vulnerability?',
        a: 'Please <strong>do not</strong> open a public GitHub issue for security vulnerabilities. Instead, send an email to the maintainer via the contact form on <a href="https://mspreboot.com" target="_blank" rel="noopener noreferrer">mspreboot.com</a> with the subject line "Depl0y Security Vulnerability".',
      },
    ]

    // ── Community links ──────────────────────────────────────────────────────
    const communityLinks = [
      {
        label: 'GitHub Repository',
        desc: 'Source code, issues and pull requests',
        href: 'https://github.com/agit8or1/Depl0y',
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>',
      },
      {
        label: 'GitHub Discussions',
        desc: 'Community forum — questions and ideas',
        href: 'https://github.com/agit8or1/Depl0y/discussions',
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
      },
      {
        label: 'GitHub Issues',
        desc: 'Bug reports and feature requests',
        href: 'https://github.com/agit8or1/Depl0y/issues',
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
      },
      {
        label: 'Releases & Changelog',
        desc: 'Release notes for every version',
        href: 'https://github.com/agit8or1/Depl0y/releases',
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
      },
      {
        label: 'GitHub Sponsors',
        desc: 'Support the project financially',
        href: 'https://github.com/sponsors/agit8or1',
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>',
      },
      {
        label: 'mspreboot.com',
        desc: 'More projects and resources from the team',
        href: 'https://mspreboot.com',
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
      },
    ]

    // ── Feedback form ────────────────────────────────────────────────────────
    const feedbackTypes = [
      { value: 'bug', label: 'Bug Report' },
      { value: 'feature', label: 'Feature Request' },
      { value: 'question', label: 'Question' },
    ]

    const feedbackForm = ref({
      type: 'bug',
      title: '',
      body: '',
      versionTag: `v${version.value}`,
    })

    const feedbackError = ref(null)

    const submitFeedback = () => {
      feedbackError.value = null
      if (!feedbackForm.value.title.trim()) {
        feedbackError.value = 'Please enter a title.'
        return
      }
      if (!feedbackForm.value.body.trim()) {
        feedbackError.value = 'Please enter a description.'
        return
      }

      const typeLabels = { bug: 'bug', feature: 'enhancement', question: 'question' }
      const ghLabel = typeLabels[feedbackForm.value.type] || 'bug'

      const titleEnc = encodeURIComponent(`[${feedbackForm.value.type.toUpperCase()}] ${feedbackForm.value.title}`)

      const bodyText = [
        feedbackForm.value.body,
        '',
        '---',
        `**Depl0y Version:** ${feedbackForm.value.versionTag}`,
        `**Type:** ${feedbackForm.value.type}`,
      ].join('\n')
      const bodyEnc = encodeURIComponent(bodyText)

      const url = `https://github.com/agit8or1/Depl0y/issues/new?title=${titleEnc}&body=${bodyEnc}&labels=${ghLabel}`
      window.open(url, '_blank', 'noopener,noreferrer')
      toast.success('GitHub issue opened in new tab')
    }

    // ── Helpers ──────────────────────────────────────────────────────────────
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

    onMounted(async () => {
      try {
        const res = await api.system.getInfo()
        if (res.data?.version) {
          version.value = res.data.version
          feedbackForm.value.versionTag = `v${res.data.version}`
        }
      } catch { /* ignore */ }

      if (isAdmin.value) {
        fetchDiagnostics()
      }
    })

    return {
      isAdmin,
      version,
      quickHelpCards,
      diagData,
      diagLoading,
      copyingDiag,
      showLogs,
      healthData,
      fetchDiagnostics,
      copyDiagnostics,
      getHealthClass,
      openFaqs,
      toggleFaq,
      faqs,
      communityLinks,
      feedbackTypes,
      feedbackForm,
      feedbackError,
      submitFeedback,
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
  gap: 1.5rem;
  max-width: 960px;
  margin: 0 auto;
}

/* ── Page header ── */
.page-header {
  padding: 0.25rem 0 0.5rem;
}

.page-title {
  font-size: 1.75rem;
  font-weight: 800;
  margin: 0 0 0.35rem;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 0.925rem;
  color: var(--text-muted);
  margin: 0;
}

/* ── Quick help grid ── */
.quick-help-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.875rem;
}

.quick-card {
  display: flex;
  align-items: flex-start;
  gap: 0.875rem;
  padding: 1rem 1.125rem;
  background: var(--card-bg, var(--surface));
  border: 1px solid var(--border-color);
  border-radius: 0.625rem;
  text-decoration: none;
  color: var(--text-primary);
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.12s;
  box-shadow: var(--shadow-sm);
  position: relative;
}

.quick-card:hover {
  border-color: var(--card-accent);
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  transform: translateY(-1px);
}

.quick-card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 0.5rem;
  background: color-mix(in srgb, var(--card-accent) 12%, transparent);
  color: var(--card-accent);
  flex-shrink: 0;
}

.quick-card-body {
  flex: 1;
  min-width: 0;
}

.quick-card-title {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.2rem;
}

.quick-card-desc {
  font-size: 0.775rem;
  color: var(--text-muted);
  line-height: 1.45;
}

.quick-card-arrow {
  color: var(--text-muted);
  opacity: 0.5;
  flex-shrink: 0;
  margin-top: 0.1rem;
  transition: opacity 0.15s, transform 0.15s;
}

.quick-card:hover .quick-card-arrow {
  opacity: 1;
  transform: translate(1px, -1px);
  color: var(--card-accent);
}

/* ── Card shared ── */
.card {
  background: var(--card-bg, var(--surface));
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  box-shadow: var(--shadow-sm);
}

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.5rem 0;
  flex-wrap: wrap;
}

.card-header-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.card-header-left h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
}

.card-header-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.card-desc {
  padding: 0.5rem 1.5rem 0;
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0;
}

.section-title-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  font-size: 0.975rem;
  font-weight: 700;
  color: var(--text-primary);
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

/* ── Buttons ── */
.btn-outline-sm {
  padding: 0.35rem 0.875rem;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.15s;
}
.btn-outline-sm:hover { border-color: var(--primary-color); color: var(--primary-color); }
.btn-outline-sm:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary-sm {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.875rem;
  background: var(--primary-color);
  border: none;
  border-radius: 0.375rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #fff;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-primary-sm:hover { opacity: 0.85; }
.btn-primary-sm:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Admin pill ── */
.admin-pill {
  font-size: 0.62rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background: rgba(245,158,11,0.15);
  color: #d97706;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
}

/* ── Diagnostics card ── */
.diag-card {
  padding-bottom: 1.25rem;
}

.diag-loading {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.75rem 1.5rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.loading-spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.diag-body {
  padding: 0.75rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.diag-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.625rem;
}

.diag-meta-item {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.625rem 0.875rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
}

.diag-meta-label {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
}

.diag-meta-value {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.diag-logs-section {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
}

.diag-logs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.625rem 0.875rem;
  background: var(--background);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.diag-logs-header:hover { background: var(--border-color); }

.diag-logs-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.diag-logs-body {
  border-top: 1px solid var(--border-color);
  max-height: 300px;
  overflow-y: auto;
}

.diag-logs-pre {
  margin: 0;
  padding: 0.75rem 0.875rem;
  font-size: 0.72rem;
  font-family: monospace;
  color: var(--text-secondary);
  white-space: pre;
  word-break: break-all;
  line-height: 1.5;
}

.diag-empty {
  padding: 1rem 1.5rem;
  font-size: 0.875rem;
  color: var(--text-muted);
}

/* ── Health summary ── */
.health-summary {
  padding: 0 1.5rem;
  margin-top: 0.25rem;
}

.health-summary-title {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}

.health-checks-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.health-chip {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
  padding: 0.35rem 0.75rem;
  border-radius: 0.375rem;
  border: 1px solid;
}

.health-chip-key {
  font-size: 0.62rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.8;
}

.health-chip-val {
  font-size: 0.78rem;
  font-weight: 600;
}

.chip-ok {
  background: rgba(16,185,129,0.08);
  border-color: rgba(16,185,129,0.3);
  color: #059669;
}
[data-theme="dark"] .chip-ok { color: #6ee7b7; }

.chip-err {
  background: rgba(239,68,68,0.08);
  border-color: rgba(239,68,68,0.3);
  color: #dc2626;
}
[data-theme="dark"] .chip-err { color: #fca5a5; }

.chip-warn {
  background: rgba(245,158,11,0.08);
  border-color: rgba(245,158,11,0.3);
  color: #d97706;
}
[data-theme="dark"] .chip-warn { color: #fcd34d; }

.chip-neutral {
  background: var(--background);
  border-color: var(--border-color);
  color: var(--text-secondary);
}

/* ── FAQ ── */
.faq-card {
  overflow: hidden;
}

.faq-list {
  display: flex;
  flex-direction: column;
}

.faq-item {
  border-bottom: 1px solid var(--border-color);
}
.faq-item:last-child { border-bottom: none; }

.faq-question {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.875rem 1.5rem;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  user-select: none;
  transition: background 0.12s;
}
.faq-question:hover { background: var(--background); }

.faq-answer {
  padding: 0 1.5rem 1rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.65;
  border-top: 1px solid var(--border-color);
  padding-top: 0.875rem;
}

.faq-answer code {
  background: var(--background);
  border: 1px solid var(--border-color);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
  font-size: 0.85em;
  font-family: monospace;
}

.faq-answer a {
  color: var(--primary-color);
  text-decoration: none;
}
.faq-answer a:hover { text-decoration: underline; }

/* ── Community links ── */
.community-card {
  overflow: hidden;
}

.community-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
}

.community-link-card {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  padding: 1rem 1.25rem;
  text-decoration: none;
  color: var(--text-primary);
  border-right: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
  transition: background 0.12s;
}

.community-link-card:nth-child(3n) { border-right: none; }
.community-link-card:nth-last-child(-n+3) { border-bottom: none; }
.community-link-card:hover { background: var(--background); }

.community-link-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 0.5rem;
  background: var(--background);
  color: var(--primary-color);
  border: 1px solid var(--border-color);
  flex-shrink: 0;
}

.community-link-label {
  font-size: 0.875rem;
  font-weight: 600;
  margin-bottom: 0.1rem;
}

.community-link-desc {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* ── Feedback form ── */
.feedback-card {
  overflow: hidden;
}

.feedback-intro {
  padding: 0.5rem 1.5rem 0;
  font-size: 0.875rem;
  color: var(--text-muted);
  margin: 0;
}

.feedback-form {
  padding: 1rem 1.5rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.feedback-row {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  flex: 1;
  min-width: 0;
}

.form-label {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.req { color: #ef4444; }

.feedback-type-btns {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.type-btn {
  padding: 0.4rem 1rem;
  border: 1px solid var(--border-color);
  background: var(--background);
  border-radius: 0.375rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.type-btn:hover { border-color: var(--primary-color); color: var(--primary-color); }

.type-btn-active {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #fff;
}

.form-input {
  width: 100%;
  padding: 0.55rem 0.875rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  font-size: 0.9rem;
  color: var(--text-primary);
  box-sizing: border-box;
  transition: border-color 0.15s;
  outline: none;
}

.form-input:focus { border-color: var(--primary-color); }
.form-input[readonly] { opacity: 0.6; cursor: default; }

.form-textarea {
  width: 100%;
  padding: 0.6rem 0.875rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-primary);
  box-sizing: border-box;
  resize: vertical;
  font-family: inherit;
  line-height: 1.55;
  transition: border-color 0.15s;
  outline: none;
}

.form-textarea:focus { border-color: var(--primary-color); }

.feedback-error {
  font-size: 0.85rem;
  color: #ef4444;
  padding: 0.5rem 0.75rem;
  background: rgba(239,68,68,0.07);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: 0.375rem;
}

.feedback-actions {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  flex-wrap: wrap;
}

.btn-submit-feedback {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.55rem 1.25rem;
  background: #1f2937;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 700;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
[data-theme="dark"] .btn-submit-feedback { background: #374151; }
.btn-submit-feedback:hover { background: #111827; }
[data-theme="dark"] .btn-submit-feedback:hover { background: #4b5563; }

.feedback-note {
  font-size: 0.775rem;
  color: var(--text-muted);
}

/* ── Collapse transition ── */
.chevron {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.chevron-open {
  transform: rotate(180deg);
}

.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.22s ease;
  overflow: hidden;
}
.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}
.collapse-enter-to,
.collapse-leave-from {
  opacity: 1;
  max-height: 2000px;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .quick-help-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .diag-meta-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .community-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .community-link-card:nth-child(3n) { border-right: 1px solid var(--border-color); }
  .community-link-card:nth-child(2n) { border-right: none; }
  .community-link-card:nth-last-child(-n+3) { border-bottom: 1px solid var(--border-color); }
  .community-link-card:nth-last-child(-n+2) { border-bottom: none; }
}

@media (max-width: 540px) {
  .quick-help-grid {
    grid-template-columns: 1fr;
  }

  .community-grid {
    grid-template-columns: 1fr;
  }

  .community-link-card {
    border-right: none !important;
    border-bottom: 1px solid var(--border-color) !important;
  }
  .community-link-card:last-child { border-bottom: none !important; }

  .card-header-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
