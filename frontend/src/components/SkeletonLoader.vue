<template>
  <div class="skeleton-wrapper" aria-busy="true" aria-label="Loading…">
    <div v-for="i in count" :key="i" class="skeleton-row" :class="`skeleton-${type}`">

      <!-- Table row skeleton -->
      <div v-if="type === 'table'" class="skeleton-table-row">
        <div class="skeleton-cell skeleton-cell--sm"></div>
        <div class="skeleton-cell skeleton-cell--lg"></div>
        <div class="skeleton-cell skeleton-cell--md"></div>
        <div class="skeleton-cell skeleton-cell--sm"></div>
        <div class="skeleton-cell skeleton-cell--md"></div>
      </div>

      <!-- Card skeleton -->
      <div v-else-if="type === 'card'" class="skeleton-card">
        <div class="skeleton-card-header"></div>
        <div class="skeleton-card-line"></div>
        <div class="skeleton-card-line skeleton-card-line--short"></div>
      </div>

      <!-- Stat skeleton -->
      <div v-else-if="type === 'stat'" class="skeleton-stat">
        <div class="skeleton-stat-value"></div>
        <div class="skeleton-stat-label"></div>
      </div>

      <!-- Text skeleton -->
      <div v-else class="skeleton-text">
        <div class="skeleton-text-line"></div>
        <div class="skeleton-text-line skeleton-text-line--short"></div>
      </div>

    </div>
  </div>
</template>

<script>
export default {
  name: 'SkeletonLoader',
  props: {
    type: {
      type: String,
      default: 'text',
      validator: (v) => ['table', 'card', 'stat', 'text'].includes(v),
    },
    count: {
      type: Number,
      default: 5,
    },
  },
}
</script>

<style scoped>
@keyframes shimmer {
  0%   { background-position: 200% center; }
  100% { background-position: -200% center; }
}

.skeleton-wrapper {
  padding: 0.25rem 0;
}

/* Shared shimmer mixin applied via utility class */
.skeleton-cell,
.skeleton-card-header,
.skeleton-card-line,
.skeleton-stat-value,
.skeleton-stat-label,
.skeleton-text-line {
  border-radius: 4px;
  background: linear-gradient(
    90deg,
    var(--border-color) 25%,
    var(--background) 50%,
    var(--border-color) 75%
  );
  background-size: 200% auto;
  animation: shimmer 1.5s linear infinite;
}

/* ── Table row ── */
.skeleton-table-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.6rem 0.875rem;
  border-top: 1px solid var(--border-color);
}

.skeleton-table-row:first-child {
  border-top: none;
}

.skeleton-cell {
  height: 14px;
  flex-shrink: 0;
}

.skeleton-cell--sm  { width: 48px; }
.skeleton-cell--md  { width: 96px; }
.skeleton-cell--lg  { flex: 1; min-width: 120px; max-width: 220px; }

/* ── Card ── */
.skeleton-card {
  padding: 1rem 1.25rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  margin-bottom: 0.75rem;
  background: var(--surface);
}

.skeleton-card-header {
  height: 18px;
  width: 55%;
  margin-bottom: 0.75rem;
}

.skeleton-card-line {
  height: 13px;
  width: 90%;
  margin-bottom: 0.5rem;
}

.skeleton-card-line--short {
  width: 60%;
  margin-bottom: 0;
}

/* ── Stat ── */
.skeleton-stat {
  display: inline-flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background: var(--surface);
  min-width: 110px;
  margin-right: 0.75rem;
  margin-bottom: 0.75rem;
}

.skeleton-stat-value {
  height: 22px;
  width: 64px;
}

.skeleton-stat-label {
  height: 11px;
  width: 48px;
}

/* ── Text ── */
.skeleton-text {
  margin-bottom: 0.6rem;
}

.skeleton-text-line {
  height: 13px;
  width: 100%;
  margin-bottom: 0.4rem;
}

.skeleton-text-line--short {
  width: 65%;
  margin-bottom: 0;
}
</style>
