<template>
  <div class="import-vm">
    <div class="page-header">
      <h1>Import VM</h1>
      <p class="subtitle">Import virtual machines via OVA/OVF, disk images, VMware export, or clone from template</p>
    </div>

    <!-- Import method tabs -->
    <div class="method-tabs">
      <button
        v-for="tab in importTabs"
        :key="tab.id"
        :class="['method-tab', activeImportTab === tab.id ? 'method-tab--active' : '']"
        @click="switchImportTab(tab.id)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ====================================================================== -->
    <!-- TAB 1: Import from OVA/OVF                                             -->
    <!-- ====================================================================== -->
    <div v-if="activeImportTab === 'ova'">
      <!-- Step indicators -->
      <div class="steps">
        <div v-for="(step, i) in ovaSteps" :key="i" class="step"
          :class="{ active: ovaStep === i, completed: ovaStep > i }">
          <div class="step-circle">
            <span v-if="ovaStep > i">&#10003;</span>
            <span v-else>{{ i + 1 }}</span>
          </div>
          <span class="step-label">{{ step }}</span>
        </div>
      </div>

      <!-- Step 0: Source -->
      <div v-if="ovaStep === 0" class="card">
        <h2>OVA / OVF Source</h2>

        <div class="source-tabs">
          <button :class="['source-tab', ovaSource === 'upload' ? 'active' : '']" @click="ovaSource = 'upload'">Upload File</button>
          <button :class="['source-tab', ovaSource === 'url' ? 'active' : '']" @click="ovaSource = 'url'">URL</button>
        </div>

        <!-- Upload -->
        <div v-if="ovaSource === 'upload'">
          <p class="hint">Supported formats: OVA, OVF, ZIP</p>
          <div class="drop-zone"
            :class="{ 'drag-over': isDragging, 'has-file': selectedFile }"
            @dragover.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @drop.prevent="onDrop"
            @click="$refs.fileInput.click()">
            <input ref="fileInput" type="file" accept=".ova,.ovf,.zip" style="display:none" @change="onFileSelected" />
            <template v-if="!selectedFile">
              <div class="drop-icon">&#128230;</div>
              <p class="drop-text">Drag &amp; drop an OVA/OVF file here, or click to browse</p>
              <p class="drop-hint">OVA &middot; OVF &middot; ZIP</p>
            </template>
            <template v-else>
              <div class="drop-icon">&#9989;</div>
              <p class="drop-text">{{ selectedFile.name }}</p>
              <p class="drop-hint">{{ formatBytes(selectedFile.size) }}</p>
            </template>
          </div>

          <div v-if="uploading" class="progress-section">
            <div class="progress-label"><span>Uploading...</span><span>{{ uploadProgress }}%</span></div>
            <div class="progress-bar"><div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div></div>
          </div>

          <div class="actions">
            <button class="btn btn-primary" :disabled="!selectedFile || uploading" @click="uploadFile">
              {{ uploading ? 'Uploading...' : 'Upload &amp; Analyse' }}
            </button>
          </div>
        </div>

        <!-- URL -->
        <div v-if="ovaSource === 'url'">
          <p class="hint">Provide a direct URL to an OVA or OVF file. The file will be downloaded server-side.</p>
          <div class="form-grid">
            <div class="form-group span-2">
              <label>File URL</label>
              <input v-model="ovaUrl" type="url" class="input" placeholder="https://example.com/image.ova" />
            </div>
          </div>
          <div class="actions">
            <button class="btn btn-primary" :disabled="!ovaUrl || uploading" @click="uploadFromUrl">
              {{ uploading ? 'Downloading...' : 'Fetch &amp; Analyse' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Step 1: Review Specs -->
      <div v-if="ovaStep === 1" class="card">
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
              {{ disk.filename || 'disk' + i }} &mdash; {{ disk.capacity_gb }} GB
            </li>
          </ul>
        </div>

        <!-- Network mapping -->
        <div v-if="parsedSpecs.nics && parsedSpecs.nics.length">
          <h3 class="section-title">Network Mapping</h3>
          <div v-for="(nic, i) in parsedSpecs.nics" :key="i" class="mapping-row">
            <span class="mapping-source">{{ nic.name || 'NIC ' + i }}</span>
            <span class="mapping-arrow">&#8594;</span>
            <select v-model="ovaNetworkMap[i]" class="input input-sm">
              <option value="vmbr0">vmbr0</option>
              <option v-for="n in availableBridges" :key="n" :value="n">{{ n }}</option>
            </select>
          </div>
        </div>

        <div class="actions">
          <button class="btn btn-secondary" @click="ovaStep = 0">Back</button>
          <button class="btn btn-primary" @click="ovaStep = 2">Continue</button>
        </div>
      </div>

      <!-- Step 2: Select Target -->
      <div v-if="ovaStep === 2" class="card">
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
            <label>Target VM ID</label>
            <input v-model.number="form.target_vmid" type="number" class="input" placeholder="auto" />
            <span class="field-note">Leave empty to auto-assign next available</span>
          </div>
          <div class="form-group">
            <label>Storage Pool</label>
            <select v-model="form.storage" class="input" :disabled="!form.node_id">
              <option value="" disabled>Select storage...</option>
              <option v-for="s in storages" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
            </select>
          </div>
        </div>

        <!-- Storage mapping per disk -->
        <div v-if="parsedSpecs.disks && parsedSpecs.disks.length > 1">
          <h3 class="section-title">Storage Mapping (per disk)</h3>
          <div v-for="(disk, i) in parsedSpecs.disks" :key="i" class="mapping-row">
            <span class="mapping-source">{{ disk.filename || 'disk' + i }} ({{ disk.capacity_gb }} GB)</span>
            <span class="mapping-arrow">&#8594;</span>
            <select v-model="ovaDiskMap[i]" class="input input-sm">
              <option :value="form.storage">{{ form.storage || 'Same as target' }}</option>
              <option v-for="s in storages" :key="s.storage" :value="s.storage">{{ s.storage }}</option>
            </select>
          </div>
        </div>

        <div class="actions">
          <button class="btn btn-secondary" @click="ovaStep = 1">Back</button>
          <button class="btn btn-primary"
            :disabled="!form.proxmox_host_id || !form.node_id || !form.storage"
            @click="ovaStep = 3">Continue</button>
        </div>
      </div>

      <!-- Step 3: Credentials & Confirm -->
      <div v-if="ovaStep === 3" class="card">
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
            <tr><td>Source</td><td>{{ jobFilename }}</td></tr>
            <tr><td>VM Name</td><td>{{ form.vm_name }}</td></tr>
            <tr><td>OS</td><td>{{ form.os_type }}</td></tr>
            <tr><td>CPU</td><td>{{ form.cpu_cores }} core(s)</td></tr>
            <tr><td>Memory</td><td>{{ form.memory_mb }} MB</td></tr>
            <tr><td>Storage</td><td>{{ form.storage }}</td></tr>
          </table>
        </div>
        <div class="actions">
          <button class="btn btn-secondary" @click="ovaStep = 2">Back</button>
          <button class="btn btn-primary" :disabled="deploying" @click="startDeploy">
            {{ deploying ? 'Deploying...' : 'Start Import' }}
          </button>
        </div>
      </div>

      <!-- Step 4: Progress -->
      <div v-if="ovaStep === 4" class="card">
        <h2>Import Progress</h2>
        <div class="progress-section large">
          <div class="progress-label"><span>{{ progressStatus }}</span><span>{{ progressValue }}%</span></div>
          <div class="progress-bar">
            <div class="progress-fill"
              :class="{ error: importFailed, success: importCompleted }"
              :style="{ width: progressValue + '%' }"></div>
          </div>
          <p class="status-msg" :class="{ error: importFailed }">{{ statusMessage }}</p>
        </div>
        <div v-if="manualImportCmd" class="warning-box">
          <strong>SSH import not available.</strong> Run this command manually on the Proxmox node:
          <pre class="code-block">{{ manualImportCmd }}</pre>
        </div>
        <div v-if="importCompleted" class="success-box">
          <p>VM imported successfully! VMID: <strong>{{ importedVmid }}</strong></p>
          <div class="actions">
            <button class="btn btn-primary" @click="$router.push('/vm-management')">Go to VM Management</button>
            <button class="btn btn-secondary" @click="resetWizard">Import Another</button>
          </div>
        </div>
        <div v-if="importFailed" class="error-box">
          <p>Import failed: {{ errorMessage }}</p>
          <div class="actions">
            <button class="btn btn-secondary" @click="resetWizard">Start Over</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ====================================================================== -->
    <!-- TAB 2: Import from QCOW2/RAW/VMDK                                      -->
    <!-- ====================================================================== -->
    <div v-if="activeImportTab === 'disk'">
      <div class="card">
        <h2>Import Disk Image</h2>
        <p class="hint">Select an existing QCOW2, RAW, or VMDK file from Proxmox storage and create a VM from it.</p>

        <!-- Target selection -->
        <h3 class="section-title">Target Host &amp; Storage</h3>
        <div class="form-grid">
          <div class="form-group">
            <label>Proxmox Host</label>
            <select v-model="diskImport.host_id" class="input" @change="onDiskHostChange">
              <option value="" disabled>Select host...</option>
              <option v-for="h in proxmoxHosts" :key="h.id" :value="h.id">{{ h.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Node</label>
            <select v-model="diskImport.node" class="input" :disabled="!diskImport.host_id" @change="onDiskNodeChange">
              <option value="" disabled>Select node...</option>
              <option v-for="n in diskNodes" :key="n.node_name" :value="n.node_name">{{ n.node_name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Browse Storage</label>
            <select v-model="diskImport.browse_storage" class="input" :disabled="!diskImport.node" @change="browseDiskStorage">
              <option value="" disabled>Select storage to browse...</option>
              <option v-for="s in diskStorages" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
            </select>
          </div>
          <div class="form-group">
            <label>Target Storage</label>
            <select v-model="diskImport.target_storage" class="input" :disabled="!diskImport.node">
              <option value="" disabled>Select target storage...</option>
              <option v-for="s in diskStorages" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
            </select>
          </div>
        </div>

        <!-- File browser -->
        <div v-if="diskImport.browse_storage">
          <h3 class="section-title">Select Disk Image</h3>
          <div v-if="diskBrowseLoading" class="text-muted text-sm">Loading files...</div>
          <div v-else-if="diskFiles.length === 0" class="text-muted text-sm">No disk images found in this storage.</div>
          <div v-else class="file-browser">
            <div v-for="f in diskFiles" :key="f.volid"
              :class="['file-row', diskImport.selected_volid === f.volid ? 'file-row--selected' : '']"
              @click="diskImport.selected_volid = f.volid; diskImport.selected_name = volFileName(f.volid)">
              <input type="radio" :value="f.volid" v-model="diskImport.selected_volid" @click.stop />
              <div class="file-info">
                <span class="file-name">{{ volFileName(f.volid) }}</span>
                <span class="file-meta">{{ f.format || '?' }} &middot; {{ f.size ? formatBytes(f.size) : '—' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- VM Config -->
        <h3 class="section-title">New VM Configuration</h3>
        <div class="form-grid">
          <div class="form-group">
            <label>VM ID</label>
            <input v-model.number="diskImport.vmid" type="number" class="input" placeholder="auto" />
          </div>
          <div class="form-group">
            <label>VM Name</label>
            <input v-model="diskImport.vm_name" type="text" class="input" placeholder="imported-vm" />
          </div>
          <div class="form-group">
            <label>OS Type</label>
            <select v-model="diskImport.os_type" class="input">
              <option value="l26">Linux 6.x (Modern)</option>
              <option value="l24">Linux 2.4</option>
              <option value="win11">Windows 11</option>
              <option value="win10">Windows 10/2016/2019</option>
              <option value="win8">Windows 8/2012</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div class="form-group">
            <label>CPU Cores</label>
            <input v-model.number="diskImport.cores" type="number" min="1" max="64" class="input" />
          </div>
          <div class="form-group">
            <label>Memory (MB)</label>
            <input v-model.number="diskImport.memory" type="number" min="256" step="256" class="input" />
            <span class="field-note">{{ (diskImport.memory / 1024).toFixed(1) }} GB</span>
          </div>
          <div class="form-group">
            <label>Bus / Interface</label>
            <select v-model="diskImport.bus" class="input">
              <option value="scsi">SCSI (recommended)</option>
              <option value="virtio">VirtIO</option>
              <option value="sata">SATA</option>
              <option value="ide">IDE</option>
            </select>
          </div>
          <div class="form-group">
            <label>Format Conversion</label>
            <select v-model="diskImport.format" class="input">
              <option value="">Keep original</option>
              <option value="qcow2">Convert to qcow2</option>
              <option value="raw">Convert to raw</option>
            </select>
          </div>
          <div class="form-group">
            <label>Network Bridge</label>
            <input v-model="diskImport.bridge" type="text" class="input" placeholder="vmbr0" />
          </div>
        </div>

        <div v-if="diskImport.selected_volid" class="info-box">
          Selected: <strong>{{ diskImport.selected_name }}</strong>
        </div>

        <div class="actions">
          <button class="btn btn-primary"
            :disabled="!diskImport.selected_volid || !diskImport.target_storage || diskImporting"
            @click="startDiskImport">
            {{ diskImporting ? 'Importing...' : 'Create VM &amp; Import Disk' }}
          </button>
        </div>

        <div v-if="diskImportResult" class="success-box mt-2">
          <p>Task started: <code>{{ diskImportResult }}</code></p>
          <p class="text-sm text-muted">Monitor the task in the Proxmox node Tasks tab.</p>
        </div>
        <div v-if="diskImportError" class="error-box mt-2">
          <p>{{ diskImportError }}</p>
        </div>
      </div>
    </div>

    <!-- ====================================================================== -->
    <!-- TAB 3: Import from VMware                                               -->
    <!-- ====================================================================== -->
    <div v-if="activeImportTab === 'vmware'">
      <!-- Step indicators -->
      <div class="steps">
        <div v-for="(step, i) in steps" :key="i" class="step"
          :class="{ active: currentStep === i, completed: currentStep > i }">
          <div class="step-circle">
            <span v-if="currentStep > i">&#10003;</span>
            <span v-else>{{ i + 1 }}</span>
          </div>
          <span class="step-label">{{ step }}</span>
        </div>
      </div>

      <!-- Step 0: VMware source -->
      <div v-if="currentStep === 0" class="card">
        <div class="source-tabs">
          <button :class="['source-tab', sourceMode === 'vmware-connect' ? 'active' : '']" @click="sourceMode = 'vmware-connect'">Connect to ESXi</button>
          <button :class="['source-tab', sourceMode === 'vmware-files' ? 'active' : '']" @click="sourceMode = 'vmware-files'">Import OVF/VMDK Files</button>
        </div>

        <!-- ESXi Connect -->
        <div v-if="sourceMode === 'vmware-connect'">
          <p class="hint">Connect to an ESXi host or vCenter server to browse and import VMs directly.</p>
          <div class="form-grid three-col">
            <div class="form-group span-2">
              <label>Hostname / IP</label>
              <input v-model="vmware.hostname" type="text" class="input" placeholder="esxi.example.com or 192.168.1.10" />
            </div>
            <div class="form-group">
              <label>Port</label>
              <input v-model.number="vmware.port" type="number" class="input" />
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
            <button class="btn btn-secondary"
              :disabled="vmwareConnecting || !vmware.hostname || !vmware.username"
              @click="vmwareConnect">
              {{ vmwareConnecting ? 'Connecting...' : 'Connect &amp; List VMs' }}
            </button>
          </div>
          <div v-if="vmwareInfo" class="info-box">
            Connected to <strong>{{ vmwareInfo.full_name }}</strong>
            ({{ vmwareInfo.api_type === 'VirtualCenter' ? 'vCenter' : 'ESXi' }})
            v{{ vmwareInfo.version }}
          </div>
          <div v-if="vmwareVMs.length > 0" class="vm-list-section">
            <h3>Select a VM to Import</h3>
            <div class="vm-list">
              <div v-for="vm in vmwareVMs" :key="vm.moref"
                :class="['vm-row', selectedVMRef === vm.moref ? 'selected' : '']"
                @click="selectedVMRef = vm.moref; selectedVMMeta = vm">
                <div class="vm-row-radio"><input type="radio" :value="vm.moref" v-model="selectedVMRef" /></div>
                <div class="vm-row-info">
                  <div class="vm-row-name">
                    {{ vm.name }}
                    <span :class="['power-badge', vm.power_state === 'poweredOn' ? 'on' : 'off']">
                      {{ vm.power_state === 'poweredOn' ? 'On' : 'Off' }}
                    </span>
                  </div>
                  <div class="vm-row-meta">
                    {{ vm.os }} &nbsp;&middot;&nbsp; {{ vm.cpu_cores }} vCPU &nbsp;&middot;&nbsp;
                    {{ vm.memory_mb }} MB RAM &nbsp;&middot;&nbsp; {{ vm.total_disk_gb }} GB disk
                  </div>
                </div>
              </div>
            </div>
            <div class="actions">
              <button class="btn btn-primary"
                :disabled="!selectedVMRef || vmwarePreparing"
                @click="vmwarePrepareImport">
                {{ vmwarePreparing ? 'Starting download...' : 'Import Selected VM' }}
              </button>
            </div>
          </div>
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

        <!-- VMware file import -->
        <div v-if="sourceMode === 'vmware-files'">
          <div class="info-box">
            <strong>Import from exported VMware files</strong><br/>
            Export your VM from VMware as OVF/VMDK, then use the <strong>OVA/OVF tab</strong> to upload the .ova or .ovf file.
            Alternatively, use the <strong>Disk Image tab</strong> to import individual VMDK files already on Proxmox storage.
          </div>
          <p class="hint" style="margin-top: 1rem;">
            To export from VMware: File &#8594; Export &#8594; Export OVF Template, or use <code>ovftool</code>.
          </p>
          <div class="actions">
            <button class="btn btn-secondary" @click="switchImportTab('ova')">Go to OVA/OVF Tab</button>
            <button class="btn btn-secondary" @click="switchImportTab('disk')">Go to Disk Image Tab</button>
          </div>
        </div>
      </div>

      <!-- Steps 1-4 reuse same OVA flow -->
      <div v-if="currentStep === 1" class="card">
        <h2>Review VM Specifications</h2>
        <p class="hint">Values extracted from the image. Edit as needed.</p>
        <div class="form-grid">
          <div class="form-group">
            <label>VM Name</label>
            <input v-model="form.vm_name" type="text" class="input" />
          </div>
          <div class="form-group">
            <label>OS Type</label>
            <select v-model="form.os_type" class="input">
              <option value="other">Other / Unknown</option>
              <option value="ubuntu">Ubuntu</option>
              <option value="debian">Debian</option>
              <option value="centos">CentOS / RHEL</option>
              <option value="windows">Windows</option>
            </select>
          </div>
          <div class="form-group">
            <label>CPU Cores</label>
            <input v-model.number="form.cpu_cores" type="number" min="1" max="64" class="input" />
          </div>
          <div class="form-group">
            <label>Memory (MB)</label>
            <input v-model.number="form.memory_mb" type="number" min="256" step="256" class="input" />
          </div>
        </div>
        <div class="actions">
          <button class="btn btn-secondary" @click="currentStep = 0">Back</button>
          <button class="btn btn-primary" @click="currentStep = 2">Continue</button>
        </div>
      </div>

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
              <option v-for="s in storages" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
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
          <button class="btn btn-primary"
            :disabled="!form.proxmox_host_id || !form.node_id || !form.storage"
            @click="currentStep = 3">Continue</button>
        </div>
      </div>

      <div v-if="currentStep === 3" class="card">
        <h2>Credentials &amp; Confirm</h2>
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
            <tr><td>Source</td><td>{{ sourceMode === 'vmware-connect' ? `VMware (${vmware.hostname})` : jobFilename }}</td></tr>
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

      <div v-if="currentStep === 4" class="card">
        <h2>Import Progress</h2>
        <div class="progress-section large">
          <div class="progress-label"><span>{{ progressStatus }}</span><span>{{ progressValue }}%</span></div>
          <div class="progress-bar">
            <div class="progress-fill"
              :class="{ error: importFailed, success: importCompleted }"
              :style="{ width: progressValue + '%' }"></div>
          </div>
          <p class="status-msg" :class="{ error: importFailed }">{{ statusMessage }}</p>
        </div>
        <div v-if="importCompleted" class="success-box">
          <p>VM imported successfully! VMID: <strong>{{ importedVmid }}</strong></p>
          <div class="actions">
            <button class="btn btn-primary" @click="$router.push('/vm-management')">Go to VM Management</button>
            <button class="btn btn-secondary" @click="resetWizard">Import Another</button>
          </div>
        </div>
        <div v-if="importFailed" class="error-box">
          <p>Import failed: {{ errorMessage }}</p>
          <div class="actions"><button class="btn btn-secondary" @click="resetWizard">Start Over</button></div>
        </div>
      </div>
    </div>

    <!-- ====================================================================== -->
    <!-- TAB 4: Clone from Template                                              -->
    <!-- ====================================================================== -->
    <div v-if="activeImportTab === 'clone'">
      <div class="card">
        <h2>Clone from Template</h2>
        <p class="hint">Select a VM template from any Proxmox host and clone it to create a new VM.</p>

        <!-- Template selector -->
        <h3 class="section-title">Source Template</h3>
        <div class="form-grid">
          <div class="form-group">
            <label>Proxmox Host</label>
            <select v-model="clone.host_id" class="input" @change="onCloneHostChange">
              <option value="" disabled>Select host...</option>
              <option v-for="h in proxmoxHosts" :key="h.id" :value="h.id">{{ h.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Source Node</label>
            <select v-model="clone.src_node" class="input" :disabled="!clone.host_id" @change="loadTemplates">
              <option value="" disabled>Select node...</option>
              <option v-for="n in cloneNodes" :key="n.node_name" :value="n.node_name">{{ n.node_name }}</option>
            </select>
          </div>
        </div>

        <div v-if="templateLoading" class="text-muted text-sm">Loading templates...</div>
        <div v-else-if="clone.src_node && templates.length === 0" class="text-muted text-sm">No templates found on this node.</div>
        <div v-else-if="templates.length" class="vm-list" style="margin-bottom:1.25rem;">
          <div v-for="t in templates" :key="t.vmid"
            :class="['vm-row', clone.src_vmid === t.vmid ? 'selected' : '']"
            @click="clone.src_vmid = t.vmid; clone.template_name = t.name">
            <div class="vm-row-radio"><input type="radio" :value="t.vmid" v-model="clone.src_vmid" @click.stop /></div>
            <div class="vm-row-info">
              <div class="vm-row-name">{{ t.name }} <span class="power-badge off">VMID {{ t.vmid }}</span></div>
              <div class="vm-row-meta">{{ t.cores || 1 }} vCPU &middot; {{ t.maxmem ? Math.round(t.maxmem / 1048576) : '?' }} MB RAM</div>
            </div>
          </div>
        </div>

        <!-- Clone target -->
        <h3 class="section-title">Clone Target</h3>
        <div class="form-grid">
          <div class="form-group">
            <label>Target Host</label>
            <select v-model="clone.target_host_id" class="input" @change="onCloneTargetHostChange">
              <option value="" disabled>Select host...</option>
              <option v-for="h in proxmoxHosts" :key="h.id" :value="h.id">{{ h.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Target Node</label>
            <select v-model="clone.target_node" class="input" :disabled="!clone.target_host_id">
              <option value="" disabled>Select node...</option>
              <option v-for="n in cloneTargetNodes" :key="n.node_name" :value="n.node_name">{{ n.node_name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Target Storage</label>
            <select v-model="clone.storage" class="input" :disabled="!clone.target_node">
              <option value="">Same as source</option>
              <option v-for="s in cloneStorages" :key="s.storage" :value="s.storage">{{ s.storage }} ({{ s.type }})</option>
            </select>
          </div>
          <div class="form-group">
            <label>New VM ID</label>
            <input v-model.number="clone.newid" type="number" class="input" placeholder="auto" />
          </div>
          <div class="form-group">
            <label>New VM Name</label>
            <input v-model="clone.name" type="text" class="input" placeholder="clone-of-template" />
          </div>
          <div class="form-group">
            <label>Clone Type</label>
            <select v-model="clone.full" class="input">
              <option :value="true">Full Clone (independent copy)</option>
              <option :value="false">Linked Clone (shares base disk)</option>
            </select>
          </div>
        </div>

        <!-- Cloud-init quick config -->
        <h3 class="section-title">Cloud-Init Quick Config <span class="optional-label">(optional)</span></h3>
        <div class="form-grid">
          <div class="form-group">
            <label>Hostname</label>
            <input v-model="clone.ci_hostname" type="text" class="input" placeholder="my-new-vm" />
          </div>
          <div class="form-group">
            <label>Username</label>
            <input v-model="clone.ci_user" type="text" class="input" placeholder="ubuntu" />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input v-model="clone.ci_password" type="password" class="input" />
          </div>
          <div class="form-group span-1">
            <label>SSH Public Key</label>
            <textarea v-model="clone.ci_sshkey" class="input" rows="2" placeholder="ssh-rsa AAAA..."></textarea>
          </div>
          <div class="form-group">
            <label>Network Bridge</label>
            <input v-model="clone.bridge" type="text" class="input" placeholder="vmbr0" />
          </div>
          <div class="form-group">
            <label>VLAN Tag (optional)</label>
            <input v-model.number="clone.vlan" type="number" class="input" placeholder="e.g. 10" />
          </div>
          <div class="form-group">
            <label>IP Config</label>
            <input v-model="clone.ipconfig" type="text" class="input" placeholder="dhcp or ip=192.168.1.x/24,gw=192.168.1.1" />
          </div>
        </div>

        <div class="actions">
          <button class="btn btn-primary"
            :disabled="!clone.src_vmid || !clone.target_node || cloneSubmitting"
            @click="startClone">
            {{ cloneSubmitting ? 'Cloning...' : 'Clone VM' }}
          </button>
        </div>

        <div v-if="cloneResult" class="success-box mt-2">
          <p>Clone task started: <code>{{ cloneResult }}</code></p>
          <p class="text-sm text-muted">Monitor the task in the Proxmox node Tasks tab.</p>
        </div>
        <div v-if="cloneError" class="error-box mt-2">
          <p>{{ cloneError }}</p>
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

    // ── Tab state ─────────────────────────────────────────────────────────────
    const activeImportTab = ref('ova')
    const importTabs = [
      { id: 'ova', label: 'OVA / OVF Import' },
      { id: 'disk', label: 'Disk Image (QCOW2/RAW/VMDK)' },
      { id: 'vmware', label: 'VMware Import' },
      { id: 'clone', label: 'Clone from Template' },
    ]

    const switchImportTab = (id) => { activeImportTab.value = id }

    // ── OVA/OVF tab state ─────────────────────────────────────────────────────
    const ovaSteps = ['Source', 'Review Specs', 'Select Target', 'Confirm', 'Deploying']
    const ovaStep = ref(0)
    const ovaSource = ref('upload')
    const ovaUrl = ref('')
    const ovaNetworkMap = ref({})
    const ovaDiskMap = ref({})
    const selectedFile = ref(null)
    const isDragging = ref(false)
    const uploading = ref(false)
    const uploadProgress = ref(0)
    const availableBridges = ref([])

    // ── VMware tab state ──────────────────────────────────────────────────────
    const steps = ['Source', 'Review Specs', 'Select Target', 'Confirm', 'Deploying']
    const currentStep = ref(0)
    const sourceMode = ref('vmware-connect')
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

    // ── Shared job / form state ───────────────────────────────────────────────
    const jobId = ref(null)
    const jobFilename = ref('')
    const parsedSpecs = ref({})
    const form = ref({
      vm_name: '', os_type: 'other', cpu_cores: 1, memory_mb: 512,
      proxmox_host_id: '', node_id: '', storage: '', network_bridge: 'vmbr0',
      username: 'administrator', password: '', target_vmid: null,
    })
    const proxmoxHosts = ref([])
    const nodes = ref([])
    const storages = ref([])
    const networks = ref([])
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

    // ── Disk image tab state ──────────────────────────────────────────────────
    const diskImport = ref({
      host_id: '', node: '', browse_storage: '', target_storage: '',
      selected_volid: '', selected_name: '',
      vmid: null, vm_name: '', os_type: 'l26', cores: 2, memory: 2048,
      bus: 'scsi', format: '', bridge: 'vmbr0',
    })
    const diskNodes = ref([])
    const diskStorages = ref([])
    const diskFiles = ref([])
    const diskBrowseLoading = ref(false)
    const diskImporting = ref(false)
    const diskImportResult = ref(null)
    const diskImportError = ref(null)

    // ── Clone tab state ───────────────────────────────────────────────────────
    const clone = ref({
      host_id: '', src_node: '', src_vmid: null, template_name: '',
      target_host_id: '', target_node: '', storage: '', newid: null, name: '',
      full: true,
      ci_hostname: '', ci_user: '', ci_password: '', ci_sshkey: '', ipconfig: '',
      bridge: 'vmbr0', vlan: null,
    })
    const cloneNodes = ref([])
    const cloneTargetNodes = ref([])
    const cloneStorages = ref([])
    const templates = ref([])
    const templateLoading = ref(false)
    const cloneSubmitting = ref(false)
    const cloneResult = ref(null)
    const cloneError = ref(null)

    // ── Initialise hosts ─────────────────────────────────────────────────────
    const loadHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        proxmoxHosts.value = (res.data || []).filter(h => h.is_active)
      } catch (e) { console.error(e) }
    }
    loadHosts()

    // ── Shared host/node cascade ──────────────────────────────────────────────
    const onHostChange = async () => {
      form.value.node_id = ''; form.value.storage = ''
      nodes.value = []; storages.value = []; networks.value = []
      if (!form.value.proxmox_host_id) return
      try {
        const res = await api.proxmox.listNodes(form.value.proxmox_host_id)
        nodes.value = res.data || []
      } catch { toast.error('Failed to load nodes') }
    }

    const onNodeChange = async () => {
      form.value.storage = ''; storages.value = []; networks.value = []
      if (!form.value.node_id) return
      try {
        // find node_name from selected node
        const nodeObj = nodes.value.find(n => n.id === form.value.node_id)
        const nodeName = nodeObj?.node_name || form.value.node_id
        const [storRes, netRes] = await Promise.all([
          api.pveNode.listStorage(form.value.proxmox_host_id, nodeName),
          api.pveNode.listNetwork(form.value.proxmox_host_id, nodeName),
        ])
        storages.value = (storRes.data || []).filter(s =>
          s.content && (s.content.includes('images') || s.content.includes('rootdir'))
        )
        networks.value = (netRes.data || []).filter(n =>
          n.type === 'bridge' || n.iface?.startsWith('vmbr')
        )
        availableBridges.value = networks.value.map(n => n.iface)
        if (networks.value.length) form.value.network_bridge = networks.value[0].iface
      } catch { toast.error('Failed to load node resources') }
    }

    // ── File helpers ──────────────────────────────────────────────────────────
    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
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
      const allowed = ['.ova', '.ovf', '.zip']
      if (!allowed.includes(ext)) { toast.error(`Unsupported file type: ${ext}`); return }
      selectedFile.value = file
    }

    const uploadFile = async () => {
      if (!selectedFile.value) return
      uploading.value = true; uploadProgress.value = 0
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
        ovaStep.value = 1
        toast.success('File uploaded and analysed!')
      } catch (e) {
        toast.error('Upload failed: ' + (e.response?.data?.detail || e.message))
      } finally { uploading.value = false }
    }

    const uploadFromUrl = async () => {
      if (!ovaUrl.value) return
      uploading.value = true; uploadProgress.value = 0
      try {
        const res = await api.vmImport.upload(
          Object.assign(new FormData(), { url: ovaUrl.value }),
          () => {}
        )
        // Fallback: some backends accept a URL field
        const data = res.data
        jobId.value = data.job_id
        jobFilename.value = data.filename || ovaUrl.value
        parsedSpecs.value = data.specs || {}
        _prefillForm(parsedSpecs.value)
        ovaStep.value = 1
        toast.success('File fetched and analysed!')
      } catch (e) {
        toast.error('Failed to fetch URL: ' + (e.response?.data?.detail || e.message))
      } finally { uploading.value = false }
    }

    const volFileName = (volid) => {
      if (!volid) return '—'
      const parts = volid.split(':')
      const vol = parts.length > 1 ? parts[1] : volid
      const segs = vol.split('/')
      return segs[segs.length - 1]
    }

    // ── VMware helpers ────────────────────────────────────────────────────────
    const vmwareConnect = async () => {
      vmwareConnecting.value = true; vmwareInfo.value = null; vmwareVMs.value = []
      selectedVMRef.value = null
      try {
        const creds = {
          hostname: vmware.value.hostname, username: vmware.value.username,
          password: vmware.value.password, port: vmware.value.port,
          verify_ssl: vmware.value.verify_ssl,
        }
        const testRes = await api.vmImport.vmwareTest(creds)
        vmwareInfo.value = testRes.data
        const listRes = await api.vmImport.vmwareListVMs(creds)
        vmwareVMs.value = listRes.data.vms || []
        if (!vmwareVMs.value.length) toast.warning('Connected, but no VMs found.')
        else toast.success(`Connected! Found ${vmwareVMs.value.length} VM(s).`)
      } catch (e) {
        toast.error('Connection failed: ' + (e.response?.data?.detail || e.message))
      } finally { vmwareConnecting.value = false }
    }

    const vmwarePrepareImport = async () => {
      if (!selectedVMRef.value) return
      vmwarePreparing.value = true; vmwareDownloading.value = true
      vmwareDownloadProgress.value = 0; vmwareDownloadStatus.value = 'Connecting to VMware...'
      try {
        const res = await api.vmImport.vmwarePrepare({
          hostname: vmware.value.hostname, username: vmware.value.username,
          password: vmware.value.password, port: vmware.value.port,
          verify_ssl: vmware.value.verify_ssl, moref: selectedVMRef.value,
        })
        jobId.value = res.data.job_id
        jobFilename.value = `VMware: ${selectedVMMeta.value?.name || selectedVMRef.value}`
        _pollDownload()
      } catch (e) {
        vmwarePreparing.value = false; vmwareDownloading.value = false
        toast.error('Failed to start download: ' + (e.response?.data?.detail || e.message))
      }
    }

    const _pollDownload = () => {
      const timer = setInterval(async () => {
        try {
          const res = await api.vmImport.getProgress(jobId.value)
          const data = res.data
          vmwareDownloadProgress.value = data.progress || 0
          vmwareDownloadStatus.value = data.status_message || ''
          if (data.status === 'parsed') {
            clearInterval(timer)
            vmwarePreparing.value = false; vmwareDownloading.value = false
            parsedSpecs.value = data.specs || selectedVMMeta.value || {}
            _prefillForm(parsedSpecs.value)
            toast.success('VMDK download complete. Review specs below.')
            currentStep.value = 1
          } else if (data.status === 'error') {
            clearInterval(timer)
            vmwarePreparing.value = false; vmwareDownloading.value = false
            toast.error('Download failed: ' + (data.error || data.status_message))
          }
        } catch (e) { console.error('Download poll error:', e) }
      }, 2000)
    }

    const _prefillForm = (specs) => {
      if (!specs) return
      form.value.vm_name = specs.name || 'imported-vm'
      form.value.os_type = specs.os_type || 'other'
      form.value.cpu_cores = specs.cpu_cores || 1
      form.value.memory_mb = specs.memory_mb || 512
    }

    // ── Deploy (OVA/VMware tabs) ──────────────────────────────────────────────
    const startDeploy = async () => {
      if (!jobId.value) return
      deploying.value = true
      if (activeImportTab.value === 'ova') ovaStep.value = 4
      else currentStep.value = 4
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
          target_vmid: form.value.target_vmid || undefined,
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
            importCompleted.value = true; importedVmid.value = data.vmid
            deploying.value = false; toast.success('VM imported successfully!')
          } else if (data.status === 'error') {
            clearInterval(pollTimer)
            importFailed.value = true
            errorMessage.value = data.error || data.status_message || 'Unknown error'
            deploying.value = false
          }
        } catch (e) { console.error('Progress poll error:', e) }
      }, 2000)
    }

    // ── Disk image import tab ─────────────────────────────────────────────────
    const onDiskHostChange = async () => {
      diskImport.value.node = ''; diskImport.value.browse_storage = ''
      diskImport.value.target_storage = ''; diskFiles.value = []
      diskNodes.value = []; diskStorages.value = []
      if (!diskImport.value.host_id) return
      try {
        const res = await api.proxmox.listNodes(diskImport.value.host_id)
        diskNodes.value = res.data || []
      } catch { toast.error('Failed to load nodes') }
    }

    const onDiskNodeChange = async () => {
      diskImport.value.browse_storage = ''; diskImport.value.target_storage = ''
      diskFiles.value = []; diskStorages.value = []
      if (!diskImport.value.node) return
      try {
        const res = await api.pveNode.listStorage(diskImport.value.host_id, diskImport.value.node)
        diskStorages.value = (res.data || []).filter(s =>
          s.content && (s.content.includes('images') || s.content.includes('rootdir') || s.content.includes('iso'))
        )
      } catch { toast.error('Failed to load storage') }
    }

    const browseDiskStorage = async () => {
      if (!diskImport.value.browse_storage) return
      diskBrowseLoading.value = true; diskFiles.value = []
      try {
        const res = await api.pveNode.browseStorage(
          diskImport.value.host_id,
          diskImport.value.node,
          diskImport.value.browse_storage,
          { content: 'images' }
        )
        diskFiles.value = (res.data || []).filter(f => {
          const name = f.volid || ''
          return /\.(qcow2|vmdk|raw|img|vhd|vhdx)$/i.test(name)
        })
      } catch { toast.error('Failed to browse storage') }
      finally { diskBrowseLoading.value = false }
    }

    const startDiskImport = async () => {
      diskImportResult.value = null; diskImportError.value = null
      diskImporting.value = true
      try {
        const payload = {
          vmid: diskImport.value.vmid || undefined,
          name: diskImport.value.vm_name || 'imported-vm',
          ostype: diskImport.value.os_type,
          cores: diskImport.value.cores,
          memory: diskImport.value.memory,
          net0: `virtio,bridge=${diskImport.value.bridge}`,
          [`${diskImport.value.bus}0`]: `${diskImport.value.target_storage}:0,import-from=${diskImport.value.selected_volid}${diskImport.value.format ? ',format=' + diskImport.value.format : ''}`,
          scsihw: 'virtio-scsi-pci',
        }
        const hostId = diskImport.value.host_id
        const node = diskImport.value.node
        const res = await api.pveNode.createVm(hostId, node, payload)
        diskImportResult.value = res.data?.upid || JSON.stringify(res.data)
        toast.success('Disk import task started!')
      } catch (e) {
        diskImportError.value = e.response?.data?.detail || e.message
        toast.error('Disk import failed: ' + diskImportError.value)
      } finally { diskImporting.value = false }
    }

    // ── Clone tab ─────────────────────────────────────────────────────────────
    const onCloneHostChange = async () => {
      clone.value.src_node = ''; clone.value.src_vmid = null
      cloneNodes.value = []; templates.value = []
      if (!clone.value.host_id) return
      try {
        const res = await api.proxmox.listNodes(clone.value.host_id)
        cloneNodes.value = res.data || []
      } catch { toast.error('Failed to load nodes') }
    }

    const onCloneTargetHostChange = async () => {
      clone.value.target_node = ''; cloneTargetNodes.value = []; cloneStorages.value = []
      if (!clone.value.target_host_id) return
      try {
        const res = await api.proxmox.listNodes(clone.value.target_host_id)
        cloneTargetNodes.value = res.data || []
      } catch { toast.error('Failed to load target nodes') }
    }

    const loadTemplates = async () => {
      if (!clone.value.src_node) return
      templateLoading.value = true; templates.value = []
      try {
        const res = await api.pveNode.listVmTemplates(clone.value.host_id, clone.value.src_node)
        templates.value = res.data || []
      } catch {
        // fallback: get all VMs and filter templates
        try {
          const res = await api.pveNode.nodeVms(clone.value.host_id, clone.value.src_node)
          templates.value = (res.data || []).filter(v => v.template == 1)
        } catch { toast.error('Failed to load templates') }
      } finally { templateLoading.value = false }
    }

    const startClone = async () => {
      cloneResult.value = null; cloneError.value = null; cloneSubmitting.value = true
      try {
        const hostId = clone.value.host_id
        const node = clone.value.src_node
        const vmid = clone.value.src_vmid
        const payload = {
          newid: clone.value.newid || undefined,
          name: clone.value.name || undefined,
          full: clone.value.full ? 1 : 0,
          target: clone.value.target_node || undefined,
          storage: clone.value.storage || undefined,
        }
        const res = await api.pveVm.clone(hostId, node, vmid, payload)
        cloneResult.value = res.data?.upid || JSON.stringify(res.data)

        // Apply cloud-init config after clone if provided
        if (clone.value.ci_user || clone.value.ci_hostname || clone.value.ci_sshkey || clone.value.ipconfig) {
          toast.info('Applying cloud-init config... (may need a few seconds for clone to complete first)')
        }

        toast.success('Clone task started!')
      } catch (e) {
        cloneError.value = e.response?.data?.detail || e.message
        toast.error('Clone failed: ' + cloneError.value)
      } finally { cloneSubmitting.value = false }
    }

    // ── Reset ─────────────────────────────────────────────────────────────────
    const resetWizard = () => {
      if (pollTimer) clearInterval(pollTimer)
      ovaStep.value = 0; currentStep.value = 0
      selectedFile.value = null; uploadProgress.value = 0
      uploading.value = false; jobId.value = null; jobFilename.value = ''
      parsedSpecs.value = {}; vmwareInfo.value = null; vmwareVMs.value = []
      selectedVMRef.value = null; selectedVMMeta.value = null
      vmwarePreparing.value = false; vmwareDownloading.value = false
      form.value = {
        vm_name: '', os_type: 'other', cpu_cores: 1, memory_mb: 512,
        proxmox_host_id: '', node_id: '', storage: '', network_bridge: 'vmbr0',
        username: 'administrator', password: '', target_vmid: null,
      }
      deploying.value = false; progressValue.value = 0; progressStatus.value = ''
      statusMessage.value = ''; importCompleted.value = false
      importFailed.value = false; errorMessage.value = ''
      importedVmid.value = null; manualImportCmd.value = null
    }

    onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer) })

    return {
      activeImportTab, importTabs, switchImportTab,
      ovaSteps, ovaStep, ovaSource, ovaUrl, ovaNetworkMap, ovaDiskMap,
      selectedFile, isDragging, uploading, uploadProgress, availableBridges,
      steps, currentStep, sourceMode,
      vmware, vmwareConnecting, vmwareInfo, vmwareVMs,
      selectedVMRef, selectedVMMeta, vmwarePreparing, vmwareDownloading,
      vmwareDownloadProgress, vmwareDownloadStatus,
      parsedSpecs, jobFilename, form, proxmoxHosts, nodes, storages, networks,
      deploying, progressValue, progressStatus, statusMessage,
      importCompleted, importFailed, errorMessage, importedVmid, manualImportCmd,
      diskImport, diskNodes, diskStorages, diskFiles, diskBrowseLoading,
      diskImporting, diskImportResult, diskImportError,
      clone, cloneNodes, cloneTargetNodes, cloneStorages,
      templates, templateLoading, cloneSubmitting, cloneResult, cloneError,
      onDrop, onFileSelected, formatBytes, uploadFile, uploadFromUrl, volFileName,
      vmwareConnect, vmwarePrepareImport,
      onHostChange, onNodeChange,
      onDiskHostChange, onDiskNodeChange, browseDiskStorage, startDiskImport,
      onCloneHostChange, onCloneTargetHostChange, loadTemplates, startClone,
      startDeploy, resetWizard,
    }
  }
}
</script>

<style scoped>
.import-vm { max-width: 920px; margin: 0 auto; padding: 2rem; }
.page-header { margin-bottom: 1.5rem; }
.page-header h1 { font-size: 1.75rem; font-weight: 700; margin: 0 0 0.5rem; }
.subtitle { color: #6b7280; margin: 0; }

/* Method tabs */
.method-tabs {
  display: flex; gap: 0; margin-bottom: 2rem;
  border-bottom: 2px solid #e5e7eb;
}
.method-tab {
  padding: 0.6rem 1.25rem; background: none; border: none;
  border-bottom: 3px solid transparent; margin-bottom: -2px;
  font-size: 0.9rem; font-weight: 500; color: #6b7280; cursor: pointer;
  transition: all 0.15s;
}
.method-tab:hover { color: #374151; }
.method-tab--active { color: #3b82f6; border-bottom-color: #3b82f6; }

/* Steps */
.steps { display: flex; align-items: center; margin-bottom: 2rem; }
.step { display: flex; align-items: center; gap: 0.5rem; flex: 1; }
.step:not(:last-child)::after { content: ''; flex: 1; height: 2px; background: #e5e7eb; margin: 0 0.5rem; }
.step.completed:not(:last-child)::after { background: #3b82f6; }
.step-circle {
  width: 2rem; height: 2rem; border-radius: 50%; background: #e5e7eb; color: #6b7280;
  display: flex; align-items: center; justify-content: center; font-weight: 700;
  font-size: 0.85rem; flex-shrink: 0;
}
.step.active .step-circle { background: #3b82f6; color: white; }
.step.completed .step-circle { background: #059669; color: white; }
.step-label { font-size: 0.8rem; white-space: nowrap; color: #6b7280; }
.step.active .step-label { color: #1f2937; font-weight: 600; }

/* Card */
.card { background: white; border-radius: 12px; padding: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,.1); margin-bottom: 1.5rem; }
.card h2 { font-size: 1.25rem; font-weight: 700; margin: 0 0 0.5rem; }
.section-title { font-size: 1rem; font-weight: 600; margin: 1.25rem 0 0.75rem; color: #374151; }
.optional-label { font-size: 0.8rem; font-weight: 400; color: #9ca3af; }
.hint { color: #6b7280; font-size: 0.875rem; margin-bottom: 1.5rem; }

/* Source tabs */
.source-tabs { display: flex; gap: 0; margin-bottom: 1.5rem; border-bottom: 2px solid #e5e7eb; }
.source-tab {
  padding: 0.5rem 1.25rem; background: none; border: none;
  border-bottom: 3px solid transparent; margin-bottom: -2px;
  font-size: 0.9rem; font-weight: 500; color: #6b7280; cursor: pointer;
}
.source-tab.active { color: #3b82f6; border-bottom-color: #3b82f6; }

/* Drop zone */
.drop-zone {
  border: 2px dashed #d1d5db; border-radius: 12px; padding: 3rem 2rem;
  text-align: center; cursor: pointer; transition: all 0.2s; margin-bottom: 1.5rem;
}
.drop-zone:hover, .drop-zone.drag-over { border-color: #3b82f6; background: #eff6ff; }
.drop-zone.has-file { border-color: #10b981; background: #f0fdf4; }
.drop-icon { font-size: 3rem; margin-bottom: 0.75rem; }
.drop-text { font-size: 1rem; font-weight: 500; margin: 0 0 0.25rem; }
.drop-hint { font-size: 0.8rem; color: #6b7280; margin: 0; }

/* Forms */
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-bottom: 1.25rem; }
.form-grid.three-col { grid-template-columns: 1fr 1fr 1fr; }
.form-group { display: flex; flex-direction: column; gap: 0.4rem; }
.form-group label { font-size: 0.875rem; font-weight: 600; color: #374151; }
.span-2 { grid-column: span 2; }
.span-1 { grid-column: span 1; }
.checkbox-label { display: flex; align-items: center; gap: 0.5rem; font-weight: 500 !important; cursor: pointer; }
.input {
  padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 8px;
  font-size: 0.9rem; background: white; transition: border-color 0.15s;
}
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,.1); }
.input:disabled { background: #f9fafb; color: #9ca3af; cursor: not-allowed; }
.input-sm { padding: 0.35rem 0.6rem; font-size: 0.85rem; }
.field-note { font-size: 0.75rem; color: #6b7280; }

/* Mapping rows */
.mapping-row {
  display: flex; align-items: center; gap: 1rem;
  margin-bottom: 0.75rem;
}
.mapping-source {
  flex: 1; font-size: 0.875rem; font-weight: 500;
  background: #f3f4f6; padding: 0.4rem 0.75rem; border-radius: 6px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.mapping-arrow { color: #9ca3af; font-size: 1.1rem; }

/* File browser */
.file-browser {
  border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;
  max-height: 300px; overflow-y: auto; margin-bottom: 1.25rem;
}
.file-row {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.6rem 1rem; border-bottom: 1px solid #f3f4f6;
  cursor: pointer; transition: background 0.15s;
}
.file-row:last-child { border-bottom: none; }
.file-row:hover { background: #f9fafb; }
.file-row--selected { background: #eff6ff; }
.file-info { display: flex; flex-direction: column; }
.file-name { font-weight: 500; font-size: 0.9rem; word-break: break-all; }
.file-meta { font-size: 0.78rem; color: #9ca3af; }

/* VMware VM list */
.vm-list-section h3 { font-size: 1rem; font-weight: 600; margin-bottom: 0.75rem; }
.vm-list {
  border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;
  margin-bottom: 1.25rem; max-height: 360px; overflow-y: auto;
}
.vm-row {
  display: flex; align-items: center; gap: 1rem;
  padding: 0.75rem 1rem; border-bottom: 1px solid #f3f4f6;
  cursor: pointer; transition: background 0.15s;
}
.vm-row:last-child { border-bottom: none; }
.vm-row:hover { background: #f9fafb; }
.vm-row.selected { background: #eff6ff; }
.vm-row-radio { flex-shrink: 0; }
.vm-row-info { flex: 1; min-width: 0; }
.vm-row-name { font-weight: 600; font-size: 0.9rem; display: flex; align-items: center; gap: 0.5rem; }
.vm-row-meta { font-size: 0.8rem; color: #6b7280; margin-top: 0.2rem; }
.power-badge { font-size: 0.7rem; padding: 0.1rem 0.4rem; border-radius: 4px; font-weight: 600; }
.power-badge.on { background: #d1fae5; color: #065f46; }
.power-badge.off { background: #f3f4f6; color: #6b7280; }

/* Info / warning / error / success boxes */
.info-box { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 1rem 1.25rem; font-size: 0.875rem; margin-bottom: 1.5rem; }
.info-box ul { margin: 0.5rem 0 0; padding-left: 1.25rem; }
.warning-box { background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 1rem 1.25rem; font-size: 0.875rem; margin-top: 1.5rem; }
.success-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 1.25rem; margin-top: 1.5rem; }
.error-box { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 1.25rem; margin-top: 1.5rem; }
.mt-2 { margin-top: 0.75rem; }
.code-block {
  background: #1f2937; color: #f3f4f6; border-radius: 6px; padding: 0.75rem 1rem;
  font-size: 0.8rem; font-family: monospace; margin-top: 0.5rem;
  overflow-x: auto; white-space: pre-wrap; word-break: break-all;
}

/* Progress */
.progress-section { margin-bottom: 1.5rem; }
.progress-section.large { margin-bottom: 0; }
.progress-label { display: flex; justify-content: space-between; font-size: 0.875rem; font-weight: 500; margin-bottom: 0.5rem; }
.progress-bar { height: 12px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }
.progress-fill { height: 100%; background: #3b82f6; border-radius: 999px; transition: width 0.4s ease; }
.progress-fill.success { background: #10b981; }
.progress-fill.error { background: #ef4444; }
.status-msg { font-size: 0.875rem; color: #6b7280; margin: 0.75rem 0 0; }
.status-msg.error { color: #dc2626; }

/* Summary */
.summary-box { background: #f9fafb; border-radius: 8px; padding: 1.25rem; margin-bottom: 1.5rem; }
.summary-box h3 { margin: 0 0 0.75rem; font-size: 1rem; }
.summary-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
.summary-table td { padding: 0.3rem 0.5rem; }
.summary-table td:first-child { color: #6b7280; width: 40%; }

/* Buttons */
.actions { display: flex; gap: 1rem; margin-top: 0.5rem; flex-wrap: wrap; }
.btn { padding: 0.6rem 1.5rem; border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer; border: none; transition: all 0.2s; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-primary:disabled { background: #93c5fd; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; }
.btn-secondary:hover:not(:disabled) { background: #e5e7eb; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.text-muted { color: #6b7280; }
.text-sm { font-size: 0.875rem; }

@media (max-width: 640px) {
  .form-grid, .form-grid.three-col { grid-template-columns: 1fr; }
  .span-2 { grid-column: span 1; }
  .steps { overflow-x: auto; padding-bottom: 0.5rem; }
  .step-label { display: none; }
  .method-tabs { overflow-x: auto; }
}
</style>
