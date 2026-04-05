<template>
  <div class="network-management-page">
    <div class="page-header mb-3">
      <div class="header-left">
        <h2>Network Management</h2>
        <p class="text-muted">Manage Proxmox node network interfaces — bridges, bonds, VLANs, and more</p>
      </div>
    </div>

    <!-- Host / Node selector bar -->
    <div class="selector-bar card mb-3">
      <div class="selector-inner">
        <div class="selector-group">
          <label class="form-label mb-0">Proxmox Host</label>
          <select v-model="selectedHostId" class="form-control" @change="onHostChange" :disabled="loadingHosts">
            <option value="">{{ loadingHosts ? 'Loading...' : '— Select Host —' }}</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
          </select>
        </div>
        <div class="selector-group" v-if="selectedHostId">
          <label class="form-label mb-0">Node</label>
          <select v-model="selectedNode" class="form-control" @change="onNodeChange" :disabled="loadingNodes">
            <option value="">{{ loadingNodes ? 'Loading...' : '— Select Node —' }}</option>
            <option v-for="n in nodes" :key="n.node_name || n.node" :value="n.node_name || n.node">
              {{ n.node_name || n.node }}
            </option>
          </select>
        </div>
        <div v-if="selectedNode" class="selector-actions">
          <span v-if="pendingCount > 0" class="badge badge-warning pending-badge">
            {{ pendingCount }} pending change{{ pendingCount !== 1 ? 's' : '' }}
          </span>
          <button class="btn btn-outline" @click="fetchInterfaces" :disabled="loading" title="Refresh interface list">
            &#8635; Refresh
          </button>
          <button
            class="btn btn-warning"
            @click="applyConfig"
            :disabled="savingApply"
            title="Apply pending network changes (will briefly disrupt networking)"
          >
            {{ savingApply ? 'Applying...' : 'Apply Config' }}
          </button>
          <button
            class="btn btn-outline"
            @click="revertConfig"
            :disabled="savingRevert"
            title="Revert pending (unapplied) changes"
          >
            {{ savingRevert ? 'Reverting...' : 'Revert' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-spinner"></div>

    <!-- Placeholder -->
    <div v-else-if="!selectedNode" class="card text-center text-muted" style="padding: 3rem;">
      <p>Select a host and node above to view and manage network interfaces.</p>
    </div>

    <!-- Content when node is selected -->
    <div v-else>

      <!-- Workflow banner when pending changes exist -->
      <div v-if="pendingCount > 0" class="workflow-banner mb-3">
        <div class="workflow-step done">
          <span class="step-num">1</span>
          <span>Stage Changes</span>
        </div>
        <div class="workflow-arrow">→</div>
        <div class="workflow-step active">
          <span class="step-num">2</span>
          <span>Apply Config</span>
        </div>
        <div class="workflow-arrow">→</div>
        <div class="workflow-step">
          <span class="step-num">3</span>
          <span>Network Reloads</span>
        </div>
        <div class="workflow-info">
          You have <strong>{{ pendingCount }}</strong> staged change{{ pendingCount !== 1 ? 's' : '' }} waiting to be applied.
          <button class="btn btn-warning btn-sm ml-1" @click="applyConfig" :disabled="savingApply">
            {{ savingApply ? 'Applying...' : 'Apply Now' }}
          </button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tab-bar mb-3">
        <button :class="['tab-btn', { active: activeNetTab === 'interfaces' }]" @click="activeNetTab = 'interfaces'">
          Interfaces
          <span v-if="interfaces.length" class="tab-count">{{ interfaces.length }}</span>
        </button>
        <button :class="['tab-btn', { active: activeNetTab === 'bridges' }]" @click="activeNetTab = 'bridges'">
          Bridges
          <span v-if="bridgeInterfaces.length" class="tab-count">{{ bridgeInterfaces.length }}</span>
        </button>
        <button :class="['tab-btn', { active: activeNetTab === 'vlans' }]" @click="activeNetTab = 'vlans'">
          VLANs
          <span v-if="vlanInterfaces.length" class="tab-count">{{ vlanInterfaces.length }}</span>
        </button>
        <button :class="['tab-btn', { active: activeNetTab === 'config' }]" @click="activeNetTab = 'config'">
          /etc/network/interfaces
        </button>
      </div>

      <!-- ══ INTERFACES TAB ════════════════════════════════════════════════════ -->
      <div v-if="activeNetTab === 'interfaces'">
        <div class="card">
          <div class="card-header">
            <div class="header-title-group">
              <h3>Network Interfaces — {{ selectedNode }}</h3>
              <span class="text-muted text-sm">{{ interfaces.length }} interface{{ interfaces.length !== 1 ? 's' : '' }}</span>
            </div>
            <button class="btn btn-primary" @click="openCreateModal">+ Create Interface</button>
          </div>

          <div v-if="interfaces.length === 0" class="text-center text-muted" style="padding: 2rem;">
            <p>No network interfaces found.</p>
          </div>

          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Interface</th>
                  <th>Type</th>
                  <th>Address / CIDR</th>
                  <th>Gateway</th>
                  <th>Ports / Slaves</th>
                  <th>Autostart</th>
                  <th>State</th>
                  <th>Comment</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="iface in interfaces" :key="iface.iface" :class="{ 'row-pending': iface.pending }">
                  <td>
                    <div class="iface-name-cell">
                      <strong>{{ iface.iface }}</strong>
                      <span v-if="iface.pending" class="pending-dot" title="Pending change"></span>
                    </div>
                  </td>
                  <td>
                    <span :class="['badge', getTypeBadge(iface.type)]">
                      {{ iface.type || 'eth' }}
                    </span>
                  </td>
                  <td class="text-sm mono">
                    <span v-if="iface.address">{{ iface.address }}<span v-if="iface.netmask">/{{ cidrFromNetmask(iface.netmask) }}</span></span>
                    <span v-else-if="iface.cidr">{{ iface.cidr }}</span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="text-sm mono">{{ iface.gateway || '—' }}</td>
                  <td class="text-sm">
                    <span v-if="iface['bridge-ports']">{{ iface['bridge-ports'] }}</span>
                    <span v-else-if="iface.slaves">{{ iface.slaves }}</span>
                    <span v-else>—</span>
                  </td>
                  <td>
                    <span :class="['badge', iface.autostart ? 'badge-success' : 'badge-secondary']">
                      {{ iface.autostart ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td>
                    <span v-if="iface.pending" class="badge badge-warning">Pending</span>
                    <span v-else :class="['badge', iface.active ? 'badge-success' : 'badge-danger']">
                      {{ iface.active ? 'Active' : 'Inactive' }}
                    </span>
                  </td>
                  <td class="text-sm">{{ iface.comments || iface.comment || '—' }}</td>
                  <td>
                    <div class="action-btns">
                      <button @click="openEditModal(iface)" class="btn btn-outline btn-sm">Edit</button>
                      <button @click="confirmDelete(iface)" class="btn btn-danger btn-sm">Delete</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══ BRIDGES TAB ═══════════════════════════════════════════════════════ -->
      <div v-if="activeNetTab === 'bridges'">
        <!-- Quick Create Bridge form -->
        <div class="card mb-3">
          <div class="card-header">
            <h3>Quick Create Bridge</h3>
            <span class="text-muted text-sm">Stage a new Linux bridge interface</span>
          </div>
          <div class="quick-form">
            <div class="form-row-quick">
              <div class="form-group">
                <label class="form-label">Bridge Name <span class="text-danger">*</span></label>
                <div class="input-prefix-group">
                  <span class="input-prefix">vmbr</span>
                  <input
                    v-model.number="quickBridge.num"
                    type="number"
                    class="form-control"
                    placeholder="0"
                    min="0"
                    max="9999"
                  />
                </div>
                <div class="help-text-sm">Will create <code>vmbr{{ quickBridge.num != null ? quickBridge.num : 'N' }}</code></div>
              </div>
              <div class="form-group">
                <label class="form-label">Bridge Ports</label>
                <input v-model="quickBridge.ports" class="form-control" placeholder="e.g. eth0 (space-separated)" />
                <div class="help-text-sm">Physical ports to attach. Leave blank for portless bridge.</div>
              </div>
              <div class="form-group">
                <label class="form-label">IP / CIDR</label>
                <input v-model="quickBridge.cidr" class="form-control" placeholder="e.g. 192.168.1.1/24" />
              </div>
              <div class="form-group">
                <label class="form-label">Gateway</label>
                <input v-model="quickBridge.gateway" class="form-control" placeholder="e.g. 192.168.1.254" />
              </div>
            </div>
            <div class="form-row-quick">
              <div class="form-group flex-center">
                <label class="form-label toggle-label">
                  <input type="checkbox" v-model="quickBridge.vlanAware" />
                  <span>VLAN Aware</span>
                </label>
                <div class="help-text-sm">Enable to allow 802.1q VLAN tagging on VMs attached to this bridge.</div>
              </div>
              <div class="form-group flex-center">
                <label class="form-label toggle-label">
                  <input type="checkbox" v-model="quickBridge.stp" />
                  <span>STP (Spanning Tree)</span>
                </label>
              </div>
              <div class="form-group">
                <label class="form-label">Comment</label>
                <input v-model="quickBridge.comment" class="form-control" placeholder="Optional description" />
              </div>
              <div class="form-group flex-end">
                <button
                  class="btn btn-primary"
                  @click="createQuickBridge"
                  :disabled="savingQuickBridge || quickBridge.num == null"
                >
                  {{ savingQuickBridge ? 'Creating...' : 'Stage Bridge' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Bridge interfaces table -->
        <div class="card">
          <div class="card-header">
            <h3>Bridge Interfaces — {{ selectedNode }}</h3>
            <span class="text-muted text-sm">{{ bridgeInterfaces.length }} bridge{{ bridgeInterfaces.length !== 1 ? 's' : '' }}</span>
          </div>
          <div v-if="bridgeInterfaces.length === 0" class="text-center text-muted" style="padding: 2rem;">
            No bridge interfaces found on this node.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Bridge</th>
                  <th>Ports</th>
                  <th>IP / CIDR</th>
                  <th>VLAN Aware</th>
                  <th>STP</th>
                  <th>State</th>
                  <th>Comment</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="br in bridgeInterfaces" :key="br.iface" :class="{ 'row-pending': br.pending }">
                  <td>
                    <div class="iface-name-cell">
                      <strong>{{ br.iface }}</strong>
                      <span v-if="br.pending" class="pending-dot" title="Pending change"></span>
                    </div>
                  </td>
                  <td class="text-sm">{{ br['bridge-ports'] || '—' }}</td>
                  <td class="text-sm mono">
                    <span v-if="br.address">{{ br.address }}<span v-if="br.netmask">/{{ cidrFromNetmask(br.netmask) }}</span></span>
                    <span v-else-if="br.cidr">{{ br.cidr }}</span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>
                    <span :class="['badge', (br['bridge_vlan_aware'] || br.bridge_vlan_aware) ? 'badge-success' : 'badge-secondary']">
                      {{ (br['bridge_vlan_aware'] || br.bridge_vlan_aware) ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td>
                    <span class="text-sm">{{ br['bridge_stp'] || br.bridge_stp || 'off' }}</span>
                  </td>
                  <td>
                    <span v-if="br.pending" class="badge badge-warning">Pending</span>
                    <span v-else :class="['badge', br.active ? 'badge-success' : 'badge-danger']">
                      {{ br.active ? 'Active' : 'Inactive' }}
                    </span>
                  </td>
                  <td class="text-sm">{{ br.comments || br.comment || '—' }}</td>
                  <td>
                    <div class="action-btns">
                      <button
                        @click="toggleBridgeVlanAware(br)"
                        class="btn btn-outline btn-sm"
                        :disabled="togglingBridge === br.iface"
                        :title="(br['bridge_vlan_aware'] || br.bridge_vlan_aware) ? 'Disable VLAN-aware' : 'Enable VLAN-aware'"
                      >
                        {{ togglingBridge === br.iface ? '...' : ((br['bridge_vlan_aware'] || br.bridge_vlan_aware) ? 'VLAN Off' : 'VLAN On') }}
                      </button>
                      <button @click="openEditModal(br)" class="btn btn-outline btn-sm">Edit</button>
                      <button @click="confirmDelete(br)" class="btn btn-danger btn-sm">Delete</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══ VLANS TAB ═════════════════════════════════════════════════════════ -->
      <div v-if="activeNetTab === 'vlans'">
        <!-- Quick Create VLAN form -->
        <div class="card mb-3">
          <div class="card-header">
            <h3>Quick Create VLAN Interface</h3>
            <span class="text-muted text-sm">Stage a new VLAN sub-interface</span>
          </div>
          <div class="quick-form">
            <div class="form-row-quick">
              <div class="form-group">
                <label class="form-label">Raw Device <span class="text-danger">*</span></label>
                <input v-model="quickVlan.rawDevice" class="form-control" placeholder="e.g. vmbr0 or eth0" />
                <div class="help-text-sm">Parent interface to tag. Usually a bridge or physical port.</div>
              </div>
              <div class="form-group">
                <label class="form-label">VLAN ID <span class="text-danger">*</span></label>
                <input v-model.number="quickVlan.tag" type="number" class="form-control" placeholder="e.g. 100" min="1" max="4094" />
                <div class="help-text-sm">
                  Interface will be named
                  <code>{{ quickVlan.rawDevice || 'device' }}.{{ quickVlan.tag || 'tag' }}</code>
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">IP / CIDR</label>
                <input v-model="quickVlan.cidr" class="form-control" placeholder="e.g. 192.168.100.1/24" />
              </div>
              <div class="form-group">
                <label class="form-label">Gateway</label>
                <input v-model="quickVlan.gateway" class="form-control" placeholder="e.g. 192.168.100.254" />
              </div>
            </div>
            <div class="form-row-quick">
              <div class="form-group">
                <label class="form-label">Comment</label>
                <input v-model="quickVlan.comment" class="form-control" placeholder="Optional description" />
              </div>
              <div class="form-group flex-center">
                <label class="form-label toggle-label">
                  <input type="checkbox" v-model="quickVlan.autostart" />
                  <span>Autostart on boot</span>
                </label>
              </div>
              <div class="form-group"></div>
              <div class="form-group flex-end">
                <button
                  class="btn btn-primary"
                  @click="createQuickVlan"
                  :disabled="savingQuickVlan || !quickVlan.rawDevice || !quickVlan.tag"
                >
                  {{ savingQuickVlan ? 'Creating...' : 'Stage VLAN' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- VLAN interfaces table -->
        <div class="card">
          <div class="card-header">
            <h3>VLAN Interfaces — {{ selectedNode }}</h3>
            <span class="text-muted text-sm">{{ vlanInterfaces.length }} VLAN interface{{ vlanInterfaces.length !== 1 ? 's' : '' }}</span>
          </div>
          <div v-if="vlanInterfaces.length === 0" class="text-center text-muted" style="padding: 2rem;">
            No VLAN interfaces found on this node.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Interface</th>
                  <th>Raw Device</th>
                  <th>VLAN Tag</th>
                  <th>IP / CIDR</th>
                  <th>Autostart</th>
                  <th>State</th>
                  <th>Comment</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="iface in vlanInterfaces" :key="iface.iface" :class="{ 'row-pending': iface.pending }">
                  <td>
                    <div class="iface-name-cell">
                      <strong>{{ iface.iface }}</strong>
                      <span v-if="iface.pending" class="pending-dot" title="Pending change"></span>
                    </div>
                  </td>
                  <td class="text-sm mono">{{ iface['vlan-raw-device'] || iface.vlan_raw_device || '—' }}</td>
                  <td>
                    <span class="vlan-tag-chip">{{ iface['vlan-id'] || iface.vlan_id || extractVlanTag(iface.iface) }}</span>
                  </td>
                  <td class="text-sm mono">
                    <span v-if="iface.address">{{ iface.address }}<span v-if="iface.netmask">/{{ cidrFromNetmask(iface.netmask) }}</span></span>
                    <span v-else-if="iface.cidr">{{ iface.cidr }}</span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>
                    <span :class="['badge', iface.autostart ? 'badge-success' : 'badge-secondary']">
                      {{ iface.autostart ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td>
                    <span v-if="iface.pending" class="badge badge-warning">Pending</span>
                    <span v-else :class="['badge', iface.active ? 'badge-success' : 'badge-danger']">
                      {{ iface.active ? 'Active' : 'Inactive' }}
                    </span>
                  </td>
                  <td class="text-sm">{{ iface.comments || iface.comment || '—' }}</td>
                  <td>
                    <div class="action-btns">
                      <button @click="openEditModal(iface)" class="btn btn-outline btn-sm">Edit</button>
                      <button @click="confirmDelete(iface)" class="btn btn-danger btn-sm">Delete</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══ CONFIG PREVIEW TAB ════════════════════════════════════════════════ -->
      <div v-if="activeNetTab === 'config'">
        <div class="card">
          <div class="card-header">
            <div class="header-title-group">
              <h3>/etc/network/interfaces — {{ selectedNode }}</h3>
              <span class="text-muted text-sm">Rendered from current interface configuration</span>
            </div>
            <button class="btn btn-outline" @click="fetchInterfaces" :disabled="loading">&#8635; Refresh</button>
          </div>

          <div v-if="interfaces.length === 0" class="text-center text-muted" style="padding: 2rem;">
            No interfaces loaded. Select a node first.
          </div>
          <div v-else class="config-preview-wrap">
            <div class="config-toolbar">
              <span class="config-toolbar-label">Syntax: Debian <code>interfaces(5)</code></span>
              <span v-if="pendingCount > 0" class="badge badge-warning">{{ pendingCount }} pending change{{ pendingCount !== 1 ? 's' : '' }} not yet applied</span>
              <button class="btn btn-outline btn-sm copy-btn" @click="copyConfig" title="Copy to clipboard">
                {{ copied ? 'Copied!' : 'Copy' }}
              </button>
            </div>
            <pre class="config-preview"><code v-html="highlightedConfig"></code></pre>
          </div>
        </div>

        <!-- Pending changes note -->
        <div v-if="pendingCount > 0" class="card mt-3">
          <div class="card-header">
            <h3>Staged Changes</h3>
            <span class="text-muted text-sm">These are buffered in Proxmox but not yet written to disk</span>
          </div>
          <div class="pending-changes-list">
            <div v-for="iface in pendingInterfaces" :key="iface.iface" class="pending-item">
              <span class="badge badge-warning">pending</span>
              <strong class="mono">{{ iface.iface }}</strong>
              <span class="text-muted text-sm">({{ iface.type || 'eth' }})</span>
              <span v-if="iface.cidr || iface.address" class="text-sm mono ml-1">
                {{ iface.cidr || iface.address }}
              </span>
            </div>
            <div class="pending-actions">
              <button class="btn btn-warning" @click="applyConfig" :disabled="savingApply">
                {{ savingApply ? 'Applying...' : 'Apply All Changes' }}
              </button>
              <button class="btn btn-outline" @click="revertConfig" :disabled="savingRevert">
                {{ savingRevert ? 'Reverting...' : 'Revert All' }}
              </button>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- ═══════════════════════════════════════════════════════════════════════
         MODALS
    ══════════════════════════════════════════════════════════════════════════ -->

    <!-- Create / Edit Interface Modal -->
    <div v-if="showModal" class="modal" @click.self="showModal = false">
      <div class="modal-content modal-lg" @click.stop>
        <div class="modal-header">
          <h3>{{ editingIface ? 'Edit Interface' : 'Create Network Interface' }}</h3>
          <button @click="showModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitModal" class="modal-body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Interface Name <span class="text-danger">*</span></label>
              <input
                v-model="form.iface"
                class="form-control"
                placeholder="e.g. vmbr0, bond0, eth0"
                :disabled="!!editingIface"
                required
              />
            </div>
            <div class="form-group">
              <label class="form-label">Type <span class="text-danger">*</span></label>
              <select v-model="form.type" class="form-control" required>
                <option value="bridge">Bridge</option>
                <option value="bond">Bond</option>
                <option value="eth">Ethernet</option>
                <option value="vlan">VLAN</option>
                <option value="OVSBridge">OVS Bridge</option>
                <option value="OVSBond">OVS Bond</option>
                <option value="OVSPort">OVS Port</option>
                <option value="OVSIntPort">OVS Int Port</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">IP Address / CIDR</label>
              <input v-model="form.cidr" class="form-control" placeholder="e.g. 192.168.1.100/24" />
            </div>
            <div class="form-group">
              <label class="form-label">Gateway</label>
              <input v-model="form.gateway" class="form-control" placeholder="e.g. 192.168.1.1" />
            </div>
          </div>

          <!-- Bridge ports (type=bridge) -->
          <div class="form-group" v-if="form.type === 'bridge' || form.type === 'OVSBridge'">
            <label class="form-label">Bridge Ports</label>
            <input v-model="form.bridge_ports" class="form-control" placeholder="e.g. eth0 (space-separated)" />
          </div>

          <!-- Bridge options -->
          <div class="form-row" v-if="form.type === 'bridge'">
            <div class="form-group">
              <label class="form-label toggle-label" style="margin-top: 0.5rem;">
                <input type="checkbox" v-model="form.bridge_vlan_aware" />
                <span>VLAN Aware Bridge</span>
              </label>
              <div class="help-text-sm">Enables 802.1q VLAN tagging for VMs using this bridge.</div>
            </div>
            <div class="form-group">
              <label class="form-label toggle-label" style="margin-top: 0.5rem;">
                <input type="checkbox" v-model="form.bridge_stp" />
                <span>Enable STP (Spanning Tree)</span>
              </label>
            </div>
          </div>

          <!-- Bond slaves (type=bond) -->
          <div class="form-group" v-if="form.type === 'bond' || form.type === 'OVSBond'">
            <label class="form-label">Bond Slaves</label>
            <input v-model="form.slaves" class="form-control" placeholder="e.g. eth0 eth1 (space-separated)" />
            <div class="form-row mt-1">
              <div class="form-group">
                <label class="form-label">Bond Mode</label>
                <select v-model="form.bond_mode" class="form-control">
                  <option value="">— default —</option>
                  <option value="balance-rr">balance-rr (Round Robin)</option>
                  <option value="active-backup">active-backup (Failover)</option>
                  <option value="balance-xor">balance-xor (XOR)</option>
                  <option value="broadcast">broadcast</option>
                  <option value="802.3ad">802.3ad (LACP)</option>
                  <option value="balance-tlb">balance-tlb (Adaptive Tx)</option>
                  <option value="balance-alb">balance-alb (Adaptive LB)</option>
                </select>
              </div>
            </div>
          </div>

          <!-- VLAN tag (type=vlan) -->
          <div class="form-row" v-if="form.type === 'vlan'">
            <div class="form-group">
              <label class="form-label">Raw Device</label>
              <input v-model="form.vlan_raw_device" type="text" class="form-control" placeholder="e.g. eth0 or vmbr0" />
              <div class="help-text-sm">Parent interface for VLAN tagging. Interface will be named <code>{{ form.vlan_raw_device || 'device' }}.{{ form.vlan_id || 'tag' }}</code></div>
            </div>
            <div class="form-group">
              <label class="form-label">VLAN Tag (ID)</label>
              <input v-model.number="form.vlan_id" type="number" class="form-control" placeholder="e.g. 100" min="1" max="4094" />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Comment</label>
              <input v-model="form.comments" class="form-control" placeholder="Optional description" />
            </div>
            <div class="form-group flex-center">
              <label class="form-label toggle-label" style="margin-top: 1.75rem;">
                <input type="checkbox" v-model="form.autostart" />
                <span>Autostart (bring up on boot)</span>
              </label>
            </div>
          </div>

          <div class="form-actions mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? 'Staging...' : (editingIface ? 'Update Interface' : 'Stage Interface') }}
            </button>
            <button type="button" @click="showModal = false" class="btn btn-outline">Cancel</button>
          </div>
          <p class="help-text-sm mt-1">
            Changes are staged (buffered by Proxmox) until you click "Apply Config". No network disruption until then.
          </p>
        </form>
      </div>
    </div>

    <!-- Apply warning modal -->
    <div v-if="showApplyWarning" class="modal" @click.self="showApplyWarning = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Apply Network Configuration</h3>
          <button @click="showApplyWarning = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="alert alert-warning mb-2">
            <strong>Warning:</strong> Applying network configuration will reload network interfaces on
            <strong>{{ selectedNode }}</strong>. This may briefly disrupt network connectivity to the node
            and any VMs using affected bridges or bonds.
          </div>
          <div class="workflow-mini mb-2">
            <span class="workflow-step-mini active">Stage</span>
            <span class="workflow-arrow">→</span>
            <span class="workflow-step-mini current">Apply</span>
            <span class="workflow-arrow">→</span>
            <span class="workflow-step-mini">Reload</span>
          </div>
          <p class="text-sm text-muted">
            After applying, the node will reload its network stack. If you lose connectivity,
            check the Proxmox console directly.
          </p>
          <div class="flex gap-1 mt-2">
            <button @click="doApplyConfig" class="btn btn-warning" :disabled="savingApply">
              {{ savingApply ? 'Applying...' : 'Yes, Apply Changes' }}
            </button>
            <button @click="showApplyWarning = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'NetworkManagement',
  setup() {
    const toast = useToast()

    // Hosts and nodes
    const hosts = ref([])
    const nodes = ref([])
    const selectedHostId = ref('')
    const selectedNode = ref('')
    const loadingHosts = ref(false)
    const loadingNodes = ref(false)

    // Interfaces
    const interfaces = ref([])
    const loading = ref(false)

    // Tabs
    const activeNetTab = ref('interfaces')

    // Saving states
    const saving = ref(false)
    const savingApply = ref(false)
    const savingRevert = ref(false)

    // Modals
    const showModal = ref(false)
    const showApplyWarning = ref(false)
    const editingIface = ref(null)

    // Copied state for config preview
    const copied = ref(false)

    // Quick bridge form
    const freshQuickBridge = () => ({
      num: null, ports: '', cidr: '', gateway: '', vlanAware: false, stp: false, comment: '',
    })
    const quickBridge = ref(freshQuickBridge())
    const savingQuickBridge = ref(false)

    // Quick VLAN form
    const freshQuickVlan = () => ({
      rawDevice: '', tag: null, cidr: '', gateway: '', comment: '', autostart: true,
    })
    const quickVlan = ref(freshQuickVlan())
    const savingQuickVlan = ref(false)

    // VLAN aware toggle state
    const togglingBridge = ref(null)

    // Form
    const freshForm = () => ({
      iface: '',
      type: 'bridge',
      cidr: '',
      gateway: '',
      bridge_ports: '',
      bridge_vlan_aware: false,
      bridge_stp: false,
      bridge_fd: 0,
      slaves: '',
      bond_mode: '',
      vlan_raw_device: '',
      vlan_id: null,
      comments: '',
      autostart: true,
    })
    const form = ref(freshForm())

    // Computed
    const bridgeInterfaces = computed(() => interfaces.value.filter(i => i.type === 'bridge'))
    const vlanInterfaces = computed(() => interfaces.value.filter(i => i.type === 'vlan'))
    const pendingInterfaces = computed(() => interfaces.value.filter(i => i.pending))
    const pendingCount = computed(() => pendingInterfaces.value.length)

    // ── /etc/network/interfaces config rendering ──────────────────────────────
    const renderedConfig = computed(() => {
      if (!interfaces.value.length) return ''
      const lines = ['# /etc/network/interfaces (rendered by Depl0y)', 'auto lo', 'iface lo inet loopback', '']
      for (const iface of interfaces.value) {
        const name = iface.iface
        const autostart = iface.autostart
        if (autostart) lines.push(`auto ${name}`)
        // Determine inet method
        const hasIp = iface.address || iface.cidr
        const method = hasIp ? 'static' : 'manual'
        lines.push(`iface ${name} inet ${method}`)
        if (iface.address && iface.netmask) {
          lines.push(`\taddress ${iface.address}`)
          lines.push(`\tnetmask ${iface.netmask}`)
        } else if (iface.cidr) {
          const [addr, prefix] = iface.cidr.split('/')
          lines.push(`\taddress ${addr}`)
          if (prefix) lines.push(`\tnetmask ${cidrToNetmask(parseInt(prefix))}`)
        }
        if (iface.gateway) lines.push(`\tgateway ${iface.gateway}`)
        // Type-specific
        if (iface.type === 'bridge') {
          if (iface['bridge-ports']) lines.push(`\tbridge_ports ${iface['bridge-ports']}`)
          if (iface['bridge_stp']) lines.push(`\tbridge_stp ${iface['bridge_stp']}`)
          if (iface['bridge_fd'] != null) lines.push(`\tbridge_fd ${iface['bridge_fd']}`)
          if (iface['bridge_vlan_aware'] || iface.bridge_vlan_aware) lines.push(`\tbridge-vlan-aware yes`)
        }
        if (iface.type === 'bond') {
          if (iface.slaves) lines.push(`\tbond-slaves ${iface.slaves}`)
          if (iface.bond_mode) lines.push(`\tbond-mode ${iface.bond_mode}`)
        }
        if (iface.type === 'vlan') {
          const rawDev = iface['vlan-raw-device'] || iface.vlan_raw_device
          if (rawDev) lines.push(`\tvlan-raw-device ${rawDev}`)
          const vlanId = iface['vlan-id'] || iface.vlan_id || extractVlanTag(name)
          if (vlanId && vlanId !== '—') lines.push(`\tvlan-id ${vlanId}`)
        }
        if (iface.mtu) lines.push(`\tmtu ${iface.mtu}`)
        const comment = iface.comments || iface.comment
        if (comment) lines.push(`\t# ${comment}`)
        lines.push('')
      }
      return lines.join('\n')
    })

    const highlightedConfig = computed(() => {
      // Simple syntax highlighting for interfaces(5) format
      return renderedConfig.value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .split('\n')
        .map(line => {
          // Comment lines
          if (/^\s*#/.test(line)) {
            return `<span class="cfg-comment">${line}</span>`
          }
          // auto / iface keywords
          if (/^auto\s/.test(line)) {
            return line.replace(/^(auto)(\s+)(\S+)/, '<span class="cfg-kw">auto</span>$2<span class="cfg-iface">$3</span>')
          }
          if (/^iface\s/.test(line)) {
            return line.replace(/^(iface)(\s+)(\S+)(\s+)(inet|inet6)(\s+)(\S+)/, '<span class="cfg-kw">iface</span>$2<span class="cfg-iface">$3</span>$4<span class="cfg-proto">$5</span>$6<span class="cfg-method">$7</span>')
          }
          // Indented directives
          if (/^\t/.test(line)) {
            return line.replace(/^(\t)(\S+)(\s+)(.+)$/, '$1<span class="cfg-dir">$2</span>$3<span class="cfg-val">$4</span>')
          }
          return line
        })
        .join('\n')
    })

    const copyConfig = async () => {
      try {
        await navigator.clipboard.writeText(renderedConfig.value)
        copied.value = true
        setTimeout(() => { copied.value = false }, 2000)
      } catch {
        toast.error('Failed to copy to clipboard')
      }
    }

    // ── Fetch hosts ──────────────────────────────────────────────────────────
    const fetchHosts = async () => {
      loadingHosts.value = true
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = (res.data || []).filter(h => h.is_active)
      } catch {
        toast.error('Failed to load Proxmox hosts')
      } finally {
        loadingHosts.value = false
      }
    }

    const onHostChange = async () => {
      selectedNode.value = ''
      nodes.value = []
      interfaces.value = []
      activeNetTab.value = 'interfaces'
      if (!selectedHostId.value) return
      loadingNodes.value = true
      try {
        const res = await api.proxmox.listNodes(selectedHostId.value)
        nodes.value = res.data || []
      } catch {
        toast.error('Failed to load nodes')
      } finally {
        loadingNodes.value = false
      }
    }

    const onNodeChange = () => {
      interfaces.value = []
      activeNetTab.value = 'interfaces'
      if (selectedNode.value) fetchInterfaces()
    }

    // ── Fetch interfaces ─────────────────────────────────────────────────────
    const fetchInterfaces = async () => {
      if (!selectedHostId.value || !selectedNode.value) return
      loading.value = true
      try {
        const res = await api.pveNode.listNetwork(selectedHostId.value, selectedNode.value)
        interfaces.value = res.data || []
      } catch {
        toast.error('Failed to load network interfaces')
      } finally {
        loading.value = false
      }
    }

    // ── Create / Edit modal ──────────────────────────────────────────────────
    const openCreateModal = () => {
      editingIface.value = null
      form.value = freshForm()
      showModal.value = true
    }

    const openEditModal = (iface) => {
      editingIface.value = iface
      form.value = {
        iface: iface.iface,
        type: iface.type || 'eth',
        cidr: iface.cidr || (iface.address ? iface.address + (iface.netmask ? '/' + cidrFromNetmask(iface.netmask) : '') : ''),
        gateway: iface.gateway || '',
        bridge_ports: iface['bridge-ports'] || '',
        bridge_vlan_aware: !!(iface['bridge_vlan_aware'] || iface.bridge_vlan_aware),
        bridge_stp: iface['bridge_stp'] === 'on' || iface.bridge_stp === true,
        bridge_fd: iface['bridge_fd'] || 0,
        slaves: iface.slaves || '',
        bond_mode: iface.bond_mode || '',
        vlan_raw_device: iface['vlan-raw-device'] || iface.vlan_raw_device || '',
        vlan_id: iface['vlan-id'] || iface.vlan_id || null,
        comments: iface.comments || iface.comment || '',
        autostart: iface.autostart === 1 || iface.autostart === true,
      }
      showModal.value = true
    }

    const submitModal = async () => {
      saving.value = true
      try {
        const payload = buildPayload()
        if (editingIface.value) {
          await api.pveNode.updateNetwork(selectedHostId.value, selectedNode.value, form.value.iface, payload)
          toast.success(`Interface ${form.value.iface} staged for update`)
        } else {
          await api.pveNode.createNetwork(selectedHostId.value, selectedNode.value, payload)
          toast.success(`Interface ${form.value.iface} staged for creation`)
        }
        showModal.value = false
        await fetchInterfaces()
      } catch {
        toast.error(editingIface.value ? 'Failed to update interface' : 'Failed to create interface')
      } finally {
        saving.value = false
      }
    }

    const buildPayload = () => {
      const f = form.value
      const p = {
        iface: f.iface,
        type: f.type,
        autostart: f.autostart ? 1 : 0,
      }
      if (f.cidr) p.cidr = f.cidr
      if (f.gateway) p.gateway = f.gateway
      if (f.comments) p.comments = f.comments

      if (f.type === 'bridge' || f.type === 'OVSBridge') {
        if (f.bridge_ports) p['bridge_ports'] = f.bridge_ports
        if (f.type === 'bridge') {
          p['bridge_stp'] = f.bridge_stp ? 'on' : 'off'
          if (f.bridge_fd !== '' && f.bridge_fd !== null) p['bridge_fd'] = f.bridge_fd
          p['bridge_vlan_aware'] = f.bridge_vlan_aware ? 1 : 0
        }
      }
      if (f.type === 'bond' || f.type === 'OVSBond') {
        if (f.slaves) p.slaves = f.slaves
        if (f.bond_mode) p.bond_mode = f.bond_mode
      }
      if (f.type === 'vlan') {
        if (f.vlan_raw_device) p['vlan-raw-device'] = f.vlan_raw_device
        if (f.vlan_id) p['vlan-id'] = f.vlan_id
      }
      return p
    }

    // ── Delete ───────────────────────────────────────────────────────────────
    const confirmDelete = async (iface) => {
      if (!confirm(`Delete interface "${iface.iface}"? This stages the deletion — apply config to finalize.`)) return
      try {
        await api.pveNode.deleteNetwork(selectedHostId.value, selectedNode.value, iface.iface)
        toast.success(`Interface ${iface.iface} staged for deletion`)
        await fetchInterfaces()
      } catch {
        toast.error(`Failed to delete interface ${iface.iface}`)
      }
    }

    // ── Apply / Revert ───────────────────────────────────────────────────────
    const applyConfig = () => {
      showApplyWarning.value = true
    }

    const doApplyConfig = async () => {
      savingApply.value = true
      try {
        await api.pveNode.applyNetwork(selectedHostId.value, selectedNode.value)
        toast.success('Network configuration applied — node is reloading network')
        showApplyWarning.value = false
        await fetchInterfaces()
      } catch {
        toast.error('Failed to apply network configuration')
      } finally {
        savingApply.value = false
      }
    }

    const revertConfig = async () => {
      if (!confirm('Revert all pending (unapplied) network configuration changes? This cannot be undone.')) return
      savingRevert.value = true
      try {
        await api.pveNode.revertNetwork(selectedHostId.value, selectedNode.value)
        toast.success('Pending changes reverted')
        await fetchInterfaces()
      } catch {
        toast.error('Failed to revert network changes')
      } finally {
        savingRevert.value = false
      }
    }

    // ── Quick create bridge ──────────────────────────────────────────────────
    const createQuickBridge = async () => {
      if (quickBridge.value.num == null) return
      savingQuickBridge.value = true
      try {
        const f = quickBridge.value
        const bridgeName = `vmbr${f.num}`
        const payload = {
          iface: bridgeName,
          type: 'bridge',
          autostart: 1,
          bridge_stp: f.stp ? 'on' : 'off',
          bridge_fd: 0,
          bridge_vlan_aware: f.vlanAware ? 1 : 0,
        }
        if (f.ports) payload['bridge_ports'] = f.ports
        if (f.cidr) payload.cidr = f.cidr
        if (f.gateway) payload.gateway = f.gateway
        if (f.comment) payload.comments = f.comment
        await api.pveNode.createNetwork(selectedHostId.value, selectedNode.value, payload)
        toast.success(`Bridge ${bridgeName} staged — click "Apply Config" to activate`)
        quickBridge.value = freshQuickBridge()
        await fetchInterfaces()
        activeNetTab.value = 'bridges'
      } catch {
        toast.error('Failed to create bridge')
      } finally {
        savingQuickBridge.value = false
      }
    }

    // ── Quick create VLAN ────────────────────────────────────────────────────
    const createQuickVlan = async () => {
      if (!quickVlan.value.rawDevice || !quickVlan.value.tag) return
      savingQuickVlan.value = true
      try {
        const f = quickVlan.value
        const ifaceName = `${f.rawDevice}.${f.tag}`
        const payload = {
          iface: ifaceName,
          type: 'vlan',
          autostart: f.autostart ? 1 : 0,
          'vlan-raw-device': f.rawDevice,
          'vlan-id': f.tag,
        }
        if (f.cidr) payload.cidr = f.cidr
        if (f.gateway) payload.gateway = f.gateway
        if (f.comment) payload.comments = f.comment
        await api.pveNode.createNetwork(selectedHostId.value, selectedNode.value, payload)
        toast.success(`VLAN interface ${ifaceName} staged — click "Apply Config" to activate`)
        quickVlan.value = freshQuickVlan()
        await fetchInterfaces()
      } catch {
        toast.error('Failed to create VLAN interface')
      } finally {
        savingQuickVlan.value = false
      }
    }

    // ── Bridge VLAN-aware toggle ─────────────────────────────────────────────
    const toggleBridgeVlanAware = async (br) => {
      togglingBridge.value = br.iface
      try {
        const currentVal = br['bridge_vlan_aware'] || br.bridge_vlan_aware
        const newVal = currentVal ? 0 : 1
        await api.pveNode.updateNetwork(selectedHostId.value, selectedNode.value, br.iface, {
          bridge_vlan_aware: newVal,
        })
        toast.success(`${br.iface} VLAN-aware ${newVal ? 'enabled' : 'disabled'} (staged)`)
        await fetchInterfaces()
      } catch {
        toast.error(`Failed to toggle VLAN-aware on ${br.iface}`)
      } finally {
        togglingBridge.value = null
      }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────
    const extractVlanTag = (ifaceName) => {
      if (!ifaceName) return '—'
      const parts = ifaceName.split('.')
      return parts.length >= 2 ? parts[parts.length - 1] : '—'
    }

    const getTypeBadge = (type) => {
      const map = {
        bridge: 'badge-info',
        bond: 'badge-warning',
        eth: 'badge-secondary',
        vlan: 'badge-primary',
        OVSBridge: 'badge-info',
        OVSBond: 'badge-warning',
        OVSPort: 'badge-secondary',
        OVSIntPort: 'badge-secondary',
      }
      return map[type] || 'badge-secondary'
    }

    const cidrFromNetmask = (netmask) => {
      if (!netmask) return ''
      return netmask.split('.').reduce((acc, octet) => {
        return acc + (parseInt(octet) >>> 0).toString(2).split('1').length - 1
      }, 0)
    }

    const cidrToNetmask = (prefix) => {
      const mask = []
      for (let i = 0; i < 4; i++) {
        const bits = Math.min(prefix, 8)
        mask.push(256 - Math.pow(2, 8 - bits))
        prefix -= bits
      }
      return mask.join('.')
    }

    onMounted(() => {
      fetchHosts()
    })

    return {
      hosts, nodes, selectedHostId, selectedNode,
      loadingHosts, loadingNodes,
      interfaces, loading,
      activeNetTab,
      saving, savingApply, savingRevert,
      pendingCount, pendingInterfaces,
      bridgeInterfaces, vlanInterfaces,
      showModal, showApplyWarning,
      editingIface, form,
      quickBridge, savingQuickBridge,
      quickVlan, savingQuickVlan,
      togglingBridge,
      copied,
      highlightedConfig,
      onHostChange, onNodeChange,
      fetchInterfaces,
      openCreateModal, openEditModal, submitModal,
      confirmDelete,
      applyConfig, doApplyConfig, revertConfig,
      createQuickBridge, createQuickVlan,
      toggleBridgeVlanAware,
      getTypeBadge, cidrFromNetmask,
      extractVlanTag, copyConfig,
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Selector bar */
.selector-bar { padding: 1rem 1.25rem; }
.selector-inner { display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap; }
.selector-group { display: flex; align-items: center; gap: 0.75rem; }
.selector-group select { min-width: 220px; }
.selector-actions { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-left: auto; }

.pending-badge {
  font-size: 0.8rem;
  padding: 0.3rem 0.75rem;
}

/* Workflow banner */
.workflow-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 1.25rem;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.35);
  border-radius: 0.5rem;
  flex-wrap: wrap;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.workflow-step.done { color: var(--text-secondary); text-decoration: line-through; }
.workflow-step.active { color: #b45309; font-weight: 600; }

.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4rem;
  height: 1.4rem;
  border-radius: 50%;
  background: var(--bg-secondary, #e2e8f0);
  font-size: 0.75rem;
  font-weight: 700;
}

.workflow-step.active .step-num {
  background: #fef3c7;
  color: #92400e;
}

.workflow-arrow { color: var(--text-secondary); font-size: 0.9rem; }

.workflow-info {
  margin-left: auto;
  font-size: 0.85rem;
  color: var(--text-primary);
}

/* Workflow mini (in apply modal) */
.workflow-mini {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.82rem;
}

.workflow-step-mini {
  padding: 0.2rem 0.6rem;
  border-radius: 0.25rem;
  background: var(--bg-secondary, #e2e8f0);
  color: var(--text-secondary);
}

.workflow-step-mini.active { background: #dcfce7; color: #166534; }
.workflow-step-mini.current { background: #fef3c7; color: #92400e; font-weight: 700; }

/* Tabs */
.tab-bar {
  display: flex;
  gap: 0.25rem;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 1.25rem;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  border-radius: 0.25rem 0.25rem 0 0;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover { color: var(--text-primary); }
.tab-btn.active {
  color: var(--color-primary, #3b82f6);
  border-bottom-color: var(--color-primary, #3b82f6);
  font-weight: 600;
}

.tab-count {
  font-size: 0.72rem;
  background: var(--bg-secondary, #e2e8f0);
  color: var(--text-secondary);
  border-radius: 9999px;
  padding: 0.1rem 0.45rem;
  font-weight: 600;
}

/* Card header */
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.card-header h3 { margin: 0; }

.header-title-group {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

/* Table */
.action-btns { display: flex; gap: 0.4rem; flex-wrap: wrap; }

/* Interface name cell */
.iface-name-cell {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.pending-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
  flex-shrink: 0;
}

.row-pending {
  background: rgba(251, 191, 36, 0.04);
}

.vlan-tag-chip {
  background: #ede9fe;
  color: #5b21b6;
  border-radius: 0.25rem;
  padding: 0.1rem 0.45rem;
  font-size: 0.8rem;
  font-weight: 600;
  font-family: monospace;
}

/* Quick form */
.quick-form {
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-row-quick {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  align-items: end;
}

.flex-end {
  display: flex;
  justify-content: flex-end;
  align-items: flex-end;
}

/* Input prefix group */
.input-prefix-group {
  display: flex;
  align-items: stretch;
}

.input-prefix {
  display: flex;
  align-items: center;
  padding: 0.4rem 0.75rem;
  background: var(--bg-secondary, #f1f5f9);
  border: 1px solid var(--border-color);
  border-right: none;
  border-radius: 0.375rem 0 0 0.375rem;
  font-size: 0.9rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.input-prefix-group .form-control {
  border-radius: 0 0.375rem 0.375rem 0;
  min-width: 60px;
}

/* Config preview */
.config-preview-wrap {
  display: flex;
  flex-direction: column;
}

.config-toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.6rem 1.25rem;
  background: var(--bg-secondary, #f8f9fa);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.82rem;
  flex-wrap: wrap;
}

.config-toolbar-label {
  color: var(--text-secondary);
}

.copy-btn {
  margin-left: auto;
}

.config-preview {
  margin: 0;
  padding: 1.25rem 1.5rem;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.82rem;
  line-height: 1.6;
  background: var(--bg-secondary, #1e1e2e);
  color: var(--text-primary, #cdd6f4);
  overflow-x: auto;
  white-space: pre;
  border-radius: 0 0 0.5rem 0.5rem;
  min-height: 300px;
}

/* Syntax highlight classes — work in both light and dark themes */
:deep(.cfg-comment) { color: #6c7086; font-style: italic; }
:deep(.cfg-kw)      { color: #89b4fa; font-weight: 600; }
:deep(.cfg-iface)   { color: #a6e3a1; font-weight: 600; }
:deep(.cfg-proto)   { color: #cba6f7; }
:deep(.cfg-method)  { color: #f38ba8; }
:deep(.cfg-dir)     { color: #f9e2af; }
:deep(.cfg-val)     { color: #cdd6f4; }

/* Pending changes list */
.pending-changes-list {
  padding: 1rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.pending-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.pending-actions {
  display: flex;
  gap: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-color);
  margin-top: 0.25rem;
}

/* Form */
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 0;
}

.form-actions { display: flex; gap: 0.75rem; }
.flex-center { display: flex; flex-direction: column; justify-content: center; }

.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  margin-top: 0.25rem;
}

.mt-1 { margin-top: 0.75rem; }
.mt-2 { margin-top: 1rem; }
.mt-3 { margin-top: 1.5rem; }
.mb-2 { margin-bottom: 1rem; }
.mb-3 { margin-bottom: 1.5rem; }
.ml-1 { margin-left: 0.5rem; }
.mono { font-family: monospace; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-danger { color: var(--color-danger, #ef4444); }

/* Alert */
.alert { padding: 0.875rem 1rem; border-radius: 0.375rem; font-size: 0.9rem; }
.alert-warning { background: rgba(251, 191, 36, 0.12); border: 1px solid rgba(251, 191, 36, 0.4); color: var(--text-primary); }

/* Help text */
.help-text-sm { font-size: 0.78rem; color: var(--text-secondary); margin-top: 0.3rem; }
.help-text-sm code {
  background: var(--bg-secondary, #f1f5f9);
  padding: 0.1rem 0.3rem;
  border-radius: 0.2rem;
  font-family: monospace;
}

/* Modal */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card, white);
  border-radius: 0.5rem;
  max-width: 540px;
  width: 95%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg, 0 20px 60px rgba(0,0,0,0.3));
}

.modal-content.modal-lg { max-width: 680px; }

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  background: var(--bg-card, white);
  z-index: 1;
}

.modal-header h3 { margin: 0; }

.btn-close {
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body { padding: 1.5rem; }

.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.875rem; }
.gap-1 { gap: 0.5rem; }
.flex { display: flex; }

@media (max-width: 1100px) {
  .form-row-quick { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 900px) {
  .selector-inner { flex-direction: column; align-items: flex-start; }
  .selector-actions { margin-left: 0; width: 100%; }
  .form-row { grid-template-columns: 1fr; }
  .form-row-quick { grid-template-columns: 1fr; }
  .workflow-banner { flex-direction: column; align-items: flex-start; }
  .workflow-info { margin-left: 0; }
}
</style>
