<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { marked } from 'marked'
import AppModal from '@/components/common/AppModal.vue'
import { taskApi, type TaskOut } from '@/api/tasks'
import { tagApi } from '@/api/tags'
import type { TagOut } from '@/api/tags'
import { useTaskStore } from '@/stores/task'
import { useToast } from '@/composables/useToast'

const toast = useToast()

const props = defineProps<{
  visible: boolean
  taskUuid: string | null
  createUrgencyLevel?: number
  createImportanceLevel?: number
}>()

const emit = defineEmits<{ close: [] }>()

const taskStore = useTaskStore()

// ── 表单状态 ──
const title = ref('')
const urgencyLevel = ref(0)
const importanceLevel = ref(0)
const dueDate = ref('')
const recurrence = ref('')
const note = ref('')
const selectedTags = ref<string[]>([])
const checklist = ref<Array<{ uuid: string; title: string; completed: boolean; _new?: boolean }>>([])

const loading = ref(false)
const saving = ref(false)
const isEdit = computed(() => !!props.taskUuid)

// ── Markdown 预览 ──
const notePreview = ref(false)
const renderedNote = computed(() => {
  if (!note.value.trim()) return ''
  try { return marked.parse(note.value) as string } catch { return note.value }
})

// ── 内联创建标签 ──
const isNewTagOpen = ref(false)
const newTagName = ref('')
const newTagColor = ref('#6366f1')
const newTagSaving = ref(false)
const presetColors = ['#007AFF', '#34C759', '#5856D6', '#FF9500', '#FFCC00', '#5AC8FA', '#FF2D55', '#AF52DE']

async function createTagInline() {
  if (!newTagName.value.trim()) return
  newTagSaving.value = true
  try {
    const { data } = await tagApi.create({ name: newTagName.value.trim(), color: newTagColor.value })
    if (data) {
      tagOptions.value.push(data)
      selectedTags.value.push(data.uuid)
    }
    newTagName.value = ''
    newTagColor.value = '#6366f1'
    isNewTagOpen.value = false
  } catch (e: any) {
    toast.error(e.message || '创建标签失败')
  } finally { newTagSaving.value = false }
}

// 标签选项（从服务器加载）
const tagOptions = ref<TagOut[]>([])

// 象限选择
function selectQuadrant(u: number, i: number) {
  urgencyLevel.value = u
  importanceLevel.value = i
}

function quadrantLabel(u: number, i: number): string {
  if (i >= 0 && u >= 0) return 'Q1 重要且紧急'
  if (i >= 0 && u < 0) return 'Q2 重要不紧急'
  if (i < 0 && u >= 0) return 'Q3 不重要紧急'
  return 'Q4 不重要不紧急'
}

const currentQuadrantLabel = computed(() => quadrantLabel(urgencyLevel.value, importanceLevel.value))

// ── 加载任务数据 ──
watch(() => [props.visible, props.taskUuid], async ([vis, uuid]) => {
  if (!vis) return
  resetForm()
  try {
    loading.value = true
    const [tagData] = await Promise.all([
      tagApi.list(),
    ])
    tagOptions.value = tagData.data?.items ?? []

    if (uuid) {
      const { data } = await taskApi.get(uuid as string)
      populateFromTask(data)
    }
  } catch (e: any) {
    toast.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}, { immediate: false })

function resetForm() {
  title.value = ''
  urgencyLevel.value = props.createUrgencyLevel ?? 0
  importanceLevel.value = props.createImportanceLevel ?? 0
  dueDate.value = ''
  recurrence.value = ''
  note.value = ''
  selectedTags.value = []
  checklist.value = []
}

function populateFromTask(task: TaskOut) {
  title.value = task.title
  urgencyLevel.value = task.urgencyLevel
  importanceLevel.value = task.importanceLevel
  dueDate.value = task.dueDate?.slice(0, 10) ?? ''
  recurrence.value = task.recurrence ?? ''
  note.value = task.note ?? ''
  const tags = task.tags
  if (tags && tags.length && typeof tags[0] !== 'string') {
    selectedTags.value = (tags as { uuid: string; name: string; color: string }[]).map(t => t.uuid)
  }
  loadChecklist(task.uuid)
}

async function loadChecklist(taskUuid: string) {
  try {
    const { data } = await taskApi.listChecklist(taskUuid)
    checklist.value = (data?.items ?? []).map(c => ({ ...c, _new: false }))
  } catch {
    checklist.value = []
  }
}

// ── 标签选择 ──
function toggleTag(uuid: string) {
  const idx = selectedTags.value.indexOf(uuid)
  if (idx >= 0) selectedTags.value.splice(idx, 1)
  else selectedTags.value.push(uuid)
}

function isTagSelected(uuid: string) {
  return selectedTags.value.includes(uuid)
}

// ── 检查项 ──
function addChecklistItem() {
  const uuid = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)
  checklist.value.push({ uuid, title: '', completed: false, _new: true })
}

function removeChecklistItem(idx: number) {
  checklist.value.splice(idx, 1)
}

// ── 提交 ──
async function handleSubmit() {
  if (!title.value.trim()) {
    toast.warning('请输入任务标题')
    return
  }
  saving.value = true
  try {
    const payload: any = {
      title: title.value.trim(),
      urgencyLevel: urgencyLevel.value,
      importanceLevel: importanceLevel.value,
      dueDate: dueDate.value || null,
      recurrence: recurrence.value || null,
      note: note.value || null,
      tags: selectedTags.value.length ? selectedTags.value : undefined,
    }

    let savedTask: TaskOut
    if (isEdit.value) {
      const { data } = await taskApi.update(props.taskUuid!, payload)
      savedTask = data
    } else {
      const { data } = await taskApi.create(payload)
      savedTask = data
    }

    // 同步检查项变更
    if (savedTask.uuid) {
      for (const item of checklist.value) {
        if (item._new && item.title.trim()) {
          await taskApi.createChecklistItem(savedTask.uuid, { title: item.title.trim() })
        } else if (!item._new) {
          // 同步已有项的完成状态
          await taskApi.updateChecklistItem(savedTask.uuid, item.uuid, {
            title: item.title,
            completed: item.completed,
          }).catch(() => {})
        }
      }
    }

    toast.success(isEdit.value ? '已更新' : '已创建')
    emit('close')
    taskStore.fetchFromServer()
  } catch (e: any) {
    toast.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function handleClose() {
  emit('close')
}
</script>

<template>
  <AppModal
    :visible="visible"
    :title="isEdit ? '编辑任务' : '新建任务'"
    width="520px"
    @close="handleClose"
  >
    <div class="task-form">
      <div v-if="loading" class="loading-overlay">
        <span class="spinner" />
      </div>
      <!-- 标题 -->
      <div class="field">
        <label class="field-label">标题</label>
        <input
          v-model="title"
          type="text"
          class="field-input"
          placeholder="周二产品评审会议准备"
          maxlength="200"
          ref="titleInput"
        />
      </div>

      <!-- 象限选择器 -->
      <div class="field">
        <label class="field-label">象限位置</label>
        <div class="quadrant-picker">
          <div
            v-for="(q, idx) in [
              { u: -2, i: 2, label: 'Q2', sub: '重要不紧急', bg: 'var(--q2-bg)' },
              { u: 2, i: 2, label: 'Q1', sub: '重要且紧急', bg: 'var(--q1-bg)' },
              { u: -2, i: -2, label: 'Q4', sub: '不重要不紧急', bg: 'var(--q4-bg)' },
              { u: 2, i: -2, label: 'Q3', sub: '不重要紧急', bg: 'var(--q3-bg)' },
            ]"
            :key="idx"
            class="qp-cell"
            :class="{ active: (q.u >= 0) === (urgencyLevel >= 0) && (q.i >= 0) === (importanceLevel >= 0) }"
            :style="{ backgroundColor: q.bg }"
            @click="selectQuadrant(q.u, q.i)"
          >
            <span class="qp-label">{{ q.label }}</span>
            <span class="qp-sub">{{ q.sub }}</span>
          </div>
        </div>
        <div class="level-sliders">
          <div class="level-row">
            <label class="level-label">紧急度 ({{ urgencyLevel }})</label>
            <input
              type="range"
              min="-4" max="4" step="1"
              :value="urgencyLevel"
              @input="(e) => urgencyLevel = parseInt((e.target as HTMLInputElement).value)"
              class="level-range"
            />
          </div>
          <div class="level-row">
            <label class="level-label">重要度 ({{ importanceLevel }})</label>
            <input
              type="range"
              min="-4" max="4" step="1"
              :value="importanceLevel"
              @input="(e) => importanceLevel = parseInt((e.target as HTMLInputElement).value)"
              class="level-range"
            />
          </div>
        </div>
        <p class="field-hint">{{ currentQuadrantLabel }}</p>
      </div>

      <!-- 截止日期 + 重复规则 -->
      <div class="field-row">
        <div class="field" style="flex:1">
          <label class="field-label">截止日期</label>
          <input v-model="dueDate" type="date" class="field-input" />
        </div>
        <div class="field" style="flex:1">
          <label class="field-label">重复规则</label>
          <select v-model="recurrence" class="field-input select">
            <option value="">不重复</option>
            <option value="daily">每天</option>
            <option value="weekdays">工作日</option>
            <option value="weekly">每周</option>
            <option value="biweekly">每两周</option>
            <option value="monthly">每月</option>
          </select>
        </div>
      </div>

      <!-- 标签 -->
      <div class="field">
        <label class="field-label">标签</label>
        <div class="tag-grid">
          <button
            v-for="tag in tagOptions"
            :key="tag.uuid"
            type="button"
            class="tag-option"
            :class="{ selected: isTagSelected(tag.uuid) }"
            :style="isTagSelected(tag.uuid)
              ? { backgroundColor: tag.color + '1A', borderColor: tag.color + '4D', color: tag.color }
              : {}"
            @click="toggleTag(tag.uuid)"
          >
            {{ tag.name }}
          </button>
          <button
            type="button"
            class="tag-option new-tag-btn"
            @click="isNewTagOpen = !isNewTagOpen"
          >
            + 新建
          </button>
        </div>
        <!-- 内联创建标签 -->
        <div v-if="isNewTagOpen" class="inline-tag-form">
          <div class="color-options">
            <button
              v-for="c in presetColors"
              :key="c"
              class="color-swatch"
              :class="{ active: newTagColor === c }"
              :style="{ backgroundColor: c }"
              @click="newTagColor = c"
            />
            <input type="color" v-model="newTagColor" class="color-picker" />
          </div>
          <div class="inline-tag-input-row">
            <input
              v-model="newTagName"
              type="text"
              class="field-input"
              placeholder="标签名称"
              maxlength="50"
              @keydown.enter="createTagInline"
            />
            <button
              type="button"
              class="add-tag-btn"
              :disabled="newTagSaving || !newTagName.trim()"
              @click="createTagInline"
            >
              {{ newTagSaving ? '...' : '添加' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 检查项 -->
      <div class="field">
        <div class="field-label-row">
          <label class="field-label">检查项</label>
          <button type="button" class="add-item-btn" @click="addChecklistItem">+ 添加</button>
        </div>
        <div v-if="checklist.length" class="checklist-items">
          <div v-for="(item, idx) in checklist" :key="item.uuid" class="checklist-row">
            <input
              type="checkbox"
              class="checklist-checkbox"
              :checked="item.completed"
              @change="item.completed = ($event.target as HTMLInputElement).checked"
            />
            <input
              v-model="item.title"
              type="text"
              class="checklist-input"
              :class="{ done: item.completed }"
              placeholder="子任务内容"
            />
            <button type="button" class="remove-btn" @click="removeChecklistItem(idx)">&times;</button>
          </div>
        </div>
        <p v-else class="field-hint">将复杂任务拆分为小步骤</p>
      </div>

      <!-- 备注 -->
      <div class="field">
        <div class="field-label-row">
          <label class="field-label">
            备注
            <span class="label-hint">支持 Markdown</span>
          </label>
          <button type="button" class="preview-toggle" @click="notePreview = !notePreview">
            {{ notePreview ? '编辑' : '预览' }}
          </button>
        </div>
        <div v-if="notePreview" class="note-preview" v-html="renderedNote || '<em style=\'color:var(--c-gray-300)\'>暂无内容</em>'"></div>
        <textarea
          v-else
          v-model="note"
          class="field-input note-input"
          placeholder="补充说明（支持 Markdown 语法）"
          rows="3"
        />
      </div>
    </div>

    <template #footer>
      <button class="cancel-btn" @click="handleClose">取消</button>
      <button
        class="submit-btn"
        :disabled="saving"
        @click="handleSubmit"
      >
        {{ saving ? '保存中...' : isEdit ? '保存' : '创建' }}
      </button>
    </template>
  </AppModal>
</template>

<style scoped>
.task-form {
  display: flex;
  flex-direction: column;
  gap: var(--s-4);
  position: relative;
}

.loading-overlay {
  position: absolute;
  inset: 0;
  background: var(--glass-bg-light);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
  border-radius: var(--r-modal);
}

.field { display: flex; flex-direction: column; gap: 6px; }
.field-label {
  font-size: var(--t-caption-size);
  font-weight: 600;
  color: var(--c-gray-600);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.field-hint { font-size: 12px; color: var(--c-gray-400); margin: 0; }

.field-input {
  padding: 8px 12px;
  border: 1px solid var(--c-gray-300);
  border-radius: var(--r-input);
  font-size: var(--t-body-size);
  outline: none;
  transition: border-color 0.2s var(--ease-standard);
  background: var(--surface-primary);
  color: var(--c-gray-900);
}
.field-input:focus { border-color: var(--c-brand-500); }
.field-input.select {
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 16 16' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M4 6l4 4 4-4' stroke='%2371717A' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  background-size: 16px;
  padding-right: 28px;
  cursor: pointer;
}

.field-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.add-item-btn {
  font-size: 13px;
  color: var(--c-brand-500);
  border: none;
  background: none;
  cursor: pointer;
  font-weight: 500;
}
.add-item-btn:hover { text-decoration: underline; }

.field-row { display: flex; gap: var(--s-3); }

/* 象限选择器 */
.quadrant-picker {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  height: 140px;
  border-radius: var(--r-card);
  overflow: hidden;
  border: 1px solid var(--c-gray-200);
}
.qp-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: filter 0.15s, outline 0.15s;
  border: 2px solid transparent;
  user-select: none;
}
.qp-cell:hover { filter: brightness(0.92); }
.qp-cell.active {
  outline: 2px solid var(--c-brand-500);
  outline-offset: -2px;
  z-index: 1;
  border-color: var(--c-brand-500);
}
.qp-label { font-weight: 700; font-size: 1rem; color: var(--c-gray-700); }
.qp-sub { font-size: 11px; color: var(--c-gray-500); }

/* Level 滑块 */
.level-sliders {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.level-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.level-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--c-gray-600);
}

.level-range {
  width: 100%;
  accent-color: var(--c-brand-500);
}

/* 标签 */
.tag-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag-option {
  padding: 4px 10px;
  border-radius: var(--r-chip);
  font-size: 13px;
  border: 1px solid var(--c-gray-200);
  background: var(--surface-primary);
  cursor: pointer;
  transition: all 0.15s;
  color: var(--c-gray-600);
}
.tag-option:hover { border-color: var(--c-gray-400); }
.tag-option.selected { font-weight: 500; }

/* 检查项 */
.checklist-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.checklist-row {
  display: flex;
  gap: 6px;
  align-items: center;
}
.checklist-input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--c-gray-300);
  border-radius: var(--r-input);
  font-size: 14px;
  outline: none;
}
.checklist-input:focus { border-color: var(--c-brand-500); }

.checklist-checkbox {
  width: 18px;
  height: 18px;
  accent-color: var(--c-brand-500);
  cursor: pointer;
  flex-shrink: 0;
  margin: 0;
}
.checklist-input.done {
  text-decoration: line-through;
  color: var(--c-gray-400);
}

.remove-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  color: var(--c-gray-400);
  cursor: pointer;
  font-size: 18px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.remove-btn:hover { color: var(--c-danger); background: rgba(220, 38, 38, 0.08); }

/* 备注 */
.note-input {
  resize: vertical;
  min-height: 60px;
  font-family: inherit;
}

/* 底部按钮 */
.cancel-btn {
  padding: 8px 18px;
  background: var(--c-gray-100);
  color: var(--c-gray-600);
  border: none;
  border-radius: var(--r-button);
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s;
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
  transition: background 0.15s;
}
.submit-btn:hover:not(:disabled) { background: var(--c-brand-600); }
.submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── 内联创建标签 ── */
.tag-option.new-tag-btn {
  border-style: dashed;
  color: var(--c-gray-400);
  font-weight: 400;
}
.tag-option.new-tag-btn:hover {
  border-color: var(--c-brand-500);
  color: var(--c-brand-500);
}

.inline-tag-form {
  margin-top: 8px;
  padding: 12px;
  background: var(--c-gray-50);
  border-radius: var(--r-card);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.color-options {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}

.color-swatch {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  transition: transform 0.15s;
}
.color-swatch:hover { transform: scale(1.1); }
.color-swatch.active { border-color: var(--c-gray-900); transform: scale(1.15); }

:root.dark .color-swatch.active { border-color: var(--c-gray-100); }

.color-picker {
  width: 28px;
  height: 28px;
  border: none;
  cursor: pointer;
  border-radius: 50%;
  padding: 0;
  border: 1px solid var(--c-gray-300);
}

.inline-tag-input-row {
  display: flex;
  gap: 6px;
}

.inline-tag-input-row .field-input {
  flex: 1;
  padding: 6px 10px;
  font-size: 13px;
}

.add-tag-btn {
  padding: 6px 14px;
  border: none;
  background: var(--c-brand-500);
  color: #fff;
  border-radius: var(--r-button);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}
.add-tag-btn:hover:not(:disabled) { background: var(--c-brand-600); }
.add-tag-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Markdown 预览 ── */
.label-hint {
  font-size: 10px;
  font-weight: 400;
  color: var(--c-gray-400);
  margin-left: 4px;
  text-transform: none;
  letter-spacing: 0;
}

.preview-toggle {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--r-chip);
  border: 1px solid var(--c-gray-200);
  background: var(--surface-primary);
  color: var(--c-gray-500);
  cursor: pointer;
  transition: all 0.15s;
}
.preview-toggle:hover { border-color: var(--c-brand-500); color: var(--c-brand-500); }

.note-preview {
  padding: 10px 12px;
  border: 1px solid var(--c-gray-200);
  border-radius: var(--r-input);
  background: var(--c-gray-50);
  font-size: 14px;
  line-height: 1.6;
  color: var(--c-gray-700);
  min-height: 60px;
  overflow-y: auto;
}
.note-preview :deep(h1), .note-preview :deep(h2) { margin: 8px 0 4px; font-size: 1.1em; }
.note-preview :deep(p) { margin: 0 0 6px; }
.note-preview :deep(ul), .note-preview :deep(ol) { padding-left: 18px; margin: 4px 0; }
.note-preview :deep(code) {
  background: var(--c-gray-200);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 0.9em;
}
.note-preview :deep(pre) {
  background: var(--c-gray-200);
  padding: 8px;
  border-radius: var(--r-input);
  overflow-x: auto;
}
.note-preview :deep(blockquote) {
  border-left: 3px solid var(--c-gray-300);
  padding-left: 10px;
  color: var(--c-gray-500);
  margin: 6px 0;
}

/* 移动端优化 */
@media (max-width: 767px) {
  .task-form {
    gap: var(--s-2);
  }

  .field-row {
    flex-direction: column;
    gap: var(--s-2);
  }

  .quadrant-picker {
    height: 100px;
  }

  .qp-label {
    font-size: 0.85rem;
  }

  .qp-sub {
    font-size: 10px;
  }

  .level-sliders {
    gap: 4px;
    margin-top: 8px;
  }

  .field-label {
    font-size: 11px;
  }

  .field-input {
    padding: 7px 10px;
    font-size: 14px;
  }

  .tag-option {
    padding: 3px 8px;
    font-size: 12px;
  }

  .inline-tag-form {
    padding: 8px;
  }

  .note-preview {
    font-size: 13px;
    line-height: 1.5;
    min-height: 48px;
  }

  .cancel-btn,
  .submit-btn {
    padding: 8px 16px;
    font-size: 14px;
    flex: 1;
    text-align: center;
  }
}
</style>
