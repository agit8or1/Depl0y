<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1 class="login-logo">Depl<span class="logo-zero">0</span>y</h1>
        <p class="login-subtitle">VM Deployment Panel</p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label for="username" class="form-label">Username</label>
          <input
            id="username"
            v-model="credentials.username"
            type="text"
            class="form-control"
            required
            autofocus
          />
        </div>

        <div class="form-group">
          <label for="password" class="form-label">Password</label>
          <input
            id="password"
            v-model="credentials.password"
            type="password"
            class="form-control"
            required
          />
        </div>

        <div v-if="show2FA" class="form-group">
          <label for="totp" class="form-label">2FA Code</label>
          <input
            id="totp"
            v-model="credentials.totp_code"
            type="text"
            class="form-control"
            placeholder="000000"
            maxlength="6"
          />
        </div>

        <button
          type="submit"
          class="btn btn-primary btn-block"
          :disabled="loading"
        >
          {{ loading ? 'Logging in...' : 'Login' }}
        </button>
      </form>

      <div class="login-footer">
        <p class="text-muted text-sm text-center">
          Open Source VM Deployment Platform
        </p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'

export default {
  name: 'Login',
  setup() {
    const router = useRouter()
    const authStore = useAuthStore()

    const credentials = ref({
      username: '',
      password: '',
      totp_code: ''
    })

    const loading = ref(false)
    const show2FA = ref(false)

    const handleLogin = async () => {
      loading.value = true

      try {
        const result = await authStore.login(credentials.value)

        if (result.success) {
          router.push('/')
        } else {
          // Only show 2FA field if specifically required
          if (result.error === '2FA code required') {
            show2FA.value = true
          }
        }
      } catch (error) {
        console.error('Login error:', error)
      } finally {
        loading.value = false
      }
    }

    return {
      credentials,
      loading,
      show2FA,
      handleLogin
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #1d4ed8 100%);
  padding: 2rem;
}

.login-card {
  background: white;
  border-radius: 1rem;
  box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1);
  width: 100%;
  max-width: 400px;
  padding: 2rem;
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.login-logo {
  font-size: 3rem;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
}

.logo-zero {
  color: #3b82f6;
}

.login-subtitle {
  color: var(--text-secondary);
  margin-top: 0.5rem;
}

.login-form {
  margin-bottom: 1.5rem;
}

.btn-block {
  width: 100%;
  margin-top: 1rem;
}

.login-footer {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}
</style>
