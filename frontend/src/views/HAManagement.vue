<template>
  <div class="ha-management">
    <div class="page-header">
      <div>
        <h1>High Availability Management</h1>
        <p class="text-muted">Manage Proxmox HA resources and monitor cluster failover status</p>
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
          <option
            v-for="host in hosts"
            :key="host.id"
            :value="host.id"
          >
            {{ host.name }} — {{ host.address }}
          </option>
        </select>

        <!-- HA Status Badge -->
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

    <!-- No host selected placeholder -->
    <div v-if="!selectedHostId" class="card empty-placeholder">
      <p class="text-muted">Select a Proxmox host above to view HA configuration.</p>
    </div>

    <template v-else>

      <!-- ─── Task 3: HA Status Panel ──────────────────────────────────────── -->
      <div class="card ha-status-panel">
        <div class="card-header">
          <h2>HA Cluster Status</h2>
          <div class="ha-toggle-wrap">
            <span class="toggle-label">HA Enabled</span>
            <button
              :class="['toggle-btn', haEnabled ? 'toggle-on' : 'toggle-off']"
              :disabled="togglingHa"
              @click="requestHaToggle"
              :title="haEnabled ? 'Click to disable HA' : 'Click to enable HA'"
            >
              <span class="toggle-knob"></span>
            </button>
          </div>
        </div>

        <div v-if="loadingStatus" class="loading-state loading-state-sm">Loading cluster status...</div>

        <div v-else class="status-grid">
          <!-- Quorum -->
          <div class="status-item">
            <span class="status-item-label">Quorum</span>
            <span :class="['badge', quorumBadgeClass]">{{ quorumDisplay }}</span>
          </div>

          <!-- Fence Device -->
          <div class="status-item">
            <span class="status-item-label">Fence Device</span>
            <span v-if="fenceStatus" :class="['badge', fenceBadgeClass]">{{ fenceStatus }}</span>
            <span v-else class="text-muted text-sm">Not configured</span>
          </div>

          <!-- Last HA Event -->
          <div class="status-item">
            <span class="status-item-label">Last HA Event</span>
            <span v-if="lastHaEvent" class="last-event-text" :title="lastHaEvent">{{ lastHaEvent }}</span>
            <span v-else class="text-muted text-sm">None recorded</span>
          </div>

          <!-- Poll indicator -->
          <div class="status-item">
            <span class="status-item-label">Live Polling</span>
            <span :class="['badge', pollActive ? 'badge-success' : 'badge-secondary']">
              {{ pollActive ? 'Every 10s' : 'Paused' }}
            </span>
          </div>
        </div>
      </div>

      <!-- ─── HA Toggle Confirm Dialog ───────────────────────────────────────── -->
      <div v-if="showHaToggleConfirm" class="modal" @click.self="showHaToggleConfirm = false">
        <div class="modal-content modal-sm">
          <div class="modal-header">
            <h3>{{ haEnabled ? 'Disable HA?' : 'Enable HA?' }}</h3>
            <button @click="showHaToggleConfirm = false" class="btn-close">&times;</button>
          </div>
          <div class="modal-body">
            <p v-if="haEnabled">
              Disabling HA will stop automatic failover for all protected resources.
              VMs will no longer migrate automatically on node failure.
            </p>
            <p v-else>
              Enabling HA will allow the cluster to automatically migrate and restart
              protected VMs when a node fails.
            </p>
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
        <button
          :class="['tab-btn', activeTab === 'resources' ? 'tab-active' : '']"
          @click="activeTab = 'resources'"
        >
          Resources
          <span v-if="haResources.length" class="tab-count">{{ haResources.length }}</span>
        </button>
        <button
          :class="['tab-btn', activeTab === 'groups' ? 'tab-active' : '']"
          @click="activeTab = 'groups'"
        >
          Groups
          <span v-if="haGroups.length" class="tab-count">{{ haGroups.length }}</span>
        </button>
      </div>

      <!-- ─── Task 1: Resources Tab ──────────────────────────────────────────── -->
      <div v-if="activeTab === 'resources'" class="card">
        <div class="card-header">
          <h2>HA Resources</h2>
          <button @click="showAddModal = true" class="btn btn-primary">+ Add Resource</button>
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
                <th>SID (Resource ID)</th>
                <th>Type</th>
                <th>Group</th>
                <th>Configured State</th>
                <th>Live State</th>
                <th>Current Node</th>
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
                <!-- Live state from poll -->
                <td>
                  <span
                    v-if="liveStatus[resource.sid]"
                    :class="['badge', resourceStateBadge(liveStatus[resource.sid].state)]"
                  >
                    {{ liveStatus[resource.sid].state }}
                  </span>
                  <span v-else class="text-muted text-sm">—</span>
                </td>
                <!-- Current node -->
                <td>
                  <span v-if="liveStatus[resource.sid]?.node" class="node-chip">
                    {{ liveStatus[resource.sid].node }}
                  </span>
                  <span v-else class="text-muted text-sm">—</span>
                </td>
                <!-- Last state change -->
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

      <!-- ─── Task 2: Groups Tab ─────────────────────────────────────────────── -->
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
                <th>Nodes</th>
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

    </template>

    <!-- ─── Add Resource Modal ──────────────────────────────────────────────── -->
    <div v-if="showAddModal" class="modal" @click.self="showAddModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Add HA Resource</h3>
          <button @click="showAddModal = false" class="btn-close">&times;</button>
        </div>
        <form @submit.prevent="addResource" class="modal-body">
          <div class="form-group">
            <label class="form-label">Resource SID <span class="required">*</span></label>
            <input
              v-model="newResource.sid"
              class="form-control"
              placeholder="e.g. vm:100 or ct:200"
              required
            />
            <p class="field-hint">Format: <code>vm:&lt;vmid&gt;</code> or <code>ct:&lt;vmid&gt;</code></p>
          </div>

          <div class="form-group">
            <label class="form-label">HA Group</label>
            <select v-model="newResource.group" class="form-control">
              <option value="">— None —</option>
              <option v-for="g in haGroups" :key="g.group" :value="g.group">
                {{ g.group }}
              </option>
            </select>
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

    <!-- ─── Create Group Modal ─────────────────────────────────────────────── -->
    <div v-if="showCreateGroupModal" class="modal" @click.self="showCreateGroupModal = false">
      <div class="modal-content">
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
            <label class="form-label">Nodes <span class="required">*</span></label>
            <p class="field-hint">Select nodes that can run resources in this group.</p>
            <div v-if="clusterNodes.length === 0" class="text-muted text-sm">
              No cluster nodes found — enter manually below.
            </div>
            <div v-else class="node-selector">
              <div
                v-for="node in clusterNodes"
                :key="node"
                :class="['node-option', newGroupSelectedNodes.includes(node) ? 'node-option-selected' : '']"
                @click="toggleGroupNode(node)"
              >
                <span class="node-check">{{ newGroupSelectedNodes.includes(node) ? '✓' : '' }}</span>
                {{ node }}
              </div>
            </div>
            <input
              v-model="newGroup.nodes"
              class="form-control"
              :placeholder="clusterNodes.length ? 'Or type: node1:1,node2:2' : 'e.g. node1:1,node2:2'"
              :class="{ 'mt-sm': clusterNodes.length > 0 }"
            />
            <p class="field-hint">Optionally append <code>:&lt;priority&gt;</code> for failover ordering (higher = preferred).</p>
          </div>

          <div class="form-row">
            <div class="form-group checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="newGroup.nofailback" class="checkbox-input" />
                No Failback
              </label>
              <p class="field-hint">Do not move resources back when the preferred node comes back online.</p>
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
  pollTimer = setInterval(() => {
    pollLiveStatus()
  }, 10000)
}

const stopPoll = () => {
  pollActive.value = false
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// ── Task 1: Live resource status ──────────────────────────────────────────────
// liveStatus is keyed by SID: { state, node, last_change, last_change_iso }
const liveStatus = ref({})

const pollLiveStatus = async () => {
  if (!selectedHostId.value) return
  try {
    const response = await api.pveNode.haStatus(selectedHostId.value)
    const data = response.data
    const newLive = {}

    // PVE returns an array from cluster/ha/status/manager_status or similar
    const entries = Array.isArray(data) ? data : (data ? [data] : [])

    for (const entry of entries) {
      // Resources appear with a sid field
      if (entry.sid) {
        newLive[entry.sid] = {
          state: entry.state ?? entry.status ?? 'unknown',
          node: entry.node ?? '',
          last_change: entry.crm_state_change ? formatRelativeTime(entry.crm_state_change) : '',
          last_change_iso: entry.crm_state_change ? new Date(entry.crm_state_change * 1000).toLocaleString() : '',
        }
      }
      // Also pick up manager status for the panel
      if (entry.type === 'manager' || entry.id === 'manager') {
        if (!haManagerStatus.value) {
          haManagerStatus.value = entry.status ?? entry.state ?? ''
        }
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

// ── Task 3: HA Status Panel ───────────────────────────────────────────────────
const haManagerStatus = ref('')
const loadingStatus = ref(false)
const statusError = ref(null)

// Quorum and fence from clusterStatus
const quorumOk = ref(null)      // true/false/null
const fenceStatus = ref('')     // string or ''
const lastHaEvent = ref('')
const haEnabled = ref(true)

const quorumDisplay = computed(() => {
  if (quorumOk.value === null) return 'Unknown'
  return quorumOk.value ? 'OK' : 'No Quorum'
})

const quorumBadgeClass = computed(() => {
  if (quorumOk.value === null) return 'badge-secondary'
  return quorumOk.value ? 'badge-success' : 'badge-danger'
})

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

const loadHaStatus = async () => {
  if (!selectedHostId.value) return
  loadingStatus.value = true
  statusError.value = null
  haManagerStatus.value = ''
  quorumOk.value = null
  fenceStatus.value = ''
  lastHaEvent.value = ''

  try {
    // Load cluster status for quorum, fence, HA enabled
    const csResp = await api.pveNode.clusterStatus(selectedHostId.value)
    const csData = Array.isArray(csResp.data) ? csResp.data : []

    for (const item of csData) {
      // Quorum node entry
      if (item.type === 'quorum' || item.id === 'quorum') {
        quorumOk.value = !!(item.quorate ?? item.quorum_ok ?? (item.flags && item.flags.includes('quorate')))
      }
      // Cluster node — check quorate flag on cluster entry
      if (item.type === 'cluster') {
        if ('quorate' in item) quorumOk.value = !!item.quorate
        if (item.nodes !== undefined && quorumOk.value === null) {
          // Fallback: quorum is met if we can talk to cluster
          quorumOk.value = true
        }
      }
      // Fence / storage fence devices
      if (item.type === 'fence' || (item.name && item.name.includes('fence'))) {
        fenceStatus.value = item.status ?? item.state ?? 'configured'
      }
    }

    // If we got cluster data but no quorum entry, assume ok
    if (csData.length > 0 && quorumOk.value === null) {
      quorumOk.value = true
    }

    // HA manager status
    const haResp = await api.pveNode.haStatus(selectedHostId.value)
    const haData = haResp.data
    const haArr = Array.isArray(haData) ? haData : (haData ? [haData] : [])

    for (const entry of haArr) {
      if (entry.type === 'manager' || entry.id === 'manager' || 'status' in entry) {
        haManagerStatus.value = entry.status ?? entry.state ?? haManagerStatus.value
        haEnabled.value = haManagerStatus.value !== 'disabled'

        // Last HA event from crm_commands or similar
        if (entry.timestamp || entry.crm_state_change) {
          const ts = entry.timestamp ?? entry.crm_state_change
          lastHaEvent.value = `Status changed to "${haManagerStatus.value}" — ${new Date(ts * 1000).toLocaleString()}`
        }
        break
      }
    }

    // Also trigger live resource state population
    await pollLiveStatus()

  } catch (err) {
    statusError.value = err.response?.data?.detail || 'Failed to load HA status'
    console.error('Failed to load HA status:', err)
  } finally {
    loadingStatus.value = false
  }
}

// ── HA Enable/Disable toggle ──────────────────────────────────────────────────
const showHaToggleConfirm = ref(false)
const togglingHa = ref(false)

const requestHaToggle = () => {
  showHaToggleConfirm.value = true
}

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
    const msg = err.response?.data?.detail || 'Failed to toggle HA'
    toast.error(msg)
  } finally {
    togglingHa.value = false
  }
}

// ── Task 1: HA Resources ──────────────────────────────────────────────────────
const haResources = ref([])
const loadingResources = ref(false)
const resourceError = ref(null)
const deletingSid = ref(null)

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
    started:   'badge-success',
    enabled:   'badge-success',
    running:   'badge-success',
    stopped:   'badge-danger',
    disabled:  'badge-secondary',
    error:     'badge-danger',
    fence:     'badge-danger',
    migrate:   'badge-info',
    migrating: 'badge-info',
    relocate:  'badge-info',
    recovery:  'badge-warning',
    freeze:    'badge-warning',
  }
  return map[(state || '').toLowerCase()] || 'badge-secondary'
}

// ── Task 2: HA Groups ─────────────────────────────────────────────────────────
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
    console.error('Failed to load HA groups:', err)
  } finally {
    loadingGroups.value = false
  }
}

const loadClusterNodes = async () => {
  if (!selectedHostId.value) return
  try {
    const resp = await api.pveNode.clusterStatus(selectedHostId.value)
    const data = Array.isArray(resp.data) ? resp.data : []
    clusterNodes.value = data
      .filter(e => e.type === 'node')
      .map(e => e.name)
      .filter(Boolean)
  } catch (err) {
    console.warn('Could not load cluster nodes for group selector:', err)
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
const newResource = ref({
  sid: '',
  group: '',
  max_restart: 1,
  max_relocate: 1,
  comment: ''
})

const resetNewResource = () => {
  newResource.value = { sid: '', group: '', max_restart: 1, max_relocate: 1, comment: '' }
}

const addResource = async () => {
  saving.value = true
  try {
    const payload = { ...newResource.value }
    Object.keys(payload).forEach(k => {
      if (payload[k] === '' || payload[k] === null || payload[k] === undefined) delete payload[k]
    })
    await api.pveNode.addHaResource(selectedHostId.value, payload)
    toast.success(`HA resource ${payload.sid} added`)
    showAddModal.value = false
    resetNewResource()
    await loadHaResources()
  } catch (err) {
    const msg = err.response?.data?.detail || 'Failed to add HA resource'
    toast.error(msg)
    console.error('Failed to add HA resource:', err)
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
    await loadHaResources()
  } catch (err) {
    const msg = err.response?.data?.detail || 'Failed to remove HA resource'
    toast.error(msg)
    console.error('Failed to remove HA resource:', err)
  } finally {
    deletingSid.value = null
  }
}

// ── Create Group Modal ────────────────────────────────────────────────────────
const showCreateGroupModal = ref(false)
const savingGroup = ref(false)
const newGroupSelectedNodes = ref([])
const newGroup = ref({
  group: '',
  nodes: '',
  nofailback: false,
  restricted: false,
  comment: ''
})

const resetNewGroup = () => {
  newGroup.value = { group: '', nodes: '', nofailback: false, restricted: false, comment: '' }
  newGroupSelectedNodes.value = []
}

const openCreateGroupModal = () => {
  resetNewGroup()
  loadClusterNodes()
  showCreateGroupModal.value = true
}

const toggleGroupNode = (node) => {
  const idx = newGroupSelectedNodes.value.indexOf(node)
  if (idx === -1) {
    newGroupSelectedNodes.value.push(node)
  } else {
    newGroupSelectedNodes.value.splice(idx, 1)
  }
  // Sync to nodes field
  if (newGroupSelectedNodes.value.length > 0) {
    newGroup.value.nodes = newGroupSelectedNodes.value.join(',')
  } else {
    newGroup.value.nodes = ''
  }
}

const createGroup = async () => {
  if (!newGroup.value.group) {
    toast.error('Group ID is required')
    return
  }
  if (!newGroup.value.nodes) {
    toast.error('At least one node must be specified')
    return
  }
  savingGroup.value = true
  try {
    const payload = {
      group: newGroup.value.group,
      nodes: newGroup.value.nodes,
    }
    if (newGroup.value.nofailback) payload.nofailback = 1
    if (newGroup.value.restricted) payload.restricted = 1
    if (newGroup.value.comment) payload.comment = newGroup.value.comment

    await api.pveNode.createHaGroup(selectedHostId.value, payload)
    toast.success(`HA group "${payload.group}" created`)
    showCreateGroupModal.value = false
    resetNewGroup()
    await loadHaGroups()
  } catch (err) {
    const msg = err.response?.data?.detail || 'Failed to create HA group'
    toast.error(msg)
    console.error('Failed to create HA group:', err)
  } finally {
    savingGroup.value = false
  }
}

// ── Delete Group ──────────────────────────────────────────────────────────────
const confirmDeleteGroup = async (groupId) => {
  if (!confirm(`Delete HA group "${groupId}"?\n\nResources assigned to this group will no longer have group-based failover preferences.`)) return
  deletingGroup.value = groupId
  try {
    await api.pveNode.deleteHaGroup(selectedHostId.value, groupId)
    toast.success(`HA group "${groupId}" deleted`)
    await loadHaGroups()
  } catch (err) {
    const msg = err.response?.data?.detail || 'Failed to delete HA group'
    toast.error(msg)
    console.error('Failed to delete HA group:', err)
  } finally {
    deletingGroup.value = null
  }
}

// ── Active tab ────────────────────────────────────────────────────────────────
const activeTab = ref('resources')

// ── Reload All ────────────────────────────────────────────────────────────────
const reloadAll = () => {
  loadHaStatus()
  loadHaResources()
  loadHaGroups()
  startPoll()
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => {
  loadHosts()
})

onUnmounted(() => {
  stopPoll()
})

// Restart poll when host changes
watch(selectedHostId, (val) => {
  if (val) startPoll()
  else stopPoll()
})
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

/* ── Page Header ── */
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

.header-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-shrink: 0;
}

/* ── Host Selector ── */
.host-selector-card {
  padding: 1rem 1.5rem !important;
}

.host-selector-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.host-selector-row .form-label {
  margin: 0;
  white-space: nowrap;
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.host-select {
  min-width: 280px;
  max-width: 420px;
}

.status-badge-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

/* ── HA Status Panel ── */
.ha-status-panel .card-header {
  margin-bottom: 1rem;
}

.ha-toggle-wrap {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.toggle-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.toggle-btn {
  position: relative;
  width: 44px;
  height: 24px;
  border-radius: 12px;
  border: none;
  cursor: pointer;
  transition: background 0.2s;
  padding: 0;
  flex-shrink: 0;
}

.toggle-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggle-on {
  background: #3b82f6;
}

.toggle-off {
  background: var(--bg-secondary, #2d3348);
}

.toggle-knob {
  position: absolute;
  top: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  transition: left 0.2s;
}

.toggle-on .toggle-knob {
  left: 23px;
}

.toggle-off .toggle-knob {
  left: 3px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
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

.last-event-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Tabs ── */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-color, #2d3348);
  margin-bottom: -1.5rem; /* collapse gap with next card */
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

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-active {
  color: #3b82f6 !important;
  border-bottom-color: #3b82f6 !important;
}

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
.loading-state {
  text-align: center;
  padding: 2.5rem;
  color: var(--text-muted, #6b7280);
  font-size: 0.9rem;
}

.loading-state-sm {
  padding: 1rem;
  text-align: left;
}

.error-banner {
  padding: 0.875rem 1rem;
  background: rgba(220, 38, 38, 0.12);
  border: 1px solid rgba(220, 38, 38, 0.3);
  border-radius: 0.375rem;
  color: #f87171;
  font-size: 0.9rem;
}

.empty-state {
  text-align: center;
  padding: 2.5rem 1.5rem;
  color: var(--text-muted, #6b7280);
}

.empty-state p {
  margin: 0.375rem 0;
}

.empty-placeholder {
  text-align: center;
  padding: 3rem 1.5rem;
}

/* ── Table ── */
.table-container {
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table thead tr {
  border-bottom: 1px solid var(--border-color, #2d3348);
}

.table th {
  padding: 0.625rem 0.875rem;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #6b7280);
}

.table td {
  padding: 0.75rem 0.875rem;
  border-bottom: 1px solid var(--border-color, #2d3348);
  font-size: 0.9rem;
  color: var(--text-primary);
  vertical-align: middle;
}

.table tbody tr:last-child td {
  border-bottom: none;
}

.table tbody tr:hover {
  background: var(--bg-hover, rgba(255, 255, 255, 0.03));
}

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

.node-priority {
  opacity: 0.7;
  font-size: 0.7rem;
}

.node-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

/* ── Node selector in modal ── */
.node-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.625rem;
}

.node-option {
  padding: 0.35rem 0.75rem;
  border-radius: 0.375rem;
  border: 1px solid var(--border-color, #2d3348);
  background: var(--bg-secondary, #151824);
  color: var(--text-secondary);
  font-size: 0.85rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.375rem;
  transition: all 0.15s;
  user-select: none;
}

.node-option:hover {
  border-color: #3b82f6;
  color: var(--text-primary);
}

.node-option-selected {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
}

.node-check {
  width: 14px;
  font-size: 0.8rem;
  color: #60a5fa;
}

.mt-sm {
  margin-top: 0.5rem;
}

/* ── Badges ── */
.badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-success  { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.badge-danger   { background: rgba(239, 68, 68, 0.15);  color: #f87171; }
.badge-warning  { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.badge-info     { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.badge-secondary { background: rgba(107, 114, 128, 0.2); color: #9ca3af; }

/* ── Buttons ── */
.btn {
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  border: none;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  transition: all 0.15s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #3b82f6;
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-secondary {
  background: var(--bg-secondary, #2d3348);
  color: var(--text-primary);
  border: 1px solid var(--border-color, #3d4568);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover, #363c55);
}

.btn-danger {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.25);
}

.btn-outline {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color, #3d4568);
}

.btn-outline:hover:not(:disabled) {
  background: var(--bg-hover, rgba(255, 255, 255, 0.05));
}

.btn-sm {
  padding: 0.25rem 0.625rem;
  font-size: 0.8rem;
}

/* ── Forms ── */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.required {
  color: #f87171;
}

.form-control {
  background: var(--bg-input, #151824);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.375rem;
  color: var(--text-primary);
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.15s;
}

.form-control:focus {
  border-color: #3b82f6;
}

.form-control option {
  background: var(--bg-card, #1e2130);
}

.field-hint {
  font-size: 0.78rem;
  color: var(--text-muted, #6b7280);
  margin: 0;
}

.field-hint code {
  background: var(--bg-secondary, #2d3348);
  padding: 0.1rem 0.3rem;
  border-radius: 0.2rem;
  font-family: monospace;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

/* ── Checkbox ── */
.checkbox-group {
  gap: 0.5rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
}

.checkbox-input {
  width: 16px;
  height: 16px;
  accent-color: #3b82f6;
  cursor: pointer;
}

/* ── Modal ── */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card, #1e2130);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 0.5rem;
  width: 90%;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-sm {
  max-width: 420px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color, #2d3348);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  color: var(--text-muted, #6b7280);
  padding: 0 0.25rem;
  transition: color 0.15s;
}

.btn-close:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  padding-top: 0.5rem;
}

/* ── Utilities ── */
.text-muted {
  color: var(--text-muted, #6b7280);
}

.text-sm {
  font-size: 0.875rem;
}

@media (max-width: 640px) {
  .ha-management {
    padding: 1rem;
  }

  .host-selector-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .host-select {
    min-width: 100%;
    max-width: 100%;
  }

  .page-header {
    flex-direction: column;
    gap: 1rem;
  }

  .form-row {
    grid-template-columns: 1fr;
  }

  .status-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
