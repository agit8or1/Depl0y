<template>
  <div class="storage-browser-page">
    <div class="page-header mb-2">
      <div class="breadcrumb text-sm text-muted mb-1">
        Proxmox Hosts &rsaquo; Host {{ hostId }} &rsaquo; {{ node }} &rsaquo; Storage
      </div>
      <h2>Storage Browser</h2>
      <p class="text-muted">Browse storage pools on node <strong>{{ node }}</strong></p>
    </div>

    <div class="two-panel-layout">
      <!-- Left panel: Storage list -->
      <div class="panel-left">
        <div class="card">
          <div class="card-header">
            <h3>Storage Pools</h3>
          </div>
          <div v-if="loadingStorage" class="loading-spinner"></div>
          <div v-else-if="storageList.length === 0" class="text-center text-muted p-3">
            No storage pools found.
          </div>
          <div v-else class="storage-list">
            <div
              v-for="s in storageList"
              :key="s.storage"
              :class="['storage-item', selectedStorage === s.storage ? 'storage-item--active' : '']"
              @click="selectStorage(s.storage)"
            >
              <div class="storage-item-header">
                <span class="storage-name">{{ s.storage }}</span>
                <span class="badge badge-info">{{ s.type }}</span>
              </div>
              <div v-if="s.total && s.total > 0" class="storage-usage">
                <div class="usage-bar-wrap">
                  <div
                    class="usage-bar-fill"
                    :class="usageBarClass(s)"
                    :style="{ width: usagePct(s) + '%' }"
                  ></div>
                </div>
                <div class="text-xs text-muted">
                  {{ formatBytes(s.used || 0) }} / {{ formatBytes(s.total) }}
                  ({{ usagePct(s) }}%)
                </div>
              </div>
              <div v-else class="text-xs text-muted mt-1">No usage data</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right panel: Content browser -->
      <div class="panel-right">
        <div class="card">
          <div class="card-header">
            <h3>{{ selectedStorage ? `Contents: ${selectedStorage}` : 'Select a Storage Pool' }}</h3>
            <button v-if="selectedStorage" @click="fetchContent" class="btn btn-outline btn-sm">
              Refresh
            </button>
          </div>

          <div v-if="!selectedStorage" class="text-center text-muted p-4">
            Select a storage pool from the left panel to browse its contents.
          </div>

          <template v-else>
            <!-- Filter tabs -->
            <div class="content-tabs">
              <button
                v-for="tab in contentFilters"
                :key="tab.value"
                :class="['content-tab', contentFilter === tab.value ? 'content-tab--active' : '']"
                @click="setFilter(tab.value)"
              >{{ tab.label }}</button>
            </div>

            <div v-if="loadingContent" class="loading-spinner"></div>

            <div v-else-if="filteredContent.length === 0" class="text-center text-muted p-3">
              No items found{{ contentFilter ? ` for "${contentFilter}"` : '' }}.
            </div>

            <div v-else class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>VMID</th>
                    <th>Format</th>
                    <th>Size</th>
                    <th>Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in filteredContent" :key="item.volid">
                    <td>
                      <span class="vol-name">{{ volDisplayName(item) }}</span>
                      <div class="text-xs text-muted">{{ item.content }}</div>
                    </td>
                    <td>{{ item.vmid || '—' }}</td>
                    <td>{{ item.format || '—' }}</td>
                    <td>{{ item.size != null ? formatBytes(item.size) : '—' }}</td>
                    <td class="text-sm">{{ item.ctime ? formatDate(item.ctime) : '—' }}</td>
                    <td>
                      <button @click="openDeleteModal(item)" class="btn btn-danger btn-sm">Delete</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Delete confirmation modal -->
    <div v-if="deleteTarget" class="modal" @click="deleteTarget = null">
      <div class="modal-content modal-small" @click.stop>
        <div class="modal-header">
          <h3>Confirm Delete</h3>
          <button @click="deleteTarget = null" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <p>Are you sure you want to delete this volume?</p>
          <code class="volid-code">{{ deleteTarget.volid }}</code>
          <p class="text-sm text-muted mt-1">This action cannot be undone.</p>
          <div class="flex gap-1 mt-2">
            <button @click="doDeleteVolume" class="btn btn-danger" :disabled="deleting">
              {{ deleting ? 'Deleting...' : 'Delete' }}
            </button>
            <button @click="deleteTarget = null" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import { formatBytes } from '@/utils/proxmox'

const route = useRoute()
const toast = useToast()

const hostId = ref(route.params.hostId)
const node = ref(route.params.node)

const storageList = ref([])
const loadingStorage = ref(false)
const selectedStorage = ref(route.query.storage || null)

const contentList = ref([])
const loadingContent = ref(false)
const contentFilter = ref('')

const deleteTarget = ref(null)
const deleting = ref(false)

const contentFilters = [
  { label: 'All', value: '' },
  { label: 'ISO', value: 'iso' },
  { label: 'Backup', value: 'backup' },
  { label: 'Template', value: 'vztmpl' },
  { label: 'Disk Image', value: 'images' },
]

const filteredContent = computed(() => {
  if (!contentFilter.value) return contentList.value
  return contentList.value.filter(item => item.content === contentFilter.value)
})

function usagePct(s) {
  if (!s.total || s.total === 0) return 0
  return Math.min(100, Math.round(((s.used || 0) / s.total) * 100))
}

function usageBarClass(s) {
  const pct = usagePct(s)
  if (pct >= 90) return 'fill--danger'
  if (pct >= 75) return 'fill--warning'
  return 'fill--ok'
}

function volDisplayName(item) {
  if (!item.volid) return '—'
  const parts = item.volid.split(':')
  const vol = parts.length > 1 ? parts[1] : item.volid
  const segments = vol.split('/')
  return segments[segments.length - 1]
}

function formatDate(epoch) {
  if (!epoch) return '—'
  return new Date(epoch * 1000).toLocaleString()
}

async function fetchStorage() {
  loadingStorage.value = true
  try {
    const res = await api.pveNode.listStorage(hostId.value, node.value)
    storageList.value = res.data || []
  } catch (err) {
    console.error('Failed to load storage list:', err)
    toast.error('Failed to load storage list')
  } finally {
    loadingStorage.value = false
  }
}

async function fetchContent() {
  if (!selectedStorage.value) return
  loadingContent.value = true
  try {
    const params = contentFilter.value ? { content: contentFilter.value } : {}
    const res = await api.pveNode.browseStorage(hostId.value, node.value, selectedStorage.value, params)
    contentList.value = res.data || []
  } catch (err) {
    console.error('Failed to load storage content:', err)
    toast.error('Failed to load storage content')
  } finally {
    loadingContent.value = false
  }
}

function selectStorage(name) {
  selectedStorage.value = name
  contentFilter.value = ''
  fetchContent()
}

function setFilter(val) {
  contentFilter.value = val
  fetchContent()
}

function openDeleteModal(item) {
  deleteTarget.value = item
}

async function doDeleteVolume() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    const volid = encodeURIComponent(deleteTarget.value.volid)
    await api.pveNode.deleteVolume(hostId.value, node.value, selectedStorage.value, volid)
    toast.success('Volume deleted')
    deleteTarget.value = null
    await fetchContent()
  } catch (err) {
    console.error('Failed to delete volume:', err)
    toast.error('Failed to delete volume')
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  await fetchStorage()
  if (selectedStorage.value) {
    await fetchContent()
  }
})
</script>

<style scoped>
.storage-browser-page {
  padding: 0;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.breadcrumb {
  margin-bottom: 0.25rem;
}

.two-panel-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 1.5rem;
  align-items: start;
}

.panel-left,
.panel-right {
  min-width: 0;
}

.storage-list {
  padding: 0.5rem;
}

.storage-item {
  padding: 0.75rem 0.875rem;
  border-radius: 0.375rem;
  cursor: pointer;
  margin-bottom: 0.375rem;
  border: 1px solid var(--border-color);
  transition: border-color 0.15s, background 0.15s;
}

.storage-item:hover {
  background: var(--bg-secondary);
  border-color: var(--primary-color, #6366f1);
}

.storage-item--active {
  border-color: var(--primary-color, #6366f1);
  background: rgba(99, 102, 241, 0.1);
}

.storage-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.storage-name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 0.9rem;
}

.storage-usage {
  margin-top: 0.25rem;
}

.usage-bar-wrap {
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.25rem;
}

.usage-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.fill--ok { background: #10b981; }
.fill--warning { background: #f59e0b; }
.fill--danger { background: #ef4444; }

.content-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  padding: 0 0.5rem;
  flex-wrap: wrap;
}

.content-tab {
  background: none;
  border: none;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  color: var(--text-muted, #888);
  font-size: 0.85rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s;
}

.content-tab:hover {
  color: var(--text-primary);
}

.content-tab--active {
  color: var(--primary-color, #6366f1);
  border-bottom-color: var(--primary-color, #6366f1);
  font-weight: 600;
}

.vol-name {
  font-weight: 500;
  word-break: break-all;
}

.volid-code {
  display: block;
  margin-top: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--bg-secondary);
  border-radius: 0.375rem;
  font-size: 0.8rem;
  word-break: break-all;
  color: var(--text-primary);
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.75rem; }
.p-3 { padding: 1.5rem; }
.p-4 { padding: 2rem; }
.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.text-muted { color: var(--text-muted, #888); }
.text-center { text-align: center; }
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }

.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card, #1a1a2e);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-content.modal-small {
  max-width: 440px;
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
  color: var(--text-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.75rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body {
  padding: 1.5rem;
  color: var(--text-primary);
}

@media (max-width: 900px) {
  .two-panel-layout {
    grid-template-columns: 1fr;
  }
}
</style>
