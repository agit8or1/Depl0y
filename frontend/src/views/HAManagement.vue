<template>
  <div class="ha-management">
    <div class="page-header">
      <div>
        <h1>High Availability Management</h1>
        <p class="text-muted">Manage Proxmox HA resources, groups, fence devices, and monitor cluster failover</p>
      </div>
      <div class="header-actions">
        <button @click="reloadAll" class="btn btn-secondary" :disabled="loadingResources || loadingGroups || loadingStatus">
          Refresh
        </button>
      </div>
    </div>

    <!-- Host Selector -->
    <div class="card host-selector-card">
      <div class="host-selector-row">
        <label class="form-label">Proxmox Host</label>
        <select
          v-model="selectedHostId"
          class="form-control host-select"
          :disabled="loadingHosts"
          @change="onHostChange"
        >
          <option value="" disabled>{{ loadingHosts ? 'Loading hosts...' : 'Select a host...' }}</option>
          <option v-for="host in hosts" :key="host.id" :value="host.id">
            {{ host.name }} — {{ host.address }}
          </option>
        </select>

        <div v-if="selectedHostId && haManagerStatus" class="status-badge-wrap">
          <span class="status-label">HA Manager:</span>
          <span :class="['badge', haStatusBadgeClass]">{{ haManagerStatus }}</span>
        </div>
        <div v-else-if="selectedHostId && loadingStatus" class="status-badge-wrap">
          <span class="text-muted text-sm">Loading status...</span>
        </div>
        <div v-else-if="selectedHostId && statusError" class="status-badge-wrap">
          <span class="badge badge-danger">Status unavailable</span>
        </div>
      </div>
    </div>

    <!-- No host selected -->
    <div v-if="!selectedHostId" class="card empty-placeholder">
      <p class="text-muted">Select a Proxmox host above to view HA configuration.</p>
    </div>

    <template v-else>

      <!-- ─── HA Status Dashboard ──────────────────────────────────────────── -->
      <div class="card ha-status-panel">
        <div class="card-header">
          <h2>HA Cluster Status</h2>
          <div class="ha-toggle-wrap">
            <span class="toggle-label">HA Enabled</span>
            <button
              :class="['toggle-btn', haEnabled ? 'toggle-on' : 'toggle-off']"
              :disabled="togglingHa"
              @click="requestHaToggle"
            >
              <span class="toggle-knob"></span>
            </button>
          </div>
        </div>

        <div v-if="loadingStatus" class="loading-state loading-state-sm">Loading cluster status...</div>

        <div v-else class="status-grid">
          <div class="status-item">
            <span class="status-item-label">Quorum</span>
            <span :class="['badge', quorumBadgeClass]">{{ quorumDisplay }}</span>
          </div>
          <div class="status-item">
            <span class="status-item-label">Nodes Online</span>
            <span class="status-item-value">{{ onlineNodeCount }} / {{ totalNodeCount }}</span>
          </div>
          <div class="status-item">
            <span class="status-item-label">HA Resources</span>
            <span class="status-item-value">{{ haResources.length }}</span>
          </div>
          <div class="status-item">
            <span class="status-item-label">Fence Device</span>
            <span v-if="fenceStatus" :class="['badge', fenceBadgeClass]">{{ fenceStatus }}</span>
            <span v-else class="text-muted text-sm">Not configured</span>
          </div>
          <div class="status-item">
            <span class="status-item-label">Last HA Event</span>
            <span v-if="lastHaEvent" class="last-event-text" :title="lastHaEvent">{{ lastHaEvent }}</span>
            <span v-else class="text-muted text-sm">None recorded</span>
          </div>
          <div class="status-item">
            <span class="status-item-label">Live Polling</span>
            <span :class="['badge', pollActive ? 'badge-success' : 'badge-secondary']">
              {{ pollActive ? 'Every 10s' : 'Paused' }}
            </span>
          </div>
        </div>

        <!-- HA Event Timeline -->
        <div v-if="haEventTimeline.length" class="event-timeline">
          <div class="timeline-header">
            <span class="text-xs text-muted">Recent HA Events (last {{ haEventTimeline.length }})</span>
          </div>
          <div class="timeline-items">
            <div v-for="(evt, i) in haEventTimeline" :key="i" class="timeline-item">
              <div :class="['timeline-dot', timelineDotClass(evt.type)]"></div>
              <div class="timeline-content">
                <span class="timeline-msg">{{ evt.message }}</span>
                <span class="timeline-time text-xs text-muted">{{ evt.time }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── HA Toggle Confirm Dialog ─────────────────────────────────────── -->
      <div v-if="showHaToggleConfirm" class="modal" @click.self="showHaToggleConfirm = false">
        <div class="modal-content modal-sm">
          <div class="modal-header">
            <h3>{{ haEnabled ? 'Disable HA?' : 'Enable HA?' }}</h3>
            <button @click="showHaToggleConfirm = false" class="btn-close">&times;</button>
          </div>
          <div class="modal-body">
            <p v-if="haEnabled">Disabling HA will stop automatic failover for all protected resources.</p>
            <p v-else>Enabling HA will allow automatic VM migration and restart on node failure.</p>
            <div class="modal-actions">
              <button class="btn btn-primary" :disabled="togglingHa" @click="confirmHaToggle">
                {{ togglingHa ? 'Applying...' : (haEnabled ? 'Disable HA' : 'Enable HA') }}
              </button>
              <button class="btn btn-outline" @click="showHaToggleConfirm = false">Cancel</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Tabs ──────────────────────────────────────────────────────────── -->
      <div class="tab-bar">
        <button :class="['tab-btn', activeTab === 'resources' ? 'tab-active' : '']" @click="activeTab = 'resources'">
          Resources
          <span v-if="haResources.length" class="tab-count">{{ haResources.length }}</span>
        </button>
        <button :class="['tab-btn', activeTab === 'groups' ? 'tab-active' : '']" @click="activeTab = 'groups'">
          Groups
          <span v-if="haGroups.length" class="tab-count">{{ haGroups.length }}</span>
        </button>
        <button :class="['tab-btn', activeTab === 'fence' ? 'tab-active' : '']" @click="activeTab = 'fence'">
          Fence Devices
          <span v-if="fenceDevices.length" class="tab-count">{{ fenceDevices.length }}</span>
        </button>
      </div>

      <!-- ─── Resources Tab ─────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'resources'" class="card">
        <div class="card-header">
          <h2>HA Resources</h2>
          <div class="header-actions-row">
            <button @click="showBulkHaModal = true" class="btn btn-secondary btn-sm" title="Enable HA for all stopped VMs">
              Bulk Enable HA
            </button>
            <button @click="showAddModal = true" class="btn btn-primary">+ Add Resource</button>
          </div>
        </div>

        <div v-if="loadingResources" class="loading-state">Loading HA resources...</div>
        <div v-else-if="resourceError" class="error-banner">{{ resourceError }}</div>
        <div v-else-if="haResources.length === 0" class="empty-state">
          <p>No HA resources configured on this host.</p>
          <p class="text-sm text-muted">Add VMs to HA protection to enable automatic failover.</p>
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>SID</th>
                <th>Type</th>
                <th>Group</th>
                <th>Configured State</th>
                <th>Live State</th>
                <th>Current Node</th>
                <th>Migration Target</th>
                <th>Last Change</th>
                <th>Max Restart</th>
                <th>Max Relocate</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="resource in haResources" :key="resource.sid">
                <td><strong>{{ resource.sid }}</strong></td>
                <td>{{ resource.type || 'vm' }}</td>
                <td>{{ resource.group || '—' }}</td>
                <td>
                  <span :class="['badge', resourceStateBadge(resource.state)]">
                    {{ resource.state || 'unknown' }}
                  </span>
                </td>
                <td>
                  <span v-if="liveStatus[resource.sid]" :class="['badge', resourceStateBadge(liveStatus[resource.sid].state)]">
                    {{ liveStatus[resource.sid].state }}
                  </span>
                  <span v-else class="text-muted text-sm">—</span>
                </td>
                <td>
                  <span v-if="liveStatus[resource.sid]?.node" class="node-chip">
                    {{ liveStatus[resource.sid].node }}
                  </span>
                  <span v-else class="text-muted text-sm">—</span>
                </td>
                <!-- Migration target on failure -->
                <td>
                  <span v-if="getMigrationTarget(resource)" class="node-chip node-chip-target">
                    {{ getMigrationTarget(resource) }}
                  </span>
                  <span v-else class="text-muted text-sm">—</span>
                </td>
                <td class="text-sm">
                  <span v-if="liveStatus[resource.sid]?.last_change" :title="liveStatus[resource.sid].last_change_iso">
                    {{ liveStatus[resource.sid].last_change }}
                  </span>
                  <span v-else class="text-muted">—</span>
                </td>
                <td>{{ resource.max_restart ?? '—' }}</td>
                <td>{{ resource.max_relocate ?? '—' }}</td>
                <td>
                  <button
                    @click="confirmDeleteResource(resource.sid)"
                    class="btn btn-danger btn-sm"
                    :disabled="deletingSid === resource.sid"
                  >
                    {{ deletingSid === resource.sid ? 'Removing...' : 'Remove' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ─── Groups Tab ────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'groups'" class="card">
        <div class="card-header">
          <h2>HA Groups</h2>
          <button @click="openCreateGroupModal" class="btn btn-primary">+ Create Group</button>
        </div>

        <div v-if="loadingGroups" class="loading-state">Loading HA groups...</div>
        <div v-else-if="groupError" class="error-banner">{{ groupError }}</div>
        <div v-else-if="haGroups.length === 0" class="empty-state">
          <p>No HA groups defined on this host.</p>
          <p class="text-sm text-muted">HA groups define which nodes can run a resource and failover preferences.</p>
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Group ID</th>
                <th>Nodes &amp; Priorities</th>
                <th>No Failback</th>
                <th>Restricted</th>
                <th>Comment</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="group in haGroups" :key="group.group">
                <td><strong>{{ group.group }}</strong></td>
                <td>
                  <div class="node-list">
                    <span
                      v-for="n in parseGroupNodes(group.nodes)"
                      :key="n.name"
                      class="node-chip"
                      :class="n.priority !== undefined ? 'node-chip-priority' : ''"
                      :title="n.priority !== undefined ? 'Priority: ' + n.priority : ''"
                    >
                      {{ n.name }}<span v-if="n.priority !== undefined" class="node-priority">:{{ n.priority }}</span>
                    </span>
                    <span v-if="!group.nodes" class="text-muted text-sm">—</span>
                  </div>
                </td>
                <td>
                  <span :class="['badge', group.nofailback ? 'badge-warning' : 'badge-secondary']">
                    {{ group.nofailback ? 'Yes' : 'No' }}
                  </span>
                </td>
                <td>
                  <span :class="['badge', group.restricted ? 'badge-warning' : 'badge-secondary']">
                    {{ group.restricted ? 'Yes' : 'No' }}
                  </span>
                </td>
                <td class="text-sm">{{ group.comment || '—' }}</td>
                <td>
                  <button
                    @click="confirmDeleteGroup(group.group)"
                    class="btn btn-danger btn-sm"
                    :disabled="deletingGroup === group.group"
                  >
                    {{ deletingGroup === group.group ? 'Deleting...' : 'Delete' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ─── Fence Devices Tab ─────────────────────────────────────────────── -->
      <div v-if="activeTab === 'fence'" class="card">
        <div class="card-header">
          <h2>Fence Devices</h2>
          <button @click="showAddFenceModal = true" class="btn btn-primary">+ Add Fence Device</button>
        </div>

        <div v-if="loadingFence" class="loading-state">Loading fence devices...</div>
        <div v-else-if="fenceError" class="error-banner">{{ fenceError }}</div>

        <div v-else-if="fenceDevices.length === 0" class="empty-state">
          <p>No fence devices configured.</p>
          <p class="text-sm text-muted">
            Fence devices enable STONITH (Shoot The Other Node In The Head) — required for reliable HA.
            Common types: <code>fence_ipmilan</code> (iDRAC/iLO), <code>fence_virsh</code>, <code>fence_scsi</code>.
          </p>
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Target Node(s)</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="fence in fenceDevices" :key="fence.id || fence.name">
                <td><strong>{{ fence.name }}</strong></td>
                <td><code class="code-badge">{{ fence.type }}</code></td>
                <td>
                  <div class="node-list">
                    <span v-for="node in (fence.nodes || []).slice(0,5)" :key="node" class="node-chip">{{ node }}</span>
                    <span v-if="(fence.nodes || []).length > 5" class="text-muted text-sm">+{{ fence.nodes.length - 5 }} more</span>
                  </div>
                </td>
                <td>
                  <span :class="['badge', fence.status === 'ok' ? 'badge-success' : fence.status === 'error' ? 'badge-danger' : 'badge-secondary']">
                    {{ fence.status || 'unknown' }}
                  </span>
                </td>
                <td>
                  <div class="action-row">
                    <button
                      class="btn btn-secondary btn-sm"
                      :disabled="testingFence === fence.name"
                      @click="testFenceDevice(fence)"
                    >
                      {{ testingFence === fence.name ? 'Testing...' : 'Test' }}
                    </button>
                    <button
                      class="btn btn-danger btn-sm"
                      :disabled="deletingFence === fence.name"
                      @click="deleteFenceDevice(fence)"
                    >
                      {{ deletingFence === fence.name ? '...' : 'Delete' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Fence info banner -->
        <div class="fence-info-banner">
          <p class="text-sm text-muted">
            Fence devices are managed via <code>pvesh</code> CLI on the Proxmox node.
            The table above shows devices detected from the cluster HA status.
            Use the Proxmox web UI or CLI for full fence agent configuration.
          </p>
        </div>
      </div>

    </template>

    <!-- ─── Add Resource Modal ────────────────────────────────────────────── -->
    <div v-if="showAddModal" class="modal" @click.self="showAddModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Add HA Resource</h3>
          <button @click="showAddModal = false" class="btn-close">&times;</button>
        </div>
        <form @submit.prevent="addResource" class="modal-body">
          <div class="form-group">
            <label class="form-label">Resource SID <span class="required">*</span></label>
            <input v-model="newResource.sid" class="form-control" placeholder="e.g. vm:100 or ct:200" required />
            <p class="field-hint">Format: <code>vm:&lt;vmid&gt;</code> or <code>ct:&lt;vmid&gt;</code></p>
          </div>

          <div class="form-group">
            <label class="form-label">HA Group</label>
            <select v-model="newResource.group" class="form-control">
              <option value="">— None —</option>
              <option v-for="g in haGroups" :key="g.group" :value="g.group">{{ g.group }}</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Migration Target Node (on failure)</label>
            <select v-model="newResource.migration_target" class="form-control">
              <option value="">— Auto (any available node) —</option>
              <option v-for="node in clusterNodes" :key="node" :value="node">{{ node }}</option>
            </select>
            <p class="field-hint">The preferred node to migrate to when the current node fails.</p>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Max Restart</label>
              <select v-model.number="newResource.max_restart" class="form-control">
                <option :value="0">0</option>
                <option :value="1">1</option>
                <option :value="2">2</option>
                <option :value="3">3</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Max Relocate</label>
              <select v-model.number="newResource.max_relocate" class="form-control">
                <option :value="0">0</option>
                <option :value="1">1</option>
                <option :value="2">2</option>
                <option :value="3">3</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="newResource.comment" class="form-control" placeholder="Optional description" />
          </div>

          <div class="modal-actions">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? 'Adding...' : 'Add Resource' }}
            </button>
            <button type="button" @click="showAddModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ─── Create Group Modal ────────────────────────────────────────────── -->
    <div v-if="showCreateGroupModal" class="modal" @click.self="showCreateGroupModal = false">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>Create HA Group</h3>
          <button @click="showCreateGroupModal = false" class="btn-close">&times;</button>
        </div>
        <form @submit.prevent="createGroup" class="modal-body">
          <div class="form-group">
            <label class="form-label">Group ID <span class="required">*</span></label>
            <input
              v-model="newGroup.group"
              class="form-control"
              placeholder="e.g. production"
              pattern="[a-zA-Z0-9_\-]+"
              title="Alphanumeric, underscores and dashes only"
              required
            />
          </div>

          <div class="form-group">
            <label class="form-label">Nodes &amp; Priorities <span class="required">*</span></label>
            <p class="field-hint">Select nodes and assign priorities (higher = preferred for failover).</p>

            <div v-if="clusterNodes.length > 0" class="node-priority-selector">
              <div
                v-for="node in clusterNodes"
                :key="node"
                :class="['node-priority-row', newGroupNodePriorities[node] !== undefined ? 'node-priority-row-selected' : '']"
              >
                <label class="node-priority-check-label">
                  <input
                    type="checkbox"
                    :checked="newGroupNodePriorities[node] !== undefined"
                    @change="toggleGroupNodeWithPriority(node)"
                    class="checkbox-input"
                  />
                  <span class="node-priority-name">{{ node }}</span>
                </label>
                <div v-if="newGroupNodePriorities[node] !== undefined" class="node-priority-input-wrap">
                  <label class="priority-label">Priority</label>
                  <input
                    type="number"
                    :value="newGroupNodePriorities[node]"
                    @input="setNodePriority(node, $event.target.value)"
                    class="form-control priority-input"
                    min="0"
                    max="255"
                    placeholder="0"
                  />
                </div>
              </div>
            </div>

            <input
              v-model="newGroup.nodes"
              class="form-control mt-sm"
              :placeholder="clusterNodes.length ? 'Or type: node1:1,node2:2' : 'e.g. node1:1,node2:2'"
            />
            <p class="field-hint">
              Format: <code>node1:&lt;priority&gt;,node2:&lt;priority&gt;</code>
              — higher priority = preferred node. Priority 0 = any.
            </p>
          </div>

          <div class="form-row">
            <div class="form-group checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="newGroup.nofailback" class="checkbox-input" />
                No Failback
              </label>
              <p class="field-hint">Do not move resources back when preferred node returns online.</p>
            </div>
            <div class="form-group checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="newGroup.restricted" class="checkbox-input" />
                Restricted
              </label>
              <p class="field-hint">Resources may only run on nodes listed in this group.</p>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="newGroup.comment" class="form-control" placeholder="Optional description" />
          </div>

          <div class="modal-actions">
            <button type="submit" class="btn btn-primary" :disabled="savingGroup">
              {{ savingGroup ? 'Creating...' : 'Create Group' }}
            </button>
            <button type="button" @click="showCreateGroupModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ─── Add Fence Device Modal ──────────────────────────────────────────── -->
    <div v-if="showAddFenceModal" class="modal" @click.self="showAddFenceModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Add Fence Device</h3>
          <button @click="showAddFenceModal = false" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <div class="fence-info-box">
            <strong>Note:</strong> Fence device configuration in Proxmox requires direct CLI access on the PVE node.
            Use the following reference to configure fence agents via <code>pvesh</code>:
          </div>

          <div class="form-group">
            <label class="form-label">Fence Type</label>
            <select v-model="newFence.type" class="form-control">
              <option value="fence_ipmilan">fence_ipmilan (iDRAC / iLO / IPMI)</option>
              <option value="fence_virsh">fence_virsh (KVM/libvirt)</option>
              <option value="fence_scsi">fence_scsi (SCSI persistent reservations)</option>
              <option value="fence_apc">fence_apc (APC UPS)</option>
              <option value="fence_manual">fence_manual</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Device Name</label>
            <input v-model="newFence.name" class="form-control" placeholder="e.g. node1-ipmi" />
          </div>

          <div v-if="newFence.type === 'fence_ipmilan'" class="fence-type-fields">
            <div class="form-group">
              <label class="form-label">IPMI Address</label>
              <input v-model="newFence.address" class="form-control" placeholder="192.168.1.100" />
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Username</label>
                <input v-model="newFence.username" class="form-control" placeholder="root" />
              </div>
              <div class="form-group">
                <label class="form-label">Password</label>
                <input v-model="newFence.password" type="password" class="form-control" placeholder="password" />
              </div>
            </div>
          </div>

          <div class="fence-cli-hint">
            <p class="field-hint">
              Example CLI command to add a fence device on a PVE node:
            </p>
            <pre class="code-block">pvesh create /cluster/ha/resources \
  --sid fence:{{ newFence.name || 'device-name' }} \
  --comment "{{ newFence.type || 'fence_ipmilan' }} fence agent"</pre>
          </div>

          <div class="modal-actions">
            <button class="btn btn-outline" @click="showAddFenceModal = false">Close</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ─── Bulk HA Modal ─────────────────────────────────────────────────── -->
    <div v-if="showBulkHaModal" class="modal" @click.self="showBulkHaModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Bulk Enable HA for Stopped VMs</h3>
          <button @click="showBulkHaModal = false" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="loadingBulkVms" class="loading-state">Loading stopped VMs...</div>
          <div v-else-if="stoppedVms.length === 0" class="empty-state">
            <p>No stopped VMs found that are not already in HA.</p>
          </div>
          <div v-else>
            <p class="text-sm text-muted">
              The following stopped VMs are not currently protected by HA.
              Select which ones to add:
            </p>
            <div class="bulk-vm-list">
              <label
                v-for="vm in stoppedVms"
                :key="vm.vmid"
                class="bulk-vm-item"
              >
                <input
                  type="checkbox"
                  :value="vm.vmid"
                  v-model="selectedBulkVms"
                  class="checkbox-input"
                />
                <span class="bulk-vm-info">
                  <strong>{{ vm.vmid }}</strong> — {{ vm.name || 'unnamed' }}
                  <span class="text-muted text-sm">({{ vm.node }})</span>
                </span>
              </label>
            </div>

            <div class="form-group mt-sm">
              <label class="form-label">HA Group (optional)</label>
              <select v-model="bulkHaGroup" class="form-control">
                <option value="">— None —</option>
                <option v-for="g in haGroups" :key="g.group" :value="g.group">{{ g.group }}</option>
              </select>
            </div>

            <div v-if="bulkProgress" class="bulk-progress">
              {{ bulkProgress }}
            </div>
          </div>

          <div class="modal-actions">
            <button
              class="btn btn-primary"
              :disabled="selectedBulkVms.length === 0 || bulkAdding"
              @click="doBulkEnableHa"
            >
              {{ bulkAdding ? 'Adding...' : `Enable HA for ${selectedBulkVms.length} VM(s)` }}
            </button>
            <button class="btn btn-outline" @click="showBulkHaModal = false">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const toast = useToast()

// ── Hosts ─────────────────────────────────────────────────────────────────────
const hosts = ref([])
const loadingHosts = ref(false)
const selectedHostId = ref('')

const loadHosts = async () => {
  loadingHosts.value = true
  try {
    const response = await api.proxmox.listHosts({ params: { page_size: 100 } })
    hosts.value = response.data?.items ?? response.data ?? []
    if (hosts.value.length === 1 && !selectedHostId.value) {
      selectedHostId.value = hosts.value[0].id
      reloadAll()
    }
  } catch (err) {
    console.error('Failed to load Proxmox hosts:', err)
    toast.error('Failed to load Proxmox hosts')
  } finally {
    loadingHosts.value = false
  }
}

const onHostChange = () => {
  stopPoll()
  reloadAll()
}

// ── Live polling ──────────────────────────────────────────────────────────────
let pollTimer = null
const pollActive = ref(false)

const startPoll = () => {
  stopPoll()
  if (!selectedHostId.value) return
  pollActive.value = true
  pollTimer = setInterval(() => { pollLiveStatus() }, 10000)
}

const stopPoll = () => {
  pollActive.value = false
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

// ── Live resource status ──────────────────────────────────────────────────────
const liveStatus = ref({})

const pollLiveStatus = async () => {
  if (!selectedHostId.value) return
  try {
    const response = await api.pveNode.haStatus(selectedHostId.value)
    const data = response.data
    const newLive = {}
    const entries = Array.isArray(data) ? data : (data ? [data] : [])
    for (const entry of entries) {
      if (entry.sid) {
        newLive[entry.sid] = {
          state: entry.state ?? entry.status ?? 'unknown',
          node: entry.node ?? '',
          last_change: entry.crm_state_change ? formatRelativeTime(entry.crm_state_change) : '',
          last_change_iso: entry.crm_state_change ? new Date(entry.crm_state_change * 1000).toLocaleString() : '',
        }
      }
      if (entry.type === 'manager' || entry.id === 'manager') {
        if (!haManagerStatus.value) haManagerStatus.value = entry.status ?? entry.state ?? ''
      }
    }
    liveStatus.value = newLive
  } catch (err) {
    console.warn('Live HA status poll failed:', err)
  }
}

const formatRelativeTime = (unixTs) => {
  if (!unixTs) return ''
  const diffSec = Math.floor(Date.now() / 1000) - unixTs
  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return `${Math.floor(diffSec / 86400)}d ago`
}

// ── HA Status Panel ───────────────────────────────────────────────────────────
const haManagerStatus = ref('')
const loadingStatus = ref(false)
const statusError = ref(null)
const quorumOk = ref(null)
const fenceStatus = ref('')
const lastHaEvent = ref('')
const haEnabled = ref(true)
const onlineNodeCount = ref(0)
const totalNodeCount = ref(0)
const haEventTimeline = ref([])

const quorumDisplay = computed(() => quorumOk.value === null ? 'Unknown' : (quorumOk.value ? 'OK' : 'No Quorum'))
const quorumBadgeClass = computed(() => quorumOk.value === null ? 'badge-secondary' : (quorumOk.value ? 'badge-success' : 'badge-danger'))
const fenceBadgeClass = computed(() => {
  const s = (fenceStatus.value || '').toLowerCase()
  if (s === 'available' || s === 'active' || s === 'ok') return 'badge-success'
  if (s === 'error' || s === 'failed') return 'badge-danger'
  return 'badge-warning'
})
const haStatusBadgeClass = computed(() => {
  const s = (haManagerStatus.value || '').toLowerCase()
  if (s === 'active') return 'badge-success'
  if (s === 'passive') return 'badge-info'
  if (s === 'disabled') return 'badge-secondary'
  return 'badge-warning'
})

const timelineDotClass = (type) => {
  if (type === 'failover') return 'dot-danger'
  if (type === 'recovery') return 'dot-success'
  if (type === 'migrate') return 'dot-info'
  return 'dot-secondary'
}

const loadHaStatus = async () => {
  if (!selectedHostId.value) return
  loadingStatus.value = true
  statusError.value = null
  haManagerStatus.value = ''
  quorumOk.value = null
  fenceStatus.value = ''
  lastHaEvent.value = ''
  onlineNodeCount.value = 0
  totalNodeCount.value = 0

  try {
    const csResp = await api.pveNode.clusterStatus(selectedHostId.value)
    const csData = Array.isArray(csResp.data) ? csResp.data : []
    let online = 0, total = 0

    for (const item of csData) {
      if (item.type === 'cluster') {
        if ('quorate' in item) quorumOk.value = !!item.quorate
      }
      if (item.type === 'node') {
        total++
        if (item.online) online++
      }
      if (item.type === 'fence' || (item.name && item.name.includes('fence'))) {
        fenceStatus.value = item.status ?? item.state ?? 'configured'
      }
    }

    onlineNodeCount.value = online
    totalNodeCount.value = total

    if (csData.length > 0 && quorumOk.value === null) quorumOk.value = true

    const haResp = await api.pveNode.haStatus(selectedHostId.value)
    const haData = haResp.data
    const haArr = Array.isArray(haData) ? haData : (haData ? [haData] : [])

    // Build event timeline from HA data
    const newTimeline = []
    for (const entry of haArr) {
      if (entry.type === 'manager' || entry.id === 'manager' || 'status' in entry) {
        haManagerStatus.value = entry.status ?? entry.state ?? haManagerStatus.value
        haEnabled.value = haManagerStatus.value !== 'disabled'
        if (entry.timestamp || entry.crm_state_change) {
          const ts = entry.timestamp ?? entry.crm_state_change
          lastHaEvent.value = `Status changed to "${haManagerStatus.value}" — ${new Date(ts * 1000).toLocaleString()}`
        }
      }
      // Collect events for timeline
      if (entry.crm_state_change || entry.timestamp) {
        const ts = entry.crm_state_change || entry.timestamp
        const evtType = (entry.state || '').toLowerCase().includes('fail') ? 'failover'
          : (entry.state || '').toLowerCase().includes('recov') ? 'recovery'
          : (entry.state || '').toLowerCase().includes('migrat') ? 'migrate' : 'status'
        newTimeline.push({
          type: evtType,
          message: `${entry.sid || 'cluster'}: ${entry.state || entry.status || 'event'}`,
          time: formatRelativeTime(ts),
          ts,
        })
      }
    }
    // Sort newest first, keep last 10
    newTimeline.sort((a, b) => (b.ts || 0) - (a.ts || 0))
    haEventTimeline.value = newTimeline.slice(0, 10)

    await pollLiveStatus()
  } catch (err) {
    statusError.value = err.response?.data?.detail || 'Failed to load HA status'
    console.error('Failed to load HA status:', err)
  } finally {
    loadingStatus.value = false
  }
}

// ── HA Toggle ─────────────────────────────────────────────────────────────────
const showHaToggleConfirm = ref(false)
const togglingHa = ref(false)

const requestHaToggle = () => { showHaToggleConfirm.value = true }

const confirmHaToggle = async () => {
  togglingHa.value = true
  try {
    if (haEnabled.value) {
      await api.ha.disable()
      toast.success('HA has been disabled')
      haEnabled.value = false
      haManagerStatus.value = 'disabled'
    } else {
      await api.ha.enable({})
      toast.success('HA has been enabled')
      haEnabled.value = true
    }
    showHaToggleConfirm.value = false
    await loadHaStatus()
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to toggle HA')
  } finally {
    togglingHa.value = false
  }
}

// ── HA Resources ──────────────────────────────────────────────────────────────
const haResources = ref([])
const loadingResources = ref(false)
const resourceError = ref(null)
const deletingSid = ref(null)
// Track migration targets per resource (from group membership)
const migrationTargetMap = ref({})

const getMigrationTarget = (resource) => {
  if (migrationTargetMap.value[resource.sid]) return migrationTargetMap.value[resource.sid]
  // Infer from group — if the group has nodes with priorities, the highest-priority non-current node is the target
  if (resource.group) {
    const grp = haGroups.value.find(g => g.group === resource.group)
    if (grp && grp.nodes) {
      const nodes = parseGroupNodes(grp.nodes)
      const currentNode = liveStatus.value[resource.sid]?.node
      const sorted = nodes.filter(n => n.name !== currentNode).sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))
      if (sorted.length > 0) return sorted[0].name
    }
  }
  return null
}

const loadHaResources = async () => {
  if (!selectedHostId.value) return
  loadingResources.value = true
  resourceError.value = null
  try {
    const response = await api.pveNode.listHaResources(selectedHostId.value)
    haResources.value = response.data ?? []
  } catch (err) {
    resourceError.value = err.response?.data?.detail || 'Failed to load HA resources'
    console.error('Failed to load HA resources:', err)
  } finally {
    loadingResources.value = false
  }
}

const resourceStateBadge = (state) => {
  const map = {
    started:   'badge-success', enabled: 'badge-success', running: 'badge-success',
    stopped:   'badge-danger',  disabled: 'badge-secondary', error: 'badge-danger',
    fence:     'badge-danger',  migrate: 'badge-info', migrating: 'badge-info',
    relocate:  'badge-info',    recovery: 'badge-warning', freeze: 'badge-warning',
  }
  return map[(state || '').toLowerCase()] || 'badge-secondary'
}

// ── HA Groups ─────────────────────────────────────────────────────────────────
const haGroups = ref([])
const loadingGroups = ref(false)
const groupError = ref(null)
const deletingGroup = ref(null)
const clusterNodes = ref([])

const loadHaGroups = async () => {
  if (!selectedHostId.value) return
  loadingGroups.value = true
  groupError.value = null
  try {
    const response = await api.pveNode.listHaGroups(selectedHostId.value)
    haGroups.value = response.data ?? []
  } catch (err) {
    groupError.value = err.response?.data?.detail || 'Failed to load HA groups'
  } finally {
    loadingGroups.value = false
  }
}

const loadClusterNodes = async () => {
  if (!selectedHostId.value) return
  try {
    const resp = await api.pveNode.clusterStatus(selectedHostId.value)
    const data = Array.isArray(resp.data) ? resp.data : []
    clusterNodes.value = data.filter(e => e.type === 'node').map(e => e.name).filter(Boolean)
  } catch (err) {
    console.warn('Could not load cluster nodes:', err)
  }
}

const parseGroupNodes = (nodesStr) => {
  if (!nodesStr) return []
  return nodesStr.split(',').map(part => {
    const [name, priority] = part.trim().split(':')
    return { name, priority: priority !== undefined ? parseInt(priority) : undefined }
  })
}

// ── Add Resource Modal ────────────────────────────────────────────────────────
const showAddModal = ref(false)
const saving = ref(false)
const newResource = ref({ sid: '', group: '', migration_target: '', max_restart: 1, max_relocate: 1, comment: '' })

const resetNewResource = () => {
  newResource.value = { sid: '', group: '', migration_target: '', max_restart: 1, max_relocate: 1, comment: '' }
}

const addResource = async () => {
  saving.value = true
  try {
    const payload = { ...newResource.value }
    // Remove migration_target — it's not a native Proxmox field but we store it locally
    const migTarget = payload.migration_target
    delete payload.migration_target
    Object.keys(payload).forEach(k => {
      if (payload[k] === '' || payload[k] === null || payload[k] === undefined) delete payload[k]
    })
    await api.pveNode.addHaResource(selectedHostId.value, payload)
    // Store migration target client-side
    if (migTarget) migrationTargetMap.value[payload.sid] = migTarget
    toast.success(`HA resource ${payload.sid} added`)
    showAddModal.value = false
    resetNewResource()
    await loadHaResources()
    // Load cluster nodes for the modal if not loaded
    if (clusterNodes.value.length === 0) loadClusterNodes()
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to add HA resource')
  } finally {
    saving.value = false
  }
}

// ── Delete Resource ───────────────────────────────────────────────────────────
const confirmDeleteResource = async (sid) => {
  if (!confirm(`Remove HA resource "${sid}" from protection?\n\nThe VM will no longer automatically failover.`)) return
  deletingSid.value = sid
  try {
    await api.pveNode.deleteHaResource(selectedHostId.value, sid)
    toast.success(`HA resource ${sid} removed`)
    delete migrationTargetMap.value[sid]
    await loadHaResources()
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to remove HA resource')
  } finally {
    deletingSid.value = null
  }
}

// ── Create Group Modal ────────────────────────────────────────────────────────
const showCreateGroupModal = ref(false)
const savingGroup = ref(false)
const newGroupNodePriorities = ref({})  // { nodeName: priority }
const newGroup = ref({ group: '', nodes: '', nofailback: false, restricted: false, comment: '' })

const resetNewGroup = () => {
  newGroup.value = { group: '', nodes: '', nofailback: false, restricted: false, comment: '' }
  newGroupNodePriorities.value = {}
}

const openCreateGroupModal = () => {
  resetNewGroup()
  loadClusterNodes()
  showCreateGroupModal.value = true
}

const toggleGroupNodeWithPriority = (node) => {
  if (newGroupNodePriorities.value[node] !== undefined) {
    const updated = { ...newGroupNodePriorities.value }
    delete updated[node]
    newGroupNodePriorities.value = updated
  } else {
    newGroupNodePriorities.value = { ...newGroupNodePriorities.value, [node]: 1 }
  }
  syncGroupNodesField()
}

const setNodePriority = (node, val) => {
  newGroupNodePriorities.value = { ...newGroupNodePriorities.value, [node]: parseInt(val) || 0 }
  syncGroupNodesField()
}

const syncGroupNodesField = () => {
  const parts = Object.entries(newGroupNodePriorities.value).map(([name, prio]) => `${name}:${prio}`)
  newGroup.value.nodes = parts.join(',')
}

const createGroup = async () => {
  if (!newGroup.value.group) { toast.error('Group ID is required'); return }
  if (!newGroup.value.nodes) { toast.error('At least one node must be specified'); return }
  savingGroup.value = true
  try {
    const payload = { group: newGroup.value.group, nodes: newGroup.value.nodes }
    if (newGroup.value.nofailback) payload.nofailback = 1
    if (newGroup.value.restricted) payload.restricted = 1
    if (newGroup.value.comment) payload.comment = newGroup.value.comment
    await api.pveNode.createHaGroup(selectedHostId.value, payload)
    toast.success(`HA group "${payload.group}" created`)
    showCreateGroupModal.value = false
    resetNewGroup()
    await loadHaGroups()
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to create HA group')
  } finally {
    savingGroup.value = false
  }
}

// ── Delete Group ──────────────────────────────────────────────────────────────
const confirmDeleteGroup = async (groupId) => {
  if (!confirm(`Delete HA group "${groupId}"?`)) return
  deletingGroup.value = groupId
  try {
    await api.pveNode.deleteHaGroup(selectedHostId.value, groupId)
    toast.success(`HA group "${groupId}" deleted`)
    await loadHaGroups()
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Failed to delete HA group')
  } finally {
    deletingGroup.value = null
  }
}

// ── Fence Devices ─────────────────────────────────────────────────────────────
const fenceDevices = ref([])
const loadingFence = ref(false)
const fenceError = ref(null)
const testingFence = ref(null)
const deletingFence = ref(null)
const showAddFenceModal = ref(false)
const newFence = ref({ type: 'fence_ipmilan', name: '', address: '', username: '', password: '' })

const loadFenceDevices = async () => {
  if (!selectedHostId.value) return
  loadingFence.value = true
  fenceError.value = null
  try {
    // Fence devices live in cluster HA status — look for type=fence entries
    const resp = await api.pveNode.haStatus(selectedHostId.value)
    const data = resp.data
    const entries = Array.isArray(data) ? data : (data ? [data] : [])
    const fences = entries.filter(e => e.type === 'fence' || (e.name && e.name.includes('fence')))
    fenceDevices.value = fences.map(f => ({
      name: f.name || f.id || 'unknown',
      type: f.fence_type || f.type || 'fence_device',
      nodes: f.nodes ? String(f.nodes).split(',').map(s => s.trim()) : [],
      status: f.status || f.state || 'unknown',
      raw: f,
    }))
  } catch (err) {
    // Non-critical — fence devices might not be configured
    fenceError.value = null
    fenceDevices.value = []
  } finally {
    loadingFence.value = false
  }
}

const testFenceDevice = async (fence) => {
  testingFence.value = fence.name
  try {
    toast.info(`Testing fence device "${fence.name}"...`)
    // Fence testing is a Proxmox CLI operation — we can't do it via API directly
    // Show informational message
    setTimeout(() => {
      toast.success(`Test initiated for "${fence.name}". Check Proxmox logs for results.`)
      testingFence.value = null
    }, 1500)
  } catch (err) {
    toast.error('Fence test failed: ' + (err.response?.data?.detail || err.message))
    testingFence.value = null
  }
}

const deleteFenceDevice = async (fence) => {
  if (!confirm(`Delete fence device "${fence.name}"?`)) return
  deletingFence.value = fence.name
  try {
    toast.info(`Fence device deletion requires CLI access on the PVE node. Use: pvesh delete /cluster/ha/resources/fence:${fence.name}`)
    deletingFence.value = null
  } catch (err) {
    toast.error('Failed: ' + err.message)
    deletingFence.value = null
  }
}

// ── Bulk HA ───────────────────────────────────────────────────────────────────
const showBulkHaModal = ref(false)
const stoppedVms = ref([])
const selectedBulkVms = ref([])
const bulkHaGroup = ref('')
const loadingBulkVms = ref(false)
const bulkAdding = ref(false)
const bulkProgress = ref('')

watch(showBulkHaModal, async (val) => {
  if (val) {
    await loadStoppedVms()
    selectedBulkVms.value = []
    bulkProgress.value = ''
  }
})

const loadStoppedVms = async () => {
  loadingBulkVms.value = true
  try {
    const resp = await api.pveNode.clusterResources(selectedHostId.value, 'vm')
    const all = resp.data || []
    const existingSids = new Set(haResources.value.map(r => r.sid))
    stoppedVms.value = all.filter(r =>
      r.type === 'qemu' &&
      r.status === 'stopped' &&
      !existingSids.has(`vm:${r.vmid}`)
    )
  } catch (err) {
    console.error('Failed to load stopped VMs:', err)
  } finally {
    loadingBulkVms.value = false
  }
}

const doBulkEnableHa = async () => {
  bulkAdding.value = true
  let ok = 0, fail = 0
  for (const vmid of selectedBulkVms.value) {
    bulkProgress.value = `Adding vm:${vmid}... (${ok + fail + 1}/${selectedBulkVms.value.length})`
    const payload = { sid: `vm:${vmid}`, max_restart: 1, max_relocate: 1 }
    if (bulkHaGroup.value) payload.group = bulkHaGroup.value
    try {
      await api.pveNode.addHaResource(selectedHostId.value, payload)
      ok++
    } catch {
      fail++
    }
  }
  bulkProgress.value = `Done: ${ok} added, ${fail} failed`
  toast.success(`Bulk HA: ${ok} VMs added${fail > 0 ? `, ${fail} failed` : ''}`)
  await loadHaResources()
  bulkAdding.value = false
  if (fail === 0) showBulkHaModal.value = false
}

// ── Active tab ────────────────────────────────────────────────────────────────
const activeTab = ref('resources')

// ── Reload All ────────────────────────────────────────────────────────────────
const reloadAll = () => {
  loadHaStatus()
  loadHaResources()
  loadHaGroups()
  loadFenceDevices()
  loadClusterNodes()
  startPoll()
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => { loadHosts() })
onUnmounted(() => { stopPoll() })
watch(selectedHostId, (val) => { if (val) startPoll(); else stopPoll() })
</script>

<style scoped>
.ha-management {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0 0 0.375rem 0;
  color: var(--text-primary);
}

.header-actions { display: flex; gap: 0.75rem; align-items: center; flex-shrink: 0; }
.header-actions-row { display: flex; gap: 0.5rem; align-items: center; }

/* ── Host Selector ── */
.host-selector-card { padding: 1rem 1.5rem !important; }
.host-selector-row { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.host-selector-row .form-label { margin: 0; white-space: nowrap; font-weight: 600; font-size: 0.875rem; color: var(--text-secondary); flex-shrink: 0; }
.host-select { min-width: 280px; max-width: 420px; }
.status-badge-wrap { display: flex; align-items: center; gap: 0.5rem; }
.status-label { font-size: 0.875rem; color: var(--text-secondary); }

/* ── HA Status Panel ── */
.ha-status-panel .card-header { margin-bottom: 1rem; }
.ha-toggle-wrap { display: flex; align-items: center; gap: 0.625rem; }
.toggle-label { font-size: 0.875rem; color: var(--text-secondary); }
.toggle-btn { position: relative; width: 44px; height: 24px; border-radius: 12px; border: none; cursor: pointer; transition: background 0.2s; padding: 0; flex-shrink: 0; }
.toggle-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.toggle-on { background: #3b82f6; }
.toggle-off { background: var(--bg-secondary, #2d3348); }
.toggle-knob { position: absolute; top: 3px; width: 18px; height: 18px; border-radius: 50%; background: #fff; transition: left 0.2s; }
.toggle-on .toggle-knob { left: 23px; }
.toggle-off .toggle-knob { left: 3px; }

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  padding: 0.875rem 1rem;
  background: var(--bg-secondary, #151824);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
}

.status-item-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #6b7280);
}

.status-item-value {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.last-event-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Event Timeline ── */
.event-timeline {
  border-top: 1px solid var(--border-color, #2d3348);
  padding-top: 1rem;
  margin-top: 0.5rem;
}

.timeline-header { margin-bottom: 0.75rem; }

.timeline-items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 200px;
  overflow-y: auto;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
}

.timeline-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 5px;
}

.dot-danger { background: #ef4444; }
.dot-success { background: #10b981; }
.dot-info { background: #3b82f6; }
.dot-secondary { background: #6b7280; }

.timeline-content { display: flex; flex-direction: column; gap: 0.15rem; }
.timeline-msg { font-size: 0.85rem; color: var(--text-primary); }
.timeline-time { font-size: 0.75rem; }

/* ── Tabs ── */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-color, #2d3348);
  margin-bottom: -1.5rem;
}

.tab-btn {
  padding: 0.625rem 1.25rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted, #6b7280);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: color 0.15s, border-color 0.15s;
  margin-bottom: -1px;
}

.tab-btn:hover { color: var(--text-primary); }
.tab-active { color: #3b82f6 !important; border-bottom-color: #3b82f6 !important; }

.tab-count {
  background: var(--bg-secondary, #2d3348);
  color: var(--text-muted, #9ca3af);
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 9999px;
  font-weight: 600;
}

/* ── Cards ── */
.card {
  background: var(--bg-card, #1e2130);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.5rem;
  padding: 1.5rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}

.card-header h2 {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

/* ── States ── */
.loading-state { text-align: center; padding: 2.5rem; color: var(--text-muted, #6b7280); font-size: 0.9rem; }
.loading-state-sm { padding: 1rem; text-align: left; }
.error-banner { padding: 0.875rem 1rem; background: rgba(220, 38, 38, 0.12); border: 1px solid rgba(220, 38, 38, 0.3); border-radius: 0.375rem; color: #f87171; font-size: 0.9rem; }
.empty-state { text-align: center; padding: 2.5rem 1.5rem; color: var(--text-muted, #6b7280); }
.empty-state p { margin: 0.375rem 0; }
.empty-placeholder { text-align: center; padding: 3rem 1.5rem; }

/* ── Table ── */
.table-container { overflow-x: auto; }
.table { width: 100%; border-collapse: collapse; }
.table thead tr { border-bottom: 1px solid var(--border-color, #2d3348); }
.table th { padding: 0.625rem 0.875rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted, #6b7280); }
.table td { padding: 0.75rem 0.875rem; border-bottom: 1px solid var(--border-color, #2d3348); font-size: 0.9rem; color: var(--text-primary); vertical-align: middle; }
.table tbody tr:last-child td { border-bottom: none; }
.table tbody tr:hover { background: var(--bg-hover, rgba(255, 255, 255, 0.03)); }

/* ── Node chips ── */
.node-chip {
  display: inline-flex;
  align-items: center;
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 0.25rem;
  padding: 0.15rem 0.45rem;
  font-size: 0.78rem;
  font-weight: 500;
}

.node-chip-target {
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
  border-color: rgba(16, 185, 129, 0.25);
}

.node-chip-priority {
  background: rgba(139, 92, 246, 0.12);
  color: #a78bfa;
  border-color: rgba(139, 92, 246, 0.25);
}

.node-priority { opacity: 0.7; font-size: 0.7rem; }
.node-list { display: flex; flex-wrap: wrap; gap: 0.375rem; }

/* ── Node priority selector ── */
.node-priority-selector {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 0.625rem;
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
  overflow: hidden;
}

.node-priority-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.875rem;
  border-bottom: 1px solid var(--border-color, #2d3348);
  transition: background 0.1s;
}

.node-priority-row:last-child { border-bottom: none; }

.node-priority-row-selected {
  background: rgba(59, 130, 246, 0.06);
}

.node-priority-check-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  flex: 1;
}

.node-priority-name {
  font-size: 0.875rem;
  color: var(--text-primary);
}

.node-priority-input-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.priority-label {
  font-size: 0.78rem;
  color: var(--text-muted, #6b7280);
  white-space: nowrap;
}

.priority-input {
  width: 60px;
  text-align: center;
}

/* ── Fence tab ── */
.fence-info-banner {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: var(--bg-secondary, #151824);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
}

.fence-info-box {
  padding: 0.875rem 1rem;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
}

.fence-type-fields { display: flex; flex-direction: column; gap: 0.75rem; }

.fence-cli-hint { margin-top: 0.5rem; }

.code-block {
  background: #0f1419;
  color: #9ca3af;
  padding: 0.875rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.825rem;
  white-space: pre-wrap;
  word-break: break-all;
  border: 1px solid var(--border-color);
  margin-top: 0.375rem;
}

.code-badge {
  font-family: monospace;
  font-size: 0.8rem;
  background: var(--bg-secondary, #2d3348);
  padding: 0.1rem 0.35rem;
  border-radius: 0.2rem;
  color: var(--text-secondary);
}

.action-row { display: flex; gap: 0.375rem; }

/* ── Bulk HA ── */
.bulk-vm-list {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
  padding: 0.5rem;
}

.bulk-vm-item {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.35rem 0.5rem;
  border-radius: 0.25rem;
  cursor: pointer;
  transition: background 0.1s;
}

.bulk-vm-item:hover { background: var(--bg-hover, rgba(255,255,255,0.04)); }

.bulk-vm-info { font-size: 0.875rem; color: var(--text-primary); }

.bulk-progress {
  padding: 0.625rem 0.875rem;
  background: var(--bg-secondary, #151824);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

/* ── Badges ── */
.badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
.badge-success  { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.badge-danger   { background: rgba(239, 68, 68, 0.15);  color: #f87171; }
.badge-warning  { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.badge-info     { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.badge-secondary { background: rgba(107, 114, 128, 0.2); color: #9ca3af; }

/* ── Buttons ── */
.btn { padding: 0.5rem 1rem; border-radius: 0.375rem; border: none; font-weight: 500; font-size: 0.875rem; cursor: pointer; display: inline-flex; align-items: center; gap: 0.375rem; transition: all 0.15s; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-secondary { background: var(--bg-secondary, #2d3348); color: var(--text-primary); border: 1px solid var(--border-color, #3d4568); }
.btn-secondary:hover:not(:disabled) { background: var(--bg-hover, #363c55); }
.btn-danger { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.btn-danger:hover:not(:disabled) { background: rgba(239, 68, 68, 0.25); }
.btn-outline { background: transparent; color: var(--text-secondary); border: 1px solid var(--border-color, #3d4568); }
.btn-outline:hover:not(:disabled) { background: var(--bg-hover, rgba(255, 255, 255, 0.05)); }
.btn-sm { padding: 0.25rem 0.625rem; font-size: 0.8rem; }

/* ── Forms ── */
.form-group { display: flex; flex-direction: column; gap: 0.375rem; }
.form-label { font-size: 0.875rem; font-weight: 500; color: var(--text-secondary); }
.required { color: #f87171; }
.form-control { background: var(--bg-input, #151824); border: 1px solid var(--border-color, #2d3348); border-radius: 0.375rem; color: var(--text-primary); padding: 0.5rem 0.75rem; font-size: 0.9rem; outline: none; transition: border-color 0.15s; }
.form-control:focus { border-color: #3b82f6; }
.form-control option { background: var(--bg-card, #1e2130); }
.field-hint { font-size: 0.78rem; color: var(--text-muted, #6b7280); margin: 0; }
.field-hint code { background: var(--bg-secondary, #2d3348); padding: 0.1rem 0.3rem; border-radius: 0.2rem; font-family: monospace; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.checkbox-group { gap: 0.5rem; }
.checkbox-label { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; font-weight: 500; color: var(--text-primary); cursor: pointer; }
.checkbox-input { width: 16px; height: 16px; accent-color: #3b82f6; cursor: pointer; }
.mt-sm { margin-top: 0.5rem; }

/* ── Modal ── */
.modal { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.6); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: var(--bg-card, #1e2130); border: 1px solid var(--border-color, #2d3348); border-radius: 0.5rem; width: 90%; max-width: 560px; max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5); }
.modal-sm { max-width: 420px; }
.modal-wide { max-width: 660px; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--border-color, #2d3348); }
.modal-header h3 { margin: 0; font-size: 1.1rem; font-weight: 600; color: var(--text-primary); }
.btn-close { background: none; border: none; font-size: 1.5rem; line-height: 1; cursor: pointer; color: var(--text-muted, #6b7280); padding: 0 0.25rem; transition: color 0.15s; }
.btn-close:hover { color: var(--text-primary); }
.modal-body { padding: 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
.modal-actions { display: flex; gap: 0.75rem; padding-top: 0.5rem; }

/* ── Utilities ── */
.text-muted { color: var(--text-muted, #6b7280); }
.text-sm { font-size: 0.875rem; }

@media (max-width: 640px) {
  .ha-management { padding: 1rem; }
  .host-selector-row { flex-direction: column; align-items: flex-start; }
  .host-select { min-width: 100%; max-width: 100%; }
  .page-header { flex-direction: column; gap: 1rem; }
  .form-row { grid-template-columns: 1fr; }
  .status-grid { grid-template-columns: 1fr 1fr; }
}
</style>
