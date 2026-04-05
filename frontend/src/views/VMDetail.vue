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
            <span :class="statusBadgeClass">{{ vmStatus?.status || 'unknown' }}</span>
            <span class="badge badge-info ml-1">QEMU</span>
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
          <button @click="openMigrateModal" class="btn btn-outline btn-sm">Migrate</button>
          <button @click="doConvertToTemplate" class="btn btn-outline btn-sm" :disabled="actioning">To Template</button>
          <button @click="showDeleteConfirm = true" class="btn btn-danger btn-sm" :disabled="actioning">Delete</button>
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
      </div>

      <!-- ─── Config Tab ─── -->
      <div v-if="activeTab === 'config'">
        <div class="card">
          <div class="card-header">
            <h3>VM Configuration</h3>
            <div class="flex gap-1">
              <button v-if="!editingConfig" @click="startEditConfig" class="btn btn-outline btn-sm">Edit</button>
              <template v-else>
                <button @click="saveConfig" class="btn btn-primary btn-sm" :disabled="savingConfig">
                  {{ savingConfig ? 'Saving...' : 'Save' }}
                </button>
                <button @click="cancelEditConfig" class="btn btn-outline btn-sm">Cancel</button>
              </template>
            </div>
          </div>
          <div class="card-body">
            <div class="config-grid">
              <div class="form-group">
                <label class="form-label">Name</label>
                <input v-if="editingConfig" v-model="editConfig.name" class="form-control" />
                <div v-else class="config-value">{{ config.name || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">CPU Cores</label>
                <input v-if="editingConfig" v-model.number="editConfig.cores" type="number" min="1" class="form-control" />
                <div v-else class="config-value">{{ config.cores || 1 }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Sockets</label>
                <input v-if="editingConfig" v-model.number="editConfig.sockets" type="number" min="1" class="form-control" />
                <div v-else class="config-value">{{ config.sockets || 1 }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">CPU Type</label>
                <input v-if="editingConfig" v-model="editConfig.cpu" class="form-control" placeholder="host" />
                <div v-else class="config-value">{{ config.cpu || 'host' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Memory (MB)</label>
                <input v-if="editingConfig" v-model.number="editConfig.memory" type="number" min="64" step="64" class="form-control" />
                <div v-else class="config-value">{{ config.memory || '—' }} MB</div>
              </div>
              <div class="form-group">
                <label class="form-label">Balloon (MB)</label>
                <input v-if="editingConfig" v-model.number="editConfig.balloon" type="number" min="0" step="64" class="form-control" />
                <div v-else class="config-value">{{ config.balloon ?? 0 }} MB</div>
              </div>
              <div class="form-group">
                <label class="form-label">Boot Order</label>
                <input v-if="editingConfig" v-model="editConfig.boot" class="form-control" placeholder="order=scsi0;ide2;net0" />
                <div v-else class="config-value">{{ config.boot || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">BIOS</label>
                <select v-if="editingConfig" v-model="editConfig.bios" class="form-control">
                  <option value="">Default (SeaBIOS)</option>
                  <option value="ovmf">OVMF (UEFI)</option>
                </select>
                <div v-else class="config-value">{{ config.bios || 'SeaBIOS' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Machine Type</label>
                <input v-if="editingConfig" v-model="editConfig.machine" class="form-control" placeholder="pc-i440fx or q35" />
                <div v-else class="config-value">{{ config.machine || 'default' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Tags</label>
                <input v-if="editingConfig" v-model="editConfig.tags" class="form-control" placeholder="tag1;tag2" />
                <div v-else class="config-value">{{ config.tags || '—' }}</div>
              </div>
              <div class="form-group config-grid-span2">
                <label class="form-label">Description</label>
                <textarea v-if="editingConfig" v-model="editConfig.description" class="form-control" rows="3"></textarea>
                <div v-else class="config-value pre-wrap">{{ config.description || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label checkbox-label">
                  <input v-if="editingConfig" v-model="editConfig.onboot" type="checkbox" />
                  <span v-else :class="config.onboot ? 'badge badge-success' : 'badge badge-danger'">
                    {{ config.onboot ? 'Yes' : 'No' }}
                  </span>
                  Start at boot
                </label>
              </div>
              <div class="form-group">
                <label class="form-label checkbox-label">
                  <input v-if="editingConfig" v-model="editConfig.protection" type="checkbox" />
                  <span v-else :class="config.protection ? 'badge badge-warning' : 'badge badge-info'">
                    {{ config.protection ? 'On' : 'Off' }}
                  </span>
                  Protection
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Disks Tab ─── -->
      <div v-if="activeTab === 'disks'">
        <div class="card">
          <div class="card-header">
            <h3>Disks</h3>
            <button @click="showAddDiskModal = true" class="btn btn-primary btn-sm">+ Add Disk</button>
          </div>
          <div class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Storage</th>
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
                  <td>{{ disk.parsed.size || '—' }}</td>
                  <td>{{ disk.parsed.format || '—' }}</td>
                  <td>{{ disk.parsed.cache || '—' }}</td>
                  <td>
                    <span v-if="disk.parsed.ssd" class="badge badge-success">SSD</span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>
                    <span v-if="disk.parsed.discard" class="badge badge-info">On</span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>
                    <div class="flex gap-1">
                      <button @click="openResizeDisk(disk)" class="btn btn-outline btn-sm">Resize</button>
                      <button @click="detachDisk(disk.key)" class="btn btn-danger btn-sm" :disabled="actioning">Detach</button>
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
                  <th>MAC</th>
                  <th>Bridge</th>
                  <th>VLAN Tag</th>
                  <th>Firewall</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="parsedNics.length === 0">
                  <td colspan="7" class="text-muted text-center">No NICs configured</td>
                </tr>
                <tr v-for="nic in parsedNics" :key="nic.key">
                  <td><code>{{ nic.key }}</code></td>
                  <td>{{ nic.parsed.model }}</td>
                  <td class="text-sm"><code>{{ nic.parsed.mac || '—' }}</code></td>
                  <td>{{ nic.parsed.bridge || '—' }}</td>
                  <td>{{ nic.parsed.vlan || '—' }}</td>
                  <td>
                    <span v-if="nic.parsed.firewall" class="badge badge-success">On</span>
                    <span v-else class="badge badge-danger">Off</span>
                  </td>
                  <td>
                    <button @click="removeNic(nic.key)" class="btn btn-danger btn-sm" :disabled="actioning">Remove</button>
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
            <button @click="showSnapshotModal = true" class="btn btn-primary btn-sm">+ Create Snapshot</button>
          </div>
          <div v-if="loadingSnapshots" class="loading-spinner"></div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Date</th>
                  <th>Parent</th>
                  <th>VM State</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="snapshots.length === 0">
                  <td colspan="6" class="text-muted text-center">No snapshots</td>
                </tr>
                <tr v-for="snap in snapshots" :key="snap.name">
                  <td>
                    <span v-if="snap._depth" class="text-muted">{{ '  └ '.repeat(snap._depth) }}</span>
                    <strong>{{ snap.name }}</strong>
                  </td>
                  <td class="text-sm text-muted">{{ snap.description || '—' }}</td>
                  <td class="text-sm">{{ snap.snaptime ? new Date(snap.snaptime * 1000).toLocaleString() : '—' }}</td>
                  <td class="text-sm">{{ snap.parent || '—' }}</td>
                  <td>
                    <span v-if="snap.vmstate" class="badge badge-info">Saved</span>
                    <span v-else class="text-muted text-sm">—</span>
                  </td>
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
    </template>

    <!-- ══════════════════════════════════════════════════════ MODALS ══ -->

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
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Migrate VM {{ vmid }}</h3>
          <button @click="showMigrateModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Target Node</label>
            <select v-model="migrateForm.target" class="form-control">
              <option value="" disabled>Select target node</option>
              <option v-for="n in clusterNodes" :key="n.node" :value="n.node">{{ n.node }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input v-model="migrateForm.online" type="checkbox" />
              Online Migration (live, VM stays running)
            </label>
          </div>
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input v-model="migrateForm.with_local_disks" type="checkbox" />
              Migrate local disks with VM
            </label>
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doMigrate" class="btn btn-primary" :disabled="actioning || !migrateForm.target">
              {{ actioning ? 'Migrating...' : 'Migrate' }}
            </button>
            <button @click="showMigrateModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Disk Modal -->
    <div v-if="showAddDiskModal" class="modal" @click.self="showAddDiskModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Disk</h3>
          <button @click="showAddDiskModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Bus / Type</label>
              <select v-model="addDiskForm.bus" class="form-control">
                <option value="scsi">SCSI</option>
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
                <option value="vmdk">vmdk</option>
              </select>
            </div>
          </div>
          <div class="flex gap-1 mt-2">
            <button @click="doAddDisk" class="btn btn-primary" :disabled="actioning">
              {{ actioning ? 'Adding...' : 'Add Disk' }}
            </button>
            <button @click="showAddDiskModal = false" class="btn btn-outline">Cancel</button>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Tooltip, Legend, Title, Filler
} from 'chart.js'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import { parseProxmoxDisk, parseProxmoxNIC, formatBytes, formatUptime, cpuPercent } from '@/utils/proxmox'

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
const activeTab = ref('overview')

// Tab data
const snapshots = ref([])
const loadingSnapshots = ref(false)
const firewallRules = ref([])
const firewallOptions = ref(null)
const loadingFirewall = ref(false)
const storageList = ref([])
const clusterNodes = ref([])
const rrdData = ref(null)
const rrdTimeframe = ref('hour')

// Modal visibility
const showDeleteConfirm = ref(false)
const showCloneModal = ref(false)
const showMigrateModal = ref(false)
const showAddDiskModal = ref(false)
const showResizeModal = ref(false)
const showAddNicModal = ref(false)
const showSnapshotModal = ref(false)
const showFirewallModal = ref(false)

// Resize disk state
const resizeDiskKey = ref('')
const resizeDiskCurrentSize = ref('')
const resizeSize = ref('')

// Edit config form
const editConfig = ref({})

// Modal forms
const cloneForm = ref({ newid: null, name: '', full: true, storage: '', target: '' })
const migrateForm = ref({ target: '', online: true, with_local_disks: false })
const addDiskForm = ref({ storage: '', size: 32, bus: 'scsi', format: 'qcow2' })
const addNicForm = ref({ bridge: 'vmbr0', model: 'virtio', tag: null })
const snapshotForm = ref({ snapname: '', description: '', vmstate: false })
const firewallForm = ref({ type: 'in', action: 'ACCEPT', proto: '', source: '', dest: '', dport: '', comment: '', enable: 1 })

const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'config', label: 'Config' },
  { id: 'disks', label: 'Disks' },
  { id: 'network', label: 'Network' },
  { id: 'snapshots', label: 'Snapshots' },
  { id: 'firewall', label: 'Firewall' },
  { id: 'console', label: 'Console' },
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
    const raw = res.data || []
    const byName = {}
    raw.forEach(s => { byName[s.name] = { ...s, _depth: 0 } })
    raw.forEach(s => {
      if (s.parent && byName[s.parent]) {
        byName[s.name]._depth = (byName[s.parent]._depth || 0) + 1
      }
    })
    snapshots.value = Object.values(byName)
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

// ── Disk Actions ───────────────────────────────────────────────────────────────

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
    await api.pveVm.addDisk(hostId.value, node.value, vmid.value, addDiskForm.value)
    toast.success('Disk added')
    showAddDiskModal.value = false
    await loadConfig()
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
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
  if (!confirm(`Rollback to snapshot '${snapName}'? Current VM state will be lost.`)) return
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

// ── Clone / Migrate ────────────────────────────────────────────────────────────

const openCloneModal = async () => {
  await loadNextId()
  showCloneModal.value = true
}

const openMigrateModal = async () => {
  await loadClusterNodes()
  if (clusterNodes.value.length > 0 && !migrateForm.value.target) {
    migrateForm.value.target = clusterNodes.value[0].node
  }
  showMigrateModal.value = true
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
  actioning.value = true
  try {
    await api.pveVm.migrate(hostId.value, node.value, vmid.value, migrateForm.value)
    toast.success('Migration started')
    showMigrateModal.value = false
  } catch (e) {
    console.error(e)
  } finally {
    actioning.value = false
  }
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
</script>

<style scoped>
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
</style>
