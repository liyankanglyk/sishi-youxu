/**
 * Dexie 仓储封装
 *
 * 封装对 IndexedDB 的所有读写，task store / sync engine 仅通过本模块访问本地数据。
 * 与 web/src/db/index.ts 配合使用（LocalTask / LocalTag / LocalChecklistItem / PendingOpRecord）。
 */

import { db, generateUuid, nowISO } from '@/db'
import type {
  LocalChecklistItem,
  LocalTag,
  LocalTask,
  LocalTaskTag,
} from '@/db'
import type { EntityType, PendingOpRecord, SyncState } from './types'

// =============================================================================
// Task
// =============================================================================

/** 读取所有未删除任务（含软删除记录，用于恢复视图） */
export async function getAllTasks(includeDeleted = false): Promise<LocalTask[]> {
  const all = await db.tasks.orderBy('updatedAt').reverse().toArray()
  return includeDeleted ? all : all.filter((t) => !t.deletedAt)
}

/** 读取单个任务 */
export async function getTask(uuid: string): Promise<LocalTask | undefined> {
  return db.tasks.get(uuid)
}

/** upsert 任务（含生成 uuid / 时间戳 / 默认同步状态） */
export async function putTask(task: Partial<LocalTask> & { uuid: string }): Promise<LocalTask> {
  const now = nowISO()
  const existing = await db.tasks.get(task.uuid)
  const merged: LocalTask = {
    uuid: task.uuid,
    userUuid: task.userUuid ?? existing?.userUuid,
    title: task.title ?? existing?.title ?? '',
    urgencyLevel: task.urgencyLevel ?? existing?.urgencyLevel ?? 0,
    importanceLevel: task.importanceLevel ?? existing?.importanceLevel ?? 0,
    dueDate: task.dueDate !== undefined ? task.dueDate : existing?.dueDate ?? null,
    recurrence: task.recurrence !== undefined ? task.recurrence : existing?.recurrence ?? null,
    note: task.note !== undefined ? task.note : existing?.note ?? null,
    completed: task.completed ?? existing?.completed ?? false,
    completedAt: task.completedAt !== undefined ? task.completedAt : existing?.completedAt ?? null,
    sortOrder: task.sortOrder ?? existing?.sortOrder ?? 0,
    remindAt: task.remindAt !== undefined ? task.remindAt : existing?.remindAt ?? null,
    remindOffsetMinutes:
      task.remindOffsetMinutes !== undefined ? task.remindOffsetMinutes : existing?.remindOffsetMinutes ?? null,
    reminderState: task.reminderState ?? existing?.reminderState ?? 'idle',
    createdAt: existing?.createdAt ?? task.createdAt ?? now,
    updatedAt: now,
    deletedAt: task.deletedAt !== undefined ? task.deletedAt : existing?.deletedAt ?? null,
    syncStatus: 'pending',
    version: (existing?.version ?? 0) + 1,
  }
  await db.tasks.put(merged)
  return merged
}

/** 软删除任务 */
export async function softDeleteTask(uuid: string): Promise<LocalTask | undefined> {
  const existing = await db.tasks.get(uuid)
  if (!existing) return undefined
  const updated: LocalTask = {
    ...existing,
    deletedAt: nowISO(),
    syncStatus: 'pending',
    version: existing.version + 1,
    updatedAt: nowISO(),
  }
  await db.tasks.put(updated)
  return updated
}

/** 用服务端记录直接覆盖本地（用于 pull 后写入或冲突解决后选择「使用服务端」） */
export async function overwriteFromServer(record: Record<string, unknown>): Promise<void> {
  const uuid = record.uuid as string
  if (!uuid) return
  const now = nowISO()
  const merged: LocalTask = {
    uuid,
    userUuid: (record.userUuid as string) ?? undefined,
    title: (record.title as string) ?? '',
    urgencyLevel: Number((record.urgencyLevel as number) ?? 0),
    importanceLevel: Number((record.importanceLevel as number) ?? 0),
    dueDate: (record.dueDate as string | null) ?? null,
    recurrence: (record.recurrence as string | null) ?? null,
    note: (record.note as string | null) ?? null,
    completed: Boolean(record.completed),
    completedAt: (record.completedAt as string | null) ?? null,
    sortOrder: Number((record.sortOrder as number) ?? 0),
    remindAt: (record.remindAt as string | null) ?? null,
    remindOffsetMinutes: (record.remindOffsetMinutes as number | null) ?? null,
    reminderState: (record.reminderState as string) ?? 'idle',
    createdAt: (record.createdAt as string) ?? now,
    updatedAt: (record.updatedAt as string) ?? now,
    deletedAt: (record.deletedAt as string | null) ?? null,
    syncStatus: 'synced',
    version: Number((record.version as number) ?? 1),
  }
  await db.tasks.put(merged)
}

/** 物理删除（用于 pull 返回 deleted[]） */
export async function hardDeleteTask(uuid: string): Promise<void> {
  await db.tasks.delete(uuid)
  await db.taskTags.where('taskUuid').equals(uuid).delete()
  await db.checklistItems.where('taskUuid').equals(uuid).delete()
}

// =============================================================================
// Tag
// =============================================================================

export async function getAllTags(): Promise<LocalTag[]> {
  return db.tags.toArray()
}

/** 读取单个标签 */
export async function getTag(uuid: string): Promise<LocalTag | undefined> {
  return db.tags.get(uuid)
}

export async function putTag(tag: Partial<LocalTag> & { uuid: string }): Promise<LocalTag> {
  const now = nowISO()
  const existing = await db.tags.get(tag.uuid)
  const merged: LocalTag = {
    uuid: tag.uuid,
    userUuid: tag.userUuid ?? existing?.userUuid,
    name: tag.name ?? existing?.name ?? '',
    color: tag.color ?? existing?.color ?? '#cccccc',
    isPreset: tag.isPreset ?? existing?.isPreset ?? false,
    createdAt: existing?.createdAt ?? tag.createdAt ?? now,
    updatedAt: now,
    deletedAt: tag.deletedAt !== undefined ? tag.deletedAt : existing?.deletedAt ?? null,
    syncStatus: 'pending',
    version: (existing?.version ?? 0) + 1,
  }
  await db.tags.put(merged)
  return merged
}

export async function softDeleteTag(uuid: string): Promise<void> {
  const existing = await db.tags.get(uuid)
  if (!existing) return
  await db.tags.put({
    ...existing,
    deletedAt: nowISO(),
    syncStatus: 'pending',
    version: existing.version + 1,
    updatedAt: nowISO(),
  })
}

export async function overwriteTagFromServer(record: Record<string, unknown>): Promise<void> {
  const uuid = record.uuid as string
  if (!uuid) return
  const now = nowISO()
  await db.tags.put({
    uuid,
    userUuid: (record.userUuid as string) ?? undefined,
    name: (record.name as string) ?? '',
    color: (record.color as string) ?? '#cccccc',
    isPreset: Boolean(record.isPreset),
    createdAt: (record.createdAt as string) ?? now,
    updatedAt: (record.updatedAt as string) ?? now,
    deletedAt: (record.deletedAt as string | null) ?? null,
    syncStatus: 'synced',
    version: Number((record.version as number) ?? 1),
  })
}

export async function hardDeleteTag(uuid: string): Promise<void> {
  await db.tags.delete(uuid)
  await db.taskTags.where('tagUuid').equals(uuid).delete()
}

// =============================================================================
// TaskTag (关联表)
// =============================================================================

export async function getTaskTags(taskUuid: string): Promise<LocalTaskTag[]> {
  return db.taskTags.where('taskUuid').equals(taskUuid).toArray()
}

export async function linkTaskTag(taskUuid: string, tagUuid: string): Promise<void> {
  await db.taskTags.put({ taskUuid, tagUuid })
}

export async function unlinkTaskTag(taskUuid: string, tagUuid: string): Promise<void> {
  await db.taskTags.where({ taskUuid, tagUuid }).delete()
}

export async function overwriteTaskTagFromServer(record: { taskUuid: string; tagUuid: string }): Promise<void> {
  await db.taskTags.put(record)
}

// =============================================================================
// ChecklistItem
// =============================================================================

export async function getChecklistItems(taskUuid: string): Promise<LocalChecklistItem[]> {
  return db.checklistItems.where('taskUuid').equals(taskUuid).sortBy('sortOrder')
}

/** 读取单个检查项 */
export async function getChecklistItem(uuid: string): Promise<LocalChecklistItem | undefined> {
  return db.checklistItems.get(uuid)
}

/** 读取单条任务-标签关联（复合主键） */
export async function getTaskTag(
  taskUuid: string,
  tagUuid: string,
): Promise<LocalTaskTag | undefined> {
  return db.taskTags.get([taskUuid, tagUuid])
}

export async function putChecklistItem(item: Partial<LocalChecklistItem> & { uuid: string }): Promise<LocalChecklistItem> {
  const now = nowISO()
  const existing = await db.checklistItems.get(item.uuid)
  const merged: LocalChecklistItem = {
    uuid: item.uuid,
    taskUuid: item.taskUuid ?? existing?.taskUuid ?? '',
    title: item.title ?? existing?.title ?? '',
    completed: item.completed ?? existing?.completed ?? false,
    sortOrder: item.sortOrder ?? existing?.sortOrder ?? 0,
    createdAt: existing?.createdAt ?? item.createdAt ?? now,
    updatedAt: now,
    deletedAt: item.deletedAt !== undefined ? item.deletedAt : existing?.deletedAt ?? null,
    syncStatus: 'pending',
    version: (existing?.version ?? 0) + 1,
  }
  await db.checklistItems.put(merged)
  return merged
}

export async function overwriteChecklistFromServer(record: Record<string, unknown>): Promise<void> {
  const uuid = record.uuid as string
  if (!uuid) return
  const now = nowISO()
  await db.checklistItems.put({
    uuid,
    taskUuid: (record.taskUuid as string) ?? '',
    title: (record.title as string) ?? '',
    completed: Boolean(record.completed),
    sortOrder: Number((record.sortOrder as number) ?? 0),
    createdAt: (record.createdAt as string) ?? now,
    updatedAt: (record.updatedAt as string) ?? now,
    deletedAt: (record.deletedAt as string | null) ?? null,
    syncStatus: 'synced',
    version: Number((record.version as number) ?? 1),
  })
}

export async function getAllTaskTags(): Promise<LocalTaskTag[]> {
  return db.taskTags.toArray()
}

export async function getAllChecklistItems(): Promise<LocalChecklistItem[]> {
  return db.checklistItems.toArray()
}

/** 写单条任务-标签关联 */
export async function putTaskTag(taskUuid: string, tagUuid: string): Promise<void> {
  await db.taskTags.put({ taskUuid, tagUuid })
}

/** 删除单条任务-标签关联 */
export async function deleteTaskTag(taskUuid: string, tagUuid: string): Promise<void> {
  await db.taskTags.where({ taskUuid, tagUuid }).delete()
}

/** 软删除检查项（与服务端软删语义一致） */
export async function softDeleteChecklistItem(uuid: string): Promise<void> {
  const existing = await db.checklistItems.get(uuid)
  if (!existing) return
  await db.checklistItems.put({
    ...existing,
    deletedAt: nowISO(),
    syncStatus: 'pending',
    version: existing.version + 1,
    updatedAt: nowISO(),
  })
}

/** 恢复被软删的任务（撤销删除用；uuid 不变，服务端走 restore 动作） */
export async function restoreTask(uuid: string): Promise<void> {
  const existing = await db.tasks.get(uuid)
  if (!existing) return
  await db.tasks.put({
    ...existing,
    deletedAt: null,
    syncStatus: 'pending',
    version: existing.version + 1,
    updatedAt: nowISO(),
  })
}

// =============================================================================
// PendingOps 队列
// =============================================================================

/** 入队一个 op（去重：同 entity+entityUuid 已有 pending op 时替换 payload）
 *
 * options.force —— 冲突已由用户裁决为"保留本地"时置 true，推送时服务端会跳过版本冲突检测。
 * 不带这个标记的话，重新入队的 op 每次推送都会再次被判冲突，形成死循环。
 */
export async function enqueueOp(
  entityType: EntityType,
  opType: 'upsert' | 'delete' | 'restore',
  entityUuid: string,
  payload: Record<string, unknown>,
  options?: { force?: boolean },
): Promise<PendingOpRecord> {
  const force = options?.force ?? false
  // 查找是否已有同实体的 pending op（schema 仅声明单字段索引，用 filter 实现）
  const existing = await db.pendingOps
    .where('entityType')
    .equals(entityType)
    .filter(
      (op) =>
        op.entityUuid === entityUuid &&
        (op.status === 'pending' || op.status === 'failed'),
    )
    .first()

  if (existing && existing.id != null) {
    // 折叠：删除 op 优先于 upsert；如果已有 pending upsert 直接覆盖 payload
    if (existing.opType === 'delete' && opType === 'upsert') {
      // upsert 后于 delete → 忽略 upsert（实体已被删除）
      return existing
    }
    const updated: PendingOpRecord = {
      ...existing,
      opType,
      payload,
      createdAt: nowISO(),
      status: 'pending',
      errorMessage: undefined,
      force: force || existing.force,
    }
    await db.pendingOps.put(updated)
    return updated
  }

  const record: PendingOpRecord = {
    opId: generateUuid(),
    entityType,
    opType,
    entityUuid,
    payload,
    createdAt: nowISO(),
    status: 'pending',
    ...(force ? { force: true } : {}),
  }
  await db.pendingOps.add(record)
  return record
}

export async function getPendingOps(): Promise<PendingOpRecord[]> {
  return db.pendingOps.orderBy('id').toArray()
}

export async function getPendingCount(): Promise<number> {
  return db.pendingOps.where('status').equals('pending').count()
}

export async function updateOpStatus(
  id: number,
  status: PendingOpRecord['status'],
  errorMessage?: string,
): Promise<void> {
  await db.pendingOps.update(id, { status, errorMessage })
}

export async function deleteOp(id: number): Promise<void> {
  await db.pendingOps.delete(id)
}

export async function clearAllPendingOps(): Promise<void> {
  await db.pendingOps.clear()
}

// =============================================================================
// SyncMeta（lastPulledAt / serverTimeOffset 等键值）
// =============================================================================

export async function getSyncMeta(key: string): Promise<string | undefined> {
  const entry = await db.syncMeta.get(key)
  return entry?.value
}

export async function setSyncMeta(key: string, value: string): Promise<void> {
  await db.syncMeta.put({ key, value })
}

// =============================================================================
// 一次性清空所有本地数据（登出 / 切换账号用）
// =============================================================================

export async function clearAllLocalData(): Promise<void> {
  await Promise.all([
    db.tasks.clear(),
    db.tags.clear(),
    db.taskTags.clear(),
    db.checklistItems.clear(),
    db.pendingOps.clear(),
    db.syncMeta.clear(),
  ])
}

// =============================================================================
// UI 用 helper
// =============================================================================

/** 读取当前 SyncState 快照（用 sync engine 主动刷新更佳，这里用于初始化） */
export async function getInitialSyncState(): Promise<Pick<SyncState, 'pendingCount' | 'lastPulledAt'>> {
  const [pendingCount, lastPulledAt] = await Promise.all([
    getPendingCount(),
    getSyncMeta('lastPulledAt'),
  ])
  return { pendingCount, lastPulledAt: lastPulledAt ?? null }
}