<template>
  <div class="vm-groups-page">
    <div class="groups-layout">
      <!-- ── Left Sidebar ──────────────────────────────────────────────── -->
      <aside class="groups-sidebar">
        <div class="sidebar-header">
          <h3>VM Groups</h3>
        </div>

        <!-- All VMs -->
        <div
          :class="['sidebar-item', selectedView.type === 'all' ? 'sidebar-item-active' : '']"
          @click="selectAll"
        >
          <span class="sidebar-item-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/></svg>
          </span>
          <span class="sidebar-item-label">All VMs</span>
          <span class="sidebar-count">{{ allVMs.length }}</span>
        </div>

        <!-- By Tag section -->
        <div class="sidebar-section-header">By Tag</div>
        <div v-if="tagsLoading" class="sidebar-loading">Loading…</div>
        <div v-else-if="allTags.length === 0" class="sidebar-empty">No tags found</div>
        <div
          v-for="tagEntry in allTags"
          :key="tagEntry.tag"
          :class="['sidebar-item', selectedView.type === 'tag' && selectedView.value === tagEntry.tag ? 'sidebar-item-active' : '']"
          @click="selectTag(tagEntry.tag)"
        >
          <span class="tag-dot" :style="{ backgroundColor: tagColor(tagEntry.tag) }"></span>
          <span class="sidebar-item-label">{{ tagEntry.tag }}</span>
          <span class="sidebar-count">{{ tagEntry.count }}</span>
        </div>

        <!-- My Groups section -->
        <div class="sidebar-section-header" style="margin-top: 0.75rem;">My Groups</div>
        <div v-if="groupsLoading" class="sidebar-loading">Loading…</div>
        <div v-else-if="groups.length === 0" class="sidebar-empty">No groups yet</div>
        <div
          v-for="group in groups"
          :key="group.id"
          :class="['sidebar-item', 'sidebar-item-group', selectedView.type === 'group' && selectedView.value === group.id ? 'sidebar-item-active' : '']"
          :style="{ borderLeftColor: group.color }"
          @click="selectGroup(group)"
        >
          <span class="sidebar-item-label" style="flex: 1;">{{ group.name }}</span>
          <span class="sidebar-count">{{ group.vmids.length }}</span>
          <button class="icon-btn" title="Edit" @click.stop="openEditGroupModal(group)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="icon-btn icon-btn-danger" title="Delete" @click.stop="confirmDeleteGroup(group)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>
          </button>
        </div>

        <!-- Create Group Button -->
        <div style="padding: 1rem;">
          <button class="btn btn-primary" style="width: 100%;" @click="openCreateGroupModal">
            + Create Group
          </button>
        </div>
      </aside>

      <!-- ── Main Panel ─────────────────────────────────────────────────── -->
      <main class="groups-main">
        <!-- All VMs view -->
        <div v-if="selectedView.type === 'all'">
          <div class="main-header">
            <h2>All VMs</h2>
            <span class="text-muted text-sm">{{ filteredMainVMs.length }} VM{{ filteredMainVMs.length !== 1 ? 's' : '' }} across {{ hostCount }} host{{ hostCount !== 1 ? 's' : '' }}</span>
          </div>
          <VMTable :vms="filteredMainVMs" :loading="vmsLoading" @edit-tags="openTagEditor" />
        </div>

        <!-- Tag view -->
        <div v-else-if="selectedView.type === 'tag'">
          <div class="main-header">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <span class="tag-badge" :style="{ backgroundColor: tagColor(selectedView.value) }">{{ selectedView.value }}</span>
              <h2 style="margin: 0;">Tag: {{ selectedView.value }}</h2>
            </div>
            <span class="text-muted text-sm">{{ tagVMs.length }} VM{{ tagVMs.length !== 1 ? 's' : '' }}</span>
          </div>

          <!-- Tag management panel -->
          <div class="tag-mgmt-panel card" style="margin-bottom: 1rem;">
            <div class="tag-mgmt-row">
              <div class="form-group" style="flex: 1; margin: 0;">
                <label class="text-sm font-medium">Rename tag across all VMs</label>
                <div style="display: flex; gap: 0.5rem; margin-top: 0.25rem;">
                  <input v-model="renameTagInput" type="text" class="form-control" :placeholder="selectedView.value"
                    @input="renameTagInput = renameTagInput.toLowerCase().replace(/[^a-z0-9\-_]/g, '')" />
                  <button class="btn btn-primary btn-sm" @click="renameTag" :disabled="!renameTagInput.trim() || renameTagInput === selectedView.value || tagOpRunning">
                    {{ tagOpRunning ? 'Renaming…' : 'Rename' }}
                  </button>
                </div>
              </div>
              <div class="form-group" style="flex: 1; margin: 0;">
                <label class="text-sm font-medium">Merge tag into another</label>
                <div style="display: flex; gap: 0.5rem; margin-top: 0.25rem;">
                  <select v-model="mergeTagTarget" class="form-control">
                    <option value="">Select target tag…</option>
                    <option v-for="t in allTags.filter(e => e.tag !== selectedView.value)" :key="t.tag" :value="t.tag">{{ t.tag }}</option>
                  </select>
                  <button class="btn btn-secondary btn-sm" @click="mergeTag" :disabled="!mergeTagTarget || tagOpRunning">
                    {{ tagOpRunning ? 'Merging…' : 'Merge' }}
                  </button>
                </div>
              </div>
              <div style="display: flex; align-items: flex-end; padding-bottom: 0.1rem;">
                <button class="btn btn-danger btn-sm" @click="deleteTag" :disabled="tagOpRunning">
                  Delete Tag
                </button>
              </div>
            </div>
          </div>

          <VMTable :vms="tagVMs" :loading="tagVMsLoading" @edit-tags="openTagEditor" />
        </div>

        <!-- Group view -->
        <div v-else-if="selectedView.type === 'group' && selectedGroup">
          <div class="main-header">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <span class="group-color-dot" :style="{ backgroundColor: selectedGroup.color }"></span>
              <h2 style="margin: 0;">{{ selectedGroup.name }}</h2>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <span class="text-muted text-sm">{{ groupVMs.length }} member VM{{ groupVMs.length !== 1 ? 's' : '' }}</span>
              <button class="btn btn-outline btn-sm" @click="openEditGroupModal(selectedGroup)">Edit Group</button>
            </div>
          </div>

          <div v-if="selectedGroup.description" class="group-description">{{ selectedGroup.description }}</div>

          <VMTable :vms="groupVMs" :loading="vmsLoading" @edit-tags="openTagEditor" />
        </div>
      </main>
    </div>

    <!-- ── Group Create/Edit Modal ────────────────────────────────────── -->
    <div v-if="showGroupModal" class="modal-overlay" @click.self="closeGroupModal">
      <div class="modal-content modal-wide" @click.stop>
        <div class="modal-header">
          <h3>{{ editingGroup ? 'Edit Group' : 'Create Group' }}</h3>
          <button @click="closeGroupModal" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-grid">
            <div class="form-group">
              <label>Name <span class="text-danger">*</span></label>
              <input v-model="groupForm.name" type="text" class="form-control" placeholder="e.g. Production Servers" maxlength="100" />
            </div>
            <div class="form-group">
              <label>Color</label>
              <div class="color-palette">
                <button
                  v-for="c in colorPalette"
                  :key="c"
                  :class="['color-swatch', groupForm.color === c ? 'color-swatch-active' : '']"
                  :style="{ backgroundColor: c }"
                  @click="groupForm.color = c"
                  :title="c"
                ></button>
              </div>
            </div>
          </div>
          <div class="form-group">
            <label>Description</label>
            <input v-model="groupForm.description" type="text" class="form-control" placeholder="Optional description" maxlength="500" />
          </div>

          <!-- VM multi-selector -->
          <div class="form-group">
            <label>Member VMs</label>
            <input v-model="vmSelectorSearch" type="text" class="form-control" placeholder="Search VMs by name or VMID…" style="margin-bottom: 0.5rem;" />
            <div class="vm-selector-list">
              <div v-if="vmsLoading" class="text-muted text-sm" style="padding: 0.5rem;">Loading VMs…</div>
              <label
                v-for="vm in filteredSelectorVMs"
                :key="`${vm.hostId}-${vm.node}-${vm.vmid}`"
                class="vm-selector-row"
              >
                <input
                  type="checkbox"
                  :value="String(vm.vmid)"
                  v-model="groupForm.vmids"
                />
                <span class="vm-selector-info">
                  <strong>{{ vm.vmid }}</strong> — {{ vm.name || '(no name)' }}
                  <span class="text-muted text-sm"> / {{ vm.node }} / {{ vm.hostName }}</span>
                </span>
                <span :class="['badge', vm.status === 'running' ? 'badge-success' : 'badge-danger']" style="font-size: 0.65rem;">{{ vm.status }}</span>
              </label>
              <div v-if="filteredSelectorVMs.length === 0 && !vmsLoading" class="text-muted text-sm" style="padding: 0.5rem;">No VMs found.</div>
            </div>
            <div class="text-muted text-sm" style="margin-top: 0.25rem;">{{ groupForm.vmids.length }} VM{{ groupForm.vmids.length !== 1 ? 's' : '' }} selected</div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeGroupModal" class="btn btn-secondary" :disabled="groupSaving">Cancel</button>
          <button @click="saveGroup" class="btn btn-primary" :disabled="groupSaving || !groupForm.name.trim()">
            {{ groupSaving ? 'Saving…' : (editingGroup ? 'Save Changes' : 'Create Group') }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Tag Editor Modal ───────────────────────────────────────────── -->
    <div v-if="showTagEditorModal" class="modal-overlay" @click.self="closeTagEditor">
      <div class="modal-content" @click.stop style="max-width: 420px;">
        <div class="modal-header">
          <h3>Edit Tags — VM {{ tagEditorVm?.vmid }} ({{ tagEditorVm?.name || '' }})</h3>
          <button @click="closeTagEditor" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="vm-tags" style="margin-bottom: 0.75rem; min-height: 2rem;">
            <span
              v-for="tag in tagEditorTags"
              :key="tag"
              class="vm-tag-pill"
              :style="{ backgroundColor: tagColor(tag), cursor: 'pointer' }"
              @click="removeTagFromEditor(tag)"
              title="Click to remove"
            >{{ tag }} ×</span>
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
        </div>
        <div class="modal-footer">
          <button @click="closeTagEditor" class="btn btn-secondary" :disabled="tagEditorSaving">Cancel</button>
          <button @click="saveTagEditor" class="btn btn-primary" :disabled="tagEditorSaving">
            {{ tagEditorSaving ? 'Saving…' : 'Save Tags' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Delete Group Confirm ───────────────────────────────────────── -->
    <div v-if="showDeleteGroupModal" class="modal-overlay" @click.self="showDeleteGroupModal = false">
      <div class="modal-content" @click.stop style="max-width: 380px;">
        <div class="modal-header">
          <h3>Delete Group</h3>
          <button @click="showDeleteGroupModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p class="text-danger">Delete group <strong>"{{ groupToDelete?.name }}"</strong>? This cannot be undone. VMs are not affected.</p>
        </div>
        <div class="modal-footer">
          <button @click="showDeleteGroupModal = false" class="btn btn-secondary">Cancel</button>
          <button @click="deleteGroup" class="btn btn-danger" :disabled="groupSaving">
            {{ groupSaving ? 'Deleting…' : 'Delete Group' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

// ── Inner VMTable component ──────────────────────────────────────────────────
const VMTable = {
  name: 'VMTable',
  props: {
    vms: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
  },
  emits: ['edit-tags'],
  setup(props, { emit }) {
    const tagColorPalette = [
      '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
      '#ef4444', '#06b6d4', '#84cc16', '#f97316',
    ]
    const tagColor = (tag) => {
      let hash = 0
      for (let i = 0; i < tag.length; i++) hash = tag.charCodeAt(i) + ((hash << 5) - hash)
      return tagColorPalette[Math.abs(hash) % tagColorPalette.length]
    }
    const parseTags = (s) => (s || '').split(';').map(t => t.trim()).filter(Boolean)
    const formatBytes = (b) => {
      if (!b) return '—'
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(b) / Math.log(1024))
      return Math.round((b / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
    }
    const statusClass = (s) => ({ running: 'badge-success', stopped: 'badge-danger', paused: 'badge-warning' }[(s || '').toLowerCase()] || 'badge-info')
    return { tagColor, parseTags, formatBytes, statusClass, emit }
  },
  template: `
    <div>
      <div v-if="loading" class="loading-spinner"></div>
      <div v-else-if="vms.length === 0" class="text-muted text-sm" style="padding: 2rem; text-align: center;">No VMs to display.</div>
      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>VMID</th><th>Name</th><th>Status</th><th>Node</th><th>Host</th><th>CPU/RAM</th><th>Tags</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="vm in vms" :key="vm.vmid + '-' + vm.node + '-' + vm.hostId">
              <td><strong>{{ vm.vmid }}</strong></td>
              <td>{{ vm.name || '(no name)' }}</td>
              <td><span :class="['badge', statusClass(vm.status)]">{{ vm.status }}</span></td>
              <td><span class="badge badge-info">{{ vm.node }}</span></td>
              <td class="text-sm">{{ vm.hostName }}</td>
              <td class="text-sm">{{ vm.cpus || '?' }} CPU / {{ formatBytes(vm.maxmem) }}</td>
              <td>
                <div class="vm-tags">
                  <span v-for="tag in parseTags(vm.tags)" :key="tag" class="vm-tag-pill" :style="{ backgroundColor: tagColor(tag) }">{{ tag }}</span>
                  <span v-if="!parseTags(vm.tags).length" class="text-muted text-sm">—</span>
                </div>
              </td>
              <td>
                <button class="btn btn-outline btn-sm" @click="emit('edit-tags', vm)">Tags</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  `
}

export default {
  name: 'VMGroups',
  components: { VMTable },
  setup() {
    const toast = useToast()

    // ── Color palette ───────────────────────────────────────────────────
    const colorPalette = [
      '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
      '#ef4444', '#06b6d4', '#84cc16', '#f97316',
    ]

    const tagColorPalette = colorPalette
    const tagColor = (tag) => {
      let hash = 0
      for (let i = 0; i < tag.length; i++) hash = tag.charCodeAt(i) + ((hash << 5) - hash)
      return tagColorPalette[Math.abs(hash) % tagColorPalette.length]
    }

    const parseTags = (s) => (s || '').split(';').map(t => t.trim()).filter(Boolean)

    // ── Data state ──────────────────────────────────────────────────────
    const allVMs = ref([])
    const vmsLoading = ref(false)
    const allTags = ref([])
    const tagsLoading = ref(false)
    const groups = ref([])
    const groupsLoading = ref(false)
    const hosts = ref([])

    // ── Sidebar selection ───────────────────────────────────────────────
    const selectedView = ref({ type: 'all', value: null })
    const selectedGroup = ref(null)

    const selectAll = () => {
      selectedView.value = { type: 'all', value: null }
      selectedGroup.value = null
    }

    const selectTag = (tag) => {
      selectedView.value = { type: 'tag', value: tag }
      selectedGroup.value = null
      loadTagVMs(tag)
      renameTagInput.value = ''
      mergeTagTarget.value = ''
    }

    const selectGroup = (group) => {
      selectedView.value = { type: 'group', value: group.id }
      selectedGroup.value = group
    }

    // ── Computed VM lists ───────────────────────────────────────────────
    const hostCount = computed(() => new Set(allVMs.value.map(v => v.hostId)).size)

    const filteredMainVMs = computed(() => allVMs.value)

    const tagVMs = ref([])
    const tagVMsLoading = ref(false)

    const loadTagVMs = async (tag) => {
      tagVMsLoading.value = true
      tagVMs.value = []
      // Filter locally from allVMs
      tagVMs.value = allVMs.value.filter(vm => parseTags(vm.tags).includes(tag))
      tagVMsLoading.value = false
    }

    const groupVMs = computed(() => {
      if (!selectedGroup.value) return []
      const ids = new Set(selectedGroup.value.vmids.map(String))
      return allVMs.value.filter(vm => ids.has(String(vm.vmid)))
    })

    // ── Fetch data ──────────────────────────────────────────────────────
    const fetchVMs = async () => {
      vmsLoading.value = true
      try {
        const hostsResp = await api.proxmox.listHosts()
        hosts.value = hostsResp.data || []
        const results = []
        await Promise.allSettled(
          hosts.value.map(async (host) => {
            try {
              const res = await api.pveNode.clusterResources(host.id, 'vm')
              const items = Array.isArray(res.data) ? res.data : (res.data?.data || [])
              items.forEach(item => {
                if (item.type && item.type !== 'qemu') return
                results.push({
                  hostId: host.id,
                  hostName: host.name || String(host.id),
                  node: item.node,
                  vmid: item.vmid,
                  name: item.name,
                  status: item.status || 'unknown',
                  cpus: item.cpus,
                  maxmem: item.maxmem,
                  tags: item.tags || '',
                  _busy: false,
                })
              })
            } catch (e) {
              console.warn(`Failed to fetch VMs for host ${host.id}:`, e)
            }
          })
        )
        allVMs.value = results
        // Refresh tag VMs if viewing a tag
        if (selectedView.value.type === 'tag') {
          loadTagVMs(selectedView.value.value)
        }
      } catch (e) {
        console.error('Failed to fetch hosts:', e)
        toast.error('Failed to load VMs')
      } finally {
        vmsLoading.value = false
      }
    }

    const fetchTags = async () => {
      if (!hosts.value.length) return
      tagsLoading.value = true
      const tagMap = {}
      try {
        allVMs.value.forEach(vm => {
          parseTags(vm.tags).forEach(t => {
            tagMap[t] = (tagMap[t] || 0) + 1
          })
        })
        allTags.value = Object.entries(tagMap).sort((a, b) => a[0].localeCompare(b[0])).map(([tag, count]) => ({ tag, count }))
      } finally {
        tagsLoading.value = false
      }
    }

    const fetchGroups = async () => {
      groupsLoading.value = true
      try {
        const res = await api.vmGroups.list()
        groups.value = res.data || []
        // Refresh selectedGroup if editing
        if (selectedGroup.value) {
          const refreshed = groups.value.find(g => g.id === selectedGroup.value.id)
          if (refreshed) selectedGroup.value = refreshed
        }
      } catch (e) {
        console.error('Failed to fetch groups:', e)
      } finally {
        groupsLoading.value = false
      }
    }

    // Watch allVMs to recompute tags
    watch(allVMs, () => {
      fetchTags()
    })

    onMounted(async () => {
      await fetchVMs()
      await fetchGroups()
    })

    // ── Tag operations ──────────────────────────────────────────────────
    const renameTagInput = ref('')
    const mergeTagTarget = ref('')
    const tagOpRunning = ref(false)

    const renameTag = async () => {
      const oldTag = selectedView.value.value
      const newTag = renameTagInput.value.trim()
      if (!newTag || newTag === oldTag) return
      if (!confirm(`Rename tag "${oldTag}" to "${newTag}" across all ${tagVMs.value.length} VMs?`)) return
      tagOpRunning.value = true
      let ok = 0, fail = 0
      for (const vm of tagVMs.value) {
        try {
          const tags = parseTags(vm.tags).map(t => t === oldTag ? newTag : t)
          await api.pveVm.updateConfig(vm.hostId, vm.node, vm.vmid, { tags: tags.join(';') })
          vm.tags = tags.join(';')
          ok++
        } catch (e) {
          fail++
        }
      }
      tagOpRunning.value = false
      toast.success(`Renamed tag on ${ok} VMs${fail ? `, ${fail} failed` : ''}`)
      await fetchVMs()
      selectTag(newTag)
    }

    const mergeTag = async () => {
      const srcTag = selectedView.value.value
      const dstTag = mergeTagTarget.value
      if (!dstTag) return
      const affected = allVMs.value.filter(vm => parseTags(vm.tags).includes(srcTag))
      if (!confirm(`Merge tag "${srcTag}" into "${dstTag}" across ${affected.length} VMs? "${srcTag}" will be removed.`)) return
      tagOpRunning.value = true
      let ok = 0, fail = 0
      for (const vm of affected) {
        try {
          let tags = parseTags(vm.tags)
          tags = tags.filter(t => t !== srcTag)
          if (!tags.includes(dstTag)) tags.push(dstTag)
          await api.pveVm.updateConfig(vm.hostId, vm.node, vm.vmid, { tags: tags.join(';') })
          vm.tags = tags.join(';')
          ok++
        } catch (e) {
          fail++
        }
      }
      tagOpRunning.value = false
      toast.success(`Merged tag on ${ok} VMs${fail ? `, ${fail} failed` : ''}`)
      await fetchVMs()
      selectTag(dstTag)
    }

    const deleteTag = async () => {
      const tag = selectedView.value.value
      const affected = allVMs.value.filter(vm => parseTags(vm.tags).includes(tag))
      if (!confirm(`Remove tag "${tag}" from all ${affected.length} VMs? This cannot be undone.`)) return
      tagOpRunning.value = true
      let ok = 0, fail = 0
      for (const vm of affected) {
        try {
          const tags = parseTags(vm.tags).filter(t => t !== tag)
          await api.pveVm.updateConfig(vm.hostId, vm.node, vm.vmid, { tags: tags.join(';') })
          vm.tags = tags.join(';')
          ok++
        } catch (e) {
          fail++
        }
      }
      tagOpRunning.value = false
      toast.success(`Removed tag from ${ok} VMs${fail ? `, ${fail} failed` : ''}`)
      await fetchVMs()
      selectAll()
    }

    // ── Group modal ─────────────────────────────────────────────────────
    const showGroupModal = ref(false)
    const editingGroup = ref(null)
    const groupForm = ref({ name: '', description: '', color: '#3b82f6', vmids: [] })
    const groupSaving = ref(false)
    const vmSelectorSearch = ref('')

    const filteredSelectorVMs = computed(() => {
      const q = vmSelectorSearch.value.trim().toLowerCase()
      if (!q) return allVMs.value
      return allVMs.value.filter(vm =>
        (vm.name || '').toLowerCase().includes(q) ||
        String(vm.vmid).includes(q) ||
        (vm.node || '').toLowerCase().includes(q)
      )
    })

    const openCreateGroupModal = () => {
      editingGroup.value = null
      groupForm.value = { name: '', description: '', color: '#3b82f6', vmids: [] }
      vmSelectorSearch.value = ''
      showGroupModal.value = true
    }

    const openEditGroupModal = (group) => {
      editingGroup.value = group
      groupForm.value = {
        name: group.name,
        description: group.description || '',
        color: group.color || '#3b82f6',
        vmids: [...group.vmids.map(String)],
      }
      vmSelectorSearch.value = ''
      showGroupModal.value = true
    }

    const closeGroupModal = () => {
      showGroupModal.value = false
      editingGroup.value = null
    }

    const saveGroup = async () => {
      groupSaving.value = true
      try {
        const data = {
          name: groupForm.value.name.trim(),
          description: groupForm.value.description.trim() || null,
          color: groupForm.value.color,
          vmids: groupForm.value.vmids,
        }
        if (editingGroup.value) {
          await api.vmGroups.update(editingGroup.value.id, data)
          toast.success('Group updated')
        } else {
          await api.vmGroups.create(data)
          toast.success('Group created')
        }
        await fetchGroups()
        closeGroupModal()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to save group')
      } finally {
        groupSaving.value = false
      }
    }

    // ── Delete group ────────────────────────────────────────────────────
    const showDeleteGroupModal = ref(false)
    const groupToDelete = ref(null)

    const confirmDeleteGroup = (group) => {
      groupToDelete.value = group
      showDeleteGroupModal.value = true
    }

    const deleteGroup = async () => {
      groupSaving.value = true
      try {
        await api.vmGroups.delete(groupToDelete.value.id)
        toast.success('Group deleted')
        if (selectedGroup.value?.id === groupToDelete.value.id) selectAll()
        await fetchGroups()
        showDeleteGroupModal.value = false
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to delete group')
      } finally {
        groupSaving.value = false
      }
    }

    // ── Inline tag editor ───────────────────────────────────────────────
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
        await api.pveVm.updateConfig(vm.hostId, vm.node, vm.vmid, {
          tags: tagEditorTags.value.join(';'),
        })
        vm.tags = tagEditorTags.value.join(';')
        toast.success(`Tags saved for VM ${vm.vmid}`)
        closeTagEditor()
        fetchTags()
        if (selectedView.value.type === 'tag') loadTagVMs(selectedView.value.value)
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to save tags')
      } finally {
        tagEditorSaving.value = false
      }
    }

    return {
      colorPalette, tagColor,
      allVMs, vmsLoading, allTags, tagsLoading, groups, groupsLoading,
      selectedView, selectedGroup, hostCount,
      filteredMainVMs, tagVMs, tagVMsLoading, groupVMs,
      selectAll, selectTag, selectGroup,
      renameTagInput, mergeTagTarget, tagOpRunning, renameTag, mergeTag, deleteTag,
      showGroupModal, editingGroup, groupForm, groupSaving, vmSelectorSearch,
      filteredSelectorVMs, openCreateGroupModal, openEditGroupModal, closeGroupModal, saveGroup,
      showDeleteGroupModal, groupToDelete, confirmDeleteGroup, deleteGroup,
      showTagEditorModal, tagEditorVm, tagEditorTags, tagEditorInput, tagEditorSaving,
      openTagEditor, closeTagEditor, addTagFromEditor, removeTagFromEditor, saveTagEditor,
    }
  }
}
</script>

<style scoped>
/* ── Page Layout ─────────────────────────────────────────────────────────── */
.vm-groups-page {
  height: calc(100vh - 4rem);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.groups-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
  gap: 0;
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
.groups-sidebar {
  width: 260px;
  min-width: 220px;
  max-width: 300px;
  border-right: 1px solid var(--border, #e2e8f0);
  background: var(--surface);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 1rem 1rem 0.5rem;
  border-bottom: 1px solid var(--border, #e2e8f0);
}

.sidebar-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.sidebar-section-header {
  padding: 0.6rem 1rem 0.2rem;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, #64748b);
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 1rem;
  cursor: pointer;
  border-radius: 0;
  transition: background 0.1s;
  font-size: 0.875rem;
  color: var(--text-primary);
}

.sidebar-item:hover {
  background: var(--background);
}

.sidebar-item-active {
  background: rgba(59, 130, 246, 0.1);
  color: var(--primary-color, #3b82f6);
  font-weight: 600;
}

.sidebar-item-group {
  border-left: 3px solid transparent;
  padding-left: calc(1rem - 3px);
}

.sidebar-item-icon {
  flex-shrink: 0;
  color: var(--text-muted);
}

.sidebar-item-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-count {
  flex-shrink: 0;
  font-size: 0.7rem;
  background: var(--background);
  color: var(--text-muted);
  border-radius: 9999px;
  padding: 0.1rem 0.4rem;
  font-weight: 600;
}

.tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.sidebar-loading, .sidebar-empty {
  padding: 0.4rem 1rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.15rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  border-radius: 0.25rem;
}

.icon-btn:hover {
  background: var(--background);
  color: var(--text-primary);
}

.icon-btn-danger:hover {
  color: #ef4444;
}

/* ── Main Panel ──────────────────────────────────────────────────────────── */
.groups-main {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
  background: var(--background);
}

.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.main-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.tag-badge {
  display: inline-block;
  padding: 0.2rem 0.7rem;
  border-radius: 9999px;
  color: #fff;
  font-size: 0.875rem;
  font-weight: 600;
}

.group-color-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}

.group-description {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
  padding: 0.5rem 0.75rem;
  background: var(--surface);
  border-radius: 0.375rem;
  border: 1px solid var(--border, #e2e8f0);
}

/* ── Tag management panel ──────────────────────────────────────────────── */
.tag-mgmt-panel {
  padding: 0.75rem 1rem;
}

.tag-mgmt-row {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  flex-wrap: wrap;
}

/* ── Modals ──────────────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--surface);
  border-radius: 0.5rem;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  max-width: 520px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-wide {
  max-width: 700px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border, #e2e8f0);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.75rem;
  line-height: 1;
  cursor: pointer;
  color: var(--text-muted);
  padding: 0;
  width: 1.75rem;
  height: 1.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-close:hover { color: var(--text-primary); }

.modal-body {
  padding: 1.25rem 1.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border, #e2e8f0);
}

/* ── Form helpers ────────────────────────────────────────────────────────── */
.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 0.35rem;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

.form-control {
  width: 100%;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 0.375rem;
  background: var(--background);
  color: var(--text-primary);
  font-size: 0.875rem;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
}

/* ── Color palette ────────────────────────────────────────────────────────── */
.color-palette {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.25rem;
}

.color-swatch {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  transition: transform 0.1s;
}

.color-swatch:hover {
  transform: scale(1.15);
}

.color-swatch-active {
  border-color: var(--text-primary, #1e293b);
  box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--text-primary, #1e293b);
}

/* ── VM Selector ─────────────────────────────────────────────────────────── */
.vm-selector-list {
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 0.375rem;
  max-height: 260px;
  overflow-y: auto;
}

.vm-selector-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  cursor: pointer;
  border-bottom: 1px solid var(--border, #e2e8f0);
  font-size: 0.875rem;
}

.vm-selector-row:last-child {
  border-bottom: none;
}

.vm-selector-row:hover {
  background: var(--background);
}

.vm-selector-info {
  flex: 1;
}

/* ── Tags display ────────────────────────────────────────────────────────── */
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

/* ── Shared ──────────────────────────────────────────────────────────────── */
.text-danger { color: #ef4444; }
.text-muted { color: var(--text-muted, #64748b); }
.text-sm { font-size: 0.8rem; }
.font-medium { font-weight: 500; }
.btn-sm { padding: 0.25rem 0.5rem; font-size: 0.8rem; }

.card {
  background: var(--surface);
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 0.5rem;
  padding: 1rem;
}

@media (max-width: 768px) {
  .groups-layout {
    flex-direction: column;
  }
  .groups-sidebar {
    width: 100%;
    max-width: none;
    border-right: none;
    border-bottom: 1px solid var(--border, #e2e8f0);
    max-height: 35vh;
  }
  .tag-mgmt-row {
    flex-direction: column;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
