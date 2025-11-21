<template>
  <div class="iso-images-page">
    <div class="card">
      <div class="card-header">
        <h3>ISO Images</h3>
        <div class="flex gap-1">
          <button @click="showAddModal = true" class="btn btn-primary">+ Add ISO</button>
        </div>
      </div>

      <div v-if="loading" class="loading-spinner"></div>

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
    <div v-if="showAddModal" class="modal" @click="showAddModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>Add ISO Image</h3>
          <button @click="closeModal" class="btn-close">×</button>
        </div>

        <!-- Selection Mode: Choose between Available, Upload or Download -->
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
            <button @click="isoSelectionMode = null" class="btn btn-outline btn-sm">
              ← Back to Selection
            </button>
            <h4>Select ISO Images</h4>
            <span v-if="selectedISONames.length > 0" class="selection-count">
              {{ selectedISONames.length }} selected
            </span>
          </div>

          <p class="text-muted text-sm mb-2">Click on ISOs to select multiple. Selected ISOs will be downloaded to your library.</p>

          <div class="predefined-images-grid">
            <div
              v-for="predefined in sortedPredefinedISOs"
              :key="predefined.name"
              @click="toggleISOSelection(predefined)"
              :class="['predefined-image-card', { selected: isISOSelected(predefined.name) }]"
            >
              <div class="predefined-image-icon">
                {{ predefined.icon }}
              </div>
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
              <span v-for="name in selectedISONames" :key="name" class="selected-image-chip">
                {{ name }}
              </span>
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" @click="closeModal" class="btn btn-outline">Cancel</button>
            <button
              type="button"
              @click="saveSelectedISOs"
              :disabled="selectedISONames.length === 0"
              class="btn btn-primary"
            >
              {{ `Add ${selectedISONames.length} ISO${selectedISONames.length !== 1 ? 's' : ''}` }}
            </button>
          </div>
        </div>

        <!-- Upload from Computer -->
        <form v-if="isoSelectionMode === 'upload'" @submit.prevent="uploadISO" class="modal-body">
          <div class="mode-header">
            <button type="button" @click="isoSelectionMode = null" class="btn btn-outline btn-sm">
              ← Back to Selection
            </button>
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
                <option value="sophos">Sophos Firewall</option>
                <option value="fortinet">FortiGate</option>
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
            <button type="button" @click="closeModal" class="btn btn-outline" :disabled="uploading">Cancel</button>
            <button type="submit" class="btn btn-primary" :disabled="uploading || !selectedFile">
              {{ uploading ? 'Uploading...' : 'Upload ISO' }}
            </button>
          </div>
        </form>

        <!-- Download from URL -->
        <form v-if="isoSelectionMode === 'download'" @submit.prevent="downloadFromUrl" class="modal-body">
          <div class="mode-header">
            <button type="button" @click="isoSelectionMode = null" class="btn btn-outline btn-sm">
              ← Back to Selection
            </button>
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
                <option value="sophos">Sophos Firewall</option>
                <option value="fortinet">FortiGate</option>
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

          <div v-if="downloading" class="upload-progress">
            <p class="text-center text-muted">Downloading ISO from URL...</p>
            <div class="loading-spinner"></div>
          </div>

          <div class="modal-footer">
            <button type="button" @click="closeModal" class="btn btn-outline" :disabled="downloading">Cancel</button>
            <button type="submit" class="btn btn-primary" :disabled="downloading">
              {{ downloading ? 'Downloading...' : 'Download ISO' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'ISOImages',
  setup() {
    const toast = useToast()
    const isos = ref([])
    const loading = ref(false)
    const uploading = ref(false)
    const downloading = ref(false)
    const saving = ref(false)
    const uploadProgress = ref(0)
    const uploadedBytes = ref(0)
    const totalBytes = ref(0)
    const uploadSpeed = ref(0)
    const showAddModal = ref(false)
    const isoSelectionMode = ref(null) // 'available', 'upload', or 'download'
    const selectedISONames = ref([]) // Array of selected ISO names for multiple selection
    const selectedFile = ref(null)
    let uploadStartTime = null

    const uploadForm = ref({
      name: '',
      os_type: '',
      version: '',
      architecture: 'amd64'
    })

    const downloadForm = ref({
      url: '',
      name: '',
      os_type: '',
      version: '',
      architecture: 'amd64'
    })

    const predefinedISOs = ref([
      // Ubuntu Server
      {
        name: 'Ubuntu 24.04 LTS Server',
        filename: 'ubuntu-24.04.3-live-server-amd64.iso',
        os_type: 'ubuntu',
        version: '24.04.3',
        architecture: 'amd64',
        download_url: 'https://releases.ubuntu.com/24.04/ubuntu-24.04.3-live-server-amd64.iso',
        icon: '🟠'
      },
      {
        name: 'Ubuntu 22.04 LTS Server',
        filename: 'ubuntu-22.04-live-server-amd64.iso',
        os_type: 'ubuntu',
        version: '22.04',
        architecture: 'amd64',
        download_url: 'https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso',
        icon: '🟠'
      },
      {
        name: 'Ubuntu 20.04 LTS Server',
        filename: 'ubuntu-20.04-live-server-amd64.iso',
        os_type: 'ubuntu',
        version: '20.04',
        architecture: 'amd64',
        download_url: 'https://releases.ubuntu.com/20.04/ubuntu-20.04.6-live-server-amd64.iso',
        icon: '🟠'
      },
      // Debian
      {
        name: 'Debian 13 (Trixie)',
        filename: 'debian-13.2.0-amd64-netinst.iso',
        os_type: 'debian',
        version: '13.2',
        architecture: 'amd64',
        download_url: 'https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.2.0-amd64-netinst.iso',
        icon: '🔴'
      },
      // Rocky Linux
      {
        name: 'Rocky Linux 9',
        filename: 'Rocky-9-latest-x86_64-minimal.iso',
        os_type: 'rocky',
        version: '9',
        architecture: 'amd64',
        download_url: 'https://download.rockylinux.org/pub/rocky/9/isos/x86_64/Rocky-9-latest-x86_64-minimal.iso',
        icon: '🟢'
      },
      {
        name: 'Rocky Linux 8',
        filename: 'Rocky-8-x86_64-minimal.iso',
        os_type: 'rocky',
        version: '8',
        architecture: 'amd64',
        download_url: 'https://download.rockylinux.org/pub/rocky/8/isos/x86_64/Rocky-8.10-x86_64-minimal.iso',
        icon: '🟢'
      },
      // AlmaLinux
      {
        name: 'AlmaLinux 9',
        filename: 'AlmaLinux-9-latest-x86_64-minimal.iso',
        os_type: 'alma',
        version: '9',
        architecture: 'amd64',
        download_url: 'https://repo.almalinux.org/almalinux/9/isos/x86_64/AlmaLinux-9-latest-x86_64-minimal.iso',
        icon: '🔵'
      },
      {
        name: 'AlmaLinux 8',
        filename: 'AlmaLinux-8-x86_64-minimal.iso',
        os_type: 'alma',
        version: '8',
        architecture: 'amd64',
        download_url: 'https://repo.almalinux.org/almalinux/8/isos/x86_64/AlmaLinux-8.10-x86_64-minimal.iso',
        icon: '🔵'
      },
      // Fedora Server
      {
        name: 'Fedora Server 41',
        filename: 'Fedora-Server-41.iso',
        os_type: 'fedora',
        version: '41',
        architecture: 'amd64',
        download_url: 'https://download.fedoraproject.org/pub/fedora/linux/releases/41/Server/x86_64/iso/Fedora-Server-netinst-x86_64-41-1.4.iso',
        icon: '🔷'
      },
      // CentOS Stream
      {
        name: 'CentOS Stream 9',
        filename: 'CentOS-Stream-9.iso',
        os_type: 'centos',
        version: '9',
        architecture: 'amd64',
        download_url: 'https://mirrors.ocf.berkeley.edu/centos-stream/9-stream/BaseOS/x86_64/iso/CentOS-Stream-9-latest-x86_64-dvd1.iso',
        icon: '🟣'
      },
      // openSUSE
      {
        name: 'openSUSE Leap 15.6',
        filename: 'openSUSE-Leap-15.6-NET-x86_64-Media.iso',
        os_type: 'other',  // opensuse not in enum, use 'other'
        version: '15.6',
        architecture: 'amd64',
        download_url: 'https://download.opensuse.org/distribution/leap/15.6/iso/openSUSE-Leap-15.6-NET-x86_64-Media.iso',
        icon: '🟢'
      },
      // pfSense
      {
        name: 'pfSense CE 2.7.2',
        filename: 'pfSense-CE-2.7.2-RELEASE-amd64.iso',
        os_type: 'pfsense',
        version: '2.7.2',
        architecture: 'amd64',
        download_url: 'https://repo.ialab.dsu.edu/pfsense/pfSense-CE-2.7.2-RELEASE-amd64.iso.gz',
        icon: '🔥'
      },
      // OPNsense
      {
        name: 'OPNsense 24.7',
        filename: 'OPNsense-24.7-dvd-amd64.iso',
        os_type: 'opnsense',
        version: '24.7',
        architecture: 'amd64',
        download_url: 'https://mirrors.dotsrc.org/opnsense/releases/24.7/OPNsense-24.7-dvd-amd64.iso.bz2',
        icon: '🛡️'
      },
      // FreeBSD
      {
        name: 'FreeBSD 14.2',
        filename: 'FreeBSD-14.2-RELEASE-amd64-disc1.iso',
        os_type: 'freebsd',
        version: '14.2',
        architecture: 'amd64',
        download_url: 'https://download.freebsd.org/releases/amd64/amd64/ISO-IMAGES/14.2/FreeBSD-14.2-RELEASE-amd64-disc1.iso',
        icon: '👹'
      },
      // TrueNAS
      {
        name: 'TrueNAS CORE 13.0-U6.2',
        filename: 'TrueNAS-13.0-U6.2.iso',
        os_type: 'truenas',
        version: '13.0-U6.2',
        architecture: 'amd64',
        download_url: 'https://download-core.sys.truenas.net/13.0/STABLE/U6.2/x64/TrueNAS-13.0-U6.2.iso',
        icon: '💾'
      },
      // Proxmox VE
      {
        name: 'Proxmox VE 8.3',
        filename: 'proxmox-ve_8.3-1.iso',
        os_type: 'proxmox',
        version: '8.3',
        architecture: 'amd64',
        download_url: 'https://www.proxmox.com/en/downloads?task=callelement&format=raw&item_id=859&element=f85c494b-2b32-4109-b8c1-083cca2b7db6&method=download',
        icon: '📦'
      },
      // Untangle NG Firewall
      {
        name: 'Untangle NG Firewall 16.3',
        filename: 'ngfw-untangle-16.3.2-amd64.iso',
        os_type: 'other',
        version: '16.3.2',
        architecture: 'amd64',
        download_url: 'https://downloads.untangle.com/public/current-release/NGFW/ngfw-untangle-16.3.2-amd64.iso',
        icon: '🛡️'
      },
      // Alpine Linux
      {
        name: 'Alpine Linux 3.21',
        filename: 'alpine-virt-3.21.0-x86_64.iso',
        os_type: 'other',
        version: '3.21.0',
        architecture: 'amd64',
        download_url: 'https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/x86_64/alpine-virt-3.21.0-x86_64.iso',
        icon: '⛰️'
      },
      // Zentyal Server
      {
        name: 'Zentyal Server 8.0',
        filename: 'zentyal-8.0-development-amd64.iso',
        os_type: 'other',
        version: '8.0',
        architecture: 'amd64',
        download_url: 'https://download.zentyal.com/zentyal-8.0-development-amd64.iso',
        icon: '🏢'
      }
    ])

    const sortedPredefinedISOs = computed(() => {
      return [...predefinedISOs.value].sort((a, b) => a.name.localeCompare(b.name))
    })

    const toggleISOSelection = (predefined) => {
      const index = selectedISONames.value.indexOf(predefined.name)
      if (index > -1) {
        selectedISONames.value.splice(index, 1)
      } else {
        selectedISONames.value.push(predefined.name)
      }
    }

    const isISOSelected = (isoName) => {
      return selectedISONames.value.includes(isoName)
    }

    const getSelectedISOs = () => {
      return predefinedISOs.value.filter(iso => selectedISONames.value.includes(iso.name))
    }

    const fetchISOs = async () => {
      loading.value = true
      try {
        const response = await api.isos.list()
        // Sort ISOs alphabetically by name
        isos.value = response.data.sort((a, b) => a.name.localeCompare(b.name))
      } catch (error) {
        console.error('Failed to fetch ISOs:', error)
      } finally {
        loading.value = false
      }
    }

    const onFileSelected = (event) => {
      const file = event.target.files[0]
      if (file) {
        selectedFile.value = file
        if (!uploadForm.value.name) {
          uploadForm.value.name = file.name.replace('.iso', '')
        }
      }
    }

    const saveSelectedISOs = () => {
      if (selectedISONames.value.length === 0) {
        toast.error('Please select at least one ISO')
        return
      }

      const selectedISOs = getSelectedISOs()
      const count = selectedISOs.length

      // Fire off all downloads without waiting - completely async
      selectedISOs.forEach(iso => {
        api.isos.downloadFromUrl({
          url: iso.download_url,
          name: iso.name,
          os_type: iso.os_type,
          version: iso.version,
          architecture: iso.architecture
        }).catch(error => {
          console.error(`Failed to queue ${iso.name}:`, error)
        })
      })

      // Show success immediately
      toast.success(`Queued ${count} ISO${count > 1 ? 's' : ''} for download`)

      // Close modal immediately
      closeModal()

      // Refresh the list after a short delay to show queued downloads
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

        // Real-time upload progress tracking (HTTP upload phase)
        const onUploadProgress = (progressEvent) => {
          if (progressEvent.total) {
            // HTTP upload is phase 1 (0-50% of total progress)
            const percentCompleted = Math.round((progressEvent.loaded * 50) / progressEvent.total)
            uploadProgress.value = percentCompleted
            uploadedBytes.value = progressEvent.loaded
            totalBytes.value = progressEvent.total

            // Calculate upload speed
            const elapsedTime = (Date.now() - uploadStartTime) / 1000 // seconds
            if (elapsedTime > 0) {
              uploadSpeed.value = progressEvent.loaded / elapsedTime // bytes per second
            }
          }
        }

        const response = await api.isos.upload(formData, onUploadProgress)
        const isoId = response.data.id

        // HTTP upload complete - now poll backend for processing progress
        toast.info('Upload complete, processing file...', { timeout: 2000 })

        // Poll for backend progress (copying + checksum calculation)
        let backendComplete = false
        while (!backendComplete) {
          await new Promise(resolve => setTimeout(resolve, 500)) // Poll every 500ms

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
              // Map backend progress (0-100) to display progress (50-100)
              uploadProgress.value = 50 + Math.round(backendProgress.progress / 2)
            }
          } catch (error) {
            // If progress endpoint fails, assume complete
            console.warn('Failed to get progress, assuming complete:', error)
            backendComplete = true
            uploadProgress.value = 100
          }
        }

        // Small delay to show 100% completion
        await new Promise(resolve => setTimeout(resolve, 500))

        closeModal()
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
        if (response.data.status === 'valid') {
          toast.success('ISO checksum is valid')
        } else {
          toast.error('ISO checksum verification failed')
        }
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

    const formatOSType = (osType) => {
      const osMap = {
        ubuntu: 'Ubuntu',
        debian: 'Debian',
        centos: 'CentOS',
        rocky: 'Rocky Linux',
        alma: 'AlmaLinux',
        windows_server_2019: 'Windows Server 2019',
        windows_server_2022: 'Windows Server 2022',
        windows_10: 'Windows 10',
        windows_11: 'Windows 11'
      }
      return osMap[osType] || osType
    }

    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
    }

    const formatTimeRemaining = () => {
      if (uploadSpeed.value === 0 || uploadedBytes.value === 0) return 'Calculating...'

      const remainingBytes = totalBytes.value - uploadedBytes.value
      const secondsRemaining = remainingBytes / uploadSpeed.value

      if (secondsRemaining < 60) {
        return Math.ceil(secondsRemaining) + 's'
      } else if (secondsRemaining < 3600) {
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
      downloading.value = true
      try {
        await api.isos.downloadFromUrl(downloadForm.value)
        toast.success('ISO download started successfully')
        closeModal()
        await fetchISOs()
      } catch (error) {
        console.error('Failed to download ISO:', error)
        toast.error('Failed to download ISO')
      } finally {
        downloading.value = false
      }
    }

    const closeModal = () => {
      showAddModal.value = false
      isoSelectionMode.value = null
      selectedISONames.value = []
      uploadForm.value = {
        name: '',
        os_type: '',
        version: '',
        architecture: 'amd64'
      }
      downloadForm.value = {
        url: '',
        name: '',
        os_type: '',
        version: '',
        architecture: 'amd64'
      }
      selectedFile.value = null
      uploadedBytes.value = 0
      totalBytes.value = 0
      uploadSpeed.value = 0
    }

    onMounted(() => {
      fetchISOs()
    })

    return {
      isos,
      loading,
      uploading,
      downloading,
      saving,
      uploadProgress,
      uploadedBytes,
      totalBytes,
      uploadSpeed,
      showAddModal,
      isoSelectionMode,
      selectedISONames,
      selectedFile,
      uploadForm,
      downloadForm,
      predefinedISOs,
      sortedPredefinedISOs,
      onFileSelected,
      uploadISO,
      downloadFromUrl,
      saveSelectedISOs,
      toggleISOSelection,
      isISOSelected,
      verifyISO,
      deleteISO,
      closeModal,
      formatOSType,
      formatBytes,
      formatTimeRemaining
    }
  }
}
</script>

<style scoped>
.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
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
  margin-top: 0;
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

.upload-stats {
  margin-bottom: 1rem;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid #475569;
}

.stat-row:last-child {
  border-bottom: none;
}

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
  position: relative;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  transition: width 0.2s ease;
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
}

/* Selection Mode Styles */
.selection-mode {
  padding: 2rem 1.5rem;
}

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
  position: relative;
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
  padding: 0.25rem 0;
  padding-left: 1.5rem;
  position: relative;
}

.selection-list li::before {
  content: '✓';
  position: absolute;
  left: 0;
  color: #4ade80;
  font-weight: bold;
  font-size: 1rem;
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
</style>
