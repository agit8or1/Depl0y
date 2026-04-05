<template>
  <div class="container-detail-page">
    <!-- Header -->
    <div class="page-header mb-2">
      <div class="header-left">
        <router-link :to="`/proxmox/${hostId}/nodes/${node}`" class="back-link">← {{ node }}</router-link>
        <h2 class="ct-title">
          <span class="ct-os-icon" :title="detectOs(config.hostname || '').name">{{ detectOs(config.hostname || '').icon }}</span>
          {{ config.hostname || `CT ${vmid}` }}
          <span class="badge badge-info ml-1">{{ vmid }}</span>
          <span :class="['badge', 'ml-1', getStatusBadge(currentStats.status || status)]">{{ currentStats.status || status }}</span>
          <span class="badge ml-1" :style="{ background: detectOs(config.hostname || '').color + '22', color: detectOs(config.hostname || '').color, border: '1px solid ' + detectOs(config.hostname || '').color }">{{ detectOs(config.hostname || '').name }}</span>
          <span class="badge badge-info ml-1">CT/LXC</span>
        </h2>
      </div>
      <div class="header-actions flex gap-1 flex-wrap">
        <button @click="action('start')" class="btn btn-success btn-sm"
          :disabled="actioning || (currentStats.status || status) === 'running'">Start</button>
        <button @click="action('shutdown')" class="btn btn-outline btn-sm"
          :disabled="actioning || (currentStats.status || status) !== 'running'" title="Graceful shutdown">Shutdown</button>
        <button @click="action('stop')" class="btn btn-outline btn-sm"
          :disabled="actioning || (currentStats.status || status) !== 'running'" title="Force stop">Stop</button>
        <button @click="action('reboot')" class="btn btn-outline btn-sm"
          :disabled="actioning || (currentStats.status || status) !== 'running'">Reboot</button>
        <button @click="openTerminal" class="btn btn-outline btn-sm">Terminal</button>
        <button @click="openConsoleTab" class="btn btn-outline btn-sm">Console</button>
        <button @click="openCloneModal" class="btn btn-outline btn-sm">Clone</button>
        <router-link
          :to="`/migrate/${hostId}/${node}/${vmid}?type=lxc`"
          class="btn btn-outline btn-sm"
        >Migrate</router-link>
        <button @click="deleteContainer" class="btn btn-danger btn-sm" :disabled="actioning">Delete</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-spinner"></div>

    <template v-else>
      <!-- Tabs -->
      <div class="tabs mb-2">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="switchTab(tab.id)"
          :class="['tab-btn', activeTab === tab.id ? 'tab-btn--active' : '']"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Overview Tab -->
      <div v-if="activeTab === 'overview'">
        <div class="stats-row mb-2">
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">CPU</div>
            <div class="stat-card-sm__value">{{ currentStats.cpu ? (currentStats.cpu * 100).toFixed(1) + '%' : '0%' }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">RAM</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.mem) }} / {{ formatBytes(currentStats.maxmem) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Uptime</div>
            <div class="stat-card-sm__value">{{ formatUptime(currentStats.uptime) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Disk Used</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.disk) }} / {{ formatBytes(currentStats.maxdisk) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Net In</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.netin) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Net Out</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.netout) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Disk Read</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.diskread) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Disk Write</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.diskwrite) }}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h3>Summary</h3></div>
          <div class="card-body">
            <div class="summary-grid">
              <div class="summary-item"><span class="summary-label">Hostname</span><span>{{ config.hostname || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">OS Type</span><span>{{ config.ostype || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Cores</span><span>{{ config.cores || config.cpus || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Memory</span><span>{{ config.memory ? config.memory + ' MB' : '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Swap</span><span>{{ config.swap !== undefined ? config.swap + ' MB' : '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Start on Boot</span><span>{{ config.onboot ? 'Yes' : 'No' }}</span></div>
              <div class="summary-item"><span class="summary-label">Unprivileged</span><span>{{ config.unprivileged ? 'Yes' : 'No' }}</span></div>
              <div class="summary-item"><span class="summary-label">Protection</span><span>{{ config.protection ? 'Yes' : 'No' }}</span></div>
              <div class="summary-item"><span class="summary-label">Root FS</span><span class="text-sm">{{ config.rootfs || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">OS Template</span><span>{{ config.ostemplate || '—' }}</span></div>
              <div v-if="config.tags" class="summary-item" style="grid-column: span 2;">
                <span class="summary-label">Tags</span>
                <div class="tags-row">
                  <span v-for="tag in parsedTags" :key="tag" class="tag-pill">{{ tag }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Console Tab -->
      <div v-if="activeTab === 'console'">
        <div class="card mb-2">
          <div class="card-header"><h3>Container Console</h3></div>
          <div class="card-body" style="text-align:center; padding:2.5rem 1.5rem;">
            <p class="text-muted mb-2">
              Open a noVNC browser console session for CT{{ vmid }} on node <strong>{{ node }}</strong>.
            </p>
            <div class="flex gap-1" style="justify-content:center; flex-wrap:wrap;">
              <button @click="openConsoleWindow" class="btn btn-primary">
                Open Console (noVNC)
              </button>
              <button @click="openTerminal" class="btn btn-outline">
                Open Shell Terminal
              </button>
            </div>
            <p class="text-muted text-sm mt-2">
              Console URL: <code>/console/{{ node }}/{{ vmid }}?type=lxc&hostId={{ hostId }}</code>
            </p>
          </div>
        </div>

        <!-- IP Addresses from config -->
        <div class="card" v-if="parsedNets.length > 0">
          <div class="card-header"><h3>Network Interfaces</h3></div>
          <div class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Interface</th>
                  <th>Name</th>
                  <th>Bridge</th>
                  <th>IP Address</th>
                  <th>Gateway</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="net in parsedNets" :key="net.key">
                  <td><code>{{ net.key }}</code></td>
                  <td>{{ net.name || '—' }}</td>
                  <td>{{ net.bridge || '—' }}</td>
                  <td class="text-sm" style="font-family:monospace;">{{ net.ip || '—' }}</td>
                  <td class="text-sm" style="font-family:monospace;">{{ net.gw || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Configuration Tab -->
      <div v-if="activeTab === 'config'">
        <!-- Inline editable fields -->
        <div class="card mb-2">
          <div class="card-header"><h3>General</h3></div>
          <div class="card-body">
            <div class="inline-edit-grid">

              <!-- Hostname -->
              <div class="inline-edit-row">
                <span class="inline-edit-label">Hostname</span>
                <div class="inline-edit-control">
                  <input v-model="inlineEdit.hostname" class="form-control form-control-sm" />
                  <button @click="saveInlineField('hostname', inlineEdit.hostname)"
                    class="btn btn-primary btn-sm" :disabled="savingField.hostname">
                    {{ savingField.hostname ? 'Saving…' : 'Save' }}
                  </button>
                </div>
              </div>

              <!-- Cores -->
              <div class="inline-edit-row">
                <span class="inline-edit-label">CPUs (cores)</span>
                <div class="inline-edit-control">
                  <input v-model.number="inlineEdit.cores" type="number" min="1" class="form-control form-control-sm" style="width:90px;" />
                  <button @click="saveInlineField('cores', inlineEdit.cores)"
                    class="btn btn-primary btn-sm" :disabled="savingField.cores">
                    {{ savingField.cores ? 'Saving…' : 'Save' }}
                  </button>
                </div>
              </div>

              <!-- Memory -->
              <div class="inline-edit-row">
                <span class="inline-edit-label">Memory (MB)</span>
                <div class="inline-edit-control">
                  <input v-model.number="inlineEdit.memory" type="number" min="16" step="16" class="form-control form-control-sm" style="width:110px;" />
                  <button @click="saveInlineField('memory', inlineEdit.memory)"
                    class="btn btn-primary btn-sm" :disabled="savingField.memory">
                    {{ savingField.memory ? 'Saving…' : 'Save' }}
                  </button>
                </div>
              </div>

              <!-- Swap -->
              <div class="inline-edit-row">
                <span class="inline-edit-label">Swap (MB)</span>
                <div class="inline-edit-control">
                  <input v-model.number="inlineEdit.swap" type="number" min="0" step="16" class="form-control form-control-sm" style="width:110px;" />
                  <button @click="saveInlineField('swap', inlineEdit.swap)"
                    class="btn btn-primary btn-sm" :disabled="savingField.swap">
                    {{ savingField.swap ? 'Saving…' : 'Save' }}
                  </button>
                </div>
              </div>

              <!-- Disk size / rootfs -->
              <div class="inline-edit-row">
                <span class="inline-edit-label">Disk (rootfs)</span>
                <div class="inline-edit-control">
                  <span class="config-value-inline text-sm">{{ config.rootfs || '—' }}</span>
                  <button @click="openResizeModal('rootfs')" class="btn btn-outline btn-sm">Resize</button>
                </div>
              </div>

            </div>
          </div>
        </div>

        <!-- Full config edit -->
        <div class="card">
          <div class="card-header">
            <h3>Container Configuration</h3>
            <div class="flex gap-1">
              <button v-if="!editMode" @click="enterEditMode" class="btn btn-outline btn-sm">Edit All</button>
              <template v-else>
                <button @click="saveConfig" class="btn btn-primary btn-sm" :disabled="savingConfig">
                  {{ savingConfig ? 'Saving...' : 'Save' }}
                </button>
                <button @click="cancelEdit" class="btn btn-outline btn-sm">Cancel</button>
              </template>
            </div>
          </div>
          <div class="card-body">
            <div class="config-grid">
              <div class="form-group">
                <label class="form-label">Hostname</label>
                <input v-if="editMode" v-model="editConfig.hostname" class="form-control" />
                <div v-else class="config-value">{{ config.hostname || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Cores</label>
                <input v-if="editMode" v-model.number="editConfig.cores" type="number" min="1" class="form-control" />
                <div v-else class="config-value">{{ config.cores || config.cpus || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Memory (MB)</label>
                <input v-if="editMode" v-model.number="editConfig.memory" type="number" min="16" step="16" class="form-control" />
                <div v-else class="config-value">{{ config.memory ? config.memory + ' MB' : '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Swap (MB)</label>
                <input v-if="editMode" v-model.number="editConfig.swap" type="number" min="0" step="16" class="form-control" />
                <div v-else class="config-value">{{ config.swap !== undefined ? config.swap + ' MB' : '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Root Filesystem</label>
                <div class="config-value text-sm">{{ config.rootfs || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Startup</label>
                <input v-if="editMode" v-model="editConfig.startup" class="form-control" placeholder="order=1,up=10" />
                <div v-else class="config-value">{{ config.startup || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Tags</label>
                <input v-if="editMode" v-model="editConfig.tags" class="form-control" placeholder="tag1;tag2" />
                <div v-else class="config-value">{{ config.tags || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">
                  <input v-if="editMode" type="checkbox" v-model="editConfig.onboot" :true-value="1" :false-value="0" />
                  <input v-else type="checkbox" :checked="!!config.onboot" disabled />
                  Start on Boot
                </label>
              </div>
              <div class="form-group">
                <label class="form-label">
                  <input v-if="editMode" type="checkbox" v-model="editConfig.unprivileged" :true-value="1" :false-value="0" />
                  <input v-else type="checkbox" :checked="!!config.unprivileged" disabled />
                  Unprivileged Container
                </label>
              </div>
              <div class="form-group">
                <label class="form-label">
                  <input v-if="editMode" type="checkbox" v-model="editConfig.protection" :true-value="1" :false-value="0" />
                  <input v-else type="checkbox" :checked="!!config.protection" disabled />
                  Protection (prevents deletion)
                </label>
              </div>
              <div class="form-group" style="grid-column: span 2;">
                <label class="form-label">Description</label>
                <textarea v-if="editMode" v-model="editConfig.description" class="form-control" rows="3"></textarea>
                <div v-else class="config-value" style="height: auto; min-height: 3rem; white-space: pre-wrap;">{{ config.description || '—' }}</div>
              </div>
            </div>

            <!-- Network Interfaces -->
            <div class="section-title mt-2 mb-1">Network Interfaces</div>
            <div v-if="parsedNets.length === 0" class="text-muted text-sm mb-2">No network interfaces configured.</div>
            <div v-else class="table-container mb-2">
              <table class="table">
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>Name</th>
                    <th>Bridge</th>
                    <th>IP</th>
                    <th>Gateway</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="net in parsedNets" :key="net.key">
                    <td><code>{{ net.key }}</code></td>
                    <td>{{ net.name || '—' }}</td>
                    <td>{{ net.bridge || '—' }}</td>
                    <td class="text-sm">{{ net.ip || '—' }}</td>
                    <td class="text-sm">{{ net.gw || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Full raw config -->
            <div class="section-title mt-2 mb-1">Full Configuration</div>
            <div class="raw-config-table">
              <div v-for="(val, key) in config" :key="key" class="raw-config-row">
                <span class="raw-config-key">{{ key }}</span>
                <span class="raw-config-val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Limits Tab -->
      <div v-if="activeTab === 'limits'">
        <div class="card">
          <div class="card-header"><h3>Resource Limits</h3></div>
          <div class="card-body">
            <div class="limits-grid">
              <div class="limit-row">
                <div class="limit-label-col">
                  <span class="limit-label">CPU Weight</span>
                  <span class="limit-hint">cpuunits — relative scheduling weight (8–512)</span>
                </div>
                <div class="limit-control-col">
                  <div class="slider-row">
                    <input v-model.number="limitsEdit.cpuunits" type="range" min="8" max="512" step="8" class="range-slider" />
                    <input v-model.number="limitsEdit.cpuunits" type="number" min="8" max="512" step="8" class="form-control form-control-sm" style="width:80px;" />
                  </div>
                  <button @click="saveLimitField('cpuunits', limitsEdit.cpuunits)" class="btn btn-primary btn-sm" :disabled="savingLimit.cpuunits">
                    {{ savingLimit.cpuunits ? 'Saving…' : 'Save' }}
                  </button>
                </div>
              </div>
              <div class="limit-row">
                <div class="limit-label-col">
                  <span class="limit-label">CPU Limit</span>
                  <span class="limit-hint">cpulimit — max CPU usage (0 = unlimited)</span>
                </div>
                <div class="limit-control-col">
                  <input v-model.number="limitsEdit.cpulimit" type="number" min="0" max="128" step="0.5" class="form-control form-control-sm" style="width:110px;" placeholder="0" />
                  <button @click="saveLimitField('cpulimit', limitsEdit.cpulimit)" class="btn btn-primary btn-sm" :disabled="savingLimit.cpulimit">
                    {{ savingLimit.cpulimit ? 'Saving…' : 'Save' }}
                  </button>
                </div>
              </div>
              <div class="limit-row">
                <div class="limit-label-col">
                  <span class="limit-label">Memory Swap (MB)</span>
                  <span class="limit-hint">swap — allocated swap space</span>
                </div>
                <div class="limit-control-col">
                  <input v-model.number="limitsEdit.swap" type="number" min="0" step="16" class="form-control form-control-sm" style="width:110px;" />
                  <button @click="saveLimitField('swap', limitsEdit.swap)" class="btn btn-primary btn-sm" :disabled="savingLimit.swap">
                    {{ savingLimit.swap ? 'Saving…' : 'Save' }}
                  </button>
                </div>
              </div>
              <div class="limit-row">
                <div class="limit-label-col">
                  <span class="limit-label">Disk Quota</span>
                  <span class="limit-hint">quota — enable/disable disk quota enforcement</span>
                </div>
                <div class="limit-control-col">
                  <label class="toggle-label">
                    <input v-model.number="limitsEdit.quota" type="checkbox" :true-value="1" :false-value="0" />
                    <span>{{ limitsEdit.quota ? 'Enabled' : 'Disabled' }}</span>
                  </label>
                  <button @click="saveLimitField('quota', limitsEdit.quota)" class="btn btn-primary btn-sm" :disabled="savingLimit.quota">
                    {{ savingLimit.quota ? 'Saving…' : 'Save' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Bind Mounts Tab -->
      <div v-if="activeTab === 'mounts'">
        <div class="card">
          <div class="card-header">
            <h3>Bind Mount Points</h3>
            <button @click="showMountModal = true" class="btn btn-primary btn-sm">+ Add Mount Point</button>
          </div>
          <div v-if="parsedMounts.length === 0" class="text-center text-muted" style="padding:2rem;">
            <p>No bind mount points configured (mp0, mp1, …).</p>
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Volume</th>
                  <th>Mount Path</th>
                  <th>Size</th>
                  <th>ACL</th>
                  <th>Quota</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="mp in parsedMounts" :key="mp.key">
                  <td><code>{{ mp.key }}</code></td>
                  <td class="text-sm">{{ mp.volume || '—' }}</td>
                  <td class="text-sm">{{ mp.mp || '—' }}</td>
                  <td class="text-sm">{{ mp.size || '—' }}</td>
                  <td class="text-sm">{{ mp.acl ? 'Yes' : 'No' }}</td>
                  <td class="text-sm">{{ mp.quota ? 'Yes' : 'No' }}</td>
                  <td>
                    <div class="flex gap-1">
                      <button @click="openMountResizeModal(mp)" class="btn btn-outline btn-sm">Resize</button>
                      <button @click="removeMountPoint(mp.key)" class="btn btn-danger btn-sm" :disabled="actioning">Remove</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Snapshots Tab -->
      <div v-if="activeTab === 'snapshots'">
        <div class="card">
          <div class="card-header">
            <h3>Snapshots</h3>
            <button @click="showSnapshotModal = true" class="btn btn-primary btn-sm">+ Create Snapshot</button>
          </div>

          <div v-if="loadingSnapshots" class="loading-spinner"></div>

          <div v-else-if="snapshots.length === 0" class="text-center text-muted" style="padding: 2rem;">
            <p>No snapshots found.</p>
          </div>

          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Parent</th>
                  <th>Description</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="snap in snapshots" :key="snap.name">
                  <td><strong>{{ snap.name }}</strong></td>
                  <td class="text-sm text-muted">{{ snap.parent || '—' }}</td>
                  <td class="text-sm text-muted">{{ snap.description || '—' }}</td>
                  <td class="text-sm">{{ snap.snaptime ? formatDate(snap.snaptime) : '—' }}</td>
                  <td>
                    <div v-if="snap.name !== 'current'" class="flex gap-1">
                      <button @click="rollbackSnapshot(snap.name)" class="btn btn-outline btn-sm" :disabled="actioning">Rollback</button>
                      <button @click="deleteSnapshot(snap.name)" class="btn btn-danger btn-sm" :disabled="actioning">Delete</button>
                    </div>
                    <span v-else class="text-muted text-sm">current</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Backup Tab -->
      <div v-if="activeTab === 'backup'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>Create Backup</h3>
          </div>
          <div class="card-body">
            <div class="backup-form-row">
              <div class="form-group" style="flex:1;min-width:180px;">
                <label class="form-label">Storage</label>
                <input v-model="backupForm.storage" class="form-control" placeholder="local" />
              </div>
              <div class="form-group" style="flex:1;min-width:180px;">
                <label class="form-label">Mode</label>
                <select v-model="backupForm.mode" class="form-control">
                  <option value="snapshot">Snapshot</option>
                  <option value="suspend">Suspend</option>
                  <option value="stop">Stop</option>
                </select>
              </div>
              <div class="form-group" style="flex:1;min-width:180px;">
                <label class="form-label">Compression</label>
                <select v-model="backupForm.compress" class="form-control">
                  <option value="zstd">zstd</option>
                  <option value="lzo">lzo</option>
                  <option value="gzip">gzip</option>
                  <option value="0">None</option>
                </select>
              </div>
              <div class="form-group" style="align-self:flex-end;">
                <button @click="runBackupNow" class="btn btn-primary" :disabled="runningBackup">
                  {{ runningBackup ? 'Starting…' : 'Backup Now' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>Existing Backups</h3>
            <button @click="fetchBackups" class="btn btn-outline btn-sm" :disabled="loadingBackups">
              {{ loadingBackups ? 'Loading…' : 'Refresh' }}
            </button>
          </div>
          <div v-if="loadingBackups" class="loading-spinner"></div>
          <div v-else-if="backups.length === 0" class="text-center text-muted" style="padding:2rem;">
            <p>No backups found for this container across configured storages.</p>
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Storage</th>
                  <th>Size</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="bk in backups" :key="bk.volid">
                  <td class="text-sm">{{ bk.volid.split('/').pop() }}</td>
                  <td class="text-sm">{{ bk._storage }}</td>
                  <td class="text-sm">{{ formatBytes(bk.size) }}</td>
                  <td class="text-sm">{{ bk.ctime ? formatDate(bk.ctime) : '—' }}</td>
                  <td>
                    <button @click="openRestoreModal(bk)" class="btn btn-outline btn-sm">Restore</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Performance Tab -->
      <div v-if="activeTab === 'performance'">
        <div class="card">
          <div class="card-header">
            <h3>Performance</h3>
            <div class="flex gap-1 align-center">
              <div class="btn-group">
                <button v-for="tf in timeframes" :key="tf.value"
                  :class="['btn', 'btn-sm', rrdTimeframe === tf.value ? 'btn-primary' : 'btn-outline']"
                  @click="rrdTimeframe = tf.value; fetchRrdData()">
                  {{ tf.label }}
                </button>
              </div>
              <button @click="fetchRrdData" class="btn btn-outline btn-sm" :disabled="loadingRrd">
                {{ loadingRrd ? 'Loading...' : 'Refresh' }}
              </button>
            </div>
          </div>
          <div class="card-body">
            <div v-if="loadingRrd" class="loading-spinner"></div>
            <div v-else-if="rrdData.length === 0" class="text-center text-muted" style="padding:2rem;">
              <p>No performance data available.</p>
            </div>
            <div v-else>
              <!-- Charts grid using PerformanceCharts component -->
              <div class="charts-grid">
                <div class="chart-card">
                  <div class="chart-card__title">CPU Usage</div>
                  <PerformanceCharts
                    :data="rrdChartData('cpu', true)"
                    label="CPU" unit="%" color="#3b82f6" :height="120"
                  />
                </div>
                <div class="chart-card">
                  <div class="chart-card__title">Memory Usage</div>
                  <PerformanceCharts
                    :data="rrdChartData('mem_pct', false)"
                    label="Memory" unit="%" color="#8b5cf6" :height="120"
                  />
                </div>
                <div class="chart-card">
                  <div class="chart-card__title">Network In</div>
                  <PerformanceCharts
                    :data="rrdChartData('netin')"
                    label="Net In" unit="B/s" color="#22c55e" :height="120"
                  />
                </div>
                <div class="chart-card">
                  <div class="chart-card__title">Network Out</div>
                  <PerformanceCharts
                    :data="rrdChartData('netout')"
                    label="Net Out" unit="B/s" color="#f59e0b" :height="120"
                  />
                </div>
                <div class="chart-card">
                  <div class="chart-card__title">Disk Read</div>
                  <PerformanceCharts
                    :data="rrdChartData('diskread')"
                    label="Disk Read" unit="B/s" color="#06b6d4" :height="120"
                  />
                </div>
                <div class="chart-card">
                  <div class="chart-card__title">Disk Write</div>
                  <PerformanceCharts
                    :data="rrdChartData('diskwrite')"
                    label="Disk Write" unit="B/s" color="#ef4444" :height="120"
                  />
                </div>
              </div>

              <!-- Latest stats summary -->
              <div v-if="rrdPoint" class="perf-grid mt-2">
                <div class="perf-card">
                  <div class="perf-card__label">CPU Usage</div>
                  <div class="perf-card__value">{{ rrdPoint.cpu != null ? (rrdPoint.cpu * 100).toFixed(2) + '%' : '—' }}</div>
                  <div class="perf-bar-track"><div class="perf-bar-fill" :style="{ width: rrdPoint.cpu != null ? Math.min(rrdPoint.cpu * 100, 100).toFixed(1) + '%' : '0%', background: cpuBarColor }"></div></div>
                </div>
                <div class="perf-card">
                  <div class="perf-card__label">Memory</div>
                  <div class="perf-card__value">{{ formatBytes(rrdPoint.mem) }} / {{ formatBytes(rrdPoint.maxmem) }}</div>
                  <div class="perf-bar-track"><div class="perf-bar-fill" :style="{ width: memPct + '%', background: memBarColor }"></div></div>
                  <div class="perf-card__sub">{{ memPct.toFixed(1) }}% used</div>
                </div>
                <div class="perf-card">
                  <div class="perf-card__label">Network In</div>
                  <div class="perf-card__value">{{ formatRateBytes(rrdPoint.netin) }}/s</div>
                </div>
                <div class="perf-card">
                  <div class="perf-card__label">Network Out</div>
                  <div class="perf-card__value">{{ formatRateBytes(rrdPoint.netout) }}/s</div>
                </div>
                <div class="perf-card">
                  <div class="perf-card__label">Disk Read</div>
                  <div class="perf-card__value">{{ formatRateBytes(rrdPoint.diskread) }}/s</div>
                </div>
                <div class="perf-card">
                  <div class="perf-card__label">Disk Write</div>
                  <div class="perf-card__value">{{ formatRateBytes(rrdPoint.diskwrite) }}/s</div>
                </div>
              </div>
              <div class="text-muted text-sm mt-2" style="text-align:right;">
                Latest data: {{ rrdPoint && rrdPoint.time ? new Date(rrdPoint.time * 1000).toLocaleString() : 'unknown' }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Terminal Tab -->
      <div v-if="activeTab === 'terminal'">
        <div class="card">
          <div class="card-header"><h3>Container Terminal</h3></div>
          <div class="card-body text-center" style="padding: 2rem;">
            <p class="text-muted mb-2">Open an interactive shell session for this LXC container.</p>
            <button @click="openTerminal" class="btn btn-primary">Open Terminal</button>
            <p class="text-muted text-sm mt-2">
              Navigates to the Depl0y terminal viewer
              (<code>/proxmox/{{ hostId }}/nodes/{{ node }}/terminal?lxc={{ vmid }}</code>)
            </p>
          </div>
        </div>
      </div>

      <!-- Firewall Tab -->
      <div v-if="activeTab === 'firewall'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>Firewall Options</h3>
          </div>
          <div class="card-body">
            <div v-if="loadingFwOptions" class="loading-spinner"></div>
            <div v-else class="fw-options-row">
              <label class="toggle-label">
                <input type="checkbox"
                  :checked="fwOptions.enable == 1 || fwOptions.enable === true"
                  @change="toggleContainerFirewall($event.target.checked)"
                  :disabled="savingFwOptions"
                />
                <span style="margin-left:0.5rem;font-weight:500;">
                  Firewall {{ (fwOptions.enable == 1 || fwOptions.enable === true) ? 'Enabled' : 'Disabled' }}
                </span>
              </label>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>Firewall Rules</h3>
            <button @click="openFwRuleModal()" class="btn btn-primary btn-sm">+ Add Rule</button>
          </div>
          <div v-if="loadingFwRules" class="loading-spinner"></div>
          <div v-else-if="fwRules.length === 0" class="text-center text-muted" style="padding:2rem;">
            <p>No firewall rules configured.</p>
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Pos</th>
                  <th>En</th>
                  <th>Direction</th>
                  <th>Action</th>
                  <th>Proto</th>
                  <th>Source</th>
                  <th>Dest</th>
                  <th>Port</th>
                  <th>Comment</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="rule in fwRules" :key="rule.pos">
                  <td class="text-sm">{{ rule.pos }}</td>
                  <td>
                    <span :class="rule.enable == 1 || rule.enable === true ? 'badge badge-success' : 'badge badge-secondary'">
                      {{ rule.enable == 1 || rule.enable === true ? 'On' : 'Off' }}
                    </span>
                  </td>
                  <td class="text-sm">{{ rule.type || '—' }}</td>
                  <td class="text-sm"><strong>{{ rule.action || '—' }}</strong></td>
                  <td class="text-sm">{{ rule.proto || '—' }}</td>
                  <td class="text-sm">{{ rule.source || '—' }}</td>
                  <td class="text-sm">{{ rule.dest || '—' }}</td>
                  <td class="text-sm">{{ rule.dport || rule.sport || '—' }}</td>
                  <td class="text-sm text-muted">{{ rule.comment || '—' }}</td>
                  <td>
                    <div class="flex gap-1">
                      <button @click="openFwRuleModal(rule)" class="btn btn-outline btn-sm">Edit</button>
                      <button @click="deleteFwRule(rule.pos)" class="btn btn-danger btn-sm">Del</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- Clone LXC Modal -->
    <div v-if="showCloneModal" class="modal" @click="showCloneModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Clone Container CT{{ vmid }}</h3>
          <button @click="showCloneModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitClone" class="modal-body">
          <div class="form-group">
            <label class="form-label">New CT ID</label>
            <input v-model.number="cloneForm.newid" type="number" min="100" class="form-control" required :disabled="loadingNextId" />
            <div v-if="loadingNextId" class="text-muted text-sm mt-1">Loading next available ID…</div>
          </div>
          <div class="form-group">
            <label class="form-label">Hostname</label>
            <input v-model="cloneForm.hostname" type="text" class="form-control" placeholder="new-container" />
          </div>
          <div class="form-group">
            <label class="form-label">Target Node</label>
            <select v-model="cloneForm.target" class="form-control">
              <option value="">Same node ({{ node }})</option>
              <option v-for="n in pveNodes" :key="n.name" :value="n.name">{{ n.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Storage (optional)</label>
            <input v-model="cloneForm.storage" type="text" class="form-control" placeholder="e.g. local-lvm" />
          </div>
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input type="checkbox" v-model="cloneForm.full" style="margin-right:0.5rem;" />
              Full Clone (uncheck for linked clone)
            </label>
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="cloningLxc">
              {{ cloningLxc ? 'Cloning…' : 'Clone' }}
            </button>
            <button type="button" @click="showCloneModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create Snapshot Modal -->
    <div v-if="showSnapshotModal" class="modal" @click="showSnapshotModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Snapshot</h3>
          <button @click="showSnapshotModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="createSnapshot" class="modal-body">
          <div class="form-group">
            <label class="form-label">Snapshot Name</label>
            <input v-model="newSnapshot.snapname" class="form-control" placeholder="snap1" required />
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <input v-model="newSnapshot.description" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingSnapshot">
              {{ savingSnapshot ? 'Creating...' : 'Create' }}
            </button>
            <button type="button" @click="showSnapshotModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Resize Disk Modal -->
    <div v-if="showResizeModal" class="modal" @click="showResizeModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Resize {{ resizeDiskKey }} — CT{{ vmid }}</h3>
          <button @click="showResizeModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Current disk key</label>
            <div class="config-value text-sm">{{ resizeDiskKey }}</div>
          </div>
          <div class="form-group">
            <label class="form-label">Additional space (e.g. +5G, +500M)</label>
            <input
              v-model="resizeAmount"
              class="form-control"
              placeholder="+5G"
              pattern="^\+[0-9]+[KMGT]$"
              title="Must start with + followed by a number and unit (K, M, G, T)"
            />
            <div class="text-muted text-sm mt-1">Use format: +5G, +500M, +1T — must be an increase</div>
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="submitResize" class="btn btn-primary" :disabled="resizing || !resizeAmount">
              {{ resizing ? 'Resizing…' : 'Resize' }}
            </button>
            <button @click="showResizeModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Mount Point Modal -->
    <div v-if="showMountModal" class="modal" @click="showMountModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Mount Point</h3>
          <button @click="showMountModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="addMountPoint" class="modal-body">
          <div class="form-group">
            <label class="form-label">Mount Key (mp0, mp1, …)</label>
            <input v-model="mountForm.key" class="form-control" placeholder="mp0" required />
          </div>
          <div class="form-group">
            <label class="form-label">Storage</label>
            <input v-model="mountForm.storage" class="form-control" placeholder="local-lvm" required />
          </div>
          <div class="form-group">
            <label class="form-label">Size (e.g. 10G)</label>
            <input v-model="mountForm.size" class="form-control" placeholder="10G" required />
          </div>
          <div class="form-group">
            <label class="form-label">Mount Path (inside container)</label>
            <input v-model="mountForm.mp" class="form-control" placeholder="/mnt/data" required />
          </div>
          <div class="form-group">
            <label class="toggle-label">
              <input type="checkbox" v-model="mountForm.acl" />
              <span style="margin-left:0.5rem;">Enable ACL</span>
            </label>
          </div>
          <div class="form-group">
            <label class="toggle-label">
              <input type="checkbox" v-model="mountForm.quota" />
              <span style="margin-left:0.5rem;">Enable Quota</span>
            </label>
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingMount">
              {{ savingMount ? 'Adding…' : 'Add' }}
            </button>
            <button type="button" @click="showMountModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Restore Backup Modal -->
    <div v-if="showRestoreModal" class="modal" @click="showRestoreModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Restore Backup</h3>
          <button @click="showRestoreModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitRestore" class="modal-body">
          <div class="form-group">
            <label class="form-label">Backup File</label>
            <div class="config-value text-sm">{{ restoreForm.volid }}</div>
          </div>
          <div class="form-group">
            <label class="form-label">Target CT ID</label>
            <input v-model.number="restoreForm.newid" type="number" min="100" class="form-control" required />
          </div>
          <div class="form-group">
            <label class="form-label">Target Storage</label>
            <input v-model="restoreForm.storage" class="form-control" placeholder="local-lvm" />
          </div>
          <div class="form-group">
            <label class="toggle-label">
              <input type="checkbox" v-model="restoreForm.start" />
              <span style="margin-left:0.5rem;">Start after restore</span>
            </label>
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="restoringBackup">
              {{ restoringBackup ? 'Restoring…' : 'Restore' }}
            </button>
            <button type="button" @click="showRestoreModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Firewall Rule Modal -->
    <div v-if="showFwRuleModal" class="modal" @click="showFwRuleModal = false">
      <div class="modal-content" style="max-width:600px;" @click.stop>
        <div class="modal-header">
          <h3>{{ fwRuleEdit.pos !== undefined ? 'Edit' : 'Add' }} Firewall Rule</h3>
          <button @click="showFwRuleModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="saveFwRule" class="modal-body">
          <div class="config-grid">
            <div class="form-group">
              <label class="form-label">Direction</label>
              <select v-model="fwRuleEdit.type" class="form-control">
                <option value="in">In</option>
                <option value="out">Out</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Action</label>
              <select v-model="fwRuleEdit.action" class="form-control">
                <option value="ACCEPT">ACCEPT</option>
                <option value="DROP">DROP</option>
                <option value="REJECT">REJECT</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Protocol</label>
              <select v-model="fwRuleEdit.proto" class="form-control">
                <option value="">Any</option>
                <option value="tcp">TCP</option>
                <option value="udp">UDP</option>
                <option value="icmp">ICMP</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Source</label>
              <input v-model="fwRuleEdit.source" class="form-control" placeholder="0.0.0.0/0" />
            </div>
            <div class="form-group">
              <label class="form-label">Dest</label>
              <input v-model="fwRuleEdit.dest" class="form-control" placeholder="optional" />
            </div>
            <div class="form-group">
              <label class="form-label">Dest Port</label>
              <input v-model="fwRuleEdit.dport" class="form-control" placeholder="80,443" />
            </div>
            <div class="form-group">
              <label class="form-label">Comment</label>
              <input v-model="fwRuleEdit.comment" class="form-control" placeholder="optional comment" />
            </div>
            <div class="form-group">
              <label class="toggle-label" style="margin-top:1.5rem;">
                <input type="checkbox" v-model="fwRuleEdit.enable" :true-value="1" :false-value="0" />
                <span style="margin-left:0.5rem;">Enabled</span>
              </label>
            </div>
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingFwRule">
              {{ savingFwRule ? 'Saving…' : 'Save Rule' }}
            </button>
            <button type="button" @click="showFwRuleModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Task Progress Modal -->
    <TaskProgressModal
      :visible="showTaskProgress"
      :upid="taskUpid"
      :host-id="hostId"
      :node="taskProgressNode"
      @close="showTaskProgress = false"
      @success="onTaskSuccess"
      @error="onTaskError"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import { formatBytes, formatUptime } from '@/utils/proxmox'
import { detectOs } from '@/utils/osIcons'
import TaskProgressModal from '@/components/TaskProgressModal.vue'
import PerformanceCharts from '@/components/PerformanceCharts.vue'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const hostId = computed(() => route.params.hostId)
const node = computed(() => route.params.node)
const vmid = computed(() => route.params.vmid)

const status = ref('unknown')
const config = ref({})
const editConfig = ref({})
const currentStats = ref({})
const snapshots = ref([])
const loading = ref(true)
const actioning = ref(false)
const savingConfig = ref(false)
const loadingSnapshots = ref(false)
const showSnapshotModal = ref(false)
const savingSnapshot = ref(false)
const activeTab = ref('overview')
const editMode = ref(false)
const newSnapshot = ref({ snapname: '', description: '' })

// Clone modal state
const showCloneModal = ref(false)
const cloningLxc = ref(false)
const loadingNextId = ref(false)
const pveNodes = ref([])
const cloneForm = ref({ newid: null, hostname: '', target: '', full: true, storage: '' })

// Performance / RRD state
const rrdData = ref([])
const loadingRrd = ref(false)
const rrdTimeframe = ref('hour')
const timeframes = [
  { value: 'hour', label: '1h' },
  { value: 'day', label: '24h' },
  { value: 'week', label: '1w' },
  { value: 'month', label: '1m' },
]

// Inline edit state
const inlineEdit = ref({ hostname: '', cores: 1, memory: 512, swap: 0 })
const savingField = ref({ hostname: false, cores: false, memory: false, swap: false })

// Limits tab state
const limitsEdit = ref({ cpuunits: 1024, cpulimit: 0, swap: 0, quota: 0 })
const savingLimit = ref({ cpuunits: false, cpulimit: false, swap: false, quota: false })

// Resize disk modal state
const showResizeModal = ref(false)
const resizeAmount = ref('')
const resizing = ref(false)
const resizeDiskKey = ref('rootfs')

// Task progress modal
const showTaskProgress = ref(false)
const taskUpid = ref('')
const taskProgressNode = ref('')

// Bind mounts
const showMountModal = ref(false)
const savingMount = ref(false)
const mountForm = ref({ key: 'mp0', storage: '', size: '10G', mp: '/mnt/data', acl: false, quota: false })

// Backup tab
const backups = ref([])
const loadingBackups = ref(false)
const runningBackup = ref(false)
const backupForm = ref({ storage: 'local', mode: 'snapshot', compress: 'zstd' })
const showRestoreModal = ref(false)
const restoringBackup = ref(false)
const restoreForm = ref({ volid: '', newid: null, storage: '', start: false })

// Firewall tab
const fwRules = ref([])
const fwOptions = ref({ enable: 0 })
const loadingFwRules = ref(false)
const loadingFwOptions = ref(false)
const savingFwOptions = ref(false)
const showFwRuleModal = ref(false)
const savingFwRule = ref(false)
const fwRuleEdit = ref({ type: 'in', action: 'ACCEPT', proto: '', source: '', dest: '', dport: '', comment: '', enable: 1 })

let pollInterval = null

const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'console', label: 'Console' },
  { id: 'config', label: 'Config' },
  { id: 'limits', label: 'Limits' },
  { id: 'mounts', label: 'Bind Mounts' },
  { id: 'snapshots', label: 'Snapshots' },
  { id: 'backup', label: 'Backup' },
  { id: 'performance', label: 'Performance' },
  { id: 'firewall', label: 'Firewall' },
  { id: 'terminal', label: 'Terminal' },
]

const NET_KEYS = ['net0', 'net1', 'net2', 'net3', 'net4', 'net5', 'net6', 'net7']
const MOUNT_KEYS = ['mp0', 'mp1', 'mp2', 'mp3', 'mp4', 'mp5', 'mp6', 'mp7']

const parsedNets = computed(() => {
  if (!config.value) return []
  return NET_KEYS
    .filter(k => config.value[k])
    .map(k => {
      const raw = config.value[k]
      const result = { key: k, raw, name: '', bridge: '', ip: '', gw: '' }
      raw.split(',').forEach(part => {
        if (part.startsWith('name=')) result.name = part.slice(5)
        else if (part.startsWith('bridge=')) result.bridge = part.slice(7)
        else if (part.startsWith('ip=')) result.ip = part.slice(3)
        else if (part.startsWith('gw=')) result.gw = part.slice(3)
      })
      return result
    })
})

const parsedMounts = computed(() => {
  if (!config.value) return []
  return MOUNT_KEYS
    .filter(k => config.value[k])
    .map(k => {
      const raw = config.value[k]
      const result = { key: k, raw, volume: '', mp: '', size: '', acl: false, quota: false }
      const parts = raw.split(',')
      // First token is typically storage:volume or just the volume path
      if (parts[0]) result.volume = parts[0]
      parts.forEach(part => {
        if (part.startsWith('mp=')) result.mp = part.slice(3)
        else if (part.startsWith('size=')) result.size = part.slice(5)
        else if (part === 'acl=1') result.acl = true
        else if (part === 'quota=1') result.quota = true
      })
      return result
    })
})

const parsedTags = computed(() => {
  if (!config.value?.tags) return []
  return config.value.tags.split(';').map(t => t.trim()).filter(Boolean)
})

// Sync inlineEdit and limitsEdit when config loads
const syncEditStates = () => {
  inlineEdit.value = {
    hostname: config.value.hostname || '',
    cores: config.value.cores || config.value.cpus || 1,
    memory: config.value.memory || 512,
    swap: config.value.swap !== undefined ? config.value.swap : 0,
  }
  limitsEdit.value = {
    cpuunits: config.value.cpuunits !== undefined ? config.value.cpuunits : 1024,
    cpulimit: config.value.cpulimit !== undefined ? config.value.cpulimit : 0,
    swap: config.value.swap !== undefined ? config.value.swap : 0,
    quota: config.value.quota !== undefined ? config.value.quota : 0,
  }
}

const fetchAll = async () => {
  loading.value = true
  try {
    const [statusRes, configRes] = await Promise.all([
      api.pveNode.getContainerStatus(hostId.value, node.value, vmid.value),
      api.pveNode.getContainerConfig(hostId.value, node.value, vmid.value),
    ])
    currentStats.value = statusRes.data || {}
    status.value = currentStats.value.status || 'unknown'
    config.value = configRes.data || {}
    syncEditStates()
  } catch (error) {
    console.error('Failed to fetch container info:', error)
    toast.error('Failed to load container information')
  } finally {
    loading.value = false
  }
}

const fetchStatus = async () => {
  try {
    const res = await api.pveNode.getContainerStatus(hostId.value, node.value, vmid.value)
    currentStats.value = res.data || {}
    status.value = currentStats.value.status || 'unknown'
  } catch (e) {
    console.warn('CT status poll failed', e)
  }
}

const fetchSnapshots = async () => {
  loadingSnapshots.value = true
  try {
    const response = await api.pveNode.listContainerSnapshots(hostId.value, node.value, vmid.value)
    snapshots.value = response.data || []
  } catch (error) {
    console.error('Failed to fetch snapshots:', error)
  } finally {
    loadingSnapshots.value = false
  }
}

// Backups
const fetchBackups = async () => {
  loadingBackups.value = true
  backups.value = []
  try {
    const storageRes = await api.pveNode.listStorage(hostId.value, node.value)
    const storages = (storageRes.data || []).filter(s => s.content && s.content.includes('backup'))
    const allBackups = await Promise.all(storages.map(async s => {
      try {
        const res = await api.pveNode.browseStorage(hostId.value, node.value, s.storage, { content: 'backup' })
        const items = (res.data || []).filter(b => {
          const name = b.volid || ''
          return name.includes(`-ct-${vmid.value}-`) || name.includes(`/ct-${vmid.value}-`)
        })
        return items.map(b => ({ ...b, _storage: s.storage }))
      } catch { return [] }
    }))
    backups.value = allBackups.flat().sort((a, b) => (b.ctime || 0) - (a.ctime || 0))
  } catch (e) {
    console.error('Failed to fetch backups:', e)
    toast.error('Failed to load backups')
  } finally {
    loadingBackups.value = false
  }
}

const runBackupNow = async () => {
  runningBackup.value = true
  try {
    const res = await api.pveNode.runBackup(hostId.value, node.value, {
      vmid: vmid.value,
      storage: backupForm.value.storage,
      mode: backupForm.value.mode,
      compress: backupForm.value.compress,
    })
    const upid = res.data?.upid || res.data
    if (upid && typeof upid === 'string' && upid.startsWith('UPID')) {
      taskUpid.value = upid
      taskProgressNode.value = node.value
      showTaskProgress.value = true
    } else {
      toast.success('Backup task started')
    }
  } catch (e) {
    console.error('Failed to start backup:', e)
    toast.error('Failed to start backup')
  } finally {
    runningBackup.value = false
  }
}

const openRestoreModal = (bk) => {
  restoreForm.value = { volid: bk.volid, newid: parseInt(vmid.value), storage: bk._storage, start: false }
  showRestoreModal.value = true
}

const submitRestore = async () => {
  restoringBackup.value = true
  try {
    const res = await api.pveNode.createLxc(hostId.value, node.value, {
      vmid: restoreForm.value.newid,
      ostemplate: restoreForm.value.volid,
      storage: restoreForm.value.storage || undefined,
      restore: 1,
      start: restoreForm.value.start ? 1 : 0,
    })
    showRestoreModal.value = false
    const upid = res.data?.upid || res.data
    if (upid && typeof upid === 'string' && upid.startsWith('UPID')) {
      taskUpid.value = upid
      taskProgressNode.value = node.value
      showTaskProgress.value = true
    } else {
      toast.success('Restore task started')
    }
  } catch (e) {
    console.error('Failed to restore backup:', e)
    toast.error('Failed to restore backup')
  } finally {
    restoringBackup.value = false
  }
}

// Firewall
const fetchFwRules = async () => {
  loadingFwRules.value = true
  try {
    const res = await api.pveNode.getCtFirewallRules(hostId.value, node.value, vmid.value)
    fwRules.value = res.data || []
  } catch (e) {
    console.error('Failed to load firewall rules:', e)
  } finally {
    loadingFwRules.value = false
  }
}

const fetchFwOptions = async () => {
  loadingFwOptions.value = true
  try {
    const res = await api.pveNode.getCtFirewallOptions(hostId.value, node.value, vmid.value)
    fwOptions.value = res.data || { enable: 0 }
  } catch (e) {
    console.error('Failed to load firewall options:', e)
  } finally {
    loadingFwOptions.value = false
  }
}

const toggleContainerFirewall = async (val) => {
  savingFwOptions.value = true
  try {
    await api.pveNode.setCtFirewallOptions(hostId.value, node.value, vmid.value, { enable: val ? 1 : 0 })
    fwOptions.value.enable = val ? 1 : 0
    toast.success(`Firewall ${val ? 'enabled' : 'disabled'}`)
  } catch (e) {
    toast.error('Failed to update firewall options')
  } finally {
    savingFwOptions.value = false
  }
}

const openFwRuleModal = (rule) => {
  if (rule) {
    fwRuleEdit.value = { ...rule }
  } else {
    fwRuleEdit.value = { type: 'in', action: 'ACCEPT', proto: '', source: '', dest: '', dport: '', comment: '', enable: 1 }
  }
  showFwRuleModal.value = true
}

const saveFwRule = async () => {
  savingFwRule.value = true
  try {
    const payload = { ...fwRuleEdit.value }
    // Remove empty strings
    Object.keys(payload).forEach(k => { if (payload[k] === '') delete payload[k] })
    if (payload.pos !== undefined) {
      const pos = payload.pos
      delete payload.pos
      await api.pveNode.updateCtFirewallRule(hostId.value, node.value, vmid.value, pos, payload)
    } else {
      await api.pveNode.addCtFirewallRule(hostId.value, node.value, vmid.value, payload)
    }
    toast.success('Firewall rule saved')
    showFwRuleModal.value = false
    await fetchFwRules()
  } catch (e) {
    toast.error('Failed to save firewall rule')
  } finally {
    savingFwRule.value = false
  }
}

const deleteFwRule = async (pos) => {
  if (!confirm(`Delete firewall rule at position ${pos}?`)) return
  try {
    await api.pveNode.deleteCtFirewallRule(hostId.value, node.value, vmid.value, pos)
    toast.success('Rule deleted')
    await fetchFwRules()
  } catch (e) {
    toast.error('Failed to delete rule')
  }
}

// RRD computed helpers
const rrdPoint = computed(() => {
  if (!rrdData.value || rrdData.value.length === 0) return null
  for (let i = rrdData.value.length - 1; i >= 0; i--) {
    const p = rrdData.value[i]
    if (p && (p.cpu != null || p.mem != null)) return p
  }
  return rrdData.value[rrdData.value.length - 1]
})

const memPct = computed(() => {
  if (!rrdPoint.value || !rrdPoint.value.maxmem || !rrdPoint.value.mem) return 0
  return Math.min((rrdPoint.value.mem / rrdPoint.value.maxmem) * 100, 100)
})

const cpuBarColor = computed(() => {
  if (!rrdPoint.value || rrdPoint.value.cpu == null) return 'var(--primary-color)'
  const pct = rrdPoint.value.cpu * 100
  if (pct > 90) return '#ef4444'
  if (pct > 70) return '#f59e0b'
  return '#22c55e'
})

const memBarColor = computed(() => {
  if (memPct.value > 90) return '#ef4444'
  if (memPct.value > 70) return '#f59e0b'
  return '#3b82f6'
})

// Convert RRD data array to PerformanceCharts format
const rrdChartData = (field, isPercent = false) => {
  return (rrdData.value || []).map(d => {
    if (!d) return null
    let val = d[field]
    if (val == null || isNaN(val)) return { time: d.time, value: null }
    if (isPercent) val = val * 100
    // mem_pct is a synthetic field
    if (field === 'mem_pct') {
      val = d.maxmem ? (d.mem / d.maxmem) * 100 : null
    }
    return { time: d.time, value: val }
  }).filter(Boolean)
}

const switchTab = (tab) => {
  activeTab.value = tab
  if (tab === 'snapshots') fetchSnapshots()
  if (tab === 'overview') fetchStatus()
  if (tab === 'performance') fetchRrdData()
  if (tab === 'backup') fetchBackups()
  if (tab === 'firewall') { fetchFwRules(); fetchFwOptions() }
}

const startPolling = () => {
  pollInterval = setInterval(() => {
    if (activeTab.value === 'overview') fetchStatus()
  }, 5000)
}

const action = async (act) => {
  actioning.value = true
  try {
    const res = await api.pveNode.containerAction(hostId.value, node.value, vmid.value, act)
    const upid = res.data?.upid || res.data
    if (upid && typeof upid === 'string' && upid.startsWith('UPID')) {
      taskUpid.value = upid
      taskProgressNode.value = node.value
      showTaskProgress.value = true
    } else {
      toast.success(`Container ${act} initiated`)
      setTimeout(() => fetchStatus(), 2000)
    }
  } catch (error) {
    console.error(`Failed to ${act} container:`, error)
    toast.error(`Failed to ${act} container`)
  } finally {
    actioning.value = false
  }
}

// Inline single-field save
const saveInlineField = async (field, value) => {
  savingField.value[field] = true
  try {
    await api.pveNode.updateContainerConfig(hostId.value, node.value, vmid.value, { [field]: value })
    toast.success(`${field} updated`)
    await fetchAll()
  } catch (error) {
    toast.error(`Failed to save ${field}`)
  } finally {
    savingField.value[field] = false
  }
}

const saveLimitField = async (field, value) => {
  savingLimit.value[field] = true
  try {
    await api.pveNode.updateContainerConfig(hostId.value, node.value, vmid.value, { [field]: value })
    toast.success(`${field} updated`)
    await fetchAll()
  } catch (error) {
    toast.error(`Failed to save ${field}`)
  } finally {
    savingLimit.value[field] = false
  }
}

const enterEditMode = () => {
  editConfig.value = {
    hostname: config.value.hostname || '',
    cores: config.value.cores || config.value.cpus || 1,
    memory: config.value.memory || 512,
    swap: config.value.swap !== undefined ? config.value.swap : 0,
    startup: config.value.startup || '',
    onboot: config.value.onboot || 0,
    unprivileged: config.value.unprivileged !== undefined ? config.value.unprivileged : 1,
    protection: config.value.protection || 0,
    description: config.value.description || '',
    tags: config.value.tags || '',
  }
  editMode.value = true
}

const cancelEdit = () => { editMode.value = false }

const saveConfig = async () => {
  savingConfig.value = true
  try {
    const payload = { ...editConfig.value }
    Object.keys(payload).forEach(k => {
      if (payload[k] === '' || payload[k] === null) delete payload[k]
    })
    await api.pveNode.updateContainerConfig(hostId.value, node.value, vmid.value, payload)
    toast.success('Configuration saved')
    editMode.value = false
    await fetchAll()
  } catch (error) {
    toast.error('Failed to save configuration')
  } finally {
    savingConfig.value = false
  }
}

// Mount point operations
const addMountPoint = async () => {
  savingMount.value = true
  try {
    const { key, storage, size, mp, acl, quota } = mountForm.value
    let val = `${storage}:${size},mp=${mp}`
    if (acl) val += ',acl=1'
    if (quota) val += ',quota=1'
    await api.pveNode.updateContainerConfig(hostId.value, node.value, vmid.value, { [key]: val })
    toast.success(`Mount point ${key} added`)
    showMountModal.value = false
    await fetchAll()
  } catch (e) {
    toast.error('Failed to add mount point')
  } finally {
    savingMount.value = false
  }
}

const removeMountPoint = async (key) => {
  if (!confirm(`Remove mount point ${key}? The volume will be detached but not deleted.`)) return
  actioning.value = true
  try {
    await api.pveNode.updateContainerConfig(hostId.value, node.value, vmid.value, { delete: key })
    toast.success(`Mount point ${key} removed`)
    await fetchAll()
  } catch (e) {
    toast.error('Failed to remove mount point')
  } finally {
    actioning.value = false
  }
}

const openMountResizeModal = (mp) => {
  resizeDiskKey.value = mp.key
  resizeAmount.value = ''
  showResizeModal.value = true
}

// Resize disk modal
const openResizeModal = (diskKey = 'rootfs') => {
  resizeDiskKey.value = diskKey
  resizeAmount.value = ''
  showResizeModal.value = true
}

const submitResize = async () => {
  if (!resizeAmount.value) return
  if (!resizeAmount.value.startsWith('+')) {
    toast.error('Size must start with + (e.g. +5G)')
    return
  }
  resizing.value = true
  try {
    await api.pveNode.resizeLxcDisk(hostId.value, node.value, vmid.value, {
      disk: resizeDiskKey.value,
      size: resizeAmount.value,
    })
    toast.success(`Disk resize to ${resizeAmount.value} initiated`)
    showResizeModal.value = false
    await fetchAll()
  } catch (error) {
    toast.error('Failed to resize disk')
  } finally {
    resizing.value = false
  }
}

const createSnapshot = async () => {
  if (!newSnapshot.value.snapname) {
    toast.error('Snapshot name is required')
    return
  }
  savingSnapshot.value = true
  try {
    await api.pveNode.createContainerSnapshot(hostId.value, node.value, vmid.value, newSnapshot.value)
    toast.success('Snapshot created')
    showSnapshotModal.value = false
    newSnapshot.value = { snapname: '', description: '' }
    await fetchSnapshots()
  } catch (error) {
    toast.error('Failed to create snapshot')
  } finally {
    savingSnapshot.value = false
  }
}

const rollbackSnapshot = async (snapname) => {
  if (!confirm(`Roll back to snapshot "${snapname}"? Current container state will be lost.`)) return
  actioning.value = true
  try {
    const res = await api.pveNode.rollbackContainerSnapshot(hostId.value, node.value, vmid.value, snapname)
    const upid = res.data?.upid || res.data
    if (upid && typeof upid === 'string' && upid.startsWith('UPID')) {
      taskUpid.value = upid
      taskProgressNode.value = node.value
      showTaskProgress.value = true
    } else {
      toast.success('Rollback initiated')
    }
    await fetchSnapshots()
  } catch (error) {
    toast.error('Failed to rollback')
  } finally {
    actioning.value = false
  }
}

const deleteSnapshot = async (snapname) => {
  if (!confirm(`Delete snapshot "${snapname}"?`)) return
  actioning.value = true
  try {
    await api.pveNode.deleteContainerSnapshot(hostId.value, node.value, vmid.value, snapname)
    toast.success('Snapshot deleted')
    await fetchSnapshots()
  } catch (error) {
    toast.error('Failed to delete snapshot')
  } finally {
    actioning.value = false
  }
}

const deleteContainer = async () => {
  if (!confirm(`Permanently delete CT ${vmid.value}? This cannot be undone.`)) return
  actioning.value = true
  try {
    await api.pveNode.deleteContainer(hostId.value, node.value, vmid.value)
    toast.success('Container deleted')
    router.push(`/proxmox/${hostId.value}/nodes/${node.value}`)
  } catch (error) {
    toast.error('Failed to delete container')
  } finally {
    actioning.value = false
  }
}

const fetchRrdData = async () => {
  loadingRrd.value = true
  try {
    const res = await api.pveNode.lxcRrdData(hostId.value, node.value, vmid.value, {
      timeframe: rrdTimeframe.value,
      cf: 'AVERAGE',
    })
    rrdData.value = res.data || []
  } catch (e) {
    console.error('Failed to fetch RRD data:', e)
    toast.error('Failed to load performance data')
  } finally {
    loadingRrd.value = false
  }
}

const formatRateBytes = (val) => {
  if (val == null || isNaN(val)) return '0 B'
  if (val >= 1073741824) return (val / 1073741824).toFixed(2) + ' GB'
  if (val >= 1048576) return (val / 1048576).toFixed(2) + ' MB'
  if (val >= 1024) return (val / 1024).toFixed(2) + ' KB'
  return val.toFixed(0) + ' B'
}

const openCloneModal = async () => {
  cloneForm.value = { newid: null, hostname: '', target: '', full: true, storage: '' }
  showCloneModal.value = true
  loadingNextId.value = true
  try {
    const [nextIdRes, clusterRes] = await Promise.all([
      api.pveNode.nextId(hostId.value),
      api.pveNode.clusterStatus(hostId.value),
    ])
    cloneForm.value.newid = nextIdRes.data
    const allNodes = (clusterRes.data || []).filter(e => e.type === 'node')
    pveNodes.value = allNodes.filter(n => n.name !== node.value)
  } catch (e) {
    console.warn('Failed to pre-populate clone form:', e)
  } finally {
    loadingNextId.value = false
  }
}

const submitClone = async () => {
  if (!cloneForm.value.newid) { toast.error('New CT ID is required'); return }
  cloningLxc.value = true
  try {
    const payload = { newid: cloneForm.value.newid, full: cloneForm.value.full ? 1 : 0 }
    if (cloneForm.value.hostname) payload.hostname = cloneForm.value.hostname
    if (cloneForm.value.target) payload.target = cloneForm.value.target
    if (cloneForm.value.storage) payload.storage = cloneForm.value.storage
    const res = await api.pveNode.cloneLxc(hostId.value, node.value, vmid.value, payload)
    showCloneModal.value = false
    const upid = res.data?.upid || res.data
    if (upid && typeof upid === 'string' && upid.startsWith('UPID')) {
      taskUpid.value = upid
      taskProgressNode.value = node.value
      showTaskProgress.value = true
    } else {
      toast.success(`Clone task started — new CT ${cloneForm.value.newid}`)
    }
  } catch (e) {
    toast.error('Failed to clone container')
  } finally {
    cloningLxc.value = false
  }
}

const onTaskSuccess = () => {
  toast.success('Task completed successfully')
  showTaskProgress.value = false
  fetchStatus()
}

const onTaskError = (msg) => {
  toast.error(`Task failed: ${msg}`)
  fetchStatus()
}

const openTerminal = () => {
  router.push(`/proxmox/${hostId.value}/nodes/${node.value}/terminal?lxc=${vmid.value}`)
}

const openConsoleTab = () => {
  activeTab.value = 'console'
}

const openConsoleWindow = () => {
  const url = `/console/${node.value}/${vmid.value}?type=lxc&hostId=${hostId.value}`
  window.open(url, '_blank', 'width=1024,height=768,menubar=no,toolbar=no')
}

const getStatusBadge = (s) => {
  if (s === 'running') return 'badge-success'
  if (s === 'stopped') return 'badge-danger'
  if (s === 'suspended') return 'badge-warning'
  return 'badge-info'
}

const formatDate = (epoch) => new Date(epoch * 1000).toLocaleString()

onMounted(async () => {
  await fetchAll()
  fetchSnapshots()
  startPolling()
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<style scoped>
.container-detail-page { padding: 0; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.back-link {
  color: var(--text-muted, var(--text-secondary));
  text-decoration: none;
  font-size: 0.875rem;
}
.back-link:hover { color: var(--text-primary); }

.ct-os-icon {
  font-size: 1.2rem;
  margin-right: 0.35rem;
  vertical-align: middle;
  cursor: default;
}

.ct-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.6rem 1.1rem;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.875rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
}
.tab-btn:hover { color: var(--text-primary); }
.tab-btn--active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(155px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card-sm {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.875rem 1rem;
}
.stat-card-sm__label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}
.stat-card-sm__value {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.card-body { padding: 1.5rem; }

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 0.75rem;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem;
  background: var(--background, var(--bg-secondary));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}

.summary-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.25rem;
}

.tag-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.15em 0.6em;
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: 9999px;
  background: var(--primary-color, #3b82f6);
  color: white;
}

/* Inline edit */
.inline-edit-grid { display: flex; flex-direction: column; gap: 0.75rem; }

.inline-edit-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.625rem 0;
  border-bottom: 1px solid var(--border-color);
}
.inline-edit-row:last-child { border-bottom: none; }

.inline-edit-label {
  width: 160px;
  flex-shrink: 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.inline-edit-control {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.config-value-inline {
  color: var(--text-primary);
  font-family: monospace;
  background: var(--bg-tertiary, var(--background, #1a1a2e));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.35rem 0.6rem;
  flex: 1;
  min-width: 0;
  word-break: break-all;
}

.form-control-sm { padding: 0.3rem 0.6rem; font-size: 0.875rem; }

/* Limits */
.limits-grid { display: flex; flex-direction: column; gap: 0; }

.limit-row {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border-color);
}
.limit-row:last-child { border-bottom: none; }

.limit-label-col {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.limit-label { font-size: 0.9rem; font-weight: 600; color: var(--text-primary); }
.limit-hint { font-size: 0.75rem; color: var(--text-secondary); }

.limit-control-col {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  flex-wrap: wrap;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
}

.range-slider { flex: 1; accent-color: var(--primary-color); cursor: pointer; }

.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
}

/* Config grid */
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 700px) {
  .config-grid { grid-template-columns: 1fr; }
  .inline-edit-row { flex-direction: column; align-items: flex-start; }
  .inline-edit-label { width: 100%; }
  .limit-row { flex-direction: column; align-items: flex-start; }
  .limit-label-col { width: 100%; }
}

.config-value {
  padding: 0.5rem 0.75rem;
  background: var(--bg-tertiary, var(--background, #1a1a2e));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  color: var(--text-primary);
  font-size: 0.9rem;
  min-height: 2.25rem;
  display: flex;
  align-items: center;
}

.section-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-top: 1px solid var(--border-color);
  padding-top: 1rem;
}

.raw-config-table {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
}

.raw-config-row {
  display: grid;
  grid-template-columns: 180px 1fr;
  border-bottom: 1px solid var(--border-color);
}
.raw-config-row:last-child { border-bottom: none; }

.raw-config-key {
  padding: 0.4rem 0.75rem;
  background: var(--background, rgba(255,255,255,0.03));
  font-family: monospace;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-right: 1px solid var(--border-color);
}

.raw-config-val {
  padding: 0.4rem 0.75rem;
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--text-primary);
  word-break: break-all;
}

.table-container { overflow-x: auto; }

/* Backup form */
.backup-form-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
}

/* Charts */
.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.chart-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
}

.chart-card__title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}

/* Performance summary cards */
.perf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

.perf-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
}
.perf-card__label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.35rem;
  font-weight: 600;
}
.perf-card__value {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}
.perf-card__sub {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.perf-bar-track {
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 0.25rem;
}
.perf-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

/* Firewall */
.fw-options-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

/* Modals */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal-header h3 { margin: 0; font-size: 1.1rem; }

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.modal-body { padding: 1.5rem; }

.align-center { align-items: center; }
.flex { display: flex; }
.flex-wrap { flex-wrap: wrap; }
.gap-1 { gap: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.mb-2 { margin-bottom: 1rem; }
.mb-1 { margin-bottom: 0.5rem; }
.ml-1 { margin-left: 0.25rem; }
.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.875rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-center { text-align: center; }

.checkbox-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-weight: 500;
}

.btn-group {
  display: flex;
  gap: 0;
}
.btn-group .btn { border-radius: 0; }
.btn-group .btn:first-child { border-radius: 0.375rem 0 0 0.375rem; }
.btn-group .btn:last-child { border-radius: 0 0.375rem 0.375rem 0; }
</style>
