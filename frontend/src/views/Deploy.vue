<template>
  <div class="deploy-hub-page">
    <div class="page-header">
      <h2>Deploy</h2>
      <p class="subtitle">Choose what you want to deploy</p>
    </div>

    <div class="deploy-hub-grid">
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
    </div>
  </div>
</template>

<script>
export default { name: 'Deploy' }
</script>

<style scoped>
.deploy-hub-page {
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.page-header {
  text-align: center;
  width: 100%;
}

.deploy-hub-grid {
  width: 100%;
}

.page-header {
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
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 640px) {
  .deploy-hub-grid { grid-template-columns: 1fr; }
}

.hub-card {
  display: flex;
  flex-direction: column;
  background: var(--card-bg, #fff);
  border: 2px solid var(--border-color, #e5e7eb);
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

.hub-card-ai {
  border-color: #8b5cf6;
}

.hub-card-ai:hover {
  border-color: #6366f1;
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.15);
}

.hub-icon {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

.hub-card h3 {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0 0 0.75rem;
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
  color: #3b82f6;
  font-size: 0.9rem;
  margin-top: auto;
}

.hub-card-ai .hub-cta {
  color: #6366f1;
}
</style>
