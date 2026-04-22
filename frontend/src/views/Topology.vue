<template>
  <div class="topology-page">
    <div class="page-header">
      <div class="page-header-row">
        <div>
          <h2>Network / Server Topology</h2>
          <p class="text-muted">
            Live graph of Proxmox hosts, nodes, VMs, storage, bridges, PBS servers and iDRAC.
          </p>
        </div>
        <div class="header-actions">
          <span v-if="generatedAt" class="text-muted text-sm">
            Updated {{ formatTime(generatedAt) }}
          </span>
          <button class="btn btn-outline" :disabled="loading" @click="fit">Fit to screen</button>
          <button class="btn btn-outline" :disabled="loading || !graph" @click="exportPNG">Export PNG</button>
          <button class="btn btn-outline" :disabled="loading || !graph" @click="exportSVG">Export SVG</button>
          <button class="btn btn-outline" :disabled="loading || !graph" @click="exportDrawio">Export draw.io</button>
          <button class="btn btn-primary" :disabled="loading" @click="refresh(true)">
            <span v-if="!loading">Refresh</span>
            <span v-else>Loading…</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ errorMsg }}</div>

    <div class="topo-body">
      <!-- ── Left toolbar: filters + legend ── -->
      <aside class="topo-sidebar card">
        <h3 class="topo-sec-title">View</h3>
        <div class="view-toggle">
          <button :class="['vt-btn', viewMode === 'infrastructure' ? 'vt-btn--active' : '']" @click="setViewMode('infrastructure')">Infrastructure</button>
          <button :class="['vt-btn', viewMode === 'network' ? 'vt-btn--active' : '']" @click="setViewMode('network')">Network</button>
          <button :class="['vt-btn', viewMode === 'combined' ? 'vt-btn--active' : '']" @click="setViewMode('combined')">Combined</button>
        </div>

        <h3 class="topo-sec-title mt-2">Filters</h3>
        <label class="topo-check">
          <input type="checkbox" v-model="filters.include_stopped" @change="refresh(false)" />
          <span>Show stopped VMs</span>
        </label>
        <label class="topo-check">
          <input type="checkbox" v-model="filters.include_lxc" @change="refresh(false)" />
          <span>Show LXC containers</span>
        </label>
        <label class="topo-check">
          <input type="checkbox" v-model="filters.include_storage" @change="refresh(false)" />
          <span>Show storage pools</span>
        </label>
        <label class="topo-check">
          <input type="checkbox" v-model="filters.include_bridges" @change="refresh(false)" />
          <span>Show network bridges</span>
        </label>
        <label class="topo-check">
          <input type="checkbox" v-model="filters.include_bmc" @change="refresh(false)" />
          <span>Show BMC / iDRAC</span>
        </label>
        <label class="topo-check">
          <input type="checkbox" v-model="filters.include_pbs" @change="refresh(false)" />
          <span>Show PBS servers</span>
        </label>
        <label class="topo-check">
          <input type="checkbox" v-model="filters.include_sync" @change="refresh(false)" />
          <span>Show sync edges</span>
        </label>

        <h3 class="topo-sec-title mt-2">Legend</h3>
        <div class="legend-row" v-for="l in legend" :key="l.type">
          <span class="legend-swatch" :style="{ background: l.color, borderColor: l.border, borderRadius: l.radius }"></span>
          <span class="legend-label">{{ l.label }}</span>
        </div>

        <h3 class="topo-sec-title mt-2">Stats</h3>
        <div v-if="graph" class="stats">
          <div>Nodes: <b>{{ graph.nodes.length }}</b></div>
          <div>Edges: <b>{{ graph.edges.length }}</b></div>
          <div v-if="graph.errors && graph.errors.length" class="text-error">
            Errors: {{ graph.errors.length }}
          </div>
        </div>
      </aside>

      <!-- ── Main graph area ── -->
      <div class="topo-graph card">
        <div ref="graphContainer" class="graph-container"></div>
        <div v-if="loading && !graph" class="graph-overlay">
          <div class="loading-spinner"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Network } from 'vis-network/standalone'
import 'vis-network/styles/vis-network.css'
import api from '@/services/api'

// ────────────────────────────────────────────────────────────────────────────
// Node type -> visual style (both for vis-network and legend / draw.io)
// Keep ONE source of truth so exports and on-screen rendering agree.
// ────────────────────────────────────────────────────────────────────────────
function stylesForTheme () {
  const cs = getComputedStyle(document.documentElement)
  const textPrimary = cs.getPropertyValue('--text-primary').trim() || '#1f2937'
  const border = cs.getPropertyValue('--border-color').trim() || '#d1d5db'
  const bgCard = cs.getPropertyValue('--bg-card').trim() || '#ffffff'
  return { textPrimary, border, bgCard }
}

// Returns fill/stroke/shape for a given node type. `status` is only used for VMs.
function styleForNode (type, status) {
  switch (type) {
    case 'pve_host':
      return { shape: 'box', color: '#3b82f6', border: '#1d4ed8', font: '#ffffff', drawioStyle: 'rounded=1;whiteSpace=wrap;html=1;fillColor=#3b82f6;strokeColor=#1d4ed8;fontColor=#ffffff;' }
    case 'pve_node':
      return { shape: 'box', color: '#1e40af', border: '#1e3a8a', font: '#ffffff', size: 28, drawioStyle: 'rounded=1;whiteSpace=wrap;html=1;fillColor=#1e40af;strokeColor=#1e3a8a;fontColor=#ffffff;fontStyle=1;' }
    case 'vm': {
      const s = (status || '').toLowerCase()
      if (s === 'paused' || s === 'suspended') {
        return { shape: 'dot', color: '#f59e0b', border: '#b45309', font: '#111827', drawioStyle: 'ellipse;whiteSpace=wrap;html=1;fillColor=#f59e0b;strokeColor=#b45309;' }
      }
      if (s !== 'running') {
        return { shape: 'dot', color: '#ef4444', border: '#b91c1c', font: '#ffffff', drawioStyle: 'ellipse;whiteSpace=wrap;html=1;fillColor=#ef4444;strokeColor=#b91c1c;fontColor=#ffffff;' }
      }
      return { shape: 'dot', color: '#10b981', border: '#047857', font: '#ffffff', drawioStyle: 'ellipse;whiteSpace=wrap;html=1;fillColor=#10b981;strokeColor=#047857;fontColor=#ffffff;' }
    }
    case 'lxc':
      return { shape: 'diamond', color: '#22c55e', border: '#14532d', font: '#ffffff', drawioStyle: 'rhombus;whiteSpace=wrap;html=1;fillColor=#22c55e;strokeColor=#14532d;fontColor=#ffffff;' }
    case 'bridge':
      return { shape: 'hexagon', color: '#8b5cf6', border: '#5b21b6', font: '#ffffff', drawioStyle: 'shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;fillColor=#8b5cf6;strokeColor=#5b21b6;fontColor=#ffffff;' }
    case 'storage':
      return { shape: 'database', color: '#6b7280', border: '#374151', font: '#ffffff', drawioStyle: 'shape=cylinder3;whiteSpace=wrap;html=1;fillColor=#6b7280;strokeColor=#374151;fontColor=#ffffff;' }
    case 'pbs':
      return { shape: 'box', color: '#f97316', border: '#9a3412', font: '#ffffff', drawioStyle: 'rounded=0;whiteSpace=wrap;html=1;fillColor=#f97316;strokeColor=#9a3412;fontColor=#ffffff;' }
    case 'bmc':
      return { shape: 'triangle', color: '#eab308', border: '#854d0e', font: '#111827', drawioStyle: 'triangle;whiteSpace=wrap;html=1;fillColor=#eab308;strokeColor=#854d0e;' }
    case 'bond':
      return { shape: 'box', color: '#a855f7', border: '#6b21a8', font: '#ffffff', drawioStyle: 'rounded=1;whiteSpace=wrap;html=1;fillColor=#a855f7;strokeColor=#6b21a8;fontColor=#ffffff;' }
    case 'nic':
      return { shape: 'dot', size: 14, color: '#0ea5e9', border: '#075985', font: '#ffffff', drawioStyle: 'ellipse;whiteSpace=wrap;html=1;fillColor=#0ea5e9;strokeColor=#075985;fontColor=#ffffff;' }
    case 'vlan':
      return { shape: 'dot', size: 14, color: '#06b6d4', border: '#0e7490', font: '#ffffff', drawioStyle: 'ellipse;whiteSpace=wrap;html=1;fillColor=#06b6d4;strokeColor=#0e7490;fontColor=#ffffff;' }
    default:
      return { shape: 'box', color: '#9ca3af', border: '#4b5563', font: '#111827', drawioStyle: 'rounded=1;whiteSpace=wrap;html=1;fillColor=#9ca3af;strokeColor=#4b5563;' }
  }
}

export default {
  name: 'Topology',
  setup () {
    const router = useRouter()
    const graphContainer = ref(null)
    const graph = ref(null)
    const loading = ref(false)
    const errorMsg = ref('')
    const generatedAt = ref(null)
    let network = null

    const filters = reactive({
      include_stopped: false,
      include_lxc: true,
      include_storage: true,
      include_bridges: true,
      include_bmc: true,
      include_pbs: true,
      include_sync: true,
    })
    const viewMode = ref('infrastructure')
    function setViewMode(m) {
      if (viewMode.value === m) return
      viewMode.value = m
      // Network-only mode hides BMC/storage to keep it readable
      if (m === 'network') {
        filters.include_bmc = false
        filters.include_storage = false
      }
      // Destroy existing network so we re-fit on next render
      if (network) { try { network.destroy() } catch {} network = null }
      refresh(true)
    }

    const legend = computed(() => ([
      { type: 'pve_host', label: 'Proxmox host', color: '#3b82f6', border: '#1d4ed8', radius: '4px' },
      { type: 'pve_node', label: 'PVE node', color: '#1e40af', border: '#1e3a8a', radius: '4px' },
      { type: 'vm', label: 'VM (running)', color: '#10b981', border: '#047857', radius: '50%' },
      { type: 'vm_stopped', label: 'VM (stopped)', color: '#ef4444', border: '#b91c1c', radius: '50%' },
      { type: 'lxc', label: 'LXC container', color: '#22c55e', border: '#14532d', radius: '0', transform: 'rotate(45deg)' },
      { type: 'bridge', label: 'Network bridge', color: '#8b5cf6', border: '#5b21b6', radius: '4px' },
      { type: 'storage', label: 'Storage pool', color: '#6b7280', border: '#374151', radius: '8px' },
      { type: 'pbs', label: 'PBS server', color: '#f97316', border: '#9a3412', radius: '2px' },
      { type: 'bmc', label: 'iDRAC / BMC', color: '#eab308', border: '#854d0e', radius: '0' },
    ]))

    function formatTime (iso) {
      try {
        const d = new Date(iso)
        return d.toLocaleTimeString()
      } catch (e) { return iso }
    }

    function toVisNodes (g) {
      return g.nodes.map(n => {
        const st = styleForNode(n.type, n.data && n.data.status)
        let label = n.label
        const tooltip = buildTooltip(n)
        const base = {
          id: n.id,
          label,
          title: tooltip,
          shape: st.shape,
          color: { background: st.color, border: st.border, highlight: { background: st.color, border: st.border } },
          font: { color: st.font || '#111827', size: 12, face: 'inherit' },
          _meta: n,
        }
        if (st.size) base.size = st.size
        return base
      })
    }

    function toVisEdges (g) {
      return g.edges.map((e, idx) => {
        const isSync = e.kind === 'sync'
        const isError = isSync && (e.data && (e.data.last_run_state || '').toLowerCase() === 'error')
        return {
          id: `${e.from}->${e.to}#${idx}`,
          from: e.from,
          to: e.to,
          label: e.label || undefined,
          arrows: e.kind === 'sync' ? 'to' : '',
          dashes: isSync,
          color: { color: isError ? '#ef4444' : (isSync ? '#f59e0b' : '#94a3b8') },
          font: { size: 10, color: '#64748b', strokeWidth: 0 },
          smooth: { enabled: true, type: 'cubicBezier', roundness: 0.3 },
          _kind: e.kind,
        }
      })
    }

    function buildTooltip (n) {
      const d = n.data || {}
      const rows = []
      rows.push(`[${n.type}] ${n.label}`)
      for (const [k, v] of Object.entries(d)) {
        if (v === null || v === undefined || v === '') continue
        if (typeof v === 'object') continue
        rows.push(`${k}: ${v}`)
      }
      return rows.join('\n')
    }

    async function refresh (force) {
      loading.value = true
      errorMsg.value = ''
      try {
        const resp = await api.topology.getGraph({
          include_stopped: filters.include_stopped,
          include_bridges: filters.include_bridges,
          include_storage: filters.include_storage,
          include_bmc: filters.include_bmc,
          include_pbs: filters.include_pbs,
          include_lxc: filters.include_lxc,
          include_sync: filters.include_sync,
          view_mode: viewMode.value,
          refresh: !!force,
        })
        graph.value = resp.data
        generatedAt.value = resp.data.generated_at
        await nextTick()
        renderGraph()
      } catch (err) {
        errorMsg.value = err.response?.data?.detail || err.message || 'Failed to load topology'
      } finally {
        loading.value = false
      }
    }

    function renderGraph () {
      if (!graphContainer.value || !graph.value) return
      const { textPrimary, border } = stylesForTheme()
      const data = {
        nodes: toVisNodes(graph.value),
        edges: toVisEdges(graph.value),
      }
      const options = {
        autoResize: true,
        physics: {
          enabled: true,
          solver: 'forceAtlas2Based',
          forceAtlas2Based: { gravitationalConstant: -50, centralGravity: 0.01, springLength: 120, springConstant: 0.08, damping: 0.6, avoidOverlap: 0.5 },
          stabilization: { enabled: true, iterations: 250, updateInterval: 25, fit: true },
        },
        nodes: {
          borderWidth: 2,
          font: { color: textPrimary, size: 12 },
        },
        edges: {
          color: { color: border, highlight: '#3b82f6' },
          width: 1.4,
        },
        interaction: {
          hover: true,
          tooltipDelay: 200,
          multiselect: false,
          navigationButtons: false,
        },
      }
      if (network) {
        network.setData(data)
      } else {
        network = new Network(graphContainer.value, data, options)
        network.on('click', onClick)
        network.on('doubleClick', onDoubleClick)
        // When stabilization is done, fit the view and turn physics off.
        // Without this, the force-directed layout keeps running forever — 30+
        // nodes + 140+ edges = rAF fires ~60×/s with no visible change after
        // stability. Users see a blank canvas because nodes land off-screen.
        network.once('stabilizationIterationsDone', () => {
          try { network.fit({ animation: false }) } catch {}
          try { network.setOptions({ physics: { enabled: false } }) } catch {}
        })
        // Hard fallback — if stabilization never fires (very rare), force a
        // fit after 4 seconds so the user at least sees something.
        setTimeout(() => {
          try { network.fit({ animation: false }) } catch {}
          try { network.setOptions({ physics: { enabled: false } }) } catch {}
        }, 4000)
      }
    }

    function onClick (params) {
      const id = params.nodes && params.nodes[0]
      if (!id || !graph.value) return
      const n = graph.value.nodes.find(x => x.id === id)
      if (!n) return
      if (n.type === 'vm') {
        const d = n.data || {}
        if (d.host_id && d.node && d.vmid) {
          router.push(`/proxmox/${d.host_id}/nodes/${d.node}/vms/${d.vmid}`)
        }
      } else if (n.type === 'lxc') {
        const d = n.data || {}
        if (d.host_id && d.node && d.vmid) {
          router.push(`/proxmox/${d.host_id}/nodes/${d.node}/containers/${d.vmid}`)
        }
      } else if (n.type === 'pve_node') {
        const d = n.data || {}
        const parts = id.split(':')
        const hostId = parts[1]
        const nodeName = parts.slice(2).join(':')
        if (hostId && nodeName) router.push(`/proxmox/${hostId}/nodes/${nodeName}`)
      } else if (n.type === 'pve_host') {
        router.push('/proxmox')
      } else if (n.type === 'pbs') {
        router.push('/pbs-management')
      } else if (n.type === 'bmc') {
        router.push('/idrac')
      }
    }

    function onDoubleClick (params) {
      if (!network) return
      const id = params.nodes && params.nodes[0]
      if (!id) return
      network.focus(id, { scale: 1.4, animation: { duration: 600, easingFunction: 'easeInOutQuad' } })
    }

    function fit () {
      if (!network) return
      network.fit({ animation: { duration: 500 } })
    }

    // ──────────────────────────────────────────────────────────────
    // Exports
    // ──────────────────────────────────────────────────────────────
    function timestamp () {
      const d = new Date()
      const pad = (n) => String(n).padStart(2, '0')
      return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`
    }

    function downloadBlob (blob, filename) {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    }

    function downloadDataUrl (dataUrl, filename) {
      const a = document.createElement('a')
      a.href = dataUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    }

    function exportPNG () {
      if (!network) return
      try {
        const canvas = network.canvas.frame.canvas
        const url = canvas.toDataURL('image/png')
        downloadDataUrl(url, `topology-${timestamp()}.png`)
      } catch (e) {
        errorMsg.value = 'PNG export failed: ' + (e.message || e)
      }
    }

    function exportSVG () {
      if (!network || !graph.value) return
      // Synthesize an SVG using vis-network's computed positions. This is more
      // reliable than a canvas2svg shim for this use case — we already know
      // the full style per node type.
      const positions = network.getPositions()
      const nodes = graph.value.nodes
      const edges = graph.value.edges

      // Compute bounds
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      for (const n of nodes) {
        const p = positions[n.id]
        if (!p) continue
        if (p.x < minX) minX = p.x
        if (p.y < minY) minY = p.y
        if (p.x > maxX) maxX = p.x
        if (p.y > maxY) maxY = p.y
      }
      if (!isFinite(minX)) { minX = 0; minY = 0; maxX = 800; maxY = 600 }
      const pad = 80
      const w = (maxX - minX) + pad * 2
      const h = (maxY - minY) + pad * 2
      const ox = pad - minX
      const oy = pad - minY

      const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

      const parts = [
        `<?xml version="1.0" encoding="UTF-8"?>`,
        `<svg xmlns="http://www.w3.org/2000/svg" width="${Math.ceil(w)}" height="${Math.ceil(h)}" viewBox="0 0 ${Math.ceil(w)} ${Math.ceil(h)}" font-family="sans-serif" font-size="12">`,
        `<rect x="0" y="0" width="${Math.ceil(w)}" height="${Math.ceil(h)}" fill="#ffffff"/>`,
      ]

      // Edges first so they sit below nodes
      for (const e of edges) {
        const p1 = positions[e.from]; const p2 = positions[e.to]
        if (!p1 || !p2) continue
        const x1 = p1.x + ox, y1 = p1.y + oy, x2 = p2.x + ox, y2 = p2.y + oy
        const isSync = e.kind === 'sync'
        const isError = isSync && (e.data && (e.data.last_run_state || '').toLowerCase() === 'error')
        const stroke = isError ? '#ef4444' : (isSync ? '#f59e0b' : '#94a3b8')
        const dash = isSync ? ' stroke-dasharray="6,4"' : ''
        parts.push(`<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${stroke}"${dash} stroke-width="1.4"/>`)
        if (e.label) {
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2
          parts.push(`<text x="${mx.toFixed(1)}" y="${my.toFixed(1)}" fill="#64748b" font-size="10" text-anchor="middle">${esc(e.label)}</text>`)
        }
      }

      // Nodes
      for (const n of nodes) {
        const p = positions[n.id]
        if (!p) continue
        const cx = p.x + ox, cy = p.y + oy
        const st = styleForNode(n.type, n.data && n.data.status)
        const size = n.type === 'pve_node' ? 30 : 22
        // Shape
        if (st.shape === 'dot') {
          parts.push(`<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${size / 2}" fill="${st.color}" stroke="${st.border}" stroke-width="2"/>`)
        } else if (st.shape === 'diamond') {
          const r = size / 2
          parts.push(`<polygon points="${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}" fill="${st.color}" stroke="${st.border}" stroke-width="2"/>`)
        } else if (st.shape === 'triangle') {
          const r = size / 2
          parts.push(`<polygon points="${cx},${cy - r} ${cx + r},${cy + r} ${cx - r},${cy + r}" fill="${st.color}" stroke="${st.border}" stroke-width="2"/>`)
        } else if (st.shape === 'hexagon') {
          const r = size / 2
          const pts = []
          for (let i = 0; i < 6; i++) {
            const a = (Math.PI / 3) * i
            pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`)
          }
          parts.push(`<polygon points="${pts.join(' ')}" fill="${st.color}" stroke="${st.border}" stroke-width="2"/>`)
        } else if (st.shape === 'database') {
          const rx = size * 0.6, ry = size * 0.25
          parts.push(`<g>`)
          parts.push(`<ellipse cx="${cx}" cy="${cy - size * 0.4}" rx="${rx}" ry="${ry}" fill="${st.color}" stroke="${st.border}" stroke-width="2"/>`)
          parts.push(`<rect x="${cx - rx}" y="${cy - size * 0.4}" width="${rx * 2}" height="${size * 0.8}" fill="${st.color}" stroke="${st.border}" stroke-width="2"/>`)
          parts.push(`<ellipse cx="${cx}" cy="${cy + size * 0.4}" rx="${rx}" ry="${ry}" fill="${st.color}" stroke="${st.border}" stroke-width="2"/>`)
          parts.push(`</g>`)
        } else {
          // box
          const half = size
          parts.push(`<rect x="${(cx - half).toFixed(1)}" y="${(cy - size / 2).toFixed(1)}" width="${(half * 2).toFixed(1)}" height="${size.toFixed(1)}" rx="4" ry="4" fill="${st.color}" stroke="${st.border}" stroke-width="2"/>`)
        }
        // Label
        const labelColor = st.font || '#111827'
        parts.push(`<text x="${cx.toFixed(1)}" y="${(cy + size + 14).toFixed(1)}" fill="${labelColor === '#ffffff' ? '#111827' : labelColor}" text-anchor="middle">${esc(n.label)}</text>`)
      }

      parts.push('</svg>')
      const blob = new Blob([parts.join('\n')], { type: 'image/svg+xml;charset=utf-8' })
      downloadBlob(blob, `topology-${timestamp()}.svg`)
    }

    function exportDrawio () {
      if (!network || !graph.value) return
      const positions = network.getPositions()
      const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

      // Build cell id map (draw.io ids must start with id-something)
      const idMap = new Map()
      let counter = 2 // 0 and 1 are the implicit root/layer cells
      for (const n of graph.value.nodes) {
        idMap.set(n.id, 'c' + (counter++))
      }

      const cells = []
      cells.push('<mxCell id="0"/>')
      cells.push('<mxCell id="1" parent="0"/>')

      // Nodes
      for (const n of graph.value.nodes) {
        const st = styleForNode(n.type, n.data && n.data.status)
        const pos = positions[n.id] || { x: 0, y: 0 }
        const w = n.type === 'pve_node' ? 120 : 100
        const h = 40
        const x = Math.round(pos.x) - w / 2
        const y = Math.round(pos.y) - h / 2
        const cellId = idMap.get(n.id)
        const label = esc(n.label)
        cells.push(
          `<mxCell id="${cellId}" value="${label}" style="${st.drawioStyle}" vertex="1" parent="1">` +
          `<mxGeometry x="${x}" y="${y}" width="${w}" height="${h}" as="geometry"/>` +
          `</mxCell>`
        )
      }

      // Edges
      for (const e of graph.value.edges) {
        const srcId = idMap.get(e.from); const dstId = idMap.get(e.to)
        if (!srcId || !dstId) continue
        const isSync = e.kind === 'sync'
        const isError = isSync && (e.data && (e.data.last_run_state || '').toLowerCase() === 'error')
        const stroke = isError ? '#EF4444' : (isSync ? '#F59E0B' : '#94A3B8')
        const dash = isSync ? 'dashed=1;' : ''
        const style = `endArrow=${e.kind === 'sync' ? 'classic' : 'none'};html=1;strokeColor=${stroke};${dash}`
        const label = e.label ? esc(e.label) : ''
        const cellId = 'e' + (counter++)
        cells.push(
          `<mxCell id="${cellId}" value="${label}" style="${style}" edge="1" parent="1" source="${srcId}" target="${dstId}">` +
          `<mxGeometry relative="1" as="geometry"/>` +
          `</mxCell>`
        )
      }

      const xml =
        `<mxfile host="depl0y" modified="${new Date().toISOString()}" agent="depl0y-topology" version="1">` +
          `<diagram id="topology" name="Topology">` +
            `<mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" pageHeight="826" math="0" shadow="0">` +
              `<root>${cells.join('')}</root>` +
            `</mxGraphModel>` +
          `</diagram>` +
        `</mxfile>`

      const blob = new Blob([xml], { type: 'application/xml;charset=utf-8' })
      downloadBlob(blob, `topology-${timestamp()}.drawio`)
    }

    onMounted(() => { refresh(false) })
    onBeforeUnmount(() => {
      if (network) { try { network.destroy() } catch (e) {} network = null }
    })

    return {
      graphContainer, graph, loading, errorMsg, generatedAt,
      filters, legend,
      viewMode, setViewMode,
      refresh, fit, exportPNG, exportSVG, exportDrawio,
      formatTime,
    }
  },
}
</script>

<style scoped>
.topology-page {
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: 100%;
}
.page-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.topo-body {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 1rem;
  min-height: calc(100vh - 180px);
}
.topo-sidebar {
  padding: 1rem;
  background: var(--bg-card, var(--surface, #ffffff));
  border: 1px solid var(--border-color, #e5e7eb);
  color: var(--text-primary, #111827);
  border-radius: 8px;
  overflow-y: auto;
  max-height: calc(100vh - 180px);
}
.topo-sec-title {
  font-size: 0.75rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-secondary, #6b7280);
  margin: 0 0 0.5rem 0;
  font-weight: 700;
}
.view-toggle {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.25rem;
  margin-bottom: 0.5rem;
}
.vt-btn {
  font-size: 0.7rem;
  padding: 0.35rem 0.25rem;
  border: 1px solid var(--border-color);
  background: var(--surface);
  color: var(--text-primary);
  border-radius: 4px;
  cursor: pointer;
}
.vt-btn:hover { background: rgba(59, 130, 246, 0.08); }
.vt-btn--active {
  background: #3b82f6;
  border-color: #1d4ed8;
  color: #ffffff;
  font-weight: 600;
}

.topo-check {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  padding: 0.3rem 0;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}
.legend-row {
  display: flex;
  gap: 0.55rem;
  align-items: center;
  padding: 0.2rem 0;
  font-size: 0.8rem;
  color: var(--text-primary);
}
.legend-swatch {
  width: 14px;
  height: 14px;
  display: inline-block;
  border-width: 2px;
  border-style: solid;
}
.legend-label { flex: 1; }

.topo-graph {
  position: relative;
  background: var(--bg-card, var(--surface, #ffffff));
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  overflow: hidden;
  /* Explicit height so vis-network canvas can size itself — height:100%
     on the inner container only works when the parent has a real height,
     not just min-height. */
  height: calc(100vh - 200px);
  min-height: 600px;
}
.graph-container {
  width: 100%;
  height: 100%;
  min-height: 600px;
}
.graph-container canvas { display: block; }
.graph-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.05);
}
.stats { font-size: 0.85rem; color: var(--text-primary); }
.stats > div { padding: 0.15rem 0; }
.mt-2 { margin-top: 0.75rem; }

.alert {
  padding: 0.65rem 0.9rem;
  border-radius: 6px;
  font-size: 0.875rem;
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
  border: 1px solid rgba(239, 68, 68, 0.3);
}
.text-error { color: #ef4444; }

@media (max-width: 900px) {
  .topo-body { grid-template-columns: 1fr; }
  .topo-sidebar { max-height: none; }
}
</style>
