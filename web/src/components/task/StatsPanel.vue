<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTaskStore, getQuadrant } from '@/stores/task'

const store = useTaskStore()

const activeTab = ref<'overview' | 'tags'>('overview')

const activeCount = computed(() => store.serverTasks.filter(t => !t.completed).length)
const completedCount = computed(() => store.serverTasks.filter(t => t.completed).length)
const completionRate = computed(() => {
  if (!store.serverTasks.length) return 0
  return Math.round((completedCount.value / store.serverTasks.length) * 100)
})

const overdueCount = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return store.serverTasks.filter(t => {
    if (!t.dueDate || t.completed) return false
    return new Date(t.dueDate) < today
  }).length
})

const todayCount = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  return store.serverTasks.filter(t => {
    if (!t.dueDate || t.completed) return false
    const due = new Date(t.dueDate)
    const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate()).getTime()
    return dueDay === today
  }).length
})

const thisWeekCount = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const endOfWeek = new Date(today)
  endOfWeek.setDate(today.getDate() + (6 - today.getDay()))
  const endOfWeekEnd = new Date(endOfWeek)
  endOfWeekEnd.setHours(23, 59, 59, 999)
  return store.serverTasks.filter(t => {
    if (!t.dueDate || t.completed) return false
    const due = new Date(t.dueDate)
    return due >= today && due <= endOfWeekEnd
  }).length
})

const thisMonthCount = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59, 999)
  return store.serverTasks.filter(t => {
    if (!t.dueDate || t.completed) return false
    const due = new Date(t.dueDate)
    return due >= today && due <= endOfMonth
  }).length
})

const quadrantDistribution = computed(() => {
  const dist: Record<string, number> = { Q1: 0, Q2: 0, Q3: 0, Q4: 0 }
  for (const t of store.serverTasks) {
    if (t.completed) continue
    dist[getQuadrant(t.urgencyLevel, t.importanceLevel)]++
  }
  return dist
})

const maxQuadrant = computed(() => Math.max(...Object.values(quadrantDistribution.value), 1))

interface TagStat { uuid: string; name: string; color: string; count: number }
const tagDistribution = computed<TagStat[]>(() => {
  const map = new Map<string, TagStat>()
  for (const t of store.serverTasks) {
    if (t.completed) continue
    const tags = t.tags
    if (!tags || !tags.length) continue
    const tagIds: string[] = typeof tags[0] === 'string' ? tags as string[] : (tags as { uuid: string }[]).map(tg => tg.uuid)
    for (const id of tagIds) {
      const tag = store.tags.find(tg => tg.uuid === id)
      if (!map.has(id) && tag) {
        map.set(id, { uuid: id, name: tag.name, color: tag.color, count: 0 })
      }
      const entry = map.get(id)
      if (entry) entry.count++
    }
  }
  return [...map.values()].sort((a, b) => b.count - a.count)
})

const quadrantConfig = [
  { key: 'Q1', label: '重要且紧急', color: '#DC2626' },
  { key: 'Q2', label: '重要不紧急', color: '#16A34A' },
  { key: 'Q3', label: '不重要紧急', color: '#2563EB' },
  { key: 'Q4', label: '不重要不紧急', color: '#D97706' },
]

function localDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Weekly completion trend (last 7 days)
const weekDays = computed(() => {
  const days: { label: string; completed: number; created: number }[] = []
  const now = new Date()
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i)
    const dateStr = localDateStr(d)
    const label = i === 0 ? '今天' : i === 1 ? '昨天' : `${d.getMonth() + 1}/${d.getDate()}`
    const completed = store.serverTasks.filter(t => {
      if (!t.completed || !t.completedAt) return false
      return localDateStr(new Date(t.completedAt)) === dateStr
    }).length
    const created = store.serverTasks.filter(t => localDateStr(new Date(t.createdAt)) === dateStr).length
    days.push({ label, completed, created })
  }
  return days
})

const maxTrend = computed(() => Math.max(...weekDays.value.flatMap(d => [d.completed, d.created]), 1))
</script>

<template>
  <aside class="stats-panel">
    <!-- Tab switcher -->
    <div class="tab-switcher">
      <button :class="['tab-btn', { active: activeTab === 'overview' }]" @click="activeTab = 'overview'">概览</button>
      <button :class="['tab-btn', { active: activeTab === 'tags' }]" @click="activeTab = 'tags'">标签</button>
    </div>

    <div class="panel-body">
      <!-- Overview tab -->
      <div v-if="activeTab === 'overview'" class="tab-content">
        <!-- Stat cards -->
        <div class="stat-grid">
          <div class="stat-card">
            <span class="stat-num" style="color: #2563EB">{{ activeCount }}</span>
            <span class="stat-label">待完成</span>
          </div>
          <div class="stat-card">
            <span class="stat-num" style="color: #16A34A">{{ completedCount }}</span>
            <span class="stat-label">已完成</span>
          </div>
          <div class="stat-card">
            <span class="stat-num" style="color: #D97706">{{ completionRate }}%</span>
            <span class="stat-label">完成率</span>
          </div>
        </div>

        <!-- Due indicators -->
        <div class="due-row">
          <div class="due-item overdue">
            <span class="due-num">{{ overdueCount }}</span>
            <span class="due-label">已过期</span>
          </div>
          <div class="due-item today">
            <span class="due-num">{{ todayCount }}</span>
            <span class="due-label">今天</span>
          </div>
          <div class="due-item week">
            <span class="due-num">{{ thisWeekCount }}</span>
            <span class="due-label">本周</span>
          </div>
          <div class="due-item month">
            <span class="due-num">{{ thisMonthCount }}</span>
            <span class="due-label">本月</span>
          </div>
        </div>

        <!-- Quadrant distribution -->
        <div class="section-title">象限分布</div>
        <div v-if="activeCount || completedCount" class="quadrant-dist">
          <div v-for="q in quadrantConfig" :key="q.key" class="quadrant-bar-row">
            <span class="quadrant-bar-label" :style="{ color: q.color }">{{ q.label }}</span>
            <div class="quadrant-bar-track">
              <div
                class="quadrant-bar-fill"
                :style="{
                  width: (quadrantDistribution[q.key] / maxQuadrant * 100) + '%',
                  backgroundColor: q.color,
                }"
              />
            </div>
            <span class="quadrant-bar-num">{{ quadrantDistribution[q.key] }}</span>
          </div>
        </div>
        <p v-else class="empty-msg">暂无任务数据</p>

        <!-- Weekly trend -->
        <div class="section-title">近7天</div>
        <div v-if="activeCount || completedCount" class="weekly-trend">
          <div v-for="d in weekDays" :key="d.label" class="trend-column">
            <div class="trend-bars">
              <div
                class="trend-bar created"
                :style="{ height: (d.created / maxTrend * 100) + '%' }"
                :title="`创建 ${d.created}`"
              />
              <div
                class="trend-bar completed"
                :style="{ height: (d.completed / maxTrend * 100) + '%' }"
                :title="`完成 ${d.completed}`"
              />
            </div>
            <span class="trend-day">{{ d.label }}</span>
          </div>
        </div>
        <div v-if="activeCount || completedCount" class="trend-legend">
          <span class="legend-dot" style="background: var(--c-gray-300)" /> 新建
          <span class="legend-dot" style="background: var(--c-success)" /> 完成
        </div>
      </div>

      <!-- Tags tab -->
      <div v-if="activeTab === 'tags'" class="tab-content">
        <p v-if="!store.tags.length" class="empty-msg">尚未创建标签</p>
        <p v-else-if="!tagDistribution.length" class="empty-msg">任务尚未添加标签</p>
        <div v-else class="tag-dist-list">
          <div v-for="t in tagDistribution" :key="t.uuid" class="tag-dist-row">
            <span class="tag-dist-name" :style="{ color: t.color }">{{ t.name }}</span>
            <div class="tag-dist-bar-track">
              <div
                class="tag-dist-bar-fill"
                :style="{
                  width: (t.count / tagDistribution[0].count * 100) + '%',
                  backgroundColor: t.color,
                }"
              />
            </div>
            <span class="tag-dist-num">{{ t.count }}</span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.stats-panel {
  width: 280px;
  flex-shrink: 0;
  height: 100%;
  background: var(--surface-primary);
  border-left: 1px solid var(--c-gray-200);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tab-switcher {
  display: flex;
  padding: 8px;
  gap: 4px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.tab-btn {
  flex: 1;
  padding: 5px 0;
  border: none;
  background: none;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--c-gray-400);
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.12s;
}
.tab-btn.active {
  background: var(--c-gray-100);
  color: var(--c-gray-700);
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-gray-400);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

/* Stat cards */
.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
}

.stat-card {
  background: var(--c-gray-50);
  border-radius: 10px;
  padding: 10px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-num {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1;
}

.stat-label {
  font-size: 11px;
  color: var(--c-gray-400);
}

/* Due row */
.due-row {
  display: flex;
  gap: 6px;
}

.due-item {
  flex: 1;
  border-radius: 8px;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.due-item.overdue { background: rgba(220, 38, 38, 0.08); }
.due-item.today { background: rgba(234, 88, 12, 0.08); }
.due-item.week { background: rgba(217, 119, 6, 0.08); }
.due-item.month { background: rgba(37, 99, 235, 0.08); }

.due-num {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.due-label {
  font-size: 11px;
  font-weight: 500;
}

.due-item.overdue .due-num, .due-item.overdue .due-label { color: #DC2626; }
.due-item.today .due-num, .due-item.today .due-label { color: #EA580C; }
.due-item.week .due-num, .due-item.week .due-label { color: #D97706; }
.due-item.month .due-num, .due-item.month .due-label { color: #2563EB; }

/* Quadrant bars */
.quadrant-dist {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.quadrant-bar-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.quadrant-bar-label {
  font-size: 11px;
  font-weight: 500;
  width: 64px;
  flex-shrink: 0;
  text-align: right;
}

.quadrant-bar-track {
  flex: 1;
  height: 8px;
  background: var(--c-gray-100);
  border-radius: 4px;
  overflow: hidden;
}

.quadrant-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
  min-width: 2px;
}

.quadrant-bar-num {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-gray-500);
  width: 24px;
  text-align: left;
}

/* Weekly trend */
.weekly-trend {
  display: flex;
  gap: 4px;
  align-items: flex-end;
  height: 80px;
}

.trend-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  height: 100%;
}

.trend-bars {
  flex: 1;
  width: 100%;
  display: flex;
  gap: 2px;
  align-items: flex-end;
  justify-content: center;
}

.trend-bar {
  width: 45%;
  border-radius: 2px;
  min-height: 2px;
  transition: height 0.3s ease;
}

.trend-bar.created { background: var(--c-gray-300); }
.trend-bar.completed { background: var(--c-success); }

.trend-day {
  font-size: 10px;
  color: var(--c-gray-400);
  white-space: nowrap;
}

.trend-legend {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 11px;
  color: var(--c-gray-400);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  display: inline-block;
}

/* Tags distribution */
.tag-dist-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.tag-dist-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tag-dist-name {
  font-size: 12px;
  font-weight: 500;
  width: 56px;
  flex-shrink: 0;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-dist-bar-track {
  flex: 1;
  height: 6px;
  background: var(--c-gray-100);
  border-radius: 3px;
  overflow: hidden;
}

.tag-dist-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
  min-width: 2px;
}

.tag-dist-num {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-gray-500);
  width: 20px;
}

.empty-msg {
  text-align: center;
  padding: 24px;
  color: var(--c-gray-400);
  font-size: 13px;
}
</style>
