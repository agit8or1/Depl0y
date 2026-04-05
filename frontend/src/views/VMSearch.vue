<template>
  <div class="vm-search-page">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2>VM Search</h2>
        <p class="text-muted">Search and filter virtual machines across all hosts</p>
      </div>
      <div class="header-actions">
        <button @click="showSaveModal = true" class="btn btn-outline btn-sm" :disabled="!canSave">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
          Save Search
        </button>
        <button @click="exportCsv" class="btn btn-outline btn-sm" :disabled="results.length === 0">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Export CSV
        </button>
        <button v-if="selectedKeys.size > 0" class="btn btn-secondary btn-sm" @click="showBulkTagModal = true">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>
          Tag ({{ selectedKeys.size }})
        </button>
        <button v-if="selectedKeys.size > 0" class="btn btn-primary btn-sm" @click="goToBulkOps">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          Bulk Ops ({{ selectedKeys.size }})
        </button>
      </div>
    </div>

    <!-- Saved Searches Bar -->
    <div v-if="savedSearches.length > 0" class="saved-searches-bar">
      <span class="saved-label">Saved:</span>
      <div class="saved-chips">
        <button
          v-for="ss in savedSearches"
          :key="ss.name"
          class="saved-chip"
          @click="loadSavedSearch(ss)"
          :title="ss.name"
        >
          {{ ss.name }}
          <span class="saved-chip-del" @click.stop="deleteSavedSearch(ss.name)">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </span>
        </button>
      </div>
    </div>

    <div class="search-layout">
      <!-- Filter Sidebar -->
      <aside class="filter-sidebar card">
        <div class="sidebar-title">Filters</div>

        <!-- Status -->
        <div class="filter-section">
          <label class="filter-label">Status</label>
          <div class="radio-group">
            <label class="radio-opt"><input type="radio" v-model="filters.status" value="" /> All</label>
            <label class="radio-opt"><input type="radio" v-model="filters.status" value="running" />
              <span class="status-dot dot-running"></span> Running
            </label>
            <label class="radio-opt"><input type="radio" v-model="filters.status" value="stopped" />
              <span class="status-dot dot-stopped"></span> Stopped
            </label>
            <label class="radio-opt"><input type="radio" v-model="filters.status" value="paused" />
              <span class="status-dot dot-paused"></span> Paused
            </label>
          </div>
        </div>

        <!-- Host -->
        <div class="filter-section">
          <label class="filter-label">Host</label>
          <select v-model="filters.host_id" class="form-input filter-select">
            <option value="">All Hosts</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name || h.hostname }}</option>
          </select>
        </div>

        <!-- Node -->
        <div class="filter-section">
          <label class="filter-label">Node</label>
          <input v-model="filters.node" class="form-input" placeholder="e.g. pve1" />
        </div>

        <!-- Tags (checkboxes) -->
        <div class="filter-section">
          <label class="filter-label">
            Tags
            <span v-if="tagsLoading" class="loading-dot"></span>
          </label>
          <div v-if="allTags.length > 0" class="tag-checkbox-list">
            <label
              v-for="t in allTags"
              :key="t.tag"
              class="tag-check-opt"
            >
              <input
                type="checkbox"
                :value="t.tag"
                :checked="selectedFilterTags.has(t.tag)"
                @change="toggleFilterTag(t.tag)"
              />
              <span class="tag-pill-sm" :style="{ background: tagColor(t.tag) }">{{ t.tag }}</span>
              <span class="tag-count">{{ t.count }}</span>
            </label>
          </div>
          <div v-else-if="!tagsLoading" class="text-muted text-xs">No tags found</div>
          <!-- Manual comma-separated fallback -->
          <input
            v-model="filters.tagsManual"
            class="form-input mt-1"
            placeholder="or type tags (comma-sep)"
            @keydown.enter.prevent=""
          />
        </div>

        <!-- OS Type -->
        <div class="filter-section">
          <label class="filter-label">OS Type</label>
          <input v-model="filters.os_type" class="form-input" placeholder="e.g. l26, win10" />
        </div>

        <!-- CPU Range -->
        <div class="filter-section">
          <label class="filter-label">CPU Usage %</label>
          <div class="range-row">
            <input v-model.number="filters.min_cpu" class="form-input range-input" type="number" min="0" max="100" placeholder="Min" />
            <span class="range-sep">–</span>
            <input v-model.number="filters.max_cpu" class="form-input range-input" type="number" min="0" max="100" placeholder="Max" />
          </div>
        </div>

        <!-- RAM Range -->
        <div class="filter-section">
          <label class="filter-label">RAM (GB)</label>
          <div class="range-row">
            <input v-model.number="filters.min_ram_gb" class="form-input range-input" type="number" min="0" placeholder="Min" />
            <span class="range-sep">–</span>
            <input v-model.number="filters.max_ram_gb" class="form-input range-input" type="number" min="0" placeholder="Max" />
          </div>
        </div>

        <button @click="clearFilters" class="btn btn-outline btn-sm mt-2" style="width:100%;">Clear Filters</button>
      </aside>

      <!-- Main content -->
      <div class="search-main">
        <!-- Search Bar -->
        <div class="search-bar card">
          <div class="search-input-wrap">
            <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input
              ref="searchInputRef"
              v-model="searchQuery"
              type="text"
              class="search-input"
              placeholder="Search VMs… or use tag:prod, node:pve1, status:running"
              @keyup.enter="runSearch"
              @keyup.escape="clearSearch"
              @input="onSearchInput"
            />
            <button v-if="searchQuery" @click="clearSearch" class="clear-btn" title="Clear (Esc)">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
            <button @click="runSearch" class="btn btn-primary btn-sm" :disabled="searching">
              {{ searching ? 'Searching…' : 'Search' }}
            </button>
          </div>
          <div class="search-meta text-sm text-muted" v-if="!searching && searched">
            {{ total }} result{{ total !== 1 ? 's' : '' }} found
            <span v-if="total > pageSize"> — showing {{ skip + 1 }}–{{ Math.min(skip + pageSize, total) }}</span>
          </div>
        </div>

        <!-- Search Tips -->
        <details class="search-tips card mt-1">
          <summary class="tips-summary">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            Search Tips
          </summary>
          <div class="tips-body">
            <div class="tips-grid">
              <div class="tip-item"><code>tag:production</code> — filter by tag</div>
              <div class="tip-item"><code>node:pve01</code> — filter by node name</div>
              <div class="tip-item"><code>status:running</code> — filter by status</div>
              <div class="tip-item"><code>host:myhost</code> — filter by host name</div>
              <div class="tip-item"><code>101</code> — search by VMID</div>
              <div class="tip-item"><code>web-server</code> — search by name fragment</div>
            </div>
            <p class="tips-note">Operators are extracted from the query and applied alongside sidebar filters. Remaining text searches name, VMID, node and tags.</p>
            <p class="tips-note">Keyboard: <kbd>Enter</kbd> to search, <kbd>Esc</kbd> to clear the search box.</p>
          </div>
        </details>

        <!-- View toggle -->
        <div v-if="results.length > 0 || (searched && !searching)" class="view-toggle-row mt-1">
          <div class="view-toggle">
            <button :class="['toggle-btn', { active: viewMode === 'cards' }]" @click="viewMode = 'cards'" title="Card view">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
            </button>
            <button :class="['toggle-btn', { active: viewMode === 'table' }]" @click="viewMode = 'table'" title="Table view">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            </button>
          </div>
          <span class="text-sm text-muted" v-if="!searching && searched">
            {{ total }} VM{{ total !== 1 ? 's' : '' }}
            <span v-if="selectedKeys.size > 0"> · {{ selectedKeys.size }} selected</span>
          </span>
        </div>

        <!-- Loading -->
        <div v-if="searching" class="loading-spinner mt-2"></div>

        <!-- Error -->
        <div v-else-if="error" class="card empty-state mt-2">
          <p class="text-danger">{{ error }}</p>
          <button @click="runSearch" class="btn btn-outline btn-sm mt-1">Retry</button>
        </div>

        <!-- No results -->
        <div v-else-if="searched && results.length === 0" class="card empty-state mt-2">
          <div class="empty-icon-wrap">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          </div>
          <h4 class="empty-title">No VMs match your search</h4>
          <p class="empty-subtitle">Try adjusting your query or removing some filters.</p>
        </div>

        <!-- CARD VIEW -->
        <template v-else-if="results.length > 0 && viewMode === 'cards'">
          <!-- Bulk action bar -->
          <div v-if="selectedKeys.size > 0" class="bulk-bar mt-1">
            <span class="bulk-count">{{ selectedKeys.size }} selected</span>
            <button @click="bulkStart" class="btn btn-primary btn-sm" :disabled="bulkRunning">Start</button>
            <button @click="bulkShutdown" class="btn btn-warning btn-sm" :disabled="bulkRunning">Shutdown</button>
            <button @click="bulkStop" class="btn btn-danger btn-sm" :disabled="bulkRunning">Stop</button>
            <button @click="showBulkTagModal = true" class="btn btn-secondary btn-sm" :disabled="bulkRunning">Tag</button>
            <button @click="selectedKeys.clear()" class="btn btn-outline btn-sm">Clear</button>
          </div>

          <div class="vm-cards-grid mt-1">
            <div
              v-for="vm in sortedResults"
              :key="vmKey(vm)"
              :class="['vm-card', { 'vm-card-selected': selectedKeys.has(vmKey(vm)) }]"
              @click="toggleSelect(vm)"
            >
              <div class="vm-card-header">
                <div class="vm-card-check">
                  <input
                    type="checkbox"
                    :checked="selectedKeys.has(vmKey(vm))"
                    @change.stop="toggleSelect(vm)"
                    @click.stop
                  />
                </div>
                <div class="vm-card-icon">
                  <span :class="['vm-os-icon', osIconClass(vm)]">
                    <svg v-if="isLinux(vm)" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/><circle cx="8.5" cy="9.5" r="1.5"/><circle cx="15.5" cy="9.5" r="1.5"/><path d="M12 17.5c-2.33 0-4.31-1.46-5.11-3.5h10.22c-.8 2.04-2.78 3.5-5.11 3.5z"/></svg>
                    <svg v-else-if="isWindows(vm)" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801"/></svg>
                    <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                  </span>
                </div>
                <div class="vm-card-title">
                  <div class="vm-card-name" @click.stop="navigateTo(vm)">
                    <span v-html="highlight(vm.name || '(no name)')"></span>
                  </div>
                  <div class="vm-card-breadcrumb">
                    <span class="breadcrumb-host">{{ vm.host_name }}</span>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                    <span class="breadcrumb-node">{{ vm.node }}</span>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                    <span class="breadcrumb-vmid">{{ vm.vmid }}</span>
                  </div>
                </div>
                <div class="vm-card-status">
                  <span :class="['badge', statusBadgeClass(vm.status)]">{{ vm.status }}</span>
                </div>
              </div>

              <div class="vm-card-stats">
                <div class="vm-stat">
                  <span class="stat-label">CPU</span>
                  <div class="stat-bar-wrap">
                    <div class="stat-bar">
                      <div class="stat-bar-fill" :style="{ width: cpuPct(vm) + '%', background: barColor(cpuPct(vm)) }"></div>
                    </div>
                    <span class="stat-val">{{ vm.cpu != null ? (vm.cpu * 100).toFixed(1) + '%' : '—' }}</span>
                  </div>
                </div>
                <div class="vm-stat">
                  <span class="stat-label">RAM</span>
                  <div class="stat-bar-wrap">
                    <div class="stat-bar">
                      <div class="stat-bar-fill" :style="{ width: memPct(vm) + '%', background: barColor(memPct(vm)) }"></div>
                    </div>
                    <span class="stat-val">{{ formatBytes(vm.maxmem) }}</span>
                  </div>
                </div>
              </div>

              <div class="vm-card-tags" v-if="parseTags(vm.tags).length">
                <span v-for="tag in parseTags(vm.tags)" :key="tag" class="tag-pill" :style="{ background: tagColor(tag) }">{{ tag }}</span>
              </div>

              <div class="vm-card-actions" @click.stop>
                <button v-if="vm.status !== 'running'" @click="vmAction(vm, 'start')" class="btn btn-primary btn-xs" :disabled="vm._busy">Start</button>
                <button v-if="vm.status === 'running'" @click="vmAction(vm, 'shutdown')" class="btn btn-warning btn-xs" :disabled="vm._busy">Shutdown</button>
                <button v-if="vm.status === 'running'" @click="vmAction(vm, 'stop')" class="btn btn-danger btn-xs" :disabled="vm._busy">Stop</button>
                <button @click="navigateTo(vm)" class="btn btn-outline btn-xs">Details</button>
              </div>
            </div>
          </div>

          <!-- Pagination (cards) -->
          <div v-if="total > pageSize" class="pagination-bar mt-1">
            <button @click="prevPage" class="btn btn-outline btn-sm" :disabled="skip === 0">Prev</button>
            <span class="page-info text-sm">Page {{ currentPage }} of {{ totalPages }}</span>
            <button @click="nextPage" class="btn btn-outline btn-sm" :disabled="skip + pageSize >= total">Next</button>
          </div>
        </template>

        <!-- TABLE VIEW -->
        <template v-else-if="results.length > 0 && viewMode === 'table'">
          <!-- Bulk action bar -->
          <div v-if="selectedKeys.size > 0" class="bulk-bar mt-1">
            <span class="bulk-count">{{ selectedKeys.size }} selected</span>
            <button @click="bulkStart" class="btn btn-primary btn-sm" :disabled="bulkRunning">Start</button>
            <button @click="bulkShutdown" class="btn btn-warning btn-sm" :disabled="bulkRunning">Shutdown</button>
            <button @click="bulkStop" class="btn btn-danger btn-sm" :disabled="bulkRunning">Stop</button>
            <button @click="showBulkTagModal = true" class="btn btn-secondary btn-sm" :disabled="bulkRunning">Tag</button>
            <button @click="selectedKeys.clear()" class="btn btn-outline btn-sm">Clear</button>
          </div>

          <div class="card mt-1">
            <div class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th class="cb-col">
                      <input type="checkbox" :checked="allSelected" :indeterminate.prop="someSelected && !allSelected" @change="toggleSelectAll" />
                    </th>
                    <th @click="toggleSort('vmid')" class="sortable-col">VMID <span class="sort-icon">{{ sortIcon('vmid') }}</span></th>
                    <th @click="toggleSort('name')" class="sortable-col">Name <span class="sort-icon">{{ sortIcon('name') }}</span></th>
                    <th @click="toggleSort('status')" class="sortable-col">Status <span class="sort-icon">{{ sortIcon('status') }}</span></th>
                    <th @click="toggleSort('node')" class="sortable-col">Node/Host <span class="sort-icon">{{ sortIcon('node') }}</span></th>
                    <th @click="toggleSort('cpu')" class="sortable-col">CPU% <span class="sort-icon">{{ sortIcon('cpu') }}</span></th>
                    <th @click="toggleSort('maxmem')" class="sortable-col">RAM <span class="sort-icon">{{ sortIcon('maxmem') }}</span></th>
                    <th>Tags</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="vm in sortedResults"
                    :key="vmKey(vm)"
                    :class="{ 'row-selected': selectedKeys.has(vmKey(vm)) }"
                  >
                    <td class="cb-col"><input type="checkbox" :checked="selectedKeys.has(vmKey(vm))" @change="toggleSelect(vm)" /></td>
                    <td><strong>{{ vm.vmid }}</strong></td>
                    <td>
                      <a class="vm-link" @click="navigateTo(vm)" style="cursor:pointer">
                        <span v-html="highlight(vm.name || '(no name)')"></span>
                      </a>
                    </td>
                    <td>
                      <span :class="['badge', statusBadgeClass(vm.status)]">{{ vm.status }}</span>
                    </td>
                    <td class="text-sm">
                      <span class="breadcrumb-host">{{ vm.host_name }}</span>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin:0 2px;opacity:0.4"><polyline points="9 18 15 12 9 6"/></svg>
                      <span>{{ vm.node }}</span>
                    </td>
                    <td class="text-sm">
                      <span v-if="vm.cpu != null">
                        <span :class="['cpu-badge', cpuClass(vm)]">{{ (vm.cpu * 100).toFixed(1) }}%</span>
                      </span>
                      <span v-else class="text-muted">—</span>
                    </td>
                    <td class="text-sm">
                      <span v-if="vm.maxmem">{{ formatBytes(vm.maxmem) }}</span>
                      <span v-else class="text-muted">—</span>
                    </td>
                    <td>
                      <div class="tags-row">
                        <span v-for="tag in parseTags(vm.tags)" :key="tag" class="tag-pill" :style="{ background: tagColor(tag) }">{{ tag }}</span>
                        <span v-if="!parseTags(vm.tags).length" class="text-muted">—</span>
                      </div>
                    </td>
                    <td>
                      <div class="action-btns">
                        <button v-if="vm.status !== 'running'" @click="vmAction(vm, 'start')" class="btn btn-primary btn-xs" :disabled="vm._busy">Start</button>
                        <button v-if="vm.status === 'running'" @click="vmAction(vm, 'shutdown')" class="btn btn-warning btn-xs" :disabled="vm._busy">Shutdown</button>
                        <button v-if="vm.status === 'running'" @click="vmAction(vm, 'stop')" class="btn btn-danger btn-xs" :disabled="vm._busy">Stop</button>
                        <button @click="navigateTo(vm)" class="btn btn-outline btn-xs">Details</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Pagination (table) -->
            <div v-if="total > pageSize" class="pagination-bar">
              <button @click="prevPage" class="btn btn-outline btn-sm" :disabled="skip === 0">Prev</button>
              <span class="page-info text-sm">Page {{ currentPage }} of {{ totalPages }}</span>
              <button @click="nextPage" class="btn btn-outline btn-sm" :disabled="skip + pageSize >= total">Next</button>
            </div>
          </div>
        </template>

        <!-- Initial state -->
        <div v-else-if="!searched && !searching" class="card empty-state mt-2">
          <div class="empty-icon-wrap">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          </div>
          <h4 class="empty-title">Search your infrastructure</h4>
          <p class="empty-subtitle">Enter a search term or use the filters on the left to find VMs across all hosts.</p>
          <div class="tips-inline">
            <code>tag:production</code>
            <code>node:pve01</code>
            <code>status:running</code>
          </div>
        </div>
      </div>
    </div>

    <!-- Save Search Modal -->
    <div v-if="showSaveModal" class="modal-overlay" @click.self="showSaveModal = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Save Search</h3>
          <button class="modal-close" @click="showSaveModal = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <label class="filter-label">Search Name</label>
          <input v-model="saveSearchName" class="form-input" placeholder="e.g. Production Running" @keyup.enter="saveSearch" autofocus />
          <p class="text-muted text-xs mt-1">Saves the current query and all active filters.</p>
        </div>
        <div class="modal-footer">
          <button @click="showSaveModal = false" class="btn btn-outline btn-sm">Cancel</button>
          <button @click="saveSearch" class="btn btn-primary btn-sm" :disabled="!saveSearchName.trim()">Save</button>
        </div>
      </div>
    </div>

    <!-- Bulk Tag Modal -->
    <div v-if="showBulkTagModal" class="modal-overlay" @click.self="showBulkTagModal = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Bulk Tag — {{ selectedKeys.size }} VM{{ selectedKeys.size !== 1 ? 's' : '' }}</h3>
          <button class="modal-close" @click="showBulkTagModal = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <label class="filter-label">Tags to Add (comma-separated)</label>
          <input v-model="bulkTagAdd" class="form-input" placeholder="e.g. production, web" />
          <label class="filter-label mt-1">Tags to Remove (comma-separated)</label>
          <input v-model="bulkTagRemove" class="form-input" placeholder="e.g. staging" />
          <div v-if="bulkTagResult.length > 0" class="bulk-tag-results mt-1">
            <div v-for="r in bulkTagResult" :key="r.vmid + r.node"
                 :class="['bulk-tag-row', r.success ? 'btag-ok' : 'btag-err']">
              <strong>{{ r.vmid }}</strong> ({{ r.node }})
              <span v-if="r.success">Updated</span>
              <span v-else class="text-danger">{{ r.error }}</span>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showBulkTagModal = false" class="btn btn-outline btn-sm">Close</button>
          <button @click="applyBulkTag" class="btn btn-primary btn-sm" :disabled="bulkTagRunning || (!bulkTagAdd.trim() && !bulkTagRemove.trim())">
            {{ bulkTagRunning ? 'Applying…' : 'Apply Tags' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, reactive, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

const PAGE_SIZE = 50
const DEBOUNCE_MS = 300
const LS_SAVED = 'depl0y_saved_searches'

const TAG_PALETTE = [
  '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
  '#ef4444', '#06b6d4', '#84cc16', '#f97316',
]

// Extract inline search operators from the query string.
// e.g. "tag:prod node:pve1 status:running web" →
//   { tags: ['prod'], node: 'pve1', status: 'running', rest: 'web' }
function parseOperators(raw) {
  const result = { tags: [], node: null, status: null, host: null, rest: '' }
  if (!raw) return result
  const parts = raw.trim().split(/\s+/)
  const leftovers = []
  for (const part of parts) {
    const m = part.match(/^(tag|node|status|host):(.+)$/i)
    if (m) {
      const op = m[1].toLowerCase()
      const val = m[2].toLowerCase()
      if (op === 'tag') result.tags.push(val)
      else if (op === 'node') result.node = val
      else if (op === 'status') result.status = val
      else if (op === 'host') result.host = val
    } else {
      leftovers.push(part)
    }
  }
  result.rest = leftovers.join(' ')
  return result
}

export default {
  name: 'VMSearch',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const toast = useToast()

    const searchInputRef = ref(null)
    const searchQuery = ref(route.query.q || '')
    const searching = ref(false)
    const searched = ref(false)
    const error = ref(null)
    const results = ref([])
    const total = ref(0)
    const skip = ref(0)
    const hosts = ref([])
    const allTags = ref([])
    const tagsLoading = ref(false)
    const viewMode = ref('cards')

    // Saved searches (localStorage)
    const savedSearches = ref(JSON.parse(localStorage.getItem(LS_SAVED) || '[]'))
    const showSaveModal = ref(false)
    const saveSearchName = ref('')

    // Bulk tag modal
    const showBulkTagModal = ref(false)
    const bulkTagAdd = ref('')
    const bulkTagRemove = ref('')
    const bulkTagRunning = ref(false)
    const bulkTagResult = ref([])

    const filters = reactive({
      status: '',
      host_id: '',
      node: '',
      tagsManual: '',
      os_type: '',
      min_cpu: null,
      max_cpu: null,
      min_ram_gb: null,
      max_ram_gb: null,
    })

    // Tag checkbox filter set
    const selectedFilterTags = reactive(new Set())

    const toggleFilterTag = (tag) => {
      if (selectedFilterTags.has(tag)) selectedFilterTags.delete(tag)
      else selectedFilterTags.add(tag)
      skip.value = 0
      debouncedSearch()
    }

    const sortKey = ref('name')
    const sortDir = ref('asc')
    const selectedKeys = reactive(new Set())
    const bulkRunning = ref(false)

    const pageSize = PAGE_SIZE

    const currentPage = computed(() => Math.floor(skip.value / PAGE_SIZE) + 1)
    const totalPages = computed(() => Math.ceil(total.value / PAGE_SIZE))

    const canSave = computed(() =>
      searchQuery.value.trim() ||
      filters.status ||
      filters.host_id ||
      filters.node ||
      filters.tagsManual ||
      selectedFilterTags.size > 0
    )

    const buildParams = () => {
      const ops = parseOperators(searchQuery.value)
      const p = { skip: skip.value, limit: PAGE_SIZE }

      // Text query (rest after operators)
      if (ops.rest.trim()) p.q = ops.rest.trim()

      // Merge operator-derived filters with sidebar filters
      const status = ops.status || filters.status
      if (status) p.status = status

      const node = ops.node || filters.node
      if (node) p.node = node

      if (filters.host_id) p.host_id = filters.host_id

      // Tags: merge checkbox set, manual input, and inline operator tags
      const tagSet = new Set([...selectedFilterTags])
      if (filters.tagsManual) {
        filters.tagsManual.split(',').map(t => t.trim()).filter(Boolean).forEach(t => tagSet.add(t))
      }
      ops.tags.forEach(t => tagSet.add(t))
      if (tagSet.size > 0) p.tags = [...tagSet].join(',')

      if (filters.os_type) p.os_type = filters.os_type
      if (filters.min_cpu != null) p.min_cpu = filters.min_cpu
      if (filters.max_cpu != null) p.max_cpu = filters.max_cpu
      if (filters.min_ram_gb != null) p.min_ram_gb = filters.min_ram_gb
      if (filters.max_ram_gb != null) p.max_ram_gb = filters.max_ram_gb
      return p
    }

    const runSearch = async () => {
      searching.value = true
      error.value = null
      searched.value = true
      selectedKeys.clear()
      try {
        const res = await api.pveVm.search(buildParams())
        const data = res.data
        results.value = (data.vms || []).map(vm => ({ ...vm, _busy: false }))
        total.value = data.total || 0
        router.replace({ query: { ...route.query, q: searchQuery.value || undefined } })
      } catch (e) {
        error.value = e.response?.data?.detail || e.message || 'Search failed'
        results.value = []
        total.value = 0
      } finally {
        searching.value = false
      }
    }

    // Debounce
    let debounceTimer = null
    const debouncedSearch = () => {
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => { skip.value = 0; runSearch() }, DEBOUNCE_MS)
    }
    const onSearchInput = () => debouncedSearch()

    const clearSearch = () => {
      searchQuery.value = ''
      skip.value = 0
      runSearch()
    }

    const prevPage = () => {
      if (skip.value > 0) {
        skip.value = Math.max(0, skip.value - PAGE_SIZE)
        runSearch()
      }
    }

    const nextPage = () => {
      if (skip.value + PAGE_SIZE < total.value) {
        skip.value += PAGE_SIZE
        runSearch()
      }
    }

    // Sort
    const toggleSort = (key) => {
      if (sortKey.value === key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
      else { sortKey.value = key; sortDir.value = 'asc' }
    }
    const sortIcon = (key) => {
      if (sortKey.value !== key) return '↕'
      return sortDir.value === 'asc' ? '↑' : '↓'
    }

    const sortedResults = computed(() => {
      const list = [...results.value]
      list.sort((a, b) => {
        let av = a[sortKey.value] ?? ''
        let bv = b[sortKey.value] ?? ''
        if (typeof av === 'string') { av = av.toLowerCase(); bv = bv.toLowerCase() }
        if (av < bv) return sortDir.value === 'asc' ? -1 : 1
        if (av > bv) return sortDir.value === 'asc' ? 1 : -1
        return 0
      })
      return list
    })

    // Selection
    const vmKey = (vm) => `${vm.host_id}:${vm.node}:${vm.vmid}`

    const toggleSelect = (vm) => {
      const k = vmKey(vm)
      if (selectedKeys.has(k)) selectedKeys.delete(k)
      else selectedKeys.add(k)
    }

    const allSelected = computed(() =>
      results.value.length > 0 && results.value.every(vm => selectedKeys.has(vmKey(vm)))
    )
    const someSelected = computed(() =>
      results.value.some(vm => selectedKeys.has(vmKey(vm)))
    )
    const toggleSelectAll = () => {
      if (allSelected.value) results.value.forEach(vm => selectedKeys.delete(vmKey(vm)))
      else results.value.forEach(vm => selectedKeys.add(vmKey(vm)))
    }

    const selectedVms = computed(() => results.value.filter(vm => selectedKeys.has(vmKey(vm))))

    // Navigation
    const navigateTo = (vm) => {
      router.push(`/proxmox/${vm.host_id}/nodes/${vm.node}/vms/${vm.vmid}`)
    }

    // Per-VM actions
    const vmAction = async (vm, action) => {
      vm._busy = true
      try {
        if (action === 'start') await api.pveVm.start(vm.host_id, vm.node, vm.vmid)
        else if (action === 'shutdown') await api.pveVm.shutdown(vm.host_id, vm.node, vm.vmid)
        else if (action === 'stop') await api.pveVm.stop(vm.host_id, vm.node, vm.vmid)
        toast.success(`VM ${vm.vmid}: ${action} initiated`)
        setTimeout(runSearch, 2000)
      } catch {
        toast.error(`Failed to ${action} VM ${vm.vmid}`)
      } finally {
        vm._busy = false
      }
    }

    // Bulk power
    const bulkStart = async () => {
      bulkRunning.value = true
      for (const vm of selectedVms.value) {
        try { await api.pveVm.start(vm.host_id, vm.node, vm.vmid) } catch {}
      }
      bulkRunning.value = false
      toast.success('Start sent to selected VMs')
      setTimeout(runSearch, 2500)
    }
    const bulkShutdown = async () => {
      bulkRunning.value = true
      for (const vm of selectedVms.value) {
        try { await api.pveVm.shutdown(vm.host_id, vm.node, vm.vmid) } catch {}
      }
      bulkRunning.value = false
      toast.success('Shutdown sent to selected VMs')
      setTimeout(runSearch, 2500)
    }
    const bulkStop = async () => {
      if (!confirm(`Force-stop ${selectedVms.value.length} VMs?`)) return
      bulkRunning.value = true
      for (const vm of selectedVms.value) {
        try { await api.pveVm.stop(vm.host_id, vm.node, vm.vmid) } catch {}
      }
      bulkRunning.value = false
      toast.success('Stop sent to selected VMs')
      setTimeout(runSearch, 2500)
    }

    // Bulk tag
    const applyBulkTag = async () => {
      bulkTagRunning.value = true
      bulkTagResult.value = []
      const vmids = selectedVms.value.map(vm => ({
        host_id: vm.host_id,
        node: vm.node,
        vmid: vm.vmid,
      }))
      const tagsAdd = bulkTagAdd.value.split(',').map(t => t.trim()).filter(Boolean)
      const tagsRemove = bulkTagRemove.value.split(',').map(t => t.trim()).filter(Boolean)
      try {
        const res = await api.vmTags.bulkTag({ vmids, tags_add: tagsAdd, tags_remove: tagsRemove })
        bulkTagResult.value = res.data?.results || []
        const ok = bulkTagResult.value.filter(r => r.success).length
        const fail = bulkTagResult.value.filter(r => !r.success).length
        if (fail === 0) toast.success(`Tags updated on ${ok} VM${ok !== 1 ? 's' : ''}`)
        else toast.warning(`${ok} succeeded, ${fail} failed`)
        // Reload tags list and results
        loadTags()
        setTimeout(runSearch, 1000)
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Bulk tag failed')
      } finally {
        bulkTagRunning.value = false
      }
    }

    const goToBulkOps = () => {
      const vms = selectedVms.value.map(vm => ({
        hostId: vm.host_id, node: vm.node, vmid: vm.vmid, name: vm.name, status: vm.status
      }))
      sessionStorage.setItem('bulkOpsVMs', JSON.stringify(vms))
      router.push('/bulk-ops')
    }

    // Saved searches
    const saveSearch = () => {
      if (!saveSearchName.value.trim()) return
      const entry = {
        name: saveSearchName.value.trim(),
        query: searchQuery.value,
        filters: { ...filters },
        filterTags: [...selectedFilterTags],
      }
      const list = JSON.parse(localStorage.getItem(LS_SAVED) || '[]')
      const idx = list.findIndex(s => s.name === entry.name)
      if (idx >= 0) list[idx] = entry
      else list.push(entry)
      localStorage.setItem(LS_SAVED, JSON.stringify(list))
      savedSearches.value = list
      toast.success(`Saved "${entry.name}"`)
      showSaveModal.value = false
      saveSearchName.value = ''
    }

    const loadSavedSearch = (ss) => {
      searchQuery.value = ss.query || ''
      Object.assign(filters, ss.filters || {})
      selectedFilterTags.clear()
      ;(ss.filterTags || []).forEach(t => selectedFilterTags.add(t))
      skip.value = 0
      runSearch()
    }

    const deleteSavedSearch = (name) => {
      const list = JSON.parse(localStorage.getItem(LS_SAVED) || '[]').filter(s => s.name !== name)
      localStorage.setItem(LS_SAVED, JSON.stringify(list))
      savedSearches.value = list
    }

    // Export CSV
    const exportCsv = () => {
      const headers = ['VMID', 'Name', 'Status', 'Node', 'Host', 'CPU%', 'Memory (GB)', 'Tags']
      const rows = results.value.map(vm => [
        vm.vmid,
        `"${(vm.name || '').replace(/"/g, '""')}"`,
        vm.status,
        vm.node,
        vm.host_name,
        vm.cpu != null ? (vm.cpu * 100).toFixed(1) : '',
        vm.maxmem ? (vm.maxmem / (1024 ** 3)).toFixed(2) : '',
        `"${(vm.tags || '').replace(/"/g, '""')}"`,
      ].join(','))
      const csv = [headers.join(','), ...rows].join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `vm-search-${Date.now()}.csv`
      a.click()
      URL.revokeObjectURL(url)
    }

    // Helpers
    const formatBytes = (bytes) => {
      if (!bytes) return '—'
      const gb = bytes / (1024 ** 3)
      return gb >= 1 ? gb.toFixed(1) + ' GB' : (bytes / (1024 ** 2)).toFixed(0) + ' MB'
    }

    const parseTags = (t) => {
      if (!t) return []
      return t.split(';').map(x => x.trim()).filter(Boolean)
    }

    const tagColor = (tag) => {
      let h = 0
      for (let i = 0; i < tag.length; i++) h = tag.charCodeAt(i) + ((h << 5) - h)
      return TAG_PALETTE[Math.abs(h) % TAG_PALETTE.length]
    }

    const statusBadgeClass = (s) => {
      if (s === 'running') return 'badge-success'
      if (s === 'stopped') return 'badge-danger'
      if (s === 'paused') return 'badge-warning'
      return 'badge-secondary'
    }

    const cpuPct = (vm) => vm.cpu != null ? Math.min(100, vm.cpu * 100) : 0
    const memPct = (vm) => {
      if (!vm.mem || !vm.maxmem) return 0
      return Math.min(100, (vm.mem / vm.maxmem) * 100)
    }
    const barColor = (pct) => {
      if (pct >= 90) return '#ef4444'
      if (pct >= 70) return '#f59e0b'
      return '#10b981'
    }
    const cpuClass = (vm) => {
      const p = cpuPct(vm)
      if (p >= 90) return 'cpu-high'
      if (p >= 70) return 'cpu-med'
      return 'cpu-low'
    }

    const isLinux = (vm) => {
      const name = (vm.name || '').toLowerCase()
      const tags = (vm.tags || '').toLowerCase()
      return name.includes('ubuntu') || name.includes('debian') || name.includes('centos') ||
             name.includes('fedora') || name.includes('arch') || name.includes('linux') ||
             tags.includes('linux')
    }
    const isWindows = (vm) => {
      const name = (vm.name || '').toLowerCase()
      const tags = (vm.tags || '').toLowerCase()
      return name.includes('win') || name.includes('windows') || tags.includes('windows')
    }
    const osIconClass = (vm) => {
      if (isLinux(vm)) return 'icon-linux'
      if (isWindows(vm)) return 'icon-windows'
      return 'icon-generic'
    }

    const highlight = (text) => {
      const ops = parseOperators(searchQuery.value)
      const q = ops.rest.trim()
      if (!q || q.length < 2) return text
      const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      return text.replace(new RegExp(`(${escaped})`, 'gi'), '<mark>$1</mark>')
    }

    const clearFilters = () => {
      filters.status = ''
      filters.host_id = ''
      filters.node = ''
      filters.tagsManual = ''
      filters.os_type = ''
      filters.min_cpu = null
      filters.max_cpu = null
      filters.min_ram_gb = null
      filters.max_ram_gb = null
      selectedFilterTags.clear()
      skip.value = 0
      runSearch()
    }

    // Load data
    const loadHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = res.data || []
      } catch {}
    }

    const loadTags = async () => {
      tagsLoading.value = true
      try {
        const res = await api.vmTags.listAllCrossHost()
        allTags.value = res.data || []
      } catch {} finally {
        tagsLoading.value = false
      }
    }

    // Keyboard shortcut: Ctrl+K / Cmd+K focus search
    const onKeydown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        nextTick(() => searchInputRef.value?.focus())
      }
    }

    onMounted(async () => {
      document.addEventListener('keydown', onKeydown)
      await Promise.all([loadHosts(), loadTags()])
      if (searchQuery.value || Object.values(filters).some(v => v)) {
        runSearch()
      }
    })

    onUnmounted(() => {
      document.removeEventListener('keydown', onKeydown)
      clearTimeout(debounceTimer)
    })

    // Watch sidebar filters
    let filterTimer = null
    watch([
      () => filters.status, () => filters.host_id, () => filters.node,
      () => filters.tagsManual, () => filters.os_type,
      () => filters.min_cpu, () => filters.max_cpu,
      () => filters.min_ram_gb, () => filters.max_ram_gb,
    ], () => {
      clearTimeout(filterTimer)
      filterTimer = setTimeout(() => { skip.value = 0; runSearch() }, 400)
    })

    return {
      searchInputRef,
      searchQuery, searching, searched, error, results, total, skip, hosts, allTags, tagsLoading,
      filters, selectedFilterTags, sortKey, sortDir, selectedKeys, bulkRunning,
      viewMode, pageSize, currentPage, totalPages, canSave,
      sortedResults, allSelected, someSelected,
      savedSearches, showSaveModal, saveSearchName,
      showBulkTagModal, bulkTagAdd, bulkTagRemove, bulkTagRunning, bulkTagResult,
      toggleFilterTag,
      runSearch, onSearchInput, clearSearch, prevPage, nextPage, clearFilters,
      toggleSort, sortIcon, vmKey, toggleSelect, toggleSelectAll,
      navigateTo, vmAction, bulkStart, bulkShutdown, bulkStop, goToBulkOps,
      applyBulkTag,
      saveSearch, loadSavedSearch, deleteSavedSearch,
      exportCsv, formatBytes, parseTags, tagColor, statusBadgeClass, highlight,
      cpuPct, memPct, barColor, cpuClass, isLinux, isWindows, osIconClass,
    }
  }
}
</script>

<style scoped>
.vm-search-page { padding: 0; }

/* ── Page header ─────────────────────────────────────────────────── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.75rem;
}
.page-header h2 {
  margin: 0 0 0.2rem;
  font-size: 1.65rem;
  font-weight: 600;
  color: var(--text-primary);
}
.header-actions { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }

/* ── Saved searches bar ──────────────────────────────────────────── */
.saved-searches-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}
.saved-label { font-size: 0.75rem; font-weight: 600; color: var(--text-muted); white-space: nowrap; }
.saved-chips { display: flex; gap: 0.35rem; flex-wrap: wrap; }
.saved-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary, var(--background));
  cursor: pointer;
  color: var(--text-primary);
  transition: background 0.15s;
}
.saved-chip:hover { background: var(--primary-color, #3b82f6); color: #fff; border-color: var(--primary-color); }
.saved-chip-del {
  display: flex;
  align-items: center;
  opacity: 0.6;
  border-radius: 50%;
  padding: 1px;
}
.saved-chip-del:hover { opacity: 1; }

/* ── Layout ──────────────────────────────────────────────────────── */
.search-layout {
  display: grid;
  grid-template-columns: 230px 1fr;
  gap: 1rem;
  align-items: start;
}
@media (max-width: 768px) {
  .search-layout { grid-template-columns: 1fr; }
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
.filter-sidebar {
  padding: 1rem;
  position: sticky;
  top: 1rem;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
}
.sidebar-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin-bottom: 0.9rem;
}
.filter-section { margin-bottom: 1rem; }
.filter-label {
  display: block;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.3rem;
}
.form-input {
  width: 100%;
  padding: 0.3rem 0.45rem;
  font-size: 0.83rem;
  border: 1px solid var(--border-color);
  border-radius: 0.35rem;
  background: var(--bg-primary, var(--background));
  color: var(--text-primary);
  box-sizing: border-box;
}
.filter-select { cursor: pointer; }
.radio-group { display: flex; flex-direction: column; gap: 0.25rem; }
.radio-opt {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.83rem;
  cursor: pointer;
  color: var(--text-primary);
}
.status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
.dot-running { background: #10b981; }
.dot-stopped { background: #ef4444; }
.dot-paused  { background: #f59e0b; }

.range-row { display: flex; align-items: center; gap: 0.3rem; }
.range-input { flex: 1; }
.range-sep { color: var(--text-muted); font-size: 0.8rem; flex-shrink: 0; }

/* tag checkboxes */
.tag-checkbox-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  max-height: 160px;
  overflow-y: auto;
  margin-bottom: 0.3rem;
}
.tag-check-opt {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  cursor: pointer;
  font-size: 0.8rem;
}
.tag-count { margin-left: auto; color: var(--text-muted); font-size: 0.72rem; }
.tag-pill-sm {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.08rem 0.35rem;
  border-radius: 9999px;
  color: #fff;
  white-space: nowrap;
}
.loading-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--primary-color, #3b82f6);
  animation: pulse 1s infinite;
  margin-left: 4px;
  vertical-align: middle;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* ── Search bar ──────────────────────────────────────────────────── */
.search-bar { padding: 0.75rem 1rem; }
.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.3rem;
}
.search-icon { color: var(--text-muted); flex-shrink: 0; }
.search-input {
  flex: 1;
  border: 1px solid var(--border-color);
  border-radius: 0.4rem;
  padding: 0.42rem 0.75rem;
  font-size: 0.9rem;
  background: var(--bg-primary, var(--background));
  color: var(--text-primary);
  outline: none;
  font-family: inherit;
}
.search-input:focus {
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59,130,246,0.14);
}
.clear-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  padding: 0;
}
.search-meta { font-size: 0.8rem; }

/* ── Search tips ─────────────────────────────────────────────────── */
.search-tips { padding: 0; overflow: hidden; }
.tips-summary {
  list-style: none;
  padding: 0.55rem 1rem;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.4rem;
  user-select: none;
}
.tips-summary::-webkit-details-marker { display: none; }
.tips-body { padding: 0 1rem 0.75rem; }
.tips-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.3rem 1rem;
  margin-bottom: 0.5rem;
}
.tip-item { font-size: 0.8rem; color: var(--text-secondary); }
.tip-item code {
  font-family: monospace;
  font-size: 0.78rem;
  background: var(--bg-secondary, rgba(0,0,0,0.05));
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
}
.tips-note { font-size: 0.78rem; color: var(--text-muted); margin: 0.25rem 0 0; }
.tips-note kbd {
  font-family: monospace;
  font-size: 0.74rem;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  padding: 0.05rem 0.25rem;
  background: var(--bg-secondary, rgba(0,0,0,0.04));
}

/* ── View toggle ─────────────────────────────────────────────────── */
.view-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.view-toggle {
  display: flex;
  gap: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
}
.toggle-btn {
  background: none;
  border: none;
  padding: 0.3rem 0.6rem;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  transition: background 0.15s;
}
.toggle-btn:first-child { border-right: 1px solid var(--border-color); }
.toggle-btn.active { background: var(--primary-color, #3b82f6); color: #fff; }
.toggle-btn:not(.active):hover { background: var(--bg-secondary, rgba(0,0,0,0.05)); }

/* ── VM Cards grid ───────────────────────────────────────────────── */
.vm-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.85rem;
}

.vm-card {
  background: var(--bg-card, var(--card-background, #fff));
  border: 1.5px solid var(--border-color);
  border-radius: 0.6rem;
  padding: 1rem;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}
.vm-card:hover { border-color: var(--primary-color, #3b82f6); }
.vm-card-selected {
  border-color: var(--primary-color, #3b82f6);
  background: rgba(59,130,246,0.05);
  box-shadow: 0 0 0 2px rgba(59,130,246,0.18);
}

.vm-card-header {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
}
.vm-card-check { flex-shrink: 0; padding-top: 2px; }
.vm-card-icon { flex-shrink: 0; }
.vm-os-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px; height: 34px;
  border-radius: 8px;
}
.icon-linux { background: rgba(234,179,8,0.15); color: #b45309; }
.icon-windows { background: rgba(59,130,246,0.15); color: #1d4ed8; }
.icon-generic { background: rgba(107,114,128,0.12); color: #6b7280; }

.vm-card-title { flex: 1; min-width: 0; }
.vm-card-name {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--primary-color, #3b82f6);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.vm-card-name:hover { text-decoration: underline; }
.vm-card-breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.72rem;
  color: var(--text-muted);
  flex-wrap: nowrap;
  white-space: nowrap;
  overflow: hidden;
}
.breadcrumb-host { font-weight: 500; }

/* Stats */
.vm-card-stats { display: flex; flex-direction: column; gap: 0.35rem; }
.vm-stat { display: flex; align-items: center; gap: 0.5rem; }
.stat-label { font-size: 0.7rem; font-weight: 600; color: var(--text-muted); width: 28px; flex-shrink: 0; }
.stat-bar-wrap { display: flex; align-items: center; gap: 0.4rem; flex: 1; }
.stat-bar { flex: 1; height: 5px; border-radius: 9999px; background: var(--border-color); overflow: hidden; }
.stat-bar-fill { height: 100%; border-radius: 9999px; transition: width 0.3s; }
.stat-val { font-size: 0.72rem; color: var(--text-muted); width: 42px; text-align: right; flex-shrink: 0; }

/* Card tags */
.vm-card-tags { display: flex; flex-wrap: wrap; gap: 0.25rem; }

/* Card actions */
.vm-card-actions { display: flex; gap: 0.3rem; flex-wrap: wrap; padding-top: 0.25rem; border-top: 1px solid var(--border-color); }

/* ── Table view ──────────────────────────────────────────────────── */
.table-container { overflow-x: auto; }
.cb-col { width: 2rem; text-align: center; }
.row-selected td { background: rgba(59,130,246,0.06); }
.sortable-col { cursor: pointer; user-select: none; white-space: nowrap; }
.sortable-col:hover { color: var(--primary-color); }
.sort-icon { font-size: 0.72rem; color: var(--text-muted); margin-left: 0.2rem; }
.vm-link { color: var(--primary-color); font-weight: 500; }
.vm-link:hover { text-decoration: underline; }
.tags-row { display: flex; flex-wrap: wrap; gap: 0.25rem; }
.tag-pill {
  display: inline-block;
  font-size: 0.63rem;
  font-weight: 600;
  padding: 0.08rem 0.38rem;
  border-radius: 9999px;
  color: #fff;
  white-space: nowrap;
}
.action-btns { display: flex; gap: 0.3rem; flex-wrap: nowrap; }
.btn-xs { padding: 0.14rem 0.42rem; font-size: 0.73rem; line-height: 1.4; }

/* CPU badge */
.cpu-badge { padding: 0.05rem 0.3rem; border-radius: 3px; font-weight: 600; font-size: 0.8rem; }
.cpu-low  { color: #059669; background: rgba(5,150,105,0.1); }
.cpu-med  { color: #d97706; background: rgba(217,119,6,0.1); }
.cpu-high { color: #dc2626; background: rgba(220,38,38,0.1); }

/* ── Bulk bar ────────────────────────────────────────────────────── */
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  background: rgba(59,130,246,0.07);
  border: 1px solid rgba(59,130,246,0.2);
}
.bulk-count { font-size: 0.83rem; font-weight: 600; color: var(--primary-color); }

/* ── Pagination ──────────────────────────────────────────────────── */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 0.65rem 1rem;
  border-top: 1px solid var(--border-color);
}
.page-info { color: var(--text-muted); }

/* ── Empty state ─────────────────────────────────────────────────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.65rem;
  padding: 3rem 1.5rem;
  text-align: center;
}
.empty-icon-wrap {
  width: 72px; height: 72px;
  border-radius: 50%;
  background: var(--background);
  border: 2px dashed var(--border-color);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-title { font-size: 1rem; font-weight: 600; color: var(--text-primary); margin: 0; }
.empty-subtitle { font-size: 0.875rem; color: var(--text-secondary); margin: 0; max-width: 360px; }
.tips-inline { display: flex; gap: 0.5rem; flex-wrap: wrap; justify-content: center; }
.tips-inline code {
  font-size: 0.78rem;
  background: var(--bg-secondary, rgba(0,0,0,0.06));
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  color: var(--text-secondary);
  font-family: monospace;
}

/* ── Modal ───────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}
.modal-box {
  background: var(--bg-card, #fff);
  border-radius: 0.6rem;
  min-width: 340px;
  max-width: 480px;
  width: 100%;
  box-shadow: 0 20px 60px rgba(0,0,0,0.25);
  overflow: hidden;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.9rem 1.1rem;
  border-bottom: 1px solid var(--border-color);
}
.modal-header h3 { margin: 0; font-size: 1rem; font-weight: 600; }
.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  padding: 2px;
}
.modal-body { padding: 1rem 1.1rem; }
.modal-footer {
  padding: 0.75rem 1.1rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

/* Bulk tag results */
.bulk-tag-results { max-height: 160px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 0.35rem; }
.bulk-tag-row { padding: 0.3rem 0.6rem; font-size: 0.8rem; display: flex; gap: 0.5rem; align-items: center; }
.bulk-tag-row + .bulk-tag-row { border-top: 1px solid var(--border-color); }
.btag-ok { background: rgba(16,185,129,0.06); }
.btag-err { background: rgba(239,68,68,0.06); }

/* ── Highlight ───────────────────────────────────────────────────── */
:deep(mark) {
  background: rgba(251,191,36,0.38);
  color: inherit;
  border-radius: 2px;
  padding: 0 1px;
}

/* ── Utilities ───────────────────────────────────────────────────── */
.mt-1 { margin-top: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.text-muted { color: var(--text-muted); }
.text-danger { color: #ef4444; }
.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.875rem; }
</style>
