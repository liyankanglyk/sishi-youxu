/**
 * @fileoverview SyncEngine 回归测试 —— 三类会导致"数据推不出去 / 丢本地"的缺陷。
 *
 *  1. 批次失败后剩余批次永久停在 syncing
 *     （旧实现一次性把所有 op 标成 syncing，第 2 批失败后第 3 批再也推不出去）
 *  2. start() 不复位上次会话遗留的 syncing op（刷新/崩溃后卡死）
 *  3. readLocalEntity 只支持 task
 *     → tag / checklist 的本地未同步修改会被服务端静默覆盖；选"保留本地"时也不重新入队
 *  4. 冲突队列按实体去重（同一实体反复 pull 会堆出多条同源冲突）
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

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

import { syncEngine } from '../engine'

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
}

beforeEach(() => {
  vi.clearAllMocks()
  resetEngine()
  mockGetPendingOps.mockResolvedValue([])
  mockGetSyncMeta.mockResolvedValue(null)
  mockStatus.mockResolvedValue({
    data: { serverTimeMs: Date.now(), serverAt: new Date().toISOString() },
  })
  mockPull.mockResolvedValue({ data: { serverAt: new Date().toISOString() } })
  mockGetPendingCount.mockResolvedValue(0)
})

function makeOps(count: number, status = 'pending'): Array<{
  id: number
  opId: string
  entityType: 'task'
  opType: 'upsert'
  entityUuid: string
  payload: Record<string, unknown>
  createdAt: string
  status: string
  force?: boolean
}> {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    opId: `op${i + 1}`,
    entityType: 'task' as const,
    opType: 'upsert' as const,
    entityUuid: `u${i + 1}`,
    payload: {},
    createdAt: new Date().toISOString(),
    status,
  }))
}

// ---------------------------------------------------------------------------
// 1. 批次失败后剩余批次不能停在 syncing
// ---------------------------------------------------------------------------

describe('pushAll 批次失败', () => {
  it('第 2 批失败时，第 3 批的 op 不应被标成 syncing', async () => {
    // 250 条 op = 3 批（每批 100）
    mockGetPendingOps.mockResolvedValue(makeOps(250))
    // 第 1 批成功，第 2 批网络失败
    mockPush
      .mockResolvedValueOnce({ data: { results: [] } })
      .mockRejectedValueOnce(new Error('network down'))

    await expect((syncEngine as any).pushAll()).rejects.toThrow('network down')

    const syncingIds = mockUpdateOpStatus.mock.calls
      .filter((c) => c[1] === 'syncing')
      .map((c) => c[0])

    // 旧实现：一次性把 250 条全标 syncing，第 3 批（201~250）永远卡住
    expect(syncingIds.some((id: number) => id > 200)).toBe(false)

    // 失败的那一批要退回 failed（可重试）
    const failedIds = mockUpdateOpStatus.mock.calls
      .filter((c) => c[1] === 'failed')
      .map((c) => c[0])
    expect(failedIds.some((id: number) => id > 100 && id <= 200)).toBe(true)
  })

  it('推送时带上 force 标记（用户裁决为保留本地的 op）', async () => {
    const ops = makeOps(1)
    ops[0].force = true
    mockGetPendingOps.mockResolvedValue(ops)
    mockPush.mockResolvedValue({ data: { results: [] } })

    await (syncEngine as any).pushAll()

    expect(mockPush).toHaveBeenCalled()
    const sent = mockPush.mock.calls[0][0]
    expect(sent[0].force).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// 2. start() 复位遗留的 syncing op
// ---------------------------------------------------------------------------

describe('start 恢复', () => {
  it('把上次会话遗留的 syncing op 复位为 pending', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 1, opId: 'op1', entityType: 'task', opType: 'upsert', entityUuid: 'u1', payload: {}, createdAt: '', status: 'syncing' },
      { id: 2, opId: 'op2', entityType: 'task', opType: 'upsert', entityUuid: 'u2', payload: {}, createdAt: '', status: 'pending' },
    ])

    await syncEngine.start()

    expect(mockUpdateOpStatus).toHaveBeenCalledWith(1, 'pending')
    expect(mockUpdateOpStatus).not.toHaveBeenCalledWith(2, 'pending')
  })
})

// ---------------------------------------------------------------------------
// 3. readLocalEntity 必须覆盖全部实体类型
// ---------------------------------------------------------------------------

describe('readLocalEntity', () => {
  it('tag 也能读到本地记录', async () => {
    mockGetTag.mockResolvedValue({ uuid: 't1', name: '工作' })
    const local = await (syncEngine as any).readLocalEntity('tag', 't1')
    expect(local).toEqual({ uuid: 't1', name: '工作' })
  })

  it('checklistItems 也能读到本地记录', async () => {
    mockGetChecklistItem.mockResolvedValue({ uuid: 'c1', title: '第一步' })
    const local = await (syncEngine as any).readLocalEntity('checklistItems', 'c1')
    expect(local).toEqual({ uuid: 'c1', title: '第一步' })
  })

  it('taskTag 按 taskUuid:tagUuid 复合键读取', async () => {
    mockGetTaskTag.mockResolvedValue({ taskUuid: 't1', tagUuid: 'g1' })
    const local = await (syncEngine as any).readLocalEntity('taskTag', 't1:g1')
    expect(mockGetTaskTag).toHaveBeenCalledWith('t1', 'g1')
    expect(local).toEqual({ taskUuid: 't1', tagUuid: 'g1' })
  })
})

// ---------------------------------------------------------------------------
// 4. 冲突队列按实体去重
// ---------------------------------------------------------------------------

describe('冲突去重', () => {
  it('同一实体重复冲突只保留一条', () => {
    const e = syncEngine as any
    e.pushConflict({
      opId: 'c1', entityType: 'task', entityUuid: 'u1',
      local: null, remote: null, opPayload: {}, displayName: 'A',
    })
    e.pushConflict({
      opId: 'c2', entityType: 'task', entityUuid: 'u1',
      local: null, remote: null, opPayload: {}, displayName: 'A',
    })
    expect(syncEngine.state.conflicts.length).toBe(1)
    expect(syncEngine.state.conflicts[0].opId).toBe('c2')
  })

  it('不同实体各自保留一条', () => {
    const e = syncEngine as any
    e.pushConflict({
      opId: 'c1', entityType: 'task', entityUuid: 'u1',
      local: null, remote: null, opPayload: {}, displayName: 'A',
    })
    e.pushConflict({
      opId: 'c2', entityType: 'task', entityUuid: 'u2',
      local: null, remote: null, opPayload: {}, displayName: 'B',
    })
    expect(syncEngine.state.conflicts.length).toBe(2)
  })
})
