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

      <!-- Filter Bar -->
      <div v-if="statusFilter" class="filter-bar">
        <div class="filter-info">
          <span class="filter-label">Filtered by status:</span>
          <span :class="['badge', getStatusBadgeClass(statusFilter)]">
            {{ statusFilter }}
          </span>
          <span class="filter-count">({{ filteredVMs.length }} VMs)</span>
        </div>
        <button @click="clearFilter" class="btn btn-sm btn-secondary">
          Clear Filter
        </button>
      </div>

      <div v-if="loading" class="loading-spinner"></div>

      <div v-else-if="filteredVMs.length === 0 && vms.length === 0" class="text-center text-muted">
        <p>No virtual machines yet.</p>
        <p class="text-sm">Create your first VM to get started.</p>
      </div>

      <div v-else-if="filteredVMs.length === 0 && statusFilter" class="text-center text-muted">
        <p>No {{ statusFilter }} VMs found.</p>
        <button @click="clearFilter" class="btn btn-sm btn-secondary mt-1">
          Show All VMs
        </button>
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

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
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
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="vm in filteredAllVMs" :key="`${vm.hostId}-${vm.node}-${vm.vmid}`">
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
      if (!statusFilter.value) {
        return vms.value
      }
      return vms.value.filter(vm =>
        vm.status.toLowerCase() === statusFilter.value.toLowerCase()
      )
    })

    const clearFilter = () => {
      statusFilter.value = null
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
</style>
