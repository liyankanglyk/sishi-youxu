import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { initDatabase } from './db'
import { useAuthStore } from './stores/auth'
import { useTaskStore } from './stores/task'
import { syncEngine } from './lib/sync/engine'

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

  if (authStore.isAuthenticated) {
    // 离线优先：先用本地数据出画面，再启动同步引擎并在后台拉全量
    const taskStore = useTaskStore()
    taskStore.bindSyncEngine()
    await taskStore.refreshFromLocal()
    void syncEngine.start()
    void taskStore.bootstrap()
  }

  app.mount('#app')
  console.log('[main] App mounted')
}

bootstrap()
