<template>
  <div class="sdn-page">
    <!-- Page header -->
    <div class="page-header mb-3">
      <div class="header-left">
        <h2>SDN / VNets</h2>
        <p class="text-muted">Manage Proxmox Software-Defined Networking — zones, VNets, and subnets</p>
      </div>
      <div class="header-right">
        <span v-if="pendingCount > 0" class="pending-badge badge badge-warning">
          {{ pendingCount }} pending change{{ pendingCount !== 1 ? 's' : '' }}
        </span>
        <button
          v-if="selectedHostId"
          class="btn"
          :class="pendingCount > 0 ? 'btn-warning' : 'btn-outline'"
          @click="applyChanges"
          :disabled="applying"
          title="Push all staged SDN changes to the cluster"
        >
          <span v-if="applying">Applying...</span>
          <span v-else-if="pendingCount > 0">Apply SDN Changes</span>
          <span v-else>Apply SDN Changes</span>
        </button>
      </div>
    </div>

    <!-- Host selector -->
    <div class="selector-bar card mb-3">
      <div class="selector-inner">
        <div class="selector-group">
          <label class="form-label mb-0">Proxmox Host</label>
          <select v-model="selectedHostId" class="form-control" @change="onHostChange" :disabled="loadingHosts">
            <option value="">{{ loadingHosts ? 'Loading...' : '— Select Host —' }}</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
          </select>
        </div>
        <div v-if="selectedHostId" class="selector-actions">
          <button class="btn btn-outline" @click="refreshAll" :disabled="loading" title="Refresh all SDN data">&#8635; Refresh</button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-spinner"></div>

    <!-- No host selected -->
    <div v-else-if="!selectedHostId" class="card text-center text-muted" style="padding: 3rem;">
      <p>Select a Proxmox host to manage its SDN configuration.</p>
    </div>

    <!-- Tabs -->
    <div v-else>
      <div class="tab-bar mb-3">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="['tab-btn', { active: activeTab === tab.id }]"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
          <span v-if="tab.id === 'zones' && zones.length" class="tab-count">{{ zones.length }}</span>
          <span v-if="tab.id === 'vnets' && vnets.length" class="tab-count">{{ vnets.length }}</span>
          <span v-if="tab.id === 'subnets' && subnets.length" class="tab-count">{{ subnets.length }}</span>
        </button>
      </div>

      <!-- ══ ZONES TAB ════════════════════════════════════════════════════════ -->
      <div v-if="activeTab === 'zones'">
        <div class="card">
          <div class="card-header">
            <div class="header-left">
              <h3>SDN Zones</h3>
              <div class="zone-type-legend">
                <span class="badge badge-secondary">simple</span> local L2 &nbsp;
                <span class="badge badge-info">vlan</span> 802.1q &nbsp;
                <span class="badge badge-warning">qinq</span> stacked VLANs &nbsp;
                <span class="badge badge-primary">vxlan</span> L2/L3 overlay &nbsp;
                <span class="badge badge-danger">evpn</span> BGP control plane
              </div>
            </div>
            <button class="btn btn-primary" @click="openCreateZoneModal">+ Create Zone</button>
          </div>

          <div v-if="zones.length === 0" class="text-center text-muted" style="padding: 2rem;">
            No SDN zones found. Create one to get started.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Zone ID</th>
                  <th>Type</th>
                  <th>MTU</th>
                  <th>Nodes</th>
                  <th>DHCP / Peers</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="z in zones" :key="z.zone">
                  <td><strong>{{ z.zone }}</strong></td>
                  <td>
                    <span :class="['badge', getZoneTypeBadge(z.type)]">{{ z.type }}</span>
                  </td>
                  <td>{{ z.mtu || '—' }}</td>
                  <td class="text-sm">{{ z.nodes || 'all' }}</td>
                  <td class="text-sm">
                    <span v-if="z.dhcp">DHCP enabled</span>
                    <span v-else-if="z.peers">{{ z.peers }}</span>
                    <span v-else-if="z.vrf_vxlan">VRF {{ z.vrf_vxlan }}</span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>
                    <span :class="['badge', z.state === 'ok' ? 'badge-success' : 'badge-warning']">
                      {{ z.state || 'pending' }}
                    </span>
                  </td>
                  <td>
                    <div class="action-btns">
                      <button @click="openEditZoneModal(z)" class="btn btn-outline btn-sm">Edit</button>
                      <button @click="confirmDeleteZone(z)" class="btn btn-danger btn-sm">Delete</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══ VNETS TAB ════════════════════════════════════════════════════════ -->
      <div v-if="activeTab === 'vnets'">
        <div class="card">
          <div class="card-header">
            <h3>VNets</h3>
            <button class="btn btn-primary" @click="openCreateVnetModal">+ Create VNet</button>
          </div>

          <div v-if="vnets.length === 0" class="text-center text-muted" style="padding: 2rem;">
            No VNets found. Create one and assign it to a zone.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>VNet ID</th>
                  <th>Alias</th>
                  <th>Zone</th>
                  <th>Tag / VLAN</th>
                  <th>Subnets</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="v in vnets" :key="v.vnet">
                  <tr :class="{ 'row-expanded': expandedVnet === v.vnet }">
                    <td>
                      <button class="expand-btn" @click="toggleVnetExpand(v.vnet)" :title="expandedVnet === v.vnet ? 'Collapse subnets' : 'Expand subnets'">
                        <span class="expand-icon">{{ expandedVnet === v.vnet ? '▾' : '▸' }}</span>
                      </button>
                      <strong>{{ v.vnet }}</strong>
                    </td>
                    <td>{{ v.alias || '—' }}</td>
                    <td>
                      <span v-if="v.zone" class="zone-ref">{{ v.zone }}</span>
                      <span v-else class="text-muted">—</span>
                    </td>
                    <td>{{ v.tag != null ? v.tag : '—' }}</td>
                    <td>
                      <span class="text-sm">{{ subnetCountFor(v.vnet) }}</span>
                    </td>
                    <td>
                      <span :class="['badge', v.state === 'ok' ? 'badge-success' : 'badge-warning']">
                        {{ v.state || 'pending' }}
                      </span>
                    </td>
                    <td>
                      <div class="action-btns">
                        <button @click="openEditVnetModal(v)" class="btn btn-outline btn-sm">Edit</button>
                        <button @click="openAddSubnetModal(v)" class="btn btn-outline btn-sm">+ Subnet</button>
                        <button @click="confirmDeleteVnet(v)" class="btn btn-danger btn-sm">Delete</button>
                      </div>
                    </td>
                  </tr>
                  <!-- Expanded subnets row -->
                  <tr v-if="expandedVnet === v.vnet" class="subnet-expand-row">
                    <td colspan="7" class="subnet-expand-cell">
                      <div class="subnet-expand-inner">
                        <div v-if="subnetsForVnet(v.vnet).length === 0" class="text-muted text-sm" style="padding: 0.5rem 0;">
                          No subnets in this VNet.
                          <button class="btn btn-outline btn-sm ml-1" @click="openAddSubnetModal(v)">Add Subnet</button>
                        </div>
                        <table v-else class="table table-compact">
                          <thead>
                            <tr>
                              <th>CIDR</th>
                              <th>Gateway</th>
                              <th>SNAT</th>
                              <th>DHCP Range</th>
                              <th>DNS</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="s in subnetsForVnet(v.vnet)" :key="s.subnet">
                              <td><code>{{ s.subnet }}</code></td>
                              <td>{{ s.gateway || '—' }}</td>
                              <td>
                                <span :class="['badge', s.snat ? 'badge-success' : 'badge-secondary']">
                                  {{ s.snat ? 'Yes' : 'No' }}
                                </span>
                              </td>
                              <td class="text-sm">{{ s.dhcp_range || '—' }}</td>
                              <td class="text-sm">{{ s.dns_nameservers || '—' }}</td>
                              <td>
                                <button @click="confirmDeleteSubnet(s)" class="btn btn-danger btn-sm">Delete</button>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══ SUBNETS TAB ═══════════════════════════════════════════════════════ -->
      <div v-if="activeTab === 'subnets'">
        <div class="card">
          <div class="card-header">
            <h3>All Subnets</h3>
            <button class="btn btn-primary" @click="openCreateSubnetStandaloneModal">+ Create Subnet</button>
          </div>

          <div v-if="subnets.length === 0" class="text-center text-muted" style="padding: 2rem;">
            No subnets found. Create a VNet first, then add subnets.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>CIDR</th>
                  <th>Gateway</th>
                  <th>VNet</th>
                  <th>DHCP Range</th>
                  <th>DNS Nameserver</th>
                  <th>SNAT</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in subnets" :key="s.subnet + s.vnet">
                  <td><code>{{ s.subnet }}</code></td>
                  <td>{{ s.gateway || '—' }}</td>
                  <td>
                    <span class="zone-ref">{{ s.vnet || '—' }}</span>
                  </td>
                  <td class="text-sm">{{ s.dhcp_range || '—' }}</td>
                  <td class="text-sm">{{ s.dns_nameservers || '—' }}</td>
                  <td>
                    <span :class="['badge', s.snat ? 'badge-success' : 'badge-secondary']">
                      {{ s.snat ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td>
                    <button @click="confirmDeleteSubnet(s)" class="btn btn-danger btn-sm">Delete</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══ DIAGRAM TAB ══════════════════════════════════════════════════════ -->
      <div v-if="activeTab === 'diagram'">
        <div class="card">
          <div class="card-header">
            <h3>SDN Topology Diagram</h3>
            <span class="text-muted text-sm">Visual overview of zones, VNets, and subnets</span>
          </div>
          <div class="diagram-panel">
            <div v-if="zones.length === 0" class="text-center text-muted" style="padding: 3rem;">
              No SDN configuration to display.
            </div>
            <div v-else class="diagram-grid">
              <div v-for="z in zones" :key="z.zone" class="zone-box">
                <div class="zone-header">
                  <span :class="['zone-type-badge', z.type]">{{ z.type }}</span>
                  <strong>{{ z.zone }}</strong>
                  <span v-if="z.mtu" class="zone-mtu">MTU {{ z.mtu }}</span>
                  <span v-if="z.nodes" class="zone-nodes" :title="z.nodes">{{ z.nodes }}</span>
                  <span :class="['badge', z.state === 'ok' ? 'badge-success' : 'badge-warning']" style="margin-left: auto; font-size: 0.7rem;">
                    {{ z.state || 'pending' }}
                  </span>
                </div>
                <div class="zone-body">
                  <div v-if="vnetsForZone(z.zone).length === 0" class="no-vnets">No VNets</div>
                  <div v-for="v in vnetsForZone(z.zone)" :key="v.vnet" class="vnet-box">
                    <div class="vnet-header">
                      <span class="vnet-id">{{ v.vnet }}</span>
                      <span v-if="v.alias" class="vnet-alias">{{ v.alias }}</span>
                      <span v-if="v.tag != null" class="vnet-tag">tag: {{ v.tag }}</span>
                      <span :class="['badge', v.state === 'ok' ? 'badge-success' : 'badge-warning']" style="margin-left: auto; font-size: 0.65rem;">
                        {{ v.state || 'pending' }}
                      </span>
                    </div>
                    <div v-if="subnetsForVnet(v.vnet).length === 0" class="subnet-label text-muted" style="font-style: italic;">No subnets</div>
                    <div v-for="s in subnetsForVnet(v.vnet)" :key="s.subnet" class="subnet-label">
                      <span class="subnet-cidr">{{ s.subnet }}</span>
                      <span v-if="s.gateway" class="gw">gw: {{ s.gateway }}</span>
                      <span v-if="s.dhcp_range" class="dhcp-hint" :title="'DHCP: ' + s.dhcp_range">DHCP</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════════
         MODALS
    ══════════════════════════════════════════════════════════════════════════ -->

    <!-- Create / Edit Zone Modal -->
    <div v-if="showZoneModal" class="modal" @click.self="showZoneModal = false">
      <div class="modal-content modal-lg" @click.stop>
        <div class="modal-header">
          <h3>{{ editingZone ? 'Edit Zone' : 'Create SDN Zone' }}</h3>
          <button @click="showZoneModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitZoneModal" class="modal-body">

          <!-- Type selector with radio cards -->
          <div v-if="!editingZone" class="form-group">
            <label class="form-label">Zone Type <span class="text-danger">*</span></label>
            <div class="zone-type-cards">
              <label
                v-for="zt in zoneTypes"
                :key="zt.value"
                :class="['zone-type-card', { selected: zoneForm.type === zt.value }]"
              >
                <input type="radio" v-model="zoneForm.type" :value="zt.value" class="sr-only" />
                <span :class="['ztc-badge', zt.value]">{{ zt.value }}</span>
                <span class="ztc-label">{{ zt.label }}</span>
                <span class="ztc-desc">{{ zt.desc }}</span>
              </label>
            </div>
          </div>
          <div v-else class="form-group">
            <label class="form-label">Zone Type</label>
            <div class="form-control-static">
              <span :class="['badge', getZoneTypeBadge(zoneForm.type)]">{{ zoneForm.type }}</span>
              <span class="text-muted text-sm ml-1">(cannot change type after creation)</span>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Zone ID <span class="text-danger">*</span></label>
              <input
                v-model="zoneForm.zone"
                class="form-control"
                placeholder="e.g. myzone"
                :disabled="!!editingZone"
                pattern="[a-zA-Z0-9\-]+"
                title="Alphanumeric and hyphens only"
                required
              />
              <div class="help-text-sm">Lowercase alphanumeric, hyphens allowed. Max 8 chars recommended.</div>
            </div>
            <div class="form-group">
              <label class="form-label">MTU</label>
              <input v-model.number="zoneForm.mtu" type="number" class="form-control" placeholder="1500" min="576" max="9000" />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Nodes</label>
            <div class="nodes-multiselect" v-if="availableNodes.length > 0">
              <label
                v-for="n in availableNodes"
                :key="n"
                class="node-checkbox-label"
              >
                <input type="checkbox" :value="n" v-model="zoneForm.selectedNodes" />
                <span>{{ n }}</span>
              </label>
              <div class="help-text-sm">Leave all unchecked to apply to all nodes.</div>
            </div>
            <div v-else>
              <input v-model="zoneForm.nodes" class="form-control" placeholder="e.g. pve1,pve2 (blank = all)" />
              <div class="help-text-sm">Comma-separated node names. Leave blank to apply to all nodes.</div>
            </div>
          </div>

          <!-- Simple / VLAN / QinQ: bridge -->
          <div class="form-group" v-if="['simple','vlan','qinq'].includes(zoneForm.type)">
            <label class="form-label">Bridge Interface</label>
            <input v-model="zoneForm.bridge" class="form-control" placeholder="e.g. vmbr0" />
            <div class="help-text-sm">Physical bridge interface to use for this zone.</div>
          </div>

          <!-- VXLAN: peers -->
          <div class="form-group" v-if="zoneForm.type === 'vxlan'">
            <label class="form-label">Peer Node IPs (comma-separated)</label>
            <input v-model="zoneForm.peers" class="form-control" placeholder="e.g. 10.0.0.1,10.0.0.2" />
            <div class="help-text-sm">Remote VTEP IPs for unicast VXLAN. Required for multicast-free mode.</div>
          </div>

          <!-- EVPN specific -->
          <div v-if="zoneForm.type === 'evpn'">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">VRF VXLAN ID</label>
                <input v-model.number="zoneForm.vrf_vxlan" type="number" class="form-control" placeholder="e.g. 10000" />
              </div>
              <div class="form-group">
                <label class="form-label">Controller</label>
                <input v-model="zoneForm.controller" class="form-control" placeholder="e.g. mycontroller" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Exit Nodes (comma-separated)</label>
                <input v-model="zoneForm.exitnodes" class="form-control" placeholder="e.g. pve1,pve2" />
              </div>
              <div class="form-group">
                <label class="form-label">Peer Node IPs</label>
                <input v-model="zoneForm.peers" class="form-control" placeholder="e.g. 10.0.0.1,10.0.0.2" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">RT Import</label>
                <input v-model="zoneForm.rt_import" class="form-control" placeholder="e.g. 65000:1" />
              </div>
              <div class="form-group">
                <label class="form-label">RT Export</label>
                <input v-model="zoneForm.rt_export" class="form-control" placeholder="e.g. 65000:1" />
              </div>
            </div>
          </div>

          <!-- Type help block -->
          <div class="type-help-block" v-if="zoneForm.type">
            <div class="type-help-icon">ℹ</div>
            <div>
              <span v-if="zoneForm.type === 'simple'"><strong>Simple:</strong> Basic L2 isolation using a local Linux bridge. Best for single-node setups or simple guest isolation.</span>
              <span v-else-if="zoneForm.type === 'vlan'"><strong>VLAN:</strong> IEEE 802.1q VLAN tagging on a shared physical bridge. Each VNet gets its own VLAN tag. Requires a VLAN-aware bridge.</span>
              <span v-else-if="zoneForm.type === 'qinq'"><strong>QinQ:</strong> Stacked VLANs (802.1ad) for provider/customer separation. Useful for multi-tenant environments.</span>
              <span v-else-if="zoneForm.type === 'vxlan'"><strong>VXLAN:</strong> Layer 2 overlay over Layer 3 tunnels. Enables multi-site/multi-node networks. Requires peer IPs for unicast mode.</span>
              <span v-else-if="zoneForm.type === 'evpn'"><strong>EVPN:</strong> BGP-based control plane for VXLAN overlays with distributed routing. Best for large multi-node clusters with exit nodes.</span>
            </div>
          </div>

          <div class="form-actions mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingZone">
              {{ savingZone ? 'Saving...' : (editingZone ? 'Update Zone' : 'Create Zone') }}
            </button>
            <button type="button" @click="showZoneModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create / Edit VNet Modal -->
    <div v-if="showVnetModal" class="modal" @click.self="showVnetModal = false">
      <div class="modal-content modal-lg" @click.stop>
        <div class="modal-header">
          <h3>{{ editingVnet ? 'Edit VNet' : 'Create VNet' }}</h3>
          <button @click="showVnetModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitVnetModal" class="modal-body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">VNet ID <span class="text-danger">*</span></label>
              <input
                v-model="vnetForm.vnet"
                class="form-control"
                placeholder="e.g. myvnet"
                :disabled="!!editingVnet"
                pattern="[a-zA-Z0-9\-]+"
                title="Alphanumeric and hyphens only"
                required
              />
            </div>
            <div class="form-group">
              <label class="form-label">Zone <span class="text-danger">*</span></label>
              <select v-model="vnetForm.zone" class="form-control" :disabled="!!editingVnet" required>
                <option value="">— Select Zone —</option>
                <option v-for="z in zones" :key="z.zone" :value="z.zone">{{ z.zone }} ({{ z.type }})</option>
              </select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Alias (display name)</label>
              <input v-model="vnetForm.alias" class="form-control" placeholder="Optional friendly name" />
            </div>
            <div class="form-group">
              <label class="form-label">Tag (VLAN / VXLAN ID)</label>
              <input v-model.number="vnetForm.tag" type="number" class="form-control" placeholder="e.g. 100" min="1" max="16777215" />
              <div class="help-text-sm">For VLAN zones: VLAN ID (1–4094). For VXLAN/EVPN: VNI (1–16777215).</div>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="vnetForm.comment" class="form-control" placeholder="Optional description" />
          </div>

          <!-- Subnet (optional at creation time) -->
          <div v-if="!editingVnet" class="form-group">
            <label class="form-label toggle-label">
              <input type="checkbox" v-model="vnetForm.addSubnet" />
              <span>Add a subnet now</span>
            </label>
          </div>
          <div v-if="!editingVnet && vnetForm.addSubnet" class="subnet-inline-form">
            <h4 class="subnet-inline-title">Subnet Details</h4>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">CIDR <span class="text-danger">*</span></label>
                <input v-model="vnetForm.subnetCidr" class="form-control" placeholder="e.g. 10.0.0.0/24" />
              </div>
              <div class="form-group">
                <label class="form-label">Gateway</label>
                <input v-model="vnetForm.subnetGw" class="form-control" placeholder="e.g. 10.0.0.1" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">DHCP Range</label>
                <input v-model="vnetForm.subnetDhcpRange" class="form-control" placeholder="e.g. 10.0.0.100-10.0.0.200" />
              </div>
              <div class="form-group">
                <label class="form-label">DNS Nameserver</label>
                <input v-model="vnetForm.subnetDns" class="form-control" placeholder="e.g. 8.8.8.8" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label toggle-label">
                <input type="checkbox" v-model="vnetForm.subnetSnat" />
                <span>Enable SNAT (masquerade outbound traffic)</span>
              </label>
            </div>
          </div>

          <div class="form-actions mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingVnet">
              {{ savingVnet ? 'Saving...' : (editingVnet ? 'Update VNet' : 'Create VNet') }}
            </button>
            <button type="button" @click="showVnetModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Add Subnet Modal -->
    <div v-if="showSubnetModal" class="modal" @click.self="showSubnetModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ subnetTargetVnet ? `Add Subnet to ${subnetTargetVnet}` : 'Create Subnet' }}</h3>
          <button @click="showSubnetModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitSubnetModal" class="modal-body">
          <div v-if="!subnetTargetVnet" class="form-group">
            <label class="form-label">VNet <span class="text-danger">*</span></label>
            <select v-model="subnetForm.vnet" class="form-control" required>
              <option value="">— Select VNet —</option>
              <option v-for="v in vnets" :key="v.vnet" :value="v.vnet">{{ v.vnet }}{{ v.alias ? ` — ${v.alias}` : '' }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">CIDR <span class="text-danger">*</span></label>
            <input v-model="subnetForm.subnet" class="form-control" placeholder="e.g. 10.0.0.0/24" required />
            <div class="help-text-sm">Network address in CIDR notation, e.g. 10.0.0.0/24</div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Gateway</label>
              <input v-model="subnetForm.gateway" class="form-control" placeholder="e.g. 10.0.0.1" />
            </div>
            <div class="form-group">
              <label class="form-label">DNS Nameserver</label>
              <input v-model="subnetForm.dns_nameservers" class="form-control" placeholder="e.g. 8.8.8.8" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">DHCP Range</label>
            <input v-model="subnetForm.dhcp_range" class="form-control" placeholder="e.g. 10.0.0.100-10.0.0.200" />
            <div class="help-text-sm">Start and end IP separated by dash. Used by Proxmox DHCP plugin.</div>
          </div>
          <div class="form-group">
            <label class="form-label toggle-label">
              <input type="checkbox" v-model="subnetForm.snat" />
              <span>Enable SNAT (masquerade outbound traffic)</span>
            </label>
          </div>
          <div class="form-actions mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingSubnet">
              {{ savingSubnet ? 'Adding...' : 'Add Subnet' }}
            </button>
            <button type="button" @click="showSubnetModal = false" class="btn btn-outline">Cancel</button>
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

export default {
  name: 'SDNManagement',
  setup() {
    const toast = useToast()

    // Host selection
    const hosts = ref([])
    const selectedHostId = ref('')
    const loadingHosts = ref(false)
    const availableNodes = ref([])

    // Data
    const zones = ref([])
    const vnets = ref([])
    const subnets = ref([])
    const loading = ref(false)
    const applying = ref(false)

    // Tabs
    const tabs = [
      { id: 'zones', label: 'Zones' },
      { id: 'vnets', label: 'VNets' },
      { id: 'subnets', label: 'Subnets' },
      { id: 'diagram', label: 'Topology' },
    ]
    const activeTab = ref('zones')

    // Expand state for VNets
    const expandedVnet = ref(null)

    // Zone type definitions
    const zoneTypes = [
      { value: 'simple', label: 'Simple', desc: 'Local VLAN / L2 isolation' },
      { value: 'vlan', label: 'VLAN', desc: 'IEEE 802.1q tagging' },
      { value: 'qinq', label: 'QinQ', desc: 'Stacked VLANs (802.1ad)' },
      { value: 'vxlan', label: 'VXLAN', desc: 'L2 overlay over L3 tunnels' },
      { value: 'evpn', label: 'EVPN', desc: 'BGP-based control plane' },
    ]

    // Pending change counter — tracks edits since last apply
    const pendingCount = computed(() => {
      const allObjs = [...zones.value, ...vnets.value, ...subnets.value]
      return allObjs.filter(o => o.state && o.state !== 'ok').length +
             allObjs.filter(o => !o.state).length
    })

    // Zone modal
    const showZoneModal = ref(false)
    const editingZone = ref(null)
    const savingZone = ref(false)
    const freshZoneForm = () => ({
      zone: '', type: 'simple', mtu: null, nodes: '', selectedNodes: [],
      bridge: '', peers: '', vrf_vxlan: null, controller: '',
      rt_import: '', rt_export: '', exitnodes: '',
    })
    const zoneForm = ref(freshZoneForm())

    // VNet modal
    const showVnetModal = ref(false)
    const editingVnet = ref(null)
    const savingVnet = ref(false)
    const freshVnetForm = () => ({
      vnet: '', zone: '', alias: '', tag: null, comment: '',
      addSubnet: false, subnetCidr: '', subnetGw: '', subnetSnat: false,
      subnetDhcpRange: '', subnetDns: '',
    })
    const vnetForm = ref(freshVnetForm())

    // Subnet modal
    const showSubnetModal = ref(false)
    const subnetTargetVnet = ref('')
    const savingSubnet = ref(false)
    const freshSubnetForm = () => ({
      subnet: '', vnet: '', gateway: '', snat: false, dhcp_range: '', dns_nameservers: '',
    })
    const subnetForm = ref(freshSubnetForm())

    // ── Load hosts ──────────────────────────────────────────────────────────
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
      zones.value = []
      vnets.value = []
      subnets.value = []
      expandedVnet.value = null
      availableNodes.value = []
      if (selectedHostId.value) {
        refreshAll()
        // Also load node list for the zone form multi-select
        try {
          const res = await api.proxmox.listNodes(selectedHostId.value)
          availableNodes.value = (res.data || []).map(n => n.node_name || n.node).filter(Boolean)
        } catch {
          // non-critical
        }
      }
    }

    // ── Data loading ─────────────────────────────────────────────────────────
    const refreshAll = async () => {
      loading.value = true
      try {
        const [zRes, vRes, sRes] = await Promise.allSettled([
          api.sdn.listZones(selectedHostId.value),
          api.sdn.listVnets(selectedHostId.value),
          api.sdn.listSubnets(selectedHostId.value),
        ])
        zones.value = zRes.status === 'fulfilled' ? (zRes.value.data || []) : []
        vnets.value = vRes.status === 'fulfilled' ? (vRes.value.data || []) : []
        subnets.value = sRes.status === 'fulfilled' ? (sRes.value.data || []) : []
      } catch {
        toast.error('Failed to load SDN data')
      } finally {
        loading.value = false
      }
    }

    // ── Apply changes ────────────────────────────────────────────────────────
    const applyChanges = async () => {
      if (!confirm('Apply all pending SDN changes to the cluster? This may briefly disrupt network connectivity.')) return
      applying.value = true
      try {
        await api.sdn.apply(selectedHostId.value)
        toast.success('SDN changes applied successfully')
        await refreshAll()
      } catch {
        toast.error('Failed to apply SDN changes')
      } finally {
        applying.value = false
      }
    }

    // ── Zone modal ───────────────────────────────────────────────────────────
    const openCreateZoneModal = () => {
      editingZone.value = null
      zoneForm.value = freshZoneForm()
      showZoneModal.value = true
    }

    const openEditZoneModal = (z) => {
      editingZone.value = z
      zoneForm.value = {
        zone: z.zone, type: z.type || 'simple',
        mtu: z.mtu || null, nodes: z.nodes || '',
        selectedNodes: z.nodes ? z.nodes.split(',').map(s => s.trim()) : [],
        bridge: z.bridge || '', peers: z.peers || '',
        vrf_vxlan: z.vrf_vxlan || null, controller: z.controller || '',
        rt_import: z.rt_import || '', rt_export: z.rt_export || '',
        exitnodes: z.exitnodes || '',
      }
      showZoneModal.value = true
    }

    const submitZoneModal = async () => {
      savingZone.value = true
      try {
        const payload = buildZonePayload()
        if (editingZone.value) {
          await api.sdn.updateZone(selectedHostId.value, zoneForm.value.zone, payload)
          toast.success(`Zone ${zoneForm.value.zone} updated`)
        } else {
          await api.sdn.createZone(selectedHostId.value, payload)
          toast.success(`Zone ${zoneForm.value.zone} created`)
        }
        showZoneModal.value = false
        await refreshAll()
      } catch {
        toast.error(editingZone.value ? 'Failed to update zone' : 'Failed to create zone')
      } finally {
        savingZone.value = false
      }
    }

    const buildZonePayload = () => {
      const f = zoneForm.value
      const p = { zone: f.zone, type: f.type }
      if (f.mtu) p.mtu = f.mtu
      // Prefer selectedNodes checkboxes if available, fall back to text
      if (f.selectedNodes && f.selectedNodes.length > 0) {
        p.nodes = f.selectedNodes.join(',')
      } else if (f.nodes) {
        p.nodes = f.nodes
      }
      if (f.bridge) p.bridge = f.bridge
      if (f.peers) p.peers = f.peers
      if (f.vrf_vxlan) p.vrf_vxlan = f.vrf_vxlan
      if (f.controller) p.controller = f.controller
      if (f.rt_import) p.rt_import = f.rt_import
      if (f.rt_export) p.rt_export = f.rt_export
      if (f.exitnodes) p.exitnodes = f.exitnodes
      return p
    }

    const confirmDeleteZone = async (z) => {
      if (!confirm(`Delete zone "${z.zone}"? All VNets in this zone must be deleted first.`)) return
      try {
        await api.sdn.deleteZone(selectedHostId.value, z.zone)
        toast.success(`Zone ${z.zone} deleted`)
        await refreshAll()
      } catch {
        toast.error(`Failed to delete zone ${z.zone}`)
      }
    }

    // ── VNet modal ───────────────────────────────────────────────────────────
    const openCreateVnetModal = () => {
      editingVnet.value = null
      vnetForm.value = freshVnetForm()
      showVnetModal.value = true
    }

    const openEditVnetModal = (v) => {
      editingVnet.value = v
      vnetForm.value = {
        vnet: v.vnet, zone: v.zone || '', alias: v.alias || '',
        tag: v.tag != null ? v.tag : null, comment: v.comment || '',
        addSubnet: false, subnetCidr: '', subnetGw: '', subnetSnat: false,
        subnetDhcpRange: '', subnetDns: '',
      }
      showVnetModal.value = true
    }

    const submitVnetModal = async () => {
      savingVnet.value = true
      try {
        const f = vnetForm.value
        if (editingVnet.value) {
          const updatePayload = {}
          if (f.alias !== undefined) updatePayload.alias = f.alias
          if (f.tag != null && f.tag !== '') updatePayload.tag = f.tag
          await api.sdn.updateVnet(selectedHostId.value, f.vnet, updatePayload)
          toast.success(`VNet ${f.vnet} updated`)
        } else {
          const payload = { vnet: f.vnet, zone: f.zone }
          if (f.alias) payload.alias = f.alias
          if (f.tag != null && f.tag !== '') payload.tag = f.tag
          await api.sdn.createVnet(selectedHostId.value, payload)
          toast.success(`VNet ${f.vnet} created`)
          if (f.addSubnet && f.subnetCidr) {
            const sPayload = { subnet: f.subnetCidr, vnet: f.vnet }
            if (f.subnetGw) sPayload.gateway = f.subnetGw
            if (f.subnetSnat) sPayload.snat = 1
            if (f.subnetDhcpRange) sPayload.dhcp_range = f.subnetDhcpRange
            if (f.subnetDns) sPayload.dns_nameservers = f.subnetDns
            await api.sdn.createSubnet(selectedHostId.value, sPayload)
            toast.success(`Subnet ${f.subnetCidr} added`)
          }
        }
        showVnetModal.value = false
        await refreshAll()
      } catch {
        toast.error(editingVnet.value ? 'Failed to update VNet' : 'Failed to create VNet')
      } finally {
        savingVnet.value = false
      }
    }

    const confirmDeleteVnet = async (v) => {
      if (!confirm(`Delete VNet "${v.vnet}"? This removes all its subnets too.`)) return
      try {
        await api.sdn.deleteVnet(selectedHostId.value, v.vnet)
        toast.success(`VNet ${v.vnet} deleted`)
        if (expandedVnet.value === v.vnet) expandedVnet.value = null
        await refreshAll()
      } catch {
        toast.error(`Failed to delete VNet ${v.vnet}`)
      }
    }

    // ── Subnet modal ─────────────────────────────────────────────────────────
    const openAddSubnetModal = (v) => {
      subnetTargetVnet.value = v.vnet
      subnetForm.value = { ...freshSubnetForm(), vnet: v.vnet }
      showSubnetModal.value = true
    }

    const openCreateSubnetStandaloneModal = () => {
      subnetTargetVnet.value = ''
      subnetForm.value = freshSubnetForm()
      showSubnetModal.value = true
    }

    const submitSubnetModal = async () => {
      savingSubnet.value = true
      try {
        const f = subnetForm.value
        const vnet = subnetTargetVnet.value || f.vnet
        if (!vnet) { toast.error('Please select a VNet'); return }
        const payload = { subnet: f.subnet, vnet }
        if (f.gateway) payload.gateway = f.gateway
        if (f.snat) payload.snat = 1
        if (f.dhcp_range) payload.dhcp_range = f.dhcp_range
        if (f.dns_nameservers) payload.dns_nameservers = f.dns_nameservers
        await api.sdn.createSubnet(selectedHostId.value, payload)
        toast.success(`Subnet ${f.subnet} added to ${vnet}`)
        showSubnetModal.value = false
        await refreshAll()
      } catch {
        toast.error('Failed to add subnet')
      } finally {
        savingSubnet.value = false
      }
    }

    const confirmDeleteSubnet = async (s) => {
      if (!confirm(`Delete subnet "${s.subnet}" from VNet "${s.vnet}"?`)) return
      try {
        await api.sdn.deleteSubnet(selectedHostId.value, s.subnet, s.vnet)
        toast.success(`Subnet ${s.subnet} deleted`)
        await refreshAll()
      } catch {
        toast.error(`Failed to delete subnet ${s.subnet}`)
      }
    }

    // ── Expand toggle ─────────────────────────────────────────────────────────
    const toggleVnetExpand = (vnetId) => {
      expandedVnet.value = expandedVnet.value === vnetId ? null : vnetId
    }

    // ── Helpers ──────────────────────────────────────────────────────────────
    const getZoneTypeBadge = (type) => {
      const map = {
        simple: 'badge-secondary',
        vlan: 'badge-info',
        qinq: 'badge-warning',
        vxlan: 'badge-primary',
        evpn: 'badge-danger',
      }
      return map[type] || 'badge-secondary'
    }

    const vnetsForZone = (zoneId) => vnets.value.filter(v => v.zone === zoneId)
    const subnetsForVnet = (vnetId) => subnets.value.filter(s => s.vnet === vnetId)
    const subnetCountFor = (vnetId) => {
      const count = subnets.value.filter(s => s.vnet === vnetId).length
      return count === 0 ? 'none' : `${count} subnet${count !== 1 ? 's' : ''}`
    }

    onMounted(() => {
      fetchHosts()
    })

    return {
      hosts, selectedHostId, loadingHosts, availableNodes,
      zones, vnets, subnets, loading, pendingCount, applying,
      tabs, activeTab, expandedVnet,
      zoneTypes,
      showZoneModal, editingZone, savingZone, zoneForm,
      showVnetModal, editingVnet, savingVnet, vnetForm,
      showSubnetModal, subnetTargetVnet, savingSubnet, subnetForm,
      onHostChange, refreshAll, applyChanges,
      openCreateZoneModal, openEditZoneModal, submitZoneModal, confirmDeleteZone,
      openCreateVnetModal, openEditVnetModal, submitVnetModal, confirmDeleteVnet,
      openAddSubnetModal, openCreateSubnetStandaloneModal, submitSubnetModal, confirmDeleteSubnet,
      toggleVnetExpand,
      getZoneTypeBadge, vnetsForZone, subnetsForVnet, subnetCountFor,
    }
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* Selector bar */
.selector-bar { padding: 1rem 1.25rem; }
.selector-inner { display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap; }
.selector-group { display: flex; align-items: center; gap: 0.75rem; }
.selector-group select { min-width: 220px; }
.selector-actions { display: flex; gap: 0.5rem; margin-left: auto; }

/* Pending badge */
.pending-badge {
  font-size: 0.8rem;
  padding: 0.35rem 0.8rem;
}

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
.tab-btn.active { color: var(--color-primary, #3b82f6); border-bottom-color: var(--color-primary, #3b82f6); font-weight: 600; }

.tab-count {
  font-size: 0.72rem;
  background: var(--bg-secondary, #e2e8f0);
  color: var(--text-secondary);
  border-radius: 9999px;
  padding: 0.1rem 0.45rem;
  font-weight: 600;
}

/* Card header with sub-legend */
.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.card-header .header-left {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.card-header h3 {
  margin: 0;
}

/* Legend */
.zone-type-legend {
  font-size: 0.78rem;
  color: var(--text-secondary);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
}

/* Table */
.action-btns { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.875rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-danger { color: var(--color-danger, #ef4444); }
.ml-1 { margin-left: 0.5rem; }

/* Zone reference chip */
.zone-ref {
  background: var(--bg-secondary, #f1f5f9);
  border: 1px solid var(--border-color);
  border-radius: 0.25rem;
  padding: 0.1rem 0.45rem;
  font-size: 0.8rem;
  font-family: monospace;
}

/* Expand row */
.expand-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0 0.25rem;
  color: var(--text-secondary);
  font-size: 0.9rem;
  vertical-align: middle;
}

.expand-icon {
  display: inline-block;
  transition: transform 0.15s;
}

.row-expanded {
  background: var(--bg-secondary, #f8fafc);
}

.subnet-expand-row td {
  padding: 0 !important;
  border-top: none !important;
}

.subnet-expand-cell {
  padding: 0 !important;
}

.subnet-expand-inner {
  padding: 0.75rem 2rem 0.75rem 3rem;
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary, #f8fafc);
}

.table-compact td, .table-compact th {
  padding: 0.4rem 0.75rem;
  font-size: 0.85rem;
}

/* Zone type cards */
.zone-type-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.6rem;
  margin-top: 0.25rem;
}

.zone-type-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
  padding: 0.75rem 0.5rem;
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  text-align: center;
}

.zone-type-card:hover {
  border-color: var(--color-primary, #3b82f6);
  background: var(--bg-secondary, #f8fafc);
}

.zone-type-card.selected {
  border-color: var(--color-primary, #3b82f6);
  background: rgba(59, 130, 246, 0.06);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0,0,0,0);
}

.ztc-badge {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
}
.ztc-badge.simple { background: #e2e8f0; color: #475569; }
.ztc-badge.vlan   { background: #dbeafe; color: #1d4ed8; }
.ztc-badge.qinq   { background: #fef3c7; color: #92400e; }
.ztc-badge.vxlan  { background: #ede9fe; color: #5b21b6; }
.ztc-badge.evpn   { background: #fee2e2; color: #991b1b; }

.ztc-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.ztc-desc {
  font-size: 0.72rem;
  color: var(--text-secondary);
  line-height: 1.3;
}

/* Nodes multi-select */
.nodes-multiselect {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.25rem;
}

.node-checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s, border-color 0.15s;
}

.node-checkbox-label:hover {
  background: var(--bg-secondary, #f1f5f9);
  border-color: var(--color-primary, #3b82f6);
}

.node-checkbox-label input:checked + span {
  color: var(--color-primary, #3b82f6);
  font-weight: 600;
}

/* Form static display */
.form-control-static {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
}

/* Type help block */
.type-help-block {
  display: flex;
  gap: 0.6rem;
  align-items: flex-start;
  font-size: 0.83rem;
  color: var(--text-secondary);
  background: var(--bg-secondary, #f8f9fa);
  border: 1px solid var(--border-color);
  border-left: 3px solid var(--color-primary, #3b82f6);
  border-radius: 0.375rem;
  padding: 0.6rem 0.875rem;
  margin-top: 0.75rem;
}

.type-help-icon {
  font-size: 1rem;
  color: var(--color-primary, #3b82f6);
  flex-shrink: 0;
  margin-top: 0.05rem;
}

/* Subnet inline form */
.subnet-inline-form {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 1rem;
  margin-top: 0.5rem;
  background: var(--bg-secondary, #f8f9fa);
}

.subnet-inline-title {
  margin: 0 0 0.75rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-secondary);
}

/* Help text */
.help-text-sm {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-top: 0.3rem;
}

/* Diagram */
.diagram-panel { padding: 1.5rem; }

.diagram-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
}

.zone-box {
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  min-width: 260px;
  max-width: 420px;
  flex: 1;
  overflow: hidden;
}

.zone-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-secondary, #f1f5f9);
  padding: 0.6rem 1rem;
  font-size: 0.9rem;
  flex-wrap: wrap;
}

.zone-mtu {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.zone-nodes {
  font-size: 0.72rem;
  color: var(--text-secondary);
  font-family: monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 80px;
}

.zone-type-badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  border-radius: 0.25rem;
  font-weight: 600;
  text-transform: uppercase;
}

.zone-type-badge.simple { background: #e2e8f0; color: #475569; }
.zone-type-badge.vlan { background: #dbeafe; color: #1d4ed8; }
.zone-type-badge.qinq { background: #fef3c7; color: #92400e; }
.zone-type-badge.vxlan { background: #ede9fe; color: #5b21b6; }
.zone-type-badge.evpn { background: #fee2e2; color: #991b1b; }

.zone-body { padding: 0.75rem 1rem; }
.no-vnets { font-size: 0.8rem; color: var(--text-secondary); font-style: italic; }

.vnet-box {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  margin-bottom: 0.6rem;
  overflow: hidden;
}

.vnet-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-card, #fff);
  padding: 0.4rem 0.75rem;
  font-size: 0.85rem;
  flex-wrap: wrap;
}

.vnet-id { font-weight: 600; }

.vnet-alias {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.vnet-tag {
  font-size: 0.75rem;
  background: #ede9fe;
  color: #5b21b6;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
}

.subnet-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.78rem;
  padding: 0.25rem 0.75rem;
  border-top: 1px solid var(--border-color);
  font-family: monospace;
  background: var(--bg-secondary, #f8f9fa);
  color: var(--text-secondary);
}

.subnet-cidr {
  font-weight: 600;
  color: var(--text-primary);
}

.gw {
  color: var(--text-secondary);
  font-style: italic;
}

.dhcp-hint {
  margin-left: auto;
  font-size: 0.7rem;
  background: #dcfce7;
  color: #166534;
  padding: 0.1rem 0.35rem;
  border-radius: 0.2rem;
  font-family: sans-serif;
  font-weight: 600;
}

/* Form */
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 0;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
}

.flex-center {
  display: flex;
  align-items: center;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  margin-top: 0.25rem;
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

.modal-content.modal-lg { max-width: 720px; }

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

.mt-2 { margin-top: 1rem; }
.mt-3 { margin-top: 1.5rem; }
.mb-2 { margin-bottom: 1rem; }
.mb-3 { margin-bottom: 1.5rem; }

@media (max-width: 1000px) {
  .zone-type-cards { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 900px) {
  .selector-inner { flex-direction: column; align-items: flex-start; }
  .selector-actions { margin-left: 0; }
  .form-row { grid-template-columns: 1fr; }
  .diagram-grid { flex-direction: column; }
  .zone-box { max-width: 100%; }
  .zone-type-cards { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 600px) {
  .zone-type-cards { grid-template-columns: 1fr; }
}
</style>
