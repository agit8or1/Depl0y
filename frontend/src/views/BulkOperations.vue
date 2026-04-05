<template>
  <div class="bulk-ops-view">
    <div class="page-header">
      <h1>Bulk Operations</h1>
      <p class="subtitle">Select VMs and run operations across many at once</p>
    </div>

    <div class="bulk-layout">
      <!-- ── LEFT: VM Selection Panel ── -->
      <div class="selection-panel">
        <div class="panel-header">
          <h2>VM Selection</h2>
          <span class="selected-badge">{{ selectedVms.length }} selected</span>
        </div>

        <!-- Filters -->
        <div class="filter-section">
          <input
            v-model="search"
            class="input"
            placeholder="Search by name, ID, IP..."
            @input="applyFilters"
          />
          <div class="filter-row">
            <select v-model="filterHost" class="select" @change="applyFilters">
              <option value="">All Hosts</option>
              <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
            </select>
            <select v-model="filterStatus" class="select" @change="applyFilters">
              <option value="">All States</option>
              <option value="running">Running</option>
              <option value="stopped">Stopped</option>
              <option value="paused">Paused</option>
            </select>
          </div>
          <div class="filter-row">
            <input v-model="filterTag" class="input" placeholder="Filter by tag..." @input="applyFilters" />
            <select v-model="filterNode" class="select" @change="applyFilters">
              <option value="">All Nodes</option>
              <option v-for="n in allNodes" :key="n" :value="n">{{ n }}</option>
            </select>
          </div>
        </div>

        <!-- Select actions -->
        <div class="select-actions">
          <button class="btn btn-xs btn-secondary" @click="selectAll">Select All</button>
          <button class="btn btn-xs btn-secondary" @click="selectFiltered">Select Filtered</button>
          <button class="btn btn-xs btn-secondary" @click="deselectAll">Deselect All</button>
        </div>

        <!-- VM list -->
        <div class="vm-list" v-if="!loadingVms">
          <div
            v-for="vm in filteredVms"
            :key="`${vm.host_id}-${vm.node}-${vm.vmid}`"
            class="vm-row"
            :class="{ selected: isSelected(vm) }"
            @click="toggleSelect(vm)"
          >
            <input
              type="checkbox"
              :checked="isSelected(vm)"
              @click.stop="toggleSelect(vm)"
              class="vm-check"
            />
            <span class="vm-status-dot" :class="vm.status"></span>
            <div class="vm-info">
              <span class="vm-name">{{ vm.name || `VM ${vm.vmid}` }}</span>
              <span class="vm-meta">{{ vm.node }} · ID {{ vm.vmid }}</span>
            </div>
            <span class="vm-host-badge">{{ hostName(vm.host_id) }}</span>
          </div>
          <div v-if="filteredVms.length === 0" class="empty-list">
            No VMs match filters
          </div>
        </div>
        <div v-else class="loading-state">Loading VMs...</div>

        <!-- Selected VMs chips -->
        <div class="selected-chips" v-if="selectedVms.length > 0">
          <div class="chips-header">
            <span>Selected ({{ selectedVms.length }})</span>
          </div>
          <div class="chips-list">
            <span
              v-for="vm in selectedVms"
              :key="`chip-${vm.host_id}-${vm.node}-${vm.vmid}`"
              class="vm-chip"
            >
              {{ vm.name || vm.vmid }}
              <button class="chip-remove" @click="deselectVm(vm)">×</button>
            </span>
          </div>
        </div>
      </div>

      <!-- ── RIGHT: Operations Panel ── -->
      <div class="operations-panel">
        <!-- Tab bar -->
        <div class="tab-bar">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="tab-btn"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <!-- ── Power Management Tab ── -->
        <div v-if="activeTab === 'power'" class="tab-content">
          <h3>Power Management</h3>
          <p class="tab-desc">Run power operations on all {{ selectedVms.length }} selected VMs.</p>

          <div class="option-row">
            <label class="option-label">Execution mode</label>
            <div class="toggle-group">
              <button :class="['toggle-btn', { active: execMode === 'parallel' }]" @click="execMode = 'parallel'">Parallel</button>
              <button :class="['toggle-btn', { active: execMode === 'sequential' }]" @click="execMode = 'sequential'">Sequential</button>
            </div>
          </div>

          <div class="option-row" v-if="execMode === 'sequential'">
            <label class="option-label">Delay between VMs (sec)</label>
            <input v-model.number="execDelay" type="range" min="0" max="30" class="slider" />
            <span class="slider-val">{{ execDelay }}s</span>
          </div>

          <div class="option-row">
            <label class="option-label">Skip already in target state</label>
            <input v-model="skipTargetState" type="checkbox" class="toggle-check" />
          </div>

          <div class="power-buttons">
            <button class="btn btn-success" :disabled="!hasSelection || executing" @click="runPower('start')">
              ▶ Start All
            </button>
            <button class="btn btn-warning" :disabled="!hasSelection || executing" @click="runPower('shutdown')">
              ⏹ Stop All (Graceful)
            </button>
            <button class="btn btn-danger" :disabled="!hasSelection || executing" @click="runPower('stop')">
              ⚡ Force Stop All
            </button>
            <button class="btn btn-secondary" :disabled="!hasSelection || executing" @click="runPower('reboot')">
              🔄 Reboot All
            </button>
          </div>
        </div>

        <!-- ── Snapshot Tab ── -->
        <div v-if="activeTab === 'snapshot'" class="tab-content">
          <h3>Snapshot Management</h3>

          <div class="form-section">
            <h4>Create Snapshots</h4>
            <div class="form-row">
              <label>Snapshot name template</label>
              <input v-model="snapTemplate" class="input" placeholder="bulk-{date}" />
              <p class="hint">Variables: <code>{vmid}</code> <code>{name}</code> <code>{date}</code></p>
            </div>
            <div class="form-row">
              <label>Description</label>
              <input v-model="snapDescription" class="input" placeholder="Bulk snapshot" />
            </div>
            <div class="form-row checkbox-row">
              <label>
                <input v-model="snapIncludeRam" type="checkbox" />
                Include RAM state
              </label>
            </div>
            <button class="btn btn-primary" :disabled="!hasSelection || executing" @click="runSnapshot">
              📷 Create Snapshots on {{ selectedVms.length }} VMs
            </button>
          </div>

          <div class="form-section danger-zone">
            <h4>Delete Old Snapshots</h4>
            <div class="form-row">
              <label>Delete snapshots older than</label>
              <div class="input-with-unit">
                <input v-model.number="snapDeleteDays" type="number" min="1" class="input input-sm" />
                <span>days</span>
              </div>
            </div>
            <button class="btn btn-danger" :disabled="!hasSelection || executing" @click="runDeleteSnapshots">
              🗑 Delete Old Snapshots on {{ selectedVms.length }} VMs
            </button>
          </div>
        </div>

        <!-- ── Config Update Tab ── -->
        <div v-if="activeTab === 'config'" class="tab-content">
          <h3>Config Update</h3>
          <p class="tab-desc">Update settings on all selected VMs. Leave blank to keep current value.</p>

          <!-- Preset selector -->
          <div class="cfg-preset-bar" v-if="cfgPresets.length > 0 || true">
            <div class="cfg-preset-controls">
              <select class="select" style="flex:1;" @change="loadCfgPreset($event.target.value); $event.target.value = ''">
                <option value="">Load preset…</option>
                <option v-for="p in cfgPresets" :key="p.name" :value="p.name">{{ p.name }}</option>
              </select>
              <button class="btn btn-xs btn-outline" @click="openSaveCfgPresetModal" title="Save current config as preset">
                Save Preset
              </button>
            </div>
          </div>

          <div class="form-section">
            <div class="form-row">
              <label>CPU Cores</label>
              <input v-model.number="cfgCores" type="number" min="1" max="256" class="input input-sm" placeholder="unchanged" />
            </div>
            <div class="form-row">
              <label>Memory (MB)</label>
              <input v-model.number="cfgMemory" type="number" min="64" class="input input-sm" placeholder="unchanged" />
            </div>
            <div class="form-row">
              <label>Add tags (comma-separated)</label>
              <input v-model="cfgTagsAdd" class="input" placeholder="env:prod, owner:ops" />
            </div>
            <div class="form-row">
              <label>Remove tags (comma-separated)</label>
              <input v-model="cfgTagsRemove" class="input" placeholder="old-tag, legacy" />
            </div>
            <div class="form-row">
              <label>QEMU Agent</label>
              <select v-model="cfgAgent" class="select">
                <option value="">unchanged</option>
                <option value="1">Enabled</option>
                <option value="0">Disabled</option>
              </select>
            </div>
            <div class="form-row">
              <label>Start at boot</label>
              <select v-model="cfgOnboot" class="select">
                <option value="">unchanged</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </div>
            <div class="form-row">
              <label>Balloon memory</label>
              <input v-model.number="cfgBalloon" type="number" min="0" class="input input-sm" placeholder="unchanged (MB)" />
            </div>
          </div>

          <div class="config-actions">
            <button class="btn btn-secondary" :disabled="!hasSelection || executing || previewLoading" @click="previewConfig">
              {{ previewLoading ? 'Loading...' : '👁 Preview Changes' }}
            </button>
            <button class="btn btn-primary" :disabled="!hasSelection || executing" @click="runConfig">
              ✔ Apply Config to {{ selectedVms.length }} VMs
            </button>
            <button
              v-if="cfgFailedVms.length > 0"
              class="btn btn-warning"
              :disabled="executing"
              @click="retryFailedConfig"
              title="Retry only failed VMs"
            >
              ↺ Retry {{ cfgFailedVms.length }} Failed
            </button>
          </div>

          <!-- Preview table with diff -->
          <div class="preview-table-wrap" v-if="configPreviewData.length > 0">
            <div class="preview-table-header">
              <h4>Preview — {{ configPreviewData.length }} VMs</h4>
              <div class="preview-legend">
                <span class="legend-item legend-change">Will change</span>
                <span class="legend-item legend-nochange">Already set</span>
                <span class="legend-item legend-error">Error</span>
              </div>
            </div>
            <table class="preview-table">
              <thead>
                <tr>
                  <th>VM</th>
                  <th>Node</th>
                  <th>Field</th>
                  <th>Current</th>
                  <th>New Value</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="row in configPreviewData" :key="`prev-${row.vmid}`">
                  <tr v-if="row.error" class="preview-row-error">
                    <td><strong>{{ row.vm_name || row.vmid }}</strong></td>
                    <td>{{ row.node }}</td>
                    <td colspan="3"><span class="preview-error">{{ row.error }}</span></td>
                    <td><span class="badge-preview badge-preview-error">Error</span></td>
                  </tr>
                  <tr v-else-if="!row.diff || Object.keys(row.diff).length === 0" class="preview-row-nochange">
                    <td><strong>{{ row.vm_name || row.vmid }}</strong></td>
                    <td>{{ row.node }}</td>
                    <td colspan="3"><span class="preview-nochange">All values already at target</span></td>
                    <td><span class="badge-preview badge-preview-skip">Already set</span></td>
                  </tr>
                  <template v-else>
                    <tr
                      v-for="(change, field, idx) in row.diff"
                      :key="`prev-${row.vmid}-${field}`"
                      class="preview-row-change"
                    >
                      <td v-if="idx === 0" :rowspan="Object.keys(row.diff).length"><strong>{{ row.vm_name || row.vmid }}</strong></td>
                      <td v-if="idx === 0" :rowspan="Object.keys(row.diff).length">{{ row.node }}</td>
                      <td class="preview-field">{{ field }}</td>
                      <td class="preview-from">{{ formatVal(change.from) }}</td>
                      <td class="preview-to">{{ formatVal(change.to) }}</td>
                      <td v-if="idx === 0" :rowspan="Object.keys(row.diff).length"><span class="badge-preview badge-preview-change">{{ Object.keys(row.diff).length }} change{{ Object.keys(row.diff).length !== 1 ? 's' : '' }}</span></td>
                    </tr>
                  </template>
                </template>
              </tbody>
            </table>
            <div class="preview-summary">
              {{ configPreviewData.filter(r => r.diff && Object.keys(r.diff).length > 0).length }} VMs will change ·
              {{ configPreviewData.filter(r => !r.error && (!r.diff || Object.keys(r.diff).length === 0)).length }} already set ·
              {{ configPreviewData.filter(r => r.error).length }} errors
            </div>
          </div>

          <!-- Save preset modal -->
          <div v-if="showSaveCfgPresetModal" class="modal-backdrop" @click.self="showSaveCfgPresetModal = false">
            <div class="mini-modal">
              <div class="mini-modal-header">
                <span>Save Config Preset</span>
                <button @click="showSaveCfgPresetModal = false" style="background:none;border:none;cursor:pointer;font-size:1.2rem;color:var(--text-muted);">×</button>
              </div>
              <div class="mini-modal-body">
                <input v-model="newCfgPresetName" type="text" class="input" placeholder="Preset name…" @keyup.enter="saveCfgPreset" />
              </div>
              <div class="mini-modal-footer">
                <button class="btn btn-secondary btn-xs" @click="showSaveCfgPresetModal = false">Cancel</button>
                <button class="btn btn-primary btn-xs" @click="saveCfgPreset" :disabled="!newCfgPresetName.trim()">Save</button>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Migrate Tab ── -->
        <div v-if="activeTab === 'migrate'" class="tab-content">
          <h3>Migrate VMs</h3>
          <p class="tab-desc">Migrate all selected VMs to a target node (sequential).</p>

          <div class="form-section">
            <div class="form-row">
              <label>Target Host</label>
              <select v-model="migrateHostId" class="select" @change="loadTargetNodes">
                <option value="">Select host...</option>
                <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
              </select>
            </div>
            <div class="form-row">
              <label>Target Node</label>
              <select v-model="migrateNode" class="select" :disabled="!migrateHostId">
                <option value="">Select node...</option>
                <option v-for="n in targetNodes" :key="n" :value="n">{{ n }}</option>
              </select>
            </div>
            <div class="form-row checkbox-row">
              <label>
                <input v-model="migrateOnline" type="checkbox" />
                Online migration (live, no downtime)
              </label>
            </div>
            <div class="form-row checkbox-row">
              <label>
                <input v-model="migrateLocalDisks" type="checkbox" />
                Migrate with local disks
              </label>
            </div>
          </div>

          <button class="btn btn-primary" :disabled="!hasSelection || !migrateNode || executing" @click="runMigrate">
            🚀 Migrate {{ selectedVms.length }} VMs to {{ migrateNode || '...' }}
          </button>
        </div>

        <!-- ── Scripts Tab ── -->
        <div v-if="activeTab === 'scripts'" class="tab-content">
          <h3>Automation Scripts</h3>

          <!-- Script selector -->
          <div class="script-list">
            <div
              v-for="script in scripts"
              :key="script.key"
              class="script-card"
              :class="{ active: activeScript === script.key }"
              @click="activeScript = script.key"
            >
              <span class="script-icon">{{ script.icon }}</span>
              <div class="script-info">
                <span class="script-name">{{ script.name }}</span>
                <span class="script-desc">{{ script.desc }}</span>
              </div>
            </div>
          </div>

          <!-- Script parameters -->
          <div class="script-params" v-if="activeScript">
            <!-- Cleanup Snapshots -->
            <template v-if="activeScript === 'cleanup-snapshots'">
              <h4>Cleanup Old Snapshots</h4>
              <div class="form-row">
                <label>Host</label>
                <select v-model="scriptHostId" class="select">
                  <option value="">Select host...</option>
                  <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
                </select>
              </div>
              <div class="form-row">
                <label>Older than (days)</label>
                <input v-model.number="cleanupDays" type="number" min="1" class="input input-sm" />
              </div>
            </template>

            <!-- Tag Compliance -->
            <template v-if="activeScript === 'tag-compliance'">
              <h4>Tag Compliance</h4>
              <div class="form-row">
                <label>Host</label>
                <select v-model="scriptHostId" class="select">
                  <option value="">Select host...</option>
                  <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
                </select>
              </div>
              <div class="form-row">
                <label>Required tags (comma-separated)</label>
                <input v-model="requiredTags" class="input" placeholder="environment, owner" />
              </div>
            </template>

            <!-- Resource Audit -->
            <template v-if="activeScript === 'resource-audit'">
              <h4>Resource Audit</h4>
              <div class="form-row">
                <label>Host</label>
                <select v-model="scriptHostId" class="select">
                  <option value="">Select host...</option>
                  <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
                </select>
              </div>
              <div class="form-row">
                <label>Flag CPU usage below (%)</label>
                <input v-model.number="auditCpuThreshold" type="number" min="1" max="100" class="input input-sm" />
              </div>
              <div class="form-row">
                <label>Flag RAM usage below (%)</label>
                <input v-model.number="auditRamThreshold" type="number" min="1" max="100" class="input input-sm" />
              </div>
            </template>

            <!-- Orphaned Disks -->
            <template v-if="activeScript === 'orphaned-disks'">
              <h4>Orphaned Disk Finder</h4>
              <div class="form-row">
                <label>Host</label>
                <select v-model="scriptHostId" class="select">
                  <option value="">Select host...</option>
                  <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
                </select>
              </div>
              <p class="hint">Scans all storage on all nodes for volumes not attached to any VM.</p>
            </template>

            <div class="script-run-row">
              <button class="btn btn-secondary" :disabled="!scriptHostId || scriptRunning" @click="runScript(true)">
                {{ scriptRunning ? 'Running...' : '👁 Preview (dry-run)' }}
              </button>
              <button
                v-if="activeScript !== 'orphaned-disks' && activeScript !== 'resource-audit'"
                class="btn btn-danger"
                :disabled="!scriptHostId || scriptRunning"
                @click="runScript(false)"
              >
                ⚡ Execute
              </button>
              <button
                v-if="activeScript === 'resource-audit' || activeScript === 'orphaned-disks'"
                class="btn btn-primary"
                :disabled="!scriptHostId || scriptRunning"
                @click="runScript(false)"
              >
                🔍 Run Audit
              </button>
            </div>

            <!-- Script Results -->
            <div class="script-results" v-if="scriptResults">
              <div class="results-header">
                <h4>Results</h4>
                <span class="results-meta" v-if="scriptResults.dry_run">Dry-run — no changes made</span>
                <button class="btn btn-xs btn-secondary" @click="downloadScriptReport">Download Report</button>
              </div>

              <!-- Cleanup Snapshots results -->
              <template v-if="activeScript === 'cleanup-snapshots' && scriptResults.findings">
                <p>Found {{ scriptResults.total_found }} old snapshots</p>
                <table class="results-table" v-if="scriptResults.findings.length > 0">
                  <thead><tr><th>VM</th><th>Snapshot</th><th>Age</th><th>Status</th></tr></thead>
                  <tbody>
                    <tr v-for="f in scriptResults.findings" :key="`${f.vmid}-${f.snapname}`">
                      <td>{{ f.vm_name }} ({{ f.vmid }})</td>
                      <td>{{ f.snapname }}</td>
                      <td>{{ ageLabel(f.snaptime) }}</td>
                      <td>
                        <span v-if="scriptResults.dry_run" class="badge badge-warning">Would delete</span>
                        <span v-else-if="f.deleted" class="badge badge-success">Deleted</span>
                        <span v-else-if="f.error" class="badge badge-error">{{ f.error }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </template>

              <!-- Tag Compliance results -->
              <template v-if="activeScript === 'tag-compliance' && scriptResults.findings">
                <p>{{ scriptResults.non_compliant_count }} non-compliant VMs</p>
                <table class="results-table" v-if="scriptResults.findings.length > 0">
                  <thead><tr><th>VM</th><th>Node</th><th>Missing Tags</th><th>Status</th></tr></thead>
                  <tbody>
                    <tr v-for="f in scriptResults.findings" :key="f.vmid">
                      <td>{{ f.vm_name }} ({{ f.vmid }})</td>
                      <td>{{ f.node }}</td>
                      <td>{{ f.missing_tags.join(', ') }}</td>
                      <td>
                        <span v-if="scriptResults.dry_run" class="badge badge-warning">Not compliant</span>
                        <span v-else-if="f.fixed" class="badge badge-success">Fixed</span>
                        <span v-else-if="f.error" class="badge badge-error">{{ f.error }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </template>

              <!-- Resource Audit results -->
              <template v-if="activeScript === 'resource-audit' && scriptResults.report">
                <p>{{ scriptResults.over_provisioned_count }} over-provisioned VMs found</p>
                <table class="results-table" v-if="scriptResults.report.length > 0">
                  <thead><tr><th>VM</th><th>Node</th><th>Cores</th><th>CPU Avg</th><th>RAM (MB)</th><th>RAM Avg</th></tr></thead>
                  <tbody>
                    <tr v-for="f in scriptResults.report" :key="f.vmid" :class="{ 'row-warn': f.over_provisioned_cpu || f.over_provisioned_ram }">
                      <td>{{ f.vm_name }}</td>
                      <td>{{ f.node }}</td>
                      <td>{{ f.allocated_cores }}</td>
                      <td :class="{ 'cell-warn': f.over_provisioned_cpu }">{{ f.cpu_avg_pct != null ? f.cpu_avg_pct + '%' : 'N/A' }}</td>
                      <td>{{ f.allocated_memory_mb }}</td>
                      <td :class="{ 'cell-warn': f.over_provisioned_ram }">{{ f.mem_avg_pct != null ? f.mem_avg_pct + '%' : 'N/A' }}</td>
                    </tr>
                  </tbody>
                </table>
              </template>

              <!-- Orphaned Disks results -->
              <template v-if="activeScript === 'orphaned-disks' && scriptResults.orphans">
                <p>{{ scriptResults.count }} orphaned volumes found</p>
                <table class="results-table" v-if="scriptResults.orphans.length > 0">
                  <thead><tr><th>Node</th><th>Storage</th><th>Volume ID</th><th>Format</th><th>Size</th></tr></thead>
                  <tbody>
                    <tr v-for="o in scriptResults.orphans" :key="o.volid">
                      <td>{{ o.node }}</td>
                      <td>{{ o.storage }}</td>
                      <td class="monospace">{{ o.volid }}</td>
                      <td>{{ o.format }}</td>
                      <td>{{ formatBytes(o.size) }}</td>
                    </tr>
                  </tbody>
                </table>
              </template>
            </div>
          </div>
        </div>

        <!-- ── Execution Panel ── -->
        <div v-if="executionResults.length > 0" class="execution-panel">
          <div class="exec-header">
            <h3>Execution Progress</h3>
            <div class="exec-header-actions">
              <span class="exec-summary">
                {{ execSuccessCount }} success ·
                {{ execFailCount }} failed ·
                {{ execPendingCount }} pending
              </span>
              <button class="btn btn-xs btn-danger" v-if="executing" @click="abortExec">Abort</button>
              <button class="btn btn-xs btn-secondary" @click="downloadReport">Download Report</button>
              <button class="btn btn-xs btn-secondary" @click="clearResults">Clear</button>
            </div>
          </div>

          <div class="exec-progress-bar">
            <div
              class="exec-progress-fill"
              :style="{ width: execProgressPct + '%' }"
              :class="{ 'progress-done': !executing && execFailCount === 0, 'progress-error': execFailCount > 0 }"
            ></div>
          </div>

          <div class="exec-table-wrap">
            <table class="exec-table">
              <thead>
                <tr>
                  <th>VM</th>
                  <th>Node</th>
                  <th>Host</th>
                  <th>Status</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in executionResults" :key="`exec-${r.host_id}-${r.node}-${r.vmid}`" :class="rowClass(r)">
                  <td>{{ r.name || r.vmid }}</td>
                  <td>{{ r.node }}</td>
                  <td>{{ hostName(r.host_id) }}</td>
                  <td>
                    <span class="exec-status-badge" :class="r.status">{{ r.status }}</span>
                  </td>
                  <td class="exec-detail">
                    <span v-if="r.upid" class="monospace">{{ r.upid }}</span>
                    <span v-if="r.error" class="error-text">{{ r.error }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'BulkOperations',
  setup() {
    const toast = useToast()

    // ── Data ──────────────────────────────────────────────────────────────
    const hosts = ref([])
    const allVms = ref([])
    const filteredVms = ref([])
    const selectedVms = ref([])
    const loadingVms = ref(false)

    // ── Filters ───────────────────────────────────────────────────────────
    const search = ref('')
    const filterHost = ref('')
    const filterStatus = ref('')
    const filterTag = ref('')
    const filterNode = ref('')

    // ── Tabs ──────────────────────────────────────────────────────────────
    const tabs = [
      { key: 'power', label: 'Power' },
      { key: 'snapshot', label: 'Snapshots' },
      { key: 'config', label: 'Config' },
      { key: 'migrate', label: 'Migrate' },
      { key: 'scripts', label: 'Scripts' },
    ]
    const activeTab = ref('power')

    // ── Power ─────────────────────────────────────────────────────────────
    const execMode = ref('parallel')
    const execDelay = ref(0)
    const skipTargetState = ref(true)

    // ── Snapshot ──────────────────────────────────────────────────────────
    const snapTemplate = ref('bulk-{date}')
    const snapDescription = ref('Bulk snapshot')
    const snapIncludeRam = ref(false)
    const snapDeleteDays = ref(30)

    // ── Config ────────────────────────────────────────────────────────────
    const cfgCores = ref(null)
    const cfgMemory = ref(null)
    const cfgTagsAdd = ref('')
    const cfgTagsRemove = ref('')
    const cfgAgent = ref('')
    const cfgOnboot = ref('')
    const cfgBalloon = ref(null)
    const configPreviewData = ref([])
    const previewLoading = ref(false)

    // Config preset management
    const CFG_PRESETS_KEY = 'depl0y_bulk_cfg_presets'
    const cfgPresets = ref([])
    const showSaveCfgPresetModal = ref(false)
    const newCfgPresetName = ref('')
    const cfgFailedVms = ref([])

    function loadCfgPresets() {
      try { cfgPresets.value = JSON.parse(localStorage.getItem(CFG_PRESETS_KEY) || '[]') } catch { cfgPresets.value = [] }
    }

    function openSaveCfgPresetModal() {
      newCfgPresetName.value = ''
      showSaveCfgPresetModal.value = true
    }

    function saveCfgPreset() {
      const name = newCfgPresetName.value.trim()
      if (!name) return
      const preset = {
        name,
        cores: cfgCores.value,
        memory: cfgMemory.value,
        tagsAdd: cfgTagsAdd.value,
        tagsRemove: cfgTagsRemove.value,
        agent: cfgAgent.value,
        onboot: cfgOnboot.value,
        balloon: cfgBalloon.value,
      }
      const list = cfgPresets.value.filter(p => p.name !== name)
      list.push(preset)
      localStorage.setItem(CFG_PRESETS_KEY, JSON.stringify(list))
      cfgPresets.value = list
      showSaveCfgPresetModal.value = false
      toast.success(`Preset "${name}" saved`)
    }

    function loadCfgPreset(name) {
      if (!name) return
      const preset = cfgPresets.value.find(p => p.name === name)
      if (!preset) return
      cfgCores.value = preset.cores ?? null
      cfgMemory.value = preset.memory ?? null
      cfgTagsAdd.value = preset.tagsAdd || ''
      cfgTagsRemove.value = preset.tagsRemove || ''
      cfgAgent.value = preset.agent || ''
      cfgOnboot.value = preset.onboot || ''
      cfgBalloon.value = preset.balloon ?? null
      configPreviewData.value = []
      cfgFailedVms.value = []
      toast.info(`Loaded preset "${name}"`)
    }

    loadCfgPresets()

    // ── Migrate ───────────────────────────────────────────────────────────
    const migrateHostId = ref('')
    const migrateNode = ref('')
    const migrateOnline = ref(true)
    const migrateLocalDisks = ref(false)
    const targetNodes = ref([])

    // ── Scripts ───────────────────────────────────────────────────────────
    const scripts = [
      { key: 'cleanup-snapshots', name: 'Cleanup Old Snapshots', icon: '🗑', desc: 'Delete snapshots older than N days across all VMs' },
      { key: 'tag-compliance', name: 'Tag Compliance', icon: '🏷', desc: 'Ensure all VMs have required tags' },
      { key: 'resource-audit', name: 'Resource Audit', icon: '📊', desc: 'Find over-provisioned VMs by comparing usage vs allocation' },
      { key: 'orphaned-disks', name: 'Orphaned Disk Finder', icon: '💿', desc: 'Find storage volumes not attached to any VM' },
    ]
    const activeScript = ref('')
    const scriptHostId = ref('')
    const cleanupDays = ref(30)
    const requiredTags = ref('')
    const auditCpuThreshold = ref(20)
    const auditRamThreshold = ref(20)
    const scriptRunning = ref(false)
    const scriptResults = ref(null)

    // ── Execution ─────────────────────────────────────────────────────────
    const executing = ref(false)
    const executionResults = ref([])
    const aborted = ref(false)

    // ── Computed ──────────────────────────────────────────────────────────
    const hasSelection = computed(() => selectedVms.value.length > 0)

    const allNodes = computed(() => {
      const nodes = new Set()
      allVms.value.forEach(vm => nodes.add(vm.node))
      return Array.from(nodes).sort()
    })

    const execSuccessCount = computed(() => executionResults.value.filter(r => r.status === 'success').length)
    const execFailCount = computed(() => executionResults.value.filter(r => r.status === 'failed').length)
    const execPendingCount = computed(() => executionResults.value.filter(r => r.status === 'pending' || r.status === 'running').length)
    const execProgressPct = computed(() => {
      const total = executionResults.value.length
      if (!total) return 0
      return Math.round(((execSuccessCount.value + execFailCount.value) / total) * 100)
    })

    // ── Methods ───────────────────────────────────────────────────────────
    const loadHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = res.data || []
      } catch (e) {
        toast.error('Failed to load hosts')
      }
    }

    const loadVms = async () => {
      loadingVms.value = true
      allVms.value = []
      try {
        // Load VMs from all hosts using cluster resources
        for (const host of hosts.value) {
          try {
            const res = await api.pveNode.clusterResources(host.id, 'vm')
            const vms = (res.data || [])
              .filter(r => r.type === 'qemu')
              .map(r => ({
                host_id: host.id,
                node: r.node,
                vmid: r.vmid,
                name: r.name,
                status: r.status,
                tags: r.tags || '',
                cpu: r.cpu,
                maxcpu: r.maxcpu,
                mem: r.mem,
                maxmem: r.maxmem,
              }))
            allVms.value.push(...vms)
          } catch (e) {
            // skip host if error
          }
        }
        applyFilters()
      } finally {
        loadingVms.value = false
      }
    }

    const applyFilters = () => {
      let result = allVms.value

      if (filterHost.value) {
        result = result.filter(v => v.host_id === filterHost.value)
      }
      if (filterStatus.value) {
        result = result.filter(v => v.status === filterStatus.value)
      }
      if (filterNode.value) {
        result = result.filter(v => v.node === filterNode.value)
      }
      if (filterTag.value) {
        const t = filterTag.value.toLowerCase()
        result = result.filter(v => (v.tags || '').toLowerCase().includes(t))
      }
      if (search.value) {
        const s = search.value.toLowerCase()
        result = result.filter(v =>
          (v.name || '').toLowerCase().includes(s) ||
          String(v.vmid).includes(s) ||
          v.node.toLowerCase().includes(s)
        )
      }

      filteredVms.value = result
    }

    const isSelected = (vm) => {
      return selectedVms.value.some(
        s => s.host_id === vm.host_id && s.node === vm.node && s.vmid === vm.vmid
      )
    }

    const toggleSelect = (vm) => {
      if (isSelected(vm)) {
        deselectVm(vm)
      } else {
        selectedVms.value.push(vm)
      }
    }

    const selectAll = () => {
      allVms.value.forEach(vm => {
        if (!isSelected(vm)) selectedVms.value.push(vm)
      })
    }

    const selectFiltered = () => {
      filteredVms.value.forEach(vm => {
        if (!isSelected(vm)) selectedVms.value.push(vm)
      })
    }

    const deselectAll = () => {
      selectedVms.value = []
    }

    const deselectVm = (vm) => {
      selectedVms.value = selectedVms.value.filter(
        s => !(s.host_id === vm.host_id && s.node === vm.node && s.vmid === vm.vmid)
      )
    }

    const hostName = (hostId) => {
      const h = hosts.value.find(h => h.id === hostId)
      return h ? h.name : String(hostId)
    }

    // Build the VMTarget payload
    const buildTargets = () => selectedVms.value.map(v => ({
      host_id: v.host_id,
      node: v.node,
      vmid: v.vmid,
    }))

    // Initialize execution results table from selected VMs
    const initExecResults = () => {
      executionResults.value = selectedVms.value.map(v => ({
        host_id: v.host_id,
        node: v.node,
        vmid: v.vmid,
        name: v.name,
        status: 'pending',
        upid: null,
        error: null,
      }))
    }

    // Merge API response results into execution table
    const mergeExecResults = (apiResults) => {
      for (const r of apiResults) {
        const idx = executionResults.value.findIndex(
          e => e.host_id === r.host_id && e.node === r.node && e.vmid === r.vmid
        )
        if (idx >= 0) {
          executionResults.value[idx].status = r.error ? 'failed' : 'success'
          executionResults.value[idx].upid = r.upid || null
          executionResults.value[idx].error = r.error || null
        }
      }
    }

    // ── Power ─────────────────────────────────────────────────────────────
    const runPower = async (action) => {
      if (!hasSelection.value) return
      executing.value = true
      aborted.value = false
      initExecResults()

      try {
        const res = await api.vmBulk.bulkPower({
          vms: buildTargets(),
          action,
        })
        mergeExecResults(res.data.results)

        const failed = res.data.results.filter(r => r.error).length
        if (failed > 0) {
          toast.warning(`${failed} VM(s) failed — see results below`)
        } else {
          toast.success(`Power action "${action}" dispatched to all VMs`)
        }
      } catch (e) {
        toast.error('Bulk power operation failed')
      } finally {
        executing.value = false
      }
    }

    // ── Snapshot ──────────────────────────────────────────────────────────
    const runSnapshot = async () => {
      if (!hasSelection.value) return
      executing.value = true
      initExecResults()

      try {
        const res = await api.vmBulk.bulkSnapshot({
          vms: buildTargets(),
          snapname_template: snapTemplate.value || 'bulk-{date}',
          description: snapDescription.value,
          vmstate: snapIncludeRam.value,
        })
        mergeExecResults(res.data.results)
        const failed = res.data.results.filter(r => r.error).length
        if (failed > 0) {
          toast.warning(`Snapshot created on ${res.data.results.length - failed} VMs, ${failed} failed`)
        } else {
          toast.success('Snapshots created on all selected VMs')
        }
      } catch (e) {
        toast.error('Bulk snapshot failed')
      } finally {
        executing.value = false
      }
    }

    const runDeleteSnapshots = async () => {
      if (!hasSelection.value) return
      if (!confirm(`Delete all snapshots older than ${snapDeleteDays.value} days on ${selectedVms.value.length} VMs?`)) return
      executing.value = true
      initExecResults()

      try {
        const res = await api.vmBulk.bulkDeleteSnapshots({
          vms: buildTargets(),
          older_than_days: snapDeleteDays.value,
        })
        // Map results differently — each entry has 'deleted' and 'errors' arrays
        for (const r of res.data.results) {
          const idx = executionResults.value.findIndex(
            e => e.host_id === r.host_id && e.node === r.node && e.vmid === r.vmid
          )
          if (idx >= 0) {
            const hasError = r.errors && r.errors.length > 0
            executionResults.value[idx].status = hasError ? 'failed' : 'success'
            executionResults.value[idx].upid = `Deleted: ${(r.deleted || []).join(', ') || 'none'}`
            executionResults.value[idx].error = hasError ? r.errors.map(e => e.error).join(', ') : null
          }
        }
        toast.success('Old snapshot cleanup complete')
      } catch (e) {
        toast.error('Delete old snapshots failed')
      } finally {
        executing.value = false
      }
    }

    // ── Config ────────────────────────────────────────────────────────────
    const buildConfigPayload = () => {
      const payload = {
        vms: buildTargets(),
      }
      if (cfgCores.value) payload.cores = cfgCores.value
      if (cfgMemory.value) payload.memory = cfgMemory.value
      if (cfgTagsAdd.value.trim()) {
        payload.tags_add = cfgTagsAdd.value.split(',').map(t => t.trim()).filter(Boolean)
      }
      if (cfgTagsRemove.value.trim()) {
        payload.tags_remove = cfgTagsRemove.value.split(',').map(t => t.trim()).filter(Boolean)
      }
      if (cfgAgent.value) payload.agent = cfgAgent.value
      if (cfgOnboot.value) payload.onboot = cfgOnboot.value === 'true'
      if (cfgBalloon.value != null) payload.balloon = cfgBalloon.value
      return payload
    }

    const previewConfig = async () => {
      if (!hasSelection.value) return
      previewLoading.value = true
      configPreviewData.value = []
      try {
        const res = await api.vmBulk.bulkConfigPreview(buildConfigPayload())
        configPreviewData.value = res.data.results
      } catch (e) {
        toast.error('Preview failed')
      } finally {
        previewLoading.value = false
      }
    }

    const runConfig = async () => {
      if (!hasSelection.value) return
      executing.value = true
      cfgFailedVms.value = []
      initExecResults()

      try {
        const res = await api.vmBulk.bulkConfig(buildConfigPayload())
        mergeExecResults(res.data.results)
        const failed = res.data.results.filter(r => r.error)
        if (failed.length > 0) {
          // Track failed VMs for retry
          cfgFailedVms.value = selectedVms.value.filter(sv =>
            failed.some(f => f.host_id === sv.host_id && f.node === sv.node && f.vmid === sv.vmid)
          )
          toast.warning(`Config updated on ${res.data.results.length - failed.length} VMs, ${failed.length} failed`)
        } else {
          toast.success('Config updated on all selected VMs')
        }
      } catch (e) {
        toast.error('Bulk config update failed')
      } finally {
        executing.value = false
      }
    }

    const retryFailedConfig = async () => {
      if (!cfgFailedVms.value.length) return
      executing.value = true
      const retryTargets = cfgFailedVms.value
      cfgFailedVms.value = []

      // Init exec results for retry
      executionResults.value = retryTargets.map(v => ({
        host_id: v.host_id,
        node: v.node,
        vmid: v.vmid,
        name: v.name,
        status: 'pending',
        upid: null,
        error: null,
      }))

      try {
        const payload = buildConfigPayload()
        payload.vms = retryTargets.map(v => ({ host_id: v.host_id, node: v.node, vmid: v.vmid }))
        const res = await api.vmBulk.bulkConfig(payload)
        mergeExecResults(res.data.results)
        const stillFailed = res.data.results.filter(r => r.error)
        if (stillFailed.length > 0) {
          cfgFailedVms.value = retryTargets.filter(sv =>
            stillFailed.some(f => f.host_id === sv.host_id && f.node === sv.node && f.vmid === sv.vmid)
          )
          toast.warning(`Retry: ${res.data.results.length - stillFailed.length} succeeded, ${stillFailed.length} still failing`)
        } else {
          toast.success('Retry successful — all VMs updated')
        }
      } catch (e) {
        toast.error('Retry failed')
      } finally {
        executing.value = false
      }
    }

    const formatVal = (v) => {
      if (v === null || v === undefined) return 'unset'
      if (Array.isArray(v)) return v.join(', ') || '(empty)'
      return String(v)
    }

    // ── Migrate ───────────────────────────────────────────────────────────
    const loadTargetNodes = async () => {
      if (!migrateHostId.value) { targetNodes.value = []; return }
      try {
        const res = await api.proxmox.listNodes(migrateHostId.value)
        targetNodes.value = (res.data || []).map(n => n.node || n.name)
      } catch (e) {
        toast.error('Failed to load target nodes')
      }
    }

    const runMigrate = async () => {
      if (!hasSelection.value || !migrateNode.value) return
      executing.value = true
      initExecResults()

      try {
        const res = await api.vmBulk.bulkMigrate({
          vms: buildTargets(),
          target_node: migrateNode.value,
          online: migrateOnline.value,
          with_local_disks: migrateLocalDisks.value,
        })
        mergeExecResults(res.data.results)
        const failed = res.data.results.filter(r => r.error).length
        if (failed > 0) {
          toast.warning(`Migration started on ${res.data.results.length - failed} VMs, ${failed} failed`)
        } else {
          toast.success('Migration started on all selected VMs')
        }
      } catch (e) {
        toast.error('Bulk migrate failed')
      } finally {
        executing.value = false
      }
    }

    // ── Scripts ───────────────────────────────────────────────────────────
    const runScript = async (dryRun) => {
      if (!scriptHostId.value) return
      scriptRunning.value = true
      scriptResults.value = null

      try {
        let res
        const hid = Number(scriptHostId.value)

        if (activeScript.value === 'cleanup-snapshots') {
          res = await api.vmBulk.scriptCleanupSnapshots({
            host_id: hid,
            older_than_days: cleanupDays.value,
            dry_run: dryRun,
          })
        } else if (activeScript.value === 'tag-compliance') {
          const tags = requiredTags.value.split(',').map(t => t.trim()).filter(Boolean)
          if (!tags.length) { toast.error('Enter at least one required tag'); return }
          res = await api.vmBulk.scriptTagCompliance({
            host_id: hid,
            required_tags: tags,
            dry_run: dryRun,
          })
        } else if (activeScript.value === 'resource-audit') {
          res = await api.vmBulk.scriptResourceAudit({
            host_id: hid,
            cpu_threshold_pct: auditCpuThreshold.value,
            ram_threshold_pct: auditRamThreshold.value,
          })
        } else if (activeScript.value === 'orphaned-disks') {
          res = await api.vmBulk.getOrphanedDisks(hid)
        }

        if (res) scriptResults.value = res.data
        toast.success('Script completed')
      } catch (e) {
        toast.error('Script failed')
      } finally {
        scriptRunning.value = false
      }
    }

    const downloadScriptReport = () => {
      if (!scriptResults.value) return
      const json = JSON.stringify(scriptResults.value, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${activeScript.value}-report-${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
    }

    // ── Execution helpers ─────────────────────────────────────────────────
    const abortExec = () => {
      aborted.value = true
      executing.value = false
      toast.warning('Execution aborted (in-flight operations may still complete)')
    }

    const clearResults = () => {
      executionResults.value = []
    }

    const downloadReport = () => {
      const json = JSON.stringify({ results: executionResults.value }, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `bulk-ops-report-${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
    }

    const rowClass = (r) => {
      if (r.status === 'success') return 'row-success'
      if (r.status === 'failed') return 'row-error'
      if (r.status === 'running') return 'row-running'
      return ''
    }

    // ── Helpers ───────────────────────────────────────────────────────────
    const ageLabel = (ts) => {
      if (!ts) return 'unknown'
      const days = Math.floor((Date.now() / 1000 - ts) / 86400)
      return `${days} days ago`
    }

    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const units = ['B', 'KB', 'MB', 'GB', 'TB']
      let i = 0
      let v = bytes
      while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
      return `${v.toFixed(1)} ${units[i]}`
    }

    // ── Init ──────────────────────────────────────────────────────────────
    onMounted(async () => {
      await loadHosts()
      await loadVms()
    })

    return {
      hosts, allVms, filteredVms, selectedVms, loadingVms,
      search, filterHost, filterStatus, filterTag, filterNode,
      tabs, activeTab, allNodes,
      execMode, execDelay, skipTargetState,
      snapTemplate, snapDescription, snapIncludeRam, snapDeleteDays,
      cfgCores, cfgMemory, cfgTagsAdd, cfgTagsRemove, cfgAgent, cfgOnboot, cfgBalloon,
      configPreviewData, previewLoading,
      cfgPresets, showSaveCfgPresetModal, newCfgPresetName, cfgFailedVms,
      openSaveCfgPresetModal, saveCfgPreset, loadCfgPreset,
      migrateHostId, migrateNode, migrateOnline, migrateLocalDisks, targetNodes,
      scripts, activeScript, scriptHostId, cleanupDays, requiredTags,
      auditCpuThreshold, auditRamThreshold, scriptRunning, scriptResults,
      executing, executionResults, aborted,
      hasSelection,
      execSuccessCount, execFailCount, execPendingCount, execProgressPct,
      isSelected, toggleSelect, selectAll, selectFiltered, deselectAll, deselectVm,
      applyFilters, hostName,
      runPower, runSnapshot, runDeleteSnapshots,
      previewConfig, runConfig, retryFailedConfig, formatVal,
      loadTargetNodes, runMigrate,
      runScript, downloadScriptReport,
      abortExec, clearResults, downloadReport, rowClass,
      ageLabel, formatBytes,
    }
  }
}
</script>

<style scoped>
.bulk-ops-view {
  padding: 1.5rem;
  max-width: 100%;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h1 {
  margin: 0 0 0.25rem;
  font-size: 1.75rem;
}

.subtitle {
  color: var(--text-muted, #6b7280);
  margin: 0;
}

/* ── Two-column layout ── */
.bulk-layout {
  display: flex;
  gap: 1.25rem;
  align-items: flex-start;
}

/* ── Selection Panel ── */
.selection-panel {
  width: 40%;
  min-width: 300px;
  background: var(--card-bg, #1e2533);
  border: 1px solid var(--border, #2d3748);
  border-radius: 0.5rem;
  padding: 1rem;
  position: sticky;
  top: 1rem;
  max-height: calc(100vh - 8rem);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-header h2 {
  margin: 0;
  font-size: 1rem;
}

.selected-badge {
  background: #3b82f6;
  color: white;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.filter-row {
  display: flex;
  gap: 0.5rem;
}

.filter-row .input,
.filter-row .select {
  flex: 1;
  min-width: 0;
}

.select-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.vm-list {
  flex: 1;
  overflow-y: auto;
  border: 1px solid var(--border, #2d3748);
  border-radius: 0.375rem;
  min-height: 100px;
}

.vm-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  border-bottom: 1px solid var(--border, #2d3748);
  transition: background 0.15s;
  font-size: 0.8rem;
}

.vm-row:last-child { border-bottom: none; }
.vm-row:hover { background: rgba(255,255,255,0.04); }
.vm-row.selected { background: rgba(59,130,246,0.12); }

.vm-check { cursor: pointer; flex-shrink: 0; }

.vm-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.vm-status-dot.running { background: #22c55e; }
.vm-status-dot.stopped { background: #6b7280; }
.vm-status-dot.paused { background: #f59e0b; }

.vm-info {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.vm-name {
  display: block;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vm-meta {
  display: block;
  font-size: 0.7rem;
  color: var(--text-muted, #6b7280);
}

.vm-host-badge {
  font-size: 0.65rem;
  background: rgba(255,255,255,0.08);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
  white-space: nowrap;
}

.empty-list {
  padding: 1.5rem;
  text-align: center;
  color: var(--text-muted, #6b7280);
  font-size: 0.85rem;
}

.loading-state {
  padding: 1rem;
  color: var(--text-muted, #6b7280);
  text-align: center;
}

.selected-chips {
  border-top: 1px solid var(--border, #2d3748);
  padding-top: 0.5rem;
}

.chips-header {
  font-size: 0.75rem;
  color: var(--text-muted, #6b7280);
  margin-bottom: 0.4rem;
}

.chips-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  max-height: 100px;
  overflow-y: auto;
}

.vm-chip {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  background: rgba(59,130,246,0.15);
  border: 1px solid rgba(59,130,246,0.3);
  border-radius: 999px;
  padding: 0.15rem 0.5rem;
  font-size: 0.72rem;
}

.chip-remove {
  background: none;
  border: none;
  color: var(--text-muted, #6b7280);
  cursor: pointer;
  padding: 0;
  font-size: 0.9rem;
  line-height: 1;
}
.chip-remove:hover { color: #ef4444; }

/* ── Operations Panel ── */
.operations-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.tab-bar {
  display: flex;
  gap: 0;
  background: var(--card-bg, #1e2533);
  border: 1px solid var(--border, #2d3748);
  border-radius: 0.5rem;
  overflow: hidden;
}

.tab-btn {
  flex: 1;
  padding: 0.6rem 1rem;
  background: none;
  border: none;
  border-right: 1px solid var(--border, #2d3748);
  color: var(--text-muted, #6b7280);
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.15s;
}

.tab-btn:last-child { border-right: none; }
.tab-btn:hover { background: rgba(255,255,255,0.05); color: white; }
.tab-btn.active { background: rgba(59,130,246,0.15); color: #3b82f6; }

.tab-content {
  background: var(--card-bg, #1e2533);
  border: 1px solid var(--border, #2d3748);
  border-radius: 0.5rem;
  padding: 1.25rem;
}

.tab-content h3 {
  margin: 0 0 0.25rem;
  font-size: 1.1rem;
}

.tab-desc {
  color: var(--text-muted, #6b7280);
  font-size: 0.85rem;
  margin: 0 0 1rem;
}

/* ── Form elements ── */
.input {
  background: var(--input-bg, #0f1419);
  border: 1px solid var(--border, #2d3748);
  border-radius: 0.375rem;
  color: var(--text, #e2e8f0);
  padding: 0.45rem 0.6rem;
  font-size: 0.875rem;
  width: 100%;
  box-sizing: border-box;
}

.input:focus {
  outline: none;
  border-color: #3b82f6;
}

.input-sm { max-width: 120px; }

.select {
  background: var(--input-bg, #0f1419);
  border: 1px solid var(--border, #2d3748);
  border-radius: 0.375rem;
  color: var(--text, #e2e8f0);
  padding: 0.45rem 0.6rem;
  font-size: 0.875rem;
  width: 100%;
}

.form-section {
  margin-bottom: 1.25rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border, #2d3748);
}

.form-section:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.form-section h4 {
  margin: 0 0 0.75rem;
  font-size: 0.9rem;
  color: var(--text-muted, #6b7280);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.form-row {
  margin-bottom: 0.75rem;
}

.form-row label {
  display: block;
  font-size: 0.8rem;
  color: var(--text-muted, #6b7280);
  margin-bottom: 0.25rem;
}

.checkbox-row label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.hint {
  font-size: 0.75rem;
  color: var(--text-muted, #6b7280);
  margin: 0.25rem 0 0;
}

.hint code {
  background: rgba(255,255,255,0.08);
  padding: 0.1rem 0.3rem;
  border-radius: 0.2rem;
  font-family: monospace;
}

.input-with-unit {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.danger-zone {
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 0.375rem;
  padding: 0.75rem;
  margin-top: 1rem;
}

/* ── Option row (power tab) ── */
.option-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.option-label {
  min-width: 200px;
  font-size: 0.85rem;
  color: var(--text-muted, #6b7280);
}

.toggle-group {
  display: flex;
  gap: 0;
}

.toggle-btn {
  padding: 0.35rem 0.75rem;
  background: var(--input-bg, #0f1419);
  border: 1px solid var(--border, #2d3748);
  color: var(--text-muted, #6b7280);
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.15s;
}

.toggle-btn:first-child { border-radius: 0.375rem 0 0 0.375rem; }
.toggle-btn:last-child { border-radius: 0 0.375rem 0.375rem 0; border-left: none; }
.toggle-btn.active { background: rgba(59,130,246,0.2); color: #3b82f6; border-color: #3b82f6; }

.slider { flex: 1; }
.slider-val { min-width: 2.5rem; text-align: right; font-size: 0.85rem; }

.toggle-check { cursor: pointer; }

.power-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
}

/* ── Config preview ── */
.config-actions {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.preview-table-wrap {
  overflow-x: auto;
}

.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.preview-table th,
.preview-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border, #2d3748);
  text-align: left;
}

.preview-table th { color: var(--text-muted, #6b7280); font-weight: 500; }

.preview-error { color: #ef4444; font-size: 0.8rem; }
.preview-nochange { color: var(--text-muted, #6b7280); font-size: 0.8rem; }
.preview-diff { display: flex; flex-direction: column; gap: 0.2rem; }

.diff-item {
  font-size: 0.8rem;
  background: rgba(59,130,246,0.08);
  padding: 0.1rem 0.4rem;
  border-radius: 0.2rem;
  display: inline-block;
  margin-right: 0.3rem;
}

/* ── Scripts ── */
.script-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.script-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border, #2d3748);
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 0.15s;
}

.script-card:hover { border-color: #3b82f6; background: rgba(59,130,246,0.05); }
.script-card.active { border-color: #3b82f6; background: rgba(59,130,246,0.1); }

.script-icon { font-size: 1.5rem; }

.script-info {
  display: flex;
  flex-direction: column;
}

.script-name { font-weight: 500; font-size: 0.9rem; }
.script-desc { font-size: 0.75rem; color: var(--text-muted, #6b7280); }

.script-params {
  padding: 1rem;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border, #2d3748);
  border-radius: 0.375rem;
}

.script-params h4 {
  margin: 0 0 0.75rem;
}

.script-run-row {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}

.script-results {
  margin-top: 1rem;
  border-top: 1px solid var(--border, #2d3748);
  padding-top: 1rem;
}

.results-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.results-header h4 { margin: 0; }

.results-meta {
  font-size: 0.75rem;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
  padding: 0.15rem 0.4rem;
  border-radius: 0.25rem;
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.results-table th,
.results-table td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid var(--border, #2d3748);
  text-align: left;
}

.results-table th { color: var(--text-muted, #6b7280); }

/* ── Execution panel ── */
.execution-panel {
  background: var(--card-bg, #1e2533);
  border: 1px solid var(--border, #2d3748);
  border-radius: 0.5rem;
  padding: 1rem;
}

.exec-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.exec-header h3 { margin: 0; font-size: 1rem; }

.exec-header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.exec-summary {
  font-size: 0.8rem;
  color: var(--text-muted, #6b7280);
}

.exec-progress-bar {
  height: 6px;
  background: var(--border, #2d3748);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.75rem;
}

.exec-progress-fill {
  height: 100%;
  background: #3b82f6;
  transition: width 0.3s ease;
  border-radius: 3px;
}

.exec-progress-fill.progress-done { background: #22c55e; }
.exec-progress-fill.progress-error { background: #f59e0b; }

.exec-table-wrap { overflow-x: auto; }

.exec-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.exec-table th,
.exec-table td {
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--border, #2d3748);
  text-align: left;
}

.exec-table th { color: var(--text-muted, #6b7280); font-weight: 500; }

.row-success { background: rgba(34, 197, 94, 0.05); }
.row-error { background: rgba(239, 68, 68, 0.05); }
.row-running { background: rgba(59, 130, 246, 0.05); }
.row-warn { background: rgba(245, 158, 11, 0.05); }

.exec-status-badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 500;
  text-transform: capitalize;
}

.exec-status-badge.pending { background: rgba(107,114,128,0.2); color: #9ca3af; }
.exec-status-badge.running { background: rgba(59,130,246,0.2); color: #3b82f6; }
.exec-status-badge.success { background: rgba(34,197,94,0.2); color: #22c55e; }
.exec-status-badge.failed { background: rgba(239,68,68,0.2); color: #ef4444; }

.exec-detail { font-size: 0.78rem; }
.monospace { font-family: monospace; color: var(--text-muted, #6b7280); }
.error-text { color: #ef4444; }

/* ── Buttons ── */
.btn {
  padding: 0.45rem 1rem;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-success { background: #22c55e; color: white; }
.btn-success:hover:not(:disabled) { background: #16a34a; }
.btn-warning { background: #f59e0b; color: white; }
.btn-warning:hover:not(:disabled) { background: #d97706; }
.btn-danger { background: #ef4444; color: white; }
.btn-danger:hover:not(:disabled) { background: #dc2626; }
.btn-secondary { background: rgba(255,255,255,0.08); color: var(--text, #e2e8f0); border: 1px solid var(--border, #2d3748); }
.btn-secondary:hover:not(:disabled) { background: rgba(255,255,255,0.12); }
.btn-xs { padding: 0.2rem 0.55rem; font-size: 0.75rem; }

/* ── Badges ── */
.badge {
  padding: 0.15rem 0.45rem;
  border-radius: 0.25rem;
  font-size: 0.72rem;
  font-weight: 500;
}

.badge-success { background: rgba(34,197,94,0.2); color: #22c55e; }
.badge-warning { background: rgba(245,158,11,0.2); color: #f59e0b; }
.badge-error { background: rgba(239,68,68,0.2); color: #ef4444; }

.cell-warn { color: #f59e0b; font-weight: 600; }

/* ── Config preset bar ── */
.cfg-preset-bar {
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border, #2d3748);
}

.cfg-preset-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

/* ── Enhanced preview table ── */
.preview-table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.preview-table-header h4 {
  margin: 0;
  font-size: 0.9rem;
}

.preview-legend {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.legend-item {
  font-size: 0.72rem;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
}

.legend-change {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.legend-nochange {
  background: rgba(107, 114, 128, 0.15);
  color: #9ca3af;
}

.legend-error {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.preview-row-change { background: rgba(59, 130, 246, 0.04); }
.preview-row-nochange { background: rgba(107, 114, 128, 0.04); }
.preview-row-error { background: rgba(239, 68, 68, 0.04); }

.preview-field { font-family: monospace; font-size: 0.78rem; color: var(--text-muted, #6b7280); }
.preview-from { font-size: 0.8rem; color: #ef4444; }
.preview-to { font-size: 0.8rem; color: #22c55e; font-weight: 500; }

.badge-preview {
  display: inline-block;
  padding: 0.12rem 0.45rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  white-space: nowrap;
}

.badge-preview-change { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
.badge-preview-skip { background: rgba(107, 114, 128, 0.2); color: #9ca3af; }
.badge-preview-error { background: rgba(239, 68, 68, 0.2); color: #ef4444; }

.preview-summary {
  margin-top: 0.5rem;
  font-size: 0.78rem;
  color: var(--text-muted, #6b7280);
  text-align: right;
}

/* ── Save preset mini modal ── */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.mini-modal {
  background: var(--card-bg, #1e2533);
  border: 1px solid var(--border, #2d3748);
  border-radius: 0.5rem;
  width: 320px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.mini-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border, #2d3748);
  font-size: 0.9rem;
  font-weight: 600;
}

.mini-modal-body {
  padding: 1rem;
}

.mini-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border, #2d3748);
}

/* ── btn-outline (for preset controls) ── */
.btn-outline {
  background: transparent;
  border: 1px solid var(--border, #2d3748);
  color: var(--text, #e2e8f0);
}
.btn-outline:hover:not(:disabled) {
  background: rgba(255,255,255,0.06);
}

/* ── Responsive ── */
@media (max-width: 900px) {
  .bulk-layout { flex-direction: column; }
  .selection-panel { width: 100%; position: static; max-height: none; }
}
</style>
