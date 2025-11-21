<template>
  <div class="cloud-images-page">
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
          <button @click="showAddModal = true" class="btn btn-primary">+ Add Cloud Image</button>
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

      <div v-if="loading" class="loading-spinner"></div>

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
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="image in images" :key="image.id">
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
                  <span class="text-xs text-muted">{{ image.download_progress }}%</span>
                </div>
                <span v-else-if="image.is_downloaded" class="badge badge-success">Downloaded</span>
                <span v-else-if="image.download_status === 'error'" class="badge badge-danger">Error</span>
                <span v-else class="badge badge-secondary">Not Downloaded</span>
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
                    v-if="image.download_status === 'downloading'"
                    class="btn btn-secondary btn-sm"
                    disabled
                  >
                    Downloading...
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
              <label v-for="image in images" :key="image.id" class="checkbox-item">
                <input
                  type="checkbox"
                  :value="image.id"
                  v-model="setupForm.selectedImageIds"
                />
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
          <button @click="showSetupModal = false" class="btn btn-outline" :disabled="settingUpTemplates">
            Cancel
          </button>
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
    <div v-if="showAddModal" class="modal" @click="showAddModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>{{ editingImage ? 'Edit' : 'Add' }} Cloud Image</h3>
          <button @click="closeModal" class="btn-close">×</button>
        </div>

        <!-- Selection Mode: Choose between Available or Custom -->
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
                <p>Choose from 14 popular cloud images</p>
                <ul class="selection-list">
                  <li>Ubuntu, Debian, Rocky, Alma</li>
                  <li>Fedora, CentOS, openSUSE</li>
                  <li>Arch Linux</li>
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
            <button @click="imageSelectionMode = null" class="btn btn-outline btn-sm">
              ← Back to Selection
            </button>
            <h4>Select a Cloud Image</h4>
          </div>

          <div class="predefined-images-grid">
            <div
              v-for="predefined in predefinedImages"
              :key="predefined.name"
              @click="selectPredefinedImage(predefined)"
              :class="['predefined-image-card', { selected: imageForm.name === predefined.name }]"
            >
              <div class="predefined-image-icon">
                {{ predefined.icon }}
              </div>
              <div class="predefined-image-info">
                <div class="predefined-image-name">{{ predefined.name }}</div>
                <div class="predefined-image-details">{{ predefined.os_type }} {{ predefined.version }}</div>
              </div>
              <div v-if="imageForm.name === predefined.name" class="predefined-image-check">✓</div>
            </div>
          </div>

          <div v-if="imageForm.name" class="selected-image-preview">
            <h5>Selected: {{ imageForm.name }}</h5>
            <p class="text-xs text-muted">{{ imageForm.download_url }}</p>
          </div>

          <div class="modal-footer">
            <button type="button" @click="closeModal" class="btn btn-outline">Cancel</button>
            <button
              type="button"
              @click="saveImage"
              :disabled="!imageForm.name || saving"
              class="btn btn-primary"
            >
              {{ saving ? 'Adding...' : 'Add Selected Image' }}
            </button>
          </div>
        </div>

        <!-- Custom Image Form -->
        <form v-if="editingImage || imageSelectionMode === 'custom'" @submit.prevent="saveImage" class="modal-body">
          <div v-if="!editingImage" class="mode-header">
            <button type="button" @click="imageSelectionMode = null" class="btn btn-outline btn-sm">
              ← Back to Selection
            </button>
            <h4>Custom Cloud Image Details</h4>
          </div>

          <div class="form-group">
            <label class="form-label">Display Name *</label>
            <input v-model="imageForm.name" class="form-control" required placeholder="Ubuntu 24.04 LTS Cloud Image" />
          </div>

          <div class="form-group">
            <label class="form-label">Filename *</label>
            <input v-model="imageForm.filename" class="form-control" required placeholder="ubuntu-24.04-server-cloudimg-amd64.img" />
            <p class="text-xs text-muted mt-1">The filename of the cloud image file</p>
          </div>

          <div class="form-group">
            <label class="form-label">Download URL *</label>
            <input v-model="imageForm.download_url" class="form-control" required type="url" placeholder="https://cloud-images.ubuntu.com/..." />
            <p class="text-xs text-muted mt-1">Direct download URL for the cloud image</p>
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
            <button type="button" @click="closeModal" class="btn btn-outline">Cancel</button>
            <button type="submit" :disabled="saving" class="btn btn-primary">
              {{ saving ? 'Saving...' : (editingImage ? 'Update' : 'Add') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'CloudImages',
  setup() {
    const toast = useToast()
    const images = ref([])
    const nodes = ref([])
    const loading = ref(false)
    const showAddModal = ref(false)
    const showSetupModal = ref(false)
    const editingImage = ref(null)
    const saving = ref(false)
    const imageSelectionMode = ref(null) // 'available' or 'custom'
    const settingUpTemplates = ref(false)
    const templateStatus = ref({})
    const checkingTemplates = ref(false)
    const fetchingLatest = ref(false)
    let refreshInterval = null

    const imageForm = ref({
      name: '',
      filename: '',
      download_url: '',
      os_type: '',
      version: '',
      architecture: 'amd64',
      checksum: ''
    })

    const setupForm = ref({
      selectedNodeId: '',
      selectedImageIds: []
    })

    const predefinedImages = ref([
      {
        name: 'Ubuntu 24.04 LTS (Noble)',
        filename: 'noble-server-cloudimg-amd64.img',
        os_type: 'ubuntu',
        version: '24.04',
        architecture: 'amd64',
        download_url: 'https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img',
        icon: '🟠'
      },
      {
        name: 'Ubuntu 22.04 LTS (Jammy)',
        filename: 'jammy-server-cloudimg-amd64.img',
        os_type: 'ubuntu',
        version: '22.04',
        architecture: 'amd64',
        download_url: 'https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img',
        icon: '🟠'
      },
      {
        name: 'Ubuntu 20.04 LTS (Focal)',
        filename: 'focal-server-cloudimg-amd64.img',
        os_type: 'ubuntu',
        version: '20.04',
        architecture: 'amd64',
        download_url: 'https://cloud-images.ubuntu.com/focal/current/focal-server-cloudimg-amd64.img',
        icon: '🟠'
      },
      {
        name: 'Debian 12 (Bookworm)',
        filename: 'debian-12-generic-amd64.qcow2',
        os_type: 'debian',
        version: '12',
        architecture: 'amd64',
        download_url: 'https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2',
        icon: '🔴'
      },
      {
        name: 'Debian 11 (Bullseye)',
        filename: 'debian-11-generic-amd64.qcow2',
        os_type: 'debian',
        version: '11',
        architecture: 'amd64',
        download_url: 'https://cloud.debian.org/images/cloud/bullseye/latest/debian-11-generic-amd64.qcow2',
        icon: '🔴'
      },
      {
        name: 'Rocky Linux 9',
        filename: 'Rocky-9-GenericCloud-Base.latest.x86_64.qcow2',
        os_type: 'rocky',
        version: '9',
        architecture: 'amd64',
        download_url: 'https://download.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud-Base.latest.x86_64.qcow2',
        icon: '🟢'
      },
      {
        name: 'Rocky Linux 8',
        filename: 'Rocky-8-GenericCloud-Base.latest.x86_64.qcow2',
        os_type: 'rocky',
        version: '8',
        architecture: 'amd64',
        download_url: 'https://download.rockylinux.org/pub/rocky/8/images/x86_64/Rocky-8-GenericCloud-Base.latest.x86_64.qcow2',
        icon: '🟢'
      },
      {
        name: 'AlmaLinux 9',
        filename: 'AlmaLinux-9-GenericCloud-latest.x86_64.qcow2',
        os_type: 'alma',
        version: '9',
        architecture: 'amd64',
        download_url: 'https://repo.almalinux.org/almalinux/9/cloud/x86_64/images/AlmaLinux-9-GenericCloud-latest.x86_64.qcow2',
        icon: '🔵'
      },
      {
        name: 'AlmaLinux 8',
        filename: 'AlmaLinux-8-GenericCloud-latest.x86_64.qcow2',
        os_type: 'alma',
        version: '8',
        architecture: 'amd64',
        download_url: 'https://repo.almalinux.org/almalinux/8/cloud/x86_64/images/AlmaLinux-8-GenericCloud-latest.x86_64.qcow2',
        icon: '🔵'
      },
      {
        name: 'Fedora Cloud 40',
        filename: 'Fedora-Cloud-Base-Generic.x86_64-40.qcow2',
        os_type: 'fedora',
        version: '40',
        architecture: 'amd64',
        download_url: 'https://download.fedoraproject.org/pub/fedora/linux/releases/40/Cloud/x86_64/images/Fedora-Cloud-Base-Generic.x86_64-40-1.14.qcow2',
        icon: '🔷'
      },
      {
        name: 'Fedora Cloud 39',
        filename: 'Fedora-Cloud-Base-Generic.x86_64-39.qcow2',
        os_type: 'fedora',
        version: '39',
        architecture: 'amd64',
        download_url: 'https://download.fedoraproject.org/pub/fedora/linux/releases/39/Cloud/x86_64/images/Fedora-Cloud-Base-Generic.x86_64-39-1.5.qcow2',
        icon: '🔷'
      },
      {
        name: 'CentOS Stream 9',
        filename: 'CentOS-Stream-GenericCloud-9.qcow2',
        os_type: 'centos',
        version: '9',
        architecture: 'amd64',
        download_url: 'https://cloud.centos.org/centos/9-stream/x86_64/images/CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2',
        icon: '🟣'
      },
      {
        name: 'openSUSE Leap 15.6',
        filename: 'openSUSE-Leap-15.6-OpenStack.x86_64.qcow2',
        os_type: 'opensuse',
        version: '15.6',
        architecture: 'amd64',
        download_url: 'https://download.opensuse.org/distribution/leap/15.6/appliances/openSUSE-Leap-15.6-OpenStack.x86_64-Cloud.qcow2',
        icon: '🟢'
      },
      {
        name: 'Arch Linux',
        filename: 'Arch-Linux-x86_64-cloudimg.qcow2',
        os_type: 'other',
        version: 'latest',
        architecture: 'amd64',
        download_url: 'https://gitlab.archlinux.org/archlinux/arch-boxes/-/jobs/artifacts/master/raw/output/Arch-Linux-x86_64-cloudimg.qcow2?job=build:secure',
        icon: '🔵'
      }
    ])

    const selectPredefinedImage = (predefined) => {
      imageForm.value = {
        name: predefined.name,
        filename: predefined.filename,
        download_url: predefined.download_url,
        os_type: predefined.os_type,
        version: predefined.version,
        architecture: predefined.architecture,
        checksum: ''
      }
    }

    const fetchImages = async () => {
      loading.value = true
      try {
        const response = await api.cloudImages.list()
        images.value = response.data
      } catch (error) {
        console.error('Failed to fetch cloud images:', error)
      } finally {
        loading.value = false
      }
    }

    const downloadImage = async (imageId) => {
      try {
        await api.cloudImages.download(imageId)
        toast.success('Cloud image download started')
        // Start polling for progress
        startProgressPolling()
      } catch (error) {
        console.error('Failed to start download:', error)
        toast.error('Failed to start download')
      }
    }

    const saveImage = async () => {
      saving.value = true
      try {
        if (editingImage.value) {
          await api.cloudImages.update(editingImage.value.id, imageForm.value)
          toast.success('Cloud image updated successfully')
        } else {
          await api.cloudImages.create(imageForm.value)
          toast.success('Cloud image added successfully')
        }
        closeModal()
        fetchImages()
      } catch (error) {
        console.error('Failed to save cloud image:', error)
        toast.error('Failed to save cloud image')
      } finally {
        saving.value = false
      }
    }

    const editImage = (image) => {
      editingImage.value = image
      imageForm.value = {
        name: image.name,
        filename: image.filename,
        download_url: image.download_url,
        os_type: image.os_type,
        version: image.version || '',
        architecture: image.architecture,
        checksum: image.checksum || ''
      }
      showAddModal.value = true
    }

    const deleteImage = async (imageId) => {
      if (!confirm('Are you sure you want to delete this cloud image?')) {
        return
      }

      try {
        await api.cloudImages.delete(imageId)
        toast.success('Cloud image deleted successfully')
        fetchImages()
      } catch (error) {
        console.error('Failed to delete cloud image:', error)
        toast.error('Failed to delete cloud image')
      }
    }

    const closeModal = () => {
      showAddModal.value = false
      editingImage.value = null
      imageSelectionMode.value = null
      imageForm.value = {
        name: '',
        filename: '',
        download_url: '',
        os_type: '',
        version: '',
        architecture: 'amd64',
        checksum: ''
      }
    }

    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
    }

    const formatOSType = (osType) => {
      const map = {
        ubuntu: 'Ubuntu',
        debian: 'Debian',
        centos: 'CentOS',
        rocky: 'Rocky Linux',
        alma: 'AlmaLinux',
        fedora: 'Fedora',
        opensuse: 'openSUSE',
        other: 'Other'
      }
      return map[osType] || osType
    }

    const fetchNodes = async () => {
      try {
        // First fetch all hosts
        const hostsResponse = await api.proxmox.listHosts()
        const allNodes = []

        // Then fetch nodes for each host
        for (const host of hostsResponse.data) {
          try {
            const nodesResponse = await api.proxmox.listNodes(host.id)
            if (nodesResponse.data && nodesResponse.data.length > 0) {
              nodesResponse.data.forEach(node => {
                allNodes.push({
                  id: node.id,
                  node_name: node.node_name,
                  proxmox_host_name: host.name
                })
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
        setupForm.value = {
          selectedNodeId: '',
          selectedImageIds: []
        }
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

        // Stop polling if no downloads are in progress
        const hasActiveDownloads = images.value.some(img => img.download_status === 'downloading')
        if (!hasActiveDownloads && refreshInterval) {
          clearInterval(refreshInterval)
          refreshInterval = null
        }
      }, 2000) // Poll every 2 seconds
    }

    const checkAllTemplates = async () => {
      checkingTemplates.value = true
      templateStatus.value = {}
      try {
        // Fetch all hosts and nodes
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

    const getTemplateCount = (templates) => {
      return Object.values(templates).filter(exists => exists).length
    }

    const fetchLatestImages = async () => {
      fetchingLatest.value = true
      try {
        const response = await api.cloudImages.fetchLatest()

        if (response.data.updated_count > 0) {
          // Check if images were added (new) or updated (existing)
          const hasAdded = response.data.updated_images?.some(img => img.status === 'added')
          if (hasAdded) {
            toast.success(`Added ${response.data.updated_count} cloud image(s) to database`)
          } else {
            toast.success(`Updated ${response.data.updated_count} cloud image(s)`)
          }
          // Reload the images list
          await fetchImages()
        } else {
          toast.info('All cloud images are up to date')
        }

        if (response.data.errors && response.data.errors.length > 0) {
          console.error('Cloud image errors:', response.data.errors)
          toast.warning(`Some images could not be updated: ${response.data.errors.length} errors`)
        }
      } catch (error) {
        console.error('Failed to fetch latest cloud images:', error)
        toast.error('Failed to fetch latest cloud images')
      } finally {
        fetchingLatest.value = false
      }
    }

    onMounted(() => {
      fetchImages()
      // Check if any downloads are in progress
      const hasActiveDownloads = images.value.some(img => img.download_status === 'downloading')
      if (hasActiveDownloads) {
        startProgressPolling()
      }
    })

    onUnmounted(() => {
      if (refreshInterval) {
        clearInterval(refreshInterval)
      }
    })

    return {
      images,
      nodes,
      loading,
      showAddModal,
      showSetupModal,
      editingImage,
      imageForm,
      setupForm,
      saving,
      imageSelectionMode,
      settingUpTemplates,
      templateStatus,
      checkingTemplates,
      fetchingLatest,
      predefinedImages,
      fetchImages,
      downloadImage,
      saveImage,
      editImage,
      deleteImage,
      closeModal,
      setupTemplates,
      openSetupModal,
      checkAllTemplates,
      getTemplateCount,
      fetchLatestImages,
      selectPredefinedImage,
      formatBytes,
      formatOSType
    }
  }
}
</script>

<style scoped>
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
  width: 100%;
  height: 100%;
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

/* Fix button contrast in modal */
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

.modal-large {
  max-width: 900px;
}

.predefined-images-section {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
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

.divider {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 1.5rem 0;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  border-bottom: 2px solid #64748b;
}

.divider span {
  padding: 0 1rem;
  color: #cbd5e1;
  font-size: 0.875rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

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
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  max-width: 800px;
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

.selected-image-preview {
  margin-top: 1.5rem;
  padding: 1.25rem;
  background: rgba(59, 130, 246, 0.15);
  border: 2px solid #60a5fa;
  border-radius: 8px;
}

.selected-image-preview h5 {
  color: #ffffff;
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.selected-image-preview p {
  color: #cbd5e1;
  margin: 0;
  word-break: break-all;
}
</style>
