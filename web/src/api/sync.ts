import apiClient from './index'

export interface SyncOp {
  opId: string
  entity: 'task' | 'tag' | 'taskTag' | 'checklistItems'
  action: 'upsert' | 'delete'
  payload: Record<string, unknown>
  clientTs: number
}

export const syncApi = {
  push(ops: SyncOp[]) {
    return apiClient.post('/sync/push', { ops })
  },

  pull(params?: { since?: string; entities?: string }) {
    return apiClient.get('/sync/pull', { params })
  },

  status() {
    return apiClient.get<{
      serverTime: string
      serverTimeMs: number
      timezone: string
    }>('/sync/status')
  },
}
