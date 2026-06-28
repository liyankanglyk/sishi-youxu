<script setup lang="ts">
import { ref } from 'vue'
import { authApi } from '@/api/auth'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const email = ref('')
const loading = ref(false)
const sent = ref(false)
const errorMsg = ref('')

async function handleRequest() {
  if (!email.value.trim()) {
    errorMsg.value = '请输入邮箱地址'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const { data } = await authApi.requestPasswordReset(email.value.trim())
    // Force unwrap: apiClient may unwrap data automatically
    const payload = data && typeof data === 'object' && 'data' in data ? (data as any).data : data
    sent.value = true
    // Show debug token in dev mode
    if (payload?.debugToken) {
      toast.success(`模拟邮件已发送，重置码：${payload.debugToken}`)
    } else {
      toast.success('密码重置邮件已发送，请查收邮箱')
    }
  } catch (e: any) {
    errorMsg.value = e.message || '请求失败，请重试'
  } finally { loading.value = false }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <h1 class="auth-title">忘记密码</h1>
      <p class="auth-subtitle">输入注册邮箱，我们将发送重置链接</p>

      <div v-if="sent" class="success-state">
        <div class="success-icon">📧</div>
        <p>密码重置邮件已发送</p>
        <p class="dim">请检查收件箱，点击邮件中的链接重置密码</p>
        <router-link to="/login" class="back-link">返回登录</router-link>
      </div>

      <form v-else @submit.prevent="handleRequest" class="auth-form">
        <div class="field">
          <label for="email">注册邮箱</label>
          <input
            id="email"
            v-model="email"
            type="email"
            autocomplete="email"
            placeholder="user@example.com"
          />
        </div>

        <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

        <button type="submit" :disabled="loading" class="btn-primary">
          {{ loading ? '发送中...' : '发送重置邮件' }}
        </button>

        <p class="auth-link">
          <router-link to="/login">返回登录</router-link>
        </p>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--c-gray-50);
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
.field input:focus { border-color: var(--c-brand-500); }
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
.btn-primary:hover:not(:disabled) { background: var(--c-brand-600); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.auth-link {
  text-align: center;
  margin-top: 0.25rem;
  font-size: 0.9rem;
  color: var(--c-gray-500);
}
.auth-link a { color: var(--c-brand-500); text-decoration: none; }

.success-state {
  text-align: center;
  padding: 1rem 0;
}
.success-icon { font-size: 3rem; margin-bottom: 0.5rem; }
.success-state p { margin: 0.5rem 0; }
.success-state .dim { color: var(--c-gray-400); font-size: 0.9rem; }
.back-link {
  display: inline-block;
  margin-top: 1rem;
  color: var(--c-brand-500);
  text-decoration: none;
  font-weight: 500;
}
</style>
