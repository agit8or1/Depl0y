<template>
  <div class="datacenter-page">
    <div class="page-header mb-2">
      <div class="page-header-left">
        <h2>Datacenter</h2>
        <p class="text-muted">Aggregate view across all Proxmox hosts</p>
      </div>
      <button @click="refresh" class="btn btn-outline btn-sm" :disabled="loading">
        <span v-if="loading">Loading...</span>
        <span v-else>Refresh</span>
      </button>
    </div>

    <!-- Global loading indicator -->
    <div v-if="loading && hosts.length === 0" class="loading-spinner"></div>

    <!-- Error state -->
    <div v-else-if="loadError" class="card mb-2">
      <div class="card-body text-center text-muted p-3">
        Failed to load datacenter data. Check your Proxmox host connections.
      </div>
    </div>

    <template v-else>
      <!-- ── Section 1: Cluster Efficiency + Resource Charts ── -->
      <div class="resource-overview-grid mb-2">

        <!-- Efficiency Score Card -->
        <div class="card efficiency-card">
          <div class="card-header">
            <h3>Cluster Efficiency</h3>
          </div>
          <div class="efficiency-body">
            <div class="efficiency-score-ring">
              <svg viewBox="0 0 100 100" class="efficiency-svg">
                <!-- background ring -->
                <circle cx="50" cy="50" r="40" class="ring-bg" />
                <!-- fill ring -->
                <circle
                  cx="50" cy="50" r="40"
                  class="ring-fill"
                  :class="efficiencyRingClass"
                  :style="efficiencyRingStyle"
                  stroke-linecap="round"
                  transform="rotate(-90 50 50)"
                />
                <text x="50" y="46" text-anchor="middle" class="ring-value">{{ clusterEfficiency }}</text>
                <text x="50" y="60" text-anchor="middle" class="ring-label">/ 100</text>
              </svg>
            </div>
            <div class="efficiency-breakdown">
              <div class="eff-row">
                <span class="eff-label">Avg CPU</span>
                <div class="eff-bar-wrap">
                  <div class="eff-bar">
                    <div class="eff-bar-fill" :class="barClass(summary.avgCpuRatio)"
                      :style="{ width: summary.avgCpuPct + '%' }"></div>
                  </div>
                  <span class="eff-pct">{{ summary.avgCpuPct }}%</span>
                </div>
              </div>
              <div class="eff-row">
                <span class="eff-label">Avg RAM</span>
                <div class="eff-bar-wrap">
                  <div class="eff-bar">
                    <div class="eff-bar-fill" :class="barClass(summary.avgMemRatio)"
                      :style="{ width: summary.avgMemPct + '%' }"></div>
                  </div>
                  <span class="eff-pct">{{ summary.avgMemPct }}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Resource Donut Chart -->
        <div class="card donut-card">
          <div class="card-header">
            <h3>Resource Allocation</h3>
          </div>
          <div class="donut-body">
            <div class="donut-chart-wrap">
              <svg viewBox="0 0 120 120" class="donut-svg">
                <!-- CPU donut (outer ring) -->
                <circle cx="60" cy="60" r="50" class="donut-bg" />
                <circle
                  cx="60" cy="60" r="50"
                  class="donut-used"
                  :style="cpuDonutStyle"
                  transform="rotate(-90 60 60)"
                  stroke-linecap="butt"
                />
                <!-- RAM donut (inner ring) -->
                <circle cx="60" cy="60" r="36" class="donut-bg" />
                <circle
                  cx="60" cy="60" r="36"
                  class="donut-used donut-used--mem"
                  :style="memDonutStyle"
                  transform="rotate(-90 60 60)"
                  stroke-linecap="butt"
                />
                <!-- Center text -->
                <text x="60" y="55" text-anchor="middle" class="donut-center-label">CPU/RAM</text>
                <text x="60" y="70" text-anchor="middle" class="donut-center-sub">Usage</text>
              </svg>
            </div>
            <div class="donut-legend">
              <div class="legend-item">
                <span class="legend-dot legend-dot--cpu"></span>
                <span class="legend-text">CPU Used: {{ summary.avgCpuPct }}%</span>
              </div>
              <div class="legend-item">
                <span class="legend-dot legend-dot--mem"></span>
                <span class="legend-text">RAM Used: {{ summary.avgMemPct }}%</span>
              </div>
              <div class="legend-sep"></div>
              <div class="legend-item">
                <span class="legend-text text-muted">Total Cores: {{ summary.totalCpuCores }}</span>
              </div>
              <div class="legend-item">
                <span class="legend-text text-muted">Total RAM: {{ formatBytes(summary.memTotal) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- VM Distribution Mini Pie -->
        <div class="card vm-dist-card">
          <div class="card-header">
            <h3>Guest Distribution</h3>
          </div>
          <div class="vm-dist-body">
            <!-- Mini pie SVG -->
            <svg viewBox="0 0 80 80" class="vm-pie-svg">
              <!-- Running slice (green) -->
              <circle cx="40" cy="40" r="30"
                class="pie-slice pie-slice--running"
                :style="vmRunningSlice"
                transform="rotate(-90 40 40)"
              />
              <!-- Paused slice (amber) -->
              <circle cx="40" cy="40" r="30"
                class="pie-slice pie-slice--paused"
                :style="vmPausedSlice"
                transform="rotate(-90 40 40)"
              />
              <!-- center -->
              <circle cx="40" cy="40" r="18" class="pie-center" />
              <text x="40" y="37" text-anchor="middle" class="pie-center-val">{{ summary.totalGuests }}</text>
              <text x="40" y="49" text-anchor="middle" class="pie-center-sub">Guests</text>
            </svg>
            <div class="vm-dist-legend">
              <div class="vd-item">
                <span class="vd-dot vd-dot--running"></span>
                <span class="vd-label">Running</span>
                <span class="vd-val">{{ summary.vmsRunning + summary.lxcRunning }}</span>
              </div>
              <div class="vd-item">
                <span class="vd-dot vd-dot--stopped"></span>
                <span class="vd-label">Stopped</span>
                <span class="vd-val">{{ summary.totalGuests - summary.vmsRunning - summary.lxcRunning - summary.vmsPaused }}</span>
              </div>
              <div class="vd-item">
                <span class="vd-dot vd-dot--paused"></span>
                <span class="vd-label">Paused</span>
                <span class="vd-val">{{ summary.vmsPaused }}</span>
              </div>
              <div class="vd-sep"></div>
              <div class="vd-item">
                <span class="vd-label text-muted">VMs</span>
                <span class="vd-val">{{ summary.vmsTotal }}</span>
              </div>
              <div class="vd-item">
                <span class="vd-label text-muted">LXC</span>
                <span class="vd-val">{{ summary.lxcTotal }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Quick stat cards -->
        <div class="card stat-summary-card">
          <div class="card-header">
            <h3>Cluster Totals</h3>
          </div>
          <div class="stat-summary-body">
            <div class="ss-row">
              <div class="ss-icon">&#128386;</div>
              <div>
                <div class="ss-value">{{ summary.totalHosts }}</div>
                <div class="ss-label">Hosts</div>
              </div>
            </div>
            <div class="ss-row">
              <div class="ss-icon">&#9881;</div>
              <div>
                <div class="ss-value">{{ summary.totalNodes }}</div>
                <div class="ss-label">Nodes</div>
              </div>
            </div>
            <div class="ss-row">
              <div class="ss-icon">&#128190;</div>
              <div>
                <div class="ss-value">{{ formatBytes(summary.storageTotal) }}</div>
                <div class="ss-label">Storage ({{ storageUsedPct }}% used)</div>
              </div>
            </div>
            <div class="ss-row">
              <div class="ss-icon">&#9654;</div>
              <div>
                <div class="ss-value stat-green">{{ summary.vmsRunning + summary.lxcRunning }}</div>
                <div class="ss-label">Guests Running</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Section 2: VM Distribution Map ── -->
      <div class="section-title mb-1">VM Distribution Map</div>
      <div class="node-distribution-grid mb-2">
        <div
          v-for="nd in nodeDistribution"
          :key="`${nd.hostId}-${nd.node}`"
          class="node-dist-card"
          :class="{ 'node-dist-card--warn': nd.imbalanced }"
          @mouseenter="hoveredNode = nd"
          @mouseleave="hoveredNode = null"
        >
          <!-- Imbalance warning badge -->
          <div v-if="nd.imbalanced" class="imbalance-badge" title="This node holds >80% of cluster guests">
            &#9888; Imbalanced
          </div>
          <div class="nd-header">
            <div class="nd-name">{{ nd.node }}</div>
            <span :class="['nd-status-dot', nd.status === 'online' ? 'nd-status-dot--online' : 'nd-status-dot--offline']"></span>
          </div>
          <div class="nd-host-label">{{ nd.hostName }}</div>
          <div class="nd-counts">
            <span class="nd-count-pill nd-count-pill--vm">&#128421; {{ nd.vms }} VM</span>
            <span class="nd-count-pill nd-count-pill--lxc">&#128230; {{ nd.lxcs }} LXC</span>
          </div>
          <div v-if="nd.cpuPct !== null" class="nd-resource-row">
            <span class="nd-resource-label">CPU</span>
            <div class="nd-mini-bar"><div class="nd-mini-fill" :style="{ width: nd.cpuPct + '%', background: nd.cpuPct > 80 ? '#ef4444' : nd.cpuPct > 60 ? '#f59e0b' : '#10b981' }"></div></div>
            <span class="nd-resource-val">{{ nd.cpuPct }}%</span>
          </div>
          <div v-if="nd.memPct !== null" class="nd-resource-row">
            <span class="nd-resource-label">RAM</span>
            <div class="nd-mini-bar"><div class="nd-mini-fill" :style="{ width: nd.memPct + '%', background: nd.memPct > 80 ? '#ef4444' : nd.memPct > 60 ? '#f59e0b' : '#10b981' }"></div></div>
            <span class="nd-resource-val">{{ nd.memPct }}%</span>
          </div>
          <div class="nd-bar-wrap">
            <div class="nd-bar" :style="{ width: nd.guestSharePct + '%' }"
              :class="nd.imbalanced ? 'nd-bar--warn' : 'nd-bar--ok'"></div>
          </div>
          <div class="nd-share-label">{{ nd.guestSharePct }}% of cluster guests</div>

          <!-- Tooltip on hover -->
          <div v-if="hoveredNode === nd" class="nd-tooltip">
            <div class="ndt-title">{{ nd.node }} — {{ nd.hostName }}</div>
            <div class="ndt-row"><span>VMs:</span> <strong>{{ nd.vms }}</strong></div>
            <div class="ndt-row"><span>LXC:</span> <strong>{{ nd.lxcs }}</strong></div>
            <div class="ndt-row"><span>Total Guests:</span> <strong>{{ nd.vms + nd.lxcs }}</strong></div>
            <div class="ndt-row"><span>Share:</span> <strong>{{ nd.guestSharePct }}%</strong></div>
            <div v-if="nd.imbalanced" class="ndt-warn">Node is overloaded with guests</div>
          </div>
        </div>

        <div v-if="nodeDistribution.length === 0" class="text-muted text-sm p-3">
          No node distribution data available yet.
        </div>
      </div>

      <!-- ── Section 3: Per-host panels ── -->
      <div class="section-title mb-1">Hosts</div>
      <div v-if="hostPanels.length === 0" class="card mb-2">
        <div class="card-body text-center text-muted p-3">No hosts configured.</div>
      </div>
      <div v-else class="host-grid mb-2">
        <div
          v-for="panel in hostPanels"
          :key="panel.hostId"
          class="card host-card"
        >
          <div class="host-card-header">
            <div class="host-name-row">
              <span class="host-name">{{ panel.name }}</span>
              <span :class="['badge', panel.online ? 'badge-success' : 'badge-danger']">
                {{ panel.online ? 'Online' : 'Offline' }}
              </span>
            </div>
            <div class="host-addr text-sm text-muted">{{ panel.address }}</div>
          </div>

          <div class="host-card-body">
            <!-- CPU bar -->
            <div class="resource-row">
              <div class="resource-label text-sm">
                CPU
                <span class="text-muted text-xs">({{ panel.cpuPct }}%)</span>
              </div>
              <div class="mini-bar-wrap">
                <div
                  class="mini-bar-fill"
                  :class="barClass(panel.cpuRatio)"
                  :style="{ width: panel.cpuPct + '%' }"
                ></div>
              </div>
            </div>

            <!-- RAM bar -->
            <div class="resource-row">
              <div class="resource-label text-sm">
                RAM
                <span class="text-muted text-xs">
                  ({{ formatBytesGb(panel.memUsed) }} / {{ formatBytesGb(panel.memTotal) }} GB)
                </span>
              </div>
              <div class="mini-bar-wrap">
                <div
                  class="mini-bar-fill"
                  :class="barClass(panel.memRatio)"
                  :style="{ width: panel.memPct + '%' }"
                ></div>
              </div>
            </div>

            <!-- Counts row -->
            <div class="host-counts text-sm">
              <div class="host-count-item">
                <span class="count-label text-muted">VMs</span>
                <span class="count-value">
                  <span class="text-green">{{ panel.vmsRunning }}</span>
                  <span class="text-muted"> / {{ panel.vmsTotal }}</span>
                </span>
              </div>
              <div class="host-count-item">
                <span class="count-label text-muted">LXC</span>
                <span class="count-value">
                  <span class="text-green">{{ panel.lxcRunning }}</span>
                  <span class="text-muted"> / {{ panel.lxcTotal }}</span>
                </span>
              </div>
              <div class="host-count-item">
                <span class="count-label text-muted">Nodes</span>
                <span class="count-value">{{ panel.nodeCount }}</span>
              </div>
            </div>
          </div>

          <div class="host-card-footer">
            <router-link :to="`/proxmox/${panel.hostId}/cluster`" class="btn btn-outline btn-sm">
              View Cluster &rarr;
            </router-link>
          </div>
        </div>
      </div>

      <!-- ── Section 4: Top VMs by Resource Usage ── -->
      <div class="card mb-2">
        <div class="card-header">
          <h3>Top VMs by Resource Usage</h3>
          <span v-if="!topVmsLoading" class="top-vms-refresh-label">
            Auto-refresh in {{ topVmsCountdown }}s
          </span>
          <button @click="fetchTopVms" class="btn btn-outline btn-sm" :disabled="topVmsLoading">
            {{ topVmsLoading ? 'Loading…' : 'Refresh' }}
          </button>
        </div>

        <div v-if="topVmsLoading && topVms.length === 0" class="loading-spinner"></div>

        <div v-else-if="topVms.length === 0" class="text-center text-muted p-3">
          No running VMs found across all hosts.
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>VMID</th>
                <th>Node</th>
                <th>Host</th>
                <th>CPU %</th>
                <th>MEM %</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="vm in topVms"
                :key="`${vm._hostId}-${vm.node}-${vm.vmid}`"
                class="resource-row-link"
                @click="navigateToResource(vm)"
              >
                <td>{{ vm.name || '—' }}</td>
                <td><strong>{{ vm.vmid }}</strong></td>
                <td>{{ vm.node || '—' }}</td>
                <td class="text-sm text-muted">{{ vm._hostName || '—' }}</td>
                <td>
                  <div class="top-vm-bar-wrap">
                    <div class="top-vm-bar">
                      <div
                        class="top-vm-bar-fill"
                        :class="topVmCpuClass(vm.cpu)"
                        :style="{ width: topVmCpuPct(vm.cpu) + '%' }"
                      ></div>
                    </div>
                    <span class="top-vm-bar-label">{{ topVmCpuPct(vm.cpu) }}%</span>
                  </div>
                </td>
                <td>
                  <div class="top-vm-bar-wrap">
                    <div class="top-vm-bar">
                      <div
                        class="top-vm-bar-fill"
                        :class="topVmMemClass(vm.mem, vm.maxmem)"
                        :style="{ width: topVmMemPct(vm.mem, vm.maxmem) + '%' }"
                      ></div>
                    </div>
                    <span class="top-vm-bar-label">{{ topVmMemPct(vm.mem, vm.maxmem) }}%</span>
                  </div>
                </td>
                <td>
                  <span :class="['badge', vm.status === 'running' ? 'badge-success' : 'badge-danger']">
                    {{ vm.status || '—' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── Section 5: Resource Trends ── -->
      <div class="card mb-2">
        <div
          class="card-header collapsible-header"
          @click="trendsExpanded = !trendsExpanded"
          style="cursor: pointer;"
        >
          <h3>Resource Trends</h3>
          <div class="collapsible-header-right">
            <div v-if="trendsExpanded" class="trend-time-selector" @click.stop>
              <button
                v-for="tf in timeframes"
                :key="tf.value"
                :class="['trend-tf-btn', { active: selectedTimeframe === tf.value }]"
                @click="setTimeframe(tf.value)"
              >{{ tf.label }}</button>
            </div>
            <span v-if="trendsLoading" class="text-muted text-sm">Loading…</span>
            <span class="collapse-chevron" :class="{ 'chevron-open': trendsExpanded }">&#9660;</span>
          </div>
        </div>

        <template v-if="trendsExpanded">
          <div v-if="trendsLoading && trendData.length === 0" class="loading-spinner"></div>
          <div v-else-if="trendData.length === 0" class="text-center text-muted p-3">
            No trend data available.
          </div>
          <div v-else class="trends-body">
            <div class="trend-section">
              <div class="trend-label">Cluster CPU Trend</div>
              <div class="sparkline-wrap">
                <svg :viewBox="`0 0 ${sparklineW} ${sparklineH}`" class="sparkline-svg">
                  <polyline
                    :points="cpuSparklinePoints"
                    class="sparkline-line sparkline-line--cpu"
                    fill="none"
                  />
                  <polyline
                    :points="cpuSparklineArea"
                    class="sparkline-area sparkline-area--cpu"
                    fill="url(#cpuGrad)"
                  />
                  <defs>
                    <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#6366f1" stop-opacity="0.35" />
                      <stop offset="100%" stop-color="#6366f1" stop-opacity="0.02" />
                    </linearGradient>
                  </defs>
                </svg>
                <div class="sparkline-stats">
                  <span class="sp-stat">Avg: <strong>{{ cpuTrendAvg }}%</strong></span>
                  <span class="sp-stat">Peak: <strong>{{ cpuTrendPeak }}%</strong></span>
                </div>
              </div>
            </div>
            <div class="trend-section">
              <div class="trend-label">Cluster Memory Trend</div>
              <div class="sparkline-wrap">
                <svg :viewBox="`0 0 ${sparklineW} ${sparklineH}`" class="sparkline-svg">
                  <polyline
                    :points="memSparklinePoints"
                    class="sparkline-line sparkline-line--mem"
                    fill="none"
                  />
                  <polyline
                    :points="memSparklineArea"
                    class="sparkline-area sparkline-area--mem"
                    fill="url(#memGrad)"
                  />
                  <defs>
                    <linearGradient id="memGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#10b981" stop-opacity="0.35" />
                      <stop offset="100%" stop-color="#10b981" stop-opacity="0.02" />
                    </linearGradient>
                  </defs>
                </svg>
                <div class="sparkline-stats">
                  <span class="sp-stat">Avg: <strong>{{ memTrendAvg }}%</strong></span>
                  <span class="sp-stat">Peak: <strong>{{ memTrendPeak }}%</strong></span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- ── Section 6: Network Overview ── -->
      <div class="card mb-2">
        <div
          class="card-header collapsible-header"
          @click="networkExpanded = !networkExpanded"
          style="cursor: pointer;"
        >
          <h3>Network Overview</h3>
          <div class="collapsible-header-right">
            <span v-if="networkLoading" class="text-muted text-sm">Loading…</span>
            <span class="collapse-chevron" :class="{ 'chevron-open': networkExpanded }">&#9660;</span>
          </div>
        </div>

        <template v-if="networkExpanded">
          <div v-if="networkLoading && networkData.length === 0" class="loading-spinner"></div>

          <div v-else-if="networkData.length === 0" class="text-center text-muted p-3">
            No network data available.
          </div>

          <div v-else class="network-overview-body">
            <div
              v-for="hostGroup in networkData"
              :key="hostGroup.hostId"
              class="network-host-group"
            >
              <div class="network-host-title">{{ hostGroup.hostName }}</div>
              <div
                v-for="nodeGroup in hostGroup.nodes"
                :key="nodeGroup.node"
                class="network-node-group"
              >
                <div class="network-node-title text-sm">
                  Node: <strong>{{ nodeGroup.node }}</strong>
                </div>
                <div v-if="nodeGroup.ifaces.length === 0" class="text-muted text-sm pl-2">
                  No interfaces found.
                </div>
                <template v-else>
                  <div v-if="nodeGroup.physicalBridges.length > 0" class="network-iface-group">
                    <div class="network-iface-group-label text-xs text-muted">Physical Bridges</div>
                    <table class="table network-table">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Type</th>
                          <th>Address / CIDR</th>
                          <th>Ports / Slaves</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="iface in nodeGroup.physicalBridges" :key="iface.iface">
                          <td class="iface-name">{{ iface.iface }}</td>
                          <td class="text-sm text-muted">{{ iface.type || '—' }}</td>
                          <td class="font-mono text-sm">{{ ifaceAddress(iface) }}</td>
                          <td class="text-sm text-muted">{{ ifaceSlaves(iface) }}</td>
                          <td>
                            <span :class="['badge', ifaceUp(iface) ? 'badge-success' : 'badge-danger']">
                              {{ ifaceUp(iface) ? 'UP' : 'DOWN' }}
                            </span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-if="nodeGroup.vlanBridges.length > 0" class="network-iface-group">
                    <div class="network-iface-group-label text-xs text-muted">VLAN Bridges</div>
                    <table class="table network-table">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Type</th>
                          <th>Address / CIDR</th>
                          <th>Ports / Slaves</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="iface in nodeGroup.vlanBridges" :key="iface.iface">
                          <td class="iface-name">{{ iface.iface }}</td>
                          <td class="text-sm text-muted">{{ iface.type || '—' }}</td>
                          <td class="font-mono text-sm">{{ ifaceAddress(iface) }}</td>
                          <td class="text-sm text-muted">{{ ifaceSlaves(iface) }}</td>
                          <td>
                            <span :class="['badge', ifaceUp(iface) ? 'badge-success' : 'badge-danger']">
                              {{ ifaceUp(iface) ? 'UP' : 'DOWN' }}
                            </span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- ── Section 7: Storage Analysis ── -->
      <div class="card mb-2">
        <div
          class="card-header collapsible-header"
          @click="storageExpanded = !storageExpanded"
          style="cursor: pointer;"
        >
          <h3>Storage Analysis</h3>
          <div class="collapsible-header-right">
            <span v-if="storageLoading" class="text-muted text-sm">Loading…</span>
            <span class="collapse-chevron" :class="{ 'chevron-open': storageExpanded }">&#9660;</span>
          </div>
        </div>

        <template v-if="storageExpanded">
          <div v-if="storageLoading && storageData.length === 0" class="loading-spinner"></div>

          <div v-else-if="storageData.length === 0" class="text-center text-muted p-3">
            No storage data available.
          </div>

          <div v-else class="storage-overview-body">
            <div
              v-for="hostGroup in storageData"
              :key="hostGroup.hostId"
              class="storage-host-group"
            >
              <div class="storage-host-title">{{ hostGroup.hostName }}</div>
              <div
                v-for="nodeGroup in hostGroup.nodes"
                :key="nodeGroup.node"
                class="storage-node-group"
              >
                <div class="storage-node-title text-sm">
                  Node: <strong>{{ nodeGroup.node }}</strong>
                </div>

                <div v-if="nodeGroup.pools.length === 0" class="text-muted text-sm pl-2">
                  No storage pools found.
                </div>

                <div v-else class="table-container">
                  <table class="table storage-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Total</th>
                        <th>Used</th>
                        <th>Available</th>
                        <th style="min-width: 140px;">Usage</th>
                        <th>Shared</th>
                        <th>Content</th>
                        <th>Health</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="pool in nodeGroup.pools"
                        :key="pool.storage"
                        :class="storageUsagePct(pool.used, pool.total) > 85 ? 'row-danger' : ''"
                      >
                        <td class="storage-name">
                          <span class="storage-type-icon">&#128190;</span>
                          {{ pool.storage }}
                        </td>
                        <td class="text-sm text-muted">{{ pool.type || '—' }}</td>
                        <td class="text-sm font-mono">{{ pool.total ? formatBytes(pool.total) : '—' }}</td>
                        <td class="text-sm font-mono">{{ pool.used != null ? formatBytes(pool.used) : '—' }}</td>
                        <td class="text-sm font-mono">{{ pool.avail != null ? formatBytes(pool.avail) : '—' }}</td>
                        <td>
                          <div class="storage-bar-wrap">
                            <div class="storage-bar">
                              <div
                                class="storage-bar-fill"
                                :class="storageBarClass(pool.used, pool.total)"
                                :style="{ width: storageUsagePct(pool.used, pool.total) + '%' }"
                              ></div>
                            </div>
                            <span class="storage-bar-label">{{ storageUsagePct(pool.used, pool.total) }}%</span>
                          </div>
                        </td>
                        <td>
                          <span v-if="pool.shared" class="badge badge-info">Yes</span>
                          <span v-else class="text-muted text-sm">No</span>
                        </td>
                        <td>
                          <div class="content-pills">
                            <span
                              v-for="ct in parseContentTypes(pool.content)"
                              :key="ct"
                              :class="['content-pill', contentPillClass(ct)]"
                            >{{ ct }}</span>
                          </div>
                        </td>
                        <td>
                          <span
                            :class="['badge', storageUsagePct(pool.used, pool.total) > 85 ? 'badge-danger' : storageUsagePct(pool.used, pool.total) > 70 ? 'badge-warning' : 'badge-success']"
                          >
                            {{ storageUsagePct(pool.used, pool.total) > 85 ? 'Critical' : storageUsagePct(pool.used, pool.total) > 70 ? 'Warning' : 'OK' }}
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- ── Section 8: All Resources table ── -->
      <div class="card">
        <div class="card-header">
          <h3>All Resources</h3>
          <div class="table-filters flex gap-1 align-center flex-wrap">
            <select v-model="filterHost" class="form-control filter-select">
              <option value="">All Hosts</option>
              <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
            </select>
            <select v-model="filterType" class="form-control filter-select">
              <option value="">All Types</option>
              <option value="qemu">VM</option>
              <option value="lxc">LXC</option>
            </select>
            <select v-model="filterStatus" class="form-control filter-select">
              <option value="">All Status</option>
              <option value="running">Running</option>
              <option value="stopped">Stopped</option>
              <option value="paused">Paused</option>
            </select>
            <input
              v-model="searchQuery"
              class="form-control search-input"
              placeholder="Search name, VMID, node..."
            />
            <label class="group-toggle-label">
              <input type="checkbox" v-model="groupByNode" />
              Group by Node
            </label>
          </div>
        </div>

        <div v-if="loading && allResources.length === 0" class="loading-spinner"></div>

        <div v-else-if="filteredResources.length === 0 && groupedResources.length === 0" class="text-center text-muted p-3">
          No resources match the current filters.
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th
                  v-for="col in columns"
                  :key="col.key"
                  :class="['sortable-th', sortKey === col.key ? 'sort-active' : '']"
                  @click="setSort(col.key)"
                >
                  {{ col.label }}
                  <span class="sort-icon">
                    {{ sortKey === col.key ? (sortDesc ? '▼' : '▲') : '⇅' }}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody v-if="!groupByNode">
              <tr
                v-for="r in filteredResources"
                :key="`${r._hostId}-${r.id}`"
                class="resource-row-link"
                @click="navigateToResource(r)"
              >
                <td>
                  <span class="type-icon">{{ typeIcon(r.type) }}</span>
                  <span :class="['badge', typeBadgeClass(r.type)]">
                    {{ typeLabel(r.type) }}
                  </span>
                </td>
                <td>{{ r.name || '—' }}</td>
                <td>
                  <div class="tags-cell">
                    <template v-if="r.tags && r.tags.trim()">
                      <span
                        v-for="tag in parseTags(r.tags)"
                        :key="tag"
                        :class="['tag-pill', tagPillClass(tag)]"
                      >{{ tag }}</span>
                    </template>
                    <span v-else class="text-muted">—</span>
                  </div>
                </td>
                <td><strong>{{ r.vmid || '—' }}</strong></td>
                <td>
                  <span :class="['badge', statusBadgeClass(r.status)]">
                    {{ r.status || '—' }}
                  </span>
                </td>
                <td>{{ r.cpu != null ? (r.cpu * 100).toFixed(1) + '%' : '—' }}</td>
                <td>{{ r.mem != null ? formatBytes(r.mem) : '—' }}</td>
                <td>
                  <span v-if="r.status === 'running' && r.uptime" class="uptime-badge">
                    {{ formatUptime(r.uptime) }}
                  </span>
                  <span v-else class="text-muted">—</span>
                </td>
                <td>{{ r.node || '—' }}</td>
                <td>{{ r._hostName || '—' }}</td>
              </tr>
            </tbody>
            <tbody v-else>
              <template v-for="group in groupedResources" :key="group.groupKey">
                <!-- Node group header row -->
                <tr class="node-group-header">
                  <td colspan="10" class="node-group-cell">
                    <span class="node-group-icon">&#127760;</span>
                    <strong>{{ group.node }}</strong>
                    <span class="text-muted text-sm"> — {{ group.hostName }}</span>
                    <span class="node-group-count">{{ group.items.length }} guests</span>
                  </td>
                </tr>
                <!-- VM rows indented -->
                <tr
                  v-for="r in group.items"
                  :key="`${r._hostId}-${r.id}`"
                  class="resource-row-link resource-row-indented"
                  @click="navigateToResource(r)"
                >
                  <td>
                    <span class="type-icon">{{ typeIcon(r.type) }}</span>
                    <span :class="['badge', typeBadgeClass(r.type)]">
                      {{ typeLabel(r.type) }}
                    </span>
                  </td>
                  <td>{{ r.name || '—' }}</td>
                  <td>
                    <div class="tags-cell">
                      <template v-if="r.tags && r.tags.trim()">
                        <span
                          v-for="tag in parseTags(r.tags)"
                          :key="tag"
                          :class="['tag-pill', tagPillClass(tag)]"
                        >{{ tag }}</span>
                      </template>
                      <span v-else class="text-muted">—</span>
                    </div>
                  </td>
                  <td><strong>{{ r.vmid || '—' }}</strong></td>
                  <td>
                    <span :class="['badge', statusBadgeClass(r.status)]">
                      {{ r.status || '—' }}
                    </span>
                  </td>
                  <td>{{ r.cpu != null ? (r.cpu * 100).toFixed(1) + '%' : '—' }}</td>
                  <td>{{ r.mem != null ? formatBytes(r.mem) : '—' }}</td>
                  <td>
                    <span v-if="r.status === 'running' && r.uptime" class="uptime-badge">
                      {{ formatUptime(r.uptime) }}
                    </span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>{{ r.node || '—' }}</td>
                  <td>{{ r._hostName || '—' }}</td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import { formatBytes } from '@/utils/proxmox'

const router = useRouter()
const toast = useToast()

// ── State ──────────────────────────────────────────────────────────────────
const hosts = ref([])
const allResources = ref([])
const loading = ref(false)
const loadError = ref(false)

// Datacenter summaries per host
const datacenterSummaries = ref({})  // hostId -> summary object

// Top VMs state
const topVms = ref([])
const topVmsLoading = ref(false)
const topVmsCountdown = ref(30)
let topVmsInterval = null
let topVmsTickInterval = null

// Network overview state
const networkData = ref([])
const networkLoading = ref(false)
const networkExpanded = ref(false)

// Storage overview state
const storageData = ref([])
const storageLoading = ref(false)
const storageExpanded = ref(false)

// Trends state
const trendsExpanded = ref(false)
const trendsLoading = ref(false)
const trendData = ref([])  // [{time, cpu, mem}]
const selectedTimeframe = ref('hour')
const timeframes = [
  { value: 'hour', label: '1h' },
  { value: 'day', label: '24h' },
  { value: 'week', label: '7d' },
]
const sparklineW = 400
const sparklineH = 60

// Node distribution hover
const hoveredNode = ref(null)

// Filters
const filterHost = ref('')
const filterType = ref('')
const filterStatus = ref('')
const searchQuery = ref('')
const groupByNode = ref(false)

// Sort
const sortKey = ref('name')
const sortDesc = ref(false)

const columns = [
  { key: 'type',      label: 'Type' },
  { key: 'name',      label: 'Name' },
  { key: 'tags',      label: 'Tags' },
  { key: 'vmid',      label: 'VMID' },
  { key: 'status',    label: 'Status' },
  { key: 'cpu',       label: 'CPU %' },
  { key: 'mem',       label: 'Memory' },
  { key: 'uptime',    label: 'Uptime' },
  { key: 'node',      label: 'Node' },
  { key: '_hostName', label: 'Host' },
]

// ── Computed summary ───────────────────────────────────────────────────────
const summary = computed(() => {
  const vmTypes = allResources.value.filter(r => r.type === 'qemu' || r.type === 'lxc')

  let vmsTotal = 0, vmsRunning = 0, vmsPaused = 0
  let lxcTotal = 0, lxcRunning = 0
  let memUsed = 0, memTotal = 0
  let cpuCores = 0
  let totalCpuUsedFrac = 0
  let totalMemUsedFrac = 0
  let nodeCount = 0

  for (const r of vmTypes) {
    if (r.type === 'qemu') {
      vmsTotal++
      if (r.status === 'running') vmsRunning++
      else if (r.status === 'paused') vmsPaused++
    } else {
      lxcTotal++
      if (r.status === 'running') lxcRunning++
    }
    memUsed += r.mem || 0
    memTotal += r.maxmem || 0
    cpuCores += r.maxcpu || 0
    if (r.status === 'running' && r.cpu != null) {
      totalCpuUsedFrac += r.cpu
    }
  }

  const nodeItems = allResources.value.filter(r => r.type === 'node')
  nodeCount = nodeItems.length

  // Aggregate node-level CPU/mem for avg
  let nodeCpuSum = 0, nodeMemSum = 0, nodeCount2 = 0
  for (const r of nodeItems) {
    if (r.cpu != null) { nodeCpuSum += r.cpu; nodeCount2++ }
    if (r.mem != null && r.maxmem) nodeMemSum += (r.mem / r.maxmem)
  }

  const avgCpuRatio = nodeCount2 > 0 ? nodeCpuSum / nodeCount2 : (cpuCores > 0 ? totalCpuUsedFrac / cpuCores : 0)
  const avgMemRatio = nodeCount2 > 0 ? nodeMemSum / nodeCount2 : (memTotal > 0 ? memUsed / memTotal : 0)

  // Storage aggregation
  let storageTotal = 0, storageUsed = 0
  for (const h of Object.values(datacenterSummaries.value)) {
    if (h.storages) {
      for (const s of h.storages) {
        storageTotal += s.total || 0
        storageUsed += s.used || 0
      }
    }
  }

  return {
    totalHosts: hosts.value.length,
    totalNodes: nodeCount,
    vmsTotal,
    vmsRunning,
    vmsPaused,
    lxcTotal,
    lxcRunning,
    totalGuests: vmsTotal + lxcTotal,
    memUsed,
    memTotal,
    totalCpuCores: cpuCores,
    avgCpuRatio,
    avgMemRatio,
    avgCpuPct: Math.round(avgCpuRatio * 100),
    avgMemPct: Math.round(avgMemRatio * 100),
    storageTotal,
    storageUsed,
  }
})

const storageUsedPct = computed(() => {
  if (!summary.value.storageTotal) return 0
  return Math.round((summary.value.storageUsed / summary.value.storageTotal) * 100)
})

const clusterEfficiency = computed(() => {
  return Math.round((summary.value.avgCpuPct + summary.value.avgMemPct) / 2)
})

const efficiencyRingClass = computed(() => {
  const s = clusterEfficiency.value
  if (s >= 80) return 'ring-fill--danger'
  if (s >= 60) return 'ring-fill--warning'
  if (s >= 30) return 'ring-fill--ok'
  return 'ring-fill--low'
})

const efficiencyRingStyle = computed(() => {
  const circumference = 2 * Math.PI * 40
  const pct = clusterEfficiency.value / 100
  return {
    strokeDasharray: `${(pct * circumference).toFixed(1)} ${circumference.toFixed(1)}`,
    strokeDashoffset: '0',
  }
})

// Donut chart styles
const cpuDonutStyle = computed(() => {
  const r = 50
  const circ = 2 * Math.PI * r
  const pct = summary.value.avgCpuPct / 100
  return {
    strokeDasharray: `${(pct * circ).toFixed(1)} ${circ.toFixed(1)}`,
    strokeWidth: '12',
    stroke: '#6366f1',
    fill: 'none',
  }
})

const memDonutStyle = computed(() => {
  const r = 36
  const circ = 2 * Math.PI * r
  const pct = summary.value.avgMemPct / 100
  return {
    strokeDasharray: `${(pct * circ).toFixed(1)} ${circ.toFixed(1)}`,
    strokeWidth: '12',
    stroke: '#10b981',
    fill: 'none',
  }
})

// VM pie chart
const vmRunningSlice = computed(() => {
  const total = summary.value.totalGuests
  if (!total) return { strokeDasharray: '0 189', strokeWidth: '28', stroke: '#10b981', fill: 'none' }
  const r = 30
  const circ = 2 * Math.PI * r
  const running = summary.value.vmsRunning + summary.value.lxcRunning
  const pct = running / total
  return {
    strokeDasharray: `${(pct * circ).toFixed(1)} ${circ.toFixed(1)}`,
    strokeWidth: '28',
    stroke: '#10b981',
    fill: 'none',
  }
})

const vmPausedSlice = computed(() => {
  const total = summary.value.totalGuests
  if (!total) return { strokeDasharray: '0 189', strokeWidth: '28', stroke: '#f59e0b', fill: 'none', strokeDashoffset: '0' }
  const r = 30
  const circ = 2 * Math.PI * r
  const running = summary.value.vmsRunning + summary.value.lxcRunning
  const paused = summary.value.vmsPaused
  const runningPct = running / total
  const pausedPct = paused / total
  const runningLen = runningPct * circ
  return {
    strokeDasharray: `${(pausedPct * circ).toFixed(1)} ${circ.toFixed(1)}`,
    strokeWidth: '28',
    stroke: '#f59e0b',
    fill: 'none',
    strokeDashoffset: `-${runningLen.toFixed(1)}`,
  }
})

// ── Node distribution map ──────────────────────────────────────────────────
const nodeDistribution = computed(() => {
  const map = {}

  // Seed ALL cluster nodes first (type='node') so empty nodes appear too
  for (const r of allResources.value) {
    if (r.type === 'node' && r.node) {
      const key = `${r._hostId}-${r.node}`
      if (!map[key]) {
        map[key] = {
          hostId: r._hostId,
          hostName: r._hostName || '',
          node: r.node,
          vms: 0,
          lxcs: 0,
          cpuPct: r.cpu != null ? Math.round(r.cpu * 100) : null,
          memPct: (r.mem && r.maxmem) ? Math.round((r.mem / r.maxmem) * 100) : null,
          status: r.status || 'online',
        }
      }
    }
  }

  // Count guests per node
  for (const r of allResources.value) {
    if ((r.type === 'qemu' || r.type === 'lxc') && r.node) {
      const key = `${r._hostId}-${r.node}`
      if (!map[key]) {
        // Guest on a node not listed as type=node (shouldn't happen, but handle gracefully)
        map[key] = {
          hostId: r._hostId,
          hostName: r._hostName || '',
          node: r.node,
          vms: 0,
          lxcs: 0,
          cpuPct: null,
          memPct: null,
          status: 'online',
        }
      }
      if (r.type === 'qemu') map[key].vms++
      else map[key].lxcs++
    }
  }

  const items = Object.values(map)
  const totalGuests = items.reduce((s, n) => s + n.vms + n.lxcs, 0)

  return items.map(nd => {
    const guests = nd.vms + nd.lxcs
    const sharePct = totalGuests > 0 ? Math.round((guests / totalGuests) * 100) : 0
    const imbalanced = items.length > 1 && totalGuests > 0 && sharePct > 80
    return { ...nd, guestSharePct: sharePct, imbalanced }
  }).sort((a, b) => (b.vms + b.lxcs) - (a.vms + a.lxcs))
})

// ── Per-host panels ────────────────────────────────────────────────────────
const hostPanels = computed(() => {
  return hosts.value.map(host => {
    const resources = allResources.value.filter(r => r._hostId === host.id)

    let vmsTotal = 0, vmsRunning = 0
    let lxcTotal = 0, lxcRunning = 0
    let memUsed = 0, memTotal = 0
    let cpuUsed = 0, cpuCores = 0
    let nodeCount = 0

    for (const r of resources) {
      if (r.type === 'qemu') {
        vmsTotal++
        if (r.status === 'running') {
          vmsRunning++
          cpuUsed += (r.cpu || 0) * (r.maxcpu || 1)
        }
        cpuCores += r.maxcpu || 0
        memUsed += r.mem || 0
        memTotal += r.maxmem || 0
      } else if (r.type === 'lxc') {
        lxcTotal++
        if (r.status === 'running') {
          lxcRunning++
          cpuUsed += (r.cpu || 0) * (r.maxcpu || 1)
        }
        cpuCores += r.maxcpu || 0
        memUsed += r.mem || 0
        memTotal += r.maxmem || 0
      } else if (r.type === 'node') {
        nodeCount++
      }
    }

    const cpuRatio = cpuCores > 0 ? Math.min(1, cpuUsed / cpuCores) : 0
    const memRatio = memTotal > 0 ? Math.min(1, memUsed / memTotal) : 0

    return {
      hostId: host.id,
      name: host.name || host.hostname || `Host ${host.id}`,
      address: host.address || host.host || '',
      online: host.status === 'online' || host.connected === true || resources.length > 0,
      vmsTotal, vmsRunning, lxcTotal, lxcRunning, nodeCount,
      memUsed, memTotal, cpuRatio, memRatio,
      cpuPct: Math.round(cpuRatio * 100),
      memPct: Math.round(memRatio * 100),
    }
  })
})

// ── Filtered + sorted resource table ──────────────────────────────────────
const filteredResources = computed(() => {
  if (groupByNode.value) return []

  let list = allResources.value.filter(r => r.type === 'qemu' || r.type === 'lxc')

  if (filterHost.value) {
    list = list.filter(r => String(r._hostId) === String(filterHost.value))
  }
  if (filterType.value) {
    list = list.filter(r => r.type === filterType.value)
  }
  if (filterStatus.value) {
    list = list.filter(r => r.status === filterStatus.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(r =>
      (r.name || '').toLowerCase().includes(q) ||
      String(r.vmid || '').includes(q) ||
      (r.node || '').toLowerCase().includes(q)
    )
  }

  const key = sortKey.value
  list = [...list].sort((a, b) => {
    let av = a[key] ?? ''
    let bv = b[key] ?? ''
    if (typeof av === 'string') av = av.toLowerCase()
    if (typeof bv === 'string') bv = bv.toLowerCase()
    if (av < bv) return sortDesc.value ? 1 : -1
    if (av > bv) return sortDesc.value ? -1 : 1
    return 0
  })

  return list
})

const groupedResources = computed(() => {
  if (!groupByNode.value) return []

  let list = allResources.value.filter(r => r.type === 'qemu' || r.type === 'lxc')

  if (filterHost.value) list = list.filter(r => String(r._hostId) === String(filterHost.value))
  if (filterType.value) list = list.filter(r => r.type === filterType.value)
  if (filterStatus.value) list = list.filter(r => r.status === filterStatus.value)
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(r =>
      (r.name || '').toLowerCase().includes(q) ||
      String(r.vmid || '').includes(q) ||
      (r.node || '').toLowerCase().includes(q)
    )
  }

  const groups = {}
  for (const r of list) {
    const key = `${r._hostId}-${r.node}`
    if (!groups[key]) {
      groups[key] = {
        groupKey: key,
        node: r.node || '(unknown)',
        hostName: r._hostName || '',
        items: [],
      }
    }
    groups[key].items.push(r)
  }

  return Object.values(groups).sort((a, b) => a.node.localeCompare(b.node))
})

// ── Trend sparkline computations ───────────────────────────────────────────
function buildSparklinePoints(data, field) {
  if (!data.length) return ''
  const vals = data.map(d => parseFloat(d[field] || 0))
  const maxVal = Math.max(...vals, 1)
  const step = sparklineW / Math.max(vals.length - 1, 1)
  return vals.map((v, i) => {
    const x = i * step
    const y = sparklineH - (v / maxVal) * (sparklineH - 4) - 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

function buildSparklineArea(data, field) {
  if (!data.length) return ''
  const pts = buildSparklinePoints(data, field)
  const lastX = ((data.length - 1) * sparklineW / Math.max(data.length - 1, 1)).toFixed(1)
  return `${pts} ${lastX},${sparklineH} 0,${sparklineH}`
}

const cpuSparklinePoints = computed(() => buildSparklinePoints(trendData.value, 'cpu'))
const cpuSparklineArea = computed(() => buildSparklineArea(trendData.value, 'cpu'))
const memSparklinePoints = computed(() => buildSparklinePoints(trendData.value, 'mem'))
const memSparklineArea = computed(() => buildSparklineArea(trendData.value, 'mem'))

const cpuTrendAvg = computed(() => {
  if (!trendData.value.length) return 0
  const sum = trendData.value.reduce((s, d) => s + parseFloat(d.cpu || 0), 0)
  return (sum / trendData.value.length).toFixed(1)
})
const cpuTrendPeak = computed(() => {
  if (!trendData.value.length) return 0
  return Math.max(...trendData.value.map(d => parseFloat(d.cpu || 0))).toFixed(1)
})
const memTrendAvg = computed(() => {
  if (!trendData.value.length) return 0
  const sum = trendData.value.reduce((s, d) => s + parseFloat(d.mem || 0), 0)
  return (sum / trendData.value.length).toFixed(1)
})
const memTrendPeak = computed(() => {
  if (!trendData.value.length) return 0
  return Math.max(...trendData.value.map(d => parseFloat(d.mem || 0))).toFixed(1)
})

// ── Helpers ────────────────────────────────────────────────────────────────
function barClass(ratio) {
  if (ratio >= 0.9) return 'fill--danger'
  if (ratio >= 0.75) return 'fill--warning'
  return 'fill--ok'
}

function formatBytesGb(bytes) {
  if (!bytes) return '0'
  return (bytes / 1073741824).toFixed(1)
}

function setSort(key) {
  if (sortKey.value === key) {
    sortDesc.value = !sortDesc.value
  } else {
    sortKey.value = key
    sortDesc.value = false
  }
}

function navigateToResource(r) {
  if (!r.vmid || !r.node || !r._hostId) return
  if (r.type === 'lxc') {
    router.push(`/proxmox/${r._hostId}/nodes/${r.node}/lxc/${r.vmid}`)
  } else {
    router.push(`/proxmox/${r._hostId}/nodes/${r.node}/vms/${r.vmid}`)
  }
}

function parseTags(tagsStr) {
  if (!tagsStr || !tagsStr.trim()) return []
  return tagsStr.split(/[;,]/).map(t => t.trim()).filter(Boolean)
}

function tagPillClass(tag) {
  // Consistent color based on tag content hash
  const colors = ['tag-blue', 'tag-green', 'tag-purple', 'tag-orange', 'tag-teal', 'tag-pink']
  let hash = 0
  for (let i = 0; i < tag.length; i++) hash = (hash * 31 + tag.charCodeAt(i)) & 0xffffff
  return colors[Math.abs(hash) % colors.length]
}

function formatUptime(seconds) {
  if (!seconds || seconds <= 0) return '—'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function typeIcon(type) {
  if (type === 'lxc') return '📦'
  if (type === 'node') return '🖧'
  if (type === 'storage') return '💾'
  return '🖥️'
}

function typeLabel(type) {
  if (type === 'lxc') return 'LXC'
  if (type === 'node') return 'Node'
  if (type === 'storage') return 'Storage'
  return 'VM'
}

function typeBadgeClass(type) {
  if (type === 'lxc') return 'badge-warning'
  if (type === 'node') return 'badge-secondary'
  return 'badge-info'
}

function statusBadgeClass(status) {
  if (status === 'running') return 'badge-success'
  if (status === 'paused') return 'badge-warning'
  return 'badge-danger'
}

function parseContentTypes(content) {
  if (!content || !content.trim()) return []
  return content.split(',').map(c => c.trim()).filter(Boolean)
}

function contentPillClass(ct) {
  const map = {
    'images': 'cp-images',
    'rootdir': 'cp-rootdir',
    'backup': 'cp-backup',
    'iso': 'cp-iso',
    'vztmpl': 'cp-vztmpl',
    'snippets': 'cp-snippets',
  }
  return map[ct.toLowerCase()] || ''
}

// ── Network helpers ────────────────────────────────────────────────────────
function ifaceAddress(iface) {
  if (iface.cidr) return iface.cidr
  if (iface.address && iface.netmask) return `${iface.address}/${iface.netmask}`
  if (iface.address) return iface.address
  return '—'
}

function ifaceSlaves(iface) {
  const s = iface.bridge_ports || iface.slaves || iface.ovs_ports || ''
  return s || '—'
}

function ifaceUp(iface) {
  if (iface.active != null) return iface.active === 1 || iface.active === true
  if (iface.autostart != null) return iface.autostart === 1 || iface.autostart === true
  return false
}

function isVlanBridge(iface) {
  if (iface.bridge_vlan_aware) return true
  if (iface.vlan_id != null) return true
  if (/\.\d+$/.test(iface.iface || '')) return true
  if (/^vlan\d+$/i.test(iface.iface || '')) return true
  return false
}

// ── Storage helpers ────────────────────────────────────────────────────────
function storageUsagePct(used, total) {
  if (!total || total === 0) return 0
  return Math.min(100, Math.round((used / total) * 100))
}

function storageBarClass(used, total) {
  const pct = storageUsagePct(used, total)
  if (pct > 85) return 'fill--danger'
  if (pct >= 70) return 'fill--warning'
  return 'fill--ok'
}

function setTimeframe(tf) {
  selectedTimeframe.value = tf
  fetchTrendData()
}

// ── Data loading ───────────────────────────────────────────────────────────
async function fetchAll() {
  loading.value = true
  loadError.value = false

  try {
    const hostsRes = await api.proxmox.listHosts()
    const hostList = hostsRes.data || []
    hosts.value = hostList

    if (hostList.length === 0) {
      allResources.value = []
      return
    }

    const results = await Promise.allSettled(
      hostList.map(host =>
        api.pveNode.clusterResources(host.id).then(res => ({
          hostId: host.id,
          hostName: host.name || host.hostname || `Host ${host.id}`,
          resources: res.data || [],
        }))
      )
    )

    const flat = []
    for (const result of results) {
      if (result.status === 'fulfilled') {
        const { hostId, hostName, resources } = result.value
        for (const r of resources) {
          flat.push({ ...r, _hostId: hostId, _hostName: hostName })
        }
      }
    }

    allResources.value = flat

    // Also fetch datacenter summaries for each host (for storage totals)
    fetchDatacenterSummaries(hostList)
  } catch (err) {
    console.error('Failed to load datacenter data:', err)
    loadError.value = true
    toast.error('Failed to load datacenter data')
  } finally {
    loading.value = false
  }
}

async function fetchDatacenterSummaries(hostList) {
  const list = hostList || hosts.value
  const results = await Promise.allSettled(
    list.map(host =>
      api.proxmox.getDatacenterSummary(host.id).then(res => ({ hostId: host.id, data: res.data }))
    )
  )

  const map = {}
  for (const r of results) {
    if (r.status === 'fulfilled') {
      map[r.value.hostId] = r.value.data
    }
  }
  datacenterSummaries.value = map
}

async function refresh() {
  await fetchAll()
  if (networkExpanded.value) await fetchNetworkData()
  if (storageExpanded.value) await fetchStorageData()
  if (trendsExpanded.value) await fetchTrendData()
}

// ── Trend data loading ─────────────────────────────────────────────────────
async function fetchTrendData() {
  trendsLoading.value = true
  try {
    const hostList = hosts.value
    if (!hostList.length) return

    // Fetch RRD data from first available node across all hosts
    const allPoints = []

    for (const host of hostList) {
      const nodeItems = allResources.value
        .filter(r => r._hostId === host.id && r.type === 'node')
        .slice(0, 3)  // max 3 nodes per host for perf

      for (const nodeItem of nodeItems) {
        try {
          const res = await api.pveNode.nodeRrdData(host.id, nodeItem.node, {
            timeframe: selectedTimeframe.value,
            cf: 'AVERAGE',
          })
          const data = res.data || []
          for (const pt of data) {
            if (pt.time) {
              allPoints.push({
                time: pt.time,
                cpu: parseFloat((pt.cpu || 0) * 100).toFixed(1),
                mem: pt.memtotal > 0 ? parseFloat((pt.memused / pt.memtotal) * 100).toFixed(1) : 0,
              })
            }
          }
        } catch {
          // ignore failed nodes
        }
      }
    }

    // Group by time bucket (avg across nodes)
    if (allPoints.length === 0) {
      trendData.value = []
      return
    }

    const buckets = {}
    for (const pt of allPoints) {
      if (!buckets[pt.time]) buckets[pt.time] = { cpu: [], mem: [] }
      buckets[pt.time].cpu.push(parseFloat(pt.cpu))
      buckets[pt.time].mem.push(parseFloat(pt.mem))
    }

    trendData.value = Object.entries(buckets)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([time, vals]) => ({
        time: Number(time),
        cpu: (vals.cpu.reduce((s, v) => s + v, 0) / vals.cpu.length).toFixed(1),
        mem: (vals.mem.reduce((s, v) => s + v, 0) / vals.mem.length).toFixed(1),
      }))

  } catch (err) {
    console.error('Failed to load trend data:', err)
  } finally {
    trendsLoading.value = false
  }
}

// ── Network data loading ───────────────────────────────────────────────────
async function fetchNetworkData() {
  networkLoading.value = true
  try {
    const hostList = hosts.value.length > 0 ? hosts.value : (await api.proxmox.listHosts()).data || []

    const hostResults = await Promise.allSettled(
      hostList.map(async host => {
        const nodeNames = [
          ...new Set(
            allResources.value
              .filter(r => r._hostId === host.id && r.type === 'node')
              .map(r => r.node)
              .filter(Boolean)
          )
        ]

        const nodeGroups = await Promise.allSettled(
          nodeNames.map(async nodeName => {
            try {
              const res = await api.pveNode.listNetwork(host.id, nodeName)
              const ifaces = (res.data || []).filter(
                i => i.type === 'bridge' || i.type === 'OVSBridge' || i.type === 'bond' || i.type === 'eth' || i.type === 'vlan'
              )
              const physicalBridges = ifaces.filter(i => !isVlanBridge(i))
              const vlanBridges = ifaces.filter(i => isVlanBridge(i))
              return { node: nodeName, ifaces, physicalBridges, vlanBridges }
            } catch {
              return { node: nodeName, ifaces: [], physicalBridges: [], vlanBridges: [] }
            }
          })
        )

        return {
          hostId: host.id,
          hostName: host.name || host.hostname || `Host ${host.id}`,
          nodes: nodeGroups.filter(r => r.status === 'fulfilled').map(r => r.value),
        }
      })
    )

    networkData.value = hostResults
      .filter(r => r.status === 'fulfilled')
      .map(r => r.value)
      .filter(h => h.nodes.length > 0)
  } catch (err) {
    console.error('Failed to load network data:', err)
  } finally {
    networkLoading.value = false
  }
}

// ── Storage data loading ───────────────────────────────────────────────────
async function fetchStorageData() {
  storageLoading.value = true
  try {
    const hostList = hosts.value.length > 0 ? hosts.value : (await api.proxmox.listHosts()).data || []

    const hostResults = await Promise.allSettled(
      hostList.map(async host => {
        const nodeNames = [
          ...new Set(
            allResources.value
              .filter(r => r._hostId === host.id && r.type === 'node')
              .map(r => r.node)
              .filter(Boolean)
          )
        ]

        const nodeGroups = await Promise.allSettled(
          nodeNames.map(async nodeName => {
            try {
              const res = await api.pveNode.listStorage(host.id, nodeName)
              const pools = res.data || []
              return { node: nodeName, pools }
            } catch {
              return { node: nodeName, pools: [] }
            }
          })
        )

        return {
          hostId: host.id,
          hostName: host.name || host.hostname || `Host ${host.id}`,
          nodes: nodeGroups.filter(r => r.status === 'fulfilled').map(r => r.value),
        }
      })
    )

    storageData.value = hostResults
      .filter(r => r.status === 'fulfilled')
      .map(r => r.value)
      .filter(h => h.nodes.length > 0)
  } catch (err) {
    console.error('Failed to load storage data:', err)
  } finally {
    storageLoading.value = false
  }
}

// ── Top VMs helpers ─────────────────────────────────────────────────────────
function topVmCpuPct(cpu) {
  if (cpu == null) return 0
  return Math.round(cpu * 100)
}
function topVmCpuClass(cpu) {
  const pct = topVmCpuPct(cpu)
  if (pct >= 80) return 'fill--danger'
  if (pct >= 60) return 'fill--warning'
  return 'fill--ok'
}
function topVmMemPct(mem, maxmem) {
  if (!mem || !maxmem) return 0
  return Math.round((mem / maxmem) * 100)
}
function topVmMemClass(mem, maxmem) {
  const pct = topVmMemPct(mem, maxmem)
  if (pct >= 80) return 'fill--danger'
  if (pct >= 60) return 'fill--warning'
  return 'fill--ok'
}

async function fetchTopVms() {
  topVmsLoading.value = true
  topVmsCountdown.value = 30
  try {
    const hostList = hosts.value.length > 0 ? hosts.value : (await api.proxmox.listHosts()).data || []

    const results = await Promise.allSettled(
      hostList.map(host =>
        api.pveNode.clusterResources(host.id, 'vm').then(res => ({
          hostId: host.id,
          hostName: host.name || host.hostname || `Host ${host.id}`,
          resources: res.data || [],
        }))
      )
    )

    const vms = []
    for (const result of results) {
      if (result.status === 'fulfilled') {
        const { hostId, hostName, resources } = result.value
        for (const r of resources) {
          if (r.type === 'qemu') {
            vms.push({ ...r, _hostId: hostId, _hostName: hostName })
          }
        }
      }
    }

    vms.sort((a, b) => (b.cpu || 0) - (a.cpu || 0))
    topVms.value = vms.slice(0, 10)
  } catch (err) {
    console.error('Failed to fetch top VMs:', err)
  } finally {
    topVmsLoading.value = false
  }
}

// ── Watchers for lazy-load of collapsible sections ─────────────────────────
watch(networkExpanded, (val) => {
  if (val && networkData.value.length === 0) fetchNetworkData()
})

watch(storageExpanded, (val) => {
  if (val && storageData.value.length === 0) fetchStorageData()
})

watch(trendsExpanded, (val) => {
  if (val && trendData.value.length === 0) fetchTrendData()
})

onMounted(() => {
  fetchAll()
  fetchTopVms()

  topVmsInterval = setInterval(() => {
    if (document.visibilityState !== 'hidden') fetchTopVms()
    topVmsCountdown.value = 30
  }, 30000)

  topVmsTickInterval = setInterval(() => {
    if (document.visibilityState !== 'hidden' && topVmsCountdown.value > 0) {
      topVmsCountdown.value--
    }
  }, 1000)
})

onUnmounted(() => {
  clearInterval(topVmsInterval)
  clearInterval(topVmsTickInterval)
})
</script>

<style scoped>
.datacenter-page {
  padding: 0;
}

/* ── Page header ─────────────────────────────────────────────────────────── */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.page-header-left h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── Resource Overview Grid ──────────────────────────────────────────────── */
.resource-overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1rem;
}

/* ── Efficiency card ─────────────────────────────────────────────────────── */
.efficiency-card .card-header { border-bottom: 1px solid var(--border-color); }

.efficiency-body {
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  align-items: center;
}

.efficiency-score-ring {
  width: 120px;
  height: 120px;
}

.efficiency-svg {
  width: 100%;
  height: 100%;
}

.ring-bg {
  fill: none;
  stroke: var(--border-color);
  stroke-width: 10;
}

.ring-fill {
  fill: none;
  stroke-width: 10;
  transition: stroke-dasharray 0.6s ease;
}

.ring-fill--ok      { stroke: #10b981; }
.ring-fill--warning { stroke: #f59e0b; }
.ring-fill--danger  { stroke: #ef4444; }
.ring-fill--low     { stroke: #9aabb8; }

.ring-value {
  font-size: 20px;
  font-weight: 700;
  fill: var(--text-primary);
  font-family: inherit;
}

.ring-label {
  font-size: 9px;
  fill: #9aabb8;
  font-family: inherit;
}

.efficiency-breakdown {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.eff-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.eff-label {
  font-size: 0.75rem;
  color: #9aabb8;
  min-width: 52px;
}

.eff-bar-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.eff-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.eff-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.eff-pct {
  font-size: 0.72rem;
  font-family: monospace;
  color: var(--text-primary);
  min-width: 2.5rem;
  text-align: right;
}

/* ── Donut card ──────────────────────────────────────────────────────────── */
.donut-card .card-header { border-bottom: 1px solid var(--border-color); }

.donut-body {
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.donut-chart-wrap {
  flex-shrink: 0;
  width: 120px;
  height: 120px;
}

.donut-svg {
  width: 100%;
  height: 100%;
}

.donut-bg {
  fill: none;
  stroke: var(--border-color);
  stroke-width: 12;
}

.donut-used {
  fill: none;
  transition: stroke-dasharray 0.6s ease;
}

.donut-center-label {
  font-size: 9px;
  font-weight: 600;
  fill: var(--text-primary);
  font-family: inherit;
}

.donut-center-sub {
  font-size: 8px;
  fill: #9aabb8;
  font-family: inherit;
}

.donut-legend {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-dot--cpu { background: #6366f1; }
.legend-dot--mem { background: #10b981; }

.legend-text { color: var(--text-primary); }

.legend-sep {
  border-top: 1px solid var(--border-color);
  margin: 0.25rem 0;
}

/* ── VM Distribution mini pie ───────────────────────────────────────────── */
.vm-dist-card .card-header { border-bottom: 1px solid var(--border-color); }

.vm-dist-body {
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.vm-pie-svg {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
}

.pie-slice {
  fill: none;
  stroke-width: 28;
  transition: stroke-dasharray 0.6s ease;
}

.pie-slice--running { stroke: #10b981; }
.pie-slice--paused  { stroke: #f59e0b; }

.pie-center { fill: var(--bg-card, #1e1e2e); }

.pie-center-val {
  font-size: 13px;
  font-weight: 700;
  fill: var(--text-primary);
  font-family: inherit;
}

.pie-center-sub {
  font-size: 8px;
  fill: #9aabb8;
  font-family: inherit;
}

.vm-dist-legend {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.vd-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
}

.vd-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.vd-dot--running { background: #10b981; }
.vd-dot--stopped { background: #6b7280; }
.vd-dot--paused  { background: #f59e0b; }

.vd-label { color: #9aabb8; min-width: 52px; }
.vd-val   { font-weight: 600; color: var(--text-primary); margin-left: auto; }

.vd-sep {
  border-top: 1px solid var(--border-color);
  margin: 0.2rem 0;
}

/* ── Stat summary card ───────────────────────────────────────────────────── */
.stat-summary-card .card-header { border-bottom: 1px solid var(--border-color); }

.stat-summary-body {
  padding: 0.75rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.ss-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.ss-icon {
  font-size: 1.2rem;
  width: 28px;
  text-align: center;
  flex-shrink: 0;
}

.ss-value {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.ss-label {
  font-size: 0.7rem;
  color: #9aabb8;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.stat-green { color: #10b981; }

/* ── Node Distribution Map ───────────────────────────────────────────────── */
.section-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #9aabb8;
  margin-bottom: 0.5rem;
}

.node-distribution-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.75rem;
}

.node-dist-card {
  position: relative;
  background: var(--bg-card, #1e1e2e);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.875rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  cursor: default;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.node-dist-card:hover {
  border-color: var(--accent, #6366f1);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent, #6366f1) 15%, transparent);
}

.node-dist-card--warn {
  border-color: #f59e0b;
}

.imbalance-badge {
  position: absolute;
  top: 0.4rem;
  right: 0.5rem;
  font-size: 0.65rem;
  font-weight: 600;
  color: #f59e0b;
  background: color-mix(in srgb, #f59e0b 12%, transparent);
  border: 1px solid color-mix(in srgb, #f59e0b 35%, transparent);
  border-radius: 4px;
  padding: 0.1rem 0.35rem;
}

.nd-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.1rem;
}

.nd-name {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
  font-family: monospace;
}

.nd-host-label {
  font-size: 0.7rem;
  color: #9aabb8;
  margin-bottom: 0.25rem;
}

.nd-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.nd-status-dot--online  { background: #10b981; box-shadow: 0 0 4px #10b981; }
.nd-status-dot--offline { background: #ef4444; }

.nd-resource-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.3rem;
}
.nd-resource-label { font-size: 0.65rem; color: #9aabb8; min-width: 26px; }
.nd-resource-val   { font-size: 0.65rem; color: #c8d8e8; min-width: 28px; text-align: right; }
.nd-mini-bar {
  flex: 1;
  height: 4px;
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
  overflow: hidden;
}
.nd-mini-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }

.nd-counts {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.nd-count-pill {
  font-size: 0.7rem;
  font-weight: 500;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
}

.nd-count-pill--vm  { background: color-mix(in srgb, #6366f1 15%, transparent); color: #6366f1; }
.nd-count-pill--lxc { background: color-mix(in srgb, #10b981 15%, transparent); color: #10b981; }

.nd-bar-wrap {
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
}

.nd-bar {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
}

.nd-bar--ok   { background: #6366f1; }
.nd-bar--warn { background: #f59e0b; }

.nd-share-label { font-size: 0.68rem; color: #9aabb8; margin-top: 0.2rem; }

/* Node tooltip */
.nd-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-secondary, #2a2a3e);
  border: 1px solid var(--border-color);
  border-radius: 0.4rem;
  padding: 0.6rem 0.85rem;
  min-width: 180px;
  z-index: 100;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  pointer-events: none;
}

.ndt-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.4rem;
  padding-bottom: 0.3rem;
  border-bottom: 1px solid var(--border-color);
}

.ndt-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: #9aabb8;
  margin-bottom: 0.15rem;
}

.ndt-row strong { color: var(--text-primary); }

.ndt-warn {
  margin-top: 0.3rem;
  font-size: 0.72rem;
  color: #f59e0b;
  font-weight: 500;
}

/* ── Host grid ───────────────────────────────────────────────────────────── */
.host-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.host-card {
  display: flex;
  flex-direction: column;
}

.host-card-header {
  padding: 1rem 1.25rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.host-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.2rem;
}

.host-name {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.host-addr { margin-top: 0.1rem; }

.host-card-body {
  padding: 0.875rem 1.25rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.host-card-footer {
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
}

/* ── Resource bars ───────────────────────────────────────────────────────── */
.resource-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.resource-label {
  min-width: 130px;
  color: var(--text-primary);
  white-space: nowrap;
}

.mini-bar-wrap {
  flex: 1;
  height: 7px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.mini-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.35s ease;
}

.fill--ok      { background: #10b981; }
.fill--warning { background: #f59e0b; }
.fill--danger  { background: #ef4444; }

/* ── Host counts row ─────────────────────────────────────────────────────── */
.host-counts {
  display: flex;
  gap: 1rem;
  margin-top: 0.25rem;
}

.host-count-item {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.count-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.count-value {
  font-weight: 600;
  color: var(--text-primary);
}

.text-green { color: #10b981; }

/* ── Resource trends section ─────────────────────────────────────────────── */
.trend-time-selector {
  display: flex;
  gap: 0.25rem;
}

.trend-tf-btn {
  padding: 0.2rem 0.5rem;
  font-size: 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: transparent;
  color: #9aabb8;
  cursor: pointer;
  transition: all 0.15s;
}

.trend-tf-btn:hover,
.trend-tf-btn.active {
  background: var(--accent, #6366f1);
  border-color: var(--accent, #6366f1);
  color: #fff;
}

.trends-body {
  padding: 0.75rem 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.trend-section {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.trend-label {
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #9aabb8;
}

.sparkline-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.sparkline-svg {
  width: 100%;
  height: 60px;
  background: var(--bg-secondary, #2a2a3e);
  border-radius: 6px;
  overflow: visible;
}

.sparkline-line {
  stroke-width: 2;
  fill: none;
}

.sparkline-line--cpu { stroke: #6366f1; }
.sparkline-line--mem { stroke: #10b981; }

.sparkline-area { opacity: 0.6; }

.sparkline-stats {
  display: flex;
  gap: 1rem;
}

.sp-stat {
  font-size: 0.75rem;
  color: #9aabb8;
}

.sp-stat strong { color: var(--text-primary); }

/* ── Resource table ──────────────────────────────────────────────────────── */
.table-filters {
  flex-wrap: wrap;
}

.filter-select {
  padding: 0.3rem 0.5rem;
  font-size: 0.875rem;
  min-width: 110px;
}

.search-input {
  max-width: 200px;
  padding: 0.3rem 0.6rem;
  font-size: 0.875rem;
}

.group-toggle-label {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--text-primary);
  cursor: pointer;
  white-space: nowrap;
}

.sortable-th {
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.sortable-th:hover { color: var(--text-primary); }

.sort-active { color: var(--accent, #6366f1); }

.sort-icon {
  margin-left: 0.3rem;
  font-size: 0.7rem;
  opacity: 0.7;
}

.resource-row-link {
  cursor: pointer;
  transition: background 0.1s;
}

.resource-row-link:hover { background: var(--bg-secondary); }

.resource-row-indented td:first-child {
  padding-left: 2rem;
}

/* Node group header row */
.node-group-header td {
  background: var(--bg-secondary, #2a2a3e);
  padding: 0.5rem 0.875rem;
}

.node-group-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.node-group-icon {
  font-size: 0.9rem;
}

.node-group-count {
  margin-left: auto;
  font-size: 0.72rem;
  color: #9aabb8;
  font-weight: 400;
}

/* Row danger highlight */
.row-danger td {
  background: color-mix(in srgb, #ef4444 6%, transparent);
}

/* ── Type icon ───────────────────────────────────────────────────────────── */
.type-icon {
  margin-right: 0.3rem;
  font-size: 0.9rem;
}

/* ── Tag pills ───────────────────────────────────────────────────────────── */
.tags-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem;
}

.tag-pill {
  display: inline-block;
  padding: 0.1rem 0.45rem;
  font-size: 0.68rem;
  font-weight: 500;
  border-radius: 999px;
  white-space: nowrap;
  border: 1px solid transparent;
}

.tag-blue   { background: color-mix(in srgb,#6366f1 18%,transparent); color:#6366f1; border-color: color-mix(in srgb,#6366f1 35%,transparent); }
.tag-green  { background: color-mix(in srgb,#10b981 18%,transparent); color:#10b981; border-color: color-mix(in srgb,#10b981 35%,transparent); }
.tag-purple { background: color-mix(in srgb,#a855f7 18%,transparent); color:#a855f7; border-color: color-mix(in srgb,#a855f7 35%,transparent); }
.tag-orange { background: color-mix(in srgb,#f97316 18%,transparent); color:#f97316; border-color: color-mix(in srgb,#f97316 35%,transparent); }
.tag-teal   { background: color-mix(in srgb,#06b6d4 18%,transparent); color:#06b6d4; border-color: color-mix(in srgb,#06b6d4 35%,transparent); }
.tag-pink   { background: color-mix(in srgb,#ec4899 18%,transparent); color:#ec4899; border-color: color-mix(in srgb,#ec4899 35%,transparent); }

/* ── Uptime badge ────────────────────────────────────────────────────────── */
.uptime-badge {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  font-size: 0.72rem;
  font-family: monospace;
  background: color-mix(in srgb, #10b981 12%, transparent);
  color: #10b981;
  border: 1px solid color-mix(in srgb, #10b981 28%, transparent);
  border-radius: 4px;
  white-space: nowrap;
}

/* ── Top VMs table ───────────────────────────────────────────────────────── */
.top-vms-refresh-label {
  font-size: 0.75rem;
  color: #9aabb8;
  margin-right: 0.5rem;
}

.top-vm-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 100px;
}

.top-vm-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.top-vm-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.35s ease;
}

.top-vm-bar-label {
  font-size: 0.72rem;
  font-family: monospace;
  color: var(--text-primary);
  white-space: nowrap;
  min-width: 2.5rem;
  text-align: right;
}

/* ── Collapsible card header ─────────────────────────────────────────────── */
.collapsible-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.collapsible-header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.collapse-chevron {
  font-size: 0.75rem;
  color: #9aabb8;
  transition: transform 0.2s ease;
  display: inline-block;
  transform: rotate(-90deg);
}

.collapse-chevron.chevron-open { transform: rotate(0deg); }

/* ── Network overview ────────────────────────────────────────────────────── */
.network-overview-body {
  padding: 0.75rem 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.network-host-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.network-host-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-primary);
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--border-color);
}

.network-node-group {
  padding-left: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.network-node-title {
  color: #9aabb8;
  margin-bottom: 0.25rem;
}

.network-iface-group { margin-top: 0.25rem; }

.network-iface-group-label {
  margin-bottom: 0.3rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.network-table { font-size: 0.85rem; }

.iface-name {
  font-weight: 600;
  font-family: monospace;
  color: var(--text-primary);
}

.font-mono { font-family: monospace; }

/* ── Storage overview ────────────────────────────────────────────────────── */
.storage-overview-body {
  padding: 0.75rem 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.storage-host-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.storage-host-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-primary);
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--border-color);
}

.storage-node-group {
  padding-left: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.storage-node-title {
  color: #9aabb8;
  margin-bottom: 0.25rem;
}

.storage-table { font-size: 0.85rem; }

.storage-name {
  font-weight: 600;
  font-family: monospace;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.storage-type-icon { font-size: 0.85rem; }

.storage-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 120px;
}

.storage-bar {
  flex: 1;
  height: 7px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.storage-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.35s ease;
}

.storage-bar-label {
  font-size: 0.72rem;
  font-family: monospace;
  color: var(--text-primary);
  white-space: nowrap;
  min-width: 2.75rem;
  text-align: right;
}

.content-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem;
}

.content-pill {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  font-size: 0.68rem;
  border-radius: 4px;
  background: var(--bg-secondary, #2a2a3e);
  color: #9aabb8;
  white-space: nowrap;
}

.cp-images  { background: color-mix(in srgb,#6366f1 14%,transparent); color:#6366f1; }
.cp-backup  { background: color-mix(in srgb,#10b981 14%,transparent); color:#10b981; }
.cp-iso     { background: color-mix(in srgb,#f97316 14%,transparent); color:#f97316; }
.cp-rootdir { background: color-mix(in srgb,#a855f7 14%,transparent); color:#a855f7; }
.cp-vztmpl  { background: color-mix(in srgb,#06b6d4 14%,transparent); color:#06b6d4; }
.cp-snippets{ background: color-mix(in srgb,#ec4899 14%,transparent); color:#ec4899; }

/* ── Utilities ───────────────────────────────────────────────────────────── */
.mb-1  { margin-bottom: 0.5rem; }
.mb-2  { margin-bottom: 1rem; }
.p-3   { padding: 1.5rem; }
.pl-2  { padding-left: 0.5rem; }
.text-xs  { font-size: 0.75rem; }
.text-sm  { font-size: 0.875rem; }
.text-muted   { color: #9aabb8; }
.text-center  { text-align: center; }
.flex         { display: flex; }
.gap-1        { gap: 0.5rem; }
.align-center { align-items: center; }
.flex-wrap    { flex-wrap: wrap; }

.card-body { padding: 1.25rem 1.5rem; }

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 900px) {
  .resource-overview-grid {
    grid-template-columns: 1fr 1fr;
  }

  .host-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 600px) {
  .resource-overview-grid {
    grid-template-columns: 1fr;
  }

  .table-filters {
    flex-direction: column;
    align-items: flex-start;
  }

  .filter-select,
  .search-input {
    width: 100%;
    max-width: none;
  }

  .node-distribution-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
