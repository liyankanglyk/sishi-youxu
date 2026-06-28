import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { initDatabase } from './db'
import { useAuthStore } from './stores/auth'

async function bootstrap() {
  // Initialize IndexedDB (offline-first storage)
  try {
    await initDatabase()
  } catch (e) {
    console.warn('[main] IndexedDB unavailable, running without offline support:', e)
  }

  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)
  app.use(router)

  // Hydrate auth state from localStorage before rendering
  const authStore = useAuthStore()
  authStore.initFromStorage()

  app.mount('#app')
  console.log('[main] App mounted')
}

bootstrap()
