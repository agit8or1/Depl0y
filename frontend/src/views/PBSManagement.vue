<template>
  <div class="pbs-page">
    <div class="page-header mb-2">
      <div class="page-header-left">
        <h2>PBS Management</h2>
        <p class="text-muted">Manage Proxmox Backup Servers, datastores, and backup jobs</p>
      </div>
      <div class="page-header-actions">
        <span v-if="lastRefreshed" class="text-muted text-xs">
          Refreshed {{ lastRefreshedAgo }}
        </span>
        <button @click="refreshAll" class="btn btn-outline btn-sm" :disabled="loading">
          {{ loading ? 'Refreshing...' : '⟳ Refresh' }}
        </button>
        <button @click="openAddServerModal" class="btn btn-primary btn-sm">
          + Add PBS Server
        </button>
      </div>
    </div>

    <!-- Error banner -->
    <div v-if="globalError" class="error-banner mb-2">{{ globalError }}</div>

    <!-- No servers state -->
    <div v-if="!loading && servers.length === 0" class="empty-state card">
      <div class="empty-state-icon">🗄️</div>
      <h3>No PBS Servers Configured</h3>
      <p class="text-muted">Add a Proxmox Backup Server to start managing backups, datastores, and jobs.</p>
      <button @click="openAddServerModal" class="btn btn-primary mt-2">Add PBS Server</button>
    </div>

    <!-- ── PBS Summary dashboard cards ── -->
    <div v-if="servers.length > 0" class="pbs-summary-grid mb-3">
      <div
        v-for="srv in servers"
        :key="`summary-${srv.id}`"
        class="pbs-summary-card"
      >
        <div class="pbs-summary-header">
          <div class="flex align-center gap-1">
            <span class="server-icon">🗄️</span>
            <strong>{{ srv.name }}</strong>
            <span class="text-xs text-muted">{{ srv.hostname }}</span>
          </div>
          <span v-if="serverSummaries[srv.id]?.error" class="badge badge-warning" :title="serverSummaries[srv.id].error">partial</span>
        </div>

        <div v-if="loadingSummaries[srv.id] && !serverSummaries[srv.id]" class="text-xs text-muted p-1">Loading…</div>

        <template v-else-if="serverSummaries[srv.id]">
          <!-- Capacity -->
          <div class="pbs-summary-section">
            <div class="pbs-summary-label">Capacity</div>
            <div class="pbs-summary-bar-wrap">
              <div
                class="pbs-summary-bar"
                :class="usageBarClass(serverSummaries[srv.id].datastore_totals.usage_pct)"
                :style="{ width: Math.min(100, serverSummaries[srv.id].datastore_totals.usage_pct) + '%' }"
              ></div>
            </div>
            <div class="pbs-summary-usage-labels">
              <span class="text-xs">
                {{ formatBytes(serverSummaries[srv.id].datastore_totals.used_bytes) }} /
                {{ formatBytes(serverSummaries[srv.id].datastore_totals.total_bytes) }}
              </span>
              <span class="text-xs"
                :class="usagePctTextClass(serverSummaries[srv.id].datastore_totals.usage_pct)">
                {{ serverSummaries[srv.id].datastore_totals.usage_pct.toFixed(1) }}% used
              </span>
            </div>
            <div class="text-xs text-muted mt-1">
              {{ formatBytes(serverSummaries[srv.id].datastore_totals.available_bytes) }} available
              · {{ serverSummaries[srv.id].datastore_totals.datastores.length }} datastore(s)
            </div>
          </div>

          <!-- Sync / Replication jobs -->
          <div class="pbs-summary-section">
            <div class="pbs-summary-label">Sync Jobs</div>
            <div
              v-if="(serverSummaries[srv.id].sync_jobs || []).length === 0"
              class="text-xs text-muted"
            >No sync jobs configured.</div>
            <div v-else class="pbs-summary-jobs">
              <div
                v-for="j in serverSummaries[srv.id].sync_jobs"
                :key="`${srv.id}-${j.id}`"
                class="pbs-summary-job"
              >
                <span
                  class="job-status-badge"
                  :class="'job-status-badge--' + syncJobBadgeClass(j)"
                >{{ syncJobBadgeLabel(j) }}</span>
                <span class="text-xs font-mono pbs-summary-job-id" :title="j.id">{{ j.id }}</span>
                <span v-if="j.store" class="text-xs text-muted">→ {{ j.store }}</span>
                <span v-if="j.last_run_endtime" class="text-xs text-muted pbs-summary-job-when">
                  {{ formatRelativeTime(j.last_run_endtime) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Recent backups (24h) -->
          <div class="pbs-summary-section">
            <div class="pbs-summary-label">Backups (last 24h)</div>
            <div class="pbs-summary-counts">
              <span class="pbs-summary-count-pill pbs-summary-count-pill--ok">
                OK: {{ serverSummaries[srv.id].recent_backups_24h.ok }}
              </span>
              <span class="pbs-summary-count-pill pbs-summary-count-pill--failed">
                Failed: {{ serverSummaries[srv.id].recent_backups_24h.failed }}
              </span>
              <span class="pbs-summary-count-pill">
                Total: {{ serverSummaries[srv.id].recent_backups_24h.total }}
              </span>
            </div>
          </div>
        </template>

        <div v-else class="text-xs text-muted p-1">No data.</div>
      </div>
    </div>

    <!-- Server cards (overview) -->
    <div v-if="servers.length > 0" class="server-grid mb-3">
      <div
        v-for="srv in servers"
        :key="srv.id"
        :class="['server-card', selectedServerId === srv.id ? 'server-card--active' : '']"
        @click="selectServer(srv)"
      >
        <div class="server-card-header">
          <div class="server-card-title">
            <span class="server-icon">🗄️</span>
            <div>
              <strong>{{ srv.name }}</strong>
              <div class="text-xs text-muted">{{ srv.hostname }}:{{ srv.port || 8007 }}</div>
            </div>
          </div>
          <div class="flex gap-1 align-center">
            <span :class="['status-dot', getServerStatus(srv)]"></span>
            <button
              @click.stop="confirmDeleteServer(srv)"
              class="btn btn-danger btn-xs"
              title="Remove server"
            >Remove</button>
          </div>
        </div>
        <div class="server-card-stats" v-if="serverStats[srv.id]">
          <div class="stat-pill">
            <span class="stat-label">Datastores</span>
            <span class="stat-value">{{ (serverStats[srv.id].datastores || []).length }}</span>
          </div>
          <div class="stat-pill">
            <span class="stat-label">Jobs</span>
            <span class="stat-value">{{ (serverStats[srv.id].jobs || []).length }}</span>
          </div>
          <div class="stat-pill">
            <span class="stat-label">Failed</span>
            <span :class="['stat-value', failedJobCount(srv.id) > 0 ? 'text-danger' : 'text-success']">
              {{ failedJobCount(srv.id) }}
            </span>
          </div>
        </div>
        <div v-else-if="loadingServerStats[srv.id]" class="text-xs text-muted mt-1">Loading stats...</div>
        <div v-else class="text-xs text-muted mt-1">Click to load details</div>
      </div>
    </div>

    <!-- Detail panel for selected server -->
    <template v-if="selectedServerId && servers.length > 0">
      <!-- Tabs -->
      <div class="tab-bar mb-2">
        <button
          :class="['tab-btn', activeTab === 'overview' ? 'tab-btn--active' : '']"
          @click="activeTab = 'overview'"
        >Overview</button>
        <button
          :class="['tab-btn', activeTab === 'datastores' ? 'tab-btn--active' : '']"
          @click="activeTab = 'datastores'; fetchDatastores()"
        >Datastores</button>
        <button
          :class="['tab-btn', activeTab === 'tapes' ? 'tab-btn--active' : '']"
          @click="activeTab = 'tapes'; fetchTapes()"
        >Tapes</button>
        <button
          :class="['tab-btn', activeTab === 'tasks' ? 'tab-btn--active' : '']"
          @click="activeTab = 'tasks'; fetchRecentTasks()"
        >Recent Tasks</button>
      </div>

      <!-- ── Overview Tab ── -->
      <div v-if="activeTab === 'overview'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>Server Overview — {{ selectedServer.name }}</h3>
            <button @click="fetchServerOverview(selectedServerId)" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="loadingOverview" class="loading-spinner"></div>
          <div v-else-if="overviewData" class="overview-grid">
            <div class="overview-item">
              <span class="overview-label">Version</span>
              <span class="overview-value">{{ overviewData.version || '—' }}</span>
            </div>
            <div class="overview-item">
              <span class="overview-label">Hostname</span>
              <span class="overview-value">{{ overviewData.hostname || selectedServer.hostname }}</span>
            </div>
            <div class="overview-item">
              <span class="overview-label">CPU Usage</span>
              <span class="overview-value">
                <span v-if="overviewData.cpu != null">{{ (overviewData.cpu * 100).toFixed(1) }}%</span>
                <span v-else>—</span>
              </span>
            </div>
            <div class="overview-item">
              <span class="overview-label">Memory</span>
              <span class="overview-value">
                <span v-if="overviewData.memory">
                  {{ formatBytes(overviewData.memory.used) }} / {{ formatBytes(overviewData.memory.total) }}
                </span>
                <span v-else>—</span>
              </span>
            </div>
            <div class="overview-item">
              <span class="overview-label">Uptime</span>
              <span class="overview-value">{{ formatUptime(overviewData.uptime) }}</span>
            </div>
          </div>
          <div v-else class="text-muted p-2 text-sm">Could not load server info.</div>
        </div>

        <!-- Recent backup job status cards -->
        <div class="card">
          <div class="card-header">
            <h3>Backup Job Status</h3>
          </div>
          <div v-if="loadingJobs" class="loading-spinner"></div>
          <div v-else-if="jobs.length === 0" class="text-muted p-2 text-sm">No backup jobs found.</div>
          <div v-else class="job-cards-grid">
            <div
              v-for="job in jobs"
              :key="job.id || job['job-id']"
              :class="['job-card', `job-card--${jobStatusClass(job)}`]"
            >
              <div class="job-card-header">
                <span class="job-icon">{{ jobStatusIcon(job) }}</span>
                <div class="job-card-info">
                  <strong class="text-sm">{{ pbsJobLabel(job) }}</strong>
                  <div class="text-xs text-muted">
                    <span class="job-type-pill">{{ (job['job-type'] || 'sync').toUpperCase() }}</span>
                    Store: {{ job.store || job.datastore || '—' }}
                    <span class="font-mono" style="opacity:0.5;margin-left:4px;">{{ job.id || job['job-id'] }}</span>
                  </div>
                </div>
                <span :class="['job-status-badge', `job-status-badge--${jobStatusClass(job)}`]">
                  {{ jobStatusLabel(job) }}
                </span>
              </div>
              <div class="job-card-meta">
                <div class="text-xs text-muted">
                  Schedule: <code class="cron-text">{{ job.schedule || '—' }}</code>
                </div>
                <div class="text-xs text-muted">
                  Last run: {{ job['last-run-upid'] ? formatRelativeTime(job['last-run-endtime']) : 'Never' }}
                </div>
                <div class="text-xs text-muted" v-if="job['next-run']">
                  Next: {{ formatDate(job['next-run']) }}
                </div>
              </div>
              <div class="job-card-actions">
                <button
                  @click="triggerJob(job)"
                  class="btn btn-outline btn-xs"
                  :disabled="triggeringJob === (job.id || job['job-id'])"
                  title="Run this backup job now"
                >
                  {{ triggeringJob === (job.id || job['job-id']) ? 'Starting...' : '▶ Run Now' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Datastores Tab ── -->
      <div v-if="activeTab === 'datastores'">
        <!-- Browse panel: shown when a datastore is selected -->
        <template v-if="browseDatastore">
          <div class="card">
            <div class="card-header">
              <div class="flex align-center gap-1">
                <button @click="closeBrowse" class="btn btn-outline btn-sm">← Back</button>
                <h3>💾 {{ browseDatastore.store || browseDatastore.name }}</h3>
              </div>
              <div class="flex gap-1 align-center">
                <button @click="fetchBrowseGroups" class="btn btn-outline btn-sm">Refresh</button>
                <button @click="openPruneGroupModal(null)" class="btn btn-outline btn-sm" title="Prune backup group">✂ Prune Group</button>
              </div>
            </div>

            <div v-if="loadingBrowse" class="loading-spinner"></div>
            <div v-else-if="browseGroups.length === 0" class="text-muted p-2 text-sm">No backup groups found in this datastore.</div>
            <div v-else>
              <div v-for="group in browseGroups" :key="group['backup-type'] + '/' + group['backup-id']" class="browse-group">
                <div class="browse-group-header" @click="toggleBrowseGroup(group)">
                  <span class="browse-group-expand">{{ browseExpandedKey === groupKey(group) ? '▼' : '▶' }}</span>
                  <span class="browse-group-type-pill">{{ group['backup-type'] }}</span>
                  <strong class="browse-group-id">{{ group['backup-id'] }}</strong>
                  <span class="text-xs text-muted ml-1">({{ group['backup-count'] || 0 }} snapshots)</span>
                  <span class="text-xs text-muted ml-1" v-if="group['last-backup']">
                    Last: {{ formatRelativeTime(group['last-backup']) }}
                  </span>
                  <div class="browse-group-actions" @click.stop>
                    <button class="btn btn-outline btn-xs" @click="openPruneGroupModal(group)" title="Prune this group">✂ Prune</button>
                  </div>
                </div>

                <!-- Snapshots for this group -->
                <div v-if="browseExpandedKey === groupKey(group)" class="browse-snapshots">
                  <div v-if="loadingSnapshots" class="text-xs text-muted p-2">Loading snapshots…</div>
                  <table v-else-if="browseSnapshots.length > 0" class="table">
                    <thead>
                      <tr>
                        <th>Backup Time</th>
                        <th>Size</th>
                        <th>Verify</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="snap in browseSnapshots" :key="snap['backup-time']">
                        <td class="text-sm">{{ formatDate(snap['backup-time']) }}</td>
                        <td class="text-sm">{{ snap.size != null ? formatBytes(snap.size) : '—' }}</td>
                        <td>
                          <span v-if="snap.verification" :class="['job-status-badge', snap.verification.state === 'ok' ? 'job-status-badge--ok' : 'job-status-badge--failed']">
                            {{ snap.verification.state }}
                          </span>
                          <span v-else class="text-xs text-muted">unverified</span>
                        </td>
                        <td @click.stop>
                          <div class="flex gap-1">
                            <button class="btn btn-outline btn-xs" @click="verifySnap(group, snap)" :disabled="snapActionRunning" title="Verify integrity">✓ Verify</button>
                            <button class="btn btn-danger btn-xs" @click="forgetSnap(group, snap)" :disabled="snapActionRunning" title="Delete snapshot">🗑</button>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-else class="text-xs text-muted p-2">No snapshots.</div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- Datastore list: shown when no datastore selected -->
        <template v-else>
          <div class="card">
            <div class="card-header">
              <h3>Datastores</h3>
              <button @click="fetchDatastores" class="btn btn-outline btn-sm">Refresh</button>
            </div>
            <div v-if="loadingDatastores" class="loading-spinner"></div>
            <div v-else-if="datastores.length === 0" class="text-muted p-2 text-sm">No datastores found.</div>
            <div v-else class="ds-grid">
              <div v-for="ds in datastores" :key="ds.store || ds.name" class="ds-card ds-card--clickable" @click="openBrowse(ds)">
                <div class="ds-card-header">
                  <span class="ds-icon">💾</span>
                  <div>
                    <strong>{{ ds.store || ds.name }}</strong>
                    <div v-if="ds.path" class="text-xs text-muted">{{ ds.path }}</div>
                  </div>
                  <span class="ds-browse-hint text-xs text-muted">Browse →</span>
                </div>
                <!-- Disk usage bar -->
                <div v-if="ds.used != null && ds.avail != null" class="ds-usage">
                  <div class="ds-usage-bar-wrap">
                    <div
                      class="ds-usage-bar"
                      :style="{ width: dsUsagePercent(ds) + '%' }"
                      :class="dsUsageClass(ds)"
                    ></div>
                  </div>
                  <div class="ds-usage-labels">
                    <span class="text-xs">{{ formatBytes(ds.used) }} used</span>
                    <span class="text-xs text-muted">{{ formatBytes(ds.avail) }} free</span>
                  </div>
                </div>
                <div class="ds-card-meta">
                  <div class="text-xs text-muted" v-if="ds.total">Total: {{ formatBytes(ds.total) }}</div>
                  <div class="text-xs text-muted" v-if="ds['gc-status']">
                    GC: {{ ds['gc-status']['last-run-endtime'] ? formatRelativeTime(ds['gc-status']['last-run-endtime']) : 'never' }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Prune Group Modal -->
      <div v-if="pruneModal.show" class="modal" @click.self="pruneModal.show = false">
        <div class="modal-content" @click.stop>
          <div class="modal-header">
            <h3>Prune Backup Group</h3>
            <button @click="pruneModal.show = false" class="btn-close">&#215;</button>
          </div>
          <div class="modal-body">
            <p class="text-sm text-muted mb-2">Remove old snapshots from <strong>{{ pruneModal.group ? (pruneModal.group['backup-type'] + '/' + pruneModal.group['backup-id']) : 'all groups' }}</strong> according to retention rules.</p>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Keep Last</label>
                <input v-model.number="pruneModal.keepLast" type="number" min="0" class="form-control" placeholder="e.g. 7" />
              </div>
              <div class="form-group">
                <label class="form-label">Keep Daily</label>
                <input v-model.number="pruneModal.keepDaily" type="number" min="0" class="form-control" placeholder="e.g. 14" />
              </div>
              <div class="form-group">
                <label class="form-label">Keep Weekly</label>
                <input v-model.number="pruneModal.keepWeekly" type="number" min="0" class="form-control" placeholder="e.g. 4" />
              </div>
              <div class="form-group">
                <label class="form-label">Keep Monthly</label>
                <input v-model.number="pruneModal.keepMonthly" type="number" min="0" class="form-control" placeholder="e.g. 3" />
              </div>
            </div>
            <div v-if="pruneModal.error" class="error-banner mt-1">{{ pruneModal.error }}</div>
            <div class="flex gap-1 mt-2">
              <button class="btn btn-danger" @click="runPrune" :disabled="pruneModal.running">
                {{ pruneModal.running ? 'Pruning…' : 'Prune Now' }}
              </button>
              <button class="btn btn-outline" @click="pruneModal.show = false">Cancel</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Tapes Tab ── -->
      <div v-if="activeTab === 'tapes'">
        <div class="card">
          <div class="card-header">
            <h3>Tape Media</h3>
            <button @click="fetchTapes" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="loadingTapes" class="loading-spinner"></div>
          <div v-else-if="tapeError" class="text-muted p-2 text-sm">{{ tapeError }}</div>
          <div v-else-if="tapes.length === 0" class="text-muted p-2 text-sm">
            No tapes found. Tape support requires a tape drive configured on the PBS server.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Media Set</th>
                  <th>Pool</th>
                  <th>Location</th>
                  <th>Status</th>
                  <th>Bytes Written</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tape in tapes" :key="tape.label">
                  <td><strong>{{ tape.label }}</strong></td>
                  <td class="text-sm text-muted">{{ tape['media-set-uuid'] || '—' }}</td>
                  <td>{{ tape.pool || '—' }}</td>
                  <td>{{ tape.location || '—' }}</td>
                  <td>
                    <span :class="['job-status-badge', tape.status === 'ok' ? 'job-status-badge--ok' : 'job-status-badge--unknown']">
                      {{ tape.status || 'unknown' }}
                    </span>
                  </td>
                  <td class="text-sm">{{ tape['bytes-written'] != null ? formatBytes(tape['bytes-written']) : '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ── Recent Tasks Tab ── -->
      <div v-if="activeTab === 'tasks'">
        <div class="card">
          <div class="card-header">
            <h3>Recent Tasks</h3>
            <button @click="fetchRecentTasks" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="loadingTasks" class="loading-spinner"></div>
          <div v-else-if="recentTasks.length === 0" class="text-muted p-2 text-sm">No recent tasks.</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Worker ID</th>
                  <th>Node</th>
                  <th>Start Time</th>
                  <th>Duration</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="task in recentTasks" :key="task.upid">
                  <td><strong>{{ task.type || task.worker_type || '—' }}</strong></td>
                  <td class="text-xs text-muted" style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" :title="task['worker-id'] || task.worker_id">
                    {{ task['worker-id'] || task.worker_id || '—' }}
                  </td>
                  <td>{{ task.node || '—' }}</td>
                  <td class="text-sm text-muted">{{ task.starttime ? formatDate(task.starttime) : '—' }}</td>
                  <td class="text-sm">{{ taskDuration(task) }}</td>
                  <td>
                    <span :class="['job-status-badge', taskStatusClass(task)]">
                      {{ task.status || task.exitstatus || 'running' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- Add PBS Server Modal -->
    <div v-if="addServerModal.show" class="modal" @click.self="closeAddServerModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add PBS Server</h3>
          <button @click="closeAddServerModal" class="btn-close">&#215;</button>
        </div>
        <form @submit.prevent="submitAddServer" class="modal-body">
          <div class="form-group">
            <label class="form-label">Name <span class="required">*</span></label>
            <input v-model="addServerForm.name" class="form-control" placeholder="e.g. pbs-main" required />
            <div class="text-xs text-muted mt-1">A friendly display name for this server.</div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Hostname / IP <span class="required">*</span></label>
              <input v-model="addServerForm.hostname" class="form-control" placeholder="pbs.example.com" required />
            </div>
            <div class="form-group">
              <label class="form-label">Port</label>
              <input
                v-model.number="addServerForm.port"
                type="number"
                class="form-control"
                min="1"
                max="65535"
                placeholder="8007"
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="addServerForm.username" class="form-control" placeholder="root@pam" autocomplete="username" />
            <div class="text-xs text-muted mt-1">Required. Use with password auth, or leave when using API token only.</div>
          </div>

          <div class="form-group">
            <label class="form-label">Authentication method</label>
            <div class="flex gap-2" style="align-items:center">
              <label class="radio-label"><input type="radio" value="password" v-model="addServerForm._auth_method" /> Password</label>
              <label class="radio-label"><input type="radio" value="token" v-model="addServerForm._auth_method" /> API token</label>
            </div>
            <div class="text-xs text-muted mt-1">Either is accepted. API tokens are preferred on PBS with 2FA.</div>
          </div>

          <div v-if="addServerForm._auth_method === 'password'" class="form-group">
            <label class="form-label">Password</label>
            <input
              v-model="addServerForm.password"
              type="password"
              class="form-control"
              placeholder="PBS user password"
              autocomplete="new-password"
            />
          </div>

          <template v-else>
            <div class="form-group">
              <label class="form-label">API Token ID</label>
              <input
                v-model="addServerForm.api_token_id"
                class="form-control"
                placeholder="root@pam!mytoken"
                autocomplete="off"
              />
              <div class="text-xs text-muted mt-1">Format: user@realm!tokenname</div>
            </div>
            <div class="form-group">
              <label class="form-label">API Token Secret</label>
              <input
                v-model="addServerForm.api_token_secret"
                type="password"
                class="form-control"
                placeholder="Token secret value"
                autocomplete="new-password"
              />
            </div>
          </template>

          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="addServerForm.verify_ssl" />
              <span>Verify SSL Certificate</span>
            </label>
            <div class="text-xs text-muted mt-1">Uncheck for self-signed certificates (typical for PBS).</div>
          </div>

          <div v-if="addServerModal.error" class="error-banner mt-1">{{ addServerModal.error }}</div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="addServerModal.saving">
              {{ addServerModal.saving ? 'Adding...' : 'Add Server' }}
            </button>
            <button type="button" @click="closeAddServerModal" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Job trigger result toast-like banner -->
    <div v-if="jobRunResult" class="job-run-result">
      <span>{{ jobRunResult }}</span>
      <button @click="jobRunResult = null" class="btn-close-sm">&#215;</button>
    </div>
  </div>
</template>

<script>
import { axiosInstance as api } from '@/services/api'

const REFRESH_INTERVAL_MS = 30000

export default {
  name: 'PBSManagement',

  data() {
    return {
      loading: false,
      globalError: null,
      servers: [],
      selectedServerId: null,
      serverStats: {},
      loadingServerStats: {},

      // Aggregated dashboard summary per PBS server (from /pbs-mgmt/{id}/summary)
      serverSummaries: {},
      loadingSummaries: {},
      _summaryTimer: null,

      activeTab: 'overview',

      // Overview tab
      loadingOverview: false,
      overviewData: null,

      // Datastores tab
      loadingDatastores: false,
      datastores: [],

      // Datastore browse
      browseDatastore: null,
      browseGroups: [],
      loadingBrowse: false,
      browseExpandedKey: null,
      browseSnapshots: [],
      loadingSnapshots: false,
      snapActionRunning: false,

      // Prune modal
      pruneModal: { show: false, group: null, keepLast: null, keepDaily: null, keepWeekly: null, keepMonthly: null, running: false, error: null },

      // Jobs tab
      loadingJobs: false,
      jobs: [],
      triggeringJob: null,
      jobRunResult: null,

      // Tapes tab
      loadingTapes: false,
      tapes: [],
      tapeError: null,

      // Recent Tasks tab
      loadingTasks: false,
      recentTasks: [],

      // Add server modal
      addServerModal: { show: false, saving: false, error: null },
      addServerForm: {
        name: '',
        hostname: '',
        port: 8007,
        username: 'root@pam',
        password: '',
        api_token_id: '',
        api_token_secret: '',
        verify_ssl: false,
        _auth_method: 'password',
      },

      lastRefreshed: null,
      _refreshTimer: null,
    }
  },

  computed: {
    selectedServer() {
      return this.servers.find(s => s.id === this.selectedServerId) || null
    },
    lastRefreshedAgo() {
      if (!this.lastRefreshed) return ''
      const secs = Math.floor((Date.now() - this.lastRefreshed) / 1000)
      if (secs < 60) return `${secs}s ago`
      return `${Math.floor(secs / 60)}m ago`
    },
  },

  methods: {
    // ── Server list ──────────────────────────────────────────────────────
    async fetchServers() {
      this.loading = true
      this.globalError = null
      try {
        const res = await api.get('/pbs-mgmt/')
        this.servers = res.data || []
        if (this.servers.length > 0 && !this.selectedServerId) {
          this.selectServer(this.servers[0])
        }
        this.lastRefreshed = Date.now()
        // Load stats for all servers
        this.servers.forEach(srv => this.fetchServerStats(srv.id))
        // Load dashboard summary cards (aggregated capacity / jobs / recent backups)
        this.servers.forEach(srv => this.fetchServerSummary(srv.id))
      } catch (e) {
        this.globalError = e?.response?.data?.detail || 'Failed to load PBS servers.'
      } finally {
        this.loading = false
      }
    },

    async fetchServerStats(serverId) {
      this.$set ? this.$set(this.loadingServerStats, serverId, true) : (this.loadingServerStats[serverId] = true)
      try {
        const [dsRes, jobRes] = await Promise.allSettled([
          api.get(`/pbs-mgmt/${serverId}/datastores`),
          api.get(`/pbs-mgmt/${serverId}/jobs`),
        ])
        const stats = {
          datastores: dsRes.status === 'fulfilled' ? (dsRes.value.data || []) : [],
          jobs: jobRes.status === 'fulfilled' ? (jobRes.value.data || []) : [],
        }
        this.serverStats = { ...this.serverStats, [serverId]: stats }
      } catch {
        // non-critical
      } finally {
        this.loadingServerStats = { ...this.loadingServerStats, [serverId]: false }
      }
    },

    async fetchServerSummary(serverId) {
      this.loadingSummaries = { ...this.loadingSummaries, [serverId]: true }
      try {
        const res = await api.get(`/pbs-mgmt/${serverId}/summary`)
        this.serverSummaries = { ...this.serverSummaries, [serverId]: res.data }
      } catch (e) {
        // Leave previous data in place if the refresh fails
      } finally {
        this.loadingSummaries = { ...this.loadingSummaries, [serverId]: false }
      }
    },

    refreshAllSummaries() {
      this.servers.forEach(srv => this.fetchServerSummary(srv.id))
    },

    usageBarClass(pct) {
      if (pct >= 90) return 'pbs-summary-bar--danger'
      if (pct >= 75) return 'pbs-summary-bar--warning'
      return 'pbs-summary-bar--ok'
    },

    usagePctTextClass(pct) {
      if (pct >= 90) return 'text-danger'
      if (pct >= 75) return 'text-warning'
      return 'text-success'
    },

    syncJobBadgeClass(job) {
      const s = (job.last_run_state || '').toLowerCase()
      if (!s) return 'unknown'
      if (s.startsWith('ok')) return 'ok'
      if (s === 'running') return 'running'
      return 'failed'
    },

    syncJobBadgeLabel(job) {
      const s = (job.last_run_state || '').toLowerCase()
      if (!s) return 'IDLE'
      if (s.startsWith('ok')) return 'OK'
      if (s === 'running') return 'RUN'
      return 'ERR'
    },

    selectServer(srv) {
      this.selectedServerId = srv.id
      this.activeTab = 'overview'
      this.overviewData = null
      this.datastores = []
      this.jobs = []
      this.tapes = []
      this.recentTasks = []
      this.fetchServerOverview(srv.id)
      this.fetchJobs()
    },

    getServerStatus(srv) {
      const stats = this.serverStats[srv.id]
      if (!stats) return 'status-dot--unknown'
      return 'status-dot--ok'
    },

    failedJobCount(serverId) {
      const stats = this.serverStats[serverId]
      if (!stats) return 0
      return (stats.jobs || []).filter(j => this.jobStatusClass(j) === 'failed').length
    },

    // ── Overview ─────────────────────────────────────────────────────────
    async fetchServerOverview(serverId) {
      this.loadingOverview = true
      this.overviewData = null
      try {
        const res = await api.get(`/pbs-mgmt/${serverId}/overview`)
        this.overviewData = res.data || null
      } catch {
        this.overviewData = null
      } finally {
        this.loadingOverview = false
      }
    },

    // ── Datastores ───────────────────────────────────────────────────────
    async fetchDatastores() {
      if (!this.selectedServerId) return
      this.loadingDatastores = true
      try {
        const res = await api.get(`/pbs-mgmt/${this.selectedServerId}/datastores`)
        this.datastores = res.data || []
      } catch {
        this.datastores = []
      } finally {
        this.loadingDatastores = false
      }
    },

    // ── Datastore Browse ─────────────────────────────────────────────────
    openBrowse(ds) {
      this.browseDatastore = ds
      this.browseGroups = []
      this.browseExpandedKey = null
      this.browseSnapshots = []
      this.fetchBrowseGroups()
    },

    closeBrowse() {
      this.browseDatastore = null
      this.browseGroups = []
      this.browseExpandedKey = null
    },

    async fetchBrowseGroups() {
      if (!this.browseDatastore || !this.selectedServerId) return
      const dsName = this.browseDatastore.store || this.browseDatastore.name
      this.loadingBrowse = true
      try {
        const res = await api.get(`/pbs-mgmt/${this.selectedServerId}/datastores/${dsName}/groups`)
        this.browseGroups = res.data || []
      } catch {
        this.browseGroups = []
      } finally {
        this.loadingBrowse = false
      }
    },

    groupKey(group) {
      return `${group['backup-type']}/${group['backup-id']}`
    },

    async toggleBrowseGroup(group) {
      const key = this.groupKey(group)
      if (this.browseExpandedKey === key) {
        this.browseExpandedKey = null
        return
      }
      this.browseExpandedKey = key
      this.browseSnapshots = []
      this.loadingSnapshots = true
      const dsName = this.browseDatastore.store || this.browseDatastore.name
      try {
        const res = await api.get(`/pbs-mgmt/${this.selectedServerId}/datastores/${dsName}/snapshots`, {
          params: { 'backup-type': group['backup-type'], 'backup-id': group['backup-id'] }
        })
        this.browseSnapshots = (res.data || []).sort((a, b) => b['backup-time'] - a['backup-time'])
      } catch {
        this.browseSnapshots = []
      } finally {
        this.loadingSnapshots = false
      }
    },

    async verifySnap(group, snap) {
      if (!confirm(`Verify snapshot from ${this.formatDate(snap['backup-time'])}?`)) return
      this.snapActionRunning = true
      const dsName = this.browseDatastore.store || this.browseDatastore.name
      try {
        await api.post(`/pbs-mgmt/${this.selectedServerId}/datastores/${dsName}/verify`, {
          'backup-type': group['backup-type'],
          'backup-id': group['backup-id'],
          'backup-time': snap['backup-time'],
        })
        this.jobRunResult = 'Verify task started.'
        setTimeout(() => { if (this.jobRunResult) this.jobRunResult = null }, 5000)
      } catch (e) {
        this.jobRunResult = `Verify failed: ${e?.response?.data?.detail || e.message}`
      } finally {
        this.snapActionRunning = false
      }
    },

    async forgetSnap(group, snap) {
      if (!confirm(`Permanently delete snapshot from ${this.formatDate(snap['backup-time'])}? This cannot be undone.`)) return
      this.snapActionRunning = true
      const dsName = this.browseDatastore.store || this.browseDatastore.name
      try {
        await api.delete(`/pbs-mgmt/${this.selectedServerId}/datastores/${dsName}/snapshots`, {
          params: {
            'backup-type': group['backup-type'],
            'backup-id': group['backup-id'],
            'backup-time': snap['backup-time'],
          }
        })
        this.browseSnapshots = this.browseSnapshots.filter(s => s['backup-time'] !== snap['backup-time'])
        const g = this.browseGroups.find(g => this.groupKey(g) === this.groupKey(group))
        if (g && g['backup-count']) g['backup-count']--
        this.jobRunResult = 'Snapshot deleted.'
        setTimeout(() => { if (this.jobRunResult) this.jobRunResult = null }, 4000)
      } catch (e) {
        this.jobRunResult = `Delete failed: ${e?.response?.data?.detail || e.message}`
      } finally {
        this.snapActionRunning = false
      }
    },

    openPruneGroupModal(group) {
      this.pruneModal = { show: true, group, keepLast: 7, keepDaily: null, keepWeekly: null, keepMonthly: null, running: false, error: null }
    },

    async runPrune() {
      if (!this.browseDatastore || !this.selectedServerId) return
      const dsName = this.browseDatastore.store || this.browseDatastore.name
      const group = this.pruneModal.group
      const payload = {
        'backup-type': group ? group['backup-type'] : 'vm',
        'backup-id': group ? group['backup-id'] : '*',
      }
      if (this.pruneModal.keepLast) payload['keep-last'] = this.pruneModal.keepLast
      if (this.pruneModal.keepDaily) payload['keep-daily'] = this.pruneModal.keepDaily
      if (this.pruneModal.keepWeekly) payload['keep-weekly'] = this.pruneModal.keepWeekly
      if (this.pruneModal.keepMonthly) payload['keep-monthly'] = this.pruneModal.keepMonthly
      this.pruneModal.running = true
      this.pruneModal.error = null
      try {
        await api.post(`/pbs-mgmt/${this.selectedServerId}/datastores/${dsName}/prune`, payload)
        this.pruneModal.show = false
        this.jobRunResult = 'Prune task started.'
        setTimeout(() => { if (this.jobRunResult) this.jobRunResult = null }, 5000)
        // Refresh groups
        await this.fetchBrowseGroups()
      } catch (e) {
        this.pruneModal.error = e?.response?.data?.detail || 'Prune failed.'
      } finally {
        this.pruneModal.running = false
      }
    },

    dsUsagePercent(ds) {
      const total = ds.total || (ds.used + ds.avail)
      if (!total) return 0
      return Math.min(100, Math.round((ds.used / total) * 100))
    },

    dsUsageClass(ds) {
      const pct = this.dsUsagePercent(ds)
      if (pct >= 90) return 'ds-usage-bar--danger'
      if (pct >= 75) return 'ds-usage-bar--warning'
      return 'ds-usage-bar--ok'
    },

    // ── Jobs ─────────────────────────────────────────────────────────────
    async fetchJobs() {
      if (!this.selectedServerId) return
      this.loadingJobs = true
      try {
        const res = await api.get(`/pbs-mgmt/${this.selectedServerId}/jobs`)
        this.jobs = res.data || []
      } catch {
        this.jobs = []
      } finally {
        this.loadingJobs = false
      }
    },

    async triggerJob(job) {
      const jobId = job.id || job['job-id']
      if (!jobId || !this.selectedServerId) return
      this.triggeringJob = jobId
      try {
        await api.post(`/pbs-mgmt/${this.selectedServerId}/jobs/${jobId}/run`, null, { params: { job_type: job['job-type'] || 'sync' } })
        this.jobRunResult = `Job "${jobId}" started successfully.`
        setTimeout(() => { if (this.jobRunResult) this.jobRunResult = null }, 6000)
      } catch (e) {
        this.jobRunResult = `Failed to start job "${jobId}": ${e?.response?.data?.detail || e.message}`
      } finally {
        this.triggeringJob = null
      }
    },

    pbsJobLabel(job) {
      if (job.comment) return job.comment
      const type = (job['job-type'] || 'job')
      const store = job.store || job.datastore || ''
      const schedule = job.schedule || ''
      // verify: "Daily Verify — backup"
      // prune:  "Hourly Prune — backup"
      // sync:   "backup → remote-store"
      const typeLabels = { verify: 'Verify', prune: 'Prune', sync: 'Sync', pull: 'Pull' }
      const typeLabel = typeLabels[type] || type
      if (type === 'sync' || type === 'pull') {
        const target = job['remote-store'] || job['target-store'] || job['store'] || ''
        return target ? `Sync → ${target}` : `${typeLabel} job`
      }
      const schedLabel = schedule === 'daily' ? 'Daily' : schedule === 'hourly' ? 'Hourly' : schedule ? `${schedule}` : ''
      return [schedLabel, typeLabel, store ? `(${store})` : ''].filter(Boolean).join(' ')
    },

    jobStatusClass(job) {
      const status = job['last-run-state'] || job.status || ''
      if (!status || status === 'unknown' || !job['last-run-upid']) return 'unknown'
      if (status === 'ok' || status === 'OK') return 'ok'
      if (status === 'warning') return 'warning'
      return 'failed'
    },

    jobStatusLabel(job) {
      if (!job['last-run-upid']) return 'Never run'
      const s = job['last-run-state'] || job.status || 'unknown'
      return s
    },

    jobStatusIcon(job) {
      const cls = this.jobStatusClass(job)
      if (cls === 'ok') return '✅'
      if (cls === 'warning') return '⚠️'
      if (cls === 'failed') return '❌'
      return '⬜'
    },

    // ── Tapes ────────────────────────────────────────────────────────────
    async fetchTapes() {
      if (!this.selectedServerId) return
      this.loadingTapes = true
      this.tapeError = null
      try {
        const res = await api.get(`/pbs-mgmt/${this.selectedServerId}/tapes`)
        this.tapes = res.data || []
      } catch (e) {
        const status = e?.response?.status
        if (status === 404 || status === 501) {
          this.tapeError = 'Tape management is not available on this PBS server.'
        } else {
          this.tapeError = e?.response?.data?.detail || 'Failed to load tape information.'
        }
        this.tapes = []
      } finally {
        this.loadingTapes = false
      }
    },

    // ── Recent Tasks ─────────────────────────────────────────────────────
    async fetchRecentTasks() {
      if (!this.selectedServerId) return
      this.loadingTasks = true
      try {
        const res = await api.get(`/pbs-mgmt/${this.selectedServerId}/tasks`)
        this.recentTasks = (res.data || []).slice(0, 50)
      } catch {
        this.recentTasks = []
      } finally {
        this.loadingTasks = false
      }
    },

    taskStatusClass(task) {
      const s = task.status || task.exitstatus || ''
      if (!s || s === 'running' || s === 'RUNNING') return 'job-status-badge--running'
      if (s === 'OK' || s === 'ok') return 'job-status-badge--ok'
      if (s.toLowerCase().includes('warn')) return 'job-status-badge--warning'
      return 'job-status-badge--failed'
    },

    taskDuration(task) {
      if (!task.starttime || !task.endtime) return '—'
      const secs = task.endtime - task.starttime
      if (secs < 60) return `${secs}s`
      if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
      return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
    },

    // ── Add server modal ─────────────────────────────────────────────────
    openAddServerModal() {
      this.addServerForm = {
        name: '',
        hostname: '',
        port: 8007,
        username: 'root@pam',
        api_token_id: '',
        api_token_secret: '',
        verify_ssl: false,
      }
      this.addServerModal = { show: true, saving: false, error: null }
    },

    closeAddServerModal() {
      this.addServerModal = { show: false, saving: false, error: null }
    },

    async submitAddServer() {
      this.addServerModal.saving = true
      this.addServerModal.error = null
      try {
        const f = this.addServerForm
        const payload = {
          name: f.name, hostname: f.hostname, port: f.port,
          username: f.username, verify_ssl: f.verify_ssl,
        }
        if (f._auth_method === 'password') {
          if (!f.password) {
            this.addServerModal.error = 'Password is required when using password auth.'
            this.addServerModal.saving = false
            return
          }
          payload.password = f.password
        } else {
          if (!f.api_token_id || !f.api_token_secret) {
            this.addServerModal.error = 'API Token ID and Secret are required when using token auth.'
            this.addServerModal.saving = false
            return
          }
          payload.api_token_id = f.api_token_id
          payload.api_token_secret = f.api_token_secret
        }
        await api.post('/pbs/', payload)
        this.closeAddServerModal()
        await this.fetchServers()
      } catch (e) {
        this.addServerModal.error = e?.response?.data?.detail || 'Failed to add PBS server.'
      } finally {
        this.addServerModal.saving = false
      }
    },

    async confirmDeleteServer(srv) {
      if (!confirm(`Remove PBS server "${srv.name}"? This will not affect any data on the PBS server.`)) return
      try {
        await api.delete(`/pbs/${srv.id}`)
        if (this.selectedServerId === srv.id) {
          this.selectedServerId = null
        }
        await this.fetchServers()
      } catch (e) {
        this.globalError = e?.response?.data?.detail || 'Failed to remove server.'
      }
    },

    // ── Utilities ────────────────────────────────────────────────────────
    async refreshAll() {
      await this.fetchServers()
      if (this.selectedServerId) {
        if (this.activeTab === 'overview') this.fetchServerOverview(this.selectedServerId)
        if (this.activeTab === 'datastores') this.fetchDatastores()
        if (this.activeTab === 'jobs') this.fetchJobs()
        if (this.activeTab === 'tasks') this.fetchRecentTasks()
      }
    },

    formatBytes(bytes) {
      if (bytes == null || bytes === 0) return '0 B'
      const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + ' ' + units[i]
    },

    formatDate(ts) {
      if (!ts) return '—'
      const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
      return d.toLocaleString()
    },

    formatRelativeTime(ts) {
      if (!ts) return '—'
      const ms = typeof ts === 'number' ? ts * 1000 : new Date(ts).getTime()
      const diff = Date.now() - ms
      const secs = Math.floor(diff / 1000)
      if (secs < 60) return 'just now'
      if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
      if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
      return `${Math.floor(secs / 86400)}d ago`
    },

    formatUptime(secs) {
      if (!secs) return '—'
      const d = Math.floor(secs / 86400)
      const h = Math.floor((secs % 86400) / 3600)
      const m = Math.floor((secs % 3600) / 60)
      if (d > 0) return `${d}d ${h}h ${m}m`
      if (h > 0) return `${h}h ${m}m`
      return `${m}m`
    },
  },

  mounted() {
    this.fetchServers()
    this._refreshTimer = setInterval(() => {
      this.fetchServers()
      if (this.selectedServerId) {
        if (this.activeTab === 'overview') {
          this.fetchServerOverview(this.selectedServerId)
          this.fetchJobs()
        } else if (this.activeTab === 'datastores') {
          this.fetchDatastores()
        } else if (this.activeTab === 'tasks') {
          this.fetchRecentTasks()
        }
      }
    }, REFRESH_INTERVAL_MS)
    // Dashboard summary card has its own 60s refresh cadence
    this._summaryTimer = setInterval(() => this.refreshAllSummaries(), 60000)
  },

  beforeUnmount() {
    clearInterval(this._refreshTimer)
    clearInterval(this._summaryTimer)
  },
}
</script>

<style scoped>
/* ── Page layout ── */
.pbs-page {
  padding: 1.5rem;
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
}

.page-header-left h2 {
  margin: 0 0 0.25rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: #e2e8f0;
}

.page-header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

/* ── Cards/shared ── */
.card {
  background: #1a2332;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 0.5rem;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.9rem 1.1rem;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  gap: 0.75rem;
  flex-wrap: wrap;
}

.card-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #e2e8f0;
}

/* ── Empty state ── */
.empty-state {
  text-align: center;
  padding: 3rem 2rem;
}

.empty-state-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.empty-state h3 {
  margin: 0 0 0.5rem;
  color: #e2e8f0;
}

/* ── Server grid ── */
.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.server-card {
  background: #1a2332;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 0.5rem;
  padding: 1rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.server-card:hover {
  background: #1e2d42;
  border-color: rgba(59,130,246,0.4);
}

.server-card--active {
  border-color: #3b82f6 !important;
  background: #1e2d42 !important;
}

.server-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.server-card-title {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
}

.server-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.server-card-stats {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.stat-pill {
  background: rgba(255,255,255,0.05);
  border-radius: 0.3rem;
  padding: 0.2rem 0.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}

.stat-label {
  font-size: 0.65rem;
  text-transform: uppercase;
  color: #7a8fa8;
  letter-spacing: 0.04em;
}

.stat-value {
  font-size: 1rem;
  font-weight: 600;
  color: #e2e8f0;
}

/* ── Status dot ── */
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-block;
}

.status-dot--ok { background: #22c55e; }
.status-dot--unknown { background: #6b7280; }
.status-dot--error { background: #ef4444; }

/* ── Tabs ── */
.tab-bar {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  flex-wrap: wrap;
}

.tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #8a9ab8;
  padding: 0.55rem 1rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
}

.tab-btn:hover { color: #c0cfe4; }

.tab-btn--active {
  color: #60a5fa;
  border-bottom-color: #3b82f6;
  font-weight: 500;
}

/* ── Overview grid ── */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0;
}

.overview-item {
  padding: 0.85rem 1.1rem;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  border-right: 1px solid rgba(255,255,255,0.04);
}

.overview-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #7a8fa8;
  display: block;
  margin-bottom: 0.25rem;
}

.overview-value {
  font-size: 0.9rem;
  color: #e2e8f0;
  font-weight: 500;
  word-break: break-all;
}

/* ── Job cards grid ── */
.job-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.75rem;
  padding: 1rem;
}

.job-card {
  background: #0f1419;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 0.4rem;
  padding: 0.8rem;
  border-left: 3px solid #6b7280;
}

.job-card--ok    { border-left-color: #22c55e; }
.job-card--warning { border-left-color: #f59e0b; }
.job-card--failed  { border-left-color: #ef4444; }
.job-card--unknown { border-left-color: #6b7280; }

.job-card-header {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.job-icon { font-size: 1.1rem; flex-shrink: 0; }

.job-card-info { flex: 1; min-width: 0; }

.job-card-meta { margin-bottom: 0.6rem; }
.job-card-meta > div { margin-bottom: 0.15rem; }

.job-card-actions { display: flex; gap: 0.5rem; }

/* ── Status badges ── */
.job-status-badge {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 0.2rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
  flex-shrink: 0;
}

.job-type-pill { display: inline-block; font-size: 0.65rem; font-weight: 700; padding: 0 4px; border-radius: 3px; background: rgba(99,102,241,0.15); color: #a5b4fc; margin-right: 4px; letter-spacing: 0.03em; }
.job-status-badge--ok      { background: rgba(34,197,94,0.15);  color: #4ade80; }
.job-status-badge--warning { background: rgba(245,158,11,0.15); color: #fbbf24; }
.job-status-badge--failed  { background: rgba(239,68,68,0.15);  color: #f87171; }
.job-status-badge--unknown { background: rgba(107,114,128,0.15); color: #9ca3af; }
.job-status-badge--running { background: rgba(59,130,246,0.15); color: #60a5fa; }

/* ── Datastores grid ── */
.ds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.75rem;
  padding: 1rem;
}

.ds-card {
  background: #0f1419;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 0.4rem;
  padding: 1rem;
}

.ds-card-header {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  margin-bottom: 0.75rem;
}

.ds-icon { font-size: 1.4rem; flex-shrink: 0; }

.ds-usage { margin-bottom: 0.5rem; }

.ds-usage-bar-wrap {
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.3rem;
}

.ds-usage-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.ds-usage-bar--ok      { background: #22c55e; }
.ds-usage-bar--warning { background: #f59e0b; }
.ds-usage-bar--danger  { background: #ef4444; }

.ds-usage-labels {
  display: flex;
  justify-content: space-between;
}

.ds-card-meta > div { margin-bottom: 0.15rem; }

.ds-card--clickable {
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.ds-card--clickable:hover {
  border-color: rgba(59,130,246,0.5);
  background: #141e2e;
}
.ds-browse-hint {
  margin-left: auto;
  flex-shrink: 0;
  opacity: 0.5;
}

/* ── Browse Groups ── */
.browse-group {
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.browse-group:last-child { border-bottom: none; }

.browse-group-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1rem;
  cursor: pointer;
  user-select: none;
  transition: background 0.1s;
}
.browse-group-header:hover { background: rgba(255,255,255,0.03); }

.browse-group-expand { color: #7a8fa8; font-size: 0.65rem; flex-shrink: 0; }

.browse-group-type-pill {
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  background: rgba(99,102,241,0.15);
  color: #a5b4fc;
  flex-shrink: 0;
}

.browse-group-id { font-size: 0.9rem; color: #e2e8f0; }

.browse-group-actions {
  margin-left: auto;
  display: flex;
  gap: 0.35rem;
}

.browse-snapshots {
  background: rgba(0,0,0,0.2);
  border-top: 1px solid rgba(255,255,255,0.04);
  padding: 0.5rem 1rem 1rem 2.5rem;
}

.ml-1 { margin-left: 0.35rem; }

/* ── Table ── */
.table-container { overflow-x: auto; }

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.table th {
  text-align: left;
  padding: 0.6rem 0.9rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #7a8fa8;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  white-space: nowrap;
}

.table td {
  padding: 0.65rem 0.9rem;
  color: #c0cfe4;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  vertical-align: middle;
}

.table tbody tr:hover {
  background: rgba(255,255,255,0.03);
}

/* ── Buttons ── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.45rem 0.9rem;
  border-radius: 0.35rem;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: background 0.15s, opacity 0.15s;
  text-decoration: none;
  white-space: nowrap;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary  { background: #2563eb; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #1d4ed8; }

.btn-outline  { background: transparent; color: #c0cfe4; border: 1px solid rgba(255,255,255,0.2); }
.btn-outline:hover:not(:disabled) { background: rgba(255,255,255,0.07); }

.btn-danger   { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
.btn-danger:hover:not(:disabled) { background: rgba(239,68,68,0.25); }

.btn-sm  { padding: 0.3rem 0.65rem; font-size: 0.8rem; }
.btn-xs  { padding: 0.2rem 0.5rem;  font-size: 0.75rem; }

/* ── Modal ── */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 1rem;
}

.modal-content {
  background: #1a2332;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 0.5rem;
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.9rem 1.1rem;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.modal-header h3 { margin: 0; font-size: 1rem; color: #e2e8f0; }

.modal-body { padding: 1.1rem; }

.btn-close {
  background: none;
  border: none;
  color: #8a9ab8;
  font-size: 1.2rem;
  cursor: pointer;
  line-height: 1;
  padding: 0.1rem 0.3rem;
  border-radius: 0.2rem;
}
.btn-close:hover { color: #e2e8f0; background: rgba(255,255,255,0.07); }

/* ── Form controls ── */
.form-group { margin-bottom: 1rem; }

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.form-label {
  display: block;
  font-size: 0.8rem;
  font-weight: 500;
  color: #a0b0c8;
  margin-bottom: 0.3rem;
}

.required { color: #f87171; }

.form-control {
  width: 100%;
  background: #0f1419;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 0.3rem;
  color: #e2e8f0;
  padding: 0.45rem 0.7rem;
  font-size: 0.875rem;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  color: #c0cfe4;
  font-size: 0.875rem;
}

/* ── Error/result banners ── */
.error-banner {
  background: rgba(239,68,68,0.1);
  border: 1px solid rgba(239,68,68,0.3);
  color: #f87171;
  border-radius: 0.35rem;
  padding: 0.6rem 0.9rem;
  font-size: 0.875rem;
}

.job-run-result {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  background: #1e2d42;
  border: 1px solid rgba(59,130,246,0.4);
  border-radius: 0.4rem;
  color: #c0cfe4;
  padding: 0.65rem 1rem;
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  z-index: 1000;
  max-width: 420px;
}

.btn-close-sm {
  background: none;
  border: none;
  color: #7a8fa8;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0.1rem;
  flex-shrink: 0;
}
.btn-close-sm:hover { color: #e2e8f0; }

/* ── Utility ── */
.loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(255,255,255,0.08);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin: 1.5rem auto;
}

@keyframes spin { to { transform: rotate(360deg); } }

.cron-text {
  font-family: monospace;
  font-size: 0.8rem;
  background: rgba(255,255,255,0.06);
  padding: 0.1rem 0.35rem;
  border-radius: 0.2rem;
  color: #93c5fd;
}

.text-mono { font-family: monospace; }
.text-muted { color: #7a8fa8; }
.text-success { color: #4ade80; }
.text-danger  { color: #f87171; }
.text-sm  { font-size: 0.875rem; }
.text-xs  { font-size: 0.75rem; }
.text-center { text-align: center; }
.p-2  { padding: 0.75rem 1.1rem; }
.mt-1 { margin-top: 0.4rem; }
.mt-2 { margin-top: 0.9rem; }
.mb-2 { margin-bottom: 0.9rem; }
.mb-3 { margin-bottom: 1.25rem; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.align-center { align-items: center; }

@media (max-width: 640px) {
  .pbs-page { padding: 1rem; }
  .form-row { grid-template-columns: 1fr; }
  .server-grid { grid-template-columns: 1fr; }
  .job-cards-grid { grid-template-columns: 1fr; }
  .ds-grid { grid-template-columns: 1fr; }
  .pbs-summary-grid { grid-template-columns: 1fr; }
}

/* ── PBS Summary dashboard cards ── */
.pbs-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 0.9rem;
}

.pbs-summary-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.9rem 1rem 1rem;
  color: var(--text-primary);
}

.pbs-summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.65rem;
}

.pbs-summary-section {
  margin-top: 0.65rem;
  padding-top: 0.65rem;
  border-top: 1px solid var(--border-color);
}

.pbs-summary-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin-bottom: 0.35rem;
}

.pbs-summary-bar-wrap {
  height: 8px;
  background: color-mix(in srgb, var(--text-secondary) 20%, transparent);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.35rem;
}

.pbs-summary-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.pbs-summary-bar--ok      { background: #22c55e; }
.pbs-summary-bar--warning { background: #f59e0b; }
.pbs-summary-bar--danger  { background: #ef4444; }

.pbs-summary-usage-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.4rem;
}

.pbs-summary-jobs {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.pbs-summary-job {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  font-size: 0.75rem;
}

.pbs-summary-job-id {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
}

.pbs-summary-job-when {
  margin-left: auto;
}

.pbs-summary-counts {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.pbs-summary-count-pill {
  background: color-mix(in srgb, var(--text-secondary) 15%, transparent);
  color: var(--text-primary);
  border-radius: 0.25rem;
  padding: 0.15rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
}

.pbs-summary-count-pill--ok {
  background: rgba(34,197,94,0.15);
  color: #4ade80;
}

.pbs-summary-count-pill--failed {
  background: rgba(239,68,68,0.15);
  color: #f87171;
}

.text-warning { color: #d97706; }
[data-theme="dark"] .text-warning { color: #fbbf24; }
</style>
