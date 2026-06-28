import axios from 'axios'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// Token 刷新状态 —— 防止多个请求同时触发刷新
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

// 自带认证处理的端点（登录 / 刷新）。这些端点：
//   (a) 不得携带（可能已过期的）access token；
//   (b) 在 401 时不得触发递归刷新。
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
        // 任何 AUTH_* 错误 → 强制跳转到登录页
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

    // 跳过认证端点的刷新（登录 / 刷新接口本身）。
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
    // 使用 replace 避免在浏览器历史中留下已损坏的页面。
    window.location.replace('/admin/login')
  }
}

export default apiClient
