import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { taskApi, type TaskCreatePayload, type TaskUpdatePayload, type TaskOut } from '@/api/tasks'
import { tagApi, type TagOut } from '@/api/tags'

/* ===== History ===== */
interface HistoryEntry {
  description: string
  undo: () => Promise<void>
  redo: () => Promise<void>
}
const MAX_HISTORY = 50

/* ===== Recurrence helpers ===== */
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

/* ===== Position helpers ===== */
export function getQuadrant(urgencyLevel: number, importanceLevel: number): string {
  // urgencyLevel = posX axis (right = urgent, positive)
  // importanceLevel = posY axis (top = important, positive)
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
  const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0)
  if (dueDay <= endOfMonth) return 'thisMonth'
  return 'normal'
}

export const DUE_STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  overdue:   { color: '#E8615C', bg: '#FEF2F2', label: '已过期' },
  today:     { color: '#EA580C', bg: '#FFF7ED', label: '今天' },
  thisWeek:  { color: '#D97706', bg: '#FFFBEB', label: '本周' },
  thisMonth: { color: '#2563EB', bg: '#EFF6FF', label: '本月' },
  normal:    { color: '', bg: '', label: '' },
  none:      { color: '', bg: '', label: '' },
}

/** Alias for TaskOut used in canvas / list rendering. */
export type TaskEx = TaskOut

export const useTaskStore = defineStore('task', () => {
  const serverTasks = ref<TaskOut[]>([])
  const tags = ref<TagOut[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // UI state
  const searchQuery = ref('')
  const tagFilter = ref<string[]>([])
  const dueFilter = ref<'all' | 'overdue' | 'today' | 'thisWeek' | 'thisMonth'>('all')
  const selectedQuadrant = ref<string | null>(null)
  // Restore density preference; default to compact on mobile
  const viewDensity = ref<'compact' | 'standard' | 'detailed'>(
    (localStorage.getItem('sishi-view-density') as any) ||
    (window.matchMedia?.('(max-width: 767px)').matches ? 'compact' : 'standard'),
  )
  // Keep a separate desktop preference so mobile auto-compact doesn't overwrite it
  const _desktopDensity = ref<'compact' | 'standard' | 'detailed'>(
    (localStorage.getItem('sishi-view-density-desktop') as any) || viewDensity.value,
  )

  // Auto-switch density on viewport change
  if (window.matchMedia) {
    window.matchMedia('(max-width: 767px)').addEventListener('change', (e) => {
      if (e.matches) {
        // Enter mobile: save current pref and force compact
        _desktopDensity.value = viewDensity.value
        localStorage.setItem('sishi-view-density-desktop', _desktopDensity.value)
        viewDensity.value = 'compact'
      } else if (viewDensity.value === 'compact') {
        // Exit mobile: restore desktop preference
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

  // Multi-select
  const selectedTaskIds = ref<string[]>([])
  const isSelectMode = computed(() => selectedTaskIds.value.length > 0)

  // Focus Today mode
  const focusToday = ref(false)

  // Generated next task mapping (taskUuid -> generatedNextUuid) for recurrence cleanup
  const generatedNextMap = ref<Map<string, string>>(new Map())

  // History
  const undoStack = ref<HistoryEntry[]>([])
  const redoStack = ref<HistoryEntry[]>([])

  function pushHistory(entry: HistoryEntry) {
    undoStack.value = [...undoStack.value.slice(-(MAX_HISTORY - 1)), entry]
    redoStack.value = []
  }

  // ── Filtered tasks (search + tag + due + focusToday) ──
  const filteredTasks = computed(() => {
    let result = serverTasks.value

    // Focus Today: only show overdue/today/thisWeek/thisMonth, hide completed
    if (focusToday.value) {
      result = result.filter(t => {
        if (t.completed) return false
        const s = getDueStatus(t.dueDate)
        return s === 'overdue' || s === 'today' || s === 'thisWeek' || s === 'thisMonth'
      })
    }

    // Always exclude completed tasks from quadrant canvas
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

  /** Whether a non-completed task should be dimmed (focusToday on & task not urgent). */
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

  const completedTasks = computed(() => serverTasks.value.filter(t => t.completed))

  // ── Data loading ──
  async function fetchFromServer() {
    loading.value = true
    error.value = null
    try {
      const [taskData, tagData] = await Promise.all([
        taskApi.list(),
        tagApi.list(),
      ])
      serverTasks.value = (taskData.data?.items ?? []) as TaskOut[]
      tags.value = tagData.data?.items ?? []
    } catch (e: any) {
      error.value = e.message || '加载失败'
    } finally { loading.value = false }
  }

  async function fetchTask(uuid: string): Promise<TaskOut | null> {
    try {
      const { data } = await taskApi.get(uuid)
      return data ?? null
    } catch { return null }
  }

  async function createTask(payload: TaskCreatePayload): Promise<TaskOut | null> {
    const { data } = await taskApi.create(payload)
    if (data) {
      serverTasks.value.push(data)
      pushHistory({
        description: `创建「${data.title}」`,
        undo: async () => { serverTasks.value = serverTasks.value.filter(t => t.uuid !== data.uuid); await taskApi.delete(data.uuid) },
        redo: async () => { serverTasks.value.push(data); await taskApi.create(payload) },
      })
    }
    return data ?? null
  }

  async function updateTask(uuid: string, changes: TaskUpdatePayload) {
    const old = serverTasks.value.find(t => t.uuid === uuid)
    if (!old) return
    const merged = { ...old, ...changes }
    const idx = serverTasks.value.indexOf(old)
    if (idx >= 0) serverTasks.value[idx] = merged as any

    try {
      const { data } = await taskApi.update(uuid, changes)
      if (data && idx >= 0) serverTasks.value[idx] = data
    } catch {
      if (idx >= 0) serverTasks.value[idx] = old
      throw new Error('更新失败')
    }

    pushHistory({
      description: `编辑「${old.title}」`,
      undo: async () => {
        const u = serverTasks.value.findIndex(t => t.uuid === uuid)
        if (u >= 0) serverTasks.value[u] = old
        await taskApi.update(uuid, { title: old.title, urgencyLevel: old.urgencyLevel, importanceLevel: old.importanceLevel, dueDate: old.dueDate, note: old.note })
      },
      redo: async () => {
        const u = serverTasks.value.findIndex(t => t.uuid === uuid)
        if (u >= 0) serverTasks.value[u] = merged as any
        await taskApi.update(uuid, changes)
      },
    })
  }

  async function moveTask(uuid: string, urgencyLevel: number, importanceLevel: number) {
    const task = serverTasks.value.find(t => t.uuid === uuid)
    if (!task) return
    if (task.urgencyLevel === urgencyLevel && task.importanceLevel === importanceLevel) return
    const oldUrg = task.urgencyLevel
    const oldImp = task.importanceLevel
    const idx = serverTasks.value.indexOf(task)
    if (idx >= 0) serverTasks.value[idx] = { ...task, urgencyLevel, importanceLevel }

    try { await taskApi.update(uuid, { urgencyLevel, importanceLevel }) }
    catch { if (idx >= 0) { serverTasks.value[idx] = { ...serverTasks.value[idx], urgencyLevel: oldUrg, importanceLevel: oldImp } } }

    pushHistory({
      description: `移动「${task.title}」`,
      undo: async () => {
        const i = serverTasks.value.findIndex(t => t.uuid === uuid)
        if (i >= 0) serverTasks.value[i] = { ...serverTasks.value[i], urgencyLevel: oldUrg, importanceLevel: oldImp }
        await taskApi.update(uuid, { urgencyLevel: oldUrg, importanceLevel: oldImp })
      },
      redo: async () => {
        const i = serverTasks.value.findIndex(t => t.uuid === uuid)
        if (i >= 0) serverTasks.value[i] = { ...serverTasks.value[i], urgencyLevel, importanceLevel }
        await taskApi.update(uuid, { urgencyLevel, importanceLevel })
      },
    })
  }

  async function completeTask(uuid: string) {
    const task = serverTasks.value.find(t => t.uuid === uuid)
    if (!task) return
    const now = new Date().toISOString()
    const wasCompleted = task.completed
    const wasCompletedAt = task.completedAt
    const idx = serverTasks.value.indexOf(task)

    if (idx >= 0) {
      serverTasks.value[idx] = { ...task, completed: !wasCompleted, completedAt: !wasCompleted ? now : null }
    }
    try {
      await taskApi.update(uuid, { completed: !wasCompleted, completedAt: !wasCompleted ? now : null })
    } catch {
      if (idx >= 0) serverTasks.value[idx] = task
      return
    }

    // ── Recurrence: auto-generate next instance on complete / clean up on reopen ──
    let generatedUuid: string | null = null
    if (!wasCompleted && task.recurrence && task.dueDate) {
      // Completing a recurring task → generate next instance
      const nextDue = getNextDueDate(task.dueDate, task.recurrence)
      if (nextDue) {
        try {
          const { data } = await taskApi.create({
            title: task.title,
            urgencyLevel: task.urgencyLevel,
            importanceLevel: task.importanceLevel,
            dueDate: nextDue,
            recurrence: task.recurrence,
            note: task.note,
            tags: task.tags && typeof task.tags[0] !== 'string'
              ? (task.tags as { uuid: string }[]).map(t => t.uuid)
              : undefined,
          })
          if (data) {
            generatedUuid = data.uuid
            if (data.uuid) {
              serverTasks.value.push(data)
              generatedNextMap.value.set(uuid, data.uuid)
            }
          }
        } catch { /* next-instance creation is best-effort */ }
      }
    } else if (wasCompleted) {
      // Reopening a recurring task → clean up generated next instance
      const nextUuid = generatedNextMap.value.get(uuid)
      if (nextUuid) {
        try {
          await taskApi.delete(nextUuid)
        } catch { /* already deleted */ }
        serverTasks.value = serverTasks.value.filter(t => t.uuid !== nextUuid)
        generatedNextMap.value.delete(uuid)
      }
    }

    if (!wasCompleted) {
      celebrationTitle.value = task.title
      setTimeout(() => { celebrationTitle.value = null }, 2000)
    }

    pushHistory({
      description: `${wasCompleted ? '恢复' : '完成'}「${task.title}」${generatedUuid ? '（已生成下一期）' : ''}`,
      undo: async () => {
        const i = serverTasks.value.findIndex(t => t.uuid === uuid)
        if (i >= 0) serverTasks.value[i] = { ...serverTasks.value[i], completed: wasCompleted, completedAt: wasCompletedAt }
        await taskApi.update(uuid, { completed: wasCompleted, completedAt: wasCompletedAt })
        // Clean up generated next instance
        if (generatedUuid) {
          try { await taskApi.delete(generatedUuid) } catch { /* ignore */ }
          serverTasks.value = serverTasks.value.filter(t => t.uuid !== generatedUuid)
          generatedNextMap.value.delete(uuid)
        }
      },
      redo: async () => {
        const i = serverTasks.value.findIndex(t => t.uuid === uuid)
        if (i >= 0) serverTasks.value[i] = { ...serverTasks.value[i], completed: !wasCompleted, completedAt: !wasCompleted ? now : null }
        await taskApi.update(uuid, { completed: !wasCompleted, completedAt: !wasCompleted ? now : null })
        if (generatedUuid) {
          const { data } = await taskApi.create({
            title: task.title, urgencyLevel: task.urgencyLevel, importanceLevel: task.importanceLevel,
            dueDate: getNextDueDate(task.dueDate!, task.recurrence!), recurrence: task.recurrence!,
            note: task.note, tags: task.tags && typeof task.tags[0] !== 'string'
              ? (task.tags as { uuid: string }[]).map(t => t.uuid) : undefined,
          })
          if (data) { serverTasks.value.push(data); generatedNextMap.value.set(uuid, data.uuid) }
        }
      },
    })
  }

  async function deleteTask(uuid: string) {
    const task = serverTasks.value.find(t => t.uuid === uuid)
    if (!task) return
    serverTasks.value = serverTasks.value.filter(t => t.uuid !== uuid)
    try { await taskApi.delete(uuid) } catch { serverTasks.value.push(task) }

    pushHistory({
      description: `删除「${task.title}」`,
      undo: async () => {
        serverTasks.value.push(task)
        await taskApi.create({ title: task.title, urgencyLevel: task.urgencyLevel, importanceLevel: task.importanceLevel, dueDate: task.dueDate, note: task.note })
      },
      redo: async () => {
        serverTasks.value = serverTasks.value.filter(t => t.uuid !== uuid)
        await taskApi.delete(uuid)
      },
    })
  }

  // ── Multi-select ──
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
    for (const uuid of ids) {
      await taskApi.update(uuid, { completed: true, completedAt: now })
    }
    await fetchFromServer()
    pushHistory({
      description: `批量完成 ${ids.length} 个任务`,
      undo: async () => {
        for (const uuid of ids) { await taskApi.update(uuid, { completed: false, completedAt: null }) }
        await fetchFromServer()
      },
      redo: async () => {
        for (const uuid of ids) { await taskApi.update(uuid, { completed: true, completedAt: now }) }
        await fetchFromServer()
      },
    })
    clearSelection()
  }

  async function batchDelete() {
    const ids = [...selectedTaskIds.value]
    const victims = serverTasks.value.filter(t => ids.includes(t.uuid))
    serverTasks.value = serverTasks.value.filter(t => !ids.includes(t.uuid))
    try {
      await taskApi.batch({ idempotencyKey: crypto.randomUUID(), action: 'delete', taskUuids: ids })
    } catch { await fetchFromServer() }
    pushHistory({
      description: `批量删除 ${ids.length} 个任务`,
      undo: async () => {
        for (const t of victims) {
          serverTasks.value.push(t)
          await taskApi.create({ title: t.title, urgencyLevel: t.urgencyLevel, importanceLevel: t.importanceLevel, dueDate: t.dueDate, note: t.note })
        }
      },
      redo: async () => {
        serverTasks.value = serverTasks.value.filter(t => !ids.includes(t.uuid))
        await taskApi.batch({ idempotencyKey: crypto.randomUUID(), action: 'delete', taskUuids: ids })
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

  function exportData() {
    const blob = new Blob([JSON.stringify({ tasks: serverTasks.value, tags: tags.value, exportedAt: new Date().toISOString() })], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `四时有序-备份-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Filters ──
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
    serverTasks, tags, loading, error,
    searchQuery, tagFilter, dueFilter, selectedQuadrant, viewDensity, isListOpen,
    editingTaskUuid, isCreating, createUrgencyLevel, createImportanceLevel,
    celebrationTitle,
    selectedTaskIds, isSelectMode,
    undoStack, redoStack,
    filteredTasks, groupedTasks, completedTasks,
    q1Tasks, q2Tasks, q3Tasks, q4Tasks,
    hasActiveFilters,
    focusToday, isDimmed,
    fetchFromServer, fetchTask, createTask, updateTask, moveTask, completeTask, deleteTask,
    toggleSelectTask, selectAllTasks, clearSelection, batchComplete, batchDelete,
    undo, redo,
    exportData,
    setSearchQuery, setQuadrantFilter, toggleTagFilter, setDueFilter, clearFilters,
    setViewDensity, cycleViewDensity, setListOpen, setEditingUuid, setCreating, setFocusToday,
  }
})