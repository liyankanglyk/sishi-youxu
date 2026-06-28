<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const nickname = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function handleRegister() {
  errorMsg.value = ''
  if (!nickname.value || !email.value || !password.value) {
    errorMsg.value = '请填写所有字段'
    return
  }
  if (nickname.value.length < 2 || nickname.value.length > 20) {
    errorMsg.value = '昵称长度需在 2-20 字符之间'
    return
  }
  if (password.value.length < 8) {
    errorMsg.value = '密码至少 8 位'
    return
  }
  if (password.value !== confirmPassword.value) {
    errorMsg.value = '两次密码输入不一致'
    return
  }

  loading.value = true
  try {
    await auth.register(nickname.value, 'password', {
      identifier: email.value,
      password: password.value,
    })
    router.push('/')
  } catch (e: any) {
    errorMsg.value = e.message || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <h1 class="auth-title">创建账号</h1>
      <p class="auth-subtitle">开始使用四时有序管理任务</p>

      <form @submit.prevent="handleRegister" class="auth-form">
        <div class="field">
          <label for="nickname">昵称</label>
          <input id="nickname" v-model="nickname" type="text" placeholder="2-20 个字符" />
        </div>
        <div class="field">
          <label for="email">邮箱</label>
          <input id="email" v-model="email" type="email" placeholder="user@example.com" />
        </div>
        <div class="field">
          <label for="password">密码</label>
          <input id="password" v-model="password" type="password" placeholder="至少 8 位" />
        </div>
        <div class="field">
          <label for="confirm">确认密码</label>
          <input id="confirm" v-model="confirmPassword" type="password" placeholder="再次输入密码" />
        </div>

        <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

        <button type="submit" :disabled="loading" class="btn-primary">
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </form>

      <p class="auth-link">
        已有账号？<router-link to="/login">去登录</router-link>
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
