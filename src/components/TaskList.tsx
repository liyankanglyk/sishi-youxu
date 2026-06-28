import { useState, useMemo, useCallback } from 'react'
import { useStore, useGroupedTasks } from '../store/useStore'
import { QUADRANT_CONFIG, Quadrant } from '../types'
import { getDueStatus, DUE_STATUS_CONFIG } from '../types'
import type { Task } from '../types'
import { taskDB } from '../db'
import { MagnifyingGlass, CaretRight, Check, Repeat, NotePencil } from '@phosphor-icons/react'

const QUADRANT_ORDER: Quadrant[] = [Quadrant.Q1, Quadrant.Q2, Quadrant.Q3, Quadrant.Q4]

export function TaskList() {
  const grouped = useGroupedTasks()
  const searchQuery = useStore((s) => s.searchQuery)
  const setSearchQuery = useStore((s) => s.setSearchQuery)
  const tagFilter = useStore((s) => s.tagFilter)
  const dueFilter = useStore((s) => s.dueFilter)
  const selectedQuadrant = useStore((s) => s.selectedQuadrant)
  const toggleTagFilter = useStore((s) => s.toggleTagFilter)
  const setDueFilter = useStore((s) => s.setDueFilter)
  const setQuadrantFilter = useStore((s) => s.setQuadrantFilter)
  const clearFilters = useStore((s) => s.clearFilters)
  const setEditingTaskId = useStore((s) => s.setEditingTaskId)
  const completeTask = useStore((s) => s.completeTask)
  const tags = useStore((s) => s.tags)
  const hasActiveFilters = searchQuery || selectedQuadrant || tagFilter.length > 0 || dueFilter !== 'all'
  const tagMap = useMemo(() => {
    const m: Record<string, { name: string; color: string }> = {}
    tags.forEach((t) => { m[t.id] = { name: t.name, color: t.color } })
    return m
  }, [tags])
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [showCompleted, setShowCompleted] = useState(false)
  const [completedTasks, setCompletedTasks] = useState<Task[]>([])

  const toggleCollapse = (q: string) => {
    setCollapsed((prev) => ({ ...prev, [q]: !prev[q] }))
  }

  const loadCompletedTasks = useCallback(async () => {
    if (!showCompleted) {
      const tasks = await taskDB.getCompleted()
      // 按完成时间倒序
      tasks.sort((a, b) => {
        const da = a.completedAt || a.updatedAt
        const db = b.completedAt || b.updatedAt
        return db.localeCompare(da)
      })
      setCompletedTasks(tasks)
    }
    setShowCompleted(!showCompleted)
  }, [showCompleted])

  const reopenTask = useStore((s) => s.reopenTask)
  const permanentDeleteTask = useStore((s) => s.permanentDeleteTask)

  const handleReopen = useCallback(async (id: string) => {
    await reopenTask(id)
    setCompletedTasks((prev) => prev.filter((t) => t.id !== id))
  }, [reopenTask])

  const handlePermanentDelete = useCallback(async (id: string) => {
    await permanentDeleteTask(id)
    setCompletedTasks((prev) => prev.filter((t) => t.id !== id))
  }, [permanentDeleteTask])

  const totalCount = Object.values(grouped).reduce((sum, tasks) => sum + tasks.length, 0)

  return (
    <div className="flex flex-col h-full">
      {/* 搜索框 */}
      <div className="p-4 pb-3">
        <div className="relative">
          <MagnifyingGlass weight="regular" className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
                           style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`搜索 ${totalCount} 个任务…`}
            data-search-input
            className="w-full pl-8 pr-3 py-2 text-xs border-0 rounded-xl bg-white/70
                       focus:outline-none focus:ring-2 focus:ring-purple-200/60 focus:bg-white
                       placeholder:text-gray-300 transition-all"
          />
        </div>

        {/* 筛选器 */}
        <div className="px-4 pb-2 space-y-1.5">
          {/* 象限筛选 */}
          <div className="flex gap-1 flex-wrap">
            {QUADRANT_ORDER.map((q) => {
              const info = QUADRANT_CONFIG[q]
              return (
                <button
                  key={q}
                  onClick={() => setQuadrantFilter(selectedQuadrant === q ? null : q)}
                  className={`text-[10px] px-2 py-0.5 rounded-full font-medium transition-all ${
                    selectedQuadrant === q
                      ? 'text-white shadow-sm'
                      : 'text-gray-400 bg-gray-100 hover:bg-gray-200'
                  }`}
                  style={selectedQuadrant === q ? { backgroundColor: info.color } : {}}
                >
                  {info.label}
                </button>
              )
            })}
          </div>

          {/* 日期筛选 */}
          <div className="flex gap-1 flex-wrap">
            {(['overdue', 'today', 'thisWeek'] as const).map((f) => {
              const cfg = DUE_STATUS_CONFIG[f]
              return (
                <button
                  key={f}
                  onClick={() => setDueFilter(dueFilter === f ? 'all' : f)}
                  className={`text-[10px] px-2 py-0.5 rounded-full font-medium transition-all ${
                    dueFilter === f
                      ? 'text-white shadow-sm'
                      : 'text-gray-400 bg-gray-100 hover:bg-gray-200'
                  }`}
                  style={dueFilter === f ? { backgroundColor: cfg.color } : {}}
                >
                  {cfg.label}
                </button>
              )
            })}
          </div>

          {/* 标签筛选 + 清除 */}
          <div className="flex gap-1 flex-wrap items-center">
            {tags.map((tag) => (
              <button
                key={tag.id}
                onClick={() => toggleTagFilter(tag.id)}
                className={`text-[10px] px-2 py-0.5 rounded-full font-medium transition-all ${
                  tagFilter.includes(tag.id)
                    ? 'text-white shadow-sm'
                    : 'text-gray-400 bg-gray-100 hover:bg-gray-200'
                }`}
                style={tagFilter.includes(tag.id) ? { backgroundColor: tag.color } : {}}
              >
                {tag.name}
              </button>
            ))}
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="text-[10px] px-2 py-0.5 rounded-full text-red-400 bg-red-50 hover:bg-red-100 font-medium transition-all ml-auto"
              >
                清除
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 象限分组列表 */}
      <div className="flex-1 overflow-y-auto px-3 pb-4 space-y-1">
        {QUADRANT_ORDER.map((q) => {
          const info = QUADRANT_CONFIG[q]
          const tasks = grouped[q] || []
          const isCollapsed = collapsed[q] ?? false

          return (
            <div key={q}>
              {/* 分组头 */}
              <button
                onClick={() => toggleCollapse(q)}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl
                           hover:bg-white/70 transition-all duration-200 text-left"
              >
                <div
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0 ring-2 ring-white"
                  style={{ backgroundColor: info.color }}
                />
                <span className="text-xs font-semibold text-gray-500 flex-1">
                  {info.label}
                </span>
                <span className="text-[10px] text-gray-400 bg-gray-100/80 rounded-full px-2 py-0.5 min-w-[22px] text-center font-medium">
                  {tasks.length}
                </span>
                <CaretRight
                  weight="bold"
                  className={`w-3 h-3 text-gray-300 transition-transform duration-200 ${isCollapsed ? '' : 'rotate-90'}`}
                />
              </button>

              {/* 任务项 */}
              {!isCollapsed && (
                <div className="ml-3.5 pl-4 border-l border-gray-100">
                  {tasks.map((task) => (
                    <div
                      key={task.id}
                      className="group flex items-center gap-2.5 px-3 py-2 -ml-4 rounded-lg
                                 hover:bg-white/70 cursor-pointer transition-all duration-150
                                 border-l-2 border-transparent hover:border-purple-200/60"
                      onClick={() => setEditingTaskId(task.id)}
                    >
                      <button
                        className="w-4 h-4 rounded-full border-2 border-gray-200 flex-shrink-0
                                   group-hover:border-green-300 hover:bg-green-50 hover:border-green-400
                                   transition-all duration-150"
                        onClick={(e) => { e.stopPropagation(); completeTask(task.id) }}
                        title="完成"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1">
                          <span className="text-[13px] text-gray-600 truncate leading-snug">{task.title}</span>
                          {task.recurrence && (
                            <Repeat weight="bold" className="w-3 h-3 flex-shrink-0 text-purple-400" />
                          )}
                          {task.note && (
                            <NotePencil weight="fill" className="w-3 h-3 flex-shrink-0 opacity-40" />
                          )}
                        </div>
                        {task.dueDate && (() => {
                          const dueStatus = getDueStatus(task.dueDate)
                          const dueConfig = DUE_STATUS_CONFIG[dueStatus]
                          const dateStr = new Date(task.dueDate).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
                          return (
                            <div className="text-[11px] mt-0.5" style={{ color: dueConfig.color || undefined }}>
                              {dueStatus !== 'normal' && dueStatus !== 'none' && (
                                <span className="inline-block text-[9px] px-1 py-px rounded mr-1"
                                      style={{ backgroundColor: dueConfig.bg, color: dueConfig.color }}>
                                  {dueConfig.label}
                                </span>
                              )}
                              {dateStr}
                            </div>
                          )
                        })()}
                      </div>
                      <div className="flex gap-1">
                        {task.tags.slice(0, 2).map((tagId) => (
                          <span
                            key={tagId}
                            className="w-1.5 h-1.5 rounded-full flex-shrink-0 opacity-60 group-hover:opacity-100 transition-opacity"
                            style={{ backgroundColor: tagMap[tagId]?.color || '#ccc' }}
                          />
                        ))}
                      </div>
                    </div>
                  ))}

                  {tasks.length === 0 && (
                    <div className="px-3 py-3 text-[12px] text-center"
                         style={{ color: 'var(--text-muted)' }}>
                      拖拽任务到这里
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}

        {/* ===== 已完成任务区域 ===== */}
        <div className="pt-2 border-t border-gray-100">
          <button
            onClick={loadCompletedTasks}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl
                       hover:bg-white/70 transition-all duration-200 text-left"
          >
            <Check weight="bold" className="w-3.5 h-3.5 text-green-400" />
            <span className="text-xs font-semibold text-gray-500 flex-1">已完成</span>
            <span className="text-[10px] text-gray-400 bg-gray-100/80 rounded-full px-2 py-0.5 min-w-[22px] text-center font-medium">
              {showCompleted ? completedTasks.length : '…'}
            </span>
            <CaretRight
              weight="bold"
              className={`w-3 h-3 text-gray-300 transition-transform duration-200 ${showCompleted ? 'rotate-90' : ''}`}
            />
          </button>

          {showCompleted && completedTasks.map((task) => (
            <div
              key={task.id}
              className="group flex items-center gap-2.5 px-3 py-1.5 ml-3 rounded-lg
                         hover:bg-white/70 transition-all duration-150"
            >
              <div className="w-4 h-4 rounded-full bg-green-100 border-2 border-green-300 flex-shrink-0
                             flex items-center justify-center">
                <Check weight="bold" className="w-2.5 h-2.5 text-green-500" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] text-gray-400 line-through truncate leading-snug">{task.title}</div>
                {task.completedAt && (
                  <div className="text-[10px] text-gray-350 mt-0.5">
                    {new Date(task.completedAt).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })}
                  </div>
                )}
              </div>
              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  className="px-2 py-1 text-[10px] text-gray-400 hover:text-purple-400 hover:bg-purple-50
                             rounded-lg transition-colors font-medium"
                  onClick={(e) => { e.stopPropagation(); handleReopen(task.id) }}
                  title="恢复"
                >
                  恢复
                </button>
                <button
                  className="px-2 py-1 text-[10px] text-gray-400 hover:text-red-400 hover:bg-red-50
                             rounded-lg transition-colors font-medium"
                  onClick={(e) => { e.stopPropagation(); handlePermanentDelete(task.id) }}
                  title="永久删除"
                >
                  删除
                </button>
              </div>
            </div>
          ))}

          {showCompleted && completedTasks.length === 0 && (
            <div className="px-3 py-3 text-[12px] text-center"
                 style={{ color: 'var(--text-muted)' }}>
              暂无已完成任务
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
