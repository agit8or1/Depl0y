<template>
  <div class="vm-detail-page">
    <div v-if="loadingInit" class="loading-spinner"></div>
    <div v-else-if="!config" class="text-center text-muted mt-4">
      <p>Failed to load VM configuration.</p>
      <button @click="loadAll" class="btn btn-outline mt-2">Retry</button>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="page-header mb-2">
        <div class="header-left">
          <router-link :to="`/proxmox/${hostId}/nodes/${node}`" class="back-link">← {{ node }}</router-link>
          <h2 class="vm-title">
            {{ config.name || `VM ${vmid}` }}
            <span class="badge badge-info ml-1">{{ vmid }}</span>
            <button class="btn-copy" @click="copyVmId" title="Copy VM ID">⎘</button>
            <span :class="statusBadgeClass">{{ vmStatus?.status || 'unknown' }}</span>
            <span class="badge badge-info ml-1">QEMU</span>
            <button class="btn-copy" @click="copySshCommand" title="Copy SSH command">SSH</button>
          </h2>
        </div>
        <div class="header-actions flex gap-1 flex-wrap">
          <button @click="vmAction('start')" class="btn btn-success btn-sm"
            :disabled="actioning || vmStatus?.status === 'running'">Start</button>
          <button @click="vmAction('shutdown')" class="btn btn-outline btn-sm"
            :disabled="actioning || vmStatus?.status !== 'running'">Stop</button>
          <button @click="vmAction('stop')" class="btn btn-danger btn-sm"
            :disabled="actioning || vmStatus?.status === 'stopped'">Force Stop</button>
          <button @click="vmAction('reboot')" class="btn btn-outline btn-sm"
            :disabled="actioning || vmStatus?.status !== 'running'">Reboot</button>
          <button @click="vmAction('reset')" class="btn btn-outline btn-sm"
            :disabled="actioning || vmStatus?.status !== 'running'">Reset</button>
          <button v-if="vmStatus?.status !== 'suspended'" @click="vmAction('suspend')" class="btn btn-outline btn-sm"
            :disabled="actioning || vmStatus?.status !== 'running'">Suspend</button>
          <button v-else @click="vmAction('resume')" class="btn btn-outline btn-sm"
            :disabled="actioning">Resume</button>
          <span class="action-sep">|</span>
          <button @click="openCloneModal" class="btn btn-outline btn-sm">Clone</button>
          <router-link
            :to="`/migrate/${hostId}/${node}/${vmid}?type=qemu`"
            class="btn btn-outline btn-sm"
          >Migrate</router-link>
          <button @click="doConvertToTemplate" class="btn btn-outline btn-sm" :disabled="actioning">To Template</button>
          <button @click="showDeleteConfirm = true" class="btn btn-danger btn-sm" :disabled="actioning">Delete</button>
          <button @click="openQuickSnapshotModal" class="btn btn-outline btn-sm" :disabled="actioning" title="Quick Snapshot">📸</button>
          <span class="action-sep">|</span>
          <router-link
            :to="`/proxmox/${hostId}/nodes/${node}/console/${vmid}`"
            class="btn btn-outline btn-sm btn-console-link"
            title="Open VM Console"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:3px;"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
            Console
          </router-link>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs mb-2">
        <button v-for="tab in tabs" :key="tab.id"
          :class="['tab-btn', activeTab === tab.id ? 'tab-btn--active' : '']"
          @click="switchTab(tab.id)">{{ tab.label }}</button>
      </div>

      <!-- ─── Overview Tab ─── -->
      <div v-if="activeTab === 'overview'">
        <div class="stats-row mb-2">
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">CPU</div>
            <div class="stat-card-sm__value">{{ cpuPct }}%</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">RAM Used</div>
            <div class="stat-card-sm__value">{{ formatBytes(vmStatus?.mem) }} / {{ formatBytes(vmStatus?.maxmem) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Uptime</div>
            <div class="stat-card-sm__value">{{ formatUptime(vmStatus?.uptime) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Net In / Out</div>
            <div class="stat-card-sm__value text-sm">{{ formatBytes(vmStatus?.netin) }} / {{ formatBytes(vmStatus?.netout) }}</div>
          </div>
        </div>

        <div class="charts-row">
          <div class="card chart-card">
            <div class="card-header">
              <h4>CPU % over time</h4>
              <select v-model="rrdTimeframe" @change="loadRrd" class="form-control form-control-sm">
                <option value="hour">Last Hour</option>
                <option value="day">Last Day</option>
                <option value="week">Last Week</option>
              </select>
            </div>
            <div class="chart-wrap">
              <Line v-if="cpuChartData" :data="cpuChartData" :options="lineChartOptions" />
              <div v-else class="text-muted text-center text-sm pt-2">Loading chart...</div>
            </div>
          </div>
          <div class="card chart-card">
            <div class="card-header"><h4>Memory % over time</h4></div>
            <div class="chart-wrap">
              <Line v-if="memChartData" :data="memChartData" :options="lineChartOptions" />
              <div v-else class="text-muted text-center text-sm pt-2">Loading chart...</div>
            </div>
          </div>
        </div>

        <!-- Tags -->
        <div class="card mt-2">
          <div class="card-header">
            <h4 style="margin:0;font-size:0.95rem;">Tags</h4>
            <button v-if="!showTagInput" @click="openTagInput" class="btn btn-outline btn-sm" :disabled="savingTags">
              + Add Tag
            </button>
          </div>
          <div class="card-body" style="padding:0.75rem 1.5rem 1rem;">
            <div class="tag-manager">
              <TagBadge
                v-for="tag in tagList"
                :key="tag"
                :tag="tag"
                :removable="!savingTags"
                @remove="removeTag"
              />
              <span v-if="tagList.length === 0 && !showTagInput" class="text-muted text-sm">No tags</span>

              <span v-if="showTagInput" class="tag-input-wrap">
                <input
                  ref="tagInputRef"
                  v-model="newTagValue"
                  class="tag-input"
                  placeholder="tagname"
                  @keyup.enter="addTag"
                  @keyup.escape="cancelTagInput"
                  @input="newTagValue = sanitizeTag(newTagValue)"
                  maxlength="40"
                />
                <button class="btn btn-primary btn-sm" @click="addTag" :disabled="!newTagValue.trim()">+</button>
                <button class="btn btn-outline btn-sm" @click="cancelTagInput">Cancel</button>
              </span>
            </div>
          </div>
        </div>

        <!-- Notes -->
        <div class="card mt-2">
          <div class="card-header">
            <h4 style="margin:0;font-size:0.95rem;">Notes</h4>
            <div class="flex gap-1">
              <button v-if="!editingNotes" @click="startEditNotes" class="btn btn-outline btn-sm">Edit</button>
              <template v-else>
                <button @click="saveNotes" class="btn btn-primary btn-sm" :disabled="savingNotes">
                  {{ savingNotes ? 'Saving...' : 'Save' }}
                </button>
                <button @click="cancelEditNotes" class="btn btn-outline btn-sm">Cancel</button>
              </template>
            </div>
          </div>
          <div class="card-body">
            <textarea v-if="editingNotes" v-model="notesText" class="form-control" rows="5"
              placeholder="Enter notes / description for this VM..."></textarea>
            <div v-else class="config-value pre-wrap" style="min-height:60px;">
              {{ config.description || '—' }}
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Config Tab ─── -->
      <div v-if="activeTab === 'config'">
        <div class="card">
          <div class="card-header">
            <h3>VM Configuration</h3>
          </div>
          <div class="card-body">
            <div class="config-grid">

              <!-- Name -->
              <div class="form-group inline-field">
                <label class="form-label">Name</label>
                <div class="inline-edit-row">
                  <input v-model="inlineEdit.name" class="form-control" placeholder="vm-name"
                    @keyup.enter="saveInlineField('name', inlineEdit.name)" />
                  <button @click="saveInlineField('name', inlineEdit.name)"
                    class="btn btn-primary btn-sm" :disabled="savingField.name">
                    {{ savingField.name ? '...' : 'Save' }}
                  </button>
                </div>
                <div class="inline-current">Current: <code>{{ config.name || '—' }}</code></div>
              </div>

              <!-- CPU Cores -->
              <div class="form-group inline-field">
                <label class="form-label">CPU Cores</label>
                <div class="inline-edit-row">
                  <input v-model.number="inlineEdit.cores" type="number" min="1" max="128"
                    class="form-control"
                    @keyup.enter="saveInlineField('cores', inlineEdit.cores)" />
                  <button @click="saveInlineField('cores', inlineEdit.cores)"
                    class="btn btn-primary btn-sm" :disabled="savingField.cores">
                    {{ savingField.cores ? '...' : 'Save' }}
                  </button>
                </div>
                <div class="inline-current">Current: <code>{{ config.cores || 1 }}</code></div>
              </div>

              <!-- Memory -->
              <div class="form-group inline-field">
                <label class="form-label">Memory (MB)</label>
                <div class="inline-edit-row">
                  <input v-model.number="inlineEdit.memory" type="number" min="64" step="64"
                    class="form-control"
                    @keyup.enter="saveInlineField('memory', inlineEdit.memory)" />
                  <button @click="saveInlineField('memory', inlineEdit.memory)"
                    class="btn btn-primary btn-sm" :disabled="savingField.memory">
                    {{ savingField.memory ? '...' : 'Save' }}
                  </button>
                </div>
                <div class="inline-current">Current: <code>{{ config.memory || '—' }} MB</code></div>
              </div>

              <!-- CPU Type -->
              <div class="form-group inline-field">
                <label class="form-label">CPU Type</label>
                <div class="inline-edit-row">
                  <select v-model="inlineEdit.cpu" class="form-control">
                    <option value="host">host</option>
                    <option value="kvm64">kvm64</option>
                    <option value="x86-64-v2-AES">x86-64-v2-AES</option>
                    <option value="qemu64">qemu64</option>
                  </select>
                  <button @click="saveInlineField('cpu', inlineEdit.cpu)"
                    class="btn btn-primary btn-sm" :disabled="savingField.cpu">
                    {{ savingField.cpu ? '...' : 'Save' }}
                  </button>
                </div>
                <div class="inline-current">Current: <code>{{ config.cpu || 'host' }}</code></div>
              </div>

              <!-- BIOS -->
              <div class="form-group inline-field">
                <label class="form-label">BIOS</label>
                <div class="inline-edit-row">
                  <select v-model="inlineEdit.bios" class="form-control">
                    <option value="seabios">SeaBIOS (default)</option>
                    <option value="ovmf">OVMF (UEFI)</option>
                  </select>
                  <button @click="saveInlineField('bios', inlineEdit.bios)"
                    class="btn btn-primary btn-sm" :disabled="savingField.bios">
                    {{ savingField.bios ? '...' : 'Save' }}
                  </button>
                </div>
                <div class="inline-current">Current: <code>{{ config.bios || 'seabios' }}</code></div>
              </div>

              <!-- Machine Type -->
              <div class="form-group inline-field">
                <label class="form-label">Machine Type</label>
                <div class="inline-edit-row">
                  <select v-model="inlineEdit.machine" class="form-control">
                    <option value="">default</option>
                    <option value="pc">pc</option>
                    <option value="q35">q35</option>
                    <option value="pc-i440fx-2.2">pc-i440fx-2.2</option>
                  </select>
                  <button @click="saveInlineField('machine', inlineEdit.machine)"
                    class="btn btn-primary btn-sm" :disabled="savingField.machine">
                    {{ savingField.machine ? '...' : 'Save' }}
                  </button>
                </div>
                <div class="inline-current">Current: <code>{{ config.machine || 'default' }}</code></div>
              </div>

              <!-- Boot Disk / Order -->
              <div class="form-group inline-field">
                <label class="form-label">Boot Order</label>
                <div class="inline-edit-row">
                  <input v-model="inlineEdit.boot" class="form-control"
                    placeholder="order=scsi0;ide2;net0"
                    @keyup.enter="saveInlineField('boot', inlineEdit.boot)" />
                  <button @click="saveInlineField('boot', inlineEdit.boot)"
                    class="btn btn-primary btn-sm" :disabled="savingField.boot">
                    {{ savingField.boot ? '...' : 'Save' }}
                  </button>
                </div>
                <div class="inline-current">Current: <code>{{ config.boot || '—' }}</code></div>
              </div>

              <!-- Sockets -->
              <div class="form-group inline-field">
                <label class="form-label">Sockets</label>
                <div class="inline-edit-row">
                  <input v-model.number="inlineEdit.sockets" type="number" min="1" max="8"
                    class="form-control"
                    @keyup.enter="saveInlineField('sockets', inlineEdit.sockets)" />
                  <button @click="saveInlineField('sockets', inlineEdit.sockets)"
                    class="btn btn-primary btn-sm" :disabled="savingField.sockets">
                    {{ savingField.sockets ? '...' : 'Save' }}
                  </button>
                </div>
                <div class="inline-current">Current: <code>{{ config.sockets || 1 }}</code></div>
              </div>

              <!-- Balloon (MB) -->
              <div class="form-group inline-field">
                <label class="form-label">Balloon (MB)</label>
                <div class="inline-edit-row">
                  <input v-model.number="inlineEdit.balloon" type="number" min="0" step="64"
                    class="form-control"
                    @keyup.enter="saveInlineField('balloon', inlineEdit.balloon)" />
                  <button @click="saveInlineField('balloon', inlineEdit.balloon)"
                    class="btn btn-primary btn-sm" :disabled="savingField.balloon">
                    {{ savingField.balloon ? '...' : 'Save' }}
                  </button>
                </div>
                <div class="inline-current">Current: <code>{{ config.balloon ?? 0 }} MB</code></div>
              </div>

              <!-- Description (full width) -->
              <div class="form-group inline-field config-grid-span2">
                <label class="form-label">Description</label>
                <textarea v-model="inlineEdit.description" class="form-control" rows="3"></textarea>
                <div class="flex gap-1 mt-1">
                  <button @click="saveInlineField('description', inlineEdit.description)"
                    class="btn btn-primary btn-sm" :disabled="savingField.description">
                    {{ savingField.description ? 'Saving...' : 'Save Description' }}
                  </button>
                </div>
              </div>

              <!-- Boolean toggles row -->
              <div class="form-group config-grid-span2">
                <label class="form-label" style="margin-bottom:0.5rem;">Toggles</label>
                <div class="toggle-row">
                  <label class="toggle-item">
                    <input type="checkbox" class="toggle-check"
                      :checked="!!inlineEdit.numa"
                      @change="saveInlineField('numa', $event.target.checked ? 1 : 0)" />
                    <span class="toggle-label">NUMA</span>
                    <span class="toggle-status" :class="inlineEdit.numa ? 'badge badge-success' : 'badge badge-info'">
                      {{ inlineEdit.numa ? 'On' : 'Off' }}
                    </span>
                  </label>
                  <label class="toggle-item">
                    <input type="checkbox" class="toggle-check"
                      :checked="!!inlineEdit.agent"
                      @change="saveInlineField('agent', $event.target.checked ? 1 : 0)" />
                    <span class="toggle-label">QEMU Agent</span>
                    <span class="toggle-status" :class="inlineEdit.agent ? 'badge badge-success' : 'badge badge-info'">
                      {{ inlineEdit.agent ? 'On' : 'Off' }}
                    </span>
                  </label>
                  <label class="toggle-item">
                    <input type="checkbox" class="toggle-check"
                      :checked="!!inlineEdit.onboot"
                      @change="saveInlineField('onboot', $event.target.checked ? 1 : 0)" />
                    <span class="toggle-label">Start at Boot</span>
                    <span class="toggle-status" :class="inlineEdit.onboot ? 'badge badge-success' : 'badge badge-danger'">
                      {{ inlineEdit.onboot ? 'Yes' : 'No' }}
                    </span>
                  </label>
                  <label class="toggle-item">
                    <input type="checkbox" class="toggle-check"
                      :checked="!!inlineEdit.protection"
                      @change="saveInlineField('protection', $event.target.checked ? 1 : 0)" />
                    <span class="toggle-label">Protection</span>
                    <span class="toggle-status" :class="inlineEdit.protection ? 'badge badge-warning' : 'badge badge-info'">
                      {{ inlineEdit.protection ? 'On' : 'Off' }}
                    </span>
                  </label>
                </div>
              </div>

            </div>
          </div>
        </div>

        <!-- Pending Config Changes -->
        <div class="card mt-2">
          <div class="card-header pending-header" @click="pendingExpanded = !pendingExpanded" style="cursor:pointer;">
            <h3 class="pending-title">
              Pending Config Changes
              <span v-if="pendingLoaded && pendingChanges.length > 0" class="badge badge-warning ml-1">{{ pendingChanges.length }}</span>
            </h3>
            <div class="flex gap-1 pending-header-actions" @click.stop>
              <button @click="loadPending" class="btn btn-outline btn-sm pending-refresh" :disabled="loadingPending" title="Refresh pending changes">
                <span :class="loadingPending ? 'spin' : ''">&#8635;</span>
              </button>
              <button class="btn btn-outline btn-sm" @click="pendingExpanded = !pendingExpanded">
                {{ pendingExpanded ? '▲' : '▼' }}
              </button>
            </div>
          </div>
          <div v-if="pendingExpanded">
            <div v-if="loadingPending" class="loading-spinner"></div>
            <div v-else-if="!pendingLoaded" class="card-body text-muted text-sm">
              Loading pending changes...
            </div>
            <div v-else-if="pendingChanges.length === 0" class="card-body text-muted text-sm">
              No pending changes.
            </div>
            <template v-else>
              <div class="pending-warning-banner">
                <span class="pending-warning-icon">&#9888;</span>
                This VM has pending configuration changes that will take effect on next boot.
              </div>
              <div class="table-container">
                <table class="table">
                  <thead>
                    <tr>
                      <th>Key</th>
                      <th>Current Value</th>
                      <th>Pending Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in pendingChanges" :key="item.key">
                      <td><code>{{ item.key }}</code></td>
                      <td class="text-sm pending-current">{{ item.value ?? '—' }}</td>
                      <td class="text-sm pending-new">{{ item.pending }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- ─── Disks Tab ─── -->
      <div v-if="activeTab === 'disks'">
        <div class="card">
          <div class="card-header">
            <h3>Disks</h3>
            <div class="flex gap-1">
              <button @click="openAddDiskModal" class="btn btn-primary btn-sm">+ Add Disk</button>
              <button @click="loadUnusedDisks" class="btn btn-outline btn-sm" :disabled="loadingUnused" title="Refresh disk list">&#8635;</button>
            </div>
          </div>

          <!-- Boot order -->
          <div v-if="diskBootOrder.length > 0" class="disk-boot-order">
            <span class="text-sm" style="margin-right:0.5rem;font-weight:600;">Boot order:</span>
            <div class="boot-order-list">
              <div v-for="(item, idx) in diskBootOrder" :key="item.key" class="boot-order-item">
                <span class="boot-pos">{{ idx + 1 }}</span>
                <code>{{ item.key }}</code>
                <div class="boot-order-btns">
                  <button class="btn btn-outline btn-xs" :disabled="idx === 0 || actioning" @click="moveBootOrder(idx, -1)">&#8593;</button>
                  <button class="btn btn-outline btn-xs" :disabled="idx === diskBootOrder.length - 1 || actioning" @click="moveBootOrder(idx, 1)">&#8595;</button>
                </div>
              </div>
            </div>
            <button class="btn btn-outline btn-sm" @click="saveBootOrder" :disabled="actioning" style="margin-left:0.75rem;">Save Boot Order</button>
          </div>

          <div class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Interface</th>
                  <th>Storage Pool</th>
                  <th>Volume</th>
                  <th>Size</th>
                  <th>Format</th>
                  <th>Cache</th>
                  <th>SSD</th>
                  <th>Discard</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="parsedDisks.length === 0">
                  <td colspan="9" class="text-muted text-center">No disks found</td>
                </tr>
                <tr v-for="disk in parsedDisks" :key="disk.key">
                  <td><code>{{ disk.key }}</code></td>
                  <td>{{ disk.parsed.storage || '—' }}</td>
                  <td class="text-sm text-muted">{{ disk.parsed.volume }}</td>
                  <td><strong>{{ formatDiskSize(disk.parsed.size) }}</strong></td>
                  <td>{{ disk.parsed.format || 'raw' }}</td>
                  <td>{{ disk.parsed.cache || 'none' }}</td>
                  <td>
                    <button @click="toggleDiskFlag(disk, 'ssd')"
                      :class="disk.parsed.ssd ? 'btn btn-success btn-xs' : 'btn btn-outline btn-xs'"
                      :disabled="actioning" title="Toggle SSD emulation">
                      {{ disk.parsed.ssd ? 'On' : 'Off' }}
                    </button>
                  </td>
                  <td>
                    <button @click="toggleDiskFlag(disk, 'discard')"
                      :class="disk.parsed.discard ? 'btn btn-success btn-xs' : 'btn btn-outline btn-xs'"
                      :disabled="actioning" title="Toggle discard/TRIM">
                      {{ disk.parsed.discard ? 'On' : 'Off' }}
                    </button>
                  </td>
                  <td>
                    <div class="flex gap-1 flex-wrap">
                      <button @click="openResizeDisk(disk)" class="btn btn-outline btn-sm">Resize</button>
                      <button @click="openMoveDisk(disk)" class="btn btn-outline btn-sm">Move</button>
                      <button @click="detachDisk(disk.key)" class="btn btn-danger btn-sm" :disabled="actioning">Detach</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Unused Disks card -->
        <div v-if="unusedDisks.length > 0" class="card mt-2">
          <div class="card-header">
            <h3>Unused Disks</h3>
            <span class="badge badge-warning">{{ unusedDisks.length }}</span>
          </div>
          <div class="table-container">
            <table class="table">
              <thead><tr><th>Slot</th><th>Volume ID</th><th>Actions</th></tr></thead>
              <tbody>
                <tr v-for="ud in unusedDisks" :key="ud.key">
                  <td><code>{{ ud.key }}</code></td>
                  <td class="text-sm text-muted">{{ ud.volid }}</td>
                  <td>
                    <div class="flex gap-1">
                      <button @click="openReattachDisk(ud)" class="btn btn-primary btn-sm" :disabled="actioning">Reattach</button>
                      <button @click="deleteUnused(ud)" class="btn btn-danger btn-sm" :disabled="actioning">Delete</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Network Tab ─── -->
      <div v-if="activeTab === 'network'">
        <div class="card">
          <div class="card-header">
            <h3>Network Interfaces</h3>
            <button @click="showAddNicModal = true" class="btn btn-primary btn-sm">+ Add NIC</button>
          </div>
          <div class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Interface</th>
                  <th>Model</th>
                  <th>MAC Address</th>
                  <th>Bridge</th>
                  <th>VLAN Tag</th>
                  <th>Firewall</th>
                  <th>Rate (MB/s)</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="parsedNics.length === 0">
                  <td colspan="8" class="text-muted text-center">No NICs configured</td>
                </tr>
                <tr v-for="nic in parsedNics" :key="nic.key">
                  <td><code>{{ nic.key }}</code></td>
                  <td><span class="badge badge-info">{{ nic.parsed.model }}</span></td>
                  <td class="text-sm"><code>{{ nic.parsed.mac || '—' }}</code></td>
                  <td>{{ nic.parsed.bridge || '—' }}</td>
                  <td>{{ nic.parsed.vlan || '—' }}</td>
                  <td>
                    <button @click="toggleNicFirewall(nic)"
                      :class="nic.parsed.firewall ? 'btn btn-success btn-xs' : 'btn btn-outline btn-xs'"
                      :disabled="actioning" title="Toggle firewall for this NIC">
                      {{ nic.parsed.firewall ? 'On' : 'Off' }}
                    </button>
                  </td>
                  <td>{{ nic.parsed.rate || '—' }}</td>
                  <td>
                    <div class="flex gap-1">
                      <button @click="openEditNic(nic)" class="btn btn-outline btn-sm">Edit</button>
                      <button @click="removeNic(nic.key)" class="btn btn-danger btn-sm" :disabled="actioning">Detach</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Snapshots Tab ─── -->
      <div v-if="activeTab === 'snapshots'">
        <div class="card">
          <div class="card-header">
            <h3>Snapshots</h3>
            <div class="flex gap-1">
              <button v-if="selectedSnaps.size === 2" @click="openCompareModal" class="btn btn-outline btn-sm">Compare Selected</button>
              <button @click="showSnapshotModal = true" class="btn btn-primary btn-sm">+ Create Snapshot</button>
            </div>
          </div>
          <div v-if="loadingSnapshots" class="loading-spinner"></div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th style="width:2rem"></th>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Date</th>
                  <th>VM State</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="snapshotTree.length === 0">
                  <td colspan="6" class="text-muted text-center">No snapshots</td>
                </tr>
                <template v-for="snap in snapshotTree" :key="snap.name">
                  <tr :class="snap.name === 'current' ? 'snap-current-row' : ''">
                    <td>
                      <input v-if="snap.name !== 'current'" type="checkbox"
                        :checked="selectedSnaps.has(snap.name)"
                        @change="toggleSnapSelect(snap.name)"
                        :disabled="selectedSnaps.size >= 2 && !selectedSnaps.has(snap.name)" />
                    </td>
                    <td>
                      <span class="snap-tree-indent" :style="{ paddingLeft: snap._depth * 1.2 + 'rem' }">
                        <span v-if="snap._depth > 0" class="snap-tree-line">{{ snap._isLast ? '└ ' : '├ ' }}</span>
                      </span>
                      <span v-if="snap.name === 'current'" class="badge badge-success" style="font-size:0.7rem;">You are here</span>
                      <strong v-else>{{ snap.name }}</strong>
                      <span v-if="snap.vmstate" class="ml-1" title="RAM state saved">💾</span>
                    </td>
                    <td class="text-sm text-muted">{{ snap.description || '—' }}</td>
                    <td class="text-sm">{{ snap.snaptime ? new Date(snap.snaptime * 1000).toLocaleString() : '—' }}</td>
                    <td>
                      <span v-if="snap.vmstate" class="badge badge-info">Saved</span>
                      <span v-else class="text-muted text-sm">—</span>
                    </td>
                    <td>
                      <div v-if="snap.name !== 'current'" class="flex gap-1">
                        <button v-if="snap._hasChildren"
                          @click="toggleSnapCollapse(snap.name)"
                          class="btn btn-outline btn-xs"
                          :title="collapsedSnaps.has(snap.name) ? 'Expand children' : 'Collapse children'">
                          {{ collapsedSnaps.has(snap.name) ? '▶' : '▼' }}
                        </button>
                        <button @click="rollbackSnapshot(snap.name)" class="btn btn-outline btn-sm" :disabled="actioning">Rollback</button>
                        <button @click="deleteSnapshot(snap.name)" class="btn btn-danger btn-sm" :disabled="actioning">Delete</button>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Firewall Tab ─── -->
      <div v-if="activeTab === 'firewall'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>Firewall Options</h3>
          </div>
          <div class="card-body" v-if="firewallOptions !== null">
            <label class="form-label checkbox-label">
              <input type="checkbox" :checked="firewallOptions.enable == 1"
                @change="toggleFirewall($event.target.checked)" />
              Firewall Enabled for this VM
            </label>
          </div>
        </div>
        <div class="card">
          <div class="card-header">
            <h3>Firewall Rules</h3>
            <button @click="showFirewallModal = true" class="btn btn-primary btn-sm">+ Add Rule</button>
          </div>
          <div v-if="loadingFirewall" class="loading-spinner"></div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Pos</th>
                  <th>Type</th>
                  <th>Action</th>
                  <th>Proto</th>
                  <th>Source</th>
                  <th>Dest</th>
                  <th>DPort</th>
                  <th>Comment</th>
                  <th>Enabled</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="firewallRules.length === 0">
                  <td colspan="10" class="text-muted text-center">No firewall rules</td>
                </tr>
                <tr v-for="rule in firewallRules" :key="rule.pos">
                  <td>{{ rule.pos }}</td>
                  <td>
                    <span :class="rule.type === 'in' ? 'badge badge-info' : 'badge badge-warning'">
                      {{ (rule.type || 'in').toUpperCase() }}
                    </span>
                  </td>
                  <td>
                    <span :class="rule.action === 'ACCEPT' ? 'badge badge-success' : rule.action === 'DROP' ? 'badge badge-danger' : 'badge badge-warning'">
                      {{ rule.action }}
                    </span>
                  </td>
                  <td>{{ rule.proto || 'any' }}</td>
                  <td class="text-sm">{{ rule.source || 'any' }}</td>
                  <td class="text-sm">{{ rule.dest || 'any' }}</td>
                  <td class="text-sm">{{ rule.dport || '—' }}</td>
                  <td class="text-sm text-muted">{{ rule.comment || '—' }}</td>
                  <td>
                    <span :class="rule.enable == 1 ? 'badge badge-success' : 'badge badge-danger'">
                      {{ rule.enable == 1 ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td>
                    <button @click="deleteFirewallRule(rule.pos)" class="btn btn-danger btn-sm" :disabled="actioning">Delete</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Power Schedule Tab ─── -->
      <div v-if="activeTab === 'schedule'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>Power Schedule</h3>
            <button @click="openAddScheduleModal" class="btn btn-primary btn-sm">+ Add Schedule</button>
          </div>
          <div class="card-body" style="padding:0.75rem 1.5rem 1rem;">
            <p class="text-muted text-sm mb-2">
              Schedule automated power actions for this VM. Schedules are stored as VM tags with the prefix <code>schedule:</code>.
              They are parsed and displayed here for easy management.
            </p>
            <div v-if="scheduleEntries.length === 0" class="text-muted text-sm">
              No power schedules configured. Click "+ Add Schedule" to create one.
            </div>
          </div>
          <div v-if="scheduleEntries.length > 0" class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Cron Expression</th>
                  <th>Description</th>
                  <th>Next Run</th>
                  <th>Enabled</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(entry, idx) in scheduleEntries" :key="idx">
                  <td>
                    <span :class="['badge', scheduleActionBadge(entry.action)]">{{ entry.action }}</span>
                  </td>
                  <td><code class="text-sm">{{ entry.cron }}</code></td>
                  <td class="text-sm text-muted">{{ entry.description || '—' }}</td>
                  <td class="text-sm">{{ computeNextRun(entry.cron) }}</td>
                  <td>
                    <button
                      @click="toggleScheduleEntry(idx)"
                      :class="entry.enabled ? 'btn btn-success btn-xs' : 'btn btn-outline btn-xs'"
                      :disabled="savingTags"
                    >
                      {{ entry.enabled ? 'Yes' : 'No' }}
                    </button>
                  </td>
                  <td>
                    <button @click="deleteScheduleEntry(idx)" class="btn btn-danger btn-sm" :disabled="savingTags">Delete</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Schedule info card -->
        <div class="card">
          <div class="card-header"><h4 style="margin:0;font-size:0.9rem;">How Power Schedules Work</h4></div>
          <div class="card-body text-sm text-muted" style="padding:1rem 1.5rem;">
            <p>Schedules are stored as VM tags in the format <code>schedule:action:cron_b64:desc_b64:enabled</code>.</p>
            <p class="mt-1">The depl0y scheduler reads these tags and executes the appropriate Proxmox API call at the scheduled time.</p>
            <p class="mt-1"><strong>Cron format:</strong> <code>minute hour day-of-month month day-of-week</code> (e.g. <code>0 2 * * *</code> = 2:00 AM daily)</p>
            <p class="mt-1"><strong>Actions:</strong> start, shutdown, reboot</p>
          </div>
        </div>
      </div>

      <!-- ─── Console Tab ─── -->
      <div v-if="activeTab === 'console'">
        <div class="card">
          <div class="card-header"><h3>Console Access</h3></div>
          <div class="card-body text-center">
            <p class="text-muted mb-2">Open a noVNC console session for this VM in a new browser tab.</p>
            <button @click="openConsole" class="btn btn-primary mb-2">Launch Console</button>
            <div class="text-sm text-muted mt-2">
              <p>Console is available while the VM is running. A VNC ticket is generated on demand.</p>
              <p>Console URL: <code>/proxmox/{{ hostId }}/nodes/{{ node }}/console/{{ vmid }}</code></p>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Performance Tab ─── -->
      <div v-if="activeTab === 'performance'">
        <!-- Time range selector -->
        <div class="flex gap-1 mb-2 align-center">
          <span class="text-sm text-muted">Time Range:</span>
          <div class="perf-time-selector">
            <button
              v-for="tr in perfTimeRanges"
              :key="tr.value"
              :class="['ptr-btn', perfTimeframe === tr.value ? 'ptr-btn--active' : '']"
              @click="setPerfTimeframe(tr.value)"
            >{{ tr.label }}</button>
          </div>
          <button @click="loadPerfRrd" class="btn btn-outline btn-sm" :disabled="loadingPerf">
            {{ loadingPerf ? 'Loading...' : 'Refresh' }}
          </button>
        </div>

        <div v-if="loadingPerf && !perfRrdData.length" class="text-center text-muted" style="padding:2rem">
          Loading performance data...
        </div>

        <div v-else class="perf-charts-grid">
          <!-- CPU -->
          <div class="card perf-chart-card">
            <div class="perf-chart-card__header">
              <span class="perf-chart-card__title">CPU Usage</span>
              <span v-if="vmCpuData.length" class="perf-chart-card__val">
                {{ latestPerfVal(vmCpuData).toFixed(1) }}%
              </span>
            </div>
            <div class="perf-chart-body">
              <PerformanceCharts
                v-if="vmCpuData.length"
                :data="vmCpuData"
                label="CPU"
                unit="%"
                color="#3b82f6"
                :height="chartH"
              />
              <div v-else class="text-muted text-sm text-center" style="line-height:100px">No data</div>
            </div>
          </div>

          <!-- Memory -->
          <div class="card perf-chart-card">
            <div class="perf-chart-card__header">
              <span class="perf-chart-card__title">Memory Usage</span>
              <span v-if="vmMemData.length" class="perf-chart-card__val">
                {{ latestPerfVal(vmMemData).toFixed(1) }}%
              </span>
            </div>
            <div class="perf-chart-body">
              <PerformanceCharts
                v-if="vmMemData.length"
                :data="vmMemData"
                label="Memory"
                unit="%"
                color="#10b981"
                :height="chartH"
              />
              <div v-else class="text-muted text-sm text-center" style="line-height:100px">No data</div>
            </div>
          </div>

          <!-- Disk Read -->
          <div class="card perf-chart-card">
            <div class="perf-chart-card__header">
              <span class="perf-chart-card__title">Disk Read</span>
              <span v-if="vmDiskReadData.length" class="perf-chart-card__val">
                {{ formatPerfMBs(latestPerfVal(vmDiskReadData)) }}
              </span>
            </div>
            <div class="perf-chart-body">
              <PerformanceCharts
                v-if="vmDiskReadData.length"
                :data="vmDiskReadData"
                label="Disk Read"
                unit="MB/s"
                color="#8b5cf6"
                :height="chartH"
              />
              <div v-else class="text-muted text-sm text-center" style="line-height:100px">No data</div>
            </div>
          </div>

          <!-- Disk Write -->
          <div class="card perf-chart-card">
            <div class="perf-chart-card__header">
              <span class="perf-chart-card__title">Disk Write</span>
              <span v-if="vmDiskWriteData.length" class="perf-chart-card__val">
                {{ formatPerfMBs(latestPerfVal(vmDiskWriteData)) }}
              </span>
            </div>
            <div class="perf-chart-body">
              <PerformanceCharts
                v-if="vmDiskWriteData.length"
                :data="vmDiskWriteData"
                label="Disk Write"
                unit="MB/s"
                color="#ef4444"
                :height="chartH"
              />
              <div v-else class="text-muted text-sm text-center" style="line-height:100px">No data</div>
            </div>
          </div>

          <!-- Net In -->
          <div class="card perf-chart-card">
            <div class="perf-chart-card__header">
              <span class="perf-chart-card__title">Network In</span>
              <span v-if="vmNetInData.length" class="perf-chart-card__val">
                {{ formatPerfMBs(latestPerfVal(vmNetInData)) }}
              </span>
            </div>
            <div class="perf-chart-body">
              <PerformanceCharts
                v-if="vmNetInData.length"
                :data="vmNetInData"
                label="Net In"
                unit="MB/s"
                color="#06b6d4"
                :height="chartH"
              />
              <div v-else class="text-muted text-sm text-center" style="line-height:100px">No data</div>
            </div>
          </div>

          <!-- Net Out -->
          <div class="card perf-chart-card">
            <div class="perf-chart-card__header">
              <span class="perf-chart-card__title">Network Out</span>
              <span v-if="vmNetOutData.length" class="perf-chart-card__val">
                {{ formatPerfMBs(latestPerfVal(vmNetOutData)) }}
              </span>
            </div>
            <div class="perf-chart-body">
              <PerformanceCharts
                v-if="vmNetOutData.length"
                :data="vmNetOutData"
                label="Net Out"
                unit="MB/s"
                color="#f59e0b"
                :height="chartH"
              />
              <div v-else class="text-muted text-sm text-center" style="line-height:100px">No data</div>
            </div>
          </div>
        </div>
      </div>
    </template>

      <!-- ─── Access Tab ─── -->
      <div v-if="activeTab === 'access'">
        <!-- Direct permissions on this VM -->
        <div class="card mb-2">
          <div class="card-header">
            <h3>VM Access Control — <code>/vms/{{ vmid }}</code></h3>
            <button @click="openVmGrantModal" class="btn btn-primary btn-sm">+ Grant Access</button>
          </div>
          <div v-if="loadingVmAcl" class="loading-spinner"></div>
          <div v-else-if="vmAclDirect.length === 0" class="text-center text-muted" style="padding:1.5rem;">
            No direct permissions on this VM.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>User / Group / Token</th>
                  <th>Role</th>
                  <th>Propagate</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(entry, idx) in vmAclDirect" :key="idx">
                  <td>
                    <span v-if="entry.type === 'group'" class="badge badge-warning" style="margin-right:0.4rem;">group</span>
                    <span v-else-if="entry.type === 'token'" class="badge badge-info" style="margin-right:0.4rem;">token</span>
                    <span v-else class="badge badge-secondary" style="margin-right:0.4rem;">user</span>
                    {{ entry.ugid }}
                  </td>
                  <td><span class="badge badge-info">{{ entry.roleid }}</span></td>
                  <td>
                    <span :class="['badge', entry.propagate ? 'badge-success' : 'badge-secondary']">
                      {{ entry.propagate ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td>
                    <button @click="revokeVmAcl(entry)" class="btn btn-danger btn-sm">Revoke</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Inherited permissions -->
        <div class="card">
          <div class="card-header">
            <h3>Inherited Permissions</h3>
            <span class="text-sm text-muted">From parent paths — cannot be removed here</span>
          </div>
          <div v-if="loadingVmAcl" class="loading-spinner"></div>
          <div v-else-if="vmAclInherited.length === 0" class="text-center text-muted" style="padding:1.5rem;">
            No inherited permissions found.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Path</th>
                  <th>User / Group / Token</th>
                  <th>Role</th>
                  <th>Propagate</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(entry, idx) in vmAclInherited" :key="idx" style="opacity:0.65;">
                  <td><code>{{ entry.path }}</code></td>
                  <td>
                    <span v-if="entry.type === 'group'" class="badge badge-warning" style="margin-right:0.4rem;">group</span>
                    <span v-else class="badge badge-secondary" style="margin-right:0.4rem;">{{ entry.type }}</span>
                    {{ entry.ugid }}
                  </td>
                  <td><span class="badge badge-info">{{ entry.roleid }}</span></td>
                  <td>
                    <span :class="['badge', entry.propagate ? 'badge-success' : 'badge-secondary']">
                      {{ entry.propagate ? 'Yes' : 'No' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>


      <!-- ─── Hardware Tab ─── -->
      <div v-if="activeTab === 'hardware'">
        <PCIPassthrough
          :host-id="hostId"
          :node="node"
          :vmid="vmid"
          :vm-config="config"
          :nodes="availableNodes"
          @config-changed="loadConfig"
        />

        <!-- USB Passthrough -->
        <div class="card mt-2">
          <div class="card-header">
            <h4>USB Passthrough</h4>
            <button @click="showAddUsbModal = true" class="btn btn-primary btn-sm">+ Add USB Device</button>
          </div>
          <div v-if="!attachedUsbDevices.length" class="text-center text-muted" style="padding:1.2rem;">
            No USB devices passed through.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Slot</th>
                  <th>Host Device</th>
                  <th>USB3</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="dev in attachedUsbDevices" :key="dev.key">
                  <td><code>{{ dev.key }}</code></td>
                  <td><code>{{ dev.host }}</code></td>
                  <td>
                    <span :class="['badge', dev.usb3 ? 'badge-info' : 'badge-secondary']">
                      {{ dev.usb3 ? 'USB 3.0' : 'USB 2.0' }}
                    </span>
                  </td>
                  <td>
                    <button @click="removeUsb(dev)" class="btn btn-danger btn-sm"
                            :disabled="removingUsb === dev.key">
                      {{ removingUsb === dev.key ? '...' : 'Remove' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Serial Ports -->
        <div class="card mt-2">
          <div class="card-header">
            <h4>Serial Ports</h4>
            <button @click="addSerialSocket" class="btn btn-primary btn-sm" :disabled="addingSerial">
              {{ addingSerial ? '...' : '+ Add Serial Socket' }}
            </button>
          </div>
          <div v-if="!attachedSerialPorts.length" class="text-center text-muted" style="padding:1.2rem;">
            No serial ports configured.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Port</th>
                  <th>Type</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="port in attachedSerialPorts" :key="port.key">
                  <td><code>{{ port.key }}</code></td>
                  <td><code>{{ port.type }}</code></td>
                  <td>
                    <button @click="removeSerial(port)" class="btn btn-danger btn-sm"
                            :disabled="removingSerial === port.key">
                      {{ removingSerial === port.key ? '...' : 'Remove' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Add USB modal -->
        <div v-if="showAddUsbModal" class="modal" @click.self="showAddUsbModal = false">
          <div class="modal-content" @click.stop style="max-width:480px;">
            <div class="modal-header">
              <h3>Add USB Device to VM {{ vmid }}</h3>
              <button @click="showAddUsbModal = false" class="btn-close">×</button>
            </div>
            <div class="modal-body">
              <p class="text-sm text-muted mb-2">
                Select from available USB devices on the node, or enter a vendor:product ID manually.
              </p>
              <div v-if="usbDevices.length > 0" class="form-group">
                <label class="form-label">Available USB Devices on Node</label>
                <select v-model="addUsbForm.host" class="form-control">
                  <option value="">-- Select device --</option>
                  <option v-for="u in usbDevices" :key="u.usbid || u.vendid+':'+u.prodid"
                          :value="u.vendid + ':' + u.prodid">
                    {{ u.vendid }}:{{ u.prodid }} — {{ u.product || u.manufacturer || '(unknown)' }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Vendor:Product ID (manual)</label>
                <input v-model="addUsbForm.host" class="form-control" placeholder="1234:abcd" />
                <p class="text-xs text-muted mt-1">Format: vendorid:productid (hex)</p>
              </div>
              <div class="form-group">
                <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;">
                  <input type="checkbox" v-model="addUsbForm.usb3" />
                  <span>USB 3.0</span>
                </label>
              </div>
              <div class="alert alert-warning text-sm">
                The VM should be <strong>powered off</strong> before making USB configuration changes.
              </div>
            </div>
            <div class="modal-footer">
              <button @click="showAddUsbModal = false" class="btn btn-outline">Cancel</button>
              <button @click="doAddUsb" class="btn btn-primary" :disabled="savingUsb || !addUsbForm.host">
                {{ savingUsb ? 'Adding...' : 'Add USB Device' }}
              </button>
            </div>
          </div>
        </div>
      </div>

    <!-- ══════════════════════════════════════════════════════ MODALS ══ -->

    <!-- Grant VM Access Modal -->
    <div v-if="showVmGrantModal" class="modal" @click.self="showVmGrantModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Grant Access to VM {{ vmid }}</h3>
          <button @click="showVmGrantModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="doGrantVmAcl" class="modal-body">
          <div class="form-group">
            <label class="form-label">User / Group / Token ID</label>
            <input v-model="vmAclForm.ugid" class="form-control"
              placeholder="user@pve or group@pve or user@pve!token" required />
            <p class="text-xs text-muted mt-1">Enter a PVE user ID, group ID, or token.</p>
          </div>
          <div class="form-group">
            <label class="form-label">Type</label>
            <select v-model="vmAclForm.ugtype" class="form-control">
              <option value="user">User</option>
              <option value="group">Group</option>
              <option value="token">Token</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Role</label>
            <div v-if="loadingVmRoles" class="text-sm text-muted">Loading roles...</div>
            <select v-else v-model="vmAclForm.roleid" class="form-control" required>
              <option value="" disabled>Select a role</option>
              <option v-for="r in vmRoles" :key="r.roleid" :value="r.roleid">{{ r.roleid }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">
              <input type="checkbox" v-model="vmAclForm.propagate" :true-value="1" :false-value="0" />
              Propagate (apply to sub-paths)
            </label>
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingVmAcl">
              {{ savingVmAcl ? 'Granting...' : 'Grant Access' }}
            </button>
            <button type="button" @click="showVmGrantModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Delete Confirmation -->
    <div v-if="showDeleteConfirm" class="modal" @click.self="showDeleteConfirm = false">
      <div class="modal-content modal-sm" @click.stop>
        <div class="modal-header">
          <h3>Delete VM {{ vmid }}?</h3>
          <button @click="showDeleteConfirm = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p class="text-muted mb-2">This action is irreversible. The VM and its disks will be permanently deleted.</p>
          <div class="flex gap-1">
            <button @click="doDeleteVM" class="btn btn-danger" :disabled="actioning">
              {{ actioning ? 'Deleting...' : 'Delete VM' }}
            </button>
            <button @click="showDeleteConfirm = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Clone Modal -->
    <div v-if="showCloneModal" class="modal" @click.self="showCloneModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Clone VM {{ vmid }}</h3>
          <button @click="showCloneModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">New VM ID</label>
              <input v-model.number="cloneForm.newid" type="number" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Name</label>
              <input v-model="cloneForm.name" class="form-control" placeholder="clone-of-vm" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Clone Type</label>
            <div class="flex gap-2">
              <label class="form-label">
                <input type="radio" v-model="cloneForm.full" :value="true" /> Full Clone
              </label>
              <label class="form-label">
                <input type="radio" v-model="cloneForm.full" :value="false" /> Linked Clone
              </label>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Target Node</label>
              <select v-model="cloneForm.target" class="form-control">
                <option value="">Same node ({{ node }})</option>
                <option v-for="n in clusterNodes" :key="n.node" :value="n.node">{{ n.node }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Target Storage</label>
              <select v-model="cloneForm.storage" class="form-control">
                <option value="">Same as source</option>
                <option v-for="s in storageList" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
              </select>
            </div>
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doClone" class="btn btn-primary" :disabled="actioning">
              {{ actioning ? 'Cloning...' : 'Clone VM' }}
            </button>
            <button @click="showCloneModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Migrate Modal -->
    <div v-if="showMigrateModal" class="modal" @click.self="showMigrateModal = false">
      <div class="modal-content modal-content--wide" @click.stop>
        <div class="modal-header">
          <h3>Migrate VM {{ vmid }}</h3>
          <button @click="showMigrateModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">

          <!-- Source Info Card -->
          <div class="migrate-source-card">
            <div class="migrate-source-title">Source</div>
            <div class="migrate-source-row">
              <span class="migrate-source-label">VM</span>
              <span><strong>{{ config?.name || 'VM ' + vmid }}</strong> ({{ vmid }})</span>
            </div>
            <div class="migrate-source-row">
              <span class="migrate-source-label">Node</span>
              <span class="badge badge-info">{{ node }}</span>
            </div>
            <div class="migrate-source-row">
              <span class="migrate-source-label">Status</span>
              <span :class="statusBadgeClass">{{ vmStatus?.status || 'unknown' }}</span>
            </div>
          </div>

          <!-- Precondition Warnings -->
          <div v-if="migrateWarnings.length > 0" class="migrate-warnings">
            <div v-for="(w, i) in migrateWarnings" :key="i" class="migrate-warning-item">
              <span class="migrate-warning-icon">&#9888;</span> {{ w }}
            </div>
          </div>

          <!-- Target node -->
          <div class="form-group">
            <label class="form-label">Target Node <span class="text-danger">*</span></label>
            <select v-model="migrateForm.target" class="form-control" @change="onMigrateTargetChange">
              <option value="" disabled>Select target node</option>
              <option v-for="n in clusterNodes" :key="n.node" :value="n.node">
                {{ n.node }}
                <template v-if="n.status"> — {{ n.status }}</template>
              </option>
            </select>
            <div v-if="clusterNodes.length === 0" class="form-hint text-danger">
              No other nodes found in the cluster. Migration requires at least one other node.
            </div>
          </div>

          <!-- Online migration -->
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input v-model="migrateForm.online" type="checkbox"
                :disabled="vmStatus?.status !== 'running'" />
              Online Migration (live, VM stays running)
            </label>
            <div class="form-hint" v-if="migrateForm.online">VM will remain running during migration. Requires shared storage or local disk migration.</div>
            <div class="form-hint" v-else-if="vmStatus?.status === 'running'">
              VM will be <strong>stopped</strong> before migration and restarted on the target node.
            </div>
            <div class="form-hint" v-else>VM is stopped — offline migration will be used.</div>
          </div>

          <!-- With local disks -->
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input v-model="migrateForm.with_local_disks" type="checkbox" />
              Migrate with Local Disks
            </label>
            <div class="form-hint">Required when VM has disks on local (non-shared) storage. Copies disk data to target node.</div>
          </div>

          <!-- Bandwidth limit -->
          <div class="form-group">
            <label class="form-label">Bandwidth Limit (MB/s, 0 = unlimited)</label>
            <input v-model.number="migrateForm.bwlimit" type="number" min="0" step="10"
              class="form-control" placeholder="0 = unlimited" />
            <div class="form-hint">Maximum migration bandwidth in MB/s. Set to 0 for unlimited.</div>
          </div>

          <!-- Target storage selector -->
          <div v-if="migrateForm.target" class="form-group">
            <label class="form-label">
              Target Storage (per-disk mapping)
              <span v-if="loadingTargetStorage" class="text-muted text-sm ml-1">(loading…)</span>
            </label>
            <div v-if="!loadingTargetStorage && targetStorageList.length === 0" class="text-muted text-sm">
              No VM-capable storage available on {{ migrateForm.target }}.
            </div>
            <div v-else-if="!loadingTargetStorage">
              <!-- Per-disk storage mapping -->
              <div v-if="parsedDisks.length > 0" class="migrate-storage-table">
                <div class="migrate-storage-header">
                  <span>Disk</span>
                  <span>Source Storage</span>
                  <span>Target Storage</span>
                </div>
                <div v-for="disk in parsedDisks" :key="disk.key" class="migrate-storage-row">
                  <span class="migrate-disk-key"><code>{{ disk.key }}</code></span>
                  <span class="migrate-storage-src text-sm text-muted">{{ disk.parsed?.storage || '—' }}</span>
                  <select
                    v-model="migrateStorageMap[disk.key]"
                    class="form-control form-control-sm"
                  >
                    <option value="">Same as source / auto</option>
                    <option v-for="s in targetStorageList" :key="s.storage" :value="s.storage">
                      {{ s.storage }} ({{ s.type }})
                    </option>
                  </select>
                </div>
              </div>
              <div v-else class="text-muted text-sm">No disk mappings required (no detected disks).</div>
            </div>
          </div>

          <div class="flex gap-1 mt-2">
            <button @click="doMigrate" class="btn btn-primary"
              :disabled="migrateSubmitting || !migrateForm.target">
              {{ migrateSubmitting ? 'Starting…' : 'Start Migration' }}
            </button>
            <button @click="showMigrateModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Migration Task Progress Modal -->
    <TaskProgressModal
      :visible="showMigrateProgress"
      :upid="migrateUpid"
      :host-id="hostId"
      :node="node"
      @close="showMigrateProgress = false"
      @success="onMigrateSuccess"
      @error="onMigrateError"
    />

    <!-- Add Disk Modal -->
    <div v-if="showAddDiskModal" class="modal" @click.self="showAddDiskModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Disk</h3>
          <button @click="showAddDiskModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <!-- Add disk mode tabs -->
          <div class="disk-mode-tabs">
            <button :class="['disk-mode-tab', addDiskMode === 'new' ? 'active' : '']" @click="addDiskMode = 'new'">New Disk</button>
            <button :class="['disk-mode-tab', addDiskMode === 'existing' ? 'active' : '']" @click="addDiskMode = 'existing'; loadStorageImages()">Import Existing Image</button>
          </div>

          <!-- New disk form -->
          <template v-if="addDiskMode === 'new'">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Bus / Type</label>
                <select v-model="addDiskForm.bus" class="form-control">
                  <option value="scsi">SCSI (recommended)</option>
                  <option value="virtio">VirtIO</option>
                  <option value="sata">SATA</option>
                  <option value="ide">IDE</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Storage</label>
                <select v-model="addDiskForm.storage" class="form-control">
                  <option v-for="s in storageList" :key="s.storage" :value="s.storage">
                    {{ s.storage }} ({{ s.type }})
                  </option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Size (GB)</label>
                <input v-model.number="addDiskForm.size" type="number" min="1" class="form-control" />
              </div>
              <div class="form-group">
                <label class="form-label">Format</label>
                <select v-model="addDiskForm.format" class="form-control">
                  <option value="qcow2">qcow2</option>
                  <option value="raw">raw</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Cache Mode</label>
                <select v-model="addDiskForm.cache" class="form-control">
                  <option value="">none (default)</option>
                  <option value="writeback">writeback</option>
                  <option value="writethrough">writethrough</option>
                  <option value="directsync">directsync</option>
                  <option value="unsafe">unsafe</option>
                </select>
              </div>
              <div class="form-group" style="justify-content:center; padding-top:1.5rem;">
                <label class="form-label checkbox-label"><input type="checkbox" v-model="addDiskForm.ssd" /> SSD Emulation</label>
                <label class="form-label checkbox-label mt-1"><input type="checkbox" v-model="addDiskForm.discard" /> Discard (TRIM)</label>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label checkbox-label"><input type="checkbox" v-model="addDiskForm.backup" /> Include in Backup</label>
              </div>
              <div class="form-group">
                <label class="form-label checkbox-label"><input type="checkbox" v-model="addDiskForm.iothread" /> IO Thread</label>
              </div>
              <div class="form-group">
                <label class="form-label checkbox-label"><input type="checkbox" v-model="addDiskForm.replicate" /> Replicate</label>
              </div>
            </div>
          </template>

          <!-- Import existing image form -->
          <template v-else>
            <div class="form-group">
              <label class="form-label">Browse Storage for Image</label>
              <select v-model="addDiskForm.browse_storage" class="form-control" @change="loadStorageImages">
                <option value="">Select storage...</option>
                <option v-for="s in storageList" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
              </select>
            </div>
            <div v-if="storageImagesLoading" class="text-muted text-sm mt-1">Loading images...</div>
            <div v-else-if="storageImages.length" class="storage-image-list mt-1">
              <div v-for="img in storageImages" :key="img.volid"
                :class="['storage-image-row', addDiskForm.import_volid === img.volid ? 'selected' : '']"
                @click="addDiskForm.import_volid = img.volid">
                <input type="radio" :value="img.volid" v-model="addDiskForm.import_volid" @click.stop />
                <span class="img-name">{{ imgFileName(img.volid) }}</span>
                <span class="img-meta">{{ img.format || '?' }} &middot; {{ img.size ? fmtBytes(img.size) : '—' }}</span>
              </div>
            </div>
            <div class="form-row mt-2">
              <div class="form-group">
                <label class="form-label">Target Bus</label>
                <select v-model="addDiskForm.bus" class="form-control">
                  <option value="scsi">SCSI</option>
                  <option value="virtio">VirtIO</option>
                  <option value="sata">SATA</option>
                  <option value="ide">IDE</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Target Storage</label>
                <select v-model="addDiskForm.storage" class="form-control">
                  <option v-for="s in storageList" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
                </select>
              </div>
            </div>
          </template>

          <div class="flex gap-1 mt-2">
            <button @click="doAddDisk" class="btn btn-primary" :disabled="actioning">
              {{ actioning ? 'Adding...' : 'Add Disk' }}
            </button>
            <button @click="showAddDiskModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Move Disk Modal -->
    <div v-if="showMoveDiskModal" class="modal" @click.self="showMoveDiskModal = false">
      <div class="modal-content modal-sm" @click.stop>
        <div class="modal-header">
          <h3>Move Disk: {{ moveDiskKey }}</h3>
          <button @click="showMoveDiskModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p class="text-sm text-muted mb-2">Move this disk to a different storage pool. The VM may need to be stopped first.</p>
          <div class="form-group">
            <label class="form-label">Target Storage <span class="text-danger">*</span></label>
            <select v-model="moveDiskForm.storage" class="form-control">
              <option value="" disabled>Select target storage...</option>
              <option v-for="s in storageList" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Target Format</label>
            <select v-model="moveDiskForm.format" class="form-control">
              <option value="">Keep original</option>
              <option value="qcow2">qcow2</option>
              <option value="raw">raw</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input type="checkbox" v-model="moveDiskForm.delete_source" />
              Delete source after move
            </label>
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doMoveDisk" class="btn btn-primary" :disabled="actioning || !moveDiskForm.storage">
              {{ actioning ? 'Moving...' : 'Move Disk' }}
            </button>
            <button @click="showMoveDiskModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Reattach Unused Disk Modal -->
    <div v-if="showReattachModal" class="modal" @click.self="showReattachModal = false">
      <div class="modal-content modal-sm" @click.stop>
        <div class="modal-header">
          <h3>Reattach Disk: {{ reattachDiskKey }}</h3>
          <button @click="showReattachModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p class="text-sm text-muted mb-2">
            Volume: <code>{{ reattachVolid }}</code>
          </p>
          <div class="form-group">
            <label class="form-label">Bus</label>
            <select v-model="reattachBus" class="form-control">
              <option value="scsi">SCSI (recommended)</option>
              <option value="virtio">VirtIO</option>
              <option value="sata">SATA</option>
              <option value="ide">IDE</option>
            </select>
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doReattachDisk" class="btn btn-primary" :disabled="actioning">
              {{ actioning ? 'Reattaching...' : 'Reattach' }}
            </button>
            <button @click="showReattachModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Resize Disk Modal -->
    <div v-if="showResizeModal" class="modal" @click.self="showResizeModal = false">
      <div class="modal-content modal-sm" @click.stop>
        <div class="modal-header">
          <h3>Resize Disk: {{ resizeDiskKey }}</h3>
          <button @click="showResizeModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p class="text-sm text-muted mb-2">
            Current size: <strong>{{ resizeDiskCurrentSize }}</strong><br/>
            Enter the amount to <em>add</em> (e.g. <code>+10G</code>) or the new total size (e.g. <code>50G</code>).
          </p>
          <div class="form-group">
            <label class="form-label">New / Additional Size</label>
            <input v-model="resizeSize" class="form-control" placeholder="+10G or 50G" autofocus />
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doResizeDisk" class="btn btn-primary" :disabled="actioning || !resizeSize">
              {{ actioning ? 'Resizing...' : 'Resize' }}
            </button>
            <button @click="showResizeModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add NIC Modal -->
    <div v-if="showAddNicModal" class="modal" @click.self="showAddNicModal = false">
      <div class="modal-content modal-sm" @click.stop>
        <div class="modal-header">
          <h3>Add Network Interface</h3>
          <button @click="showAddNicModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Model</label>
            <select v-model="addNicForm.model" class="form-control">
              <option value="virtio">VirtIO (recommended)</option>
              <option value="e1000">Intel E1000</option>
              <option value="rtl8139">RTL8139</option>
              <option value="vmxnet3">VMware vmxnet3</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Bridge</label>
            <input v-model="addNicForm.bridge" class="form-control" placeholder="vmbr0" />
          </div>
          <div class="form-group">
            <label class="form-label">VLAN Tag (optional)</label>
            <input v-model.number="addNicForm.tag" type="number" class="form-control" placeholder="e.g. 10" />
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doAddNic" class="btn btn-primary" :disabled="actioning || !addNicForm.bridge">
              {{ actioning ? 'Adding...' : 'Add NIC' }}
            </button>
            <button @click="showAddNicModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit NIC Modal -->
    <div v-if="showEditNicModal" class="modal" @click.self="showEditNicModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Edit NIC: {{ editNicKey }}</h3>
          <button @click="showEditNicModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Model</label>
              <select v-model="editNicForm.model" class="form-control">
                <option value="virtio">VirtIO (recommended)</option>
                <option value="e1000">Intel E1000</option>
                <option value="rtl8139">RTL8139</option>
                <option value="vmxnet3">VMware vmxnet3</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Bridge</label>
              <input v-model="editNicForm.bridge" class="form-control" placeholder="vmbr0" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">VLAN Tag (optional)</label>
              <input v-model.number="editNicForm.tag" type="number" class="form-control" placeholder="e.g. 10" />
            </div>
            <div class="form-group">
              <label class="form-label">Rate Limit (MB/s, optional)</label>
              <input v-model.number="editNicForm.rate" type="number" min="0" step="1" class="form-control" placeholder="e.g. 100" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input v-model="editNicForm.firewall" type="checkbox" />
              Firewall enabled for this NIC
            </label>
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doEditNic" class="btn btn-primary" :disabled="actioning || !editNicForm.bridge">
              {{ actioning ? 'Saving...' : 'Save NIC' }}
            </button>
            <button @click="showEditNicModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Snapshot Modal -->
    <div v-if="showQuickSnapshotModal" class="modal" @click.self="showQuickSnapshotModal = false">
      <div class="modal-content modal-sm" @click.stop>
        <div class="modal-header">
          <h3>Quick Snapshot</h3>
          <button @click="showQuickSnapshotModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Snapshot Name <span class="text-danger">*</span></label>
            <input v-model="quickSnapForm.snapname" class="form-control" placeholder="snap-YYYYMMDD-HHmm" />
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <input v-model="quickSnapForm.description" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doQuickSnapshot" class="btn btn-primary"
              :disabled="actioning || !quickSnapForm.snapname">
              {{ actioning ? 'Creating...' : 'Create Snapshot' }}
            </button>
            <button @click="showQuickSnapshotModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Snapshot Compare Modal -->
    <div v-if="showCompareModal" class="modal" @click.self="showCompareModal = false">
      <div class="modal-content modal-lg" @click.stop>
        <div class="modal-header">
          <h3>Compare Snapshots</h3>
          <button @click="showCompareModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="loadingCompare" class="loading-spinner"></div>
          <div v-else>
            <div class="compare-grid">
              <div class="compare-col">
                <h4 class="compare-col-title">{{ compareSnaps[0] }}</h4>
                <div class="compare-body">
                  <div v-for="(val, key) in compareLeft" :key="key"
                    :class="['compare-row', compareRowClass(key, 'left')]">
                    <span class="compare-key">{{ key }}</span>
                    <span class="compare-val">{{ val }}</span>
                  </div>
                  <div v-for="key in compareOnlyRight" :key="'missing-' + key"
                    class="compare-row compare-row--missing">
                    <span class="compare-key">{{ key }}</span>
                    <span class="compare-val text-muted">— (not present)</span>
                  </div>
                </div>
              </div>
              <div class="compare-col">
                <h4 class="compare-col-title">{{ compareSnaps[1] }}</h4>
                <div class="compare-body">
                  <div v-for="(val, key) in compareRight" :key="key"
                    :class="['compare-row', compareRowClass(key, 'right')]">
                    <span class="compare-key">{{ key }}</span>
                    <span class="compare-val">{{ val }}</span>
                  </div>
                  <div v-for="key in compareOnlyLeft" :key="'missing-' + key"
                    class="compare-row compare-row--missing">
                    <span class="compare-key">{{ key }}</span>
                    <span class="compare-val text-muted">— (not present)</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="compareIdentical" class="text-center text-muted mt-2">
              Configurations are identical.
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Snapshot Task Progress -->
    <TaskProgressModal
      :visible="showQuickSnapProgress"
      :upid="quickSnapUpid"
      :host-id="hostId"
      :node="node"
      @close="showQuickSnapProgress = false; loadSnapshots()"
      @success="onQuickSnapSuccess"
      @error="onQuickSnapError"
    />

    <!-- Create Snapshot Modal -->
    <div v-if="showSnapshotModal" class="modal" @click.self="showSnapshotModal = false">
      <div class="modal-content modal-sm" @click.stop>
        <div class="modal-header">
          <h3>Create Snapshot</h3>
          <button @click="showSnapshotModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Snapshot Name <span class="text-danger">*</span></label>
            <input v-model="snapshotForm.snapname" class="form-control" placeholder="snap1" />
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <input v-model="snapshotForm.description" class="form-control" placeholder="Optional description" />
          </div>
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input v-model="snapshotForm.vmstate" type="checkbox" />
              Include RAM (save VM state — slower but allows full resume)
            </label>
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doCreateSnapshot" class="btn btn-primary"
              :disabled="actioning || !snapshotForm.snapname">
              {{ actioning ? 'Creating...' : 'Create Snapshot' }}
            </button>
            <button @click="showSnapshotModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Power Schedule Modal -->
    <div v-if="showAddScheduleModal" class="modal" @click.self="showAddScheduleModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Power Schedule</h3>
          <button @click="showAddScheduleModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Action <span class="text-danger">*</span></label>
            <select v-model="scheduleForm.action" class="form-control">
              <option value="start">Start</option>
              <option value="shutdown">Shutdown</option>
              <option value="reboot">Reboot</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Cron Expression <span class="text-danger">*</span></label>
            <input v-model="scheduleForm.cron" class="form-control" placeholder="0 2 * * *" />
            <div class="form-hint">Format: minute hour day month weekday — e.g. <code>0 2 * * *</code> = 2:00 AM every day</div>
          </div>
          <div class="schedule-presets">
            <span class="text-sm text-muted" style="margin-right:0.5rem;">Presets:</span>
            <button v-for="p in schedulePresets" :key="p.label" @click="scheduleForm.cron = p.cron"
              class="btn btn-outline btn-xs" style="margin:0.15rem;">{{ p.label }}</button>
          </div>
          <div class="form-group mt-2">
            <label class="form-label">Description (optional)</label>
            <input v-model="scheduleForm.description" class="form-control" placeholder="e.g. Nightly shutdown" />
          </div>
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input v-model="scheduleForm.enabled" type="checkbox" />
              Enabled
            </label>
          </div>
          <div v-if="scheduleForm.cron && isValidCron(scheduleForm.cron)" class="form-hint" style="color:var(--secondary-color,#10b981);">
            Next run: {{ computeNextRun(scheduleForm.cron) }}
          </div>
          <div v-else-if="scheduleForm.cron" class="form-hint text-danger">Invalid cron expression</div>
          <div class="flex gap-1 mt-2">
            <button @click="doAddSchedule" class="btn btn-primary"
              :disabled="savingTags || !scheduleForm.cron || !isValidCron(scheduleForm.cron)">
              {{ savingTags ? 'Saving...' : 'Add Schedule' }}
            </button>
            <button @click="showAddScheduleModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Firewall Rule Modal -->
    <div v-if="showFirewallModal" class="modal" @click.self="showFirewallModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Firewall Rule</h3>
          <button @click="showFirewallModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Direction</label>
              <select v-model="firewallForm.type" class="form-control">
                <option value="in">IN (Inbound)</option>
                <option value="out">OUT (Outbound)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Action</label>
              <select v-model="firewallForm.action" class="form-control">
                <option value="ACCEPT">ACCEPT</option>
                <option value="DROP">DROP</option>
                <option value="REJECT">REJECT</option>
              </select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Protocol</label>
              <select v-model="firewallForm.proto" class="form-control">
                <option value="">any</option>
                <option value="tcp">TCP</option>
                <option value="udp">UDP</option>
                <option value="icmp">ICMP</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="firewallForm.enable" :true-value="1" :false-value="0" />
                Enabled
              </label>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Source</label>
              <input v-model="firewallForm.source" class="form-control" placeholder="any or CIDR" />
            </div>
            <div class="form-group">
              <label class="form-label">Destination</label>
              <input v-model="firewallForm.dest" class="form-control" placeholder="any or CIDR" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Dest Port</label>
              <input v-model="firewallForm.dport" class="form-control" placeholder="80, 443, 8080-8090" />
            </div>
            <div class="form-group">
              <label class="form-label">Comment</label>
              <input v-model="firewallForm.comment" class="form-control" placeholder="Optional" />
            </div>
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doAddFirewallRule" class="btn btn-primary" :disabled="actioning">
              {{ actioning ? 'Adding...' : 'Add Rule' }}
            </button>
            <button @click="showFirewallModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Line } from 'vue-chartjs'
import TaskProgressModal from '@/components/TaskProgressModal.vue'
import PerformanceCharts from '@/components/PerformanceCharts.vue'
import TagBadge from '@/components/TagBadge.vue'
import { tagColor as _tagColorUtil } from '@/utils/tagColors'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Tooltip, Legend, Title, Filler
} from 'chart.js'
import PCIPassthrough from '@/components/PCIPassthrough.vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import { parseProxmoxDisk, parseProxmoxNIC, formatBytes, formatUptime, cpuPercent } from '@/utils/proxmox'
import { copyToClipboard } from '@/utils/clipboard'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Title, Filler)

const DISK_KEYS = [
  'ide0','ide1','ide2','ide3',
  'sata0','sata1','sata2','sata3','sata4','sata5',
  'scsi0','scsi1','scsi2','scsi3','scsi4','scsi5','scsi6','scsi7',
  'scsi8','scsi9','scsi10','scsi11','scsi12','scsi13','scsi14','scsi15',
  'virtio0','virtio1','virtio2','virtio3','virtio4','virtio5',
  'virtio6','virtio7','virtio8','virtio9','virtio10','virtio11','virtio12','virtio13',
]
const NIC_KEYS = ['net0','net1','net2','net3','net4','net5','net6','net7']

const route = useRoute()
const router = useRouter()
const toast = useToast()

const hostId = computed(() => route.params.hostId)
const node = computed(() => route.params.node)
const vmid = computed(() => route.params.vmid)

// Core state
const config = ref(null)
const vmStatus = ref(null)
const loadingInit = ref(true)
const actioning = ref(false)
const savingConfig = ref(false)
const editingConfig = ref(false)
const editingNotes = ref(false)
const savingNotes = ref(false)
const notesText = ref('')
const activeTab = ref('overview')

// ── Access tab state ───────────────────────────────────────────────────────────
const vmAclAll = ref([])
const loadingVmAcl = ref(false)
const showVmGrantModal = ref(false)
const savingVmAcl = ref(false)
const vmRoles = ref([])
const loadingVmRoles = ref(false)
const vmAclForm = ref({ ugid: '', ugtype: 'user', roleid: '', propagate: 1 })

const vmAclDirect = computed(() =>
  vmAclAll.value.filter(e => e.path === `/vms/${vmid.value}`)
)
const vmAclInherited = computed(() =>
  vmAclAll.value.filter(e => e.path !== `/vms/${vmid.value}` && e.propagate)
)

const loadVmAcl = async () => {
  loadingVmAcl.value = true
  try {
    const resp = await api.pveNode.listAcl(hostId.value)
    const all = resp.data || []
    const vmPath = `/vms/${vmid.value}`
    // Direct: entries explicitly on this VM path
    // Inherited: entries on parent paths with propagate=1 (e.g. /, /pools/...)
    vmAclAll.value = all.filter(e => {
      if (e.path === vmPath) return true
      // Inherited if propagate and path is an ancestor (/, /pools/...)
      if (e.propagate && (e.path === '/' || e.path.startsWith('/pools/'))) return true
      return false
    })
  } catch (e) {
    console.error('Failed to load VM ACL', e)
    toast.error('Failed to load VM access control')
  } finally {
    loadingVmAcl.value = false
  }
}

const loadVmRoles = async () => {
  if (vmRoles.value.length > 0) return
  loadingVmRoles.value = true
  try {
    const resp = await api.pveNode.listRoles(hostId.value)
    vmRoles.value = resp.data || []
  } catch (e) {
    console.error('Failed to load roles', e)
  } finally {
    loadingVmRoles.value = false
  }
}

const openVmGrantModal = async () => {
  vmAclForm.value = { ugid: '', ugtype: 'user', roleid: '', propagate: 1 }
  showVmGrantModal.value = true
  await loadVmRoles()
}

const doGrantVmAcl = async () => {
  savingVmAcl.value = true
  try {
    await api.pveNode.updateAcl(hostId.value, {
      path: `/vms/${vmid.value}`,
      roles: vmAclForm.value.roleid,
      ugid: vmAclForm.value.ugid,
      delete: 0,
      propagate: vmAclForm.value.propagate,
    })
    toast.success('Access granted')
    showVmGrantModal.value = false
    await loadVmAcl()
  } catch (e) {
    console.error(e)
    toast.error(e.response?.data?.detail || 'Failed to grant access')
  } finally {
    savingVmAcl.value = false
  }
}

const revokeVmAcl = async (entry) => {
  if (!confirm(`Remove "${entry.roleid}" on /vms/${vmid.value} for "${entry.ugid}"?`)) return
  try {
    await api.pveNode.updateAcl(hostId.value, {
      path: entry.path,
      roles: entry.roleid,
      ugid: entry.ugid,
      delete: 1,
      propagate: entry.propagate ? 1 : 0,
    })
    toast.success('Access revoked')
    await loadVmAcl()
  } catch (e) {
    console.error(e)
    toast.error('Failed to revoke access')
  }
}

// Tab data
const snapshots = ref([])
const loadingSnapshots = ref(false)
const selectedSnaps = ref(new Set())
const collapsedSnaps = ref(new Set())
const firewallRules = ref([])
const firewallOptions = ref(null)
const loadingFirewall = ref(false)
const storageList = ref([])
const clusterNodes = ref([])
const rrdData = ref(null)
const rrdTimeframe = ref('hour')

// ── Performance tab state ──────────────────────────────────────────────────────
const perfRrdData = ref([])
const perfTimeframe = ref('hour')
const loadingPerf = ref(false)
const chartH = 120

const perfTimeRanges = [
  { label: '1h', value: 'hour' },
  { label: '6h', value: 'day' },
  { label: '24h', value: 'day' },
  { label: '1w', value: 'week' },
]

const vmCpuData = computed(() =>
  perfRrdData.value
    .filter(d => d.cpu != null && isFinite(d.cpu))
    .map(d => ({ time: d.time, value: d.cpu * 100 }))
)

const vmMemData = computed(() =>
  perfRrdData.value
    .filter(d => d.mem != null && d.maxmem)
    .map(d => ({ time: d.time, value: (d.mem / d.maxmem) * 100 }))
)

const vmDiskReadData = computed(() =>
  perfRrdData.value
    .filter(d => d.diskread != null && isFinite(d.diskread))
    .map(d => ({ time: d.time, value: d.diskread / 1e6 }))
)

const vmDiskWriteData = computed(() =>
  perfRrdData.value
    .filter(d => d.diskwrite != null && isFinite(d.diskwrite))
    .map(d => ({ time: d.time, value: d.diskwrite / 1e6 }))
)

const vmNetInData = computed(() =>
  perfRrdData.value
    .filter(d => d.netin != null && isFinite(d.netin))
    .map(d => ({ time: d.time, value: d.netin / 1e6 }))
)

const vmNetOutData = computed(() =>
  perfRrdData.value
    .filter(d => d.netout != null && isFinite(d.netout))
    .map(d => ({ time: d.time, value: d.netout / 1e6 }))
)

const latestPerfVal = (series) => {
  if (!series.length) return 0
  return series[series.length - 1].value
}

const formatPerfMBs = (v) => {
  if (v == null || !isFinite(v)) return '—'
  if (v >= 1) return v.toFixed(2) + ' MB/s'
  if (v >= 0.001) return (v * 1000).toFixed(1) + ' KB/s'
  return (v * 1e6).toFixed(0) + ' B/s'
}

const setPerfTimeframe = (tf) => {
  perfTimeframe.value = tf
  loadPerfRrd()
}

const loadPerfRrd = async () => {
  loadingPerf.value = true
  try {
    const res = await api.pveVm.getRrdData(hostId.value, node.value, vmid.value, {
      timeframe: perfTimeframe.value,
      cf: 'AVERAGE',
    })
    perfRrdData.value = res.data || []
  } catch (e) {
    console.warn('Perf RRD failed', e)
    perfRrdData.value = []
  } finally {
    loadingPerf.value = false
  }
}

// Pending config changes
const pendingChanges = ref([])
const loadingPending = ref(false)
const pendingLoaded = ref(false)
const pendingExpanded = ref(true)

// Modal visibility
const showDeleteConfirm = ref(false)
const showCloneModal = ref(false)
const showMigrateModal = ref(false)
const showAddDiskModal = ref(false)
const showResizeModal = ref(false)
const showAddNicModal = ref(false)
const showSnapshotModal = ref(false)
const showQuickSnapshotModal = ref(false)
const showCompareModal = ref(false)
const showQuickSnapProgress = ref(false)
const showFirewallModal = ref(false)
const showEditNicModal = ref(false)
const showMoveDiskModal = ref(false)
const showReattachModal = ref(false)

// Resize disk state
const resizeDiskKey = ref('')
const resizeDiskCurrentSize = ref('')
const resizeSize = ref('')

// Move disk state
const moveDiskKey = ref('')
const moveDiskForm = ref({ storage: '', format: '', delete_source: false })

// Reattach unused disk state
const reattachDiskKey = ref('')
const reattachVolid = ref('')
const reattachBus = ref('scsi')

// Unused disks state
const unusedDisks = ref([])
const loadingUnused = ref(false)

// Add disk mode + enhancements
const addDiskMode = ref('new')
const storageImages = ref([])
const storageImagesLoading = ref(false)

// Boot order state (mirrors parsedDisks order, editable)
const diskBootOrder = ref([])

const imgFileName = (volid) => {
  if (!volid) return '—'
  const segs = (volid.includes(':') ? volid.split(':')[1] : volid).split('/')
  return segs[segs.length - 1]
}

const fmtBytes = (bytes) => {
  if (!bytes) return '0 B'
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

// Edit NIC state
const editNicKey = ref('')
const editNicForm = ref({ model: 'virtio', bridge: 'vmbr0', tag: null, rate: null, firewall: false })

// Tag management
const tagList = computed(() => {
  if (!config.value?.tags) return []
  return config.value.tags.split(';').map(t => t.trim()).filter(Boolean)
})
const showTagInput = ref(false)
const newTagValue = ref('')
const savingTags = ref(false)
const tagInputRef = ref(null)

const tagColor = _tagColorUtil

const openTagInput = async () => {
  showTagInput.value = true
  newTagValue.value = ''
  await nextTick()
  tagInputRef.value?.focus()
}

const cancelTagInput = () => {
  showTagInput.value = false
  newTagValue.value = ''
}

const sanitizeTag = (val) => val.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\-_]/g, '')

const addTag = async () => {
  const tag = sanitizeTag(newTagValue.value.trim())
  if (!tag) { cancelTagInput(); return }
  if (tagList.value.includes(tag)) {
    toast.warning(`Tag "${tag}" already exists`)
    return
  }
  const newTags = [...tagList.value, tag].join(';')
  await saveTags(newTags)
  cancelTagInput()
}

const removeTag = async (tag) => {
  const newTags = tagList.value.filter(t => t !== tag).join(';')
  await saveTags(newTags)
}

const saveTags = async (tagsString) => {
  savingTags.value = true
  try {
    await api.pveVm.updateConfig(hostId.value, node.value, vmid.value, { tags: tagsString })
    await loadConfig()
    toast.success('Tags updated')
  } catch (e) {
    console.error(e)
    toast.error('Failed to update tags')
  } finally {
    savingTags.value = false
  }
}

// Edit config form
const editConfig = ref({})

// Inline config editing (per-field save, used by Config tab)
const inlineEdit = ref({
  name: '', cores: 1, memory: 512, cpu: 'host', bios: 'seabios',
  machine: '', boot: '', sockets: 1, balloon: 0, description: '',
  numa: 0, agent: 0, onboot: 0, protection: 0,
})
const savingField = ref({})

const saveInlineField = async (field, value) => {
  savingField.value = { ...savingField.value, [field]: true }
  try {
    const payload = { [field]: value }
    await api.pveVm.updateConfig(hostId.value, node.value, vmid.value, payload)
    toast.success(`${field} saved`)
    await loadConfig()
    inlineEdit.value[field] = config.value[field] ?? value
  } catch (e) {
    console.error(e)
    toast.error(`Failed to save ${field}`)
  } finally {
    savingField.value = { ...savingField.value, [field]: false }
  }
}

// Modal forms
const cloneForm = ref({ newid: null, name: '', full: true, storage: '', target: '' })
const migrateForm = ref({ target: '', online: true, with_local_disks: true, bwlimit: 0 })

// Migrate — target storage
const targetStorageList = ref([])
const loadingTargetStorage = ref(false)
const migrateStorageMap = ref({})   // { diskKey: targetStorageName }

// Migrate — task progress
const showMigrateProgress = ref(false)
const migrateSubmitting = ref(false)
const migrateUpid = ref('')
const addDiskForm = ref({
  storage: '', size: 32, bus: 'scsi', format: 'qcow2',
  cache: '', ssd: false, discard: false, backup: true, iothread: false, replicate: true,
  browse_storage: '', import_volid: '',
})
const addNicForm = ref({ bridge: 'vmbr0', model: 'virtio', tag: null })
const snapshotForm = ref({ snapname: '', description: '', vmstate: false })
const quickSnapForm = ref({ snapname: '', description: '' })
const quickSnapUpid = ref('')
const compareSnaps = ref([])
const compareLeft = ref({})
const compareRight = ref({})
const loadingCompare = ref(false)
const firewallForm = ref({ type: 'in', action: 'ACCEPT', proto: '', source: '', dest: '', dport: '', comment: '', enable: 1 })

// ── Hardware tab state ────────────────────────────────────────────────────────
const showAddUsbModal = ref(false)
const savingUsb = ref(false)
const removingUsb = ref(null)
const removingSerial = ref(null)
const addingSerial = ref(false)
const usbDevices = ref([])
const addUsbForm = ref({ host: '', usb3: false })

const attachedUsbDevices = computed(() => {
  const result = []
  const cfg = config.value || {}
  for (let i = 0; i < 8; i++) {
    const key = `usb${i}`
    if (cfg[key]) {
      const val = cfg[key]
      const parts = val.split(',')
      const hostPart = parts.find(p => p.startsWith('host='))
      const host = hostPart ? hostPart.replace('host=', '') : val
      const usb3 = parts.some(p => p === 'usb3=1')
      result.push({ key, index: i, host, usb3 })
    }
  }
  return result
})

const attachedSerialPorts = computed(() => {
  const result = []
  const cfg = config.value || {}
  for (let i = 0; i < 4; i++) {
    const key = `serial${i}`
    if (cfg[key]) {
      result.push({ key, index: i, type: cfg[key] })
    }
  }
  return result
})

const availableNodes = computed(() => {
  return clusterNodes.value.map(n => n.node || n)
})

const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'config', label: 'Config' },
  { id: 'disks', label: 'Disks' },
  { id: 'network', label: 'Network' },
  { id: 'snapshots', label: 'Snapshots' },
  { id: 'firewall', label: 'Firewall' },
  { id: 'schedule', label: 'Power Schedule' },
  { id: 'performance', label: 'Performance' },
  { id: 'console', label: 'Console' },
  { id: 'access', label: 'Access' },
  { id: 'hardware', label: 'Hardware' },
]

let pollInterval = null

// ── Computed ──────────────────────────────────────────────────────────────────

const statusBadgeClass = computed(() => {
  const s = vmStatus.value?.status
  if (s === 'running') return 'badge badge-success ml-1'
  if (s === 'stopped') return 'badge badge-danger ml-1'
  if (s === 'suspended') return 'badge badge-warning ml-1'
  return 'badge badge-info ml-1'
})

const cpuPct = computed(() => cpuPercent(vmStatus.value))

// ── Snapshot Tree ──────────────────────────────────────────────────────────────

const snapshotTree = computed(() => {
  if (!snapshots.value.length) return []
  const byName = {}
  snapshots.value.forEach(s => { byName[s.name] = { ...s, _children: [] } })
  const roots = []
  snapshots.value.forEach(s => {
    const parent = s.parent
    if (!parent || parent === 'current' || !byName[parent]) {
      if (s.name !== 'current') roots.push(byName[s.name])
    } else {
      byName[parent]._children.push(byName[s.name])
    }
  })
  // Put "current" node first always
  const currentNode = byName['current']

  const flatten = (nodes, depth, parentCollapsed) => {
    const result = []
    nodes.forEach((node, idx) => {
      if (parentCollapsed) return
      const isLast = idx === nodes.length - 1
      const hasChildren = node._children.length > 0
      const isCollapsed = collapsedSnaps.value.has(node.name)
      result.push({ ...node, _depth: depth, _isLast: isLast, _hasChildren: hasChildren })
      if (hasChildren && !isCollapsed) {
        result.push(...flatten(node._children, depth + 1, false))
      }
    })
    return result
  }

  const treeRows = currentNode ? [{ ...currentNode, _depth: 0, _isLast: true, _hasChildren: false }] : []
  treeRows.push(...flatten(roots, 0, false))
  return treeRows
})

// ── Compare Computed ───────────────────────────────────────────────────────────

const compareOnlyLeft = computed(() => {
  return Object.keys(compareLeft.value).filter(k => !(k in compareRight.value))
})

const compareOnlyRight = computed(() => {
  return Object.keys(compareRight.value).filter(k => !(k in compareLeft.value))
})

const compareIdentical = computed(() => {
  const allKeys = new Set([...Object.keys(compareLeft.value), ...Object.keys(compareRight.value)])
  for (const k of allKeys) {
    if (String(compareLeft.value[k] ?? '') !== String(compareRight.value[k] ?? '')) return false
  }
  return true
})

const compareRowClass = (key, side) => {
  const lVal = String(compareLeft.value[key] ?? '')
  const rVal = String(compareRight.value[key] ?? '')
  const onlyInSide = side === 'left' ? !(key in compareRight.value) : !(key in compareLeft.value)
  if (onlyInSide) return 'compare-row--only'
  if (lVal !== rVal) return 'compare-row--diff'
  return ''
}

const parsedDisks = computed(() => {
  if (!config.value) return []
  return DISK_KEYS
    .filter(k => config.value[k])
    .map(k => ({ key: k, raw: config.value[k], parsed: parseProxmoxDisk(config.value[k]) }))
    .filter(d => d.parsed)
})

const parsedNics = computed(() => {
  if (!config.value) return []
  return NIC_KEYS
    .filter(k => config.value[k])
    .map(k => ({ key: k, raw: config.value[k], parsed: parseProxmoxNIC(config.value[k]) }))
    .filter(n => n.parsed)
})

const cpuChartData = computed(() => {
  if (!rrdData.value?.length) return null
  const labels = rrdData.value.map(d => d.time ? new Date(d.time * 1000).toLocaleTimeString() : '')
  return {
    labels,
    datasets: [{
      label: 'CPU %',
      data: rrdData.value.map(d => d.cpu != null ? parseFloat((d.cpu * 100).toFixed(1)) : null),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.1)',
      fill: true, tension: 0.3, pointRadius: 0,
    }]
  }
})

const memChartData = computed(() => {
  if (!rrdData.value?.length) return null
  const labels = rrdData.value.map(d => d.time ? new Date(d.time * 1000).toLocaleTimeString() : '')
  return {
    labels,
    datasets: [{
      label: 'Memory %',
      data: rrdData.value.map(d => {
        if (d.mem != null && d.maxmem && d.maxmem > 0) {
          return parseFloat(((d.mem / d.maxmem) * 100).toFixed(1))
        }
        return null
      }),
      borderColor: '#10b981',
      backgroundColor: 'rgba(16,185,129,0.1)',
      fill: true, tension: 0.3, pointRadius: 0,
    }]
  }
})

const lineChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { maxTicksLimit: 8, color: '#9ca3af' }, grid: { color: '#374151' } },
    y: { min: 0, max: 100, ticks: { color: '#9ca3af', callback: v => v + '%' }, grid: { color: '#374151' } }
  }
}

// ── Data Loading ──────────────────────────────────────────────────────────────

const loadConfig = async () => {
  const res = await api.pveVm.getConfig(hostId.value, node.value, vmid.value)
  config.value = res.data
  // Sync inlineEdit with fresh config
  const c = res.data
  inlineEdit.value = {
    name: c.name || '',
    cores: c.cores || 1,
    memory: c.memory || 512,
    cpu: c.cpu || 'host',
    bios: c.bios || 'seabios',
    machine: c.machine || '',
    boot: c.boot || '',
    sockets: c.sockets || 1,
    balloon: c.balloon ?? 0,
    description: c.description || '',
    numa: c.numa || 0,
    agent: c.agent || 0,
    onboot: c.onboot || 0,
    protection: c.protection || 0,
  }
  // Sync boot order from config
  _syncBootOrder(c)
}

const _syncBootOrder = (c) => {
  // Parse "order=scsi0;net0;ide2" from boot config
  const bootStr = c.boot || ''
  const orderMatch = bootStr.match(/order=([^,]+)/)
  const diskKeys = DISK_KEYS.filter(k => c[k])
  if (orderMatch) {
    const ordered = orderMatch[1].split(';').filter(k => diskKeys.includes(k))
    const rest = diskKeys.filter(k => !ordered.includes(k))
    diskBootOrder.value = [...ordered, ...rest].map(k => ({ key: k }))
  } else {
    diskBootOrder.value = diskKeys.map(k => ({ key: k }))
  }
}

const loadStatus = async () => {
  try {
    const res = await api.pveVm.getStatus(hostId.value, node.value, vmid.value)
    vmStatus.value = res.data
  } catch (e) {
    console.warn('Status poll failed', e)
  }
}

const loadRrd = async () => {
  try {
    const res = await api.pveVm.getRrdData(hostId.value, node.value, vmid.value, { timeframe: rrdTimeframe.value, cf: 'AVERAGE' })
    rrdData.value = res.data
  } catch (e) {
    console.warn('RRD failed', e)
  }
}

const loadSnapshots = async () => {
  loadingSnapshots.value = true
  try {
    const res = await api.pveVm.listSnapshots(hostId.value, node.value, vmid.value)
    snapshots.value = res.data || []
    selectedSnaps.value = new Set()
  } catch (e) {
    console.warn('Snapshots failed', e)
  } finally {
    loadingSnapshots.value = false
  }
}

const loadFirewall = async () => {
  loadingFirewall.value = true
  try {
    const [rulesRes, optsRes] = await Promise.all([
      api.pveVm.getFirewallRules(hostId.value, node.value, vmid.value),
      api.pveVm.getFirewallOptions(hostId.value, node.value, vmid.value).catch(() => ({ data: {} }))
    ])
    firewallRules.value = rulesRes.data || []
    firewallOptions.value = optsRes.data || {}
  } catch (e) {
    console.warn('Firewall load failed', e)
  } finally {
    loadingFirewall.value = false
  }
}

const loadStorage = async () => {
  try {
    const res = await api.pveNode.listStorage(hostId.value, node.value)
    storageList.value = res.data || []
    if (storageList.value.length && !addDiskForm.value.storage) {
      addDiskForm.value.storage = storageList.value[0].storage
    }
  } catch (e) {
    console.warn('Storage load failed', e)
  }
}

const loadClusterNodes = async () => {
  try {
    const res = await api.pveNode.clusterResources(hostId.value)
    const allNodes = (res.data || []).filter(r => r.type === 'node' && r.node !== node.value)
    // Deduplicate by node name
    const seen = new Set()
    clusterNodes.value = allNodes.filter(n => {
      if (seen.has(n.node)) return false
      seen.add(n.node)
      return true
    })
  } catch (e) {
    console.warn('Cluster nodes failed', e)
  }
}

const loadPending = async () => {
  loadingPending.value = true
  try {
    const res = await api.pveVm.vmPending(hostId.value, node.value, vmid.value)
    const raw = res.data || []
    pendingChanges.value = raw.filter(item => item.pending !== undefined && item.pending !== null)
    pendingLoaded.value = true
  } catch (e) {
    console.warn('Pending config load failed', e)
  } finally {
    loadingPending.value = false
  }
}

const loadNextId = async () => {
  try {
    const res = await api.pveNode.nextId(hostId.value)
    cloneForm.value.newid = res.data?.nextid || res.data
  } catch (e) {
    console.warn('nextid failed', e)
  }
}

const loadAll = async () => {
  loadingInit.value = true
  try {
    await Promise.all([loadConfig(), loadStatus()])
    await Promise.all([loadRrd(), loadStorage(), loadClusterNodes()])
  } catch (e) {
    console.error('Failed to load VM detail', e)
  } finally {
    loadingInit.value = false
  }
}

// ── Tab Management ─────────────────────────────────────────────────────────────

const switchTab = (tab) => {
  activeTab.value = tab
  if (tab === 'snapshots') loadSnapshots()
  if (tab === 'firewall') loadFirewall()
  if (tab === 'overview') { loadStatus(); loadRrd() }
  if (tab === 'config') loadPending()
  if (tab === 'performance') loadPerfRrd()
  if (tab === 'disks') loadUnusedDisks()
  if (tab === 'access') { loadVmAcl(); loadVmRoles() }
  if (tab === 'hardware') { loadUsbDevices() }
}


// ── Hardware tab — USB / Serial management ────────────────────────────────────

const loadUsbDevices = async () => {
  if (!node.value) return
  try {
    const res = await api.pveNode.listUsbDevices(hostId.value, node.value)
    usbDevices.value = res.data || []
  } catch {
    usbDevices.value = []
  }
}

const doAddUsb = async () => {
  if (!addUsbForm.value.host) return
  savingUsb.value = true
  try {
    await api.pveVm.addUsbDevice(hostId.value, node.value, vmid.value, {
      host: addUsbForm.value.host,
      usb3: addUsbForm.value.usb3,
    })
    toast.success('USB device added to VM config')
    showAddUsbModal.value = false
    addUsbForm.value = { host: '', usb3: false }
    await loadConfig()
  } catch (e) {
    toast.error('Failed to add USB device: ' + (e.response?.data?.detail || e.message))
  } finally {
    savingUsb.value = false
  }
}

const removeUsb = async (dev) => {
  if (!confirm(`Remove ${dev.key} (${dev.host}) from VM config?`)) return
  removingUsb.value = dev.key
  try {
    await api.pveVm.removeUsbDevice(hostId.value, node.value, vmid.value, dev.index)
    toast.success(`${dev.key} removed from VM config`)
    await loadConfig()
  } catch (e) {
    toast.error('Failed to remove USB device: ' + (e.response?.data?.detail || e.message))
  } finally {
    removingUsb.value = null
  }
}

const addSerialSocket = async () => {
  addingSerial.value = true
  try {
    await api.pveVm.addSerialPort(hostId.value, node.value, vmid.value, { type: 'socket' })
    toast.success('Serial port (socket) added to VM config')
    await loadConfig()
  } catch (e) {
    toast.error('Failed to add serial port: ' + (e.response?.data?.detail || e.message))
  } finally {
    addingSerial.value = false
  }
}

const removeSerial = async (port) => {
  if (!confirm(`Remove ${port.key} from VM config?`)) return
  removingSerial.value = port.key
  try {
    await api.pveVm.removeSerialPort(hostId.value, node.value, vmid.value, port.index)
    toast.success(`${port.key} removed from VM config`)
    await loadConfig()
  } catch (e) {
    toast.error('Failed to remove serial port: ' + (e.response?.data?.detail || e.message))
  } finally {
    removingSerial.value = null
  }
}

// ── Polling ────────────────────────────────────────────────────────────────────

const startPolling = () => {
  pollInterval = setInterval(() => {
    if (activeTab.value === 'overview' && vmStatus.value?.status === 'running') {
      loadStatus()
    }
  }, 5000)
}

// ── VM Actions ─────────────────────────────────────────────────────────────────

const vmAction = async (action) => {
  actioning.value = true
  try {
    const fnMap = {
      start: api.pveVm.start,
      stop: api.pveVm.stop,
      shutdown: api.pveVm.shutdown,
      reboot: api.pveVm.reboot,
      reset: api.pveVm.reset,
      suspend: api.pveVm.suspend,
      resume: api.pveVm.resume,
    }
    await fnMap[action](hostId.value, node.value, vmid.value)
    toast.success(`VM ${action} initiated`)
    setTimeout(loadStatus, 2000)
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const doDeleteVM = async () => {
  actioning.value = true
  try {
    await api.pveVm.deleteVm(hostId.value, node.value, vmid.value)
    toast.success('VM deletion started')
    router.push(`/proxmox/${hostId.value}/nodes/${node.value}`)
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
    showDeleteConfirm.value = false
  }
}

const doConvertToTemplate = async () => {
  if (!confirm('Convert this VM to a template? This is irreversible.')) return
  actioning.value = true
  try {
    await api.pveVm.convertToTemplate(hostId.value, node.value, vmid.value)
    toast.success('Converted to template')
    await loadConfig()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

// ── Config Tab ──────────────────────────────────────────────────────────────────

const startEditConfig = () => {
  editConfig.value = {
    name: config.value.name || '',
    description: config.value.description || '',
    tags: config.value.tags || '',
    cores: config.value.cores || 1,
    sockets: config.value.sockets || 1,
    memory: config.value.memory || 512,
    balloon: config.value.balloon ?? 0,
    cpu: config.value.cpu || 'host',
    boot: config.value.boot || '',
    bios: config.value.bios || '',
    machine: config.value.machine || '',
    onboot: !!config.value.onboot,
    protection: !!config.value.protection,
  }
  editingConfig.value = true
}

const cancelEditConfig = () => {
  editingConfig.value = false
}

const saveConfig = async () => {
  savingConfig.value = true
  try {
    const payload = { ...editConfig.value }
    // Remove empty optional strings
    Object.keys(payload).forEach(k => {
      if (payload[k] === '' || payload[k] === null) delete payload[k]
    })
    await api.pveVm.updateConfig(hostId.value, node.value, vmid.value, payload)
    toast.success('Configuration saved')
    editingConfig.value = false
    await loadConfig()
  } catch (e) {
    console.error(e)
  } finally {
    savingConfig.value = false
  }
}

// ── Notes Actions ──────────────────────────────────────────────────────────────

const startEditNotes = () => {
  notesText.value = config.value.description || ''
  editingNotes.value = true
}

const cancelEditNotes = () => {
  editingNotes.value = false
}

const saveNotes = async () => {
  savingNotes.value = true
  try {
    await api.pveVm.updateConfig(hostId.value, node.value, vmid.value, { description: notesText.value })
    toast.success('Notes saved')
    editingNotes.value = false
    await loadConfig()
  } catch (e) {
    console.error(e)
    toast.error('Failed to save notes')
  } finally {
    savingNotes.value = false
  }
}

// ── Disk Actions ───────────────────────────────────────────────────────────────

const openAddDiskModal = () => {
  addDiskMode.value = 'new'
  addDiskForm.value = {
    storage: storageList.value[0]?.storage || '', size: 32, bus: 'scsi', format: 'qcow2',
    cache: '', ssd: false, discard: false, backup: true, iothread: false, replicate: true,
    browse_storage: '', import_volid: '',
  }
  storageImages.value = []
  showAddDiskModal.value = true
}

const openResizeDisk = (disk) => {
  resizeDiskKey.value = disk.key
  resizeDiskCurrentSize.value = disk.parsed.size || 'unknown'
  resizeSize.value = ''
  showResizeModal.value = true
}

const doResizeDisk = async () => {
  if (!resizeSize.value) return
  actioning.value = true
  try {
    await api.pveVm.resizeDisk(hostId.value, node.value, vmid.value, resizeDiskKey.value, { size: resizeSize.value })
    toast.success('Disk resize initiated')
    showResizeModal.value = false
    await loadConfig()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const detachDisk = async (diskKey) => {
  if (!confirm(`Detach disk ${diskKey}? The disk will be kept as an unused volume.`)) return
  actioning.value = true
  try {
    await api.pveVm.deleteDisk(hostId.value, node.value, vmid.value, diskKey)
    toast.success('Disk detached')
    await loadConfig()
    await loadUnusedDisks()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const doAddDisk = async () => {
  if (!addDiskForm.value.storage) {
    toast.error('Please select a storage')
    return
  }
  actioning.value = true
  try {
    if (addDiskMode.value === 'existing' && addDiskForm.value.import_volid) {
      // Reattach an existing image by importing via move_disk workaround
      // We attach the volid directly to a bus slot
      const busKey = addDiskForm.value.bus
      const payload = { [busKey + '0']: addDiskForm.value.import_volid }
      await api.pveVm.updateConfig(hostId.value, node.value, vmid.value, payload)
      toast.success('Existing disk attached')
    } else {
      await api.pveVm.addDisk(hostId.value, node.value, vmid.value, {
        storage: addDiskForm.value.storage,
        size: addDiskForm.value.size,
        bus: addDiskForm.value.bus,
        format: addDiskForm.value.format,
        cache: addDiskForm.value.cache,
        ssd: addDiskForm.value.ssd,
        discard: addDiskForm.value.discard,
        backup: addDiskForm.value.backup,
        iothread: addDiskForm.value.iothread,
        replicate: addDiskForm.value.replicate,
      })
      toast.success('Disk added')
    }
    showAddDiskModal.value = false
    await loadConfig()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const loadStorageImages = async () => {
  const storage = addDiskForm.value.browse_storage
  if (!storage) return
  storageImagesLoading.value = true; storageImages.value = []
  try {
    const res = await api.pveNode.browseStorage(hostId.value, node.value, storage, { content: 'images' })
    storageImages.value = (res.data || []).filter(f => {
      const n = f.volid || ''
      return /\.(qcow2|vmdk|raw|img|vhd|vhdx)$/i.test(n)
    })
  } catch (e) { console.warn('Storage image browse failed', e) }
  finally { storageImagesLoading.value = false }
}

// Move disk
const openMoveDisk = (disk) => {
  moveDiskKey.value = disk.key
  moveDiskForm.value = { storage: '', format: '', delete_source: false }
  showMoveDiskModal.value = true
}

const doMoveDisk = async () => {
  if (!moveDiskForm.value.storage) { toast.error('Select a target storage'); return }
  actioning.value = true
  try {
    await api.pveVm.moveDisk(hostId.value, node.value, vmid.value, {
      disk: moveDiskKey.value,
      storage: moveDiskForm.value.storage,
      format: moveDiskForm.value.format || undefined,
      delete_source: moveDiskForm.value.delete_source,
    })
    toast.success('Disk move started')
    showMoveDiskModal.value = false
    await loadConfig()
  } catch (e) {
    console.error(e)
    toast.error('Move disk failed')
  } finally { actioning.value = false }
}

// Unused disks
const loadUnusedDisks = async () => {
  loadingUnused.value = true
  try {
    const res = await api.pveVm.listUnusedDisks(hostId.value, node.value, vmid.value)
    unusedDisks.value = res.data || []
  } catch (e) { console.warn('Unused disks failed', e) }
  finally { loadingUnused.value = false }
}

const openReattachDisk = (ud) => {
  reattachDiskKey.value = ud.key
  reattachVolid.value = ud.volid
  reattachBus.value = 'scsi'
  showReattachModal.value = true
}

const doReattachDisk = async () => {
  actioning.value = true
  try {
    await api.pveVm.reattachDisk(hostId.value, node.value, vmid.value, reattachDiskKey.value, reattachBus.value)
    toast.success('Disk reattached')
    showReattachModal.value = false
    await loadConfig()
    await loadUnusedDisks()
  } catch (e) {
    console.error(e)
    toast.error('Reattach failed')
  } finally { actioning.value = false }
}

const deleteUnused = async (ud) => {
  if (!confirm(`Delete unused disk ${ud.key} (${ud.volid})? This cannot be undone.`)) return
  actioning.value = true
  try {
    await api.pveVm.updateConfig(hostId.value, node.value, vmid.value, { [ud.key]: null })
    toast.success('Unused disk deleted')
    await loadUnusedDisks()
  } catch (e) {
    console.error(e)
    toast.error('Delete failed')
  } finally { actioning.value = false }
}

// Boot order
const moveBootOrder = (idx, dir) => {
  const arr = [...diskBootOrder.value]
  const newIdx = idx + dir
  if (newIdx < 0 || newIdx >= arr.length) return
  ;[arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]]
  diskBootOrder.value = arr
}

const saveBootOrder = async () => {
  actioning.value = true
  try {
    const orderStr = 'order=' + diskBootOrder.value.map(d => d.key).join(';')
    await api.pveVm.updateConfig(hostId.value, node.value, vmid.value, { boot: orderStr })
    toast.success('Boot order saved')
    await loadConfig()
  } catch (e) {
    console.error(e)
    toast.error('Failed to save boot order')
  } finally { actioning.value = false }
}

// ── NIC Actions ────────────────────────────────────────────────────────────────

const removeNic = async (nicKey) => {
  if (!confirm(`Remove NIC ${nicKey}?`)) return
  actioning.value = true
  try {
    await api.pveVm.deleteNic(hostId.value, node.value, vmid.value, nicKey)
    toast.success('NIC removed')
    await loadConfig()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const doAddNic = async () => {
  if (!addNicForm.value.bridge) {
    toast.error('Please enter a bridge name')
    return
  }
  actioning.value = true
  try {
    const payload = { ...addNicForm.value }
    if (!payload.tag) delete payload.tag
    await api.pveVm.addNic(hostId.value, node.value, vmid.value, payload)
    toast.success('NIC added')
    showAddNicModal.value = false
    addNicForm.value = { bridge: 'vmbr0', model: 'virtio', tag: null }
    await loadConfig()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const openEditNic = (nic) => {
  editNicKey.value = nic.key
  editNicForm.value = {
    model: nic.parsed.model || 'virtio',
    bridge: nic.parsed.bridge || 'vmbr0',
    tag: nic.parsed.vlan ? parseInt(nic.parsed.vlan) : null,
    rate: nic.parsed.rate ? parseFloat(nic.parsed.rate) : null,
    firewall: !!nic.parsed.firewall,
  }
  showEditNicModal.value = true
}

const doEditNic = async () => {
  if (!editNicForm.value.bridge) {
    toast.error('Please enter a bridge name')
    return
  }
  actioning.value = true
  try {
    // Build Proxmox NIC string: model=MAC,bridge=br,tag=n,firewall=0/1,rate=n
    const f = editNicForm.value
    // preserve original MAC by extracting from raw config
    const rawNic = parsedNics.value.find(n => n.key === editNicKey.value)
    const mac = rawNic?.parsed.mac || ''
    let nicStr = `${f.model}=${mac}`
    nicStr += `,bridge=${f.bridge}`
    if (f.tag) nicStr += `,tag=${f.tag}`
    if (f.rate) nicStr += `,rate=${f.rate}`
    nicStr += `,firewall=${f.firewall ? 1 : 0}`
    await api.pveVm.updateConfig(hostId.value, node.value, vmid.value, { [editNicKey.value]: nicStr })
    toast.success(`${editNicKey.value} updated`)
    showEditNicModal.value = false
    await loadConfig()
  } catch (e) {
    console.error(e)
    toast.error('Failed to update NIC')
  } finally {
    actioning.value = false
  }
}

const toggleNicFirewall = async (nic) => {
  actioning.value = true
  try {
    const mac = nic.parsed.mac || ''
    const newFirewall = nic.parsed.firewall ? 0 : 1
    let nicStr = `${nic.parsed.model}=${mac}`
    nicStr += `,bridge=${nic.parsed.bridge || 'vmbr0'}`
    if (nic.parsed.vlan) nicStr += `,tag=${nic.parsed.vlan}`
    if (nic.parsed.rate) nicStr += `,rate=${nic.parsed.rate}`
    nicStr += `,firewall=${newFirewall}`
    await api.pveVm.updateConfig(hostId.value, node.value, vmid.value, { [nic.key]: nicStr })
    toast.success(`Firewall ${newFirewall ? 'enabled' : 'disabled'} for ${nic.key}`)
    await loadConfig()
  } catch (e) {
    console.error(e)
    toast.error('Failed to toggle firewall')
  } finally {
    actioning.value = false
  }
}

// ── Disk Helpers ──────────────────────────────────────────────────────────────

const formatDiskSize = (sizeStr) => {
  if (!sizeStr) return '—'
  // Proxmox size strings: 32G, 512M, 1T, 100K
  const match = sizeStr.match(/^([0-9.]+)([KMGT]?)$/i)
  if (!match) return sizeStr
  const num = parseFloat(match[1])
  const unit = match[2].toUpperCase()
  const unitMap = { K: 'KB', M: 'MB', G: 'GB', T: 'TB', '': 'B' }
  return `${num} ${unitMap[unit] || unit}`
}

const toggleDiskFlag = async (disk, flag) => {
  actioning.value = true
  try {
    // Rebuild the disk config string with the toggled flag
    const p = disk.parsed
    const newVal = flag === 'ssd' ? (p.ssd ? 0 : 1) : (p.discard ? 0 : 1)
    // Build a minimal config string from known parts
    let diskStr = `${p.storage}:${p.volume}`
    if (p.size) diskStr += `,size=${p.size}`
    if (p.format) diskStr += `,format=${p.format}`
    if (p.cache) diskStr += `,cache=${p.cache}`
    const ssdVal = flag === 'ssd' ? newVal : (p.ssd ? 1 : 0)
    const discardVal = flag === 'discard' ? newVal : (p.discard ? 'on' : 0)
    if (ssdVal) diskStr += `,ssd=1`
    if (discardVal && discardVal !== 0) diskStr += `,discard=on`
    if (!p.backup) diskStr += `,backup=0`
    if (p.iothread) diskStr += `,iothread=1`
    await api.pveVm.updateConfig(hostId.value, node.value, vmid.value, { [disk.key]: diskStr })
    const label = flag === 'ssd' ? 'SSD emulation' : 'Discard'
    toast.success(`${label} ${newVal ? 'enabled' : 'disabled'} for ${disk.key}`)
    await loadConfig()
  } catch (e) {
    console.error(e)
    toast.error(`Failed to toggle ${flag}`)
  } finally {
    actioning.value = false
  }
}

// ── Snapshot Actions ───────────────────────────────────────────────────────────

const doCreateSnapshot = async () => {
  if (!snapshotForm.value.snapname) {
    toast.error('Snapshot name is required')
    return
  }
  actioning.value = true
  try {
    await api.pveVm.createSnapshot(hostId.value, node.value, vmid.value, snapshotForm.value)
    toast.success('Snapshot creation started')
    showSnapshotModal.value = false
    snapshotForm.value = { snapname: '', description: '', vmstate: false }
    await loadSnapshots()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const rollbackSnapshot = async (snapName) => {
  if (!confirm(`This will revert the VM to this snapshot. Continue?`)) return
  actioning.value = true
  try {
    await api.pveVm.rollbackSnapshot(hostId.value, node.value, vmid.value, snapName)
    toast.success('Rollback initiated')
    await loadSnapshots()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const deleteSnapshot = async (snapName) => {
  if (!confirm(`Delete snapshot '${snapName}'? This cannot be undone.`)) return
  actioning.value = true
  try {
    await api.pveVm.deleteSnapshot(hostId.value, node.value, vmid.value, snapName)
    toast.success('Snapshot deleted')
    await loadSnapshots()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const toggleSnapSelect = (snapName) => {
  const s = new Set(selectedSnaps.value)
  if (s.has(snapName)) {
    s.delete(snapName)
  } else if (s.size < 2) {
    s.add(snapName)
  }
  selectedSnaps.value = s
}

const toggleSnapCollapse = (snapName) => {
  const s = new Set(collapsedSnaps.value)
  if (s.has(snapName)) {
    s.delete(snapName)
  } else {
    s.add(snapName)
  }
  collapsedSnaps.value = s
}

const openCompareModal = async () => {
  const [snapA, snapB] = [...selectedSnaps.value]
  compareSnaps.value = [snapA, snapB]
  loadingCompare.value = true
  showCompareModal.value = true
  try {
    const [resA, resB] = await Promise.all([
      api.pveVm.getSnapshotConfig(hostId.value, node.value, vmid.value, snapA),
      api.pveVm.getSnapshotConfig(hostId.value, node.value, vmid.value, snapB),
    ])
    compareLeft.value = resA.data || {}
    compareRight.value = resB.data || {}
  } catch (e) {
    console.error(e)
    toast.error('Failed to load snapshot configs')
    showCompareModal.value = false
  } finally {
    loadingCompare.value = false
  }
}

// Quick Snapshot
const openQuickSnapshotModal = () => {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const name = `snap-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`
  quickSnapForm.value = { snapname: name, description: '' }
  showQuickSnapshotModal.value = true
}

const doQuickSnapshot = async () => {
  if (!quickSnapForm.value.snapname) {
    toast.error('Snapshot name is required')
    return
  }
  actioning.value = true
  try {
    const res = await api.pveVm.createSnapshot(hostId.value, node.value, vmid.value, {
      snapname: quickSnapForm.value.snapname,
      description: quickSnapForm.value.description,
      vmstate: false,
    })
    showQuickSnapshotModal.value = false
    const upid = res.data
    if (upid && typeof upid === 'string' && upid.startsWith('UPID:')) {
      quickSnapUpid.value = upid
      showQuickSnapProgress.value = true
    } else {
      toast.success('Snapshot creation started')
      await loadSnapshots()
    }
  } catch (e) {
    console.error(e)
    toast.error('Failed to create snapshot')
  } finally {
    actioning.value = false
  }
}

const onQuickSnapSuccess = async () => {
  showQuickSnapProgress.value = false
  toast.success('Snapshot created')
  await loadSnapshots()
}

const onQuickSnapError = () => {
  showQuickSnapProgress.value = false
  toast.error('Snapshot creation failed')
}

// ── Firewall Actions ───────────────────────────────────────────────────────────

const toggleFirewall = async (enabled) => {
  try {
    await api.pveVm.setFirewallOptions(hostId.value, node.value, vmid.value, { enable: enabled ? 1 : 0 })
    firewallOptions.value = { ...firewallOptions.value, enable: enabled ? 1 : 0 }
    toast.success(`Firewall ${enabled ? 'enabled' : 'disabled'}`)
  } catch (e) {
    console.error(e)
    toast.error('Failed to update firewall options')
  }
}

const doAddFirewallRule = async () => {
  actioning.value = true
  try {
    const payload = { ...firewallForm.value }
    Object.keys(payload).forEach(k => {
      if (payload[k] === '' || payload[k] === null) delete payload[k]
    })
    // Always keep type and action
    payload.type = firewallForm.value.type
    payload.action = firewallForm.value.action
    await api.pveVm.addFirewallRule(hostId.value, node.value, vmid.value, payload)
    toast.success('Firewall rule added')
    showFirewallModal.value = false
    firewallForm.value = { type: 'in', action: 'ACCEPT', proto: '', source: '', dest: '', dport: '', comment: '', enable: 1 }
    await loadFirewall()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const deleteFirewallRule = async (pos) => {
  if (!confirm(`Delete firewall rule at position ${pos}?`)) return
  actioning.value = true
  try {
    await api.pveVm.deleteFirewallRule(hostId.value, node.value, vmid.value, pos)
    toast.success('Rule deleted')
    await loadFirewall()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

// ── Power Schedule ─────────────────────────────────────────────────────────────

const showAddScheduleModal = ref(false)
const scheduleForm = ref({ action: 'shutdown', cron: '0 2 * * *', description: '', enabled: true })

const schedulePresets = [
  { label: 'Daily 2AM', cron: '0 2 * * *' },
  { label: 'Daily 8AM', cron: '0 8 * * *' },
  { label: 'Weekdays 9AM', cron: '0 9 * * 1-5' },
  { label: 'Every Sunday midnight', cron: '0 0 * * 0' },
  { label: 'Every hour', cron: '0 * * * *' },
]

const SCHEDULE_TAG_PREFIX = 'schedule:'

// Parse schedule entries from VM tags
const scheduleEntries = computed(() => {
  if (!config.value?.tags) return []
  return config.value.tags
    .split(';')
    .map(t => t.trim())
    .filter(t => t.startsWith(SCHEDULE_TAG_PREFIX))
    .map(t => {
      try {
        const rest = t.slice(SCHEDULE_TAG_PREFIX.length)
        const parts = rest.split(':')
        // format: action:cron_b64:desc_b64:enabled
        const action = parts[0] || 'shutdown'
        const cron = parts[1] ? atob(parts[1]) : '0 0 * * *'
        const description = parts[2] ? atob(parts[2]) : ''
        const enabled = parts[3] !== '0'
        return { action, cron, description, enabled }
      } catch {
        return null
      }
    })
    .filter(Boolean)
})

const encodeScheduleTag = (entry) => {
  const cronB64 = btoa(entry.cron)
  const descB64 = btoa(entry.description || '')
  const en = entry.enabled ? '1' : '0'
  return `${SCHEDULE_TAG_PREFIX}${entry.action}:${cronB64}:${descB64}:${en}`
}

const isValidCron = (cron) => {
  if (!cron) return false
  const parts = cron.trim().split(/\s+/)
  if (parts.length !== 5) return false
  const ranges = [
    [0, 59], [0, 23], [1, 31], [1, 12], [0, 7]
  ]
  return parts.every((p, i) => {
    if (p === '*') return true
    if (p.includes('-')) {
      const [a, b] = p.split('-').map(Number)
      return !isNaN(a) && !isNaN(b) && a >= ranges[i][0] && b <= ranges[i][1]
    }
    if (p.includes('/')) {
      const [base, step] = p.split('/')
      return base === '*' && !isNaN(Number(step)) && Number(step) > 0
    }
    if (p.includes(',')) {
      return p.split(',').every(v => {
        const n = Number(v)
        return !isNaN(n) && n >= ranges[i][0] && n <= ranges[i][1]
      })
    }
    const n = Number(p)
    return !isNaN(n) && n >= ranges[i][0] && n <= ranges[i][1]
  })
}

const computeNextRun = (cronStr) => {
  if (!isValidCron(cronStr)) return 'Invalid cron'
  try {
    const parts = cronStr.trim().split(/\s+/)
    const [minPart, hourPart, domPart, monPart, dowPart] = parts

    const matchField = (part, val, min, max) => {
      if (part === '*') return true
      if (part.includes('/')) {
        const step = parseInt(part.split('/')[1])
        return (val - min) % step === 0
      }
      if (part.includes(',')) return part.split(',').map(Number).includes(val)
      if (part.includes('-')) {
        const [a, b] = part.split('-').map(Number)
        return val >= a && val <= b
      }
      return parseInt(part) === val
    }

    const now = new Date()
    const candidate = new Date(now)
    candidate.setSeconds(0, 0)
    candidate.setMinutes(candidate.getMinutes() + 1) // start from next minute

    for (let i = 0; i < 525600; i++) { // max 1 year of minutes
      const m = candidate.getMinutes()
      const h = candidate.getHours()
      const dom = candidate.getDate()
      const mon = candidate.getMonth() + 1
      const dow = candidate.getDay()

      if (
        matchField(monPart, mon, 1, 12) &&
        matchField(domPart, dom, 1, 31) &&
        matchField(dowPart, dow, 0, 7) &&
        matchField(hourPart, h, 0, 23) &&
        matchField(minPart, m, 0, 59)
      ) {
        return candidate.toLocaleString()
      }
      candidate.setMinutes(candidate.getMinutes() + 1)
    }
    return 'No match within 1 year'
  } catch {
    return 'Error'
  }
}

const scheduleActionBadge = (action) => {
  if (action === 'start') return 'badge-success'
  if (action === 'shutdown') return 'badge-warning'
  if (action === 'reboot') return 'badge-info'
  return 'badge-secondary'
}

const openAddScheduleModal = () => {
  scheduleForm.value = { action: 'shutdown', cron: '0 2 * * *', description: '', enabled: true }
  showAddScheduleModal.value = true
}

const doAddSchedule = async () => {
  if (!scheduleForm.value.cron || !isValidCron(scheduleForm.value.cron)) {
    toast.error('Invalid cron expression')
    return
  }
  const newTag = encodeScheduleTag(scheduleForm.value)
  const currentTags = tagList.value
  const newTags = [...currentTags, newTag].join(';')
  await saveTags(newTags)
  showAddScheduleModal.value = false
}

const toggleScheduleEntry = async (idx) => {
  const allTags = config.value.tags
    ? config.value.tags.split(';').map(t => t.trim()).filter(Boolean)
    : []
  // Find the nth schedule tag
  let schedIdx = -1
  const newTags = allTags.map(t => {
    if (t.startsWith(SCHEDULE_TAG_PREFIX)) {
      schedIdx++
      if (schedIdx === idx) {
        // Toggle the last part
        const parts = t.split(':')
        const currentEnabled = parts[parts.length - 1]
        parts[parts.length - 1] = currentEnabled === '0' ? '1' : '0'
        return parts.join(':')
      }
    }
    return t
  })
  await saveTags(newTags.join(';'))
}

const deleteScheduleEntry = async (idx) => {
  const allTags = config.value.tags
    ? config.value.tags.split(';').map(t => t.trim()).filter(Boolean)
    : []
  let schedIdx = -1
  const newTags = allTags.filter(t => {
    if (t.startsWith(SCHEDULE_TAG_PREFIX)) {
      schedIdx++
      if (schedIdx === idx) return false
    }
    return true
  })
  await saveTags(newTags.join(';'))
}

// ── Migration Warnings ─────────────────────────────────────────────────────────

const migrateWarnings = computed(() => {
  if (!config.value) return []
  const warnings = []
  // Check for CD-ROM
  const allKeys = Object.keys(config.value)
  const hasCdrom = allKeys.some(k => {
    const v = config.value[k]
    if (typeof v !== 'string') return false
    return v.includes('media=cdrom') || (k.startsWith('ide') && v.includes('.iso'))
  })
  if (hasCdrom) {
    warnings.push('VM has a CD-ROM/ISO mounted. Unmount it before live migration to avoid issues.')
  }
  // Check for snapshots
  if (snapshots.value.length > 1) { // >1 because 'current' is always present
    warnings.push('VM has snapshots. Live migration with snapshots may fail if disks are on local storage.')
  }
  // Warn if online migration is disabled but VM is running
  if (vmStatus.value?.status === 'running' && !migrateForm.value.online) {
    warnings.push('VM is running and online migration is disabled. The VM will be stopped during migration.')
  }
  return warnings
})

// ── Clone / Migrate ────────────────────────────────────────────────────────────

const openCloneModal = async () => {
  await loadNextId()
  showCloneModal.value = true
}

const openMigrateModal = async () => {
  await loadClusterNodes()
  // Load snapshots for warning detection (if not already loaded)
  if (snapshots.value.length === 0) {
    await loadSnapshots()
  }
  // Default online=true if running, false if stopped
  const isRunning = vmStatus.value?.status === 'running'
  migrateForm.value.online = isRunning
  migrateForm.value.with_local_disks = true
  migrateForm.value.bwlimit = 0
  migrateForm.value.target = ''
  targetStorageList.value = []
  migrateStorageMap.value = {}
  if (clusterNodes.value.length > 0) {
    migrateForm.value.target = clusterNodes.value[0].node
    await loadTargetStorage(clusterNodes.value[0].node)
  }
  showMigrateModal.value = true
}

const loadTargetStorage = async (targetNode) => {
  if (!targetNode) return
  loadingTargetStorage.value = true
  try {
    const res = await api.pveNode.listStorage(hostId.value, targetNode)
    const all = res.data || []
    // Filter to only VM disk-capable storage types
    const vmCapableTypes = new Set(['dir', 'lvm', 'lvmthin', 'zfspool', 'zfs', 'nfs', 'cifs', 'rbd', 'cephfs'])
    targetStorageList.value = all.filter(s => vmCapableTypes.has(s.type))
    // Reset storage map
    migrateStorageMap.value = {}
  } catch (e) {
    console.warn('Failed to load target storage', e)
    targetStorageList.value = []
  } finally {
    loadingTargetStorage.value = false
  }
}

const onMigrateTargetChange = async () => {
  if (migrateForm.value.target) {
    await loadTargetStorage(migrateForm.value.target)
  }
}

const doClone = async () => {
  if (!cloneForm.value.newid) {
    toast.error('New VM ID is required')
    return
  }
  actioning.value = true
  try {
    const payload = { ...cloneForm.value }
    if (!payload.storage) delete payload.storage
    if (!payload.target) delete payload.target
    if (!payload.name) delete payload.name
    await api.pveVm.clone(hostId.value, node.value, vmid.value, payload)
    toast.success('Clone started')
    showCloneModal.value = false
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
}

const doMigrate = async () => {
  if (!migrateForm.value.target) {
    toast.error('Select a target node')
    return
  }
  migrateSubmitting.value = true
  try {
    // Build payload
    const payload = {
      target: migrateForm.value.target,
      online: migrateForm.value.online ? 1 : 0,
      with_local_disks: migrateForm.value.with_local_disks ? 1 : 0,
    }
    if (migrateForm.value.bwlimit > 0) {
      payload.bwlimit = migrateForm.value.bwlimit
    }
    // Append target storage mappings (targetstorage or per-disk)
    // Collect non-empty mappings: if all disks map to same storage use targetstorage,
    // otherwise pass individual disk:storage pairs in targetstorage field (PVE syntax)
    const mappings = Object.entries(migrateStorageMap.value)
      .filter(([, v]) => v)
    if (mappings.length > 0) {
      // Build PVE targetstorage string: "storage1,scsi0=storage2,..."
      const unique = [...new Set(mappings.map(([, v]) => v))]
      if (unique.length === 1 && mappings.length === parsedDisks.value.length) {
        // All disks → same storage, use simple form
        payload.targetstorage = unique[0]
      } else {
        // Mixed: comma-separated diskkey=storage pairs
        payload.targetstorage = mappings.map(([k, v]) => `${k}=${v}`).join(',')
      }
    }

    const res = await api.pveVm.migrate(hostId.value, node.value, vmid.value, payload)
    const upid = res.data?.upid || res.data
    if (upid && typeof upid === 'string' && upid.startsWith('UPID')) {
      migrateUpid.value = upid
      showMigrateModal.value = false
      showMigrateProgress.value = true
    } else {
      toast.success('Migration started')
      showMigrateModal.value = false
    }
  } catch (e) {
    console.error(e)
  } finally {
    migrateSubmitting.value = false
  }
}

const onMigrateSuccess = () => {
  toast.success('Migration completed successfully')
  showMigrateProgress.value = false
  // Reload VM status
  loadAll()
}

const onMigrateError = (msg) => {
  toast.error(`Migration failed: ${msg}`)
}

// ── Console ────────────────────────────────────────────────────────────────────

const openConsole = async () => {
  try {
    await api.pveVm.getVncTicket(hostId.value, node.value, vmid.value)
  } catch (e) {
    console.warn('VNC ticket request failed', e)
  }
  router.push(`/proxmox/${hostId.value}/nodes/${node.value}/console/${vmid.value}`)
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadAll()
  await loadNextId()
  startPolling()
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})

// ── Copy helpers ──────────────────────────────────────────────────────────
const copyVmId = () => copyToClipboard(String(vmid.value), { toast: true })
const copySshCommand = () => {
  const ip = vmStatus.value?.ip || vmStatus.value?.['ip-address']
  if (ip) copyToClipboard(`ssh root@${ip}`, { toast: true })
  else toast.warning('IP address not available')
}
</script>

<style scoped>
.btn-copy {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.7rem;
  padding: 1px 5px;
  margin-left: 4px;
  line-height: 1.4;
  transition: background 0.15s, color 0.15s;
  vertical-align: middle;
}
.btn-copy:hover {
  background: var(--background);
  color: var(--primary-color);
}

.vm-detail-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.back-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
}

.back-link:hover {
  color: var(--text-primary);
}

.vm-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.header-actions {
  flex-wrap: wrap;
}

.action-sep {
  color: var(--border-color);
  padding: 0 0.25rem;
  line-height: 1.8;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1.5rem;
  overflow-x: auto;
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.6rem 1.25rem;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.9rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn--active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

/* Stats row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card-sm {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  box-shadow: var(--shadow);
}

.stat-card-sm__label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.stat-card-sm__value {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Charts */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 900px) {
  .charts-row { grid-template-columns: 1fr; }
}

.chart-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-card .card-header h4 {
  margin: 0;
  font-size: 0.9rem;
}

.chart-wrap {
  height: 200px;
  padding: 0.5rem;
}

.form-control-sm {
  padding: 0.2rem 0.5rem;
  font-size: 0.8rem;
  width: auto;
}

/* Config grid */
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 700px) {
  .config-grid { grid-template-columns: 1fr; }
}

.config-grid-span2 {
  grid-column: 1 / -1;
}

.config-value {
  padding: 0.5rem 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  color: var(--text-primary);
  min-height: 36px;
}

.config-value.pre-wrap {
  white-space: pre-wrap;
  min-height: 60px;
}

.card-body {
  padding: 1.5rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-weight: 500;
}

/* Modals */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  max-width: 580px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.modal-content.modal-sm {
  max-width: 440px;
}

.modal-content--wide {
  max-width: 720px;
}

/* Migrate storage mapping table */
.migrate-storage-table {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
  margin-top: 0.5rem;
}

.migrate-storage-header {
  display: grid;
  grid-template-columns: 80px 1fr 1fr;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: var(--bg-tertiary, rgba(255,255,255,0.04));
  border-bottom: 1px solid var(--border-color);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.migrate-storage-row {
  display: grid;
  grid-template-columns: 80px 1fr 1fr;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
}

.migrate-storage-row:last-child {
  border-bottom: none;
}

.migrate-disk-key {
  font-size: 0.82rem;
}

.migrate-storage-src {
  font-family: monospace;
  font-size: 0.8rem;
}

/* Form hints */
.form-hint {
  margin-top: 0.3rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
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
  font-size: 1.1rem;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.modal-body {
  padding: 1.5rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 600px) {
  .form-row { grid-template-columns: 1fr; }
}

/* Utilities */
.ml-1 { margin-left: 0.25rem; }
.mt-2 { margin-top: 1rem; }
.mb-2 { margin-bottom: 1rem; }
.mt-4 { margin-top: 2rem; }
.pt-2 { padding-top: 1rem; }
.flex { display: flex; }
.flex-wrap { flex-wrap: wrap; }
.gap-1 { gap: 0.5rem; }
.gap-2 { gap: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-center { text-align: center; }
.text-danger { color: var(--danger-color); }
.table-container { overflow-x: auto; }

.btn-success {
  background-color: var(--secondary-color);
  color: white;
}

.btn-success:hover {
  background-color: #059669;
}

/* Pending Config Changes */
.pending-header {
  user-select: none;
}

.pending-title {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin: 0;
  font-size: 1rem;
}

.pending-header-actions {
  align-items: center;
}

.pending-refresh {
  font-size: 1rem;
  line-height: 1;
  padding: 0.2rem 0.5rem;
}

.pending-warning-banner {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: rgba(234, 179, 8, 0.12);
  border-left: 4px solid #eab308;
  color: #ca8a04;
  padding: 0.75rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.pending-warning-icon {
  font-size: 1.1rem;
  flex-shrink: 0;
}

.pending-current {
  color: var(--text-secondary);
  font-family: monospace;
  word-break: break-all;
}

.pending-new {
  color: #eab308;
  font-family: monospace;
  font-weight: 600;
  word-break: break-all;
}

/* Tag management */
.tag-manager {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
  min-height: 2rem;
}

.tag-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  color: #fff;
  white-space: nowrap;
  letter-spacing: 0.02em;
  text-transform: lowercase;
}

.tag-remove {
  background: none;
  border: none;
  color: rgba(255,255,255,0.8);
  cursor: pointer;
  font-size: 0.9rem;
  line-height: 1;
  padding: 0;
  margin-left: 0.1rem;
  display: flex;
  align-items: center;
}

.tag-remove:hover {
  color: #fff;
}

.tag-remove:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tag-input-wrap {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.tag-input {
  width: 130px;
  padding: 0.2rem 0.5rem;
  font-size: 0.8rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background: var(--background);
  color: var(--text-primary);
}

.tag-input:focus {
  outline: none;
  border-color: var(--primary-color);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.spin {
  display: inline-block;
  animation: spin 0.8s linear infinite;
}

/* Inline config field editing */
.inline-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.inline-edit-row {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

.inline-edit-row .form-control {
  flex: 1;
}

.inline-current {
  font-size: 0.72rem;
  color: var(--text-secondary);
}

.inline-current code {
  font-size: 0.72rem;
}

/* Toggle row (boolean fields) */
.toggle-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.toggle-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  font-size: 0.875rem;
}

.toggle-check {
  cursor: pointer;
}

.toggle-label {
  font-weight: 500;
  color: var(--text-primary);
}

.toggle-status {
  font-size: 0.7rem;
}

.mt-1 { margin-top: 0.5rem; }

/* Extra-small button variant for toggle cells */
.btn-xs {
  padding: 0.15rem 0.5rem;
  font-size: 0.72rem;
  border-radius: 0.25rem;
  line-height: 1.4;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.15s, color 0.15s;
}

.btn-xs.btn-success {
  background-color: var(--secondary-color);
  color: white;
  border-color: var(--secondary-color);
}

.btn-xs.btn-outline {
  background: transparent;
  color: var(--text-secondary);
  border-color: var(--border-color);
}

.btn-xs:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-xs:hover:not(:disabled) {
  opacity: 0.85;
}

/* ── Snapshot Tree ── */
.snap-tree-indent {
  display: inline-flex;
  align-items: center;
}

.snap-tree-line {
  font-family: monospace;
  color: var(--text-secondary);
  margin-right: 0.2rem;
  user-select: none;
}

.snap-current-row td {
  background: rgba(16, 185, 129, 0.06);
}

/* ── Snapshot Compare Modal ── */
.modal-content.modal-lg {
  max-width: 860px;
  width: 95vw;
}

.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.compare-col-title {
  font-size: 0.9rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.25rem;
}

.compare-body {
  font-size: 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  max-height: 60vh;
  overflow-y: auto;
}

.compare-row {
  display: flex;
  gap: 0.5rem;
  padding: 0.2rem 0.35rem;
  border-radius: 3px;
}

.compare-row--diff {
  background: rgba(245, 158, 11, 0.12);
}

.compare-row--only {
  background: rgba(59, 130, 246, 0.1);
}

.compare-row--missing {
  background: rgba(239, 68, 68, 0.07);
}

.compare-key {
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 8rem;
  flex-shrink: 0;
  word-break: break-all;
}

.compare-val {
  color: var(--text-primary);
  word-break: break-all;
}

/* ── Migration Source Card ── */
.migrate-source-card {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
}

.migrate-source-title {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
}

.migrate-source-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.3rem;
  font-size: 0.875rem;
}

.migrate-source-row:last-child {
  margin-bottom: 0;
}

.migrate-source-label {
  min-width: 60px;
  font-weight: 500;
  color: var(--text-secondary);
  font-size: 0.78rem;
}

/* ── Migration Warnings ── */
.migrate-warnings {
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.4);
  border-radius: 0.375rem;
  padding: 0.6rem 1rem;
  margin-bottom: 1rem;
}

.migrate-warning-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.82rem;
  color: #ca8a04;
  padding: 0.2rem 0;
  line-height: 1.4;
}

.migrate-warning-icon {
  font-size: 1rem;
  flex-shrink: 0;
  margin-top: 0.05rem;
}

/* ── Schedule Presets ── */
.schedule-presets {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.4rem;
  margin-bottom: 0.4rem;
}

/* ── Mobile Responsive ──────────────────────────────────────────────────── */
@media (max-width: 768px) {
  /* Header: stack vertically on small screens */
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .header-actions {
    width: 100%;
  }

  .vm-title {
    font-size: 1.1rem;
  }

  /* Tabs: horizontal scroll, no wrapping */
  .tabs {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    flex-wrap: nowrap;
    scrollbar-width: none;
  }
  .tabs::-webkit-scrollbar {
    display: none;
  }

  /* Stats: 2-column on mobile */
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.5rem;
  }

  /* Modals: full-screen on mobile */
  .modal-content,
  .modal-content.modal-sm,
  .modal-content--wide,
  .modal-content.modal-lg {
    width: 100%;
    max-width: 100%;
    height: 100%;
    max-height: 100%;
    border-radius: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
  }

  .modal {
    align-items: flex-end;
  }

  .modal-body {
    flex: 1;
    overflow-y: auto;
  }
}

/* ── Performance Tab ─────────────────────────────────────────────────────── */
.perf-time-selector {
  display: flex;
  gap: 2px;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 2px;
}

.ptr-btn {
  background: none;
  border: none;
  padding: 0.25rem 0.65rem;
  border-radius: 0.35rem;
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--text-secondary);
  transition: all 0.15s;
  white-space: nowrap;
}

.ptr-btn:hover {
  color: var(--text-primary);
  background: var(--background);
}

.ptr-btn--active {
  background: var(--primary-color);
  color: white;
  font-weight: 600;
}

.perf-charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 900px) {
  .perf-charts-grid {
    grid-template-columns: 1fr;
  }
}

.perf-chart-card {
  overflow: hidden;
}

.perf-chart-card__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 0.65rem 1rem 0.2rem;
}

.perf-chart-card__title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.perf-chart-card__val {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-secondary);
  font-family: monospace;
}

.perf-chart-body {
  height: 120px;
  padding: 0.2rem 0.5rem 0.5rem;
  position: relative;
}

/* ── Disk boot order strip ───────────────────────────── */
.disk-boot-order {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  background: var(--background-secondary, #f8f9fa);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  margin-bottom: 0.75rem;
}

.boot-order-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  flex: 1;
}

.boot-order-item {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  background: var(--card-background, #fff);
  border: 1px solid var(--border-color);
  border-radius: 0.35rem;
  padding: 0.2rem 0.5rem;
  font-size: 0.8rem;
}

.boot-pos {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.3em;
  height: 1.3em;
  border-radius: 50%;
  background: var(--primary-color);
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
  flex-shrink: 0;
}

.boot-order-btns {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.boot-order-btns .btn {
  padding: 0 0.3rem;
  font-size: 0.7rem;
  line-height: 1.3;
}

/* ── Add-disk mode tabs ──────────────────────────────── */
.disk-mode-tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1rem;
}

.disk-mode-tab {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  padding: 0.5rem 1.1rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.disk-mode-tab:hover {
  color: var(--text-primary);
}

.disk-mode-tab.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

/* ── Storage image browser (import existing) ─────────── */
.storage-image-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 0.4rem;
}

.storage-image-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.45rem 0.75rem;
  cursor: pointer;
  transition: background 0.12s;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.85rem;
}

.storage-image-row:last-child {
  border-bottom: none;
}

.storage-image-row:hover {
  background: var(--background-secondary, #f5f5f5);
}

.storage-image-row.selected {
  background: color-mix(in srgb, var(--primary-color) 10%, transparent);
  border-color: var(--primary-color);
}

.img-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
  font-size: 0.82rem;
}

.img-meta {
  flex-shrink: 0;
  color: var(--text-secondary);
  font-size: 0.78rem;
  white-space: nowrap;
}
</style>
