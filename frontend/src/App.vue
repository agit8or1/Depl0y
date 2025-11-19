<template>
  <div id="app" class="app-container">
    <Sidebar v-if="isAuthenticated" />
    <div class="main-content" :class="{ 'full-width': !isAuthenticated }">
      <Header v-if="isAuthenticated" />
      <main class="content">
        <router-view />
      </main>
    </div>

  </div>
</template>

<script>
import { computed } from 'vue'
import { useAuthStore } from '@/store/auth'
import Sidebar from '@/components/layout/Sidebar.vue'
import Header from '@/components/layout/Header.vue'

export default {
  name: 'App',
  components: {
    Sidebar,
    Header
  },
  setup() {
    const authStore = useAuthStore()
    const isAuthenticated = computed(() => authStore.isAuthenticated)

    return {
      isAuthenticated
    }
  }
}
</script>

<style scoped>
.app-container {
  display: flex;
  min-height: 100vh;
  background-color: #f5f7fa;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: 250px;
  transition: margin-left 0.3s ease;
}

.main-content.full-width {
  margin-left: 0;
}

.content {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
}

@media (max-width: 768px) {
  .main-content {
    margin-left: 0;
  }

  .content {
    padding: 1rem;
  }
}
</style>
