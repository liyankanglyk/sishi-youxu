<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppToast from '@/components/common/AppToast.vue'
import ConfettiCanvas from '@/components/common/ConfettiCanvas.vue'
import KeyboardHelp from '@/components/common/KeyboardHelp.vue'
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
  <KeyboardHelp />
  <ConfettiCanvas
    :active="!!taskStore.celebrationTitle"
    :origin-x="taskStore.celebrationOrigin?.x"
    :origin-y="taskStore.celebrationOrigin?.y"
    :intensity="taskStore.completionIntensity"
    :quadrant="taskStore.lastCompletedQuadrant ?? undefined"
  />
</template>

<style>
/* ── 全局 CSS 重置 ── */
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  /* 灰阶 8 档（原版紫调中性色） */
  --c-gray-50: #FFF8F6;
  --c-gray-100: #F7F1F0;
  --c-gray-200: #ECE5E8;
  --c-gray-300: #DCD4DE;
  --c-gray-400: #B6AEC0;
  --c-gray-500: #A6A0B2;
  --c-gray-600: #867E98;
  --c-gray-700: #6B6480;
  --c-gray-800: #575068;
  --c-gray-900: #4A4458;

  /* 品牌色 */
  --c-brand-50: #F5EFF9;
  --c-brand-500: #A07CCB;
  --c-brand-600: #8A63B8;

  /* 语义色 */
  --c-success: #34A06A;
  --c-warning: #D9822B;
  --c-danger: #E8615C;

  /* 象限强调色 */
  --q1-accent: #E88090;
  --q2-accent: #7FB895;
  --q3-accent: #8FAACB;
  --q4-accent: #E0BE45;

  /* 截止状态底色 */
  --danger-soft: #FDF0EF;
  --today-soft: #FFF7ED;
  --week-soft: #FFF5E4;
  --month-soft: #F6F0FB;
  --c-today: #EA580C;
  --c-week: #C97A1E;

  /* 象限色（浅色）*/
  --q1-bg: #FEF0F3;
  --q2-bg: #F0F8F3;
  --q3-bg: #F2F5FA;
  --q4-bg: #FFFCF2;

  /* 表面色 */
  --surface-primary: #FFFFFF;
  --surface-secondary: #FFFBF9;
  --border-light: #F1E9EC;

  /* 象限色（深色）*/
  --q1-bg-dark: #33202A;
  --q2-bg-dark: #1E3027;
  --q3-bg-dark: #1E2532;
  --q4-bg-dark: #302A1A;

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
  --r-chip: 8px;
  --r-input: 10px;
  --r-button: 12px;
  --r-card: 16px;
  --r-modal: 18px;

  /* 阴影 */
  --sh-pop: 0 1px 3px rgba(74, 68, 88, 0.09);
  --sh-modal: 0 6px 24px rgba(74, 68, 88, 0.14);

  /* 动效 */
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);

  /* 玻璃 */
  --glass-header: blur(20px) saturate(180%);
  --glass-modal-scrim: blur(8px);
  --glass-toast: blur(16px) saturate(160%);
  --glass-bg-light: rgba(255, 255, 255, 0.78);
  --glass-bg-dark: rgba(26, 22, 32, 0.78);

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
  --task-card-max-width: 220px;

  /* 字体栈 */
  font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
  font-size: 16px;
  color: var(--c-gray-900);
  background: var(--c-gray-50);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ── 深色主题 ── */
:root.dark {
  --c-gray-50: #1A1620;
  --c-gray-100: #221D2B;
  --c-gray-200: #2A2433;
  --c-gray-300: #3A3346;
  --c-gray-400: #4E4660;
  --c-gray-500: #8E86A2;
  --c-gray-600: #A69EB2;
  --c-gray-700: #C5BFD0;
  --c-gray-800: #D8D2E2;
  --c-gray-900: #E0DAE8;

  --c-brand-50: #2D2438;
  --c-brand-500: #B8A0D8;
  --c-brand-600: #C4A8D4;

  --c-success: #4FB286;
  --c-warning: #E0A458;
  --c-danger: #F08A86;

  --q1-accent: #C97A87;
  --q2-accent: #86B89A;
  --q3-accent: #9AB5D2;
  --q4-accent: #C9B468;

  --danger-soft: #3B2226;
  --today-soft: #38281C;
  --week-soft: #33291A;
  --month-soft: #2D2438;
  --c-today: #F5A26B;
  --c-week: #E0B878;

  --q1-bg: var(--q1-bg-dark);
  --q2-bg: var(--q2-bg-dark);
  --q3-bg: var(--q3-bg-dark);
  --q4-bg: var(--q4-bg-dark);

  --sh-pop: 0 1px 3px rgba(0, 0, 0, 0.30);
  --sh-modal: 0 6px 24px rgba(0, 0, 0, 0.45);

  --glass-bg-light: var(--glass-bg-dark);

  --surface-primary: #2A2433;
  --surface-secondary: #221D2B;
  --border-light: #302A3A;

  color-scheme: dark;
}

/* 移动端调整 */
@media (max-width: 767px) {
  :root {
    --header-height: 48px;
    --t-display-size: 22px;
    --t-title-size: 16px;
    --t-body-size: 14px;
    --t-caption-size: 12px;
    --r-modal: 16px;
    --task-card-max-width: 88px;
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
