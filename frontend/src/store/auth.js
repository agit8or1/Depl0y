import { defineStore } from 'pinia'
import api, { refreshAccessToken } from '@/services/api'
import { setAccessToken, takeLegacyRefreshToken } from '@/services/tokens'
import { useToast } from 'vue-toastification'

const toast = useToast()

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    isAuthenticated: false,
    initialized: false,
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

        // The refresh token arrives as an httpOnly cookie; keep only the access token, in memory.
        setAccessToken(data.access_token)

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
        setAccessToken(response.data.access_token)

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
      api.auth.logout()
      this.user = null
      this.isAuthenticated = false
      toast.info('Logged out successfully')
    },

    // Called once per page load: trade the refresh cookie (or a pre-2.2.111
    // localStorage token, once) for an access token. No session → stay logged out.
    async initializeAuth() {
      if (this.initialized) return
      this.initialized = true
      try {
        await refreshAccessToken(takeLegacyRefreshToken())
      } catch (e) {
        return
      }
      await this.fetchUser()
    }
  }
})
