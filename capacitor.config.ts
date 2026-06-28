import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.xiaohua.sishiyouxu',
  appName: '四时有序',
  webDir: 'dist',

  // 开发服务器（npm run dev 时用）
  server: process.env.CAPACITOR_DEV
    ? {
        url: 'http://10.0.2.2:5173', // Android 模拟器 → 宿主机
        cleartext: true,
      }
    : undefined,

  // Android 专属配置
  android: {
    allowMixedContent: true,
    captureInput: true,
    webContentsDebuggingEnabled: false,
  },

  // iOS 专属配置
  ios: {
    contentInset: 'automatic',
    scheme: 'SishiYouxu',
  },
}

export default config
