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
      <button class="cmd-palette-btn" @click="openCommandPalette" title="Open command palette (Ctrl K)">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <span class="cmd-palette-btn-label">Search</span>
        <kbd class="cmd-palette-kbd">⌘K</kbd>
      </button>
      <NotificationBell />
      <router-link to="/profile" class="user-info user-info-link">
        <span class="username">{{ username }}</span>
        <span class="user-role badge badge-info">{{ userRole }}</span>
      </router-link>

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
import NotificationBell from '@/components/layout/NotificationBell.vue'

export default {
  name: 'Header',
  components: {
    GlobalSearch,
    NotificationBell
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

    // Open the global command palette via keyboard event dispatch
    const openCommandPalette = () => {
      window.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'k',
        ctrlKey: true,
        bubbles: true,
        cancelable: true,
      }))
    }

    return {
      username,
      userRole,
      pageTitle,
      handleLogout,
      openCommandPalette,
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

.user-info-link {
  text-decoration: none;
  border-radius: 6px;
  padding: 0.25rem 0.5rem;
  transition: background 0.2s;
}

.user-info-link:hover {
  background: rgba(255, 255, 255, 0.08);
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

/* ── Command palette trigger button ── */
.cmd-palette-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  padding: 0.35rem 0.65rem;
  color: rgba(255, 255, 255, 0.65);
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}

.cmd-palette-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(59, 130, 246, 0.4);
  color: rgba(255, 255, 255, 0.9);
}

.cmd-palette-btn-label {
  font-weight: 500;
}

.cmd-palette-kbd {
  font-size: 0.65rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  padding: 1px 5px;
  color: rgba(255, 255, 255, 0.5);
  font-family: inherit;
  line-height: 1.5;
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

  .cmd-palette-btn-label,
  .cmd-palette-kbd {
    display: none;
  }
}
</style>
