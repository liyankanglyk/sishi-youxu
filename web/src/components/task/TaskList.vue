<script setup lang="ts">
import { ref } from 'vue'
import { useTaskStore } from '@/stores/task'
import type { TaskEx } from '@/stores/task'
import TagChip from '@/components/common/TagChip.vue'

const store = useTaskStore()

const collapsedGroups = ref<Record<string, boolean>>({ Q2: false, Q1: false, Q4: false, Q3: false })
const showCompleted = ref(false)

const quadrantConfig: Record<string, { label: string; color: string }> = {
  Q1: { label: '重要且紧急', color: '#DC2626' },
  Q2: { label: '重要不紧急', color: '#16A34A' },
  Q3: { label: '不重要紧急', color: '#2563EB' },
  Q4: { label: '不重要不紧急', color: '#D97706' },
}

const quadrantsOrder = ['Q1', 'Q2', 'Q3', 'Q4']

function toggleGroup(q: string) {
  collapsedGroups.value[q] = !collapsedGroups.value[q]
}

function getTaskTags(task: TaskEx): { uuid: string; name: string; color: string }[] {
  const tt = task.tags
  if (!tt || !tt.length) return []
  if (typeof tt[0] === 'string') {
    return (tt as string[]).map(id => store.tags.find(t => t.uuid === id)).filter((t): t is NonNullable<typeof t> => !!t)
  }
  return tt as { uuid: string; name: string; color: string }[]
}

const WEEKDAY_NAMES = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

function formatDueDate(dueDate: string | null): { text: string; color: string } | null {
  if (!dueDate) return null
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const due = new Date(dueDate)
  const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate())
  const diffDays = Math.round((dueDay.getTime() - today.getTime()) / 86400000)

  const mm = due.getMonth() + 1
  const dd = due.getDate()
  const dateStr = `${mm}/${dd}`

  if (diffDays < 0) return { text: `${dateStr} 已过期`, color: '#E8615C' }
  if (diffDays === 0) return { text: `今天 ${dateStr}`, color: '#EA580C' }
  if (diffDays === 1) return { text: `明天 ${dateStr}`, color: '#D97706' }
  if (diffDays <= 6) return { text: `${WEEKDAY_NAMES[due.getDay()]} ${dateStr}`, color: '#D97706' }
  return { text: dateStr, color: '#6B7280' }
}

function handleTaskClick(uuid: string) {
  store.setEditingUuid(uuid)
}

function handleTaskComplete(uuid: string, e: Event) {
  e.stopPropagation()
  store.completeTask(uuid)
}

function handleTaskDelete(uuid: string, e: Event) {
  e.stopPropagation()
  store.deleteTask(uuid)
}

function handleRestore(uuid: string, e: Event) {
  e.stopPropagation()
  store.completeTask(uuid)
}

function handlePermanentDelete(uuid: string, e: Event) {
  e.stopPropagation()
  store.deleteTask(uuid)
}
</script>

<template>
  <aside class="task-list-panel">
    <!-- 过滤器 -->
    <div class="filter-bar">
      <!-- 截止日期筛选 chip -->
      <div class="filter-row">
        <button
          v-for="f in [
            { key: 'all', label: '全部' },
            { key: 'overdue', label: '已过期' },
            { key: 'today', label: '今天' },
            { key: 'thisWeek', label: '本周' },
            { key: 'thisMonth', label: '本月' },
          ]"
          :key="f.key"
          class="filter-chip"
          :class="{ active: store.dueFilter === f.key }"
          @click="store.setDueFilter(f.key as any)"
        >{{ f.label }}</button>
      </div>

      <!-- 象限筛选 chip -->
      <div class="filter-row">
        <button
          class="filter-chip"
          :class="{ active: !store.selectedQuadrant }"
          @click="store.setQuadrantFilter(null)"
        >全部象限</button>
        <button
          v-for="q in quadrantsOrder"
          :key="q"
          class="filter-chip"
          :class="{ active: store.selectedQuadrant === q }"
          :style="store.selectedQuadrant === q ? { borderColor: quadrantConfig[q].color, color: quadrantConfig[q].color } : {}"
          @click="store.setQuadrantFilter(q)"
        >{{ quadrantConfig[q].label }}</button>
      </div>

      <!-- 标签筛选 -->
      <div v-if="store.tags.length" class="filter-row tag-filter-row">
        <button
          v-for="tag in store.tags"
          :key="tag.uuid"
          class="filter-chip tag-filter-chip"
          :class="{ active: store.tagFilter.includes(tag.uuid) }"
          :style="store.tagFilter.includes(tag.uuid) ? { borderColor: tag.color, color: tag.color, backgroundColor: tag.color + '14' } : {}"
          @click="store.toggleTagFilter(tag.uuid)"
        >{{ tag.name }}</button>
      </div>

      <button v-if="store.hasActiveFilters" class="clear-filters-btn" @click="store.clearFilters()">清除筛选</button>
    </div>

    <!-- 任务列表 -->
    <div class="task-sections">
      <template v-for="q in quadrantsOrder" :key="q">
        <div v-if="store.groupedTasks[q]?.length" class="group-section">
          <button class="group-header" @click="toggleGroup(q)">
            <span class="group-dot" :style="{ backgroundColor: quadrantConfig[q].color }" />
            <span class="group-label">{{ quadrantConfig[q].label }}</span>
            <span class="group-count">{{ store.groupedTasks[q].length }}</span>
            <svg
              class="group-chevron"
              :class="{ open: !collapsedGroups[q] }"
              viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"
            ><path d="M4 6l4 4 4-4"/></svg>
          </button>
          <div v-if="!collapsedGroups[q]" class="group-tasks">
            <div
              v-for="task in store.groupedTasks[q]"
              :key="task.uuid"
              class="task-item"
              :class="{ completed: task.completed }"
              @click="handleTaskClick(task.uuid)"
            >
              <button
                class="task-check"
                :class="{ done: task.completed }"
                @click="handleTaskComplete(task.uuid, $event)"
              >
                <svg v-if="task.completed" viewBox="0 0 16 16" width="12" height="12"><path d="M3 8l3 3 7-7" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round"/></svg>
              </button>
              <div class="task-body">
                <span class="task-title" :class="{ 'line-through': task.completed }">{{ task.title }}</span>
                <div class="task-meta">
                  <span
                    v-if="formatDueDate(task.dueDate)"
                    class="due-badge"
                    :style="{ color: formatDueDate(task.dueDate)!.color }"
                  >{{ formatDueDate(task.dueDate)!.text }}</span>
                  <div class="task-tags-inline">
                    <TagChip
                      v-for="tag in getTaskTags(task).slice(0, 2)"
                      :key="tag.uuid"
                      :name="tag.name"
                      :color="tag.color"
                      :small="true"
                    />
                  </div>
                </div>
              </div>
              <button class="task-delete-btn" title="删除" @click="handleTaskDelete(task.uuid, $event)">
                <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 5h10M6 5V3h4v2M5 5v7a1 1 0 001 1h4a1 1 0 001-1V5"/></svg>
              </button>
            </div>
          </div>
        </div>
      </template>

      <p v-if="!store.filteredTasks.length" class="empty-msg">暂无任务</p>
    </div>

    <!-- 已完成任务 -->
    <div v-if="store.completedTasks.length" class="completed-section">
      <button class="group-header" @click="showCompleted = !showCompleted">
        <span class="group-label">已完成 ({{ store.completedTasks.length }})</span>
        <svg class="group-chevron" :class="{ open: showCompleted }" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6l4 4 4-4"/></svg>
      </button>
      <div v-if="showCompleted" class="group-tasks">
        <div
          v-for="task in store.completedTasks"
          :key="task.uuid"
          class="task-item completed"
        >
          <div class="task-body">
            <span class="task-title line-through">{{ task.title }}</span>
          </div>
          <div class="completed-actions">
            <button class="restore-btn" title="恢复" @click="handleRestore(task.uuid, $event)">恢复</button>
            <button class="perm-delete-btn" title="永久删除" @click="handlePermanentDelete(task.uuid, $event)">删除</button>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.task-list-panel {
  width: 280px;
  flex-shrink: 0;
  height: 100%;
  background: var(--surface-primary);
  border-right: 1px solid var(--c-gray-200);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 过滤器 */
.filter-bar {
  padding: 12px;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.filter-row {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.tag-filter-row {
  gap: 3px;
}

.filter-chip {
  padding: 3px 10px;
  border-radius: var(--r-chip);
  font-size: 11.5px;
  border: 1px solid var(--c-gray-200);
  background: var(--surface-primary);
  color: var(--c-gray-600);
  cursor: pointer;
  transition: all 0.12s;
  white-space: nowrap;
}
.filter-chip:hover { border-color: var(--c-gray-400); }
.filter-chip.active {
  background: var(--c-brand-50);
  border-color: var(--c-brand-500);
  color: var(--c-brand-600);
  font-weight: 500;
}

.tag-filter-chip.active {
  background: var(--c-brand-50);
}

.clear-filters-btn {
  font-size: 11px;
  color: var(--c-gray-400);
  border: none;
  background: none;
  cursor: pointer;
  align-self: flex-start;
  padding: 2px 0;
}
.clear-filters-btn:hover { color: var(--c-danger); }

/* 任务分组 */
.task-sections {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
}

.group-section {
  border-bottom: 1px solid var(--border-light);
}

.group-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  color: var(--c-gray-600);
  transition: background 0.12s;
}
.group-header:hover { background: var(--c-gray-100); }

.group-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.group-label {
  font-weight: 500;
  flex: 1;
  text-align: left;
}

.group-count {
  font-size: 11px;
  color: var(--c-gray-400);
  background: var(--c-gray-100);
  padding: 1px 6px;
  border-radius: 8px;
}

.group-chevron {
  color: var(--c-gray-400);
  transition: transform 0.15s;
  flex-shrink: 0;
}
.group-chevron.open { transform: rotate(180deg); }

.group-tasks {
  padding: 0 0 4px;
}

.task-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  transition: background 0.1s;
}
.task-item:hover { background: var(--c-gray-100); }
.task-item.completed { opacity: 0.6; }

.task-check {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1.5px solid var(--c-gray-300);
  background: var(--surface-primary);
  cursor: pointer;
  flex-shrink: 0;
  margin-top: 1px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.task-check:hover { border-color: var(--c-success); }
.task-check.done {
  background: var(--c-success);
  border-color: var(--c-success);
}

.task-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.task-title {
  font-size: 13.5px;
  color: var(--c-gray-800);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-title.line-through { text-decoration: line-through; color: var(--c-gray-400); }

.task-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.due-badge {
  font-size: 10.5px;
  font-weight: 500;
}

.task-tags-inline {
  display: flex;
  gap: 3px;
}

.task-delete-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: none;
  color: var(--c-gray-300);
  cursor: pointer;
  border-radius: 4px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.12s, color 0.12s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.task-item:hover .task-delete-btn { opacity: 1; }
.task-delete-btn:hover { color: var(--c-danger); }

.empty-msg {
  text-align: center;
  padding: 32px 16px;
  color: var(--c-gray-400);
  font-size: 13px;
}

/* 已完成分组 */
.completed-section {
  border-top: 1px solid var(--c-gray-200);
  flex-shrink: 0;
}

.completed-section .group-header {
  padding: 10px 12px;
}

.completed-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.12s;
}

.task-item:hover .completed-actions { opacity: 1; }

.restore-btn,
.perm-delete-btn {
  font-size: 11px;
  border: none;
  background: none;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.restore-btn {
  color: var(--c-brand-500);
}
.restore-btn:hover { background: var(--c-brand-50); }

.perm-delete-btn {
  color: var(--c-danger);
}
.perm-delete-btn:hover { background: rgba(220, 38, 38, 0.08); }
</style>
