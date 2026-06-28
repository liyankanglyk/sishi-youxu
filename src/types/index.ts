// ===== 重复规则 =====
export type Recurrence = null | 'daily' | 'weekly' | 'monthly'

export const RECURRENCE_OPTIONS: { value: Recurrence; label: string }[] = [
  { value: null, label: '不重复' },
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' },
]

/** 根据重复规则计算下一次截止日期 */
export function getNextDueDate(dueDate: string | null, recurrence: Recurrence): string | null {
  if (!dueDate || !recurrence) return null
  const base = new Date(dueDate)
  const next = new Date(base)
  switch (recurrence) {
    case 'daily':
      next.setDate(base.getDate() + 1)
      break
    case 'weekly':
      next.setDate(base.getDate() + 7)
      break
    case 'monthly':
      next.setMonth(base.getMonth() + 1)
      break
  }
  return next.toISOString().slice(0, 10)
}

// ===== 任务数据模型 =====
export interface Task {
  id: string
  title: string
  posX: number            // 紧急度相对位置 0-1
  posY: number            // 重要度相对位置 0-1
  urgencyLevel: number    // 紧急性等级 -4~4
  importanceLevel: number // 重要性等级 -4~4
  dueDate: string | null  // ISO 日期字符串
  tags: string[]          // 标签 ID 数组
  note: string
  recurrence: Recurrence   // 重复规则
  generatedNextId?: string  // 自动生成的下一期任务 ID（恢复/撤销时用来清理）
  completed: boolean
  completedAt: string | null
  createdAt: string
  updatedAt: string
}

// ===== 标签数据模型 =====
export interface Tag {
  id: string
  name: string
  color: string           // HEX 色值
  isPreset: boolean
}

// ===== 象限常量 =====
export const Quadrant = {
  Q1: 'Q1', // 重要 + 紧急 (右上)
  Q2: 'Q2', // 重要 + 不紧急 (左上)
  Q3: 'Q3', // 不重要 + 紧急 (右下)
  Q4: 'Q4', // 不重要 + 不紧急 (左下)
} as const
export type Quadrant = (typeof Quadrant)[keyof typeof Quadrant]

// ===== 象限信息 =====
export interface QuadrantInfo {
  id: Quadrant
  label: string
  subtitle: string
  color: string
  colorLight: string
  colorDark: string
  bgClass: string
}

// ===== 视图密度 =====
export type ViewDensity = 'compact' | 'standard' | 'detailed'

// ===== 根据坐标计算象限和等级 =====
export function getQuadrant(posX: number, posY: number): Quadrant {
  if (posY >= 0.5) {
    return posX >= 0.5 ? Quadrant.Q1 : Quadrant.Q2
  } else {
    return posX >= 0.5 ? Quadrant.Q3 : Quadrant.Q4
  }
}

export function posToLevel(pos: number): number {
  return Math.round(pos * 8) - 4
}

export function levelToPos(level: number): number {
  // ±4 映射到 0.06~0.94，留边距防止卡片溢出（移动端卡片宽占比大）
  return 0.06 + ((level + 4) / 8) * 0.88
}

// ===== 预设标签 =====
// 只保留场景分类标签，不与象限轴（紧急度/重要度）重复
export const PRESET_TAGS: Omit<Tag, 'id'>[] = [
  { name: '工作', color: '#6366F1', isPreset: true },
  { name: '学习', color: '#059669', isPreset: true },
  { name: '生活', color: '#EA580C', isPreset: true },
  { name: '健康', color: '#E8615C', isPreset: true },
]

// ===== 象限配置 =====
export const QUADRANT_CONFIG: Record<Quadrant, QuadrantInfo> = {
  [Quadrant.Q1]: {
    id: Quadrant.Q1,
    label: '重要 & 紧急',
    subtitle: '立即处理',
    color: '#F2A7B3',
    colorLight: '#FDE8EC',
    colorDark: '#E88593',
    bgClass: 'bg-[#FDE8EC]',
  },
  [Quadrant.Q2]: {
    id: Quadrant.Q2,
    label: '重要 & 不紧急',
    subtitle: '计划安排',
    color: '#B5D9C4',
    colorLight: '#E8F5EC',
    colorDark: '#8EC4A3',
    bgClass: 'bg-[#E8F5EC]',
  },
  [Quadrant.Q3]: {
    id: Quadrant.Q3,
    label: '不重要 & 紧急',
    subtitle: '尽快完成',
    color: '#C5D5E8',
    colorLight: '#EEF3F9',
    colorDark: '#9DB5D2',
    bgClass: 'bg-[#EEF3F9]',
  },
  [Quadrant.Q4]: {
    id: Quadrant.Q4,
    label: '不重要 & 不紧急',
    subtitle: '有空再做',
    color: '#FBE4A0',
    colorLight: '#FEF9EB',
    colorDark: '#F5D56A',
    bgClass: 'bg-[#FEF9EB]',
  },
}

// ===== 截止日期状态 =====
export type DueStatus = 'overdue' | 'today' | 'thisWeek' | 'normal' | 'none'

/** 根据截止日期计算状态 */
export function getDueStatus(dueDate: string | null): DueStatus {
  if (!dueDate) return 'none'
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const due = new Date(dueDate)
  const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate())

  if (dueDay.getTime() < today.getTime()) return 'overdue'
  if (dueDay.getTime() === today.getTime()) return 'today'

  // 本周结束（周六 = 6）
  const endOfWeek = new Date(today)
  const daysUntilSaturday = 6 - today.getDay()
  endOfWeek.setDate(today.getDate() + daysUntilSaturday)

  if (dueDay <= endOfWeek) return 'thisWeek'
  return 'normal'
}

/** 状态对应的颜色和标签 */
export const DUE_STATUS_CONFIG: Record<DueStatus, { color: string; bg: string; label: string }> = {
  overdue:  { color: '#E8615C', bg: '#FEF2F2', label: '已过期' },
  today:    { color: '#EA580C', bg: '#FFF7ED', label: '今天' },
  thisWeek: { color: '#D97706', bg: '#FFFBEB', label: '本周' },
  normal:   { color: '', bg: '', label: '' },
  none:     { color: '', bg: '', label: '' },
}

// ===== 空任务工厂 =====
export function createEmptyTask(partial?: Partial<Task>): Task {
  const now = new Date().toISOString()
  const posX = partial?.posX ?? 0.5
  const posY = partial?.posY ?? 0.5
  return {
    id: '',
    title: '',
    posX,
    posY,
    urgencyLevel: posToLevel(posX),
    importanceLevel: posToLevel(posY),
    dueDate: null,
    tags: [],
    note: '',
    recurrence: null,
    completed: false,
    completedAt: null,
    createdAt: now,
    updatedAt: now,
    ...partial,
  }
}
