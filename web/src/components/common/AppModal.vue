<script setup lang="ts">
import { watch } from 'vue'

const props = defineProps<{
  visible: boolean
  title?: string
  width?: string
}>()

const emit = defineEmits<{ close: [] }>()

function onScrimClick(e: MouseEvent) {
  if ((e.target as HTMLElement).classList.contains('modal-scrim')) {
    emit('close')
  }
}

watch(() => props.visible, (v) => {
  if (v) {
    document.addEventListener('keydown', onEsc)
  } else {
    document.removeEventListener('keydown', onEsc)
  }
})

function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="modal-scrim" @mousedown="onScrimClick">
        <div class="modal-panel" :style="{ maxWidth: width || '520px' }" @mousedown.stop>
          <div v-if="title || $slots.header" class="modal-header">
            <slot name="header">
              <h2 class="modal-title">{{ title }}</h2>
            </slot>
            <button class="modal-close" @click="emit('close')" aria-label="关闭">&times;</button>
          </div>
          <div class="modal-body">
            <slot />
          </div>
          <div v-if="$slots.footer" class="modal-footer">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-scrim {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: var(--glass-modal-scrim);
  padding: 1rem;
}

@supports not (backdrop-filter: blur(1px)) {
  .modal-scrim { background: rgba(0, 0, 0, 0.4); }
}

.modal-panel {
  width: 100%;
  background: var(--surface-primary);
  border-radius: var(--r-modal);
  box-shadow: var(--sh-modal);
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  color: var(--c-gray-900);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--s-4) var(--s-5);
  border-bottom: 1px solid var(--c-gray-200);
}

.modal-title {
  font-size: var(--t-title-size);
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0;
}

.modal-close {
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  font-size: 22px;
  color: var(--c-gray-400);
  cursor: pointer;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, background 0.15s;
}
.modal-close:hover {
  color: var(--c-gray-700);
  background: var(--c-gray-100);
}

.modal-body {
  padding: var(--s-5);
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--s-2);
  padding: var(--s-3) var(--s-5);
  border-top: 1px solid var(--c-gray-200);
}

/* Mobile full-width */
@media (max-width: 767px) {
  .modal-scrim {
    padding: 0;
    align-items: flex-end;
  }

  .modal-panel {
    max-width: 100% !important;
    max-height: 92vh;
    border-radius: var(--r-modal) var(--r-modal) 0 0;
  }

  .modal-body {
    padding: var(--s-3) var(--s-4);
  }

  .modal-footer {
    padding: var(--s-3) var(--s-4);
  }
}

/* Transition */
.modal-enter-active {
  transition: opacity 0.28s var(--ease-spring);
}
.modal-enter-active .modal-panel {
  transition: transform 0.28s var(--ease-spring);
}
.modal-leave-active {
  transition: opacity 0.2s var(--ease-standard);
}
.modal-leave-active .modal-panel {
  transition: transform 0.2s var(--ease-standard);
}
.modal-enter-from {
  opacity: 0;
}
.modal-enter-from .modal-panel {
  transform: scale(0.95);
}
.modal-leave-to {
  opacity: 0;
}
.modal-leave-to .modal-panel {
  transform: scale(0.95);
}
</style>
