<template>
  <div class="vms-page">
    <!-- Tab Toggle -->
    <div class="tab-bar">
      <button
        :class="['tab-btn', activeTab === 'managed' ? 'tab-btn-active' : '']"
        @click="switchTab('managed')"
      >
        Depl0y Managed
      </button>
      <button
        :class="['tab-btn', activeTab === 'all' ? 'tab-btn-active' : '']"
        @click="switchTab('all')"
      >
        All Proxmox VMs
      </button>
    </div>

    <!-- ===== DEPL0Y MANAGED TAB ===== -->
    <div v-if="activeTab === 'managed'" class="card">
      <div class="card-header">
        <h3>Virtual Machines</h3>
        <router-link to="/vms/create" class="btn btn-primary">+ Create VM</router-link>
      </div>

      <!-- Managed tab error banner -->
      <div v-if="managedError" class="error-banner-inline">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <span>{{ managedError }}</span>
        <button @click="fetchVMs" class="btn btn-sm btn-outline" style="margin-left:auto">Retry</button>
      </div>

      <!-- Search + Filter Bar -->
      <div class="filter-bar">
        <div class="filter-info" style="flex-wrap: wrap; gap: 0.5rem;">
          <input
            v-model="managedSearch"
            type="text"
            placeholder="Search by name, VMID, node…"
            class="form-control"
            style="width: 220px;"
            :disabled="loading"
          />
          <select v-model="managedStatusFilter" class="form-control" style="width: 140px;" :disabled="loading">
            <option value="">All statuses</option>
            <option value="running">Running</option>
            <option value="stopped">Stopped</option>
            <option value="paused">Paused</option>
          </select>
          <select v-model="managedNodeFilter" class="form-control" style="width: 140px;" :disabled="loading">
            <option value="">All nodes</option>
            <option v-for="n in managedNodes" :key="n" :value="n">{{ n }}</option>
          </select>
          <span class="filter-count">Showing {{ filteredVMs.length }} of {{ vms.length }} VM{{ vms.length !== 1 ? 's' : '' }}</span>
        </div>
        <div class="filter-actions">
          <button v-if="managedSearch || managedStatusFilter || managedNodeFilter || statusFilter" @click="clearFilter" class="btn btn-sm btn-secondary">Clear</button>
        </div>
      </div>

      <SkeletonLoader v-if="loading" type="table" :count="8" />

      <div v-else-if="filteredVMs.length === 0 && vms.length === 0 && !managedError" class="empty-state">
        <div class="empty-icon-wrap">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
        </div>
        <h4 class="empty-title">No virtual machines found</h4>
        <p class="empty-subtitle">Deploy your first VM to get started with Depl0y.</p>
        <router-link to="/vms/create" class="btn btn-primary">+ Create VM</router-link>
      </div>

      <div v-else-if="filteredVMs.length === 0 && !managedError" class="empty-state">
        <div class="empty-icon-wrap">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </div>
        <h4 class="empty-title">No VMs match your filters</h4>
        <p class="empty-subtitle">Try adjusting the search query or status filter.</p>
        <button @click="clearFilter" class="btn btn-outline">Clear Filters</button>
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th @click="sortBy('vmid')" class="sortable">
                VMID
                <span class="sort-indicator" v-if="sortField === 'vmid'">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th @click="sortBy('name')" class="sortable">
                Name
                <span class="sort-indicator" v-if="sortField === 'name'">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th @click="sortBy('node')" class="sortable">
                Node
                <span class="sort-indicator" v-if="sortField === 'node'">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th>Resources</th>
              <th @click="sortBy('status')" class="sortable">
                Status
                <span class="sort-indicator" v-if="sortField === 'status'">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="vm in filteredVMs" :key="vm.vmid">
              <td><strong>{{ vm.vmid }}</strong></td>
              <td>
                {{ vm.name }}
                <span v-if="vm.description" class="notes-chip ml-1" :title="vm.description">📝</span>
              </td>
              <td>
                <span class="badge badge-info">{{ vm.node }}</span>
              </td>
              <td class="text-sm">
                {{ vm.cpus }} CPU / {{ formatBytes(vm.maxmem) }} RAM / {{ formatBytes(vm.maxdisk) }} Disk
              </td>
              <td>
                <span :class="['badge', getStatusBadgeClass(vm.status)]">
                  {{ vm.status }}
                </span>
              </td>
              <td @click.stop>
                <div class="flex gap-1 vm-actions" style="align-items:center;">
                  <button v-if="vm.status === 'running'" @click="stopVM(vm.vmid, vm.node)" class="btn btn-warning btn-sm">Stop</button>
                  <button v-if="vm.status === 'running'" @click="restartVM(vm.vmid, vm.node)" class="btn btn-info btn-sm">Restart</button>
                  <button v-if="vm.status === 'stopped'" @click="startVM(vm.vmid, vm.node)" class="btn btn-primary btn-sm">Start</button>
                  <button v-if="vm.status === 'suspended'" @click="resumeVm(adaptManagedVm(vm))" class="btn btn-primary btn-sm">Resume</button>
                  <button class="btn btn-outline btn-sm btn-console" @click="openConsole(adaptManagedVm(vm))" title="Open Console">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:2px;"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                    Console
                  </button>
                  <div class="more-menu-wrap">
                    <button class="btn btn-outline btn-sm" @click.stop="toggleMoreMenu('m-'+vm.vmid)" title="More actions">⋮</button>
                    <div v-if="openMoreMenuKey === 'm-'+vm.vmid" class="more-menu">
                      <button @click="openSnapshotModal(adaptManagedVm(vm)); openMoreMenuKey = null">📷 Snapshot</button>
                      <button @click="openCloneModal(adaptManagedVm(vm)); openMoreMenuKey = null">📋 Clone</button>
                      <button @click="openMigrateModal(adaptManagedVm(vm)); openMoreMenuKey = null">🚀 Migrate</button>
                      <button v-if="vm.status === 'running'" @click="suspendVm(adaptManagedVm(vm)); openMoreMenuKey = null">⏸ Suspend</button>
                      <button v-if="vm.status === 'running'" @click="powerOffVM(vm.vmid, vm.node); openMoreMenuKey = null">⚡ Power Off</button>
                      <button @click="showDeleteModal(vm); openMoreMenuKey = null" class="more-menu-danger">🗑 Delete</button>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ===== ALL PROXMOX VMs TAB ===== -->
    <div v-if="activeTab === 'all'" class="card">
      <div class="card-header">
        <h3>All Proxmox VMs</h3>
        <div style="display:flex;align-items:center;gap:0.5rem;">
          <span class="refresh-countdown" v-if="!allLoading">Auto-refresh in {{ allCountdown }}s</span>
          <button @click="exportCSV" class="btn btn-outline btn-sm" title="Export visible VMs as CSV">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:3px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Export CSV
          </button>
          <button @click="fetchAllProxmoxVMs(true)" class="btn btn-secondary" :disabled="allLoading">
            {{ allLoading ? 'Refreshing…' : 'Refresh' }}
          </button>
        </div>
      </div>

      <!-- Search / Filter Bar -->
      <div class="filter-bar">
        <div class="filter-info" style="flex-wrap: wrap; gap: 0.5rem;">
          <input
            v-model="allSearch"
            type="text"
            placeholder="Search by name, node or host…"
            class="form-control"
            style="width: 220px;"
          />
          <select v-model="allStatusFilter" class="form-control" style="width: 140px;">
            <option value="">All statuses</option>
            <option value="running">Running</option>
            <option value="stopped">Stopped</option>
            <option value="paused">Paused</option>
          </select>

          <!-- Filter Presets -->
          <div class="preset-wrap">
            <select class="form-control" style="width: 155px;" @change="applyPreset($event.target.value); $event.target.value = ''">
              <option value="">Load preset…</option>
              <optgroup label="Built-in">
                <option value="__running__">All Running</option>
                <option value="__stopped__">All Stopped</option>
                <option value="__all__">Clear Filters</option>
              </optgroup>
              <optgroup v-if="savedFilterPresets.length > 0" label="Saved">
                <option v-for="p in savedFilterPresets" :key="p.name" :value="'__saved__' + p.name">{{ p.name }}</option>
              </optgroup>
            </select>
            <button class="btn btn-sm btn-outline" title="Save current filter as preset" @click="openSavePresetModal">Save</button>
          </div>

          <!-- Column Visibility Toggle -->
          <div class="col-toggle-wrap" style="position:relative;">
            <button class="btn btn-sm btn-outline" @click="showColMenu = !showColMenu" title="Toggle columns">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:3px;"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
              Columns
            </button>
            <div v-if="showColMenu" class="col-menu" @click.stop>
              <div class="col-menu-header">Toggle Columns</div>
              <label v-for="col in allColumns" :key="col.key" class="col-menu-item">
                <input type="checkbox" v-model="visibleColumns[col.key]" @change="saveColumnPrefs" />
                {{ col.label }}
              </label>
            </div>
          </div>

          <!-- Group by Node toggle -->
          <label class="toggle-label">
            <input type="checkbox" v-model="groupByNode" @change="saveColumnPrefs" />
            Group by node
          </label>

          <label class="toggle-label" style="margin-left:8px;">
            <input type="checkbox" v-model="showTemplates" />
            Show templates<span v-if="templateCount > 0"> ({{ templateCount }})</span>
          </label>

          <span class="filter-count">Showing {{ filteredAllVMs.length }} of {{ allVMs.length }} VM{{ allVMs.length !== 1 ? 's' : '' }}</span>
        </div>
        <button v-if="allSearch || allStatusFilter || activeTagFilters.size > 0" @click="allSearch = ''; allStatusFilter = ''; activeTagFilters = new Set()" class="btn btn-sm btn-secondary">
          Clear
        </button>
      </div>

      <!-- Advanced Filter Panel -->
      <div class="adv-filter-bar">
        <button class="adv-filter-toggle" @click="showAdvFilter = !showAdvFilter">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:4px;"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
          Advanced Filters
          <span v-if="advFilterCount > 0" class="adv-filter-badge">{{ advFilterCount }}</span>
          <span class="adv-filter-arrow">{{ showAdvFilter ? '▲' : '▼' }}</span>
        </button>
        <div v-if="showAdvFilter" class="adv-filter-panel">
          <div class="adv-filter-grid">
            <!-- Filter by Host -->
            <div class="adv-filter-field">
              <label>Host</label>
              <select v-model="advFilter.hostId" class="form-control">
                <option value="">All hosts</option>
                <option v-for="h in uniqueHosts" :key="h.id" :value="h.id">{{ h.name }}</option>
              </select>
            </div>
            <!-- Filter by Node -->
            <div class="adv-filter-field">
              <label>Node</label>
              <select v-model="advFilter.node" class="form-control">
                <option value="">All nodes</option>
                <option v-for="n in uniqueNodes" :key="n" :value="n">{{ n }}</option>
              </select>
            </div>
            <!-- Filter by OS type -->
            <div class="adv-filter-field">
              <label>OS Type</label>
              <select v-model="advFilter.osType" class="form-control">
                <option value="">Any OS</option>
                <option value="linux">Linux</option>
                <option value="windows">Windows</option>
                <option value="bsd">BSD</option>
                <option value="other">Other</option>
              </select>
            </div>
            <!-- CPU cores -->
            <div class="adv-filter-field">
              <label>Min CPUs</label>
              <input v-model.number="advFilter.minCpus" type="number" min="0" class="form-control" placeholder="0" />
            </div>
            <!-- RAM range -->
            <div class="adv-filter-field">
              <label>Min RAM (GB)</label>
              <input v-model.number="advFilter.minRamGb" type="number" min="0" step="0.5" class="form-control" placeholder="0" />
            </div>
            <div class="adv-filter-field">
              <label>Max RAM (GB)</label>
              <input v-model.number="advFilter.maxRamGb" type="number" min="0" step="0.5" class="form-control" placeholder="∞" />
            </div>
          </div>

          <!-- Tag multi-select -->
          <div class="adv-filter-tags" v-if="allTagList.length > 0">
            <label class="adv-filter-tags-label">Filter by tags (must have all selected):</label>
            <div class="adv-filter-tag-pills">
              <button
                v-for="tag in allTagList"
                :key="tag"
                :class="['tag-filter-pill', activeTagFilters.has(tag) ? 'tag-filter-pill-active' : '']"
                :style="activeTagFilters.has(tag) ? { backgroundColor: tagColor(tag), color: '#fff', borderColor: tagColor(tag) } : { borderColor: tagColor(tag), color: tagColor(tag) }"
                @click="toggleTagFilter(tag)"
              >{{ tag }}</button>
              <button v-if="activeTagFilters.size > 0" class="btn btn-sm btn-secondary" @click="activeTagFilters = new Set()">Clear tags</button>
            </div>
          </div>

          <div style="display:flex;gap:0.5rem;margin-top:0.75rem;">
            <button @click="clearAdvFilter" class="btn btn-sm btn-outline">Clear Advanced Filters</button>
          </div>
        </div>
      </div>

      <!-- Classic Tag Filter Pills (shown when adv panel is closed and tags exist) -->
      <div v-if="!showAdvFilter && allTagList.length > 0" class="tag-filter-bar">
        <span class="tag-filter-label">Filter by tag:</span>
        <button
          v-for="tag in allTagList"
          :key="tag"
          :class="['tag-filter-pill', activeTagFilters.has(tag) ? 'tag-filter-pill-active' : '']"
          :style="activeTagFilters.has(tag) ? { backgroundColor: tagColor(tag), color: '#fff', borderColor: tagColor(tag) } : { borderColor: tagColor(tag), color: tagColor(tag) }"
          @click="toggleTagFilter(tag)"
        >{{ tag }}</button>
        <button v-if="activeTagFilters.size > 0" class="btn btn-sm btn-secondary" @click="activeTagFilters = new Set()">Clear tags</button>
      </div>

      <!-- Save Preset Modal -->
      <div v-if="showSavePresetModal" class="modal-overlay" @click.self="showSavePresetModal = false">
        <div class="modal-content" @click.stop style="max-width: 360px;">
          <div class="modal-header">
            <h3>Save Filter Preset</h3>
            <button @click="showSavePresetModal = false" class="btn-close">×</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>Preset Name <span class="text-danger">*</span></label>
              <input v-model="newPresetName" type="text" class="form-control" placeholder="e.g. Production Running" @keyup.enter="savePreset" />
            </div>
            <p class="text-muted text-sm">Current filter: status="{{ allStatusFilter || 'all' }}" search="{{ allSearch }}"</p>
          </div>
          <div class="modal-footer">
            <button @click="showSavePresetModal = false" class="btn btn-secondary">Cancel</button>
            <button @click="savePreset" class="btn btn-primary" :disabled="!newPresetName.trim()">Save</button>
          </div>
        </div>
      </div>

      <!-- All tab error banner -->
      <div v-if="allError" class="error-banner-inline" style="margin: 0.75rem 1rem;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <span>{{ allError }}</span>
        <button @click="fetchAllProxmoxVMs(true)" class="btn btn-sm btn-outline" style="margin-left:auto">Retry</button>
      </div>

      <!-- Partial failure / timeout warning -->
      <div v-if="allPartialFailedHosts.length > 0 && !allError" class="warning-banner-inline" style="margin: 0.5rem 1rem;">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        <span>
          <strong>{{ allPartialFailedHosts.length }} host{{ allPartialFailedHosts.length !== 1 ? 's' : '' }} unreachable:</strong>
          {{ allPartialFailedHosts.join(', ') }} — results may be incomplete.
        </span>
      </div>
      <div v-if="allTimeoutWarning && !allError" class="warning-banner-inline" style="margin: 0.5rem 1rem;">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        <span>Some hosts are responding slowly — data shown may be incomplete.</span>
        <button @click="allTimeoutWarning = false" class="btn-inline-close-sm">×</button>
      </div>

      <SkeletonLoader v-if="allLoading" type="table" :count="8" />

      <div v-else-if="!allError && allVMs.length === 0" class="empty-state-flat">
        <div class="empty-icon-wrap">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
        </div>
        <h4 class="empty-title">No Proxmox VMs found</h4>
        <p class="empty-subtitle">Make sure at least one Proxmox host is configured and reachable.</p>
        <button @click="fetchAllProxmoxVMs(true)" class="btn btn-outline btn-sm">Refresh</button>
      </div>

      <div v-else-if="!allError && filteredAllVMs.length === 0 && allVMs.length > 0" class="empty-state-flat">
        <div class="empty-icon-wrap">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </div>
        <h4 class="empty-title">No VMs match your filters</h4>
        <p class="empty-subtitle">Try adjusting the search, status, or advanced filters.</p>
        <button @click="allSearch = ''; allStatusFilter = ''; activeTagFilters = new Set()" class="btn btn-outline btn-sm">Clear Filters</button>
      </div>

      <!-- Flat table -->
      <div v-else-if="!groupByNode" class="table-container" style="position:relative;">
        <table class="table">
          <thead>
            <tr>
              <th class="cb-col">
                <input
                  type="checkbox"
                  :checked="allPageSelected"
                  :indeterminate.prop="somePageSelected && !allPageSelected"
                  @change="toggleSelectAll"
                  title="Select all visible VMs"
                />
              </th>
              <th @click="allSortBy('vmid')" class="sortable">
                VMID
                <span class="sort-indicator" v-if="allSortField === 'vmid'">{{ allSortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th @click="allSortBy('name')" class="sortable">
                Name
                <span class="sort-indicator" v-if="allSortField === 'name'">{{ allSortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th @click="allSortBy('status')" class="sortable">
                Status
                <span class="sort-indicator" v-if="allSortField === 'status'">{{ allSortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th @click="allSortBy('node')" class="sortable">
                Node
                <span class="sort-indicator" v-if="allSortField === 'node'">{{ allSortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th @click="allSortBy('hostName')" class="sortable" v-if="visibleColumns.host">
                Host
                <span class="sort-indicator" v-if="allSortField === 'hostName'">{{ allSortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th v-if="visibleColumns.resources">CPU / Memory</th>
              <th v-if="visibleColumns.uptime" @click="allSortBy('uptime')" class="sortable">
                Uptime
                <span class="sort-indicator" v-if="allSortField === 'uptime'">{{ allSortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th v-if="visibleColumns.ip">IP Address</th>
              <th v-if="visibleColumns.tags && anyVmHasTags">Tags</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="vm in filteredAllVMs" :key="`${vm.hostId}-${vm.node}-${vm.vmid}`"
              :class="{ 'row-selected': selectedVmKeys.has(vmKey(vm)), 'row-clickable': true }"
              @click.exact="navigateToVM(vm)"
            >
              <td class="cb-col" @click.stop>
                <input
                  type="checkbox"
                  :checked="selectedVmKeys.has(vmKey(vm))"
                  @change="toggleSelectVm(vm)"
                />
              </td>
              <td><strong>{{ vm.vmid }}</strong></td>
              <td>
                <a class="vm-name-link" @click.stop="navigateToVM(vm)" style="cursor: pointer;">
                  {{ vm.name || '(no name)' }}
                </a>
                <span v-if="vm.description" class="notes-chip ml-1" :title="vm.description">📝</span>
              </td>
              <td>
                <span :class="['badge', getStatusBadgeClass(vm.status)]">
                  {{ vm.status }}
                </span>
              </td>
              <td>
                <span class="badge badge-info">{{ vm.node }}</span>
              </td>
              <td v-if="visibleColumns.host" class="text-sm">{{ vm.hostName }}</td>
              <td v-if="visibleColumns.resources" class="text-sm">
                {{ vm.cpus || '?' }} CPU / {{ formatBytes(vm.maxmem) }} RAM
              </td>
              <td v-if="visibleColumns.uptime" class="text-sm mono">{{ formatUptime(vm.uptime) }}</td>
              <td v-if="visibleColumns.ip" class="text-sm mono">{{ extractIP(vm) }}</td>
              <td v-if="visibleColumns.tags && anyVmHasTags">
                <div class="vm-tags">
                  <TagBadge
                    v-for="tag in parseTags(vm.tags)"
                    :key="tag"
                    :tag="tag"
                    small
                  />
                  <span v-if="!parseTags(vm.tags).length" class="text-muted text-sm">—</span>
                </div>
              </td>
              <td @click.stop>
                <div class="flex gap-1 vm-actions" style="align-items: center;">
                  <button v-if="vm.status === 'running'" @click="allShutdownVM(vm)" class="btn btn-warning btn-sm" :disabled="vm._busy">Shutdown</button>
                  <button v-if="vm.status === 'running'" @click="allStopVM(vm)" class="btn btn-danger btn-sm" :disabled="vm._busy">Stop</button>
                  <button v-if="vm.status !== 'running' && vm.status !== 'suspended'" @click="allStartVM(vm)" class="btn btn-primary btn-sm" :disabled="vm._busy">Start</button>
                  <button v-if="vm.status === 'suspended'" @click="resumeVm(vm)" class="btn btn-primary btn-sm" :disabled="vm._busy">Resume</button>
                  <button class="btn btn-outline btn-sm btn-console" title="Open Console" @click="openConsole(vm)">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:2px;"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                    Console
                  </button>
                  <div class="more-menu-wrap">
                    <button class="btn btn-outline btn-sm" @click.stop="toggleMoreMenu(vmKey(vm))" title="More actions">⋮</button>
                    <div v-if="openMoreMenuKey === vmKey(vm)" class="more-menu">
                      <button @click="openTagEditor(vm); openMoreMenuKey = null">🏷 Tags</button>
                      <button @click="openSnapshotModal(vm); openMoreMenuKey = null">📷 Snapshot</button>
                      <button @click="openCloneModal(vm); openMoreMenuKey = null">📋 Clone</button>
                      <button @click="openMigrateModal(vm); openMoreMenuKey = null">🚀 Migrate</button>
                      <button v-if="vm.status === 'running'" @click="suspendVm(vm); openMoreMenuKey = null">⏸ Suspend</button>
                      <button @click="openVmDeleteModal(vm); openMoreMenuKey = null" class="more-menu-danger">🗑 Delete</button>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Bulk Action Bar -->
        <div v-if="selectedVmKeys.size > 0" class="bulk-action-bar">
          <span class="bulk-count">{{ selectedVmKeys.size }} VM{{ selectedVmKeys.size !== 1 ? 's' : '' }} selected</span>
          <button class="btn btn-primary btn-sm" @click="bulkAction('start')" :disabled="bulkRunning">Start Selected</button>
          <button class="btn btn-warning btn-sm" @click="bulkAction('shutdown')" :disabled="bulkRunning">Shutdown Selected</button>
          <button class="btn btn-danger btn-sm" @click="bulkAction('stop')" :disabled="bulkRunning">Stop Selected</button>
          <button class="btn btn-outline btn-sm" @click="openBulkSnapshotModal" :disabled="bulkRunning" title="Create snapshot on all selected VMs">Snapshot All</button>
          <button class="btn btn-outline btn-sm" @click="openBulkTagModal" :disabled="bulkRunning" title="Apply tag to all selected VMs">Tag All</button>
          <button class="btn btn-danger btn-sm" @click="openBulkDeleteModal" :disabled="bulkRunning" title="Delete all selected VMs">Delete All</button>
          <a href="#" class="bulk-clear-link" @click.prevent="clearSelection">Clear Selection</a>
        </div>
      </div>

      <!-- Grouped by node view -->
      <div v-else class="table-container" style="position:relative;">
        <div v-for="(group, nodeName) in groupedVMs" :key="nodeName" class="node-group">
          <div class="node-group-header">
            <span class="node-group-name">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:5px;"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/></svg>
              {{ nodeName }}
            </span>
            <span class="node-group-count">{{ group.length }} VM{{ group.length !== 1 ? 's' : '' }}</span>
          </div>
          <table class="table node-group-table">
            <thead>
              <tr>
                <th class="cb-col">
                  <input type="checkbox"
                    :checked="group.every(vm => selectedVmKeys.has(vmKey(vm)))"
                    @change="toggleGroupSelect(group, $event)"
                  />
                </th>
                <th>VMID</th>
                <th>Name</th>
                <th>Status</th>
                <th v-if="visibleColumns.host">Host</th>
                <th v-if="visibleColumns.resources">CPU / Memory</th>
                <th v-if="visibleColumns.uptime">Uptime</th>
                <th v-if="visibleColumns.ip">IP Address</th>
                <th v-if="visibleColumns.tags && anyVmHasTags">Tags</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="vm in group" :key="`${vm.hostId}-${vm.node}-${vm.vmid}`"
                :class="{ 'row-selected': selectedVmKeys.has(vmKey(vm)), 'row-clickable': true }"
                @click.exact="navigateToVM(vm)"
              >
                <td class="cb-col" @click.stop>
                  <input type="checkbox" :checked="selectedVmKeys.has(vmKey(vm))" @change="toggleSelectVm(vm)" />
                </td>
                <td><strong>{{ vm.vmid }}</strong></td>
                <td>
                  <a class="vm-name-link" @click.stop="navigateToVM(vm)" style="cursor:pointer;">{{ vm.name || '(no name)' }}</a>
                  <span v-if="vm.description" class="notes-chip ml-1" :title="vm.description">📝</span>
                </td>
                <td>
                  <span :class="['badge', getStatusBadgeClass(vm.status)]">{{ vm.status }}</span>
                </td>
                <td v-if="visibleColumns.host" class="text-sm">{{ vm.hostName }}</td>
                <td v-if="visibleColumns.resources" class="text-sm">{{ vm.cpus || '?' }} CPU / {{ formatBytes(vm.maxmem) }} RAM</td>
                <td v-if="visibleColumns.uptime" class="text-sm mono">{{ formatUptime(vm.uptime) }}</td>
                <td v-if="visibleColumns.ip" class="text-sm mono">{{ extractIP(vm) }}</td>
                <td v-if="visibleColumns.tags && anyVmHasTags">
                  <div class="vm-tags">
                    <TagBadge v-for="tag in parseTags(vm.tags)" :key="tag" :tag="tag" small />
                    <span v-if="!parseTags(vm.tags).length" class="text-muted text-sm">—</span>
                  </div>
                </td>
                <td @click.stop>
                  <div class="flex gap-1 vm-actions" style="align-items: center;">
                    <button v-if="vm.status === 'running'" @click="allShutdownVM(vm)" class="btn btn-warning btn-sm" :disabled="vm._busy">Shutdown</button>
                    <button v-if="vm.status === 'running'" @click="allStopVM(vm)" class="btn btn-danger btn-sm" :disabled="vm._busy">Stop</button>
                    <button v-if="vm.status !== 'running' && vm.status !== 'suspended'" @click="allStartVM(vm)" class="btn btn-primary btn-sm" :disabled="vm._busy">Start</button>
                    <button v-if="vm.status === 'suspended'" @click="resumeVm(vm)" class="btn btn-primary btn-sm" :disabled="vm._busy">Resume</button>
                    <button class="btn btn-outline btn-sm btn-console" @click="openConsole(vm)">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:2px;"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                      Console
                    </button>
                    <div class="more-menu-wrap">
                      <button class="btn btn-outline btn-sm" @click.stop="toggleMoreMenu(vmKey(vm))" title="More actions">⋮</button>
                      <div v-if="openMoreMenuKey === vmKey(vm)" class="more-menu">
                        <button @click="openTagEditor(vm); openMoreMenuKey = null">🏷 Tags</button>
                        <button @click="openSnapshotModal(vm); openMoreMenuKey = null">📷 Snapshot</button>
                        <button @click="openCloneModal(vm); openMoreMenuKey = null">📋 Clone</button>
                        <button @click="openMigrateModal(vm); openMoreMenuKey = null">🚀 Migrate</button>
                        <button v-if="vm.status === 'running'" @click="suspendVm(vm); openMoreMenuKey = null">⏸ Suspend</button>
                        <button @click="openVmDeleteModal(vm); openMoreMenuKey = null" class="more-menu-danger">🗑 Delete</button>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Bulk Action Bar (grouped view) -->
        <div v-if="selectedVmKeys.size > 0" class="bulk-action-bar">
          <span class="bulk-count">{{ selectedVmKeys.size }} VM{{ selectedVmKeys.size !== 1 ? 's' : '' }} selected</span>
          <button class="btn btn-primary btn-sm" @click="bulkAction('start')" :disabled="bulkRunning">Start Selected</button>
          <button class="btn btn-warning btn-sm" @click="bulkAction('shutdown')" :disabled="bulkRunning">Shutdown Selected</button>
          <button class="btn btn-danger btn-sm" @click="bulkAction('stop')" :disabled="bulkRunning">Stop Selected</button>
          <button class="btn btn-outline btn-sm" @click="openBulkSnapshotModal" :disabled="bulkRunning">Snapshot All</button>
          <button class="btn btn-outline btn-sm" @click="openBulkTagModal" :disabled="bulkRunning">Tag All</button>
          <button class="btn btn-danger btn-sm" @click="openBulkDeleteModal" :disabled="bulkRunning">Delete All</button>
          <a href="#" class="bulk-clear-link" @click.prevent="clearSelection">Clear Selection</a>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="showDeleteConfirmModal" class="modal-overlay" @click="closeDeleteModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Confirm VM Deletion</h3>
          <button @click="closeDeleteModal" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p class="text-danger mb-1">
            <strong>Warning:</strong> This will permanently delete VM {{ vmToDelete?.vmid }} ({{ vmToDelete?.name }}) from Proxmox.
          </p>
          <p class="text-muted mb-2">This action cannot be undone.</p>
          <div class="form-group">
            <label>Type the VM ID <strong>{{ vmToDelete?.vmid }}</strong> to confirm:</label>
            <input
              v-model="deleteConfirmInput"
              type="text"
              class="form-control"
              :placeholder="`Type ${vmToDelete?.vmid} to confirm`"
              @keyup.enter="deleteVM"
            />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeDeleteModal" class="btn btn-secondary">Cancel</button>
          <button
            @click="deleteVM"
            class="btn btn-danger"
            :disabled="deleteConfirmInput !== String(vmToDelete?.vmid)"
          >
            Delete VM
          </button>
        </div>
      </div>
    </div>

    <!-- Bulk Snapshot Modal -->
    <div v-if="showBulkSnapshotModal" class="modal-overlay" @click.self="showBulkSnapshotModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Snapshot All Selected VMs ({{ selectedVmKeys.size }})</h3>
          <button @click="showBulkSnapshotModal = false" class="btn-close" :disabled="bulkRunning">×</button>
        </div>
        <div class="modal-body">
          <div v-if="!bulkOpDone">
            <p class="text-muted mb-2">
              A snapshot will be created on each of the {{ selectedVmKeys.size }} selected VMs using the same snapshot name.
            </p>
            <div class="form-group">
              <label>Snapshot Name <span class="text-danger">*</span></label>
              <input v-model="bulkSnapName" type="text" class="form-control"
                placeholder="e.g. pre-update-20260405" :disabled="bulkRunning" />
            </div>
            <div class="form-group">
              <label>Description (optional)</label>
              <input v-model="bulkSnapDescription" type="text" class="form-control"
                placeholder="Optional description" :disabled="bulkRunning" />
            </div>
          </div>
          <div v-if="bulkOpResults.length > 0" class="bulk-results-table">
            <div class="bulk-results-header"><span>VMID</span><span>Name</span><span>Node</span><span>Result</span></div>
            <div v-for="r in bulkOpResults" :key="r.key" class="bulk-results-row">
              <span><strong>{{ r.vmid }}</strong></span>
              <span>{{ r.name || '—' }}</span>
              <span class="text-muted text-sm">{{ r.node }}</span>
              <span>
                <span v-if="r.status === 'pending'" class="text-muted text-sm">Waiting…</span>
                <span v-else-if="r.status === 'running'" class="text-sm" style="color:#3b82f6;">Running…</span>
                <span v-else-if="r.status === 'success'" class="badge badge-success">OK</span>
                <span v-else-if="r.status === 'error'" class="badge badge-danger" :title="r.error">Failed</span>
              </span>
            </div>
          </div>
          <div v-if="bulkOpDone" class="bulk-done-summary">
            {{ bulkOpResults.filter(r => r.status === 'success').length }} succeeded,
            {{ bulkOpResults.filter(r => r.status === 'error').length }} failed.
          </div>
        </div>
        <div class="modal-footer">
          <button v-if="!bulkOpDone" @click="showBulkSnapshotModal = false" class="btn btn-secondary" :disabled="bulkRunning">Cancel</button>
          <button v-if="!bulkOpDone" @click="runBulkSnapshot" class="btn btn-primary" :disabled="bulkRunning || !bulkSnapName.trim()">
            {{ bulkRunning ? 'Running…' : 'Create Snapshots' }}
          </button>
          <button v-if="bulkOpDone" @click="closeBulkModal" class="btn btn-secondary">Close</button>
        </div>
      </div>
    </div>

    <!-- Bulk Tag Modal -->
    <div v-if="showBulkTagModal" class="modal-overlay" @click.self="showBulkTagModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Tag All Selected VMs ({{ selectedVmKeys.size }})</h3>
          <button @click="showBulkTagModal = false" class="btn-close" :disabled="bulkRunning">×</button>
        </div>
        <div class="modal-body">
          <div v-if="!bulkOpDone">
            <p class="text-muted mb-2">
              The following tag will be added to all {{ selectedVmKeys.size }} selected VMs (appended to existing tags).
            </p>
            <div class="form-group">
              <label>Tag <span class="text-danger">*</span></label>
              <input v-model="bulkTagValue" type="text" class="form-control"
                placeholder="e.g. production" :disabled="bulkRunning"
                @input="bulkTagValue = bulkTagValue.toLowerCase().replace(/[^a-z0-9\-_]/g, '')" />
              <small class="text-muted">Lowercase letters, numbers, hyphens, and underscores only.</small>
            </div>
          </div>
          <div v-if="bulkOpResults.length > 0" class="bulk-results-table">
            <div class="bulk-results-header"><span>VMID</span><span>Name</span><span>Node</span><span>Result</span></div>
            <div v-for="r in bulkOpResults" :key="r.key" class="bulk-results-row">
              <span><strong>{{ r.vmid }}</strong></span>
              <span>{{ r.name || '—' }}</span>
              <span class="text-muted text-sm">{{ r.node }}</span>
              <span>
                <span v-if="r.status === 'pending'" class="text-muted text-sm">Waiting…</span>
                <span v-else-if="r.status === 'running'" class="text-sm" style="color:#3b82f6;">Running…</span>
                <span v-else-if="r.status === 'success'" class="badge badge-success">OK</span>
                <span v-else-if="r.status === 'error'" class="badge badge-danger" :title="r.error">Failed</span>
              </span>
            </div>
          </div>
          <div v-if="bulkOpDone" class="bulk-done-summary">
            {{ bulkOpResults.filter(r => r.status === 'success').length }} succeeded,
            {{ bulkOpResults.filter(r => r.status === 'error').length }} failed.
          </div>
        </div>
        <div class="modal-footer">
          <button v-if="!bulkOpDone" @click="showBulkTagModal = false" class="btn btn-secondary" :disabled="bulkRunning">Cancel</button>
          <button v-if="!bulkOpDone" @click="runBulkTag" class="btn btn-primary" :disabled="bulkRunning || !bulkTagValue.trim()">
            {{ bulkRunning ? 'Running…' : 'Apply Tag' }}
          </button>
          <button v-if="bulkOpDone" @click="closeBulkModal" class="btn btn-secondary">Close</button>
        </div>
      </div>
    </div>

    <!-- Tag Editor Modal -->
    <div v-if="showTagEditorModal" class="modal-overlay" @click.self="closeTagEditor">
      <div class="modal-content" @click.stop style="max-width: 420px;">
        <div class="modal-header">
          <h3>Edit Tags — VM {{ tagEditorVm?.vmid }} ({{ tagEditorVm?.name || '' }})</h3>
          <button @click="closeTagEditor" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="vm-tags" style="margin-bottom: 0.75rem; min-height: 2rem;">
            <TagBadge
              v-for="tag in tagEditorTags"
              :key="tag"
              :tag="tag"
              :removable="true"
              @remove="removeTagFromEditor"
            />
            <span v-if="tagEditorTags.length === 0" class="text-muted text-sm">No tags yet</span>
          </div>
          <div style="display: flex; gap: 0.5rem;">
            <input
              v-model="tagEditorInput"
              type="text"
              class="form-control"
              placeholder="Add tag (letters, numbers, -_)"
              @keyup.enter="addTagFromEditor"
              @input="tagEditorInput = tagEditorInput.toLowerCase().replace(/[^a-z0-9\-_]/g, '')"
              style="flex: 1;"
            />
            <button class="btn btn-primary btn-sm" @click="addTagFromEditor" :disabled="!tagEditorInput.trim()">Add</button>
          </div>
          <p class="text-muted text-sm" style="margin-top: 0.5rem;">Click a tag to remove it. Press Enter or "Add" to add a new tag.</p>
        </div>
        <div class="modal-footer">
          <button @click="closeTagEditor" class="btn btn-secondary" :disabled="tagEditorSaving">Cancel</button>
          <button @click="saveTagEditor" class="btn btn-primary" :disabled="tagEditorSaving">
            {{ tagEditorSaving ? 'Saving…' : 'Save Tags' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Snapshot Modal (single VM) -->
    <div v-if="showSnapshotModal" class="modal-overlay" @click.self="showSnapshotModal = false">
      <div class="modal-content" @click.stop style="max-width:460px;">
        <div class="modal-header">
          <h3>Create Snapshot — VM {{ snapshotVm?.vmid }} ({{ snapshotVm?.name }})</h3>
          <button @click="showSnapshotModal = false" class="btn-close" :disabled="snapshotRunning">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Snapshot Name <span class="text-danger">*</span></label>
            <input v-model="snapshotName" type="text" class="form-control" placeholder="e.g. pre-update-20260417" :disabled="snapshotRunning" />
          </div>
          <div class="form-group">
            <label>Description (optional)</label>
            <input v-model="snapshotDesc" type="text" class="form-control" placeholder="Optional description" :disabled="snapshotRunning" />
          </div>
          <div class="form-group" style="display:flex;align-items:center;gap:0.5rem;">
            <input id="snap-vmstate" type="checkbox" v-model="snapshotVmState" :disabled="snapshotRunning || snapshotVm?.status !== 'running'" />
            <label for="snap-vmstate" style="margin:0;">Include VM RAM state (only for running VMs)</label>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showSnapshotModal = false" class="btn btn-secondary" :disabled="snapshotRunning">Cancel</button>
          <button @click="runSnapshot" class="btn btn-primary" :disabled="snapshotRunning || !snapshotName.trim()">
            {{ snapshotRunning ? 'Creating…' : 'Create Snapshot' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Migrate Modal -->
    <div v-if="showMigrateModal" class="modal-overlay" @click.self="!migrateRunning && (showMigrateModal = false)">
      <div class="modal-content" @click.stop style="max-width:520px;">
        <div class="modal-header">
          <h3>Migrate VM {{ migrateVm?.vmid }} ({{ migrateVm?.name }})</h3>
          <button @click="showMigrateModal = false" class="btn-close" :disabled="migrateRunning">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Target Node <span class="text-danger">*</span></label>
            <select v-model="migrateTarget" class="form-control" :disabled="migrateRunning || migrateNodes.length === 0">
              <option value="">{{ migrateNodes.length === 0 ? 'Loading nodes…' : 'Select target node' }}</option>
              <option v-for="n in migrateNodes" :key="n.node" :value="n.node">{{ n.node }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Target Storage</label>
            <select v-model="migrateTargetStorage" class="form-control" :disabled="migrateRunning || !migrateTarget">
              <option value="">{{ migrateStorageLoading ? 'Loading…' : migrateTarget ? 'Auto / shared storage only' : 'Select target node first' }}</option>
              <option v-for="s in migrateTargetStorages" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
            </select>
            <small v-if="migrateVmDiskStorages.length" class="text-muted">
              VM disks on: <strong>{{ migrateVmDiskStorages.join(', ') }}</strong> — select a target storage to move them
            </small>
            <small v-else class="text-muted">Required if VM has disks on local (non-shared) storage</small>
          </div>
          <div class="form-group">
            <label>Migration Type</label>
            <select v-model="migrateMigrationType" class="form-control" :disabled="migrateRunning">
              <option value="secure">Secure (SSH tunnel, default)</option>
              <option value="insecure">Insecure (plain TCP, faster on trusted networks)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Bandwidth Limit (KiB/s)</label>
            <input v-model="migrateBwlimit" type="number" min="0" class="form-control" placeholder="0 = unlimited" :disabled="migrateRunning" />
          </div>
          <div class="form-group">
            <label>Migration Network (CIDR, optional)</label>
            <input v-model="migrateMigrationNetwork" type="text" class="form-control" placeholder="e.g. 10.0.1.0/24" :disabled="migrateRunning" />
            <small class="text-muted">Use a dedicated network interface for migration traffic</small>
          </div>
          <div class="form-group" style="display:flex;align-items:center;gap:0.5rem;">
            <input id="migrate-online" type="checkbox" v-model="migrateOnline" :disabled="migrateRunning || migrateVm?.status !== 'running'" />
            <label for="migrate-online" style="margin:0;">Live migration (online, VM stays running)</label>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showMigrateModal = false" class="btn btn-secondary" :disabled="migrateRunning">Cancel</button>
          <button @click="runMigrate" class="btn btn-primary" :disabled="migrateRunning || !migrateTarget">
            {{ migrateRunning ? 'Migrating…' : 'Migrate' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Clone Modal -->
    <div v-if="showCloneModal" class="modal-overlay" @click.self="!cloneRunning && (showCloneModal = false)">
      <div class="modal-content" @click.stop style="max-width:480px;">
        <div class="modal-header">
          <h3>Clone VM {{ cloneVm?.vmid }} ({{ cloneVm?.name }})</h3>
          <button @click="showCloneModal = false" class="btn-close" :disabled="cloneRunning">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>New VM ID <span class="text-danger">*</span></label>
            <input v-model.number="cloneNewId" type="number" class="form-control" placeholder="e.g. 200" min="100" :disabled="cloneRunning" />
          </div>
          <div class="form-group">
            <label>New VM Name</label>
            <input v-model="cloneName" type="text" class="form-control" :placeholder="`${cloneVm?.name || 'vm'}-clone`" :disabled="cloneRunning" />
          </div>
          <div class="form-group">
            <label>Target Node (optional)</label>
            <select v-model="cloneTarget" class="form-control" :disabled="cloneRunning">
              <option value="">Same node ({{ cloneVm?.node }})</option>
              <option v-for="n in cloneNodes" :key="n.node" :value="n.node">{{ n.node }}</option>
            </select>
          </div>
          <div class="form-group" style="display:flex;align-items:center;gap:0.5rem;">
            <input id="clone-full" type="checkbox" v-model="cloneFull" :disabled="cloneRunning" />
            <label for="clone-full" style="margin:0;">Full clone (independent copy, not linked clone)</label>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showCloneModal = false" class="btn btn-secondary" :disabled="cloneRunning">Cancel</button>
          <button @click="runClone" class="btn btn-primary" :disabled="cloneRunning || !cloneNewId">
            {{ cloneRunning ? 'Cloning…' : 'Clone VM' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Single VM Delete Modal (All Proxmox tab) -->
    <div v-if="showVmDeleteModal" class="modal-overlay" @click.self="showVmDeleteModal = false">
      <div class="modal-content" @click.stop style="max-width:420px;">
        <div class="modal-header">
          <h3>Delete VM</h3>
          <button @click="showVmDeleteModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p class="text-danger mb-1"><strong>Warning:</strong> This permanently deletes VM {{ vmDeleteTarget?.vmid }} ({{ vmDeleteTarget?.name }}) from Proxmox.</p>
          <p class="text-muted mb-2">This cannot be undone.</p>
          <div class="form-group">
            <label>Type <strong>{{ vmDeleteTarget?.vmid }}</strong> to confirm:</label>
            <input v-model="vmDeleteConfirm" type="text" class="form-control" :placeholder="`Type ${vmDeleteTarget?.vmid}`" @keyup.enter="confirmVmDelete" />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showVmDeleteModal = false" class="btn btn-secondary">Cancel</button>
          <button @click="confirmVmDelete" class="btn btn-danger" :disabled="vmDeleteConfirm !== String(vmDeleteTarget?.vmid)">Delete VM</button>
        </div>
      </div>
    </div>

    <!-- Bulk Delete Modal -->
    <div v-if="showBulkDeleteModal" class="modal-overlay" @click.self="!bulkRunning && (showBulkDeleteModal = false)">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Delete All Selected VMs ({{ selectedVmKeys.size }})</h3>
          <button @click="showBulkDeleteModal = false" class="btn-close" :disabled="bulkRunning">×</button>
        </div>
        <div class="modal-body">
          <div v-if="!bulkOpDone">
            <p class="text-danger mb-1">
              <strong>Warning:</strong> This will permanently delete {{ selectedVmKeys.size }} VMs from Proxmox.
              Running VMs will be stopped first. This action cannot be undone.
            </p>
            <ul class="bulk-delete-list">
              <li v-for="vm in selectedVmObjects" :key="vmKey(vm)">
                <strong>{{ vm.vmid }}</strong> — {{ vm.name || '(no name)' }}
                <span class="badge badge-info ml-1">{{ vm.node }}</span>
                <span :class="['badge', vm.status === 'running' ? 'badge-success' : 'badge-danger', 'ml-1']">{{ vm.status }}</span>
              </li>
            </ul>
            <div class="form-group mt-2">
              <label>Type <strong>DELETE</strong> to confirm:</label>
              <input v-model="bulkDeleteConfirm" type="text" class="form-control"
                placeholder="Type DELETE to confirm" :disabled="bulkRunning" />
            </div>
          </div>
          <div v-if="bulkOpResults.length > 0" class="bulk-results-table">
            <div class="bulk-results-header"><span>VMID</span><span>Name</span><span>Node</span><span>Result</span></div>
            <div v-for="r in bulkOpResults" :key="r.key" class="bulk-results-row">
              <span><strong>{{ r.vmid }}</strong></span>
              <span>{{ r.name || '—' }}</span>
              <span class="text-muted text-sm">{{ r.node }}</span>
              <span>
                <span v-if="r.status === 'pending'" class="text-muted text-sm">Waiting…</span>
                <span v-else-if="r.status === 'running'" class="text-sm" style="color:#3b82f6;">Running…</span>
                <span v-else-if="r.status === 'stopping'" class="text-sm" style="color:#f59e0b;">Stopping…</span>
                <span v-else-if="r.status === 'success'" class="badge badge-success">Deleted</span>
                <span v-else-if="r.status === 'error'" class="badge badge-danger" :title="r.error">Failed</span>
              </span>
            </div>
          </div>
          <div v-if="bulkOpDone" class="bulk-done-summary">
            {{ bulkOpResults.filter(r => r.status === 'success').length }} deleted,
            {{ bulkOpResults.filter(r => r.status === 'error').length }} failed.
          </div>
        </div>
        <div class="modal-footer">
          <button v-if="!bulkOpDone" @click="showBulkDeleteModal = false" class="btn btn-secondary" :disabled="bulkRunning">Cancel</button>
          <button v-if="!bulkOpDone" @click="runBulkDelete" class="btn btn-danger"
            :disabled="bulkRunning || bulkDeleteConfirm !== 'DELETE'">
            {{ bulkRunning ? 'Deleting…' : 'Delete All VMs' }}
          </button>
          <button v-if="bulkOpDone" @click="closeBulkModal" class="btn btn-secondary">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import TagBadge from '@/components/TagBadge.vue'
import { tagColor as _tagColor } from '@/utils/tagColors'

const COL_PREFS_KEY = 'depl0y_vm_col_prefs'
const DEFAULT_COLS = { host: true, resources: true, uptime: true, ip: true, tags: true }

export default {
  name: 'VirtualMachines',
  components: { SkeletonLoader, TagBadge },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const toast = useToast()

    // ── Tab state ──────────────────────────────────────────────────────────
    const activeTab = ref('managed')

    const switchTab = (tab) => {
      activeTab.value = tab
      if (tab === 'all' && allVMs.value.length === 0 && !allLoading.value) {
        fetchAllProxmoxVMs()
      }
    }

    // ── Depl0y Managed tab ─────────────────────────────────────────────────
    const vms = ref([])
    const loading = ref(false)
    const managedError = ref(null)
    const sortField = ref('vmid')
    const sortDirection = ref('asc')
    const statusFilter = ref(route.query.status || null)
    const managedSearch = ref('')
    const managedStatusFilter = ref('')
    const managedNodeFilter = ref('')
    const showDeleteConfirmModal = ref(false)
    const vmToDelete = ref(null)
    const deleteConfirmInput = ref('')

    const fetchVMs = async () => {
      loading.value = true
      managedError.value = null
      let lastErr = null
      for (let attempt = 1; attempt <= 2; attempt++) {
        try {
          const response = await api.vms.list()
          vms.value = response.data
          sortVMs()
          lastErr = null
          break
        } catch (error) {
          lastErr = error
          if (attempt < 2) await new Promise(r => setTimeout(r, 1000))
        }
      }
      if (lastErr) {
        console.error('Failed to fetch VMs:', lastErr)
        managedError.value = lastErr.response?.data?.detail || lastErr.message || 'Failed to load VMs'
        toast.error('Failed to load virtual machines')
      }
      loading.value = false
    }

    const sortBy = (field) => {
      if (sortField.value === field) {
        sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
      } else {
        sortField.value = field
        sortDirection.value = 'asc'
      }
      sortVMs()
    }

    const sortVMs = () => {
      vms.value.sort((a, b) => {
        let aVal = a[sortField.value]
        let bVal = b[sortField.value]
        if (typeof aVal === 'string') { aVal = aVal.toLowerCase(); bVal = bVal.toLowerCase() }
        if (sortDirection.value === 'asc') return aVal > bVal ? 1 : aVal < bVal ? -1 : 0
        else return aVal < bVal ? 1 : aVal > bVal ? -1 : 0
      })
    }

    const startVM = async (vmid, node) => {
      try {
        await api.vms.startByVmid(vmid, node)
        toast.success(`VM ${vmid} started successfully`)
        setTimeout(fetchVMs, 1000)
      } catch (error) {
        toast.error('Failed to start VM')
      }
    }

    const stopVM = async (vmid, node) => {
      try {
        await api.vms.stopByVmid(vmid, node)
        toast.success(`VM ${vmid} stopped successfully`)
        setTimeout(fetchVMs, 1000)
      } catch (error) {
        toast.error('Failed to stop VM')
      }
    }

    const powerOffVM = async (vmid, node) => {
      if (!confirm(`Are you sure you want to power off VM ${vmid}? This is equivalent to pulling the power plug.`)) return
      try {
        await api.vms.powerOffByVmid(vmid, node)
        toast.success(`VM ${vmid} powered off successfully`)
        setTimeout(fetchVMs, 1000)
      } catch (error) {
        toast.error('Failed to power off VM')
      }
    }

    const restartVM = async (vmid, node) => {
      try {
        await api.vms.restartByVmid(vmid, node)
        toast.success(`VM ${vmid} restarting...`)
        setTimeout(fetchVMs, 1000)
      } catch (error) {
        toast.error('Failed to restart VM')
      }
    }

    const showDeleteModal = (vm) => {
      vmToDelete.value = vm
      deleteConfirmInput.value = ''
      showDeleteConfirmModal.value = true
    }

    const closeDeleteModal = () => {
      showDeleteConfirmModal.value = false
      vmToDelete.value = null
      deleteConfirmInput.value = ''
    }

    const deleteVM = async () => {
      if (deleteConfirmInput.value !== String(vmToDelete.value.vmid)) {
        toast.error('VM ID confirmation does not match')
        return
      }
      try {
        await api.vms.deleteByVmid(vmToDelete.value.vmid, vmToDelete.value.node)
        toast.success(`VM ${vmToDelete.value.vmid} deleted successfully`)
        closeDeleteModal()
        fetchVMs()
      } catch (error) {
        toast.error(`Failed to delete VM: ${error.response?.data?.detail || error.message}`)
      }
    }

    const managedNodes = computed(() => [...new Set(vms.value.map(v => v.node).filter(Boolean))].sort())

    const filteredVMs = computed(() => {
      let list = vms.value
      if (statusFilter.value) {
        list = list.filter(vm => vm.status.toLowerCase() === statusFilter.value.toLowerCase())
      }
      if (managedStatusFilter.value) {
        list = list.filter(vm => vm.status.toLowerCase() === managedStatusFilter.value.toLowerCase())
      }
      if (managedNodeFilter.value) {
        list = list.filter(vm => vm.node === managedNodeFilter.value)
      }
      if (managedSearch.value.trim()) {
        const q = managedSearch.value.trim().toLowerCase()
        list = list.filter(vm =>
          (vm.name || '').toLowerCase().includes(q) ||
          String(vm.vmid).includes(q) ||
          (vm.node || '').toLowerCase().includes(q)
        )
      }
      return list
    })

    const clearFilter = () => {
      statusFilter.value = null
      managedSearch.value = ''
      managedStatusFilter.value = ''
      managedNodeFilter.value = ''
      router.push('/vms')
    }

    watch(() => route.query.status, (newStatus) => {
      statusFilter.value = newStatus || null
    })

    // ── All Proxmox VMs tab ────────────────────────────────────────────────
    const ALL_FILTER_KEY = 'depl0y_all_vms_filter'
    const PRESETS_KEY = 'depl0y_vm_filter_presets'
    const ALL_LOAD_TIMEOUT_MS = 10_000
    const allPartialFailedHosts = ref([])
    const allTimeoutWarning = ref(false)

    function loadSavedFilter() {
      try { return JSON.parse(sessionStorage.getItem(ALL_FILTER_KEY) || '{}') } catch { return {} }
    }

    const savedFilter = loadSavedFilter()

    const allVMs = ref([])
    const allLoading = ref(false)
    const allError = ref(null)
    const allSearch = ref(savedFilter.search || '')
    const allStatusFilter = ref(savedFilter.status || '')
    const showTemplates = ref(false)  // hide cloud-init templates by default
    const allSortField = ref('vmid')
    const allSortDirection = ref('asc')

    // Column visibility
    function loadColumnPrefs() {
      try { return { ...DEFAULT_COLS, ...JSON.parse(localStorage.getItem(COL_PREFS_KEY) || '{}') } } catch { return { ...DEFAULT_COLS } }
    }
    const visibleColumns = ref(loadColumnPrefs())
    const groupByNode = ref(false)
    const showColMenu = ref(false)
    const allColumns = [
      { key: 'host', label: 'Host' },
      { key: 'resources', label: 'CPU / Memory' },
      { key: 'uptime', label: 'Uptime' },
      { key: 'ip', label: 'IP Address' },
      { key: 'tags', label: 'Tags' },
    ]
    function saveColumnPrefs() {
      localStorage.setItem(COL_PREFS_KEY, JSON.stringify({ ...visibleColumns.value, groupByNode: groupByNode.value }))
    }
    // Restore groupByNode from prefs
    try {
      const saved = JSON.parse(localStorage.getItem(COL_PREFS_KEY) || '{}')
      if (saved.groupByNode !== undefined) groupByNode.value = saved.groupByNode
    } catch {}

    // Advanced filter
    const showAdvFilter = ref(false)
    const advFilter = ref({ hostId: '', node: '', osType: '', minCpus: null, minRamGb: null, maxRamGb: null })
    const advFilterCount = computed(() => {
      let c = 0
      if (advFilter.value.hostId) c++
      if (advFilter.value.node) c++
      if (advFilter.value.osType) c++
      if (advFilter.value.minCpus) c++
      if (advFilter.value.minRamGb) c++
      if (advFilter.value.maxRamGb) c++
      if (activeTagFilters.value.size > 0) c += activeTagFilters.value.size
      return c
    })
    const clearAdvFilter = () => {
      advFilter.value = { hostId: '', node: '', osType: '', minCpus: null, minRamGb: null, maxRamGb: null }
      activeTagFilters.value = new Set()
    }

    const uniqueHosts = computed(() => {
      const map = new Map()
      allVMs.value.forEach(vm => { if (!map.has(vm.hostId)) map.set(vm.hostId, { id: vm.hostId, name: vm.hostName }) })
      return [...map.values()]
    })
    const uniqueNodes = computed(() => [...new Set(allVMs.value.map(v => v.node))].sort())

    // OS type detection from VM name
    const detectOsType = (name) => {
      if (!name) return 'other'
      const n = name.toLowerCase()
      if (n.includes('win') || n.includes('server')) return 'windows'
      if (n.includes('bsd') || n.includes('freebsd') || n.includes('openbsd')) return 'bsd'
      if (n.includes('ubuntu') || n.includes('debian') || n.includes('centos') || n.includes('fedora') ||
          n.includes('rhel') || n.includes('alma') || n.includes('rocky') || n.includes('linux') ||
          n.includes('arch') || n.includes('suse') || n.includes('oracle')) return 'linux'
      return 'other'
    }

    // Persist filter changes to sessionStorage
    watch([allSearch, allStatusFilter], () => {
      sessionStorage.setItem(ALL_FILTER_KEY, JSON.stringify({ search: allSearch.value, status: allStatusFilter.value }))
    })

    // ── Filter Presets ──────────────────────────────────────────────────────
    const savedFilterPresets = ref([])
    const showSavePresetModal = ref(false)
    const newPresetName = ref('')

    function loadPresets() {
      try { savedFilterPresets.value = JSON.parse(localStorage.getItem(PRESETS_KEY) || '[]') } catch { savedFilterPresets.value = [] }
    }

    function savePreset() {
      const name = newPresetName.value.trim()
      if (!name) return
      const preset = { name, search: allSearch.value, status: allStatusFilter.value }
      const list = savedFilterPresets.value.filter(p => p.name !== name)
      list.push(preset)
      localStorage.setItem(PRESETS_KEY, JSON.stringify(list))
      savedFilterPresets.value = list
      showSavePresetModal.value = false
      newPresetName.value = ''
    }

    function applyPreset(value) {
      if (!value) return
      if (value === '__running__') { allStatusFilter.value = 'running'; allSearch.value = ''; activeTagFilters.value = new Set() }
      else if (value === '__stopped__') { allStatusFilter.value = 'stopped'; allSearch.value = ''; activeTagFilters.value = new Set() }
      else if (value === '__all__') { allStatusFilter.value = ''; allSearch.value = ''; activeTagFilters.value = new Set() }
      else if (value.startsWith('__saved__')) {
        const name = value.slice(9)
        const preset = savedFilterPresets.value.find(p => p.name === name)
        if (preset) { allSearch.value = preset.search || ''; allStatusFilter.value = preset.status || '' }
      }
    }

    function openSavePresetModal() {
      newPresetName.value = ''
      showSavePresetModal.value = true
    }

    loadPresets()

    function withAllTimeout(promise, ms) {
      let timer
      const timeout = new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('timeout')), ms)
      })
      return Promise.race([promise, timeout]).finally(() => clearTimeout(timer))
    }

    async function doFetchAllProxmoxVMs() {
      const hostsResp = await api.proxmox.listHosts()
      const hosts = hostsResp.data
      if (!hosts || hosts.length === 0) { allVMs.value = []; return }

      const results = []
      const localFailedHosts = []
      let timedOut = false

      await Promise.allSettled(
        hosts.map(async (host) => {
          try {
            const resResp = await withAllTimeout(
              api.pveNode.clusterResources(host.id, 'vm'),
              ALL_LOAD_TIMEOUT_MS
            )
            const resources = resResp.data
            const items = Array.isArray(resources) ? resources : (resources.data || [])
            items.forEach((item) => {
              if (item.type && item.type !== 'qemu') return
              results.push({
                hostId: host.id,
                hostName: host.name || host.host || String(host.id),
                node: item.node,
                vmid: item.vmid,
                name: item.name,
                status: item.status || 'unknown',
                cpus: item.cpus,
                maxmem: item.maxmem,
                mem: item.mem,
                maxdisk: item.maxdisk,
                uptime: item.uptime || 0,
                tags: item.tags || '',
                description: item.description || '',
                netin: item.netin,
                netout: item.netout,
                template: item.template || 0,
                _busy: false,
              })
            })
          } catch (err) {
            if (err.message === 'timeout') timedOut = true
            localFailedHosts.push(host.name || String(host.id))
            console.warn(`Failed to fetch cluster resources for host ${host.id}:`, err)
          }
        })
      )

      allPartialFailedHosts.value = localFailedHosts
      allTimeoutWarning.value = timedOut
      allVMs.value = results
    }

    const fetchAllProxmoxVMs = async (resetCountdown = false) => {
      if (resetCountdown) {
        const intervalSecs = parseInt(localStorage.getItem('depl0y_refresh_interval') || '30', 10)
        resetAllCountdown(intervalSecs)
      }
      allLoading.value = true
      allError.value = null

      let lastErr = null
      for (let attempt = 1; attempt <= 2; attempt++) {
        try {
          await doFetchAllProxmoxVMs()
          lastErr = null
          break
        } catch (err) {
          lastErr = err
          if (attempt < 2) await new Promise(r => setTimeout(r, 1000 * attempt))
        }
      }

      if (lastErr) {
        console.error('Failed to fetch Proxmox hosts:', lastErr)
        allError.value = lastErr.response?.data?.detail || lastErr.message || 'Failed to load Proxmox hosts. Check that at least one host is configured.'
      }

      allLoading.value = false
    }

    const allSortBy = (field) => {
      if (allSortField.value === field) {
        allSortDirection.value = allSortDirection.value === 'asc' ? 'desc' : 'asc'
      } else {
        allSortField.value = field
        allSortDirection.value = 'asc'
      }
    }

    const templateCount = computed(() => allVMs.value.filter(vm => vm.template).length)

    const filteredAllVMs = computed(() => {
      let list = allVMs.value

      // Hide templates (cloud-init base images) unless explicitly shown
      if (!showTemplates.value) {
        list = list.filter(vm => !vm.template)
      }

      if (allStatusFilter.value) {
        list = list.filter(vm => vm.status.toLowerCase() === allStatusFilter.value.toLowerCase())
      }

      if (allSearch.value.trim()) {
        const q = allSearch.value.trim().toLowerCase()
        list = list.filter(vm =>
          (vm.name || '').toLowerCase().includes(q) ||
          (vm.node || '').toLowerCase().includes(q) ||
          (vm.hostName || '').toLowerCase().includes(q) ||
          String(vm.vmid).includes(q)
        )
      }

      // Tag filter
      if (activeTagFilters.value.size > 0) {
        const required = [...activeTagFilters.value]
        list = list.filter(vm => {
          const vmTags = parseTags(vm.tags)
          return required.every(t => vmTags.includes(t))
        })
      }

      // Advanced filters
      const af = advFilter.value
      if (af.hostId) list = list.filter(vm => vm.hostId === af.hostId)
      if (af.node) list = list.filter(vm => vm.node === af.node)
      if (af.osType) list = list.filter(vm => detectOsType(vm.name) === af.osType)
      if (af.minCpus) list = list.filter(vm => (vm.cpus || 0) >= af.minCpus)
      if (af.minRamGb) list = list.filter(vm => (vm.maxmem || 0) >= af.minRamGb * 1024 * 1024 * 1024)
      if (af.maxRamGb) list = list.filter(vm => (vm.maxmem || 0) <= af.maxRamGb * 1024 * 1024 * 1024)

      // Sort
      const field = allSortField.value
      const dir = allSortDirection.value
      return [...list].sort((a, b) => {
        let aVal = a[field] ?? ''
        let bVal = b[field] ?? ''
        if (typeof aVal === 'string') { aVal = aVal.toLowerCase(); bVal = bVal.toLowerCase() }
        if (dir === 'asc') return aVal > bVal ? 1 : aVal < bVal ? -1 : 0
        return aVal < bVal ? 1 : aVal > bVal ? -1 : 0
      })
    })

    // Grouped by node
    const groupedVMs = computed(() => {
      const groups = {}
      filteredAllVMs.value.forEach(vm => {
        const key = vm.node || 'unknown'
        if (!groups[key]) groups[key] = []
        groups[key].push(vm)
      })
      return groups
    })

    const toggleGroupSelect = (group, event) => {
      const allSelected = group.every(vm => selectedVmKeys.value.has(vmKey(vm)))
      const newSet = new Set(selectedVmKeys.value)
      if (allSelected) {
        group.forEach(vm => newSet.delete(vmKey(vm)))
      } else {
        group.forEach(vm => newSet.add(vmKey(vm)))
      }
      selectedVmKeys.value = newSet
    }

    // Export CSV
    const exportCSV = () => {
      const cols = ['vmid', 'name', 'status', 'node', 'hostName', 'cpus', 'maxmem', 'uptime', 'tags']
      const header = cols.join(',')
      const rows = filteredAllVMs.value.map(vm =>
        cols.map(c => {
          const v = vm[c] ?? ''
          const s = String(v).replace(/"/g, '""')
          return `"${s}"`
        }).join(',')
      )
      const csv = [header, ...rows].join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `vms-export-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    }

    const navigateToVM = (vm) => {
      router.push(`/proxmox/${vm.hostId}/nodes/${vm.node}/vms/${vm.vmid}`)
    }

    const openConsole = (vm) => {
      router.push(`/proxmox/${vm.hostId}/nodes/${vm.node}/console/${vm.vmid}`)
    }

    const allStartVM = async (vm) => {
      vm._busy = true
      try {
        await api.pveVm.start(vm.hostId, vm.node, vm.vmid)
        toast.success(`VM ${vm.vmid} started`)
        setTimeout(fetchAllProxmoxVMs, 2000)
      } catch (err) {
        toast.error(`Failed to start VM ${vm.vmid}`)
      } finally {
        vm._busy = false
      }
    }

    const allStopVM = async (vm) => {
      if (!confirm(`Force-stop VM ${vm.vmid} (${vm.name || ''})? This is equivalent to pulling the power plug.`)) return
      vm._busy = true
      try {
        await api.pveVm.stop(vm.hostId, vm.node, vm.vmid)
        toast.success(`VM ${vm.vmid} stopped`)
        setTimeout(fetchAllProxmoxVMs, 2000)
      } catch (err) {
        toast.error(`Failed to stop VM ${vm.vmid}`)
      } finally {
        vm._busy = false
      }
    }

    const allShutdownVM = async (vm) => {
      vm._busy = true
      try {
        await api.pveVm.shutdown(vm.hostId, vm.node, vm.vmid)
        toast.success(`VM ${vm.vmid} shutdown initiated`)
        setTimeout(fetchAllProxmoxVMs, 2000)
      } catch (err) {
        toast.error(`Failed to shutdown VM ${vm.vmid}`)
      } finally {
        vm._busy = false
      }
    }

    // ── Bulk selection ──────────────────────────────────────────────────────
    const selectedVmKeys = ref(new Set())
    const bulkRunning = ref(false)

    const vmKey = (vm) => `${vm.hostId}:${vm.node}:${vm.vmid}`

    const toggleSelectVm = (vm) => {
      const key = vmKey(vm)
      const newSet = new Set(selectedVmKeys.value)
      if (newSet.has(key)) newSet.delete(key)
      else newSet.add(key)
      selectedVmKeys.value = newSet
    }

    const allPageSelected = computed(() =>
      filteredAllVMs.value.length > 0 &&
      filteredAllVMs.value.every(vm => selectedVmKeys.value.has(vmKey(vm)))
    )

    const somePageSelected = computed(() =>
      filteredAllVMs.value.some(vm => selectedVmKeys.value.has(vmKey(vm)))
    )

    const toggleSelectAll = () => {
      if (allPageSelected.value) {
        const newSet = new Set(selectedVmKeys.value)
        filteredAllVMs.value.forEach(vm => newSet.delete(vmKey(vm)))
        selectedVmKeys.value = newSet
      } else {
        const newSet = new Set(selectedVmKeys.value)
        filteredAllVMs.value.forEach(vm => newSet.add(vmKey(vm)))
        selectedVmKeys.value = newSet
      }
    }

    const clearSelection = () => { selectedVmKeys.value = new Set() }

    const bulkAction = async (action) => {
      const vmsToAct = allVMs.value.filter(vm => selectedVmKeys.value.has(vmKey(vm)))
      if (vmsToAct.length === 0) return
      const actionFn = {
        start: (vm) => api.pveVm.start(vm.hostId, vm.node, vm.vmid),
        shutdown: (vm) => api.pveVm.shutdown(vm.hostId, vm.node, vm.vmid),
        stop: (vm) => api.pveVm.stop(vm.hostId, vm.node, vm.vmid),
      }[action]
      bulkRunning.value = true
      for (let i = 0; i < vmsToAct.length; i++) {
        const vm = vmsToAct[i]
        toast.info(`${action.charAt(0).toUpperCase() + action.slice(1)}ing VM ${vm.vmid}... (${i + 1}/${vmsToAct.length})`)
        try { await actionFn(vm) } catch (err) { toast.error(`Failed to ${action} VM ${vm.vmid}`) }
        if (i < vmsToAct.length - 1) await new Promise(r => setTimeout(r, 300))
      }
      bulkRunning.value = false
      clearSelection()
      setTimeout(() => fetchAllProxmoxVMs(), 2000)
    }

    // ── Bulk Snapshot / Tag / Delete ────────────────────────────────────────
    const showBulkSnapshotModal = ref(false)
    const showBulkTagModal = ref(false)
    const showBulkDeleteModal = ref(false)
    const bulkSnapName = ref('')
    const bulkSnapDescription = ref('')
    const bulkTagValue = ref('')
    const bulkDeleteConfirm = ref('')
    const bulkOpResults = ref([])
    const bulkOpDone = ref(false)

    const selectedVmObjects = computed(() => allVMs.value.filter(vm => selectedVmKeys.value.has(vmKey(vm))))

    const openBulkSnapshotModal = () => {
      const now = new Date()
      const pad = (n) => String(n).padStart(2, '0')
      bulkSnapName.value = `bulk-snap-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`
      bulkSnapDescription.value = ''
      bulkOpResults.value = []
      bulkOpDone.value = false
      showBulkSnapshotModal.value = true
    }

    const openBulkTagModal = () => { bulkTagValue.value = ''; bulkOpResults.value = []; bulkOpDone.value = false; showBulkTagModal.value = true }
    const openBulkDeleteModal = () => { bulkDeleteConfirm.value = ''; bulkOpResults.value = []; bulkOpDone.value = false; showBulkDeleteModal.value = true }

    const closeBulkModal = () => {
      showBulkSnapshotModal.value = false
      showBulkTagModal.value = false
      showBulkDeleteModal.value = false
      bulkOpResults.value = []
      bulkOpDone.value = false
    }

    const initBulkResults = () => {
      const vmsToAct = allVMs.value.filter(vm => selectedVmKeys.value.has(vmKey(vm)))
      bulkOpResults.value = vmsToAct.map(vm => ({
        key: vmKey(vm), vmid: vm.vmid, name: vm.name, node: vm.node, hostId: vm.hostId, status: 'pending', error: null,
      }))
      return vmsToAct
    }

    const runBulkSnapshot = async () => {
      if (!bulkSnapName.value.trim()) return
      bulkRunning.value = true
      initBulkResults()
      for (let i = 0; i < bulkOpResults.value.length; i++) {
        const r = bulkOpResults.value[i]
        bulkOpResults.value[i] = { ...r, status: 'running' }
        try {
          await api.pveVm.createSnapshot(r.hostId, r.node, r.vmid, { snapname: bulkSnapName.value.trim(), description: bulkSnapDescription.value.trim() })
          bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'success' }
          toast.success(`Snapshot created on VM ${r.vmid}`)
        } catch (err) {
          const msg = err.response?.data?.detail || err.message || 'Unknown error'
          bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'error', error: msg }
          toast.error(`Failed to snapshot VM ${r.vmid}: ${msg}`)
        }
        if (i < bulkOpResults.value.length - 1) await new Promise(r => setTimeout(r, 300))
      }
      bulkRunning.value = false
      bulkOpDone.value = true
    }

    const runBulkTag = async () => {
      const tag = bulkTagValue.value.trim()
      if (!tag) return
      bulkRunning.value = true
      initBulkResults()
      for (let i = 0; i < bulkOpResults.value.length; i++) {
        const r = bulkOpResults.value[i]
        bulkOpResults.value[i] = { ...r, status: 'running' }
        try {
          const configRes = await api.pveVm.getConfig(r.hostId, r.node, r.vmid)
          const currentTags = configRes.data?.tags || ''
          const tagsArr = currentTags ? currentTags.split(';').map(t => t.trim()).filter(Boolean) : []
          if (!tagsArr.includes(tag)) tagsArr.push(tag)
          await api.pveVm.updateConfig(r.hostId, r.node, r.vmid, { tags: tagsArr.join(';') })
          bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'success' }
        } catch (err) {
          const msg = err.response?.data?.detail || err.message || 'Unknown error'
          bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'error', error: msg }
          toast.error(`Failed to tag VM ${r.vmid}: ${msg}`)
        }
        if (i < bulkOpResults.value.length - 1) await new Promise(r => setTimeout(r, 200))
      }
      bulkRunning.value = false
      bulkOpDone.value = true
      setTimeout(() => fetchAllProxmoxVMs(), 1500)
    }

    const runBulkDelete = async () => {
      if (bulkDeleteConfirm.value !== 'DELETE') return
      bulkRunning.value = true
      initBulkResults()
      for (let i = 0; i < bulkOpResults.value.length; i++) {
        const r = bulkOpResults.value[i]
        const vm = allVMs.value.find(v => vmKey(v) === r.key)
        if (vm?.status === 'running') {
          bulkOpResults.value[i] = { ...r, status: 'stopping' }
          try { await api.pveVm.stop(r.hostId, r.node, r.vmid); await new Promise(r => setTimeout(r, 3000)) } catch {}
        }
        bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'running' }
        try {
          await api.pveVm.deleteVm(r.hostId, r.node, r.vmid)
          bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'success' }
          toast.success(`VM ${r.vmid} deleted`)
        } catch (err) {
          const msg = err.response?.data?.detail || err.message || 'Unknown error'
          bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'error', error: msg }
          toast.error(`Failed to delete VM ${r.vmid}: ${msg}`)
        }
        if (i < bulkOpResults.value.length - 1) await new Promise(r => setTimeout(r, 500))
      }
      bulkRunning.value = false
      bulkOpDone.value = true
      clearSelection()
      setTimeout(() => fetchAllProxmoxVMs(), 2000)
    }

    // ── Adapt managed-tab VM to modal format (uses host_id, not hostId) ──────
    const adaptManagedVm = (vm) => ({
      ...vm,
      hostId: vm.host_id || vm.hostId || 1,
    })

    // ── More-actions dropdown ────────────────────────────────────────────────
    const openMoreMenuKey = ref(null)
    const toggleMoreMenu = (key) => { openMoreMenuKey.value = openMoreMenuKey.value === key ? null : key }

    const handleMenuOutsideClick = (e) => {
      if (!e.target.closest('.more-menu-wrap')) openMoreMenuKey.value = null
      if (!e.target.closest('.col-toggle-wrap')) showColMenu.value = false
    }

    // ── Suspend / Resume ─────────────────────────────────────────────────────
    const suspendVm = async (vm) => {
      vm._busy = true
      try {
        await api.pveVm.suspend(vm.hostId, vm.node, vm.vmid)
        toast.success(`VM ${vm.vmid} suspended`)
        setTimeout(fetchAllProxmoxVMs, 2000)
      } catch (err) {
        toast.error(`Failed to suspend VM ${vm.vmid}: ${err.response?.data?.detail || err.message}`)
      } finally { vm._busy = false }
    }

    const resumeVm = async (vm) => {
      vm._busy = true
      try {
        await api.pveVm.resume(vm.hostId, vm.node, vm.vmid)
        toast.success(`VM ${vm.vmid} resumed`)
        setTimeout(fetchAllProxmoxVMs, 2000)
      } catch (err) {
        toast.error(`Failed to resume VM ${vm.vmid}: ${err.response?.data?.detail || err.message}`)
      } finally { vm._busy = false }
    }

    // ── Single-VM Snapshot ───────────────────────────────────────────────────
    const showSnapshotModal = ref(false)
    const snapshotVm = ref(null)
    const snapshotName = ref('')
    const snapshotDesc = ref('')
    const snapshotVmState = ref(false)
    const snapshotRunning = ref(false)

    const openSnapshotModal = (vm) => {
      snapshotVm.value = vm
      const now = new Date()
      const pad = n => String(n).padStart(2, '0')
      snapshotName.value = `snap-${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`
      snapshotDesc.value = ''
      snapshotVmState.value = false
      showSnapshotModal.value = true
    }

    const runSnapshot = async () => {
      if (!snapshotName.value.trim()) return
      snapshotRunning.value = true
      const vm = snapshotVm.value
      try {
        await api.pveVm.createSnapshot(vm.hostId, vm.node, vm.vmid, {
          snapname: snapshotName.value.trim(),
          description: snapshotDesc.value.trim(),
          vmstate: snapshotVmState.value ? 1 : 0,
        })
        toast.success(`Snapshot created for VM ${vm.vmid}`)
        showSnapshotModal.value = false
      } catch (err) {
        toast.error(`Snapshot failed: ${err.response?.data?.detail || err.message}`)
      } finally { snapshotRunning.value = false }
    }

    // ── Migrate ──────────────────────────────────────────────────────────────
    const showMigrateModal = ref(false)
    const migrateVm = ref(null)
    const migrateTarget = ref('')
    const migrateOnline = ref(true)
    const migrateTargetStorage = ref('')
    const migrateBwlimit = ref('')
    const migrateMigrationType = ref('secure')
    const migrateMigrationNetwork = ref('')
    const migrateForce = ref(false)
    const migrateRunning = ref(false)
    const migrateNodes = ref([])
    const migrateTargetStorages = ref([])
    const migrateStorageLoading = ref(false)
    const migrateVmDiskStorages = ref([])  // source storage names used by VM disks

    const openMigrateModal = async (vm) => {
      migrateVm.value = vm
      migrateTarget.value = ''
      migrateOnline.value = vm.status === 'running'
      migrateTargetStorage.value = ''
      migrateBwlimit.value = ''
      migrateMigrationType.value = 'secure'
      migrateMigrationNetwork.value = ''
      migrateNodes.value = []
      migrateTargetStorages.value = []
      migrateVmDiskStorages.value = []
      showMigrateModal.value = true

      // Fetch nodes and VM config in parallel
      const [nodesRes, configRes] = await Promise.allSettled([
        api.proxmox.listNodes(vm.hostId),
        api.pveVm.getConfig(vm.hostId, vm.node, vm.vmid),
      ])
      migrateNodes.value = nodesRes.status === 'fulfilled'
        ? (nodesRes.value.data || []).filter(n => n.node_name !== vm.node).map(n => ({ node: n.node_name, status: n.status }))
        : []
      if (configRes.status === 'fulfilled') {
        const cfg = configRes.value.data || {}
        const diskKeys = ['virtio', 'scsi', 'ide', 'sata']
        const storages = new Set()
        Object.entries(cfg).forEach(([k, v]) => {
          if (diskKeys.some(d => k.startsWith(d)) && typeof v === 'string' && v.includes(':')) {
            storages.add(v.split(':')[0])
          }
        })
        migrateVmDiskStorages.value = [...storages]
      }
    }

    watch(migrateTarget, async (node) => {
      migrateTargetStorages.value = []
      migrateTargetStorage.value = ''
      if (!node || !migrateVm.value) return
      migrateStorageLoading.value = true
      try {
        const res = await api.pveNode.listStorage(migrateVm.value.hostId, node)
        const storages = (res.data || []).filter(s => s.content && s.content.includes('images'))
        migrateTargetStorages.value = storages
        // Auto-select: prefer a storage whose name matches source, else first available
        const sourceStorages = migrateVmDiskStorages.value
        const match = storages.find(s => sourceStorages.includes(s.storage))
        migrateTargetStorage.value = match ? match.storage : (storages[0]?.storage || '')
      } catch { migrateTargetStorages.value = [] }
      finally { migrateStorageLoading.value = false }
    })

    const runMigrate = async () => {
      if (!migrateTarget.value) return
      migrateRunning.value = true
      const vm = migrateVm.value
      try {
        const payload = {
          target: migrateTarget.value,
          online: migrateOnline.value,

          migration_type: migrateMigrationType.value || undefined,
        }
        if (migrateTargetStorage.value) payload.targetstorage = migrateTargetStorage.value
        if (migrateBwlimit.value !== '') payload.bwlimit = parseInt(migrateBwlimit.value) || 0
        if (migrateMigrationNetwork.value) payload.migration_network = migrateMigrationNetwork.value
        await api.pveVm.migrate(vm.hostId, vm.node, vm.vmid, payload)
        toast.success(`VM ${vm.vmid} migration to ${migrateTarget.value} initiated`)
        showMigrateModal.value = false
        setTimeout(fetchAllProxmoxVMs, 3000)
      } catch (err) {
        toast.error(`Migration failed: ${err.response?.data?.detail || err.message}`)
      } finally { migrateRunning.value = false }
    }

    // ── Clone ────────────────────────────────────────────────────────────────
    const showCloneModal = ref(false)
    const cloneVm = ref(null)
    const cloneNewId = ref(null)
    const cloneName = ref('')
    const cloneTarget = ref('')
    const cloneFull = ref(true)
    const cloneRunning = ref(false)
    const cloneNodes = ref([])

    const openCloneModal = async (vm) => {
      cloneVm.value = vm
      cloneNewId.value = null
      cloneName.value = `${vm.name || 'vm'}-clone`
      cloneTarget.value = ''
      cloneFull.value = true
      cloneNodes.value = []
      showCloneModal.value = true
      try {
        const res = await api.proxmox.listNodes(vm.hostId)
        cloneNodes.value = (res.data || []).filter(n => n.node_name !== vm.node)
          .map(n => ({ node: n.node_name }))
      } catch { cloneNodes.value = [] }
    }

    const runClone = async () => {
      if (!cloneNewId.value) return
      cloneRunning.value = true
      const vm = cloneVm.value
      const params = { newid: cloneNewId.value, full: cloneFull.value ? 1 : 0 }
      if (cloneName.value.trim()) params.name = cloneName.value.trim()
      if (cloneTarget.value) params.target = cloneTarget.value
      try {
        await api.pveVm.clone(vm.hostId, vm.node, vm.vmid, params)
        toast.success(`Clone of VM ${vm.vmid} → VM ${cloneNewId.value} initiated`)
        showCloneModal.value = false
        setTimeout(fetchAllProxmoxVMs, 4000)
      } catch (err) {
        toast.error(`Clone failed: ${err.response?.data?.detail || err.message}`)
      } finally { cloneRunning.value = false }
    }

    // ── Single VM Delete (All Proxmox tab) ───────────────────────────────────
    const showVmDeleteModal = ref(false)
    const vmDeleteTarget = ref(null)
    const vmDeleteConfirm = ref('')

    const openVmDeleteModal = (vm) => {
      vmDeleteTarget.value = vm
      vmDeleteConfirm.value = ''
      showVmDeleteModal.value = true
    }

    const confirmVmDelete = async () => {
      if (vmDeleteConfirm.value !== String(vmDeleteTarget.value.vmid)) return
      const vm = vmDeleteTarget.value
      showVmDeleteModal.value = false
      try {
        if (vm.status === 'running') {
          await api.pveVm.stop(vm.hostId, vm.node, vm.vmid)
          await new Promise(r => setTimeout(r, 3000))
        }
        await api.pveVm.deleteVm(vm.hostId, vm.node, vm.vmid)
        toast.success(`VM ${vm.vmid} deleted`)
        fetchAllProxmoxVMs()
      } catch (err) {
        toast.error(`Delete failed: ${err.response?.data?.detail || err.message}`)
      }
    }

    // ── Tags helpers ────────────────────────────────────────────────────────
    const parseTags = (tagsStr) => {
      if (!tagsStr) return []
      return tagsStr.split(';').map(t => t.trim()).filter(Boolean)
    }

    const tagColor = _tagColor
    const anyVmHasTags = computed(() => allVMs.value.some(vm => vm.tags))

    const activeTagFilters = ref(new Set())
    const allTagList = computed(() => {
      const tagSet = new Set()
      allVMs.value.forEach(vm => parseTags(vm.tags).forEach(t => tagSet.add(t)))
      return [...tagSet].sort()
    })

    const toggleTagFilter = (tag) => {
      const s = new Set(activeTagFilters.value)
      if (s.has(tag)) s.delete(tag)
      else s.add(tag)
      activeTagFilters.value = s
    }

    // ── Inline tag editor ───────────────────────────────────────────────────
    const showTagEditorModal = ref(false)
    const tagEditorVm = ref(null)
    const tagEditorTags = ref([])
    const tagEditorInput = ref('')
    const tagEditorSaving = ref(false)

    const openTagEditor = (vm) => {
      tagEditorVm.value = vm
      tagEditorTags.value = [...parseTags(vm.tags)]
      tagEditorInput.value = ''
      showTagEditorModal.value = true
    }

    const closeTagEditor = () => {
      showTagEditorModal.value = false
      tagEditorVm.value = null
      tagEditorTags.value = []
      tagEditorInput.value = ''
    }

    const addTagFromEditor = () => {
      const t = tagEditorInput.value.trim()
      if (!t) return
      if (!tagEditorTags.value.includes(t)) tagEditorTags.value.push(t)
      tagEditorInput.value = ''
    }

    const removeTagFromEditor = (tag) => {
      tagEditorTags.value = tagEditorTags.value.filter(t => t !== tag)
    }

    const saveTagEditor = async () => {
      if (!tagEditorVm.value) return
      tagEditorSaving.value = true
      const vm = tagEditorVm.value
      try {
        await api.pveVm.updateConfig(vm.hostId, vm.node, vm.vmid, { tags: tagEditorTags.value.join(';') })
        vm.tags = tagEditorTags.value.join(';')
        toast.success(`Tags saved for VM ${vm.vmid}`)
        closeTagEditor()
      } catch (err) {
        const msg = err.response?.data?.detail || err.message || 'Unknown error'
        toast.error(`Failed to save tags: ${msg}`)
      } finally {
        tagEditorSaving.value = false
      }
    }

    // ── IP extraction ───────────────────────────────────────────────────────
    const extractIP = (vm) => {
      // Try to find an IP-like string in description or name
      const text = vm.description || vm.name || ''
      const match = text.match(/\b(\d{1,3}\.){3}\d{1,3}\b/)
      return match ? match[0] : '—'
    }

    // ── Uptime formatting ────────────────────────────────────────────────────
    const formatUptime = (seconds) => {
      if (!seconds || seconds <= 0) return '—'
      const d = Math.floor(seconds / 86400)
      const h = Math.floor((seconds % 86400) / 3600)
      const m = Math.floor((seconds % 3600) / 60)
      if (d > 0) return `${d}d ${h}h`
      if (h > 0) return `${h}h ${m}m`
      return `${m}m`
    }

    // ── Shared helpers ─────────────────────────────────────────────────────
    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
    }

    const getStatusBadgeClass = (status) => {
      const classMap = { running: 'badge-success', stopped: 'badge-danger', paused: 'badge-warning', suspended: 'badge-warning', unknown: 'badge-secondary' }
      return classMap[(status || '').toLowerCase()] || 'badge-info'
    }

    // ── Auto-refresh ────────────────────────────────────────────────────────
    const allCountdown = ref(0)
    let managedInterval = null
    let allInterval = null
    let allTickInterval = null

    const resetAllCountdown = (intervalSecs) => { allCountdown.value = intervalSecs }

    const startAllIntervals = (intervalSecs) => {
      clearInterval(allInterval)
      clearInterval(allTickInterval)
      resetAllCountdown(intervalSecs)
      allInterval = setInterval(() => {
        if (document.visibilityState === 'hidden') return
        if (activeTab.value === 'all') fetchAllProxmoxVMs()
        resetAllCountdown(intervalSecs)
      }, intervalSecs * 1000)
      allTickInterval = setInterval(() => {
        if (document.visibilityState === 'hidden') return
        if (allCountdown.value > 0) allCountdown.value--
      }, 1000)
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && activeTab.value === 'all') fetchAllProxmoxVMs()
    }

    onMounted(() => {
      fetchVMs()
      const intervalSecs = parseInt(localStorage.getItem('depl0y_refresh_interval') || '30', 10)
      managedInterval = setInterval(() => {
        if (document.visibilityState === 'hidden') return
        if (activeTab.value === 'managed') fetchVMs()
      }, intervalSecs * 1000)
      startAllIntervals(intervalSecs)
      document.addEventListener('visibilitychange', handleVisibilityChange)
      document.addEventListener('mousedown', handleMenuOutsideClick)
    })

    onUnmounted(() => {
      clearInterval(managedInterval)
      clearInterval(allInterval)
      clearInterval(allTickInterval)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      document.removeEventListener('mousedown', handleMenuOutsideClick)
    })

    return {
      activeTab, switchTab,
      vms, loading, managedError, sortField, sortDirection, statusFilter, managedSearch, managedStatusFilter, managedNodeFilter, managedNodes,
      filteredVMs, showDeleteConfirmModal, vmToDelete, deleteConfirmInput,
      sortBy, startVM, stopVM, powerOffVM, restartVM,
      showDeleteModal, closeDeleteModal, deleteVM, clearFilter,
      allVMs, allLoading, allError, allSearch, allStatusFilter, allSortField, allSortDirection,
      allPartialFailedHosts, allTimeoutWarning,
      showTemplates, templateCount,
      filteredAllVMs, groupedVMs, fetchAllProxmoxVMs, allSortBy,
      navigateToVM, allStartVM, allStopVM, allShutdownVM, allCountdown, openConsole,
      exportCSV,
      savedFilterPresets, showSavePresetModal, newPresetName, savePreset, applyPreset, openSavePresetModal,
      visibleColumns, allColumns, showColMenu, groupByNode, saveColumnPrefs,
      showAdvFilter, advFilter, advFilterCount, clearAdvFilter, uniqueHosts, uniqueNodes,
      formatBytes, getStatusBadgeClass, formatUptime, extractIP,
      parseTags, tagColor, anyVmHasTags,
      activeTagFilters, allTagList, toggleTagFilter,
      showTagEditorModal, tagEditorVm, tagEditorTags, tagEditorInput, tagEditorSaving,
      openTagEditor, closeTagEditor, addTagFromEditor, removeTagFromEditor, saveTagEditor,
      selectedVmKeys, bulkRunning, vmKey, toggleSelectVm,
      allPageSelected, somePageSelected, toggleSelectAll, clearSelection, bulkAction,
      showBulkSnapshotModal, showBulkTagModal, showBulkDeleteModal,
      bulkSnapName, bulkSnapDescription, bulkTagValue, bulkDeleteConfirm,
      bulkOpResults, bulkOpDone, selectedVmObjects,
      openBulkSnapshotModal, openBulkTagModal, openBulkDeleteModal, closeBulkModal,
      runBulkSnapshot, runBulkTag, runBulkDelete,
      toggleGroupSelect,
      adaptManagedVm,
      openMoreMenuKey, toggleMoreMenu,
      suspendVm, resumeVm,
      showSnapshotModal, snapshotVm, snapshotName, snapshotDesc, snapshotVmState, snapshotRunning,
      openSnapshotModal, runSnapshot,
      showMigrateModal, migrateVm, migrateTarget, migrateOnline,
      migrateTargetStorage, migrateBwlimit, migrateMigrationType, migrateMigrationNetwork,
      migrateRunning, migrateNodes, migrateTargetStorages, migrateStorageLoading, migrateVmDiskStorages,
      openMigrateModal, runMigrate,
      showCloneModal, cloneVm, cloneNewId, cloneName, cloneTarget, cloneFull, cloneRunning, cloneNodes,
      openCloneModal, runClone,
      showVmDeleteModal, vmDeleteTarget, vmDeleteConfirm,
      openVmDeleteModal, confirmVmDelete,
    }
  }
}
</script>

<style scoped>
/* ── Tab bar ──────────────────────────────────────────────────────────────── */
.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 1rem;
  border-bottom: 2px solid var(--border, #e2e8f0);
}

.tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  padding: 0.6rem 1.25rem;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--text-muted, #64748b);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover { color: var(--text-primary, #1e293b); }
.tab-btn-active { color: var(--primary-color, #3b82f6); border-bottom-color: var(--primary-color, #3b82f6); }

/* ── VM name link ─────────────────────────────────────────────────────────── */
.vm-name-link { color: var(--primary-color, #3b82f6); text-decoration: none; }
.vm-name-link:hover { text-decoration: underline; }
.notes-chip {
  display: inline-flex; align-items: center; cursor: default; font-size: 0.72rem;
  padding: 1px 4px; border-radius: 4px;
  background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.2);
  color: var(--text-secondary);
}
.ml-1 { margin-left: 0.25rem; }

/* ── Clickable row ────────────────────────────────────────────────────────── */
.row-clickable { cursor: pointer; transition: background 0.1s; }
.row-clickable:hover td { background-color: rgba(59, 130, 246, 0.04); }

/* ── Existing styles ──────────────────────────────────────────────────────── */
/* ── More-actions dropdown ─────────────────────────────────────────────────── */
.more-menu-wrap { position: relative; z-index: 300; }
.more-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  background: var(--surface, #fff);
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  z-index: 1000;
  min-width: 150px;
  padding: 4px 0;
}
.more-menu button {
  display: block;
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  padding: 0.45rem 0.85rem;
  font-size: 0.875rem;
  cursor: pointer;
  color: var(--text-primary, #1e293b);
  white-space: nowrap;
}
.more-menu button:hover { background: var(--background, #f8fafc); }
.more-menu-danger { color: var(--danger-color, #ef4444) !important; }

.btn-sm { padding: 0.25rem 0.5rem; font-size: 0.875rem; }
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { background-color: var(--background); }
.sort-indicator { margin-left: 0.25rem; font-size: 0.75rem; opacity: 0.7; }
.mono { font-family: 'Fira Mono', 'Consolas', monospace; }

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background-color: var(--background);
  border-bottom: 1px solid var(--border);
}

.filter-info { display: flex; align-items: center; gap: 0.5rem; }
.filter-count { font-size: 0.875rem; color: var(--text-muted); margin-left: 0.25rem; }
.filter-actions { display: flex; align-items: center; gap: 0.5rem; }
.preset-wrap { display: flex; align-items: center; gap: 0.35rem; }

/* ── Column visibility dropdown ───────────────────────────────────────────── */
.col-toggle-wrap { position: relative; z-index: 300; }
.col-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  background: var(--surface);
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 0.375rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  z-index: 1000;
  min-width: 170px;
  padding: 0.25rem 0;
}
.col-menu-header {
  padding: 0.4rem 0.75rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border, #e2e8f0);
  margin-bottom: 0.25rem;
}
.col-menu-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0.75rem;
  font-size: 0.85rem;
  cursor: pointer;
  color: var(--text-primary);
  transition: background 0.1s;
}
.col-menu-item:hover { background: var(--background); }

/* ── Group by node toggle ──────────────────────────────────────────────────── */
.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}

/* ── Advanced filter panel ──────────────────────────────────────────────────── */
.adv-filter-bar {
  border-bottom: 1px solid var(--border, #e2e8f0);
  background: var(--background);
}
.adv-filter-toggle {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.45rem 1rem;
  background: none;
  border: none;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.12s;
}
.adv-filter-toggle:hover { color: var(--primary-color, #3b82f6); }
.adv-filter-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-color, #3b82f6);
  color: #fff;
  border-radius: 9999px;
  font-size: 0.65rem;
  font-weight: 700;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
}
.adv-filter-arrow { margin-left: auto; font-size: 0.65rem; opacity: 0.6; }
.adv-filter-panel {
  padding: 0.75rem 1rem 1rem;
  border-top: 1px solid var(--border, #e2e8f0);
  animation: slideDown 0.15s ease;
}
@keyframes slideDown { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }
.adv-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}
.adv-filter-field label {
  display: block;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.25rem;
}
.adv-filter-tags-label {
  display: block;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.4rem;
}
.adv-filter-tag-pills { display: flex; flex-wrap: wrap; gap: 0.35rem; }

/* ── Node group ──────────────────────────────────────────────────────────── */
.node-group { margin-bottom: 1.5rem; }
.node-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: var(--background);
  border-top: 1px solid var(--border, #e2e8f0);
  border-bottom: 1px solid var(--border, #e2e8f0);
}
.node-group-name { font-size: 0.85rem; font-weight: 700; color: var(--text-primary); }
.node-group-count { font-size: 0.75rem; color: var(--text-muted); }
.node-group-table { margin-bottom: 0; }

/* ── Modals ───────────────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal-content {
  background-color: var(--surface);
  border-radius: 0.5rem;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  max-width: 500px; width: 90%;
  max-height: 90vh; overflow-y: auto;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 1rem 1.5rem; border-bottom: 1px solid var(--border-color);
}
.modal-header h3 { margin: 0; font-size: 1.25rem; color: var(--text-primary); }
.btn-close {
  background: none; border: none; font-size: 2rem; line-height: 1;
  color: var(--text-secondary); cursor: pointer; padding: 0;
  width: 2rem; height: 2rem; display: flex; align-items: center; justify-content: center;
}
.btn-close:hover { color: var(--text-primary); }
.modal-body { padding: 1.5rem; }
.modal-footer {
  display: flex; justify-content: flex-end; gap: 0.5rem;
  padding: 1rem 1.5rem; border-top: 1px solid var(--border-color);
}

.text-danger { color: #991b1b; font-weight: 500; }
.text-muted { color: #475569; }
.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }
.form-group { margin-top: 1rem; }
.form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; color: var(--text-primary); }
.form-control {
  width: 100%; padding: 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background-color: var(--background);
  color: var(--text-primary); font-size: 1rem;
}
.form-control:focus { outline: none; border-color: var(--primary-color); }
.btn-secondary { background-color: var(--secondary-color); color: white; }
.btn-secondary:hover { opacity: 0.9; }

/* ── Refresh countdown ────────────────────────────────────────────────────── */
.refresh-countdown { font-size: 0.75rem; color: var(--text-muted, #64748b); margin-right: 0.5rem; }

/* ── Checkbox column ─────────────────────────────────────────────────────── */
.cb-col { width: 2rem; text-align: center; padding-left: 0.5rem; padding-right: 0.25rem; }
.row-selected td { background-color: rgba(59, 130, 246, 0.07); }

/* ── Bulk action bar ─────────────────────────────────────────────────────── */
.bulk-action-bar {
  position: sticky; bottom: 0; left: 0; right: 0;
  display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
  padding: 0.6rem 1rem;
  background: var(--surface);
  border-top: 2px solid var(--primary-color, #3b82f6);
  box-shadow: 0 -4px 16px rgba(0,0,0,0.15);
  z-index: 10;
}
.bulk-count { font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-right: 0.25rem; }
.bulk-clear-link { font-size: 0.8rem; color: var(--text-secondary); text-decoration: underline; margin-left: auto; }
.bulk-clear-link:hover { color: var(--text-primary); }

/* ── VM Tags ──────────────────────────────────────────────────────────────── */
.vm-tags { display: flex; flex-wrap: wrap; gap: 0.25rem; }

/* ── Tag Filter Bar ───────────────────────────────────────────────────────── */
.tag-filter-bar {
  display: flex; align-items: center; flex-wrap: wrap; gap: 0.4rem;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--border, #e2e8f0);
  background: var(--background);
  overflow-x: auto; -webkit-overflow-scrolling: touch;
}
.tag-filter-label {
  font-size: 0.75rem; font-weight: 600; color: var(--text-muted, #64748b);
  white-space: nowrap; text-transform: uppercase; letter-spacing: 0.04em; margin-right: 0.25rem;
}
.tag-filter-pill {
  display: inline-block; font-size: 0.7rem; font-weight: 600;
  padding: 0.2rem 0.6rem; border-radius: 9999px;
  border: 1.5px solid transparent; background: transparent;
  cursor: pointer; white-space: nowrap; transition: background 0.12s, color 0.12s;
  letter-spacing: 0.02em;
}
.tag-filter-pill:hover { opacity: 0.8; }
.tag-filter-pill-active { font-weight: 700; }

/* ── Bulk results ─────────────────────────────────────────────────────────── */
.bulk-results-table {
  border: 1px solid var(--border, #e2e8f0); border-radius: 0.375rem;
  overflow: hidden; margin-top: 1rem;
}
.bulk-results-header {
  display: grid; grid-template-columns: 70px 1fr 80px 90px; gap: 0.5rem;
  padding: 0.4rem 0.75rem; background: var(--background);
  border-bottom: 1px solid var(--border, #e2e8f0);
  font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted, #64748b);
}
.bulk-results-row {
  display: grid; grid-template-columns: 70px 1fr 80px 90px; gap: 0.5rem;
  padding: 0.45rem 0.75rem; align-items: center; font-size: 0.875rem;
  border-bottom: 1px solid var(--border, #e2e8f0);
}
.bulk-results-row:last-child { border-bottom: none; }
.bulk-done-summary { margin-top: 0.75rem; font-size: 0.875rem; font-weight: 600; color: var(--text-primary); }

.bulk-delete-list {
  list-style: none; padding: 0; margin: 0.5rem 0 1rem 0;
  max-height: 200px; overflow-y: auto;
  border: 1px solid var(--border, #e2e8f0); border-radius: 0.375rem;
}
.bulk-delete-list li { padding: 0.4rem 0.75rem; font-size: 0.875rem; border-bottom: 1px solid var(--border, #e2e8f0); }
.bulk-delete-list li:last-child { border-bottom: none; }
.ml-1 { margin-left: 0.25rem; }
.mt-2 { margin-top: 1rem; }

/* ── Console button ──────────────────────────────────────────────────────── */
.btn-console { display: inline-flex; align-items: center; gap: 0.2rem; }

/* ── Empty state ── */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 0.75rem; padding: 3.5rem 1.5rem; text-align: center;
}
.empty-icon-wrap {
  display: flex; align-items: center; justify-content: center;
  width: 80px; height: 80px; border-radius: 50%;
  background: var(--background); border: 2px dashed var(--border-color); color: var(--text-muted);
}
.empty-title { font-size: 1rem; font-weight: 600; color: var(--text-primary); margin: 0; }
.empty-subtitle { font-size: 0.875rem; color: var(--text-secondary); margin: 0; }

/* ── Error / Warning Banners ─────────────────────────────────────────────── */
.error-banner-inline {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.65rem 1rem;
  background: rgba(239, 68, 68, 0.07);
  border-bottom: 1px solid rgba(239, 68, 68, 0.25);
  font-size: 0.875rem;
  color: var(--text-primary);
}
.error-banner-inline svg { color: #ef4444; flex-shrink: 0; }

.warning-banner-inline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 1rem;
  background: rgba(245, 158, 11, 0.07);
  border-bottom: 1px solid rgba(245, 158, 11, 0.25);
  font-size: 0.825rem;
  color: var(--text-primary);
}
.warning-banner-inline svg { color: #f59e0b; flex-shrink: 0; }

.btn-inline-close-sm {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  color: var(--text-muted);
  padding: 0 0.2rem;
  margin-left: auto;
}
.btn-inline-close-sm:hover { color: var(--text-primary); }

/* ── Empty state flat (within card, no border of own) ─────────────────────── */
.empty-state-flat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1.5rem;
  text-align: center;
}

/* ── Mobile ──────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .filter-bar { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
  .filter-bar .filter-info { width: 100%; }
  .filter-bar input.form-control, .filter-bar select.form-control { width: 100% !important; }
  .table-container table thead { display: none; }
  .table-container table tr { display: block; border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 0.5rem; background: var(--surface); overflow: hidden; }
  .table-container table tr.row-selected { border-color: var(--primary-color); }
  .table-container table td { display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0.75rem; border-top: 1px solid var(--border-color); border-bottom: none; }
  .table-container table td:first-child { border-top: none; }
  .table-container table td::before { content: attr(data-label); font-weight: 600; color: var(--text-secondary); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; flex-shrink: 0; margin-right: 0.5rem; }
  .bulk-action-bar { position: fixed; bottom: 0; left: 0; right: 0; flex-direction: column; align-items: stretch; padding: 0.75rem 1rem; gap: 0.4rem; }
  .bulk-action-bar .btn { justify-content: center; }
  .bulk-clear-link { text-align: center; margin-left: 0; }
  .tab-bar { overflow-x: auto; -webkit-overflow-scrolling: touch; white-space: nowrap; flex-wrap: nowrap; }
  .adv-filter-grid { grid-template-columns: 1fr 1fr; }
}
</style>
