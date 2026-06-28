import axios from 'axios'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor: inject Bearer token ──
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: unwrap {success,data} / handle 401 refresh ──
let isRefreshing = false
let refreshQueue: Array<{
  resolve: (token: string) => void
  reject: (err: unknown) => void
}> = []

function queueRefresh(token: string) {
  refreshQueue.forEach((p) => p.resolve(token))
  refreshQueue = []
}

function rejectRefresh(err: unknown) {
  refreshQueue.forEach((p) => p.reject(err))
  refreshQueue = []
}

apiClient.interceptors.response.use(
  (response) => {
    // Unwrap the backend envelope { success, data }
    const body = response.data
    if (body && body.success !== undefined) {
      if (!body.success) {
        const err = body.error || {}
        const error = new Error(err.message || '请求失败') as any
        error.code = err.code || 'UNKNOWN'
        error.detail = err.detail
        return Promise.reject(error)
      }
      // Replace response.data with the inner data
      response.data = body.data
    }
    return response
  },
  async (error: AxiosError) => {
    // Replace generic "Request failed with status code NNN" with backend error message
    const body = (error.response?.data ?? {}) as Record<string, any>
    if (body?.error?.message) {
      error.message = body.error.message
    }

    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // Only attempt refresh on 401, not on login/refresh endpoints themselves
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/tokens')
    ) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        clearAuthAndRedirect()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // Queue this request until refresh completes
        return new Promise((resolve, reject) => {
          refreshQueue.push({
            resolve: (token: string) => {
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${token}`
              }
              resolve(apiClient(originalRequest))
            },
            reject,
          })
        })
      }

      isRefreshing = true
      originalRequest._retry = true

      try {
        const { data } = await axios.post('/api/v1/auth/tokens/refresh', {
          refresh_token: refreshToken,
        })
        const newAccessToken = data.data?.access_token || data.access_token
        const newRefreshToken = data.data?.refresh_token || data.refresh_token

        localStorage.setItem('access_token', newAccessToken)
        if (newRefreshToken) {
          localStorage.setItem('refresh_token', newRefreshToken)
        }

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        }

        queueRefresh(newAccessToken)
        return apiClient(originalRequest)
      } catch (refreshError) {
        rejectRefresh(refreshError)
        clearAuthAndRedirect()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  },
)

function clearAuthAndRedirect() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  // Only redirect if not already on login/register page
  if (
    window.location.pathname !== '/login' &&
    window.location.pathname !== '/register'
  ) {
    window.location.href = '/login'
  }
}

export default apiClient
export { apiClient }
