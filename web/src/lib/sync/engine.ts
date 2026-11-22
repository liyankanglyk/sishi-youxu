/**
 * SyncEngine —— 离线优先同步引擎（单例）
 *
 * 核心职责：
 * 1. 监听 Dexie pendingOps 队列，500ms debounce 批量推送
 * 2. 启动 / 网络恢复时拉取远端变更（since=lastPulledAt）
 * 3. 处理 push 返回值：applied 更新 syncStatus；conflict 入队 conflicts[]；rejected 标记失败
 * 4. 暴露 reactive<SyncState> 供 UI 订阅
 *
 * 安全保护：
 * - pull 时若本地有未同步修改，不直接覆盖，改为入冲突队列
 * - resolveConflict 用最新 local 重新入队
 * - pushAll 失败后指数退避，避免重试风暴
 *
 * 不依赖 Pinia（避免循环依赖），通过 useSync() 暴露只读状态。
 */

import { reactive, computed } from 'vue'
import { syncApi, type StatusResponse } from '@/api/sync'
import type {
  ConflictInfo,
  EntityType,
  PendingOpRecord,
  PullResponse,
  PushOpResult,
  SyncState,
} from './types'
import * as repo from './repository'

/** push 批量上限（与服务端契约对齐） */
const PUSH_BATCH_LIMIT = 100
/** debounce 间隔 */
const DEBOUNCE_MS = 500
/** 网络恢复后多久自动重试（ms） */
const RETRY_AFTER_ONLINE_MS = 800
/** 服务端时差缓存键 */
const SERVER_OFFSET_KEY = 'serverTimeOffsetMs'
/** 指数退避序列（ms）— 第 N 次失败后下次重试需等待 */
const BACKOFF_SEQUENCE_MS = [2000, 5000, 15000, 60000, 120000, 300000]
/** 同一 pull 失败最大重试次数（备用，保留以备后续 UI 显示） */
// const PULL_MAX_RETRY = 3

class SyncEngine {
  /** 全局响应式状态 */
  state: SyncState = reactive<SyncState>({
    status: 'idle',
    pendingCount: 0,
    conflicts: [],
    lastSyncedAt: null,
    lastError: null,
    isRunning: false,
    lastPulledAt: null,
  })

  private debounceTimer: ReturnType<typeof setTimeout> | null = null
  private onlineHandler: (() => void) | null = null
  private offlineHandler: (() => void) | null = null
  private started = false
  /** push 连续失败次数，用于指数退避 */
  private pushFailStreak = 0
  /** pull 连续失败次数 */
  private pullFailStreak = 0
  /** 下次允许同步的最早时间（用于 backoff） */
  private nextAllowedAt = 0

  // ===========================================================================
  // 公共 API
  // ===========================================================================

  /**
   * 安排一次同步（debounce 500ms）。
   * 多次调用会被合并为单次 push + pull。
   */
  schedule(): void {
    if (!this.started) return
    if (this.debounceTimer) clearTimeout(this.debounceTimer)
    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null
      void this.sync()
    }, DEBOUNCE_MS)
  }

  /** 立即触发一次完整同步（push + pull） */
  async sync(): Promise<void> {
    if (!this.started) return
    if (this.state.status === 'offline') {
      console.debug('[sync] offline, skip sync')
      return
    }
    // Backoff 期间跳过
    if (Date.now() < this.nextAllowedAt) {
      console.debug('[sync] in backoff until', new Date(this.nextAllowedAt).toISOString())
      return
    }
    if (this.state.isRunning) {
      console.debug('[sync] already running, defer')
      if (this.debounceTimer) clearTimeout(this.debounceTimer)
      this.debounceTimer = setTimeout(() => {
        this.debounceTimer = null
        void this.sync()
      }, DEBOUNCE_MS)
      return
    }
    this.state.isRunning = true
    this.state.status = 'syncing'
    let pushOk = true
    let pullOk = true
    try {
      try {
        await this.pushAll()
      } catch (e: any) {
        pushOk = false
        throw e
      }
      try {
        await this.pull()
      } catch (e: any) {
        pullOk = false
        throw e
      }
      this.state.lastSyncedAt = new Date().toISOString()
      this.state.lastError = null
      this.pushFailStreak = 0
      this.pullFailStreak = 0
      this.state.status = 'idle'
    } catch (e: any) {
      this.state.lastError = e?.message ?? String(e)
      this.state.status = 'error'
      // 指数退避
      const streak = pushOk ? this.pullFailStreak : this.pushFailStreak
      const idx = Math.min(streak, BACKOFF_SEQUENCE_MS.length - 1)
      this.nextAllowedAt = Date.now() + BACKOFF_SEQUENCE_MS[idx]
      if (!pushOk) this.pushFailStreak++
      if (!pullOk) this.pullFailStreak++
      console.warn('[sync] failed (backoff', BACKOFF_SEQUENCE_MS[idx], 'ms):', e)
    } finally {
      this.state.isRunning = false
      await this.refreshPendingCount()
    }
  }

  /** 强制拉取（忽略 since + backoff） */
  async forcePull(): Promise<void> {
    if (!this.started) return
    try {
      await this.pull(true)
      this.pullFailStreak = 0
    } catch (e: any) {
      this.state.lastError = e?.message ?? String(e)
      this.pullFailStreak++
    }
  }

  /** 解决冲突 */
  async resolveConflict(opId: string, choice: 'local' | 'remote'): Promise<void> {
    const idx = this.state.conflicts.findIndex((c) => c.opId === opId)
    if (idx < 0) return
    const conflict = this.state.conflicts[idx]

    if (choice === 'remote') {
      // 用服务端版本覆盖本地
      if (conflict.remote) {
        await this.applyServerRecord(conflict.entityType, conflict.remote, true)
      }
    } else {
      // 保留本地：删除原 conflict op，从 Dexie 读最新 local 重新入队
      const orig = await repo.getPendingOps()
      const found = orig.find((o) => o.opId === opId)
      if (found?.id != null) await repo.deleteOp(found.id)

      // ⚠️ 关键：重读 db 而不是用 conflict.local（可能是过期快照）
      const latest = await this.readLocalEntity(conflict.entityType, conflict.entityUuid)
      if (latest) {
        // force=true：用户已裁决为"保留本地"，服务端必须跳过版本冲突检测，
        // 否则重新入队的 op 每次推送都会被再次判冲突，形成死循环
        await repo.enqueueOp(
          conflict.entityType,
          'upsert',
          conflict.entityUuid,
          latest,
          { force: true },
        )
      }
    }

    // 从冲突队列移除
    this.state.conflicts.splice(idx, 1)
    this.schedule()
  }

  /** 启动引擎（鉴权恢复后调用） */
  async start(): Promise<void> {
    if (this.started) return
    this.started = true

    // 复位上一次会话遗留的 syncing op：页面被关闭或崩溃时 op 会停在 syncing，
    // 而取队列只认 pending|failed，这些 op 就永远推不出去
    await this.recoverStuckOps()

    // 初始状态
    await this.refreshPendingCount()
    const lastPulledAt = await repo.getSyncMeta('lastPulledAt')
    if (lastPulledAt) this.state.lastPulledAt = lastPulledAt

    // 网络监听
    this.onlineHandler = () => {
      console.log('[sync] online')
      this.state.status = 'idle'
      this.nextAllowedAt = 0
      setTimeout(() => void this.sync(), RETRY_AFTER_ONLINE_MS)
    }
    this.offlineHandler = () => {
      console.log('[sync] offline')
      this.state.status = 'offline'
    }
    window.addEventListener('online', this.onlineHandler)
    window.addEventListener('offline', this.offlineHandler)
    if (!navigator.onLine) this.state.status = 'offline'

    // 校时 + 首次拉取（独立 try/catch，失败仅记日志不阻塞）
    void this.bootstrapSync()
  }

  /** 启动期的校时与拉取，独立 try/catch */
  private async bootstrapSync(): Promise<void> {
    try {
      await this.calibrateTime()
    } catch (e) {
      console.warn('[sync] calibrateTime failed:', e)
      this.state.lastError = 'time calibration failed'
    }
    try {
      await this.pull()
    } catch (e: any) {
      console.warn('[sync] initial pull failed:', e)
      this.state.lastError = e?.message ?? String(e)
      // 不抛错，UI 仍可用
    }
  }

  /** 停止引擎（不清理数据，仅停止监听和定时器） */
  async stop(): Promise<void> {
    if (!this.started) return
    this.started = false
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer)
      this.debounceTimer = null
    }
    if (this.onlineHandler) {
      window.removeEventListener('online', this.onlineHandler)
      this.onlineHandler = null
    }
    if (this.offlineHandler) {
      window.removeEventListener('offline', this.offlineHandler)
      this.offlineHandler = null
    }
    this.state.status = 'idle'
  }

  /** 清空所有本地数据（登出 / 切换账号） */
  async clearLocal(): Promise<void> {
    await this.stop()
    await repo.clearAllLocalData()
    Object.assign(this.state, {
      status: 'idle',
      pendingCount: 0,
      conflicts: [],
      lastSyncedAt: null,
      lastError: null,
      isRunning: false,
      lastPulledAt: null,
    } satisfies SyncState)
    this.pushFailStreak = 0
    this.pullFailStreak = 0
    this.nextAllowedAt = 0
  }

  // ===========================================================================
  // 内部：push
  // ===========================================================================

  /** 把停在 syncing 的 op 复位成 pending（崩溃/刷新后恢复） */
  private async recoverStuckOps(): Promise<void> {
    const ops = await repo.getPendingOps()
    for (const op of ops) {
      if (op.status === 'syncing' && op.id != null) {
        await repo.updateOpStatus(op.id, 'pending')
      }
    }
  }

  private async pushAll(): Promise<void> {
    let ops = await repo.getPendingOps()
    ops = ops.filter((o) => o.status === 'pending' || o.status === 'failed')
    if (ops.length === 0) return

    // 分批（按 PUSH_BATCH_LIMIT 切）
    for (let i = 0; i < ops.length; i += PUSH_BATCH_LIMIT) {
      const batch = ops.slice(i, i + PUSH_BATCH_LIMIT)

      // 只把当前批标记为 syncing。
      // 早先把全部 op 一次性标成 syncing，某批失败后剩余批次永远停在 syncing：
      // 取队列只认 pending|failed、重启也没有复位逻辑，这些 op 就再也不会被推送。
      for (const op of batch) {
        if (op.id != null) {
          await repo.updateOpStatus(op.id, 'syncing')
        }
      }

      try {
        const resp = await syncApi.push(
          batch.map((o) => ({
            opId: o.opId,
            entity: o.entityType,
            action: o.opType,
            payload: o.payload,
            clientTs: new Date(o.createdAt).getTime(),
            // 用户已裁决为"保留本地"的 op：服务端跳过版本冲突检测
            force: o.force === true,
          })),
        )
        await this.handlePushResults(batch, resp.data.results ?? [])
      } catch (e: any) {
        // 整批失败：标记回 failed（失败批次可重试；未开始的批次保持 pending）
        for (const op of batch) {
          if (op.id != null) {
            await repo.updateOpStatus(op.id, 'failed', e?.message ?? String(e))
          }
        }
        throw e
      }
    }
  }

  private async handlePushResults(
    batch: PendingOpRecord[],
    results: PushOpResult[],
  ): Promise<void> {
    const resultMap = new Map(results.map((r) => [r.opId, r]))
    for (const op of batch) {
      const r = resultMap.get(op.opId)
      if (!r) {
        // 服务端没返回该 op（异常情况），标记为 failed
        if (op.id != null) {
          await repo.updateOpStatus(op.id, 'failed', 'no result from server')
        }
        continue
      }

      if (r.status === 'applied') {
        if (r.serverRecord) {
          await this.applyServerRecord(op.entityType, r.serverRecord, false)
        }
        if (op.id != null) await repo.deleteOp(op.id)
      } else if (r.status === 'conflict') {
        const local = await this.readLocalEntity(op.entityType, op.entityUuid)
        const remote = r.serverRecord ?? null
        const displayName =
          op.entityType === 'task'
            ? (remote?.title as string) ?? (local?.title as string) ?? '未命名任务'
            : op.entityType === 'tag'
              ? (remote?.name as string) ?? (local?.name as string) ?? '未命名标签'
              : op.entityType === 'checklistItems'
                ? (remote?.title as string) ?? '检查项'
                : op.entityUuid
        this.pushConflict({
          opId: op.opId,
          entityType: op.entityType,
          entityUuid: op.entityUuid,
          local,
          remote,
          opPayload: op.payload,
          displayName,
        })
        if (op.id != null) await repo.updateOpStatus(op.id, 'conflict', r.reason)
      } else {
        if (op.id != null) {
          await repo.updateOpStatus(op.id, 'failed', r.reason ?? 'rejected')
        }
      }
    }
  }

  // ===========================================================================
  // 内部：pull
  // ===========================================================================

  private async pull(force = false): Promise<void> {
    const since = force ? undefined : this.state.lastPulledAt ?? undefined
    const params: Record<string, string> = {}
    if (since) params.since = since
    const resp = await syncApi.pull(Object.keys(params).length ? params : undefined)
    await this.applyPull(resp.data)
    const serverAt = resp.data.serverAt ?? new Date().toISOString()
    this.state.lastPulledAt = serverAt
    await repo.setSyncMeta('lastPulledAt', serverAt)
  }

  private async applyPull(resp: PullResponse): Promise<void> {
    // tasks
    if (resp.tasks) {
      for (const t of resp.tasks.items ?? []) {
        await this.applyServerRecord('task', t, false)
      }
      for (const uuid of resp.tasks.deleted ?? []) {
        await repo.hardDeleteTask(uuid)
      }
    }
    // tags
    if (resp.tags) {
      for (const t of resp.tags.items ?? []) {
        await this.applyServerRecord('tag', t, false)
      }
    }
    // taskTags
    if (resp.taskTags) {
      for (const tt of resp.taskTags.items ?? []) {
        await repo.overwriteTaskTagFromServer(tt)
      }
    }
    // checklistItems
    if (resp.checklistItems) {
      for (const c of resp.checklistItems.items ?? []) {
        await this.applyServerRecord('checklistItems', c, false)
      }
    }
  }

  // ===========================================================================
  // 内部：辅助
  // ===========================================================================

  /**
   * 应用服务端记录到本地。
   * @param force true 表示用户已明确选择「使用服务端」，直接覆盖
   *              false 表示 pull 正常路径，需要保护本地未同步修改
   */
  private async applyServerRecord(
    entityType: EntityType,
    record: Record<string, unknown>,
    force: boolean,
  ): Promise<void> {
    const uuid = record.uuid as string | undefined
    if (!uuid) return

    // ⚠️ pending-guard：若本地有未同步修改，不直接覆盖，转入冲突队列
    if (!force) {
      const local = await this.readLocalEntity(entityType, uuid)
      if (local && local.syncStatus === 'pending') {
        const displayName =
          entityType === 'task'
            ? (record.title as string) ?? (local.title as string) ?? '未命名任务'
            : entityType === 'tag'
              ? (record.name as string) ?? (local.name as string) ?? '未命名标签'
              : entityType === 'checklistItems'
                ? (record.title as string) ?? '检查项'
                : uuid
        // 用服务端 opId 作为冲突标识
        this.pushConflict({
          opId: `pull-${uuid}-${Date.now()}`,
          entityType,
          entityUuid: uuid,
          local,
          remote: record,
          opPayload: {},
          displayName,
        })
        return
      }
    }

    switch (entityType) {
      case 'task':
        await repo.overwriteFromServer(record)
        break
      case 'tag':
        await repo.overwriteTagFromServer(record)
        break
      case 'checklistItems':
        await repo.overwriteChecklistFromServer(record)
        break
      case 'taskTag':
        await repo.overwriteTaskTagFromServer(
          record as unknown as { taskUuid: string; tagUuid: string },
        )
        break
    }
  }

  /**
   * 读本地实体，用于冲突判定与"保留本地"时取最新值。
   * 必须覆盖全部实体类型：之前只支持 task，tag / checklist 的 pending 保护形同虚设
   * （服务端会直接覆盖本地未同步的修改），选"保留本地"时 latest 为 null 也就不重新入队，
   * 本地改动直接丢失。taskTag 的 entityUuid 约定为 `${taskUuid}:${tagUuid}`。
   */
  private async readLocalEntity(
    entityType: EntityType,
    uuid: string,
  ): Promise<Record<string, unknown> | null> {
    if (entityType === 'task') {
      const t = await repo.getTask(uuid)
      return t ? ({ ...t } as Record<string, unknown>) : null
    }
    if (entityType === 'tag') {
      const t = await repo.getTag(uuid)
      return t ? ({ ...t } as Record<string, unknown>) : null
    }
    if (entityType === 'checklistItems') {
      const c = await repo.getChecklistItem(uuid)
      return c ? ({ ...c } as Record<string, unknown>) : null
    }
    if (entityType === 'taskTag') {
      const [taskUuid, tagUuid] = uuid.split(':')
      if (!taskUuid || !tagUuid) return null
      const link = await repo.getTaskTag(taskUuid, tagUuid)
      return link ? ({ ...link } as Record<string, unknown>) : null
    }
    return null
  }

  /** 冲突队列按实体去重：同一实体被反复 pull 时不会堆出多条同源冲突 */
  private pushConflict(conflict: ConflictInfo): void {
    const idx = this.state.conflicts.findIndex(
      (c) => c.entityType === conflict.entityType && c.entityUuid === conflict.entityUuid,
    )
    if (idx >= 0) this.state.conflicts.splice(idx, 1)
    this.state.conflicts.push(conflict)
  }

  private async refreshPendingCount(): Promise<void> {
    this.state.pendingCount = await repo.getPendingCount()
  }

  /** 校时：记录服务端时间与本地时间的差，用于后续 timestamp 换算 */
  private async calibrateTime(): Promise<void> {
    const resp = await syncApi.status()
    const data: StatusResponse = resp.data
    const serverMs = data.serverTimeMs
    const localMs = Date.now()
    const offset = serverMs - localMs
    await repo.setSyncMeta(SERVER_OFFSET_KEY, String(offset))
    // lastPulledAt 校准
    if (!this.state.lastPulledAt && data.serverAt) {
      this.state.lastPulledAt = data.serverAt
      await repo.setSyncMeta('lastPulledAt', data.serverAt)
    }
  }
}

/** 全局单例 */
export const syncEngine = new SyncEngine()

/** 派生：是否空闲且无冲突（用于 UI 显示"已同步"状态） */
export const isFullySynced = computed(
  () =>
    syncEngine.state.status === 'idle' &&
    syncEngine.state.pendingCount === 0 &&
    syncEngine.state.conflicts.length === 0,
)