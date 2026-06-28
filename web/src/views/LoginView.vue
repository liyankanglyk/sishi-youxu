<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  if (!email.value || !password.value) {
    errorMsg.value = '请输入邮箱和密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    await auth.login('password', { identifier: email.value, password: password.value })
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: any) {
    errorMsg.value = e.message || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <svg viewBox="0 0 32 32" width="48" height="48" fill="none">
          <rect x="2" y="2" width="12" height="12" rx="3" fill="#6366f1" opacity="0.9"/>
          <rect x="18" y="2" width="12" height="12" rx="3" fill="#818cf8" opacity="0.7"/>
          <rect x="2" y="18" width="12" height="12" rx="3" fill="#a5b4fc" opacity="0.6"/>
          <rect x="18" y="18" width="12" height="12" rx="3" fill="#c7d2fe" opacity="0.5"/>
        </svg>
      </div>
      <h1 class="auth-title">四时有序</h1>
      <p class="auth-subtitle">登录以管理你的任务</p>

      <form @submit.prevent="handleLogin" class="auth-form">
        <div class="field">
          <label for="email">用户名 / 邮箱</label>
          <input
            id="email"
            v-model="email"
            type="text"
            autocomplete="username"
            placeholder="用户名或邮箱"
          />
        </div>

        <div class="field">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="至少 8 位"
          />
        </div>

        <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

        <button type="submit" :disabled="loading" class="btn-primary">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>

      <p class="auth-link">
        <router-link to="/forgot-password">忘记密码？</router-link>
      </p>
      <p class="auth-link">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background:
    radial-gradient(ellipse 100% 70% at 0% 0%, rgba(129, 140, 248, 0.35) 0%, transparent 50%),
    radial-gradient(ellipse 100% 70% at 100% 0%, rgba(99, 102, 241, 0.30) 0%, transparent 50%),
    radial-gradient(ellipse 100% 70% at 0% 100%, rgba(199, 210, 254, 0.32) 0%, transparent 50%),
    radial-gradient(ellipse 100% 70% at 100% 100%, rgba(165, 180, 252, 0.26) 0%, transparent 50%),
    var(--c-gray-50);
  padding: 1rem;
}
.auth-card {
  width: 100%;
  max-width: 400px;
  background: var(--surface-primary);
  border-radius: 12px;
  padding: 2.5rem 2rem;
  box-shadow: var(--sh-modal);
  color: var(--c-gray-900);
}
.auth-logo {
  text-align: center;
  margin-bottom: 0.75rem;
}
.auth-title {
  text-align: center;
  font-size: 1.75rem;
  margin: 0 0 0.25rem;
  color: var(--c-gray-900);
}
.auth-subtitle {
  text-align: center;
  color: var(--c-gray-500);
  margin: 0 0 1.5rem;
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.field label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--c-gray-700);
}
.field input {
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--c-gray-300);
  border-radius: 8px;
  font-size: 1rem;
  outline: none;
  transition: border-color 0.2s;
  background: var(--surface-primary);
  color: var(--c-gray-900);
}
.field input:focus {
  border-color: var(--c-brand-500);
}
.error {
  color: var(--c-danger);
  font-size: 0.85rem;
  margin: 0;
}
.btn-primary {
  padding: 0.75rem;
  background: var(--c-brand-500);
  color: #FFFFFF;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-primary:hover { background: var(--c-brand-600); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.auth-link {
  text-align: center;
  margin-top: 1.25rem;
  font-size: 0.9rem;
  color: var(--c-gray-500);
}
.auth-link a { color: var(--c-brand-500); text-decoration: none; }
</style>
