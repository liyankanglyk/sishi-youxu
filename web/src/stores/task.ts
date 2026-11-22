import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { taskApi, type TaskCreatePayload, type TaskUpdatePayload, type TaskOut, type ChecklistItem } from '@/api/tasks'
import { tagApi, type TagOut } from '@/api/tags'
import * as repo from '@/lib/sync/repository'
import { syncEngine } from '@/lib/sync/engine'
import { generateUuid } from '@/db'

/* ===== 历史记录 ===== */
interface HistoryEntry {
  description: string
  undo: () => Promise<void>
  redo: () => Promise<void>
}
const MAX_HISTORY = 50

/* ===== 重复任务辅助函数 ===== */
export function getNextDueDate(dueDate: string, recurrence: string): string | null {
  if (!dueDate || !recurrence) return null
  const base = new Date(dueDate)
  const next = new Date(base)
  switch (recurrence) {
    case 'daily':
      next.setDate(base.getDate() + 1)
      break
    case 'weekdays': {
      next.setDate(base.getDate() + 1)
      while (next.getDay() === 0 || next.getDay() === 6) next.setDate(next.getDate() + 1)
      break
    }
    case 'weekly':
      next.setDate(base.getDate() + 7)
      break
    case 'biweekly':
      next.setDate(base.getDate() + 14)
      break
    case 'monthly':
      next.setMonth(base.getMonth() + 1)
      break
    default:
      return null
  }
  return next.toISOString().slice(0, 10)
}

/* ===== 坐标辅助函数 ===== */
export function getQuadrant(urgencyLevel: number, importanceLevel: number): string {
  // urgencyLevel = posX 轴（右侧 = 紧急，取正值）
  // importanceLevel = posY 轴（顶部 = 重要，取正值）
  const imp = importanceLevel >= 0 ? 'high' : 'low'
  const urg = urgencyLevel >= 0 ? 'high' : 'low'
  if (imp === 'high' && urg === 'high') return 'Q1'
  if (imp === 'high' && urg === 'low') return 'Q2'
  if (imp === 'low' && urg === 'high') return 'Q3'
  return 'Q4'
}

export function getDueStatus(dueDate: string | null): 'overdue' | 'today' | 'thisWeek' | 'thisMonth' | 'normal' | 'none' {
  if (!dueDate) return 'none'
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const due = new Date(dueDate)
  const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate())
  if (dueDay.getTime() < today.getTime()) return 'overdue'
  if (dueDay.getTime() === today.getTime()) return 'today'
  const endOfWeek = new Date(today)
  endOfWeek.setDate(today.getDate() + (6 - today.getDay()))
  if (dueDay <= endOfWeek) return 'thisWeek'
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  if (dueDay <= endOfMonth) return 'thisMonth'
  return 'normal'
}

export const DUE_STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  overdue:   { color: 'var(--c-danger)', bg: 'var(--danger-soft)', label: '已过期' },
  today:     { color: 'var(--c-today)', bg: 'var(--today-soft)', label: '今天' },
  thisWeek:  { color: 'var(--c-week)', bg: 'var(--week-soft)', label: '本周' },
  thisMonth: { color: 'var(--c-brand-500)', bg: 'var(--month-soft)', label: '本月' },
  normal:    { color: '', bg: '', label: '' },
  none:      { color: '', bg: '', label: '' },
}

/** TaskOut 的别名，用于象限画布 / 列表渲染。 */
export type TaskEx = TaskOut

export const useTaskStore = defineStore('task', () => {
  /** UI 视图模型：数据来自本地 Dexie（Dexie 是唯一数据源） */
  const tasks = ref<TaskOut[]>([])
  const tags = ref<TagOut[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // UI 状态
  const searchQuery = ref('')
  const tagFilter = ref<string[]>([])
  const dueFilter = ref<'all' | 'overdue' | 'today' | 'thisWeek' | 'thisMonth'>('all')
  const selectedQuadrant = ref<string | null>(null)
  // 移动端一律 compact：原来只在视口 change 事件里降级，手机首屏会沿用桌面上存的详细档，卡片叠成一团
  const isMobileViewport = window.matchMedia?.('(max-width: 767px)').matches ?? false
  const desktopDensityPref =
    (localStorage.getItem('sishi-view-density-desktop') as 'compact' | 'standard' | 'detailed' | null) ||
    (localStorage.getItem('sishi-view-density') as 'compact' | 'standard' | 'detailed' | null) ||
    'standard'
  const viewDensity = ref<'compact' | 'standard' | 'detailed'>(
    isMobileViewport ? 'compact' : desktopDensityPref,
  )
  // 单独保存桌面端偏好，避免移动端自动 compact 时覆盖
  const _desktopDensity = ref<'compact' | 'standard' | 'detailed'>(desktopDensityPref)

  // 视口变化时自动切换密度
  if (window.matchMedia) {
    window.matchMedia('(max-width: 767px)').addEventListener('change', (e) => {
      if (e.matches) {
        // 进入移动端：保存当前偏好并强制 compact
        _desktopDensity.value = viewDensity.value
        localStorage.setItem('sishi-view-density-desktop', _desktopDensity.value)
        viewDensity.value = 'compact'
      } else if (viewDensity.value === 'compact') {
        // 离开移动端：恢复桌面端偏好
        viewDensity.value = _desktopDensity.value
      }
    })
  }
  const isListOpen = ref(false)
  const editingTaskUuid = ref<string | null>(null)
  const isCreating = ref(false)
  const createUrgencyLevel = ref(0)
  const createImportanceLevel = ref(0)
  const celebrationTitle = ref<string | null>(null)
  const celebrationOrigin = ref<{ x: number; y: number } | null>(null)

  /** 今日已完成任务数 */
  const todayCompletedCount = computed(() => {
    const today = new Date().toISOString().slice(0, 10)
    return tasks.value.filter(t => t.completed && t.completedAt?.startsWith(today)).length
  })

  /** 完成强度等级 1-5，基于今日完成数逐级升级 */
  const completionIntensity = computed(() => {
    const n = todayCompletedCount.value
    if (n >= 25) return 5
    if (n >= 10) return 4
    if (n >= 5) return 3
    if (n >= 3) return 2
    return 1
  })

  /** 最近完成任务的象限（用于粒子色板选择） */
  const lastCompletedQuadrant = ref<string | null>(null)

  // 多选
  const selectedTaskIds = ref<string[]>([])
  const isSelectMode = computed(() => selectedTaskIds.value.length > 0)

  // 今日焦点模式
  const focusToday = ref(false)

  // 已生成的下一个任务的映射（taskUuid -> generatedNextUuid），用于重复任务清理
  const generatedNextMap = ref<Map<string, string>>(new Map())

  // 历史记录
  const undoStack = ref<HistoryEntry[]>([])
  const redoStack = ref<HistoryEntry[]>([])

  function pushHistory(entry: HistoryEntry) {
    undoStack.value = [...undoStack.value.slice(-(MAX_HISTORY - 1)), entry]
    redoStack.value = []
  }

  // ── 过滤后的任务（搜索 + 标签 + 截止日期 + focusToday） ──
  const filteredTasks = computed(() => {
    let result = tasks.value

    // 今日焦点：仅展示已过期/今天/本周/本月，并隐藏已完成
    if (focusToday.value) {
      result = result.filter(t => {
        if (t.completed) return false
        const s = getDueStatus(t.dueDate)
        return s === 'overdue' || s === 'today' || s === 'thisWeek' || s === 'thisMonth'
      })
    }

    // 在象限画布上始终排除已完成任务
    result = result.filter(t => !t.completed)

    if (selectedQuadrant.value) {
      result = result.filter(t => getQuadrant(t.urgencyLevel, t.importanceLevel) === selectedQuadrant.value)
    }

    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      result = result.filter(t => t.title.toLowerCase().includes(q) || (t.note || '').toLowerCase().includes(q))
    }
    if (tagFilter.value.length > 0) {
      const tagIds = new Set(tagFilter.value)
      result = result.filter(t => {
        const tt = t.tags
        if (!tt || !tt.length) return false
        if (typeof tt[0] === 'string') return (tt as string[]).some(id => tagIds.has(id))
        return (tt as { uuid: string }[]).some(tag => tagIds.has(tag.uuid))
      })
    }
    if (dueFilter.value !== 'all') {
      result = result.filter(t => {
        const s = getDueStatus(t.dueDate)
        if (dueFilter.value === 'overdue') return s === 'overdue'
        if (dueFilter.value === 'today') return s === 'today'
        if (dueFilter.value === 'thisWeek') return s === 'today' || s === 'thisWeek'
        if (dueFilter.value === 'thisMonth') return s === 'today' || s === 'thisWeek' || s === 'thisMonth'
        return true
      })
    }
    return result
  })

  /** 当未完成任务是否应当被置灰（focusToday 开启且任务不在紧迫范围）。 */
  const isDimmed = (task: TaskOut): boolean => {
    if (!focusToday.value) return false
    if (task.completed) return false
    const s = getDueStatus(task.dueDate)
    return s !== 'overdue' && s !== 'today' && s !== 'thisWeek' && s !== 'thisMonth'
  }

  const groupedTasks = computed(() => {
    const groups: Record<string, TaskEx[]> = { Q1: [], Q2: [], Q3: [], Q4: [] }
    for (const t of filteredTasks.value) {
      const q = getQuadrant(t.urgencyLevel, t.importanceLevel)
      if (selectedQuadrant.value && q !== selectedQuadrant.value) continue
      groups[q].push(t)
    }
    return groups
  })

  const q1Tasks = computed(() => filteredTasks.value.filter(t => t.importanceLevel >= 0 && t.urgencyLevel >= 0))
  const q2Tasks = computed(() => filteredTasks.value.filter(t => t.importanceLevel >= 0 && t.urgencyLevel < 0))
  const q3Tasks = computed(() => filteredTasks.value.filter(t => t.importanceLevel < 0 && t.urgencyLevel >= 0))
  const q4Tasks = computed(() => filteredTasks.value.filter(t => t.importanceLevel < 0 && t.urgencyLevel < 0))

  const completedTasks = computed(() => tasks.value.filter(t => t.completed))

  // ===========================================================================
  // 本地数据层（Dexie 是唯一数据源）
  // ===========================================================================

  /** 本地记录 → UI 模型。tags 用 uuid 数组，组件再按 uuid 去 store.tags 里取名称与颜色。 */
  function toTaskOut(
    local: {
      uuid: string
      title: string
      urgencyLevel: number
      importanceLevel: number
      dueDate: string | null
      recurrence: string | null
      note: string | null
      completed: boolean
      completedAt: string | null
      sortOrder: number
      createdAt: string
      updatedAt: string
    },
    tagUuids: string[],
    checklist: { total: number; done: number; items: ChecklistItem[] },
  ): TaskOut {
    return {
      uuid: local.uuid,
      title: local.title,
      urgencyLevel: local.urgencyLevel,
      importanceLevel: local.importanceLevel,
      dueDate: local.dueDate,
      recurrence: local.recurrence,
      note: local.note,
      tags: tagUuids,
      checklistTotal: checklist.total,
      checklistCompleted: checklist.done,
      checklistItems: checklist.items,
      completed: local.completed,
      completedAt: local.completedAt,
      sortOrder: local.sortOrder,
      createdAt: local.createdAt,
      updatedAt: local.updatedAt,
    } as TaskOut
  }

  /** 从 Dexie 重读全部数据并刷新视图模型。 */
  async function refreshFromLocal(): Promise<void> {
    const [localTasks, localTags, links, items] = await Promise.all([
      repo.getAllTasks(),
      repo.getAllTags(),
      repo.getAllTaskTags(),
      repo.getAllChecklistItems(),
    ])

    const tagMap = new Map<string, string[]>()
    for (const link of links) {
      const arr = tagMap.get(link.taskUuid) ?? []
      arr.push(link.tagUuid)
      tagMap.set(link.taskUuid, arr)
    }

    const clMap = new Map<string, { total: number; done: number; items: ChecklistItem[] }>()
    for (const item of items) {
      if (item.deletedAt) continue
      const cur = clMap.get(item.taskUuid) ?? { total: 0, done: 0, items: [] }
      cur.total += 1
      if (item.completed) cur.done += 1
      cur.items.push({
        uuid: item.uuid,
        title: item.title,
        completed: item.completed,
        sortOrder: item.sortOrder,
        createdAt: item.createdAt,
        updatedAt: item.updatedAt,
      })
      clMap.set(item.taskUuid, cur)
    }

    tasks.value = localTasks.map(t =>
      toTaskOut(t, tagMap.get(t.uuid) ?? [], clMap.get(t.uuid) ?? { total: 0, done: 0, items: [] }),
    )
    tags.value = localTags
      .filter(t => !t.deletedAt)
      .map(t => ({
        uuid: t.uuid,
        name: t.name,
        color: t.color,
        isPreset: t.isPreset,
        createdAt: t.createdAt,
        updatedAt: t.updatedAt,
      }))
  }

  /** 同步引擎完成一次 push/pull 后重读本地（只注册一次，避免重复刷新）。 */
  let syncBound = false
  function bindSyncEngine() {
    if (syncBound) return
    syncBound = true
    syncEngine.onDataChanged(() => {
      void refreshFromLocal()
    })
  }

  // ===========================================================================
  // 写路径：本地优先（写 Dexie → 入队 → 触发同步）
  // ===========================================================================

  /** 组装给服务端的 op payload（字段与后端 create/update 接受的 camelCase 一致）。 */
  function opPayload(local: {
    uuid: string
    title: string
    urgencyLevel: number
    importanceLevel: number
    dueDate: string | null
    recurrence: string | null
    note: string | null
    completed: boolean
    completedAt: string | null
    sortOrder: number
    remindAt: string | null
    remindOffsetMinutes: number | null
    updatedAt: string
  }, tagUuids?: string[]): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      uuid: local.uuid,
      title: local.title,
      urgencyLevel: local.urgencyLevel,
      importanceLevel: local.importanceLevel,
      dueDate: local.dueDate,
      recurrence: local.recurrence,
      note: local.note,
      completed: local.completed,
      completedAt: local.completedAt,
      sortOrder: local.sortOrder,
      remindAt: local.remindAt,
      remindOffsetMinutes: local.remindOffsetMinutes,
      updatedAt: local.updatedAt,
    }
    if (tagUuids) payload.tags = tagUuids
    return payload
  }

  /** 更新本地任务-标签关联集合（与 task op 一起同步，服务端按 tags 字段整体覆盖）。 */
  async function setTaskTags(taskUuid: string, tagUuids: string[]): Promise<void> {
    const existing = (await repo.getAllTaskTags()).filter(l => l.taskUuid === taskUuid)
    const target = new Set(tagUuids)
    for (const link of existing) {
      if (!target.has(link.tagUuid)) await repo.deleteTaskTag(link.taskUuid, link.tagUuid)
    }
    for (const tagUuid of tagUuids) await repo.putTaskTag(taskUuid, tagUuid)
  }

  async function currentTagUuids(taskUuid: string): Promise<string[]> {
    return (await repo.getAllTaskTags()).filter(l => l.taskUuid === taskUuid).map(l => l.tagUuid)
  }

  /**
   * 唯一的任务写入口：写本地 → 入队 → 触发同步 → 刷新视图。
   * opType：upsert（新增/修改）、delete（软删）、restore（撤销删除）。
   */
  async function writeTask(
    uuid: string,
    patch: Partial<{
      title: string
      urgencyLevel: number
      importanceLevel: number
      dueDate: string | null
      recurrence: string | null
      note: string | null
      completed: boolean
      completedAt: string | null
      sortOrder: number
      remindAt: string | null
      remindOffsetMinutes: number | null
    }>,
    opType: 'upsert' | 'delete' | 'restore' = 'upsert',
  ): Promise<void> {
    const current = await repo.getTask(uuid)
    if (!current) return

    if (opType === 'delete') {
      await repo.softDeleteTask(uuid)
      await repo.enqueueOp('task', 'delete', uuid, { uuid })
    } else if (opType === 'restore') {
      await repo.restoreTask(uuid)
      await repo.enqueueOp('task', 'restore', uuid, { uuid })
    } else {
      const merged = await repo.putTask({ ...current, ...patch, uuid })
      const tagUuids = await currentTagUuids(uuid)
      await repo.enqueueOp('task', 'upsert', uuid, opPayload(merged, tagUuids))
    }
    syncEngine.schedule()
    await refreshFromLocal()
  }

  // ===========================================================================
  // 数据加载
  // ===========================================================================

  /** 后端 pageSize 上限为 100，逐页取完，避免任务数超过一页时被静默截断。 */
  const FETCH_PAGE_SIZE = 100
  const FETCH_MAX_PAGES = 50

  async function fetchAllTasks(): Promise<TaskOut[]> {
    const acc: TaskOut[] = []
    for (let page = 1; page <= FETCH_MAX_PAGES; page++) {
      const { data } = await taskApi.list({ page, pageSize: FETCH_PAGE_SIZE })
      acc.push(...(data?.items ?? []))
      if (!data?.meta?.hasMore) break
    }
    return acc
  }

  /** 把服务端返回的记录写进本地（标记为已同步，作为离线缓存）。 */
  async function hydrateFromServer(list: TaskOut[], tagList: TagOut[]): Promise<void> {
    for (const tag of tagList) {
      await repo.overwriteTagFromServer(tag as unknown as Record<string, unknown>)
    }
    for (const t of list) {
      await repo.overwriteFromServer(t as unknown as Record<string, unknown>)
      const tagUuids = Array.isArray(t.tags)
        ? (t.tags as unknown[]).map((tag) =>
            typeof tag === 'string' ? tag : (tag as { uuid: string }).uuid,
          )
        : []
      await setTaskTags(t.uuid, tagUuids)
    }
  }

  /**
   * 首屏加载：先读本地（离线也能立刻出画面），再联网拉全量覆盖本地。
   * 之后的增量变更交给同步引擎。
   */
  async function bootstrap(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await refreshFromLocal()
      if (!navigator.onLine) return
      const [list, tagData] = await Promise.all([fetchAllTasks(), tagApi.list()])
      await hydrateFromServer(list, tagData.data?.items ?? [])
      await refreshFromLocal()
    } catch (e: any) {
      error.value = e.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  /** 兼容旧调用点：现在等价于 bootstrap。 */
  async function fetchFromServer() {
    await bootstrap()
  }

  async function fetchTask(uuid: string): Promise<TaskOut | null> {
    await refreshFromLocal()
    return tasks.value.find(t => t.uuid === uuid) ?? null
  }

  // ===========================================================================
  // 任务操作（全部本地优先）
  // ===========================================================================

  async function createTask(payload: TaskCreatePayload): Promise<TaskOut | null> {
    const uuid = generateUuid()
    const local = await repo.putTask({
      uuid,
      title: payload.title ?? '',
      urgencyLevel: payload.urgencyLevel ?? 0,
      importanceLevel: payload.importanceLevel ?? 0,
      dueDate: payload.dueDate ?? null,
      recurrence: payload.recurrence ?? null,
      note: payload.note ?? null,
      completed: false,
      completedAt: null,
      sortOrder: payload.sortOrder ?? 0,
    })
    const tagUuids = payload.tags ?? []
    if (tagUuids.length) await setTaskTags(uuid, tagUuids)
    await repo.enqueueOp('task', 'upsert', uuid, opPayload(local, tagUuids))
    syncEngine.schedule()
    await refreshFromLocal()

    pushHistory({
      description: `创建「${local.title}」`,
      undo: async () => {
        await repo.softDeleteTask(uuid)
        await repo.enqueueOp('task', 'delete', uuid, { uuid })
        syncEngine.schedule()
        await refreshFromLocal()
      },
      redo: async () => {
        await repo.restoreTask(uuid)
        await repo.enqueueOp('task', 'restore', uuid, { uuid })
        syncEngine.schedule()
        await refreshFromLocal()
      },
    })

    return tasks.value.find(t => t.uuid === uuid) ?? null
  }

  async function updateTask(uuid: string, changes: TaskUpdatePayload) {
    const before = await repo.getTask(uuid)
    if (!before) return
    const tagUuids = changes.tags ? changes.tags : await currentTagUuids(uuid)
    if (changes.tags) await setTaskTags(uuid, changes.tags)

    await writeTask(uuid, {
      title: changes.title,
      urgencyLevel: changes.urgencyLevel,
      importanceLevel: changes.importanceLevel,
      dueDate: changes.dueDate,
      recurrence: changes.recurrence,
      note: changes.note,
      completed: changes.completed,
      completedAt: changes.completedAt,
      sortOrder: changes.sortOrder,
    })
    // tags 也要跟着 op 一起发（服务端按 tags 覆盖关联）
    if (changes.tags) {
      const merged = await repo.getTask(uuid)
      if (merged) {
        await repo.enqueueOp('task', 'upsert', uuid, opPayload(merged, tagUuids))
        syncEngine.schedule()
      }
    }

    pushHistory({
      description: `编辑「${before.title}」`,
      undo: async () => {
        await writeTask(uuid, {
          title: before.title,
          urgencyLevel: before.urgencyLevel,
          importanceLevel: before.importanceLevel,
          dueDate: before.dueDate,
          recurrence: before.recurrence,
          note: before.note,
          completed: before.completed,
          completedAt: before.completedAt,
          sortOrder: before.sortOrder,
        })
      },
      redo: async () => {
        await writeTask(uuid, changes)
      },
    })
  }

  async function moveTask(uuid: string, urgencyLevel: number, importanceLevel: number) {
    const before = await repo.getTask(uuid)
    if (!before) return
    if (before.urgencyLevel === urgencyLevel && before.importanceLevel === importanceLevel) return

    await writeTask(uuid, { urgencyLevel, importanceLevel })

    pushHistory({
      description: `移动「${before.title}」`,
      undo: async () => {
        await writeTask(uuid, { urgencyLevel: before.urgencyLevel, importanceLevel: before.importanceLevel })
      },
      redo: async () => {
        await writeTask(uuid, { urgencyLevel, importanceLevel })
      },
    })
  }

  async function completeTask(uuid: string) {
    const task = await repo.getTask(uuid)
    if (!task) return
    const wasCompleted = task.completed
    const wasCompletedAt = task.completedAt
    const now = new Date().toISOString()

    await writeTask(uuid, {
      completed: !wasCompleted,
      completedAt: !wasCompleted ? now : null,
    })

    // ── 重复任务：完成时自动生成下一个实例；取消完成时清理 ──
    let generatedUuid: string | null = null
    if (!wasCompleted && task.recurrence && task.dueDate) {
      const nextDue = getNextDueDate(task.dueDate, task.recurrence)
      if (nextDue) {
        const next = await repo.putTask({
          uuid: generateUuid(),
          title: task.title,
          urgencyLevel: task.urgencyLevel,
          importanceLevel: task.importanceLevel,
          dueDate: nextDue,
          recurrence: task.recurrence,
          note: task.note,
          completed: false,
          completedAt: null,
          sortOrder: task.sortOrder,
        })
        const tagUuids = await currentTagUuids(uuid)
        if (tagUuids.length) await setTaskTags(next.uuid, tagUuids)
        await repo.enqueueOp('task', 'upsert', next.uuid, opPayload(next, tagUuids))
        generatedUuid = next.uuid
        generatedNextMap.value.set(uuid, next.uuid)
      }
    } else if (wasCompleted) {
      const nextUuid = generatedNextMap.value.get(uuid)
      if (nextUuid) {
        await repo.softDeleteTask(nextUuid)
        await repo.enqueueOp('task', 'delete', nextUuid, { uuid: nextUuid })
        generatedNextMap.value.delete(uuid)
      }
    }
    syncEngine.schedule()
    await refreshFromLocal()

    if (!wasCompleted) {
      celebrationTitle.value = task.title
      lastCompletedQuadrant.value = getQuadrant(task.urgencyLevel, task.importanceLevel)
      setTimeout(() => { celebrationTitle.value = null }, 2200)
    }

    pushHistory({
      description: `${wasCompleted ? '恢复' : '完成'}「${task.title}」${generatedUuid ? '（已生成下一期）' : ''}`,
      undo: async () => {
        await writeTask(uuid, { completed: wasCompleted, completedAt: wasCompletedAt })
        if (generatedUuid) {
          await repo.softDeleteTask(generatedUuid)
          await repo.enqueueOp('task', 'delete', generatedUuid, { uuid: generatedUuid })
          generatedNextMap.value.delete(uuid)
        }
        syncEngine.schedule()
        await refreshFromLocal()
      },
      redo: async () => {
        await writeTask(uuid, { completed: !wasCompleted, completedAt: !wasCompleted ? now : null })
        syncEngine.schedule()
        await refreshFromLocal()
      },
    })
  }

  async function deleteTask(uuid: string) {
    const task = await repo.getTask(uuid)
    if (!task) return

    await writeTask(uuid, {}, 'delete')

    pushHistory({
      description: `删除「${task.title}」`,
      undo: async () => {
        await repo.restoreTask(uuid)
        await repo.enqueueOp('task', 'restore', uuid, { uuid })
        syncEngine.schedule()
        await refreshFromLocal()
      },
      redo: async () => {
        await repo.softDeleteTask(uuid)
        await repo.enqueueOp('task', 'delete', uuid, { uuid })
        syncEngine.schedule()
        await refreshFromLocal()
      },
    })
  }

  // ── 多选 ──
  function toggleSelectTask(uuid: string) {
    const i = selectedTaskIds.value.indexOf(uuid)
    if (i >= 0) selectedTaskIds.value.splice(i, 1)
    else selectedTaskIds.value.push(uuid)
  }
  function selectAllTasks() {
    selectedTaskIds.value = filteredTasks.value.map(t => t.uuid)
  }
  function clearSelection() { selectedTaskIds.value = [] }

  async function batchComplete() {
    const ids = [...selectedTaskIds.value]
    const now = new Date().toISOString()
    const before = new Map<string, { completed: boolean; completedAt: string | null }>()
    for (const uuid of ids) {
      const t = await repo.getTask(uuid)
      if (t) before.set(uuid, { completed: t.completed, completedAt: t.completedAt })
      await writeTask(uuid, { completed: true, completedAt: now })
    }
    pushHistory({
      description: `批量完成 ${ids.length} 个任务`,
      undo: async () => {
        for (const uuid of ids) {
          const prev = before.get(uuid)
          await writeTask(uuid, { completed: prev?.completed ?? false, completedAt: prev?.completedAt ?? null })
        }
      },
      redo: async () => {
        for (const uuid of ids) await writeTask(uuid, { completed: true, completedAt: now })
      },
    })
    clearSelection()
  }

  async function batchDelete() {
    const ids = [...selectedTaskIds.value]
    for (const uuid of ids) await writeTask(uuid, {}, 'delete')
    pushHistory({
      description: `批量删除 ${ids.length} 个任务`,
      undo: async () => {
        for (const uuid of ids) {
          await repo.restoreTask(uuid)
          await repo.enqueueOp('task', 'restore', uuid, { uuid })
        }
        syncEngine.schedule()
        await refreshFromLocal()
      },
      redo: async () => {
        for (const uuid of ids) await writeTask(uuid, {}, 'delete')
      },
    })
    clearSelection()
  }

  async function undo() {
    if (!undoStack.value.length) return
    const entry = undoStack.value[undoStack.value.length - 1]
    await entry.undo()
    undoStack.value.pop()
    redoStack.value.push(entry)
  }
  async function redo() {
    if (!redoStack.value.length) return
    const entry = redoStack.value[redoStack.value.length - 1]
    await entry.redo()
    redoStack.value.pop()
    undoStack.value.push(entry)
  }

  // ── 标签（本地优先）──
  async function createTag(name: string, color: string): Promise<TagOut | null> {
    const local = await repo.putTag({ uuid: generateUuid(), name, color, isPreset: false })
    await repo.enqueueOp('tag', 'upsert', local.uuid, {
      uuid: local.uuid,
      name: local.name,
      color: local.color,
    })
    syncEngine.schedule()
    await refreshFromLocal()
    return tags.value.find(t => t.uuid === local.uuid) ?? null
  }

  async function updateTag(uuid: string, changes: { name?: string; color?: string }) {
    const before = await repo.getTag(uuid)
    if (!before) return
    const merged = await repo.putTag({ ...before, ...changes, uuid })
    await repo.enqueueOp('tag', 'upsert', uuid, {
      uuid: merged.uuid,
      name: merged.name,
      color: merged.color,
    })
    syncEngine.schedule()
    await refreshFromLocal()
  }

  async function deleteTag(uuid: string) {
    await repo.softDeleteTag(uuid)
    await repo.enqueueOp('tag', 'delete', uuid, { uuid })
    syncEngine.schedule()
    await refreshFromLocal()
  }

  // ── 检查项（本地优先）──
  async function addChecklistItem(taskUuid: string, title: string): Promise<void> {
    const local = await repo.putChecklistItem({
      uuid: generateUuid(),
      taskUuid,
      title,
      completed: false,
      sortOrder: 0,
    })
    await repo.enqueueOp('checklistItems', 'upsert', local.uuid, {
      uuid: local.uuid,
      taskUuid: local.taskUuid,
      title: local.title,
      completed: local.completed,
      sortOrder: local.sortOrder,
    })
    syncEngine.schedule()
    await refreshFromLocal()
  }

  async function updateChecklistItem(itemUuid: string, changes: { title?: string; completed?: boolean }): Promise<void> {
    const before = await repo.getChecklistItem(itemUuid)
    if (!before) return
    const merged = await repo.putChecklistItem({ ...before, ...changes, uuid: itemUuid })
    await repo.enqueueOp('checklistItems', 'upsert', itemUuid, {
      uuid: merged.uuid,
      taskUuid: merged.taskUuid,
      title: merged.title,
      completed: merged.completed,
      sortOrder: merged.sortOrder,
    })
    syncEngine.schedule()
    await refreshFromLocal()
  }

  async function deleteChecklistItem(itemUuid: string): Promise<void> {
    await repo.softDeleteChecklistItem(itemUuid)
    await repo.enqueueOp('checklistItems', 'delete', itemUuid, { uuid: itemUuid })
    syncEngine.schedule()
    await refreshFromLocal()
  }

  function exportData() {
    const blob = new Blob([JSON.stringify({ tasks: tasks.value, tags: tags.value, exportedAt: new Date().toISOString() })], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `四时有序-备份-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── 过滤器 ──
  function setSearchQuery(q: string) { searchQuery.value = q }
  function setQuadrantFilter(q: string | null) { selectedQuadrant.value = q }
  function toggleTagFilter(tagId: string) {
    const i = tagFilter.value.indexOf(tagId)
    if (i >= 0) tagFilter.value.splice(i, 1)
    else tagFilter.value.push(tagId)
  }
  function setDueFilter(f: 'all' | 'overdue' | 'today' | 'thisWeek' | 'thisMonth') { dueFilter.value = f }
  function clearFilters() {
    searchQuery.value = ''
    selectedQuadrant.value = null
    tagFilter.value = []
    dueFilter.value = 'all'
  }

  function setViewDensity(d: 'compact' | 'standard' | 'detailed') { viewDensity.value = d; localStorage.setItem('sishi-view-density', d) }
  function cycleViewDensity() {
    const order: Array<'compact' | 'standard' | 'detailed'> = ['compact', 'standard', 'detailed']
    const idx = order.indexOf(viewDensity.value)
    setViewDensity(order[(idx + 1) % 3])
  }
  function setListOpen(o: boolean) { isListOpen.value = o }
  function setEditingUuid(uuid: string | null) { editingTaskUuid.value = uuid }
  function setCreating(c: boolean, u = 0, i = 0) {
    isCreating.value = c
    createUrgencyLevel.value = u
    createImportanceLevel.value = i
  }
  function setFocusToday(v: boolean) { focusToday.value = v }

  const hasActiveFilters = computed(() => !!searchQuery.value || !!selectedQuadrant.value || tagFilter.value.length > 0 || dueFilter.value !== 'all' || focusToday.value)

  return {
    tasks, tags, loading, error,
    searchQuery, tagFilter, dueFilter, selectedQuadrant, viewDensity, isListOpen,
    editingTaskUuid, isCreating, createUrgencyLevel, createImportanceLevel,
    celebrationTitle, celebrationOrigin, todayCompletedCount, completionIntensity, lastCompletedQuadrant,
    selectedTaskIds, isSelectMode,
    undoStack, redoStack,
    filteredTasks, groupedTasks, completedTasks,
    q1Tasks, q2Tasks, q3Tasks, q4Tasks,
    hasActiveFilters,
    focusToday, isDimmed,
    bootstrap, fetchFromServer, refreshFromLocal, bindSyncEngine, fetchTask,
    createTask, updateTask, moveTask, completeTask, deleteTask,
    createTag, updateTag, deleteTag,
    addChecklistItem, updateChecklistItem, deleteChecklistItem,
    toggleSelectTask, selectAllTasks, clearSelection, batchComplete, batchDelete,
    undo, redo,
    exportData,
    setSearchQuery, setQuadrantFilter, toggleTagFilter, setDueFilter, clearFilters,
    setViewDensity, cycleViewDensity, setListOpen, setEditingUuid, setCreating, setFocusToday,
  }
})
