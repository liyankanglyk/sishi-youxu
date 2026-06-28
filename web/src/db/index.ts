import Dexie, { type Table } from 'dexie'

// ── 与后端模型对齐的实体接口 ──

export interface LocalTask {
  uuid: string
  userUuid?: string
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
  reminderState: string
  createdAt: string
  updatedAt: string
  deletedAt: string | null
  syncStatus: 'local' | 'synced' | 'pending'
  version: number
}

export interface LocalTag {
  uuid: string
  userUuid?: string
  name: string
  color: string
  isPreset: boolean
  createdAt: string
  updatedAt: string
  deletedAt: string | null
  syncStatus: 'local' | 'synced' | 'pending'
  version: number
}

export interface LocalTaskTag {
  taskUuid: string
  tagUuid: string
}

export interface LocalChecklistItem {
  uuid: string
  taskUuid: string
  title: string
  completed: boolean
  sortOrder: number
  createdAt: string
  updatedAt: string
  deletedAt: string | null
  syncStatus: 'local' | 'synced' | 'pending'
  version: number
}

export interface PendingOp {
  id?: number
  opType: 'upsert' | 'delete'
  entityType: 'task' | 'tag' | 'taskTag' | 'checklistItems'
  entityUuid: string
  payload: Record<string, unknown>
  createdAt: string
}

export interface SyncMetaEntry {
  key: string
  value: string
}

export interface AuthSessionEntry {
  key: string
  accessToken: string
  refreshToken: string
  user: Record<string, unknown>
  expiresAt: string
}

// ── 数据库类 ──

class SishiYouxuDB extends Dexie {
  tasks!: Table<LocalTask, string>
  tags!: Table<LocalTag, string>
  taskTags!: Table<LocalTaskTag, [string, string]>
  checklistItems!: Table<LocalChecklistItem, string>
  pendingOps!: Table<PendingOp, number>
  syncMeta!: Table<SyncMetaEntry, string>
  authSession!: Table<AuthSessionEntry, string>

  constructor() {
    super('sishi_youxu')

    this.version(1).stores({
      tasks: 'uuid, userUuid, completed, sortOrder, syncStatus, updatedAt',
      tags: 'uuid, userUuid, name, syncStatus',
      taskTags: '[taskUuid+tagUuid], taskUuid, tagUuid',
      checklistItems: 'uuid, taskUuid, sortOrder, syncStatus',
      pendingOps: '++id, entityType, entityUuid, createdAt',
      syncMeta: 'key',
      authSession: 'key',
    })
  }
}

// ── 单例 ──

export const db = new SishiYouxuDB()

// ── 辅助函数 ──

/** 打开数据库（应用启动时调用一次）。 */
export async function initDatabase(): Promise<void> {
  try {
    await db.open()
    console.log('[db] IndexedDB initialized')
  } catch (err) {
    console.error('[db] Failed to open IndexedDB:', err)
    throw err
  }
}

/** 生成 UUID v4（离线时的客户端兜底实现）。 */
export function generateUuid(): string {
  return crypto.randomUUID?.() ?? 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/** 返回 ISO 8601 格式的 UTC 时间戳字符串。 */
export function nowISO(): string {
  return new Date().toISOString()
}
