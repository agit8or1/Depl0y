import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Toast from 'vue-toastification'
import 'vue-toastification/dist/index.css'

import App from './App.vue'
import router from './router'
import './assets/style.css'
import { ToastPlugin } from './plugins/toast.js'
import { loadMessages } from './i18n/index.js'
import en from './i18n/en.js'
import de from './i18n/de.js'
import fr from './i18n/fr.js'

// ── i18n: load all message catalogues ──────────────────────────────────────
loadMessages('en', en)
loadMessages('de', de)
loadMessages('fr', fr)

// ── Theme initialisation (before mounting to prevent flash) ─────────────────
const applyTheme = (theme) => {
  const root = document.documentElement
  if (theme === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    root.setAttribute('data-theme', prefersDark ? 'dark' : 'light')
  } else {
    root.setAttribute('data-theme', theme || 'light')
  }
}
applyTheme(localStorage.getItem('depl0y_theme') || 'light')

// ── PWA: register service worker ────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((registration) => {
        console.log('[SW] Registered, scope:', registration.scope)
      })
      .catch((err) => {
        console.warn('[SW] Registration failed:', err)
      })

    // When SW sends SW_UPDATED, reload to pick up new asset hashes
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data?.type === 'SW_UPDATED') {
        window.location.reload()
      }
    })
  })
}

// ── Chunk load error recovery ────────────────────────────────────────────────
// After a deploy, old cached index.js references stale chunk hashes → 404.
// Catch these and force a hard reload so the browser fetches fresh assets.
router.onError((err) => {
  const isChunkError = err?.message && (
    err.message.includes('Unable to preload') ||
    err.message.includes('Failed to fetch') ||
    err.message.includes('Importing a module script failed') ||
    err.message.includes('Loading chunk') ||
    err.message.includes('Loading CSS chunk')
  )
  if (isChunkError) {
    console.warn('[App] Stale chunk detected — reloading for fresh assets')
    window.location.reload()
  }
})

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ToastPlugin)
app.use(Toast, {
  position: 'top-right',
  timeout: 3000,
  closeOnClick: true,
  pauseOnFocusLoss: true,
  pauseOnHover: true,
  draggable: true,
  draggablePercent: 0.6,
  showCloseButtonOnHover: false,
  hideProgressBar: false,
  closeButton: 'button',
  icon: true,
  rtl: false
})

app.mount('#app')
