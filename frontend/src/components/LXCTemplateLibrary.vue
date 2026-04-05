<template>
  <div class="lxc-template-library">
    <!-- Search bar -->
    <div class="library-search-bar">
      <input
        v-model="searchQuery"
        type="text"
        class="form-control"
        placeholder="Search templates..."
      />
    </div>

    <!-- Tab switcher -->
    <div class="library-tabs">
      <button
        type="button"
        :class="['lib-tab', { active: activeTab === 'local' }]"
        @click="activeTab = 'local'"
      >
        Local Templates
        <span v-if="localTemplates.length" class="tab-count">{{ localTemplates.length }}</span>
      </button>
      <button
        type="button"
        :class="['lib-tab', { active: activeTab === 'available' }]"
        @click="activeTab = 'available'; loadAvailable()"
      >
        Available for Download
        <span v-if="availableTemplates.length" class="tab-count">{{ availableTemplates.length }}</span>
      </button>
    </div>

    <!-- ======================== LOCAL TAB ======================== -->
    <div v-if="activeTab === 'local'" class="tab-pane">
      <div v-if="loadingLocal" class="lib-loading">
        <div class="lib-spinner"></div>
        <span>Loading local templates...</span>
      </div>
      <div v-else-if="filteredLocal.length === 0" class="lib-empty">
        <div class="lib-empty-icon">📦</div>
        <p>No local templates found.</p>
        <p class="lib-empty-sub">Upload a template or download one from the Available tab.</p>
      </div>
      <div v-else class="template-grid">
        <div
          v-for="tmpl in filteredLocal"
          :key="tmpl.volid"
          :class="['template-card', { selected: selectedVolid === tmpl.volid }]"
        >
          <div class="template-card-icon">{{ tmpl._os.icon }}</div>
          <div class="template-card-body">
            <div class="template-card-name">{{ tmpl._displayName }}</div>
            <div class="template-card-meta">
              <span class="os-badge" :style="{ borderColor: tmpl._os.color, color: tmpl._os.color }">
                {{ tmpl._os.name }}
              </span>
              <span class="meta-tag">{{ tmpl._storage }}</span>
              <span v-if="tmpl.size" class="meta-tag">{{ formatBytes(tmpl.size) }}</span>
            </div>
            <div v-if="tmpl.ctime" class="template-card-date">
              Added {{ formatDate(tmpl.ctime) }}
            </div>
          </div>
          <div class="template-card-actions">
            <button
              type="button"
              class="btn btn-sm btn-primary"
              @click="selectTemplate(tmpl)"
            >Use</button>
            <button
              type="button"
              class="btn btn-sm btn-danger-outline"
              :disabled="deletingVolid === tmpl.volid"
              @click="deleteTemplate(tmpl)"
              title="Delete template"
            >
              <span v-if="deletingVolid === tmpl.volid">...</span>
              <span v-else>Delete</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ======================== AVAILABLE TAB ======================== -->
    <div v-if="activeTab === 'available'" class="tab-pane">
      <!-- Category filter -->
      <div class="available-filters">
        <div class="category-pills">
          <button
            type="button"
            :class="['cat-pill', { active: categoryFilter === 'all' }]"
            @click="categoryFilter = 'all'"
          >All</button>
          <button
            v-for="cat in categories"
            :key="cat"
            type="button"
            :class="['cat-pill', { active: categoryFilter === cat }]"
            @click="categoryFilter = cat"
          >{{ cat }}</button>
        </div>
      </div>

      <div v-if="loadingAvailable" class="lib-loading">
        <div class="lib-spinner"></div>
        <span>Loading available templates...</span>
      </div>
      <div v-else-if="filteredAvailable.length === 0" class="lib-empty">
        <div class="lib-empty-icon">🌐</div>
        <p>No templates found for current filter.</p>
      </div>
      <div v-else class="available-table-wrap">
        <table class="available-table">
          <thead>
            <tr>
              <th>OS</th>
              <th>Package</th>
              <th>Version</th>
              <th>Section</th>
              <th>Size</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tmpl in filteredAvailable" :key="tmpl.package">
              <td class="os-icon-cell">
                <span :title="tmpl._os.name">{{ tmpl._os.icon }}</span>
              </td>
              <td>
                <div class="pkg-name">{{ tmpl.package }}</div>
                <div v-if="tmpl.infopage" class="pkg-info-link">
                  <a :href="tmpl.infopage" target="_blank" rel="noopener">Info page</a>
                </div>
              </td>
              <td class="text-sm">{{ tmpl.version }}</td>
              <td class="text-sm">
                <span class="section-badge">{{ tmpl.section }}</span>
              </td>
              <td class="text-sm">{{ formatTemplateSize(tmpl.size) }}</td>
              <td>
                <div class="avail-actions">
                  <span
                    v-if="isDownloaded(tmpl.package)"
                    class="downloaded-badge"
                  >Downloaded</span>
                  <button
                    v-else-if="downloadingPkg === tmpl.package"
                    type="button"
                    class="btn btn-sm btn-outline"
                    disabled
                  >
                    <span class="btn-spinner-sm"></span> Downloading...
                  </button>
                  <button
                    v-else
                    type="button"
                    class="btn btn-sm btn-primary"
                    :disabled="!targetStorage || downloadingPkg !== null"
                    @click="downloadTemplate(tmpl)"
                  >Download</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Target storage selector -->
      <div v-if="storages.length > 0" class="target-storage-row">
        <label class="form-label">Download to storage:</label>
        <select v-model="targetStorage" class="form-control" style="width:auto;display:inline-block;margin-left:0.5rem">
          <option v-for="s in storages" :key="s.storage" :value="s.storage">{{ s.storage }}</option>
        </select>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/services/api'
import { detectOs, templateDisplayName, formatTemplateSize } from '@/utils/osIcons'

export default {
  name: 'LXCTemplateLibrary',

  props: {
    hostId: { type: [Number, String], required: true },
    node: { type: String, required: true },
    storages: { type: Array, default: () => [] }, // storages with vztmpl content
  },

  emits: ['select'],

  data() {
    return {
      activeTab: 'local',
      searchQuery: '',
      categoryFilter: 'all',

      localTemplates: [],
      availableTemplates: [],

      loadingLocal: false,
      loadingAvailable: false,
      availableLoaded: false,

      selectedVolid: '',
      deletingVolid: '',
      downloadingPkg: null,

      targetStorage: '',
    }
  },

  computed: {
    filteredLocal() {
      const q = this.searchQuery.toLowerCase()
      return this.localTemplates.filter(t =>
        !q || t._displayName.toLowerCase().includes(q) || t._os.name.toLowerCase().includes(q)
      )
    },

    filteredAvailable() {
      const q = this.searchQuery.toLowerCase()
      return this.availableTemplates.filter(t => {
        const matchSearch = !q || t.package.toLowerCase().includes(q) || (t.version || '').toLowerCase().includes(q)
        const matchCat = this.categoryFilter === 'all' || t.section === this.categoryFilter
        return matchSearch && matchCat
      })
    },

    categories() {
      const cats = [...new Set(this.availableTemplates.map(t => t.section).filter(Boolean))]
      return cats.sort()
    },

    downloadedPackages() {
      return new Set(this.localTemplates.map(t => {
        // Extract package name from volid filename
        const fname = (t.volid || '').split('/').pop() || ''
        // e.g. ubuntu-22.04-standard_22.04-1_amd64.tar.zst → extract up to first part
        return fname.replace(/\.(tar\.gz|tar\.xz|tar\.zst|tar\.bz2)$/, '')
      }))
    },
  },

  watch: {
    storages: {
      handler(val) {
        if (val.length && !this.targetStorage) {
          this.targetStorage = val[0].storage
        }
      },
      immediate: true,
    },
  },

  async mounted() {
    await this.loadLocal()
  },

  methods: {
    formatTemplateSize,

    async loadLocal() {
      if (!this.hostId || !this.node) return
      this.loadingLocal = true
      const all = []
      try {
        const tmplStorages = this.storages.filter(s => s.content?.includes('vztmpl'))
        for (const stor of tmplStorages) {
          try {
            const r = await api.pveNode.listStorageTemplates(this.hostId, this.node, stor.storage)
            const items = Array.isArray(r.data) ? r.data : []
            for (const item of items) {
              const fname = (item.volid || '').split('/').pop() || ''
              all.push({
                ...item,
                _storage: stor.storage,
                _os: detectOs(fname),
                _displayName: templateDisplayName(item.volid),
              })
            }
          } catch (e) {
            console.warn(`Cannot list templates on ${stor.storage}:`, e)
          }
        }
        this.localTemplates = all
      } finally {
        this.loadingLocal = false
      }
    },

    async loadAvailable() {
      if (this.availableLoaded || this.loadingAvailable) return
      this.loadingAvailable = true
      try {
        const r = await api.pveNode.listAvailableTemplates(this.hostId, this.node)
        const items = Array.isArray(r.data) ? r.data : []
        this.availableTemplates = items.map(t => ({
          ...t,
          _os: detectOs(t.package || ''),
        }))
        this.availableLoaded = true
      } catch (e) {
        console.error('Failed to load available templates:', e)
      } finally {
        this.loadingAvailable = false
      }
    },

    isDownloaded(pkg) {
      // Check if any local template filename starts with the package name
      return this.localTemplates.some(t => {
        const fname = (t.volid || '').split('/').pop() || ''
        return fname.startsWith(pkg.replace(/:/g, '_'))
      })
    },

    selectTemplate(tmpl) {
      this.selectedVolid = tmpl.volid
      this.$emit('select', {
        volid: tmpl.volid,
        os: tmpl._os,
        displayName: tmpl._displayName,
        storage: tmpl._storage,
      })
    },

    async deleteTemplate(tmpl) {
      if (!confirm(`Delete template "${tmpl._displayName}"?`)) return
      this.deletingVolid = tmpl.volid
      try {
        // volid is like "local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst"
        // The delete endpoint expects storage + volid path
        const [storage, volPath] = tmpl.volid.split(':')
        await api.pveNode.deleteVolume(this.hostId, this.node, storage, encodeURIComponent(tmpl.volid))
        this.localTemplates = this.localTemplates.filter(t => t.volid !== tmpl.volid)
        if (this.selectedVolid === tmpl.volid) {
          this.selectedVolid = ''
          this.$emit('select', null)
        }
      } catch (e) {
        console.error('Failed to delete template:', e)
        alert('Failed to delete template: ' + (e.response?.data?.detail || e.message))
      } finally {
        this.deletingVolid = ''
      }
    },

    async downloadTemplate(tmpl) {
      if (!this.targetStorage) {
        alert('Please select a storage to download to.')
        return
      }
      this.downloadingPkg = tmpl.package
      try {
        await api.pveNode.downloadTemplate(this.hostId, this.node, {
          storage: this.targetStorage,
          template: tmpl.package,
        })
        // After triggering download, reload local list after a short delay
        setTimeout(() => this.loadLocal(), 3000)
      } catch (e) {
        console.error('Failed to download template:', e)
        alert('Failed to start download: ' + (e.response?.data?.detail || e.message))
      } finally {
        this.downloadingPkg = null
      }
    },

    formatBytes(bytes) {
      if (!bytes) return '—'
      const gb = bytes / (1024 * 1024 * 1024)
      if (gb >= 1) return gb.toFixed(2) + ' GB'
      return (bytes / (1024 * 1024)).toFixed(0) + ' MB'
    },

    formatDate(ts) {
      if (!ts) return ''
      return new Date(ts * 1000).toLocaleDateString()
    },
  },
}
</script>

<style scoped>
.lxc-template-library { display: flex; flex-direction: column; gap: 1rem; }

/* Search */
.library-search-bar { margin-bottom: 0.25rem; }

/* Tabs */
.library-tabs {
  display: flex;
  gap: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
  width: fit-content;
  margin-bottom: 0.25rem;
}
.lib-tab {
  padding: 0.5rem 1.25rem;
  border: none;
  background: none;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.lib-tab.active { background: #14b8a6; color: white; }
.lib-tab:not(.active):hover { background: rgba(20,184,166,0.1); color: #14b8a6; }
.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.25rem;
  height: 1.25rem;
  padding: 0 0.3rem;
  border-radius: 9999px;
  font-size: 0.7rem;
  font-weight: 700;
  background: rgba(255,255,255,0.25);
  color: inherit;
}
.lib-tab.active .tab-count { background: rgba(255,255,255,0.3); }
.lib-tab:not(.active) .tab-count { background: rgba(20,184,166,0.15); color: #14b8a6; }

/* Loading / empty states */
.lib-loading { display: flex; align-items: center; gap: 0.75rem; color: var(--text-secondary); padding: 2rem; }
.lib-spinner {
  width: 20px; height: 20px;
  border: 2px solid var(--border-color);
  border-top-color: #14b8a6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}
.lib-empty { text-align: center; padding: 2.5rem 1rem; color: var(--text-secondary); }
.lib-empty-icon { font-size: 2.5rem; margin-bottom: 0.5rem; }
.lib-empty p { margin: 0.25rem 0; }
.lib-empty-sub { font-size: 0.8rem; }

/* Local templates grid */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.75rem;
}
.template-card {
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.875rem;
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  background: var(--background);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.template-card.selected {
  border-color: #14b8a6;
  box-shadow: 0 0 0 3px rgba(20,184,166,0.15);
}
.template-card:hover { border-color: #14b8a6; }
.template-card-icon { font-size: 1.75rem; flex-shrink: 0; margin-top: 0.1rem; }
.template-card-body { flex: 1; min-width: 0; }
.template-card-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
  word-break: break-all;
  margin-bottom: 0.3rem;
}
.template-card-meta { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.25rem; }
.os-badge {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  border: 1px solid currentColor;
}
.meta-tag {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  background: rgba(0,0,0,0.05);
  color: var(--text-secondary);
}
.template-card-date { font-size: 0.7rem; color: var(--text-secondary); }
.template-card-actions {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  flex-shrink: 0;
}

.btn-danger-outline {
  background: none;
  border: 1px solid #ef4444;
  color: #ef4444;
  padding: 0.25rem 0.6rem;
  border-radius: 0.25rem;
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-danger-outline:hover:not(:disabled) { background: #fee2e2; }
.btn-danger-outline:disabled { opacity: 0.5; cursor: not-allowed; }

/* Available tab */
.available-filters { margin-bottom: 0.75rem; }
.category-pills { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.cat-pill {
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 9999px;
  background: none;
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--text-secondary);
  transition: all 0.2s;
}
.cat-pill.active { background: #14b8a6; border-color: #14b8a6; color: white; }
.cat-pill:not(.active):hover { border-color: #14b8a6; color: #14b8a6; }

.available-table-wrap { overflow-x: auto; }
.available-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.available-table th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 2px solid var(--border-color);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.available-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: middle;
}
.available-table tbody tr:hover { background: rgba(20,184,166,0.04); }
.os-icon-cell { font-size: 1.25rem; }
.pkg-name { font-weight: 500; color: var(--text-primary); }
.pkg-info-link a { font-size: 0.75rem; color: #14b8a6; text-decoration: none; }
.pkg-info-link a:hover { text-decoration: underline; }
.section-badge {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  background: rgba(20,184,166,0.1);
  color: #0d9488;
  font-size: 0.75rem;
  font-weight: 500;
}
.avail-actions { display: flex; align-items: center; gap: 0.5rem; }
.downloaded-badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  background: #d1fae5;
  color: #065f46;
  font-size: 0.75rem;
  font-weight: 600;
}
.btn-spinner-sm {
  display: inline-block;
  width: 12px; height: 12px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 4px;
}

/* Target storage */
.target-storage-row {
  display: flex;
  align-items: center;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-color);
  font-size: 0.875rem;
  color: var(--text-secondary);
  gap: 0.5rem;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
