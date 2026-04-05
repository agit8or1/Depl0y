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

    if (import.meta.env.DEV) {
      console.error('API Error Details:', {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        headers: error.response?.headers
      })
    }

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
    getAgentIP: (node, vmid) => api.get(`/vms/control/${node}/${vmid}/ip`)
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
    getInfo: () => api.get('/system/info')
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
    // SSH-based (host OS)
    runIdracSshUpdate: (id) => api.post(`/pbs/${id}/idrac/ssh/update`),
    testIdracSsh: (id) => api.get(`/pbs/${id}/idrac/ssh/test`),
    getIdracSshHardware: (id) => api.get(`/pbs/${id}/idrac/ssh/hardware`),
    getIdracSshNetwork: (id) => api.get(`/pbs/${id}/idrac/ssh/network`),
    getIdracSshFirmware: (id) => api.get(`/pbs/${id}/idrac/ssh/firmware`),
    getIdracSshLogs: (id, limit = 100) => api.get(`/pbs/${id}/idrac/ssh/logs`, { params: { limit } }),
  }
}
