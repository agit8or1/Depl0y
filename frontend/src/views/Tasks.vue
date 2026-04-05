<template>
  <div class="tasks-page">
    <div class="page-header mb-2">
      <div>
        <h2>Task Log</h2>
        <p class="text-muted">Proxmox task history across nodes</p>
      </div>
    </div>

    <!-- Filters -->
    <div class="card mb-2">
      <div class="card-body">
        <div class="filters-row">
          <div class="form-group">
            <label class="form-label">Host</label>
            <select v-model="selectedHostId" @change="onHostChange" class="form-control">
              <option value="">All Hosts</option>
              <option v-for="h in hosts" :key="h.id" :value="h.id">{{ h.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Node</label>
            <select v-model="selectedNode" @change="onFilterChange" class="form-control" :disabled="!selectedHostId">
              <option value="">All Nodes</option>
              <option v-for="n in nodes" :key="n.node_name" :value="n.node_name">{{ n.node_name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Type</label>
            <input v-model="filterType" @input="onFilterChange" class="form-control" placeholder="qmstart, qmstop..." />
          </div>
          <div class="form-group">
            <label class="form-label">VMID</label>
            <input v-model.number="filterVmid" @input="onFilterChange" type="number" class="form-control" placeholder="100" />
          </div>
          <div class="form-group form-group--btn">
            <button @click="loadTasks(true)" class="btn btn-outline btn-sm">Refresh</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Table -->
    <div class="card">
      <div v-if="loading" class="loading-spinner"></div>
      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Start Time</th>
              <th>Node</th>
              <th>VMID</th>
              <th>Type</th>
              <th>Status</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="tasks.length === 0">
              <td colspan="6" class="text-muted text-center">No tasks found</td>
            </tr>
            <template v-for="task in tasks" :key="task._key">
              <tr class="clickable-row" @click="toggleLog(task)">
                <td class="text-sm">{{ task.starttime ? new Date(task.starttime * 1000).toLocaleString() : '—' }}</td>
                <td class="text-sm">{{ task.node }}</td>
                <td class="text-sm">{{ task.id || '—' }}</td>
                <td class="text-sm">{{ task.type }}</td>
                <td>
                  <span :class="statusBadgeClass(task.status)">{{ task.status || 'running' }}</span>
                </td>
                <td class="text-sm text-muted">{{ task.upid }}</td>
              </tr>
              <tr v-if="task._expanded" :key="task._key + '-log'">
                <td colspan="6" class="task-log-cell">
                  <div v-if="task._loadingLog" class="text-muted text-sm" style="padding:0.5rem 1rem">Loading log...</div>
                  <pre v-else class="task-log">{{ (task._log || []).map(l => l.t).join('\n') || 'No log output' }}</pre>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <div v-if="!loading && hasMore" class="text-center" style="padding:1rem">
        <button @click="loadMore" class="btn btn-outline" :disabled="loadingMore">
          {{ loadingMore ? 'Loading...' : 'Load More' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'

const PAGE_SIZE = 50

export default {
  name: 'Tasks',
  setup() {
    const route = useRoute()

    const hosts = ref([])
    const nodes = ref([])
    const tasks = ref([])
    const loading = ref(false)
    const loadingMore = ref(false)
    const hasMore = ref(false)
    const page = ref(0)

    const selectedHostId = ref(route.params.hostId || '')
    const selectedNode = ref('')
    const filterType = ref('')
    const filterVmid = ref(null)

    const loadHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = res.data || []
      } catch (e) {
        console.warn('Failed to load hosts', e)
      }
    }

    const loadNodes = async () => {
      nodes.value = []
      if (!selectedHostId.value) return
      try {
        const res = await api.proxmox.listNodes(selectedHostId.value)
        nodes.value = res.data || []
      } catch (e) {
        console.warn('Failed to load nodes', e)
      }
    }

    const buildParams = (start = 0) => {
      const p = { limit: PAGE_SIZE, start }
      if (filterType.value) p.typefilter = filterType.value
      if (filterVmid.value) p.vmid = filterVmid.value
      return p
    }

    const loadTasksForHostNode = async (hostId, nodeName, start = 0) => {
      const res = await api.pveNode.tasks(hostId, nodeName, buildParams(start))
      return (res.data || []).map((t, i) => ({
        ...t,
        _key: `${hostId}-${nodeName}-${t.upid || i}`,
        _hostId: hostId,
        _node: nodeName,
        _expanded: false,
        _log: null,
        _loadingLog: false,
      }))
    }

    const loadTasks = async (reset = true) => {
      if (reset) {
        page.value = 0
        tasks.value = []
      }
      loading.value = true
      try {
        let collected = []

        if (selectedHostId.value && selectedNode.value) {
          collected = await loadTasksForHostNode(selectedHostId.value, selectedNode.value, page.value * PAGE_SIZE)
        } else if (selectedHostId.value) {
          const nodeList = nodes.value.length ? nodes.value : await api.proxmox.listNodes(selectedHostId.value).then(r => r.data || [])
          const results = await Promise.all(
            nodeList.map(n => loadTasksForHostNode(selectedHostId.value, n.node_name, 0).catch(() => []))
          )
          collected = results.flat().sort((a, b) => (b.starttime || 0) - (a.starttime || 0)).slice(0, PAGE_SIZE)
        } else {
          const results = await Promise.all(
            hosts.value.map(async h => {
              try {
                const nRes = await api.proxmox.listNodes(h.id)
                const nodeList = nRes.data || []
                const taskResults = await Promise.all(
                  nodeList.map(n => loadTasksForHostNode(h.id, n.node_name, 0).catch(() => []))
                )
                return taskResults.flat()
              } catch { return [] }
            })
          )
          collected = results.flat().sort((a, b) => (b.starttime || 0) - (a.starttime || 0)).slice(0, PAGE_SIZE)
        }

        if (reset) {
          tasks.value = collected
        } else {
          tasks.value = [...tasks.value, ...collected]
        }
        hasMore.value = collected.length === PAGE_SIZE
      } catch (e) {
        console.error('Failed to load tasks', e)
      } finally {
        loading.value = false
      }
    }

    const loadMore = async () => {
      page.value++
      loadingMore.value = true
      try {
        if (selectedHostId.value && selectedNode.value) {
          const more = await loadTasksForHostNode(selectedHostId.value, selectedNode.value, page.value * PAGE_SIZE)
          tasks.value = [...tasks.value, ...more]
          hasMore.value = more.length === PAGE_SIZE
        }
      } catch (e) {
        console.error(e)
      } finally {
        loadingMore.value = false
      }
    }

    const onHostChange = async () => {
      selectedNode.value = ''
      await loadNodes()
      await loadTasks(true)
    }

    const onFilterChange = () => {
      loadTasks(true)
    }

    const toggleLog = async (task) => {
      task._expanded = !task._expanded
      if (task._expanded && !task._log) {
        task._loadingLog = true
        try {
          const res = await api.pveNode.taskLog(task._hostId, task._node || task.node, task.upid)
          task._log = res.data || []
        } catch (e) {
          task._log = [{ t: 'Failed to load log' }]
        } finally {
          task._loadingLog = false
        }
      }
    }

    const statusBadgeClass = (status) => {
      if (status === 'OK') return 'badge badge-success'
      if (!status || status === 'running') return 'badge badge-warning'
      return 'badge badge-danger'
    }

    onMounted(async () => {
      await loadHosts()
      if (selectedHostId.value) await loadNodes()
      await loadTasks(true)
    })

    return {
      hosts, nodes, tasks, loading, loadingMore, hasMore,
      selectedHostId, selectedNode, filterType, filterVmid,
      loadTasks, loadMore, onHostChange, onFilterChange,
      toggleLog, statusBadgeClass,
    }
  }
}
</script>

<style scoped>
.tasks-page {
  padding: 0;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.filters-row {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: flex-end;
}

.filters-row .form-group {
  flex: 1;
  min-width: 150px;
  margin-bottom: 0;
}

.form-group--btn {
  flex: 0 0 auto;
}

.table-container {
  overflow-x: auto;
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background: var(--bg-secondary);
}

.task-log-cell {
  padding: 0;
  background: #0f1419;
}

.task-log {
  margin: 0;
  padding: 0.75rem 1rem;
  font-size: 0.8rem;
  color: #9ca3af;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.card-body {
  padding: 1rem;
}

.mb-2 { margin-bottom: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-muted); }
.text-center { text-align: center; }

.badge-warning {
  background-color: #d97706;
  color: #fff;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}
</style>
