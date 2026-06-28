import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { initDatabase } from './db'
import { useAuthStore } from './stores/auth'

async function bootstrap() {
  // 初始化 IndexedDB（离线优先存储）
  try {
    await initDatabase()
  } catch (e) {
    console.warn('[main] IndexedDB 不可用，将在没有离线支持的情况下运行：', e)
  }

  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)
  app.use(router)

  // 在渲染前从 localStorage 恢复登录状态
  const authStore = useAuthStore()
  authStore.initFromStorage()

  app.mount('#app')
  console.log('[main] App mounted')
}

bootstrap()
