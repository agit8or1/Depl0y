<template>
  <div class="pci-passthrough">
    <!-- Currently attached PCI devices -->
    <div class="card mb-2">
      <div class="card-header">
        <h4>Attached PCI Devices</h4>
        <button @click="showAddModal = true" class="btn btn-primary btn-sm" :disabled="loading">
          + Add PCI Device
        </button>
      </div>
      <div v-if="loadingAttached" class="loading-spinner"></div>
      <div v-else-if="attachedDevices.length === 0" class="text-center text-muted" style="padding:1.2rem;">
        No PCI devices passed through.
      </div>
      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Slot</th>
              <th>PCI ID / Config</th>
              <th>Options</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="dev in attachedDevices" :key="dev.key">
              <td><code>{{ dev.key }}</code></td>
              <td>
                <code>{{ dev.pciid }}</code>
                <span v-if="dev.pcie" class="badge badge-info ml-1">PCIe</span>
                <span v-if="dev.xvga" class="badge badge-warning ml-1">x-vga</span>
                <span v-if="dev.mdev" class="badge badge-secondary ml-1">mdev:{{ dev.mdev }}</span>
              </td>
              <td class="text-sm text-muted">
                rombar={{ dev.rombar ? '1' : '0' }}
              </td>
              <td>
                <button @click="removePci(dev)" class="btn btn-danger btn-sm"
                        :disabled="removing === dev.key">
                  {{ removing === dev.key ? '...' : 'Remove' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- PCI device browser -->
    <div class="card">
      <div class="card-header">
        <h4>Available PCI Devices on Node</h4>
        <div class="flex gap-1 align-center">
          <select v-model="selectedNode" @change="loadPciDevices" class="form-control form-control-sm"
                  style="min-width:140px;">
            <option v-for="n in nodes" :key="n" :value="n">{{ n }}</option>
          </select>
          <button @click="loadPciDevices" class="btn btn-outline btn-sm" :disabled="loading">
            Refresh
          </button>
        </div>
      </div>

      <div v-if="loading" class="loading-spinner"></div>
      <div v-else-if="!pciDevices.length" class="text-center text-muted" style="padding:1.2rem;">
        No PCI devices found on this node.
      </div>
      <div v-else>
        <!-- IOMMU group tree -->
        <div v-for="(group, gid) in iommuGroups" :key="gid" class="iommu-group">
          <div class="iommu-group-header" @click="toggleGroup(gid)">
            <span class="iommu-group-toggle">{{ expandedGroups.has(gid) ? '▼' : '▶' }}</span>
            <span class="iommu-group-label">IOMMU Group {{ gid }}</span>
            <span class="badge badge-secondary ml-1">{{ group.length }} device{{ group.length !== 1 ? 's' : '' }}</span>
            <span v-if="hasGpu(group)" class="badge badge-warning ml-1">GPU</span>
            <span v-if="groupPartiallyAttached(group)" class="badge badge-danger ml-1">partially attached</span>
          </div>
          <div v-show="expandedGroups.has(gid)" class="iommu-group-devices">
            <div v-for="dev in group" :key="dev.id" class="pci-device-row"
                 :class="{ 'pci-device-row--gpu': isGpu(dev), 'pci-device-row--attached': isAttached(dev.id) }">
              <div class="pci-device-info">
                <span class="pci-id"><code>{{ dev.id }}</code></span>
                <span class="pci-name ml-1">{{ dev.device_name || dev.vendor_name || '(unknown)' }}</span>
                <span v-if="isGpu(dev)" class="badge badge-warning ml-1">GPU</span>
                <span v-if="isAttached(dev.id)" class="badge badge-success ml-1">in use by VM</span>
                <span v-else-if="isUsedByHost(dev)" class="badge badge-danger ml-1">used by host</span>
                <span class="pci-class text-muted ml-1 text-sm">{{ dev.class_name || dev.class }}</span>
              </div>
              <div class="pci-device-actions">
                <button
                  @click="openAddDeviceModal(dev, group)"
                  class="btn btn-primary btn-sm"
                  :disabled="isAttached(dev.id)"
                >
                  Add to VM
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add PCI device modal -->
    <div v-if="showAddModal" class="modal" @click.self="closeAddModal">
      <div class="modal-content" @click.stop style="max-width:480px;">
        <div class="modal-header">
          <h3>Add PCI Device to VM {{ vmid }}</h3>
          <button @click="closeAddModal" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="selectedDevice" class="mb-2">
            <p class="text-sm">
              <strong>Device:</strong> <code>{{ selectedDevice.id }}</code><br>
              <strong>Name:</strong> {{ selectedDevice.device_name || selectedDevice.vendor_name || '(unknown)' }}
            </p>
            <div v-if="groupWarning" class="alert alert-warning text-sm mb-2">
              This IOMMU group has {{ selectedGroupDevices.length }} devices. For full isolation, you should pass
              through all devices in the group. The following are in the same group:<br>
              <span v-for="d in selectedGroupDevices" :key="d.id">
                <code>{{ d.id }}</code> {{ d.device_name || '' }}<br>
              </span>
            </div>
          </div>

          <!-- PCI ID input (manual if no device selected) -->
          <div v-if="!selectedDevice" class="form-group">
            <label class="form-label">PCI ID</label>
            <input v-model="addForm.pciid" class="form-control" placeholder="0000:01:00.0" />
          </div>

          <div class="form-group">
            <label class="toggle-item" style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;">
              <input type="checkbox" v-model="addForm.pcie" />
              <span>PCIe mode (recommended)</span>
            </label>
          </div>

          <div class="form-group">
            <label class="toggle-item" style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;">
              <input type="checkbox" v-model="addForm.x_vga" />
              <span>Primary GPU (x-vga) — enables VGA framebuffer, use for GPU display output</span>
            </label>
          </div>

          <div class="form-group">
            <label class="toggle-item" style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;">
              <input type="checkbox" v-model="addForm.rombar" />
              <span>ROM bar — expose device VBIOS ROM to guest</span>
            </label>
          </div>

          <!-- mdev type dropdown (only when mdev types are available) -->
          <div v-if="mdevTypes.length > 0" class="form-group">
            <label class="form-label">vGPU / Mediated Device Type (optional)</label>
            <select v-model="addForm.mdev" class="form-control">
              <option value="">None (full passthrough)</option>
              <option v-for="t in mdevTypes" :key="t.type" :value="t.type">
                {{ t.type }} — {{ t.description || '' }} (available: {{ t.available }})
              </option>
            </select>
          </div>

          <div class="alert alert-warning text-sm mt-2">
            The VM must be <strong>powered off</strong> before making PCI configuration changes.
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeAddModal" class="btn btn-outline">Cancel</button>
          <button @click="doAddPci" class="btn btn-primary" :disabled="saving || !effectivePciId">
            {{ saving ? 'Adding...' : 'Add Device' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

const props = defineProps({
  hostId: { type: [String, Number], required: true },
  node: { type: String, required: true },
  vmid: { type: [String, Number], required: true },
  vmConfig: { type: Object, default: () => ({}) },
  nodes: { type: Array, default: () => [] },
})

const emit = defineEmits(['config-changed'])
const toast = useToast()

// State
const selectedNode = ref(props.node)
const pciDevices = ref([])
const loading = ref(false)
const loadingAttached = ref(false)
const showAddModal = ref(false)
const saving = ref(false)
const removing = ref(null)
const expandedGroups = ref(new Set())
const mdevTypes = ref([])

// Add form
const addForm = ref({
  pciid: '',
  pcie: true,
  x_vga: false,
  rombar: true,
  mdev: '',
})

const selectedDevice = ref(null)
const selectedGroupDevices = ref([])

// Parse currently attached PCI devices from vmConfig
const attachedDevices = computed(() => {
  const result = []
  const cfg = props.vmConfig || {}
  for (let i = 0; i < 16; i++) {
    const key = `hostpci${i}`
    if (cfg[key]) {
      const val = cfg[key]
      const parts = val.split(',')
      const pciid = parts[0]
      const pcie = parts.some(p => p === 'pcie=1')
      const xvga = parts.some(p => p === 'x-vga=1')
      const rombar = !parts.some(p => p === 'rombar=0')
      const mdevPart = parts.find(p => p.startsWith('mdev='))
      const mdev = mdevPart ? mdevPart.replace('mdev=', '') : null
      result.push({ key, index: i, pciid, pcie, xvga, rombar, mdev })
    }
  }
  return result
})

// Group by IOMMU group
const iommuGroups = computed(() => {
  const groups = {}
  for (const dev of pciDevices.value) {
    const gid = dev.iommugroup !== undefined ? String(dev.iommugroup) : 'none'
    if (!groups[gid]) groups[gid] = []
    groups[gid].push(dev)
  }
  return groups
})

const groupWarning = computed(() => {
  return selectedGroupDevices.value.length > 1
})

const effectivePciId = computed(() => {
  if (selectedDevice.value) return selectedDevice.value.id
  return addForm.value.pciid.trim()
})

// Helpers
function isGpu(dev) {
  const cls = (dev.class || '').toLowerCase()
  const name = (dev.device_name || dev.vendor_name || '').toLowerCase()
  return cls.includes('0300') || cls.includes('display') || cls.includes('vga') ||
         name.includes('gpu') || name.includes('geforce') || name.includes('radeon') ||
         name.includes('nvidia') || name.includes('amd') || name.includes('intel')
}

function hasGpu(group) {
  return group.some(d => isGpu(d))
}

function isAttached(pciid) {
  return attachedDevices.value.some(d =>
    d.pciid === pciid || d.pciid.startsWith(pciid) || pciid.startsWith(d.pciid)
  )
}

function isUsedByHost(dev) {
  // If it has iommu group but no attached VMs — host may use it (driver check not available via API)
  return false
}

function groupPartiallyAttached(group) {
  if (group.length <= 1) return false
  const attachedCount = group.filter(d => isAttached(d.id)).length
  return attachedCount > 0 && attachedCount < group.length
}

function toggleGroup(gid) {
  if (expandedGroups.value.has(gid)) {
    expandedGroups.value.delete(gid)
  } else {
    expandedGroups.value.add(gid)
  }
  // Trigger reactivity
  expandedGroups.value = new Set(expandedGroups.value)
}

// Load PCI devices from node
async function loadPciDevices() {
  if (!selectedNode.value) return
  loading.value = true
  pciDevices.value = []
  try {
    const res = await api.pveNode.listPciDevices(props.hostId, selectedNode.value)
    pciDevices.value = res.data || []
    // Auto-expand groups with GPUs
    for (const [gid, group] of Object.entries(iommuGroups.value)) {
      if (hasGpu(group)) {
        expandedGroups.value.add(gid)
      }
    }
    expandedGroups.value = new Set(expandedGroups.value)
  } catch (e) {
    toast.error('Failed to load PCI devices: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

// Open add modal from device tree
async function openAddDeviceModal(dev, groupDevices) {
  selectedDevice.value = dev
  selectedGroupDevices.value = groupDevices.filter(d => d.id !== dev.id)
  addForm.value = {
    pciid: dev.id,
    pcie: true,
    x_vga: isGpu(dev),
    rombar: true,
    mdev: '',
  }
  mdevTypes.value = []
  showAddModal.value = true

  // Try to load mdev types (for vGPU capable devices)
  try {
    const res = await api.pveNode.getPciMdevTypes(props.hostId, selectedNode.value, dev.id)
    mdevTypes.value = res.data || []
  } catch {
    // Not all devices support mdev — silently ignore
    mdevTypes.value = []
  }
}

function closeAddModal() {
  showAddModal.value = false
  selectedDevice.value = null
  selectedGroupDevices.value = []
  mdevTypes.value = []
  addForm.value = { pciid: '', pcie: true, x_vga: false, rombar: true, mdev: '' }
}

// Add PCI device to VM
async function doAddPci() {
  const pciid = effectivePciId.value
  if (!pciid) {
    toast.error('PCI ID is required')
    return
  }
  saving.value = true
  try {
    const payload = {
      pciid,
      pcie: addForm.value.pcie,
      x_vga: addForm.value.x_vga,
      rombar: addForm.value.rombar,
    }
    if (addForm.value.mdev) {
      payload.mdev = addForm.value.mdev
    }
    await api.pveVm.addPciDevice(props.hostId, props.node, props.vmid, payload)
    toast.success('PCI device added to VM config')
    closeAddModal()
    emit('config-changed')
  } catch (e) {
    toast.error('Failed to add PCI device: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

// Remove PCI device from VM
async function removePci(dev) {
  if (!confirm(`Remove ${dev.key} (${dev.pciid}) from VM config?`)) return
  removing.value = dev.key
  try {
    await api.pveVm.removePciDevice(props.hostId, props.node, props.vmid, dev.index)
    toast.success(`${dev.key} removed from VM config`)
    emit('config-changed')
  } catch (e) {
    toast.error('Failed to remove PCI device: ' + (e.response?.data?.detail || e.message))
  } finally {
    removing.value = null
  }
}

// Init
onMounted(() => {
  selectedNode.value = props.node
  loadPciDevices()
})

watch(() => props.node, (newNode) => {
  selectedNode.value = newNode
  loadPciDevices()
})
</script>

<style scoped>
.pci-passthrough {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.iommu-group {
  border-bottom: 1px solid var(--border-color);
}

.iommu-group:last-child {
  border-bottom: none;
}

.iommu-group-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.25rem;
  cursor: pointer;
  background: var(--surface);
  user-select: none;
  font-weight: 600;
  font-size: 0.85rem;
}

.iommu-group-header:hover {
  background: rgba(148, 163, 184, 0.12);
}

.iommu-group-toggle {
  font-size: 0.7rem;
  color: var(--text-secondary);
  width: 12px;
}

.iommu-group-label {
  color: var(--text-primary);
}

.iommu-group-devices {
  padding: 0 0 0.5rem 1.5rem;
}

.pci-device-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  margin: 0.25rem 0;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.pci-device-row--gpu {
  border-color: var(--warning-color, #f59e0b);
  background: rgba(245, 158, 11, 0.04);
}

.pci-device-row--attached {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.04);
  opacity: 0.8;
}

.pci-device-info {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.pci-id {
  font-size: 0.8rem;
}

.pci-name {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary);
}

.pci-class {
  font-size: 0.75rem;
}

.pci-device-actions {
  flex-shrink: 0;
  margin-left: 0.75rem;
}

.modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card);
  border-radius: 8px;
  width: 90%;
  max-width: 520px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 1rem;
}

.modal-body {
  padding: 1.25rem 1.5rem;
  overflow-y: auto;
  max-height: 70vh;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color);
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.4rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.alert {
  padding: 0.6rem 0.9rem;
  border-radius: 4px;
  border-left: 3px solid;
}

.alert-warning {
  background: rgba(245, 158, 11, 0.08);
  border-color: var(--warning-color, #f59e0b);
  color: var(--text-primary);
}

.form-group {
  margin-bottom: 1rem;
}

.form-label {
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
  margin-bottom: 0.35rem;
  color: var(--text-secondary);
}

.ml-1 { margin-left: 0.25rem; }
.mb-2 { margin-bottom: 0.75rem; }
.mt-2 { margin-top: 0.75rem; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.align-center { align-items: center; }
.text-sm { font-size: 0.85rem; }
.text-muted { color: var(--text-secondary); }
.text-center { text-align: center; }
</style>
