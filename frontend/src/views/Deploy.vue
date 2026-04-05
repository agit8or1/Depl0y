<template>
  <div class="deploy-hub-page">
    <div class="page-header">
      <h2>Deploy</h2>
      <p class="subtitle">Choose a deployment type to launch the wizard</p>
    </div>

    <!-- Wizard Cards -->
    <div class="deploy-hub-grid">
      <router-link to="/vms/create" class="hub-card">
        <div class="hub-icon">🖥️</div>
        <h3>Standard VM</h3>
        <p>Create a general-purpose virtual machine. Full tabbed wizard with General, System, CPU, Memory, Disks, Network, Cloud-Init, and Summary steps.</p>
        <ul class="hub-features">
          <li>Any OS: Ubuntu, Debian, AlmaLinux, Windows, etc.</li>
          <li>ISO or Cloud Image installation</li>
          <li>Multiple disks, NICs, CPU flags, NUMA</li>
          <li>BIOS / UEFI / TPM 2.0 support</li>
          <li>VM ID check, tag chips, CLI preview</li>
        </ul>
        <div class="hub-cta">Launch Wizard →</div>
      </router-link>

      <router-link to="/llm-deploy" class="hub-card hub-card-ai">
        <div class="hub-icon">🤖</div>
        <h3>AI / LLM VM</h3>
        <p>Deploy a self-hosted AI inference server with a guided wizard. Supports chat, coding, document analysis, reasoning, and image generation.</p>
        <ul class="hub-features">
          <li>Ollama, vLLM, LocalAI, llama.cpp, Stable Diffusion</li>
          <li>Simple 4-click wizard or full advanced mode</li>
          <li>Auto-configured GPU passthrough</li>
          <li>Open WebUI, ComfyUI, or Meme Maker UI included</li>
        </ul>
        <div class="hub-cta">Launch Wizard →</div>
      </router-link>

      <router-link to="/create-pve-vm" class="hub-card hub-card-pve">
        <div class="hub-icon">⚙️</div>
        <h3>Native PVE VM</h3>
        <p>Create a VM directly in Proxmox VE with full hardware control. Ideal for advanced configurations, nested virtualisation, or custom BIOS/UEFI setups.</p>
        <ul class="hub-features">
          <li>Full Proxmox hardware options (BIOS, UEFI, OVMF)</li>
          <li>CPU pinning, NUMA, and balloon memory</li>
          <li>PCIe passthrough and custom device mappings</li>
        </ul>
        <div class="hub-cta">Launch Wizard →</div>
      </router-link>

      <router-link to="/create-lxc" class="hub-card hub-card-lxc">
        <div class="hub-icon">📦</div>
        <h3>LXC Container</h3>
        <p>Lightweight Linux container using Proxmox LXC. Tabbed wizard with template library, multiple NICs, mount points, and container features.</p>
        <ul class="hub-features">
          <li>Local templates or pull from library (11+ distros)</li>
          <li>Multiple network interfaces (net0–net3)</li>
          <li>Additional mount points beyond rootfs</li>
          <li>FUSE, nesting, NFS, CIFS, keyctl features</li>
        </ul>
        <div class="hub-cta">Launch Wizard →</div>
      </router-link>

      <router-link to="/import-vm" class="hub-card hub-card-import">
        <div class="hub-icon">📥</div>
        <h3>Import VM</h3>
        <p>Import an existing VMware or OVF virtual machine into Proxmox. Migrate workloads from VMware ESXi, Workstation, or other hypervisors.</p>
        <ul class="hub-features">
          <li>VMware OVF / OVA / VMDK support</li>
          <li>Automatic disk format conversion</li>
          <li>Preserves VM metadata and settings</li>
        </ul>
        <div class="hub-cta">Launch Wizard →</div>
      </router-link>
    </div>

    <!-- Recent Deployments -->
    <div class="recent-deployments">
      <div class="recent-header">
        <h3>Recent Deployments</h3>
        <router-link to="/vms" class="view-all-link">View all VMs →</router-link>
      </div>

      <div v-if="loadingRecent" class="recent-loading">
        <div class="recent-spinner"></div>
        <span>Loading recent deployments...</span>
      </div>

      <div v-else-if="recentVMs.length === 0" class="recent-empty">
        <div class="recent-empty-icon">🖥️</div>
        <p>No VMs deployed yet. Create your first VM above.</p>
      </div>

      <div v-else class="recent-list">
        <div v-for="vm in recentVMs" :key="vm.id" class="recent-item">
          <div class="recent-item-icon" :class="statusClass(vm.status)">
            {{ statusIcon(vm.status) }}
          </div>
          <div class="recent-item-info">
            <div class="recent-item-name">{{ vm.name }}</div>
            <div class="recent-item-meta">
              <span class="recent-item-status" :class="statusClass(vm.status)">{{ vm.status }}</span>
              <span class="recent-item-time">{{ formatRelativeTime(vm.created_at) }}</span>
            </div>
          </div>
          <div class="recent-item-actions">
            <router-link :to="`/vms/${vm.id}`" class="btn btn-sm btn-outline">View →</router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import toast from '@/plugins/toast.js'

export default {
  name: 'Deploy',

  setup() {
    const recentVMs = ref([])
    const loadingRecent = ref(true)

    const loadRecentDeployments = async () => {
      loadingRecent.value = true
      try {
        const r = await api.dashboard.getActivity({ limit: 5 })
        recentVMs.value = r.data.recent_vms || []
      } catch (e) {
        toast.warning('Could not load recent deployments')
        recentVMs.value = []
      } finally {
        loadingRecent.value = false
      }
    }

    const statusIcon = (status) => {
      const icons = {
        running: '▶',
        stopped: '■',
        creating: '⟳',
        error: '✕',
        paused: '⏸',
      }
      return icons[status] || '○'
    }

    const statusClass = (status) => {
      const map = {
        running: 'status-running',
        stopped: 'status-stopped',
        creating: 'status-creating',
        error: 'status-error',
        paused: 'status-paused',
      }
      return map[status] || ''
    }

    const formatRelativeTime = (isoStr) => {
      if (!isoStr) return ''
      const diff = Date.now() - new Date(isoStr).getTime()
      const minutes = Math.floor(diff / 60000)
      const hours = Math.floor(minutes / 60)
      const days = Math.floor(hours / 24)
      if (days > 0) return `${days}d ago`
      if (hours > 0) return `${hours}h ago`
      if (minutes > 0) return `${minutes}m ago`
      return 'just now'
    }

    onMounted(loadRecentDeployments)

    return { recentVMs, loadingRecent, statusIcon, statusClass, formatRelativeTime }
  }
}
</script>

<style scoped>
.deploy-hub-page {
  max-width: 1100px;
  margin: 0 auto;
  padding-bottom: 3rem;
}

.page-header {
  text-align: center;
  margin-bottom: 2.5rem;
}

.page-header h2 {
  font-size: 2rem;
  font-weight: 700;
  margin: 0 0 0.3rem;
}

.subtitle {
  color: var(--text-secondary);
  margin: 0;
  font-size: 1rem;
}

/* Card grid */
.deploy-hub-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
  margin-bottom: 3rem;
}

/* 5th card spans full row 3 / centered */
.deploy-hub-grid > *:nth-child(4) { grid-column: 1; }
.deploy-hub-grid > *:nth-child(5) { grid-column: 2; }

@media (max-width: 960px) {
  .deploy-hub-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .deploy-hub-grid > *:nth-child(4),
  .deploy-hub-grid > *:nth-child(5) {
    grid-column: span 1;
  }
}

@media (max-width: 640px) {
  .deploy-hub-grid {
    grid-template-columns: 1fr;
  }
}

.hub-card {
  display: flex;
  flex-direction: column;
  background: var(--card-bg, #1e2235);
  border: 2px solid var(--border-color, #2d3348);
  border-radius: 1rem;
  padding: 2rem;
  text-decoration: none;
  color: inherit;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
}

.hub-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 6px 24px rgba(59, 130, 246, 0.14);
  transform: translateY(-3px);
}

.hub-card-ai { border-color: #8b5cf6; }
.hub-card-ai:hover { border-color: #6366f1; box-shadow: 0 6px 24px rgba(99, 102, 241, 0.16); }

.hub-card-pve { border-color: #22c55e; }
.hub-card-pve:hover { border-color: #16a34a; box-shadow: 0 6px 24px rgba(34, 197, 94, 0.16); }

.hub-card-lxc { border-color: #14b8a6; }
.hub-card-lxc:hover { border-color: #0d9488; box-shadow: 0 6px 24px rgba(20, 184, 166, 0.16); }

.hub-card-import { border-color: #eab308; }
.hub-card-import:hover { border-color: #ca8a04; box-shadow: 0 6px 24px rgba(234, 179, 8, 0.16); }

.hub-icon { font-size: 2.75rem; margin-bottom: 1rem; }

.hub-card h3 {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0 0 0.75rem;
  color: var(--text-primary, #f1f5f9);
}

.hub-card p {
  color: var(--text-secondary);
  font-size: 0.875rem;
  line-height: 1.6;
  margin: 0 0 1rem;
}

.hub-features {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  flex: 1;
}

.hub-features li {
  font-size: 0.825rem;
  color: var(--text-secondary);
  padding: 0.2rem 0;
  padding-left: 1.25rem;
  position: relative;
}

.hub-features li::before {
  content: '✓';
  position: absolute;
  left: 0;
  color: #10b981;
  font-weight: 700;
}

.hub-cta {
  font-weight: 600;
  font-size: 0.9rem;
  margin-top: auto;
  color: #3b82f6;
  padding: 0.6rem 1.2rem;
  border: 1.5px solid #3b82f6;
  border-radius: 0.5rem;
  text-align: center;
  transition: background 0.2s, color 0.2s;
}

.hub-card:hover .hub-cta {
  background: #3b82f6;
  color: white;
}

.hub-card-ai .hub-cta { color: #8b5cf6; border-color: #8b5cf6; }
.hub-card-ai:hover .hub-cta { background: #8b5cf6; color: white; }

.hub-card-pve .hub-cta { color: #22c55e; border-color: #22c55e; }
.hub-card-pve:hover .hub-cta { background: #22c55e; color: white; }

.hub-card-lxc .hub-cta { color: #14b8a6; border-color: #14b8a6; }
.hub-card-lxc:hover .hub-cta { background: #14b8a6; color: white; }

.hub-card-import .hub-cta { color: #eab308; border-color: #eab308; }
.hub-card-import:hover .hub-cta { background: #eab308; color: white; }

/* Recent Deployments */
.recent-deployments {
  background: var(--card-bg, #1e2235);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 1rem;
  padding: 1.75rem;
}

.recent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.recent-header h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-primary);
}

.view-all-link {
  font-size: 0.875rem;
  color: #3b82f6;
  text-decoration: none;
  font-weight: 500;
}

.view-all-link:hover { text-decoration: underline; }

.recent-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.5rem;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.recent-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border-color);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  flex-shrink: 0;
}

.recent-empty {
  text-align: center;
  padding: 2.5rem 1rem;
  color: var(--text-secondary);
}

.recent-empty-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
.recent-empty p { margin: 0; font-size: 0.9rem; }

.recent-list { display: flex; flex-direction: column; gap: 0; }

.recent-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.875rem 0;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.1s;
}

.recent-item:last-child { border-bottom: none; padding-bottom: 0; }
.recent-item:first-child { padding-top: 0; }

.recent-item:hover { background: rgba(255,255,255,0.02); }

.recent-item-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: 700;
  flex-shrink: 0;
  background: var(--border-color);
  color: var(--text-secondary);
}

.recent-item-icon.status-running { background: #d1fae5; color: #059669; }
.recent-item-icon.status-stopped { background: #f3f4f6; color: #6b7280; }
.recent-item-icon.status-creating { background: #dbeafe; color: #2563eb; }
.recent-item-icon.status-error { background: #fee2e2; color: #ef4444; }
.recent-item-icon.status-paused { background: #fef9c3; color: #ca8a04; }

.recent-item-info { flex: 1; min-width: 0; }

.recent-item-name {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-item-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.2rem;
}

.recent-item-status {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.recent-item-status.status-running { color: #059669; }
.recent-item-status.status-stopped { color: #6b7280; }
.recent-item-status.status-creating { color: #2563eb; }
.recent-item-status.status-error { color: #ef4444; }
.recent-item-status.status-paused { color: #ca8a04; }

.recent-item-time {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.recent-item-actions { flex-shrink: 0; }

.btn-sm {
  padding: 0.3rem 0.875rem;
  font-size: 0.8rem;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
