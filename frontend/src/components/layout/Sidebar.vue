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

    <nav class="sidebar-nav" @keydown="onNavKeydown">

      <!-- ── Favorites ── -->
      <div
        v-if="favorites.length > 0"
        class="nav-section-header"
        @click="toggleSection('favorites')"
        :aria-expanded="!collapsed.favorites"
        role="button"
        tabindex="0"
        @keydown.enter.prevent="toggleSection('favorites')"
        @keydown.space.prevent="toggleSection('favorites')"
      >
        <span class="nav-section-label-text">{{ t('nav.section.favorites') }}</span>
        <span class="nav-section-arrow" :class="{ 'arrow-collapsed': collapsed.favorites }">›</span>
      </div>
        <div v-show="favorites.length > 0 && !collapsed.favorites" class="nav-section-items">
          <div
            v-for="fav in favorites"
            :key="fav.path"
            class="nav-item nav-item-fav"
            :class="{ 'router-link-active': isActive(fav.path) }"
            role="link"
            tabindex="0"
            @click="navigateTo(fav.path)"
            @keydown.enter.prevent="navigateTo(fav.path)"
          >
            <span class="icon">{{ fav.icon }}</span>
            <span class="nav-item-label">{{ fav.label }}</span>
            <button
              class="star-btn star-btn--active"
              :title="'Remove from favorites'"
              @click.stop="removeFavorite(fav.path)"
              tabindex="-1"
            >★</button>
          </div>
        </div>

      <!-- ── Overview ── -->
      <div
        class="nav-section-header"
        :class="{ 'nav-section-header--active': activeSectionKey === 'overview' }"
        @click="toggleSection('overview')"
        :aria-expanded="!collapsed.overview"
        role="button"
        tabindex="0"
        @keydown.enter.prevent="toggleSection('overview')"
        @keydown.space.prevent="toggleSection('overview')"
      >
        <span class="nav-section-label-text">{{ t('nav.section.overview') }}</span>
        <span class="nav-section-arrow" :class="{ 'arrow-collapsed': collapsed.overview }">›</span>
      </div>
        <div v-show="!collapsed.overview" class="nav-section-items">
          <NavItem :to="'/'" :icon="'📊'" :label="t('nav.dashboard')" :badge="unreadNotifications || null" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/federation'" :icon="'🌍'" :label="t('nav.federation')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/datacenter'" :icon="'🏢'" :label="t('nav.datacenter')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/cluster'" :icon="'🌐'" :label="t('nav.cluster')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/tasks'" :icon="'📋'" :label="t('nav.tasklog')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
        </div>

      <!-- ── Compute ── -->
      <div
        class="nav-section-header"
        :class="{ 'nav-section-header--active': activeSectionKey === 'compute' }"
        @click="toggleSection('compute')"
        :aria-expanded="!collapsed.compute"
        role="button"
        tabindex="0"
        @keydown.enter.prevent="toggleSection('compute')"
        @keydown.space.prevent="toggleSection('compute')"
      >
        <span class="nav-section-label-text">{{ t('nav.section.compute') }}</span>
        <span class="nav-section-arrow" :class="{ 'arrow-collapsed': collapsed.compute }">›</span>
      </div>
        <div v-show="!collapsed.compute" class="nav-section-items">
          <NavItem v-if="isOperator" :to="'/containers'" :icon="'📦'" :label="t('nav.containers')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/create-lxc'" :icon="'➕'" :label="t('nav.create_lxc')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/create-pve-vm'" :icon="'➕'" :label="t('nav.create_vm_pve')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/deploy'" :icon="'🚀'" :label="t('nav.deploy_vm')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/import-vm'" :icon="'📥'" :label="t('nav.import_vm')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/llm-deploy'" :icon="'🤖'" :label="t('nav.llm_deploy')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/templates'" :icon="'📄'" :label="t('nav.templates')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/vms'" :icon="'🖥️'" :label="t('nav.vms')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/vm-management'" :icon="'🛠️'" :label="t('nav.vm_management')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/vm-groups'" :icon="'🗃️'" :label="t('nav.vm_groups')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/bulk-ops'" :icon="'⚡'" :label="t('nav.bulk_ops')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/vm-search'" :icon="'🔎'" :label="t('nav.vm_search')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
        </div>

      <!-- ── Infrastructure ── -->
      <div
        class="nav-section-header"
        :class="{ 'nav-section-header--active': activeSectionKey === 'infrastructure' }"
        @click="toggleSection('infrastructure')"
        :aria-expanded="!collapsed.infrastructure"
        role="button"
        tabindex="0"
        @keydown.enter.prevent="toggleSection('infrastructure')"
        @keydown.space.prevent="toggleSection('infrastructure')"
      >
        <span class="nav-section-label-text">{{ t('nav.section.infrastructure') }}</span>
        <span class="nav-section-arrow" :class="{ 'arrow-collapsed': collapsed.infrastructure }">›</span>
      </div>
        <div v-show="!collapsed.infrastructure" class="nav-section-items">
          <NavItem :to="'/backup'" :icon="'💾'" :label="t('nav.backup')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/snapshots'" :icon="'📷'" :label="t('nav.snapshots')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isAdmin" :to="'/ha-management'" :icon="'🔄'" :label="t('nav.ha_management')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/replication'" :icon="'🔁'" :label="t('nav.replication')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/idrac'" :icon="'🖧'" :label="t('nav.idrac')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/network'" :icon="'🔌'" :label="t('nav.network')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isAdmin" :to="'/sdn'" :icon="'🕸️'" :label="t('nav.sdn')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/firewall-manager'" :icon="'🛡️'" :label="t('nav.firewall')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isAdmin" :to="'/ceph'" :icon="'🪨'" :label="t('nav.ceph')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isAdmin" :to="'/pve-users'" :icon="'👤'" :label="t('nav.pve_users')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isOperator" :to="'/node-monitor'" :icon="'📡'" :label="t('nav.node_monitor')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isAdmin" :to="'/pbs-management'" :icon="'🗄️'" :label="t('nav.pbs_management')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/images'" :icon="'💿'" :label="t('nav.images')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/proxmox'" :icon="'🌐'" :label="t('nav.proxmox_hosts')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isAdmin" :to="'/storage-management'" :icon="'🗄️'" :label="t('nav.storage_management')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem v-if="isAdmin" :to="'/pools'" :icon="'🗂️'" :label="t('nav.resource_pools')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
        </div>

      <!-- ── Admin ── -->
      <template v-if="isAdmin">
        <div
          class="nav-section-header"
          :class="{ 'nav-section-header--active': activeSectionKey === 'admin' }"
          @click="toggleSection('admin')"
          :aria-expanded="!collapsed.admin"
          role="button"
          tabindex="0"
          @keydown.enter.prevent="toggleSection('admin')"
          @keydown.space.prevent="toggleSection('admin')"
        >
          <span class="nav-section-label-text">{{ t('nav.section.admin') }}</span>
          <span class="nav-section-arrow" :class="{ 'arrow-collapsed': collapsed.admin }">›</span>
        </div>
            <div v-show="!collapsed.admin" class="nav-section-items">
            <NavItem :to="'/audit-log'" :icon="'🔍'" :label="t('nav.audit_log')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
            <NavItem v-if="linuxAgentEnabled" :to="'/linux-vms'" :icon="'🛡️'" :label="t('nav.linux_vm_security')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
            <NavItem :to="'/security'" :icon="'🔒'" :label="t('nav.security')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
            <NavItem :to="'/alerts'" :icon="'🚨'" :label="t('nav.alert_rules')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
            <NavItem :to="'/notifications'" :icon="'🔔'" :label="t('nav.notifications')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
            <NavItem :to="'/system-health'" :icon="'💚'" :label="t('nav.system_health')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
            <NavItem :to="'/system-logs'" :icon="'📜'" :label="t('nav.system_logs')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
            <NavItem :to="'/users'" :icon="'👥'" :label="t('nav.users')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
            <NavItem :to="'/integrations'" :icon="'🔗'" :label="t('nav.integrations')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
            <NavItem :to="'/api-explorer'" :icon="'⚡'" :label="t('nav.api_explorer')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          </div>
        </template>

      <!-- ── Account ── -->
      <div
        class="nav-section-header"
        :class="{ 'nav-section-header--active': activeSectionKey === 'account' }"
        @click="toggleSection('account')"
        :aria-expanded="!collapsed.account"
        role="button"
        tabindex="0"
        @keydown.enter.prevent="toggleSection('account')"
        @keydown.space.prevent="toggleSection('account')"
      >
        <span class="nav-section-label-text">{{ t('nav.section.account') }}</span>
        <span class="nav-section-arrow" :class="{ 'arrow-collapsed': collapsed.account }">›</span>
      </div>
        <div v-show="!collapsed.account" class="nav-section-items">
          <NavItem :to="'/about'" :icon="'ℹ️'" :label="t('nav.about')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/documentation'" :icon="'📖'" :label="t('nav.documentation')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/profile'" :icon="'👤'" :label="t('nav.my_profile')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/settings'" :icon="'⚙️'" :label="t('nav.settings')" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <NavItem :to="'/support'" :icon="'❤️'" :label="t('nav.support')" :extra-class="'nav-item-heart'" :favorites="favorites" @click="handleNavClick" @toggle-fav="toggleFavorite" />
          <a href="https://github.com/agit8or1/Depl0y/issues" target="_blank" rel="noopener noreferrer" class="nav-item">
            <span class="icon">🐛</span>
            <span class="nav-item-label">{{ t('nav.report_bug') }}</span>
          </a>
        </div>

    </nav>

    <div class="sidebar-footer">
      <p class="version">v{{ appVersion }}</p>
      <p class="copyright">Open Source</p>
    </div>
  </aside>
</template>

<script>
import { ref, reactive, computed, onMounted, defineComponent } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import { useI18n } from '@/i18n/index.js'

const COLLAPSED_KEY = 'sidebar_collapsed_sections'
const FAVORITES_KEY = 'sidebar_favorites'

// Maps route paths to which section they belong
const SECTION_ROUTES = {
  overview: ['/', '/federation', '/datacenter', '/cluster', '/tasks'],
  compute: ['/containers', '/create-lxc', '/create-pve-vm', '/deploy', '/import-vm', '/llm-deploy', '/templates', '/vms', '/vm-management', '/vm-groups', '/bulk-ops', '/vm-search'],
  infrastructure: ['/backup', '/snapshots', '/ha-management', '/replication', '/idrac', '/network', '/sdn', '/firewall-manager', '/ceph', '/pve-users', '/node-monitor', '/pbs-management', '/images', '/proxmox', '/storage-management', '/pools'],
  admin: ['/audit-log', '/linux-vms', '/security', '/alerts', '/notifications', '/system-health', '/system-logs', '/users', '/integrations', '/api-explorer'],
  account: ['/about', '/documentation', '/profile', '/settings', '/support'],
}

// NavItem sub-component
const NavItem = defineComponent({
  name: 'NavItem',
  props: {
    to: { type: String, required: true },
    icon: { type: String, required: true },
    label: { type: String, required: true },
    badge: { type: Number, default: null },
    favorites: { type: Array, default: () => [] },
    extraClass: { type: String, default: '' },
  },
  emits: ['click', 'toggle-fav'],
  setup(props, { emit }) {
    const route = useRoute()
    const router = useRouter()
    const isFav = computed(() => props.favorites.some(f => f.path === props.to))
    const isActive = computed(() => {
      if (props.to === '/') return route.path === '/'
      return route.path.startsWith(props.to)
    })

    const navigate = () => {
      router.push(props.to)
      emit('click')
    }

    const toggleFav = (e) => {
      e.preventDefault()
      e.stopPropagation()
      emit('toggle-fav', { path: props.to, icon: props.icon, label: props.label })
    }

    return { isFav, isActive, navigate, toggleFav }
  },
  template: `
    <div
      :class="['nav-item', extraClass, isActive ? 'router-link-active' : '']"
      role="link"
      tabindex="0"
      @click="navigate"
      @keydown.enter.prevent="navigate"
    >
      <span class="icon">{{ icon }}</span>
      <span class="nav-item-label">{{ label }}</span>
      <span v-if="badge && badge > 0" class="nav-badge">{{ badge > 99 ? '99+' : badge }}</span>
      <button
        :class="['star-btn', isFav ? 'star-btn--active' : '']"
        :title="isFav ? 'Remove from favorites' : 'Add to favorites'"
        @click="toggleFav"
        tabindex="-1"
      >{{ isFav ? '★' : '☆' }}</button>
    </div>
  `
})

export default {
  name: 'Sidebar',
  components: { NavItem },
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
    const route = useRoute()
    const router = useRouter()
    const isAdmin = computed(() => authStore.isAdmin)
    const isOperator = computed(() => authStore.isOperator || authStore.isAdmin)
    const appVersion = ref('1.8.0')
    const linuxAgentEnabled = ref(false)
    const unreadNotifications = ref(0)

    // ── Collapsed sections (persisted) ──────────────────────────────────────
    // Use plain reactive object instead of Set for reliable Vue 3 reactivity
    const collapsed = reactive({
      overview: false,
      compute: false,
      infrastructure: false,
      admin: false,
      account: false,
      favorites: false,
    })

    const loadCollapsed = () => {
      try {
        const stored = localStorage.getItem(COLLAPSED_KEY)
        if (stored) {
          const keys = JSON.parse(stored)
          // Only restore if it's an array (old Set format)
          if (Array.isArray(keys)) {
            keys.forEach(k => { if (k in collapsed) collapsed[k] = true })
          }
        }
      } catch (e) {}
    }

    const saveCollapsed = () => {
      try {
        const keys = Object.keys(collapsed).filter(k => collapsed[k])
        localStorage.setItem(COLLAPSED_KEY, JSON.stringify(keys))
      } catch (e) {}
    }

    const toggleSection = (key) => {
      if (key in collapsed) {
        collapsed[key] = !collapsed[key]
        saveCollapsed()
      }
    }

    // ── Active section highlight ──────────────────────────────────────────
    const activeSectionKey = computed(() => {
      const path = route.path
      for (const [key, paths] of Object.entries(SECTION_ROUTES)) {
        if (paths.some(p => p === '/' ? path === '/' : path.startsWith(p))) {
          return key
        }
      }
      return null
    })

    const isActive = (path) => {
      if (path === '/') return route.path === '/'
      return route.path.startsWith(path)
    }

    // ── Favorites (persisted) ────────────────────────────────────────────
    const favorites = ref([])

    const loadFavorites = () => {
      try {
        const stored = localStorage.getItem(FAVORITES_KEY)
        if (stored) favorites.value = JSON.parse(stored)
      } catch (e) {}
    }

    const saveFavorites = () => {
      try {
        localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites.value))
      } catch (e) {}
    }

    const toggleFavorite = ({ path, icon, label }) => {
      const idx = favorites.value.findIndex(f => f.path === path)
      if (idx === -1) {
        favorites.value.push({ path, icon, label })
      } else {
        favorites.value.splice(idx, 1)
      }
      saveFavorites()
    }

    const removeFavorite = (path) => {
      const idx = favorites.value.findIndex(f => f.path === path)
      if (idx !== -1) favorites.value.splice(idx, 1)
      saveFavorites()
    }

    // ── Navigation ────────────────────────────────────────────────────────
    const navigateTo = (path) => {
      router.push(path)
      handleNavClick()
    }

    const handleNavClick = () => {
      if (window.innerWidth <= 768) {
        emit('close')
      }
    }

    // ── Keyboard navigation within nav ───────────────────────────────────
    const onNavKeydown = (e) => {
      if (!['ArrowDown', 'ArrowUp'].includes(e.key)) return
      const items = Array.from(e.currentTarget.querySelectorAll('[tabindex="0"]'))
      const idx = items.indexOf(document.activeElement)
      if (idx === -1) return
      e.preventDefault()
      if (e.key === 'ArrowDown' && idx < items.length - 1) {
        items[idx + 1].focus()
      } else if (e.key === 'ArrowUp' && idx > 0) {
        items[idx - 1].focus()
      }
    }

    // ── API fetches ───────────────────────────────────────────────────────
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

    const fetchUnreadNotifications = async () => {
      try {
        const res = await api.dashboard.getAlerts()
        const alerts = res.data?.alerts || []
        unreadNotifications.value = alerts.filter(a => !a.acknowledged).length
      } catch {
        // non-blocking
      }
    }

    onMounted(() => {
      loadCollapsed()
      loadFavorites()
      fetchVersion()
      fetchLinuxAgentEnabled()
      fetchUnreadNotifications()
    })

    return {
      t,
      isAdmin,
      isOperator,
      appVersion,
      linuxAgentEnabled,
      unreadNotifications,
      handleNavClick,
      navigateTo,
      collapsed,
      toggleSection,
      activeSectionKey,
      isActive,
      favorites,
      toggleFavorite,
      removeFavorite,
      onNavKeydown,
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
  padding: 0.5rem 0;
  overflow-y: auto;
  overflow-x: hidden;
}

/* ── Section headers (collapsible) ── */
.nav-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.55rem 1.1rem 0.25rem 1.5rem;
  margin-top: 0.5rem;
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
  border-radius: 0.25rem 0.25rem 0 0;
  transition: background 0.15s;
}

.nav-section-header:hover {
  background: rgba(255, 255, 255, 0.04);
}

.nav-section-header:focus-visible {
  outline: 2px solid rgba(59, 130, 246, 0.6);
  outline-offset: -2px;
}

/* When the active route is inside this section, tint the label */
.nav-section-header--active .nav-section-label-text {
  color: #93c5fd;
}

.nav-section-label-text {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #7a8fa8;
  transition: color 0.2s;
}

.nav-section-arrow {
  font-size: 0.85rem;
  color: #7a8fa8;
  line-height: 1;
  transition: transform 0.2s, color 0.2s;
  transform: rotate(90deg);
}

.arrow-collapsed {
  transform: rotate(0deg);
}

.nav-section-items {
  overflow: hidden;
}

/* ── Section collapse transition ── */
.section-collapse-enter-active,
.section-collapse-leave-active {
  transition: max-height 0.22s ease, opacity 0.18s ease;
  max-height: 2000px;
  opacity: 1;
}

.section-collapse-enter-from,
.section-collapse-leave-to {
  max-height: 0;
  opacity: 0;
}

/* ── Nav items ── */
.nav-item {
  display: flex;
  align-items: center;
  padding: 0.65rem 0.75rem 0.65rem 1.5rem;
  color: #d1d9e6;
  text-decoration: none;
  transition: background 0.15s, color 0.15s;
  gap: 0.65rem;
  cursor: pointer;
  position: relative;
  outline: none;
}

.nav-item:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: #ffffff;
}

.nav-item:focus-visible {
  outline: 2px solid rgba(59, 130, 246, 0.6);
  outline-offset: -2px;
}

.nav-item.router-link-active {
  background-color: rgba(59, 130, 246, 0.22);
  color: #ffffff;
  border-left: 3px solid #60a5fa;
  font-weight: 500;
  padding-left: calc(1.5rem - 3px);
}

.nav-item-fav {
  background: rgba(59, 130, 246, 0.04);
}

.nav-item-label {
  flex: 1;
  font-size: 0.875rem;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.icon {
  font-size: 1.1rem;
  flex-shrink: 0;
  width: 1.35rem;
  text-align: center;
}

/* ── Notification badge ── */
.nav-badge {
  font-size: 0.6rem;
  font-weight: 700;
  background: #ef4444;
  color: #fff;
  border-radius: 9999px;
  padding: 0.1rem 0.35rem;
  min-width: 1.1rem;
  text-align: center;
  flex-shrink: 0;
  line-height: 1.4;
}

/* ── Star / favorite button ── */
.star-btn {
  background: none;
  border: none;
  color: #4a5568;
  font-size: 0.85rem;
  cursor: pointer;
  padding: 0.1rem 0.2rem;
  border-radius: 0.2rem;
  line-height: 1;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}

.nav-item:hover .star-btn,
.nav-item:focus-within .star-btn {
  opacity: 1;
}

.star-btn--active {
  color: #f59e0b;
  opacity: 1 !important;
}

.star-btn:hover {
  color: #f59e0b;
}

/* ── Heart item ── */
.nav-item-heart {
  color: #f9b8b8;
}

.nav-item-heart:hover {
  color: #fca5a5;
}

/* ── Footer ── */
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
