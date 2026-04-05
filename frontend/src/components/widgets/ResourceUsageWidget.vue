<template>
  <div class="resource-usage">
    <SkeletonLoader v-if="loading" type="card" :count="2" />
    <div v-else>
      <div v-for="bar in bars" :key="bar.label" class="res-item">
        <div class="res-header">
          <span class="res-label">{{ bar.label }}</span>
          <span class="res-val">{{ bar.display }}</span>
        </div>
        <div class="res-track">
          <div
            class="res-fill"
            :class="bar.pct > 85 ? 'fill-danger' : bar.pct > 70 ? 'fill-warn' : 'fill-ok'"
            :style="{ width: bar.pct + '%' }"
          ></div>
        </div>
        <span class="res-pct">{{ bar.pct }}%</span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

export default {
  name: 'ResourceUsageWidget',
  components: { SkeletonLoader },
  setup() {
    const loading = ref(true)
    const bars = ref([])
    let timer = null

    const fetch = async () => {
      try {
        const res = await api.dashboard.getResources()
        const r = res.data
        bars.value = [
          {
            label: 'CPU Cores',
            pct: r.total_cpu_cores > 0 ? Math.round((r.used_cpu_cores / r.total_cpu_cores) * 100) : 0,
            display: `${r.used_cpu_cores} / ${r.total_cpu_cores}`
          },
          {
            label: 'Memory',
            pct: r.total_memory_gb > 0 ? Math.round((r.used_memory_gb / r.total_memory_gb) * 100) : 0,
            display: `${r.used_memory_gb}GB / ${r.total_memory_gb}GB`
          },
          {
            label: 'Disk',
            pct: r.total_disk_gb > 0 ? Math.round((r.used_disk_gb / r.total_disk_gb) * 100) : 0,
            display: `${r.used_disk_gb}GB / ${r.total_disk_gb}GB`
          }
        ]
      } catch (e) {}
      finally { loading.value = false }
    }

    onMounted(() => { fetch(); timer = setInterval(fetch, 30000) })
    onUnmounted(() => clearInterval(timer))

    return { loading, bars }
  }
}
</script>

<style scoped>
.resource-usage { height: 100%; }
.wl { font-size: 0.8rem; color: var(--text-secondary); }

.res-item {
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto;
  gap: 0.15rem 0.5rem;
  margin-bottom: 0.75rem;
}
.res-item:last-child { margin-bottom: 0; }

.res-header {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.res-label { font-size: 0.75rem; font-weight: 500; color: var(--text-secondary); }
.res-val   { font-size: 0.7rem;  color: var(--text-secondary); }

.res-track {
  grid-column: 1;
  height: 0.375rem;
  background: var(--border-color);
  border-radius: 9999px;
  overflow: hidden;
  align-self: center;
}

.res-fill {
  height: 100%;
  border-radius: 9999px;
  transition: width 0.3s ease;
}

.fill-ok     { background: linear-gradient(90deg, var(--primary-color), var(--secondary-color, #22c55e)); }
.fill-warn   { background: #f59e0b; }
.fill-danger { background: #ef4444; }

.res-pct {
  grid-column: 2;
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--text-primary);
  align-self: center;
}
</style>
