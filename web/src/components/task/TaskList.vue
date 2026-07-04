<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useTaskStore, getDueStatus, getQuadrant } from '@/stores/task'
import type { TaskEx } from '@/stores/task'

const store = useTaskStore()

// ── 搜索 ──
const searchText = ref(store.searchQuery)
let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearchInput(val: string) {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => store.setSearchQuery(val), 200)
}

watch(() => store.searchQuery, (v) => {
  if (searchText.value !== v) searchText.value = v
})

function clearSearch() {
  searchText.value = ''
  store.setSearchQuery('')
}

// ── 折叠状态 ──
const collapsedGroups = ref<Record<string, boolean>>({ attention: false, upcoming: false, planned: false })
const showCompleted = ref(false)

// ── 筛选面板（含排序 + 象限 + 标签 + 日期）—— 直接内嵌在面板里 ──
const showMoreFilters = ref(false)

// 排序模式
type SortMode = 'dueDate' | 'urgency' | 'title'
const sortMode = ref<SortMode>('dueDate')

const sortOptions: { key: SortMode; label: string; icon: string }[] = [
  { key: 'dueDate',  label: '按截止日期', icon: '📅' },
  { key: 'urgency',  label: '按紧急度',   icon: '⚡' },
  { key: 'title',    label: '按标题',     icon: '🔤' },
]

function selectSort(mode: SortMode) {
  // 再次点击当前已选中的排序 → 取消，恢复默认
  sortMode.value = sortMode.value === mode ? 'dueDate' : mode
}

// ── 是否有额外筛选激活 ──
const hasExtraFilters = computed(() =>
  !!store.selectedQuadrant || store.tagFilter.length > 0 || store.dueFilter === 'overdue' || store.dueFilter === 'thisMonth',
)

// ── 主筛选 chips ──
const mainFilters = [
  { key: 'all' as const, label: '全部' },
  { key: 'today' as const, label: '今天' },
  { key: 'thisWeek' as const, label: '本周' },
]

// ── 象限配置 ──
const quadrantConfig: Record<string, { label: string; color: string }> = {
  Q1: { label: '重要且紧急', color: '#DC2626' },
  Q2: { label: '重要不紧急', color: '#16A34A' },
  Q3: { label: '不重要紧急', color: '#2563EB' },
  Q4: { label: '不重要不紧急', color: '#D97706' },
}

const quadrantsOrder = ['Q1', 'Q2', 'Q3', 'Q4']

function quadrantColor(task: TaskEx): string {
  const q = getQuadrant(task.urgencyLevel, task.importanceLevel)
  return quadrantConfig[q]?.color ?? '#999'
}

// ── 排序辅助 ──
function sortTasks(list: TaskEx[]): TaskEx[] {
  const sorted = [...list]
  if (sortMode.value === 'dueDate') {
    // 截止日期升序（无日期排最后），再按 urgencyLevel 降序
    sorted.sort((a, b) => {
      const da = a.dueDate ?? '9999'
      const db = b.dueDate ?? '9999'
      if (da !== db) return da.localeCompare(db)
      return b.urgencyLevel - a.urgencyLevel
    })
  } else if (sortMode.value === 'urgency') {
    // 紧急度降序 → 重要度降序
    sorted.sort((a, b) => {
      if (b.urgencyLevel !== a.urgencyLevel) return b.urgencyLevel - a.urgencyLevel
      return b.importanceLevel - a.importanceLevel
    })
  } else if (sortMode.value === 'title') {
    sorted.sort((a, b) => (a.title || '').localeCompare(b.title || '', 'zh-CN'))
  }
  return sorted
}

// ── 时间分组 ──
const attentionTasks = computed(() =>
  sortTasks(store.filteredTasks.filter(t => {
    const s = getDueStatus(t.dueDate)
    return s === 'overdue' || s === 'today'
  })),
)

const upcomingTasks = computed(() =>
  sortTasks(store.filteredTasks.filter(t => {
    const s = getDueStatus(t.dueDate)
    return s === 'thisWeek'
  })),
)

const plannedTasks = computed(() =>
  sortTasks(store.filteredTasks.filter(t => {
    const s = getDueStatus(t.dueDate)
    return s === 'thisMonth' || s === 'normal' || s === 'none'
  })),
)

const timeGroups = computed(() => [
  { key: 'attention', icon: '🔴', label: '需要关注', tasks: attentionTasks.value },
  { key: 'upcoming', icon: '🟡', label: '即将到来', tasks: upcomingTasks.value },
  { key: 'planned', icon: '🔵', label: '计划中', tasks: plannedTasks.value },
])

const isEmpty = computed(() =>
  timeGroups.value.every(g => g.tasks.length === 0) && store.completedTasks.length === 0,
)

const hasNoResults = computed(() =>
  store.hasActiveFilters && timeGroups.value.every(g => g.tasks.length === 0),
)

// ── 日期格式化 ──
const WEEKDAY_NAMES = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

function formatDueDate(dueDate: string | null): { text: string; urgent: boolean } | null {
  if (!dueDate) return null
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const due = new Date(dueDate)
  const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate())
  const diffDays = Math.round((dueDay.getTime() - today.getTime()) / 86400000)

  const mm = due.getMonth() + 1
  const dd = due.getDate()

  if (diffDays < 0) return { text: `${mm}/${dd} 已过期`, urgent: true }
  if (diffDays === 0) return { text: '今天', urgent: true }
  if (diffDays === 1) return { text: `明天 ${mm}/${dd}`, urgent: false }
  if (diffDays <= 6) return { text: `${WEEKDAY_NAMES[due.getDay()]} ${mm}/${dd}`, urgent: false }
  return { text: `${mm}/${dd}`, urgent: false }
}

// ── 分组收起 / 展开 ──
function toggleGroup(key: string) {
  collapsedGroups.value[key] = !collapsedGroups.value[key]
}

// ── 标签获取 ──
function getTaskTags(task: TaskEx): { uuid: string; name: string; color: string }[] {
  const tt = task.tags
  if (!tt || !tt.length) return []
  if (typeof tt[0] === 'string') {
    return (tt as string[]).map(id => store.tags.find(t => t.uuid === id)).filter((t): t is NonNullable<typeof t> => !!t)
  }
  return tt as { uuid: string; name: string; color: string }[]
}

// ── 操作 ──
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
    <!-- ── 搜索栏 ── -->
    <div class="search-bar">
      <div class="search-input-wrap">
        <svg class="search-icon" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="6.5" cy="6.5" r="4.5" />
          <path d="M10 10l4.5 4.5" />
        </svg>
        <input
          class="search-input"
          type="text"
          :value="searchText"
          @input="onSearchInput(($event.target as HTMLInputElement).value)"
          placeholder="搜索任务..."
        />
        <button v-if="searchText" class="search-clear" @click="clearSearch">&times;</button>
      </div>

      <!-- 更多筛选按钮（点击展开内嵌面板） -->
      <button
        class="more-filters-btn"
        :class="{ active: showMoreFilters || hasExtraFilters || sortMode !== 'dueDate' }"
        @click="showMoreFilters = !showMoreFilters"
        title="更多筛选"
      >
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6">
          <path d="M1 3h14M3 8h10M5 13h6" />
        </svg>
        <span v-if="hasExtraFilters || sortMode !== 'dueDate'" class="filter-dot" />
      </button>
    </div>

    <!-- ── 更多筛选面板（直接内嵌在面板里，含排序 + 象限 + 标签 + 日期） ── -->
    <div v-if="showMoreFilters" class="more-filters">
      <!-- 排序 -->
      <div class="filter-section">
        <span class="filter-section-label">排序方式</span>
        <div class="sort-grid">
          <button
            v-for="opt in sortOptions"
            :key="opt.key"
            class="sort-option"
            :class="{ active: sortMode === opt.key }"
            @click="selectSort(opt.key)"
          >
            <span class="sort-icon">{{ opt.icon }}</span>
            <span>{{ opt.label }}</span>
            <span v-if="sortMode === opt.key" class="sort-check">✓</span>
          </button>
        </div>
      </div>

      <!-- 象限筛选 -->
      <div class="filter-section">
        <span class="filter-section-label">象限</span>
        <div class="filter-row">
          <button
            class="mini-chip"
            :class="{ active: !store.selectedQuadrant }"
            @click="store.setQuadrantFilter(null)"
          >全部</button>
          <button
            v-for="q in quadrantsOrder"
            :key="q"
            class="mini-chip"
            :class="{ active: store.selectedQuadrant === q }"
            :style="store.selectedQuadrant === q ? { borderColor: quadrantConfig[q].color, color: quadrantConfig[q].color, backgroundColor: quadrantConfig[q].color + '14' } : {}"
            @click="store.setQuadrantFilter(q)"
          >{{ quadrantConfig[q].label }}</button>
        </div>
      </div>

      <!-- 标签筛选 -->
      <div v-if="store.tags.length" class="filter-section">
        <span class="filter-section-label">标签</span>
        <div class="filter-row">
          <button
            v-for="tag in store.tags"
            :key="tag.uuid"
            class="mini-chip"
            :class="{ active: store.tagFilter.includes(tag.uuid) }"
            :style="store.tagFilter.includes(tag.uuid) ? { borderColor: tag.color, color: tag.color, backgroundColor: tag.color + '14' } : {}"
            @click="store.toggleTagFilter(tag.uuid)"
          >{{ tag.name }}</button>
        </div>
      </div>

      <!-- 更多日期选项 -->
      <div class="filter-section">
        <span class="filter-section-label">截止日期</span>
        <div class="filter-row">
          <button
            class="mini-chip"
            :class="{ active: store.dueFilter === 'overdue' }"
            @click="store.setDueFilter(store.dueFilter === 'overdue' ? 'all' : 'overdue')"
          >已过期</button>
          <button
            class="mini-chip"
            :class="{ active: store.dueFilter === 'thisMonth' }"
            @click="store.setDueFilter(store.dueFilter === 'thisMonth' ? 'all' : 'thisMonth')"
          >本月</button>
        </div>
      </div>

      <button v-if="store.hasActiveFilters" class="clear-filters-btn" @click="store.clearFilters()">
        清除所有筛选
      </button>
    </div>

    <!-- ── 主筛选 chips ── -->
    <div class="filter-bar">
      <button
        v-for="f in mainFilters"
        :key="f.key"
        class="filter-chip"
        :class="{ active: store.dueFilter === f.key && !hasExtraFilters }"
        @click="store.setDueFilter(f.key)"
      >{{ f.label }}</button>
    </div>

    <!-- ── 任务分组 ── -->
    <div class="task-sections">
      <template v-for="group in timeGroups" :key="group.key">
        <div v-if="group.tasks.length" class="group-section">
          <button class="group-header" @click="toggleGroup(group.key)">
            <span class="group-icon">{{ collapsedGroups[group.key] ? '▶' : '▼' }}</span>
            <span class="group-label">{{ group.label }}</span>
            <span class="group-count">{{ group.tasks.length }}</span>
          </button>
          <div v-if="!collapsedGroups[group.key]" class="group-tasks">
            <div
              v-for="task in group.tasks"
              :key="task.uuid"
              class="task-item"
              :class="{ completed: task.completed }"
              @click="handleTaskClick(task.uuid)"
            >
              <!-- 象限色点 -->
              <span class="quadrant-dot" :style="{ backgroundColor: quadrantColor(task) }" />

              <!-- 完成勾选 -->
              <button
                class="task-check"
                :class="{ done: task.completed }"
                @click="handleTaskComplete(task.uuid, $event)"
              >
                <svg v-if="task.completed" viewBox="0 0 16 16" width="12" height="12">
                  <path d="M3 8l3 3 7-7" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" />
                </svg>
              </button>

              <!-- 任务正文 -->
              <div class="task-body">
                <span class="task-title" :class="{ 'line-through': task.completed }">{{ task.title || '未命名' }}</span>
                <div class="task-meta">
                  <span
                    v-if="formatDueDate(task.dueDate)"
                    class="due-text"
                    :class="{ urgent: formatDueDate(task.dueDate)!.urgent }"
                  >{{ formatDueDate(task.dueDate)!.text }}</span>
                  <!-- 标签色点 -->
                  <span
                    v-for="tag in getTaskTags(task).slice(0, 2)"
                    :key="tag.uuid"
                    class="tag-mini-dot"
                    :style="{ backgroundColor: tag.color }"
                    :title="tag.name"
                  />
                </div>
              </div>

              <!-- 删除 -->
              <button class="task-delete-btn" title="删除" @click="handleTaskDelete(task.uuid, $event)">
                <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6">
                  <path d="M3 5h10M6 5V3h4v2M5 5v7a1 1 0 001 1h4a1 1 0 001-1V5" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </template>

      <!-- 空状态 -->
      <div v-if="hasNoResults" class="empty-state">
        <p class="empty-title">没有匹配的任务</p>
        <p class="empty-desc">试试调整筛选条件或搜索关键词</p>
      </div>
      <div v-else-if="isEmpty && !store.hasActiveFilters" class="empty-state">
        <p class="empty-title">暂无任务</p>
        <p class="empty-desc">在四象限画布上双击创建任务</p>
      </div>
    </div>

    <!-- ── 已完成 ── -->
    <div v-if="store.completedTasks.length" class="completed-section">
      <button class="group-header completed-header" @click="showCompleted = !showCompleted">
        <span class="group-icon">{{ showCompleted ? '▼' : '▶' }}</span>
        <span class="group-label">已完成</span>
        <span class="group-count">{{ store.completedTasks.length }}</span>
      </button>
      <div v-if="showCompleted" class="group-tasks">
        <div
          v-for="task in store.completedTasks"
          :key="task.uuid"
          class="task-item completed"
        >
          <span class="quadrant-dot" :style="{ backgroundColor: quadrantColor(task), opacity: '0.4' }" />
          <div class="task-body">
            <span class="task-title line-through">{{ task.title || '未命名' }}</span>
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

/* ══════════════════════════════════════════ */
/* 搜索栏                                    */
/* ══════════════════════════════════════════ */

.search-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px 6px;
  flex-shrink: 0;
}

.search-input-wrap {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 10px;
  color: var(--c-gray-400);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 32px;
  padding: 0 28px 0 30px;
  border: 1px solid var(--c-gray-200);
  border-radius: 8px;
  font-size: 13px;
  color: var(--c-gray-800);
  background: var(--c-gray-50);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.search-input:focus {
  border-color: var(--c-brand-500);
  box-shadow: 0 0 0 2px rgba(46, 91, 255, 0.1);
}

.search-input::placeholder {
  color: var(--c-gray-400);
}

.search-clear {
  position: absolute;
  right: 4px;
  width: 20px;
  height: 20px;
  border: none;
  background: none;
  color: var(--c-gray-400);
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: color 0.12s, background 0.12s;
}

.search-clear:hover {
  color: var(--c-gray-600);
  background: var(--c-gray-200);
}

/* 更多筛选按钮 */
.more-filters-btn {
  position: relative;
  width: 32px;
  height: 32px;
  border: 1px solid var(--c-gray-200);
  border-radius: 8px;
  background: var(--c-gray-50);
  color: var(--c-gray-500);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.12s;
}

.more-filters-btn:hover {
  border-color: var(--c-gray-300);
  color: var(--c-gray-700);
}

.more-filters-btn.active {
  border-color: var(--c-brand-500);
  color: var(--c-brand-500);
  background: var(--c-brand-50);
}

.filter-dot {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-brand-500);
}

/* 排序选项（内嵌在更多筛选面板里） */
.sort-grid {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sort-option {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: none;
  background: none;
  border-radius: 6px;
  font-size: 12.5px;
  color: var(--c-gray-700);
  cursor: pointer;
  text-align: left;
  transition: background 0.12s;
}

.sort-option:hover {
  background: var(--c-gray-100);
}

.sort-option.active {
  color: var(--c-brand-600);
  background: var(--c-brand-50);
  font-weight: 500;
}

.sort-icon {
  font-size: 14px;
  width: 16px;
  text-align: center;
}

.sort-check {
  margin-left: auto;
  font-size: 11px;
  color: var(--c-brand-500);
}

.filter-dropdown-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-dropdown-divider {
  height: 1px;
  background: var(--border-light);
  margin: 2px -4px;
}

.sort-grid {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sort-option {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: none;
  background: none;
  border-radius: 6px;
  font-size: 12.5px;
  color: var(--c-gray-700);
  cursor: pointer;
  text-align: left;
  transition: background 0.12s;
}

.sort-option:hover {
  background: var(--c-gray-100);
}

.sort-option.active {
  color: var(--c-brand-600);
  background: var(--c-brand-50);
  font-weight: 500;
}

.sort-icon {
  font-size: 14px;
  width: 16px;
  text-align: center;
}

.sort-check {
  margin-left: auto;
  font-size: 11px;
  color: var(--c-brand-500);
}

.dropdown-clear-btn {
  font-size: 11px;
  color: var(--c-gray-400);
  border: none;
  background: none;
  cursor: pointer;
  padding: 4px 0;
  align-self: flex-start;
  transition: color 0.12s;
}

.dropdown-clear-btn:hover {
  color: var(--c-danger);
}

.filter-menu-enter-active,
.filter-menu-leave-active {
  transition: opacity 0.15s var(--ease-standard), transform 0.15s var(--ease-standard);
}

.filter-menu-enter-from,
.filter-menu-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.97);
}

/* ══════════════════════════════════════════ */
/* 主筛选 chips                              */
/* ══════════════════════════════════════════ */

.filter-bar {
  display: flex;
  gap: 4px;
  padding: 4px 12px 8px;
  flex-shrink: 0;
}

.filter-chip {
  padding: 4px 12px;
  border-radius: 14px;
  font-size: 12px;
  border: 1px solid var(--c-gray-200);
  background: var(--surface-primary);
  color: var(--c-gray-600);
  cursor: pointer;
  transition: all 0.12s;
  white-space: nowrap;
  font-weight: 500;
}

.filter-chip:hover {
  border-color: var(--c-gray-300);
  background: var(--c-gray-100);
}

.filter-chip.active {
  background: var(--c-brand-500);
  border-color: var(--c-brand-500);
  color: #fff;
}

/* ══════════════════════════════════════════ */
/* 更多筛选面板（直接内嵌在 TaskList 面板里） */
/* ══════════════════════════════════════════ */

.more-filters {
  padding: 8px 12px 12px;
  border-bottom: 1px solid var(--border-light);
  background: var(--c-gray-50);
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex-shrink: 0;
  animation: filterSlideDown 0.18s var(--ease-standard);
}

@keyframes filterSlideDown {
  from { opacity: 0; max-height: 0; }
  to   { opacity: 1; max-height: 600px; }
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.filter-section-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--c-gray-400);
}

.filter-row {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.mini-chip {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  border: 1px solid var(--c-gray-200);
  background: var(--surface-primary);
  color: var(--c-gray-600);
  cursor: pointer;
  transition: all 0.12s;
  white-space: nowrap;
}

.mini-chip:hover {
  border-color: var(--c-gray-400);
}

.mini-chip.active {
  border-color: var(--c-brand-500);
  color: var(--c-brand-600);
  background: var(--c-brand-50);
  font-weight: 500;
}

.clear-filters-btn {
  font-size: 11px;
  color: var(--c-gray-400);
  border: none;
  background: none;
  cursor: pointer;
  align-self: flex-start;
  padding: 2px 0;
  transition: color 0.12s;
}

.clear-filters-btn:hover {
  color: var(--c-danger);
}

/* ══════════════════════════════════════════ */
/* 任务分组                                  */
/* ══════════════════════════════════════════ */

.task-sections {
  flex: 1;
  overflow-y: auto;
  padding: 2px 0;
}

.group-section {
  border-bottom: 1px solid var(--border-light);
}

.group-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 12px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--c-gray-600);
  transition: background 0.12s;
}

.group-header:hover {
  background: var(--c-gray-100);
}

.group-icon {
  font-size: 8px;
  width: 12px;
  text-align: center;
  flex-shrink: 0;
}

.group-label {
  flex: 1;
  text-align: left;
}

.group-count {
  font-size: 11px;
  color: var(--c-gray-400);
  background: var(--c-gray-100);
  padding: 1px 7px;
  border-radius: 8px;
  font-weight: 500;
}

/* ── 任务条目 ── */
.group-tasks {
  padding: 0 0 2px;
}

.task-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 7px 12px 7px 10px;
  cursor: pointer;
  transition: background 0.1s;
  position: relative;
}

.task-item:hover {
  background: var(--c-gray-100);
}

.task-item.completed {
  opacity: 0.55;
}

/* 象限色点 */
.quadrant-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 7px;
}

/* 完成勾选 */
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
  padding: 0;
}

.task-check:hover {
  border-color: var(--c-success);
}

.task-check.done {
  background: var(--c-success);
  border-color: var(--c-success);
}

/* 任务正文 */
.task-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.task-title {
  font-size: 13px;
  color: var(--c-gray-800);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.task-title.line-through {
  text-decoration: line-through;
  color: var(--c-gray-400);
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 4px;
}

.due-text {
  font-size: 10.5px;
  color: var(--c-gray-500);
  white-space: nowrap;
}

.due-text.urgent {
  color: #DC2626;
  font-weight: 500;
}

/* 标签迷你色点 */
.tag-mini-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
  opacity: 0.7;
}

/* 删除按钮 */
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
  padding: 0;
}

.task-item:hover .task-delete-btn {
  opacity: 1;
}

.task-delete-btn:hover {
  color: var(--c-danger);
}

/* ══════════════════════════════════════════ */
/* 空状态                                    */
/* ══════════════════════════════════════════ */

.empty-state {
  text-align: center;
  padding: 40px 20px;
}

.empty-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-gray-500);
  margin: 0 0 4px;
}

.empty-desc {
  font-size: 12px;
  color: var(--c-gray-400);
  margin: 0;
}

/* ══════════════════════════════════════════ */
/* 已完成分组                                */
/* ══════════════════════════════════════════ */

.completed-section {
  border-top: 1px solid var(--c-gray-200);
  flex-shrink: 0;
  max-height: 40%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.completed-section .group-tasks {
  overflow-y: auto;
  flex: 1;
}

.completed-header {
  padding: 9px 12px;
}

.completed-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.12s;
  align-items: center;
}

.task-item:hover .completed-actions {
  opacity: 1;
}

.restore-btn,
.perm-delete-btn {
  font-size: 11px;
  border: none;
  background: none;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
}

.restore-btn {
  color: var(--c-brand-500);
}

.restore-btn:hover {
  background: var(--c-brand-50);
}

.perm-delete-btn {
  color: var(--c-danger);
}

.perm-delete-btn:hover {
  background: rgba(220, 38, 38, 0.08);
}

/* ══════════════════════════════════════════ */
/* 移动端适配                                */
/* ══════════════════════════════════════════ */

@media (max-width: 767px) {
  /* 移动端由 HomeView 的 .mobile-drawer-panel 控制宽度（min(320px, 85vw)），
     不要在这里强制 width: 100%，否则会撑满整页挡住画布 */
  .task-list-panel {
    border-right: none;
  }

  .search-bar {
    padding: 8px 8px 4px;
  }

  .filter-bar {
    padding: 4px 8px 6px;
  }

  .more-filters {
    padding: 6px 8px 10px;
  }

  .task-item {
    padding: 8px 8px 8px 6px;
  }

  .task-delete-btn {
    opacity: 1;
    width: 28px;
    height: 28px;
  }

  .completed-actions {
    opacity: 1;
  }
}
</style>
