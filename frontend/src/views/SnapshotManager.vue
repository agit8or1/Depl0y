<template>
  <div class="snapshot-manager-page">
    <!-- Page Header -->
    <div class="page-header mb-3">
      <div class="page-header-left">
        <h2>
          <span v-if="singleVmMode">
            Snapshot Manager — <span class="text-accent">{{ vmName }}</span>
          </span>
          <span v-else>Cluster Snapshot Overview</span>
        </h2>
        <p class="text-muted text-sm">
          <span v-if="singleVmMode">
            {{ route.query.node }} / VMID {{ route.query.vmid }}
          </span>
          <span v-else>All snapshots across all VMs</span>
        </p>
      </div>
      <div class="page-header-right gap-2">
        <button v-if="singleVmMode" @click="openCreateSnap" class="btn btn-primary">
          + Take Snapshot
        </button>
        <button @click="refresh" class="btn btn-outline btn-sm" :disabled="loading">
          {{ loading ? 'Loading…' : 'Refresh' }}
        </button>
      </div>
    </div>

    <!-- Host / VM selector bar (when not pre-filled from query) -->
    <div v-if="!route.query.hostId" class="card mb-3">
      <div class="card-body">
        <div class="flex gap-3 flex-wrap">
          <div class="form-group" style="min-width:180px; margin:0;">
            <label class="form-label">Host</label>
            <select v-model="sel.hostId" class="form-control" @change="onHostChange">
              <option value="">— Select host —</option>
              <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
            </select>
          </div>
          <div class="form-group" style="min-width:140px; margin:0;">
            <label class="form-label">Node</label>
            <select v-model="sel.node" class="form-control" @change="onNodeChange" :disabled="!sel.hostId">
              <option value="">— Node —</option>
              <option v-for="n in nodes" :key="n.node" :value="n.node">{{ n.node }}</option>
            </select>
          </div>
          <div class="form-group" style="min-width:160px; margin:0;">
            <label class="form-label">VM / Container</label>
            <select v-model="sel.vmid" class="form-control" :disabled="!sel.node">
              <option value="">— All VMs —</option>
              <option v-for="v in allVms" :key="v.vmid" :value="String(v.vmid)">
                {{ v.vmid }} — {{ v.name || v.vmid }}
              </option>
            </select>
          </div>
          <div class="form-group" style="margin:0; align-self:flex-end;">
            <button @click="refresh" class="btn btn-primary" :disabled="!sel.hostId">Load</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading spinner -->
    <div v-if="loading" class="loading-spinner"></div>

    <!-- ─── SINGLE VM MODE ─────────────────────────────────────────────────── -->
    <template v-if="singleVmMode && !loading">
      <!-- VM Info Header -->
      <div class="card mb-3">
        <div class="card-body vm-info-header">
          <div class="vm-info-item">
            <span class="label">Name</span>
            <span class="value">{{ vmStatus.name || '—' }}</span>
          </div>
          <div class="vm-info-item">
            <span class="label">Status</span>
            <span :class="['value badge', vmStatus.status === 'running' ? 'badge-success' : 'badge-secondary']">
              {{ vmStatus.status || '—' }}
            </span>
          </div>
          <div class="vm-info-item">
            <span class="label">Node</span>
            <span class="value">{{ route.query.node }}</span>
          </div>
          <div class="vm-info-item">
            <span class="label">VMID</span>
            <span class="value">{{ route.query.vmid }}</span>
          </div>
          <div class="vm-info-item">
            <span class="label">Memory</span>
            <span class="value">{{ vmConfig.memory ? (vmConfig.memory / 1024).toFixed(1) + ' GB' : '—' }}</span>
          </div>
          <div class="vm-info-item">
            <span class="label">CPUs</span>
            <span class="value">{{ vmConfig.cores || '—' }}</span>
          </div>
        </div>
      </div>

      <!-- Compare notice -->
      <div v-if="selectedForCompare.length === 2" class="compare-bar mb-2">
        <span>2 snapshots selected — </span>
        <button @click="openCompare" class="btn btn-sm btn-warning">Compare Configs</button>
        <button @click="selectedForCompare = []" class="btn btn-sm btn-outline ml-2">Clear</button>
      </div>
      <div v-else-if="selectedForCompare.length === 1" class="compare-bar compare-bar--info mb-2">
        Select one more snapshot to compare.
      </div>

      <!-- Snapshot Tree -->
      <div class="card">
        <div class="card-header">
          <h3>Snapshots ({{ snapshots.filter(s => s.name !== 'current').length }})</h3>
          <span class="text-muted text-sm">Click a row to expand; use checkboxes to compare two snapshots</span>
        </div>

        <div v-if="snapshots.length === 0" class="empty-state">
          No snapshots found for this VM.
        </div>

        <div v-else class="snapshot-tree-wrap">
          <!-- Snapshot tree root nodes -->
          <SnapNode
            v-for="root in treeRoots"
            :key="root.name"
            :node="root"
            :all-snapshots="snapshots"
            :selected-compare="selectedForCompare"
            :acting-snap="actingSnap"
            @rollback="doRollback"
            @delete="doDelete"
            @clone="openCloneFromSnap"
            @toggle-compare="toggleCompare"
          />
        </div>
      </div>
    </template>

    <!-- ─── CLUSTER-WIDE MODE ─────────────────────────────────────────────── -->
    <template v-if="!singleVmMode && !loading">
      <!-- Bulk cleanup toolbar -->
      <div class="card mb-3">
        <div class="card-body flex gap-3 flex-wrap align-center">
          <span class="text-muted text-sm">Bulk cleanup:</span>
          <label class="form-label mb-0">Delete snapshots older than</label>
          <input v-model.number="bulkDays" type="number" min="1" class="form-control" style="width:80px;" />
          <span class="form-label mb-0">days</span>
          <button @click="previewBulkDelete" class="btn btn-warning btn-sm" :disabled="!sel.hostId">
            Preview
          </button>
          <div class="form-group mb-0" style="min-width:120px;">
            <label class="form-label mb-0">Min snapshots</label>
            <input v-model.number="filterMinSnaps" type="number" min="0" class="form-control" style="width:70px;" />
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3>VM Snapshot Summary</h3>
        </div>

        <div v-if="clusterRows.length === 0" class="empty-state">
          No VMs with snapshots found.
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>VMID</th>
                <th>Name</th>
                <th>Node</th>
                <th>Snapshots</th>
                <th>Oldest</th>
                <th>Newest</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in filteredClusterRows"
                :key="`${row.node}-${row.vmid}`"
              >
                <td>{{ row.vmid }}</td>
                <td>{{ row.name || '—' }}</td>
                <td>{{ row.node }}</td>
                <td>
                  <span :class="['badge', row.snapCount > 10 ? 'badge-warning' : 'badge-info']">
                    {{ row.snapCount }}
                  </span>
                </td>
                <td class="text-sm text-muted">{{ row.oldest ? fmtTs(row.oldest) : '—' }}</td>
                <td class="text-sm text-muted">{{ row.newest ? fmtTs(row.newest) : '—' }}</td>
                <td>
                  <router-link
                    :to="`/snapshots?hostId=${sel.hostId}&node=${row.node}&vmid=${row.vmid}`"
                    class="btn btn-outline btn-sm"
                  >
                    Manage
                  </router-link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ─── CREATE SNAPSHOT MODAL ─────────────────────────────────────────── -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Take Snapshot</h3>
          <button @click="showCreateModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Snapshot Name <span class="text-danger">*</span></label>
            <input v-model="createForm.snapname" class="form-control" placeholder="e.g. before-upgrade" />
            <p class="form-hint">Only alphanumeric + hyphens/underscores</p>
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <input v-model="createForm.description" class="form-control" placeholder="Optional description" />
          </div>
          <div class="form-group">
            <label class="toggle-label">
              <input type="checkbox" v-model="createForm.vmstate" />
              <span>Include RAM state (freeze VM while snapping)</span>
            </label>
          </div>
          <div v-if="createError" class="error-msg">{{ createError }}</div>
        </div>
        <div class="modal-footer">
          <button @click="showCreateModal = false" class="btn btn-outline">Cancel</button>
          <button @click="doCreate" class="btn btn-primary" :disabled="creating">
            {{ creating ? 'Creating…' : 'Create Snapshot' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ─── CLONE FROM SNAPSHOT MODAL ────────────────────────────────────── -->
    <div v-if="showCloneModal" class="modal-overlay" @click.self="showCloneModal = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Clone VM from Snapshot <em class="text-accent">{{ cloneForm.snapname }}</em></h3>
          <button @click="showCloneModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">New VMID <span class="text-danger">*</span></label>
            <input v-model.number="cloneForm.newid" type="number" class="form-control" />
          </div>
          <div class="form-group">
            <label class="form-label">New VM Name <span class="text-danger">*</span></label>
            <input v-model="cloneForm.name" class="form-control" />
          </div>
          <div class="form-group">
            <label class="form-label">Target Node</label>
            <select v-model="cloneForm.target" class="form-control">
              <option value="">Same node</option>
              <option v-for="n in nodes" :key="n.node" :value="n.node">{{ n.node }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="toggle-label">
              <input type="checkbox" v-model="cloneForm.full" />
              <span>Full clone (independent copy)</span>
            </label>
          </div>
          <div v-if="cloneError" class="error-msg">{{ cloneError }}</div>
        </div>
        <div class="modal-footer">
          <button @click="showCloneModal = false" class="btn btn-outline">Cancel</button>
          <button @click="doClone" class="btn btn-primary" :disabled="cloning">
            {{ cloning ? 'Cloning…' : 'Clone VM' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ─── BULK DELETE PREVIEW MODAL ────────────────────────────────────── -->
    <div v-if="showBulkModal" class="modal-overlay" @click.self="showBulkModal = false">
      <div class="modal-box modal-box--wide">
        <div class="modal-header">
          <h3>Bulk Delete Preview — Snapshots older than {{ bulkDays }} days</h3>
          <button @click="showBulkModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="bulkPreview.length === 0" class="text-muted text-sm">
            No snapshots match the criteria.
          </div>
          <div v-else>
            <p class="text-sm mb-2">
              <strong>{{ bulkPreview.length }}</strong> snapshot(s) will be deleted:
            </p>
            <div class="table-container" style="max-height:300px; overflow-y:auto;">
              <table class="table text-sm">
                <thead>
                  <tr><th>VMID</th><th>Node</th><th>Snapshot</th><th>Created</th></tr>
                </thead>
                <tbody>
                  <tr v-for="item in bulkPreview" :key="`${item.vmid}-${item.snapname}`">
                    <td>{{ item.vmid }}</td>
                    <td>{{ item.node }}</td>
                    <td><code>{{ item.snapname }}</code></td>
                    <td>{{ fmtTs(item.snaptime) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showBulkModal = false" class="btn btn-outline">Cancel</button>
          <button
            v-if="bulkPreview.length > 0"
            @click="executeBulkDelete"
            class="btn btn-danger"
            :disabled="bulkDeleting"
          >
            {{ bulkDeleting ? 'Deleting…' : `Delete ${bulkPreview.length} Snapshots` }}
          </button>
        </div>
      </div>
    </div>

    <!-- ─── SNAPSHOT CONFIG COMPARE MODAL ───────────────────────────────── -->
    <div v-if="showCompareModal" class="modal-overlay" @click.self="showCompareModal = false">
      <div class="modal-box modal-box--wide">
        <div class="modal-header">
          <h3>Config Diff: <em class="text-accent">{{ selectedForCompare[0] }}</em> vs <em class="text-accent">{{ selectedForCompare[1] }}</em></h3>
          <button @click="showCompareModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="compareLoading" class="loading-spinner"></div>
          <div v-else>
            <div class="compare-legend mb-2 text-sm flex gap-3">
              <span class="diff-changed">Changed</span>
              <span class="diff-added">Added in B</span>
              <span class="diff-removed">Removed in B</span>
              <span class="diff-same" style="cursor:pointer;" @click="showUnchanged = !showUnchanged">
                {{ showUnchanged ? 'Hide unchanged' : 'Show unchanged' }}
              </span>
            </div>
            <div class="table-container" style="max-height:500px; overflow-y:auto;">
              <table class="table text-sm compare-table">
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>{{ selectedForCompare[0] }}</th>
                    <th>{{ selectedForCompare[1] }}</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="row in diffRows" :key="row.key">
                    <tr v-if="showUnchanged || row.type !== 'same'" :class="`diff-row diff-row--${row.type}`">
                      <td><code>{{ row.key }}</code></td>
                      <td class="diff-cell-a">{{ row.a ?? '—' }}</td>
                      <td class="diff-cell-b">{{ row.b ?? '—' }}</td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showCompareModal = false" class="btn btn-outline">Close</button>
        </div>
      </div>
    </div>

    <!-- TaskProgressModal -->
    <TaskProgressModal
      :visible="!!taskUpid"
      :upid="taskUpid"
      :host-id="effectiveHostId"
      :node="effectiveNode"
      @close="taskUpid = null; refresh()"
      @success="onTaskSuccess"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, defineComponent, h } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import TaskProgressModal from '@/components/TaskProgressModal.vue'
import { useToast } from 'vue-toastification'

const route = useRoute()
const toast = useToast()

// ── State ─────────────────────────────────────────────────────────────────────
const loading = ref(false)
const hosts = ref([])
const nodes = ref([])
const allVms = ref([])
const snapshots = ref([])
const vmStatus = ref({})
const vmConfig = ref({})
const clusterRows = ref([])

const sel = ref({ hostId: '', node: '', vmid: '' })

const selectedForCompare = ref([])
const actingSnap = ref(null)

// Create snapshot modal
const showCreateModal = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = ref({ snapname: '', description: '', vmstate: false })

// Clone from snapshot modal
const showCloneModal = ref(false)
const cloning = ref(false)
const cloneError = ref('')
const cloneForm = ref({ snapname: '', newid: null, name: '', target: '', full: true })

// Bulk delete
const bulkDays = ref(30)
const filterMinSnaps = ref(0)
const showBulkModal = ref(false)
const bulkPreview = ref([])
const bulkDeleting = ref(false)

// Compare modal
const showCompareModal = ref(false)
const compareLoading = ref(false)
const compareConfigs = ref([null, null])
const showUnchanged = ref(false)

// Task progress
const taskUpid = ref(null)

// ── Computed ──────────────────────────────────────────────────────────────────

const singleVmMode = computed(() => !!effectiveVmid.value)

const effectiveHostId = computed(() =>
  route.query.hostId ? Number(route.query.hostId) : (sel.value.hostId ? Number(sel.value.hostId) : null)
)
const effectiveNode = computed(() =>
  route.query.node || sel.value.node || ''
)
const effectiveVmid = computed(() =>
  route.query.vmid ? Number(route.query.vmid) : (sel.value.vmid ? Number(sel.value.vmid) : null)
)

const vmName = computed(() => vmStatus.value?.name || vmConfig.value?.name || `VM ${effectiveVmid.value}`)

// Build hierarchical snapshot tree
const treeRoots = computed(() => {
  const snaps = snapshots.value.filter(s => s.name !== 'current')
  const map = {}
  snaps.forEach(s => { map[s.name] = { ...s, children: [] } })
  const roots = []
  snaps.forEach(s => {
    if (s.parent && map[s.parent]) {
      map[s.parent].children.push(map[s.name])
    } else {
      roots.push(map[s.name])
    }
  })
  return roots
})

const filteredClusterRows = computed(() =>
  clusterRows.value.filter(r => r.snapCount >= filterMinSnaps.value)
)

const diffRows = computed(() => {
  const [cfgA, cfgB] = compareConfigs.value
  if (!cfgA || !cfgB) return []
  const keys = new Set([...Object.keys(cfgA), ...Object.keys(cfgB)])
  const rows = []
  const SKIP = new Set(['digest'])
  keys.forEach(k => {
    if (SKIP.has(k)) return
    const a = cfgA[k]
    const b = cfgB[k]
    let type = 'same'
    if (a === undefined) type = 'added'
    else if (b === undefined) type = 'removed'
    else if (JSON.stringify(a) !== JSON.stringify(b)) type = 'changed'
    rows.push({ key: k, a, b, type })
  })
  rows.sort((x, y) => {
    const order = { changed: 0, added: 1, removed: 2, same: 3 }
    return (order[x.type] - order[y.type]) || x.key.localeCompare(y.key)
  })
  return rows
})

// ── Methods ───────────────────────────────────────────────────────────────────

function fmtTs(ts) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString()
}

async function loadHosts() {
  try {
    const res = await api.proxmox.listHosts()
    hosts.value = res.data || []
    if (route.query.hostId) {
      sel.value.hostId = Number(route.query.hostId)
      await onHostChange()
    }
  } catch (e) {
    console.error(e)
  }
}

async function onHostChange() {
  nodes.value = []
  allVms.value = []
  sel.value.node = route.query.node || ''
  if (!effectiveHostId.value) return
  try {
    const res = await api.proxmox.listNodes(effectiveHostId.value)
    nodes.value = res.data || []
    if (sel.value.node) await onNodeChange()
  } catch (e) {
    console.error(e)
  }
}

async function onNodeChange() {
  allVms.value = []
  if (!effectiveHostId.value || !effectiveNode.value) return
  try {
    const res = await api.pveNode.nodeVms(effectiveHostId.value, effectiveNode.value)
    const vms = res.data?.vms || []
    const cts = res.data?.containers || []
    allVms.value = [...vms, ...cts]
  } catch (e) {
    console.error(e)
  }
}

async function refresh() {
  if (!effectiveHostId.value) return
  loading.value = true
  try {
    if (singleVmMode.value) {
      await loadSingleVm()
    } else {
      await loadClusterWide()
    }
  } finally {
    loading.value = false
  }
}

async function loadSingleVm() {
  const h = effectiveHostId.value
  const node = effectiveNode.value
  const vmid = effectiveVmid.value
  try {
    const [snapRes, statusRes, configRes] = await Promise.allSettled([
      api.pveVm.listSnapshots(h, node, vmid),
      api.pveVm.getStatus(h, node, vmid),
      api.pveVm.getConfig(h, node, vmid),
    ])
    snapshots.value = snapRes.status === 'fulfilled' ? (snapRes.value.data || []) : []
    vmStatus.value = statusRes.status === 'fulfilled' ? (statusRes.value.data || {}) : {}
    vmConfig.value = configRes.status === 'fulfilled' ? (configRes.value.data || {}) : {}
  } catch (e) {
    console.error(e)
  }
}

async function loadClusterWide() {
  if (!effectiveHostId.value) return
  const rows = []
  try {
    const nodesRes = await api.proxmox.listNodes(effectiveHostId.value)
    const nodeList = (nodesRes.data || []).map(n => n.node)
    for (const node of nodeList) {
      try {
        const vmsRes = await api.pveNode.nodeVms(effectiveHostId.value, node)
        const vms = [...(vmsRes.data?.vms || []), ...(vmsRes.data?.containers || [])]
        for (const vm of vms) {
          try {
            let snapsRes
            if (vm.type === 'lxc') {
              snapsRes = await api.pveNode.listContainerSnapshots(effectiveHostId.value, node, vm.vmid)
            } else {
              snapsRes = await api.pveVm.listSnapshots(effectiveHostId.value, node, vm.vmid)
            }
            const snaps = (snapsRes.data || []).filter(s => s.name !== 'current')
            if (snaps.length > 0) {
              const times = snaps.map(s => s.snaptime || 0).filter(Boolean)
              rows.push({
                vmid: vm.vmid,
                name: vm.name,
                node,
                type: vm.type || 'qemu',
                snapCount: snaps.length,
                oldest: times.length ? Math.min(...times) : null,
                newest: times.length ? Math.max(...times) : null,
                snaps,
              })
            }
          } catch (e) { /* skip */ }
        }
      } catch (e) { /* skip */ }
    }
  } catch (e) {
    console.error(e)
  }
  clusterRows.value = rows
  if (!sel.value.hostId && effectiveHostId.value) {
    sel.value.hostId = effectiveHostId.value
    const nodesRes = await api.proxmox.listNodes(effectiveHostId.value)
    nodes.value = nodesRes.data || []
  }
}

function openCreateSnap() {
  createForm.value = { snapname: '', description: '', vmstate: false }
  createError.value = ''
  showCreateModal.value = true
}

async function doCreate() {
  if (!createForm.value.snapname) {
    createError.value = 'Snapshot name is required.'
    return
  }
  creating.value = true
  createError.value = ''
  try {
    const res = await api.pveVm.createSnapshot(
      effectiveHostId.value,
      effectiveNode.value,
      effectiveVmid.value,
      createForm.value
    )
    showCreateModal.value = false
    taskUpid.value = res.data?.upid
    toast.success('Snapshot task started')
  } catch (e) {
    createError.value = e.response?.data?.detail || String(e)
  } finally {
    creating.value = false
  }
}

async function doRollback(snapname) {
  if (!confirm(`Roll back VM to snapshot "${snapname}"?\n\nWARNING: All changes since this snapshot will be lost unless you have saved them as a newer snapshot.`)) return
  actingSnap.value = snapname
  try {
    const res = await api.pveVm.rollbackSnapshot(
      effectiveHostId.value,
      effectiveNode.value,
      effectiveVmid.value,
      snapname
    )
    taskUpid.value = res.data?.upid
    toast.success('Rollback task started')
  } catch (e) {
    toast.error(e.response?.data?.detail || String(e))
  } finally {
    actingSnap.value = null
  }
}

async function doDelete(snapname, hasChildren) {
  if (hasChildren) {
    alert(`Cannot delete snapshot "${snapname}" — it has child snapshots. Delete children first.`)
    return
  }
  if (!confirm(`Delete snapshot "${snapname}"?`)) return
  actingSnap.value = snapname
  try {
    const res = await api.pveVm.deleteSnapshot(
      effectiveHostId.value,
      effectiveNode.value,
      effectiveVmid.value,
      snapname
    )
    taskUpid.value = res.data?.upid
    toast.success('Delete task started')
  } catch (e) {
    toast.error(e.response?.data?.detail || String(e))
  } finally {
    actingSnap.value = null
  }
}

async function openCloneFromSnap(snapname) {
  // get next free vmid
  let nextId = null
  try {
    const res = await api.pveNode.nextId(effectiveHostId.value)
    nextId = res.data?.vmid
  } catch (e) { /* ignore */ }
  cloneForm.value = {
    snapname,
    newid: nextId,
    name: `clone-from-${snapname}`,
    target: '',
    full: true,
  }
  cloneError.value = ''
  showCloneModal.value = true
}

async function doClone() {
  if (!cloneForm.value.newid || !cloneForm.value.name) {
    cloneError.value = 'New VMID and Name are required.'
    return
  }
  cloning.value = true
  cloneError.value = ''
  try {
    const params = {
      newid: cloneForm.value.newid,
      name: cloneForm.value.name,
      full: cloneForm.value.full,
      snapname: cloneForm.value.snapname,
    }
    if (cloneForm.value.target) params.target = cloneForm.value.target
    const res = await api.pveVm.clone(
      effectiveHostId.value,
      effectiveNode.value,
      effectiveVmid.value,
      params
    )
    showCloneModal.value = false
    taskUpid.value = res.data?.upid
    toast.success('Clone task started')
  } catch (e) {
    cloneError.value = e.response?.data?.detail || String(e)
  } finally {
    cloning.value = false
  }
}

function toggleCompare(snapname) {
  const idx = selectedForCompare.value.indexOf(snapname)
  if (idx >= 0) {
    selectedForCompare.value.splice(idx, 1)
  } else if (selectedForCompare.value.length < 2) {
    selectedForCompare.value.push(snapname)
  } else {
    // Replace oldest
    selectedForCompare.value.shift()
    selectedForCompare.value.push(snapname)
  }
}

async function openCompare() {
  showCompareModal.value = true
  compareLoading.value = true
  showUnchanged.value = false
  try {
    const [r1, r2] = await Promise.all([
      api.pveVm.getSnapshotConfig(effectiveHostId.value, effectiveNode.value, effectiveVmid.value, selectedForCompare.value[0]),
      api.pveVm.getSnapshotConfig(effectiveHostId.value, effectiveNode.value, effectiveVmid.value, selectedForCompare.value[1]),
    ])
    compareConfigs.value = [r1.data || {}, r2.data || {}]
  } catch (e) {
    toast.error('Failed to load snapshot configs: ' + (e.response?.data?.detail || String(e)))
    showCompareModal.value = false
  } finally {
    compareLoading.value = false
  }
}

async function previewBulkDelete() {
  if (!effectiveHostId.value) return
  const cutoff = Date.now() / 1000 - bulkDays.value * 86400
  const preview = []
  for (const row of clusterRows.value) {
    for (const snap of row.snaps || []) {
      if (snap.snaptime && snap.snaptime < cutoff && snap.name !== 'current') {
        preview.push({ vmid: row.vmid, node: row.node, type: row.type, snapname: snap.name, snaptime: snap.snaptime })
      }
    }
  }
  bulkPreview.value = preview
  showBulkModal.value = true
}

async function executeBulkDelete() {
  bulkDeleting.value = true
  let deleted = 0
  let errors = 0
  for (const item of bulkPreview.value) {
    try {
      if (item.type === 'lxc') {
        await api.pveNode.deleteContainerSnapshot(effectiveHostId.value, item.node, item.vmid, item.snapname)
      } else {
        await api.pveVm.deleteSnapshot(effectiveHostId.value, item.node, item.vmid, item.snapname)
      }
      deleted++
    } catch (e) {
      errors++
    }
  }
  bulkDeleting.value = false
  showBulkModal.value = false
  toast.success(`Bulk delete: ${deleted} deleted, ${errors} errors`)
  await loadClusterWide()
}

function onTaskSuccess() {
  taskUpid.value = null
  refresh()
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadHosts()
  if (effectiveHostId.value) {
    await refresh()
  }
})

watch(() => route.query, async () => {
  await loadHosts()
  if (effectiveHostId.value) await refresh()
}, { deep: true })
</script>

<!-- ─── SnapNode sub-component defined inline ──────────────────────────────── -->
<script>
// Recursive snapshot tree node component
import { defineComponent, h, ref } from 'vue'

export const SnapNode = defineComponent({
  name: 'SnapNode',
  props: {
    node: Object,
    allSnapshots: Array,
    selectedCompare: Array,
    actingSnap: String,
  },
  emits: ['rollback', 'delete', 'clone', 'toggleCompare'],
  setup(props, { emit }) {
    const expanded = ref(true)

    function fmtTs(ts) {
      if (!ts) return '—'
      return new Date(ts * 1000).toLocaleString()
    }

    function renderNode(snap, depth = 0) {
      const isChecked = props.selectedCompare?.includes(snap.name) ?? false
      const isActing = props.actingSnap === snap.name
      const hasChildren = (snap.children || []).length > 0

      return h('div', { class: 'snap-node', style: `padding-left: ${depth * 1.5}rem` }, [
        h('div', { class: ['snap-row', isChecked ? 'snap-row--selected' : ''] }, [
          // expand toggle
          h('span', {
            class: ['snap-toggle', hasChildren ? 'snap-toggle--active' : 'snap-toggle--empty'],
            onClick: () => { if (hasChildren) expanded.value = !expanded.value }
          }, hasChildren ? (expanded.value ? '▼' : '▶') : '·'),

          // compare checkbox
          h('input', {
            type: 'checkbox',
            class: 'snap-check',
            checked: isChecked,
            onChange: () => emit('toggleCompare', snap.name),
          }),

          // info
          h('div', { class: 'snap-info' }, [
            h('span', { class: 'snap-name' }, snap.name),
            snap.description ? h('span', { class: 'snap-desc text-muted' }, ' — ' + snap.description) : null,
            h('span', { class: 'snap-time text-muted text-xs' }, ' · ' + fmtTs(snap.snaptime)),
            snap.vmstate ? h('span', { class: 'badge badge-info snap-badge' }, 'RAM') : null,
          ]),

          // actions
          h('div', { class: 'snap-actions' }, [
            h('button', {
              class: 'btn btn-warning btn-xs',
              disabled: isActing,
              onClick: () => emit('rollback', snap.name),
            }, isActing ? '…' : 'Rollback'),
            h('button', {
              class: 'btn btn-outline btn-xs',
              disabled: isActing,
              onClick: () => emit('clone', snap.name),
            }, 'Clone VM'),
            h('button', {
              class: 'btn btn-danger btn-xs',
              disabled: isActing || hasChildren,
              title: hasChildren ? 'Has child snapshots — delete children first' : 'Delete',
              onClick: () => emit('delete', snap.name, hasChildren),
            }, 'Delete'),
          ]),
        ]),

        // children
        expanded.value && hasChildren
          ? h('div', { class: 'snap-children' },
              snap.children.map(child => renderNode(child, depth + 1))
            )
          : null,
      ])
    }

    return () => renderNode(props.node)
  }
})
</script>

<style scoped>
/* ── Layout ────────────────────────────────────────────────── */
.snapshot-manager-page {
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem;
}

.page-header-right {
  display: flex;
  align-items: center;
}

.text-accent { color: var(--primary-color, #3b82f6); }
.text-xs { font-size: 0.75rem; }

/* ── VM info header ────────────────────────────────────────── */
.vm-info-header {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
}

.vm-info-item {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.vm-info-item .label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.vm-info-item .value {
  font-weight: 600;
  font-size: 0.9rem;
}

/* ── Compare bar ───────────────────────────────────────────── */
.compare-bar {
  background: rgba(234, 179, 8, 0.12);
  border: 1px solid rgba(234, 179, 8, 0.3);
  border-radius: 0.375rem;
  padding: 0.6rem 1rem;
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.compare-bar--info {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.3);
}

/* ── Snapshot tree ─────────────────────────────────────────── */
.snapshot-tree-wrap {
  padding: 0.75rem 1rem;
}

.snap-node {
  margin-bottom: 0.25rem;
}

.snap-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  transition: background 0.1s;
}

.snap-row:hover {
  background: rgba(255,255,255,0.04);
}

.snap-row--selected {
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.snap-toggle {
  width: 1.2rem;
  cursor: pointer;
  font-size: 0.7rem;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.snap-toggle--active { color: var(--text-primary); }

.snap-check {
  flex-shrink: 0;
  cursor: pointer;
}

.snap-info {
  flex: 1;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.snap-name {
  font-weight: 600;
  font-family: monospace;
  font-size: 0.9rem;
}

.snap-desc { font-size: 0.8rem; }
.snap-time { font-size: 0.75rem; }

.snap-badge {
  font-size: 0.65rem;
  padding: 0.1rem 0.4rem;
}

.snap-actions {
  display: flex;
  gap: 0.4rem;
  flex-shrink: 0;
}

.btn-xs {
  padding: 0.2rem 0.55rem;
  font-size: 0.75rem;
  border-radius: 0.25rem;
}

.snap-children {
  margin-left: 0.5rem;
  border-left: 2px solid var(--border-color);
  padding-left: 0.5rem;
}

/* ── Badges ────────────────────────────────────────────────── */
.badge {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
}

.badge-success  { background: rgba(34,197,94,.15); color: #4ade80; border: 1px solid rgba(34,197,94,.3); }
.badge-secondary{ background: rgba(148,163,184,.15); color: #94a3b8; border: 1px solid rgba(148,163,184,.3); }
.badge-info     { background: rgba(59,130,246,.15); color: #60a5fa; border: 1px solid rgba(59,130,246,.3); }
.badge-warning  { background: rgba(234,179,8,.15); color: #facc15; border: 1px solid rgba(234,179,8,.3); }
.badge-danger   { background: rgba(239,68,68,.15); color: #f87171; border: 1px solid rgba(239,68,68,.3); }

/* ── Cards ─────────────────────────────────────────────────── */
.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
}

.card-header {
  padding: 0.875rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 { margin: 0; font-size: 1rem; }

.card-body {
  padding: 1rem 1.25rem;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary);
}

/* ── Form helpers ──────────────────────────────────────────── */
.form-group { margin-bottom: 1rem; }
.form-label { display: block; margin-bottom: 0.35rem; font-size: 0.85rem; font-weight: 500; }
.form-hint  { font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem; }

.form-control {
  width: 100%;
  padding: 0.45rem 0.75rem;
  background: var(--bg-tertiary, #0d0d1a);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  color: var(--text-primary);
  font-size: 0.875rem;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
}

/* ── Buttons ───────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.15s;
}

.btn-primary  { background: var(--primary-color, #3b82f6); color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-warning  { background: rgba(234,179,8,.2); color: #facc15; border-color: rgba(234,179,8,.4); }
.btn-warning:hover { background: rgba(234,179,8,.3); }
.btn-danger   { background: rgba(239,68,68,.2); color: #f87171; border-color: rgba(239,68,68,.3); }
.btn-danger:hover { background: rgba(239,68,68,.3); }
.btn-outline  { background: transparent; border-color: var(--border-color); color: var(--text-primary); }
.btn-outline:hover { background: var(--bg-tertiary, rgba(255,255,255,.06)); }
.btn-sm { padding: 0.3rem 0.75rem; font-size: 0.8rem; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Modal ─────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  width: 500px;
  max-width: 95vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-box--wide {
  width: 850px;
}

.modal-header {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 { margin: 0; font-size: 1rem; }

.modal-close {
  background: none;
  border: none;
  font-size: 1.4rem;
  cursor: pointer;
  color: var(--text-secondary);
}

.modal-body {
  padding: 1.25rem;
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  padding: 0.875rem 1.25rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.error-msg {
  background: rgba(239,68,68,.1);
  border: 1px solid rgba(239,68,68,.3);
  border-radius: 0.375rem;
  padding: 0.6rem 0.9rem;
  color: #f87171;
  font-size: 0.85rem;
  margin-top: 0.5rem;
}

/* ── Compare table ─────────────────────────────────────────── */
.compare-legend span {
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  cursor: default;
}

.diff-same     { color: var(--text-secondary); }
.diff-changed  { background: rgba(234,179,8,.2); color: #facc15; }
.diff-added    { background: rgba(34,197,94,.15); color: #4ade80; }
.diff-removed  { background: rgba(239,68,68,.15); color: #f87171; }

.compare-table tbody tr td { vertical-align: top; word-break: break-all; font-size: 0.8rem; }

.diff-row--changed td { background: rgba(234,179,8,.07); }
.diff-row--added   td { background: rgba(34,197,94,.07); }
.diff-row--removed td { background: rgba(239,68,68,.07); }
.diff-row--same    td { opacity: 0.7; }

/* ── Table ─────────────────────────────────────────────────── */
.table-container { overflow-x: auto; }

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.table th, .table td {
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border-color);
  text-align: left;
}

.table th {
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 0.78rem;
  text-transform: uppercase;
}

/* ── Misc ──────────────────────────────────────────────────── */
.mb-2 { margin-bottom: 0.75rem; }
.mb-3 { margin-bottom: 1rem; }
.flex { display: flex; }
.gap-2 { gap: 0.75rem; }
.gap-3 { gap: 1rem; }
.flex-wrap { flex-wrap: wrap; }
.align-center { align-items: center; }
.ml-2 { margin-left: 0.5rem; }
.mb-0 { margin-bottom: 0; }
.text-muted { color: var(--text-secondary); }
.text-sm { font-size: 0.875rem; }
.text-danger { color: #f87171; }

.loading-spinner {
  width: 2rem;
  height: 2rem;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color, #3b82f6);
  border-radius: 50%;
  animation: spin .7s linear infinite;
  margin: 2rem auto;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
