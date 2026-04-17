<template>
  <div class="node-detail-page">
    <SkeletonLoader v-if="loadingInit" type="stat" :count="4" />
    <div v-else-if="!nodeStatus" class="node-error-state">
      <div class="node-error-state__icon">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      </div>
      <h4 class="node-error-state__title">Failed to load node information</h4>
      <p class="node-error-state__sub">{{ nodeLoadError || 'Could not reach the Proxmox API for this node.' }}</p>
      <button @click="loadAll" class="btn btn-outline">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:4px;"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
        Retry
      </button>
    </div>

    <template v-else>
      <!-- Breadcrumb -->
      <nav class="breadcrumb-nav" aria-label="breadcrumb">
        <router-link to="/proxmox" class="breadcrumb-crumb">All Hosts</router-link>
        <span class="breadcrumb-sep">›</span>
        <router-link :to="`/proxmox/${hostId}/cluster`" class="breadcrumb-crumb">{{ hostName || hostId }}</router-link>
        <span class="breadcrumb-sep">›</span>
        <span class="breadcrumb-crumb breadcrumb-crumb--current">{{ node }}</span>
      </nav>

      <!-- Header -->
      <div class="page-header mb-2">
        <div class="header-left">
          <router-link to="/proxmox" class="back-link">← Proxmox Hosts</router-link>
          <h2 class="node-title">
            {{ node }}
            <button class="btn-copy" @click="copyNodeName" title="Copy node name">⎘</button>
            <button class="btn-copy" @click="copySshCommand" title="Copy SSH command">SSH</button>
            <span :class="nodeStatus.status === 'online' ? 'badge badge-success ml-1' : 'badge badge-danger ml-1'">
              {{ nodeStatus.status || 'unknown' }}
            </span>
          </h2>
          <div class="header-meta flex gap-2 text-sm text-muted">
            <span v-if="nodeStatus.pveversion || nodeStatus['pve-manager-version']">
              PVE {{ nodeStatus.pveversion || nodeStatus['pve-manager-version'] }}
            </span>
            <span v-if="nodeStatus.kversion || nodeStatus.kernel_version">
              Kernel: {{ nodeStatus.kversion || nodeStatus.kernel_version }}
            </span>
            <span>Uptime: {{ formatUptime(nodeStatus.uptime) }}</span>
          </div>
        </div>
        <div class="header-stats flex gap-2">
          <div class="mini-stat">
            <span class="mini-stat__label">CPU</span>
            <span class="mini-stat__value">{{ nodeCpuPct }}%</span>
          </div>
          <div class="mini-stat">
            <span class="mini-stat__label">RAM</span>
            <span class="mini-stat__value">{{ nodeRamPct }}%</span>
          </div>
          <button
            @click="router.push(`/monitor/${hostId}/${node}`)"
            class="btn btn-outline btn-sm"
            style="align-self:center"
            title="Open full performance monitor"
          >Monitor</button>
        </div>
      </div>

      <!-- Stats row -->
      <div class="stats-row mb-2">
        <div class="stat-card-sm">
          <div class="stat-card-sm__label">CPU Cores</div>
          <div class="stat-card-sm__value">{{ nodeStatus.cpuinfo?.cpus || nodeStatus.cpu_count || '—' }}</div>
          <div v-if="nodeStatus.cpuinfo?.model" class="stat-card-sm__sub text-xs text-muted">{{ nodeStatus.cpuinfo.model }}</div>
        </div>
        <div class="stat-card-sm">
          <div class="stat-card-sm__label">RAM Used / Total</div>
          <div class="stat-card-sm__value">
            {{ formatBytes(nodeStatus.memory?.used) }} / {{ formatBytes(nodeStatus.memory?.total) }}
          </div>
          <div class="stat-card-sm__sub">
            <div class="mini-usage-bar">
              <div class="mini-usage-fill" :style="{ width: nodeRamPct + '%', background: nodeRamPct > 85 ? '#ef4444' : nodeRamPct > 65 ? '#f59e0b' : '#22c55e' }"></div>
            </div>
          </div>
        </div>
        <div class="stat-card-sm">
          <div class="stat-card-sm__label">Root Disk</div>
          <div class="stat-card-sm__value">{{ formatBytes(nodeStatus.rootfs?.used) }} / {{ formatBytes(nodeStatus.rootfs?.total) }}</div>
        </div>
        <div class="stat-card-sm">
          <div class="stat-card-sm__label">Load Avg</div>
          <div class="stat-card-sm__value">{{ formatLoadAvg(nodeStatus.loadavg) }}</div>
        </div>
        <div v-if="nodeStatus.cpuinfo?.sockets" class="stat-card-sm">
          <div class="stat-card-sm__label">CPU Sockets</div>
          <div class="stat-card-sm__value">{{ nodeStatus.cpuinfo.sockets }}</div>
          <div v-if="nodeStatus.cpuinfo?.cores" class="stat-card-sm__sub text-xs text-muted">{{ nodeStatus.cpuinfo.cores }} cores/socket</div>
        </div>
        <div v-if="nodeStatus.swap" class="stat-card-sm">
          <div class="stat-card-sm__label">Swap</div>
          <div class="stat-card-sm__value">{{ formatBytes(nodeStatus.swap?.used) }} / {{ formatBytes(nodeStatus.swap?.total) }}</div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs mb-2">
        <button v-for="tab in tabs" :key="tab.id"
          :class="['tab-btn', activeTab === tab.id ? 'tab-btn--active' : '']"
          @click="switchTab(tab.id)">{{ tab.label }}</button>
      </div>

      <!-- ─── Overview Tab ─── -->
      <div v-if="activeTab === 'overview'">
        <div class="flex gap-1 mb-2 align-center">
          <span class="text-sm text-muted">Timeframe:</span>
          <select v-model="rrdTimeframe" @change="loadRrd" class="form-control form-control-sm" style="width:auto">
            <option value="hour">Last Hour</option>
            <option value="day">Last Day</option>
            <option value="week">Last Week</option>
          </select>
        </div>
        <div class="charts-grid">
          <div class="card chart-card">
            <div class="card-header"><h4>CPU %</h4></div>
            <div class="chart-wrap">
              <Line v-if="cpuChartData" :data="cpuChartData" :options="lineChartOptions" />
              <div v-else class="text-muted text-center text-sm pt-2">{{ rrdLoaded ? 'No data' : 'Loading...' }}</div>
            </div>
          </div>
          <div class="card chart-card">
            <div class="card-header"><h4>Memory %</h4></div>
            <div class="chart-wrap">
              <Line v-if="memChartData" :data="memChartData" :options="lineChartOptions" />
              <div v-else class="text-muted text-center text-sm pt-2">{{ rrdLoaded ? 'No data' : 'Loading...' }}</div>
            </div>
          </div>
          <div class="card chart-card">
            <div class="card-header"><h4>Network I/O (bytes/s)</h4></div>
            <div class="chart-wrap">
              <Line v-if="netChartData" :data="netChartData" :options="bytesChartOptions" />
              <div v-else class="text-muted text-center text-sm pt-2">{{ rrdLoaded ? 'No data' : 'Loading...' }}</div>
            </div>
          </div>
          <div class="card chart-card">
            <div class="card-header"><h4>Disk I/O (bytes/s)</h4></div>
            <div class="chart-wrap">
              <Line v-if="diskChartData" :data="diskChartData" :options="bytesChartOptions" />
              <div v-else-if="diskIoLive" class="disk-io-live">
                <div class="dil-row"><span class="dil-label dil-read">R</span><span class="dil-val">{{ fmtBps(diskIoLive.read) }}</span><span class="dil-hint">(VM aggregate)</span></div>
                <div class="dil-row"><span class="dil-label dil-write">W</span><span class="dil-val">{{ fmtBps(diskIoLive.write) }}</span></div>
              </div>
              <div v-else class="text-muted text-center text-sm pt-2">{{ rrdLoaded ? 'Not reported by Proxmox for this node' : 'Loading...' }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── VMs & Containers Tab ─── -->
      <div v-if="activeTab === 'guests'">
        <div class="card">
          <div class="card-header">
            <h3>VMs &amp; Containers on {{ node }}</h3>
            <button @click="loadGuests" class="btn btn-outline btn-sm" :disabled="loadingGuests">
              {{ loadingGuests ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <SkeletonLoader v-if="loadingGuests" type="table" :count="5" />
          <div v-else-if="guestsError" class="tab-error-banner">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>{{ guestsError }}</span>
            <button @click="loadGuests" class="btn btn-sm btn-outline">Retry</button>
          </div>
          <div v-else-if="guests.length === 0" class="tab-empty">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/></svg>
            <p>No VMs or containers found on this node.</p>
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>VMID</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>CPU</th>
                  <th>RAM</th>
                  <th>Disk Used</th>
                  <th>Uptime</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="guests.length === 0">
                  <td colspan="9" class="text-muted text-center">No guests found</td>
                </tr>
                <tr v-for="g in guests" :key="`${g.type}-${g.vmid}`"
                  class="clickable-row"
                  @click.stop="navigateToGuest(g)">
                  <td><strong>{{ g.vmid }}</strong></td>
                  <td>{{ g.name || '—' }}</td>
                  <td>
                    <span v-if="g.type === 'qemu'" class="badge badge-info">VM</span>
                    <span v-else class="badge badge-warning">CT</span>
                  </td>
                  <td>
                    <span :class="g.status === 'running' ? 'badge badge-success' : 'badge badge-danger'">
                      {{ g.status }}
                    </span>
                  </td>
                  <td>{{ g.cpu != null ? (g.cpu * 100).toFixed(1) + '%' : '—' }}</td>
                  <td class="text-sm">
                    {{ g.maxmem ? formatBytes(g.mem) + ' / ' + formatBytes(g.maxmem) : '—' }}
                  </td>
                  <td class="text-sm">
                    {{ g.maxdisk ? formatBytes(g.disk) + ' / ' + formatBytes(g.maxdisk) : '—' }}
                  </td>
                  <td class="text-sm">{{ formatUptime(g.uptime) }}</td>
                  <td @click.stop>
                    <div class="flex gap-1">
                      <button
                        v-if="g.status !== 'running'"
                        @click="guestAction(g, 'start')"
                        class="btn btn-success btn-sm"
                        :disabled="guestActioning[`${g.type}-${g.vmid}`]">
                        Start
                      </button>
                      <button
                        v-else
                        @click="guestAction(g, 'shutdown')"
                        class="btn btn-outline btn-sm"
                        :disabled="guestActioning[`${g.type}-${g.vmid}`]">
                        Stop
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Storage Tab ─── -->
      <div v-if="activeTab === 'storage'">
        <!-- Storage Pools -->
        <div class="card mb-2">
          <div class="card-header">
            <h3>Storage Pools</h3>
            <button @click="loadStorage" class="btn btn-outline btn-sm" :disabled="loadingStorage">
              {{ loadingStorage ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <SkeletonLoader v-if="loadingStorage" type="table" :count="5" />
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Content</th>
                  <th>Usage</th>
                  <th>Available</th>
                  <th>Total</th>
                  <th>Enabled</th>
                  <th>Shared</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="storageList.length === 0">
                  <td colspan="10" class="text-muted text-center">No storage found</td>
                </tr>
                <tr v-for="s in storageList" :key="s.storage" class="clickable-row" @click="browseStorage(s.storage)">
                  <td><strong>{{ s.storage }}</strong></td>
                  <td><span class="badge badge-info">{{ s.type }}</span></td>
                  <td class="text-sm">{{ (s.content || '').replace(/,/g, ', ') || '—' }}</td>
                  <td style="min-width:140px">
                    <div class="usage-bar-wrap">
                      <div class="usage-bar" :style="{ width: usagePct(s) + '%', background: usageColor(s) }"></div>
                    </div>
                    <span class="text-sm">{{ formatBytes(s.used) }} / {{ formatBytes(s.total) }} ({{ usagePct(s) }}%)</span>
                  </td>
                  <td class="text-sm">{{ formatBytes(s.avail) }}</td>
                  <td class="text-sm">{{ formatBytes(s.total) }}</td>
                  <td>
                    <span v-if="s.enabled !== 0 && s.enabled !== false" class="badge badge-success">Yes</span>
                    <span v-else class="badge badge-danger">No</span>
                  </td>
                  <td>
                    <span v-if="s.shared" class="badge badge-info">Shared</span>
                    <span v-else class="text-muted text-sm">Local</span>
                  </td>
                  <td>
                    <span v-if="s.active" class="badge badge-success">Active</span>
                    <span v-else class="badge badge-danger">Inactive</span>
                  </td>
                  <td @click.stop>
                    <button @click="browseStorage(s.storage)" class="btn btn-outline btn-sm">Browse</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- ZFS Pools -->
        <div class="card">
          <div class="card-header">
            <h3>ZFS Pools</h3>
            <button @click="loadZfsPools" class="btn btn-outline btn-sm" :disabled="loadingZfs">
              {{ loadingZfs ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <SkeletonLoader v-if="loadingZfs" type="table" :count="3" />
          <div v-else-if="zfsError" class="text-muted text-center" style="padding:1.5rem">
            {{ zfsError }}
          </div>
          <div v-else-if="zfsPools.length === 0" class="text-muted text-center" style="padding:1.5rem">
            No ZFS pools found on this node
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Pool Name</th>
                  <th>Status</th>
                  <th>Size</th>
                  <th>Free</th>
                  <th>Allocated</th>
                  <th>Usage</th>
                  <th>Dedup</th>
                  <th>Fragmentation</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pool in zfsPools" :key="pool.name">
                  <td><strong>{{ pool.name }}</strong></td>
                  <td>
                    <span :class="zfsStatusBadge(pool.health || pool.status)">
                      {{ pool.health || pool.status || '—' }}
                    </span>
                  </td>
                  <td class="text-sm">{{ pool.size ? formatBytes(pool.size) : '—' }}</td>
                  <td class="text-sm">{{ pool.free ? formatBytes(pool.free) : '—' }}</td>
                  <td class="text-sm">{{ pool.alloc ? formatBytes(pool.alloc) : '—' }}</td>
                  <td style="min-width:120px">
                    <template v-if="pool.size && pool.alloc">
                      <div class="usage-bar-wrap">
                        <div class="usage-bar" :style="{ width: zfsUsagePct(pool) + '%', background: usageColorPct(zfsUsagePct(pool)) }"></div>
                      </div>
                      <span class="text-sm">{{ zfsUsagePct(pool) }}%</span>
                    </template>
                    <span v-else class="text-muted text-sm">—</span>
                  </td>
                  <td class="text-sm">{{ pool.dedup != null ? parseFloat(pool.dedup).toFixed(2) + 'x' : '—' }}</td>
                  <td class="text-sm">{{ pool.frag != null ? pool.frag + '%' : '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Network Tab ─── -->
      <div v-if="activeTab === 'network'">
        <div class="card">
          <div class="card-header">
            <h3>Network Interfaces</h3>
            <div class="flex gap-1">
              <button @click="showCreateNetworkModal = true" class="btn btn-primary btn-sm">
                + Create Interface
              </button>
              <button @click="applyNetwork" class="btn btn-outline btn-sm" :disabled="applyingNetwork">
                {{ applyingNetwork ? 'Applying...' : 'Apply Network Config' }}
              </button>
              <button @click="loadNetwork" class="btn btn-outline btn-sm" :disabled="loadingNetwork">
                Refresh
              </button>
            </div>
          </div>
          <SkeletonLoader v-if="loadingNetwork" type="table" :count="5" />
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Interface</th>
                  <th>Type</th>
                  <th>State</th>
                  <th>Address / CIDR</th>
                  <th>Gateway</th>
                  <th>Bridge Ports / Slaves</th>
                  <th>VLAN ID</th>
                  <th>Autostart</th>
                  <th>Comments</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="networkIfaces.length === 0">
                  <td colspan="10" class="text-muted text-center">No interfaces found</td>
                </tr>
                <tr v-for="iface in networkIfaces" :key="iface.iface">
                  <td><code>{{ iface.iface }}</code></td>
                  <td>
                    <span class="badge badge-info">{{ iface.type }}</span>
                  </td>
                  <td>
                    <span :class="iface.active ? 'badge badge-success' : 'badge badge-danger'">
                      {{ iface.active ? 'UP' : 'DOWN' }}
                    </span>
                  </td>
                  <td class="text-sm">
                    <code v-if="iface.address">{{ iface.address }}{{ iface.netmask ? '/' + cidrFromNetmask(iface.netmask) : '' }}</code>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="text-sm">{{ iface.gateway || '—' }}</td>
                  <td class="text-sm">{{ iface['bridge-ports'] || iface.slaves || '—' }}</td>
                  <td class="text-sm">
                    <span v-if="iface['vlan-id'] || iface.vlan_id" class="badge badge-secondary">{{ iface['vlan-id'] || iface.vlan_id }}</span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>
                    <span v-if="iface.autostart" class="badge badge-success">Yes</span>
                    <span v-else class="text-muted text-sm">No</span>
                  </td>
                  <td class="text-sm text-muted" style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" :title="iface.comments || iface.comment || ''">
                    {{ iface.comments || iface.comment || '—' }}
                  </td>
                  <td @click.stop>
                    <div class="flex gap-1">
                      <button
                        @click="openEditNetworkModal(iface)"
                        class="btn btn-outline btn-sm"
                        title="Edit interface">
                        Edit
                      </button>
                      <button
                        @click="deleteNetworkIface(iface)"
                        class="btn btn-danger btn-sm"
                        :disabled="networkIfaceDeleting[iface.iface]"
                        title="Delete interface">
                        {{ networkIfaceDeleting[iface.iface] ? '...' : 'Delete' }}
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Updates Tab ─── -->
      <div v-if="activeTab === 'updates'">
        <!-- Installed PVE Versions -->
        <div class="card mb-2">
          <div class="card-header">
            <h3>Installed Proxmox Versions</h3>
            <button @click="loadAptVersions" class="btn btn-outline btn-sm" :disabled="loadingAptVersions">
              {{ loadingAptVersions ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <SkeletonLoader v-if="loadingAptVersions" type="table" :count="5" />
          <div v-else-if="aptVersions.length === 0" class="text-muted text-center" style="padding:1.5rem">No version data available</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Package</th>
                  <th>Current Version</th>
                  <th>Latest Available</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pkg in aptVersions" :key="pkg.Package || pkg.package">
                  <td><code class="text-sm">{{ pkg.Package || pkg.package }}</code></td>
                  <td class="text-sm">{{ pkg.CurrentVersion || pkg.current_version || '—' }}</td>
                  <td class="text-sm">{{ pkg.NewVersion || pkg.new_version || pkg.Version || '—' }}</td>
                  <td>
                    <span v-if="(pkg.NewVersion || pkg.new_version) && (pkg.NewVersion || pkg.new_version) !== (pkg.CurrentVersion || pkg.current_version)" class="badge badge-warning">Update Available</span>
                    <span v-else class="badge badge-success">Up to date</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Available Updates (Enhanced) -->
        <div class="card">
          <div class="card-header">
            <h3>
              Available Updates
              <span v-if="aptUpdates.length > 0" class="badge badge-warning ml-1">{{ aptUpdates.length }}</span>
            </h3>
            <div class="flex gap-1 flex-wrap">
              <button
                @click="refreshPackageList"
                class="btn btn-outline btn-sm"
                :disabled="refreshingPackages">
                {{ refreshingPackages ? 'Refreshing...' : 'Refresh Package List' }}
              </button>
              <button @click="loadAptUpdates" class="btn btn-outline btn-sm" :disabled="loadingAptUpdates">
                {{ loadingAptUpdates ? 'Loading...' : 'Reload List' }}
              </button>
              <template v-if="aptUpdates.length > 0">
                <button
                  @click="upgradeSelectedPackages"
                  class="btn btn-outline btn-sm"
                  :disabled="upgradingSelected || selectedPackages.size === 0">
                  {{ upgradingSelected ? 'Starting...' : `Update Selected (${selectedPackages.size})` }}
                </button>
                <button
                  @click="upgradeAllPackages"
                  class="btn btn-primary btn-sm"
                  :disabled="upgradingAll">
                  {{ upgradingAll ? 'Starting...' : 'Update All' }}
                </button>
              </template>
            </div>
          </div>

          <!-- Active upgrade task progress -->
          <div v-if="upgradeTaskUpid" class="info-banner text-sm">
            <span>
              Task <code>{{ upgradeTaskUpid.slice(0, 30) }}...</code>
              <span v-if="upgradeTaskStatus" :class="upgradeTaskStatus === 'OK' ? 'badge badge-success ml-1' : upgradeTaskStatus === 'running' ? 'badge badge-warning ml-1' : 'badge badge-danger ml-1'">
                {{ upgradeTaskStatus || 'running' }}
              </span>
            </span>
            <button @click="dismissUpgradeTask" class="btn-inline-close">×</button>
          </div>

          <!-- Task log output for active upgrade -->
          <div v-if="upgradeTaskUpid && upgradeTaskLog.length" class="apt-task-log">
            <div class="apt-task-log__header">
              <span class="text-sm text-muted">Upgrade output</span>
              <button @click="upgradeTaskLog = []" class="btn-inline-close">×</button>
            </div>
            <pre class="apt-task-log__body">{{ upgradeTaskLog.join('\n') }}</pre>
          </div>

          <!-- Package search + select-all controls -->
          <div v-if="!loadingAptUpdates && aptUpdates.length > 0" class="apt-controls">
            <div class="apt-search">
              <input
                v-model="aptSearchQuery"
                class="form-control form-control-sm"
                placeholder="Filter packages..."
                style="min-width:200px"
              />
            </div>
            <div class="flex gap-1 align-center">
              <button @click="selectAllPackages" class="btn btn-outline btn-sm">Select All</button>
              <button @click="deselectAllPackages" class="btn btn-outline btn-sm">Deselect All</button>
              <span class="text-sm text-muted">
                {{ selectedPackages.size }} / {{ filteredAptUpdates.length }} selected
                <template v-if="aptSearchQuery"> (filtered from {{ aptUpdates.length }})</template>
              </span>
            </div>
          </div>

          <SkeletonLoader v-if="loadingAptUpdates" type="table" :count="5" />
          <div v-else-if="aptUpdates.length === 0" class="text-center" style="padding:2rem">
            <span class="badge badge-success" style="font-size:1rem;padding:0.5rem 1rem">System is up to date</span>
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th style="width:36px">
                    <input
                      type="checkbox"
                      :checked="allFilteredSelected"
                      :indeterminate.prop="someFilteredSelected && !allFilteredSelected"
                      @change="toggleAllFiltered"
                      title="Select / deselect all visible packages"
                    />
                  </th>
                  <th>Package</th>
                  <th>Current Version</th>
                  <th>New Version</th>
                  <th>Priority</th>
                  <th>Section</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="filteredAptUpdates.length === 0">
                  <td colspan="7" class="text-muted text-center">No packages match filter</td>
                </tr>
                <tr
                  v-for="pkg in filteredAptUpdates"
                  :key="pkg.Package || pkg.package"
                  :class="selectedPackages.has(pkg.Package || pkg.package) ? 'apt-row--selected' : ''"
                  @click="togglePackage(pkg.Package || pkg.package)"
                  style="cursor:pointer"
                >
                  <td @click.stop>
                    <input
                      type="checkbox"
                      :checked="selectedPackages.has(pkg.Package || pkg.package)"
                      @change="togglePackage(pkg.Package || pkg.package)"
                    />
                  </td>
                  <td><code class="text-sm">{{ pkg.Package || pkg.package }}</code></td>
                  <td class="text-sm text-muted">{{ pkg.OldVersion || pkg.old_version || pkg.current_version || '—' }}</td>
                  <td class="text-sm">
                    <strong>{{ pkg.Version || pkg.new_version || pkg.NewVersion || '—' }}</strong>
                  </td>
                  <td class="text-sm">{{ pkg.Priority || pkg.priority || '—' }}</td>
                  <td class="text-sm">{{ pkg.Section || pkg.section || '—' }}</td>
                  <td class="text-sm text-muted" style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" :title="pkg.Description || pkg.description || ''">
                    {{ pkg.Description || pkg.description || '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Hardware Tab ─── -->
      <div v-if="activeTab === 'hardware'">
        <!-- PCI Devices -->
        <div class="card mb-2">
          <div class="card-header">
            <h3>PCI Devices</h3>
            <button @click="loadPciDevices" class="btn btn-outline btn-sm" :disabled="loadingPci">
              {{ loadingPci ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <SkeletonLoader v-if="loadingPci" type="table" :count="4" />
          <div v-else-if="pciDevices.length === 0" class="text-muted text-center" style="padding:1.5rem">No PCI device data available</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Vendor</th>
                  <th>Device</th>
                  <th>Class</th>
                  <th>IOMMU Group</th>
                  <th>Sub-devices</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="dev in pciDevices" :key="dev.id || dev.device_name">
                  <td><code class="text-sm">{{ dev.id }}</code></td>
                  <td class="text-sm">{{ dev.vendor_name || dev.vendor || '—' }}</td>
                  <td class="text-sm">{{ dev.device_name || dev.device || '—' }}</td>
                  <td class="text-sm text-muted">{{ dev.class_name || dev.class || '—' }}</td>
                  <td class="text-sm">{{ dev.iommugroup != null ? dev.iommugroup : '—' }}</td>
                  <td class="text-sm text-muted">{{ dev.mdev ? 'mdev' : '' }}{{ dev.subsystem_vendor_name ? dev.subsystem_vendor_name + ' ' + (dev.subsystem_device_name || '') : '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- USB Devices -->
        <div class="card">
          <div class="card-header">
            <h3>USB Devices</h3>
            <button @click="loadUsbDevices" class="btn btn-outline btn-sm" :disabled="loadingUsb">
              {{ loadingUsb ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <SkeletonLoader v-if="loadingUsb" type="table" :count="4" />
          <div v-else-if="usbDevices.length === 0" class="text-muted text-center" style="padding:1.5rem">No USB device data available</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Bus/Dev</th>
                  <th>Vendor ID</th>
                  <th>Product ID</th>
                  <th>Manufacturer</th>
                  <th>Product</th>
                  <th>Speed</th>
                  <th>Class</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="dev in usbDevices" :key="`${dev.busnum}-${dev.devnum}`">
                  <td><code class="text-sm">{{ dev.busnum }}/{{ dev.devnum }}</code></td>
                  <td><code class="text-sm">{{ dev.vendid || dev.vendor_id || '—' }}</code></td>
                  <td><code class="text-sm">{{ dev.prodid || dev.product_id || '—' }}</code></td>
                  <td class="text-sm">{{ dev.manufacturer || dev.vendor_name || '—' }}</td>
                  <td class="text-sm">{{ dev.product || dev.product_name || '—' }}</td>
                  <td class="text-sm">{{ dev.speed || '—' }}</td>
                  <td class="text-sm text-muted">{{ dev.class || dev.usbclass || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Backup Schedules Tab ─── -->
      <div v-if="activeTab === 'backups'">
        <div class="card">
          <div class="card-header">
            <h3>Backup Schedules</h3>
            <div class="flex gap-1">
              <button @click="showCreateBackupModal = true" class="btn btn-primary btn-sm">
                + Create Schedule
              </button>
              <button @click="loadBackupSchedules" class="btn btn-outline btn-sm" :disabled="loadingBackups">
                Refresh
              </button>
            </div>
          </div>
          <SkeletonLoader v-if="loadingBackups" type="table" :count="5" />
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Schedule</th>
                  <th>Storage</th>
                  <th>Node</th>
                  <th>Mode</th>
                  <th>Compress</th>
                  <th>Enabled</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="backupSchedules.length === 0">
                  <td colspan="8" class="text-muted text-center">No backup schedules configured</td>
                </tr>
                <tr v-for="sched in backupSchedules" :key="sched.id">
                  <td><code class="text-sm">{{ sched.id }}</code></td>
                  <td class="text-sm"><code>{{ sched.schedule || sched.starttime || '—' }}</code></td>
                  <td class="text-sm">{{ sched.storage || '—' }}</td>
                  <td class="text-sm">{{ sched.node || 'all' }}</td>
                  <td class="text-sm">{{ sched.mode || '—' }}</td>
                  <td class="text-sm">{{ sched.compress || '—' }}</td>
                  <td>
                    <span v-if="sched.enabled !== 0 && sched.enabled !== false" class="badge badge-success">Yes</span>
                    <span v-else class="badge badge-danger">No</span>
                  </td>
                  <td @click.stop>
                    <button
                      @click="deleteBackupSchedule(sched)"
                      class="btn btn-danger btn-sm"
                      :disabled="backupDeleting[sched.id]">
                      {{ backupDeleting[sched.id] ? '...' : 'Delete' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Tasks Tab ─── -->
      <div v-if="activeTab === 'tasks'">
        <div class="card">
          <div class="card-header">
            <h3>Recent Tasks</h3>
            <button @click="loadTasks" class="btn btn-outline btn-sm" :disabled="loadingTasks">
              {{ loadingTasks ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <SkeletonLoader v-if="loadingTasks" type="table" :count="5" />
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Start Time</th>
                  <th>Type</th>
                  <th>ID</th>
                  <th>User</th>
                  <th>Status</th>
                  <th>Duration</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="tasks.length === 0">
                  <td colspan="7" class="text-muted text-center">No tasks found</td>
                </tr>
                <template v-for="task in tasks" :key="task.upid">
                  <tr :class="['clickable-row', task._expanded ? 'row-expanded' : '']"
                    @click="toggleTaskLog(task)">
                    <td class="text-sm">
                      {{ task.starttime ? new Date(task.starttime * 1000).toLocaleString() : '—' }}
                    </td>
                    <td class="text-sm">{{ formatTaskType(task) }}</td>
                    <td class="text-sm text-muted">{{ task.id || '—' }}</td>
                    <td class="text-sm">{{ task.user || '—' }}</td>
                    <td>
                      <span :class="taskBadgeClass(task.status)">{{ task.status || 'running' }}</span>
                    </td>
                    <td class="text-sm">{{ taskDuration(task) }}</td>
                    <td @click.stop>
                      <button
                        v-if="!task.endtime"
                        @click="stopTask(task)"
                        class="btn btn-danger btn-sm"
                        :disabled="task._stopping">
                        {{ task._stopping ? '...' : 'Stop' }}
                      </button>
                      <span v-else class="text-muted text-sm">{{ task._expanded ? '▲' : '▼' }}</span>
                    </td>
                  </tr>
                  <tr v-if="task._expanded" :key="task.upid + '-log'">
                    <td colspan="7" class="task-log-cell">
                      <div v-if="task._loadingLog" class="text-muted text-sm" style="padding: 0.75rem 1rem;">
                        Loading log...
                      </div>
                      <pre v-else class="task-log">{{ formatTaskLog(task._log) }}</pre>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Disk Health Tab ─── -->
      <div v-if="activeTab === 'disks'">
        <div class="card">
          <div class="card-header">
            <h3>Physical Disks</h3>
            <button @click="loadDisks" class="btn btn-outline btn-sm" :disabled="loadingDisks">
              {{ loadingDisks ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <div v-if="loadingDisks" class="loading-spinner"></div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Device</th>
                  <th>Model</th>
                  <th>Size</th>
                  <th>Type</th>
                  <th>Wearout</th>
                  <th>Health</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="diskList.length === 0">
                  <td colspan="7" class="text-muted text-center">No disks found</td>
                </tr>
                <tr v-for="disk in diskList" :key="disk.devpath || disk.dev">
                  <td><code class="text-sm">{{ disk.devpath || disk.dev }}</code></td>
                  <td class="text-sm">{{ disk.model || '—' }}</td>
                  <td class="text-sm">{{ disk.size ? formatBytes(disk.size) : '—' }}</td>
                  <td>
                    <span class="badge badge-info">{{ diskTypeLabel(disk) }}</span>
                  </td>
                  <td class="text-sm">{{ diskWearout(disk) }}</td>
                  <td>
                    <span v-if="diskHealth(disk) === 'PASSED'" class="badge badge-success">PASSED</span>
                    <span v-else-if="diskHealth(disk) === 'FAILED'" class="badge badge-danger">FAILED</span>
                    <span v-else class="text-muted text-sm">{{ diskHealth(disk) }}</span>
                  </td>
                  <td>
                    <button @click="openSmartModal(disk)" class="btn btn-outline btn-sm">SMART</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Services Tab ─── -->
      <div v-if="activeTab === 'services'">
        <div class="card">
          <div class="card-header">
            <h3>System Services</h3>
            <button @click="loadServices" class="btn btn-outline btn-sm" :disabled="loadingServices">
              {{ loadingServices ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <div v-if="loadingServices" class="loading-spinner"></div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Service Name</th>
                  <th>Description</th>
                  <th>State</th>
                  <th>Auto-start</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="servicesList.length === 0">
                  <td colspan="5" class="text-muted text-center">No services found</td>
                </tr>
                <tr v-for="svc in servicesList" :key="svc.name">
                  <td><code class="text-sm">{{ svc.name }}</code></td>
                  <td class="text-sm text-muted">{{ svc.desc || '—' }}</td>
                  <td>
                    <span :class="serviceBadgeClass(svc.state)">{{ svc.state || '—' }}</span>
                  </td>
                  <td>
                    <span v-if="svc.unitstate === 'enabled'" class="badge badge-success">Yes</span>
                    <span v-else class="text-muted text-sm">No</span>
                  </td>
                  <td>
                    <div class="flex gap-1">
                      <button
                        @click="doServiceAction(svc, 'start')"
                        class="btn btn-success btn-sm"
                        :disabled="svc.state === 'running' || serviceActioning[svc.name + ':start']"
                        title="Start">
                        {{ serviceActioning[svc.name + ':start'] ? '...' : 'Start' }}
                      </button>
                      <button
                        @click="doServiceAction(svc, 'stop')"
                        class="btn btn-outline btn-sm"
                        :disabled="svc.state !== 'running' || serviceActioning[svc.name + ':stop']"
                        title="Stop">
                        {{ serviceActioning[svc.name + ':stop'] ? '...' : 'Stop' }}
                      </button>
                      <button
                        @click="doServiceAction(svc, 'restart')"
                        class="btn btn-outline btn-sm"
                        :disabled="serviceActioning[svc.name + ':restart']"
                        title="Restart">
                        {{ serviceActioning[svc.name + ':restart'] ? '...' : 'Restart' }}
                      </button>
                      <button
                        @click="doServiceAction(svc, 'reload')"
                        class="btn btn-outline btn-sm"
                        :disabled="svc.state !== 'running' || serviceActioning[svc.name + ':reload']"
                        title="Reload">
                        {{ serviceActioning[svc.name + ':reload'] ? '...' : 'Reload' }}
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─── Certificates Tab ─── -->
      <div v-if="activeTab === 'certificates'">
        <div class="card">
          <div class="card-header">
            <h3>TLS Certificates</h3>
            <div class="flex gap-1">
              <button @click="toast.info('Use PVE web UI for ACME configuration')" class="btn btn-outline btn-sm">
                Order ACME Certificate
              </button>
              <button @click="loadCertificates" class="btn btn-outline btn-sm" :disabled="loadingCertificates">
                {{ loadingCertificates ? 'Loading...' : 'Refresh' }}
              </button>
            </div>
          </div>
          <div v-if="loadingCertificates" class="loading-spinner"></div>
          <div v-else-if="certificatesList.length === 0" class="text-muted text-center" style="padding: 2rem;">
            No certificates found
          </div>
          <div v-else style="padding: 1rem; display: flex; flex-direction: column; gap: 1rem;">
            <div v-for="cert in certificatesList" :key="cert.filename || cert.subject" class="cert-card">
              <div class="cert-row">
                <span class="cert-label">Subject</span>
                <span class="cert-value text-sm">{{ cert.subject || '—' }}</span>
              </div>
              <div class="cert-row">
                <span class="cert-label">Issuer</span>
                <span class="cert-value text-sm text-muted">{{ cert.issuer || '—' }}</span>
              </div>
              <div class="cert-row">
                <span class="cert-label">Fingerprint</span>
                <code class="cert-value text-sm" style="word-break:break-all;">{{ cert.fingerprint || '—' }}</code>
              </div>
              <div class="cert-row">
                <span class="cert-label">Expires</span>
                <span :class="certExpiryClass(cert.notafter)">{{ certExpiryLabel(cert.notafter) }}</span>
              </div>
              <div v-if="cert.san" class="cert-row">
                <span class="cert-label">SANs</span>
                <span class="cert-value text-sm text-muted">{{ Array.isArray(cert.san) ? cert.san.join(', ') : cert.san }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Terminal Tab ─── -->
      <div v-if="activeTab === 'terminal'">
        <div class="card">
          <div class="card-header">
            <h3>
              Node Shell — {{ node }}
              <span
                :class="termConnected ? 'badge badge-success ml-1' : (termConnecting ? 'badge badge-warning ml-1' : 'badge badge-danger ml-1')"
                style="font-size:0.7rem">
                {{ termConnected ? 'Connected' : (termConnecting ? 'Connecting...' : 'Disconnected') }}
              </span>
            </h3>
            <div class="flex gap-1">
              <button
                v-if="!termConnected && !termConnecting"
                @click="connectTerminal"
                class="btn btn-primary btn-sm">
                Connect
              </button>
              <button
                v-if="termConnected || termConnecting"
                @click="disconnectTerminal"
                class="btn btn-outline btn-sm">
                Disconnect
              </button>
              <button @click="clearTerminal" class="btn btn-outline btn-sm">Clear</button>
              <button @click="openTerminalWindow" class="btn btn-outline btn-sm" title="Open in new window">
                Pop Out
              </button>
            </div>
          </div>

          <!-- SSH fallback notice when WS unavailable -->
          <div v-if="termWsUnavailable" class="info-banner text-sm" style="gap:1rem;flex-direction:column;align-items:flex-start">
            <div>
              <strong>WebSocket terminal unavailable</strong> — connect directly via SSH instead:
            </div>
            <div class="flex gap-1 align-center">
              <code class="ssh-cmd">ssh root@{{ node }}</code>
              <button @click="copyToClipboard('ssh root@' + node, { toast: true })" class="btn btn-outline btn-sm">Copy</button>
            </div>
            <div class="text-muted" style="font-size:0.8rem">
              Note: The Proxmox node terminal requires the PVE termproxy WebSocket. Make sure your browser can reach
              <code>{{ pveWsOrigin }}</code>
            </div>
          </div>

          <!-- Terminal output window -->
          <div class="term-wrapper" ref="termWrapperRef">
            <div
              class="term-output"
              ref="termOutputRef"
              @click="focusTermInput"
            >
              <div v-for="(line, i) in termLines" :key="i" class="term-line" v-html="line"></div>
              <div v-if="termLines.length === 0 && !termConnected" class="term-placeholder">
                Click <strong>Connect</strong> to open a shell session on {{ node }}
              </div>
            </div>
          </div>

          <!-- Input row -->
          <div class="term-input-row">
            <span class="term-prompt">$</span>
            <input
              ref="termInputRef"
              v-model="termInput"
              class="term-input"
              placeholder="Type a command and press Enter..."
              :disabled="!termConnected"
              @keydown.enter="sendTermCommand"
              @keydown.up.prevent="termHistoryUp"
              @keydown.down.prevent="termHistoryDown"
              @keydown.ctrl.c.prevent="sendCtrlC"
              spellcheck="false"
              autocomplete="off"
              autocorrect="off"
            />
            <button
              @click="sendTermCommand"
              class="btn btn-outline btn-sm"
              :disabled="!termConnected || !termInput">
              Send
            </button>
          </div>
        </div>

        <!-- SSH Connect Info Panel -->
        <div class="card mt-2">
          <div class="card-header"><h3>SSH Connection Info</h3></div>
          <div class="card-body">
            <div class="flex gap-2 flex-wrap align-center">
              <div>
                <span class="text-sm text-muted">Command:</span>
                <code class="ssh-cmd ml-1">ssh root@{{ node }}</code>
              </div>
              <button @click="copyToClipboard('ssh root@' + node, { toast: true })" class="btn btn-outline btn-sm">
                Copy SSH Command
              </button>
              <button @click="openTerminal" class="btn btn-outline btn-sm">
                Open PVE Terminal Page
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Task Log Modal -->
    <div v-if="showTaskModal" class="modal" @click.self="showTaskModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>Task Log: {{ selectedTask?.type }} — {{ selectedTask?.id }}</h3>
          <button @click="showTaskModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="selectedTask?._loadingLog" class="loading-spinner"></div>
          <pre v-else class="task-log task-log-modal">{{ formatTaskLog(selectedTask?._log) }}</pre>
        </div>
      </div>
    </div>

    <!-- Edit Network Interface Modal -->
    <div v-if="showEditNetworkModal" class="modal" @click.self="showEditNetworkModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Edit Interface: <code>{{ editNetworkForm.iface }}</code></h3>
          <button @click="showEditNetworkModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">IP Address</label>
            <input v-model="editNetworkForm.address" class="form-control" placeholder="e.g. 192.168.1.1" />
          </div>
          <div class="form-group">
            <label class="form-label">Netmask</label>
            <input v-model="editNetworkForm.netmask" class="form-control" placeholder="e.g. 255.255.255.0" />
          </div>
          <div class="form-group">
            <label class="form-label">Gateway</label>
            <input v-model="editNetworkForm.gateway" class="form-control" placeholder="e.g. 192.168.1.254" />
          </div>
          <div v-if="editNetworkForm.type === 'bridge'" class="form-group">
            <label class="form-label">Bridge Ports</label>
            <input v-model="editNetworkForm.bridge_ports" class="form-control" placeholder="e.g. eth0 eth1" />
          </div>
          <div class="form-group">
            <label class="form-label">Comments</label>
            <input v-model="editNetworkForm.comments" class="form-control" placeholder="Optional description" />
          </div>
          <div class="form-group flex gap-1 align-center">
            <input type="checkbox" v-model="editNetworkForm.autostart" id="edit-net-autostart" />
            <label for="edit-net-autostart" class="form-label" style="margin:0">Autostart</label>
          </div>
          <div class="flex gap-1 mt-2" style="justify-content:flex-end">
            <button @click="showEditNetworkModal = false" class="btn btn-outline">Cancel</button>
            <button @click="saveEditNetworkIface" class="btn btn-primary" :disabled="savingNetwork">
              {{ savingNetwork ? 'Saving...' : 'Save Changes' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Network Interface Modal -->
    <div v-if="showCreateNetworkModal" class="modal" @click.self="showCreateNetworkModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Network Interface</h3>
          <button @click="showCreateNetworkModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Interface Name *</label>
            <input v-model="newNetworkForm.iface" class="form-control" placeholder="e.g. vmbr1, bond0, vlan10" />
          </div>
          <div class="form-group">
            <label class="form-label">Type *</label>
            <select v-model="newNetworkForm.type" class="form-control">
              <option value="bridge">Bridge</option>
              <option value="bond">Bond</option>
              <option value="vlan">VLAN</option>
              <option value="eth">Ethernet</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">IP Address</label>
            <input v-model="newNetworkForm.address" class="form-control" placeholder="e.g. 192.168.1.1" />
          </div>
          <div class="form-group">
            <label class="form-label">Netmask</label>
            <input v-model="newNetworkForm.netmask" class="form-control" placeholder="e.g. 255.255.255.0" />
          </div>
          <div class="form-group">
            <label class="form-label">Gateway</label>
            <input v-model="newNetworkForm.gateway" class="form-control" placeholder="e.g. 192.168.1.254" />
          </div>
          <div v-if="newNetworkForm.type === 'bridge'" class="form-group">
            <label class="form-label">Bridge Ports</label>
            <input v-model="newNetworkForm.bridge_ports" class="form-control" placeholder="e.g. eth0 eth1" />
          </div>
          <div v-if="newNetworkForm.type === 'bond'" class="form-group">
            <label class="form-label">Bond Mode</label>
            <select v-model="newNetworkForm.bond_mode" class="form-control">
              <option value="active-backup">active-backup</option>
              <option value="balance-rr">balance-rr</option>
              <option value="balance-xor">balance-xor</option>
              <option value="broadcast">broadcast</option>
              <option value="802.3ad">802.3ad (LACP)</option>
              <option value="balance-tlb">balance-tlb</option>
              <option value="balance-alb">balance-alb</option>
            </select>
          </div>
          <div v-if="newNetworkForm.type === 'vlan'" class="form-group">
            <label class="form-label">VLAN ID</label>
            <input v-model="newNetworkForm.vlan_id" class="form-control" type="number" placeholder="e.g. 100" />
          </div>
          <div class="form-group">
            <label class="form-label">Comments</label>
            <input v-model="newNetworkForm.comments" class="form-control" placeholder="Optional description" />
          </div>
          <div class="form-group flex gap-1 align-center">
            <input type="checkbox" v-model="newNetworkForm.autostart" id="net-autostart" />
            <label for="net-autostart" class="form-label" style="margin:0">Autostart</label>
          </div>
          <div class="flex gap-1 mt-2" style="justify-content:flex-end">
            <button @click="showCreateNetworkModal = false" class="btn btn-outline">Cancel</button>
            <button @click="createNetworkIface" class="btn btn-primary" :disabled="creatingNetwork">
              {{ creatingNetwork ? 'Creating...' : 'Create Interface' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- SMART Data Modal -->
    <div v-if="showSmartModal" class="modal" @click.self="showSmartModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>SMART Data: {{ smartDisk?.devpath || smartDisk?.dev }}</h3>
          <button @click="showSmartModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="loadingSmart" class="loading-spinner"></div>
          <div v-else-if="smartData?.error" class="text-muted text-sm">{{ smartData.error }}</div>
          <template v-else-if="smartData">
            <div class="flex gap-2 mb-2 text-sm">
              <span v-if="smartData.health"><strong>Health:</strong>
                <span :class="smartData.health === 'PASSED' ? 'badge badge-success ml-1' : 'badge badge-danger ml-1'">
                  {{ smartData.health }}
                </span>
              </span>
              <span v-if="smartData.type"><strong>Type:</strong> {{ smartData.type }}</span>
            </div>
            <div v-if="smartData.attributes && smartData.attributes.length" class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Attribute</th>
                    <th>Value</th>
                    <th>Worst</th>
                    <th>Threshold</th>
                    <th>Raw</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="attr in smartData.attributes" :key="attr.id || attr.name">
                    <td class="text-sm text-muted">{{ attr.id }}</td>
                    <td class="text-sm">{{ attr.name }}</td>
                    <td class="text-sm">{{ attr.value }}</td>
                    <td class="text-sm">{{ attr.worst }}</td>
                    <td class="text-sm">{{ attr.threshold }}</td>
                    <td class="text-sm text-muted">{{ attr.raw }}</td>
                    <td>
                      <span v-if="attr.flags && attr.flags.includes('f')" class="badge badge-danger">FAIL</span>
                      <span v-else class="badge badge-success">OK</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else-if="smartData.text" class="text-sm">
              <pre class="task-log" style="max-height:400px">{{ smartData.text }}</pre>
            </div>
            <div v-else class="text-muted text-sm">No SMART attributes available.</div>
          </template>
          <div v-else class="text-muted text-sm">No data.</div>
        </div>
      </div>
    </div>

    <!-- Create Backup Schedule Modal -->
    <div v-if="showCreateBackupModal" class="modal" @click.self="showCreateBackupModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Backup Schedule</h3>
          <button @click="showCreateBackupModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Storage *</label>
            <input v-model="newBackupForm.storage" class="form-control" placeholder="e.g. local, backup-store" />
            <span class="text-sm text-muted">Storage ID where backups will be saved</span>
          </div>
          <div class="form-group">
            <label class="form-label">Node</label>
            <input v-model="newBackupForm.node" class="form-control" :placeholder="node" />
            <span class="text-sm text-muted">Leave blank to back up all nodes</span>
          </div>
          <div class="form-group">
            <label class="form-label">Schedule (cron)</label>
            <input v-model="newBackupForm.schedule" class="form-control" placeholder="e.g. daily, 0 2 * * *" />
            <span class="text-sm text-muted">Systemd calendar format or cron expression</span>
          </div>
          <div class="form-group">
            <label class="form-label">Compression</label>
            <select v-model="newBackupForm.compress" class="form-control">
              <option value="zstd">zstd (recommended)</option>
              <option value="lzo">lzo (fast)</option>
              <option value="gzip">gzip</option>
              <option value="0">None</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Mode</label>
            <select v-model="newBackupForm.mode" class="form-control">
              <option value="snapshot">snapshot</option>
              <option value="suspend">suspend</option>
              <option value="stop">stop</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Mail Notification</label>
            <select v-model="newBackupForm.mailnotification" class="form-control">
              <option value="failure">On failure only</option>
              <option value="always">Always</option>
            </select>
          </div>
          <div class="form-group flex gap-1 align-center">
            <input type="checkbox" v-model="newBackupForm.enabled" :true-value="1" :false-value="0" id="backup-enabled" />
            <label for="backup-enabled" class="form-label" style="margin:0">Enabled</label>
          </div>
          <div class="flex gap-1 mt-2" style="justify-content:flex-end">
            <button @click="showCreateBackupModal = false" class="btn btn-outline">Cancel</button>
            <button @click="createBackupSchedule" class="btn btn-primary" :disabled="creatingBackup">
              {{ creatingBackup ? 'Creating...' : 'Create Schedule' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Tooltip, Legend, Title, Filler
} from 'chart.js'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import { formatBytes, formatUptime, formatTaskType } from '@/utils/proxmox'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { copyToClipboard } from '@/utils/clipboard'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Title, Filler)

const route = useRoute()
const router = useRouter()
const toast = useToast()

const hostId = computed(() => route.params.hostId)
const node = computed(() => route.params.node)

// Host name for breadcrumb
const hostName = ref(null)
const fetchHostName = async () => {
  try {
    const res = await api.proxmox.getHost(hostId.value)
    hostName.value = res.data?.name || null
  } catch {
    // non-critical — breadcrumb falls back to hostId
  }
}

// Core state
const nodeStatus = ref(null)
const loadingInit = ref(true)
const nodeLoadError = ref(null)
const activeTab = ref('overview')

// RRD
const rrdData = ref(null)
const rrdLoaded = ref(false)
const rrdTimeframe = ref('hour')

// Live disk I/O (VM-aggregate fallback when Proxmox RRD has no disk data)
const diskIoLive = ref(null)   // { read: bytes/s, write: bytes/s } or null
const fmtBps = (b) => {
  if (!b || !isFinite(b)) return '0 B/s'
  if (b >= 1e9) return (b / 1e9).toFixed(1) + ' GB/s'
  if (b >= 1e6) return (b / 1e6).toFixed(1) + ' MB/s'
  if (b >= 1e3) return (b / 1e3).toFixed(0) + ' KB/s'
  return b.toFixed(0) + ' B/s'
}

// Guests
const guests = ref([])
const loadingGuests = ref(false)
const guestsError = ref(null)
const guestActioning = ref({})

// Storage
const storageList = ref([])
const loadingStorage = ref(false)

// Network
const networkIfaces = ref([])
const loadingNetwork = ref(false)
const applyingNetwork = ref(false)
const networkIfaceDeleting = ref({})
const showCreateNetworkModal = ref(false)
const newNetworkForm = ref({
  iface: '',
  type: 'bridge',
  address: '',
  netmask: '',
  gateway: '',
  bridge_ports: '',
  bond_mode: 'active-backup',
  vlan_id: '',
  autostart: true,
  comments: '',
})
const creatingNetwork = ref(false)

// Backup Schedules
const backupSchedules = ref([])
const loadingBackups = ref(false)
const backupDeleting = ref({})
const showCreateBackupModal = ref(false)
const newBackupForm = ref({
  node: '',
  storage: '',
  schedule: 'daily',
  compress: 'zstd',
  mode: 'snapshot',
  enabled: 1,
  mailnotification: 'failure',
})
const creatingBackup = ref(false)

// Tasks
const tasks = ref([])
const loadingTasks = ref(false)
const showTaskModal = ref(false)
const selectedTask = ref(null)

// Disk Health
const diskList = ref([])
const loadingDisks = ref(false)
const showSmartModal = ref(false)
const smartDisk = ref(null)
const smartData = ref(null)
const loadingSmart = ref(false)

// Services
const servicesList = ref([])
const loadingServices = ref(false)
const serviceActioning = ref({})

// Certificates
const certificatesList = ref([])
const loadingCertificates = ref(false)

// APT / Updates
const aptUpdates = ref([])
const aptVersions = ref([])
const loadingAptUpdates = ref(false)
const loadingAptVersions = ref(false)
const refreshingPackages = ref(false)
const upgradingAll = ref(false)
const upgradingSelected = ref(false)
const upgradeTaskUpid = ref(null)
const upgradeTaskStatus = ref(null)
const upgradeTaskLog = ref([])
const aptSearchQuery = ref('')
const selectedPackages = ref(new Set())
let upgradeTaskPollInterval = null

// Terminal
const termConnected = ref(false)
const termConnecting = ref(false)
const termWsUnavailable = ref(false)
const termLines = ref([])
const termInput = ref('')
const termHistory = ref([])
const termHistoryIndex = ref(-1)
const termOutputRef = ref(null)
const termInputRef = ref(null)
const termWrapperRef = ref(null)
let termWs = null
let termTicket = null

// Hardware (PCI / USB)
const pciDevices = ref([])
const usbDevices = ref([])
const loadingPci = ref(false)
const loadingUsb = ref(false)

// ZFS Pools
const zfsPools = ref([])
const loadingZfs = ref(false)
const zfsError = ref(null)

// Edit Network Interface
const showEditNetworkModal = ref(false)
const editNetworkForm = ref({
  iface: '',
  type: '',
  address: '',
  netmask: '',
  gateway: '',
  bridge_ports: '',
  autostart: false,
  comments: '',
})
const savingNetwork = ref(false)

// Polling
let pollInterval = null

const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'guests', label: 'VMs & Containers' },
  { id: 'storage', label: 'Storage' },
  { id: 'network', label: 'Network' },
  { id: 'updates', label: 'APT Updates' },
  { id: 'backups', label: 'Backup Schedules' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'disks', label: 'Disk Health' },
  { id: 'hardware', label: 'Hardware' },
  { id: 'services', label: 'Services' },
  { id: 'certificates', label: 'Certificates' },
  { id: 'terminal', label: 'Terminal' },
]

// ── Computed ──────────────────────────────────────────────────────────────────

const nodeCpuPct = computed(() => {
  if (!nodeStatus.value?.cpu) return 0
  const val = nodeStatus.value.cpu
  return val > 1 ? parseFloat(val.toFixed(1)) : parseFloat((val * 100).toFixed(1))
})

const nodeRamPct = computed(() => {
  const mem = nodeStatus.value?.memory
  if (!mem?.total || !mem?.used) return 0
  return parseFloat(((mem.used / mem.total) * 100).toFixed(1))
})

const makeLabels = (data) =>
  (data || []).map(d => d.time ? new Date(d.time * 1000).toLocaleTimeString() : '')

const cpuChartData = computed(() => {
  if (!rrdData.value?.length) return null
  return {
    labels: makeLabels(rrdData.value),
    datasets: [{
      label: 'CPU %',
      data: rrdData.value.map(d => d.cpu != null ? parseFloat((d.cpu * 100).toFixed(1)) : null),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.1)',
      fill: true, tension: 0.3, pointRadius: 0,
    }]
  }
})

const memChartData = computed(() => {
  if (!rrdData.value?.length) return null
  return {
    labels: makeLabels(rrdData.value),
    datasets: [{
      label: 'Memory %',
      data: rrdData.value.map(d => {
        if (d.memtotal && d.memused) return parseFloat(((d.memused / d.memtotal) * 100).toFixed(1))
        return null
      }),
      borderColor: '#10b981',
      backgroundColor: 'rgba(16,185,129,0.1)',
      fill: true, tension: 0.3, pointRadius: 0,
    }]
  }
})

const netChartData = computed(() => {
  if (!rrdData.value?.length) return null
  return {
    labels: makeLabels(rrdData.value),
    datasets: [
      {
        label: 'In (bytes/s)',
        data: rrdData.value.map(d => d.netin ?? null),
        borderColor: '#06b6d4',
        backgroundColor: 'rgba(6,182,212,0.05)',
        fill: false, tension: 0.3, pointRadius: 0,
      },
      {
        label: 'Out (bytes/s)',
        data: rrdData.value.map(d => d.netout ?? null),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.05)',
        fill: false, tension: 0.3, pointRadius: 0,
      },
    ]
  }
})

const diskChartData = computed(() => {
  if (!rrdData.value?.length) return null
  const hasData = rrdData.value.some(d => d.diskread != null || d.diskwrite != null)
  if (!hasData) return null
  return {
    labels: makeLabels(rrdData.value),
    datasets: [
      {
        label: 'Read (bytes/s)',
        data: rrdData.value.map(d => d.diskread ?? null),
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139,92,246,0.05)',
        fill: false, tension: 0.3, pointRadius: 0,
      },
      {
        label: 'Write (bytes/s)',
        data: rrdData.value.map(d => d.diskwrite ?? null),
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239,68,68,0.05)',
        fill: false, tension: 0.3, pointRadius: 0,
      },
    ]
  }
})

const lineChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { maxTicksLimit: 8, color: '#9ca3af' }, grid: { color: '#374151' } },
    y: { min: 0, max: 100, ticks: { color: '#9ca3af', callback: v => v + '%' }, grid: { color: '#374151' } }
  }
}

const bytesChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: true, labels: { color: '#9ca3af', boxWidth: 12 } } },
  scales: {
    x: { ticks: { maxTicksLimit: 8, color: '#9ca3af' }, grid: { color: '#374151' } },
    y: { min: 0, ticks: { color: '#9ca3af', callback: v => formatBytes(v) + '/s' }, grid: { color: '#374151' } }
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const NODE_TIMEOUT_MS = 10_000

function withNodeTimeout(promise, ms = NODE_TIMEOUT_MS) {
  let timer
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error('timeout')), ms)
  })
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer))
}

async function retryOnce(fn) {
  try {
    return await fn()
  } catch (e) {
    await new Promise(r => setTimeout(r, 1000))
    return fn()
  }
}

// ── Data Loading ──────────────────────────────────────────────────────────────

const loadNodeStatus = async () => {
  const res = await withNodeTimeout(api.pveNode.nodeStatus(hostId.value, node.value))
  nodeStatus.value = res.data
}

const loadRrd = async () => {
  try {
    const res = await withNodeTimeout(
      api.pveNode.nodeRrdData(hostId.value, node.value, { timeframe: rrdTimeframe.value, cf: 'AVERAGE' })
    )
    rrdData.value = res.data
  } catch (e) {
    console.warn('RRD failed', e)
  } finally {
    rrdLoaded.value = true
  }
  // If RRD has no disk data, fetch live aggregate from VM counters (two-call delta)
  const hasRrdDisk = rrdData.value?.some(d => d.diskread != null || d.diskwrite != null)
  if (!hasRrdDisk) {
    try {
      await api.pveNode.diskIoRates(hostId.value)  // prime the counter
      await new Promise(r => setTimeout(r, 3000))
      const r2 = await api.pveNode.diskIoRates(hostId.value)
      const nodeEntry = (r2.data || []).find(n => n.node === node.value)
      if (nodeEntry) diskIoLive.value = { read: nodeEntry.read || 0, write: nodeEntry.write || 0 }
    } catch { /* ignore */ }
  }
}

const loadGuests = async () => {
  loadingGuests.value = true
  guestsError.value = null
  try {
    const [vmRes, ctRes] = await retryOnce(() => Promise.all([
      api.pveNode.nodeVms(hostId.value, node.value).catch(() => ({ data: { vms: [], containers: [] } })),
      api.pveNode.listContainers(hostId.value, node.value).catch(() => ({ data: [] })),
    ]))
    // nodeVms returns {vms, containers} shape; listContainers returns a bare array
    const vmData = vmRes.data
    const vmsArray = Array.isArray(vmData) ? vmData : (vmData?.vms ?? [])
    const ctData = ctRes.data
    const ctsArray = Array.isArray(ctData) ? ctData : (ctData?.containers ?? [])
    guests.value = [
      ...vmsArray.map(v => ({ ...v, type: 'qemu' })),
      ...ctsArray.map(c => ({ ...c, type: 'lxc' })),
    ].sort((a, b) => a.vmid - b.vmid)
  } catch (e) {
    console.warn('Guests load failed', e)
    guestsError.value = e.response?.data?.detail || e.message || 'Failed to load guests'
    toast.error('Failed to load guests for this node')
  } finally {
    loadingGuests.value = false
  }
}

const loadStorage = async () => {
  loadingStorage.value = true
  try {
    const res = await retryOnce(() => api.pveNode.listStorage(hostId.value, node.value))
    storageList.value = res.data || []
  } catch (e) {
    console.warn('Storage failed', e)
    toast.error('Failed to load storage pools')
  } finally {
    loadingStorage.value = false
  }
}

const loadNetwork = async () => {
  loadingNetwork.value = true
  try {
    const res = await retryOnce(() => api.pveNode.listNetwork(hostId.value, node.value))
    networkIfaces.value = res.data || []
  } catch (e) {
    console.warn('Network failed', e)
    toast.error('Failed to load network interfaces')
  } finally {
    loadingNetwork.value = false
  }
}

const loadTasks = async () => {
  loadingTasks.value = true
  try {
    const res = await retryOnce(() => api.pveNode.listTasks(hostId.value, node.value, { limit: 50 }))
    tasks.value = (res.data || []).map(t => ({
      ...t,
      _expanded: false,
      _log: null,
      _loadingLog: false,
      _stopping: false,
    }))
  } catch (e) {
    console.warn('Tasks failed', e)
    toast.error('Failed to load task history')
  } finally {
    loadingTasks.value = false
  }
}

const loadAll = async () => {
  if (!hostId.value || hostId.value === 'undefined' || !node.value || node.value === 'undefined') {
    nodeLoadError.value = 'Invalid navigation — missing host or node parameters'
    loadingInit.value = false
    return
  }
  loadingInit.value = true
  nodeLoadError.value = null
  let lastErr = null
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      await loadNodeStatus()
      await loadRrd()
      lastErr = null
      break
    } catch (e) {
      lastErr = e
      if (attempt < 2) await new Promise(r => setTimeout(r, 1500))
    }
  }
  if (lastErr) {
    console.error('Failed to load node detail', lastErr)
    nodeLoadError.value = lastErr.message === 'timeout'
      ? 'Request timed out — the node may be unreachable'
      : (lastErr.response?.data?.detail || lastErr.message || 'Unknown error')
    toast.error(`Failed to load node ${node.value}`)
  }
  loadingInit.value = false
}

// ── Tab Management ─────────────────────────────────────────────────────────────

const switchTab = (tab) => {
  activeTab.value = tab
  if (tab === 'guests') loadGuests()
  if (tab === 'storage') { loadStorage(); loadZfsPools() }
  if (tab === 'network') loadNetwork()
  if (tab === 'backups') loadBackupSchedules()
  if (tab === 'tasks') loadTasks()
  if (tab === 'disks') loadDisks()
  if (tab === 'services') loadServices()
  if (tab === 'certificates') loadCertificates()
  if (tab === 'overview') { loadNodeStatus(); loadRrd() }
  if (tab === 'updates') { loadAptUpdates(); loadAptVersions() }
  if (tab === 'hardware') { loadPciDevices(); loadUsbDevices() }
  if (tab === 'terminal') { /* auto-connect on tab switch */ }
  // Disconnect terminal when leaving tab
  if (tab !== 'terminal' && termConnected.value) disconnectTerminal()
}

// ── Polling ────────────────────────────────────────────────────────────────────

const startPolling = () => {
  pollInterval = setInterval(() => {
    if (activeTab.value === 'overview') {
      loadNodeStatus()
    }
  }, 10000)
}

// ── Guest Actions ──────────────────────────────────────────────────────────────

const navigateToGuest = (guest) => {
  if (guest.type === 'qemu') {
    router.push(`/proxmox/${hostId.value}/nodes/${node.value}/vms/${guest.vmid}`)
  } else {
    router.push(`/proxmox/${hostId.value}/nodes/${node.value}/containers/${guest.vmid}`)
  }
}

const guestAction = async (guest, action) => {
  const key = `${guest.type}-${guest.vmid}`
  guestActioning.value[key] = true
  try {
    if (guest.type === 'qemu') {
      if (action === 'start') await api.pveVm.start(hostId.value, node.value, guest.vmid)
      else await api.pveVm.shutdown(hostId.value, node.value, guest.vmid)
    } else {
      await api.pveNode.containerAction(hostId.value, node.value, guest.vmid, action)
    }
    toast.success(`${guest.name || guest.vmid}: ${action} initiated`)
    setTimeout(loadGuests, 2000)
  } catch (e) {
    console.error(e)
  } finally {
    delete guestActioning.value[key]
  }
}

// ── Storage ────────────────────────────────────────────────────────────────────

const browseStorage = (storageName) => {
  router.push(`/proxmox/${hostId.value}/nodes/${node.value}/storage?storage=${storageName}`)
}

const usagePct = (s) => {
  if (!s.total || !s.used) return 0
  return Math.min(100, Math.round((s.used / s.total) * 100))
}

const usageColor = (s) => {
  const pct = usagePct(s)
  if (pct > 90) return '#dc2626'
  if (pct > 75) return '#f59e0b'
  return '#2563eb'
}

// ── Network ────────────────────────────────────────────────────────────────────

const applyNetwork = async () => {
  if (!confirm('Apply network configuration? This may briefly interrupt connectivity on this node.')) return
  applyingNetwork.value = true
  try {
    await api.pveNode.applyNetwork(hostId.value, node.value)
    toast.success('Network configuration applied')
    await loadNetwork()
  } catch (e) {
    console.error(e)
  } finally {
    applyingNetwork.value = false
  }
}

const resetNetworkForm = () => {
  newNetworkForm.value = {
    iface: '',
    type: 'bridge',
    address: '',
    netmask: '',
    gateway: '',
    bridge_ports: '',
    bond_mode: 'active-backup',
    vlan_id: '',
    autostart: true,
    comments: '',
  }
}

const createNetworkIface = async () => {
  if (!newNetworkForm.value.iface) {
    toast.error('Interface name is required')
    return
  }
  creatingNetwork.value = true
  try {
    const payload = {
      iface: newNetworkForm.value.iface,
      type: newNetworkForm.value.type,
      autostart: newNetworkForm.value.autostart ? 1 : 0,
    }
    if (newNetworkForm.value.address) payload.address = newNetworkForm.value.address
    if (newNetworkForm.value.netmask) payload.netmask = newNetworkForm.value.netmask
    if (newNetworkForm.value.gateway) payload.gateway = newNetworkForm.value.gateway
    if (newNetworkForm.value.comments) payload.comments = newNetworkForm.value.comments
    if (newNetworkForm.value.type === 'bridge' && newNetworkForm.value.bridge_ports) {
      payload['bridge-ports'] = newNetworkForm.value.bridge_ports
    }
    if (newNetworkForm.value.type === 'bond' && newNetworkForm.value.bond_mode) {
      payload.bond_mode = newNetworkForm.value.bond_mode
    }
    if (newNetworkForm.value.type === 'vlan' && newNetworkForm.value.vlan_id) {
      payload['vlan-id'] = newNetworkForm.value.vlan_id
    }
    await api.pveNode.createNetwork(hostId.value, node.value, payload)
    toast.success(`Interface ${payload.iface} created (apply changes to activate)`)
    showCreateNetworkModal.value = false
    resetNetworkForm()
    await loadNetwork()
  } catch (e) {
    toast.error('Failed to create interface: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
    console.error(e)
  } finally {
    creatingNetwork.value = false
  }
}

const deleteNetworkIface = async (iface) => {
  if (!confirm(`Delete interface "${iface.iface}"? Apply network changes afterwards to make it permanent.`)) return
  networkIfaceDeleting.value[iface.iface] = true
  try {
    await api.pveNode.deleteNetwork(hostId.value, node.value, iface.iface)
    toast.success(`Interface ${iface.iface} deleted (apply changes to activate)`)
    await loadNetwork()
  } catch (e) {
    toast.error('Failed to delete interface: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
    console.error(e)
  } finally {
    delete networkIfaceDeleting.value[iface.iface]
  }
}

const cidrFromNetmask = (netmask) => {
  if (!netmask) return ''
  // If already a CIDR prefix number, return as-is
  if (/^\d+$/.test(netmask)) return netmask
  const parts = netmask.split('.')
  if (parts.length !== 4) return netmask
  return parts.reduce((acc, octet) => {
    const n = parseInt(octet, 10)
    let bits = 0
    for (let i = 7; i >= 0; i--) { if (n & (1 << i)) bits++; else break }
    return acc + bits
  }, 0).toString()
}

// ── Backup Schedules ───────────────────────────────────────────────────────────

const loadBackupSchedules = async () => {
  loadingBackups.value = true
  try {
    const res = await api.pveNode.listBackupSchedules(hostId.value)
    backupSchedules.value = res.data || []
  } catch (e) {
    console.warn('Backup schedules failed', e)
    backupSchedules.value = []
  } finally {
    loadingBackups.value = false
  }
}

const resetBackupForm = () => {
  newBackupForm.value = {
    node: node.value,
    storage: '',
    schedule: 'daily',
    compress: 'zstd',
    mode: 'snapshot',
    enabled: 1,
    mailnotification: 'failure',
  }
}

const createBackupSchedule = async () => {
  if (!newBackupForm.value.storage) {
    toast.error('Storage is required')
    return
  }
  creatingBackup.value = true
  try {
    const payload = {
      storage: newBackupForm.value.storage,
      schedule: newBackupForm.value.schedule,
      compress: newBackupForm.value.compress,
      mode: newBackupForm.value.mode,
      enabled: newBackupForm.value.enabled,
      mailnotification: newBackupForm.value.mailnotification,
    }
    if (newBackupForm.value.node) payload.node = newBackupForm.value.node
    await api.pveNode.createBackupSchedule(hostId.value, payload)
    toast.success('Backup schedule created')
    showCreateBackupModal.value = false
    resetBackupForm()
    await loadBackupSchedules()
  } catch (e) {
    toast.error('Failed to create schedule: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
    console.error(e)
  } finally {
    creatingBackup.value = false
  }
}

const deleteBackupSchedule = async (sched) => {
  if (!confirm(`Delete backup schedule "${sched.id}"?`)) return
  backupDeleting.value[sched.id] = true
  try {
    await api.pveNode.deleteBackupSchedule(hostId.value, sched.id)
    toast.success('Backup schedule deleted')
    await loadBackupSchedules()
  } catch (e) {
    toast.error('Failed to delete schedule: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
    console.error(e)
  } finally {
    delete backupDeleting.value[sched.id]
  }
}

// ── Tasks ──────────────────────────────────────────────────────────────────────

const toggleTaskLog = async (task) => {
  task._expanded = !task._expanded
  if (task._expanded && !task._log) {
    task._loadingLog = true
    try {
      const res = await api.pveNode.taskLog(hostId.value, node.value, encodeURIComponent(task.upid))
      task._log = res.data || []
    } catch (e) {
      task._log = [{ t: 'Failed to load log: ' + (e.message || 'unknown error') }]
    } finally {
      task._loadingLog = false
    }
  }
}

const stopTask = async (task) => {
  if (!confirm(`Stop task ${task.type}?`)) return
  task._stopping = true
  try {
    await api.pveNode.stopTask(hostId.value, node.value, encodeURIComponent(task.upid))
    toast.success('Task stop requested')
    setTimeout(loadTasks, 1500)
  } catch (e) {
    console.error(e)
  } finally {
    task._stopping = false
  }
}

const formatTaskLog = (log) => {
  if (!log || !Array.isArray(log)) return 'No log data available.'
  return log.map(l => l.t || l.text || JSON.stringify(l)).join('\n')
}

const taskBadgeClass = (status) => {
  if (status === 'OK') return 'badge badge-success'
  if (!status || status === 'running') return 'badge badge-warning'
  return 'badge badge-danger'
}

const taskDuration = (task) => {
  if (!task.starttime) return '—'
  const end = task.endtime || Math.floor(Date.now() / 1000)
  const secs = end - task.starttime
  if (secs < 60) return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
  return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
}

// ── Disk Health ────────────────────────────────────────────────────────────────

const loadDisks = async () => {
  loadingDisks.value = true
  try {
    const res = await api.pveNode.listDisks(hostId.value, node.value)
    diskList.value = res.data || []
  } catch (e) {
    console.warn('Disk list failed', e)
    diskList.value = []
  } finally {
    loadingDisks.value = false
  }
}

const openSmartModal = async (disk) => {
  smartDisk.value = disk
  smartData.value = null
  showSmartModal.value = true
  loadingSmart.value = true
  try {
    const res = await api.pveNode.getSmartData(hostId.value, node.value, disk.devpath || disk.dev)
    smartData.value = res.data
  } catch (e) {
    smartData.value = { error: e?.response?.data?.detail || e.message || 'Failed to load SMART data' }
  } finally {
    loadingSmart.value = false
  }
}

const diskTypeLabel = (disk) => {
  if (disk.type) return disk.type.toUpperCase()
  if (disk.rpm === 0 || disk.rpm === '0') return 'SSD'
  if (disk.rpm > 0) return 'HDD'
  return '—'
}

const diskWearout = (disk) => {
  if (disk.wearout != null && disk.wearout !== '') return disk.wearout + '%'
  return '—'
}

const diskHealth = (disk) => {
  if (disk.health) return disk.health
  return '—'
}

// ── Services ───────────────────────────────────────────────────────────────────

const loadServices = async () => {
  loadingServices.value = true
  try {
    const res = await api.pveNode.listServices(hostId.value, node.value)
    servicesList.value = (res.data || []).sort((a, b) => (a.name || '').localeCompare(b.name || ''))
  } catch (e) {
    console.warn('Services load failed', e)
    servicesList.value = []
  } finally {
    loadingServices.value = false
  }
}

const doServiceAction = async (svc, cmd) => {
  const key = svc.name + ':' + cmd
  serviceActioning.value[key] = true
  try {
    await api.pveNode.serviceAction(hostId.value, node.value, svc.name, cmd)
    toast.success(`${svc.name}: ${cmd} requested`)
    setTimeout(loadServices, 1500)
  } catch (e) {
    console.error(e)
  } finally {
    delete serviceActioning.value[key]
  }
}

const serviceBadgeClass = (state) => {
  if (state === 'running') return 'badge badge-success'
  if (state === 'failed') return 'badge badge-danger'
  return 'badge badge-secondary'
}

// ── Certificates ───────────────────────────────────────────────────────────────

const loadCertificates = async () => {
  loadingCertificates.value = true
  try {
    const res = await api.pveNode.listCertificates(hostId.value, node.value)
    certificatesList.value = res.data || []
  } catch (e) {
    console.warn('Certificates load failed', e)
    certificatesList.value = []
  } finally {
    loadingCertificates.value = false
  }
}

const certExpiryClass = (notafter) => {
  if (!notafter) return ''
  const now = Date.now() / 1000
  const diff = notafter - now
  const days = diff / 86400
  if (days < 30) return 'badge badge-danger'
  if (days < 90) return 'badge badge-warning'
  return 'badge badge-success'
}

const certExpiryLabel = (notafter) => {
  if (!notafter) return '—'
  const d = new Date(notafter * 1000)
  const now = Date.now() / 1000
  const days = Math.floor((notafter - now) / 86400)
  const dateStr = d.toLocaleDateString()
  if (days < 0) return `${dateStr} (expired)`
  return `${dateStr} (${days}d)`
}

// ── APT / Updates ──────────────────────────────────────────────────────────────

const filteredAptUpdates = computed(() => {
  const q = aptSearchQuery.value.trim().toLowerCase()
  if (!q) return aptUpdates.value
  return aptUpdates.value.filter(pkg => {
    const name = (pkg.Package || pkg.package || '').toLowerCase()
    const desc = (pkg.Description || pkg.description || '').toLowerCase()
    const section = (pkg.Section || pkg.section || '').toLowerCase()
    return name.includes(q) || desc.includes(q) || section.includes(q)
  })
})

const allFilteredSelected = computed(() => {
  if (filteredAptUpdates.value.length === 0) return false
  return filteredAptUpdates.value.every(pkg => selectedPackages.value.has(pkg.Package || pkg.package))
})

const someFilteredSelected = computed(() => {
  return filteredAptUpdates.value.some(pkg => selectedPackages.value.has(pkg.Package || pkg.package))
})

const toggleAllFiltered = () => {
  const newSet = new Set(selectedPackages.value)
  if (allFilteredSelected.value) {
    filteredAptUpdates.value.forEach(pkg => newSet.delete(pkg.Package || pkg.package))
  } else {
    filteredAptUpdates.value.forEach(pkg => newSet.add(pkg.Package || pkg.package))
  }
  selectedPackages.value = newSet
}

const togglePackage = (name) => {
  const newSet = new Set(selectedPackages.value)
  if (newSet.has(name)) newSet.delete(name)
  else newSet.add(name)
  selectedPackages.value = newSet
}

const selectAllPackages = () => {
  selectedPackages.value = new Set(aptUpdates.value.map(p => p.Package || p.package))
}

const deselectAllPackages = () => {
  selectedPackages.value = new Set()
}

const loadAptUpdates = async () => {
  loadingAptUpdates.value = true
  try {
    const res = await api.pveNode.aptListUpdates(hostId.value, node.value)
    aptUpdates.value = res.data || []
    // Clear selection for packages no longer present
    const names = new Set(aptUpdates.value.map(p => p.Package || p.package))
    selectedPackages.value = new Set([...selectedPackages.value].filter(n => names.has(n)))
  } catch (e) {
    console.warn('APT updates failed', e)
    aptUpdates.value = []
  } finally {
    loadingAptUpdates.value = false
  }
}

const loadAptVersions = async () => {
  loadingAptVersions.value = true
  try {
    const res = await api.pveNode.aptInstalledVersions(hostId.value, node.value)
    aptVersions.value = res.data || []
  } catch (e) {
    console.warn('APT versions failed', e)
    aptVersions.value = []
  } finally {
    loadingAptVersions.value = false
  }
}

const startUpgradeTaskPolling = (upid) => {
  upgradeTaskStatus.value = 'running'
  upgradeTaskLog.value = []
  let logOffset = 0
  if (upgradeTaskPollInterval) clearInterval(upgradeTaskPollInterval)
  upgradeTaskPollInterval = setInterval(async () => {
    try {
      // Fetch log lines since last offset
      const logRes = await api.pveNode.taskLog(hostId.value, node.value, encodeURIComponent(upid))
      const lines = logRes.data?.lines || []
      if (lines.length > logOffset) {
        upgradeTaskLog.value = [...upgradeTaskLog.value, ...lines.slice(logOffset)]
        logOffset = lines.length
      }
      // Fetch task status
      const statusRes = await api.pveNode.taskStatus(hostId.value, node.value, encodeURIComponent(upid))
      const taskStatus = statusRes.data?.status
      if (taskStatus && taskStatus !== 'running') {
        upgradeTaskStatus.value = taskStatus
        clearInterval(upgradeTaskPollInterval)
        upgradeTaskPollInterval = null
        // Reload updates after a moment
        setTimeout(loadAptUpdates, 3000)
        if (taskStatus === 'OK') {
          toast.success('Package upgrade completed successfully')
        } else {
          toast.error(`Package upgrade finished with status: ${taskStatus}`)
        }
      }
    } catch (e) {
      console.warn('Task poll error', e)
    }
  }, 2500)
}

const dismissUpgradeTask = () => {
  if (upgradeTaskPollInterval) clearInterval(upgradeTaskPollInterval)
  upgradeTaskUpid.value = null
  upgradeTaskStatus.value = null
  upgradeTaskLog.value = []
}

const refreshPackageList = async () => {
  if (!confirm('This will run apt-get update on the node. Continue?')) return
  refreshingPackages.value = true
  try {
    const res = await api.pveNode.aptRefreshPackages(hostId.value, node.value)
    toast.info('Package list refresh started')
    const upid = res.data?.upid
    if (upid) {
      upgradeTaskUpid.value = upid
      startUpgradeTaskPolling(upid)
    }
    setTimeout(() => loadAptUpdates(), 4000)
  } catch (e) {
    toast.error('Failed to refresh package list: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
    console.error(e)
  } finally {
    refreshingPackages.value = false
  }
}

const upgradeAllPackages = async () => {
  if (!confirm('This will upgrade ALL packages on this node. This is a potentially disruptive operation. Continue?')) return
  upgradingAll.value = true
  try {
    const res = await api.pveNode.aptUpgradeAll(hostId.value, node.value)
    toast.success('Package upgrade started')
    const upid = res.data?.upid
    if (upid) {
      upgradeTaskUpid.value = upid
      startUpgradeTaskPolling(upid)
    }
  } catch (e) {
    toast.error('Failed to start upgrade: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
    console.error(e)
  } finally {
    upgradingAll.value = false
  }
}

const upgradeSelectedPackages = async () => {
  const pkgs = Array.from(selectedPackages.value)
  if (pkgs.length === 0) {
    toast.warning('No packages selected')
    return
  }
  if (!confirm(`Upgrade ${pkgs.length} selected package(s)? Continue?`)) return
  upgradingSelected.value = true
  try {
    const res = await api.pveNode.aptUpgradeSelected(hostId.value, node.value, pkgs)
    toast.success(`Upgrade of ${pkgs.length} package(s) started`)
    const upid = res.data?.upid
    if (upid) {
      upgradeTaskUpid.value = upid
      startUpgradeTaskPolling(upid)
    }
    selectedPackages.value = new Set()
  } catch (e) {
    toast.error('Failed to start upgrade: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
    console.error(e)
  } finally {
    upgradingSelected.value = false
  }
}

// ── Hardware (PCI / USB) ────────────────────────────────────────────────────────

const loadPciDevices = async () => {
  loadingPci.value = true
  try {
    const res = await api.pveNode.listPciDevices(hostId.value, node.value)
    pciDevices.value = res.data || []
  } catch (e) {
    console.warn('PCI list failed', e)
    pciDevices.value = []
  } finally {
    loadingPci.value = false
  }
}

const loadUsbDevices = async () => {
  loadingUsb.value = true
  try {
    const res = await api.pveNode.listUsbDevices(hostId.value, node.value)
    usbDevices.value = res.data || []
  } catch (e) {
    console.warn('USB list failed', e)
    usbDevices.value = []
  } finally {
    loadingUsb.value = false
  }
}

// ── ZFS Pools ──────────────────────────────────────────────────────────────────

const loadZfsPools = async () => {
  loadingZfs.value = true
  zfsError.value = null
  try {
    const res = await api.storage.getZfsPools(hostId.value, node.value)
    zfsPools.value = res.data || []
  } catch (e) {
    // ZFS may not be available on all nodes — treat as non-critical
    if (e?.response?.status === 500 || e?.response?.status === 404) {
      zfsError.value = 'ZFS not available or no pools configured on this node'
    } else {
      console.warn('ZFS pools load failed', e)
      zfsError.value = 'Failed to load ZFS pools'
    }
    zfsPools.value = []
  } finally {
    loadingZfs.value = false
  }
}

const zfsStatusBadge = (status) => {
  if (!status) return 'badge badge-secondary'
  const s = status.toUpperCase()
  if (s === 'ONLINE') return 'badge badge-success'
  if (s === 'DEGRADED') return 'badge badge-warning'
  if (s === 'FAULTED' || s === 'OFFLINE' || s === 'UNAVAIL') return 'badge badge-danger'
  return 'badge badge-secondary'
}

const zfsUsagePct = (pool) => {
  if (!pool.size || !pool.alloc) return 0
  return Math.min(100, Math.round((pool.alloc / pool.size) * 100))
}

const usageColorPct = (pct) => {
  if (pct > 90) return '#dc2626'
  if (pct > 75) return '#f59e0b'
  return '#2563eb'
}

// ── Edit Network Interface ─────────────────────────────────────────────────────

const openEditNetworkModal = (iface) => {
  editNetworkForm.value = {
    iface: iface.iface,
    type: iface.type || '',
    address: iface.address || '',
    netmask: iface.netmask || '',
    gateway: iface.gateway || '',
    bridge_ports: iface['bridge-ports'] || iface.slaves || '',
    autostart: !!iface.autostart,
    comments: iface.comments || iface.comment || '',
  }
  showEditNetworkModal.value = true
}

const saveEditNetworkIface = async () => {
  savingNetwork.value = true
  try {
    const payload = {
      type: editNetworkForm.value.type,
      autostart: editNetworkForm.value.autostart ? 1 : 0,
    }
    if (editNetworkForm.value.address) payload.address = editNetworkForm.value.address
    if (editNetworkForm.value.netmask) payload.netmask = editNetworkForm.value.netmask
    if (editNetworkForm.value.gateway) payload.gateway = editNetworkForm.value.gateway
    if (editNetworkForm.value.comments) payload.comments = editNetworkForm.value.comments
    if (editNetworkForm.value.type === 'bridge' && editNetworkForm.value.bridge_ports) {
      payload['bridge-ports'] = editNetworkForm.value.bridge_ports
    }
    await api.pveNode.updateNetwork(hostId.value, node.value, editNetworkForm.value.iface, payload)
    toast.success(`Interface ${editNetworkForm.value.iface} updated (apply changes to activate)`)
    showEditNetworkModal.value = false
    await loadNetwork()
  } catch (e) {
    toast.error('Failed to update interface: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
    console.error(e)
  } finally {
    savingNetwork.value = false
  }
}

// ── Terminal ───────────────────────────────────────────────────────────────────

const pveWsOrigin = computed(() => {
  // Best-effort: derive the Proxmox WS origin from node name
  return `wss://${node.value}:8006`
})

const termAppendLine = (text, cls = '') => {
  // Convert ANSI escape sequences to basic HTML; sanitize angle-brackets
  const safe = String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  const wrapped = cls ? `<span class="${cls}">${safe}</span>` : safe
  termLines.value.push(wrapped)
  nextTick(() => {
    if (termOutputRef.value) {
      termOutputRef.value.scrollTop = termOutputRef.value.scrollHeight
    }
  })
}

const connectTerminal = async () => {
  if (termConnected.value || termConnecting.value) return
  termConnecting.value = true
  termWsUnavailable.value = false
  termAppendLine(`Connecting to node ${node.value}...`, 'term-info')

  try {
    const res = await api.pveNode.nodeTermproxy(hostId.value, node.value)
    termTicket = res.data
    const { ticket, port, host: pveHost, pve_port: pvePort } = termTicket

    // Build WebSocket URL pointing at the Proxmox node
    const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsHost = pveHost || node.value
    const wsPort = pvePort || 8006
    const wsUrl = `${wsProto}://${wsHost}:${wsPort}/api2/json/nodes/${node.value}/termproxy`

    termAppendLine(`Got ticket — opening WebSocket to ${wsHost}:${wsPort}`, 'term-info')

    const ws = new WebSocket(wsUrl)
    termWs = ws

    ws.onopen = () => {
      // Proxmox termproxy handshake: send ticket as first message
      ws.send(JSON.stringify({ password: ticket }))
      termConnected.value = true
      termConnecting.value = false
      termAppendLine('Connected. Type commands below.', 'term-success')
    }

    ws.onmessage = (evt) => {
      const data = evt.data
      if (typeof data === 'string') {
        // Split on newlines so each line is a separate entry
        data.split('\n').forEach(line => {
          if (line !== '') termAppendLine(line)
        })
      }
    }

    ws.onerror = () => {
      termConnecting.value = false
      termConnected.value = false
      termWsUnavailable.value = true
      termAppendLine('WebSocket connection failed. See SSH info below.', 'term-error')
    }

    ws.onclose = (evt) => {
      termConnected.value = false
      termConnecting.value = false
      termAppendLine(`Connection closed (code ${evt.code}).`, 'term-info')
    }
  } catch (e) {
    termConnecting.value = false
    termWsUnavailable.value = true
    termAppendLine('Failed to get terminal ticket: ' + (e?.response?.data?.detail || e.message || 'Unknown error'), 'term-error')
  }
}

const disconnectTerminal = () => {
  if (termWs) {
    termWs.close()
    termWs = null
  }
  termConnected.value = false
  termConnecting.value = false
}

const clearTerminal = () => {
  termLines.value = []
}

const sendTermCommand = () => {
  const cmd = termInput.value
  if (!cmd || !termConnected.value || !termWs) return
  // Echo locally
  termAppendLine(`$ ${cmd}`, 'term-cmd')
  // Save to history
  termHistory.value.unshift(cmd)
  if (termHistory.value.length > 100) termHistory.value.pop()
  termHistoryIndex.value = -1
  // Send via WebSocket
  termWs.send(cmd + '\n')
  termInput.value = ''
}

const sendCtrlC = () => {
  if (termConnected.value && termWs) {
    termWs.send('\x03')
    termAppendLine('^C', 'term-info')
    termInput.value = ''
  }
}

const focusTermInput = () => {
  termInputRef.value?.focus()
}

const termHistoryUp = () => {
  if (termHistory.value.length === 0) return
  termHistoryIndex.value = Math.min(termHistoryIndex.value + 1, termHistory.value.length - 1)
  termInput.value = termHistory.value[termHistoryIndex.value]
}

const termHistoryDown = () => {
  if (termHistoryIndex.value <= 0) {
    termHistoryIndex.value = -1
    termInput.value = ''
    return
  }
  termHistoryIndex.value--
  termInput.value = termHistory.value[termHistoryIndex.value]
}

const openTerminalWindow = () => {
  window.open(`/proxmox/${hostId.value}/nodes/${node.value}/terminal`, '_blank', 'width=900,height=600')
}

const openTerminal = () => {
  router.push(`/proxmox/${hostId.value}/nodes/${node.value}/terminal`)
}

// ── Utilities ──────────────────────────────────────────────────────────────────

const formatLoadAvg = (loadavg) => {
  if (!loadavg) return '—'
  if (Array.isArray(loadavg)) return loadavg.map(v => parseFloat(v).toFixed(2)).join(', ')
  return String(loadavg)
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────

onMounted(async () => {
  fetchHostName()
  await loadAll()
  startPolling()
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
  if (upgradeTaskPollInterval) clearInterval(upgradeTaskPollInterval)
  disconnectTerminal()
})

// ── Copy helpers ──────────────────────────────────────────────────────────
const copyNodeName = () => copyToClipboard(node, { toast: true })
const copySshCommand = () => copyToClipboard(`ssh root@${node}`, { toast: true })
</script>

<style scoped>
.btn-copy {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.7rem;
  padding: 1px 5px;
  margin-left: 4px;
  line-height: 1.4;
  transition: background 0.15s, color 0.15s;
  vertical-align: middle;
}
.btn-copy:hover {
  background: var(--background);
  color: var(--primary-color);
}

.node-detail-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.back-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
}

.back-link:hover {
  color: var(--text-primary);
}

.node-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-meta {
  flex-wrap: wrap;
}

.header-stats {
  align-items: center;
}

.mini-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.5rem 1rem;
  min-width: 70px;
}

.mini-stat__label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mini-stat__value {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
}

/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1.5rem;
  overflow-x: auto;
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
  white-space: nowrap;
}

.tab-btn:hover { color: var(--text-primary); }

.tab-btn--active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

/* Stats row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card-sm {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  box-shadow: var(--shadow);
}

.stat-card-sm__label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.stat-card-sm__value {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Charts */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 900px) {
  .charts-grid { grid-template-columns: 1fr; }
}

.chart-card .card-header h4 {
  margin: 0;
  font-size: 0.9rem;
}

.chart-wrap {
  height: 200px;
  padding: 0.5rem;
}

.form-control-sm {
  padding: 0.2rem 0.5rem;
  font-size: 0.8rem;
}

/* Clickable rows */
.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background: var(--background);
}

.row-expanded {
  background: var(--background);
}

/* Usage bar */
.usage-bar-wrap {
  width: 100%;
  background: var(--border-color);
  border-radius: 4px;
  height: 6px;
  overflow: hidden;
  margin-bottom: 0.25rem;
}

.usage-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

/* Task log */
.task-log-cell {
  padding: 0;
  background: #0f1419;
}

.task-log {
  margin: 0;
  padding: 0.75rem 1rem;
  font-size: 0.8rem;
  color: #9ca3af;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
}

.task-log-modal {
  max-height: 60vh;
  background: #0f1419;
  border-radius: 0.375rem;
}

.table-container {
  overflow-x: auto;
}

.card-body {
  padding: 1.5rem;
}

/* Modal */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  max-width: 580px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.modal-content.modal-large {
  max-width: 800px;
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.modal-body {
  padding: 1.5rem;
}

/* Form groups */
.form-group {
  margin-bottom: 1rem;
}

.form-label {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary);
}

/* Utilities */
.ml-1 { margin-left: 0.25rem; }
.mb-2 { margin-bottom: 1rem; }
.mt-2 { margin-top: 1rem; }
.mt-4 { margin-top: 2rem; }
.pt-2 { padding-top: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-center { text-align: center; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.gap-2 { gap: 1rem; }
.align-center { align-items: center; }

.btn-success {
  background-color: var(--secondary-color);
  color: white;
}

.btn-success:hover {
  background-color: #059669;
}

.badge-warning {
  background-color: #fef3c7;
  color: #92400e;
}

.badge-secondary {
  background-color: var(--border-color);
  color: var(--text-secondary);
}

/* Certificate card */
.cert-card {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.cert-row {
  display: flex;
  gap: 1rem;
  align-items: baseline;
}

.cert-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  min-width: 100px;
  flex-shrink: 0;
}

.cert-value {
  flex: 1;
}

/* ── Stats card sub-text ──────────────────────────────────────────────── */
.stat-card-sm__sub {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-usage-bar {
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 0.375rem;
}

.mini-usage-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
}

/* ── Info banner (updates tab) ──────────────────────────────────────── */
.info-banner {
  padding: 0.625rem 1rem;
  background: rgba(59,130,246,0.08);
  border-bottom: 1px solid var(--border-color);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-inline-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  color: var(--text-secondary);
  margin-left: auto;
  line-height: 1;
  padding: 0;
}

/* ── Mobile Responsive ──────────────────────────────────────────────────── */
@media (max-width: 768px) {
  /* Header: stack on mobile */
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-stats {
    width: 100%;
    justify-content: flex-start;
  }

  .node-title {
    font-size: 1.1rem;
  }

  /* Tabs: horizontal scroll */
  .tabs {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    flex-wrap: nowrap;
    scrollbar-width: none;
  }
  .tabs::-webkit-scrollbar {
    display: none;
  }

  /* Stats: 2-column on mobile */
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.5rem;
  }

  /* Modals: full-screen on mobile */
  .modal-content,
  .modal-content.modal-large {
    width: 100%;
    max-width: 100%;
    height: 100%;
    max-height: 100%;
    border-radius: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
  }

  .modal {
    align-items: flex-end;
  }

  .modal-body {
    flex: 1;
    overflow-y: auto;
  }

  /* Config / info grids: single column */
  .config-grid,
  .form-row {
    grid-template-columns: 1fr !important;
  }
}

/* ── Terminal ──────────────────────────────────────────────────────────── */

.term-wrapper {
  background: #0d1117;
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
}

.term-output {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.82rem;
  line-height: 1.5;
  color: #c9d1d9;
  padding: 0.75rem 1rem;
  min-height: 300px;
  max-height: 520px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  cursor: text;
}

.term-line {
  display: block;
  min-height: 1.25rem;
}

.term-placeholder {
  color: #6e7681;
  font-style: italic;
  padding: 2rem 0;
  text-align: center;
}

.term-info  { color: #58a6ff; }
.term-success { color: #3fb950; }
.term-error { color: #f85149; }
.term-cmd   { color: #d2a8ff; }

.term-input-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: #0d1117;
  border-top: 1px solid #30363d;
}

.term-prompt {
  color: #3fb950;
  font-family: monospace;
  font-weight: bold;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.term-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #c9d1d9;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.82rem;
  caret-color: #c9d1d9;
  padding: 0;
  min-width: 0;
}

.term-input::placeholder { color: #6e7681; }

.term-input:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.ssh-cmd {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 0.2rem 0.5rem;
  font-size: 0.85rem;
  color: var(--text-primary);
}

/* ── APT Controls ──────────────────────────────────────────────────────── */

.apt-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.625rem 1rem;
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.apt-search {
  flex: 1;
  min-width: 200px;
  max-width: 340px;
}

.apt-row--selected {
  background: rgba(59, 130, 246, 0.06);
}

.apt-task-log {
  background: #0d1117;
  border-bottom: 1px solid var(--border-color);
}

.apt-task-log__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 1rem;
  border-bottom: 1px solid #30363d;
}

.apt-task-log__body {
  margin: 0;
  padding: 0.75rem 1rem;
  font-size: 0.78rem;
  color: #9ca3af;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 220px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
}

.flex-wrap { flex-wrap: wrap; }

/* ── Node error / empty states ─────────────────────────────────────────── */
.node-error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.85rem;
  padding: 4rem 1.5rem;
  text-align: center;
}

.node-error-state__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.08);
  border: 2px dashed rgba(239, 68, 68, 0.3);
  color: #ef4444;
}

.node-error-state__title {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.node-error-state__sub {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin: 0;
  max-width: 400px;
}

/* ── Tab-level error banner ─────────────────────────────────────────────── */
.tab-error-banner {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.75rem 1rem;
  background: rgba(239, 68, 68, 0.06);
  border-bottom: 1px solid rgba(239, 68, 68, 0.2);
  font-size: 0.875rem;
  color: var(--text-primary);
}
.tab-error-banner svg { color: #ef4444; flex-shrink: 0; }
.tab-error-banner .btn { margin-left: auto; flex-shrink: 0; }

/* ── Tab-level empty state ──────────────────────────────────────────────── */
.tab-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  padding: 2.5rem 1rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}
.tab-empty svg { opacity: 0.4; }

/* ── Breadcrumb navigation ──────────────────────────────────────────────── */
.breadcrumb-nav {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}
.breadcrumb-crumb {
  color: var(--text-secondary);
  text-decoration: none;
  transition: color 0.15s;
}
.breadcrumb-crumb:hover {
  color: var(--text-primary);
  text-decoration: underline;
}
.breadcrumb-crumb--current {
  color: var(--text-primary);
  font-weight: 500;
  cursor: default;
}
.breadcrumb-crumb--current:hover {
  text-decoration: none;
}
.breadcrumb-sep {
  color: var(--text-muted);
  user-select: none;
}
.disk-io-live {
  display: flex; flex-direction: column; gap: 0.5rem;
  padding: 1rem; justify-content: center; height: 100%;
}
.dil-row { display: flex; align-items: center; gap: 0.5rem; }
.dil-label { font-size: 0.7rem; font-weight: 700; width: 14px; flex-shrink: 0; }
.dil-read { color: #8b5cf6; }
.dil-write { color: #ef4444; }
.dil-val { font-size: 0.9rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.dil-hint { font-size: 0.65rem; color: var(--text-secondary); }
</style>
