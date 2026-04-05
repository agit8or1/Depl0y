<template>
  <div class="quick-actions-widget">
    <div class="qa-search-wrap">
      <div class="qa-search-row">
        <span class="qa-search-icon">🔍</span>
        <input
          v-model="searchQuery"
          type="text"
          class="qa-search-input"
          placeholder="Search VMs by name or VMID..."
          @keyup.escape="searchQuery = ''"
        />
        <button v-if="searchQuery" class="qa-clear" @click="searchQuery = ''">×</button>
      </div>
      <div v-if="searchQuery.trim() && searchResults.length > 0" class="qa-results">
        <div
          v-for="vm in searchResults"
          :key="`${vm.hostId}-${vm.node}-${vm.vmid}`"
          class="qa-result-item"
          @click="goToVM(vm)"
        >
          <span class="qr-vmid">{{ vm.vmid }}</span>
          <span class="qr-name">{{ vm.name || '(no name)' }}</span>
          <span :class="['qr-status', vm.status === 'running' ? 'qs-run' : vm.status === 'stopped' ? 'qs-stop' : 'qs-other']">{{ vm.status }}</span>
          <span class="qr-node">{{ vm.node }}</span>
        </div>
      </div>
      <div v-else-if="searchQuery.trim() && searchResults.length === 0" class="qa-no-results">
        No VMs found matching "{{ searchQuery }}"
      </div>
    </div>

    <div class="qa-grid">
      <router-link v-for="action in actions" :key="action.to" :to="action.to" class="qa-btn">
        <span class="qa-icon">{{ action.icon }}</span>
        <div>
          <p class="qa-title">{{ action.title }}</p>
          <p class="qa-desc">{{ action.desc }}</p>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

export default {
  name: 'QuickActionsWidget',
  setup() {
    const router = useRouter()
    const searchQuery = ref('')
    const allVms = ref([])
    let timer = null

    const actions = [
      { to: '/deploy',    icon: '➕', title: 'Deploy VM',     desc: 'Create a new virtual machine' },
      { to: '/create-lxc', icon: '📦', title: 'Create LXC',  desc: 'Provision a new LXC container' },
      { to: '/images',   icon: '🖼️', title: 'Browse Images', desc: 'View and manage disk images' },
      { to: '/tasks',    icon: '📋', title: 'View Tasks',    desc: 'Monitor running and recent tasks' },
      { to: '/proxmox',  icon: '🌐', title: 'Manage Hosts',  desc: 'Configure Proxmox hosts' },
    ]

    const searchResults = computed(() => {
      const q = searchQuery.value.trim().toLowerCase()
      if (!q) return []
      return allVms.value.filter(vm =>
        (vm.name || '').toLowerCase().includes(q) || String(vm.vmid).includes(q)
      ).slice(0, 8)
    })

    const goToVM = (vm) => {
      searchQuery.value = ''
      router.push(`/proxmox/${vm.hostId}/nodes/${vm.node}/vms/${vm.vmid}`)
    }

    const loadVms = async () => {
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = (hostsRes.data || []).filter(h => h.is_active)
        const results = await Promise.allSettled(hosts.map(h => api.pveNode.clusterResources(h.id)))
        const acc = []
        results.forEach((result, idx) => {
          const host = hosts[idx]
          if (result.status === 'fulfilled') {
            ;(result.value.data || []).forEach(item => {
              if (item.type === 'qemu') {
                acc.push({ hostId: host.id, node: item.node, vmid: item.vmid, name: item.name, status: item.status || 'unknown' })
              }
            })
          }
        })
        allVms.value = acc
      } catch (e) {}
    }

    onMounted(() => { loadVms(); timer = setInterval(loadVms, 60000) })
    onUnmounted(() => clearInterval(timer))

    return { searchQuery, searchResults, actions, goToVM }
  }
}
</script>

<style scoped>
.quick-actions-widget { display: flex; flex-direction: column; gap: 0.6rem; height: 100%; }

.qa-search-wrap { border-bottom: 1px solid var(--border-color); padding-bottom: 0.6rem; }
.qa-search-row {
  display: flex; align-items: center; gap: 0.4rem;
  background: var(--background); border: 1px solid var(--border-color);
  border-radius: 0.375rem; padding: 0.3rem 0.5rem; transition: border-color 0.15s;
}
.qa-search-row:focus-within { border-color: var(--primary-color); }
.qa-search-icon { font-size: 0.85rem; opacity: 0.6; flex-shrink: 0; }
.qa-search-input { flex: 1; border: none; background: transparent; color: var(--text-primary); font-size: 0.82rem; outline: none; min-width: 0; }
.qa-search-input::placeholder { color: var(--text-secondary); }
.qa-clear { background: none; border: none; color: var(--text-secondary); font-size: 1.1rem; cursor: pointer; padding: 0; }
.qa-clear:hover { color: var(--text-primary); }

.qa-results {
  margin-top: 0.35rem; border: 1px solid var(--border-color); border-radius: 0.375rem;
  overflow: hidden; max-height: 200px; overflow-y: auto;
}

.qa-result-item {
  display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0.55rem;
  cursor: pointer; font-size: 0.8rem; transition: background 0.1s;
  border-bottom: 1px solid var(--border-color);
}
.qa-result-item:last-child { border-bottom: none; }
.qa-result-item:hover { background: var(--background); }

.qr-vmid { font-weight: 700; color: var(--text-secondary); font-size: 0.72rem; min-width: 2.5rem; }
.qr-name { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.qr-status { font-size: 0.65rem; font-weight: 600; padding: 0.1rem 0.3rem; border-radius: 9999px; white-space: nowrap; }
.qs-run  { background: rgba(34,197,94,0.15);  color: #22c55e; }
.qs-stop { background: rgba(239,68,68,0.12);  color: #ef4444; }
.qs-other{ background: rgba(100,116,139,0.15);color: var(--text-secondary); }
.qr-node { font-size: 0.7rem; color: var(--text-secondary); white-space: nowrap; }

.qa-no-results { font-size: 0.78rem; color: var(--text-secondary); padding: 0.3rem 0.1rem; margin-top: 0.3rem; }

.qa-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.4rem;
}

.qa-btn {
  display: flex; align-items: center; gap: 0.45rem; padding: 0.45rem 0.5rem;
  border: 1px solid var(--border-color); border-radius: 0.375rem; text-decoration: none;
  transition: all 0.15s;
}
.qa-btn:hover { background: var(--background); border-color: var(--primary-color); }
.qa-icon { font-size: 1.15rem; flex-shrink: 0; }
.qa-title { font-weight: 600; color: var(--text-primary); margin: 0; font-size: 0.82rem; }
.qa-desc  { font-size: 0.68rem; color: var(--text-secondary); margin: 0; }
</style>
