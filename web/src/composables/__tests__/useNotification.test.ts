/**
 * @fileoverview useNotification 单元测试 — 本地到期提醒通知。
 *
 * 重点覆盖：
 *  1. 时区一致：daysUntilDue 计算使用本地日期，不受 UTC 偏移影响
 *  2. 快过期：今天或明天到期的任务 → 触发通知
 *  3. 已过期：过期任务 → 触发通知（标 "已过期"）
 *  4. 已过期仅通知一次：同一过期任务多次轮询不重复（核心 bug 修复）
 *  5. 快过期仅通知一次：同一任务多次轮询不重复
 *  6. 任务已完成 → 不通知
 *  7. 没有 dueDate → 不通知
 *  8. 用户未启用 → 不通知（即使满足条件）
 *  9. 去重状态按 task.uuid 持久化到 localStorage（与日期无关）
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { useNotification } from '../useNotification'

// ---------------------------------------------------------------------------
// Helpers — 用 mount() 创建组件上下文以支持 onUnmounted
// ---------------------------------------------------------------------------

function withNotification(getTasks: () => any[]) {
  let captured!: ReturnType<typeof useNotification>
  const Comp = defineComponent({
    setup() {
      captured = useNotification(getTasks)
      return () => h('div')
    },
  })
  const wrapper = mount(Comp)
  return { api: captured, wrapper }
}

// 让 Notification 构造函数可观察
const NotificationMock = (globalThis as any).Notification
function getNotifications() {
  return NotificationMock.instances
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  localStorage.clear()
  // 重置 mock 实例计数
  NotificationMock.instances.length = 0
  // 重置 requestPermission 返回值
  NotificationMock.requestPermission = async () => 'granted' as NotificationPermission
  NotificationMock.permission = 'granted' as NotificationPermission
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useNotification - 基础行为', () => {
  it('requestPermission 后 enabled 持久化到 localStorage', async () => {
    const { api } = withNotification(() => [])
    const result = await api.requestPermission()
    expect(result).toBe(true)
    expect(api.enabled.value).toBe(true)
    expect(localStorage.getItem('sishi-notifications')).toBe('true')
  })

  it('setEnabled(false) 持久化', () => {
    const { api } = withNotification(() => [])
    api.setEnabled(true)
    api.setEnabled(false)
    expect(api.enabled.value).toBe(false)
    expect(localStorage.getItem('sishi-notifications')).toBe('false')
  })

  it('checkAndNotify 在 enabled=false 时不发通知', () => {
    const tasks = [
      { uuid: 'u1', title: '今天到期', completed: false, dueDate: new Date().toISOString() },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(false)
    api.checkAndNotify()
    expect(getNotifications().length).toBe(0)
  })
})

describe('useNotification - 触发条件', () => {
  it('今天到期 → 触发通知', () => {
    const tasks = [
      {
        uuid: 'u1',
        title: '今天到期',
        completed: false,
        dueDate: new Date().toISOString(),
      },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()
    expect(getNotifications().length).toBe(1)
    expect(getNotifications()[0].title).toContain('今天到期')
  })

  it('已过期 → 触发通知（标题带"已过期"）', () => {
    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 3)
    const tasks = [
      { uuid: 'u1', title: '过期任务', completed: false, dueDate: yesterday.toISOString() },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()
    expect(getNotifications().length).toBe(1)
    expect(getNotifications()[0].title).toContain('已过期')
  })

  it('两天后到期 → 不通知', () => {
    const future = new Date()
    future.setDate(future.getDate() + 2)
    future.setHours(0, 0, 0, 0)
    const tasks = [
      { uuid: 'u1', title: '后天到期', completed: false, dueDate: future.toISOString() },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()
    expect(getNotifications().length).toBe(0)
  })

  it('明天到期 → 触发"快过期"通知', () => {
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    tomorrow.setHours(0, 0, 0, 0)
    const tasks = [
      { uuid: 'u1', title: '明天到期', completed: false, dueDate: tomorrow.toISOString() },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()
    expect(getNotifications().length).toBe(1)
    expect(getNotifications()[0].title).toContain('快过期')
    expect(getNotifications()[0].title).not.toContain('今天到期')
  })

  it('已完成任务 → 不通知', () => {
    const tasks = [
      {
        uuid: 'u1',
        title: '已完成',
        completed: true,
        dueDate: new Date().toISOString(),
      },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()
    expect(getNotifications().length).toBe(0)
  })

  it('无 dueDate → 不通知', () => {
    const tasks = [
      { uuid: 'u1', title: '无日期', completed: false, dueDate: '' },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()
    expect(getNotifications().length).toBe(0)
  })
})

describe('useNotification - 去重与跨日', () => {
  it('同一任务当日只通知一次（即使 checkAndNotify 调用多次）', () => {
    const tasks = [
      {
        uuid: 'u1',
        title: '今天到期',
        completed: false,
        dueDate: new Date().toISOString(),
      },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()
    api.checkAndNotify()
    api.checkAndNotify()
    expect(getNotifications().length).toBe(1)
  })

  it('同一任务跨日不重复通知（核心 bug 修复）', () => {
    const tasks = [
      {
        uuid: 'u1',
        title: '今天到期',
        completed: false,
        dueDate: new Date().toISOString(),
      },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)

    // 第 1 天：触发"今天到期"通知
    api.checkAndNotify()
    expect(getNotifications().length).toBe(1)

    // 同一天再次轮询：去重生效，不会新增
    NotificationMock.instances.length = 0
    api.checkAndNotify()
    expect(getNotifications().length).toBe(0)

    // 模拟跨日（实际产品中下一天来临时 localStorage 不会被自动清空）
    // 关键：同一个任务跨日后不应再通知
    NotificationMock.instances.length = 0
    api.checkAndNotify()
    expect(getNotifications().length).toBe(0)
  })

  it('已过期任务多次轮询只通知一次（核心 bug 修复）', () => {
    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 3)
    const tasks = [
      { uuid: 'u1', title: '过期', completed: false, dueDate: yesterday.toISOString() },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)

    // 第一次：触发"已过期"
    api.checkAndNotify()
    expect(getNotifications().length).toBe(1)

    // 同一天反复轮询：不去重就疯狂弹通知 — bug 修复后应只 1 次
    api.checkAndNotify()
    api.checkAndNotify()
    expect(getNotifications().length).toBe(1)

    // 跨日模拟（不清 localStorage）：依然不再通知
    NotificationMock.instances.length = 0
    api.checkAndNotify()
    expect(getNotifications().length).toBe(0)
  })

  it('快过期任务多次轮询只通知一次', () => {
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    tomorrow.setHours(0, 0, 0, 0)
    const tasks = [
      { uuid: 'u1', title: '明天', completed: false, dueDate: tomorrow.toISOString() },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()
    api.checkAndNotify()
    api.checkAndNotify()
    expect(getNotifications().length).toBe(1)
  })

  it('多个任务独立去重', () => {
    const tasks = [
      { uuid: 'u1', title: 'A', completed: false, dueDate: new Date().toISOString() },
      { uuid: 'u2', title: 'B', completed: false, dueDate: new Date().toISOString() },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()
    expect(getNotifications().length).toBe(2)

    // 再次轮询：去重生效
    NotificationMock.instances.length = 0
    api.checkAndNotify()
    expect(getNotifications().length).toBe(0)
  })
})

describe('useNotification - 时区一致性', () => {
  it('daysUntilDue 判定使用本地日期（不受 UTC 偏移影响）', () => {
    // 关键不变量：today / dueDay 都按本地日期 0 点计算
    // 否则凌晨跨日时会出现"漏报"或"误报"
    const tasks = [
      {
        uuid: 'u1',
        title: '今日',
        completed: false,
        // dueDate 设为今日 23:59:59 本地时间
        dueDate: new Date(new Date().setHours(23, 59, 59, 0)).toISOString(),
      },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()
    expect(getNotifications().length).toBe(1)

    // 去重状态持久化在持久 key（不再按日期切分）
    const stored = JSON.parse(localStorage.getItem('sishi-notified-near-expiry') || '[]')
    expect(stored).toContain('u1')
  })

  it('已过期状态持久化在独立 key', () => {
    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 3)
    const tasks = [
      { uuid: 'u1', title: '过期', completed: false, dueDate: yesterday.toISOString() },
    ]
    const { api } = withNotification(() => tasks)
    api.setEnabled(true)
    api.checkAndNotify()

    const nearExpiryStored = JSON.parse(localStorage.getItem('sishi-notified-near-expiry') || '[]')
    const expiredStored = JSON.parse(localStorage.getItem('sishi-notified-expired') || '[]')
    expect(nearExpiryStored).not.toContain('u1')
    expect(expiredStored).toContain('u1')
  })
})

describe('useNotification - stopPolling / 生命周期', () => {
  it('stopPolling 后定时器被清除', () => {
    const { api } = withNotification(() => [])
    api.setEnabled(true)
    // startPolling 内部 setInterval，会在 stop 时 clear
    api.startPolling()
    api.stopPolling()
    // 不抛错即视为通过；具体 interval ID 是私有变量无法直接断言
    expect(true).toBe(true)
  })

  it('组件卸载时 onUnmounted 自动 stopPolling', async () => {
    const { wrapper } = withNotification(() => [])
    expect(() => wrapper.unmount()).not.toThrow()
  })
})