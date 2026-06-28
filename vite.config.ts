import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => {
  /**
   * Web 构建：mode = 'web' → 完整 PWA + 离线支持
   * Capacitor 构建：mode = 'capacitor' → 精简构建，相对路径，无 PWA（WebView 自带离线能力）
   */
  const isCapacitor = mode === 'capacitor'

  return {
    base: './', // 相对路径，兼容 Capacitor file:// 协议和 Web 部署

    plugins: [
      react(),
      tailwindcss(),
      // 仅 Web 构建启用 PWA；Capacitor 构建跳过（避免 SW 与 WebView 冲突）
      ...(isCapacitor
        ? []
        : [
            VitePWA({
              registerType: 'autoUpdate',
              includeAssets: ['favicon.svg'],
              manifest: {
                name: '四时有序',
                short_name: '四时有序',
                description: '四象限时间管理，让每一天四时有序',
                theme_color: '#F2A7B3',
                background_color: '#FFF5F5',
                display: 'standalone',
                start_url: './',
                scope: './',
                orientation: 'any',
                categories: ['productivity', 'utilities'],
                icons: [
                  {
                    src: 'icon-192.png',
                    sizes: '192x192',
                    type: 'image/png',
                  },
                  {
                    src: 'icon-512.png',
                    sizes: '512x512',
                    type: 'image/png',
                    purpose: 'any maskable',
                  },
                  {
                    src: 'favicon.svg',
                    sizes: 'any',
                    type: 'image/svg+xml',
                    purpose: 'any',
                  },
                ],
              },
              workbox: {
                globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
              },
            }),
          ]),
    ],

    // 开发服务器绑定所有网络接口（局域网设备可访问）
    server: {
      host: '0.0.0.0',
    },
  }
})
