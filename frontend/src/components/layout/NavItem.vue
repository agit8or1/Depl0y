<template>
  <div
    :class="['nav-item', extraClass, isActive ? 'router-link-active' : '']"
    role="link"
    tabindex="0"
    @click="navigate"
    @keydown.enter.prevent="navigate"
  >
    <span class="icon">{{ icon }}</span>
    <span class="nav-item-label">{{ label }}</span>
    <span v-if="badge && badge > 0" class="nav-badge">{{ badge > 99 ? '99+' : badge }}</span>
  </div>
</template>

<script>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export default {
  name: 'NavItem',
  props: {
    to: { type: String, required: true },
    icon: { type: String, required: true },
    label: { type: String, required: true },
    badge: { type: Number, default: null },
    extraClass: { type: String, default: '' },
  },
  emits: ['click'],
  setup(props, { emit }) {
    const route = useRoute()
    const router = useRouter()

    const isActive = computed(() => {
      if (props.to === '/') return route.path === '/'
      return route.path.startsWith(props.to)
    })

    const navigate = () => {
      router.push(props.to)
      emit('click')
    }

    return { isActive, navigate }
  },
}
</script>
