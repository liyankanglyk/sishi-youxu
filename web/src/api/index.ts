import axios from 'axios'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ── 请求拦截器：注入 Bearer token ──
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── 响应拦截器：解包 {success,data} / 处理 401 token 刷新 ──
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
    // 解包后端返回的外层结构 { success, data }
    const body = response.data
    if (body && body.success !== undefined) {
      if (!body.success) {
        const err = body.error || {}
        const error = new Error(err.message || '请求失败') as any
        error.code = err.code || 'UNKNOWN'
        error.detail = err.detail
        return Promise.reject(error)
      }
      // 用内层 data 替换 response.data
      response.data = body.data
    }
    return response
  },
  async (error: AxiosError) => {
    // 用后端的错误信息替换默认的 "Request failed with status code NNN"
    const body = (error.response?.data ?? {}) as Record<string, any>
    if (body?.error?.message) {
      error.message = body.error.message
    }

    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // 仅在 401 时尝试刷新 token，登录/刷新接口本身不会触发
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
        // 将该请求加入队列，等待刷新完成后重放
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
  // 仅在不在登录/注册页时跳转
  if (
    window.location.pathname !== '/login' &&
    window.location.pathname !== '/register'
  ) {
    window.location.href = '/login'
  }
}

export default apiClient
export { apiClient }
