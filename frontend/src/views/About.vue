<template>
  <div class="about-page">

    <!-- Hero Section -->
    <div class="hero-card card">
      <div class="hero-gradient-bg"></div>
      <div class="hero-content">
        <div class="logo-wrap">
          <h1 class="about-logo">Depl<span class="logo-zero">0</span>y</h1>
          <p class="tagline">Open-source Proxmox VE Management Platform</p>
          <div class="badges">
            <span class="badge badge-success">
              <span class="status-dot"></span>
              Running
            </span>
            <span class="version-badge" v-if="version !== '...'">v{{ version }}</span>
            <span class="version-badge loading-badge" v-else>Loading...</span>
            <span class="build-badge">{{ buildDate }}</span>
          </div>
        </div>

        <div class="hero-actions">
          <a
            href="https://github.com/agit8or1/Depl0y"
            target="_blank"
            rel="noopener noreferrer"
            class="hero-btn hero-btn-primary"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
            GitHub
          </a>
          <a
            href="https://github.com/agit8or1/Depl0y/wiki"
            target="_blank"
            rel="noopener noreferrer"
            class="hero-btn hero-btn-outline"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            Documentation
          </a>
          <a
            href="https://github.com/agit8or1/Depl0y/issues"
            target="_blank"
            rel="noopener noreferrer"
            class="hero-btn hero-btn-outline"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            Issues
          </a>
          <a
            href="https://github.com/sponsors/agit8or1"
            target="_blank"
            rel="noopener noreferrer"
            class="hero-btn hero-btn-sponsor"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
            Sponsor
          </a>
        </div>

        <div class="system-info-grid">
          <div class="info-item">
            <span class="info-label">Backend</span>
            <span class="info-value">FastAPI (Python)</span>
          </div>
          <div class="info-item">
            <span class="info-label">Frontend</span>
            <span class="info-value">Vue 3 + Vite</span>
          </div>
          <div class="info-item">
            <span class="info-label">Database</span>
            <span class="info-value">SQLite</span>
          </div>
          <div class="info-item">
            <span class="info-label">License</span>
            <span class="info-value">Open Source</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Feature Highlights Grid -->
    <div class="section-card card">
      <h3 class="section-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        Feature Highlights
      </h3>
      <div class="features-grid">
        <div class="feature-card" v-for="feature in featureHighlights" :key="feature.title">
          <div class="feature-icon-wrap" :style="{ background: feature.iconBg }">
            <span class="feature-svg" v-html="feature.icon"></span>
          </div>
          <div class="feature-body">
            <div class="feature-title">{{ feature.title }}</div>
            <div class="feature-desc">{{ feature.desc }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Technology Stack -->
    <div class="section-card card">
      <h3 class="section-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        Technology Stack
      </h3>
      <div class="stack-grid">
        <div v-for="group in techStack" :key="group.label" class="stack-group">
          <div class="stack-group-label">{{ group.label }}</div>
          <div class="stack-items">
            <span v-for="tech in group.items" :key="tech" class="stack-badge">{{ tech }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Changelog -->
    <div class="section-card card">
      <h3 class="section-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        Changelog
      </h3>
      <div class="changelog-versions">
        <div
          v-for="release in changelog"
          :key="release.version"
          class="changelog-version"
        >
          <div class="version-header" @click="toggleVersion(release.version)">
            <div class="version-left">
              <span class="version-tag" :class="release.version === currentVersion ? 'version-current' : ''">
                {{ release.version }}
              </span>
              <span v-if="release.version === currentVersion" class="current-label">Current</span>
              <span class="version-date">{{ release.date }}</span>
            </div>
            <svg
              class="chevron"
              :class="{ 'chevron-open': openVersions.has(release.version) }"
              width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            ><polyline points="6 9 12 15 18 9"/></svg>
          </div>
          <transition name="collapse">
            <div v-if="openVersions.has(release.version)" class="version-entries">
              <div
                v-for="entry in release.entries"
                :key="entry.text"
                class="changelog-entry"
                :class="`entry-${entry.type}`"
              >
                <span class="entry-type-badge">{{ entry.type }}</span>
                <span class="entry-text">{{ entry.text }}</span>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </div>

    <!-- System Information -->
    <div class="section-card card">
      <h3 class="section-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        System Information
        <button class="refresh-btn" @click="fetchHealthInfo" :disabled="healthLoading">
          <svg v-if="!healthLoading" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          <span v-else class="spin-icon">...</span>
        </button>
      </h3>
      <div v-if="healthLoading && !healthInfo" class="sysinfo-loading">Loading...</div>
      <div v-else-if="healthInfo" class="sysinfo-grid">
        <div class="sysinfo-item">
          <span class="sysinfo-label">Database</span>
          <span :class="['sysinfo-value', healthInfo.checks?.db === 'ok' ? 'val-ok' : 'val-err']">
            {{ healthInfo.checks?.db === 'ok' ? 'Connected' : 'Error' }}
          </span>
        </div>
        <div class="sysinfo-item">
          <span class="sysinfo-label">SMTP</span>
          <span :class="['sysinfo-value', healthInfo.checks?.smtp === 'configured' ? 'val-ok' : 'val-warn']">
            {{ healthInfo.checks?.smtp === 'configured' ? 'Configured' : 'Not configured' }}
          </span>
        </div>
        <div class="sysinfo-item">
          <span class="sysinfo-label">Proxmox Hosts</span>
          <span class="sysinfo-value">{{ healthInfo.checks?.hosts ?? '—' }}</span>
        </div>
        <div class="sysinfo-item">
          <span class="sysinfo-label">Encryption Key</span>
          <span :class="['sysinfo-value', healthInfo.checks?.encryption === 'ok' ? 'val-ok' : 'val-err']">
            {{ healthInfo.checks?.encryption === 'ok' ? 'Set' : 'Missing' }}
          </span>
        </div>
        <div class="sysinfo-item">
          <span class="sysinfo-label">Disk Free</span>
          <span :class="['sysinfo-value', (healthInfo.checks?.disk_free_gb ?? 0) > 1 ? 'val-ok' : 'val-warn']">
            {{ healthInfo.checks?.disk_free_gb != null ? healthInfo.checks.disk_free_gb + ' GB' : '—' }}
          </span>
        </div>
        <div class="sysinfo-item">
          <span class="sysinfo-label">Overall Status</span>
          <span :class="['sysinfo-value', healthInfo.status === 'healthy' ? 'val-ok' : 'val-warn']">
            {{ healthInfo.status }}
          </span>
        </div>
      </div>
      <div v-else class="sysinfo-empty">
        <button class="btn-load-sysinfo" @click="fetchHealthInfo">Load System Info</button>
      </div>
    </div>

    <!-- Check for Updates -->
    <div class="section-card card">
      <h3 class="section-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        Updates
      </h3>
      <div class="updates-section">
        <div class="updates-row">
          <div class="updates-info">
            <span class="updates-current">Current version: <strong>v{{ version }}</strong></span>
            <span v-if="updateStatus === 'up-to-date'" class="update-badge update-ok">Up to date</span>
            <span v-else-if="updateStatus === 'available'" class="update-badge update-avail">Update available!</span>
            <span v-else-if="updateStatus === 'pre-release'" class="update-badge update-pre">Pre-release</span>
            <span v-if="latestVersion && updateStatus !== 'loading'" class="updates-latest">Latest release: <strong>v{{ latestVersion }}</strong></span>
          </div>
          <button class="check-update-btn" @click="checkForUpdates" :disabled="updateChecking">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            {{ updateChecking ? 'Checking...' : 'Check for Updates' }}
          </button>
        </div>
        <div v-if="updateReleaseNotes" class="update-notes">
          <p class="update-notes-label">Release notes:</p>
          <pre class="update-notes-body">{{ updateReleaseNotes }}</pre>
        </div>
        <p v-if="updateError" class="update-error">{{ updateError }}</p>
      </div>
    </div>

    <!-- License -->
    <div class="section-card card">
      <h3 class="section-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        License
      </h3>
      <div class="license-section">
        <div class="license-header">
          <span class="license-badge">MIT License</span>
          <span class="license-year">Copyright &copy; 2024–2026 Agit8or</span>
        </div>
        <p class="license-summary">
          Free and open source software. Permission is granted to use, copy, modify, merge, publish,
          distribute, sublicense, and/or sell copies, subject to the conditions below.
        </p>
        <div class="license-expand-wrap">
          <button class="license-toggle" @click="showLicense = !showLicense">
            {{ showLicense ? 'Hide full license text' : 'Show full license text' }}
            <svg
              :class="['chevron', showLicense ? 'chevron-open' : '']"
              width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            ><polyline points="6 9 12 15 18 9"/></svg>
          </button>
          <transition name="collapse">
            <div v-if="showLicense" class="license-text">
              <pre>MIT License

Copyright (c) 2024-2026 Agit8or

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.</pre>
            </div>
          </transition>
        </div>
      </div>
    </div>

    <!-- Contributors -->
    <div class="section-card card">
      <h3 class="section-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        Contributors
      </h3>
      <div class="contributors-section">
        <div class="contributor-card">
          <div class="contributor-avatar">A</div>
          <div class="contributor-info">
            <a href="https://github.com/agit8or1" target="_blank" rel="noopener noreferrer" class="contributor-name">Agit8or</a>
            <span class="contributor-role">Core maintainer</span>
            <a href="https://mspreboot.com" target="_blank" rel="noopener noreferrer" class="contributor-site">mspreboot.com</a>
          </div>
        </div>
        <div class="contributors-cta">
          <p>Want to contribute? Pull requests are welcome!</p>
          <a href="https://github.com/agit8or1/Depl0y/fork" target="_blank" rel="noopener noreferrer" class="contribute-btn">
            Fork on GitHub
          </a>
        </div>
      </div>
    </div>

    <!-- Credits -->
    <div class="section-card card">
      <h3 class="section-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        Credits &amp; Open Source
      </h3>
      <div class="credits-section">
        <div class="credits-group">
          <div class="credits-group-label">Core Libraries</div>
          <div class="credits-list">
            <a v-for="lib in coreLibs" :key="lib.name"
               :href="lib.url" target="_blank" rel="noopener noreferrer"
               class="credit-item">
              <span class="credit-name">{{ lib.name }}</span>
              <span class="credit-desc">{{ lib.desc }}</span>
            </a>
          </div>
        </div>
        <div class="credits-group">
          <div class="credits-group-label">Built By</div>
          <div class="builder-inner">
            <div class="builder-info">
              <a href="https://mspreboot.com" target="_blank" rel="noopener noreferrer" class="builder-name">
                Agit8or
              </a>
              <span class="builder-url">mspreboot.com</span>
            </div>
            <div class="builder-links">
              <a href="https://github.com/agit8or1/Depl0y" target="_blank" rel="noopener noreferrer" class="builder-link-btn">
                GitHub
              </a>
              <a href="https://github.com/agit8or1/Depl0y/issues" target="_blank" rel="noopener noreferrer" class="builder-link-btn">
                Issues
              </a>
              <a href="https://github.com/sponsors/agit8or1" target="_blank" rel="noopener noreferrer" class="builder-link-btn sponsor-btn">
                Sponsor
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import api from '@/services/api'

const CURRENT_VERSION = '1.8.0'

export default {
  name: 'About',
  setup() {
    const version = ref('...')
    const currentVersion = ref(CURRENT_VERSION)
    const buildDate = ref(new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }))
    const openVersions = ref(new Set([CURRENT_VERSION]))

    const toggleVersion = (v) => {
      if (openVersions.value.has(v)) {
        openVersions.value = new Set([...openVersions.value].filter(x => x !== v))
      } else {
        openVersions.value = new Set([...openVersions.value, v])
      }
    }

    const featureHighlights = [
      {
        title: 'VM & LXC Management',
        desc: 'Full lifecycle management for QEMU VMs and LXC containers across all Proxmox hosts.',
        iconBg: 'rgba(59,130,246,0.12)',
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>'
      },
      {
        title: 'Backup & Restore',
        desc: 'Schedule vzdump backups, connect PBS servers and restore from snapshots.',
        iconBg: 'rgba(16,185,129,0.12)',
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
      },
      {
        title: 'Cluster Monitoring',
        desc: 'Real-time CPU, RAM and storage metrics for every node in your cluster.',
        iconBg: 'rgba(245,158,11,0.12)',
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>'
      },
      {
        title: 'Security & 2FA',
        desc: 'TOTP two-factor auth, IP allowlists, GeoIP rules, and full audit logging.',
        iconBg: 'rgba(239,68,68,0.12)',
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
      },
      {
        title: 'API Integration',
        desc: 'Full REST API with 73+ endpoints, API key management and OpenAPI explorer.',
        iconBg: 'rgba(139,92,246,0.12)',
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>'
      },
      {
        title: 'Multi-Host Support',
        desc: 'Manage multiple independent Proxmox clusters from a single dashboard.',
        iconBg: 'rgba(6,182,212,0.12)',
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
      },
      {
        title: 'Template Library',
        desc: 'Community template catalog plus convert any VM to a reusable template.',
        iconBg: 'rgba(236,72,153,0.12)',
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ec4899" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>'
      },
      {
        title: 'Network Management',
        desc: 'Create and manage bridges, VLANs, bonds and firewall rules per node.',
        iconBg: 'rgba(20,184,166,0.12)',
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" stroke-width="2"><rect x="9" y="2" width="6" height="6"/><rect x="16" y="16" width="6" height="6"/><rect x="2" y="16" width="6" height="6"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="12" x2="5" y2="16"/><line x1="12" y1="12" x2="19" y2="16"/></svg>'
      },
      {
        title: 'Real-time Metrics',
        desc: 'Live RRD graphs for CPU, memory, disk I/O and network throughput.',
        iconBg: 'rgba(249,115,22,0.12)',
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'
      },
    ]

    const techStack = [
      {
        label: 'Backend',
        items: ['Python 3.11+', 'FastAPI', 'SQLAlchemy', 'Proxmoxer', 'Pydantic', 'SQLite', 'Alembic']
      },
      {
        label: 'Frontend',
        items: ['Vue 3', 'Vite', 'Pinia', 'Vue Router', 'Axios', 'vue-toastification']
      },
      {
        label: 'Infrastructure',
        items: ['Proxmox VE', 'Proxmox Backup Server', 'noVNC', 'xterm.js', 'cloud-init']
      },
    ]

    const changelog = [
      {
        version: '1.8.0',
        date: 'April 2026',
        entries: [
          { type: 'new', text: 'VM Groups — logical grouping of VMs across hosts with full CRUD management' },
          { type: 'new', text: 'Snapshot Manager — cross-host snapshot overview with create, rollback and delete' },
          { type: 'new', text: 'Storage Management — cluster-wide storage definition editor with ZFS and Ceph support' },
          { type: 'new', text: 'SDN / VNets — Software-Defined Networking zones, VNets and subnets management' },
          { type: 'new', text: 'Network Management — per-node bridge, VLAN and bond configuration with apply/revert' },
          { type: 'new', text: 'Replication Manager — cross-node and cross-cluster replication job management' },
          { type: 'new', text: 'Node Monitor — cluster-wide per-node resource overview with live metrics' },
          { type: 'new', text: 'API Explorer — interactive OpenAPI endpoint browser with full schema details' },
          { type: 'new', text: 'VM Import — OVA, VMDK and direct VMware/vSphere import with progress tracking' },
          { type: 'new', text: 'Cloud-Init Editor — standalone cloud-init configuration view per VM' },
          { type: 'improved', text: 'Sidebar now includes VM Groups link under Compute section' },
          { type: 'improved', text: 'Version number consistently sourced across all fallback paths (backend + frontend)' },
          { type: 'improved', text: 'Added .badge-outline CSS utility for consistent outlined badge styling' },
          { type: 'improved', text: 'VM Import router registered in backend — /vm-import endpoints now reachable' },
          { type: 'improved', text: 'Router audit: all 40+ views have registered routes with correct auth guards' },
          { type: 'fixed', text: 'package.json version was stale at 1.6.1 — now tracks release version correctly' },
          { type: 'fixed', text: 'system.py fallback version was returning 1.1.3 on DB failure — fixed to 1.8.0' },
        ]
      },
      {
        version: '1.7.0',
        date: 'April 2026',
        entries: [
          { type: 'new', text: 'Full Proxmox VE management — VM, LXC, Node, Cluster, Backup and Access Control' },
          { type: 'new', text: 'VNC Console via noVNC; Node and LXC terminal via xterm.js' },
          { type: 'new', text: 'Global search across all Proxmox hosts' },
          { type: 'new', text: 'Live node stats (CPU, RAM, VM/LXC counts) on Proxmox Hosts page' },
          { type: 'new', text: 'Auto-refresh on Dashboard and VM list' },
          { type: 'new', text: 'Proxmox Integration settings — default host, console preferences, refresh interval' },
          { type: 'new', text: '73 new API endpoints, 20+ new views' },
          { type: 'new', text: 'iDRAC / iLO management for all server types' },
          { type: 'new', text: 'PBS Backup Server management and snapshot restore' },
          { type: 'new', text: 'Cluster-wide replication job management' },
          { type: 'new', text: 'VM import from OVA / VMDK / VMware direct import' },
          { type: 'new', text: 'LLM / AI VM deployments with Ollama model management' },
          { type: 'new', text: 'Linux VM Security Agent with AI-powered tuning' },
          { type: 'new', text: 'High Availability groups and resource management' },
          { type: 'improved', text: 'Polished About page with feature highlights, tech stack and full changelog' },
          { type: 'improved', text: 'Page-level loading bar on route navigation' },
          { type: 'improved', text: 'Network offline detection banner' },
          { type: 'improved', text: 'Empty states for all main list views' },
          { type: 'improved', text: 'Consistent API error handling with toast messages per status code' },
          { type: 'improved', text: 'All routes use lazy loading with prefetch hints on common pages' },
          { type: 'improved', text: 'Vite manual chunk splitting for optimised production bundles' },
        ]
      },
      {
        version: '1.6.0',
        date: 'January 2026',
        entries: [
          { type: 'new', text: 'Command palette (Ctrl+K) for quick navigation' },
          { type: 'new', text: 'Keyboard shortcut system with chord sequences (g+d, g+v, etc.)' },
          { type: 'new', text: 'Dark / light / system theme support' },
          { type: 'new', text: 'In-app notification centre with webhook delivery log' },
          { type: 'new', text: 'Security dashboard — failed logins, lockouts, IP rules, GeoIP' },
          { type: 'new', text: 'Audit log with CSV export and advanced filtering' },
          { type: 'new', text: 'Node Monitor — cluster-wide overview across all nodes' },
          { type: 'new', text: 'Resource Pools management' },
          { type: 'new', text: 'API Explorer with OpenAPI summary' },
          { type: 'improved', text: 'Bulk actions on VM and container list pages' },
          { type: 'improved', text: 'Sortable columns on all major tables' },
          { type: 'fixed', text: 'Token refresh no longer causes duplicate login redirects' },
        ]
      },
      {
        version: '1.5.0',
        date: 'October 2025',
        entries: [
          { type: 'new', text: 'Multi-user authentication with RBAC (admin / operator / viewer)' },
          { type: 'new', text: 'TOTP 2FA with backup codes' },
          { type: 'new', text: 'Session management and API key support' },
          { type: 'new', text: 'Cloud image downloads and template provisioning' },
          { type: 'new', text: 'Cloud-init editor for VM customisation' },
          { type: 'new', text: 'ISO management with upload and URL download' },
          { type: 'new', text: 'Automated update management for guest VMs' },
          { type: 'new', text: 'Bug report form' },
          { type: 'improved', text: 'Dashboard stats with recent activity feed' },
          { type: 'improved', text: 'Responsive layout optimised for tablets and mobile' },
          { type: 'fixed', text: 'VM deployment race condition with cloud-init generation' },
        ]
      },
    ]

    const coreLibs = [
      { name: 'FastAPI', desc: 'Python web framework', url: 'https://fastapi.tiangolo.com' },
      { name: 'Proxmoxer', desc: 'Proxmox API Python wrapper', url: 'https://github.com/proxmoxer/proxmoxer' },
      { name: 'Vue 3', desc: 'Progressive JavaScript framework', url: 'https://vuejs.org' },
      { name: 'Vite', desc: 'Next-generation frontend tooling', url: 'https://vitejs.dev' },
      { name: 'Pinia', desc: 'Vue state management', url: 'https://pinia.vuejs.org' },
      { name: 'Axios', desc: 'HTTP client', url: 'https://axios-http.com' },
      { name: 'noVNC', desc: 'VNC client in browser', url: 'https://novnc.com' },
      { name: 'xterm.js', desc: 'Terminal emulator', url: 'https://xtermjs.org' },
      { name: 'SQLAlchemy', desc: 'Python ORM', url: 'https://www.sqlalchemy.org' },
    ]

    // Health info
    const healthInfo = ref(null)
    const healthLoading = ref(false)

    const fetchHealthInfo = async () => {
      healthLoading.value = true
      try {
        const res = await api.system.health()
        healthInfo.value = res.data
      } catch {
        // silently ignore — may not be admin
      } finally {
        healthLoading.value = false
      }
    }

    // Update check
    const updateChecking = ref(false)
    const updateStatus = ref(null)   // 'up-to-date' | 'available' | 'pre-release' | 'loading'
    const latestVersion = ref(null)
    const updateReleaseNotes = ref(null)
    const updateError = ref(null)

    const _compareVersions = (a, b) => {
      const parse = v => (v || '').replace(/^v/, '').split('.').map(Number)
      const av = parse(a)
      const bv = parse(b)
      for (let i = 0; i < 3; i++) {
        if ((av[i] || 0) > (bv[i] || 0)) return 1
        if ((av[i] || 0) < (bv[i] || 0)) return -1
      }
      return 0
    }

    const checkForUpdates = async () => {
      updateChecking.value = true
      updateStatus.value = 'loading'
      updateError.value = null
      updateReleaseNotes.value = null
      try {
        const res = await fetch('https://api.github.com/repos/agit8or1/Depl0y/releases/latest', {
          headers: { Accept: 'application/vnd.github+json' }
        })
        if (!res.ok) throw new Error(`GitHub API ${res.status}`)
        const data = await res.json()
        latestVersion.value = (data.tag_name || '').replace(/^v/, '')
        updateReleaseNotes.value = data.body ? data.body.slice(0, 600) + (data.body.length > 600 ? '…' : '') : null
        const cmp = _compareVersions(version.value, latestVersion.value)
        if (cmp < 0) updateStatus.value = 'available'
        else if (cmp > 0) updateStatus.value = 'pre-release'
        else updateStatus.value = 'up-to-date'
      } catch (e) {
        updateError.value = 'Could not reach GitHub. Check your network connection.'
        updateStatus.value = null
      } finally {
        updateChecking.value = false
      }
    }

    // License toggle
    const showLicense = ref(false)

    onMounted(async () => {
      try {
        const response = await api.system.getInfo()
        if (response.data?.version) version.value = response.data.version
      } catch {
        version.value = '1.8.0'
      }
      fetchHealthInfo()
    })

    return {
      version,
      currentVersion,
      buildDate,
      openVersions,
      toggleVersion,
      featureHighlights,
      techStack,
      changelog,
      coreLibs,
      // System info
      healthInfo,
      healthLoading,
      fetchHealthInfo,
      // Updates
      updateChecking,
      updateStatus,
      latestVersion,
      updateReleaseNotes,
      updateError,
      checkForUpdates,
      // License
      showLicense,
    }
  }
}
</script>

<style scoped>
.about-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 960px;
  margin: 0 auto;
}

/* ── Hero ── */
.hero-card {
  position: relative;
  overflow: hidden;
  padding: 0;
}

.hero-gradient-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 40%, #1d4ed8 70%, #2563eb 100%);
  opacity: 0.97;
}

.hero-content {
  position: relative;
  z-index: 1;
  padding: 2.5rem 2rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
}

.logo-wrap {
  text-align: center;
}

.about-logo {
  font-size: 4.5rem;
  font-weight: 800;
  margin: 0;
  letter-spacing: -3px;
  color: #fff;
  text-shadow: 0 2px 20px rgba(0,0,0,0.3);
  background: linear-gradient(135deg, #ffffff 0%, #bfdbfe 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.logo-zero {
  background: linear-gradient(135deg, #60a5fa 0%, #93c5fd 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.tagline {
  font-size: 1.05rem;
  color: rgba(255,255,255,0.8);
  margin: 0.6rem 0 1rem;
  letter-spacing: 0.01em;
}

.badges {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.status-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  background: #34d399;
  border-radius: 50%;
  box-shadow: 0 0 6px #34d399;
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.version-badge {
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.25);
  color: rgba(255,255,255,0.9);
  padding: 0.2rem 0.65rem;
  border-radius: 9999px;
  font-size: 0.78rem;
  font-weight: 600;
  font-family: monospace;
}

.loading-badge {
  opacity: 0.6;
  animation: fade-pulse 1.2s ease-in-out infinite;
}

@keyframes fade-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 0.3; }
}

.build-badge {
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.15);
  color: rgba(255,255,255,0.65);
  padding: 0.2rem 0.65rem;
  border-radius: 9999px;
  font-size: 0.75rem;
}

/* Hero action buttons */
.hero-actions {
  display: flex;
  justify-content: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.hero-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1.1rem;
  border-radius: 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.18s ease;
  border: 1px solid transparent;
}

.hero-btn-primary {
  background: rgba(255,255,255,0.2);
  color: #fff;
  border-color: rgba(255,255,255,0.35);
}

.hero-btn-primary:hover {
  background: rgba(255,255,255,0.3);
}

.hero-btn-outline {
  background: rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.85);
  border-color: rgba(255,255,255,0.2);
}

.hero-btn-outline:hover {
  background: rgba(255,255,255,0.16);
  color: #fff;
}

.hero-btn-sponsor {
  background: rgba(236,72,153,0.25);
  color: #fce7f3;
  border-color: rgba(236,72,153,0.4);
}

.hero-btn-sponsor:hover {
  background: rgba(236,72,153,0.4);
  color: #fff;
}

/* System info grid */
.system-info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.875rem 1rem;
  background: rgba(255,255,255,0.08);
  border-radius: 0.5rem;
  border: 1px solid rgba(255,255,255,0.12);
}

.info-label {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255,255,255,0.55);
  font-weight: 700;
}

.info-value {
  font-size: 0.9rem;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
}

/* ── Section cards ── */
.section-card {
  padding: 1.5rem 1.75rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 1.25rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  padding-bottom: 0.875rem;
  border-bottom: 2px solid var(--border-color);
}

/* ── Features grid ── */
.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

.feature-card {
  display: flex;
  align-items: flex-start;
  gap: 0.875rem;
  padding: 1rem;
  background: var(--background);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  transition: box-shadow 0.15s;
}

.feature-card:hover {
  box-shadow: var(--shadow-lg);
}

.feature-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 0.5rem;
  flex-shrink: 0;
}

.feature-body {
  flex: 1;
  min-width: 0;
}

.feature-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}

.feature-desc {
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* ── Tech stack ── */
.stack-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.stack-group-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}

.stack-items {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.stack-badge {
  padding: 0.3rem 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-primary);
}

/* ── Changelog ── */
.changelog-versions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.changelog-version {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
}

.version-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1rem;
  background: var(--background);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.version-header:hover {
  background: var(--border-color);
}

.version-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.version-tag {
  font-family: monospace;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-primary);
  padding: 0.15rem 0.5rem;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}

.version-current {
  color: var(--primary-color);
  border-color: var(--primary-color);
  background: rgba(59,130,246,0.08);
}

.current-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--secondary-color);
  background: rgba(16,185,129,0.1);
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
}

.version-date {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.chevron {
  color: var(--text-muted);
  transition: transform 0.2s ease;
}

.chevron-open {
  transform: rotate(180deg);
}

.version-entries {
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  border-top: 1px solid var(--border-color);
}

.changelog-entry {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  font-size: 0.85rem;
  color: var(--text-primary);
  padding: 0.35rem 0;
}

.entry-type-badge {
  flex-shrink: 0;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.15rem 0.45rem;
  border-radius: 0.25rem;
  margin-top: 0.1rem;
}

.entry-new .entry-type-badge {
  background: rgba(59,130,246,0.12);
  color: #2563eb;
}
[data-theme="dark"] .entry-new .entry-type-badge {
  background: rgba(59,130,246,0.2);
  color: #93c5fd;
}

.entry-improved .entry-type-badge {
  background: rgba(16,185,129,0.12);
  color: #059669;
}
[data-theme="dark"] .entry-improved .entry-type-badge {
  background: rgba(16,185,129,0.2);
  color: #6ee7b7;
}

.entry-fixed .entry-type-badge {
  background: rgba(245,158,11,0.12);
  color: #d97706;
}
[data-theme="dark"] .entry-fixed .entry-type-badge {
  background: rgba(245,158,11,0.2);
  color: #fcd34d;
}

/* Collapse transition */
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.25s ease;
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

/* ── Credits ── */
.credits-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.credits-group-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.credits-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.5rem;
}

.credit-item {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.65rem 0.875rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  text-decoration: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.credit-item:hover {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(59,130,246,0.1);
}

.credit-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--primary-color);
}

.credit-desc {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.builder-inner {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  padding: 1rem 1.25rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
}

.builder-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.builder-name {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--primary-color);
  text-decoration: none;
  transition: opacity 0.15s;
}

.builder-name:hover {
  opacity: 0.8;
  text-decoration: underline;
}

.builder-url {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-family: monospace;
}

.builder-links {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.builder-link-btn {
  display: inline-block;
  padding: 0.35rem 0.875rem;
  background: var(--surface);
  color: var(--text-primary);
  text-decoration: none;
  border-radius: 0.375rem;
  font-size: 0.8rem;
  font-weight: 600;
  border: 1px solid var(--border-color);
  transition: border-color 0.15s, background 0.15s;
}

.builder-link-btn:hover {
  border-color: var(--primary-color);
  background: var(--background);
}

.sponsor-btn {
  color: #be185d;
  border-color: rgba(236,72,153,0.35);
}
[data-theme="dark"] .sponsor-btn {
  color: #f9a8d4;
}

.sponsor-btn:hover {
  background: rgba(236,72,153,0.08);
  border-color: #ec4899;
}

/* ── System Info section ── */
.sysinfo-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
}

.sysinfo-item {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.75rem 1rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
}

.sysinfo-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
}

.sysinfo-value {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.val-ok { color: #10b981; }
.val-warn { color: #f59e0b; }
.val-err { color: #ef4444; }

.sysinfo-loading {
  font-size: 0.85rem;
  color: var(--text-muted);
  padding: 0.5rem 0;
}

.sysinfo-empty {
  padding: 0.5rem 0;
}

.btn-load-sysinfo {
  padding: 0.4rem 1rem;
  background: var(--primary-color);
  color: #fff;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-load-sysinfo:hover { opacity: 0.85; }

.refresh-btn {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.7rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.15s;
}

.refresh-btn:hover { border-color: var(--primary-color); }
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Updates section ── */
.updates-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.updates-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.updates-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.updates-current {
  font-size: 0.9rem;
  color: var(--text-primary);
}

.updates-latest {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.update-badge {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.2rem 0.55rem;
  border-radius: 9999px;
}

.update-ok {
  background: rgba(16,185,129,0.12);
  color: #059669;
}
[data-theme="dark"] .update-ok { background: rgba(16,185,129,0.2); color: #6ee7b7; }

.update-avail {
  background: rgba(59,130,246,0.12);
  color: #2563eb;
}
[data-theme="dark"] .update-avail { background: rgba(59,130,246,0.2); color: #93c5fd; }

.update-pre {
  background: rgba(245,158,11,0.12);
  color: #d97706;
}
[data-theme="dark"] .update-pre { background: rgba(245,158,11,0.2); color: #fcd34d; }

.check-update-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 1rem;
  background: var(--primary-color);
  color: #fff;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
  white-space: nowrap;
}

.check-update-btn:hover { opacity: 0.85; }
.check-update-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.update-notes {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.875rem 1rem;
}

.update-notes-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 0.5rem;
}

.update-notes-body {
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  font-family: inherit;
  line-height: 1.55;
}

.update-error {
  font-size: 0.85rem;
  color: #ef4444;
  margin: 0;
}

/* ── License section ── */
.license-section {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

.license-header {
  display: flex;
  align-items: center;
  gap: 0.875rem;
}

.license-badge {
  padding: 0.25rem 0.75rem;
  background: rgba(59,130,246,0.1);
  border: 1px solid rgba(59,130,246,0.3);
  color: var(--primary-color);
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 700;
}

.license-year {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.license-summary {
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}

.license-expand-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.license-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.35rem 0.875rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
  width: fit-content;
}

.license-toggle:hover { border-color: var(--primary-color); color: var(--primary-color); }

.license-text {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
}

.license-text pre {
  font-size: 0.78rem;
  font-family: monospace;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.6;
}

/* ── Contributors section ── */
.contributors-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.contributor-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
}

.contributor-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1e40af, #2563eb);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  font-weight: 700;
  flex-shrink: 0;
}

.contributor-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.contributor-name {
  font-size: 1rem;
  font-weight: 700;
  color: var(--primary-color);
  text-decoration: none;
}

.contributor-name:hover { text-decoration: underline; }

.contributor-role {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.contributor-site {
  font-size: 0.78rem;
  color: var(--text-muted);
  text-decoration: none;
  font-family: monospace;
}

.contributor-site:hover { color: var(--primary-color); }

.contributors-cta {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 0.875rem 1rem;
  background: var(--background);
  border: 1px dashed var(--border-color);
  border-radius: 0.5rem;
}

.contributors-cta p {
  margin: 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
  flex: 1;
}

.contribute-btn {
  padding: 0.4rem 1rem;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
  text-decoration: none;
  transition: border-color 0.15s;
  white-space: nowrap;
}

.contribute-btn:hover { border-color: var(--primary-color); color: var(--primary-color); }

/* ── Responsive ── */
@media (max-width: 768px) {
  .system-info-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .features-grid {
    grid-template-columns: 1fr;
  }
  .hero-actions {
    flex-direction: column;
    align-items: center;
  }
  .sysinfo-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .updates-row {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 480px) {
  .system-info-grid {
    grid-template-columns: 1fr 1fr;
  }
  .about-logo {
    font-size: 3rem;
  }
  .sysinfo-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
