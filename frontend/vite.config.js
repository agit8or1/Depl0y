import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        // Vite 8 bundles with Rolldown, which only accepts the function form
        // of manualChunks — the object form throws "manualChunks is not a
        // function" at build time. Same three chunks as before.
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (/[\\/]node_modules[\\/](vue|vue-router|pinia)[\\/]/.test(id)) return 'vendor-vue'
          if (/[\\/]node_modules[\\/]axios[\\/]/.test(id)) return 'vendor-axios'
          if (/[\\/]node_modules[\\/]vue-toastification[\\/]/.test(id)) return 'vendor-toast'
        }
      }
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
