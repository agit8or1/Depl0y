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

      <!-- Search + Filter Bar -->
      <div class="filter-bar">
        <div class="filter-info" style="flex-wrap: wrap; gap: 0.5rem;">
          <input
            v-model="managedSearch"
            type="text"
            placeholder="Search by name, VMID, node…"
            class="form-control"
            style="width: 220px;"
          />
          <select v-model="managedStatusFilter" class="form-control" style="width: 140px;">
            <option value="">All statuses</option>
            <option value="running">Running</option>
            <option value="stopped">Stopped</option>
            <option value="paused">Paused</option>
          </select>
          <span class="filter-count">{{ filteredVMs.length }} VM{{ filteredVMs.length !== 1 ? 's' : '' }}</span>
        </div>
        <button v-if="managedSearch || managedStatusFilter || statusFilter" @click="clearFilter" class="btn btn-sm btn-secondary">
          Clear
        </button>
      </div>

      <div v-if="loading" class="loading-spinner"></div>

      <div v-else-if="filteredVMs.length === 0 && vms.length === 0" class="empty-state">
        <div class="empty-icon-wrap">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
        </div>
        <h4 class="empty-title">No virtual machines found</h4>
        <p class="empty-subtitle">Deploy your first VM to get started with Depl0y.</p>
        <router-link to="/vms/create" class="btn btn-primary">+ Create VM</router-link>
      </div>

      <div v-else-if="filteredVMs.length === 0" class="empty-state">
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
              <td>{{ vm.name }}</td>
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
              <td>
                <div class="flex gap-1">
                  <button
                    v-if="vm.status === 'running'"
                    @click="stopVM(vm.vmid, vm.node)"
                    class="btn btn-warning btn-sm"
                  >
                    Stop
                  </button>
                  <button
                    v-if="vm.status === 'running'"
                    @click="restartVM(vm.vmid, vm.node)"
                    class="btn btn-info btn-sm"
                  >
                    Restart
                  </button>
                  <button
                    v-if="vm.status === 'running'"
                    @click="powerOffVM(vm.vmid, vm.node)"
                    class="btn btn-danger btn-sm"
                  >
                    Power Off
                  </button>
                  <button
                    v-if="vm.status === 'stopped'"
                    @click="startVM(vm.vmid, vm.node)"
                    class="btn btn-primary btn-sm"
                  >
                    Start
                  </button>
                  <button
                    @click="showDeleteModal(vm)"
                    class="btn btn-danger btn-sm"
                    title="Delete VM"
                  >
                    Delete
                  </button>
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
        <span class="refresh-countdown" v-if="!allLoading">Auto-refresh in {{ allCountdown }}s</span>
        <button @click="fetchAllProxmoxVMs(true)" class="btn btn-secondary" :disabled="allLoading">
          {{ allLoading ? 'Refreshing…' : 'Refresh' }}
        </button>
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
          <span class="filter-count">{{ filteredAllVMs.length }} VM{{ filteredAllVMs.length !== 1 ? 's' : '' }}</span>
        </div>
        <button v-if="allSearch || allStatusFilter" @click="allSearch = ''; allStatusFilter = ''" class="btn btn-sm btn-secondary">
          Clear
        </button>
      </div>

      <div v-if="allLoading" class="loading-spinner"></div>

      <div v-else-if="allError" class="text-center text-muted" style="padding: 2rem;">
        <p class="text-danger">{{ allError }}</p>
        <button @click="fetchAllProxmoxVMs" class="btn btn-secondary btn-sm mt-1">Retry</button>
      </div>

      <div v-else-if="allVMs.length === 0" class="text-center text-muted" style="padding: 2rem;">
        <p>No Proxmox VMs found.</p>
        <p class="text-sm">Make sure at least one Proxmox host is configured and reachable.</p>
      </div>

      <div v-else-if="filteredAllVMs.length === 0" class="text-center text-muted" style="padding: 2rem;">
        <p>No VMs match your search.</p>
        <button @click="allSearch = ''; allStatusFilter = ''" class="btn btn-sm btn-secondary mt-1">Clear Filters</button>
      </div>

      <div v-else class="table-container" style="position:relative;">
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
              <th @click="allSortBy('hostName')" class="sortable">
                Host
                <span class="sort-indicator" v-if="allSortField === 'hostName'">{{ allSortDirection === 'asc' ? '▲' : '▼' }}</span>
              </th>
              <th>CPU / Memory</th>
              <th v-if="anyVmHasTags">Tags</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="vm in filteredAllVMs" :key="`${vm.hostId}-${vm.node}-${vm.vmid}`"
              :class="{ 'row-selected': selectedVmKeys.has(vmKey(vm)) }">
              <td class="cb-col">
                <input
                  type="checkbox"
                  :checked="selectedVmKeys.has(vmKey(vm))"
                  @change="toggleSelectVm(vm)"
                />
              </td>
              <td><strong>{{ vm.vmid }}</strong></td>
              <td>
                <a
                  class="vm-name-link"
                  @click="navigateToVM(vm)"
                  style="cursor: pointer;"
                >
                  {{ vm.name || '(no name)' }}
                </a>
              </td>
              <td>
                <span :class="['badge', getStatusBadgeClass(vm.status)]">
                  {{ vm.status }}
                </span>
              </td>
              <td>
                <span class="badge badge-info">{{ vm.node }}</span>
              </td>
              <td class="text-sm">{{ vm.hostName }}</td>
              <td class="text-sm">
                {{ vm.cpus || '?' }} CPU / {{ formatBytes(vm.maxmem) }} RAM
              </td>
              <td v-if="anyVmHasTags">
                <div class="vm-tags">
                  <span
                    v-for="tag in parseTags(vm.tags)"
                    :key="tag"
                    class="vm-tag-pill"
                    :style="{ backgroundColor: tagColor(tag) }"
                  >{{ tag }}</span>
                  <span v-if="!parseTags(vm.tags).length" class="text-muted text-sm">—</span>
                </div>
              </td>
              <td>
                <div class="flex gap-1">
                  <button
                    v-if="vm.status === 'running'"
                    @click="allShutdownVM(vm)"
                    class="btn btn-warning btn-sm"
                    :disabled="vm._busy"
                  >
                    Shutdown
                  </button>
                  <button
                    v-if="vm.status === 'running'"
                    @click="allStopVM(vm)"
                    class="btn btn-danger btn-sm"
                    :disabled="vm._busy"
                  >
                    Stop
                  </button>
                  <button
                    v-if="vm.status !== 'running'"
                    @click="allStartVM(vm)"
                    class="btn btn-primary btn-sm"
                    :disabled="vm._busy"
                  >
                    Start
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Bulk Action Bar -->
        <div v-if="selectedVmKeys.size > 0" class="bulk-action-bar">
          <span class="bulk-count">{{ selectedVmKeys.size }} VM{{ selectedVmKeys.size !== 1 ? 's' : '' }} selected</span>
          <button
            class="btn btn-primary btn-sm"
            @click="bulkAction('start')"
            :disabled="bulkRunning"
          >
            Start Selected
          </button>
          <button
            class="btn btn-warning btn-sm"
            @click="bulkAction('shutdown')"
            :disabled="bulkRunning"
          >
            Shutdown Selected
          </button>
          <button
            class="btn btn-danger btn-sm"
            @click="bulkAction('stop')"
            :disabled="bulkRunning"
          >
            Stop Selected
          </button>
          <button
            class="btn btn-outline btn-sm"
            @click="openBulkSnapshotModal"
            :disabled="bulkRunning"
            title="Create snapshot on all selected VMs"
          >
            Snapshot All
          </button>
          <button
            class="btn btn-outline btn-sm"
            @click="openBulkTagModal"
            :disabled="bulkRunning"
            title="Apply tag to all selected VMs"
          >
            Tag All
          </button>
          <button
            class="btn btn-danger btn-sm"
            @click="openBulkDeleteModal"
            :disabled="bulkRunning"
            title="Delete all selected VMs"
          >
            Delete All
          </button>
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
          <!-- Progress Table -->
          <div v-if="bulkOpResults.length > 0" class="bulk-results-table">
            <div class="bulk-results-header">
              <span>VMID</span>
              <span>Name</span>
              <span>Node</span>
              <span>Result</span>
            </div>
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
          <button v-if="!bulkOpDone" @click="runBulkSnapshot" class="btn btn-primary"
            :disabled="bulkRunning || !bulkSnapName.trim()">
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
          <!-- Progress Table -->
          <div v-if="bulkOpResults.length > 0" class="bulk-results-table">
            <div class="bulk-results-header">
              <span>VMID</span>
              <span>Name</span>
              <span>Node</span>
              <span>Result</span>
            </div>
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
          <button v-if="!bulkOpDone" @click="runBulkTag" class="btn btn-primary"
            :disabled="bulkRunning || !bulkTagValue.trim()">
            {{ bulkRunning ? 'Running…' : 'Apply Tag' }}
          </button>
          <button v-if="bulkOpDone" @click="closeBulkModal" class="btn btn-secondary">Close</button>
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
          <!-- Progress Table -->
          <div v-if="bulkOpResults.length > 0" class="bulk-results-table">
            <div class="bulk-results-header">
              <span>VMID</span>
              <span>Name</span>
              <span>Node</span>
              <span>Result</span>
            </div>
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

export default {
  name: 'VirtualMachines',
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
    const sortField = ref('vmid')
    const sortDirection = ref('asc')
    const statusFilter = ref(route.query.status || null)
    const managedSearch = ref('')
    const managedStatusFilter = ref('')
    const showDeleteConfirmModal = ref(false)
    const vmToDelete = ref(null)
    const deleteConfirmInput = ref('')

    const fetchVMs = async () => {
      loading.value = true
      try {
        const response = await api.vms.list()
        vms.value = response.data
        sortVMs()
      } catch (error) {
        console.error('Failed to fetch VMs:', error)
      } finally {
        loading.value = false
      }
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

        if (typeof aVal === 'string') {
          aVal = aVal.toLowerCase()
          bVal = bVal.toLowerCase()
        }

        if (sortDirection.value === 'asc') {
          return aVal > bVal ? 1 : aVal < bVal ? -1 : 0
        } else {
          return aVal < bVal ? 1 : aVal > bVal ? -1 : 0
        }
      })
    }

    const startVM = async (vmid, node) => {
      try {
        await api.vms.startByVmid(vmid, node)
        toast.success(`VM ${vmid} started successfully`)
        setTimeout(fetchVMs, 1000)
      } catch (error) {
        console.error('Failed to start VM:', error)
        toast.error('Failed to start VM')
      }
    }

    const stopVM = async (vmid, node) => {
      try {
        await api.vms.stopByVmid(vmid, node)
        toast.success(`VM ${vmid} stopped successfully`)
        setTimeout(fetchVMs, 1000)
      } catch (error) {
        console.error('Failed to stop VM:', error)
        toast.error('Failed to stop VM')
      }
    }

    const powerOffVM = async (vmid, node) => {
      if (!confirm(`Are you sure you want to power off VM ${vmid}? This is equivalent to pulling the power plug.`)) {
        return
      }

      try {
        await api.vms.powerOffByVmid(vmid, node)
        toast.success(`VM ${vmid} powered off successfully`)
        setTimeout(fetchVMs, 1000)
      } catch (error) {
        console.error('Failed to power off VM:', error)
        toast.error('Failed to power off VM')
      }
    }

    const restartVM = async (vmid, node) => {
      try {
        await api.vms.restartByVmid(vmid, node)
        toast.success(`VM ${vmid} restarting...`)
        setTimeout(fetchVMs, 1000)
      } catch (error) {
        console.error('Failed to restart VM:', error)
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
        console.error('Failed to delete VM:', error)
        toast.error(`Failed to delete VM: ${error.response?.data?.detail || error.message}`)
      }
    }

    const filteredVMs = computed(() => {
      let list = vms.value

      // Route query status filter (from dashboard clicks)
      if (statusFilter.value) {
        list = list.filter(vm => vm.status.toLowerCase() === statusFilter.value.toLowerCase())
      }

      // Inline status dropdown
      if (managedStatusFilter.value) {
        list = list.filter(vm => vm.status.toLowerCase() === managedStatusFilter.value.toLowerCase())
      }

      // Free-text search across name, VMID, and node
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
      router.push('/vms')
    }

    watch(() => route.query.status, (newStatus) => {
      statusFilter.value = newStatus || null
    })

    // ── All Proxmox VMs tab ────────────────────────────────────────────────
    const allVMs = ref([])
    const allLoading = ref(false)
    const allError = ref(null)
    const allSearch = ref('')
    const allStatusFilter = ref('')
    const allSortField = ref('vmid')
    const allSortDirection = ref('asc')

    const fetchAllProxmoxVMs = async (resetCountdown = false) => {
      if (resetCountdown) {
        const intervalSecs = parseInt(localStorage.getItem('depl0y_refresh_interval') || '30', 10)
        resetAllCountdown(intervalSecs)
      }
      allLoading.value = true
      allError.value = null
      try {
        const hostsResp = await api.proxmox.listHosts()
        const hosts = hostsResp.data

        if (!hosts || hosts.length === 0) {
          allVMs.value = []
          return
        }

        const results = []
        await Promise.allSettled(
          hosts.map(async (host) => {
            try {
              const resResp = await api.pveNode.clusterResources(host.id, 'vm')
              const resources = resResp.data
              // clusterResources may return { data: [...] } or directly an array
              const items = Array.isArray(resources) ? resources : (resources.data || [])
              items.forEach((item) => {
                // Only include qemu VMs (not lxc containers)
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
                  tags: item.tags || '',
                  _busy: false,
                })
              })
            } catch (err) {
              console.warn(`Failed to fetch cluster resources for host ${host.id}:`, err)
            }
          })
        )

        allVMs.value = results
      } catch (err) {
        console.error('Failed to fetch Proxmox hosts:', err)
        allError.value = 'Failed to load Proxmox hosts. Check that at least one host is configured.'
      } finally {
        allLoading.value = false
      }
    }

    const allSortBy = (field) => {
      if (allSortField.value === field) {
        allSortDirection.value = allSortDirection.value === 'asc' ? 'desc' : 'asc'
      } else {
        allSortField.value = field
        allSortDirection.value = 'asc'
      }
    }

    const filteredAllVMs = computed(() => {
      let list = allVMs.value

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

    const navigateToVM = (vm) => {
      router.push(`/proxmox/${vm.hostId}/nodes/${vm.node}/vms/${vm.vmid}`)
    }

    const allStartVM = async (vm) => {
      vm._busy = true
      try {
        await api.pveVm.start(vm.hostId, vm.node, vm.vmid)
        toast.success(`VM ${vm.vmid} started`)
        setTimeout(fetchAllProxmoxVMs, 2000)
      } catch (err) {
        console.error('Failed to start VM:', err)
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
        console.error('Failed to stop VM:', err)
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
        console.error('Failed to shutdown VM:', err)
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
      if (newSet.has(key)) {
        newSet.delete(key)
      } else {
        newSet.add(key)
      }
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
        // deselect all visible
        const newSet = new Set(selectedVmKeys.value)
        filteredAllVMs.value.forEach(vm => newSet.delete(vmKey(vm)))
        selectedVmKeys.value = newSet
      } else {
        // select all visible
        const newSet = new Set(selectedVmKeys.value)
        filteredAllVMs.value.forEach(vm => newSet.add(vmKey(vm)))
        selectedVmKeys.value = newSet
      }
    }

    const clearSelection = () => {
      selectedVmKeys.value = new Set()
    }

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
        try {
          await actionFn(vm)
        } catch (err) {
          console.error(`Bulk ${action} failed for VM ${vm.vmid}:`, err)
          toast.error(`Failed to ${action} VM ${vm.vmid}`)
        }
        if (i < vmsToAct.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 300))
        }
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

    const selectedVmObjects = computed(() =>
      allVMs.value.filter(vm => selectedVmKeys.value.has(vmKey(vm)))
    )

    const openBulkSnapshotModal = () => {
      const now = new Date()
      const pad = (n) => String(n).padStart(2, '0')
      bulkSnapName.value = `bulk-snap-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`
      bulkSnapDescription.value = ''
      bulkOpResults.value = []
      bulkOpDone.value = false
      showBulkSnapshotModal.value = true
    }

    const openBulkTagModal = () => {
      bulkTagValue.value = ''
      bulkOpResults.value = []
      bulkOpDone.value = false
      showBulkTagModal.value = true
    }

    const openBulkDeleteModal = () => {
      bulkDeleteConfirm.value = ''
      bulkOpResults.value = []
      bulkOpDone.value = false
      showBulkDeleteModal.value = true
    }

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
        key: vmKey(vm),
        vmid: vm.vmid,
        name: vm.name,
        node: vm.node,
        hostId: vm.hostId,
        status: 'pending',
        error: null,
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
          await api.pveVm.createSnapshot(r.hostId, r.node, r.vmid, {
            snapname: bulkSnapName.value.trim(),
            description: bulkSnapDescription.value.trim(),
          })
          bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'success' }
          toast.success(`Snapshot created on VM ${r.vmid}`)
        } catch (err) {
          const msg = err.response?.data?.detail || err.message || 'Unknown error'
          bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'error', error: msg }
          toast.error(`Failed to snapshot VM ${r.vmid}: ${msg}`)
        }
        if (i < bulkOpResults.value.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 300))
        }
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
          if (!tagsArr.includes(tag)) {
            tagsArr.push(tag)
          }
          await api.pveVm.updateConfig(r.hostId, r.node, r.vmid, { tags: tagsArr.join(';') })
          bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'success' }
        } catch (err) {
          const msg = err.response?.data?.detail || err.message || 'Unknown error'
          bulkOpResults.value[i] = { ...bulkOpResults.value[i], status: 'error', error: msg }
          toast.error(`Failed to tag VM ${r.vmid}: ${msg}`)
        }
        if (i < bulkOpResults.value.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 200))
        }
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
          try {
            await api.pveVm.stop(r.hostId, r.node, r.vmid)
            await new Promise(resolve => setTimeout(resolve, 3000))
          } catch (err) {
            console.warn(`Failed to stop VM ${r.vmid} before delete:`, err)
          }
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
        if (i < bulkOpResults.value.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 500))
        }
      }
      bulkRunning.value = false
      bulkOpDone.value = true
      clearSelection()
      setTimeout(() => fetchAllProxmoxVMs(), 2000)
    }

    // ── Tags helpers ────────────────────────────────────────────────────────
    const parseTags = (tagsStr) => {
      if (!tagsStr) return []
      // PVE tags are semicolon-separated
      return tagsStr.split(';').map(t => t.trim()).filter(Boolean)
    }

    // Stable color per tag string (based on hash)
    const tagColorPalette = [
      '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
      '#ef4444', '#06b6d4', '#84cc16', '#f97316',
    ]
    const tagColor = (tag) => {
      let hash = 0
      for (let i = 0; i < tag.length; i++) hash = tag.charCodeAt(i) + ((hash << 5) - hash)
      return tagColorPalette[Math.abs(hash) % tagColorPalette.length]
    }

    const anyVmHasTags = computed(() => allVMs.value.some(vm => vm.tags))

    // ── Shared helpers ─────────────────────────────────────────────────────
    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
    }

    const getStatusBadgeClass = (status) => {
      const classMap = {
        running: 'badge-success',
        stopped: 'badge-danger',
        paused: 'badge-warning',
        suspended: 'badge-warning',
        unknown: 'badge-secondary'
      }
      return classMap[(status || '').toLowerCase()] || 'badge-info'
    }

    // ── Auto-refresh ────────────────────────────────────────────────────────
    const allCountdown = ref(0)
    let managedInterval = null
    let allInterval = null
    let allTickInterval = null

    const resetAllCountdown = (intervalSecs) => {
      allCountdown.value = intervalSecs
    }

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
      // Resume tick immediately when page becomes visible again
      if (document.visibilityState === 'visible' && activeTab.value === 'all') {
        fetchAllProxmoxVMs()
      }
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
    })

    onUnmounted(() => {
      clearInterval(managedInterval)
      clearInterval(allInterval)
      clearInterval(allTickInterval)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    })

    return {
      // tab
      activeTab,
      switchTab,
      // managed tab
      vms,
      loading,
      sortField,
      sortDirection,
      statusFilter,
      managedSearch,
      managedStatusFilter,
      filteredVMs,
      showDeleteConfirmModal,
      vmToDelete,
      deleteConfirmInput,
      sortBy,
      startVM,
      stopVM,
      powerOffVM,
      restartVM,
      showDeleteModal,
      closeDeleteModal,
      deleteVM,
      clearFilter,
      // all proxmox tab
      allVMs,
      allLoading,
      allError,
      allSearch,
      allStatusFilter,
      allSortField,
      allSortDirection,
      filteredAllVMs,
      fetchAllProxmoxVMs,
      allSortBy,
      navigateToVM,
      allStartVM,
      allStopVM,
      allShutdownVM,
      allCountdown,
      // shared
      formatBytes,
      getStatusBadgeClass,
      // tags
      parseTags,
      tagColor,
      anyVmHasTags,
      // bulk selection
      selectedVmKeys,
      bulkRunning,
      vmKey,
      toggleSelectVm,
      allPageSelected,
      somePageSelected,
      toggleSelectAll,
      clearSelection,
      bulkAction,
      // bulk ops
      showBulkSnapshotModal,
      showBulkTagModal,
      showBulkDeleteModal,
      bulkSnapName,
      bulkSnapDescription,
      bulkTagValue,
      bulkDeleteConfirm,
      bulkOpResults,
      bulkOpDone,
      selectedVmObjects,
      openBulkSnapshotModal,
      openBulkTagModal,
      openBulkDeleteModal,
      closeBulkModal,
      runBulkSnapshot,
      runBulkTag,
      runBulkDelete,
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

.tab-btn:hover {
  color: var(--text-primary, #1e293b);
}

.tab-btn-active {
  color: var(--primary-color, #3b82f6);
  border-bottom-color: var(--primary-color, #3b82f6);
}

/* ── VM name link ─────────────────────────────────────────────────────────── */
.vm-name-link {
  color: var(--primary-color, #3b82f6);
  text-decoration: none;
}

.vm-name-link:hover {
  text-decoration: underline;
}

/* ── Existing styles (unchanged) ──────────────────────────────────────────── */
.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.sortable {
  cursor: pointer;
  user-select: none;
}

.sortable:hover {
  background-color: var(--background);
}

.sort-indicator {
  margin-left: 0.25rem;
  font-size: 0.75rem;
  opacity: 0.7;
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background-color: var(--background);
  border-bottom: 1px solid var(--border);
}

.filter-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.filter-label {
  font-size: 0.875rem;
  color: var(--text-muted);
}

.filter-count {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin-left: 0.25rem;
}

/* Delete Confirmation Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background-color: var(--surface);
  border-radius: 0.5rem;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 2rem;
  line-height: 1;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-close:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: 1.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color);
}

.text-danger {
  color: #991b1b;
  font-weight: 500;
}

.text-muted {
  color: #475569;
}

.mb-1 {
  margin-bottom: 0.5rem;
}

.mb-2 {
  margin-bottom: 1rem;
}

.form-group {
  margin-top: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--text-primary);
}

.form-control {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background-color: var(--background);
  color: var(--text-primary);
  font-size: 1rem;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color);
}

.btn-secondary {
  background-color: var(--secondary-color);
  color: white;
}

.btn-secondary:hover {
  opacity: 0.9;
}

.refresh-countdown {
  font-size: 0.75rem;
  color: var(--text-muted, #64748b);
  margin-right: 0.5rem;
}

/* ── Checkbox column ─────────────────────────────────────────────────────── */
.cb-col {
  width: 2rem;
  text-align: center;
  padding-left: 0.5rem;
  padding-right: 0.25rem;
}

/* ── Selected row highlight ───────────────────────────────────────────────── */
.row-selected td {
  background-color: rgba(59, 130, 246, 0.07);
}

/* ── Bulk action bar ─────────────────────────────────────────────────────── */
.bulk-action-bar {
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.6rem 1rem;
  background: var(--surface);
  border-top: 2px solid var(--primary-color, #3b82f6);
  box-shadow: 0 -4px 16px rgba(0,0,0,0.15);
  z-index: 10;
}

.bulk-count {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-right: 0.25rem;
}

.bulk-clear-link {
  font-size: 0.8rem;
  color: var(--text-secondary);
  text-decoration: underline;
  margin-left: auto;
}

.bulk-clear-link:hover {
  color: var(--text-primary);
}

/* ── VM Tags ──────────────────────────────────────────────────────────────── */
.vm-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.vm-tag-pill {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 9999px;
  color: #fff;
  white-space: nowrap;
  letter-spacing: 0.02em;
  text-transform: lowercase;
}

/* ── Bulk Op Results Table ──────────────────────────────────────────────────── */
.bulk-results-table {
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 0.375rem;
  overflow: hidden;
  margin-top: 1rem;
}

.bulk-results-header {
  display: grid;
  grid-template-columns: 70px 1fr 80px 90px;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: var(--background);
  border-bottom: 1px solid var(--border, #e2e8f0);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #64748b);
}

.bulk-results-row {
  display: grid;
  grid-template-columns: 70px 1fr 80px 90px;
  gap: 0.5rem;
  padding: 0.45rem 0.75rem;
  align-items: center;
  font-size: 0.875rem;
  border-bottom: 1px solid var(--border, #e2e8f0);
}

.bulk-results-row:last-child {
  border-bottom: none;
}

.bulk-done-summary {
  margin-top: 0.75rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── Bulk Delete List ─────────────────────────────────────────────────────── */
.bulk-delete-list {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 1rem 0;
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 0.375rem;
}

.bulk-delete-list li {
  padding: 0.4rem 0.75rem;
  font-size: 0.875rem;
  border-bottom: 1px solid var(--border, #e2e8f0);
}

.bulk-delete-list li:last-child {
  border-bottom: none;
}

.ml-1 { margin-left: 0.25rem; }
.mt-2 { margin-top: 1rem; }

/* ── Mobile Responsive ──────────────────────────────────────────────────── */
@media (max-width: 768px) {
  /* Filter bar: stack on mobile */
  .filter-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .filter-bar .filter-info {
    width: 100%;
  }

  .filter-bar input.form-control,
  .filter-bar select.form-control {
    width: 100% !important;
  }

  /* VM table: card layout on mobile */
  .table-container table thead {
    display: none;
  }

  .table-container table tr {
    display: block;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin-bottom: 0.5rem;
    background: var(--surface);
    overflow: hidden;
  }

  .table-container table tr.row-selected {
    border-color: var(--primary-color);
  }

  .table-container table td {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.4rem 0.75rem;
    border-top: 1px solid var(--border-color);
    border-bottom: none;
  }

  .table-container table td:first-child {
    border-top: none;
  }

  .table-container table td::before {
    content: attr(data-label);
    font-weight: 600;
    color: var(--text-secondary);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    flex-shrink: 0;
    margin-right: 0.5rem;
  }

  /* Bulk action bar: full-width on mobile */
  .bulk-action-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    flex-direction: column;
    align-items: stretch;
    padding: 0.75rem 1rem;
    gap: 0.4rem;
  }

  .bulk-action-bar .btn {
    justify-content: center;
  }

  .bulk-clear-link {
    text-align: center;
    margin-left: 0;
  }

  /* Tab bar: scrollable on mobile */
  .tab-bar {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    white-space: nowrap;
    flex-wrap: nowrap;
  }
}

/* ── Empty state ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3.5rem 1.5rem;
  text-align: center;
}

.empty-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--background);
  border: 2px dashed var(--border-color);
  color: var(--text-muted);
}

.empty-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.empty-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
}
</style>
