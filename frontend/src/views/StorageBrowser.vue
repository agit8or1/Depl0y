<template>
  <div class="storage-browser-page">
    <div class="page-header mb-2">
      <!-- Breadcrumb navigation -->
      <nav class="breadcrumb-nav" aria-label="breadcrumb">
        <span class="crumb crumb-link" @click="goToHosts">Proxmox Hosts</span>
        <span class="crumb-sep">&rsaquo;</span>
        <span class="crumb crumb-link" @click="goToHost">Host {{ hostId }}</span>
        <span class="crumb-sep">&rsaquo;</span>
        <span class="crumb crumb-link" @click="goToNode">{{ node }}</span>
        <span class="crumb-sep">&rsaquo;</span>
        <template v-if="selectedStorage">
          <span class="crumb crumb-link" @click="clearStorage">Storage</span>
          <span class="crumb-sep">&rsaquo;</span>
          <span class="crumb crumb-current">{{ selectedStorage }}</span>
        </template>
        <template v-else>
          <span class="crumb crumb-current">Storage</span>
        </template>
      </nav>
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

        <!-- Storage stats card -->
        <div v-if="selectedStorage" class="card stats-card mb-3">
          <div class="card-header">
            <h3>Storage Statistics: {{ selectedStorage }}</h3>
            <div class="header-actions">
              <button @click="fetchStats" class="btn btn-outline btn-sm" :disabled="loadingStats">
                {{ loadingStats ? 'Loading…' : 'Refresh' }}
              </button>
            </div>
          </div>
          <div v-if="loadingStats" class="loading-spinner"></div>
          <div v-else-if="storageStats" class="stats-body">
            <!-- Capacity bar -->
            <div class="stats-capacity">
              <div class="stats-capacity-labels">
                <span>Used: <strong>{{ formatBytes(storageStats.used || 0) }}</strong></span>
                <span>Available: <strong>{{ formatBytes(storageStats.avail || 0) }}</strong></span>
                <span>Total: <strong>{{ formatBytes(storageStats.total || 0) }}</strong></span>
              </div>
              <div class="usage-bar-wrap usage-bar-wrap--large">
                <div
                  class="usage-bar-fill"
                  :class="usageBarClass(storageStats)"
                  :style="{ width: usagePct(storageStats) + '%' }"
                ></div>
              </div>
              <div class="text-xs text-muted mt-1">{{ usagePct(storageStats) }}% used</div>
            </div>
            <!-- Content type breakdown -->
            <div class="stats-breakdown">
              <div
                v-for="ct in contentTypeBreakdown"
                :key="ct.label"
                class="stats-breakdown-item"
              >
                <span class="breakdown-count">{{ ct.count }}</span>
                <span class="breakdown-label">{{ ct.label }}</span>
              </div>
            </div>
          </div>
          <div v-else class="text-center text-muted p-3 text-sm">No statistics available.</div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>{{ selectedStorage ? `Contents: ${selectedStorage}` : 'Select a Storage Pool' }}</h3>
            <div class="header-actions">
              <button v-if="selectedStorage" @click="triggerUpload" class="btn btn-primary btn-sm">
                Upload
              </button>
              <button v-if="selectedStorage" @click="fetchContent" class="btn btn-outline btn-sm">
                Refresh
              </button>
            </div>
          </div>

          <!-- Hidden file input -->
          <input
            ref="fileInput"
            type="file"
            style="display: none"
            @change="onFileSelected"
          />

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

            <!-- Sort and pagination controls -->
            <div v-if="!loadingContent && filteredContent.length > 0" class="table-controls">
              <div class="sort-controls">
                <span class="text-xs text-muted">Sort:</span>
                <button
                  v-for="col in sortColumns"
                  :key="col.key"
                  :class="['sort-btn', sortKey === col.key ? 'sort-btn--active' : '']"
                  @click="toggleSort(col.key)"
                >
                  {{ col.label }}
                  <span v-if="sortKey === col.key" class="sort-arrow">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
                </button>
              </div>
              <div class="pagination-meta text-xs text-muted">
                {{ totalItems }} item{{ totalItems !== 1 ? 's' : '' }},
                showing {{ pageStart + 1 }}–{{ pageEnd }} &nbsp;|&nbsp;
                Per page:
                <button
                  v-for="n in pageSizeOptions"
                  :key="n"
                  :class="['page-size-btn', pageSize === n ? 'page-size-btn--active' : '']"
                  @click="setPageSize(n)"
                >{{ n }}</button>
              </div>
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
                  <template v-for="item in pagedContent" :key="item.volid">
                    <tr
                      :class="['content-row', expandedVolid === item.volid ? 'content-row--expanded' : '']"
                      @click="toggleExpand(item)"
                      style="cursor: pointer;"
                    >
                      <td>
                        <div class="vol-name-row">
                          <span class="expand-chevron">{{ expandedVolid === item.volid ? '▾' : '▸' }}</span>
                          <span class="vol-name">{{ volDisplayName(item) }}</span>
                        </div>
                        <div class="text-xs text-muted">{{ item.content }}</div>
                      </td>
                      <td>{{ item.vmid || '—' }}</td>
                      <td>{{ item.format || '—' }}</td>
                      <td>{{ item.size != null ? formatBytes(item.size) : '—' }}</td>
                      <td class="text-sm">{{ item.ctime ? formatDate(item.ctime) : '—' }}</td>
                      <td @click.stop>
                        <div class="row-actions">
                          <button
                            @click="copyVolid(item.volid)"
                            class="btn btn-outline btn-sm btn-icon"
                            title="Copy volume ID"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                          </button>
                          <button @click="openDeleteModal(item)" class="btn btn-danger btn-sm">Delete</button>
                        </div>
                      </td>
                    </tr>
                    <!-- Expanded detail row -->
                    <tr v-if="expandedVolid === item.volid" class="detail-row">
                      <td colspan="6" class="detail-cell">
                        <div class="detail-panel">
                          <component :is="'div'" v-html="renderDetail(item)"></component>
                        </div>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>

              <!-- Pagination controls -->
              <div v-if="totalPages > 1" class="pagination-controls">
                <button class="btn btn-outline btn-sm" :disabled="currentPage === 1" @click="currentPage--">
                  &lsaquo; Prev
                </button>
                <span class="page-info text-sm">Page {{ currentPage }} / {{ totalPages }}</span>
                <button class="btn btn-outline btn-sm" :disabled="currentPage === totalPages" @click="currentPage++">
                  Next &rsaquo;
                </button>
              </div>
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

    <!-- Upload progress modal -->
    <div v-if="uploading" class="modal">
      <div class="modal-content modal-small" @click.stop>
        <div class="modal-header">
          <h3>Uploading File</h3>
        </div>
        <div class="modal-body">
          <p class="upload-filename">{{ uploadFileName }}</p>
          <div class="progress-bar-wrap">
            <div class="progress-bar-fill" :style="{ width: uploadProgress + '%' }"></div>
          </div>
          <div class="progress-label">{{ uploadProgress }}%</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '@/services/api'
import { formatBytes } from '@/utils/proxmox'

const route = useRoute()
const router = useRouter()
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

const fileInput = ref(null)
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadFileName = ref('')

// Expanded row state
const expandedVolid = ref(null)

// Storage stats
const storageStats = ref(null)
const loadingStats = ref(false)

// Sort state
const sortKey = ref('name')
const sortDir = ref('asc')
const sortColumns = [
  { key: 'name', label: 'Name' },
  { key: 'size', label: 'Size' },
  { key: 'ctime', label: 'Date' },
  { key: 'content', label: 'Type' },
]

// Pagination state
const currentPage = ref(1)
const pageSize = ref(25)
const pageSizeOptions = [25, 50, 100]

const contentFilters = [
  { label: 'All', value: '' },
  { label: 'ISO', value: 'iso' },
  { label: 'Backup', value: 'backup' },
  { label: 'Template', value: 'vztmpl' },
  { label: 'Disk Image', value: 'images' },
]

// ── Computed ──────────────────────────────────────────────────────────────────

const filteredContent = computed(() => {
  let list = contentFilter.value
    ? contentList.value.filter(item => item.content === contentFilter.value)
    : contentList.value.slice()

  // Sort
  list = list.slice().sort((a, b) => {
    let va, vb
    if (sortKey.value === 'name') {
      va = volDisplayName(a).toLowerCase()
      vb = volDisplayName(b).toLowerCase()
    } else if (sortKey.value === 'size') {
      va = a.size ?? -1
      vb = b.size ?? -1
    } else if (sortKey.value === 'ctime') {
      va = a.ctime ?? 0
      vb = b.ctime ?? 0
    } else if (sortKey.value === 'content') {
      va = (a.content || '').toLowerCase()
      vb = (b.content || '').toLowerCase()
    } else {
      va = ''
      vb = ''
    }
    if (va < vb) return sortDir.value === 'asc' ? -1 : 1
    if (va > vb) return sortDir.value === 'asc' ? 1 : -1
    return 0
  })

  return list
})

const totalItems = computed(() => filteredContent.value.length)
const totalPages = computed(() => Math.max(1, Math.ceil(totalItems.value / pageSize.value)))
const pageStart = computed(() => (currentPage.value - 1) * pageSize.value)
const pageEnd = computed(() => Math.min(pageStart.value + pageSize.value, totalItems.value))

const pagedContent = computed(() =>
  filteredContent.value.slice(pageStart.value, pageEnd.value)
)

const contentTypeBreakdown = computed(() => {
  const map = { iso: 0, backup: 0, vztmpl: 0, images: 0 }
  for (const item of contentList.value) {
    if (item.content in map) map[item.content]++
  }
  return [
    { label: 'ISOs', count: map.iso },
    { label: 'Backups', count: map.backup },
    { label: 'Templates', count: map.vztmpl },
    { label: 'Disk Images', count: map.images },
  ]
})

// ── Helpers ───────────────────────────────────────────────────────────────────

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

/**
 * Build an HTML string for the expandable detail panel based on content type.
 * We avoid a child component to keep the file self-contained.
 */
function renderDetail(item) {
  const rows = []
  const ct = item.content || ''
  const name = volDisplayName(item)

  const row = (label, value) =>
    `<div class="detail-row-item"><span class="detail-label">${label}</span><span class="detail-value">${value}</span></div>`

  // Full volid always shown
  rows.push(row('Volume ID', `<code class="detail-code">${escHtml(item.volid)}</code>`))

  if (ct === 'iso') {
    // ISO details
    if (item.size != null) rows.push(row('File Size', formatBytes(item.size)))
    if (item.ctime) rows.push(row('Created', formatDate(item.ctime)))
    if (item.format) rows.push(row('Format', escHtml(item.format)))
    const ext = name.split('.').pop().toLowerCase()
    rows.push(row('Type', ext === 'iso' ? 'ISO 9660 disc image' : escHtml(ext.toUpperCase())))
  } else if (ct === 'images') {
    // Disk image details
    if (item.format) rows.push(row('Disk Format', escHtml(item.format.toUpperCase())))
    if (item.size != null) rows.push(row('Virtual Size', formatBytes(item.size)))
    if (item.vmid) rows.push(row('Assigned VM', escHtml(String(item.vmid))))
    if (item.parent) rows.push(row('Backing File', `<code class="detail-code">${escHtml(item.parent)}</code>`))
    else rows.push(row('Backing File', 'None (base image)'))
    if (item.ctime) rows.push(row('Created', formatDate(item.ctime)))
  } else if (ct === 'backup') {
    // VM backup details
    if (item.vmid) rows.push(row('Source VMID', escHtml(String(item.vmid))))
    if (item.ctime) rows.push(row('Created', formatDate(item.ctime)))
    if (item.size != null) rows.push(row('Backup Size', formatBytes(item.size)))
    if (item.format) rows.push(row('Format', escHtml(item.format)))
    if (item.notes) rows.push(row('Notes', escHtml(item.notes)))
    // Parse info from filename (e.g. vzdump-qemu-113-2025_01_01-12_00_00.vma.zst)
    const match = name.match(/vzdump-(qemu|lxc)-(\d+)-(\d{4}_\d{2}_\d{2}-\d{2}_\d{2}_\d{2})/)
    if (match) {
      rows.push(row('Guest Type', match[1] === 'qemu' ? 'QEMU/KVM VM' : 'LXC Container'))
      const ts = match[3].replace(/_/g, (c, i) => i === 10 ? ' ' : (i < 10 ? '_' : ':'))
      rows.push(row('Timestamp', escHtml(ts)))
    }
  } else if (ct === 'vztmpl') {
    // LXC template details
    if (item.size != null) rows.push(row('Archive Size', formatBytes(item.size)))
    if (item.ctime) rows.push(row('Created', formatDate(item.ctime)))
    // Parse distribution/arch from filename (e.g. debian-12-standard_12.7-1_amd64.tar.zst)
    const archMatch = name.match(/_(amd64|i386|arm64|armhf|arm7|x86_64)/)
    if (archMatch) rows.push(row('Architecture', archMatch[1]))
    const distroMatch = name.match(/^([a-zA-Z]+)-/)
    if (distroMatch) {
      const distro = distroMatch[1].charAt(0).toUpperCase() + distroMatch[1].slice(1)
      rows.push(row('Distribution', escHtml(distro)))
    }
    const verMatch = name.match(/^[a-zA-Z]+-(\d[\d.]*)/)
    if (verMatch) rows.push(row('Version', escHtml(verMatch[1])))
  } else {
    // Fallback: show whatever fields exist
    if (item.size != null) rows.push(row('Size', formatBytes(item.size)))
    if (item.ctime) rows.push(row('Created', formatDate(item.ctime)))
    if (item.format) rows.push(row('Format', escHtml(item.format)))
  }

  return `<div class="detail-grid">${rows.join('')}</div>`
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// ── Sort / Pagination ─────────────────────────────────────────────────────────

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
  currentPage.value = 1
}

function setPageSize(n) {
  pageSize.value = n
  currentPage.value = 1
}

// ── Expand row ────────────────────────────────────────────────────────────────

function toggleExpand(item) {
  expandedVolid.value = expandedVolid.value === item.volid ? null : item.volid
}

// ── Breadcrumb navigation ─────────────────────────────────────────────────────

function goToHosts() {
  router.push({ name: 'PveHosts' }).catch(() => router.push('/pve'))
}

function goToHost() {
  router.push({ name: 'PveHostDetail', params: { hostId: hostId.value } })
    .catch(() => router.push(`/pve/${hostId.value}`))
}

function goToNode() {
  router.push({ name: 'PveNode', params: { hostId: hostId.value, node: node.value } })
    .catch(() => router.push(`/pve/${hostId.value}/nodes/${node.value}`))
}

function clearStorage() {
  selectedStorage.value = null
  contentList.value = []
  storageStats.value = null
  expandedVolid.value = null
  currentPage.value = 1
}

// ── Data fetching ─────────────────────────────────────────────────────────────

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

async function fetchStats() {
  if (!selectedStorage.value) return
  loadingStats.value = true
  try {
    const res = await api.pveNode.listStorage(hostId.value, node.value)
    const all = res.data || []
    storageStats.value = all.find(s => s.storage === selectedStorage.value) || null
  } catch (err) {
    console.error('Failed to load storage stats:', err)
  } finally {
    loadingStats.value = false
  }
}

async function fetchContent() {
  if (!selectedStorage.value) return
  loadingContent.value = true
  expandedVolid.value = null
  currentPage.value = 1
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
  storageStats.value = null
  expandedVolid.value = null
  currentPage.value = 1
  fetchContent()
  fetchStats()
}

function setFilter(val) {
  contentFilter.value = val
  currentPage.value = 1
  expandedVolid.value = null
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

function triggerUpload() {
  if (fileInput.value) {
    fileInput.value.value = ''
    fileInput.value.click()
  }
}

async function onFileSelected(event) {
  const file = event.target.files[0]
  if (!file) return

  uploadFileName.value = file.name
  uploadProgress.value = 0
  uploading.value = true

  try {
    const formData = new FormData()
    formData.append('filename', file)

    const ext = file.name.split('.').pop().toLowerCase()
    if (ext === 'iso') formData.append('content', 'iso')
    else if (ext === 'tar' || ext === 'gz' || file.name.includes('.tar.')) formData.append('content', 'vztmpl')

    const onProgress = (evt) => {
      if (evt.total) uploadProgress.value = Math.round((evt.loaded * 100) / evt.total)
    }

    await api.pveNode.uploadToStorage(
      hostId.value,
      node.value,
      selectedStorage.value,
      formData,
      onProgress
    )

    uploadProgress.value = 100
    toast.success(`${file.name} uploaded successfully`)
    await fetchContent()
  } catch (err) {
    console.error('Failed to upload file:', err)
    toast.error('Upload failed: ' + (err?.response?.data?.detail || err.message || 'Unknown error'))
  } finally {
    uploading.value = false
    uploadFileName.value = ''
    uploadProgress.value = 0
  }
}

async function copyVolid(volid) {
  try {
    await navigator.clipboard.writeText(volid)
    toast.success('Volume ID copied to clipboard')
  } catch (err) {
    console.error('Failed to copy to clipboard:', err)
    toast.error('Failed to copy to clipboard')
  }
}

onMounted(async () => {
  await fetchStorage()
  if (selectedStorage.value) {
    await fetchContent()
    await fetchStats()
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

/* ── Breadcrumb ─────────────────────────────────────────────── */
.breadcrumb-nav {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.125rem;
  font-size: 0.8rem;
  margin-bottom: 0.4rem;
  color: var(--text-muted, #888);
}

.crumb-sep {
  color: var(--text-muted, #888);
  padding: 0 0.2rem;
  user-select: none;
}

.crumb-link {
  cursor: pointer;
  color: var(--primary-color, #6366f1);
  transition: color 0.15s, text-decoration 0.15s;
}

.crumb-link:hover {
  text-decoration: underline;
  color: var(--primary-hover, #818cf8);
}

.crumb-current {
  color: var(--text-primary);
  font-weight: 600;
}

/* ── Layout ─────────────────────────────────────────────────── */
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

.mb-3 { margin-bottom: 1rem; }

/* ── Storage list ───────────────────────────────────────────── */
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

.usage-bar-wrap--large {
  height: 10px;
  margin-top: 0.5rem;
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

/* ── Stats card ─────────────────────────────────────────────── */
.stats-card .card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stats-body {
  padding: 1rem 1.25rem 1.25rem;
}

.stats-capacity-labels {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  font-size: 0.85rem;
  color: var(--text-muted, #888);
}

.stats-capacity-labels strong {
  color: var(--text-primary);
}

.stats-breakdown {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 1rem;
  border-top: 1px solid var(--border-color);
  padding-top: 0.875rem;
}

.stats-breakdown-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 70px;
  background: var(--bg-secondary);
  border-radius: 0.375rem;
  padding: 0.5rem 0.75rem;
}

.breakdown-count {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.breakdown-label {
  font-size: 0.75rem;
  color: var(--text-muted, #888);
  margin-top: 0.125rem;
}

/* ── Content tabs ───────────────────────────────────────────── */
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

/* ── Sort / pagination toolbar ──────────────────────────────── */
.table-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
  font-size: 0.8rem;
}

.sort-controls {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.sort-btn {
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 0.25rem;
  padding: 0.2rem 0.5rem;
  font-size: 0.78rem;
  cursor: pointer;
  color: var(--text-muted, #888);
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.sort-btn:hover {
  color: var(--text-primary);
  border-color: var(--primary-color, #6366f1);
}

.sort-btn--active {
  color: var(--primary-color, #6366f1);
  border-color: var(--primary-color, #6366f1);
  background: rgba(99, 102, 241, 0.1);
  font-weight: 600;
}

.sort-arrow {
  margin-left: 0.2rem;
}

.pagination-meta {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.page-size-btn {
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 0.25rem;
  padding: 0.15rem 0.4rem;
  font-size: 0.78rem;
  cursor: pointer;
  color: var(--text-muted, #888);
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.page-size-btn:hover {
  color: var(--text-primary);
  border-color: var(--primary-color, #6366f1);
}

.page-size-btn--active {
  color: var(--primary-color, #6366f1);
  border-color: var(--primary-color, #6366f1);
  background: rgba(99, 102, 241, 0.1);
  font-weight: 600;
}

/* ── Table ──────────────────────────────────────────────────── */
.vol-name-row {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.expand-chevron {
  color: var(--text-muted, #888);
  font-size: 0.75rem;
  flex-shrink: 0;
  transition: color 0.15s;
}

.content-row:hover .expand-chevron {
  color: var(--primary-color, #6366f1);
}

.content-row--expanded {
  background: rgba(99, 102, 241, 0.06);
}

.vol-name {
  font-weight: 500;
  word-break: break-all;
}

/* ── Expandable detail row ──────────────────────────────────── */
.detail-row td {
  padding: 0 !important;
}

.detail-cell {
  background: var(--bg-secondary);
  border-bottom: 2px solid var(--primary-color, #6366f1);
}

.detail-panel {
  padding: 0.75rem 1.25rem 1rem;
}

/* These classes are injected via v-html, so they must NOT be scoped.
   We use :deep() to punch through the scoping. */
:deep(.detail-grid) {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 2rem;
}

:deep(.detail-row-item) {
  display: flex;
  flex-direction: column;
  min-width: 160px;
}

:deep(.detail-label) {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #888);
  margin-bottom: 0.15rem;
}

:deep(.detail-value) {
  font-size: 0.85rem;
  color: var(--text-primary);
  word-break: break-all;
}

:deep(.detail-code) {
  display: inline-block;
  padding: 0.1rem 0.35rem;
  background: var(--bg-card, #1a1a2e);
  border: 1px solid var(--border-color);
  border-radius: 0.25rem;
  font-size: 0.78rem;
  word-break: break-all;
  color: var(--text-primary);
}

/* ── Pagination controls ────────────────────────────────────── */
.pagination-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-top: 1px solid var(--border-color);
}

.page-info {
  color: var(--text-muted, #888);
  min-width: 90px;
  text-align: center;
}

/* ── Misc helpers ───────────────────────────────────────────── */
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

.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.row-actions {
  display: flex;
  gap: 0.375rem;
  align-items: center;
}

.btn-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.25rem 0.375rem;
}

.progress-bar-wrap {
  height: 10px;
  background: var(--border-color);
  border-radius: 5px;
  overflow: hidden;
  margin: 0.75rem 0 0.375rem;
}

.progress-bar-fill {
  height: 100%;
  background: var(--primary-color, #6366f1);
  border-radius: 5px;
  transition: width 0.2s;
}

.progress-label {
  text-align: right;
  font-size: 0.85rem;
  color: var(--text-muted, #888);
}

.upload-filename {
  font-weight: 500;
  color: var(--text-primary);
  word-break: break-all;
  margin: 0;
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

/* ── Modals ─────────────────────────────────────────────────── */
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
