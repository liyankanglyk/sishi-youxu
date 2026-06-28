import apiClient from './index'

export const feedbackApi = {
  submit(content: string, contact?: string) {
    return apiClient.post('/feedback', { content, contact })
  },

  list(params?: { page?: number; pageSize?: number }) {
    return apiClient.get('/feedback', { params })
  },
}
