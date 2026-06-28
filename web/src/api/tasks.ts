import apiClient from './index'

export interface TaskCreatePayload {
  title: string
  urgencyLevel?: number
  importanceLevel?: number
  dueDate?: string | null
  recurrence?: string | null
  note?: string | null
  tags?: string[]
  remindAt?: string | null
  remindOffsetMinutes?: number | null
  sortOrder?: number
}

export interface TaskUpdatePayload {
  title?: string
  urgencyLevel?: number
  importanceLevel?: number
  dueDate?: string | null
  recurrence?: string | null
  note?: string | null
  tags?: string[]
  remindAt?: string | null
  remindOffsetMinutes?: number | null
  completed?: boolean
  completedAt?: string | null
  sortOrder?: number
}

export interface TaskOut {
  uuid: string
  title: string
  urgencyLevel: number
  importanceLevel: number
  dueDate: string | null
  recurrence: string | null
  note: string | null
  tags: string[] | { uuid: string; name: string; color: string }[]
  checklistTotal: number
  checklistCompleted: number
  completed: boolean
  completedAt: string | null
  sortOrder: number
  createdAt: string
  updatedAt: string
}

export interface ChecklistItem {
  uuid: string
  title: string
  completed: boolean
  sortOrder: number
  createdAt: string
  updatedAt: string
}

export interface PaginatedResponse<T> {
  items: T[]
  meta: { total: number; page: number; pageSize: number; hasMore: boolean }
}

export const taskApi = {
  list(params?: {
    since?: string
    completed?: boolean
    q?: string
    page?: number
    pageSize?: number
  }) {
    return apiClient.get<PaginatedResponse<TaskOut>>('/tasks', { params })
  },

  create(data: TaskCreatePayload) {
    return apiClient.post<TaskOut>('/tasks', data)
  },

  get(uuid: string) {
    return apiClient.get<TaskOut>(`/tasks/${uuid}`)
  },

  update(uuid: string, data: TaskUpdatePayload) {
    return apiClient.patch<TaskOut>(`/tasks/${uuid}`, data)
  },

  delete(uuid: string) {
    return apiClient.delete(`/tasks/${uuid}`)
  },

  restore(uuid: string) {
    return apiClient.post(`/tasks/${uuid}/restore`)
  },

  batch(data: { idempotencyKey: string; action: string; taskUuids: string[]; quadrant?: number }) {
    return apiClient.post('/tasks/batch', data)
  },

  // ── Checklist ──
  listChecklist(taskUuid: string) {
    return apiClient.get<PaginatedResponse<ChecklistItem>>(`/tasks/${taskUuid}/checklist`)
  },

  createChecklistItem(taskUuid: string, data: { title: string; sortOrder?: number }) {
    return apiClient.post<ChecklistItem>(`/tasks/${taskUuid}/checklist`, data)
  },

  updateChecklistItem(taskUuid: string, itemUuid: string, data: Partial<ChecklistItem>) {
    return apiClient.patch<ChecklistItem>(`/tasks/${taskUuid}/checklist/${itemUuid}`, data)
  },

  deleteChecklistItem(taskUuid: string, itemUuid: string) {
    return apiClient.delete(`/tasks/${taskUuid}/checklist/${itemUuid}`)
  },
}