<template>
  <div class="deploy-hub-page">
    <div class="page-header">
      <h2>Deploy</h2>
      <p class="subtitle">Choose what you want to deploy</p>
    </div>

    <div class="deploy-hub-grid">
      <!-- Row 1: Standard VM + AI VM -->
      <router-link to="/vms/create" class="hub-card">
        <div class="hub-icon">🖥️</div>
        <h3>Standard VM</h3>
        <p>Create a general-purpose virtual machine. Choose OS, CPU, RAM, disk, and network settings. Full control over the VM configuration.</p>
        <ul class="hub-features">
          <li>Any OS image (Ubuntu, Debian, AlmaLinux, etc.)</li>
          <li>Manual or cloud-init configuration</li>
          <li>Custom CPU, RAM, disk, and networking</li>
        </ul>
        <div class="hub-cta">Configure VM →</div>
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
        <div class="hub-cta">Deploy AI VM →</div>
      </router-link>

      <!-- Row 2: Native PVE + LXC + Import -->
      <router-link to="/create-pve-vm" class="hub-card hub-card-pve">
        <div class="hub-icon">⚙️</div>
        <h3>Native PVE VM</h3>
        <p>Create a VM directly in Proxmox VE with full hardware control. Ideal for advanced configurations, nested virtualisation, or custom BIOS/UEFI setups.</p>
        <ul class="hub-features">
          <li>Full Proxmox hardware options (BIOS, UEFI, OVMF)</li>
          <li>CPU pinning, NUMA, and balloon memory</li>
          <li>PCIe passthrough and custom device mappings</li>
        </ul>
        <div class="hub-cta">Create PVE VM →</div>
      </router-link>

      <router-link to="/create-lxc" class="hub-card hub-card-lxc">
        <div class="hub-icon">📦</div>
        <h3>LXC Container</h3>
        <p>Lightweight Linux container using Proxmox LXC. Fast to start, low overhead, and shares the host kernel — great for services and microservices.</p>
        <ul class="hub-features">
          <li>Minimal resource usage vs. full VMs</li>
          <li>Pre-built CT templates (Debian, Alpine, Ubuntu)</li>
          <li>Persistent storage with bind mounts</li>
        </ul>
        <div class="hub-cta">Create Container →</div>
      </router-link>

      <router-link to="/import-vm" class="hub-card hub-card-import">
        <div class="hub-icon">📥</div>
        <h3>Import VM</h3>
        <p>Import an existing VMware or OVF virtual machine into Proxmox. Migrate workloads from VMware ESXi, Workstation, or other hypervisors with ease.</p>
        <ul class="hub-features">
          <li>VMware OVF / OVA / VMDK support</li>
          <li>Automatic disk format conversion</li>
          <li>Preserves VM metadata and settings where possible</li>
        </ul>
        <div class="hub-cta">Import VM →</div>
      </router-link>
    </div>
  </div>
</template>

<script>
export default { name: 'Deploy' }
</script>

<style scoped>
.deploy-hub-page {
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.page-header {
  text-align: center;
  width: 100%;
  margin-bottom: 2rem;
}

.page-header h2 {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0 0 0.25rem;
}

.subtitle {
  color: var(--text-secondary);
  margin: 0;
}

.deploy-hub-grid {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
}

/* First two cards span the top row as a 2-col layout within 3-col grid */
.deploy-hub-grid > *:nth-child(1),
.deploy-hub-grid > *:nth-child(2) {
  grid-column: span 1;
}

/* Force the top two cards to sit together and be wider on the 3-col grid */
/* Use a sub-grid approach: first two cards each take 1.5 cols visually */
/* Simpler: keep 3-col, top row first 2 cards each col, 3rd col empty on row 1 */
/* Then row 2 all three fill the grid */

@media (max-width: 900px) {
  .deploy-hub-grid {
    grid-template-columns: repeat(2, 1fr);
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
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.12);
  transform: translateY(-2px);
}

/* AI — purple */
.hub-card-ai {
  border-color: #8b5cf6;
}

.hub-card-ai:hover {
  border-color: #6366f1;
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.15);
}

/* Native PVE — green */
.hub-card-pve {
  border-color: #22c55e;
}

.hub-card-pve:hover {
  border-color: #16a34a;
  box-shadow: 0 4px 20px rgba(34, 197, 94, 0.15);
}

/* LXC — teal */
.hub-card-lxc {
  border-color: #14b8a6;
}

.hub-card-lxc:hover {
  border-color: #0d9488;
  box-shadow: 0 4px 20px rgba(20, 184, 166, 0.15);
}

/* Import — yellow */
.hub-card-import {
  border-color: #eab308;
}

.hub-card-import:hover {
  border-color: #ca8a04;
  box-shadow: 0 4px 20px rgba(234, 179, 8, 0.15);
}

.hub-icon {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

.hub-card h3 {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0 0 0.75rem;
  color: var(--text-primary, #f1f5f9);
}

.hub-card p {
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.5;
  margin: 0 0 1rem;
}

.hub-features {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  flex: 1;
}

.hub-features li {
  font-size: 0.85rem;
  color: var(--text-secondary);
  padding: 0.2rem 0;
}

.hub-features li::before {
  content: '✓ ';
  color: #10b981;
  font-weight: 700;
}

.hub-cta {
  font-weight: 600;
  font-size: 0.9rem;
  margin-top: auto;
  color: #3b82f6;
}

.hub-card-ai .hub-cta {
  color: #8b5cf6;
}

.hub-card-pve .hub-cta {
  color: #22c55e;
}

.hub-card-lxc .hub-cta {
  color: #14b8a6;
}

.hub-card-import .hub-cta {
  color: #eab308;
}
</style>
