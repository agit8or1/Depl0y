<template>
  <!--
    Reusable entry point: the heart button plus the modal it owns. Drop
    <HelpUsGrowButton /> anywhere (header, sidebar, settings page) and it works.
    The modal only ever opens from a click — never automatically.
  -->
  <button
    type="button"
    class="hug-trigger"
    :aria-label="label"
    :title="label"
    @click="open = true"
  >
    <span class="hug-trigger-heart" aria-hidden="true">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
    </span>
    <span class="hug-trigger-label">{{ label }}</span>
  </button>

  <HelpUsGrowModal :open="open" @close="open = false" />
</template>

<script>
import { ref } from 'vue'
import HelpUsGrowModal from '@/components/HelpUsGrowModal.vue'

export default {
  name: 'HelpUsGrowButton',
  components: { HelpUsGrowModal },
  props: {
    label: { type: String, default: 'Help Us Grow' },
  },
  setup() {
    const open = ref(false)
    return { open }
  },
}
</script>

<style scoped>
/*
  The app header is a fixed dark gradient in both themes, so this button is
  styled for a dark background rather than from the theme tokens.
*/
.hug-trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.38);
  border-radius: 8px;
  padding: 0.35rem 0.7rem;
  color: #fecaca;
  font-size: 0.8rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.hug-trigger:hover {
  background: rgba(239, 68, 68, 0.22);
  border-color: rgba(239, 68, 68, 0.65);
  color: #fff;
}

.hug-trigger:focus-visible {
  outline: 2px solid #f87171;
  outline-offset: 2px;
}

.hug-trigger-heart {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #f87171;
  /* Static glow — the baseline for browsers and users without animation. */
  filter: drop-shadow(0 0 3px rgba(239, 68, 68, 0.55));
}

.hug-trigger-label {
  font-weight: 600;
  letter-spacing: 0.01em;
}

/*
  Heartbeat: two quick beats then a long rest, so it reads as a pulse rather
  than a throb. Only applied when the user has not asked for reduced motion.
  Scoped to the heart alone — the button itself never moves, so it cannot shift
  neighbouring header items.
*/
@media (prefers-reduced-motion: no-preference) {
  .hug-trigger-heart {
    animation: hug-heartbeat 3.2s ease-in-out infinite;
    transform-origin: center;
  }

  .hug-trigger:hover .hug-trigger-heart {
    animation-duration: 1.6s;
  }
}

@keyframes hug-heartbeat {
  0%,  100% { transform: scale(1);    filter: drop-shadow(0 0 3px rgba(239, 68, 68, 0.45)); }
  6%        { transform: scale(1.19); filter: drop-shadow(0 0 7px rgba(239, 68, 68, 0.85)); }
  12%       { transform: scale(1);    filter: drop-shadow(0 0 3px rgba(239, 68, 68, 0.45)); }
  18%       { transform: scale(1.12); filter: drop-shadow(0 0 6px rgba(239, 68, 68, 0.7));  }
  26%       { transform: scale(1);    filter: drop-shadow(0 0 3px rgba(239, 68, 68, 0.45)); }
  /* 26%–100% is the rest between beats. */
}

/*
  Small screens: heart only. The label is dropped rather than wrapped or
  clipped, and `aria-label`/`title` keep the button named for screen readers
  and tooltips.
*/
@media (max-width: 1100px) {
  .hug-trigger-label { display: none; }

  .hug-trigger {
    padding: 0.35rem;
    width: 32px;
    height: 32px;
    justify-content: center;
  }
}
</style>
