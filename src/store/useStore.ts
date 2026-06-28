import { create } from 'zustand'
import { useMemo } from 'react'
import type { Task, Tag, ViewDensity } from '../types'
import { posToLevel, levelToPos, getNextDueDate, getQuadrant } from '../types'
import { v4 as uuid } from 'uuid'
import type { User } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'
import { pullFromCloud, subscribeToChanges, unsubscribeChanges, uploadTask, uploadTasks, uploadTag, deleteTaskRemote, deleteTasksRemote, deleteTagRemote, setSyncUserId } from '../lib/sync'
import { taskDB, tagDB, createPresetTagsInCloud } from '../db'

// ===== 历史记录 =====
interface HistoryEntry {
  description: string
  undo: () => Promise<void>
  redo: () => Promise<void>
}

/** 最大历史记录数 */
const MAX_HISTORY = 50

// ===== Store 状态定义 =====
interface AppState {
  // 数据
  tasks: Task[]
  tags: Tag[]
  loading: boolean

  // 认证
  user: User | null
  authLoading: boolean
  signUp: (email: string, password: string) => Promise<void>
  signInWithPassword: (email: string, password: string) => Promise<void>
  signInWithEmail: (email: string) => Promise<void>
  signOut: () => Promise<void>
  initAuth: () => Promise<void>

  // 同步
  syncing: boolean
  syncNow: () => Promise<void>

  // 筛选
  selectedQuadrant: string | null // 象限筛选，null = 全部
  searchQuery: string
  tagFilter: string[]
  dueFilter: 'all' | 'overdue' | 'today' | 'thisWeek'

  // 视图
  viewDensity: ViewDensity
  focusToday: boolean      // 今日焦点模式
  isListOpen: boolean    // 移动端列表 Sheet
  editingTaskId: string | null
  isCreating: boolean
  createPosX: number
  createPosY: number

  // 历史
  undoStack: HistoryEntry[]
  redoStack: HistoryEntry[]

  // 庆祝动画
  celebrationTitle: string | null
  triggerCelebration: (title: string | null) => void

  // 多选
  selectedTaskIds: string[]
  isSelectMode: boolean

  // 操作
  initialize: () => Promise<void>
  addTask: (task: Task) => Promise<void>
  updateTask: (id: string, changes: Partial<Task>) => Promise<void>
  completeTask: (id: string) => Promise<void>
  reopenTask: (id: string) => Promise<void>
  deleteTask: (id: string) => Promise<void>
  permanentDeleteTask: (id: string) => Promise<void>
  moveTask: (id: string, posX: number, posY: number) => Promise<void>
  autoArrange: () => Promise<void>
  exportData: () => Promise<void>
  importData: (file: File, strategy: 'overwrite' | 'skip' | 'new') => Promise<{ importedTasks: number; importedTags: number; skippedTasks: number; skippedTags: number }>
  undo: () => Promise<void>
  redo: () => Promise<void>

  // 多选
  toggleSelectTask: (id: string) => void
  selectAllTasks: () => void
  clearSelection: () => void
  batchComplete: () => Promise<void>
  batchDelete: () => Promise<void>

  // 标签
  addTag: (name: string, color: string) => Promise<void>
  updateTag: (id: string, changes: Partial<{ name: string; color: string }>) => Promise<void>
  deleteTag: (id: string) => Promise<void>

  // 筛选
  setSearchQuery: (query: string) => void
  setQuadrantFilter: (q: string | null) => void
  toggleTagFilter: (tagId: string) => void
  setDueFilter: (f: 'all' | 'overdue' | 'today' | 'thisWeek') => void
  clearFilters: () => void

  // 主题
  theme: 'light' | 'dark'
  setTheme: (theme: 'light' | 'dark') => void

  // 通知
  notificationsEnabled: boolean
  setNotificationsEnabled: (enabled: boolean) => void

  // UI 状态
  setViewDensity: (density: ViewDensity) => void
  setFocusToday: (focus: boolean) => void
  setListOpen: (open: boolean) => void
  setEditingTaskId: (id: string | null) => void
  setCreating: (creating: boolean, posX?: number, posY?: number) => void
}

// ===== 过滤任务 =====
function filterTasks(
  tasks: Task[],
  searchQuery: string,
  tagFilter: string[],
  dueFilter: string,
): Task[] {
  let result = tasks

  // 文本搜索
  if (searchQuery.trim()) {
    const q = searchQuery.toLowerCase()
    result = result.filter((t) => t.title.toLowerCase().includes(q) || t.note.toLowerCase().includes(q))
  }

  // 标签筛选
  if (tagFilter.length > 0) {
    result = result.filter((t) => tagFilter.some((tid) => t.tags.includes(tid)))
  }

  // 截止日期筛选
  if (dueFilter !== 'all') {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const endOfWeek = new Date(today)
    endOfWeek.setDate(today.getDate() + (6 - today.getDay()))

    result = result.filter((t) => {
      if (!t.dueDate) return false
      const due = new Date(t.dueDate)
      const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate())
      if (dueFilter === 'overdue') return dueDay.getTime() < today.getTime()
      if (dueFilter === 'today') return dueDay.getTime() === today.getTime()
      if (dueFilter === 'thisWeek') return dueDay >= today && dueDay <= endOfWeek
      return true
    })
  }

  return result
}

// ===== Store 实现 =====
export const useStore = create<AppState>((set) => {
  // ---- 内部辅助：推入历史记录 ----
  function pushHistory(entry: HistoryEntry) {
    set((s) => ({
      undoStack: [...s.undoStack.slice(-(MAX_HISTORY - 1)), entry],
      redoStack: [],
    }))
  }

  return {
  tasks: [],
  tags: [],
  loading: true,

  // ---- 认证 ----
  user: null,
  authLoading: true,
  syncing: false,

  initAuth: async () => {
    const { data } = await supabase.auth.getSession()
    const u = data.session?.user ?? null
    setSyncUserId(u?.id ?? null)
    set({ user: u, authLoading: false })

    supabase.auth.onAuthStateChange((_event, session) => {
      const u = session?.user ?? null
      setSyncUserId(u?.id ?? null)
      set({ user: u })
    })
  },

  signUp: async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) throw error
    // 已存在用户：Supabase 返回 data.user 但 session 为 null（不报错）
    if (data.user && !data.session) {
      throw new Error('该邮箱已被注册，请直接登录')
    }
  },

  signInWithPassword: async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  },

  signInWithEmail: async (email: string) => {
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin },
    })
    if (error) throw error
  },

  signOut: async () => {
    await unsubscribeChanges()
    setSyncUserId(null)
    await supabase.auth.signOut()
    set({ tasks: [], tags: [], selectedQuadrant: null, searchQuery: '' })
  },

  // ---- 手动同步 ----
  syncNow: async () => {
    set({ syncing: true })
    try {
      const result = await pullFromCloud()
      const [tasks, tags] = await Promise.all([taskDB.getActive(), tagDB.getAll()])
      set({ tasks, tags, syncing: false })
      console.log(`[sync] 手动同步完成：${result.taskCount} 任务, ${result.tagCount} 标签`)
    } catch (e) {
      console.error('[sync] 手动同步失败:', e)
      set({ syncing: false })
    }
  },

  selectedQuadrant: null,
  searchQuery: '',
  tagFilter: [],
  dueFilter: 'all',
  viewDensity: 'standard',
  focusToday: false,
  isListOpen: false,
  editingTaskId: null,
  isCreating: false,
  createPosX: 0.5,
  createPosY: 0.5,
  undoStack: [],
  redoStack: [],
  celebrationTitle: null,
  selectedTaskIds: [],
  isSelectMode: false,

  // ---- 初始化 ----
  initialize: async () => {
    // 确保云端有预设标签（upsert，不重复）
    const uid = useStore.getState().user?.id
    if (uid) await createPresetTagsInCloud(uid).catch(() => {})

    // 从云端拉取数据（含预设标签）
    try {
      await pullFromCloud()
    } catch {
      console.warn('云端同步失败，使用本地缓存')
    }

    const [tasks, tags] = await Promise.all([taskDB.getActive(), tagDB.getAll()])
    // 清理无效任务（空标题 / 无 ID），防止空白卡片出现
    const invalidTaskIds: string[] = []
    for (const t of tasks) {
      if (!t.id || !t.title?.trim()) invalidTaskIds.push(t.id)
    }
    if (invalidTaskIds.length > 0) {
      console.warn(`[init] 清理 ${invalidTaskIds.length} 个无效任务`)
      for (const id of invalidTaskIds) {
        await taskDB.removeSilent(id).catch(() => {})
      }
      const cleaned = tasks.filter((t) => !invalidTaskIds.includes(t.id))
      set({ tasks: cleaned, tags, loading: false })
    } else {
      set({ tasks, tags, loading: false })
    }

    // 订阅实时变更（跨设备同步）
    await subscribeToChanges(async () => {
      const [tasks, tags] = await Promise.all([taskDB.getActive(), tagDB.getAll()])
      set({ tasks, tags })
    })
  },

  // ---- 任务操作 ----
  addTask: async (task) => {
    await taskDB.create(task)
    uploadTask(task).catch((e) => { console.warn('[sync] 上传失败，本地数据不受影响:', e) }) // 云端同步（静默失败，本地优先）
    const tasks = await taskDB.getActive()
    set({ tasks, isCreating: false, editingTaskId: null })
    pushHistory({
      description: `创建「${task.title}」`,
      undo: async () => {
        await taskDB.remove(task.id)
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
      redo: async () => {
        await taskDB.create(task)
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
    })
  },

  updateTask: async (id, changes) => {
    const oldTask = await taskDB.getById(id)
    if (!oldTask) return
    const extras: Partial<Task> = {}
    if (changes.posX !== undefined) {
      extras.urgencyLevel = posToLevel(changes.posX)
    }
    if (changes.posY !== undefined) {
      extras.importanceLevel = posToLevel(changes.posY)
    }
    await taskDB.update(id, { ...changes, ...extras })
    // 云端同步
    taskDB.getById(id).then((t) => { if (t) uploadTask(t).catch((e) => { console.warn('[sync] 上传失败，本地数据不受影响:', e) }) })
    const tasks = await taskDB.getActive()
    set({ tasks, editingTaskId: null })
    const newChanges = { ...changes, ...extras }
    pushHistory({
      description: `编辑「${oldTask.title}」`,
      undo: async () => {
        await taskDB.update(id, {
          title: oldTask.title,
          note: oldTask.note,
          dueDate: oldTask.dueDate,
          posX: oldTask.posX,
          posY: oldTask.posY,
          urgencyLevel: oldTask.urgencyLevel,
          importanceLevel: oldTask.importanceLevel,
          tags: oldTask.tags,
        })
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
      redo: async () => {
        await taskDB.update(id, newChanges)
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
    })
  },

  completeTask: async (id) => {
    const task = await taskDB.getById(id)
    if (!task) return
    await taskDB.complete(id)
    taskDB.getById(id).then((t) => { if (t) uploadTask(t).catch((e) => { console.warn('[sync] 上传失败，本地数据不受影响:', e) }) })

    // 单任务完成 → 触发庆祝（批量操作走 batchComplete，不触发）
    set({ celebrationTitle: task.title })

    // 重复任务：自动创建下一期，并记录关联
    const generatedNextId = task.recurrence ? uuid() : null
    if (task.recurrence && generatedNextId) {
      const nextDue = getNextDueDate(task.dueDate, task.recurrence)
      const nextTask: Task = {
        ...task,
        id: generatedNextId,
        dueDate: nextDue,
        recurrence: task.recurrence,
        generatedNextId: undefined,
        completed: false,
        completedAt: null,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      }
      await taskDB.create(nextTask as any) // eslint-disable-line
      // 在原任务上记录生成的下一期 ID
      await taskDB.update(id, { generatedNextId } as any) // eslint-disable-line
    }

    const tasks = await taskDB.getActive()
    set({ tasks })
    pushHistory({
      description: `完成「${task.title}」${task.recurrence ? '（已生成下一期）' : ''}`,
      undo: async () => {
        await taskDB.reopen(id)
        // 精确删除自动生成的下一期（用 stored generatedNextId）
        const refreshed = await taskDB.getById(id)
        if (refreshed?.generatedNextId) {
          await taskDB.remove(refreshed.generatedNextId)
          await taskDB.update(id, { generatedNextId: undefined } as any)
        }
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
      redo: async () => {
        await taskDB.complete(id)
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
    })
  },

  reopenTask: async (id) => {
    const task = await taskDB.getById(id)
    if (!task) return
    // 先清理自动生成的下一期
    if (task.generatedNextId) {
      await taskDB.remove(task.generatedNextId)
      await taskDB.update(id, { generatedNextId: undefined } as any)
    }
    await taskDB.reopen(id)
    taskDB.getById(id).then((t) => { if (t) uploadTask(t).catch((e) => { console.warn('[sync] 上传失败，本地数据不受影响:', e) }) })
    const tasks = await taskDB.getActive()
    set({ tasks })
    pushHistory({
      description: `恢复「${task.title}」`,
      undo: async () => {
        await taskDB.complete(id)
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
      redo: async () => {
        await taskDB.reopen(id)
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
    })
  },

  deleteTask: async (id) => {
    const task = await taskDB.getById(id)
    if (!task) return
    await taskDB.remove(id)
    deleteTaskRemote(id).catch((e) => { console.warn('[sync] 上传失败，本地数据不受影响:', e) })
    const tasks = await taskDB.getActive()
    set({ tasks, editingTaskId: null })
    pushHistory({
      description: `删除「${task.title}」`,
      undo: async () => {
        await taskDB.create(task)
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
      redo: async () => {
        await taskDB.remove(id)
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
    })
  },

  permanentDeleteTask: async (id) => {
    await taskDB.permanentRemove(id)
    deleteTaskRemote(id).catch((e) => { console.warn('[sync] 上传失败，本地数据不受影响:', e) })
  },

  moveTask: async (id, posX, posY) => {
    const task = await taskDB.getById(id)
    if (!task) return
    const oldPosX = task.posX
    const oldPosY = task.posY
    await taskDB.update(id, {
      posX,
      posY,
      urgencyLevel: posToLevel(posX),
      importanceLevel: posToLevel(posY),
      updatedAt: new Date().toISOString(),
    })
    const updated = await taskDB.getById(id)
    if (updated) uploadTask(updated).catch((e) => { console.warn('[sync] 上传失败，本地数据不受影响:', e) })
    const tasks = await taskDB.getActive()
    set({ tasks })
    pushHistory({
      description: `移动「${task.title}」`,
      undo: async () => {
        await taskDB.update(id, {
          posX: oldPosX,
          posY: oldPosY,
          urgencyLevel: posToLevel(oldPosX),
          importanceLevel: posToLevel(oldPosY),
        })
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
      redo: async () => {
        await taskDB.update(id, {
          posX,
          posY,
          urgencyLevel: posToLevel(posX),
          importanceLevel: posToLevel(posY),
        })
        const tasks = await taskDB.getActive()
        set({ tasks })
      },
    })
  },

  // ---- 一键排列 ----
  autoArrange: async () => {
    const { tasks } = useStore.getState()
    const active = tasks.filter((t) => !t.completed)
    if (active.length === 0) return

    // 保存旧位置
    const oldPositions = new Map(active.map((t) => [t.id, { posX: t.posX, posY: t.posY }]))

    // 按象限分组（基于等级语义）
    const groups: Record<string, typeof active> = { Q1: [], Q2: [], Q3: [], Q4: [] }
    for (const task of active) {
      const q = getQuadrant(task.posX, task.posY)
      groups[q].push(task)
    }

    // 记录同一坐标点的任务数，用于碰撞微偏移
    const slotMap = new Map<string, number>()
    const newPositions = new Map<string, { posX: number; posY: number }>()

    for (const [_q, qTasks] of Object.entries(groups)) {
      if (qTasks.length === 0) continue

      const sorted = [...qTasks].sort((a, b) => {
        const scoreA = Math.abs(a.importanceLevel * a.urgencyLevel)
        const scoreB = Math.abs(b.importanceLevel * b.urgencyLevel)
        return scoreB - scoreA
      })

      for (const task of sorted) {
        let posX = levelToPos(task.urgencyLevel)
        let posY = levelToPos(task.importanceLevel)

        const key = `${posX.toFixed(2)},${posY.toFixed(2)}`
        const slotIdx = slotMap.get(key) ?? 0
        slotMap.set(key, slotIdx + 1)

        if (slotIdx > 0) {
          const angle = slotIdx * 2.4
          const r = 0.025 * Math.ceil(slotIdx / 2)
          posX = Math.max(0.01, Math.min(0.99, posX + Math.cos(angle) * r))
          posY = Math.max(0.01, Math.min(0.99, posY + Math.sin(angle) * r))
        }

        if (Math.abs(task.posX - posX) < 0.001 && Math.abs(task.posY - posY) < 0.001) continue

        newPositions.set(task.id, { posX, posY })
        await taskDB.update(task.id, {
          posX,
          posY,
          updatedAt: new Date().toISOString(),
        })
      }
    }

    const updatedTasks = await taskDB.getActive()
    set({ tasks: updatedTasks })

    // 批量上传位置变更的任务
    if (newPositions.size > 0) {
      const changed = updatedTasks.filter((t) => newPositions.has(t.id))
      uploadTasks(changed).catch(() => {})
      pushHistory({
        description: '一键排列',
        undo: async () => {
          for (const [id, pos] of oldPositions) {
            await taskDB.update(id, {
              posX: pos.posX,
              posY: pos.posY,
              urgencyLevel: posToLevel(pos.posX),
              importanceLevel: posToLevel(pos.posY),
            })
          }
          const tasks = await taskDB.getActive()
          set({ tasks })
        },
        redo: async () => {
          for (const [id, pos] of newPositions) {
            await taskDB.update(id, {
              posX: pos.posX,
              posY: pos.posY,
              urgencyLevel: posToLevel(pos.posX),
              importanceLevel: posToLevel(pos.posY),
            })
          }
          const tasks = await taskDB.getActive()
          set({ tasks })
        },
      })
    }
  },

  // ---- 撤销 / 重做 ----
  undo: async () => {
    const { undoStack } = useStore.getState()
    if (undoStack.length === 0) return
    const entry = undoStack[undoStack.length - 1]
    await entry.undo()
    set((s) => ({
      undoStack: s.undoStack.slice(0, -1),
      redoStack: [...s.redoStack, entry],
    }))
  },

  redo: async () => {
    const { redoStack } = useStore.getState()
    if (redoStack.length === 0) return
    const entry = redoStack[redoStack.length - 1]
    await entry.redo()
    set((s) => ({
      redoStack: s.redoStack.slice(0, -1),
      undoStack: [...s.undoStack, entry],
    }))
  },

  // ---- 庆祝 ----
  triggerCelebration: (title) => set({ celebrationTitle: title }),

  // ---- 多选 ----
  toggleSelectTask: (id) => {
    set((s) => {
      const exists = s.selectedTaskIds.includes(id)
      const next = exists
        ? s.selectedTaskIds.filter((x) => x !== id)
        : [...s.selectedTaskIds, id]
      return {
        selectedTaskIds: next,
        isSelectMode: next.length > 0,
      }
    })
  },

  selectAllTasks: () => {
    const { tasks } = useStore.getState()
    set({ selectedTaskIds: tasks.map((t) => t.id), isSelectMode: true })
  },

  clearSelection: () => {
    set({ selectedTaskIds: [], isSelectMode: false })
  },

  batchComplete: async () => {
    const { selectedTaskIds } = useStore.getState()
    const updated: Task[] = []
    for (const id of selectedTaskIds) {
      await taskDB.complete(id)
      const t = await taskDB.getById(id)
      if (t) updated.push(t)
    }
    uploadTasks(updated).catch((e) => { console.warn('[sync] 批量上传失败:', e) })
    const tasks = await taskDB.getActive()
    set({ tasks, selectedTaskIds: [], isSelectMode: false })
  },

  batchDelete: async () => {
    const { selectedTaskIds } = useStore.getState()
    // 保存已选任务以便撤销
    const deletedTasks: Task[] = []
    for (const id of selectedTaskIds) {
      const task = await taskDB.getById(id)
      if (task) deletedTasks.push(task)
      await taskDB.remove(id)
    }
    deleteTasksRemote(selectedTaskIds).catch(() => {})
    const tasks = await taskDB.getActive()
    set({ tasks, selectedTaskIds: [], isSelectMode: false })
    if (deletedTasks.length > 0) {
      pushHistory({
        description: `批量删除 ${deletedTasks.length} 个任务`,
        undo: async () => {
          for (const t of deletedTasks) {
            await taskDB.create(t)
          }
          const tasks = await taskDB.getActive()
          set({ tasks })
        },
        redo: async () => {
          for (const t of deletedTasks) {
            await taskDB.remove(t.id)
          }
          const tasks = await taskDB.getActive()
          set({ tasks })
        },
      })
    }
  },

  exportData: async () => {
    const json = await taskDB.exportJSON()
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const date = new Date().toISOString().slice(0, 10)
    a.download = `四时有序-备份-${date}.json`
    a.click()
    URL.revokeObjectURL(url)
  },

  importData: async (file, strategy) => {
    const text = await file.text()
    const result = await taskDB.importJSON(text, strategy)
    const [tasks, tags] = await Promise.all([taskDB.getActive(), tagDB.getAll()])
    set({ tasks, tags })
    return result
  },

  // ---- 标签操作 ----
  addTag: async (name, color) => {
    const id = await tagDB.create({ name, color, isPreset: false })
    const created = await tagDB.getById(id)
    if (created) uploadTag(created).catch((e) => { console.warn('[sync] 上传失败，本地数据不受影响:', e) })
    const tags = await tagDB.getAll()
    set({ tags })
  },

  updateTag: async (id, changes) => {
    await tagDB.update(id, changes)
    const updated = await tagDB.getById(id)
    if (updated) uploadTag(updated).catch((e) => { console.warn('[sync] 上传失败，本地数据不受影响:', e) })
    const tags = await tagDB.getAll()
    set({ tags })
  },

  deleteTag: async (id) => {
    await tagDB.remove(id)
    deleteTagRemote(id).catch((e) => { console.warn('[sync] 上传失败，本地数据不受影响:', e) })
    const tags = await tagDB.getAll()
    set({ tags })
  },

  // ---- 筛选 ----
  setSearchQuery: (query) => set({ searchQuery: query }),
  setQuadrantFilter: (q) => set({ selectedQuadrant: q }),
  toggleTagFilter: (tagId) =>
    set((s) => ({
      tagFilter: s.tagFilter.includes(tagId)
        ? s.tagFilter.filter((id) => id !== tagId)
        : [...s.tagFilter, tagId],
    })),
  setDueFilter: (f) => set({ dueFilter: f }),
  clearFilters: () => set({ searchQuery: '', selectedQuadrant: null, tagFilter: [], dueFilter: 'all' }),

  // ---- 主题 ----
  theme: 'light',
  setTheme: (theme) => {
    localStorage.setItem('sishi-theme', theme)
    set({ theme })
  },

  // ---- 通知 ----
  notificationsEnabled: false,
  setNotificationsEnabled: (enabled) => {
    localStorage.setItem('sishi-notifications', String(enabled))
    set({ notificationsEnabled: enabled })
  },

  // ---- UI 状态 ----
  setViewDensity: (density) => {
    localStorage.setItem('sishi-view-density', density)
    set({ viewDensity: density })
  },
  setFocusToday: (focus) => set({ focusToday: focus }),
  setListOpen: (open) => set({ isListOpen: open }),
  setEditingTaskId: (id) => set({ editingTaskId: id }),
  setCreating: (creating, posX = 0.5, posY = 0.5) =>
    set({ isCreating: creating, createPosX: posX, createPosY: posY }),
}})

// ===== 外部选择器 =====

// 按象限分组的活跃任务（精确订阅 tasks + searchQuery，避免无关状态更新触发重渲染）
export function useGroupedTasks(): Record<string, Task[]> {
  const tasks = useStore((s) => s.tasks)
  const searchQuery = useStore((s) => s.searchQuery)
  const tagFilter = useStore((s) => s.tagFilter)
  const dueFilter = useStore((s) => s.dueFilter)
  const selectedQuadrant = useStore((s) => s.selectedQuadrant)

  return useMemo(() => {
    const filtered = filterTasks(tasks, searchQuery, tagFilter, dueFilter)
    const groups: Record<string, Task[]> = { Q1: [], Q2: [], Q3: [], Q4: [] }
    for (const task of filtered) {
      const q = getQuadrant(task.posX, task.posY)
      // 象限筛选
      if (selectedQuadrant && q !== selectedQuadrant) continue
      groups[q].push(task)
    }
    return groups
  }, [tasks, searchQuery, tagFilter, dueFilter, selectedQuadrant])
}

// 根据 ID 获取标签映射
export function useTagMap(): Record<string, Tag> {
  const tags = useStore((s) => s.tags)
  return useMemo(() => {
    const map: Record<string, Tag> = {}
    for (const t of tags) map[t.id] = t
    return map
  }, [tags])
}
