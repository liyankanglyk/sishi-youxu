<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { adminApi, type DashboardStats } from '@/api/admin'

const stats = ref<DashboardStats | null>(null)
const loading = ref(false)

// Chart
const chartRef = ref<HTMLDivElement>()
let chartInstance: echarts.ECharts | null = null
const activeMetric = ref('new_users')
const chartData = ref<Array<{ date: string; count: number }>>([])
const chartLoading = ref(false)

const metricOptions = [
  { label: '新增用户', value: 'new_users' },
  { label: '创建任务', value: 'tasks_created' },
  { label: '完成任务', value: 'tasks_completed' },
] as const

async function fetchStats() {
  loading.value = true
  try {
    const { data } = await adminApi.getStats()
    stats.value = data
  } catch (err: any) {
    ElMessage.error(err?.message || '加载统计数据失败')
  } finally { loading.value = false }
}

async function fetchChart() {
  chartLoading.value = true
  try {
    const { data } = await adminApi.getChart(activeMetric.value)
    chartData.value = data?.data ?? []
    renderChart()
  } catch (err: any) {
    ElMessage.error(err?.message || '加载图表数据失败')
  } finally { chartLoading.value = false }
}

function renderChart() {
  if (!chartInstance || !chartData.value.length) return
  const labels: Record<string, string> = {
    new_users: '新增用户',
    tasks_created: '创建任务',
    tasks_completed: '完成任务',
  }
  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#e2e8f0',
      textStyle: { color: '#1e293b', fontSize: 13 },
      boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
    },
    grid: { left: '2%', right: '3%', top: '8%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: chartData.value.map(d => d.date),
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { show: false },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
    },
    series: [{
      name: labels[activeMetric.value],
      type: 'line',
      data: chartData.value.map(d => d.count),
      smooth: true,
      showSymbol: false,
      lineStyle: { color: '#6366f1', width: 2.5 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(99,102,241,0.18)' },
          { offset: 1, color: 'rgba(99,102,241,0.01)' },
        ]),
      },
    }],
  } as echarts.EChartsOption)
}

function handleResize() { chartInstance?.resize() }

watch(activeMetric, () => fetchChart())

onMounted(async () => {
  await fetchStats()
  await nextTick()
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value)
    window.addEventListener('resize', handleResize)
    await fetchChart()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<template>
  <div class="dashboard">
    <!-- Stat Cards -->
    <div class="stat-grid">
      <div class="stat-card stat-users">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        </div>
        <div class="stat-body">
          <span class="stat-label">总用户数</span>
          <span class="stat-value">{{ stats?.total_users ?? '-' }}</span>
        </div>
      </div>

      <div class="stat-card stat-active">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        </div>
        <div class="stat-body">
          <span class="stat-label">今日活跃</span>
          <span class="stat-value">{{ stats?.active_users_today ?? '-' }}</span>
        </div>
      </div>

      <div class="stat-card stat-tasks">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        </div>
        <div class="stat-body">
          <span class="stat-label">总任务数</span>
          <span class="stat-value">{{ stats?.total_tasks ?? '-' }}</span>
        </div>
      </div>

      <div class="stat-card stat-done">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
        </div>
        <div class="stat-body">
          <span class="stat-label">今日完成</span>
          <span class="stat-value">{{ stats?.completed_tasks_today ?? '-' }}</span>
        </div>
      </div>
    </div>

    <!-- Charts Row -->
    <div class="chart-row">
      <!-- Quadrant -->
      <div class="card quadrant-card">
        <div class="card-header">
          <h3>象限分布</h3>
          <span class="card-sub">艾森豪威尔矩阵</span>
        </div>
        <div class="quadrant-matrix-wrap" v-if="stats?.quadrant_distribution">
          <!-- Top axis: 重要 -->
          <div class="qm-top-label">重要 ↑</div>
          <div class="qm-row">
            <!-- Left axis: 不紧急 -->
            <div class="qm-left-label">← 不紧急</div>
            <!-- 2x2 Grid -->
            <div class="qm-grid">
              <div class="qm-cell qm-q2">
                <strong>{{ stats.quadrant_distribution.q2 }}</strong>
                <span>重要不紧急</span>
              </div>
              <div class="qm-cell qm-q1">
                <strong>{{ stats.quadrant_distribution.q1 }}</strong>
                <span>重要且紧急</span>
              </div>
              <div class="qm-cell qm-q4">
                <strong>{{ stats.quadrant_distribution.q4 }}</strong>
                <span>不重要不紧急</span>
              </div>
              <div class="qm-cell qm-q3">
                <strong>{{ stats.quadrant_distribution.q3 }}</strong>
                <span>不重要紧急</span>
              </div>
            </div>
            <!-- Right axis: 紧急 -->
            <div class="qm-right-label">紧急 →</div>
          </div>
          <!-- Bottom axis: 不重要 -->
          <div class="qm-bottom-label">不重要 ↓</div>
        </div>
        <div v-else class="card-empty">
          <span class="empty-text">暂无数据</span>
        </div>
      </div>

      <!-- Trend -->
      <div class="card chart-card">
        <div class="card-header">
          <h3>时间趋势</h3>
          <div class="metric-tabs">
            <button
              v-for="m in metricOptions"
              :key="m.value"
              :class="['metric-tab', { active: activeMetric === m.value }]"
              @click="activeMetric = m.value"
            >{{ m.label }}</button>
          </div>
        </div>
        <div v-loading="chartLoading" ref="chartRef" class="chart-container" />
        <div v-if="!chartData.length && !chartLoading" class="card-empty">
          <span class="empty-text">暂无数据</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ===== Stat Grid ===== */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  border: 1px solid #e2e8f0;
  transition: box-shadow 250ms ease, transform 150ms ease;
}

.stat-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  transform: translateY(-1px);
}

.stat-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-users .stat-icon { background: #eef2ff; color: #6366f1; }
.stat-active .stat-icon { background: #ecfdf5; color: #10b981; }
.stat-tasks .stat-icon { background: #fef3c7; color: #f59e0b; }
.stat-done .stat-icon { background: #fce7f3; color: #ec4899; }

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-label {
  font-size: 12.5px;
  color: #94a3b8;
  font-weight: 500;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
  line-height: 1;
}

/* ===== Chart Row ===== */
.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

/* ===== Card ===== */
.card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.card-header {
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.card-sub {
  font-size: 12px;
  color: #94a3b8;
}

.card-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
}

.empty-text {
  color: #cbd5e1;
  font-size: 14px;
}

/* ===== Quadrant Matrix ===== */
.quadrant-matrix-wrap {
  padding: 16px 20px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.qm-top-label,
.qm-bottom-label {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-align: center;
}

.qm-row {
  display: flex;
  align-items: stretch;
  gap: 6px;
  flex: 1;
  width: 100%;
}

.qm-left-label,
.qm-right-label {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
  letter-spacing: 0.04em;
  min-width: 20px;
}

.qm-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 3px;
  flex: 1;
}

.qm-cell {
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border-radius: 8px;
  transition: transform 150ms ease;
}

.qm-cell:hover {
  transform: scale(1.03);
}

.qm-cell strong {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
}

.qm-cell span {
  font-size: 11.5px;
  font-weight: 500;
  opacity: 0.8;
  text-align: center;
}

.qm-q1 { background: #fee2e2; }
.qm-q1 strong { color: #dc2626; }
.qm-q1 span { color: #991b1b; }

.qm-q2 { background: #dcfce7; }
.qm-q2 strong { color: #16a34a; }
.qm-q2 span { color: #166534; }

.qm-q3 { background: #dbeafe; }
.qm-q3 strong { color: #2563eb; }
.qm-q3 span { color: #1e40af; }

.qm-q4 { background: #fef3c7; }
.qm-q4 strong { color: #d97706; }
.qm-q4 span { color: #92400e; }

/* ===== Metric Tabs ===== */
.metric-tabs {
  display: flex;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 3px;
  gap: 2px;
}

.metric-tab {
  border: none;
  background: transparent;
  padding: 5px 14px;
  border-radius: 6px;
  font-size: 12.5px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 150ms ease;
  font-family: inherit;
}

.metric-tab.active {
  background: #fff;
  color: #6366f1;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.metric-tab:hover:not(.active) {
  color: #475569;
}

/* ===== Chart ===== */
.chart-container {
  width: 100%;
  height: 360px;
  padding: 16px;
}

/* ===== Responsive ===== */
@media (max-width: 1200px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .chart-row { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .stat-grid { grid-template-columns: 1fr; }
}
</style>
