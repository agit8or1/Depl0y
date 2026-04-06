<template>
  <div class="cluster-stats">
    <SkeletonLoader v-if="loading" type="stat" :count="4" />
    <div v-else class="stats-grid">
      <router-link to="/vms" class="stat-tile">
        <span class="tile-icon">🖥️</span>
        <span class="tile-val">{{ data.vm_count }}</span>
        <span class="tile-label">Total VMs</span>
      </router-link>
      <router-link to="/vms?status=running" class="stat-tile stat-green">
        <span class="tile-icon">▶️</span>
        <span class="tile-val">{{ data.running_vms }}</span>
        <span class="tile-label">Running</span>
      </router-link>
      <router-link to="/proxmox" class="stat-tile">
        <span class="tile-icon">🖧</span>
        <span class="tile-val">{{ data.node_count }}</span>
        <span class="tile-label">Nodes</span>
      </router-link>
      <router-link to="/storage-management" class="stat-tile stat-amber">
        <span class="tile-icon">💾</span>
        <span class="tile-val">{{ data.storage_used_gb }}<span class="tile-unit">GB</span></span>
        <span class="tile-label">Storage Used</span>
      </router-link>
      <router-link to="/audit-log" class="stat-tile" :class="data.failed_tasks_24h > 0 ? 'stat-red' : 'stat-green'">
        <span class="tile-icon">{{ data.failed_tasks_24h > 0 ? '⚠️' : '✅' }}</span>
        <span class="tile-val">{{ data.failed_tasks_24h }}</span>
        <span class="tile-label">Failed (24h)</span>
      </router-link>
      <router-link to="/user-management" class="stat-tile">
        <span class="tile-icon">👤</span>
        <span class="tile-val">{{ data.active_users }}</span>
        <span class="tile-label">Active Users</span>
      </router-link>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

export default {
  name: 'ClusterStatsWidget',
  components: { SkeletonLoader },
  setup() {
    const loading = ref(true)
    const data = ref({
      vm_count: 0, running_vms: 0, node_count: 0,
      storage_used_gb: 0, failed_tasks_24h: 0, active_users: 0
    })
    let timer = null

    const fetch = async () => {
      try {
        const res = await api.dashboard.getSummary()
        data.value = res.data
      } catch (e) {
        // fallback to basic stats
        try {
          const [statsRes, resRes] = await Promise.all([
            api.dashboard.getStats(),
            api.dashboard.getResources()
          ])
          data.value = {
            vm_count: statsRes.data.total_vms || 0,
            running_vms: statsRes.data.running_vms || 0,
            node_count: statsRes.data.total_nodes || 0,
            storage_used_gb: resRes.data.used_disk_gb || 0,
            failed_tasks_24h: 0,
            active_users: 0
          }
        } catch (e2) {}
      } finally {
        loading.value = false
      }
    }

    onMounted(() => {
      fetch()
      timer = setInterval(fetch, 30000)
    })
    onUnmounted(() => clearInterval(timer))

    return { loading, data }
  }
}
</script>

<style scoped>
.cluster-stats {
  height: 100%;
}

.stats-loading {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}

.stat-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  padding: 0.6rem 0.4rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  text-decoration: none;
  transition: all 0.15s;
  background: var(--background);
  cursor: default;
}

a.stat-tile {
  cursor: pointer;
}

a.stat-tile:hover {
  border-color: var(--primary-color);
  transform: translateY(-1px);
}

.stat-green { border-left: 3px solid #22c55e; }
.stat-red   { border-left: 3px solid #ef4444; }
.stat-amber { border-left: 3px solid #f59e0b; }

.tile-icon {
  font-size: 1.1rem;
}

.tile-val {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.tile-unit {
  font-size: 0.65rem;
  font-weight: 400;
  color: var(--text-secondary);
  margin-left: 1px;
}

.tile-label {
  font-size: 0.65rem;
  color: var(--text-secondary);
  text-align: center;
  white-space: nowrap;
}
</style>
