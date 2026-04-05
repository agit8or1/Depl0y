<template>
  <div class="dashboard">
    <!-- Dashboard header bar -->
    <div class="dash-header">
      <h2 class="dash-title">Dashboard</h2>
      <div class="dash-actions">
        <span class="last-updated">{{ lastUpdatedSeconds }}s ago</span>
        <button class="btn-icon" title="Add Widget" @click="showPicker = true">+</button>
        <button class="btn-icon" title="Reset Layout" @click="resetLayout">↺</button>
      </div>
    </div>

    <!-- Widget grid -->
    <div class="widget-grid" ref="gridEl">
      <div
        v-for="widget in layout"
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
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, markRaw, nextTick } from 'vue'

// Widget component imports
import ClusterStatsWidget   from '@/components/widgets/ClusterStatsWidget.vue'
import RecentTasksWidget    from '@/components/widgets/RecentTasksWidget.vue'
import AlertsWidget         from '@/components/widgets/AlertsWidget.vue'
import ResourceUsageWidget  from '@/components/widgets/ResourceUsageWidget.vue'
import QuickActionsWidget   from '@/components/widgets/QuickActionsWidget.vue'
import ActivityFeedWidget   from '@/components/widgets/ActivityFeedWidget.vue'
import TopVMsWidget         from '@/components/widgets/TopVMsWidget.vue'
import StorageOverviewWidget from '@/components/widgets/StorageOverviewWidget.vue'
import BackupStatusWidget   from '@/components/widgets/BackupStatusWidget.vue'
import SystemInfoWidget     from '@/components/widgets/SystemInfoWidget.vue'

const STORAGE_KEY = 'dashboard_layout'

const WIDGET_META = {
  cluster_stats:    { type: 'cluster_stats',    label: 'Cluster Stats',    icon: '🖥️', multi: false },
  recent_tasks:     { type: 'recent_tasks',     label: 'Recent Tasks',     icon: '📋', multi: false },
  alerts:           { type: 'alerts',           label: 'Alerts',           icon: '⚠️', multi: false },
  resource_usage:   { type: 'resource_usage',   label: 'Resource Usage',   icon: '📊', multi: false },
  quick_actions:    { type: 'quick_actions',    label: 'Quick Actions',    icon: '⚡', multi: false },
  activity_feed:    { type: 'activity_feed',    label: 'Activity Feed',    icon: '📡', multi: false },
  top_vms:          { type: 'top_vms',          label: 'Top VMs',          icon: '🏆', multi: false },
  storage_overview: { type: 'storage_overview', label: 'Storage Overview', icon: '💾', multi: false },
  backup_status:    { type: 'backup_status',    label: 'Backup Status',    icon: '🗄️', multi: false },
  system_info:      { type: 'system_info',      label: 'System Info',      icon: 'ℹ️', multi: false },
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
}

const DEFAULT_LAYOUT = [
  { id: 'w1', type: 'cluster_stats',  colSpan: 1, collapsed: false, config: {} },
  { id: 'w2', type: 'recent_tasks',   colSpan: 1, collapsed: false, config: {} },
  { id: 'w3', type: 'alerts',         colSpan: 1, collapsed: false, config: {} },
  { id: 'w4', type: 'resource_usage', colSpan: 1, collapsed: false, config: {} },
  { id: 'w5', type: 'quick_actions',  colSpan: 1, collapsed: false, config: {} },
  { id: 'w6', type: 'activity_feed',  colSpan: 1, collapsed: false, config: {} },
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
  },
  setup() {
    const layout   = ref([])
    const showPicker = ref(false)
    const settingsWidget = ref(null)
    const gridEl   = ref(null)
    const dragging = ref(null)
    const lastUpdatedSeconds = ref(0)
    let tickInterval = null

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
      tickInterval = setInterval(() => lastUpdatedSeconds.value++, 1000)
    })

    onUnmounted(() => {
      clearInterval(tickInterval)
    })

    return {
      layout,
      showPicker,
      settingsWidget,
      gridEl,
      dragging,
      lastUpdatedSeconds,
      allWidgetTypes,
      widgetMeta,
      widgetComponent,
      widgetStyle,
      isWidgetAdded,
      addWidget,
      removeWidget,
      toggleCollapse,
      openSettings,
      saveLayout,
      resetLayout,
      startDrag,
      startDragTouch,
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
}
</style>
