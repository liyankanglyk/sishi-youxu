<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppToast from '@/components/common/AppToast.vue'
import ConfettiCanvas from '@/components/common/ConfettiCanvas.vue'
import { useTaskStore } from '@/stores/task'

const route = useRoute()
const isAuthPage = computed(() => route.meta.guest === true)
const taskStore = useTaskStore()
</script>

<template>
  <AppHeader v-if="!isAuthPage" />
  <main :class="{ 'has-header': !isAuthPage }">
    <router-view />
  </main>
  <AppToast />
  <ConfettiCanvas :active="!!taskStore.celebrationTitle" />
</template>

<style>
/* ── Global CSS Reset ── */
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  /* 灰阶 8 档 */
  --c-gray-50: #FAFAFA;
  --c-gray-100: #F4F4F5;
  --c-gray-200: #E4E4E7;
  --c-gray-300: #D4D4D8;
  --c-gray-400: #A1A1AA;
  --c-gray-500: #71717A;
  --c-gray-600: #52525B;
  --c-gray-700: #3F3F46;
  --c-gray-800: #27272A;
  --c-gray-900: #18181B;

  /* 品牌色 */
  --c-brand-50: #EEF2FF;
  --c-brand-500: #2E5BFF;
  --c-brand-600: #1E40D0;

  /* 语义色 */
  --c-success: #059669;
  --c-warning: #D97706;
  --c-danger: #DC2626;

  /* 象限色（浅色）*/
  --q1-bg: #F6DFE0;
  --q2-bg: #DAE5F0;
  --q3-bg: #F9EAD6;
  --q4-bg: #DDE8DC;

  /* 表面色 */
  --surface-primary: #FFFFFF;
  --surface-secondary: #FAFAFA;
  --border-light: #F1F5F9;

  /* 象限色（深色）*/
  --q1-bg-dark: #42282D;
  --q2-bg-dark: #1E283A;
  --q3-bg-dark: #3D2E23;
  --q4-bg-dark: #1C2D22;

  /* 字号 */
  --t-display-size: 26px;
  --t-title-size: 18px;
  --t-body-size: 15px;
  --t-caption-size: 13px;

  /* 间距 */
  --s-1: 4px;
  --s-2: 8px;
  --s-3: 12px;
  --s-4: 16px;
  --s-5: 20px;
  --s-6: 24px;

  /* 圆角 */
  --r-chip: 6px;
  --r-input: 10px;
  --r-button: 10px;
  --r-card: 14px;
  --r-modal: 20px;

  /* 阴影 */
  --sh-pop: 0 1px 3px rgba(0, 0, 0, 0.08);
  --sh-modal: 0 4px 16px rgba(0, 0, 0, 0.12);

  /* 动效 */
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);

  /* 玻璃 */
  --glass-header: blur(20px) saturate(180%);
  --glass-modal-scrim: blur(8px);
  --glass-toast: blur(16px) saturate(160%);
  --glass-bg-light: rgba(255, 255, 255, 0.72);
  --glass-bg-dark: rgba(24, 24, 27, 0.72);

  /* iOS 系统色板（标签 chip）*/
  --ios-blue: #007AFF;
  --ios-green: #34C759;
  --ios-indigo: #5856D6;
  --ios-orange: #FF9500;
  --ios-yellow: #FFCC00;
  --ios-teal: #5AC8FA;
  --ios-pink: #FF2D55;
  --ios-purple: #AF52DE;

  /* 布局 */
  --header-height: 56px;
  --toolbar-height: 44px;
  --task-card-max-width: 260px;

  /* 字体栈 */
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 16px;
  color: var(--c-gray-900);
  background: var(--c-gray-50);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ── Dark Theme ── */
:root.dark {
  --c-gray-50: #18181B;
  --c-gray-100: #27272A;
  --c-gray-200: #3F3F46;
  --c-gray-300: #52525B;
  --c-gray-400: #71717A;
  --c-gray-500: #A1A1AA;
  --c-gray-600: #D4D4D8;
  --c-gray-700: #E4E4E7;
  --c-gray-800: #F4F4F5;
  --c-gray-900: #FAFAFA;

  --c-brand-50: #1E1B4B;
  --c-brand-500: #818CF8;
  --c-brand-600: #A5B4FC;

  --c-success: #34D399;
  --c-warning: #FBBF24;
  --c-danger: #F87171;

  --q1-bg: var(--q1-bg-dark);
  --q2-bg: var(--q2-bg-dark);
  --q3-bg: var(--q3-bg-dark);
  --q4-bg: var(--q4-bg-dark);

  --sh-pop: 0 1px 3px rgba(0, 0, 0, 0.25);
  --sh-modal: 0 4px 16px rgba(0, 0, 0, 0.35);

  --glass-bg-light: var(--glass-bg-dark);

  --surface-primary: #1E1E24;
  --surface-secondary: #18181B;
  --border-light: #2A2A32;

  color-scheme: dark;
}

/* Mobile adjustments */
@media (max-width: 767px) {
  :root {
    --header-height: 48px;
    --t-display-size: 22px;
    --t-title-size: 16px;
    --t-body-size: 14px;
    --t-caption-size: 12px;
    --r-modal: 16px;
    --task-card-max-width: 100px;
  }
}

body {
  min-height: 100vh;
  overflow-x: hidden;
}

a {
  color: var(--c-brand-500);
  text-decoration: none;
}

button {
  font-family: inherit;
}

main.has-header {
  height: 100vh;
  padding-top: var(--header-height);
}

/* 全局 input 基础样式 */
input, textarea, select {
  font-family: inherit;
}

/* 玻璃降级 */
@supports not (backdrop-filter: blur(1px)) {
  .glass-header { background-color: rgba(255, 255, 255, 0.95); }
  .glass-toast { background-color: rgba(255, 255, 255, 0.95); }
}

/* 减少动画偏好 */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0s !important;
  }
}
</style>
