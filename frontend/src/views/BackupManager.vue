<template>
  <div class="backup-manager-page">
    <div class="page-header mb-2">
      <h2>Backup Manager</h2>
      <p class="text-muted">Manage backup schedules and run manual backups for host {{ hostId }}</p>
    </div>

    <!-- Tabs -->
    <div class="tab-bar mb-2">
      <button
        :class="['tab-btn', activeTab === 'schedules' ? 'tab-btn--active' : '']"
        @click="activeTab = 'schedules'"
      >Schedules</button>
      <button
        :class="['tab-btn', activeTab === 'run' ? 'tab-btn--active' : '']"
        @click="activeTab = 'run'"
      >Run Backup</button>
      <button
        :class="['tab-btn', activeTab === 'restore' ? 'tab-btn--active' : '']"
        @click="activeTab = 'restore'; onRestoreTabOpen()"
      >Restore</button>
      <button
        :class="['tab-btn', activeTab === 'pbs-servers' ? 'tab-btn--active' : '']"
        @click="activeTab = 'pbs-servers'; onPbsServersTabOpen()"
      >PBS Servers</button>
      <button
        :class="['tab-btn', activeTab === 'pbs' ? 'tab-btn--active' : '']"
        @click="activeTab = 'pbs'; onPbsTabOpen()"
      >PBS Browser</button>
      <button
        :class="['tab-btn', activeTab === 'pbs-tasks' ? 'tab-btn--active' : '']"
        @click="activeTab = 'pbs-tasks'; onPbsTasksTabOpen()"
      >PBS Tasks</button>
      <button
        :class="['tab-btn', activeTab === 'notifications' ? 'tab-btn--active' : '']"
        @click="activeTab = 'notifications'"
      >Notifications</button>
      <button
        :class="['tab-btn', activeTab === 'retention' ? 'tab-btn--active' : '']"
        @click="activeTab = 'retention'; onRetentionTabOpen()"
      >Retention Policies</button>
    </div>

    <!-- Schedules tab -->
    <div v-if="activeTab === 'schedules'">
      <div class="card">
        <div class="card-header">
          <h3>Backup Schedules</h3>
          <div class="flex gap-1">
            <button @click="openQuickBackupModal" class="btn btn-outline">Quick Backup</button>
            <button @click="openCreateModal" class="btn btn-primary">+ New Schedule</button>
          </div>
        </div>

        <div v-if="loadingSchedules" class="loading-spinner"></div>

        <div v-else-if="schedules.length === 0" class="text-center text-muted p-3">
          No backup schedules configured.
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Comment</th>
                <th>Schedule</th>
                <th>Node</th>
                <th>Storage</th>
                <th>VMs</th>
                <th>Enabled</th>
                <th>Last Run</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="sched in schedules" :key="sched.id">
                <td><strong>{{ sched.id }}</strong></td>
                <td>{{ sched.comment || '—' }}</td>
                <td><code class="cron-text">{{ sched.schedule || sched.dow || '—' }}</code></td>
                <td>{{ sched.node || 'all' }}</td>
                <td>{{ sched.storage || '—' }}</td>
                <td class="text-sm">{{ sched.vmid || 'all' }}</td>
                <td>
                  <label class="toggle-switch" :title="sched.enabled === 0 ? 'Disabled — click to enable' : 'Enabled — click to disable'">
                    <input
                      type="checkbox"
                      :checked="sched.enabled !== 0"
                      @change="toggleScheduleEnabled(sched)"
                    />
                    <span class="toggle-slider"></span>
                  </label>
                </td>
                <td class="text-sm text-muted">
                  {{ sched['next-run'] ? formatDate(sched['next-run']) : (sched.starttime ? formatDate(sched.starttime) : '—') }}
                </td>
                <td>
                  <div class="flex gap-1">
                    <button @click="openRunNowModal(sched)" class="btn btn-outline btn-sm" title="Run this schedule now">Run Now</button>
                    <button @click="openEditModal(sched)" class="btn btn-outline btn-sm">Edit</button>
                    <button @click="deleteSchedule(sched.id)" class="btn btn-danger btn-sm">Delete</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Run Backup tab -->
    <div v-if="activeTab === 'run'">
      <div class="card">
        <div class="card-header">
          <h3>Run Manual Backup</h3>
        </div>
        <div class="card-body">
          <div v-if="runResult" class="run-result">
            <p class="text-sm"><strong>Backup started. Task UPID:</strong></p>
            <code class="upid-code">{{ runResult }}</code>
            <button @click="runResult = null" class="btn btn-outline btn-sm mt-1">Dismiss</button>
          </div>

          <form @submit.prevent="runBackup">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Node <span class="required">*</span></label>
                <select v-model="runForm.node" class="form-control" required>
                  <option value="">Select node...</option>
                  <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">
                    {{ n.node || n.name }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Storage <span class="required">*</span></label>
                <input v-model="runForm.storage" class="form-control" placeholder="e.g. local" required />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">VM IDs</label>
              <input
                v-model="runForm.vmid"
                class="form-control"
                placeholder='Comma-separated IDs or "all" (e.g. 100,101,102)'
              />
              <div class="text-xs text-muted mt-1">Leave blank or enter "all" to back up all VMs.</div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Compression</label>
                <select v-model="runForm.compress" class="form-control">
                  <option value="zstd">zstd (recommended)</option>
                  <option value="lzo">lzo</option>
                  <option value="gzip">gzip</option>
                  <option value="0">none</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Mode</label>
                <select v-model="runForm.mode" class="form-control">
                  <option value="snapshot">snapshot</option>
                  <option value="suspend">suspend</option>
                  <option value="stop">stop</option>
                </select>
              </div>
            </div>

            <div class="flex gap-1 mt-2">
              <button type="submit" class="btn btn-primary" :disabled="running">
                {{ running ? 'Starting...' : 'Run Now' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Restore tab -->
    <div v-if="activeTab === 'restore'">
      <!-- Restore Wizard launcher -->
      <div class="card mb-2">
        <div class="card-body" style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:0.75rem;">
          <div>
            <strong>Restore Wizard</strong>
            <p class="text-muted text-sm mb-0" style="margin:0.1rem 0 0;">
              Step-by-step guided restore from Proxmox storage or PBS
            </p>
          </div>
          <button @click="showRestoreWizard = true" class="btn btn-primary">
            Launch Restore Wizard
          </button>
        </div>
      </div>

      <div class="card mb-2">
        <div class="card-header">
          <h3>Browse Backups</h3>
          <div class="flex gap-1">
            <select v-model="restoreFilter.node" class="form-control form-control-sm" @change="onRestoreNodeChange">
              <option value="">Select node...</option>
              <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">
                {{ n.node || n.name }}
              </option>
            </select>
            <select v-model="restoreFilter.storage" class="form-control form-control-sm" :disabled="!restoreFilter.node || loadingRestoreStorages" @change="fetchBackupFiles">
              <option value="">Select storage...</option>
              <option v-for="s in restoreStorages" :key="s.storage" :value="s.storage">
                {{ s.storage }}
              </option>
            </select>
            <button @click="fetchBackupFiles" class="btn btn-outline btn-sm" :disabled="!restoreFilter.node || !restoreFilter.storage || loadingBackupFiles">
              Refresh
            </button>
          </div>
        </div>

        <!-- Backup search/filter bar -->
        <div v-if="!loadingBackupFiles && restoreFilter.node && restoreFilter.storage && backupGroups.length > 0" class="backup-filter-bar">
          <input v-model="backupSearch" type="text" class="form-control form-control-sm" placeholder="Search by VMID or filename…" style="width:200px;" />
          <input v-model="backupDateFrom" type="date" class="form-control form-control-sm" style="width:145px;" title="From date" />
          <input v-model="backupDateTo" type="date" class="form-control form-control-sm" style="width:145px;" title="To date" />
          <select v-model="backupSortBy" class="form-control form-control-sm" style="width:130px;">
            <option value="date_desc">Newest first</option>
            <option value="date_asc">Oldest first</option>
            <option value="size_desc">Largest first</option>
            <option value="size_asc">Smallest first</option>
          </select>
          <button v-if="backupSearch || backupDateFrom || backupDateTo" @click="backupSearch=''; backupDateFrom=''; backupDateTo=''" class="btn btn-outline btn-sm">Clear</button>
        </div>

        <div v-if="loadingBackupFiles" class="loading-spinner"></div>

        <div v-else-if="!restoreFilter.node || !restoreFilter.storage" class="text-center text-muted p-3">
          Select a node and storage to browse backup files.
        </div>

        <div v-else-if="filteredBackupGroups.length === 0" class="text-center text-muted p-3">
          <span v-if="backupGroups.length === 0">No backup files found in this storage.</span>
          <span v-else>No backups match your search/filter.</span>
        </div>

        <div v-else>
          <div v-for="group in filteredBackupGroups" :key="group.vmid" class="backup-group">
            <div class="backup-group-header">
              <span class="vmid-badge">VMID {{ group.vmid }}</span>
              <span class="text-muted text-sm ml-1">{{ group.backups.length }} backup{{ group.backups.length !== 1 ? 's' : '' }}</span>
            </div>
            <table class="table table-sm">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Format</th>
                  <th>Size</th>
                  <th>Volume ID</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="bk in group.backups" :key="bk.volid">
                  <td>{{ formatDate(bk.ctime) }}</td>
                  <td><code class="text-xs">{{ bk.format || '—' }}</code></td>
                  <td>{{ formatSize(bk.size) }}</td>
                  <td class="text-xs volid-cell">{{ bk.volid }}</td>
                  <td>
                    <button @click="openRestoreModal(bk, group.vmid)" class="btn btn-primary btn-sm">
                      Restore
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- PBS Servers tab -->
    <div v-if="activeTab === 'pbs-servers'">
      <div class="card">
        <div class="card-header">
          <h3>PBS Servers</h3>
          <button @click="openAddPbsServerModal" class="btn btn-primary">+ Add Server</button>
        </div>

        <div v-if="loadingPbsServersCrud" class="loading-spinner"></div>

        <div v-else-if="pbsServerList.length === 0" class="text-center text-muted p-3">
          No PBS servers configured. Add one to get started.
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Hostname</th>
                <th>Port</th>
                <th>Datastore</th>
                <th>Token ID</th>
                <th>SSL</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="srv in pbsServerList" :key="srv.id">
                <tr>
                  <td><strong>{{ srv.name }}</strong></td>
                  <td>{{ srv.hostname }}</td>
                  <td>{{ srv.port }}</td>
                  <td class="text-sm text-muted">
                    <span v-if="pbsServerDatastores[srv.id]">
                      {{ pbsServerDatastores[srv.id].map(d => d.store || d.name).join(', ') || '—' }}
                    </span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="text-sm text-muted">{{ srv.api_token_id || '—' }}</td>
                  <td>
                    <span :class="['badge', srv.verify_ssl ? 'badge--ok' : 'badge--off']">
                      {{ srv.verify_ssl ? 'Verified' : 'Skip' }}
                    </span>
                  </td>
                  <td>
                    <span v-if="pbsServerStatus[srv.id] === undefined" class="text-muted text-sm">—</span>
                    <span v-else-if="pbsServerStatus[srv.id] === 'testing'" class="text-muted text-sm">Testing...</span>
                    <span v-else-if="pbsServerStatus[srv.id] === true" class="badge badge--ok">Online</span>
                    <span v-else class="badge badge--fail">Offline</span>
                  </td>
                  <td>
                    <div class="flex gap-1">
                      <button
                        @click="testPbsServer(srv)"
                        class="btn btn-outline btn-sm"
                        :disabled="pbsServerStatus[srv.id] === 'testing'"
                      >Test</button>
                      <button
                        @click="togglePbsServerSnapshots(srv)"
                        class="btn btn-outline btn-sm"
                      >{{ expandedPbsServer === srv.id ? 'Hide Snapshots' : 'View Snapshots' }}</button>
                      <button @click="deletePbsServer(srv)" class="btn btn-danger btn-sm">Delete</button>
                    </div>
                  </td>
                </tr>
                <!-- Per-server snapshot sub-panel -->
                <tr v-if="expandedPbsServer === srv.id">
                  <td colspan="8" style="padding:0; background:var(--bg-secondary,rgba(0,0,0,0.15));">
                    <div class="pbs-server-snapshot-panel">
                      <div class="pbs-server-snapshot-header">
                        <strong class="text-sm">Snapshots for {{ srv.name }}</strong>
                        <div class="flex gap-1 align-center">
                          <select
                            v-model="pbsServerSnapshotState.selectedDatastore"
                            class="form-control form-control-sm"
                            :disabled="pbsServerSnapshotState.loadingDatastores"
                            @change="fetchPbsServerSnapshots(srv)"
                            style="min-width:160px;"
                          >
                            <option value="">{{ pbsServerSnapshotState.loadingDatastores ? 'Loading...' : 'Select datastore...' }}</option>
                            <option
                              v-for="ds in (pbsServerDatastores[srv.id] || [])"
                              :key="ds.store || ds.name"
                              :value="ds.store || ds.name"
                            >{{ ds.store || ds.name }}</option>
                          </select>
                          <button
                            @click="fetchPbsServerSnapshots(srv)"
                            class="btn btn-outline btn-sm"
                            :disabled="!pbsServerSnapshotState.selectedDatastore || pbsServerSnapshotState.loading"
                          >Refresh</button>
                        </div>
                      </div>

                      <div v-if="pbsServerSnapshotState.loading" class="loading-spinner" style="margin:1rem;"></div>
                      <div v-else-if="!pbsServerSnapshotState.selectedDatastore" class="text-center text-muted p-3 text-sm">
                        Select a datastore to view snapshots.
                      </div>
                      <div v-else-if="pbsServerSnapshotState.snapshots.length === 0" class="text-center text-muted p-3 text-sm">
                        No snapshots found.
                      </div>
                      <div v-else class="table-container">
                        <table class="table table-sm">
                          <thead>
                            <tr>
                              <th>Type</th>
                              <th>VM/CT ID</th>
                              <th>Date</th>
                              <th>Size</th>
                              <th>Verify</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="snap in pbsServerSnapshotState.snapshots" :key="`${snap['backup-type']}/${snap['backup-id']}/${snap['backup-time']}`">
                              <td><code class="text-xs">{{ snap['backup-type'] }}</code></td>
                              <td><span class="vmid-badge">{{ snap['backup-id'] }}</span></td>
                              <td class="text-sm">{{ formatDate(snap['backup-time']) }}</td>
                              <td class="text-sm">{{ snap.size !== undefined ? formatSize(snap.size) : '—' }}</td>
                              <td>
                                <span
                                  v-if="snap['verify-state']"
                                  :class="['verify-badge', snap['verify-state'] === 'ok' ? 'verify-badge--ok' : 'verify-badge--fail']"
                                >{{ snap['verify-state'] }}</span>
                                <span v-else class="text-muted text-xs">—</span>
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

    <!-- PBS Tasks tab -->
    <div v-if="activeTab === 'pbs-tasks'">
      <div class="card">
        <div class="card-header">
          <h3>PBS Tasks</h3>
          <div class="flex gap-1 align-center">
            <select v-model="pbsTasks.serverId" class="form-control form-control-sm" @change="fetchPbsTasks">
              <option value="">Select PBS server...</option>
              <option v-for="srv in pbsServerList" :key="srv.id" :value="srv.id">
                {{ srv.name }} ({{ srv.hostname }})
              </option>
            </select>
            <button
              @click="fetchPbsTasks"
              class="btn btn-outline btn-sm"
              :disabled="!pbsTasks.serverId || loadingPbsTasks"
            >Refresh</button>
          </div>
        </div>

        <div v-if="!pbsTasks.serverId" class="text-center text-muted p-3">
          Select a PBS server to view its task history.
        </div>
        <div v-else-if="loadingPbsTasks" class="loading-spinner"></div>
        <div v-else-if="pbsTasks.items.length === 0" class="text-center text-muted p-3">
          No tasks found.
        </div>
        <div v-else class="table-container">
          <table class="table table-sm">
            <thead>
              <tr>
                <th>Start Time</th>
                <th>Task Type</th>
                <th>User</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in pbsTasks.items" :key="task.upid">
                <td class="text-sm">{{ formatDate(task.starttime) }}</td>
                <td class="text-sm"><code>{{ task.worker_type || task.type || '—' }}</code></td>
                <td class="text-sm text-muted">{{ task.user || '—' }}</td>
                <td>
                  <span :class="['task-status-badge', taskStatusClass(task)]">
                    {{ task.status || (task.endtime ? 'stopped' : 'running') }}
                  </span>
                </td>
                <td class="text-sm text-muted">{{ formatDuration(task.starttime, task.endtime) }}</td>
                <td>
                  <button @click="openTaskLogModal(task)" class="btn btn-outline btn-sm">Log</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- PBS Browser tab -->
    <div v-if="activeTab === 'pbs'">
      <div class="card">
        <div class="card-header">
          <h3>PBS Datastore Browser</h3>
          <div class="flex gap-1 align-center">
            <select v-model="pbsBrowser.selectedServerId" class="form-control form-control-sm" @change="onPbsServerChange">
              <option value="">Select PBS server...</option>
              <option v-for="srv in pbsServers" :key="srv.id" :value="srv.id">
                {{ srv.name }} ({{ srv.hostname }})
              </option>
            </select>
            <select
              v-if="pbsBrowser.selectedServerId"
              v-model="pbsBrowser.selectedDatastore"
              class="form-control form-control-sm"
              :disabled="loadingPbsDatastores"
              @change="fetchPbsGroups"
            >
              <option value="">{{ loadingPbsDatastores ? 'Loading...' : 'Select datastore...' }}</option>
              <option v-for="ds in pbsBrowserDatastores" :key="ds.store || ds.name" :value="ds.store || ds.name">
                {{ ds.store || ds.name }}
              </option>
            </select>
            <button
              @click="fetchPbsGroups"
              class="btn btn-outline btn-sm"
              :disabled="!pbsBrowser.selectedServerId || !pbsBrowser.selectedDatastore || loadingPbsGroups"
            >
              Refresh
            </button>
          </div>
        </div>

        <!-- Loading PBS servers -->
        <div v-if="loadingPbsServers" class="loading-spinner"></div>

        <!-- No server selected -->
        <div v-else-if="!pbsBrowser.selectedServerId" class="text-center text-muted p-3">
          Select a PBS server to browse its datastores.
        </div>

        <!-- No datastore selected -->
        <div v-else-if="!pbsBrowser.selectedDatastore" class="text-center text-muted p-3">
          Select a datastore to browse backup groups.
        </div>

        <!-- Loading groups -->
        <div v-else-if="loadingPbsGroups" class="loading-spinner"></div>

        <!-- No groups -->
        <div v-else-if="pbsBrowserGroups.length === 0" class="text-center text-muted p-3">
          No backup groups found in this datastore.
        </div>

        <!-- Groups list -->
        <div v-else class="pbs-browser-groups">
          <div
            v-for="group in pbsBrowserGroups"
            :key="group['backup-type'] + '/' + group['backup-id']"
            class="pbs-group"
          >
            <!-- Group header row -->
            <div
              class="pbs-group-header"
              @click="togglePbsGroup(group)"
              :class="{ 'pbs-group-header--expanded': expandedPbsGroups[pbsGroupKey(group)] }"
            >
              <span class="pbs-group-chevron">{{ expandedPbsGroups[pbsGroupKey(group)] ? '▾' : '▸' }}</span>
              <span class="vmid-badge">{{ group['backup-type'] === 'vm' ? 'VMID' : group['backup-type'].toUpperCase() }} {{ group['backup-id'] }}</span>
              <span class="pbs-group-meta text-sm text-muted">
                Last backup: {{ group['last-backup'] ? formatDate(group['last-backup']) : '—' }}
              </span>
              <span class="pbs-group-meta text-sm text-muted">
                {{ group['backup-count'] ?? '?' }} snapshot{{ (group['backup-count'] ?? 0) !== 1 ? 's' : '' }}
              </span>
              <button
                @click.stop="openPruneModal(group)"
                class="btn btn-outline btn-sm pbs-group-action"
                title="Prune old snapshots in this group"
              >Prune</button>
            </div>

            <!-- Snapshots (expanded) -->
            <div v-if="expandedPbsGroups[pbsGroupKey(group)]" class="pbs-snapshots">
              <div v-if="loadingPbsSnapshots[pbsGroupKey(group)]" class="loading-spinner" style="margin: 0.75rem 0;"></div>
              <div v-else-if="!pbsSnapshots[pbsGroupKey(group)] || pbsSnapshots[pbsGroupKey(group)].length === 0" class="text-muted text-sm p-3">
                No snapshots found.
              </div>
              <table v-else class="table table-sm">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Size</th>
                    <th>Verify Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="snap in pbsSnapshots[pbsGroupKey(group)]" :key="snap['backup-time']">
                    <td>{{ formatDate(snap['backup-time']) }}</td>
                    <td>{{ snap.size !== undefined ? formatSize(snap.size) : '—' }}</td>
                    <td>
                      <span
                        v-if="snap['verify-state']"
                        :class="['verify-badge', snap['verify-state'] === 'ok' ? 'verify-badge--ok' : 'verify-badge--fail']"
                      >
                        {{ snap['verify-state'] }}
                      </span>
                      <span v-else class="text-muted text-xs">—</span>
                    </td>
                    <td>
                      <div class="flex gap-1">
                        <button
                          @click="openRestoreModalFromPbs(snap, group)"
                          class="btn btn-primary btn-sm"
                        >
                          Restore
                        </button>
                        <button
                          @click="verifyPbsSnapshot(snap, group)"
                          class="btn btn-outline btn-sm"
                          :disabled="verifyingSnapshot[pbsSnapshotKey(snap, group)]"
                          title="Verify this snapshot"
                        >
                          {{ verifyingSnapshot[pbsSnapshotKey(snap, group)] ? 'Verifying...' : 'Verify' }}
                        </button>
                        <button
                          @click="forgetPbsSnapshot(snap, group)"
                          class="btn btn-danger btn-sm"
                          :disabled="forgettingSnapshot[pbsSnapshotKey(snap, group)]"
                          title="Permanently delete this snapshot"
                        >
                          {{ forgettingSnapshot[pbsSnapshotKey(snap, group)] ? 'Deleting...' : 'Forget' }}
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Notifications tab -->
    <div v-if="activeTab === 'notifications'">
      <div class="card">
        <div class="card-header">
          <h3>Backup Notifications</h3>
        </div>
        <div class="card-body">
          <p class="text-muted text-sm mb-2">
            Configure email notifications for backup job results. Settings are applied to all backup schedules for this host.
          </p>

          <div class="form-group">
            <label class="form-label">Email Notifications</label>
            <div class="radio-group">
              <label class="radio-label">
                <input type="radio" v-model="notifForm.mailnotification" value="never" />
                <span>Disabled</span>
              </label>
              <label class="radio-label">
                <input type="radio" v-model="notifForm.mailnotification" value="failure" />
                <span>On failure only</span>
              </label>
              <label class="radio-label">
                <input type="radio" v-model="notifForm.mailnotification" value="always" />
                <span>Always (success &amp; failure)</span>
              </label>
            </div>
          </div>

          <div class="form-group" style="max-width: 420px;">
            <label class="form-label">Email Address</label>
            <input
              v-model="notifForm.mailto"
              type="email"
              class="form-control"
              placeholder="admin@example.com"
              :disabled="notifForm.mailnotification === 'never'"
            />
            <div class="text-xs text-muted mt-1">Separate multiple addresses with a comma.</div>
          </div>

          <div class="form-group">
            <label class="form-label">Apply to Schedule</label>
            <select v-model="notifForm.scheduleId" class="form-control" style="max-width: 340px;">
              <option value="">— All schedules —</option>
              <option v-for="sched in schedules" :key="sched.id" :value="sched.id">{{ sched.id }}</option>
            </select>
            <div class="text-xs text-muted mt-1">
              Choose a specific schedule, or leave blank to apply to all schedules.
            </div>
          </div>

          <div v-if="notifSaveResult" :class="['notif-result', notifSaveResult.ok ? 'notif-result--ok' : 'notif-result--err']">
            {{ notifSaveResult.message }}
          </div>

          <div class="flex gap-1 mt-2">
            <button
              @click="saveNotifications"
              class="btn btn-primary"
              :disabled="savingNotif || notifForm.mailnotification !== 'never' && !notifForm.mailto"
            >
              {{ savingNotif ? 'Saving...' : 'Save Notification Settings' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Retention Policies tab -->
    <div v-if="activeTab === 'retention'">
      <!-- Per-Schedule Retention -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Per-Schedule Retention</h3>
          <button @click="fetchSchedules" class="btn btn-outline btn-sm" :disabled="loadingSchedules">Refresh</button>
        </div>

        <div v-if="loadingSchedules" class="loading-spinner"></div>
        <div v-else-if="schedules.length === 0" class="text-center text-muted p-3">
          No backup schedules configured. Create a schedule first.
        </div>
        <div v-else>
          <div
            v-for="sched in schedules"
            :key="sched.id"
            class="retention-sched-card"
          >
            <div class="retention-sched-header">
              <div class="retention-sched-meta">
                <strong class="retention-sched-id">{{ sched.id }}</strong>
                <code class="retention-cron">{{ sched.schedule || '—' }}</code>
                <span class="text-muted text-sm">{{ sched.storage || 'no storage' }}</span>
              </div>
              <button
                @click="openRetentionEditModal(sched)"
                class="btn btn-outline btn-sm"
              >Edit Retention</button>
            </div>

            <!-- Current policy display -->
            <div class="retention-policy-chips">
              <span v-if="sched['keep-last']" class="retention-chip">Last: {{ sched['keep-last'] }}</span>
              <span v-if="sched['keep-daily']" class="retention-chip">Daily: {{ sched['keep-daily'] }}</span>
              <span v-if="sched['keep-weekly']" class="retention-chip">Weekly: {{ sched['keep-weekly'] }}</span>
              <span v-if="sched['keep-monthly']" class="retention-chip">Monthly: {{ sched['keep-monthly'] }}</span>
              <span v-if="sched['keep-yearly']" class="retention-chip">Yearly: {{ sched['keep-yearly'] }}</span>
              <span v-if="sched.maxfiles && !sched['keep-last']" class="retention-chip">Max files: {{ sched.maxfiles }}</span>
              <span
                v-if="!sched['keep-last'] && !sched['keep-daily'] && !sched['keep-weekly'] && !sched['keep-monthly'] && !sched['keep-yearly'] && !sched.maxfiles"
                class="text-muted text-sm"
              >No retention policy set (keep all)</span>
            </div>

            <!-- Visual retention timeline calculator -->
            <div v-if="retentionTimeline(sched).length > 0" class="retention-timeline">
              <div class="retention-timeline-label text-xs text-muted">Estimated backups kept over time:</div>
              <div class="retention-timeline-bars">
                <div
                  v-for="(bucket, i) in retentionTimeline(sched)"
                  :key="i"
                  class="retention-timeline-bucket"
                  :title="bucket.label + ': ' + bucket.count + ' backup(s)'"
                >
                  <div
                    class="retention-timeline-bar"
                    :style="{ height: Math.min(40, bucket.count * 8) + 'px' }"
                  ></div>
                  <span class="retention-timeline-tick text-xs text-muted">{{ bucket.shortLabel }}</span>
                </div>
              </div>
              <div class="retention-timeline-summary text-xs text-muted">
                ~{{ retentionTotal(sched) }} backup{{ retentionTotal(sched) !== 1 ? 's' : '' }} retained at steady state
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- PBS Per-Datastore Retention -->
      <div class="card">
        <div class="card-header">
          <h3>PBS Datastore Retention</h3>
          <div class="flex gap-1 align-center">
            <select v-model="retentionPbs.serverId" class="form-control form-control-sm" @change="fetchRetentionPbsDatastores">
              <option value="">Select PBS server...</option>
              <option v-for="srv in pbsServerList" :key="srv.id" :value="srv.id">
                {{ srv.name }} ({{ srv.hostname }})
              </option>
            </select>
          </div>
        </div>

        <div v-if="!retentionPbs.serverId" class="text-center text-muted p-3">
          Select a PBS server to manage per-datastore retention.
        </div>
        <div v-else-if="retentionPbs.loadingDatastores" class="loading-spinner"></div>
        <div v-else-if="retentionPbs.datastores.length === 0" class="text-center text-muted p-3">
          No datastores found on this PBS server.
        </div>
        <div v-else>
          <div
            v-for="ds in retentionPbs.datastores"
            :key="ds.store || ds.name"
            class="retention-ds-card"
          >
            <div class="retention-ds-header">
              <div>
                <strong>{{ ds.store || ds.name }}</strong>
                <span class="text-muted text-sm" style="margin-left: 0.5rem;">{{ ds.path || '' }}</span>
              </div>
              <button
                @click="openPbsRetentionModal(ds)"
                class="btn btn-outline btn-sm"
              >Configure Prune Policy</button>
            </div>

            <div v-if="retentionPbs.policies[ds.store || ds.name]" class="retention-policy-chips">
              <template v-for="(v, k) in retentionPbs.policies[ds.store || ds.name]" :key="k">
                <span v-if="v" class="retention-chip">{{ k.replace('keep-', '') }}: {{ v }}</span>
              </template>
            </div>
            <div v-else class="text-muted text-sm" style="padding: 0.25rem 0;">
              No prune policy configured — all backups kept.
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Run Now Modal (per schedule) -->
    <div v-if="runNowModal.show" class="modal" @click="closeRunNowModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Run Schedule Now</h3>
          <button @click="closeRunNowModal" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <div class="restore-source-info mb-2">
            <div class="text-sm text-muted">Schedule: <strong>{{ runNowModal.scheduleId }}</strong></div>
          </div>

          <div v-if="runNowModal.result" :class="['notif-result', runNowModal.result.ok ? 'notif-result--ok' : 'notif-result--err']" style="margin-bottom:1rem;">
            {{ runNowModal.result.message }}
            <div v-if="runNowModal.result.upid" class="mt-1">
              <span class="text-xs text-muted">Task UPID: </span>
              <code class="upid-code" style="display:inline;font-size:0.75rem;">{{ runNowModal.result.upid }}</code>
            </div>
          </div>

          <div v-if="!runNowModal.result">
            <div class="form-group mb-2">
              <label class="form-label">Target Node <span class="required">*</span></label>
              <select v-model="runNowModal.node" class="form-control" required>
                <option value="">Select node...</option>
                <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">
                  {{ n.node || n.name }}
                </option>
              </select>
              <div class="text-xs text-muted mt-1">The node that will execute the backup job.</div>
            </div>
            <p class="text-sm text-muted">
              This will immediately trigger the backup job defined by schedule <strong>{{ runNowModal.scheduleId }}</strong>.
              A task UPID will be returned to track progress.
            </p>
          </div>

          <div class="flex gap-1 mt-2">
            <button
              v-if="!runNowModal.result"
              @click="submitRunNow"
              class="btn btn-primary"
              :disabled="runNowModal.running || !runNowModal.node"
            >
              {{ runNowModal.running ? 'Starting...' : 'Run Now' }}
            </button>
            <button @click="closeRunNowModal" class="btn btn-outline">{{ runNowModal.result ? 'Close' : 'Cancel' }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create / Edit Schedule Modal — 4-step wizard -->
    <div v-if="scheduleModal.show" class="modal" @click="closeScheduleModal">
      <div class="modal-content modal-content--wide sched-wizard" @click.stop>
        <div class="modal-header">
          <div>
            <h3 style="margin:0;">{{ scheduleModal.editing ? 'Edit Schedule' : 'Create Backup Schedule' }}</h3>
            <p class="text-muted text-sm" style="margin:0.2rem 0 0;">{{ schedWizardStepTitle }}</p>
          </div>
          <button @click="closeScheduleModal" class="btn-close">&#215;</button>
        </div>

        <!-- Step indicator -->
        <div class="sched-wizard-steps" v-if="!scheduleModal.editing">
          <div
            v-for="(lbl, idx) in ['Scope', 'Storage & Timing', 'Options', 'Review']"
            :key="idx"
            :class="['sw-step', schedWizardStep === idx + 1 ? 'sw-step--active' : schedWizardStep > idx + 1 ? 'sw-step--done' : '']"
          >
            <span class="sw-step-num">{{ idx + 1 }}</span>
            <span class="sw-step-label">{{ lbl }}</span>
          </div>
        </div>

        <div class="modal-body">

          <!-- ── Edit mode: single flat form ── -->
          <form v-if="scheduleModal.editing" @submit.prevent="saveSchedule">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Node</label>
                <select v-model="scheduleForm.node" class="form-control">
                  <option value="">All nodes</option>
                  <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">{{ n.node || n.name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Storage <span class="required">*</span></label>
                <input v-model="scheduleForm.storage" class="form-control" required />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Schedule (cron) <span class="required">*</span></label>
                <input v-model="scheduleForm.schedule" class="form-control" required />
              </div>
              <div class="form-group">
                <label class="form-label">VM IDs</label>
                <input v-model="scheduleForm.vmid" class="form-control" placeholder='all or 100,101' />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Compression</label>
                <select v-model="scheduleForm.compress" class="form-control">
                  <option value="zstd">zstd (recommended)</option>
                  <option value="lzo">lzo</option>
                  <option value="gzip">gzip</option>
                  <option value="0">none</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Mode</label>
                <select v-model="scheduleForm.mode" class="form-control">
                  <option value="snapshot">snapshot</option>
                  <option value="suspend">suspend</option>
                  <option value="stop">stop</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Keep Last</label>
                <input v-model.number="scheduleForm['keep-last']" type="number" min="0" class="form-control" />
              </div>
              <div class="form-group">
                <label class="form-label">Keep Daily</label>
                <input v-model.number="scheduleForm['keep-daily']" type="number" min="0" class="form-control" />
              </div>
              <div class="form-group">
                <label class="form-label">Keep Weekly</label>
                <input v-model.number="scheduleForm['keep-weekly']" type="number" min="0" class="form-control" />
              </div>
              <div class="form-group">
                <label class="form-label">Keep Monthly</label>
                <input v-model.number="scheduleForm['keep-monthly']" type="number" min="0" class="form-control" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Comment</label>
              <input v-model="scheduleForm.comment" class="form-control" placeholder="Optional description" />
            </div>
            <div class="flex gap-1 mt-2">
              <button type="submit" class="btn btn-primary" :disabled="savingSchedule">
                {{ savingSchedule ? 'Saving...' : 'Save Changes' }}
              </button>
              <button type="button" @click="closeScheduleModal" class="btn btn-outline">Cancel</button>
            </div>
          </form>

          <!-- ── Create wizard steps ── -->
          <template v-else>

            <!-- Step 1: Scope -->
            <div v-if="schedWizardStep === 1">
              <div class="form-group">
                <label class="form-label">Backup Scope</label>
                <div class="scope-options">
                  <label :class="['scope-opt', scheduleForm.scopeType === 'all' ? 'scope-opt--active' : '']">
                    <input type="radio" v-model="scheduleForm.scopeType" value="all" />
                    <div class="scope-opt-body">
                      <strong>All VMs on host</strong>
                      <span class="text-muted text-xs">Back up every VM and container on the selected host</span>
                    </div>
                  </label>
                  <label :class="['scope-opt', scheduleForm.scopeType === 'nodes' ? 'scope-opt--active' : '']">
                    <input type="radio" v-model="scheduleForm.scopeType" value="nodes" />
                    <div class="scope-opt-body">
                      <strong>Specific nodes</strong>
                      <span class="text-muted text-xs">Back up all VMs on selected nodes only</span>
                    </div>
                  </label>
                  <label :class="['scope-opt', scheduleForm.scopeType === 'vmids' ? 'scope-opt--active' : '']">
                    <input type="radio" v-model="scheduleForm.scopeType" value="vmids" />
                    <div class="scope-opt-body">
                      <strong>Specific VMIDs</strong>
                      <span class="text-muted text-xs">Back up only the listed VM/CT IDs</span>
                    </div>
                  </label>
                </div>
              </div>

              <!-- Node multi-select -->
              <div v-if="scheduleForm.scopeType === 'nodes'" class="form-group">
                <label class="form-label">Select Nodes <span class="required">*</span></label>
                <div class="node-checklist">
                  <label v-for="n in clusterNodes" :key="n.node || n.name" class="node-check-item">
                    <input
                      type="checkbox"
                      :value="n.node || n.name"
                      v-model="scheduleForm.selectedNodes"
                    />
                    <span>{{ n.node || n.name }}</span>
                  </label>
                </div>
                <div class="text-xs text-muted mt-1">Proxmox backup schedules execute per-node; one schedule will be created per selected node.</div>
              </div>

              <!-- VMID list input -->
              <div v-if="scheduleForm.scopeType === 'vmids'" class="form-group">
                <label class="form-label">VM / CT IDs <span class="required">*</span></label>
                <div class="vmid-tag-input" @click="$refs.vmidInput.focus()">
                  <span
                    v-for="(id, idx) in scheduleForm.vmidList"
                    :key="idx"
                    class="vmid-tag"
                  >
                    {{ id }}
                    <button type="button" @click.stop="removeVmidTag(idx)" class="vmid-tag-remove">×</button>
                  </span>
                  <input
                    ref="vmidInput"
                    v-model="vmidTagInput"
                    @keydown.enter.prevent="addVmidTag"
                    @keydown.comma.prevent="addVmidTag"
                    @keydown.tab.prevent="addVmidTag"
                    @keydown.backspace="onVmidBackspace"
                    class="vmid-tag-text-input"
                    placeholder="Type VMID + Enter"
                  />
                </div>
                <div class="text-xs text-muted mt-1">Press Enter or comma to add each VMID.</div>
              </div>

              <div class="form-group">
                <label class="form-label">Comment</label>
                <input v-model="scheduleForm.comment" class="form-control" placeholder="Optional description for this schedule" />
              </div>
            </div>

            <!-- Step 2: Storage & Timing -->
            <div v-if="schedWizardStep === 2">
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">Node (for storage list) <span class="required">*</span></label>
                  <select v-model="scheduleForm.storageNode" class="form-control" @change="fetchSchedStorages">
                    <option value="">Select node...</option>
                    <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">{{ n.node || n.name }}</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Storage <span class="required">*</span></label>
                  <select v-model="scheduleForm.storage" class="form-control" :disabled="loadingSchedStorages || !scheduleForm.storageNode">
                    <option value="">{{ loadingSchedStorages ? 'Loading...' : 'Select storage...' }}</option>
                    <option v-for="s in schedStorages" :key="s.storage" :value="s.storage">
                      {{ s.storage }}{{ s.type ? ` (${s.type})` : '' }}
                    </option>
                  </select>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Schedule Preset</label>
                <div class="cron-presets">
                  <button
                    type="button"
                    v-for="preset in cronPresets"
                    :key="preset.label"
                    :class="['cron-preset-btn', scheduleForm.schedule === preset.value ? 'cron-preset-btn--active' : '']"
                    @click="scheduleForm.schedule = preset.value; scheduleForm.cronCustom = false"
                  >{{ preset.label }}</button>
                  <button
                    type="button"
                    :class="['cron-preset-btn', scheduleForm.cronCustom ? 'cron-preset-btn--active' : '']"
                    @click="scheduleForm.cronCustom = true"
                  >Custom</button>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Cron Expression <span class="required">*</span></label>
                <input
                  v-model="scheduleForm.schedule"
                  class="form-control"
                  placeholder="e.g. 0 2 * * *"
                  :readonly="!scheduleForm.cronCustom && !scheduleModal.editing"
                  @input="scheduleForm.cronCustom = true"
                />
                <div class="text-xs text-muted mt-1">Format: minute hour day-of-month month day-of-week</div>
              </div>

              <div class="sched-retention-row">
                <div class="form-group">
                  <label class="form-label">Keep Last</label>
                  <input v-model.number="scheduleForm['keep-last']" type="number" min="0" class="form-control" placeholder="e.g. 3" />
                  <span class="form-hint">Most recent N</span>
                </div>
                <div class="form-group">
                  <label class="form-label">Keep Daily</label>
                  <input v-model.number="scheduleForm['keep-daily']" type="number" min="0" class="form-control" placeholder="e.g. 7" />
                  <span class="form-hint">1/day for N days</span>
                </div>
                <div class="form-group">
                  <label class="form-label">Keep Weekly</label>
                  <input v-model.number="scheduleForm['keep-weekly']" type="number" min="0" class="form-control" placeholder="e.g. 4" />
                  <span class="form-hint">1/week for N weeks</span>
                </div>
                <div class="form-group">
                  <label class="form-label">Keep Monthly</label>
                  <input v-model.number="scheduleForm['keep-monthly']" type="number" min="0" class="form-control" placeholder="e.g. 3" />
                  <span class="form-hint">1/month for N months</span>
                </div>
              </div>
            </div>

            <!-- Step 3: Options -->
            <div v-if="schedWizardStep === 3">
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">Compression</label>
                  <select v-model="scheduleForm.compress" class="form-control">
                    <option value="zstd">zstd (recommended)</option>
                    <option value="lzo">lzo (fast)</option>
                    <option value="gzip">gzip (compatible)</option>
                    <option value="0">none</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Mode</label>
                  <select v-model="scheduleForm.mode" class="form-control">
                    <option value="snapshot">snapshot (live, no downtime)</option>
                    <option value="suspend">suspend (pause then backup)</option>
                    <option value="stop">stop (shut down then backup)</option>
                  </select>
                </div>
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">Email Notification</label>
                  <select v-model="scheduleForm.mailnotification" class="form-control">
                    <option value="never">Disabled</option>
                    <option value="failure">On failure only</option>
                    <option value="always">Always</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Email Address</label>
                  <input
                    v-model="scheduleForm.mailto"
                    type="email"
                    class="form-control"
                    placeholder="admin@example.com"
                    :disabled="scheduleForm.mailnotification === 'never'"
                  />
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Bandwidth Limit (KB/s)</label>
                <input
                  v-model.number="scheduleForm.bwlimit"
                  type="number"
                  min="0"
                  class="form-control"
                  placeholder="0 = unlimited"
                  style="max-width:200px;"
                />
                <div class="text-xs text-muted mt-1">Throttle I/O bandwidth. 0 or blank = unlimited.</div>
              </div>
            </div>

            <!-- Step 4: Review -->
            <div v-if="schedWizardStep === 4">
              <div class="review-sections">
                <div class="review-section">
                  <div class="review-section-title">Scope</div>
                  <div class="review-row">
                    <span>Type</span>
                    <span>{{ { all: 'All VMs on host', nodes: 'Specific nodes', vmids: 'Specific VMIDs' }[scheduleForm.scopeType] }}</span>
                  </div>
                  <div v-if="scheduleForm.scopeType === 'nodes'" class="review-row">
                    <span>Nodes</span><span>{{ scheduleForm.selectedNodes.join(', ') || '—' }}</span>
                  </div>
                  <div v-if="scheduleForm.scopeType === 'vmids'" class="review-row">
                    <span>VMIDs</span><span>{{ scheduleForm.vmidList.join(', ') || '—' }}</span>
                  </div>
                  <div v-if="scheduleForm.comment" class="review-row">
                    <span>Comment</span><span>{{ scheduleForm.comment }}</span>
                  </div>
                </div>

                <div class="review-section">
                  <div class="review-section-title">Storage & Timing</div>
                  <div class="review-row"><span>Storage</span><span>{{ scheduleForm.storage || '—' }}</span></div>
                  <div class="review-row"><span>Schedule</span><code>{{ scheduleForm.schedule || '—' }}</code></div>
                  <div class="review-row" v-if="scheduleForm['keep-last']"><span>Keep Last</span><span>{{ scheduleForm['keep-last'] }}</span></div>
                  <div class="review-row" v-if="scheduleForm['keep-daily']"><span>Keep Daily</span><span>{{ scheduleForm['keep-daily'] }}</span></div>
                  <div class="review-row" v-if="scheduleForm['keep-weekly']"><span>Keep Weekly</span><span>{{ scheduleForm['keep-weekly'] }}</span></div>
                  <div class="review-row" v-if="scheduleForm['keep-monthly']"><span>Keep Monthly</span><span>{{ scheduleForm['keep-monthly'] }}</span></div>
                </div>

                <div class="review-section">
                  <div class="review-section-title">Options</div>
                  <div class="review-row"><span>Compression</span><span>{{ scheduleForm.compress }}</span></div>
                  <div class="review-row"><span>Mode</span><span>{{ scheduleForm.mode }}</span></div>
                  <div class="review-row"><span>Email</span><span>{{ scheduleForm.mailnotification === 'never' ? 'Disabled' : scheduleForm.mailnotification }}</span></div>
                  <div v-if="scheduleForm.bwlimit" class="review-row"><span>Bandwidth</span><span>{{ scheduleForm.bwlimit }} KB/s</span></div>
                </div>
              </div>

              <div v-if="scheduleForm.scopeType === 'nodes' && scheduleForm.selectedNodes.length > 1" class="info-box mt-2">
                <strong>{{ scheduleForm.selectedNodes.length }} schedules</strong> will be created — one for each selected node.
              </div>
            </div>

          </template>
        </div>

        <!-- Footer -->
        <div class="sched-wizard-footer">
          <button
            v-if="!scheduleModal.editing && schedWizardStep > 1"
            type="button"
            @click="schedWizardStep--"
            class="btn btn-outline"
            :disabled="savingSchedule"
          >Back</button>
          <span style="flex:1;" />
          <template v-if="!scheduleModal.editing">
            <button
              v-if="schedWizardStep < 4"
              type="button"
              @click="schedWizardNext"
              class="btn btn-primary"
              :disabled="!schedWizardCanNext"
            >Next</button>
            <button
              v-else
              type="button"
              @click="saveSchedule"
              class="btn btn-primary"
              :disabled="savingSchedule"
            >{{ savingSchedule ? 'Creating...' : 'Create Schedule' }}</button>
          </template>
          <button type="button" @click="closeScheduleModal" class="btn btn-outline">{{ scheduleModal.editing ? 'Cancel' : 'Cancel' }}</button>
        </div>
      </div>
    </div>

    <!-- Quick Backup Modal -->
    <div v-if="quickBackupModal.show" class="modal" @click="closeQuickBackupModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Quick Backup</h3>
          <button @click="closeQuickBackupModal" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <!-- Task progress after start -->
          <div v-if="quickBackupModal.upid" class="restore-progress mb-2">
            <div class="restore-progress-header">
              <strong>Backup Task</strong>
              <span :class="['task-status-badge', `task-status-badge--${quickBackupModal.taskStatus || 'running'}`]">
                {{ quickBackupModal.taskStatus || 'running' }}
              </span>
            </div>
            <code class="upid-code">{{ quickBackupModal.upid }}</code>
            <div v-if="quickBackupModal.taskStatus === 'running'" class="progress-bar-wrap mt-1">
              <div class="progress-bar progress-bar--animated"></div>
            </div>
            <div v-if="quickBackupModal.taskLog.length > 0" class="quick-backup-log mt-1">
              <div class="quick-backup-log-title text-xs text-muted">Task output:</div>
              <pre class="task-log-pre" style="max-height:200px;">{{ quickBackupModal.taskLog.join('\n') }}</pre>
            </div>
            <div v-if="quickBackupModal.taskStatus === 'stopped'" class="text-sm text-success mt-1">
              Backup completed successfully.
            </div>
          </div>

          <!-- Form (hidden once task started) -->
          <form v-if="!quickBackupModal.upid" @submit.prevent="submitQuickBackup">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Node <span class="required">*</span></label>
                <select v-model="quickBackupForm.node" class="form-control" required @change="fetchQuickBackupNodeData">
                  <option value="">Select node...</option>
                  <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">{{ n.node || n.name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Storage <span class="required">*</span></label>
                <select v-model="quickBackupForm.storage" class="form-control" required :disabled="loadingQuickBackupData || !quickBackupForm.node">
                  <option value="">{{ loadingQuickBackupData ? 'Loading...' : 'Select storage...' }}</option>
                  <option v-for="s in quickBackupStorages" :key="s.storage" :value="s.storage">{{ s.storage }}{{ s.type ? ` (${s.type})` : '' }}</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">VM / Container</label>
              <select v-model="quickBackupForm.vmid" class="form-control" :disabled="loadingQuickBackupData || !quickBackupForm.node">
                <option value="">All VMs and containers on node</option>
                <option v-for="vm in quickBackupVMs" :key="vm.vmid" :value="String(vm.vmid)">
                  {{ vm.vmid }} — {{ vm.name || '(unnamed)' }} [{{ vm.type || 'qemu' }}]
                </option>
              </select>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Compression</label>
                <select v-model="quickBackupForm.compress" class="form-control">
                  <option value="zstd">zstd (recommended)</option>
                  <option value="lzo">lzo</option>
                  <option value="gzip">gzip</option>
                  <option value="0">none</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Mode</label>
                <select v-model="quickBackupForm.mode" class="form-control">
                  <option value="snapshot">snapshot</option>
                  <option value="suspend">suspend</option>
                  <option value="stop">stop</option>
                </select>
              </div>
            </div>

            <div v-if="quickBackupModal.error" class="error-banner mt-1">{{ quickBackupModal.error }}</div>

            <div class="flex gap-1 mt-2">
              <button type="submit" class="btn btn-primary" :disabled="quickBackupModal.running">
                {{ quickBackupModal.running ? 'Starting...' : 'Start Backup Now' }}
              </button>
              <button type="button" @click="closeQuickBackupModal" class="btn btn-outline">Cancel</button>
            </div>
          </form>

          <div v-if="quickBackupModal.upid" class="flex gap-1 mt-2">
            <button @click="closeQuickBackupModal" class="btn btn-outline">Close</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Restore Modal -->
    <div v-if="restoreModal.show" class="modal" @click="closeRestoreModal">
      <div class="modal-content modal-content--wide" @click.stop>
        <div class="modal-header">
          <h3>Restore Backup</h3>
          <button @click="closeRestoreModal" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <!-- Source info -->
          <div class="restore-source-info mb-2">
            <div class="text-sm text-muted">Restoring from:</div>
            <code class="upid-code">{{ restoreModal.volid }}</code>
          </div>

          <!-- Task progress (shown after restore starts) -->
          <div v-if="restoreTask.upid" class="restore-progress mb-2">
            <div class="restore-progress-header">
              <strong>Restore Task</strong>
              <span :class="['task-status-badge', `task-status-badge--${restoreTask.status}`]">
                {{ restoreTask.status }}
              </span>
            </div>
            <code class="upid-code">{{ restoreTask.upid }}</code>
            <div v-if="restoreTask.status === 'running'" class="progress-bar-wrap mt-1">
              <div class="progress-bar progress-bar--animated"></div>
            </div>
            <div v-if="restoreTask.exitstatus && restoreTask.exitstatus !== 'OK'" class="text-sm text-danger mt-1">
              Exit status: {{ restoreTask.exitstatus }}
            </div>
            <div v-if="restoreTask.status === 'stopped' && restoreTask.exitstatus === 'OK'" class="text-sm text-success mt-1">
              Restore completed successfully.
            </div>
          </div>

          <!-- Restore form (hidden once task is running/done) -->
          <form v-if="!restoreTask.upid" @submit.prevent="submitRestore">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Target VM ID <span class="required">*</span></label>
                <input
                  v-model.number="restoreForm.vmid"
                  type="number"
                  class="form-control"
                  min="100"
                  max="999999999"
                  required
                />
                <div class="text-xs text-muted mt-1">The VM ID that will be created/overwritten.</div>
              </div>
              <div class="form-group">
                <label class="form-label">Target Node <span class="required">*</span></label>
                <select v-model="restoreForm.node" class="form-control" required @change="onRestoreFormNodeChange">
                  <option value="">Select node...</option>
                  <option v-for="n in clusterNodes" :key="n.node || n.name" :value="n.node || n.name">
                    {{ n.node || n.name }}
                  </option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Target Storage <span class="required">*</span></label>
                <select v-model="restoreForm.storage" class="form-control" required :disabled="loadingRestoreTargetStorages || !restoreForm.node">
                  <option value="">{{ loadingRestoreTargetStorages ? 'Loading...' : 'Select storage...' }}</option>
                  <option v-for="s in restoreTargetStorages" :key="s.storage" :value="s.storage">
                    {{ s.storage }}{{ s.type ? ` (${s.type})` : '' }}
                  </option>
                </select>
              </div>
              <div class="form-group form-group--center">
                <label class="form-label">&nbsp;</label>
                <label class="checkbox-label">
                  <input type="checkbox" v-model="restoreForm.start" />
                  <span>Start VM after restore</span>
                </label>
              </div>
            </div>

            <div class="flex gap-1 mt-2">
              <button type="submit" class="btn btn-primary" :disabled="restoringBackup">
                {{ restoringBackup ? 'Starting restore...' : 'Restore' }}
              </button>
              <button type="button" @click="closeRestoreModal" class="btn btn-outline">Cancel</button>
            </div>
          </form>

          <!-- Actions after task started -->
          <div v-if="restoreTask.upid" class="flex gap-1 mt-2">
            <button @click="closeRestoreModal" class="btn btn-outline">Close</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add PBS Server Modal -->
    <div v-if="addPbsServerModal.show" class="modal" @click="closeAddPbsServerModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add PBS Server</h3>
          <button @click="closeAddPbsServerModal" class="btn-close">&#215;</button>
        </div>
        <form @submit.prevent="submitAddPbsServer" class="modal-body">
          <div class="form-group">
            <label class="form-label">Name <span class="required">*</span></label>
            <input v-model="addPbsServerForm.name" class="form-control" placeholder="e.g. pbs-main" required />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Hostname <span class="required">*</span></label>
              <input v-model="addPbsServerForm.hostname" class="form-control" placeholder="pbs.example.com" required />
            </div>
            <div class="form-group">
              <label class="form-label">Port</label>
              <input v-model.number="addPbsServerForm.port" type="number" class="form-control" min="1" max="65535" />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="addPbsServerForm.username" class="form-control" placeholder="root@pam" />
            <div class="text-xs text-muted mt-1">Used for display purposes.</div>
          </div>

          <div class="form-group">
            <label class="form-label">API Token ID <span class="required">*</span></label>
            <input
              v-model="addPbsServerForm.api_token_id"
              class="form-control"
              placeholder="root@pam!mytoken"
              required
            />
            <div class="text-xs text-muted mt-1">Format: user@realm!tokenname</div>
          </div>

          <div class="form-group">
            <label class="form-label">API Token Secret <span class="required">*</span></label>
            <input
              v-model="addPbsServerForm.api_token_secret"
              class="form-control"
              type="password"
              placeholder="Token secret value"
              required
            />
          </div>

          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="addPbsServerForm.verify_ssl" />
              <span>Verify SSL Certificate</span>
            </label>
            <div class="text-xs text-muted mt-1">Disable for self-signed certificates (typical for PBS).</div>
          </div>

          <div v-if="addPbsServerModal.error" class="error-banner mt-1">{{ addPbsServerModal.error }}</div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="addPbsServerModal.saving">
              {{ addPbsServerModal.saving ? 'Adding...' : 'Add Server' }}
            </button>
            <button type="button" @click="closeAddPbsServerModal" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Prune Modal -->
    <div v-if="pruneModal.show" class="modal" @click="closePruneModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Prune Backup Group</h3>
          <button @click="closePruneModal" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <div class="restore-source-info mb-2">
            <div class="text-sm text-muted">Group:</div>
            <code class="upid-code">{{ pruneModal.group ? `${pruneModal.group['backup-type']}/${pruneModal.group['backup-id']}` : '' }}</code>
          </div>

          <p class="text-sm text-muted mb-2">
            Configure how many snapshots to retain. Older snapshots will be permanently deleted.
            Leave fields blank to use PBS defaults.
          </p>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Keep Last</label>
              <input v-model.number="pruneForm['keep-last']" type="number" min="0" class="form-control" placeholder="e.g. 5" />
            </div>
            <div class="form-group">
              <label class="form-label">Keep Hourly</label>
              <input v-model.number="pruneForm['keep-hourly']" type="number" min="0" class="form-control" placeholder="e.g. 0" />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Keep Daily</label>
              <input v-model.number="pruneForm['keep-daily']" type="number" min="0" class="form-control" placeholder="e.g. 7" />
            </div>
            <div class="form-group">
              <label class="form-label">Keep Weekly</label>
              <input v-model.number="pruneForm['keep-weekly']" type="number" min="0" class="form-control" placeholder="e.g. 4" />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Keep Monthly</label>
              <input v-model.number="pruneForm['keep-monthly']" type="number" min="0" class="form-control" placeholder="e.g. 12" />
            </div>
            <div class="form-group">
              <label class="form-label">Keep Yearly</label>
              <input v-model.number="pruneForm['keep-yearly']" type="number" min="0" class="form-control" placeholder="e.g. 0" />
            </div>
          </div>

          <div v-if="pruneModal.result" :class="['notif-result', pruneModal.result.ok ? 'notif-result--ok' : 'notif-result--err']">
            {{ pruneModal.result.message }}
          </div>

          <div class="flex gap-1 mt-2">
            <button @click="submitPrune" class="btn btn-primary" :disabled="pruneModal.saving">
              {{ pruneModal.saving ? 'Pruning...' : 'Prune Now' }}
            </button>
            <button @click="closePruneModal" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Task Log Modal -->
    <div v-if="taskLogModal.show" class="modal" @click="closeTaskLogModal">
      <div class="modal-content modal-content--wide" @click.stop>
        <div class="modal-header">
          <h3>Task Log</h3>
          <button @click="closeTaskLogModal" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <div class="restore-source-info mb-2">
            <div class="text-sm text-muted">UPID:</div>
            <code class="upid-code">{{ taskLogModal.upid }}</code>
          </div>
          <div v-if="taskLogModal.loading" class="loading-spinner"></div>
          <div v-else-if="taskLogModal.lines.length === 0" class="text-muted text-sm">No log output.</div>
          <pre v-else class="task-log-pre">{{ taskLogModal.lines.join('\n') }}</pre>
          <div class="flex gap-1 mt-2">
            <button @click="closeTaskLogModal" class="btn btn-outline">Close</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Retention Edit Modal (per-schedule) -->
    <div v-if="retentionModal.show" class="modal" @click="closeRetentionModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Edit Retention Policy</h3>
          <button @click="closeRetentionModal" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <div class="restore-source-info mb-2">
            <div class="text-sm text-muted">Schedule: <strong>{{ retentionModal.scheduleId }}</strong></div>
          </div>

          <p class="text-sm text-muted mb-2">
            Configure how many backups to retain. Leave blank for no limit on that dimension.
          </p>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Keep Last</label>
              <input v-model.number="retentionForm['keep-last']" type="number" min="0" class="form-control" placeholder="e.g. 3" />
              <div class="text-xs text-muted mt-1">Keep the N most recent backups regardless of schedule.</div>
            </div>
            <div class="form-group">
              <label class="form-label">Keep Daily</label>
              <input v-model.number="retentionForm['keep-daily']" type="number" min="0" class="form-control" placeholder="e.g. 7" />
              <div class="text-xs text-muted mt-1">Keep 1 backup per day for the last N days.</div>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Keep Weekly</label>
              <input v-model.number="retentionForm['keep-weekly']" type="number" min="0" class="form-control" placeholder="e.g. 4" />
              <div class="text-xs text-muted mt-1">Keep 1 backup per week for the last N weeks.</div>
            </div>
            <div class="form-group">
              <label class="form-label">Keep Monthly</label>
              <input v-model.number="retentionForm['keep-monthly']" type="number" min="0" class="form-control" placeholder="e.g. 3" />
              <div class="text-xs text-muted mt-1">Keep 1 backup per month for the last N months.</div>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Keep Yearly</label>
              <input v-model.number="retentionForm['keep-yearly']" type="number" min="0" class="form-control" placeholder="e.g. 1" />
              <div class="text-xs text-muted mt-1">Keep 1 backup per year for the last N years.</div>
            </div>
          </div>

          <!-- Preview -->
          <div v-if="retentionPreviewTotal > 0" class="retention-preview-box">
            <strong class="text-sm">Policy Preview</strong>
            <div class="retention-preview-chips">
              <span v-if="retentionForm['keep-last']" class="retention-chip">Last {{ retentionForm['keep-last'] }}</span>
              <span v-if="retentionForm['keep-daily']" class="retention-chip">{{ retentionForm['keep-daily'] }} daily</span>
              <span v-if="retentionForm['keep-weekly']" class="retention-chip">{{ retentionForm['keep-weekly'] }} weekly</span>
              <span v-if="retentionForm['keep-monthly']" class="retention-chip">{{ retentionForm['keep-monthly'] }} monthly</span>
              <span v-if="retentionForm['keep-yearly']" class="retention-chip">{{ retentionForm['keep-yearly'] }} yearly</span>
            </div>
            <div class="text-sm text-muted">
              Approximately <strong>{{ retentionPreviewTotal }}</strong> backups retained at steady state.
            </div>
          </div>

          <div v-if="retentionModal.result" :class="['notif-result', retentionModal.result.ok ? 'notif-result--ok' : 'notif-result--err']">
            {{ retentionModal.result.message }}
          </div>

          <div class="flex gap-1 mt-2">
            <button @click="saveRetentionPolicy" class="btn btn-primary" :disabled="retentionModal.saving">
              {{ retentionModal.saving ? 'Saving...' : 'Save Policy' }}
            </button>
            <button @click="closeRetentionModal" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- PBS Prune Policy Modal (per-datastore) -->
    <div v-if="pbsRetentionModal.show" class="modal" @click="closePbsRetentionModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Configure Prune Policy</h3>
          <button @click="closePbsRetentionModal" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <div class="restore-source-info mb-2">
            <div class="text-sm text-muted">Datastore: <strong>{{ pbsRetentionModal.dsName }}</strong></div>
          </div>

          <p class="text-sm text-muted mb-2">
            Set the prune/garbage-collection policy for this datastore.
            This will be applied to all backup groups when a prune job runs.
          </p>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Keep Last</label>
              <input v-model.number="pbsRetentionForm['keep-last']" type="number" min="0" class="form-control" placeholder="e.g. 3" />
            </div>
            <div class="form-group">
              <label class="form-label">Keep Hourly</label>
              <input v-model.number="pbsRetentionForm['keep-hourly']" type="number" min="0" class="form-control" placeholder="e.g. 0" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Keep Daily</label>
              <input v-model.number="pbsRetentionForm['keep-daily']" type="number" min="0" class="form-control" placeholder="e.g. 7" />
            </div>
            <div class="form-group">
              <label class="form-label">Keep Weekly</label>
              <input v-model.number="pbsRetentionForm['keep-weekly']" type="number" min="0" class="form-control" placeholder="e.g. 4" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Keep Monthly</label>
              <input v-model.number="pbsRetentionForm['keep-monthly']" type="number" min="0" class="form-control" placeholder="e.g. 12" />
            </div>
            <div class="form-group">
              <label class="form-label">Keep Yearly</label>
              <input v-model.number="pbsRetentionForm['keep-yearly']" type="number" min="0" class="form-control" placeholder="e.g. 0" />
            </div>
          </div>

          <!-- Apply to existing backups section -->
          <div class="prune-apply-section">
            <h4 class="prune-apply-title">Apply to Existing Backups</h4>
            <p class="text-sm text-muted mb-2">
              Run a prune job now on all groups in this datastore using the policy above.
              A preview is shown before deletion.
            </p>
            <div v-if="pbsRetentionModal.prunePreview" class="prune-preview-box">
              <div class="prune-preview-header">
                <strong class="text-sm">Prune Preview</strong>
                <span class="text-sm text-muted">{{ pbsRetentionModal.prunePreview.length }} group(s)</span>
              </div>
              <div v-if="pbsRetentionModal.prunePreview.length === 0" class="text-sm text-muted" style="padding: 0.5rem 0;">
                No backups would be deleted.
              </div>
              <div v-else class="prune-preview-list">
                <div
                  v-for="item in pbsRetentionModal.prunePreview.slice(0, 10)"
                  :key="item.key"
                  class="prune-preview-item"
                >
                  <span class="text-sm">{{ item['backup-type'] }}/{{ item['backup-id'] }}</span>
                  <span class="text-danger text-sm">-{{ item.remove }} to remove</span>
                  <span class="text-success text-sm">keep {{ item.keep }}</span>
                </div>
                <div v-if="pbsRetentionModal.prunePreview.length > 10" class="text-xs text-muted" style="padding: 0.25rem 0;">
                  ...and {{ pbsRetentionModal.prunePreview.length - 10 }} more groups
                </div>
              </div>
            </div>
            <div class="flex gap-1">
              <button
                @click="previewPbsPrune"
                class="btn btn-outline"
                :disabled="pbsRetentionModal.loadingPreview"
              >
                {{ pbsRetentionModal.loadingPreview ? 'Loading preview...' : 'Preview Prune' }}
              </button>
              <button
                v-if="pbsRetentionModal.prunePreview !== null"
                @click="applyPbsPrune"
                class="btn btn-danger"
                :disabled="pbsRetentionModal.pruning"
              >
                {{ pbsRetentionModal.pruning ? 'Pruning...' : 'Apply Prune Now' }}
              </button>
            </div>
          </div>

          <div v-if="pbsRetentionModal.result" :class="['notif-result', pbsRetentionModal.result.ok ? 'notif-result--ok' : 'notif-result--err']">
            {{ pbsRetentionModal.result.message }}
          </div>

          <div class="flex gap-1 mt-2">
            <button @click="savePbsRetentionPolicy" class="btn btn-primary" :disabled="pbsRetentionModal.saving">
              {{ pbsRetentionModal.saving ? 'Saving...' : 'Save Policy' }}
            </button>
            <button @click="closePbsRetentionModal" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Restore Wizard -->
  <RestoreWizard
    :visible="showRestoreWizard"
    :pre-host-id="hostId"
    @close="showRestoreWizard = false"
    @restored="showRestoreWizard = false"
  />
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import RestoreWizard from '@/components/RestoreWizard.vue'

const route = useRoute()
const toast = useToast()

const hostId = ref(route.params.hostId)

const activeTab = ref('schedules')
const showRestoreWizard = ref(false)

// Schedules
const schedules = ref([])
const loadingSchedules = ref(false)
const savingSchedule = ref(false)

const scheduleModal = ref({ show: false, editing: false, editId: null })
const schedWizardStep = ref(1)

const cronPresets = [
  { label: 'Nightly 2am', value: '0 2 * * *' },
  { label: 'Every 6h', value: '0 */6 * * *' },
  { label: 'Weekly Sunday', value: '0 2 * * 0' },
  { label: 'Weekly Monday', value: '0 2 * * 1' },
]

const emptyScheduleForm = () => ({
  node: '',
  storage: '',
  storageNode: '',
  schedule: '0 2 * * *',
  cronCustom: false,
  comment: '',
  vmid: 'all',
  compress: 'zstd',
  mode: 'snapshot',
  mailnotification: 'never',
  mailto: '',
  bwlimit: null,
  'keep-last': null,
  'keep-daily': null,
  'keep-weekly': null,
  'keep-monthly': null,
  // wizard scope
  scopeType: 'all',
  selectedNodes: [],
  vmidList: [],
})
const scheduleForm = ref(emptyScheduleForm())

// For VMID tag input
const vmidTagInput = ref('')

function addVmidTag() {
  const val = vmidTagInput.value.trim().replace(/,/g, '')
  if (val && /^\d+$/.test(val)) {
    if (!scheduleForm.value.vmidList.includes(val)) {
      scheduleForm.value.vmidList.push(val)
    }
  }
  vmidTagInput.value = ''
}

function removeVmidTag(idx) {
  scheduleForm.value.vmidList.splice(idx, 1)
}

function onVmidBackspace() {
  if (!vmidTagInput.value && scheduleForm.value.vmidList.length > 0) {
    scheduleForm.value.vmidList.pop()
  }
}

// Storage list for schedule wizard step 2
const schedStorages = ref([])
const loadingSchedStorages = ref(false)

async function fetchSchedStorages() {
  const node = scheduleForm.value.storageNode
  if (!node) { schedStorages.value = []; return }
  loadingSchedStorages.value = true
  try {
    const res = await api.pveNode.listStorage(hostId.value, node)
    schedStorages.value = res.data || []
  } catch (e) {
    schedStorages.value = []
  } finally {
    loadingSchedStorages.value = false
  }
}

const schedWizardStepTitle = computed(() => {
  if (scheduleModal.value.editing) return 'Edit schedule settings'
  const titles = ['Select backup scope', 'Configure storage and timing', 'Set backup options', 'Review and create']
  return titles[(schedWizardStep.value - 1)] || ''
})

const schedWizardCanNext = computed(() => {
  if (schedWizardStep.value === 1) {
    if (scheduleForm.value.scopeType === 'nodes') return scheduleForm.value.selectedNodes.length > 0
    if (scheduleForm.value.scopeType === 'vmids') return scheduleForm.value.vmidList.length > 0
    return true
  }
  if (schedWizardStep.value === 2) {
    return !!(scheduleForm.value.storage && scheduleForm.value.schedule)
  }
  return true
})

function schedWizardNext() {
  if (schedWizardCanNext.value) schedWizardStep.value++
}

// Quick Backup modal state
const quickBackupModal = ref({ show: false, running: false, error: null, upid: null, taskStatus: null, taskLog: [] })
const quickBackupForm = ref({ node: '', storage: '', vmid: '', compress: 'zstd', mode: 'snapshot' })
const quickBackupStorages = ref([])
const quickBackupVMs = ref([])
const loadingQuickBackupData = ref(false)
let quickBackupPollTimer = null

function openQuickBackupModal() {
  quickBackupForm.value = { node: '', storage: '', vmid: '', compress: 'zstd', mode: 'snapshot' }
  quickBackupModal.value = { show: true, running: false, error: null, upid: null, taskStatus: null, taskLog: [] }
  quickBackupStorages.value = []
  quickBackupVMs.value = []
}

function closeQuickBackupModal() {
  stopQuickBackupPoll()
  quickBackupModal.value = { show: false, running: false, error: null, upid: null, taskStatus: null, taskLog: [] }
}

async function fetchQuickBackupNodeData() {
  const node = quickBackupForm.value.node
  quickBackupForm.value.storage = ''
  quickBackupForm.value.vmid = ''
  quickBackupStorages.value = []
  quickBackupVMs.value = []
  if (!node) return
  loadingQuickBackupData.value = true
  try {
    const [storRes, vmRes] = await Promise.all([
      api.pveNode.listStorage(hostId.value, node),
      api.pveNode.nodeVms(hostId.value, node),
    ])
    quickBackupStorages.value = storRes.data || []
    const vms = (vmRes.data?.vms || []).map(v => ({ ...v, type: 'qemu' }))
    const cts = (vmRes.data?.containers || []).map(c => ({ ...c, type: 'lxc' }))
    quickBackupVMs.value = [...vms, ...cts].sort((a, b) => a.vmid - b.vmid)
  } catch (e) {
    console.error('Failed to load quick backup node data:', e)
  } finally {
    loadingQuickBackupData.value = false
  }
}

async function submitQuickBackup() {
  if (!quickBackupForm.value.node) { toast.error('Please select a node'); return }
  if (!quickBackupForm.value.storage) { toast.error('Please select a storage'); return }
  quickBackupModal.value.running = true
  quickBackupModal.value.error = null
  try {
    const payload = {
      storage: quickBackupForm.value.storage,
      compress: quickBackupForm.value.compress,
      mode: quickBackupForm.value.mode,
    }
    if (quickBackupForm.value.vmid) payload.vmid = quickBackupForm.value.vmid
    const res = await api.pveNode.runBackup(hostId.value, quickBackupForm.value.node, payload)
    const upid = res.data?.upid || res.data
    toast.success('Backup started')
    quickBackupModal.value.upid = upid
    quickBackupModal.value.taskStatus = 'running'
    startQuickBackupPoll(quickBackupForm.value.node, upid)
  } catch (err) {
    console.error('Quick backup failed:', err)
    quickBackupModal.value.error = err.response?.data?.detail || 'Failed to start backup'
  } finally {
    quickBackupModal.value.running = false
  }
}

function startQuickBackupPoll(node, upid) {
  stopQuickBackupPoll()
  pollQuickBackupStatus(node, upid)
  quickBackupPollTimer = setInterval(() => pollQuickBackupStatus(node, upid), 3000)
}

function stopQuickBackupPoll() {
  if (quickBackupPollTimer) { clearInterval(quickBackupPollTimer); quickBackupPollTimer = null }
}

async function pollQuickBackupStatus(node, upid) {
  try {
    const [statusRes, logRes] = await Promise.all([
      api.pveNode.taskStatus(hostId.value, node, encodeURIComponent(upid)),
      api.pveNode.taskLog(hostId.value, node, upid).catch(() => ({ data: { lines: [] } })),
    ])
    const data = statusRes.data || {}
    quickBackupModal.value.taskStatus = data.status || 'running'
    quickBackupModal.value.taskLog = logRes.data?.lines || []
    if (data.status === 'stopped') {
      stopQuickBackupPoll()
      if (data.exitstatus === 'OK') {
        toast.success('Backup completed successfully')
      } else {
        toast.error(`Backup finished with status: ${data.exitstatus}`)
      }
    }
  } catch (e) {
    console.warn('Quick backup poll error:', e)
  }
}

// Run backup
const clusterNodes = ref([])
const running = ref(false)
const runResult = ref(null)
const runForm = ref({
  node: '',
  storage: '',
  vmid: 'all',
  compress: 'zstd',
  mode: 'snapshot',
})

// Restore tab state
const restoreFilter = ref({ node: '', storage: '' })
const restoreStorages = ref([])
const loadingRestoreStorages = ref(false)
const backupFiles = ref([])
const loadingBackupFiles = ref(false)

// Restore modal state
const restoreModal = ref({ show: false, volid: '' })
const restoreForm = ref({ vmid: null, node: '', storage: '', start: false })
const restoringBackup = ref(false)
const restoreTargetStorages = ref([])
const loadingRestoreTargetStorages = ref(false)

// Restore task polling
const restoreTask = ref({ upid: null, status: null, exitstatus: null })
let restoreTaskPollTimer = null

// ── PBS Servers CRUD state ────────────────────────────────────────────────────

const pbsServerList = ref([])
const loadingPbsServersCrud = ref(false)
const pbsServerStatus = ref({})  // id -> true | false | 'testing' | undefined

const addPbsServerModal = ref({ show: false, saving: false, error: null })
const emptyAddPbsServerForm = () => ({
  name: '',
  hostname: '',
  port: 8007,
  username: 'root@pam',
  api_token_id: '',
  api_token_secret: '',
  verify_ssl: false,
})
const addPbsServerForm = ref(emptyAddPbsServerForm())

async function fetchPbsServerListCrud() {
  loadingPbsServersCrud.value = true
  try {
    const res = await api.pbs.list()
    pbsServerList.value = res.data || []
    pbsServers.value = pbsServerList.value
  } catch (err) {
    console.error('Failed to load PBS servers:', err)
    toast.error('Failed to load PBS servers')
  } finally {
    loadingPbsServersCrud.value = false
  }
}

function onPbsServersTabOpen() {
  if (pbsServerList.value.length === 0) {
    fetchPbsServerListCrud()
  }
}

function openAddPbsServerModal() {
  addPbsServerForm.value = emptyAddPbsServerForm()
  addPbsServerModal.value = { show: true, saving: false, error: null }
}

function closeAddPbsServerModal() {
  addPbsServerModal.value = { show: false, saving: false, error: null }
}

async function submitAddPbsServer() {
  addPbsServerModal.value.saving = true
  addPbsServerModal.value.error = null
  try {
    await api.pbs.create({ ...addPbsServerForm.value })
    toast.success('PBS server added')
    closeAddPbsServerModal()
    await fetchPbsServerListCrud()
    // Also refresh the pbsServers list used in PBS Browser
    pbsServers.value = pbsServerList.value
  } catch (err) {
    console.error('Failed to add PBS server:', err)
    addPbsServerModal.value.error = err.response?.data?.detail || 'Failed to add server'
  } finally {
    addPbsServerModal.value.saving = false
  }
}

// ── PBS Server per-row snapshot sub-panel ────────────────────────────────────

const expandedPbsServer = ref(null)
// server id -> array of datastores
const pbsServerDatastores = ref({})
const pbsServerSnapshotState = ref({
  serverId: null,
  selectedDatastore: '',
  loadingDatastores: false,
  loading: false,
  snapshots: [],
})

async function togglePbsServerSnapshots(srv) {
  if (expandedPbsServer.value === srv.id) {
    expandedPbsServer.value = null
    return
  }
  expandedPbsServer.value = srv.id
  pbsServerSnapshotState.value = {
    serverId: srv.id,
    selectedDatastore: '',
    loadingDatastores: true,
    loading: false,
    snapshots: [],
  }
  // Load datastores for this server if not already cached
  if (!pbsServerDatastores.value[srv.id]) {
    try {
      const res = await api.pbsMgmt.listDatastores(srv.id)
      pbsServerDatastores.value = { ...pbsServerDatastores.value, [srv.id]: res.data || [] }
    } catch (err) {
      console.error('Failed to load PBS datastores for server', srv.id, err)
      pbsServerDatastores.value = { ...pbsServerDatastores.value, [srv.id]: [] }
    }
  }
  pbsServerSnapshotState.value.loadingDatastores = false
  // Auto-select the first datastore and load snapshots
  const dsList = pbsServerDatastores.value[srv.id] || []
  if (dsList.length === 1) {
    pbsServerSnapshotState.value.selectedDatastore = dsList[0].store || dsList[0].name
    await fetchPbsServerSnapshots(srv)
  }
}

async function fetchPbsServerSnapshots(srv) {
  const ds = pbsServerSnapshotState.value.selectedDatastore
  if (!ds) return
  pbsServerSnapshotState.value.loading = true
  pbsServerSnapshotState.value.snapshots = []
  try {
    const res = await api.pbsMgmt.listSnapshots(srv.id, ds)
    pbsServerSnapshotState.value.snapshots = (res.data || []).sort(
      (a, b) => (b['backup-time'] || 0) - (a['backup-time'] || 0)
    )
  } catch (err) {
    console.error('Failed to load snapshots for server', srv.id, 'datastore', ds, err)
    toast.error('Failed to load snapshots')
    pbsServerSnapshotState.value.snapshots = []
  } finally {
    pbsServerSnapshotState.value.loading = false
  }
}

// ── Run Now modal (per schedule) ─────────────────────────────────────────────

const runNowModal = ref({ show: false, scheduleId: null, node: '', running: false, result: null })

function openRunNowModal(sched) {
  runNowModal.value = { show: true, scheduleId: sched.id, node: sched.node || '', running: false, result: null }
}

function closeRunNowModal() {
  runNowModal.value = { show: false, scheduleId: null, node: '', running: false, result: null }
}

async function submitRunNow() {
  if (!runNowModal.value.scheduleId) return
  if (!runNowModal.value.node) { toast.error('Please select a target node'); return }
  runNowModal.value.running = true
  runNowModal.value.result = null
  try {
    const payload = { node: runNowModal.value.node }
    const res = await api.pveNode.runBackupScheduleNow(hostId.value, runNowModal.value.scheduleId, payload)
    const upid = res.data?.upid || res.data || null
    runNowModal.value.result = {
      ok: true,
      message: 'Backup job started successfully.',
      upid,
    }
    toast.success('Backup job started')
  } catch (err) {
    console.error('Failed to run schedule now:', err)
    runNowModal.value.result = {
      ok: false,
      message: err.response?.data?.detail || 'Failed to start backup job.',
      upid: null,
    }
    toast.error('Failed to start backup job')
  } finally {
    runNowModal.value.running = false
  }
}

// ── Schedule enabled toggle ───────────────────────────────────────────────────

async function toggleScheduleEnabled(sched) {
  const newEnabled = sched.enabled === 0 ? 1 : 0
  try {
    await api.pveNode.updateBackupSchedule(hostId.value, sched.id, { enabled: newEnabled })
    // Optimistically update local state
    sched.enabled = newEnabled
    toast.success(`Schedule ${newEnabled ? 'enabled' : 'disabled'}`)
  } catch (err) {
    console.error('Failed to toggle schedule enabled:', err)
    toast.error('Failed to update schedule')
  }
}

async function testPbsServer(srv) {
  pbsServerStatus.value = { ...pbsServerStatus.value, [srv.id]: 'testing' }
  try {
    const res = await api.pbsMgmt.test(srv.id)
    pbsServerStatus.value = {
      ...pbsServerStatus.value,
      [srv.id]: (res.data?.status === 'success'),
    }
  } catch (err) {
    pbsServerStatus.value = { ...pbsServerStatus.value, [srv.id]: false }
  }
}

async function deletePbsServer(srv) {
  if (!confirm(`Delete PBS server "${srv.name}"? This cannot be undone.`)) return
  try {
    await api.pbs.delete(srv.id)
    toast.success('PBS server deleted')
    await fetchPbsServerListCrud()
    pbsServers.value = pbsServerList.value
  } catch (err) {
    console.error('Failed to delete PBS server:', err)
    toast.error('Failed to delete PBS server')
  }
}

// ── PBS Tasks state ───────────────────────────────────────────────────────────

const pbsTasks = ref({ serverId: '', items: [] })
const loadingPbsTasks = ref(false)

const taskLogModal = ref({ show: false, upid: '', loading: false, lines: [] })

async function fetchPbsTasks() {
  if (!pbsTasks.value.serverId) return
  loadingPbsTasks.value = true
  pbsTasks.value.items = []
  try {
    const res = await api.pbsMgmt.listTasks(pbsTasks.value.serverId)
    pbsTasks.value.items = res.data || []
  } catch (err) {
    console.error('Failed to load PBS tasks:', err)
    toast.error('Failed to load tasks')
  } finally {
    loadingPbsTasks.value = false
  }
}

function onPbsTasksTabOpen() {
  if (pbsServerList.value.length === 0) {
    fetchPbsServerListCrud()
  }
}

function taskStatusClass(task) {
  const s = task.status || (task.endtime ? 'stopped' : 'running')
  if (s === 'stopped' || s === 'OK') return 'task-status-badge--stopped'
  if (s === 'running') return 'task-status-badge--running'
  return 'task-status-badge--unknown'
}

function formatDuration(start, end) {
  if (!start) return '—'
  const s = (end || Math.floor(Date.now() / 1000)) - start
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}

async function openTaskLogModal(task) {
  taskLogModal.value = { show: true, upid: task.upid, loading: true, lines: [] }
  try {
    const res = await api.pbsMgmt.getTaskLog(pbsTasks.value.serverId, task.upid)
    taskLogModal.value.lines = res.data || []
  } catch (err) {
    console.error('Failed to load task log:', err)
    taskLogModal.value.lines = ['Error loading log.']
  } finally {
    taskLogModal.value.loading = false
  }
}

function closeTaskLogModal() {
  taskLogModal.value = { show: false, upid: '', loading: false, lines: [] }
}

// ── PBS Prune state ───────────────────────────────────────────────────────────

const pruneModal = ref({ show: false, group: null, saving: false, result: null })
const pruneForm = ref({
  'keep-last': null,
  'keep-hourly': null,
  'keep-daily': null,
  'keep-weekly': null,
  'keep-monthly': null,
  'keep-yearly': null,
})

function openPruneModal(group) {
  pruneForm.value = {
    'keep-last': null,
    'keep-hourly': null,
    'keep-daily': null,
    'keep-weekly': null,
    'keep-monthly': null,
    'keep-yearly': null,
  }
  pruneModal.value = { show: true, group, saving: false, result: null }
}

function closePruneModal() {
  pruneModal.value = { show: false, group: null, saving: false, result: null }
}

async function submitPrune() {
  if (!pruneModal.value.group) return
  const group = pruneModal.value.group
  pruneModal.value.saving = true
  pruneModal.value.result = null

  const payload = {
    'backup-type': group['backup-type'],
    'backup-id': group['backup-id'],
  }
  // Only include non-null / non-empty keep options
  for (const [k, v] of Object.entries(pruneForm.value)) {
    if (v !== null && v !== '' && v >= 0) {
      payload[k] = v
    }
  }

  try {
    await api.pbsMgmt.pruneGroup(
      pbsBrowser.value.selectedServerId,
      pbsBrowser.value.selectedDatastore,
      payload
    )
    pruneModal.value.result = { ok: true, message: 'Prune job started successfully.' }
    toast.success('Prune job started')
    // Reload group snapshots
    const groupKey = pbsGroupKey(group)
    delete pbsSnapshots.value[groupKey]
    if (expandedPbsGroups.value[groupKey]) {
      expandedPbsGroups.value = { ...expandedPbsGroups.value, [groupKey]: false }
      await togglePbsGroup(group)
    }
    await fetchPbsGroups()
  } catch (err) {
    console.error('Failed to prune group:', err)
    pruneModal.value.result = { ok: false, message: 'Prune failed. Check console for details.' }
    toast.error('Failed to prune group')
  } finally {
    pruneModal.value.saving = false
  }
}

// ── PBS Forget snapshot ───────────────────────────────────────────────────────

// snapshot key -> bool (forgetting)
const forgettingSnapshot = ref({})

async function forgetPbsSnapshot(snap, group) {
  const key = pbsSnapshotKey(snap, group)
  const confirmMsg = `Permanently delete snapshot from ${formatDate(snap['backup-time'])} for ${group['backup-type']}/${group['backup-id']}? This cannot be undone.`
  if (!confirm(confirmMsg)) return

  forgettingSnapshot.value = { ...forgettingSnapshot.value, [key]: true }
  try {
    await api.pbsMgmt.forgetSnapshot(
      pbsBrowser.value.selectedServerId,
      pbsBrowser.value.selectedDatastore,
      {
        'backup-type': group['backup-type'],
        'backup-id': group['backup-id'],
        'backup-time': snap['backup-time'],
      }
    )
    toast.success('Snapshot deleted')
    // Reload snapshots for this group
    const groupKey = pbsGroupKey(group)
    delete pbsSnapshots.value[groupKey]
    if (expandedPbsGroups.value[groupKey]) {
      await togglePbsGroup(group)
    }
    // Refresh group list to update backup-count
    await fetchPbsGroups()
  } catch (err) {
    console.error('Failed to forget snapshot:', err)
    toast.error('Failed to delete snapshot')
  } finally {
    forgettingSnapshot.value = { ...forgettingSnapshot.value, [key]: false }
  }
}

// ── PBS Browser state ─────────────────────────────────────────────────────────

const pbsServers = ref([])
const loadingPbsServers = ref(false)

const pbsBrowser = ref({
  selectedServerId: '',
  selectedDatastore: '',
})

const pbsBrowserDatastores = ref([])
const loadingPbsDatastores = ref(false)

const pbsBrowserGroups = ref([])
const loadingPbsGroups = ref(false)

// expanded group keys -> true
const expandedPbsGroups = ref({})
// group key -> snapshot array
const pbsSnapshots = ref({})
// group key -> bool (loading)
const loadingPbsSnapshots = ref({})
// snapshot key -> bool (verifying)
const verifyingSnapshot = ref({})

function pbsGroupKey(group) {
  return `${group['backup-type']}/${group['backup-id']}`
}

function pbsSnapshotKey(snap, group) {
  return `${pbsGroupKey(group)}@${snap['backup-time']}`
}

// ── Notifications state ───────────────────────────────────────────────────────

const notifForm = ref({
  mailnotification: 'never',
  mailto: '',
  scheduleId: '',
})
const savingNotif = ref(false)
const notifSaveResult = ref(null)

// Computed: group backup files by VMID
const backupGroups = computed(() => {
  const groups = {}
  for (const bk of backupFiles.value) {
    const vmid = parseVmidFromVolid(bk.volid) || bk.vmid || 'unknown'
    if (!groups[vmid]) groups[vmid] = { vmid, backups: [] }
    groups[vmid].backups.push(bk)
  }
  return Object.values(groups)
    .sort((a, b) => String(a.vmid).localeCompare(String(b.vmid), undefined, { numeric: true }))
    .map(g => ({
      ...g,
      backups: [...g.backups].sort((a, b) => (b.ctime || 0) - (a.ctime || 0))
    }))
})

function parseVmidFromVolid(volid) {
  if (!volid) return null
  const m = volid.match(/vzdump-(?:qemu|lxc)-(\d+)-/)
  return m ? m[1] : null
}

// Backup filter state
const backupSearch = ref('')
const backupDateFrom = ref('')
const backupDateTo = ref('')
const backupSortBy = ref('date_desc')

const filteredBackupGroups = computed(() => {
  const q = backupSearch.value.trim().toLowerCase()
  const fromTs = backupDateFrom.value ? new Date(backupDateFrom.value).getTime() / 1000 : null
  const toTs = backupDateTo.value ? (new Date(backupDateTo.value).getTime() / 1000) + 86399 : null

  return backupGroups.value
    .map(group => {
      // Filter by VMID search
      if (q && !String(group.vmid).includes(q)) {
        // Also check individual backup voids
        const matchedBackups = group.backups.filter(bk =>
          (bk.volid || '').toLowerCase().includes(q)
        )
        if (matchedBackups.length === 0) return null
        return { ...group, backups: sortBackups(filterBackupsByDate(matchedBackups, fromTs, toTs)) }
      }
      const filtered = filterBackupsByDate(group.backups, fromTs, toTs)
      if (filtered.length === 0) return null
      return { ...group, backups: sortBackups(filtered) }
    })
    .filter(Boolean)
})

function filterBackupsByDate(backups, fromTs, toTs) {
  return backups.filter(bk => {
    if (fromTs && (bk.ctime || 0) < fromTs) return false
    if (toTs && (bk.ctime || 0) > toTs) return false
    return true
  })
}

function sortBackups(backups) {
  return [...backups].sort((a, b) => {
    if (backupSortBy.value === 'date_desc') return (b.ctime || 0) - (a.ctime || 0)
    if (backupSortBy.value === 'date_asc') return (a.ctime || 0) - (b.ctime || 0)
    if (backupSortBy.value === 'size_desc') return (b.size || 0) - (a.size || 0)
    if (backupSortBy.value === 'size_asc') return (a.size || 0) - (b.size || 0)
    return 0
  })
}

function formatDate(ctime) {
  if (!ctime) return '—'
  return new Date(ctime * 1000).toLocaleString()
}

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = bytes
  let u = 0
  while (v >= 1024 && u < units.length - 1) { v /= 1024; u++ }
  return `${v.toFixed(1)} ${units[u]}`
}

// ── Schedules ────────────────────────────────────────────────────────────────

async function fetchSchedules() {
  loadingSchedules.value = true
  try {
    const res = await api.pveNode.listBackupSchedules(hostId.value)
    schedules.value = res.data || []
  } catch (err) {
    console.error('Failed to load backup schedules:', err)
    toast.error('Failed to load backup schedules')
  } finally {
    loadingSchedules.value = false
  }
}

async function fetchClusterNodes() {
  try {
    const res = await api.pveNode.clusterResources(hostId.value)
    const resources = res.data || []
    clusterNodes.value = resources.filter(r => r.type === 'node')
  } catch (err) {
    console.warn('Failed to load cluster nodes:', err)
  }
}

function openCreateModal() {
  scheduleForm.value = emptyScheduleForm()
  schedWizardStep.value = 1
  schedStorages.value = []
  scheduleModal.value = { show: true, editing: false, editId: null }
}

function openEditModal(sched) {
  scheduleForm.value = {
    ...emptyScheduleForm(),
    node: sched.node || '',
    storage: sched.storage || '',
    storageNode: sched.node || '',
    schedule: sched.schedule || sched.dow || '',
    comment: sched.comment || '',
    vmid: sched.vmid || 'all',
    compress: sched.compress || 'zstd',
    mode: sched.mode || 'snapshot',
    mailnotification: sched.mailnotification || 'never',
    mailto: sched.mailto || '',
    bwlimit: sched.bwlimit || null,
    'keep-last': sched['keep-last'] || null,
    'keep-daily': sched['keep-daily'] || null,
    'keep-weekly': sched['keep-weekly'] || null,
    'keep-monthly': sched['keep-monthly'] || null,
  }
  scheduleModal.value = { show: true, editing: true, editId: sched.id }
}

function closeScheduleModal() {
  scheduleModal.value = { show: false, editing: false, editId: null }
}

async function saveSchedule() {
  savingSchedule.value = true

  // Build payload — strip internal wizard-only fields and empty values
  const wizardOnlyFields = ['scopeType', 'selectedNodes', 'vmidList', 'storageNode', 'cronCustom']
  const buildPayload = () => {
    const p = {}
    for (const [k, v] of Object.entries(scheduleForm.value)) {
      if (wizardOnlyFields.includes(k)) continue
      if (v === '' || v === null || v === undefined) continue
      p[k] = v
    }
    return p
  }

  // Determine vmid value from scope
  if (!scheduleModal.value.editing) {
    if (scheduleForm.value.scopeType === 'all') {
      delete scheduleForm.value.vmid
    } else if (scheduleForm.value.scopeType === 'vmids') {
      scheduleForm.value.vmid = scheduleForm.value.vmidList.join(',')
    }
    // For 'nodes' scope: we'll loop below
  }

  try {
    if (scheduleModal.value.editing) {
      const payload = buildPayload()
      await api.pveNode.updateBackupSchedule(hostId.value, scheduleModal.value.editId, payload)
      toast.success('Schedule updated')
      closeScheduleModal()
      await fetchSchedules()
    } else if (scheduleForm.value.scopeType === 'nodes' && scheduleForm.value.selectedNodes.length > 1) {
      // Create one schedule per selected node
      let created = 0
      for (const node of scheduleForm.value.selectedNodes) {
        scheduleForm.value.node = node
        const payload = buildPayload()
        await api.pveNode.createBackupSchedule(hostId.value, payload)
        created++
      }
      toast.success(`${created} schedules created`)
      closeScheduleModal()
      await fetchSchedules()
    } else {
      if (scheduleForm.value.scopeType === 'nodes' && scheduleForm.value.selectedNodes.length === 1) {
        scheduleForm.value.node = scheduleForm.value.selectedNodes[0]
      }
      const payload = buildPayload()
      await api.pveNode.createBackupSchedule(hostId.value, payload)
      toast.success('Schedule created')
      closeScheduleModal()
      await fetchSchedules()
    }
  } catch (err) {
    console.error('Failed to save schedule:', err)
    toast.error('Failed to save schedule')
  } finally {
    savingSchedule.value = false
  }
}

async function deleteSchedule(id) {
  if (!confirm(`Delete backup schedule "${id}"? This cannot be undone.`)) return
  try {
    await api.pveNode.deleteBackupSchedule(hostId.value, id)
    toast.success('Schedule deleted')
    await fetchSchedules()
  } catch (err) {
    console.error('Failed to delete schedule:', err)
    toast.error('Failed to delete schedule')
  }
}

// ── Run Backup ───────────────────────────────────────────────────────────────

async function runBackup() {
  if (!runForm.value.node) {
    toast.error('Please select a node')
    return
  }
  running.value = true
  runResult.value = null
  try {
    const payload = { ...runForm.value }
    Object.keys(payload).forEach(k => { if (payload[k] === '' || payload[k] === null) delete payload[k] })
    const res = await api.pveNode.runBackup(hostId.value, runForm.value.node, payload)
    runResult.value = res.data?.upid || res.data || 'started'
    toast.success('Backup started')
  } catch (err) {
    console.error('Failed to start backup:', err)
    toast.error('Failed to start backup')
  } finally {
    running.value = false
  }
}

// ── Restore tab ──────────────────────────────────────────────────────────────

function onRestoreTabOpen() {
  if (restoreFilter.value.node && restoreStorages.value.length === 0) {
    fetchRestoreStorages(restoreFilter.value.node)
  }
}

async function onRestoreNodeChange() {
  restoreFilter.value.storage = ''
  restoreStorages.value = []
  backupFiles.value = []
  if (restoreFilter.value.node) {
    await fetchRestoreStorages(restoreFilter.value.node)
  }
}

async function fetchRestoreStorages(node) {
  loadingRestoreStorages.value = true
  try {
    const res = await api.pveNode.listStorage(hostId.value, node)
    restoreStorages.value = res.data || []
  } catch (err) {
    console.warn('Failed to load storages:', err)
  } finally {
    loadingRestoreStorages.value = false
  }
}

async function fetchBackupFiles() {
  if (!restoreFilter.value.node || !restoreFilter.value.storage) return
  loadingBackupFiles.value = true
  backupFiles.value = []
  try {
    const res = await api.pveNode.browseStorage(
      hostId.value,
      restoreFilter.value.node,
      restoreFilter.value.storage,
      { content: 'backup' }
    )
    backupFiles.value = res.data || []
  } catch (err) {
    console.error('Failed to browse backup storage:', err)
    toast.error('Failed to load backup files')
  } finally {
    loadingBackupFiles.value = false
  }
}

// ── Restore modal ─────────────────────────────────────────────────────────────

function openRestoreModal(backup, vmid) {
  restoreTask.value = { upid: null, status: null, exitstatus: null }
  restoreForm.value = {
    vmid: Number(vmid) || null,
    node: restoreFilter.value.node,
    storage: '',
    start: false,
  }
  restoreModal.value = { show: true, volid: backup.volid }
  if (restoreForm.value.node) {
    fetchRestoreTargetStorages(restoreForm.value.node)
  }
}

function openRestoreModalFromPbs(snap, group) {
  // Build a display volid reference for PBS snapshots
  const label = `pbs:${pbsBrowser.value.selectedDatastore}/${group['backup-type']}/${group['backup-id']}/${snap['backup-time']}`
  restoreTask.value = { upid: null, status: null, exitstatus: null }
  restoreForm.value = {
    vmid: Number(group['backup-id']) || null,
    node: clusterNodes.value.length > 0 ? (clusterNodes.value[0].node || clusterNodes.value[0].name) : '',
    storage: '',
    start: false,
  }
  restoreModal.value = { show: true, volid: label }
  if (restoreForm.value.node) {
    fetchRestoreTargetStorages(restoreForm.value.node)
  }
}

function closeRestoreModal() {
  stopTaskPolling()
  restoreModal.value = { show: false, volid: '' }
  restoreTask.value = { upid: null, status: null, exitstatus: null }
}

async function onRestoreFormNodeChange() {
  restoreForm.value.storage = ''
  restoreTargetStorages.value = []
  if (restoreForm.value.node) {
    await fetchRestoreTargetStorages(restoreForm.value.node)
  }
}

async function fetchRestoreTargetStorages(node) {
  loadingRestoreTargetStorages.value = true
  try {
    const res = await api.pveNode.listStorage(hostId.value, node)
    restoreTargetStorages.value = res.data || []
  } catch (err) {
    console.warn('Failed to load target storages:', err)
  } finally {
    loadingRestoreTargetStorages.value = false
  }
}

async function submitRestore() {
  if (!restoreForm.value.node) { toast.error('Please select a target node'); return }
  if (!restoreForm.value.storage) { toast.error('Please select a target storage'); return }
  if (!restoreForm.value.vmid) { toast.error('Please enter a target VM ID'); return }

  restoringBackup.value = true
  try {
    const payload = {
      archive: restoreModal.value.volid,
      storage: restoreForm.value.storage,
      start: restoreForm.value.start ? 1 : 0,
    }
    const res = await api.pveNode.restoreBackup(
      hostId.value,
      restoreForm.value.node,
      restoreForm.value.vmid,
      payload
    )
    const upid = res.data?.upid || res.data
    toast.success('Restore task started')
    restoreTask.value = { upid, status: 'running', exitstatus: null }
    startTaskPolling(restoreForm.value.node, upid)
  } catch (err) {
    console.error('Failed to start restore:', err)
    toast.error('Failed to start restore')
  } finally {
    restoringBackup.value = false
  }
}

// ── Task polling ─────────────────────────────────────────────────────────────

function startTaskPolling(node, upid) {
  stopTaskPolling()
  restoreTaskPollTimer = setInterval(() => pollTaskStatus(node, upid), 3000)
  pollTaskStatus(node, upid)
}

function stopTaskPolling() {
  if (restoreTaskPollTimer) {
    clearInterval(restoreTaskPollTimer)
    restoreTaskPollTimer = null
  }
}

async function pollTaskStatus(node, upid) {
  try {
    const res = await api.pveNode.taskStatus(hostId.value, node, encodeURIComponent(upid))
    const data = res.data || {}
    restoreTask.value.status = data.status || 'unknown'
    restoreTask.value.exitstatus = data.exitstatus || null
    if (data.status === 'stopped') {
      stopTaskPolling()
      if (data.exitstatus === 'OK') {
        toast.success('Restore completed successfully')
      } else {
        toast.error(`Restore finished with status: ${data.exitstatus}`)
      }
    }
  } catch (err) {
    console.warn('Failed to poll task status:', err)
  }
}

// ── PBS Browser ───────────────────────────────────────────────────────────────

function onPbsTabOpen() {
  if (pbsServers.value.length === 0) {
    fetchPbsServerList()
  }
}

async function fetchPbsServerList() {
  loadingPbsServers.value = true
  try {
    const res = await api.pbs.list()
    pbsServers.value = res.data || []
    // Keep the CRUD list in sync too
    pbsServerList.value = pbsServers.value
  } catch (err) {
    console.error('Failed to load PBS servers:', err)
  } finally {
    loadingPbsServers.value = false
  }
}

async function onPbsServerChange() {
  pbsBrowser.value.selectedDatastore = ''
  pbsBrowserDatastores.value = []
  pbsBrowserGroups.value = []
  expandedPbsGroups.value = {}
  pbsSnapshots.value = {}

  if (!pbsBrowser.value.selectedServerId) return
  loadingPbsDatastores.value = true
  try {
    const res = await api.pbsMgmt.listDatastores(pbsBrowser.value.selectedServerId)
    pbsBrowserDatastores.value = res.data || []
  } catch (err) {
    console.error('Failed to load PBS datastores:', err)
    toast.error('Failed to load datastores')
  } finally {
    loadingPbsDatastores.value = false
  }
}

async function fetchPbsGroups() {
  if (!pbsBrowser.value.selectedServerId || !pbsBrowser.value.selectedDatastore) return
  loadingPbsGroups.value = true
  pbsBrowserGroups.value = []
  expandedPbsGroups.value = {}
  pbsSnapshots.value = {}
  try {
    const res = await api.pbsMgmt.listGroups(
      pbsBrowser.value.selectedServerId,
      pbsBrowser.value.selectedDatastore
    )
    pbsBrowserGroups.value = res.data || []
  } catch (err) {
    console.error('Failed to load PBS groups:', err)
    toast.error('Failed to load backup groups')
  } finally {
    loadingPbsGroups.value = false
  }
}

async function togglePbsGroup(group) {
  const key = pbsGroupKey(group)
  if (expandedPbsGroups.value[key]) {
    expandedPbsGroups.value = { ...expandedPbsGroups.value, [key]: false }
    return
  }
  expandedPbsGroups.value = { ...expandedPbsGroups.value, [key]: true }
  if (pbsSnapshots.value[key]) return  // already loaded
  loadingPbsSnapshots.value = { ...loadingPbsSnapshots.value, [key]: true }
  try {
    const res = await api.pbsMgmt.listSnapshots(
      pbsBrowser.value.selectedServerId,
      pbsBrowser.value.selectedDatastore,
      { 'backup-type': group['backup-type'], 'backup-id': group['backup-id'] }
    )
    const snaps = (res.data || []).sort((a, b) => (b['backup-time'] || 0) - (a['backup-time'] || 0))
    pbsSnapshots.value = { ...pbsSnapshots.value, [key]: snaps }
  } catch (err) {
    console.error('Failed to load PBS snapshots:', err)
    toast.error('Failed to load snapshots')
    pbsSnapshots.value = { ...pbsSnapshots.value, [key]: [] }
  } finally {
    loadingPbsSnapshots.value = { ...loadingPbsSnapshots.value, [key]: false }
  }
}

async function verifyPbsSnapshot(snap, group) {
  const key = pbsSnapshotKey(snap, group)
  verifyingSnapshot.value = { ...verifyingSnapshot.value, [key]: true }
  try {
    await api.pbsMgmt.verifySnapshot(
      pbsBrowser.value.selectedServerId,
      pbsBrowser.value.selectedDatastore,
      {
        'backup-type': group['backup-type'],
        'backup-id': group['backup-id'],
        'backup-time': snap['backup-time'],
      }
    )
    toast.success('Verify job started')
    // Reload snapshots to reflect updated verify-state
    const groupKey = pbsGroupKey(group)
    delete pbsSnapshots.value[groupKey]
    await togglePbsGroup(group)
  } catch (err) {
    console.error('Failed to verify snapshot:', err)
    toast.error('Failed to start verify')
  } finally {
    verifyingSnapshot.value = { ...verifyingSnapshot.value, [key]: false }
  }
}

// ── Notifications ─────────────────────────────────────────────────────────────

async function saveNotifications() {
  const scheduleIds = notifForm.value.scheduleId
    ? [notifForm.value.scheduleId]
    : schedules.value.map(s => s.id)

  if (scheduleIds.length === 0) {
    toast.error('No backup schedules found. Create a schedule first.')
    return
  }

  savingNotif.value = true
  notifSaveResult.value = null

  const payload = {
    mailnotification: notifForm.value.mailnotification,
  }
  if (notifForm.value.mailnotification !== 'never' && notifForm.value.mailto) {
    payload.mailto = notifForm.value.mailto
  }

  let successCount = 0
  let failCount = 0
  for (const id of scheduleIds) {
    try {
      await api.pveNode.updateBackupSchedule(hostId.value, id, payload)
      successCount++
    } catch (err) {
      console.error(`Failed to update schedule ${id}:`, err)
      failCount++
    }
  }

  savingNotif.value = false
  if (failCount === 0) {
    notifSaveResult.value = {
      ok: true,
      message: `Notification settings saved for ${successCount} schedule${successCount !== 1 ? 's' : ''}.`,
    }
    toast.success('Notification settings saved')
  } else {
    notifSaveResult.value = {
      ok: false,
      message: `Saved ${successCount}, failed ${failCount} schedule(s). Check console for details.`,
    }
    toast.error('Some schedules could not be updated')
  }
}

// ── Retention Policies ────────────────────────────────────────────────────────

const retentionModal = ref({ show: false, scheduleId: null, saving: false, result: null })
const retentionForm = ref({
  'keep-last': null,
  'keep-daily': null,
  'keep-weekly': null,
  'keep-monthly': null,
  'keep-yearly': null,
})

const retentionPreviewTotal = computed(() => {
  const f = retentionForm.value
  let total = 0
  if (f['keep-last']) total += Number(f['keep-last'])
  if (f['keep-daily']) total += Number(f['keep-daily'])
  if (f['keep-weekly']) total += Number(f['keep-weekly'])
  if (f['keep-monthly']) total += Number(f['keep-monthly'])
  if (f['keep-yearly']) total += Number(f['keep-yearly'])
  return total
})

function retentionTimeline(sched) {
  const buckets = []
  const keepLast = Number(sched['keep-last'] || 0)
  const keepDaily = Number(sched['keep-daily'] || 0)
  const keepWeekly = Number(sched['keep-weekly'] || 0)
  const keepMonthly = Number(sched['keep-monthly'] || 0)
  const keepYearly = Number(sched['keep-yearly'] || 0)

  if (keepDaily > 0) {
    for (let i = 0; i < Math.min(keepDaily, 14); i++) {
      buckets.push({ label: `Day -${i + 1}`, shortLabel: `D${i + 1}`, count: 1 })
    }
  }
  if (keepWeekly > 0) {
    for (let i = 0; i < Math.min(keepWeekly, 8); i++) {
      buckets.push({ label: `Week -${i + 1}`, shortLabel: `W${i + 1}`, count: 1 })
    }
  }
  if (keepMonthly > 0) {
    for (let i = 0; i < Math.min(keepMonthly, 12); i++) {
      buckets.push({ label: `Month -${i + 1}`, shortLabel: `M${i + 1}`, count: 1 })
    }
  }
  if (keepYearly > 0) {
    for (let i = 0; i < Math.min(keepYearly, 5); i++) {
      buckets.push({ label: `Year -${i + 1}`, shortLabel: `Y${i + 1}`, count: 1 })
    }
  }
  return buckets.slice(0, 30)
}

function retentionTotal(sched) {
  return (
    Number(sched['keep-last'] || 0) +
    Number(sched['keep-daily'] || 0) +
    Number(sched['keep-weekly'] || 0) +
    Number(sched['keep-monthly'] || 0) +
    Number(sched['keep-yearly'] || 0)
  )
}

function openRetentionEditModal(sched) {
  retentionForm.value = {
    'keep-last': sched['keep-last'] || null,
    'keep-daily': sched['keep-daily'] || null,
    'keep-weekly': sched['keep-weekly'] || null,
    'keep-monthly': sched['keep-monthly'] || null,
    'keep-yearly': sched['keep-yearly'] || null,
  }
  retentionModal.value = { show: true, scheduleId: sched.id, saving: false, result: null }
}

function closeRetentionModal() {
  retentionModal.value = { show: false, scheduleId: null, saving: false, result: null }
}

async function saveRetentionPolicy() {
  if (!retentionModal.value.scheduleId) return
  retentionModal.value.saving = true
  retentionModal.value.result = null

  const payload = {}
  const keepFields = ['keep-last', 'keep-daily', 'keep-weekly', 'keep-monthly', 'keep-yearly']
  for (const k of keepFields) {
    if (retentionForm.value[k] !== null && retentionForm.value[k] !== '') {
      payload[k] = retentionForm.value[k]
    }
  }

  try {
    await api.pveNode.updateBackupSchedule(hostId.value, retentionModal.value.scheduleId, payload)
    retentionModal.value.result = { ok: true, message: 'Retention policy saved.' }
    toast.success('Retention policy saved')
    await fetchSchedules()
  } catch (err) {
    console.error('Failed to save retention policy:', err)
    retentionModal.value.result = { ok: false, message: 'Failed to save retention policy.' }
    toast.error('Failed to save retention policy')
  } finally {
    retentionModal.value.saving = false
  }
}

// PBS per-datastore retention
const retentionPbs = ref({
  serverId: '',
  loadingDatastores: false,
  datastores: [],
  policies: {},  // dsName -> { keep-last, keep-daily, ... }
})

const pbsRetentionModal = ref({
  show: false,
  dsName: '',
  saving: false,
  result: null,
  loadingPreview: false,
  prunePreview: null,
  pruning: false,
})

const pbsRetentionForm = ref({
  'keep-last': null,
  'keep-hourly': null,
  'keep-daily': null,
  'keep-weekly': null,
  'keep-monthly': null,
  'keep-yearly': null,
})

function onRetentionTabOpen() {
  if (pbsServerList.value.length === 0) {
    fetchPbsServerListCrud()
  }
}

async function fetchRetentionPbsDatastores() {
  if (!retentionPbs.value.serverId) return
  retentionPbs.value.loadingDatastores = true
  retentionPbs.value.datastores = []
  try {
    const res = await api.pbsMgmt.listDatastores(retentionPbs.value.serverId)
    retentionPbs.value.datastores = res.data || []
  } catch (err) {
    console.error('Failed to load PBS datastores for retention:', err)
    toast.error('Failed to load datastores')
  } finally {
    retentionPbs.value.loadingDatastores = false
  }
}

function openPbsRetentionModal(ds) {
  const dsName = ds.store || ds.name
  const existing = retentionPbs.value.policies[dsName] || {}
  pbsRetentionForm.value = {
    'keep-last': existing['keep-last'] || null,
    'keep-hourly': existing['keep-hourly'] || null,
    'keep-daily': existing['keep-daily'] || null,
    'keep-weekly': existing['keep-weekly'] || null,
    'keep-monthly': existing['keep-monthly'] || null,
    'keep-yearly': existing['keep-yearly'] || null,
  }
  pbsRetentionModal.value = {
    show: true,
    dsName,
    saving: false,
    result: null,
    loadingPreview: false,
    prunePreview: null,
    pruning: false,
  }
}

function closePbsRetentionModal() {
  pbsRetentionModal.value = {
    show: false,
    dsName: '',
    saving: false,
    result: null,
    loadingPreview: false,
    prunePreview: null,
    pruning: false,
  }
}

function savePbsRetentionPolicy() {
  // Store policy locally (PBS datastore prune config is applied at prune time)
  const dsName = pbsRetentionModal.value.dsName
  const policy = {}
  for (const [k, v] of Object.entries(pbsRetentionForm.value)) {
    if (v !== null && v !== '') policy[k] = v
  }
  retentionPbs.value.policies = { ...retentionPbs.value.policies, [dsName]: policy }
  pbsRetentionModal.value.result = { ok: true, message: 'Policy saved locally. Use "Apply Prune Now" to apply to existing backups.' }
  toast.success('Policy saved')
  pbsRetentionModal.value.saving = false
}

async function previewPbsPrune() {
  const dsName = pbsRetentionModal.value.dsName
  pbsRetentionModal.value.loadingPreview = true
  pbsRetentionModal.value.prunePreview = null
  try {
    // Get all groups in this datastore and simulate what would be pruned
    const res = await api.pbsMgmt.listGroups(retentionPbs.value.serverId, dsName)
    const groups = res.data || []
    // Build a preview: for each group show how many would be kept/removed
    const keepLast = Number(pbsRetentionForm.value['keep-last'] || 0)
    const keepDaily = Number(pbsRetentionForm.value['keep-daily'] || 0)
    const keepWeekly = Number(pbsRetentionForm.value['keep-weekly'] || 0)
    const keepMonthly = Number(pbsRetentionForm.value['keep-monthly'] || 0)

    const preview = []
    for (const g of groups) {
      const total = g['backup-count'] || 0
      // Rough estimation: keep = sum of retention values, remove = max(0, total - keep)
      const maxKeep = Math.max(keepLast, keepDaily + keepWeekly + keepMonthly)
      const wouldKeep = Math.min(total, maxKeep || total)
      const wouldRemove = Math.max(0, total - wouldKeep)
      if (wouldRemove > 0) {
        preview.push({
          'backup-type': g['backup-type'],
          'backup-id': g['backup-id'],
          key: `${g['backup-type']}/${g['backup-id']}`,
          keep: wouldKeep,
          remove: wouldRemove,
        })
      }
    }
    pbsRetentionModal.value.prunePreview = preview
  } catch (err) {
    console.error('Failed to build prune preview:', err)
    toast.error('Failed to load preview')
    pbsRetentionModal.value.prunePreview = []
  } finally {
    pbsRetentionModal.value.loadingPreview = false
  }
}

async function applyPbsPrune() {
  const dsName = pbsRetentionModal.value.dsName
  const groupsToProcess = pbsRetentionModal.value.prunePreview || []

  if (groupsToProcess.length === 0) {
    toast.info('Nothing to prune.')
    return
  }

  const confirmed = confirm(`Prune ${groupsToProcess.length} group(s) in datastore "${dsName}"? This will permanently delete old backups.`)
  if (!confirmed) return

  pbsRetentionModal.value.pruning = true
  pbsRetentionModal.value.result = null

  const keepPolicy = {}
  for (const [k, v] of Object.entries(pbsRetentionForm.value)) {
    if (v !== null && v !== '' && v > 0) keepPolicy[k] = v
  }

  let successCount = 0
  let failCount = 0
  for (const g of groupsToProcess) {
    try {
      await api.pbsMgmt.pruneGroup(
        retentionPbs.value.serverId,
        dsName,
        {
          'backup-type': g['backup-type'],
          'backup-id': g['backup-id'],
          ...keepPolicy,
        }
      )
      successCount++
    } catch (err) {
      console.error(`Failed to prune group ${g['backup-type']}/${g['backup-id']}:`, err)
      failCount++
    }
  }

  pbsRetentionModal.value.pruning = false
  if (failCount === 0) {
    pbsRetentionModal.value.result = { ok: true, message: `Prune jobs started for ${successCount} group(s).` }
    toast.success(`Prune started for ${successCount} groups`)
  } else {
    pbsRetentionModal.value.result = { ok: false, message: `Pruned ${successCount}, failed ${failCount} groups.` }
    toast.error('Some prune jobs failed')
  }
  pbsRetentionModal.value.prunePreview = null
}

onMounted(async () => {
  await Promise.all([fetchSchedules(), fetchClusterNodes()])
})

onUnmounted(() => {
  stopTaskPolling()
  stopQuickBackupPoll()
})
</script>

<style scoped>
.backup-manager-page {
  padding: 0;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.tab-bar {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 1.5rem;
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.6rem 1.25rem;
  cursor: pointer;
  color: var(--text-muted, #888);
  font-size: 0.9rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn--active {
  color: var(--primary-color, #6366f1);
  border-bottom-color: var(--primary-color, #6366f1);
  font-weight: 600;
}

.card-body {
  padding: 1.5rem;
}

.cron-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.required {
  color: #ef4444;
}

.run-result {
  padding: 1rem;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid #10b981;
  border-radius: 0.375rem;
  margin-bottom: 1.5rem;
}

.upid-code {
  display: block;
  padding: 0.5rem 0.75rem;
  background: var(--bg-secondary);
  border-radius: 0.375rem;
  font-size: 0.8rem;
  word-break: break-all;
  margin-top: 0.25rem;
  color: var(--text-primary);
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.form-control-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
  height: auto;
}

/* Backup filter bar */
.backup-filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--background);
}

.backup-filter-bar input,
.backup-filter-bar select {
  background: var(--bg-secondary, rgba(255,255,255,0.05));
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  padding: 0.3rem 0.6rem;
  font-size: 0.85rem;
}

.backup-filter-bar input[type="text"] {
  flex: 1;
  min-width: 160px;
}

.backup-filter-bar label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

/* Restore tab */
.backup-group {
  border-top: 1px solid var(--border-color);
}

.backup-group:first-child {
  border-top: none;
}

.backup-group-header {
  padding: 0.6rem 1rem;
  background: var(--bg-secondary, rgba(255,255,255,0.03));
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.vmid-badge {
  background: var(--primary-color, #6366f1);
  color: #fff;
  border-radius: 0.25rem;
  padding: 0.1rem 0.45rem;
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
}

.table-sm td,
.table-sm th {
  padding: 0.4rem 0.75rem;
  font-size: 0.875rem;
}

.volid-cell {
  color: var(--text-muted);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* PBS Browser */
.pbs-browser-groups {
  border-top: 1px solid var(--border-color);
}

.pbs-group {
  border-bottom: 1px solid var(--border-color);
}

.pbs-group:last-child {
  border-bottom: none;
}

.pbs-group-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 1rem;
  cursor: pointer;
  user-select: none;
  background: var(--bg-secondary, rgba(255,255,255,0.02));
  transition: background 0.12s;
}

.pbs-group-header:hover {
  background: var(--bg-hover, rgba(99, 102, 241, 0.06));
}

.pbs-group-header--expanded {
  background: var(--bg-hover, rgba(99, 102, 241, 0.06));
}

.pbs-group-chevron {
  font-size: 0.85rem;
  color: var(--text-muted);
  width: 1rem;
  flex-shrink: 0;
}

.pbs-group-meta {
  margin-left: auto;
}

.pbs-group-meta + .pbs-group-meta {
  margin-left: 1.25rem;
}

.pbs-snapshots {
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary, rgba(255,255,255,0.01));
}

.verify-badge {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
}

.verify-badge--ok {
  background: rgba(5, 150, 105, 0.12);
  color: #059669;
  border: 1px solid #059669;
}

.verify-badge--fail {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border: 1px solid #ef4444;
}

.align-center {
  align-items: center;
}

/* Notifications */
.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.25rem;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.radio-label input[type="radio"] {
  width: 1rem;
  height: 1rem;
  cursor: pointer;
}

.notif-result {
  padding: 0.75rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
}

.notif-result--ok {
  background: rgba(5, 150, 105, 0.1);
  border: 1px solid #059669;
  color: #059669;
}

.notif-result--err {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid #ef4444;
  color: #ef4444;
}

/* Restore modal */
.modal-content--wide {
  max-width: 720px;
}

.restore-source-info {
  padding: 0.75rem 1rem;
  background: var(--bg-secondary);
  border-radius: 0.375rem;
}

.restore-progress {
  padding: 1rem;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid var(--primary-color, #6366f1);
  border-radius: 0.375rem;
}

.restore-progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.task-status-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
}

.task-status-badge--running {
  background: rgba(180, 83, 9, 0.1);
  color: #b45309;
  border: 1px solid #d97706;
}

.task-status-badge--stopped {
  background: rgba(5, 150, 105, 0.12);
  color: #059669;
  border: 1px solid #059669;
}

.task-status-badge--unknown {
  background: rgba(107, 114, 128, 0.12);
  color: #4b5563;
  border: 1px solid #9ca3af;
}

.progress-bar-wrap {
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--primary-color, #6366f1);
}

.progress-bar--animated {
  width: 40%;
  animation: progress-slide 1.4s ease-in-out infinite;
}

@keyframes progress-slide {
  0%   { transform: translateX(-150%); }
  100% { transform: translateX(400%); }
}

.text-danger { color: #ef4444; }
.text-success { color: #059669; }

.form-group--center {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-primary);
  padding-bottom: 0.5rem;
}

.checkbox-label input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
  cursor: pointer;
}

.ml-1 { margin-left: 0.25rem; }
.mb-2 { margin-bottom: 1rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.75rem; }
.p-3 { padding: 1.5rem; }
.text-xs { font-size: 0.75rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-muted, #888); }
.text-center { text-align: center; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }

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
  max-width: 640px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.75rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body {
  padding: 1.5rem;
  color: var(--text-primary);
}

/* Status badges */
.badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.1rem 0.45rem;
  border-radius: 0.25rem;
  text-transform: uppercase;
  border: 1px solid;
}

.badge--ok {
  background: rgba(5, 150, 105, 0.1);
  color: #059669;
  border-color: #059669;
}

.badge--fail {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border-color: #ef4444;
}

.badge--off {
  background: rgba(107, 114, 128, 0.1);
  color: #6b7280;
  border-color: #9ca3af;
}

/* PBS group prune action button (right-aligned in group header) */
.pbs-group-action {
  margin-left: auto;
  flex-shrink: 0;
}

/* Task log pre block */
.task-log-pre {
  background: var(--bg-secondary, #111);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.75rem 1rem;
  font-size: 0.8rem;
  color: var(--text-primary);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 60vh;
  overflow-y: auto;
}

/* Error banner in modals */
.error-banner {
  padding: 0.65rem 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid #ef4444;
  border-radius: 0.375rem;
  color: #ef4444;
  font-size: 0.875rem;
}

@media (max-width: 640px) {
  .form-row {
    grid-template-columns: 1fr;
  }
  .pbs-group-meta {
    display: none;
  }
  .retention-sched-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
}

/* ── Schedule creation wizard ────────────────────────────────────── */
.sched-wizard {
  max-width: 780px;
}

.sched-wizard-steps {
  display: flex;
  gap: 0;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  overflow-x: auto;
}

.sw-step {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.sw-step--active {
  background: rgba(99,102,241,.15);
  color: var(--primary-color, #6366f1);
}

.sw-step--done { color: #4ade80; }

.sw-step-num {
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  background: var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 700;
  flex-shrink: 0;
}

.sw-step--active .sw-step-num { background: var(--primary-color, #6366f1); color: #fff; }
.sw-step--done .sw-step-num   { background: #22c55e; color: #fff; }

.sched-wizard-footer {
  padding: 0.875rem 1.5rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* Scope options */
.scope-options {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.scope-opt {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background 0.1s, border-color 0.1s;
}

.scope-opt:hover { background: rgba(255,255,255,.03); }

.scope-opt--active {
  background: rgba(99,102,241,.08);
  border-color: rgba(99,102,241,.4);
}

.scope-opt input[type="radio"] { margin-top: 0.1rem; flex-shrink: 0; }

.scope-opt-body {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

/* Node checklist */
.node-checklist {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.25rem;
}

.node-check-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 9999px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.1s;
}

.node-check-item:hover { background: rgba(255,255,255,.04); }
.node-check-item input[type="checkbox"] { cursor: pointer; }

/* VMID tag input */
.vmid-tag-input {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.35rem 0.5rem;
  background: var(--bg-secondary, rgba(255,255,255,.04));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: text;
  min-height: 2.4rem;
  align-items: center;
}

.vmid-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  background: rgba(99,102,241,.15);
  color: var(--primary-color, #6366f1);
  border-radius: 9999px;
  padding: 0.1rem 0.4rem 0.1rem 0.6rem;
  font-size: 0.8rem;
  font-weight: 600;
}

.vmid-tag-remove {
  background: none;
  border: none;
  cursor: pointer;
  color: inherit;
  opacity: 0.7;
  font-size: 0.9rem;
  line-height: 1;
  padding: 0;
}

.vmid-tag-remove:hover { opacity: 1; }

.vmid-tag-text-input {
  flex: 1;
  min-width: 80px;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 0.875rem;
  padding: 0.15rem 0.25rem;
}

/* Cron presets */
.cron-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.75rem;
}

.cron-preset-btn {
  padding: 0.3rem 0.75rem;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 9999px;
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--text-secondary);
  transition: background 0.1s, border-color 0.1s, color 0.1s;
}

.cron-preset-btn:hover {
  background: rgba(255,255,255,.04);
  color: var(--text-primary);
}

.cron-preset-btn--active {
  background: rgba(99,102,241,.15);
  border-color: rgba(99,102,241,.5);
  color: var(--primary-color, #6366f1);
}

/* Retention row in step 2 */
.sched-retention-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.form-hint {
  display: block;
  font-size: 0.72rem;
  color: var(--text-muted, #888);
  margin-top: 0.2rem;
}

/* Review sections in step 4 */
.review-sections {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.review-section {
  background: var(--bg-secondary, rgba(255,255,255,.02));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
}

.review-section-title {
  padding: 0.4rem 0.875rem;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #888);
  border-bottom: 1px solid var(--border-color);
  background: rgba(0,0,0,.1);
}

.review-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.35rem 0.875rem;
  font-size: 0.875rem;
  border-bottom: 1px solid rgba(255,255,255,.04);
  gap: 1rem;
}

.review-row:last-child { border-bottom: none; }
.review-row > span:first-child { color: var(--text-secondary); flex-shrink: 0; }
.review-row code { font-size: 0.8rem; background: rgba(0,0,0,.15); padding: 0.1rem 0.3rem; border-radius: 3px; }

.info-box {
  padding: 0.75rem 1rem;
  background: rgba(59,130,246,.08);
  border: 1px solid rgba(59,130,246,.25);
  border-radius: 0.375rem;
  color: #60a5fa;
  font-size: 0.875rem;
}

/* Quick backup log */
.quick-backup-log-title {
  margin-bottom: 0.25rem;
}

@media (max-width: 640px) {
  .sched-retention-row {
    grid-template-columns: 1fr 1fr;
  }
}

/* Retention Policies tab */
.retention-sched-card {
  border-bottom: 1px solid var(--border-color);
  padding: 1rem 1.25rem;
}

.retention-sched-card:last-child {
  border-bottom: none;
}

.retention-sched-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.65rem;
}

.retention-sched-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.retention-sched-id {
  font-size: 0.95rem;
  color: var(--text-primary);
}

.retention-cron {
  font-size: 0.8rem;
  background: var(--bg-secondary, rgba(255,255,255,0.05));
  color: var(--text-secondary);
  padding: 0.1rem 0.35rem;
  border-radius: 0.2rem;
}

.retention-policy-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}

.retention-chip {
  background: rgba(99, 102, 241, 0.1);
  color: var(--primary-color, #6366f1);
  border: 1px solid var(--primary-color, #6366f1);
  border-radius: 0.25rem;
  padding: 0.1rem 0.45rem;
  font-size: 0.75rem;
  font-weight: 600;
}

/* Retention timeline */
.retention-timeline {
  margin-top: 0.5rem;
}

.retention-timeline-label {
  margin-bottom: 0.35rem;
}

.retention-timeline-bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 52px;
  overflow-x: auto;
  padding-bottom: 0.25rem;
}

.retention-timeline-bucket {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  min-width: 28px;
}

.retention-timeline-bar {
  width: 20px;
  background: var(--primary-color, #6366f1);
  border-radius: 3px 3px 0 0;
  opacity: 0.8;
  min-height: 4px;
  transition: height 0.3s ease;
}

.retention-timeline-tick {
  font-size: 0.62rem;
  white-space: nowrap;
}

.retention-timeline-summary {
  margin-top: 0.35rem;
}

/* PBS datastore retention */
.retention-ds-card {
  border-bottom: 1px solid var(--border-color);
  padding: 1rem 1.25rem;
}

.retention-ds-card:last-child {
  border-bottom: none;
}

.retention-ds-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

/* Retention edit modal */
.retention-preview-box {
  padding: 0.75rem 1rem;
  background: rgba(99, 102, 241, 0.07);
  border: 1px solid var(--primary-color, #6366f1);
  border-radius: 0.375rem;
  margin-bottom: 1rem;
}

.retention-preview-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0.4rem 0;
}

/* PBS prune policy modal */
.prune-apply-section {
  border-top: 1px solid var(--border-color);
  padding-top: 1.25rem;
  margin-top: 1.25rem;
}

.prune-apply-title {
  margin: 0 0 0.75rem 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
}

.prune-preview-box {
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background: var(--bg-secondary, rgba(255,255,255,0.02));
  margin-bottom: 0.75rem;
}

.prune-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.prune-preview-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.prune-preview-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  font-size: 0.875rem;
  flex-wrap: wrap;
}

.text-danger { color: #ef4444; }
.text-success { color: #059669; }

/* Toggle switch for schedule enabled/disabled */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  cursor: pointer;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}

.toggle-slider {
  position: absolute;
  inset: 0;
  background: rgba(107, 114, 128, 0.4);
  border-radius: 20px;
  transition: background 0.2s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  width: 14px;
  height: 14px;
  left: 3px;
  top: 3px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
}

.toggle-switch input:checked + .toggle-slider {
  background: var(--primary-color, #6366f1);
}

.toggle-switch input:checked + .toggle-slider::before {
  transform: translateX(16px);
}

/* PBS Server per-row snapshot sub-panel */
.pbs-server-snapshot-panel {
  padding: 0.75rem 1rem;
  border-top: 2px solid var(--primary-color, #6366f1);
}

.pbs-server-snapshot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
</style>
