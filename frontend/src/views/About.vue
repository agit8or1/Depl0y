<template>
  <div class="about-page">
    <div class="hero-card card">
      <div class="logo-section">
        <h1 class="about-logo">Depl<span class="logo-zero">0</span>y</h1>
        <p class="tagline">VM Deployment Panel for Proxmox VE</p>
        <div class="badges">
          <span class="badge badge-success">Running</span>
          <span class="version-badge">v{{ version }}</span>
        </div>
      </div>

      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">Backend</span>
          <span class="info-value">FastAPI (Python)</span>
        </div>
        <div class="info-item">
          <span class="info-label">Frontend</span>
          <span class="info-value">Vue.js 3</span>
        </div>
        <div class="info-item">
          <span class="info-label">Database</span>
          <span class="info-value">SQLite</span>
        </div>
        <div class="info-item">
          <span class="info-label">License</span>
          <span class="info-value">Open Source</span>
        </div>
      </div>
    </div>

    <div class="card builder-card">
      <div class="builder-inner">
        <div class="builder-icon">🚀</div>
        <div class="builder-info">
          <p class="builder-by">Built by</p>
          <a href="https://mspreboot.com" target="_blank" rel="noopener noreferrer" class="builder-name">
            Agit8or
          </a>
          <p class="builder-url">mspreboot.com</p>
        </div>
        <div class="builder-links">
          <a href="https://github.com/agit8or1/Depl0y" target="_blank" rel="noopener noreferrer" class="builder-link-btn">
            GitHub
          </a>
          <a href="https://github.com/agit8or1/Depl0y/issues" target="_blank" rel="noopener noreferrer" class="builder-link-btn">
            Issues
          </a>
          <a href="https://github.com/sponsors/agit8or1" target="_blank" rel="noopener noreferrer" class="builder-link-btn sponsor-btn">
            ❤️ Sponsor
          </a>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 class="section-title">Features</h3>
      <div class="features-grid">
        <div class="feature-item" v-for="feature in features" :key="feature">
          <span class="feature-icon">✓</span>
          <span>{{ feature }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import api from '@/services/api'

export default {
  name: 'About',
  setup() {
    const version = ref('...')

    const features = [
      'Automated VM Deployment',
      'Cloud-init Support',
      'ISO Management',
      'Cloud Image Deployments',
      'Multi-user Authentication',
      '2FA Support (TOTP)',
      'Update Management',
      'Resource Monitoring',
      'Proxmox API Integration',
      'LLM / AI VM Deployments',
      'High Availability',
      'Linux VM Security Agent',
    ]

    onMounted(async () => {
      try {
        const response = await api.system.getInfo()
        if (response.data?.version) version.value = response.data.version
      } catch {
        version.value = '—'
      }
    })

    return { version, features }
  }
}
</script>

<style scoped>
.about-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 860px;
  margin: 0 auto;
}

.hero-card {
  padding: 2.5rem 2rem;
}

.logo-section {
  text-align: center;
  padding-bottom: 2rem;
  margin-bottom: 2rem;
  border-bottom: 2px solid var(--border-color);
}

.about-logo {
  font-size: 4rem;
  font-weight: 700;
  margin: 0;
  letter-spacing: -2px;
  color: var(--text-primary);
}

.logo-zero {
  color: #3b82f6;
}

.tagline {
  font-size: 1.2rem;
  color: var(--text-secondary);
  margin: 0.5rem 0 1rem;
}

.badges {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.75rem;
}

.version-badge {
  background: var(--background);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 600;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 1rem;
  background: var(--background);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
}

.info-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
  font-weight: 600;
}

.info-value {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.builder-card {
  padding: 0;
  overflow: hidden;
  background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #1d4ed8 100%);
  border: none;
}

.builder-inner {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1.75rem 2rem;
  flex-wrap: wrap;
}

.builder-icon {
  font-size: 3rem;
  filter: drop-shadow(0 4px 6px rgba(0,0,0,0.3));
  flex-shrink: 0;
}

.builder-info {
  flex: 1;
  color: white;
}

.builder-by {
  margin: 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  opacity: 0.8;
}

.builder-name {
  display: block;
  color: white;
  text-decoration: none;
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1.2;
  transition: opacity 0.2s;
}

.builder-name:hover {
  opacity: 0.85;
  text-decoration: underline;
}

.builder-url {
  margin: 0.25rem 0 0;
  font-size: 0.9rem;
  opacity: 0.75;
  font-family: monospace;
}

.builder-links {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.builder-link-btn {
  display: inline-block;
  padding: 0.45rem 1rem;
  background: rgba(255,255,255,0.15);
  color: white;
  text-decoration: none;
  border-radius: 0.375rem;
  font-size: 0.85rem;
  font-weight: 600;
  border: 1px solid rgba(255,255,255,0.25);
  transition: background 0.2s;
}

.builder-link-btn:hover {
  background: rgba(255,255,255,0.25);
}

.sponsor-btn {
  background: rgba(236, 72, 153, 0.3);
  border-color: rgba(236, 72, 153, 0.5);
}

.sponsor-btn:hover {
  background: rgba(236, 72, 153, 0.5);
}

.section-title {
  margin: 0 0 1.25rem 0;
  font-size: 1.1rem;
  font-weight: 600;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--border-color);
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 0.75rem;
  background: var(--background);
  border-radius: 0.375rem;
  border: 1px solid var(--border-color);
  font-size: 0.875rem;
}

.feature-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  height: 1.25rem;
  background: var(--secondary-color);
  color: white;
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: bold;
  flex-shrink: 0;
}

@media (max-width: 600px) {
  .builder-inner {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
