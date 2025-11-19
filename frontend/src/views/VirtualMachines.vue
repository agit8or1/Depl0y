<template>
  <div class="vms-page">
    <div class="card">
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
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'VirtualMachines',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const toast = useToast()
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
        setTimeout(fetchVMs, 1000) // Refresh after 1 second
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
      return classMap[status.toLowerCase()] || 'badge-info'
    }

    // Computed property for filtered VMs
    const filteredVMs = computed(() => {
      if (!statusFilter.value) {
        return vms.value
      }
      return vms.value.filter(vm =>
        vm.status.toLowerCase() === statusFilter.value.toLowerCase()
      )
    })

    // Clear filter and return to all VMs
    const clearFilter = () => {
      statusFilter.value = null
      router.push('/vms')
    }

    // Watch for route changes to update filter
    watch(() => route.query.status, (newStatus) => {
      statusFilter.value = newStatus || null
    })

    onMounted(() => {
      fetchVMs()
      // Auto-refresh every 30 seconds
      const interval = setInterval(fetchVMs, 30000)
      return () => clearInterval(interval)
    })

    return {
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
      formatBytes,
      getStatusBadgeClass,
      clearFilter
    }
  }
}
</script>

<style scoped>
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
</style>
