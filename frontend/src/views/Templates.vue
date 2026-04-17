<template>
  <div class="templates-page">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">Template Library</h2>
        <p class="page-subtitle">
          Manage cloud images, LXC templates, and ISO files across all Proxmox hosts
          <span v-if="!loading && countBadgeText" class="count-badge">{{ countBadgeText }}</span>
        </p>
      </div>
      <div class="header-right">
        <!-- Cloud Images tab controls -->
        <template v-if="activeTab === 'cloud'">
          <input v-model="cloudSearch" class="form-control search-input" placeholder="Search cloud images..." />
          <select v-model="cloudHostFilter" class="form-control host-select">
            <option value="">All Hosts</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name || h.host }}</option>
          </select>
          <button @click="loadCloudImages" class="btn btn-outline" :disabled="loading">
            {{ loading ? 'Loading...' : 'Refresh' }}
          </button>
          <button @click="openDownloadModal" class="btn btn-primary">+ Download Image</button>
        </template>
        <!-- pveam Library tab controls -->
        <template v-else-if="activeTab === 'pveam'">
          <input v-model="pveamSearch" class="form-control search-input" placeholder="Search templates..." />
          <select v-model="pveamSection" class="form-control host-select" @change="loadPveamTemplates">
            <option value="">All Sections</option>
            <option value="system">System</option>
            <option value="turnkeylinux">TurnKey Linux</option>
          </select>
          <select v-model="pveamHostId" class="form-control host-select" @change="onPveamHostChange">
            <option value="">Select Host...</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name || h.host }}</option>
          </select>
          <button @click="loadPveamTemplates" class="btn btn-outline" :disabled="pveamLoading || !pveamHostId">
            {{ pveamLoading ? 'Loading...' : 'Refresh' }}
          </button>
        </template>
        <!-- ISO Images tab controls -->
        <template v-else-if="activeTab === 'iso'">
          <input v-model="isoSearch" class="form-control search-input" placeholder="Search ISOs..." />
          <select v-model="isoHostFilter" class="form-control host-select">
            <option value="">All Hosts</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name || h.host }}</option>
          </select>
          <button @click="loadIsoImages" class="btn btn-outline" :disabled="isoLoading">
            {{ isoLoading ? 'Loading...' : 'Refresh' }}
          </button>
          <button @click="openIsoUploadModal" class="btn btn-primary">+ Add ISO</button>
        </template>
        <!-- My Templates tab controls -->
        <template v-else-if="activeTab === 'local'">
          <input v-model="localSearch" class="form-control search-input" placeholder="Search by name or VMID..." />
          <select v-model="localHostFilter" class="form-control host-select">
            <option value="">All Hosts</option>
            <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name || h.host }}</option>
          </select>
          <button @click="loadLocalTemplates" class="btn btn-outline" :disabled="loading">
            {{ loading ? 'Loading...' : 'Refresh' }}
          </button>
        </template>
      </div>
    </div>

    <!-- Tab Bar -->
    <div class="tab-bar">
      <button :class="['tab-btn', { active: activeTab === 'cloud' }]" @click="switchTab('cloud')">
        Cloud Images
      </button>
      <button :class="['tab-btn', { active: activeTab === 'pveam' }]" @click="switchTab('pveam')">
        pveam Library
      </button>
      <button :class="['tab-btn', { active: activeTab === 'iso' }]" @click="switchTab('iso')">
        ISO Images
      </button>
      <button :class="['tab-btn', { active: activeTab === 'local' }]" @click="switchTab('local')">
        VM Templates
      </button>
    </div>

    <div v-if="error" class="alert alert-danger mb-3">{{ error }}</div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Cloud Images Tab                                                      -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <template v-if="activeTab === 'cloud'">
      <div class="card">
        <div class="card-body p-0">
          <div v-if="loading" class="loading-state">
            <div class="loading-spinner"></div>
            <span>Loading cloud images...</span>
          </div>
          <div v-else-if="filteredCloudImages.length === 0" class="empty-state-full">
            <div class="empty-icon-wrap">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>
            </div>
            <h4 class="empty-title">No cloud images found</h4>
            <p class="empty-subtitle">Download cloud images (qcow2/img) to Proxmox storage using the "Download Image" button, or search Proxmox storage content for existing images.</p>
            <button @click="openDownloadModal" class="btn btn-primary">Download Image</button>
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>OS</th>
                  <th>Name</th>
                  <th>Node</th>
                  <th>Storage</th>
                  <th>Size</th>
                  <th>Type</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="img in filteredCloudImages" :key="`${img.hostId}-${img.volid}`">
                  <td>
                    <span class="os-pill" :style="{ background: getOsColor(img.name) + '22', color: getOsColor(img.name), borderColor: getOsColor(img.name) + '55' }">
                      {{ detectOsInfo(img.name).icon }} {{ detectOsInfo(img.name).name }}
                    </span>
                  </td>
                  <td class="name-cell">
                    <span class="name-text" :title="img.name">{{ img.name }}</span>
                  </td>
                  <td class="mono">{{ img.node }}</td>
                  <td class="mono">{{ img.storage }}</td>
                  <td>{{ formatBytes(img.size) }}</td>
                  <td>
                    <span class="type-badge">{{ img.content || img.format || 'image' }}</span>
                  </td>
                  <td class="actions-cell">
                    <button class="btn btn-danger btn-sm" @click="confirmDeleteVolume(img)">Delete</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- pveam Library Tab                                                     -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <template v-else-if="activeTab === 'pveam'">
      <div class="card">
        <div class="card-body p-0">
          <div v-if="!pveamHostId" class="empty-state-full">
            <div class="empty-icon-wrap">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </div>
            <h4 class="empty-title">Select a Proxmox host</h4>
            <p class="empty-subtitle">Choose a host from the dropdown above to browse downloadable LXC templates from the Proxmox mirror network.</p>
          </div>
          <div v-else-if="pveamLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <span>Loading pveam catalog...</span>
          </div>
          <div v-else-if="filteredPveamTemplates.length === 0" class="empty-state-full">
            <div class="empty-icon-wrap">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            </div>
            <h4 class="empty-title">No templates match your search</h4>
            <p class="empty-subtitle">Try clearing your search or selecting a different section.</p>
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>OS</th>
                  <th>Template Name</th>
                  <th>Version</th>
                  <th>Section</th>
                  <th>Size</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tpl in filteredPveamTemplates" :key="tpl.package">
                  <td>
                    <span class="os-pill" :style="{ background: getOsColor(tpl.package) + '22', color: getOsColor(tpl.package), borderColor: getOsColor(tpl.package) + '55' }">
                      {{ detectOsInfo(tpl.package).icon }} {{ detectOsInfo(tpl.package).name }}
                    </span>
                  </td>
                  <td class="name-cell">
                    <span class="name-text" :title="tpl.package">{{ tpl.package }}</span>
                    <span v-if="tpl.description" class="name-sub">{{ truncate(tpl.description, 60) }}</span>
                  </td>
                  <td class="mono dim">{{ tpl.version || '—' }}</td>
                  <td>
                    <span class="section-badge" :class="tpl.section === 'turnkeylinux' ? 'section-tkl' : 'section-sys'">
                      {{ tpl.section === 'turnkeylinux' ? 'TurnKey' : tpl.section || 'system' }}
                    </span>
                  </td>
                  <td>{{ formatTemplateSize(tpl.size) }}</td>
                  <td class="actions-cell">
                    <button class="btn btn-primary btn-sm" @click="openPveamDownload(tpl)">Download</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- ISO Images Tab                                                        -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <template v-else-if="activeTab === 'iso'">
      <div class="card">
        <div class="card-body p-0">
          <div v-if="isoLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <span>Loading ISO images...</span>
          </div>
          <div v-else-if="filteredIsoImages.length === 0" class="empty-state-full">
            <div class="empty-icon-wrap">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>
            </div>
            <h4 class="empty-title">No ISO images found</h4>
            <p class="empty-subtitle">Add ISOs by uploading from your computer or providing a download URL. Proxmox will download directly to node storage.</p>
            <button @click="openIsoUploadModal" class="btn btn-primary">Add ISO</button>
          </div>
          <div v-else class="table-container">
            <!-- Bulk actions bar -->
            <div v-if="isoSelected.size > 0" class="bulk-bar">
              <span>{{ isoSelected.size }} selected</span>
              <button class="btn btn-danger btn-sm" @click="bulkDeleteIsos" :disabled="isoDeleting">
                {{ isoDeleting ? 'Deleting...' : 'Delete Selected' }}
              </button>
              <button class="btn btn-outline btn-sm" @click="isoSelected.clear(); isoSelected = new Set()">Clear</button>
            </div>
            <table class="table">
              <thead>
                <tr>
                  <th class="col-check">
                    <input type="checkbox" @change="toggleAllIsos" :checked="isoAllChecked" />
                  </th>
                  <th>Name</th>
                  <th>Node</th>
                  <th>Storage</th>
                  <th>Size</th>
                  <th>Used By</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="iso in filteredIsoImages" :key="`${iso.hostId}-${iso.volid}`">
                  <td class="col-check">
                    <input type="checkbox" :checked="isoSelected.has(iso.volid)" @change="toggleIsoSelect(iso)" />
                  </td>
                  <td class="name-cell">
                    <span class="name-text" :title="iso.name">{{ iso.name }}</span>
                  </td>
                  <td class="mono">{{ iso.node }}</td>
                  <td class="mono">{{ iso.storage }}</td>
                  <td>{{ formatBytes(iso.size) }}</td>
                  <td>
                    <span v-if="iso.usedBy && iso.usedBy.length" class="used-by-list">
                      <span v-for="vmid in iso.usedBy.slice(0, 3)" :key="vmid" class="vmid-chip">{{ vmid }}</span>
                      <span v-if="iso.usedBy.length > 3" class="dim">+{{ iso.usedBy.length - 3 }}</span>
                    </span>
                    <span v-else class="dim">—</span>
                  </td>
                  <td class="actions-cell">
                    <button class="btn btn-danger btn-sm" @click="confirmDeleteVolume(iso)">Delete</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- VM Templates (local) Tab                                              -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <template v-else-if="activeTab === 'local'">
      <div class="card">
        <div class="card-body p-0">
          <div v-if="loading" class="loading-state">
            <div class="loading-spinner"></div>
            <span>Loading VM templates...</span>
          </div>
          <div v-else-if="filteredLocalTemplates.length === 0" class="empty-state-full">
            <div class="empty-icon-wrap">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
            </div>
            <h4 class="empty-title">No VM templates found</h4>
            <p class="empty-subtitle">Convert a QEMU VM to a template in Proxmox, then it will appear here for cloning.</p>
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>VMID</th>
                  <th>Name</th>
                  <th>OS</th>
                  <th>Node</th>
                  <th>Host</th>
                  <th>Memory</th>
                  <th>CPUs</th>
                  <th>Disk</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tpl in filteredLocalTemplates" :key="`${tpl.hostId}-${tpl.vmid}`">
                  <td class="vmid-cell">{{ tpl.vmid }}</td>
                  <td class="name-cell">
                    <span class="name-text">{{ tpl.name || `VM ${tpl.vmid}` }}</span>
                  </td>
                  <td>
                    <span class="os-pill" :style="{ background: getOsColor(tpl.name) + '22', color: getOsColor(tpl.name), borderColor: getOsColor(tpl.name) + '55' }">
                      {{ detectOsInfo(tpl.name).icon }} {{ detectOsInfo(tpl.name).name }}
                    </span>
                  </td>
                  <td class="mono">{{ tpl.node }}</td>
                  <td class="mono">{{ tpl.hostName }}</td>
                  <td>
                    <span v-if="tpl.maxmem" class="dim">{{ Math.round(tpl.maxmem / 1024 / 1024) }} MB</span>
                    <span v-else class="dim">—</span>
                  </td>
                  <td>
                    <span v-if="tpl.maxcpu" class="dim">{{ tpl.maxcpu }} vCPU</span>
                    <span v-else class="dim">—</span>
                  </td>
                  <td>
                    <span v-if="tpl.maxdisk" class="dim">{{ formatBytes(tpl.maxdisk) }}</span>
                    <span v-else class="dim">—</span>
                  </td>
                  <td class="actions-cell">
                    <button class="btn btn-primary btn-sm" @click="openCloneModal(tpl)">Clone</button>
                    <router-link
                      :to="`/proxmox/${tpl.hostId}/nodes/${tpl.node}/vms/${tpl.vmid}`"
                      class="btn btn-outline btn-sm"
                    >Details</router-link>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- ═══════════════════════════════════════════════════════════════════ -->
    <!-- Download Cloud Image Modal                                          -->
    <!-- ═══════════════════════════════════════════════════════════════════ -->
    <div v-if="showDownloadModal" class="modal" @click.self="showDownloadModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Download Cloud Image to Proxmox</h3>
          <button @click="showDownloadModal = false" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <p class="hint-text mb-3">Proxmox will download the image directly to node storage — it never passes through this server.</p>

          <div class="form-group">
            <label class="form-label">Proxmox Host <span class="req">*</span></label>
            <select v-model="dlForm.hostId" class="form-control" @change="onDlHostChange">
              <option value="">Select host...</option>
              <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name || h.host }}</option>
            </select>
          </div>

          <div class="form-group" v-if="dlForm.hostId">
            <label class="form-label">Node <span class="req">*</span></label>
            <select v-model="dlForm.node" class="form-control" @change="onDlNodeChange">
              <option value="">Select node...</option>
              <option v-for="n in dlNodes" :key="n.node_name || n.node" :value="n.node_name || n.node">{{ n.node_name || n.node }}</option>
            </select>
          </div>

          <div class="form-group" v-if="dlForm.node">
            <label class="form-label">Storage <span class="req">*</span></label>
            <select v-model="dlForm.storage" class="form-control">
              <option value="">Select storage...</option>
              <option v-for="s in dlStorages" :key="s.storage" :value="s.storage">
                {{ s.storage }} ({{ s.type }})<template v-if="s.avail"> — {{ formatBytes(s.avail) }} free</template>
              </option>
            </select>
          </div>

          <!-- Preset picks -->
          <div class="form-group">
            <label class="form-label">Quick Presets</label>
            <div class="presets-grid">
              <button
                v-for="preset in CLOUD_IMAGE_PRESETS"
                :key="preset.id"
                class="preset-btn"
                :class="{ active: dlForm.url === preset.url }"
                @click="applyPreset(preset)"
              >
                <span class="preset-os-icon">{{ detectOsInfo(preset.name).icon }}</span>
                <span class="preset-name">{{ preset.name }}</span>
              </button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Image URL <span class="req">*</span></label>
            <input v-model="dlForm.url" class="form-control mono-input" placeholder="https://cloud-images.ubuntu.com/..." />
          </div>

          <div class="form-group">
            <label class="form-label">Filename <span class="req">*</span></label>
            <input v-model="dlForm.filename" class="form-control" placeholder="noble-server-cloudimg-amd64.img" />
          </div>

          <div class="form-group">
            <label class="form-label">Content Type</label>
            <select v-model="dlForm.content" class="form-control">
              <option value="import">Raw Import (cloud images)</option>
              <option value="iso">ISO</option>
              <option value="vztmpl">Container Template</option>
            </select>
          </div>

          <div v-if="dlError" class="alert alert-danger mt-2">{{ dlError }}</div>
          <div v-if="dlSuccess" class="alert alert-success mt-2">{{ dlSuccess }}</div>

          <div class="flex gap-1 mt-3">
            <button
              @click="submitDownload"
              class="btn btn-primary"
              :disabled="dlBusy || !dlForm.hostId || !dlForm.node || !dlForm.storage || !dlForm.url || !dlForm.filename"
            >
              {{ dlBusy ? 'Submitting...' : 'Start Download' }}
            </button>
            <button @click="showDownloadModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════ -->
    <!-- pveam Download Modal                                                -->
    <!-- ═══════════════════════════════════════════════════════════════════ -->
    <div v-if="showPveamModal" class="modal" @click.self="showPveamModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Download LXC Template</h3>
          <button @click="showPveamModal = false" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <p class="hint-text mb-2">
            Downloading <strong>{{ pveamTarget?.package }}</strong>
          </p>

          <div class="form-group">
            <label class="form-label">Node <span class="req">*</span></label>
            <select v-model="pveamDlForm.node" class="form-control" @change="onPveamDlNodeChange">
              <option value="">Select node...</option>
              <option v-for="n in pveamNodes" :key="n.node_name || n.node" :value="n.node_name || n.node">{{ n.node_name || n.node }}</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Target Storage <span class="req">*</span></label>
            <select v-model="pveamDlForm.storage" class="form-control" :disabled="pveamDlStoragesLoading">
              <option value="">{{ pveamDlStoragesLoading ? 'Loading...' : 'Select storage...' }}</option>
              <option v-for="s in pveamDlStorages" :key="s.storage" :value="s.storage">
                {{ s.storage }} ({{ s.type }})<template v-if="s.avail"> — {{ formatBytes(s.avail) }} free</template>
              </option>
            </select>
          </div>

          <div v-if="pveamDlError" class="alert alert-danger mt-2">{{ pveamDlError }}</div>
          <div v-if="pveamDlSuccess" class="alert alert-success mt-2">{{ pveamDlSuccess }}</div>

          <div class="flex gap-1 mt-3">
            <button
              @click="submitPveamDownload"
              class="btn btn-primary"
              :disabled="pveamDlBusy || !pveamDlForm.node || !pveamDlForm.storage"
            >
              {{ pveamDlBusy ? 'Downloading...' : 'Download Template' }}
            </button>
            <button @click="showPveamModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════ -->
    <!-- ISO Upload/URL Modal                                                -->
    <!-- ═══════════════════════════════════════════════════════════════════ -->
    <div v-if="showIsoModal" class="modal" @click.self="showIsoModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add ISO Image</h3>
          <button @click="showIsoModal = false" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <!-- Mode selector -->
          <div class="iso-mode-tabs mb-3">
            <button :class="['iso-mode-btn', { active: isoMode === 'url' }]" @click="isoMode = 'url'">URL Download</button>
            <button :class="['iso-mode-btn', { active: isoMode === 'info' }]" @click="isoMode = 'info'">Upload Info</button>
          </div>

          <template v-if="isoMode === 'url'">
            <p class="hint-text mb-3">Proxmox downloads the ISO directly from the URL to node storage — no file upload needed.</p>

            <div class="form-group">
              <label class="form-label">Proxmox Host <span class="req">*</span></label>
              <select v-model="isoForm.hostId" class="form-control" @change="onIsoHostChange">
                <option value="">Select host...</option>
                <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name || h.host }}</option>
              </select>
            </div>

            <div class="form-group" v-if="isoForm.hostId">
              <label class="form-label">Node <span class="req">*</span></label>
              <select v-model="isoForm.node" class="form-control" @change="onIsoNodeChange">
                <option value="">Select node...</option>
                <option v-for="n in isoNodes" :key="n.node_name || n.node" :value="n.node_name || n.node">{{ n.node_name || n.node }}</option>
              </select>
            </div>

            <div class="form-group" v-if="isoForm.node">
              <label class="form-label">Storage <span class="req">*</span></label>
              <select v-model="isoForm.storage" class="form-control">
                <option value="">Select storage...</option>
                <option v-for="s in isoStorages" :key="s.storage" :value="s.storage">
                  {{ s.storage }} ({{ s.type }})<template v-if="s.avail"> — {{ formatBytes(s.avail) }} free</template>
                </option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">ISO URL <span class="req">*</span></label>
              <input v-model="isoForm.url" class="form-control mono-input" placeholder="https://example.com/image.iso" @input="autoFillIsoFilename" />
            </div>

            <div class="form-group">
              <label class="form-label">Filename <span class="req">*</span></label>
              <input v-model="isoForm.filename" class="form-control" placeholder="image.iso" />
            </div>

            <div class="form-group">
              <label class="form-label">Checksum Algorithm</label>
              <select v-model="isoForm.checksumAlgo" class="form-control">
                <option value="">None</option>
                <option value="sha256">SHA-256</option>
                <option value="sha512">SHA-512</option>
                <option value="md5">MD5</option>
              </select>
            </div>

            <div class="form-group" v-if="isoForm.checksumAlgo">
              <label class="form-label">Checksum Value</label>
              <input v-model="isoForm.checksum" class="form-control mono-input" placeholder="Paste checksum here..." />
            </div>
          </template>

          <template v-else>
            <div class="info-note">
              <strong>Direct upload via Proxmox web UI:</strong>
              <ol class="upload-steps">
                <li>Open your Proxmox web interface</li>
                <li>Navigate to Datacenter &rarr; Node &rarr; Storage</li>
                <li>Click the storage that supports ISOs (e.g. <code>local</code>)</li>
                <li>Go to the <strong>ISO Images</strong> tab</li>
                <li>Click <strong>Upload</strong> and select your ISO file</li>
              </ol>
              <p class="mt-2">Once uploaded, click <strong>Refresh</strong> on this page to see it listed.</p>
            </div>
          </template>

          <div v-if="isoError" class="alert alert-danger mt-2">{{ isoError }}</div>
          <div v-if="isoSuccess" class="alert alert-success mt-2">{{ isoSuccess }}</div>

          <div v-if="isoMode === 'url'" class="flex gap-1 mt-3">
            <button
              @click="submitIsoDownload"
              class="btn btn-primary"
              :disabled="isoBusy || !isoForm.hostId || !isoForm.node || !isoForm.storage || !isoForm.url || !isoForm.filename"
            >
              {{ isoBusy ? 'Submitting...' : 'Download ISO' }}
            </button>
            <button @click="showIsoModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════ -->
    <!-- Delete Confirmation Modal                                           -->
    <!-- ═══════════════════════════════════════════════════════════════════ -->
    <div v-if="showDeleteModal" class="modal" @click.self="showDeleteModal = false">
      <div class="modal-content modal-sm" @click.stop>
        <div class="modal-header">
          <h3>Confirm Delete</h3>
          <button @click="showDeleteModal = false" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <p>Are you sure you want to delete <strong>{{ deleteTarget?.name }}</strong>?</p>
          <p class="hint-text mt-1">This will permanently remove the volume from Proxmox storage. This action cannot be undone.</p>
          <div v-if="deleteTarget?.usedBy?.length" class="alert alert-danger mt-2">
            Warning: This image is referenced by VM(s): {{ deleteTarget.usedBy.join(', ') }}
          </div>
          <div v-if="deleteError" class="alert alert-danger mt-2">{{ deleteError }}</div>
          <div class="flex gap-1 mt-3">
            <button @click="executeDelete" class="btn btn-danger" :disabled="deleting">
              {{ deleting ? 'Deleting...' : 'Delete' }}
            </button>
            <button @click="showDeleteModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════ -->
    <!-- Clone Modal (VM Templates tab)                                      -->
    <!-- ═══════════════════════════════════════════════════════════════════ -->
    <div v-if="showCloneModal" class="modal" @click.self="closeCloneModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Clone Template</h3>
          <button @click="closeCloneModal" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <p class="hint-text mb-3">
            Cloning <strong>{{ cloneTarget?.name || `VM ${cloneTarget?.vmid}` }}</strong>
            (VMID {{ cloneTarget?.vmid }}) from <strong>{{ cloneTarget?.node }}</strong>
          </p>

          <div class="form-group">
            <label class="form-label">New VM ID <span class="req">*</span></label>
            <input v-model.number="cloneForm.newid" type="number" class="form-control" placeholder="e.g. 200" />
          </div>

          <div class="form-group">
            <label class="form-label">New Name <span class="req">*</span></label>
            <input v-model="cloneForm.name" class="form-control" placeholder="new-vm-name" />
          </div>

          <div class="form-group">
            <label class="form-label">Clone Mode</label>
            <div class="radio-group">
              <label class="radio-label">
                <input v-model="cloneForm.full" type="radio" :value="true" />
                <span>
                  <strong>Full Clone</strong>
                  <span class="radio-hint">Independent copy — can be moved to any storage</span>
                </span>
              </label>
              <label class="radio-label">
                <input v-model="cloneForm.full" type="radio" :value="false" />
                <span>
                  <strong>Linked Clone</strong>
                  <span class="radio-hint">Shares base disk — faster, uses less space</span>
                </span>
              </label>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Target Node</label>
            <select v-model="cloneForm.target" class="form-control" @change="onCloneNodeChange">
              <option value="">Same as template ({{ cloneTarget?.node }})</option>
              <option v-for="n in cloneNodes" :key="n.node_name || n.node" :value="n.node_name || n.node">{{ n.node_name || n.node }}</option>
            </select>
          </div>

          <div v-if="cloneForm.full" class="form-group">
            <label class="form-label">Target Storage</label>
            <select v-model="cloneForm.storage" class="form-control" :disabled="cloneStoragesLoading">
              <option value="">Default storage</option>
              <option v-for="s in cloneStorages" :key="s.storage" :value="s.storage">
                {{ s.storage }}<template v-if="s.avail"> ({{ formatBytes(s.avail) }} free)</template>
              </option>
            </select>
          </div>

          <div class="form-group checkbox-group">
            <label class="checkbox-label">
              <input v-model="cloneForm.startAfterClone" type="checkbox" />
              Start VM after clone
            </label>
          </div>

          <div v-if="cloneError" class="alert alert-danger mt-2">{{ cloneError }}</div>

          <div class="flex gap-1 mt-3">
            <button @click="submitClone" class="btn btn-primary" :disabled="cloning || !cloneForm.newid || !cloneForm.name">
              {{ cloning ? 'Cloning...' : 'Clone VM' }}
            </button>
            <button @click="closeCloneModal" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <transition name="toast-fade">
      <div v-if="toastMsg.show" class="toast-msg" :class="toastMsg.type === 'error' ? 'toast-error' : 'toast-success'">
        <span>{{ toastMsg.message }}</span>
        <button class="toast-close" @click="toastMsg.show = false">&times;</button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { detectOs, formatTemplateSize } from '@/utils/osIcons'

const router = useRouter()

// ── Active tab ────────────────────────────────────────────────────────────────
const activeTab = ref('cloud')

// ── Global state ──────────────────────────────────────────────────────────────
const hosts = ref([])
const error = ref('')
const loading = ref(false)

// ── Toast ─────────────────────────────────────────────────────────────────────
const toastMsg = ref({ show: false, message: '', type: 'success' })
function showToast(msg, type = 'success') {
  toastMsg.value = { show: true, message: msg, type }
  setTimeout(() => { toastMsg.value.show = false }, 6000)
}

// ── Cloud Images ──────────────────────────────────────────────────────────────
const cloudImages = ref([])
const cloudSearch = ref('')
const cloudHostFilter = ref('')

const filteredCloudImages = computed(() => {
  let list = cloudImages.value
  if (cloudHostFilter.value) list = list.filter(i => String(i.hostId) === String(cloudHostFilter.value))
  const q = cloudSearch.value.trim().toLowerCase()
  if (q) list = list.filter(i => (i.name || '').toLowerCase().includes(q) || (i.storage || '').toLowerCase().includes(q))
  return list
})

// ── pveam Library ─────────────────────────────────────────────────────────────
const pveamTemplates = ref([])
const pveamSearch = ref('')
const pveamSection = ref('')
const pveamHostId = ref('')
const pveamNode = ref('')
const pveamNodes = ref([])
const pveamLoading = ref(false)

const filteredPveamTemplates = computed(() => {
  let list = pveamTemplates.value
  const q = pveamSearch.value.trim().toLowerCase()
  if (q) list = list.filter(t => (t.package || '').toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q))
  return list
})

// ── ISO Images ────────────────────────────────────────────────────────────────
const isoImages = ref([])
const isoSearch = ref('')
const isoHostFilter = ref('')
const isoLoading = ref(false)
const isoSelected = ref(new Set())
const isoDeleting = ref(false)

const filteredIsoImages = computed(() => {
  let list = isoImages.value
  if (isoHostFilter.value) list = list.filter(i => String(i.hostId) === String(isoHostFilter.value))
  const q = isoSearch.value.trim().toLowerCase()
  if (q) list = list.filter(i => (i.name || '').toLowerCase().includes(q))
  return list
})

const isoAllChecked = computed(() =>
  filteredIsoImages.value.length > 0 && filteredIsoImages.value.every(i => isoSelected.value.has(i.volid))
)

// ── Local VM Templates ────────────────────────────────────────────────────────
const localTemplates = ref([])
const localSearch = ref('')
const localHostFilter = ref('')

const filteredLocalTemplates = computed(() => {
  let list = localTemplates.value
  if (localHostFilter.value) list = list.filter(t => String(t.hostId) === String(localHostFilter.value))
  const q = localSearch.value.trim().toLowerCase()
  if (q) list = list.filter(t => (t.name || '').toLowerCase().includes(q) || String(t.vmid).includes(q))
  return [...list].sort((a, b) => (a.name || '').localeCompare(b.name || ''))
})

// ── Count badge ───────────────────────────────────────────────────────────────
const countBadgeText = computed(() => {
  if (activeTab.value === 'cloud') {
    const n = filteredCloudImages.value.length
    return n ? `${n} image${n !== 1 ? 's' : ''}` : ''
  }
  if (activeTab.value === 'pveam') {
    const n = filteredPveamTemplates.value.length
    return n ? `${n} available` : ''
  }
  if (activeTab.value === 'iso') {
    const n = filteredIsoImages.value.length
    return n ? `${n} ISO${n !== 1 ? 's' : ''}` : ''
  }
  if (activeTab.value === 'local') {
    const n = filteredLocalTemplates.value.length
    return n ? `${n} template${n !== 1 ? 's' : ''}` : ''
  }
  return ''
})

// ── Cloud Image Presets ───────────────────────────────────────────────────────
const CLOUD_IMAGE_PRESETS = [
  { id: 'ubuntu-2404', name: 'Ubuntu 24.04 LTS', url: 'https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img', filename: 'noble-server-cloudimg-amd64.img' },
  { id: 'ubuntu-2204', name: 'Ubuntu 22.04 LTS', url: 'https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img', filename: 'jammy-server-cloudimg-amd64.img' },
  { id: 'debian-12',   name: 'Debian 12',         url: 'https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2', filename: 'debian-12-generic-amd64.qcow2' },
  { id: 'rocky-9',     name: 'Rocky Linux 9',     url: 'https://download.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud.latest.x86_64.qcow2', filename: 'Rocky-9-GenericCloud.latest.x86_64.qcow2' },
  { id: 'alma-9',      name: 'AlmaLinux 9',       url: 'https://repo.almalinux.org/almalinux/9/cloud/x86_64/images/AlmaLinux-9-GenericCloud-latest.x86_64.qcow2', filename: 'AlmaLinux-9-GenericCloud-latest.x86_64.qcow2' },
  { id: 'centos-9',    name: 'CentOS Stream 9',   url: 'https://cloud.centos.org/centos/9-stream/x86_64/images/CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2', filename: 'CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2' },
  { id: 'alpine-319',  name: 'Alpine 3.19',       url: 'https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/cloud/nocloud_alpine-3.19.0-x86_64-bios-cloudinit-r0.qcow2', filename: 'alpine-3.19-cloudimg.qcow2' },
]

// ── Download Cloud Image Modal ────────────────────────────────────────────────
const showDownloadModal = ref(false)
const dlForm = ref({ hostId: '', node: '', storage: '', url: '', filename: '', content: 'import' })
const dlNodes = ref([])
const dlStorages = ref([])
const dlBusy = ref(false)
const dlError = ref('')
const dlSuccess = ref('')

function openDownloadModal() {
  dlForm.value = { hostId: hosts.value[0]?.id || '', node: '', storage: '', url: '', filename: '', content: 'import' }
  dlNodes.value = []
  dlStorages.value = []
  dlError.value = ''
  dlSuccess.value = ''
  showDownloadModal.value = true
  if (dlForm.value.hostId) onDlHostChange()
}

async function onDlHostChange() {
  dlForm.value.node = ''
  dlForm.value.storage = ''
  dlNodes.value = []
  dlStorages.value = []
  if (!dlForm.value.hostId) return
  try {
    const res = await api.proxmox.listNodes(dlForm.value.hostId)
    dlNodes.value = res.data || []
    if (dlNodes.value.length === 1) {
      dlForm.value.node = dlNodes.value[0].node
      await onDlNodeChange()
    }
  } catch (e) { console.warn(e) }
}

async function onDlNodeChange() {
  dlForm.value.storage = ''
  dlStorages.value = []
  const { hostId, node } = dlForm.value
  if (!hostId || !node) return
  try {
    const res = await api.pveNode.listStorage(hostId, node)
    dlStorages.value = res.data || []
    const img = dlStorages.value.find(s => s.content && s.content.includes('images'))
    if (img) dlForm.value.storage = img.storage
  } catch (e) { console.warn(e) }
}

function applyPreset(preset) {
  dlForm.value.url = preset.url
  dlForm.value.filename = preset.filename
}

async function submitDownload() {
  dlBusy.value = true
  dlError.value = ''
  dlSuccess.value = ''
  try {
    const { hostId, node, storage, url, filename, content } = dlForm.value
    await api.pveNode.downloadUrlToStorage(hostId, node, storage, { url, filename, content })
    dlSuccess.value = 'Download task submitted to Proxmox. Monitor progress in the node task log.'
    showToast('Download task started — check Proxmox task log for progress.')
    setTimeout(() => loadCloudImages(), 3000)
  } catch (e) {
    dlError.value = e?.response?.data?.detail || 'Failed to start download.'
  } finally {
    dlBusy.value = false
  }
}

// ── pveam Download Modal ──────────────────────────────────────────────────────
const showPveamModal = ref(false)
const pveamTarget = ref(null)
const pveamDlForm = ref({ node: '', storage: '' })
const pveamDlStorages = ref([])
const pveamDlStoragesLoading = ref(false)
const pveamDlBusy = ref(false)
const pveamDlError = ref('')
const pveamDlSuccess = ref('')

async function openPveamDownload(tpl) {
  pveamTarget.value = tpl
  pveamDlForm.value = { node: pveamNodes.value[0]?.node || '', storage: '' }
  pveamDlStorages.value = []
  pveamDlError.value = ''
  pveamDlSuccess.value = ''
  showPveamModal.value = true
  if (pveamDlForm.value.node) await onPveamDlNodeChange()
}

async function onPveamDlNodeChange() {
  pveamDlForm.value.storage = ''
  pveamDlStorages.value = []
  pveamDlStoragesLoading.value = true
  try {
    const res = await api.pveNode.listStorage(pveamHostId.value, pveamDlForm.value.node)
    // filter storages that can hold vztmpl
    pveamDlStorages.value = (res.data || []).filter(s => s.content && s.content.includes('vztmpl'))
    if (pveamDlStorages.value.length === 0) pveamDlStorages.value = res.data || []
    const first = pveamDlStorages.value[0]
    if (first) pveamDlForm.value.storage = first.storage
  } catch (e) { console.warn(e) } finally {
    pveamDlStoragesLoading.value = false
  }
}

async function submitPveamDownload() {
  pveamDlBusy.value = true
  pveamDlError.value = ''
  pveamDlSuccess.value = ''
  try {
    const { node, storage } = pveamDlForm.value
    await api.pveNode.downloadTemplate(pveamHostId.value, node, {
      storage,
      template: pveamTarget.value.package,
    })
    pveamDlSuccess.value = `Download of ${pveamTarget.value.package} started. Check node task log for progress.`
    showToast(`Downloading ${pveamTarget.value.package}...`)
  } catch (e) {
    pveamDlError.value = e?.response?.data?.detail || 'Download failed.'
  } finally {
    pveamDlBusy.value = false
  }
}

// ── ISO Upload Modal ──────────────────────────────────────────────────────────
const showIsoModal = ref(false)
const isoMode = ref('url')
const isoForm = ref({ hostId: '', node: '', storage: '', url: '', filename: '', checksumAlgo: '', checksum: '' })
const isoNodes = ref([])
const isoStorages = ref([])
const isoBusy = ref(false)
const isoError = ref('')
const isoSuccess = ref('')

function openIsoUploadModal() {
  isoMode.value = 'url'
  isoForm.value = { hostId: hosts.value[0]?.id || '', node: '', storage: '', url: '', filename: '', checksumAlgo: '', checksum: '' }
  isoNodes.value = []
  isoStorages.value = []
  isoError.value = ''
  isoSuccess.value = ''
  showIsoModal.value = true
  if (isoForm.value.hostId) onIsoHostChange()
}

async function onIsoHostChange() {
  isoForm.value.node = ''
  isoForm.value.storage = ''
  isoNodes.value = []
  isoStorages.value = []
  if (!isoForm.value.hostId) return
  try {
    const res = await api.proxmox.listNodes(isoForm.value.hostId)
    isoNodes.value = res.data || []
    if (isoNodes.value.length === 1) {
      isoForm.value.node = isoNodes.value[0].node
      await onIsoNodeChange()
    }
  } catch (e) { console.warn(e) }
}

async function onIsoNodeChange() {
  isoForm.value.storage = ''
  isoStorages.value = []
  const { hostId, node } = isoForm.value
  if (!hostId || !node) return
  try {
    const res = await api.pveNode.listStorage(hostId, node)
    isoStorages.value = (res.data || []).filter(s => s.content && s.content.includes('iso'))
    if (isoStorages.value.length === 0) isoStorages.value = res.data || []
    if (isoStorages.value.length > 0) isoForm.value.storage = isoStorages.value[0].storage
  } catch (e) { console.warn(e) }
}

function autoFillIsoFilename() {
  const url = isoForm.value.url
  if (url && !isoForm.value.filename) {
    try {
      const parts = new URL(url).pathname.split('/')
      isoForm.value.filename = parts[parts.length - 1] || ''
    } catch (e) {
      // invalid url, ignore
    }
  }
}

async function submitIsoDownload() {
  isoBusy.value = true
  isoError.value = ''
  isoSuccess.value = ''
  try {
    const { hostId, node, storage, url, filename, checksumAlgo, checksum } = isoForm.value
    const payload = { url, filename, content: 'iso' }
    if (checksumAlgo) { payload.checksum_algorithm = checksumAlgo; payload.checksum = checksum }
    await api.pveNode.downloadUrlToStorage(hostId, node, storage, payload)
    isoSuccess.value = 'ISO download task submitted. Proxmox will download directly to storage.'
    showToast('ISO download started — monitor in Proxmox task log.')
    setTimeout(() => loadIsoImages(), 3000)
  } catch (e) {
    isoError.value = e?.response?.data?.detail || 'Failed to submit download.'
  } finally {
    isoBusy.value = false
  }
}

// ── Delete Volume Modal ───────────────────────────────────────────────────────
const showDeleteModal = ref(false)
const deleteTarget = ref(null)
const deleteError = ref('')
const deleting = ref(false)

function confirmDeleteVolume(item) {
  deleteTarget.value = item
  deleteError.value = ''
  showDeleteModal.value = true
}

async function executeDelete() {
  deleting.value = true
  deleteError.value = ''
  try {
    const item = deleteTarget.value
    await api.pveNode.deleteVolume(item.hostId, item.node, item.storage, item.volid)
    showDeleteModal.value = false
    showToast(`Deleted ${item.name}`)
    // Refresh the relevant list
    if (activeTab.value === 'cloud') await loadCloudImages()
    else if (activeTab.value === 'iso') await loadIsoImages()
  } catch (e) {
    deleteError.value = e?.response?.data?.detail || 'Delete failed.'
  } finally {
    deleting.value = false
  }
}

// ── Bulk ISO delete ───────────────────────────────────────────────────────────
function toggleIsoSelect(iso) {
  const s = new Set(isoSelected.value)
  if (s.has(iso.volid)) s.delete(iso.volid)
  else s.add(iso.volid)
  isoSelected.value = s
}

function toggleAllIsos() {
  if (isoAllChecked.value) {
    isoSelected.value = new Set()
  } else {
    isoSelected.value = new Set(filteredIsoImages.value.map(i => i.volid))
  }
}

async function bulkDeleteIsos() {
  if (!confirm(`Delete ${isoSelected.value.size} selected ISO(s)? This cannot be undone.`)) return
  isoDeleting.value = true
  const toDelete = isoImages.value.filter(i => isoSelected.value.has(i.volid))
  let failed = 0
  for (const item of toDelete) {
    try {
      await api.pveNode.deleteVolume(item.hostId, item.node, item.storage, item.volid)
    } catch (e) {
      failed++
    }
  }
  isoSelected.value = new Set()
  isoDeleting.value = false
  await loadIsoImages()
  if (failed) showToast(`${toDelete.length - failed} deleted, ${failed} failed.`, 'error')
  else showToast(`${toDelete.length} ISO(s) deleted.`)
}

// ── Clone Modal ───────────────────────────────────────────────────────────────
const showCloneModal = ref(false)
const cloneTarget = ref(null)
const cloneNodes = ref([])
const cloneStorages = ref([])
const cloneStoragesLoading = ref(false)
const cloneForm = ref({ newid: null, name: '', target: '', storage: '', full: true, startAfterClone: false })
const cloning = ref(false)
const cloneError = ref('')

async function openCloneModal(tpl) {
  cloneTarget.value = tpl
  cloneError.value = ''
  cloneForm.value = {
    newid: null,
    name: `${tpl.name || `vm${tpl.vmid}`}-clone`,
    target: '',
    storage: '',
    full: true,
    startAfterClone: false,
  }
  cloneNodes.value = []
  cloneStorages.value = []
  showCloneModal.value = true

  try {
    const res = await api.pveNode.nextId(tpl.hostId)
    const next = res.data?.vmid
    if (next) cloneForm.value.newid = Number(next)
  } catch (e) { console.warn(e) }

  try {
    const res = await api.proxmox.listNodes(tpl.hostId)
    cloneNodes.value = (res.data || []).filter(n => (n.node_name || n.node) !== tpl.node)
  } catch (e) { console.warn(e) }

  await loadCloneStorages(tpl.hostId, tpl.node)
}

async function loadCloneStorages(hostId, node) {
  cloneStoragesLoading.value = true
  try {
    const res = await api.pveNode.listStorage(hostId, node)
    cloneStorages.value = (res.data || []).filter(s => s.content && s.content.includes('images'))
  } catch (e) { console.warn(e) } finally {
    cloneStoragesLoading.value = false
  }
}

async function onCloneNodeChange() {
  cloneForm.value.storage = ''
  const node = cloneForm.value.target || cloneTarget.value?.node
  if (node) await loadCloneStorages(cloneTarget.value.hostId, node)
}

function closeCloneModal() {
  showCloneModal.value = false
  cloneTarget.value = null
  cloneError.value = ''
}

async function submitClone() {
  if (!cloneForm.value.newid || !cloneForm.value.name) return
  cloning.value = true
  cloneError.value = ''
  try {
    const { newid, name, target, full, storage } = cloneForm.value
    const payload = { newid, name, full: full ? 1 : 0, ...(target ? { target } : {}), ...(full && storage ? { storage } : {}) }
    await api.pveVm.clone(cloneTarget.value.hostId, cloneTarget.value.node, cloneTarget.value.vmid, payload)
    if (cloneForm.value.startAfterClone) {
      try { await api.pveVm.start(cloneTarget.value.hostId, target || cloneTarget.value.node, newid) } catch (e) { console.warn(e) }
    }
    closeCloneModal()
    showToast(`VM ${newid} cloned successfully.`)
  } catch (e) {
    cloneError.value = e?.response?.data?.detail || 'Clone failed.'
  } finally {
    cloning.value = false
  }
}

// ── OS helpers ────────────────────────────────────────────────────────────────
function detectOsInfo(name) {
  return detectOs(name)
}

function getOsColor(name) {
  return detectOs(name).color
}

// ── Format helpers ────────────────────────────────────────────────────────────
function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—'
  const n = Number(bytes)
  if (n >= 1024 * 1024 * 1024) return (n / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
  if (n >= 1024 * 1024) return (n / (1024 * 1024)).toFixed(0) + ' MB'
  if (n >= 1024) return (n / 1024).toFixed(0) + ' KB'
  return n + ' B'
}

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '…' : str
}

// ── Data Loading ──────────────────────────────────────────────────────────────
async function loadHosts() {
  try {
    const res = await api.proxmox.listHosts()
    hosts.value = (res.data || []).filter(h => h.is_active !== false)
  } catch (e) {
    error.value = 'Failed to load Proxmox hosts.'
  }
}

async function loadCloudImages() {
  loading.value = true
  cloudImages.value = []
  const results = []
  await Promise.allSettled(
    hosts.value.map(async (host) => {
      try {
        // Get all nodes for this host
        const nodesRes = await api.proxmox.listNodes(host.id)
        const nodeList = nodesRes.data || []
        await Promise.allSettled(
          nodeList.map(async (nodeObj) => {
            const node = nodeObj.node_name || nodeObj.node
            try {
              // Get storage list for this node
              const storRes = await api.pveNode.listStorage(host.id, node)
              const storages = storRes.data || []
              await Promise.allSettled(
                storages.map(async (stor) => {
                  // Only look in storages that can hold images
                  if (!stor.content || !stor.content.includes('images')) return
                  try {
                    const cRes = await api.pveNode.browseStorage(host.id, node, stor.storage, { content: 'images' })
                    const items = cRes.data || []
                    for (const item of items) {
                      // Cloud images: qcow2, raw, vmdk, img — but NOT VM disk files (vm-NNN-disk-N.*)
                      const fname = (item.volid || '').split('/').pop()
                      const isVmDisk = /^(vm|base)-\d+-disk-\d+/i.test(fname)
                      if (!isVmDisk && fname.match(/\.(qcow2|img|raw|vmdk)$/i)) {
                        results.push({
                          ...item,
                          name: fname,
                          storage: stor.storage,
                          node,
                          hostId: host.id,
                          hostName: host.name || host.host,
                        })
                      }
                    }
                  } catch (e) { /* storage may not respond */ }
                })
              )
            } catch (e) { /* node storage unavailable */ }
          })
        )
      } catch (e) { console.warn(`Host ${host.id} error:`, e) }
    })
  )
  cloudImages.value = results
  loading.value = false
}

async function loadIsoImages() {
  isoLoading.value = true
  isoImages.value = []
  const results = []
  await Promise.allSettled(
    hosts.value.map(async (host) => {
      try {
        const nodesRes = await api.proxmox.listNodes(host.id)
        const nodeList = nodesRes.data || []
        // Also fetch all VMs to build a usage map
        let vmList = []
        try {
          const vmRes = await api.pveNode.clusterResources(host.id, 'vm')
          vmList = vmRes.data || []
        } catch (e) { /* ignore */ }

        await Promise.allSettled(
          nodeList.map(async (nodeObj) => {
            const node = nodeObj.node_name || nodeObj.node
            try {
              const storRes = await api.pveNode.listStorage(host.id, node)
              const storages = storRes.data || []
              await Promise.allSettled(
                storages.map(async (stor) => {
                  if (!stor.content || !stor.content.includes('iso')) return
                  try {
                    const cRes = await api.pveNode.browseStorage(host.id, node, stor.storage, { content: 'iso' })
                    const items = cRes.data || []
                    for (const item of items) {
                      const fname = (item.volid || '').split('/').pop()
                      // Find VMs that reference this ISO
                      const usedBy = vmList
                        .filter(vm => vm.node === node)
                        .filter(vm => {
                          // We can't easily check config without extra API calls, so leave empty for now
                          return false
                        })
                        .map(vm => vm.vmid)
                      results.push({
                        ...item,
                        name: fname,
                        storage: stor.storage,
                        node,
                        hostId: host.id,
                        hostName: host.name || host.host,
                        usedBy,
                      })
                    }
                  } catch (e) { /* storage unavailable */ }
                })
              )
            } catch (e) { /* node unavailable */ }
          })
        )
      } catch (e) { console.warn(`Host ${host.id} error:`, e) }
    })
  )
  isoImages.value = results
  isoLoading.value = false
}

async function loadLocalTemplates() {
  loading.value = true
  localTemplates.value = []
  const results = []
  await Promise.allSettled(
    hosts.value.map(async (host) => {
      try {
        const res = await api.pveNode.clusterResources(host.id, 'vm')
        const items = (res.data || [])
          .filter(vm => vm.template === 1)
          .map(vm => ({ ...vm, hostId: host.id, hostName: host.name || host.host }))
        results.push(...items)
      } catch (e) { console.warn(e) }
    })
  )
  localTemplates.value = results
  loading.value = false
}

async function loadPveamTemplates() {
  if (!pveamHostId.value) return
  pveamLoading.value = true
  pveamTemplates.value = []
  try {
    // Use first node
    if (!pveamNodes.value.length) {
      const res = await api.proxmox.listNodes(pveamHostId.value)
      pveamNodes.value = res.data || []
    }
    const node = pveamNodes.value[0]?.node
    if (!node) return
    pveamNode.value = node
    const params = pveamSection.value ? { section: pveamSection.value } : {}
    const res = await api.pveNode.listAvailableTemplates(pveamHostId.value, node, pveamSection.value || undefined)
    pveamTemplates.value = res.data || []
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to load pveam templates.'
  } finally {
    pveamLoading.value = false
  }
}

async function onPveamHostChange() {
  pveamNodes.value = []
  pveamTemplates.value = []
  if (!pveamHostId.value) return
  try {
    const res = await api.proxmox.listNodes(pveamHostId.value)
    pveamNodes.value = res.data || []
  } catch (e) { console.warn(e) }
  await loadPveamTemplates()
}

// ── Tab switch ────────────────────────────────────────────────────────────────
async function switchTab(tab) {
  activeTab.value = tab
  error.value = ''
  if (tab === 'cloud' && cloudImages.value.length === 0) await loadCloudImages()
  if (tab === 'iso' && isoImages.value.length === 0) await loadIsoImages()
  if (tab === 'local' && localTemplates.value.length === 0) await loadLocalTemplates()
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadHosts()
  await loadCloudImages()
})
</script>

<style scoped>
/* ── Layout ──────────────────────────────────────────────────────────────── */
.templates-page {
  padding: 1.5rem;
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1rem;
}

.page-title { font-size: 1.5rem; font-weight: 700; color: var(--text-primary); margin: 0; }

.page-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0.25rem 0 0;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.count-badge {
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 12px;
  padding: 0.1rem 0.6rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.search-input { width: 220px; }
.host-select  { width: 180px; }

/* ── Tabs ────────────────────────────────────────────────────────────────── */
.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 1.25rem;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  padding: 0.6rem 1.25rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.tab-btn:hover { color: var(--text-primary); }
.tab-btn.active { color: var(--primary-color); border-bottom-color: var(--primary-color); font-weight: 600; }

/* ── Card ────────────────────────────────────────────────────────────────── */
.card {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}
.card-body { padding: 1.5rem; }
.p-0 { padding: 0; }

/* ── States ──────────────────────────────────────────────────────────────── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 4rem 2rem;
  color: var(--text-secondary);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state-full {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3.5rem 1.5rem;
  text-align: center;
}

.empty-icon-wrap {
  width: 80px; height: 80px;
  border-radius: 50%;
  background: var(--background);
  border: 2px dashed var(--border-color);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-title { font-size: 1rem; font-weight: 600; color: var(--text-primary); margin: 0; }
.empty-subtitle { font-size: 0.875rem; color: var(--text-secondary); margin: 0; max-width: 440px; }

/* ── Table ───────────────────────────────────────────────────────────────── */
.table-container { overflow-x: auto; }

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.table th {
  background: var(--background);
  color: var(--text-secondary);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.72rem;
  letter-spacing: 0.05em;
  padding: 0.65rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}

.table td {
  padding: 0.7rem 1rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
  vertical-align: middle;
}

.table tbody tr:last-child td { border-bottom: none; }
.table tbody tr:hover { background: rgba(255, 255, 255, 0.025); }

.col-check { width: 40px; }
.vmid-cell { font-family: monospace; font-weight: 600; color: var(--primary-color) !important; }

.name-cell { max-width: 260px; }
.name-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}
.name-sub {
  display: block;
  font-size: 0.75rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono { font-family: monospace; font-size: 0.8rem; }
.dim  { color: var(--text-secondary); font-size: 0.8rem; }

.actions-cell { display: flex; gap: 0.4rem; align-items: center; flex-wrap: nowrap; }

/* ── OS Pill ─────────────────────────────────────────────────────────────── */
.os-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.15rem 0.55rem;
  border-radius: 20px;
  font-size: 0.72rem;
  font-weight: 600;
  border: 1px solid transparent;
  white-space: nowrap;
}

/* ── Badges ──────────────────────────────────────────────────────────────── */
.type-badge {
  background: rgba(100, 116, 139, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(100, 116, 139, 0.25);
  border-radius: 4px;
  padding: 0.1rem 0.45rem;
  font-size: 0.7rem;
  font-weight: 600;
  font-family: monospace;
}

.section-badge {
  display: inline-block;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  border: 1px solid transparent;
}
.section-sys { background: rgba(59, 130, 246, 0.12); color: #60a5fa; border-color: rgba(59, 130, 246, 0.3); }
.section-tkl { background: rgba(16, 185, 129, 0.12); color: #34d399; border-color: rgba(16, 185, 129, 0.3); }

/* ── Used-by chips ───────────────────────────────────────────────────────── */
.used-by-list { display: flex; gap: 0.25rem; align-items: center; flex-wrap: wrap; }
.vmid-chip {
  background: rgba(59, 130, 246, 0.1);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 4px;
  padding: 0.05rem 0.35rem;
  font-size: 0.7rem;
  font-family: monospace;
  font-weight: 600;
}

/* ── Bulk bar ────────────────────────────────────────────────────────────── */
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 1rem;
  background: rgba(59, 130, 246, 0.07);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.875rem;
  color: var(--text-primary);
}

/* ── Presets grid ────────────────────────────────────────────────────────── */
.presets-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.preset-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.65rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--text-secondary);
  transition: all 0.15s;
}
.preset-btn:hover { border-color: var(--primary-color); color: var(--text-primary); }
.preset-btn.active { border-color: var(--primary-color); background: rgba(59, 130, 246, 0.1); color: var(--primary-color); }

.preset-os-icon { font-size: 1rem; }
.preset-name { white-space: nowrap; }

/* ── ISO mode tabs ───────────────────────────────────────────────────────── */
.iso-mode-tabs { display: flex; gap: 0; border: 1px solid var(--border-color); border-radius: 6px; overflow: hidden; }
.iso-mode-btn {
  flex: 1;
  padding: 0.4rem 0.75rem;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.iso-mode-btn.active { background: var(--primary-color); color: white; }

/* ── Upload steps ────────────────────────────────────────────────────────── */
.upload-steps {
  margin: 0.5rem 0 0 1.25rem;
  padding: 0;
  font-size: 0.82rem;
  color: var(--text-primary);
  line-height: 1.8;
}
code { background: rgba(255,255,255,0.08); padding: 0.1em 0.35em; border-radius: 3px; font-size: 0.9em; }

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.15s;
  white-space: nowrap;
  color: var(--text-primary);
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-sm { padding: 0.3rem 0.65rem; font-size: 0.8rem; }

.btn-primary { background: var(--primary-color); color: white; border-color: var(--primary-color); }
.btn-primary:hover:not(:disabled) { background: #2563eb; }

.btn-outline { background: transparent; border-color: var(--border-color); }
.btn-outline:hover:not(:disabled) { background: rgba(255,255,255,0.07); }

.btn-danger { background: rgba(239, 68, 68, 0.1); color: #f87171; border-color: rgba(239, 68, 68, 0.3); }
.btn-danger:hover:not(:disabled) { background: rgba(239, 68, 68, 0.2); }

/* ── Form ────────────────────────────────────────────────────────────────── */
.form-control {
  padding: 0.5rem 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 0.875rem;
  color: var(--text-primary);
  min-height: 36px;
  width: 100%;
}
.form-control:focus { outline: none; border-color: var(--primary-color); box-shadow: 0 0 0 2px rgba(59,130,246,0.2); }
.form-control:disabled { opacity: 0.5; cursor: not-allowed; }
.mono-input { font-family: monospace; font-size: 0.8rem; }

.form-group { margin-bottom: 1rem; }

.form-label {
  display: block;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 0.35rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.req { color: #f87171; }

.checkbox-group { margin-bottom: 0.75rem; }
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}
.checkbox-label input[type="checkbox"] { width: 16px; height: 16px; accent-color: var(--primary-color); cursor: pointer; }

/* ── Radio ───────────────────────────────────────────────────────────────── */
.radio-group { display: flex; flex-direction: column; gap: 0.5rem; }
.radio-label {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
  transition: border-color 0.15s;
}
.radio-label:hover { border-color: var(--primary-color); }
.radio-label input[type="radio"] { margin-top: 2px; accent-color: var(--primary-color); }
.radio-label > span { display: flex; flex-direction: column; gap: 0.15rem; }
.radio-hint { font-size: 0.775rem; color: var(--text-secondary); font-weight: 400; }

/* ── Modal ───────────────────────────────────────────────────────────────── */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  width: 100%;
  max-width: 540px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.modal-sm { max-width: 400px; }
.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  background: var(--surface);
  z-index: 1;
}
.modal-header h3 { margin: 0; font-size: 1.1rem; color: var(--text-primary); }
.btn-close { background: none; border: none; font-size: 1.4rem; cursor: pointer; color: var(--text-secondary); line-height: 1; padding: 0; }
.btn-close:hover { color: var(--text-primary); }
.modal-body { padding: 1.5rem; }

/* ── Alerts ──────────────────────────────────────────────────────────────── */
.alert { padding: 0.75rem 1rem; border-radius: 6px; font-size: 0.875rem; }
.alert-danger { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); color: #f87171; }
.alert-success { background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); color: #34d399; }

.info-note {
  background: rgba(234,179,8,0.08);
  border: 1px solid rgba(234,179,8,0.25);
  color: #fbbf24;
  border-radius: 6px;
  padding: 0.75rem 1rem;
  font-size: 0.825rem;
  line-height: 1.6;
}

/* ── Toast ───────────────────────────────────────────────────────────────── */
.toast-msg {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.875rem;
  z-index: 2000;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  max-width: 400px;
}
.toast-success {
  background: rgba(16,185,129,0.15);
  border: 1px solid rgba(16,185,129,0.4);
  color: #34d399;
}
.toast-error {
  background: rgba(239,68,68,0.15);
  border: 1px solid rgba(239,68,68,0.4);
  color: #f87171;
}
.toast-close { background: none; border: none; font-size: 1.1rem; cursor: pointer; color: inherit; padding: 0; line-height: 1; margin-left: auto; opacity: 0.7; }
.toast-close:hover { opacity: 1; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity 0.3s ease, transform 0.3s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateY(0.5rem); }

/* ── Utilities ───────────────────────────────────────────────────────────── */
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.5rem; }
.mt-3 { margin-top: 1rem; }
.mb-2 { margin-bottom: 0.5rem; }
.mb-3 { margin-bottom: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
</style>
