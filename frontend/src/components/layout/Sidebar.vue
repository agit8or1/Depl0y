<template>
  <aside class="sidebar" :class="{ 'sidebar-open': isOpen }">
    <div class="sidebar-header">
      <h1 class="logo">Depl<span class="logo-zero">0</span>y</h1>
      <p class="tagline">VM Deployment Panel</p>
    </div>

    <nav class="sidebar-nav">
      <!-- Core -->
      <router-link to="/" class="nav-item">
        <span class="icon">📊</span>
        <span>Dashboard</span>
      </router-link>

      <router-link to="/datacenter" class="nav-item">
        <span class="icon">🏢</span>
        <span>Datacenter</span>
      </router-link>

      <router-link to="/vms" class="nav-item">
        <span class="icon">🖥️</span>
        <span>Virtual Machines</span>
      </router-link>

      <!-- Deploy -->
      <router-link v-if="isOperator" to="/deploy" class="nav-item">
        <span class="icon">🚀</span>
        <span>Deploy VM</span>
      </router-link>

      <router-link v-if="isOperator" to="/import-vm" class="nav-item">
        <span class="icon">📥</span>
        <span>Import VM</span>
      </router-link>

      <router-link v-if="isOperator" to="/create-lxc" class="nav-item">
        <span class="icon">📦</span>
        <span>Create LXC</span>
      </router-link>

      <router-link v-if="isOperator" to="/llm-deploy" class="nav-item">
        <span class="icon">🤖</span>
        <span>LLM Deploy</span>
      </router-link>

      <router-link v-if="isOperator" to="/create-pve-vm" class="nav-item">
        <span class="icon">🖥️</span>
        <span>Create VM (PVE)</span>
      </router-link>

      <router-link v-if="isOperator" to="/vm-management" class="nav-item">
        <span class="icon">🛠️</span>
        <span>VM Management</span>
      </router-link>

      <!-- Infrastructure -->
      <router-link to="/proxmox" class="nav-item">
        <span class="icon">🌐</span>
        <span>Proxmox Hosts</span>
      </router-link>

      <router-link v-if="isOperator" to="/containers" class="nav-item">
        <span class="icon">📦</span>
        <span>Containers</span>
      </router-link>

      <router-link to="/templates" class="nav-item">
        <span class="icon">📋</span>
        <span>Templates</span>
      </router-link>

      <router-link to="/tasks" class="nav-item">
        <span class="icon">📋</span>
        <span>Task Log</span>
      </router-link>

      <router-link v-if="isAdmin" to="/ha-management" class="nav-item">
        <span class="icon">🔄</span>
        <span>HA Management</span>
      </router-link>

      <router-link v-if="isOperator" to="/idrac" class="nav-item">
        <span class="icon">🖧</span>
        <span>iDRAC / iLO</span>
      </router-link>

      <!-- Images -->
      <router-link to="/images" class="nav-item">
        <span class="icon">💿</span>
        <span>Images</span>
      </router-link>

      <!-- Admin -->
      <router-link v-if="isAdmin" to="/users" class="nav-item">
        <span class="icon">👥</span>
        <span>Users</span>
      </router-link>

      <router-link v-if="isAdmin" to="/security" class="nav-item">
        <span class="icon">🔒</span>
        <span>Security</span>
      </router-link>

      <router-link v-if="isAdmin && linuxAgentEnabled" to="/linux-vms" class="nav-item">
        <span class="icon">🛡️</span>
        <span>Linux VM Security</span>
      </router-link>

      <!-- System -->
      <router-link to="/profile" class="nav-item">
        <span class="icon">👤</span>
        <span>My Profile</span>
      </router-link>

      <router-link to="/documentation" class="nav-item">
        <span class="icon">📖</span>
        <span>Documentation</span>
      </router-link>

      <router-link to="/settings" class="nav-item">
        <span class="icon">⚙️</span>
        <span>Settings</span>
      </router-link>

      <router-link to="/support" class="nav-item nav-item-heart">
        <span class="icon">❤️</span>
        <span>Support Project</span>
      </router-link>

      <router-link to="/about" class="nav-item">
        <span class="icon">ℹ️</span>
        <span>About</span>
      </router-link>

      <a href="https://github.com/agit8or1/Depl0y/issues" target="_blank" rel="noopener noreferrer" class="nav-item">
        <span class="icon">🐛</span>
        <span>Report Bug</span>
      </a>
    </nav>

    <div class="sidebar-footer">
      <p class="version">v{{ appVersion }}</p>
      <p class="copyright">Open Source</p>
    </div>
  </aside>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/store/auth'
import api from '@/services/api'

export default {
  name: 'Sidebar',
  props: {
    isOpen: {
      type: Boolean,
      default: true
    }
  },
  emits: ['close'],
  setup() {
    const authStore = useAuthStore()
    const isAdmin = computed(() => authStore.isAdmin)
    const isOperator = computed(() => authStore.isOperator || authStore.isAdmin)
    const appVersion = ref('1.7.0') // Fallback version
    const linuxAgentEnabled = ref(false)

    // Fetch version from API
    const fetchVersion = async () => {
      try {
        const response = await api.system.getInfo()
        if (response.data && response.data.version) {
          appVersion.value = response.data.version
        }
      } catch (error) {
        console.warn('Failed to fetch version from API, using fallback:', error)
      }
    }

    const fetchLinuxAgentEnabled = async () => {
      if (!authStore.isAdmin) return
      try {
        const response = await api.vmAgent.getSettings()
        linuxAgentEnabled.value = response.data.enabled
      } catch {
        // ignore
      }
    }

    onMounted(() => {
      fetchVersion()
      fetchLinuxAgentEnabled()
    })

    return {
      isAdmin,
      isOperator,
      appVersion,
      linuxAgentEnabled
    }
  }
}
</script>

<style scoped>
.sidebar {
  width: 250px;
  background: linear-gradient(180deg, #1a2332 0%, #0f1419 100%);
  color: white;
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  display: flex;
  flex-direction: column;
  z-index: 100;
  box-shadow: 2px 0 10px rgba(0,0,0,0.3);
}

.sidebar-header {
  padding: 2rem 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo {
  font-size: 2rem;
  font-weight: 700;
  margin: 0;
  letter-spacing: -1px;
}

.logo-zero {
  color: #3b82f6;
}

.tagline {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.7);
  margin-top: 0.25rem;
}

.sidebar-nav {
  flex: 1;
  padding: 1rem 0;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 0.75rem 1.5rem;
  color: rgba(255, 255, 255, 0.8);
  text-decoration: none;
  transition: all 0.2s;
  gap: 0.75rem;
}

.nav-item:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: white;
}

.nav-item.router-link-active {
  background-color: rgba(59, 130, 246, 0.15);
  color: white;
  border-left: 3px solid #3b82f6;
}

.icon {
  font-size: 1.25rem;
}

.nav-item-heart {
  color: rgba(255, 200, 200, 0.85);
}

.nav-item-heart:hover {
  color: #fca5a5;
}

.sidebar-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.55);
}

.version,
.copyright {
  margin: 0.25rem 0;
}

@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    transition: transform 0.3s ease;
  }

  .sidebar.sidebar-open {
    transform: translateX(0);
  }
}
</style>
