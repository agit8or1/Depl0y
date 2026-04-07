<template>
  <div class="dashboard">

    <!-- ── Welcome Banner (first visit, localStorage flag) ── -->
    <transition name="banner-fade">
      <div v-if="showWelcomeBanner" class="welcome-banner">
        <div class="welcome-banner-inner">
          <div class="welcome-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/>
            </svg>
          </div>
          <div class="welcome-content">
            <span class="welcome-title">Welcome to Depl0y!</span>
            <span class="welcome-text">Add your first Proxmox host to get started.</span>
          </div>
          <button class="btn btn-primary btn-sm welcome-action" @click="openWizardFromBanner">Add Host</button>
          <button class="welcome-dismiss" @click="dismissWelcomeBanner" title="Dismiss" aria-label="Dismiss welcome banner">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>
    </transition>

    <!-- ── First-run onboarding (admin, no hosts) ── -->
    <transition name="onboard-fade">
      <div v-if="showOnboarding" class="onboarding-screen">
        <div class="onboard-hero">
          <div class="onboard-logo">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="var(--primary-color)" stroke-width="1.5">
              <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
          </div>
          <h1 class="onboard-title">Welcome to Depl0y</h1>
          <p class="onboard-sub">Your Proxmox VM management platform. Follow the steps below to get started.</p>
        </div>

        <div class="onboard-checklist">
          <!-- Step 1: Account created -->
          <div class="checklist-item checklist-done">
            <div class="check-icon check-complete">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
            <div class="check-content">
              <span class="check-label">Account Created</span>
              <span class="check-desc">You're logged in and ready to go</span>
            </div>
          </div>

          <!-- Step 2: Add first host -->
          <div :class="['checklist-item', firstHostAdded ? 'checklist-done' : 'checklist-active']">
            <div :class="['check-icon', firstHostAdded ? 'check-complete' : 'check-pending']">
              <svg v-if="firstHostAdded" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span v-else class="check-num">2</span>
            </div>
            <div class="check-content">
              <span class="check-label">Add Your First Proxmox Host</span>
              <span v-if="firstHostAdded" class="check-desc check-done-text">Proxmox datacenter connected</span>
              <span v-else class="check-desc">Connect Depl0y to your Proxmox cluster or standalone node</span>
            </div>
            <button v-if="!firstHostAdded" class="btn btn-primary btn-sm" @click="openWizard">
              Add Host
            </button>
          </div>

          <!-- Step 3: Deploy first VM -->
          <div :class="['checklist-item', !firstHostAdded ? 'checklist-locked' : 'checklist-active']">
            <div :class="['check-icon', !firstHostAdded ? 'check-locked' : 'check-pending']">
              <svg v-if="!firstHostAdded" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              <span v-else class="check-num">3</span>
            </div>
            <div class="check-content">
              <span class="check-label">Deploy Your First VM</span>
              <span class="check-desc">Provision a new virtual machine on your Proxmox cluster</span>
            </div>
            <router-link v-if="firstHostAdded" to="/vms" class="btn btn-outline btn-sm">
              Deploy VM
            </router-link>
          </div>
        </div>

        <p class="onboard-skip">
          <a href="#" @click.prevent="skipOnboarding" class="skip-link">Skip — go to dashboard</a>
        </p>

        <!-- Wizard -->
        <AddHostWizard v-model="showWizard" @host-added="onFirstHostAdded" />
      </div>
    </transition>

    <!-- ── Normal dashboard (hosts exist or onboarding skipped) ── -->
    <template v-if="!showOnboarding">

    <!-- QuickStatsBar — always full-width at top -->
    <QuickStatsBar />

    <!-- ── No Hosts Configured State ── -->
    <transition name="banner-fade">
      <div v-if="noHostsConfigured && !initialLoading" class="no-hosts-state">
        <div class="no-hosts-inner">
          <div class="no-hosts-icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <ellipse cx="12" cy="5" rx="9" ry="3"/>
              <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
            </svg>
          </div>
          <div class="no-hosts-content">
            <p class="no-hosts-title">No Proxmox Hosts Configured</p>
            <p class="no-hosts-sub">Add a Proxmox host to start monitoring your infrastructure and deploying VMs.</p>
          </div>
          <router-link to="/proxmox" class="btn btn-primary btn-sm">Manage Hosts</router-link>
        </div>
      </div>
    </transition>

    <!-- ── Quick Search Bar ── -->
    <div class="quick-search-wrap" ref="searchWrapEl">
      <div class="quick-search-input-row">
        <svg class="qs-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          ref="searchInputEl"
          v-model="searchQuery"
          @input="onSearchInput"
          @focus="searchFocused = true"
          @keydown.down.prevent="searchNavDown"
          @keydown.up.prevent="searchNavUp"
          @keydown.enter.prevent="searchNavSelect"
          @keydown.escape="closeSearch"
          class="quick-search-input"
          placeholder="Search VMs, nodes, hosts... (/ to focus)"
          autocomplete="off"
        />
        <span v-if="searchLoading" class="qs-spinner"></span>
        <kbd v-if="!searchFocused && !searchQuery" class="qs-kbd">/</kbd>
        <button v-if="searchQuery" class="qs-clear" @click="clearSearch" aria-label="Clear search">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- Search Results Dropdown -->
      <transition name="dropdown-fade">
        <div v-if="searchFocused && (searchResults.length > 0 || (searchQuery.length >= 2 && !searchLoading))" class="qs-dropdown">
          <div v-if="searchResults.length === 0 && !searchLoading" class="qs-no-results">
            No results for "{{ searchQuery }}"
          </div>
          <template v-else>
            <div
              v-for="(item, idx) in searchResults"
              :key="`${item.type}-${item.id}`"
              :class="['qs-result-item', searchNavIndex === idx ? 'qs-result-active' : '']"
              @mousedown.prevent="navigateToResult(item)"
              @mouseover="searchNavIndex = idx"
            >
              <span :class="['qs-result-badge', item.type === 'vm' ? 'badge-type-vm' : item.type === 'node' ? 'badge-type-node' : 'badge-type-host']">
                {{ item.type }}
              </span>
              <span class="qs-result-name">{{ item.name }}</span>
              <span class="qs-result-meta">{{ item.meta }}</span>
              <span v-if="item.status" :class="['qs-status-dot', item.status === 'running' || item.status === 'online' ? 'dot-green' : 'dot-grey']"></span>
            </div>
          </template>
        </div>
      </transition>
    </div>

    <!-- ── Alerts Summary Widget ── -->
    <transition name="alerts-slide">
      <div v-if="alertsSummary && alertsSummary.count > 0" class="alerts-summary-bar" @click="$router.push('/alerts')" role="button">
        <div class="asb-left">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="asb-icon">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span class="asb-title">{{ alertsSummary.count }} Active Alert{{ alertsSummary.count !== 1 ? 's' : '' }}</span>
        </div>
        <div class="asb-breakdown">
          <span v-if="alertsBySeverity.error > 0" class="asb-chip asb-chip-error">
            {{ alertsBySeverity.error }} Error{{ alertsBySeverity.error !== 1 ? 's' : '' }}
          </span>
          <span v-if="alertsBySeverity.warning > 0" class="asb-chip asb-chip-warn">
            {{ alertsBySeverity.warning }} Warning{{ alertsBySeverity.warning !== 1 ? 's' : '' }}
          </span>
          <span v-if="alertsBySeverity.info > 0" class="asb-chip asb-chip-info">
            {{ alertsBySeverity.info }} Info
          </span>
        </div>
        <div class="asb-right">
          <span class="asb-cta">View Alerts</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </div>
      </div>
    </transition>

    <!-- Dashboard header bar -->
    <div class="dash-header">
      <h2 class="dash-title">Dashboard</h2>
      <div class="dash-actions">
        <span class="last-updated" :title="lastUpdatedAt ? 'Last updated: ' + lastUpdatedAt : ''">
          {{ lastUpdatedSeconds }}s ago
        </span>
        <button class="btn-icon" title="Refresh dashboard" aria-label="Refresh dashboard" @click="refreshAll" :class="{ 'btn-icon--spinning': globalRefreshing }">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <polyline points="23 4 23 10 17 10"/>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
          </svg>
        </button>
        <button class="btn-icon" title="Customize Widgets" aria-label="Customize widgets" @click="showCustomize = !showCustomize">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/>
          </svg>
        </button>
        <button class="btn-icon" title="Add Widget" aria-label="Add widget" @click="showPicker = true">+</button>
        <button class="btn-icon" title="Reset Layout" aria-label="Reset layout" @click="resetLayout">↺</button>
        <button class="btn-icon" title="Keyboard shortcuts (?)" aria-label="Show keyboard shortcuts" @click="showShortcutsHint = !showShortcutsHint">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- ── Keyboard Shortcuts Hint Overlay ── -->
    <transition name="panel-slide">
      <div v-if="showShortcutsHint" class="shortcuts-hint-panel">
        <div class="shp-header">
          <span class="shp-title">Dashboard Shortcuts</span>
          <button class="shp-close" @click="showShortcutsHint = false" aria-label="Close shortcuts panel">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="shp-grid">
          <div class="shp-row"><kbd>/</kbd><span>Focus search</span></div>
          <div class="shp-row"><kbd>?</kbd><span>All shortcuts</span></div>
          <div class="shp-row"><kbd>Ctrl</kbd><span>+</span><kbd>K</kbd><span>Command palette</span></div>
          <div class="shp-row"><kbd>g</kbd><span>+</span><kbd>d</kbd><span>Go to Dashboard</span></div>
          <div class="shp-row"><kbd>g</kbd><span>+</span><kbd>v</kbd><span>Go to VMs</span></div>
          <div class="shp-row"><kbd>g</kbd><span>+</span><kbd>n</kbd><span>Go to Nodes</span></div>
          <div class="shp-row"><kbd>g</kbd><span>+</span><kbd>t</kbd><span>Go to Tasks</span></div>
          <div class="shp-row"><kbd>g</kbd><span>+</span><kbd>b</kbd><span>Go to Backup</span></div>
          <div class="shp-row"><kbd>g</kbd><span>+</span><kbd>s</kbd><span>Go to Settings</span></div>
        </div>
        <p class="shp-hint">Press <kbd>?</kbd> for the full shortcut reference.</p>
      </div>
    </transition>

    <!-- Customize panel -->
    <transition name="panel-slide">
      <div v-if="showCustomize" class="customize-panel">
        <div class="customize-header">
          <span class="customize-title">Widget Visibility</span>
          <span class="customize-hint">Toggled widgets are hidden but not removed from your layout</span>
        </div>
        <div class="customize-grid">
          <label
            v-for="type in allWidgetTypes"
            :key="type.type"
            class="toggle-item"
            :class="{ 'toggle-active': isWidgetVisible(type.type) }"
          >
            <input
              type="checkbox"
              class="toggle-check"
              :checked="isWidgetVisible(type.type)"
              @change="toggleWidgetVisibility(type.type)"
            />
            <span class="toggle-icon">{{ type.icon }}</span>
            <span class="toggle-label">{{ type.label }}</span>
          </label>
        </div>
      </div>
    </transition>

    <!-- ── Resource Summary Bar ── -->
    <div v-if="!initialLoading" class="resource-summary-bar">
      <!-- VMs -->
      <div class="rsb-card rsb-card-link" @click="$router.push('/vms')" role="link" tabindex="0" @keydown.enter="$router.push('/vms')">
        <div class="rsb-icon rsb-icon-vm">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        </div>
        <div class="rsb-content">
          <span class="rsb-label">Virtual Machines</span>
          <div class="rsb-value-row">
            <span class="rsb-big">{{ dashSummary.vm_count ?? '—' }}</span>
            <span class="rsb-sub">
              <span class="rsb-chip rsb-chip-green">{{ dashSummary.running_vms ?? 0 }} running</span>
              <span class="rsb-chip rsb-chip-gray">{{ (dashSummary.vm_count ?? 0) - (dashSummary.running_vms ?? 0) }} stopped</span>
            </span>
          </div>
        </div>
      </div>
      <!-- Nodes -->
      <div class="rsb-card rsb-card-link" @click="$router.push('/cluster')" role="link" tabindex="0" @keydown.enter="$router.push('/cluster')">
        <div class="rsb-icon rsb-icon-node">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
        </div>
        <div class="rsb-content">
          <span class="rsb-label">Nodes</span>
          <div class="rsb-value-row">
            <span class="rsb-big">{{ dashSummary.node_count ?? '—' }}</span>
            <span class="rsb-sub">
              <span class="rsb-chip rsb-chip-green">online</span>
            </span>
          </div>
        </div>
      </div>
      <!-- Storage -->
      <div class="rsb-card rsb-card-link" @click="$router.push('/storage-management')" role="link" tabindex="0" @keydown.enter="$router.push('/storage-management')">
        <div class="rsb-icon rsb-icon-storage">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
        </div>
        <div class="rsb-content">
          <span class="rsb-label">Storage</span>
          <div class="rsb-value-row">
            <span class="rsb-big">{{ resourceStats ? resourceStats.used_disk_gb.toFixed(1) : (dashSummary.storage_used_gb ?? '—') }} GB</span>
            <span class="rsb-sub" v-if="resourceStats">
              <span class="rsb-chip rsb-chip-gray">/ {{ resourceStats.total_disk_gb.toFixed(1) }} GB</span>
            </span>
          </div>
        </div>
      </div>
      <!-- CPU -->
      <div class="rsb-card rsb-card-link" v-if="resourceStats" @click="$router.push('/node-monitor')" role="link" tabindex="0" @keydown.enter="$router.push('/node-monitor')">
        <div class="rsb-icon rsb-icon-cpu">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>
        </div>
        <div class="rsb-content">
          <span class="rsb-label">CPU Usage</span>
          <div class="rsb-value-row">
            <span class="rsb-big" :class="cpuUsedPct > 80 ? 'rsb-big-warn' : ''">{{ cpuUsedPct }}%</span>
            <span class="rsb-sub">
              <span class="rsb-chip rsb-chip-gray">{{ resourceStats.used_cpu_cores }}/{{ resourceStats.total_cpu_cores }} cores</span>
            </span>
          </div>
        </div>
      </div>
      <!-- RAM -->
      <div class="rsb-card rsb-card-link" v-if="resourceStats" @click="$router.push('/node-monitor')" role="link" tabindex="0" @keydown.enter="$router.push('/node-monitor')">
        <div class="rsb-icon rsb-icon-ram">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="5" width="22" height="14" rx="2"/><line x1="7" y1="9" x2="7" y2="15"/><line x1="11" y1="9" x2="11" y2="15"/><line x1="15" y1="9" x2="15" y2="15"/><line x1="19" y1="9" x2="19" y2="15"/></svg>
        </div>
        <div class="rsb-content">
          <span class="rsb-label">RAM Usage</span>
          <div class="rsb-value-row">
            <span class="rsb-big" :class="ramUsedPct > 85 ? 'rsb-big-warn' : ''">{{ ramUsedPct }}%</span>
            <span class="rsb-sub">
              <span class="rsb-chip rsb-chip-gray">{{ resourceStats.used_memory_gb.toFixed(1) }}/{{ resourceStats.total_memory_gb.toFixed(1) }} GB</span>
            </span>
          </div>
        </div>
      </div>
    </div>
    <!-- Loading skeleton for resource summary -->
    <div v-else-if="initialLoading" class="resource-summary-bar">
      <div v-for="i in 5" :key="i" class="rsb-card rsb-card-skel">
        <div class="rsb-skel-icon"></div>
        <div class="rsb-skel-content">
          <div class="rsb-skel-label"></div>
          <div class="rsb-skel-value"></div>
        </div>
      </div>
    </div>

    <!-- ── Quick Actions Panel ── -->
    <div class="quick-actions-panel">
      <span class="qap-title">Quick Actions</span>
      <div class="qap-buttons">
        <button class="qap-btn" @click="$router.push('/vms/create')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="12" y1="17" x2="12" y2="21"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="8" x2="12" y2="14"/><line x1="9" y1="11" x2="15" y2="11"/></svg>
          New VM
        </button>
        <button class="qap-btn" @click="$router.push('/create-lxc')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
          New Container
        </button>
        <button class="qap-btn" @click="$router.push('/bulk-ops')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="5" width="20" height="4" rx="1"/><rect x="2" y="12" width="20" height="4" rx="1"/><rect x="2" y="19" width="20" height="4" rx="1"/></svg>
          Bulk Operations
        </button>
        <button class="qap-btn" @click="$router.push('/vm-search')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          VM Search
        </button>
        <button class="qap-btn" @click="$router.push('/proxmox')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
          Manage Hosts
        </button>
      </div>
    </div>

    <!-- ── Resource Trending Row ── -->
    <div v-if="resourceStats" class="resource-trending-row">
      <div class="rt-card">
        <span class="rt-label">CPU</span>
        <span class="rt-value">{{ cpuUsedPct }}%</span>
        <span :class="['rt-arrow', trendClass(cpuTrend)]" :title="trendTitle(cpuTrend)">{{ trendArrow(cpuTrend) }}</span>
      </div>
      <div class="rt-card">
        <span class="rt-label">RAM</span>
        <span class="rt-value">{{ ramUsedPct }}%</span>
        <span :class="['rt-arrow', trendClass(ramTrend)]" :title="trendTitle(ramTrend)">{{ trendArrow(ramTrend) }}</span>
      </div>
      <div class="rt-card">
        <span class="rt-label">Storage</span>
        <span class="rt-value">{{ diskUsedPct }}%</span>
        <span :class="['rt-arrow', trendClass(diskTrend)]" :title="trendTitle(diskTrend)">{{ trendArrow(diskTrend) }}</span>
      </div>
      <div class="rt-card">
        <span class="rt-label">RAM Used</span>
        <span class="rt-value">{{ resourceStats.used_memory_gb.toFixed(1) }} / {{ resourceStats.total_memory_gb.toFixed(1) }} GB</span>
      </div>
    </div>
    <!-- Loading skeleton for resource row -->
    <div v-else-if="initialLoading" class="resource-trending-row">
      <SkeletonLoader type="stat" :count="5" />
    </div>

    <!-- Widget grid -->
    <transition-group tag="div" name="widget-reorder" class="widget-grid" ref="gridEl">
      <div
        v-for="widget in displayLayout"
        :key="widget.id"
        :class="['widget-card',
          dragging && dragging.id === widget.id ? 'widget-dragging' : '',
          dropTarget && dropTarget.id === widget.id && dragging && dragging.id !== widget.id ? 'widget-drop-target' : '',
          widgetHasError(widget.id) ? 'widget-card--error' : '']"
        :data-widget-id="widget.id"
        :style="widgetStyle(widget)"
      >
        <!-- Widget title bar -->
        <div
          class="widget-bar"
          @mousedown="startDrag($event, widget)"
          @touchstart.prevent="startDragTouch($event, widget)"
        >
          <span class="widget-grip" title="Drag to reorder">⠿</span>
          <span class="widget-title">{{ widgetMeta(widget.type).label }}</span>
          <div class="widget-controls">
            <!-- Per-widget last-updated + refresh -->
            <span v-if="widgetLastUpdated(widget.id)" class="widget-ts" :title="'Last updated: ' + widgetLastUpdated(widget.id)">
              {{ widgetAgo(widget.id) }}
            </span>
            <button
              class="wc-btn"
              title="Refresh widget"
              aria-label="Refresh widget"
              @click.stop="refreshWidget(widget)"
              :class="{ 'wc-spinning': widgetRefreshing.has(widget.id) }"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
                <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
            </button>
            <button class="wc-btn" :title="widget.collapsed ? 'Expand' : 'Collapse'" :aria-label="widget.collapsed ? 'Expand widget' : 'Collapse widget'" @click.stop="toggleCollapse(widget)">
              {{ widget.collapsed ? '▲' : '▼' }}
            </button>
            <button class="wc-btn" title="Settings" aria-label="Widget settings" @click.stop="openSettings(widget)">⚙</button>
            <button class="wc-btn wc-remove" title="Remove" aria-label="Remove widget" @click.stop="removeWidget(widget)">×</button>
          </div>
        </div>

        <!-- Widget body: loading skeleton -->
        <div v-if="!widget.collapsed && widgetLoading.has(widget.id)" class="widget-body">
          <SkeletonLoader type="card" :count="2" />
        </div>

        <!-- Widget body: error state -->
        <div v-else-if="!widget.collapsed && widgetHasError(widget.id)" class="widget-body widget-error-body">
          <div class="widget-error-state">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.5">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <p class="widget-error-msg">{{ widgetErrorMsg(widget.id) }}</p>
            <button class="btn btn-outline btn-sm" @click.stop="refreshWidget(widget)">Retry</button>
          </div>
        </div>

        <!-- Widget body: normal -->
        <div v-else-if="!widget.collapsed" class="widget-body">
          <component
            :is="widgetComponent(widget.type)"
            v-bind="widget.config || {}"
            @error="onWidgetError(widget.id, $event)"
            @loaded="onWidgetLoaded(widget.id)"
          />
        </div>
      </div>
    </transition-group>

    <!-- Initial dashboard skeleton (before first load) -->
    <div v-if="initialLoading && layout.length === 0" class="widget-grid">
      <div v-for="i in 6" :key="i" class="widget-card" :style="{ gridColumn: 'span 1' }">
        <div class="widget-bar">
          <span class="widget-grip" title="Drag to reorder">⠿</span>
          <div class="widget-title-skel"></div>
        </div>
        <div class="widget-body">
          <SkeletonLoader type="card" :count="2" />
        </div>
      </div>
    </div>

    <!-- ── Recent Activity Feed ── -->
    <div class="activity-feed-panel">
      <div class="afp-header">
        <span class="afp-title">Recent Activity</span>
        <div class="afp-header-right">
          <span v-if="activityLastUpdated" class="afp-ts">{{ activityAgoText }}</span>
          <button class="afp-refresh" @click="fetchActivity" :disabled="activityLoading" title="Refresh activity" aria-label="Refresh activity feed">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" :class="{ 'spinning': activityLoading }" aria-hidden="true">
              <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </button>
          <router-link to="/audit" class="afp-viewall">View All</router-link>
        </div>
      </div>
      <div v-if="activityLoading && activityFeed.length === 0" class="afp-loading">
        <SkeletonLoader type="table" :count="5" />
      </div>
      <div v-else-if="activityError" class="afp-error-state">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.5">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span>Failed to load activity</span>
        <button class="btn btn-outline btn-sm" @click="fetchActivity">Retry</button>
      </div>
      <div v-else-if="activityFeed.length === 0" class="afp-empty">No recent activity.</div>
      <div v-else class="afp-list">
        <div v-for="entry in activityFeed" :key="entry.id" class="afp-item">
          <span class="afp-icon">{{ entry.icon || '▸' }}</span>
          <div class="afp-body">
            <span class="afp-action">{{ entry.action }}</span>
            <span v-if="entry.resource" class="afp-resource"> on {{ entry.resource }}</span>
          </div>
          <div class="afp-right">
            <span class="afp-user">{{ entry.user }}</span>
            <span class="afp-time">{{ formatRelTime(entry.time) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="layout.length === 0 && !initialLoading" class="dash-empty">
      <p>No widgets on your dashboard.</p>
      <button class="btn btn-primary" @click="showPicker = true">+ Add Widget</button>
    </div>

    <!-- Widget picker modal -->
    <transition name="modal-fade">
      <div v-if="showPicker" class="modal-overlay" @click.self="showPicker = false" role="dialog" aria-modal="true" aria-label="Add Widget">
        <div class="modal-box picker-modal">
          <div class="modal-header">
            <h3>Add Widget</h3>
            <button class="modal-close" @click="showPicker = false" aria-label="Close dialog">×</button>
          </div>
          <div class="picker-grid">
            <button
              v-for="meta in allWidgetTypes"
              :key="meta.type"
              class="picker-item"
              :disabled="isWidgetAdded(meta.type) && !meta.multi"
              @click="addWidget(meta.type)"
            >
              <span class="picker-icon">{{ meta.icon }}</span>
              <span class="picker-label">{{ meta.label }}</span>
              <span v-if="isWidgetAdded(meta.type) && !meta.multi" class="picker-added">Added</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Widget settings modal -->
    <transition name="modal-fade">
      <div v-if="settingsWidget" class="modal-overlay" @click.self="settingsWidget = null" role="dialog" aria-modal="true" :aria-label="widgetMeta(settingsWidget.type).label + ' Settings'">
        <div class="modal-box settings-modal">
          <div class="modal-header">
            <h3>{{ widgetMeta(settingsWidget.type).label }} — Settings</h3>
            <button class="modal-close" @click="settingsWidget = null" aria-label="Close dialog">×</button>
          </div>
          <div class="settings-body">
            <p class="settings-hint">Widget ID: {{ settingsWidget.id }}</p>
            <p class="settings-hint">Type: {{ settingsWidget.type }}</p>
            <div class="settings-row">
              <label class="form-label">Column span</label>
              <select v-model.number="settingsWidget.colSpan" class="form-control" @change="saveLayout">
                <option :value="1">1 column</option>
                <option :value="2">2 columns</option>
                <option :value="3">3 columns (full width)</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" @click="settingsWidget = null">Done</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- AddHostWizard (from banner) -->
    <AddHostWizard v-model="showWizard" @host-added="onFirstHostAdded" />

    </template><!-- end v-if="!showOnboarding" -->
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, markRaw, nextTick } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import AddHostWizard from '@/components/AddHostWizard.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

// Original widget imports
import ClusterStatsWidget    from '@/components/widgets/ClusterStatsWidget.vue'
import RecentTasksWidget     from '@/components/widgets/RecentTasksWidget.vue'
import AlertsWidget          from '@/components/widgets/AlertsWidget.vue'
import ResourceUsageWidget   from '@/components/widgets/ResourceUsageWidget.vue'
import QuickActionsWidget    from '@/components/widgets/QuickActionsWidget.vue'
import ActivityFeedWidget    from '@/components/widgets/ActivityFeedWidget.vue'
import TopVMsWidget          from '@/components/widgets/TopVMsWidget.vue'
import StorageOverviewWidget from '@/components/widgets/StorageOverviewWidget.vue'
import BackupStatusWidget    from '@/components/widgets/BackupStatusWidget.vue'
import SystemInfoWidget      from '@/components/widgets/SystemInfoWidget.vue'

// New widget imports
import NetworkTrafficWidget  from '@/components/widgets/NetworkTrafficWidget.vue'
import DiskIOWidget          from '@/components/widgets/DiskIOWidget.vue'
import DiskThroughputWidget  from '@/components/widgets/DiskThroughputWidget.vue'
import NodeStatusGrid        from '@/components/widgets/NodeStatusGrid.vue'
import QuickStatsBar         from '@/components/widgets/QuickStatsBar.vue'

const STORAGE_KEY        = 'dashboard_layout'
const VISIBILITY_KEY     = 'dashboard_widget_visibility'
const WELCOME_BANNER_KEY = 'depl0y_welcome_banner_dismissed'

const WIDGET_META = {
  cluster_stats:    { type: 'cluster_stats',    label: 'Cluster Stats',     icon: '🖥️', multi: false },
  recent_tasks:     { type: 'recent_tasks',     label: 'Recent Tasks',      icon: '📋', multi: false },
  alerts:           { type: 'alerts',           label: 'Alerts',            icon: '⚠️', multi: false },
  resource_usage:   { type: 'resource_usage',   label: 'Resource Usage',    icon: '📊', multi: false },
  quick_actions:    { type: 'quick_actions',    label: 'Quick Actions',     icon: '⚡', multi: false },
  activity_feed:    { type: 'activity_feed',    label: 'Activity Feed',     icon: '📡', multi: false },
  top_vms:          { type: 'top_vms',          label: 'Top VMs',           icon: '🏆', multi: false },
  storage_overview: { type: 'storage_overview', label: 'Storage Overview',  icon: '💾', multi: false },
  backup_status:    { type: 'backup_status',    label: 'Backup Status',     icon: '🗄️', multi: false },
  system_info:      { type: 'system_info',      label: 'System Info',       icon: 'ℹ️', multi: false },
  network_traffic:  { type: 'network_traffic',  label: 'Network Traffic',   icon: '📶', multi: false },
  disk_io:          { type: 'disk_io',          label: 'Disk Usage',        icon: '💿', multi: false },
  node_status_grid:  { type: 'node_status_grid',  label: 'Node Status Grid',   icon: '🔲', multi: false },
  disk_throughput:   { type: 'disk_throughput',   label: 'Disk I/O',           icon: '📀', multi: false },
}

const WIDGET_COMPONENTS = {
  cluster_stats:    markRaw(ClusterStatsWidget),
  recent_tasks:     markRaw(RecentTasksWidget),
  alerts:           markRaw(AlertsWidget),
  resource_usage:   markRaw(ResourceUsageWidget),
  quick_actions:    markRaw(QuickActionsWidget),
  activity_feed:    markRaw(ActivityFeedWidget),
  top_vms:          markRaw(TopVMsWidget),
  storage_overview: markRaw(StorageOverviewWidget),
  backup_status:    markRaw(BackupStatusWidget),
  system_info:      markRaw(SystemInfoWidget),
  network_traffic:  markRaw(NetworkTrafficWidget),
  disk_io:          markRaw(DiskIOWidget),
  node_status_grid:  markRaw(NodeStatusGrid),
  disk_throughput:   markRaw(DiskThroughputWidget),
}

const DEFAULT_LAYOUT = [
  { id: 'w1', type: 'cluster_stats',    colSpan: 1, collapsed: false, config: {} },
  { id: 'w2', type: 'node_status_grid', colSpan: 2, collapsed: false, config: {} },
  { id: 'w3', type: 'network_traffic',  colSpan: 1, collapsed: false, config: {} },
  { id: 'w4', type: 'disk_io',          colSpan: 1, collapsed: false, config: {} },
  { id: 'w10', type: 'disk_throughput', colSpan: 1, collapsed: false, config: {} },
  { id: 'w5', type: 'resource_usage',   colSpan: 1, collapsed: false, config: {} },
  { id: 'w6', type: 'top_vms',          colSpan: 1, collapsed: false, config: {} },
  { id: 'w7', type: 'alerts',           colSpan: 1, collapsed: false, config: {} },
  { id: 'w8', type: 'activity_feed',    colSpan: 1, collapsed: false, config: {} },
  { id: 'w9', type: 'recent_tasks',     colSpan: 1, collapsed: false, config: {} },
]

let _idCounter = 100

export default {
  name: 'Dashboard',
  components: {
    ClusterStatsWidget,
    RecentTasksWidget,
    AlertsWidget,
    ResourceUsageWidget,
    QuickActionsWidget,
    ActivityFeedWidget,
    TopVMsWidget,
    StorageOverviewWidget,
    BackupStatusWidget,
    SystemInfoWidget,
    NetworkTrafficWidget,
    DiskIOWidget,
    NodeStatusGrid,
    DiskThroughputWidget,
    QuickStatsBar,
    AddHostWizard,
    SkeletonLoader,
  },
  setup() {
    const authStore = useAuthStore()
    const router    = useRouter()
    const layout   = ref([])
    const showPicker     = ref(false)
    const showCustomize  = ref(false)
    const showShortcutsHint = ref(false)
    const settingsWidget = ref(null)
    const gridEl   = ref(null)
    const dragging = ref(null)
    const dropTarget = ref(null)
    const lastUpdatedSeconds = ref(0)
    const lastUpdatedAt = ref(null)
    const initialLoading = ref(true)
    const globalRefreshing = ref(false)
    let tickInterval = null
    let resourceInterval = null

    // ── Per-widget state (loading, error, last-updated timestamps) ────────────
    const widgetLoading    = ref(new Set())
    const widgetErrors     = ref(new Map())  // id -> error message
    const widgetTimestamps = ref(new Map())  // id -> Date
    const widgetRefreshing = ref(new Set())

    const widgetHasError  = (id) => widgetErrors.value.has(id)
    const widgetErrorMsg  = (id) => widgetErrors.value.get(id) || 'Unknown error'
    const widgetLastUpdated = (id) => widgetTimestamps.value.get(id) || null

    const widgetAgo = (id) => {
      const ts = widgetTimestamps.value.get(id)
      if (!ts) return ''
      const diff = Math.floor((Date.now() - ts.getTime()) / 1000)
      if (diff < 10) return 'just now'
      if (diff < 60) return `${diff}s ago`
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
      return `${Math.floor(diff / 3600)}h ago`
    }

    const onWidgetError = (id, err) => {
      const msg = err?.message || (typeof err === 'string' ? err : 'Widget failed to load')
      widgetErrors.value = new Map(widgetErrors.value).set(id, msg)
      widgetLoading.value.delete(id)
      widgetLoading.value = new Set(widgetLoading.value)
    }

    const onWidgetLoaded = (id) => {
      widgetErrors.value.delete(id)
      widgetErrors.value = new Map(widgetErrors.value)
      widgetLoading.value.delete(id)
      widgetLoading.value = new Set(widgetLoading.value)
      widgetTimestamps.value = new Map(widgetTimestamps.value).set(id, new Date())
    }

    const refreshWidget = (widget) => {
      // Clear error and mark as loading — the component will re-mount via key trick
      widgetErrors.value.delete(widget.id)
      widgetErrors.value = new Map(widgetErrors.value)
      widgetRefreshing.value.add(widget.id)
      widgetRefreshing.value = new Set(widgetRefreshing.value)
      // Force re-mount by temporarily toggling collapsed
      widget.collapsed = true
      nextTick(() => {
        widget.collapsed = false
        setTimeout(() => {
          widgetRefreshing.value.delete(widget.id)
          widgetRefreshing.value = new Set(widgetRefreshing.value)
          widgetTimestamps.value = new Map(widgetTimestamps.value).set(widget.id, new Date())
        }, 800)
      })
    }

    // ── Global refresh ─────────────────────────────────────────────────────
    const refreshAll = async () => {
      globalRefreshing.value = true
      await Promise.all([
        fetchAlerts(),
        fetchActivity(),
        fetchResources(),
        fetchSummary(),
      ])
      lastUpdatedSeconds.value = 0
      lastUpdatedAt.value = new Date().toLocaleTimeString()
      // Refresh all widgets
      layout.value.forEach(w => {
        if (!w.collapsed) refreshWidget(w)
      })
      globalRefreshing.value = false
    }

    // ── Dashboard Summary (VM counts, node count, storage) ─────────────────
    const dashSummary = ref({})

    const fetchSummary = async () => {
      try {
        const res = await api.dashboard.getSummary()
        dashSummary.value = res.data || {}
      } catch (e) {
        // Non-blocking
      }
    }

    // ── No hosts state ────────────────────────────────────────────────────
    const noHostsConfigured = ref(false)

    const checkHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        const hosts = res.data || []
        noHostsConfigured.value = hosts.length === 0
      } catch (e) {
        // non-blocking
      }
    }

    // ── Welcome Banner ─────────────────────────────────────────────────────────
    const showWelcomeBanner = ref(false)

    const checkWelcomeBanner = () => {
      // Only show when there are no hosts configured
      if (!noHostsConfigured.value) return
      if (localStorage.getItem(WELCOME_BANNER_KEY)) return
      showWelcomeBanner.value = true
    }

    const dismissWelcomeBanner = () => {
      showWelcomeBanner.value = false
      localStorage.setItem(WELCOME_BANNER_KEY, '1')
    }

    const openWizardFromBanner = () => {
      dismissWelcomeBanner()
      showWizard.value = true
    }

    // ── Alerts Summary ─────────────────────────────────────────────────────────
    const alertsSummary = ref(null)

    const alertsBySeverity = computed(() => {
      if (!alertsSummary.value) return { error: 0, warning: 0, info: 0 }
      const alerts = alertsSummary.value.alerts || []
      return {
        error:   alerts.filter(a => a.severity === 'error').length,
        warning: alerts.filter(a => a.severity === 'warning').length,
        info:    alerts.filter(a => a.severity === 'info').length,
      }
    })

    const fetchAlerts = async () => {
      try {
        const res = await api.dashboard.getAlerts()
        alertsSummary.value = res.data
      } catch (e) {
        // Non-blocking
      }
    }

    // ── Recent Activity Feed ───────────────────────────────────────────────────
    const activityFeed    = ref([])
    const activityLoading = ref(false)
    const activityError   = ref(false)
    const activityLastUpdated = ref(null)

    const activityAgoText = computed(() => {
      if (!activityLastUpdated.value) return ''
      const diff = Math.floor((Date.now() - activityLastUpdated.value.getTime()) / 1000)
      if (diff < 10) return 'just now'
      if (diff < 60) return `${diff}s ago`
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
      return `${Math.floor(diff / 3600)}h ago`
    })

    const fetchActivity = async () => {
      activityLoading.value = true
      activityError.value = false
      try {
        const res = await api.dashboard.getRecentActivity({ limit: 10 })
        activityFeed.value = Array.isArray(res.data) ? res.data : []
        activityLastUpdated.value = new Date()
      } catch (e) {
        activityError.value = true
      } finally {
        activityLoading.value = false
      }
    }

    const formatRelTime = (isoStr) => {
      if (!isoStr) return ''
      const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000)
      if (diff < 10) return 'just now'
      if (diff < 60) return `${diff}s ago`
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
      return `${Math.floor(diff / 86400)}d ago`
    }

    // ── Resource Trending ──────────────────────────────────────────────────────
    const resourceStats = ref(null)
    const prevResourceStats = ref(null)

    const cpuUsedPct = computed(() => {
      if (!resourceStats.value) return 0
      const { used_cpu_cores, total_cpu_cores } = resourceStats.value
      if (!total_cpu_cores) return 0
      return Math.round((used_cpu_cores / total_cpu_cores) * 100)
    })

    const ramUsedPct = computed(() => {
      if (!resourceStats.value) return 0
      const { used_memory_gb, total_memory_gb } = resourceStats.value
      if (!total_memory_gb) return 0
      return Math.round((used_memory_gb / total_memory_gb) * 100)
    })

    const diskUsedPct = computed(() => {
      if (!resourceStats.value) return 0
      const { used_disk_gb, total_disk_gb } = resourceStats.value
      if (!total_disk_gb) return 0
      return Math.round((used_disk_gb / total_disk_gb) * 100)
    })

    const prevCpuPct = computed(() => {
      if (!prevResourceStats.value) return null
      const { used_cpu_cores, total_cpu_cores } = prevResourceStats.value
      if (!total_cpu_cores) return null
      return Math.round((used_cpu_cores / total_cpu_cores) * 100)
    })

    const prevRamPct = computed(() => {
      if (!prevResourceStats.value) return null
      const { used_memory_gb, total_memory_gb } = prevResourceStats.value
      if (!total_memory_gb) return null
      return Math.round((used_memory_gb / total_memory_gb) * 100)
    })

    const prevDiskPct = computed(() => {
      if (!prevResourceStats.value) return null
      const { used_disk_gb, total_disk_gb } = prevResourceStats.value
      if (!total_disk_gb) return null
      return Math.round((used_disk_gb / total_disk_gb) * 100)
    })

    const calcTrend = (curr, prev) => {
      if (prev === null || curr === null) return null
      const delta = curr - prev
      if (delta > 1) return 'up'
      if (delta < -1) return 'down'
      return 'stable'
    }

    const cpuTrend  = computed(() => calcTrend(cpuUsedPct.value, prevCpuPct.value))
    const ramTrend  = computed(() => calcTrend(ramUsedPct.value, prevRamPct.value))
    const diskTrend = computed(() => calcTrend(diskUsedPct.value, prevDiskPct.value))

    const trendArrow = (t) => {
      if (t === 'up') return '↑'
      if (t === 'down') return '↓'
      if (t === 'stable') return '→'
      return ''
    }

    const trendClass = (t) => {
      if (t === 'up') return 'trend-up'
      if (t === 'down') return 'trend-down'
      if (t === 'stable') return 'trend-stable'
      return ''
    }

    const trendTitle = (t) => {
      if (t === 'up') return 'Increasing since last refresh'
      if (t === 'down') return 'Decreasing since last refresh'
      if (t === 'stable') return 'Stable since last refresh'
      return ''
    }

    const fetchResources = async () => {
      try {
        const res = await api.dashboard.getResources()
        prevResourceStats.value = resourceStats.value
        resourceStats.value = res.data
        lastUpdatedAt.value = new Date().toLocaleTimeString()
      } catch (e) {
        // Non-blocking
      }
    }

    // ── Quick Search ───────────────────────────────────────────────────────────
    const searchQuery    = ref('')
    const searchResults  = ref([])
    const searchLoading  = ref(false)
    const searchFocused  = ref(false)
    const searchNavIndex = ref(-1)
    const searchInputEl  = ref(null)
    const searchWrapEl   = ref(null)
    let searchTimer = null

    const onSearchInput = () => {
      searchNavIndex.value = -1
      clearTimeout(searchTimer)
      if (searchQuery.value.length < 2) {
        searchResults.value = []
        return
      }
      searchTimer = setTimeout(runSearch, 300)
    }

    const runSearch = async () => {
      if (searchQuery.value.length < 2) return
      searchLoading.value = true
      const q = searchQuery.value.toLowerCase()
      const results = []

      try {
        const vmRes = await api.pveVm.search({ q, limit: 10 }).catch(() => null)
        if (vmRes && Array.isArray(vmRes.data)) {
          for (const vm of vmRes.data) {
            results.push({
              type: 'vm',
              id: `vm-${vm.host_id}-${vm.vmid}`,
              name: vm.name || `VM ${vm.vmid}`,
              meta: `${vm.node} · ID ${vm.vmid}`,
              status: vm.status,
              _nav: { type: 'vm', hostId: vm.host_id, node: vm.node, vmid: vm.vmid },
            })
          }
        }
      } catch (e) { /* search may not be available */ }

      try {
        const hostRes = await api.proxmox.listHosts().catch(() => null)
        if (hostRes && Array.isArray(hostRes.data)) {
          for (const host of hostRes.data) {
            if (host.name && host.name.toLowerCase().includes(q)) {
              results.push({
                type: 'host',
                id: `host-${host.id}`,
                name: host.name,
                meta: host.api_url || '',
                status: host.is_active ? 'online' : 'offline',
                _nav: { type: 'host', hostId: host.id },
              })
            }
            if (Array.isArray(host.nodes)) {
              for (const node of host.nodes) {
                const nodeName = node.node_name || node.name || ''
                if (nodeName.toLowerCase().includes(q)) {
                  results.push({
                    type: 'node',
                    id: `node-${host.id}-${nodeName}`,
                    name: nodeName,
                    meta: host.name,
                    status: node.status,
                    _nav: { type: 'node', hostId: host.id, node: nodeName },
                  })
                }
              }
            }
          }
        }
      } catch (e) { /* non-blocking */ }

      searchResults.value = results.slice(0, 12)
      searchLoading.value = false
    }

    const navigateToResult = (item) => {
      closeSearch()
      const n = item._nav
      if (!n) return
      if (n.type === 'vm') {
        router.push(`/proxmox/${n.hostId}/nodes/${n.node}/vms/${n.vmid}`)
      } else if (n.type === 'host') {
        router.push(`/proxmox/${n.hostId}/cluster`)
      } else if (n.type === 'node') {
        router.push(`/proxmox/${n.hostId}/nodes/${n.node}`)
      }
    }

    const closeSearch = () => {
      searchFocused.value = false
      searchResults.value = []
      searchNavIndex.value = -1
    }

    const clearSearch = () => {
      searchQuery.value = ''
      searchResults.value = []
      searchNavIndex.value = -1
      nextTick(() => searchInputEl.value?.focus())
    }

    const searchNavDown = () => {
      if (searchResults.value.length === 0) return
      searchNavIndex.value = Math.min(searchNavIndex.value + 1, searchResults.value.length - 1)
    }

    const searchNavUp = () => {
      searchNavIndex.value = Math.max(searchNavIndex.value - 1, 0)
    }

    const searchNavSelect = () => {
      if (searchNavIndex.value >= 0 && searchResults.value[searchNavIndex.value]) {
        navigateToResult(searchResults.value[searchNavIndex.value])
      }
    }

    const onDocClick = (e) => {
      if (searchWrapEl.value && !searchWrapEl.value.contains(e.target)) {
        closeSearch()
      }
    }

    const onDocKeydown = (e) => {
      if (e.key === '/' && document.activeElement !== searchInputEl.value &&
          !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        e.preventDefault()
        searchInputEl.value?.focus()
        searchFocused.value = true
      }
    }

    // ── Widget visibility (localStorage) ──────────────────────────────────────
    const hiddenTypes = ref(new Set())

    const loadVisibility = () => {
      try {
        const stored = localStorage.getItem(VISIBILITY_KEY)
        if (stored) hiddenTypes.value = new Set(JSON.parse(stored))
      } catch (e) {}
    }

    const saveVisibility = () => {
      try {
        localStorage.setItem(VISIBILITY_KEY, JSON.stringify([...hiddenTypes.value]))
      } catch (e) {}
    }

    const isWidgetVisible = (type) => !hiddenTypes.value.has(type)

    const toggleWidgetVisibility = (type) => {
      if (hiddenTypes.value.has(type)) {
        hiddenTypes.value.delete(type)
      } else {
        hiddenTypes.value.add(type)
      }
      hiddenTypes.value = new Set(hiddenTypes.value)
      saveVisibility()
    }

    const visibleLayout = computed(() =>
      layout.value.filter(w => isWidgetVisible(w.type))
    )

    // Live drag-preview: reorder tiles in real-time as cursor moves
    const displayLayout = computed(() => {
      if (!dragging.value || !dropTarget.value || dragging.value.id === dropTarget.value.id) {
        return visibleLayout.value
      }
      const arr = visibleLayout.value.filter(w => w.id !== dragging.value.id)
      const toIdx = arr.findIndex(w => w.id === dropTarget.value.id)
      if (toIdx === -1) return visibleLayout.value
      arr.splice(toIdx, 0, dragging.value)
      return arr
    })

    // ── Onboarding ────────────────────────────────────────────────────────────
    const ONBOARD_SKIP_KEY = 'depl0y_onboarding_skip'
    const showOnboarding = ref(false)
    const showWizard = ref(false)
    const firstHostAdded = ref(false)

    const openWizard = () => { showWizard.value = true }

    const onFirstHostAdded = () => {
      firstHostAdded.value = true
      noHostsConfigured.value = false
    }

    const skipOnboarding = () => {
      localStorage.setItem(ONBOARD_SKIP_KEY, '1')
      showOnboarding.value = false
    }

    const checkOnboarding = async () => {
      if (!authStore.isAdmin) return
      if (localStorage.getItem(ONBOARD_SKIP_KEY)) return
      try {
        const res = await api.proxmox.listHosts()
        const hosts = res.data || []
        if (hosts.length === 0) {
          showOnboarding.value = true
        }
      } catch (e) {
        // Non-blocking
      }
    }

    // ── Persistence ──────────────────────────────────────────────────────────
    const saveLayout = () => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(layout.value.map(w => ({
          id: w.id, type: w.type, colSpan: w.colSpan, collapsed: w.collapsed, config: w.config || {}
        }))))
      } catch (e) {}
    }

    const loadLayout = () => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
          const parsed = JSON.parse(stored)
          const loaded = parsed.map(w => ({ ...w, config: w.config || {} }))
          // Merge in any new widget types from DEFAULT_LAYOUT that are missing
          const existingTypes = new Set(loaded.map(w => w.type))
          for (const def of DEFAULT_LAYOUT) {
            if (!existingTypes.has(def.type)) {
              loaded.push({ ...def })
            }
          }
          layout.value = loaded
          return
        }
      } catch (e) {}
      layout.value = DEFAULT_LAYOUT.map(w => ({ ...w }))
    }

    const resetLayout = () => {
      layout.value = DEFAULT_LAYOUT.map(w => ({ ...w }))
      saveLayout()
    }

    // ── Widget helpers ────────────────────────────────────────────────────────
    const widgetMeta = (type) => WIDGET_META[type] || { label: type, icon: '□' }
    const widgetComponent = (type) => WIDGET_COMPONENTS[type] || null
    const allWidgetTypes = computed(() => Object.values(WIDGET_META))
    const isWidgetAdded = (type) => layout.value.some(w => w.type === type)
    const widgetStyle = (widget) => ({ gridColumn: `span ${widget.colSpan || 1}` })

    // ── Add / remove ─────────────────────────────────────────────────────────
    const addWidget = (type) => {
      const id = 'w' + (++_idCounter)
      layout.value.push({ id, type, colSpan: 1, collapsed: false, config: {} })
      saveLayout()
      showPicker.value = false
    }

    const removeWidget = (widget) => {
      const idx = layout.value.findIndex(w => w.id === widget.id)
      if (idx !== -1) layout.value.splice(idx, 1)
      saveLayout()
    }

    const toggleCollapse = (widget) => {
      widget.collapsed = !widget.collapsed
      saveLayout()
    }

    const openSettings = (widget) => {
      settingsWidget.value = widget
    }

    // ── Drag-to-reorder (mouse) ───────────────────────────────────────────────
    let dragState = null

    const startDrag = (e, widget) => {
      if (e.button !== 0) return
      e.preventDefault()
      dragState = { widget, startX: e.clientX, startY: e.clientY, moved: false }
      dragging.value = widget
      dropTarget.value = null
      document.body.style.cursor = 'grabbing'

      const onMove = (ev) => {
        if (!dragState) return
        const dx = Math.abs(ev.clientX - dragState.startX)
        const dy = Math.abs(ev.clientY - dragState.startY)
        if (dx > 5 || dy > 5) dragState.moved = true
        if (!dragState.moved) return
        const target = getWidgetAtPoint(ev.clientX, ev.clientY, widget.id)
        dropTarget.value = target || null
      }

      const onUp = () => {
        if (dragState && dragState.moved && dropTarget.value && dropTarget.value.id !== widget.id) {
          moveWidget(widget.id, dropTarget.value.id)
        }
        dragState = null
        dragging.value = null
        dropTarget.value = null
        document.body.style.cursor = ''
        saveLayout()
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
      }

      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
    }

    const startDragTouch = (e, widget) => {
      const touch = e.touches[0]
      dragState = { widget, startX: touch.clientX, startY: touch.clientY, moved: false }
      dragging.value = widget
      dropTarget.value = null

      const onMove = (ev) => {
        if (!dragState) return
        const t = ev.touches[0]
        dragState.moved = true
        const target = getWidgetAtPoint(t.clientX, t.clientY, widget.id)
        dropTarget.value = target || null
      }

      const onEnd = () => {
        if (dragState && dragState.moved && dropTarget.value && dropTarget.value.id !== widget.id) {
          moveWidget(widget.id, dropTarget.value.id)
        }
        dragState = null
        dragging.value = null
        dropTarget.value = null
        saveLayout()
        window.removeEventListener('touchmove', onMove)
        window.removeEventListener('touchend', onEnd)
      }

      window.addEventListener('touchmove', onMove, { passive: true })
      window.addEventListener('touchend', onEnd)
    }

    const getWidgetAtPoint = (x, y, excludeId) => {
      if (!gridEl.value) return null
      const el = gridEl.value.$el ?? gridEl.value
      const cards = el.querySelectorAll('.widget-card')
      for (const card of cards) {
        if (card.dataset.widgetId === excludeId) continue
        const rect = card.getBoundingClientRect()
        if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
          const id = card.dataset.widgetId
          return layout.value.find(w => w.id === id) || null
        }
      }
      return null
    }

    const moveWidget = (fromId, toId) => {
      const arr = [...layout.value]
      const fromIdx = arr.findIndex(w => w.id === fromId)
      if (fromIdx === -1) return
      const [item] = arr.splice(fromIdx, 1)
      const toIdx = arr.findIndex(w => w.id === toId)
      if (toIdx === -1) { arr.push(item); layout.value = arr; return }
      arr.splice(toIdx, 0, item)
      layout.value = arr
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────
    onMounted(async () => {
      loadLayout()
      loadVisibility()
      tickInterval = setInterval(() => lastUpdatedSeconds.value++, 1000)

      // Kick off all initial fetches
      await Promise.all([
        fetchAlerts(),
        fetchActivity(),
        fetchResources(),
        fetchSummary(),
        checkHosts(),
      ])
      initialLoading.value = false
      lastUpdatedAt.value = new Date().toLocaleTimeString()

      // Show welcome/onboarding only after host check resolves
      checkWelcomeBanner()
      checkOnboarding()

      // Refresh resources every 30s to track trends
      resourceInterval = setInterval(() => {
        fetchResources()
        lastUpdatedSeconds.value = 0
      }, 30000)

      document.addEventListener('keydown', onDocKeydown)
      document.addEventListener('mousedown', onDocClick)
    })

    onUnmounted(() => {
      clearInterval(tickInterval)
      clearInterval(resourceInterval)
      document.removeEventListener('keydown', onDocKeydown)
      document.removeEventListener('mousedown', onDocClick)
    })

    return {
      layout,
      visibleLayout,
      displayLayout,
      showPicker,
      showCustomize,
      showShortcutsHint,
      settingsWidget,
      gridEl,
      dragging,
      dropTarget,
      lastUpdatedSeconds,
      lastUpdatedAt,
      initialLoading,
      globalRefreshing,
      allWidgetTypes,
      widgetMeta,
      widgetComponent,
      widgetStyle,
      isWidgetAdded,
      isWidgetVisible,
      toggleWidgetVisibility,
      addWidget,
      removeWidget,
      toggleCollapse,
      openSettings,
      saveLayout,
      resetLayout,
      startDrag,
      startDragTouch,
      // Per-widget state
      widgetLoading,
      widgetRefreshing,
      widgetHasError,
      widgetErrorMsg,
      widgetLastUpdated,
      widgetAgo,
      onWidgetError,
      onWidgetLoaded,
      refreshWidget,
      refreshAll,
      // No hosts
      noHostsConfigured,
      // Onboarding
      showOnboarding,
      showWizard,
      firstHostAdded,
      openWizard,
      onFirstHostAdded,
      skipOnboarding,
      // Welcome banner
      showWelcomeBanner,
      dismissWelcomeBanner,
      openWizardFromBanner,
      // Dashboard summary (VM/node/storage counts)
      dashSummary,
      fetchSummary,
      // Alerts summary
      alertsSummary,
      alertsBySeverity,
      // Activity feed
      activityFeed,
      activityLoading,
      activityError,
      activityLastUpdated,
      activityAgoText,
      fetchActivity,
      formatRelTime,
      // Resource trending
      resourceStats,
      cpuUsedPct,
      ramUsedPct,
      diskUsedPct,
      cpuTrend,
      ramTrend,
      diskTrend,
      trendArrow,
      trendClass,
      trendTitle,
      // Quick search
      searchQuery,
      searchResults,
      searchLoading,
      searchFocused,
      searchNavIndex,
      searchInputEl,
      searchWrapEl,
      onSearchInput,
      navigateToResult,
      closeSearch,
      clearSearch,
      searchNavDown,
      searchNavUp,
      searchNavSelect,
    }
  }
}
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* ── Welcome Banner ──────────────────────────────────────────────────────── */
.welcome-banner {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(99, 102, 241, 0.08) 100%);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 0.5rem;
  overflow: hidden;
}

.welcome-banner-inner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.8rem 1rem;
  flex-wrap: wrap;
}

.welcome-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(59, 130, 246, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-color);
  flex-shrink: 0;
}

.welcome-content {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
  min-width: 0;
}

.welcome-title {
  font-weight: 700;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.welcome-text {
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.welcome-action {
  flex-shrink: 0;
}

.welcome-dismiss {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.2rem;
  border-radius: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.12s;
}

.welcome-dismiss:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

.banner-fade-enter-active,
.banner-fade-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.banner-fade-enter-from,
.banner-fade-leave-to {
  opacity: 0;
  max-height: 0;
  margin-bottom: 0;
}

.banner-fade-enter-to,
.banner-fade-leave-from {
  opacity: 1;
  max-height: 100px;
}

/* ── No Hosts Configured ─────────────────────────────────────────────────── */
.no-hosts-state {
  border: 1.5px dashed var(--border-color);
  border-radius: 0.75rem;
  background: var(--surface);
  overflow: hidden;
}

.no-hosts-inner {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  flex-wrap: wrap;
}

.no-hosts-icon {
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.07);
  border-radius: 0.75rem;
  color: var(--primary-color);
  flex-shrink: 0;
}

.no-hosts-content {
  flex: 1;
  min-width: 0;
}

.no-hosts-title {
  font-weight: 700;
  font-size: 1rem;
  color: var(--text-primary);
  margin: 0 0 0.25rem;
}

.no-hosts-sub {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin: 0;
}

/* ── Alerts Summary Bar ───────────────────────────────────────────────────── */
.alerts-summary-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.65rem 1rem;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.15s;
  flex-wrap: wrap;
}

.alerts-summary-bar:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.4);
}

.asb-left {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.asb-icon {
  color: #ef4444;
  flex-shrink: 0;
}

.asb-title {
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--text-primary);
}

.asb-breakdown {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: 1;
  flex-wrap: wrap;
}

.asb-chip {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
}

.asb-chip-error {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.asb-chip-warn {
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
}

.asb-chip-info {
  background: rgba(59, 130, 246, 0.1);
  color: var(--primary-color);
}

.asb-right {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  color: var(--primary-color);
  font-weight: 500;
  margin-left: auto;
}

.alerts-slide-enter-active,
.alerts-slide-leave-active {
  transition: all 0.22s ease;
  overflow: hidden;
}

.alerts-slide-enter-from,
.alerts-slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.alerts-slide-enter-to,
.alerts-slide-leave-from {
  opacity: 1;
  max-height: 80px;
}

/* ── Resource Trending Row ───────────────────────────────────────────────── */
.resource-trending-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.rt-card {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.4rem 0.75rem;
  font-size: 0.8rem;
  flex-shrink: 0;
}

.rt-label {
  color: var(--text-secondary);
  font-weight: 500;
}

.rt-value {
  color: var(--text-primary);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.rt-arrow {
  font-size: 1rem;
  font-weight: 700;
  line-height: 1;
}

.trend-up    { color: #ef4444; }
.trend-down  { color: #22c55e; }
.trend-stable { color: var(--text-secondary); }

/* ── Quick Search Bar ────────────────────────────────────────────────────── */
.quick-search-wrap {
  position: relative;
  z-index: 200;
}

.quick-search-input-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.45rem 0.75rem;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.quick-search-input-row:focus-within {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.qs-icon {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.quick-search-input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  font-size: 0.875rem;
  color: var(--text-primary);
  min-width: 0;
}

.quick-search-input::placeholder {
  color: var(--text-secondary);
}

.qs-kbd {
  font-size: 0.7rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.25rem;
  padding: 0.1rem 0.35rem;
  color: var(--text-secondary);
  font-family: monospace;
  flex-shrink: 0;
}

.qs-clear {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.1rem;
  border-radius: 0.2rem;
  display: flex;
  align-items: center;
  transition: color 0.12s;
  flex-shrink: 0;
}

.qs-clear:hover { color: var(--text-primary); }

.qs-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Dropdown */
.qs-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.14);
  overflow: hidden;
  max-height: 320px;
  overflow-y: auto;
}

.qs-no-results {
  padding: 1rem;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.82rem;
}

.qs-result-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.9rem;
  cursor: pointer;
  transition: background 0.12s;
}

.qs-result-item:hover,
.qs-result-active {
  background: rgba(59, 130, 246, 0.06);
}

.qs-result-badge {
  font-size: 0.62rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
  flex-shrink: 0;
}

.badge-type-vm   { background: rgba(99, 102, 241, 0.12); color: #6366f1; }
.badge-type-node { background: rgba(16, 185, 129, 0.12); color: #10b981; }
.badge-type-host { background: rgba(245, 158, 11, 0.12); color: #f59e0b; }

.qs-result-name {
  font-weight: 500;
  font-size: 0.85rem;
  color: var(--text-primary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.qs-result-meta {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}

.qs-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-green { background: #22c55e; }
.dot-grey  { background: var(--text-secondary); opacity: 0.5; }

.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ── Activity Feed Panel ─────────────────────────────────────────────────── */
.activity-feed-panel {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
}

.afp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--background);
}

.afp-title {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-primary);
}

.afp-header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.afp-ts {
  font-size: 0.68rem;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.afp-refresh {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.15rem;
  border-radius: 0.2rem;
  display: flex;
  align-items: center;
  transition: color 0.12s;
}

.afp-refresh:hover { color: var(--primary-color); }
.afp-refresh:disabled { opacity: 0.4; cursor: not-allowed; }

.afp-viewall {
  font-size: 0.72rem;
  color: var(--primary-color);
  text-decoration: none;
  font-weight: 500;
  transition: opacity 0.12s;
}

.afp-viewall:hover { opacity: 0.75; }

.afp-loading {
  padding: 0.5rem 0.85rem;
}

.afp-error-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 1.25rem;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.afp-empty {
  padding: 1.25rem;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.82rem;
}

.afp-list {
  display: flex;
  flex-direction: column;
}

.afp-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0.85rem;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.12s;
  font-size: 0.8rem;
}

.afp-item:last-child { border-bottom: none; }
.afp-item:hover { background: rgba(59, 130, 246, 0.04); }

.afp-icon {
  font-size: 1rem;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

.afp-body {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.afp-action {
  color: var(--text-primary);
  font-weight: 500;
}

.afp-resource {
  color: var(--text-secondary);
}

.afp-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.05rem;
  flex-shrink: 0;
}

.afp-user {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-primary);
}

.afp-time {
  font-size: 0.68rem;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* ── Header ───────────────────────────────────────────────────────────────── */
.dash-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.dash-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.dash-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.last-updated {
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.btn-icon {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  color: var(--text-primary);
  font-size: 1.1rem;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
  padding: 0;
  line-height: 1;
}

.btn-icon:hover {
  background: var(--primary-color);
  color: #fff;
  border-color: var(--primary-color);
}

.btn-icon--spinning svg {
  animation: spin 0.8s linear infinite;
}

/* ── Keyboard shortcuts hint panel ─────────────────────────────────────── */
.shortcuts-hint-panel {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.shp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.25rem;
}

.shp-title {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-primary);
}

.shp-close {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.15rem;
  border-radius: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.12s;
}

.shp-close:hover { color: var(--text-primary); }

.shp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.35rem 1.5rem;
}

.shp-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.shp-row kbd {
  font-size: 0.68rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.2rem;
  padding: 0.05rem 0.35rem;
  color: var(--text-primary);
  font-family: monospace;
  flex-shrink: 0;
}

.shp-hint {
  font-size: 0.7rem;
  color: var(--text-secondary);
  margin: 0.25rem 0 0;
}

.shp-hint kbd {
  font-size: 0.65rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.2rem;
  padding: 0.05rem 0.3rem;
  color: var(--text-primary);
  font-family: monospace;
}

/* ── Customize Panel ──────────────────────────────────────────────────────── */
.customize-panel {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.customize-header {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.customize-title {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-primary);
}

.customize-hint {
  font-size: 0.72rem;
  color: var(--text-secondary);
}

.customize-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.toggle-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: pointer;
  background: var(--background);
  transition: all 0.15s;
  user-select: none;
  -webkit-user-select: none;
}

.toggle-item:hover { border-color: var(--primary-color); }

.toggle-active {
  border-color: var(--primary-color);
  background: rgba(59, 130, 246, 0.06);
}

.toggle-check {
  width: 0.9rem;
  height: 0.9rem;
  accent-color: var(--primary-color);
  cursor: pointer;
}

.toggle-icon { font-size: 0.85rem; line-height: 1; }

.toggle-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}

/* Panel slide transition */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: all 0.22s ease;
  overflow: hidden;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
  max-height: 0;
}

.panel-slide-enter-to,
.panel-slide-leave-from {
  opacity: 1;
  transform: translateY(0);
  max-height: 400px;
}

/* ── Widget Grid ──────────────────────────────────────────────────────────── */
.widget-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  align-items: start;
}

.widget-card {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
  transition: box-shadow 0.2s, transform 0.2s;
}

.widget-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.widget-card--error {
  border-color: rgba(239, 68, 68, 0.35);
}

/* FLIP animation: tiles slide smoothly to their new grid positions while dragging */
.widget-reorder-move {
  transition: transform 0.2s ease;
}

.widget-dragging {
  opacity: 0.45;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  z-index: 100;
  pointer-events: none;
  outline: 2px dashed var(--primary-color, #6366f1);
  outline-offset: -2px;
}

.widget-drop-target {
  border: 2px dashed var(--primary-color, #6366f1);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
  transform: scale(1.01);
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

/* ── Widget Title Bar ─────────────────────────────────────────────────────── */
.widget-bar {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.65rem;
  background: var(--background);
  border-bottom: 1px solid var(--border-color);
  cursor: grab;
  user-select: none;
  -webkit-user-select: none;
}

.widget-bar:active { cursor: grabbing; }

.widget-grip {
  font-size: 0.9rem;
  color: var(--text-secondary);
  opacity: 0.5;
  letter-spacing: -1px;
  flex-shrink: 0;
}

.widget-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Skeleton title placeholder */
.widget-title-skel {
  height: 12px;
  width: 100px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--border-color) 25%, var(--background) 50%, var(--border-color) 75%);
  background-size: 200% auto;
  animation: shimmer 1.5s linear infinite;
  flex: 1;
}

@keyframes shimmer {
  0%   { background-position: 200% center; }
  100% { background-position: -200% center; }
}

.widget-controls {
  display: flex;
  align-items: center;
  gap: 0.1rem;
  flex-shrink: 0;
}

/* Per-widget timestamp */
.widget-ts {
  font-size: 0.6rem;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  padding: 0 0.2rem;
  white-space: nowrap;
}

.wc-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 0.85rem;
  width: 1.4rem;
  height: 1.4rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.25rem;
  cursor: pointer;
  transition: all 0.12s;
  padding: 0;
}

.wc-btn:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

.wc-remove:hover {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.wc-spinning svg {
  animation: spin 0.8s linear infinite;
}

/* ── Widget Body ─────────────────────────────────────────────────────── */
.widget-body { padding: 0.75rem; }

.widget-error-body { padding: 0; }

.widget-error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 1.5rem 1rem;
  text-align: center;
}

.widget-error-msg {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin: 0;
  max-width: 200px;
}

/* ── Empty State ─────────────────────────────────────────────────────────── */
.dash-empty {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.dash-empty p { margin-bottom: 0.75rem; }

/* ── Modal ───────────────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.modal-box {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.22);
  width: 100%;
  max-height: 80vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.picker-modal  { max-width: 560px; }
.settings-modal { max-width: 420px; }

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.2rem;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.15rem 0.3rem;
  border-radius: 0.25rem;
  transition: all 0.12s;
}

.modal-close:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

/* ── Widget Picker ───────────────────────────────────────────────────────── */
.picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.5rem;
  padding: 1rem 1.25rem;
}

.picker-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 0.75rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background: var(--background);
  cursor: pointer;
  transition: all 0.15s;
  position: relative;
}

.picker-item:hover:not(:disabled) {
  border-color: var(--primary-color);
  background: rgba(var(--primary-color-rgb, 59, 130, 246), 0.05);
}

.picker-item:disabled { opacity: 0.5; cursor: not-allowed; }

.picker-icon  { font-size: 1.5rem; }
.picker-label { font-size: 0.78rem; font-weight: 500; color: var(--text-primary); text-align: center; }
.picker-added {
  font-size: 0.6rem; font-weight: 700; text-transform: uppercase;
  background: rgba(34, 197, 94, 0.15); color: #22c55e;
  padding: 0.1rem 0.35rem; border-radius: 9999px;
}

/* ── Widget Settings ────────────────────────────────────────────────────── */
.settings-body {
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.settings-hint {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin: 0;
  font-family: monospace;
}

.settings-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.modal-footer {
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
}

/* ── Modal transitions ───────────────────────────────────────────────────── */
.modal-fade-enter-active,
.modal-fade-leave-active { transition: opacity 0.2s ease; }
.modal-fade-enter-from,
.modal-fade-leave-to { opacity: 0; }

/* ── Spinning animation ─────────────────────────────────────────────────── */
.spinning {
  animation: spin 0.8s linear infinite;
}

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 1024px) {
  .widget-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 640px) {
  .widget-grid { grid-template-columns: 1fr; }
  .widget-card { grid-column: span 1 !important; }
  .picker-grid { grid-template-columns: repeat(2, 1fr); }
  .customize-grid { flex-direction: column; }
  .resource-trending-row { flex-direction: column; }
  .rt-card { width: 100%; }
  .shp-grid { grid-template-columns: 1fr; }
}

/* ── Onboarding screen ──────────────────────────────────────────────────── */
.onboarding-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 70vh;
  padding: 2rem 1rem;
  gap: 2rem;
}

.onboard-hero {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.onboard-logo {
  width: 80px;
  height: 80px;
  border-radius: 1.25rem;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.onboard-title {
  font-size: 2rem;
  font-weight: 800;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.02em;
}

.onboard-sub {
  font-size: 1rem;
  color: var(--text-secondary);
  margin: 0;
  max-width: 420px;
}

/* Checklist */
.onboard-checklist {
  display: flex;
  flex-direction: column;
  gap: 0;
  width: 100%;
  max-width: 540px;
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  overflow: hidden;
  background: var(--surface);
}

.checklist-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s;
  position: relative;
}

.checklist-item:last-child { border-bottom: none; }

.checklist-done   { background: var(--surface); }
.checklist-active { background: rgba(59, 130, 246, 0.04); }
.checklist-locked { background: var(--surface); opacity: 0.55; }

.checklist-active::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--primary-color);
  border-radius: 0 2px 2px 0;
}

.check-icon {
  width: 32px; height: 32px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  font-size: 0.75rem; font-weight: 700;
}

.check-complete { background: rgba(34, 197, 94, 0.12); color: #22c55e; }
.check-complete svg { stroke: #22c55e; }
.check-pending  { background: rgba(59, 130, 246, 0.1); color: var(--primary-color); border: 2px solid var(--primary-color); }
.check-num      { font-size: 0.8rem; font-weight: 700; color: var(--primary-color); }
.check-locked   { background: var(--background); border: 2px solid var(--border-color); color: var(--text-secondary); }
.check-locked svg { stroke: var(--text-secondary); }

.check-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.check-label { font-weight: 600; font-size: 0.9rem; color: var(--text-primary); }
.check-desc  { font-size: 0.78rem; color: var(--text-secondary); }
.check-done-text { color: #22c55e; }

/* Buttons */
.btn-sm { padding: 0.35rem 0.85rem; font-size: 0.8rem; }

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  padding: 0.5rem 1.1rem;
  transition: all 0.15s;
  text-decoration: none;
  white-space: nowrap;
}

.btn-primary { background: var(--primary-color); color: #fff; border-color: var(--primary-color); }
.btn-primary:hover { opacity: 0.9; }

.btn-outline { background: transparent; color: var(--text-primary); border-color: var(--border-color); }
.btn-outline:hover { border-color: var(--primary-color); color: var(--primary-color); }

.onboard-skip { margin: 0; }

.skip-link {
  font-size: 0.8rem;
  color: var(--text-secondary);
  text-decoration: none;
  transition: color 0.15s;
}

.skip-link:hover { color: var(--text-primary); text-decoration: underline; }

.onboard-fade-enter-active,
.onboard-fade-leave-active { transition: opacity 0.3s ease; }
.onboard-fade-enter-from,
.onboard-fade-leave-to { opacity: 0; }

/* ── Resource Summary Bar ─────────────────────────────────────────────── */
.resource-summary-bar {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.6rem;
}

@media (max-width: 1100px) {
  .resource-summary-bar { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 640px) {
  .resource-summary-bar { grid-template-columns: repeat(2, 1fr); }
}

.rsb-card {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.7rem 0.9rem;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.1s;
}

.rsb-card-link {
  cursor: pointer;
}

.rsb-card-link:hover {
  border-color: var(--accent-color);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
  transform: translateY(-1px);
}

.rsb-card-link:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
}

.rsb-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.08);
}

.rsb-icon {
  width: 32px;
  height: 32px;
  border-radius: 0.375rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.rsb-icon-vm      { background: rgba(99, 102, 241, 0.12); color: #818cf8; }
.rsb-icon-node    { background: rgba(16, 185, 129, 0.12); color: #34d399; }
.rsb-icon-storage { background: rgba(245, 158, 11, 0.12); color: #fbbf24; }
.rsb-icon-cpu     { background: rgba(239, 68, 68, 0.1);   color: #f87171; }
.rsb-icon-ram     { background: rgba(59, 130, 246, 0.1);  color: #60a5fa; }

.rsb-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.rsb-label {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rsb-value-row {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.rsb-big {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.rsb-big-warn { color: #f87171; }

.rsb-sub {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.rsb-chip {
  font-size: 0.62rem;
  font-weight: 600;
  padding: 0.1rem 0.35rem;
  border-radius: 9999px;
  white-space: nowrap;
}

.rsb-chip-green { background: rgba(34, 197, 94, 0.12); color: #22c55e; }
.rsb-chip-gray  { background: rgba(148, 163, 184, 0.12); color: #94a3b8; }

/* Skeleton */
.rsb-card-skel {
  pointer-events: none;
}

.rsb-skel-icon {
  width: 32px;
  height: 32px;
  border-radius: 0.375rem;
  background: linear-gradient(90deg, var(--border-color) 25%, var(--background) 50%, var(--border-color) 75%);
  background-size: 200% auto;
  animation: shimmer 1.5s linear infinite;
  flex-shrink: 0;
}

.rsb-skel-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.rsb-skel-label {
  height: 8px;
  width: 60%;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--border-color) 25%, var(--background) 50%, var(--border-color) 75%);
  background-size: 200% auto;
  animation: shimmer 1.5s linear infinite;
}

.rsb-skel-value {
  height: 16px;
  width: 80%;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--border-color) 25%, var(--background) 50%, var(--border-color) 75%);
  background-size: 200% auto;
  animation: shimmer 1.5s linear infinite;
}

/* ── Quick Actions Panel ──────────────────────────────────────────────── */
.quick-actions-panel {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.6rem 0.85rem;
  flex-wrap: wrap;
}

.qap-title {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
  flex-shrink: 0;
}

.qap-buttons {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  flex: 1;
}

.qap-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.7rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.qap-btn:hover {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #fff;
}

.qap-btn svg {
  flex-shrink: 0;
  transition: stroke 0.15s;
}
</style>
