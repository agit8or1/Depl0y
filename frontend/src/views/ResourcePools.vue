<template>
  <div class="resource-pools-page">
    <div class="page-header">
      <div class="page-header-top">
        <div>
          <h2>Resource Pools</h2>
          <p class="text-muted">Organize VMs and storage into logical groups with access control</p>
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
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
          <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
        </svg>
      </div>
      <p>Select a Proxmox host to manage its resource pools.</p>
    </div>

    <div v-else class="pools-layout">
      <!-- ── Sidebar: Pool List ──────────────────────────────── -->
      <div class="pools-sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">Pools</span>
          <button @click="showCreateModal = true" class="btn btn-primary btn-sm">+ Create</button>
        </div>

        <div v-if="loadingPools" class="sidebar-loading">
          <div class="loading-spinner-sm"></div>
          <span>Loading pools...</span>
        </div>

        <div v-else-if="pools.length === 0" class="sidebar-empty text-muted text-sm">
          No pools found. Create one to get started.
        </div>

        <div v-else class="pool-list">
          <div
            v-for="pool in pools"
            :key="pool.poolid"
            :class="['pool-list-item', { active: selectedPool === pool.poolid }]"
            @click="selectPool(pool.poolid)"
          >
            <div class="pool-list-main">
              <div class="pool-list-name">{{ pool.poolid }}</div>
              <div class="pool-list-meta text-xs text-muted">{{ pool.comment || 'No description' }}</div>
              <div class="pool-list-counts">
                <span class="pool-count-badge" title="VMs & Containers">
                  <svg viewBox="0 0 16 16" fill="currentColor" width="10" height="10"><rect x="1" y="3" width="14" height="10" rx="1.5"/><path d="M5 3V2a1 1 0 011-1h4a1 1 0 011 1v1"/></svg>
                  {{ (pool.members || []).filter(m => m.type === 'qemu' || m.type === 'lxc').length }}
                </span>
                <span class="pool-count-badge" title="Storage">
                  <svg viewBox="0 0 16 16" fill="currentColor" width="10" height="10"><path d="M3 3a2 2 0 012-2h6a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V3z"/></svg>
                  {{ (pool.members || []).filter(m => m.type === 'storage').length }}
                </span>
              </div>
            </div>
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
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40" style="opacity:.3;margin-bottom:.5rem;">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5a1.125 1.125 0 01-1.125-1.125v-1.5a3.375 3.375 0 00-3.375-3.375H9.75" />
          </svg>
          <p class="text-muted">Select a pool from the left to view details.</p>
        </div>

        <div v-else-if="loadingDetail" class="detail-loading">
          <div class="loading-spinner-sm"></div>
          <span>Loading pool details...</span>
        </div>

        <div v-else-if="poolDetail" class="detail-content">
          <!-- Header -->
          <div class="detail-header">
            <div class="detail-title-row">
              <h3 class="detail-title">{{ poolDetail.poolid }}</h3>
              <div class="detail-actions">
                <button @click="openAddVm" class="btn btn-outline btn-sm">+ Add VM</button>
                <button @click="openAddStorage" class="btn btn-outline btn-sm">+ Add Storage</button>
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

          <!-- Resource Summary Cards -->
          <div class="stats-row">
            <div class="stat-card">
              <div class="stat-value">{{ vmMembers.length }}</div>
              <div class="stat-label">Total VMs / CTs</div>
            </div>
            <div class="stat-card stat-running">
              <div class="stat-value">{{ runningVms }}</div>
              <div class="stat-label">Running</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ storageMembers.length }}</div>
              <div class="stat-label">Storage</div>
            </div>
            <div class="stat-card stat-cpu">
              <div class="stat-value">{{ totalCores }}</div>
              <div class="stat-label">Total Cores</div>
            </div>
            <div class="stat-card stat-ram">
              <div class="stat-value">{{ formatRam(totalRamMb) }}</div>
              <div class="stat-label">Allocated RAM</div>
            </div>
          </div>

          <!-- VMs / LXCs Table -->
          <div class="detail-section">
            <div class="section-header">
              <h4 class="section-title">VMs &amp; Containers</h4>
              <button @click="openAddVm" class="btn btn-outline btn-xs">+ Add</button>
            </div>
            <div class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>VMID</th>
                    <th>Name</th>
                    <th>Node</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>CPU</th>
                    <th>RAM</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="m in vmMembers" :key="m.vmid">
                    <td><strong>{{ m.vmid }}</strong></td>
                    <td>{{ m.name || '—' }}</td>
                    <td>
                      <span class="node-badge">{{ m.node }}</span>
                    </td>
                    <td>
                      <span :class="['badge', m.type === 'qemu' ? 'badge-info' : 'badge-warning']">
                        {{ m.type === 'qemu' ? 'VM' : 'CT' }}
                      </span>
                    </td>
                    <td>
                      <span :class="['status-dot', m.status === 'running' ? 'status-running' : 'status-stopped']">
                        {{ m.status || 'unknown' }}
                      </span>
                    </td>
                    <td class="text-sm text-muted">{{ m.maxcpu != null ? m.maxcpu + ' vCPU' : '—' }}</td>
                    <td class="text-sm text-muted">{{ m.maxmem ? formatRam(m.maxmem / 1024 / 1024) : '—' }}</td>
                    <td>
                      <div class="flex gap-1">
                        <button
                          v-if="m.status !== 'running'"
                          @click="vmAction(m, 'start')"
                          class="btn btn-success btn-xs"
                          :disabled="vmActionLoading[m.vmid]"
                          title="Start"
                        >&#9654;</button>
                        <button
                          v-if="m.status === 'running'"
                          @click="vmAction(m, 'shutdown')"
                          class="btn btn-warning btn-xs"
                          :disabled="vmActionLoading[m.vmid]"
                          title="Shutdown"
                        >&#9632;</button>
                        <button
                          @click="removeMember(m.vmid, null)"
                          class="btn btn-danger btn-xs"
                          title="Remove from pool"
                        >Remove</button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="vmMembers.length === 0">
                    <td colspan="8" class="text-center text-muted text-sm" style="padding: 1.5rem;">
                      No VMs or containers in this pool
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Storage Table -->
          <div class="detail-section">
            <div class="section-header">
              <h4 class="section-title">Storage</h4>
              <button @click="openAddStorage" class="btn btn-outline btn-xs">+ Add</button>
            </div>
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
                    <td>
                      <span class="node-badge">{{ m.node }}</span>
                    </td>
                    <td>
                      <span :class="['type-badge', 'type-' + (m.plugintype || m.type || '')]">
                        {{ m.plugintype || m.type || '—' }}
                      </span>
                    </td>
                    <td>
                      <div class="content-tags">
                        <span v-for="c in parseContent(m.content)" :key="c" class="content-tag">{{ contentLabel(c) }}</span>
                        <span v-if="!m.content" class="text-muted text-xs">—</span>
                      </div>
                    </td>
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

          <!-- Permissions / ACL Section -->
          <div class="detail-section">
            <div class="section-header">
              <h4 class="section-title">Permissions</h4>
              <button @click="loadPoolAcl" class="btn btn-outline btn-xs" :disabled="loadingAcl">
                {{ loadingAcl ? 'Loading...' : 'Refresh' }}
              </button>
            </div>
            <div v-if="loadingAcl" class="acl-loading text-sm text-muted">Loading permissions...</div>
            <div v-else-if="poolAclEntries.length === 0" class="acl-empty text-sm text-muted">
              No explicit ACL entries for this pool. Access is controlled by parent datacenter permissions.
            </div>
            <div v-else class="acl-table-wrap">
              <table class="table">
                <thead>
                  <tr>
                    <th>Principal</th>
                    <th>Type</th>
                    <th>Role</th>
                    <th>Propagate</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(entry, idx) in poolAclEntries" :key="idx">
                    <td><strong>{{ entry.ugid || entry.userid || entry.groupid || '—' }}</strong></td>
                    <td>
                      <span :class="['badge', entry.type === 'group' ? 'badge-warning' : 'badge-info']">
                        {{ entry.type === 'group' ? 'Group' : 'User' }}
                      </span>
                    </td>
                    <td>
                      <span class="role-badge">{{ entry.roleid || '—' }}</span>
                    </td>
                    <td>
                      <span :class="['badge', entry.propagate ? 'badge-success' : 'badge-secondary']">
                        {{ entry.propagate ? 'Yes' : 'No' }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="acl-hint text-xs text-muted" style="margin-top:.5rem;">
              To grant access, use the Proxmox VE web UI or manage ACLs via the Access Control view.
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
            <label class="form-label">Pool ID <span class="required">*</span></label>
            <input
              v-model="newPool.poolid"
              class="form-control"
              placeholder="e.g. production"
              required
              pattern="[A-Za-z0-9_\-]+"
              title="Letters, numbers, hyphens and underscores only"
            />
            <p class="form-hint">Letters, numbers, hyphens and underscores only</p>
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

    <!-- ── Add VM Modal ────────────────────────────────────── -->
    <div v-if="showAddVmModal" class="modal-overlay" @click.self="showAddVmModal = false">
      <div class="modal-box modal-wide">
        <div class="modal-header">
          <h3>Add VMs to "{{ selectedPool }}"</h3>
          <button @click="showAddVmModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="search-row">
            <input
              v-model="vmSearch"
              class="form-control"
              placeholder="Filter by VMID or name..."
            />
          </div>
          <div v-if="loadingResources" class="loading-state-sm">Loading VMs...</div>
          <div v-else class="member-select-list">
            <label
              v-for="vm in filteredAvailableVms"
              :key="vm.vmid"
              class="member-check-row"
            >
              <input type="checkbox" :value="vm.vmid" v-model="selectedVmids" />
              <span class="member-check-label">
                <span class="vmid-badge">{{ vm.vmid }}</span>
                <strong class="ml-1">{{ vm.name || 'unnamed' }}</strong>
                <span class="node-badge ml-1">{{ vm.node }}</span>
                <span :class="['badge ml-1', vm.type === 'qemu' ? 'badge-info' : 'badge-warning']" style="font-size:.7rem;">
                  {{ vm.type === 'qemu' ? 'VM' : 'CT' }}
                </span>
                <span :class="['status-dot ml-1', vm.status === 'running' ? 'status-running' : 'status-stopped']" style="font-size:.75rem;">
                  {{ vm.status || 'unknown' }}
                </span>
              </span>
            </label>
            <p v-if="filteredAvailableVms.length === 0 && !loadingResources" class="text-muted text-sm" style="padding: 1rem 0;">
              No VMs available to add.
            </p>
          </div>
          <div class="modal-footer-inline">
            <span class="text-sm text-muted">{{ selectedVmids.length }} selected</span>
            <div class="flex gap-1">
              <button @click="addVms" class="btn btn-primary" :disabled="addingMembers || selectedVmids.length === 0">
                {{ addingMembers ? 'Adding...' : 'Add Selected' }}
              </button>
              <button @click="showAddVmModal = false" class="btn btn-outline">Cancel</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Add Storage Modal ───────────────────────────────── -->
    <div v-if="showAddStorageModal" class="modal-overlay" @click.self="showAddStorageModal = false">
      <div class="modal-box modal-wide">
        <div class="modal-header">
          <h3>Add Storage to "{{ selectedPool }}"</h3>
          <button @click="showAddStorageModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="search-row">
            <input
              v-model="storageSearch"
              class="form-control"
              placeholder="Filter storage..."
            />
          </div>
          <div v-if="loadingResources" class="loading-state-sm">Loading storage...</div>
          <div v-else class="member-select-list">
            <label
              v-for="st in filteredAvailableStorage"
              :key="st.storage + '-' + st.node"
              class="member-check-row"
            >
              <input type="checkbox" :value="st.storage" v-model="selectedStorages" />
              <span class="member-check-label">
                <strong>{{ st.storage }}</strong>
                <span class="node-badge ml-1">{{ st.node }}</span>
                <span :class="['type-badge ml-1', 'type-' + (st.plugintype || st.type || '')]" style="font-size:.7rem;">
                  {{ st.plugintype || st.type || '—' }}
                </span>
              </span>
            </label>
            <p v-if="filteredAvailableStorage.length === 0 && !loadingResources" class="text-muted text-sm" style="padding: 1rem 0;">
              No storage available to add.
            </p>
          </div>
          <div class="modal-footer-inline">
            <span class="text-sm text-muted">{{ selectedStorages.length }} selected</span>
            <div class="flex gap-1">
              <button @click="addStorages" class="btn btn-primary" :disabled="addingMembers || selectedStorages.length === 0">
                {{ addingMembers ? 'Adding...' : 'Add Selected' }}
              </button>
              <button @click="showAddStorageModal = false" class="btn btn-outline">Cancel</button>
            </div>
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

    // Add VM modal
    const showAddVmModal = ref(false)
    const vmSearch = ref('')
    const selectedVmids = ref([])

    // Add Storage modal
    const showAddStorageModal = ref(false)
    const storageSearch = ref('')
    const selectedStorages = ref([])

    // Shared resource loading
    const loadingResources = ref(false)
    const availableVms = ref([])
    const availableStorage = ref([])
    const addingMembers = ref(false)

    // VM action loading
    const vmActionLoading = ref({})

    // Pool ACL
    const poolAclEntries = ref([])
    const loadingAcl = ref(false)

    // Computed members
    const vmMembers = computed(() => {
      if (!poolDetail.value?.members) return []
      return poolDetail.value.members.filter(m => m.type === 'qemu' || m.type === 'lxc')
    })

    const storageMembers = computed(() => {
      if (!poolDetail.value?.members) return []
      return poolDetail.value.members.filter(m => m.type === 'storage')
    })

    const runningVms = computed(() => vmMembers.value.filter(m => m.status === 'running').length)

    const totalCores = computed(() =>
      vmMembers.value.reduce((sum, m) => sum + (m.maxcpu || 0), 0)
    )

    const totalRamMb = computed(() =>
      vmMembers.value.reduce((sum, m) => sum + (m.maxmem ? Math.round(m.maxmem / 1024 / 1024) : 0), 0)
    )

    const filteredAvailableVms = computed(() => {
      if (!vmSearch.value) return availableVms.value
      const q = vmSearch.value.toLowerCase()
      return availableVms.value.filter(vm =>
        String(vm.vmid).includes(q) || (vm.name || '').toLowerCase().includes(q)
      )
    })

    const filteredAvailableStorage = computed(() => {
      if (!storageSearch.value) return availableStorage.value
      const q = storageSearch.value.toLowerCase()
      return availableStorage.value.filter(st =>
        (st.storage || '').toLowerCase().includes(q) || (st.node || '').toLowerCase().includes(q)
      )
    })

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
      poolAclEntries.value = []
      if (selectedHostId.value) fetchPools()
    }

    // Fetch pools list
    const fetchPools = async () => {
      if (!selectedHostId.value) return
      loadingPools.value = true
      try {
        const res = await api.pveNode.listPools(selectedHostId.value)
        // Enrich pool list items with member counts if available
        pools.value = (res.data || []).map(p => ({
          ...p,
          members: p.members || [],
        }))
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
      poolAclEntries.value = []
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
      // Load ACL in background
      loadPoolAcl()
    }

    // Load ACL entries for selected pool
    const loadPoolAcl = async () => {
      if (!selectedPool.value || !selectedHostId.value) return
      loadingAcl.value = true
      try {
        const res = await api.pveNode.listAcl(selectedHostId.value)
        const allAcl = res.data || []
        const poolPath = `/pool/${selectedPool.value}`
        poolAclEntries.value = allAcl
          .filter(e => e.path === poolPath)
          .map(e => ({
            ...e,
            ugid: e.ugid || e.userid || e.groupid || '—',
            type: e.type || (e.userid ? 'user' : 'group'),
          }))
      } catch (e) {
        console.error('Failed to load ACL:', e)
        poolAclEntries.value = []
      } finally {
        loadingAcl.value = false
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
          poolAclEntries.value = []
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
        setTimeout(() => selectPool(selectedPool.value), 2500)
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

    // Load available resources (shared for both modals)
    const loadAvailableResources = async () => {
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

    // Open Add VM modal
    const openAddVm = async () => {
      selectedVmids.value = []
      vmSearch.value = ''
      showAddVmModal.value = true
      await loadAvailableResources()
    }

    // Open Add Storage modal
    const openAddStorage = async () => {
      selectedStorages.value = []
      storageSearch.value = ''
      showAddStorageModal.value = true
      await loadAvailableResources()
    }

    // Submit add VMs
    const addVms = async () => {
      if (selectedVmids.value.length === 0) return
      addingMembers.value = true
      try {
        await api.pveNode.updatePool(selectedHostId.value, selectedPool.value, {
          vms: selectedVmids.value.join(','),
        })
        toast.success(`Added ${selectedVmids.value.length} VM(s) to pool`)
        showAddVmModal.value = false
        await selectPool(selectedPool.value)
      } catch (e) {
        console.error('Failed to add VMs:', e)
        toast.error('Failed to add VMs to pool')
      } finally {
        addingMembers.value = false
      }
    }

    // Submit add storages
    const addStorages = async () => {
      if (selectedStorages.value.length === 0) return
      addingMembers.value = true
      try {
        await api.pveNode.updatePool(selectedHostId.value, selectedPool.value, {
          storage: selectedStorages.value.join(','),
        })
        toast.success(`Added ${selectedStorages.value.length} storage(s) to pool`)
        showAddStorageModal.value = false
        await selectPool(selectedPool.value)
      } catch (e) {
        console.error('Failed to add storage:', e)
        toast.error('Failed to add storage to pool')
      } finally {
        addingMembers.value = false
      }
    }

    // Helpers
    const formatRam = (mb) => {
      if (!mb && mb !== 0) return '—'
      if (mb === 0) return '0 MB'
      if (mb >= 1024) return (mb / 1024).toFixed(mb >= 10240 ? 0 : 1) + ' GB'
      return mb + ' MB'
    }

    const parseContent = (content) => {
      if (!content) return []
      return content.split(',').map(c => c.trim()).filter(Boolean)
    }

    const CONTENT_LABELS = {
      images: 'VM Images',
      rootdir: 'Container Volumes',
      vztmpl: 'CT Templates',
      backup: 'Backups',
      snippets: 'Snippets',
      iso: 'ISO Images',
    }

    const contentLabel = (c) => CONTENT_LABELS[c] || c

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
      totalCores,
      totalRamMb,
      editingComment,
      commentDraft,
      savingComment,
      showCreateModal,
      saving,
      newPool,
      showAddVmModal,
      vmSearch,
      selectedVmids,
      filteredAvailableVms,
      showAddStorageModal,
      storageSearch,
      selectedStorages,
      filteredAvailableStorage,
      loadingResources,
      availableVms,
      availableStorage,
      addingMembers,
      vmActionLoading,
      poolAclEntries,
      loadingAcl,
      onHostChange,
      selectPool,
      loadPoolAcl,
      startEditComment,
      cancelEditComment,
      saveComment,
      createPool,
      deletePool,
      vmAction,
      removeMember,
      openAddVm,
      openAddStorage,
      addVms,
      addStorages,
      formatRam,
      parseContent,
      contentLabel,
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
  color: var(--text-secondary);
  opacity: 0.5;
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
  width: 28%;
  min-width: 200px;
  max-width: 280px;
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
  font-weight: 700;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-secondary);
}

.sidebar-loading,
.sidebar-empty {
  padding: 2rem 1rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.pool-list {
  flex: 1;
  overflow-y: auto;
}

.pool-list-item {
  position: relative;
  padding: 0.75rem 1rem;
  padding-right: 2.25rem;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s;
}

.pool-list-item:hover {
  background: rgba(59, 130, 246, 0.05);
}

.pool-list-item.active {
  background: rgba(59, 130, 246, 0.08);
  border-left: 3px solid var(--primary, #3b82f6);
}

.pool-list-main {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.pool-list-name {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.pool-list-meta {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pool-list-counts {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.2rem;
}

.pool-count-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.7rem;
  color: var(--text-secondary);
  background: rgba(100, 116, 139, 0.1);
  border-radius: 0.25rem;
  padding: 0.1rem 0.35rem;
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
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  gap: 0.5rem;
}

.detail-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem;
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
  gap: 1rem;
}

.detail-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
}

.detail-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
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
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.stat-card {
  flex: 1;
  min-width: 90px;
  background: var(--background, #f9fafb);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.85rem 1rem;
  text-align: center;
}

.stat-card.stat-running {
  background: rgba(16, 185, 129, 0.05);
  border-color: rgba(16, 185, 129, 0.3);
}

.stat-card.stat-cpu {
  background: rgba(59, 130, 246, 0.04);
  border-color: rgba(59, 130, 246, 0.2);
}

.stat-card.stat-ram {
  background: rgba(139, 92, 246, 0.04);
  border-color: rgba(139, 92, 246, 0.2);
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}

.stat-label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-top: 0.2rem;
}

/* Section */
.detail-section {
  margin-bottom: 2rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.section-title {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-secondary);
  margin: 0;
}

/* Node badge */
.node-badge {
  display: inline-block;
  background: rgba(59, 130, 246, 0.1);
  color: #1d4ed8;
  border-radius: 0.25rem;
  padding: 0.1rem 0.4rem;
  font-size: 0.72rem;
  font-weight: 500;
}

/* VMID badge */
.vmid-badge {
  display: inline-block;
  background: rgba(100, 116, 139, 0.12);
  color: var(--text-secondary);
  border-radius: 0.25rem;
  padding: 0.1rem 0.4rem;
  font-size: 0.72rem;
  font-weight: 600;
  font-family: monospace;
}

/* Status dot */
.status-dot {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  font-weight: 500;
}

.status-dot::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.status-running::before { background: #22c55e; }
.status-stopped::before { background: #94a3b8; }
.status-running { color: #15803d; }
.status-stopped { color: #64748b; }

/* Content tags */
.content-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem;
}

.content-tag {
  display: inline-block;
  background: var(--tag-bg, #f1f5f9);
  color: var(--text-secondary, #475569);
  border-radius: 0.25rem;
  padding: 0.1rem 0.4rem;
  font-size: 0.7rem;
  white-space: nowrap;
}

/* Type badges */
.type-badge {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  border-radius: 0.3rem;
  font-size: 0.72rem;
  font-weight: 600;
  background: #e2e8f0;
  color: #475569;
}

.type-zfspool, .type-zfs { background: #dbeafe; color: #1d4ed8; }
.type-dir { background: #d1fae5; color: #065f46; }
.type-lvm, .type-lvmthin { background: #fef3c7; color: #92400e; }
.type-nfs, .type-cifs { background: #ede9fe; color: #5b21b6; }
.type-rbd { background: #fee2e2; color: #991b1b; }

/* Role badge */
.role-badge {
  display: inline-block;
  background: rgba(139, 92, 246, 0.1);
  color: #6d28d9;
  border-radius: 0.25rem;
  padding: 0.1rem 0.45rem;
  font-size: 0.75rem;
  font-weight: 600;
  font-family: monospace;
}

/* ACL section */
.acl-loading, .acl-empty {
  padding: 0.75rem 0;
}

.acl-hint {
  margin-top: 0.5rem;
  font-style: italic;
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
  padding: 1rem;
}

.modal-box {
  background: var(--card-background, #fff);
  border-radius: 0.5rem;
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
}

.modal-box.modal-wide {
  max-width: 620px;
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
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
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.modal-footer-inline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}

.search-row {
  margin-bottom: 0.75rem;
}

/* Member selection list */
.member-select-list {
  flex: 1;
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.5rem;
  margin-bottom: 0;
}

.member-check-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.35rem;
  cursor: pointer;
  border-radius: 0.25rem;
  transition: background 0.1s;
}

.member-check-row:hover {
  background: rgba(59, 130, 246, 0.05);
}

.member-check-label {
  flex: 1;
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.loading-state-sm {
  padding: 1rem;
  color: var(--text-secondary);
  font-size: 0.875rem;
  text-align: center;
}

/* Loading spinner */
.loading-spinner-sm {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary, #3b82f6);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Utilities */
.ml-1 { margin-left: 0.25rem; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.text-muted { color: var(--text-secondary); }
.text-center { text-align: center; }
.required { color: #ef4444; }

/* Form */
.form-group { margin-bottom: 1rem; }
.form-label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 0.35rem;
}
.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.4rem;
  font-size: 0.875rem;
  background: var(--input-bg, #fff);
  color: var(--text-primary);
  box-sizing: border-box;
}
.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}
.form-hint { font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem; }

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
.btn-outline { background: none; border: 1px solid var(--border-color); color: var(--text-primary); }
.btn-outline:hover:not(:disabled) { background: var(--background); }
.btn-danger { background: #ef4444; color: #fff; }
.btn-danger:hover:not(:disabled) { background: #dc2626; }
.btn-success { background: #22c55e; color: #fff; }
.btn-success:hover:not(:disabled) { background: #16a34a; }
.btn-warning { background: #f59e0b; color: #fff; }
.btn-warning:hover:not(:disabled) { background: #d97706; }
.btn-sm { padding: 0.35rem 0.75rem; font-size: 0.8rem; }
.btn-xs { padding: 0.2rem 0.45rem; font-size: 0.75rem; }

/* Table */
.table-container { overflow-x: auto; }
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}
.table th {
  padding: 0.6rem 0.875rem;
  text-align: left;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  background: var(--background, #f9fafb);
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}
.table td {
  padding: 0.65rem 0.875rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: middle;
}
.table tr:last-child td { border-bottom: none; }
.table tr:hover td { background: rgba(59, 130, 246, 0.02); }

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
.badge-info { background: #dbeafe; color: #1d4ed8; }
</style>
