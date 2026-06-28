import { useMemo } from 'react'
import { useStore } from '../store/useStore'
import { QUADRANT_CONFIG, Quadrant, getDueStatus, getQuadrant } from '../types'

const QUADRANT_ORDER: Quadrant[] = [Quadrant.Q1, Quadrant.Q2, Quadrant.Q3, Quadrant.Q4]

interface StatsPanelProps {
  onClose: () => void
}

export function StatsPanel({ onClose }: StatsPanelProps) {
  const tasks = useStore((s) => s.tasks)
  const tags = useStore((s) => s.tags)

  const stats = useMemo(() => {
    const total = tasks.length
    const completed = tasks.filter((t) => t.completed).length
    const active = total - completed

    // 象限分布（活跃任务）
    const quadrantCounts: Record<string, number> = { Q1: 0, Q2: 0, Q3: 0, Q4: 0 }
    tasks.filter((t) => !t.completed).forEach((t) => {
      quadrantCounts[getQuadrant(t.posX, t.posY)]++
    })

    // 日期状态
    let overdue = 0, today = 0, thisWeek = 0
    tasks.filter((t) => !t.completed).forEach((t) => {
      const s = getDueStatus(t.dueDate)
      if (s === 'overdue') overdue++
      else if (s === 'today') today++
      else if (s === 'thisWeek') thisWeek++
    })

    // 标签分布
    const tagCounts: { name: string; color: string; count: number }[] = tags.map((tag) => ({
      name: tag.name,
      color: tag.color,
      count: tasks.filter((t) => !t.completed && t.tags.includes(tag.id)).length,
    })).filter((t) => t.count > 0).sort((a, b) => b.count - a.count)

    // 完成率趋势（按天，最近 7 天）
    const last7Days: { date: string; completed: number }[] = []
    for (let i = 6; i >= 0; i--) {
      const d = new Date()
      d.setDate(d.getDate() - i)
      const key = d.toISOString().slice(0, 10)
      const count = tasks.filter((t) => {
        if (!t.completedAt) return false
        return t.completedAt.slice(0, 10) === key
      }).length
      last7Days.push({ date: key.slice(5), completed: count })
    }

    return {
      total,
      active,
      completed,
      completionRate: total > 0 ? Math.round((completed / total) * 100) : 0,
      quadrantCounts,
      overdue,
      today,
      thisWeek,
      tagCounts,
      last7Days,
      maxDayCount: Math.max(1, ...last7Days.map((d) => d.completed)),
    }
  }, [tasks, tags])

  return (
    <div
      className="fixed inset-0 z-[110] flex items-center justify-center bg-black/15 backdrop-blur-sm px-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="bg-white rounded-3xl shadow-xl shadow-purple-100/50 w-full max-w-sm p-6 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题 */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold text-gray-600">📊 任务统计</h2>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100
                       text-gray-300 hover:text-gray-500 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 概览卡片 */}
        <div className="grid grid-cols-3 gap-2 mb-5">
          <div className="bg-purple-50 rounded-2xl p-3 text-center">
            <div className="text-2xl font-bold text-purple-500">{stats.active}</div>
            <div className="text-[10px] text-gray-400 mt-0.5">活跃</div>
          </div>
          <div className="bg-green-50 rounded-2xl p-3 text-center">
            <div className="text-2xl font-bold text-green-500">{stats.completed}</div>
            <div className="text-[10px] text-gray-400 mt-0.5">已完成</div>
          </div>
          <div className="bg-blue-50 rounded-2xl p-3 text-center">
            <div className="text-2xl font-bold text-blue-500">{stats.completionRate}%</div>
            <div className="text-[10px] text-gray-400 mt-0.5">完成率</div>
          </div>
        </div>

        {/* 紧急状态 */}
        <div className="flex gap-2 mb-5">
          <div className="flex-1 bg-red-50 rounded-2xl p-2.5 text-center">
            <div className="text-lg font-bold text-red-400">{stats.overdue}</div>
            <div className="text-[10px] text-gray-400">已过期</div>
          </div>
          <div className="flex-1 bg-orange-50 rounded-2xl p-2.5 text-center">
            <div className="text-lg font-bold text-orange-400">{stats.today}</div>
            <div className="text-[10px] text-gray-400">今天到期</div>
          </div>
          <div className="flex-1 bg-yellow-50 rounded-2xl p-2.5 text-center">
            <div className="text-lg font-bold text-yellow-500">{stats.thisWeek}</div>
            <div className="text-[10px] text-gray-400">本周到期</div>
          </div>
        </div>

        {/* 象限分布 */}
        <h3 className="text-xs font-semibold text-gray-500 mb-3">象限分布</h3>
        <div className="space-y-2 mb-5">
          {QUADRANT_ORDER.map((q) => {
            const info = QUADRANT_CONFIG[q]
            const count = stats.quadrantCounts[q] || 0
            const pct = stats.active > 0 ? Math.round((count / stats.active) * 100) : 0
            return (
              <div key={q} className="flex items-center gap-3">
                <span className="text-[10px] text-gray-400 w-4">{q}</span>
                <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.max(pct, count > 0 ? 4 : 0)}%`,
                      backgroundColor: info.color,
                      minWidth: count > 0 ? '8px' : '0',
                    }}
                  />
                </div>
                <span className="text-[11px] font-medium text-gray-500 w-8 text-right">{count}</span>
                <span className="text-[10px] text-gray-350 w-8 text-right">{pct}%</span>
              </div>
            )
          })}
        </div>

        {/* 标签分布 */}
        {stats.tagCounts.length > 0 && (
          <>
            <h3 className="text-xs font-semibold text-gray-500 mb-3">标签分布</h3>
            <div className="space-y-2 mb-5">
              {stats.tagCounts.slice(0, 6).map((tag) => {
                const pct = stats.active > 0 ? Math.round((tag.count / stats.active) * 100) : 0
                return (
                  <div key={tag.name} className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: tag.color }} />
                    <span className="text-[11px] text-gray-500 flex-1 truncate">{tag.name}</span>
                    <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden max-w-[100px]">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${Math.max(pct, 3)}%`,
                          backgroundColor: tag.color,
                          opacity: 0.6,
                        }}
                      />
                    </div>
                    <span className="text-[10px] text-gray-400 w-6 text-right">{tag.count}</span>
                  </div>
                )
              })}
            </div>
          </>
        )}

        {/* 最近 7 天完成趋势 */}
        <h3 className="text-xs font-semibold text-gray-500 mb-3">最近 7 天完成</h3>
        <div className="flex items-end gap-1 h-16 mb-1">
          {stats.last7Days.map((day) => {
            const h = Math.max(4, Math.round((day.completed / stats.maxDayCount) * 100))
            return (
              <div key={day.date} className="flex-1 flex flex-col items-center gap-0.5">
                <span className="text-[10px] text-gray-500 font-medium">{day.completed || ''}</span>
                <div
                  className="w-full rounded-t-md transition-all duration-300"
                  style={{
                    height: `${h}%`,
                    backgroundColor: day.completed > 0 ? '#A78BFA' : '#E8E0EF',
                    minHeight: '4px',
                  }}
                />
                <span className="text-[9px] text-gray-350">{day.date}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
