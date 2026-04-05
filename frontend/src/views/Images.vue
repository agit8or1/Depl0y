<template>
  <div class="images-page">

    <!-- ===== Quick Download Card ===== -->
    <div class="card quick-download-card">
      <div class="card-header">
        <h3>Quick Download to Proxmox Storage</h3>
        <span class="text-sm text-muted">Download a cloud image or ISO directly to a Proxmox node without going through this server</span>
      </div>
      <div class="quick-download-body">
        <div class="quick-download-presets">
          <button @click="openQuickDownload('Ubuntu 24.04 LTS')" class="quick-preset-btn">
            <span class="preset-icon">🟠</span>
            <span class="preset-label">Ubuntu 24.04 LTS</span>
          </button>
          <button @click="openQuickDownload('Debian 12')" class="quick-preset-btn">
            <span class="preset-icon">🔴</span>
            <span class="preset-label">Debian 12</span>
          </button>
          <button @click="openQuickDownload('AlmaLinux 9')" class="quick-preset-btn">
            <span class="preset-icon">🔵</span>
            <span class="preset-label">AlmaLinux 9</span>
          </button>
          <button @click="openQuickDownload('Rocky Linux 9')" class="quick-preset-btn">
            <span class="preset-icon">🟢</span>
            <span class="preset-label">Rocky Linux 9</span>
          </button>
          <button @click="openQuickDownload('')" class="quick-preset-btn quick-preset-custom">
            <span class="preset-icon">⬇️</span>
            <span class="preset-label">Custom URL</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Quick Download Modal -->
    <div v-if="showQuickDownloadModal" class="modal" @click="showQuickDownloadModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Quick Download to Proxmox</h3>
          <button @click="showQuickDownloadModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p class="text-muted text-sm mb-2">Downloads the file directly to a Proxmox node using the Proxmox download-url API. The file never touches this server.</p>
          <div class="form-group">
            <label class="form-label">Filename *</label>
            <input v-model="quickDownloadForm.filename" class="form-control" placeholder="e.g. noble-server-cloudimg-amd64.img" required />
          </div>
          <div class="form-group">
            <label class="form-label">Download URL *</label>
            <input v-model="quickDownloadForm.url" type="url" class="form-control" placeholder="https://cloud-images.ubuntu.com/..." required />
            <p class="text-xs text-muted mt-1">Paste the direct download URL for the image or ISO.</p>
          </div>
          <div class="form-group">
            <label class="form-label">Content Type *</label>
            <select v-model="quickDownloadForm.content" class="form-control">
              <option value="iso">ISO (iso)</option>
              <option value="vztmpl">Container Template (vztmpl)</option>
              <option value="import">Import (import)</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Checksum Algorithm</label>
            <select v-model="quickDownloadForm.checksum_algorithm" class="form-control">
              <option value="">None</option>
              <option value="sha256">SHA-256</option>
              <option value="sha512">SHA-512</option>
              <option value="md5">MD5</option>
            </select>
          </div>
          <div v-if="quickDownloadForm.checksum_algorithm" class="form-group">
            <label class="form-label">Checksum Value</label>
            <input v-model="quickDownloadForm.checksum" class="form-control" placeholder="Optional checksum for verification" />
          </div>
          <div class="form-group">
            <label class="form-label">Target Host *</label>
            <select v-model="quickDownloadForm.hostId" class="form-control" @change="onQuickHostChange">
              <option value="">Select host...</option>
              <option v-for="host in pxHosts" :key="host.id" :value="host.id">{{ host.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Target Node *</label>
            <select v-model="quickDownloadForm.node" class="form-control" @change="onQuickNodeChange" :disabled="!quickDownloadForm.hostId || quickDownloadNodesLoading">
              <option value="">{{ quickDownloadNodesLoading ? 'Loading...' : 'Select node...' }}</option>
              <option v-for="n in quickDownloadNodes" :key="n.node" :value="n.node">{{ n.node }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Target Storage *</label>
            <select v-model="quickDownloadForm.storage" class="form-control" :disabled="!quickDownloadForm.node || quickDownloadStoragesLoading">
              <option value="">{{ quickDownloadStoragesLoading ? 'Loading...' : 'Select storage...' }}</option>
              <option v-for="s in quickDownloadStorages" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
            </select>
          </div>
          <div v-if="quickDownloadRunning" class="alert alert-info mt-2">
            <p>Download task submitted to Proxmox. Monitor progress in the Proxmox task log.</p>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showQuickDownloadModal = false" class="btn btn-outline">Cancel</button>
          <button
            @click="submitQuickDownload"
            class="btn btn-primary"
            :disabled="!quickDownloadForm.url || !quickDownloadForm.filename || !quickDownloadForm.hostId || !quickDownloadForm.node || !quickDownloadForm.storage || quickDownloadRunning"
          >
            {{ quickDownloadRunning ? 'Submitting...' : 'Download to Node' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Tab Navigation -->
    <div class="images-tab-nav">
      <button
        :class="['images-tab-btn', { active: activeTab === 'isos' }]"
        @click="activeTab = 'isos'"
      >
        💿 ISO Images
      </button>
      <button
        :class="['images-tab-btn', { active: activeTab === 'cloud' }]"
        @click="activeTab = 'cloud'"
      >
        ☁️ Cloud Images
      </button>
      <button
        :class="['images-tab-btn', { active: activeTab === 'proxmox-storage' }]"
        @click="activeTab = 'proxmox-storage'; initProxmoxStorage()"
      >
        🗄️ Proxmox Storage
      </button>
    </div>

    <!-- ===== ISO Images Tab ===== -->
    <div v-if="activeTab === 'isos'">
      <div class="card">
        <div class="card-header">
          <h3>ISO Images</h3>
          <div class="flex gap-1">
            <button @click="showISOAddModal = true" class="btn btn-primary">+ Add ISO</button>
          </div>
        </div>

        <div v-if="isoLoading" class="loading-spinner"></div>

        <div v-else-if="isos.length === 0" class="text-center text-muted">
          <p>No ISO images uploaded yet.</p>
          <p class="text-sm">Upload ISOs to deploy VMs.</p>
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>OS Type</th>
                <th>Version</th>
                <th>Architecture</th>
                <th>Size</th>
                <th>Checksum</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="iso in isos" :key="iso.id">
                <td>{{ iso.name }}</td>
                <td>
                  <span class="badge badge-info">{{ formatOSType(iso.os_type) }}</span>
                </td>
                <td>{{ iso.version || 'N/A' }}</td>
                <td>{{ iso.architecture }}</td>
                <td>{{ formatBytes(iso.file_size) }}</td>
                <td class="text-xs text-muted">
                  <span v-if="iso.checksum === 'downloading...'" class="text-blue-500">
                    ⏳ Downloading...
                  </span>
                  <span v-else-if="iso.checksum === 'calculating...'" class="text-yellow-500">
                    ⚙️ Calculating checksum...
                  </span>
                  <span v-else-if="iso.checksum === 'error'" class="text-red-500">
                    ❌ Error
                  </span>
                  <span v-else>
                    {{ iso.checksum ? iso.checksum.substring(0, 16) + '...' : 'N/A' }}
                  </span>
                </td>
                <td>
                  <span v-if="iso.checksum === 'downloading...'" class="badge badge-info">
                    Downloading
                  </span>
                  <span v-else-if="iso.checksum === 'calculating...'" class="badge badge-warning">
                    Processing
                  </span>
                  <span v-else :class="['badge', iso.is_available ? 'badge-success' : 'badge-danger']">
                    {{ iso.is_available ? 'Available' : 'Unavailable' }}
                  </span>
                </td>
                <td>
                  <div class="flex gap-1">
                    <button @click="verifyISO(iso.id)" class="btn btn-outline btn-sm">Verify</button>
                    <button @click="deleteISO(iso.id)" class="btn btn-danger btn-sm">Delete</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Add ISO Modal -->
      <div v-if="showISOAddModal" class="modal" @click="closeISOModal">
        <div class="modal-content modal-large" @click.stop>
          <div class="modal-header">
            <h3>Add ISO Image</h3>
            <button @click="closeISOModal" class="btn-close">×</button>
          </div>

          <!-- Selection Mode -->
          <div v-if="!isoSelectionMode" class="modal-body selection-mode">
            <div class="selection-prompt">
              <h4>How would you like to add an ISO image?</h4>
              <p class="text-muted">Choose from popular ISOs, upload from your computer, or download from a URL</p>
            </div>
            <div class="selection-options">
              <div @click="isoSelectionMode = 'available'" class="selection-card">
                <div class="selection-icon">💿</div>
                <div class="selection-info">
                  <h5>Select from Available</h5>
                  <p>Choose from 19 verified ISOs</p>
                  <ul class="selection-list">
                    <li>Ubuntu, Debian, RHEL-based</li>
                    <li>pfSense, OPNsense, TrueNAS</li>
                    <li>Proxmox, Untangle, Zentyal</li>
                  </ul>
                </div>
                <div class="selection-arrow">→</div>
              </div>
              <div @click="isoSelectionMode = 'upload'" class="selection-card">
                <div class="selection-icon">⬆️</div>
                <div class="selection-info">
                  <h5>Upload from Computer</h5>
                  <p>Upload an ISO file from your device</p>
                  <ul class="selection-list">
                    <li>Any ISO file</li>
                    <li>Custom distributions</li>
                    <li>Local files</li>
                  </ul>
                </div>
                <div class="selection-arrow">→</div>
              </div>
              <div @click="isoSelectionMode = 'download'" class="selection-card">
                <div class="selection-icon">⬇️</div>
                <div class="selection-info">
                  <h5>Download from URL</h5>
                  <p>Provide a direct download link</p>
                  <ul class="selection-list">
                    <li>Direct ISO URLs</li>
                    <li>Mirror servers</li>
                    <li>Custom sources</li>
                  </ul>
                </div>
                <div class="selection-arrow">→</div>
              </div>
            </div>
          </div>

          <!-- Available ISOs Selection -->
          <div v-if="isoSelectionMode === 'available'" class="modal-body">
            <div class="mode-header">
              <button @click="isoSelectionMode = null" class="btn btn-outline btn-sm">← Back</button>
              <h4>Select ISO Images</h4>
              <span v-if="selectedISONames.length > 0" class="selection-count">
                {{ selectedISONames.length }} selected
              </span>
            </div>
            <p class="text-muted text-sm mb-2">Click on ISOs to select multiple.</p>
            <div class="predefined-images-grid">
              <div
                v-for="predefined in sortedPredefinedISOs"
                :key="predefined.name"
                @click="toggleISOSelection(predefined)"
                :class="['predefined-image-card', { selected: isISOSelected(predefined.name) }]"
              >
                <div class="predefined-image-icon">{{ predefined.icon }}</div>
                <div class="predefined-image-info">
                  <div class="predefined-image-name">{{ predefined.name }}</div>
                  <div class="predefined-image-details">{{ formatOSType(predefined.os_type) }} {{ predefined.version }}</div>
                </div>
                <div v-if="isISOSelected(predefined.name)" class="predefined-image-check">✓</div>
              </div>
            </div>
            <div v-if="selectedISONames.length > 0" class="selected-images-preview">
              <h5>Selected ISOs ({{ selectedISONames.length }}):</h5>
              <div class="selected-images-list">
                <span v-for="name in selectedISONames" :key="name" class="selected-image-chip">{{ name }}</span>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" @click="closeISOModal" class="btn btn-outline">Cancel</button>
              <button type="button" @click="saveSelectedISOs" :disabled="selectedISONames.length === 0" class="btn btn-primary">
                {{ `Add ${selectedISONames.length} ISO${selectedISONames.length !== 1 ? 's' : ''}` }}
              </button>
            </div>
          </div>

          <!-- Upload from Computer -->
          <form v-if="isoSelectionMode === 'upload'" @submit.prevent="uploadISO" class="modal-body">
            <div class="mode-header">
              <button type="button" @click="isoSelectionMode = null" class="btn btn-outline btn-sm">← Back</button>
              <h4>Upload ISO from Computer</h4>
            </div>
            <div class="form-group">
              <label class="form-label">ISO File *</label>
              <input type="file" @change="onFileSelected" accept=".iso" class="form-control" required />
              <p v-if="selectedFile" class="text-sm text-muted mt-1">
                Selected: {{ selectedFile.name }} ({{ formatBytes(selectedFile.size) }})
              </p>
            </div>
            <div class="form-group">
              <label class="form-label">Display Name *</label>
              <input v-model="uploadForm.name" class="form-control" required />
            </div>
            <div class="form-group">
              <label class="form-label">OS Type *</label>
              <select v-model="uploadForm.os_type" class="form-control" required>
                <option value="">Select OS</option>
                <optgroup label="Linux Server">
                  <option value="ubuntu">Ubuntu Server</option>
                  <option value="debian">Debian</option>
                  <option value="centos">CentOS</option>
                  <option value="rocky">Rocky Linux</option>
                  <option value="alma">AlmaLinux</option>
                  <option value="fedora">Fedora Server</option>
                  <option value="opensuse">openSUSE</option>
                </optgroup>
                <optgroup label="Windows">
                  <option value="windows_server_2019">Windows Server 2019</option>
                  <option value="windows_server_2022">Windows Server 2022</option>
                  <option value="windows_10">Windows 10</option>
                  <option value="windows_11">Windows 11</option>
                </optgroup>
                <optgroup label="Firewall / Network">
                  <option value="pfsense">pfSense</option>
                  <option value="opnsense">OPNsense</option>
                  <option value="vyos">VyOS</option>
                </optgroup>
                <optgroup label="Other">
                  <option value="freebsd">FreeBSD</option>
                  <option value="truenas">TrueNAS</option>
                  <option value="proxmox">Proxmox VE</option>
                  <option value="esxi">VMware ESXi</option>
                  <option value="other">Other / Custom</option>
                </optgroup>
              </select>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">Version</label>
                <input v-model="uploadForm.version" class="form-control" placeholder="22.04" />
              </div>
              <div class="form-group">
                <label class="form-label">Architecture</label>
                <select v-model="uploadForm.architecture" class="form-control">
                  <option value="amd64">amd64 (x86_64)</option>
                  <option value="arm64">arm64</option>
                </select>
              </div>
            </div>
            <div v-if="uploading" class="upload-progress">
              <div class="upload-stats">
                <div class="stat-row">
                  <span class="stat-label">Progress:</span>
                  <span class="stat-value">{{ uploadProgress }}%</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">Transferred:</span>
                  <span class="stat-value">{{ formatBytes(uploadedBytes) }} / {{ formatBytes(totalBytes) }}</span>
                </div>
                <div class="stat-row" v-if="uploadSpeed > 0">
                  <span class="stat-label">Speed:</span>
                  <span class="stat-value">{{ formatBytes(uploadSpeed) }}/s</span>
                </div>
                <div class="stat-row" v-if="uploadSpeed > 0 && uploadProgress < 100">
                  <span class="stat-label">Time remaining:</span>
                  <span class="stat-value">{{ formatTimeRemaining() }}</span>
                </div>
              </div>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" @click="closeISOModal" class="btn btn-outline" :disabled="uploading">Cancel</button>
              <button type="submit" class="btn btn-primary" :disabled="uploading || !selectedFile">
                {{ uploading ? 'Uploading...' : 'Upload ISO' }}
              </button>
            </div>
          </form>

          <!-- Download from URL -->
          <form v-if="isoSelectionMode === 'download'" @submit.prevent="downloadFromUrl" class="modal-body">
            <div class="mode-header">
              <button type="button" @click="isoSelectionMode = null" class="btn btn-outline btn-sm">← Back</button>
              <h4>Download ISO from URL</h4>
            </div>
            <div class="form-group">
              <label class="form-label">ISO URL *</label>
              <input v-model="downloadForm.url" type="url" class="form-control" placeholder="https://example.com/path/to/image.iso" required />
              <p class="text-xs text-muted mt-1">Direct link to the ISO file</p>
            </div>
            <div class="form-group">
              <label class="form-label">Display Name *</label>
              <input v-model="downloadForm.name" class="form-control" required />
            </div>
            <div class="form-group">
              <label class="form-label">OS Type *</label>
              <select v-model="downloadForm.os_type" class="form-control" required>
                <option value="">Select OS</option>
                <optgroup label="Linux Server">
                  <option value="ubuntu">Ubuntu Server</option>
                  <option value="debian">Debian</option>
                  <option value="centos">CentOS</option>
                  <option value="rocky">Rocky Linux</option>
                  <option value="alma">AlmaLinux</option>
                  <option value="fedora">Fedora Server</option>
                  <option value="opensuse">openSUSE</option>
                </optgroup>
                <optgroup label="Windows">
                  <option value="windows_server_2019">Windows Server 2019</option>
                  <option value="windows_server_2022">Windows Server 2022</option>
                  <option value="windows_10">Windows 10</option>
                  <option value="windows_11">Windows 11</option>
                </optgroup>
                <optgroup label="Firewall / Network">
                  <option value="pfsense">pfSense</option>
                  <option value="opnsense">OPNsense</option>
                  <option value="vyos">VyOS</option>
                </optgroup>
                <optgroup label="Other">
                  <option value="freebsd">FreeBSD</option>
                  <option value="truenas">TrueNAS</option>
                  <option value="proxmox">Proxmox VE</option>
                  <option value="esxi">VMware ESXi</option>
                  <option value="other">Other / Custom</option>
                </optgroup>
              </select>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">Version</label>
                <input v-model="downloadForm.version" class="form-control" placeholder="22.04" />
              </div>
              <div class="form-group">
                <label class="form-label">Architecture</label>
                <select v-model="downloadForm.architecture" class="form-control">
                  <option value="amd64">amd64 (x86_64)</option>
                  <option value="arm64">arm64</option>
                </select>
              </div>
            </div>
            <div v-if="isoDownloading" class="upload-progress">
              <p class="text-center text-muted">Downloading ISO from URL...</p>
              <div class="loading-spinner"></div>
            </div>
            <div class="modal-footer">
              <button type="button" @click="closeISOModal" class="btn btn-outline" :disabled="isoDownloading">Cancel</button>
              <button type="submit" class="btn btn-primary" :disabled="isoDownloading">
                {{ isoDownloading ? 'Downloading...' : 'Download ISO' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- ===== Cloud Images Tab ===== -->
    <div v-if="activeTab === 'cloud'">
      <div class="card">
        <div class="card-header">
          <h3>Cloud Images</h3>
          <div class="flex gap-1">
            <button @click="fetchLatestImages" class="btn btn-outline" :disabled="fetchingLatest">
              {{ fetchingLatest ? '🔄 Updating...' : '⬇️ Fetch Latest' }}
            </button>
            <button @click="checkAllTemplates" class="btn btn-outline" :disabled="checkingTemplates">
              {{ checkingTemplates ? '🔄 Checking...' : '🔍 Check Templates' }}
            </button>
            <button @click="openSetupModal" class="btn btn-outline">⚙️ Setup Templates</button>
            <button @click="showCloudAddModal = true" class="btn btn-primary">+ Add Cloud Image</button>
          </div>
        </div>

        <!-- Template Status Section -->
        <div v-if="templateStatus && Object.keys(templateStatus).length > 0" class="template-status-section">
          <h4 class="template-status-title">Template Status by Node</h4>
          <div class="template-status-grid">
            <div v-for="nodeStatus in templateStatus" :key="nodeStatus.node_id" class="node-status-card">
              <div class="node-status-header">
                <span class="node-name">{{ nodeStatus.node_name }}</span>
                <span class="template-count">{{ getTemplateCount(nodeStatus.templates) }} templates</span>
              </div>
              <div class="template-list">
                <div v-for="(exists, vmid) in nodeStatus.templates" :key="vmid" class="template-item">
                  <span class="template-vmid">{{ vmid }}</span>
                  <span :class="['template-badge', exists ? 'exists' : 'missing']">
                    {{ exists ? '✓ Exists' : '✗ Missing' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="cloudLoading" class="loading-spinner"></div>

        <div v-else-if="images.length === 0" class="text-center text-muted">
          <p>No cloud images configured yet.</p>
          <p class="text-sm">Add cloud images for fast VM deployment.</p>
        </div>

        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>OS Type</th>
                <th>Version</th>
                <th>Architecture</th>
                <th>Size</th>
                <th>Download Status</th>
                <th>Template Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="image in sortedImages" :key="image.id">
                <td>{{ image.name }}</td>
                <td>
                  <span class="badge badge-info">{{ formatOSType(image.os_type) }}</span>
                </td>
                <td>{{ image.version || 'N/A' }}</td>
                <td>{{ image.architecture }}</td>
                <td>{{ image.file_size ? formatBytes(image.file_size) : 'Unknown' }}</td>
                <td>
                  <div v-if="image.download_status === 'downloading'" class="download-progress">
                    <div class="progress-bar-container">
                      <div class="progress-bar-fill" :style="{ width: image.download_progress + '%' }"></div>
                    </div>
                    <div class="download-progress-row">
                      <span class="text-xs text-muted">{{ image.download_progress }}%</span>
                      <button @click="cancelDownload(image.id)" class="btn btn-danger btn-xs ml-1">Cancel</button>
                    </div>
                  </div>
                  <span v-else-if="image.is_downloaded" class="badge badge-success">Downloaded</span>
                  <span v-else-if="image.download_status === 'error'" class="badge badge-danger">Error</span>
                  <span v-else class="badge badge-secondary">Not Downloaded</span>
                </td>
                <td>
                  <span v-if="image.template_vmid" class="badge badge-success">Template {{ image.template_vmid }}</span>
                  <span v-else-if="image.is_downloaded" class="badge badge-warning">Not templated</span>
                  <span v-else class="badge badge-secondary">—</span>
                </td>
                <td>
                  <div class="flex gap-1">
                    <button
                      v-if="!image.is_downloaded && image.download_status !== 'downloading'"
                      @click="downloadImage(image.id)"
                      class="btn btn-primary btn-sm"
                    >
                      Download
                    </button>
                    <button
                      v-if="image.is_downloaded && !image.template_vmid"
                      @click="deleteLocalCopy(image.id)"
                      class="btn btn-outline btn-sm"
                      title="Delete local copy to free disk space"
                    >
                      Del Local
                    </button>
                    <button @click="editImage(image)" class="btn btn-outline btn-sm">Edit</button>
                    <button @click="deleteImage(image.id)" class="btn btn-danger btn-sm">Delete</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Setup Templates Modal -->
      <div v-if="showSetupModal" class="modal" @click="showSetupModal = false">
        <div class="modal-content" @click.stop>
          <div class="modal-header">
            <h3>Setup Cloud Image Templates</h3>
            <button @click="showSetupModal = false" class="btn-close">×</button>
          </div>
          <div class="modal-body">
            <p class="text-muted mb-2">Automatically create cloud image templates on a Proxmox node.</p>
            <div class="form-group">
              <label class="form-label">Select Proxmox Node *</label>
              <select v-model="setupForm.selectedNodeId" class="form-control" required>
                <option value="">Choose a node...</option>
                <option v-for="node in nodes" :key="node.id" :value="node.id">
                  {{ node.node_name }} ({{ node.proxmox_host_name }})
                </option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Select Cloud Images to Setup *</label>
              <div class="checkbox-list">
                <label v-for="image in sortedImages" :key="image.id" class="checkbox-item">
                  <input type="checkbox" :value="image.id" v-model="setupForm.selectedImageIds" />
                  <span>{{ image.name }} ({{ image.os_type }} {{ image.version }})</span>
                </label>
              </div>
              <p class="text-xs text-muted mt-1">Selected images will be created as templates 9000+</p>
            </div>
            <div v-if="settingUpTemplates" class="alert alert-info">
              <p>Setting up templates... This may take several minutes.</p>
              <p class="text-sm">Templates are being downloaded and configured in the background.</p>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showSetupModal = false" class="btn btn-outline" :disabled="settingUpTemplates">Cancel</button>
            <button
              @click="setupTemplates"
              class="btn btn-primary"
              :disabled="!setupForm.selectedNodeId || setupForm.selectedImageIds.length === 0 || settingUpTemplates"
            >
              {{ settingUpTemplates ? 'Setting Up...' : 'Setup Templates' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Add/Edit Cloud Image Modal -->
      <div v-if="showCloudAddModal" class="modal" @click="showCloudAddModal = false">
        <div class="modal-content modal-large" @click.stop>
          <div class="modal-header">
            <h3>{{ editingImage ? 'Edit' : 'Add' }} Cloud Image</h3>
            <button @click="closeCloudModal" class="btn-close">×</button>
          </div>

          <!-- Selection Mode -->
          <div v-if="!editingImage && !imageSelectionMode" class="modal-body selection-mode">
            <div class="selection-prompt">
              <h4>How would you like to add a cloud image?</h4>
              <p class="text-muted">Choose from popular distributions or add your own custom image</p>
            </div>
            <div class="selection-options">
              <div @click="imageSelectionMode = 'available'" class="selection-card">
                <div class="selection-icon">📦</div>
                <div class="selection-info">
                  <h5>Select from Available</h5>
                  <p>Choose from 15 cloud-ready images</p>
                  <ul class="selection-list">
                    <li>Ubuntu, Debian, RHEL-based</li>
                    <li>Fedora, CentOS, openSUSE</li>
                    <li>Arch, Alpine, Flatcar Container</li>
                  </ul>
                </div>
                <div class="selection-arrow">→</div>
              </div>
              <div @click="imageSelectionMode = 'custom'" class="selection-card">
                <div class="selection-icon">⚙️</div>
                <div class="selection-info">
                  <h5>Add Custom Image</h5>
                  <p>Enter details for your own cloud image</p>
                  <ul class="selection-list">
                    <li>Custom download URL</li>
                    <li>Any Linux distribution</li>
                    <li>Private or local images</li>
                  </ul>
                </div>
                <div class="selection-arrow">→</div>
              </div>
            </div>
          </div>

          <!-- Available Images Selection -->
          <div v-if="!editingImage && imageSelectionMode === 'available'" class="modal-body">
            <div class="mode-header">
              <button @click="imageSelectionMode = null" class="btn btn-outline btn-sm">← Back</button>
              <h4>Select Cloud Images</h4>
              <span v-if="selectedImageNames.length > 0" class="selection-count">
                {{ selectedImageNames.length }} selected
              </span>
            </div>
            <p class="text-muted text-sm mb-2">Click on images to select multiple.</p>
            <div class="predefined-images-grid">
              <div
                v-for="predefined in sortedPredefinedImages"
                :key="predefined.name"
                @click="toggleImageSelection(predefined)"
                :class="['predefined-image-card', { selected: isImageSelected(predefined.name) }]"
              >
                <div class="predefined-image-icon">{{ predefined.icon }}</div>
                <div class="predefined-image-info">
                  <div class="predefined-image-name">{{ predefined.name }}</div>
                  <div class="predefined-image-details">{{ predefined.os_type }} {{ predefined.version }}</div>
                </div>
                <div v-if="isImageSelected(predefined.name)" class="predefined-image-check">✓</div>
              </div>
            </div>
            <div v-if="selectedImageNames.length > 0" class="selected-images-preview">
              <h5>Selected Images ({{ selectedImageNames.length }}):</h5>
              <div class="selected-images-list">
                <span v-for="name in selectedImageNames" :key="name" class="selected-image-chip">{{ name }}</span>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" @click="closeCloudModal" class="btn btn-outline">Cancel</button>
              <button
                type="button"
                @click="saveSelectedImages"
                :disabled="selectedImageNames.length === 0 || cloudSaving"
                class="btn btn-primary"
              >
                {{ cloudSaving ? 'Adding...' : `Add ${selectedImageNames.length} Image${selectedImageNames.length !== 1 ? 's' : ''}` }}
              </button>
            </div>
          </div>

          <!-- Custom Image Form -->
          <form v-if="editingImage || imageSelectionMode === 'custom'" @submit.prevent="saveImage" class="modal-body">
            <div v-if="!editingImage" class="mode-header">
              <button type="button" @click="imageSelectionMode = null" class="btn btn-outline btn-sm">← Back</button>
              <h4>Custom Cloud Image Details</h4>
            </div>
            <div class="form-group">
              <label class="form-label">Display Name *</label>
              <input v-model="imageForm.name" class="form-control" required placeholder="Ubuntu 24.04 LTS Cloud Image" />
            </div>
            <div class="form-group">
              <label class="form-label">Filename *</label>
              <input v-model="imageForm.filename" class="form-control" required placeholder="ubuntu-24.04-server-cloudimg-amd64.img" />
            </div>
            <div class="form-group">
              <label class="form-label">Download URL *</label>
              <input v-model="imageForm.download_url" class="form-control" required type="url" placeholder="https://cloud-images.ubuntu.com/..." />
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">OS Type *</label>
                <select v-model="imageForm.os_type" class="form-control" required>
                  <option value="">Select OS</option>
                  <option value="ubuntu">Ubuntu</option>
                  <option value="debian">Debian</option>
                  <option value="centos">CentOS</option>
                  <option value="rocky">Rocky Linux</option>
                  <option value="alma">AlmaLinux</option>
                  <option value="fedora">Fedora</option>
                  <option value="opensuse">openSUSE</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Version</label>
                <input v-model="imageForm.version" class="form-control" placeholder="24.04" />
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">Architecture</label>
                <select v-model="imageForm.architecture" class="form-control">
                  <option value="amd64">amd64 (x86_64)</option>
                  <option value="arm64">arm64</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">SHA256 Checksum</label>
                <input v-model="imageForm.checksum" class="form-control" placeholder="Optional" />
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" @click="closeCloudModal" class="btn btn-outline">Cancel</button>
              <button type="submit" :disabled="cloudSaving" class="btn btn-primary">
                {{ cloudSaving ? 'Saving...' : (editingImage ? 'Update' : 'Add') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- ===== Proxmox Storage Tab ===== -->
    <div v-if="activeTab === 'proxmox-storage'">
      <div class="card">
        <div class="card-header">
          <h3>Proxmox Storage Browser</h3>
          <button @click="refreshProxmoxStorage" class="btn btn-outline" :disabled="pxStorageLoading">
            {{ pxStorageLoading ? '🔄 Loading...' : '🔄 Refresh' }}
          </button>
        </div>

        <!-- Selectors row -->
        <div class="px-storage-selectors">
          <!-- Host selector -->
          <div class="form-group">
            <label class="form-label">Host</label>
            <select v-model="pxSelectedHostId" class="form-control" @change="onPxHostChange">
              <option value="">Select host...</option>
              <option v-for="host in pxHosts" :key="host.id" :value="host.id">
                {{ host.name }}
              </option>
            </select>
          </div>

          <!-- Node selector -->
          <div class="form-group">
            <label class="form-label">Node</label>
            <select v-model="pxSelectedNode" class="form-control" @change="onPxNodeChange" :disabled="!pxSelectedHostId || pxNodesLoading">
              <option value="">{{ pxNodesLoading ? 'Loading...' : 'Select node...' }}</option>
              <option v-for="node in pxNodes" :key="node.node" :value="node.node">
                {{ node.node }}
              </option>
            </select>
          </div>

          <!-- Storage selector -->
          <div class="form-group">
            <label class="form-label">Storage</label>
            <select v-model="pxSelectedStorage" class="form-control" @change="onPxStorageChange" :disabled="!pxSelectedNode || pxStoragesLoading">
              <option value="">{{ pxStoragesLoading ? 'Loading...' : 'Select storage...' }}</option>
              <option v-for="stor in pxStorages" :key="stor.storage" :value="stor.storage">
                {{ stor.storage }} ({{ stor.type }})
              </option>
            </select>
          </div>
        </div>

        <!-- Content type filter -->
        <div v-if="pxSelectedStorage" class="px-content-filter">
          <span class="filter-label">Content type:</span>
          <div class="filter-btns">
            <button
              v-for="ft in ['All', 'ISO', 'Images']"
              :key="ft"
              :class="['btn btn-sm', pxContentFilter === ft ? 'btn-primary' : 'btn-outline']"
              @click="pxContentFilter = ft"
            >
              {{ ft }}
            </button>
          </div>
        </div>

        <!-- ISO Upload Section -->
        <div v-if="pxSelectedStorage && pxStorageSupportsIso" class="px-upload-section">
          <div class="px-upload-header" @click="pxShowUpload = !pxShowUpload">
            <span class="px-upload-title">Upload ISO</span>
            <span class="px-upload-toggle">{{ pxShowUpload ? '▲' : '▼' }}</span>
          </div>
          <div v-if="pxShowUpload" class="px-upload-body">
            <div class="px-upload-row">
              <div class="form-group" style="flex:1;margin-bottom:0">
                <input
                  type="file"
                  accept=".iso,.img"
                  @change="onPxFileSelected"
                  class="form-control"
                  :disabled="pxUploading"
                />
                <p v-if="pxUploadFile" class="text-sm text-muted mt-1">
                  {{ pxUploadFile.name }} ({{ formatBytes(pxUploadFile.size) }})
                </p>
              </div>
              <button
                class="btn btn-primary"
                :disabled="!pxUploadFile || pxUploading"
                @click="uploadToProxmoxStorage"
                style="white-space:nowrap"
              >
                {{ pxUploading ? 'Uploading...' : 'Upload' }}
              </button>
            </div>
            <div v-if="pxUploading" class="px-upload-progress">
              <div class="px-progress-bar">
                <div class="px-progress-fill" :style="{ width: pxUploadProgress + '%' }"></div>
              </div>
              <span class="px-progress-label">{{ pxUploadProgress }}%</span>
            </div>
          </div>
        </div>

        <!-- Loading spinner -->
        <div v-if="pxStorageLoading" class="loading-spinner"></div>

        <!-- Empty states -->
        <div v-else-if="!pxSelectedStorage" class="text-center text-muted px-empty-state">
          <p>Select a host, node, and storage to browse files.</p>
        </div>

        <div v-else-if="pxFilteredContent.length === 0" class="text-center text-muted px-empty-state">
          <p>No files found in this storage for the selected content type.</p>
        </div>

        <!-- Content table -->
        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Size</th>
                <th>Checksum</th>
                <th>Full Path (volid)</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pxFilteredContent" :key="item.volid">
                <td class="px-filename">{{ pxBasename(item.volid) }}</td>
                <td>
                  <span :class="['badge', pxFormatBadgeClass(item.format || item.content)]">
                    {{ item.format || item.content || 'unknown' }}
                  </span>
                </td>
                <td>{{ item.size ? formatBytes(item.size) : '—' }}</td>
                <td class="text-xs text-muted px-checksum">
                  <span v-if="item.csum" :title="item.csum">{{ item.csum.substring(0, 12) }}...</span>
                  <span v-else class="text-muted">—</span>
                </td>
                <td class="text-xs text-muted px-volid">{{ item.volid }}</td>
                <td>
                  <div class="flex gap-1">
                    <button @click="openCopyToNode(item)" class="btn btn-outline btn-sm">Copy to Node</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Download URL section (below the upload section) -->
        <div v-if="pxSelectedStorage" class="px-upload-section">
          <div class="px-upload-header" @click="pxShowDownloadUrl = !pxShowDownloadUrl">
            <span class="px-upload-title">Download URL to Storage</span>
            <span class="px-upload-toggle">{{ pxShowDownloadUrl ? '▲' : '▼' }}</span>
          </div>
          <div v-if="pxShowDownloadUrl" class="px-upload-body">
            <div class="form-group">
              <label class="form-label">Filename *</label>
              <input v-model="pxDownloadUrlForm.filename" class="form-control" placeholder="e.g. noble-server-cloudimg-amd64.img" />
            </div>
            <div class="form-group">
              <label class="form-label">URL *</label>
              <input v-model="pxDownloadUrlForm.url" type="url" class="form-control" placeholder="https://..." />
            </div>
            <div class="form-group">
              <label class="form-label">Content Type</label>
              <select v-model="pxDownloadUrlForm.content" class="form-control">
                <option value="iso">ISO (iso)</option>
                <option value="vztmpl">Container Template (vztmpl)</option>
                <option value="import">Import (import)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Checksum Algorithm</label>
              <select v-model="pxDownloadUrlForm.checksum_algorithm" class="form-control">
                <option value="">None</option>
                <option value="sha256">SHA-256</option>
                <option value="sha512">SHA-512</option>
                <option value="md5">MD5</option>
              </select>
            </div>
            <div v-if="pxDownloadUrlForm.checksum_algorithm" class="form-group">
              <label class="form-label">Checksum Value</label>
              <input v-model="pxDownloadUrlForm.checksum" class="form-control" placeholder="Optional" />
            </div>
            <div class="px-upload-row" style="justify-content: flex-end">
              <button
                class="btn btn-primary"
                :disabled="!pxDownloadUrlForm.url || !pxDownloadUrlForm.filename || pxDownloadingUrl"
                @click="submitDownloadUrlToStorage"
              >
                {{ pxDownloadingUrl ? 'Submitting...' : 'Download to Storage' }}
              </button>
            </div>
            <div v-if="pxDownloadUrlTaskId" class="alert alert-info mt-1">
              <p>Task submitted to Proxmox (UPID: {{ pxDownloadUrlTaskId }}). Monitor in the Proxmox task log.</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Copy to Node Modal -->
      <div v-if="showCopyToNodeModal" class="modal" @click="showCopyToNodeModal = false">
        <div class="modal-content" @click.stop>
          <div class="modal-header">
            <h3>Copy to Another Node</h3>
            <button @click="showCopyToNodeModal = false" class="btn-close">×</button>
          </div>
          <div class="modal-body">
            <p class="text-muted text-sm mb-2">
              Copy <strong class="text-white">{{ copyToNodeItem ? pxBasename(copyToNodeItem.volid) : '' }}</strong> to another node's storage using Proxmox download-url.
            </p>
            <div class="form-group">
              <label class="form-label">Target Host *</label>
              <select v-model="copyToNodeForm.hostId" class="form-control" @change="onCopyHostChange">
                <option value="">Select host...</option>
                <option v-for="host in pxHosts" :key="host.id" :value="host.id">{{ host.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Target Node *</label>
              <select v-model="copyToNodeForm.node" class="form-control" @change="onCopyNodeChange" :disabled="!copyToNodeForm.hostId || copyToNodeNodesLoading">
                <option value="">{{ copyToNodeNodesLoading ? 'Loading...' : 'Select node...' }}</option>
                <option v-for="n in copyToNodeNodes" :key="n.node" :value="n.node">{{ n.node }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Target Storage *</label>
              <select v-model="copyToNodeForm.storage" class="form-control" :disabled="!copyToNodeForm.node || copyToNodeStoragesLoading">
                <option value="">{{ copyToNodeStoragesLoading ? 'Loading...' : 'Select storage...' }}</option>
                <option v-for="s in copyToNodeStorages" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Download URL *</label>
              <input v-model="copyToNodeForm.url" type="url" class="form-control" placeholder="https://... (source URL for the file)" />
              <p class="text-xs text-muted mt-1">Proxmox will download from this URL directly. Provide the original source URL for the file.</p>
            </div>
            <div v-if="copyToNodeRunning" class="alert alert-info mt-1">
              <p>Task submitted to Proxmox. Monitor progress in the Proxmox task log.</p>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showCopyToNodeModal = false" class="btn btn-outline">Cancel</button>
            <button
              @click="submitCopyToNode"
              class="btn btn-primary"
              :disabled="!copyToNodeForm.hostId || !copyToNodeForm.node || !copyToNodeForm.storage || !copyToNodeForm.url || copyToNodeRunning"
            >
              {{ copyToNodeRunning ? 'Submitting...' : 'Copy to Node' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'Images',
  setup() {
    const toast = useToast()
    const activeTab = ref('isos')

    // ===== ISO Images State =====
    const isos = ref([])
    const isoLoading = ref(false)
    const uploading = ref(false)
    const isoDownloading = ref(false)
    const uploadProgress = ref(0)
    const uploadedBytes = ref(0)
    const totalBytes = ref(0)
    const uploadSpeed = ref(0)
    const showISOAddModal = ref(false)
    const isoSelectionMode = ref(null)
    const selectedISONames = ref([])
    const selectedFile = ref(null)
    let uploadStartTime = null

    const uploadForm = ref({ name: '', os_type: '', version: '', architecture: 'amd64' })
    const downloadForm = ref({ url: '', name: '', os_type: '', version: '', architecture: 'amd64' })

    const predefinedISOs = ref([
      { name: 'Ubuntu 24.04 LTS Server', filename: 'ubuntu-24.04.3-live-server-amd64.iso', os_type: 'ubuntu', version: '24.04.3', architecture: 'amd64', download_url: 'https://releases.ubuntu.com/24.04/ubuntu-24.04.3-live-server-amd64.iso', icon: '🟠' },
      { name: 'Ubuntu 22.04 LTS Server', filename: 'ubuntu-22.04-live-server-amd64.iso', os_type: 'ubuntu', version: '22.04', architecture: 'amd64', download_url: 'https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso', icon: '🟠' },
      { name: 'Ubuntu 20.04 LTS Server', filename: 'ubuntu-20.04-live-server-amd64.iso', os_type: 'ubuntu', version: '20.04', architecture: 'amd64', download_url: 'https://releases.ubuntu.com/20.04/ubuntu-20.04.6-live-server-amd64.iso', icon: '🟠' },
      { name: 'Debian 13 (Trixie)', filename: 'debian-13.2.0-amd64-netinst.iso', os_type: 'debian', version: '13.2', architecture: 'amd64', download_url: 'https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.2.0-amd64-netinst.iso', icon: '🔴' },
      { name: 'Rocky Linux 9', filename: 'Rocky-9-latest-x86_64-minimal.iso', os_type: 'rocky', version: '9', architecture: 'amd64', download_url: 'https://download.rockylinux.org/pub/rocky/9/isos/x86_64/Rocky-9-latest-x86_64-minimal.iso', icon: '🟢' },
      { name: 'Rocky Linux 8', filename: 'Rocky-8-x86_64-minimal.iso', os_type: 'rocky', version: '8', architecture: 'amd64', download_url: 'https://download.rockylinux.org/pub/rocky/8/isos/x86_64/Rocky-8.10-x86_64-minimal.iso', icon: '🟢' },
      { name: 'AlmaLinux 9', filename: 'AlmaLinux-9-latest-x86_64-minimal.iso', os_type: 'alma', version: '9', architecture: 'amd64', download_url: 'https://repo.almalinux.org/almalinux/9/isos/x86_64/AlmaLinux-9-latest-x86_64-minimal.iso', icon: '🔵' },
      { name: 'AlmaLinux 8', filename: 'AlmaLinux-8-x86_64-minimal.iso', os_type: 'alma', version: '8', architecture: 'amd64', download_url: 'https://repo.almalinux.org/almalinux/8/isos/x86_64/AlmaLinux-8.10-x86_64-minimal.iso', icon: '🔵' },
      { name: 'Fedora Server 41', filename: 'Fedora-Server-41.iso', os_type: 'fedora', version: '41', architecture: 'amd64', download_url: 'https://download.fedoraproject.org/pub/fedora/linux/releases/41/Server/x86_64/iso/Fedora-Server-netinst-x86_64-41-1.4.iso', icon: '🔷' },
      { name: 'CentOS Stream 9', filename: 'CentOS-Stream-9.iso', os_type: 'centos', version: '9', architecture: 'amd64', download_url: 'https://mirrors.ocf.berkeley.edu/centos-stream/9-stream/BaseOS/x86_64/iso/CentOS-Stream-9-latest-x86_64-dvd1.iso', icon: '🟣' },
      { name: 'openSUSE Leap 15.6', filename: 'openSUSE-Leap-15.6-NET-x86_64-Media.iso', os_type: 'other', version: '15.6', architecture: 'amd64', download_url: 'https://download.opensuse.org/distribution/leap/15.6/iso/openSUSE-Leap-15.6-NET-x86_64-Media.iso', icon: '🟢' },
      { name: 'pfSense CE 2.7.2', filename: 'pfSense-CE-2.7.2-RELEASE-amd64.iso', os_type: 'pfsense', version: '2.7.2', architecture: 'amd64', download_url: 'https://repo.ialab.dsu.edu/pfsense/pfSense-CE-2.7.2-RELEASE-amd64.iso.gz', icon: '🔥' },
      { name: 'OPNsense 24.7', filename: 'OPNsense-24.7-dvd-amd64.iso', os_type: 'opnsense', version: '24.7', architecture: 'amd64', download_url: 'https://mirrors.dotsrc.org/opnsense/releases/24.7/OPNsense-24.7-dvd-amd64.iso.bz2', icon: '🛡️' },
      { name: 'FreeBSD 14.2', filename: 'FreeBSD-14.2-RELEASE-amd64-disc1.iso', os_type: 'freebsd', version: '14.2', architecture: 'amd64', download_url: 'https://download.freebsd.org/releases/amd64/amd64/ISO-IMAGES/14.2/FreeBSD-14.2-RELEASE-amd64-disc1.iso', icon: '👹' },
      { name: 'TrueNAS CORE 13.0-U6.2', filename: 'TrueNAS-13.0-U6.2.iso', os_type: 'truenas', version: '13.0-U6.2', architecture: 'amd64', download_url: 'https://download-core.sys.truenas.net/13.0/STABLE/U6.2/x64/TrueNAS-13.0-U6.2.iso', icon: '💾' },
      { name: 'Proxmox VE 8.3', filename: 'proxmox-ve_8.3-1.iso', os_type: 'proxmox', version: '8.3', architecture: 'amd64', download_url: 'https://www.proxmox.com/en/downloads?task=callelement&format=raw&item_id=859&element=f85c494b-2b32-4109-b8c1-083cca2b7db6&method=download', icon: '📦' },
      { name: 'Untangle NG Firewall 16.3', filename: 'ngfw-untangle-16.3.2-amd64.iso', os_type: 'other', version: '16.3.2', architecture: 'amd64', download_url: 'https://downloads.untangle.com/public/current-release/NGFW/ngfw-untangle-16.3.2-amd64.iso', icon: '🛡️' },
      { name: 'Alpine Linux 3.21', filename: 'alpine-virt-3.21.0-x86_64.iso', os_type: 'other', version: '3.21.0', architecture: 'amd64', download_url: 'https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/x86_64/alpine-virt-3.21.0-x86_64.iso', icon: '⛰️' },
      { name: 'Zentyal Server 8.0', filename: 'zentyal-8.0-development-amd64.iso', os_type: 'other', version: '8.0', architecture: 'amd64', download_url: 'https://download.zentyal.com/zentyal-8.0-development-amd64.iso', icon: '🏢' }
    ])

    const sortedPredefinedISOs = computed(() =>
      [...predefinedISOs.value].sort((a, b) => a.name.localeCompare(b.name))
    )

    const toggleISOSelection = (predefined) => {
      const index = selectedISONames.value.indexOf(predefined.name)
      if (index > -1) selectedISONames.value.splice(index, 1)
      else selectedISONames.value.push(predefined.name)
    }

    const isISOSelected = (isoName) => selectedISONames.value.includes(isoName)

    const getSelectedISOs = () =>
      predefinedISOs.value.filter(iso => selectedISONames.value.includes(iso.name))

    const fetchISOs = async () => {
      isoLoading.value = true
      try {
        const response = await api.isos.list()
        isos.value = response.data.sort((a, b) => a.name.localeCompare(b.name))
      } catch (error) {
        console.error('Failed to fetch ISOs:', error)
      } finally {
        isoLoading.value = false
      }
    }

    const onFileSelected = (event) => {
      const file = event.target.files[0]
      if (file) {
        selectedFile.value = file
        if (!uploadForm.value.name) uploadForm.value.name = file.name.replace('.iso', '')
      }
    }

    const saveSelectedISOs = () => {
      if (selectedISONames.value.length === 0) { toast.error('Please select at least one ISO'); return }
      const selectedISOs = getSelectedISOs()
      const count = selectedISOs.length
      selectedISOs.forEach(iso => {
        api.isos.downloadFromUrl({
          url: iso.download_url, name: iso.name, os_type: iso.os_type,
          version: iso.version, architecture: iso.architecture
        }).catch(error => console.error(`Failed to queue ${iso.name}:`, error))
      })
      toast.success(`Queued ${count} ISO${count > 1 ? 's' : ''} for download`)
      closeISOModal()
      setTimeout(() => fetchISOs(), 1500)
    }

    const uploadISO = async () => {
      if (!selectedFile.value) return
      uploading.value = true
      uploadProgress.value = 0
      uploadStartTime = Date.now()
      try {
        const formData = new FormData()
        formData.append('file', selectedFile.value)
        formData.append('name', uploadForm.value.name)
        formData.append('os_type', uploadForm.value.os_type)
        formData.append('version', uploadForm.value.version)
        formData.append('architecture', uploadForm.value.architecture)
        const onUploadProgress = (progressEvent) => {
          if (progressEvent.total) {
            uploadProgress.value = Math.round((progressEvent.loaded * 50) / progressEvent.total)
            uploadedBytes.value = progressEvent.loaded
            totalBytes.value = progressEvent.total
            const elapsedTime = (Date.now() - uploadStartTime) / 1000
            if (elapsedTime > 0) uploadSpeed.value = progressEvent.loaded / elapsedTime
          }
        }
        const response = await api.isos.upload(formData, onUploadProgress)
        const isoId = response.data.id
        toast.info('Upload complete, processing file...', { timeout: 2000 })
        let backendComplete = false
        while (!backendComplete) {
          await new Promise(resolve => setTimeout(resolve, 500))
          try {
            const progressResponse = await api.isos.getProgress(isoId)
            const backendProgress = progressResponse.data
            if (backendProgress.status === 'completed') {
              uploadProgress.value = 100
              backendComplete = true
              toast.success('ISO uploaded and processed successfully')
            } else if (backendProgress.status === 'error') {
              throw new Error(backendProgress.message || 'Processing failed')
            } else {
              uploadProgress.value = 50 + Math.round(backendProgress.progress / 2)
            }
          } catch (error) {
            backendComplete = true
            uploadProgress.value = 100
          }
        }
        await new Promise(resolve => setTimeout(resolve, 500))
        closeISOModal()
        await fetchISOs()
      } catch (error) {
        console.error('Failed to upload ISO:', error)
        toast.error('Failed to upload ISO: ' + (error.message || 'Unknown error'))
      } finally {
        uploading.value = false
        uploadProgress.value = 0
        uploadedBytes.value = 0
        totalBytes.value = 0
        uploadSpeed.value = 0
      }
    }

    const verifyISO = async (isoId) => {
      const loadingToast = toast.info('Checking ISO checksum...', { timeout: false })
      try {
        const response = await api.isos.verify(isoId)
        toast.dismiss(loadingToast)
        if (response.data.status === 'valid') toast.success('ISO checksum is valid')
        else toast.error('ISO checksum verification failed')
      } catch (error) {
        toast.dismiss(loadingToast)
        console.error('Failed to verify ISO:', error)
      }
    }

    const deleteISO = async (isoId) => {
      if (!confirm('Are you sure you want to delete this ISO image?')) return
      try {
        await api.isos.delete(isoId)
        toast.success('ISO deleted successfully')
        await fetchISOs()
      } catch (error) {
        console.error('Failed to delete ISO:', error)
      }
    }

    const formatTimeRemaining = () => {
      if (uploadSpeed.value === 0 || uploadedBytes.value === 0) return 'Calculating...'
      const remainingBytes = totalBytes.value - uploadedBytes.value
      const secondsRemaining = remainingBytes / uploadSpeed.value
      if (secondsRemaining < 60) return Math.ceil(secondsRemaining) + 's'
      else if (secondsRemaining < 3600) {
        const minutes = Math.floor(secondsRemaining / 60)
        const seconds = Math.ceil(secondsRemaining % 60)
        return `${minutes}m ${seconds}s`
      } else {
        const hours = Math.floor(secondsRemaining / 3600)
        const minutes = Math.ceil((secondsRemaining % 3600) / 60)
        return `${hours}h ${minutes}m`
      }
    }

    const downloadFromUrl = async () => {
      isoDownloading.value = true
      try {
        await api.isos.downloadFromUrl(downloadForm.value)
        toast.success('ISO download started successfully')
        closeISOModal()
        await fetchISOs()
      } catch (error) {
        console.error('Failed to download ISO:', error)
        toast.error('Failed to download ISO')
      } finally {
        isoDownloading.value = false
      }
    }

    const closeISOModal = () => {
      showISOAddModal.value = false
      isoSelectionMode.value = null
      selectedISONames.value = []
      uploadForm.value = { name: '', os_type: '', version: '', architecture: 'amd64' }
      downloadForm.value = { url: '', name: '', os_type: '', version: '', architecture: 'amd64' }
      selectedFile.value = null
      uploadedBytes.value = 0
      totalBytes.value = 0
      uploadSpeed.value = 0
    }

    // ===== Cloud Images State =====
    const images = ref([])
    const nodes = ref([])
    const cloudLoading = ref(false)
    const showCloudAddModal = ref(false)
    const showSetupModal = ref(false)
    const editingImage = ref(null)
    const cloudSaving = ref(false)
    const imageSelectionMode = ref(null)
    const selectedImageNames = ref([])
    const settingUpTemplates = ref(false)
    const templateStatus = ref({})
    const checkingTemplates = ref(false)
    const fetchingLatest = ref(false)
    let refreshInterval = null

    const imageForm = ref({
      name: '', filename: '', download_url: '', os_type: '',
      version: '', architecture: 'amd64', checksum: ''
    })

    const setupForm = ref({ selectedNodeId: '', selectedImageIds: [] })

    const predefinedImages = ref([
      { name: 'Ubuntu 24.04 LTS (Noble)', filename: 'noble-server-cloudimg-amd64.img', os_type: 'ubuntu', version: '24.04', architecture: 'amd64', download_url: 'https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img', icon: '🟠' },
      { name: 'Ubuntu 22.04 LTS (Jammy)', filename: 'jammy-server-cloudimg-amd64.img', os_type: 'ubuntu', version: '22.04', architecture: 'amd64', download_url: 'https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img', icon: '🟠' },
      { name: 'Ubuntu 20.04 LTS (Focal)', filename: 'focal-server-cloudimg-amd64.img', os_type: 'ubuntu', version: '20.04', architecture: 'amd64', download_url: 'https://cloud-images.ubuntu.com/focal/current/focal-server-cloudimg-amd64.img', icon: '🟠' },
      { name: 'Debian 12 (Bookworm)', filename: 'debian-12-generic-amd64.qcow2', os_type: 'debian', version: '12', architecture: 'amd64', download_url: 'https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2', icon: '🔴' },
      { name: 'Debian 11 (Bullseye)', filename: 'debian-11-generic-amd64.qcow2', os_type: 'debian', version: '11', architecture: 'amd64', download_url: 'https://cloud.debian.org/images/cloud/bullseye/latest/debian-11-generic-amd64.qcow2', icon: '🔴' },
      { name: 'Rocky Linux 9', filename: 'Rocky-9-GenericCloud-Base.latest.x86_64.qcow2', os_type: 'rocky', version: '9', architecture: 'amd64', download_url: 'https://download.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud-Base.latest.x86_64.qcow2', icon: '🟢' },
      { name: 'Rocky Linux 8', filename: 'Rocky-8-GenericCloud-Base.latest.x86_64.qcow2', os_type: 'rocky', version: '8', architecture: 'amd64', download_url: 'https://download.rockylinux.org/pub/rocky/8/images/x86_64/Rocky-8-GenericCloud-Base.latest.x86_64.qcow2', icon: '🟢' },
      { name: 'AlmaLinux 9', filename: 'AlmaLinux-9-GenericCloud-latest.x86_64.qcow2', os_type: 'alma', version: '9', architecture: 'amd64', download_url: 'https://repo.almalinux.org/almalinux/9/cloud/x86_64/images/AlmaLinux-9-GenericCloud-latest.x86_64.qcow2', icon: '🔵' },
      { name: 'AlmaLinux 8', filename: 'AlmaLinux-8-GenericCloud-latest.x86_64.qcow2', os_type: 'alma', version: '8', architecture: 'amd64', download_url: 'https://repo.almalinux.org/almalinux/8/cloud/x86_64/images/AlmaLinux-8-GenericCloud-latest.x86_64.qcow2', icon: '🔵' },
      { name: 'Fedora Cloud 41', filename: 'Fedora-Cloud-Base-41.qcow2', os_type: 'fedora', version: '41', architecture: 'amd64', download_url: 'https://download.fedoraproject.org/pub/fedora/linux/releases/41/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-41-1.4.x86_64.qcow2', icon: '🔷' },
      { name: 'CentOS Stream 9', filename: 'CentOS-Stream-GenericCloud-9.qcow2', os_type: 'centos', version: '9', architecture: 'amd64', download_url: 'https://cloud.centos.org/centos/9-stream/x86_64/images/CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2', icon: '🟣' },
      { name: 'openSUSE Leap 15.6', filename: 'openSUSE-Leap-15.6-Minimal-VM.qcow2', os_type: 'opensuse', version: '15.6', architecture: 'amd64', download_url: 'https://download.opensuse.org/distribution/leap/15.6/appliances/openSUSE-Leap-15.6-Minimal-VM.x86_64-Cloud.qcow2', icon: '🟢' },
      { name: 'Arch Linux', filename: 'Arch-Linux-x86_64-cloudimg.qcow2', os_type: 'other', version: 'latest', architecture: 'amd64', download_url: 'https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2', icon: '🔵' },
      { name: 'Alpine Linux 3.21', filename: 'alpine-virt-3.21.0-x86_64.qcow2', os_type: 'other', version: '3.21', architecture: 'amd64', download_url: 'https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/cloud/nocloud_alpine-3.21.0-x86_64-bios-cloudinit-r0.qcow2', icon: '⛰️' },
      { name: 'Flatcar Container Linux', filename: 'flatcar_production_qemu_image.img', os_type: 'other', version: 'stable', architecture: 'amd64', download_url: 'https://stable.release.flatcar-linux.net/amd64-usr/current/flatcar_production_qemu_image.img', icon: '🐋' }
    ])

    const sortedPredefinedImages = computed(() =>
      [...predefinedImages.value].sort((a, b) => a.name.localeCompare(b.name))
    )

    const sortedImages = computed(() =>
      [...images.value].sort((a, b) => a.name.localeCompare(b.name))
    )

    const toggleImageSelection = (predefined) => {
      const index = selectedImageNames.value.indexOf(predefined.name)
      if (index > -1) selectedImageNames.value.splice(index, 1)
      else selectedImageNames.value.push(predefined.name)
    }

    const isImageSelected = (imageName) => selectedImageNames.value.includes(imageName)

    const getSelectedImages = () =>
      predefinedImages.value.filter(img => selectedImageNames.value.includes(img.name))

    const fetchImages = async () => {
      cloudLoading.value = true
      try {
        const response = await api.cloudImages.list()
        images.value = response.data
      } catch (error) {
        console.error('Failed to fetch cloud images:', error)
      } finally {
        cloudLoading.value = false
      }
    }

    const downloadImage = async (imageId) => {
      try {
        await api.cloudImages.download(imageId)
        toast.success('Cloud image download started')
        startProgressPolling()
      } catch (error) {
        console.error('Failed to start download:', error)
        toast.error('Failed to start download')
      }
    }

    const saveImage = async () => {
      cloudSaving.value = true
      try {
        if (editingImage.value) {
          await api.cloudImages.update(editingImage.value.id, imageForm.value)
          toast.success('Cloud image updated successfully')
        } else {
          await api.cloudImages.create(imageForm.value)
          toast.success('Cloud image added successfully')
        }
        closeCloudModal()
        fetchImages()
      } catch (error) {
        console.error('Failed to save cloud image:', error)
        toast.error('Failed to save cloud image')
      } finally {
        cloudSaving.value = false
      }
    }

    const saveSelectedImages = async () => {
      if (selectedImageNames.value.length === 0) {
        toast.error('Please select at least one cloud image')
        return
      }
      cloudSaving.value = true
      const selectedImages = getSelectedImages()
      let successCount = 0, failCount = 0
      try {
        for (const image of selectedImages) {
          try {
            await api.cloudImages.create({
              name: image.name, filename: image.filename, download_url: image.download_url,
              os_type: image.os_type, version: image.version, architecture: image.architecture, checksum: ''
            })
            successCount++
          } catch (error) {
            console.error(`Failed to add ${image.name}:`, error)
            failCount++
          }
        }
        if (successCount > 0) toast.success(`Successfully added ${successCount} cloud image${successCount > 1 ? 's' : ''}`)
        if (failCount > 0) toast.warning(`Failed to add ${failCount} cloud image${failCount > 1 ? 's' : ''} (may already exist)`)
        closeCloudModal()
        fetchImages()
      } catch (error) {
        console.error('Failed to save cloud images:', error)
        toast.error('Failed to save cloud images')
      } finally {
        cloudSaving.value = false
      }
    }

    const editImage = (image) => {
      editingImage.value = image
      imageForm.value = {
        name: image.name, filename: image.filename, download_url: image.download_url,
        os_type: image.os_type, version: image.version || '', architecture: image.architecture,
        checksum: image.checksum || ''
      }
      showCloudAddModal.value = true
    }

    const deleteImage = async (imageId) => {
      if (!confirm('Are you sure you want to delete this cloud image?')) return
      try {
        await api.cloudImages.delete(imageId)
        toast.success('Cloud image deleted successfully')
        fetchImages()
      } catch (error) {
        console.error('Failed to delete cloud image:', error)
        toast.error('Failed to delete cloud image')
      }
    }

    const closeCloudModal = () => {
      showCloudAddModal.value = false
      editingImage.value = null
      imageSelectionMode.value = null
      selectedImageNames.value = []
      imageForm.value = { name: '', filename: '', download_url: '', os_type: '', version: '', architecture: 'amd64', checksum: '' }
    }

    const fetchNodes = async () => {
      try {
        const hostsResponse = await api.proxmox.listHosts()
        const allNodes = []
        for (const host of hostsResponse.data) {
          try {
            const nodesResponse = await api.proxmox.listNodes(host.id)
            if (nodesResponse.data && nodesResponse.data.length > 0) {
              nodesResponse.data.forEach(node => {
                allNodes.push({ id: node.id, node_name: node.node_name, proxmox_host_name: host.name })
              })
            }
          } catch (error) {
            console.error(`Failed to fetch nodes for host ${host.name}:`, error)
          }
        }
        nodes.value = allNodes
      } catch (error) {
        console.error('Failed to fetch nodes:', error)
        toast.error('Failed to fetch Proxmox nodes')
      }
    }

    const setupTemplates = async () => {
      if (!setupForm.value.selectedNodeId || setupForm.value.selectedImageIds.length === 0) {
        toast.error('Please select a node and at least one cloud image')
        return
      }
      settingUpTemplates.value = true
      try {
        await api.cloudImages.setupTemplates({
          node_id: parseInt(setupForm.value.selectedNodeId),
          cloud_image_ids: setupForm.value.selectedImageIds
        })
        toast.success('Template setup started! This may take several minutes.')
        showSetupModal.value = false
        setupForm.value = { selectedNodeId: '', selectedImageIds: [] }
      } catch (error) {
        console.error('Failed to setup templates:', error)
        toast.error('Failed to start template setup')
      } finally {
        settingUpTemplates.value = false
      }
    }

    const openSetupModal = async () => {
      showSetupModal.value = true
      await fetchNodes()
    }

    const startProgressPolling = () => {
      if (refreshInterval) return
      refreshInterval = setInterval(() => {
        fetchImages()
        const hasActiveDownloads = images.value.some(img => img.download_status === 'downloading')
        if (!hasActiveDownloads && refreshInterval) {
          clearInterval(refreshInterval)
          refreshInterval = null
        }
      }, 2000)
    }

    const checkAllTemplates = async () => {
      checkingTemplates.value = true
      templateStatus.value = {}
      try {
        const hostsResponse = await api.proxmox.listHosts()
        const statusResults = {}
        for (const host of hostsResponse.data) {
          try {
            const nodesResponse = await api.proxmox.listNodes(host.id)
            if (nodesResponse.data && nodesResponse.data.length > 0) {
              for (const node of nodesResponse.data) {
                const status = await api.cloudImages.checkTemplates(node.id)
                statusResults[node.id] = status.data
              }
            }
          } catch (error) {
            console.error(`Failed to check templates for host ${host.name}:`, error)
          }
        }
        templateStatus.value = statusResults
        toast.success('Template status checked successfully')
      } catch (error) {
        console.error('Failed to check templates:', error)
        toast.error('Failed to check template status')
      } finally {
        checkingTemplates.value = false
      }
    }

    const getTemplateCount = (templates) =>
      Object.values(templates).filter(exists => exists).length

    const fetchLatestImages = async () => {
      fetchingLatest.value = true
      try {
        const response = await api.cloudImages.fetchLatest()
        if (response.data.updated_count > 0) {
          const hasAdded = response.data.updated_images?.some(img => img.status === 'added')
          if (hasAdded) toast.success(`Added ${response.data.updated_count} cloud image(s) to database`)
          else toast.success(`Updated ${response.data.updated_count} cloud image(s)`)
          await fetchImages()
        } else {
          toast.info('All cloud images are up to date')
        }
        if (response.data.errors && response.data.errors.length > 0) {
          toast.warning(`Some images could not be updated: ${response.data.errors.length} errors`)
        }
      } catch (error) {
        console.error('Failed to fetch latest cloud images:', error)
        toast.error('Failed to fetch latest cloud images')
      } finally {
        fetchingLatest.value = false
      }
    }

    // ===== Proxmox Storage State =====
    const pxHosts = ref([])
    const pxNodes = ref([])
    const pxStorages = ref([])
    const pxContent = ref([])
    const pxSelectedHostId = ref('')
    const pxSelectedNode = ref('')
    const pxSelectedStorage = ref('')
    const pxContentFilter = ref('All')
    const pxStorageLoading = ref(false)
    const pxNodesLoading = ref(false)
    const pxStoragesLoading = ref(false)

    // Upload state
    const pxShowUpload = ref(false)
    const pxUploadFile = ref(null)
    const pxUploading = ref(false)
    const pxUploadProgress = ref(0)

    // Download URL to storage state
    const pxShowDownloadUrl = ref(false)
    const pxDownloadingUrl = ref(false)
    const pxDownloadUrlTaskId = ref(null)
    const pxDownloadUrlForm = ref({ url: '', filename: '', content: 'iso', checksum_algorithm: '', checksum: '' })

    // Copy to Node state
    const showCopyToNodeModal = ref(false)
    const copyToNodeItem = ref(null)
    const copyToNodeNodesLoading = ref(false)
    const copyToNodeStoragesLoading = ref(false)
    const copyToNodeNodes = ref([])
    const copyToNodeStorages = ref([])
    const copyToNodeRunning = ref(false)
    const copyToNodeForm = ref({ hostId: '', node: '', storage: '', url: '' })

    // Quick Download state
    const showQuickDownloadModal = ref(false)
    const quickDownloadNodesLoading = ref(false)
    const quickDownloadStoragesLoading = ref(false)
    const quickDownloadNodes = ref([])
    const quickDownloadStorages = ref([])
    const quickDownloadRunning = ref(false)
    const quickDownloadForm = ref({ hostId: '', node: '', storage: '', url: '', filename: '', content: 'iso', checksum_algorithm: '', checksum: '' })

    const pxStorageSupportsIso = computed(() => {
      if (!pxSelectedStorage.value) return false
      const stor = pxStorages.value.find(s => s.storage === pxSelectedStorage.value)
      if (!stor) return false
      return (stor.content || '').includes('iso')
    })

    const onPxFileSelected = (event) => {
      pxUploadFile.value = event.target.files[0] || null
      pxUploadProgress.value = 0
    }

    const uploadToProxmoxStorage = async () => {
      if (!pxUploadFile.value) return
      pxUploading.value = true
      pxUploadProgress.value = 0
      try {
        const formData = new FormData()
        formData.append('content', 'iso')
        formData.append('filename', pxUploadFile.value)
        const onProgress = (evt) => {
          if (evt.total) pxUploadProgress.value = Math.round((evt.loaded * 100) / evt.total)
        }
        await api.pveNode.uploadToStorage(
          pxSelectedHostId.value,
          pxSelectedNode.value,
          pxSelectedStorage.value,
          formData,
          onProgress
        )
        pxUploadProgress.value = 100
        toast.success(`${pxUploadFile.value.name} uploaded successfully`)
        pxUploadFile.value = null
        pxShowUpload.value = false
        await loadPxContent()
      } catch (error) {
        console.error('Failed to upload ISO to Proxmox storage:', error)
        toast.error('Upload failed: ' + (error?.response?.data?.detail || error.message || 'Unknown error'))
      } finally {
        pxUploading.value = false
      }
    }

    const pxFilteredContent = computed(() => {
      if (pxContentFilter.value === 'ISO') return pxContent.value.filter(i => i.content === 'iso')
      if (pxContentFilter.value === 'Images') return pxContent.value.filter(i => i.content === 'images')
      return pxContent.value
    })

    const pxBasename = (volid) => {
      if (!volid) return ''
      const parts = volid.split('/')
      return parts[parts.length - 1]
    }

    const pxFormatBadgeClass = (fmt) => {
      const map = { iso: 'badge-info', raw: 'badge-secondary', qcow2: 'badge-success', vmdk: 'badge-warning', images: 'badge-secondary' }
      return map[fmt] || 'badge-secondary'
    }

    const initProxmoxStorage = async () => {
      if (pxHosts.value.length > 0) return
      try {
        const res = await api.proxmox.listHosts()
        pxHosts.value = res.data
      } catch (e) {
        console.error('Failed to fetch Proxmox hosts:', e)
        toast.error('Failed to load Proxmox hosts')
      }
    }

    const onPxHostChange = async () => {
      pxSelectedNode.value = ''
      pxSelectedStorage.value = ''
      pxNodes.value = []
      pxStorages.value = []
      pxContent.value = []
      if (!pxSelectedHostId.value) return
      pxNodesLoading.value = true
      try {
        const res = await api.proxmox.listNodes(pxSelectedHostId.value)
        pxNodes.value = res.data
      } catch (e) {
        console.error('Failed to fetch nodes:', e)
        toast.error('Failed to load nodes')
      } finally {
        pxNodesLoading.value = false
      }
    }

    const onPxNodeChange = async () => {
      pxSelectedStorage.value = ''
      pxStorages.value = []
      pxContent.value = []
      if (!pxSelectedNode.value) return
      pxStoragesLoading.value = true
      try {
        const res = await api.pveNode.listStorage(pxSelectedHostId.value, pxSelectedNode.value)
        pxStorages.value = (res.data || []).filter(s => {
          const c = s.content || ''
          return c.includes('iso') || c.includes('images')
        })
      } catch (e) {
        console.error('Failed to fetch storages:', e)
        toast.error('Failed to load storages')
      } finally {
        pxStoragesLoading.value = false
      }
    }

    const onPxStorageChange = async () => {
      pxContent.value = []
      if (!pxSelectedStorage.value) return
      await loadPxContent()
    }

    const loadPxContent = async () => {
      pxStorageLoading.value = true
      pxContent.value = []
      try {
        const [isoRes, imgRes] = await Promise.allSettled([
          api.pveNode.browseStorage(pxSelectedHostId.value, pxSelectedNode.value, pxSelectedStorage.value, { content: 'iso' }),
          api.pveNode.browseStorage(pxSelectedHostId.value, pxSelectedNode.value, pxSelectedStorage.value, { content: 'images' })
        ])
        const combined = []
        if (isoRes.status === 'fulfilled') combined.push(...(isoRes.value.data || []))
        if (imgRes.status === 'fulfilled') combined.push(...(imgRes.value.data || []))
        // deduplicate by volid
        const seen = new Set()
        pxContent.value = combined.filter(item => {
          if (seen.has(item.volid)) return false
          seen.add(item.volid)
          return true
        })
      } catch (e) {
        console.error('Failed to browse storage:', e)
        toast.error('Failed to browse storage content')
      } finally {
        pxStorageLoading.value = false
      }
    }

    const refreshProxmoxStorage = async () => {
      if (pxSelectedStorage.value) {
        await loadPxContent()
      } else if (pxSelectedNode.value) {
        await onPxNodeChange()
      } else if (pxSelectedHostId.value) {
        await onPxHostChange()
      } else {
        pxHosts.value = []
        await initProxmoxStorage()
      }
    }

    const submitDownloadUrlToStorage = async () => {
      if (!pxDownloadUrlForm.value.url || !pxDownloadUrlForm.value.filename) return
      pxDownloadingUrl.value = true
      pxDownloadUrlTaskId.value = null
      try {
        const payload = { url: pxDownloadUrlForm.value.url, filename: pxDownloadUrlForm.value.filename, content: pxDownloadUrlForm.value.content }
        if (pxDownloadUrlForm.value.checksum_algorithm) {
          payload['checksum-algorithm'] = pxDownloadUrlForm.value.checksum_algorithm
          if (pxDownloadUrlForm.value.checksum) payload.checksum = pxDownloadUrlForm.value.checksum
        }
        const res = await api.pveNode.downloadUrlToStorage(pxSelectedHostId.value, pxSelectedNode.value, pxSelectedStorage.value, payload)
        pxDownloadUrlTaskId.value = res.data?.upid || 'submitted'
        toast.success('Download task submitted to Proxmox')
        pxDownloadUrlForm.value = { url: '', filename: '', content: 'iso', checksum_algorithm: '', checksum: '' }
      } catch (e) {
        console.error('Failed to submit download-url task:', e)
        toast.error('Failed to submit download: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
      } finally {
        pxDownloadingUrl.value = false
      }
    }

    const openCopyToNode = async (item) => {
      copyToNodeItem.value = item
      copyToNodeForm.value = { hostId: '', node: '', storage: '', url: '' }
      copyToNodeNodes.value = []
      copyToNodeStorages.value = []
      showCopyToNodeModal.value = true
      // Pre-populate hosts if not yet loaded
      if (pxHosts.value.length === 0) await initProxmoxStorage()
    }

    const onCopyHostChange = async () => {
      copyToNodeForm.value.node = ''
      copyToNodeForm.value.storage = ''
      copyToNodeNodes.value = []
      copyToNodeStorages.value = []
      if (!copyToNodeForm.value.hostId) return
      copyToNodeNodesLoading.value = true
      try {
        const res = await api.proxmox.listNodes(copyToNodeForm.value.hostId)
        copyToNodeNodes.value = res.data
      } catch (e) {
        toast.error('Failed to load nodes')
      } finally {
        copyToNodeNodesLoading.value = false
      }
    }

    const onCopyNodeChange = async () => {
      copyToNodeForm.value.storage = ''
      copyToNodeStorages.value = []
      if (!copyToNodeForm.value.node) return
      copyToNodeStoragesLoading.value = true
      try {
        const res = await api.pveNode.listStorage(copyToNodeForm.value.hostId, copyToNodeForm.value.node)
        copyToNodeStorages.value = (res.data || []).filter(s => (s.content || '').includes('iso') || (s.content || '').includes('images'))
      } catch (e) {
        toast.error('Failed to load storages')
      } finally {
        copyToNodeStoragesLoading.value = false
      }
    }

    const submitCopyToNode = async () => {
      if (!copyToNodeForm.value.url || !copyToNodeItem.value) return
      copyToNodeRunning.value = true
      try {
        const filename = pxBasename(copyToNodeItem.value.volid)
        const payload = { url: copyToNodeForm.value.url, filename, content: copyToNodeItem.value.content || 'iso' }
        await api.pveNode.downloadUrlToStorage(copyToNodeForm.value.hostId, copyToNodeForm.value.node, copyToNodeForm.value.storage, payload)
        toast.success('Copy task submitted to Proxmox successfully')
        showCopyToNodeModal.value = false
      } catch (e) {
        console.error('Failed to copy to node:', e)
        toast.error('Failed to submit copy: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
      } finally {
        copyToNodeRunning.value = false
      }
    }

    // Quick Download functions
    const openQuickDownload = async (presetName) => {
      quickDownloadForm.value = { hostId: '', node: '', storage: '', url: '', filename: '', content: 'iso', checksum_algorithm: '', checksum: '' }
      if (presetName) quickDownloadForm.value._label = presetName
      quickDownloadNodes.value = []
      quickDownloadStorages.value = []
      showQuickDownloadModal.value = true
      if (pxHosts.value.length === 0) await initProxmoxStorage()
    }

    const onQuickHostChange = async () => {
      quickDownloadForm.value.node = ''
      quickDownloadForm.value.storage = ''
      quickDownloadNodes.value = []
      quickDownloadStorages.value = []
      if (!quickDownloadForm.value.hostId) return
      quickDownloadNodesLoading.value = true
      try {
        const res = await api.proxmox.listNodes(quickDownloadForm.value.hostId)
        quickDownloadNodes.value = res.data
      } catch (e) {
        toast.error('Failed to load nodes')
      } finally {
        quickDownloadNodesLoading.value = false
      }
    }

    const onQuickNodeChange = async () => {
      quickDownloadForm.value.storage = ''
      quickDownloadStorages.value = []
      if (!quickDownloadForm.value.node) return
      quickDownloadStoragesLoading.value = true
      try {
        const res = await api.pveNode.listStorage(quickDownloadForm.value.hostId, quickDownloadForm.value.node)
        quickDownloadStorages.value = (res.data || []).filter(s => (s.content || '').includes('iso') || (s.content || '').includes('images'))
      } catch (e) {
        toast.error('Failed to load storages')
      } finally {
        quickDownloadStoragesLoading.value = false
      }
    }

    const submitQuickDownload = async () => {
      if (!quickDownloadForm.value.url || !quickDownloadForm.value.filename) return
      quickDownloadRunning.value = true
      try {
        const payload = { url: quickDownloadForm.value.url, filename: quickDownloadForm.value.filename, content: quickDownloadForm.value.content }
        if (quickDownloadForm.value.checksum_algorithm) {
          payload['checksum-algorithm'] = quickDownloadForm.value.checksum_algorithm
          if (quickDownloadForm.value.checksum) payload.checksum = quickDownloadForm.value.checksum
        }
        await api.pveNode.downloadUrlToStorage(quickDownloadForm.value.hostId, quickDownloadForm.value.node, quickDownloadForm.value.storage, payload)
        toast.success('Download task submitted to Proxmox node')
        showQuickDownloadModal.value = false
      } catch (e) {
        console.error('Failed to submit quick download:', e)
        toast.error('Failed to submit: ' + (e?.response?.data?.detail || e.message || 'Unknown error'))
      } finally {
        quickDownloadRunning.value = false
      }
    }

    // Cloud image: cancel download
    const cancelDownload = async (imageId) => {
      if (!confirm('Cancel this download?')) return
      try {
        await api.cloudImages.delete(imageId)
        toast.info('Download cancelled')
        await fetchImages()
      } catch (e) {
        console.error('Failed to cancel download:', e)
        toast.error('Failed to cancel download')
      }
    }

    // Cloud image: delete local copy after templating to free disk
    const deleteLocalCopy = async (imageId) => {
      if (!confirm('Delete the local copy of this image? The VM template on Proxmox will not be affected.')) return
      try {
        await api.cloudImages.delete(imageId)
        toast.success('Local copy deleted')
        await fetchImages()
      } catch (e) {
        console.error('Failed to delete local copy:', e)
        toast.error('Failed to delete local copy')
      }
    }

    // ===== Shared Helpers =====
    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
    }

    const formatOSType = (osType) => {
      const map = {
        ubuntu: 'Ubuntu', debian: 'Debian', centos: 'CentOS', rocky: 'Rocky Linux',
        alma: 'AlmaLinux', fedora: 'Fedora', opensuse: 'openSUSE',
        windows_server_2019: 'Windows Server 2019', windows_server_2022: 'Windows Server 2022',
        windows_10: 'Windows 10', windows_11: 'Windows 11',
        pfsense: 'pfSense', opnsense: 'OPNsense', freebsd: 'FreeBSD',
        truenas: 'TrueNAS', proxmox: 'Proxmox VE', esxi: 'VMware ESXi', other: 'Other'
      }
      return map[osType] || osType
    }

    onMounted(() => {
      fetchISOs()
      fetchImages()
      const hasActiveDownloads = images.value.some(img => img.download_status === 'downloading')
      if (hasActiveDownloads) startProgressPolling()
    })

    onUnmounted(() => {
      if (refreshInterval) clearInterval(refreshInterval)
    })

    return {
      activeTab,
      // ISO
      isos, isoLoading, uploading, isoDownloading, uploadProgress, uploadedBytes, totalBytes, uploadSpeed,
      showISOAddModal, isoSelectionMode, selectedISONames, selectedFile,
      uploadForm, downloadForm, predefinedISOs, sortedPredefinedISOs,
      onFileSelected, uploadISO, downloadFromUrl, saveSelectedISOs,
      toggleISOSelection, isISOSelected, verifyISO, deleteISO, closeISOModal, formatTimeRemaining,
      // Cloud
      images, sortedImages, nodes, cloudLoading, showCloudAddModal, showSetupModal,
      editingImage, imageForm, setupForm, cloudSaving, imageSelectionMode, selectedImageNames,
      settingUpTemplates, templateStatus, checkingTemplates, fetchingLatest,
      predefinedImages, sortedPredefinedImages,
      fetchImages, downloadImage, saveImage, saveSelectedImages,
      editImage, deleteImage, closeCloudModal, setupTemplates, openSetupModal,
      checkAllTemplates, getTemplateCount, fetchLatestImages,
      toggleImageSelection, isImageSelected,
      cancelDownload, deleteLocalCopy,
      // Proxmox Storage
      pxHosts, pxNodes, pxStorages, pxContent, pxFilteredContent,
      pxSelectedHostId, pxSelectedNode, pxSelectedStorage,
      pxContentFilter, pxStorageLoading, pxNodesLoading, pxStoragesLoading,
      pxBasename, pxFormatBadgeClass,
      initProxmoxStorage, onPxHostChange, onPxNodeChange, onPxStorageChange, refreshProxmoxStorage,
      pxShowUpload, pxUploadFile, pxUploading, pxUploadProgress, pxStorageSupportsIso,
      onPxFileSelected, uploadToProxmoxStorage,
      pxShowDownloadUrl, pxDownloadingUrl, pxDownloadUrlTaskId, pxDownloadUrlForm, submitDownloadUrlToStorage,
      showCopyToNodeModal, copyToNodeItem, copyToNodeNodesLoading, copyToNodeStoragesLoading,
      copyToNodeNodes, copyToNodeStorages, copyToNodeRunning, copyToNodeForm,
      openCopyToNode, onCopyHostChange, onCopyNodeChange, submitCopyToNode,
      // Quick Download
      showQuickDownloadModal, quickDownloadNodesLoading, quickDownloadStoragesLoading,
      quickDownloadNodes, quickDownloadStorages, quickDownloadRunning, quickDownloadForm,
      openQuickDownload, onQuickHostChange, onQuickNodeChange, submitQuickDownload,
      // Shared
      formatBytes, formatOSType
    }
  }
}
</script>

<style scoped>
.images-tab-nav {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1.5rem;
  background: var(--background);
  padding: 0.35rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  width: fit-content;
}

.images-tab-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1.25rem;
  border: none;
  background: transparent;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all 0.15s;
}

.images-tab-btn:hover {
  color: var(--text-primary);
  background: white;
}

.images-tab-btn.active {
  background: white;
  color: var(--text-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  font-weight: 600;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.download-progress {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.progress-bar-container {
  width: 100px;
  height: 8px;
  background-color: var(--background);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background-color: var(--primary);
  transition: width 0.3s ease;
}

.modal {
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
  background: #1e293b;
  border: 2px solid #475569;
  border-radius: 12px;
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
}

.modal-large {
  max-width: 900px;
}

.modal-content .btn-outline {
  background-color: #334155;
  border: 2px solid #64748b;
  color: #f1f5f9;
}

.modal-content .btn-outline:hover {
  background-color: #475569;
  border-color: #94a3b8;
  color: #ffffff;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 2px solid #475569;
  background: #334155;
}

.modal-header h3 {
  margin: 0;
  color: #ffffff;
  font-weight: 600;
}

.btn-close {
  background: #475569;
  border: none;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  color: #cbd5e1;
  padding: 0;
  width: 2rem;
  height: 2rem;
  border-radius: 6px;
  transition: all 0.2s;
}

.btn-close:hover {
  background: #ef4444;
  color: #ffffff;
}

.modal-body {
  padding: 1.5rem;
  background: #1e293b;
}

.modal-body :deep(.form-label) {
  color: #e2e8f0;
  font-weight: 500;
}

.modal-body :deep(.form-control),
.modal-body :deep(input),
.modal-body :deep(select),
.modal-body :deep(textarea) {
  background: #0f172a;
  border: 1px solid #475569;
  color: #f1f5f9;
}

.modal-body :deep(.form-control:focus),
.modal-body :deep(input:focus),
.modal-body :deep(select:focus),
.modal-body :deep(textarea:focus) {
  border-color: #3b82f6;
  outline: none;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.modal-body :deep(.text-muted) {
  color: #94a3b8 !important;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  border-top: 2px solid #475569;
  background: #334155;
}

.upload-progress {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #0f172a;
  border-radius: 0.5rem;
  border: 2px solid #475569;
}

.upload-stats { margin-bottom: 1rem; }

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid #475569;
}

.stat-row:last-child { border-bottom: none; }

.stat-label {
  font-size: 0.875rem;
  color: #94a3b8;
  font-weight: 500;
}

.stat-value {
  font-size: 0.875rem;
  color: #f1f5f9;
  font-weight: 600;
  font-family: monospace;
}

.progress-bar {
  height: 1.25rem;
  background-color: #475569;
  border-radius: 9999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  transition: width 0.2s ease;
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
}

.selection-mode { padding: 2rem 1.5rem; }

.selection-prompt {
  text-align: center;
  margin-bottom: 2rem;
}

.selection-prompt h4 {
  color: #ffffff;
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.selection-prompt p {
  color: #cbd5e1;
  font-size: 1rem;
}

.selection-options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  max-width: 1000px;
  margin: 0 auto;
}

.selection-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2rem 1.5rem;
  background: #1e293b;
  border: 3px solid #475569;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s;
}

.selection-card:hover {
  background: #334155;
  border-color: #3b82f6;
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.4);
}

.selection-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.selection-info {
  text-align: center;
  flex: 1;
}

.selection-info h5 {
  color: #ffffff;
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.selection-info p {
  color: #e2e8f0;
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.selection-list {
  list-style: none;
  padding: 0;
  margin: 0;
  text-align: left;
}

.selection-list li {
  color: #f1f5f9;
  font-size: 0.875rem;
  padding: 0.25rem 0 0.25rem 1.5rem;
  position: relative;
}

.selection-list li::before {
  content: '✓';
  position: absolute;
  left: 0;
  color: #4ade80;
  font-weight: bold;
}

.selection-arrow {
  font-size: 2rem;
  color: #60a5fa;
  margin-top: 1rem;
  opacity: 0.9;
  transition: all 0.3s;
}

.selection-card:hover .selection-arrow {
  opacity: 1;
  color: #3b82f6;
  transform: translateX(4px);
}

.mode-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid #475569;
}

.mode-header h4 {
  color: #ffffff;
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
  flex: 1;
}

.selection-count {
  background: #3b82f6;
  color: #ffffff;
  padding: 0.375rem 0.875rem;
  border-radius: 20px;
  font-size: 0.875rem;
  font-weight: 600;
  white-space: nowrap;
}

.predefined-images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.predefined-image-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: #1e293b;
  border: 2px solid #475569;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.predefined-image-card:hover {
  background: #334155;
  border-color: #60a5fa;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.predefined-image-card.selected {
  background: #334155;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.4);
}

.predefined-image-icon {
  font-size: 2rem;
  line-height: 1;
  flex-shrink: 0;
}

.predefined-image-info {
  flex: 1;
  min-width: 0;
}

.predefined-image-name {
  color: #ffffff;
  font-weight: 600;
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.predefined-image-details {
  color: #cbd5e1;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 500;
}

.predefined-image-check {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: #3b82f6;
  color: #ffffff;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  font-weight: bold;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.5);
}

.selected-images-preview {
  margin-top: 1.5rem;
  padding: 1.25rem;
  background: rgba(59, 130, 246, 0.15);
  border: 2px solid #60a5fa;
  border-radius: 8px;
}

.selected-images-preview h5 {
  color: #ffffff;
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.selected-images-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.selected-image-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.375rem 0.75rem;
  background: #334155;
  border: 1px solid #60a5fa;
  border-radius: 6px;
  color: #f1f5f9;
  font-size: 0.8125rem;
  font-weight: 500;
  white-space: nowrap;
}

.checkbox-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
  padding: 0.75rem;
  border: 2px solid #475569;
  border-radius: 8px;
  background-color: #0f172a;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  padding: 0.75rem;
  border-radius: 6px;
  background: #1e293b;
  border: 1px solid #334155;
  transition: all 0.2s;
}

.checkbox-item:hover {
  background: #334155;
  border-color: #3b82f6;
}

.checkbox-item span {
  color: #f1f5f9;
  font-weight: 500;
}

.checkbox-item input[type="checkbox"] {
  cursor: pointer;
  width: 18px;
  height: 18px;
  accent-color: #3b82f6;
}

.alert {
  padding: 1rem;
  border-radius: 8px;
  margin-top: 1rem;
  border: 2px solid;
}

.alert-info {
  background-color: rgba(59, 130, 246, 0.15);
  border-color: #3b82f6;
  color: #dbeafe;
}

.alert-info p {
  color: #dbeafe;
  margin: 0.25rem 0;
}

.template-status-section {
  padding: 1.5rem;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 2px solid #475569;
}

.template-status-title {
  color: #f1f5f9;
  margin-bottom: 1rem;
  font-size: 1.25rem;
  font-weight: 600;
}

.template-status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.node-status-card {
  background: #1e293b;
  border: 2px solid #475569;
  border-radius: 8px;
  padding: 1rem;
}

.node-status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #475569;
}

.node-name {
  color: #f1f5f9;
  font-weight: 600;
  font-size: 1.1rem;
}

.template-count {
  color: #94a3b8;
  font-size: 0.875rem;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.template-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
  background: #0f172a;
  border-radius: 4px;
}

.template-vmid {
  color: #e2e8f0;
  font-weight: 500;
}

.template-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 500;
}

.template-badge.exists {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
  border: 1px solid #22c55e;
}

.template-badge.missing {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
  border: 1px solid #ef4444;
}

/* ===== Proxmox Storage Tab ===== */
.px-storage-selectors {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.px-content-filter {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.02);
}

.filter-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
}

.filter-btns {
  display: flex;
  gap: 0.375rem;
}

.px-empty-state {
  padding: 3rem 1.5rem;
}

.px-filename {
  font-weight: 500;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.px-volid {
  max-width: 340px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
}

.px-upload-section {
  border-bottom: 1px solid var(--border-color);
}

.px-upload-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  cursor: pointer;
  background: rgba(59, 130, 246, 0.05);
  user-select: none;
}

.px-upload-header:hover {
  background: rgba(59, 130, 246, 0.1);
}

.px-upload-title {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.px-upload-toggle {
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.px-upload-body {
  padding: 1rem 1.5rem;
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.px-upload-row {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.px-upload-progress {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.px-progress-bar {
  flex: 1;
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.px-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  transition: width 0.2s ease;
}

.px-progress-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  min-width: 3rem;
  text-align: right;
  font-family: monospace;
}

.px-checksum {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
}

/* Quick Download card */
.quick-download-card {
  margin-bottom: 1.5rem;
}

.quick-download-body {
  padding: 1.25rem 1.5rem;
}

.quick-download-presets {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.quick-preset-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 0.75rem 1.25rem;
  background: var(--background);
  border: 2px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 110px;
  color: var(--text-primary);
  font-family: inherit;
}

.quick-preset-btn:hover {
  border-color: var(--primary);
  background: rgba(59, 130, 246, 0.07);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}

.quick-preset-custom {
  border-style: dashed;
}

.preset-icon {
  font-size: 1.75rem;
  line-height: 1;
}

.preset-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
  text-align: center;
}

/* Download progress row (for cancel button) */
.download-progress-row {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.2rem;
}

.btn-xs {
  padding: 0.15rem 0.4rem;
  font-size: 0.75rem;
}

.ml-1 { margin-left: 0.25rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.5rem; }
</style>
