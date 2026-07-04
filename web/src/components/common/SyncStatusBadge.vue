<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSync } from '@/lib/sync'
import { useToast } from '@/composables/useToast'
import ConflictDialog from './ConflictDialog.vue'

const { state, syncNow } = useSync()
const toast = useToast()
const dialogOpen = ref(false)

// 派生文案与图标
const view = computed(() => {
  const s = state.status
  if (s === 'offline') {
    return { kind: 'offline' as const, icon: '☁️', text: '离线', title: '离线：操作已暂存到本地，恢复网络后自动同步' }
  }
  if (s === 'syncing' || state.isRunning) {
    return { kind: 'syncing' as const, icon: '⟳', text: '同步中…', title: '正在与云端同步' }
  }
  if (s === 'error') {
    return { kind: 'error' as const, icon: '⚠', text: '同步失败', title: state.lastError ?? '同步出错，点击重试' }
  }
  // idle
  if (state.conflicts.length > 0) {
    return {
      kind: 'conflict' as const,
      icon: '⚠',
      text: `${state.conflicts.length} 项冲突`,
      title: '存在同步冲突，点击解决',
    }
  }
  if (state.pendingCount > 0) {
    return {
      kind: 'pending' as const,
      icon: '☁',
      text: `${state.pendingCount} 项待同步`,
      title: '本地有未同步的变更，点击立即同步',
    }
  }
  return { kind: 'synced' as const, icon: '✓', text: '已同步', title: '所有数据已同步到云端' }
})

async function handleClick() {
  if (view.value.kind === 'conflict') {
    dialogOpen.value = true
    return
  }
  try {
    await syncNow()
    if (state.status !== 'error') {
      toast.success('已同步')
    }
  } catch (e: any) {
    toast.error(e?.message ?? '同步失败')
  }
}
</script>

<template>
  <button
    class="sync-badge"
    :class="['kind-' + view.kind]"
    :title="view.title"
    :aria-label="view.title"
    :disabled="view.kind === 'offline'"
    @click="handleClick"
  >
    <span class="sync-icon" :class="{ spinning: view.kind === 'syncing' }">
      {{ view.icon }}
    </span>
    <span class="sync-text">{{ view.text }}</span>
    <span v-if="state.pendingCount > 0 && view.kind !== 'conflict'" class="sync-dot" />
  </button>
  <ConflictDialog v-model:open="dialogOpen" />
</template>

<style scoped>
.sync-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--border-light, #E4E4E7);
  background: var(--surface-secondary, #FAFAFA);
  color: var(--c-gray-700, #3F3F46);
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
  position: relative;
  white-space: nowrap;
  user-select: none;
}

.sync-badge:hover:not(:disabled) {
  background: var(--c-gray-100, #F4F4F5);
}

.sync-badge:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.sync-icon {
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.sync-icon.spinning {
  animation: sync-spin 1.1s linear infinite;
}

@keyframes sync-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.sync-text {
  font-weight: 500;
}

.sync-dot {
  position: absolute;
  top: 2px;
  right: 4px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-warning, #D97706);
}

/* kind-specific 配色 */
.sync-badge.kind-synced {
  color: var(--c-success, #059669);
  border-color: rgba(5, 150, 105, 0.3);
  background: rgba(5, 150, 105, 0.08);
}
.sync-badge.kind-synced:hover {
  background: rgba(5, 150, 105, 0.15);
}

.sync-badge.kind-pending {
  color: #92400E;
  border-color: rgba(217, 119, 6, 0.3);
  background: rgba(217, 119, 6, 0.08);
}
.sync-badge.kind-pending:hover {
  background: rgba(217, 119, 6, 0.15);
}

.sync-badge.kind-syncing {
  color: var(--c-brand-500, #2E5BFF);
  border-color: rgba(46, 91, 255, 0.3);
  background: rgba(46, 91, 255, 0.08);
}

.sync-badge.kind-offline {
  color: var(--c-gray-500, #71717A);
}

.sync-badge.kind-conflict {
  color: var(--c-danger, #DC2626);
  border-color: rgba(220, 38, 38, 0.35);
  background: rgba(220, 38, 38, 0.08);
}
.sync-badge.kind-conflict:hover {
  background: rgba(220, 38, 38, 0.15);
}

.sync-badge.kind-error {
  color: var(--c-danger, #DC2626);
  border-color: rgba(220, 38, 38, 0.35);
  background: rgba(220, 38, 38, 0.08);
}
</style>