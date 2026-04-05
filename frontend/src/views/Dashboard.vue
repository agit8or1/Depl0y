<template>
  <div class="dashboard">

    <!-- ── First-run onboarding (admin, no hosts) ── -->
    <transition name="onboard-fade">
      <div v-if="showOnboarding" class="onboarding-screen">
        <div class="onboard-hero">
          <div class="onboard-logo">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="var(--primary-color)" stroke-width="1.5">
              <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
          </div>
          <h1 class="onboard-title">Welcome to Depl0y</h1>
          <p class="onboard-sub">Your Proxmox VM management platform. Follow the steps below to get started.</p>
        </div>

        <div class="onboard-checklist">
          <!-- Step 1: Account created -->
          <div class="checklist-item checklist-done">
            <div class="check-icon check-complete">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
            <div class="check-content">
              <span class="check-label">Account Created</span>
              <span class="check-desc">You're logged in and ready to go</span>
            </div>
          </div>

          <!-- Step 2: Add first host -->
          <div :class="['checklist-item', firstHostAdded ? 'checklist-done' : 'checklist-active']">
            <div :class="['check-icon', firstHostAdded ? 'check-complete' : 'check-pending']">
              <svg v-if="firstHostAdded" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span v-else class="check-num">2</span>
            </div>
            <div class="check-content">
              <span class="check-label">Add Your First Proxmox Host</span>
              <span v-if="firstHostAdded" class="check-desc check-done-text">Proxmox datacenter connected</span>
              <span v-else class="check-desc">Connect Depl0y to your Proxmox cluster or standalone node</span>
            </div>
            <button v-if="!firstHostAdded" class="btn btn-primary btn-sm" @click="openWizard">
              Add Host
            </button>
          </div>

          <!-- Step 3: Deploy first VM -->
          <div :class="['checklist-item', !firstHostAdded ? 'checklist-locked' : 'checklist-active']">
            <div :class="['check-icon', !firstHostAdded ? 'check-locked' : 'check-pending']">
              <svg v-if="!firstHostAdded" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              <span v-else class="check-num">3</span>
            </div>
            <div class="check-content">
              <span class="check-label">Deploy Your First VM</span>
              <span class="check-desc">Provision a new virtual machine on your Proxmox cluster</span>
            </div>
            <router-link v-if="firstHostAdded" to="/vms" class="btn btn-outline btn-sm">
              Deploy VM
            </router-link>
          </div>
        </div>

        <p class="onboard-skip">
          <a href="#" @click.prevent="skipOnboarding" class="skip-link">Skip — go to dashboard</a>
        </p>

        <!-- Wizard -->
        <AddHostWizard v-model="showWizard" @host-added="onFirstHostAdded" />
      </div>
    </transition>

    <!-- ── Normal dashboard (hosts exist or onboarding skipped) ── -->
    <template v-if="!showOnboarding">

    <!-- QuickStatsBar — always full-width at top -->
    <QuickStatsBar />

    <!-- Dashboard header bar -->
    <div class="dash-header">
      <h2 class="dash-title">Dashboard</h2>
      <div class="dash-actions">
        <span class="last-updated">{{ lastUpdatedSeconds }}s ago</span>
        <button class="btn-icon" title="Customize Widgets" @click="showCustomize = !showCustomize">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/>
          </svg>
        </button>
        <button class="btn-icon" title="Add Widget" @click="showPicker = true">+</button>
        <button class="btn-icon" title="Reset Layout" @click="resetLayout">↺</button>
      </div>
    </div>

    <!-- Customize panel -->
    <transition name="panel-slide">
      <div v-if="showCustomize" class="customize-panel">
        <div class="customize-header">
          <span class="customize-title">Widget Visibility</span>
          <span class="customize-hint">Toggled widgets are hidden but not removed from your layout</span>
        </div>
        <div class="customize-grid">
          <label
            v-for="type in allWidgetTypes"
            :key="type.type"
            class="toggle-item"
            :class="{ 'toggle-active': isWidgetVisible(type.type) }"
          >
            <input
              type="checkbox"
              class="toggle-check"
              :checked="isWidgetVisible(type.type)"
              @change="toggleWidgetVisibility(type.type)"
            />
            <span class="toggle-icon">{{ type.icon }}</span>
            <span class="toggle-label">{{ type.label }}</span>
          </label>
        </div>
      </div>
    </transition>

    <!-- Widget grid -->
    <div class="widget-grid" ref="gridEl">
      <div
        v-for="widget in visibleLayout"
        :key="widget.id"
        :class="['widget-card', dragging && dragging.id === widget.id ? 'widget-dragging' : '']"
        :data-widget-id="widget.id"
        :style="widgetStyle(widget)"
      >
        <!-- Widget title bar -->
        <div
          class="widget-bar"
          @mousedown="startDrag($event, widget)"
          @touchstart.prevent="startDragTouch($event, widget)"
        >
          <span class="widget-grip">⠿</span>
          <span class="widget-title">{{ widgetMeta(widget.type).label }}</span>
          <div class="widget-controls">
            <button class="wc-btn" :title="widget.collapsed ? 'Expand' : 'Collapse'" @click.stop="toggleCollapse(widget)">
              {{ widget.collapsed ? '▲' : '▼' }}
            </button>
            <button class="wc-btn" title="Settings" @click.stop="openSettings(widget)">⚙</button>
            <button class="wc-btn wc-remove" title="Remove" @click.stop="removeWidget(widget)">×</button>
          </div>
        </div>

        <!-- Widget body -->
        <div v-if="!widget.collapsed" class="widget-body">
          <component :is="widgetComponent(widget.type)" v-bind="widget.config || {}" />
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="layout.length === 0" class="dash-empty">
      <p>No widgets on your dashboard.</p>
      <button class="btn btn-primary" @click="showPicker = true">+ Add Widget</button>
    </div>

    <!-- Widget picker modal -->
    <transition name="modal-fade">
      <div v-if="showPicker" class="modal-overlay" @click.self="showPicker = false">
        <div class="modal-box picker-modal">
          <div class="modal-header">
            <h3>Add Widget</h3>
            <button class="modal-close" @click="showPicker = false">×</button>
          </div>
          <div class="picker-grid">
            <button
              v-for="meta in allWidgetTypes"
              :key="meta.type"
              class="picker-item"
              :disabled="isWidgetAdded(meta.type) && !meta.multi"
              @click="addWidget(meta.type)"
            >
              <span class="picker-icon">{{ meta.icon }}</span>
              <span class="picker-label">{{ meta.label }}</span>
              <span v-if="isWidgetAdded(meta.type) && !meta.multi" class="picker-added">Added</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Widget settings modal -->
    <transition name="modal-fade">
      <div v-if="settingsWidget" class="modal-overlay" @click.self="settingsWidget = null">
        <div class="modal-box settings-modal">
          <div class="modal-header">
            <h3>{{ widgetMeta(settingsWidget.type).label }} — Settings</h3>
            <button class="modal-close" @click="settingsWidget = null">×</button>
          </div>
          <div class="settings-body">
            <p class="settings-hint">Widget ID: {{ settingsWidget.id }}</p>
            <p class="settings-hint">Type: {{ settingsWidget.type }}</p>
            <div class="settings-row">
              <label class="form-label">Column span</label>
              <select v-model.number="settingsWidget.colSpan" class="form-control" @change="saveLayout">
                <option :value="1">1 column</option>
                <option :value="2">2 columns</option>
                <option :value="3">3 columns (full width)</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" @click="settingsWidget = null">Done</button>
          </div>
        </div>
      </div>
    </transition>

    </template><!-- end v-if="!showOnboarding" -->
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, markRaw, nextTick } from 'vue'
import { useAuthStore } from '@/store/auth'
import api from '@/services/api'
import AddHostWizard from '@/components/AddHostWizard.vue'

// Original widget imports
import ClusterStatsWidget    from '@/components/widgets/ClusterStatsWidget.vue'
import RecentTasksWidget     from '@/components/widgets/RecentTasksWidget.vue'
import AlertsWidget          from '@/components/widgets/AlertsWidget.vue'
import ResourceUsageWidget   from '@/components/widgets/ResourceUsageWidget.vue'
import QuickActionsWidget    from '@/components/widgets/QuickActionsWidget.vue'
import ActivityFeedWidget    from '@/components/widgets/ActivityFeedWidget.vue'
import TopVMsWidget          from '@/components/widgets/TopVMsWidget.vue'
import StorageOverviewWidget from '@/components/widgets/StorageOverviewWidget.vue'
import BackupStatusWidget    from '@/components/widgets/BackupStatusWidget.vue'
import SystemInfoWidget      from '@/components/widgets/SystemInfoWidget.vue'

// New widget imports
import NetworkTrafficWidget  from '@/components/widgets/NetworkTrafficWidget.vue'
import DiskIOWidget          from '@/components/widgets/DiskIOWidget.vue'
import NodeStatusGrid        from '@/components/widgets/NodeStatusGrid.vue'
import QuickStatsBar         from '@/components/widgets/QuickStatsBar.vue'

const STORAGE_KEY        = 'dashboard_layout'
const VISIBILITY_KEY     = 'dashboard_widget_visibility'

const WIDGET_META = {
  cluster_stats:    { type: 'cluster_stats',    label: 'Cluster Stats',     icon: '🖥️', multi: false },
  recent_tasks:     { type: 'recent_tasks',     label: 'Recent Tasks',      icon: '📋', multi: false },
  alerts:           { type: 'alerts',           label: 'Alerts',            icon: '⚠️', multi: false },
  resource_usage:   { type: 'resource_usage',   label: 'Resource Usage',    icon: '📊', multi: false },
  quick_actions:    { type: 'quick_actions',    label: 'Quick Actions',     icon: '⚡', multi: false },
  activity_feed:    { type: 'activity_feed',    label: 'Activity Feed',     icon: '📡', multi: false },
  top_vms:          { type: 'top_vms',          label: 'Top VMs',           icon: '🏆', multi: false },
  storage_overview: { type: 'storage_overview', label: 'Storage Overview',  icon: '💾', multi: false },
  backup_status:    { type: 'backup_status',    label: 'Backup Status',     icon: '🗄️', multi: false },
  system_info:      { type: 'system_info',      label: 'System Info',       icon: 'ℹ️', multi: false },
  network_traffic:  { type: 'network_traffic',  label: 'Network Traffic',   icon: '📶', multi: false },
  disk_io:          { type: 'disk_io',          label: 'Disk I/O',          icon: '💿', multi: false },
  node_status_grid: { type: 'node_status_grid', label: 'Node Status Grid',  icon: '🔲', multi: false },
}

const WIDGET_COMPONENTS = {
  cluster_stats:    markRaw(ClusterStatsWidget),
  recent_tasks:     markRaw(RecentTasksWidget),
  alerts:           markRaw(AlertsWidget),
  resource_usage:   markRaw(ResourceUsageWidget),
  quick_actions:    markRaw(QuickActionsWidget),
  activity_feed:    markRaw(ActivityFeedWidget),
  top_vms:          markRaw(TopVMsWidget),
  storage_overview: markRaw(StorageOverviewWidget),
  backup_status:    markRaw(BackupStatusWidget),
  system_info:      markRaw(SystemInfoWidget),
  network_traffic:  markRaw(NetworkTrafficWidget),
  disk_io:          markRaw(DiskIOWidget),
  node_status_grid: markRaw(NodeStatusGrid),
}

const DEFAULT_LAYOUT = [
  { id: 'w1', type: 'cluster_stats',    colSpan: 1, collapsed: false, config: {} },
  { id: 'w2', type: 'node_status_grid', colSpan: 2, collapsed: false, config: {} },
  { id: 'w3', type: 'network_traffic',  colSpan: 1, collapsed: false, config: {} },
  { id: 'w4', type: 'disk_io',          colSpan: 1, collapsed: false, config: {} },
  { id: 'w5', type: 'resource_usage',   colSpan: 1, collapsed: false, config: {} },
  { id: 'w6', type: 'top_vms',          colSpan: 1, collapsed: false, config: {} },
  { id: 'w7', type: 'alerts',           colSpan: 1, collapsed: false, config: {} },
  { id: 'w8', type: 'activity_feed',    colSpan: 1, collapsed: false, config: {} },
  { id: 'w9', type: 'recent_tasks',     colSpan: 1, collapsed: false, config: {} },
]

let _idCounter = 100

export default {
  name: 'Dashboard',
  components: {
    ClusterStatsWidget,
    RecentTasksWidget,
    AlertsWidget,
    ResourceUsageWidget,
    QuickActionsWidget,
    ActivityFeedWidget,
    TopVMsWidget,
    StorageOverviewWidget,
    BackupStatusWidget,
    SystemInfoWidget,
    NetworkTrafficWidget,
    DiskIOWidget,
    NodeStatusGrid,
    QuickStatsBar,
    AddHostWizard,
  },
  setup() {
    const authStore = useAuthStore()
    const layout   = ref([])
    const showPicker     = ref(false)
    const showCustomize  = ref(false)
    const settingsWidget = ref(null)
    const gridEl   = ref(null)
    const dragging = ref(null)
    const lastUpdatedSeconds = ref(0)
    let tickInterval = null

    // ── Widget visibility (localStorage) ──────────────────────────────────────
    // A Set of widget types that are explicitly hidden. Empty = all visible.
    const hiddenTypes = ref(new Set())

    const loadVisibility = () => {
      try {
        const stored = localStorage.getItem(VISIBILITY_KEY)
        if (stored) {
          hiddenTypes.value = new Set(JSON.parse(stored))
        }
      } catch (e) {}
    }

    const saveVisibility = () => {
      try {
        localStorage.setItem(VISIBILITY_KEY, JSON.stringify([...hiddenTypes.value]))
      } catch (e) {}
    }

    const isWidgetVisible = (type) => !hiddenTypes.value.has(type)

    const toggleWidgetVisibility = (type) => {
      if (hiddenTypes.value.has(type)) {
        hiddenTypes.value.delete(type)
      } else {
        hiddenTypes.value.add(type)
      }
      // Trigger reactivity — replace with new Set
      hiddenTypes.value = new Set(hiddenTypes.value)
      saveVisibility()
    }

    // Filtered layout: only show widgets whose type is not hidden
    const visibleLayout = computed(() =>
      layout.value.filter(w => isWidgetVisible(w.type))
    )

    // ── Onboarding ────────────────────────────────────────────────────────────
    const ONBOARD_SKIP_KEY = 'depl0y_onboarding_skip'
    const showOnboarding = ref(false)
    const showWizard = ref(false)
    const firstHostAdded = ref(false)

    const openWizard = () => { showWizard.value = true }

    const onFirstHostAdded = () => {
      firstHostAdded.value = true
    }

    const skipOnboarding = () => {
      localStorage.setItem(ONBOARD_SKIP_KEY, '1')
      showOnboarding.value = false
    }

    const checkOnboarding = async () => {
      if (!authStore.isAdmin) return
      if (localStorage.getItem(ONBOARD_SKIP_KEY)) return
      try {
        const res = await api.proxmox.listHosts()
        const hosts = res.data || []
        if (hosts.length === 0) {
          showOnboarding.value = true
        }
      } catch (e) {
        // Non-blocking — silently ignore
      }
    }

    // ── Persistence ──────────────────────────────────────────────────────────
    const saveLayout = () => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(layout.value.map(w => ({
          id: w.id, type: w.type, colSpan: w.colSpan, collapsed: w.collapsed, config: w.config || {}
        }))))
      } catch (e) {}
    }

    const loadLayout = () => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
          const parsed = JSON.parse(stored)
          layout.value = parsed.map(w => ({ ...w, config: w.config || {} }))
          return
        }
      } catch (e) {}
      layout.value = DEFAULT_LAYOUT.map(w => ({ ...w }))
    }

    const resetLayout = () => {
      layout.value = DEFAULT_LAYOUT.map(w => ({ ...w }))
      saveLayout()
    }

    // ── Widget helpers ────────────────────────────────────────────────────────
    const widgetMeta = (type) => WIDGET_META[type] || { label: type, icon: '□' }

    const widgetComponent = (type) => WIDGET_COMPONENTS[type] || null

    const allWidgetTypes = computed(() => Object.values(WIDGET_META))

    const isWidgetAdded = (type) => layout.value.some(w => w.type === type)

    const widgetStyle = (widget) => ({
      gridColumn: `span ${widget.colSpan || 1}`
    })

    // ── Add / remove ─────────────────────────────────────────────────────────
    const addWidget = (type) => {
      const id = 'w' + (++_idCounter)
      layout.value.push({ id, type, colSpan: 1, collapsed: false, config: {} })
      saveLayout()
      showPicker.value = false
    }

    const removeWidget = (widget) => {
      const idx = layout.value.findIndex(w => w.id === widget.id)
      if (idx !== -1) layout.value.splice(idx, 1)
      saveLayout()
    }

    const toggleCollapse = (widget) => {
      widget.collapsed = !widget.collapsed
      saveLayout()
    }

    const openSettings = (widget) => {
      settingsWidget.value = widget
    }

    // ── Drag-to-reorder (mouse) ───────────────────────────────────────────────
    let dragState = null

    const startDrag = (e, widget) => {
      if (e.button !== 0) return
      e.preventDefault()
      dragState = {
        widget,
        startX: e.clientX,
        startY: e.clientY,
        moved: false,
      }
      dragging.value = widget

      const onMove = (ev) => {
        if (!dragState) return
        const dx = Math.abs(ev.clientX - dragState.startX)
        const dy = Math.abs(ev.clientY - dragState.startY)
        if (dx > 5 || dy > 5) dragState.moved = true
        if (!dragState.moved) return

        const target = getWidgetAtPoint(ev.clientX, ev.clientY, widget.id)
        if (target && target !== widget) {
          swapWidgets(widget.id, target.id)
        }
      }

      const onUp = () => {
        dragState = null
        dragging.value = null
        saveLayout()
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
      }

      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
    }

    const startDragTouch = (e, widget) => {
      const touch = e.touches[0]
      dragState = {
        widget,
        startX: touch.clientX,
        startY: touch.clientY,
        moved: false,
      }
      dragging.value = widget

      const onMove = (ev) => {
        if (!dragState) return
        const t = ev.touches[0]
        dragState.moved = true
        const target = getWidgetAtPoint(t.clientX, t.clientY, widget.id)
        if (target && target !== widget) swapWidgets(widget.id, target.id)
      }

      const onEnd = () => {
        dragState = null
        dragging.value = null
        saveLayout()
        window.removeEventListener('touchmove', onMove)
        window.removeEventListener('touchend', onEnd)
      }

      window.addEventListener('touchmove', onMove, { passive: true })
      window.addEventListener('touchend', onEnd)
    }

    const getWidgetAtPoint = (x, y, excludeId) => {
      if (!gridEl.value) return null
      const cards = gridEl.value.querySelectorAll('.widget-card')
      for (const card of cards) {
        if (card.dataset.widgetId === excludeId) continue
        const rect = card.getBoundingClientRect()
        if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
          const id = card.dataset.widgetId
          return layout.value.find(w => w.id === id) || null
        }
      }
      return null
    }

    const swapWidgets = (idA, idB) => {
      const idxA = layout.value.findIndex(w => w.id === idA)
      const idxB = layout.value.findIndex(w => w.id === idB)
      if (idxA === -1 || idxB === -1) return
      const tmp = layout.value[idxA]
      layout.value[idxA] = layout.value[idxB]
      layout.value[idxB] = tmp
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────
    onMounted(() => {
      loadLayout()
      loadVisibility()
      tickInterval = setInterval(() => lastUpdatedSeconds.value++, 1000)
      checkOnboarding()
    })

    onUnmounted(() => {
      clearInterval(tickInterval)
    })

    return {
      layout,
      visibleLayout,
      showPicker,
      showCustomize,
      settingsWidget,
      gridEl,
      dragging,
      lastUpdatedSeconds,
      allWidgetTypes,
      widgetMeta,
      widgetComponent,
      widgetStyle,
      isWidgetAdded,
      isWidgetVisible,
      toggleWidgetVisibility,
      addWidget,
      removeWidget,
      toggleCollapse,
      openSettings,
      saveLayout,
      resetLayout,
      startDrag,
      startDragTouch,
      // Onboarding
      showOnboarding,
      showWizard,
      firstHostAdded,
      openWizard,
      onFirstHostAdded,
      skipOnboarding,
    }
  }
}
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* ── Header ───────────────────────────────────────────────────────────────── */
.dash-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.dash-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.dash-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.last-updated {
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.btn-icon {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  color: var(--text-primary);
  font-size: 1.1rem;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
  padding: 0;
  line-height: 1;
}

.btn-icon:hover {
  background: var(--primary-color);
  color: #fff;
  border-color: var(--primary-color);
}

/* ── Customize Panel ──────────────────────────────────────────────────────── */
.customize-panel {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.customize-header {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.customize-title {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-primary);
}

.customize-hint {
  font-size: 0.72rem;
  color: var(--text-secondary);
}

.customize-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.toggle-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: pointer;
  background: var(--background);
  transition: all 0.15s;
  user-select: none;
  -webkit-user-select: none;
}

.toggle-item:hover {
  border-color: var(--primary-color);
}

.toggle-active {
  border-color: var(--primary-color);
  background: rgba(59, 130, 246, 0.06);
}

.toggle-check {
  width: 0.9rem;
  height: 0.9rem;
  accent-color: var(--primary-color);
  cursor: pointer;
}

.toggle-icon {
  font-size: 0.85rem;
  line-height: 1;
}

.toggle-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}

/* Panel slide transition */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: all 0.22s ease;
  overflow: hidden;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
  max-height: 0;
}

.panel-slide-enter-to,
.panel-slide-leave-from {
  opacity: 1;
  transform: translateY(0);
  max-height: 300px;
}

/* ── Widget Grid ──────────────────────────────────────────────────────────── */
.widget-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  align-items: start;
}

.widget-card {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
  transition: box-shadow 0.2s, transform 0.2s;
}

.widget-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.widget-dragging {
  opacity: 0.7;
  transform: scale(0.98);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  z-index: 100;
}

/* ── Widget Title Bar ─────────────────────────────────────────────────────── */
.widget-bar {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.65rem;
  background: var(--background);
  border-bottom: 1px solid var(--border-color);
  cursor: grab;
  user-select: none;
  -webkit-user-select: none;
}

.widget-bar:active {
  cursor: grabbing;
}

.widget-grip {
  font-size: 0.9rem;
  color: var(--text-secondary);
  opacity: 0.5;
  letter-spacing: -1px;
  flex-shrink: 0;
}

.widget-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.widget-controls {
  display: flex;
  align-items: center;
  gap: 0.1rem;
  flex-shrink: 0;
}

.wc-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 0.85rem;
  width: 1.4rem;
  height: 1.4rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.25rem;
  cursor: pointer;
  transition: all 0.12s;
  padding: 0;
}

.wc-btn:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

.wc-remove:hover {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

/* ── Widget Body ─────────────────────────────────────────────────────────── */
.widget-body {
  padding: 0.75rem;
}

/* ── Empty State ─────────────────────────────────────────────────────────── */
.dash-empty {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.dash-empty p {
  margin-bottom: 0.75rem;
}

/* ── Modal ───────────────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.modal-box {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.22);
  width: 100%;
  max-height: 80vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.picker-modal  { max-width: 560px; }
.settings-modal { max-width: 420px; }

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.2rem;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.15rem 0.3rem;
  border-radius: 0.25rem;
  transition: all 0.12s;
}

.modal-close:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

/* ── Widget Picker ───────────────────────────────────────────────────────── */
.picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.5rem;
  padding: 1rem 1.25rem;
}

.picker-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 0.75rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background: var(--background);
  cursor: pointer;
  transition: all 0.15s;
  position: relative;
}

.picker-item:hover:not(:disabled) {
  border-color: var(--primary-color);
  background: rgba(var(--primary-color-rgb, 59, 130, 246), 0.05);
}

.picker-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.picker-icon  { font-size: 1.5rem; }
.picker-label { font-size: 0.78rem; font-weight: 500; color: var(--text-primary); text-align: center; }
.picker-added {
  font-size: 0.6rem; font-weight: 700; text-transform: uppercase;
  background: rgba(34, 197, 94, 0.15); color: #22c55e;
  padding: 0.1rem 0.35rem; border-radius: 9999px;
}

/* ── Widget Settings ────────────────────────────────────────────────────── */
.settings-body {
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.settings-hint {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin: 0;
  font-family: monospace;
}

.settings-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.modal-footer {
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
}

/* ── Modal transitions ───────────────────────────────────────────────────── */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 1024px) {
  .widget-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .widget-grid {
    grid-template-columns: 1fr;
  }

  .widget-card {
    grid-column: span 1 !important;
  }

  .picker-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .customize-grid {
    flex-direction: column;
  }
}

/* ── Onboarding screen ──────────────────────────────────────────────────── */
.onboarding-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 70vh;
  padding: 2rem 1rem;
  gap: 2rem;
}

.onboard-hero {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.onboard-logo {
  width: 80px;
  height: 80px;
  border-radius: 1.25rem;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.onboard-title {
  font-size: 2rem;
  font-weight: 800;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.02em;
}

.onboard-sub {
  font-size: 1rem;
  color: var(--text-secondary);
  margin: 0;
  max-width: 420px;
}

/* Checklist */
.onboard-checklist {
  display: flex;
  flex-direction: column;
  gap: 0;
  width: 100%;
  max-width: 540px;
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  overflow: hidden;
  background: var(--surface);
}

.checklist-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s;
  position: relative;
}

.checklist-item:last-child {
  border-bottom: none;
}

.checklist-done {
  background: var(--surface);
}

.checklist-active {
  background: rgba(59, 130, 246, 0.04);
}

.checklist-locked {
  background: var(--surface);
  opacity: 0.55;
}

/* Left pulse animation for active step */
.checklist-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--primary-color);
  border-radius: 0 2px 2px 0;
}

/* Icons */
.check-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 0.75rem;
  font-weight: 700;
}

.check-complete {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}

.check-complete svg {
  stroke: #22c55e;
}

.check-pending {
  background: rgba(59, 130, 246, 0.1);
  color: var(--primary-color);
  border: 2px solid var(--primary-color);
}

.check-num {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--primary-color);
}

.check-locked {
  background: var(--background);
  border: 2px solid var(--border-color);
  color: var(--text-secondary);
}

.check-locked svg {
  stroke: var(--text-secondary);
}

/* Content */
.check-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.check-label {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.check-desc {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.check-done-text {
  color: #22c55e;
}

/* Buttons */
.btn-sm {
  padding: 0.35rem 0.85rem;
  font-size: 0.8rem;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  padding: 0.5rem 1.1rem;
  transition: all 0.15s;
  text-decoration: none;
  white-space: nowrap;
}

.btn-primary {
  background: var(--primary-color);
  color: #fff;
  border-color: var(--primary-color);
}

.btn-primary:hover { opacity: 0.9; }

.btn-outline {
  background: transparent;
  color: var(--text-primary);
  border-color: var(--border-color);
}

.btn-outline:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

/* Skip link */
.onboard-skip {
  margin: 0;
}

.skip-link {
  font-size: 0.8rem;
  color: var(--text-secondary);
  text-decoration: none;
  transition: color 0.15s;
}

.skip-link:hover {
  color: var(--text-primary);
  text-decoration: underline;
}

/* Onboarding fade transition */
.onboard-fade-enter-active,
.onboard-fade-leave-active {
  transition: opacity 0.3s ease;
}
.onboard-fade-enter-from,
.onboard-fade-leave-to {
  opacity: 0;
}
</style>
