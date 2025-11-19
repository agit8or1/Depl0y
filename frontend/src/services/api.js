import axios from 'axios'
import { useToast } from 'vue-toastification'

const toast = useToast()

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Handle 401 errors (unauthorized)
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken) {
          const response = await axios.post('/api/v1/auth/refresh', {
            refresh_token: refreshToken
          })

          const { access_token, refresh_token: newRefreshToken } = response.data

          localStorage.setItem('access_token', access_token)
          localStorage.setItem('refresh_token', newRefreshToken)

          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return api(originalRequest)
        }
      } catch (refreshError) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }

    // Show error toast with detailed message (but not for login errors)
    let message = 'An error occurred'
    if (error.response?.data) {
      // Handle FastAPI validation errors
      if (error.response.data.detail) {
        if (Array.isArray(error.response.data.detail)) {
          // Validation errors from FastAPI
          message = error.response.data.detail.map(err =>
            `${err.loc.join('.')}: ${err.msg}`
          ).join(', ')
        } else {
          message = error.response.data.detail
        }
      }
    }

    console.error('API Error Details:', {
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      headers: error.response?.headers
    })

    // Don't show toast for login endpoint errors (auth store handles them)
    // This prevents duplicate error messages during login/2FA
    const isLoginEndpoint = originalRequest.url?.includes('/auth/login')
    if (!isLoginEndpoint) {
      toast.error(message)
    }

    return Promise.reject(error)
  }
)

export default {
  // Auth
  auth: {
    login: (credentials) => api.post('/auth/login', credentials),
    logout: () => {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    },
    getMe: () => api.get('/auth/me'),
    setupTOTP: () => api.post('/auth/totp/setup'),
    verifyTOTP: (code) => api.post('/auth/totp/verify', { code }),
    disableTOTP: (code) => api.post('/auth/totp/disable', { code })
  },

  // Users
  users: {
    list: (params) => api.get('/users/', { params }),
    get: (id) => api.get(`/users/${id}`),
    create: (data) => api.post('/users/', data),
    update: (id, data) => api.put(`/users/${id}`),
    delete: (id) => api.delete(`/users/${id}`),
    changePassword: (data) => api.post('/users/change-password', data)
  },

  // Proxmox
  proxmox: {
    listHosts: (params) => api.get('/proxmox/', { params }),
    getHost: (id) => api.get(`/proxmox/${id}`),
    createHost: (data) => api.post('/proxmox/', data),
    updateHost: (id, data) => api.put(`/proxmox/${id}`, data),
    deleteHost: (id) => api.delete(`/proxmox/${id}`),
    testConnection: (id) => api.post(`/proxmox/${id}/test`),
    pollHost: (id) => api.post(`/proxmox/${id}/poll`),
    listNodes: (hostId) => api.get(`/proxmox/${hostId}/nodes`),
    getNode: (nodeId) => api.get(`/proxmox/nodes/${nodeId}`),
    getStats: (hostId) => api.get(`/proxmox/${hostId}/stats`),
    getNodeStorage: (nodeId) => api.get(`/proxmox/nodes/${nodeId}/storage`),
    getNodeNetwork: (nodeId) => api.get(`/proxmox/nodes/${nodeId}/network`)
  },

  // Virtual Machines
  vms: {
    list: (params) => api.get('/vms/', { params }),
    get: (id) => api.get(`/vms/${id}`),
    create: (data) => api.post('/vms/', data),
    update: (id, data) => api.put(`/vms/${id}`, data),
    delete: (id) => api.delete(`/vms/${id}`),
    start: (id) => api.post(`/vms/${id}/start`),
    stop: (id) => api.post(`/vms/${id}/stop`),
    getStatus: (id) => api.get(`/vms/${id}/status`),
    getProgress: (id) => api.get(`/vms/${id}/progress`),
    startByVmid: (vmid, node) => api.post(`/vms/control/${node}/${vmid}/start`),
    stopByVmid: (vmid, node) => api.post(`/vms/control/${node}/${vmid}/stop`),
    powerOffByVmid: (vmid, node) => api.post(`/vms/control/${node}/${vmid}/shutdown`),
    restartByVmid: (vmid, node) => api.post(`/vms/control/${node}/${vmid}/restart`),
    deleteByVmid: (vmid, node) => api.delete(`/vms/control/${node}/${vmid}/delete`)
  },

  // ISOs
  isos: {
    list: (params) => api.get('/isos/', { params }),
    get: (id) => api.get(`/isos/${id}`),
    upload: (formData, onUploadProgress) => api.post('/isos/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onUploadProgress
    }),
    downloadFromUrl: (data) => api.post('/isos/download', data),
    delete: (id) => api.delete(`/isos/${id}`),
    verify: (id) => api.post(`/isos/${id}/verify`),
    getProgress: (id) => api.get(`/isos/${id}/progress`)
  },

  // Cloud Images
  cloudImages: {
    list: (params) => api.get('/cloud-images/', { params }),
    get: (id) => api.get(`/cloud-images/${id}`),
    create: (data) => api.post('/cloud-images/', data),
    update: (id, data) => api.put(`/cloud-images/${id}`, data),
    delete: (id) => api.delete(`/cloud-images/${id}`),
    download: (id) => api.post(`/cloud-images/${id}/download`),
    getProgress: (id) => api.get(`/cloud-images/${id}/progress`),
    getSetupScript: () => api.get('/cloud-images/setup-script'),
    checkTemplates: (nodeId) => api.get(`/cloud-images/templates/status/${nodeId}`),
    setupTemplates: (data) => api.post('/cloud-images/setup-templates', data),
    checkSSHStatus: () => api.get('/cloud-images/ssh-status'),
    fetchLatest: () => api.post('/cloud-images/fetch-latest')
  },

  // Updates
  updates: {
    check: (vmId) => api.post(`/updates/vm/${vmId}/check`),
    install: (vmId) => api.post(`/updates/vm/${vmId}/install`),
    getHistory: (vmId, params) => api.get(`/updates/vm/${vmId}/history`, { params }),
    getLog: (logId) => api.get(`/updates/log/${logId}`),
    installQemuAgent: (vmId) => api.post(`/updates/vm/${vmId}/install-qemu-agent`)
  },

  // Dashboard
  dashboard: {
    getStats: () => api.get('/dashboard/stats'),
    getResources: () => api.get('/dashboard/resources'),
    getActivity: (params) => api.get('/dashboard/activity', { params })
  },

  // Bug Report
  bugReport: {
    submit: (data) => api.post('/bug-report/', data)
  },

  // System Logs
  logs: {
    getBackendLogs: (lines = 100) => api.get('/logs/backend', { params: { lines } }),
    tailBackendLogs: (lines = 50) => api.get('/logs/backend/tail', { params: { lines } })
  },

  // Documentation
  docs: {
    list: () => api.get('/docs/'),
    get: (docId, format = 'json') => api.get(`/docs/${docId}`, { params: { format } }),
    downloadPDF: () => api.get('/docs/download/pdf', { responseType: 'blob' })
  },

  // Setup
  setup: {
    enableCloudImages: (password) => api.post('/setup/cloud-images/enable', { proxmox_password: password }),
    enableClusterSSH: (password) => api.post('/setup/proxmox-cluster-ssh/enable', { proxmox_password: password })
  },

  // System Updates
  systemUpdates: {
    check: () => api.get('/system-updates/check'),
    download: () => api.get('/system-updates/download', { responseType: 'blob' }),
    apply: () => api.post('/system-updates/apply')
  },

  // High Availability
  ha: {
    checkStatus: () => api.get('/ha/status'),
    enable: (data) => api.post('/ha/enable', data),
    disable: () => api.post('/ha/disable'),
    listGroups: () => api.get('/ha/groups'),
    createGroup: (data) => api.post('/ha/groups', data),
    listResources: () => api.get('/ha/resources'),
    addResource: (data) => api.post('/ha/resources', data),
    addToGroup: (vmid, group, priority) => api.post('/ha/resources', { vmid, group, priority }),
    removeFromGroup: (vmid) => api.delete(`/ha/resources/${vmid}`)
  },

  // System
  system: {
    getInfo: () => api.get('/system/info')
  }
}
