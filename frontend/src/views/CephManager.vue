<template>
  <div class="ceph-manager">
    <div class="page-header">
      <div>
        <h1>Ceph Cluster Manager</h1>
        <p class="text-muted">Monitor and manage Ceph storage clusters across Proxmox hosts</p>
      </div>
      <div class="header-actions">
        <button @click="refreshAll" class="btn btn-secondary" :disabled="loading">
          {{ loading ? 'Refreshing…' : 'Refresh' }}
        </button>
      </div>
    </div>

    <!-- Host / Node selector -->
    <div class="card selector-card">
      <div class="selector-row">
        <div class="selector-item">
          <label class="form-label">Proxmox Host</label>
          <select v-model="selectedHostId" class="form-control" :disabled="loadingHosts" @change="onHostChange">
            <option value="">{{ loadingHosts ? 'Loading…' : 'Select a host…' }}</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }} — {{ h.address }}</option>
          </select>
        </div>
        <div class="selector-item">
          <label class="form-label">Node</label>
          <select v-model="selectedNode" class="form-control" :disabled="!selectedHostId || loadingNodes" @change="onNodeChange">
            <option value="">{{ loadingNodes ? 'Loading…' : 'Select a node…' }}</option>
            <option v-for="n in nodes" :key="n.node" :value="n.node">{{ n.node }}</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Nothing selected yet -->
    <div v-if="!selectedHostId || !selectedNode" class="card empty-placeholder">
      <p class="text-muted">Select a Proxmox host and node above to view Ceph cluster information.</p>
    </div>

    <template v-else>
      <!-- Tabs -->
      <div class="tab-bar">
        <button v-for="tab in tabs" :key="tab.id"
          :class="['tab-btn', activeTab === tab.id ? 'active' : '']"
          @click="switchTab(tab.id)">
          {{ tab.label }}
        </button>
      </div>

      <!-- ── OVERVIEW TAB ── -->
      <div v-if="activeTab === 'overview'">
        <div v-if="loadingStatus" class="card loading-state">Loading Ceph status…</div>
        <div v-else-if="statusError" class="card error-state">
          <p class="text-danger">{{ statusError }}</p>
        </div>
        <template v-else-if="cephStatus">
          <!-- Health banner -->
          <div class="card health-banner" :class="healthClass">
            <div class="health-main">
              <span class="health-icon">{{ healthIcon }}</span>
              <div>
                <div class="health-label">Cluster Health</div>
                <div class="health-status">{{ healthStatus }}</div>
              </div>
            </div>
            <div v-if="healthSummary" class="health-summary">{{ healthSummary }}</div>
          </div>

          <!-- Stats grid -->
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-label">Total OSDs</div>
              <div class="stat-value">{{ osdStats.total }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">OSDs Up</div>
              <div class="stat-value text-success">{{ osdStats.up }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">OSDs In</div>
              <div class="stat-value text-success">{{ osdStats.in }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">Monitors</div>
              <div class="stat-value">{{ monCount }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">PG Count</div>
              <div class="stat-value">{{ pgCount }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">Total Space</div>
              <div class="stat-value">{{ formatBytes(bytesTotal) }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">Used</div>
              <div class="stat-value text-warning">{{ formatBytes(bytesUsed) }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">Available</div>
              <div class="stat-value text-success">{{ formatBytes(bytesAvail) }}</div>
            </div>
          </div>

          <!-- Space bar -->
          <div v-if="bytesTotal > 0" class="card">
            <div class="card-header"><h2>Space Usage</h2></div>
            <div class="usage-bar-wrap">
              <div class="usage-bar">
                <div class="usage-fill" :style="{ width: usedPercent + '%' }" :class="usedPercent > 85 ? 'usage-fill-danger' : usedPercent > 70 ? 'usage-fill-warn' : 'usage-fill-ok'"></div>
              </div>
              <span class="usage-pct">{{ usedPercent }}%</span>
            </div>
          </div>

          <!-- Health detail messages -->
          <div v-if="healthChecks.length" class="card">
            <div class="card-header"><h2>Health Details</h2></div>
            <div v-for="(check, idx) in healthChecks" :key="idx" class="health-detail-row" :class="'health-detail-' + check.severity.toLowerCase()">
              <span class="hd-severity">{{ check.severity }}</span>
              <div class="hd-body">
                <div class="hd-summary">{{ check.summary }}</div>
                <div v-if="check.detail" class="hd-detail">{{ check.detail }}</div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- ── OSDs TAB ── -->
      <div v-if="activeTab === 'osds'">
        <div v-if="loadingOsds" class="card loading-state">Loading OSD tree…</div>
        <div v-else-if="osdsError" class="card error-state">
          <p class="text-danger">{{ osdsError }}</p>
        </div>
        <template v-else>
          <!-- OSD Distribution visualization -->
          <div class="card">
            <div class="card-header"><h2>OSD Distribution</h2></div>
            <div v-if="osdHosts.length === 0" class="empty-state">No OSD data available.</div>
            <div v-else class="osd-tree">
              <div v-for="host in osdHosts" :key="host.name" class="osd-host-block">
                <div class="osd-host-label">
                  <span class="icon">🖥️</span> {{ host.name }}
                  <span class="badge badge-secondary ml-1">{{ host.osds.length }} OSD{{ host.osds.length !== 1 ? 's' : '' }}</span>
                </div>
                <div class="osd-chips">
                  <div v-for="osd in host.osds" :key="osd.osd"
                    class="osd-chip"
                    :class="osd.up && osd.in ? 'osd-chip-ok' : !osd.up ? 'osd-chip-down' : 'osd-chip-out'"
                    :title="`OSD.${osd.osd} — up:${osd.up} in:${osd.in}`">
                    osd.{{ osd.osd }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- OSD Table -->
          <div class="card">
            <div class="card-header">
              <h2>OSD List</h2>
              <span class="badge badge-secondary">{{ flatOsds.length }} total</span>
            </div>
            <div v-if="flatOsds.length === 0" class="empty-state">No OSDs found.</div>
            <div v-else class="table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Host</th>
                    <th>Device</th>
                    <th>Status</th>
                    <th>In/Out</th>
                    <th>Weight</th>
                    <th>Reweight</th>
                    <th>PGs</th>
                    <th>Read Ops</th>
                    <th>Write Ops</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="osd in flatOsds" :key="osd.osd">
                    <td><strong>osd.{{ osd.osd }}</strong></td>
                    <td>{{ osd.host || '—' }}</td>
                    <td class="text-mono text-small">{{ osd.device_class || '—' }}</td>
                    <td>
                      <span :class="['badge', osd.up ? 'badge-success' : 'badge-danger']">
                        {{ osd.up ? 'UP' : 'DOWN' }}
                      </span>
                    </td>
                    <td>
                      <span :class="['badge', osd.in ? 'badge-success' : 'badge-secondary']">
                        {{ osd.in ? 'IN' : 'OUT' }}
                      </span>
                    </td>
                    <td>{{ osd.crush_weight !== undefined ? osd.crush_weight.toFixed(4) : '—' }}</td>
                    <td>{{ osd.reweight !== undefined ? osd.reweight.toFixed(4) : '—' }}</td>
                    <td>{{ osd.pgs !== undefined ? osd.pgs : '—' }}</td>
                    <td>{{ osd.kb_read !== undefined ? formatOps(osd.kb_read) : '—' }}</td>
                    <td>{{ osd.kb_write !== undefined ? formatOps(osd.kb_write) : '—' }}</td>
                    <td>
                      <div class="action-btns">
                        <button @click="osdAction(osd, 'in')" class="btn btn-xs btn-secondary" title="Mark In">In</button>
                        <button @click="osdAction(osd, 'out')" class="btn btn-xs btn-secondary" title="Mark Out">Out</button>
                        <button @click="osdAction(osd, 'up')" class="btn btn-xs btn-secondary" title="Mark Up">Up</button>
                        <button @click="osdAction(osd, 'down')" class="btn btn-xs btn-danger" title="Mark Down">Down</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
      </div>

      <!-- ── POOLS TAB ── -->
      <div v-if="activeTab === 'pools'">
        <div class="card">
          <div class="card-header">
            <h2>Ceph Pools</h2>
            <button @click="openCreatePool" class="btn btn-primary btn-sm">+ Create Pool</button>
          </div>
          <div v-if="loadingPools" class="loading-state">Loading pools…</div>
          <div v-else-if="poolsError" class="text-danger p-3">{{ poolsError }}</div>
          <div v-else-if="cephPools.length === 0" class="empty-state">No Ceph pools found.</div>
          <div v-else class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Size</th>
                  <th>Min-Size</th>
                  <th>PG Num</th>
                  <th>PGP Num</th>
                  <th>Used</th>
                  <th>% Used</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pool in cephPools" :key="pool.pool_name || pool.pool">
                  <td><strong>{{ pool.pool_name || pool.pool }}</strong></td>
                  <td>{{ pool.pool }}</td>
                  <td>
                    <span class="badge badge-secondary">{{ pool.type || 'replicated' }}</span>
                  </td>
                  <td>{{ pool.size || '—' }}</td>
                  <td>{{ pool.min_size || '—' }}</td>
                  <td>{{ pool.pg_num || '—' }}</td>
                  <td>{{ pool.pg_placement_num || pool.pgp_num || '—' }}</td>
                  <td>{{ pool.bytes_used !== undefined ? formatBytes(pool.bytes_used) : '—' }}</td>
                  <td>
                    <span v-if="pool.percent_used !== undefined" :class="['badge', pool.percent_used > 85 ? 'badge-danger' : pool.percent_used > 70 ? 'badge-warning' : 'badge-success']">
                      {{ pool.percent_used.toFixed(1) }}%
                    </span>
                    <span v-else>—</span>
                  </td>
                  <td>
                    <button @click="confirmDeletePool(pool)" class="btn btn-xs btn-danger">Delete</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ── MONITORS TAB ── -->
      <div v-if="activeTab === 'monitors'">
        <div v-if="loadingMons" class="card loading-state">Loading monitors…</div>
        <div v-else-if="monsError" class="card error-state">
          <p class="text-danger">{{ monsError }}</p>
        </div>
        <template v-else>
          <!-- Quorum visualization -->
          <div class="card">
            <div class="card-header"><h2>Monitor Quorum</h2></div>
            <div class="quorum-row">
              <div v-for="mon in cephMons" :key="mon.name" class="quorum-node" :class="mon.quorum ? 'quorum-ok' : 'quorum-warn'">
                <div class="quorum-icon">{{ mon.quorum ? '✓' : '✗' }}</div>
                <div class="quorum-name">{{ mon.name }}</div>
                <div class="quorum-rank">Rank {{ mon.rank !== undefined ? mon.rank : '?' }}</div>
              </div>
            </div>
            <div v-if="cephMons.length === 0" class="empty-state">No monitor data available.</div>
          </div>

          <!-- Monitors table -->
          <div class="card">
            <div class="card-header">
              <h2>Monitors</h2>
              <span class="badge badge-secondary">{{ cephMons.length }} total</span>
            </div>
            <div v-if="cephMons.length === 0" class="empty-state">No monitors found.</div>
            <div v-else class="table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Address</th>
                    <th>Rank</th>
                    <th>In Quorum</th>
                    <th>State</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="mon in cephMons" :key="mon.name">
                    <td><strong>{{ mon.name }}</strong></td>
                    <td class="text-mono text-small">{{ mon.addr || mon.public_addr || '—' }}</td>
                    <td>{{ mon.rank !== undefined ? mon.rank : '—' }}</td>
                    <td>
                      <span :class="['badge', mon.quorum ? 'badge-success' : 'badge-danger']">
                        {{ mon.quorum ? 'Yes' : 'No' }}
                      </span>
                    </td>
                    <td>{{ mon.state || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
      </div>

      <!-- ── CONFIG TAB ── -->
      <div v-if="activeTab === 'config'">
        <div class="card">
          <div class="card-header">
            <h2>Ceph Configuration</h2>
            <p class="card-subtitle">Key cluster configuration parameters from ceph status</p>
          </div>
          <div v-if="loadingStatus" class="loading-state">Loading config…</div>
          <div v-else-if="!cephStatus" class="empty-state">No configuration data available.</div>
          <div v-else class="config-grid">
            <div v-for="item in configItems" :key="item.key" class="config-row">
              <div class="config-key">{{ item.label }}</div>
              <div class="config-value">
                <template v-if="editingKey === item.key">
                  <input v-model="editValue" class="form-control form-control-sm config-input" @keyup.enter="saveConfig(item)" @keyup.escape="editingKey = null" />
                  <button @click="saveConfig(item)" class="btn btn-xs btn-primary ml-1">Save</button>
                  <button @click="editingKey = null" class="btn btn-xs btn-secondary ml-1">Cancel</button>
                </template>
                <template v-else>
                  <span class="config-val-text">{{ item.value }}</span>
                  <button v-if="item.editable" @click="startEdit(item)" class="btn btn-xs btn-secondary ml-2">Edit</button>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ── CREATE POOL MODAL ── -->
    <div v-if="showCreatePool" class="modal-overlay" @click.self="showCreatePool = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Create Ceph Pool</h3>
          <button class="modal-close" @click="showCreatePool = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Pool Name <span class="required">*</span></label>
            <input v-model="newPool.name" class="form-control" placeholder="e.g. rbd, cephfs-data" />
          </div>
          <div class="form-group">
            <label class="form-label">Type</label>
            <select v-model="newPool.type" class="form-control">
              <option value="replicated">Replicated</option>
              <option value="erasure">Erasure</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Size (Replicas)</label>
            <input v-model.number="newPool.size" class="form-control" type="number" min="1" max="10" />
          </div>
          <div class="form-group">
            <label class="form-label">PG Num</label>
            <input v-model.number="newPool.pg_num" class="form-control" type="number" min="1" />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showCreatePool = false" class="btn btn-secondary">Cancel</button>
          <button @click="createPool" class="btn btn-primary" :disabled="!newPool.name || creatingPool">
            {{ creatingPool ? 'Creating…' : 'Create Pool' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── DELETE POOL CONFIRM ── -->
    <div v-if="showDeletePool" class="modal-overlay" @click.self="showDeletePool = false">
      <div class="modal-box modal-box-sm">
        <div class="modal-header">
          <h3>Delete Pool</h3>
          <button class="modal-close" @click="showDeletePool = false">&times;</button>
        </div>
        <div class="modal-body">
          <p>Are you absolutely sure you want to delete pool <strong>{{ poolToDelete?.pool_name || poolToDelete?.pool }}</strong>?</p>
          <p class="text-danger text-small">This operation is <strong>irreversible</strong> and will permanently destroy all data in this pool.</p>
          <div class="form-group mt-3">
            <label class="form-label">Type the pool name to confirm:</label>
            <input v-model="deleteConfirmName" class="form-control" :placeholder="poolToDelete?.pool_name || poolToDelete?.pool" />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showDeletePool = false" class="btn btn-secondary">Cancel</button>
          <button @click="deletePool"
            :disabled="deleteConfirmName !== (poolToDelete?.pool_name || poolToDelete?.pool) || deletingPool"
            class="btn btn-danger">
            {{ deletingPool ? 'Deleting…' : 'Delete Pool' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── OSD ACTION CONFIRM ── -->
    <div v-if="showOsdAction" class="modal-overlay" @click.self="showOsdAction = false">
      <div class="modal-box modal-box-sm">
        <div class="modal-header">
          <h3>OSD Action</h3>
          <button class="modal-close" @click="showOsdAction = false">&times;</button>
        </div>
        <div class="modal-body">
          <p>Mark <strong>osd.{{ pendingOsd?.osd }}</strong> as <strong>{{ pendingAction }}</strong>?</p>
          <p class="text-muted text-small">This changes the OSD state in the cluster. Proceed with caution.</p>
        </div>
        <div class="modal-footer">
          <button @click="showOsdAction = false" class="btn btn-secondary">Cancel</button>
          <button @click="executeOsdAction" class="btn btn-primary" :disabled="executingOsdAction">
            {{ executingOsdAction ? 'Applying…' : 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'CephManager',
  setup() {
    const toast = useToast()

    // ── Selectors ─────────────────────────────────────────────────────────────
    const hosts = ref([])
    const nodes = ref([])
    const selectedHostId = ref('')
    const selectedNode = ref('')
    const loadingHosts = ref(false)
    const loadingNodes = ref(false)

    // ── Tab state ─────────────────────────────────────────────────────────────
    const activeTab = ref('overview')
    const tabs = [
      { id: 'overview', label: 'Overview' },
      { id: 'osds', label: 'OSDs' },
      { id: 'pools', label: 'Pools' },
      { id: 'monitors', label: 'Monitors' },
      { id: 'config', label: 'Config' },
    ]

    // ── Status / overview ─────────────────────────────────────────────────────
    const cephStatus = ref(null)
    const loadingStatus = ref(false)
    const statusError = ref('')

    // ── OSDs ──────────────────────────────────────────────────────────────────
    const cephOsds = ref(null)
    const loadingOsds = ref(false)
    const osdsError = ref('')

    // ── Pools ─────────────────────────────────────────────────────────────────
    const cephPools = ref([])
    const loadingPools = ref(false)
    const poolsError = ref('')

    // ── Monitors ──────────────────────────────────────────────────────────────
    const cephMons = ref([])
    const loadingMons = ref(false)
    const monsError = ref('')

    // ── Modals ────────────────────────────────────────────────────────────────
    const showCreatePool = ref(false)
    const creatingPool = ref(false)
    const newPool = ref({ name: '', type: 'replicated', size: 3, pg_num: 128 })

    const showDeletePool = ref(false)
    const deletingPool = ref(false)
    const poolToDelete = ref(null)
    const deleteConfirmName = ref('')

    const showOsdAction = ref(false)
    const executingOsdAction = ref(false)
    const pendingOsd = ref(null)
    const pendingAction = ref('')

    // ── Config editing ────────────────────────────────────────────────────────
    const editingKey = ref(null)
    const editValue = ref('')

    // ── Loading aggregate ─────────────────────────────────────────────────────
    const loading = computed(() =>
      loadingStatus.value || loadingOsds.value || loadingPools.value || loadingMons.value
    )

    // ── Health computed ───────────────────────────────────────────────────────
    const healthStatus = computed(() => {
      return cephStatus.value?.health?.status || cephStatus.value?.status || 'UNKNOWN'
    })

    const healthClass = computed(() => {
      const s = healthStatus.value
      if (s === 'HEALTH_OK') return 'health-ok'
      if (s === 'HEALTH_WARN') return 'health-warn'
      if (s === 'HEALTH_ERR') return 'health-err'
      return 'health-unknown'
    })

    const healthIcon = computed(() => {
      const s = healthStatus.value
      if (s === 'HEALTH_OK') return '✅'
      if (s === 'HEALTH_WARN') return '⚠️'
      if (s === 'HEALTH_ERR') return '❌'
      return '❓'
    })

    const healthSummary = computed(() => {
      const checks = cephStatus.value?.health?.checks
      if (!checks) return ''
      return Object.values(checks).map(c => c.summary?.message || '').filter(Boolean).join(' | ')
    })

    const healthChecks = computed(() => {
      const checks = cephStatus.value?.health?.checks
      if (!checks) return []
      return Object.entries(checks).map(([key, val]) => ({
        key,
        severity: val.severity || 'HEALTH_WARN',
        summary: val.summary?.message || key,
        detail: val.detail?.map(d => d.message).join('; ') || '',
      }))
    })

    // ── OSD stats ─────────────────────────────────────────────────────────────
    const osdStats = computed(() => {
      const osdmap = cephStatus.value?.osdmap
      if (!osdmap) return { total: 0, up: 0, in: 0 }
      return {
        total: osdmap.num_osds || 0,
        up: osdmap.num_up_osds || 0,
        in: osdmap.num_in_osds || 0,
      }
    })

    const monCount = computed(() => {
      return cephStatus.value?.monmap?.num_mons || cephMons.value.length || 0
    })

    const pgCount = computed(() => {
      return cephStatus.value?.pgmap?.num_pgs || 0
    })

    const bytesTotal = computed(() => cephStatus.value?.pgmap?.bytes_total || 0)
    const bytesUsed = computed(() => cephStatus.value?.pgmap?.bytes_used || 0)
    const bytesAvail = computed(() => cephStatus.value?.pgmap?.bytes_avail || 0)

    const usedPercent = computed(() => {
      if (!bytesTotal.value) return 0
      return Math.round((bytesUsed.value / bytesTotal.value) * 100)
    })

    // ── OSD tree ──────────────────────────────────────────────────────────────
    const flatOsds = computed(() => {
      if (!cephOsds.value) return []
      // Proxmox returns an object with a 'tree' and 'nodes' array
      const nodes = cephOsds.value.nodes || cephOsds.value
      if (!Array.isArray(nodes)) return []
      return nodes.filter(n => n.type === 'osd' || n.osd !== undefined)
    })

    const osdHosts = computed(() => {
      if (!cephOsds.value) return []
      const allNodes = cephOsds.value.nodes || cephOsds.value
      if (!Array.isArray(allNodes)) return []

      const hostNodes = allNodes.filter(n => n.type === 'host')
      if (hostNodes.length > 0) {
        return hostNodes.map(h => ({
          name: h.name,
          osds: allNodes.filter(n => (n.type === 'osd' || n.osd !== undefined) &&
            (h.children || []).includes(n.id)),
        })).filter(h => h.osds.length > 0)
      }

      // Fallback: group by host field on OSD entries
      const osdList = allNodes.filter(n => n.osd !== undefined)
      const byHost = {}
      for (const osd of osdList) {
        const key = osd.host || 'unknown'
        if (!byHost[key]) byHost[key] = []
        byHost[key].push(osd)
      }
      return Object.entries(byHost).map(([name, osds]) => ({ name, osds }))
    })

    // ── Config items ──────────────────────────────────────────────────────────
    const configItems = computed(() => {
      if (!cephStatus.value) return []
      const s = cephStatus.value
      return [
        { key: 'fsid', label: 'FSID', value: s.fsid || '—', editable: false },
        { key: 'health_status', label: 'Health Status', value: healthStatus.value, editable: false },
        { key: 'osd_total', label: 'Total OSDs', value: osdStats.value.total, editable: false },
        { key: 'osd_up', label: 'OSDs Up', value: osdStats.value.up, editable: false },
        { key: 'osd_in', label: 'OSDs In', value: osdStats.value.in, editable: false },
        { key: 'mon_count', label: 'Monitor Count', value: monCount.value, editable: false },
        { key: 'pg_count', label: 'PG Count', value: pgCount.value, editable: false },
        { key: 'bytes_total', label: 'Total Space', value: formatBytes(bytesTotal.value), editable: false },
        { key: 'bytes_used', label: 'Used Space', value: formatBytes(bytesUsed.value), editable: false },
        { key: 'bytes_avail', label: 'Available Space', value: formatBytes(bytesAvail.value), editable: false },
        { key: 'used_pct', label: 'Used %', value: usedPercent.value + '%', editable: false },
        {
          key: 'election_epoch',
          label: 'Election Epoch',
          value: s.election_epoch || s.monmap?.epoch || '—',
          editable: false,
        },
      ]
    })

    // ── Helpers ───────────────────────────────────────────────────────────────
    function formatBytes(bytes) {
      if (!bytes || bytes === 0) return '0 B'
      const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
      let i = 0
      let val = bytes
      while (val >= 1024 && i < units.length - 1) {
        val /= 1024
        i++
      }
      return `${val.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
    }

    function formatOps(val) {
      if (val === undefined || val === null) return '—'
      if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M'
      if (val >= 1000) return (val / 1000).toFixed(1) + 'K'
      return String(val)
    }

    // ── Data fetching ─────────────────────────────────────────────────────────
    async function fetchHosts() {
      loadingHosts.value = true
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = res.data || []
      } catch (e) {
        toast.error('Failed to load hosts')
      } finally {
        loadingHosts.value = false
      }
    }

    async function fetchNodes() {
      if (!selectedHostId.value) return
      loadingNodes.value = true
      nodes.value = []
      try {
        const res = await api.pveNode.clusterResources(selectedHostId.value, 'node')
        nodes.value = res.data || []
      } catch (e) {
        toast.error('Failed to load nodes')
      } finally {
        loadingNodes.value = false
      }
    }

    async function fetchStatus() {
      if (!selectedHostId.value || !selectedNode.value) return
      loadingStatus.value = true
      statusError.value = ''
      try {
        const res = await api.storage.getCephStatus(selectedHostId.value, selectedNode.value)
        cephStatus.value = res.data
      } catch (e) {
        statusError.value = e?.response?.data?.detail || 'Failed to fetch Ceph status'
        cephStatus.value = null
      } finally {
        loadingStatus.value = false
      }
    }

    async function fetchOsds() {
      if (!selectedHostId.value || !selectedNode.value) return
      loadingOsds.value = true
      osdsError.value = ''
      try {
        const res = await api.storage.getCephOsds(selectedHostId.value, selectedNode.value)
        cephOsds.value = res.data
      } catch (e) {
        osdsError.value = e?.response?.data?.detail || 'Failed to fetch OSD data'
        cephOsds.value = null
      } finally {
        loadingOsds.value = false
      }
    }

    async function fetchPools() {
      if (!selectedHostId.value || !selectedNode.value) return
      loadingPools.value = true
      poolsError.value = ''
      try {
        const res = await api.storage.getCephPools(selectedHostId.value, selectedNode.value)
        cephPools.value = res.data || []
      } catch (e) {
        poolsError.value = e?.response?.data?.detail || 'Failed to fetch pools'
        cephPools.value = []
      } finally {
        loadingPools.value = false
      }
    }

    async function fetchMons() {
      if (!selectedHostId.value || !selectedNode.value) return
      loadingMons.value = true
      monsError.value = ''
      try {
        const res = await api.storage.getCephMons(selectedHostId.value, selectedNode.value)
        cephMons.value = res.data || []
      } catch (e) {
        monsError.value = e?.response?.data?.detail || 'Failed to fetch monitors'
        cephMons.value = []
      } finally {
        loadingMons.value = false
      }
    }

    async function refreshAll() {
      await Promise.all([fetchStatus(), fetchOsds(), fetchPools(), fetchMons()])
    }

    function switchTab(id) {
      activeTab.value = id
    }

    function onHostChange() {
      selectedNode.value = ''
      cephStatus.value = null
      cephOsds.value = null
      cephPools.value = []
      cephMons.value = []
      fetchNodes()
    }

    function onNodeChange() {
      refreshAll()
    }

    // ── Pool actions ──────────────────────────────────────────────────────────
    function openCreatePool() {
      newPool.value = { name: '', type: 'replicated', size: 3, pg_num: 128 }
      showCreatePool.value = true
    }

    async function createPool() {
      if (!newPool.value.name) return
      creatingPool.value = true
      try {
        await api.storage.createCephPool(selectedHostId.value, selectedNode.value, {
          name: newPool.value.name,
          pg_num: newPool.value.pg_num,
          size: newPool.value.size,
        })
        toast.success(`Pool '${newPool.value.name}' created`)
        showCreatePool.value = false
        await fetchPools()
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Failed to create pool')
      } finally {
        creatingPool.value = false
      }
    }

    function confirmDeletePool(pool) {
      poolToDelete.value = pool
      deleteConfirmName.value = ''
      showDeletePool.value = true
    }

    async function deletePool() {
      if (!poolToDelete.value) return
      const name = poolToDelete.value.pool_name || poolToDelete.value.pool
      if (deleteConfirmName.value !== name) return
      deletingPool.value = true
      try {
        await api.storage.deleteCephPool(selectedHostId.value, selectedNode.value, name)
        toast.success(`Pool '${name}' deleted`)
        showDeletePool.value = false
        await fetchPools()
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Failed to delete pool')
      } finally {
        deletingPool.value = false
      }
    }

    // ── OSD actions ───────────────────────────────────────────────────────────
    function osdAction(osd, action) {
      pendingOsd.value = osd
      pendingAction.value = action
      showOsdAction.value = true
    }

    async function executeOsdAction() {
      if (!pendingOsd.value) return
      executingOsdAction.value = true
      try {
        await api.storage.cephOsdAction(
          selectedHostId.value,
          selectedNode.value,
          pendingOsd.value.osd,
          pendingAction.value
        )
        toast.success(`OSD ${pendingOsd.value.osd} marked ${pendingAction.value}`)
        showOsdAction.value = false
        await fetchOsds()
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'OSD action failed')
      } finally {
        executingOsdAction.value = false
      }
    }

    // ── Config editing (read-only display in this version) ────────────────────
    function startEdit(item) {
      editingKey.value = item.key
      editValue.value = String(item.value)
    }

    async function saveConfig(item) {
      toast.info('Config editing requires direct Ceph CLI access — not available via Proxmox API')
      editingKey.value = null
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────
    onMounted(() => {
      fetchHosts()
    })

    return {
      hosts, nodes, selectedHostId, selectedNode, loadingHosts, loadingNodes,
      activeTab, tabs,
      cephStatus, loadingStatus, statusError,
      cephOsds, loadingOsds, osdsError,
      cephPools, loadingPools, poolsError,
      cephMons, loadingMons, monsError,
      loading,
      healthStatus, healthClass, healthIcon, healthSummary, healthChecks,
      osdStats, monCount, pgCount, bytesTotal, bytesUsed, bytesAvail, usedPercent,
      flatOsds, osdHosts,
      configItems, editingKey, editValue,
      showCreatePool, creatingPool, newPool,
      showDeletePool, deletingPool, poolToDelete, deleteConfirmName,
      showOsdAction, executingOsdAction, pendingOsd, pendingAction,
      formatBytes, formatOps,
      refreshAll, switchTab, onHostChange, onNodeChange,
      openCreatePool, createPool, confirmDeletePool, deletePool,
      osdAction, executeOsdAction,
      startEdit, saveConfig,
    }
  }
}
</script>

<style scoped>
.ceph-manager {
  padding: 1.5rem;
  max-width: 1400px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.page-header h1 {
  margin: 0 0 0.25rem;
  font-size: 1.6rem;
  font-weight: 700;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

/* ── Selector card ── */
.selector-card {
  margin-bottom: 1rem;
}

.selector-row {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.selector-item {
  flex: 1;
  min-width: 220px;
}

/* ── Tab bar ── */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color, #e2e8f0);
  margin-bottom: 1.5rem;
  overflow-x: auto;
}

.tab-btn {
  padding: 0.6rem 1.2rem;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-muted, #718096);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  white-space: nowrap;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover {
  color: var(--text-primary, #2d3748);
}

.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
  font-weight: 600;
}

/* ── Cards ── */
.card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.card-header h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.card-subtitle {
  margin: -0.5rem 0 0.75rem;
  font-size: 0.85rem;
  color: var(--text-muted, #718096);
}

/* ── Health banner ── */
.health-banner {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
}

.health-ok { border-left: 4px solid #22c55e; }
.health-warn { border-left: 4px solid #f59e0b; }
.health-err { border-left: 4px solid #ef4444; }
.health-unknown { border-left: 4px solid #94a3b8; }

.health-main {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.health-icon {
  font-size: 2rem;
}

.health-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, #718096);
  font-weight: 600;
}

.health-status {
  font-size: 1.4rem;
  font-weight: 700;
}

.health-summary {
  font-size: 0.9rem;
  color: var(--text-muted, #718096);
  flex: 1;
  padding-top: 0.25rem;
}

/* ── Stats grid ── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.stat-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  text-align: center;
}

.stat-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, #718096);
  font-weight: 600;
  margin-bottom: 0.35rem;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
}

/* ── Usage bar ── */
.usage-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.usage-bar {
  flex: 1;
  height: 14px;
  background: var(--border-color, #e2e8f0);
  border-radius: 7px;
  overflow: hidden;
}

.usage-fill {
  height: 100%;
  border-radius: 7px;
  transition: width 0.4s ease;
}

.usage-fill-ok { background: #22c55e; }
.usage-fill-warn { background: #f59e0b; }
.usage-fill-danger { background: #ef4444; }

.usage-pct {
  font-size: 0.9rem;
  font-weight: 600;
  min-width: 3.5rem;
  text-align: right;
}

/* ── Health details ── */
.health-detail-row {
  display: flex;
  gap: 0.75rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  align-items: flex-start;
}

.health-detail-row:last-child { border-bottom: none; }

.hd-severity {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.15rem 0.4rem;
  border-radius: 0.25rem;
  white-space: nowrap;
  min-width: 90px;
  text-align: center;
}

.health-detail-health_ok .hd-severity { background: #dcfce7; color: #166534; }
.health-detail-health_warn .hd-severity { background: #fef3c7; color: #92400e; }
.health-detail-health_err .hd-severity { background: #fee2e2; color: #991b1b; }

.hd-summary {
  font-weight: 500;
  font-size: 0.9rem;
}

.hd-detail {
  font-size: 0.8rem;
  color: var(--text-muted, #718096);
  margin-top: 0.2rem;
}

/* ── OSD tree ── */
.osd-tree {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.osd-host-block {
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.5rem;
  padding: 0.75rem;
  min-width: 160px;
  flex: 1;
}

.osd-host-label {
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.osd-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.osd-chip {
  font-size: 0.7rem;
  padding: 0.2rem 0.4rem;
  border-radius: 0.25rem;
  cursor: default;
  font-weight: 600;
}

.osd-chip-ok { background: #dcfce7; color: #166534; }
.osd-chip-down { background: #fee2e2; color: #991b1b; }
.osd-chip-out { background: #fef3c7; color: #92400e; }

/* ── Quorum ── */
.quorum-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  padding: 0.5rem 0;
}

.quorum-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
  padding: 0.75rem 1.25rem;
  border-radius: 0.5rem;
  min-width: 100px;
  border: 2px solid transparent;
}

.quorum-ok {
  background: #f0fdf4;
  border-color: #22c55e;
}

.quorum-warn {
  background: #fefce8;
  border-color: #eab308;
}

.quorum-icon {
  font-size: 1.4rem;
  font-weight: 700;
}

.quorum-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.quorum-rank {
  font-size: 0.75rem;
  color: var(--text-muted, #718096);
}

/* ── Config grid ── */
.config-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  flex-wrap: wrap;
}

.config-row:last-child { border-bottom: none; }

.config-key {
  flex: 0 0 220px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted, #718096);
}

.config-value {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  flex-wrap: wrap;
}

.config-val-text {
  font-family: monospace;
  font-size: 0.9rem;
}

.config-input {
  max-width: 300px;
}

/* ── Table ── */
.table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.data-table th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 2px solid var(--border-color, #e2e8f0);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #718096);
  white-space: nowrap;
}

.data-table td {
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  vertical-align: middle;
}

.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: var(--row-hover, #f8fafc); }

/* ── Badges ── */
.badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.badge-success { background: #dcfce7; color: #166534; }
.badge-danger { background: #fee2e2; color: #991b1b; }
.badge-warning { background: #fef3c7; color: #92400e; }
.badge-secondary { background: #e2e8f0; color: #475569; }

/* ── Buttons ── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: background 0.15s, opacity 0.15s;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-secondary { background: #e2e8f0; color: #475569; }
.btn-secondary:hover:not(:disabled) { background: #cbd5e1; }
.btn-danger { background: #ef4444; color: #fff; }
.btn-danger:hover:not(:disabled) { background: #dc2626; }
.btn-sm { padding: 0.35rem 0.75rem; font-size: 0.8rem; }
.btn-xs { padding: 0.2rem 0.5rem; font-size: 0.72rem; }

/* ── Action buttons group ── */
.action-btns {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-box {
  background: var(--card-bg, #fff);
  border-radius: 0.5rem;
  width: 100%;
  max-width: 500px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.25);
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  overflow: hidden;
}

.modal-box-sm { max-width: 400px; }

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

.modal-header h3 { margin: 0; font-size: 1.1rem; }

.modal-close {
  background: none;
  border: none;
  font-size: 1.4rem;
  cursor: pointer;
  color: var(--text-muted, #718096);
  line-height: 1;
  padding: 0;
}

.modal-body {
  padding: 1.25rem;
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid var(--border-color, #e2e8f0);
}

/* ── Form ── */
.form-group { margin-bottom: 1rem; }
.form-label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.3rem; }
.required { color: #ef4444; }

.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  background: var(--input-bg, #fff);
  color: var(--text-primary, #1a202c);
  box-sizing: border-box;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
}

.form-control-sm { padding: 0.3rem 0.5rem; font-size: 0.8rem; }

/* ── States ── */
.loading-state, .empty-state, .error-state, .empty-placeholder {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted, #718096);
}

.error-state { color: #ef4444; }

/* ── Misc ── */
.text-muted { color: var(--text-muted, #718096); }
.text-success { color: #22c55e; }
.text-warning { color: #f59e0b; }
.text-danger { color: #ef4444; }
.text-small { font-size: 0.8rem; }
.text-mono { font-family: monospace; }
.ml-1 { margin-left: 0.25rem; }
.ml-2 { margin-left: 0.5rem; }
.mt-3 { margin-top: 0.75rem; }
.p-3 { padding: 0.75rem; }

@media (max-width: 640px) {
  .ceph-manager { padding: 1rem; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .config-key { flex: 0 0 140px; }
}
</style>
