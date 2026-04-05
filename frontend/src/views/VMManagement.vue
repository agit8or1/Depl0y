<template>
  <div class="vm-management-page">
    <div class="page-header">
      <h2>VM Management</h2>
      <p class="text-muted">Updates, security scanning, monitoring, and AI tuning for your virtual machines</p>
    </div>

    <!-- Tab Nav -->
    <div class="tab-nav">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-btn', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        {{ tab.label }}
        <span v-if="tab.badge" class="tab-badge">{{ tab.badge }}</span>
      </button>
    </div>

    <!-- ── FLEET TAB ── -->
    <div v-if="activeTab === 'fleet'">
      <div class="card">
        <div class="card-header">
          <h3>Proxmox VM Fleet</h3>
          <button @click="loadFleetVMs" class="btn btn-outline" :disabled="fleetLoading">
            {{ fleetLoading ? 'Loading…' : 'Refresh' }}
          </button>
        </div>

        <!-- Quick Filters -->
        <div class="fleet-quick-filters">
          <span class="fleet-qf-label">Quick filter:</span>
          <button :class="['fleet-qf-btn', fleetQuickFilter === '' ? 'active' : '']" @click="fleetQuickFilter = ''">All</button>
          <button :class="['fleet-qf-btn fleet-qf-warning', fleetQuickFilter === 'no-backups' ? 'active' : '']" @click="fleetQuickFilter = fleetQuickFilter === 'no-backups' ? '' : 'no-backups'">No Backups</button>
          <button :class="['fleet-qf-btn fleet-qf-info', fleetQuickFilter === 'has-snapshots' ? 'active' : '']" @click="fleetQuickFilter = fleetQuickFilter === 'has-snapshots' ? '' : 'has-snapshots'">Has Snapshots</button>
          <button :class="['fleet-qf-btn fleet-qf-success', fleetQuickFilter === 'protected' ? 'active' : '']" @click="fleetQuickFilter = fleetQuickFilter === 'protected' ? '' : 'protected'">Protected</button>
          <button :class="['fleet-qf-btn fleet-qf-danger', fleetQuickFilter === 'high-cpu' ? 'active' : '']" @click="fleetQuickFilter = fleetQuickFilter === 'high-cpu' ? '' : 'high-cpu'">High CPU (&gt;80%)</button>
          <button :class="['fleet-qf-btn fleet-qf-danger', fleetQuickFilter === 'high-ram' ? 'active' : '']" @click="fleetQuickFilter = fleetQuickFilter === 'high-ram' ? '' : 'high-ram'">High RAM (&gt;80%)</button>
        </div>

        <!-- Toolbar -->
        <div class="table-toolbar">
          <input v-model="fleetSearch" class="search-input" placeholder="Search by name, VMID, node, tag…" />
          <span class="text-sm text-muted">{{ filteredFleetVMs.length }} of {{ fleetVMs.length }} VMs</span>
          <template v-if="fleetSelectedKeys.size > 0">
            <span class="fleet-sel-count">{{ fleetSelectedKeys.size }} selected</span>
            <button class="btn btn-sm btn-outline" @click="openBatchTagModal('add')">+ Tag</button>
            <button class="btn btn-sm btn-outline" @click="openBatchTagModal('remove')">- Tag</button>
            <button class="btn btn-sm btn-outline" @click="openBatchNotesModal">Notes</button>
            <button class="btn btn-sm btn-secondary" @click="clearFleetSelection">Clear</button>
          </template>
        </div>

        <div v-if="fleetLoading" class="loading-row">
          <div class="loading-spinner"></div>
          <span>Loading fleet data (fetching configs &amp; snapshots)…</span>
        </div>
        <div v-else-if="fleetError" class="empty-state">
          <p class="text-danger">{{ fleetError }}</p>
          <button @click="loadFleetVMs" class="btn btn-outline btn-sm">Retry</button>
        </div>
        <div v-else-if="!fleetVMs.length" class="empty-state">
          <p>No Proxmox hosts configured, or no VMs found.</p>
          <button @click="loadFleetVMs" class="btn btn-outline btn-sm">Load Fleet</button>
        </div>
        <div v-else-if="!filteredFleetVMs.length" class="empty-state">
          <p>No VMs match the current filter.</p>
          <button @click="fleetSearch = ''; fleetQuickFilter = ''" class="btn btn-outline btn-sm">Clear Filters</button>
        </div>

        <div v-else class="table-wrapper">
          <table class="mgmt-table fleet-table">
            <thead>
              <tr>
                <th class="cb-col-fleet">
                  <input type="checkbox"
                    :checked="fleetAllSelected"
                    :indeterminate.prop="fleetSomeSelected && !fleetAllSelected"
                    @change="toggleFleetSelectAll"
                  />
                </th>
                <th class="th-sortable" @click="fleetSortBy('vmid')">VMID <span class="sort-icon">{{ fleetSortIcon('vmid') }}</span></th>
                <th class="th-sortable" @click="fleetSortBy('name')">Name <span class="sort-icon">{{ fleetSortIcon('name') }}</span></th>
                <th class="th-sortable" @click="fleetSortBy('status')">Status <span class="sort-icon">{{ fleetSortIcon('status') }}</span></th>
                <th class="th-sortable" @click="fleetSortBy('node')">Node <span class="sort-icon">{{ fleetSortIcon('node') }}</span></th>
                <th>Resources</th>
                <th>Tags</th>
                <th>Snapshots</th>
                <th>Lock</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="vm in filteredFleetVMs" :key="fleetVmKey(vm)"
                :class="{ 'row-fleet-selected': fleetSelectedKeys.has(fleetVmKey(vm)) }">
                <td class="cb-col-fleet">
                  <input type="checkbox"
                    :checked="fleetSelectedKeys.has(fleetVmKey(vm))"
                    @change="toggleFleetSelect(vm)"
                  />
                </td>
                <td><strong>{{ vm.vmid }}</strong></td>
                <td>
                  <div style="display:flex;flex-direction:column;gap:2px;">
                    <span class="fleet-vm-name">{{ vm.name || '(no name)' }}</span>
                    <span v-if="vm.description" class="fleet-vm-desc text-muted text-sm">{{ vm.description.slice(0, 60) }}{{ vm.description.length > 60 ? '…' : '' }}</span>
                  </div>
                </td>
                <td>
                  <span :class="['badge', vm.status === 'running' ? 'badge-success' : vm.status === 'stopped' ? 'badge-danger' : 'badge-warning']">
                    {{ vm.status }}
                  </span>
                  <span v-if="vm.isProtected" class="fleet-badge-pill fleet-badge-protect" title="Protection enabled">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:middle;"><path d="M12 2L4 7v5c0 5.25 3.4 10.16 8 11.36C16.6 22.16 20 17.25 20 12V7l-8-5z"/></svg>
                  </span>
                </td>
                <td class="text-sm">{{ vm.node }}</td>
                <td class="text-sm">
                  <span>{{ vm.cpus }}C / {{ fleetFormatBytes(vm.maxmem) }}</span>
                  <div v-if="vm.status === 'running'" class="fleet-usage-bars">
                    <div class="fleet-bar-wrap" title="CPU usage">
                      <div class="fleet-bar" :style="{ width: Math.round((vm.cpu || 0) * 100) + '%', background: (vm.cpu || 0) > 0.8 ? '#ef4444' : '#3b82f6' }"></div>
                    </div>
                    <div class="fleet-bar-wrap" title="RAM usage">
                      <div class="fleet-bar" :style="{ width: (vm.maxmem > 0 ? Math.round(vm.mem / vm.maxmem * 100) : 0) + '%', background: (vm.maxmem > 0 && vm.mem / vm.maxmem > 0.8) ? '#ef4444' : '#10b981' }"></div>
                    </div>
                  </div>
                </td>
                <td>
                  <div class="vm-tags" style="max-width:140px;">
                    <span v-for="tag in fleetParseTags(vm.tags)" :key="tag" class="fleet-tag-pill">{{ tag }}</span>
                    <span v-if="!fleetParseTags(vm.tags).length" class="text-muted text-sm">—</span>
                  </div>
                </td>
                <td class="text-sm text-center">
                  <span v-if="vm.snapshotCount > 0" class="fleet-snap-count">{{ vm.snapshotCount }}</span>
                  <span v-else class="text-muted">—</span>
                </td>
                <td class="text-sm text-center">
                  <span v-if="vm.isLocked" class="fleet-badge-pill fleet-badge-lock" title="VM is locked">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                    Locked
                  </span>
                  <span v-else class="text-muted">—</span>
                </td>
                <td>
                  <div style="display:flex;gap:0.3rem;flex-wrap:wrap;">
                    <button class="btn btn-sm btn-outline" @click="openQuickEdit(vm)" title="Quick Edit">Edit</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Quick Edit Drawer -->
      <div v-if="showQuickEdit" class="fleet-drawer-overlay" @click.self="closeQuickEdit" role="dialog" aria-modal="true" :aria-label="'Quick Edit VM ' + (quickEditVM?.vmid || '')">
        <div class="fleet-drawer" @click.stop>
          <div class="fleet-drawer-header">
            <div>
              <h3>Quick Edit — VM {{ quickEditVM?.vmid }}</h3>
              <span class="text-muted text-sm">{{ quickEditVM?.name }}</span>
            </div>
            <button @click="closeQuickEdit" class="btn-close-sm" aria-label="Close quick edit panel">×</button>
          </div>
          <div class="fleet-drawer-body">
            <div class="form-group">
              <label class="form-label">Name</label>
              <input v-model="quickEditForm.name" class="form-control" placeholder="VM name" />
            </div>
            <div class="form-group">
              <label class="form-label">Description / Notes</label>
              <textarea v-model="quickEditForm.description" class="form-control" rows="5" placeholder="Notes, IP, purpose…"></textarea>
            </div>
            <div class="form-group fleet-toggle-row">
              <label class="toggle-check-label">
                <input type="checkbox" v-model="quickEditForm.onboot" />
                Start at boot
              </label>
            </div>
            <div class="form-group fleet-toggle-row">
              <label class="toggle-check-label">
                <input type="checkbox" v-model="quickEditForm.protection" />
                Enable protection (prevent accidental delete)
              </label>
            </div>
          </div>
          <div class="fleet-drawer-footer">
            <button @click="closeQuickEdit" class="btn btn-outline">Cancel</button>
            <button @click="saveQuickEdit" class="btn btn-primary" :disabled="quickEditSaving">
              {{ quickEditSaving ? 'Saving…' : 'Save Changes' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Batch Tag Modal -->
      <div v-if="showBatchTagModal" class="modal-overlay" @click.self="!batchTagRunning && closeBatchTagModal()" role="dialog" aria-modal="true" :aria-label="batchTagMode === 'add' ? 'Add Tag to VMs' : 'Remove Tag from VMs'">
        <div class="modal-content" @click.stop style="max-width:480px;">
          <div class="modal-header">
            <h3>{{ batchTagMode === 'add' ? 'Add Tag to' : 'Remove Tag from' }} {{ fleetSelectedKeys.size }} VMs</h3>
            <button @click="closeBatchTagModal" class="btn-close-sm" :disabled="batchTagRunning" aria-label="Close dialog">×</button>
          </div>
          <div class="modal-body">
            <div v-if="!batchTagDone">
              <div class="form-group">
                <label class="form-label">Tag <span class="text-danger">*</span></label>
                <input v-model="batchTagValue" class="form-control"
                  :placeholder="batchTagMode === 'add' ? 'e.g. production' : 'e.g. old-tag'"
                  :disabled="batchTagRunning"
                  @input="batchTagValue = batchTagValue.toLowerCase().replace(/[^a-z0-9\-_]/g, '')"
                />
                <small class="text-muted">Lowercase letters, numbers, hyphens, underscores only</small>
              </div>
            </div>
            <div v-if="batchTagResults.length > 0" class="bulk-results-table">
              <div class="bulk-results-header"><span>VMID</span><span>Name</span><span>Node</span><span>Result</span></div>
              <div v-for="r in batchTagResults" :key="r.key" class="bulk-results-row">
                <span><strong>{{ r.vmid }}</strong></span>
                <span>{{ r.name || '—' }}</span>
                <span class="text-muted text-sm">{{ r.node }}</span>
                <span>
                  <span v-if="r.status === 'pending'" class="text-muted text-sm">Waiting…</span>
                  <span v-else-if="r.status === 'running'" class="text-sm" style="color:#3b82f6;">Running…</span>
                  <span v-else-if="r.status === 'success'" class="badge badge-success">OK</span>
                  <span v-else-if="r.status === 'error'" class="badge badge-danger" :title="r.error">Failed</span>
                </span>
              </div>
            </div>
            <div v-if="batchTagDone" class="bulk-done-summary">
              {{ batchTagResults.filter(r => r.status === 'success').length }} succeeded,
              {{ batchTagResults.filter(r => r.status === 'error').length }} failed.
            </div>
          </div>
          <div class="modal-footer">
            <button v-if="!batchTagDone" @click="closeBatchTagModal" class="btn btn-outline" :disabled="batchTagRunning">Cancel</button>
            <button v-if="!batchTagDone" @click="runBatchTag" class="btn btn-primary" :disabled="batchTagRunning || !batchTagValue.trim()">
              {{ batchTagRunning ? 'Running…' : (batchTagMode === 'add' ? 'Add Tag' : 'Remove Tag') }}
            </button>
            <button v-if="batchTagDone" @click="closeBatchTagModal" class="btn btn-outline">Close</button>
          </div>
        </div>
      </div>

      <!-- Batch Notes Modal -->
      <div v-if="showBatchNotesModal" class="modal-overlay" @click.self="!batchNotesRunning && closeBatchNotesModal()" role="dialog" aria-modal="true" aria-label="Batch Notes">
        <div class="modal-content" @click.stop style="max-width:520px;">
          <div class="modal-header">
            <h3>Batch Notes — {{ fleetSelectedKeys.size }} VMs</h3>
            <button @click="closeBatchNotesModal" class="btn-close-sm" :disabled="batchNotesRunning" aria-label="Close dialog">×</button>
          </div>
          <div class="modal-body">
            <div v-if="!batchNotesDone">
              <div class="form-group">
                <label class="form-label">Mode</label>
                <select v-model="batchNotesMode" class="form-control" :disabled="batchNotesRunning">
                  <option value="replace">Replace existing description</option>
                  <option value="append">Append to existing description</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Notes / Description</label>
                <textarea v-model="batchNotesText" class="form-control" rows="5"
                  placeholder="Enter notes to apply to all selected VMs"
                  :disabled="batchNotesRunning"></textarea>
              </div>
            </div>
            <div v-if="batchNotesResults.length > 0" class="bulk-results-table">
              <div class="bulk-results-header"><span>VMID</span><span>Name</span><span>Node</span><span>Result</span></div>
              <div v-for="r in batchNotesResults" :key="r.key" class="bulk-results-row">
                <span><strong>{{ r.vmid }}</strong></span>
                <span>{{ r.name || '—' }}</span>
                <span class="text-muted text-sm">{{ r.node }}</span>
                <span>
                  <span v-if="r.status === 'pending'" class="text-muted text-sm">Waiting…</span>
                  <span v-else-if="r.status === 'running'" class="text-sm" style="color:#3b82f6;">Running…</span>
                  <span v-else-if="r.status === 'success'" class="badge badge-success">OK</span>
                  <span v-else-if="r.status === 'error'" class="badge badge-danger" :title="r.error">Failed</span>
                </span>
              </div>
            </div>
            <div v-if="batchNotesDone" class="bulk-done-summary">
              {{ batchNotesResults.filter(r => r.status === 'success').length }} succeeded,
              {{ batchNotesResults.filter(r => r.status === 'error').length }} failed.
            </div>
          </div>
          <div class="modal-footer">
            <button v-if="!batchNotesDone" @click="closeBatchNotesModal" class="btn btn-outline" :disabled="batchNotesRunning">Cancel</button>
            <button v-if="!batchNotesDone" @click="runBatchNotes" class="btn btn-primary" :disabled="batchNotesRunning || !batchNotesText.trim()">
              {{ batchNotesRunning ? 'Running…' : 'Apply Notes' }}
            </button>
            <button v-if="batchNotesDone" @click="closeBatchNotesModal" class="btn btn-outline">Close</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── UPDATES TAB ── -->
    <div v-if="activeTab === 'updates'">
      <div class="card">
        <div class="card-header">
          <h3>OS Update Management</h3>
          <button @click="loadVMs" class="btn btn-outline" :disabled="loadingVMs">Refresh</button>
        </div>

        <!-- Auto-check schedule -->
        <div class="auto-check-bar">
          <label class="auto-check-toggle">
            <input type="checkbox" v-model="schedule.auto_update_check_enabled" @change="saveSchedule" />
            Auto-check every
          </label>
          <select v-model="schedule.auto_update_check_interval_hours" @change="saveSchedule" class="interval-select">
            <option :value="6">6 hours</option>
            <option :value="12">12 hours</option>
            <option :value="24">24 hours</option>
            <option :value="48">48 hours</option>
            <option :value="168">7 days</option>
          </select>
          <span class="text-sm text-muted">— runs on all managed VMs with saved credentials</span>
        </div>

        <div class="table-toolbar">
          <input v-model="search" class="search-input" placeholder="Search VMs, VMID, IP, OS..." />
          <select v-model="statusFilterMgmt" class="search-input" style="width: 140px; flex: none;">
            <option value="">All statuses</option>
            <option value="running">Running</option>
            <option value="stopped">Stopped</option>
            <option value="paused">Paused</option>
          </select>
          <span class="text-sm text-muted">{{ filteredVMs.length }} of {{ vms.length }} VMs</span>
        </div>

        <div v-if="loadingVMs" class="loading-row">
          <div class="loading-spinner"></div>
          <span>Loading VMs...</span>
        </div>

        <div v-else-if="vms.length === 0" class="empty-state">
          <p>No virtual machines found.</p>
        </div>

        <div v-else-if="filteredVMs.length === 0" class="empty-state">
          <p>No VMs match "{{ search }}"</p>
        </div>

        <div v-else class="table-wrapper">
          <table class="mgmt-table">
            <thead>
              <tr>
                <th class="th-sortable" @click="setSort('name')">VM <span class="sort-icon">{{ sortIcon('name') }}</span></th>
                <th>OS</th>
                <th class="th-sortable" @click="setSort('ip')">IP Address <span class="sort-icon">{{ sortIcon('ip') }}</span></th>
                <th class="th-sortable" @click="setSort('status')">Status <span class="sort-icon">{{ sortIcon('status') }}</span></th>
                <th>Last Update Check</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="vm in filteredVMs" :key="vm.vmid">
                <tr :class="{ 'row-expanded': expandedVM === vm.vmid }">
                  <td>
                    <div class="vm-name">
                      <strong>{{ vm.name }}</strong>
                      <span class="text-sm text-muted">VMID: {{ vm.vmid }}</span>
                      <span v-if="getManagedVM(vm.vmid)?.ip_address" class="cred-indicator cred-saved" title="SSH credentials saved">🔑</span>
                      <span v-else-if="sessionCreds[vm.vmid]?.ip_address" class="cred-indicator cred-session" title="Session credentials (not saved)">🔑</span>
                    </div>
                  </td>
                  <td class="text-sm">{{ getManagedVM(vm.vmid)?.os_type || '—' }}</td>
                  <td class="text-sm mono">{{ getManagedVM(vm.vmid)?.ip_address || '—' }}</td>
                  <td>
                    <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
                  </td>
                  <td class="text-sm text-muted">
                    <span v-if="updateChecks[vm.vmid]?.checked_at">{{ formatDate(updateChecks[vm.vmid].checked_at) }}</span>
                    <span v-else-if="getCacheEntry(getManagedVM(vm.vmid)?.id, 'updates')">
                      {{ formatDate(getCacheEntry(getManagedVM(vm.vmid)?.id, 'updates').scanned_at) }}
                      <span class="auto-badge">auto</span>
                    </span>
                    <span v-else>Never</span>
                  </td>
                  <td>
                    <div class="action-btns">
                      <button
                        @click="checkUpdates(vm)"
                        class="btn btn-sm btn-outline"
                        :disabled="updatingVM === vm.vmid || vm.status !== 'running' || !getManagedVM(vm.vmid)?.ip_address"
                        :title="!getManagedVM(vm.vmid) ? 'Not managed by Depl0y' : !getManagedVM(vm.vmid)?.ip_address ? 'No IP — set SSH credentials first' : vm.status !== 'running' ? 'VM must be running' : 'Check for updates'"
                      >
                        {{ updatingVM === vm.vmid && updateAction === 'check' ? '...' : 'Check' }}
                      </button>
                      <button
                        @click="installUpdates(vm)"
                        class="btn btn-sm btn-primary"
                        :disabled="updatingVM === vm.vmid || vm.status !== 'running' || !getManagedVM(vm.vmid)?.ip_address"
                        :title="!getManagedVM(vm.vmid) ? 'Not managed by Depl0y' : !getManagedVM(vm.vmid)?.ip_address ? 'No IP — set SSH credentials first' : vm.status !== 'running' ? 'VM must be running' : 'Install updates'"
                      >
                        {{ updatingVM === vm.vmid && updateAction === 'install' ? 'Installing...' : 'Update' }}
                      </button>
                      <button
                        @click="toggleHistory(vm.vmid)"
                        class="btn btn-sm btn-secondary"
                      >
                        History
                      </button>
                      <button
                        @click="openCredModal(vm)"
                        class="btn btn-sm btn-outline"
                        title="Set SSH credentials"
                      >
                        🔑
                      </button>
                    </div>
                  </td>
                </tr>

                <!-- Update check result (manual or cached) -->
                <tr v-if="getUpdateResult(vm) && expandedVM !== vm.vmid" class="result-row">
                  <td colspan="6">
                    <div :class="['update-result', getUpdateResult(vm).updates_available > 0 ? 'has-updates' : 'up-to-date']">
                      <span v-if="getUpdateResult(vm).updates_available > 0">
                        ⚠️ <strong>{{ getUpdateResult(vm).updates_available }}</strong> update(s) available
                        <span v-if="!updateChecks[vm.vmid] && getCacheEntry(getManagedVM(vm.vmid)?.id, 'updates')" class="auto-badge">auto-check</span>
                      </span>
                      <span v-else>✅ Up to date</span>
                    </div>
                  </td>
                </tr>

                <!-- Live update progress -->
                <tr v-if="liveLog[vm.vmid]" class="live-log-row">
                  <td colspan="6">
                    <div class="live-log-panel">
                      <div class="live-log-header">
                        <span class="live-log-title">
                          <span v-if="liveLog[vm.vmid].status === 'running'" class="live-dot"></span>
                          Installing updates on <strong>{{ vm.name }}</strong>
                        </span>
                        <div class="live-log-meta">
                          <span v-if="liveLog[vm.vmid].status === 'completed'" class="text-success text-sm">
                            ✅ {{ liveLog[vm.vmid].packages_updated }} package(s) updated
                          </span>
                          <span v-else-if="liveLog[vm.vmid].status === 'failed'" class="text-danger text-sm">
                            ❌ {{ liveLog[vm.vmid].error_message || 'Update failed' }}
                          </span>
                          <span :class="['badge', liveLog[vm.vmid].status === 'completed' ? 'badge-success' : liveLog[vm.vmid].status === 'failed' ? 'badge-danger' : 'badge-warning']">
                            {{ liveLog[vm.vmid].status }}
                          </span>
                          <button @click="closeLiveLog(vm.vmid)" class="btn-close-sm" title="Dismiss" aria-label="Dismiss live log">×</button>
                        </div>
                      </div>
                      <pre class="live-log-output" :id="`livelog-${vm.vmid}`">{{ liveLog[vm.vmid].output || 'Starting…' }}</pre>
                      <div v-if="liveLog[vm.vmid].output?.includes('deferred due to phasing')" class="phasing-note">
                        <strong>Phased update:</strong> some packages are held back by Ubuntu's gradual rollout system — this is normal. They install automatically when your system's turn comes. To force-install now, run <code>apt-get dist-upgrade</code> on the VM.
                      </div>
                    </div>
                  </td>
                </tr>

                <!-- Update history panel -->
                <tr v-if="expandedVM === vm.vmid" class="history-row">
                  <td colspan="6">
                    <div class="history-panel">
                      <div v-if="loadingHistory[vm.vmid]" class="loading-row">
                        <div class="loading-spinner"></div>
                        <span>Loading history...</span>
                      </div>
                      <div v-else-if="!updateHistory[vm.vmid] || updateHistory[vm.vmid].length === 0" class="history-empty">
                        No update history for this VM.
                      </div>
                      <div v-else>
                        <table class="history-table">
                          <thead>
                            <tr>
                              <th>Date</th>
                              <th>Status</th>
                              <th>Packages</th>
                              <th>Output</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="log in updateHistory[vm.vmid]" :key="log.id">
                              <td class="text-sm">{{ formatDate(log.started_at) }}</td>
                              <td>
                                <span :class="['badge', log.status === 'completed' ? 'badge-success' : log.status === 'failed' ? 'badge-danger' : 'badge-warning']">
                                  {{ log.status }}
                                </span>
                              </td>
                              <td class="text-sm">{{ log.packages_updated ?? '—' }}</td>
                              <td>
                                <details v-if="log.output">
                                  <summary class="text-sm">View</summary>
                                  <pre class="log-output">{{ log.output }}</pre>
                                </details>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- SSH Credentials Modal -->
    <div v-if="credModal.show" class="modal-overlay" @click="credModal.show = false" role="dialog" aria-modal="true" :aria-label="'SSH Credentials — ' + (credModal.vm?.name || '')">
      <div class="cred-modal" @click.stop>
        <div class="cred-modal-header">
          <h3>SSH Credentials — {{ credModal.vm?.name }}</h3>
          <button @click="credModal.show = false" class="btn-close-sm" aria-label="Close dialog">×</button>
        </div>
        <div class="cred-modal-body">
          <p class="cred-note">These credentials are used to SSH into the VM for update and security scan operations.</p>
          <div class="form-group">
            <label class="form-label">
              IP Address
              <span v-if="fetchingIP" class="fetching-ip">fetching from agent...</span>
            </label>
            <input v-model="credForm.ip_address" class="form-control" placeholder="192.168.1.100" autocomplete="off" :disabled="fetchingIP" />
          </div>
          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="credForm.username" class="form-control" placeholder="ubuntu" autocomplete="off" />
          </div>
          <form @submit.prevent>
            <div class="form-group">
              <label class="form-label">Password</label>
              <input v-model="credForm.password" type="password" class="form-control" placeholder="Leave blank to keep existing" autocomplete="new-password" />
            </div>
          </form>
          <label class="cred-save-row">
            <input
              type="checkbox"
              v-model="credForm.saveToDb"
              :disabled="!credModal.managed"
            />
            <span :class="{ 'text-muted': !credModal.managed }">Save credentials (encrypted)</span>
            <span class="cred-save-hint">
              {{ credModal.managed ? 'Uncheck to use for this session only' : 'Not managed by Depl0y — session only' }}
            </span>
          </label>
        </div>
        <div class="cred-modal-footer">
          <button @click="credModal.show = false" class="btn btn-outline">Cancel</button>
          <button @click="saveCredentials" class="btn btn-primary" :disabled="savingCreds">
            {{ savingCreds ? 'Saving...' : credForm.saveToDb ? 'Save' : 'Use for Session' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── SECURITY TAB ── -->
    <div v-if="activeTab === 'security'">
      <div class="card">
        <div class="card-header">
          <h3>Security &amp; Dependency Scan</h3>
          <span class="text-sm text-muted">SSH-based scan: OS security updates, open ports, failed login attempts, outdated packages</span>
        </div>

        <!-- Auto-scan schedule -->
        <div class="auto-check-bar">
          <label class="auto-check-toggle">
            <input type="checkbox" v-model="schedule.auto_security_scan_enabled" @change="saveSchedule" />
            Auto-scan every
          </label>
          <select v-model="schedule.auto_security_scan_interval_hours" @change="saveSchedule" class="interval-select">
            <option :value="6">6 hours</option>
            <option :value="12">12 hours</option>
            <option :value="24">24 hours</option>
            <option :value="48">48 hours</option>
            <option :value="168">7 days</option>
          </select>
          <span class="text-sm text-muted">— runs on all managed VMs with saved credentials</span>
        </div>

        <div class="table-toolbar">
          <input v-model="search" class="search-input" placeholder="Search VMs, VMID, IP, OS..." />
          <select v-model="statusFilterMgmt" class="search-input" style="width: 140px; flex: none;">
            <option value="">All statuses</option>
            <option value="running">Running</option>
            <option value="stopped">Stopped</option>
            <option value="paused">Paused</option>
          </select>
          <span class="text-sm text-muted">{{ filteredVMs.length }} of {{ vms.length }} VMs</span>
        </div>

        <div v-if="loadingVMs" class="loading-row">
          <div class="loading-spinner"></div>
          <span>Loading VMs...</span>
        </div>

        <div v-else-if="vms.length === 0" class="empty-state">
          <p>No virtual machines found.</p>
        </div>

        <div v-else class="table-wrapper">
          <table class="mgmt-table">
            <thead>
              <tr>
                <th class="th-sortable" @click="setSort('name')">VM <span class="sort-icon">{{ sortIcon('name') }}</span></th>
                <th class="th-sortable" @click="setSort('ip')">IP Address <span class="sort-icon">{{ sortIcon('ip') }}</span></th>
                <th class="th-sortable" @click="setSort('status')">Status <span class="sort-icon">{{ sortIcon('status') }}</span></th>
                <th>Last Scan</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="vm in filteredVMs" :key="vm.vmid">
                <tr>
                  <td>
                    <div class="vm-name">
                      <strong>{{ vm.name }}</strong>
                      <span class="text-sm text-muted">VMID: {{ vm.vmid }}</span>
                      <span v-if="getManagedVM(vm.vmid)?.ip_address" class="cred-indicator cred-saved" title="SSH credentials saved">🔑</span>
                      <span v-else-if="sessionCreds[vm.vmid]?.ip_address" class="cred-indicator cred-session" title="Session credentials (not saved)">🔑</span>
                    </div>
                  </td>
                  <td class="text-sm mono">{{ getManagedVM(vm.vmid)?.ip_address || '—' }}</td>
                  <td>
                    <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
                  </td>
                  <td class="text-sm text-muted">
                    <span v-if="scanResults[vm.vmid]">
                      <span :class="['badge', scanResults[vm.vmid].severity === 'critical' ? 'badge-danger' : scanResults[vm.vmid].severity === 'warning' ? 'badge-warning' : 'badge-success']">
                        {{ scanResults[vm.vmid].severity }}
                      </span>
                      &nbsp;{{ formatDate(scanResults[vm.vmid].scanned_at) }}
                    </span>
                    <span v-else-if="getCacheEntry(getManagedVM(vm.vmid)?.id, 'security')">
                      <span :class="['badge', getCacheEntry(getManagedVM(vm.vmid)?.id, 'security').severity === 'critical' ? 'badge-danger' : getCacheEntry(getManagedVM(vm.vmid)?.id, 'security').severity === 'warning' ? 'badge-warning' : 'badge-success']">
                        {{ getCacheEntry(getManagedVM(vm.vmid)?.id, 'security').severity }}
                      </span>
                      &nbsp;{{ formatDate(getCacheEntry(getManagedVM(vm.vmid)?.id, 'security').scanned_at) }}
                      <span class="auto-badge">auto</span>
                    </span>
                    <span v-else>Never</span>
                  </td>
                  <td>
                    <button
                      @click="runScan(vm)"
                      class="btn btn-sm btn-outline"
                      :disabled="scanning === vm.vmid || vm.status !== 'running' || !getManagedVM(vm.vmid)?.ip_address"
                      :title="!getManagedVM(vm.vmid) ? 'Not managed by Depl0y' : !getManagedVM(vm.vmid)?.ip_address ? 'No IP — set SSH credentials first' : vm.status !== 'running' ? 'VM must be running' : 'Run security scan'"
                    >
                      {{ scanning === vm.vmid ? 'Scanning...' : 'Scan' }}
                    </button>
                    <button
                      v-if="scanResults[vm.vmid]"
                      @click="scanExpanded[vm.vmid] = !scanExpanded[vm.vmid]"
                      class="btn btn-sm btn-secondary"
                      style="margin-left: 0.4rem"
                    >
                      {{ scanExpanded[vm.vmid] ? 'Hide' : 'Details' }}
                    </button>
                  </td>
                </tr>

                <!-- Scan results panel -->
                <tr v-if="scanResults[vm.vmid] && scanExpanded[vm.vmid]" class="history-row">
                  <td colspan="5">
                    <div class="history-panel scan-panel">
                      <div class="scan-grid">
                        <!-- OS Updates -->
                        <div class="scan-card">
                          <div class="scan-card-title">OS Updates</div>
                          <div class="scan-stat" :class="scanResults[vm.vmid].os_updates?.security_updates > 0 ? 'scan-stat-warn' : 'scan-stat-ok'">
                            {{ scanResults[vm.vmid].os_updates?.security_updates ?? '—' }}
                            <span class="scan-stat-label">security</span>
                          </div>
                          <div class="scan-sub text-muted">{{ scanResults[vm.vmid].os_updates?.total_upgradable ?? 0 }} total upgradable</div>
                          <div v-if="scanResults[vm.vmid].os_updates?.security_packages?.length" class="scan-pkg-list">
                            <div v-for="pkg in scanResults[vm.vmid].os_updates.security_packages.slice(0,8)" :key="pkg" class="scan-pkg">{{ pkg }}</div>
                          </div>
                        </div>

                        <!-- Failed SSH -->
                        <div class="scan-card">
                          <div class="scan-card-title">Failed SSH Logins</div>
                          <div class="scan-stat" :class="scanResults[vm.vmid].failed_ssh_attempts > 100 ? 'scan-stat-crit' : scanResults[vm.vmid].failed_ssh_attempts > 10 ? 'scan-stat-warn' : 'scan-stat-ok'">
                            {{ scanResults[vm.vmid].failed_ssh_attempts ?? 0 }}
                          </div>
                          <div class="scan-sub text-muted">attempts in auth.log</div>
                        </div>

                        <!-- Open Ports -->
                        <div class="scan-card scan-card-wide">
                          <div class="scan-card-title">Open Listening Ports</div>
                          <div v-if="scanResults[vm.vmid].open_ports?.length" class="scan-ports">
                            <pre class="scan-pre">{{ scanResults[vm.vmid].open_ports.join('\n') }}</pre>
                          </div>
                          <div v-else class="text-muted text-sm">None detected</div>
                        </div>

                        <!-- Python outdated -->
                        <div class="scan-card">
                          <div class="scan-card-title">Outdated Python Packages</div>
                          <div class="scan-stat" :class="scanResults[vm.vmid].python_outdated?.count > 0 ? 'scan-stat-warn' : 'scan-stat-ok'">
                            {{ scanResults[vm.vmid].python_outdated?.count ?? 0 }}
                          </div>
                          <div v-if="scanResults[vm.vmid].python_outdated?.packages?.length" class="scan-pkg-list">
                            <div v-for="pkg in scanResults[vm.vmid].python_outdated.packages.slice(0,5)" :key="pkg" class="scan-pkg">{{ pkg }}</div>
                          </div>
                          <div v-else class="scan-sub text-muted">pip3 not found or all current</div>
                        </div>

                        <!-- npm outdated -->
                        <div class="scan-card">
                          <div class="scan-card-title">Outdated npm (global)</div>
                          <div class="scan-stat" :class="scanResults[vm.vmid].npm_outdated?.count > 0 ? 'scan-stat-warn' : 'scan-stat-ok'">
                            {{ scanResults[vm.vmid].npm_outdated?.count ?? 0 }}
                          </div>
                          <div v-if="scanResults[vm.vmid].npm_outdated?.packages?.length" class="scan-pkg-list">
                            <div v-for="pkg in scanResults[vm.vmid].npm_outdated.packages.slice(0,5)" :key="pkg" class="scan-pkg">{{ pkg }}</div>
                          </div>
                          <div v-else class="scan-sub text-muted">npm not found or all current</div>
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ── MONITORING TAB ── -->
    <div v-if="activeTab === 'monitoring'">
      <div class="card">
        <div class="card-header">
          <h3>VM Resource Monitoring</h3>
          <button @click="loadMonitoring" class="btn btn-outline" :disabled="loadingMonitor">Refresh</button>
        </div>

        <div v-if="loadingMonitor" class="loading-row">
          <div class="loading-spinner"></div>
          <span>Loading resource data...</span>
        </div>

        <div v-else-if="vms.length === 0" class="empty-state">
          <p>No virtual machines found.</p>
        </div>

        <div v-else class="monitor-grid">
          <div v-for="vm in vms" :key="vm.vmid" class="monitor-card">
            <div class="monitor-header">
              <div>
                <strong>{{ vm.name }}</strong>
                <span class="text-sm text-muted" v-if="getManagedVM(vm.vmid)?.os_type"> · {{ getManagedVM(vm.vmid).os_type }}</span>
              </div>
              <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
            </div>

            <div class="monitor-specs">
              <div class="spec-row">
                <span class="spec-label">VMID</span>
                <span class="spec-value mono">{{ vm.vmid }}</span>
              </div>
              <div class="spec-row">
                <span class="spec-label">Node</span>
                <span class="spec-value mono">{{ vm.node || '—' }}</span>
              </div>
              <div class="spec-row">
                <span class="spec-label">CPU</span>
                <span class="spec-value">{{ vm.cpus || '—' }} cores</span>
              </div>
              <div class="spec-row">
                <span class="spec-label">RAM</span>
                <span class="spec-value">{{ formatBytes(vm.maxmem) }}</span>
              </div>
              <div class="spec-row">
                <span class="spec-label">Disk</span>
                <span class="spec-value">{{ formatBytes(vm.maxdisk) }}</span>
              </div>
              <div class="spec-row">
                <span class="spec-label">IP</span>
                <span class="spec-value mono">{{ getManagedVM(vm.vmid)?.ip_address || '—' }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="monitor-note info-box" style="margin: 0 1rem 1rem; font-size: 0.8rem;">
          Live CPU/RAM usage metrics require the QEMU Guest Agent on each VM and are available in the Proxmox web UI.
          The <router-link to="/proxmox">Proxmox Hosts</router-link> page shows node-level resource usage.
        </div>
      </div>
    </div>

    <!-- ── CONV LOGS TAB ── -->
    <div v-if="activeTab === 'conv-logs'">
      <div class="card">
        <div class="card-header">
          <h3>Conversation Logs</h3>
          <span class="text-sm text-muted">Intercepts and logs all Ollama API calls for analysis, fine-tuning, and auditing</span>
        </div>

        <div v-if="llmOllamaVMs.length === 0" class="empty-state">
          <p>No Ollama LLM VMs found.</p>
          <p class="text-sm text-muted">Deploy an Ollama VM via <router-link to="/llm-deploy">Deploy LLM</router-link>.</p>
        </div>

        <div v-else class="conv-layout">
          <!-- VM selector sidebar -->
          <div class="conv-vm-list">
            <div
              v-for="vm in llmOllamaVMs"
              :key="vm.vmid"
              :class="['conv-vm-item', { active: convLogVM?.vmid === vm.vmid }]"
              @click="selectConvLogVM(vm)"
            >
              <strong>{{ vm.name }}</strong>
              <span class="text-sm text-muted">{{ getManagedVM(vm.vmid)?.ip_address || 'No IP' }}</span>
              <span v-if="convLogStatus[vm.vmid]?.active" class="badge badge-success" style="font-size:0.65rem">logging</span>
              <span v-else-if="convLogStatus[vm.vmid]?.installed" class="badge badge-warning" style="font-size:0.65rem">stopped</span>
            </div>
          </div>

          <!-- Main panel -->
          <div class="conv-main" v-if="convLogVM">
            <div class="conv-controls">
              <div v-if="!convLogStatus[convLogVM.vmid]?.installed" class="info-box" style="margin-bottom:1rem">
                <p class="text-sm">The conversation logger proxy is not installed on this VM. Install it to start capturing all Ollama API calls.</p>
                <button @click="installConvLogger(convLogVM)" class="btn btn-primary" style="margin-top:0.75rem">
                  Install Logger
                </button>
              </div>
              <div v-else class="conv-status-bar">
                <span v-if="convLogStatus[convLogVM.vmid]?.active" class="text-success text-sm">● Logger active</span>
                <span v-else class="text-danger text-sm">● Logger stopped</span>
                <span class="text-sm text-muted" style="margin-left:1rem">
                  {{ convLogStatus[convLogVM.vmid]?.log_entries || 0 }} entries
                </span>
                <div style="margin-left:auto;display:flex;gap:0.5rem">
                  <button @click="loadConvLogs" class="btn btn-sm btn-outline" :disabled="convLogLoading">
                    {{ convLogLoading ? 'Loading...' : 'Refresh' }}
                  </button>
                  <button @click="clearConvLogs(convLogVM)" class="btn btn-sm btn-danger-outline">Clear All</button>
                </div>
              </div>

              <!-- Live install terminal -->
              <div v-if="tuneApplyJobs[convLogVM.vmid]" class="live-log-panel" style="margin-top:0.75rem">
                <div class="live-log-header">
                  <span class="live-log-title">
                    <span v-if="tuneApplyJobs[convLogVM.vmid].status === 'running'" class="live-dot"></span>
                    {{ tuneApplyJobs[convLogVM.vmid].action }}
                  </span>
                  <div class="live-log-meta">
                    <span v-if="tuneApplyJobs[convLogVM.vmid].status === 'completed'" class="text-success text-sm">✅ Done</span>
                    <span v-else-if="tuneApplyJobs[convLogVM.vmid].status === 'failed'" class="text-danger text-sm">❌ Failed</span>
                    <button class="btn btn-xs" @click="closeTuneApplyLog(convLogVM.vmid)" style="margin-left:0.5rem">✕</button>
                  </div>
                </div>
                <pre class="live-log-output" :id="`tuneapply-${convLogVM.vmid}`">{{ tuneApplyJobs[convLogVM.vmid].output || 'Starting...' }}</pre>
              </div>
            </div>

            <!-- Log entries -->
            <div v-if="convLogEntries.length" class="conv-entries">
              <div v-for="(entry, i) in convLogEntries" :key="i" class="conv-entry">
                <div class="conv-entry-meta">
                  <span class="conv-model badge badge-info">{{ entry.model }}</span>
                  <span class="text-sm text-muted">{{ entry.ts }}</span>
                </div>
                <div class="conv-bubble conv-user">{{ entry.user || '(empty)' }}</div>
                <div class="conv-bubble conv-assistant">{{ entry.assistant || '(empty)' }}</div>
              </div>
            </div>
            <div v-else-if="convLogStatus[convLogVM.vmid]?.installed" class="empty-state">
              <p>No conversations logged yet.</p>
              <p class="text-sm text-muted">Click Refresh after making some Ollama API calls.</p>
            </div>
          </div>
          <div v-else class="conv-main empty-state">
            <p>Select a VM from the left to view conversation logs.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ── RAG TAB ── -->
    <div v-if="activeTab === 'rag'">
      <div class="card">
        <div class="card-header">
          <h3>RAG — Knowledge Base</h3>
          <span class="text-sm text-muted">ChromaDB vector store + Ollama embeddings for retrieval-augmented generation</span>
        </div>

        <div v-if="llmOllamaVMs.length === 0" class="empty-state">
          <p>No Ollama LLM VMs found.</p>
        </div>

        <div v-else class="conv-layout">
          <!-- VM selector -->
          <div class="conv-vm-list">
            <div
              v-for="vm in llmOllamaVMs"
              :key="vm.vmid"
              :class="['conv-vm-item', { active: ragVM?.vmid === vm.vmid }]"
              @click="selectRagVM(vm)"
            >
              <strong>{{ vm.name }}</strong>
              <span class="text-sm text-muted">{{ getManagedVM(vm.vmid)?.ip_address || 'No IP' }}</span>
              <span v-if="ragStatus[vm.vmid]?.active" class="badge badge-success" style="font-size:0.65rem">active</span>
            </div>
          </div>

          <!-- Main panel -->
          <div class="conv-main" v-if="ragVM">
            <!-- Install section -->
            <div v-if="!ragStatus[ragVM.vmid]?.installed" class="info-box" style="margin-bottom:1rem">
              <p class="text-sm">RAG service not installed. Choose an embedding model and install.</p>
              <div style="display:flex;gap:0.5rem;margin-top:0.75rem;align-items:center;flex-wrap:wrap">
                <select v-model="ragSelectedEmbed" class="pull-select" style="max-width:280px">
                  <option v-for="m in (ragStatus[ragVM.vmid]?.catalog || [{id:'nomic-embed-text',name:'Nomic Embed Text'}])" :key="m.id" :value="m.id">
                    {{ m.name }} {{ m.size ? '(' + m.size + ')' : '' }}
                  </option>
                </select>
                <button @click="installRag(ragVM)" class="btn btn-primary">Install RAG</button>
              </div>
            </div>

            <!-- Live install terminal -->
            <div v-if="tuneApplyJobs[ragVM.vmid]" class="live-log-panel" style="margin-bottom:1rem">
              <div class="live-log-header">
                <span class="live-log-title">
                  <span v-if="tuneApplyJobs[ragVM.vmid].status === 'running'" class="live-dot"></span>
                  {{ tuneApplyJobs[ragVM.vmid].action }}
                </span>
                <div class="live-log-meta">
                  <span v-if="tuneApplyJobs[ragVM.vmid].status === 'completed'" class="text-success text-sm">✅ Done</span>
                  <span v-else-if="tuneApplyJobs[ragVM.vmid].status === 'failed'" class="text-danger text-sm">❌ Failed</span>
                  <button class="btn btn-xs" @click="closeTuneApplyLog(ragVM.vmid)" style="margin-left:0.5rem">✕</button>
                </div>
              </div>
              <pre class="live-log-output" :id="`tuneapply-${ragVM.vmid}`">{{ tuneApplyJobs[ragVM.vmid].output || 'Starting...' }}</pre>
            </div>

            <div v-if="ragStatus[ragVM.vmid]?.installed">
              <!-- Ingest -->
              <div class="rag-section">
                <h4>Ingest Document</h4>
                <div class="form-group">
                  <label class="form-label">Source / Name</label>
                  <input v-model="ragIngestSource" class="form-control" placeholder="e.g. company-faq.txt" />
                </div>
                <div class="form-group">
                  <label class="form-label">Text Content</label>
                  <textarea v-model="ragIngestText" class="form-control" rows="5" placeholder="Paste document text here..." style="resize:vertical"></textarea>
                </div>
                <button @click="ragIngestDoc" class="btn btn-primary" :disabled="ragLoading || !ragIngestText.trim()">
                  {{ ragLoading ? 'Ingesting...' : 'Ingest' }}
                </button>
              </div>

              <!-- Query -->
              <div class="rag-section">
                <h4>Query Knowledge Base</h4>
                <div style="display:flex;gap:0.5rem">
                  <input v-model="ragQueryText" class="form-control" placeholder="Ask a question..." @keyup.enter="ragDoQuery" />
                  <button @click="ragDoQuery" class="btn btn-primary" :disabled="ragLoading || !ragQueryText.trim()">Search</button>
                </div>
                <div v-if="ragQueryResults.length" class="rag-results">
                  <div v-for="(r, i) in ragQueryResults" :key="i" class="rag-result">
                    <div class="rag-result-meta text-sm text-muted">
                      <span>{{ r.source }}</span>
                      <span>score: {{ (1 - r.distance).toFixed(3) }}</span>
                    </div>
                    <p class="rag-result-text">{{ r.text }}</p>
                  </div>
                </div>
              </div>

              <!-- Docs list -->
              <div class="rag-section">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
                  <h4>Ingested Documents ({{ ragDocs.length }})</h4>
                  <button @click="loadRagDocs" class="btn btn-sm btn-outline" :disabled="ragLoading">Refresh</button>
                </div>
                <div v-if="ragDocs.length" class="rag-doc-list">
                  <div v-for="doc in ragDocs" :key="doc.id" class="rag-doc-row">
                    <span class="model-name mono text-sm">{{ doc.source }}</span>
                    <span class="text-sm text-muted" style="flex:1">{{ doc.preview }}...</span>
                    <button @click="ragDeleteDoc(doc.id)" class="btn btn-sm btn-danger-outline">Delete</button>
                  </div>
                </div>
                <div v-else class="text-sm text-muted" style="padding:0.5rem 0">No documents ingested yet.</div>
              </div>
            </div>
          </div>
          <div v-else class="conv-main empty-state">
            <p>Select a VM from the left to manage its knowledge base.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ── ALL PROXMOX VMs (UNMANAGED) SECTION ── -->
    <div class="card unmanaged-section">
      <div class="card-header unmanaged-header" @click="unmanagedExpanded = !unmanagedExpanded" style="cursor:pointer">
        <div>
          <h3 style="margin:0">All Proxmox VMs <span class="text-muted" style="font-weight:400;font-size:0.9rem">(unmanaged)</span></h3>
          <span class="text-sm text-muted">VMs present in Proxmox but not tracked by Depl0y</span>
        </div>
        <div style="display:flex;align-items:center;gap:0.75rem">
          <span v-if="unmanagedVMs.length" class="badge badge-secondary">{{ unmanagedVMs.length }}</span>
          <button
            @click.stop="loadUnmanagedVMs"
            class="btn btn-outline btn-sm"
            :disabled="loadingUnmanaged"
          >{{ loadingUnmanaged ? 'Loading...' : 'Refresh' }}</button>
          <span class="unmanaged-chevron" :class="{ rotated: unmanagedExpanded }">▾</span>
        </div>
      </div>

      <div v-if="unmanagedExpanded">
        <div v-if="loadingUnmanaged" class="loading-row">
          <div class="loading-spinner"></div>
          <span>Loading Proxmox cluster resources...</span>
        </div>
        <div v-else-if="unmanagedVMs.length === 0" class="empty-state">
          <p>All Proxmox VMs are already tracked by Depl0y, or no Proxmox hosts are configured.</p>
        </div>
        <div v-else class="table-wrapper">
          <table class="mgmt-table">
            <thead>
              <tr>
                <th>VMID</th>
                <th>Name</th>
                <th>Status</th>
                <th>Node</th>
                <th>Host</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="vm in unmanagedVMs" :key="`${vm.hostId}-${vm.vmid}`">
                <td class="mono text-sm">{{ vm.vmid }}</td>
                <td><strong>{{ vm.name || '—' }}</strong></td>
                <td>
                  <span :class="['badge', vm.status === 'running' ? 'badge-success' : 'badge-secondary']">
                    {{ vm.status || 'unknown' }}
                  </span>
                </td>
                <td class="text-sm mono">{{ vm.node || '—' }}</td>
                <td class="text-sm text-muted">{{ vm.hostName || vm.hostId }}</td>
                <td>
                  <button
                    class="btn btn-primary btn-sm"
                    :disabled="adoptingVMs.has(`${vm.hostId}-${vm.vmid}`)"
                    @click="adoptVm(vm)"
                  >
                    {{ adoptingVMs.has(`${vm.hostId}-${vm.vmid}`) ? 'Adopting...' : 'Adopt' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ── AI TUNING TAB ── -->
    <div v-if="activeTab === 'ai-tuning'">
      <div class="card">
        <div class="card-header">
          <h3>AI Performance Tuning</h3>
          <span class="badge badge-info">Beta</span>
        </div>
        <div class="ai-tuning-intro info-box">
          <p>
            AI Tuning SSHes into your LLM VM, inspects the running model server configuration,
            hardware profile, and inference load — then uses AI analysis to generate and apply
            optimized settings for maximum throughput and lowest latency.
          </p>
        </div>

        <div v-if="loadingVMs" class="loading-row">
          <div class="loading-spinner"></div>
          <span>Loading VMs...</span>
        </div>

        <div v-else-if="llmVMs.length === 0" class="empty-state">
          <p>No LLM VMs found.</p>
          <p class="text-sm text-muted">Deploy an LLM VM via <router-link to="/llm-deploy">Deploy LLM</router-link> to get started.</p>
        </div>

        <div v-else class="llm-vm-list">
          <div v-for="vm in llmVMs" :key="vm.vmid" class="llm-vm-card">
            <div class="llm-vm-header">
              <div>
                <strong>{{ vm.name }}</strong>
                <span class="text-sm text-muted"> · {{ getManagedVM(vm.vmid)?.ip_address || 'No IP' }}</span>
                <span v-if="getLLMDeployment(vm.vmid)" class="text-sm text-muted"> · {{ getLLMDeployment(vm.vmid).engine }}</span>
              </div>
              <span :class="['badge', getVMStatusBadge(vm.status)]">{{ vm.status }}</span>
            </div>
            <div class="llm-vm-specs text-sm text-muted">
              {{ vm.cpus || '—' }} CPU · {{ formatBytes(vm.maxmem) }} RAM · {{ formatBytes(vm.maxdisk) }} disk
            </div>
            <div class="llm-vm-actions">
              <button
                @click="runAITune(vm)"
                class="btn btn-primary"
                :disabled="tuningVM === vm.vmid || vm.status !== 'running' || !getManagedVM(vm.vmid)"
                :title="!getManagedVM(vm.vmid) ? 'Not managed by Depl0y' : ''"
              >
                <span v-if="tuningVM === vm.vmid">Analyzing...</span>
                <span v-else>Run AI Tune</span>
              </button>

              <!-- Open Meme Generator button for meme-maker deployments -->
              <button
                v-if="getLLMDeployment(vm.vmid)?.engine === 'meme-maker'"
                @click="openMemeGenerator(vm)"
                class="btn btn-secondary"
                :disabled="vm.status !== 'running'"
                title="Open Meme Generator web UI"
              >
                Open Meme Generator
              </button>
            </div>

            <!-- Tuning results -->
            <div v-if="tuningResults[vm.vmid]" class="tuning-results">
              <div :class="['tuning-status', tuningResults[vm.vmid].error ? 'tuning-error' : 'tuning-success']">
                <span v-if="tuningResults[vm.vmid].error">❌ {{ tuningResults[vm.vmid].error }}</span>
                <span v-else>✅ Analysis complete</span>
              </div>
              <div v-if="tuningResults[vm.vmid].recommendations" class="tuning-recs">
                <h4>Recommendations</h4>
                <pre class="tuning-output">{{ tuningResults[vm.vmid].recommendations }}</pre>
              </div>
              <!-- Applicable actions -->
              <div v-if="tuningResults[vm.vmid].actions?.length" class="tuning-actions">
                <h4>Apply Recommendations</h4>
                <div v-for="action in tuningResults[vm.vmid].actions" :key="action.id" class="tune-action-card">
                  <div class="tune-action-info">
                    <strong>{{ action.label }}</strong>
                    <p class="text-sm text-muted">{{ action.description }}</p>
                  </div>
                  <div class="tune-action-result" v-if="applyResults[vm.vmid]?.[action.id]">
                    <span v-if="applyResults[vm.vmid][action.id].ok" class="text-success text-sm">✅ Applied</span>
                    <span v-else class="text-danger text-sm">❌ {{ applyResults[vm.vmid][action.id].error }}</span>
                  </div>
                  <button
                    @click="applyTuneAction(vm, action.id)"
                    class="btn btn-sm btn-primary"
                    :disabled="applyingAction[vm.vmid] === action.id || applyResults[vm.vmid]?.[action.id]?.ok"
                  >
                    {{ applyingAction[vm.vmid] === action.id ? 'Applying...' : applyResults[vm.vmid]?.[action.id]?.ok ? 'Applied' : 'Apply' }}
                  </button>
                </div>
                <!-- Live apply terminal -->
                <div v-if="tuneApplyJobs[vm.vmid]" class="live-log-panel" style="margin-top:0.75rem">
                  <div class="live-log-header">
                    <span class="live-log-title">
                      <span v-if="tuneApplyJobs[vm.vmid].status === 'running'" class="live-dot"></span>
                      {{ tuneApplyJobs[vm.vmid].action || 'Applying…' }}
                    </span>
                    <div class="live-log-meta">
                      <span v-if="tuneApplyJobs[vm.vmid].status === 'completed'" class="text-success text-sm">✅ Done</span>
                      <span v-else-if="tuneApplyJobs[vm.vmid].status === 'failed'" class="text-danger text-sm">
                        ❌ {{ tuneApplyJobs[vm.vmid].error || 'Failed' }}
                      </span>
                      <span :class="['badge', tuneApplyJobs[vm.vmid].status === 'completed' ? 'badge-success' : tuneApplyJobs[vm.vmid].status === 'failed' ? 'badge-danger' : 'badge-warning']">
                        {{ tuneApplyJobs[vm.vmid].status }}
                      </span>
                      <button class="btn btn-xs" @click="closeTuneApplyLog(vm.vmid)" style="margin-left:0.5rem">✕</button>
                    </div>
                  </div>
                  <pre class="live-log-output" :id="`tuneapply-${vm.vmid}`">{{ tuneApplyJobs[vm.vmid].output || 'Starting…' }}</pre>
                </div>
              </div>
            </div>

            <!-- ── Ollama Model Manager (Ollama deployments only) ── -->
            <div v-if="getLLMDeployment(vm.vmid)?.engine === 'ollama'" class="model-manager">
              <div class="model-section-header">
                <h4>Installed Models</h4>
                <button
                  @click="loadVMModels(vm)"
                  class="btn btn-sm btn-outline"
                  :disabled="loadingModels[vm.vmid] || vm.status !== 'running'"
                >{{ loadingModels[vm.vmid] ? 'Loading...' : 'Refresh' }}</button>
              </div>

              <div v-if="vmModels[vm.vmid]?.length" class="model-list">
                <div v-for="model in vmModels[vm.vmid]" :key="model.name" class="model-row">
                  <span class="model-name mono">{{ model.name }}</span>
                  <span class="model-size text-sm text-muted">{{ model.size }}</span>
                  <span class="model-modified text-sm text-muted">{{ model.modified }}</span>
                  <button
                    @click="deleteModel(vm, model.name)"
                    class="btn btn-sm btn-danger-outline"
                    :disabled="deletingModel[vm.vmid] === model.name"
                  >{{ deletingModel[vm.vmid] === model.name ? '...' : 'Delete' }}</button>
                </div>
              </div>
              <div v-else-if="loadingModels[vm.vmid]" class="text-sm text-muted model-loading">Loading models...</div>
              <div v-else-if="vmModels[vm.vmid]" class="text-sm text-muted model-loading">No models installed.</div>
              <div v-else class="text-sm text-muted model-loading">Click Refresh to load installed models.</div>

              <div class="pull-section">
                <h4>Pull New Model</h4>
                <div class="pull-controls">
                  <select v-model="selectedPullModel[vm.vmid]" class="pull-select">
                    <option value="">Select a model...</option>
                    <option v-for="m in ollamaCatalog" :key="m.id" :value="m.id">
                      {{ m.name }}
                    </option>
                  </select>
                  <button
                    @click="pullModel(vm)"
                    class="btn btn-primary"
                    :disabled="!selectedPullModel[vm.vmid] || pullJobs[vm.vmid]?.status === 'running' || vm.status !== 'running'"
                  >Pull Model</button>
                </div>

                <!-- Live pull terminal -->
                <div v-if="pullJobs[vm.vmid]" class="live-log-panel" style="margin-top:0.75rem">
                  <div class="live-log-header">
                    <span class="live-log-title">
                      <span v-if="pullJobs[vm.vmid].status === 'running'" class="live-dot"></span>
                      Pulling {{ pullJobs[vm.vmid].model }}...
                    </span>
                    <div class="live-log-meta">
                      <span v-if="pullJobs[vm.vmid].status === 'completed'" class="text-success text-sm">✅ Done</span>
                      <span v-else-if="pullJobs[vm.vmid].status === 'failed'" class="text-danger text-sm">
                        ❌ {{ pullJobs[vm.vmid].error || 'Failed' }}
                      </span>
                      <span :class="['badge', pullJobs[vm.vmid].status === 'completed' ? 'badge-success' : pullJobs[vm.vmid].status === 'failed' ? 'badge-danger' : 'badge-warning']">
                        {{ pullJobs[vm.vmid].status }}
                      </span>
                      <button class="btn btn-xs" @click="closePullLog(vm.vmid)" style="margin-left:0.5rem">✕</button>
                    </div>
                  </div>
                  <pre class="live-log-output" :id="`pulllog-${vm.vmid}`">{{ pullJobs[vm.vmid].output || 'Starting...' }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'VMManagement',
  setup() {
    const toast = useToast()

    const activeTab = ref('fleet')
    const vms = ref([])          // Proxmox live VMs (display)
    const managedVMs = ref([])   // Depl0y DB VMs (for update/credential operations)
    const loadingVMs = ref(false)
    const loadingMonitor = ref(false)
    const expandedVM = ref(null)
    const updatingVM = ref(null)
    const updateAction = ref(null)
    const updateChecks = ref({})
    const updateHistory = ref({})
    const loadingHistory = ref({})
    const tuningVM = ref(null)
    const tuningResults = ref({})
    const applyingAction = ref({})   // vmid → action_id being applied
    const applyResults = ref({})     // vmid → { action_id → { ok, error } }
    const tuneApplyJobs = ref({})    // vmid → { jobId, status, output, error, actionId }
    const tuneApplyPollers = ref({}) // vmid → interval ID
    const liveLog = ref({})         // vmid → { status, output, packages_updated, error_message }
    const liveLogPollers = ref({})  // vmid → interval ID
    const llmDeployments = ref([])   // LLM deployment records
    const vmModels = ref({})         // vmid → [{name, size, modified}]
    const loadingModels = ref({})    // vmid → bool
    const deletingModel = ref({})    // vmid → model name being deleted
    const pullJobs = ref({})         // vmid → {jobId, model, status, output, error}
    const pullPollers = ref({})      // vmid → interval ID
    const selectedPullModel = ref({})// vmid → model id string
    const ollamaCatalog = ref([])    // populated from API
    // Conversation Logging
    const convLogVM = ref(null)          // selected vm for conv-log tab
    const convLogStatus = ref({})        // vmid → {installed, active, log_entries}
    const convLogEntries = ref([])       // entries for selected VM
    const convLogLoading = ref(false)
    const convLogInstallJobs = ref({})   // vmid → jobId
    const convLogInstallPollers = ref({})

    // RAG
    const ragVM = ref(null)             // selected vm for rag tab
    const ragStatus = ref({})           // vmid → {installed, active, doc_count, catalog}
    const ragDocs = ref([])             // docs for selected VM
    const ragLoading = ref(false)
    const ragIngestText = ref('')
    const ragIngestSource = ref('')
    const ragQueryText = ref('')
    const ragQueryResults = ref([])
    const ragInstallJobs = ref({})      // vmid → jobId
    const ragInstallPollers = ref({})
    const ragSelectedEmbed = ref('nomic-embed-text')

    // Unmanaged VMs (Proxmox VMs not tracked by Depl0y)
    const unmanagedVMs = ref([])
    const loadingUnmanaged = ref(false)
    const unmanagedExpanded = ref(false)
    const adoptingVMs = ref(new Set()) // set of vmids currently being adopted

    const adoptVm = async (vm) => {
      const key = `${vm.hostId}-${vm.vmid}`
      adoptingVMs.value = new Set([...adoptingVMs.value, key])
      try {
        await api.vms.adoptVm({
          vmid: vm.vmid,
          name: vm.name,
          node: vm.node,
          proxmox_host_id: vm.hostId,
          status: vm.status,
          cpu_cores: vm.maxcpu || 1,
          memory_mb: vm.maxmem ? Math.round(vm.maxmem / 1024 / 1024) : 512,
        })
        unmanagedVMs.value = unmanagedVMs.value.filter(v => !(v.vmid === vm.vmid && v.hostId === vm.hostId))
        toast.success('VM adopted into Depl0y')
        // Refresh managed VMs list so the adopted VM appears
        await loadVMs()
      } catch (err) {
        const msg = err?.response?.data?.detail || 'Failed to adopt VM'
        toast.error(msg)
      } finally {
        const next = new Set(adoptingVMs.value)
        next.delete(key)
        adoptingVMs.value = next
      }
    }

    const loadUnmanagedVMs = async () => {
      loadingUnmanaged.value = true
      try {
        const hostsRes = await api.proxmox.listHosts().catch(() => ({ data: [] }))
        const hosts = hostsRes.data || []
        const allPveVMs = []
        await Promise.all(hosts.map(async (host) => {
          try {
            const res = await api.pveNode.clusterResources(host.id, 'vm')
            const items = res.data || []
            items.forEach(item => {
              allPveVMs.push({
                vmid: item.vmid,
                name: item.name,
                status: item.status,
                node: item.node,
                hostId: host.id,
                hostName: host.name || host.host,
                maxcpu: item.maxcpu || item.cpus || 1,
                maxmem: item.maxmem || 0,
              })
            })
          } catch { /* skip unreachable hosts */ }
        }))
        // Filter out VMs already managed by Depl0y (match by vmid)
        const managedVmids = new Set(managedVMs.value.map(m => Number(m.vmid)))
        unmanagedVMs.value = allPveVMs.filter(vm => !managedVmids.has(Number(vm.vmid)))
      } catch {
        toast.error('Failed to load Proxmox VMs')
      } finally {
        loadingUnmanaged.value = false
      }
    }

    const schedule = ref({
      auto_update_check_enabled: false,
      auto_update_check_interval_hours: 24,
      auto_security_scan_enabled: false,
      auto_security_scan_interval_hours: 24,
    })
    const scanCache = ref([])       // flat array from /updates/cache
    const credModal = ref({ show: false, vm: null })
    const credForm = ref({ ip_address: '', username: '', password: '', saveToDb: true })
    const savingCreds = ref(false)
    const fetchingIP = ref(false)
    const sessionCreds = ref({})   // vmid → { ip_address, username, password } for session-only creds
    const scanResults = ref({})    // vmid → scan result object
    const scanning = ref(null)     // vmid currently being scanned
    const scanExpanded = ref({})   // vmid → bool
    const search = ref('')
    const statusFilterMgmt = ref('')
    const sortKey = ref('name')
    const sortDir = ref('asc')

    // Returns the DB-managed VM matching a Proxmox vmid (for update/SSH ops)
    // Uses Number() to safely compare regardless of whether vmid is string or integer
    const getManagedVM = (vmid) => {
      const id = Number(vmid)
      return managedVMs.value.find(m => Number(m.vmid) === id) || null
    }

    // Returns the scan cache entry for a DB vm id + scan type ("updates" or "security")
    const getCacheEntry = (vmDbId, scanType) => {
      if (!vmDbId) return null
      return scanCache.value.find(c => c.vm_id === vmDbId && c.scan_type === scanType) || null
    }

    // Returns the most recent update check result for display (manual check takes priority)
    const getUpdateResult = (vm) => {
      if (updateChecks.value[vm.vmid]) return updateChecks.value[vm.vmid]
      const managed = getManagedVM(vm.vmid)
      if (!managed) return null
      const cache = getCacheEntry(managed.id, 'updates')
      if (!cache) return null
      try { return JSON.parse(cache.result_json || '{}') } catch { return null }
    }

    const loadScheduleAndCache = async () => {
      try {
        const [schedRes, cacheRes] = await Promise.all([
          api.updates.getSchedule().catch(() => null),
          api.updates.getCache().catch(() => ({ data: [] })),
        ])
        if (schedRes?.data) Object.assign(schedule.value, schedRes.data)
        scanCache.value = cacheRes?.data || []
      } catch { /* non-critical */ }
    }

    const saveSchedule = async () => {
      try {
        await api.updates.saveSchedule({
          auto_update_check_enabled: schedule.value.auto_update_check_enabled,
          auto_update_check_interval_hours: schedule.value.auto_update_check_interval_hours,
          auto_security_scan_enabled: schedule.value.auto_security_scan_enabled,
          auto_security_scan_interval_hours: schedule.value.auto_security_scan_interval_hours,
        })
        toast.success('Schedule saved')
      } catch {
        toast.error('Failed to save schedule')
      }
    }

    const closeTuneApplyLog = (vmid) => {
      if (tuneApplyPollers.value[vmid]) {
        clearInterval(tuneApplyPollers.value[vmid])
        delete tuneApplyPollers.value[vmid]
      }
      delete tuneApplyJobs.value[vmid]
    }

    const closePullLog = (vmid) => {
      if (pullPollers.value[vmid]) {
        clearInterval(pullPollers.value[vmid])
        delete pullPollers.value[vmid]
      }
      delete pullJobs.value[vmid]
    }

    const loadVMModels = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      loadingModels.value = { ...loadingModels.value, [vm.vmid]: true }
      try {
        const res = await api.llm.getVMModels(managed.id)
        vmModels.value = { ...vmModels.value, [vm.vmid]: res.data.models || [] }
        if (res.data.catalog?.length) {
          ollamaCatalog.value = res.data.catalog
        }
      } catch (err) {
        toast.error(`Failed to load models: ${err.response?.data?.detail || err.message}`)
      } finally {
        loadingModels.value = { ...loadingModels.value, [vm.vmid]: false }
      }
    }

    const pullModel = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      const model = selectedPullModel.value[vm.vmid]
      if (!model) return
      closePullLog(vm.vmid)
      try {
        const res = await api.llm.pullModel(managed.id, model)
        const jobId = res.data.job_id
        pullJobs.value = { ...pullJobs.value, [vm.vmid]: { jobId, model, status: 'running', output: '', error: null } }
        pullPollers.value[vm.vmid] = setInterval(async () => {
          try {
            const poll = await api.llm.getPullJobStatus(managed.id, jobId)
            pullJobs.value = { ...pullJobs.value, [vm.vmid]: { ...pullJobs.value[vm.vmid], ...poll.data, model } }
            if (poll.data.status === 'completed') {
              clearInterval(pullPollers.value[vm.vmid])
              delete pullPollers.value[vm.vmid]
              toast.success(`Model ${model} pulled successfully`)
              await loadVMModels(vm)
            } else if (poll.data.status === 'failed') {
              clearInterval(pullPollers.value[vm.vmid])
              delete pullPollers.value[vm.vmid]
              toast.error(`Failed to pull model ${model}`)
            }
          } catch { /* non-fatal poll error */ }
        }, 1200)
      } catch (err) {
        toast.error(`Failed to start pull: ${err.response?.data?.detail || err.message}`)
      }
    }

    const deleteModel = async (vm, modelName) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      deletingModel.value = { ...deletingModel.value, [vm.vmid]: modelName }
      try {
        await api.llm.deleteModel(managed.id, modelName)
        toast.success(`Model ${modelName} deleted`)
        await loadVMModels(vm)
      } catch (err) {
        toast.error(`Failed to delete model: ${err.response?.data?.detail || err.message}`)
      } finally {
        deletingModel.value = { ...deletingModel.value, [vm.vmid]: null }
      }
    }

    const openMemeGenerator = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (managed?.ip_address) {
        window.open(`http://${managed.ip_address}:8189`, '_blank')
        return
      }
      if (vm.status === 'running' && vm.node) {
        try {
          const res = await api.vms.getAgentIP(vm.node, vm.vmid)
          if (res.data?.ip_address) {
            window.open(`http://${res.data.ip_address}:8189`, '_blank')
            return
          }
        } catch { /* agent not available */ }
      }
      toast.error('No IP address found for this VM — set SSH credentials first')
    }

    const applyTuneAction = async (vm, actionId) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      applyingAction.value = { ...applyingAction.value, [vm.vmid]: actionId }
      // Clear any previous log for this VM
      closeTuneApplyLog(vm.vmid)
      try {
        const res = await api.vmAgent.applyTuneAction(managed.id, actionId)
        const jobId = res.data.job_id
        // Open live terminal immediately
        tuneApplyJobs.value[vm.vmid] = { jobId, actionId, status: 'running', output: '', error: null }
        // Poll for progress
        tuneApplyPollers.value[vm.vmid] = setInterval(async () => {
          try {
            const poll = await api.vmAgent.getApplyJobStatus(managed.id, jobId)
            tuneApplyJobs.value[vm.vmid] = { ...tuneApplyJobs.value[vm.vmid], ...poll.data }
            if (poll.data.status === 'completed') {
              clearInterval(tuneApplyPollers.value[vm.vmid])
              delete tuneApplyPollers.value[vm.vmid]
              applyingAction.value = { ...applyingAction.value, [vm.vmid]: null }
              applyResults.value = {
                ...applyResults.value,
                [vm.vmid]: { ...(applyResults.value[vm.vmid] || {}), [actionId]: { ok: true } }
              }
              toast.success('Tuning action applied successfully')
            } else if (poll.data.status === 'failed') {
              clearInterval(tuneApplyPollers.value[vm.vmid])
              delete tuneApplyPollers.value[vm.vmid]
              applyingAction.value = { ...applyingAction.value, [vm.vmid]: null }
            }
          } catch { /* poll error — keep trying */ }
        }, 1200)
      } catch (err) {
        const msg = err.response?.data?.detail || 'Apply failed'
        applyResults.value = {
          ...applyResults.value,
          [vm.vmid]: { ...(applyResults.value[vm.vmid] || {}), [actionId]: { ok: false, error: msg } }
        }
        applyingAction.value = { ...applyingAction.value, [vm.vmid]: null }
      }
    }

    const setSort = (key) => {
      if (sortKey.value === key) {
        sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
      } else {
        sortKey.value = key
        sortDir.value = 'asc'
      }
    }

    const filteredVMs = computed(() => {
      const q = search.value.toLowerCase().trim()
      let list = q
        ? vms.value.filter(vm =>
            vm.name?.toLowerCase().includes(q) ||
            String(vm.vmid).includes(q) ||
            vm.node?.toLowerCase().includes(q) ||
            getManagedVM(vm.vmid)?.ip_address?.includes(q) ||
            getManagedVM(vm.vmid)?.os_type?.toLowerCase().includes(q)
          )
        : [...vms.value]

      if (statusFilterMgmt.value) {
        list = list.filter(vm => (vm.status || '').toLowerCase() === statusFilterMgmt.value)
      }

      list.sort((a, b) => {
        let av, bv
        if (sortKey.value === 'vmid') { av = Number(a.vmid); bv = Number(b.vmid) }
        else if (sortKey.value === 'ip') { av = getManagedVM(a.vmid)?.ip_address || ''; bv = getManagedVM(b.vmid)?.ip_address || '' }
        else if (sortKey.value === 'status') { av = a.status || ''; bv = b.status || '' }
        else { av = (a.name || '').toLowerCase(); bv = (b.name || '').toLowerCase() }
        if (av < bv) return sortDir.value === 'asc' ? -1 : 1
        if (av > bv) return sortDir.value === 'asc' ? 1 : -1
        return 0
      })
      return list
    })

    const sortIcon = (key) => {
      if (sortKey.value !== key) return '↕'
      return sortDir.value === 'asc' ? '↑' : '↓'
    }

    const tabs = computed(() => [
      { id: 'fleet', label: 'Fleet', icon: '🖥', badge: null },
      { id: 'updates', label: 'Updates', icon: '🔄', badge: null },
      { id: 'security', label: 'Security Scan', icon: '🔒', badge: null },
      { id: 'monitoring', label: 'Monitoring', icon: '📊', badge: null },
      { id: 'ai-tuning', label: 'AI Tuning', icon: '🤖', badge: null },
      { id: 'conv-logs', label: 'Conv. Logs', icon: '💬', badge: null },
      { id: 'rag', label: 'RAG', icon: '📚', badge: null },
    ])

    const getLLMDeployment = (vmid) => {
      const managed = getManagedVM(vmid)
      if (!managed) return null
      return llmDeployments.value.find(d => d.vm_id === managed.id) || null
    }

    const llmVMs = computed(() =>
      vms.value.filter(vm =>
        vm.name?.toLowerCase().includes('llm') ||
        vm.name?.toLowerCase().includes('ollama') ||
        vm.name?.toLowerCase().includes('comfyui') ||
        vm.name?.toLowerCase().includes('stable-diffusion') ||
        vm.name?.toLowerCase().includes('meme') ||
        vm.tags?.includes('llm') ||
        llmDeployments.value.some(d => {
          const managed = getManagedVM(vm.vmid)
          return managed && d.vm_id === managed.id
        })
      )
    )

    const loadVMs = async () => {
      loadingVMs.value = true
      try {
        const [proxmoxRes, managedRes, deplRes] = await Promise.all([
          api.vms.list().catch(() => ({ data: [] })),
          api.vms.listManaged().catch(() => ({ data: [] })),
          api.llm.listDeployments().catch(() => ({ data: [] })),
        ])
        vms.value = proxmoxRes.data || []
        managedVMs.value = managedRes.data || []
        llmDeployments.value = deplRes.data || []
      } catch {
        toast.error('Failed to load VMs')
      } finally {
        loadingVMs.value = false
      }
    }

    const openCredModal = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      const sess = sessionCreds.value[vm.vmid]
      credModal.value = { show: true, vm, managed }
      credForm.value = {
        ip_address: managed?.ip_address || sess?.ip_address || '',
        username: managed?.username || sess?.username || '',
        password: '',
        saveToDb: !!managed,  // can only save to DB if there's a managed record
      }
      // If no IP stored anywhere and VM is running, auto-fetch from QEMU guest agent
      if (!credForm.value.ip_address && vm.status === 'running' && vm.node) {
        fetchingIP.value = true
        try {
          const res = await api.vms.getAgentIP(vm.node, vm.vmid)
          if (res.data?.ip_address) {
            credForm.value.ip_address = res.data.ip_address
          }
        } catch { /* agent not available or not running — field stays blank */ }
        finally { fetchingIP.value = false }
      }
    }

    const saveCredentials = async () => {
      const { vm, managed } = credModal.value
      const { ip_address, username, password, saveToDb } = credForm.value

      if (saveToDb) {
        if (!managed) {
          toast.error('This VM is not managed by Depl0y — uncheck "Save credentials" to use for this session only')
          return
        }
        savingCreds.value = true
        try {
          const payload = { ip_address, username }
          if (password) payload.password = password
          await api.vms.update(managed.id, payload)
          toast.success('Credentials saved (encrypted)')
          credModal.value.show = false
          await loadVMs()
        } catch {
          toast.error('Failed to save credentials')
        } finally {
          savingCreds.value = false
        }
      } else {
        // Session-only: store in memory, never sent to DB
        sessionCreds.value[vm.vmid] = {
          ip_address,
          username,
          password: password || undefined,
        }
        toast.success('Credentials stored for this session only')
        credModal.value.show = false
      }
    }

    const loadMonitoring = async () => {
      loadingMonitor.value = true
      await loadVMs()
      loadingMonitor.value = false
    }

    const getSessionCreds = (vmid) => {
      const s = sessionCreds.value[vmid]
      if (!s) return null
      return { ip_address: s.ip_address || undefined, username: s.username || undefined, password: s.password || undefined }
    }

    const checkUpdates = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      updatingVM.value = vm.vmid
      updateAction.value = 'check'
      try {
        const response = await api.updates.check(managed.id, getSessionCreds(vm.vmid))
        updateChecks.value[vm.vmid] = response.data
        toast.success(`Update check complete for ${vm.name}`)
      } catch {
        toast.error(`Failed to check updates for ${vm.name}`)
      } finally {
        updatingVM.value = null
        updateAction.value = null
      }
    }

    const closeLiveLog = (vmid) => {
      if (liveLogPollers.value[vmid]) {
        clearInterval(liveLogPollers.value[vmid])
        delete liveLogPollers.value[vmid]
      }
      delete liveLog.value[vmid]
    }

    const startLiveMonitor = (vm, managedId) => {
      closeLiveLog(vm.vmid)
      liveLog.value[vm.vmid] = { status: 'running', output: '', packages_updated: 0, error_message: null }
      const poll = async () => {
        try {
          const res = await api.updates.currentLog(managedId)
          liveLog.value[vm.vmid] = res.data
          if (res.data.status === 'completed' || res.data.status === 'failed') {
            clearInterval(liveLogPollers.value[vm.vmid])
            delete liveLogPollers.value[vm.vmid]
            // Refresh history if it was already open
            if (expandedVM.value === vm.vmid) {
              loadingHistory.value[vm.vmid] = true
              try {
                const h = await api.updates.getHistory(managedId)
                updateHistory.value[vm.vmid] = h.data
              } finally {
                loadingHistory.value[vm.vmid] = false
              }
            }
            if (res.data.status === 'completed') {
              toast.success(`Updates installed on ${vm.name} (${res.data.packages_updated} packages)`)
            } else {
              toast.error(`Update failed on ${vm.name} — see log below`)
            }
          }
        } catch { /* polling errors are non-fatal */ }
      }
      liveLogPollers.value[vm.vmid] = setInterval(poll, 1500)
      poll()
    }

    const installUpdates = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      updatingVM.value = vm.vmid
      updateAction.value = 'install'
      try {
        await api.updates.install(managed.id, getSessionCreds(vm.vmid))
        startLiveMonitor(vm, managed.id)
      } catch {
        toast.error(`Failed to start updates for ${vm.name}`)
      } finally {
        updatingVM.value = null
        updateAction.value = null
      }
    }

    const runScan = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      scanning.value = vm.vmid
      try {
        const response = await api.updates.scanSecurity(managed.id, getSessionCreds(vm.vmid))
        scanResults.value[vm.vmid] = response.data
        scanExpanded.value[vm.vmid] = true
        const sev = response.data.severity
        if (sev === 'critical') toast.error(`${vm.name}: critical security issues found`)
        else if (sev === 'warning') toast.warning(`${vm.name}: security warnings found`)
        else toast.success(`${vm.name}: scan complete — no critical issues`)
      } catch {
        toast.error(`Security scan failed for ${vm.name}`)
      } finally {
        scanning.value = null
      }
    }

    const toggleHistory = async (vmid) => {
      if (expandedVM.value === vmid) {
        expandedVM.value = null
        return
      }
      expandedVM.value = vmid
      const managed = getManagedVM(vmid)
      if (!managed) {
        updateHistory.value[vmid] = []
        return
      }
      if (!updateHistory.value[vmid]) {
        loadingHistory.value[vmid] = true
        try {
          const response = await api.updates.getHistory(managed.id)
          updateHistory.value[vmid] = response.data
        } catch {
          updateHistory.value[vmid] = []
        } finally {
          loadingHistory.value[vmid] = false
        }
      }
    }

    const runAITune = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      tuningVM.value = vm.vmid
      tuningResults.value[vm.vmid] = null
      try {
        const response = await api.vmAgent.runAITune(managed.id)
        tuningResults.value[vm.vmid] = response.data
        toast.success(`AI Tuning complete for ${vm.name}`)
      } catch (error) {
        tuningResults.value[vm.vmid] = {
          error: error.response?.data?.detail || 'Tuning failed — ensure the VM is running and SSH is accessible'
        }
      } finally {
        tuningVM.value = null
      }
    }

    // ── Conversation Logging ────────────────────────────────────────────────

    const llmOllamaVMs = computed(() =>
      llmVMs.value.filter(vm => {
        const dep = getLLMDeployment(vm.vmid)
        return dep && (dep.engine === 'ollama' || dep.engine === 'meme-maker')
      })
    )

    const selectConvLogVM = async (vm) => {
      convLogVM.value = vm
      convLogEntries.value = []
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      try {
        const res = await api.llm.getConvLoggerStatus(managed.id)
        convLogStatus.value = { ...convLogStatus.value, [vm.vmid]: res.data }
      } catch { /* ignore */ }
    }

    const loadConvLogs = async () => {
      const vm = convLogVM.value
      if (!vm) return
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      convLogLoading.value = true
      try {
        const res = await api.llm.getConvLogs(managed.id, 100)
        convLogEntries.value = (res.data.entries || []).reverse()
      } catch (err) {
        toast.error(`Failed to load logs: ${err.response?.data?.detail || err.message}`)
      } finally {
        convLogLoading.value = false
      }
    }

    const installConvLogger = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      try {
        const res = await api.llm.installConvLogger(managed.id)
        const jobId = res.data.job_id
        convLogInstallJobs.value[vm.vmid] = jobId
        // Show job in tuneApplyJobs so the live terminal renders
        tuneApplyJobs.value[vm.vmid] = { jobId, status: 'running', output: '', error: null, action: 'Install conversation logger' }
        convLogInstallPollers.value[vm.vmid] = setInterval(async () => {
          try {
            const poll = await api.llm.getJobStatus(managed.id, jobId)
            tuneApplyJobs.value[vm.vmid] = { ...tuneApplyJobs.value[vm.vmid], ...poll.data }
            if (poll.data.status === 'completed' || poll.data.status === 'failed') {
              clearInterval(convLogInstallPollers.value[vm.vmid])
              delete convLogInstallPollers.value[vm.vmid]
              if (poll.data.status === 'completed') {
                toast.success('Conversation logger installed')
                const s = await api.llm.getConvLoggerStatus(managed.id)
                convLogStatus.value = { ...convLogStatus.value, [vm.vmid]: s.data }
              } else {
                toast.error('Logger installation failed')
              }
            }
          } catch { /* ignore */ }
        }, 1500)
      } catch (err) {
        toast.error(`Install failed: ${err.response?.data?.detail || err.message}`)
      }
    }

    const clearConvLogs = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      try {
        await api.llm.clearConvLogs(managed.id)
        convLogEntries.value = []
        toast.success('Conversation logs cleared')
        const s = await api.llm.getConvLoggerStatus(managed.id)
        convLogStatus.value = { ...convLogStatus.value, [vm.vmid]: s.data }
      } catch (err) {
        toast.error(`Failed to clear: ${err.response?.data?.detail || err.message}`)
      }
    }

    // ── RAG ─────────────────────────────────────────────────────────────────

    const selectRagVM = async (vm) => {
      ragVM.value = vm
      ragDocs.value = []
      ragQueryResults.value = []
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      try {
        const res = await api.llm.getRagStatus(managed.id)
        ragStatus.value = { ...ragStatus.value, [vm.vmid]: res.data }
      } catch { /* ignore */ }
    }

    const installRag = async (vm) => {
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      try {
        const res = await api.llm.installRag(managed.id, ragSelectedEmbed.value)
        const jobId = res.data.job_id
        ragInstallJobs.value[vm.vmid] = jobId
        tuneApplyJobs.value[vm.vmid] = { jobId, status: 'running', output: '', error: null, action: 'Install RAG service' }
        ragInstallPollers.value[vm.vmid] = setInterval(async () => {
          try {
            const poll = await api.llm.getJobStatus(managed.id, jobId)
            tuneApplyJobs.value[vm.vmid] = { ...tuneApplyJobs.value[vm.vmid], ...poll.data }
            if (poll.data.status === 'completed' || poll.data.status === 'failed') {
              clearInterval(ragInstallPollers.value[vm.vmid])
              delete ragInstallPollers.value[vm.vmid]
              if (poll.data.status === 'completed') {
                toast.success('RAG service installed')
                const s = await api.llm.getRagStatus(managed.id)
                ragStatus.value = { ...ragStatus.value, [vm.vmid]: s.data }
              } else {
                toast.error('RAG installation failed — see log')
              }
            }
          } catch { /* ignore */ }
        }, 1500)
      } catch (err) {
        toast.error(`Install failed: ${err.response?.data?.detail || err.message}`)
      }
    }

    const loadRagDocs = async () => {
      const vm = ragVM.value
      if (!vm) return
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      ragLoading.value = true
      try {
        const res = await api.llm.ragListDocs(managed.id)
        ragDocs.value = res.data.docs || []
      } catch (err) {
        toast.error(`Failed to load docs: ${err.response?.data?.detail || err.message}`)
      } finally {
        ragLoading.value = false
      }
    }

    const ragIngestDoc = async () => {
      const vm = ragVM.value
      if (!vm || !ragIngestText.value.trim()) return
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      ragLoading.value = true
      try {
        await api.llm.ragIngest(managed.id, ragIngestText.value, ragIngestSource.value || 'manual', {})
        toast.success('Document ingested into knowledge base')
        ragIngestText.value = ''
        ragIngestSource.value = ''
        await loadRagDocs()
      } catch (err) {
        toast.error(`Ingest failed: ${err.response?.data?.detail || err.message}`)
      } finally {
        ragLoading.value = false
      }
    }

    const ragDoQuery = async () => {
      const vm = ragVM.value
      if (!vm || !ragQueryText.value.trim()) return
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      ragLoading.value = true
      try {
        const res = await api.llm.ragQuery(managed.id, ragQueryText.value)
        ragQueryResults.value = res.data.results || []
      } catch (err) {
        toast.error(`Query failed: ${err.response?.data?.detail || err.message}`)
      } finally {
        ragLoading.value = false
      }
    }

    const ragDeleteDoc = async (docId) => {
      const vm = ragVM.value
      if (!vm) return
      const managed = getManagedVM(vm.vmid)
      if (!managed) return
      try {
        await api.llm.ragDeleteDoc(managed.id, docId)
        toast.success('Document removed')
        await loadRagDocs()
      } catch (err) {
        toast.error(`Delete failed: ${err.response?.data?.detail || err.message}`)
      }
    }

    const getVMStatusBadge = (status) => {
      const map = {
        running: 'badge-success',
        stopped: 'badge-secondary',
        error: 'badge-danger',
        creating: 'badge-warning',
        deleting: 'badge-danger',
      }
      return map[status] || 'badge-secondary'
    }

    const formatDate = (dt) => dt ? new Date(dt).toLocaleString() : '—'

    // For Proxmox live data (maxmem, maxdisk are in bytes)
    const formatBytes = (bytes) => {
      if (!bytes) return '—'
      const gb = bytes / (1024 * 1024 * 1024)
      if (gb >= 1) return `${gb.toFixed(1)} GB`
      return `${(bytes / (1024 * 1024)).toFixed(0)} MB`
    }

    // Legacy: for DB VMs that store memory in MB
    const formatMB = (mb) => {
      if (!mb) return '—'
      return mb >= 1024 ? `${(mb / 1024).toFixed(0)} GB` : `${mb} MB`
    }

    // Auto-scroll live log terminals to bottom when output updates
    watch(liveLog, () => {
      nextTick(() => {
        Object.keys(liveLog.value).forEach(vmid => {
          const el = document.getElementById(`livelog-${vmid}`)
          if (el) el.scrollTop = el.scrollHeight
        })
      })
    }, { deep: true })

    // Clean up pollers on unmount
    // Auto-scroll tune apply terminal
    watch(tuneApplyJobs, () => {
      nextTick(() => {
        Object.keys(tuneApplyJobs.value).forEach(vmid => {
          const el = document.getElementById(`tuneapply-${vmid}`)
          if (el) el.scrollTop = el.scrollHeight
        })
      })
    }, { deep: true })

    // Auto-scroll pull log terminal
    watch(pullJobs, () => {
      nextTick(() => {
        Object.keys(pullJobs.value).forEach(vmid => {
          const el = document.getElementById(`pulllog-${vmid}`)
          if (el) el.scrollTop = el.scrollHeight
        })
      })
    }, { deep: true })

    // Lazy-load unmanaged VMs when section is first expanded
    watch(unmanagedExpanded, (val) => {
      if (val && unmanagedVMs.value.length === 0 && !loadingUnmanaged.value) {
        loadUnmanagedVMs()
      }
    })

    onUnmounted(() => {
      Object.values(liveLogPollers.value).forEach(id => clearInterval(id))
      Object.values(tuneApplyPollers.value).forEach(id => clearInterval(id))
      Object.values(pullPollers.value).forEach(id => clearInterval(id))
    })

    onMounted(() => {
      loadVMs()
      loadScheduleAndCache()
    })

    // ── FLEET TAB ───────────────────────────────────────────────────────────
    // Proxmox hosts + VMs for the fleet table
    const fleetVMs = ref([])
    const fleetLoading = ref(false)
    const fleetError = ref(null)

    const fleetSearch = ref('')
    const fleetSortKey = ref('vmid')
    const fleetSortDir = ref('asc')

    // Quick filter presets
    const fleetQuickFilter = ref('')  // '', 'no-backups', 'has-snapshots', 'protected', 'high-cpu', 'high-ram'

    const loadFleetVMs = async () => {
      fleetLoading.value = true
      fleetError.value = null
      try {
        const hostsResp = await api.proxmox.listHosts()
        const hosts = hostsResp.data || []
        if (!hosts.length) { fleetVMs.value = []; return }

        const results = []
        await Promise.allSettled(hosts.map(async (host) => {
          try {
            const resResp = await api.pveNode.clusterResources(host.id, 'vm')
            const items = Array.isArray(resResp.data) ? resResp.data : (resResp.data?.data || [])
            await Promise.allSettled(items.filter(i => !i.type || i.type === 'qemu').map(async (item) => {
              let snapshotCount = 0
              let isProtected = false
              let isLocked = false
              let configData = null
              let description = ''
              let notes = ''
              try {
                const cfgResp = await api.pveVm.getConfig(host.id, item.node, item.vmid)
                configData = cfgResp.data || {}
                isProtected = !!configData.protection
                isLocked = !!(configData.lock)
                description = configData.description || ''
                notes = configData.description || ''
              } catch {}
              try {
                const snapResp = await api.pveVm.listSnapshots(host.id, item.node, item.vmid)
                const snaps = Array.isArray(snapResp.data) ? snapResp.data : []
                snapshotCount = snaps.filter(s => s.name !== 'current').length
              } catch {}
              results.push({
                hostId: host.id,
                hostName: host.name || host.host || String(host.id),
                node: item.node,
                vmid: item.vmid,
                name: item.name || '',
                status: item.status || 'unknown',
                cpus: item.cpus || 0,
                maxmem: item.maxmem || 0,
                mem: item.mem || 0,
                maxdisk: item.maxdisk || 0,
                uptime: item.uptime || 0,
                cpu: item.cpu || 0,   // current CPU usage fraction
                tags: item.tags || '',
                description,
                notes,
                snapshotCount,
                isProtected,
                isLocked,
                lastBackup: null,   // not available from cluster resources
                _busy: false,
                _selected: false,
              })
            }))
          } catch (err) {
            console.warn('Fleet load failed for host', host.id, err)
          }
        }))
        fleetVMs.value = results
      } catch (err) {
        fleetError.value = 'Failed to load hosts'
      } finally {
        fleetLoading.value = false
      }
    }

    const fleetSortBy = (key) => {
      if (fleetSortKey.value === key) fleetSortDir.value = fleetSortDir.value === 'asc' ? 'desc' : 'asc'
      else { fleetSortKey.value = key; fleetSortDir.value = 'asc' }
    }
    const fleetSortIcon = (key) => {
      if (fleetSortKey.value !== key) return '↕'
      return fleetSortDir.value === 'asc' ? '↑' : '↓'
    }

    const filteredFleetVMs = computed(() => {
      let list = fleetVMs.value
      // quick filter
      if (fleetQuickFilter.value === 'no-backups') list = list.filter(v => !v.lastBackup)
      else if (fleetQuickFilter.value === 'has-snapshots') list = list.filter(v => v.snapshotCount > 0)
      else if (fleetQuickFilter.value === 'protected') list = list.filter(v => v.isProtected)
      else if (fleetQuickFilter.value === 'high-cpu') list = list.filter(v => (v.cpu || 0) > 0.8)
      else if (fleetQuickFilter.value === 'high-ram') list = list.filter(v => v.maxmem > 0 && v.mem / v.maxmem > 0.8)

      if (fleetSearch.value.trim()) {
        const q = fleetSearch.value.trim().toLowerCase()
        list = list.filter(v =>
          (v.name || '').toLowerCase().includes(q) ||
          String(v.vmid).includes(q) ||
          (v.node || '').toLowerCase().includes(q) ||
          (v.tags || '').toLowerCase().includes(q)
        )
      }
      const key = fleetSortKey.value
      const dir = fleetSortDir.value
      return [...list].sort((a, b) => {
        let av = a[key] ?? ''; let bv = b[key] ?? ''
        if (typeof av === 'string') { av = av.toLowerCase(); bv = bv.toLowerCase() }
        if (dir === 'asc') return av > bv ? 1 : av < bv ? -1 : 0
        return av < bv ? 1 : av > bv ? -1 : 0
      })
    })

    // Fleet selection
    const fleetSelectedKeys = ref(new Set())
    const fleetVmKey = (vm) => `${vm.hostId}:${vm.node}:${vm.vmid}`
    const toggleFleetSelect = (vm) => {
      const k = fleetVmKey(vm)
      const s = new Set(fleetSelectedKeys.value)
      if (s.has(k)) s.delete(k); else s.add(k)
      fleetSelectedKeys.value = s
    }
    const fleetAllSelected = computed(() =>
      filteredFleetVMs.value.length > 0 && filteredFleetVMs.value.every(v => fleetSelectedKeys.value.has(fleetVmKey(v)))
    )
    const fleetSomeSelected = computed(() => filteredFleetVMs.value.some(v => fleetSelectedKeys.value.has(fleetVmKey(v))))
    const toggleFleetSelectAll = () => {
      const s = new Set(fleetSelectedKeys.value)
      if (fleetAllSelected.value) filteredFleetVMs.value.forEach(v => s.delete(fleetVmKey(v)))
      else filteredFleetVMs.value.forEach(v => s.add(fleetVmKey(v)))
      fleetSelectedKeys.value = s
    }
    const clearFleetSelection = () => { fleetSelectedKeys.value = new Set() }
    const fleetSelectedVMs = computed(() => fleetVMs.value.filter(v => fleetSelectedKeys.value.has(fleetVmKey(v))))

    // ── Quick Edit Drawer ───────────────────────────────────────────────────
    const showQuickEdit = ref(false)
    const quickEditVM = ref(null)
    const quickEditForm = ref({ name: '', description: '', onboot: false, protection: false })
    const quickEditSaving = ref(false)

    const openQuickEdit = (vm) => {
      quickEditVM.value = vm
      quickEditForm.value = {
        name: vm.name || '',
        description: vm.description || '',
        onboot: false,
        protection: vm.isProtected || false,
      }
      // Try to get onboot from config (may already be in vm object)
      showQuickEdit.value = true
    }

    const closeQuickEdit = () => {
      showQuickEdit.value = false
      quickEditVM.value = null
    }

    const saveQuickEdit = async () => {
      if (!quickEditVM.value) return
      quickEditSaving.value = true
      const vm = quickEditVM.value
      try {
        const payload = {}
        if (quickEditForm.value.name !== vm.name) payload.name = quickEditForm.value.name
        payload.description = quickEditForm.value.description
        payload.onboot = quickEditForm.value.onboot ? 1 : 0
        payload.protection = quickEditForm.value.protection ? 1 : 0
        await api.pveVm.updateConfig(vm.hostId, vm.node, vm.vmid, payload)
        // Update local data
        vm.name = quickEditForm.value.name || vm.name
        vm.description = quickEditForm.value.description
        vm.isProtected = quickEditForm.value.protection
        toast.success(`VM ${vm.vmid} updated`)
        closeQuickEdit()
      } catch (err) {
        toast.error(`Failed to update VM: ${err.response?.data?.detail || err.message}`)
      } finally {
        quickEditSaving.value = false
      }
    }

    // ── Batch Tag Operations ────────────────────────────────────────────────
    const showBatchTagModal = ref(false)
    const batchTagMode = ref('add')  // 'add' or 'remove'
    const batchTagValue = ref('')
    const batchTagRunning = ref(false)
    const batchTagResults = ref([])
    const batchTagDone = ref(false)

    const openBatchTagModal = (mode) => {
      batchTagMode.value = mode
      batchTagValue.value = ''
      batchTagResults.value = []
      batchTagDone.value = false
      showBatchTagModal.value = true
    }

    const runBatchTag = async () => {
      const tag = batchTagValue.value.trim()
      if (!tag) return
      const vmsToTag = fleetSelectedVMs.value
      batchTagRunning.value = true
      batchTagResults.value = vmsToTag.map(v => ({ key: fleetVmKey(v), vmid: v.vmid, name: v.name, node: v.node, hostId: v.hostId, status: 'pending', error: null }))
      for (let i = 0; i < batchTagResults.value.length; i++) {
        batchTagResults.value[i] = { ...batchTagResults.value[i], status: 'running' }
        const r = batchTagResults.value[i]
        try {
          const cfgRes = await api.pveVm.getConfig(r.hostId, r.node, r.vmid)
          const current = cfgRes.data?.tags || ''
          let arr = current ? current.split(';').map(t => t.trim()).filter(Boolean) : []
          if (batchTagMode.value === 'add') { if (!arr.includes(tag)) arr.push(tag) }
          else { arr = arr.filter(t => t !== tag) }
          await api.pveVm.updateConfig(r.hostId, r.node, r.vmid, { tags: arr.join(';') })
          // update local
          const vm = fleetVMs.value.find(v => fleetVmKey(v) === r.key)
          if (vm) vm.tags = arr.join(';')
          batchTagResults.value[i] = { ...batchTagResults.value[i], status: 'success' }
        } catch (err) {
          const msg = err.response?.data?.detail || err.message
          batchTagResults.value[i] = { ...batchTagResults.value[i], status: 'error', error: msg }
        }
        if (i < batchTagResults.value.length - 1) await new Promise(r => setTimeout(r, 200))
      }
      batchTagRunning.value = false
      batchTagDone.value = true
    }

    const closeBatchTagModal = () => {
      showBatchTagModal.value = false
      batchTagResults.value = []
      batchTagDone.value = false
    }

    // ── Batch Notes ─────────────────────────────────────────────────────────
    const showBatchNotesModal = ref(false)
    const batchNotesText = ref('')
    const batchNotesMode = ref('append')  // 'replace' or 'append'
    const batchNotesRunning = ref(false)
    const batchNotesDone = ref(false)
    const batchNotesResults = ref([])

    const openBatchNotesModal = () => {
      batchNotesText.value = ''
      batchNotesMode.value = 'append'
      batchNotesResults.value = []
      batchNotesDone.value = false
      showBatchNotesModal.value = true
    }

    const runBatchNotes = async () => {
      const text = batchNotesText.value.trim()
      const vmsToNote = fleetSelectedVMs.value
      batchNotesRunning.value = true
      batchNotesResults.value = vmsToNote.map(v => ({ key: fleetVmKey(v), vmid: v.vmid, name: v.name, node: v.node, hostId: v.hostId, status: 'pending', error: null }))
      for (let i = 0; i < batchNotesResults.value.length; i++) {
        batchNotesResults.value[i] = { ...batchNotesResults.value[i], status: 'running' }
        const r = batchNotesResults.value[i]
        try {
          let finalDesc = text
          if (batchNotesMode.value === 'append') {
            const cfgRes = await api.pveVm.getConfig(r.hostId, r.node, r.vmid)
            const existing = cfgRes.data?.description || ''
            finalDesc = existing ? `${existing}\n${text}` : text
          }
          await api.pveVm.updateConfig(r.hostId, r.node, r.vmid, { description: finalDesc })
          const vm = fleetVMs.value.find(v => fleetVmKey(v) === r.key)
          if (vm) vm.description = finalDesc
          batchNotesResults.value[i] = { ...batchNotesResults.value[i], status: 'success' }
        } catch (err) {
          const msg = err.response?.data?.detail || err.message
          batchNotesResults.value[i] = { ...batchNotesResults.value[i], status: 'error', error: msg }
        }
        if (i < batchNotesResults.value.length - 1) await new Promise(r => setTimeout(r, 200))
      }
      batchNotesRunning.value = false
      batchNotesDone.value = true
    }

    const closeBatchNotesModal = () => {
      showBatchNotesModal.value = false
      batchNotesResults.value = []
      batchNotesDone.value = false
    }

    // Fleet helpers
    const fleetFormatBytes = (bytes) => {
      if (!bytes) return '—'
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
    }
    const fleetFormatUptime = (secs) => {
      if (!secs || secs <= 0) return '—'
      const d = Math.floor(secs / 86400), h = Math.floor((secs % 86400) / 3600), m = Math.floor((secs % 3600) / 60)
      if (d > 0) return `${d}d ${h}h`; if (h > 0) return `${h}h ${m}m`; return `${m}m`
    }
    const fleetParseTags = (t) => { if (!t) return []; return t.split(';').map(x => x.trim()).filter(Boolean) }

    return {
      activeTab, tabs, vms, loadingVMs, loadingMonitor,
      expandedVM, updatingVM, updateAction, updateChecks,
      updateHistory, loadingHistory, tuningVM, tuningResults, llmVMs, llmOllamaVMs,
      applyingAction, applyResults, applyTuneAction,
      tuneApplyJobs, closeTuneApplyLog,
      liveLog, closeLiveLog,
      loadVMs, loadMonitoring, checkUpdates, installUpdates,
      toggleHistory, runAITune, getManagedVM, getLLMDeployment,
      runScan, scanResults, scanning, scanExpanded,
      getVMStatusBadge, formatDate, formatBytes, formatMB,
      credModal, credForm, savingCreds, fetchingIP, openCredModal, saveCredentials, sessionCreds,
      search, statusFilterMgmt, sortKey, sortDir, filteredVMs, setSort, sortIcon,
      schedule, saveSchedule, scanCache, getCacheEntry, getUpdateResult,
      vmModels, loadingModels, deletingModel, loadVMModels,
      pullJobs, selectedPullModel, ollamaCatalog, pullModel, deleteModel, closePullLog,
      openMemeGenerator,
      // Conv Logs
      convLogVM, convLogStatus, convLogEntries, convLogLoading,
      selectConvLogVM, loadConvLogs, installConvLogger, clearConvLogs,
      // RAG
      ragVM, ragStatus, ragDocs, ragLoading, ragIngestText, ragIngestSource,
      ragQueryText, ragQueryResults, ragSelectedEmbed,
      selectRagVM, installRag, loadRagDocs, ragIngestDoc, ragDoQuery, ragDeleteDoc,
      // Unmanaged VMs
      unmanagedVMs, loadingUnmanaged, unmanagedExpanded, loadUnmanagedVMs,
      adoptingVMs, adoptVm,
      // Fleet tab
      fleetVMs, fleetLoading, fleetError, fleetSearch, fleetSortKey, fleetSortDir,
      fleetQuickFilter, loadFleetVMs, filteredFleetVMs, fleetSortBy, fleetSortIcon,
      fleetSelectedKeys, fleetVmKey, toggleFleetSelect, fleetAllSelected, fleetSomeSelected,
      toggleFleetSelectAll, clearFleetSelection, fleetSelectedVMs,
      showQuickEdit, quickEditVM, quickEditForm, quickEditSaving, openQuickEdit, closeQuickEdit, saveQuickEdit,
      showBatchTagModal, batchTagMode, batchTagValue, batchTagRunning, batchTagResults, batchTagDone,
      openBatchTagModal, runBatchTag, closeBatchTagModal,
      showBatchNotesModal, batchNotesText, batchNotesMode, batchNotesRunning, batchNotesDone, batchNotesResults,
      openBatchNotesModal, runBatchNotes, closeBatchNotesModal,
      fleetFormatBytes, fleetFormatUptime, fleetParseTags,
    }
  }
}
</script>

<style scoped>
.vm-management-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
}

/* Tabs */
.tab-nav {
  display: flex;
  gap: 0.25rem;
  background: var(--background);
  padding: 0.35rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  width: fit-content;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1.1rem;
  border: none;
  background: transparent;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all 0.15s;
}

.tab-btn:hover { color: var(--text-primary); background: white; }

.tab-btn.active {
  background: white;
  color: var(--text-primary);
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}

.tab-icon { font-size: 1rem; }

.tab-badge {
  background: #ef4444;
  color: white;
  font-size: 0.7rem;
  padding: 0 0.35rem;
  border-radius: 9999px;
  font-weight: 700;
}

/* Toolbar */
.table-toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
}

.search-input {
  flex: 1;
  max-width: 320px;
  padding: 0.45rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  background: var(--card-bg, #fff);
  color: var(--text-primary);
}

.search-input::placeholder {
  color: var(--text-muted, #8fa3b8);
  opacity: 1;
}

.search-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.15); outline: none; }

.search-input:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 0;
  border-color: #3b82f6;
}

/* Table */
.table-wrapper { overflow-x: auto; }

.th-sortable {
  cursor: pointer;
  user-select: none;
}
.th-sortable:hover { color: var(--text-primary); }

.sort-icon {
  font-size: 0.7rem;
  opacity: 0.6;
  margin-left: 0.2rem;
}

.mgmt-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.mgmt-table th {
  text-align: left;
  padding: 0.75rem 1rem;
  background: var(--background);
  border-bottom: 2px solid var(--border-color);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.mgmt-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: middle;
}

.row-expanded td { background: rgba(59, 130, 246, 0.04); }

.vm-name {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.action-btns { display: flex; gap: 0.4rem; flex-wrap: wrap; }

.result-row td { padding: 0.4rem 1rem 0.6rem; }

.update-result {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.85rem;
}

.has-updates { background: #fef3c7; color: #92400e; }
.up-to-date { background: #d1fae5; color: #065f46; }

/* History */
.history-row td { padding: 0; border-bottom: 2px solid var(--border-color); }
.history-panel { padding: 1rem 1.5rem; background: var(--background); }

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.history-table th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.75rem;
}

.history-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.log-output {
  margin: 0.5rem 0 0;
  padding: 0.5rem;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
}

.history-empty { color: var(--text-secondary); font-size: 0.9rem; padding: 0.5rem 0; }

/* Monitoring */
.monitor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
  padding: 1rem;
}

.monitor-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.monitor-specs { display: flex; flex-direction: column; gap: 0.4rem; }

.spec-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
}

.spec-label { color: var(--text-secondary); font-weight: 500; }

.spec-value { color: var(--text-primary); }

.monitor-meta {
  display: flex;
  justify-content: space-between;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-color);
}

.monitor-note { margin: 0 1rem 1rem; }

/* AI Tuning */
.ai-tuning-intro { margin: 0 0 1.5rem 0; }

.llm-vm-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
}

.llm-vm-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.llm-vm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.llm-vm-actions { display: flex; gap: 0.5rem; }

.tuning-results { margin-top: 0.5rem; }

.tuning-status {
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.tuning-success { background: #d1fae5; color: #065f46; }
.tuning-error { background: #fee2e2; color: #991b1b; }

.tuning-recs h4 { margin: 0 0 0.5rem; font-size: 0.9rem; }

.tuning-output {
  background: #1e293b;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 0.375rem;
  font-size: 0.8rem;
  white-space: pre-wrap;
  max-height: 300px;
  overflow-y: auto;
}

/* Credentials save row */
.cred-save-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
  margin-top: 0.25rem;
}

/* Live update progress terminal */
.live-log-row td { padding: 0; }
.live-log-panel {
  background: #0d1117;
  border-radius: 0;
  border-top: 2px solid var(--primary, #4f8ef7);
}
.live-log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 1rem;
  background: #161b22;
  border-bottom: 1px solid #30363d;
}
.live-log-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #c9d1d9;
  font-size: 0.875rem;
}
.live-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3fb950;
  animation: pulse 1.2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.live-log-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.live-log-output {
  margin: 0;
  padding: 0.75rem 1rem;
  max-height: 280px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  color: #c9d1d9;
  white-space: pre-wrap;
  word-break: break-all;
  background: transparent;
}
.phasing-note {
  padding: 0.5rem 1rem;
  background: #1c2333;
  border-top: 1px solid #30363d;
  color: #8b949e;
  font-size: 0.8rem;
}
.phasing-note code {
  background: #30363d;
  padding: 1px 5px;
  border-radius: 3px;
  color: #e3b341;
}

/* Auto-check schedule bar */
.auto-check-bar {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 1.25rem;
  background: var(--bg-secondary, #f8f9fa);
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  font-size: 0.875rem;
}
.auto-check-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-weight: 500;
  cursor: pointer;
}
.interval-select {
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--border-color, #ccc);
  border-radius: 4px;
  font-size: 0.85rem;
  background: var(--bg-primary, #fff);
}

/* Credential indicator icon in VM name */
.cred-indicator {
  font-size: 0.7rem;
  margin-left: 0.3rem;
  opacity: 0.5;
}
.cred-saved { opacity: 1; }
.cred-session { opacity: 0.65; filter: sepia(1) hue-rotate(30deg); }

/* Auto-check badge on cached results */
.auto-badge {
  display: inline-block;
  font-size: 0.65rem;
  background: var(--bg-secondary, #e8e8e8);
  color: var(--text-secondary, #4a5568);
  border-radius: 3px;
  padding: 0 4px;
  margin-left: 4px;
  vertical-align: middle;
}

/* AI Tune action cards */
.tuning-actions {
  margin-top: 1rem;
}
.tuning-actions h4 {
  margin: 0 0 0.75rem;
  font-size: 0.9rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.tune-action-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background: var(--bg-secondary, #f8f9fa);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  margin-bottom: 0.5rem;
}
.tune-action-info { flex: 1; }
.tune-action-info p { margin: 0.2rem 0 0; }
.tune-action-result { font-size: 0.85rem; white-space: nowrap; }

.cred-save-hint {
  color: var(--text-secondary);
  font-size: 0.75rem;
}

/* Security Scan */
.scan-panel { padding: 1rem 1.5rem; background: var(--background); }

.scan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
}

.scan-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.scan-card-wide { grid-column: span 2; }

.scan-card-title {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.scan-stat {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1;
  display: flex;
  align-items: baseline;
  gap: 0.3rem;
}

.scan-stat-label { font-size: 0.8rem; font-weight: 400; color: var(--text-secondary); }
.scan-stat-ok { color: #059669; }
.scan-stat-warn { color: #d97706; }
.scan-stat-crit { color: #dc2626; }

.scan-sub { font-size: 0.8rem; color: var(--text-secondary); }

.scan-pkg-list { display: flex; flex-direction: column; gap: 0.15rem; margin-top: 0.25rem; }
.scan-pkg { font-size: 0.75rem; font-family: monospace; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.scan-ports { overflow-x: auto; }
.scan-pre {
  font-size: 0.72rem;
  font-family: monospace;
  background: #1e293b;
  color: #e2e8f0;
  padding: 0.5rem 0.75rem;
  border-radius: 0.25rem;
  margin: 0;
  white-space: pre;
  overflow-x: auto;
  max-height: 160px;
  overflow-y: auto;
}

/* SSH Credentials Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.cred-modal {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  width: 90%;
  max-width: 440px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.2);
}

.cred-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
}

.cred-modal-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.btn-close-sm {
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 0 0.25rem;
  line-height: 1;
  border-radius: 0.25rem;
}

.btn-close-sm:focus-visible {
  outline: 2px solid var(--accent-color, #3b82f6);
  outline-offset: 2px;
}

.cred-modal-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.fetching-ip {
  font-size: 0.75rem;
  color: #3b82f6;
  font-weight: 400;
  margin-left: 0.5rem;
}

.cred-note {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin: 0 0 0.25rem;
}

.cred-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid var(--border-color);
}

/* Ollama Model Manager */
.model-manager {
  margin-top: 1.25rem;
  border-top: 1px solid var(--border-color);
  padding-top: 1rem;
}

.model-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.model-section-header h4 {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.model-list { display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 1rem; }

.model-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  background: var(--bg-secondary, #f8f9fa);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 0.875rem;
}

.model-name { flex: 1; font-weight: 500; }
.model-size { min-width: 70px; }
.model-modified { flex: 1; }

.btn-danger-outline {
  padding: 0.25rem 0.6rem;
  font-size: 0.8rem;
  background: transparent;
  color: #dc2626;
  border: 1px solid #dc2626;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
}
.btn-danger-outline:hover { background: #fee2e2; }
.btn-danger-outline:disabled { opacity: 0.5; cursor: not-allowed; }

.model-loading { padding: 0.5rem 0; font-style: italic; }

.pull-section {
  border-top: 1px solid var(--border-color);
  padding-top: 0.75rem;
}

.pull-section h4 {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.pull-controls { display: flex; gap: 0.5rem; align-items: center; }

.pull-select {
  flex: 1;
  padding: 0.45rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  background: var(--card-bg, #fff);
  color: var(--text-primary);
}

/* Conv Logs / RAG layout */
.conv-layout {
  display: flex;
  gap: 0;
  min-height: 400px;
}
.conv-vm-list {
  width: 200px;
  min-width: 160px;
  border-right: 1px solid var(--border-color);
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.conv-vm-item {
  padding: 0.6rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  border: 1px solid transparent;
  font-size: 0.875rem;
}
.conv-vm-item:hover { background: var(--bg-secondary, #f8f9fa); }
.conv-vm-item.active { background: rgba(59,130,246,0.08); border-color: rgba(59,130,246,0.3); }
.conv-main {
  flex: 1;
  padding: 1rem 1.25rem;
  overflow-y: auto;
}
.conv-controls { margin-bottom: 1rem; }
.conv-status-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 0.75rem;
}
.conv-entries { display: flex; flex-direction: column; gap: 1rem; }
.conv-entry {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}
.conv-entry-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: var(--bg-secondary, #f8f9fa);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.8rem;
}
.conv-model { font-size: 0.7rem; }
.conv-bubble {
  padding: 0.6rem 0.75rem;
  font-size: 0.85rem;
  white-space: pre-wrap;
  word-break: break-word;
}
.conv-user { background: #eff6ff; border-bottom: 1px solid var(--border-color); }
.conv-assistant { background: white; }

/* RAG sections */
.rag-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}
.rag-section:last-child { border-bottom: none; }
.rag-section h4 { margin: 0 0 0.75rem; font-size: 0.9rem; color: var(--text-secondary); }
.rag-results { margin-top: 0.75rem; display: flex; flex-direction: column; gap: 0.5rem; }
.rag-result {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 0.6rem 0.75rem;
}
.rag-result-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.35rem;
}
.rag-result-text { font-size: 0.85rem; margin: 0; white-space: pre-wrap; }
.rag-doc-list { display: flex; flex-direction: column; gap: 0.35rem; }
.rag-doc-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.45rem 0.75rem;
  background: var(--bg-secondary, #f8f9fa);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 0.875rem;
}

/* Unmanaged VMs section */
.unmanaged-section { overflow: hidden; }
.unmanaged-header {
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s;
}
.unmanaged-header:hover { background: var(--background); }
.unmanaged-chevron {
  font-size: 1.1rem;
  color: var(--text-secondary);
  transition: transform 0.2s;
  display: inline-block;
}
.unmanaged-chevron.rotated { transform: rotate(180deg); }

/* Shared */
.loading-row { display: flex; align-items: center; gap: 0.75rem; padding: 1.5rem; }
.empty-state { text-align: center; padding: 2.5rem; color: var(--text-secondary); }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mono { font-family: monospace; }

.info-box {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(147, 51, 234, 0.08));
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 0.5rem;
  padding: 0.85rem 1rem;
}

/* ── Fleet Tab ────────────────────────────────────────────────────────────── */
.fleet-quick-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--background, #f8fafc);
}

.fleet-qf-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-right: 0.25rem;
}

.fleet-qf-btn {
  padding: 0.2rem 0.65rem;
  font-size: 0.78rem;
  font-weight: 600;
  border-radius: 9999px;
  border: 1.5px solid var(--border-color, #e2e8f0);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}

.fleet-qf-btn:hover,
.fleet-qf-btn.active { background: var(--primary-color, #3b82f6); color: #fff; border-color: var(--primary-color, #3b82f6); }
.fleet-qf-warning.active,
.fleet-qf-warning:hover { background: #f59e0b; border-color: #f59e0b; color: #fff; }
.fleet-qf-success.active,
.fleet-qf-success:hover { background: #10b981; border-color: #10b981; color: #fff; }
.fleet-qf-danger.active,
.fleet-qf-danger:hover { background: #ef4444; border-color: #ef4444; color: #fff; }
.fleet-qf-info.active,
.fleet-qf-info:hover { background: #6366f1; border-color: #6366f1; color: #fff; }

.fleet-sel-count {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--primary-color, #3b82f6);
}

.fleet-table { width: 100%; }
.fleet-table th, .fleet-table td { white-space: nowrap; }

.cb-col-fleet { width: 2rem; text-align: center; }

.row-fleet-selected td { background-color: rgba(59, 130, 246, 0.06); }

.fleet-vm-name { font-weight: 600; }
.fleet-vm-desc { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.fleet-badge-pill {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 9999px;
  margin-left: 4px;
}

.fleet-badge-protect { background: rgba(16, 185, 129, 0.12); color: #059669; }
.fleet-badge-lock { background: rgba(239, 68, 68, 0.12); color: #dc2626; }

.fleet-snap-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
  font-size: 0.72rem;
  font-weight: 700;
  border-radius: 9999px;
  min-width: 22px;
  height: 20px;
  padding: 0 6px;
}

/* Usage mini-bars */
.fleet-usage-bars { display: flex; flex-direction: column; gap: 2px; margin-top: 3px; }
.fleet-bar-wrap { height: 4px; background: var(--border-color, #e2e8f0); border-radius: 2px; width: 80px; overflow: hidden; }
.fleet-bar { height: 100%; border-radius: 2px; transition: width 0.3s; }

.fleet-tag-pill {
  display: inline-block;
  font-size: 0.62rem;
  font-weight: 600;
  padding: 0.1rem 0.35rem;
  border-radius: 9999px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  white-space: nowrap;
}

/* Quick Edit Drawer */
.fleet-drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.35);
  z-index: 500;
  display: flex;
  justify-content: flex-end;
}

.fleet-drawer {
  width: 380px;
  max-width: 95vw;
  background: var(--surface, #fff);
  box-shadow: -4px 0 24px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
  animation: slideInRight 0.2s ease;
}

@keyframes slideInRight {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.fleet-drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.25rem 1.5rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.fleet-drawer-header h3 { margin: 0; font-size: 1.1rem; }

.fleet-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.5rem;
}

.fleet-drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-top: 1px solid var(--border-color);
}

.fleet-toggle-row { margin-top: 0.75rem; }

.toggle-check-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
  user-select: none;
}

/* Modal shared (reuse from above) */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 600;
}

.modal-content {
  background: var(--surface, #fff);
  border-radius: 0.5rem;
  box-shadow: 0 10px 30px rgba(0,0,0,0.2);
  max-width: 500px; width: 90%;
  max-height: 90vh; overflow-y: auto;
}

.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 1rem 1.5rem; border-bottom: 1px solid var(--border-color);
}

.modal-header h3 { margin: 0; font-size: 1.1rem; }
.modal-body { padding: 1.25rem 1.5rem; }
.modal-footer {
  display: flex; justify-content: flex-end; gap: 0.5rem;
  padding: 0.75rem 1.5rem; border-top: 1px solid var(--border-color);
}

.bulk-results-table {
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.375rem; overflow: hidden; margin-top: 1rem;
}
.bulk-results-header, .bulk-results-row {
  display: grid; grid-template-columns: 60px 1fr 80px 80px;
  gap: 0.5rem; padding: 0.4rem 0.75rem; align-items: center;
  font-size: 0.82rem;
}
.bulk-results-header {
  font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
  color: var(--text-muted); background: var(--background);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}
.bulk-results-row { border-bottom: 1px solid var(--border-color, #e2e8f0); }
.bulk-results-row:last-child { border-bottom: none; }
.bulk-done-summary { margin-top: 0.75rem; font-size: 0.875rem; font-weight: 600; color: var(--text-primary); }

.form-label { display: block; font-size: 0.82rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 0.35rem; }
.text-danger { color: #dc2626; }

@media (max-width: 768px) {
  .fleet-drawer { width: 100vw; }
  .fleet-quick-filters { flex-wrap: wrap; }
}
</style>
