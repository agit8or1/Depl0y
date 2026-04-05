<template>
  <div class="network-management-page">
    <div class="page-header mb-3">
      <div class="header-left">
        <h2>Network Management</h2>
        <p class="text-muted">Manage Proxmox node network interfaces</p>
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
          <button class="btn btn-primary" @click="openCreateModal">+ Create Interface</button>
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
            {{ savingRevert ? 'Reverting...' : 'Revert Changes' }}
          </button>
          <button class="btn btn-outline" @click="fetchInterfaces" :disabled="loading" title="Refresh">
            &#8635;
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

    <!-- Tabs (only shown when node is selected) -->
    <div v-else-if="selectedNode" class="tab-bar mb-3">
      <button :class="['tab-btn', { active: activeNetTab === 'interfaces' }]" @click="activeNetTab = 'interfaces'">Interfaces</button>
      <button :class="['tab-btn', { active: activeNetTab === 'vlans' }]" @click="activeNetTab = 'vlans'; fetchVlanInfo()">VLANs</button>
    </div>

    <!-- Interfaces table -->
    <div v-if="selectedNode && activeNetTab === 'interfaces'" class="card">
      <div class="card-header">
        <h3>Network Interfaces — {{ selectedNode }}</h3>
        <span class="text-muted text-sm">{{ interfaces.length }} interface{{ interfaces.length !== 1 ? 's' : '' }}</span>
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
              <th>Active</th>
              <th>Comment</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="iface in interfaces" :key="iface.iface">
              <td><strong>{{ iface.iface }}</strong></td>
              <td>
                <span :class="['badge', getTypeBadge(iface.type)]">
                  {{ iface.type || 'eth' }}
                </span>
              </td>
              <td class="text-sm">
                <span v-if="iface.address">{{ iface.address }}<span v-if="iface.netmask">/{{ cidrFromNetmask(iface.netmask) }}</span></span>
                <span v-else-if="iface.cidr">{{ iface.cidr }}</span>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="text-sm">{{ iface.gateway || '—' }}</td>
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
                <span :class="['badge', iface.active ? 'badge-success' : 'badge-danger']">
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

    <!-- VLANs tab -->
    <div v-if="selectedNode && activeNetTab === 'vlans'">
      <!-- VLAN interfaces across node -->
      <div class="card mb-3">
        <div class="card-header">
          <h3>VLAN Interfaces — {{ selectedNode }}</h3>
          <button class="btn btn-primary" @click="openCreateVlanModal">+ Create VLAN Interface</button>
        </div>
        <div v-if="loadingVlans" class="loading-spinner"></div>
        <div v-else-if="vlanInterfaces.length === 0" class="text-center text-muted" style="padding: 2rem;">
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
                <th>Active</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="iface in vlanInterfaces" :key="iface.iface">
                <td><strong>{{ iface.iface }}</strong></td>
                <td>{{ iface['vlan-raw-device'] || iface.vlan_raw_device || '—' }}</td>
                <td>{{ iface['vlan-id'] || iface.vlan_id || extractVlanTag(iface.iface) }}</td>
                <td class="text-sm">
                  <span v-if="iface.address">{{ iface.address }}<span v-if="iface.netmask">/{{ cidrFromNetmask(iface.netmask) }}</span></span>
                  <span v-else-if="iface.cidr">{{ iface.cidr }}</span>
                  <span v-else class="text-muted">—</span>
                </td>
                <td>
                  <span :class="['badge', iface.active ? 'badge-success' : 'badge-danger']">
                    {{ iface.active ? 'Active' : 'Inactive' }}
                  </span>
                </td>
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

      <!-- Bridge VLAN-aware section -->
      <div class="card mb-3">
        <div class="card-header">
          <h3>Bridge VLAN-Aware Settings</h3>
          <span class="text-muted text-sm">Enable/disable VLAN-aware mode on Linux bridges</span>
        </div>
        <div v-if="bridgeInterfaces.length === 0" class="text-center text-muted" style="padding: 1.5rem;">
          No bridge interfaces found on this node.
        </div>
        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Bridge</th>
                <th>Ports</th>
                <th>VLAN Aware</th>
                <th>Toggle</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="br in bridgeInterfaces" :key="br.iface">
                <td><strong>{{ br.iface }}</strong></td>
                <td class="text-sm">{{ br['bridge-ports'] || '—' }}</td>
                <td>
                  <span :class="['badge', br['bridge_vlan_aware'] || br.bridge_vlan_aware ? 'badge-success' : 'badge-secondary']">
                    {{ (br['bridge_vlan_aware'] || br.bridge_vlan_aware) ? 'Yes' : 'No' }}
                  </span>
                </td>
                <td>
                  <button
                    @click="toggleBridgeVlanAware(br)"
                    class="btn btn-outline btn-sm"
                    :disabled="togglingBridge === br.iface"
                  >
                    {{ togglingBridge === br.iface ? 'Saving...' : ((br['bridge_vlan_aware'] || br.bridge_vlan_aware) ? 'Disable VLAN-Aware' : 'Enable VLAN-Aware') }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Create VLAN Interface Modal -->
    <div v-if="showVlanModal" class="modal" @click="showVlanModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create VLAN Interface</h3>
          <button @click="showVlanModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitVlanModal" class="modal-body">
          <div class="form-group">
            <label class="form-label">Raw Device <span class="text-danger">*</span></label>
            <input v-model="vlanForm.raw_device" class="form-control" placeholder="e.g. vmbr0" required />
            <div class="help-text-sm">The parent interface to tag (usually a bridge or ethernet port)</div>
          </div>
          <div class="form-group">
            <label class="form-label">VLAN Tag <span class="text-danger">*</span></label>
            <input v-model.number="vlanForm.tag" type="number" class="form-control" placeholder="e.g. 100" min="1" max="4094" required />
            <div class="help-text-sm">Creates interface named <code>{{ vlanForm.raw_device || 'device' }}.{{ vlanForm.tag || 'tag' }}</code></div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">IP / CIDR</label>
              <input v-model="vlanForm.cidr" class="form-control" placeholder="e.g. 192.168.100.1/24" />
            </div>
            <div class="form-group">
              <label class="form-label">Gateway</label>
              <input v-model="vlanForm.gateway" class="form-control" placeholder="e.g. 192.168.100.254" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="vlanForm.comments" class="form-control" placeholder="Optional" />
          </div>
          <div class="form-group">
            <label class="form-label toggle-label">
              <input type="checkbox" v-model="vlanForm.autostart" />
              <span>Autostart on boot</span>
            </label>
          </div>
          <div class="form-actions mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingVlan">
              {{ savingVlan ? 'Creating...' : 'Create VLAN Interface' }}
            </button>
            <button type="button" @click="showVlanModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create / Edit Modal -->
    <div v-if="showModal" class="modal" @click="showModal = false">
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
              <input
                v-model="form.cidr"
                class="form-control"
                placeholder="e.g. 192.168.1.100/24"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Gateway</label>
              <input
                v-model="form.gateway"
                class="form-control"
                placeholder="e.g. 192.168.1.1"
              />
            </div>
          </div>

          <!-- Bridge ports (type=bridge) -->
          <div class="form-group" v-if="form.type === 'bridge' || form.type === 'OVSBridge'">
            <label class="form-label">Bridge Ports</label>
            <input
              v-model="form.bridge_ports"
              class="form-control"
              placeholder="e.g. eth0 (space-separated)"
            />
          </div>

          <!-- Bond slaves (type=bond) -->
          <div class="form-group" v-if="form.type === 'bond' || form.type === 'OVSBond'">
            <label class="form-label">Bond Slaves</label>
            <input
              v-model="form.slaves"
              class="form-control"
              placeholder="e.g. eth0 eth1 (space-separated)"
            />
            <div class="form-row mt-1">
              <div class="form-group">
                <label class="form-label">Bond Mode</label>
                <select v-model="form.bond_mode" class="form-control">
                  <option value="">— default —</option>
                  <option value="balance-rr">balance-rr</option>
                  <option value="active-backup">active-backup</option>
                  <option value="balance-xor">balance-xor</option>
                  <option value="broadcast">broadcast</option>
                  <option value="802.3ad">802.3ad (LACP)</option>
                  <option value="balance-tlb">balance-tlb</option>
                  <option value="balance-alb">balance-alb</option>
                </select>
              </div>
            </div>
          </div>

          <!-- VLAN tag (type=vlan) -->
          <div class="form-row" v-if="form.type === 'vlan'">
            <div class="form-group">
              <label class="form-label">VLAN Tag</label>
              <input
                v-model.number="form.vlan_raw_device"
                type="text"
                class="form-control"
                placeholder="e.g. eth0.100 or parent interface"
              />
            </div>
          </div>

          <!-- Bridge options -->
          <div class="form-row" v-if="form.type === 'bridge'">
            <div class="form-group">
              <label class="form-label toggle-label">
                <input type="checkbox" v-model="form.bridge_stp" />
                <span>Enable STP (Spanning Tree)</span>
              </label>
            </div>
            <div class="form-group">
              <label class="form-label">Bridge FD (Forward Delay)</label>
              <input
                v-model.number="form.bridge_fd"
                type="number"
                class="form-control"
                placeholder="0"
              />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Comment</label>
              <input v-model="form.comments" class="form-control" placeholder="Optional description" />
            </div>
            <div class="form-group flex-center">
              <label class="form-label toggle-label">
                <input type="checkbox" v-model="form.autostart" />
                <span>Autostart (bring up on boot)</span>
              </label>
            </div>
          </div>

          <div class="form-actions mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? 'Saving...' : (editingIface ? 'Update Interface' : 'Create Interface') }}
            </button>
            <button type="button" @click="showModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Apply warning modal -->
    <div v-if="showApplyWarning" class="modal" @click="showApplyWarning = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Apply Network Configuration</h3>
          <button @click="showApplyWarning = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="alert alert-warning mb-2">
            <strong>Warning:</strong> Applying network configuration will reload network interfaces on node
            <strong>{{ selectedNode }}</strong>. This may briefly disrupt network connectivity to the node
            and any VMs using affected bridges or bonds.
          </div>
          <p>Are you sure you want to apply pending network changes?</p>
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

    // Saving states
    const saving = ref(false)
    const savingApply = ref(false)
    const savingRevert = ref(false)

    // Modals
    const showModal = ref(false)
    const showApplyWarning = ref(false)
    const editingIface = ref(null)

    // Form
    const freshForm = () => ({
      iface: '',
      type: 'bridge',
      cidr: '',
      gateway: '',
      bridge_ports: '',
      slaves: '',
      bond_mode: '',
      bridge_stp: false,
      bridge_fd: 0,
      vlan_raw_device: '',
      comments: '',
      autostart: true,
    })
    const form = ref(freshForm())

    // Pending changes count — interfaces with "pending" flag set in Proxmox
    const pendingCount = computed(() => {
      return interfaces.value.filter(i => i.pending).length
    })

    // ── Fetch hosts ──────────────────────────────────────────────────────────
    const fetchHosts = async () => {
      loadingHosts.value = true
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = (res.data || []).filter(h => h.is_active)
      } catch (err) {
        toast.error('Failed to load Proxmox hosts')
      } finally {
        loadingHosts.value = false
      }
    }

    const onHostChange = async () => {
      selectedNode.value = ''
      nodes.value = []
      interfaces.value = []
      if (!selectedHostId.value) return
      loadingNodes.value = true
      try {
        const res = await api.proxmox.listNodes(selectedHostId.value)
        nodes.value = res.data || []
      } catch (err) {
        toast.error('Failed to load nodes')
      } finally {
        loadingNodes.value = false
      }
    }

    const onNodeChange = () => {
      interfaces.value = []
      if (selectedNode.value) {
        fetchInterfaces()
      }
    }

    // ── Fetch interfaces ─────────────────────────────────────────────────────
    const fetchInterfaces = async () => {
      if (!selectedHostId.value || !selectedNode.value) return
      loading.value = true
      try {
        const res = await api.pveNode.listNetwork(selectedHostId.value, selectedNode.value)
        interfaces.value = res.data || []
      } catch (err) {
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
        slaves: iface.slaves || '',
        bond_mode: iface.bond_mode || '',
        bridge_stp: iface['bridge_stp'] === 'on' || iface.bridge_stp === true,
        bridge_fd: iface['bridge_fd'] || 0,
        vlan_raw_device: iface['vlan-raw-device'] || iface.vlan_raw_device || '',
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
          toast.success(`Interface ${form.value.iface} updated`)
        } else {
          await api.pveNode.createNetwork(selectedHostId.value, selectedNode.value, payload)
          toast.success(`Interface ${form.value.iface} created`)
        }
        showModal.value = false
        await fetchInterfaces()
      } catch (err) {
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
        }
      }
      if (f.type === 'bond' || f.type === 'OVSBond') {
        if (f.slaves) p.slaves = f.slaves
        if (f.bond_mode) p.bond_mode = f.bond_mode
      }
      if (f.type === 'vlan') {
        if (f.vlan_raw_device) p['vlan-raw-device'] = f.vlan_raw_device
      }
      return p
    }

    // ── Delete ───────────────────────────────────────────────────────────────
    const confirmDelete = async (iface) => {
      if (!confirm(`Delete interface ${iface.iface}? This cannot be undone.`)) return
      try {
        await api.pveNode.deleteNetwork(selectedHostId.value, selectedNode.value, iface.iface)
        toast.success(`Interface ${iface.iface} deleted`)
        await fetchInterfaces()
      } catch (err) {
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
        toast.success('Network configuration applied successfully')
        showApplyWarning.value = false
        await fetchInterfaces()
      } catch (err) {
        toast.error('Failed to apply network configuration')
      } finally {
        savingApply.value = false
      }
    }

    const revertConfig = async () => {
      if (!confirm('Revert all pending (unapplied) network configuration changes?')) return
      savingRevert.value = true
      try {
        await api.pveNode.revertNetwork(selectedHostId.value, selectedNode.value)
        toast.success('Pending changes reverted')
        await fetchInterfaces()
      } catch (err) {
        toast.error('Failed to revert network changes')
      } finally {
        savingRevert.value = false
      }
    }

    // ── VLANs tab ─────────────────────────────────────────────────────────────
    const activeNetTab = ref('interfaces')
    const loadingVlans = ref(false)
    const vlanInterfaces = computed(() => interfaces.value.filter(i => i.type === 'vlan'))
    const bridgeInterfaces = computed(() => interfaces.value.filter(i => i.type === 'bridge'))
    const togglingBridge = ref(null)

    // VLAN create modal
    const showVlanModal = ref(false)
    const savingVlan = ref(false)
    const freshVlanForm = () => ({
      raw_device: '', tag: null, cidr: '', gateway: '', comments: '', autostart: true,
    })
    const vlanForm = ref(freshVlanForm())

    const fetchVlanInfo = async () => {
      // VLAN info is derived from interfaces; re-fetch if empty
      if (interfaces.value.length === 0) {
        loadingVlans.value = true
        await fetchInterfaces()
        loadingVlans.value = false
      }
    }

    const openCreateVlanModal = () => {
      vlanForm.value = freshVlanForm()
      showVlanModal.value = true
    }

    const submitVlanModal = async () => {
      savingVlan.value = true
      try {
        const f = vlanForm.value
        const ifaceName = `${f.raw_device}.${f.tag}`
        const payload = {
          iface: ifaceName,
          type: 'vlan',
          autostart: f.autostart ? 1 : 0,
          'vlan-raw-device': f.raw_device,
        }
        if (f.cidr) payload.cidr = f.cidr
        if (f.gateway) payload.gateway = f.gateway
        if (f.comments) payload.comments = f.comments
        await api.pveNode.createNetwork(selectedHostId.value, selectedNode.value, payload)
        toast.success(`VLAN interface ${ifaceName} created`)
        showVlanModal.value = false
        await fetchInterfaces()
      } catch {
        toast.error('Failed to create VLAN interface')
      } finally {
        savingVlan.value = false
      }
    }

    const toggleBridgeVlanAware = async (br) => {
      togglingBridge.value = br.iface
      try {
        const currentVal = br['bridge_vlan_aware'] || br.bridge_vlan_aware
        const newVal = currentVal ? 0 : 1
        await api.pveNode.updateNetwork(selectedHostId.value, selectedNode.value, br.iface, {
          bridge_vlan_aware: newVal,
        })
        toast.success(`${br.iface} VLAN-aware ${newVal ? 'enabled' : 'disabled'}`)
        await fetchInterfaces()
      } catch {
        toast.error(`Failed to toggle VLAN-aware on ${br.iface}`)
      } finally {
        togglingBridge.value = null
      }
    }

    const extractVlanTag = (ifaceName) => {
      // e.g. vmbr0.100 → 100
      if (!ifaceName) return '—'
      const parts = ifaceName.split('.')
      return parts.length >= 2 ? parts[parts.length - 1] : '—'
    }

    // ── Helpers ──────────────────────────────────────────────────────────────
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
      // Convert dotted netmask to CIDR prefix length
      return netmask.split('.').reduce((acc, octet) => {
        return acc + (parseInt(octet) >>> 0).toString(2).split('1').length - 1
      }, 0)
    }

    onMounted(() => {
      fetchHosts()
    })

    return {
      hosts, nodes, selectedHostId, selectedNode,
      loadingHosts, loadingNodes,
      interfaces, loading,
      saving, savingApply, savingRevert,
      pendingCount,
      showModal, showApplyWarning,
      editingIface, form,
      onHostChange, onNodeChange,
      fetchInterfaces,
      openCreateModal, openEditModal, submitModal,
      confirmDelete,
      applyConfig, doApplyConfig, revertConfig,
      getTypeBadge, cidrFromNetmask,
      // VLAN tab
      activeNetTab,
      loadingVlans, vlanInterfaces, bridgeInterfaces, togglingBridge,
      showVlanModal, savingVlan, vlanForm,
      fetchVlanInfo, openCreateVlanModal, submitVlanModal,
      toggleBridgeVlanAware, extractVlanTag,
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
.selector-bar {
  padding: 1rem 1.25rem;
}

.selector-inner {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.selector-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.selector-group select {
  min-width: 220px;
}

.selector-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-left: auto;
}

.pending-badge {
  font-size: 0.8rem;
  padding: 0.3rem 0.75rem;
}

/* Table */
.action-btns {
  display: flex;
  gap: 0.4rem;
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
  margin-top: 1.75rem;
}

.mt-1 {
  margin-top: 0.75rem;
}

/* Alert */
.alert {
  padding: 0.875rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.9rem;
}

.alert-warning {
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.4);
  color: var(--text-primary);
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
  background: white;
  border-radius: 0.5rem;
  max-width: 540px;
  width: 95%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg, 0 20px 60px rgba(0,0,0,0.3));
}

.modal-content.modal-lg {
  max-width: 680px;
}

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

.modal-body {
  padding: 1.5rem;
}

.btn-sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.875rem;
}

.gap-1 {
  gap: 0.5rem;
}

.text-sm {
  font-size: 0.875rem;
}

.text-danger {
  color: var(--color-danger, #ef4444);
}

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
.tab-btn.active {
  color: var(--color-primary, #3b82f6);
  border-bottom-color: var(--color-primary, #3b82f6);
  font-weight: 600;
}

.help-text-sm {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-top: 0.3rem;
}

.help-text-sm code {
  background: var(--bg-secondary, #f1f5f9);
  padding: 0.1rem 0.3rem;
  border-radius: 0.2rem;
  font-family: monospace;
}

@media (max-width: 900px) {
  .selector-inner {
    flex-direction: column;
    align-items: flex-start;
  }

  .selector-actions {
    margin-left: 0;
    width: 100%;
  }

  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
