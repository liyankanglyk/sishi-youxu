/**
 * 云端同步模块
 * IndexedDB 为主数据源，Supabase 为云端镜像。写操作同时写两端，读操作从本地读。
 */
import type { RealtimeChannel } from '@supabase/supabase-js'
import { supabase } from './supabase'
import { taskDB, tagDB } from '../db'
import type { Task, Tag } from '../types'

// ===== 内部工具 =====

const warn = (...args: unknown[]) => { if (import.meta.env.DEV) console.warn(...args) }

interface SupabaseRow { [key: string]: unknown }

function taskToRow(task: Task, userId: string): SupabaseRow {
  return {
    id: task.id, user_id: userId, title: task.title,
    pos_x: task.posX, pos_y: task.posY,
    urgency_level: task.urgencyLevel, importance_level: task.importanceLevel,
    due_date: task.dueDate, tags: task.tags, note: task.note,
    recurrence: task.recurrence, generated_next_id: task.generatedNextId ?? null,
    completed: task.completed, completed_at: task.completedAt,
    created_at: task.createdAt, updated_at: task.updatedAt,
  }
}

function parseTags(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw
  if (typeof raw === 'string') {
    const t = raw.trim()
    if (t === '{}' || t === '') return []
    return t.replace(/[{}"]/g, '').split(',').filter(Boolean)
  }
  return []
}

function rowToTask(row: SupabaseRow): Task | null {
  // 防御：过滤掉无效数据（空标题 / 无 ID）
  const id = row.id as string | null
  const title = row.title as string | null
  if (!id || !title || !title.trim()) return null
  return {
    id, title,
    posX: typeof row.pos_x === 'number' && !isNaN(row.pos_x) ? row.pos_x : 0.5,
    posY: typeof row.pos_y === 'number' && !isNaN(row.pos_y) ? row.pos_y : 0.5,
    urgencyLevel: typeof row.urgency_level === 'number' && !isNaN(row.urgency_level) ? row.urgency_level : 0,
    importanceLevel: typeof row.importance_level === 'number' && !isNaN(row.importance_level) ? row.importance_level : 0,
    dueDate: (row.due_date as string) || null, tags: parseTags(row.tags),
    note: (row.note as string) || '', recurrence: (row.recurrence as Task['recurrence']) || null,
    generatedNextId: (row.generated_next_id as string) || undefined,
    completed: !!row.completed, completedAt: (row.completed_at as string) || null,
    createdAt: (row.created_at as string) || new Date().toISOString(),
    updatedAt: (row.updated_at as string) || new Date().toISOString(),
  }
}

function tagToRow(tag: Tag, userId: string): SupabaseRow {
  return { id: tag.id, user_id: userId, name: tag.name, color: tag.color, is_preset: tag.isPreset }
}

function rowToTag(row: SupabaseRow): Tag {
  return { id: row.id as string, name: row.name as string, color: row.color as string, isPreset: !!row.is_preset }
}

// ===== 用户 ID 缓存 =====

let cachedUserId: string | null = null
export function setSyncUserId(uid: string | null) { cachedUserId = uid }

// ===== 上传 =====

export async function uploadTask(task: Task): Promise<void> {
  if (!cachedUserId || !task.id || !task.title) return
  const { error } = await supabase.from('sishi_tasks').upsert(taskToRow(task, cachedUserId) as any)
  if (error) warn('[sync] uploadTask 失败:', error.message)
}

export async function uploadTasks(tasks: Task[]): Promise<void> {
  if (!cachedUserId || tasks.length === 0) return
  const rows = tasks.filter((t) => t.id && t.title).map((t) => taskToRow(t, cachedUserId!))
  if (rows.length === 0) return
  const { error } = await supabase.from('sishi_tasks').upsert(rows as any)
  if (error) warn('[sync] uploadTasks 失败:', error.message)
}

export async function uploadTag(tag: Tag): Promise<void> {
  if (!cachedUserId) return
  const { error } = await supabase.from('sishi_tags').upsert(tagToRow(tag, cachedUserId) as any)
  if (error) warn('[sync] uploadTag 失败:', error.message)
}

export async function deleteTasksRemote(ids: string[]): Promise<void> {
  if (ids.length === 0) return
  const { error } = await supabase.from('sishi_tasks').delete().in('id', ids)
  if (error) warn('[sync] deleteTasks 失败:', error.message)
}

export async function deleteTaskRemote(id: string): Promise<void> {
  const { error } = await supabase.from('sishi_tasks').delete().eq('id', id)
  if (error) warn('[sync] deleteTask 失败:', error.message)
}

export async function deleteTagRemote(id: string): Promise<void> {
  const { error } = await supabase.from('sishi_tags').delete().eq('id', id)
  if (error) warn('[sync] deleteTag 失败:', error.message)
}

// ===== 下拉同步 =====

export async function pullFromCloud(): Promise<{ taskCount: number; tagCount: number }> {
  const { data } = await supabase.auth.getSession()
  const session = data?.session
  if (!session?.user) return { taskCount: 0, tagCount: 0 }

  const [taskRes, tagRes] = await Promise.all([
    supabase.from('sishi_tasks').select('*').eq('user_id', session.user.id),
    supabase.from('sishi_tags').select('*').eq('user_id', session.user.id),
  ])

  if (taskRes.error || tagRes.error) {
    warn('[sync] pullFromCloud 失败:', taskRes.error?.message || tagRes.error?.message)
    return { taskCount: 0, tagCount: 0 }
  }

  const cloudTasks = ((taskRes.data || []) as SupabaseRow[]).map(rowToTask).filter((t): t is Task => t !== null)
  const cloudTags = ((tagRes.data || []) as SupabaseRow[]).map(rowToTag)

  // 按名称合并标签（保证同名标签 ID 跨设备统一）
  const localTags = await tagDB.getAll()
  const localByName = new Map(localTags.map((t) => [t.name, t]))
  const idMap = new Map<string, string>()

  for (const ct of cloudTags) {
    const local = localByName.get(ct.name)
    if (local && local.id !== ct.id) {
      idMap.set(local.id, ct.id)
      await tagDB.remove(local.id)
      await tagDB.createIfNotExists(ct)
    } else if (!local) {
      await tagDB.createIfNotExists(ct)
    }
  }

  // 合并任务并修正标签 ID
  for (const ct of cloudTasks) {
    if (idMap.size > 0) ct.tags = ct.tags.map((tid) => idMap.get(tid) || tid)
    await taskDB.createIfNotExists(ct)
  }

  // 修正本地任务的旧标签 ID
  if (idMap.size > 0) {
    for (const lt of await taskDB.getAll()) {
      const fixed = lt.tags.map((tid) => idMap.get(tid) || tid)
      if (fixed.some((t, i) => t !== lt.tags[i])) {
        await taskDB.update(lt.id, { tags: fixed } as Partial<Task>)
      }
    }
  }

  return { taskCount: cloudTasks.length, tagCount: cloudTags.length }
}

// ===== 实时订阅 =====

let realtimeChannel: RealtimeChannel | null = null
let subscribing = false

export async function subscribeToChanges(onChange: () => void): Promise<void> {
  if (subscribing) return
  subscribing = true
  await unsubscribeChanges()

  realtimeChannel = supabase
    .channel('sishi-sync')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'sishi_tasks' }, async (payload) => {
      if (payload.eventType === 'DELETE') {
        await taskDB.removeSilent(payload.old.id as string)
      } else {
        const task = rowToTask(payload.new as SupabaseRow)
        if (task) await taskDB.createIfNotExists(task)  // 跳过无效任务（如空标题）
      }
      onChange()
    })
    .on('postgres_changes', { event: '*', schema: 'public', table: 'sishi_tags' }, async (payload) => {
      if (payload.eventType === 'DELETE') {
        await tagDB.removeSilent(payload.old.id as string)
      } else {
        await tagDB.createIfNotExists(rowToTag(payload.new as SupabaseRow))
      }
      onChange()
    })
    .subscribe()
  subscribing = false
}

export async function unsubscribeChanges(): Promise<void> {
  if (realtimeChannel) {
    await supabase.removeChannel(realtimeChannel)
    realtimeChannel = null
  }
  subscribing = false
}
