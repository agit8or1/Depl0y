import { defineStore } from 'pinia'
import api from '@/services/api'

const CACHE_TTL = 30_000 // 30 seconds

export const useClusterStore = defineStore('cluster', {
  state: () => ({
    resources: [],
    hosts: [],
    lastFetch: null,
    lastHostsFetch: null,
    loading: false
  }),

  getters: {
    vms: (state) => state.resources.filter(r => r.type === 'qemu'),
    nodes: (state) => state.resources.filter(r => r.type === 'node'),
    lxc: (state) => state.resources.filter(r => r.type === 'lxc'),
    allSearchable: (state) => state.resources
  },

  actions: {
    async fetchHosts(force = false) {
      const now = Date.now()
      if (!force && this.lastHostsFetch && now - this.lastHostsFetch < CACHE_TTL) {
        return this.hosts
      }
      try {
        const res = await api.proxmox.listHosts()
        const data = res.data
        this.hosts = Array.isArray(data) ? data : (data.items || data.results || [])
        this.lastHostsFetch = now
      } catch (err) {
        console.warn('[ClusterStore] Failed to fetch hosts:', err)
      }
      return this.hosts
    },

    async fetchResources(force = false) {
      const now = Date.now()
      if (!force && this.lastFetch && now - this.lastFetch < CACHE_TTL) return

      this.loading = true
      try {
        const hosts = await this.fetchHosts(force)
        const allItems = []

        await Promise.allSettled(
          hosts.map(async (host) => {
            const hostId = host.id
            const hostName = host.name || host.hostname || `Host ${hostId}`
            try {
              const res = await api.pveNode.clusterResources(hostId)
              const list = Array.isArray(res.data)
                ? res.data
                : (res.data?.items || res.data?.data || [])
              for (const item of list) {
                allItems.push({
                  ...item,
                  _hostId: hostId,
                  _hostName: hostName
                })
              }
            } catch {
              // skip unreachable host
            }
          })
        )

        this.resources = allItems
        this.lastFetch = now
      } catch (err) {
        console.warn('[ClusterStore] fetchResources error:', err)
      } finally {
        this.loading = false
      }
    }
  }
})
