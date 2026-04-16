<template>
  <div class="multi-chart-wrapper" ref="wrapperRef">
    <!-- No data overlay -->
    <div v-if="!hasData" class="no-data-overlay">
      <span>No data available</span>
    </div>

    <svg
      v-else
      :viewBox="`0 0 ${W} ${totalH}`"
      preserveAspectRatio="none"
      class="multi-chart-svg"
      @mousemove="onMouseMove"
      @mouseleave="onMouseLeave"
    >
      <defs>
        <clipPath :id="clipId">
          <rect :x="PAD_L" :y="PAD_T" :width="innerW" :height="innerH" />
        </clipPath>
        <!-- Gradient per series -->
        <linearGradient
          v-for="(s, i) in series"
          :key="'grad' + i"
          :id="`${gradBase}-${i}`"
          x1="0" y1="0" x2="0" y2="1"
        >
          <stop offset="0%" :stop-color="s.color" stop-opacity="0.3" />
          <stop offset="100%" :stop-color="s.color" stop-opacity="0.02" />
        </linearGradient>
      </defs>

      <!-- Grid lines -->
      <template v-if="showGrid">
        <line
          v-for="(gl, i) in gridLines"
          :key="'gl' + i"
          :x1="PAD_L" :y1="gl.y"
          :x2="PAD_L + innerW" :y2="gl.y"
          stroke="rgba(156,163,175,0.12)" stroke-width="1"
          stroke-dasharray="4,4"
        />
      </template>

      <!-- Y-axis labels -->
      <text
        v-for="(gl, i) in gridLines"
        :key="'yl' + i"
        :x="PAD_L - 6"
        :y="gl.y + 4"
        text-anchor="end"
        class="axis-label"
      >{{ gl.label }}</text>

      <!-- X-axis labels -->
      <text
        v-for="(xl, i) in xLabels"
        :key="'xl' + i"
        :x="xl.x"
        :y="totalH - 2"
        text-anchor="middle"
        class="axis-label"
      >{{ xl.label }}</text>

      <!-- Filled areas (render behind lines) -->
      <template v-if="fillArea">
        <template v-for="(s, i) in computedSeries" :key="'area' + i">
          <path
            v-if="s.areaPath"
            :d="s.areaPath"
            :fill="`url(#${gradBase}-${i})`"
            :clip-path="`url(#${clipId})`"
          />
        </template>
      </template>

      <!-- Lines -->
      <template v-for="(s, i) in computedSeries" :key="'line' + i">
        <path
          v-if="s.linePath"
          :d="s.linePath"
          :stroke="s.color"
          stroke-width="2"
          fill="none"
          class="chart-line"
          :clip-path="`url(#${clipId})`"
        />
      </template>

      <!-- Hover crosshair -->
      <template v-if="hoverX !== null">
        <line
          :x1="hoverX" :y1="PAD_T"
          :x2="hoverX" :y2="PAD_T + innerH"
          stroke="rgba(255,255,255,0.25)" stroke-width="1"
        />
        <!-- Hover dots per series -->
        <template v-for="(s, i) in computedSeries" :key="'dot' + i">
          <circle
            v-if="hoverPoints[i]"
            :cx="hoverPoints[i].sx"
            :cy="hoverPoints[i].sy"
            r="4"
            :fill="s.color"
            stroke="white"
            stroke-width="1.5"
          />
        </template>
      </template>
    </svg>

    <!-- Legend -->
    <div v-if="hasData && series.length > 1" class="chart-legend">
      <div
        v-for="(s, i) in series"
        :key="'leg' + i"
        class="legend-item"
      >
        <span class="legend-dot" :style="{ background: s.color }"></span>
        <span class="legend-label">{{ s.label }}</span>
      </div>
    </div>

    <!-- Tooltip -->
    <div
      v-if="tooltip"
      class="multi-tooltip"
      :style="tooltipStyle"
    >
      <div class="multi-tooltip__time">{{ tooltip.time }}</div>
      <div
        v-for="(row, i) in tooltip.rows"
        :key="i"
        class="multi-tooltip__row"
      >
        <span class="multi-tooltip__dot" :style="{ background: row.color }"></span>
        <span class="multi-tooltip__label">{{ row.label }}:</span>
        <span class="multi-tooltip__val">{{ row.value }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  // series: [{ label, data: [{time, value}], color }]
  series: {
    type: Array,
    default: () => []
  },
  unit: {
    type: String,
    default: ''
  },
  height: {
    type: Number,
    default: 130
  },
  showGrid: {
    type: Boolean,
    default: true
  },
  fillArea: {
    type: Boolean,
    default: false
  },
  formatValue: {
    type: Function,
    default: null
  }
})

// SVG coordinate constants
const W = 600
const PAD_L = 42
const PAD_T = 8
const PAD_R = 8
const PAD_B = 18

const totalH = computed(() => props.height)
const innerW = computed(() => W - PAD_L - PAD_R)
const innerH = computed(() => totalH.value - PAD_T - PAD_B)

const uid = Math.random().toString(36).slice(2, 8)
const gradBase = `mg-${uid}`
const clipId = `mc-${uid}`

const hasData = computed(() =>
  props.series.some(s => s.data && s.data.length > 0)
)

// Global min/max across all series
const globalMin = computed(() => {
  let min = Infinity
  props.series.forEach(s => {
    ;(s.data || []).forEach(d => {
      if (d != null && typeof d.value === 'number' && isFinite(d.value) && d.value < min) {
        min = d.value
      }
    })
  })
  return min === Infinity ? 0 : Math.min(0, min)
})

const globalMax = computed(() => {
  let max = -Infinity
  props.series.forEach(s => {
    ;(s.data || []).forEach(d => {
      if (d != null && typeof d.value === 'number' && isFinite(d.value) && d.value > max) {
        max = d.value
      }
    })
  })
  if (max === -Infinity || max === 0) return 1
  return max
})

// Shared time domain
const timeMin = computed(() => {
  let min = Infinity
  props.series.forEach(s => {
    ;(s.data || []).forEach(d => { if (d.time && d.time < min) min = d.time })
  })
  return min === Infinity ? 0 : min
})

const timeMax = computed(() => {
  let max = -Infinity
  props.series.forEach(s => {
    ;(s.data || []).forEach(d => { if (d.time && d.time > max) max = d.time })
  })
  return max === -Infinity ? 1 : max
})

const toSX = (t) => {
  const range = timeMax.value - timeMin.value
  if (range === 0) return PAD_L + innerW.value / 2
  return PAD_L + ((t - timeMin.value) / range) * innerW.value
}

const toSY = (v) => {
  const range = globalMax.value - globalMin.value
  if (range === 0) return PAD_T + innerH.value / 2
  return PAD_T + innerH.value - ((v - globalMin.value) / range) * innerH.value
}

// Compute paths for each series
const computedSeries = computed(() => {
  return props.series.filter(s => s != null).map((s, _i) => {
    const pts = (s.data || [])
      .filter(d => d != null && typeof d.value === 'number' && isFinite(d.value))
      .map(d => ({ sx: toSX(d.time), sy: toSY(d.value), value: d.value, time: d.time }))

    if (pts.length < 2) return { ...s, linePath: '', areaPath: '', pts }

    // Cubic bezier line
    let linePath = `M ${pts[0].sx} ${pts[0].sy}`
    for (let i = 1; i < pts.length; i++) {
      const prev = pts[i - 1]
      const cur = pts[i]
      const cpx = (prev.sx + cur.sx) / 2
      linePath += ` C ${cpx} ${prev.sy}, ${cpx} ${cur.sy}, ${cur.sx} ${cur.sy}`
    }

    // Area path
    const bottom = PAD_T + innerH.value
    let areaPath = `M ${pts[0].sx} ${bottom} L ${pts[0].sx} ${pts[0].sy}`
    for (let i = 1; i < pts.length; i++) {
      const prev = pts[i - 1]
      const cur = pts[i]
      const cpx = (prev.sx + cur.sx) / 2
      areaPath += ` C ${cpx} ${prev.sy}, ${cpx} ${cur.sy}, ${cur.sx} ${cur.sy}`
    }
    areaPath += ` L ${pts[pts.length - 1].sx} ${bottom} Z`

    return { ...s, linePath, areaPath, pts }
  })
})

// Grid lines
const formatAxisVal = (v) => {
  if (props.formatValue) return props.formatValue(v)
  if (props.unit === '%') return v.toFixed(0) + '%'
  if (Math.abs(v) >= 1) return v.toFixed(1)
  if (Math.abs(v) >= 0.001) return (v * 1000).toFixed(1) + 'm'
  return v.toFixed(2)
}

const gridLines = computed(() => {
  const lines = []
  const steps = 4
  for (let i = 0; i <= steps; i++) {
    const fraction = i / steps
    const v = globalMin.value + fraction * (globalMax.value - globalMin.value)
    const y = PAD_T + innerH.value - fraction * innerH.value
    lines.push({ y, label: formatAxisVal(v) })
  }
  return lines
})

// X-axis labels: from first series with data
const xLabels = computed(() => {
  const s = computedSeries.value.find(s => s.pts && s.pts.length > 1)
  if (!s) return []
  const pts = s.pts
  const count = Math.min(5, pts.length)
  const result = []
  for (let i = 0; i < count; i++) {
    const idx = Math.round((i / (count - 1)) * (pts.length - 1))
    const pt = pts[idx]
    if (!pt?.time) continue
    const d = new Date(pt.time * 1000)
    const hh = d.getHours().toString().padStart(2, '0')
    const mm = d.getMinutes().toString().padStart(2, '0')
    result.push({ x: pt.sx, label: `${hh}:${mm}` })
  }
  return result
})

// Hover/tooltip
const wrapperRef = ref(null)
const hoverX = ref(null)
const hoverPoints = ref([])
const tooltip = ref(null)
const tooltipStyle = ref({})

const formatVal = (v) => {
  if (props.formatValue) return props.formatValue(v)
  if (props.unit === '%') return v.toFixed(1) + '%'
  if (props.unit) return v.toFixed(2) + ' ' + props.unit
  return v.toFixed(2)
}

const onMouseMove = (e) => {
  if (!wrapperRef.value || !hasData.value) return
  const rect = wrapperRef.value.getBoundingClientRect()
  const relX = ((e.clientX - rect.left) / rect.width) * W

  // For each series, find nearest point
  const points = computedSeries.value.map(s => {
    if (!s || !s.pts || !s.pts.length) return null
    let nearest = null
    let minDist = Infinity
    s.pts.forEach(pt => {
      const dist = Math.abs(pt.sx - relX)
      if (dist < minDist) { minDist = dist; nearest = pt }
    })
    return nearest
  })

  hoverX.value = relX
  hoverPoints.value = points

  // Build tooltip
  const timeStr = (() => {
    const pt = points.find(p => p && p.time)
    if (!pt) return ''
    const d = new Date(pt.time * 1000)
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
  })()

  const rows = props.series.map((s, i) => ({
    color: s.color,
    label: s.label,
    value: points[i] ? formatVal(points[i].value) : '—'
  }))

  tooltip.value = { time: timeStr, rows }

  const tipX = e.clientX - rect.left
  const tipY = e.clientY - rect.top
  const leftPos = tipX > rect.width / 2 ? tipX - 150 : tipX + 12
  tooltipStyle.value = {
    left: Math.max(0, leftPos) + 'px',
    top: Math.max(0, tipY - 46) + 'px',
  }
}

const onMouseLeave = () => {
  hoverX.value = null
  hoverPoints.value = []
  tooltip.value = null
}
</script>

<style scoped>
.multi-chart-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.no-data-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 0.8rem;
  color: var(--text-secondary, #6b7280);
}

.multi-chart-svg {
  width: 100%;
  height: 100%;
  display: block;
  overflow: visible;
}

.chart-line {
  transition: d 0.3s ease;
}

.axis-label {
  font-size: 9px;
  fill: #6b7280;
  font-family: 'Consolas', 'Monaco', monospace;
}

.chart-legend {
  display: flex;
  gap: 1rem;
  justify-content: center;
  padding: 0.25rem 0.5rem 0.25rem;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  color: var(--text-secondary, #9ca3af);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  white-space: nowrap;
}

.multi-tooltip {
  position: absolute;
  background: rgba(15, 20, 30, 0.93);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 7px 12px;
  pointer-events: none;
  z-index: 20;
  min-width: 130px;
  backdrop-filter: blur(4px);
}

.multi-tooltip__time {
  font-size: 0.7rem;
  color: #9ca3af;
  font-family: monospace;
  margin-bottom: 5px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding-bottom: 4px;
}

.multi-tooltip__row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 4px;
  font-size: 0.8rem;
}

.multi-tooltip__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.multi-tooltip__label {
  color: #9ca3af;
  flex-shrink: 0;
}

.multi-tooltip__val {
  font-weight: 700;
  color: #f9fafb;
  font-family: monospace;
  margin-left: auto;
}
</style>
