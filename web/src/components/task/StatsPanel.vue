<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useTaskStore, getQuadrant } from '@/stores/task'

const store = useTaskStore()
const activeTab = ref<'overview' | 'activity'>('overview')

// ── 基础统计 ──
const activeCount = computed(() => store.serverTasks.filter(t => !t.completed).length)
const completedCount = computed(() => store.serverTasks.filter(t => t.completed).length)
const totalCount = computed(() => store.serverTasks.length)
const completionRate = computed(() => {
  if (!totalCount.value) return 0
  return Math.round((completedCount.value / totalCount.value) * 100)
})

const overdueCount = computed(() => {
  const today = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate())
  return store.serverTasks.filter(t => {
    if (!t.dueDate || t.completed) return false
    return new Date(t.dueDate) < today
  }).length
})

const todayCount = computed(() => {
  const today = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()).getTime()
  return store.serverTasks.filter(t => {
    if (!t.dueDate || t.completed) return false
    const dueDay = new Date(new Date(t.dueDate).getFullYear(), new Date(t.dueDate).getMonth(), new Date(t.dueDate).getDate()).getTime()
    return dueDay === today
  }).length
})

// ── 象限分布 ──
const quadrantDistribution = computed(() => {
  const dist: Record<string, number> = { Q1: 0, Q2: 0, Q3: 0, Q4: 0 }
  for (const t of store.serverTasks) {
    if (t.completed) continue
    dist[getQuadrant(t.urgencyLevel, t.importanceLevel)]++
  }
  return dist
})

const maxQuadrant = computed(() => Math.max(...Object.values(quadrantDistribution.value), 1))

const quadrants = [
  { key: 'Q1', label: '重要且紧急', color: '#DC2626', bg: 'rgba(220,38,38,0.08)' },
  { key: 'Q2', label: '重要不紧急', color: '#16A34A', bg: 'rgba(22,163,74,0.08)' },
  { key: 'Q3', label: '紧急不重要', color: '#2563EB', bg: 'rgba(37,99,235,0.08)' },
  { key: 'Q4', label: '不重要不紧急', color: '#D97706', bg: 'rgba(217,119,6,0.08)' },
]

// ── 近 7 天趋势 ──
const weekDays = computed(() => {
  const days: { label: string; completed: number; created: number; dateStr: string }[] = []
  const now = new Date()
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i)
    const ds = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
    const label = i === 0 ? '今' : i === 1 ? '昨' : `${d.getMonth()+1}/${d.getDate()}`
    const completed = store.serverTasks.filter(t => {
      if (!t.completed || !t.completedAt) return false
      return t.completedAt.startsWith(ds)
    }).length
    const created = store.serverTasks.filter(t => t.createdAt.startsWith(ds)).length
    days.push({ label, completed, created, dateStr: ds })
  }
  return days
})

const maxTrend = computed(() => Math.max(...weekDays.value.flatMap(d => [d.completed, d.created]), 1))

// ── 标签分布 ──
const tagDistribution = computed(() => {
  const map = new Map<string, { uuid: string; name: string; color: string; count: number }>()
  for (const t of store.serverTasks) {
    if (t.completed) continue
    const tags = t.tags
    if (!tags || !tags.length) continue
    const ids: string[] = typeof tags[0] === 'string' ? tags as string[] : (tags as {uuid:string}[]).map(tg => tg.uuid)
    for (const id of ids) {
      const tag = store.tags.find(tg => tg.uuid === id)
      if (!tag) continue
      if (!map.has(id)) map.set(id, { uuid: id, name: tag.name, color: tag.color, count: 0 })
      map.get(id)!.count++
    }
  }
  return [...map.values()].sort((a,b) => b.count - a.count)
})

// ── 月历数据 ──
const calYear = ref(new Date().getFullYear())
const calMonth = ref(new Date().getMonth()) // 0-indexed
const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

const calTitle = computed(() => `${calYear.value}年${calMonth.value + 1}月`)

const calWeeks = computed(() => {
  const firstDay = new Date(calYear.value, calMonth.value, 1)
  const lastDate = new Date(calYear.value, calMonth.value + 1, 0).getDate()
  const startDow = firstDay.getDay() // 0=Sun

  // 构建每天的任务统计
  const dayMap = new Map<string, { due: number; completed: number; overdue: number }>()
  const today = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate())
  for (const t of store.serverTasks) {
    if (!t.dueDate) continue
    const d = new Date(t.dueDate)
    const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
    if (!dayMap.has(key)) dayMap.set(key, { due: 0, completed: 0, overdue: 0 })
    const s = dayMap.get(key)!
    if (t.completed) s.completed++
    else if (d < today) s.overdue++
    else s.due++
  }

  const weeks: { day: number; key: string; stats: { due: number; completed: number; overdue: number } | null; isToday: boolean }[][] = []
  let row: typeof weeks[0] = []

  for (let i = 0; i < startDow; i++) {
    row.push({ day: 0, key: '', stats: null, isToday: false })
  }

  for (let d = 1; d <= lastDate; d++) {
    const key = `${calYear.value}-${calMonth.value}-${d}`
    const isToday = today.getTime() === new Date(calYear.value, calMonth.value, d).getTime()
    row.push({ day: d, key, stats: dayMap.get(key) ?? null, isToday })
    if (row.length === 7) { weeks.push(row); row = [] }
  }

  if (row.length > 0) {
    while (row.length < 7) row.push({ day: 0, key: '', stats: null, isToday: false })
    weeks.push(row)
  }

  return weeks
})

function prevMonth() { if (calMonth.value === 0) { calMonth.value = 11; calYear.value-- } else calMonth.value-- }
function nextMonth() { if (calMonth.value === 11) { calMonth.value = 0; calYear.value++ } else calMonth.value++ }

// 选中某天查看详情
const selectedDayKey = ref<string | null>(null)
const selectedDayLabel = computed(() => {
  if (!selectedDayKey.value) return ''
  const [y, m, d] = selectedDayKey.value.split('-')
  return `${y}年${Number(m)+1}月${Number(d)}日`
})
const selectedDayTasks = computed(() => {
  if (!selectedDayKey.value) return []
  return store.serverTasks.filter(t => {
    if (!t.dueDate) return false
    const due = new Date(t.dueDate)
    const key = `${due.getFullYear()}-${due.getMonth()}-${due.getDate()}`
    return key === selectedDayKey.value
  }).sort((a, b) => {
    // 未完成在前，再按紧急度排序
    if (a.completed !== b.completed) return a.completed ? 1 : -1
    return b.urgencyLevel - a.urgencyLevel
  })
})

function toggleDay(key: string) {
  selectedDayKey.value = selectedDayKey.value === key ? null : key
}

function qColor(t: { urgencyLevel: number; importanceLevel: number }): string {
  const q = getQuadrant(t.urgencyLevel, t.importanceLevel)
  const map: Record<string, string> = { Q1: '#DC2626', Q2: '#16A34A', Q3: '#2563EB', Q4: '#D97706' }
  return map[q] || '#999'
}

// ── 紧急-重要 5×5 矩阵热力图 ──
const matrixData = computed(() => {
  // matrixData[u][i] where u = urgencyLevel (1-5), i = importanceLevel (1-5)
  const grid: number[][] = Array.from({ length: 5 }, () => Array(5).fill(0))
  for (const t of store.serverTasks) {
    if (t.completed) continue
    const u = t.urgencyLevel - 1  // 0-indexed
    const im = t.importanceLevel - 1
    if (u >= 0 && u < 5 && im >= 0 && im < 5) {
      grid[im][u]++  // row=importance, col=urgency
    }
  }
  return grid
})

const matrixMax = computed(() => {
  let m = 0
  for (const row of matrixData.value) {
    for (const v of row) m = Math.max(m, v)
  }
  return Math.max(m, 1)
})

const matrixQuadrantLabel = computed(() => {
  // 找到任务最密集的象限
  const qCounts: Record<string, number> = { Q1: 0, Q2: 0, Q3: 0, Q4: 0 }
  for (const t of store.serverTasks) {
    if (t.completed) continue
    qCounts[getQuadrant(t.urgencyLevel, t.importanceLevel)]++
  }
  const maxQ = Object.entries(qCounts).sort((a, b) => b[1] - a[1])[0]
  const labels: Record<string, string> = {
    Q1: '重要且紧急 — 需要立即处理',
    Q2: '重要不紧急 — 建议投入更多时间',
    Q3: '紧急不重要 — 尽量委派或快速处理',
    Q4: '不重要不紧急 — 警惕时间黑洞',
  }
  return { key: maxQ[0], count: maxQ[1], label: labels[maxQ[0]] }
})

// ── 数字滚动动画 ──
function useAnimatedNumber(source: () => number) {
  const display = ref(0)
  let animId = 0
  watch(source, (to) => {
    const from = display.value
    const start = performance.now()
    const duration = 400
    const id = ++animId
    function step(now: number) {
      if (id !== animId) return
      const p = Math.min((now - start) / duration, 1)
      // ease-out
      const t = 1 - Math.pow(1 - p, 3)
      display.value = Math.round(from + (to - from) * t)
      if (p < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, { immediate: true })
  return display
}

const animRate = useAnimatedNumber(() => completionRate.value)
const animOverdue = useAnimatedNumber(() => overdueCount.value)
const animToday = useAnimatedNumber(() => todayCount.value)
const animActive = useAnimatedNumber(() => activeCount.value)
</script>

<template>
  <aside class="stats-panel">
    <!-- 标签页 -->
    <div class="tab-switcher">
      <button :class="['tab-btn', { active: activeTab === 'overview' }]" @click="activeTab = 'overview'">概览</button>
      <button :class="['tab-btn', { active: activeTab === 'activity' }]" @click="activeTab = 'activity'">动态</button>
    </div>

    <div class="panel-body">
      <!-- ═══════════ 概览 ═══════════ -->
      <div v-if="activeTab === 'overview'" class="tab-content">
        <!-- 今日状态卡 -->
        <section class="card today-card">
          <p class="card-label">今日完成率</p>
          <div class="donut-row">
            <!-- SVG 环形图 -->
            <svg class="donut-chart" viewBox="0 0 100 100">
              <defs>
                <linearGradient id="donutGrad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stop-color="#6366f1" />
                  <stop offset="100%" stop-color="#10b981" />
                </linearGradient>
              </defs>
              <circle class="donut-track" cx="50" cy="50" r="38"
                fill="none" stroke="var(--c-gray-200)" stroke-width="7" />
              <circle class="donut-fill" cx="50" cy="50" r="38"
                fill="none" stroke="url(#donutGrad)" stroke-width="7"
                stroke-linecap="round"
                :stroke-dasharray="2 * Math.PI * 38"
                :stroke-dashoffset="2 * Math.PI * 38 * (1 - completionRate / 100)"
                transform="rotate(-90 50 50)" />
              <text x="50" y="46" class="donut-num">{{ animRate }}</text>
              <text x="50" y="62" class="donut-unit">%</text>
            </svg>
            <!-- 状态药丸 -->
            <div class="status-pills">
              <span v-if="overdueCount" class="pill pill-overdue">
                {{ animOverdue }} 项过期
              </span>
              <span v-if="todayCount" class="pill pill-today">
                {{ animToday }} 项今日到期
              </span>
              <span class="pill pill-active">
                {{ animActive }} 项待完成
              </span>
            </div>
          </div>
        </section>

        <!-- 迷你月历 -->
        <section class="card cal-card">
          <div class="cal-header">
            <button class="cal-nav" @click="prevMonth()">
              <svg viewBox="0 0 16 16" width="12" height="12"><path d="M10 3L5 8l5 5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>
            </button>
            <span class="cal-title">{{ calTitle }}</span>
            <button class="cal-nav" @click="nextMonth()">
              <svg viewBox="0 0 16 16" width="12" height="12"><path d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>
            </button>
          </div>
          <div class="cal-grid">
            <div v-for="wd in WEEKDAYS" :key="'wd'+wd" class="cal-wd">{{ wd }}</div>
            <template v-for="(row, ri) in calWeeks" :key="'rw'+ri">
              <div
                v-for="(cell, ci) in row"
                :key="'cd'+ri+'-'+ci"
                class="cal-day"
                :class="{
                  'cal-today': cell.isToday,
                  'cal-empty': !cell.day,
                  'cal-clickable': cell.day && cell.stats,
                  'cal-selected': cell.key && selectedDayKey === cell.key,
                }"
                @click="cell.key && cell.stats && toggleDay(cell.key)"
              >
                <span v-if="cell.day" class="cal-day-num">{{ cell.day }}</span>
                <span v-if="cell.stats" class="cal-dots">
                  <span v-if="cell.stats.overdue" class="cal-dot od" />
                  <span v-if="cell.stats.due" class="cal-dot du" />
                  <span v-if="cell.stats.completed" class="cal-dot dn" />
                </span>
              </div>
            </template>
          </div>

          <!-- 选中日期的任务详情 -->
          <div v-if="selectedDayKey && selectedDayTasks.length" class="cal-detail">
            <div class="cal-detail-hd">
              <span class="cal-detail-date">{{ selectedDayLabel }}</span>
              <button class="cal-detail-close" @click="selectedDayKey = null">
                <svg viewBox="0 0 16 16" width="12" height="12"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
              </button>
            </div>
            <div class="cal-detail-list">
              <div
                v-for="t in selectedDayTasks"
                :key="t.uuid"
                class="cal-task-item"
                :class="{ 'cal-task-done': t.completed }"
              >
                <span class="cal-task-q" :style="{ color: qColor(t) }">●</span>
                <span class="cal-task-title">{{ t.title }}</span>
                <span v-if="t.completed" class="cal-task-check">✓</span>
              </div>
            </div>
          </div>
          <div v-else-if="selectedDayKey && !selectedDayTasks.length" class="cal-detail">
            <p class="cal-detail-empty">{{ selectedDayLabel }} 没有到期任务</p>
          </div>

          <div class="cal-legend">
            <span><i class="cl-dot cl-overdue" />过期</span>
            <span><i class="cl-dot cl-due" />待办</span>
            <span><i class="cl-dot cl-done" />完成</span>
          </div>
        </section>

        <!-- 紧急-重要 5×5 热力图 -->
        <section class="card">
          <p class="card-label">紧急 → 重要矩阵</p>
          <div class="matrix-grid">
            <div class="matrix-header-corner" />
            <div v-for="u in 5" :key="'hu'+u" class="matrix-col-label">{{ u }}</div>
            <template v-for="im in 5" :key="'row'+im">
              <div class="matrix-row-label">{{ 6 - im }}</div>
              <div
                v-for="u in 5"
                :key="'cell'+im+'-'+u"
                class="matrix-cell"
                :style="{
                  backgroundColor: matrixData[5-im][u-1]
                    ? `rgba(99,102,241,${0.06 + (matrixData[5-im][u-1] / matrixMax) * 0.74})`
                    : 'transparent',
                  color: matrixData[5-im][u-1] / matrixMax > 0.5 ? '#fff' : 'var(--c-gray-600)',
                }"
                :title="`紧急${u} · 重要${6-im}: ${matrixData[5-im][u-1]} 个任务`"
              >
                {{ matrixData[5-im][u-1] || '' }}
              </div>
            </template>
          </div>
          <p class="matrix-insight">
            最多集中在 <strong>{{ matrixQuadrantLabel.key }}</strong>（{{ matrixQuadrantLabel.count }} 个）— {{ matrixQuadrantLabel.label }}
          </p>
        </section>

      </div>

      <!-- ═══════════ 标签 ═══════════ -->
      <div v-if="activeTab === 'activity'" class="tab-content">
        <!-- 象限分布 -->
        <section class="card">
          <p class="card-label">象限分布</p>
          <div class="quadrant-bars">
            <div v-for="q in quadrants" :key="q.key" class="qb-row">
              <span class="qb-name" :style="{ color: q.color }">{{ q.label }}</span>
              <div class="qb-track">
                <div
                  class="qb-fill"
                  :style="{
                    width: (quadrantDistribution[q.key] / maxQuadrant * 100) + '%',
                    background: q.color,
                  }"
                />
              </div>
              <span class="qb-num" :style="{ color: q.color }">{{ quadrantDistribution[q.key] }}</span>
            </div>
          </div>
        </section>

        <!-- 近 7 天趋势 -->
        <section class="card">
          <p class="card-label">近 7 天趋势</p>
          <div class="sparkline">
            <div
              v-for="d in weekDays"
              :key="d.dateStr"
              class="spark-col"
              :title="`${d.label} 新建${d.created} 完成${d.completed}`"
            >
              <div class="spark-bars">
                <div
                  class="spark-bar created"
                  :style="{ height: (d.created / maxTrend * 100) + '%' }"
                />
                <div
                  class="spark-bar completed"
                  :style="{ height: (d.completed / maxTrend * 100) + '%' }"
                />
              </div>
              <span class="spark-label">{{ d.label }}</span>
            </div>
          </div>
          <div class="trend-legend">
            <span><span class="ldot ldot-created" /> 新建</span>
            <span><span class="ldot ldot-completed" /> 完成</span>
          </div>
        </section>

        <!-- 标签分布 -->
        <section class="card">
          <p class="card-label">标签分布</p>
          <p v-if="!store.tags.length" class="empty">尚未创建标签</p>
          <p v-else-if="!tagDistribution.length" class="empty">任务尚未添加标签</p>
          <div v-else class="tag-list">
            <div v-for="t in tagDistribution" :key="t.uuid" class="tag-row">
              <span class="tag-name" :style="{ color: t.color }">{{ t.name }}</span>
              <div class="tag-track">
                <div class="tag-fill" :style="{ width: (t.count / tagDistribution[0].count * 100) + '%', background: t.color }" />
              </div>
              <span class="tag-num">{{ t.count }}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  </aside>
</template>

<style scoped>
/* ═══════════ 容器 ═══════════ */
.stats-panel {
  width: 240px;
  flex-shrink: 0;
  height: 100%;
  background: var(--surface-primary);
  border-left: 1px solid var(--c-gray-100);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tab-switcher {
  display: flex;
  padding: 8px 10px;
  gap: 4px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}
.tab-btn {
  flex: 1;
  padding: 6px 0;
  border: none;
  background: none;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--c-gray-400);
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.15s;
}
.tab-btn.active {
  background: var(--c-gray-100);
  color: var(--c-gray-800);
  font-weight: 600;
}
.tab-btn:hover:not(.active) { color: var(--c-gray-600); }

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ═══════════ 卡片 ═══════════ */
.card {
  padding: 14px;
  border-radius: 14px;
  background: var(--c-gray-50);
  border: 1px solid var(--border-light);
}
.card-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-gray-500);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 10px;
}

/* ═══════════ 今日状态 ═══════════ */
.today-card {
  background: linear-gradient(135deg, rgba(99,102,241,0.04), rgba(16,185,129,0.04));
}

.donut-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.donut-chart {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
  filter: drop-shadow(0 2px 4px rgba(99,102,241,0.15));
}

.donut-track {
  opacity: 0.4;
}

.donut-fill {
  transition: stroke-dashoffset 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.donut-num {
  font-size: 18px;
  font-weight: 800;
  fill: var(--c-gray-900);
  text-anchor: middle;
  dominant-baseline: central;
}

.donut-unit {
  font-size: 9px;
  font-weight: 600;
  fill: var(--c-gray-400);
  text-anchor: middle;
  dominant-baseline: central;
}

/* 状态药丸 */
.status-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pill {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  line-height: 1.5;
}
.pill-overdue { background: rgba(220,38,38,0.1); color: #DC2626; }
.pill-today   { background: rgba(234,88,12,0.1); color: #EA580C; }
.pill-active  { background: rgba(37,99,235,0.08); color: #2563EB; }

/* ═══════════ 象限分布 ═══════════ */
.quadrant-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.qb-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.qb-name {
  width: 70px;
  font-size: 11px;
  font-weight: 500;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qb-track {
  flex: 1;
  height: 6px;
  background: var(--c-gray-200);
  border-radius: 3px;
  overflow: hidden;
}
.qb-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s cubic-bezier(0.4,0,0.2,1);
}
.qb-num {
  font-size: 12px;
  font-weight: 700;
  min-width: 18px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* ═══════════ 趋势 ═══════════ */
.sparkline {
  display: flex;
  gap: 4px;
  align-items: flex-end;
  height: 52px;
}
.spark-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  height: 100%;
}
.spark-bars {
  flex: 1;
  width: 100%;
  display: flex;
  gap: 2px;
  align-items: flex-end;
  justify-content: center;
}
.spark-bar {
  width: 8px;
  border-radius: 2px 2px 0 0;
  min-height: 2px;
  transition: height 0.4s ease;
}
.spark-bar.created   { background: var(--c-gray-300); }
.spark-bar.completed { background: var(--c-success); }

.spark-label {
  font-size: 10px;
  color: var(--c-gray-400);
}

.trend-legend {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  font-size: 10px;
  color: var(--c-gray-400);
}
.ldot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 2px;
  margin-right: 3px;
  vertical-align: -1px;
}
.ldot-created   { background: var(--c-gray-300); }
.ldot-completed { background: var(--c-success); }

/* ═══════════ 标签 ═══════════ */
.tag-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tag-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.tag-name {
  width: 52px;
  font-size: 12px;
  font-weight: 500;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}
.tag-track {
  flex: 1;
  height: 6px;
  background: var(--c-gray-200);
  border-radius: 3px;
  overflow: hidden;
}
.tag-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
  min-width: 2px;
}
.tag-num {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-gray-500);
  width: 18px;
  text-align: right;
}

.empty {
  text-align: center;
  padding: 20px 12px;
  color: var(--c-gray-400);
  font-size: 12px;
}

/* ═══════════ 迷你月历 ═══════════ */
.cal-card {
  padding: 10px 12px 12px;
}

.cal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.cal-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-gray-800);
}

.cal-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  background: var(--c-gray-100);
  border-radius: 6px;
  color: var(--c-gray-500);
  cursor: pointer;
  transition: background 0.12s;
}
.cal-nav:hover { background: var(--c-gray-200); color: var(--c-gray-700); }

.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
}

.cal-wd {
  text-align: center;
  font-size: 9px;
  font-weight: 600;
  color: var(--c-gray-400);
  padding: 2px 0 4px;
}

.cal-day {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  aspect-ratio: 1;
  border-radius: 5px;
  padding: 2px 0;
  position: relative;
  gap: 1px;
}

.cal-day-num {
  font-size: 10px;
  font-weight: 500;
  color: var(--c-gray-600);
  line-height: 1;
}

.cal-today .cal-day-num {
  background: var(--c-brand-500);
  color: #fff;
  border-radius: 50%;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}

.cal-empty { pointer-events: none; }

/* 迷你指示点 */
.cal-dots {
  display: flex;
  gap: 2px;
  justify-content: center;
}

.cal-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  flex-shrink: 0;
}
.cal-dot.od { background: #DC2626; }
.cal-dot.du { background: #2563EB; }
.cal-dot.dn { background: #16A34A; }

/* 图例 */
.cal-legend {
  display: flex;
  gap: 10px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid var(--border-light);
}

.cal-legend span {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 9px;
  color: var(--c-gray-400);
}

.cl-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.cl-overdue { background: #DC2626; }
.cl-due     { background: #2563EB; }
.cl-done    { background: #16A34A; }

/* 可点击日期 */
.cal-clickable {
  cursor: pointer;
  transition: background 0.12s;
}
.cal-clickable:hover {
  background: var(--c-gray-200);
}

.cal-selected {
  background: var(--c-brand-50) !important;
  outline: 1.5px solid var(--c-brand-500);
  outline-offset: -1px;
}

/* 日期详情面板 */
.cal-detail {
  margin-top: 8px;
  padding: 8px 0 0;
  border-top: 1px solid var(--border-light);
  animation: calFadeIn 0.18s ease;
}

@keyframes calFadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.cal-detail-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.cal-detail-date {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-gray-800);
}

.cal-detail-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  background: var(--c-gray-100);
  border-radius: 50%;
  color: var(--c-gray-400);
  cursor: pointer;
}
.cal-detail-close:hover { background: var(--c-gray-200); color: var(--c-gray-600); }

.cal-detail-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-height: 120px;
  overflow-y: auto;
}

.cal-task-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 6px;
  border-radius: 5px;
  font-size: 11px;
  transition: background 0.1s;
}
.cal-task-item:hover { background: var(--c-gray-100); }

.cal-task-done {
  opacity: 0.55;
}
.cal-task-done .cal-task-title {
  text-decoration: line-through;
}

.cal-task-q {
  font-size: 8px;
  flex-shrink: 0;
}

.cal-task-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--c-gray-700);
}

.cal-task-check {
  font-size: 10px;
  color: var(--c-success);
  font-weight: 700;
}

.cal-detail-empty {
  text-align: center;
  font-size: 11px;
  color: var(--c-gray-400);
  padding: 8px 0;
  margin: 0;
}

/* ═══════════ 5×5 紧急-重要热力图 ═══════════ */
.matrix-grid {
  display: grid;
  grid-template-columns: 18px repeat(5, 1fr);
  grid-template-rows: 16px repeat(5, 28px);
  gap: 2px;
  align-items: center;
}

.matrix-header-corner {
  /* 左上角空白 */
}

.matrix-col-label {
  text-align: center;
  font-size: 10px;
  font-weight: 500;
  color: var(--c-gray-400);
}

.matrix-row-label {
  text-align: center;
  font-size: 10px;
  font-weight: 500;
  color: var(--c-gray-400);
}

.matrix-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  aspect-ratio: 1;
  transition: background-color 0.3s ease;
  cursor: default;
}

.matrix-insight {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--c-gray-500);
  line-height: 1.5;
}

.matrix-insight strong {
  color: var(--c-brand-500);
}
</style>
