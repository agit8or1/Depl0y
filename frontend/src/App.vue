<template>
  <div id="app" class="app-container">
    <!-- Overlay backdrop for mobile sidebar -->
    <div
      v-if="isAuthenticated && !isFullscreen && sidebarOpen"
      class="sidebar-overlay"
      @click="sidebarOpen = false"
    />

    <Sidebar
      v-if="isAuthenticated && !isFullscreen"
      :is-open="sidebarOpen"
      @close="sidebarOpen = false"
    />
    <div class="main-content" :class="{ 'full-width': !isAuthenticated || isFullscreen }">
      <Header
        v-if="isAuthenticated && !isFullscreen"
        @toggle-sidebar="sidebarOpen = !sidebarOpen"
      />
      <main :class="isFullscreen ? 'content-fullscreen' : 'content'">
        <router-view />
      </main>
    </div>

  </div>
</template>

<script>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
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

    // Sidebar open: default true on desktop, false on mobile
    const sidebarOpen = ref(window.innerWidth > 768)

    const handleResize = () => {
      if (window.innerWidth > 768) {
        sidebarOpen.value = true
      }
    }

    onMounted(() => window.addEventListener('resize', handleResize))
    onBeforeUnmount(() => window.removeEventListener('resize', handleResize))

    return {
      isAuthenticated,
      isFullscreen,
      sidebarOpen
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

.sidebar-overlay {
  display: none;
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
  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 99;
  }

  .main-content {
    margin-left: 0;
  }

  .content {
    padding: 1rem;
  }
}
</style>
