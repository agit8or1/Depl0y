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
      <div class="nav-section-label">{{ t('nav.section.overview') }}</div>
      <router-link to="/" class="nav-item" @click="handleNavClick">
        <span class="icon">📊</span>
        <span>{{ t('nav.dashboard') }}</span>
      </router-link>
      <router-link to="/federation" class="nav-item" @click="handleNavClick">
        <span class="icon">🌍</span>
        <span>{{ t('nav.federation') }}</span>
      </router-link>
      <router-link to="/datacenter" class="nav-item" @click="handleNavClick">
        <span class="icon">🏢</span>
        <span>{{ t('nav.datacenter') }}</span>
      </router-link>
      <router-link to="/tasks" class="nav-item" @click="handleNavClick">
        <span class="icon">📋</span>
        <span>{{ t('nav.tasklog') }}</span>
      </router-link>

      <!-- ── Compute ── -->
      <div class="nav-section-label">{{ t('nav.section.compute') }}</div>
      <router-link v-if="isOperator" to="/containers" class="nav-item" @click="handleNavClick">
        <span class="icon">📦</span>
        <span>{{ t('nav.containers') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/create-lxc" class="nav-item" @click="handleNavClick">
        <span class="icon">➕</span>
        <span>{{ t('nav.create_lxc') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/create-pve-vm" class="nav-item" @click="handleNavClick">
        <span class="icon">➕</span>
        <span>{{ t('nav.create_vm_pve') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/deploy" class="nav-item" @click="handleNavClick">
        <span class="icon">🚀</span>
        <span>{{ t('nav.deploy_vm') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/import-vm" class="nav-item" @click="handleNavClick">
        <span class="icon">📥</span>
        <span>{{ t('nav.import_vm') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/llm-deploy" class="nav-item" @click="handleNavClick">
        <span class="icon">🤖</span>
        <span>{{ t('nav.llm_deploy') }}</span>
      </router-link>
      <router-link to="/templates" class="nav-item" @click="handleNavClick">
        <span class="icon">📄</span>
        <span>{{ t('nav.templates') }}</span>
      </router-link>
      <router-link to="/vms" class="nav-item" @click="handleNavClick">
        <span class="icon">🖥️</span>
        <span>{{ t('nav.vms') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/vm-management" class="nav-item" @click="handleNavClick">
        <span class="icon">🛠️</span>
        <span>{{ t('nav.vm_management') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/vm-groups" class="nav-item" @click="handleNavClick">
        <span class="icon">🗃️</span>
        <span>{{ t('nav.vm_groups') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/bulk-ops" class="nav-item" @click="handleNavClick">
        <span class="icon">⚡</span>
        <span>{{ t('nav.bulk_ops') }}</span>
      </router-link>

      <!-- ── Infrastructure ── -->
      <div class="nav-section-label">{{ t('nav.section.infrastructure') }}</div>
      <router-link to="/backup" class="nav-item" @click="handleNavClick">
        <span class="icon">💾</span>
        <span>{{ t('nav.backup') }}</span>
      </router-link>
      <router-link to="/snapshots" class="nav-item" @click="handleNavClick">
        <span class="icon">📷</span>
        <span>{{ t('nav.snapshots') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/ha-management" class="nav-item" @click="handleNavClick">
        <span class="icon">🔄</span>
        <span>{{ t('nav.ha_management') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/replication" class="nav-item" @click="handleNavClick">
        <span class="icon">🔁</span>
        <span>{{ t('nav.replication') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/idrac" class="nav-item" @click="handleNavClick">
        <span class="icon">🖧</span>
        <span>{{ t('nav.idrac') }}</span>
      </router-link>
      <router-link v-if="isOperator" to="/network" class="nav-item" @click="handleNavClick">
        <span class="icon">🔌</span>
        <span>{{ t('nav.network') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/sdn" class="nav-item" @click="handleNavClick">
        <span class="icon">🕸️</span>
        <span>{{ t('nav.sdn') }}</span>
      </router-link>
      <router-link to="/images" class="nav-item" @click="handleNavClick">
        <span class="icon">💿</span>
        <span>{{ t('nav.images') }}</span>
      </router-link>
      <router-link to="/proxmox" class="nav-item" @click="handleNavClick">
        <span class="icon">🌐</span>
        <span>{{ t('nav.proxmox_hosts') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/storage-management" class="nav-item" @click="handleNavClick">
        <span class="icon">🗄️</span>
        <span>{{ t('nav.storage_management') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/pools" class="nav-item" @click="handleNavClick">
        <span class="icon">🗂️</span>
        <span>{{ t('nav.resource_pools') }}</span>
      </router-link>

      <!-- ── Admin ── -->
      <div v-if="isAdmin" class="nav-section-label">{{ t('nav.section.admin') }}</div>
      <router-link v-if="isAdmin" to="/audit-log" class="nav-item" @click="handleNavClick">
        <span class="icon">🔍</span>
        <span>{{ t('nav.audit_log') }}</span>
      </router-link>
      <router-link v-if="isAdmin && linuxAgentEnabled" to="/linux-vms" class="nav-item" @click="handleNavClick">
        <span class="icon">🛡️</span>
        <span>{{ t('nav.linux_vm_security') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/security" class="nav-item" @click="handleNavClick">
        <span class="icon">🔒</span>
        <span>{{ t('nav.security') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/alerts" class="nav-item" @click="handleNavClick">
        <span class="icon">🚨</span>
        <span>{{ t('nav.alert_rules') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/system-health" class="nav-item" @click="handleNavClick">
        <span class="icon">💚</span>
        <span>{{ t('nav.system_health') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/system-logs" class="nav-item" @click="handleNavClick">
        <span class="icon">📜</span>
        <span>{{ t('nav.system_logs') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/users" class="nav-item" @click="handleNavClick">
        <span class="icon">👥</span>
        <span>{{ t('nav.users') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/integrations" class="nav-item" @click="handleNavClick">
        <span class="icon">🔗</span>
        <span>{{ t('nav.integrations') }}</span>
      </router-link>
      <router-link v-if="isAdmin" to="/api-explorer" class="nav-item" @click="handleNavClick">
        <span class="icon">⚡</span>
        <span>{{ t('nav.api_explorer') }}</span>
      </router-link>

      <!-- ── Account ── -->
      <div class="nav-section-label">{{ t('nav.section.account') }}</div>
      <router-link to="/about" class="nav-item" @click="handleNavClick">
        <span class="icon">ℹ️</span>
        <span>{{ t('nav.about') }}</span>
      </router-link>
      <router-link to="/documentation" class="nav-item" @click="handleNavClick">
        <span class="icon">📖</span>
        <span>{{ t('nav.documentation') }}</span>
      </router-link>
      <router-link to="/profile" class="nav-item" @click="handleNavClick">
        <span class="icon">👤</span>
        <span>{{ t('nav.my_profile') }}</span>
      </router-link>
      <router-link to="/settings" class="nav-item" @click="handleNavClick">
        <span class="icon">⚙️</span>
        <span>{{ t('nav.settings') }}</span>
      </router-link>
      <router-link to="/support" class="nav-item nav-item-heart" @click="handleNavClick">
        <span class="icon">❤️</span>
        <span>{{ t('nav.support') }}</span>
      </router-link>

      <a href="https://github.com/agit8or1/Depl0y/issues" target="_blank" rel="noopener noreferrer" class="nav-item">
        <span class="icon">🐛</span>
        <span>{{ t('nav.report_bug') }}</span>
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
import { useI18n } from '@/i18n/index.js'

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
    const { t } = useI18n()
    const isAdmin = computed(() => authStore.isAdmin)
    const isOperator = computed(() => authStore.isOperator || authStore.isAdmin)
    const appVersion = ref('1.8.0') // Fallback version
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
      t,
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
  color: #c0cfe4;
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
  color: rgba(255, 255, 255, 0.85);
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
  color: #d1d9e6;
  text-decoration: none;
  transition: all 0.2s;
  gap: 0.75rem;
}

.nav-item:hover {
  background-color: rgba(255, 255, 255, 0.12);
  color: #ffffff;
}

.nav-item.router-link-active {
  background-color: rgba(59, 130, 246, 0.22);
  color: #ffffff;
  border-left: 3px solid #60a5fa;
  font-weight: 500;
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
  color: #7a8fa8;
  margin-top: 0.5rem;
}

.nav-item-heart {
  color: #f9b8b8;
}

.nav-item-heart:hover {
  color: #fca5a5;
}

.sidebar-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 0.75rem;
  color: #8a9ab8;
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
