import { defineStore } from 'pinia'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const toast = useToast()

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    isAuthenticated: false,
    loading: false
  }),

  getters: {
    isAdmin: (state) => state.user?.role === 'admin',
    isOperator: (state) => ['admin', 'operator'].includes(state.user?.role),
    username: (state) => state.user?.username || '',
    userRole: (state) => state.user?.role || 'viewer'
  },

  actions: {
    async login(credentials) {
      this.loading = true
      try {
        const response = await api.auth.login(credentials)
        const data = response.data

        // 2FA challenge — step 1 returned a temp_token instead of full tokens
        if (data.requires_2fa) {
          return { success: false, requires_2fa: true, temp_token: data.temp_token }
        }

        const { access_token, refresh_token } = data
        localStorage.setItem('access_token', access_token)
        localStorage.setItem('refresh_token', refresh_token)

        await this.fetchUser()
        toast.success('Login successful')
        return { success: true }
      } catch (error) {
        const errorDetail = error.response?.data?.detail || 'Login failed'
        toast.error(errorDetail)
        return { success: false, error: errorDetail }
      } finally {
        this.loading = false
      }
    },

    async login2fa(tempToken, totpCode) {
      this.loading = true
      try {
        const response = await api.auth.login2fa({ temp_token: tempToken, totp_code: totpCode })
        const { access_token, refresh_token } = response.data

        localStorage.setItem('access_token', access_token)
        localStorage.setItem('refresh_token', refresh_token)

        await this.fetchUser()
        toast.success('Login successful')
        return { success: true }
      } catch (error) {
        const errorDetail = error.response?.data?.detail || '2FA verification failed'
        toast.error(errorDetail)
        return { success: false, error: errorDetail }
      } finally {
        this.loading = false
      }
    },

    async fetchUser() {
      try {
        const response = await api.auth.getMe()
        this.user = response.data
        this.isAuthenticated = true
      } catch (error) {
        this.logout()
      }
    },

    logout() {
      const refreshToken = localStorage.getItem('refresh_token')
      api.auth.logout(refreshToken)
      this.user = null
      this.isAuthenticated = false
      toast.info('Logged out successfully')
    },

    async initializeAuth() {
      const token = localStorage.getItem('access_token')
      if (token) {
        await this.fetchUser()
      }
    }
  }
})
