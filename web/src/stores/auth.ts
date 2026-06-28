import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type UserOut } from '@/api/auth'
import { db } from '@/db'

const STORAGE_KEYS = {
  ACCESS_TOKEN: 'access_token',
  REFRESH_TOKEN: 'refresh_token',
  USER: 'user',
}

export const useAuthStore = defineStore('auth', () => {
  // ── State ──
  const user = ref<UserOut | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)

  // ── Getters ──
  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)
  const userRole = computed(() => user.value?.role ?? 'guest')

  // ── Persistence ──
  function persistTokens() {
    if (accessToken.value) localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, accessToken.value)
    else localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN)

    if (refreshToken.value) localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refreshToken.value)
    else localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)

    if (user.value) localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user.value))
    else localStorage.removeItem(STORAGE_KEYS.USER)
  }

  function initFromStorage() {
    const at = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN)
    const rt = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN)
    const u = localStorage.getItem(STORAGE_KEYS.USER)

    if (at) accessToken.value = at
    if (rt) refreshToken.value = rt
    if (u) {
      try {
        user.value = JSON.parse(u)
      } catch {
        // corrupted data, ignore
      }
    }
  }

  function clearAuth() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN)
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
    localStorage.removeItem(STORAGE_KEYS.USER)
  }

  // ── Actions ──
  async function login(provider: string, payload: Record<string, unknown>) {
    const { data } = await authApi.login(provider, payload)
    user.value = data.user
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    persistTokens()
    // Persist to Dexie for offline access
    try {
      await db.authSession.put({
        key: 'current',
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        user: data.user as unknown as Record<string, unknown>,
        expiresAt: new Date(Date.now() + data.expires_in * 1000).toISOString(),
      })
    } catch { /* Dexie may not be open yet */ }
    return data
  }

  async function register(nickname: string, provider: string, payload: Record<string, unknown>) {
    const { data } = await authApi.register(nickname, provider, payload)
    user.value = data.user
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    persistTokens()
    return data
  }

  async function refresh() {
    if (!refreshToken.value) throw new Error('No refresh token')
    const { data } = await authApi.refresh(refreshToken.value)
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token || data.refresh_token
    persistTokens()
    return data
  }

  async function logout() {
    try {
      if (refreshToken.value) {
        await authApi.logout(refreshToken.value)
      }
    } catch {
      // Ignore errors during logout
    } finally {
      clearAuth()
    }
  }

  async function wechatLogin(code: string) {
    const { data } = await authApi.wechatLogin(code)
    user.value = data.user
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    persistTokens()
    return data
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    await authApi.changePassword(oldPassword, newPassword)
    // Force re-login: clear tokens so user must sign in again
    clearAuth()
  }

  return {
    // State
    user,
    accessToken,
    refreshToken,
    // Getters
    isAuthenticated,
    userRole,
    // Actions
    initFromStorage,
    clearAuth,
    login,
    register,
    refresh,
    logout,
    wechatLogin,
    changePassword,
  }
})
