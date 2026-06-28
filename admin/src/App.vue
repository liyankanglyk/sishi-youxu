<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AdminLayout from '@/components/layout/AdminLayout.vue'

const route = useRoute()
const isLoginPage = computed(() => route.name === 'adminLogin')
</script>

<template>
  <AdminLayout v-if="!isLoginPage" />
  <router-view v-else />
</template>

<style>
/* ===== Reset ===== */
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* ===== Design Tokens ===== */
:root {
  --font-sans: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  --font-mono: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', Consolas, monospace;
  --color-bg: #f1f5f9;
  --color-surface: #ffffff;
  --color-border: #e2e8f0;
  --color-text: #1e293b;
  --color-text-secondary: #64748b;
  --color-text-muted: #94a3b8;
  --color-primary: #6366f1;
  --color-primary-light: #818cf8;
  --color-primary-bg: #eef2ff;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-info: #3b82f6;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.06);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.08);
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 250ms cubic-bezier(0.4, 0, 0.2, 1);
}

body {
  font-family: var(--font-sans);
  font-size: 14px;
  color: var(--color-text);
  background: var(--color-bg);
  min-height: 100vh;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ===== Scrollbar ===== */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* ===== Element Plus Global Overrides ===== */

/* Card */
.el-card {
  border-radius: var(--radius-md) !important;
  border: 1px solid var(--color-border) !important;
  box-shadow: var(--shadow-sm) !important;
  transition: box-shadow var(--transition-normal);
}
.el-card:hover {
  box-shadow: var(--shadow-md) !important;
}
.el-card__header {
  padding: 16px 20px !important;
  font-weight: 600;
  font-size: 15px;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border) !important;
}
.el-card__body {
  padding: 20px !important;
}

/* Table */
.el-table {
  border-radius: var(--radius-md);
  overflow: hidden;
  --el-table-border-color: var(--color-border);
}
.el-table th.el-table__cell {
  background: #f8fafc !important;
  color: var(--color-text-secondary);
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 2px solid var(--color-border) !important;
}
.el-table .el-table__row:hover > td.el-table__cell {
  background: #f8fafc !important;
}
.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background: #fafbfc;
}

/* Button */
.el-button {
  border-radius: var(--radius-sm) !important;
  font-weight: 500 !important;
  transition: all var(--transition-fast) !important;
}
.el-button--primary {
  --el-button-bg-color: var(--color-primary);
  --el-button-border-color: var(--color-primary);
  --el-button-hover-bg-color: var(--color-primary-light);
  --el-button-hover-border-color: var(--color-primary-light);
}
.el-button--primary:active {
  transform: scale(0.97);
}

/* Input */
.el-input__wrapper {
  border-radius: var(--radius-sm) !important;
  box-shadow: 0 0 0 1px var(--color-border) inset !important;
  transition: box-shadow var(--transition-fast);
}
.el-input__wrapper:hover {
  box-shadow: 0 0 0 1px #cbd5e1 inset !important;
}
.el-input__wrapper.is-focus,
.el-textarea__inner:focus {
  box-shadow: 0 0 0 2px var(--color-primary-bg) inset, 0 0 0 1px var(--color-primary) inset !important;
}
.el-textarea__inner {
  border-radius: var(--radius-sm) !important;
}

/* Select */
.el-select .el-input__wrapper {
  border-radius: var(--radius-sm) !important;
}

/* Tag */
.el-tag {
  border-radius: 4px !important;
  font-weight: 500 !important;
  letter-spacing: 0.01em;
}

/* Pagination */
.el-pagination {
  --el-pagination-button-bg-color: var(--color-surface);
}
.el-pagination .el-pager li {
  border-radius: var(--radius-sm) !important;
}

/* Dialog */
.el-dialog {
  border-radius: var(--radius-lg) !important;
  overflow: hidden;
}
.el-dialog__header {
  padding: 20px 24px !important;
  border-bottom: 1px solid var(--color-border);
}
.el-dialog__body {
  padding: 24px !important;
}
.el-dialog__footer {
  padding: 16px 24px !important;
  border-top: 1px solid var(--color-border);
}

/* Message Box */
.el-message-box {
  border-radius: var(--radius-lg) !important;
}

/* Alert */
.el-alert {
  border-radius: var(--radius-sm) !important;
}

/* Divider */
.el-divider__text {
  font-weight: 600;
  color: var(--color-text-secondary);
}

/* Switch */
.el-switch {
  --el-switch-on-color: var(--color-primary);
}

/* Radio Button */
.el-radio-button__inner {
  transition: all var(--transition-fast);
}

/* Statistic */
.el-statistic__head {
  color: var(--color-text-secondary) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
}
.el-statistic__number {
  font-size: 28px !important;
  font-weight: 700 !important;
}

/* Menu overrides handled in AdminLayout scoped */

/* Date Picker */
.el-date-editor {
  --el-date-editor-daterange-width: 260px;
}
</style>
