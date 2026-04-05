<template>
  <div class="top-vms">
    <div v-if="loading" class="wl">Loading...</div>
    <div v-else-if="vms.length === 0" class="we">No running VMs found.</div>
    <div v-else class="vm-list">
      <div v-for="vm in vms" :key="`${vm.hostId}-${vm.vmid}`" class="vm-row" @click="go(vm)">
        <div class="vm-info">
          <span class="vm-id">{{ vm.vmid }}</span>
          <span class="vm-name">{{ vm.name || '(no name)' }}</span>
          <span class="vm-node">{{ vm.node }}</span>
        </div>
        <div class="vm-bars">
          <div class="bar-row">
            <span class="bar-lbl">CPU</span>
            <div class="bar-track"><div class="bar-fill bar-cpu" :style="{ width: Math.min(100,(vm.cpu||0)*100).toFixed(1)+'%' }"></div></div>
            <span class="bar-pct">{{ ((vm.cpu||0)*100).toFixed(1) }}%</span>
          </div>
          <div class="bar-row">
            <span class="bar-lbl">Mem</span>
            <div class="bar-track"><div class="bar-fill bar-mem" :style="{ width: vm.memPct.toFixed(1)+'%' }"></div></div>
            <span class="bar-pct">{{ vm.memPct.toFixed(1) }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

export default {
  name: 'TopVMsWidget',
  setup() {
    const router = useRouter()
    const loading = ref(true)
    const vms = ref([])
    let timer = null

    const fetch = async () => {
      try {
        const hostsRes = await api.proxmox.listHosts()
        const hosts = (hostsRes.data || []).filter(h => h.is_active)
        const results = await Promise.allSettled(hosts.map(h => api.pveNode.clusterResources(h.id)))
        const acc = []
        results.forEach((result, idx) => {
          const host = hosts[idx]
          if (result.status === 'fulfilled') {
            ;(result.value.data || []).forEach(item => {
              if (item.type === 'qemu' && item.status === 'running') {
                acc.push({
                  hostId: host.id, node: item.node, vmid: item.vmid, name: item.name,
                  cpu: item.cpu || 0, mem: item.mem || 0, maxmem: item.maxmem || 0,
                  memPct: item.maxmem > 0 ? (item.mem / item.maxmem) * 100 : 0
                })
              }
            })
          }
        })
        vms.value = acc.sort((a, b) => (b.cpu || 0) - (a.cpu || 0)).slice(0, 5)
      } catch (e) {}
      finally { loading.value = false }
    }

    const go = (vm) => router.push(`/proxmox/${vm.hostId}/nodes/${vm.node}/vms/${vm.vmid}`)

    onMounted(() => { fetch(); timer = setInterval(fetch, 30000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, vms, go }
  }
}
</script>

<style scoped>
.top-vms { height: 100%; }
.wl, .we { font-size: 0.8rem; color: var(--text-secondary); }
.vm-list { display: flex; flex-direction: column; gap: 0.4rem; }
.vm-row { display: flex; align-items: center; gap: 0.6rem; padding: 0.4rem 0.45rem; border-radius: 0.375rem; cursor: pointer; transition: background 0.1s; }
.vm-row:hover { background: var(--background); }
.vm-info { display: flex; align-items: center; gap: 0.3rem; flex: 0 0 40%; min-width: 0; }
.vm-id   { font-size: 0.7rem; font-weight: 700; color: var(--text-secondary); flex-shrink: 0; }
.vm-name { font-size: 0.78rem; font-weight: 600; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vm-node { font-size: 0.65rem; color: var(--text-secondary); flex-shrink: 0; }
.vm-bars { flex: 1; display: flex; flex-direction: column; gap: 0.18rem; }
.bar-row { display: flex; align-items: center; gap: 0.3rem; }
.bar-lbl { font-size: 0.62rem; color: var(--text-secondary); width: 2rem; flex-shrink: 0; }
.bar-track { flex: 1; height: 0.3rem; background: var(--border-color); border-radius: 9999px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 9999px; transition: width 0.3s; }
.bar-cpu { background: var(--primary-color); }
.bar-mem { background: #10b981; }
.bar-pct { font-size: 0.62rem; color: var(--text-secondary); width: 2.5rem; text-align: right; flex-shrink: 0; }
</style>
