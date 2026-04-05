<template>
  <div class="federation-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header-row">
        <div>
          <h2>Federation View</h2>
          <p class="text-muted">Unified cross-cluster overview across all registered Proxmox hosts</p>
        </div>
        <div class="header-actions">
          <span v-if="fetchedAt" class="text-muted text-sm">
            Updated {{ formatRelativeTime(fetchedAt) }}
          </span>
          <button @click="refresh" class="btn btn-outline" :disabled="loading">
            <span v-if="!loading">Refresh</span>
            <span v-else>Loading...</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading && !summary" class="loading-spinner"></div>

    <!-- No hosts state -->
    <div v-else-if="!loading && summary && summary.hosts.length === 0" class="empty-state card">
      <p class="text-muted">No Proxmox hosts registered yet.</p>
      <router-link to="/proxmox" class="btn btn-primary mt-1">Add Proxmox Host</router-link>
    </div>

    <template v-else-if="summary">
      <!-- ── Federation Health Score ── -->
      <div class="fed-health-row mb-2">
        <div class="health-gauge-card">
          <div class="hg-label">Federation Health</div>
          <div class="hg-gauge-wrap">
            <svg class="hg-gauge-svg" viewBox="0 0 120 70" width="120" height="70">
              <!-- Background arc -->
              <path
                d="M10 65 A55 55 0 0 1 110 65"
                fill="none"
                stroke="var(--border-color)"
                stroke-width="10"
                stroke-linecap="round"
              />
              <!-- Foreground arc -->
              <path
                d="M10 65 A55 55 0 0 1 110 65"
                fill="none"
                :stroke="healthGaugeColor"
                stroke-width="10"
                stroke-linecap="round"
                stroke-dasharray="172.8"
                :stroke-dashoffset="gaugeOffset"
                style="transition: stroke-dashoffset 0.6s ease, stroke 0.4s ease;"
              />
            </svg>
            <div class="hg-score">{{ federationHealthScore }}%</div>
          </div>
          <div class="hg-sublabel" :class="healthScoreLabelClass">{{ healthScoreLabel }}</div>
        </div>

        <div class="health-breakdown">
          <div class="hb-row" v-for="host in summary.hosts" :key="host.host_id">
            <span :class="['hb-dot', host.status === 'online' ? 'dot-online' : 'dot-offline']"></span>
            <span class="hb-name">{{ host.host_name }}</span>
            <div class="hb-bar-wrap">
              <div class="hb-bar">
                <div
                  class="hb-bar-fill"
                  :class="barClass(hostHealthPct(host))"
                  :style="{ width: hostHealthPct(host) + '%' }"
                ></div>
              </div>
            </div>
            <span class="hb-pct">{{ hostHealthPct(host) }}%</span>
            <span :class="['badge', 'badge-sm', statusBadgeClass(host.status)]">{{ host.status }}</span>
          </div>
        </div>
      </div>

      <!-- Global Stats Bar -->
      <div class="global-stats-grid mb-2">
        <div class="stat-card">
          <div class="stat-value">{{ summary.total_vms }}</div>
          <div class="stat-label">Total VMs</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary.total_lxc }}</div>
          <div class="stat-label">Total LXC</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary.total_nodes }}</div>
          <div class="stat-label">Total Nodes</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary.online_hosts }} / {{ summary.hosts.length }}</div>
          <div class="stat-label">Hosts Online</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary.total_storage_used_gb }} GB</div>
          <div class="stat-label">Storage Used</div>
          <div class="stat-sub">of {{ summary.total_storage_total_gb }} GB</div>
        </div>
      </div>

      <!-- ── World Map / Datacenter Locations ── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Datacenter Locations</h3>
          <span class="card-header-sub">Geographic overview of your infrastructure</span>
        </div>
        <div class="world-map-container">
          <!-- Simplified SVG world map outline (Mercator projection placeholder) -->
          <svg
            class="world-map-svg"
            viewBox="0 0 900 450"
            xmlns="http://www.w3.org/2000/svg"
            preserveAspectRatio="xMidYMid meet"
          >
            <!-- Background ocean -->
            <rect width="900" height="450" fill="var(--map-ocean, rgba(59,130,246,0.05))" rx="8"/>

            <!-- Simplified continent outlines (decorative, not to-scale) -->
            <!-- North America -->
            <path d="M 60 80 L 120 70 L 170 90 L 200 120 L 210 170 L 180 210 L 150 230 L 130 260 L 100 270 L 80 250 L 60 200 L 50 150 Z"
              fill="var(--map-land, rgba(100,160,100,0.18))" stroke="var(--border-color)" stroke-width="0.8"/>
            <!-- South America -->
            <path d="M 140 280 L 180 270 L 210 290 L 220 330 L 210 380 L 190 400 L 160 410 L 140 390 L 130 350 L 125 310 Z"
              fill="var(--map-land, rgba(100,160,100,0.18))" stroke="var(--border-color)" stroke-width="0.8"/>
            <!-- Europe -->
            <path d="M 390 60 L 440 55 L 460 75 L 450 100 L 430 110 L 400 105 L 380 90 Z"
              fill="var(--map-land, rgba(100,160,100,0.18))" stroke="var(--border-color)" stroke-width="0.8"/>
            <!-- Africa -->
            <path d="M 390 130 L 450 120 L 480 150 L 490 210 L 470 280 L 440 320 L 410 330 L 380 310 L 360 260 L 360 200 L 370 160 Z"
              fill="var(--map-land, rgba(100,160,100,0.18))" stroke="var(--border-color)" stroke-width="0.8"/>
            <!-- Asia -->
            <path d="M 470 50 L 620 40 L 700 60 L 740 90 L 750 130 L 720 160 L 670 170 L 620 160 L 570 150 L 520 140 L 490 120 L 465 95 Z"
              fill="var(--map-land, rgba(100,160,100,0.18))" stroke="var(--border-color)" stroke-width="0.8"/>
            <!-- Australia -->
            <path d="M 680 280 L 760 270 L 800 300 L 810 340 L 790 370 L 750 380 L 710 370 L 680 340 L 670 310 Z"
              fill="var(--map-land, rgba(100,160,100,0.18))" stroke="var(--border-color)" stroke-width="0.8"/>

            <!-- Grid lines (longitude/latitude feel) -->
            <line v-for="x in [180, 270, 360, 450, 540, 630, 720]" :key="'v'+x"
              :x1="x" y1="0" :x2="x" y2="450"
              stroke="var(--border-color)" stroke-width="0.4" opacity="0.4"/>
            <line v-for="y in [90, 180, 270, 360]" :key="'h'+y"
              x1="0" :y1="y" x2="900" :y2="y"
              stroke="var(--border-color)" stroke-width="0.4" opacity="0.4"/>

            <!-- Host datacenter pins -->
            <g v-for="(host, idx) in summary.hosts" :key="'pin-'+host.host_id">
              <!-- Pin position cycles through preset locations if no lat/lon -->
              <circle
                :cx="hostMapX(host, idx)"
                :cy="hostMapY(host, idx)"
                r="10"
                :fill="host.status === 'online' ? 'rgba(59,130,246,0.2)' : 'rgba(239,68,68,0.15)'"
                stroke="none"
                class="host-pin-pulse"
              />
              <circle
                :cx="hostMapX(host, idx)"
                :cy="hostMapY(host, idx)"
                r="5"
                :fill="host.status === 'online' ? '#3b82f6' : '#ef4444'"
                stroke="white"
                stroke-width="1.5"
                class="host-pin-dot"
              />
              <!-- Label -->
              <text
                :x="hostMapX(host, idx) + 8"
                :y="hostMapY(host, idx) - 8"
                font-size="9"
                fill="var(--text-primary)"
                class="host-pin-label"
              >{{ host.host_name }}</text>
            </g>

            <!-- Connection lines between online hosts -->
            <g v-if="summary.hosts.filter(h => h.status === 'online').length > 1">
              <line
                v-for="pair in hostConnectionPairs"
                :key="pair.key"
                :x1="pair.x1" :y1="pair.y1"
                :x2="pair.x2" :y2="pair.y2"
                stroke="rgba(59,130,246,0.25)"
                stroke-width="1"
                stroke-dasharray="4 3"
              />
            </g>
          </svg>

          <!-- Host legend below map -->
          <div class="map-legend">
            <div v-for="host in summary.hosts" :key="'leg-'+host.host_id" class="map-legend-item">
              <span :class="['legend-dot', host.status === 'online' ? 'dot-online' : 'dot-offline']"></span>
              <span class="legend-name">{{ host.host_name }}</span>
              <span class="text-muted text-sm">{{ host.api_url }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Cross-Host VM Migration Recommendations ── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Migration Opportunities</h3>
          <span class="card-header-sub">VMs that may benefit from cross-host migration</span>
        </div>

        <div v-if="migrationLoading" class="loading-spinner"></div>

        <div v-else-if="migrationCandidates.length === 0" class="migration-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="migration-empty-icon">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
          <p>No migration recommendations at this time.</p>
          <span class="text-muted text-sm">Resources appear balanced across your hosts.</span>
        </div>

        <div v-else class="migration-table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>VM</th>
                <th>Source Host</th>
                <th>Source Load</th>
                <th>Target Host</th>
                <th>Target Load</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="cand in migrationCandidates" :key="cand.vm_name + cand.source_host">
                <td>
                  <span class="vm-name-cell">{{ cand.vm_name }}</span>
                  <span class="text-muted text-sm">ID {{ cand.vmid }}</span>
                </td>
                <td class="text-sm">{{ cand.source_host }}</td>
                <td>
                  <div class="mini-bar-wrap">
                    <div class="mini-bar">
                      <div class="mini-bar-fill" :class="barClass(cand.source_cpu_pct)" :style="{ width: cand.source_cpu_pct + '%' }"></div>
                    </div>
                    <span class="text-sm">{{ cand.source_cpu_pct }}% CPU</span>
                  </div>
                </td>
                <td class="text-sm">{{ cand.target_host }}</td>
                <td>
                  <div class="mini-bar-wrap">
                    <div class="mini-bar">
                      <div class="mini-bar-fill" :class="barClass(cand.target_cpu_pct)" :style="{ width: cand.target_cpu_pct + '%' }"></div>
                    </div>
                    <span class="text-sm">{{ cand.target_cpu_pct }}% CPU</span>
                  </div>
                </td>
                <td>
                  <span class="badge badge-warning text-sm">{{ cand.reason }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── Bandwidth / SDN Placeholder ── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Inter-Host Bandwidth</h3>
          <span class="card-header-sub text-muted">SDN tunnel statistics — coming soon</span>
        </div>
        <div class="bandwidth-placeholder">
          <div class="bw-host-row" v-for="pair in hostPairs" :key="pair.key">
            <div class="bw-host bw-host-a">
              <span :class="['bw-status', pair.aOnline ? 'dot-online' : 'dot-offline']"></span>
              {{ pair.a }}
            </div>
            <div class="bw-line">
              <div class="bw-arrow-wrap">
                <svg width="100%" height="24" viewBox="0 0 200 24">
                  <line x1="10" y1="12" x2="190" y2="12" stroke="var(--border-color)" stroke-width="2" stroke-dasharray="6 3"/>
                  <polygon points="185,8 195,12 185,16" fill="var(--border-color)"/>
                </svg>
              </div>
              <div class="bw-label">N/A</div>
            </div>
            <div class="bw-host bw-host-b">
              <span :class="['bw-status', pair.bOnline ? 'dot-online' : 'dot-offline']"></span>
              {{ pair.b }}
            </div>
          </div>
          <p class="bw-note text-muted text-sm">
            Real-time bandwidth metrics will be available once SDN tunnel integration is configured.
          </p>
        </div>
      </div>

      <!-- Per-Host Cards Grid -->
      <div class="section-title">Proxmox Clusters</div>
      <div class="hosts-grid mb-2">
        <div
          v-for="host in summary.hosts"
          :key="host.host_id"
          class="host-card"
          :class="{ 'host-card--offline': host.status === 'offline' }"
        >
          <!-- Card Header -->
          <div class="host-card-header">
            <div class="host-title-row">
              <h3 class="host-name">{{ host.host_name }}</h3>
              <span :class="['badge', statusBadgeClass(host.status)]">
                {{ host.status }}
              </span>
            </div>
            <div class="host-meta">
              <span class="text-muted text-sm">{{ host.api_url }}</span>
              <span v-if="host.cluster_name" class="cluster-name text-sm">
                Cluster: <strong>{{ host.cluster_name }}</strong>
              </span>
            </div>
          </div>

          <!-- Counts row -->
          <div class="host-counts">
            <div class="count-item">
              <span class="count-val">{{ host.node_count }}</span>
              <span class="count-lbl">Nodes</span>
            </div>
            <div class="count-item">
              <span class="count-val">{{ host.vm_count }}</span>
              <span class="count-lbl">VMs</span>
            </div>
            <div class="count-item">
              <span class="count-val">{{ host.lxc_count }}</span>
              <span class="count-lbl">LXC</span>
            </div>
            <div class="count-item">
              <span v-if="host.latency_ms != null" :class="['badge', 'badge-sm', latencyBadgeClass(host.latency_ms)]">
                {{ host.latency_ms }}ms
              </span>
              <span v-else class="count-lbl">—</span>
              <span class="count-lbl">Latency</span>
            </div>
          </div>

          <!-- Usage bars (only when online) -->
          <div v-if="host.status === 'online'" class="host-usage">
            <!-- CPU -->
            <div class="usage-row">
              <span class="usage-label">CPU</span>
              <div class="usage-bar-wrap">
                <div class="usage-bar">
                  <div
                    class="usage-bar-fill"
                    :class="barClass(host.cpu_usage_pct)"
                    :style="{ width: host.cpu_usage_pct + '%' }"
                  ></div>
                </div>
                <span class="usage-pct">{{ host.cpu_usage_pct }}%</span>
              </div>
            </div>
            <!-- Memory -->
            <div class="usage-row">
              <span class="usage-label">Memory</span>
              <div class="usage-bar-wrap">
                <div class="usage-bar">
                  <div
                    class="usage-bar-fill"
                    :class="barClass(host.memory_usage_pct)"
                    :style="{ width: host.memory_usage_pct + '%' }"
                  ></div>
                </div>
                <span class="usage-pct">
                  {{ host.memory_usage_pct }}%
                  ({{ formatGB(host.memory_used_bytes) }} / {{ formatGB(host.memory_total_bytes) }} GB)
                </span>
              </div>
            </div>
            <!-- Storage -->
            <div class="usage-row">
              <span class="usage-label">Storage</span>
              <div class="usage-bar-wrap">
                <div class="usage-bar">
                  <div
                    class="usage-bar-fill"
                    :class="barClass(storageUsedPct(host))"
                    :style="{ width: storageUsedPct(host) + '%' }"
                  ></div>
                </div>
                <span class="usage-pct">
                  {{ host.storage_used_gb }} / {{ host.storage_total_gb }} GB
                </span>
              </div>
            </div>
          </div>

          <!-- Cluster health badge -->
          <div class="host-card-footer">
            <span :class="['badge', healthBadgeClass(host.cluster_health)]">
              {{ (host.cluster_health || 'unknown').toUpperCase() }}
            </span>
            <div class="quick-links">
              <router-link :to="`/proxmox/${host.host_id}/cluster`" class="link-btn">Cluster</router-link>
              <router-link :to="`/vms?host=${host.host_id}`" class="link-btn">VMs</router-link>
              <router-link :to="`/proxmox`" class="link-btn">Nodes</router-link>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Global Search (searches across all hosts simultaneously) ── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Global Search</h3>
          <span class="card-header-sub">Search VMs and nodes across all hosts simultaneously</span>
        </div>
        <div class="search-bar">
          <div class="global-search-row">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="gs-icon">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              v-model="vmSearchQuery"
              @input="onVmSearchInput"
              class="form-control global-search-input"
              placeholder="Search VMs across all hosts by name or ID..."
            />
            <span v-if="vmSearchLoading" class="gs-spinner"></span>
          </div>
        </div>

        <div v-if="vmSearchLoading" class="loading-spinner"></div>

        <div v-else-if="vmSearchQuery.length >= 2 && vmSearchResults.length === 0" class="text-center text-muted p-2">
          No VMs found matching "{{ vmSearchQuery }}"
        </div>

        <div v-else-if="vmSearchResults.length > 0" class="search-results">
          <div v-for="group in vmSearchResults" :key="group.host_id" class="search-group">
            <div class="search-group-header">{{ group.host_name }}</div>
            <div class="search-group-items">
              <div
                v-for="vm in group.vms"
                :key="`${group.host_id}-${vm.vmid}`"
                class="search-result-item"
                @click="navigateToVm(group.host_id, vm)"
              >
                <span class="vm-name">{{ vm.name || '(no name)' }}</span>
                <span class="vm-meta text-sm text-muted">
                  ID: {{ vm.vmid }} &bull; {{ vm.node }} &bull;
                  <span :class="['badge', 'badge-sm', vm.status === 'running' ? 'badge-success' : 'badge-secondary']">
                    {{ vm.status }}
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Cross-Host Recent Tasks -->
      <div class="card">
        <div class="card-header">
          <h3>Recent Tasks (All Hosts)</h3>
          <button @click="fetchRecentTasks" class="btn btn-outline btn-sm" :disabled="tasksLoading">
            {{ tasksLoading ? 'Loading...' : 'Refresh' }}
          </button>
        </div>

        <div v-if="tasksLoading" class="loading-spinner"></div>

        <div v-else-if="recentTasks.length === 0" class="text-center text-muted p-2">
          No recent tasks found.
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Host</th>
                <th>Task</th>
                <th>Node</th>
                <th>Status</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in recentTasks" :key="`${task.host_id}-${task.upid}`">
                <td class="text-sm">{{ task.host_name }}</td>
                <td class="text-sm">{{ task.type || task.upid }}</td>
                <td class="text-sm">{{ task.node }}</td>
                <td>
                  <span :class="['badge', taskStatusClass(task.status)]">
                    {{ task.status || 'running' }}
                  </span>
                </td>
                <td class="text-sm">{{ formatDate(task.starttime) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

// Preset map coordinates (x, y in 900x450 viewBox) for hosts without lat/lon
const MAP_PRESETS = [
  { x: 160, y: 140 },  // North America East
  { x: 100, y: 130 },  // North America West
  { x: 420, y: 80  },  // Western Europe
  { x: 500, y: 100 },  // Eastern Europe / Middle East
  { x: 620, y: 110 },  // East Asia
  { x: 720, y: 310 },  // Australia
  { x: 160, y: 310 },  // South America
  { x: 420, y: 200 },  // Africa
]

export default {
  name: 'FederatedDashboard',
  setup() {
    const router = useRouter()

    const loading = ref(false)
    const summary = ref(null)
    const fetchedAt = ref(null)

    // VM Search
    const vmSearchQuery = ref('')
    const vmSearchResults = ref([])
    const vmSearchLoading = ref(false)
    let vmSearchTimer = null

    // Tasks
    const recentTasks = ref([])
    const tasksLoading = ref(false)

    // Migration
    const migrationCandidates = ref([])
    const migrationLoading = ref(false)

    const fetchSummary = async () => {
      loading.value = true
      try {
        const response = await api.proxmox.getFederationSummary()
        summary.value = response.data
        fetchedAt.value = response.data.fetched_at
      } catch (error) {
        console.error('Failed to fetch federation summary:', error)
      } finally {
        loading.value = false
      }
    }

    const refresh = () => {
      fetchSummary().then(() => {
        computeMigrationCandidates()
      })
      if (recentTasks.value.length > 0 || tasksLoading.value) {
        fetchRecentTasks()
      }
    }

    // ── Federation Health Score ─────────────────────────────────────────────
    // Composite score: penalise offline hosts, high resource usage, degraded health
    const federationHealthScore = computed(() => {
      if (!summary.value || summary.value.hosts.length === 0) return 0
      const hosts = summary.value.hosts
      let total = 0
      for (const host of hosts) {
        total += hostHealthPct(host)
      }
      return Math.round(total / hosts.length)
    })

    const hostHealthPct = (host) => {
      if (host.status === 'offline') return 0
      let score = 100
      // Penalise high CPU
      if (host.cpu_usage_pct > 90) score -= 30
      else if (host.cpu_usage_pct > 75) score -= 15
      else if (host.cpu_usage_pct > 60) score -= 5
      // Penalise high memory
      if (host.memory_usage_pct > 90) score -= 30
      else if (host.memory_usage_pct > 75) score -= 15
      else if (host.memory_usage_pct > 60) score -= 5
      // Penalise degraded health
      if (host.cluster_health === 'degraded') score -= 20
      else if (!host.cluster_health || host.cluster_health === 'unknown') score -= 5
      return Math.max(0, score)
    }

    const gaugeOffset = computed(() => {
      // Arc total length is 172.8 (semicircle, r=55, half circumference)
      const score = federationHealthScore.value
      return 172.8 - (172.8 * score) / 100
    })

    const healthGaugeColor = computed(() => {
      const s = federationHealthScore.value
      if (s >= 80) return '#22c55e'
      if (s >= 60) return '#f59e0b'
      return '#ef4444'
    })

    const healthScoreLabel = computed(() => {
      const s = federationHealthScore.value
      if (s >= 80) return 'Healthy'
      if (s >= 60) return 'Degraded'
      return 'Critical'
    })

    const healthScoreLabelClass = computed(() => {
      const s = federationHealthScore.value
      if (s >= 80) return 'health-good'
      if (s >= 60) return 'health-warn'
      return 'health-bad'
    })

    // ── Map helpers ─────────────────────────────────────────────────────────
    const hostMapX = (host, idx) => {
      if (host.longitude != null) {
        return Math.round(((host.longitude + 180) / 360) * 900)
      }
      return MAP_PRESETS[idx % MAP_PRESETS.length].x
    }

    const hostMapY = (host, idx) => {
      if (host.latitude != null) {
        return Math.round(((90 - host.latitude) / 180) * 450)
      }
      return MAP_PRESETS[idx % MAP_PRESETS.length].y
    }

    const hostConnectionPairs = computed(() => {
      if (!summary.value) return []
      const online = summary.value.hosts.filter(h => h.status === 'online')
      const pairs = []
      for (let i = 0; i < online.length; i++) {
        for (let j = i + 1; j < online.length; j++) {
          const a = online[i]
          const b = online[j]
          const aIdx = summary.value.hosts.indexOf(a)
          const bIdx = summary.value.hosts.indexOf(b)
          pairs.push({
            key: `${a.host_id}-${b.host_id}`,
            x1: hostMapX(a, aIdx),
            y1: hostMapY(a, aIdx),
            x2: hostMapX(b, bIdx),
            y2: hostMapY(b, bIdx),
          })
        }
      }
      return pairs
    })

    // ── Host pairs for bandwidth display ────────────────────────────────────
    const hostPairs = computed(() => {
      if (!summary.value) return []
      const hosts = summary.value.hosts
      const pairs = []
      for (let i = 0; i < hosts.length; i++) {
        for (let j = i + 1; j < hosts.length; j++) {
          pairs.push({
            key: `${hosts[i].host_id}-${hosts[j].host_id}`,
            a: hosts[i].host_name,
            b: hosts[j].host_name,
            aOnline: hosts[i].status === 'online',
            bOnline: hosts[j].status === 'online',
          })
        }
      }
      return pairs.slice(0, 6)  // cap at 6 pairs
    })

    // ── Migration Candidates ─────────────────────────────────────────────────
    // Find hosts with high CPU (>70%) paired with hosts with low CPU (<40%)
    // and suggest moving VMs
    const computeMigrationCandidates = async () => {
      if (!summary.value || summary.value.hosts.length < 2) {
        migrationCandidates.value = []
        return
      }
      migrationLoading.value = true
      const candidates = []

      const onlineHosts = summary.value.hosts.filter(h => h.status === 'online')
      const highCpu = onlineHosts.filter(h => (h.cpu_usage_pct || 0) > 70)
      const lowCpu  = onlineHosts.filter(h => (h.cpu_usage_pct || 0) < 40)

      if (highCpu.length > 0 && lowCpu.length > 0) {
        for (const srcHost of highCpu) {
          const tgtHost = lowCpu[0]
          // Try to fetch top VMs from the overloaded host
          try {
            const nodesRes = await api.proxmox.listNodes(srcHost.host_id)
            const nodes = Array.isArray(nodesRes.data) ? nodesRes.data.slice(0, 2) : []
            for (const node of nodes) {
              try {
                const vmsRes = await api.pveNode.nodeVms(srcHost.host_id, node.node_name)
                const vms = (Array.isArray(vmsRes.data) ? vmsRes.data : [])
                  .filter(v => v.status === 'running')
                  .slice(0, 2)

                for (const vm of vms) {
                  candidates.push({
                    vm_name: vm.name || `VM ${vm.vmid}`,
                    vmid: vm.vmid,
                    source_host: srcHost.host_name,
                    source_cpu_pct: srcHost.cpu_usage_pct || 0,
                    target_host: tgtHost.host_name,
                    target_cpu_pct: tgtHost.cpu_usage_pct || 0,
                    reason: 'High CPU imbalance',
                  })
                  if (candidates.length >= 5) break
                }
              } catch (e) { /* skip node */ }
              if (candidates.length >= 5) break
            }
          } catch (e) { /* skip host */ }
          if (candidates.length >= 5) break
        }
      }

      // Also check high memory
      const highMem = onlineHosts.filter(h => (h.memory_usage_pct || 0) > 75)
      const lowMem  = onlineHosts.filter(h => (h.memory_usage_pct || 0) < 40)

      if (highMem.length > 0 && lowMem.length > 0 && candidates.length < 5) {
        for (const srcHost of highMem) {
          const tgtHost = lowMem[0]
          if (srcHost.host_id === tgtHost.host_id) continue
          // Don't duplicate if already added for CPU
          const already = candidates.some(c => c.source_host === srcHost.host_name && c.target_host === tgtHost.host_name)
          if (!already) {
            candidates.push({
              vm_name: '(multiple VMs)',
              vmid: '—',
              source_host: srcHost.host_name,
              source_cpu_pct: srcHost.cpu_usage_pct || 0,
              target_host: tgtHost.host_name,
              target_cpu_pct: tgtHost.cpu_usage_pct || 0,
              reason: 'High memory imbalance',
            })
          }
        }
      }

      migrationCandidates.value = candidates
      migrationLoading.value = false
    }

    // Cross-host VM search
    const onVmSearchInput = () => {
      clearTimeout(vmSearchTimer)
      if (vmSearchQuery.value.length < 2) {
        vmSearchResults.value = []
        return
      }
      vmSearchTimer = setTimeout(() => {
        runVmSearch()
      }, 350)
    }

    const runVmSearch = async () => {
      if (!summary.value || summary.value.hosts.length === 0) return
      vmSearchLoading.value = true
      vmSearchResults.value = []
      const q = vmSearchQuery.value.toLowerCase()

      const onlineHosts = summary.value.hosts.filter(h => h.status === 'online')

      const searchTasks = onlineHosts.map(async (host) => {
        try {
          const res = await api.pveNode.clusterResources(host.host_id, 'qemu')
          const vms = Array.isArray(res.data) ? res.data : []
          const matched = vms.filter(vm => {
            const nameMatch = (vm.name || '').toLowerCase().includes(q)
            const idMatch = String(vm.vmid || '').includes(q)
            return nameMatch || idMatch
          })
          if (matched.length > 0) {
            return { host_id: host.host_id, host_name: host.host_name, vms: matched }
          }
        } catch (e) {
          console.warn(`VM search failed for host ${host.host_name}:`, e)
        }
        return null
      })

      const results = await Promise.allSettled(searchTasks)
      vmSearchResults.value = results
        .filter(r => r.status === 'fulfilled' && r.value !== null)
        .map(r => r.value)
      vmSearchLoading.value = false
    }

    const navigateToVm = (hostId, vm) => {
      router.push(`/proxmox/${hostId}/nodes/${vm.node}/vms/${vm.vmid}`)
    }

    // Cross-host tasks
    const fetchRecentTasks = async () => {
      if (!summary.value) return
      tasksLoading.value = true
      recentTasks.value = []

      const onlineHosts = summary.value.hosts.filter(h => h.status === 'online')

      const taskFetches = onlineHosts.map(async (host) => {
        try {
          const nodesRes = await api.proxmox.listNodes(host.host_id)
          const nodes = Array.isArray(nodesRes.data) ? nodesRes.data : []
          const nodeTasks = await Promise.allSettled(
            nodes.map(node =>
              api.pveNode.listTasks(host.host_id, node.node_name, { limit: 10 })
                .then(r => (Array.isArray(r.data) ? r.data : []).map(t => ({
                  ...t,
                  host_id: host.host_id,
                  host_name: host.host_name,
                  node: node.node_name,
                })))
            )
          )
          return nodeTasks
            .filter(r => r.status === 'fulfilled')
            .flatMap(r => r.value)
        } catch (e) {
          console.warn(`Task fetch failed for host ${host.host_name}:`, e)
          return []
        }
      })

      const all = await Promise.allSettled(taskFetches)
      const merged = all
        .filter(r => r.status === 'fulfilled')
        .flatMap(r => r.value)

      merged.sort((a, b) => (b.starttime || 0) - (a.starttime || 0))
      recentTasks.value = merged.slice(0, 50)
      tasksLoading.value = false
    }

    // Helpers
    const statusBadgeClass = (status) => {
      if (status === 'online') return 'badge-success'
      if (status === 'degraded') return 'badge-warning'
      return 'badge-danger'
    }

    const healthBadgeClass = (health) => {
      if (health === 'healthy') return 'badge-success'
      if (health === 'degraded') return 'badge-danger'
      return 'badge-secondary'
    }

    const latencyBadgeClass = (ms) => {
      if (ms == null) return 'badge-secondary'
      if (ms < 100) return 'badge-success'
      if (ms < 500) return 'badge-warning'
      return 'badge-danger'
    }

    const barClass = (pct) => {
      if (pct >= 80) return 'bar-danger'
      if (pct >= 60) return 'bar-warning'
      return 'bar-success'
    }

    const storageUsedPct = (host) => {
      if (!host.storage_total_gb) return 0
      return Math.round((host.storage_used_gb / host.storage_total_gb) * 100)
    }

    const formatGB = (bytes) => {
      if (!bytes) return '0'
      return (bytes / (1024 ** 3)).toFixed(1)
    }

    const formatDate = (val) => {
      if (!val) return '—'
      const d = typeof val === 'number' ? new Date(val * 1000) : new Date(val)
      return d.toLocaleString()
    }

    const formatRelativeTime = (isoStr) => {
      if (!isoStr) return ''
      const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000)
      if (diff < 10) return 'just now'
      if (diff < 60) return `${diff}s ago`
      return `${Math.floor(diff / 60)}m ago`
    }

    const taskStatusClass = (status) => {
      if (!status || status === 'running') return 'badge-info'
      if (status === 'OK') return 'badge-success'
      if (status.startsWith('WARN')) return 'badge-warning'
      return 'badge-danger'
    }

    onMounted(() => {
      fetchSummary().then(() => {
        fetchRecentTasks()
        computeMigrationCandidates()
      })
    })

    return {
      loading,
      summary,
      fetchedAt,
      vmSearchQuery,
      vmSearchResults,
      vmSearchLoading,
      recentTasks,
      tasksLoading,
      migrationCandidates,
      migrationLoading,
      federationHealthScore,
      gaugeOffset,
      healthGaugeColor,
      healthScoreLabel,
      healthScoreLabelClass,
      hostConnectionPairs,
      hostPairs,
      hostHealthPct,
      hostMapX,
      hostMapY,
      refresh,
      onVmSearchInput,
      navigateToVm,
      fetchRecentTasks,
      statusBadgeClass,
      healthBadgeClass,
      latencyBadgeClass,
      barClass,
      storageUsedPct,
      formatGB,
      formatDate,
      formatRelativeTime,
      taskStatusClass,
    }
  }
}
</script>

<style scoped>
.federation-page {
  padding-bottom: 2rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.page-header .text-muted {
  font-size: 0.95rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}

/* ── Federation Health Score ─────────────────────────────────────────────── */
.fed-health-row {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 1rem;
  align-items: start;
}

.health-gauge-card {
  background: var(--card-background, #fff);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  text-align: center;
  box-shadow: var(--shadow-sm, none);
}

.hg-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
}

.hg-gauge-wrap {
  position: relative;
  width: 120px;
  height: 70px;
}

.hg-gauge-svg {
  display: block;
}

.hg-score {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  font-size: 1.4rem;
  font-weight: 800;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.hg-sublabel {
  font-size: 0.78rem;
  font-weight: 600;
}

.health-good { color: #22c55e; }
.health-warn { color: #f59e0b; }
.health-bad  { color: #ef4444; }

.health-breakdown {
  background: var(--card-background, #fff);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  box-shadow: var(--shadow-sm, none);
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.hb-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.82rem;
}

.hb-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.hb-name {
  width: 140px;
  flex-shrink: 0;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hb-bar-wrap {
  flex: 1;
}

.hb-bar {
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.hb-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.hb-pct {
  width: 36px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
  font-size: 0.75rem;
  flex-shrink: 0;
}

/* ── World Map ───────────────────────────────────────────────────────────── */
.world-map-container {
  padding: 0.5rem 1rem 1rem;
}

.world-map-svg {
  width: 100%;
  border-radius: 0.375rem;
  border: 1px solid var(--border-color);
  overflow: visible;
}

.host-pin-pulse {
  animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;
}

@keyframes ping {
  0%    { transform: scale(1); opacity: 0.8; }
  75%   { transform: scale(2.5); opacity: 0; }
  100%  { transform: scale(2.5); opacity: 0; }
}

.host-pin-dot {
  filter: drop-shadow(0 1px 3px rgba(0,0,0,0.3));
}

.host-pin-label {
  font-family: var(--font-sans, sans-serif);
  font-weight: 600;
  pointer-events: none;
  fill: var(--text-primary);
  font-size: 9px;
}

.map-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.5rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-color);
}

.map-legend-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-name {
  font-weight: 500;
  color: var(--text-primary);
}

.dot-online  { background: #22c55e; }
.dot-offline { background: #ef4444; }

/* ── Migration Card ──────────────────────────────────────────────────────── */
.migration-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 2rem 1rem;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.migration-empty-icon {
  color: var(--text-secondary);
  opacity: 0.5;
}

.migration-table-wrap {
  overflow-x: auto;
}

.vm-name-cell {
  display: block;
  font-weight: 500;
  color: var(--text-primary);
}

.mini-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.mini-bar {
  width: 60px;
  height: 5px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
  flex-shrink: 0;
}

.mini-bar-fill {
  height: 100%;
  border-radius: 3px;
}

/* ── Bandwidth Placeholder ───────────────────────────────────────────────── */
.bandwidth-placeholder {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.bw-host-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.bw-host {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--text-primary);
  width: 140px;
  flex-shrink: 0;
}

.bw-host-b { justify-content: flex-end; }

.bw-status {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.bw-line {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
}

.bw-arrow-wrap { width: 100%; }

.bw-label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.bw-note {
  margin: 0;
  text-align: center;
  font-style: italic;
}

/* ── Card header sub ─────────────────────────────────────────────────────── */
.card-header-sub {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 400;
}

/* ── Global Search ───────────────────────────────────────────────────────── */
.global-search-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.gs-icon {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.global-search-input {
  flex: 1;
}

.gs-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Global stats bar */
.global-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem;
}

.stat-card {
  background: var(--card-background, #fff);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem 1rem;
  text-align: center;
  box-shadow: var(--shadow-sm, none);
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--primary-color, #3b82f6);
  line-height: 1;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.stat-sub {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.1rem;
}

/* Section title */
.section-title {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

/* Hosts grid */
.hosts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1rem;
}

.host-card {
  background: var(--card-background, #fff);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem;
  box-shadow: var(--shadow-sm, none);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.host-card--offline { opacity: 0.65; }

.host-card-header {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.host-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.host-name {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.host-meta {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.cluster-name { color: var(--text-secondary); }

/* Counts row */
.host-counts {
  display: flex;
  gap: 1.25rem;
  flex-wrap: wrap;
}

.count-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
}

.count-val {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.count-lbl {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.badge-sm {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
}

/* Usage bars */
.host-usage {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.usage-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
}

.usage-label {
  width: 4.5rem;
  flex-shrink: 0;
  color: var(--text-secondary);
  font-weight: 500;
}

.usage-bar-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
}

.usage-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
  min-width: 0;
}

.usage-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.bar-success { background-color: #22c55e; }
.bar-warning { background-color: #f59e0b; }
.bar-danger  { background-color: #ef4444; }

.usage-pct {
  font-size: 0.75rem;
  color: var(--text-primary);
  font-family: monospace;
  white-space: nowrap;
}

/* Card footer */
.host-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-color);
}

.quick-links { display: flex; gap: 0.5rem; }

.link-btn {
  font-size: 0.8rem;
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.25rem;
  color: var(--primary-color, #3b82f6);
  text-decoration: none;
  transition: background 0.15s;
}

.link-btn:hover { background: var(--border-color); }

/* VM Search */
.search-bar {
  padding: 1rem;
  border-bottom: 1px solid var(--border-color);
}

.search-results { padding: 0.5rem 0; }
.search-group   { margin-bottom: 0.5rem; }

.search-group-header {
  padding: 0.5rem 1rem;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
  background: var(--background, #f9fafb);
}

.search-group-items { padding: 0 0.5rem; }

.search-result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 0.75rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background 0.15s;
  gap: 0.5rem;
}

.search-result-item:hover { background: var(--border-color); }

.vm-name {
  font-weight: 500;
  color: var(--text-primary);
}

.vm-meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

/* Spacing helpers */
.mb-2  { margin-bottom: 1.25rem; }
.mt-1  { margin-top: 0.5rem; }
.p-2   { padding: 1.5rem; }

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
}

/* Badge variants */
.badge-info      { background-color: #3b82f6; color: #fff; }
.badge-warning   { background-color: #f59e0b; color: #fff; }
.badge-secondary { background-color: var(--text-secondary, #6b7280); color: #fff; }
.badge-danger    { background-color: #ef4444; color: #fff; }

/* Buttons */
.btn-sm { padding: 0.3rem 0.7rem; font-size: 0.8rem; }

/* Responsive */
@media (max-width: 768px) {
  .fed-health-row {
    grid-template-columns: 1fr;
  }

  .health-gauge-card {
    flex-direction: row;
    gap: 1rem;
    justify-content: flex-start;
    text-align: left;
  }

  .bw-host-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .bw-line { width: 100%; }
}
</style>
