<template>
  <header class="header">
    <div class="header-left">
      <h2 class="page-title">{{ pageTitle }}</h2>
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

export default {
  name: 'Header',
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
  background-color: white;
  border-bottom: 1px solid var(--border-color);
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 50;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.username {
  font-weight: 500;
  color: var(--text-primary);
}

@media (max-width: 768px) {
  .header {
    padding: 1rem;
  }

  .page-title {
    font-size: 1.25rem;
  }

  .user-info {
    display: none;
  }
}
</style>
