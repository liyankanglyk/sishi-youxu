<script setup lang="ts">
import { onMounted, onUnmounted, watch, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useUiStore } from '@/stores/ui'
import { useKeyboard } from '@/composables/useKeyboard'
import { useToast } from '@/composables/useToast'
import { useNotification } from '@/composables/useNotification'
import QuadrantCanvas from '@/components/task/QuadrantCanvas.vue'
import TaskList from '@/components/task/TaskList.vue'
import StatsPanel from '@/components/task/StatsPanel.vue'
import TaskModal from '@/components/task/TaskModal.vue'
import type { TaskEx } from '@/stores/task'

const route = useRoute()
const store = useTaskStore()
const ui = useUiStore()
const toast = useToast()

useKeyboard()

// ── 通知系统 ──
const notif = useNotification(() => store.serverTasks)
if (notif.enabled.value && Notification.permission === 'granted') {
  notif.startPolling()
}

// 让通知组合函数与 ui store 的开关保持同步
watch(() => ui.notificationsEnabled, (val) => {
  notif.setEnabled(val)
})

// ── 可调节宽度的侧边栏 ──
const isResizing = ref(false)
const resizeRef = ref<HTMLElement | null>(null)

function onResizeStart(e: MouseEvent | TouchEvent) {
  e.preventDefault()
  isResizing.value = true
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'

  const onMove = (clientX: number) => {
    if (!isResizing.value) return
    const min = 200
    const max = window.innerWidth * 0.5
    ui.leftSidebarWidth = Math.max(min, Math.min(max, clientX))
  }

  const onMouseMove = (ev: MouseEvent) => onMove(ev.clientX)
  const onTouchMove = (ev: TouchEvent) => onMove(ev.touches[0].clientX)
  const onEnd = () => {
    isResizing.value = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onEnd)
    document.removeEventListener('touchmove', onTouchMove)
    document.removeEventListener('touchend', onEnd)
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onEnd)
  document.addEventListener('touchmove', onTouchMove)
  document.addEventListener('touchend', onEnd)
}

// ── 导入 ──
type ImportStrategy = 'skip' | 'overwrite' | 'new'
const importFile = ref<File | null>(null)
const importStrategy = ref<ImportStrategy>('skip')
const importResult = ref<{ importedTasks: number; importedTags: number; skippedTasks: number; skippedTags: number } | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

watch(() => ui.importTrigger, () => {
  fileInputRef.value?.click()
})

onMounted(async () => {
  await store.fetchFromServer()
})

onUnmounted(() => {
  notif.stopPolling()
})

watch(() => route.query.q, (q) => {
  store.setSearchQuery((q as string) || '')
}, { immediate: true })

function handleTaskClick(task: TaskEx) {
  store.setEditingUuid(task.uuid)
}

async function handleTaskComplete(task: TaskEx | null) {
  if (!task) { store.batchComplete(); return }
  await store.completeTask(task.uuid)
  if (store.celebrationTitle) {
    toast.success(`已完成「${store.celebrationTitle}」`)
  }
}

async function handleTaskDelete(task: TaskEx | null) {
  if (!task) {
    if (!confirm(`确定删除选中的 ${store.selectedTaskIds.length} 个任务？`)) return
    store.batchDelete()
    return
  }
  if (!confirm(`删除任务「${task.title}」？`)) return
  try { await store.deleteTask(task.uuid) } catch (e: any) { toast.error(e.message || '删除失败') }
}

function handleSelectToggle(uuid: string) {
  if (!uuid) store.clearSelection()
  else store.toggleSelectTask(uuid)
}

function handleCanvasDblClick(urgencyLevel: number, importanceLevel: number) {
  store.setCreating(true, urgencyLevel, importanceLevel)
}

function handleCloseModal() {
  store.setCreating(false)
  store.setEditingUuid(null)
}

function handleFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) {
    importFile.value = file
    importResult.value = null
  }
  if (fileInputRef.value) fileInputRef.value.value = ''
}

async function handleImportConfirm() {
  if (!importFile.value) return
  try {
    const text = await importFile.value.text()
    const data = JSON.parse(text)
    if (!data.tasks || !Array.isArray(data.tasks)) { toast.error('无效的备份文件'); return }

    let importedTasks = 0; let skippedTasks = 0
    for (const t of data.tasks) {
      try {
        if (importStrategy.value === 'skip') {
          const exists = store.serverTasks.some(existing => existing.title === t.title && existing.dueDate === t.dueDate)
          if (exists) { skippedTasks++; continue }
        }
        if (importStrategy.value === 'overwrite') {
          const existing = store.serverTasks.find(existing => existing.title === t.title && existing.dueDate === t.dueDate)
          if (existing) {
            await store.updateTask(existing.uuid, { title: t.title, urgencyLevel: t.urgencyLevel ?? 0, importanceLevel: t.importanceLevel ?? 0, dueDate: t.dueDate ?? null, note: t.note ?? null })
            importedTasks++; continue
          }
        }
        await store.createTask({ title: t.title, urgencyLevel: t.urgencyLevel ?? 0, importanceLevel: t.importanceLevel ?? 0, dueDate: t.dueDate ?? null, recurrence: t.recurrence ?? null, note: t.note ?? null, tags: t.tags ?? [] })
        importedTasks++
      } catch { skippedTasks++ }
    }
    importResult.value = { importedTasks, importedTags: 0, skippedTasks, skippedTags: 0 }
    store.fetchFromServer()
  } catch { toast.error('解析文件失败') }
}

function handleImportCancel() {
  importFile.value = null
  importResult.value = null
}

function handleImportDismiss() {
  importFile.value = null
  importResult.value = null
}
</script>

<template>
  <div class="home-layout">
    <TaskModal
      :visible="store.isCreating || !!store.editingTaskUuid"
      :task-uuid="store.editingTaskUuid"
      :create-urgency-level="store.createUrgencyLevel"
      :create-importance-level="store.createImportanceLevel"
      @close="handleCloseModal"
    />

    <!-- 隐藏的文件输入框，用于导入 -->
    <input ref="fileInputRef" type="file" accept=".json,application/json" class="hidden-input" @change="handleFileChange" />

    <!-- 主行：左侧栏 | 画布 | 右侧栏 -->
    <div class="home-body" :class="{ 'is-mobile': ui.isMobile }">
      <!-- 桌面端：内联 TaskList -->
      <template v-if="!ui.isMobile">
        <Transition name="slide-left">
          <TaskList v-if="ui.leftSidebarWidth > 0" :style="{ width: ui.leftSidebarWidth + 'px' }" />
        </Transition>

        <div
          v-if="ui.leftSidebarWidth > 0"
          ref="resizeRef"
          class="resize-handle"
          @mousedown="onResizeStart"
          @touchstart="onResizeStart"
        >
          <div class="resize-grip" />
        </div>
      </template>

      <div class="canvas-area">
        <QuadrantCanvas
          :density="store.viewDensity"
          :select-mode="store.isSelectMode"
          :selected-ids="store.selectedTaskIds"
          @task-click="handleTaskClick"
          @task-complete="handleTaskComplete"
          @task-delete="handleTaskDelete"
          @select-toggle="handleSelectToggle"
          @double-click="handleCanvasDblClick"
        />
      </div>

      <!-- 桌面端：内联 StatsPanel -->
      <template v-if="!ui.isMobile">
        <Transition name="slide-right">
          <StatsPanel v-if="ui.showStatsPanel" />
        </Transition>
      </template>
    </div>

    <!-- 移动端：浮层抽屉（Teleport 到 body） -->
    <template v-if="ui.isMobile">
      <Teleport to="body">
        <!-- TaskList 抽屉 -->
        <Transition name="drawer-left">
          <div v-if="ui.showMobileTaskList" class="mobile-drawer">
            <div class="mobile-drawer-scrim" @click="ui.closeMobileTaskList()" />
            <TaskList class="mobile-drawer-panel mobile-drawer-left" @task-click="ui.closeMobileTaskList()" />
          </div>
        </Transition>

        <!-- StatsPanel 抽屉 -->
        <Transition name="drawer-right">
          <div v-if="ui.showMobileStatsPanel" class="mobile-drawer">
            <div class="mobile-drawer-scrim" @click="ui.closeMobileStatsPanel()" />
            <StatsPanel class="mobile-drawer-panel mobile-drawer-right" />
          </div>
        </Transition>
      </Teleport>
    </template>

    <!-- 导入策略对话框 -->
    <div v-if="importFile && !importResult" class="dialog-overlay" @click.self="handleImportCancel">
      <div class="import-dialog">
        <h2 class="import-title">导入备份</h2>
        <p class="import-file-name">文件：{{ importFile.name }}</p>

        <div class="import-options">
          <label class="import-option" v-for="opt in [
            { value: 'skip' as ImportStrategy, title: '跳过已有任务', desc: '相同标题+日期的任务不覆盖，保留现有数据' },
            { value: 'overwrite' as ImportStrategy, title: '覆盖已有任务', desc: '相同标题+日期的任务用导入数据替换' },
            { value: 'new' as ImportStrategy, title: '全部作为新任务', desc: '所有任务直接创建，不检测重复' },
          ]" :key="opt.value">
            <input type="radio" name="importStrategy" :value="opt.value" v-model="importStrategy" />
            <div>
              <div class="opt-title">{{ opt.title }}</div>
              <div class="opt-desc">{{ opt.desc }}</div>
            </div>
          </label>
        </div>

        <div class="import-actions">
          <button class="cancel-btn" @click="handleImportCancel">取消</button>
          <button class="submit-btn" @click="handleImportConfirm">确认导入</button>
        </div>
      </div>
    </div>

    <!-- 导入结果对话框 -->
    <div v-if="importResult && importFile" class="dialog-overlay" @click.self="handleImportDismiss">
      <div class="import-dialog import-result">
        <div class="result-icon">✅</div>
        <h2 class="import-title">导入完成</h2>
        <div class="result-stats">
          <p>任务：导入 {{ importResult.importedTasks }} 个，跳过 {{ importResult.skippedTasks }} 个</p>
        </div>
        <button class="submit-btn" style="margin-top: 16px; width: 100%;" @click="handleImportDismiss">知道了</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* ── 主体：侧边栏 + 画布 ── */
.home-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

.canvas-area {
  flex: 1;
  position: relative;
  overflow: hidden;
  min-width: 0;
}

/* ── 侧边栏过渡动画 ── */
.slide-left-enter-active,
.slide-left-leave-active {
  transition: width 0.2s ease, opacity 0.15s ease;
  overflow: hidden;
}
.slide-left-enter-from,
.slide-left-leave-to {
  width: 0 !important;
  opacity: 0;
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: width 0.2s ease, opacity 0.15s ease;
  overflow: hidden;
}
.slide-right-enter-from,
.slide-right-leave-to {
  width: 0 !important;
  opacity: 0;
}

/* ── 拖拽调整宽度把手 ── */
.hidden-input { display: none; }

.resize-handle {
  width: 6px;
  flex-shrink: 0;
  height: 100%;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: transparent;
  transition: background 0.15s;
  z-index: 10;
}
.resize-handle:hover { background: rgba(46, 91, 255, 0.06); }

.resize-grip {
  width: 2px;
  height: 32px;
  border-radius: 1px;
  background: var(--c-gray-300);
  transition: background 0.15s, height 0.15s;
}
.resize-handle:hover .resize-grip {
  background: var(--c-brand-500);
  height: 48px;
}

/* ── 导入对话框 ── */
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.import-dialog {
  background: var(--surface-primary);
  border-radius: var(--r-modal);
  padding: 24px;
  width: 100%;
  max-width: 400px;
  box-shadow: var(--sh-modal);
}

.import-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--c-gray-900);
  margin: 0 0 4px;
}

.import-file-name {
  font-size: 12px;
  color: var(--c-gray-400);
  margin: 0 0 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.import-option {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: var(--c-gray-50);
  border-radius: var(--r-card);
  cursor: pointer;
  transition: background 0.15s;
}
.import-option:hover { background: var(--c-gray-100); }
.import-option input[type="radio"] { accent-color: var(--c-brand-500); margin-top: 2px; }

.opt-title { font-size: 14px; font-weight: 500; color: var(--c-gray-700); }
.opt-desc { font-size: 11px; color: var(--c-gray-400); margin-top: 2px; }

.import-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.import-result { text-align: center; }
.result-icon { font-size: 40px; margin-bottom: 8px; }
.result-stats {
  text-align: center;
  font-size: 14px;
  color: var(--c-gray-500);
  line-height: 1.6;
}

.cancel-btn {
  padding: 8px 18px;
  background: var(--c-gray-100);
  color: var(--c-gray-600);
  border: none;
  border-radius: var(--r-button);
  font-size: 14px;
  cursor: pointer;
}
.cancel-btn:hover { background: var(--c-gray-200); }

.submit-btn {
  padding: 8px 24px;
  background: var(--c-brand-500);
  color: #fff;
  border: none;
  border-radius: var(--r-button);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
.submit-btn:hover { background: var(--c-brand-600); }

/* ══════════════════════════════════════════ */
/* 移动端抽屉                                */
/* ══════════════════════════════════════════ */

.mobile-drawer {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
}

.mobile-drawer-scrim {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
}

.mobile-drawer-panel {
  position: relative;
  width: min(320px, 85vw);
  height: 100%;
  z-index: 1;
  background: var(--surface-primary);
  overflow-y: auto;
}

.mobile-drawer-right {
  margin-left: auto;
}

.mobile-drawer-panel :deep(.task-list-panel),
.mobile-drawer-panel :deep(.stats-panel) {
  width: 100% !important;
  border: none;
  height: 100%;
}

/* 左侧抽屉滑入过渡 */
.drawer-left-enter-active,
.drawer-left-leave-active {
  transition: opacity 0.25s ease;
}
.drawer-left-enter-active .mobile-drawer-scrim,
.drawer-left-leave-active .mobile-drawer-scrim {
  transition: opacity 0.25s ease;
}
.drawer-left-enter-active .mobile-drawer-panel,
.drawer-left-leave-active .mobile-drawer-panel {
  transition: transform 0.25s var(--ease-standard);
}
.drawer-left-enter-from,
.drawer-left-leave-to {
  opacity: 0;
}
.drawer-left-enter-from .mobile-drawer-scrim,
.drawer-left-leave-to .mobile-drawer-scrim {
  opacity: 0;
}
.drawer-left-enter-from .mobile-drawer-panel,
.drawer-left-leave-to .mobile-drawer-panel {
  transform: translateX(-100%);
}

/* 右侧抽屉滑入过渡 */
.drawer-right-enter-active,
.drawer-right-leave-active {
  transition: opacity 0.25s ease;
}
.drawer-right-enter-active .mobile-drawer-scrim,
.drawer-right-leave-active .mobile-drawer-scrim {
  transition: opacity 0.25s ease;
}
.drawer-right-enter-active .mobile-drawer-panel,
.drawer-right-leave-active .mobile-drawer-panel {
  transition: transform 0.25s var(--ease-standard);
}
.drawer-right-enter-from,
.drawer-right-leave-to {
  opacity: 0;
}
.drawer-right-enter-from .mobile-drawer-scrim,
.drawer-right-leave-to .mobile-drawer-scrim {
  opacity: 0;
}
.drawer-right-enter-from .mobile-drawer-panel,
.drawer-right-leave-to .mobile-drawer-panel {
  transform: translateX(100%);
}

/* 在移动端隐藏拖拽调整宽度把手 */
@media (max-width: 767px) {
  .resize-handle { display: none !important; }

  .import-dialog {
    max-width: 100%;
    border-radius: var(--r-modal) var(--r-modal) 0 0;
    padding: 20px 16px;
  }

  .dialog-overlay {
    align-items: flex-end;
  }

  .import-option {
    padding: 10px;
    gap: 8px;
  }

  .opt-title { font-size: 13px; }
  .opt-desc { font-size: 10px; }
}
</style>
