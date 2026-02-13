<template>
  <div class="create-vm-page">
    <div class="card">
      <div class="card-header">
        <h3>Create Virtual Machine</h3>
      </div>

      <form @submit.prevent="createVM" class="create-vm-form">
        <!-- Basic Information -->
        <div class="form-section">
          <h4 class="section-title">Basic Information</h4>

          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">VM Name *</label>
              <input v-model="formData.name" class="form-control" required />
            </div>

            <div class="form-group">
              <label class="form-label">Hostname *</label>
              <input v-model="formData.hostname" class="form-control" required />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">Operating System *</label>
              <select v-model="formData.os_type" class="form-control" required>
                <option value="">Select OS</option>
                <optgroup label="Linux Server">
                  <option value="ubuntu">Ubuntu</option>
                  <option value="debian">Debian</option>
                  <option value="centos">CentOS</option>
                  <option value="rocky">Rocky Linux</option>
                  <option value="alma">AlmaLinux</option>
                </optgroup>
                <optgroup label="Windows">
                  <option value="windows_server_2016">Windows Server 2016</option>
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

            <div class="form-group">
              <label class="form-label">Installation Method *</label>
              <div class="radio-group" style="display: flex; gap: 1rem; margin-bottom: 0.5rem;">
                <label class="radio-label">
                  <input type="radio" v-model="imageSource" value="iso" />
                  <span>ISO Image</span>
                </label>
                <label class="radio-label">
                  <input type="radio" v-model="imageSource" value="cloud_image" />
                  <span>Cloud Image (Fast)</span>
                </label>
              </div>

              <!-- ISO Selection -->
              <select v-if="imageSource === 'iso'" v-model="formData.iso_id" class="form-control">
                <option :value="null">No ISO (cloud-init only)</option>
                <option v-for="iso in isos" :key="iso.id" :value="iso.id">
                  {{ iso.name }} ({{ iso.version }})
                </option>
              </select>

              <!-- Cloud Image Selection -->
              <select v-if="imageSource === 'cloud_image'" v-model="formData.cloud_image_id" class="form-control" required>
                <option :value="null">Select Cloud Image</option>
                <option v-for="image in cloudImages" :key="image.id" :value="image.id">
                  {{ image.name }} {{ image.version ? '(' + image.version + ')' : '' }}
                  <span v-if="!image.is_downloaded"> - Not Downloaded</span>
                </option>
              </select>
            </div>
          </div>
        </div>

        <!-- Proxmox Configuration -->
        <div class="form-section">
          <h4 class="section-title">Datacenter & Node Selection</h4>

          <div class="datacenter-selector">
            <div class="form-group">
              <label class="form-label">Select Proxmox Datacenter *</label>
              <div class="datacenter-cards">
                <div
                  v-for="host in hosts"
                  :key="host.id"
                  :class="['datacenter-card', { 'selected': selectedHostId === host.id }]"
                  @click="selectDatacenter(host.id)"
                >
                  <div class="datacenter-icon">🏢</div>
                  <div class="datacenter-info">
                    <h5>{{ host.name }}</h5>
                    <p class="text-xs">{{ host.hostname }}:{{ host.port }}</p>
                    <span :class="['badge', host.is_active ? 'badge-success' : 'badge-danger']">
                      {{ host.is_active ? 'Active' : 'Inactive' }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="selectedHostId && nodes.length > 0" class="form-group">
              <label class="form-label">Select Node *</label>
              <div class="node-cards">
                <div
                  v-for="node in nodes"
                  :key="node.id"
                  :class="['node-card', { 'selected': formData.node_id === node.id }]"
                  @click="selectNode(node.id)"
                >
                  <div class="node-header">
                    <h6>{{ node.node_name }}</h6>
                    <span :class="['badge', 'badge-sm', node.status === 'online' ? 'badge-success' : 'badge-danger']">
                      {{ node.status }}
                    </span>
                  </div>
                  <div class="node-resources">
                    <div class="resource-item">
                      <span class="resource-icon">🖥️</span>
                      <span>{{ node.cpu_cores }} cores ({{ node.cpu_usage }}%)</span>
                    </div>
                    <div class="resource-item">
                      <span class="resource-icon">💾</span>
                      <span>{{ formatBytes(node.memory_total) }} RAM</span>
                    </div>
                    <div class="resource-item">
                      <span class="resource-icon">💿</span>
                      <span>{{ formatBytes(node.disk_total) }} Disk</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="selectedHostId && loadingNodes" class="loading-message">
              <div class="loading-spinner"></div>
              <p>Loading nodes...</p>
            </div>
          </div>
        </div>

        <!-- Storage Configuration -->
        <div v-if="formData.node_id" class="form-section">
          <h4 class="section-title">Storage Configuration</h4>

          <div v-if="loadingStorage" class="loading-message">
            <div class="loading-spinner"></div>
            <p>Loading storage pools...</p>
          </div>

          <div v-else-if="storageList.length === 0" class="text-muted text-center">
            <p>No storage pools available</p>
          </div>

          <div v-else class="form-group">
            <label class="form-label">Storage Pool *</label>
            <div class="storage-cards">
              <div
                v-for="storage in sortedStorageList"
                :key="storage.storage"
                :class="['storage-card', { 'selected': selectedStorage === storage.storage, 'disabled': !storage.enabled || !storage.active }]"
                @click="selectStorage(storage.storage)"
              >
                <div class="storage-header">
                  <h6>{{ storage.storage }}</h6>
                  <span class="badge badge-sm badge-info">{{ storage.type }}</span>
                </div>
                <div class="storage-info">
                  <div class="storage-bar">
                    <div class="storage-bar-fill" :style="{ width: getStorageUsagePercent(storage) + '%' }"></div>
                  </div>
                  <div class="storage-stats">
                    <span>{{ formatBytes(storage.available) }} free</span>
                    <span>{{ formatBytes(storage.total) }} total</span>
                  </div>
                </div>
                <div v-if="storage.shared" class="storage-badge">
                  <span class="badge badge-success">Shared</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ISO Storage Configuration -->
        <div v-if="formData.node_id" class="form-section">
          <h4 class="section-title">ISO Storage</h4>
          <p class="section-description">Select where installation media (ISO files) will be stored</p>

          <div v-if="loadingStorage" class="loading-message">
            <div class="loading-spinner"></div>
            <p>Loading storage pools...</p>
          </div>

          <div v-else-if="storageList.length === 0" class="text-muted text-center">
            <p>No storage pools available</p>
          </div>

          <div v-else class="form-group">
            <label class="form-label">ISO Storage Pool *</label>
            <div class="storage-cards">
              <div
                v-for="storage in sortedISOStorageList"
                :key="'iso-' + storage.storage"
                :class="['storage-card', { 'selected': formData.iso_storage === storage.storage, 'disabled': !storage.enabled || !storage.active }]"
                @click="formData.iso_storage = storage.storage"
              >
                <div class="storage-header">
                  <h6>{{ storage.storage }}</h6>
                  <span class="badge badge-sm badge-info">{{ storage.type }}</span>
                </div>
                <div class="storage-info">
                  <div class="storage-bar">
                    <div class="storage-bar-fill" :style="{ width: getStorageUsagePercent(storage) + '%' }"></div>
                  </div>
                  <div class="storage-stats">
                    <span>{{ formatBytes(storage.used) }} / {{ formatBytes(storage.total) }}</span>
                    <span>{{ getStorageUsagePercent(storage) }}% used</span>
                  </div>
                </div>
                <div v-if="storage.shared" class="storage-badge">
                  <span class="badge badge-success">Shared</span>
                </div>
              </div>
            </div>
            <p class="help-text">Only showing storage pools that support ISO content</p>
          </div>
        </div>

        <!-- Network Configuration -->
        <div v-if="formData.node_id" class="form-section">
          <h4 class="section-title">Network Configuration</h4>

          <div v-if="loadingNetwork" class="loading-message">
            <div class="loading-spinner"></div>
            <p>Loading network interfaces...</p>
          </div>

          <div v-else-if="networkList.length === 0" class="text-muted text-center">
            <p>No network bridges available</p>
          </div>

          <div v-else>
            <div class="form-group">
              <label class="form-label">Network Bridge *</label>
              <div class="network-cards">
                <div
                  v-for="net in sortedNetworkList"
                  :key="net.iface"
                  :class="['network-card', { 'selected': selectedBridge === net.iface, 'disabled': !net.active }]"
                  @click="selectBridge(net.iface)"
                >
                  <div class="network-header">
                    <h6>{{ net.iface }}</h6>
                    <span :class="['badge', 'badge-sm', net.active ? 'badge-success' : 'badge-danger']">
                      {{ net.active ? 'Active' : 'Inactive' }}
                    </span>
                  </div>
                  <div class="network-info">
                    <div v-if="net.address" class="text-xs">
                      <strong>IP:</strong> {{ net.address }}{{ net.netmask ? '/' + net.netmask : '' }}
                    </div>
                    <div v-if="net.gateway" class="text-xs">
                      <strong>Gateway:</strong> {{ net.gateway }}
                    </div>
                    <div v-if="net.bridge_ports" class="text-xs">
                      <strong>Ports:</strong> {{ net.bridge_ports }}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">VLAN Tag (optional)</label>
              <input v-model.number="vlanTag" type="number" min="1" max="4094" class="form-control" placeholder="Leave empty for no VLAN" />
              <p class="text-xs text-muted">Enter VLAN ID (1-4094) or leave empty for untagged</p>
            </div>
          </div>
        </div>

        <!-- Resource Allocation -->
        <div class="form-section">
          <h4 class="section-title">Resource Allocation</h4>

          <div class="grid grid-cols-4 gap-2">
            <div class="form-group">
              <label class="form-label">CPU Sockets *</label>
              <input v-model.number="formData.cpu_sockets" type="number" min="1" max="8" class="form-control" required />
            </div>

            <div class="form-group">
              <label class="form-label">CPU Cores *</label>
              <input v-model.number="formData.cpu_cores" type="number" min="1" max="64" class="form-control" required />
            </div>

            <div class="form-group">
              <label class="form-label">Memory (MB) *</label>
              <input v-model.number="formData.memory" type="number" min="512" step="512" class="form-control" required />
            </div>

            <div class="form-group">
              <label class="form-label">Disk Size (GB) *</label>
              <input v-model.number="formData.disk_size" type="number" min="10" class="form-control" required />
            </div>
          </div>
        </div>

        <!-- Advanced Hardware Options -->
        <div class="form-section">
          <h4 class="section-title collapsible-header" @click="showAdvancedHardware = !showAdvancedHardware">
            <span class="toggle-icon">{{ showAdvancedHardware ? '▼' : '▶' }}</span>
            Advanced Hardware Options
          </h4>

          <div v-show="showAdvancedHardware" class="collapsible-content">

          <div class="grid grid-cols-3 gap-2">
            <div class="form-group">
              <label class="form-label">CPU Type</label>
              <select v-model="formData.cpu_type" class="form-control">
                <option value="x86-64-v2-AES">x86-64-v2-AES (Default)</option>
                <option value="host">Host (Passthrough)</option>
                <option value="qemu64">QEMU64</option>
                <option value="kvm64">KVM64</option>
                <option value="x86-64-v2">x86-64-v2</option>
                <option value="x86-64-v3">x86-64-v3</option>
                <option value="x86-64-v4">x86-64-v4</option>
                <option value="max">Max (All features)</option>
                <option value="Broadwell">Intel Broadwell</option>
                <option value="Broadwell-noTSX">Intel Broadwell-noTSX</option>
                <option value="Cascadelake-Server">Intel Cascadelake Server</option>
                <option value="Cascadelake-Server-noTSX">Intel Cascadelake Server-noTSX</option>
                <option value="Haswell">Intel Haswell</option>
                <option value="Haswell-noTSX">Intel Haswell-noTSX</option>
                <option value="IvyBridge">Intel IvyBridge</option>
                <option value="SandyBridge">Intel SandyBridge</option>
                <option value="Skylake-Client">Intel Skylake Client</option>
                <option value="Skylake-Server">Intel Skylake Server</option>
                <option value="Westmere">Intel Westmere</option>
                <option value="EPYC">AMD EPYC</option>
                <option value="EPYC-Rome">AMD EPYC Rome</option>
                <option value="EPYC-Milan">AMD EPYC Milan</option>
                <option value="Opteron_G5">AMD Opteron G5</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">BIOS Type</label>
              <select v-model="formData.bios_type" class="form-control">
                <option value="seabios">SeaBIOS (Legacy)</option>
                <option value="ovmf">OVMF (UEFI)</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">VGA Type</label>
              <select v-model="formData.vga_type" class="form-control">
                <option value="std">Standard VGA</option>
                <option value="virtio">VirtIO-GPU</option>
                <option value="qxl">QXL (SPICE)</option>
                <option value="vmware">VMware compatible</option>
                <option value="cirrus">Cirrus Logic</option>
              </select>
            </div>
          </div>

          <div class="grid grid-cols-3 gap-2">
            <div class="form-group">
              <label class="form-label">Machine Type</label>
              <select v-model="formData.machine_type" class="form-control">
                <option value="pc">PC (i440FX)</option>
                <option value="q35">Q35 (PCIe)</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Boot Order</label>
              <select v-model="formData.boot_order" class="form-control">
                <option value="cdn">Disk, CD-ROM, Network</option>
                <option value="dcn">CD-ROM, Disk, Network</option>
                <option value="ncd">Network, Disk, CD-ROM</option>
                <option value="c">Disk only</option>
                <option value="d">CD-ROM only</option>
                <option value="n">Network only</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">
                <input v-model="formData.numa_enabled" type="checkbox" style="margin-right: 8px;" />
                Enable NUMA
              </label>
              <div class="form-text">Enable Non-Uniform Memory Access</div>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">CPU Flags (optional)</label>
            <input v-model="formData.cpu_flags" type="text" class="form-control" placeholder="e.g., +aes,+ssse3" />
            <small class="form-help">Additional CPU flags (comma-separated)</small>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">CPU Limit (optional)</label>
              <input v-model.number="formData.cpu_limit" type="number" min="0" max="128" class="form-control" placeholder="0 = unlimited" />
              <small class="form-help">Limit CPU usage (0-128, 0 = unlimited)</small>
            </div>

            <div class="form-group">
              <label class="form-label">CPU Units</label>
              <input v-model.number="formData.cpu_units" type="number" min="8" max="500000" class="form-control" />
              <small class="form-help">CPU scheduler weight (default: 1024)</small>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">Memory Balloon (MB, optional)</label>
              <input v-model.number="formData.balloon" type="number" min="0" class="form-control" placeholder="0 = disabled" />
              <small class="form-help">Dynamic memory allocation (0 = disabled)</small>
            </div>

            <div class="form-group">
              <label class="form-label">Memory Shares (optional)</label>
              <input v-model.number="formData.shares" type="number" min="0" max="50000" class="form-control" placeholder="Default" />
              <small class="form-help">Memory scheduler weight</small>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">SCSI Controller</label>
              <select v-model="formData.scsihw" class="form-control">
                <option value="virtio-scsi-pci">VirtIO SCSI (Default)</option>
                <option value="virtio-scsi-single">VirtIO SCSI Single</option>
                <option value="lsi">LSI 53C895A</option>
                <option value="lsi53c810">LSI 53C810</option>
                <option value="megasas">MegaRAID SAS 8708EM2</option>
                <option value="pvscsi">VMware PVSCSI</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="formData.tablet" style="margin-right: 8px;">
                Enable Tablet Pointer Device
              </label>
              <div class="form-text">Improves mouse tracking in VNC/SPICE</div>
            </div>
          </div>
          </div>
        </div>

        <!-- Boot & Startup Options -->
        <div class="form-section">
          <h4 class="section-title collapsible-header" @click="showBootStartup = !showBootStartup">
            <span class="toggle-icon">{{ showBootStartup ? '▼' : '▶' }}</span>
            Boot & Startup Options
          </h4>

          <div v-show="showBootStartup" class="collapsible-content">
          <div class="form-group">
            <label class="form-label">
              <input type="checkbox" v-model="formData.onboot" style="margin-right: 8px;">
              Start VM at boot
            </label>
            <div class="form-text">Automatically start this VM when the Proxmox host boots</div>
          </div>

          <div class="grid grid-cols-3 gap-2">
            <div class="form-group">
              <label class="form-label">Startup Order (optional)</label>
              <input v-model.number="formData.startup_order" type="number" min="0" class="form-control" placeholder="Default" />
              <small class="form-help">Boot order (lower starts first)</small>
            </div>

            <div class="form-group">
              <label class="form-label">Startup Delay (seconds)</label>
              <input v-model.number="formData.startup_up" type="number" min="0" class="form-control" placeholder="0" />
              <small class="form-help">Delay before starting</small>
            </div>

            <div class="form-group">
              <label class="form-label">Shutdown Timeout (seconds)</label>
              <input v-model.number="formData.startup_down" type="number" min="0" class="form-control" placeholder="60" />
              <small class="form-help">Wait time before force stop</small>
            </div>
          </div>
          </div>
        </div>

        <!-- System Options -->
        <div class="form-section">
          <h4 class="section-title collapsible-header" @click="showSystemOptions = !showSystemOptions">
            <span class="toggle-icon">{{ showSystemOptions ? '▼' : '▶' }}</span>
            System Options
          </h4>

          <div v-show="showSystemOptions" class="collapsible-content">
          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">Hotplug Options (optional)</label>
              <input v-model="formData.hotplug" type="text" class="form-control" placeholder="disk,network,usb,memory,cpu" />
              <small class="form-help">Comma-separated list of hotplug devices</small>
            </div>

            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="formData.protection" style="margin-right: 8px;">
                Protection (prevent deletion)
              </label>
              <div class="form-text">Protect VM from accidental removal</div>
            </div>
          </div>

          <div class="grid grid-cols-3 gap-2">
            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="formData.kvm" style="margin-right: 8px;">
                Enable KVM Hardware Virtualization
              </label>
              <div class="form-text">Use hardware virtualization</div>
            </div>

            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="formData.acpi" style="margin-right: 8px;">
                Enable ACPI
              </label>
              <div class="form-text">Advanced power management</div>
            </div>

            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="formData.agent_enabled" style="margin-right: 8px;">
                Enable QEMU Guest Agent
              </label>
              <div class="form-text">Better VM management</div>
            </div>
          </div>
          </div>
        </div>

        <!-- VM Metadata -->
        <div class="form-section">
          <h4 class="section-title collapsible-header" @click="showMetadata = !showMetadata">
            <span class="toggle-icon">{{ showMetadata ? '▼' : '▶' }}</span>
            VM Metadata
          </h4>

          <div v-show="showMetadata" class="collapsible-content">
          <div class="form-group">
            <label class="form-label">Description (optional)</label>
            <textarea v-model="formData.description" class="form-control" rows="2" placeholder="VM description or notes..."></textarea>
          </div>

          <div class="form-group">
            <label class="form-label">Tags (optional)</label>
            <input v-model="formData.tags" type="text" class="form-control" placeholder="production;web-server;app" />
            <small class="form-help">Semicolon-separated tags</small>
          </div>
          </div>
        </div>

        <!-- Network Configuration -->
        <div class="form-section">
          <h4 class="section-title">Network Configuration</h4>

          <div class="form-group">
            <label class="form-label">
              <input v-model="useDHCP" type="checkbox" />
              Use DHCP (automatic IP assignment)
            </label>
          </div>

          <div v-if="!useDHCP" class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">IP Address</label>
              <input v-model="formData.ip_address" type="text" class="form-control" placeholder="192.168.1.100" />
            </div>

            <div class="form-group">
              <label class="form-label">Netmask (CIDR)</label>
              <input v-model="formData.netmask" type="text" class="form-control" placeholder="24" />
            </div>

            <div class="form-group">
              <label class="form-label">Gateway</label>
              <input v-model="formData.gateway" type="text" class="form-control" placeholder="192.168.1.1" />
            </div>

            <div class="form-group">
              <label class="form-label">DNS Servers</label>
              <input v-model="formData.dns_servers" type="text" class="form-control" placeholder="8.8.8.8,8.8.4.4" />
            </div>
          </div>
        </div>

        <!-- Credentials -->
        <div class="form-section">
          <h4 class="section-title">Credentials</h4>

          <div class="grid grid-cols-2 gap-2">
            <div class="form-group">
              <label class="form-label">Username *</label>
              <input v-model="formData.username" type="text" class="form-control" required />
            </div>

            <div class="form-group">
              <label class="form-label">Password *</label>
              <input v-model="formData.password" type="password" class="form-control" required />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">SSH Public Key (optional)</label>
            <textarea v-model="formData.ssh_key" class="form-control" rows="3" placeholder="ssh-rsa AAAA..."></textarea>
          </div>
        </div>

        <!-- Actions -->
        <div class="form-actions">
          <button type="submit" class="btn btn-primary" :disabled="creating">
            {{ creating ? 'Creating VM...' : 'Create Virtual Machine' }}
          </button>
          <router-link to="/vms" class="btn btn-outline">
            Cancel
          </router-link>
        </div>
      </form>
    </div>
  </div>

  <!-- Progress Modal - Teleported to body -->
  <Teleport to="body">
    <div v-show="showProgressModal" class="modal">
      <div class="modal-content progress-modal">
        <div class="modal-header">
          <h3>{{ progressData.status === 'error' ? 'Deployment Failed' : 'Deploying VM' }}</h3>
        </div>
        <div class="modal-body">
          <div class="progress-container">
            <div v-if="progressData.status === 'creating'" class="spinner-container">
              <div class="spinner"></div>
            </div>
            <div v-else-if="progressData.status === 'running'" class="success-icon">✓</div>
            <div v-else-if="progressData.status === 'error'" class="error-icon">✕</div>

            <h4 class="progress-vm-name">{{ progressData.name }}</h4>

            <div class="progress-steps">
              <div class="current-step">
                {{ progressData.status_message || 'Initializing deployment...' }}
              </div>
            </div>

            <!-- Progress Bar -->
            <div v-if="uploadProgress > 0 && uploadProgress < 100" class="progress-bar-container">
              <div class="progress-bar-background">
                <div class="progress-bar-fill" :style="{ width: uploadProgress + '%' }">
                  <span class="progress-bar-text">{{ uploadProgress }}%</span>
                </div>
              </div>
            </div>

            <div v-if="progressData.vmid" class="progress-vmid">
              VM ID: {{ progressData.vmid }}
            </div>

            <div v-if="progressData.error_message" class="progress-error">
              <strong>Error:</strong> {{ progressData.error_message }}
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button
            v-if="progressData.status === 'running' || progressData.status === 'error'"
            @click="closeProgressModal"
            class="btn btn-primary"
          >
            {{ progressData.status === 'running' ? 'Go to VMs' : 'Close' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'CreateVM',
  setup() {
    const router = useRouter()
    const toast = useToast()

    const hosts = ref([])
    const nodes = ref([])
    const isos = ref([])
    const cloudImages = ref([])
    const imageSource = ref('iso')
    const storageList = ref([])
    const networkList = ref([])
    const selectedHostId = ref('')
    const selectedStorage = ref('')
    const selectedBridge = ref('')
    const vlanTag = ref(null)
    const loadingNodes = ref(false)
    const loadingStorage = ref(false)
    const loadingNetwork = ref(false)
    const creating = ref(false)
    const useDHCP = ref(true)
    const showProgressModal = ref(false)

    // Section visibility state
    const showAdvancedHardware = ref(false)
    const showBootStartup = ref(false)
    const showSystemOptions = ref(false)
    const showMetadata = ref(false)
    const progressData = ref({
      name: '',
      status: 'creating',
      status_message: '',
      error_message: '',
      vmid: null
    })
    let progressInterval = null

    // Computed properties for sorted lists
    const sortedStorageList = computed(() => {
      return [...storageList.value]
        .filter(s => s.content && s.content.includes('images'))
        .sort((a, b) => a.storage.localeCompare(b.storage, undefined, { numeric: true, sensitivity: 'base' }))
    })

    const sortedISOStorageList = computed(() => {
      return [...storageList.value]
        .filter(s => s.content && s.content.includes('iso'))
        .sort((a, b) =>
          a.storage.localeCompare(b.storage, undefined, { numeric: true, sensitivity: 'base' })
        )
    })

    const sortedNetworkList = computed(() => {
      return [...networkList.value].sort((a, b) =>
        a.iface.localeCompare(b.iface, undefined, { numeric: true, sensitivity: 'base' })
      )
    })

    const formData = ref({
      name: '',
      hostname: '',
      proxmox_host_id: null,
      node_id: null,
      iso_id: null,
      cloud_image_id: null,
      os_type: '',
      cpu_sockets: 1,
      cpu_cores: 2,
      cpu_type: 'x86-64-v2-AES',
      cpu_flags: '',
      cpu_limit: null,
      cpu_units: 1024,
      numa_enabled: false,
      memory: 2048,
      balloon: null,
      shares: null,
      disk_size: 20,
      storage: '',
      iso_storage: '',
      scsihw: 'virtio-scsi-pci',
      bios_type: 'seabios',
      machine_type: 'pc',
      vga_type: 'std',
      boot_order: 'cdn',
      onboot: true,
      tablet: true,
      hotplug: null,
      protection: false,
      startup_order: null,
      startup_up: null,
      startup_down: null,
      kvm: true,
      acpi: true,
      agent_enabled: true,
      network_bridge: '',
      network_interfaces: [],
      vlan_tag: null,
      ip_address: '',
      gateway: '',
      netmask: '24',
      dns_servers: '8.8.8.8,8.8.4.4',
      username: 'administrator',
      password: '',
      ssh_key: '',
      description: '',
      tags: ''
    })

    const loadHosts = async () => {
      try {
        const response = await api.proxmox.listHosts()
        hosts.value = response.data.filter(h => h.is_active)
      } catch (error) {
        console.error('Failed to load hosts:', error)
      }
    }

    const selectDatacenter = async (hostId) => {
      selectedHostId.value = hostId
      formData.value.proxmox_host_id = hostId
      formData.value.node_id = null
      nodes.value = []
      storageList.value = []
      networkList.value = []
      selectedStorage.value = ''
      selectedBridge.value = ''

      loadingNodes.value = true
      try {
        const response = await api.proxmox.listNodes(hostId)
        nodes.value = response.data
      } catch (error) {
        console.error('Failed to load nodes:', error)
        toast.error('Failed to load nodes. Try polling the host first.')
      } finally {
        loadingNodes.value = false
      }
    }

    const selectNode = async (nodeId) => {
      formData.value.node_id = nodeId
      selectedStorage.value = ''
      selectedBridge.value = ''
      // Clear storage from form data to prevent using old node's storage
      formData.value.storage = ''
      formData.value.iso_storage = ''

      // Load storage and network for this node
      await Promise.all([loadStorage(nodeId), loadNetwork(nodeId)])
    }

    const loadStorage = async (nodeId) => {
      console.log('[DEBUG] loadStorage START, nodeId:', nodeId)
      loadingStorage.value = true
      console.log('[DEBUG] loadingStorage set to true')
      try {
        console.log('[DEBUG] Calling API...')
        const response = await api.proxmox.getNodeStorage(nodeId)
        console.log('[DEBUG] API response received:', response.data)
        console.log('[DEBUG] Setting storageList.value...')
        storageList.value = response.data.storage || []
        console.log('[DEBUG] storageList.value set, length:', storageList.value.length)

        // Auto-select first available storage for VM disks
        if (storageList.value.length > 0) {
          const firstStorage = storageList.value.find(s => s.enabled && s.active) || storageList.value[0]
          selectedStorage.value = firstStorage.storage
          formData.value.storage = firstStorage.storage
          console.log('[DEBUG] Auto-selected storage:', firstStorage.storage)
        }

        // Auto-select first available ISO storage
        const isoStorages = response.data.storage
          .filter(s => s.content && s.content.includes('iso') && s.enabled && s.active)
          .sort((a, b) => a.storage.localeCompare(b.storage, undefined, { numeric: true, sensitivity: 'base' }))
        if (isoStorages.length > 0) {
          formData.value.iso_storage = isoStorages[0].storage
          console.log('[DEBUG] Auto-selected ISO storage:', isoStorages[0].storage)
        }
        console.log('[DEBUG] loadStorage completing successfully')
      } catch (error) {
        console.error('[DEBUG] loadStorage ERROR:', error)
        console.error('Failed to load storage:', error)
        toast.error('Failed to load storage pools')
      } finally {
        console.log('[DEBUG] loadStorage FINALLY block, setting loadingStorage to false')
        loadingStorage.value = false
        console.log('[DEBUG] loadStorage END')
      }
    }

    const loadNetwork = async (nodeId) => {
      loadingNetwork.value = true
      try {
        const response = await api.proxmox.getNodeNetwork(nodeId)
        networkList.value = response.data.network
          .sort((a, b) => a.iface.localeCompare(b.iface, undefined, { numeric: true, sensitivity: 'base' }))

        // Auto-select first active bridge
        if (networkList.value.length > 0) {
          const firstBridge = networkList.value.find(n => n.active) || networkList.value[0]
          selectedBridge.value = firstBridge.iface
          formData.value.network_bridge = firstBridge.iface
        }
      } catch (error) {
        console.error('Failed to load network:', error)
        toast.error('Failed to load network interfaces')
      } finally {
        loadingNetwork.value = false
      }
    }

    const selectStorage = (storageName) => {
      const storage = storageList.value.find(s => s.storage === storageName)
      if (storage && storage.enabled && storage.active) {
        selectedStorage.value = storageName
        formData.value.storage = storageName
      }
    }

    const selectBridge = (bridgeName) => {
      const bridge = networkList.value.find(n => n.iface === bridgeName)
      if (bridge && bridge.active) {
        selectedBridge.value = bridgeName
        formData.value.network_bridge = bridgeName
      }
    }

    const getStorageUsagePercent = (storage) => {
      if (!storage.total || storage.total === 0) return 0
      return Math.round((storage.used / storage.total) * 100)
    }

    const loadISOs = async () => {
      try {
        const response = await api.isos.list()
        isos.value = response.data
      } catch (error) {
        console.error('Failed to load ISOs:', error)
      }
    }

    const loadCloudImages = async () => {
      try {
        const response = await api.cloudImages.list()
        cloudImages.value = response.data
      } catch (error) {
        console.error('Failed to load cloud images:', error)
      }
    }

    const pollProgress = async (vmId) => {
      try {
        const response = await api.vms.getProgress(vmId)
        console.log('Progress update received:', response.data)
        progressData.value = response.data

        // Stop polling if VM is running, stopped, or error
        if (response.data.status === 'running' || response.data.status === 'stopped' || response.data.status === 'error') {
          console.log('VM deployment finished with status:', response.data.status)
          if (progressInterval) {
            clearInterval(progressInterval)
            progressInterval = null
          }
        }
      } catch (error) {
        console.error('Failed to poll progress:', error)
      }
    }

    const closeProgressModal = () => {
      showProgressModal.value = false
      if (progressInterval) {
        clearInterval(progressInterval)
        progressInterval = null
      }
      if (progressData.value.status === 'running') {
        router.push('/vms')
      }
    }

    const validateForm = () => {
      const errors = []

      // Basic validation
      if (!formData.value.name || formData.value.name.trim() === '') {
        errors.push('VM name is required')
      }
      if (!formData.value.hostname || formData.value.hostname.trim() === '') {
        errors.push('Hostname is required')
      }
      if (!formData.value.os_type) {
        errors.push('Operating system must be selected')
      }

      // Datacenter and node validation
      if (!formData.value.proxmox_host_id) {
        errors.push('Proxmox datacenter must be selected')
      }
      if (!formData.value.node_id) {
        errors.push('Node must be selected')
      }

      // Storage validation
      if (!selectedStorage.value) {
        errors.push('Storage pool must be selected')
      }

      // Network validation
      if (!selectedBridge.value) {
        errors.push('Network bridge must be selected')
      }

      // Image source validation
      if (imageSource.value === 'iso' && formData.value.iso_id === null) {
        // ISO can be null for cloud-init only, but warn if cloud_image_id is also null
        if (!formData.value.cloud_image_id) {
          // This is okay - user might want ISO-less installation
        }
      } else if (imageSource.value === 'cloud_image' && !formData.value.cloud_image_id) {
        errors.push('Cloud image must be selected')
      }

      // Resource validation
      if (!formData.value.cpu_cores || formData.value.cpu_cores < 1) {
        errors.push('CPU cores must be at least 1')
      }
      if (!formData.value.memory || formData.value.memory < 512) {
        errors.push('Memory must be at least 512 MB')
      }
      if (!formData.value.disk_size || formData.value.disk_size < 10) {
        errors.push('Disk size must be at least 10 GB')
      }

      // Credentials validation
      if (!formData.value.username || formData.value.username.trim() === '') {
        errors.push('Username is required')
      }
      if (!formData.value.password || formData.value.password.trim() === '') {
        errors.push('Password is required')
      }

      // Network configuration validation (if not using DHCP)
      if (!useDHCP.value) {
        if (!formData.value.ip_address || formData.value.ip_address.trim() === '') {
          errors.push('IP address is required when not using DHCP')
        }
        if (!formData.value.gateway || formData.value.gateway.trim() === '') {
          errors.push('Gateway is required when not using DHCP')
        }
      }

      return errors
    }

    const createVM = async () => {
      // Validate form before submission
      const validationErrors = validateForm()
      if (validationErrors.length > 0) {
        // Show all validation errors
        validationErrors.forEach(error => {
          toast.error(error)
        })
        return
      }

      creating.value = true
      try {
        // Prepare payload with only the fields the backend expects
        const payload = {
          name: formData.value.name,
          hostname: formData.value.hostname,
          proxmox_host_id: formData.value.proxmox_host_id,
          node_id: formData.value.node_id,
          iso_id: imageSource.value === 'iso' ? formData.value.iso_id : null,
          cloud_image_id: imageSource.value === 'cloud_image' ? formData.value.cloud_image_id : null,
          os_type: formData.value.os_type,

          // CPU configuration
          cpu_sockets: formData.value.cpu_sockets,
          cpu_cores: formData.value.cpu_cores,
          cpu_type: formData.value.cpu_type || 'host',
          cpu_flags: formData.value.cpu_flags || null,
          cpu_limit: formData.value.cpu_limit || null,
          cpu_units: formData.value.cpu_units || 1024,
          numa_enabled: formData.value.numa_enabled || false,

          // Memory and disk
          memory: formData.value.memory,
          balloon: formData.value.balloon || null,
          shares: formData.value.shares || null,
          disk_size: formData.value.disk_size,
          storage: selectedStorage.value || null,
          iso_storage: formData.value.iso_storage || null,
          scsihw: formData.value.scsihw || 'virtio-scsi-pci',

          // Hardware options
          bios_type: formData.value.bios_type || 'seabios',
          machine_type: formData.value.machine_type || 'pc',
          vga_type: formData.value.vga_type || 'std',
          boot_order: formData.value.boot_order || 'cdn',
          onboot: formData.value.onboot !== undefined ? formData.value.onboot : true,
          tablet: formData.value.tablet !== undefined ? formData.value.tablet : true,
          hotplug: formData.value.hotplug || null,
          protection: formData.value.protection || false,
          startup_order: formData.value.startup_order || null,
          startup_up: formData.value.startup_up || null,
          startup_down: formData.value.startup_down || null,
          kvm: formData.value.kvm !== undefined ? formData.value.kvm : true,
          acpi: formData.value.acpi !== undefined ? formData.value.acpi : true,
          agent_enabled: formData.value.agent_enabled !== undefined ? formData.value.agent_enabled : true,

          // Network configuration
          network_bridge: selectedBridge.value || null,
          network_interfaces: formData.value.network_interfaces || null,

          // Credentials
          username: formData.value.username,
          password: formData.value.password,
          ssh_key: formData.value.ssh_key || null,

          // Metadata
          description: formData.value.description || null,
          tags: formData.value.tags || null
        }

        // If using DHCP, clear static IP fields
        if (useDHCP.value) {
          payload.ip_address = null
          payload.gateway = null
          payload.netmask = null
          payload.dns_servers = null
        } else {
          payload.ip_address = formData.value.ip_address || null
          payload.gateway = formData.value.gateway || null
          payload.netmask = formData.value.netmask || null
          payload.dns_servers = formData.value.dns_servers || null
        }

        console.log('Creating VM with payload:', JSON.stringify(payload, null, 2))
        const response = await api.vms.create(payload)

        console.log('VM created successfully, response:', response.data)
        console.log('Setting showProgressModal to true')

        // Show progress modal
        showProgressModal.value = true
        progressData.value = {
          name: formData.value.name,
          status: 'creating',
          status_message: 'Initializing VM deployment...',
          error_message: '',
          vmid: null
        }

        console.log('Progress modal should be visible now, showProgressModal:', showProgressModal.value)

        // Start polling for progress
        const vmId = response.data.id
        console.log('Starting progress polling for VM ID:', vmId)
        progressInterval = setInterval(() => {
          pollProgress(vmId)
        }, 1000) // Poll every second

        toast.success('VM creation started!')
      } catch (error) {
        console.error('Failed to create VM:', error)

        // Show specific validation errors if available
        if (error.response?.data?.detail) {
          if (Array.isArray(error.response.data.detail)) {
            // Pydantic validation errors
            const errors = error.response.data.detail.map(err => {
              const field = err.loc[err.loc.length - 1]
              return `${field}: ${err.msg}`
            }).join(', ')
            toast.error(`Validation error: ${errors}`)
          } else {
            toast.error(`Error: ${error.response.data.detail}`)
          }
        } else {
          toast.error('Failed to create VM. Check the form and try again.')
        }
      } finally {
        creating.value = false
      }
    }

    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const gb = bytes / (1024 * 1024 * 1024)
      return gb.toFixed(2) + ' GB'
    }

    // Watch for DHCP changes to clear/restore fields
    watch(useDHCP, (newVal) => {
      if (newVal) {
        formData.value.ip_address = ''
        formData.value.gateway = ''
        formData.value.netmask = '24'
        formData.value.dns_servers = '8.8.8.8,8.8.4.4'
      }
    })

    // Extract upload progress percentage from status message
    const uploadProgress = computed(() => {
      const message = progressData.value.status_message || ''
      // Match patterns like "Uploading: 45%" or "45%"
      const match = message.match(/(\d+)%/)
      return match ? parseInt(match[1]) : 0
    })

    onMounted(() => {
      loadHosts()
      loadISOs()
      loadCloudImages()
    })

    return {
      hosts,
      nodes,
      isos,
      cloudImages,
      imageSource,
      storageList,
      networkList,
      sortedStorageList,
      sortedISOStorageList,
      sortedNetworkList,
      selectedHostId,
      selectedStorage,
      selectedBridge,
      vlanTag,
      loadingNodes,
      showProgressModal,
      progressData,
      uploadProgress,
      closeProgressModal,
      loadingStorage,
      loadingNetwork,
      formData,
      creating,
      useDHCP,
      selectDatacenter,
      selectNode,
      selectStorage,
      selectBridge,
      getStorageUsagePercent,
      createVM,
      formatBytes,
      showAdvancedHardware,
      showBootStartup,
      showSystemOptions,
      showMetadata
    }
  }
}
</script>

<style scoped>
.create-vm-form {
  padding: 1.5rem;
}

.form-section {
  margin-bottom: 2rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid var(--border-color);
}

.form-section:last-of-type {
  border-bottom: none;
}

.section-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.datacenter-cards, .node-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
  margin-top: 0.5rem;
}

.datacenter-card, .node-card {
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--background);
}

.datacenter-card:hover, .node-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.datacenter-card.selected, .node-card.selected {
  border-color: var(--primary-color);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(147, 51, 234, 0.1));
}

.datacenter-card {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.datacenter-icon {
  font-size: 2.5rem;
  flex-shrink: 0;
}

.datacenter-info h5 {
  margin: 0 0 0.25rem 0;
  font-size: 1.125rem;
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.node-header h6 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.node-resources {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.resource-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.resource-icon {
  font-size: 1rem;
}

.storage-cards, .network-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
  margin-top: 0.5rem;
}

.storage-card, .network-card {
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--background);
  position: relative;
}

.storage-card:hover, .network-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.storage-card.selected, .network-card.selected {
  border-color: var(--primary-color);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(147, 51, 234, 0.1));
}

.storage-card.disabled, .network-card.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.storage-header, .network-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.storage-header h6, .network-header h6 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.storage-bar {
  width: 100%;
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.storage-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
  transition: width 0.3s;
}

.storage-stats {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.storage-badge {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
}

.network-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.loading-message {
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary);
}

.badge-sm {
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
}

.form-actions {
  display: flex;
  gap: 1rem;
  padding-top: 1rem;
}

/* Progress Modal Styles */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal[style*="display: none"] {
  display: none !important;
}

.progress-modal {
  background: white;
  border-radius: 0.5rem;
  max-width: 500px;
  width: 90%;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.modal-body {
  padding: 2rem 1.5rem;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
}

.progress-container {
  text-align: center;
}

.spinner-container {
  margin: 0 auto 1.5rem;
  width: 64px;
  height: 64px;
}

.spinner {
  width: 64px;
  height: 64px;
  border: 4px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.success-icon {
  width: 64px;
  height: 64px;
  line-height: 64px;
  margin: 0 auto 1.5rem;
  font-size: 3rem;
  color: #10b981;
  background: #d1fae5;
  border-radius: 50%;
}

.error-icon {
  width: 64px;
  height: 64px;
  line-height: 64px;
  margin: 0 auto 1.5rem;
  font-size: 3rem;
  color: #ef4444;
  background: #fee2e2;
  border-radius: 50%;
}

.progress-vm-name {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.progress-steps {
  margin: 1.5rem 0;
  padding: 1.25rem;
  background: #f8fafc;
  border-radius: 0.5rem;
  border-left: 4px solid #3b82f6;
}

.current-step {
  font-size: 1.125rem;
  font-weight: 500;
  color: #1e40af;
  line-height: 1.6;
  animation: pulse-text 2s ease-in-out infinite;
}

@keyframes pulse-text {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.progress-vmid {
  font-size: 0.875rem;
  color: var(--text-secondary);
  font-family: monospace;
  margin-top: 0.5rem;
}

.progress-error {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #fee2e2;
  border: 1px solid #ef4444;
  border-radius: 0.375rem;
  color: #991b1b;
  text-align: left;
}

.progress-error strong {
  display: block;
  margin-bottom: 0.5rem;
}

.progress-bar-container {
  margin: 1.5rem 0;
}

.progress-bar-background {
  width: 100%;
  height: 32px;
  background-color: #e5e7eb;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
  transition: width 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
}

.progress-bar-fill::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.progress-bar-text {
  color: white;
  font-weight: 600;
  font-size: 0.875rem;
  z-index: 1;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
  opacity: 0.8;
}

/* Collapsible section styles */
.collapsible-header {
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  margin: -0.75rem;
  border-radius: 6px;
  transition: background-color 0.2s;
}

.collapsible-header:hover {
  background-color: rgba(59, 130, 246, 0.05);
}

.toggle-icon {
  font-size: 0.875rem;
  color: #3b82f6;
  transition: transform 0.2s;
  display: inline-block;
  width: 1rem;
}

.collapsible-content {
  margin-top: 1rem;
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
