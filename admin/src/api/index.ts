import axios from 'axios'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// Token refresh state — prevents multiple simultaneous refresh attempts
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string | null) => void
  reject: (error: unknown) => void
}> = []

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token)
  })
  failedQueue = []
}

// Endpoints that handle their own auth (login / refresh). Must NOT:
//   (a) carry the (possibly expired) access token, or
//   (b) trigger a recursive refresh on 401.
const AUTH_BYPASS_PATHS = ['/admin/auth/tokens']

function isAuthBypassUrl(url?: string): boolean {
  if (!url) return false
  return AUTH_BYPASS_PATHS.some((p) => url.includes(p))
}

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (isAuthBypassUrl(config.url)) return config
  const token = localStorage.getItem('admin_access_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && body.success !== undefined) {
      if (!body.success) {
        const err = body.error || {}
        const error = new Error(err.message || '请求失败') as any
        error.code = err.code || 'UNKNOWN'
        // Any AUTH_* error → force redirect to login
        if (
          err.code === 'AUTH_ADMIN_REQUIRED' ||
          err.code === 'ADMIN_FORBIDDEN' ||
          (typeof err.code === 'string' && err.code.startsWith('AUTH_'))
        ) {
          clearAuthAndRedirect()
        }
        return Promise.reject(error)
      }
      response.data = body.data
    }
    return response
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // Skip refresh for auth endpoints (login / refresh itself).
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !isAuthBypassUrl(originalRequest.url)
    ) {
      const refreshToken = localStorage.getItem('admin_refresh_token')
      if (!refreshToken) {
        clearAuthAndRedirect()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          if (token && originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`
          }
          return apiClient(originalRequest)
        })
      }

      isRefreshing = true
      originalRequest._retry = true

      try {
        const response = await apiClient.post(
          '/admin/auth/tokens/refresh',
          { refresh_token: refreshToken },
          { _retry: true } as unknown as InternalAxiosRequestConfig,
        )
        const newToken = response.data.access_token
        const newRefreshToken = response.data.refresh_token
        localStorage.setItem('admin_access_token', newToken)
        if (newRefreshToken) {
          localStorage.setItem('admin_refresh_token', newRefreshToken)
        }
        processQueue(null, newToken)
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`
        }
        return apiClient(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
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
  localStorage.removeItem('admin_access_token')
  localStorage.removeItem('admin_refresh_token')
  localStorage.removeItem('admin_user')
  if (window.location.pathname !== '/admin/login') {
    // Use replace to avoid leaving the broken page in browser history.
    window.location.replace('/admin/login')
  }
}

export default apiClient
