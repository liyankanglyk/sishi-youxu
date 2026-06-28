import { ref, onUnmounted } from 'vue'
import type { TaskOut } from '@/api/tasks'

const NOTIFICATIONS_STORAGE_KEY = 'sishi-notifications'
const NOTIFIED_KEY_PREFIX = 'sishi-notified-'

/**
 * Composable for local due-date reminder notifications via Web Notification API.
 *
 * Usage:
 *   const { enabled, requestPermission, startPolling, stopPolling } = useNotification(getTasks)
 *   startPolling()
 */
export function useNotification(getTasks: () => TaskOut[]) {
  const enabled = ref(localStorage.getItem(NOTIFICATIONS_STORAGE_KEY) === 'true')
  let intervalId: ReturnType<typeof setInterval> | null = null

  function persist() {
    localStorage.setItem(NOTIFICATIONS_STORAGE_KEY, String(enabled.value))
  }

  async function requestPermission(): Promise<boolean> {
    if (!('Notification' in window)) {
      alert('此浏览器不支持通知功能')
      return false
    }
    if (Notification.permission === 'denied') {
      alert('通知权限已被拒绝，请在浏览器设置中手动开启')
      return false
    }
    const result = await Notification.requestPermission()
    enabled.value = result === 'granted'
    persist()
    return enabled.value
  }

  function setEnabled(val: boolean) {
    enabled.value = val
    persist()
    if (val) {
      startPolling()
    } else {
      stopPolling()
    }
  }

  function notify(title: string, body: string, tag: string) {
    if (!enabled.value || Notification.permission !== 'granted') return
    try {
      new Notification(title, { body, icon: '/favicon.ico', tag })
    } catch {
      // Notification constructor may fail in some environments
    }
  }

  function checkAndNotify() {
    if (!enabled.value) return

    const todayKey = new Date().toISOString().slice(0, 10)
    const notifiedKey = NOTIFIED_KEY_PREFIX + todayKey
    const notifiedIds = new Set(JSON.parse(localStorage.getItem(notifiedKey) || '[]') as string[])

    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()

    const tasks = getTasks()
    for (const task of tasks) {
      if (task.completed || !task.dueDate || notifiedIds.has(task.uuid)) continue
      const due = new Date(task.dueDate)
      const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate()).getTime()

      if (dueDay <= today) {
        const isOverdue = dueDay < today
        notify(
          `⏰ ${isOverdue ? '已过期' : '今天到期'}：${task.title}`,
          task.note || `截止日期：${due.toLocaleDateString('zh-CN')}`,
          `task-${task.uuid}-${todayKey}`,
        )
        notifiedIds.add(task.uuid)
      }
    }

    localStorage.setItem(notifiedKey, JSON.stringify([...notifiedIds]))
  }

  function startPolling() {
    if (!enabled.value) return
    // Initial check after 5s
    setTimeout(checkAndNotify, 5000)
    // Periodic check every 10 minutes
    intervalId = setInterval(checkAndNotify, 10 * 60 * 1000)
  }

  function stopPolling() {
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  onUnmounted(stopPolling)

  return {
    enabled,
    requestPermission,
    setEnabled,
    startPolling,
    stopPolling,
    checkAndNotify,
  }
}
