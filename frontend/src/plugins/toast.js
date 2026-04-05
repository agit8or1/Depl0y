/**
 * Toast plugin — exposes $toast on Vue globalProperties and window.$toast.
 *
 * Usage:
 *   this.$toast.success('VM started')
 *   this.$toast.error('Something failed')
 *   this.$toast.warning('Disk near full')
 *   this.$toast.info('Fetching data...')
 *
 *   // From non-Vue JS:
 *   window.$toast.success('Done')
 */

import { addToast } from '@/components/ToastContainer.vue'

const toast = {
  success: (msg, duration) => addToast('success', msg, duration),
  error:   (msg, duration) => addToast('error',   msg, duration),
  warning: (msg, duration) => addToast('warning', msg, duration),
  info:    (msg, duration) => addToast('info',    msg, duration),
}

export const ToastPlugin = {
  install(app) {
    app.config.globalProperties.$toast = toast
    window.$toast = toast
  }
}

export default toast
