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
    // 强制解包：apiClient 可能会自动解包 data
    const payload = data && typeof data === 'object' && 'data' in data ? (data as any).data : data
    sent.value = true
    // 在开发模式下展示调试 token
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
      <div class="auth-logo">
        <svg viewBox="0 0 32 32" width="48" height="48" fill="none">
          <rect x="2" y="2" width="12" height="12" rx="3" fill="#6366f1" opacity="0.9"/>
          <rect x="18" y="2" width="12" height="12" rx="3" fill="#818cf8" opacity="0.7"/>
          <rect x="2" y="18" width="12" height="12" rx="3" fill="#a5b4fc" opacity="0.6"/>
          <rect x="18" y="18" width="12" height="12" rx="3" fill="#c7d2fe" opacity="0.5"/>
        </svg>
      </div>
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
