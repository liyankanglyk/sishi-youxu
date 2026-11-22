import { ref, onUnmounted } from 'vue'
import type { TaskOut } from '@/api/tasks'

const NOTIFICATIONS_STORAGE_KEY = 'sishi-notifications'
/** 去重状态按 uuid 持久化且与日期无关，拆成「已过期」与「今天/快过期」两组 */
const NEAR_EXPIRY_STORAGE_KEY = 'sishi-notified-near-expiry'
const EXPIRED_STORAGE_KEY = 'sishi-notified-expired'

/**
 * 通过 Web Notification API 实现本地到期提醒通知的组合式函数。
 *
 * 用法：
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
      // Notification 构造函数在某些环境下可能失败
    }
  }

  /** 本地日期差（天）：两端都归零到 0 点，避免 UTC 偏移导致凌晨漏报/误报。 */
  function daysUntilDue(dueDate: string): number {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
    const due = new Date(dueDate)
    const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate()).getTime()
    return Math.round((dueDay - today) / 86_400_000)
  }

  function readNotified(key: string): Set<string> {
    return new Set<string>(JSON.parse(localStorage.getItem(key) || '[]') as string[])
  }

  function writeNotified(key: string, ids: Set<string>) {
    localStorage.setItem(key, JSON.stringify([...ids]))
  }

  function checkAndNotify() {
    if (!enabled.value) return

    const near = readNotified(NEAR_EXPIRY_STORAGE_KEY)
    const expired = readNotified(EXPIRED_STORAGE_KEY)
    let nearDirty = false
    let expiredDirty = false

    const tasks = getTasks()
    for (const task of tasks) {
      if (task.completed || !task.dueDate || !task.uuid) continue
      const days = daysUntilDue(task.dueDate)
      if (days > 1) continue

      const dueStr = new Date(task.dueDate).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
      if (days < 0) {
        if (expired.has(task.uuid)) continue
        notify(`⏰ 已过期：${task.title}`, `截止日期：${dueStr}`, `task-${task.uuid}-expired`)
        expired.add(task.uuid)
        expiredDirty = true
      } else {
        if (near.has(task.uuid)) continue
        notify(
          days === 0 ? `⏰ 今天到期：${task.title}` : `⏰ 快过期：${task.title}`,
          task.note || `截止日期：${dueStr}`,
          `task-${task.uuid}-${days === 0 ? 'today' : 'soon'}`,
        )
        near.add(task.uuid)
        nearDirty = true
      }
    }

    if (nearDirty) writeNotified(NEAR_EXPIRY_STORAGE_KEY, near)
    if (expiredDirty) writeNotified(EXPIRED_STORAGE_KEY, expired)
  }

  function startPolling() {
    if (!enabled.value) return
    // 5 秒后做首次检查
    setTimeout(checkAndNotify, 5000)
    // 每 10 分钟定期检查
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
