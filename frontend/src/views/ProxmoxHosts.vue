<template>
  <div class="proxmox-hosts-page">
    <!-- Page Header -->
    <div class="page-header mb-2">
      <div class="page-header-row">
        <div>
          <h2>Proxmox Datacenters and Hosts</h2>
          <p class="text-muted">Manage your Proxmox clusters and hypervisor nodes</p>
        </div>
        <div class="flex gap-1 align-center">
          <router-link to="/federation" class="btn btn-outline">
            🌍 Federation View
          </router-link>
        </div>
      </div>
    </div>

    <!-- Datacenters Section -->
    <div class="card mb-2">
      <div class="card-header">
        <h3>Datacenters</h3>
        <div class="flex gap-1 align-center">
          <button
            v-if="hosts.length > 1"
            @click="testAllConnections"
            class="btn btn-outline btn-sm"
            :disabled="testingAll">
            {{ testingAll ? 'Testing...' : 'Test All' }}
          </button>
          <button @click="showAddModal = true" class="btn btn-primary">+ Add Datacenter</button>
        </div>
      </div>

      <div v-if="loading" class="loading-spinner"></div>

      <div v-else-if="hosts.length === 0" class="text-center text-muted" style="padding: 2rem;">
        <p>No Proxmox datacenters configured yet.</p>
        <p class="text-sm">Add a datacenter to start deploying VMs.</p>
      </div>

      <!-- Card view -->
      <div v-else class="host-cards-grid">
        <div
          v-for="host in hosts"
          :key="host.id"
          class="host-card"
          :class="hostCardClass(host)">

          <!-- Card header: status pulse + name -->
          <div class="host-card__header">
            <div class="flex align-center gap-1">
              <span class="status-pulse" :class="hostPulseClass(host)"></span>
              <h4 class="host-card__name">{{ host.name }}</h4>
            </div>
            <span :class="['badge', host.is_active ? 'badge-success' : 'badge-danger']">
              {{ host.is_active ? 'Active' : 'Inactive' }}
            </span>
          </div>

          <!-- Hostname row -->
          <div class="host-card__hostname text-sm text-muted">
            <code>{{ host.hostname }}:{{ host.port }}</code>
          </div>

          <!-- Cluster info row -->
          <div v-if="getFedSummary(host.id)" class="host-card__cluster-info">
            <div class="cluster-info-row">
              <span class="ci-label">Cluster</span>
              <span class="ci-value">{{ getFedSummary(host.id).cluster_name || '—' }}</span>
            </div>
            <div class="cluster-info-row">
              <span class="ci-label">Nodes</span>
              <span class="ci-value">{{ getFedSummary(host.id).node_count }}</span>
            </div>
            <div class="cluster-info-row">
              <span class="ci-label">VMs / LXC</span>
              <span class="ci-value">
                <span class="badge badge-info">{{ getFedSummary(host.id).vm_count }} VMs</span>
                <span class="badge badge-secondary ml-1">{{ getFedSummary(host.id).lxc_count }} LXC</span>
              </span>
            </div>
          </div>

          <!-- Resource summary bars -->
          <div v-if="getHostResourceSummary(host.id)" class="host-card__resources">
            <div class="res-bar-row">
              <span class="res-label">CPU</span>
              <div class="res-bar-wrap">
                <div class="res-bar">
                  <div
                    class="res-bar-fill"
                    :class="pctBarClass(getHostResourceSummary(host.id).cpuPct)"
                    :style="{ width: getHostResourceSummary(host.id).cpuPct + '%' }">
                  </div>
                </div>
                <span class="res-bar-label">{{ getHostResourceSummary(host.id).cpuPct }}%</span>
              </div>
            </div>
            <div class="res-bar-row">
              <span class="res-label">RAM</span>
              <div class="res-bar-wrap">
                <div class="res-bar">
                  <div
                    class="res-bar-fill"
                    :class="pctBarClass(getHostResourceSummary(host.id).ramPct)"
                    :style="{ width: getHostResourceSummary(host.id).ramPct + '%' }">
                  </div>
                </div>
                <span class="res-bar-label">{{ getHostResourceSummary(host.id).ramPct }}% ({{ getHostResourceSummary(host.id).ramUsedGB }}GB / {{ getHostResourceSummary(host.id).ramTotalGB }}GB)</span>
              </div>
            </div>
            <div class="res-bar-row">
              <span class="res-label">Disk</span>
              <div class="res-bar-wrap">
                <div class="res-bar">
                  <div
                    class="res-bar-fill"
                    :class="pctBarClass(getHostResourceSummary(host.id).diskPct)"
                    :style="{ width: getHostResourceSummary(host.id).diskPct + '%' }">
                  </div>
                </div>
                <span class="res-bar-label">{{ getHostResourceSummary(host.id).diskPct }}% ({{ getHostResourceSummary(host.id).diskUsedTB }} / {{ getHostResourceSummary(host.id).diskTotalTB }})</span>
              </div>
            </div>
          </div>

          <!-- Latency + health -->
          <div class="host-card__meta flex align-center gap-1 mt-1">
            <template v-if="getFedSummary(host.id)">
              <span :class="latencyBadgeClass(getFedSummary(host.id).latency_ms)" class="badge">
                {{ getFedSummary(host.id).latency_ms != null ? getFedSummary(host.id).latency_ms + 'ms' : '—' }}
              </span>
            </template>
            <template v-if="testResults[host.id]">
              <span :class="['badge', testResults[host.id].ok ? 'badge-success' : 'badge-danger']">
                {{ testResults[host.id].ok ? 'Reachable' : 'Unreachable' }}
              </span>
            </template>
            <span v-if="host.idrac_type" class="badge badge-info">{{ host.idrac_type.toUpperCase() }}</span>
            <span v-if="host.last_poll" class="text-xs text-muted ml-auto">{{ formatDate(host.last_poll) }}</span>
          </div>

          <!-- iDRAC row -->
          <div v-if="host.idrac_hostname" class="text-sm text-muted mt-1">
            BMC: {{ host.idrac_hostname }}
          </div>

          <!-- Action buttons -->
          <div class="host-card__actions flex gap-1 mt-1">
            <router-link
              :to="`/proxmox/${host.id}/cluster`"
              class="btn btn-primary btn-sm flex-1 text-center">
              Open Cluster
            </router-link>
            <button @click="openDetailDrawer(host)" class="btn btn-outline btn-sm" title="View Details">Details</button>
            <button @click="testConnection(host.id)" class="btn btn-outline btn-sm" :disabled="testing[host.id]" title="Test Connection">
              {{ testing[host.id] ? '...' : 'Test' }}
            </button>
            <button @click="pollHost(host.id)" class="btn btn-outline btn-sm" title="Force poll">Poll</button>
            <button @click="openEdit(host)" class="btn btn-outline btn-sm" title="Edit">Edit</button>
            <button @click="deleteHost(host.id)" class="btn btn-danger btn-sm" title="Delete">Del</button>
          </div>
        </div>
      </div>

      <!-- Test-All Results Table -->
      <div v-if="testAllResults.length > 0" class="test-all-results">
        <h5 class="test-all-title">Connection Test Results</h5>
        <table class="table">
          <thead>
            <tr>
              <th>Datacenter</th>
              <th>Hostname</th>
              <th>Status</th>
              <th>Latency</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in testAllResults" :key="r.id">
              <td>{{ r.name }}</td>
              <td class="text-sm"><code>{{ r.hostname }}</code></td>
              <td>
                <span :class="['badge', r.ok ? 'badge-success' : 'badge-danger']">
                  {{ r.ok ? 'Online' : 'Offline' }}
                </span>
              </td>
              <td class="text-sm">{{ r.latency != null ? r.latency + 'ms' : '—' }}</td>
              <td class="text-sm text-muted">{{ r.message || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Cluster Nodes Section -->
    <div class="card">
      <div class="card-header">
        <h3>Cluster Nodes</h3>
        <button @click="handleRefreshAll" class="btn btn-outline">
          <span v-if="!loadingNodes">Refresh All</span>
          <span v-else>Loading...</span>
        </button>
      </div>

      <div v-if="loadingNodes" class="loading-spinner"></div>

      <div v-else-if="allNodes.length === 0" class="text-center text-muted" style="padding: 2rem;">
        <p>No cluster nodes found.</p>
        <p class="text-sm">Poll your datacenters to discover nodes.</p>
      </div>

      <div v-else class="nodes-section">
        <div v-for="datacenter in datacentersWithNodes" :key="datacenter.id" class="datacenter-section">
          <h4 class="datacenter-title">{{ datacenter.name }}</h4>

          <div v-if="datacenter.nodes.length === 0" class="text-muted text-sm" style="padding: 0.5rem 0;">
            No nodes discovered yet. Click "Poll" to discover nodes.
          </div>

          <div v-else class="nodes-grid">
            <div v-for="node in datacenter.nodes" :key="node.id" class="node-card">
              <div class="node-header">
                <h5>
                  <router-link :to="`/proxmox/${datacenter.id}/nodes/${node.node_name}`" class="node-link">
                    {{ node.node_name }}
                  </router-link>
                </h5>
                <span :class="['badge', node.status === 'online' ? 'badge-success' : 'badge-danger']">
                  {{ node.status || 'unknown' }}
                </span>
              </div>
              <div class="node-stats">
                <div class="stat">
                  <span class="stat-label">CPU:</span>
                  <span class="stat-value">{{ node.cpu_cores }} cores ({{ node.cpu_usage }}%)</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Memory:</span>
                  <span class="stat-value">{{ formatBytes(node.memory_used) }} / {{ formatBytes(node.memory_total) }}</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Disk:</span>
                  <span class="stat-value">{{ formatBytes(node.disk_used) }} / {{ formatBytes(node.disk_total) }}</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Uptime:</span>
                  <span class="stat-value">{{ formatUptime(node.uptime) }}</span>
                </div>
              </div>

              <!-- Live Stats -->
              <div class="node-live-stats">
                <div class="live-stats-divider"></div>

                <!-- CPU usage bar -->
                <div class="live-stat-row">
                  <span class="live-stat-label">Live CPU</span>
                  <template v-if="getNodeStat(datacenter.id, node.node_name)">
                    <div class="stat-bar-wrap">
                      <div class="stat-bar">
                        <div
                          class="stat-bar-fill"
                          :class="cpuBarClass(getNodeStat(datacenter.id, node.node_name).cpu)"
                          :style="{ width: cpuPct(getNodeStat(datacenter.id, node.node_name).cpu) + '%' }"
                        ></div>
                      </div>
                      <span class="stat-bar-label">{{ cpuPct(getNodeStat(datacenter.id, node.node_name).cpu) }}%</span>
                    </div>
                  </template>
                  <span v-else class="stat-skeleton">—</span>
                </div>

                <!-- RAM usage bar -->
                <div class="live-stat-row">
                  <span class="live-stat-label">Live RAM</span>
                  <template v-if="getNodeStat(datacenter.id, node.node_name)">
                    <div class="stat-bar-wrap">
                      <div class="stat-bar">
                        <div
                          class="stat-bar-fill"
                          :class="ramBarClass(getNodeStat(datacenter.id, node.node_name).memory)"
                          :style="{ width: ramPct(getNodeStat(datacenter.id, node.node_name).memory) + '%' }"
                        ></div>
                      </div>
                      <span class="stat-bar-label">
                        {{ ramPct(getNodeStat(datacenter.id, node.node_name).memory) }}%
                        ({{ formatGB(getNodeStat(datacenter.id, node.node_name).memory?.used) }} /
                        {{ formatGB(getNodeStat(datacenter.id, node.node_name).memory?.total) }} GB)
                      </span>
                    </div>
                  </template>
                  <span v-else class="stat-skeleton">—</span>
                </div>

                <!-- Disk usage bar -->
                <div class="live-stat-row">
                  <span class="live-stat-label">Live Disk</span>
                  <template v-if="getNodeStat(datacenter.id, node.node_name)">
                    <div class="stat-bar-wrap">
                      <div class="stat-bar">
                        <div
                          class="stat-bar-fill"
                          :class="diskBarClass(getNodeStat(datacenter.id, node.node_name).rootfs)"
                          :style="{ width: diskPct(getNodeStat(datacenter.id, node.node_name).rootfs) + '%' }"
                        ></div>
                      </div>
                      <span class="stat-bar-label">
                        {{ diskPct(getNodeStat(datacenter.id, node.node_name).rootfs) }}%
                        ({{ formatGB(getNodeStat(datacenter.id, node.node_name).rootfs?.used) }} /
                        {{ formatGB(getNodeStat(datacenter.id, node.node_name).rootfs?.total) }} GB)
                      </span>
                    </div>
                  </template>
                  <span v-else class="stat-skeleton">—</span>
                </div>

                <!-- Uptime -->
                <div class="live-stat-row">
                  <span class="live-stat-label">Uptime</span>
                  <template v-if="getNodeStat(datacenter.id, node.node_name)">
                    <span class="stat-value text-sm">{{ formatUptime(getNodeStat(datacenter.id, node.node_name).uptime) }}</span>
                  </template>
                  <span v-else class="stat-skeleton">—</span>
                </div>

                <!-- VM / LXC count badges -->
                <div class="live-stat-row">
                  <span class="live-stat-label">Guests</span>
                  <template v-if="getNodeStat(datacenter.id, node.node_name)">
                    <div class="guest-badges">
                      <span class="badge badge-info">{{ getNodeStat(datacenter.id, node.node_name).vmCount }} VMs</span>
                      <span class="badge badge-secondary">{{ getNodeStat(datacenter.id, node.node_name).lxcCount }} LXC</span>
                    </div>
                  </template>
                  <span v-else class="stat-skeleton">—</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Host Detail Side Drawer ── -->
    <transition name="drawer-slide">
      <div v-if="showDetailDrawer" class="drawer-backdrop" @click.self="closeDetailDrawer">
        <div class="detail-drawer">
          <div class="drawer-header">
            <div class="drawer-title-row">
              <div>
                <h3 class="drawer-title">{{ drawerHost && drawerHost.name }}</h3>
                <div class="drawer-subtitle text-sm text-muted">
                  <code>{{ drawerHost && drawerHost.hostname }}:{{ drawerHost && drawerHost.port }}</code>
                </div>
              </div>
              <button class="btn-close" @click="closeDetailDrawer">&#215;</button>
            </div>
            <!-- Quick action buttons -->
            <div class="drawer-quick-actions flex gap-1 mt-1">
              <router-link
                v-if="drawerHost"
                :to="`/proxmox/${drawerHost.id}/cluster`"
                class="btn btn-primary btn-sm"
                @click="closeDetailDrawer">
                Open Cluster Overview
              </router-link>
              <router-link
                v-if="drawerHost"
                :to="`/proxmox/${drawerHost.id}/cluster`"
                class="btn btn-outline btn-sm"
                @click="closeDetailDrawer">
                View VMs
              </router-link>
              <button
                v-if="drawerHost"
                class="btn btn-outline btn-sm"
                :disabled="testing[drawerHost.id]"
                @click="testConnection(drawerHost.id)">
                {{ testing[drawerHost.id] ? 'Testing...' : 'Test Connection' }}
              </button>
            </div>
          </div>

          <div class="drawer-body">
            <!-- Federation / Cluster info -->
            <div v-if="drawerHost && getFedSummary(drawerHost.id)" class="drawer-section">
              <div class="drawer-section-title">Cluster Info</div>
              <div class="drawer-info-grid">
                <div class="di-row">
                  <span class="di-label">Cluster</span>
                  <span class="di-value">{{ getFedSummary(drawerHost.id).cluster_name || 'Standalone' }}</span>
                </div>
                <div class="di-row">
                  <span class="di-label">API URL</span>
                  <span class="di-value font-mono text-sm">{{ getFedSummary(drawerHost.id).api_url || `https://${drawerHost.hostname}:${drawerHost.port}` }}</span>
                </div>
                <div class="di-row">
                  <span class="di-label">Status</span>
                  <span :class="['badge', getFedSummary(drawerHost.id).status === 'online' ? 'badge-success' : 'badge-danger']">
                    {{ getFedSummary(drawerHost.id).status || 'unknown' }}
                  </span>
                </div>
                <div class="di-row">
                  <span class="di-label">Health</span>
                  <span :class="['badge', getFedSummary(drawerHost.id).cluster_health === 'healthy' ? 'badge-success' : getFedSummary(drawerHost.id).cluster_health === 'degraded' ? 'badge-warning' : 'badge-secondary']">
                    {{ getFedSummary(drawerHost.id).cluster_health || 'unknown' }}
                  </span>
                </div>
                <div class="di-row">
                  <span class="di-label">Latency</span>
                  <span :class="['badge', latencyBadgeClass(getFedSummary(drawerHost.id).latency_ms)]">
                    {{ getFedSummary(drawerHost.id).latency_ms != null ? getFedSummary(drawerHost.id).latency_ms + 'ms' : '—' }}
                  </span>
                </div>
                <div class="di-row">
                  <span class="di-label">VMs / LXC</span>
                  <span class="di-value">
                    <span class="badge badge-info">{{ getFedSummary(drawerHost.id).vm_count }} VMs</span>
                    <span class="badge badge-secondary ml-1">{{ getFedSummary(drawerHost.id).lxc_count }} LXC</span>
                  </span>
                </div>
              </div>
            </div>

            <!-- Live Node Metrics -->
            <div class="drawer-section">
              <div class="drawer-section-title">
                Live Node Metrics
                <span v-if="drawerLoadingNodes" class="text-muted text-xs"> Loading…</span>
              </div>

              <div v-if="drawerNodes.length === 0 && !drawerLoadingNodes" class="text-muted text-sm">
                No nodes discovered.
              </div>

              <div
                v-for="node in drawerNodes"
                :key="node.node_name"
                class="drawer-node-card"
              >
                <div class="dnc-header">
                  <span class="dnc-name">{{ node.node_name }}</span>
                  <span :class="['badge', node.status === 'online' ? 'badge-success' : 'badge-danger']">
                    {{ node.status || 'unknown' }}
                  </span>
                </div>

                <template v-if="drawerHost && getNodeStat(drawerHost.id, node.node_name)">
                  <div class="dnc-bars">
                    <div class="dnc-bar-row">
                      <span class="dnc-bar-label">CPU</span>
                      <div class="dnc-bar-wrap">
                        <div class="dnc-bar">
                          <div
                            class="dnc-bar-fill"
                            :class="cpuBarClass(getNodeStat(drawerHost.id, node.node_name).cpu)"
                            :style="{ width: cpuPct(getNodeStat(drawerHost.id, node.node_name).cpu) + '%' }"
                          ></div>
                        </div>
                        <span class="dnc-bar-pct">{{ cpuPct(getNodeStat(drawerHost.id, node.node_name).cpu) }}%</span>
                      </div>
                    </div>
                    <div class="dnc-bar-row">
                      <span class="dnc-bar-label">RAM</span>
                      <div class="dnc-bar-wrap">
                        <div class="dnc-bar">
                          <div
                            class="dnc-bar-fill"
                            :class="ramBarClass(getNodeStat(drawerHost.id, node.node_name).memory)"
                            :style="{ width: ramPct(getNodeStat(drawerHost.id, node.node_name).memory) + '%' }"
                          ></div>
                        </div>
                        <span class="dnc-bar-pct">
                          {{ ramPct(getNodeStat(drawerHost.id, node.node_name).memory) }}%
                          <span class="text-muted text-xs">({{ formatGB(getNodeStat(drawerHost.id, node.node_name).memory?.used) }}/{{ formatGB(getNodeStat(drawerHost.id, node.node_name).memory?.total) }} GB)</span>
                        </span>
                      </div>
                    </div>
                    <div class="dnc-bar-row">
                      <span class="dnc-bar-label">Disk</span>
                      <div class="dnc-bar-wrap">
                        <div class="dnc-bar">
                          <div
                            class="dnc-bar-fill"
                            :class="diskBarClass(getNodeStat(drawerHost.id, node.node_name).rootfs)"
                            :style="{ width: diskPct(getNodeStat(drawerHost.id, node.node_name).rootfs) + '%' }"
                          ></div>
                        </div>
                        <span class="dnc-bar-pct">
                          {{ diskPct(getNodeStat(drawerHost.id, node.node_name).rootfs) }}%
                          <span class="text-muted text-xs">({{ formatGB(getNodeStat(drawerHost.id, node.node_name).rootfs?.used) }}/{{ formatGB(getNodeStat(drawerHost.id, node.node_name).rootfs?.total) }} GB)</span>
                        </span>
                      </div>
                    </div>
                  </div>
                  <div class="dnc-meta text-xs text-muted">
                    Uptime: {{ formatUptime(getNodeStat(drawerHost.id, node.node_name).uptime) }} &nbsp;|&nbsp;
                    {{ getNodeStat(drawerHost.id, node.node_name).vmCount }} VMs &nbsp;|&nbsp;
                    {{ getNodeStat(drawerHost.id, node.node_name).lxcCount }} LXC
                  </div>
                </template>
                <div v-else-if="drawerLoadingNodes" class="text-muted text-xs">Loading stats…</div>
                <div v-else class="text-muted text-xs">No live data available</div>
              </div>
            </div>

            <!-- Recent Tasks -->
            <div class="drawer-section">
              <div class="drawer-section-title">
                Recent Tasks
                <span v-if="drawerTasksLoading" class="text-muted text-xs"> Loading…</span>
              </div>

              <div v-if="!drawerTasksLoading && drawerTasks.length === 0" class="text-muted text-sm">
                No recent tasks found.
              </div>

              <div v-else class="drawer-tasks-list">
                <div
                  v-for="task in drawerTasks"
                  :key="task.upid"
                  class="drawer-task-item"
                >
                  <div class="dt-row">
                    <span
                      :class="['dt-status-dot', task.status === 'OK' || task.status === 'ok' ? 'dot-ok' : task.status === 'running' ? 'dot-running' : 'dot-error']"
                    ></span>
                    <span class="dt-type">{{ task.type || task.upid?.split(':')[5] || '—' }}</span>
                    <span class="dt-id text-muted text-xs">{{ task.id || '' }}</span>
                  </div>
                  <div class="dt-meta text-xs text-muted">
                    Node: {{ task.node }} &nbsp;|&nbsp; {{ task.user || '—' }}
                    <span v-if="task.endtime"> &nbsp;|&nbsp; {{ formatTaskTime(task.endtime) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- Edit Host Modal -->
    <div v-if="showEditModal" class="modal" @click="showEditModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Edit Host — {{ editHost.name }}</h3>
          <button @click="showEditModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="saveEdit" class="modal-body">

          <!-- Basic Settings -->
          <div class="edit-section">
            <h5 class="section-subtitle">Basic Settings</h5>
            <div class="form-group">
              <label class="form-label">Name</label>
              <input v-model="editHost.name" class="form-control" required />
            </div>
            <div class="form-row-2">
              <div class="form-group">
                <label class="form-label">Hostname / IP</label>
                <input v-model="editHost.hostname" class="form-control" required />
              </div>
              <div class="form-group">
                <label class="form-label">Port</label>
                <input v-model.number="editHost.port" type="number" class="form-control" />
              </div>
            </div>
            <div class="form-inline-row">
              <label class="form-label inline-check">
                <input v-model="editHost.is_active" type="checkbox" />
                Active
              </label>
              <label class="form-label inline-check">
                <input v-model="editHost.verify_ssl" type="checkbox" />
                Verify SSL Certificate
              </label>
            </div>
          </div>

          <!-- Authentication -->
          <div class="edit-section">
            <h5 class="section-subtitle">Authentication</h5>
            <div class="form-group">
              <label class="form-label">Auth Method</label>
              <select v-model="editAuthMethod" class="form-control">
                <option value="token">API Token (recommended)</option>
                <option value="password">Username / Password</option>
              </select>
            </div>
            <template v-if="editAuthMethod === 'token'">
              <div class="form-group">
                <label class="form-label">API Token ID</label>
                <input v-model="editHost.token_id" class="form-control" placeholder="e.g. root@pam!mytoken" autocomplete="off" />
              </div>
              <div class="form-group">
                <label class="form-label">API Token Secret <span class="text-muted text-sm">(leave blank to keep current)</span></label>
                <input v-model="editHost.token_secret" type="password" class="form-control" autocomplete="new-password" />
              </div>
              <div class="info-box text-sm">
                <strong>Token format:</strong> Create via PVE &rarr; Datacenter &rarr; Permissions &rarr; API Tokens.
                Token ID format: <code>user@realm!tokenname</code>
              </div>
            </template>
            <template v-else>
              <div class="form-group">
                <label class="form-label">Username</label>
                <input v-model="editHost.username" class="form-control" placeholder="root@pam" autocomplete="off" />
              </div>
              <div class="form-group">
                <label class="form-label">Password <span class="text-muted text-sm">(leave blank to keep current)</span></label>
                <input v-model="editHost.password" type="password" class="form-control" autocomplete="new-password" />
              </div>
            </template>
          </div>

          <!-- Defaults -->
          <div class="edit-section">
            <h5 class="section-subtitle">Deployment Defaults</h5>
            <div class="form-row-2">
              <div class="form-group">
                <label class="form-label">Default Storage</label>
                <input v-model="editHost.default_storage" class="form-control" placeholder="e.g. local-lvm" />
              </div>
              <div class="form-group">
                <label class="form-label">Default Bridge</label>
                <input v-model="editHost.default_bridge" class="form-control" placeholder="e.g. vmbr0" />
              </div>
            </div>
            <div class="form-row-2">
              <div class="form-group">
                <label class="form-label">Default Node</label>
                <input v-model="editHost.default_node" class="form-control" placeholder="e.g. pve" />
              </div>
              <div class="form-group">
                <label class="form-label">ISO Storage</label>
                <input v-model="editHost.iso_storage" class="form-control" placeholder="e.g. local" />
              </div>
            </div>
          </div>

          <!-- iDRAC / iLO -->
          <div class="edit-section">
            <h5 class="section-subtitle">iDRAC / iLO</h5>
            <div class="form-group">
              <label class="form-label">BMC Type</label>
              <select v-model="editHost.idrac_type" class="form-control">
                <option value="">None</option>
                <option value="idrac">Dell iDRAC</option>
                <option value="ilo">HPE iLO</option>
              </select>
            </div>
            <div v-if="editHost.idrac_type">
              <div class="form-row-2">
                <div class="form-group">
                  <label class="form-label">BMC Hostname / IP</label>
                  <input v-model="editHost.idrac_hostname" class="form-control" placeholder="192.168.1.10" />
                </div>
                <div class="form-group">
                  <label class="form-label">BMC Port</label>
                  <input v-model.number="editHost.idrac_port" type="number" class="form-control" placeholder="443" />
                </div>
              </div>
              <div class="form-row-2">
                <div class="form-group">
                  <label class="form-label">BMC Username</label>
                  <input v-model="editHost.idrac_username" class="form-control" placeholder="root or administrator" />
                </div>
                <div class="form-group">
                  <label class="form-label">BMC Password <span class="text-muted text-sm">(leave blank to keep)</span></label>
                  <input v-model="editHost.idrac_password" type="password" autocomplete="new-password" class="form-control" />
                </div>
              </div>
            </div>
          </div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? 'Saving...' : 'Save Changes' }}
            </button>
            <button type="button" @click="showEditModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Add Host Wizard -->
    <AddHostWizard v-model="showAddModal" @host-added="onHostAdded" />
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import AddHostWizard from '@/components/AddHostWizard.vue'

export default {
  name: 'ProxmoxHosts',
  components: { AddHostWizard },
  setup() {
    const toast = useToast()
    const router = useRouter()
    const hosts = ref([])
    const allNodes = ref([])
    const loading = ref(false)
    const loadingNodes = ref(false)
    const saving = ref(false)
    const showAddModal = ref(false)
    const showEditModal = ref(false)
    const useApiToken = ref(false)
    const editAuthMethod = ref('token')

    // Per-host test loading
    const testing = ref({})
    // Per-host test results (simple ok/latency)
    const testResults = ref({})

    // Test-all state
    const testingAll = ref(false)
    const testAllResults = ref([])

    // Federation summary keyed by host_id
    const federationSummary = ref({})

    // Live stats keyed by "${hostId}-${nodeName}"
    const nodeStats = ref({})

    // Host resource summaries (aggregated from node stats) keyed by hostId
    const hostResourceSummary = ref({})

    const editHost = ref({
      id: null, name: '', hostname: '', port: 8006,
      is_active: true, verify_ssl: false,
      token_id: '', token_secret: '',
      username: '', password: '',
      default_storage: '', default_bridge: '', default_node: '', iso_storage: '',
      idrac_type: '', idrac_hostname: '', idrac_port: 443,
      idrac_username: '', idrac_password: '',
    })

    // ── Detail Drawer state ────────────────────────────────────────────────
    const showDetailDrawer = ref(false)
    const drawerHost = ref(null)
    const drawerNodes = ref([])
    const drawerTasks = ref([])
    const drawerLoadingNodes = ref(false)
    const drawerTasksLoading = ref(false)

    const openDetailDrawer = async (host) => {
      drawerHost.value = host
      showDetailDrawer.value = true
      drawerNodes.value = []
      drawerTasks.value = []

      // Load nodes
      drawerLoadingNodes.value = true
      try {
        const res = await api.proxmox.listNodes(host.id)
        drawerNodes.value = res.data || []

        // Load live stats for each drawer node
        const tasks = drawerNodes.value.map(node => {
          const key = `${host.id}-${node.node_name}`
          if (nodeStats.value[key]) return Promise.resolve()
          return Promise.allSettled([
            api.pveNode.nodeStatus(host.id, node.node_name),
            api.pveNode.nodeVms(host.id, node.node_name),
            api.pveNode.containers(host.id, node.node_name),
          ]).then(([statusRes, vmsRes, lxcRes]) => {
            const status = statusRes.status === 'fulfilled' ? statusRes.value.data : null
            const vms = vmsRes.status === 'fulfilled' ? vmsRes.value.data : []
            const lxcs = lxcRes.status === 'fulfilled' ? lxcRes.value.data : []
            nodeStats.value = {
              ...nodeStats.value,
              [key]: {
                cpu: status?.cpu ?? null,
                memory: status?.memory ?? null,
                rootfs: status?.rootfs ?? null,
                uptime: status?.uptime ?? null,
                vmCount: Array.isArray(vms) ? vms.filter(v => v.type === 'qemu' || !v.type).length : 0,
                lxcCount: Array.isArray(lxcs) ? lxcs.length : 0,
              }
            }
          }).catch(() => {})
        })
        await Promise.allSettled(tasks)
      } catch {
        // ignore
      } finally {
        drawerLoadingNodes.value = false
      }

      // Load recent tasks
      drawerTasksLoading.value = true
      try {
        const nodeList = drawerNodes.value.slice(0, 3)
        const allTasks = []
        for (const node of nodeList) {
          try {
            const res = await api.pveNode.listTasks(host.id, node.node_name, { limit: 5 })
            const tasks = res.data || []
            for (const t of tasks) {
              allTasks.push({ ...t, node: node.node_name })
            }
          } catch { /* ignore */ }
        }
        allTasks.sort((a, b) => (b.starttime || 0) - (a.starttime || 0))
        drawerTasks.value = allTasks.slice(0, 5)
      } catch {
        // ignore
      } finally {
        drawerTasksLoading.value = false
      }
    }

    const closeDetailDrawer = () => {
      showDetailDrawer.value = false
      drawerHost.value = null
    }

    const formatTaskTime = (ts) => {
      if (!ts) return '—'
      return new Date(ts * 1000).toLocaleString()
    }
    // ─────────────────────────────────────────────────────────────────────

    const fetchHosts = async () => {
      loading.value = true
      try {
        const response = await api.proxmox.listHosts()
        hosts.value = response.data
      } catch (error) {
        console.error('Failed to fetch hosts:', error)
      } finally {
        loading.value = false
      }
    }

    const fetchFederationSummary = async () => {
      try {
        const response = await api.proxmox.getFederationSummary()
        const map = {}
        for (const h of (response.data.hosts || [])) {
          map[h.host_id] = h
        }
        federationSummary.value = map
      } catch (error) {
        console.error('Failed to fetch federation summary:', error)
      }
    }

    const getFedSummary = (hostId) => {
      return federationSummary.value[hostId] || null
    }

    const latencyBadgeClass = (ms) => {
      if (ms == null) return 'badge-secondary'
      if (ms < 100) return 'badge-success'
      if (ms < 500) return 'badge-warning'
      return 'badge-danger'
    }

    const hostCardClass = (host) => {
      if (!host.is_active) return 'host-card--inactive'
      const fed = getFedSummary(host.id)
      if (!fed) return ''
      if (fed.latency_ms == null) return 'host-card--unknown'
      if (fed.latency_ms > 500) return 'host-card--degraded'
      return 'host-card--online'
    }

    const hostPulseClass = (host) => {
      if (!host.is_active) return 'pulse-inactive'
      const fed = getFedSummary(host.id)
      if (!fed) return 'pulse-unknown'
      if (fed.latency_ms == null) return 'pulse-unknown'
      if (fed.latency_ms > 500) return 'pulse-warning'
      return 'pulse-online'
    }

    const pctBarClass = (pct) => {
      if (pct >= 85) return 'bar-danger'
      if (pct >= 65) return 'bar-warning'
      return 'bar-success'
    }

    const getHostResourceSummary = (hostId) => {
      return hostResourceSummary.value[hostId] || null
    }

    const computeHostResourceSummary = () => {
      const result = {}
      for (const host of hosts.value) {
        const hostNodes = allNodes.value.filter(n => n.host_id === host.id)
        if (!hostNodes.length) continue

        let totalCpu = 0
        let totalMem = 0
        let usedMem = 0
        let totalDisk = 0
        let usedDisk = 0
        let statCount = 0

        for (const node of hostNodes) {
          const stat = nodeStats.value[`${host.id}-${node.node_name}`]
          if (!stat) continue
          statCount++
          if (stat.cpu != null) totalCpu += stat.cpu
          if (stat.memory?.total) { totalMem += stat.memory.total; usedMem += stat.memory.used || 0 }
          if (stat.rootfs?.total) { totalDisk += stat.rootfs.total; usedDisk += stat.rootfs.used || 0 }
        }

        if (!statCount) continue

        const cpuPct = Math.round((totalCpu / statCount) * 100)
        const ramPct = totalMem ? Math.round((usedMem / totalMem) * 100) : 0
        const diskPct = totalDisk ? Math.round((usedDisk / totalDisk) * 100) : 0

        result[host.id] = {
          cpuPct,
          ramPct,
          diskPct,
          ramUsedGB: (usedMem / (1024 ** 3)).toFixed(0),
          ramTotalGB: (totalMem / (1024 ** 3)).toFixed(0),
          diskUsedTB: totalDisk > (1024 ** 4) ? (usedDisk / (1024 ** 4)).toFixed(1) + 'TB' : (usedDisk / (1024 ** 3)).toFixed(0) + 'GB',
          diskTotalTB: totalDisk > (1024 ** 4) ? (totalDisk / (1024 ** 4)).toFixed(1) + 'TB' : (totalDisk / (1024 ** 3)).toFixed(0) + 'GB',
        }
      }
      hostResourceSummary.value = result
    }

    const onHostAdded = async () => {
      showAddModal.value = false
      await fetchHosts()
      handleRefreshAll()
    }

    const testConnection = async (hostId) => {
      testing.value[hostId] = true
      try {
        const response = await api.proxmox.testConnection(hostId)
        const ok = response.data.status === 'success'
        testResults.value = {
          ...testResults.value,
          [hostId]: { ok, latency: response.data.latency_ms, message: response.data.message }
        }
        if (ok) {
          toast.success('Connection successful!')
        } else {
          toast.error('Connection failed: ' + response.data.message)
        }
      } catch (error) {
        testResults.value = {
          ...testResults.value,
          [hostId]: { ok: false, latency: null, message: 'Request failed' }
        }
        console.error('Failed to test connection:', error)
      } finally {
        delete testing.value[hostId]
      }
    }

    const testAllConnections = async () => {
      testingAll.value = true
      testAllResults.value = []
      try {
        const results = await Promise.all(
          hosts.value.map(host =>
            api.proxmox.testConnection(host.id)
              .then(res => ({
                id: host.id,
                name: host.name,
                hostname: `${host.hostname}:${host.port}`,
                ok: res.data.status === 'success',
                latency: res.data.latency_ms,
                message: res.data.message || '',
              }))
              .catch(err => ({
                id: host.id,
                name: host.name,
                hostname: `${host.hostname}:${host.port}`,
                ok: false,
                latency: null,
                message: err?.response?.data?.detail || 'Request failed',
              }))
          )
        )
        testAllResults.value = results
        const failed = results.filter(r => !r.ok).length
        if (failed === 0) {
          toast.success(`All ${results.length} hosts reachable`)
        } else {
          toast.warning(`${failed} of ${results.length} hosts unreachable`)
        }
      } finally {
        testingAll.value = false
      }
    }

    const pollHost = async (hostId) => {
      try {
        await api.proxmox.pollHost(hostId)
        toast.success('Polling started')
        setTimeout(() => {
          fetchHosts()
          handleRefreshAll()
        }, 2000)
      } catch (error) {
        console.error('Failed to poll host:', error)
      }
    }

    const refreshAllNodes = async () => {
      loadingNodes.value = true
      try {
        const nodesPromises = hosts.value.map(host =>
          api.proxmox.listNodes(host.id).catch(err => {
            console.error(`Failed to fetch nodes for ${host.name}:`, err)
            return { data: [] }
          })
        )
        const results = await Promise.all(nodesPromises)

        // Flatten all nodes and add host_id reference
        allNodes.value = results.flatMap((result, index) =>
          result.data.map(node => ({
            ...node,
            host_id: hosts.value[index].id
          }))
        )
      } catch (error) {
        console.error('Failed to refresh nodes:', error)
      } finally {
        loadingNodes.value = false
      }
    }

    // Load live stats for all nodes in parallel after the node list is ready
    const loadNodeStats = async () => {
      if (allNodes.value.length === 0) return

      const tasks = allNodes.value.map(node => {
        const hostId = node.host_id
        const nodeName = node.node_name
        const key = `${hostId}-${nodeName}`

        return Promise.allSettled([
          api.pveNode.nodeStatus(hostId, nodeName),
          api.pveNode.nodeVms(hostId, nodeName),
          api.pveNode.containers(hostId, nodeName),
        ]).then(([statusRes, vmsRes, lxcRes]) => {
          const status = statusRes.status === 'fulfilled' ? statusRes.value.data : null
          const vms = vmsRes.status === 'fulfilled' ? vmsRes.value.data : []
          const lxcs = lxcRes.status === 'fulfilled' ? lxcRes.value.data : []

          nodeStats.value = {
            ...nodeStats.value,
            [key]: {
              cpu: status?.cpu ?? null,
              memory: status?.memory ?? null,
              rootfs: status?.rootfs ?? null,
              uptime: status?.uptime ?? null,
              vmCount: Array.isArray(vms) ? vms.filter(v => v.type === 'qemu' || !v.type).length : 0,
              lxcCount: Array.isArray(lxcs) ? lxcs.length : 0,
            }
          }
        }).catch(err => {
          console.error(`Failed to load live stats for ${nodeName}:`, err)
        })
      })

      await Promise.allSettled(tasks)
      computeHostResourceSummary()
    }

    // Combined refresh: nodes first, then live stats async (non-blocking)
    const handleRefreshAll = async () => {
      await refreshAllNodes()
      loadNodeStats()
    }

    const datacentersWithNodes = computed(() => {
      return hosts.value.map(host => ({
        ...host,
        nodes: allNodes.value.filter(node => node.host_id === host.id)
      }))
    })

    // Helper: retrieve live stats for a node (returns null if still loading)
    const getNodeStat = (hostId, nodeName) => {
      return nodeStats.value[`${hostId}-${nodeName}`] ?? null
    }

    // CPU helpers
    const cpuPct = (cpu) => {
      if (cpu == null) return 0
      return Math.round(cpu * 100)
    }
    const cpuBarClass = (cpu) => {
      const pct = cpuPct(cpu)
      if (pct >= 80) return 'bar-danger'
      if (pct >= 60) return 'bar-warning'
      return 'bar-success'
    }

    // RAM helpers
    const ramPct = (memory) => {
      if (!memory || !memory.total) return 0
      return Math.round((memory.used / memory.total) * 100)
    }
    const ramBarClass = (memory) => {
      const pct = ramPct(memory)
      if (pct >= 80) return 'bar-danger'
      if (pct >= 60) return 'bar-warning'
      return 'bar-success'
    }

    // Disk helpers
    const diskPct = (rootfs) => {
      if (!rootfs || !rootfs.total) return 0
      return Math.round((rootfs.used / rootfs.total) * 100)
    }
    const diskBarClass = (rootfs) => {
      const pct = diskPct(rootfs)
      if (pct >= 80) return 'bar-danger'
      if (pct >= 60) return 'bar-warning'
      return 'bar-success'
    }

    const formatGB = (bytes) => {
      if (!bytes) return '0'
      return (bytes / (1024 * 1024 * 1024)).toFixed(1)
    }

    const formatUptime = (seconds) => {
      if (!seconds) return 'N/A'
      const days = Math.floor(seconds / 86400)
      const hours = Math.floor((seconds % 86400) / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)
      return `${days}d ${hours}h ${minutes}m`
    }

    const openEdit = (host) => {
      editHost.value = {
        id: host.id,
        name: host.name,
        hostname: host.hostname,
        port: host.port,
        is_active: host.is_active,
        verify_ssl: host.verify_ssl,
        token_id: host.token_id || '',
        token_secret: '',
        username: host.username || '',
        password: '',
        default_storage: host.default_storage || '',
        default_bridge: host.default_bridge || '',
        default_node: host.default_node || '',
        iso_storage: host.iso_storage || '',
        idrac_type: host.idrac_type || '',
        idrac_hostname: host.idrac_hostname || '',
        idrac_port: host.idrac_port || 443,
        idrac_username: host.idrac_username || '',
        idrac_password: '',
      }
      editAuthMethod.value = host.token_id ? 'token' : 'password'
      showEditModal.value = true
    }

    const saveEdit = async () => {
      saving.value = true
      try {
        const data = { ...editHost.value }
        // Don't send empty secrets (would clear existing)
        if (!data.token_secret) delete data.token_secret
        if (!data.password) delete data.password
        if (!data.idrac_password) delete data.idrac_password
        // Clear iDRAC fields if type removed
        if (!data.idrac_type) {
          data.idrac_hostname = ''
          data.idrac_username = ''
          delete data.idrac_password
        }
        await api.proxmox.updateHost(editHost.value.id, data)
        toast.success('Host updated')
        showEditModal.value = false
        await fetchHosts()
      } catch (error) {
        console.error('Failed to update host:', error)
      } finally {
        saving.value = false
      }
    }

    const deleteHost = async (hostId) => {
      if (!confirm('Are you sure you want to delete this Proxmox host?')) return

      try {
        await api.proxmox.deleteHost(hostId)
        toast.success('Host deleted')
        await fetchHosts()
      } catch (error) {
        console.error('Failed to delete host:', error)
      }
    }

    const formatDate = (dateString) => {
      return new Date(dateString).toLocaleString()
    }

    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const gb = bytes / (1024 * 1024 * 1024)
      return gb.toFixed(2) + ' GB'
    }

    onMounted(() => {
      fetchHosts().then(() => {
        handleRefreshAll()
      })
      fetchFederationSummary()
    })

    return {
      hosts,
      allNodes,
      loading,
      loadingNodes,
      saving,
      showAddModal,
      showEditModal,
      editHost,
      editAuthMethod,
      useApiToken,
      nodeStats,
      federationSummary,
      datacentersWithNodes,
      testing,
      testResults,
      testingAll,
      testAllResults,
      onHostAdded,
      openEdit,
      saveEdit,
      testConnection,
      testAllConnections,
      pollHost,
      refreshAllNodes,
      handleRefreshAll,
      deleteHost,
      formatDate,
      formatBytes,
      formatUptime,
      formatGB,
      getNodeStat,
      getFedSummary,
      getHostResourceSummary,
      latencyBadgeClass,
      hostCardClass,
      hostPulseClass,
      pctBarClass,
      cpuPct,
      cpuBarClass,
      ramPct,
      ramBarClass,
      diskPct,
      diskBarClass,
      // Drawer
      showDetailDrawer,
      drawerHost,
      drawerNodes,
      drawerTasks,
      drawerLoadingNodes,
      drawerTasksLoading,
      openDetailDrawer,
      closeDetailDrawer,
      formatTaskTime,
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}

.page-header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
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

/* ── Host cards grid ──────────────────────────────────────────────────────── */

.host-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
  padding: 1rem;
}

.host-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  background: var(--background);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.host-card--online {
  border-left: 3px solid #22c55e;
}

.host-card--degraded {
  border-left: 3px solid #f59e0b;
}

.host-card--inactive {
  border-left: 3px solid #6b7280;
  opacity: 0.75;
}

.host-card--unknown {
  border-left: 3px solid var(--border-color);
}

.host-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.host-card__name {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.host-card__hostname {
  font-family: monospace;
}

/* Animated status pulse dot */
.status-pulse {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.pulse-online {
  background-color: #22c55e;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.6);
  animation: pulse-green 2s infinite;
}

.pulse-warning {
  background-color: #f59e0b;
  box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.6);
  animation: pulse-orange 2s infinite;
}

.pulse-inactive {
  background-color: #6b7280;
}

.pulse-unknown {
  background-color: var(--border-color);
}

@keyframes pulse-green {
  0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.6); }
  70% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

@keyframes pulse-orange {
  0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.6); }
  70% { box-shadow: 0 0 0 8px rgba(245, 158, 11, 0); }
  100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
}

/* Cluster info rows */
.host-card__cluster-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.5rem 0;
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
}

.cluster-info-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
}

.ci-label {
  color: var(--text-secondary);
  width: 4rem;
  flex-shrink: 0;
  font-weight: 500;
}

.ci-value {
  color: var(--text-primary);
}

/* Resource bars */
.host-card__resources {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.res-bar-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
}

.res-label {
  color: var(--text-secondary);
  font-weight: 500;
  width: 2.75rem;
  flex-shrink: 0;
}

.res-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex: 1;
  min-width: 0;
}

.res-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.res-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.res-bar-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
  font-family: monospace;
}

/* Action buttons */
.host-card__actions {
  flex-wrap: wrap;
}

.flex-1 {
  flex: 1;
}

/* Test-all results */
.test-all-results {
  padding: 1rem;
  border-top: 1px solid var(--border-color);
}

.test-all-title {
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0 0 0.75rem 0;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* ── Badge colors ─────────────────────────────────────────────────────────── */

.badge-warning {
  background-color: #f59e0b;
  color: #fff;
}

.badge-secondary {
  background-color: var(--text-secondary, #6b7280);
  color: #fff;
}

.bar-success { background-color: #22c55e; }
.bar-warning { background-color: #f59e0b; }
.bar-danger  { background-color: #ef4444; }

/* ── Button sizes ─────────────────────────────────────────────────────────── */

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

/* ── Nodes section ────────────────────────────────────────────────────────── */

.nodes-section { padding: 0; }

.datacenter-section {
  margin-bottom: 2rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid var(--border-color);
}

.datacenter-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.datacenter-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--primary-color);
  padding-left: 0.5rem;
  border-left: 3px solid var(--primary-color);
}

.nodes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.node-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  background: var(--background);
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.node-header h5 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
}

.node-link {
  color: #3b82f6;
  text-decoration: none;
}
.node-link:hover { text-decoration: underline; }

.node-stats {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.stat {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
}

.stat-label {
  color: var(--text-secondary);
  font-weight: 500;
}

.stat-value {
  color: var(--text-primary);
  font-family: monospace;
}

/* Live stats section */
.node-live-stats { margin-top: 0.75rem; }

.live-stats-divider {
  border-top: 1px dashed var(--border-color);
  margin-bottom: 0.75rem;
}

.live-stat-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
  margin-bottom: 0.5rem;
}

.live-stat-row:last-child { margin-bottom: 0; }

.live-stat-label {
  color: var(--text-secondary);
  font-weight: 500;
  width: 4.5rem;
  flex-shrink: 0;
}

.stat-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: 1;
  min-width: 0;
}

.stat-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
  min-width: 0;
}

.stat-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.stat-bar-label {
  color: var(--text-primary);
  font-family: monospace;
  font-size: 0.75rem;
  white-space: nowrap;
}

.guest-badges {
  display: flex;
  gap: 0.375rem;
}

.stat-skeleton {
  color: var(--text-secondary);
  opacity: 0.45;
  font-size: 0.875rem;
}

/* ── Modal ────────────────────────────────────────────────────────────────── */

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
  background: var(--surface, white);
  border-radius: 0.5rem;
  max-width: 640px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
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

.modal-body { padding: 1.5rem; }

/* Edit sections */
.edit-section {
  margin-bottom: 1.25rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border-color);
}

.edit-section:last-of-type {
  border-bottom: none;
  margin-bottom: 0;
}

.section-subtitle {
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 0.75rem 0;
  color: var(--text-secondary);
}

.form-group { margin-bottom: 0.875rem; }

.form-label {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
}

.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.form-inline-row {
  display: flex;
  gap: 1.5rem;
  align-items: center;
}

.inline-check {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  cursor: pointer;
}

.info-box {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.625rem 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.5rem;
}

/* ── Detail Drawer ────────────────────────────────────────────────────────── */

.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 500;
  display: flex;
  justify-content: flex-end;
}

.detail-drawer {
  width: 420px;
  max-width: 95vw;
  height: 100%;
  background: var(--surface, var(--bg-card, #1e1e2e));
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.4);
}

/* Slide transition */
.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 0.28s cubic-bezier(0.25, 0.8, 0.25, 1),
              opacity 0.25s ease;
}

.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.drawer-header {
  padding: 1.25rem 1.5rem 1rem;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.drawer-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.drawer-title {
  margin: 0 0 0.15rem 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

.drawer-subtitle { margin-top: 0.1rem; }

.drawer-quick-actions {
  flex-wrap: wrap;
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 0 1.5rem 0;
}

/* Drawer sections */
.drawer-section {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.drawer-section:last-child { border-bottom: none; }

.drawer-section-title {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted, #888);
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

/* Info grid */
.drawer-info-grid {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.di-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.di-label {
  min-width: 72px;
  color: var(--text-secondary, var(--text-muted, #888));
  font-weight: 500;
  flex-shrink: 0;
}

.di-value {
  color: var(--text-primary);
  word-break: break-all;
}

.font-mono { font-family: monospace; }

/* Drawer node cards */
.drawer-node-card {
  background: var(--background, var(--bg-secondary, #2a2a3e));
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
}

.drawer-node-card:last-child { margin-bottom: 0; }

.dnc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.625rem;
}

.dnc-name {
  font-size: 0.9rem;
  font-weight: 600;
  font-family: monospace;
  color: var(--text-primary);
}

.dnc-bars {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.dnc-bar-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
}

.dnc-bar-label {
  min-width: 3rem;
  color: var(--text-secondary, var(--text-muted, #888));
  font-weight: 500;
}

.dnc-bar-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
}

.dnc-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
  min-width: 60px;
}

.dnc-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.dnc-bar-pct {
  font-size: 0.75rem;
  font-family: monospace;
  color: var(--text-primary);
  white-space: nowrap;
}

.dnc-meta {
  margin-top: 0.5rem;
  padding-top: 0.4rem;
  border-top: 1px dashed var(--border-color);
}

/* Tasks list */
.drawer-tasks-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.drawer-task-item {
  padding: 0.5rem 0.75rem;
  background: var(--background, var(--bg-secondary, #2a2a3e));
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}

.dt-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  margin-bottom: 0.2rem;
}

.dt-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-ok      { background: #10b981; }
.dot-running { background: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.2); }
.dot-error   { background: #ef4444; }

.dt-type {
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.dt-id { font-family: monospace; }

.dt-meta { color: var(--text-secondary, var(--text-muted, #888)); }

/* ── Utility ──────────────────────────────────────────────────────────────── */

.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.align-center { align-items: center; }
.mt-1 { margin-top: 0.5rem; }
.ml-1 { margin-left: 0.25rem; }
.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.text-muted { color: var(--text-secondary); }
.text-center { text-align: center; }
.ml-auto { margin-left: auto; }
</style>
