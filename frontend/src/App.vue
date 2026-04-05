<template>
  <div id="app" class="app-container">
    <!-- Overlay backdrop for mobile sidebar -->
    <transition name="fade">
      <div
        v-if="isAuthenticated && !isFullscreen && sidebarOpen && isMobile"
        class="sidebar-overlay"
        @click="sidebarOpen = false"
      />
    </transition>

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

    const isMobile = ref(window.innerWidth <= 768)

    // Sidebar open: default true on desktop, false on mobile
    const sidebarOpen = ref(window.innerWidth > 768)

    const handleResize = () => {
      const mobile = window.innerWidth <= 768
      isMobile.value = mobile
      if (!mobile) {
        sidebarOpen.value = true
      }
    }

    onMounted(() => {
      window.addEventListener('resize', handleResize)
      // Apply saved theme on startup
      applyTheme(localStorage.getItem('depl0y_theme') || 'light')
    })

    onBeforeUnmount(() => window.removeEventListener('resize', handleResize))

    const applyTheme = (theme) => {
      const root = document.documentElement
      if (theme === 'system') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
        root.setAttribute('data-theme', prefersDark ? 'dark' : 'light')
      } else {
        root.setAttribute('data-theme', theme)
      }
    }

    return {
      isAuthenticated,
      isFullscreen,
      sidebarOpen,
      isMobile
    }
  }
}
</script>

<style scoped>
.app-container {
  display: flex;
  min-height: 100vh;
  background-color: var(--background);
}

.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 150;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: var(--sidebar-width);
  min-width: 0;
  transition: margin-left 0.3s ease;
}

.main-content.full-width {
  margin-left: 0;
}

.content {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
  overflow-x: hidden;
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
