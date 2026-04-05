<template>
  <div class="notfound-page">
    <div class="notfound-card">
      <div class="error-code">404</div>
      <h1 class="error-title">Page Not Found</h1>
      <p class="error-message">
        The page you're looking for doesn't exist or has been moved.
        Check the URL or head back to the dashboard.
      </p>
      <router-link to="/" class="home-btn">Go to Dashboard</router-link>
    </div>
  </div>
</template>

<script>
export default {
  name: 'NotFound'
}
</script>

<style scoped>
.notfound-page {
  min-height: calc(100vh - 4rem);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.notfound-card {
  background: var(--card-bg, #1e2235);
  border: 1px solid var(--border-color, #2d3348);
  border-radius: 1.25rem;
  padding: 3rem 4rem;
  text-align: center;
  max-width: 480px;
  width: 100%;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.3);
}

.error-code {
  font-size: 7rem;
  font-weight: 800;
  line-height: 1;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 1rem;
  letter-spacing: -2px;
}

.error-title {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-primary, #f1f5f9);
  margin: 0 0 1rem;
}

.error-message {
  color: var(--text-secondary, #94a3b8);
  font-size: 0.95rem;
  line-height: 1.6;
  margin: 0 0 2rem;
}

.home-btn {
  display: inline-block;
  background: #3b82f6;
  color: #fff;
  font-weight: 600;
  font-size: 0.95rem;
  padding: 0.7rem 1.75rem;
  border-radius: 0.6rem;
  text-decoration: none;
  transition: background 0.2s, transform 0.15s, box-shadow 0.2s;
}

.home-btn:hover {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.35);
}

@media (max-width: 480px) {
  .notfound-card {
    padding: 2rem 1.5rem;
  }

  .error-code {
    font-size: 5rem;
  }

  .error-title {
    font-size: 1.3rem;
  }
}
</style>
