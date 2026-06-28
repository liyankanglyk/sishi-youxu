import { useMemo } from 'react'
import { useDraggable } from '@dnd-kit/core'
import { Check, Repeat, NotePencil } from '@phosphor-icons/react'
import { useStore } from '../store/useStore'
import type { Task, ViewDensity } from '../types'
import { getDueStatus, DUE_STATUS_CONFIG } from '../types'

interface TaskCardProps {
  task: Task
}

/** 密度配置：宽 / 字号 / 内边距 / 最小高度 / 显示项 */
const densityStyles: Record<ViewDensity, {
  width: string; fontSize: string; padding: string; minH: string
  showDate: boolean; showTags: boolean; showLevel: boolean; showNote: boolean; showTagNames: boolean
}> = {
  compact: {
    width: 'w-[4.5rem]', fontSize: 'text-[11px]', padding: 'px-2 py-2', minH: 'min-h-[44px]',
    showDate: false, showTags: false, showLevel: false, showNote: false, showTagNames: false,
  },
  standard: {
    width: 'w-[7rem]', fontSize: 'text-xs', padding: 'px-2.5 py-2.5', minH: 'min-h-[68px]',
    showDate: true, showTags: true, showLevel: false, showNote: false, showTagNames: false,
  },
  detailed: {
    width: 'w-[9rem]', fontSize: 'text-[13px]', padding: 'px-3 py-3', minH: 'min-h-[90px]',
    showDate: true, showTags: true, showLevel: true, showNote: true, showTagNames: true,
  },
}

export function TaskCard({ task }: TaskCardProps) {
  const viewDensity = useStore((s) => s.viewDensity)
  const setEditingTaskId = useStore((s) => s.setEditingTaskId)
  const completeTask = useStore((s) => s.completeTask)
  const isSelectMode = useStore((s) => s.isSelectMode)
  const focusToday = useStore((s) => s.focusToday)
  const selectedTaskIds = useStore((s) => s.selectedTaskIds)
  const toggleSelectTask = useStore((s) => s.toggleSelectTask)
  const tags = useStore((s) => s.tags)
  const isSelected = selectedTaskIds.includes(task.id)
  const tagMap = useMemo(() => {
    const m: Record<string, string> = {}
    tags.forEach((t) => { m[t.id] = t.color })
    return m
  }, [tags])

  const ds = densityStyles[viewDensity]
  const dueStatus = getDueStatus(task.dueDate)
  const dueConfig = DUE_STATUS_CONFIG[dueStatus]
  const isUrgent = dueStatus === 'overdue' || dueStatus === 'today' || dueStatus === 'thisWeek'
  const isFaded = focusToday && !isUrgent
  const dueDateStr = task.dueDate
    ? new Date(task.dueDate).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
    : null

  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
    data: { task },
  })

  const style: React.CSSProperties = {
    position: 'absolute',
    left: `${task.posX * 100}%`,
    bottom: `${task.posY * 100}%`,
    // dnd-kit transform 跟随拖拽；无 CSS transition 避免点击时移位
    transform: transform
      ? `translate(-50%, 50%) translate(${transform.x}px, ${transform.y}px)`
      : 'translate(-50%, 50%)',
    zIndex: isDragging ? 50 : 10,
    touchAction: 'none',
  }

  return (
    <div
      ref={setNodeRef}
      data-task-card={task.id}
      className={`
        ${ds.width} ${ds.padding} ${ds.minH} rounded-2xl cursor-grab active:cursor-grabbing
        border border-white/70 select-none group flex flex-col justify-between
        hover:shadow-md transition-shadow duration-200
        ${isDragging ? 'shadow-lg scale-105' : 'shadow-sm'}
        ${dueStatus === 'overdue' && !isDragging ? 'ring-1 ring-red-200/60' : ''}
        ${isSelected ? 'ring-2 ring-purple-400' : ''}
        ${isFaded ? '!opacity-35' : ''}
      `}
      style={{
        ...style,
        opacity: isFaded ? 0.35 : undefined,
        background: isSelected ? 'var(--card-selected-bg)' : 'var(--card-bg)',
        backdropFilter: 'blur(8px)',
        borderLeft: dueConfig.color ? `3px solid ${dueConfig.color}` : '3px solid transparent',
      }}
      {...listeners}
      {...attributes}
      onClick={(e) => {
        e.stopPropagation()
        if (isDragging) return
        if (isSelectMode || e.ctrlKey || e.metaKey) {
          toggleSelectTask(task.id)
          return
        }
        setEditingTaskId(task.id)
      }}
      onContextMenu={(e) => {
        e.preventDefault()
        toggleSelectTask(task.id)
      }}
    >
      {/* 选中标记 + 完成按钮 */}
      {!isDragging && (
        <>
          {(isSelectMode || isSelected) && (
            <div
              className={`absolute -top-2 -left-2 w-5 h-5 rounded-full border-2 flex items-center justify-center shadow-sm transition-all z-10 ${
                isSelected
                  ? 'bg-purple-400 border-purple-400 text-white'
                  : 'bg-white border-gray-300 opacity-0 group-hover:opacity-100'
              }`}
            >
              {isSelected && <Check weight="bold" className="w-2.5 h-2.5" />}
            </div>
          )}
          {!isSelectMode && (
            <button
              className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-white border border-gray-200
                         flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all
                         hover:bg-green-50 hover:border-green-300 hover:scale-110 shadow-sm z-10"
              onClick={(e) => { e.stopPropagation(); completeTask(task.id) }}
              title="完成"
            >
              <Check weight="bold" className="w-2.5 h-2.5 text-green-500" />
            </button>
          )}
        </>
      )}

      {/* 上部：级别 + 标题 */}
      <div className="min-w-0">
        {ds.showLevel && (
          <div className="flex items-center gap-1 mb-1.5">
            <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: `hsl(${task.importanceLevel * 30}, 60%, 70%)` }} />
            <span className="text-[9px] text-gray-400">I{task.importanceLevel}</span>
            <span className="w-1.5 h-1.5 rounded-full ml-0.5 flex-shrink-0" style={{ background: `hsl(${220 - task.urgencyLevel * 30}, 60%, 70%)` }} />
            <span className="text-[9px] text-gray-400">U{task.urgencyLevel}</span>
          </div>
        )}
        <div className={`${ds.fontSize} font-semibold leading-snug flex items-center gap-1`} style={{ color: 'var(--text-primary)' }}>
          <span className="truncate">{task.title || '未命名'}</span>
          {task.recurrence && (
            <Repeat weight="bold" className="w-3 h-3 flex-shrink-0 text-purple-400" />
          )}
        </div>
      </div>

      {/* 下部：日期 + 标签 + 备注 */}
      <div className="min-w-0 mt-1">
        {/* 截止日期 — 始终占位保证高度 */}
        {ds.showDate && (
          <div className="text-[11px] leading-tight h-[16px]">
            {dueDateStr && (
              <span className="font-medium inline-flex items-center gap-1" style={{ color: dueConfig.color || undefined }}>
                {dueStatus !== 'normal' && dueStatus !== 'none' && (
                  <span className="text-[9px] px-1 py-px rounded align-[1px]" style={{ backgroundColor: dueConfig.bg, color: dueConfig.color }}>
                    {dueConfig.label}
                  </span>
                )}
                {dueDateStr}
              </span>
            )}
          </div>
        )}

        {/* 标签 — 标准：色点 / 详细：色点+名称 */}
        {ds.showTags && task.tags.length > 0 && (
          <div className={`flex flex-wrap items-center ${ds.showTagNames ? 'gap-1.5' : 'gap-1'} ${ds.showDate ? 'mt-0.5' : ''}`}>
            {task.tags.slice(0, ds.showTagNames ? 4 : 3).map((tagId) => {
              const tag = tags.find((t) => t.id === tagId)
              return ds.showTagNames && tag ? (
                <span key={tagId} className="flex items-center gap-1 text-[9px] text-gray-500">
                  <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: tag.color }} />
                  <span className="truncate max-w-[3rem]">{tag.name}</span>
                </span>
              ) : (
                <span key={tagId} className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: tagMap[tagId] || '#ccc' }} />
              )
            })}
            {task.tags.length > (ds.showTagNames ? 4 : 3) && (
              <span className="text-[9px] text-gray-400">+{task.tags.length - (ds.showTagNames ? 4 : 3)}</span>
            )}
          </div>
        )}

        {/* 备注摘要（仅详细模式） */}
        {ds.showNote && task.note && (
          <div className="flex items-start gap-1 mt-1.5">
            <NotePencil weight="fill" className="w-2.5 h-2.5 text-gray-350 flex-shrink-0 mt-[1px]" />
            <div className="text-[10px] leading-snug line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
              {task.note.slice(0, 80)}
            </div>
          </div>
        )}
      </div>

      {/* 拖拽时等级角标 */}
      {isDragging && (
        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 bg-white rounded-full px-2 py-0.5 text-[11px] text-gray-500 shadow-md whitespace-nowrap font-medium">
          I{task.importanceLevel} · U{task.urgencyLevel}
        </div>
      )}
    </div>
  )
}
