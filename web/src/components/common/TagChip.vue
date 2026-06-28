<script setup lang="ts">
defineProps<{
  name: string
  color: string
  small?: boolean
  clickable?: boolean
}>()

const emit = defineEmits<{ click: [] }>()

function handleClick() {
  emit('click')
}
</script>

<template>
  <span
    class="tag-chip"
    :class="{ small, clickable }"
    :style="{ backgroundColor: color + '1A', color: color, borderColor: color + '4D' }"
    @click.stop="clickable ? handleClick() : undefined"
    role="button"
    :tabindex="clickable ? 0 : undefined"
    @keydown.enter="clickable ? handleClick() : undefined"
  >
    {{ name }}
  </span>
</template>

<style scoped>
.tag-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--r-chip);
  font-size: var(--t-caption-size);
  font-weight: 500;
  line-height: 1.5;
  border: 1px solid transparent;
  white-space: nowrap;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: opacity 0.15s var(--ease-standard);
}

.tag-chip.small {
  padding: 1px 6px;
  font-size: 11px;
}

.tag-chip.clickable {
  cursor: pointer;
}

.tag-chip.clickable:hover {
  opacity: 0.75;
}
</style>
