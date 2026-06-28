<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAdminAuthStore } from '@/stores/adminAuth'

const router = useRouter()
const auth = useAdminAuthStore()

async function handleLogout() {
  await auth.logout()
  router.push('/admin/login')
}
</script>

<template>
  <el-container class="admin-layout">
    <!-- Sidebar -->
    <el-aside width="232px" class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-icon">
          <svg viewBox="0 0 32 32" width="28" height="28" fill="none">
            <rect x="2" y="2" width="12" height="12" rx="3" fill="#6366f1" opacity="0.9"/>
            <rect x="18" y="2" width="12" height="12" rx="3" fill="#818cf8" opacity="0.7"/>
            <rect x="2" y="18" width="12" height="12" rx="3" fill="#a5b4fc" opacity="0.6"/>
            <rect x="18" y="18" width="12" height="12" rx="3" fill="#c7d2fe" opacity="0.5"/>
          </svg>
        </div>
        <div class="brand-text">
          <span class="brand-name">四时有序</span>
          <span class="brand-tag">管理后台</span>
        </div>
      </div>

      <el-menu
        :default-active="$route.path"
        router
        background-color="transparent"
        text-color="#94a3b8"
        active-text-color="#e2e8f0"
        class="sidebar-menu"
      >
        <el-menu-item index="/admin/dashboard" class="menu-top">
          <template #title>
            <span class="menu-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
            </span>
            <span>仪表盘</span>
          </template>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <template #title>
            <span class="menu-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </span>
            <span>用户管理</span>
          </template>
        </el-menu-item>

        <el-sub-menu index="security">
          <template #title>
            <span class="menu-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </span>
            <span>安全中心</span>
          </template>
          <el-menu-item index="/admin/audit">
            <span>审计日志</span>
          </el-menu-item>
          <el-menu-item index="/admin/login-logs">
            <span>登录日志</span>
          </el-menu-item>
          <el-menu-item index="/admin/ip-blacklist">
            <span>IP 黑名单</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="content">
          <template #title>
            <span class="menu-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            </span>
            <span>内容管理</span>
          </template>
          <el-menu-item index="/admin/feedback">
            <span>反馈管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/sensitive-words">
            <span>敏感词管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/announcements">
            <span>公告管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/tasks">
            <span>任务管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/tags">
            <span>标签管理</span>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/admin/config">
          <template #title>
            <span class="menu-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            </span>
            <span>系统配置</span>
          </template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="sidebar-footer-avatar">
          {{ (auth.admin?.nickname || '管')[0] }}
        </div>
        <div class="sidebar-footer-info">
          <span class="sf-name">{{ auth.admin?.nickname || '管理员' }}</span>
          <span class="sf-role">超级管理员</span>
        </div>
      </div>
    </el-aside>

    <!-- Main -->
    <el-container class="main-area">
      <el-header height="56px" class="top-header">
        <div class="header-breadcrumb">
          <span class="hb-divider">/</span>
          <span class="hb-current">{{ $route.matched[$route.matched.length - 1]?.meta?.title || '' }}</span>
        </div>
        <div class="header-actions">
          <el-button text size="small" class="logout-btn" @click="handleLogout">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            <span>退出</span>
          </el-button>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
            <keep-alive :include="['UserListView']">
              <component :is="Component" />
            </keep-alive>
          </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.admin-layout {
  height: 100vh;
  display: flex;
}

/* ===== Sidebar ===== */
.sidebar {
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  flex-shrink: 0;
}

.sidebar-brand {
  padding: 20px 20px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.brand-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: 0.02em;
}

.brand-tag {
  font-size: 11px;
  color: #64748b;
  font-weight: 500;
  letter-spacing: 0.05em;
}

/* ===== Menu ===== */
.sidebar-menu {
  flex: 1;
  border-right: none !important;
  padding: 8px;
  overflow-y: auto;
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  border-radius: 8px;
  margin-bottom: 2px;
  height: 42px;
  line-height: 42px;
  font-size: 13.5px;
  transition: all 150ms ease;
}

.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255,255,255,0.06) !important;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: rgba(99, 102, 241, 0.15) !important;
  color: #e2e8f0 !important;
  font-weight: 600;
}

.menu-icon {
  margin-right: 10px;
  display: inline-flex;
  align-items: center;
  opacity: 0.7;
}

.sidebar-menu :deep(.el-menu-item.is-active .menu-icon) {
  opacity: 1;
  color: #a5b4fc;
}

/* Sub-menu children */
.sidebar-menu :deep(.el-sub-menu .el-menu) {
  background: transparent !important;
  padding: 2px 0;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item) {
  padding-left: 60px !important;
  height: 36px;
  line-height: 36px;
  font-size: 13px;
  color: #94a3b8;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item.is-active) {
  background: rgba(99, 102, 241, 0.12) !important;
  color: #c7d2fe !important;
}

/* ===== Sidebar Footer ===== */
.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,0.06);
  display: flex;
  align-items: center;
  gap: 10px;
}

.sidebar-footer-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.sidebar-footer-info {
  display: flex;
  flex-direction: column;
}

.sf-name {
  font-size: 12.5px;
  color: #e2e8f0;
  font-weight: 500;
}

.sf-role {
  font-size: 11px;
  color: #64748b;
}

/* ===== Main Area ===== */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ===== Top Header ===== */
.top-header {
  background: #fff;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}

.header-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  color: #94a3b8;
}

.hb-divider {
  color: #cbd5e1;
}

.hb-current {
  color: #1e293b;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
}

.logout-btn {
  color: #94a3b8 !important;
  font-size: 13px;
  gap: 6px;
  transition: color 150ms;
}

.logout-btn:hover {
  color: #ef4444 !important;
}

/* ===== Main Content ===== */
.main-content {
  background: #f1f5f9;
  padding: 24px;
  flex: 1;
  overflow-y: auto;
}
</style>
