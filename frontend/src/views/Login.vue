<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1 class="login-logo">Depl<span class="logo-zero">0</span>y</h1>
        <p class="login-subtitle">{{ t('login.title') }}</p>
      </div>

      <!-- Step 1: Username + Password -->
      <form v-if="step === 'credentials'" @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label for="username" class="form-label">{{ t('login.username') }}</label>
          <input
            id="username"
            v-model="credentials.username"
            type="text"
            class="form-control"
            autocomplete="username"
            required
            autofocus
          />
        </div>

        <div class="form-group">
          <label for="password" class="form-label">{{ t('login.password') }}</label>
          <input
            id="password"
            v-model="credentials.password"
            type="password"
            autocomplete="current-password"
            class="form-control"
            required
          />
        </div>

        <div v-if="errorMsg" class="login-error">{{ errorMsg }}</div>

        <button
          type="submit"
          class="btn btn-primary btn-block"
          :disabled="loading"
        >
          {{ loading ? t('login.logging_in') : t('login.login') }}
        </button>
      </form>

      <!-- Step 2: 2FA Challenge -->
      <div v-else-if="step === '2fa'" class="login-form">
        <div class="twofa-header">
          <div class="twofa-icon">&#128274;</div>
          <h2 class="twofa-title">{{ t('login.2fa_title') }}</h2>
          <p class="twofa-subtitle">{{ t('login.2fa_subtitle') }}</p>
        </div>

        <form @submit.prevent="handleTwoFA">
          <div v-if="!useBackupCode" class="form-group">
            <label for="totp" class="form-label">{{ t('login.2fa_code_label') }}</label>
            <input
              id="totp"
              ref="totpInput"
              v-model="totpCode"
              type="text"
              class="form-control totp-input"
              placeholder="000000"
              maxlength="6"
              inputmode="numeric"
              autocomplete="one-time-code"
              required
            />
          </div>

          <div v-else class="form-group">
            <label for="backup" class="form-label">{{ t('login.2fa_backup_label') }}</label>
            <input
              id="backup"
              ref="backupInput"
              v-model="totpCode"
              type="text"
              class="form-control totp-input"
              placeholder="XXXXXXXX"
              maxlength="8"
              autocomplete="off"
              required
            />
          </div>

          <div v-if="errorMsg" class="login-error">{{ errorMsg }}</div>

          <button
            type="submit"
            class="btn btn-primary btn-block"
            :disabled="loading || totpCode.length < 6"
          >
            {{ loading ? t('login.verifying') : t('login.verify') }}
          </button>
        </form>

        <div class="twofa-footer">
          <button
            class="btn-link"
            type="button"
            @click="toggleBackupCode"
          >
            {{ useBackupCode ? t('login.use_authenticator') : t('login.use_backup_code') }}
          </button>
          <button
            class="btn-link btn-link-secondary"
            type="button"
            @click="backToCredentials"
          >
            {{ t('login.back_to_login') }}
          </button>
        </div>
      </div>

      <div class="login-footer">
        <p class="text-muted text-sm text-center">
          {{ t('login.footer') }}
        </p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { useI18n } from '@/i18n/index.js'

export default {
  name: 'Login',
  setup() {
    const router = useRouter()
    const authStore = useAuthStore()
    const { t } = useI18n()

    const step = ref('credentials')
    const credentials = ref({ username: '', password: '' })
    const totpCode = ref('')
    const tempToken = ref('')
    const useBackupCode = ref(false)
    const loading = ref(false)
    const errorMsg = ref('')

    const totpInput = ref(null)
    const backupInput = ref(null)

    const handleLogin = async () => {
      errorMsg.value = ''
      loading.value = true
      try {
        const result = await authStore.login(credentials.value)
        if (result.success) {
          router.push('/')
        } else if (result.requires_2fa) {
          tempToken.value = result.temp_token
          step.value = '2fa'
          await nextTick()
          totpInput.value?.focus()
        } else {
          errorMsg.value = result.error || t('login.failed')
        }
      } finally {
        loading.value = false
      }
    }

    const handleTwoFA = async () => {
      errorMsg.value = ''
      loading.value = true
      const code = useBackupCode.value ? totpCode.value.toUpperCase() : totpCode.value
      try {
        const result = await authStore.login2fa(tempToken.value, code)
        if (result.success) {
          router.push('/')
        } else {
          errorMsg.value = result.error || t('login.verification_failed')
          totpCode.value = ''
          await nextTick()
          if (useBackupCode.value) {
            backupInput.value?.focus()
          } else {
            totpInput.value?.focus()
          }
        }
      } finally {
        loading.value = false
      }
    }

    const toggleBackupCode = async () => {
      useBackupCode.value = !useBackupCode.value
      totpCode.value = ''
      errorMsg.value = ''
      await nextTick()
      if (useBackupCode.value) {
        backupInput.value?.focus()
      } else {
        totpInput.value?.focus()
      }
    }

    const backToCredentials = () => {
      step.value = 'credentials'
      totpCode.value = ''
      tempToken.value = ''
      useBackupCode.value = false
      errorMsg.value = ''
    }

    return {
      t,
      step,
      credentials,
      totpCode,
      useBackupCode,
      loading,
      errorMsg,
      totpInput,
      backupInput,
      handleLogin,
      handleTwoFA,
      toggleBackupCode,
      backToCredentials,
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
  background: #0c1220;
  padding: 2rem;
}

.login-card {
  background: #111827;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 1rem;
  box-shadow: 0 25px 50px rgba(0,0,0,0.6);
  width: 100%;
  max-width: 400px;
  padding: 2.5rem;
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.login-logo {
  font-size: 3rem;
  font-weight: 800;
  margin: 0;
  color: #e2e8f0;
  letter-spacing: -0.02em;
}

.logo-zero {
  color: #3b82f6;
}

.login-subtitle {
  color: #7a8fa8;
  margin-top: 0.5rem;
  font-size: 0.95rem;
}

.login-form {
  margin-bottom: 1.5rem;
}

/* Override any global form-label / form-control if they're light */
.login-card :deep(.form-label),
.form-label {
  color: #94a3b8;
  font-size: 0.85rem;
  font-weight: 500;
  display: block;
  margin-bottom: 0.35rem;
}

.login-card :deep(.form-control),
.form-control {
  background: #1e2d42;
  border: 1px solid rgba(255,255,255,0.12);
  color: #e2e8f0;
  border-radius: 0.4rem;
  padding: 0.55rem 0.8rem;
  font-size: 0.95rem;
  width: 100%;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.login-card :deep(.form-control):focus,
.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.2);
}

.btn-block {
  width: 100%;
  margin-top: 1rem;
  padding: 0.65rem;
  font-size: 1rem;
  font-weight: 600;
  border-radius: 0.5rem;
  background: #2563eb;
  color: #fff;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-block:hover:not(:disabled) { background: #1d4ed8; }
.btn-block:disabled { opacity: 0.55; cursor: not-allowed; }

.login-footer {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255,255,255,0.07);
}

.login-footer p { color: #4b5563; }

.login-error {
  background: rgba(239,68,68,0.1);
  color: #f87171;
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: 0.4rem;
  padding: 0.6rem 0.9rem;
  font-size: 0.875rem;
  margin-top: 0.75rem;
}

/* 2FA step */
.twofa-header {
  text-align: center;
  margin-bottom: 1.5rem;
}

.twofa-icon {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.twofa-title {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0 0 0.4rem;
  color: #e2e8f0;
}

.twofa-subtitle {
  font-size: 0.875rem;
  color: #7a8fa8;
  margin: 0;
}

.totp-input {
  letter-spacing: 0.2em;
  font-size: 1.25rem;
  text-align: center;
  font-family: 'Courier New', monospace;
}

.twofa-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  margin-top: 1.25rem;
}

.btn-link {
  background: none;
  border: none;
  color: #60a5fa;
  cursor: pointer;
  font-size: 0.875rem;
  text-decoration: underline;
  padding: 0;
}

.btn-link:hover {
  color: #93c5fd;
}

.btn-link-secondary {
  color: #4b5563;
}

.btn-link-secondary:hover {
  color: #7a8fa8;
}

.text-muted { color: #4b5563; }
.text-sm { font-size: 0.875rem; }
.text-center { text-align: center; }
</style>
