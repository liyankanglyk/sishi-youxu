<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts } = useToast()
</script>

<template>
  <TransitionGroup name="toast" tag="div" class="toast-container">
    <div v-for="t in toasts" :key="t.id" class="toast-item" :class="`toast-${t.type}`">
      <span class="toast-icon">
        <template v-if="t.type === 'success'">&#10003;</template>
        <template v-else-if="t.type === 'error'">&#10007;</template>
        <template v-else-if="t.type === 'warning'">&#9888;</template>
        <template v-else>&#8505;</template>
      </span>
      {{ t.message }}
    </div>
  </TransitionGroup>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: calc(var(--header-height) + 12px);
  right: 16px;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--glass-bg-light);
  backdrop-filter: var(--glass-toast);
  border-radius: var(--r-input);
  box-shadow: var(--sh-modal);
  font-size: 14px;
  color: var(--c-gray-900);
  pointer-events: auto;
  border: 1px solid var(--c-gray-200);
}

.toast-success .toast-icon { color: var(--c-success); }
.toast-error .toast-icon { color: var(--c-danger); }
.toast-warning .toast-icon { color: var(--c-warning); }
.toast-info .toast-icon { color: var(--c-brand-500); }

.toast-enter-active {
  transition: all 0.3s var(--ease-spring);
}
.toast-leave-active {
  transition: all 0.2s var(--ease-standard);
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}
</style>
