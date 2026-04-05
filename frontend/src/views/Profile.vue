<template>
  <div class="profile-page">
    <div class="page-header">
      <h1>My Profile</h1>
      <p class="text-muted">Manage your account information and security settings</p>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading profile...</p>
    </div>

    <div v-else>
      <!-- Account Info Card (read-only) -->
      <div class="card mb-4">
        <div class="card-header">
          <h3>Account Information</h3>
        </div>
        <div class="card-body">
          <div class="profile-header mb-4">
            <div class="profile-avatar">{{ user ? user.username.charAt(0).toUpperCase() : '?' }}</div>
            <div>
              <h4>{{ user ? user.username : '' }}</h4>
              <p class="text-sm text-muted">{{ user ? user.email : '' }}</p>
              <span v-if="user" :class="['badge', 'badge-' + getRoleBadge(user.role)]">{{ user.role }}</span>
            </div>
          </div>

          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Username</span>
              <span class="info-value">{{ user ? user.username : '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Email</span>
              <span class="info-value">{{ user ? user.email : '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Role</span>
              <span v-if="user" :class="['badge', 'badge-' + getRoleBadge(user.role)]">{{ user.role }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Member Since</span>
              <span class="info-value">{{ user ? formatDate(user.created_at) : '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Two-Factor Auth</span>
              <span v-if="user && user.totp_enabled" class="badge badge-success">Enabled</span>
              <span v-else class="badge badge-warning">Disabled</span>
            </div>
            <div class="info-item">
              <span class="info-label">Status</span>
              <span v-if="user && user.is_active" class="badge badge-success">Active</span>
              <span v-else class="badge badge-danger">Inactive</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Change Password Card -->
      <div class="card mb-4">
        <div class="card-header">
          <h3>Change Password</h3>
        </div>
        <div class="card-body">
          <form @submit.prevent="changePassword" class="password-form">
            <div class="form-group">
              <label class="form-label">Current Password</label>
              <input
                v-model="passwordForm.current_password"
                type="password"
                autocomplete="current-password"
                class="form-control"
                required
              />
            </div>

            <div class="form-group">
              <label class="form-label">New Password</label>
              <input
                v-model="passwordForm.new_password"
                type="password"
                autocomplete="new-password"
                class="form-control"
                required
              />
              <p
                v-if="passwordForm.new_password && passwordForm.new_password.length < 8"
                class="field-hint field-error"
              >
                Password must be at least 8 characters
              </p>
            </div>

            <div class="form-group">
              <label class="form-label">Confirm New Password</label>
              <input
                v-model="passwordForm.confirm_password"
                type="password"
                autocomplete="new-password"
                class="form-control"
                required
              />
              <p
                v-if="passwordForm.confirm_password && passwordForm.new_password !== passwordForm.confirm_password"
                class="field-hint field-error"
              >
                Passwords do not match
              </p>
            </div>

            <div
              v-if="passwordMsg"
              :class="['alert', passwordMsgType === 'success' ? 'alert-success' : 'alert-danger']"
            >
              {{ passwordMsg }}
            </div>

            <button
              type="submit"
              class="btn btn-primary"
              :disabled="changingPassword || !passwordFormValid"
            >
              {{ changingPassword ? 'Changing...' : 'Change Password' }}
            </button>
          </form>
        </div>
      </div>

      <!-- Preferences Card -->
      <div class="card">
        <div class="card-header">
          <h3>Preferences</h3>
        </div>
        <div class="card-body">
          <p class="text-muted">
            Proxmox connection preferences and system options are managed in the Settings page.
          </p>
          <router-link to="/settings" class="btn btn-outline mt-3">
            Go to Settings
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'Profile',
  async setup() {
    const authStore = useAuthStore()
    const toast = useToast()

    const loading = ref(true)
    const user = ref(null)
    const changingPassword = ref(false)
    const passwordMsg = ref('')
    const passwordMsgType = ref('success')

    const passwordForm = ref({
      current_password: '',
      new_password: '',
      confirm_password: ''
    })

    const passwordFormValid = computed(() => {
      const f = passwordForm.value
      return (
        f.current_password.length > 0 &&
        f.new_password.length >= 8 &&
        f.new_password === f.confirm_password
      )
    })

    const getRoleBadge = (role) => {
      const map = { admin: 'danger', operator: 'warning', viewer: 'info' }
      return map[role] || 'secondary'
    }

    const formatDate = (dateStr) => {
      if (!dateStr) return '—'
      return new Date(dateStr).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
    }

    const loadProfile = async () => {
      loading.value = true
      try {
        const resp = await api.auth.getMe()
        user.value = resp.data
        authStore.user = resp.data
      } catch (e) {
        console.error('Failed to load profile', e)
      } finally {
        loading.value = false
      }
    }

    const changePassword = async () => {
      passwordMsg.value = ''
      if (!passwordFormValid.value) return
      changingPassword.value = true
      try {
        await api.auth.changePassword({
          current_password: passwordForm.value.current_password,
          new_password: passwordForm.value.new_password
        })
        toast.success('Password changed successfully')
        passwordMsg.value = 'Password changed successfully'
        passwordMsgType.value = 'success'
        passwordForm.value = { current_password: '', new_password: '', confirm_password: '' }
      } catch (e) {
        const msg = e.response?.data?.detail || 'Failed to change password'
        passwordMsg.value = msg
        passwordMsgType.value = 'error'
      } finally {
        changingPassword.value = false
      }
    }

    await loadProfile()

    return {
      loading,
      user,
      passwordForm,
      passwordFormValid,
      changingPassword,
      passwordMsg,
      passwordMsgType,
      getRoleBadge,
      formatDate,
      changePassword
    }
  }
}
</script>

<style scoped>
.profile-page {
  max-width: 680px;
  margin: 0 auto;
  padding: 1.5rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h1 {
  margin: 0 0 0.25rem;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.profile-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--primary, #3b82f6);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: 700;
  flex-shrink: 0;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem 1.5rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.info-label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  opacity: 0.55;
}

.info-value {
  font-size: 0.95rem;
}

.password-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 420px;
}

.field-hint {
  font-size: 0.8rem;
  margin: 0.3rem 0 0;
}

.field-error {
  color: #ef4444;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem;
  color: var(--text-muted, #6b7280);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-bottom: 0.75rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.mb-4 { margin-bottom: 1.25rem; }
.mt-3 { display: inline-block; margin-top: 0.75rem; }
.card-body { padding: 1.25rem; }
.text-muted { opacity: 0.65; }
.text-sm { font-size: 0.875rem; }
</style>
