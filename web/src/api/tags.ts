import apiClient from './index'

export interface TagOut {
  uuid: string
  name: string
  color: string
  isPreset: boolean
  createdAt: string
  updatedAt: string
}

export const tagApi = {
  list() {
    return apiClient.get<{ items: TagOut[]; meta: any }>('/tags')
  },

  create(data: { name: string; color: string }) {
    return apiClient.post<TagOut>('/tags', data)
  },

  update(uuid: string, data: { name?: string; color?: string }) {
    return apiClient.patch<TagOut>(`/tags/${uuid}`, data)
  },

  delete(uuid: string) {
    return apiClient.delete(`/tags/${uuid}`)
  },
}
