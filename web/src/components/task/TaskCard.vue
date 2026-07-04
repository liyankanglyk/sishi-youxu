<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTaskStore, getDueStatus, DUE_STATUS_CONFIG } from '@/stores/task'
import type { TaskOut } from '@/api/tasks'

const props = defineProps<{
  task: TaskOut
  density?: 'compact' | 'standard' | 'detailed'
  dimmed?: boolean
}>()

const emit = defineEmits<{
  click: [task: TaskOut]
  complete: [task: TaskOut, event: MouseEvent]
  delete: [task: TaskOut]
  contextmenu: [task: TaskOut]
}>()

const store = useTaskStore()

// ── 完成动画状态 ──
const isCompleting = ref(false)
const animPeak = ref(1.05)
const animDuration = ref(600)

function handleComplete(e: MouseEvent) {
  if (isCompleting.value || props.task.completed) return
  isCompleting.value = true
  // 随机化动画参数，每次完成略有不同
  animPeak.value = 1.03 + Math.random() * 0.04   // 1.03 ~ 1.07
  animDuration.value = 550 + Math.random() * 150  // 550ms ~ 700ms
  emit('complete', props.task, e)
  setTimeout(() => {
    isCompleting.value = false
  }, animDuration.value + 50)
}

const isMilestone = computed(() => store.completionIntensity >= 4)
const isCompact = computed(() => props.density === 'compact')
const isDetailed = computed(() => props.density === 'detailed')

const dueStatus = computed(() => getDueStatus(props.task.dueDate))
const dueConfig = computed(() => DUE_STATUS_CONFIG[dueStatus.value])

const dueDateStr = computed(() => {
  if (!props.task.dueDate) return null
  const d = new Date(props.task.dueDate)
  return `${d.getMonth() + 1}月${d.getDate()}日`
})

const tags = computed(() => {
  const t = props.task.tags
  if (!t || !t.length) return []
  if (typeof t[0] === 'string') {
    return (t as string[]).map(uuid => store.tags.find(tg => tg.uuid === uuid)).filter(Boolean) as { uuid: string; name: string; color: string }[]
  }
  return t as { uuid: string; name: string; color: string }[]
})

const checklistProgress = computed(() => {
  const total = Number(props.task.checklistTotal)
  if (!total) return null
  const done = Number(props.task.checklistCompleted)
  return `☑ ${done}/${total}`
})
</script>

<template>
  <div
    class="task-card"
    :class="[
      `density-${density ?? 'standard'}`,
      {
        completed: task.completed && !isCompleting,
        'just-completed': isCompleting,
        'is-milestone': isCompleting && isMilestone,
        'due-overdue': dueStatus === 'overdue',
        'due-today': dueStatus === 'today',
        'is-dimmed': dimmed,
      },
    ]"
    :style="{
      borderLeftColor: dueConfig.color || 'transparent',
      '--pulse-peak': isCompleting ? animPeak : 1.05,
      '--pulse-duration': `${isCompleting ? animDuration : 600}ms`,
    }"
    @click="emit('click', task)"
    @contextmenu.prevent="emit('contextmenu', task)"
    role="button"
    tabindex="0"
    @keydown.enter="emit('click', task)"
  >
    <!-- 完成 / 选中指示 -->
    <template v-if="!task.completed">
      <button
        class="complete-btn"
        :title="task.completed ? '取消完成' : '标记完成'"
        @click.stop="handleComplete"
      >
        <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M3 8l3 3 7-7" />
        </svg>
      </button>
    </template>

    <!-- 标题行 -->
    <div class="card-title-row">
      <span class="card-title">{{ task.title || '未命名' }}</span>
      <svg
        v-if="task.recurrence"
        class="recurrence-icon"
        viewBox="0 0 16 16"
        width="12"
        height="12"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <path d="M1 4v4h4M15 12v-4h-4" />
        <path d="M12.5 2.5a7 7 0 00-10 2M3.5 13.5a7 7 0 0010-2" />
      </svg>
    </div>

    <!-- 底部行：标签 + 日期 -->
    <div class="card-footer">
      <!-- 标签 —— 紧凑模式隐藏，标准模式显示色点，详细模式显示名称 -->
      <div v-if="!isCompact && tags.length" class="card-tags">
        <template v-if="!isDetailed">
          <span
            v-for="tag in tags.slice(0, 3)"
            :key="tag.uuid"
            class="tag-dot"
            :style="{ backgroundColor: tag.color }"
          />
          <span v-if="tags.length > 3" class="tag-extra">+{{ tags.length - 3 }}</span>
        </template>
        <template v-else>
          <span
            v-for="tag in tags"
            :key="tag.uuid"
            class="tag-chip"
            :style="{ color: tag.color }"
          >
            <span class="tag-chip-dot" :style="{ backgroundColor: tag.color }" />
            {{ tag.name }}
          </span>
        </template>
      </div>

      <!-- 截止日期 + 检查项 -->
      <div v-if="dueDateStr || checklistProgress" class="card-due">
        <span v-if="checklistProgress" class="checklist-text">{{ checklistProgress }}</span>
        <span
          v-if="dueDateStr"
          class="due-text"
        >
          <span
            v-if="dueConfig.label"
            class="due-status-chip"
            :style="{ backgroundColor: dueConfig.bg, color: dueConfig.color }"
          >{{ dueConfig.label }}</span>
          {{ dueDateStr }}
        </span>
      </div>
    </div>

    <!-- 备注预览（仅详细模式） -->
    <div v-if="isDetailed && task.note" class="card-note">
      {{ task.note }}
    </div>

    <!-- 删除按钮（绝对定位，悬停时显示） -->
    <button
      class="delete-btn"
      title="删除"
      @click.stop="emit('delete', task)"
    >&times;</button>
  </div>
</template>

<style scoped>
/* ── 基础卡片 ── */
.task-card {
  position: relative;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-left: 3px solid transparent;
  border-radius: 16px;
  padding: 10px 12px;
  cursor: grab;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s ease, border-color 0.2s ease, opacity 0.2s ease;
  user-select: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 68px;
  max-width: var(--task-card-max-width);
}

.task-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

:root.dark .task-card {
  background: rgba(40, 40, 47, 0.85);
  border-color: rgba(255, 255, 255, 0.08);
}

.task-card:active {
  cursor: grabbing;
}

/* ── 状态 ── */

/* 完成瞬间动画 —— 光晕脉冲 → 缩略 → 静置 */
.task-card.just-completed {
  animation: cardBurst var(--pulse-duration, 600ms) cubic-bezier(0.22, 0.98, 0.36, 1) forwards;
  pointer-events: none;
}

@keyframes cardBurst {
  0% {
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
    filter: brightness(1);
    transform: scale(1);
    opacity: 1;
  }
  18% {
    box-shadow: 0 0 0 6px rgba(5, 150, 105, 0.28), 0 8px 24px rgba(5, 150, 105, 0.16);
    filter: brightness(1.1);
    transform: scale(var(--pulse-peak, 1.12));
    opacity: 1;
  }
  40% {
    box-shadow: 0 0 0 10px rgba(5, 150, 105, 0.08), 0 12px 32px rgba(5, 150, 105, 0.06);
    filter: brightness(1.15);
    transform: scale(1.08);
    opacity: 0.8;
  }
  70% {
    box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.04), 0 2px 6px rgba(0, 0, 0, 0.04);
    filter: brightness(0.95);
    transform: scale(0.3);
    opacity: 0.15;
  }
  85% {
    transform: scale(0.92);
    opacity: 0.55;
  }
  100% {
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
    filter: brightness(0.94);
    transform: scale(0.97);
    opacity: 0.6;
  }
}

/* 里程碑金色扫光 */
.task-card.is-milestone {
  overflow: hidden;
}
.task-card.is-milestone::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: linear-gradient(
    45deg,
    transparent 40%,
    rgba(247, 203, 77, 0.25) 45%,
    rgba(247, 203, 77, 0.4) 50%,
    rgba(247, 203, 77, 0.25) 55%,
    transparent 60%
  );
  animation: goldSweep 0.7s ease-out forwards;
  z-index: 10;
  pointer-events: none;
}

@keyframes goldSweep {
  from { transform: translateX(-100%) translateY(-100%); }
  to   { transform: translateX(100%) translateY(100%); }
}

.task-card.just-completed .card-title {
  text-decoration: line-through;
  text-decoration-thickness: 2px;
  text-decoration-color: var(--c-success);
}

.task-card.completed {
  opacity: 0.6;
}

.task-card.completed .card-title {
  text-decoration: line-through;
}

.task-card.due-overdue {
  border-left: 3px solid;
}

.task-card.due-today {
  border-left: 3px solid;
}

.task-card.is-dimmed {
  opacity: 0.35;
}

/* ── 完成按钮（右上角，悬停显示） ── */
.complete-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid var(--c-gray-200);
  background: var(--surface-primary);
  color: var(--c-success);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s ease, transform 0.15s ease;
  transform: scale(0.85);
  z-index: 5;
  padding: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.task-card:hover .complete-btn {
  opacity: 1;
  transform: scale(1);
}

.complete-btn:hover {
  background: var(--c-success);
  border-color: var(--c-success);
  color: #fff;
}

/* ── 删除按钮（左上角，悬停显示） ── */
.delete-btn {
  position: absolute;
  top: -6px;
  left: -6px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid var(--c-gray-200);
  background: var(--surface-primary);
  color: var(--c-gray-400);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  line-height: 1;
  opacity: 0;
  transition: opacity 0.15s ease, transform 0.15s ease;
  transform: scale(0.85);
  z-index: 5;
  padding: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.task-card:hover .delete-btn {
  opacity: 1;
  transform: scale(1);
}

.delete-btn:hover {
  background: var(--c-danger);
  border-color: var(--c-danger);
  color: #fff;
}

/* ── 标题 ── */
.card-title-row {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.card-title {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--c-gray-900);
  flex: 1;
  min-width: 0;
}

.recurrence-icon {
  flex-shrink: 0;
  color: var(--c-brand-500);
}

/* ── 底部（标签 + 截止日期） ── */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-top: auto;
}

.card-tags {
  display: flex;
  align-items: center;
  gap: 3px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tag-extra {
  font-size: 10px;
  color: var(--c-gray-400);
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  color: var(--c-gray-500);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 72px;
}

.tag-chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* ── 截止日期 ── */
.card-due {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--c-gray-500);
  white-space: nowrap;
  flex-shrink: 0;
}

.due-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.due-status-chip {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.4;
}

.checklist-text {
  color: var(--c-gray-400);
  font-variant-numeric: tabular-nums;
}

/* ── 备注 ── */
.card-note {
  margin-top: 4px;
  font-size: 10px;
  line-height: 1.45;
  color: var(--c-gray-500);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

/* ══════════════════════════════════════════ */
/* 密度变体                                   */
/* ══════════════════════════════════════════ */

/* ── 紧凑 ── */
.density-compact {
  padding: 6px 8px;
  min-width: 72px;
  min-height: 44px;
  gap: 0;
}

.density-compact .card-title {
  font-size: 11px;
}

.density-compact .card-footer {
  margin-top: 2px;
  gap: 2px;
}

.density-compact .card-title {
  font-size: 11px;
}

.density-compact .due-status-chip {
  display: none;
}

.density-compact .due-text {
  font-size: 10px;
}

/* ── 详细 ── */
.density-detailed {
  padding: 10px 12px;
  min-width: 140px;
  max-width: 200px;
  gap: 6px;
}

.density-detailed .card-title {
  font-size: 13px;
  white-space: normal;
  word-break: break-word;
}

/* ── 移动端：窄而高，纵向堆叠 ── */
@media (max-width: 767px) {
  .task-card {
    padding: 7px 8px;
    min-height: 54px;
    border-radius: 9px;
    border-left-width: 2px;
    gap: 4px;
    min-width: 64px;
    max-width: 110px;
  }

  /* 标题：允许最多两行换行 */
  .card-title-row {
    align-items: flex-start;
  }

  .card-title {
    font-size: 11px;
    font-weight: 600;
    line-height: 1.3;
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    word-break: break-word;
  }

  .recurrence-icon {
    width: 10px;
    height: 10px;
    margin-top: 1px;
  }

  /* 底部：纵向堆叠 */
  .card-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    margin-top: auto;
  }

  .card-due {
    flex-direction: row;
    align-items: center;
    font-size: 10px;
    gap: 3px;
  }

  .due-text {
    font-size: 10px;
    gap: 3px;
  }

  .due-status-chip {
    font-size: 8px;
    padding: 1px 4px;
    border-radius: 3px;
  }

  .checklist-text {
    font-size: 9px;
  }

  /* 标签：小 chip，最多展示 2 个 */
  .card-tags {
    display: flex !important;
    flex-wrap: wrap;
    gap: 2px;
    margin-bottom: 2px;
  }

  .tag-dot { display: none !important; }
  .tag-extra { display: none !important; }

  .tag-chip {
    display: inline-flex !important;
    font-size: 8px;
    max-width: 48px;
    gap: 2px;
  }

  .tag-chip-dot {
    width: 5px;
    height: 5px;
  }

  /* 按钮始终可见 */
  .complete-btn,
  .delete-btn {
    opacity: 1;
    transform: scale(1);
  }

  .complete-btn {
    width: 14px;
    height: 14px;
    top: -3px;
    right: -3px;
  }

  .complete-btn svg {
    width: 8px;
    height: 8px;
  }

  .delete-btn {
    display: none;
  }

  /* ---- 移动端密度变体 ---- */

  /* 标准：窄，适中高度 */
  .density-standard {
    max-width: 110px;
    min-width: 72px;
    min-height: 58px;
    padding: 6px 8px;
  }

  /* 紧凑：极窄、极简 */
  .density-compact {
    max-width: 76px;
    min-width: 52px;
    min-height: 40px;
    padding: 4px 6px;
    border-radius: 7px;
    gap: 2px;
  }

  .density-compact .card-title {
    font-size: 10px;
    -webkit-line-clamp: 1;
    white-space: nowrap;
  }

  .density-compact .card-tags {
    display: none !important;
  }

  .density-compact .card-footer {
    display: none;
  }

  /* 详细：最宽、最高 */
  .density-detailed {
    max-width: 140px;
    min-width: 96px;
    min-height: 76px;
    padding: 8px 10px;
    gap: 4px;
  }

  .density-detailed .card-title {
    font-size: 12px;
  }

  .density-detailed .card-note {
    font-size: 9px;
    -webkit-line-clamp: 2;
  }

  .density-detailed .tag-chip {
    font-size: 9px;
    max-width: 56px;
  }
}
</style>
