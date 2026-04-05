<template>
  <div class="container-detail-page">
    <!-- Header -->
    <div class="page-header mb-2">
      <div class="header-left">
        <router-link :to="`/proxmox/${hostId}/nodes/${node}`" class="back-link">← {{ node }}</router-link>
        <h2 class="ct-title">
          {{ config.hostname || `CT ${vmid}` }}
          <span class="badge badge-info ml-1">{{ vmid }}</span>
          <span :class="['badge', 'ml-1', getStatusBadge(currentStats.status || status)]">{{ currentStats.status || status }}</span>
          <span class="badge badge-info ml-1">CT/LXC</span>
        </h2>
      </div>
      <div class="header-actions flex gap-1 flex-wrap">
        <button @click="action('start')" class="btn btn-success btn-sm"
          :disabled="actioning || (currentStats.status || status) === 'running'">Start</button>
        <button @click="action('stop')" class="btn btn-outline btn-sm"
          :disabled="actioning || (currentStats.status || status) !== 'running'">Stop</button>
        <button @click="action('reboot')" class="btn btn-outline btn-sm"
          :disabled="actioning || (currentStats.status || status) !== 'running'">Reboot</button>
        <button @click="action('restart')" class="btn btn-outline btn-sm"
          :disabled="actioning || (currentStats.status || status) !== 'running'">Restart</button>
        <button @click="openTerminal" class="btn btn-outline btn-sm">Terminal</button>
        <button @click="openCloneModal" class="btn btn-outline btn-sm">Clone</button>
        <button @click="deleteContainer" class="btn btn-danger btn-sm" :disabled="actioning">Delete</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-spinner"></div>

    <template v-else>
      <!-- Tabs -->
      <div class="tabs mb-2">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="switchTab(tab.id)"
          :class="['tab-btn', activeTab === tab.id ? 'tab-btn--active' : '']"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Overview Tab -->
      <div v-if="activeTab === 'overview'">
        <div class="stats-row mb-2">
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">CPU</div>
            <div class="stat-card-sm__value">{{ currentStats.cpu ? (currentStats.cpu * 100).toFixed(1) + '%' : '0%' }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">RAM</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.mem) }} / {{ formatBytes(currentStats.maxmem) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Uptime</div>
            <div class="stat-card-sm__value">{{ formatUptime(currentStats.uptime) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Disk Used</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.disk) }} / {{ formatBytes(currentStats.maxdisk) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Net In</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.netin) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Net Out</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.netout) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Disk Read</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.diskread) }}</div>
          </div>
          <div class="stat-card-sm">
            <div class="stat-card-sm__label">Disk Write</div>
            <div class="stat-card-sm__value">{{ formatBytes(currentStats.diskwrite) }}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h3>Summary</h3></div>
          <div class="card-body">
            <div class="summary-grid">
              <div class="summary-item"><span class="summary-label">Hostname</span><span>{{ config.hostname || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">OS Type</span><span>{{ config.ostype || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Cores</span><span>{{ config.cores || config.cpus || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Memory</span><span>{{ config.memory ? config.memory + ' MB' : '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Swap</span><span>{{ config.swap !== undefined ? config.swap + ' MB' : '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Start on Boot</span><span>{{ config.onboot ? 'Yes' : 'No' }}</span></div>
              <div class="summary-item"><span class="summary-label">Root FS</span><span class="text-sm">{{ config.rootfs || '—' }}</span></div>
              <div class="summary-item"><span class="summary-label">Template</span><span>{{ config.ostemplate || '—' }}</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Configuration Tab -->
      <div v-if="activeTab === 'config'">
        <div class="card">
          <div class="card-header">
            <h3>Container Configuration</h3>
            <div class="flex gap-1">
              <button v-if="!editMode" @click="enterEditMode" class="btn btn-outline btn-sm">Edit</button>
              <template v-else>
                <button @click="saveConfig" class="btn btn-primary btn-sm" :disabled="savingConfig">
                  {{ savingConfig ? 'Saving...' : 'Save' }}
                </button>
                <button @click="cancelEdit" class="btn btn-outline btn-sm">Cancel</button>
              </template>
            </div>
          </div>
          <div class="card-body">
            <div class="config-grid">
              <div class="form-group">
                <label class="form-label">Hostname</label>
                <input v-if="editMode" v-model="editConfig.hostname" class="form-control" />
                <div v-else class="config-value">{{ config.hostname || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Cores</label>
                <input v-if="editMode" v-model.number="editConfig.cores" type="number" min="1" class="form-control" />
                <div v-else class="config-value">{{ config.cores || config.cpus || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Memory (MB)</label>
                <input v-if="editMode" v-model.number="editConfig.memory" type="number" min="16" step="16" class="form-control" />
                <div v-else class="config-value">{{ config.memory ? config.memory + ' MB' : '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Swap (MB)</label>
                <input v-if="editMode" v-model.number="editConfig.swap" type="number" min="0" step="16" class="form-control" />
                <div v-else class="config-value">{{ config.swap !== undefined ? config.swap + ' MB' : '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Root Filesystem</label>
                <div class="config-value text-sm">{{ config.rootfs || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">Startup</label>
                <input v-if="editMode" v-model="editConfig.startup" class="form-control" placeholder="order=1,up=10" />
                <div v-else class="config-value">{{ config.startup || '—' }}</div>
              </div>
              <div class="form-group">
                <label class="form-label">
                  <input v-if="editMode" type="checkbox" v-model="editConfig.onboot" :true-value="1" :false-value="0" />
                  <input v-else type="checkbox" :checked="!!config.onboot" disabled />
                  Start on Boot
                </label>
              </div>
              <div class="form-group" style="grid-column: span 2;">
                <label class="form-label">Description</label>
                <textarea v-if="editMode" v-model="editConfig.description" class="form-control" rows="3"></textarea>
                <div v-else class="config-value" style="height: auto; min-height: 3rem; white-space: pre-wrap;">{{ config.description || '—' }}</div>
              </div>
            </div>

            <!-- Network Interfaces -->
            <div class="section-title mt-2 mb-1">Network Interfaces</div>
            <div v-if="parsedNets.length === 0" class="text-muted text-sm mb-2">No network interfaces configured.</div>
            <div v-else class="table-container mb-2">
              <table class="table">
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>Name</th>
                    <th>Bridge</th>
                    <th>IP</th>
                    <th>Gateway</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="net in parsedNets" :key="net.key">
                    <td><code>{{ net.key }}</code></td>
                    <td>{{ net.name || '—' }}</td>
                    <td>{{ net.bridge || '—' }}</td>
                    <td class="text-sm">{{ net.ip || '—' }}</td>
                    <td class="text-sm">{{ net.gw || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Full raw config -->
            <div class="section-title mt-2 mb-1">Full Configuration</div>
            <div class="raw-config-table">
              <div v-for="(val, key) in config" :key="key" class="raw-config-row">
                <span class="raw-config-key">{{ key }}</span>
                <span class="raw-config-val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Snapshots Tab -->
      <div v-if="activeTab === 'snapshots'">
        <div class="card">
          <div class="card-header">
            <h3>Snapshots</h3>
            <button @click="showSnapshotModal = true" class="btn btn-primary btn-sm">+ Create Snapshot</button>
          </div>

          <div v-if="loadingSnapshots" class="loading-spinner"></div>

          <div v-else-if="snapshots.length === 0" class="text-center text-muted" style="padding: 2rem;">
            <p>No snapshots found.</p>
          </div>

          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="snap in snapshots" :key="snap.name">
                  <td><strong>{{ snap.name }}</strong></td>
                  <td class="text-sm text-muted">{{ snap.description || '—' }}</td>
                  <td class="text-sm">{{ snap.snaptime ? formatDate(snap.snaptime) : '—' }}</td>
                  <td>
                    <div v-if="snap.name !== 'current'" class="flex gap-1">
                      <button @click="rollbackSnapshot(snap.name)" class="btn btn-outline btn-sm"
                        :disabled="actioning">Rollback</button>
                      <button @click="deleteSnapshot(snap.name)" class="btn btn-danger btn-sm"
                        :disabled="actioning">Delete</button>
                    </div>
                    <span v-else class="text-muted text-sm">current</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Performance Tab -->
      <div v-if="activeTab === 'performance'">
        <div class="card">
          <div class="card-header">
            <h3>Performance</h3>
            <button @click="fetchRrdData" class="btn btn-outline btn-sm" :disabled="loadingRrd">
              {{ loadingRrd ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <div class="card-body">
            <div v-if="loadingRrd" class="loading-spinner"></div>
            <div v-else-if="!rrdPoint" class="text-center text-muted" style="padding:2rem;">
              <p>No performance data available.</p>
            </div>
            <div v-else>
              <div class="perf-timeframe-row mb-2">
                <label class="form-label" style="margin:0;align-self:center;">Timeframe:</label>
                <select v-model="rrdTimeframe" @change="fetchRrdData" class="form-control" style="width:auto;">
                  <option value="hour">Last Hour</option>
                  <option value="day">Last Day</option>
                  <option value="week">Last Week</option>
                  <option value="month">Last Month</option>
                </select>
              </div>
              <div class="perf-grid">
                <div class="perf-card">
                  <div class="perf-card__label">CPU Usage</div>
                  <div class="perf-card__value">{{ rrdPoint.cpu != null ? (rrdPoint.cpu * 100).toFixed(2) + '%' : '—' }}</div>
                  <div class="perf-bar-track"><div class="perf-bar-fill" :style="{ width: rrdPoint.cpu != null ? Math.min(rrdPoint.cpu * 100, 100).toFixed(1) + '%' : '0%', background: cpuBarColor }"></div></div>
                </div>
                <div class="perf-card">
                  <div class="perf-card__label">Memory</div>
                  <div class="perf-card__value">{{ formatBytes(rrdPoint.mem) }} / {{ formatBytes(rrdPoint.maxmem) }}</div>
                  <div class="perf-bar-track"><div class="perf-bar-fill" :style="{ width: memPct + '%', background: memBarColor }"></div></div>
                  <div class="perf-card__sub">{{ memPct.toFixed(1) }}% used</div>
                </div>
                <div class="perf-card">
                  <div class="perf-card__label">Network In</div>
                  <div class="perf-card__value">{{ formatRateBytes(rrdPoint.netin) }}/s</div>
                </div>
                <div class="perf-card">
                  <div class="perf-card__label">Network Out</div>
                  <div class="perf-card__value">{{ formatRateBytes(rrdPoint.netout) }}/s</div>
                </div>
                <div class="perf-card">
                  <div class="perf-card__label">Disk Read</div>
                  <div class="perf-card__value">{{ formatRateBytes(rrdPoint.diskread) }}/s</div>
                </div>
                <div class="perf-card">
                  <div class="perf-card__label">Disk Write</div>
                  <div class="perf-card__value">{{ formatRateBytes(rrdPoint.diskwrite) }}/s</div>
                </div>
              </div>
              <div class="text-muted text-sm mt-2" style="text-align:right;">
                Data point: {{ rrdPoint.time ? new Date(rrdPoint.time * 1000).toLocaleString() : 'unknown' }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Terminal Tab -->
      <div v-if="activeTab === 'terminal'">
        <div class="card">
          <div class="card-header"><h3>Container Terminal</h3></div>
          <div class="card-body text-center" style="padding: 2rem;">
            <p class="text-muted mb-2">Open an interactive shell session for this LXC container.</p>
            <button @click="openTerminal" class="btn btn-primary">Open Terminal</button>
            <p class="text-muted text-sm mt-2">
              Navigates to the Depl0y terminal viewer
              (<code>/proxmox/{{ hostId }}/nodes/{{ node }}/terminal?lxc={{ vmid }}</code>)
            </p>
          </div>
        </div>
      </div>
    </template>

    <!-- Clone LXC Modal -->
    <div v-if="showCloneModal" class="modal" @click="showCloneModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Clone Container CT{{ vmid }}</h3>
          <button @click="showCloneModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitClone" class="modal-body">
          <div class="form-group">
            <label class="form-label">New CT ID</label>
            <input v-model.number="cloneForm.newid" type="number" min="100" class="form-control" required :disabled="loadingNextId" />
            <div v-if="loadingNextId" class="text-muted text-sm mt-1">Loading next available ID…</div>
          </div>
          <div class="form-group">
            <label class="form-label">Hostname</label>
            <input v-model="cloneForm.hostname" type="text" class="form-control" placeholder="new-container" />
          </div>
          <div class="form-group">
            <label class="form-label">Target Node</label>
            <select v-model="cloneForm.target" class="form-control">
              <option value="">Same node ({{ node }})</option>
              <option v-for="n in pveNodes" :key="n.name" :value="n.name">{{ n.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Storage (optional)</label>
            <input v-model="cloneForm.storage" type="text" class="form-control" placeholder="e.g. local-lvm" />
          </div>
          <div class="form-group">
            <label class="form-label checkbox-label">
              <input type="checkbox" v-model="cloneForm.full" style="margin-right:0.5rem;" />
              Full Clone (uncheck for linked clone)
            </label>
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="cloningLxc">
              {{ cloningLxc ? 'Cloning…' : 'Clone' }}
            </button>
            <button type="button" @click="showCloneModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create Snapshot Modal -->
    <div v-if="showSnapshotModal" class="modal" @click="showSnapshotModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Snapshot</h3>
          <button @click="showSnapshotModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="createSnapshot" class="modal-body">
          <div class="form-group">
            <label class="form-label">Snapshot Name</label>
            <input v-model="newSnapshot.snapname" class="form-control" placeholder="snap1" required />
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <input v-model="newSnapshot.description" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingSnapshot">
              {{ savingSnapshot ? 'Creating...' : 'Create' }}
            </button>
            <button type="button" @click="showSnapshotModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import { formatBytes, formatUptime } from '@/utils/proxmox'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const hostId = computed(() => route.params.hostId)
const node = computed(() => route.params.node)
const vmid = computed(() => route.params.vmid)

const status = ref('unknown')
const config = ref({})
const editConfig = ref({})
const currentStats = ref({})
const snapshots = ref([])
const loading = ref(true)
const actioning = ref(false)
const savingConfig = ref(false)
const loadingSnapshots = ref(false)
const showSnapshotModal = ref(false)
const savingSnapshot = ref(false)
const activeTab = ref('overview')
const editMode = ref(false)
const newSnapshot = ref({ snapname: '', description: '' })

// Clone modal state
const showCloneModal = ref(false)
const cloningLxc = ref(false)
const loadingNextId = ref(false)
const pveNodes = ref([])
const cloneForm = ref({ newid: null, hostname: '', target: '', full: true, storage: '' })

// Performance / RRD state
const rrdData = ref([])
const loadingRrd = ref(false)
const rrdTimeframe = ref('hour')

let pollInterval = null

const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'config', label: 'Config' },
  { id: 'snapshots', label: 'Snapshots' },
  { id: 'performance', label: 'Performance' },
  { id: 'terminal', label: 'Terminal' },
]

const NET_KEYS = ['net0', 'net1', 'net2', 'net3', 'net4', 'net5', 'net6', 'net7']

const parsedNets = computed(() => {
  if (!config.value) return []
  return NET_KEYS
    .filter(k => config.value[k])
    .map(k => {
      const raw = config.value[k]
      const result = { key: k, raw, name: '', bridge: '', ip: '', gw: '' }
      raw.split(',').forEach(part => {
        if (part.startsWith('name=')) result.name = part.slice(5)
        else if (part.startsWith('bridge=')) result.bridge = part.slice(7)
        else if (part.startsWith('ip=')) result.ip = part.slice(3)
        else if (part.startsWith('gw=')) result.gw = part.slice(3)
      })
      return result
    })
})

const fetchAll = async () => {
  loading.value = true
  try {
    const [statusRes, configRes] = await Promise.all([
      api.pveNode.getContainerStatus(hostId.value, node.value, vmid.value),
      api.pveNode.getContainerConfig(hostId.value, node.value, vmid.value),
    ])
    currentStats.value = statusRes.data || {}
    status.value = currentStats.value.status || 'unknown'
    config.value = configRes.data || {}
  } catch (error) {
    console.error('Failed to fetch container info:', error)
    toast.error('Failed to load container information')
  } finally {
    loading.value = false
  }
}

const fetchStatus = async () => {
  try {
    const res = await api.pveNode.getContainerStatus(hostId.value, node.value, vmid.value)
    currentStats.value = res.data || {}
    status.value = currentStats.value.status || 'unknown'
  } catch (e) {
    console.warn('CT status poll failed', e)
  }
}

const fetchSnapshots = async () => {
  loadingSnapshots.value = true
  try {
    const response = await api.pveNode.listContainerSnapshots(hostId.value, node.value, vmid.value)
    snapshots.value = response.data || []
  } catch (error) {
    console.error('Failed to fetch snapshots:', error)
  } finally {
    loadingSnapshots.value = false
  }
}

// RRD computed helpers
const rrdPoint = computed(() => {
  if (!rrdData.value || rrdData.value.length === 0) return null
  // Find the last non-null data point
  for (let i = rrdData.value.length - 1; i >= 0; i--) {
    const p = rrdData.value[i]
    if (p && (p.cpu != null || p.mem != null)) return p
  }
  return rrdData.value[rrdData.value.length - 1]
})

const memPct = computed(() => {
  if (!rrdPoint.value || !rrdPoint.value.maxmem || !rrdPoint.value.mem) return 0
  return Math.min((rrdPoint.value.mem / rrdPoint.value.maxmem) * 100, 100)
})

const cpuBarColor = computed(() => {
  if (!rrdPoint.value || rrdPoint.value.cpu == null) return 'var(--primary-color)'
  const pct = rrdPoint.value.cpu * 100
  if (pct > 90) return '#ef4444'
  if (pct > 70) return '#f59e0b'
  return '#22c55e'
})

const memBarColor = computed(() => {
  if (memPct.value > 90) return '#ef4444'
  if (memPct.value > 70) return '#f59e0b'
  return '#3b82f6'
})

const switchTab = (tab) => {
  activeTab.value = tab
  if (tab === 'snapshots') fetchSnapshots()
  if (tab === 'overview') fetchStatus()
  if (tab === 'performance') fetchRrdData()
}

const startPolling = () => {
  pollInterval = setInterval(() => {
    if (activeTab.value === 'overview') fetchStatus()
  }, 5000)
}

const action = async (act) => {
  actioning.value = true
  try {
    await api.pveNode.containerAction(hostId.value, node.value, vmid.value, act)
    toast.success(`Container ${act} initiated`)
    setTimeout(() => fetchStatus(), 2000)
  } catch (error) {
    console.error(`Failed to ${act} container:`, error)
    toast.error(`Failed to ${act} container`)
  } finally {
    actioning.value = false
  }
}

const enterEditMode = () => {
  editConfig.value = {
    hostname: config.value.hostname || '',
    cores: config.value.cores || config.value.cpus || 1,
    memory: config.value.memory || 512,
    swap: config.value.swap !== undefined ? config.value.swap : 0,
    startup: config.value.startup || '',
    onboot: config.value.onboot || 0,
    description: config.value.description || '',
  }
  editMode.value = true
}

const cancelEdit = () => {
  editMode.value = false
}

const saveConfig = async () => {
  savingConfig.value = true
  try {
    const payload = { ...editConfig.value }
    Object.keys(payload).forEach(k => {
      if (payload[k] === '' || payload[k] === null) delete payload[k]
    })
    await api.pveNode.updateContainerConfig(hostId.value, node.value, vmid.value, payload)
    toast.success('Configuration saved')
    editMode.value = false
    await fetchAll()
  } catch (error) {
    console.error('Failed to save config:', error)
    toast.error('Failed to save configuration')
  } finally {
    savingConfig.value = false
  }
}

const createSnapshot = async () => {
  if (!newSnapshot.value.snapname) {
    toast.error('Snapshot name is required')
    return
  }
  savingSnapshot.value = true
  try {
    await api.pveNode.createContainerSnapshot(hostId.value, node.value, vmid.value, newSnapshot.value)
    toast.success('Snapshot created')
    showSnapshotModal.value = false
    newSnapshot.value = { snapname: '', description: '' }
    await fetchSnapshots()
  } catch (error) {
    console.error('Failed to create snapshot:', error)
    toast.error('Failed to create snapshot')
  } finally {
    savingSnapshot.value = false
  }
}

const rollbackSnapshot = async (snapname) => {
  if (!confirm(`Roll back to snapshot "${snapname}"? Current container state will be lost.`)) return
  actioning.value = true
  try {
    await api.pveNode.rollbackContainerSnapshot(hostId.value, node.value, vmid.value, snapname)
    toast.success('Rollback initiated')
    await fetchSnapshots()
  } catch (error) {
    console.error('Failed to rollback:', error)
    toast.error('Failed to rollback')
  } finally {
    actioning.value = false
  }
}

const deleteSnapshot = async (snapname) => {
  if (!confirm(`Delete snapshot "${snapname}"?`)) return
  actioning.value = true
  try {
    const token = localStorage.getItem('access_token')
    const { default: axios } = await import('axios')
    await axios.delete(
      `/api/v1/pve-node/${hostId.value}/nodes/${node.value}/lxc/${vmid.value}/snapshots/${snapname}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    toast.success('Snapshot deleted')
    await fetchSnapshots()
  } catch (error) {
    console.error('Failed to delete snapshot:', error)
    toast.error('Failed to delete snapshot')
  } finally {
    actioning.value = false
  }
}

const deleteContainer = async () => {
  if (!confirm(`Permanently delete CT ${vmid.value}? This cannot be undone.`)) return
  actioning.value = true
  try {
    await api.pveNode.deleteContainer(hostId.value, node.value, vmid.value)
    toast.success('Container deleted')
    router.push(`/proxmox/${hostId.value}/nodes/${node.value}`)
  } catch (error) {
    console.error('Failed to delete container:', error)
    toast.error('Failed to delete container')
  } finally {
    actioning.value = false
  }
}

const fetchRrdData = async () => {
  loadingRrd.value = true
  try {
    const res = await api.pveNode.lxcRrdData(hostId.value, node.value, vmid.value, {
      timeframe: rrdTimeframe.value,
      cf: 'AVERAGE',
    })
    rrdData.value = res.data || []
  } catch (e) {
    console.error('Failed to fetch RRD data:', e)
    toast.error('Failed to load performance data')
  } finally {
    loadingRrd.value = false
  }
}

const formatRateBytes = (val) => {
  if (val == null || isNaN(val)) return '0 B'
  if (val >= 1073741824) return (val / 1073741824).toFixed(2) + ' GB'
  if (val >= 1048576) return (val / 1048576).toFixed(2) + ' MB'
  if (val >= 1024) return (val / 1024).toFixed(2) + ' KB'
  return val.toFixed(0) + ' B'
}

const openCloneModal = async () => {
  cloneForm.value = { newid: null, hostname: '', target: '', full: true, storage: '' }
  showCloneModal.value = true
  // Load next ID and cluster nodes in parallel
  loadingNextId.value = true
  try {
    const [nextIdRes, clusterRes] = await Promise.all([
      api.pveNode.nextId(hostId.value),
      api.pveNode.clusterStatus(hostId.value),
    ])
    cloneForm.value.newid = nextIdRes.data
    // clusterStatus returns mixed entries (type=cluster + type=node); keep only nodes
    const allNodes = (clusterRes.data || []).filter(e => e.type === 'node')
    pveNodes.value = allNodes.filter(n => n.name !== node.value)
  } catch (e) {
    console.warn('Failed to pre-populate clone form:', e)
  } finally {
    loadingNextId.value = false
  }
}

const submitClone = async () => {
  if (!cloneForm.value.newid) {
    toast.error('New CT ID is required')
    return
  }
  cloningLxc.value = true
  try {
    const payload = { newid: cloneForm.value.newid, full: cloneForm.value.full ? 1 : 0 }
    if (cloneForm.value.hostname) payload.hostname = cloneForm.value.hostname
    if (cloneForm.value.target) payload.target = cloneForm.value.target
    if (cloneForm.value.storage) payload.storage = cloneForm.value.storage
    await api.pveNode.cloneLxc(hostId.value, node.value, vmid.value, payload)
    toast.success(`Clone task started — new CT ${cloneForm.value.newid}`)
    showCloneModal.value = false
  } catch (e) {
    console.error('Failed to clone container:', e)
    toast.error('Failed to clone container')
  } finally {
    cloningLxc.value = false
  }
}

const openTerminal = () => {
  router.push(`/proxmox/${hostId.value}/nodes/${node.value}/terminal?lxc=${vmid.value}`)
}

const getStatusBadge = (s) => {
  if (s === 'running') return 'badge-success'
  if (s === 'stopped') return 'badge-danger'
  if (s === 'suspended') return 'badge-warning'
  return 'badge-info'
}

const formatDate = (epoch) => new Date(epoch * 1000).toLocaleString()

onMounted(async () => {
  await fetchAll()
  fetchSnapshots()
  startPolling()
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<style scoped>
.container-detail-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.back-link {
  color: var(--text-muted, var(--text-secondary));
  text-decoration: none;
  font-size: 0.875rem;
}

.back-link:hover {
  color: var(--text-primary);
}

.ct-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1.5rem;
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
}

.tab-btn:hover { color: var(--text-primary); }

.tab-btn--active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(155px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card-sm {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.875rem 1rem;
}

.stat-card-sm__label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.stat-card-sm__value {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.card-body {
  padding: 1.5rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 0.75rem;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem;
  background: var(--background, var(--bg-secondary));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}

.summary-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 700px) {
  .config-grid { grid-template-columns: 1fr; }
}

.config-value {
  padding: 0.5rem 0.75rem;
  background: var(--bg-tertiary, var(--background, #1a1a2e));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  color: var(--text-primary);
  font-size: 0.9rem;
  min-height: 2.25rem;
  display: flex;
  align-items: center;
}

.section-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-top: 1px solid var(--border-color);
  padding-top: 1rem;
}

.raw-config-table {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
}

.raw-config-row {
  display: grid;
  grid-template-columns: 180px 1fr;
  border-bottom: 1px solid var(--border-color);
}

.raw-config-row:last-child { border-bottom: none; }

.raw-config-key {
  padding: 0.4rem 0.75rem;
  background: var(--background, rgba(255,255,255,0.03));
  font-family: monospace;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-right: 1px solid var(--border-color);
}

.raw-config-val {
  padding: 0.4rem 0.75rem;
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--text-primary);
  word-break: break-all;
}

.table-container { overflow-x: auto; }

.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 { margin: 0; font-size: 1.1rem; }

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.modal-body { padding: 1.5rem; }

.flex { display: flex; }
.flex-wrap { flex-wrap: wrap; }
.gap-1 { gap: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.mb-2 { margin-bottom: 1rem; }
.mb-1 { margin-bottom: 0.5rem; }
.ml-1 { margin-left: 0.25rem; }
.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.875rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-center { text-align: center; }

/* Performance tab */
.perf-timeframe-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.perf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

.perf-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
}

.perf-card__label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.35rem;
  font-weight: 600;
}

.perf-card__value {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.perf-card__sub {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.perf-bar-track {
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 0.25rem;
}

.perf-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

/* Clone modal extras */
.checkbox-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-weight: 500;
}
</style>
