<script setup lang="ts">
/**
 * 图形验证码输入组件 —— 通用，可在登录/注册/管理后台复用
 *
 * 用法：
 *   <CaptchaInput v-model:captcha-id="captchaId" v-model:solution="solution" />
 *
 * 自动加载验证码图片，提供"看不清？换一张"按钮。
 */
import { onMounted, ref, watch } from 'vue'
import { authApi } from '@/api/auth'

const props = defineProps<{
  /** v-model:captchaId */
  captchaId: string
  /** v-model:solution */
  solution: string
}>()

const emit = defineEmits<{
  'update:captchaId': [value: string]
  'update:solution': [value: string]
}>()

const image = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function loadCaptcha() {
  loading.value = true
  errorMsg.value = ''
  try {
    // 后端响应：{success: true, data: {captcha_id, image, solution?}}
    // apiClient 拦截器已解壳 → response.data = 内层 data
    const { data } = await authApi.getCaptcha()
    image.value = data.image
    emit('update:captchaId', data.captcha_id)
    emit('update:solution', '')
  } catch (e: any) {
    errorMsg.value = e.message || '验证码加载失败'
    image.value = ''
  } finally {
    loading.value = false
  }
}

// 监听外部 captchaId 被清空时重新加载（例如切换登录方式）
watch(() => props.captchaId, (val, old) => {
  if (!val && old) loadCaptcha()
})

onMounted(loadCaptcha)
</script>

<template>
  <div class="captcha-field">
    <label for="captcha-solution">图形验证码</label>
    <div class="captcha-row">
      <input
        id="captcha-solution"
        :value="solution"
        @input="emit('update:solution', ($event.target as HTMLInputElement).value)"
        type="text"
        maxlength="6"
        autocomplete="off"
        placeholder="请输入图中字符"
        class="captcha-input"
      />
      <button
        type="button"
        class="captcha-img-btn"
        :disabled="loading"
        @click="loadCaptcha"
        :title="loading ? '加载中...' : '点击换一张'"
      >
        <img v-if="image" :src="image" alt="captcha" class="captcha-img" />
        <span v-else-if="loading" class="captcha-placeholder">···</span>
        <span v-else class="captcha-placeholder">点击加载</span>
      </button>
    </div>
    <p v-if="errorMsg" class="captcha-error">{{ errorMsg }}</p>
  </div>
</template>

<style scoped>
.captcha-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.captcha-field label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--c-gray-700);
}

.captcha-row {
  display: flex;
  gap: 0.5rem;
  align-items: stretch;
}

.captcha-input {
  flex: 1;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--c-gray-300);
  border-radius: 8px;
  font-size: 1rem;
  outline: none;
  transition: border-color 0.2s;
  background: var(--surface-primary);
  color: var(--c-gray-900);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.captcha-input:focus {
  border-color: var(--c-brand-500);
}

.captcha-img-btn {
  flex-shrink: 0;
  width: 120px;
  height: auto;
  border: 1px solid var(--c-gray-300);
  border-radius: 8px;
  background: var(--surface-secondary);
  cursor: pointer;
  padding: 0;
  overflow: hidden;
  transition: border-color 0.2s;
}

.captcha-img-btn:hover:not(:disabled) {
  border-color: var(--c-brand-500);
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
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 42px;
  font-size: 0.85rem;
  color: var(--c-gray-400);
}

.captcha-error {
  font-size: 0.8rem;
  color: var(--c-danger);
  margin: 0;
}
</style>