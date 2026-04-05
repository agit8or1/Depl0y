<template>
  <div id="app" class="app-container">
    <Sidebar v-if="isAuthenticated && !isFullscreen" />
    <div class="main-content" :class="{ 'full-width': !isAuthenticated || isFullscreen }">
      <Header v-if="isAuthenticated && !isFullscreen" />
      <main :class="isFullscreen ? 'content-fullscreen' : 'content'">
        <router-view />
      </main>
    </div>

  </div>
</template>

<script>
import { computed } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useRoute } from 'vue-router'
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
    const route = useRoute()
    const isAuthenticated = computed(() => authStore.isAuthenticated)
    const isFullscreen = computed(() => route.meta?.layout === 'fullscreen')

    return {
      isAuthenticated,
      isFullscreen
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

.content-fullscreen {
  flex: 1;
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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
