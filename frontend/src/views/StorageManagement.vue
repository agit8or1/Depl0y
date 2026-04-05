<template>
  <div class="storage-management">
    <div class="page-header">
      <div>
        <h1>Storage Management</h1>
        <p class="text-muted">Manage Proxmox storage pools, ZFS, and Ceph across all hosts</p>
      </div>
      <div class="header-actions">
        <button @click="refresh" class="btn btn-secondary" :disabled="loading">Refresh</button>
        <button v-if="activeTab === 'overview'" @click="openCreateModal" class="btn btn-primary">
          + Add Storage
        </button>
        <button v-if="activeTab === 'zfs' && selectedHostId && selectedNode" @click="openCreateZfsModal" class="btn btn-primary">
          + Create ZFS Pool
        </button>
      </div>
    </div>

    <!-- Host Selector -->
    <div class="card selector-card">
      <div class="selector-row">
        <div class="selector-item">
          <label class="form-label">Proxmox Host</label>
          <select v-model="selectedHostId" class="form-control" :disabled="loadingHosts" @change="onHostChange">
            <option value="">{{ loadingHosts ? 'Loading...' : 'Select a host...' }}</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }} — {{ h.address }}</option>
          </select>
        </div>
        <div v-if="activeTab !== 'overview'" class="selector-item">
          <label class="form-label">Node</label>
          <select v-model="selectedNode" class="form-control" :disabled="!selectedHostId || loadingNodes" @change="onNodeChange">
            <option value="">{{ loadingNodes ? 'Loading...' : 'Select a node...' }}</option>
            <option v-for="n in nodes" :key="n.node" :value="n.node">{{ n.node }}</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tab-bar">
      <button :class="['tab-btn', activeTab === 'overview' ? 'active' : '']" @click="activeTab = 'overview'">
        Storage Pools
      </button>
      <button :class="['tab-btn', activeTab === 'zfs' ? 'active' : '']" @click="activeTab = 'zfs'">
        ZFS Pools
      </button>
      <button :class="['tab-btn', activeTab === 'ceph' ? 'active' : '']" @click="activeTab = 'ceph'">
        Ceph
      </button>
    </div>

    <!-- ── OVERVIEW TAB ── -->
    <div v-if="activeTab === 'overview'">
      <div v-if="!selectedHostId" class="card empty-placeholder">
        <p class="text-muted">Select a Proxmox host above to view storage pools.</p>
      </div>
      <div v-else-if="loadingStorage" class="card loading-state">Loading storage pools...</div>
      <div v-else-if="storageError" class="card error-state">
        <p class="text-danger">{{ storageError }}</p>
      </div>
      <div v-else class="card">
        <div class="card-header">
          <h2>Storage Pools</h2>
          <span class="badge badge-secondary">{{ storagePools.length }} pools</span>
        </div>
        <div v-if="storagePools.length === 0" class="empty-state">No storage pools found.</div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Node</th>
                <th>Content</th>
                <th>Usage</th>
                <th>Shared</th>
                <th>Enabled</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in storagePools" :key="s.storage">
                <td class="storage-name">{{ s.storage }}</td>
                <td><span :class="['type-badge', 'type-' + s.type]">{{ s.type }}</span></td>
                <td>{{ s.nodes || 'all' }}</td>
                <td class="content-cell">
                  <span v-for="c in parseContent(s.content)" :key="c" class="content-tag">{{ c }}</span>
                </td>
                <td class="usage-cell">
                  <div v-if="s.total > 0" class="usage-bar-wrap">
                    <div class="usage-bar">
                      <div :class="['usage-fill', usageClass(s.used, s.total)]"
                           :style="{ width: usagePct(s.used, s.total) + '%' }"></div>
                    </div>
                    <span class="usage-text">
                      {{ formatBytes(s.used) }} / {{ formatBytes(s.total) }}
                      ({{ usagePct(s.used, s.total) }}%)
                    </span>
                  </div>
                  <span v-else class="text-muted text-sm">N/A</span>
                </td>
                <td>
                  <span :class="['badge', s.shared ? 'badge-success' : 'badge-secondary']">
                    {{ s.shared ? 'Shared' : 'Local' }}
                  </span>
                </td>
                <td>
                  <span :class="['badge', s.enabled !== false ? 'badge-success' : 'badge-danger']">
                    {{ s.enabled !== false ? 'Enabled' : 'Disabled' }}
                  </span>
                </td>
                <td class="actions-cell">
                  <button @click="editStorage(s)" class="btn-icon" title="Edit">&#9998;</button>
                  <button @click="toggleStorage(s)" class="btn-icon"
                          :title="s.enabled !== false ? 'Disable' : 'Enable'">
                    {{ s.enabled !== false ? '&#9632;' : '&#9654;' }}
                  </button>
                  <button @click="confirmDeleteStorage(s)" class="btn-icon btn-icon-danger" title="Delete">&#128465;</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ── ZFS TAB ── -->
    <div v-if="activeTab === 'zfs'">
      <div v-if="!selectedHostId || !selectedNode" class="card empty-placeholder">
        <p class="text-muted">Select a host and node above to view ZFS pools.</p>
      </div>
      <div v-else-if="loadingZfs" class="card loading-state">Loading ZFS pools...</div>
      <div v-else-if="zfsError" class="card error-state">
        <p class="text-danger">{{ zfsError }}</p>
      </div>
      <div v-else class="card">
        <div class="card-header">
          <h2>ZFS Pools — {{ selectedNode }}</h2>
          <span class="badge badge-secondary">{{ zfsPools.length }} pools</span>
        </div>
        <div v-if="zfsPools.length === 0" class="empty-state">No ZFS pools found on this node.</div>
        <div v-else>
          <div v-for="pool in zfsPools" :key="pool.name" class="zfs-pool-card">
            <div class="zfs-pool-header" @click="togglePoolExpand(pool.name)">
              <div class="zfs-pool-info">
                <span class="zfs-pool-name">{{ pool.name }}</span>
                <span :class="['badge', zfsStatusBadge(pool.health)]">{{ pool.health || 'UNKNOWN' }}</span>
              </div>
              <div class="zfs-pool-stats">
                <span class="stat">
                  <strong>Size:</strong> {{ formatBytes(pool.size) }}
                </span>
                <span class="stat">
                  <strong>Used:</strong> {{ formatBytes(pool.alloc) }}
                </span>
                <span class="stat">
                  <strong>Free:</strong> {{ formatBytes(pool.free) }}
                </span>
                <span class="stat" v-if="pool.frag !== undefined">
                  <strong>Frag:</strong> {{ pool.frag }}%
                </span>
                <span class="stat" v-if="pool.dedup !== undefined">
                  <strong>Dedup:</strong> {{ pool.dedup }}x
                </span>
              </div>
              <div class="zfs-pool-actions" @click.stop>
                <button @click="scrubPool(pool)" class="btn btn-sm btn-secondary"
                        :disabled="scrubbingPool === pool.name">
                  {{ scrubbingPool === pool.name ? 'Scrubbing...' : 'Scrub' }}
                </button>
                <span class="expand-icon">{{ expandedPools.has(pool.name) ? '▲' : '▼' }}</span>
              </div>
            </div>

            <!-- Usage bar -->
            <div class="zfs-usage-bar-wrap" v-if="pool.size > 0">
              <div class="usage-bar usage-bar-lg">
                <div :class="['usage-fill', usageClass(pool.alloc, pool.size)]"
                     :style="{ width: usagePct(pool.alloc, pool.size) + '%' }"></div>
              </div>
            </div>

            <!-- Expanded: vdev tree -->
            <div v-if="expandedPools.has(pool.name)" class="vdev-tree">
              <div v-if="loadingPoolDetail[pool.name]" class="loading-state-sm">Loading vdev tree...</div>
              <div v-else-if="poolDetails[pool.name]">
                <div v-for="vdev in getVdevs(pool.name)" :key="vdev.name || vdev.msg" class="vdev-row">
                  <div class="vdev-header">
                    <span class="vdev-name">{{ vdev.name || vdev.msg }}</span>
                    <span v-if="vdev.state" :class="['badge', zfsStatusBadge(vdev.state)]">{{ vdev.state }}</span>
                  </div>
                  <div v-if="vdev.children && vdev.children.length" class="vdev-children">
                    <div v-for="child in vdev.children" :key="child.name" class="vdev-disk-row">
                      <span class="disk-path">{{ child.name }}</span>
                      <span :class="['badge', zfsStatusBadge(child.state)]">{{ child.state || 'ONLINE' }}</span>
                      <span class="disk-errors text-sm text-muted">
                        R:{{ child.read || 0 }} W:{{ child.write || 0 }} C:{{ child.cksum || 0 }}
                      </span>
                    </div>
                  </div>
                  <div v-else-if="!vdev.children && vdev.name" class="vdev-children">
                    <div class="vdev-disk-row">
                      <span class="disk-path">{{ vdev.name }}</span>
                      <span :class="['badge', zfsStatusBadge(vdev.state)]">{{ vdev.state || 'ONLINE' }}</span>
                      <span class="disk-errors text-sm text-muted">
                        R:{{ vdev.read || 0 }} W:{{ vdev.write || 0 }} C:{{ vdev.cksum || 0 }}
                      </span>
                    </div>
                  </div>
                </div>
                <div v-if="getVdevs(pool.name).length === 0" class="text-muted text-sm" style="padding: 0.5rem 1rem;">
                  No vdev detail available.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── CEPH TAB ── -->
    <div v-if="activeTab === 'ceph'">
      <div v-if="!selectedHostId || !selectedNode" class="card empty-placeholder">
        <p class="text-muted">Select a host and node above to view Ceph status.</p>
      </div>
      <div v-else-if="loadingCeph" class="card loading-state">Checking Ceph configuration...</div>
      <div v-else-if="!cephConfigured" class="card ceph-not-configured">
        <div class="ceph-not-configured-inner">
          <div class="ceph-icon">&#128722;</div>
          <h3>Ceph Not Detected</h3>
          <p class="text-muted">Ceph does not appear to be configured on node <strong>{{ selectedNode }}</strong>.</p>
          <div class="ceph-setup-info">
            <p class="text-muted">To set up Ceph on Proxmox VE:</p>
            <ol class="setup-steps">
              <li>Navigate to the Proxmox VE web UI for this node</li>
              <li>Go to <strong>Datacenter &rarr; Ceph</strong></li>
              <li>Install Ceph on each node that will participate</li>
              <li>Create monitors (Mon) on at least 3 nodes</li>
              <li>Create OSDs from available disks</li>
              <li>Create a pool for use with PVE storage</li>
            </ol>
          </div>
          <button @click="loadCeph" class="btn btn-secondary">Re-check Ceph</button>
        </div>
      </div>
      <div v-else>
        <!-- Cluster Health -->
        <div class="card">
          <div class="card-header">
            <h2>Ceph Cluster Health</h2>
            <span :class="['badge', cephHealthBadge]">{{ cephHealth }}</span>
          </div>
          <div class="ceph-health-grid" v-if="cephStatus">
            <div class="ceph-stat-item">
              <span class="ceph-stat-label">Total OSDs</span>
              <span class="ceph-stat-value">{{ cephStatus.osdmap?.osdmap?.num_osds || cephStatus.osdmap?.num_osds || '—' }}</span>
            </div>
            <div class="ceph-stat-item">
              <span class="ceph-stat-label">OSDs Up</span>
              <span class="ceph-stat-value">{{ cephStatus.osdmap?.osdmap?.num_up_osds || cephStatus.osdmap?.num_up_osds || '—' }}</span>
            </div>
            <div class="ceph-stat-item">
              <span class="ceph-stat-label">OSDs In</span>
              <span class="ceph-stat-value">{{ cephStatus.osdmap?.osdmap?.num_in_osds || cephStatus.osdmap?.num_in_osds || '—' }}</span>
            </div>
            <div class="ceph-stat-item">
              <span class="ceph-stat-label">PGs Active+Clean</span>
              <span class="ceph-stat-value">{{ cephPgsClean }}</span>
            </div>
            <div class="ceph-stat-item">
              <span class="ceph-stat-label">Total Capacity</span>
              <span class="ceph-stat-value">{{ formatBytes(cephStatus.pgmap?.bytes_total) }}</span>
            </div>
            <div class="ceph-stat-item">
              <span class="ceph-stat-label">Used</span>
              <span class="ceph-stat-value">{{ formatBytes(cephStatus.pgmap?.bytes_used) }}</span>
            </div>
            <div class="ceph-stat-item">
              <span class="ceph-stat-label">Available</span>
              <span class="ceph-stat-value">{{ formatBytes(cephStatus.pgmap?.bytes_avail) }}</span>
            </div>
          </div>
        </div>

        <!-- Monitors -->
        <div class="card">
          <div class="card-header">
            <h2>Monitors</h2>
          </div>
          <div v-if="loadingCephMons" class="loading-state-sm">Loading monitors...</div>
          <div v-else-if="cephMons.length === 0" class="empty-state">No monitors found.</div>
          <div v-else class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Address</th>
                  <th>Quorum</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="mon in cephMons" :key="mon.name">
                  <td>{{ mon.name }}</td>
                  <td class="text-mono">{{ mon.addr || '—' }}</td>
                  <td>
                    <span :class="['badge', mon.quorum !== undefined ? (mon.quorum ? 'badge-success' : 'badge-danger') : 'badge-secondary']">
                      {{ mon.quorum !== undefined ? (mon.quorum ? 'In Quorum' : 'Not in Quorum') : '—' }}
                    </span>
                  </td>
                  <td>
                    <span :class="['badge', mon.host ? 'badge-success' : 'badge-secondary']">
                      {{ mon.rank !== undefined ? 'rank ' + mon.rank : '—' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- OSDs -->
        <div class="card">
          <div class="card-header">
            <h2>OSDs</h2>
          </div>
          <div v-if="loadingCephOsds" class="loading-state-sm">Loading OSDs...</div>
          <div v-else-if="cephOsds.length === 0" class="empty-state">No OSDs found.</div>
          <div v-else class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Host</th>
                  <th>Status</th>
                  <th>Device</th>
                  <th>Size</th>
                  <th>Used</th>
                  <th>Version</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="osd in flatOsds" :key="osd.id">
                  <td>{{ osd.id }}</td>
                  <td>{{ osd.host || '—' }}</td>
                  <td>
                    <span :class="['badge', osdStatusBadge(osd.up, osd.inn)]">
                      {{ osd.up ? 'up' : 'down' }} / {{ osd.inn ? 'in' : 'out' }}
                    </span>
                  </td>
                  <td class="text-mono">{{ osd.device_path || osd.dev_node || '—' }}</td>
                  <td>{{ formatBytes(osd.total_space || osd.kb_total ? (osd.kb_total * 1024) : undefined) }}</td>
                  <td>{{ formatBytes(osd.used_space || osd.kb_used ? (osd.kb_used * 1024) : undefined) }}</td>
                  <td class="text-sm">{{ osd.version || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Ceph Pools -->
        <div class="card">
          <div class="card-header">
            <h2>Ceph Pools</h2>
          </div>
          <div v-if="loadingCephPools" class="loading-state-sm">Loading pools...</div>
          <div v-else-if="cephPools.length === 0" class="empty-state">No Ceph pools found.</div>
          <div v-else class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Replicas</th>
                  <th>PGs</th>
                  <th>Used</th>
                  <th>Available</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in cephPools" :key="p.pool_name || p.name">
                  <td>{{ p.pool_name || p.name }}</td>
                  <td>{{ p.size || '—' }}</td>
                  <td>{{ p.pg_num || '—' }}</td>
                  <td>{{ formatBytes(p.bytes_used) }}</td>
                  <td>{{ formatBytes(p.max_avail) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- ── CREATE / EDIT STORAGE MODAL ── -->
    <div v-if="showStorageModal" class="modal-overlay" @click.self="closeStorageModal">
      <div class="modal modal-lg">
        <div class="modal-header">
          <h2>{{ editingStorage ? 'Edit Storage' : 'Add Storage' }}</h2>
          <button class="modal-close" @click="closeStorageModal">&times;</button>
        </div>
        <div class="modal-body">
          <!-- Type tabs (only when creating) -->
          <div v-if="!editingStorage" class="type-tabs">
            <button v-for="t in storageTypes" :key="t.value"
                    :class="['type-tab', storageForm.type === t.value ? 'active' : '']"
                    @click="storageForm.type = t.value">
              {{ t.label }}
            </button>
          </div>

          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Storage ID <span class="required">*</span></label>
              <input v-model="storageForm.storage" type="text" class="form-control"
                     placeholder="e.g. local-zfs" :disabled="!!editingStorage" />
            </div>
            <div class="form-group" v-if="!editingStorage">
              <label class="form-label">Type</label>
              <input :value="storageForm.type" class="form-control" disabled />
            </div>
          </div>

          <!-- Directory -->
          <template v-if="storageForm.type === 'dir'">
            <div class="form-group">
              <label class="form-label">Path <span class="required">*</span></label>
              <input v-model="storageForm.path" type="text" class="form-control" placeholder="/mnt/storage" />
            </div>
            <div class="form-group">
              <label class="form-label">Content Types</label>
              <div class="checkbox-group">
                <label v-for="c in contentTypes" :key="c.value" class="checkbox-label">
                  <input type="checkbox" :value="c.value" v-model="selectedContentTypes" />
                  {{ c.label }}
                </label>
              </div>
            </div>
            <div class="form-group form-toggle">
              <label class="form-label">Shared Mount</label>
              <input type="checkbox" v-model="storageForm.shared" class="toggle-input" />
            </div>
          </template>

          <!-- LVM -->
          <template v-if="storageForm.type === 'lvm'">
            <div class="form-group">
              <label class="form-label">Volume Group <span class="required">*</span></label>
              <input v-model="storageForm.vgname" type="text" class="form-control" placeholder="pve" />
            </div>
            <div class="form-group">
              <label class="form-label">Content Types</label>
              <div class="checkbox-group">
                <label v-for="c in vmContentTypes" :key="c.value" class="checkbox-label">
                  <input type="checkbox" :value="c.value" v-model="selectedContentTypes" />
                  {{ c.label }}
                </label>
              </div>
            </div>
          </template>

          <!-- LVM-Thin -->
          <template v-if="storageForm.type === 'lvmthin'">
            <div class="form-group">
              <label class="form-label">Volume Group <span class="required">*</span></label>
              <input v-model="storageForm.vgname" type="text" class="form-control" placeholder="pve" />
            </div>
            <div class="form-group">
              <label class="form-label">Thin Pool Name <span class="required">*</span></label>
              <input v-model="storageForm.thinpool" type="text" class="form-control" placeholder="data" />
            </div>
            <div class="form-group">
              <label class="form-label">Content Types</label>
              <div class="checkbox-group">
                <label v-for="c in vmContentTypes" :key="c.value" class="checkbox-label">
                  <input type="checkbox" :value="c.value" v-model="selectedContentTypes" />
                  {{ c.label }}
                </label>
              </div>
            </div>
          </template>

          <!-- ZFS -->
          <template v-if="storageForm.type === 'zfspool'">
            <div class="form-group">
              <label class="form-label">ZFS Pool Name <span class="required">*</span></label>
              <input v-model="storageForm.pool" type="text" class="form-control" placeholder="tank" />
            </div>
            <div class="form-group form-toggle">
              <label class="form-label">Sparse (thin-provisioning)</label>
              <input type="checkbox" v-model="storageForm.sparse" class="toggle-input" />
            </div>
            <div class="form-group">
              <label class="form-label">Content Types</label>
              <div class="checkbox-group">
                <label v-for="c in vmContentTypes" :key="c.value" class="checkbox-label">
                  <input type="checkbox" :value="c.value" v-model="selectedContentTypes" />
                  {{ c.label }}
                </label>
              </div>
            </div>
          </template>

          <!-- NFS -->
          <template v-if="storageForm.type === 'nfs'">
            <div class="form-grid">
              <div class="form-group">
                <label class="form-label">Server IP <span class="required">*</span></label>
                <input v-model="storageForm.server" type="text" class="form-control" placeholder="192.168.1.100" />
              </div>
              <div class="form-group">
                <label class="form-label">Export Path <span class="required">*</span></label>
                <input v-model="storageForm.export" type="text" class="form-control" placeholder="/export/pve" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Mount Options</label>
              <input v-model="storageForm.options" type="text" class="form-control" placeholder="vers=4,soft" />
            </div>
            <div class="form-group">
              <label class="form-label">Content Types</label>
              <div class="checkbox-group">
                <label v-for="c in contentTypes" :key="c.value" class="checkbox-label">
                  <input type="checkbox" :value="c.value" v-model="selectedContentTypes" />
                  {{ c.label }}
                </label>
              </div>
            </div>
          </template>

          <!-- SMB/CIFS -->
          <template v-if="storageForm.type === 'cifs'">
            <div class="form-grid">
              <div class="form-group">
                <label class="form-label">Server <span class="required">*</span></label>
                <input v-model="storageForm.server" type="text" class="form-control" placeholder="192.168.1.100" />
              </div>
              <div class="form-group">
                <label class="form-label">Share <span class="required">*</span></label>
                <input v-model="storageForm.share" type="text" class="form-control" placeholder="backups" />
              </div>
            </div>
            <div class="form-grid">
              <div class="form-group">
                <label class="form-label">Username</label>
                <input v-model="storageForm.username" type="text" class="form-control" />
              </div>
              <div class="form-group">
                <label class="form-label">Password</label>
                <input v-model="storageForm.password" type="password" class="form-control" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Domain</label>
              <input v-model="storageForm.domain" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Content Types</label>
              <div class="checkbox-group">
                <label v-for="c in contentTypes" :key="c.value" class="checkbox-label">
                  <input type="checkbox" :value="c.value" v-model="selectedContentTypes" />
                  {{ c.label }}
                </label>
              </div>
            </div>
          </template>

          <!-- RBD/Ceph -->
          <template v-if="storageForm.type === 'rbd'">
            <div class="form-group">
              <label class="form-label">Monitor Hosts <span class="required">*</span></label>
              <input v-model="storageForm.monhost" type="text" class="form-control" placeholder="192.168.1.10;192.168.1.11" />
              <p class="form-hint">Separate multiple hosts with semicolons</p>
            </div>
            <div class="form-grid">
              <div class="form-group">
                <label class="form-label">Pool Name <span class="required">*</span></label>
                <input v-model="storageForm.pool" type="text" class="form-control" placeholder="rbd" />
              </div>
              <div class="form-group">
                <label class="form-label">Username</label>
                <input v-model="storageForm.username" type="text" class="form-control" placeholder="admin" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Keyring</label>
              <textarea v-model="storageForm.keyring" class="form-control" rows="3"
                        placeholder="Paste Ceph keyring here"></textarea>
            </div>
            <div class="form-group">
              <label class="form-label">Content Types</label>
              <div class="checkbox-group">
                <label v-for="c in vmContentTypes" :key="c.value" class="checkbox-label">
                  <input type="checkbox" :value="c.value" v-model="selectedContentTypes" />
                  {{ c.label }}
                </label>
              </div>
            </div>
          </template>

          <!-- Common: nodes restriction -->
          <div class="form-group">
            <label class="form-label">Restrict to Nodes (optional)</label>
            <input v-model="storageForm.nodes" type="text" class="form-control"
                   placeholder="Leave empty for all nodes, or enter comma-separated node names" />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeStorageModal" class="btn btn-secondary">Cancel</button>
          <button @click="saveStorage" class="btn btn-primary" :disabled="savingStorage">
            {{ savingStorage ? 'Saving...' : (editingStorage ? 'Save Changes' : 'Create Storage') }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── CREATE ZFS POOL MODAL ── -->
    <div v-if="showZfsModal" class="modal-overlay" @click.self="closeZfsModal">
      <div class="modal">
        <div class="modal-header">
          <h2>Create ZFS Pool</h2>
          <button class="modal-close" @click="closeZfsModal">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Pool Name <span class="required">*</span></label>
            <input v-model="zfsForm.name" type="text" class="form-control" placeholder="tank" />
          </div>
          <div class="form-group">
            <label class="form-label">RAID Level <span class="required">*</span></label>
            <select v-model="zfsForm.raidlevel" class="form-control">
              <option value="single">Single Disk (no redundancy)</option>
              <option value="mirror">Mirror (RAID-1)</option>
              <option value="raid10">RAID-10</option>
              <option value="raidz">RAIDZ (RAID-5)</option>
              <option value="raidz2">RAIDZ2 (RAID-6)</option>
              <option value="raidz3">RAIDZ3</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Devices <span class="required">*</span></label>
            <input v-model="zfsForm.devices" type="text" class="form-control"
                   placeholder="/dev/sdb,/dev/sdc" />
            <p class="form-hint">Comma-separated device paths</p>
          </div>
          <div class="form-group form-toggle">
            <label class="form-label">Add as PVE Storage</label>
            <input type="checkbox" v-model="zfsForm.add_storage" class="toggle-input" />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeZfsModal" class="btn btn-secondary">Cancel</button>
          <button @click="createZfsPool" class="btn btn-primary" :disabled="creatingZfs">
            {{ creatingZfs ? 'Creating...' : 'Create Pool' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── DELETE CONFIRM MODAL ── -->
    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="showDeleteConfirm = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h2>Confirm Delete</h2>
          <button class="modal-close" @click="showDeleteConfirm = false">&times;</button>
        </div>
        <div class="modal-body">
          <p>Are you sure you want to delete storage <strong>{{ deletingStorage?.storage }}</strong>?</p>
          <p class="text-danger text-sm">This action cannot be undone. Existing data on this storage will not be removed, but the storage definition will be deleted from Proxmox.</p>
        </div>
        <div class="modal-footer">
          <button @click="showDeleteConfirm = false" class="btn btn-secondary">Cancel</button>
          <button @click="deleteStorage" class="btn btn-danger" :disabled="deletingStorageInProgress">
            {{ deletingStorageInProgress ? 'Deleting...' : 'Delete' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'StorageManagement',
  setup() {
    const toast = useToast()

    // ── State ──────────────────────────────────────────────────────────────────
    const activeTab = ref('overview')
    const hosts = ref([])
    const nodes = ref([])
    const loadingHosts = ref(false)
    const loadingNodes = ref(false)
    const selectedHostId = ref('')
    const selectedNode = ref('')

    // Overview tab
    const storagePools = ref([])
    const loadingStorage = ref(false)
    const storageError = ref('')

    // ZFS tab
    const zfsPools = ref([])
    const loadingZfs = ref(false)
    const zfsError = ref('')
    const expandedPools = ref(new Set())
    const poolDetails = ref({})
    const loadingPoolDetail = ref({})
    const scrubbingPool = ref('')

    // Ceph tab
    const cephConfigured = ref(false)
    const loadingCeph = ref(false)
    const cephStatus = ref(null)
    const cephMons = ref([])
    const cephOsds = ref([])
    const cephPools = ref([])
    const loadingCephMons = ref(false)
    const loadingCephOsds = ref(false)
    const loadingCephPools = ref(false)

    // Create/Edit modal
    const showStorageModal = ref(false)
    const editingStorage = ref(null)
    const savingStorage = ref(false)
    const storageForm = ref({})
    const selectedContentTypes = ref([])

    // ZFS create modal
    const showZfsModal = ref(false)
    const creatingZfs = ref(false)
    const zfsForm = ref({ name: '', raidlevel: 'mirror', devices: '', add_storage: true })

    // Delete confirm
    const showDeleteConfirm = ref(false)
    const deletingStorage = ref(null)
    const deletingStorageInProgress = ref(false)

    // ── Constants ─────────────────────────────────────────────────────────────
    const storageTypes = [
      { value: 'dir', label: 'Directory' },
      { value: 'lvm', label: 'LVM' },
      { value: 'lvmthin', label: 'LVM-Thin' },
      { value: 'zfspool', label: 'ZFS' },
      { value: 'nfs', label: 'NFS' },
      { value: 'cifs', label: 'SMB/CIFS' },
      { value: 'rbd', label: 'RBD (Ceph)' },
    ]

    const contentTypes = [
      { value: 'images', label: 'VM Images' },
      { value: 'rootdir', label: 'Container Volumes' },
      { value: 'vztmpl', label: 'CT Templates' },
      { value: 'backup', label: 'Backups' },
      { value: 'snippets', label: 'Snippets' },
      { value: 'iso', label: 'ISO Images' },
    ]

    const vmContentTypes = [
      { value: 'images', label: 'VM Images' },
      { value: 'rootdir', label: 'Container Volumes' },
    ]

    // ── Computed ──────────────────────────────────────────────────────────────
    const cephHealth = computed(() => {
      if (!cephStatus.value) return 'UNKNOWN'
      return cephStatus.value.health?.status || cephStatus.value.health?.overall_status || 'UNKNOWN'
    })

    const cephHealthBadge = computed(() => {
      const h = cephHealth.value
      if (h === 'HEALTH_OK') return 'badge-success'
      if (h === 'HEALTH_WARN') return 'badge-warning'
      if (h === 'HEALTH_ERR') return 'badge-danger'
      return 'badge-secondary'
    })

    const cephPgsClean = computed(() => {
      if (!cephStatus.value?.pgmap?.pgs_by_state) return '—'
      const cleanState = cephStatus.value.pgmap.pgs_by_state.find(s => s.state_name === 'active+clean')
      return cleanState ? cleanState.count : 0
    })

    const flatOsds = computed(() => {
      // Proxmox returns nested: { nodes: [ { opsd: [{...}] } ] } or flat array
      if (!cephOsds.value) return []
      if (Array.isArray(cephOsds.value)) {
        const result = []
        for (const item of cephOsds.value) {
          if (item.osd !== undefined) {
            result.push({ id: item.osd, ...item })
          } else if (item.osds) {
            result.push(...item.osds.map(o => ({ host: item.name, ...o, id: o.osd })))
          } else {
            result.push(item)
          }
        }
        return result
      }
      return []
    })

    // ── Methods ───────────────────────────────────────────────────────────────
    const loadHosts = async () => {
      loadingHosts.value = true
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = res.data || []
      } catch {
        toast.error('Failed to load Proxmox hosts')
      } finally {
        loadingHosts.value = false
      }
    }

    const loadNodes = async () => {
      if (!selectedHostId.value) { nodes.value = []; return }
      loadingNodes.value = true
      try {
        const res = await api.proxmox.listNodes(selectedHostId.value)
        nodes.value = res.data || []
        if (nodes.value.length === 1) selectedNode.value = nodes.value[0].node
      } catch {
        nodes.value = []
      } finally {
        loadingNodes.value = false
      }
    }

    const onHostChange = () => {
      selectedNode.value = ''
      storagePools.value = []
      zfsPools.value = []
      cephConfigured.value = false
      cephStatus.value = null
      storageError.value = ''
      zfsError.value = ''
      loadNodes()
      if (activeTab.value === 'overview') loadStorage()
    }

    const onNodeChange = () => {
      if (activeTab.value === 'zfs') loadZfs()
      if (activeTab.value === 'ceph') loadCeph()
    }

    const loadStorage = async () => {
      if (!selectedHostId.value) return
      loadingStorage.value = true
      storageError.value = ''
      try {
        // Use cluster-wide storage list
        const res = await api.storage.list(selectedHostId.value)
        storagePools.value = res.data || []
      } catch {
        // Fallback: per-node storage query using first available node
        try {
          const fallbackNode = nodes.value[0]?.node
          if (fallbackNode) {
            const res2 = await api.pveNode.listStorage(selectedHostId.value, fallbackNode)
            storagePools.value = res2.data || []
          } else {
            storageError.value = 'No nodes available to query storage'
          }
        } catch (e) {
          storageError.value = e.response?.data?.detail || 'Failed to load storage pools'
        }
      } finally {
        loadingStorage.value = false
      }
    }

    const loadZfs = async () => {
      if (!selectedHostId.value || !selectedNode.value) return
      loadingZfs.value = true
      zfsError.value = ''
      zfsPools.value = []
      expandedPools.value = new Set()
      poolDetails.value = {}
      try {
        const res = await api.storage.getZfsPools(selectedHostId.value, selectedNode.value)
        zfsPools.value = res.data || []
      } catch (e) {
        zfsError.value = e.response?.data?.detail || 'Failed to load ZFS pools (ZFS may not be installed on this node)'
      } finally {
        loadingZfs.value = false
      }
    }

    const loadCeph = async () => {
      if (!selectedHostId.value || !selectedNode.value) return
      loadingCeph.value = true
      cephConfigured.value = false
      cephStatus.value = null
      try {
        const res = await api.storage.getCephStatus(selectedHostId.value, selectedNode.value)
        cephStatus.value = res.data
        cephConfigured.value = true
        loadCephDetails()
      } catch {
        cephConfigured.value = false
      } finally {
        loadingCeph.value = false
      }
    }

    const loadCephDetails = async () => {
      loadingCephMons.value = true
      loadingCephOsds.value = true
      loadingCephPools.value = true

      try {
        const [monsRes, osdsRes, poolsRes] = await Promise.allSettled([
          api.storage.getCephMons(selectedHostId.value, selectedNode.value),
          api.storage.getCephOsds(selectedHostId.value, selectedNode.value),
          api.storage.getCephPools(selectedHostId.value, selectedNode.value),
        ])
        if (monsRes.status === 'fulfilled') cephMons.value = monsRes.value.data || []
        if (osdsRes.status === 'fulfilled') cephOsds.value = osdsRes.value.data || []
        if (poolsRes.status === 'fulfilled') cephPools.value = poolsRes.value.data || []
      } finally {
        loadingCephMons.value = false
        loadingCephOsds.value = false
        loadingCephPools.value = false
      }
    }

    const togglePoolExpand = async (name) => {
      const newSet = new Set(expandedPools.value)
      if (newSet.has(name)) {
        newSet.delete(name)
      } else {
        newSet.add(name)
        if (!poolDetails.value[name]) {
          loadingPoolDetail.value = { ...loadingPoolDetail.value, [name]: true }
          try {
            const res = await api.storage.getZfsPool(selectedHostId.value, selectedNode.value, name)
            poolDetails.value = { ...poolDetails.value, [name]: res.data }
          } catch {
            poolDetails.value = { ...poolDetails.value, [name]: null }
          } finally {
            loadingPoolDetail.value = { ...loadingPoolDetail.value, [name]: false }
          }
        }
      }
      expandedPools.value = newSet
    }

    const getVdevs = (poolName) => {
      const detail = poolDetails.value[poolName]
      if (!detail) return []
      // Proxmox returns: { children: [...] } or { vdevs: [...] }
      return detail.children || detail.vdevs || []
    }

    const scrubPool = async (pool) => {
      scrubbingPool.value = pool.name
      try {
        await api.storage.scrubZfsPool(selectedHostId.value, selectedNode.value, pool.name)
        toast.success(`Scrub started for pool ${pool.name}`)
      } catch (e) {
        toast.error(e.response?.data?.detail || `Failed to start scrub for ${pool.name}`)
      } finally {
        scrubbingPool.value = ''
      }
    }

    const openCreateModal = () => {
      editingStorage.value = null
      selectedContentTypes.value = []
      storageForm.value = { type: 'dir', storage: '', shared: false, sparse: false }
      showStorageModal.value = true
    }

    const editStorage = (s) => {
      editingStorage.value = s
      storageForm.value = { ...s }
      selectedContentTypes.value = s.content ? s.content.split(',').map(c => c.trim()) : []
      showStorageModal.value = true
    }

    const closeStorageModal = () => {
      showStorageModal.value = false
      editingStorage.value = null
    }

    const saveStorage = async () => {
      if (!storageForm.value.storage) {
        toast.error('Storage ID is required')
        return
      }
      savingStorage.value = true
      try {
        const payload = {
          ...storageForm.value,
          content: selectedContentTypes.value.join(','),
        }
        if (editingStorage.value) {
          await api.storage.update(selectedHostId.value, storageForm.value.storage, payload)
          toast.success('Storage updated')
        } else {
          await api.storage.create(selectedHostId.value, payload)
          toast.success('Storage created')
        }
        closeStorageModal()
        await loadStorage()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to save storage')
      } finally {
        savingStorage.value = false
      }
    }

    const toggleStorage = async (s) => {
      try {
        const enabled = s.enabled === false ? 1 : 0
        await api.storage.update(selectedHostId.value, s.storage, { enabled })
        toast.success(`Storage ${enabled ? 'enabled' : 'disabled'}`)
        await loadStorage()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to toggle storage')
      }
    }

    const confirmDeleteStorage = (s) => {
      deletingStorage.value = s
      showDeleteConfirm.value = true
    }

    const deleteStorage = async () => {
      if (!deletingStorage.value) return
      deletingStorageInProgress.value = true
      try {
        await api.storage.delete(selectedHostId.value, deletingStorage.value.storage)
        toast.success(`Storage ${deletingStorage.value.storage} deleted`)
        showDeleteConfirm.value = false
        deletingStorage.value = null
        await loadStorage()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to delete storage')
      } finally {
        deletingStorageInProgress.value = false
      }
    }

    const openCreateZfsModal = () => {
      zfsForm.value = { name: '', raidlevel: 'mirror', devices: '', add_storage: true }
      showZfsModal.value = true
    }

    const closeZfsModal = () => { showZfsModal.value = false }

    const createZfsPool = async () => {
      if (!zfsForm.value.name || !zfsForm.value.devices) {
        toast.error('Pool name and devices are required')
        return
      }
      creatingZfs.value = true
      try {
        const payload = {
          name: zfsForm.value.name,
          raidlevel: zfsForm.value.raidlevel,
          devices: zfsForm.value.devices,
          'add_storage': zfsForm.value.add_storage ? 1 : 0,
        }
        await api.storage.createZfsPool(selectedHostId.value, selectedNode.value, payload)
        toast.success(`ZFS pool ${zfsForm.value.name} creation started`)
        closeZfsModal()
        await loadZfs()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to create ZFS pool')
      } finally {
        creatingZfs.value = false
      }
    }

    const refresh = () => {
      if (activeTab.value === 'overview') loadStorage()
      if (activeTab.value === 'zfs') loadZfs()
      if (activeTab.value === 'ceph') loadCeph()
    }

    // ── Formatters / helpers ─────────────────────────────────────────────────
    const formatBytes = (bytes) => {
      if (!bytes && bytes !== 0) return '—'
      if (bytes === 0) return '0 B'
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return (bytes / Math.pow(1024, i)).toFixed(i > 1 ? 1 : 0) + ' ' + sizes[i]
    }

    const usagePct = (used, total) => {
      if (!total || total === 0) return 0
      return Math.round((used / total) * 100)
    }

    const usageClass = (used, total) => {
      const pct = usagePct(used, total)
      if (pct >= 80) return 'usage-red'
      if (pct >= 60) return 'usage-amber'
      return 'usage-green'
    }

    const parseContent = (content) => {
      if (!content) return []
      return content.split(',').map(c => c.trim()).filter(Boolean)
    }

    const zfsStatusBadge = (status) => {
      if (!status) return 'badge-secondary'
      const s = status.toUpperCase()
      if (s === 'ONLINE') return 'badge-success'
      if (s === 'DEGRADED') return 'badge-warning'
      if (s === 'FAULTED' || s === 'UNAVAIL') return 'badge-danger'
      if (s === 'OFFLINE') return 'badge-secondary'
      return 'badge-secondary'
    }

    const osdStatusBadge = (up, inn) => {
      if (up && inn) return 'badge-success'
      if (up && !inn) return 'badge-warning'
      return 'badge-danger'
    }

    // ── Watch tab change ─────────────────────────────────────────────────────
    watch(activeTab, (tab) => {
      if (tab === 'overview' && selectedHostId.value) loadStorage()
      if (tab === 'zfs' && selectedHostId.value && selectedNode.value) loadZfs()
      if (tab === 'ceph' && selectedHostId.value && selectedNode.value) loadCeph()
    })

    onMounted(loadHosts)

    return {
      activeTab, hosts, nodes, loadingHosts, loadingNodes,
      selectedHostId, selectedNode,
      storagePools, loadingStorage, storageError,
      zfsPools, loadingZfs, zfsError, expandedPools, poolDetails,
      loadingPoolDetail, scrubbingPool,
      cephConfigured, loadingCeph, cephStatus, cephMons, cephOsds, cephPools,
      loadingCephMons, loadingCephOsds, loadingCephPools,
      showStorageModal, editingStorage, savingStorage, storageForm, selectedContentTypes,
      showZfsModal, creatingZfs, zfsForm,
      showDeleteConfirm, deletingStorage, deletingStorageInProgress,
      storageTypes, contentTypes, vmContentTypes,
      cephHealth, cephHealthBadge, cephPgsClean, flatOsds,
      onHostChange, onNodeChange, refresh,
      loadStorage, loadZfs, loadCeph,
      togglePoolExpand, getVdevs, scrubPool,
      openCreateModal, editStorage, closeStorageModal, saveStorage,
      toggleStorage, confirmDeleteStorage, deleteStorage,
      openCreateZfsModal, closeZfsModal, createZfsPool,
      formatBytes, usagePct, usageClass, parseContent,
      zfsStatusBadge, osdStatusBadge,
    }
  }
}
</script>

<style scoped>
.storage-management {
  padding: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.page-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary, #1e293b);
  margin: 0 0 0.25rem;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

/* Cards */
.card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.75rem;
  margin-bottom: 1.25rem;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  gap: 0.75rem;
  flex-wrap: wrap;
}

.card-header h2 {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary, #1e293b);
}

/* Selector */
.selector-card {
  padding: 1rem 1.25rem;
}

.selector-row {
  display: flex;
  gap: 1.25rem;
  flex-wrap: wrap;
  align-items: flex-end;
}

.selector-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 220px;
  flex: 1;
}

/* Tab bar */
.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 1.25rem;
  border-bottom: 2px solid var(--border-color, #e2e8f0);
}

.tab-btn {
  padding: 0.65rem 1.25rem;
  background: none;
  border: none;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-muted, #64748b);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover { color: var(--text-primary, #1e293b); }
.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

/* Tables */
.table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.data-table th {
  padding: 0.65rem 1rem;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #64748b);
  background: var(--table-header-bg, #f8fafc);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  white-space: nowrap;
}

.data-table td {
  padding: 0.65rem 1rem;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  vertical-align: middle;
}

.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: var(--hover-bg, #f8fafc); }

/* Storage-specific cells */
.storage-name { font-weight: 600; }

.type-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.3rem;
  font-size: 0.75rem;
  font-weight: 600;
  background: #e2e8f0;
  color: #475569;
}

.type-zfspool, .type-zfs { background: #dbeafe; color: #1d4ed8; }
.type-dir { background: #d1fae5; color: #065f46; }
.type-lvm, .type-lvmthin { background: #fef3c7; color: #92400e; }
.type-nfs, .type-cifs { background: #ede9fe; color: #5b21b6; }
.type-rbd { background: #fee2e2; color: #991b1b; }

.content-cell { max-width: 200px; }
.content-tag {
  display: inline-block;
  background: var(--tag-bg, #f1f5f9);
  color: var(--text-secondary, #475569);
  border-radius: 0.25rem;
  padding: 0.1rem 0.4rem;
  font-size: 0.7rem;
  margin: 0.1rem 0.1rem 0.1rem 0;
  white-space: nowrap;
}

.usage-cell { min-width: 200px; }

.usage-bar-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.usage-bar {
  width: 100%;
  height: 6px;
  background: var(--bar-bg, #e2e8f0);
  border-radius: 3px;
  overflow: hidden;
}

.usage-bar-lg {
  height: 8px;
}

.usage-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.usage-green { background: #22c55e; }
.usage-amber { background: #f59e0b; }
.usage-red { background: #ef4444; }

.usage-text {
  font-size: 0.75rem;
  color: var(--text-muted, #64748b);
  white-space: nowrap;
}

/* Actions */
.actions-cell {
  display: flex;
  gap: 0.4rem;
  white-space: nowrap;
}

.btn-icon {
  background: none;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.375rem;
  padding: 0.3rem 0.5rem;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--text-secondary, #475569);
  transition: background 0.15s, color 0.15s;
}

.btn-icon:hover { background: var(--hover-bg, #f1f5f9); color: var(--text-primary, #1e293b); }

.btn-icon-danger { color: #dc2626; }
.btn-icon-danger:hover { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }

/* Empty / loading states */
.empty-placeholder, .loading-state, .error-state {
  padding: 2.5rem;
  text-align: center;
}

.loading-state-sm { padding: 1rem 1.25rem; color: var(--text-muted, #64748b); font-size: 0.875rem; }
.empty-state { padding: 1.5rem; text-align: center; color: var(--text-muted, #64748b); font-size: 0.875rem; }

/* Badges */
.badge {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
}

.badge-success { background: #dcfce7; color: #15803d; }
.badge-warning { background: #fef9c3; color: #a16207; }
.badge-danger { background: #fee2e2; color: #dc2626; }
.badge-secondary { background: #f1f5f9; color: #475569; }

/* ZFS pool cards */
.zfs-pool-card {
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.5rem;
  margin: 1rem 1.25rem;
  overflow: hidden;
}

.zfs-pool-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1rem;
  cursor: pointer;
  background: var(--table-header-bg, #f8fafc);
  flex-wrap: wrap;
  gap: 0.75rem;
  transition: background 0.15s;
}

.zfs-pool-header:hover { background: var(--hover-bg, #f1f5f9); }

.zfs-pool-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.zfs-pool-name {
  font-weight: 600;
  font-size: 0.95rem;
}

.zfs-pool-stats {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.stat {
  font-size: 0.8rem;
  color: var(--text-muted, #64748b);
}

.stat strong {
  color: var(--text-secondary, #475569);
}

.zfs-pool-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.expand-icon {
  font-size: 0.75rem;
  color: var(--text-muted, #64748b);
}

.zfs-usage-bar-wrap {
  padding: 0.5rem 1rem;
  background: var(--card-bg, #fff);
}

.vdev-tree {
  padding: 0.75rem 1rem;
  background: var(--card-bg, #fff);
  border-top: 1px solid var(--border-color, #e2e8f0);
}

.vdev-row {
  margin-bottom: 0.75rem;
}

.vdev-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--text-secondary, #475569);
  margin-bottom: 0.35rem;
}

.vdev-name { font-family: monospace; }

.vdev-children {
  margin-left: 1.25rem;
  border-left: 2px solid var(--border-color, #e2e8f0);
  padding-left: 0.75rem;
}

.vdev-disk-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.25rem 0;
  font-size: 0.8rem;
}

.disk-path { font-family: monospace; color: var(--text-secondary, #475569); }
.disk-errors { font-size: 0.72rem; }

/* Ceph */
.ceph-not-configured {
  padding: 0;
}

.ceph-not-configured-inner {
  padding: 3rem;
  text-align: center;
  max-width: 580px;
  margin: 0 auto;
}

.ceph-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.ceph-not-configured-inner h3 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
}

.ceph-setup-info {
  background: var(--table-header-bg, #f8fafc);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  text-align: left;
  margin: 1rem 0;
}

.setup-steps {
  margin: 0.5rem 0 0;
  padding-left: 1.25rem;
  font-size: 0.875rem;
  color: var(--text-muted, #64748b);
}

.setup-steps li { margin-bottom: 0.35rem; }

.ceph-health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 1rem;
  padding: 1rem 1.25rem;
}

.ceph-stat-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.ceph-stat-label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #64748b);
}

.ceph-stat-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary, #1e293b);
}

/* Forms */
.form-group { margin-bottom: 1rem; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.form-label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary, #475569);
  margin-bottom: 0.35rem;
}

.required { color: #ef4444; }

.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.4rem;
  font-size: 0.875rem;
  background: var(--input-bg, #fff);
  color: var(--text-primary, #1e293b);
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-hint { font-size: 0.75rem; color: var(--text-muted, #64748b); margin-top: 0.25rem; }

.checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-secondary, #475569);
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.35rem;
  background: var(--card-bg, #fff);
  transition: background 0.15s;
}

.checkbox-label:hover { background: var(--hover-bg, #f1f5f9); }

.form-toggle { display: flex; align-items: center; justify-content: space-between; }
.toggle-input { width: 1rem; height: 1rem; cursor: pointer; }

/* Type tabs (storage modal) */
.type-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 1.25rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

.type-tab {
  padding: 0.35rem 0.85rem;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.35rem;
  background: var(--card-bg, #fff);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  color: var(--text-secondary, #475569);
  transition: all 0.15s;
}

.type-tab:hover { background: var(--hover-bg, #f1f5f9); }
.type-tab.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }

/* Buttons */
.btn {
  padding: 0.5rem 1rem;
  border-radius: 0.4rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-secondary { background: var(--button-bg, #f1f5f9); color: var(--text-primary, #1e293b); border: 1px solid var(--border-color, #e2e8f0); }
.btn-secondary:hover:not(:disabled) { background: var(--hover-bg, #e2e8f0); }
.btn-danger { background: #ef4444; color: #fff; }
.btn-danger:hover:not(:disabled) { background: #dc2626; }
.btn-sm { padding: 0.3rem 0.65rem; font-size: 0.8rem; }

/* Modal */
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

.modal {
  background: var(--card-bg, #fff);
  border-radius: 0.75rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  width: 100%;
  max-width: 560px;
  max-height: 85vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.modal-lg { max-width: 720px; }
.modal-sm { max-width: 420px; }

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  flex-shrink: 0;
}

.modal-header h2 { font-size: 1.1rem; font-weight: 600; margin: 0; }

.modal-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-muted, #64748b);
  line-height: 1;
  padding: 0;
}

.modal-close:hover { color: var(--text-primary, #1e293b); }

.modal-body { padding: 1.5rem; flex: 1; overflow-y: auto; }
.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color, #e2e8f0);
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  flex-shrink: 0;
}

/* Text utilities */
.text-muted { color: var(--text-muted, #64748b); }
.text-danger { color: #dc2626; }
.text-sm { font-size: 0.8rem; }
.text-mono { font-family: monospace; font-size: 0.8rem; }

@media (max-width: 768px) {
  .storage-management { padding: 1rem; }
  .page-header { flex-direction: column; }
  .form-grid { grid-template-columns: 1fr; }
  .selector-item { min-width: 100%; }
  .zfs-pool-header { flex-direction: column; align-items: flex-start; }
  .ceph-health-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
