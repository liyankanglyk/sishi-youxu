import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { adminApi, type AdminUser } from '@/api/admin'

const TOKEN_KEY = 'admin_access_token'
const REFRESH_KEY = 'admin_refresh_token'
const USER_KEY = 'admin_user'

export const useAdminAuthStore = defineStore('adminAuth', () => {
  const admin = ref<AdminUser | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value && !!admin.value)

  function persist() {
    if (accessToken.value) localStorage.setItem(TOKEN_KEY, accessToken.value)
    else localStorage.removeItem(TOKEN_KEY)
    if (refreshToken.value) localStorage.setItem(REFRESH_KEY, refreshToken.value)
    else localStorage.removeItem(REFRESH_KEY)
    if (admin.value) localStorage.setItem(USER_KEY, JSON.stringify(admin.value))
    else localStorage.removeItem(USER_KEY)
  }

  function initFromStorage() {
    accessToken.value = localStorage.getItem(TOKEN_KEY)
    refreshToken.value = localStorage.getItem(REFRESH_KEY)
    const u = localStorage.getItem(USER_KEY)
    if (u) {
      try { admin.value = JSON.parse(u) } catch { /* ignore */ }
    }
  }

  function clearAuth() {
    admin.value = null
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
  }

  async function login(username: string, password: string) {
    const { data } = await adminApi.login(username, password)
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    admin.value = data.user || data.admin || null
    persist()
    return data
  }

  async function logout() {
    try {
      if (refreshToken.value) await adminApi.logout(refreshToken.value)
    } catch { /* ignore */ }
    clearAuth()
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    await adminApi.changePassword(oldPassword, newPassword)
    clearAuth()
  }

  return { admin, accessToken, refreshToken, isAuthenticated, initFromStorage, clearAuth, login, logout, changePassword }
})
