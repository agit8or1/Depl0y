<template>
  <div class="create-vm-page">
    <div class="card">
      <div class="card-header">
        <h3>Create Virtual Machine</h3>
        <p class="card-subtitle">Configure your new VM, then review and create.</p>
      </div>

      <!-- Step Progress Bar -->
      <div class="step-progress">
        <div
          v-for="(tab, i) in tabs"
          :key="tab.id"
          class="step-item"
          :class="{
            'step-active': activeTab === tab.id,
            'step-done': tabIndex > i,
            'step-error': tabErrors[tab.id]
          }"
          @click="goToTab(i)"
        >
          <div class="step-connector-before" v-if="i > 0"></div>
          <div class="step-circle">
            <span v-if="tabErrors[tab.id]" class="step-circle-icon">!</span>
            <span v-else-if="tabIndex > i" class="step-circle-icon">&#10003;</span>
            <span v-else class="step-circle-num">{{ i + 1 }}</span>
          </div>
          <div class="step-label">{{ tab.label }}</div>
          <div class="step-connector-after" v-if="i < tabs.length - 1"></div>
        </div>
      </div>

      <form @submit.prevent="createVM" class="create-vm-form">

        <!-- ==================== GENERAL TAB ==================== -->
        <div v-show="activeTab === 'general'" class="tab-content">
          <h4 class="section-title">General Settings</h4>

          <!-- Datacenter & Node Selection -->
          <div class="form-section">
            <h5 class="subsection-title">Datacenter &amp; Node</h5>
            <div class="form-group">
              <label class="form-label">Select Proxmox Datacenter *</label>
              <div class="datacenter-cards">
                <div
                  v-for="host in hosts"
                  :key="host.id"
                  :class="['datacenter-card', { 'selected': selectedHostId === host.id }]"
                  @click="selectDatacenter(host.id)"
                >
                  <div class="datacenter-icon">&#127970;</div>
                  <div class="datacenter-info">
                    <h5>{{ host.name }}</h5>
                    <p class="text-xs">{{ host.hostname }}:{{ host.port }}</p>
                    <span :class="['badge', host.is_active ? 'badge-success' : 'badge-danger']">
                      {{ host.is_active ? 'Active' : 'Inactive' }}
                    </span>
                  </div>
                </div>
              </div>
              <small v-if="stepErrors.general?.host" class="form-error-text">{{ stepErrors.general.host }}</small>
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
                      <span class="resource-icon">&#128421;</span>
                      <span>{{ node.cpu_cores }} cores</span>
                      <div class="resource-bar-wrap">
                        <div class="resource-bar">
                          <div class="resource-bar-fill cpu" :style="{ width: Math.round(node.cpu_usage || 0) + '%' }"></div>
                        </div>
                        <span class="resource-pct">{{ Math.round(node.cpu_usage || 0) }}%</span>
                      </div>
                    </div>
                    <div class="resource-item">
                      <span class="resource-icon">&#128190;</span>
                      <span>{{ formatBytes(node.memory_total) }} RAM</span>
                      <div class="resource-bar-wrap">
                        <div class="resource-bar">
                          <div class="resource-bar-fill mem" :style="{ width: node.memory_total ? Math.round(((node.memory_total - (node.memory_free || 0)) / node.memory_total) * 100) + '%' : '0%' }"></div>
                        </div>
                        <span class="resource-pct">{{ node.memory_total ? Math.round(((node.memory_total - (node.memory_free || 0)) / node.memory_total) * 100) : 0 }}%</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <small v-if="stepErrors.general?.node" class="form-error-text">{{ stepErrors.general.node }}</small>
            </div>
            <div v-if="selectedHostId && loadingNodes" class="loading-message">
              <div class="loading-spinner"></div>
              <p>Loading nodes...</p>
            </div>
          </div>

          <!-- VM Identity -->
          <div class="form-section">
            <h5 class="subsection-title">VM Identity</h5>
            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">VM ID</label>
                <div class="input-with-status">
                  <input
                    v-model.number="formData.vmid"
                    type="number"
                    min="100"
                    max="999999999"
                    class="form-control"
                    :class="{ 'input-error': vmIdStatus === 'taken', 'input-ok': vmIdStatus === 'free' }"
                    placeholder="Auto-assign"
                    @input="debouncedCheckVmId"
                  />
                  <span v-if="vmIdStatus === 'checking'" class="status-icon checking">&#8635;</span>
                  <span v-else-if="vmIdStatus === 'taken'" class="status-icon taken" title="VM ID already in use">&#10005;</span>
                  <span v-else-if="vmIdStatus === 'free'" class="status-icon free" title="VM ID available">&#10003;</span>
                </div>
                <small v-if="vmIdStatus === 'taken'" class="form-help error-text">VM ID {{ formData.vmid }} is already in use</small>
                <small v-else class="form-help">Leave blank to auto-assign</small>
              </div>

              <div class="form-group">
                <label class="form-label">VM Name *</label>
                <input
                  v-model="formData.name"
                  :class="['form-control', { 'input-error': fieldErrors.name }]"
                  required
                  placeholder="my-vm"
                  @blur="validateField('name', formData.name, [rules.required, rules.vmName])"
                />
                <small v-if="fieldErrors.name" class="form-error-text">{{ fieldErrors.name }}</small>
                <small v-else class="form-help">Letters, numbers, hyphens, dots. Max 63 chars.</small>
              </div>

              <div class="form-group">
                <label class="form-label">Hostname *</label>
                <input
                  v-model="formData.hostname"
                  :class="['form-control', { 'input-error': fieldErrors.hostname }]"
                  required
                  placeholder="my-vm"
                  @blur="validateField('hostname', formData.hostname, [rules.required, rules.hostname])"
                />
                <small v-if="fieldErrors.hostname" class="form-error-text">{{ fieldErrors.hostname }}</small>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Description / Notes</label>
              <textarea v-model="formData.description" class="form-control" rows="2" placeholder="Optional notes about this VM..."></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Tags</label>
              <div class="tag-input-area" @click="$refs.tagInput.focus()">
                <span
                  v-for="(tag, idx) in parsedTags"
                  :key="idx"
                  class="tag-chip"
                  :style="{ background: tagColor(tag) }"
                >
                  {{ tag }}
                  <button type="button" class="tag-remove" @click.stop="removeTag(idx)">&#215;</button>
                </span>
                <input
                  ref="tagInput"
                  v-model="tagInputValue"
                  class="tag-text-input"
                  placeholder="Add tag, press Enter or comma..."
                  @keydown.enter.prevent="addTag"
                  @keydown.comma.prevent="addTag"
                  @keydown.backspace="removeLastTagOnBackspace"
                />
              </div>
              <small class="form-help">Press Enter or comma to add a tag</small>
            </div>
          </div>

          <!-- OS & Installation -->
          <div class="form-section">
            <h5 class="subsection-title">Operating System &amp; Installation</h5>
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
                    <option value="vyos">VyOS</option>
                  </optgroup>
                  <optgroup label="Other">
                    <option value="freebsd">FreeBSD</option>
                    <option value="truenas">TrueNAS</option>
                    <option value="proxmox">Proxmox VE</option>
                    <option value="other">Other / Custom</option>
                  </optgroup>
                </select>
                <small v-if="stepErrors.general?.os" class="form-error-text">{{ stepErrors.general.os }}</small>
              </div>

              <div class="form-group">
                <label class="form-label">Installation Method *</label>
                <div class="radio-group">
                  <label class="radio-label">
                    <input type="radio" v-model="imageSource" value="iso" />
                    <span>ISO Image</span>
                  </label>
                  <label class="radio-label">
                    <input type="radio" v-model="imageSource" value="cloud_image" />
                    <span>Cloud Image (Fast)</span>
                  </label>
                </div>
                <select v-if="imageSource === 'iso'" v-model="formData.iso_id" class="form-control" style="margin-top:0.5rem">
                  <option :value="null">No ISO</option>
                  <option v-for="iso in isos" :key="iso.id" :value="iso.id">
                    {{ iso.name }} ({{ iso.version }})
                  </option>
                </select>
                <select v-if="imageSource === 'cloud_image'" v-model="formData.cloud_image_id" class="form-control" style="margin-top:0.5rem" required>
                  <option :value="null">Select Cloud Image</option>
                  <option v-for="image in cloudImages" :key="image.id" :value="image.id">
                    {{ image.name }} {{ image.version ? '(' + image.version + ')' : '' }}
                  </option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <!-- ==================== HARDWARE TAB ==================== -->
        <div v-show="activeTab === 'hardware'" class="tab-content">
          <h4 class="section-title">Hardware Configuration</h4>

          <!-- Hardware Presets -->
          <div class="form-section">
            <h5 class="subsection-title">Quick Presets</h5>
            <p class="preset-hint">Click a preset to fill CPU, RAM, and primary disk size instantly.</p>
            <div class="preset-cards">
              <div
                v-for="preset in hwPresets"
                :key="preset.name"
                :class="['preset-card', { 'preset-selected': activePreset === preset.name }]"
                @click="applyPreset(preset)"
              >
                <div class="preset-name">{{ preset.name }}</div>
                <div class="preset-specs">
                  <span class="preset-spec">&#128421; {{ preset.cpu }}vCPU</span>
                  <span class="preset-spec">&#128190; {{ preset.memGb }}GB</span>
                  <span class="preset-spec">&#128190; {{ preset.diskGb }}GB</span>
                </div>
              </div>
            </div>
          </div>

          <!-- CPU -->
          <div class="form-section">
            <h5 class="subsection-title">CPU</h5>
            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">CPU Sockets *</label>
                <input
                  v-model.number="formData.cpu_sockets"
                  type="number" min="1" max="8"
                  :class="['form-control', { 'input-error': fieldErrors.cpu_sockets }]"
                  required
                  @blur="validateField('cpu_sockets', formData.cpu_sockets, [rules.required, rules.intRange(1, 16)])"
                />
                <small v-if="fieldErrors.cpu_sockets" class="form-error-text">{{ fieldErrors.cpu_sockets }}</small>
              </div>
              <div class="form-group">
                <label class="form-label">CPU Cores *</label>
                <input
                  v-model.number="formData.cpu_cores"
                  type="number" min="1" max="64"
                  :class="['form-control', { 'input-error': fieldErrors.cpu_cores }]"
                  required
                  @blur="validateField('cpu_cores', formData.cpu_cores, [rules.required, rules.intRange(1, 512)])"
                />
                <small v-if="fieldErrors.cpu_cores" class="form-error-text">{{ fieldErrors.cpu_cores }}</small>
              </div>
              <div class="form-group">
                <label class="form-label">Total vCPUs</label>
                <input :value="formData.cpu_sockets * formData.cpu_cores" type="number" class="form-control" disabled style="background:var(--border-color);color:var(--text-secondary)" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">CPU Type</label>
              <select v-model="formData.cpu_type" class="form-control">
                <optgroup label="Generic / Recommended">
                  <option value="x86-64-v2-AES">x86-64-v2-AES (Recommended)</option>
                  <option value="x86-64-v2">x86-64-v2 (Broadwell+)</option>
                  <option value="x86-64-v3">x86-64-v3 (Haswell+)</option>
                  <option value="x86-64-v4">x86-64-v4 (AVX-512)</option>
                  <option value="host">host (Passthrough — best performance)</option>
                  <option value="max">max (All features)</option>
                  <option value="kvm64">kvm64 (Legacy KVM)</option>
                  <option value="qemu64">qemu64 (Generic QEMU)</option>
                </optgroup>
                <optgroup label="Intel">
                  <option value="Cascadelake-Server">Cascadelake Server</option>
                  <option value="Skylake-Server">Skylake Server</option>
                  <option value="Broadwell">Broadwell</option>
                  <option value="Haswell">Haswell</option>
                  <option value="IvyBridge">IvyBridge</option>
                  <option value="SandyBridge">SandyBridge</option>
                </optgroup>
                <optgroup label="AMD">
                  <option value="EPYC">AMD EPYC</option>
                  <option value="EPYC-Rome">AMD EPYC Rome</option>
                  <option value="EPYC-Milan">AMD EPYC Milan</option>
                </optgroup>
              </select>
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">CPU Limit (max usage)</label>
                <input v-model.number="formData.cpu_limit" type="number" min="0" max="128" class="form-control" placeholder="0 = unlimited" />
              </div>
              <div class="form-group">
                <label class="form-label">CPU Units (priority weight)</label>
                <input v-model.number="formData.cpu_units" type="number" min="8" max="500000" class="form-control" />
                <small class="form-help">Default 1024, higher = more priority</small>
              </div>
            </div>
          </div>

          <!-- Memory -->
          <div class="form-section">
            <h5 class="subsection-title">Memory</h5>
            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">Memory (MB) *</label>
                <input
                  v-model.number="formData.memory"
                  type="number" min="512" max="4194304" step="512"
                  :class="['form-control', { 'input-error': fieldErrors.memory }]"
                  required
                  @blur="validateField('memory', formData.memory, [rules.required, rules.intRange(512, 4194304)])"
                />
                <small v-if="fieldErrors.memory" class="form-error-text">{{ fieldErrors.memory }}</small>
                <small v-else class="form-help">{{ (formData.memory / 1024).toFixed(1) }} GB</small>
              </div>
              <div class="form-group">
                <label class="form-label">Memory Shares</label>
                <input v-model.number="formData.shares" type="number" min="0" max="50000" class="form-control" placeholder="Default (1000)" />
                <small class="form-help">Higher = more priority under contention</small>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="formData.balloon_enabled" style="margin-right:8px" />
                Enable Ballooning Device
              </label>
              <div class="form-text">Allows dynamic RAM adjustment. Requires balloon driver in guest.</div>
            </div>
            <div v-if="formData.balloon_enabled" class="form-group">
              <label class="form-label">Minimum Memory (MB)</label>
              <input v-model.number="formData.balloon" type="number" min="0" :max="formData.memory" step="256" class="form-control" placeholder="0 = disable balloon" />
            </div>
          </div>

          <!-- System -->
          <div class="form-section">
            <h5 class="subsection-title">Machine &amp; BIOS</h5>
            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">Machine Type</label>
                <select v-model="formData.machine_type" class="form-control">
                  <option value="pc">i440FX (PC) — Classic, broad compatibility</option>
                  <option value="q35">Q35 (PCIe) — Modern, PCIe passthrough support</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">BIOS Type</label>
                <select v-model="formData.bios_type" class="form-control">
                  <option value="seabios">SeaBIOS (Legacy BIOS)</option>
                  <option value="ovmf">OVMF (UEFI)</option>
                </select>
              </div>
            </div>
            <div v-if="formData.bios_type === 'ovmf'" class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="formData.tpm_enabled" style="margin-right:8px" />
                Enable TPM 2.0
              </label>
              <div class="form-text">Required for Windows 11 and secure boot environments</div>
            </div>

            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">SCSI Controller</label>
                <select v-model="formData.scsihw" class="form-control">
                  <option value="virtio-scsi-pci">VirtIO SCSI (Recommended)</option>
                  <option value="virtio-scsi-single">VirtIO SCSI Single</option>
                  <option value="lsi">LSI 53C895A</option>
                  <option value="megasas">MegaRAID SAS</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">VGA Type</label>
                <select v-model="formData.vga_type" class="form-control">
                  <option value="std">Standard VGA</option>
                  <option value="virtio">VirtIO-GPU</option>
                  <option value="qxl">QXL (SPICE)</option>
                  <option value="none">None</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Boot Order</label>
                <select v-model="formData.boot_order" class="form-control">
                  <option value="cdn">Disk, CD-ROM, Network</option>
                  <option value="dcn">CD-ROM, Disk, Network</option>
                  <option value="ncd">Network, Disk, CD-ROM</option>
                  <option value="c">Disk only</option>
                </select>
              </div>
            </div>

            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">
                  <input type="checkbox" v-model="formData.agent_enabled" style="margin-right:8px" />
                  QEMU Guest Agent
                </label>
              </div>
              <div class="form-group">
                <label class="form-label">
                  <input type="checkbox" v-model="formData.onboot" style="margin-right:8px" />
                  Start at Boot
                </label>
              </div>
              <div class="form-group">
                <label class="form-label">
                  <input type="checkbox" v-model="formData.protection" style="margin-right:8px" />
                  Protection (prevent deletion)
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- ==================== STORAGE TAB ==================== -->
        <div v-show="activeTab === 'storage'" class="tab-content">
          <h4 class="section-title">Storage Configuration</h4>

          <div v-if="!formData.node_id" class="info-banner">Select a Proxmox host and node first (General tab).</div>

          <div v-else>
            <!-- Storage Pool Selection -->
            <div class="form-section">
              <h5 class="subsection-title">Storage Pool</h5>
              <div v-if="loadingStorage" class="loading-message">
                <div class="loading-spinner"></div><p>Loading storage pools...</p>
              </div>
              <div v-else>
                <p class="storage-hint">
                  Primary disk size: <strong>{{ disks[0]?.size || 0 }} GB</strong>.
                  Greyed-out pools have insufficient free space.
                </p>
                <div v-if="sortedStorageList.length === 0" class="info-banner">
                  No image-capable storage pools found on this node. Ensure at least one storage has the <strong>Images</strong> content type enabled in Proxmox.
                </div>
                <div class="storage-cards">
                  <div
                    v-for="storage in sortedStorageList"
                    :key="storage.storage"
                    :class="['storage-card', {
                      'selected': selectedStorage === storage.storage,
                      'disabled': !storage.enabled || !storage.active || !storageHasSpace(storage)
                    }]"
                    @click="selectStorage(storage.storage)"
                  >
                    <div class="storage-header">
                      <div class="storage-name-row">
                        <span class="storage-type-icon">{{ storageTypeIcon(storage.type) }}</span>
                        <h6>{{ storage.storage }}</h6>
                      </div>
                      <span class="badge badge-sm badge-info">{{ storage.type }}</span>
                    </div>
                    <div class="storage-info">
                      <div class="storage-bar">
                        <div class="storage-bar-fill"
                          :class="getStorageUsagePercent(storage) > 85 ? 'storage-bar-danger' : ''"
                          :style="{ width: getStorageUsagePercent(storage) + '%' }">
                        </div>
                      </div>
                      <div class="storage-stats">
                        <span>{{ formatBytes(storage.available) }} free</span>
                        <span>{{ formatBytes(storage.total) }} total</span>
                      </div>
                    </div>
                    <div v-if="!storageHasSpace(storage)" class="storage-insufficient">Insufficient space</div>
                    <div v-if="storage.shared" class="storage-badge"><span class="badge badge-success">Shared</span></div>
                  </div>
                </div>
                <small v-if="stepErrors.storage?.pool" class="form-error-text">{{ stepErrors.storage.pool }}</small>
              </div>
            </div>

            <!-- Disk List -->
            <div class="form-section">
              <div class="section-header-with-action">
                <h5 class="subsection-title">Virtual Disks</h5>
                <button type="button" class="btn btn-sm btn-outline" @click="addDisk" :disabled="disks.length >= 8">+ Add Disk</button>
              </div>

              <div v-for="(disk, idx) in disks" :key="idx" class="disk-row">
                <div class="disk-row-header">
                  <span class="disk-label">scsi{{ idx }}</span>
                  <button type="button" class="btn-icon-danger" @click="removeDisk(idx)" v-if="idx > 0" title="Remove disk">&#10005;</button>
                </div>
                <div class="grid grid-cols-4 gap-2">
                  <div class="form-group">
                    <label class="form-label">Storage</label>
                    <select v-model="disk.storage" class="form-control">
                      <option v-for="s in sortedStorageList" :key="s.storage" :value="s.storage">{{ s.storage }}</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label">Size (GB)</label>
                    <input v-model.number="disk.size" type="number" min="1" class="form-control" :required="idx === 0" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Format</label>
                    <select v-model="disk.format" class="form-control">
                      <option value="qcow2">qcow2 (sparse, snapshots)</option>
                      <option value="raw">raw (best performance)</option>
                      <option value="vmdk">vmdk</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label">Cache</label>
                    <select v-model="disk.cache" class="form-control">
                      <option value="">Default (no cache)</option>
                      <option value="none">None (safest)</option>
                      <option value="writethrough">Write-through</option>
                      <option value="writeback">Write-back (fastest)</option>
                      <option value="unsafe">Unsafe</option>
                    </select>
                  </div>
                </div>
                <div class="disk-options-row">
                  <label class="disk-option-check"><input type="checkbox" v-model="disk.discard" /> Discard (SSD TRIM)</label>
                  <label class="disk-option-check"><input type="checkbox" v-model="disk.ssd" /> SSD emulation</label>
                  <label class="disk-option-check"><input type="checkbox" v-model="disk.backup" /> Include in backup</label>
                  <label class="disk-option-check"><input type="checkbox" v-model="disk.iothread" /> IO Thread</label>
                </div>
              </div>
            </div>

            <!-- ISO Storage -->
            <div class="form-section">
              <h5 class="subsection-title">ISO Storage (if using ISO)</h5>
              <div class="storage-cards">
                <div
                  v-for="storage in sortedISOStorageList"
                  :key="'iso-' + storage.storage"
                  :class="['storage-card', { 'selected': formData.iso_storage === storage.storage, 'disabled': !storage.enabled || !storage.active }]"
                  @click="formData.iso_storage = storage.storage"
                >
                  <div class="storage-header">
                    <div class="storage-name-row">
                      <span class="storage-type-icon">{{ storageTypeIcon(storage.type) }}</span>
                      <h6>{{ storage.storage }}</h6>
                    </div>
                    <span class="badge badge-sm badge-info">{{ storage.type }}</span>
                  </div>
                  <div class="storage-stats-simple">{{ formatBytes(storage.available) }} free / {{ formatBytes(storage.total) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ==================== NETWORK TAB ==================== -->
        <div v-show="activeTab === 'network'" class="tab-content">
          <h4 class="section-title">Network Configuration</h4>

          <div v-if="!formData.node_id" class="info-banner">Select a Proxmox host and node first (General tab).</div>

          <div v-else>
            <!-- Bridge Selection -->
            <div class="form-section">
              <h5 class="subsection-title">Available Bridges</h5>
              <div v-if="loadingNetwork" class="loading-message">
                <div class="loading-spinner"></div><p>Loading network interfaces...</p>
              </div>
              <div v-else class="network-cards">
                <div
                  v-for="net in sortedNetworkList"
                  :key="net.iface"
                  :class="['network-card', { 'selected': selectedBridge === net.iface, 'disabled': !net.active }]"
                  @click="selectBridge(net.iface)"
                >
                  <div class="network-header">
                    <h6>{{ net.iface }}</h6>
                    <div class="network-badges">
                      <span :class="['badge', 'badge-sm', net.active ? 'badge-success' : 'badge-danger']">
                        {{ net.active ? 'Active' : 'Down' }}
                      </span>
                      <span v-if="bridgeSupportsVlan(net)" class="badge badge-sm badge-info">VLAN-aware</span>
                    </div>
                  </div>
                  <div class="network-details">
                    <div v-if="net.address" class="net-detail"><span class="net-detail-label">IP:</span> {{ net.address }}</div>
                    <div v-if="net.bridge_ports" class="net-detail"><span class="net-detail-label">Ports:</span> {{ net.bridge_ports }}</div>
                    <div v-if="net.mtu" class="net-detail"><span class="net-detail-label">MTU:</span> {{ net.mtu }}</div>
                    <div v-if="net.bridge_vlan_aware" class="net-detail net-vlan-aware"><span class="net-detail-label">VLAN-aware:</span> Yes</div>
                  </div>
                </div>
              </div>
              <small v-if="stepErrors.network?.bridge" class="form-error-text">{{ stepErrors.network.bridge }}</small>
            </div>

            <!-- NIC List -->
            <div class="form-section">
              <div class="section-header-with-action">
                <h5 class="subsection-title">Network Interfaces (NICs)</h5>
                <button type="button" class="btn btn-sm btn-outline" @click="addNic" :disabled="nics.length >= 8">+ Add NIC</button>
              </div>

              <div v-for="(nic, idx) in nics" :key="idx" class="nic-row">
                <div class="nic-row-header">
                  <span class="nic-label">net{{ idx }}</span>
                  <button type="button" class="btn-icon-danger" @click="removeNic(idx)" v-if="idx > 0" title="Remove NIC">&#10005;</button>
                </div>
                <div class="grid grid-cols-3 gap-2">
                  <div class="form-group">
                    <label class="form-label">Model</label>
                    <select v-model="nic.model" class="form-control">
                      <option value="virtio">VirtIO (Recommended)</option>
                      <option value="e1000">Intel E1000</option>
                      <option value="e1000e">Intel E1000e</option>
                      <option value="vmxnet3">VMware VMXNET3</option>
                      <option value="rtl8139">Realtek RTL8139</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label">Bridge</label>
                    <select v-model="nic.bridge" class="form-control">
                      <option v-for="net in sortedNetworkList" :key="net.iface" :value="net.iface">{{ net.iface }}</option>
                      <option v-if="sortedNetworkList.length === 0" :value="selectedBridge || 'vmbr0'">{{ selectedBridge || 'vmbr0' }}</option>
                    </select>
                  </div>
                  <div class="form-group" v-if="nicBridgeSupportsVlan(nic)">
                    <label class="form-label">VLAN Tag <span class="vlan-optional">(optional)</span></label>
                    <input v-model.number="nic.vlan" type="number" min="1" max="4094" class="form-control" placeholder="None" />
                    <small class="form-help">1–4094, leave blank for untagged</small>
                  </div>
                  <div class="form-group" v-else>
                    <label class="form-label">VLAN Tag</label>
                    <input v-model.number="nic.vlan" type="number" min="1" max="4094" class="form-control" placeholder="None" />
                  </div>
                </div>

                <!-- MAC address row -->
                <div class="grid grid-cols-3 gap-2">
                  <div class="form-group">
                    <label class="form-label">MAC Address</label>
                    <div class="mac-row">
                      <div class="mac-toggle">
                        <label class="radio-label">
                          <input type="radio" :name="'mac-mode-' + idx" value="random" v-model="nic.macMode" />
                          <span>Random</span>
                        </label>
                        <label class="radio-label">
                          <input type="radio" :name="'mac-mode-' + idx" value="custom" v-model="nic.macMode" />
                          <span>Custom</span>
                        </label>
                      </div>
                      <input
                        v-if="nic.macMode === 'custom'"
                        v-model="nic.mac"
                        type="text"
                        :class="['form-control', 'mac-input', { 'input-error': nic.macError }]"
                        placeholder="AA:BB:CC:DD:EE:FF"
                        pattern="([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}"
                        @blur="validateMac(nic)"
                      />
                      <small v-if="nic.macError" class="form-error-text">{{ nic.macError }}</small>
                    </div>
                  </div>
                  <div class="form-group">
                    <label class="form-label">Rate Limit (MB/s)</label>
                    <input v-model.number="nic.rate" type="number" min="0" class="form-control" placeholder="Unlimited" />
                  </div>
                  <div class="form-group" style="padding-top:1.5rem">
                    <label class="disk-option-check">
                      <input type="checkbox" v-model="nic.firewall" />
                      Firewall enabled
                    </label>
                    <label class="disk-option-check" style="margin-top:0.25rem">
                      <input type="checkbox" v-model="nic.linkdown" />
                      Link down (disconnected)
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ==================== CLOUD-INIT TAB ==================== -->
        <div v-show="activeTab === 'cloudinit'" class="tab-content">
          <h4 class="section-title">Cloud-Init / Credentials</h4>

          <div class="form-section">
            <h5 class="subsection-title">Authentication</h5>
            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">Username *</label>
                <input v-model="formData.username" type="text"
                  :class="['form-control', { 'input-error': fieldErrors.username }]"
                  required placeholder="administrator"
                  @blur="validateField('username', formData.username, [rules.required])"
                />
                <small v-if="fieldErrors.username" class="form-error-text">{{ fieldErrors.username }}</small>
              </div>
              <div class="form-group">
                <label class="form-label">Password *</label>
                <input v-model="formData.password" type="password"
                  :class="['form-control', { 'input-error': fieldErrors.password }]"
                  required autocomplete="new-password"
                  @blur="validateField('password', formData.password, [rules.required, rules.password(8)])"
                />
                <small v-if="fieldErrors.password" class="form-error-text">{{ fieldErrors.password }}</small>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">SSH Public Keys</label>
              <textarea v-model="formData.ssh_key" class="form-control" rows="4" placeholder="ssh-rsa AAAA...&#10;ssh-ed25519 AAAA...&#10;(one per line)"></textarea>
              <small class="form-help">One public key per line</small>
            </div>
          </div>

          <div class="form-section">
            <h5 class="subsection-title">IP Configuration</h5>
            <div class="form-group">
              <label class="form-label">
                <input v-model="useDHCP" type="checkbox" style="margin-right:8px" />
                Use DHCP (automatic IP assignment)
              </label>
            </div>

            <div v-if="!useDHCP" class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">IP Address</label>
                <input
                  v-model="formData.ip_address"
                  type="text"
                  :class="['form-control', { 'input-error': fieldErrors.ip_address }]"
                  placeholder="192.168.1.100"
                  @blur="validateField('ip_address', formData.ip_address, [rules.required, rules.ipAddress])"
                />
                <small v-if="fieldErrors.ip_address" class="form-error-text">{{ fieldErrors.ip_address }}</small>
              </div>
              <div class="form-group">
                <label class="form-label">Netmask (CIDR prefix)</label>
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

          <div class="form-section">
            <h5 class="subsection-title">DNS &amp; Options</h5>
            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">DNS Search Domain</label>
                <input v-model="formData.searchdomain" type="text" class="form-control" placeholder="example.com" />
              </div>
              <div class="form-group">
                <label class="form-label">
                  <input type="checkbox" v-model="formData.upgrade_packages" style="margin-right:8px" />
                  Upgrade packages on first boot
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- ==================== CONFIRM TAB ==================== -->
        <div v-show="activeTab === 'confirm'" class="tab-content">
          <h4 class="section-title">Review &amp; Create</h4>

          <!-- Resource usage estimation -->
          <div v-if="selectedNodeObj" class="resource-estimate-banner">
            <h5 class="resource-estimate-title">Estimated Resource Usage on <strong>{{ selectedNodeObj.node_name }}</strong></h5>
            <div class="resource-estimate-bars">
              <div class="res-estimate-item">
                <div class="res-estimate-label">
                  <span>CPU</span>
                  <span class="res-estimate-nums">{{ formData.cpu_sockets * formData.cpu_cores }} vCPUs / {{ selectedNodeObj.cpu_cores }} cores</span>
                </div>
                <div class="res-estimate-track">
                  <div class="res-estimate-existing" :style="{ width: Math.min(selectedNodeObj.cpu_usage || 0, 100) + '%' }"></div>
                  <div class="res-estimate-new" :style="{ width: Math.min(cpuAllocationPercent, 100 - (selectedNodeObj.cpu_usage || 0)) + '%' }"></div>
                </div>
                <div class="res-estimate-pct">{{ Math.round(cpuAllocationPercent) }}% allocated</div>
              </div>
              <div class="res-estimate-item">
                <div class="res-estimate-label">
                  <span>RAM</span>
                  <span class="res-estimate-nums">{{ (formData.memory / 1024).toFixed(1) }} GB / {{ formatBytes(selectedNodeObj.memory_total) }}</span>
                </div>
                <div class="res-estimate-track">
                  <div class="res-estimate-existing" :style="{ width: Math.min(nodeMemUsedPercent, 100) + '%' }"></div>
                  <div class="res-estimate-new" :style="{ width: Math.min(memAllocationPercent, 100 - nodeMemUsedPercent) + '%' }"></div>
                </div>
                <div class="res-estimate-pct">{{ Math.round(memAllocationPercent) }}% of node RAM</div>
              </div>
              <div class="res-estimate-item">
                <div class="res-estimate-label">
                  <span>Disk</span>
                  <span class="res-estimate-nums">{{ totalDiskSize }} GB requested</span>
                </div>
                <div class="res-estimate-track">
                  <div class="res-estimate-existing" :style="{ width: Math.min(diskUsedPercent, 100) + '%' }"></div>
                  <div class="res-estimate-new" :style="{ width: Math.min(diskAllocationPercent, 100 - diskUsedPercent) + '%' }"></div>
                </div>
                <div class="res-estimate-pct">{{ Math.round(diskAllocationPercent) }}% of selected pool</div>
              </div>
            </div>
            <div class="res-estimate-legend">
              <span class="legend-item"><span class="legend-dot existing"></span> Currently used</span>
              <span class="legend-item"><span class="legend-dot new"></span> This VM</span>
            </div>
          </div>

          <div class="summary-grid">
            <!-- General -->
            <div class="summary-section">
              <h5 class="summary-section-title">General</h5>
              <table class="summary-table">
                <tr><td>Name</td><td>{{ formData.name || '—' }}</td></tr>
                <tr><td>Hostname</td><td>{{ formData.hostname || '—' }}</td></tr>
                <tr v-if="formData.vmid"><td>VM ID</td><td>{{ formData.vmid }}</td></tr>
                <tr><td>OS</td><td>{{ formData.os_type || '—' }}</td></tr>
                <tr><td>Install method</td><td>{{ imageSource === 'iso' ? 'ISO' : 'Cloud Image' }}</td></tr>
                <tr v-if="parsedTags.length"><td>Tags</td><td>{{ parsedTags.join(', ') }}</td></tr>
              </table>
            </div>
            <!-- Hardware -->
            <div class="summary-section">
              <h5 class="summary-section-title">Hardware</h5>
              <table class="summary-table">
                <tr><td>vCPUs</td><td>{{ formData.cpu_sockets }} × {{ formData.cpu_cores }} = {{ formData.cpu_sockets * formData.cpu_cores }}</td></tr>
                <tr><td>CPU Type</td><td>{{ formData.cpu_type }}</td></tr>
                <tr><td>RAM</td><td>{{ formData.memory }} MB ({{ (formData.memory/1024).toFixed(1) }} GB)</td></tr>
                <tr v-if="formData.balloon_enabled"><td>Balloon min</td><td>{{ formData.balloon || 0 }} MB</td></tr>
                <tr><td>Machine</td><td>{{ formData.machine_type === 'q35' ? 'Q35 (PCIe)' : 'i440FX (PC)' }}</td></tr>
                <tr><td>BIOS</td><td>{{ formData.bios_type === 'ovmf' ? 'OVMF (UEFI)' : 'SeaBIOS' }}</td></tr>
                <tr><td>Agent</td><td>{{ formData.agent_enabled ? 'Yes' : 'No' }}</td></tr>
                <tr><td>Start at boot</td><td>{{ formData.onboot ? 'Yes' : 'No' }}</td></tr>
              </table>
            </div>
            <!-- Disks -->
            <div class="summary-section">
              <h5 class="summary-section-title">Disks</h5>
              <table class="summary-table">
                <tr v-for="(disk, idx) in disks" :key="idx">
                  <td>scsi{{ idx }}</td>
                  <td>{{ disk.storage }}:{{ disk.size }}GB {{ disk.format }} {{ disk.cache ? '(' + disk.cache + ')' : '' }}</td>
                </tr>
              </table>
            </div>
            <!-- Network -->
            <div class="summary-section">
              <h5 class="summary-section-title">Network</h5>
              <table class="summary-table">
                <tr v-for="(nic, idx) in nics" :key="idx">
                  <td>net{{ idx }}</td>
                  <td>{{ nic.model }} / {{ nic.bridge }}{{ nic.vlan ? ' VLAN ' + nic.vlan : '' }}{{ nic.macMode === 'custom' && nic.mac ? ' / ' + nic.mac : ' / random MAC' }}</td>
                </tr>
              </table>
            </div>
            <!-- Cloud-Init -->
            <div class="summary-section">
              <h5 class="summary-section-title">Cloud-Init</h5>
              <table class="summary-table">
                <tr><td>Username</td><td>{{ formData.username || '—' }}</td></tr>
                <tr><td>IP</td><td>{{ useDHCP ? 'DHCP' : (formData.ip_address + '/' + formData.netmask) }}</td></tr>
                <tr v-if="!useDHCP && formData.gateway"><td>Gateway</td><td>{{ formData.gateway }}</td></tr>
                <tr><td>SSH key</td><td>{{ formData.ssh_key ? 'Provided' : 'None' }}</td></tr>
                <tr><td>Upgrade on boot</td><td>{{ formData.upgrade_packages ? 'Yes' : 'No' }}</td></tr>
              </table>
            </div>
          </div>

          <!-- CLI command preview -->
          <div class="form-section">
            <div class="section-header-with-action">
              <h5 class="subsection-title">Equivalent CLI Command</h5>
              <button type="button" class="btn btn-sm btn-outline" @click="copyCliCommand">Copy</button>
            </div>
            <pre class="cli-preview">{{ generatedCliCommand }}</pre>
          </div>

          <!-- Create Actions -->
          <div class="form-actions" style="padding-top:1.5rem">
            <button type="submit" class="btn btn-primary btn-lg" :disabled="creating || vmIdStatus === 'taken'">
              <span v-if="creating">
                <span class="btn-spinner"></span>
                Creating VM...
              </span>
              <span v-else>Create Virtual Machine</span>
            </button>
            <router-link to="/vms" class="btn btn-outline">Cancel</router-link>
          </div>
        </div>

        <!-- Bottom nav (prev/next + validate) -->
        <div class="tab-nav-footer">
          <button type="button" class="btn btn-outline" @click="prevTab" :disabled="tabIndex === 0">
            &#8592; Back
          </button>
          <span class="tab-position">Step {{ tabIndex + 1 }} of {{ tabs.length }}</span>
          <button
            v-if="tabIndex < tabs.length - 1"
            type="button"
            class="btn btn-primary"
            @click="nextTabWithValidation"
          >
            Next &#8594;
          </button>
        </div>

      </form>
    </div>
  </div>

  <!-- Progress Modal -->
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
            <div v-else-if="progressData.status === 'running'" class="success-icon">&#10003;</div>
            <div v-else-if="progressData.status === 'error'" class="error-icon">&#10005;</div>

            <h4 class="progress-vm-name">{{ progressData.name }}</h4>
            <div class="progress-steps">
              <div class="current-step">{{ progressData.status_message || 'Initializing deployment...' }}</div>
            </div>

            <div v-if="uploadProgress > 0 && uploadProgress < 100" class="progress-bar-container">
              <div class="progress-bar-background">
                <div class="progress-bar-fill" :style="{ width: uploadProgress + '%' }">
                  <span class="progress-bar-text">{{ uploadProgress }}%</span>
                </div>
              </div>
            </div>

            <div v-if="progressData.vmid" class="progress-vmid">VM ID: {{ progressData.vmid }}</div>
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
import { rules, validate } from '@/utils/formValidation'

export default {
  name: 'CreateVM',
  setup() {
    const router = useRouter()
    const toast = useToast()

    // ---------- Tabs ----------
    const tabs = [
      { id: 'general',  label: 'General'    },
      { id: 'hardware', label: 'Hardware'   },
      { id: 'storage',  label: 'Storage'    },
      { id: 'network',  label: 'Network'    },
      { id: 'cloudinit',label: 'Cloud-Init' },
      { id: 'confirm',  label: 'Confirm'    },
    ]
    const activeTab = ref('general')
    const tabErrors = ref({})
    // Per-step inline validation errors
    const stepErrors = ref({ general: {}, hardware: {}, storage: {}, network: {}, cloudinit: {} })

    const tabIndex = computed(() => tabs.findIndex(t => t.id === activeTab.value))

    const goToTab = (i) => { activeTab.value = tabs[i].id }
    const prevTab = () => { if (tabIndex.value > 0) activeTab.value = tabs[tabIndex.value - 1].id }

    // Validate current step, then advance
    const nextTabWithValidation = () => {
      const errs = validateStep(activeTab.value)
      if (errs.length > 0) {
        errs.forEach(e => toast.error(e))
        return
      }
      if (tabIndex.value < tabs.length - 1) activeTab.value = tabs[tabIndex.value + 1].id
    }

    // ---------- Hardware Presets ----------
    const hwPresets = [
      { name: 'Micro',  cpu: 1, memGb: 0.5, diskGb: 8  },
      { name: 'Small',  cpu: 1, memGb: 1,   diskGb: 20  },
      { name: 'Medium', cpu: 2, memGb: 2,   diskGb: 40  },
      { name: 'Large',  cpu: 4, memGb: 8,   diskGb: 80  },
      { name: 'XLarge', cpu: 8, memGb: 16,  diskGb: 160 },
    ]
    const activePreset = ref('')

    const applyPreset = (preset) => {
      activePreset.value = preset.name
      formData.value.cpu_sockets = 1
      formData.value.cpu_cores   = preset.cpu
      formData.value.memory      = Math.round(preset.memGb * 1024)
      if (disks.value.length > 0) disks.value[0].size = preset.diskGb
    }

    // ---------- VM ID check ----------
    const vmIdStatus = ref('')
    let vmIdCheckTimer = null
    const debouncedCheckVmId = () => {
      clearTimeout(vmIdCheckTimer)
      if (!formData.value.vmid || !selectedHostId.value) { vmIdStatus.value = ''; return }
      vmIdStatus.value = 'checking'
      vmIdCheckTimer = setTimeout(async () => {
        try {
          const resp = await api.pveNode.clusterResources(selectedHostId.value)
          const resources = resp.data || []
          const taken = resources.some(r => r.vmid === formData.value.vmid)
          vmIdStatus.value = taken ? 'taken' : 'free'
        } catch {
          vmIdStatus.value = ''
        }
      }, 500)
    }

    // ---------- Tags ----------
    const tagInputValue = ref('')
    const parsedTags = ref([])
    const TAG_COLORS = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#ef4444','#06b6d4','#ec4899','#6366f1']
    const tagColor = (tag) => TAG_COLORS[tag.charCodeAt(0) % TAG_COLORS.length]

    const addTag = () => {
      const raw = tagInputValue.value.replace(/,/g, '').trim()
      if (raw && !parsedTags.value.includes(raw)) parsedTags.value.push(raw)
      tagInputValue.value = ''
    }
    const removeTag = (idx) => parsedTags.value.splice(idx, 1)
    const removeLastTagOnBackspace = () => {
      if (!tagInputValue.value && parsedTags.value.length) parsedTags.value.pop()
    }
    watch(parsedTags, (tags) => { formData.value.tags = tags.join(';') }, { deep: true })

    // ---------- Disks ----------
    const disks = ref([{ storage: '', size: 20, format: 'qcow2', cache: '', discard: false, ssd: false, backup: true, replicate: false, iothread: false }])
    const addDisk = () => {
      if (disks.value.length < 8) {
        disks.value.push({ storage: selectedStorage.value || '', size: 20, format: 'qcow2', cache: '', discard: false, ssd: false, backup: true, replicate: false, iothread: false })
      }
    }
    const removeDisk = (idx) => { if (idx > 0) disks.value.splice(idx, 1) }

    // Watch disk[0].size changes to reset active preset if user types manually
    watch(() => disks.value[0]?.size, () => { activePreset.value = '' })

    // ---------- NICs ----------
    const nics = ref([{ model: 'virtio', bridge: '', vlan: null, mac: '', macMode: 'random', macError: '', rate: null, firewall: false, linkdown: false }])
    const addNic = () => {
      if (nics.value.length < 8) {
        nics.value.push({ model: 'virtio', bridge: selectedBridge.value || '', vlan: null, mac: '', macMode: 'random', macError: '', rate: null, firewall: false, linkdown: false })
      }
    }
    const removeNic = (idx) => { if (idx > 0) nics.value.splice(idx, 1) }

    // ---------- Bridge VLAN support ----------
    const bridgeSupportsVlan = (net) => {
      return net.bridge_vlan_aware || net.vlan_aware || false
    }
    const nicBridgeSupportsVlan = (nic) => {
      const net = networkList.value.find(n => n.iface === nic.bridge)
      return net ? bridgeSupportsVlan(net) : false
    }

    // ---------- MAC validation ----------
    const macRegex = /^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/
    const validateMac = (nic) => {
      if (nic.macMode === 'custom' && nic.mac && !macRegex.test(nic.mac)) {
        nic.macError = 'Invalid MAC address format (AA:BB:CC:DD:EE:FF)'
      } else {
        nic.macError = ''
      }
    }

    // ---------- Storage type icons ----------
    const storageTypeIcon = (type) => {
      const icons = {
        dir: '📁', lvm: '💽', lvmthin: '💽', zfspool: '🗄️',
        nfs: '🌐', cifs: '🌐', rbd: '☁️', sheepdog: '☁️',
        btrfs: '📁', zfs: '🗄️',
      }
      return icons[type] || '💾'
    }

    // ---------- State ----------
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
    const loadingNodes = ref(false)
    const loadingStorage = ref(false)
    const loadingNetwork = ref(false)
    const creating = ref(false)
    const useDHCP = ref(true)
    const showProgressModal = ref(false)
    const progressData = ref({ name: '', status: 'creating', status_message: '', error_message: '', vmid: null })
    let progressInterval = null

    // ---------- Form data ----------
    const formData = ref({
      name: '', hostname: '', proxmox_host_id: null, node_id: null, vmid: null,
      iso_id: null, cloud_image_id: null, os_type: '', description: '', tags: '',
      // System
      machine_type: 'pc', bios_type: 'seabios', tpm_enabled: false,
      scsihw: 'virtio-scsi-pci', vga_type: 'std', boot_order: 'cdn',
      agent_enabled: true, kvm: true, acpi: true, tablet: true, onboot: true,
      protection: false, hotplug: null,
      startup_order: null, startup_up: null, startup_down: null,
      // CPU
      cpu_sockets: 1, cpu_cores: 2, cpu_type: 'x86-64-v2-AES', cpu_flags: '',
      cpu_limit: null, cpu_units: 1024, numa_enabled: false, numa_nodes: 1,
      // Memory
      memory: 2048, balloon_enabled: false, balloon: null, shares: null, hugepages: '',
      // Storage
      storage: '', iso_storage: '', disk_size: 20,
      // Network
      network_bridge: '', vlan_tag: null, network_interfaces: [],
      // Cloud-init
      username: 'administrator', password: '', ssh_key: '',
      ip_address: '', gateway: '', netmask: '24', dns_servers: '8.8.8.8,8.8.4.4',
      searchdomain: '', upgrade_packages: false,
    })

    // Reset active preset when user manually changes CPU/memory (must be after formData declaration)
    watch(() => formData.value.cpu_cores, () => { activePreset.value = '' })
    watch(() => formData.value.memory, () => { activePreset.value = '' })

    // ---------- Selected node object (for summary) ----------
    const selectedNodeObj = computed(() => {
      return nodes.value.find(n => n.id === formData.value.node_id) || null
    })

    // ---------- Resource estimation ----------
    const cpuAllocationPercent = computed(() => {
      const node = selectedNodeObj.value
      if (!node || !node.cpu_cores) return 0
      return ((formData.value.cpu_sockets * formData.value.cpu_cores) / node.cpu_cores) * 100
    })

    const nodeMemUsedPercent = computed(() => {
      const node = selectedNodeObj.value
      if (!node || !node.memory_total) return 0
      return Math.round(((node.memory_total - (node.memory_free || 0)) / node.memory_total) * 100)
    })

    const memAllocationPercent = computed(() => {
      const node = selectedNodeObj.value
      if (!node || !node.memory_total) return 0
      return ((formData.value.memory * 1024 * 1024) / node.memory_total) * 100
    })

    const totalDiskSize = computed(() => disks.value.reduce((s, d) => s + (d.size || 0), 0))

    const diskUsedPercent = computed(() => {
      const pool = storageList.value.find(s => s.storage === selectedStorage.value)
      if (!pool || !pool.total) return 0
      return Math.round(((pool.total - (pool.available || 0)) / pool.total) * 100)
    })

    const diskAllocationPercent = computed(() => {
      const pool = storageList.value.find(s => s.storage === selectedStorage.value)
      if (!pool || !pool.total) return 0
      return ((totalDiskSize.value * 1024 * 1024 * 1024) / pool.total) * 100
    })

    // ---------- Computed sorted lists ----------
    const sortedStorageList = computed(() =>
      [...storageList.value]
        .filter(s =>
          s.active &&                    // must be mounted/accessible on this node
          s.type !== 'pbs' &&            // PBS is backup-only, never a VM disk target
          (!s.content || s.content.includes('images') || s.content.includes('rootdir'))
        )
        .sort((a, b) => a.storage.localeCompare(b.storage, undefined, { numeric: true, sensitivity: 'base' }))
    )
    const sortedISOStorageList = computed(() =>
      [...storageList.value]
        .filter(s => s.content && s.content.includes('iso'))
        .sort((a, b) => a.storage.localeCompare(b.storage, undefined, { numeric: true, sensitivity: 'base' }))
    )
    const sortedNetworkList = computed(() =>
      [...networkList.value]
        .filter(n => n.type === 'bridge' || n.iface?.startsWith('vmbr'))
        .sort((a, b) => a.iface.localeCompare(b.iface, undefined, { numeric: true, sensitivity: 'base' }))
    )

    const storageHasSpace = (storage) => {
      const needed = (disks.value[0]?.size || 0) * 1024 * 1024 * 1024
      return (storage.available || 0) >= needed
    }

    // ---------- CLI command preview ----------
    const generatedCliCommand = computed(() => {
      const parts = [`qm create ${formData.value.vmid || '<VMID>'}`]
      parts.push(`--name "${formData.value.name || 'vm'}"`)
      parts.push(`--memory ${formData.value.memory}`)
      parts.push(`--cores ${formData.value.cpu_cores}`)
      parts.push(`--sockets ${formData.value.cpu_sockets}`)
      parts.push(`--cpu ${formData.value.cpu_type}`)
      parts.push(`--machine ${formData.value.machine_type}`)
      parts.push(`--bios ${formData.value.bios_type}`)
      parts.push(`--scsihw ${formData.value.scsihw}`)
      disks.value.forEach((d, i) => {
        if (d.storage && d.size) {
          parts.push(`--scsi${i} ${d.storage}:${d.size}${d.format ? ',format=' + d.format : ''}${d.cache ? ',cache=' + d.cache : ''}${d.discard ? ',discard=on' : ''}${d.iothread ? ',iothread=1' : ''}`)
        }
      })
      nics.value.forEach((n, i) => {
        let netstr = `model=${n.model},bridge=${n.bridge || 'vmbr0'}`
        if (n.vlan) netstr += `,tag=${n.vlan}`
        if (n.macMode === 'custom' && n.mac) netstr += `,macaddr=${n.mac}`
        if (n.firewall) netstr += ',firewall=1'
        if (n.rate) netstr += `,rate=${n.rate}`
        parts.push(`--net${i} ${netstr}`)
      })
      if (formData.value.onboot) parts.push('--onboot 1')
      if (formData.value.agent_enabled) parts.push('--agent enabled=1')
      if (formData.value.tags) parts.push(`--tags "${formData.value.tags}"`)
      return parts.join(' \\\n  ')
    })

    const copyCliCommand = () => {
      navigator.clipboard.writeText(generatedCliCommand.value).then(() => toast.success('CLI command copied!'))
    }

    // ---------- Per-field validation ----------
    const fieldErrors = ref({
      vmid: '', name: '', hostname: '', memory: '', cpu_cores: '', cpu_sockets: '',
      disk_size: '', ip_address: '', password: '', username: '',
    })

    const validateField = (field, value, rulesArr) => {
      const result = validate(value, rulesArr)
      fieldErrors.value[field] = result === true ? '' : result
      return result === true
    }

    // ---------- Per-step validation ----------
    const validateStep = (step) => {
      const errors = []
      stepErrors.value[step] = {}

      if (step === 'general') {
        if (!selectedHostId.value) {
          stepErrors.value.general.host = 'Please select a Proxmox datacenter'
          errors.push('Please select a Proxmox datacenter')
        }
        if (!formData.value.node_id) {
          stepErrors.value.general.node = 'Please select a node'
          errors.push('Please select a node')
        }
        const nameErr = validate(formData.value.name, [rules.required, rules.vmName])
        if (nameErr !== true) { fieldErrors.value.name = nameErr; errors.push(`VM Name: ${nameErr}`) }
        const hostnameErr = validate(formData.value.hostname, [rules.required, rules.hostname])
        if (hostnameErr !== true) { fieldErrors.value.hostname = hostnameErr; errors.push(`Hostname: ${hostnameErr}`) }
        if (!formData.value.os_type) {
          stepErrors.value.general.os = 'Please select an operating system'
          errors.push('Operating system must be selected')
        }
        if (vmIdStatus.value === 'taken') errors.push(`VM ID ${formData.value.vmid} is already in use`)
      }

      if (step === 'hardware') {
        const memErr = validate(formData.value.memory, [rules.required, rules.intRange(512, 4194304)])
        if (memErr !== true) { fieldErrors.value.memory = memErr; errors.push(`Memory: ${memErr}`) }
        const coresErr = validate(formData.value.cpu_cores, [rules.required, rules.intRange(1, 512)])
        if (coresErr !== true) { fieldErrors.value.cpu_cores = coresErr; errors.push(`CPU cores: ${coresErr}`) }
        const socketsErr = validate(formData.value.cpu_sockets, [rules.required, rules.intRange(1, 16)])
        if (socketsErr !== true) { fieldErrors.value.cpu_sockets = socketsErr; errors.push(`CPU sockets: ${socketsErr}`) }
      }

      if (step === 'storage') {
        if (!selectedStorage.value) {
          stepErrors.value.storage.pool = 'Please select a storage pool'
          errors.push('Storage pool must be selected')
        }
        const diskErr = validate(disks.value[0]?.size, [rules.required, rules.positiveInt])
        if (diskErr !== true) { fieldErrors.value.disk_size = diskErr; errors.push(`Primary disk: ${diskErr}`) }
      }

      if (step === 'network') {
        if (!selectedBridge.value && nics.value[0] && !nics.value[0].bridge) {
          stepErrors.value.network.bridge = 'Please select a network bridge'
          errors.push('Network bridge must be selected')
        }
        nics.value.forEach((nic, i) => {
          if (nic.macMode === 'custom' && nic.mac && !macRegex.test(nic.mac)) {
            errors.push(`net${i}: invalid MAC address format`)
          }
        })
      }

      if (step === 'cloudinit') {
        const userErr = validate(formData.value.username, [rules.required])
        if (userErr !== true) { fieldErrors.value.username = userErr; errors.push(`Username: ${userErr}`) }
        const pwErr = validate(formData.value.password, [rules.required, rules.password(8)])
        if (pwErr !== true) { fieldErrors.value.password = pwErr; errors.push(`Password: ${pwErr}`) }
        if (!useDHCP.value) {
          const ipErr = validate(formData.value.ip_address, [rules.required, rules.ipOrCidr])
          if (ipErr !== true) { fieldErrors.value.ip_address = ipErr; errors.push(`IP address: ${ipErr}`) }
        }
      }

      return errors
    }

    // ---------- Full form validation ----------
    const validateForm = () => {
      const allErrors = []
      for (const tab of tabs.slice(0, -1)) {
        const errs = validateStep(tab.id)
        if (errs.length) { tabErrors.value[tab.id] = true; allErrors.push(...errs) }
        else { tabErrors.value[tab.id] = false }
      }
      return allErrors
    }

    // ---------- API calls ----------
    const loadHosts = async () => {
      try {
        const r = await api.proxmox.listHosts()
        hosts.value = r.data.filter(h => h.is_active)
      } catch (e) { console.error(e) }
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
      vmIdStatus.value = ''

      loadingNodes.value = true
      try {
        const r = await api.proxmox.listNodes(hostId)
        nodes.value = r.data
      } catch (e) {
        toast.error('Failed to load nodes')
      } finally {
        loadingNodes.value = false
      }
    }

    const selectNode = async (nodeId) => {
      formData.value.node_id = nodeId
      selectedStorage.value = ''
      selectedBridge.value = ''
      formData.value.storage = ''
      formData.value.iso_storage = ''
      await Promise.all([loadStorage(nodeId), loadNetwork(nodeId)])
    }

    const loadStorage = async (nodeId) => {
      loadingStorage.value = true
      try {
        const r = await api.proxmox.getNodeStorage(nodeId)
        storageList.value = r.data.storage || []
        const first = storageList.value.find(s => s.enabled && s.active && s.content?.includes('images'))
          || storageList.value.find(s => s.enabled && s.active)
          || storageList.value[0]
        if (first) {
          selectedStorage.value = first.storage
          formData.value.storage = first.storage
          disks.value[0].storage = first.storage
        }
        const isoFirst = storageList.value.find(s => s.content?.includes('iso') && s.enabled && s.active)
        if (isoFirst) formData.value.iso_storage = isoFirst.storage
      } catch (e) {
        toast.error('Failed to load storage pools')
      } finally {
        loadingStorage.value = false
      }
    }

    const loadNetwork = async (nodeId) => {
      loadingNetwork.value = true
      try {
        const r = await api.proxmox.getNodeNetwork(nodeId)
        networkList.value = r.data.network || []
        const firstBridge = networkList.value.find(n => (n.type === 'bridge' || n.iface?.startsWith('vmbr')) && n.active) || networkList.value[0]
        if (firstBridge) {
          selectedBridge.value = firstBridge.iface
          formData.value.network_bridge = firstBridge.iface
          nics.value[0].bridge = firstBridge.iface
        }
      } catch (e) {
        toast.error('Failed to load network interfaces')
      } finally {
        loadingNetwork.value = false
      }
    }

    const selectStorage = (name) => {
      const s = storageList.value.find(s => s.storage === name)
      if (s && s.enabled && s.active) {
        selectedStorage.value = name
        formData.value.storage = name
      }
    }

    const selectBridge = (name) => {
      const b = networkList.value.find(n => n.iface === name)
      if (b && b.active) {
        selectedBridge.value = name
        formData.value.network_bridge = name
        nics.value[0].bridge = name
      }
    }

    const getStorageUsagePercent = (s) => {
      if (!s.total || s.total === 0) return 0
      return Math.round(((s.total - (s.available || 0)) / s.total) * 100)
    }

    const loadISOs = async () => {
      try { isos.value = (await api.isos.list()).data } catch (e) { console.error(e) }
    }
    const loadCloudImages = async () => {
      try { cloudImages.value = (await api.cloudImages.list()).data } catch (e) { console.error(e) }
    }

    // ---------- Progress polling ----------
    const pollProgress = async (vmId) => {
      try {
        const r = await api.vms.getProgress(vmId)
        progressData.value = r.data
        if (['running', 'stopped', 'error'].includes(r.data.status)) {
          clearInterval(progressInterval); progressInterval = null
        }
      } catch (e) { console.error(e) }
    }

    const closeProgressModal = () => {
      showProgressModal.value = false
      if (progressInterval) { clearInterval(progressInterval); progressInterval = null }
      if (progressData.value.status === 'running') router.push('/vms')
    }

    const uploadProgress = computed(() => {
      const m = (progressData.value.status_message || '').match(/(\d+)%/)
      return m ? parseInt(m[1]) : 0
    })

    // ---------- Create ----------
    const createVM = async () => {
      const errors = validateForm()
      if (errors.length) { errors.slice(0, 3).forEach(e => toast.error(e)); return }

      creating.value = true
      try {
        const payload = {
          name: formData.value.name,
          hostname: formData.value.hostname,
          proxmox_host_id: formData.value.proxmox_host_id,
          node_id: formData.value.node_id,
          iso_id: imageSource.value === 'iso' ? formData.value.iso_id : null,
          cloud_image_id: imageSource.value === 'cloud_image' ? formData.value.cloud_image_id : null,
          os_type: formData.value.os_type,
          cpu_sockets: formData.value.cpu_sockets,
          cpu_cores: formData.value.cpu_cores,
          cpu_type: formData.value.cpu_type || 'x86-64-v2-AES',
          cpu_flags: formData.value.cpu_flags || null,
          cpu_limit: formData.value.cpu_limit || null,
          cpu_units: formData.value.cpu_units || 1024,
          numa_enabled: formData.value.numa_enabled || false,
          memory: formData.value.memory,
          balloon: formData.value.balloon_enabled ? (formData.value.balloon || null) : null,
          shares: formData.value.shares || null,
          disk_size: disks.value[0].size,
          storage: selectedStorage.value || null,
          iso_storage: formData.value.iso_storage || null,
          scsihw: formData.value.scsihw || 'virtio-scsi-pci',
          bios_type: formData.value.bios_type || 'seabios',
          machine_type: formData.value.machine_type || 'pc',
          vga_type: formData.value.vga_type || 'std',
          boot_order: formData.value.boot_order || 'cdn',
          onboot: formData.value.onboot !== undefined ? formData.value.onboot : true,
          tablet: formData.value.tablet !== undefined ? formData.value.tablet : true,
          hotplug: formData.value.hotplug || null,
          protection: formData.value.protection || false,
          kvm: formData.value.kvm !== undefined ? formData.value.kvm : true,
          acpi: formData.value.acpi !== undefined ? formData.value.acpi : true,
          agent_enabled: formData.value.agent_enabled !== undefined ? formData.value.agent_enabled : true,
          network_bridge: selectedBridge.value || nics.value[0]?.bridge || null,
          vlan_tag: nics.value[0]?.vlan || null,
          network_interfaces: null,
          username: formData.value.username,
          password: formData.value.password,
          ssh_key: formData.value.ssh_key || null,
          description: formData.value.description || null,
          tags: formData.value.tags || null,
        }

        if (useDHCP.value) {
          payload.ip_address = null; payload.gateway = null; payload.netmask = null; payload.dns_servers = null
        } else {
          payload.ip_address = formData.value.ip_address || null
          payload.gateway = formData.value.gateway || null
          payload.netmask = formData.value.netmask || null
          payload.dns_servers = formData.value.dns_servers || null
        }

        const r = await api.vms.create(payload)
        showProgressModal.value = true
        progressData.value = { name: formData.value.name, status: 'creating', status_message: 'Initializing VM deployment...', error_message: '', vmid: null }
        const vmId = r.data.id
        progressInterval = setInterval(() => pollProgress(vmId), 1000)
        toast.success('VM creation started!')
      } catch (e) {
        console.error(e)
        if (e.response?.data?.detail) {
          if (Array.isArray(e.response.data.detail)) {
            e.response.data.detail.map(err => `${err.loc[err.loc.length - 1]}: ${err.msg}`).forEach(m => toast.error(m))
          } else {
            toast.error(`Error: ${e.response.data.detail}`)
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
      if (gb >= 1) return gb.toFixed(2) + ' GB'
      return (bytes / (1024 * 1024)).toFixed(0) + ' MB'
    }

    watch(useDHCP, (val) => {
      if (val) { formData.value.ip_address = ''; formData.value.gateway = ''; formData.value.netmask = '24'; formData.value.dns_servers = '8.8.8.8,8.8.4.4' }
    })
    watch(selectedStorage, (name) => {
      disks.value.forEach(d => { if (!d.storage) d.storage = name })
    })
    watch(selectedBridge, (name) => {
      nics.value.forEach(n => { if (!n.bridge) n.bridge = name })
    })

    onMounted(() => { loadHosts(); loadISOs(); loadCloudImages() })

    return {
      tabs, activeTab, tabErrors, stepErrors, tabIndex, goToTab, prevTab, nextTabWithValidation,
      hwPresets, activePreset, applyPreset,
      vmIdStatus, debouncedCheckVmId,
      tagInputValue, parsedTags, tagColor, addTag, removeTag, removeLastTagOnBackspace,
      disks, addDisk, removeDisk,
      nics, addNic, removeNic,
      bridgeSupportsVlan, nicBridgeSupportsVlan, validateMac,
      storageTypeIcon, storageHasSpace,
      hosts, nodes, isos, cloudImages, imageSource,
      storageList, networkList,
      sortedStorageList, sortedISOStorageList, sortedNetworkList,
      selectedHostId, selectedStorage, selectedBridge,
      loadingNodes, loadingStorage, loadingNetwork,
      creating, useDHCP,
      showProgressModal, progressData, uploadProgress, closeProgressModal,
      formData,
      selectedNodeObj,
      cpuAllocationPercent, nodeMemUsedPercent, memAllocationPercent,
      totalDiskSize, diskUsedPercent, diskAllocationPercent,
      selectDatacenter, selectNode, selectStorage, selectBridge,
      getStorageUsagePercent, formatBytes,
      createVM,
      generatedCliCommand, copyCliCommand,
      fieldErrors, validateField, rules, validate,
    }
  }
}
</script>

<style scoped>
/* ---- Layout ---- */
.create-vm-page { max-width: 1100px; margin: 0 auto; }
.card-subtitle { color: var(--text-secondary); margin: 0.25rem 0 0; font-size: 0.9rem; }
.create-vm-form { padding: 0 1.5rem 1.5rem; }

/* ---- Step Progress Bar ---- */
.step-progress {
  display: flex;
  align-items: flex-start;
  padding: 1.25rem 1.5rem 0;
  overflow-x: auto;
  scrollbar-width: none;
  gap: 0;
}
.step-progress::-webkit-scrollbar { display: none; }

.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  min-width: 70px;
  position: relative;
  cursor: pointer;
}

.step-connector-before,
.step-connector-after {
  position: absolute;
  top: 14px;
  height: 2px;
  background: var(--border-color);
  z-index: 0;
  transition: background 0.3s;
}
.step-connector-before { right: 50%; width: 50%; }
.step-connector-after  { left:  50%; width: 50%; }

.step-done .step-connector-after,
.step-active .step-connector-before,
.step-done .step-connector-before { background: var(--primary-color); }

.step-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid var(--border-color);
  background: var(--card-bg, white);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  z-index: 1;
  transition: all 0.3s;
  color: var(--text-secondary);
  position: relative;
}
.step-active .step-circle {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: white;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.2);
}
.step-done .step-circle {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: white;
}
.step-error .step-circle {
  border-color: #ef4444;
  background: #ef4444;
  color: white;
}
.step-circle-icon { font-size: 0.8rem; }
.step-circle-num { font-size: 0.75rem; }

.step-label {
  margin-top: 0.4rem;
  font-size: 0.72rem;
  font-weight: 500;
  text-align: center;
  color: var(--text-secondary);
  white-space: nowrap;
}
.step-active .step-label { color: var(--primary-color); font-weight: 600; }
.step-done .step-label { color: var(--primary-color); }
.step-error .step-label { color: #ef4444; }

/* ---- Tab content ---- */
.tab-content { padding-top: 1.5rem; min-height: 400px; }

/* ---- Tab nav footer ---- */
.tab-nav-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 0 0.5rem;
  border-top: 1px solid var(--border-color);
  margin-top: 2rem;
}
.tab-position { color: var(--text-secondary); font-size: 0.875rem; }

/* ---- Sections ---- */
.form-section { margin-bottom: 1.75rem; padding-bottom: 1.75rem; border-bottom: 1px solid var(--border-color); }
.form-section:last-child { border-bottom: none; }
.section-title { font-size: 1.125rem; font-weight: 600; margin-bottom: 1.25rem; color: var(--text-primary); }
.subsection-title { font-size: 0.9375rem; font-weight: 600; color: var(--text-primary); margin: 0 0 0.875rem; }
.section-header-with-action { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.875rem; }
.info-banner { padding: 1rem 1.25rem; background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.2); border-radius: 0.5rem; color: var(--text-secondary); font-size: 0.9rem; }

/* ---- Hardware Presets ---- */
.preset-hint { font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.75rem; }
.preset-cards {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.preset-card {
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--background);
  min-width: 110px;
  text-align: center;
}
.preset-card:hover { border-color: var(--primary-color); transform: translateY(-1px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
.preset-selected { border-color: var(--primary-color) !important; background: linear-gradient(135deg, rgba(37,99,235,0.08), rgba(147,51,234,0.08)) !important; }
.preset-name { font-size: 1rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.4rem; }
.preset-specs { display: flex; flex-direction: column; gap: 0.15rem; }
.preset-spec { font-size: 0.75rem; color: var(--text-secondary); }

/* ---- VM ID input ---- */
.input-with-status { position: relative; }
.input-with-status .form-control { padding-right: 2rem; }
.status-icon { position: absolute; right: 0.6rem; top: 50%; transform: translateY(-50%); font-size: 1rem; }
.status-icon.free { color: #10b981; }
.status-icon.taken { color: #ef4444; }
.status-icon.checking { color: var(--text-secondary); animation: spin 1s linear infinite; display: inline-block; }
.input-ok { border-color: #10b981 !important; }
.input-error { border-color: #ef4444 !important; box-shadow: 0 0 0 2px rgba(239,68,68,0.15) !important; }
.error-text { color: #ef4444; }
.form-error-text { display: block; margin-top: 0.25rem; font-size: 0.78rem; color: #ef4444; }
.form-error-text::before { content: '\26A0 '; }

/* ---- Tag input ---- */
.tag-input-area {
  display: flex; flex-wrap: wrap; gap: 0.35rem; padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-color); border-radius: 0.375rem; cursor: text;
  min-height: 2.5rem; background: var(--background); align-items: center;
}
.tag-chip { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.15rem 0.6rem; border-radius: 9999px; color: white; font-size: 0.78rem; font-weight: 500; }
.tag-remove { background: none; border: none; color: rgba(255,255,255,0.8); cursor: pointer; padding: 0; font-size: 1rem; line-height: 1; }
.tag-remove:hover { color: white; }
.tag-text-input { border: none; outline: none; background: none; font-size: 0.875rem; flex: 1; min-width: 120px; color: var(--text-primary); }

/* ---- Node resource bars ---- */
.resource-bar-wrap { display: flex; align-items: center; gap: 0.35rem; flex: 1; }
.resource-bar { height: 6px; background: var(--border-color); border-radius: 3px; overflow: hidden; flex: 1; }
.resource-bar-fill { height: 100%; border-radius: 3px; }
.resource-bar-fill.cpu { background: #3b82f6; }
.resource-bar-fill.mem { background: #8b5cf6; }
.resource-pct { font-size: 0.72rem; color: var(--text-secondary); min-width: 2.5rem; text-align: right; }

/* ---- Storage ---- */
.storage-hint { font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.75rem; }
.storage-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; margin: 0.5rem 0; }
.storage-card {
  border: 2px solid var(--border-color); border-radius: 0.5rem; padding: 1rem;
  cursor: pointer; transition: all 0.2s; background: var(--background); position: relative;
}
.storage-card:hover { border-color: var(--primary-color); }
.storage-card.selected { border-color: var(--primary-color); background: linear-gradient(135deg, rgba(37,99,235,0.08), rgba(147,51,234,0.08)); }
.storage-card.disabled { opacity: 0.5; cursor: not-allowed; }
.storage-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.storage-name-row { display: flex; align-items: center; gap: 0.4rem; }
.storage-type-icon { font-size: 1.1rem; }
.storage-header h6 { margin: 0; font-size: 0.95rem; font-weight: 600; }
.storage-bar { width: 100%; height: 8px; background: var(--border-color); border-radius: 4px; overflow: hidden; margin-bottom: 0.5rem; }
.storage-bar-fill { height: 100%; background: linear-gradient(90deg, var(--primary-color), var(--secondary-color)); }
.storage-bar-danger { background: linear-gradient(90deg, #f59e0b, #ef4444) !important; }
.storage-stats { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary); }
.storage-stats-simple { font-size: 0.78rem; color: var(--text-secondary); margin-top: 0.35rem; }
.storage-insufficient { font-size: 0.72rem; color: #ef4444; margin-top: 0.25rem; font-weight: 500; }
.storage-badge { position: absolute; top: 0.5rem; right: 0.5rem; }

/* ---- Network ---- */
.network-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 0.875rem; margin-bottom: 1rem; }
.network-card { border: 2px solid var(--border-color); border-radius: 0.5rem; padding: 0.875rem; cursor: pointer; transition: all 0.2s; background: var(--background); }
.network-card:hover { border-color: var(--primary-color); }
.network-card.selected { border-color: var(--primary-color); background: linear-gradient(135deg, rgba(37,99,235,0.08), rgba(147,51,234,0.08)); }
.network-card.disabled { opacity: 0.5; cursor: not-allowed; }
.network-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.network-header h6 { margin: 0; font-size: 0.9rem; font-weight: 600; }
.network-badges { display: flex; gap: 0.35rem; flex-wrap: wrap; }
.network-details { display: flex; flex-direction: column; gap: 0.2rem; margin-top: 0.35rem; }
.net-detail { font-size: 0.78rem; color: var(--text-secondary); }
.net-detail-label { font-weight: 600; color: var(--text-primary); }
.net-vlan-aware { color: #0891b2; font-weight: 500; }
.vlan-optional { font-size: 0.75rem; color: var(--text-secondary); font-weight: 400; }

/* ---- MAC address ---- */
.mac-row { display: flex; flex-direction: column; gap: 0.4rem; }
.mac-toggle { display: flex; gap: 1rem; }
.mac-input { margin-top: 0.25rem; }

/* ---- Disk rows ---- */
.disk-row, .nic-row { border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; background: var(--background); }
.disk-row-header, .nic-row-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border-color); }
.disk-label, .nic-label { font-family: monospace; font-size: 0.875rem; font-weight: 600; color: var(--primary-color); }
.btn-icon-danger { background: none; border: 1px solid #ef4444; color: #ef4444; border-radius: 0.25rem; padding: 0.2rem 0.5rem; cursor: pointer; font-size: 0.8rem; }
.btn-icon-danger:hover { background: #fee2e2; }
.disk-options-row { display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid var(--border-color); }
.disk-option-check { display: flex; align-items: center; gap: 0.4rem; font-size: 0.83rem; color: var(--text-secondary); cursor: pointer; }

/* ---- Resource Estimate Banner ---- */
.resource-estimate-banner {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}
.resource-estimate-title { font-size: 0.9rem; font-weight: 600; margin: 0 0 1rem; color: var(--text-primary); }
.resource-estimate-bars { display: flex; flex-direction: column; gap: 0.875rem; }
.res-estimate-item { }
.res-estimate-label { display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.3rem; }
.res-estimate-nums { color: var(--text-secondary); }
.res-estimate-track {
  height: 12px; background: var(--border-color); border-radius: 6px; overflow: hidden;
  display: flex; position: relative;
}
.res-estimate-existing { height: 100%; background: #64748b; }
.res-estimate-new { height: 100%; background: var(--primary-color); opacity: 0.85; }
.res-estimate-pct { font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.2rem; text-align: right; }
.res-estimate-legend { display: flex; gap: 1.25rem; margin-top: 0.75rem; }
.legend-item { display: flex; align-items: center; gap: 0.4rem; font-size: 0.78rem; color: var(--text-secondary); }
.legend-dot { width: 12px; height: 12px; border-radius: 50%; }
.legend-dot.existing { background: #64748b; }
.legend-dot.new { background: var(--primary-color); }

/* ---- Summary ---- */
.summary-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.25rem; margin-bottom: 1.5rem; }
.summary-section { border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1rem; background: var(--background); }
.summary-section-title { font-size: 0.875rem; font-weight: 700; color: var(--primary-color); margin: 0 0 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.summary-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
.summary-table tr { border-bottom: 1px solid var(--border-color); }
.summary-table tr:last-child { border-bottom: none; }
.summary-table td { padding: 0.3rem 0; }
.summary-table td:first-child { color: var(--text-secondary); width: 40%; }
.summary-table td:last-child { font-weight: 500; color: var(--text-primary); word-break: break-all; }

/* ---- CLI preview ---- */
.cli-preview { background: #0f172a; color: #94a3b8; border-radius: 0.5rem; padding: 1rem 1.25rem; font-size: 0.8rem; line-height: 1.7; overflow-x: auto; white-space: pre-wrap; word-break: break-all; font-family: 'Courier New', monospace; }

/* ---- Datacenter / Node cards ---- */
.datacenter-cards, .node-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 1rem; margin-top: 0.5rem; }
.datacenter-card, .node-card { border: 2px solid var(--border-color); border-radius: 0.5rem; padding: 1rem; cursor: pointer; transition: all 0.2s; background: var(--background); }
.datacenter-card:hover, .node-card:hover { border-color: var(--primary-color); box-shadow: 0 4px 6px rgba(0,0,0,0.1); transform: translateY(-2px); }
.datacenter-card.selected, .node-card.selected { border-color: var(--primary-color); background: linear-gradient(135deg, rgba(37,99,235,0.08), rgba(147,51,234,0.08)); }
.datacenter-card { display: flex; align-items: center; gap: 1rem; }
.datacenter-icon { font-size: 2.5rem; flex-shrink: 0; }
.datacenter-info h5 { margin: 0 0 0.25rem; font-size: 1.125rem; }
.node-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.node-header h6 { margin: 0; font-size: 1rem; font-weight: 600; }
.node-resources { display: flex; flex-direction: column; gap: 0.45rem; }
.resource-item { display: flex; align-items: center; gap: 0.4rem; font-size: 0.83rem; }
.resource-icon { font-size: 0.9rem; }

/* ---- Loading ---- */
.loading-message { text-align: center; padding: 2rem; color: var(--text-secondary); }
.loading-spinner { width: 32px; height: 32px; border: 3px solid var(--border-color); border-top-color: var(--primary-color); border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 0.75rem; }

/* ---- Badges ---- */
.badge-sm { padding: 0.125rem 0.5rem; font-size: 0.75rem; }

/* ---- Buttons ---- */
.form-actions { display: flex; gap: 1rem; align-items: center; }
.btn-lg { padding: 0.75rem 2rem; font-size: 1rem; }
.btn-sm { padding: 0.3rem 0.75rem; font-size: 0.8rem; }
.btn-spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.4); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 0.5rem; }

/* ---- Radio group ---- */
.radio-group { display: flex; gap: 1.25rem; }
.radio-label { display: flex; align-items: center; gap: 0.4rem; cursor: pointer; font-size: 0.9rem; }

/* ---- Form helpers ---- */
.form-help { display: block; margin-top: 0.25rem; font-size: 0.8rem; color: var(--text-secondary); }

/* ---- Animations ---- */
@keyframes spin { to { transform: rotate(360deg); } }

/* ---- Progress Modal ---- */
.modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.progress-modal { background: var(--card-bg, white); border-radius: 0.5rem; max-width: 500px; width: 90%; box-shadow: var(--shadow-lg); }
.modal-header { padding: 1.5rem; border-bottom: 1px solid var(--border-color); }
.modal-header h3 { margin: 0; font-size: 1.5rem; font-weight: 600; }
.modal-body { padding: 2rem 1.5rem; }
.modal-footer { padding: 1rem 1.5rem; border-top: 1px solid var(--border-color); display: flex; justify-content: flex-end; }
.progress-container { text-align: center; }
.spinner-container { margin: 0 auto 1.5rem; width: 64px; height: 64px; }
.spinner { width: 64px; height: 64px; border: 4px solid var(--border-color); border-top-color: var(--primary-color); border-radius: 50%; animation: spin 1s linear infinite; }
.success-icon { width: 64px; height: 64px; line-height: 64px; margin: 0 auto 1.5rem; font-size: 3rem; color: #10b981; background: #d1fae5; border-radius: 50%; }
.error-icon { width: 64px; height: 64px; line-height: 64px; margin: 0 auto 1.5rem; font-size: 3rem; color: #ef4444; background: #fee2e2; border-radius: 50%; }
.progress-vm-name { font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem; }
.progress-steps { margin: 1.5rem 0; padding: 1.25rem; background: #f8fafc; border-radius: 0.5rem; border-left: 4px solid #3b82f6; }
.current-step { font-size: 1.1rem; font-weight: 500; color: #1e40af; line-height: 1.6; animation: pulse-text 2s ease-in-out infinite; }
@keyframes pulse-text { 0%,100%{opacity:1} 50%{opacity:0.7} }
.progress-vmid { font-size: 0.875rem; color: var(--text-secondary); font-family: monospace; margin-top: 0.5rem; }
.progress-error { margin-top: 1rem; padding: 1rem; background: #fee2e2; border: 1px solid #ef4444; border-radius: 0.375rem; color: #991b1b; text-align: left; }
.progress-bar-container { margin: 1.5rem 0; }
.progress-bar-background { width: 100%; height: 32px; background: #e5e7eb; border-radius: 16px; overflow: hidden; }
.progress-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #2563eb); transition: width 0.3s; display: flex; align-items: center; justify-content: center; }
.progress-bar-text { color: white; font-weight: 600; font-size: 0.875rem; }
</style>
