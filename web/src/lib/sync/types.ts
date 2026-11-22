/**
 * 同步引擎类型定义
 *
 * 与 docs/03-技术架构/同步协议.md 完全对齐。
 */
import type { PendingOp as PendingOpBase } from '@/db'

export type SyncStatus = 'idle' | 'syncing' | 'offline' | 'error'

export type EntityType = 'task' | 'tag' | 'taskTag' | 'checklistItems'

export type OpType = 'upsert' | 'delete' | 'restore'

/** 入队时的 op（包含排队状态） —— 与 IndexedDB 行结构完全一致 */
export type PendingOpRecord = PendingOpBase

/** 后端 push 单条 op 的返回 */
export interface PushOpResult {
  opId: string
  status: 'applied' | 'conflict' | 'rejected'
  serverRecord?: Record<string, unknown>
  reason?: string
  serverTime: string
}

/** push 端点响应 */
export interface PushResponse {
  results: PushOpResult[]
  serverTime: string
}

/** pull 端点响应 */
export interface PullResponse {
  tasks?: {
    items: Array<Record<string, unknown>>
    deleted: string[]
  }
  tags?: {
    items: Array<Record<string, unknown>>
  }
  taskTags?: {
    items: Array<{ taskUuid: string; tagUuid: string }>
  }
  checklistItems?: {
    items: Array<Record<string, unknown>>
  }
  serverAt: string
}

/** status 端点响应 */
export interface StatusResponse {
  serverAt: string
  serverTimeMs: number
  timezone: string
}

/** 冲突信息（弹窗用） */
export interface ConflictInfo {
  opId: string
  entityType: EntityType
  entityUuid: string
  /** 本地当前版本（db.tasks.find(uuid)） */
  local: Record<string, unknown> | null
  /** 服务端版本（push 返回的 serverRecord） */
  remote: Record<string, unknown> | null
  /** 触发冲突的操作 payload */
  opPayload: Record<string, unknown>
  /** 实体人类可读名（任务标题等），用于 UI */
  displayName: string
}

/** 同步引擎全局状态 */
export interface SyncState {
  status: SyncStatus
  /** Dexie 待同步 op 数 */
  pendingCount: number
  /** 当前冲突列表（弹窗渲染用） */
  conflicts: ConflictInfo[]
  /** 最近一次同步完成时间（ISO） */
  lastSyncedAt: string | null
  /** 最近一次错误 */
  lastError: string | null
  /** 是否正在执行 push/pull */
  isRunning: boolean
  /** 上次拉取时间（用于下次 since 参数） */
  lastPulledAt: string | null
}