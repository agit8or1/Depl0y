<template>
  <div class="resource-pools-page">
    <div class="page-header">
      <div class="page-header-top">
        <div>
          <h2>Resource Pools</h2>
          <p class="text-muted">Organize VMs and storage into logical groups</p>
        </div>
        <div class="header-controls">
          <select v-model="selectedHostId" class="form-control host-select" @change="onHostChange">
            <option value="">Select a Proxmox host...</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
          </select>
        </div>
      </div>
    </div>

    <div v-if="!selectedHostId" class="empty-state">
      <div class="empty-icon">🗂️</div>
      <p>Select a Proxmox host to manage its resource pools.</p>
    </div>

    <div v-else class="pools-layout">
      <!-- ── Sidebar: Pool List ──────────────────────────────── -->
      <div class="pools-sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">Pools</span>
          <button @click="showCreateModal = true" class="btn btn-primary btn-sm">+ Create</button>
        </div>

        <div v-if="loadingPools" class="loading-spinner"></div>

        <div v-else-if="pools.length === 0" class="sidebar-empty text-muted text-sm">
          No pools found.
        </div>

        <div v-else class="pool-list">
          <div
            v-for="pool in pools"
            :key="pool.poolid"
            :class="['pool-list-item', { active: selectedPool === pool.poolid }]"
            @click="selectPool(pool.poolid)"
          >
            <div class="pool-list-name">{{ pool.poolid }}</div>
            <div class="pool-list-meta text-xs text-muted">{{ pool.comment || 'No description' }}</div>
            <button
              @click.stop="deletePool(pool.poolid)"
              class="pool-delete-btn"
              title="Delete pool"
            >×</button>
          </div>
        </div>
      </div>

      <!-- ── Detail Panel ───────────────────────────────────── -->
      <div class="pools-detail">
        <div v-if="!selectedPool" class="detail-empty">
          <p class="text-muted">Select a pool from the left to view details.</p>
        </div>

        <div v-else-if="loadingDetail" class="loading-spinner"></div>

        <div v-else-if="poolDetail" class="detail-content">
          <!-- Header -->
          <div class="detail-header">
            <div class="detail-title-row">
              <h3 class="detail-title">{{ poolDetail.poolid }}</h3>
              <div class="detail-actions">
                <button @click="openAddMembers" class="btn btn-outline btn-sm">+ Add Members</button>
              </div>
            </div>

            <!-- Inline comment editor -->
            <div class="comment-row">
              <template v-if="editingComment">
                <input
                  v-model="commentDraft"
                  class="form-control comment-input"
                  placeholder="Pool description..."
                  @keyup.enter="saveComment"
                  @keyup.escape="cancelEditComment"
                />
                <button @click="saveComment" class="btn btn-primary btn-sm" :disabled="savingComment">
                  {{ savingComment ? 'Saving...' : 'Save' }}
                </button>
                <button @click="cancelEditComment" class="btn btn-outline btn-sm">Cancel</button>
              </template>
              <template v-else>
                <span class="comment-text text-muted text-sm">{{ poolDetail.comment || 'No description' }}</span>
                <button @click="startEditComment" class="btn btn-outline btn-xs">Edit</button>
              </template>
            </div>
          </div>

          <!-- Stats Cards -->
          <div class="stats-row">
            <div class="stat-card">
              <div class="stat-value">{{ vmMembers.length }}</div>
              <div class="stat-label">Total VMs/CTs</div>
            </div>
            <div class="stat-card stat-running">
              <div class="stat-value">{{ runningVms }}</div>
              <div class="stat-label">Running</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ storageMembers.length }}</div>
              <div class="stat-label">Storage</div>
            </div>
          </div>

          <!-- VMs / LXCs Table -->
          <div class="detail-section">
            <h4 class="section-title">VMs &amp; Containers</h4>
            <div class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>VMID</th>
                    <th>Name</th>
                    <th>Node</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="m in vmMembers" :key="m.vmid">
                    <td><strong>{{ m.vmid }}</strong></td>
                    <td>{{ m.name || '—' }}</td>
                    <td>{{ m.node }}</td>
                    <td>
                      <span :class="['badge', m.type === 'qemu' ? 'badge-info' : 'badge-warning']">
                        {{ m.type === 'qemu' ? 'VM' : 'CT' }}
                      </span>
                    </td>
                    <td>
                      <span :class="['badge', m.status === 'running' ? 'badge-success' : 'badge-secondary']">
                        {{ m.status || 'unknown' }}
                      </span>
                    </td>
                    <td>
                      <div class="flex gap-1">
                        <button
                          v-if="m.status !== 'running'"
                          @click="vmAction(m, 'start')"
                          class="btn btn-success btn-xs"
                          :disabled="vmActionLoading[m.vmid]"
                        >Start</button>
                        <button
                          v-if="m.status === 'running'"
                          @click="vmAction(m, 'shutdown')"
                          class="btn btn-warning btn-xs"
                          :disabled="vmActionLoading[m.vmid]"
                        >Stop</button>
                        <button
                          @click="removeMember(m.vmid, null)"
                          class="btn btn-danger btn-xs"
                          title="Remove from pool"
                        >Remove</button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="vmMembers.length === 0">
                    <td colspan="6" class="text-center text-muted text-sm" style="padding: 1.5rem;">
                      No VMs or containers in this pool
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Storage Table -->
          <div class="detail-section">
            <h4 class="section-title">Storage</h4>
            <div class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>Storage</th>
                    <th>Node</th>
                    <th>Type</th>
                    <th>Content</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="m in storageMembers" :key="m.storage + '-' + m.node">
                    <td><strong>{{ m.storage }}</strong></td>
                    <td>{{ m.node }}</td>
                    <td><span class="badge badge-secondary">{{ m.plugintype || '—' }}</span></td>
                    <td class="text-sm">{{ m.content || '—' }}</td>
                    <td>
                      <button
                        @click="removeMember(null, m.storage)"
                        class="btn btn-danger btn-xs"
                        title="Remove from pool"
                      >Remove</button>
                    </td>
                  </tr>
                  <tr v-if="storageMembers.length === 0">
                    <td colspan="5" class="text-center text-muted text-sm" style="padding: 1.5rem;">
                      No storage in this pool
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Create Pool Modal ────────────────────────────────── -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Create Resource Pool</h3>
          <button @click="showCreateModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="createPool" class="modal-body">
          <div class="form-group">
            <label class="form-label">Pool ID *</label>
            <input
              v-model="newPool.poolid"
              class="form-control"
              placeholder="e.g. production"
              required
              pattern="[A-Za-z0-9_\-]+"
              title="Letters, numbers, hyphens and underscores only"
            />
            <p class="text-xs text-muted mt-1">Letters, numbers, hyphens and underscores only</p>
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
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

    <!-- ── Add Members Modal ────────────────────────────────── -->
    <div v-if="showAddMembersModal" class="modal-overlay" @click.self="showAddMembersModal = false">
      <div class="modal-box modal-wide">
        <div class="modal-header">
          <h3>Add Members to "{{ selectedPool }}"</h3>
          <button @click="showAddMembersModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <!-- Tabs -->
          <div class="modal-tabs">
            <button
              :class="['modal-tab', { active: addTab === 'vms' }]"
              @click="addTab = 'vms'"
            >VMs &amp; Containers</button>
            <button
              :class="['modal-tab', { active: addTab === 'storage' }]"
              @click="addTab = 'storage'"
            >Storage</button>
          </div>

          <!-- VMs Tab -->
          <div v-if="addTab === 'vms'">
            <div v-if="loadingResources" class="loading-spinner"></div>
            <div v-else class="member-select-list">
              <label
                v-for="vm in availableVms"
                :key="vm.vmid"
                class="member-check-row"
              >
                <input type="checkbox" :value="vm.vmid" v-model="selectedVmids" />
                <span class="member-check-label">
                  <strong>{{ vm.vmid }}</strong>
                  <span class="text-muted text-sm"> — {{ vm.name || 'unnamed' }}</span>
                  <span class="badge badge-secondary ml-1" style="font-size:0.7rem;">{{ vm.node }}</span>
                  <span :class="['badge ml-1', vm.type === 'qemu' ? 'badge-info' : 'badge-warning']" style="font-size:0.7rem;">
                    {{ vm.type === 'qemu' ? 'VM' : 'CT' }}
                  </span>
                </span>
              </label>
              <p v-if="availableVms.length === 0" class="text-muted text-sm" style="padding: 1rem 0;">
                No VMs available to add.
              </p>
            </div>
          </div>

          <!-- Storage Tab -->
          <div v-if="addTab === 'storage'">
            <div v-if="loadingResources" class="loading-spinner"></div>
            <div v-else class="member-select-list">
              <label
                v-for="st in availableStorage"
                :key="st.storage + '-' + st.node"
                class="member-check-row"
              >
                <input type="checkbox" :value="st.storage" v-model="selectedStorages" />
                <span class="member-check-label">
                  <strong>{{ st.storage }}</strong>
                  <span class="text-muted text-sm"> — {{ st.node }}</span>
                  <span class="badge badge-secondary ml-1" style="font-size:0.7rem;">{{ st.plugintype || st.type }}</span>
                </span>
              </label>
              <p v-if="availableStorage.length === 0" class="text-muted text-sm" style="padding: 1rem 0;">
                No storage available to add.
              </p>
            </div>
          </div>

          <div class="flex gap-1 mt-2">
            <button @click="addMembers" class="btn btn-primary" :disabled="addingMembers || (selectedVmids.length === 0 && selectedStorages.length === 0)">
              {{ addingMembers ? 'Adding...' : 'Add Selected' }}
            </button>
            <button @click="showAddMembersModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'ResourcePools',
  setup() {
    const toast = useToast()

    // Host selection
    const hosts = ref([])
    const selectedHostId = ref('')

    // Pools list
    const pools = ref([])
    const loadingPools = ref(false)

    // Selected pool detail
    const selectedPool = ref(null)
    const poolDetail = ref(null)
    const loadingDetail = ref(false)

    // Comment editing
    const editingComment = ref(false)
    const commentDraft = ref('')
    const savingComment = ref(false)

    // Create pool modal
    const showCreateModal = ref(false)
    const saving = ref(false)
    const newPool = ref({ poolid: '', comment: '' })

    // Add members modal
    const showAddMembersModal = ref(false)
    const addTab = ref('vms')
    const loadingResources = ref(false)
    const availableVms = ref([])
    const availableStorage = ref([])
    const selectedVmids = ref([])
    const selectedStorages = ref([])
    const addingMembers = ref(false)

    // VM action loading
    const vmActionLoading = ref({})

    // Computed members
    const vmMembers = computed(() => {
      if (!poolDetail.value || !poolDetail.value.members) return []
      return poolDetail.value.members.filter(m => m.type === 'qemu' || m.type === 'lxc')
    })

    const storageMembers = computed(() => {
      if (!poolDetail.value || !poolDetail.value.members) return []
      return poolDetail.value.members.filter(m => m.type === 'storage')
    })

    const runningVms = computed(() => vmMembers.value.filter(m => m.status === 'running').length)

    // Load hosts
    const fetchHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = res.data || []
        if (hosts.value.length === 1) {
          selectedHostId.value = hosts.value[0].id
          await fetchPools()
        }
      } catch (e) {
        console.error('Failed to fetch hosts:', e)
      }
    }

    const onHostChange = () => {
      selectedPool.value = null
      poolDetail.value = null
      pools.value = []
      if (selectedHostId.value) fetchPools()
    }

    // Fetch pools list
    const fetchPools = async () => {
      if (!selectedHostId.value) return
      loadingPools.value = true
      try {
        const res = await api.pveNode.listPools(selectedHostId.value)
        pools.value = res.data || []
      } catch (e) {
        console.error('Failed to fetch pools:', e)
        toast.error('Failed to load pools')
      } finally {
        loadingPools.value = false
      }
    }

    // Select pool
    const selectPool = async (poolid) => {
      selectedPool.value = poolid
      poolDetail.value = null
      loadingDetail.value = true
      editingComment.value = false
      try {
        const res = await api.pveNode.getPool(selectedHostId.value, poolid)
        poolDetail.value = res.data
      } catch (e) {
        console.error('Failed to fetch pool detail:', e)
        toast.error('Failed to load pool details')
      } finally {
        loadingDetail.value = false
      }
    }

    // Comment editing
    const startEditComment = () => {
      commentDraft.value = poolDetail.value.comment || ''
      editingComment.value = true
    }

    const cancelEditComment = () => {
      editingComment.value = false
    }

    const saveComment = async () => {
      savingComment.value = true
      try {
        await api.pveNode.updatePool(selectedHostId.value, selectedPool.value, { comment: commentDraft.value })
        poolDetail.value.comment = commentDraft.value
        // Update pools list comment too
        const poolInList = pools.value.find(p => p.poolid === selectedPool.value)
        if (poolInList) poolInList.comment = commentDraft.value
        editingComment.value = false
        toast.success('Description updated')
      } catch (e) {
        console.error('Failed to save comment:', e)
        toast.error('Failed to update description')
      } finally {
        savingComment.value = false
      }
    }

    // Create pool
    const createPool = async () => {
      saving.value = true
      try {
        await api.pveNode.createPool(selectedHostId.value, newPool.value)
        toast.success(`Pool "${newPool.value.poolid}" created`)
        showCreateModal.value = false
        const createdId = newPool.value.poolid
        newPool.value = { poolid: '', comment: '' }
        await fetchPools()
        selectPool(createdId)
      } catch (e) {
        console.error('Failed to create pool:', e)
        toast.error('Failed to create pool')
      } finally {
        saving.value = false
      }
    }

    // Delete pool
    const deletePool = async (poolid) => {
      if (!confirm(`Delete pool "${poolid}"? VMs will remain but will be removed from the pool.`)) return
      try {
        await api.pveNode.deletePool(selectedHostId.value, poolid)
        toast.success(`Pool "${poolid}" deleted`)
        if (selectedPool.value === poolid) {
          selectedPool.value = null
          poolDetail.value = null
        }
        await fetchPools()
      } catch (e) {
        console.error('Failed to delete pool:', e)
        toast.error('Failed to delete pool')
      }
    }

    // VM actions (start / stop)
    const vmAction = async (member, action) => {
      vmActionLoading.value[member.vmid] = true
      try {
        if (member.type === 'qemu') {
          await api.pveVm[action === 'start' ? 'start' : 'shutdown'](selectedHostId.value, member.node, member.vmid)
        } else {
          await api.pveNode.ctAction(selectedHostId.value, member.node, member.vmid, action === 'start' ? 'start' : 'shutdown')
        }
        toast.success(`${action === 'start' ? 'Started' : 'Stopped'} ${member.name || member.vmid}`)
        // Refresh detail after brief delay
        setTimeout(() => selectPool(selectedPool.value), 2000)
      } catch (e) {
        console.error('VM action failed:', e)
        toast.error(`Failed to ${action} ${member.name || member.vmid}`)
      } finally {
        vmActionLoading.value[member.vmid] = false
      }
    }

    // Remove a member from pool
    const removeMember = async (vmid, storage) => {
      const label = vmid != null ? `VM ${vmid}` : `storage ${storage}`
      if (!confirm(`Remove ${label} from pool "${selectedPool.value}"?`)) return
      try {
        const params = { delete: 1 }
        if (vmid != null) params.vms = String(vmid)
        if (storage != null) params.storage = storage
        await api.pveNode.updatePool(selectedHostId.value, selectedPool.value, params)
        toast.success(`${label} removed from pool`)
        await selectPool(selectedPool.value)
      } catch (e) {
        console.error('Remove member failed:', e)
        toast.error(`Failed to remove ${label}`)
      }
    }

    // Open Add Members modal
    const openAddMembers = async () => {
      selectedVmids.value = []
      selectedStorages.value = []
      addTab.value = 'vms'
      showAddMembersModal.value = true
      loadingResources.value = true

      const currentVmIds = new Set(vmMembers.value.map(m => m.vmid))
      const currentStorages = new Set(storageMembers.value.map(m => m.storage))

      try {
        const res = await api.pveNode.clusterResources(selectedHostId.value)
        const all = res.data || []
        availableVms.value = all
          .filter(r => (r.type === 'qemu' || r.type === 'lxc') && !currentVmIds.has(r.vmid))
          .sort((a, b) => a.vmid - b.vmid)
        availableStorage.value = all
          .filter(r => r.type === 'storage' && !currentStorages.has(r.storage))
          .sort((a, b) => (a.storage || '').localeCompare(b.storage || ''))
      } catch (e) {
        console.error('Failed to fetch resources:', e)
        toast.error('Failed to load cluster resources')
        availableVms.value = []
        availableStorage.value = []
      } finally {
        loadingResources.value = false
      }
    }

    // Submit add members
    const addMembers = async () => {
      if (selectedVmids.value.length === 0 && selectedStorages.value.length === 0) return
      addingMembers.value = true
      try {
        const params = {}
        if (selectedVmids.value.length > 0) params.vms = selectedVmids.value.join(',')
        if (selectedStorages.value.length > 0) params.storage = selectedStorages.value.join(',')
        await api.pveNode.updatePool(selectedHostId.value, selectedPool.value, params)
        const count = selectedVmids.value.length + selectedStorages.value.length
        toast.success(`Added ${count} member(s) to pool`)
        showAddMembersModal.value = false
        await selectPool(selectedPool.value)
      } catch (e) {
        console.error('Failed to add members:', e)
        toast.error('Failed to add members to pool')
      } finally {
        addingMembers.value = false
      }
    }

    onMounted(() => {
      fetchHosts()
    })

    return {
      hosts,
      selectedHostId,
      pools,
      loadingPools,
      selectedPool,
      poolDetail,
      loadingDetail,
      vmMembers,
      storageMembers,
      runningVms,
      editingComment,
      commentDraft,
      savingComment,
      showCreateModal,
      saving,
      newPool,
      showAddMembersModal,
      addTab,
      loadingResources,
      availableVms,
      availableStorage,
      selectedVmids,
      selectedStorages,
      addingMembers,
      vmActionLoading,
      onHostChange,
      selectPool,
      startEditComment,
      cancelEditComment,
      saveComment,
      createPool,
      deletePool,
      vmAction,
      removeMember,
      openAddMembers,
      addMembers,
    }
  }
}
</script>

<style scoped>
.resource-pools-page {
  padding: 1.5rem;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.host-select {
  min-width: 220px;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  gap: 0.75rem;
}

.empty-icon {
  font-size: 3rem;
}

/* ── Layout ─────────────────────────────────────────────── */

.pools-layout {
  flex: 1;
  display: flex;
  gap: 0;
  min-height: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
  background: var(--card-background, #fff);
}

.pools-sidebar {
  width: 30%;
  min-width: 200px;
  max-width: 300px;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  background: var(--background, #f9fafb);
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-title {
  font-weight: 600;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.sidebar-empty {
  padding: 2rem 1rem;
  text-align: center;
}

.pool-list {
  flex: 1;
  overflow-y: auto;
}

.pool-list-item {
  position: relative;
  padding: 0.75rem 1rem;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s;
  padding-right: 2.25rem;
}

.pool-list-item:hover {
  background: rgba(59, 130, 246, 0.05);
}

.pool-list-item.active {
  background: rgba(59, 130, 246, 0.1);
  border-left: 3px solid var(--primary, #3b82f6);
}

.pool-list-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--text-primary);
}

.pool-list-meta {
  margin-top: 0.15rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pool-delete-btn {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  font-size: 1.25rem;
  color: var(--text-secondary);
  cursor: pointer;
  line-height: 1;
  padding: 0.1rem 0.25rem;
  border-radius: 0.25rem;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}

.pool-list-item:hover .pool-delete-btn {
  opacity: 1;
}

.pool-delete-btn:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

/* ── Detail Panel ──────────────────────────────────────── */

.pools-detail {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.detail-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.detail-content {
  padding: 1.5rem;
  flex: 1;
}

.detail-header {
  margin-bottom: 1.25rem;
}

.detail-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.detail-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
}

.comment-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.comment-text {
  flex: 1;
}

.comment-input {
  flex: 1;
  max-width: 400px;
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

/* Stats */
.stats-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  flex: 1;
  background: var(--background, #f9fafb);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  text-align: center;
}

.stat-card.stat-running {
  background: rgba(16, 185, 129, 0.05);
  border-color: rgba(16, 185, 129, 0.3);
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-top: 0.25rem;
}

/* Section */
.detail-section {
  margin-bottom: 2rem;
}

.section-title {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-secondary);
  margin: 0 0 0.75rem 0;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

/* ── Modals ────────────────────────────────────────────── */

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-box {
  background: var(--card-background, #fff);
  border-radius: 0.5rem;
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3);
}

.modal-box.modal-wide {
  max-width: 640px;
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
  font-size: 1.75rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.modal-body {
  padding: 1.5rem;
}

/* Modal tabs */
.modal-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 1rem;
}

.modal-tab {
  padding: 0.5rem 1rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-secondary);
  font-weight: 500;
  transition: all 0.15s;
}

.modal-tab.active {
  color: var(--primary, #3b82f6);
  border-bottom-color: var(--primary, #3b82f6);
}

/* Member selection list */
.member-select-list {
  max-height: 280px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.5rem;
  margin-bottom: 1rem;
}

.member-check-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.25rem;
  cursor: pointer;
  border-radius: 0.25rem;
  transition: background 0.1s;
}

.member-check-row:hover {
  background: rgba(59, 130, 246, 0.05);
}

.member-check-label {
  flex: 1;
  font-size: 0.9rem;
}

/* Utilities */
.ml-1 {
  margin-left: 0.25rem;
}

.btn-xs {
  padding: 0.2rem 0.4rem;
  font-size: 0.75rem;
}

.badge-secondary {
  background-color: rgba(100, 116, 139, 0.15);
  color: #475569;
}

.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.mt-1 { margin-top: 0.25rem; }
.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.text-muted { color: var(--text-secondary); }
.text-center { text-align: center; }
</style>
