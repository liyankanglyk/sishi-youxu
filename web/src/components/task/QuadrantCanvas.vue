<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useTaskStore, type TaskEx } from '@/stores/task'
import type { TaskOut } from '@/api/tasks'
import TaskCard from '@/components/task/TaskCard.vue'

const props = defineProps<{
  density?: 'compact' | 'standard' | 'detailed'
  selectMode?: boolean
  selectedIds?: string[]
}>()

const emit = defineEmits<{
  'task-click': [task: TaskEx]
  'task-complete': [task: TaskEx | null]
  'task-delete': [task: TaskEx | null]
  'select-toggle': [uuid: string]
  'double-click': [urgencyLevel: number, importanceLevel: number]
}>()

const store = useTaskStore()

const canvasRef = ref<HTMLElement | null>(null)

interface DragState {
  uuid: string | null
  startX: number
  startY: number
  offsetX: number        // 抓取时光标相对卡片中心的偏移量
  offsetY: number
  canvasLeft: number
  canvasTop: number
  canvasWidth: number
  canvasHeight: number
  pointerId: number | null
  active: boolean
  moved: boolean
  liveLeft: string | null   // 拖拽过程中相对画布的 px 值
  liveTop: string | null
  snappedU: number          // pointermove 最近一次吸附后的 level
  snappedI: number
}

const drag = reactive<DragState>({
  uuid: null,
  startX: 0, startY: 0,
  offsetX: 0, offsetY: 0,
  canvasLeft: 0, canvasTop: 0,
  canvasWidth: 0, canvasHeight: 0,
  pointerId: null,
  active: false,
  moved: false,
  liveLeft: null,
  liveTop: null,
  snappedU: 0,
  snappedI: 0,
})

const wrapperRefs = new Map<string, HTMLElement>()
const DRAG_THRESHOLD = 4

// ── 画布布局常量 ──
const CANVAS_MARGIN = 6
const CANVAS_RANGE = 88
const LEVEL_MIN = -4
const LEVEL_MAX = 4
const LEVEL_RANGE = LEVEL_MAX - LEVEL_MIN  // 8

function levelToPercent(level: number): number {
  const clamped = Math.max(LEVEL_MIN, Math.min(LEVEL_MAX, level))
  return ((clamped - LEVEL_MIN) / LEVEL_RANGE) * CANVAS_RANGE + CANVAS_MARGIN
}

function percentToLevel(pct: number): number {
  const raw = Math.round((pct - CANVAS_MARGIN) / CANVAS_RANGE * LEVEL_RANGE) + LEVEL_MIN
  return Math.max(LEVEL_MIN, Math.min(LEVEL_MAX, raw))
}

interface QuadrantDef { id: string; label: string; sub: string; desc: string; bg: string }

const quadrants: QuadrantDef[] = [
  { id: 'Q2', label: '重要不紧急', sub: '多做', desc: '学技能、锻炼、做规划——这些事今天不做没感觉，但坚持一年就能拉开差距。主动给它们留出整块时间。', bg: 'var(--q2-bg)' },
  { id: 'Q1', label: '重要且紧急', sub: '马上做', desc: '截止日到了、出了问题、有人等着——这种事躲不掉，越快越好。平时多投入 Q2，这里的东西自然会变少。', bg: 'var(--q1-bg)' },
  { id: 'Q4', label: '不重要不紧急', sub: '尽量少做', desc: '刷手机、闲聊、无意义重复——偶尔放松没问题，但要警惕它们悄悄吃掉大量时间。', bg: 'var(--q4-bg)' },
  { id: 'Q3', label: '不重要紧急', sub: '能推就推', desc: '别人的急事不一定是你的急事。能交给别人就交出去，不行就快速处理掉，别让它挤占重要的事。', bg: 'var(--q3-bg)' },
]

function tasksForQuadrant(qId: string): TaskEx[] {
  if (qId === 'Q1') return store.q1Tasks
  if (qId === 'Q2') return store.q2Tasks
  if (qId === 'Q3') return store.q3Tasks
  return store.q4Tasks
}

// ── 堆叠：相同 (u,i) 上的任务渲染为一摞卡片 —— 顶部卡片完全可见，
//     下方的卡片以明显的对角偏移露出一角 ──
const STACK_OFFSET_PX = 22 // 堆叠中相邻卡片之间的像素偏移
const STACK_MAX_OFFSET_PX = 88 // 总偏移上限，避免偏离网格点过远

// 缓存 key → 每个任务的 {stackIndex, total, z}
let _stackCacheKey = ''
const _stackMap = new Map<string, { stackIndex: number; total: number; z: number }>()

function buildStackMap() {
  // 在缓存 key 中包含 level 信息，使移动操作能正确触发缓存失效
  const key = store.filteredTasks.map(t => `${t.uuid}:${t.urgencyLevel},${t.importanceLevel}`).join('|')
  if (key === _stackCacheKey) return
  _stackCacheKey = key
  _stackMap.clear()

  // 按 (u,i) 坐标对任务进行分组
  const groups = new Map<string, TaskEx[]>()
  for (const t of store.filteredTasks) {
    const k = `${t.urgencyLevel},${t.importanceLevel}`
    if (!groups.has(k)) groups.set(k, [])
    groups.get(k)!.push(t)
  }

  for (const [, group] of groups) {
    // 排序规则：截止日期升序（空值排最后），再按 sortOrder，最后按 uuid
    group.sort((a, b) => {
      const da = a.dueDate ?? '9999'
      const db = b.dueDate ?? '9999'
      if (da !== db) return da.localeCompare(db)
      return (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.uuid.localeCompare(b.uuid)
    })

    group.forEach((t, idx) => {
      // idx=0 = 最早到期 = 堆叠顶部（最高 z）
      _stackMap.set(t.uuid, {
        stackIndex: idx,
        total: group.length,
        z: group.length - idx,
      })
    })
  }
}

function stackEntry(task: TaskEx): { stackIndex: number; total: number; z: number } {
  return _stackMap.get(task.uuid) ?? { stackIndex: 0, total: 1, z: 1 }
}

/** 所有任务相对于整个画布定位 —— 与拖拽计算使用同一套坐标系。 */
function taskStyle(task: TaskEx): Record<string, string> {
  if (drag.active && drag.uuid === task.uuid && drag.liveLeft && drag.liveTop) {
    return {
      left: drag.liveLeft,
      top: drag.liveTop,
      zIndex: '999',
    }
  }
  buildStackMap()
  const e = stackEntry(task)

  // 基于紧急/重要程度的基础位置
  const baseLeftPct = levelToPercent(task.urgencyLevel)
  const baseTopPct = levelToPercent(-task.importanceLevel)

  if (e.total <= 1) {
    return {
      left: `${baseLeftPct}%`,
      top: `${baseTopPct}%`,
      zIndex: '1',
    }
  }

  // 堆叠时通过 CSS calc 增加像素偏移，使其在任何画布尺寸下都生效。
  // 偏移量用 calc() 表示，在百分比位置上加上 px。
  // wrapper 设置了 transform: translate(-50%,-50%)，因此 left/top 指的是卡片中心。
  // 增加的 px 会让位于堆叠深处的卡片中心向右下方偏移。
  const px = Math.min(e.stackIndex * STACK_OFFSET_PX, STACK_MAX_OFFSET_PX)
  // 堆叠更深的卡片在垂直方向上偏移略小（呈现更明显的扇形展开）
  const pxY = Math.min(e.stackIndex * (STACK_OFFSET_PX * 0.6), STACK_MAX_OFFSET_PX * 0.6)
  return {
    left: `calc(${baseLeftPct}% + ${px}px)`,
    top: `calc(${baseTopPct}% + ${pxY}px)`,
    zIndex: String(Math.max(e.z, drag.uuid === task.uuid ? 999 : 1)),
  }
}

function setWrapperRef(uuid: string, el: Element | null) {
  if (el instanceof HTMLElement) wrapperRefs.set(uuid, el)
  else wrapperRefs.delete(uuid)
}

function gridPointToLevel(gx: number, gy: number): { u: number; i: number } {
  const canvasXPct = CANVAS_MARGIN + gx * CANVAS_RANGE
  const canvasYPct = CANVAS_MARGIN + gy * CANVAS_RANGE
  return {
    u: percentToLevel(canvasXPct),
    i: -percentToLevel(canvasYPct),
  }
}

// ── 拖拽 ──

function onPointerDown(e: PointerEvent, uuid: string) {
  const target = e.target as HTMLElement
  if (target.closest('.action-btn')) return

  const wrapper = wrapperRefs.get(uuid)
  if (!wrapper) return
  const canvas = canvasRef.value
  if (!canvas) return

  const canvasRect = canvas.getBoundingClientRect()
  const wrapperRect = wrapper.getBoundingClientRect()

  const cardCenterX = wrapperRect.left + wrapperRect.width / 2
  const cardCenterY = wrapperRect.top + wrapperRect.height / 2

  drag.uuid = uuid
  drag.startX = e.clientX
  drag.startY = e.clientY
  drag.offsetX = e.clientX - cardCenterX
  drag.offsetY = e.clientY - cardCenterY
  drag.canvasLeft = canvasRect.left
  drag.canvasTop = canvasRect.top
  drag.canvasWidth = canvasRect.width
  drag.canvasHeight = canvasRect.height
  drag.pointerId = e.pointerId
  drag.active = false
  drag.moved = false
  drag.liveLeft = null
  drag.liveTop = null

  // 在拖拽阈值被突破之后再延迟启用 pointer capture，这样仅点击卡片时浏览器原生 click 事件仍会触发。
  document.addEventListener('pointermove', onPointerMove)
  document.addEventListener('pointerup', onPointerUp)
  document.addEventListener('pointercancel', onPointerCancel)
}

function onPointerMove(e: PointerEvent) {
  if (!drag.uuid) return
  const dist = Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY)
  if (!drag.moved && dist < DRAG_THRESHOLD) return

  if (!drag.moved) {
    // 首次越过阈值 —— 切换到 pointer capture 并为画布添加标记 class
    drag.moved = true
    const wrapper = wrapperRefs.get(drag.uuid!)
    if (wrapper) {
      try { wrapper.setPointerCapture(drag.pointerId!) } catch { /* 忽略 */ }
    }
    canvasRef.value?.classList.add('is-dragging')
  }
  drag.active = true

  // 卡片中心在画布像素坐标系中的位置
  const cxCanvas = e.clientX - drag.offsetX - drag.canvasLeft
  const cyCanvas = e.clientY - drag.offsetY - drag.canvasTop
  const cxClamped = Math.max(0, Math.min(drag.canvasWidth, cxCanvas))
  const cyClamped = Math.max(0, Math.min(drag.canvasHeight, cyCanvas))

  // 转换为画布 0..1 比例 → level → 吸附后的 level
  const gx = cxClamped / drag.canvasWidth
  const gy = cyClamped / drag.canvasHeight
  const { u, i } = gridPointToLevel(gx, gy)
  drag.snappedU = u
  drag.snappedI = i

  // 将吸附后的 level 重新换算为画布像素位置，用于 liveLeft/Top
  drag.liveLeft = `${(levelToPercent(u) / 100) * drag.canvasWidth}px`
  drag.liveTop = `${(levelToPercent(-i) / 100) * drag.canvasHeight}px`
}

function endDragCleanup() {
  document.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('pointerup', onPointerUp)
  document.removeEventListener('pointercancel', onPointerCancel)
  if (drag.uuid) {
    const wrapper = wrapperRefs.get(drag.uuid)
    if (wrapper && drag.pointerId !== null) {
      try { wrapper.releasePointerCapture(drag.pointerId) } catch { /* 忽略 */ }
    }
  }
  canvasRef.value?.classList.remove('is-dragging')
  drag.uuid = null
  drag.active = false
  drag.moved = false
  drag.pointerId = null
  drag.liveLeft = null
  drag.liveTop = null
}

function onPointerUp(_e: PointerEvent) {
  if (!drag.uuid) return
  const wasDrag = drag.moved
  const uuid = drag.uuid

  if (!wasDrag) {
    endDragCleanup()
    return
  }

  store.moveTask(uuid, drag.snappedU, drag.snappedI)
  endDragCleanup()
}

function onPointerCancel() {
  endDragCleanup()
}

function onClickCapture(e: MouseEvent) {
  if (drag.moved || drag.active) {
    e.stopPropagation()
    e.preventDefault()
  }
}

function onCanvasDblClick(e: MouseEvent) {
  if ((e.target as HTMLElement).closest('.task-card-wrapper')) return
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const gx = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  const gy = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height))
  const { u, i } = gridPointToLevel(gx, gy)
  emit('double-click', u, i)
}

function handleTaskClick(task: TaskEx) {
  if (props.selectMode) emit('select-toggle', task.uuid)
  else emit('task-click', task)
}
</script>

<template>
  <div
    ref="canvasRef"
    class="quadrant-canvas"
    @click.capture="onClickCapture"
    @dblclick="onCanvasDblClick"
  >
    <!-- 象限背景 + 空状态 -->
    <div class="quadrant-grid">
      <div
        v-for="q in quadrants"
        :key="q.id"
        class="quadrant-pane"
        :style="{ backgroundColor: q.bg }"
      >
        <!-- 始终可见的标签 -->
        <div class="quadrant-label">
          <span class="ql-name">{{ q.label }}</span>
          <span class="ql-sub">{{ q.sub }}</span>
        </div>
        <div class="quadrant-content">
          <div v-if="!tasksForQuadrant(q.id).length" class="empty-area">
            <p class="empty-hint">{{ store.hasActiveFilters ? '无匹配任务' : '双击此处创建任务' }}</p>
            <p class="empty-desc">{{ q.desc }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 任务 wrapper —— 作为画布的直接子元素，相对于整个画布定位 -->
    <div
      v-for="task in store.filteredTasks"
      :key="task.uuid"
      :ref="(el) => setWrapperRef(task.uuid, el as Element | null)"
      class="task-card-wrapper"
      :class="{
        selected: selectedIds?.includes(task.uuid),
        dragging: drag.uuid === task.uuid,
        stacked: stackEntry(task).total > 1,
        'stack-under': stackEntry(task).stackIndex > 0,
      }"
      :style="taskStyle(task)"
      @pointerdown="(e: PointerEvent) => onPointerDown(e, task.uuid)"
    >
      <TaskCard
        :task="task"
        :density="density"
        :dimmed="store.isDimmed(task)"
        @click="(t: TaskOut) => handleTaskClick(t as TaskEx)"
        @complete="(t: TaskOut) => emit('task-complete', t as TaskEx)"
        @delete="(t: TaskOut) => emit('task-delete', t as TaskEx)"
        @contextmenu="(t: TaskOut) => emit('select-toggle', t.uuid)"
      />
      <!-- 堆叠指示 —— 仅在顶部卡片左上角显示，避免遮挡完成按钮 -->
      <span
        v-if="stackEntry(task).total > 1 && stackEntry(task).stackIndex === 0"
        class="stack-badge"
      >×{{ stackEntry(task).total }}</span>
      <!-- 拖拽 level 指示徽标 -->
      <div v-if="drag.uuid === task.uuid && drag.active" class="drag-level-badge">
        I{{ drag.snappedI }} · U{{ drag.snappedU }}
      </div>
    </div>

    <!-- 坐标轴覆盖层 -->
    <div class="axis-overlay">
      <div class="axis-h-line" />
      <div class="axis-v-line" />
      <span class="ax-label ax-top">重要 ↑</span>
      <span class="ax-label ax-bottom">不重要 ↓</span>
      <span class="ax-label ax-left">← 不紧急</span>
      <span class="ax-label ax-right">紧急 →</span>
    </div>

    <!-- 批量模式操作栏 -->
    <div v-if="selectMode && (selectedIds?.length ?? 0) > 0" class="batch-bar">
      <span class="batch-count">已选 {{ selectedIds?.length }} 项</span>
      <div class="batch-actions">
        <button class="batch-btn" @click="emit('task-complete', null as any)">
          <svg viewBox="0 0 16 16" width="14" height="14"><path d="M3 8l3 3 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg>
          完成
        </button>
        <button class="batch-btn danger" @click="emit('task-delete', null as any)">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 5h10M6 5V3h4v2M5 5v7a1 1 0 001 1h4a1 1 0 001-1V5"/></svg>
          删除
        </button>
      </div>
      <button class="batch-cancel" @click="emit('select-toggle', '')">取消</button>
    </div>
  </div>
</template>

<style scoped>
.quadrant-canvas {
  position: relative;
  height: 100%;
  width: 100%;
}

/* ── 象限网格（仅背景） ── */
.quadrant-grid {
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  pointer-events: none;
}

.quadrant-pane {
  position: relative;
  border: 0.5px solid var(--c-gray-200);
  overflow: hidden;
  pointer-events: none;
}

/* ── 始终可见的象限标签 ── */
.quadrant-label {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 2;
  pointer-events: none;
  opacity: 0.55;
}

.ql-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-gray-700);
  letter-spacing: 0.02em;
}

.ql-sub {
  font-size: 11px;
  font-weight: 500;
  color: var(--c-gray-500);
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 8px;
  border-radius: 10px;
}

:root.dark .ql-sub {
  background: rgba(255, 255, 255, 0.08);
}

.quadrant-content {
  position: relative;
  height: 100%;
  width: 100%;
}

/* ── 任务卡片 wrapper ── */
.task-card-wrapper {
  position: absolute;
  touch-action: none;
  cursor: grab;
  transform: translate(-50%, -50%);
}
.task-card-wrapper :deep(.task-card) {
  display: block;
}
.task-card-wrapper:hover { z-index: 100 !important; }
.task-card-wrapper.dragging {
  cursor: grabbing;
  transition: none !important;
}
.task-card-wrapper.dragging :deep(.task-card) {
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18), 0 0 0 2px var(--c-brand-500);
  cursor: grabbing;
}
.task-card-wrapper.selected :deep(.task-card) {
  outline: 2px solid var(--c-brand-500);
  outline-offset: 1px;
}

/* 卡片拖拽过程中，允许 quadrant-pane 显示该卡片 */
.quadrant-canvas.is-dragging .quadrant-pane {
  overflow: visible;
}

/* ── 空区域 ── */
.empty-area {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}

.empty-hint {
  color: var(--c-gray-600);
  font-size: 13px;
  margin: 0;
}

.empty-desc {
  color: var(--c-gray-500);
  font-size: 11px;
  margin: 4px 0 0;
}

/* ── 坐标轴覆盖层 ── */
.axis-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 5;
}

.axis-h-line {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 2px;
  background: var(--c-gray-200);
  transform: translateY(-1px);
}

.axis-v-line {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 2px;
  background: var(--c-gray-200);
  transform: translateX(-1px);
}

.ax-label {
  position: absolute;
  font-size: 11px;
  font-weight: 600;
  color: var(--c-gray-500);
  letter-spacing: 0.03em;
  background: var(--glass-bg-light);
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
}

.ax-top    { top: 8px;    left: 50%; transform: translateX(-50%); }
.ax-bottom { bottom: 8px; left: 50%; transform: translateX(-50%); }
.ax-left   { left: 8px;   top: 50%;  transform: translateY(-50%); }
.ax-right  { right: 8px;  top: 50%;  transform: translateY(-50%); }

/* ── 批量操作栏 ── */
.batch-bar {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--c-gray-900);
  color: #fff;
  border-radius: 12px;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 50;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.2s var(--ease-spring);
}

@keyframes slideUp {
  from { transform: translateX(-50%) translateY(20px); opacity: 0; }
  to   { transform: translateX(-50%) translateY(0);    opacity: 1; }
}

.batch-count  { font-size: 13px; font-weight: 500; white-space: nowrap; }
.batch-actions { display: flex; gap: 6px; }

.batch-btn {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: background 0.12s;
}
.batch-btn:hover { background: rgba(255, 255, 255, 0.2); }
.batch-btn.danger:hover { background: #DC2626; border-color: #DC2626; }

.batch-cancel {
  padding: 4px 6px;
  border: none;
  background: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
  cursor: pointer;
}
.batch-cancel:hover { color: #fff; }

/* ── 拖拽 level 徽标 ── */
/* ── 堆叠徽标 ── */
.stack-badge {
  position: absolute;
  top: -7px;
  left: -7px;
  min-width: 18px;
  height: 18px;
  border-radius: 9px;
  background: var(--c-gray-800);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
  z-index: 50;
  pointer-events: none;
  box-shadow: 0 1px 4px rgba(0,0,0,0.15);
}

/* ── 拖拽 level 徽标 ── */
.drag-level-badge {
  position: absolute;
  bottom: -24px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--surface-primary);
  border: 1px solid var(--c-gray-200);
  border-radius: 10px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 500;
  color: var(--c-gray-600);
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 101;
}

/* 移动端适配 */
@media (max-width: 767px) {
  .ax-label {
    font-size: 8px;
    padding: 0px 3px;
    border-radius: 3px;
  }

  .ax-top    { top: 2px; }
  .ax-bottom { bottom: 2px; }
  .ax-left   { left: 2px; }
  .ax-right  { right: 2px; }

  .axis-h-line, .axis-v-line {
    opacity: 0.5;
  }

  .quadrant-label { top: 4px; gap: 4px; }
  .ql-name { font-size: 11px; }
  .ql-sub  { font-size: 9px; padding: 1px 5px; }

  .empty-hint { font-size: 11px; }
  .empty-desc { font-size: 10px; }

  .batch-bar {
    bottom: 6px;
    padding: 5px 10px;
    gap: 6px;
    border-radius: 10px;
  }

  .batch-count  { font-size: 11px; }
  .batch-btn    { padding: 3px 7px; font-size: 10px; }
  .batch-cancel { font-size: 10px; }

  .drag-level-badge {
    font-size: 9px;
    padding: 1px 5px;
    bottom: -18px;
  }

  .stack-badge {
    top: -5px;
    left: -5px;
    min-width: 14px;
    height: 14px;
    font-size: 8px;
    padding: 0 3px;
  }
}
</style>
