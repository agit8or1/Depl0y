<template>
  <teleport to="body">
    <div class="toast-container" role="region" aria-label="Notifications" aria-live="polite">
      <transition-group name="toast-slide" tag="div" class="toast-stack">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="['toast-item', `toast-${toast.type}`]"
          role="alert"
        >
          <span class="toast-icon">{{ iconFor(toast.type) }}</span>
          <span class="toast-message">{{ toast.message }}</span>
          <button class="toast-close" @click="dismiss(toast.id)" aria-label="Close">×</button>
          <div class="toast-progress">
            <div
              class="toast-progress-bar"
              :style="{ animationDuration: toast.duration + 'ms' }"
              @animationend="dismiss(toast.id)"
            ></div>
          </div>
        </div>
      </transition-group>
    </div>
  </teleport>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'

// Shared reactive state — accessible from the plugin
export const toastState = ref([])
let _nextId = 1

export function addToast(type, message, duration = 4000) {
  const id = _nextId++
  toastState.value.push({ id, type, message, duration })
  return id
}

export function dismissToast(id) {
  const idx = toastState.value.findIndex(t => t.id === id)
  if (idx !== -1) toastState.value.splice(idx, 1)
}

export default {
  name: 'ToastContainer',
  setup() {
    const toasts = toastState

    const iconFor = (type) => {
      switch (type) {
        case 'success': return '✓'
        case 'error':   return '✕'
        case 'warning': return '⚠'
        case 'info':    return 'ℹ'
        default:        return 'ℹ'
      }
    }

    const dismiss = (id) => dismissToast(id)

    return { toasts, iconFor, dismiss }
  }
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 1.25rem;
  right: 1.25rem;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: none;
  max-width: 360px;
  width: 100%;
}

.toast-stack {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.toast-item {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.65rem 0.85rem;
  border-radius: 0.5rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
  font-size: 0.875rem;
  position: relative;
  overflow: hidden;
  pointer-events: all;
  backdrop-filter: blur(2px);
  border-left: 3px solid transparent;
  background: var(--surface, #fff);
  color: var(--text-primary, #1a202c);
  min-width: 260px;
}

.toast-success {
  border-left-color: #22c55e;
  background: #f0fdf4;
  color: #166534;
}

.toast-error {
  border-left-color: #ef4444;
  background: #fef2f2;
  color: #991b1b;
}

.toast-warning {
  border-left-color: #f59e0b;
  background: #fffbeb;
  color: #92400e;
}

.toast-info {
  border-left-color: #3b82f6;
  background: #eff6ff;
  color: #1d4ed8;
}

/* Dark theme overrides */
[data-theme="dark"] .toast-success {
  background: rgba(34, 197, 94, 0.12);
  color: #86efac;
}
[data-theme="dark"] .toast-error {
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
}
[data-theme="dark"] .toast-warning {
  background: rgba(245, 158, 11, 0.12);
  color: #fcd34d;
}
[data-theme="dark"] .toast-info {
  background: rgba(59, 130, 246, 0.12);
  color: #93c5fd;
}

.toast-icon {
  font-size: 1rem;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 0.05rem;
}

.toast-message {
  flex: 1;
  line-height: 1.4;
  word-break: break-word;
}

.toast-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  opacity: 0.6;
  padding: 0 0.15rem;
  flex-shrink: 0;
  color: inherit;
  transition: opacity 0.15s;
}

.toast-close:hover {
  opacity: 1;
}

.toast-progress {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.toast-progress-bar {
  height: 100%;
  background: currentColor;
  opacity: 0.4;
  animation: toast-shrink linear forwards;
  width: 100%;
}

@keyframes toast-shrink {
  from { width: 100%; }
  to   { width: 0%; }
}

/* Transition animations */
.toast-slide-enter-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-slide-leave-active {
  transition: all 0.2s ease-in;
}
.toast-slide-enter-from {
  opacity: 0;
  transform: translateX(110%);
}
.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(110%);
}
.toast-slide-move {
  transition: transform 0.25s ease;
}

@media (max-width: 480px) {
  .toast-container {
    top: auto;
    bottom: 1rem;
    right: 0.75rem;
    left: 0.75rem;
    max-width: 100%;
  }
}
</style>
