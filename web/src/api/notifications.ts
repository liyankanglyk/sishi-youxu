import apiClient from './index'

export interface NotificationOut {
  uuid: string
  kind: string
  title: string
  body: string
  taskUuid: string | null
  isRead: boolean
  createdAt: string
}

export const notificationApi = {
  list(params?: { isRead?: boolean; page?: number; pageSize?: number }) {
    return apiClient.get('/notifications', { params })
  },

  unreadCount() {
    return apiClient.get('/notifications/unread-count')
  },

  markRead(uuid: string) {
    return apiClient.patch(`/notifications/${uuid}/read`)
  },

  markAllRead() {
    return apiClient.post('/notifications/read-all')
  },

  delete(uuid: string) {
    return apiClient.delete(`/notifications/${uuid}`)
  },
}
