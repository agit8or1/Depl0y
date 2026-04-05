<template>
  <div class="containers-page">
    <div class="page-header mb-2">
      <div>
        <h2>LXC Containers</h2>
        <p class="text-muted">All LXC containers across configured Proxmox hosts</p>
      </div>
      <button @click="loadAll" class="btn btn-outline btn-sm">Refresh</button>
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <div v-else class="card">
      <div class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>VMID</th>
              <th>Name</th>
              <th>Host / Node</th>
              <th>Status</th>
              <th>CPU</th>
              <th>RAM</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="containers.length === 0">
              <td colspan="7" class="text-muted text-center">No containers found. Make sure your Proxmox hosts are configured and polled.</td>
            </tr>
            <tr v-for="ct in containers" :key="`${ct._hostId}-${ct._node}-${ct.vmid}`">
              <td>{{ ct.vmid }}</td>
              <td>
                <span class="clickable-name" @click="openDetail(ct)">{{ ct.name || `CT ${ct.vmid}` }}</span>
              </td>
              <td class="text-sm">{{ ct._hostName }} / {{ ct._node }}</td>
              <td>
                <span :class="ct.status === 'running' ? 'badge badge-success' : 'badge badge-danger'">
                  {{ ct.status }}
                </span>
              </td>
              <td>{{ ct.cpu != null ? (ct.cpu * 100).toFixed(1) + '%' : '—' }}</td>
              <td>{{ ct.maxmem ? formatBytes(ct.mem) + ' / ' + formatBytes(ct.maxmem) : '—' }}</td>
              <td>
                <div class="flex gap-1">
                  <button
                    v-if="ct.status !== 'running'"
                    @click="ctAction(ct, 'start')"
                    class="btn btn-success btn-sm"
                    :disabled="ct._actioning">
                    Start
                  </button>
                  <button
                    v-if="ct.status === 'running'"
                    @click="ctAction(ct, 'stop')"
                    class="btn btn-danger btn-sm"
                    :disabled="ct._actioning">
                    Stop
                  </button>
                  <button
                    v-if="ct.status === 'running'"
                    @click="openShell(ct)"
                    class="btn btn-outline btn-sm">
                    Shell
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Inline Container Detail Panel -->
    <div v-if="selectedCt" class="card mt-2">
      <div class="card-header">
        <h3>Container {{ selectedCt.vmid }} — {{ selectedCt.name }}</h3>
        <button @click="selectedCt = null" class="btn btn-outline btn-sm">Close</button>
      </div>
      <div v-if="loadingDetail" class="loading-spinner"></div>
      <div v-else-if="ctConfig" class="card-body">
        <div class="detail-grid">
          <div class="detail-item">
            <span class="detail-label">Hostname</span>
            <span class="detail-value">{{ ctConfig.hostname || '—' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">OS Template</span>
            <span class="detail-value">{{ ctConfig.ostemplate || '—' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Cores</span>
            <span class="detail-value">{{ ctConfig.cores || '—' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Memory</span>
            <span class="detail-value">{{ ctConfig.memory ? ctConfig.memory + ' MB' : '—' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Swap</span>
            <span class="detail-value">{{ ctConfig.swap != null ? ctConfig.swap + ' MB' : '—' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Root FS</span>
            <span class="detail-value">{{ ctConfig.rootfs || '—' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Network</span>
            <span class="detail-value">{{ ctConfig.net0 || '—' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Start at boot</span>
            <span class="detail-value">{{ ctConfig.onboot ? 'Yes' : 'No' }}</span>
          </div>
        </div>

        <div v-if="ctSnapshots.length > 0" class="mt-2">
          <h4 class="mb-1">Snapshots</h4>
          <div class="snapshot-list">
            <div v-for="snap in ctSnapshots" :key="snap.name" class="snapshot-item">
              <span class="snapshot-name">{{ snap.name }}</span>
              <span class="text-muted text-sm">{{ snap.snaptime ? new Date(snap.snaptime * 1000).toLocaleString() : '' }}</span>
              <span class="text-muted text-sm">{{ snap.description || '' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import { formatBytes } from '@/utils/proxmox'

export default {
  name: 'Containers',
  setup() {
    const toast = useToast()
    const containers = ref([])
    const loading = ref(true)
    const selectedCt = ref(null)
    const ctConfig = ref(null)
    const ctSnapshots = ref([])
    const loadingDetail = ref(false)

    const loadAll = async () => {
      loading.value = true
      containers.value = []
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = hostsRes.data || []

        const allCts = await Promise.all(
          hosts.map(async (host) => {
            try {
              const nodesRes = await api.proxmox.listNodes(host.id)
              const nodes = nodesRes.data || []
              const ctResults = await Promise.all(
                nodes.map(n =>
                  api.pveNode.containers(host.id, n.node_name)
                    .then(r => (r.data || []).map(ct => ({
                      ...ct,
                      _hostId: host.id,
                      _hostName: host.name,
                      _node: n.node_name,
                      _actioning: false,
                    })))
                    .catch(() => [])
                )
              )
              return ctResults.flat()
            } catch { return [] }
          })
        )

        containers.value = allCts.flat().sort((a, b) => a.vmid - b.vmid)
      } catch (e) {
        console.error('Failed to load containers', e)
      } finally {
        loading.value = false
      }
    }

    const ctAction = async (ct, action) => {
      ct._actioning = true
      try {
        await api.pveNode.ctAction(ct._hostId, ct._node, ct.vmid, action)
        toast.success(`Container ${action} initiated`)
        setTimeout(loadAll, 2000)
      } catch (e) {
        console.error(e)
      } finally {
        ct._actioning = false
      }
    }

    const openShell = (ct) => {
      window.open(`/proxmox/${ct._hostId}/nodes/${ct._node}/lxc/${ct.vmid}/console`, '_blank')
    }

    const openDetail = async (ct) => {
      if (selectedCt.value?.vmid === ct.vmid && selectedCt.value?._node === ct._node) {
        selectedCt.value = null
        return
      }
      selectedCt.value = ct
      ctConfig.value = null
      ctSnapshots.value = []
      loadingDetail.value = true
      try {
        const [configRes, snapRes] = await Promise.all([
          api.pveNode.ctConfig(ct._hostId, ct._node, ct.vmid),
          api.pveNode.ctSnapshots(ct._hostId, ct._node, ct.vmid).catch(() => ({ data: [] })),
        ])
        ctConfig.value = configRes.data
        ctSnapshots.value = (snapRes.data || []).filter(s => s.name !== 'current')
      } catch (e) {
        console.warn('Failed to load container detail', e)
      } finally {
        loadingDetail.value = false
      }
    }

    onMounted(loadAll)

    return {
      containers, loading, selectedCt, ctConfig, ctSnapshots, loadingDetail,
      formatBytes, loadAll, ctAction, openShell, openDetail,
    }
  }
}
</script>

<style scoped>
.containers-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.table-container {
  overflow-x: auto;
}

.clickable-name {
  cursor: pointer;
  color: var(--primary-color);
  text-decoration: underline;
}

.clickable-name:hover {
  color: var(--text-primary);
}

.card-body {
  padding: 1.5rem;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.detail-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.detail-value {
  font-size: 0.9rem;
  color: var(--text-primary);
  word-break: break-all;
}

.snapshot-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.snapshot-item {
  display: flex;
  gap: 1rem;
  align-items: center;
  padding: 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
}

.snapshot-name {
  font-weight: 600;
  min-width: 100px;
}

.flex { display: flex; }
.gap-1 { gap: 0.5rem; }
.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }
.mt-2 { margin-top: 1rem; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--text-muted); }
.text-center { text-align: center; }
</style>
