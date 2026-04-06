<template>
  <div class="backup-page">
    <div class="page-header mb-2">
      <h2>Backup Management</h2>
      <p class="text-muted">Manage vzdump backup schedules and run manual backups</p>
    </div>

    <!-- Host Selector -->
    <div class="card mb-2">
      <div class="card-header">
        <h3>Proxmox Host</h3>
      </div>
      <div class="card-body">
        <div class="form-group" style="max-width: 400px; margin: 0;">
          <label class="form-label">Select Datacenter</label>
          <select v-model="selectedHostId" class="form-control" @change="onHostChange">
            <option value="">— Select a host —</option>
            <option v-for="host in hosts" :key="host.id" :value="host.id">
              {{ host.name }} ({{ host.hostname }})
            </option>
          </select>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="card">
      <div class="card-header" style="border-bottom: none; padding-bottom: 0;">
        <div class="tabs">
          <button
            v-for="tab in availableTabs"
            :key="tab"
            @click="activeTab = tab"
            :class="['tab-btn', activeTab === tab ? 'tab-active' : '']"
          >
            {{ tab }}
          </button>
        </div>
      </div>

      <!-- PBS Servers Tab -->
      <div v-if="activeTab === 'PBS Servers'" class="tab-content">
        <div class="tab-header">
          <h3>Proxmox Backup Servers</h3>
          <button @click="fetchPbsServers" class="btn btn-outline btn-sm" :disabled="loadingPbs">
            {{ loadingPbs ? 'Refreshing...' : 'Refresh' }}
          </button>
        </div>

        <SkeletonLoader v-if="loadingPbs" type="table" :count="3" />

        <div v-else-if="pbsServers.length === 0" class="text-center text-muted" style="padding: 2rem;">
          <p>No PBS servers configured.</p>
        </div>

        <div v-else class="pbs-list">
          <div v-for="pbs in pbsServers" :key="pbs.id" class="pbs-card">
            <div class="pbs-card-header">
              <div class="pbs-card-title">
                <strong>{{ pbs.name }}</strong>
                <span class="text-muted text-sm">{{ pbs.hostname }}</span>
              </div>
              <div class="pbs-card-badges">
                <span v-if="pbsStatus[pbs.id] === 'ok'" class="badge badge-success">Connected</span>
                <span v-else-if="pbsStatus[pbs.id] === 'error'" class="badge badge-danger">Failed</span>
                <span v-else-if="pbsStatus[pbs.id] === 'testing'" class="badge badge-info">Testing...</span>
                <span v-else class="badge badge-secondary">Unknown</span>
                <span v-if="pbs.datastore_count !== undefined" class="badge badge-info">
                  {{ pbs.datastore_count }} datastore{{ pbs.datastore_count !== 1 ? 's' : '' }}
                </span>
              </div>
              <div class="pbs-card-actions">
                <button
                  @click="testPbsConnection(pbs.id)"
                  class="btn btn-outline btn-sm"
                  :disabled="pbsStatus[pbs.id] === 'testing'"
                >
                  Test Connection
                </button>
                <button
                  @click="toggleDatastores(pbs.id)"
                  class="btn btn-outline btn-sm"
                >
                  {{ expandedPbs === pbs.id ? 'Hide Datastores' : 'View Datastores' }}
                </button>
              </div>
            </div>

            <!-- Datastores expand section -->
            <div v-if="expandedPbs === pbs.id" class="pbs-datastores">
              <div v-if="loadingDatastores[pbs.id]" class="loading-spinner" style="margin: 1rem 0;"></div>
              <div v-else-if="pbsDatastores[pbs.id] && pbsDatastores[pbs.id].length === 0" class="text-muted text-sm" style="padding: 1rem 0;">
                No datastores found.
              </div>
              <div v-else-if="pbsDatastores[pbs.id]" style="margin-top: 0.75rem;">
                <div
                  v-for="ds in pbsDatastores[pbs.id]"
                  :key="ds.store || ds.name"
                  class="ds-card"
                >
                  <div class="ds-card-header">
                    <div class="ds-card-title">
                      <strong>{{ ds.store || ds.name }}</strong>
                      <span class="text-sm text-muted">{{ ds.path || '' }}</span>
                    </div>
                    <div class="ds-card-actions">
                      <button
                        @click="pruneDatastore(pbs.id, ds.store || ds.name)"
                        class="btn btn-outline btn-sm"
                        :disabled="pruningDs[pbs.id + ':' + (ds.store || ds.name)]"
                        title="Prune old backups in this datastore"
                      >
                        {{ pruningDs[pbs.id + ':' + (ds.store || ds.name)] ? 'Pruning...' : 'Prune' }}
                      </button>
                    </div>
                  </div>

                  <!-- Usage bar -->
                  <div class="ds-usage" v-if="ds.total">
                    <div class="ds-usage-labels">
                      <span class="text-sm">Used: <strong>{{ formatBytes(ds.used) }}</strong></span>
                      <span class="text-sm text-muted">of {{ formatBytes(ds.total) }}</span>
                      <span class="text-sm text-muted" style="margin-left: auto;">Free: {{ formatBytes(ds.avail) }}</span>
                    </div>
                    <div class="ds-usage-bar-wrap">
                      <div
                        class="ds-usage-bar"
                        :style="{ width: dsUsagePct(ds) + '%' }"
                        :class="dsUsageClass(ds)"
                      ></div>
                    </div>
                    <div class="text-xs text-muted" style="margin-top: 0.2rem;">{{ dsUsagePct(ds).toFixed(1) }}% used</div>
                  </div>

                  <!-- Last backup -->
                  <div class="ds-last-backup text-sm text-muted" v-if="dsLastBackup[pbs.id + ':' + (ds.store || ds.name)] !== undefined">
                    Last backup:
                    <strong>{{ dsLastBackup[pbs.id + ':' + (ds.store || ds.name)] || 'none' }}</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Schedules Tab -->
      <div v-if="activeTab === 'Schedules'" class="tab-content">
        <div v-if="!selectedHostId" class="text-center text-muted" style="padding: 2rem;">
          <p>Select a Proxmox host above to manage backup schedules.</p>
        </div>
        <template v-else>
          <div class="tab-header">
            <h3>Backup Schedules</h3>
            <div class="flex gap-1">
              <button @click="fetchSchedules" class="btn btn-outline btn-sm" :disabled="loadingSchedules">Refresh</button>
              <button @click="openCreateScheduleModal" class="btn btn-primary">+ Add Schedule</button>
            </div>
          </div>

          <SkeletonLoader v-if="loadingSchedules" type="table" :count="5" />

          <div v-else-if="schedules.length === 0" class="empty-state">
            <div class="empty-icon-wrap">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </div>
            <h4 class="empty-title">No backup schedules configured</h4>
            <p class="empty-subtitle">Create a backup schedule to automatically back up your VMs and containers.</p>
            <button @click="openCreateScheduleModal" class="btn btn-primary">+ Create Schedule</button>
          </div>

          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Enabled</th>
                  <th>Schedule</th>
                  <th>Node</th>
                  <th>VMs</th>
                  <th>Storage</th>
                  <th>Mode</th>
                  <th>Compress</th>
                  <th>Keep Last</th>
                  <th>Email</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sched in schedules" :key="sched.id">
                  <td><strong>{{ sched.id }}</strong></td>
                  <td>
                    <button
                      @click="toggleScheduleEnabled(sched)"
                      :class="['toggle-btn', sched.enabled == 1 ? 'toggle-btn--on' : 'toggle-btn--off']"
                      :title="sched.enabled == 1 ? 'Click to disable' : 'Click to enable'"
                    >
                      {{ sched.enabled == 1 ? 'Enabled' : 'Disabled' }}
                    </button>
                  </td>
                  <td>
                    <code class="cron-code">{{ sched.schedule || (sched.dow ? sched.dow + ' ' + sched.starttime : '—') }}</code>
                    <div class="text-xs text-muted">{{ describeCron(sched.schedule || '') }}</div>
                  </td>
                  <td class="text-sm">{{ sched.node || 'all' }}</td>
                  <td class="text-sm">
                    <span v-if="!sched.vmid || sched.vmid === 'all'" class="badge badge-info">All VMs</span>
                    <span v-else class="vm-id-preview" :title="sched.vmid">{{ vmidPreview(sched.vmid) }}</span>
                  </td>
                  <td>{{ sched.storage || '—' }}</td>
                  <td>
                    <span class="badge badge-info">{{ sched.mode || 'snapshot' }}</span>
                  </td>
                  <td class="text-sm">{{ sched.compress || '—' }}</td>
                  <td>{{ sched['keep-last'] || sched.maxfiles || '—' }}</td>
                  <td class="text-sm text-muted">{{ sched.mailnotification || '—' }}</td>
                  <td class="actions-cell">
                    <button
                      @click="runScheduleNow(sched)"
                      class="btn btn-outline btn-sm"
                      :disabled="runningSchedule === sched.id"
                      title="Run this backup job immediately"
                    >
                      {{ runningSchedule === sched.id ? 'Starting...' : 'Run Now' }}
                    </button>
                    <button @click="openEditScheduleModal(sched)" class="btn btn-outline btn-sm">Edit</button>
                    <button @click="deleteSchedule(sched.id)" class="btn btn-danger btn-sm">Delete</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Run Now: Node selector modal -->
          <div v-if="showRunNowModal" class="modal" @click="showRunNowModal = false">
            <div class="modal-content" @click.stop style="max-width: 420px;">
              <div class="modal-header">
                <h3>Run Backup Now</h3>
                <button @click="showRunNowModal = false" class="btn-close">×</button>
              </div>
              <div class="modal-body">
                <p class="text-sm text-muted" style="margin-bottom: 1rem;">
                  Select the node to run schedule <strong>{{ pendingRunSchedule?.id }}</strong> on.
                </p>
                <div class="form-group">
                  <label class="form-label">Node</label>
                  <select v-model="runNowNode" class="form-control">
                    <option value="">— Select node —</option>
                    <option v-for="node in nodes" :key="node.node || node.name" :value="node.node || node.name">
                      {{ node.node || node.name }}
                    </option>
                  </select>
                </div>
                <div class="flex gap-1 mt-2">
                  <button
                    @click="confirmRunNow"
                    class="btn btn-primary"
                    :disabled="!runNowNode || runningSchedule === pendingRunSchedule?.id"
                  >
                    Run Now
                  </button>
                  <button @click="showRunNowModal = false" class="btn btn-outline">Cancel</button>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Run Backup Now Tab -->
      <div v-if="activeTab === 'Run Backup Now'" class="tab-content">
        <div v-if="!selectedHostId" class="text-center text-muted" style="padding: 2rem;">
          <p>Select a Proxmox host above to run a manual backup.</p>
        </div>
        <template v-else>
          <div class="tab-header">
            <h3>Manual Backup</h3>
          </div>

          <div class="backup-form">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Node</label>
                <select v-model="manualBackup.node" class="form-control" @change="onNodeChange">
                  <option value="">— Select node —</option>
                  <option v-for="node in nodes" :key="node.node || node.name" :value="node.node || node.name">
                    {{ node.node || node.name }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Virtual Machine</label>
                <select v-model="manualBackup.vmid" class="form-control">
                  <option value="">— Select VM —</option>
                  <option v-for="vm in nodeVMs" :key="vm.vmid" :value="vm.vmid">
                    {{ vm.vmid }} — {{ vm.name }} ({{ vm.type }})
                  </option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Storage</label>
                <select v-model="manualBackup.storage" class="form-control">
                  <option value="">— Select storage —</option>
                  <option v-for="s in storages" :key="s.storage" :value="s.storage">
                    {{ s.storage }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Mode</label>
                <select v-model="manualBackup.mode" class="form-control">
                  <option value="snapshot">Snapshot</option>
                  <option value="suspend">Suspend</option>
                  <option value="stop">Stop</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Compress</label>
              <select v-model="manualBackup.compress" class="form-control" style="max-width: 200px;">
                <option value="lzo">LZO (fast)</option>
                <option value="gzip">Gzip</option>
                <option value="zstd">Zstd (recommended)</option>
                <option value="0">None</option>
              </select>
            </div>

            <button @click="startBackup" class="btn btn-primary" :disabled="startingBackup || !manualBackup.vmid || !manualBackup.storage">
              {{ startingBackup ? 'Starting...' : 'Start Backup' }}
            </button>

            <!-- Task status -->
            <div v-if="backupTask" class="task-status">
              <h4>Backup Task</h4>
              <div class="task-info">
                <div class="task-upid">
                  <span class="info-label">UPID:</span>
                  <code>{{ backupTask.upid }}</code>
                </div>
                <div class="task-state">
                  <span class="info-label">Status:</span>
                  <span :class="['badge', getTaskBadge(taskStatus?.status)]">
                    {{ taskStatus?.status || 'running' }}
                  </span>
                </div>
                <div v-if="taskStatus?.exitstatus" class="task-exit">
                  <span class="info-label">Exit:</span>
                  <span :class="taskStatus.exitstatus === 'OK' ? 'text-success' : 'text-danger'">
                    {{ taskStatus.exitstatus }}
                  </span>
                </div>
              </div>
              <div v-if="taskLog" class="task-log">
                <pre>{{ taskLog }}</pre>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- History Tab -->
      <div v-if="activeTab === 'History'" class="tab-content">
        <div v-if="!selectedHostId" class="text-center text-muted" style="padding: 2rem;">
          <p>Select a Proxmox host above to view backup history.</p>
        </div>
        <template v-else>
          <div class="tab-header">
            <h3>Backup History</h3>
            <div class="flex gap-1 align-center">
              <button @click="fetchHistory" class="btn btn-outline btn-sm" :disabled="loadingHistory">
                {{ loadingHistory ? 'Loading...' : 'Refresh' }}
              </button>
              <button @click="exportHistoryCSV" class="btn btn-outline btn-sm" :disabled="historyTasks.length === 0">
                Export CSV
              </button>
            </div>
          </div>

          <!-- Filters -->
          <div class="history-filters">
            <div class="filter-group">
              <label class="filter-label">Node</label>
              <select v-model="historyFilter.node" class="form-control form-control-sm" @change="fetchHistory">
                <option value="">All nodes</option>
                <option v-for="node in nodes" :key="node.node || node.name" :value="node.node || node.name">
                  {{ node.node || node.name }}
                </option>
              </select>
            </div>
            <div class="filter-group">
              <label class="filter-label">VM ID</label>
              <input v-model="historyFilter.vmid" class="form-control form-control-sm" placeholder="e.g. 100" @input="applyHistoryFilter" />
            </div>
            <div class="filter-group">
              <label class="filter-label">Status</label>
              <select v-model="historyFilter.status" class="form-control form-control-sm" @change="applyHistoryFilter">
                <option value="">All</option>
                <option value="OK">Success</option>
                <option value="failed">Failed</option>
                <option value="running">Running</option>
              </select>
            </div>
            <div class="filter-group">
              <label class="filter-label">Search</label>
              <input v-model="historyFilter.search" class="form-control form-control-sm" placeholder="Search UPID..." @input="applyHistoryFilter" />
            </div>
          </div>

          <SkeletonLoader v-if="loadingHistory" type="table" :count="5" />

          <div v-else-if="filteredHistory.length === 0" class="text-center text-muted" style="padding: 2rem;">
            <p>No backup tasks found.</p>
          </div>

          <div v-else>
            <!-- Storage per VM chart -->
            <div v-if="vmStorageStats.length > 0" class="storage-chart-section">
              <h4 class="section-subtitle">Backup Storage Usage per VM</h4>
              <div class="vm-storage-bars">
                <div v-for="stat in vmStorageStats.slice(0, 15)" :key="stat.vmid" class="vm-bar-row">
                  <span class="vm-bar-label">VM {{ stat.vmid }}</span>
                  <div class="vm-bar-track">
                    <div
                      class="vm-bar-fill"
                      :style="{ width: (stat.count / vmStorageStats[0].count * 100) + '%' }"
                    ></div>
                  </div>
                  <span class="vm-bar-count text-sm text-muted">{{ stat.count }} backup{{ stat.count !== 1 ? 's' : '' }}</span>
                </div>
              </div>
            </div>

            <div class="table-container" style="margin-top: 1rem;">
              <table class="table table-sm">
                <thead>
                  <tr>
                    <th>Start Time</th>
                    <th>Node</th>
                    <th>VM ID</th>
                    <th>Status</th>
                    <th>Exit</th>
                    <th>Duration</th>
                    <th>User</th>
                    <th>UPID</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="task in filteredHistory.slice(0, 200)" :key="task.upid">
                    <td class="text-sm">{{ formatDate(task.starttime) }}</td>
                    <td class="text-sm">{{ task._node || task.node || '—' }}</td>
                    <td class="text-sm">
                      <span v-if="extractVmid(task)" class="vmid-chip">{{ extractVmid(task) }}</span>
                      <span v-else class="text-muted">—</span>
                    </td>
                    <td>
                      <span :class="['history-badge', historyStatusClass(task)]">
                        {{ historyStatusLabel(task) }}
                      </span>
                    </td>
                    <td class="text-sm">
                      <span :class="task.exitstatus === 'OK' ? 'text-success' : (task.exitstatus ? 'text-danger' : 'text-muted')">
                        {{ task.exitstatus || (task.status === 'running' ? 'running' : '—') }}
                      </span>
                    </td>
                    <td class="text-sm text-muted">{{ formatDuration(task.starttime, task.endtime) }}</td>
                    <td class="text-sm text-muted">{{ task.user || '—' }}</td>
                    <td class="text-xs upid-cell" :title="task.upid">{{ task.upid ? task.upid.slice(0, 40) + '...' : '—' }}</td>
                  </tr>
                </tbody>
              </table>
              <p v-if="filteredHistory.length > 200" class="text-xs text-muted" style="padding: 0.5rem 1rem;">
                Showing 200 of {{ filteredHistory.length }} results. Use filters to narrow results.
              </p>
            </div>
          </div>
        </template>
      </div>

      <!-- Restore Tab -->
      <div v-if="activeTab === 'Restore'" class="tab-content">
        <div class="tab-header" style="display:flex; justify-content:space-between; align-items:center; padding:1.25rem; border-bottom:1px solid var(--border-color);">
          <div>
            <h3 style="margin:0;">Restore Wizard</h3>
            <p class="text-muted text-sm" style="margin:0.2rem 0 0;">Guided step-by-step restore from Proxmox storage or PBS</p>
          </div>
          <button @click="showRestoreWizard = true" class="btn btn-primary">
            Launch Restore Wizard
          </button>
        </div>
        <div style="padding:1.5rem; color:var(--text-secondary); font-size:0.875rem; line-height:1.7;">
          <p>The Restore Wizard guides you through:</p>
          <ol style="margin:0.5rem 0 0 1.25rem;">
            <li><strong>Source</strong> — Select a backup from Proxmox storage or PBS</li>
            <li><strong>Target</strong> — Choose the destination node, VMID and storage</li>
            <li><strong>Options</strong> — Start after restore, unique MACs, live restore</li>
            <li><strong>Confirm &amp; Execute</strong> — Review and run with live task progress</li>
          </ol>
        </div>
      </div>
    </div>

    <!-- Restore Wizard modal -->
    <RestoreWizard
      :visible="showRestoreWizard"
      :pre-host-id="selectedHostId"
      @close="showRestoreWizard = false"
      @restored="showRestoreWizard = false"
    />

    <!-- Create / Edit Schedule Modal -->
    <div v-if="scheduleModal.show" class="modal" @click="closeScheduleModal">
      <div class="modal-content modal-content--wide" @click.stop>
        <div class="modal-header">
          <h3>{{ scheduleModal.editing ? 'Edit Backup Schedule' : 'Create Backup Schedule' }}</h3>
          <button @click="closeScheduleModal" class="btn-close">×</button>
        </div>
        <form @submit.prevent="saveSchedule" class="modal-body">

          <!-- VM Selection mode -->
          <div class="form-section">
            <h4 class="form-section-title">VM Selection</h4>
            <div class="form-group">
              <label class="form-label">Selection Mode</label>
              <div class="radio-group radio-group--inline">
                <label class="radio-label">
                  <input type="radio" v-model="scheduleForm.vmSelectionMode" value="all" />
                  <span>All VMs</span>
                </label>
                <label class="radio-label">
                  <input type="radio" v-model="scheduleForm.vmSelectionMode" value="include" />
                  <span>Specific VMs (include)</span>
                </label>
                <label class="radio-label">
                  <input type="radio" v-model="scheduleForm.vmSelectionMode" value="exclude" />
                  <span>All except selected (exclude)</span>
                </label>
              </div>
            </div>

            <!-- VM multi-selector (when include or exclude) -->
            <div v-if="scheduleForm.vmSelectionMode !== 'all'" class="vm-selector">
              <div class="vm-selector-search">
                <input
                  v-model="vmSelectorSearch"
                  class="form-control form-control-sm"
                  placeholder="Search VMs by ID or name..."
                />
              </div>
              <div v-if="loadingAllVms" class="text-sm text-muted" style="padding: 0.5rem;">Loading VMs...</div>
              <div v-else-if="allVms.length === 0" class="text-sm text-muted" style="padding: 0.5rem;">
                No VMs found. Select a node to browse VMs, or enter VMIDs manually below.
              </div>
              <div v-else class="vm-selector-list">
                <label
                  v-for="vm in filteredAllVms"
                  :key="vm.vmid"
                  class="vm-selector-item"
                >
                  <input
                    type="checkbox"
                    :value="String(vm.vmid)"
                    v-model="scheduleForm.selectedVmids"
                  />
                  <span class="vm-selector-vmid">{{ vm.vmid }}</span>
                  <span class="vm-selector-name">{{ vm.name || '—' }}</span>
                  <span class="vm-selector-type text-muted text-xs">{{ vm.type || 'vm' }}</span>
                  <span class="vm-selector-node text-muted text-xs">{{ vm._node }}</span>
                </label>
              </div>
              <div class="vm-selector-footer text-xs text-muted">
                {{ scheduleForm.selectedVmids.length }} selected
                <span v-if="scheduleForm.vmSelectionMode === 'include'"> — will back up these VMs</span>
                <span v-else> — will back up all VMs except these</span>
              </div>
            </div>
          </div>

          <!-- Storage & Node -->
          <div class="form-section">
            <h4 class="form-section-title">Storage & Node</h4>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Storage <span class="required">*</span></label>
                <select v-model="scheduleForm.storage" class="form-control" required>
                  <option value="">— Select storage —</option>
                  <option v-for="s in storages" :key="s.storage" :value="s.storage">{{ s.storage }}</option>
                </select>
                <div class="text-xs text-muted mt-1">Only backup-capable storages are listed.</div>
              </div>
              <div class="form-group">
                <label class="form-label">Node</label>
                <select v-model="scheduleForm.node" class="form-control">
                  <option value="">All nodes</option>
                  <option v-for="node in nodes" :key="node.node || node.name" :value="node.node || node.name">
                    {{ node.node || node.name }}
                  </option>
                </select>
              </div>
            </div>
          </div>

          <!-- Schedule -->
          <div class="form-section">
            <h4 class="form-section-title">Schedule</h4>
            <div class="form-group">
              <label class="form-label">Preset</label>
              <div class="cron-presets">
                <button
                  v-for="preset in cronPresets"
                  :key="preset.value"
                  type="button"
                  @click="applyCronPreset(preset.value)"
                  :class="['cron-preset-btn', scheduleForm.schedule === preset.value ? 'cron-preset-btn--active' : '']"
                >
                  {{ preset.label }}
                </button>
                <button
                  type="button"
                  @click="scheduleForm.customCron = true"
                  :class="['cron-preset-btn', scheduleForm.customCron ? 'cron-preset-btn--active' : '']"
                >
                  Custom
                </button>
              </div>
            </div>
            <div v-if="scheduleForm.customCron" class="form-group">
              <label class="form-label">Cron Expression <span class="required">*</span></label>
              <input
                v-model="scheduleForm.schedule"
                class="form-control"
                placeholder="0 2 * * *"
                required
              />
              <div class="text-xs text-muted mt-1">
                Format: minute hour day month weekday
                — Preview: <strong>{{ describeCron(scheduleForm.schedule) }}</strong>
              </div>
            </div>
            <div v-else class="form-group">
              <label class="form-label">Schedule (cron)</label>
              <input v-model="scheduleForm.schedule" class="form-control" readonly style="background: var(--bg-secondary); cursor: default;" />
              <div class="text-xs text-muted mt-1">{{ describeCron(scheduleForm.schedule) }}</div>
            </div>
          </div>

          <!-- Backup Options -->
          <div class="form-section">
            <h4 class="form-section-title">Backup Options</h4>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Backup Mode</label>
                <select v-model="scheduleForm.mode" class="form-control">
                  <option value="snapshot">Snapshot (live, no downtime)</option>
                  <option value="suspend">Suspend (brief pause)</option>
                  <option value="stop">Stop (offline backup)</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Compression</label>
                <select v-model="scheduleForm.compress" class="form-control">
                  <option value="zstd">zstd (recommended)</option>
                  <option value="gzip">gzip</option>
                  <option value="lzo">lzo (fast)</option>
                  <option value="0">none</option>
                </select>
              </div>
            </div>
          </div>

          <!-- Retention -->
          <div class="form-section">
            <h4 class="form-section-title">Retention Policy</h4>
            <div class="form-row form-row-3">
              <div class="form-group">
                <label class="form-label">Keep Last</label>
                <input v-model.number="scheduleForm['keep-last']" type="number" min="0" class="form-control" placeholder="e.g. 3 (0=unlimited)" />
              </div>
              <div class="form-group">
                <label class="form-label">Keep Daily</label>
                <input v-model.number="scheduleForm['keep-daily']" type="number" min="0" class="form-control" placeholder="e.g. 7" />
              </div>
              <div class="form-group">
                <label class="form-label">Keep Weekly</label>
                <input v-model.number="scheduleForm['keep-weekly']" type="number" min="0" class="form-control" placeholder="e.g. 4" />
              </div>
              <div class="form-group">
                <label class="form-label">Keep Monthly</label>
                <input v-model.number="scheduleForm['keep-monthly']" type="number" min="0" class="form-control" placeholder="e.g. 3" />
              </div>
              <div class="form-group">
                <label class="form-label">Keep Yearly</label>
                <input v-model.number="scheduleForm['keep-yearly']" type="number" min="0" class="form-control" placeholder="e.g. 1" />
              </div>
            </div>
          </div>

          <!-- Notifications -->
          <div class="form-section">
            <h4 class="form-section-title">Notifications</h4>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Email on</label>
                <select v-model="scheduleForm.mailnotification" class="form-control">
                  <option value="never">Never</option>
                  <option value="failure">Failure only</option>
                  <option value="always">Always</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Email address</label>
                <input
                  v-model="scheduleForm.mailto"
                  type="email"
                  class="form-control"
                  placeholder="admin@example.com"
                  :disabled="scheduleForm.mailnotification === 'never'"
                />
              </div>
            </div>
          </div>

          <!-- Misc -->
          <div class="form-section">
            <h4 class="form-section-title">Additional Options</h4>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Comment / Notes</label>
                <textarea v-model="scheduleForm.comment" class="form-control" rows="2" placeholder="Optional description"></textarea>
              </div>
            </div>
            <div class="flex gap-2" style="flex-wrap: wrap; margin-top: 0.5rem;">
              <label class="checkbox-label">
                <input type="checkbox" v-model="scheduleForm.enabled" :true-value="1" :false-value="0" />
                <span>Enabled</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="scheduleForm.protected" :true-value="1" :false-value="0" />
                <span>Protected (prevent deletion)</span>
              </label>
            </div>
          </div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingSchedule">
              {{ savingSchedule ? 'Saving...' : (scheduleModal.editing ? 'Save Changes' : 'Create Schedule') }}
            </button>
            <button type="button" @click="closeScheduleModal" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import RestoreWizard from '@/components/RestoreWizard.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

export default {
  name: 'Backup',
  components: { RestoreWizard, SkeletonLoader },
  setup() {
    const toast = useToast()
    const hosts = ref([])
    const selectedHostId = ref('')
    const activeTab = ref('PBS Servers')
    const schedules = ref([])
    const loadingSchedules = ref(false)
    const savingSchedule = ref(false)
    const nodes = ref([])
    const nodeVMs = ref([])
    const storages = ref([])
    const startingBackup = ref(false)
    const backupTask = ref(null)
    const taskStatus = ref(null)
    const taskLog = ref(null)
    let pollTimer = null

    // PBS state
    const pbsServers = ref([])
    const loadingPbs = ref(false)
    const pbsStatus = ref({})
    const expandedPbs = ref(null)
    const pbsDatastores = ref({})
    const loadingDatastores = ref({})
    const pruningDs = ref({})
    const dsLastBackup = ref({})

    // Run Now state
    const runningSchedule = ref(null)
    const showRunNowModal = ref(false)
    const pendingRunSchedule = ref(null)
    const runNowNode = ref('')

    // Schedule modal state
    const scheduleModal = ref({ show: false, editing: false, editId: null })
    const vmSelectorSearch = ref('')
    const allVms = ref([])
    const loadingAllVms = ref(false)

    // History state
    const historyTasks = ref([])
    const loadingHistory = ref(false)
    const historyFilter = ref({ node: '', vmid: '', status: '', search: '' })

    const availableTabs = computed(() => ['PBS Servers', 'Schedules', 'Run Backup Now', 'History', 'Restore'])
    const showRestoreWizard = ref(false)

    const cronPresets = [
      { label: 'Daily at 2AM', value: '0 2 * * *' },
      { label: 'Daily at 4AM', value: '0 4 * * *' },
      { label: 'Weekly Sunday', value: '0 2 * * 0' },
      { label: 'Weekly Monday', value: '0 2 * * 1' },
      { label: 'Monthly 1st', value: '0 2 1 * *' },
    ]

    const emptyScheduleForm = () => ({
      vmSelectionMode: 'all',
      selectedVmids: [],
      storage: '',
      node: '',
      schedule: '0 2 * * *',
      customCron: false,
      mode: 'snapshot',
      compress: 'zstd',
      'keep-last': null,
      'keep-daily': null,
      'keep-weekly': null,
      'keep-monthly': null,
      'keep-yearly': null,
      mailnotification: 'never',
      mailto: '',
      comment: '',
      enabled: 1,
      protected: 0,
    })
    const scheduleForm = ref(emptyScheduleForm())

    const manualBackup = ref({
      node: '',
      vmid: '',
      storage: '',
      mode: 'snapshot',
      compress: 'zstd'
    })

    const filteredAllVms = computed(() => {
      if (!vmSelectorSearch.value) return allVms.value
      const q = vmSelectorSearch.value.toLowerCase()
      return allVms.value.filter(v =>
        String(v.vmid).includes(q) || (v.name || '').toLowerCase().includes(q)
      )
    })

    const filteredHistory = computed(() => {
      let tasks = historyTasks.value
      const f = historyFilter.value
      if (f.node) tasks = tasks.filter(t => (t._node || t.node) === f.node)
      if (f.vmid) tasks = tasks.filter(t => String(extractVmid(t) || '').includes(f.vmid))
      if (f.status) {
        if (f.status === 'OK') tasks = tasks.filter(t => t.exitstatus === 'OK')
        else if (f.status === 'failed') tasks = tasks.filter(t => t.exitstatus && t.exitstatus !== 'OK' && t.status === 'stopped')
        else if (f.status === 'running') tasks = tasks.filter(t => t.status === 'running')
      }
      if (f.search) {
        const q = f.search.toLowerCase()
        tasks = tasks.filter(t => (t.upid || '').toLowerCase().includes(q) || (t.id || '').toLowerCase().includes(q))
      }
      return tasks
    })

    const vmStorageStats = computed(() => {
      const counts = {}
      for (const t of historyTasks.value) {
        const vmid = extractVmid(t)
        if (vmid) {
          counts[vmid] = (counts[vmid] || 0) + 1
        }
      }
      return Object.entries(counts)
        .map(([vmid, count]) => ({ vmid, count }))
        .sort((a, b) => b.count - a.count)
    })

    // Methods
    const fetchHosts = async () => {
      try {
        const response = await api.proxmox.listHosts()
        hosts.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch hosts:', error)
      }
    }

    const onHostChange = async () => {
      if (!selectedHostId.value) return
      schedules.value = []
      nodes.value = []
      nodeVMs.value = []
      storages.value = []
      historyTasks.value = []
      manualBackup.value.node = ''
      manualBackup.value.vmid = ''
      manualBackup.value.storage = ''
      await Promise.all([fetchSchedules(), fetchNodes(), fetchStorages()])
    }

    const fetchSchedules = async () => {
      loadingSchedules.value = true
      try {
        const response = await api.pveNode.listBackupSchedules(selectedHostId.value)
        schedules.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch schedules:', error)
        toast.error('Failed to load schedules')
      } finally {
        loadingSchedules.value = false
      }
    }

    const fetchNodes = async () => {
      try {
        const response = await api.proxmox.listNodes(selectedHostId.value)
        nodes.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch nodes:', error)
      }
    }

    const fetchStorages = async () => {
      try {
        const firstNode = nodes.value[0]?.node || nodes.value[0]?.name || ''
        if (!firstNode) return
        const response = await api.pveNode.listStorage(selectedHostId.value, firstNode)
        storages.value = (response.data || []).filter(s => s.content && s.content.includes('backup'))
      } catch (error) {
        console.error('Failed to fetch storages:', error)
      }
    }

    const fetchAllVms = async () => {
      if (!selectedHostId.value || nodes.value.length === 0) return
      loadingAllVms.value = true
      allVms.value = []
      try {
        for (const node of nodes.value) {
          const nodeName = node.node || node.name
          const [qemuRes, lxcRes] = await Promise.all([
            api.pveNode.nodeVms(selectedHostId.value, nodeName).catch(() => ({ data: {} })),
            api.pveNode.listContainers(selectedHostId.value, nodeName).catch(() => ({ data: [] }))
          ])
          const qemus = ((qemuRes.data?.vms || qemuRes.data || [])).map(v => ({ ...v, type: 'vm', _node: nodeName }))
          const lxcs = (lxcRes.data || []).map(v => ({ ...v, type: 'ct', _node: nodeName }))
          allVms.value.push(...qemus, ...lxcs)
        }
      } catch (error) {
        console.error('Failed to fetch all VMs:', error)
      } finally {
        loadingAllVms.value = false
      }
    }

    const onNodeChange = async () => {
      if (!manualBackup.value.node) { nodeVMs.value = []; return }
      try {
        const [qemuRes, lxcRes] = await Promise.all([
          api.pveNode.nodeVms(selectedHostId.value, manualBackup.value.node).catch(() => ({ data: [] })),
          api.pveNode.listContainers(selectedHostId.value, manualBackup.value.node).catch(() => ({ data: [] }))
        ])
        const qemus = ((qemuRes.data?.vms || qemuRes.data || [])).map(v => ({ ...v, type: 'vm' }))
        const lxcs = (lxcRes.data || []).map(v => ({ ...v, type: 'ct' }))
        nodeVMs.value = [...qemus, ...lxcs]
      } catch (error) {
        console.error('Failed to fetch node VMs:', error)
      }
    }

    // Schedule modal
    const openCreateScheduleModal = () => {
      scheduleForm.value = emptyScheduleForm()
      scheduleModal.value = { show: true, editing: false, editId: null }
      vmSelectorSearch.value = ''
      if (allVms.value.length === 0) fetchAllVms()
    }

    const openEditScheduleModal = (sched) => {
      const form = emptyScheduleForm()
      form.storage = sched.storage || ''
      form.node = sched.node || ''
      form.schedule = sched.schedule || sched.dow || '0 2 * * *'
      form.mode = sched.mode || 'snapshot'
      form.compress = sched.compress || 'zstd'
      form['keep-last'] = sched['keep-last'] || null
      form['keep-daily'] = sched['keep-daily'] || null
      form['keep-weekly'] = sched['keep-weekly'] || null
      form['keep-monthly'] = sched['keep-monthly'] || null
      form['keep-yearly'] = sched['keep-yearly'] || null
      form.mailnotification = sched.mailnotification || 'never'
      form.mailto = sched.mailto || ''
      form.comment = sched.comment || ''
      form.enabled = sched.enabled !== undefined ? sched.enabled : 1
      form.protected = sched.protected || 0
      // VM selection
      if (!sched.vmid || sched.vmid === 'all') {
        form.vmSelectionMode = 'all'
        form.selectedVmids = []
      } else {
        form.vmSelectionMode = 'include'
        form.selectedVmids = String(sched.vmid).split(',').map(s => s.trim()).filter(Boolean)
      }
      // Detect custom cron
      const isPreset = cronPresets.some(p => p.value === form.schedule)
      form.customCron = !isPreset
      scheduleForm.value = form
      scheduleModal.value = { show: true, editing: true, editId: sched.id }
      vmSelectorSearch.value = ''
      if (allVms.value.length === 0) fetchAllVms()
    }

    const closeScheduleModal = () => {
      scheduleModal.value = { show: false, editing: false, editId: null }
    }

    const applyCronPreset = (value) => {
      scheduleForm.value.schedule = value
      scheduleForm.value.customCron = false
    }

    const buildSchedulePayload = () => {
      const f = scheduleForm.value
      const payload = {}
      if (f.storage) payload.storage = f.storage
      if (f.node) payload.node = f.node
      if (f.schedule) payload.schedule = f.schedule
      if (f.mode) payload.mode = f.mode
      if (f.compress) payload.compress = f.compress
      // VM ids
      if (f.vmSelectionMode === 'all') {
        // omit vmid → Proxmox defaults to all
      } else if (f.vmSelectionMode === 'include' && f.selectedVmids.length > 0) {
        payload.vmid = f.selectedVmids.join(',')
      } else if (f.vmSelectionMode === 'exclude' && f.selectedVmids.length > 0) {
        payload.exclude = f.selectedVmids.join(',')
      }
      // Retention
      const keepFields = ['keep-last', 'keep-daily', 'keep-weekly', 'keep-monthly', 'keep-yearly']
      for (const k of keepFields) {
        if (f[k] !== null && f[k] !== '' && f[k] >= 0) payload[k] = f[k]
      }
      // Notifications
      payload.mailnotification = f.mailnotification
      if (f.mailnotification !== 'never' && f.mailto) payload.mailto = f.mailto
      // Misc
      if (f.comment) payload.comment = f.comment
      payload.enabled = f.enabled
      if (f.protected) payload.protected = 1
      return payload
    }

    const saveSchedule = async () => {
      savingSchedule.value = true
      try {
        const payload = buildSchedulePayload()
        if (scheduleModal.value.editing) {
          await api.pveNode.updateBackupSchedule(selectedHostId.value, scheduleModal.value.editId, payload)
          toast.success('Schedule updated')
        } else {
          await api.pveNode.createBackupSchedule(selectedHostId.value, payload)
          toast.success('Schedule created')
        }
        closeScheduleModal()
        await fetchSchedules()
      } catch (error) {
        console.error('Failed to save schedule:', error)
        toast.error('Failed to save schedule')
      } finally {
        savingSchedule.value = false
      }
    }

    const deleteSchedule = async (id) => {
      if (!confirm(`Delete backup schedule "${id}"?`)) return
      try {
        await api.pveNode.deleteBackupSchedule(selectedHostId.value, id)
        toast.success('Schedule deleted')
        await fetchSchedules()
      } catch (error) {
        console.error('Failed to delete schedule:', error)
        toast.error('Failed to delete schedule')
      }
    }

    const toggleScheduleEnabled = async (sched) => {
      const newVal = sched.enabled == 1 ? 0 : 1
      try {
        await api.pveNode.updateBackupSchedule(selectedHostId.value, sched.id, { enabled: newVal })
        sched.enabled = newVal
        toast.success(`Schedule ${newVal === 1 ? 'enabled' : 'disabled'}`)
      } catch (error) {
        console.error('Failed to toggle schedule:', error)
        toast.error('Failed to update schedule')
      }
    }

    // Run Now
    const runScheduleNow = (sched) => {
      if (nodes.value.length === 0) {
        toast.error('No nodes loaded. Select a host first.')
        return
      }
      pendingRunSchedule.value = sched
      runNowNode.value = nodes.value.length === 1 ? (nodes.value[0].node || nodes.value[0].name) : ''
      showRunNowModal.value = true
    }

    const confirmRunNow = async () => {
      const sched = pendingRunSchedule.value
      if (!sched || !runNowNode.value) return
      showRunNowModal.value = false
      runningSchedule.value = sched.id
      try {
        const res = await api.pveNode.runBackupScheduleNow(selectedHostId.value, sched.id, { node: runNowNode.value })
        const upid = res.data?.upid || res.data
        toast.success(`Backup job "${sched.id}" started — UPID: ${String(upid).slice(0, 30)}...`)
      } catch (error) {
        console.error('Failed to run backup schedule:', error)
        toast.error('Failed to start backup job')
      } finally {
        runningSchedule.value = null
        pendingRunSchedule.value = null
        runNowNode.value = ''
      }
    }

    const startBackup = async () => {
      startingBackup.value = true
      backupTask.value = null
      taskStatus.value = null
      taskLog.value = null
      if (pollTimer) clearInterval(pollTimer)
      try {
        const response = await api.pveNode.runBackup(
          selectedHostId.value,
          manualBackup.value.node,
          {
            vmid: manualBackup.value.vmid,
            storage: manualBackup.value.storage,
            mode: manualBackup.value.mode,
            compress: manualBackup.value.compress
          }
        )
        backupTask.value = { upid: response.data?.upid || response.data }
        toast.success('Backup started')
        pollTaskStatus()
      } catch (error) {
        console.error('Failed to start backup:', error)
        toast.error('Failed to start backup')
      } finally {
        startingBackup.value = false
      }
    }

    const pollTaskStatus = () => {
      if (!backupTask.value?.upid) return
      pollTimer = setInterval(async () => {
        try {
          const response = await api.pveNode.taskStatus(
            selectedHostId.value,
            manualBackup.value.node,
            encodeURIComponent(backupTask.value.upid)
          )
          taskStatus.value = response.data
          if (taskStatus.value.status === 'stopped') {
            clearInterval(pollTimer)
            try {
              const logRes = await api.pveNode.taskLog(
                selectedHostId.value,
                manualBackup.value.node,
                encodeURIComponent(backupTask.value.upid)
              )
              taskLog.value = (logRes.data?.lines || logRes.data || []).join('\n')
            } catch {}
          }
        } catch (error) {
          console.error('Failed to poll task:', error)
        }
      }, 3000)
    }

    const getTaskBadge = (status) => {
      if (status === 'stopped') return 'badge-success'
      if (status === 'running') return 'badge-info'
      return 'badge-warning'
    }

    // History
    const fetchHistory = async () => {
      if (!selectedHostId.value) return
      loadingHistory.value = true
      try {
        const params = { limit: 500 }
        if (historyFilter.value.node) params.node = historyFilter.value.node
        const res = await api.pveNode.getBackupHistory(selectedHostId.value, params)
        historyTasks.value = res.data || []
      } catch (error) {
        console.error('Failed to fetch history:', error)
        toast.error('Failed to load backup history')
      } finally {
        loadingHistory.value = false
      }
    }

    const applyHistoryFilter = () => {
      // reactive filter applied via computed
    }

    const extractVmid = (task) => {
      if (!task) return null
      if (task.id) return task.id
      const upid = task.upid || ''
      const m = upid.match(/:(\d+):/)
      return m ? m[1] : null
    }

    const historyStatusLabel = (task) => {
      if (task.status === 'running') return 'Running'
      if (task.exitstatus === 'OK') return 'OK'
      if (task.exitstatus) return 'Failed'
      return task.status || 'Unknown'
    }

    const historyStatusClass = (task) => {
      if (task.status === 'running') return 'history-badge--running'
      if (task.exitstatus === 'OK') return 'history-badge--ok'
      if (task.exitstatus) return 'history-badge--fail'
      return 'history-badge--unknown'
    }

    const formatDuration = (start, end) => {
      if (!start) return '—'
      const s = (end || Math.floor(Date.now() / 1000)) - start
      if (s < 60) return `${s}s`
      if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
      return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
    }

    const formatDate = (ctime) => {
      if (!ctime) return '—'
      return new Date(ctime * 1000).toLocaleString()
    }

    const exportHistoryCSV = () => {
      const tasks = filteredHistory.value
      const header = ['Start Time', 'Node', 'VM ID', 'Status', 'Exit', 'Duration (s)', 'User', 'UPID']
      const rows = tasks.map(t => [
        t.starttime ? new Date(t.starttime * 1000).toISOString() : '',
        t._node || t.node || '',
        extractVmid(t) || '',
        historyStatusLabel(t),
        t.exitstatus || '',
        t.endtime && t.starttime ? (t.endtime - t.starttime) : '',
        t.user || '',
        t.upid || ''
      ])
      const csv = [header, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `backup-history-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    }

    // PBS methods
    const fetchPbsServers = async () => {
      loadingPbs.value = true
      try {
        const response = await api.pbs.list()
        pbsServers.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch PBS servers:', error)
        toast.error('Failed to load PBS servers')
      } finally {
        loadingPbs.value = false
      }
    }

    const testPbsConnection = async (pbsId) => {
      pbsStatus.value = { ...pbsStatus.value, [pbsId]: 'testing' }
      try {
        await api.pbsMgmt.test(pbsId)
        pbsStatus.value = { ...pbsStatus.value, [pbsId]: 'ok' }
        toast.success('PBS connection successful')
      } catch (error) {
        pbsStatus.value = { ...pbsStatus.value, [pbsId]: 'error' }
        toast.error('PBS connection failed')
      }
    }

    const toggleDatastores = async (pbsId) => {
      if (expandedPbs.value === pbsId) {
        expandedPbs.value = null
        return
      }
      expandedPbs.value = pbsId
      if (pbsDatastores.value[pbsId]) return
      loadingDatastores.value = { ...loadingDatastores.value, [pbsId]: true }
      try {
        const response = await api.pbsMgmt.listDatastores(pbsId)
        const datastores = response.data || []
        pbsDatastores.value = { ...pbsDatastores.value, [pbsId]: datastores }
        datastores.forEach(ds => { fetchDsLastBackup(pbsId, ds.store || ds.name) })
      } catch (error) {
        toast.error('Failed to load datastores')
        pbsDatastores.value = { ...pbsDatastores.value, [pbsId]: [] }
      } finally {
        loadingDatastores.value = { ...loadingDatastores.value, [pbsId]: false }
      }
    }

    const fetchDsLastBackup = async (pbsId, dsName) => {
      const key = pbsId + ':' + dsName
      try {
        const res = await api.pbsMgmt.listGroups(pbsId, dsName)
        const groups = res.data || []
        if (groups.length === 0) {
          dsLastBackup.value = { ...dsLastBackup.value, [key]: 'none' }
          return
        }
        let maxTs = 0
        for (const g of groups) {
          if (g['last-backup'] && g['last-backup'] > maxTs) maxTs = g['last-backup']
        }
        dsLastBackup.value = {
          ...dsLastBackup.value,
          [key]: maxTs ? new Date(maxTs * 1000).toLocaleString() : 'none',
        }
      } catch {
        dsLastBackup.value = { ...dsLastBackup.value, [key]: 'unknown' }
      }
    }

    const pruneDatastore = async (pbsId, dsName) => {
      const key = pbsId + ':' + dsName
      if (!confirm(`Prune datastore "${dsName}"? This will remove expired backups based on retention settings.`)) return
      pruningDs.value = { ...pruningDs.value, [key]: true }
      try {
        await api.pbsMgmt.pruneDatastore(pbsId, dsName, {})
        toast.success(`Prune job started for datastore "${dsName}"`)
      } catch (error) {
        toast.error('Failed to start prune job')
      } finally {
        pruningDs.value = { ...pruningDs.value, [key]: false }
      }
    }

    const dsUsagePct = (ds) => {
      if (!ds.total || ds.total === 0) return 0
      return Math.min(100, ((ds.used || 0) / ds.total) * 100)
    }

    const dsUsageClass = (ds) => {
      const pct = dsUsagePct(ds)
      if (pct >= 90) return 'ds-usage-bar--danger'
      if (pct >= 75) return 'ds-usage-bar--warn'
      return 'ds-usage-bar--ok'
    }

    const formatBytes = (bytes) => {
      if (bytes === undefined || bytes === null) return '—'
      if (bytes === 0) return '0 B'
      const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
    }

    const describeCron = (cron) => {
      if (!cron) return ''
      const parts = cron.trim().split(/\s+/)
      if (parts.length !== 5) return cron
      const [min, hour, dom, mon, dow] = parts
      const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      try {
        if (dom === '*' && mon === '*') {
          if (dow === '*') return `Daily at ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
          if (!isNaN(Number(dow))) return `Weekly on ${days[Number(dow)]} at ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
        }
        if (dom !== '*' && mon === '*' && dow === '*') {
          return `Monthly on day ${dom} at ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
        }
      } catch {}
      return `At ${min} ${hour} ${dom} ${mon} ${dow}`
    }

    const vmidPreview = (vmid) => {
      if (!vmid) return '—'
      const parts = String(vmid).split(',')
      if (parts.length <= 3) return vmid
      return parts.slice(0, 3).join(', ') + ` +${parts.length - 3} more`
    }

    // Watch for History tab activation
    const onTabChange = (tab) => {
      if (tab === 'History' && selectedHostId.value && historyTasks.value.length === 0) {
        fetchHistory()
      }
    }

    onMounted(() => {
      fetchHosts()
      fetchPbsServers()
    })

    return {
      hosts,
      selectedHostId,
      activeTab,
      availableTabs,
      showRestoreWizard,
      schedules,
      loadingSchedules,
      savingSchedule,
      scheduleForm,
      scheduleModal,
      cronPresets,
      vmSelectorSearch,
      allVms,
      loadingAllVms,
      filteredAllVms,
      nodes,
      nodeVMs,
      storages,
      manualBackup,
      startingBackup,
      backupTask,
      taskStatus,
      taskLog,
      // PBS
      pbsServers,
      loadingPbs,
      pbsStatus,
      expandedPbs,
      pbsDatastores,
      loadingDatastores,
      pruningDs,
      dsLastBackup,
      // Run Now
      runningSchedule,
      showRunNowModal,
      pendingRunSchedule,
      runNowNode,
      // History
      historyTasks,
      loadingHistory,
      historyFilter,
      filteredHistory,
      vmStorageStats,
      // Methods
      onHostChange,
      onNodeChange,
      fetchSchedules,
      openCreateScheduleModal,
      openEditScheduleModal,
      closeScheduleModal,
      applyCronPreset,
      saveSchedule,
      deleteSchedule,
      toggleScheduleEnabled,
      runScheduleNow,
      confirmRunNow,
      startBackup,
      getTaskBadge,
      fetchHistory,
      applyHistoryFilter,
      extractVmid,
      historyStatusLabel,
      historyStatusClass,
      formatDuration,
      formatDate,
      exportHistoryCSV,
      fetchPbsServers,
      testPbsConnection,
      toggleDatastores,
      pruneDatastore,
      dsUsagePct,
      dsUsageClass,
      formatBytes,
      describeCron,
      vmidPreview,
    }
  },
  watch: {
    activeTab(tab) {
      if (tab === 'History' && this.selectedHostId && this.historyTasks.length === 0) {
        this.fetchHistory()
      }
      if (tab === 'Schedules' && this.selectedHostId && this.schedules.length === 0) {
        this.fetchSchedules()
      }
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.card-body {
  padding: 1.5rem;
}

.mb-2 {
  margin-bottom: 1rem;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.75rem 1.5rem;
  cursor: pointer;
  font-size: 0.95rem;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-active {
  color: var(--primary-color) !important;
  border-bottom-color: var(--primary-color) !important;
  font-weight: 600;
}

.tab-content {
  padding: 1.5rem;
}

.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.tab-header h3 {
  margin: 0;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-row-3 {
  grid-template-columns: 1fr 1fr 1fr;
}

.backup-form {
  max-width: 700px;
}

.task-status {
  margin-top: 1.5rem;
  padding: 1.5rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
}

.task-status h4 {
  margin: 0 0 1rem 0;
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.task-upid {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.task-upid code {
  font-size: 0.8rem;
  background: #1e293b;
  color: #e2e8f0;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  word-break: break-all;
}

.task-state, .task-exit {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.info-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.task-log {
  background: #1e1e1e;
  border-radius: 0.375rem;
  overflow: hidden;
  max-height: 300px;
  overflow-y: auto;
}

.task-log pre {
  margin: 0;
  padding: 1rem;
  color: #d4d4d4;
  font-family: monospace;
  font-size: 0.8rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.text-success { color: #059669; }
.text-danger { color: #ef4444; }
.text-muted { color: var(--text-secondary); }
.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.text-center { text-align: center; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.gap-2 { gap: 1rem; }
.align-center { align-items: center; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.75rem; }

/* PBS Servers */
.pbs-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.pbs-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
}

.pbs-card-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: var(--background);
  flex-wrap: wrap;
}

.pbs-card-title {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
  min-width: 150px;
}

.pbs-card-badges {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.pbs-card-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-shrink: 0;
}

.pbs-datastores {
  padding: 0 1.25rem 1.25rem;
  border-top: 1px solid var(--border-color);
}

.actions-cell {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

/* Toggle button */
.toggle-btn {
  border: none;
  padding: 0.2rem 0.6rem;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  transition: all 0.15s;
}

.toggle-btn--on {
  background: rgba(5, 150, 105, 0.12);
  color: #059669;
  border: 1px solid #059669;
}

.toggle-btn--on:hover {
  background: rgba(5, 150, 105, 0.25);
}

.toggle-btn--off {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border: 1px solid #ef4444;
}

.toggle-btn--off:hover {
  background: rgba(239, 68, 68, 0.2);
}

/* Cron code */
.cron-code {
  font-size: 0.82rem;
  background: var(--bg-secondary, rgba(255,255,255,0.05));
  color: var(--text-primary);
  padding: 0.1rem 0.35rem;
  border-radius: 0.2rem;
}

/* VM id preview */
.vm-id-preview {
  font-size: 0.8rem;
  color: var(--text-secondary);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

/* Modals */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card, #1a1a2e);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-content--wide {
  max-width: 800px;
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  background: var(--bg-card, #1a1a2e);
  z-index: 1;
}

.modal-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body {
  padding: 1.5rem;
  color: var(--text-primary);
}

/* Form sections */
.form-section {
  margin-bottom: 1.75rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border-color);
}

.form-section:last-of-type {
  border-bottom: none;
  margin-bottom: 1rem;
}

.form-section-title {
  margin: 0 0 1rem 0;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-secondary);
  font-weight: 700;
}

/* Cron presets */
.cron-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.cron-preset-btn {
  border: 1px solid var(--border-color);
  background: none;
  color: var(--text-secondary);
  padding: 0.3rem 0.75rem;
  border-radius: 0.25rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.15s;
}

.cron-preset-btn:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.cron-preset-btn--active {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #fff;
  font-weight: 600;
}

/* VM Selector */
.vm-selector {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
  margin-top: 0.5rem;
}

.vm-selector-search {
  padding: 0.5rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary, rgba(255,255,255,0.02));
}

.vm-selector-list {
  max-height: 200px;
  overflow-y: auto;
}

.vm-selector-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.4rem 0.75rem;
  cursor: pointer;
  font-size: 0.875rem;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.1s;
}

.vm-selector-item:last-child {
  border-bottom: none;
}

.vm-selector-item:hover {
  background: var(--bg-hover, rgba(99,102,241,0.05));
}

.vm-selector-item input[type="checkbox"] {
  flex-shrink: 0;
}

.vm-selector-vmid {
  font-weight: 600;
  color: var(--primary-color, #6366f1);
  min-width: 50px;
}

.vm-selector-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vm-selector-type {
  min-width: 30px;
}

.vm-selector-node {
  min-width: 70px;
  text-align: right;
}

.vm-selector-footer {
  padding: 0.35rem 0.75rem;
  background: var(--bg-secondary, rgba(255,255,255,0.02));
  border-top: 1px solid var(--border-color);
  color: var(--text-muted);
}

/* Radio group inline */
.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.25rem;
}

.radio-group--inline {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
}

/* Checkbox label */
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
}

/* History */
.history-filters {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  padding: 1rem;
  background: var(--bg-secondary, rgba(255,255,255,0.02));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 150px;
}

.filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
}

.form-control-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
  height: auto;
}

.vmid-chip {
  background: var(--primary-color, #6366f1);
  color: #fff;
  border-radius: 0.2rem;
  padding: 0.05rem 0.35rem;
  font-size: 0.8rem;
  font-weight: 600;
}

.upid-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-muted);
  font-family: monospace;
}

/* History status badges */
.history-badge {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
  border: 1px solid;
}

.history-badge--ok {
  background: rgba(5, 150, 105, 0.1);
  color: #059669;
  border-color: #059669;
}

.history-badge--fail {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border-color: #ef4444;
}

.history-badge--running {
  background: rgba(180, 83, 9, 0.1);
  color: #b45309;
  border-color: #d97706;
}

.history-badge--unknown {
  background: rgba(107, 114, 128, 0.1);
  color: #6b7280;
  border-color: #9ca3af;
}

/* Storage chart */
.storage-chart-section {
  margin-top: 0.5rem;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background: var(--bg-secondary, rgba(255,255,255,0.02));
}

.section-subtitle {
  margin: 0 0 0.75rem 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
}

.vm-storage-bars {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.vm-bar-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.vm-bar-label {
  min-width: 70px;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.vm-bar-track {
  flex: 1;
  height: 10px;
  background: var(--border-color, rgba(255,255,255,0.1));
  border-radius: 5px;
  overflow: hidden;
}

.vm-bar-fill {
  height: 100%;
  background: var(--primary-color, #6366f1);
  border-radius: 5px;
  transition: width 0.4s ease;
}

.vm-bar-count {
  min-width: 80px;
  text-align: right;
}

/* Badges */
.badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.1rem 0.45rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
  border: 1px solid;
}

.badge-success {
  background: rgba(5, 150, 105, 0.1);
  color: #059669;
  border-color: #059669;
}

.badge-danger {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border-color: #ef4444;
}

.badge-info {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  border-color: #3b82f6;
}

.badge-warning {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
  border-color: #f59e0b;
}

.badge-secondary {
  background-color: var(--border-color);
  color: var(--text-secondary);
  border-color: var(--border-color);
}

/* Datastore cards */
.ds-card {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.9rem 1rem;
  margin-bottom: 0.75rem;
  background: var(--bg-card, transparent);
}

.ds-card:last-child {
  margin-bottom: 0;
}

.ds-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.65rem;
}

.ds-card-title {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.ds-card-actions {
  flex-shrink: 0;
}

.ds-usage {
  margin-bottom: 0.5rem;
}

.ds-usage-labels {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.3rem;
  flex-wrap: wrap;
}

.ds-usage-bar-wrap {
  height: 8px;
  background: var(--border-color, rgba(255,255,255,0.1));
  border-radius: 4px;
  overflow: hidden;
}

.ds-usage-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.ds-usage-bar--ok { background: #10b981; }
.ds-usage-bar--warn { background: #f59e0b; }
.ds-usage-bar--danger { background: #ef4444; }

.ds-last-backup {
  margin-top: 0.4rem;
  padding-top: 0.4rem;
  border-top: 1px solid var(--border-color);
}

.required { color: #ef4444; }

@media (max-width: 640px) {
  .form-row, .form-row-3 {
    grid-template-columns: 1fr;
  }
  .radio-group--inline {
    flex-direction: column;
  }
  .history-filters {
    flex-direction: column;
  }
}

/* ── Empty state ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1.5rem;
  text-align: center;
}

.empty-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--background);
  border: 2px dashed var(--border-color);
  color: var(--text-muted);
}

.empty-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.empty-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
  max-width: 420px;
}
</style>
