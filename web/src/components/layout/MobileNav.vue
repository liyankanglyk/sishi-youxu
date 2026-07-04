<script setup lang="ts">
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
</script>

<template>
  <nav class="mobile-nav">
    <button class="nav-item" @click="ui.toggleMobileTaskList()">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <rect x="3" y="4" width="18" height="14" rx="2" />
        <line x1="7" y1="9" x2="17" y2="9" />
        <line x1="7" y1="13" x2="13" y2="13" />
      </svg>
      <span>任务列表</span>
    </button>

    <button class="nav-item active">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8">
        <rect x="2" y="2" width="9" height="9" rx="2" />
        <rect x="13" y="2" width="9" height="9" rx="2" />
        <rect x="2" y="13" width="9" height="9" rx="2" />
        <rect x="13" y="13" width="9" height="9" rx="2" />
      </svg>
      <span>四象限</span>
    </button>

    <button class="nav-item" @click="ui.toggleMobileStatsPanel()">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8">
        <rect x="2" y="16" width="5" height="6" rx="1" />
        <rect x="9.5" y="10" width="5" height="12" rx="1" />
        <rect x="17" y="4" width="5" height="18" rx="1" />
      </svg>
      <span>统计</span>
    </button>
  </nav>
</template>

<style scoped>
.mobile-nav {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: var(--glass-bg-light);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  z-index: 90;
  justify-content: space-around;
  align-items: center;
  padding: 0 4px;
  padding-bottom: env(safe-area-inset-bottom);
}

@media (max-width: 767px) {
  .mobile-nav {
    display: flex;
  }
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  border: none;
  background: none;
  color: var(--c-gray-400);
  cursor: pointer;
  padding: 4px 12px;
  border-radius: 10px;
  transition: color 0.15s;
  min-width: 64px;
  -webkit-tap-highlight-color: transparent;
}

.nav-item.active {
  color: var(--c-brand-500);
}

.nav-item span {
  font-size: 10px;
  font-weight: 500;
  line-height: 1;
}

:root.dark .mobile-nav {
  border-top-color: rgba(255, 255, 255, 0.08);
}
</style>
