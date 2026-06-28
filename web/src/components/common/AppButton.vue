<script setup lang="ts">
defineProps<{
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
  block?: boolean
}>()
</script>

<template>
  <button
    class="app-btn"
    :class="[`btn-${variant ?? 'primary'}`, `btn-${size ?? 'md'}`, { loading, block }]"
    :disabled="disabled || loading"
    type="button"
  >
    <span v-if="loading" class="spinner" />
    <span :style="{ visibility: loading ? 'hidden' : 'visible' }">
      <slot />
    </span>
  </button>
</template>

<style scoped>
.app-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
  border-radius: var(--r-button);
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s var(--ease-standard), transform 0.1s var(--ease-standard);
  position: relative;
  outline: none;
}

.app-btn:active:not(:disabled) {
  transform: scale(0.97);
}

.app-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.app-btn.block {
  width: 100%;
}

/* 尺寸 */
.btn-sm { padding: 4px 12px; font-size: 13px; height: 30px; }
.btn-md { padding: 8px 18px; font-size: 14px; height: 38px; }
.btn-lg { padding: 10px 24px; font-size: 16px; height: 44px; }

/* 变体 */
.btn-primary {
  background: var(--c-brand-500);
  color: #fff;
}
.btn-primary:hover:not(:disabled) {
  background: var(--c-brand-600);
}

.btn-secondary {
  background: var(--c-gray-100);
  color: var(--c-gray-700);
}
.btn-secondary:hover:not(:disabled) {
  background: var(--c-gray-200);
}

.btn-danger {
  background: rgba(220, 38, 38, 0.08);
  color: var(--c-danger);
  border: 1px solid rgba(220, 38, 38, 0.2);
}
.btn-danger:hover:not(:disabled) {
  background: rgba(220, 38, 38, 0.15);
}

.btn-ghost {
  background: transparent;
  color: var(--c-gray-600);
}
.btn-ghost:hover:not(:disabled) {
  background: var(--c-gray-100);
}

.spinner {
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
