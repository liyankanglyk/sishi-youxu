import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

/**
 * Vitest 配置 — 复用 vite 的 alias 与插件。
 *
 *  - environment: happy-dom（轻量 DOM）
 *  - globals: false（显式 import vitest API，类型更严格）
 *  - setupFiles: 全局 mock（Notification、matchMedia、fake-indexeddb）
 */
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'happy-dom',
      globals: false,
      setupFiles: ['./src/test-utils/setup.ts'],
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      css: false,
    },
  }),
)