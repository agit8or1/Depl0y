<template>
  <aside class="sidebar" :class="{ 'sidebar-open': isOpen }">
    <div class="sidebar-header">
      <div class="sidebar-header-row">
        <div>
          <h1 class="logo">Depl<span class="logo-zero">0</span>y</h1>
          <p class="tagline">VM Deployment Panel</p>
        </div>
        <!-- Close button visible only on mobile -->
        <button class="sidebar-close-btn" @click="$emit('close')" aria-label="Close sidebar">
          &#x2715;
        </button>
      </div>
    </div>

    <nav class="sidebar-nav">

      <!-- ── Overview ── -->
      <div class="nav-section-label">Overview</div>
      <router-link to="/" class="nav-item" @click="handleNavClick">
        <span class="icon">📊</span>
        <span>Dashboard</span>
      </router-link>
      <router-link to="/datacenter" class="nav-item" @click="handleNavClick">
        <span class="icon">🏢</span>
        <span>Datacenter</span>
      </router-link>
      <router-link to="/tasks" class="nav-item" @click="handleNavClick">
        <span class="icon">📋</span>
        <span>Task Log</span>
      </router-link>

      <!-- ── Compute ── -->
      <div class="nav-section-label">Compute</div>
      <router-link v-if="isOperator" to="/containers" class="nav-item" @click="handleNavClick">
        <span class="icon">📦</span>
        <span>Containers</span>
      </router-link>
      <router-link v-if="isOperator" to="/create-lxc" class="nav-item" @click="handleNavClick">
        <span class="icon">➕</span>
        <span>Create LXC</span>
      </router-link>
      <router-link v-if="isOperator" to="/create-pve-vm" class="nav-item" @click="handleNavClick">
        <span class="icon">➕</span>
        <span>Create VM (PVE)</span>
      </router-link>
      <router-link v-if="isOperator" to="/deploy" class="nav-item" @click="handleNavClick">
        <span class="icon">🚀</span>
        <span>Deploy VM</span>
      </router-link>
      <router-link v-if="isOperator" to="/import-vm" class="nav-item" @click="handleNavClick">
        <span class="icon">📥</span>
        <span>Import VM</span>
      </router-link>
      <router-link v-if="isOperator" to="/llm-deploy" class="nav-item" @click="handleNavClick">
        <span class="icon">🤖</span>
        <span>LLM Deploy</span>
      </router-link>
      <router-link to="/templates" class="nav-item" @click="handleNavClick">
        <span class="icon">📄</span>
        <span>Templates</span>
      </router-link>
      <router-link to="/vms" class="nav-item" @click="handleNavClick">
        <span class="icon">🖥️</span>
        <span>Virtual Machines</span>
      </router-link>
      <router-link v-if="isOperator" to="/vm-management" class="nav-item" @click="handleNavClick">
        <span class="icon">🛠️</span>
        <span>VM Management</span>
      </router-link>

      <!-- ── Infrastructure ── -->
      <div class="nav-section-label">Infrastructure</div>
      <router-link to="/backup" class="nav-item" @click="handleNavClick">
        <span class="icon">💾</span>
        <span>Backup</span>
      </router-link>
      <router-link v-if="isAdmin" to="/ha-management" class="nav-item" @click="handleNavClick">
        <span class="icon">🔄</span>
        <span>HA Management</span>
      </router-link>
      <router-link v-if="isOperator" to="/replication" class="nav-item" @click="handleNavClick">
        <span class="icon">🔁</span>
        <span>Replication</span>
      </router-link>
      <router-link v-if="isOperator" to="/idrac" class="nav-item" @click="handleNavClick">
        <span class="icon">🖧</span>
        <span>iDRAC / iLO</span>
      </router-link>
      <router-link v-if="isOperator" to="/network" class="nav-item" @click="handleNavClick">
        <span class="icon">🔌</span>
        <span>Network Management</span>
      </router-link>
      <router-link to="/images" class="nav-item" @click="handleNavClick">
        <span class="icon">💿</span>
        <span>Images</span>
      </router-link>
      <router-link to="/proxmox" class="nav-item" @click="handleNavClick">
        <span class="icon">🌐</span>
        <span>Proxmox Hosts</span>
      </router-link>
      <router-link v-if="isAdmin" to="/pools" class="nav-item" @click="handleNavClick">
        <span class="icon">🗂️</span>
        <span>Resource Pools</span>
      </router-link>

      <!-- ── Admin ── -->
      <div v-if="isAdmin" class="nav-section-label">Admin</div>
      <router-link v-if="isAdmin" to="/audit-log" class="nav-item" @click="handleNavClick">
        <span class="icon">🔍</span>
        <span>Audit Log</span>
      </router-link>
      <router-link v-if="isAdmin && linuxAgentEnabled" to="/linux-vms" class="nav-item" @click="handleNavClick">
        <span class="icon">🛡️</span>
        <span>Linux VM Security</span>
      </router-link>
      <router-link v-if="isAdmin" to="/security" class="nav-item" @click="handleNavClick">
        <span class="icon">🔒</span>
        <span>Security</span>
      </router-link>
      <router-link v-if="isAdmin" to="/system-health" class="nav-item" @click="handleNavClick">
        <span class="icon">💚</span>
        <span>System Health</span>
      </router-link>
      <router-link v-if="isAdmin" to="/system-logs" class="nav-item" @click="handleNavClick">
        <span class="icon">📜</span>
        <span>System Logs</span>
      </router-link>
      <router-link v-if="isAdmin" to="/users" class="nav-item" @click="handleNavClick">
        <span class="icon">👥</span>
        <span>Users</span>
      </router-link>
      <router-link v-if="isAdmin" to="/api-explorer" class="nav-item" @click="handleNavClick">
        <span class="icon">⚡</span>
        <span>API Explorer</span>
      </router-link>

      <!-- ── Account ── -->
      <div class="nav-section-label">Account</div>
      <router-link to="/about" class="nav-item" @click="handleNavClick">
        <span class="icon">ℹ️</span>
        <span>About</span>
      </router-link>
      <router-link to="/documentation" class="nav-item" @click="handleNavClick">
        <span class="icon">📖</span>
        <span>Documentation</span>
      </router-link>
      <router-link to="/profile" class="nav-item" @click="handleNavClick">
        <span class="icon">👤</span>
        <span>My Profile</span>
      </router-link>
      <router-link to="/settings" class="nav-item" @click="handleNavClick">
        <span class="icon">⚙️</span>
        <span>Settings</span>
      </router-link>
      <router-link to="/support" class="nav-item nav-item-heart" @click="handleNavClick">
        <span class="icon">❤️</span>
        <span>Support Project</span>
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
  setup(props, { emit }) {
    const authStore = useAuthStore()
    const isAdmin = computed(() => authStore.isAdmin)
    const isOperator = computed(() => authStore.isOperator || authStore.isAdmin)
    const appVersion = ref('1.7.0') // Fallback version
    const linuxAgentEnabled = ref(false)

    // Close sidebar on mobile when navigating
    const handleNavClick = () => {
      if (window.innerWidth <= 768) {
        emit('close')
      }
    }

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
      linuxAgentEnabled,
      handleNavClick
    }
  }
}
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  background: linear-gradient(180deg, #1a2332 0%, #0f1419 100%);
  color: white;
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  display: flex;
  flex-direction: column;
  z-index: 200;
  box-shadow: 2px 0 10px rgba(0,0,0,0.3);
  transition: transform 0.3s ease;
}

.sidebar-header {
  padding: 1.5rem 1.5rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.sidebar-header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.sidebar-close-btn {
  display: none;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
  border-radius: 0.25rem;
  transition: color 0.15s, background 0.15s;
  flex-shrink: 0;
  margin-top: 0.25rem;
}

.sidebar-close-btn:hover {
  color: white;
  background: rgba(255, 255, 255, 0.1);
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
  overflow-x: hidden;
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
  flex-shrink: 0;
}

.nav-section-label {
  padding: 0.6rem 1.5rem 0.25rem;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.38);
  margin-top: 0.5rem;
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
  flex-shrink: 0;
}

.version,
.copyright {
  margin: 0.25rem 0;
}

@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    z-index: 200;
  }

  .sidebar.sidebar-open {
    transform: translateX(0);
  }

  .sidebar-close-btn {
    display: block;
  }
}
</style>
