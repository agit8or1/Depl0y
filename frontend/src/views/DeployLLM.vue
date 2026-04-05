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

    <!-- Top-level tab bar -->
    <div class="top-tab-bar">
      <button :class="['top-tab', { active: topTab === 'catalog' }]" @click="topTab = 'catalog'">Model Catalog</button>
      <button :class="['top-tab', { active: topTab === 'deploy' }]" @click="topTab = 'deploy'">Deploy New</button>
      <button :class="['top-tab', { active: topTab === 'instances' }]" @click="switchToInstances()">
        Deployed Instances
        <span v-if="instancesCount > 0" class="tab-badge">{{ instancesCount }}</span>
      </button>
    </div>

    <!-- ═══════════════════════════════════════════════════════ -->
    <!-- MODEL CATALOG TAB                                      -->
    <!-- ═══════════════════════════════════════════════════════ -->
    <div v-if="topTab === 'catalog'" class="tab-panel">
      <div class="catalog-filters">
        <div class="filter-group">
          <label class="filter-label">Category</label>
          <div class="filter-pills">
            <button
              v-for="cat in catalogCategories"
              :key="cat.id"
              :class="['pill', { active: catalogCatFilter === cat.id }]"
              @click="catalogCatFilter = cat.id"
            >{{ cat.label }}</button>
          </div>
        </div>
        <div class="filter-group">
          <label class="filter-label">Size</label>
          <div class="filter-pills">
            <button :class="['pill', { active: catalogSizeFilter === 'all' }]" @click="catalogSizeFilter = 'all'">All</button>
            <button :class="['pill', { active: catalogSizeFilter === 'small' }]" @click="catalogSizeFilter = 'small'">&lt;2 GB</button>
            <button :class="['pill', { active: catalogSizeFilter === 'medium' }]" @click="catalogSizeFilter = 'medium'">2–8 GB</button>
            <button :class="['pill', { active: catalogSizeFilter === 'large' }]" @click="catalogSizeFilter = 'large'">&gt;8 GB</button>
          </div>
        </div>
      </div>

      <div v-for="cat in visibleCatalogCategories" :key="cat.id" class="catalog-section">
        <h3 class="catalog-section-title">{{ cat.icon }} {{ cat.label }}</h3>
        <div class="catalog-grid">
          <div
            v-for="m in cat.models"
            :key="m.id"
            :class="['catalog-card', { selected: selectedCatalogModels.includes(m.id) }]"
          >
            <div class="catalog-card-header">
              <span class="catalog-model-name">{{ m.name }}</span>
              <span :class="['catalog-model-size', m.size_gb >= 4 ? 'size-large' : '']">{{ m.size_gb }} GB</span>
            </div>
            <p class="catalog-model-desc">{{ m.description }}</p>
            <div class="catalog-model-meta">
              <span class="meta-chip">{{ m.params }}</span>
              <span class="meta-chip">{{ m.context_len }}</span>
              <span class="meta-chip vram">VRAM: {{ m.vram }}</span>
              <span v-if="m.size_gb >= 4" class="meta-chip ram-warn">8+ GB RAM req.</span>
            </div>
            <div class="catalog-card-footer">
              <button
                v-if="!selectedCatalogModels.includes(m.id)"
                class="btn btn-sm btn-outline"
                @click="addCatalogModel(m)"
              >+ Select</button>
              <button
                v-else
                class="btn btn-sm btn-selected"
                @click="removeCatalogModel(m.id)"
              >&#10003; Selected</button>
            </div>
          </div>
        </div>
      </div>

      <!-- RAM warning for selected models -->
      <div v-if="catalogRamWarning" class="catalog-ram-warning">
        <span class="ram-warning-icon">&#9888;</span>
        <div>
          <strong>RAM Warning:</strong> Selected models total <strong>{{ catalogSelectedTotalGb.toFixed(1) }} GB</strong> on disk.
          Ollama loads models into RAM — ensure your VM has at least <strong>{{ Math.ceil(catalogSelectedTotalGb + 2) }} GB RAM</strong> available.
          Models ≥ 4 GB each require 8+ GB RAM; consider deploying on a node with sufficient memory.
        </div>
        <div class="ram-threshold-control">
          <label>VM RAM (GB): <input type="number" v-model.number="catalogRamLimit" min="4" max="256" class="ram-limit-input" /></label>
        </div>
      </div>

      <div v-if="selectedCatalogModels.length > 0" class="catalog-selection-bar">
        <div class="catalog-selection-info">
          <span>{{ selectedCatalogModels.length }} model(s) selected</span>
          <span class="catalog-selection-size">{{ catalogSelectedTotalGb.toFixed(1) }} GB total</span>
        </div>
        <button class="btn btn-primary" @click="goDeployWithCatalogModels()">Deploy with selected models →</button>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════ -->
    <!-- DEPLOYED INSTANCES TAB                                 -->
    <!-- ═══════════════════════════════════════════════════════ -->
    <div v-if="topTab === 'instances'" class="tab-panel">
      <div class="instances-toolbar">
        <button class="btn btn-secondary btn-sm" @click="loadInstances()" :disabled="instancesLoading">
          <span v-if="instancesLoading"><div class="spinner inline small"></div></span>
          <span v-else>&#8635; Refresh</span>
        </button>
      </div>

      <div v-if="instancesLoading && instances.length === 0" class="card loading-card">
        <div class="spinner"></div>
        <p>Loading instances...</p>
      </div>

      <div v-else-if="instances.length === 0" class="card empty-state">
        <div class="empty-icon">&#129302;</div>
        <h3>No LLM instances found</h3>
        <p>VMs tagged with <code>llm</code> or <code>ai</code> will appear here.</p>
        <button class="btn btn-primary" @click="topTab = 'deploy'">Deploy your first LLM →</button>
      </div>

      <div v-else>
        <div
          v-for="inst in instances"
          :key="inst.vmid + '-' + inst.host_id"
          class="instance-card"
        >
          <div class="instance-header" @click="toggleInstance(inst)">
            <div class="instance-status-dot" :class="inst.status === 'running' ? 'dot-green' : 'dot-gray'"></div>
            <div class="instance-info">
              <span class="instance-name">{{ inst.name }}</span>
              <span class="instance-meta">
                {{ inst.host_name || 'host-' + inst.host_id }} / {{ inst.node }} / {{ inst.vmid }}
                <span v-if="inst.ip_address"> · {{ inst.ip_address }}</span>
                <span v-if="inst.engine"> · {{ inst.engine }}</span>
              </span>
            </div>
            <div class="instance-actions-quick">
              <a
                v-if="inst.ip_address && inst.status === 'running'"
                :href="'http://' + inst.ip_address + ':11434'"
                target="_blank"
                class="btn btn-xs btn-outline"
                title="Open Ollama REST API"
                @click.stop
              >Open API</a>
              <a
                v-if="inst.ip_address && inst.status === 'running' && inst.ui_type === 'open-webui'"
                :href="'http://' + inst.ip_address + ':3000'"
                target="_blank"
                class="btn btn-xs btn-outline"
                @click.stop
              >Open WebUI</a>
              <a
                v-if="inst.ip_address && inst.status === 'running' && (inst.engine === 'meme-maker')"
                :href="'http://' + inst.ip_address + ':8189'"
                target="_blank"
                class="btn btn-xs btn-outline"
                @click.stop
              >Meme Maker</a>
              <a
                v-if="inst.ip_address && inst.status === 'running' && (inst.engine === 'stable-diffusion' || inst.ui_type === 'comfyui')"
                :href="'http://' + inst.ip_address + ':8188'"
                target="_blank"
                class="btn btn-xs btn-outline"
                @click.stop
              >ComfyUI</a>
              <span :class="['status-badge', 'status-' + inst.status]">{{ inst.status }}</span>
            </div>
            <span class="expand-arrow">{{ expandedInstances.includes(inst.vmid) ? '▲' : '▼' }}</span>
          </div>

          <!-- Expanded panel -->
          <div v-if="expandedInstances.includes(inst.vmid)" class="instance-detail">
            <!-- Ollama status check -->
            <div v-if="!instStatus[inst.vmid]" class="inst-loading">
              <div class="spinner small"></div> Checking Ollama status...
            </div>

            <template v-else>
              <div v-if="!instStatus[inst.vmid].reachable" class="info-box warning">
                Ollama is not reachable: {{ instStatus[inst.vmid].error || 'offline' }}.
                The VM may still be starting or Ollama is not installed.
              </div>

              <template v-else>
                <!-- Instance header info row -->
                <div class="inst-info-row">
                  <div class="inst-info-chip">
                    <span class="inst-info-label">IP</span>
                    <span class="inst-info-value">{{ inst.ip_address || instStatus[inst.vmid].ip || '—' }}</span>
                  </div>
                  <div class="inst-info-chip">
                    <span class="inst-info-label">Ollama</span>
                    <span class="inst-info-value">{{ instVersions[inst.vmid] || 'loading...' }}</span>
                  </div>
                  <div v-if="inst.engine" class="inst-info-chip">
                    <span class="inst-info-label">Engine</span>
                    <span class="inst-info-value">{{ inst.engine }}</span>
                  </div>
                  <div v-if="inst.gpu_enabled" class="inst-info-chip inst-info-chip-gpu">
                    <span class="inst-info-label">GPU</span>
                    <span class="inst-info-value">{{ inst.gpu_type || 'enabled' }}</span>
                  </div>
                  <a
                    v-if="inst.ip_address"
                    :href="'http://' + inst.ip_address + ':11434'"
                    target="_blank"
                    class="btn btn-xs btn-outline inst-api-btn"
                  >Open API :11434</a>
                </div>

                <!-- Running models -->
                <div class="inst-section">
                  <h4 class="inst-section-title">Loaded in VRAM</h4>
                  <div v-if="instStatus[inst.vmid].models_loaded.length === 0" class="muted-text">No models currently loaded.</div>
                  <div v-else class="model-chip-row">
                    <div v-for="m in instStatus[inst.vmid].models_loaded" :key="m.name" class="model-chip loaded-chip">
                      <span>{{ m.name }}</span>
                      <span class="chip-size">{{ formatModelSize(m.size) }}</span>
                      <button class="btn-chip-action" @click="unloadModel(inst, m.name)" title="Unload from VRAM">&#9111;</button>
                    </div>
                  </div>
                </div>

                <!-- Installed models -->
                <div class="inst-section">
                  <h4 class="inst-section-title">Installed Models</h4>
                  <div v-if="instStatus[inst.vmid].models_installed.length === 0" class="muted-text">No models installed yet.</div>
                  <table v-else class="models-table">
                    <thead>
                      <tr><th>Model</th><th>Size</th><th>Modified</th><th></th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="m in instStatus[inst.vmid].models_installed" :key="m.name">
                        <td class="model-name-cell">{{ m.name }}</td>
                        <td class="model-size-cell">{{ formatModelSize(m.size) }}</td>
                        <td class="model-date-cell">{{ formatDate(m.modified_at) }}</td>
                        <td>
                          <button class="btn btn-xs btn-danger" @click="deleteModel(inst, m.name)">Delete</button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- Pull model -->
                <div class="inst-section">
                  <h4 class="inst-section-title">Pull Model</h4>
                  <!-- Quick-select popular models -->
                  <div class="pull-quick-select">
                    <span class="pull-quick-label">Quick select:</span>
                    <button
                      v-for="qm in QUICK_PULL_MODELS"
                      :key="qm.id"
                      :class="['btn btn-xs pull-quick-btn', pullModelInputs[inst.vmid] === qm.id ? 'pull-quick-btn-active' : 'btn-outline']"
                      @click="pullModelInputs[inst.vmid] = qm.id"
                      :title="qm.label"
                    >{{ qm.id }}</button>
                  </div>
                  <div class="pull-row" style="margin-top:0.5rem">
                    <input
                      v-model="pullModelInputs[inst.vmid]"
                      class="form-control pull-input"
                      placeholder="e.g. llama3.2:3b"
                      @keyup.enter="pullModel(inst)"
                    />
                    <button
                      class="btn btn-primary btn-sm"
                      :disabled="pullingModel[inst.vmid]"
                      @click="pullModel(inst)"
                    >
                      <span v-if="pullingModel[inst.vmid]"><div class="spinner inline small"></div> Pulling...</span>
                      <span v-else>Pull</span>
                    </button>
                  </div>
                  <!-- Pull progress -->
                  <div v-if="pullProgress[inst.vmid]" class="pull-progress-box">
                    <div class="pull-progress-status">{{ pullProgress[inst.vmid].status }}</div>
                    <div v-if="pullProgress[inst.vmid].total" class="pull-progress-bar-wrap">
                      <div class="pull-progress-bar" :style="{ width: Math.round((pullProgress[inst.vmid].completed / pullProgress[inst.vmid].total) * 100) + '%' }"></div>
                    </div>
                    <div v-if="pullProgress[inst.vmid].error" class="error-box">{{ pullProgress[inst.vmid].error }}</div>
                  </div>
                </div>
              </template>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="topTab === 'deploy' && loading" class="card loading-card">
      <div class="spinner"></div>
      <p>Loading catalog...</p>
    </div>

    <template v-if="topTab === 'deploy' && !loading">

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
                <li>Best engine auto-selected for your use case</li>
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
                <div class="simple-icon">&#127912;</div>
                <div class="simple-label">Humor &amp; Memes</div>
                <div class="simple-desc">Generate meme images using Stable Diffusion AI (ComfyUI on port 8188)</div>
              </div>
            </div>
          </div>
        </div>

        <!-- S1: Model / Quality picker -->
        <div v-if="simpleStep === 1" class="wizard-step">
          <div class="card">
            <!-- LLM use cases: show model cards -->
            <template v-if="simpleAnswers.useCase !== 'memes'">
              <div class="card-header"><h3>Choose a model</h3></div>
              <p class="step-desc">Click any model to select it and continue. All run without a GPU — GPU speeds up inference 5–20×.</p>

              <div v-for="tier in ['light', 'balanced', 'quality']" :key="tier" class="model-tier-group">
                <div class="model-tier-label">
                  <span v-if="tier === 'light'">&#9889; Fast &amp; Light</span>
                  <span v-else-if="tier === 'balanced'">&#9878;&#65039; Balanced</span>
                  <span v-else>&#127775; High Quality</span>
                </div>
                <div class="model-pick-grid">
                  <div
                    v-for="m in (USE_CASE_MODELS[simpleAnswers.useCase] || []).filter(x => x.tier === tier)"
                    :key="m.model"
                    :class="['model-pick-card', { selected: simpleAnswers.model === m.model }]"
                    @click="selectSimpleModel(m)"
                  >
                    <div class="model-pick-header">
                      <span class="model-pick-name">{{ m.modelName }}</span>
                      <span v-if="m.recommended" class="badge-recommended">Recommended</span>
                      <span class="model-pick-size">{{ m.size }}</span>
                    </div>
                    <div class="model-pick-desc">{{ m.desc }}</div>
                    <div class="model-pick-meta">{{ m.memory / 1024 }} GB RAM &middot; {{ m.cpu_cores }} CPU</div>
                  </div>
                </div>
              </div>
            </template>

            <!-- Memes: image quality tier picker -->
            <template v-else>
              <div class="card-header"><h3>Image quality?</h3></div>
              <p class="step-desc">Higher quality needs more RAM and disk. A GPU is strongly recommended for image generation.</p>
              <div class="simple-grid">
                <div :class="['simple-card', { selected: simpleAnswers.quality === 'light' }]"
                  @click="simpleAnswers.quality = 'light'; simpleNext()">
                  <div class="simple-icon">&#9889;</div>
                  <div class="simple-label">Fast &amp; Light</div>
                  <div class="simple-desc">SD v1.5 · 8 GB RAM · CPU-capable, GPU faster</div>
                </div>
                <div :class="['simple-card simple-card-recommended', { selected: simpleAnswers.quality === 'balanced' }]"
                  @click="simpleAnswers.quality = 'balanced'; simpleNext()">
                  <div class="simple-icon">&#9878;&#65039;</div>
                  <div class="simple-label">Balanced <span class="badge-recommended">Recommended</span></div>
                  <div class="simple-desc">DreamShaper 8 · 12 GB RAM · GPU recommended</div>
                </div>
                <div :class="['simple-card', { selected: simpleAnswers.quality === 'quality' }]"
                  @click="simpleAnswers.quality = 'quality'; simpleNext()">
                  <div class="simple-icon">&#127775;</div>
                  <div class="simple-label">High Quality</div>
                  <div class="simple-desc">SDXL · 24 GB RAM · GPU required</div>
                </div>
              </div>
            </template>
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
            <!-- Memes: choose between Meme Maker AI or raw ComfyUI -->
            <template v-if="simpleAnswers.useCase === 'memes'">
              <div class="card-header"><h3>How would you like to use it?</h3></div>
              <p class="step-desc">Pick the interface that suits you. You can always SSH in to use the other one later.</p>
              <div class="simple-grid">
                <div
                  :class="['simple-card simple-card-recommended', { selected: simpleAnswers.webui === 'meme-maker' }]"
                  @click="simpleAnswers.webui = 'meme-maker'; simpleNext()"
                >
                  <div class="simple-icon">&#127917;</div>
                  <div class="simple-label">Meme Maker AI <span class="badge-recommended">New</span></div>
                  <div class="simple-desc">Simple web UI on port 8189. Enter a topic, AI suggests captions, generates the image. No technical knowledge needed. Includes ComfyUI + Ollama.</div>
                </div>
                <div
                  :class="['simple-card', { selected: simpleAnswers.webui === 'comfyui' }]"
                  @click="simpleAnswers.webui = 'comfyui'; simpleNext()"
                >
                  <div class="simple-icon">&#127912;</div>
                  <div class="simple-label">ComfyUI (Advanced)</div>
                  <div class="simple-desc">Professional node-based workflow editor on port 8188. Full control over the generation pipeline. Best for power users.</div>
                </div>
              </div>
            </template>
            <!-- All other use cases: Open WebUI vs API -->
            <template v-else>
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
            </template>
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
                <span class="summary-value">
                  <template v-if="simpleAnswers.webui === 'meme-maker'">Meme Maker (ComfyUI + Ollama)</template>
                  <template v-else-if="simpleAnswers.useCase === 'memes'">Stable Diffusion (ComfyUI)</template>
                  <template v-else>Ollama</template>
                </span>
              </div>
              <div class="summary-item">
                <span class="summary-label">Interface</span>
                <span class="summary-value">
                  <template v-if="simpleAnswers.webui === 'meme-maker'">Meme Maker UI (port 8189)</template>
                  <template v-else-if="simpleAnswers.useCase === 'memes'">ComfyUI (port 8188)</template>
                  <template v-else-if="simpleAnswers.webui === 'yes'">Open WebUI (port 3000)</template>
                  <template v-else>API only (port 11434)</template>
                </span>
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
            <div class="form-group">
              <label class="form-label">SSH Public Key <span class="form-label-optional">(optional)</span></label>
              <textarea
                v-model="form.ssh_public_key"
                class="form-control ssh-key-input"
                placeholder="ssh-rsa AAAA... user@host"
                rows="3"
              ></textarea>
              <small class="form-hint">Paste your public key for passwordless SSH login (cloud-init)</small>
            </div>

            <!-- Resources adjustable -->
            <h4 class="section-label">Resources (auto-suggested, adjust if needed)</h4>
            <div class="grid grid-cols-4 gap-2">
              <div class="form-group">
                <label class="form-label">Sockets</label>
                <select v-model.number="form.cpu_sockets" class="form-control">
                  <option :value="1">1</option>
                  <option :value="2">2</option>
                  <option :value="4">4</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Cores / socket</label>
                <input v-model.number="form.cpu_cores" type="number" min="1" class="form-control" />
                <small class="form-hint">{{ form.cpu_sockets * form.cpu_cores }} total</small>
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
            <div class="form-group" style="margin-top:0.5rem">
              <label class="form-label">CPU Type</label>
              <select v-model="form.cpu_type" class="form-control">
                <option value="host">host (passthrough — best performance)</option>
                <option value="x86-64-v2-AES">x86-64-v2-AES (portable)</option>
                <option value="x86-64-v2">x86-64-v2</option>
                <option value="kvm64">kvm64</option>
                <option value="qemu64">qemu64</option>
              </select>
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
                  <tr><td>Engine</td><td>{{ engineLabel }}</td></tr>
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
              <template v-if="simpleAnswers.webui === 'meme-maker'">
                ComfyUI (DreamShaper 8), Ollama (llama3.2:1b), and the Meme Maker web app install automatically.
                This may take 20–40 minutes. Open <strong>http://&lt;vm-ip&gt;:8189</strong> once setup completes.
              </template>
              <template v-else-if="simpleAnswers.useCase === 'memes'">
                ComfyUI and Stable Diffusion install automatically, then the model checkpoint downloads.
                This may take 20–60 minutes depending on model size and network speed.
                Access ComfyUI on port 8188 once setup completes.
              </template>
              <template v-else>
                the engine installs and pulls the model automatically. This may take 10–30 minutes depending on
                network speed.
                <span v-if="form.ui_type === 'open-webui'">
                  Open WebUI will be available on port 3000 once setup completes.
                </span>
              </template>
              Check progress at <code>/var/log/llm-setup.log</code> inside the VM.
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

            <!-- RAM warning if configured RAM is below model minimum -->
            <div v-if="selectedModelInfo && form.memory < selectedModelInfo.min_ram_gb * 1024" class="info-box warning" style="margin-top:0.5rem">
              <strong>&#9888; RAM Warning:</strong>
              Model <strong>{{ selectedModelInfo.name }}</strong> requires at least
              <strong>{{ selectedModelInfo.min_ram_gb }} GB RAM</strong> ({{ selectedModelInfo.min_ram_gb * 1024 }} MB),
              but you have only <strong>{{ (form.memory / 1024).toFixed(1) }} GB</strong> configured.
              Increase RAM or choose a smaller model to avoid OOM crashes.
            </div>

            <div class="grid grid-cols-3 gap-2">
              <div class="form-group">
                <label class="form-label">CPU Sockets</label>
                <select v-model.number="form.cpu_sockets" class="form-control">
                  <option :value="1">1 socket</option>
                  <option :value="2">2 sockets</option>
                  <option :value="4">4 sockets</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">CPU Cores (per socket) *</label>
                <input v-model.number="form.cpu_cores" type="number" min="1" class="form-control" />
                <small class="form-hint">{{ form.cpu_sockets * form.cpu_cores }} total vCPU{{ form.cpu_sockets * form.cpu_cores !== 1 ? 's' : '' }}</small>
              </div>
              <div class="form-group">
                <label class="form-label">CPU Type</label>
                <select v-model="form.cpu_type" class="form-control">
                  <option value="host">host (passthrough, best perf)</option>
                  <option value="x86-64-v2-AES">x86-64-v2-AES</option>
                  <option value="x86-64-v2">x86-64-v2</option>
                  <option value="kvm64">kvm64</option>
                  <option value="qemu64">qemu64</option>
                </select>
                <small class="form-hint">
                  <span v-if="form.cpu_type === 'host'">Best performance; disables live migration</span>
                  <span v-else>Portable across Proxmox hosts</span>
                </small>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2" style="margin-top:0.75rem">
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
            <div class="form-group">
              <label class="form-label">SSH Public Key <span class="form-label-optional">(optional)</span></label>
              <textarea
                v-model="form.ssh_public_key"
                class="form-control ssh-key-input"
                placeholder="ssh-rsa AAAA... user@host"
                rows="3"
              ></textarea>
              <small class="form-hint">Paste your public key for passwordless SSH login (cloud-init)</small>
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

// ─── Static model catalog for the catalog browser tab ────────────────────
const CATALOG_CATEGORIES = [
  {
    id: 'chat',
    label: 'Chat / General',
    icon: '💬',
    models: [
      { id: 'llama3.2:1b',    name: 'Llama 3.2 1B',       params: '1B',   size_gb: 0.8,  context_len: '128K', vram: '2 GB',  description: "Meta's smallest Llama 3.2. Fastest responses, minimal RAM. Great for quick Q&A and testing." },
      { id: 'llama3.2:3b',    name: 'Llama 3.2 3B',       params: '3B',   size_gb: 2.0,  context_len: '128K', vram: '3 GB',  description: 'Balanced speed and quality. Solid CPU-only choice for chat and document tasks.' },
      { id: 'llama3.2:8b',    name: 'Llama 3.2 8B',       params: '8B',   size_gb: 4.7,  context_len: '128K', vram: '6 GB',  description: "Meta's 8B Llama 3.2. Excellent quality-to-cost ratio. Ideal general-purpose model." },
      { id: 'qwen2.5:0.5b',   name: 'Qwen 2.5 0.5B',      params: '0.5B', size_gb: 0.4,  context_len: '32K',  vram: '1 GB',  description: 'Alibaba Qwen 2.5 ultra-small. Runs anywhere, good for simple completions.' },
      { id: 'qwen2.5:1.5b',   name: 'Qwen 2.5 1.5B',      params: '1.5B', size_gb: 1.0,  context_len: '32K',  vram: '2 GB',  description: 'Qwen 2.5 1.5B. Strong multilingual support for its size.' },
      { id: 'qwen2.5:3b',     name: 'Qwen 2.5 3B',        params: '3B',   size_gb: 1.9,  context_len: '32K',  vram: '3 GB',  description: 'Alibaba Qwen 2.5 3B. Excellent multilingual support, strong benchmarks.' },
      { id: 'qwen2.5:7b',     name: 'Qwen 2.5 7B',        params: '7B',   size_gb: 4.4,  context_len: '128K', vram: '5 GB',  description: 'Qwen 2.5 7B — among the best 7B models for multilingual tasks and reasoning.' },
      { id: 'phi3.5',         name: 'Phi-3.5 Mini',       params: '3.8B', size_gb: 2.2,  context_len: '128K', vram: '3 GB',  description: "Microsoft Phi-3.5 Mini. Surprisingly capable reasoning for its compact size." },
      { id: 'gemma2:2b',      name: 'Gemma 2 2B',         params: '2B',   size_gb: 1.6,  context_len: '8K',   vram: '2 GB',  description: "Google Gemma 2 2B. Very efficient for basic tasks, fast on CPU." },
      { id: 'gemma2:9b',      name: 'Gemma 2 9B',         params: '9B',   size_gb: 5.4,  context_len: '8K',   vram: '8 GB',  description: 'Google Gemma 2 9B. Strong quality with manageable resource needs.' },
    ],
  },
  {
    id: 'code',
    label: 'Code',
    icon: '💻',
    models: [
      { id: 'codellama:7b',         name: 'Code Llama 7B',        params: '7B',   size_gb: 3.8,  context_len: '16K',  vram: '5 GB',  description: "Meta's Code Llama 7B. Purpose-built for code generation, completion, and debugging." },
      { id: 'deepseek-coder:1.3b',  name: 'DeepSeek Coder 1.3B',  params: '1.3B', size_gb: 0.8,  context_len: '16K',  vram: '2 GB',  description: 'Lightweight DeepSeek Coder. Fast code completions on CPU.' },
      { id: 'deepseek-coder:6.7b',  name: 'DeepSeek Coder 6.7B',  params: '6.7B', size_gb: 3.8,  context_len: '16K',  vram: '5 GB',  description: 'DeepSeek Coder 6.7B. Excellent at multi-language code tasks.' },
      { id: 'qwen2.5-coder:1.5b',   name: 'Qwen2.5-Coder 1.5B',   params: '1.5B', size_gb: 1.0,  context_len: '32K',  vram: '2 GB',  description: 'Qwen2.5-Coder 1.5B. Strong coding benchmarks in a tiny package.' },
      { id: 'qwen2.5-coder:7b',     name: 'Qwen2.5-Coder 7B',     params: '7B',   size_gb: 4.4,  context_len: '128K', vram: '5 GB',  description: 'Qwen2.5-Coder 7B. Excellent across 92+ languages. Top coding benchmark scores.' },
    ],
  },
  {
    id: 'vision',
    label: 'Vision',
    icon: '👁️',
    models: [
      { id: 'llava:7b',      name: 'LLaVA 7B',     params: '7B',  size_gb: 4.5,  context_len: '4K',  vram: '6 GB',  description: 'LLaVA 7B — multimodal model for visual question answering and image understanding.' },
      { id: 'bakllava',      name: 'BakLLaVA',     params: '7B',  size_gb: 4.1,  context_len: '4K',  vram: '6 GB',  description: 'BakLLaVA — Mistral-based visual model. Capable image description and chat.' },
    ],
  },
  {
    id: 'reasoning',
    label: 'Reasoning',
    icon: '🧠',
    models: [
      { id: 'deepseek-r1:7b',  name: 'DeepSeek R1 7B',    params: '7B',   size_gb: 4.7,  context_len: '128K', vram: '5 GB',  description: 'DeepSeek R1 reasoning model. Shows chain-of-thought. Great for complex problems. Requires 8+ GB RAM.' },
      { id: 'deepseek-r1:1.5b', name: 'DeepSeek R1 1.5B',  params: '1.5B', size_gb: 1.1,  context_len: '128K', vram: '2 GB',  description: 'Compact reasoning model. Surprising CoT capability in a small package.' },
      { id: 'phi3:mini',        name: 'Phi-3 Mini',         params: '3.8B', size_gb: 2.3,  context_len: '128K', vram: '3 GB',  description: 'Microsoft Phi-3 Mini. Exceptional step-by-step reasoning for its size. Runs well on CPU.' },
      { id: 'mistral:7b',       name: 'Mistral 7B',         params: '7B',   size_gb: 4.1,  context_len: '32K',  vram: '5 GB',  description: 'Highly capable 7B model with strong reasoning. One of the most popular choices. Requires 8+ GB RAM.' },
    ],
  },
  {
    id: 'embedding',
    label: 'Embedding',
    icon: '🔢',
    models: [
      { id: 'nomic-embed-text',   name: 'Nomic Embed Text',   params: '137M', size_gb: 0.3, context_len: '8K',  vram: '0.5 GB', description: 'High-quality text embeddings for RAG pipelines and semantic search. Very fast.' },
      { id: 'mxbai-embed-large',  name: 'mxbai-embed-large',  params: '335M', size_gb: 0.7, context_len: '512', vram: '1 GB',   description: 'State-of-the-art sentence embeddings. Best retrieval quality for RAG.' },
    ],
  },
]

// Simple mode model choices per use-case
const USE_CASE_MODELS = {
  chat: [
    { model: 'llama3.2:1b',  modelName: 'Llama 3.2 1B',       tier: 'light',    desc: 'Fastest responses. Great for quick Q&A.',              size: '1.3 GB', cpu_cores: 2, memory: 6144,  disk_size: 20 },
    { model: 'phi3',          modelName: 'Phi-3 Mini',         tier: 'light',    desc: 'Microsoft. Surprisingly capable for its size.',        size: '2.2 GB', cpu_cores: 2, memory: 8192,  disk_size: 25 },
    { model: 'mistral',       modelName: 'Mistral 7B',         tier: 'balanced', desc: 'Fast and capable all-rounder.', size: '4.1 GB', cpu_cores: 4, memory: 12288, disk_size: 30, recommended: true },
    { model: 'llama3.1',      modelName: 'Llama 3.1 8B',       tier: 'balanced', desc: 'Meta. Strong reasoning, long context window.',         size: '4.7 GB', cpu_cores: 4, memory: 12288, disk_size: 35 },
    { model: 'gemma2',        modelName: 'Gemma 2 9B',         tier: 'balanced', desc: 'Google. Excellent quality-to-size ratio.',             size: '5.5 GB', cpu_cores: 4, memory: 16384, disk_size: 35 },
    { model: 'qwen2.5',       modelName: 'Qwen 2.5 7B',        tier: 'balanced', desc: 'Multilingual, strong benchmarks.',                     size: '4.7 GB', cpu_cores: 4, memory: 12288, disk_size: 35 },
    { model: 'llama3.1:70b',  modelName: 'Llama 3.1 70B',      tier: 'quality',  desc: 'Best-in-class quality. Requires ~48 GB RAM.',          size: '40 GB',  cpu_cores: 8, memory: 49152, disk_size: 80 },
  ],
  code: [
    { model: 'phi3',          modelName: 'Phi-3 Mini',         tier: 'light',    desc: 'Microsoft. Strong at code for its size.',              size: '2.2 GB', cpu_cores: 2, memory: 8192,  disk_size: 25 },
    { model: 'llama3.2:3b',   modelName: 'Llama 3.2 3B',       tier: 'light',    desc: 'Quick code snippets and explanations.',                size: '2 GB',   cpu_cores: 2, memory: 8192,  disk_size: 25 },
    { model: 'codellama',     modelName: 'Code Llama 7B',      tier: 'balanced', desc: 'Meta. Purpose-built for code generation.', size: '3.8 GB', cpu_cores: 4, memory: 12288, disk_size: 30, recommended: true },
    { model: 'qwen2.5',       modelName: 'Qwen 2.5 Coder 7B',  tier: 'balanced', desc: 'Top coding benchmark scores. Multi-language.',         size: '4.7 GB', cpu_cores: 4, memory: 12288, disk_size: 35 },
    { model: 'llama3.1',      modelName: 'Llama 3.1 8B',       tier: 'quality',  desc: 'Broad knowledge plus strong coding ability.',          size: '4.7 GB', cpu_cores: 8, memory: 16384, disk_size: 40 },
  ],
  docs: [
    { model: 'llama3.2:3b',   modelName: 'Llama 3.2 3B',       tier: 'light',    desc: 'Fast summaries of short documents.',                   size: '2 GB',   cpu_cores: 2, memory: 8192,  disk_size: 25 },
    { model: 'mistral',       modelName: 'Mistral 7B',         tier: 'balanced', desc: 'Good at extraction and summarization.',                size: '4.1 GB', cpu_cores: 4, memory: 12288, disk_size: 30 },
    { model: 'llama3.1',      modelName: 'Llama 3.1 8B',       tier: 'balanced', desc: 'Long context, accurate analysis.', size: '4.7 GB', cpu_cores: 4, memory: 12288, disk_size: 35, recommended: true },
    { model: 'gemma2',        modelName: 'Gemma 2 9B',         tier: 'quality',  desc: 'Google. Thorough, structured analysis.',               size: '5.5 GB', cpu_cores: 8, memory: 16384, disk_size: 40 },
    { model: 'llama3.1:70b',  modelName: 'Llama 3.1 70B',      tier: 'quality',  desc: 'Maximum comprehension. ~48 GB RAM.',                   size: '40 GB',  cpu_cores: 8, memory: 49152, disk_size: 80 },
  ],
  reasoning: [
    { model: 'phi3',          modelName: 'Phi-3 Mini',         tier: 'light',    desc: 'Microsoft. Efficient step-by-step reasoning.',         size: '2.2 GB', cpu_cores: 2, memory: 8192,  disk_size: 25 },
    { model: 'deepseek-r1',   modelName: 'DeepSeek R1 7B',     tier: 'balanced', desc: 'Chain-of-thought specialist. Shows its work.', size: '4.7 GB', cpu_cores: 4, memory: 12288, disk_size: 35, recommended: true },
    { model: 'llama3.1',      modelName: 'Llama 3.1 8B',       tier: 'balanced', desc: 'Meta. Strong multi-step problem solving.',             size: '4.7 GB', cpu_cores: 4, memory: 12288, disk_size: 35 },
    { model: 'llama3.1:70b',  modelName: 'Llama 3.1 70B',      tier: 'quality',  desc: 'Best reasoning capability. ~48 GB RAM.',               size: '40 GB',  cpu_cores: 8, memory: 49152, disk_size: 80 },
  ],
}

// Simple mode recommendation table (used for memes + fallback)
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
  'memes-light':        { engine: 'stable-diffusion', model: 'sd-v1.5',       modelName: 'SD v1.5',        cpu_cores: 4,  memory: 8192,  disk_size: 30 },
  'memes-balanced':     { engine: 'stable-diffusion', model: 'dreamshaper-8', modelName: 'DreamShaper 8',  cpu_cores: 4,  memory: 12288, disk_size: 40 },
  'memes-quality':      { engine: 'stable-diffusion', model: 'sdxl',          modelName: 'SDXL 1.0',       cpu_cores: 8,  memory: 24576, disk_size: 60 },
}

// Quick-pull model list shown as chips in the instance panel
const QUICK_PULL_MODELS = [
  { id: 'llama3.2:1b',     label: 'Llama 3.2 1B  (0.8 GB, CPU)' },
  { id: 'llama3.2:3b',     label: 'Llama 3.2 3B  (2.0 GB, CPU)' },
  { id: 'qwen2.5:3b',      label: 'Qwen 2.5 3B  (1.9 GB, CPU)' },
  { id: 'phi3:mini',       label: 'Phi-3 Mini  (2.3 GB, CPU)' },
  { id: 'gemma2:2b',       label: 'Gemma 2 2B  (1.6 GB, CPU)' },
  { id: 'mistral:7b',      label: 'Mistral 7B  (4.1 GB, 8+ GB RAM)' },
  { id: 'qwen2.5:7b',      label: 'Qwen 2.5 7B  (4.7 GB, 8+ GB RAM)' },
  { id: 'deepseek-r1:7b',  label: 'DeepSeek R1 7B  (4.7 GB, reasoning)' },
  { id: 'nomic-embed-text', label: 'Nomic Embed  (0.3 GB, embeddings)' },
]

export default {
  name: 'DeployLLM',

  setup() {
    const toast = useToast()

    // ── mode: null | 'simple' | 'advanced' ────────────────────────
    // ── top-level tab ──────────────────────────────────────────
    const topTab = ref('catalog')

    // ── catalog tab state ──────────────────────────────────────
    const catalogCatFilter = ref('all')
    const catalogSizeFilter = ref('all')
    const selectedCatalogModels = ref([])
    const catalogRamLimit = ref(8)  // GB — user-set VM RAM threshold for warnings

    const catalogCategories = computed(() => [
      { id: 'all', label: 'All' },
      ...CATALOG_CATEGORIES.map(c => ({ id: c.id, label: c.label })),
    ])

    const visibleCatalogCategories = computed(() => {
      return CATALOG_CATEGORIES
        .filter(cat => catalogCatFilter.value === 'all' || cat.id === catalogCatFilter.value)
        .map(cat => ({
          ...cat,
          models: cat.models.filter(m => {
            if (catalogSizeFilter.value === 'small') return m.size_gb < 2
            if (catalogSizeFilter.value === 'medium') return m.size_gb >= 2 && m.size_gb <= 8
            if (catalogSizeFilter.value === 'large') return m.size_gb > 8
            return true
          }),
        }))
        .filter(cat => cat.models.length > 0)
    })

    // Catalog RAM warning computed properties
    const catalogSelectedTotalGb = computed(() => {
      const allModels = CATALOG_CATEGORIES.flatMap(c => c.models)
      return selectedCatalogModels.value.reduce((sum, id) => {
        const m = allModels.find(x => x.id === id)
        return sum + (m ? m.size_gb : 0)
      }, 0)
    })

    const catalogRamWarning = computed(() => {
      if (selectedCatalogModels.value.length === 0) return false
      // Warn if largest single model >= 4GB or total > catalogRamLimit
      const allModels = CATALOG_CATEGORIES.flatMap(c => c.models)
      const hasLargeModel = selectedCatalogModels.value.some(id => {
        const m = allModels.find(x => x.id === id)
        return m && m.size_gb >= 4
      })
      return hasLargeModel || catalogSelectedTotalGb.value > catalogRamLimit.value
    })

    function addCatalogModel(m) { if (!selectedCatalogModels.value.includes(m.id)) selectedCatalogModels.value.push(m.id) }
    function removeCatalogModel(id) { selectedCatalogModels.value = selectedCatalogModels.value.filter(x => x !== id) }
    function goDeployWithCatalogModels() { topTab.value = 'deploy' }

    // ── deployed instances tab state ───────────────────────────
    const instances = ref([])
    const instancesLoading = ref(false)
    const expandedInstances = ref([])
    const instStatus = ref({})
    const instVersions = ref({})   // vmid → ollama version string
    const pullModelInputs = ref({})
    const pullProgress = ref({})
    const pullingModel = ref({})

    const instancesCount = computed(() => instances.value.length)

    async function loadInstances() {
      instancesLoading.value = true
      try {
        const res = await api.llm.listInstances()
        instances.value = res.data
      } catch (e) {
        toast.error('Failed to load LLM instances')
      } finally {
        instancesLoading.value = false
      }
    }

    async function switchToInstances() {
      topTab.value = 'instances'
      if (instances.value.length === 0) await loadInstances()
    }

    async function toggleInstance(inst) {
      const id = inst.vmid
      if (expandedInstances.value.includes(id)) {
        expandedInstances.value = expandedInstances.value.filter(x => x !== id)
      } else {
        expandedInstances.value.push(id)
        await refreshInstStatus(inst)
      }
    }

    async function refreshInstStatus(inst) {
      try {
        const [statusRes, versionRes] = await Promise.allSettled([
          api.llm.getInstanceStatus(inst.host_id, inst.node, inst.vmid),
          inst.node ? api.llm.getInstanceVersion(inst.host_id, inst.node, inst.vmid) : Promise.reject('no node'),
        ])
        if (statusRes.status === 'fulfilled') {
          instStatus.value = { ...instStatus.value, [inst.vmid]: statusRes.value.data }
        } else {
          instStatus.value = { ...instStatus.value, [inst.vmid]: { reachable: false, error: 'Request failed' } }
        }
        if (versionRes.status === 'fulfilled' && versionRes.value.data?.version) {
          instVersions.value = { ...instVersions.value, [inst.vmid]: 'v' + versionRes.value.data.version }
        } else {
          instVersions.value = { ...instVersions.value, [inst.vmid]: 'unknown' }
        }
      } catch (e) {
        instStatus.value = { ...instStatus.value, [inst.vmid]: { reachable: false, error: 'Request failed' } }
        instVersions.value = { ...instVersions.value, [inst.vmid]: 'unknown' }
      }
    }

    async function pullModel(inst) {
      const model = (pullModelInputs.value[inst.vmid] || '').trim()
      if (!model) { toast.warning('Enter a model name'); return }
      pullingModel.value = { ...pullingModel.value, [inst.vmid]: true }
      pullProgress.value = { ...pullProgress.value, [inst.vmid]: { status: 'Starting pull...', completed: 0, total: 0 } }

      try {
        const token = localStorage.getItem('access_token')
        const response = await fetch(
          `/api/v1/llm/instances/${inst.host_id}/${inst.node}/${inst.vmid}/pull`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ model }),
          }
        )
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const lines = decoder.decode(value).split('\n').filter(l => l.trim())
          for (const line of lines) {
            try {
              const obj = JSON.parse(line)
              if (obj.error) {
                pullProgress.value = { ...pullProgress.value, [inst.vmid]: { ...pullProgress.value[inst.vmid], error: obj.error, status: 'Error' } }
              } else {
                pullProgress.value = { ...pullProgress.value, [inst.vmid]: {
                  status: obj.status || 'Pulling...',
                  completed: obj.completed || 0,
                  total: obj.total || 0,
                }}
              }
            } catch (_) {}
          }
        }
        toast.success(`Model ${model} pulled successfully`)
        pullModelInputs.value = { ...pullModelInputs.value, [inst.vmid]: '' }
        await refreshInstStatus(inst)
      } catch (e) {
        toast.error(`Pull failed: ${e.message}`)
        pullProgress.value = { ...pullProgress.value, [inst.vmid]: { status: 'Failed', error: e.message } }
      } finally {
        pullingModel.value = { ...pullingModel.value, [inst.vmid]: false }
      }
    }

    async function deleteModel(inst, modelName) {
      if (!confirm(`Delete model "${modelName}" from VM? This cannot be undone.`)) return
      try {
        await api.llm.deleteInstanceModel(inst.host_id, inst.node, inst.vmid, modelName)
        toast.success(`Deleted ${modelName}`)
        await refreshInstStatus(inst)
      } catch (e) {
        toast.error(e.response?.data?.detail || `Failed to delete ${modelName}`)
      }
    }

    async function unloadModel(inst, modelName) {
      try {
        await api.llm.unloadInstanceModel(inst.host_id, inst.node, inst.vmid, modelName)
        toast.success(`Unloaded ${modelName} from VRAM`)
        await refreshInstStatus(inst)
      } catch (e) {
        toast.error(e.response?.data?.detail || `Failed to unload ${modelName}`)
      }
    }

    function formatModelSize(bytes) {
      if (!bytes) return '?'
      const gb = bytes / 1073741824
      return gb >= 1 ? gb.toFixed(1) + ' GB' : Math.round(bytes / 1048576) + ' MB'
    }

    function formatDate(dt) {
      if (!dt) return ''
      try { return new Date(dt).toLocaleDateString() } catch { return dt }
    }

    const mode = ref(null)

    // Advanced wizard steps
    const steps = [
      'Engine', 'Model', 'Hardware', 'OS',
      'Interface', 'Infrastructure', 'Resources', 'Network', 'Review'
    ]
    const currentStep = ref(0)

    // Simple wizard
    const simpleSteps = ['Use Case', 'Model', 'GPU', 'Interface', 'Summary', 'Infrastructure', 'Credentials', 'Review']
    const simpleStep = ref(0)
    const simpleAnswers = ref({ useCase: null, quality: null, gpu: null, webui: null, model: null, modelName: null, modelResources: null })

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
      cpu_sockets: 1,
      cpu_cores: 4,
      cpu_type: 'host',
      memory: 8192,
      disk_size: 40,
      ip_address: '',
      gateway: '',
      netmask: '',
      dns_servers: '',
      username: 'ubuntu',
      password: '',
      ssh_public_key: '',
      cloud_image_id: null,
    })

    // ── simple mode computed ───────────────────────────────────────
    const simpleRec = computed(() => {
      // LLM use cases: user picked a specific model card
      if (simpleAnswers.value.useCase !== 'memes' && simpleAnswers.value.model) {
        return {
          model: simpleAnswers.value.model,
          modelName: simpleAnswers.value.modelName || simpleAnswers.value.model,
          ...(simpleAnswers.value.modelResources || { cpu_cores: 4, memory: 12288, disk_size: 35 }),
        }
      }
      const key = `${simpleAnswers.value.useCase}-${simpleAnswers.value.quality}`
      return SIMPLE_RECS[key] || SIMPLE_RECS['chat-balanced']
    })

    function selectSimpleModel(m) {
      simpleAnswers.value.quality = m.tier
      simpleAnswers.value.model = m.model
      simpleAnswers.value.modelName = m.modelName
      simpleAnswers.value.modelResources = { cpu_cores: m.cpu_cores, memory: m.memory, disk_size: m.disk_size }
      simpleNext()
    }

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
      simpleAnswers.value = { useCase: null, quality: null, gpu: null, webui: null, model: null, modelName: null, modelResources: null }
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
      form.value.os_variant = 'ubuntu2404'

      if (simpleAnswers.value.useCase === 'memes' && simpleAnswers.value.webui === 'meme-maker') {
        // Meme Maker AI stack: ComfyUI + Ollama + Flask UI on :8189
        const memeRec = SIMPLE_RECS[`memes-${simpleAnswers.value.quality}`] || SIMPLE_RECS['memes-balanced']
        form.value.engine = 'meme-maker'
        form.value.model = 'meme-maker-v1'
        form.value.ui_type = 'api-only'
        form.value.cpu_cores = memeRec.cpu_cores
        form.value.memory = memeRec.memory
        form.value.disk_size = Math.max(memeRec.disk_size, 40)
      } else {
        form.value.engine = rec.engine || 'ollama'
        form.value.model = rec.model
        form.value.cpu_cores = rec.cpu_cores
        form.value.memory = rec.memory
        form.value.disk_size = rec.disk_size
        // UI type
        if (simpleAnswers.value.useCase === 'memes') {
          form.value.ui_type = 'comfyui'
        } else {
          form.value.ui_type = simpleAnswers.value.webui === 'yes' ? 'open-webui' : 'api-only'
        }
      }

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
          cpu_sockets: form.value.cpu_sockets,
          cpu_cores: form.value.cpu_cores,
          cpu_type: form.value.cpu_type || 'host',
          memory: form.value.memory,
          disk_size: form.value.disk_size,
          ip_address: useDhcp.value ? null : form.value.ip_address,
          gateway: useDhcp.value ? null : form.value.gateway,
          netmask: useDhcp.value ? null : form.value.netmask,
          dns_servers: form.value.dns_servers || null,
          username: form.value.username,
          password: form.value.password,
          ssh_public_key: form.value.ssh_public_key || null,
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
      simpleAnswers.value = { useCase: null, quality: null, gpu: null, webui: null, model: null, modelName: null, modelResources: null }
      form.value = {
        engine: 'ollama', model: '', ui_type: 'open-webui',
        gpu_enabled: false, gpu_type: null, gpu_device_id: null,
        os_variant: 'ubuntu2404', proxmox_host_id: null, node_id: null,
        storage: '', network_bridge: '', vm_name: '', hostname: '',
        cpu_cores: 4, memory: 8192, disk_size: 40,
        ip_address: '', gateway: '', netmask: '', dns_servers: '',
        username: 'ubuntu', password: '', ssh_public_key: '', cloud_image_id: null,
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
      // top-level tabs
      topTab, switchToInstances,
      // catalog tab
      catalogCatFilter, catalogSizeFilter, catalogCategories, visibleCatalogCategories,
      selectedCatalogModels, addCatalogModel, removeCatalogModel, goDeployWithCatalogModels,
      catalogRamLimit, catalogSelectedTotalGb, catalogRamWarning,
      // instances tab
      instances, instancesLoading, instancesCount, loadInstances,
      expandedInstances, toggleInstance, instStatus, instVersions, refreshInstStatus,
      pullModelInputs, pullProgress, pullingModel, pullModel,
      deleteModel, unloadModel, formatModelSize, formatDate,
      QUICK_PULL_MODELS,
      // deploy wizard
      mode, steps, currentStep, simpleSteps, simpleStep, simpleAnswers, simpleRec, selectSimpleModel, USE_CASE_MODELS,
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

/* Model picker grid in simple mode */
.model-tier-group { margin-bottom: 1.5rem; }
.model-tier-label {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
  padding-left: 2px;
}
.model-pick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.6rem;
}
.model-pick-card {
  border: 2px solid #e5e7eb;
  border-radius: 0.75rem;
  padding: 0.75rem 1rem;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  background: var(--card-bg, #fff);
}
.model-pick-card:hover { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,.08); }
.model-pick-card.selected { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,.15); background: #f5f3ff; }
.model-pick-header { display: flex; align-items: baseline; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.25rem; }
.model-pick-name { font-weight: 600; font-size: 0.9rem; }
.model-pick-size { margin-left: auto; font-size: 0.75rem; color: var(--text-secondary); font-family: monospace; }
.model-pick-desc { font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.3rem; line-height: 1.35; }
.model-pick-meta { font-size: 0.72rem; color: #6b7280; }

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
.stage-pending .stage-label { color: #6b7280; }
.stage-hint { display: block; font-size: 0.78rem; color: #6b7280; margin-top: 0.1rem; }

@media (max-width: 640px) {
  .mode-grid { grid-template-columns: 1fr; }
  .simple-grid { grid-template-columns: 1fr 1fr; }
  .summary-grid { grid-template-columns: 1fr 1fr; }
  .option-grid, .model-grid { grid-template-columns: 1fr; }
  .review-grid { grid-template-columns: 1fr; }
  .grid-cols-2, .grid-cols-3 { grid-template-columns: 1fr; }
  .catalog-grid { grid-template-columns: 1fr; }
}

/* ── top-level tab bar ──────────────────────────────────── */
.top-tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 2px solid #e5e7eb;
  margin-bottom: 1.5rem;
}
.top-tab {
  padding: 0.65rem 1.4rem;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 0.92rem;
  font-weight: 600;
  color: #6b7280;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.top-tab:hover { color: #374151; }
.top-tab.active { color: #3b82f6; border-bottom-color: #3b82f6; }
.tab-badge {
  background: #3b82f6;
  color: white;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 10px;
  min-width: 1.2rem;
  text-align: center;
}
.tab-panel { }

/* ── catalog tab ────────────────────────────────────────── */
.catalog-filters {
  display: flex;
  gap: 2rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}
.filter-group { display: flex; flex-direction: column; gap: 0.4rem; }
.filter-label { font-size: 0.75rem; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.filter-pills { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.pill {
  padding: 0.3rem 0.85rem;
  border: 1px solid #d1d5db;
  border-radius: 20px;
  background: white;
  cursor: pointer;
  font-size: 0.8rem;
  color: #374151;
  transition: all 0.15s;
}
.pill:hover { border-color: #3b82f6; color: #3b82f6; }
.pill.active { background: #3b82f6; color: white; border-color: #3b82f6; }

.catalog-section { margin-bottom: 2rem; }
.catalog-section-title { font-size: 1rem; font-weight: 700; color: #374151; margin: 0 0 0.75rem; }

.catalog-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.9rem;
}
.catalog-card {
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  padding: 1rem;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.catalog-card:hover { border-color: #93c5fd; box-shadow: 0 2px 8px rgba(59,130,246,0.1); }
.catalog-card.selected { border-color: #3b82f6; background: #eff6ff; box-shadow: 0 0 0 3px rgba(59,130,246,0.12); }
.catalog-card-header { display: flex; justify-content: space-between; align-items: baseline; }
.catalog-model-name { font-weight: 700; font-size: 0.92rem; color: #111; }
.catalog-model-size { font-size: 0.78rem; color: #6b7280; font-family: monospace; }
.catalog-model-desc { font-size: 0.8rem; color: #555; line-height: 1.4; margin: 0; flex-grow: 1; }
.catalog-model-meta { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.meta-chip {
  font-size: 0.7rem;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  color: #374151;
}
.meta-chip.vram { background: #fef3c7; border-color: #fde68a; color: #92400e; }
.catalog-card-footer { margin-top: 0.3rem; }

.btn-sm { padding: 0.35rem 0.8rem; font-size: 0.8rem; border-radius: 6px; border: none; cursor: pointer; font-weight: 600; transition: all 0.15s; }
.btn-xs { padding: 0.2rem 0.55rem; font-size: 0.75rem; border-radius: 5px; border: none; cursor: pointer; font-weight: 600; transition: all 0.15s; }
.btn-outline { background: white; border: 1px solid #d1d5db; color: #374151; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn-selected { background: #eff6ff; border: 1px solid #3b82f6; color: #1d4ed8; }
.btn-danger { background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; }
.btn-danger:hover { background: #fecaca; }

.catalog-selection-bar {
  position: sticky;
  bottom: 1rem;
  background: #1e293b;
  color: white;
  border-radius: 12px;
  padding: 0.85rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 8px 24px rgba(0,0,0,0.25);
  margin-top: 1rem;
  font-size: 0.9rem;
  font-weight: 600;
}

/* ── instances tab ──────────────────────────────────────── */
.instances-toolbar { display: flex; gap: 0.75rem; margin-bottom: 1rem; align-items: center; }
.empty-state { text-align: center; padding: 3rem 2rem; }
.empty-icon { font-size: 3rem; margin-bottom: 0.75rem; }
.empty-state h3 { margin: 0 0 0.5rem; }
.empty-state p { color: #6b7280; margin: 0 0 1.5rem; }

.instance-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  margin-bottom: 0.75rem;
  overflow: hidden;
  background: white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.instance-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  cursor: pointer;
  transition: background 0.15s;
}
.instance-header:hover { background: #f8fafc; }
.instance-status-dot {
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}
.dot-green { background: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,0.2); }
.dot-gray { background: #9ca3af; }
.instance-info { flex: 1; min-width: 0; }
.instance-name { display: block; font-weight: 700; font-size: 0.95rem; color: #111; }
.instance-meta { font-size: 0.78rem; color: #6b7280; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.instance-actions-quick { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }
.expand-arrow { color: #9ca3af; font-size: 0.75rem; flex-shrink: 0; }

.status-badge {
  font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.5rem;
  border-radius: 10px; text-transform: uppercase; letter-spacing: 0.04em;
}
.status-running { background: #d1fae5; color: #065f46; }
.status-stopped { background: #f3f4f6; color: #6b7280; }
.status-creating { background: #dbeafe; color: #1d4ed8; }
.status-error { background: #fee2e2; color: #dc2626; }
.status-unknown { background: #f3f4f6; color: #6b7280; }

.instance-detail {
  border-top: 1px solid #f3f4f6;
  padding: 1rem 1.25rem;
  background: #fafafa;
}
.inst-loading { display: flex; align-items: center; gap: 0.6rem; color: #6b7280; font-size: 0.85rem; }
.inst-section { margin-bottom: 1.25rem; }
.inst-section:last-child { margin-bottom: 0; }
.inst-section-title { font-size: 0.82rem; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.6rem; }
.muted-text { font-size: 0.85rem; color: #9ca3af; font-style: italic; }

.model-chip-row { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.model-chip {
  display: flex; align-items: center; gap: 0.4rem;
  background: #eff6ff; border: 1px solid #bfdbfe;
  border-radius: 20px; padding: 0.3rem 0.75rem;
  font-size: 0.8rem; color: #1d4ed8;
}
.loaded-chip { background: #d1fae5; border-color: #6ee7b7; color: #065f46; }
.chip-size { font-size: 0.72rem; color: inherit; opacity: 0.7; }
.btn-chip-action {
  background: none; border: none; cursor: pointer; padding: 0 0.1rem;
  color: inherit; font-size: 1rem; line-height: 1; opacity: 0.6;
  transition: opacity 0.15s;
}
.btn-chip-action:hover { opacity: 1; }

.models-table { width: 100%; border-collapse: collapse; font-size: 0.84rem; }
.models-table th { text-align: left; padding: 0.4rem 0.6rem; font-size: 0.72rem; color: #6b7280; font-weight: 600; text-transform: uppercase; border-bottom: 1px solid #e5e7eb; }
.models-table td { padding: 0.45rem 0.6rem; border-bottom: 1px solid #f3f4f6; color: #374151; }
.model-name-cell { font-family: monospace; font-size: 0.82rem; }
.model-size-cell { color: #6b7280; white-space: nowrap; }
.model-date-cell { color: #9ca3af; font-size: 0.78rem; }

.pull-row { display: flex; gap: 0.6rem; align-items: center; }
.pull-input { flex: 1; }
.pull-progress-box {
  margin-top: 0.75rem;
  background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 6px; padding: 0.6rem 0.85rem;
  font-size: 0.82rem;
}
.pull-progress-status { color: #475569; margin-bottom: 0.4rem; }
.pull-progress-bar-wrap { background: #e2e8f0; border-radius: 4px; height: 6px; overflow: hidden; }
.pull-progress-bar { height: 100%; background: #3b82f6; transition: width 0.3s; border-radius: 4px; }

/* ── catalog RAM warning ────────────────────────────────── */
.catalog-ram-warning {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  background: #fffbeb;
  border: 1px solid #fbbf24;
  border-radius: 8px;
  padding: 0.85rem 1rem;
  margin-bottom: 1.25rem;
  font-size: 0.85rem;
  color: #78350f;
}
.ram-warning-icon { font-size: 1.2rem; flex-shrink: 0; }
.catalog-ram-warning > div { flex: 1; }
.ram-threshold-control { margin-top: 0.5rem; font-size: 0.8rem; }
.ram-limit-input {
  width: 56px;
  padding: 0.15rem 0.35rem;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 0.8rem;
  margin-left: 0.3rem;
}

.catalog-selection-info { display: flex; flex-direction: column; gap: 0.15rem; }
.catalog-selection-size { font-size: 0.78rem; opacity: 0.7; }

/* ── size chip for large models ─────────────────────────── */
.catalog-model-size.size-large { color: #dc2626; font-weight: 700; }
.meta-chip.ram-warn { background: #fee2e2; border-color: #fca5a5; color: #991b1b; }

/* ── instance info row ──────────────────────────────────── */
.inst-info-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #f3f4f6;
}
.inst-info-chip {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 0.2rem 0.6rem;
  font-size: 0.78rem;
}
.inst-info-chip-gpu { background: #fef3c7; border-color: #fde68a; }
.inst-info-label { color: #6b7280; font-weight: 600; text-transform: uppercase; font-size: 0.65rem; letter-spacing: 0.04em; }
.inst-info-value { color: #111; font-family: monospace; font-size: 0.8rem; }
.inst-api-btn { margin-left: auto; text-decoration: none; }

/* ── pull quick-select ──────────────────────────────────── */
.pull-quick-select { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; }
.pull-quick-label { font-size: 0.75rem; color: #6b7280; font-weight: 600; flex-shrink: 0; }
.pull-quick-btn { font-family: monospace; font-size: 0.72rem; }
.pull-quick-btn-active {
  background: #eff6ff; border: 1px solid #3b82f6; color: #1d4ed8;
}

/* ── SSH key textarea ───────────────────────────────────── */
.ssh-key-input { font-family: monospace; font-size: 0.78rem; resize: vertical; }
.form-label-optional { font-weight: 400; color: #9ca3af; font-size: 0.78rem; }

/* ── grid-cols-4 ────────────────────────────────────────── */
.grid-cols-4 { grid-template-columns: 1fr 1fr 1fr 1fr; }
@media (max-width: 640px) { .grid-cols-4 { grid-template-columns: 1fr 1fr; } }
</style>
