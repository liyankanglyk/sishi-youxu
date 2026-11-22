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
              // 重放前也要标记，否则它再次 401 时会发起第二轮刷新
              originalRequest._retry = true
              resolve(apiClient(originalRequest))
            },
            reject,
          })
        })
      }

      isRefreshing = true
      originalRequest._retry = true

      try {
        // 必须走 apiClient：裸 axios 不经过响应拦截器，
        // 后端 HTTP 200 + {success:false} 时不会 reject，access_token 会变成 undefined
        // 并被写成字符串 "undefined"，之后每个请求都带 Bearer undefined 一直 401。
        const { data } = await apiClient.post<{ access_token: string; refresh_token?: string }>(
          '/auth/tokens/refresh',
          { refresh_token: refreshToken },
        )
        const newAccessToken = data?.access_token
        const newRefreshToken = data?.refresh_token

        if (typeof newAccessToken !== 'string' || !newAccessToken) {
          throw new Error('刷新响应缺少 access_token')
        }

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
  // 与 authStore.clearAuth 对齐：user 键也要删，否则下次登录前守卫/头像会读到上一个人的资料
  localStorage.removeItem('user')
  // 仅在不在登录/注册页时跳转
  const path = window.location.pathname
  if (path !== '/login' && path !== '/register') {
    // 带上 redirect，重新登录后才能回到原页面（路由守卫就是这么写的）
    const back = encodeURIComponent(path + window.location.search)
    window.location.href = `/login?redirect=${back}`
  }
}

export default apiClient
export { apiClient }
