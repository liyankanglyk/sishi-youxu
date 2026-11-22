/**
 * @fileoverview SyncEngine 单元测试 — 同步引擎核心逻辑。
 *
 * 重点覆盖（按业务关键度排序）：
 *  1. push 成功 → 清零退避状态 + status='idle'
 *  2. push 连续失败 → 触发指数退避 (nextAllowedAt)
 *  3. applyServerRecord 在本地 pending 时 → 入冲突队列（pending-guard）
 *  4. resolveConflict('local') → 重新读最新 local（不是过期快照）
 *  5. resolveConflict('remote') → 用服务端覆盖本地
 *  6. forcePull → 忽略 since 和 backoff
 *  7. status 状态机：idle → syncing → idle / error
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'

// ---------------------------------------------------------------------------
// Mocks — 必须在 import engine 之前
// ---------------------------------------------------------------------------

const mockPush = vi.fn()
const mockPull = vi.fn()
const mockStatus = vi.fn()

vi.mock('@/api/sync', () => ({
  syncApi: {
    push: (...args: unknown[]) => mockPush(...args),
    pull: (...args: unknown[]) => mockPull(...args),
    status: (...args: unknown[]) => mockStatus(...args),
  },
}))

const mockGetPendingOps = vi.fn()
const mockUpdateOpStatus = vi.fn()
const mockDeleteOp = vi.fn()
const mockGetTask = vi.fn()
const mockGetTag = vi.fn()
const mockGetChecklistItem = vi.fn()
const mockGetTaskTag = vi.fn()
const mockOverwriteFromServer = vi.fn()
const mockOverwriteTagFromServer = vi.fn()
const mockOverwriteChecklistFromServer = vi.fn()
const mockOverwriteTaskTagFromServer = vi.fn()
const mockHardDeleteTask = vi.fn()
const mockGetPendingCount = vi.fn()
const mockEnqueueOp = vi.fn()
const mockGetSyncMeta = vi.fn()
const mockSetSyncMeta = vi.fn()
const mockClearAllLocalData = vi.fn()

vi.mock('../repository', () => ({
  getPendingOps: (...args: unknown[]) => mockGetPendingOps(...args),
  updateOpStatus: (...args: unknown[]) => mockUpdateOpStatus(...args),
  deleteOp: (...args: unknown[]) => mockDeleteOp(...args),
  getTask: (...args: unknown[]) => mockGetTask(...args),
  getTag: (...args: unknown[]) => mockGetTag(...args),
  getChecklistItem: (...args: unknown[]) => mockGetChecklistItem(...args),
  getTaskTag: (...args: unknown[]) => mockGetTaskTag(...args),
  overwriteFromServer: (...args: unknown[]) => mockOverwriteFromServer(...args),
  overwriteTagFromServer: (...args: unknown[]) => mockOverwriteTagFromServer(...args),
  overwriteChecklistFromServer: (...args: unknown[]) => mockOverwriteChecklistFromServer(...args),
  overwriteTaskTagFromServer: (...args: unknown[]) => mockOverwriteTaskTagFromServer(...args),
  hardDeleteTask: (...args: unknown[]) => mockHardDeleteTask(...args),
  getPendingCount: (...args: unknown[]) => mockGetPendingCount(...args),
  enqueueOp: (...args: unknown[]) => mockEnqueueOp(...args),
  getSyncMeta: (...args: unknown[]) => mockGetSyncMeta(...args),
  setSyncMeta: (...args: unknown[]) => mockSetSyncMeta(...args),
  clearAllLocalData: (...args: unknown[]) => mockClearAllLocalData(...args),
}))

// 现在才能 import engine（其依赖已被 mock）
import { syncEngine } from '../engine'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** 重置 singleton 私有状态，让每个测试从干净起点开始 */
function resetEngine() {
  const e = syncEngine as any
  e.started = false
  e.debounceTimer = null
  e.pushFailStreak = 0
  e.pullFailStreak = 0
  e.nextAllowedAt = 0
  Object.assign(syncEngine.state, {
    status: 'idle',
    pendingCount: 0,
    conflicts: [],
    lastSyncedAt: null,
    lastError: null,
    isRunning: false,
    lastPulledAt: null,
  })
  // 移除事件监听（start 会重新加）
  if (e.onlineHandler) window.removeEventListener('online', e.onlineHandler)
  if (e.offlineHandler) window.removeEventListener('offline', e.offlineHandler)
  e.onlineHandler = null
  e.offlineHandler = null
}

beforeEach(() => {
  vi.clearAllMocks()
  resetEngine()
})

afterEach(() => {
  vi.useRealTimers()
})

// ---------------------------------------------------------------------------
// 1. schedule() — debounce 500ms
// ---------------------------------------------------------------------------
describe('syncEngine.schedule', () => {
  it('500ms 后触发 sync()', async () => {
    vi.useFakeTimers()
    mockGetPendingOps.mockResolvedValue([])
    mockGetPendingCount.mockResolvedValue(0)
    mockStatus.mockResolvedValue({ data: { serverAt: '2024-01-01', serverTimeMs: 0, timezone: 'UTC' } })
    mockPull.mockResolvedValue({ data: { serverAt: '2024-01-01' } })
    ;(syncEngine as any).started = true

    syncEngine.schedule()
    // 500ms 之内不应触发 sync
    expect(mockGetPendingOps).not.toHaveBeenCalled()
    vi.advanceTimersByTime(500)
    // 等 microtask
    await vi.runAllTimersAsync()
    expect(mockGetPendingOps).toHaveBeenCalled()
  })

  it('多次调用合并为一次 sync', async () => {
    vi.useFakeTimers()
    mockGetPendingOps.mockResolvedValue([])
    mockGetPendingCount.mockResolvedValue(0)
    mockStatus.mockResolvedValue({ data: { serverAt: 'x', serverTimeMs: 0, timezone: 'UTC' } })
    mockPull.mockResolvedValue({ data: { serverAt: 'x' } })
    ;(syncEngine as any).started = true

    syncEngine.schedule()
    syncEngine.schedule()
    syncEngine.schedule()
    vi.advanceTimersByTime(500)
    await vi.runAllTimersAsync()
    // 多次 schedule 只触发 1 次 sync（即 1 次 pull）
    expect(mockPull).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// 2. sync() — push 成功路径 + 状态机
// ---------------------------------------------------------------------------
describe('syncEngine.sync (happy path)', () => {
  beforeEach(() => {
    ;(syncEngine as any).started = true
  })

  it('无 pending ops 时跳过 push', async () => {
    mockGetPendingOps.mockResolvedValue([])
    mockPull.mockResolvedValue({ data: { serverAt: 'x' } })
    await syncEngine.sync()
    expect(mockPush).not.toHaveBeenCalled()
    expect(mockPull).toHaveBeenCalledTimes(1)
    expect(syncEngine.state.status).toBe('idle')
    expect(syncEngine.state.lastError).toBeNull()
  })

  it('push 成功后 status=idle 且 lastSyncedAt 更新', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 1, opId: 'op1', entityType: 'task', opType: 'upsert', entityUuid: 'u1',
        payload: {}, createdAt: Date.now(), status: 'pending' },
    ])
    mockPush.mockResolvedValue({
      data: {
        results: [{ opId: 'op1', status: 'applied', serverRecord: { uuid: 'u1', title: 'A' } }],
        serverTime: '2024-01-01',
      },
    })
    mockGetTask.mockResolvedValue(null)
    mockOverwriteFromServer.mockResolvedValue(undefined)
    mockDeleteOp.mockResolvedValue(undefined)
    mockPull.mockResolvedValue({ data: { serverAt: 'x' } })
    mockGetPendingCount.mockResolvedValue(0)

    const before = syncEngine.state.lastSyncedAt
    await syncEngine.sync()
    expect(syncEngine.state.status).toBe('idle')
    expect(syncEngine.state.lastSyncedAt).not.toBe(before)
    expect(syncEngine.state.lastError).toBeNull()
    expect((syncEngine as any).pushFailStreak).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// 3. sync() — push 失败 → 指数退避
// ---------------------------------------------------------------------------
describe('syncEngine.sync (backoff)', () => {
  beforeEach(() => {
    ;(syncEngine as any).started = true
  })

  it('push 失败 → nextAllowedAt 设置到 2s 后', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 1, opId: 'op1', entityType: 'task', opType: 'upsert', entityUuid: 'u1',
        payload: {}, createdAt: Date.now(), status: 'pending' },
    ])
    mockPush.mockRejectedValue(new Error('network down'))
    mockUpdateOpStatus.mockResolvedValue(undefined)
    mockGetPendingCount.mockResolvedValue(0)

    const t0 = Date.now()
    await syncEngine.sync()
    expect(syncEngine.state.status).toBe('error')
    expect(syncEngine.state.lastError).toContain('network down')
    const next = (syncEngine as any).nextAllowedAt as number
    expect(next).toBeGreaterThan(t0)
    // 第一次失败：退避序列 [2000, 5000, ...] → 至少 2000ms
    expect(next - t0).toBeGreaterThanOrEqual(1900)
  })

  it('backoff 期内 sync() 被跳过', async () => {
    ;(syncEngine as any).nextAllowedAt = Date.now() + 60_000
    await syncEngine.sync()
    expect(mockPush).not.toHaveBeenCalled()
    expect(mockPull).not.toHaveBeenCalled()
  })

  it('连续失败退避序列递增', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 1, opId: 'op1', entityType: 'task', opType: 'upsert', entityUuid: 'u1',
        payload: {}, createdAt: Date.now(), status: 'pending' },
    ])
    mockPush.mockRejectedValue(new Error('fail'))
    mockUpdateOpStatus.mockResolvedValue(undefined)
    mockGetPendingCount.mockResolvedValue(0)

    // 第 1 次失败：~2s
    await syncEngine.sync()
    const s1 = (syncEngine as any).nextAllowedAt - Date.now()
    ;(syncEngine as any).nextAllowedAt = 0  // 解除 backoff 以便下次能跑

    // 第 2 次失败：~5s
    await syncEngine.sync()
    const s2 = (syncEngine as any).nextAllowedAt - Date.now()
    expect(s2).toBeGreaterThan(s1)
  })
})

// ---------------------------------------------------------------------------
// 4. pending-guard — pull 时本地有未同步修改 → 入冲突队列
// ---------------------------------------------------------------------------
describe('applyServerRecord pending-guard', () => {
  beforeEach(() => {
    ;(syncEngine as any).started = true
  })

  it('pull 路径下，本地 syncStatus=pending 时 → 入 conflicts，不覆盖', async () => {
    const local = { uuid: 'u1', title: 'local-edit', syncStatus: 'pending' }
    mockGetPendingOps.mockResolvedValue([])
    mockGetTask.mockResolvedValue(local)
    mockPull.mockResolvedValue({
      data: {
        tasks: { items: [{ uuid: 'u1', title: 'remote-edit', updatedAt: 'x' }], deleted: [] },
        serverAt: '2024-01-01',
      },
    })
    mockGetPendingCount.mockResolvedValue(0)

    await syncEngine.sync()
    expect(syncEngine.state.conflicts.length).toBe(1)
    expect(syncEngine.state.conflicts[0].entityUuid).toBe('u1')
    expect(syncEngine.state.conflicts[0].local).toEqual(local)
    // 不应直接覆盖
    expect(mockOverwriteFromServer).not.toHaveBeenCalled()
  })

  it('pull 路径下，本地 syncStatus=synced → 直接覆盖', async () => {
    mockGetPendingOps.mockResolvedValue([])
    mockGetTask.mockResolvedValue({ uuid: 'u1', title: 'local', syncStatus: 'synced' })
    mockOverwriteFromServer.mockResolvedValue(undefined)
    mockPull.mockResolvedValue({
      data: {
        tasks: { items: [{ uuid: 'u1', title: 'remote', updatedAt: 'x' }], deleted: [] },
        serverAt: '2024-01-01',
      },
    })
    mockGetPendingCount.mockResolvedValue(0)

    await syncEngine.sync()
    expect(syncEngine.state.conflicts.length).toBe(0)
    expect(mockOverwriteFromServer).toHaveBeenCalledWith(
      expect.objectContaining({ uuid: 'u1', title: 'remote' }),
    )
  })
})

// ---------------------------------------------------------------------------
// 5. resolveConflict — local 重新读最新；remote 直接覆盖
// ---------------------------------------------------------------------------
describe('resolveConflict', () => {
  beforeEach(() => {
    ;(syncEngine as any).started = true
  })

  it('choice=remote → 用服务端记录直接覆盖本地', async () => {
    syncEngine.state.conflicts.push({
      opId: 'op1',
      entityType: 'task',
      entityUuid: 'u1',
      local: { uuid: 'u1', title: 'local' },
      remote: { uuid: 'u1', title: 'remote' },
      opPayload: {},
      displayName: 'remote',
    })
    mockOverwriteFromServer.mockResolvedValue(undefined)

    await syncEngine.resolveConflict('op1', 'remote')
    expect(mockOverwriteFromServer).toHaveBeenCalledWith(
      expect.objectContaining({ uuid: 'u1', title: 'remote' }),
    )
    expect(syncEngine.state.conflicts.length).toBe(0)
  })

  it('choice=local → 重新读最新 local（不是 conflict.local 快照）', async () => {
    syncEngine.state.conflicts.push({
      opId: 'op1',
      entityType: 'task',
      entityUuid: 'u1',
      local: { uuid: 'u1', title: 'stale-snapshot' },  // 过期快照
      remote: { uuid: 'u1', title: 'remote' },
      opPayload: {},
      displayName: 'task',
    })
    // Dexie 中返回的"最新"本地版本
    mockGetPendingOps.mockResolvedValue([])
    mockGetTask.mockResolvedValue({ uuid: 'u1', title: 'freshest-local' })
    mockEnqueueOp.mockResolvedValue(undefined)
    mockDeleteOp.mockResolvedValue(undefined)

    await syncEngine.resolveConflict('op1', 'local')
    // 入队的应是 freshest-local，而不是 conflict.local
    expect(mockEnqueueOp).toHaveBeenCalledWith(
      'task',
      'upsert',
      'u1',
      expect.objectContaining({ title: 'freshest-local' }),
      // force=true：用户已裁决"保留本地"，服务端据此跳过冲突检测，
      // 否则这个 op 每次推送都会被再次判冲突
      { force: true },
    )
    // 关键断言：传入的 payload 不是 stale-snapshot
    const call = mockEnqueueOp.mock.calls[0]
    expect(call[3].title).not.toBe('stale-snapshot')
    expect(syncEngine.state.conflicts.length).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// 6. forcePull — 忽略 backoff
// ---------------------------------------------------------------------------
describe('forcePull', () => {
  beforeEach(() => {
    ;(syncEngine as any).started = true
  })

  it('即使在 backoff 期内也强制拉取', async () => {
    ;(syncEngine as any).nextAllowedAt = Date.now() + 60_000
    mockPull.mockResolvedValue({ data: { serverAt: 'now' } })

    await syncEngine.forcePull()
    expect(mockPull).toHaveBeenCalledWith(undefined)  // force=true → since=undefined
    expect(syncEngine.state.lastPulledAt).toBe('now')
  })

  it('pull 失败时记录 lastError 但不抛出', async () => {
    mockPull.mockRejectedValue(new Error('pull-failed'))

    await expect(syncEngine.forcePull()).resolves.not.toThrow()
    expect(syncEngine.state.lastError).toContain('pull-failed')
    expect((syncEngine as any).pullFailStreak).toBe(1)
  })
})

// ---------------------------------------------------------------------------
// 7. pushAll — handlePushResults: applied/conflict/rejected 分支
// ---------------------------------------------------------------------------
describe('pushAll result handling', () => {
  beforeEach(() => {
    ;(syncEngine as any).started = true
  })

  it('status=applied → 删除 op + 写 serverRecord', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 1, opId: 'op1', entityType: 'task', opType: 'upsert', entityUuid: 'u1',
        payload: {}, createdAt: Date.now(), status: 'pending' },
    ])
    mockPush.mockResolvedValue({
      data: {
        results: [{
          opId: 'op1', status: 'applied',
          serverRecord: { uuid: 'u1', title: 'new' },
        }],
      },
    })
    mockGetTask.mockResolvedValue(null)
    mockOverwriteFromServer.mockResolvedValue(undefined)
    mockDeleteOp.mockResolvedValue(undefined)
    mockPull.mockResolvedValue({ data: { serverAt: 'x' } })
    mockGetPendingCount.mockResolvedValue(0)

    await syncEngine.sync()
    expect(mockDeleteOp).toHaveBeenCalledWith(1)
    expect(mockOverwriteFromServer).toHaveBeenCalled()
  })

  it('status=conflict → 入 conflicts 队列 + op 标 conflict', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 1, opId: 'op1', entityType: 'task', opType: 'upsert', entityUuid: 'u1',
        payload: { title: 'local-conflict' }, createdAt: Date.now(), status: 'pending' },
    ])
    mockPush.mockResolvedValue({
      data: {
        results: [{
          opId: 'op1', status: 'conflict', reason: 'server-newer',
          serverRecord: { uuid: 'u1', title: 'server-newer' },
        }],
      },
    })
    mockGetTask.mockResolvedValue({ uuid: 'u1', title: 'local-conflict' })
    mockUpdateOpStatus.mockResolvedValue(undefined)
    mockPull.mockResolvedValue({ data: { serverAt: 'x' } })
    mockGetPendingCount.mockResolvedValue(0)

    await syncEngine.sync()
    expect(syncEngine.state.conflicts.length).toBe(1)
    expect(syncEngine.state.conflicts[0].opId).toBe('op1')
    expect(mockUpdateOpStatus).toHaveBeenCalledWith(1, 'conflict', expect.any(String))
  })

  it('status=rejected → op 标 failed 带 reason', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 1, opId: 'op1', entityType: 'task', opType: 'upsert', entityUuid: 'u1',
        payload: {}, createdAt: Date.now(), status: 'pending' },
    ])
    mockPush.mockResolvedValue({
      data: {
        results: [{ opId: 'op1', status: 'rejected', reason: 'permission-denied' }],
      },
    })
    mockUpdateOpStatus.mockResolvedValue(undefined)
    mockPull.mockResolvedValue({ data: { serverAt: 'x' } })
    mockGetPendingCount.mockResolvedValue(0)

    await syncEngine.sync()
    expect(mockUpdateOpStatus).toHaveBeenCalledWith(1, 'failed', 'permission-denied')
    expect(syncEngine.state.conflicts.length).toBe(0)
  })
})