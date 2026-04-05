<template>
  <div class="pve-pools-page">
    <div class="page-header mb-2">
      <h2>Resource Pools</h2>
      <p class="text-muted">Manage Proxmox resource pools for host {{ hostId }}</p>
    </div>

    <div class="card">
      <div class="card-header">
        <h3>Pools</h3>
        <button @click="showCreateModal = true" class="btn btn-primary">+ Create Pool</button>
      </div>

      <div v-if="loading" class="loading-spinner"></div>

      <div v-else-if="pools.length === 0" class="text-center text-muted" style="padding: 2rem;">
        <p>No resource pools configured.</p>
        <p class="text-sm">Create a pool to organize your VMs and storage.</p>
      </div>

      <div v-else class="pools-list">
        <div v-for="pool in pools" :key="pool.poolid" class="pool-item">
          <div class="pool-row">
            <div class="pool-info">
              <div class="pool-name">
                <strong>{{ pool.poolid }}</strong>
                <span class="badge badge-info" style="margin-left: 0.5rem;">{{ (pool.members || []).filter(m => m.type === 'qemu' || m.type === 'lxc').length }} VMs</span>
                <span class="badge badge-warning" style="margin-left: 0.25rem;">{{ (pool.members || []).filter(m => m.type === 'storage').length }} Storage</span>
              </div>
              <div class="text-sm text-muted">{{ pool.comment || 'No description' }}</div>
            </div>
            <div class="pool-actions flex gap-1">
              <button @click="toggleExpand(pool.poolid)" class="btn btn-outline btn-sm">
                {{ expanded[pool.poolid] ? 'Collapse' : 'Expand' }}
              </button>
              <button @click="deletePool(pool.poolid)" class="btn btn-danger btn-sm">Delete</button>
            </div>
          </div>

          <!-- Expanded Detail -->
          <div v-if="expanded[pool.poolid]" class="pool-expanded">
            <div v-if="loadingDetail[pool.poolid]" class="loading-spinner"></div>
            <div v-else-if="poolDetails[pool.poolid]">
              <div class="expanded-section">
                <h5>Member VMs / Containers</h5>
                <div class="table-container">
                  <table class="table">
                    <thead>
                      <tr>
                        <th>VMID</th>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Node</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="m in poolDetails[pool.poolid].members.filter(m => m.type === 'qemu' || m.type === 'lxc')" :key="m.vmid">
                        <td><strong>{{ m.vmid }}</strong></td>
                        <td>{{ m.name || '—' }}</td>
                        <td>
                          <span :class="['badge', m.type === 'qemu' ? 'badge-info' : 'badge-warning']">
                            {{ m.type === 'qemu' ? 'VM' : 'CT' }}
                          </span>
                        </td>
                        <td>{{ m.node }}</td>
                        <td>
                          <span :class="['badge', m.status === 'running' ? 'badge-success' : 'badge-danger']">
                            {{ m.status }}
                          </span>
                        </td>
                      </tr>
                      <tr v-if="poolDetails[pool.poolid].members.filter(m => m.type === 'qemu' || m.type === 'lxc').length === 0">
                        <td colspan="5" class="text-center text-muted text-sm">No VMs or containers in this pool</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div class="expanded-section">
                <h5>Storage Volumes</h5>
                <div class="table-container">
                  <table class="table">
                    <thead>
                      <tr>
                        <th>Storage ID</th>
                        <th>Node</th>
                        <th>Content</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="m in poolDetails[pool.poolid].members.filter(m => m.type === 'storage')" :key="m.storage + m.node">
                        <td><strong>{{ m.storage }}</strong></td>
                        <td>{{ m.node }}</td>
                        <td class="text-sm">{{ m.content || '—' }}</td>
                        <td>
                          <span :class="['badge', m.active ? 'badge-success' : 'badge-danger']">
                            {{ m.active ? 'Active' : 'Inactive' }}
                          </span>
                        </td>
                      </tr>
                      <tr v-if="poolDetails[pool.poolid].members.filter(m => m.type === 'storage').length === 0">
                        <td colspan="4" class="text-center text-muted text-sm">No storage in this pool</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Pool Modal -->
    <div v-if="showCreateModal" class="modal" @click="showCreateModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Resource Pool</h3>
          <button @click="showCreateModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="createPool" class="modal-body">
          <div class="form-group">
            <label class="form-label">Pool ID</label>
            <input v-model="newPool.poolid" class="form-control" placeholder="mypool" required />
            <p class="text-xs text-muted mt-1">Letters, numbers, hyphens and underscores only</p>
          </div>
          <div class="form-group">
            <label class="form-label">Comment / Description</label>
            <input v-model="newPool.comment" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? 'Creating...' : 'Create Pool' }}
            </button>
            <button type="button" @click="showCreateModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'PvePools',
  setup() {
    const route = useRoute()
    const toast = useToast()
    const hostId = ref(route.params.hostId)
    const pools = ref([])
    const loading = ref(false)
    const saving = ref(false)
    const showCreateModal = ref(false)
    const expanded = ref({})
    const poolDetails = ref({})
    const loadingDetail = ref({})

    const newPool = ref({ poolid: '', comment: '' })

    const fetchPools = async () => {
      loading.value = true
      try {
        const response = await api.pveNode.listPools(hostId.value)
        pools.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch pools:', error)
        toast.error('Failed to load pools')
      } finally {
        loading.value = false
      }
    }

    const toggleExpand = async (poolid) => {
      expanded.value[poolid] = !expanded.value[poolid]
      if (expanded.value[poolid] && !poolDetails.value[poolid]) {
        loadingDetail.value[poolid] = true
        try {
          const response = await api.pveNode.getPool(hostId.value, poolid)
          poolDetails.value[poolid] = response.data
        } catch (error) {
          console.error('Failed to fetch pool details:', error)
          poolDetails.value[poolid] = { members: [] }
        } finally {
          loadingDetail.value[poolid] = false
        }
      }
    }

    const createPool = async () => {
      saving.value = true
      try {
        await api.pveNode.createPool(hostId.value, newPool.value)
        toast.success('Pool created')
        showCreateModal.value = false
        newPool.value = { poolid: '', comment: '' }
        await fetchPools()
      } catch (error) {
        console.error('Failed to create pool:', error)
        toast.error('Failed to create pool')
      } finally {
        saving.value = false
      }
    }

    const deletePool = async (poolid) => {
      if (!confirm(`Delete pool "${poolid}"? VMs will not be deleted but will be removed from the pool.`)) return
      try {
        await api.pveNode.deletePool(hostId.value, poolid)
        toast.success('Pool deleted')
        delete expanded.value[poolid]
        delete poolDetails.value[poolid]
        await fetchPools()
      } catch (error) {
        console.error('Failed to delete pool:', error)
        toast.error('Failed to delete pool')
      }
    }

    onMounted(() => {
      fetchPools()
    })

    return {
      hostId,
      pools,
      loading,
      saving,
      showCreateModal,
      expanded,
      poolDetails,
      loadingDetail,
      newPool,
      fetchPools,
      toggleExpand,
      createPool,
      deletePool
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.pools-list {
  padding: 0;
}

.pool-item {
  border-bottom: 1px solid var(--border-color);
}

.pool-item:last-child {
  border-bottom: none;
}

.pool-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
}

.pool-name {
  margin-bottom: 0.25rem;
}

.pool-expanded {
  background: var(--background);
  border-top: 1px solid var(--border-color);
  padding: 1.5rem;
}

.expanded-section {
  margin-bottom: 1.5rem;
}

.expanded-section h5 {
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

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
  background: white;
  border-radius: 0.5rem;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 1.5rem;
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

.modal-body {
  padding: 1.5rem;
}
</style>
