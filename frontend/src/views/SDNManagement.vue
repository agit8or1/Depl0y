<template>
  <div class="sdn-page">
    <!-- Page header -->
    <div class="page-header mb-3">
      <div class="header-left">
        <h2>SDN / VNets</h2>
        <p class="text-muted">Manage Proxmox Software-Defined Networking — zones, VNets, and subnets</p>
      </div>
      <div class="header-right">
        <button
          v-if="pendingChanges"
          class="btn btn-warning"
          @click="applyChanges"
          :disabled="applying"
        >
          {{ applying ? 'Applying...' : 'Apply Pending Changes' }}
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
          <button class="btn btn-outline" @click="refreshAll" :disabled="loading" title="Refresh">&#8635;</button>
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
        >{{ tab.label }}</button>
      </div>

      <!-- ══ ZONES TAB ════════════════════════════════════════════════════════ -->
      <div v-if="activeTab === 'zones'">
        <div class="card">
          <div class="card-header">
            <h3>SDN Zones</h3>
            <button class="btn btn-primary" @click="openCreateZoneModal">+ Create Zone</button>
          </div>

          <div class="zone-type-legend mb-2" style="padding: 0 1.25rem;">
            <span class="legend-title">Zone types: </span>
            <span class="badge badge-secondary">simple</span> basic L2 isolation &nbsp;
            <span class="badge badge-info">vlan</span> IEEE 802.1q VLAN tagging &nbsp;
            <span class="badge badge-warning">qinq</span> double-tagging (802.1ad) &nbsp;
            <span class="badge badge-primary">vxlan</span> L2 over L3 tunnels &nbsp;
            <span class="badge badge-danger">evpn</span> BGP EVPN control plane
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
                  <th>Bridge</th>
                  <th>Nodes</th>
                  <th>Peers / VRF</th>
                  <th>State</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="z in zones" :key="z.zone">
                  <td><strong>{{ z.zone }}</strong></td>
                  <td><span :class="['badge', getZoneTypeBadge(z.type)]">{{ z.type }}</span></td>
                  <td>{{ z.mtu || '—' }}</td>
                  <td>{{ z.bridge || '—' }}</td>
                  <td class="text-sm">{{ z.nodes || 'all' }}</td>
                  <td class="text-sm">{{ z.peers || z.vrf_vxlan || '—' }}</td>
                  <td>
                    <span :class="['badge', z.state === 'ok' ? 'badge-success' : 'badge-secondary']">
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
                  <th>Zone</th>
                  <th>Alias</th>
                  <th>Tag (VLAN/VXLAN)</th>
                  <th>Subnets</th>
                  <th>State</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="v in vnets" :key="v.vnet">
                  <td><strong>{{ v.vnet }}</strong></td>
                  <td>{{ v.zone || '—' }}</td>
                  <td>{{ v.alias || '—' }}</td>
                  <td>{{ v.tag != null ? v.tag : '—' }}</td>
                  <td>
                    <span class="text-sm text-muted">{{ subnetCountFor(v.vnet) }}</span>
                  </td>
                  <td>
                    <span :class="['badge', v.state === 'ok' ? 'badge-success' : 'badge-secondary']">
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
              </tbody>
            </table>
          </div>
        </div>

        <!-- Subnets per VNet -->
        <div v-if="subnets.length > 0" class="card mt-3">
          <div class="card-header">
            <h3>Subnets</h3>
          </div>
          <div class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Subnet (CIDR)</th>
                  <th>VNet</th>
                  <th>Gateway</th>
                  <th>SNAT</th>
                  <th>DHCP Range</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in subnets" :key="s.subnet + s.vnet">
                  <td><strong>{{ s.subnet }}</strong></td>
                  <td>{{ s.vnet || '—' }}</td>
                  <td>{{ s.gateway || '—' }}</td>
                  <td>
                    <span :class="['badge', s.snat ? 'badge-success' : 'badge-secondary']">
                      {{ s.snat ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td class="text-sm">{{ s.dhcp_range || '—' }}</td>
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
            <span class="text-muted text-sm">Visual overview of zones and VNets</span>
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
                </div>
                <div class="zone-body">
                  <div v-if="vnetsForZone(z.zone).length === 0" class="no-vnets">No VNets</div>
                  <div v-for="v in vnetsForZone(z.zone)" :key="v.vnet" class="vnet-box">
                    <div class="vnet-header">
                      <span class="vnet-id">{{ v.vnet }}</span>
                      <span v-if="v.alias" class="vnet-alias">{{ v.alias }}</span>
                      <span v-if="v.tag != null" class="vnet-tag">tag: {{ v.tag }}</span>
                    </div>
                    <div v-for="s in subnetsForVnet(v.vnet)" :key="s.subnet" class="subnet-label">
                      {{ s.subnet }}
                      <span v-if="s.gateway" class="gw">gw: {{ s.gateway }}</span>
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
    <div v-if="showZoneModal" class="modal" @click="showZoneModal = false">
      <div class="modal-content modal-lg" @click.stop>
        <div class="modal-header">
          <h3>{{ editingZone ? 'Edit Zone' : 'Create SDN Zone' }}</h3>
          <button @click="showZoneModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitZoneModal" class="modal-body">
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
            </div>
            <div class="form-group">
              <label class="form-label">Type <span class="text-danger">*</span></label>
              <select v-model="zoneForm.type" class="form-control" :disabled="!!editingZone" required>
                <option value="simple">Simple — basic L2 isolation</option>
                <option value="vlan">VLAN — 802.1q tagging</option>
                <option value="qinq">QinQ — double tagging (802.1ad)</option>
                <option value="vxlan">VXLAN — L2 over L3 tunnels</option>
                <option value="evpn">EVPN — BGP control plane</option>
              </select>
            </div>
          </div>

          <div class="help-text mb-2">
            <span v-if="zoneForm.type === 'simple'">Simple zones provide basic L2 network isolation using a Linux bridge.</span>
            <span v-else-if="zoneForm.type === 'vlan'">VLAN zones use IEEE 802.1q tagging on a physical bridge interface. Each VNet gets a VLAN ID.</span>
            <span v-else-if="zoneForm.type === 'qinq'">QinQ (802.1ad) double-tagging for provider/customer VLAN separation.</span>
            <span v-else-if="zoneForm.type === 'vxlan'">VXLAN tunnels L2 over L3, enabling multi-site networks. Specify peer IPs for multicast-free mode.</span>
            <span v-else-if="zoneForm.type === 'evpn'">EVPN uses BGP as a control plane for VXLAN overlays with distributed routing and exit nodes.</span>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">MTU</label>
              <input v-model.number="zoneForm.mtu" type="number" class="form-control" placeholder="1500" min="576" max="9000" />
            </div>
            <div class="form-group">
              <label class="form-label">Nodes (comma-separated, blank = all)</label>
              <input v-model="zoneForm.nodes" class="form-control" placeholder="e.g. pve1,pve2" />
            </div>
          </div>

          <!-- Simple / VLAN / QinQ: bridge -->
          <div class="form-group" v-if="['simple','vlan','qinq'].includes(zoneForm.type)">
            <label class="form-label">Bridge Interface</label>
            <input v-model="zoneForm.bridge" class="form-control" placeholder="e.g. vmbr0" />
          </div>

          <!-- VXLAN: peers -->
          <div class="form-group" v-if="zoneForm.type === 'vxlan'">
            <label class="form-label">Peer Node IPs (comma-separated)</label>
            <input v-model="zoneForm.peers" class="form-control" placeholder="e.g. 10.0.0.1,10.0.0.2" />
          </div>

          <!-- EVPN specific -->
          <div v-if="zoneForm.type === 'evpn'">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">VRF VXLAN ID</label>
                <input v-model.number="zoneForm.vrf_vxlan" type="number" class="form-control" placeholder="e.g. 10000" />
              </div>
              <div class="form-group">
                <label class="form-label">Exit Nodes (comma-separated)</label>
                <input v-model="zoneForm.exitnodes" class="form-control" placeholder="e.g. pve1,pve2" />
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
            <div class="form-group">
              <label class="form-label">Peer Nodes</label>
              <input v-model="zoneForm.peers" class="form-control" placeholder="e.g. 10.0.0.1,10.0.0.2" />
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
    <div v-if="showVnetModal" class="modal" @click="showVnetModal = false">
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
              <select v-model="vnetForm.zone" class="form-control" required>
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
              <label class="form-label">Tag (VLAN/VXLAN ID)</label>
              <input v-model.number="vnetForm.tag" type="number" class="form-control" placeholder="e.g. 100" min="1" max="16777215" />
            </div>
          </div>

          <!-- Subnet (optional at creation time) -->
          <div class="form-group">
            <label class="form-label toggle-label">
              <input type="checkbox" v-model="vnetForm.addSubnet" />
              <span>Add a subnet now</span>
            </label>
          </div>
          <div v-if="vnetForm.addSubnet" class="subnet-inline-form">
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
              <div class="form-group flex-center">
                <label class="form-label toggle-label">
                  <input type="checkbox" v-model="vnetForm.subnetSnat" />
                  <span>Enable SNAT (masquerade outbound)</span>
                </label>
              </div>
              <div class="form-group">
                <label class="form-label">DHCP Range</label>
                <input v-model="vnetForm.subnetDhcpRange" class="form-control" placeholder="e.g. 10.0.0.100-10.0.0.200" />
              </div>
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
    <div v-if="showSubnetModal" class="modal" @click="showSubnetModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Subnet to {{ subnetTargetVnet }}</h3>
          <button @click="showSubnetModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitSubnetModal" class="modal-body">
          <div class="form-group">
            <label class="form-label">CIDR <span class="text-danger">*</span></label>
            <input v-model="subnetForm.subnet" class="form-control" placeholder="e.g. 10.0.0.0/24" required />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Gateway</label>
              <input v-model="subnetForm.gateway" class="form-control" placeholder="e.g. 10.0.0.1" />
            </div>
            <div class="form-group">
              <label class="form-label">DHCP Range</label>
              <input v-model="subnetForm.dhcp_range" class="form-control" placeholder="e.g. 10.0.0.100-10.0.0.200" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label toggle-label">
              <input type="checkbox" v-model="subnetForm.snat" />
              <span>Enable SNAT (masquerade outbound)</span>
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

    // Data
    const zones = ref([])
    const vnets = ref([])
    const subnets = ref([])
    const loading = ref(false)
    const pendingChanges = ref(false)
    const applying = ref(false)

    // Tabs
    const tabs = [
      { id: 'zones', label: 'Zones' },
      { id: 'vnets', label: 'VNets & Subnets' },
      { id: 'diagram', label: 'Topology Diagram' },
    ]
    const activeTab = ref('zones')

    // Zone modal
    const showZoneModal = ref(false)
    const editingZone = ref(null)
    const savingZone = ref(false)
    const freshZoneForm = () => ({
      zone: '', type: 'simple', mtu: null, nodes: '', bridge: '',
      peers: '', vrf_vxlan: null, controller: '', rt_import: '', rt_export: '',
      exitnodes: '',
    })
    const zoneForm = ref(freshZoneForm())

    // VNet modal
    const showVnetModal = ref(false)
    const editingVnet = ref(null)
    const savingVnet = ref(false)
    const freshVnetForm = () => ({
      vnet: '', zone: '', alias: '', tag: null,
      addSubnet: false, subnetCidr: '', subnetGw: '', subnetSnat: false, subnetDhcpRange: '',
    })
    const vnetForm = ref(freshVnetForm())

    // Subnet modal
    const showSubnetModal = ref(false)
    const subnetTargetVnet = ref('')
    const savingSubnet = ref(false)
    const freshSubnetForm = () => ({ subnet: '', gateway: '', snat: false, dhcp_range: '' })
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

    const onHostChange = () => {
      zones.value = []
      vnets.value = []
      subnets.value = []
      pendingChanges.value = false
      if (selectedHostId.value) refreshAll()
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

        // Detect pending changes: any object with state != 'ok' or state missing
        const allObjs = [...zones.value, ...vnets.value, ...subnets.value]
        pendingChanges.value = allObjs.some(o => o.state && o.state !== 'ok') ||
          allObjs.some(o => !o.state)
      } catch {
        toast.error('Failed to load SDN data')
      } finally {
        loading.value = false
      }
    }

    // ── Apply changes ────────────────────────────────────────────────────────
    const applyChanges = async () => {
      if (!confirm('Apply all pending SDN changes to the cluster?')) return
      applying.value = true
      try {
        await api.sdn.apply(selectedHostId.value)
        toast.success('SDN changes applied successfully')
        pendingChanges.value = false
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
        mtu: z.mtu || null, nodes: z.nodes || '', bridge: z.bridge || '',
        peers: z.peers || '', vrf_vxlan: z.vrf_vxlan || null,
        controller: z.controller || '', rt_import: z.rt_import || '',
        rt_export: z.rt_export || '', exitnodes: z.exitnodes || '',
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
        pendingChanges.value = true
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
      if (f.nodes) p.nodes = f.nodes
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
        pendingChanges.value = true
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
        tag: v.tag != null ? v.tag : null,
        addSubnet: false, subnetCidr: '', subnetGw: '', subnetSnat: false, subnetDhcpRange: '',
      }
      showVnetModal.value = true
    }

    const submitVnetModal = async () => {
      savingVnet.value = true
      try {
        const f = vnetForm.value
        const payload = { vnet: f.vnet, zone: f.zone }
        if (f.alias) payload.alias = f.alias
        if (f.tag != null && f.tag !== '') payload.tag = f.tag

        if (editingVnet.value) {
          const updatePayload = {}
          if (f.alias !== undefined) updatePayload.alias = f.alias
          if (f.tag != null && f.tag !== '') updatePayload.tag = f.tag
          await api.sdn.updateVnet(selectedHostId.value, f.vnet, updatePayload)
          toast.success(`VNet ${f.vnet} updated`)
        } else {
          await api.sdn.createVnet(selectedHostId.value, payload)
          toast.success(`VNet ${f.vnet} created`)
          // Optionally create subnet
          if (f.addSubnet && f.subnetCidr) {
            const sPayload = { subnet: f.subnetCidr, vnet: f.vnet }
            if (f.subnetGw) sPayload.gateway = f.subnetGw
            if (f.subnetSnat) sPayload.snat = 1
            if (f.subnetDhcpRange) sPayload.dhcp_range = f.subnetDhcpRange
            await api.sdn.createSubnet(selectedHostId.value, sPayload)
            toast.success(`Subnet ${f.subnetCidr} added`)
          }
        }
        showVnetModal.value = false
        pendingChanges.value = true
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
        pendingChanges.value = true
        await refreshAll()
      } catch {
        toast.error(`Failed to delete VNet ${v.vnet}`)
      }
    }

    // ── Subnet modal ─────────────────────────────────────────────────────────
    const openAddSubnetModal = (v) => {
      subnetTargetVnet.value = v.vnet
      subnetForm.value = freshSubnetForm()
      showSubnetModal.value = true
    }

    const submitSubnetModal = async () => {
      savingSubnet.value = true
      try {
        const f = subnetForm.value
        const payload = { subnet: f.subnet, vnet: subnetTargetVnet.value }
        if (f.gateway) payload.gateway = f.gateway
        if (f.snat) payload.snat = 1
        if (f.dhcp_range) payload.dhcp_range = f.dhcp_range
        await api.sdn.createSubnet(selectedHostId.value, payload)
        toast.success(`Subnet ${f.subnet} added to ${subnetTargetVnet.value}`)
        showSubnetModal.value = false
        pendingChanges.value = true
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
        pendingChanges.value = true
        await refreshAll()
      } catch {
        toast.error(`Failed to delete subnet ${s.subnet}`)
      }
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
      hosts, selectedHostId, loadingHosts,
      zones, vnets, subnets, loading, pendingChanges, applying,
      tabs, activeTab,
      showZoneModal, editingZone, savingZone, zoneForm,
      showVnetModal, editingVnet, savingVnet, vnetForm,
      showSubnetModal, subnetTargetVnet, savingSubnet, subnetForm,
      onHostChange, refreshAll, applyChanges,
      openCreateZoneModal, openEditZoneModal, submitZoneModal, confirmDeleteZone,
      openCreateVnetModal, openEditVnetModal, submitVnetModal, confirmDeleteVnet,
      openAddSubnetModal, submitSubnetModal, confirmDeleteSubnet,
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

/* Tabs */
.tab-bar {
  display: flex;
  gap: 0.25rem;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
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

/* Table */
.action-btns { display: flex; gap: 0.4rem; }
.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.875rem; }
.text-sm { font-size: 0.875rem; }
.text-danger { color: var(--color-danger, #ef4444); }

/* Legend */
.zone-type-legend {
  font-size: 0.8rem;
  color: var(--text-secondary);
  padding-bottom: 0.75rem;
}

/* Help text */
.help-text {
  font-size: 0.83rem;
  color: var(--text-secondary);
  background: var(--bg-secondary, #f8f9fa);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.5rem 0.875rem;
}

/* Subnet inline form */
.subnet-inline-form {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 1rem;
  margin-top: 0.5rem;
  background: var(--bg-secondary, #f8f9fa);
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
  max-width: 400px;
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
}

.zone-mtu {
  margin-left: auto;
  font-size: 0.75rem;
  color: var(--text-secondary);
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
}

.vnet-id { font-weight: 600; }

.vnet-alias {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.vnet-tag {
  margin-left: auto;
  font-size: 0.75rem;
  background: #ede9fe;
  color: #5b21b6;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
}

.subnet-label {
  font-size: 0.78rem;
  padding: 0.25rem 0.75rem;
  border-top: 1px solid var(--border-color);
  font-family: monospace;
  background: var(--bg-secondary, #f8f9fa);
  color: var(--text-secondary);
}

.gw {
  margin-left: 0.5rem;
  color: var(--text-secondary);
  font-style: italic;
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

.modal-content.modal-lg { max-width: 680px; }

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
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

@media (max-width: 900px) {
  .selector-inner { flex-direction: column; align-items: flex-start; }
  .selector-actions { margin-left: 0; }
  .form-row { grid-template-columns: 1fr; }
  .diagram-grid { flex-direction: column; }
  .zone-box { max-width: 100%; }
}
</style>
