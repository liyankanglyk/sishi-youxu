import { useRef, useCallback, type PointerEvent, type TouchEvent } from 'react'
import { DndContext, PointerSensor, TouchSensor, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { useStore } from '../store/useStore'
import { QUADRANT_CONFIG, Quadrant } from '../types'
import { TaskCard } from './TaskCard'

function QuadrantBg({ quadrant }: { quadrant: Quadrant }) {
  const info = QUADRANT_CONFIG[quadrant]
  const gridClass = {
    [Quadrant.Q1]: 'top-0 left-1/2 rounded-br-3xl',
    [Quadrant.Q2]: 'top-0 left-0 rounded-bl-3xl',
    [Quadrant.Q3]: 'top-1/2 left-1/2 rounded-tr-3xl',
    [Quadrant.Q4]: 'top-1/2 left-0 rounded-tl-3xl',
  }[quadrant]

  // 映射象限到 CSS 变量名
  const varKey = { Q1: 'pink', Q2: 'mint', Q3: 'blue', Q4: 'yellow' }[quadrant]

  return (
    <div
      className={`absolute w-1/2 h-1/2 ${gridClass} flex items-center justify-center`}
      style={{
        background: `radial-gradient(ellipse at center, var(--quadrant-${varKey}-light) 30%, transparent 100%)`,
        boxShadow: 'none',
      }}
    >
      <div className="text-center select-none pointer-events-none">
        <div className="text-2xl font-bold tracking-tight" style={{ color: `var(--quadrant-${varKey}-dark)`, opacity: 0.5 }}>{quadrant}</div>
        <div className="text-xs mt-1.5 font-medium" style={{ color: `var(--quadrant-${varKey}-dark)`, opacity: 0.55 }}>{info.label}</div>
        <div className="text-[11px] mt-0.5" style={{ color: `var(--quadrant-${varKey}-dark)`, opacity: 0.4 }}>{info.subtitle}</div>
      </div>
    </div>
  )
}

export function QuadrantCanvas() {
  const canvasRef = useRef<HTMLDivElement>(null)
  const tasks = useStore((s) => s.tasks)
  const isCreating = useStore((s) => s.isCreating)
  const createPosX = useStore((s) => s.createPosX)
  const createPosY = useStore((s) => s.createPosY)
  const setCreating = useStore((s) => s.setCreating)
  const moveTask = useStore((s) => s.moveTask)
  const clearSelection = useStore((s) => s.clearSelection)

  const pointerSensor = useSensor(PointerSensor, {
    activationConstraint: { distance: 5 },
  })
  const touchSensor = useSensor(TouchSensor, {
    activationConstraint: { delay: 150, tolerance: 5 },
  })
  const sensors = useSensors(pointerSensor, touchSensor)

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, delta } = event
      if (!canvasRef.current) return
      const rect = canvasRef.current.getBoundingClientRect()
      const task = tasks.find((t) => t.id === active.id)
      if (!task) return
      const dx = delta.x / rect.width
      const dy = -delta.y / rect.height
      const newX = Math.max(0, Math.min(1, task.posX + dx))
      const newY = Math.max(0, Math.min(1, task.posY + dy))
      moveTask(task.id, newX, newY)
    },
    [tasks, moveTask]
  )

  const handleDoubleClick = useCallback(
    (e: PointerEvent<HTMLDivElement>) => {
      if (!canvasRef.current) return
      // 选择模式下，点击空白区域取消选择
      const { isSelectMode } = useStore.getState()
      if (isSelectMode) {
        clearSelection()
        return
      }
      const rect = canvasRef.current.getBoundingClientRect()
      const posX = (e.clientX - rect.left) / rect.width
      const posY = 1 - (e.clientY - rect.top) / rect.height
      setCreating(true, posX, posY)
    },
    [setCreating, clearSelection]
  )

  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handleTouchStart = useCallback(
    (e: TouchEvent<HTMLDivElement>) => {
      if ((e.target as HTMLElement).closest('[data-task-card]')) return
      longPressTimer.current = setTimeout(() => {
        if (!canvasRef.current) return
        const touch = e.touches[0]
        const rect = canvasRef.current.getBoundingClientRect()
        const posX = (touch.clientX - rect.left) / rect.width
        const posY = 1 - (touch.clientY - rect.top) / rect.height
        setCreating(true, posX, posY)
      }, 500)
    },
    [setCreating]
  )
  const handleTouchEnd = useCallback(() => {
    if (longPressTimer.current) { clearTimeout(longPressTimer.current); longPressTimer.current = null }
  }, [])

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div
        ref={canvasRef}
        className="relative w-full h-full overflow-hidden rounded-2xl m-2"
        onDoubleClick={handleDoubleClick}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onTouchMove={handleTouchEnd}
        style={{ touchAction: 'none' }}
      >
        <QuadrantBg quadrant={Quadrant.Q1} />
        <QuadrantBg quadrant={Quadrant.Q2} />
        <QuadrantBg quadrant={Quadrant.Q3} />
        <QuadrantBg quadrant={Quadrant.Q4} />

        {/* 十字分割线 */}
        <div className="absolute top-0 left-1/2 bottom-0 w-px pointer-events-none"
             style={{ background: 'linear-gradient(to bottom, transparent, rgba(180,160,180,0.25) 20%, rgba(180,160,180,0.25) 80%, transparent)' }} />
        <div className="absolute left-0 right-0 top-1/2 h-px pointer-events-none"
             style={{ background: 'linear-gradient(to right, transparent, rgba(180,160,180,0.25) 20%, rgba(180,160,180,0.25) 80%, transparent)' }} />

        {/* 坐标轴 */}
        <div className="absolute top-1/2 left-1/2 right-3 h-[1.5px] pointer-events-none"
             style={{ background: 'linear-gradient(to right, rgba(140,120,155,0.35), rgba(140,120,155,0.18))' }} />
        <div className="absolute top-1/2 right-3 -translate-y-1/2 pointer-events-none"
             style={{ width: 0, height: 0, borderTop: '5px solid transparent', borderBottom: '5px solid transparent', borderLeft: '7px solid rgba(140,120,155,0.4)' }} />
        <div className="absolute top-1/2 left-3 right-1/2 h-[1.5px] pointer-events-none"
             style={{ background: 'linear-gradient(to left, rgba(140,120,155,0.35), rgba(140,120,155,0.18))' }} />
        <div className="absolute top-1/2 left-3 -translate-y-1/2 pointer-events-none"
             style={{ width: 0, height: 0, borderTop: '5px solid transparent', borderBottom: '5px solid transparent', borderRight: '7px solid rgba(140,120,155,0.4)' }} />
        <div className="absolute top-3 bottom-1/2 left-1/2 w-[1.5px] pointer-events-none"
             style={{ background: 'linear-gradient(to top, rgba(140,120,155,0.35), rgba(140,120,155,0.18))' }} />
        <div className="absolute top-3 left-1/2 -translate-x-1/2 pointer-events-none"
             style={{ width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderBottom: '7px solid rgba(140,120,155,0.4)' }} />
        <div className="absolute top-1/2 bottom-3 left-1/2 w-[1.5px] pointer-events-none"
             style={{ background: 'linear-gradient(to bottom, rgba(140,120,155,0.35), rgba(140,120,155,0.18))' }} />
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 pointer-events-none"
             style={{ width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderTop: '7px solid rgba(140,120,155,0.4)' }} />

        <span className="absolute top-2.5 left-[52%] text-[13px] font-medium pointer-events-none" style={{ color: 'rgba(130,110,145,0.5)' }}>重要</span>
        <span className="absolute bottom-2.5 left-[52%] text-[13px] font-medium pointer-events-none" style={{ color: 'rgba(130,110,145,0.5)' }}>不重要</span>
        <span className="absolute left-2.5 top-[48%] text-[13px] font-medium pointer-events-none" style={{ color: 'rgba(130,110,145,0.5)' }}>不紧急</span>
        <span className="absolute right-2.5 top-[48%] text-[13px] font-medium pointer-events-none" style={{ color: 'rgba(130,110,145,0.5)' }}>紧急</span>

        {tasks.filter((task) => task.id && task.title?.trim()).map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}

        {isCreating && (
          <div
            className="absolute w-3 h-3 rounded-full bg-purple-400/60 animate-pulse pointer-events-none z-20"
            style={{ left: `${createPosX * 100}%`, bottom: `${createPosY * 100}%`, transform: 'translate(-50%, 50%)' }}
          />
        )}
      </div>
    </DndContext>
  )
}
