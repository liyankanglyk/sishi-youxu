<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminAuthStore } from '@/stores/adminAuth'
import { adminApi } from '@/api/admin'

const router = useRouter()
const auth = useAdminAuthStore()

const username = ref('admin')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

// 图形验证码
const captchaId = ref('')
const captchaSolution = ref('')
const captchaImage = ref('')
const captchaLoading = ref(false)

async function loadCaptcha() {
  captchaLoading.value = true
  try {
    // 拦截器已解壳 → response.data = 内层 captcha 数据
    const { data } = await adminApi.getAdminCaptcha()
    captchaImage.value = data.image
    captchaId.value = data.captcha_id
    captchaSolution.value = ''
  } catch (e: any) {
    errorMsg.value = e.message || '验证码加载失败'
  } finally {
    captchaLoading.value = false
  }
}

async function handleLogin() {
  if (!username.value || !password.value) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  if (!captchaId.value || !captchaSolution.value) {
    errorMsg.value = '请输入图形验证码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    await auth.login(
      username.value,
      password.value,
      { captchaId: captchaId.value, captchaSolution: captchaSolution.value },
    )
    router.push('/admin/dashboard')
  } catch (e: any) {
    errorMsg.value = e.message || '登录失败'
    // 失败后刷新验证码
    await loadCaptcha()
  } finally {
    loading.value = false
  }
}

onMounted(loadCaptcha)
</script>

<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="bg-shape bg-shape-1" />
      <div class="bg-shape bg-shape-2" />
    </div>

    <div class="login-card">
      <div class="login-brand">
        <div class="brand-mark">
          <svg viewBox="0 0 32 32" width="36" height="36" fill="none">
            <rect x="2" y="2" width="12" height="12" rx="3" fill="#6366f1" opacity="0.9"/>
            <rect x="18" y="2" width="12" height="12" rx="3" fill="#818cf8" opacity="0.7"/>
            <rect x="2" y="18" width="12" height="12" rx="3" fill="#a5b4fc" opacity="0.6"/>
            <rect x="18" y="18" width="12" height="12" rx="3" fill="#c7d2fe" opacity="0.5"/>
          </svg>
        </div>
        <h1>四时有序</h1>
        <p>管理后台</p>
      </div>

      <form class="login-form" @submit.prevent="handleLogin">
        <div class="form-field">
          <label>用户名</label>
          <div class="input-wrap">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            <input v-model="username" type="text" placeholder="请输入用户名" autocomplete="username" />
          </div>
        </div>

        <div class="form-field">
          <label>密码</label>
          <div class="input-wrap">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            <input v-model="password" type="password" placeholder="请输入密码" autocomplete="current-password" />
          </div>
        </div>

        <!-- 图形验证码 -->
        <div class="form-field">
          <label>图形验证码</label>
          <div class="captcha-row">
            <div class="input-wrap captcha-input-wrap">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12l2 2 4-4"/><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
              <input
                v-model="captchaSolution"
                type="text"
                placeholder="请输入验证码"
                maxlength="6"
                autocomplete="off"
                class="captcha-input"
              />
            </div>
            <button
              type="button"
              class="captcha-img-btn"
              :disabled="captchaLoading"
              @click="loadCaptcha"
              :title="captchaLoading ? '加载中...' : '点击换一张'"
            >
              <img v-if="captchaImage" :src="captchaImage" alt="captcha" class="captcha-img" />
              <span v-else-if="captchaLoading" class="captcha-placeholder">···</span>
              <span v-else class="captcha-placeholder">点击加载</span>
            </button>
          </div>
        </div>

        <div v-if="errorMsg" class="form-error">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span>{{ errorMsg }}</span>
        </div>

        <button type="submit" :disabled="loading" class="login-btn">
          <span v-if="!loading">登录</span>
          <span v-else class="btn-loading">
            <span class="spinner" />
            登录中...
          </span>
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(ellipse 100% 70% at 0% 0%, rgba(129, 140, 248, 0.35) 0%, transparent 50%),
    radial-gradient(ellipse 100% 70% at 100% 0%, rgba(99, 102, 241, 0.30) 0%, transparent 50%),
    radial-gradient(ellipse 100% 70% at 0% 100%, rgba(199, 210, 254, 0.32) 0%, transparent 50%),
    radial-gradient(ellipse 100% 70% at 100% 100%, rgba(165, 180, 252, 0.26) 0%, transparent 50%),
    #f8fafc;
}

/* 背景装饰形状 */
.login-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.bg-shape {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.15;
}

.bg-shape-1 {
  width: 500px;
  height: 500px;
  background: #6366f1;
  top: -120px;
  right: -160px;
}

.bg-shape-2 {
  width: 400px;
  height: 400px;
  background: #10b981;
  bottom: -100px;
  left: -120px;
}

/* 卡片 */
.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  background: #fff;
  border-radius: 16px;
  padding: 40px 36px 36px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 8px 32px rgba(0,0,0,0.06);
  border: 1px solid #e2e8f0;
}

.login-brand {
  text-align: center;
  margin-bottom: 32px;
}

.brand-mark {
  margin-bottom: 12px;
  display: inline-flex;
}

.login-brand h1 {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 4px;
  letter-spacing: -0.01em;
}

.login-brand p {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

/* 表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.input-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0 14px;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}

.input-wrap:focus-within {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
  background: #fff;
}

.input-wrap input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 12px 0;
  font-size: 14px;
  color: #1e293b;
  outline: none;
  font-family: inherit;
}

.input-wrap input::placeholder {
  color: #94a3b8;
}

/* 验证码 */
.captcha-row {
  display: flex;
  gap: 10px;
  align-items: stretch;
}
.captcha-input-wrap {
  flex: 1;
}
.captcha-input {
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.captcha-img-btn {
  flex-shrink: 0;
  width: 120px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  cursor: pointer;
  padding: 0;
  overflow: hidden;
  transition: border-color 150ms ease;
  display: flex;
  align-items: center;
  justify-content: center;
}
.captcha-img-btn:hover:not(:disabled) {
  border-color: #6366f1;
}
.captcha-img-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.captcha-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.captcha-placeholder {
  font-size: 12px;
  color: #94a3b8;
  padding: 12px 0;
}

/* 错误提示 */
.form-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #fef2f2;
  border-radius: 8px;
  font-size: 13px;
  color: #dc2626;
}

/* 按钮 */
.login-btn {
  margin-top: 4px;
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms ease;
  font-family: inherit;
}

.login-btn:hover:not(:disabled) {
  box-shadow: 0 4px 16px rgba(99,102,241,0.4);
  transform: translateY(-1px);
}

.login-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn-loading {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>