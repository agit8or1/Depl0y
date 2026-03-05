<template>
  <div class="support-page">
    <div class="page-header">
      <h2>Support This Project</h2>
      <p class="text-muted">Depl0y is open source and free. Here's how you can help keep it going.</p>
    </div>

    <div class="support-grid">
      <!-- Visit mspreboot.com -->
      <a href="https://mspreboot.com" target="_blank" rel="noopener noreferrer" class="support-card">
        <div class="card-icon globe-icon">🌐</div>
        <h3>Visit mspreboot.com</h3>
        <p>Check out the team behind Depl0y. See other projects, tools, and resources we build.</p>
        <span class="card-link">mspreboot.com →</span>
      </a>

      <!-- GitHub Stars -->
      <a href="https://github.com/agit8or1/Depl0y" target="_blank" rel="noopener noreferrer" class="support-card">
        <div class="card-icon star-icon">⭐</div>
        <h3>Star on GitHub</h3>
        <p>Give Depl0y a star on GitHub — it helps others discover the project and keeps us motivated.</p>
        <span class="card-link">github.com/agit8or1/Depl0y →</span>
      </a>

      <!-- Sponsor -->
      <a href="https://github.com/sponsors/agit8or1" target="_blank" rel="noopener noreferrer" class="support-card sponsor-card">
        <div class="card-icon heart-icon">❤️</div>
        <h3>Sponsor the Project</h3>
        <p>Buy us a coffee via GitHub Sponsors. Every contribution helps fund continued development and new features.</p>
        <span class="card-link">Become a sponsor →</span>
      </a>
    </div>

    <div class="card contribute-card">
      <h3>Other Ways to Help</h3>
      <div class="contribute-grid">
        <div class="contribute-item">
          <div class="contribute-icon">🐛</div>
          <div>
            <h4>Report Bugs</h4>
            <p class="text-sm text-muted">Found an issue? Open a GitHub issue so we can fix it.</p>
            <a href="https://github.com/agit8or1/Depl0y/issues" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline">
              Open an Issue
            </a>
          </div>
        </div>
        <div class="contribute-item">
          <div class="contribute-icon">💡</div>
          <div>
            <h4>Request Features</h4>
            <p class="text-sm text-muted">Have an idea? Share it on GitHub Discussions.</p>
            <a href="https://github.com/agit8or1/Depl0y/discussions" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline">
              Start a Discussion
            </a>
          </div>
        </div>
        <div class="contribute-item">
          <div class="contribute-icon">🔀</div>
          <div>
            <h4>Contribute Code</h4>
            <p class="text-sm text-muted">Pull requests are welcome — fork the repo and dive in.</p>
            <a href="https://github.com/agit8or1/Depl0y/fork" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline">
              Fork on GitHub
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Support'
}
</script>

<style scoped>
.support-page {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  max-width: 1000px;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
}

.support-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
}

.support-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 2rem;
  background: white;
  border-radius: 0.75rem;
  border: 2px solid var(--border-color);
  box-shadow: var(--shadow-md);
  text-decoration: none;
  color: var(--text-primary);
  transition: all 0.2s;
  cursor: pointer;
}

.support-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.15);
  transform: translateY(-2px);
}

.sponsor-card:hover {
  border-color: #ec4899;
  box-shadow: 0 8px 24px rgba(236, 72, 153, 0.15);
}

.card-icon {
  font-size: 2.5rem;
  line-height: 1;
}

.support-card h3 {
  margin: 0;
  font-size: 1.2rem;
}

.support-card p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.5;
  flex: 1;
}

.card-link {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--primary-color);
}

.sponsor-card .card-link {
  color: #ec4899;
}

.contribute-card {
  padding: 2rem;
}

.contribute-card h3 {
  margin: 0 0 1.5rem 0;
  font-size: 1.2rem;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--border-color);
}

.contribute-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.5rem;
}

.contribute-item {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.contribute-icon {
  font-size: 1.75rem;
  line-height: 1;
  flex-shrink: 0;
}

.contribute-item h4 {
  margin: 0 0 0.25rem 0;
  font-size: 1rem;
}

.contribute-item p {
  margin: 0 0 0.75rem 0;
}

.text-muted {
  color: var(--text-secondary);
}

.text-sm {
  font-size: 0.875rem;
}
</style>
