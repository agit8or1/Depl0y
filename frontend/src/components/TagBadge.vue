<template>
  <span
    class="tag-badge-pill"
    :class="{ 'tag-badge-pill--small': small, 'tag-badge-pill--removable': removable }"
    :style="{ backgroundColor: bg, color: fg }"
  >
    <span class="tag-badge-pill__text">{{ tag }}</span>
    <button
      v-if="removable"
      class="tag-badge-pill__remove"
      :style="{ color: fg }"
      @click.stop="$emit('remove', tag)"
      :title="`Remove ${tag}`"
      type="button"
    >×</button>
  </span>
</template>

<script>
import { computed } from 'vue'
import { tagColor, tagTextColor } from '@/utils/tagColors'

export default {
  name: 'TagBadge',
  props: {
    tag: { type: String, required: true },
    removable: { type: Boolean, default: false },
    small: { type: Boolean, default: false },
  },
  emits: ['remove'],
  setup(props) {
    const bg = computed(() => tagColor(props.tag))
    const fg = computed(() => tagTextColor(bg.value))
    return { bg, fg }
  }
}
</script>

<style scoped>
.tag-badge-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  white-space: nowrap;
  letter-spacing: 0.02em;
  text-transform: lowercase;
  transition: opacity 0.15s, transform 0.1s;
  user-select: none;
}

.tag-badge-pill:hover {
  opacity: 0.9;
}

.tag-badge-pill--small {
  font-size: 0.62rem;
  padding: 0.1rem 0.35rem;
}

.tag-badge-pill__text {
  line-height: 1.2;
}

.tag-badge-pill__remove {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  margin: 0;
  font-size: 0.85rem;
  line-height: 1;
  opacity: 0.75;
  transition: opacity 0.1s, transform 0.1s;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tag-badge-pill__remove:hover {
  opacity: 1;
  background: rgba(0, 0, 0, 0.15);
  transform: scale(1.15);
}
</style>
