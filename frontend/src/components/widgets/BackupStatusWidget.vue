<template>
  <div class="backup-status">
    <div v-if="loading" class="wl">Loading backup status...</div>
    <div v-else-if="items.length === 0" class="we">No backup data found. Configure PBS or backup schedules.</div>
    <div v-else class="bk-list">
      <div v-for="item in items" :key="item.vm" class="bk-row">
        <div class="bk-vm">
          <span class="bk-vmid">{{ item.vm }}</span>
          <span class="bk-when">{{ item.when }}</span>
        </div>
        <span :class="['bk-chip', `bk-${item.status}`]">{{ item.status }}</span>
      </div>
    </div>
    <div v-if="!loading" class="bk-footer">
      <span class="bk-note">Backup data from Proxmox task logs</span>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

export default {
  name: 'BackupStatusWidget',
  setup() {
    const loading = ref(true)
    const items = ref([])
    let timer = null

    const fetch = async () => {
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = (hostsRes.data || []).filter(h => h.is_active)
        if (!hosts.length) { loading.value = false; return }

        const resourceResults = await Promise.allSettled(
          hosts.map(h => api.pveNode.clusterResources(h.id))
        )

        const nodeTargets = []
        resourceResults.forEach((result, idx) => {
          const host = hosts[idx]
          if (result.status === 'fulfilled') {
            const nodes = (result.value.data || []).filter(i => i.type === 'node').map(i => i.node)
            nodes.forEach(n => nodeTargets.push({ hostId: host.id, node: n }))
          }
        })

        // Fetch tasks filtered to backup type
        const taskResults = await Promise.allSettled(
          nodeTargets.map(t => api.pveNode.listTasks(t.hostId, t.node, { limit: 50, typefilter: 'vzdump' }))
        )

        // Build a map: vmid -> latest backup task
        const vmMap = {}
        taskResults.forEach((result) => {
          if (result.status === 'fulfilled') {
            ;(result.value.data || []).forEach(task => {
              // Extract vmid from upid or id field if available
              const vmid = task.id || task.vmid || extractVmidFromUpid(task.upid)
              if (!vmid) return
              if (!vmMap[vmid] || (task.starttime > vmMap[vmid].starttime)) {
                vmMap[vmid] = task
              }
            })
          }
        })

        items.value = Object.entries(vmMap).map(([vm, task]) => ({
          vm,
          status: taskStatusToChip(task.status),
          when: task.starttime ? new Date(task.starttime * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'
        })).slice(0, 10)
      } catch (e) {}
      loading.value = false
    }

    const extractVmidFromUpid = (upid) => {
      if (!upid) return null
      // UPID format: UPID:node:pid:starttime:type:id:...
      const parts = upid.split(':')
      return parts[5] || null
    }

    const taskStatusToChip = (status) => {
      if (!status) return 'running'
      const s = status.toLowerCase()
      if (s === 'ok') return 'pass'
      if (s.includes('error') || s.includes('fail')) return 'fail'
      return 'running'
    }

    onMounted(() => { fetch(); timer = setInterval(fetch, 120000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, items }
  }
}
</script>

<style scoped>
.backup-status { height: 100%; display: flex; flex-direction: column; gap: 0.4rem; }
.wl, .we { font-size: 0.8rem; color: var(--text-secondary); }
.bk-list { flex: 1; display: flex; flex-direction: column; gap: 0.3rem; overflow-y: auto; max-height: 280px; }
.bk-row { display: flex; align-items: center; justify-content: space-between; padding: 0.35rem 0.5rem; border-radius: 0.375rem; border: 1px solid var(--border-color); font-size: 0.8rem; gap: 0.5rem; }
.bk-vm { display: flex; flex-direction: column; gap: 0.05rem; min-width: 0; }
.bk-vmid { font-weight: 600; color: var(--text-primary); }
.bk-when { font-size: 0.68rem; color: var(--text-secondary); }
.bk-chip { font-size: 0.62rem; font-weight: 700; text-transform: uppercase; padding: 0.1rem 0.4rem; border-radius: 0.2rem; flex-shrink: 0; }
.bk-pass    { background: rgba(34,197,94,0.15); color: #22c55e; }
.bk-fail    { background: rgba(239,68,68,0.12); color: #ef4444; }
.bk-running { background: rgba(59,130,246,0.15); color: #3b82f6; }
.bk-footer { font-size: 0.68rem; color: var(--text-secondary); padding-top: 0.25rem; }
.bk-note { opacity: 0.7; }
</style>
