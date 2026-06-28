import apiClient from './index'

// ── 类型定义 ──

export interface AdminUser {
  uuid: string
  nickname: string
  avatarUrl?: string | null
  role: string
  status: string
  locale: string
  createdAt: string
}

export interface UserDetail extends AdminUser {
  authIdentities: Array<{ provider: string; identifier: string }>
  taskCount: number
  completedTaskCount: number
  updatedAt: string
}

export interface PaginatedResponse<T> {
  items: T[]
  meta: { total: number; page: number; pageSize: number; hasMore: boolean }
}

export interface DashboardStats {
  total_users: number
  active_users_today: number
  total_tasks: number
  completed_tasks_today: number
  quadrant_distribution: { q1: number; q2: number; q3: number; q4: number }
  dau?: { date: string; count: number }
  mau?: { month: string; count: number }
}

export interface AuditEntry {
  uuid: string
  userUuid: string | null
  userNickname?: string | null
  action: string
  actionLabel?: string
  resourceType: string
  resourceUuid: string | null
  ipAddress: string | null
  userAgent?: string | null
  detail: Record<string, unknown> | null
  createdAt: string
}

export interface FeedbackEntry {
  uuid: string
  userUuid: string | null
  content: string
  contact: string | null
  status: string
  createdAt: string
}

export interface SystemConfig {
  [key: string]: string | boolean
}

export interface LoginLogEntry {
  uuid: string
  userUuid: string | null
  provider: string
  ipAddress: string | null
  userAgent?: string | null
  loginStatus: 'success' | 'failed'
  failReason?: string | null
  createdAt: string
}

export interface SensitiveWord {
  uuid: string
  word: string
  level: number
  createdAt?: string
  updatedAt?: string
}

export interface IpBlacklistEntry {
  uuid: string
  ipAddress: string
  reason: string | null
  createdBy: string | null
  expiresAt: string | null
  createdAt: string
}

export interface Announcement {
  uuid: string
  title: string
  content: string
  type: 'info' | 'warning' | 'critical'
  isPinned: boolean
  isActive: boolean
  startTime: string | null
  endTime: string | null
  createdBy: string | null
  createdAt: string
  updatedAt?: string
}

// ── 内容管理相关类型 ──

export interface AdminTaskListItem {
  uuid: string
  title: string
  urgencyLevel: number
  importanceLevel: number
  completed: boolean
  completedAt: string | null
  dueDate: string | null
  tags: Array<{ uuid: string; name: string; color: string }>
  userUuid: string
  userNickname: string
  createdAt: string
  updatedAt: string
}

export interface ChecklistItem {
  uuid: string
  title: string
  completed: boolean
  sortOrder: number
}

export interface AdminTaskDetail extends AdminTaskListItem {
  recurrence: string | null
  note: string | null
  sortOrder: number
  checklist: ChecklistItem[]
}

export interface AdminTagListItem {
  uuid: string
  name: string
  color: string
  isPreset: boolean
  taskCount: number
  userUuid: string | null
  userNickname: string
  createdAt: string
}

export interface AdminTagDetail {
  uuid: string
  name: string
  color: string
  isPreset: boolean
  taskCount: number
  users: Array<{ uuid: string; nickname: string }>
  createdAt: string
  updatedAt: string
}

// ── API 方法 ──

export const adminApi = {
  // 认证相关
  login(username: string, password: string) {
    return apiClient.post('/admin/auth/tokens', { username, password })
  },
  refresh(refreshToken: string) {
    return apiClient.post('/admin/auth/tokens/refresh', { refresh_token: refreshToken })
  },
  logout(refreshToken: string) {
    return apiClient.delete('/admin/auth/tokens', { data: { refresh_token: refreshToken } })
  },
  getMe() {
    return apiClient.get<AdminUser>('/admin/users/me')
  },

  // 用户相关
  listUsers(params?: {
    page?: number; pageSize?: number; keyword?: string
    status?: string; role?: string; startTime?: string; endTime?: string
  }) {
    return apiClient.get<PaginatedResponse<AdminUser>>('/admin/users', { params })
  },
  getUser(uuid: string) {
    return apiClient.get<UserDetail>(`/admin/users/${uuid}`)
  },
  updateUser(uuid: string, data: { status?: string; nickname?: string }) {
    return apiClient.patch(`/admin/users/${uuid}`, data)
  },
  deleteUser(uuid: string) {
    return apiClient.delete(`/admin/users/${uuid}`)
  },
  disableUser(uuid: string) {
    return apiClient.post(`/admin/users/${uuid}/disable`)
  },
  enableUser(uuid: string) {
    return apiClient.post(`/admin/users/${uuid}/enable`)
  },
  forceLogout(uuid: string) {
    return apiClient.post(`/admin/users/${uuid}/force-logout`)
  },
  resetUserPassword(uuid: string, newPassword: string) {
    return apiClient.post(`/admin/users/${uuid}/reset-password`, { newPassword })
  },
  changePassword(oldPassword: string, newPassword: string) {
    return apiClient.post('/admin/auth/password', { oldPassword, newPassword })
  },
  batchUsers(data: { idempotencyKey: string; action: string; uuids: string[] }) {
    return apiClient.post('/admin/users/batch', data)
  },
  exportUsers() {
    return apiClient.get('/admin/users/export', { responseType: 'blob' })
  },

  // 仪表盘相关
  getStats() {
    return apiClient.get<DashboardStats>('/admin/dashboard/stats')
  },
  getChart(metric: string) {
    return apiClient.get(`/admin/dashboard/charts/${metric}`)
  },

  // 审计日志相关
  listAudit(params?: {
    page?: number; pageSize?: number; userUuid?: string
    action?: string; resourceType?: string; startTime?: string; endTime?: string
  }) {
    return apiClient.get<PaginatedResponse<AuditEntry>>('/admin/audit', { params })
  },
  getAuditEntry(uuid: string) {
    return apiClient.get<AuditEntry>(`/admin/audit/${uuid}`)
  },

  // 反馈相关
  listFeedback(params?: { page?: number; pageSize?: number; status?: string }) {
    return apiClient.get<PaginatedResponse<FeedbackEntry>>('/admin/feedback', { params })
  },
  updateFeedback(uuid: string, data: { status: string }) {
    return apiClient.patch(`/admin/feedback/${uuid}`, data)
  },
  deleteFeedback(uuid: string) {
    return apiClient.delete(`/admin/feedback/${uuid}`)
  },

  // 登录日志相关
  listLoginLogs(params?: {
    page?: number; pageSize?: number; status?: string; provider?: string; userUuid?: string
  }) {
    return apiClient.get<PaginatedResponse<LoginLogEntry>>('/admin/login-logs', { params })
  },

  // 敏感词相关
  listSensitiveWords(params?: { page?: number; pageSize?: number }) {
    return apiClient.get<PaginatedResponse<SensitiveWord>>('/admin/sensitive-words', { params })
  },
  addSensitiveWord(data: { word: string; level: number }) {
    return apiClient.post('/admin/sensitive-words', data)
  },
  updateSensitiveWord(uuid: string, data: { word?: string; level?: number }) {
    return apiClient.patch(`/admin/sensitive-words/${uuid}`, data)
  },
  deleteSensitiveWord(uuid: string) {
    return apiClient.delete(`/admin/sensitive-words/${uuid}`)
  },
  importSensitiveWords(formData: FormData) {
    return apiClient.post('/admin/sensitive-words/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // IP 黑名单相关
  listIpBlacklist(params?: { page?: number; pageSize?: number }) {
    return apiClient.get<PaginatedResponse<IpBlacklistEntry>>('/admin/security/ip-blacklist', { params })
  },
  addIpBlacklist(data: { ipAddress: string; reason?: string; expiresAt?: string }) {
    return apiClient.post('/admin/security/ip-blacklist', data)
  },
  deleteIpBlacklist(uuid: string) {
    return apiClient.delete(`/admin/security/ip-blacklist/${uuid}`)
  },

  // 公告相关
  listAnnouncements(params?: { page?: number; pageSize?: number; type?: string }) {
    return apiClient.get<PaginatedResponse<Announcement>>('/admin/announcements', { params })
  },
  createAnnouncement(data: {
    title: string; content: string; type: string
    isPinned?: boolean; isActive?: boolean
    startTime?: string; endTime?: string
  }) {
    return apiClient.post('/admin/announcements', data)
  },
  updateAnnouncement(uuid: string, data: Record<string, unknown>) {
    return apiClient.patch(`/admin/announcements/${uuid}`, data)
  },
  deleteAnnouncement(uuid: string) {
    return apiClient.delete(`/admin/announcements/${uuid}`)
  },

  // 系统配置相关
  getConfig() {
    return apiClient.get<SystemConfig>('/admin/config')
  },
  updateConfig(data: Record<string, unknown>) {
    return apiClient.patch('/admin/config', data)
  },

  // 内容管理：任务
  listAdminTasks(params?: {
    page?: number; pageSize?: number; userUuid?: string
    quadrant?: number; completed?: boolean; tagUuid?: string
    startTime?: string; endTime?: string
  }) {
    return apiClient.get<PaginatedResponse<AdminTaskListItem>>('/admin/tasks', { params })
  },
  getAdminTask(uuid: string) {
    return apiClient.get<AdminTaskDetail>(`/admin/tasks/${uuid}`)
  },
  deleteAdminTask(uuid: string) {
    return apiClient.delete(`/admin/tasks/${uuid}`)
  },
  createAdminTask(data: {
    title: string; userUuid: string
    urgencyLevel?: number; importanceLevel?: number
    dueDate?: string; note?: string; tagUuids?: string[]
  }) {
    return apiClient.post<AdminTaskDetail>('/admin/tasks', data)
  },
  updateAdminTask(uuid: string, data: {
    title?: string; urgencyLevel?: number; importanceLevel?: number
    dueDate?: string; note?: string; completed?: boolean; tagUuids?: string[]
  }) {
    return apiClient.patch<AdminTaskDetail>(`/admin/tasks/${uuid}`, data)
  },
  batchAdminTasks(data: { action: string; taskUuids: string[] }) {
    return apiClient.post('/admin/tasks/batch', data)
  },

  // 内容管理：标签
  createAdminTag(data: { name: string; color?: string; userUuid?: string }) {
    return apiClient.post<AdminTagListItem>('/admin/tags', data)
  },
  listAdminTags(params?: {
    page?: number; pageSize?: number; userUuid?: string; q?: string
  }) {
    return apiClient.get<PaginatedResponse<AdminTagListItem>>('/admin/tags', { params })
  },
  getAdminTag(uuid: string) {
    return apiClient.get<AdminTagDetail>(`/admin/tags/${uuid}`)
  },
  patchAdminTag(uuid: string, data: { name?: string; color?: string }) {
    return apiClient.patch<AdminTagListItem>(`/admin/tags/${uuid}`, data)
  },
  deleteAdminTag(uuid: string) {
    return apiClient.delete(`/admin/tags/${uuid}`)
  },

  // 按用户范围的内容
  listUserTasks(userUuid: string, params?: {
    page?: number; pageSize?: number; quadrant?: number; completed?: boolean
  }) {
    return apiClient.get<PaginatedResponse<AdminTaskListItem>>(`/admin/users/${userUuid}/tasks`, { params })
  },
  listUserTags(userUuid: string, params?: { page?: number; pageSize?: number }) {
    return apiClient.get<PaginatedResponse<AdminTagListItem>>(`/admin/users/${userUuid}/tags`, { params })
  },

  // 用于下拉选择的快速搜索辅助方法
  searchUsers(keyword: string, limit = 20) {
    return apiClient.get<PaginatedResponse<AdminUser>>('/admin/users', { params: { keyword, pageSize: limit } })
  },
  searchTags(q: string, limit = 20) {
    return apiClient.get<PaginatedResponse<AdminTagListItem>>('/admin/tags', { params: { q, pageSize: limit } })
  },
}
