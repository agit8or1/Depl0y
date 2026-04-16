import axios from 'axios'
import { useToast } from 'vue-toastification'

const toast = useToast()

// Global request timeout: 30 seconds
const REQUEST_TIMEOUT_MS = 30_000

const api = axios.create({
  baseURL: '/api/v1',
  timeout: REQUEST_TIMEOUT_MS,
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
    const status = error.response?.status

    // Handle 401 — try token refresh, then redirect to login
    if (status === 401 && !originalRequest._retry) {
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
        toast.error('Session expired — please log in again')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }

      // No refresh token available — go to login
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      toast.error('Session expired — please log in again')
      window.location.href = '/login'
      return Promise.reject(error)
    }

    if (import.meta.env.DEV) {
      console.error('API Error Details:', {
        status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        url: originalRequest?.url,
      })
    }

    // Don't show toast for login/2FA endpoint errors — auth store handles those
    const isAuthEndpoint = originalRequest?.url?.includes('/auth/login') ||
                           originalRequest?.url?.includes('/auth/2fa')
    if (isAuthEndpoint) return Promise.reject(error)

    // Request timeout (ECONNABORTED or code === 'ECONNABORTED')
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      toast.error('Request timed out — the server is taking too long to respond')
      return Promise.reject(error)
    }

    // Network error — no response received
    if (!error.response) {
      toast.error('Network error — check your connection')
      return Promise.reject(error)
    }

    // 403 — permission denied
    if (status === 403) {
      toast.error("Permission denied — you don't have access to this resource")
      return Promise.reject(error)
    }

    // 503 — service unavailable
    if (status === 503) {
      toast.error('Service unavailable — the backend or Proxmox host may be temporarily down. Please try again shortly.')
      return Promise.reject(error)
    }

    // 422 — FastAPI validation error: extract per-field messages
    if (status === 422) {
      const detail = error.response.data?.detail
      if (Array.isArray(detail) && detail.length > 0) {
        const fieldErrors = detail.map(err => {
          const field = err.loc?.slice(1).join('.') || err.loc?.join('.') || 'field'
          return `${field}: ${err.msg}`
        })
        toast.error('Validation error: ' + fieldErrors.join(' | '))
      } else {
        toast.error('Validation error — please check your input')
      }
      return Promise.reject(error)
    }

    // 5xx — server errors (excluding 503 handled above)
    if (status >= 500) {
      toast.error('Server error — please try again')
      return Promise.reject(error)
    }

    // All other errors — extract FastAPI detail message or fall back
    let message = 'An error occurred'
    if (error.response?.data?.detail) {
      if (Array.isArray(error.response.data.detail)) {
        message = error.response.data.detail.map(err =>
          `${err.loc?.join('.') || 'field'}: ${err.msg}`
        ).join(', ')
      } else {
        message = String(error.response.data.detail)
      }
    }

    toast.error(message)
    return Promise.reject(error)
  }
)

// Named export for views that use the raw axios instance directly
export { api as axiosInstance }

export default {
  // Auth
  auth: {
    login: (credentials) => api.post('/auth/login', credentials),
    login2fa: (data) => api.post('/auth/2fa/login', data),
    logout: (refreshToken) => {
      const p = refreshToken
        ? api.post('/auth/logout', { refresh_token: refreshToken }).catch(() => {})
        : Promise.resolve()
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      return p
    },
    getMe: () => api.get('/auth/me'),
    setupTOTP: () => api.post('/auth/totp/setup'),
    verifyTOTP: (code) => api.post('/auth/totp/verify', { code }),
    disableTOTP: (code) => api.post('/auth/totp/disable', { code }),
    regenerateBackupCodes: (code) => api.post('/auth/totp/backup-codes', { code }),
    getBackupCodeCount: () => api.get('/auth/totp/backup-codes/count'),
    changePassword: (data) => api.patch('/auth/me/password', data),
    updateMe: (data) => api.patch('/auth/me', data),
    listApiKeys: () => api.get('/auth/api-keys'),
    createApiKey: (data) => api.post('/auth/api-keys', data),
    deleteApiKey: (id) => api.delete('/auth/api-keys/' + id),
    listSessions: () => api.get('/auth/sessions'),
    revokeSession: (id) => api.delete('/auth/sessions/' + id),
  },

  // Users
  users: {
    list: (params) => api.get('/users/', { params }),
    get: (id) => api.get(`/users/${id}`),
    create: (data) => api.post('/users/', data),
    update: (id, data) => api.put(`/users/${id}`, data),
    patch: (id, data) => api.patch(`/users/${id}`, data),
    delete: (id) => api.delete(`/users/${id}`),
    changePassword: (data) => api.post('/users/change-password', data),
    setStatus: (id, isActive) => api.patch(`/users/${id}/status`, { is_active: isActive }),
    resetPassword: (id) => api.post(`/users/${id}/reset-password`),
    disableTotp: (id) => api.post(`/users/${id}/disable-totp`),
    invalidateSessions: (id) => api.post(`/users/invalidate-sessions/${id}`),
    invalidateAllSessions: () => api.post('/users/invalidate-sessions-all'),
    setPassword: (id, password) => api.post(`/users/${id}/set-password`, { password }),
    getLoginHistory: (id, limit = 10) => api.get(`/users/${id}/login-history`, { params: { limit } }),
    listHostPermissions: (id) => api.get(`/users/${id}/host-permissions`),
    grantHostPermission: (id, data) => api.post(`/users/${id}/host-permissions`, data),
    updateHostPermission: (id, hostId, data) => api.put(`/users/${id}/host-permissions/${hostId}`, data),
    revokeHostPermission: (id, hostId) => api.delete(`/users/${id}/host-permissions/${hostId}`),
  },

  // Proxmox
  proxmox: {
    listHosts: (params) => api.get('/proxmox/', { params }),
    getHost: (id) => api.get(`/proxmox/${id}`),
    createHost: (data) => api.post('/proxmox/', data),
    updateHost: (id, data) => api.put(`/proxmox/${id}`, data),
    deleteHost: (id) => api.delete(`/proxmox/${id}`),
    testConnection: (id) => api.post(`/proxmox/${id}/test`),
    testNewConnection: (data) => api.post('/proxmox/test-connection', data),
    pollHost: (id) => api.post(`/proxmox/${id}/poll`),
    listNodes: (hostId) => api.get(`/proxmox/${hostId}/nodes`),
    getNode: (nodeId) => api.get(`/proxmox/nodes/${nodeId}`),
    getStats: (hostId) => api.get(`/proxmox/${hostId}/stats`),
    getNodeStorage: (nodeId) => api.get(`/proxmox/nodes/${nodeId}/storage`),
    getNodeNetwork: (nodeId) => api.get(`/proxmox/nodes/${nodeId}/network`),
    deleteNode: (nodeId) => api.delete(`/proxmox/nodes/${nodeId}`),
    updateNodeIdrac: (nodeId, data) => api.patch(`/proxmox/nodes/${nodeId}/idrac`, data),
    getFederationSummary: () => api.get('/proxmox/federation/summary'),
    getDatacenterSummary: (hostId) => api.get(`/proxmox/${hostId}/datacenter/summary`),
    getHostVersion: (hostId) => api.get(`/proxmox/${hostId}/version`),
    reconnectHost: (hostId) => api.post(`/proxmox/${hostId}/reconnect`),
  },

  // Virtual Machines
  vms: {
    list: (params) => api.get('/vms/', { params }),
    listManaged: () => api.get('/vms/managed'),
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
    deleteByVmid: (vmid, node) => api.delete(`/vms/control/${node}/${vmid}/delete`),
    getAgentIP: (node, vmid) => api.get(`/vms/control/${node}/${vmid}/ip`),
    adoptVm: (data) => api.post('/vms/adopt', data),
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
    check: (vmId, creds = null) => api.post(`/updates/vm/${vmId}/check`, creds || {}),
    install: (vmId, creds = null) => api.post(`/updates/vm/${vmId}/install`, creds || {}),
    scanSecurity: (vmId, creds = null) => api.post(`/updates/vm/${vmId}/scan-security`, creds || {}),
    currentLog: (vmId) => api.get(`/updates/vm/${vmId}/current-log`),
    getHistory: (vmId, params) => api.get(`/updates/vm/${vmId}/history`, { params }),
    getLog: (logId) => api.get(`/updates/log/${logId}`),
    installQemuAgent: (vmId) => api.post(`/updates/vm/${vmId}/install-qemu-agent`),
    getSchedule: () => api.get('/updates/schedule'),
    saveSchedule: (data) => api.put('/updates/schedule', data),
    getCache: () => api.get('/updates/cache'),
  },

  // Dashboard
  dashboard: {
    getStats: () => api.get('/dashboard/stats'),
    getResources: () => api.get('/dashboard/resources'),
    getActivity: (params) => api.get('/dashboard/activity', { params }),
    getSummary: () => api.get('/dashboard/summary'),
    getRecentActivity: (params) => api.get('/dashboard/recent-activity', { params }),
    getAlerts: () => api.get('/dashboard/alerts'),
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
    apply: () => api.post('/system-updates/apply'),
    log: () => api.get('/system-updates/log')
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
    getInfo: () => api.get('/system/info'),
    testEmail: () => api.post('/system/test-email'),
    getDiagnostics: () => api.get('/system/diagnostics'),
    dbCheck: () => api.post('/system/db-check'),
    health: () => api.get('/system/health'),
    getMetrics: () => api.get('/system/metrics'),
    getSettings: () => api.get('/system/settings'),
    updateSettings: (data) => api.patch('/system/settings', data),
    getCacheStats: () => api.get('/system/cache/stats'),
    clearCache: () => api.post('/system/cache/clear'),
    dbVacuum: () => api.post('/system/db-vacuum'),
    restartBackend: () => api.post('/system/restart'),
    validateSettings: (data) => api.post('/system/settings/validate', data),
  },

  // Developer Tools
  devTools: {
    getOpenApiSummary: () => api.get('/openapi-summary'),
  },

  // LLM Deployment
  llm: {
    getCatalog: () => api.get('/llm/catalog'),
    getGpuDevices: (hostId, nodeId) => api.get('/llm/gpu-devices', { params: { host_id: hostId, node_id: nodeId } }),
    deploy: (data) => api.post('/llm/deploy', data),
    listDeployments: () => api.get('/llm/deployments'),
    getDeployment: (id) => api.get(`/llm/deployments/${id}`),
    // Ollama Model Manager
    getVMModels: (vmId) => api.get(`/llm/ai-tune/${vmId}/models`),
    pullModel: (vmId, model) => api.post(`/llm/ai-tune/${vmId}/models/pull`, { model }),
    getPullJobStatus: (vmId, jobId) => api.get(`/llm/ai-tune/${vmId}/models/pull/${jobId}`),
    deleteModel: (vmId, modelName) => api.delete(`/llm/ai-tune/${vmId}/models/${encodeURIComponent(modelName)}`),
    // Conversation Logger
    getConvLogs: (vmId, limit = 50) => api.get(`/llm/ai-tune/${vmId}/conv-logs`, { params: { limit } }),
    getConvLoggerStatus: (vmId) => api.get(`/llm/ai-tune/${vmId}/conv-logs/status`),
    installConvLogger: (vmId) => api.post(`/llm/ai-tune/${vmId}/conv-logs/install`),
    clearConvLogs: (vmId) => api.delete(`/llm/ai-tune/${vmId}/conv-logs`),
    // RAG
    getRagStatus: (vmId) => api.get(`/llm/ai-tune/${vmId}/rag/status`),
    installRag: (vmId, embedModel) => api.post(`/llm/ai-tune/${vmId}/rag/install`, { embed_model: embedModel }),
    ragIngest: (vmId, text, source, metadata) => api.post(`/llm/ai-tune/${vmId}/rag/ingest`, { text, source, metadata }),
    ragQuery: (vmId, query, nResults = 5) => api.post(`/llm/ai-tune/${vmId}/rag/query`, { query, n_results: nResults }),
    ragListDocs: (vmId) => api.get(`/llm/ai-tune/${vmId}/rag/docs`),
    ragDeleteDoc: (vmId, docId) => api.delete(`/llm/ai-tune/${vmId}/rag/docs/${docId}`),
    getJobStatus: (vmId, jobId) => api.get(`/llm/ai-tune/${vmId}/apply/${jobId}`),
    // Instance management (deployed VM proxy)
    listInstances: () => api.get('/llm/instances'),
    getInstanceModels: (hostId, node, vmid) => api.get(`/llm/instances/${hostId}/${node}/${vmid}/models`),
    getInstanceStatus: (hostId, node, vmid) => api.get(`/llm/instances/${hostId}/${node}/${vmid}/status`),
    pullInstanceModel: (hostId, node, vmid, model) => api.post(`/llm/instances/${hostId}/${node}/${vmid}/pull`, { model }),
    deleteInstanceModel: (hostId, node, vmid, model) => api.delete(`/llm/instances/${hostId}/${node}/${vmid}/models/${encodeURIComponent(model)}`),
    unloadInstanceModel: (hostId, node, vmid, model) => api.post(`/llm/instances/${hostId}/${node}/${vmid}/unload/${encodeURIComponent(model)}`),
    getInstanceVersion: (hostId, node, vmid) => api.get(`/llm/instances/${hostId}/${node}/${vmid}/version`),
  },

  // VM Import
  vmImport: {
    list: () => api.get('/vm-import/'),
    upload: (formData, onUploadProgress) => api.post('/vm-import/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress,
      timeout: 0,  // no timeout for large uploads
    }),
    deploy: (jobId, data) => api.post(`/vm-import/${jobId}/deploy`, data),
    getProgress: (jobId) => api.get(`/vm-import/${jobId}/progress`),
    cancel: (jobId) => api.delete(`/vm-import/${jobId}`),
    // VMware direct import
    vmwareTest: (data) => api.post('/vm-import/vmware/test', data),
    vmwareListVMs: (data) => api.post('/vm-import/vmware/vms', data),
    vmwarePrepare: (data) => api.post('/vm-import/vmware/prepare', data),
    // URL / OVF / format-detect / disk-convert
    fromUrl: (data) => api.post('/vm-import/from-url', data),
    fromOvf: (data) => api.post('/vm-import/from-ovf', data),
    detectFormat: (params) => api.get('/vm-import/detect-format', { params }),
    convertDisk: (data) => api.post('/vm-import/convert-disk', data),
  },

  // VM Agent
  vmAgent: {
    register: (data) => api.post('/vm-agent/register', data),
    list: () => api.get('/vm-agent/'),
    get: (id) => api.get(`/vm-agent/${id}`),
    getScans: (id, limit = 50) => api.get(`/vm-agent/${id}/scans`, { params: { limit } }),
    delete: (id) => api.delete(`/vm-agent/${id}`),
    getInstallCommand: (id) => api.get(`/vm-agent/${id}/install-command`),
    getSettings: () => api.get('/vm-agent/settings/linux-agent'),
    updateSettings: (data) => api.put('/vm-agent/settings/linux-agent', data),
    runAITune: (vmId) => api.post(`/llm/ai-tune/${vmId}`),
    applyTuneAction: (vmId, actionId) => api.post(`/llm/ai-tune/${vmId}/apply`, { action_id: actionId }),
    getApplyJobStatus: (vmId, jobId) => api.get(`/llm/ai-tune/${vmId}/apply/${jobId}`)
  },

  // Security management
  security: {
    getSettings: () => api.get('/security/settings'),
    updateSettings: (data) => api.put('/security/settings', data),
    getLockouts: () => api.get('/security/lockouts'),
    unlockAccount: (username) => api.delete(`/security/lockouts/${username}`),
    getFailedLogins: (limit = 100) => api.get('/security/failed-logins', { params: { limit } }),
    getIPList: () => api.get('/security/ip-list'),
    addIPEntry: (data) => api.post('/security/ip-list', data),
    deleteIPEntry: (id) => api.delete(`/security/ip-list/${id}`),
    toggleIPEntry: (id) => api.patch(`/security/ip-list/${id}/toggle`),
    getGeoIPRules: () => api.get('/security/geoip'),
    addGeoIPRule: (data) => api.post('/security/geoip', data),
    deleteGeoIPRule: (id) => api.delete(`/security/geoip/${id}`),
    toggleGeoIPRule: (id) => api.patch(`/security/geoip/${id}/toggle`),
    getEvents: (params) => api.get('/security/events', { params }),
    lookupIP: (ip) => api.get(`/security/lookup-ip/${ip}`),
    getLoginHistory: (limit = 50, params) => api.get('/security/login-history', { params: { limit, ...params } }),
    getPasswordPolicy: () => api.get('/security/password-policy'),
    updatePasswordPolicy: (data) => api.patch('/security/password-policy', data),
    get2faOverview: () => api.get('/security/2fa-overview'),
    adminDisable2fa: (userId) => api.post(`/users/${userId}/disable-totp`),
  },

  // iDRAC / iLO management (Proxmox hosts)
  idrac: {
    getStatus: () => api.get('/idrac/status'),
    triggerPoll: () => api.post('/idrac/poll'),
    testConnection: (hostId) => api.get(`/idrac/${hostId}/test`),
    getInfo: (hostId) => api.get(`/idrac/${hostId}/info`),
    getPowerState: (hostId) => api.get(`/idrac/${hostId}/power`),
    powerAction: (hostId, action) => api.post(`/idrac/${hostId}/power/${action}`),
    getLogs: (hostId, limit = 50) => api.get(`/idrac/${hostId}/logs`, { params: { limit } }),
    getThermal: (hostId) => api.get(`/idrac/${hostId}/thermal`),
    getPowerUsage: (hostId) => api.get(`/idrac/${hostId}/power-usage`),
    getManager: (hostId) => api.get(`/idrac/${hostId}/manager`),
    getNetwork: (hostId) => api.get(`/idrac/${hostId}/network`),
    patchNetwork: (hostId, ifaceId, config) => api.patch(`/idrac/${hostId}/network/${ifaceId}`, config),
    getProcessors: (hostId) => api.get(`/idrac/${hostId}/processors`),
    getMemory: (hostId) => api.get(`/idrac/${hostId}/memory`),
    getStorage: (hostId) => api.get(`/idrac/${hostId}/storage`),
    getFirmware: (hostId) => api.get(`/idrac/${hostId}/firmware`),
    // Standalone BMC CRUD
    listStandalone: () => api.get('/idrac/standalone/'),
    createStandalone: (data) => api.post('/idrac/standalone/', data),
    updateStandalone: (id, data) => api.put(`/idrac/standalone/${id}`, data),
    deleteStandalone: (id) => api.delete(`/idrac/standalone/${id}`),
    testStandalone: (id) => api.get(`/idrac/standalone/${id}/test`),
    getStandaloneInfo: (id) => api.get(`/idrac/standalone/${id}/info`),
    standalonepower: (id, action) => api.post(`/idrac/standalone/${id}/power/${action}`),
    getStandaloneLogs: (id, limit = 50) => api.get(`/idrac/standalone/${id}/logs`, { params: { limit } }),
    getStandaloneThermal: (id) => api.get(`/idrac/standalone/${id}/thermal`),
    getStandalonePowerUsage: (id) => api.get(`/idrac/standalone/${id}/power-usage`),
    getStandaloneManager: (id) => api.get(`/idrac/standalone/${id}/manager`),
    getStandaloneNetwork: (id) => api.get(`/idrac/standalone/${id}/network`),
    patchStandaloneNetwork: (id, ifaceId, config) => api.patch(`/idrac/standalone/${id}/network/${ifaceId}`, config),
    getStandaloneProcessors: (id) => api.get(`/idrac/standalone/${id}/processors`),
    getStandaloneMemory: (id) => api.get(`/idrac/standalone/${id}/memory`),
    getStandaloneStorage: (id) => api.get(`/idrac/standalone/${id}/storage`),
    getStandaloneFirmware: (id) => api.get(`/idrac/standalone/${id}/firmware`),
    // Sensors (unified IPMI-style: temp + fans + PSU + voltage)
    getSensors: (hostId) => api.get(`/idrac/${hostId}/sensors`),
    getStandaloneSensors: (id) => api.get(`/idrac/standalone/${id}/sensors`),
    // SSH-based (host OS)
    runSshUpdate: (hostId) => api.post(`/idrac/${hostId}/ssh/update`),
    testSsh: (hostId) => api.get(`/idrac/${hostId}/ssh/test`),
    getSshHardware: (hostId) => api.get(`/idrac/${hostId}/ssh/hardware`),
    getSshNetwork: (hostId) => api.get(`/idrac/${hostId}/ssh/network`),
    getSshFirmware: (hostId) => api.get(`/idrac/${hostId}/ssh/firmware`),
    getSshLogs: (hostId, limit = 100) => api.get(`/idrac/${hostId}/ssh/logs`, { params: { limit } }),
    runStandaloneSshUpdate: (id) => api.post(`/idrac/standalone/${id}/ssh/update`),
    testStandaloneSsh: (id) => api.get(`/idrac/standalone/${id}/ssh/test`),
    getStandaloneSshHardware: (id) => api.get(`/idrac/standalone/${id}/ssh/hardware`),
    getStandaloneSshNetwork: (id) => api.get(`/idrac/standalone/${id}/ssh/network`),
    getStandaloneSshFirmware: (id) => api.get(`/idrac/standalone/${id}/ssh/firmware`),
    getStandaloneSshLogs: (id, limit = 100) => api.get(`/idrac/standalone/${id}/ssh/logs`, { params: { limit } }),
  },

  // PBS Servers
  pbs: {
    list: () => api.get('/pbs/'),
    get: (id) => api.get(`/pbs/${id}`),
    create: (data) => api.post('/pbs/', data),
    update: (id, data) => api.put(`/pbs/${id}`, data),
    delete: (id) => api.delete(`/pbs/${id}`),
    // iDRAC/iLO sub-endpoints
    testIdrac: (id) => api.get(`/pbs/${id}/idrac/test`),
    getIdracInfo: (id) => api.get(`/pbs/${id}/idrac/info`),
    getIdracPower: (id) => api.get(`/pbs/${id}/idrac/power`),
    idracPowerAction: (id, action) => api.post(`/pbs/${id}/idrac/power/${action}`),
    getIdracLogs: (id, limit = 50) => api.get(`/pbs/${id}/idrac/logs`, { params: { limit } }),
    getIdracThermal: (id) => api.get(`/pbs/${id}/idrac/thermal`),
    getIdracPowerUsage: (id) => api.get(`/pbs/${id}/idrac/power-usage`),
    getIdracManager: (id) => api.get(`/pbs/${id}/idrac/manager`),
    getIdracNetwork: (id) => api.get(`/pbs/${id}/idrac/network`),
    patchIdracNetwork: (id, ifaceId, config) => api.patch(`/pbs/${id}/idrac/network/${ifaceId}`, config),
    getIdracProcessors: (id) => api.get(`/pbs/${id}/idrac/processors`),
    getIdracMemory: (id) => api.get(`/pbs/${id}/idrac/memory`),
    getIdracStorage: (id) => api.get(`/pbs/${id}/idrac/storage`),
    getIdracFirmware: (id) => api.get(`/pbs/${id}/idrac/firmware`),
    getIdracSensors: (id) => api.get(`/pbs/${id}/idrac/sensors`),
    // SSH-based (host OS)
    runIdracSshUpdate: (id) => api.post(`/pbs/${id}/idrac/ssh/update`),
    testIdracSsh: (id) => api.get(`/pbs/${id}/idrac/ssh/test`),
    getIdracSshHardware: (id) => api.get(`/pbs/${id}/idrac/ssh/hardware`),
    getIdracSshNetwork: (id) => api.get(`/pbs/${id}/idrac/ssh/network`),
    getIdracSshFirmware: (id) => api.get(`/pbs/${id}/idrac/ssh/firmware`),
    getIdracSshLogs: (id, limit = 100) => api.get(`/pbs/${id}/idrac/ssh/logs`, { params: { limit } }),
  },

  // PVE VM Control (/pve-vm/{host_id}/{node}/{vmid}/...)
  pveVm: {
    getConfig: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/config`),
    updateConfig: (h, node, vmid, data) => api.put(`/pve-vm/${h}/${node}/${vmid}/config`, data),
    getStatus: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/status`),
    start: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/start`),
    stop: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/stop`),
    shutdown: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/shutdown`),
    reboot: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/reboot`),
    reset: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/reset`),
    suspend: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/suspend`),
    resume: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/resume`),
    listSnapshots: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/snapshots`),
    createSnapshot: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/snapshots`, data),
    deleteSnapshot: (h, node, vmid, snap) => api.delete(`/pve-vm/${h}/${node}/${vmid}/snapshots/${snap}`),
    rollbackSnapshot: (h, node, vmid, snap) => api.post(`/pve-vm/${h}/${node}/${vmid}/snapshots/${snap}/rollback`),
    getSnapshotConfig: (h, node, vmid, snapname) => api.get(`/pve-vm/${h}/${node}/${vmid}/snapshot/${snapname}/config`),
    clone: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/clone`, data),
    migrate: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/migrate`, data),
    convertToTemplate: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/template`),
    deleteVm: (h, node, vmid) => api.delete(`/pve-vm/${h}/${node}/${vmid}`),
    addDisk: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/disk`, data),
    resizeDisk: (h, node, vmid, disk, data) => api.put(`/pve-vm/${h}/${node}/${vmid}/disk/${disk}/resize`, data),
    deleteDisk: (h, node, vmid, disk) => api.delete(`/pve-vm/${h}/${node}/${vmid}/disk/${disk}`),
    addNic: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/network`, data),
    deleteNic: (h, node, vmid, nic) => api.delete(`/pve-vm/${h}/${node}/${vmid}/network/${nic}`),
    getFirewallRules: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/firewall/rules`),
    addFirewallRule: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/firewall/rules`, data),
    updateFirewallRule: (h, node, vmid, pos, data) => api.put(`/pve-vm/${h}/${node}/${vmid}/firewall/rules/${pos}`, data),
    deleteFirewallRule: (h, node, vmid, pos) => api.delete(`/pve-vm/${h}/${node}/${vmid}/firewall/rules/${pos}`),
    getFirewallOptions: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/firewall/options`),
    setFirewallOptions: (h, node, vmid, data) => api.put(`/pve-vm/${h}/${node}/${vmid}/firewall/options`, data),
    getVncTicket: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/vncticket`),
    getRrdData: (h, node, vmid, params) => api.get(`/pve-vm/${h}/${node}/${vmid}/rrddata`, { params }),
    vmPending: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/pending`),
    // Aliases for VMDetail.vue naming convention
    config: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/config`),
    updateConfig: (h, node, vmid, data) => api.put(`/pve-vm/${h}/${node}/${vmid}/config`, data),
    status: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/status`),
    rrddata: (h, node, vmid, timeframe = 'hour') => api.get(`/pve-vm/${h}/${node}/${vmid}/rrddata`, { params: { timeframe } }),
    snapshots: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/snapshots`),
    firewallRules: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/firewall/rules`),
    detachDisk: (h, node, vmid, disk, del = false) => api.delete(`/pve-vm/${h}/${node}/${vmid}/disk/${disk}`, { params: { delete: del } }),
    moveDisk: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/move-disk`, data),
    listUnusedDisks: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/unused-disks`),
    reattachDisk: (h, node, vmid, unused_key, bus = 'scsi') => api.post(`/pve-vm/${h}/${node}/${vmid}/reattach-disk`, null, { params: { unused_key, bus } }),
    addNIC: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/network`, data),
    updateNIC: (h, node, vmid, nic, data) => api.put(`/pve-vm/${h}/${node}/${vmid}/network/${nic}`, data),
    removeNIC: (h, node, vmid, nic) => api.delete(`/pve-vm/${h}/${node}/${vmid}/network/${nic}`),
    template: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/template`),
    delete: (h, node, vmid) => api.delete(`/pve-vm/${h}/${node}/${vmid}`),
    // VM search across all hosts
    search: (params) => api.get('/pve-vm/search', { params }),
    // Cloud-init
    getCloudInit: (h, node, vmid) => api.get(`/pve-vm/${h}/${node}/${vmid}/config`),
    updateCloudInit: (h, node, vmid, data) => api.put(`/pve-vm/${h}/${node}/${vmid}/cloudinit`, data),
    regenerateCloudinit: (h, node, vmid) => api.post(`/pve-vm/${h}/${node}/${vmid}/cloudinit/regenerate`),
    // PCI passthrough
    addPciDevice: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/pci`, data),
    removePciDevice: (h, node, vmid, index) => api.delete(`/pve-vm/${h}/${node}/${vmid}/pci/${index}`),
    // USB passthrough
    addUsbDevice: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/usb`, data),
    removeUsbDevice: (h, node, vmid, index) => api.delete(`/pve-vm/${h}/${node}/${vmid}/usb/${index}`),
    // Serial ports
    addSerialPort: (h, node, vmid, data) => api.post(`/pve-vm/${h}/${node}/${vmid}/serial`, data),
    removeSerialPort: (h, node, vmid, index) => api.delete(`/pve-vm/${h}/${node}/${vmid}/serial/${index}`),
  },

  // PVE Node/Cluster Control (/pve-node/{host_id}/...)
  pveNode: {
    // Cluster
    clusterStatus: (h) => api.get(`/pve-node/${h}/cluster/status`),
    nextId: (h) => api.get(`/pve-node/${h}/cluster/nextid`),
    clusterOptions: (h) => api.get(`/pve-node/${h}/cluster/options`),
    // Cluster Firewall
    getClusterFirewallRules: (h) => api.get(`/pve-node/${h}/cluster/firewall/rules`),
    addClusterFirewallRule: (h, data) => api.post(`/pve-node/${h}/cluster/firewall/rules`, data),
    deleteClusterFirewallRule: (h, pos) => api.delete(`/pve-node/${h}/cluster/firewall/rules/${pos}`),
    // HA
    listHaResources: (h) => api.get(`/pve-node/${h}/cluster/ha/resources`),
    addHaResource: (h, data) => api.post(`/pve-node/${h}/cluster/ha/resources`, data),
    updateHaResource: (h, sid, data) => api.put(`/pve-node/${h}/cluster/ha/resources/${encodeURIComponent(sid)}`, data),
    deleteHaResource: (h, sid) => api.delete(`/pve-node/${h}/cluster/ha/resources/${encodeURIComponent(sid)}`),
    listHaGroups: (h) => api.get(`/pve-node/${h}/cluster/ha/groups`),
    createHaGroup: (h, data) => api.post(`/pve-node/${h}/cluster/ha/groups`, data),
    updateHaGroup: (h, groupid, data) => api.put(`/pve-node/${h}/cluster/ha/groups/${encodeURIComponent(groupid)}`, data),
    deleteHaGroup: (h, groupid) => api.delete(`/pve-node/${h}/cluster/ha/groups/${encodeURIComponent(groupid)}`),
    haStatus: (h) => api.get(`/pve-node/${h}/cluster/ha/status`),
    haCurrentStatus: (h) => api.get(`/pve-node/${h}/cluster/ha/status`),
    // Access
    listUsers: (h) => api.get(`/pve-node/${h}/access/users`),
    createUser: (h, data) => api.post(`/pve-node/${h}/access/users`, data),
    updateUser: (h, uid, data) => api.put(`/pve-node/${h}/access/users/${uid}`, data),
    deleteUser: (h, uid) => api.delete(`/pve-node/${h}/access/users/${uid}`),
    listUserTokens: (h, uid) => api.get(`/pve-node/${h}/access/users/${uid}/tokens`),
    createUserToken: (h, uid, tid, data = {}) => api.post(`/pve-node/${h}/access/users/${uid}/tokens/${tid}`, data),
    deleteUserToken: (h, uid, tid) => api.delete(`/pve-node/${h}/access/users/${uid}/tokens/${tid}`),
    listRoles: (h) => api.get(`/pve-node/${h}/access/roles`),
    createRole: (h, data) => api.post(`/pve-node/${h}/access/roles`, data),
    updateRole: (h, roleid, data) => api.put(`/pve-node/${h}/access/roles/${encodeURIComponent(roleid)}`, data),
    deleteRole: (h, roleid) => api.delete(`/pve-node/${h}/access/roles/${encodeURIComponent(roleid)}`),
    listAcl: (h) => api.get(`/pve-node/${h}/access/acl`),
    updateAcl: (h, data) => api.put(`/pve-node/${h}/access/acl`, data),
    listGroups: (h) => api.get(`/pve-node/${h}/access/groups`),
    createGroup: (h, data) => api.post(`/pve-node/${h}/access/groups`, data),
    updateGroup: (h, groupid, data) => api.put(`/pve-node/${h}/access/groups/${encodeURIComponent(groupid)}`, data),
    deleteGroup: (h, groupid) => api.delete(`/pve-node/${h}/access/groups/${encodeURIComponent(groupid)}`),
    // Pools
    listPools: (h) => api.get(`/pve-node/${h}/pools`),
    getPool: (h, pid) => api.get(`/pve-node/${h}/pools/${pid}`),
    createPool: (h, data) => api.post(`/pve-node/${h}/pools`, data),
    updatePool: (h, pid, data) => api.put(`/pve-node/${h}/pools/${pid}`, data),
    deletePool: (h, pid) => api.delete(`/pve-node/${h}/pools/${pid}`),
    // Node
    nodeStatus: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/status`),
    nodeRrdData: (h, node, params) => api.get(`/pve-node/${h}/nodes/${node}/rrddata`, { params }),
    nodeVms: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/vms`),
    // Tasks
    listTasks: (h, node, params) => api.get(`/pve-node/${h}/nodes/${node}/tasks`, { params }),
    taskStatus: (h, node, upid) => api.get(`/pve-node/${h}/nodes/${node}/tasks/${upid}/status`),
    stopTask: (h, node, upid) => api.delete(`/pve-node/${h}/nodes/${node}/tasks/${upid}`),
    // Storage
    listStorage: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/storage`),
    browseStorage: (h, node, storage, params) => api.get(`/pve-node/${h}/nodes/${node}/storage/${storage}/content`, { params }),
    deleteVolume: (h, node, storage, volid) => api.delete(`/pve-node/${h}/nodes/${node}/storage/${storage}/content/${volid}`),
    // Network
    listNetwork: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/network`),
    createNetwork: (h, node, data) => api.post(`/pve-node/${h}/nodes/${node}/network`, data),
    updateNetwork: (h, node, iface, data) => api.put(`/pve-node/${h}/nodes/${node}/network/${iface}`, data),
    deleteNetwork: (h, node, iface) => api.delete(`/pve-node/${h}/nodes/${node}/network/${iface}`),
    applyNetwork: (h, node) => api.put(`/pve-node/${h}/nodes/${node}/network`),
    revertNetwork: (h, node) => api.delete(`/pve-node/${h}/nodes/${node}/network`),
    // Terminal
    nodeTermproxy: (h, node) => api.post(`/pve-node/${h}/nodes/${node}/termproxy`),
    // Backup
    runBackup: (h, node, data) => api.post(`/pve-node/${h}/nodes/${node}/vzdump`, data),
    listBackupSchedules: (h) => api.get(`/pve-node/${h}/cluster/backup`),
    createBackupSchedule: (h, data) => api.post(`/pve-node/${h}/cluster/backup`, data),
    updateBackupSchedule: (h, id, data) => api.put(`/pve-node/${h}/cluster/backup/${id}`, data),
    deleteBackupSchedule: (h, id) => api.delete(`/pve-node/${h}/cluster/backup/${id}`),
    runBackupScheduleNow: (h, id, data) => api.post(`/pve-node/${h}/cluster/backup/${id}/run`, data),
    getBackupHistory: (h, params) => api.get(`/pve-node/${h}/backup/history`, { params }),
    // LXC
    listContainers: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/lxc`),
    getContainerConfig: (h, node, vmid) => api.get(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/config`),
    updateContainerConfig: (h, node, vmid, data) => api.put(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/config`, data),
    getContainerStatus: (h, node, vmid) => api.get(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/status`),
    containerAction: (h, node, vmid, action) => api.post(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/${action}`),
    listContainerSnapshots: (h, node, vmid) => api.get(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/snapshots`),
    createContainerSnapshot: (h, node, vmid, data) => api.post(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/snapshots`, data),
    rollbackContainerSnapshot: (h, node, vmid, snap) => api.post(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/snapshots/${snap}/rollback`),
    containerTermproxy: (h, node, vmid) => api.post(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/termproxy`),
    deleteContainer: (h, node, vmid) => api.delete(`/pve-node/${h}/nodes/${node}/lxc/${vmid}`),
    cloneLxc: (h, node, vmid, data) => api.post(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/clone`, data),
    migrateLxc: (h, node, vmid, data) => api.post(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/migrate`, data),
    lxcRrdData: (h, node, vmid, params) => api.get(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/rrddata`, { params }),
    resizeLxcDisk: (h, node, vmid, data) => api.post(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/resize`, data),
    deleteContainerSnapshot: (h, node, vmid, snap) => api.delete(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/snapshots/${snap}`),
    // LXC Firewall
    getCtFirewallRules: (h, node, vmid) => api.get(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/firewall/rules`),
    addCtFirewallRule: (h, node, vmid, data) => api.post(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/firewall/rules`, data),
    updateCtFirewallRule: (h, node, vmid, pos, data) => api.put(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/firewall/rules/${pos}`, data),
    deleteCtFirewallRule: (h, node, vmid, pos) => api.delete(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/firewall/rules/${pos}`),
    getCtFirewallOptions: (h, node, vmid) => api.get(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/firewall/options`),
    setCtFirewallOptions: (h, node, vmid, data) => api.put(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/firewall/options`, data),
    // Restore
    restoreBackup: (h, node, vmid, data) => api.post(`/pve-node/${h}/nodes/${node}/qemu/${vmid}/restore`, data),
    restoreLxcBackup: (h, node, vmid, data) => api.post(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/restore`, data),
    // Aliases for NodeDetail.vue / Tasks.vue / Containers.vue naming convention
    nodeRrddata: (h, node, timeframe = 'hour') => api.get(`/pve-node/${h}/nodes/${node}/rrddata`, { params: { timeframe } }),
    tasks: (h, node, params) => api.get(`/pve-node/${h}/nodes/${node}/tasks`, { params }),
    taskLog: (h, node, upid) => api.get(`/pve-node/${h}/nodes/${node}/tasks/${upid}/log`),
    storage: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/storage`),
    storageContent: (h, node, storage, content) => api.get(`/pve-node/${h}/nodes/${node}/storage/${storage}/content`, { params: { content } }),
    network: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/network`),
    containers: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/lxc`),
    ctStatus: (h, node, vmid) => api.get(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/status`),
    ctAction: (h, node, vmid, action) => api.post(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/${action}`),
    ctConfig: (h, node, vmid) => api.get(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/config`),
    ctSnapshots: (h, node, vmid) => api.get(`/pve-node/${h}/nodes/${node}/lxc/${vmid}/snapshots`),
    clusterResources: (h, type) => api.get(`/pve-node/${h}/cluster/resources`, { params: { type } }),
    clusterResourcesFresh: (h) => api.get(`/pve-node/${h}/cluster/resources`, { params: { nocache: true } }),
    diskIoRates: (h) => api.get(`/pve-node/${h}/disk-io-rates`),
    // VM / LXC create
    createVm: (h, node, data) => api.post(`/pve-node/${h}/nodes/${node}/qemu`, data),
    createLxc: (h, node, data) => api.post(`/pve-node/${h}/nodes/${node}/lxc`, data),
    // Templates
    listLxcTemplates: (h, node, storage) => api.get(`/pve-node/${h}/nodes/${node}/lxc-templates`, { params: { storage } }),
    listStorageTemplates: (h, node, storage) => api.get(`/pve-node/${h}/nodes/${node}/storage/${storage}/templates`),
    listAvailableTemplates: (h, node, section) => api.get(`/pve-node/${h}/nodes/${node}/pveam/available`, { params: section ? { section } : {} }),
    listAllAvailableTemplates: (h, section) => api.get(`/pve-node/${h}/pveam/available`, { params: section ? { section } : {} }),
    downloadTemplate: (h, node, data) => api.post(`/pve-node/${h}/nodes/${node}/pveam/download`, data),
    listVmTemplates: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/templates`),
    // Storage upload
    uploadToStorage: (h, node, storage, formData, onProgress) => api.post(`/pve-node/${h}/nodes/${node}/storage/${storage}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
      onUploadProgress: onProgress,
    }),
    // Download URL directly to Proxmox storage (Proxmox download-url API)
    downloadUrlToStorage: (h, node, storage, data) => api.post(`/pve-node/${h}/nodes/${node}/storage/${storage}/download-url`, data),
    // Disk Health / SMART
    listDisks: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/disks/list`),
    getSmartData: (h, node, disk) => api.get(`/pve-node/${h}/nodes/${node}/disks/${encodeURIComponent(disk)}/smart`),
    // Services
    listServices: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/services`),
    serviceAction: (h, node, service, cmd) => api.post(`/pve-node/${h}/nodes/${node}/services/${service}/${cmd}`),
    // Certificates
    listCertificates: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/certificates/info`),
    // APT / Package updates
    aptListUpdates: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/apt/update`),
    aptRefreshPackages: (h, node) => api.post(`/pve-node/${h}/nodes/${node}/apt/update`),
    aptUpgradeAll: (h, node) => api.post(`/pve-node/${h}/nodes/${node}/apt/upgrade`, {}),
    aptUpgradeSelected: (h, node, packages) => api.post(`/pve-node/${h}/nodes/${node}/apt/upgrade`, { packages }),
    aptInstalledVersions: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/apt/versions`),
    // Hardware
    listPciDevices: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/hardware/pci`),
    listUsbDevices: (h, node) => api.get(`/pve-node/${h}/nodes/${node}/hardware/usb`),
    getPciDeviceDetail: (h, node, pciid) => api.get(`/pve-node/${h}/nodes/${node}/hardware/pci/${encodeURIComponent(pciid)}`),
    getPciMdevTypes: (h, node, pciid) => api.get(`/pve-node/${h}/nodes/${node}/hardware/pci/${encodeURIComponent(pciid)}/mdev`),
  },

  // Audit Log
  audit: {
    list: (params) => api.get('/audit/', { params }),
    log: (params) => api.get('/audit/', { params }),  // alias — GET /audit/?limit=N
    feed: (params) => api.get('/audit/feed', { params }),
    stats: (params) => api.get('/audit/stats', { params }),
    getStats: (params) => api.get('/audit/stats', { params }),
    export: (params) => api.get('/audit/export', { params, responseType: 'blob' }),
    cleanup: (days) => api.delete('/audit/cleanup', { params: { days } }),
  },

  // PBS Management
  pbsMgmt: {
    test: (id) => api.get(`/pbs-mgmt/${id}/test`),
    listDatastores: (id) => api.get(`/pbs-mgmt/${id}/datastores`),
    listGroups: (id, ds) => api.get(`/pbs-mgmt/${id}/datastores/${ds}/groups`),
    listSnapshots: (id, ds, params) => api.get(`/pbs-mgmt/${id}/datastores/${ds}/snapshots`, { params }),
    verifySnapshot: (id, ds, data) => api.post(`/pbs-mgmt/${id}/datastores/${ds}/verify`, data),
    forgetSnapshot: (id, ds, params) => api.delete(`/pbs-mgmt/${id}/datastores/${ds}/snapshots`, { params }),
    pruneGroup: (id, ds, data) => api.post(`/pbs-mgmt/${id}/datastores/${ds}/prune`, data),
    listTasks: (id, params) => api.get(`/pbs-mgmt/${id}/tasks`, { params }),
    getTaskLog: (id, upid) => api.get(`/pbs-mgmt/${id}/tasks/${encodeURIComponent(upid)}/log`),
  },

  // PVE Firewall — IPSets, Aliases, Security Groups, cluster/node firewall
  pveFirewall: {
    // IPSets
    listIpsets: (h) => api.get(`/pve-firewall/${h}/ipsets`),
    createIpset: (h, data) => api.post(`/pve-firewall/${h}/ipsets`, data),
    deleteIpset: (h, name) => api.delete(`/pve-firewall/${h}/ipsets/${encodeURIComponent(name)}`),
    listIpsetEntries: (h, name) => api.get(`/pve-firewall/${h}/ipsets/${encodeURIComponent(name)}`),
    addIpsetEntry: (h, name, data) => api.post(`/pve-firewall/${h}/ipsets/${encodeURIComponent(name)}`, data),
    removeIpsetEntry: (h, name, cidr) => api.delete(`/pve-firewall/${h}/ipsets/${encodeURIComponent(name)}/${encodeURIComponent(cidr)}`),
    // Aliases
    listAliases: (h) => api.get(`/pve-firewall/${h}/aliases`),
    createAlias: (h, data) => api.post(`/pve-firewall/${h}/aliases`, data),
    updateAlias: (h, name, data) => api.put(`/pve-firewall/${h}/aliases/${encodeURIComponent(name)}`, data),
    deleteAlias: (h, name) => api.delete(`/pve-firewall/${h}/aliases/${encodeURIComponent(name)}`),
    // Cluster firewall rules
    updateClusterFirewallRule: (h, pos, data) => api.put(`/pve-firewall/${h}/cluster/firewall/rules/${pos}`, data),
    // Cluster firewall options
    getClusterFirewallOptions: (h) => api.get(`/pve-firewall/${h}/cluster/firewall/options`),
    setClusterFirewallOptions: (h, data) => api.put(`/pve-firewall/${h}/cluster/firewall/options`, data),
    // Security Groups
    listSecurityGroups: (h) => api.get(`/pve-firewall/${h}/security-groups`),
    createSecurityGroup: (h, data) => api.post(`/pve-firewall/${h}/security-groups`, data),
    deleteSecurityGroup: (h, name) => api.delete(`/pve-firewall/${h}/security-groups/${encodeURIComponent(name)}`),
    listSecurityGroupRules: (h, name) => api.get(`/pve-firewall/${h}/security-groups/${encodeURIComponent(name)}`),
    addSecurityGroupRule: (h, name, data) => api.post(`/pve-firewall/${h}/security-groups/${encodeURIComponent(name)}`, data),
    updateSecurityGroupRule: (h, name, pos, data) => api.put(`/pve-firewall/${h}/security-groups/${encodeURIComponent(name)}/${pos}`, data),
    deleteSecurityGroupRule: (h, name, pos) => api.delete(`/pve-firewall/${h}/security-groups/${encodeURIComponent(name)}/${pos}`),
    // Node firewall
    listNodeFirewallRules: (h, node) => api.get(`/pve-firewall/${h}/nodes/${node}/firewall/rules`),
    addNodeFirewallRule: (h, node, data) => api.post(`/pve-firewall/${h}/nodes/${node}/firewall/rules`, data),
    updateNodeFirewallRule: (h, node, pos, data) => api.put(`/pve-firewall/${h}/nodes/${node}/firewall/rules/${pos}`, data),
    deleteNodeFirewallRule: (h, node, pos) => api.delete(`/pve-firewall/${h}/nodes/${node}/firewall/rules/${pos}`),
    getNodeFirewallOptions: (h, node) => api.get(`/pve-firewall/${h}/nodes/${node}/firewall/options`),
    setNodeFirewallOptions: (h, node, data) => api.put(`/pve-firewall/${h}/nodes/${node}/firewall/options`, data),
  },

  // Integrations — Slack, PagerDuty, InfluxDB, OIDC
  integrations: {
    getAll: () => api.get('/integrations/all'),
    // Slack
    getSlack: () => api.get('/integrations/slack'),
    saveSlack: (data) => api.put('/integrations/slack', data),
    testSlack: () => api.post('/integrations/slack/test'),
    // PagerDuty
    getPagerDuty: () => api.get('/integrations/pagerduty'),
    savePagerDuty: (data) => api.put('/integrations/pagerduty', data),
    // InfluxDB
    getInfluxDB: () => api.get('/integrations/influxdb'),
    saveInfluxDB: (data) => api.put('/integrations/influxdb', data),
    // OIDC
    getOIDC: () => api.get('/integrations/oidc'),
    saveOIDC: (data) => api.put('/integrations/oidc', data),
  },

  // Notifications / Webhooks
  notifications: {
    // In-app notifications
    list: () => api.get('/notifications/in-app'),
    markRead: (data) => api.post('/notifications/in-app/mark-read', data),
    delete: (id) => api.delete(`/notifications/in-app/${id}`),
    deleteAll: () => api.delete('/notifications/in-app'),
    sendTest: () => api.post('/notifications/in-app/test'),
    // Notification settings
    getSettings: () => api.get('/notifications/settings'),
    updateSettings: (data) => api.put('/notifications/settings', data),
    // Webhooks
    listWebhooks: () => api.get('/notifications/webhooks'),
    createWebhook: (data) => api.post('/notifications/webhooks', data),
    updateWebhook: (id, data) => api.put(`/notifications/webhooks/${id}`, data),
    deleteWebhook: (id) => api.delete(`/notifications/webhooks/${id}`),
    testWebhook: (id) => api.post(`/notifications/webhooks/${id}/test`),
    getWebhookDeliveries: (id) => api.get(`/notifications/webhooks/${id}/deliveries`),
  },

  // Cluster Operations (/cluster/{host_id}/...)
  cluster: {
    // Tasks (cluster-wide, across all nodes)
    listTasks: (hostId, params) => api.get(`/cluster/${hostId}/tasks`, { params }),
    // Replication jobs
    listReplication: (hostId) => api.get(`/cluster/${hostId}/replication`),
    createReplication: (hostId, data) => api.post(`/cluster/${hostId}/replication`, data),
    updateReplication: (hostId, jobId, data) => api.put(`/cluster/${hostId}/replication/${encodeURIComponent(jobId)}`, data),
    deleteReplication: (hostId, jobId) => api.delete(`/cluster/${hostId}/replication/${encodeURIComponent(jobId)}`),
    forceReplication: (hostId, jobId) => api.post(`/cluster/${hostId}/replication/${encodeURIComponent(jobId)}/schedule_now`),
    // Node evacuation (migrate all VMs off node)
    evacuateNode: (hostId, node, data) => api.post(`/cluster/${hostId}/nodes/${node}/evacuate`, data || {}),
    // Cluster-wide event log
    getLog: (hostId, max) => api.get(`/cluster/${hostId}/log`, { params: { max } }),
    // Cluster config / join
    getClusterStatus: (hostId) => api.get(`/cluster/${hostId}/status`),
    getClusterConfig: (hostId) => api.get(`/cluster/${hostId}/config`),
    getJoinInfo: (hostId) => api.get(`/cluster/${hostId}/config/join`),
    joinCluster: (hostId, data) => api.post(`/cluster/${hostId}/config/join`, data),
    createCluster: (hostId, data) => api.post(`/cluster/${hostId}/config`, data),
    removeClusterNode: (hostId, node) => api.delete(`/cluster/${hostId}/config/nodes/${encodeURIComponent(node)}`),
  },

  // PVE Console — ticket endpoints (/pve-console/...)
  pveConsole: {
    getVmTicket: (hostId, node, vmid) => api.get(`/pve-console/ticket/${hostId}/${node}/${vmid}`),
    getLxcTicket: (hostId, node, ctid) => api.get(`/pve-console/lxc-ticket/${hostId}/${node}/${ctid}`),
    downloadSpice: (hostId, node, vmid) => api.get(`/pve-console/spice/${hostId}/${node}/${vmid}`, { responseType: 'text' }),
  },

  // Resource Pools (convenience namespace — delegates to pve-node pool endpoints)
  pools: {
    list: (hostId) => api.get(`/pve-node/${hostId}/pools`),
    get: (hostId, poolid) => api.get(`/pve-node/${hostId}/pools/${encodeURIComponent(poolid)}`),
    create: (hostId, data) => api.post(`/pve-node/${hostId}/pools`, data),
    update: (hostId, poolid, data) => api.put(`/pve-node/${hostId}/pools/${encodeURIComponent(poolid)}`, data),
    delete: (hostId, poolid) => api.delete(`/pve-node/${hostId}/pools/${encodeURIComponent(poolid)}`),
  },

  // Storage Management
  storage: {
    // Cluster-wide storage definitions (via pve-node router)
    list: (hostId) => api.get(`/pve-node/${hostId}/storage`),
    create: (hostId, data) => api.post(`/pve-node/${hostId}/storage`, data),
    update: (hostId, storageId, data) => api.put(`/pve-node/${hostId}/storage/${encodeURIComponent(storageId)}`, data),
    // wipe=true adds ?destroy=1 to also wipe data when deleting storage
    delete: (hostId, storageId, wipe = false) => api.delete(`/pve-node/${hostId}/storage/${encodeURIComponent(storageId)}`, { params: wipe ? { destroy: 1 } : {} }),
    // Browse storage content on a specific node
    browse: (hostId, node, storageId, params) => api.get(`/pve-node/${hostId}/nodes/${node}/storage/${encodeURIComponent(storageId)}/content`, { params }),
    // ZFS pool management
    getZfsPools: (hostId, node) => api.get(`/pve-node/${hostId}/nodes/${node}/disks/zfs`),
    createZfsPool: (hostId, node, data) => api.post(`/pve-node/${hostId}/nodes/${node}/disks/zfs`, data),
    getZfsPool: (hostId, node, name) => api.get(`/pve-node/${hostId}/nodes/${node}/disks/zfs/${encodeURIComponent(name)}`),
    scrubZfsPool: (hostId, node, name) => api.post(`/pve-node/${hostId}/nodes/${node}/disks/zfs/${encodeURIComponent(name)}/scrub`),
    // Ceph management
    getCephStatus: (hostId, node) => api.get(`/pve-node/${hostId}/nodes/${node}/ceph/status`),
    getCephOsds: (hostId, node) => api.get(`/pve-node/${hostId}/nodes/${node}/ceph/osd`),
    getCephMons: (hostId, node) => api.get(`/pve-node/${hostId}/nodes/${node}/ceph/mon`),
    getCephPools: (hostId, node) => api.get(`/pve-node/${hostId}/nodes/${node}/ceph/pools`),
    createCephPool: (hostId, node, data) => api.post(`/pve-node/${hostId}/nodes/${node}/ceph/pools`, data),
    deleteCephPool: (hostId, node, pool) => api.delete(`/pve-node/${hostId}/nodes/${node}/ceph/pools/${encodeURIComponent(pool)}`),
    cephOsdAction: (hostId, node, osdId, action) => api.post(`/pve-node/${hostId}/nodes/${node}/ceph/osd/${osdId}/${action}`),
  },

  // VM Tags — Proxmox native tags (semicolon-separated in VM config)
  vmTags: {
    // Cross-host tag listing (optionally filtered to one host)
    listAllCrossHost: (hostId) => api.get('/pve-vm/tags', { params: hostId ? { host_id: hostId } : {} }),
    // Bulk add/remove tags across multiple VMs
    bulkTag: (data) => api.post('/pve-vm/bulk-tag', data),
    // Per-host tag listing (legacy, host-scoped)
    listAll: (hostId) => api.get(`/pve-vm/${hostId}/tags`),
    getByTag: (hostId, tag) => api.get(`/pve-vm/${hostId}/tags/${encodeURIComponent(tag)}/vms`),
    addTag: (hostId, node, vmid, tag) => api.post(`/pve-vm/${hostId}/${node}/${vmid}/tags`, { tag }),
    removeTag: (hostId, node, vmid, tag) => api.delete(`/pve-vm/${hostId}/${node}/${vmid}/tags/${encodeURIComponent(tag)}`),
    // Client-side helper: read-modify-write tags via config endpoint
    patchTags: async (hostId, node, vmid, addTags = [], removeTags = []) => {
      const cfgRes = await api.get(`/pve-vm/${hostId}/${node}/${vmid}/config`)
      const current = cfgRes.data?.tags || ''
      let arr = current ? current.split(';').map(t => t.trim()).filter(Boolean) : []
      addTags.forEach(t => { if (!arr.includes(t)) arr.push(t) })
      removeTags.forEach(t => { arr = arr.filter(x => x !== t) })
      return api.put(`/pve-vm/${hostId}/${node}/${vmid}/config`, { tags: arr.join(';') })
    },
  },

  // VM Groups — local logical groups stored in Depl0y DB
  vmGroups: {
    list: () => api.get('/vm-groups/'),
    get: (id) => api.get(`/vm-groups/${id}`),
    create: (data) => api.post('/vm-groups/', data),
    update: (id, data) => api.put(`/vm-groups/${id}`, data),
    delete: (id) => api.delete(`/vm-groups/${id}`),
    addVm: (id, vmid) => api.post(`/vm-groups/${id}/add-vm`, { vmid }),
    removeVm: (id, vmid) => api.delete(`/vm-groups/${id}/remove-vm/${encodeURIComponent(vmid)}`),
  },

  // Bulk VM Operations
  vmBulk: {
    // Power management
    bulkPower: (data) => api.post('/pve-vm/bulk/power', data),
    // Rolling restart (sequential, with configurable delay)
    bulkRollingRestart: (data) => api.post('/pve-vm/bulk/rolling-restart', data),
    // Snapshots
    bulkSnapshot: (data) => api.post('/pve-vm/bulk/snapshot', data),
    bulkDeleteSnapshots: (data) => api.post('/pve-vm/bulk/delete-snapshots', data),
    // Config update (supports dry_run flag)
    bulkConfig: (data) => api.post('/pve-vm/bulk/config', data),
    bulkConfigPreview: (data) => api.post('/pve-vm/bulk/config/preview', data),
    // Migration
    bulkMigrate: (data) => api.post('/pve-vm/bulk/migrate', data),
    // Orphaned disks
    getOrphanedDisks: (hostId) => api.get(`/pve-vm/orphaned-disks/${hostId}`),
    // Automation scripts — existing
    scriptCleanupSnapshots: (data) => api.post('/pve-vm/scripts/cleanup-snapshots', data),
    scriptTagCompliance: (data) => api.post('/pve-vm/scripts/tag-compliance', data),
    scriptResourceAudit: (data) => api.post('/pve-vm/scripts/resource-audit', data),
    // Automation scripts — new
    scriptNightlySnapshot: (data) => api.post('/pve-vm/scripts/nightly-snapshot', data),
    scriptVmHealthCheck: (data) => api.post('/pve-vm/scripts/vm-health-check', data),
    scriptResourceRebalancer: (data) => api.post('/pve-vm/scripts/resource-rebalancer', data),
    scriptBulkTagUpdater: (data) => api.post('/pve-vm/scripts/bulk-tag-updater', data),
    scriptConfigStandardizer: (data) => api.post('/pve-vm/scripts/config-standardizer', data),
  },

  // Task Queue — Depl0y-tracked Proxmox async operations
  tasks: {
    getRunning: () => api.get('/tasks/running'),
    getHistory: (params) => api.get('/tasks/history', { params }),
    getStatus: (hostId, node, upid) => api.get(`/tasks/${hostId}/${node}/${encodeURIComponent(upid)}/status`),
    getLog: (hostId, node, upid) => api.get(`/tasks/${hostId}/${node}/${encodeURIComponent(upid)}/log`),
    stop: (hostId, node, upid) => api.delete(`/tasks/${hostId}/${node}/${encodeURIComponent(upid)}`),
  },

  // Alerts — proactive monitoring & alert rules
  alerts: {
    getActive: () => api.get('/alerts/active'),
    dismiss: (id) => api.post(`/alerts/${id}/dismiss`),
    dismissAll: () => api.post('/alerts/dismiss-all'),
    acknowledgeEvent: (eventId) => api.post(`/alerts/events/${eventId}/acknowledge`),
    getHistory: (params) => api.get('/alerts/history', { params }),
    getSparkline: (days = 7) => api.get('/alerts/history/sparkline', { params: { days } }),
    listRules: () => api.get('/alerts/rules'),
    createRule: (data) => api.post('/alerts/rules', data),
    updateRule: (id, data) => api.put(`/alerts/rules/${id}`, data),
    deleteRule: (id) => api.delete(`/alerts/rules/${id}`),
    toggleRule: (id) => api.post(`/alerts/rules/${id}/toggle`),
    evaluate: () => api.post('/alerts/evaluate'),
    listVmMutes: () => api.get('/alerts/vm-mutes'),
    addVmMute: (host_id, vmid) => api.post('/alerts/vm-mutes', { host_id, vmid }),
    removeVmMute: (host_id, vmid) => api.delete(`/alerts/vm-mutes/${host_id}/${vmid}`),
  },

  // Analysis / Recommendations
  analysis: {
    getRecommendations: (params) => api.get('/analysis/recommendations', { params }),
    getSummary: () => api.get('/analysis/summary'),
    dismiss: (id) => api.post(`/analysis/recommendations/${id}/dismiss`),
    dismissAll: (category) => api.post('/analysis/recommendations/dismiss-all', null, { params: category ? { category } : {} }),
    run: () => api.post('/analysis/run'),
  },

  // PVE Access Control — dedicated /pve-access router (users, groups, roles, ACL)
  pveAccess: {
    // Users
    listUsers:  (h, params) => api.get(`/pve-access/${h}/users`, { params }),
    createUser: (h, data)   => api.post(`/pve-access/${h}/users`, data),
    updateUser: (h, uid, data) => api.put(`/pve-access/${h}/users/${encodeURIComponent(uid)}`, data),
    deleteUser: (h, uid)    => api.delete(`/pve-access/${h}/users/${encodeURIComponent(uid)}`),
    // User tokens
    listTokens:  (h, uid)            => api.get(`/pve-access/${h}/users/${encodeURIComponent(uid)}/tokens`),
    createToken: (h, uid, tid, data) => api.post(`/pve-access/${h}/users/${encodeURIComponent(uid)}/tokens/${tid}`, data),
    deleteToken: (h, uid, tid)       => api.delete(`/pve-access/${h}/users/${encodeURIComponent(uid)}/tokens/${tid}`),
    // Groups
    listGroups:  (h)           => api.get(`/pve-access/${h}/groups`),
    getGroup:    (h, gid)      => api.get(`/pve-access/${h}/groups/${encodeURIComponent(gid)}`),
    createGroup: (h, data)     => api.post(`/pve-access/${h}/groups`, data),
    updateGroup: (h, gid, data) => api.put(`/pve-access/${h}/groups/${encodeURIComponent(gid)}`, data),
    deleteGroup: (h, gid)      => api.delete(`/pve-access/${h}/groups/${encodeURIComponent(gid)}`),
    // Roles
    listRoles:  (h)           => api.get(`/pve-access/${h}/roles`),
    createRole: (h, data)     => api.post(`/pve-access/${h}/roles`, data),
    updateRole: (h, rid, data) => api.put(`/pve-access/${h}/roles/${encodeURIComponent(rid)}`, data),
    deleteRole: (h, rid)      => api.delete(`/pve-access/${h}/roles/${encodeURIComponent(rid)}`),
    // ACL
    listAcl:   (h)       => api.get(`/pve-access/${h}/acl`),
    updateAcl: (h, data) => api.put(`/pve-access/${h}/acl`, data),
  },

  // SDN — Software-Defined Networking
  sdn: {
    listVnets: (hostId) => api.get(`/sdn/${hostId}/vnets`),
    createVnet: (hostId, data) => api.post(`/sdn/${hostId}/vnets`, data),
    updateVnet: (hostId, vnet, data) => api.put(`/sdn/${hostId}/vnets/${encodeURIComponent(vnet)}`, data),
    deleteVnet: (hostId, vnet) => api.delete(`/sdn/${hostId}/vnets/${encodeURIComponent(vnet)}`),
    listZones: (hostId) => api.get(`/sdn/${hostId}/zones`),
    createZone: (hostId, data) => api.post(`/sdn/${hostId}/zones`, data),
    updateZone: (hostId, zone, data) => api.put(`/sdn/${hostId}/zones/${encodeURIComponent(zone)}`, data),
    deleteZone: (hostId, zone) => api.delete(`/sdn/${hostId}/zones/${encodeURIComponent(zone)}`),
    listSubnets: (hostId, vnet) => api.get(`/sdn/${hostId}/subnets`, { params: vnet ? { vnet } : {} }),
    createSubnet: (hostId, data) => api.post(`/sdn/${hostId}/subnets`, data),
    deleteSubnet: (hostId, subnet, vnet) => api.delete(`/sdn/${hostId}/subnets/${encodeURIComponent(subnet)}`, { params: { vnet } }),
    apply: (hostId) => api.post(`/sdn/${hostId}/apply`),
  },
}
