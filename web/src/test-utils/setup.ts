/**
 * Vitest 全局 setup — 屏蔽浏览器环境差异、注入通用 mock。
 *
 *  - fake-indexeddb: Dexie 需要
 *  - Notification: happy-dom 默认未实现，避免 ReferenceError
 *  - window.matchMedia: 部分组件依赖
 */

import 'fake-indexeddb/auto'

// Notification API mock（happy-dom 部分版本未实现）
// 用类 + 静态实例数组，让测试可以断言"创建了几条通知"
const NotificationMock = class NotificationMock {
  static permission: NotificationPermission = 'default'
  static requestPermission = async () => 'granted' as NotificationPermission
  static instances: Array<{ title: string; options?: NotificationOptions }> = []
  title: string
  options?: NotificationOptions
  constructor(title: string, options?: NotificationOptions) {
    this.title = title
    this.options = options
    NotificationMock.instances.push({ title, options })
  }
  close() {}
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent(): boolean { return false }
}
;(globalThis as any).Notification = NotificationMock

// matchMedia mock（响应式组件可能用到）
if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })
}