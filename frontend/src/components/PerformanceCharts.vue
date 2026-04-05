<template>
  <div class="perf-chart-wrapper" ref="wrapperRef">
    <svg
      :viewBox="`0 0 ${W} ${totalH}`"
      preserveAspectRatio="none"
      class="perf-chart-svg"
      @mousemove="onMouseMove"
      @mouseleave="onMouseLeave"
    >
      <defs>
        <linearGradient :id="gradId" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="color" stop-opacity="0.35" />
          <stop offset="100%" :stop-color="color" stop-opacity="0.03" />
        </linearGradient>
        <!-- clip path to keep chart in bounds -->
        <clipPath :id="clipId">
          <rect :x="PAD_L" :y="PAD_T" :width="innerW" :height="innerH" />
        </clipPath>
      </defs>

      <!-- Grid lines -->
      <template v-if="showGrid">
        <line
          v-for="(gl, i) in gridLines"
          :key="'gl' + i"
          :x1="PAD_L" :y1="gl.y"
          :x2="PAD_L + innerW" :y2="gl.y"
          stroke="rgba(156,163,175,0.15)" stroke-width="1"
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

      <!-- Filled area -->
      <path
        v-if="fillArea && areaPath"
        :d="areaPath"
        :fill="`url(#${gradId})`"
        clip-path="url(#${clipId})"
      />

      <!-- Curve line -->
      <path
        v-if="linePath"
        :d="linePath"
        :stroke="color"
        stroke-width="2"
        fill="none"
        class="chart-line"
        :clip-path="`url(#${clipId})`"
      />

      <!-- Hover crosshair -->
      <template v-if="hoverIdx !== null && hoverIdx >= 0 && hoverIdx < validPoints.length">
        <line
          :x1="validPoints[hoverIdx].sx" :y1="PAD_T"
          :x2="validPoints[hoverIdx].sx" :y2="PAD_T + innerH"
          stroke="rgba(255,255,255,0.3)" stroke-width="1"
        />
        <circle
          :cx="validPoints[hoverIdx].sx"
          :cy="validPoints[hoverIdx].sy"
          r="4"
          :fill="color"
          stroke="white"
          stroke-width="1.5"
        />
      </template>
    </svg>

    <!-- Tooltip -->
    <div
      v-if="tooltip"
      class="perf-tooltip"
      :style="tooltipStyle"
    >
      <div class="perf-tooltip__time">{{ tooltip.time }}</div>
      <div class="perf-tooltip__val">{{ tooltip.value }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  label: {
    type: String,
    default: ''
  },
  unit: {
    type: String,
    default: ''
  },
  color: {
    type: String,
    default: '#3b82f6'
  },
  height: {
    type: Number,
    default: 120
  },
  showGrid: {
    type: Boolean,
    default: true
  },
  fillArea: {
    type: Boolean,
    default: true
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

// Unique IDs for gradient/clip (avoids collisions when multiple charts on page)
const uid = Math.random().toString(36).slice(2, 8)
const gradId = `pg-${uid}`
const clipId = `pc-${uid}`

// Filter data to valid numeric points
const validData = computed(() => {
  return (props.data || []).filter(d => d != null && typeof d.value === 'number' && isFinite(d.value))
})

// Min/max
const minVal = computed(() => {
  if (!validData.value.length) return 0
  return Math.min(0, ...validData.value.map(d => d.value))
})
const maxVal = computed(() => {
  if (!validData.value.length) return 100
  const m = Math.max(...validData.value.map(d => d.value))
  return m === 0 ? 1 : m
})

// Map a value to SVG Y coordinate
const toSY = (v) => {
  const range = maxVal.value - minVal.value
  if (range === 0) return PAD_T + innerH.value / 2
  return PAD_T + innerH.value - ((v - minVal.value) / range) * innerH.value
}

// Map an index to SVG X coordinate (across all raw data points, not just valid)
const toSX = (i, total) => {
  if (total <= 1) return PAD_L
  return PAD_L + (i / (total - 1)) * innerW.value
}

// Compute screen-space points for valid data only
const validPoints = computed(() => {
  const total = props.data.length
  return (props.data || []).map((d, i) => {
    if (d == null || typeof d.value !== 'number' || !isFinite(d.value)) return null
    return {
      sx: toSX(i, total),
      sy: toSY(d.value),
      value: d.value,
      time: d.time,
      rawIdx: i,
    }
  }).filter(Boolean)
})

// Cubic bezier smooth line path
const linePath = computed(() => {
  const pts = validPoints.value
  if (pts.length < 2) return ''
  let d = `M ${pts[0].sx} ${pts[0].sy}`
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1]
    const cur = pts[i]
    const cpx = (prev.sx + cur.sx) / 2
    d += ` C ${cpx} ${prev.sy}, ${cpx} ${cur.sy}, ${cur.sx} ${cur.sy}`
  }
  return d
})

// Filled area under curve
const areaPath = computed(() => {
  const pts = validPoints.value
  if (pts.length < 2) return ''
  const bottom = PAD_T + innerH.value
  let d = `M ${pts[0].sx} ${bottom} L ${pts[0].sx} ${pts[0].sy}`
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1]
    const cur = pts[i]
    const cpx = (prev.sx + cur.sx) / 2
    d += ` C ${cpx} ${prev.sy}, ${cpx} ${cur.sy}, ${cur.sx} ${cur.sy}`
  }
  d += ` L ${pts[pts.length - 1].sx} ${bottom} Z`
  return d
})

// Grid lines (4 horizontal divisions)
const gridLines = computed(() => {
  const lines = []
  const steps = 4
  for (let i = 0; i <= steps; i++) {
    const fraction = i / steps
    const v = minVal.value + fraction * (maxVal.value - minVal.value)
    const y = PAD_T + innerH.value - fraction * innerH.value
    const label = formatAxisVal(v)
    lines.push({ y, label })
  }
  return lines
})

const formatAxisVal = (v) => {
  if (props.unit === '%') return v.toFixed(0) + '%'
  if (props.unit === 'MB/s') {
    if (Math.abs(v) >= 1) return v.toFixed(1)
    return v.toFixed(2)
  }
  if (Math.abs(v) >= 1000000) return (v / 1000000).toFixed(1) + 'M'
  if (Math.abs(v) >= 1000) return (v / 1000).toFixed(0) + 'k'
  return v.toFixed(1)
}

// X-axis labels: show up to 5 time labels
const xLabels = computed(() => {
  const pts = validPoints.value
  if (pts.length < 2) return []
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

// Hover/tooltip logic
const wrapperRef = ref(null)
const hoverIdx = ref(null)
const tooltip = ref(null)
const tooltipStyle = ref({})

const onMouseMove = (e) => {
  if (!wrapperRef.value || !validPoints.value.length) return
  const rect = wrapperRef.value.getBoundingClientRect()
  // Map mouse X to SVG coordinate space
  const relX = ((e.clientX - rect.left) / rect.width) * W
  // Find nearest valid point
  let nearest = null
  let minDist = Infinity
  validPoints.value.forEach((pt, i) => {
    const dist = Math.abs(pt.sx - relX)
    if (dist < minDist) {
      minDist = dist
      nearest = i
    }
  })
  if (nearest === null) return
  hoverIdx.value = nearest
  const pt = validPoints.value[nearest]
  const timeStr = pt.time ? (() => {
    const d = new Date(pt.time * 1000)
    const hh = d.getHours().toString().padStart(2, '0')
    const mm = d.getMinutes().toString().padStart(2, '0')
    const ss = d.getSeconds().toString().padStart(2, '0')
    return `${hh}:${mm}:${ss}`
  })() : ''
  const valStr = props.unit === '%'
    ? pt.value.toFixed(1) + '%'
    : props.unit
      ? pt.value.toFixed(2) + ' ' + props.unit
      : pt.value.toFixed(2)

  tooltip.value = { time: timeStr, value: valStr }

  // Position tooltip — keep it inside wrapper
  const tipX = e.clientX - rect.left
  const tipY = e.clientY - rect.top
  const leftPos = tipX > rect.width / 2 ? tipX - 130 : tipX + 12
  tooltipStyle.value = {
    left: Math.max(0, leftPos) + 'px',
    top: Math.max(0, tipY - 36) + 'px',
  }
}

const onMouseLeave = () => {
  hoverIdx.value = null
  tooltip.value = null
}
</script>

<style scoped>
.perf-chart-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.perf-chart-svg {
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

.perf-tooltip {
  position: absolute;
  background: rgba(15, 20, 30, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 6px 10px;
  pointer-events: none;
  z-index: 10;
  min-width: 110px;
  backdrop-filter: blur(4px);
}

.perf-tooltip__time {
  font-size: 0.7rem;
  color: #9ca3af;
  font-family: monospace;
}

.perf-tooltip__val {
  font-size: 0.9rem;
  font-weight: 700;
  color: #f9fafb;
  margin-top: 2px;
}
</style>
