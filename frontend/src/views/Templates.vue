<template>
  <div class="templates-page">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">VM Templates</h2>
        <p class="page-subtitle">
          Clone and manage templates across all Proxmox hosts
          <span v-if="!loading && activeTab === 'library'" class="count-badge">
            {{ COMMUNITY_TEMPLATES.length }} community templates
          </span>
          <span v-else-if="!loading && filteredTemplates.length > 0" class="count-badge">
            {{ filteredTemplates.length }} template{{ filteredTemplates.length !== 1 ? 's' : '' }}
            across {{ uniqueHostCount }} host{{ uniqueHostCount !== 1 ? 's' : '' }}
          </span>
        </p>
      </div>
      <div class="header-right">
        <template v-if="activeTab === 'local'">
          <input
            v-model="search"
            class="form-control search-input"
            placeholder="Search by name or VMID..."
          />
          <select v-model="selectedHostId" class="form-control host-select">
            <option value="">All Hosts</option>
            <option v-for="host in hosts" :key="host.id" :value="host.id">
              {{ host.name || host.host }}
            </option>
          </select>
          <select v-model="sortBy" class="form-control sort-select">
            <option value="name">Sort: Name</option>
            <option value="vmid">Sort: VMID</option>
            <option value="size">Sort: Size</option>
            <option value="node">Sort: Node</option>
          </select>
          <button @click="loadTemplates" class="btn btn-outline" :disabled="loading">
            {{ loading ? 'Loading...' : 'Refresh' }}
          </button>
        </template>
        <template v-else>
          <input
            v-model="librarySearch"
            class="form-control search-input"
            placeholder="Search library..."
          />
        </template>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tab-bar">
      <button
        :class="['tab-btn', { active: activeTab === 'local' }]"
        @click="activeTab = 'local'"
      >My Templates</button>
      <button
        :class="['tab-btn', { active: activeTab === 'library' }]"
        @click="activeTab = 'library'"
      >Template Library</button>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <!-- ── Local Templates Tab ────────────────────────────────────────────── -->
    <template v-if="activeTab === 'local'">
      <div class="card">
        <div class="card-body p-0">
          <div v-if="loading" class="loading-state">
            <div class="loading-spinner"></div>
            <span>Loading templates...</span>
          </div>
          <div v-else-if="filteredTemplates.length === 0" class="empty-state">
            <span class="empty-icon">&#128203;</span>
            <p>No templates found{{ search ? ' matching your search' : '' }}.</p>
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>VMID</th>
                  <th>Name</th>
                  <th>OS</th>
                  <th>Node</th>
                  <th>Host</th>
                  <th>Memory</th>
                  <th>CPUs</th>
                  <th>Disk</th>
                  <th>Notes</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tpl in filteredTemplates" :key="`${tpl.hostId}-${tpl.vmid}`">
                  <td class="vmid-cell">{{ tpl.vmid }}</td>
                  <td class="name-cell">
                    <span class="name-text">{{ tpl.name || `VM ${tpl.vmid}` }}</span>
                  </td>
                  <td>
                    <span class="os-badge" :class="`os-${detectOS(tpl.name)}`">
                      {{ detectOSLabel(tpl.name) }}
                    </span>
                  </td>
                  <td class="mono">{{ tpl.node }}</td>
                  <td class="mono">{{ tpl.hostName }}</td>
                  <td>
                    <span v-if="tpl.maxmem" class="meta-val">{{ formatMB(tpl.maxmem) }} MB</span>
                    <span v-else class="dim">—</span>
                  </td>
                  <td>
                    <span v-if="tpl.maxcpu" class="meta-val">{{ tpl.maxcpu }} vCPU</span>
                    <span v-else class="dim">—</span>
                  </td>
                  <td>
                    <span v-if="tpl.maxdisk" class="meta-val">{{ formatGB(tpl.maxdisk) }}</span>
                    <span v-else class="dim">—</span>
                  </td>
                  <td class="notes-cell">
                    <span v-if="tpl.description" class="notes-text" :title="tpl.description">
                      {{ truncate(tpl.description, 40) }}
                    </span>
                    <span v-else class="dim">—</span>
                  </td>
                  <td class="actions-cell">
                    <button class="btn btn-primary btn-sm" @click="openCloneModal(tpl)">Clone</button>
                    <button class="btn btn-outline btn-sm" @click="openMetaModal(tpl)">Edit Info</button>
                    <router-link
                      :to="`/proxmox/${tpl.hostId}/nodes/${tpl.node}/vms/${tpl.vmid}`"
                      class="btn btn-outline btn-sm"
                    >Details</router-link>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- ── Template Library Tab ───────────────────────────────────────────── -->
    <template v-else>
      <div class="library-grid">
        <div
          v-for="tpl in filteredLibrary"
          :key="tpl.id"
          class="library-card"
        >
          <div class="library-card-header">
            <span class="os-badge" :class="`os-${tpl.osKey}`">{{ tpl.osLabel }}</span>
            <div class="library-badges">
              <span v-if="tpl.cloudinit" class="badge-ci">cloud-init</span>
              <span v-if="tpl.lts" class="badge-lts">LTS</span>
            </div>
          </div>
          <h3 class="library-card-title">{{ tpl.name }}</h3>
          <p class="library-card-desc">{{ tpl.description }}</p>
          <div class="library-card-meta">
            <span>Min disk: {{ tpl.minDisk }} GB</span>
            <span>Min RAM: {{ tpl.minRam }} MB</span>
          </div>
          <div class="library-card-url">
            <span class="url-label">Image URL</span>
            <span class="url-text" :title="tpl.downloadUrl">{{ truncate(tpl.downloadUrl, 60) }}</span>
          </div>
          <div class="library-card-actions">
            <button
              class="btn btn-primary btn-sm"
              @click="openLibraryDownloadModal(tpl)"
            >Download &amp; Create Template</button>
            <a :href="tpl.downloadUrl" target="_blank" class="btn btn-outline btn-sm">
              Direct Link
            </a>
          </div>
        </div>
      </div>
      <div v-if="filteredLibrary.length === 0" class="empty-state">
        <span class="empty-icon">&#128214;</span>
        <p>No templates match your search.</p>
      </div>
    </template>

    <!-- ── Clone Modal ────────────────────────────────────────────────────── -->
    <div v-if="showCloneModal" class="modal" @click.self="closeCloneModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Clone Template</h3>
          <button @click="closeCloneModal" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <p class="text-sm text-muted mb-3">
            Cloning <strong>{{ cloneTarget?.name || `VM ${cloneTarget?.vmid}` }}</strong>
            (VMID {{ cloneTarget?.vmid }}) from node <strong>{{ cloneTarget?.node }}</strong>
          </p>

          <!-- Disk usage estimate -->
          <div v-if="cloneTarget?.maxdisk" class="info-note mb-3">
            Estimated disk usage: <strong>{{ formatGB(cloneTarget.maxdisk) }}</strong>
            {{ cloneForm.full ? '(full clone — independent copy)' : '(linked clone — minimal extra space)' }}
          </div>

          <div class="form-group">
            <label class="form-label">New VM ID <span class="text-danger">*</span></label>
            <input v-model.number="cloneForm.newid" type="number" class="form-control" placeholder="e.g. 200" />
          </div>

          <div class="form-group">
            <label class="form-label">New Name <span class="text-danger">*</span></label>
            <input v-model="cloneForm.name" class="form-control" placeholder="new-vm-name" />
          </div>

          <div class="form-group">
            <label class="form-label">Clone Mode</label>
            <div class="radio-group">
              <label class="radio-label">
                <input v-model="cloneForm.full" type="radio" :value="true" />
                <span>
                  <strong>Full Clone</strong>
                  <span class="radio-hint">Independent copy — can be moved to any storage</span>
                </span>
              </label>
              <label class="radio-label">
                <input v-model="cloneForm.full" type="radio" :value="false" />
                <span>
                  <strong>Linked Clone</strong>
                  <span class="radio-hint">Shares base disk with template — faster, less space</span>
                </span>
              </label>
            </div>
            <div v-if="!cloneForm.full" class="info-note mt-2">
              Linked clones cannot be moved to different storage pools.
            </div>
          </div>

          <!-- Target host (cross-host) -->
          <div class="form-group">
            <label class="form-label">Target Host</label>
            <select v-model="cloneForm.targetHostId" class="form-control" @change="onTargetHostChange">
              <option :value="cloneTarget?.hostId">Same host ({{ cloneTarget?.hostName }})</option>
              <option v-for="h in otherHosts" :key="h.id" :value="h.id">
                {{ h.name || h.host }} (cross-host via migration)
              </option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Target Node</label>
            <select v-model="cloneForm.target" class="form-control" @change="onTargetNodeChange">
              <option value="">Same as template ({{ cloneTarget?.node }})</option>
              <option v-for="n in cloneNodes" :key="n.node" :value="n.node">
                {{ n.node }}
              </option>
            </select>
          </div>

          <div v-if="cloneForm.full" class="form-group">
            <label class="form-label">Target Storage</label>
            <select v-model="cloneForm.storage" class="form-control" :disabled="loadingStorages">
              <option value="">Default storage</option>
              <option v-for="s in cloneStorages" :key="s.storage" :value="s.storage">
                {{ s.storage }}
                <template v-if="s.avail"> ({{ formatGB(s.avail) }} free)</template>
              </option>
            </select>
            <div v-if="loadingStorages" class="hint-text mt-1">Loading storages...</div>
          </div>

          <!-- MAC address -->
          <div class="form-group">
            <label class="form-label">
              <input v-model="cloneForm.generateMac" type="checkbox" />
              Generate new MAC address for network interfaces
            </label>
            <p class="hint-text">Proxmox generates a new MAC when cloning by default.</p>
          </div>

          <!-- Cloud-init seed -->
          <div v-if="cloneTarget && templateHasCloudInit(cloneTarget)" class="form-group">
            <label class="form-label">
              <input v-model="cloneForm.cloudInitSeed" type="checkbox" />
              Configure Cloud-Init after clone
            </label>
            <p class="hint-text">Opens the Cloud-Init Configurator once cloning completes.</p>
          </div>

          <div class="form-group checkbox-group">
            <label class="checkbox-label">
              <input v-model="cloneForm.startAfterClone" type="checkbox" />
              Start VM after clone
            </label>
          </div>

          <div v-if="cloneError" class="alert alert-danger mt-2">{{ cloneError }}</div>

          <div class="flex gap-1 mt-3">
            <button
              @click="submitClone"
              class="btn btn-primary"
              :disabled="cloning || !cloneForm.newid || !cloneForm.name"
            >
              {{ cloning ? 'Cloning...' : 'Clone VM' }}
            </button>
            <button @click="closeCloneModal" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Metadata Edit Modal ────────────────────────────────────────────── -->
    <div v-if="showMetaModal" class="modal" @click.self="closeMetaModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Edit Template Info</h3>
          <button @click="closeMetaModal" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <p class="text-sm text-muted mb-3">
            Editing metadata for <strong>{{ metaTarget?.name || `VM ${metaTarget?.vmid}` }}</strong>
          </p>

          <div class="form-group">
            <label class="form-label">Name</label>
            <input v-model="metaForm.name" class="form-control" />
          </div>

          <div class="form-group">
            <label class="form-label">Description / Notes</label>
            <textarea v-model="metaForm.description" class="form-control" rows="4" placeholder="Template notes..."></textarea>
          </div>

          <div class="form-group">
            <label class="form-label">Tags</label>
            <input v-model="metaForm.tags" class="form-control" placeholder="production;ubuntu;lts" />
            <p class="hint-text">Semicolon-separated tags.</p>
          </div>

          <div v-if="metaError" class="alert alert-danger mt-2">{{ metaError }}</div>
          <div v-if="metaSuccess" class="alert alert-success mt-2">{{ metaSuccess }}</div>

          <div class="flex gap-1 mt-3">
            <button @click="saveMeta" class="btn btn-primary" :disabled="savingMeta">
              {{ savingMeta ? 'Saving...' : 'Save' }}
            </button>
            <button @click="closeMetaModal" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Library Download Modal ─────────────────────────────────────────── -->
    <div v-if="showLibraryModal" class="modal" @click.self="showLibraryModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Download &amp; Create Template</h3>
          <button @click="showLibraryModal = false" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <p class="text-sm text-muted mb-3">
            Downloading <strong>{{ libraryTarget?.name }}</strong> cloud image directly to Proxmox storage.
          </p>

          <div class="form-group">
            <label class="form-label">Proxmox Host <span class="text-danger">*</span></label>
            <select v-model="libForm.hostId" class="form-control" @change="onLibHostChange">
              <option value="">Select host...</option>
              <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name || h.host }}</option>
            </select>
          </div>

          <div class="form-group" v-if="libForm.hostId">
            <label class="form-label">Node <span class="text-danger">*</span></label>
            <select v-model="libForm.node" class="form-control" @change="onLibNodeChange">
              <option value="">Select node...</option>
              <option v-for="n in libNodes" :key="n.node" :value="n.node">{{ n.node }}</option>
            </select>
          </div>

          <div class="form-group" v-if="libForm.node">
            <label class="form-label">Storage <span class="text-danger">*</span></label>
            <select v-model="libForm.storage" class="form-control">
              <option value="">Select storage...</option>
              <option v-for="s in libStorages" :key="s.storage" :value="s.storage">
                {{ s.storage }} ({{ s.type }})
                <template v-if="s.avail"> — {{ formatGB(s.avail) }} free</template>
              </option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Download URL</label>
            <input v-model="libForm.url" class="form-control mono-input" />
          </div>

          <div class="form-group">
            <label class="form-label">Filename</label>
            <input v-model="libForm.filename" class="form-control" />
          </div>

          <div class="info-note mb-2">
            The image will be downloaded by Proxmox directly to the selected storage.
            After download, go to the node storage browser to import it as a VM disk and convert to a template.
          </div>

          <div v-if="libError" class="alert alert-danger mt-2">{{ libError }}</div>
          <div v-if="libSuccess" class="alert alert-success mt-2">{{ libSuccess }}</div>

          <div class="flex gap-1 mt-3">
            <button
              @click="submitLibraryDownload"
              class="btn btn-primary"
              :disabled="libDownloading || !libForm.hostId || !libForm.node || !libForm.storage"
            >
              {{ libDownloading ? 'Downloading...' : 'Start Download' }}
            </button>
            <button @click="showLibraryModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Success Toast -->
    <transition name="toast-fade">
      <div v-if="successToast.show" class="toast-success">
        <span>{{ successToast.message }}</span>
        <router-link
          v-if="successToast.vmLink"
          :to="successToast.vmLink"
          class="toast-link"
          @click="successToast.show = false"
        >Go to VM &rarr;</router-link>
        <button class="toast-close" @click="successToast.show = false">&times;</button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

const router = useRouter()

// ── State ────────────────────────────────────────────────────────────────────
const hosts = ref([])
const templates = ref([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const librarySearch = ref('')
const selectedHostId = ref('')
const sortBy = ref('name')
const activeTab = ref('local')

// Clone modal state
const showCloneModal = ref(false)
const cloneTarget = ref(null)
const cloneNodes = ref([])
const cloneStorages = ref([])
const loadingStorages = ref(false)
const cloneForm = ref({
  newid: null,
  name: '',
  target: '',
  targetHostId: null,
  storage: '',
  full: true,
  startAfterClone: false,
  generateMac: true,
  cloudInitSeed: false,
})
const cloning = ref(false)
const cloneError = ref('')
const otherHosts = computed(() => hosts.value.filter(h => h.id !== cloneTarget.value?.hostId))

// Metadata modal
const showMetaModal = ref(false)
const metaTarget = ref(null)
const metaForm = ref({ name: '', description: '', tags: '' })
const savingMeta = ref(false)
const metaError = ref('')
const metaSuccess = ref('')

// Library download modal
const showLibraryModal = ref(false)
const libraryTarget = ref(null)
const libForm = ref({ hostId: '', node: '', storage: '', url: '', filename: '' })
const libNodes = ref([])
const libStorages = ref([])
const libDownloading = ref(false)
const libError = ref('')
const libSuccess = ref('')

// Success toast
const successToast = ref({ show: false, message: '', vmLink: '' })

// ── Community Template Library ────────────────────────────────────────────────
const COMMUNITY_TEMPLATES = [
  {
    id: 'ubuntu-2204',
    name: 'Ubuntu 22.04 LTS (Jammy)',
    osKey: 'ubuntu',
    osLabel: 'Ubuntu',
    description: 'Ubuntu 22.04 LTS cloud image. Long-term support until April 2027. Ideal for production servers.',
    downloadUrl: 'https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img',
    minDisk: 10,
    minRam: 512,
    cloudinit: true,
    lts: true,
  },
  {
    id: 'ubuntu-2404',
    name: 'Ubuntu 24.04 LTS (Noble)',
    osKey: 'ubuntu',
    osLabel: 'Ubuntu',
    description: 'Ubuntu 24.04 LTS cloud image. Latest LTS release with support until April 2029.',
    downloadUrl: 'https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img',
    minDisk: 10,
    minRam: 512,
    cloudinit: true,
    lts: true,
  },
  {
    id: 'debian-12',
    name: 'Debian 12 (Bookworm)',
    osKey: 'debian',
    osLabel: 'Debian',
    description: 'Debian 12 stable cloud image. Rock-solid, conservative package selections. Excellent for servers.',
    downloadUrl: 'https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2',
    minDisk: 8,
    minRam: 512,
    cloudinit: true,
    lts: false,
  },
  {
    id: 'centos-stream-9',
    name: 'CentOS Stream 9',
    osKey: 'centos',
    osLabel: 'CentOS',
    description: 'CentOS Stream 9 cloud image. Rolling-release midstream between RHEL and Fedora.',
    downloadUrl: 'https://cloud.centos.org/centos/9-stream/x86_64/images/CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2',
    minDisk: 10,
    minRam: 1024,
    cloudinit: true,
    lts: false,
  },
  {
    id: 'rocky-9',
    name: 'Rocky Linux 9',
    osKey: 'rocky',
    osLabel: 'Rocky',
    description: 'Rocky Linux 9 cloud image. Enterprise-grade, RHEL-compatible, community-maintained.',
    downloadUrl: 'https://download.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud.latest.x86_64.qcow2',
    minDisk: 10,
    minRam: 1024,
    cloudinit: true,
    lts: false,
  },
  {
    id: 'alma-9',
    name: 'AlmaLinux 9',
    osKey: 'alma',
    osLabel: 'AlmaLinux',
    description: 'AlmaLinux 9 cloud image. 1:1 binary compatible with RHEL 9. Community-owned forever.',
    downloadUrl: 'https://repo.almalinux.org/almalinux/9/cloud/x86_64/images/AlmaLinux-9-GenericCloud-latest.x86_64.qcow2',
    minDisk: 10,
    minRam: 1024,
    cloudinit: true,
    lts: false,
  },
  {
    id: 'fedora-39',
    name: 'Fedora 39',
    osKey: 'fedora',
    osLabel: 'Fedora',
    description: 'Fedora 39 cloud image. Latest Fedora release with cutting-edge packages and technologies.',
    downloadUrl: 'https://download.fedoraproject.org/pub/fedora/linux/releases/39/Cloud/x86_64/images/Fedora-Cloud-Base-39-1.5.x86_64.qcow2',
    minDisk: 10,
    minRam: 1024,
    cloudinit: true,
    lts: false,
  },
  {
    id: 'opensuse-leap-155',
    name: 'openSUSE Leap 15.5',
    osKey: 'suse',
    osLabel: 'openSUSE',
    description: 'openSUSE Leap 15.5 cloud image. Enterprise-class stability with community-driven development.',
    downloadUrl: 'https://download.opensuse.org/distribution/leap/15.5/appliances/openSUSE-Leap-15.5-Minimal-VM.x86_64-Cloud.qcow2',
    minDisk: 10,
    minRam: 1024,
    cloudinit: true,
    lts: false,
  },
  {
    id: 'alpine-318',
    name: 'Alpine Linux 3.18',
    osKey: 'alpine',
    osLabel: 'Alpine',
    description: 'Alpine Linux 3.18 cloud image. Extremely small (~5 MB), security-oriented, musl libc.',
    downloadUrl: 'https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/cloud/nocloud_alpine-3.18.0-x86_64-bios-cloudinit-r0.qcow2',
    minDisk: 1,
    minRam: 128,
    cloudinit: true,
    lts: false,
  },
  {
    id: 'windows-server-2022',
    name: 'Windows Server 2022',
    osKey: 'windows',
    osLabel: 'Windows',
    description: 'Windows Server 2022 evaluation ISO. Requires manual setup — cloud-init not supported natively.',
    downloadUrl: 'https://go.microsoft.com/fwlink/p/?LinkID=2195280&clcid=0x409&culture=en-us&country=US',
    minDisk: 40,
    minRam: 2048,
    cloudinit: false,
    lts: true,
  },
  {
    id: 'debian-11',
    name: 'Debian 11 (Bullseye)',
    osKey: 'debian',
    osLabel: 'Debian',
    description: 'Debian 11 oldstable cloud image. Still receives security updates. Good for compatibility.',
    downloadUrl: 'https://cloud.debian.org/images/cloud/bullseye/latest/debian-11-generic-amd64.qcow2',
    minDisk: 8,
    minRam: 512,
    cloudinit: true,
    lts: false,
  },
]

// ── Computed ─────────────────────────────────────────────────────────────────
const filteredTemplates = computed(() => {
  let list = templates.value
  if (selectedHostId.value) {
    list = list.filter(t => String(t.hostId) === String(selectedHostId.value))
  }
  if (search.value.trim()) {
    const q = search.value.trim().toLowerCase()
    list = list.filter(t =>
      (t.name || '').toLowerCase().includes(q) ||
      String(t.vmid).includes(q)
    )
  }
  list = [...list].sort((a, b) => {
    if (sortBy.value === 'vmid') return a.vmid - b.vmid
    if (sortBy.value === 'size') return (b.maxdisk || 0) - (a.maxdisk || 0)
    if (sortBy.value === 'node') return a.node.localeCompare(b.node)
    const an = (a.name || `vm${a.vmid}`).toLowerCase()
    const bn = (b.name || `vm${b.vmid}`).toLowerCase()
    return an.localeCompare(bn)
  })
  return list
})

const uniqueHostCount = computed(() => {
  const ids = new Set(filteredTemplates.value.map(t => t.hostId))
  return ids.size
})

const filteredLibrary = computed(() => {
  const q = librarySearch.value.trim().toLowerCase()
  if (!q) return COMMUNITY_TEMPLATES
  return COMMUNITY_TEMPLATES.filter(t =>
    t.name.toLowerCase().includes(q) ||
    t.description.toLowerCase().includes(q) ||
    t.osLabel.toLowerCase().includes(q)
  )
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatMB(bytes) {
  return Math.round(bytes / 1024 / 1024)
}

function formatGB(bytes) {
  if (!bytes) return '0 GB'
  const gb = bytes / 1024 / 1024 / 1024
  return gb >= 1 ? `${gb.toFixed(0)} GB` : `${(bytes / 1024 / 1024).toFixed(0)} MB`
}

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '…' : str
}

const OS_PATTERNS = [
  { key: 'ubuntu',  label: 'Ubuntu',  patterns: ['ubuntu'] },
  { key: 'debian',  label: 'Debian',  patterns: ['debian'] },
  { key: 'centos',  label: 'CentOS',  patterns: ['centos'] },
  { key: 'rhel',    label: 'RHEL',    patterns: ['rhel', 'redhat', 'red-hat'] },
  { key: 'rocky',   label: 'Rocky',   patterns: ['rocky'] },
  { key: 'alma',    label: 'AlmaLinux', patterns: ['alma'] },
  { key: 'fedora',  label: 'Fedora',  patterns: ['fedora'] },
  { key: 'suse',    label: 'SUSE',    patterns: ['suse', 'opensuse'] },
  { key: 'alpine',  label: 'Alpine',  patterns: ['alpine'] },
  { key: 'arch',    label: 'Arch',    patterns: ['arch'] },
  { key: 'windows', label: 'Windows', patterns: ['win', 'windows', 'server-20', 'w2k'] },
  { key: 'freebsd', label: 'FreeBSD', patterns: ['freebsd', 'bsd'] },
]

function detectOS(name) {
  if (!name) return 'unknown'
  const lower = (name || '').toLowerCase()
  for (const os of OS_PATTERNS) {
    if (os.patterns.some(p => lower.includes(p))) return os.key
  }
  return 'unknown'
}

function detectOSLabel(name) {
  if (!name) return 'Unknown'
  const lower = (name || '').toLowerCase()
  for (const os of OS_PATTERNS) {
    if (os.patterns.some(p => lower.includes(p))) return os.label
  }
  return 'Linux'
}

function templateHasCloudInit(tpl) {
  // Heuristic: check OS name for known cloud-init distros
  const ci = ['ubuntu', 'debian', 'centos', 'rocky', 'alma', 'fedora', 'suse', 'alpine']
  const key = detectOS(tpl.name)
  return ci.includes(key)
}

// ── Data Loading ──────────────────────────────────────────────────────────────
async function loadHosts() {
  try {
    const res = await api.proxmox.listHosts()
    hosts.value = res.data || []
  } catch (err) {
    error.value = 'Failed to load Proxmox hosts.'
    console.error(err)
  }
}

async function loadTemplates() {
  if (hosts.value.length === 0) return
  loading.value = true
  error.value = ''
  templates.value = []

  const results = []
  await Promise.allSettled(
    hosts.value.map(async (host) => {
      try {
        const res = await api.pveNode.clusterResources(host.id, 'vm')
        const items = (res.data || [])
          .filter(vm => vm.template === 1)
          .map(vm => ({
            ...vm,
            hostId: host.id,
            hostName: host.name || host.host
          }))
        results.push(...items)
      } catch (err) {
        console.warn(`Failed to load resources for host ${host.id}:`, err)
      }
    })
  )

  templates.value = results
  loading.value = false
}

// ── Clone Modal ───────────────────────────────────────────────────────────────
async function openCloneModal(tpl) {
  cloneTarget.value = tpl
  cloneError.value = ''
  cloneNodes.value = []
  cloneStorages.value = []
  cloneForm.value = {
    newid: null,
    name: `${tpl.name || `vm${tpl.vmid}`}-clone`,
    target: '',
    targetHostId: tpl.hostId,
    storage: '',
    full: true,
    startAfterClone: false,
    generateMac: true,
    cloudInitSeed: false,
  }
  showCloneModal.value = true

  try {
    const res = await api.pveNode.nextId(tpl.hostId)
    const next = res.data?.nextid ?? res.data
    if (next) cloneForm.value.newid = Number(next)
  } catch (err) {
    console.warn('Could not fetch next VM ID:', err)
  }

  try {
    const res = await api.proxmox.listNodes(tpl.hostId)
    cloneNodes.value = (res.data || []).filter(n => n.node !== tpl.node)
  } catch (err) {
    console.warn('Could not fetch nodes:', err)
  }

  await loadStoragesForNode(tpl.hostId, tpl.node)
}

async function loadStoragesForNode(hostId, node) {
  loadingStorages.value = true
  cloneStorages.value = []
  try {
    const res = await api.pveNode.listStorage(hostId, node)
    cloneStorages.value = (res.data || []).filter(s =>
      s.content && s.content.split(',').includes('images')
    )
  } catch (err) {
    console.warn('Could not fetch storages:', err)
  } finally {
    loadingStorages.value = false
  }
}

async function onTargetHostChange() {
  const hostId = cloneForm.value.targetHostId
  cloneNodes.value = []
  cloneStorages.value = []
  cloneForm.value.target = ''
  cloneForm.value.storage = ''
  if (!hostId) return
  try {
    const res = await api.proxmox.listNodes(hostId)
    cloneNodes.value = res.data || []
  } catch (err) {
    console.warn('Could not fetch nodes for selected host:', err)
  }
}

async function onTargetNodeChange() {
  const hostId = cloneForm.value.targetHostId || cloneTarget.value?.hostId
  const node = cloneForm.value.target || cloneTarget.value?.node
  cloneForm.value.storage = ''
  if (hostId && node) {
    await loadStoragesForNode(hostId, node)
  }
}

function closeCloneModal() {
  showCloneModal.value = false
  cloneTarget.value = null
  cloneError.value = ''
}

function showSuccessToast(msg, vmLink) {
  successToast.value = { show: true, message: msg, vmLink: vmLink || '' }
  setTimeout(() => { successToast.value.show = false }, 8000)
}

async function submitClone() {
  if (!cloneForm.value.newid || !cloneForm.value.name) return
  cloning.value = true
  cloneError.value = ''

  const { newid, name, target, full, storage } = cloneForm.value
  const payload = {
    newid,
    name,
    full: full ? 1 : 0,
    ...(target ? { target } : {}),
    ...(full && storage ? { storage } : {})
  }

  const resolvedNode = target || cloneTarget.value.node
  const resolvedHostId = cloneForm.value.targetHostId || cloneTarget.value.hostId

  try {
    await api.pveVm.clone(
      cloneTarget.value.hostId,
      cloneTarget.value.node,
      cloneTarget.value.vmid,
      payload
    )

    if (cloneForm.value.startAfterClone) {
      try {
        await api.pveVm.start(resolvedHostId, resolvedNode, newid)
      } catch (startErr) {
        console.warn('Could not start VM after clone:', startErr)
      }
    }

    const savedHostId = cloneTarget.value.hostId
    const wantCi = cloneForm.value.cloudInitSeed

    closeCloneModal()
    showSuccessToast(
      `VM ${newid} cloned successfully.`,
      `/proxmox/${savedHostId}/nodes/${resolvedNode}/vms/${newid}`
    )
    await loadTemplates()

    // Navigate to cloud-init editor if requested
    if (wantCi) {
      await router.push(`/cloud-init?hostId=${savedHostId}&node=${resolvedNode}&vmid=${newid}`)
    }
  } catch (err) {
    cloneError.value =
      err?.response?.data?.detail ||
      err?.response?.data?.message ||
      'Clone operation failed.'
  } finally {
    cloning.value = false
  }
}

// ── Metadata Modal ────────────────────────────────────────────────────────────
function openMetaModal(tpl) {
  metaTarget.value = tpl
  metaForm.value = {
    name: tpl.name || '',
    description: tpl.description || '',
    tags: tpl.tags || '',
  }
  metaError.value = ''
  metaSuccess.value = ''
  showMetaModal.value = true
}

function closeMetaModal() {
  showMetaModal.value = false
  metaTarget.value = null
}

async function saveMeta() {
  savingMeta.value = true
  metaError.value = ''
  metaSuccess.value = ''
  try {
    const payload = {}
    if (metaForm.value.name) payload.name = metaForm.value.name
    if (metaForm.value.description !== undefined) payload.description = metaForm.value.description
    if (metaForm.value.tags !== undefined) payload.tags = metaForm.value.tags
    await api.pveVm.updateConfig(
      metaTarget.value.hostId,
      metaTarget.value.node,
      metaTarget.value.vmid,
      payload
    )
    metaSuccess.value = 'Template info updated.'
    // Refresh local list
    await loadTemplates()
  } catch (err) {
    metaError.value = err?.response?.data?.detail || 'Failed to save metadata.'
  } finally {
    savingMeta.value = false
  }
}

// ── Library Download Modal ────────────────────────────────────────────────────
function openLibraryDownloadModal(tpl) {
  libraryTarget.value = tpl
  libError.value = ''
  libSuccess.value = ''
  libForm.value = {
    hostId: hosts.value[0]?.id || '',
    node: '',
    storage: '',
    url: tpl.downloadUrl,
    filename: tpl.downloadUrl.split('/').pop() || `${tpl.id}.qcow2`,
  }
  libNodes.value = []
  libStorages.value = []
  showLibraryModal.value = true
  if (libForm.value.hostId) {
    onLibHostChange()
  }
}

async function onLibHostChange() {
  libNodes.value = []
  libStorages.value = []
  libForm.value.node = ''
  libForm.value.storage = ''
  if (!libForm.value.hostId) return
  try {
    const res = await api.proxmox.listNodes(libForm.value.hostId)
    libNodes.value = res.data || []
    if (libNodes.value.length === 1) {
      libForm.value.node = libNodes.value[0].node
      onLibNodeChange()
    }
  } catch (err) {
    console.warn('Could not fetch nodes:', err)
  }
}

async function onLibNodeChange() {
  libStorages.value = []
  libForm.value.storage = ''
  const { hostId, node } = libForm.value
  if (!hostId || !node) return
  try {
    const res = await api.pveNode.listStorage(hostId, node)
    // Show all storages (images or vztmpl — user can pick)
    libStorages.value = res.data || []
    // Auto-select first images-capable storage
    const img = libStorages.value.find(s => s.content && s.content.includes('images'))
    if (img) libForm.value.storage = img.storage
  } catch (err) {
    console.warn('Could not fetch storages:', err)
  }
}

async function submitLibraryDownload() {
  libDownloading.value = true
  libError.value = ''
  libSuccess.value = ''
  try {
    const { hostId, node, storage, url, filename } = libForm.value
    await api.pveNode.downloadUrlToStorage(hostId, node, storage, {
      url,
      filename,
      content: 'import',
    })
    libSuccess.value = `Download started. Check the node task log in Proxmox to monitor progress. Once complete, import the image as a VM disk and convert it to a template.`
  } catch (err) {
    libError.value = err?.response?.data?.detail || 'Download request failed.'
  } finally {
    libDownloading.value = false
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadHosts()
  await loadTemplates()
})
</script>

<style scoped>
/* ── Layout ─────────────────────────────────────────────────────────────── */
.templates-page {
  padding: 1.5rem;
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1rem;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.page-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0.25rem 0 0;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.count-badge {
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 12px;
  padding: 0.1rem 0.6rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.search-input { width: 220px; }
.host-select  { width: 180px; }
.sort-select  { width: 150px; }

/* ── Tabs ───────────────────────────────────────────────────────────────── */
.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 1.25rem;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  padding: 0.6rem 1.25rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

/* ── Card ───────────────────────────────────────────────────────────────── */
.card {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}

.card-body { padding: 1.5rem; }
.p-0 { padding: 0; }

/* ── States ─────────────────────────────────────────────────────────────── */
.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 4rem 2rem;
  color: var(--text-secondary);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.empty-icon { font-size: 2.5rem; }

/* ── Table ──────────────────────────────────────────────────────────────── */
.table-container { overflow-x: auto; }

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.table th {
  background: var(--background);
  color: var(--text-secondary);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}

.table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
  vertical-align: middle;
}

.table tbody tr:last-child td { border-bottom: none; }
.table tbody tr:hover { background: rgba(255, 255, 255, 0.03); }

.vmid-cell { font-family: monospace; font-weight: 600; color: var(--primary-color) !important; }
.name-cell { font-weight: 500; }
.name-text { display: block; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mono { font-family: monospace; font-size: 0.8rem; }
.meta-val { font-size: 0.8rem; }
.dim { color: var(--text-secondary); font-size: 0.8rem; }
.notes-cell { max-width: 200px; }
.notes-text { font-size: 0.8rem; color: var(--text-secondary); cursor: help; }
.actions-cell { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }

/* ── OS Badges ──────────────────────────────────────────────────────────── */
.os-badge {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  background: rgba(100, 116, 139, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(100, 116, 139, 0.25);
  white-space: nowrap;
}

.os-ubuntu  { background: rgba(233, 84, 32, 0.12);   color: #f97316; border-color: rgba(249, 115, 22, 0.3); }
.os-debian  { background: rgba(167, 0, 51, 0.12);    color: #f472b6; border-color: rgba(244, 114, 182, 0.3); }
.os-centos  { background: rgba(156, 39, 176, 0.12);  color: #c084fc; border-color: rgba(192, 132, 252, 0.3); }
.os-rhel    { background: rgba(220, 38, 38, 0.12);   color: #f87171; border-color: rgba(248, 113, 113, 0.3); }
.os-rocky   { background: rgba(20, 184, 166, 0.12);  color: #2dd4bf; border-color: rgba(45, 212, 191, 0.3); }
.os-alma    { background: rgba(59, 130, 246, 0.12);  color: #60a5fa; border-color: rgba(96, 165, 250, 0.3); }
.os-fedora  { background: rgba(37, 99, 235, 0.12);   color: #818cf8; border-color: rgba(129, 140, 248, 0.3); }
.os-suse    { background: rgba(132, 204, 22, 0.12);  color: #a3e635; border-color: rgba(163, 230, 53, 0.3); }
.os-alpine  { background: rgba(14, 165, 233, 0.12);  color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); }
.os-arch    { background: rgba(14, 165, 233, 0.12);  color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); }
.os-windows { background: rgba(0, 120, 212, 0.12);   color: #7dd3fc; border-color: rgba(125, 211, 252, 0.3); }
.os-freebsd { background: rgba(220, 38, 38, 0.10);   color: #fca5a5; border-color: rgba(252, 165, 165, 0.3); }

/* ── Library Grid ───────────────────────────────────────────────────────── */
.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.25rem;
}

.library-card {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.library-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.1);
}

.library-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.library-badges {
  display: flex;
  gap: 0.35rem;
}

.badge-ci {
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 4px;
  padding: 0.1rem 0.45rem;
  font-size: 0.67rem;
  font-weight: 600;
}

.badge-lts {
  background: rgba(234, 179, 8, 0.12);
  color: #fbbf24;
  border: 1px solid rgba(234, 179, 8, 0.3);
  border-radius: 4px;
  padding: 0.1rem 0.45rem;
  font-size: 0.67rem;
  font-weight: 600;
}

.library-card-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.library-card-desc {
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
  flex: 1;
}

.library-card-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.library-card-url {
  font-size: 0.75rem;
}

.url-label {
  display: block;
  color: var(--text-secondary);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 0.7rem;
  margin-bottom: 0.2rem;
}

.url-text {
  font-family: monospace;
  color: #60a5fa;
  word-break: break-all;
}

.library-card-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.25rem;
}

/* ── Buttons ────────────────────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.15s;
  white-space: nowrap;
  color: var(--text-primary);
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-sm { padding: 0.3rem 0.65rem; font-size: 0.8rem; }

.btn-primary { background: var(--primary-color); color: white; border-color: var(--primary-color); }
.btn-primary:hover:not(:disabled) { background: #2563eb; border-color: #2563eb; }

.btn-outline { background: transparent; border-color: var(--border-color); }
.btn-outline:hover:not(:disabled) { background: rgba(255, 255, 255, 0.07); }

/* ── Form Controls ──────────────────────────────────────────────────────── */
.form-control {
  padding: 0.5rem 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 0.875rem;
  color: var(--text-primary);
  min-height: 36px;
  width: 100%;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.form-control:disabled { opacity: 0.5; cursor: not-allowed; }
.mono-input { font-family: monospace; font-size: 0.8rem; }

.form-group { margin-bottom: 1rem; }

.form-label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 0.4rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.checkbox-group { margin-bottom: 0.75rem; }

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--primary-color);
  cursor: pointer;
}

/* ── Radio group ────────────────────────────────────────────────────────── */
.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.radio-label {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
  transition: border-color 0.15s, background 0.15s;
}

.radio-label:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: var(--primary-color);
}

.radio-label input[type="radio"] {
  margin-top: 2px;
  accent-color: var(--primary-color);
  flex-shrink: 0;
}

.radio-label > span {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.radio-hint {
  font-size: 0.775rem;
  color: var(--text-secondary);
  font-weight: 400;
}

/* ── Info note ──────────────────────────────────────────────────────────── */
.info-note {
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.3);
  color: #fbbf24;
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
}

.hint-text {
  font-size: 0.775rem;
  color: var(--text-secondary);
}

/* ── Modal ──────────────────────────────────────────────────────────────── */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  background: var(--surface);
  z-index: 1;
}

.modal-header h3 { margin: 0; font-size: 1.1rem; color: var(--text-primary); }

.btn-close {
  background: none;
  border: none;
  font-size: 1.4rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.btn-close:hover { color: var(--text-primary); }

.modal-body { padding: 1.5rem; }

/* ── Alert ──────────────────────────────────────────────────────────────── */
.alert {
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
}

.alert-danger {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.alert-success {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #34d399;
}

/* ── Toast ──────────────────────────────────────────────────────────────── */
.toast-success {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.4);
  color: #34d399;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.875rem;
  z-index: 2000;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  max-width: 380px;
}

.toast-link {
  color: #6ee7b7;
  text-decoration: underline;
  font-weight: 600;
  white-space: nowrap;
}

.toast-link:hover { color: #a7f3d0; }

.toast-close {
  background: none;
  border: none;
  color: #34d399;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  margin-left: auto;
  opacity: 0.7;
}

.toast-close:hover { opacity: 1; }

.toast-fade-enter-active,
.toast-fade-leave-active { transition: opacity 0.3s ease, transform 0.3s ease; }
.toast-fade-enter-from,
.toast-fade-leave-to { opacity: 0; transform: translateY(0.5rem); }

/* ── Utilities ──────────────────────────────────────────────────────────── */
.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-2 { margin-top: 0.5rem; }
.mt-3 { margin-top: 1rem; }
.mb-2 { margin-bottom: 0.5rem; }
.mb-3 { margin-bottom: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-secondary); }
.text-danger { color: var(--danger-color, #ef4444); }
</style>
