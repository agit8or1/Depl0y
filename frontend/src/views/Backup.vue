<template>
  <div class="backup-page">
    <div class="page-header mb-2">
      <h2>Backup Management</h2>
      <p class="text-muted">Manage vzdump backup schedules and run manual backups</p>
    </div>

    <!-- Host Selector -->
    <div class="card mb-2">
      <div class="card-header">
        <h3>Proxmox Host</h3>
      </div>
      <div class="card-body">
        <div class="form-group" style="max-width: 400px; margin: 0;">
          <label class="form-label">Select Host</label>
          <select v-model="selectedHostId" class="form-control" @change="onHostChange">
            <option value="">— Select a host —</option>
            <option v-for="host in hosts" :key="host.id" :value="host.id">
              {{ host.name }} ({{ host.hostname }})
            </option>
          </select>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="card">
      <div class="card-header" style="border-bottom: none; padding-bottom: 0;">
        <div class="tabs">
          <button
            v-for="tab in availableTabs"
            :key="tab"
            @click="activeTab = tab"
            :class="['tab-btn', activeTab === tab ? 'tab-active' : '']"
          >
            {{ tab }}
          </button>
        </div>
      </div>

      <!-- PBS Servers Tab -->
      <div v-if="activeTab === 'PBS Servers'" class="tab-content">
        <div class="tab-header">
          <h3>Proxmox Backup Servers</h3>
          <button @click="fetchPbsServers" class="btn btn-outline btn-sm" :disabled="loadingPbs">
            {{ loadingPbs ? 'Refreshing...' : 'Refresh' }}
          </button>
        </div>

        <div v-if="loadingPbs" class="loading-spinner"></div>

        <div v-else-if="pbsServers.length === 0" class="text-center text-muted" style="padding: 2rem;">
          <p>No PBS servers configured.</p>
        </div>

        <div v-else class="pbs-list">
          <div v-for="pbs in pbsServers" :key="pbs.id" class="pbs-card">
            <div class="pbs-card-header">
              <div class="pbs-card-title">
                <strong>{{ pbs.name }}</strong>
                <span class="text-muted text-sm">{{ pbs.hostname }}</span>
              </div>
              <div class="pbs-card-badges">
                <span v-if="pbsStatus[pbs.id] === 'ok'" class="badge badge-success">Connected</span>
                <span v-else-if="pbsStatus[pbs.id] === 'error'" class="badge badge-danger">Failed</span>
                <span v-else-if="pbsStatus[pbs.id] === 'testing'" class="badge badge-info">Testing...</span>
                <span v-else class="badge badge-secondary">Unknown</span>
                <span v-if="pbs.datastore_count !== undefined" class="badge badge-info">
                  {{ pbs.datastore_count }} datastore{{ pbs.datastore_count !== 1 ? 's' : '' }}
                </span>
              </div>
              <div class="pbs-card-actions">
                <button
                  @click="testPbsConnection(pbs.id)"
                  class="btn btn-outline btn-sm"
                  :disabled="pbsStatus[pbs.id] === 'testing'"
                >
                  Test Connection
                </button>
                <button
                  @click="toggleDatastores(pbs.id)"
                  class="btn btn-outline btn-sm"
                >
                  {{ expandedPbs === pbs.id ? 'Hide Datastores' : 'View Datastores' }}
                </button>
              </div>
            </div>

            <!-- Datastores expand section -->
            <div v-if="expandedPbs === pbs.id" class="pbs-datastores">
              <div v-if="loadingDatastores[pbs.id]" class="loading-spinner" style="margin: 1rem 0;"></div>
              <div v-else-if="pbsDatastores[pbs.id] && pbsDatastores[pbs.id].length === 0" class="text-muted text-sm" style="padding: 1rem 0;">
                No datastores found.
              </div>
              <div v-else-if="pbsDatastores[pbs.id]" class="table-container" style="margin-top: 0.75rem;">
                <table class="table table-sm">
                  <thead>
                    <tr>
                      <th>Datastore</th>
                      <th>Path</th>
                      <th>Total</th>
                      <th>Used</th>
                      <th>Available</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="ds in pbsDatastores[pbs.id]" :key="ds.store || ds.name">
                      <td><strong>{{ ds.store || ds.name }}</strong></td>
                      <td class="text-sm text-muted">{{ ds.path || '—' }}</td>
                      <td>{{ formatBytes(ds.total) }}</td>
                      <td>{{ formatBytes(ds.used) }}</td>
                      <td>{{ formatBytes(ds.avail) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Schedules Tab -->
      <div v-if="activeTab === 'Schedules'" class="tab-content">
        <div v-if="!selectedHostId" class="text-center text-muted" style="padding: 2rem;">
          <p>Select a Proxmox host above to manage backup schedules.</p>
        </div>
        <template v-else>
          <div class="tab-header">
            <h3>Backup Schedules</h3>
            <button @click="showAddScheduleModal = true" class="btn btn-primary">+ Add Schedule</button>
          </div>

          <div v-if="loadingSchedules" class="loading-spinner"></div>

          <div v-else-if="schedules.length === 0" class="text-center text-muted" style="padding: 2rem;">
            <p>No backup schedules configured.</p>
          </div>

          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Enabled</th>
                  <th>Schedule</th>
                  <th>VMs</th>
                  <th>Storage</th>
                  <th>Mode</th>
                  <th>Keep Last</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sched in schedules" :key="sched.id">
                  <td><strong>{{ sched.id }}</strong></td>
                  <td>
                    <span :class="['badge', sched.enabled == 1 ? 'badge-success' : 'badge-danger']">
                      {{ sched.enabled == 1 ? 'Enabled' : 'Disabled' }}
                    </span>
                  </td>
                  <td><code>{{ sched.schedule || sched.dow + ' ' + sched.starttime }}</code></td>
                  <td class="text-sm">{{ sched.vmid || 'all' }}</td>
                  <td>{{ sched.storage || '—' }}</td>
                  <td>
                    <span class="badge badge-info">{{ sched.mode || 'snapshot' }}</span>
                  </td>
                  <td>{{ sched['keep-last'] || sched.maxfiles || '—' }}</td>
                  <td class="actions-cell">
                    <button
                      @click="runScheduleNow(sched)"
                      class="btn btn-outline btn-sm"
                      :disabled="runningSchedule === sched.id"
                      title="Run this backup job immediately"
                    >
                      {{ runningSchedule === sched.id ? 'Starting...' : 'Run Now' }}
                    </button>
                    <button @click="deleteSchedule(sched.id)" class="btn btn-danger btn-sm">Delete</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Run Now: Node selector modal -->
          <div v-if="showRunNowModal" class="modal" @click="showRunNowModal = false">
            <div class="modal-content" @click.stop style="max-width: 400px;">
              <div class="modal-header">
                <h3>Run Backup Now</h3>
                <button @click="showRunNowModal = false" class="btn-close">×</button>
              </div>
              <div class="modal-body">
                <p class="text-sm text-muted" style="margin-bottom: 1rem;">
                  Select the node to run schedule <strong>{{ pendingRunSchedule?.id }}</strong> on.
                </p>
                <div class="form-group">
                  <label class="form-label">Node</label>
                  <select v-model="runNowNode" class="form-control">
                    <option value="">— Select node —</option>
                    <option v-for="node in nodes" :key="node.node || node.name" :value="node.node || node.name">
                      {{ node.node || node.name }}
                    </option>
                  </select>
                </div>
                <div class="flex gap-1 mt-2">
                  <button
                    @click="confirmRunNow"
                    class="btn btn-primary"
                    :disabled="!runNowNode || runningSchedule === pendingRunSchedule?.id"
                  >
                    Run Now
                  </button>
                  <button @click="showRunNowModal = false" class="btn btn-outline">Cancel</button>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Run Backup Now Tab -->
      <div v-if="activeTab === 'Run Backup Now'" class="tab-content">
        <div v-if="!selectedHostId" class="text-center text-muted" style="padding: 2rem;">
          <p>Select a Proxmox host above to run a manual backup.</p>
        </div>
        <template v-else>
          <div class="tab-header">
            <h3>Manual Backup</h3>
          </div>

          <div class="backup-form">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Node</label>
                <select v-model="manualBackup.node" class="form-control" @change="onNodeChange">
                  <option value="">— Select node —</option>
                  <option v-for="node in nodes" :key="node.node || node.name" :value="node.node || node.name">
                    {{ node.node || node.name }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Virtual Machine</label>
                <select v-model="manualBackup.vmid" class="form-control">
                  <option value="">— Select VM —</option>
                  <option v-for="vm in nodeVMs" :key="vm.vmid" :value="vm.vmid">
                    {{ vm.vmid }} — {{ vm.name }} ({{ vm.type }})
                  </option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Storage</label>
                <select v-model="manualBackup.storage" class="form-control">
                  <option value="">— Select storage —</option>
                  <option v-for="s in storages" :key="s.storage" :value="s.storage">
                    {{ s.storage }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Mode</label>
                <select v-model="manualBackup.mode" class="form-control">
                  <option value="snapshot">Snapshot</option>
                  <option value="suspend">Suspend</option>
                  <option value="stop">Stop</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Compress</label>
              <select v-model="manualBackup.compress" class="form-control" style="max-width: 200px;">
                <option value="lzo">LZO (fast)</option>
                <option value="gzip">Gzip</option>
                <option value="zstd">Zstd (recommended)</option>
                <option value="0">None</option>
              </select>
            </div>

            <button @click="startBackup" class="btn btn-primary" :disabled="startingBackup || !manualBackup.vmid || !manualBackup.storage">
              {{ startingBackup ? 'Starting...' : 'Start Backup' }}
            </button>

            <!-- Task status -->
            <div v-if="backupTask" class="task-status">
              <h4>Backup Task</h4>
              <div class="task-info">
                <div class="task-upid">
                  <span class="info-label">UPID:</span>
                  <code>{{ backupTask.upid }}</code>
                </div>
                <div class="task-state">
                  <span class="info-label">Status:</span>
                  <span :class="['badge', getTaskBadge(taskStatus?.status)]">
                    {{ taskStatus?.status || 'running' }}
                  </span>
                </div>
                <div v-if="taskStatus?.exitstatus" class="task-exit">
                  <span class="info-label">Exit:</span>
                  <span :class="taskStatus.exitstatus === 'OK' ? 'text-success' : 'text-danger'">
                    {{ taskStatus.exitstatus }}
                  </span>
                </div>
              </div>
              <div v-if="taskLog" class="task-log">
                <pre>{{ taskLog }}</pre>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Add Schedule Modal -->
    <div v-if="showAddScheduleModal" class="modal" @click="showAddScheduleModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Backup Schedule</h3>
          <button @click="showAddScheduleModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="addSchedule" class="modal-body">
          <div class="form-group">
            <label class="form-label">Schedule <span class="text-muted text-sm">(cron expression)</span></label>
            <input v-model="newSchedule.schedule" class="form-control" placeholder="0 2 * * *" required />
            <p class="text-xs text-muted mt-1">e.g. "0 2 * * *" = every day at 2am</p>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">VMs (vmid)</label>
              <input v-model="newSchedule.vmid" class="form-control" placeholder="all or 100,101,102" />
            </div>
            <div class="form-group">
              <label class="form-label">Storage</label>
              <select v-model="newSchedule.storage" class="form-control">
                <option value="">— Select storage —</option>
                <option v-for="s in storages" :key="s.storage" :value="s.storage">{{ s.storage }}</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Mode</label>
              <select v-model="newSchedule.mode" class="form-control">
                <option value="snapshot">Snapshot</option>
                <option value="suspend">Suspend</option>
                <option value="stop">Stop</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Keep Last (retention)</label>
              <input v-model.number="newSchedule['keep-last']" type="number" min="1" class="form-control" placeholder="3" />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              <input type="checkbox" v-model="newSchedule.enabled" :true-value="1" :false-value="0" />
              Enabled
            </label>
          </div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingSchedule">
              {{ savingSchedule ? 'Adding...' : 'Add Schedule' }}
            </button>
            <button type="button" @click="showAddScheduleModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'Backup',
  setup() {
    const toast = useToast()
    const hosts = ref([])
    const selectedHostId = ref('')
    const activeTab = ref('PBS Servers')
    const schedules = ref([])
    const loadingSchedules = ref(false)
    const showAddScheduleModal = ref(false)
    const savingSchedule = ref(false)
    const nodes = ref([])
    const nodeVMs = ref([])
    const storages = ref([])
    const startingBackup = ref(false)
    const backupTask = ref(null)
    const taskStatus = ref(null)
    const taskLog = ref(null)
    let pollTimer = null

    // PBS state
    const pbsServers = ref([])
    const loadingPbs = ref(false)
    const pbsStatus = ref({})       // id -> 'ok' | 'error' | 'testing'
    const expandedPbs = ref(null)
    const pbsDatastores = ref({})   // id -> array
    const loadingDatastores = ref({})

    // Run Now state
    const runningSchedule = ref(null)
    const showRunNowModal = ref(false)
    const pendingRunSchedule = ref(null)
    const runNowNode = ref('')

    const availableTabs = computed(() => {
      const tabs = ['PBS Servers', 'Schedules', 'Run Backup Now']
      return tabs
    })

    const newSchedule = ref({
      schedule: '',
      vmid: 'all',
      storage: '',
      mode: 'snapshot',
      'keep-last': 3,
      enabled: 1
    })

    const manualBackup = ref({
      node: '',
      vmid: '',
      storage: '',
      mode: 'snapshot',
      compress: 'zstd'
    })

    const fetchHosts = async () => {
      try {
        const response = await api.proxmox.listHosts()
        hosts.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch hosts:', error)
      }
    }

    const onHostChange = async () => {
      if (!selectedHostId.value) return
      schedules.value = []
      nodes.value = []
      nodeVMs.value = []
      storages.value = []
      manualBackup.value.node = ''
      manualBackup.value.vmid = ''
      manualBackup.value.storage = ''
      await Promise.all([fetchSchedules(), fetchNodes(), fetchStorages()])
    }

    const fetchSchedules = async () => {
      loadingSchedules.value = true
      try {
        const response = await api.pveNode.listBackupSchedules(selectedHostId.value)
        schedules.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch schedules:', error)
        toast.error('Failed to load schedules')
      } finally {
        loadingSchedules.value = false
      }
    }

    const fetchNodes = async () => {
      try {
        const response = await api.proxmox.listNodes(selectedHostId.value)
        nodes.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch nodes:', error)
      }
    }

    const fetchStorages = async () => {
      try {
        const response = await api.pveNode.listStorage(selectedHostId.value, nodes.value[0]?.node || nodes.value[0]?.name || '')
        storages.value = (response.data || []).filter(s => s.content && s.content.includes('backup'))
      } catch (error) {
        console.error('Failed to fetch storages:', error)
      }
    }

    const onNodeChange = async () => {
      if (!manualBackup.value.node) { nodeVMs.value = []; return }
      try {
        const [qemuRes, lxcRes] = await Promise.all([
          api.pveNode.nodeVms(selectedHostId.value, manualBackup.value.node).catch(() => ({ data: [] })),
          api.pveNode.listContainers(selectedHostId.value, manualBackup.value.node).catch(() => ({ data: [] }))
        ])
        const qemus = (qemuRes.data || []).map(v => ({ ...v, type: 'vm' }))
        const lxcs = (lxcRes.data || []).map(v => ({ ...v, type: 'ct' }))
        nodeVMs.value = [...qemus, ...lxcs]
      } catch (error) {
        console.error('Failed to fetch node VMs:', error)
      }
    }

    const addSchedule = async () => {
      savingSchedule.value = true
      try {
        const payload = { ...newSchedule.value }
        if (!payload.vmid || payload.vmid === 'all') delete payload.vmid
        await api.pveNode.createBackupSchedule(selectedHostId.value, payload)
        toast.success('Backup schedule added')
        showAddScheduleModal.value = false
        newSchedule.value = { schedule: '', vmid: 'all', storage: '', mode: 'snapshot', 'keep-last': 3, enabled: 1 }
        await fetchSchedules()
      } catch (error) {
        console.error('Failed to add schedule:', error)
        toast.error('Failed to add schedule')
      } finally {
        savingSchedule.value = false
      }
    }

    const deleteSchedule = async (id) => {
      if (!confirm(`Delete backup schedule "${id}"?`)) return
      try {
        await api.pveNode.deleteBackupSchedule(selectedHostId.value, id)
        toast.success('Schedule deleted')
        await fetchSchedules()
      } catch (error) {
        console.error('Failed to delete schedule:', error)
        toast.error('Failed to delete schedule')
      }
    }

    // Run Now: open node-picker modal if nodes are loaded, else pick first available
    const runScheduleNow = (sched) => {
      if (nodes.value.length === 0) {
        toast.error('No nodes loaded. Select a host first.')
        return
      }
      pendingRunSchedule.value = sched
      runNowNode.value = nodes.value.length === 1 ? (nodes.value[0].node || nodes.value[0].name) : ''
      showRunNowModal.value = true
    }

    const confirmRunNow = async () => {
      const sched = pendingRunSchedule.value
      if (!sched || !runNowNode.value) return
      showRunNowModal.value = false
      runningSchedule.value = sched.id
      try {
        const payload = {
          mode: sched.mode || 'snapshot',
          compress: 'zstd',
        }
        if (sched.vmid) payload.vmid = sched.vmid
        if (sched.storage) payload.storage = sched.storage
        await api.pveNode.runBackup(selectedHostId.value, runNowNode.value, payload)
        toast.success(`Backup job "${sched.id}" started on node ${runNowNode.value}`)
      } catch (error) {
        console.error('Failed to run backup schedule:', error)
        toast.error('Failed to start backup job')
      } finally {
        runningSchedule.value = null
        pendingRunSchedule.value = null
        runNowNode.value = ''
      }
    }

    const startBackup = async () => {
      startingBackup.value = true
      backupTask.value = null
      taskStatus.value = null
      taskLog.value = null
      if (pollTimer) clearInterval(pollTimer)
      try {
        const response = await api.pveNode.runBackup(
          selectedHostId.value,
          manualBackup.value.node,
          {
            vmid: manualBackup.value.vmid,
            storage: manualBackup.value.storage,
            mode: manualBackup.value.mode,
            compress: manualBackup.value.compress
          }
        )
        backupTask.value = { upid: response.data.data || response.data }
        toast.success('Backup started')
        pollTaskStatus()
      } catch (error) {
        console.error('Failed to start backup:', error)
        toast.error('Failed to start backup')
      } finally {
        startingBackup.value = false
      }
    }

    const pollTaskStatus = () => {
      if (!backupTask.value?.upid) return
      pollTimer = setInterval(async () => {
        try {
          const response = await api.pveNode.taskStatus(
            selectedHostId.value,
            manualBackup.value.node,
            encodeURIComponent(backupTask.value.upid)
          )
          taskStatus.value = response.data
          if (taskStatus.value.status === 'stopped') {
            clearInterval(pollTimer)
            try {
              const logRes = await api.pveNode.taskLog(
                selectedHostId.value,
                manualBackup.value.node,
                encodeURIComponent(backupTask.value.upid)
              )
              taskLog.value = (logRes.data || []).map(l => l.t).join('\n')
            } catch {}
          }
        } catch (error) {
          console.error('Failed to poll task:', error)
        }
      }, 3000)
    }

    const getTaskBadge = (status) => {
      if (status === 'stopped') return 'badge-success'
      if (status === 'running') return 'badge-info'
      return 'badge-warning'
    }

    // PBS methods
    const fetchPbsServers = async () => {
      loadingPbs.value = true
      try {
        const response = await api.pbs.list()
        pbsServers.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch PBS servers:', error)
        toast.error('Failed to load PBS servers')
      } finally {
        loadingPbs.value = false
      }
    }

    const testPbsConnection = async (pbsId) => {
      pbsStatus.value = { ...pbsStatus.value, [pbsId]: 'testing' }
      try {
        await api.pbsMgmt.test(pbsId)
        pbsStatus.value = { ...pbsStatus.value, [pbsId]: 'ok' }
        toast.success('PBS connection successful')
      } catch (error) {
        console.error('PBS connection test failed:', error)
        pbsStatus.value = { ...pbsStatus.value, [pbsId]: 'error' }
        toast.error('PBS connection failed')
      }
    }

    const toggleDatastores = async (pbsId) => {
      if (expandedPbs.value === pbsId) {
        expandedPbs.value = null
        return
      }
      expandedPbs.value = pbsId
      if (pbsDatastores.value[pbsId]) return  // already loaded
      loadingDatastores.value = { ...loadingDatastores.value, [pbsId]: true }
      try {
        const response = await api.pbsMgmt.listDatastores(pbsId)
        pbsDatastores.value = { ...pbsDatastores.value, [pbsId]: response.data || [] }
      } catch (error) {
        console.error('Failed to fetch PBS datastores:', error)
        toast.error('Failed to load datastores')
        pbsDatastores.value = { ...pbsDatastores.value, [pbsId]: [] }
      } finally {
        loadingDatastores.value = { ...loadingDatastores.value, [pbsId]: false }
      }
    }

    const formatBytes = (bytes) => {
      if (bytes === undefined || bytes === null) return '—'
      if (bytes === 0) return '0 B'
      const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
      const i = Math.floor(Math.log(bytes) / Math.log(1024))
      return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
    }

    onMounted(() => {
      fetchHosts()
      fetchPbsServers()
    })

    return {
      hosts,
      selectedHostId,
      activeTab,
      availableTabs,
      schedules,
      loadingSchedules,
      showAddScheduleModal,
      savingSchedule,
      newSchedule,
      nodes,
      nodeVMs,
      storages,
      manualBackup,
      startingBackup,
      backupTask,
      taskStatus,
      taskLog,
      // PBS
      pbsServers,
      loadingPbs,
      pbsStatus,
      expandedPbs,
      pbsDatastores,
      loadingDatastores,
      // Run Now
      runningSchedule,
      showRunNowModal,
      pendingRunSchedule,
      runNowNode,
      // Methods
      onHostChange,
      onNodeChange,
      addSchedule,
      deleteSchedule,
      runScheduleNow,
      confirmRunNow,
      startBackup,
      getTaskBadge,
      fetchPbsServers,
      testPbsConnection,
      toggleDatastores,
      formatBytes,
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.card-body {
  padding: 1.5rem;
}

.mb-2 {
  margin-bottom: 1rem;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.75rem 1.5rem;
  cursor: pointer;
  font-size: 0.95rem;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-active {
  color: var(--primary-color) !important;
  border-bottom-color: var(--primary-color) !important;
  font-weight: 600;
}

.tab-content {
  padding: 1.5rem;
}

.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.tab-header h3 {
  margin: 0;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.backup-form {
  max-width: 700px;
}

.task-status {
  margin-top: 1.5rem;
  padding: 1.5rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
}

.task-status h4 {
  margin: 0 0 1rem 0;
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.task-upid {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.task-upid code {
  font-size: 0.8rem;
  background: #1e293b;
  color: #e2e8f0;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  word-break: break-all;
}

.task-state, .task-exit {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.info-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.task-log {
  background: #1e1e1e;
  border-radius: 0.375rem;
  overflow: hidden;
  max-height: 300px;
  overflow-y: auto;
}

.task-log pre {
  margin: 0;
  padding: 1rem;
  color: #d4d4d4;
  font-family: monospace;
  font-size: 0.8rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.text-success { color: #059669; }
.text-danger { color: #ef4444; }

/* PBS Servers */
.pbs-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.pbs-card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
}

.pbs-card-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: var(--background);
  flex-wrap: wrap;
}

.pbs-card-title {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
  min-width: 150px;
}

.pbs-card-badges {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.pbs-card-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-shrink: 0;
}

.pbs-datastores {
  padding: 0 1.25rem 1.25rem;
  border-top: 1px solid var(--border-color);
}

.table-sm th,
.table-sm td {
  padding: 0.4rem 0.75rem;
  font-size: 0.875rem;
}

.actions-cell {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

/* Modals */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 0.5rem;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 { margin: 0; }

.btn-close {
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body {
  padding: 1.5rem;
}

.badge-secondary {
  background-color: var(--border-color);
  color: var(--text-secondary);
}
</style>
