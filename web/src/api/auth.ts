import apiClient from './index'

export interface LoginPayload {
  identifier?: string
  password?: string
  phone?: string
  code?: string
  email?: string
}

export interface RegisterPayload {
  nickname: string
  provider: 'password' | 'phone_sms' | 'email_code'
  payload: Record<string, string>
}

export interface UserOut {
  uuid: string
  nickname: string
  avatar_url: string | null
  role: string
  status: string
  locale: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserOut
  is_new_user?: boolean
}

export const authApi = {
  /** 账号密码 / 短信 / 邮箱 登录 */
  login(provider: string, payload: Record<string, unknown>) {
    return apiClient.post<TokenResponse>('/auth/tokens', { provider, payload })
  },

  /** 注册新用户 */
  register(nickname: string, provider: string, payload: Record<string, unknown>) {
    return apiClient.post<TokenResponse>('/users', { nickname, provider, payload })
  },

  /** 刷新 token */
  refresh(refreshToken: string) {
    return apiClient.post('/auth/tokens/refresh', { refresh_token: refreshToken })
  },

  /** 登出当前设备 */
  logout(refreshToken: string) {
    return apiClient.post('/auth/tokens/logout', { refresh_token: refreshToken })
  },

  /** 登出所有设备 */
  logoutAll() {
    return apiClient.post('/auth/tokens/logout-all')
  },

  /** 微信小程序登录 */
  wechatLogin(code: string, encryptedData?: string, iv?: string) {
    return apiClient.post<TokenResponse>('/auth/wechat/login', {
      code,
      encrypted_data: encryptedData,
      iv,
    })
  },

  /** 获取 WebSocket ticket */
  getWsTicket() {
    return apiClient.post('/auth/ws-ticket')
  },

  /** 获取可用登录方式列表 */
  getLoginMethods() {
    return apiClient.get('/auth/login-methods')
  },

  /** 获取图形验证码 */
  getCaptcha() {
    return apiClient.get('/auth/captcha')
  },

  /** 校验图形验证码 */
  verifyCaptcha(captchaId: string, solution: string) {
    return apiClient.post('/auth/captcha/verify', {
      captcha_id: captchaId,
      captcha_solution: solution,
    })
  },

  /** 发送短信验证码 */
  sendSms(phone: string, purpose: 'login' | 'register' | 'bind' = 'login') {
    return apiClient.post('/auth/sms/send', { phone, purpose })
  },

  /** 短信验证码登录 */
  loginBySms(phone: string, code: string) {
    return apiClient.post('/auth/sms/login', { phone, code })
  },

  /** 发送邮箱验证码 */
  sendEmailCode(email: string, purpose: 'login' | 'register' | 'bind' = 'login') {
    return apiClient.post('/auth/email/send', { email, purpose })
  },

  /** 邮箱验证码登录 */
  loginByEmail(email: string, code: string) {
    return apiClient.post('/auth/email/login', { email, code })
  },

  /** 请求密码重置 */
  requestPasswordReset(email: string) {
    return apiClient.post('/auth/password/reset-request', null, { params: { email } })
  },

  /** 执行密码重置 */
  resetPassword(resetToken: string, newPassword: string) {
    return apiClient.post('/auth/password/reset', {
      reset_token: resetToken,
      new_password: newPassword,
    })
  },

  /** 获取当前用户信息 */
  getMe() {
    return apiClient.get<UserOut>('/users/me')
  },

  /** 修改当前用户密码 */
  changePassword(oldPassword: string, newPassword: string) {
    return apiClient.post('/users/me/password', {
      oldPassword,
      newPassword,
    })
  },
}
