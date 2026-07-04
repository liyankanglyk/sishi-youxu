/**
 * 同步模块对外暴露
 */

import { computed } from 'vue'
import { syncEngine, isFullySynced } from './engine'

export function useSync() {
  return {
    /** 响应式同步状态 */
    state: syncEngine.state,
    /** 是否完全同步（空闲 + 无 pending + 无冲突） */
    isFullySynced,
    /** 派生：是否有冲突 */
    hasConflicts: computed(() => syncEngine.state.conflicts.length > 0),
    /** 派生：是否有待同步项 */
    hasPending: computed(() => syncEngine.state.pendingCount > 0),
    /** 安排一次同步（500ms debounce） */
    schedule: () => syncEngine.schedule(),
    /** 立即完整同步 */
    syncNow: () => syncEngine.sync(),
    /** 强制拉取（忽略 since） */
    forcePull: () => syncEngine.forcePull(),
    /** 启动 / 停止 / 清空 */
    start: () => syncEngine.start(),
    stop: () => syncEngine.stop(),
    clearLocal: () => syncEngine.clearLocal(),
    /** 解决冲突 */
    resolveConflict: (opId: string, choice: 'local' | 'remote') =>
      syncEngine.resolveConflict(opId, choice),
  }
}

export { syncEngine } from './engine'
export type { SyncState, ConflictInfo, SyncStatus } from './types'