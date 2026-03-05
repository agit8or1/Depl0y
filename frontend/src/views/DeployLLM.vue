<template>
  <div class="deploy-llm-page">
    <!-- Header -->
    <div class="page-header">
      <div class="page-header-left">
        <router-link to="/vms" class="back-link">← Back</router-link>
        <h2>Deploy LLM</h2>
        <p class="subtitle">Deploy a self-hosted AI inference server in a few steps</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="card loading-card">
      <div class="spinner"></div>
      <p>Loading catalog...</p>
    </div>

    <template v-else>

      <!-- ═══════════════════════════════════════════════════════ -->
      <!-- MODE PICKER (shown before any steps)                   -->
      <!-- ═══════════════════════════════════════════════════════ -->
      <div v-if="mode === null" class="wizard-step">
        <div class="card mode-picker-card">
          <div class="card-header"><h3>How would you like to proceed?</h3></div>
          <p class="step-desc">Choose Simple Mode for a quick guided setup, or Advanced Mode to configure every detail.</p>
          <div class="mode-grid">
            <div class="mode-card" @click="pickMode('simple')">
              <div class="mode-icon">&#9889;</div>
              <h4>Simple Mode</h4>
              <p>Answer 4 quick questions and we'll recommend the best configuration. No technical knowledge required.</p>
              <ul class="mode-features">
                <li>4 clicks to configure</li>
                <li>Auto-selected model &amp; resources</li>
                <li>Always uses Ollama + Ubuntu 24.04</li>
              </ul>
              <div class="mode-cta">Get Started →</div>
            </div>
            <div class="mode-card mode-card-advanced" @click="pickMode('advanced')">
              <div class="mode-icon">&#9881;&#65039;</div>
              <h4>Advanced Mode</h4>
              <p>Full control over engine, model, GPU, OS, networking, and every resource parameter.</p>
              <ul class="mode-features">
                <li>Choose any engine (Ollama, vLLM, LocalAI, llama.cpp)</li>
                <li>Full GPU passthrough configuration</li>
                <li>Custom networking &amp; storage</li>
              </ul>
              <div class="mode-cta">Configure →</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════════════════ -->
      <!-- SIMPLE MODE                                            -->
      <!-- ═══════════════════════════════════════════════════════ -->
      <template v-if="mode === 'simple'">
        <!-- Back to mode selection -->
        <div class="mode-back-bar">
          <button class="mode-back-link" @click="resetToModePicker">← Back to mode selection</button>
          <span class="mode-badge">Simple Mode</span>
        </div>

        <!-- Simple Step Progress Bar -->
        <div class="step-bar">
          <div
            v-for="(step, idx) in simpleSteps"
            :key="idx"
            :class="['step-item', { active: simpleStep === idx, completed: simpleStep > idx }]"
            @click="goToSimpleStep(idx)"
          >
            <div class="step-circle">
              <span v-if="simpleStep > idx">✓</span>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <span class="step-label">{{ step }}</span>
          </div>
        </div>

        <!-- S0: Use case -->
        <div v-if="simpleStep === 0" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>What will you use it for?</h3></div>
            <p class="step-desc">Pick the primary use case — we'll choose the best model for you.</p>
            <div class="simple-grid">
              <div
                :class="['simple-card', { selected: simpleAnswers.useCase === 'chat' }]"
                @click="simpleAnswers.useCase = 'chat'; simpleNext()"
              >
                <div class="simple-icon">&#128172;</div>
                <div class="simple-label">Chat &amp; Q&amp;A</div>
                <div class="simple-desc">General conversation and question answering</div>
              </div>
              <div
                :class="['simple-card', { selected: simpleAnswers.useCase === 'code' }]"
                @click="simpleAnswers.useCase = 'code'; simpleNext()"
              >
                <div class="simple-icon">&#128187;</div>
                <div class="simple-label">Coding Helper</div>
                <div class="simple-desc">Generate, explain and review code</div>
              </div>
              <div
                :class="['simple-card', { selected: simpleAnswers.useCase === 'docs' }]"
                @click="simpleAnswers.useCase = 'docs'; simpleNext()"
              >
                <div class="simple-icon">&#128196;</div>
                <div class="simple-label">Document Analysis</div>
                <div class="simple-desc">Summarise and extract info from documents</div>
              </div>
              <div
                :class="['simple-card', { selected: simpleAnswers.useCase === 'reasoning' }]"
                @click="simpleAnswers.useCase = 'reasoning'; simpleNext()"
              >
                <div class="simple-icon">&#129504;</div>
                <div class="simple-label">Research &amp; Reasoning</div>
                <div class="simple-desc">Complex multi-step problems and analysis</div>
              </div>
              <div
                :class="['simple-card', { selected: simpleAnswers.useCase === 'memes' }]"
                @click="simpleAnswers.useCase = 'memes'; simpleNext()"
              >
                <div class="simple-icon">&#129315;</div>
                <div class="simple-label">Memes</div>
                <div class="simple-desc">Generate captions, jokes, and cursed content</div>
              </div>
            </div>
          </div>
        </div>

        <!-- S1: Quality -->
        <div v-if="simpleStep === 1" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Response quality?</h3></div>
            <p class="step-desc">Higher quality needs more RAM and disk. All options run without a GPU.</p>
            <div class="simple-grid">
              <div
                :class="['simple-card', { selected: simpleAnswers.quality === 'light' }]"
                @click="simpleAnswers.quality = 'light'; simpleNext()"
              >
                <div class="simple-icon">&#9889;</div>
                <div class="simple-label">Fast &amp; Light</div>
                <div class="simple-desc">1–3B models · 4–8 GB RAM · Instant responses</div>
              </div>
              <div
                :class="['simple-card simple-card-recommended', { selected: simpleAnswers.quality === 'balanced' }]"
                @click="simpleAnswers.quality = 'balanced'; simpleNext()"
              >
                <div class="simple-icon">&#9878;&#65039;</div>
                <div class="simple-label">Balanced <span class="badge-recommended">Recommended</span></div>
                <div class="simple-desc">7–8B models · 12–16 GB RAM · Best quality/speed ratio</div>
              </div>
              <div
                :class="['simple-card', { selected: simpleAnswers.quality === 'quality' }]"
                @click="simpleAnswers.quality = 'quality'; simpleNext()"
              >
                <div class="simple-icon">&#127775;</div>
                <div class="simple-label">High Quality</div>
                <div class="simple-desc">14B+ models · 24+ GB RAM · Best results</div>
              </div>
            </div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="simpleStep--">← Back</button>
          </div>
        </div>

        <!-- S2: GPU -->
        <div v-if="simpleStep === 2" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Do you have a GPU available?</h3></div>
            <p class="step-desc">A GPU speeds up inference 5–20×. All configurations also work on CPU only.</p>
            <div class="simple-grid">
              <div
                :class="['simple-card', { selected: simpleAnswers.gpu === 'none' }]"
                @click="simpleAnswers.gpu = 'none'; simpleNext()"
              >
                <div class="simple-icon">&#128187;</div>
                <div class="simple-label">No GPU (CPU only)</div>
                <div class="simple-desc">Works on any server. Slightly slower inference.</div>
              </div>
              <div
                :class="['simple-card', { selected: simpleAnswers.gpu === 'nvidia' }]"
                @click="simpleAnswers.gpu = 'nvidia'; simpleNext()"
              >
                <div class="simple-icon">&#127381;</div>
                <div class="simple-label">NVIDIA GPU</div>
                <div class="simple-desc">GeForce, RTX, Tesla. Requires IOMMU enabled in Proxmox.</div>
              </div>
              <div
                :class="['simple-card', { selected: simpleAnswers.gpu === 'amd' }]"
                @click="simpleAnswers.gpu = 'amd'; simpleNext()"
              >
                <div class="simple-icon">&#128308;</div>
                <div class="simple-label">AMD GPU</div>
                <div class="simple-desc">Radeon RX / Instinct. Requires IOMMU enabled in Proxmox.</div>
              </div>
            </div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="simpleStep--">← Back</button>
          </div>
        </div>

        <!-- S3: Web UI -->
        <div v-if="simpleStep === 3" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Do you want a web interface?</h3></div>
            <p class="step-desc">Open WebUI gives you a ChatGPT-like browser interface. API-only is for developers.</p>
            <div class="simple-grid simple-grid-2">
              <div
                :class="['simple-card', { selected: simpleAnswers.webui === 'yes' }]"
                @click="simpleAnswers.webui = 'yes'; simpleNext()"
              >
                <div class="simple-icon">&#127760;</div>
                <div class="simple-label">Yes, Open WebUI</div>
                <div class="simple-desc">Browser chat interface on port 3000. No coding needed.</div>
              </div>
              <div
                :class="['simple-card', { selected: simpleAnswers.webui === 'no' }]"
                @click="simpleAnswers.webui = 'no'; simpleNext()"
              >
                <div class="simple-icon">&#128279;</div>
                <div class="simple-label">No, API Only</div>
                <div class="simple-desc">REST API on port 11434. For custom integrations.</div>
              </div>
            </div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="simpleStep--">← Back</button>
          </div>
        </div>

        <!-- S4: Auto-configuration summary -->
        <div v-if="simpleStep === 4" class="wizard-step">
          <div class="card simple-summary-card">
            <div class="card-header"><h3>Here's what we'll deploy</h3></div>
            <p class="step-desc">Based on your answers, we've selected the optimal configuration.</p>
            <div class="summary-grid">
              <div class="summary-item">
                <span class="summary-label">Model</span>
                <span class="summary-value">{{ simpleRec.modelName }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">Engine</span>
                <span class="summary-value">Ollama</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">Interface</span>
                <span class="summary-value">{{ simpleAnswers.webui === 'yes' ? 'Open WebUI (port 3000)' : 'API only (port 11434)' }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">Hardware</span>
                <span class="summary-value">{{ simpleAnswers.gpu === 'none' ? 'CPU only' : simpleAnswers.gpu.toUpperCase() + ' GPU' }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">CPU</span>
                <span class="summary-value">{{ simpleRec.cpu_cores }} cores</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">RAM</span>
                <span class="summary-value">{{ (simpleRec.memory / 1024).toFixed(0) }} GB</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">Disk</span>
                <span class="summary-value">{{ simpleRec.disk_size }} GB</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">OS</span>
                <span class="summary-value">Ubuntu 24.04 LTS</span>
              </div>
            </div>
            <div class="info-box" style="margin-top:1rem;">
              You can still adjust CPU, RAM, VM name, and networking in the next steps.
            </div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="simpleStep--">← Back</button>
            <button class="btn btn-primary" @click="applySimpleRec(); simpleStep++">Continue →</button>
          </div>
        </div>

        <!-- S5: Infrastructure (same as advanced step 5) -->
        <div v-if="simpleStep === 5" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Infrastructure</h3></div>
            <p class="step-desc">Select the Proxmox datacenter and node to deploy on.</p>

            <h4 class="section-label">Proxmox Datacenter</h4>
            <div class="host-grid">
              <div
                v-for="host in proxmoxHosts"
                :key="host.id"
                :class="['host-card', { selected: form.proxmox_host_id === host.id }]"
                @click="selectHost(host)"
              >
                <span class="host-name">{{ host.name }}</span>
                <span class="host-addr">{{ host.hostname }}</span>
              </div>
            </div>

            <template v-if="form.proxmox_host_id">
              <h4 class="section-label">Node</h4>
              <div v-if="nodesLoading" class="inline-loading">
                <div class="spinner small"></div> Loading nodes...
              </div>
              <div v-else class="node-grid">
                <div
                  v-for="node in nodes"
                  :key="node.id"
                  :class="['node-card', { selected: form.node_id === node.id }]"
                  @click="selectNode(node)"
                >
                  <span class="node-name">{{ node.node_name }}</span>
                  <div class="node-stats">
                    <span>CPU {{ node.cpu_usage || 0 }}%</span>
                    <span>RAM {{ formatBytes(node.memory_used) }} / {{ formatBytes(node.memory_total) }}</span>
                  </div>
                </div>
              </div>
            </template>

            <template v-if="form.node_id">
              <div class="grid grid-cols-2 gap-2" style="margin-top:1.5rem;">
                <div class="form-group">
                  <label class="form-label">Storage Pool *</label>
                  <div v-if="storageLoading" class="inline-loading">
                    <div class="spinner small"></div> Loading storage pools...
                  </div>
                  <div v-else-if="sortedStorageList.length === 0 && form.node_id" class="text-muted">
                    No image-capable storage found on this node
                  </div>
                  <div v-else class="storage-cards">
                    <div
                      v-for="s in sortedStorageList"
                      :key="s.storage"
                      :class="['storage-card', { selected: form.storage === s.storage, disabled: !s.enabled || !s.active }]"
                      @click="s.enabled && s.active ? form.storage = s.storage : null"
                    >
                      <div class="storage-header">
                        <h6>{{ s.storage }}</h6>
                        <span class="badge badge-sm badge-info">{{ s.type }}</span>
                      </div>
                      <div class="storage-info">
                        <div class="storage-bar">
                          <div class="storage-bar-fill" :style="{ width: getStorageUsagePercent(s) + '%' }"></div>
                        </div>
                        <div class="storage-stats">
                          <span>{{ formatBytes(s.available) }} free</span>
                          <span>{{ formatBytes(s.total) }} total</span>
                        </div>
                      </div>
                      <div v-if="s.shared" class="storage-badge">
                        <span class="badge badge-success">Shared</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="form-group">
                  <label class="form-label">Network Bridge</label>
                  <input v-model="form.network_bridge" class="form-control" placeholder="vmbr0 (default)" />
                </div>
              </div>
            </template>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="simpleStep--">← Back</button>
            <button class="btn btn-primary" :disabled="!infraValid" @click="simpleStep++">Next →</button>
          </div>
        </div>

        <!-- S6: Credentials -->
        <div v-if="simpleStep === 6" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>VM Identity &amp; Credentials</h3></div>

            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">VM Name *</label>
                <input v-model="form.vm_name" class="form-control" placeholder="llm-server" />
              </div>
              <div class="form-group">
                <label class="form-label">Hostname *</label>
                <input v-model="form.hostname" class="form-control" placeholder="llm-server" />
              </div>
            </div>

            <h4 class="section-label">Network</h4>
            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="useDhcp" /> Use DHCP (auto IP)
              </label>
            </div>
            <template v-if="!useDhcp">
              <div class="grid grid-cols-3 gap-2">
                <div class="form-group">
                  <label class="form-label">IP Address</label>
                  <input v-model="form.ip_address" class="form-control" placeholder="192.168.1.50" />
                </div>
                <div class="form-group">
                  <label class="form-label">Subnet Mask</label>
                  <input v-model="form.netmask" class="form-control" placeholder="24" />
                </div>
                <div class="form-group">
                  <label class="form-label">Gateway</label>
                  <input v-model="form.gateway" class="form-control" placeholder="192.168.1.1" />
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">DNS Servers</label>
                <input v-model="form.dns_servers" class="form-control" placeholder="8.8.8.8" />
              </div>
            </template>

            <h4 class="section-label">Admin Credentials</h4>
            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">Username *</label>
                <input v-model="form.username" class="form-control" placeholder="ubuntu" />
              </div>
              <div class="form-group">
                <label class="form-label">Password *</label>
                <input v-model="form.password" type="password" autocomplete="new-password" class="form-control" />
              </div>
            </div>

            <!-- Resources adjustable -->
            <h4 class="section-label">Resources (auto-suggested, adjust if needed)</h4>
            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">CPU Cores</label>
                <input v-model.number="form.cpu_cores" type="number" min="2" class="form-control" />
              </div>
              <div class="form-group">
                <label class="form-label">RAM (MB)</label>
                <input v-model.number="form.memory" type="number" min="2048" step="1024" class="form-control" />
                <small class="form-hint">{{ (form.memory / 1024).toFixed(1) }} GB</small>
              </div>
              <div class="form-group">
                <label class="form-label">Disk (GB)</label>
                <input v-model.number="form.disk_size" type="number" min="20" class="form-control" />
              </div>
            </div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="simpleStep--">← Back</button>
            <button class="btn btn-primary" :disabled="!networkCredsValid" @click="simpleStep++">Next →</button>
          </div>
        </div>

        <!-- S7: Review & Deploy -->
        <div v-if="simpleStep === 7" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Review &amp; Deploy</h3></div>
            <p class="step-desc">Review your configuration before deploying.</p>

            <div class="review-grid">
              <div class="review-section">
                <h4>AI Stack</h4>
                <table class="review-table">
                  <tr><td>Engine</td><td>Ollama</td></tr>
                  <tr><td>Model</td><td>{{ form.model }}</td></tr>
                  <tr><td>Interface</td><td>{{ uiLabel }}</td></tr>
                  <tr><td>GPU</td><td>{{ form.gpu_enabled ? (form.gpu_type || 'enabled') : 'CPU only' }}</td></tr>
                </table>
              </div>
              <div class="review-section">
                <h4>VM Configuration</h4>
                <table class="review-table">
                  <tr><td>Name</td><td>{{ form.vm_name }}</td></tr>
                  <tr><td>OS</td><td>Ubuntu 24.04 LTS</td></tr>
                  <tr><td>CPU</td><td>{{ form.cpu_cores }} cores</td></tr>
                  <tr><td>RAM</td><td>{{ (form.memory / 1024).toFixed(1) }} GB</td></tr>
                  <tr><td>Disk</td><td>{{ form.disk_size }} GB</td></tr>
                </table>
              </div>
              <div class="review-section">
                <h4>Infrastructure</h4>
                <table class="review-table">
                  <tr><td>Host</td><td>{{ selectedHostName }}</td></tr>
                  <tr><td>Node</td><td>{{ selectedNodeName }}</td></tr>
                  <tr><td>Storage</td><td>{{ form.storage || 'local-lvm' }}</td></tr>
                  <tr><td>Network</td><td>{{ form.ip_address || 'DHCP' }}</td></tr>
                </table>
              </div>
            </div>

            <div class="info-box">
              <strong>What happens after deploy:</strong> The VM will be created and booted. On first boot,
              Ollama installs and pulls the model automatically. This may take 10–30 minutes depending on
              network speed. Check progress at <code>/var/log/llm-setup.log</code> inside the VM.
              <span v-if="form.ui_type === 'open-webui'">
                Open WebUI will be available on port 3000 once setup completes.
              </span>
            </div>

            <div v-if="deployError" class="error-box">{{ deployError }}</div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="simpleStep--">← Back</button>
            <button class="btn btn-primary btn-deploy" :disabled="deploying" @click="deployLLM">
              <span v-if="deploying"><div class="spinner inline"></div> Deploying...</span>
              <span v-else>Deploy LLM</span>
            </button>
          </div>
        </div>

        <!-- S8: Deployment progress -->
        <div v-if="simpleStep === 8" class="wizard-step">
          <div class="card deploy-progress-card">
            <div class="deploy-progress-header">
              <div v-if="progressData && progressData.status === 'error'" class="deploy-status-icon deploy-icon-error">✗</div>
              <div v-else-if="progressData && progressData.status === 'running'" class="deploy-status-icon deploy-icon-done">✓</div>
              <div v-else class="deploy-status-icon deploy-icon-spinning"><div class="spinner"></div></div>
              <div>
                <h3 v-if="progressData && progressData.status === 'error'">Deployment Failed</h3>
                <h3 v-else-if="progressData && progressData.status === 'running'">VM is Live!</h3>
                <h3 v-else>Deploying...</h3>
                <p class="deploy-vm-subtitle">{{ form.vm_name }} &middot; {{ form.model }}</p>
              </div>
            </div>

            <div class="deploy-live-msg" v-if="progressData">
              <code>{{ progressData.status_message || 'Starting...' }}</code>
            </div>

            <div v-if="progressData && progressData.status === 'error'" class="deploy-error-box">
              {{ progressData.error_message || 'An error occurred during deployment.' }}
            </div>

            <div class="deploy-stages">
              <div v-for="(stage, idx) in [
                { label: 'Queued' },
                { label: 'Provisioning VM' },
                { label: 'Cloning disk image' },
                { label: 'Starting VM' },
                { label: 'VM running — LLM setup in progress', hint: 'Installing engine & pulling model inside VM. This takes 5–30 min.' }
              ]" :key="idx"
                :class="['deploy-stage',
                  progressData && progressData.status === 'error' ? 'stage-error' :
                  idx < getDeployStage() ? 'stage-done' :
                  idx === getDeployStage() ? 'stage-active' : 'stage-pending'
                ]"
              >
                <div class="stage-dot">
                  <span v-if="progressData && progressData.status !== 'error' && idx < getDeployStage()">✓</span>
                  <span v-else-if="idx === getDeployStage() && !(progressData && progressData.status === 'error')">
                    <div class="stage-spinner"></div>
                  </span>
                </div>
                <div class="stage-content">
                  <span class="stage-label">{{ stage.label }}</span>
                  <span v-if="stage.hint && idx === getDeployStage()" class="stage-hint">{{ stage.hint }}</span>
                </div>
              </div>
            </div>

            <div v-if="progressData && progressData.status === 'running' && deployedAccessUrl" class="access-url-box" style="margin-top:1.5rem;">
              <strong>Access URL (once model is ready):</strong><br />
              <a :href="deployedAccessUrl" target="_blank">{{ deployedAccessUrl }}</a>
            </div>

            <div class="success-actions" style="margin-top:1.5rem;">
              <router-link to="/vms" class="btn btn-primary">View VMs</router-link>
              <button v-if="progressData && (progressData.status === 'running' || progressData.status === 'error')"
                class="btn btn-secondary" @click="resetWizard">Deploy Another</button>
            </div>
          </div>
        </div>
      </template>

      <!-- ═══════════════════════════════════════════════════════ -->
      <!-- ADVANCED MODE                                          -->
      <!-- ═══════════════════════════════════════════════════════ -->
      <template v-if="mode === 'advanced'">
        <!-- Back to mode selection -->
        <div class="mode-back-bar">
          <button class="mode-back-link" @click="resetToModePicker">← Back to mode selection</button>
          <span class="mode-badge mode-badge-advanced">Advanced Mode</span>
        </div>

        <!-- Step Progress Bar -->
        <div class="step-bar">
          <div
            v-for="(step, idx) in steps"
            :key="idx"
            :class="['step-item', { active: currentStep === idx, completed: currentStep > idx }]"
            @click="goToStep(idx)"
          >
            <div class="step-circle">
              <span v-if="currentStep > idx">✓</span>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <span class="step-label">{{ step }}</span>
          </div>
        </div>

        <!-- ─────────────── STEP 0: Engine ─────────────── -->
        <div v-if="currentStep === 0" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Choose Inference Engine</h3></div>
            <p class="step-desc">Select the software that will run your AI model.</p>
            <div class="option-grid">
              <div
                v-for="engine in catalog.engines"
                :key="engine.id"
                :class="['option-card', { selected: form.engine === engine.id }]"
                @click="selectEngine(engine.id)"
              >
                <div class="option-header">
                  <span class="option-name">{{ engine.name }}</span>
                  <span v-if="engine.recommended" class="badge-recommended">Recommended</span>
                  <span v-if="engine.gpu_required" class="badge-gpu">GPU Required</span>
                </div>
                <p class="option-desc">{{ engine.description }}</p>
              </div>
            </div>
          </div>
          <div class="wizard-nav">
            <span></span>
            <button class="btn btn-primary" :disabled="!form.engine" @click="next">Next →</button>
          </div>
        </div>

        <!-- ─────────────── STEP 1: Model ─────────────── -->
        <div v-if="currentStep === 1" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Choose Model</h3></div>
            <p class="step-desc">Pick the AI model to deploy. Resources are auto-suggested based on your selection.</p>

            <div class="category-tabs">
              <button
                v-for="cat in modelCategories"
                :key="cat"
                :class="['tab-btn', { active: activeModelCategory === cat }]"
                @click="activeModelCategory = cat"
              >
                {{ cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1) }}
              </button>
            </div>

            <div class="model-grid">
              <div
                v-for="model in filteredModels"
                :key="model.id"
                :class="['model-card', { selected: form.model === model.id }]"
                @click="selectModel(model)"
              >
                <div class="model-header">
                  <span class="model-name">{{ model.name }}</span>
                  <span class="model-size">{{ model.size_gb }} GB</span>
                </div>
                <p class="model-desc">{{ model.description }}</p>
                <div class="model-reqs">
                  <span class="req-item">
                    <strong>RAM:</strong> {{ model.min_ram_gb }}+ GB
                  </span>
                  <span class="req-item">
                    <strong>CPU:</strong> {{ model.min_cpu_cores }}+ cores
                  </span>
                  <span v-if="!model.gpu_optional" class="req-item req-gpu">
                    GPU required
                  </span>
                  <span v-else class="req-item req-opt">
                    GPU optional
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="prev">← Back</button>
            <button class="btn btn-primary" :disabled="!form.model" @click="next">Next →</button>
          </div>
        </div>

        <!-- ─────────────── STEP 2: Hardware ─────────────── -->
        <div v-if="currentStep === 2" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Hardware Profile</h3></div>
            <p class="step-desc">Choose between CPU-only or GPU-accelerated inference.</p>

            <div class="option-grid">
              <div
                :class="['option-card', { selected: !form.gpu_enabled }]"
                @click="setGpu(false)"
              >
                <div class="option-header">
                  <span class="option-name">CPU Only</span>
                </div>
                <p class="option-desc">Works on any server. Slower inference but no GPU setup required. Good for smaller models (≤8B).</p>
              </div>
              <div
                :class="['option-card', { selected: form.gpu_enabled }]"
                @click="setGpu(true)"
              >
                <div class="option-header">
                  <span class="option-name">GPU Accelerated</span>
                </div>
                <p class="option-desc">5–20× faster inference. Requires a GPU with IOMMU/passthrough enabled in Proxmox BIOS.</p>
              </div>
            </div>

            <!-- GPU type + device (only shown when GPU enabled) -->
            <template v-if="form.gpu_enabled">
              <div class="form-section-inner">
                <h4>GPU Type</h4>
                <div class="option-grid small">
                  <div
                    :class="['option-card small', { selected: form.gpu_type === 'nvidia' }]"
                    @click="selectGpuType('nvidia')"
                  >
                    <span class="option-name">NVIDIA (CUDA)</span>
                    <p class="option-desc">GeForce, RTX, Tesla, A-series</p>
                  </div>
                  <div
                    :class="['option-card small', { selected: form.gpu_type === 'amd' }]"
                    @click="selectGpuType('amd')"
                  >
                    <span class="option-name">AMD (ROCm)</span>
                    <p class="option-desc">Radeon RX / Instinct series</p>
                  </div>
                </div>
              </div>

              <!-- GPU device selection -->
              <div v-if="form.gpu_type && form.proxmox_host_id && form.node_id" class="form-section-inner">
                <h4>GPU Device</h4>
                <div v-if="gpuLoading" class="inline-loading">
                  <div class="spinner small"></div> Scanning for GPU devices...
                </div>
                <div v-else-if="gpuDevices.length === 0" class="info-box warning">
                  No GPU devices found on the selected node. Ensure IOMMU is enabled and a GPU is present.
                </div>
                <div v-else class="option-grid small">
                  <div
                    v-for="dev in gpuDevices"
                    :key="dev.id"
                    :class="['option-card small', { selected: form.gpu_device_id === dev.id }]"
                    @click="form.gpu_device_id = dev.id"
                  >
                    <span class="option-name">{{ dev.name }}</span>
                    <p class="option-desc">PCI: {{ dev.id }} | IOMMU group: {{ dev.iommugroup }}</p>
                  </div>
                </div>
              </div>

              <div v-if="form.gpu_enabled && (!form.proxmox_host_id || !form.node_id)" class="info-box">
                Complete the Infrastructure step first to scan for GPU devices.
              </div>
            </template>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="prev">← Back</button>
            <button class="btn btn-primary" :disabled="!hardwareValid" @click="next">Next →</button>
          </div>
        </div>

        <!-- ─────────────── STEP 3: OS ─────────────── -->
        <div v-if="currentStep === 3" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Operating System</h3></div>
            <p class="step-desc">Select the OS for your LLM VM. Ubuntu is required for cloud-image deployment.</p>
            <div class="option-grid">
              <div
                v-for="os in catalog.os_options"
                :key="os.id"
                :class="['option-card', { selected: form.os_variant === os.id }]"
                @click="form.os_variant = os.id"
              >
                <div class="option-header">
                  <span class="option-name">{{ os.name }}</span>
                  <span v-if="os.recommended" class="badge-recommended">Recommended</span>
                </div>
                <p class="option-desc">{{ os.description }}</p>
              </div>
            </div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="prev">← Back</button>
            <button class="btn btn-primary" :disabled="!form.os_variant" @click="next">Next →</button>
          </div>
        </div>

        <!-- ─────────────── STEP 4: Web UI ─────────────── -->
        <div v-if="currentStep === 4" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Web Interface</h3></div>
            <p class="step-desc">Choose how you want to interact with your LLM.</p>
            <div class="option-grid">
              <div
                v-for="ui in catalog.ui_options"
                :key="ui.id"
                :class="['option-card', { selected: form.ui_type === ui.id }]"
                @click="form.ui_type = ui.id"
              >
                <div class="option-header">
                  <span class="option-name">{{ ui.name }}</span>
                  <span v-if="ui.recommended" class="badge-recommended">Recommended</span>
                  <span class="badge-port">:{{ ui.port }}</span>
                </div>
                <p class="option-desc">{{ ui.description }}</p>
              </div>
            </div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="prev">← Back</button>
            <button class="btn btn-primary" :disabled="!form.ui_type" @click="next">Next →</button>
          </div>
        </div>

        <!-- ─────────────── STEP 5: Infrastructure ─────────────── -->
        <div v-if="currentStep === 5" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Infrastructure</h3></div>
            <p class="step-desc">Select the Proxmox datacenter and node to deploy on.</p>

            <!-- Host selection -->
            <h4 class="section-label">Proxmox Datacenter</h4>
            <div class="host-grid">
              <div
                v-for="host in proxmoxHosts"
                :key="host.id"
                :class="['host-card', { selected: form.proxmox_host_id === host.id }]"
                @click="selectHost(host)"
              >
                <span class="host-name">{{ host.name }}</span>
                <span class="host-addr">{{ host.hostname }}</span>
              </div>
            </div>

            <!-- Node selection -->
            <template v-if="form.proxmox_host_id">
              <h4 class="section-label">Node</h4>
              <div v-if="nodesLoading" class="inline-loading">
                <div class="spinner small"></div> Loading nodes...
              </div>
              <div v-else class="node-grid">
                <div
                  v-for="node in nodes"
                  :key="node.id"
                  :class="['node-card', { selected: form.node_id === node.id }]"
                  @click="selectNode(node)"
                >
                  <span class="node-name">{{ node.node_name }}</span>
                  <div class="node-stats">
                    <span>CPU {{ node.cpu_usage || 0 }}%</span>
                    <span>RAM {{ formatBytes(node.memory_used) }} / {{ formatBytes(node.memory_total) }}</span>
                  </div>
                </div>
              </div>
            </template>

            <!-- Storage and network -->
            <template v-if="form.node_id">
              <div class="grid grid-cols-2 gap-2" style="margin-top:1.5rem;">
                <div class="form-group">
                  <label class="form-label">Storage Pool</label>
                  <input
                    v-model="form.storage"
                    class="form-control"
                    placeholder="local-lvm (default)"
                  />
                </div>
                <div class="form-group">
                  <label class="form-label">Network Bridge</label>
                  <input
                    v-model="form.network_bridge"
                    class="form-control"
                    placeholder="vmbr0 (default)"
                  />
                </div>
              </div>
            </template>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="prev">← Back</button>
            <button class="btn btn-primary" :disabled="!infraValid" @click="onInfraNext">Next →</button>
          </div>
        </div>

        <!-- ─────────────── STEP 6: Resources ─────────────── -->
        <div v-if="currentStep === 6" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Resource Allocation</h3></div>
            <p class="step-desc">
              Resources are auto-suggested based on <strong>{{ selectedModelInfo ? selectedModelInfo.name : form.model }}</strong>.
              Adjust as needed.
            </p>

            <div v-if="selectedModelInfo" class="info-box">
              <strong>Model requirements:</strong>
              RAM ≥ {{ selectedModelInfo.min_ram_gb }} GB ·
              CPU ≥ {{ selectedModelInfo.min_cpu_cores }} cores ·
              Disk ≥ {{ selectedModelInfo.min_disk_gb }} GB
              <span v-if="form.gpu_enabled"> · VRAM ≥ {{ selectedModelInfo.min_vram_gb }} GB</span>
            </div>

            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">CPU Cores *</label>
                <input v-model.number="form.cpu_cores" type="number" min="2" class="form-control" />
              </div>
              <div class="form-group">
                <label class="form-label">RAM (MB) *</label>
                <input v-model.number="form.memory" type="number" min="2048" step="1024" class="form-control" />
                <small class="form-hint">{{ (form.memory / 1024).toFixed(1) }} GB</small>
              </div>
              <div class="form-group">
                <label class="form-label">Disk (GB) *</label>
                <input v-model.number="form.disk_size" type="number" min="20" class="form-control" />
              </div>
            </div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="prev">← Back</button>
            <button class="btn btn-primary" :disabled="!resourcesValid" @click="next">Next →</button>
          </div>
        </div>

        <!-- ─────────────── STEP 7: Network & Credentials ─────────────── -->
        <div v-if="currentStep === 7" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Network &amp; Credentials</h3></div>

            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">VM Name *</label>
                <input v-model="form.vm_name" class="form-control" placeholder="llm-server" />
              </div>
              <div class="form-group">
                <label class="form-label">Hostname *</label>
                <input v-model="form.hostname" class="form-control" placeholder="llm-server" />
              </div>
            </div>

            <h4 class="section-label">Network</h4>
            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="useDhcp" /> Use DHCP (auto IP)
              </label>
            </div>

            <template v-if="!useDhcp">
              <div class="grid grid-cols-3 gap-2">
                <div class="form-group">
                  <label class="form-label">IP Address</label>
                  <input v-model="form.ip_address" class="form-control" placeholder="192.168.1.50" />
                </div>
                <div class="form-group">
                  <label class="form-label">Subnet Mask</label>
                  <input v-model="form.netmask" class="form-control" placeholder="24" />
                </div>
                <div class="form-group">
                  <label class="form-label">Gateway</label>
                  <input v-model="form.gateway" class="form-control" placeholder="192.168.1.1" />
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">DNS Servers</label>
                <input v-model="form.dns_servers" class="form-control" placeholder="8.8.8.8" />
              </div>
            </template>

            <h4 class="section-label">Admin Credentials</h4>
            <div class="grid grid-cols-2 gap-2">
              <div class="form-group">
                <label class="form-label">Username *</label>
                <input v-model="form.username" class="form-control" placeholder="ubuntu" />
              </div>
              <div class="form-group">
                <label class="form-label">Password *</label>
                <input v-model="form.password" type="password" autocomplete="new-password" class="form-control" />
              </div>
            </div>
          </div>
          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="prev">← Back</button>
            <button class="btn btn-primary" :disabled="!networkCredsValid" @click="next">Next →</button>
          </div>
        </div>

        <!-- ─────────────── STEP 8: Review & Deploy ─────────────── -->
        <div v-if="currentStep === 8" class="wizard-step">
          <div class="card">
            <div class="card-header"><h3>Review &amp; Deploy</h3></div>
            <p class="step-desc">Review your configuration before deploying.</p>

            <div class="review-grid">
              <div class="review-section">
                <h4>AI Stack</h4>
                <table class="review-table">
                  <tr><td>Engine</td><td>{{ engineLabel }}</td></tr>
                  <tr><td>Model</td><td>{{ selectedModelInfo ? selectedModelInfo.name : form.model }}</td></tr>
                  <tr><td>Interface</td><td>{{ uiLabel }}</td></tr>
                  <tr><td>GPU</td><td>{{ form.gpu_enabled ? (form.gpu_type || 'enabled') + (form.gpu_device_id ? ' – ' + form.gpu_device_id : '') : 'CPU only' }}</td></tr>
                </table>
              </div>

              <div class="review-section">
                <h4>VM Configuration</h4>
                <table class="review-table">
                  <tr><td>Name</td><td>{{ form.vm_name }}</td></tr>
                  <tr><td>OS</td><td>{{ osLabel }}</td></tr>
                  <tr><td>CPU</td><td>{{ form.cpu_cores }} cores</td></tr>
                  <tr><td>RAM</td><td>{{ (form.memory / 1024).toFixed(1) }} GB</td></tr>
                  <tr><td>Disk</td><td>{{ form.disk_size }} GB</td></tr>
                </table>
              </div>

              <div class="review-section">
                <h4>Infrastructure</h4>
                <table class="review-table">
                  <tr><td>Host</td><td>{{ selectedHostName }}</td></tr>
                  <tr><td>Node</td><td>{{ selectedNodeName }}</td></tr>
                  <tr><td>Storage</td><td>{{ form.storage || 'local-lvm' }}</td></tr>
                  <tr><td>Network</td><td>{{ form.ip_address || 'DHCP' }}</td></tr>
                </table>
              </div>
            </div>

            <div class="info-box">
              <strong>What happens after deploy:</strong> The VM will be created and booted. On first boot,
              the setup script installs the LLM engine and pulls the model automatically.
              Depending on model size and network speed, this may take 10–60 minutes.
              Track progress at <code>/var/log/llm-setup.log</code> inside the VM.
              <span v-if="form.ui_type === 'open-webui'">
                Open WebUI will be available on port 3000 once setup completes.
              </span>
            </div>

            <div v-if="deployError" class="error-box">
              {{ deployError }}
            </div>
          </div>

          <div class="wizard-nav">
            <button class="btn btn-secondary" @click="prev">← Back</button>
            <button
              class="btn btn-primary btn-deploy"
              :disabled="deploying"
              @click="deployLLM"
            >
              <span v-if="deploying"><div class="spinner inline"></div> Deploying...</span>
              <span v-else>Deploy LLM</span>
            </button>
          </div>
        </div>

        <!-- ─────────────── STEP 9: Deployment progress ─────────────── -->
        <div v-if="currentStep === 9" class="wizard-step">
          <div class="card deploy-progress-card">
            <div class="deploy-progress-header">
              <div v-if="progressData && progressData.status === 'error'" class="deploy-status-icon deploy-icon-error">✗</div>
              <div v-else-if="progressData && progressData.status === 'running'" class="deploy-status-icon deploy-icon-done">✓</div>
              <div v-else class="deploy-status-icon deploy-icon-spinning"><div class="spinner"></div></div>
              <div>
                <h3 v-if="progressData && progressData.status === 'error'">Deployment Failed</h3>
                <h3 v-else-if="progressData && progressData.status === 'running'">VM is Live!</h3>
                <h3 v-else>Deploying...</h3>
                <p class="deploy-vm-subtitle">{{ form.vm_name }} &middot; {{ selectedModelInfo ? selectedModelInfo.name : form.model }}</p>
              </div>
            </div>

            <div class="deploy-live-msg" v-if="progressData">
              <code>{{ progressData.status_message || 'Starting...' }}</code>
            </div>

            <div v-if="progressData && progressData.status === 'error'" class="deploy-error-box">
              {{ progressData.error_message || 'An error occurred during deployment.' }}
            </div>

            <div class="deploy-stages">
              <div v-for="(stage, idx) in [
                { label: 'Queued' },
                { label: 'Provisioning VM' },
                { label: 'Cloning disk image' },
                { label: 'Starting VM' },
                { label: 'VM running — LLM setup in progress', hint: 'Installing engine & pulling model inside VM. This takes 5–30 min.' }
              ]" :key="idx"
                :class="['deploy-stage',
                  progressData && progressData.status === 'error' ? 'stage-error' :
                  idx < getDeployStage() ? 'stage-done' :
                  idx === getDeployStage() ? 'stage-active' : 'stage-pending'
                ]"
              >
                <div class="stage-dot">
                  <span v-if="progressData && progressData.status !== 'error' && idx < getDeployStage()">✓</span>
                  <span v-else-if="idx === getDeployStage() && !(progressData && progressData.status === 'error')">
                    <div class="stage-spinner"></div>
                  </span>
                </div>
                <div class="stage-content">
                  <span class="stage-label">{{ stage.label }}</span>
                  <span v-if="stage.hint && idx === getDeployStage()" class="stage-hint">{{ stage.hint }}</span>
                </div>
              </div>
            </div>

            <div v-if="progressData && progressData.status === 'running' && deployedAccessUrl" class="access-url-box" style="margin-top:1.5rem;">
              <strong>Access URL (once model is ready):</strong><br />
              <a :href="deployedAccessUrl" target="_blank">{{ deployedAccessUrl }}</a>
            </div>

            <div class="success-actions" style="margin-top:1.5rem;">
              <router-link to="/vms" class="btn btn-primary">View VMs</router-link>
              <button v-if="progressData && (progressData.status === 'running' || progressData.status === 'error')"
                class="btn btn-secondary" @click="resetWizard">Deploy Another</button>
            </div>
          </div>
        </div>
      </template>

    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

// Simple mode recommendation table
const SIMPLE_RECS = {
  'chat-light':      { model: 'llama3.2:1b',        modelName: 'Llama 3.2 1B',          cpu_cores: 2,  memory: 6144,  disk_size: 20 },
  'chat-balanced':   { model: 'llama3.2:3b',        modelName: 'Llama 3.2 3B',          cpu_cores: 4,  memory: 12288, disk_size: 25 },
  'chat-quality':    { model: 'llama3.1:8b',        modelName: 'Llama 3.1 8B',          cpu_cores: 8,  memory: 16384, disk_size: 40 },
  'code-light':      { model: 'llama3.2:3b',        modelName: 'Llama 3.2 3B',          cpu_cores: 4,  memory: 12288, disk_size: 25 },
  'code-balanced':   { model: 'codellama:7b',       modelName: 'Code Llama 7B',         cpu_cores: 8,  memory: 16384, disk_size: 35 },
  'code-quality':    { model: 'qwen2.5-coder:7b',   modelName: 'Qwen 2.5 Coder 7B',    cpu_cores: 8,  memory: 16384, disk_size: 35 },
  'docs-light':      { model: 'llama3.2:3b',        modelName: 'Llama 3.2 3B',          cpu_cores: 4,  memory: 12288, disk_size: 25 },
  'docs-balanced':   { model: 'llama3.1:8b',        modelName: 'Llama 3.1 8B',          cpu_cores: 8,  memory: 16384, disk_size: 40 },
  'docs-quality':    { model: 'llama3.1:8b',        modelName: 'Llama 3.1 8B',          cpu_cores: 8,  memory: 24576, disk_size: 40 },
  'reasoning-light':    { model: 'deepseek-r1:7b', modelName: 'DeepSeek R1 7B',       cpu_cores: 8,  memory: 16384, disk_size: 40 },
  'reasoning-balanced': { model: 'deepseek-r1:7b', modelName: 'DeepSeek R1 7B',       cpu_cores: 8,  memory: 16384, disk_size: 40 },
  'reasoning-quality':  { model: 'deepseek-r1:7b', modelName: 'DeepSeek R1 7B',       cpu_cores: 8,  memory: 16384, disk_size: 40 },
  'memes-light':        { model: 'llama3.2:1b',    modelName: 'Llama 3.2 1B',         cpu_cores: 2,  memory: 6144,  disk_size: 20 },
  'memes-balanced':     { model: 'llama3.2:3b',    modelName: 'Llama 3.2 3B',         cpu_cores: 4,  memory: 12288, disk_size: 25 },
  'memes-quality':      { model: 'llama3.1:8b',    modelName: 'Llama 3.1 8B',         cpu_cores: 8,  memory: 16384, disk_size: 40 },
}

export default {
  name: 'DeployLLM',

  setup() {
    const toast = useToast()

    // ── mode: null | 'simple' | 'advanced' ────────────────────────
    const mode = ref(null)

    // Advanced wizard steps
    const steps = [
      'Engine', 'Model', 'Hardware', 'OS',
      'Interface', 'Infrastructure', 'Resources', 'Network', 'Review'
    ]
    const currentStep = ref(0)

    // Simple wizard
    const simpleSteps = ['Use Case', 'Quality', 'GPU', 'Web UI', 'Summary', 'Infrastructure', 'Credentials', 'Review']
    const simpleStep = ref(0)
    const simpleAnswers = ref({ useCase: null, quality: null, gpu: null, webui: null })

    const loading = ref(true)
    const deploying = ref(false)
    const deployError = ref(null)
    const deployedAccessUrl = ref(null)
    const deployedVmId = ref(null)
    const progressData = ref(null)
    let progressInterval = null

    const catalog = ref({ engines: [], models: {}, os_options: [], ui_options: [] })
    const proxmoxHosts = ref([])
    const nodes = ref([])
    const nodesLoading = ref(false)
    const storageList = ref([])
    const storageLoading = ref(false)
    const gpuDevices = ref([])
    const gpuLoading = ref(false)

    const activeModelCategory = ref('all')
    const useDhcp = ref(true)

    // Shared form — used by BOTH modes
    const form = ref({
      engine: 'ollama',
      model: '',
      ui_type: 'open-webui',
      gpu_enabled: false,
      gpu_type: null,
      gpu_device_id: null,
      os_variant: 'ubuntu2404',
      proxmox_host_id: null,
      node_id: null,
      storage: '',
      network_bridge: '',
      vm_name: '',
      hostname: '',
      cpu_cores: 4,
      memory: 8192,
      disk_size: 40,
      ip_address: '',
      gateway: '',
      netmask: '',
      dns_servers: '',
      username: 'ubuntu',
      password: '',
      cloud_image_id: null,
    })

    // ── simple mode computed ───────────────────────────────────────
    const simpleRec = computed(() => {
      const key = `${simpleAnswers.value.useCase}-${simpleAnswers.value.quality}`
      return SIMPLE_RECS[key] || SIMPLE_RECS['chat-balanced']
    })

    // ── advanced computed ──────────────────────────────────────────
    const sortedStorageList = computed(() =>
      [...storageList.value]
        .filter(s => s.content && s.content.includes('images'))
        .sort((a, b) => a.storage.localeCompare(b.storage, undefined, { numeric: true, sensitivity: 'base' }))
    )

    function getStorageUsagePercent(storage) {
      if (!storage.total || storage.total === 0) return 0
      return Math.round((storage.used / storage.total) * 100)
    }

    const engineModels = computed(
      () => catalog.value.models[form.value.engine] || []
    )

    const modelCategories = computed(() => {
      const cats = new Set(['all'])
      engineModels.value.forEach(m => cats.add(m.category))
      return Array.from(cats)
    })

    const filteredModels = computed(() => {
      if (activeModelCategory.value === 'all') return engineModels.value
      return engineModels.value.filter(m => m.category === activeModelCategory.value)
    })

    const selectedModelInfo = computed(() =>
      engineModels.value.find(m => m.id === form.value.model) || null
    )

    const engineLabel = computed(
      () => catalog.value.engines.find(e => e.id === form.value.engine)?.name || form.value.engine
    )
    const uiLabel = computed(
      () => catalog.value.ui_options.find(u => u.id === form.value.ui_type)?.name || form.value.ui_type
    )
    const osLabel = computed(
      () => catalog.value.os_options.find(o => o.id === form.value.os_variant)?.name || form.value.os_variant
    )
    const selectedHostName = computed(
      () => proxmoxHosts.value.find(h => h.id === form.value.proxmox_host_id)?.name || '-'
    )
    const selectedNodeName = computed(
      () => nodes.value.find(n => n.id === form.value.node_id)?.node_name || '-'
    )

    const hardwareValid = computed(() => {
      if (!form.value.gpu_enabled) return true
      return !!form.value.gpu_type
    })

    const infraValid = computed(
      () => !!(form.value.proxmox_host_id && form.value.node_id)
    )

    const resourcesValid = computed(
      () => form.value.cpu_cores > 0 && form.value.memory >= 1024 && form.value.disk_size >= 10
    )

    const networkCredsValid = computed(() => {
      if (!form.value.vm_name || !form.value.hostname || !form.value.username || !form.value.password) return false
      if (!useDhcp.value && (!form.value.ip_address || !form.value.gateway || !form.value.netmask)) return false
      return true
    })

    // ── init ──────────────────────────────────────────────────────
    onMounted(async () => {
      await Promise.all([loadCatalog(), loadHosts()])
      loading.value = false
    })

    async function loadCatalog() {
      try {
        const res = await api.llm.getCatalog()
        catalog.value = res.data
      } catch (e) {
        toast.error('Failed to load LLM catalog')
      }
    }

    async function loadHosts() {
      try {
        const res = await api.proxmox.listHosts()
        proxmoxHosts.value = res.data
      } catch (e) {
        toast.error('Failed to load Proxmox hosts')
      }
    }

    async function loadNodes(hostId) {
      nodesLoading.value = true
      nodes.value = []
      try {
        const res = await api.proxmox.listNodes(hostId)
        nodes.value = res.data
      } catch (e) {
        toast.error('Failed to load nodes')
      } finally {
        nodesLoading.value = false
      }
    }

    async function loadGpuDevices() {
      if (!form.value.proxmox_host_id || !form.value.node_id) return
      gpuLoading.value = true
      gpuDevices.value = []
      try {
        const res = await api.llm.getGpuDevices(form.value.proxmox_host_id, form.value.node_id)
        gpuDevices.value = res.data.devices || []
      } catch (e) {
        toast.warning('Could not query GPU devices – IOMMU may not be enabled')
      } finally {
        gpuLoading.value = false
      }
    }

    // ── mode picker ───────────────────────────────────────────────
    function pickMode(m) {
      mode.value = m
      currentStep.value = 0
      simpleStep.value = 0
    }

    function resetToModePicker() {
      mode.value = null
      currentStep.value = 0
      simpleStep.value = 0
      simpleAnswers.value = { useCase: null, quality: null, gpu: null, webui: null }
    }

    // ── simple wizard navigation ──────────────────────────────────
    function simpleNext() {
      simpleStep.value++
    }

    function goToSimpleStep(idx) {
      if (idx < simpleStep.value) simpleStep.value = idx
    }

    // Apply simple recommendation to shared form before infrastructure step
    function applySimpleRec() {
      const rec = simpleRec.value
      form.value.engine = 'ollama'
      form.value.model = rec.model
      form.value.os_variant = 'ubuntu2404'
      form.value.cpu_cores = rec.cpu_cores
      form.value.memory = rec.memory
      form.value.disk_size = rec.disk_size

      // GPU settings from simple answers
      const gpuAnswer = simpleAnswers.value.gpu
      if (gpuAnswer === 'none') {
        form.value.gpu_enabled = false
        form.value.gpu_type = null
        form.value.gpu_device_id = null
      } else {
        form.value.gpu_enabled = true
        form.value.gpu_type = gpuAnswer  // 'nvidia' | 'amd'
        form.value.gpu_device_id = null
      }

      // Web UI
      form.value.ui_type = simpleAnswers.value.webui === 'yes' ? 'open-webui' : 'api-only'
    }

    // ── advanced wizard navigation ────────────────────────────────
    function goToStep(idx) {
      if (idx < currentStep.value) currentStep.value = idx
    }

    function next() {
      if (currentStep.value < steps.length) currentStep.value++
    }

    function prev() {
      if (currentStep.value > 0) currentStep.value--
    }

    function onInfraNext() {
      if (form.value.gpu_enabled && form.value.gpu_type) loadGpuDevices()
      next()
    }

    // ── selections ────────────────────────────────────────────────
    function selectEngine(id) {
      form.value.engine = id
      form.value.model = ''
      activeModelCategory.value = 'all'
    }

    function selectModel(model) {
      form.value.model = model.id
      form.value.cpu_cores = model.min_cpu_cores
      form.value.memory = model.recommended_ram_gb * 1024
      form.value.disk_size = model.min_disk_gb
      if (!model.gpu_optional && !form.value.gpu_enabled) {
        toast.warning(`${model.name} strongly recommends GPU acceleration.`)
      }
    }

    function setGpu(enabled) {
      form.value.gpu_enabled = enabled
      if (!enabled) {
        form.value.gpu_type = null
        form.value.gpu_device_id = null
      }
    }

    function selectGpuType(type) {
      form.value.gpu_type = type
      if (form.value.proxmox_host_id && form.value.node_id) loadGpuDevices()
    }

    function selectHost(host) {
      form.value.proxmox_host_id = host.id
      form.value.node_id = null
      nodes.value = []
      loadNodes(host.id)
    }

    async function loadStorage(nodeId) {
      storageLoading.value = true
      storageList.value = []
      form.value.storage = ''
      try {
        const res = await api.proxmox.getNodeStorage(nodeId)
        storageList.value = res.data.storage || []
        // Auto-select first images-capable storage
        const first = storageList.value.find(
          s => s.active && s.enabled && s.content && s.content.includes('images')
        )
        if (first) form.value.storage = first.storage
      } catch (e) {
        console.error('Failed to load storage:', e)
      } finally {
        storageLoading.value = false
      }
    }

    function selectNode(node) {
      form.value.node_id = node.id
      loadStorage(node.id)
      if (form.value.gpu_enabled && form.value.gpu_type) loadGpuDevices()
    }

    // ── progress polling ──────────────────────────────────────────
    async function pollProgress(vmId) {
      try {
        const res = await api.vms.getProgress(vmId)
        progressData.value = res.data
        // Stop polling on terminal states
        if (res.data.status === 'running' || res.data.status === 'error' || res.data.status === 'stopped') {
          if (progressInterval) { clearInterval(progressInterval); progressInterval = null }
        }
      } catch (e) {
        console.error('Progress poll failed:', e)
      }
    }

    function startProgressPolling(vmId) {
      deployedVmId.value = vmId
      progressData.value = null
      if (progressInterval) clearInterval(progressInterval)
      pollProgress(vmId)
      progressInterval = setInterval(() => pollProgress(vmId), 3000)
    }

    // Map current status/message to a stage index 0-4
    // 0=Queued, 1=Provisioning, 2=Cloning disk, 3=Starting VM, 4=VM running
    function getDeployStage() {
      if (!progressData.value) return 0
      const s = progressData.value.status
      const msg = (progressData.value.status_message || '').toLowerCase()
      if (s === 'running') return 4
      if (s === 'error') return -1
      if (msg.includes('starting') || msg.includes('waiting') || msg.includes('boot') ||
          msg.includes('cloud-init') || msg.includes('customizing') || msg.includes('finaliz')) return 3
      if (msg.includes('cloning') || msg.includes('template') || msg.includes('preparing cloud') ||
          msg.includes('cloud image') || msg.includes('setting up cloud') || msg.includes('validating storage')) return 2
      if (msg.includes('allocat') || msg.includes('connect') || msg.includes('locating') ||
          msg.includes('initializ') || msg.includes('proxmox') || msg.includes('establishing') ||
          msg.includes('creating vm')) return 1
      return 1
    }

    onUnmounted(() => { if (progressInterval) clearInterval(progressInterval) })

    // ── deploy ────────────────────────────────────────────────────
    async function deployLLM() {
      deploying.value = true
      deployError.value = null
      try {
        const payload = {
          engine: form.value.engine,
          model: form.value.model,
          ui_type: form.value.ui_type,
          gpu_enabled: form.value.gpu_enabled,
          gpu_type: form.value.gpu_enabled ? form.value.gpu_type : null,
          gpu_device_id: form.value.gpu_enabled ? form.value.gpu_device_id : null,
          os_variant: form.value.os_variant,
          cloud_image_id: form.value.cloud_image_id || null,
          proxmox_host_id: form.value.proxmox_host_id,
          node_id: form.value.node_id,
          storage: form.value.storage || null,
          network_bridge: form.value.network_bridge || null,
          vm_name: form.value.vm_name,
          hostname: form.value.hostname,
          cpu_cores: form.value.cpu_cores,
          memory: form.value.memory,
          disk_size: form.value.disk_size,
          ip_address: useDhcp.value ? null : form.value.ip_address,
          gateway: useDhcp.value ? null : form.value.gateway,
          netmask: useDhcp.value ? null : form.value.netmask,
          dns_servers: form.value.dns_servers || null,
          username: form.value.username,
          password: form.value.password,
        }

        const res = await api.llm.deploy(payload)
        deployedAccessUrl.value = res.data.access_url || null
        toast.success('LLM deployment started!')
        startProgressPolling(res.data.vm_id)

        // Advance to progress screen
        if (mode.value === 'simple') {
          simpleStep.value = 8
        } else {
          currentStep.value = steps.length
        }
      } catch (e) {
        deployError.value =
          e.response?.data?.detail || e.message || 'Deployment failed'
        toast.error('Deployment failed')
      } finally {
        deploying.value = false
      }
    }

    function resetWizard() {
      mode.value = null
      currentStep.value = 0
      simpleStep.value = 0
      simpleAnswers.value = { useCase: null, quality: null, gpu: null, webui: null }
      form.value = {
        engine: 'ollama', model: '', ui_type: 'open-webui',
        gpu_enabled: false, gpu_type: null, gpu_device_id: null,
        os_variant: 'ubuntu2404', proxmox_host_id: null, node_id: null,
        storage: '', network_bridge: '', vm_name: '', hostname: '',
        cpu_cores: 4, memory: 8192, disk_size: 40,
        ip_address: '', gateway: '', netmask: '', dns_servers: '',
        username: 'ubuntu', password: '', cloud_image_id: null,
      }
      deployedAccessUrl.value = null
      deployedVmId.value = null
      progressData.value = null
      if (progressInterval) { clearInterval(progressInterval); progressInterval = null }
      deployError.value = null
    }

    function formatBytes(bytes) {
      if (!bytes) return '0 GB'
      return (bytes / 1073741824).toFixed(1) + ' GB'
    }

    return {
      mode, steps, currentStep, simpleSteps, simpleStep, simpleAnswers, simpleRec,
      loading, deploying, deployError, deployedAccessUrl, deployedVmId, progressData, getDeployStage,
      catalog, proxmoxHosts, nodes, nodesLoading, storageList, storageLoading, sortedStorageList, gpuDevices, gpuLoading,
      activeModelCategory, useDhcp, form,
      engineModels, modelCategories, filteredModels, selectedModelInfo,
      engineLabel, uiLabel, osLabel, selectedHostName, selectedNodeName,
      hardwareValid, infraValid, resourcesValid, networkCredsValid,
      pickMode, resetToModePicker,
      simpleNext, goToSimpleStep, applySimpleRec,
      goToStep, next, prev, onInfraNext,
      selectEngine, selectModel, setGpu, selectGpuType, selectHost, selectNode,
      deployLLM, resetWizard, formatBytes, getStorageUsagePercent,
    }
  }
}
</script>

<style scoped>
/* ── page layout ────────────────────────────────────────── */
.deploy-llm-page { max-width: 900px; margin: 0 auto; }

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}
.page-header h2 { margin: 0.25rem 0 0; font-size: 1.6rem; }
.subtitle { color: #666; margin: 0; font-size: 0.9rem; }
.back-link { color: #3b82f6; text-decoration: none; font-size: 0.85rem; }

/* ── mode back bar ──────────────────────────────────────── */
.mode-back-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}
.mode-back-link {
  background: none;
  border: none;
  color: #3b82f6;
  font-size: 0.85rem;
  cursor: pointer;
  padding: 0;
  text-decoration: none;
}
.mode-back-link:hover { text-decoration: underline; }
.mode-badge {
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.mode-badge-advanced {
  background: #faf5ff;
  color: #7c3aed;
}

/* ── mode picker grid ───────────────────────────────────── */
.mode-picker-card { padding: 2rem; }
.mode-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-top: 1.5rem;
}
.mode-card {
  border: 2px solid #e5e7eb;
  border-radius: 14px;
  padding: 1.75rem 1.5rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.mode-card:hover {
  border-color: #3b82f6;
  background: #f0f9ff;
  box-shadow: 0 4px 16px rgba(59,130,246,0.1);
}
.mode-card-advanced:hover {
  border-color: #7c3aed;
  background: #faf5ff;
  box-shadow: 0 4px 16px rgba(124,58,237,0.1);
}
.mode-icon { font-size: 2rem; margin-bottom: 0.25rem; }
.mode-card h4 { margin: 0; font-size: 1.15rem; color: #111; }
.mode-card p { margin: 0; font-size: 0.88rem; color: #555; line-height: 1.5; }
.mode-features {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.mode-features li {
  font-size: 0.82rem;
  color: #374151;
  padding-left: 1.1rem;
  position: relative;
}
.mode-features li::before {
  content: '✓';
  position: absolute;
  left: 0;
  color: #3b82f6;
  font-weight: 700;
}
.mode-card-advanced .mode-features li::before { color: #7c3aed; }
.mode-cta {
  margin-top: auto;
  padding-top: 1rem;
  font-size: 0.9rem;
  font-weight: 700;
  color: #3b82f6;
}
.mode-card-advanced .mode-cta { color: #7c3aed; }

/* ── simple mode cards ──────────────────────────────────── */
.simple-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}
.simple-grid-2 { grid-template-columns: 1fr 1fr; }

.simple-card {
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  padding: 1.25rem 1rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
  background: #fafafa;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
}
.simple-card:hover {
  border-color: #3b82f6;
  background: #f0f9ff;
  box-shadow: 0 2px 10px rgba(59,130,246,0.1);
}
.simple-card.selected {
  border-color: #3b82f6;
  background: #eff6ff;
}
.simple-card-recommended {
  border-color: #bbf7d0;
  background: #f0fdf4;
}
.simple-card-recommended:hover {
  border-color: #22c55e;
  background: #dcfce7;
}
.simple-card-recommended.selected {
  border-color: #16a34a;
  background: #dcfce7;
}
.simple-icon { font-size: 1.8rem; }
.simple-label { font-weight: 700; font-size: 1rem; color: #111; }
.simple-desc { font-size: 0.82rem; color: #555; line-height: 1.4; }

/* ── simple summary ─────────────────────────────────────── */
.simple-summary-card { }
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-top: 1rem;
}
.summary-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.summary-label { font-size: 0.72rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; }
.summary-value { font-size: 0.95rem; font-weight: 600; color: #111; }

/* ── step progress bar ──────────────────────────────────── */
.step-bar {
  display: flex;
  gap: 0;
  margin-bottom: 2rem;
  overflow-x: auto;
  padding-bottom: 0.5rem;
}
.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
  min-width: 80px;
  cursor: pointer;
  position: relative;
  flex: 1;
}
.step-item::after {
  content: '';
  position: absolute;
  top: 14px;
  right: -50%;
  width: 100%;
  height: 2px;
  background: #e5e7eb;
  z-index: 0;
}
.step-item:last-child::after { display: none; }
.step-circle {
  width: 30px; height: 30px;
  border-radius: 50%;
  border: 2px solid #d1d5db;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.8rem; font-weight: 600;
  background: white;
  z-index: 1;
  position: relative;
}
.step-item.active .step-circle {
  border-color: #3b82f6;
  color: #3b82f6;
  background: #eff6ff;
}
.step-item.completed .step-circle {
  background: #3b82f6;
  border-color: #3b82f6;
  color: white;
}
.step-item.completed::after { background: #3b82f6; }
.step-label { font-size: 0.7rem; color: #6b7280; text-align: center; }
.step-item.active .step-label { color: #3b82f6; font-weight: 600; }

/* ── cards ──────────────────────────────────────────────── */
.card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}
.card-header { margin-bottom: 0.25rem; }
.card-header h3 { margin: 0; font-size: 1.2rem; }
.step-desc { color: #555; font-size: 0.9rem; margin: 0.25rem 0 1.5rem; }

/* ── option cards (engine, OS, UI) ──────────────────────── */
.option-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.option-grid.small { grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }

.option-card {
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  padding: 1rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  background: #fafafa;
}
.option-card.small { padding: 0.75rem; }
.option-card:hover { border-color: #93c5fd; background: #f0f9ff; }
.option-card.selected { border-color: #3b82f6; background: #eff6ff; }

.option-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}
.option-name { font-weight: 600; font-size: 0.95rem; }
.option-desc { color: #555; font-size: 0.85rem; margin: 0; }

/* ── model grid ─────────────────────────────────────────── */
.category-tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap; }
.tab-btn {
  padding: 0.35rem 0.8rem;
  border: 1px solid #d1d5db;
  border-radius: 20px;
  background: white;
  cursor: pointer;
  font-size: 0.8rem;
  color: #374151;
  transition: all 0.15s;
}
.tab-btn.active, .tab-btn:hover { background: #3b82f6; color: white; border-color: #3b82f6; }

.model-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.model-card {
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  padding: 1rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  background: #fafafa;
}
.model-card:hover { border-color: #93c5fd; background: #f0f9ff; }
.model-card.selected { border-color: #3b82f6; background: #eff6ff; }

.model-header { display: flex; justify-content: space-between; margin-bottom: 0.35rem; }
.model-name { font-weight: 600; font-size: 0.9rem; }
.model-size { font-size: 0.8rem; color: #888; }
.model-desc { color: #555; font-size: 0.82rem; margin: 0 0 0.6rem; }
.model-reqs { display: flex; gap: 0.6rem; flex-wrap: wrap; }
.req-item { font-size: 0.75rem; color: #555; }
.req-gpu { color: #dc2626; font-weight: 600; }
.req-opt { color: #059669; }

/* ── badges ─────────────────────────────────────────────── */
.badge-recommended {
  background: #d1fae5; color: #065f46;
  font-size: 0.7rem; font-weight: 600;
  padding: 0.1rem 0.5rem; border-radius: 10px;
}
.badge-gpu {
  background: #fef3c7; color: #92400e;
  font-size: 0.7rem; font-weight: 600;
  padding: 0.1rem 0.5rem; border-radius: 10px;
}
.badge-port {
  background: #e0e7ff; color: #3730a3;
  font-size: 0.7rem; font-weight: 600;
  padding: 0.1rem 0.5rem; border-radius: 10px;
  margin-left: auto;
}

/* ── host / node cards ──────────────────────────────────── */
.section-label { font-size: 0.9rem; font-weight: 600; margin: 1.2rem 0 0.6rem; color: #374151; }

.host-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 0.75rem; }
.host-card {
  border: 2px solid #e5e7eb; border-radius: 8px; padding: 0.75rem;
  cursor: pointer; transition: border-color 0.15s, background 0.15s;
  background: #fafafa;
}
.host-card:hover { border-color: #93c5fd; background: #f0f9ff; }
.host-card.selected { border-color: #3b82f6; background: #eff6ff; }
.host-name { display: block; font-weight: 600; font-size: 0.9rem; }
.host-addr { font-size: 0.8rem; color: #888; }

.storage-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1rem;
  margin-top: 0.5rem;
}
.storage-card {
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--background);
  position: relative;
}
.storage-card:hover { border-color: var(--primary-color); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
.storage-card.selected {
  border-color: var(--primary-color);
  background: linear-gradient(135deg, rgba(37,99,235,0.1), rgba(147,51,234,0.1));
}
.storage-card.disabled { opacity: 0.5; cursor: not-allowed; }
.storage-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.storage-header h6 { margin: 0; font-size: 1rem; font-weight: 600; }
.storage-bar { width: 100%; height: 8px; background: var(--border-color); border-radius: 4px; overflow: hidden; margin-bottom: 0.5rem; }
.storage-bar-fill { height: 100%; background: linear-gradient(90deg, var(--primary-color), var(--secondary-color)); transition: width 0.3s; }
.storage-stats { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary); }
.storage-info {}
.storage-badge { position: absolute; top: 0.5rem; right: 0.5rem; }

.node-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem; }
.node-card {
  border: 2px solid #e5e7eb; border-radius: 8px; padding: 0.75rem;
  cursor: pointer; transition: border-color 0.15s, background 0.15s;
  background: #fafafa;
}
.node-card:hover { border-color: #93c5fd; background: #f0f9ff; }
.node-card.selected { border-color: #3b82f6; background: #eff6ff; }
.node-name { display: block; font-weight: 600; font-size: 0.9rem; }
.node-stats { display: flex; gap: 1rem; font-size: 0.78rem; color: #666; margin-top: 0.25rem; }

/* ── forms ──────────────────────────────────────────────── */
.form-section-inner { margin-top: 1.25rem; }
.form-group { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 0.75rem; }
.form-label { font-size: 0.85rem; font-weight: 600; color: #374151; }
.form-control {
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.15s;
}
.form-control:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.1); }
.form-hint { font-size: 0.75rem; color: #888; }
.grid { display: grid; }
.grid-cols-2 { grid-template-columns: 1fr 1fr; }
.grid-cols-3 { grid-template-columns: 1fr 1fr 1fr; }
.gap-2 { gap: 1rem; }

/* ── info / warning / error boxes ───────────────────────── */
.info-box {
  background: #eff6ff; border: 1px solid #bfdbfe;
  border-radius: 8px; padding: 0.75rem 1rem;
  font-size: 0.85rem; color: #1e40af;
  margin: 1rem 0;
}
.info-box.warning { background: #fffbeb; border-color: #fde68a; color: #92400e; }
.error-box {
  background: #fee2e2; border: 1px solid #fca5a5;
  border-radius: 8px; padding: 0.75rem 1rem;
  font-size: 0.85rem; color: #991b1b;
  margin: 1rem 0;
}

/* ── review table ───────────────────────────────────────── */
.review-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem; margin-bottom: 1rem; }
.review-section h4 { font-size: 0.9rem; color: #374151; margin: 0 0 0.5rem; font-weight: 600; }
.review-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.review-table td { padding: 0.3rem 0.4rem; color: #555; }
.review-table td:first-child { font-weight: 600; color: #374151; white-space: nowrap; width: 40%; }

/* ── nav buttons ────────────────────────────────────────── */
.wizard-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}
.btn {
  padding: 0.6rem 1.4rem;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: background 0.15s, opacity 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-secondary { background: #f3f4f6; color: #374151; }
.btn-secondary:hover:not(:disabled) { background: #e5e7eb; }
.btn-deploy { padding: 0.7rem 2rem; font-size: 1rem; }

/* ── loading ────────────────────────────────────────────── */
.loading-card { text-align: center; padding: 3rem; }
.spinner {
  width: 28px; height: 28px;
  border: 3px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}
.spinner.small { width: 18px; height: 18px; border-width: 2px; }
.spinner.inline { margin: 0; }
@keyframes spin { to { transform: rotate(360deg); } }

.inline-loading { display: flex; align-items: center; gap: 0.6rem; font-size: 0.85rem; color: #555; }

/* ── success screen ─────────────────────────────────────── */
.success-card { text-align: center; padding: 3rem 2rem; }
.success-icon {
  width: 64px; height: 64px;
  background: #d1fae5;
  color: #065f46;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.8rem;
  margin: 0 auto 1rem;
  font-weight: 700;
}
.success-card h3 { margin: 0 0 0.5rem; font-size: 1.4rem; }
.success-card p { color: #555; margin: 0.25rem 0; }
.muted { font-size: 0.85rem; }
.access-url-box {
  background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 8px; padding: 1rem 1.5rem;
  margin: 1.5rem auto; max-width: 400px;
  font-size: 0.9rem;
}
.access-url-box a { color: #3b82f6; }
.success-actions { display: flex; gap: 1rem; justify-content: center; margin-top: 1.5rem; }

code {
  background: #f1f5f9;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-size: 0.85em;
  color: #374151;
}

/* ── deployment progress card ──────────────────────────── */
.deploy-progress-card { padding: 2rem; }
.deploy-progress-header { display: flex; align-items: center; gap: 1.25rem; margin-bottom: 1.25rem; }
.deploy-progress-header h3 { margin: 0 0 0.2rem; font-size: 1.3rem; }
.deploy-vm-subtitle { margin: 0; color: var(--text-secondary); font-size: 0.9rem; }
.deploy-status-icon {
  width: 3rem; height: 3rem; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.4rem; font-weight: 700; flex-shrink: 0;
}
.deploy-icon-done { background: #d1fae5; color: #059669; }
.deploy-icon-error { background: #fee2e2; color: #dc2626; }
.deploy-icon-spinning { background: #eff6ff; color: #3b82f6; }

.deploy-live-msg {
  background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 6px; padding: 0.6rem 1rem; margin-bottom: 1.5rem;
  font-size: 0.85rem; color: #475569; min-height: 2.2rem;
  transition: all 0.3s;
}
.deploy-live-msg code { background: none; padding: 0; font-size: 0.85rem; color: #475569; }

.deploy-error-box {
  background: #fef2f2; border: 1px solid #fecaca;
  border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem;
  color: #b91c1c; font-size: 0.9rem;
}

.deploy-stages { display: flex; flex-direction: column; gap: 0; margin: 0.5rem 0; }
.deploy-stage { display: flex; align-items: flex-start; gap: 1rem; padding: 0.6rem 0; position: relative; }
.deploy-stage:not(:last-child)::before {
  content: ''; position: absolute; left: 0.95rem; top: 2.2rem;
  width: 2px; height: calc(100% - 1rem); background: #e2e8f0;
}
.stage-done::before, .stage-active::before { background: #3b82f6 !important; }

.stage-dot {
  width: 2rem; height: 2rem; border-radius: 50%; border: 2px solid #d1d5db;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.75rem; font-weight: 700; flex-shrink: 0; background: white;
  z-index: 1;
}
.stage-done .stage-dot { border-color: #3b82f6; background: #3b82f6; color: white; }
.stage-active .stage-dot { border-color: #3b82f6; background: white; color: #3b82f6; }
.stage-error .stage-dot { border-color: #dc2626; background: #fee2e2; color: #dc2626; }

.stage-spinner {
  width: 14px; height: 14px; border: 2px solid #bfdbfe;
  border-top-color: #3b82f6; border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.stage-content { padding-top: 0.3rem; }
.stage-label { font-size: 0.9rem; font-weight: 500; color: #374151; }
.stage-pending .stage-label { color: #9ca3af; }
.stage-hint { display: block; font-size: 0.78rem; color: #6b7280; margin-top: 0.1rem; }

@media (max-width: 640px) {
  .mode-grid { grid-template-columns: 1fr; }
  .simple-grid { grid-template-columns: 1fr 1fr; }
  .summary-grid { grid-template-columns: 1fr 1fr; }
  .option-grid, .model-grid { grid-template-columns: 1fr; }
  .review-grid { grid-template-columns: 1fr; }
  .grid-cols-2, .grid-cols-3 { grid-template-columns: 1fr; }
}
</style>
