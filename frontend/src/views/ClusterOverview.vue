<template>
  <div class="cluster-overview-page">
    <div class="page-header mb-2">
      <h2>Cluster Overview</h2>
      <div class="header-right">
        <p class="text-muted">Status and resources for Proxmox host {{ hostId }}</p>
        <div class="refresh-control">
          <span class="countdown-badge" :class="{ 'countdown-urgent': refreshCountdown <= 5 }">
            Refreshing in {{ refreshCountdown }}s
          </span>
          <button @click="manualRefresh" class="btn btn-outline btn-sm">Refresh Now</button>
        </div>
      </div>
    </div>

    <!-- Cluster status + node list -->
    <div class="summary-grid mb-2">
      <!-- Cluster status card -->
      <div class="card">
        <div class="card-header">
          <h3>Cluster Status</h3>
        </div>
        <div v-if="loadingStatus" class="loading-spinner"></div>
        <div v-else class="card-body">
          <div v-if="clusterNodes.length === 0" class="text-muted text-sm">No cluster data.</div>
          <div v-else class="node-list">
            <div v-for="item in clusterNodes" :key="item.name || item.id" class="node-card">
              <div class="node-card-header">
                <span class="node-name">{{ item.name }}</span>
                <div class="node-card-actions">
                  <span v-if="maintenanceNodes.has(item.name)" class="badge badge-warning">Maintenance</span>
                  <span :class="['badge', item.online ? 'badge-success' : 'badge-danger']">
                    {{ item.online ? 'Online' : 'Offline' }}
                  </span>
                  <button
                    class="btn btn-outline btn-xs"
                    @click.stop="navigateToNode(item.name)"
                    title="View node details"
                  >
                    View
                  </button>
                  <button
                    v-if="item.online"
                    class="btn btn-xs"
                    :class="maintenanceNodes.has(item.name) ? 'btn-success' : 'btn-warning'"
                    @click.stop="toggleMaintenance(item.name)"
                    title="Toggle maintenance mode"
                  >
                    {{ maintenanceNodes.has(item.name) ? 'Exit Maint.' : 'Maintenance' }}
                  </button>
                </div>
              </div>
              <div class="node-card-meta text-sm text-muted">
                <span v-if="item.level">Level: {{ item.level }}</span>
                <span v-if="item.quorate !== undefined" class="ml-1">
                  Quorate: <strong>{{ item.quorate ? 'Yes' : 'No' }}</strong>
                </span>
                <span v-if="item.nodeid !== undefined" class="ml-1">
                  Node ID: {{ item.nodeid }}
                </span>
              </div>
              <!-- Per-node CPU and memory from cluster resources -->
              <div v-if="nodeStats[item.name]" class="node-resource-bars mt-1">
                <div class="node-bar-row">
                  <span class="node-bar-label text-xs">CPU</span>
                  <div class="mini-bar-wrap mini-bar-wrap--sm">
                    <div
                      class="mini-bar-fill"
                      :class="barClass(nodeStats[item.name].cpuRatio)"
                      :style="{ width: Math.round(nodeStats[item.name].cpuRatio * 100) + '%' }"
                    ></div>
                  </div>
                  <span class="text-xs text-muted node-bar-pct">{{ Math.round(nodeStats[item.name].cpuRatio * 100) }}%</span>
                </div>
                <div class="node-bar-row">
                  <span class="node-bar-label text-xs">MEM</span>
                  <div class="mini-bar-wrap mini-bar-wrap--sm">
                    <div
                      class="mini-bar-fill"
                      :class="barClass(nodeStats[item.name].memRatio)"
                      :style="{ width: Math.round(nodeStats[item.name].memRatio * 100) + '%' }"
                    ></div>
                  </div>
                  <span class="text-xs text-muted node-bar-pct">{{ Math.round(nodeStats[item.name].memRatio * 100) }}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Resource summary card -->
      <div class="card">
        <div class="card-header">
          <h3>Resource Summary</h3>
        </div>
        <div v-if="loadingResources" class="loading-spinner"></div>
        <div v-else class="card-body">
          <div class="summary-stats">
            <div class="stat-item">
              <div class="stat-value">{{ summary.vmsTotal }}</div>
              <div class="stat-label">Total VMs</div>
            </div>
            <div class="stat-item stat-item--green">
              <div class="stat-value">{{ summary.vmsRunning }}</div>
              <div class="stat-label">Running VMs</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ summary.ctsTotal }}</div>
              <div class="stat-label">Total CTs</div>
            </div>
            <div class="stat-item stat-item--green">
              <div class="stat-value">{{ summary.ctsRunning }}</div>
              <div class="stat-label">Running CTs</div>
            </div>
          </div>
          <div class="resource-bars">
            <div class="resource-row">
              <div class="resource-label text-sm">
                CPU: {{ summary.cpuUsed.toFixed(1) }} / {{ summary.cpuTotal }} cores
              </div>
              <div class="mini-bar-wrap">
                <div
                  class="mini-bar-fill"
                  :class="barClass(summary.cpuTotal ? summary.cpuUsed / summary.cpuTotal : 0)"
                  :style="{ width: cpuPct + '%' }"
                ></div>
              </div>
              <div class="text-xs text-muted">{{ cpuPct }}%</div>
            </div>
            <div class="resource-row">
              <div class="resource-label text-sm">
                RAM: {{ formatBytes(summary.memUsed) }} / {{ formatBytes(summary.memTotal) }}
              </div>
              <div class="mini-bar-wrap">
                <div
                  class="mini-bar-fill"
                  :class="barClass(summary.memTotal ? summary.memUsed / summary.memTotal : 0)"
                  :style="{ width: memPct + '%' }"
                ></div>
              </div>
              <div class="text-xs text-muted">{{ memPct }}%</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Node Balance Chart -->
    <div class="card mb-2">
      <div class="card-header" @click="balanceExpanded = !balanceExpanded" style="cursor:pointer;">
        <h3>Node Balance</h3>
        <div class="flex gap-1 align-center">
          <button
            v-if="balanceExpanded"
            class="btn btn-outline btn-sm"
            @click.stop="suggestRebalance"
            :disabled="rebalancing"
          >
            Suggest Rebalance
          </button>
          <span class="toggle-icon">{{ balanceExpanded ? '▲' : '▼' }}</span>
        </div>
      </div>
      <div v-if="balanceExpanded" class="card-body">
        <!-- Bar chart per node -->
        <div class="balance-chart">
          <div v-for="(nstat, nname) in nodeStats" :key="nname" class="balance-node-col">
            <div class="balance-bars">
              <div class="balance-bar-group">
                <div class="balance-bar-label text-xs text-muted">CPU</div>
                <div class="balance-bar-track">
                  <div
                    class="balance-bar-fill"
                    :class="barClass(nstat.cpuRatio)"
                    :style="{ height: Math.round(nstat.cpuRatio * 100) + '%' }"
                  ></div>
                </div>
                <div class="balance-bar-pct text-xs">{{ Math.round(nstat.cpuRatio * 100) }}%</div>
              </div>
              <div class="balance-bar-group">
                <div class="balance-bar-label text-xs text-muted">MEM</div>
                <div class="balance-bar-track">
                  <div
                    class="balance-bar-fill"
                    :class="barClass(nstat.memRatio)"
                    :style="{ height: Math.round(nstat.memRatio * 100) + '%' }"
                  ></div>
                </div>
                <div class="balance-bar-pct text-xs">{{ Math.round(nstat.memRatio * 100) }}%</div>
              </div>
            </div>
            <div class="balance-node-name text-sm">{{ nname }}</div>
          </div>
        </div>

        <!-- Rebalance suggestion -->
        <div v-if="rebalanceSuggestions.length" class="rebalance-panel mt-2">
          <div class="rebalance-header">
            <strong class="text-sm">Suggested Migrations</strong>
            <button
              class="btn btn-primary btn-sm"
              @click="applyRebalance"
              :disabled="applyingRebalance"
            >
              {{ applyingRebalance ? 'Applying...' : 'Apply All' }}
            </button>
          </div>
          <div v-for="(sug, i) in rebalanceSuggestions" :key="i" class="rebalance-item text-sm">
            <span class="text-muted">VM {{ sug.vmid }}</span>
            <span class="rebalance-arrow">{{ sug.from }} &rarr; {{ sug.to }}</span>
            <button class="btn btn-outline btn-xs" @click="applySingleMigration(sug)">Migrate</button>
          </div>
          <div v-if="rebalanceMsg" class="text-sm mt-1" :class="rebalanceErr ? 'text-danger' : 'text-success'">
            {{ rebalanceMsg }}
          </div>
        </div>
        <div v-else-if="rebalanceAnalyzed" class="text-muted text-sm mt-1">
          Cluster is balanced — no migrations recommended.
        </div>
      </div>
    </div>

    <!-- Live Migrations panel -->
    <div class="card mb-2">
      <div class="card-header" @click="liveMigrationsExpanded = !liveMigrationsExpanded" style="cursor:pointer;">
        <h3>
          Live Migrations
          <span v-if="runningMigrations.length" class="badge badge-warning ml-1">{{ runningMigrations.length }} running</span>
        </h3>
        <span class="toggle-icon">{{ liveMigrationsExpanded ? '▲' : '▼' }}</span>
      </div>
      <div v-if="liveMigrationsExpanded" class="card-body">
        <!-- Running migrations -->
        <div v-if="runningMigrations.length" class="mb-2">
          <div class="text-sm font-semibold mb-1">Currently Running</div>
          <div v-for="m in runningMigrations" :key="m.upid" class="migration-running-item">
            <div class="migration-info">
              <strong>VM {{ m.id || m.vmid }}</strong>
              <span class="text-muted text-sm ml-1">{{ m._node }} &rarr; {{ extractTarget(m.upid) }}</span>
            </div>
            <div class="migration-progress-wrap">
              <div class="migration-progress-bar">
                <div class="migration-progress-fill anim-pulse" style="width: 100%"></div>
              </div>
              <span class="text-xs text-muted">Running</span>
            </div>
          </div>
        </div>
        <div v-else class="text-muted text-sm mb-2">No migrations currently running.</div>

        <!-- Recent migration history -->
        <div class="text-sm font-semibold mb-1">Recent Migrations (last 10)</div>
        <div v-if="recentMigrations.length === 0" class="text-muted text-sm">No recent migrations.</div>
        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>VMID</th>
                <th>Node</th>
                <th>Started</th>
                <th>Status</th>
                <th>UPID</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in recentMigrations" :key="m.upid">
                <td>{{ m.id || m.vmid || '—' }}</td>
                <td class="text-sm text-muted">{{ m._node }}</td>
                <td class="text-sm text-muted">{{ m.starttime ? new Date(m.starttime * 1000).toLocaleString() : '—' }}</td>
                <td>
                  <span :class="migrationBadge(m.status)">{{ m.status || 'running' }}</span>
                </td>
                <td class="text-xs text-muted" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;">{{ m.upid }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Migrate VM panel -->
    <div class="card mb-2">
      <div class="card-header" @click="migrationExpanded = !migrationExpanded" style="cursor:pointer;">
        <h3>Migrate VM</h3>
        <span class="toggle-icon">{{ migrationExpanded ? '▲' : '▼' }}</span>
      </div>
      <div v-if="migrationExpanded" class="card-body">
        <div v-if="loadingResources" class="text-muted text-sm">Loading VM list...</div>
        <div v-else>
          <div class="migration-form">
            <div class="form-group">
              <label class="form-label">Virtual Machine</label>
              <select v-model="migrateVmid" class="form-control">
                <option value="">-- Select VM --</option>
                <option
                  v-for="vm in migrateableVms"
                  :key="vm.vmid"
                  :value="vm.vmid"
                >
                  {{ vm.vmid }} — {{ vm.name || 'unnamed' }} ({{ vm.node }})
                </option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Target Node</label>
              <select v-model="migrateTarget" class="form-control">
                <option value="">-- Select target node --</option>
                <option
                  v-for="node in migrateTargetNodes"
                  :key="node.name"
                  :value="node.name"
                >
                  {{ node.name }}{{ node.online ? '' : ' (offline)' }}
                </option>
              </select>
            </div>

            <div class="form-group form-group--inline">
              <label class="form-label checkbox-label">
                <input type="checkbox" v-model="migrateOnline" class="form-check" />
                Online migration (live, no downtime)
              </label>
            </div>

            <div class="form-group">
              <button
                class="btn btn-primary"
                :disabled="!migrateVmid || !migrateTarget || migrating"
                @click="doMigrate"
              >
                <span v-if="migrating">Migrating...</span>
                <span v-else>Migrate VM</span>
              </button>
              <span v-if="migrateError" class="migrate-error text-sm ml-1">{{ migrateError }}</span>
              <span v-if="migrateSuccess" class="migrate-success text-sm ml-1">{{ migrateSuccess }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Maintenance Mode / Node Evacuation -->
    <div v-if="evacuationNode" class="card mb-2">
      <div class="card-header">
        <h3>Evacuate Node: {{ evacuationNode }}</h3>
      </div>
      <div class="card-body">
        <p class="text-sm text-muted mb-2">
          This will migrate all VMs off <strong>{{ evacuationNode }}</strong> to other online nodes.
        </p>
        <div class="flex gap-1 align-center mb-2">
          <div class="form-group" style="min-width:200px;margin-bottom:0;">
            <label class="form-label">Target Node (optional)</label>
            <select v-model="evacuateTarget" class="form-control">
              <option value="">Auto (round-robin)</option>
              <option v-for="n in evacuationTargets" :key="n.name" :value="n.name">{{ n.name }}</option>
            </select>
          </div>
          <button
            class="btn btn-danger"
            :disabled="evacuating"
            @click="doEvacuate"
          >
            {{ evacuating ? 'Evacuating...' : 'Start Evacuation' }}
          </button>
          <button class="btn btn-outline" @click="evacuationNode = null">Cancel</button>
        </div>
        <div v-if="evacuationResult" class="evacuation-result text-sm">
          <div v-if="evacuationResult.queued && evacuationResult.queued.length">
            <strong>Queued {{ evacuationResult.queued.length }} migrations:</strong>
            <div v-for="q in evacuationResult.queued" :key="q.vmid" class="text-muted">
              VM {{ q.vmid }} → {{ q.target }}
            </div>
          </div>
          <div v-if="evacuationResult.errors && evacuationResult.errors.length" class="text-danger mt-1">
            <strong>Errors:</strong>
            <div v-for="e in evacuationResult.errors" :key="e.vmid">
              VM {{ e.vmid }}: {{ e.error }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Cluster Join Wizard (admin only) -->
    <div v-if="isAdmin" class="card mb-2">
      <div class="card-header" @click="joinWizardExpanded = !joinWizardExpanded" style="cursor:pointer;">
        <h3>Cluster Join Wizard</h3>
        <span class="toggle-icon">{{ joinWizardExpanded ? '▲' : '▼' }}</span>
      </div>
      <div v-if="joinWizardExpanded" class="card-body">
        <!-- Step 1 -->
        <div v-if="joinStep === 1">
          <p class="text-sm text-muted mb-2">
            Step 1: Enter the new node's hostname/IP and root password to generate the join command.
          </p>
          <div class="migration-form">
            <div class="form-group">
              <label class="form-label">New Node IP / Hostname</label>
              <input v-model="joinNodeIp" class="form-control" placeholder="192.168.1.50" />
            </div>
            <div class="form-group">
              <label class="form-label">Cluster Password</label>
              <input v-model="joinPassword" type="password" class="form-control" placeholder="Proxmox cluster password" />
            </div>
            <div class="form-group">
              <button class="btn btn-primary" :disabled="!joinNodeIp || !joinPassword" @click="generateJoinCommand">
                Generate Join Command
              </button>
            </div>
          </div>
        </div>

        <!-- Step 2 -->
        <div v-if="joinStep === 2">
          <p class="text-sm text-muted mb-2">
            Step 2: Run this command on the new node (<strong>{{ joinNodeIp }}</strong>) as root:
          </p>
          <pre class="join-command">{{ joinCommand }}</pre>
          <div class="flex gap-1 mt-2">
            <button class="btn btn-primary" @click="joinStep = 3; startJoinVerification()">
              Node is joined — Verify
            </button>
            <button class="btn btn-outline" @click="joinStep = 1">Back</button>
          </div>
        </div>

        <!-- Step 3 -->
        <div v-if="joinStep === 3">
          <p class="text-sm text-muted mb-2">
            Step 3: Verifying that <strong>{{ joinNodeIp }}</strong> appears in the cluster...
          </p>
          <div v-if="joinVerifying" class="flex align-center gap-1">
            <div class="loading-spinner-sm"></div>
            <span class="text-sm text-muted">Polling cluster nodes...</span>
          </div>
          <div v-if="joinVerified" class="text-success text-sm">
            Node joined successfully! The new node is now visible in the cluster.
          </div>
          <div v-if="joinVerifyFail" class="text-danger text-sm">
            Node not yet visible. Check if the join command was run correctly.
          </div>
          <div class="flex gap-1 mt-2">
            <button class="btn btn-outline" @click="resetJoinWizard">Start Over</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Resource table -->
    <div class="card mb-2">
      <div class="card-header">
        <h3>All Resources</h3>
        <div class="flex gap-1 align-center">
          <input
            v-model="resourceSearch"
            class="form-control search-input"
            placeholder="Search by name or VMID..."
          />
        </div>
      </div>

      <div v-if="loadingResources" class="loading-spinner"></div>

      <div v-else-if="filteredResources.length === 0" class="text-center text-muted p-3">
        No resources found.
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>VMID</th>
              <th>Name</th>
              <th>Node</th>
              <th>Type</th>
              <th>Status</th>
              <th>CPU %</th>
              <th>RAM</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in filteredResources"
              :key="r.id || r.vmid"
              class="resource-row-link"
              @click="navigateToResource(r)"
            >
              <td><strong>{{ r.vmid || '—' }}</strong></td>
              <td>{{ r.name || '—' }}</td>
              <td>{{ r.node || '—' }}</td>
              <td>
                <span :class="['badge', r.type === 'lxc' ? 'badge-warning' : 'badge-info']">
                  {{ r.type === 'lxc' ? 'CT' : 'VM' }}
                </span>
              </td>
              <td>
                <span :class="['badge', r.status === 'running' ? 'badge-success' : 'badge-danger']">
                  {{ r.status || '—' }}
                </span>
              </td>
              <td>{{ r.cpu != null ? (r.cpu * 100).toFixed(1) + '%' : '—' }}</td>
              <td>{{ r.mem != null ? formatBytes(r.mem) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Cluster Firewall Rules -->
    <div class="card">
      <div class="card-header">
        <h3>Cluster Firewall Rules</h3>
      </div>
      <div v-if="loadingFirewall" class="loading-spinner"></div>
      <div v-else-if="firewallRules.length === 0" class="text-center text-muted p-3">
        No cluster firewall rules configured.
      </div>
      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Pos</th>
              <th>Direction</th>
              <th>Action</th>
              <th>Protocol</th>
              <th>Source</th>
              <th>Destination</th>
              <th>Ports</th>
              <th>Comment</th>
              <th>Enabled</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(rule, idx) in firewallRules" :key="rule.pos ?? idx">
              <td><strong>{{ rule.pos ?? idx }}</strong></td>
              <td>
                <span :class="['badge', rule.type === 'out' ? 'badge-warning' : 'badge-info']">
                  {{ (rule.type || 'in').toUpperCase() }}
                </span>
              </td>
              <td>
                <span :class="['badge', actionBadge(rule.action)]">{{ rule.action || '—' }}</span>
              </td>
              <td>{{ rule.proto || 'any' }}</td>
              <td class="text-sm">{{ rule.source || '—' }}</td>
              <td class="text-sm">{{ rule.dest || '—' }}</td>
              <td class="text-sm">
                <span v-if="rule.dport || rule.sport">
                  <span v-if="rule.dport">dst:{{ rule.dport }}</span>
                  <span v-if="rule.sport"> src:{{ rule.sport }}</span>
                </span>
                <span v-else>—</span>
              </td>
              <td class="text-sm">{{ rule.comment || '—' }}</td>
              <td>
                <span :class="['badge', rule.enable == 1 || rule.enable === true ? 'badge-success' : 'badge-danger']">
                  {{ rule.enable == 1 || rule.enable === true ? 'Yes' : 'No' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import { useAuthStore } from '@/store/auth'
import api from '@/services/api'
import { formatBytes } from '@/utils/proxmox'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const authStore = useAuthStore()

const hostId = ref(route.params.hostId)
const isAdmin = computed(() => authStore.isAdmin)

const clusterNodes = ref([])
const loadingStatus = ref(false)

const allResources = ref([])
const loadingResources = ref(false)
const resourceSearch = ref('')

const firewallRules = ref([])
const loadingFirewall = ref(false)

// Maintenance mode state (client-side toggle — tracks which nodes are in maintenance)
const maintenanceNodes = ref(new Set())

// Auto-refresh
const REFRESH_INTERVAL = 30
const refreshCountdown = ref(REFRESH_INTERVAL)
let countdownTimer = null
let refreshTimer = null

// Migration poll (every 5s)
let migrationPollTimer = null
const MIGRATION_POLL_INTERVAL = 5000

// Live migrations from task log
const runningMigrations = ref([])
const recentMigrations = ref([])
const liveMigrationsExpanded = ref(true)

// Balance
const balanceExpanded = ref(false)
const rebalancing = ref(false)
const rebalanceSuggestions = ref([])
const rebalanceAnalyzed = ref(false)
const applyingRebalance = ref(false)
const rebalanceMsg = ref('')
const rebalanceErr = ref(false)

// Migration panel
const migrationExpanded = ref(false)
const migrateVmid = ref('')
const migrateTarget = ref('')
const migrateOnline = ref(true)
const migrating = ref(false)
const migrateError = ref('')
const migrateSuccess = ref('')

// Evacuation
const evacuationNode = ref(null)
const evacuateTarget = ref('')
const evacuating = ref(false)
const evacuationResult = ref(null)

// Join wizard
const joinWizardExpanded = ref(false)
const joinStep = ref(1)
const joinNodeIp = ref('')
const joinPassword = ref('')
const joinCommand = ref('')
const joinVerifying = ref(false)
const joinVerified = ref(false)
const joinVerifyFail = ref(false)
let joinPollTimer = null

const summary = ref({
  vmsTotal: 0,
  vmsRunning: 0,
  ctsTotal: 0,
  ctsRunning: 0,
  cpuUsed: 0,
  cpuTotal: 0,
  memUsed: 0,
  memTotal: 0,
})

const cpuPct = computed(() => {
  if (!summary.value.cpuTotal) return 0
  return Math.min(100, Math.round((summary.value.cpuUsed / summary.value.cpuTotal) * 100))
})

const memPct = computed(() => {
  if (!summary.value.memTotal) return 0
  return Math.min(100, Math.round((summary.value.memUsed / summary.value.memTotal) * 100))
})

const filteredResources = computed(() => {
  const q = resourceSearch.value.trim().toLowerCase()
  const vmsCts = allResources.value.filter(r => r.type === 'qemu' || r.type === 'lxc')
  if (!q) return vmsCts
  return vmsCts.filter(r =>
    (r.name || '').toLowerCase().includes(q) ||
    String(r.vmid || '').includes(q) ||
    (r.node || '').toLowerCase().includes(q)
  )
})

// Per-node CPU/mem stats derived from cluster resources (type=node entries)
const nodeStats = computed(() => {
  const stats = {}
  for (const r of allResources.value) {
    if (r.type === 'node') {
      const cpuRatio = r.maxcpu ? (r.cpu || 0) : 0
      const memRatio = r.maxmem ? (r.mem || 0) / r.maxmem : 0
      stats[r.node || r.name] = { cpuRatio, memRatio }
    }
  }
  return stats
})

// VMs available for migration (qemu type only — LXC migration is different)
const migrateableVms = computed(() => {
  return allResources.value.filter(r => r.type === 'qemu' && r.vmid)
})

// Target nodes for migration: all online nodes except the current VM's node
const selectedVmNode = computed(() => {
  if (!migrateVmid.value) return null
  const vm = migrateableVms.value.find(v => String(v.vmid) === String(migrateVmid.value))
  return vm ? vm.node : null
})

const migrateTargetNodes = computed(() => {
  return clusterNodes.value.filter(n => n.name !== selectedVmNode.value)
})

const evacuationTargets = computed(() => {
  return clusterNodes.value.filter(n => n.online && n.name !== evacuationNode.value)
})

function barClass(ratio) {
  if (ratio >= 0.9) return 'fill--danger'
  if (ratio >= 0.75) return 'fill--warning'
  return 'fill--ok'
}

function actionBadge(action) {
  const map = { ACCEPT: 'badge-success', DROP: 'badge-danger', REJECT: 'badge-warning' }
  return map[action] || 'badge-info'
}

function migrationBadge(status) {
  if (status === 'OK') return 'badge badge-success'
  if (!status || status === 'running') return 'badge badge-warning'
  return 'badge badge-danger'
}

function extractTarget(upid) {
  // UPID format: UPID:node:pid:pstart:starttime:type:id:user@realm
  // For migration tasks the type contains target info — we just show what we can
  if (!upid) return '?'
  const parts = upid.split(':')
  return parts.length > 6 ? parts[6] || '?' : '?'
}

function navigateToResource(r) {
  if (!r.vmid || !r.node) return
  if (r.type === 'lxc') {
    router.push(`/proxmox/${hostId.value}/nodes/${r.node}/containers/${r.vmid}`)
  } else {
    router.push(`/proxmox/${hostId.value}/nodes/${r.node}/vms/${r.vmid}`)
  }
}

function navigateToNode(nodeName) {
  router.push(`/proxmox/${hostId.value}/nodes/${nodeName}`)
}

// ── Maintenance Mode ──────────────────────────────────────────────────────────

function toggleMaintenance(nodeName) {
  const inMaintenance = maintenanceNodes.value.has(nodeName)
  if (!inMaintenance) {
    // Enter maintenance — prompt evacuation
    if (!confirm(`Put ${nodeName} into maintenance mode?\n\nThis will mark the node as under maintenance. You can then evacuate all VMs off the node.`)) return
    maintenanceNodes.value = new Set([...maintenanceNodes.value, nodeName])
    toast.info(`${nodeName} is now in maintenance mode`)
    // Prompt evacuation
    evacuationNode.value = nodeName
    evacuateTarget.value = ''
    evacuationResult.value = null
  } else {
    maintenanceNodes.value = new Set([...maintenanceNodes.value].filter(n => n !== nodeName))
    toast.success(`${nodeName} exited maintenance mode`)
    if (evacuationNode.value === nodeName) evacuationNode.value = null
  }
}

// ── Node Evacuation ───────────────────────────────────────────────────────────

async function doEvacuate() {
  if (!evacuationNode.value) return
  evacuating.value = true
  evacuationResult.value = null
  try {
    const body = evacuateTarget.value ? { target: evacuateTarget.value } : {}
    const res = await api.cluster.evacuateNode(hostId.value, evacuationNode.value, body)
    evacuationResult.value = res.data
    const queued = res.data?.queued?.length || 0
    const errs = res.data?.errors?.length || 0
    if (queued > 0) toast.success(`Queued ${queued} VM migrations from ${evacuationNode.value}`)
    if (errs > 0) toast.warning(`${errs} migrations failed to queue`)
    // Refresh migration list after a moment
    setTimeout(fetchMigrationTasks, 2000)
  } catch (err) {
    const msg = err?.response?.data?.detail || err?.message || 'Evacuation failed'
    toast.error('Evacuation failed: ' + msg)
  } finally {
    evacuating.value = false
  }
}

// ── Migration ─────────────────────────────────────────────────────────────────

async function doMigrate() {
  migrateError.value = ''
  migrateSuccess.value = ''
  if (!migrateVmid.value || !migrateTarget.value) return

  const vm = migrateableVms.value.find(v => String(v.vmid) === String(migrateVmid.value))
  if (!vm) {
    migrateError.value = 'VM not found in resource list.'
    return
  }

  migrating.value = true
  try {
    await api.pveVm.migrate(hostId.value, vm.node, vm.vmid, {
      target: migrateTarget.value,
      online: migrateOnline.value ? 1 : 0,
    })
    migrateSuccess.value = `Migration of VM ${vm.vmid} to ${migrateTarget.value} initiated.`
    toast.success(migrateSuccess.value)
    migrateVmid.value = ''
    migrateTarget.value = ''
    setTimeout(fetchMigrationTasks, 2000)
  } catch (err) {
    const msg = err?.response?.data?.detail || err?.message || 'Migration failed.'
    migrateError.value = msg
    toast.error('Migration failed: ' + msg)
  } finally {
    migrating.value = false
  }
}

// ── Live migration task polling ───────────────────────────────────────────────

async function fetchMigrationTasks() {
  try {
    const res = await api.cluster.listTasks(hostId.value, { typefilter: 'qmigrate', limit: 50 })
    const tasks = res.data || []
    runningMigrations.value = tasks.filter(t => !t.status || t.status === 'running')
    recentMigrations.value = tasks
      .filter(t => t.status && t.status !== 'running')
      .slice(0, 10)
  } catch (e) {
    // silent — not critical
  }
}

function startMigrationPoll() {
  if (migrationPollTimer) return
  migrationPollTimer = setInterval(fetchMigrationTasks, MIGRATION_POLL_INTERVAL)
}

function stopMigrationPoll() {
  if (migrationPollTimer) { clearInterval(migrationPollTimer); migrationPollTimer = null }
}

// ── Rebalance ─────────────────────────────────────────────────────────────────

async function suggestRebalance() {
  rebalancing.value = true
  rebalanceSuggestions.value = []
  rebalanceAnalyzed.value = false
  rebalanceMsg.value = ''
  rebalanceErr.value = false

  try {
    // Analyse node loads
    const stats = nodeStats.value
    const nodeNames = Object.keys(stats)
    if (nodeNames.length < 2) {
      rebalanceAnalyzed.value = true
      return
    }

    // Find overloaded and underloaded nodes (by mem ratio)
    const sorted = nodeNames.map(n => ({ name: n, ...stats[n] }))
      .sort((a, b) => b.memRatio - a.memRatio)

    const overloaded = sorted[0]
    const underloaded = sorted[sorted.length - 1]
    const diff = overloaded.memRatio - underloaded.memRatio

    if (diff < 0.15) {
      // Balanced enough
      rebalanceAnalyzed.value = true
      return
    }

    // Find VMs on overloaded node that could move
    const vmsOnOverloaded = allResources.value.filter(
      r => r.type === 'qemu' && r.node === overloaded.name && r.status === 'running'
    )

    // Suggest up to 3 migrations
    const suggestions = []
    for (const vm of vmsOnOverloaded.slice(0, 3)) {
      suggestions.push({
        vmid: vm.vmid,
        name: vm.name,
        from: overloaded.name,
        to: underloaded.name,
      })
    }
    rebalanceSuggestions.value = suggestions
    rebalanceAnalyzed.value = true
  } finally {
    rebalancing.value = false
  }
}

async function applySingleMigration(sug) {
  try {
    await api.pveVm.migrate(hostId.value, sug.from, sug.vmid, { target: sug.to, online: 1 })
    toast.success(`VM ${sug.vmid} migration to ${sug.to} queued`)
    rebalanceSuggestions.value = rebalanceSuggestions.value.filter(s => s.vmid !== sug.vmid)
    setTimeout(fetchMigrationTasks, 2000)
  } catch (err) {
    toast.error(`Migration failed: ${err?.response?.data?.detail || err?.message}`)
  }
}

async function applyRebalance() {
  applyingRebalance.value = true
  rebalanceMsg.value = ''
  rebalanceErr.value = false
  let ok = 0
  let fail = 0
  for (const sug of rebalanceSuggestions.value) {
    try {
      await api.pveVm.migrate(hostId.value, sug.from, sug.vmid, { target: sug.to, online: 1 })
      ok++
    } catch {
      fail++
    }
  }
  applyingRebalance.value = false
  rebalanceSuggestions.value = []
  if (fail === 0) {
    rebalanceMsg.value = `Queued ${ok} migration(s) successfully.`
    rebalanceErr.value = false
  } else {
    rebalanceMsg.value = `${ok} queued, ${fail} failed.`
    rebalanceErr.value = true
  }
  setTimeout(fetchMigrationTasks, 2000)
}

// ── Cluster Join Wizard ───────────────────────────────────────────────────────

async function generateJoinCommand() {
  // Fetch the cluster's join info from the Proxmox API (cluster/config/join)
  try {
    const res = await api.pveNode.clusterStatus(hostId.value)
    const items = res.data || []
    const clusterItem = items.find(i => i.type === 'cluster')
    const clusterName = clusterItem?.name || 'cluster'
    // Get current host's hostname
    const hostRes = await api.proxmox.getHost(hostId.value)
    const masterHostname = hostRes.data?.hostname || 'proxmox-master'
    // Build the join command
    joinCommand.value = `pvecm add ${masterHostname} --password '${joinPassword.value}' --force`
    joinStep.value = 2
  } catch (err) {
    toast.error('Failed to get cluster info: ' + (err?.response?.data?.detail || err?.message))
  }
}

function startJoinVerification() {
  joinVerifying.value = true
  joinVerified.value = false
  joinVerifyFail.value = false
  let attempts = 0
  const MAX_ATTEMPTS = 20

  joinPollTimer = setInterval(async () => {
    attempts++
    try {
      const res = await api.pveNode.clusterStatus(hostId.value)
      const items = res.data || []
      const nodes = items.filter(i => i.type === 'node')
      const found = nodes.some(n =>
        n.name?.includes(joinNodeIp.value) || n.ip === joinNodeIp.value
      )
      if (found) {
        joinVerified.value = true
        joinVerifying.value = false
        clearInterval(joinPollTimer)
        joinPollTimer = null
        toast.success('New node joined the cluster successfully!')
        await fetchClusterStatus()
      } else if (attempts >= MAX_ATTEMPTS) {
        joinVerifyFail.value = true
        joinVerifying.value = false
        clearInterval(joinPollTimer)
        joinPollTimer = null
      }
    } catch { /* ignore */ }
  }, 5000)
}

function resetJoinWizard() {
  joinStep.value = 1
  joinNodeIp.value = ''
  joinPassword.value = ''
  joinCommand.value = ''
  joinVerifying.value = false
  joinVerified.value = false
  joinVerifyFail.value = false
  if (joinPollTimer) { clearInterval(joinPollTimer); joinPollTimer = null }
}

// ── Data fetch ────────────────────────────────────────────────────────────────

async function fetchClusterStatus() {
  loadingStatus.value = true
  try {
    const res = await api.pveNode.clusterStatus(hostId.value)
    const items = res.data || []
    clusterNodes.value = items.filter(i => i.type === 'node')
  } catch (err) {
    console.error('Failed to load cluster status:', err)
    toast.error('Failed to load cluster status')
  } finally {
    loadingStatus.value = false
  }
}

async function fetchResources() {
  loadingResources.value = true
  try {
    const res = await api.pveNode.clusterResources(hostId.value)
    const resources = res.data || []
    allResources.value = resources

    let vmsTotal = 0, vmsRunning = 0, ctsTotal = 0, ctsRunning = 0
    let cpuUsed = 0, cpuTotal = 0, memUsed = 0, memTotal = 0

    for (const r of resources) {
      if (r.type === 'qemu') {
        vmsTotal++
        if (r.status === 'running') {
          vmsRunning++
          cpuUsed += (r.cpu || 0) * (r.maxcpu || 1)
        }
        cpuTotal += r.maxcpu || 0
        memUsed += r.mem || 0
        memTotal += r.maxmem || 0
      } else if (r.type === 'lxc') {
        ctsTotal++
        if (r.status === 'running') {
          ctsRunning++
          cpuUsed += (r.cpu || 0) * (r.maxcpu || 1)
        }
        cpuTotal += r.maxcpu || 0
        memUsed += r.mem || 0
        memTotal += r.maxmem || 0
      }
    }

    summary.value = { vmsTotal, vmsRunning, ctsTotal, ctsRunning, cpuUsed, cpuTotal, memUsed, memTotal }
  } catch (err) {
    console.error('Failed to load cluster resources:', err)
    toast.error('Failed to load cluster resources')
  } finally {
    loadingResources.value = false
  }
}

async function fetchFirewallRules() {
  loadingFirewall.value = true
  try {
    const res = await api.pveNode.getClusterFirewallRules(hostId.value)
    firewallRules.value = res.data || []
  } catch (err) {
    console.error('Failed to load firewall rules:', err)
  } finally {
    loadingFirewall.value = false
  }
}

async function refresh() {
  await Promise.all([fetchClusterStatus(), fetchResources(), fetchFirewallRules()])
}

function startAutoRefresh() {
  refreshCountdown.value = REFRESH_INTERVAL
  countdownTimer = setInterval(() => {
    refreshCountdown.value--
    if (refreshCountdown.value <= 0) refreshCountdown.value = REFRESH_INTERVAL
  }, 1000)
  refreshTimer = setInterval(() => { refresh() }, REFRESH_INTERVAL * 1000)
}

function stopAutoRefresh() {
  if (countdownTimer) clearInterval(countdownTimer)
  if (refreshTimer) clearInterval(refreshTimer)
}

async function manualRefresh() {
  stopAutoRefresh()
  await refresh()
  startAutoRefresh()
}

onMounted(async () => {
  await refresh()
  await fetchMigrationTasks()
  startAutoRefresh()
  startMigrationPoll()
})

onUnmounted(() => {
  stopAutoRefresh()
  stopMigrationPoll()
  if (joinPollTimer) clearInterval(joinPollTimer)
})
</script>

<style scoped>
.cluster-overview-page {
  padding: 0;
}

.page-header {
  margin-bottom: 1.5rem;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.header-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.5rem;
}

.refresh-control {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.countdown-badge {
  font-size: 0.75rem;
  color: var(--text-muted, #888);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.25rem;
  padding: 0.2rem 0.5rem;
  font-variant-numeric: tabular-nums;
  transition: color 0.3s, border-color 0.3s;
}

.countdown-urgent {
  color: #b45309;
  border-color: #f59e0b;
}

.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  align-items: start;
}

.card-body {
  padding: 1.25rem 1.5rem;
}

.node-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.node-card {
  padding: 0.625rem 0.875rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background: var(--bg-secondary);
}

.node-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.25rem;
}

.node-card-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.node-name {
  font-weight: 600;
  color: var(--text-primary);
}

.node-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.node-resource-bars {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.node-bar-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.node-bar-label {
  min-width: 30px;
  color: var(--text-muted, #888);
  font-weight: 500;
}

.node-bar-pct {
  min-width: 34px;
  text-align: right;
}

.mini-bar-wrap--sm {
  height: 6px;
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.stat-item {
  text-align: center;
  padding: 0.75rem;
  background: var(--bg-secondary);
  border-radius: 0.375rem;
  border: 1px solid var(--border-color);
}

.stat-item--green .stat-value {
  color: #10b981;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-muted, #888);
}

.resource-bars {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.resource-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.resource-label {
  min-width: 180px;
  color: var(--text-primary);
}

.mini-bar-wrap {
  flex: 1;
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.mini-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.fill--ok { background: #10b981; }
.fill--warning { background: #f59e0b; }
.fill--danger { background: #ef4444; }

/* Balance chart */
.balance-chart {
  display: flex;
  gap: 1.5rem;
  align-items: flex-end;
  padding: 1rem 0;
  overflow-x: auto;
}

.balance-node-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  min-width: 80px;
}

.balance-bars {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
  height: 120px;
}

.balance-bar-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  width: 28px;
}

.balance-bar-label {
  font-weight: 500;
}

.balance-bar-track {
  width: 28px;
  height: 80px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  align-items: flex-end;
}

.balance-bar-fill {
  width: 100%;
  border-radius: 4px;
  min-height: 2px;
  transition: height 0.3s;
}

.balance-bar-pct {
  color: var(--text-muted, #888);
}

.balance-node-name {
  font-weight: 600;
  text-align: center;
  color: var(--text-primary);
}

/* Rebalance panel */
.rebalance-panel {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.875rem;
  background: var(--bg-secondary);
}

.rebalance-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.rebalance-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--border-color);
}

.rebalance-item:last-child {
  border-bottom: none;
}

.rebalance-arrow {
  flex: 1;
  color: var(--text-primary);
}

/* Live migration items */
.migration-running-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background: var(--bg-secondary);
  margin-bottom: 0.5rem;
}

.migration-info {
  min-width: 180px;
}

.migration-progress-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.migration-progress-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.migration-progress-fill {
  height: 100%;
  border-radius: 4px;
  background: #3b82f6;
}

@keyframes pulse-bar {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.anim-pulse {
  animation: pulse-bar 1.5s ease-in-out infinite;
}

/* Migration panel */
.migration-form {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 200px;
}

.form-group--inline {
  justify-content: flex-end;
  min-width: unset;
}

.form-label {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-primary);
}

.form-check {
  margin-right: 0.4rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.migrate-error { color: #ef4444; }
.migrate-success { color: #10b981; }

/* Evacuation result */
.evacuation-result {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.75rem;
  background: var(--bg-secondary);
  margin-top: 0.75rem;
}

/* Join wizard */
.join-command {
  background: #0f1419;
  color: #9ca3af;
  padding: 0.875rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  white-space: pre-wrap;
  word-break: break-all;
  border: 1px solid var(--border-color);
}

.toggle-icon {
  font-size: 0.75rem;
  color: var(--text-muted, #888);
}

.search-input {
  max-width: 260px;
  padding: 0.3rem 0.6rem;
  font-size: 0.875rem;
}

.resource-row-link {
  cursor: pointer;
  transition: background 0.1s;
}

.resource-row-link:hover {
  background: var(--bg-secondary);
}

.loading-spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border-color);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Buttons */
.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.btn-xs {
  padding: 0.15rem 0.4rem;
  font-size: 0.75rem;
}

.btn-warning {
  background: #f59e0b;
  color: #1a1a1a;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  font-weight: 500;
}

.btn-warning:hover { background: #d97706; }

.btn-danger {
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  font-weight: 500;
}

.btn-danger:hover { background: #dc2626; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-success {
  background: #10b981;
  color: white;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  font-weight: 500;
}

.btn-success:hover { background: #059669; }

.font-semibold { font-weight: 600; }
.text-danger { color: #ef4444; }
.text-success { color: #10b981; }

.mb-2 { margin-bottom: 1rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.75rem; }
.ml-1 { margin-left: 0.5rem; }
.p-3 { padding: 1.5rem; }
.text-xs { font-size: 0.75rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-muted, #888); }
.text-center { text-align: center; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.align-center { align-items: center; }
.table-container { overflow-x: auto; }

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .summary-stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-right {
    align-items: flex-start;
  }
}

@media (max-width: 500px) {
  .summary-stats {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
