import apiClient from './index'

export interface SyncOp {
  opId: string
  entity: 'task' | 'tag' | 'taskTag' | 'checklistItems'
  action: 'upsert' | 'delete'
  payload: Record<string, unknown>
  clientTs: number
}

export interface PushOpResult {
  opId: string
  status: 'applied' | 'conflict' | 'rejected'
  serverRecord?: Record<string, unknown>
  reason?: string
  serverTime: string
}

export interface PushResponse {
  results: PushOpResult[]
  serverTime: string
}

export interface PullResponse {
  tasks?: {
    items: Array<Record<string, unknown>>
    deleted: string[]
  }
  tags?: { items: Array<Record<string, unknown>> }
  taskTags?: { items: Array<{ taskUuid: string; tagUuid: string }> }
  checklistItems?: { items: Array<Record<string, unknown>> }
  serverAt: string
}

export interface StatusResponse {
  serverAt: string
  serverTimeMs: number
  timezone: string
}

export const syncApi = {
  push(ops: SyncOp[]) {
    return apiClient.post<PushResponse, { data: PushResponse }>('/sync/push', { ops }) as unknown as Promise<{ data: PushResponse }>
  },

  pull(params?: { since?: string; entities?: string }) {
    return apiClient.get<PullResponse, { data: PullResponse }>('/sync/pull', { params }) as unknown as Promise<{ data: PullResponse }>
  },

  status() {
    return apiClient.get<StatusResponse, { data: StatusResponse }>('/sync/status') as unknown as Promise<{ data: StatusResponse }>
  },
}