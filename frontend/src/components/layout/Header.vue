<template>
  <header class="header">
    <div class="header-left">
      <button class="hamburger" @click="$emit('toggle-sidebar')" aria-label="Toggle navigation">
        <span></span>
        <span></span>
        <span></span>
      </button>
      <h2 class="page-title">{{ pageTitle }}</h2>
    </div>

    <div class="header-center">
      <GlobalSearch />
    </div>

    <div class="header-right">
      <div class="user-info">
        <span class="username">{{ username }}</span>
        <span class="user-role badge badge-info">{{ userRole }}</span>
      </div>

      <button @click="handleLogout" class="btn btn-outline">
        Logout
      </button>
    </div>
  </header>
</template>

<script>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import GlobalSearch from '@/components/layout/GlobalSearch.vue'

export default {
  name: 'Header',
  components: {
    GlobalSearch
  },
  emits: ['toggle-sidebar'],
  setup() {
    const router = useRouter()
    const route = useRoute()
    const authStore = useAuthStore()

    const username = computed(() => authStore.username)
    const userRole = computed(() => authStore.userRole)

    const pageTitle = computed(() => {
      const titles = {
        Dashboard: 'Dashboard',
        VirtualMachines: 'Virtual Machines',
        CreateVM: 'Create Virtual Machine',
        VMDetails: 'VM Details',
        ProxmoxHosts: 'Proxmox Hosts',
        ISOImages: 'ISO Images',
        Users: 'User Management',
        Settings: 'Settings'
      }
      return titles[route.name] || 'Depl0y'
    })

    const handleLogout = () => {
      authStore.logout()
      router.push('/login')
    }

    return {
      username,
      userRole,
      pageTitle,
      handleLogout
    }
  }
}
</script>

<style scoped>
.header {
  background: linear-gradient(90deg, #1a2332 0%, #162030 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0.75rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 50;
  gap: 1.5rem;
}

.header-left {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.hamburger {
  display: none;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 5px;
  width: 36px;
  height: 36px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px;
  flex-shrink: 0;
}

.hamburger span {
  display: block;
  width: 22px;
  height: 2px;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 2px;
  transition: background 0.2s;
}

.hamburger:hover span {
  background: #fff;
}

.page-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-center {
  flex: 0 0 auto;
  display: flex;
  justify-content: center;
}

.header-right {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 1.25rem;
  min-width: 0;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.username {
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
  white-space: nowrap;
}

/* Override the global btn-outline for the dark header */
.btn.btn-outline {
  border-color: rgba(255, 255, 255, 0.25);
  color: rgba(255, 255, 255, 0.8);
  background: transparent;
  white-space: nowrap;
}

.btn.btn-outline:hover {
  border-color: rgba(255, 255, 255, 0.5);
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

@media (max-width: 900px) {
  .header-center {
    display: none;
  }
}

@media (max-width: 768px) {
  .header {
    padding: 0.75rem 1rem;
  }

  .hamburger {
    display: flex;
  }

  .page-title {
    font-size: 1rem;
  }

  .user-info {
    display: none;
  }
}
</style>
