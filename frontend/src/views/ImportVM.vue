<template>
  <div class="import-vm">
    <div class="page-header">
      <h1>Import VM</h1>
      <p class="subtitle">Import virtual machines from VMware, VirtualBox, Hyper-V, or upload any OVA/OVF/VMDK file</p>
    </div>

    <!-- Step indicators -->
    <div class="steps">
      <div
        v-for="(step, i) in steps"
        :key="i"
        class="step"
        :class="{ active: currentStep === i, completed: currentStep > i }"
      >
        <div class="step-circle">
          <span v-if="currentStep > i">✓</span>
          <span v-else>{{ i + 1 }}</span>
        </div>
        <span class="step-label">{{ step }}</span>
      </div>
    </div>

    <!-- ================================================================== -->
    <!-- Step 0: Source selection                                            -->
    <!-- ================================================================== -->
    <div v-if="currentStep === 0" class="card">
      <!-- Source tabs -->
      <div class="source-tabs">
        <button
          class="source-tab"
          :class="{ active: sourceMode === 'file' }"
          @click="sourceMode = 'file'"
        >
          📁 Upload File
        </button>
        <button
          class="source-tab"
          :class="{ active: sourceMode === 'vmware' }"
          @click="sourceMode = 'vmware'"
        >
          ☁️ Connect to VMware
        </button>
      </div>

      <!-- ---- File upload panel ---- -->
      <div v-if="sourceMode === 'file'">
        <p class="hint">Supported: OVA, OVF, VMDK, VHD, VHDX, QCOW2, RAW, ZIP</p>

        <div
          class="drop-zone"
          :class="{ 'drag-over': isDragging, 'has-file': selectedFile }"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="onDrop"
          @click="$refs.fileInput.click()"
        >
          <input
            ref="fileInput"
            type="file"
            accept=".ova,.ovf,.vmdk,.vhd,.vhdx,.qcow2,.img,.raw,.zip"
            style="display:none"
            @change="onFileSelected"
          />
          <template v-if="!selectedFile">
            <div class="drop-icon">📦</div>
            <p class="drop-text">Drag &amp; drop a VM image here, or click to browse</p>
            <p class="drop-hint">OVA · OVF · VMDK · VHD · VHDX · QCOW2 · RAW</p>
          </template>
          <template v-else>
            <div class="drop-icon">✅</div>
            <p class="drop-text">{{ selectedFile.name }}</p>
            <p class="drop-hint">{{ formatBytes(selectedFile.size) }}</p>
          </template>
        </div>

        <div v-if="uploading" class="progress-section">
          <div class="progress-label">
            <span>Uploading...</span><span>{{ uploadProgress }}%</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div></div>
        </div>

        <div class="actions">
          <button class="btn btn-primary" :disabled="!selectedFile || uploading" @click="uploadFile">
            {{ uploading ? 'Uploading...' : 'Upload & Analyse' }}
          </button>
        </div>
      </div>

      <!-- ---- VMware panel ---- -->
      <div v-if="sourceMode === 'vmware'">
        <p class="hint">Connect to an ESXi host or vCenter server to browse and import VMs directly.</p>

        <!-- Connection form -->
        <div class="form-grid three-col">
          <div class="form-group span-2">
            <label>Hostname / IP</label>
            <input v-model="vmware.hostname" type="text" class="input" placeholder="esxi.example.com or 192.168.1.10" />
          </div>
          <div class="form-group">
            <label>Port</label>
            <input v-model.number="vmware.port" type="number" class="input" value="443" />
          </div>
          <div class="form-group">
            <label>Username</label>
            <input v-model="vmware.username" type="text" class="input" placeholder="root" />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input v-model="vmware.password" type="password" class="input" />
          </div>
          <div class="form-group" style="justify-content: flex-end; padding-top: 1.4rem;">
            <label class="checkbox-label">
              <input v-model="vmware.verify_ssl" type="checkbox" />
              Verify SSL
            </label>
          </div>
        </div>

        <div class="actions" style="margin-bottom: 1.5rem;">
          <button
            class="btn btn-secondary"
            :disabled="vmwareConnecting || !vmware.hostname || !vmware.username"
            @click="vmwareConnect"
          >
            {{ vmwareConnecting ? 'Connecting...' : 'Connect & List VMs' }}
          </button>
        </div>

        <!-- Connection info banner -->
        <div v-if="vmwareInfo" class="info-box">
          Connected to <strong>{{ vmwareInfo.full_name }}</strong>
          ({{ vmwareInfo.api_type === 'VirtualCenter' ? 'vCenter' : 'ESXi' }})
          v{{ vmwareInfo.version }}
        </div>

        <!-- VM list -->
        <div v-if="vmwareVMs.length > 0" class="vm-list-section">
          <h3>Select a VM to Import</h3>
          <div class="vm-list">
            <div
              v-for="vm in vmwareVMs"
              :key="vm.moref"
              class="vm-row"
              :class="{ selected: selectedVMRef === vm.moref }"
              @click="selectedVMRef = vm.moref; selectedVMMeta = vm"
            >
              <div class="vm-row-radio">
                <input type="radio" :value="vm.moref" v-model="selectedVMRef" />
              </div>
              <div class="vm-row-info">
                <div class="vm-row-name">
                  {{ vm.name }}
                  <span class="power-badge" :class="vm.power_state === 'poweredOn' ? 'on' : 'off'">
                    {{ vm.power_state === 'poweredOn' ? 'On' : 'Off' }}
                  </span>
                </div>
                <div class="vm-row-meta">
                  {{ vm.os }} &nbsp;·&nbsp;
                  {{ vm.cpu_cores }} vCPU &nbsp;·&nbsp;
                  {{ vm.memory_mb }} MB RAM &nbsp;·&nbsp;
                  {{ vm.total_disk_gb }} GB disk
                </div>
              </div>
            </div>
          </div>

          <div class="actions">
            <button
              class="btn btn-primary"
              :disabled="!selectedVMRef || vmwarePreparing"
              @click="vmwarePrepareImport"
            >
              {{ vmwarePreparing ? 'Starting download...' : 'Import Selected VM' }}
            </button>
          </div>
        </div>

        <!-- Download progress (while downloading VMDKs) -->
        <div v-if="vmwareDownloading" class="progress-section" style="margin-top: 1.5rem;">
          <div class="progress-label">
            <span>{{ vmwareDownloadStatus }}</span>
            <span>{{ vmwareDownloadProgress }}%</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: vmwareDownloadProgress + '%' }"></div>
          </div>
          <p class="hint" style="margin-top:.5rem">Downloading VMDK files from VMware. This may take a while for large disks.</p>
        </div>
      </div>
    </div>

    <!-- ================================================================== -->
    <!-- Step 1: Review parsed specs                                         -->
    <!-- ================================================================== -->
    <div v-if="currentStep === 1" class="card">
      <h2>Review VM Specifications</h2>
      <p class="hint">Values extracted from the image. Edit as needed.</p>

      <div class="form-grid">
        <div class="form-group">
          <label>VM Name</label>
          <input v-model="form.vm_name" type="text" class="input" placeholder="my-vm" />
        </div>
        <div class="form-group">
          <label>OS Type</label>
          <select v-model="form.os_type" class="input">
            <option value="other">Other / Unknown</option>
            <option value="ubuntu">Ubuntu</option>
            <option value="debian">Debian</option>
            <option value="centos">CentOS / RHEL</option>
            <option value="rocky">Rocky Linux</option>
            <option value="alma">AlmaLinux</option>
            <option value="windows">Windows</option>
            <option value="pfsense">pfSense</option>
            <option value="opnsense">OPNsense</option>
            <option value="freebsd">FreeBSD</option>
          </select>
        </div>
        <div class="form-group">
          <label>CPU Cores</label>
          <input v-model.number="form.cpu_cores" type="number" min="1" max="64" class="input" />
        </div>
        <div class="form-group">
          <label>Memory (MB)</label>
          <input v-model.number="form.memory_mb" type="number" min="256" step="256" class="input" />
          <span class="field-note">{{ (form.memory_mb / 1024).toFixed(1) }} GB</span>
        </div>
      </div>

      <div v-if="parsedSpecs.disks && parsedSpecs.disks.length" class="info-box">
        <strong>Detected disk(s):</strong>
        <ul>
          <li v-for="(disk, i) in parsedSpecs.disks" :key="i">
            {{ disk.filename || 'disk' + i }} — {{ disk.capacity_gb }} GB
          </li>
        </ul>
      </div>

      <div class="actions">
        <button class="btn btn-secondary" @click="currentStep = 0">Back</button>
        <button class="btn btn-primary" @click="currentStep = 2">Continue</button>
      </div>
    </div>

    <!-- ================================================================== -->
    <!-- Step 2: Select Proxmox target                                       -->
    <!-- ================================================================== -->
    <div v-if="currentStep === 2" class="card">
      <h2>Select Deployment Target</h2>

      <div class="form-grid">
        <div class="form-group">
          <label>Proxmox Host</label>
          <select v-model="form.proxmox_host_id" class="input" @change="onHostChange">
            <option value="" disabled>Select host...</option>
            <option v-for="h in proxmoxHosts" :key="h.id" :value="h.id">{{ h.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Node</label>
          <select v-model="form.node_id" class="input" :disabled="!form.proxmox_host_id" @change="onNodeChange">
            <option value="" disabled>Select node...</option>
            <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.node_name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Storage Pool</label>
          <select v-model="form.storage" class="input" :disabled="!form.node_id">
            <option value="" disabled>Select storage...</option>
            <option v-for="s in storages" :key="s.storage" :value="s.storage">
              {{ s.storage }} ({{ s.type }})
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>Network Bridge</label>
          <select v-model="form.network_bridge" class="input" :disabled="!form.node_id">
            <option v-for="n in networks" :key="n.iface" :value="n.iface">{{ n.iface }}</option>
          </select>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-secondary" @click="currentStep = 1">Back</button>
        <button
          class="btn btn-primary"
          :disabled="!form.proxmox_host_id || !form.node_id || !form.storage"
          @click="currentStep = 3"
        >Continue</button>
      </div>
    </div>

    <!-- ================================================================== -->
    <!-- Step 3: Credentials & confirm                                       -->
    <!-- ================================================================== -->
    <div v-if="currentStep === 3" class="card">
      <h2>Credentials &amp; Confirm</h2>
      <p class="hint">Credentials stored for VM management after import.</p>

      <div class="form-grid">
        <div class="form-group">
          <label>Username</label>
          <input v-model="form.username" type="text" class="input" placeholder="administrator" />
        </div>
        <div class="form-group">
          <label>Password</label>
          <input v-model="form.password" type="password" class="input" placeholder="Optional" />
        </div>
      </div>

      <div class="summary-box">
        <h3>Import Summary</h3>
        <table class="summary-table">
          <tr><td>Source</td><td>{{ sourceMode === 'vmware' ? `VMware (${vmware.hostname})` : jobFilename }}</td></tr>
          <tr><td>VM Name</td><td>{{ form.vm_name }}</td></tr>
          <tr><td>OS</td><td>{{ form.os_type }}</td></tr>
          <tr><td>CPU</td><td>{{ form.cpu_cores }} core(s)</td></tr>
          <tr><td>Memory</td><td>{{ form.memory_mb }} MB</td></tr>
          <tr><td>Storage</td><td>{{ form.storage }}</td></tr>
          <tr><td>Network</td><td>{{ form.network_bridge }}</td></tr>
        </table>
      </div>

      <div class="actions">
        <button class="btn btn-secondary" @click="currentStep = 2">Back</button>
        <button class="btn btn-primary" :disabled="deploying" @click="startDeploy">
          {{ deploying ? 'Deploying...' : 'Start Import' }}
        </button>
      </div>
    </div>

    <!-- ================================================================== -->
    <!-- Step 4: Progress                                                    -->
    <!-- ================================================================== -->
    <div v-if="currentStep === 4" class="card">
      <h2>Import Progress</h2>

      <div class="progress-section large">
        <div class="progress-label">
          <span>{{ progressStatus }}</span>
          <span>{{ progressValue }}%</span>
        </div>
        <div class="progress-bar">
          <div
            class="progress-fill"
            :class="{ error: importFailed, success: importCompleted }"
            :style="{ width: progressValue + '%' }"
          ></div>
        </div>
        <p class="status-msg" :class="{ error: importFailed }">{{ statusMessage }}</p>
      </div>

      <!-- Manual import command fallback -->
      <div v-if="manualImportCmd" class="warning-box">
        <strong>SSH import not available.</strong> Run this command manually on the Proxmox node:
        <pre class="code-block">{{ manualImportCmd }}</pre>
      </div>

      <!-- Success -->
      <div v-if="importCompleted" class="success-box">
        <p>VM imported successfully! VMID: <strong>{{ importedVmid }}</strong></p>
        <div class="actions">
          <button class="btn btn-primary" @click="$router.push('/vm-management')">Go to VM Management</button>
          <button class="btn btn-secondary" @click="resetWizard">Import Another</button>
        </div>
      </div>

      <!-- Error -->
      <div v-if="importFailed" class="error-box">
        <p>Import failed: {{ errorMessage }}</p>
        <div class="actions">
          <button class="btn btn-secondary" @click="resetWizard">Start Over</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'ImportVM',
  setup() {
    const router = useRouter()
    const toast = useToast()

    const steps = ['Source', 'Review Specs', 'Select Target', 'Confirm', 'Deploying']
    const currentStep = ref(0)
    const sourceMode = ref('file')  // 'file' | 'vmware'

    // --- File upload state ---
    const selectedFile = ref(null)
    const isDragging = ref(false)
    const uploading = ref(false)
    const uploadProgress = ref(0)

    // --- VMware connection state ---
    const vmware = ref({ hostname: '', username: 'root', password: '', port: 443, verify_ssl: false })
    const vmwareConnecting = ref(false)
    const vmwareInfo = ref(null)
    const vmwareVMs = ref([])
    const selectedVMRef = ref(null)
    const selectedVMMeta = ref(null)
    const vmwarePreparing = ref(false)
    const vmwareDownloading = ref(false)
    const vmwareDownloadProgress = ref(0)
    const vmwareDownloadStatus = ref('')

    // --- Shared job state ---
    const jobId = ref(null)
    const jobFilename = ref('')
    const parsedSpecs = ref({})

    // --- Form state ---
    const form = ref({
      vm_name: '', os_type: 'other', cpu_cores: 1, memory_mb: 512,
      proxmox_host_id: '', node_id: '', storage: '', network_bridge: 'vmbr0',
      username: 'administrator', password: '',
    })

    // --- Proxmox resource lists ---
    const proxmoxHosts = ref([])
    const nodes = ref([])
    const storages = ref([])
    const networks = ref([])

    // --- Deploy / progress state ---
    const deploying = ref(false)
    const progressValue = ref(0)
    const progressStatus = ref('')
    const statusMessage = ref('')
    const importCompleted = ref(false)
    const importFailed = ref(false)
    const errorMessage = ref('')
    const importedVmid = ref(null)
    const manualImportCmd = ref(null)
    let pollTimer = null

    // Load Proxmox hosts on mount
    const loadHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        proxmoxHosts.value = (res.data || []).filter(h => h.is_active)
      } catch (e) {
        console.error('Failed to load hosts:', e)
      }
    }
    loadHosts()

    // --- Proxmox cascade loaders ---
    const onHostChange = async () => {
      form.value.node_id = ''
      form.value.storage = ''
      nodes.value = []
      storages.value = []
      networks.value = []
      if (!form.value.proxmox_host_id) return
      try {
        const res = await api.proxmox.listNodes(form.value.proxmox_host_id)
        nodes.value = res.data || []
      } catch {
        toast.error('Failed to load nodes')
      }
    }

    const onNodeChange = async () => {
      form.value.storage = ''
      storages.value = []
      networks.value = []
      if (!form.value.node_id) return
      try {
        const [storRes, netRes] = await Promise.all([
          api.proxmox.getNodeStorage(form.value.node_id),
          api.proxmox.getNodeNetwork(form.value.node_id),
        ])
        storages.value = (storRes.data.storage || []).filter(s =>
          s.content && (s.content.includes('images') || s.content.includes('rootdir'))
        )
        networks.value = (netRes.data.network || []).filter(n =>
          n.type === 'bridge' || n.iface?.startsWith('vmbr')
        )
        if (networks.value.length) form.value.network_bridge = networks.value[0].iface
      } catch {
        toast.error('Failed to load node resources')
      }
    }

    // --- File helpers ---
    const formatBytes = (bytes) => {
      if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
      if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
      return `${(bytes / 1024 ** 3).toFixed(2)} GB`
    }

    const onDrop = (e) => {
      isDragging.value = false
      const file = e.dataTransfer.files[0]
      if (file) validateAndSetFile(file)
    }

    const onFileSelected = (e) => {
      const file = e.target.files[0]
      if (file) validateAndSetFile(file)
    }

    const validateAndSetFile = (file) => {
      const ext = '.' + file.name.split('.').pop().toLowerCase()
      const allowed = ['.ova', '.ovf', '.vmdk', '.vhd', '.vhdx', '.qcow2', '.img', '.raw', '.zip']
      if (!allowed.includes(ext)) { toast.error(`Unsupported file type: ${ext}`); return }
      selectedFile.value = file
    }

    const uploadFile = async () => {
      if (!selectedFile.value) return
      uploading.value = true
      uploadProgress.value = 0
      const fd = new FormData()
      fd.append('file', selectedFile.value)
      try {
        const res = await api.vmImport.upload(fd, (evt) => {
          if (evt.total) uploadProgress.value = Math.round((evt.loaded / evt.total) * 100)
        })
        const data = res.data
        jobId.value = data.job_id
        jobFilename.value = data.filename
        parsedSpecs.value = data.specs || {}
        _prefillForm(parsedSpecs.value)
        currentStep.value = 1
        toast.success('File uploaded and analysed!')
      } catch (e) {
        toast.error('Upload failed: ' + (e.response?.data?.detail || e.message))
      } finally {
        uploading.value = false
      }
    }

    // --- VMware helpers ---
    const vmwareConnect = async () => {
      vmwareConnecting.value = true
      vmwareInfo.value = null
      vmwareVMs.value = []
      selectedVMRef.value = null
      try {
        // Test connection first
        const testRes = await api.vmImport.vmwareTest({
          hostname: vmware.value.hostname,
          username: vmware.value.username,
          password: vmware.value.password,
          port: vmware.value.port,
          verify_ssl: vmware.value.verify_ssl,
        })
        vmwareInfo.value = testRes.data

        // Then list VMs
        const listRes = await api.vmImport.vmwareListVMs({
          hostname: vmware.value.hostname,
          username: vmware.value.username,
          password: vmware.value.password,
          port: vmware.value.port,
          verify_ssl: vmware.value.verify_ssl,
        })
        vmwareVMs.value = listRes.data.vms || []
        if (!vmwareVMs.value.length) toast.warning('Connected, but no VMs found.')
        else toast.success(`Connected! Found ${vmwareVMs.value.length} VM(s).`)
      } catch (e) {
        toast.error('Connection failed: ' + (e.response?.data?.detail || e.message))
      } finally {
        vmwareConnecting.value = false
      }
    }

    const vmwarePrepareImport = async () => {
      if (!selectedVMRef.value) return
      vmwarePreparing.value = true
      vmwareDownloading.value = true
      vmwareDownloadProgress.value = 0
      vmwareDownloadStatus.value = 'Connecting to VMware...'

      try {
        const res = await api.vmImport.vmwarePrepare({
          hostname: vmware.value.hostname,
          username: vmware.value.username,
          password: vmware.value.password,
          port: vmware.value.port,
          verify_ssl: vmware.value.verify_ssl,
          moref: selectedVMRef.value,
        })
        jobId.value = res.data.job_id
        jobFilename.value = `VMware: ${selectedVMMeta.value?.name || selectedVMRef.value}`

        // Poll until 'parsed' (download complete)
        pollDownload()
      } catch (e) {
        vmwarePreparing.value = false
        vmwareDownloading.value = false
        toast.error('Failed to start download: ' + (e.response?.data?.detail || e.message))
      }
    }

    const pollDownload = () => {
      const timer = setInterval(async () => {
        try {
          const res = await api.vmImport.getProgress(jobId.value)
          const data = res.data
          vmwareDownloadProgress.value = data.progress || 0
          vmwareDownloadStatus.value = data.status_message || ''

          if (data.status === 'parsed') {
            clearInterval(timer)
            vmwarePreparing.value = false
            vmwareDownloading.value = false
            // Populate specs from job
            const specs = data.specs || selectedVMMeta.value || {}
            parsedSpecs.value = specs
            _prefillForm(specs)
            toast.success('VMDK download complete. Review specs below.')
            currentStep.value = 1
          } else if (data.status === 'error') {
            clearInterval(timer)
            vmwarePreparing.value = false
            vmwareDownloading.value = false
            toast.error('Download failed: ' + (data.error || data.status_message))
          }
        } catch (e) {
          console.error('Download poll error:', e)
        }
      }, 2000)
    }

    // Pre-fill form from parsed specs
    const _prefillForm = (specs) => {
      if (!specs) return
      form.value.vm_name = specs.name || 'imported-vm'
      form.value.os_type = specs.os_type || 'other'
      form.value.cpu_cores = specs.cpu_cores || 1
      form.value.memory_mb = specs.memory_mb || 512
    }

    // --- Deploy ---
    const startDeploy = async () => {
      if (!jobId.value) return
      deploying.value = true
      currentStep.value = 4

      try {
        await api.vmImport.deploy(jobId.value, {
          proxmox_host_id: form.value.proxmox_host_id,
          node_id: form.value.node_id,
          storage: form.value.storage,
          vm_name: form.value.vm_name,
          cpu_cores: form.value.cpu_cores,
          memory_mb: form.value.memory_mb,
          network_bridge: form.value.network_bridge,
          os_type: form.value.os_type,
          username: form.value.username,
          password: form.value.password,
        })
        pollProgress()
      } catch (e) {
        importFailed.value = true
        errorMessage.value = e.response?.data?.detail || e.message
        deploying.value = false
      }
    }

    const pollProgress = () => {
      pollTimer = setInterval(async () => {
        try {
          const res = await api.vmImport.getProgress(jobId.value)
          const data = res.data
          progressValue.value = data.progress || 0
          progressStatus.value = data.status || ''
          statusMessage.value = data.status_message || ''
          if (data.manual_import_cmd) manualImportCmd.value = data.manual_import_cmd

          if (data.status === 'completed') {
            clearInterval(pollTimer)
            importCompleted.value = true
            importedVmid.value = data.vmid
            deploying.value = false
            toast.success('VM imported successfully!')
          } else if (data.status === 'error') {
            clearInterval(pollTimer)
            importFailed.value = true
            errorMessage.value = data.error || data.status_message || 'Unknown error'
            deploying.value = false
          }
        } catch (e) {
          console.error('Progress poll error:', e)
        }
      }, 2000)
    }

    const resetWizard = () => {
      if (pollTimer) clearInterval(pollTimer)
      currentStep.value = 0
      sourceMode.value = 'file'
      selectedFile.value = null
      uploadProgress.value = 0
      uploading.value = false
      jobId.value = null
      jobFilename.value = ''
      parsedSpecs.value = {}
      vmwareInfo.value = null
      vmwareVMs.value = []
      selectedVMRef.value = null
      selectedVMMeta.value = null
      vmwarePreparing.value = false
      vmwareDownloading.value = false
      form.value = {
        vm_name: '', os_type: 'other', cpu_cores: 1, memory_mb: 512,
        proxmox_host_id: '', node_id: '', storage: '', network_bridge: 'vmbr0',
        username: 'administrator', password: '',
      }
      deploying.value = false
      progressValue.value = 0
      progressStatus.value = ''
      statusMessage.value = ''
      importCompleted.value = false
      importFailed.value = false
      errorMessage.value = ''
      importedVmid.value = null
      manualImportCmd.value = null
    }

    onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer) })

    return {
      steps, currentStep, sourceMode,
      selectedFile, isDragging, uploading, uploadProgress,
      vmware, vmwareConnecting, vmwareInfo, vmwareVMs,
      selectedVMRef, selectedVMMeta,
      vmwarePreparing, vmwareDownloading, vmwareDownloadProgress, vmwareDownloadStatus,
      parsedSpecs, jobFilename,
      form,
      proxmoxHosts, nodes, storages, networks,
      deploying, progressValue, progressStatus, statusMessage,
      importCompleted, importFailed, errorMessage, importedVmid, manualImportCmd,
      onDrop, onFileSelected, formatBytes, uploadFile,
      vmwareConnect, vmwarePrepareImport,
      onHostChange, onNodeChange,
      startDeploy, resetWizard,
    }
  }
}
</script>

<style scoped>
.import-vm {
  max-width: 860px;
  margin: 0 auto;
  padding: 2rem;
}

.page-header {
  margin-bottom: 2rem;
}

.page-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0 0 0.5rem;
}

.subtitle {
  color: #6b7280;
  margin: 0;
}

/* Steps */
.steps {
  display: flex;
  align-items: center;
  margin-bottom: 2rem;
}

.step {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.step:not(:last-child)::after {
  content: '';
  flex: 1;
  height: 2px;
  background: #e5e7eb;
  margin: 0 0.5rem;
}

.step.completed:not(:last-child)::after {
  background: #3b82f6;
}

.step-circle {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
  flex-shrink: 0;
}

.step.active .step-circle { background: #3b82f6; color: white; }
.step.completed .step-circle { background: #059669; color: white; }

.step-label {
  font-size: 0.8rem;
  white-space: nowrap;
  color: #6b7280;
}

.step.active .step-label { color: #1f2937; font-weight: 600; }

/* Card */
.card {
  background: white;
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 1px 3px rgba(0,0,0,.1);
  margin-bottom: 1.5rem;
}

.card h2 {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0 0 0.5rem;
}

.hint {
  color: #6b7280;
  font-size: 0.875rem;
  margin-bottom: 1.5rem;
}

/* Source tabs */
.source-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 1.75rem;
  border-bottom: 2px solid #e5e7eb;
}

.source-tab {
  padding: 0.6rem 1.5rem;
  background: none;
  border: none;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  font-size: 0.95rem;
  font-weight: 500;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.15s;
}

.source-tab:hover { color: #374151; }
.source-tab.active { color: #3b82f6; border-bottom-color: #3b82f6; }

/* Drop zone */
.drop-zone {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 3rem 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 1.5rem;
}

.drop-zone:hover, .drop-zone.drag-over { border-color: #3b82f6; background: #eff6ff; }
.drop-zone.has-file { border-color: #10b981; background: #f0fdf4; }

.drop-icon { font-size: 3rem; margin-bottom: 0.75rem; }
.drop-text { font-size: 1rem; font-weight: 500; margin: 0 0 0.25rem; }
.drop-hint { font-size: 0.8rem; color: #6b7280; margin: 0; }

/* Forms */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
  margin-bottom: 1.5rem;
}

.form-grid.three-col {
  grid-template-columns: 1fr 1fr 1fr;
}

.span-2 { grid-column: span 2; }

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500 !important;
  cursor: pointer;
}

.input {
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 0.9rem;
  background: white;
  transition: border-color 0.15s;
}

.input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59,130,246,.1);
}

.input:disabled { background: #f9fafb; color: #9ca3af; cursor: not-allowed; }

.field-note { font-size: 0.75rem; color: #6b7280; }

/* VMware VM list */
.vm-list-section h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.vm-list {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 1.25rem;
  max-height: 380px;
  overflow-y: auto;
}

.vm-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
  transition: background 0.15s;
}

.vm-row:last-child { border-bottom: none; }
.vm-row:hover { background: #f9fafb; }
.vm-row.selected { background: #eff6ff; }

.vm-row-radio { flex-shrink: 0; }

.vm-row-info { flex: 1; min-width: 0; }

.vm-row-name {
  font-weight: 600;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.vm-row-meta {
  font-size: 0.8rem;
  color: #6b7280;
  margin-top: 0.2rem;
}

.power-badge {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-weight: 600;
}

.power-badge.on { background: #d1fae5; color: #065f46; }
.power-badge.off { background: #f3f4f6; color: #6b7280; }

/* Info / warning / error / success boxes */
.info-box {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  font-size: 0.875rem;
  margin-bottom: 1.5rem;
}

.info-box ul { margin: 0.5rem 0 0; padding-left: 1.25rem; }

.warning-box {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  font-size: 0.875rem;
  margin-top: 1.5rem;
}

.success-box {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  padding: 1.25rem;
  margin-top: 1.5rem;
}

.error-box {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 1.25rem;
  margin-top: 1.5rem;
}

.code-block {
  background: #1f2937;
  color: #f3f4f6;
  border-radius: 6px;
  padding: 0.75rem 1rem;
  font-size: 0.8rem;
  font-family: monospace;
  margin-top: 0.5rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Progress */
.progress-section { margin-bottom: 1.5rem; }
.progress-section.large { margin-bottom: 0; }

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: 0.5rem;
}

.progress-bar {
  height: 12px;
  background: #e5e7eb;
  border-radius: 999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #3b82f6;
  border-radius: 999px;
  transition: width 0.4s ease;
}

.progress-fill.success { background: #10b981; }
.progress-fill.error { background: #ef4444; }

.status-msg { font-size: 0.875rem; color: #6b7280; margin: 0.75rem 0 0; }
.status-msg.error { color: #dc2626; }

/* Summary */
.summary-box {
  background: #f9fafb;
  border-radius: 8px;
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}

.summary-box h3 { margin: 0 0 0.75rem; font-size: 1rem; }

.summary-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.summary-table td { padding: 0.3rem 0.5rem; }
.summary-table td:first-child { color: #6b7280; width: 40%; }

/* Buttons */
.actions { display: flex; gap: 1rem; margin-top: 0.5rem; }

.btn {
  padding: 0.6rem 1.5rem;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-primary:disabled { background: #93c5fd; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; }
.btn-secondary:hover:not(:disabled) { background: #e5e7eb; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 640px) {
  .form-grid, .form-grid.three-col { grid-template-columns: 1fr; }
  .span-2 { grid-column: span 1; }
  .steps { overflow-x: auto; padding-bottom: 0.5rem; }
  .step-label { display: none; }
}
</style>
