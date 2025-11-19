<template>
  <div class="iso-images-page">
    <div class="card">
      <div class="card-header">
        <h3>ISO Images</h3>
        <div class="flex gap-1">
          <button @click="showUploadModal = true" class="btn btn-primary">+ Upload ISO</button>
          <button @click="showDownloadModal = true" class="btn btn-outline">Download from URL</button>
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
              <td class="text-xs text-muted">{{ iso.checksum ? iso.checksum.substring(0, 16) + '...' : 'N/A' }}</td>
              <td>
                <span :class="['badge', iso.is_available ? 'badge-success' : 'badge-danger']">
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

    <!-- Upload Modal -->
    <div v-if="showUploadModal" class="modal" @click="showUploadModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Upload ISO Image</h3>
          <button @click="showUploadModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="uploadISO" class="modal-body">
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

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="uploading || !selectedFile">
              {{ uploading ? 'Uploading...' : 'Upload ISO' }}
            </button>
            <button type="button" @click="showUploadModal = false" class="btn btn-outline" :disabled="uploading">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Download from URL Modal -->
    <div v-if="showDownloadModal" class="modal" @click="showDownloadModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Download ISO from URL</h3>
          <button @click="showDownloadModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="downloadFromUrl" class="modal-body">
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

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="downloading">
              {{ downloading ? 'Downloading...' : 'Download ISO' }}
            </button>
            <button type="button" @click="showDownloadModal = false" class="btn btn-outline" :disabled="downloading">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
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
    const uploadProgress = ref(0)
    const uploadedBytes = ref(0)
    const totalBytes = ref(0)
    const uploadSpeed = ref(0)
    const showUploadModal = ref(false)
    const showDownloadModal = ref(false)
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

    const fetchISOs = async () => {
      loading.value = true
      try {
        const response = await api.isos.list()
        isos.value = response.data
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

        showUploadModal.value = false

        // Reset form
        uploadForm.value = {
          name: '',
          os_type: '',
          version: '',
          architecture: 'amd64'
        }
        selectedFile.value = null
        uploadedBytes.value = 0
        totalBytes.value = 0
        uploadSpeed.value = 0

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
        showDownloadModal.value = false

        // Reset form
        downloadForm.value = {
          url: '',
          name: '',
          os_type: '',
          version: '',
          architecture: 'amd64'
        }

        await fetchISOs()
      } catch (error) {
        console.error('Failed to download ISO:', error)
      } finally {
        downloading.value = false
      }
    }

    onMounted(() => {
      fetchISOs()
    })

    return {
      isos,
      loading,
      uploading,
      downloading,
      uploadProgress,
      uploadedBytes,
      totalBytes,
      uploadSpeed,
      showUploadModal,
      showDownloadModal,
      selectedFile,
      uploadForm,
      downloadForm,
      onFileSelected,
      uploadISO,
      downloadFromUrl,
      verifyISO,
      deleteISO,
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
  background: white;
  border-radius: 0.5rem;
  max-width: 600px;
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

.modal-header h3 {
  margin: 0;
}

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

.upload-progress {
  margin-top: 1rem;
  padding: 1rem;
  background-color: var(--background);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
}

.upload-stats {
  margin-bottom: 1rem;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border-color);
}

.stat-row:last-child {
  border-bottom: none;
}

.stat-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.stat-value {
  font-size: 0.875rem;
  color: var(--text-primary);
  font-weight: 600;
  font-family: monospace;
}

.progress-bar {
  height: 1.25rem;
  background-color: var(--border-color);
  border-radius: 9999px;
  overflow: hidden;
  position: relative;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
  transition: width 0.2s ease;
  box-shadow: 0 0 10px rgba(37, 99, 235, 0.5);
}
</style>
