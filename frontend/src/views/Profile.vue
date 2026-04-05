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
      <!-- Account Info -->
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

          <form @submit.prevent="updateProfile" class="profile-form">
            <div class="form-group">
              <label class="form-label">Username</label>
              <input v-model="profileForm.username" class="form-control" disabled />
              <p class="text-xs text-muted">Username cannot be changed</p>
            </div>

            <div class="form-group">
              <label class="form-label">Email Address</label>
              <input v-model="profileForm.email" type="email" class="form-control" required />
            </div>

            <div v-if="profileMsg" :class="['alert', profileMsgType === 'success' ? 'alert-success' : 'alert-danger']">
              {{ profileMsg }}
            </div>

            <button type="submit" class="btn btn-primary" :disabled="updatingProfile">
              {{ updatingProfile ? 'Updating...' : 'Update Profile' }}
            </button>
          </form>
        </div>
      </div>

      <!-- Change Password -->
      <div class="card">
        <div class="card-header">
          <h3>Change Password</h3>
        </div>
        <div class="card-body">
          <form @submit.prevent="changePassword" class="password-form">
            <div class="form-group">
              <label class="form-label">Current Password</label>
              <input v-model="passwordForm.current_password" type="password" autocomplete="current-password" class="form-control" required />
            </div>

            <div class="form-group">
              <label class="form-label">New Password</label>
              <input v-model="passwordForm.new_password" type="password" autocomplete="new-password" class="form-control" required />
            </div>

            <div class="form-group">
              <label class="form-label">Confirm New Password</label>
              <input v-model="passwordForm.confirm_password" type="password" autocomplete="new-password" class="form-control" required />
            </div>

            <div v-if="passwordMsg" :class="['alert', passwordMsgType === 'success' ? 'alert-success' : 'alert-danger']">
              {{ passwordMsg }}
            </div>

            <button type="submit" class="btn btn-primary" :disabled="changingPassword">
              {{ changingPassword ? 'Changing...' : 'Change Password' }}
            </button>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/services/api'

export default {
  name: 'Profile',
  data() {
    return {
      loading: true,
      user: null,
      profileForm: { username: '', email: '' },
      passwordForm: { current_password: '', new_password: '', confirm_password: '' },
      updatingProfile: false,
      changingPassword: false,
      profileMsg: '',
      profileMsgType: 'success',
      passwordMsg: '',
      passwordMsgType: 'success',
    }
  },
  async mounted() {
    await this.loadProfile()
  },
  methods: {
    async loadProfile() {
      this.loading = true
      try {
        const resp = await api.auth.getMe()
        this.user = resp.data
        this.profileForm.username = this.user.username
        this.profileForm.email = this.user.email || ''
      } catch (e) {
        console.error('Failed to load profile', e)
      } finally {
        this.loading = false
      }
    },
    getRoleBadge(role) {
      const map = { admin: 'danger', operator: 'warning', viewer: 'info' }
      return map[role] || 'secondary'
    },
    async updateProfile() {
      this.profileMsg = ''
      this.updatingProfile = true
      try {
        await api.auth.updateMe({ email: this.profileForm.email })
        this.profileMsg = 'Profile updated successfully'
        this.profileMsgType = 'success'
        await this.loadProfile()
      } catch (e) {
        this.profileMsg = e.response?.data?.detail || 'Failed to update profile'
        this.profileMsgType = 'error'
      } finally {
        this.updatingProfile = false
      }
    },
    async changePassword() {
      this.passwordMsg = ''
      if (this.passwordForm.new_password !== this.passwordForm.confirm_password) {
        this.passwordMsg = 'New passwords do not match'
        this.passwordMsgType = 'error'
        return
      }
      this.changingPassword = true
      try {
        await api.auth.changePassword({
          current_password: this.passwordForm.current_password,
          new_password: this.passwordForm.new_password,
        })
        this.passwordMsg = 'Password changed successfully'
        this.passwordMsgType = 'success'
        this.passwordForm = { current_password: '', new_password: '', confirm_password: '' }
      } catch (e) {
        this.passwordMsg = e.response?.data?.detail || 'Failed to change password'
        this.passwordMsgType = 'error'
      } finally {
        this.changingPassword = false
      }
    },
  },
}
</script>

<style scoped>
.profile-page {
  max-width: 640px;
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

.profile-form,
.password-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 480px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem;
  color: var(--text-muted, #6b7280);
}

.mb-4 { margin-bottom: 1rem; }
.card-body { padding: 1.25rem; }
</style>
