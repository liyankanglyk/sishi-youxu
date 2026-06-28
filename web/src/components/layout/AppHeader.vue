<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTaskStore } from '@/stores/task'
import { useUiStore } from '@/stores/ui'
import { notificationApi, type NotificationOut } from '@/api/notifications'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const store = useTaskStore()
const ui = useUiStore()
const toast = useToast()

const isHome = computed(() => route.path === '/')

const searchText = ref(store.searchQuery)
const unreadCount = ref(0)
const notifOpen = ref(false)
const notifications = ref<NotificationOut[]>([])
const notifLoading = ref(false)
const notifMeta = ref<{ total: number; page: number; pageSize: number; hasMore: boolean } | null>(null)
const notifLoadingMore = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

watch(() => store.searchQuery, (v) => { searchText.value = v })

onMounted(() => {
  if (auth.isAuthenticated) {
    fetchUnreadCount()
    pollTimer = setInterval(fetchUnreadCount, 30_000)
  }
  document.addEventListener('click', onDocClick)
})

onUnmounted(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  document.removeEventListener('click', onDocClick)
})

function onDocClick() {
  if (notifOpen.value) notifOpen.value = false
}

async function fetchUnreadCount() {
  if (!auth.isAuthenticated) return
  try {
    const { data } = await notificationApi.unreadCount()
    unreadCount.value = (data as any)?.unreadCount ?? 0
  } catch { /* ignore */ }
}

async function toggleNotifPanel() {
  notifOpen.value = !notifOpen.value
  if (notifOpen.value) {
    notifLoading.value = true
    try {
      const { data } = await notificationApi.list({ pageSize: 10 })
      const payload = data as any
      notifications.value = payload?.items ?? []
      notifMeta.value = payload?.meta ?? null
    } catch { /* ignore */ }
    finally { notifLoading.value = false }
  }
}

async function loadMore() {
  if (notifLoadingMore.value || !notifMeta.value?.hasMore) return
  notifLoadingMore.value = true
  try {
    const nextPage = (notifMeta.value?.page ?? 1) + 1
    const { data } = await notificationApi.list({ page: nextPage, pageSize: 10 })
    const payload = data as any
    const items = payload?.items ?? []
    notifications.value.push(...items)
    notifMeta.value = payload?.meta ?? null
  } catch { /* ignore */ }
  finally { notifLoadingMore.value = false }
}

function handleNotifClick(n: NotificationOut) {
  markRead(n.uuid)
  // Task reminders: open the task modal
  if (n.kind === 'task_reminder' && n.taskUuid) {
    notifOpen.value = false
    store.setEditingUuid(n.taskUuid)
  }
}

async function markRead(uuid: string) {
  try {
    await notificationApi.markRead(uuid)
    const n = notifications.value.find(x => x.uuid === uuid)
    if (n) n.isRead = true
    if (unreadCount.value > 0) unreadCount.value--
  } catch { /* ignore */ }
}

async function markAllRead() {
  try {
    await notificationApi.markAllRead()
    notifications.value.forEach(n => { n.isRead = true })
    unreadCount.value = 0
  } catch (e: any) {
    toast.error(e.message || '操作失败')
  }
}

async function deleteNotif(uuid: string, isRead: boolean) {
  try {
    await notificationApi.delete(uuid)
    notifications.value = notifications.value.filter(n => n.uuid !== uuid)
    if (notifMeta.value) notifMeta.value.total--
    if (!isRead && unreadCount.value > 0) unreadCount.value--
  } catch { /* ignore */ }
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}天前`
  const d = new Date(iso)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

function notifKindIcon(kind: string): string {
  return kind === 'task_reminder' ? '⏰' : '📢'
}

function notifKindLabel(kind: string): string {
  return kind === 'task_reminder' ? '任务提醒' : '系统公告'
}

function onSearchEnter() {
  store.setSearchQuery(searchText.value.trim())
}

function focusSearch() {
  const input = document.getElementById('header-search-input')
  input?.focus()
}

if (typeof window !== 'undefined') {
  ;(window as any).__focusHeaderSearch = focusSearch
}

// ── Toolbar actions ──
async function handleNotifToggle() {
  if (ui.notificationsEnabled) {
    ui.setNotificationsEnabled(false)
  } else {
    if (!('Notification' in window)) { alert('此浏览器不支持通知功能'); return }
    if (Notification.permission === 'denied') { alert('通知权限已被拒绝，请在浏览器设置中手动开启'); return }
    const result = await Notification.requestPermission()
    ui.setNotificationsEnabled(result === 'granted')
  }
}

function handleNewTask() { store.setCreating(true, 2, 2) }
function handleUndo() { store.undo().catch(() => {}) }
function handleRedo() { store.redo().catch(() => {}) }
function handleExport() { store.exportData(); toast.success('已导出备份文件') }
function handleImport() { ui.triggerImport() }
</script>

<template>
  <header class="app-header glass-header" :class="{ 'is-mobile': ui.isMobile }">
    <!-- Logo -->
    <router-link to="/" class="logo" :class="{ 'logo-hide': ui.isMobile && ui.showMobileSearch }">
      <svg class="logo-icon" viewBox="0 0 44 44" width="28" height="28" fill="none" aria-hidden="true">
        <rect x="2" y="2" width="40" height="40" rx="9" :fill="ui.theme === 'dark' ? '#27272A' : '#18181B'" />
        <rect x="4.5" y="4.5" width="16" height="16" rx="4.5" fill="#DAE5F0" />
        <rect x="23.5" y="4.5" width="16" height="16" rx="4.5" fill="#F6DFE0" />
        <rect x="4.5" y="23.5" width="16" height="16" rx="4.5" fill="#DDE8DC" />
        <rect x="23.5" y="23.5" width="16" height="16" rx="4.5" fill="#F9EAD6" />
      </svg>
      <span class="logo-text">四时有序</span>
    </router-link>

    <!-- Desktop search -->
    <div v-if="!ui.isMobile && auth.isAuthenticated" class="header-center">
      <div class="search-box" @click="focusSearch">
        <svg class="search-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/>
          <path d="m21 21-4.35-4.35"/>
        </svg>
        <input
          id="header-search-input"
          v-model="searchText"
          type="text"
          class="search-input"
          placeholder="搜索任务..."
          @keydown.enter="onSearchEnter"
          @input="store.setSearchQuery(searchText.trim())"
        />
        <kbd v-if="!searchText" class="search-kbd">/</kbd>
      </div>
    </div>

    <!-- Desktop toolbar (home page only) -->
    <div v-if="!ui.isMobile && isHome && auth.isAuthenticated" class="header-toolbar">
      <div class="toolbar-group">
        <button class="icon-btn" :disabled="!store.undoStack.length" title="撤销 (Ctrl+Z)" @click="handleUndo">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 6L1 9l3 3"/><path d="M2 9h8a4 4 0 014 4v0"/></svg>
        </button>
        <button class="icon-btn" :disabled="!store.redoStack.length" title="重做 (Ctrl+Shift+Z)" @click="handleRedo">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 6l3 3-3 3"/><path d="M14 9H6a4 4 0 00-4 4v0"/></svg>
        </button>
      </div>

      <div class="toolbar-sep" />

      <button
        class="icon-btn density-icon-btn"
        :class="`density-${store.viewDensity}`"
        title="切换密度 (D)"
        @click="store.cycleViewDensity()"
      >
        <span class="density-bar d1" />
        <span class="density-bar d2" />
        <span class="density-bar d3" />
      </button>

      <div class="toolbar-sep" />

      <button
        class="icon-btn today-btn"
        :class="{ active: store.focusToday }"
        title="今日焦点"
        @click="store.setFocusToday(!store.focusToday)"
      >
        📌
      </button>

      <button class="new-task-btn" @click="handleNewTask">+ 新建</button>

      <div class="toolbar-sep" />

      <button class="icon-btn" title="从备份文件导入" @click="handleImport">
        <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 4l3 3-3 3M13 7H3M1 13h14"/></svg>
      </button>
      <button class="icon-btn" title="导出备份" @click="handleExport">
        <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 11l3-3-3-3M13 8H3M1 2h14v0"/></svg>
      </button>
    </div>

    <!-- Desktop right area -->
    <div v-if="!ui.isMobile" class="header-right">
      <template v-if="auth.isAuthenticated">
        <button v-if="isHome" class="icon-btn" :class="{ active: ui.leftSidebarWidth > 0 }" title="任务列表" @click="ui.toggleLeftSidebar()">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="2.5" y="3" width="11" height="10" rx="1.5"/><line x1="5" y1="6" x2="11" y2="6"/><line x1="5" y1="9" x2="9" y2="9"/></svg>
        </button>
        <button v-if="isHome" class="icon-btn" :class="{ active: ui.showStatsPanel }" title="统计面板" @click="ui.toggleStatsPanel()">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="1" y="11" width="3" height="4" rx="0.5"/><rect x="6.5" y="5" width="3" height="10" rx="0.5"/><rect x="12" y="2" width="3" height="13" rx="0.5"/></svg>
        </button>

        <button class="icon-btn" :title="ui.notificationsEnabled ? '关闭通知' : '开启通知'" @click="handleNotifToggle">
          {{ ui.notificationsEnabled ? '🔔' : '🔕' }}
        </button>

        <button class="icon-btn" :title="ui.theme === 'dark' ? '切换浅色模式' : '切换深色模式'" @click="ui.toggleTheme()">
          {{ ui.theme === 'dark' ? '☀️' : '🌙' }}
        </button>

        <div class="notif-trigger">
          <button
            class="icon-btn notification-btn"
            :class="{ 'has-unread': unreadCount > 0 }"
            @click.stop="toggleNotifPanel"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
            <span v-if="unreadCount" class="notif-dot">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
          </button>
          <Transition name="notif-drop">
            <div v-if="notifOpen" class="notif-dropdown" @click.stop>
              <!-- Header -->
              <div class="notif-header">
                <div class="notif-header-left">
                  <span class="notif-title">通知</span>
                  <span v-if="unreadCount" class="notif-count-badge">{{ unreadCount }} 条未读</span>
                </div>
                <button v-if="unreadCount" class="notif-mark-all" @click="markAllRead">全部已读</button>
              </div>

              <!-- Body -->
              <div class="notif-body">
                <!-- Loading skeleton -->
                <template v-if="notifLoading">
                  <div v-for="i in 3" :key="'sk'+i" class="notif-skeleton">
                    <div class="sk-avatar" />
                    <div class="sk-lines">
                      <div class="sk-line w-60" />
                      <div class="sk-line w-80" />
                      <div class="sk-line w-30" />
                    </div>
                  </div>
                </template>

                <!-- Item list -->
                <template v-else-if="notifications.length">
                  <div
                    v-for="n in notifications"
                    :key="n.uuid"
                    :class="['notif-item', { unread: !n.isRead, 'is-link': n.kind === 'task_reminder' && n.taskUuid }]"
                    @click="handleNotifClick(n)"
                  >
                    <span class="notif-item-icon">{{ notifKindIcon(n.kind) }}</span>
                    <div class="notif-item-content">
                      <div class="notif-item-head">
                        <span class="notif-item-title">{{ n.title }}</span>
                        <span :class="['notif-kind-badge', n.kind]">{{ notifKindLabel(n.kind) }}</span>
                      </div>
                      <div class="notif-item-body">{{ n.body }}</div>
                      <div class="notif-item-time">{{ timeAgo(n.createdAt) }}</div>
                    </div>
                    <span v-if="!n.isRead" class="notif-unread-dot" />
                    <button class="notif-delete-btn" title="删除" @click.stop="deleteNotif(n.uuid, n.isRead)">
                      <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                        <line x1="4" y1="4" x2="12" y2="12" /><line x1="12" y1="4" x2="4" y2="12" />
                      </svg>
                    </button>
                  </div>
                </template>

                <!-- Empty state -->
                <div v-else class="notif-empty">
                  <span class="notif-empty-icon">🔔</span>
                  <span class="notif-empty-text">暂无通知</span>
                  <span class="notif-empty-sub">新消息会在这里显示</span>
                </div>
              </div>

              <!-- Footer -->
              <div v-if="notifMeta?.hasMore" class="notif-footer">
                <button class="notif-load-more" :disabled="notifLoadingMore" @click="loadMore">
                  {{ notifLoadingMore ? '加载中...' : `加载更多 (${notifMeta.total - notifications.length} 条)` }}
                </button>
              </div>
            </div>
          </Transition>
        </div>

        <div class="user-chip" @click="router.push('/settings')">
          <span class="user-avatar">{{ auth.user?.nickname?.charAt(0) ?? '?' }}</span>
        </div>
      </template>
      <template v-else>
        <button class="text-btn" @click="router.push('/login')">登录</button>
      </template>
    </div>

    <!-- ── Mobile layout ── -->
    <template v-if="ui.isMobile && auth.isAuthenticated">
      <!-- Search icon -->
      <button class="icon-btn mobile-search-btn" @click="ui.showMobileSearch = true; searchText = ''">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
      </button>

      <!-- New task -->
      <button class="new-task-btn" @click="handleNewTask">+</button>

      <!-- Hamburger -->
      <button class="icon-btn hamburger-btn" :class="{ active: ui.showMobileOverflowMenu }" @click="ui.toggleMobileOverflowMenu()">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      <!-- Mobile search overlay -->
      <div v-if="ui.showMobileSearch" class="mobile-search-overlay">
        <input
          ref="mobileSearchInput"
          v-model="searchText"
          type="search"
          placeholder="搜索任务..."
          @keydown.enter="onSearchEnter(); ui.showMobileSearch = false"
          @input="store.setSearchQuery(searchText.trim())"
        />
        <button @click="ui.showMobileSearch = false; searchText = ''">取消</button>
      </div>
    </template>
  </header>

  <!-- Mobile overflow menu (Teleported to body) -->
  <Teleport to="body" v-if="ui.isMobile">
    <Transition name="mobile-menu">
      <div v-if="ui.showMobileOverflowMenu" class="mobile-menu-container">
        <div class="mobile-menu-scrim" @click="ui.closeMobileOverflowMenu()" />
        <div class="mobile-menu-panel">
          <div class="mobile-menu-header">
            <span>菜单</span>
            <button @click="ui.closeMobileOverflowMenu()">&times;</button>
          </div>
          <div class="mobile-menu-items">
            <!-- Undo / Redo -->
            <div class="menu-row">
              <button :class="{ 'is-disabled': !store.undoStack.length }" @click="handleUndo(); ui.closeMobileOverflowMenu()">
                <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 6L1 9l3 3"/><path d="M2 9h8a4 4 0 014 4v0"/></svg>
                撤销
              </button>
              <button :class="{ 'is-disabled': !store.redoStack.length }" @click="handleRedo(); ui.closeMobileOverflowMenu()">
                <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 6l3 3-3 3"/><path d="M14 9H6a4 4 0 00-4 4v0"/></svg>
                重做
              </button>
            </div>

            <!-- Density -->
            <button @click="store.cycleViewDensity()">
              <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>
              切换密度（{{ { compact: '紧凑', standard: '标准', detailed: '详细' }[store.viewDensity] }}）
            </button>

            <!-- Focus Today -->
            <button @click="store.setFocusToday(!store.focusToday)">
              📌 今日焦点
              <span v-if="store.focusToday" class="menu-badge-on">开</span>
              <span v-else class="menu-badge-off">关</span>
            </button>

            <!-- Import / Export -->
            <div class="menu-row">
              <button @click="handleImport(); ui.closeMobileOverflowMenu()">
                <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 4l3 3-3 3M13 7H3M1 13h14"/></svg>
                导入
              </button>
              <button @click="handleExport(); ui.closeMobileOverflowMenu()">
                <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 11l3-3-3-3M13 8H3M1 2h14v0"/></svg>
                导出
              </button>
            </div>

            <div class="menu-divider" />

            <!-- Sidebar toggles -->
            <button v-if="isHome" @click="ui.toggleMobileTaskList(); ui.closeMobileOverflowMenu()">
              <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2.5" y="3" width="11" height="10" rx="1.5"/><line x1="5" y1="6" x2="11" y2="6"/><line x1="5" y1="9" x2="9" y2="9"/></svg>
              任务列表
            </button>
            <button v-if="isHome" @click="ui.toggleMobileStatsPanel(); ui.closeMobileOverflowMenu()">
              <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="1" y="11" width="3" height="4" rx="0.5"/><rect x="6.5" y="5" width="3" height="10" rx="0.5"/><rect x="12" y="2" width="3" height="13" rx="0.5"/></svg>
              统计面板
            </button>

            <div class="menu-divider" />

            <!-- Notification -->
            <button @click="handleNotifToggle()">
              {{ ui.notificationsEnabled ? '🔔' : '🔕' }}
              通知（{{ ui.notificationsEnabled ? '开' : '关' }}）
            </button>

            <!-- Theme -->
            <button @click="ui.toggleTheme()">
              {{ ui.theme === 'dark' ? '☀️' : '🌙' }}
              {{ ui.theme === 'dark' ? '浅色模式' : '深色模式' }}
            </button>

            <!-- Settings -->
            <button @click="router.push('/settings'); ui.closeMobileOverflowMenu()">
              <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="8" cy="8" r="2.5"/><path d="M8 1.5v1M8 13.5v1M13.5 8h-1M3.5 8h-1M11.9 4.1l-.7.7M4.8 11.2l-.7.7M11.9 11.9l-.7-.7M4.8 4.8l-.7-.7"/></svg>
              设置
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ══════════════════════════════════════════ */
/* Base header                               */
/* ══════════════════════════════════════════ */

.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--header-height);
  display: flex;
  align-items: center;
  padding: 0 var(--s-4);
  z-index: 100;
  gap: var(--s-2);
}

.glass-header {
  background: var(--glass-bg-light);
  backdrop-filter: var(--glass-header);
  -webkit-backdrop-filter: var(--glass-header);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

@supports not (backdrop-filter: blur(1px)) {
  .glass-header { background: rgba(255, 255, 255, 0.95); }
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--t-body-size);
  font-weight: 700;
  color: var(--c-gray-900);
  text-decoration: none;
  letter-spacing: -0.01em;
  flex-shrink: 0;
}

.logo-icon {
  flex-shrink: 0;
}

.logo-text {
  white-space: nowrap;
}

/* ══════════════════════════════════════════ */
/* Search                                    */
/* ══════════════════════════════════════════ */

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 0 var(--s-2);
  min-width: 0;
}

.search-box {
  display: flex;
  align-items: center;
  background: var(--c-gray-100);
  border-radius: var(--r-input);
  padding: 0 10px;
  height: 36px;
  max-width: 320px;
  width: 100%;
  transition: background 0.2s, box-shadow 0.2s;
  cursor: text;
}
.search-box:focus-within {
  background: var(--surface-primary);
  box-shadow: 0 0 0 2px var(--c-brand-50), 0 0 0 1px var(--c-brand-500);
}

.search-icon { color: var(--c-gray-400); flex-shrink: 0; }

.search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  padding: 0 8px;
  font-size: 14px;
  color: var(--c-gray-900);
}
.search-input::placeholder { color: var(--c-gray-400); }

.search-kbd {
  font-size: 11px;
  background: var(--surface-primary);
  border: 1px solid var(--c-gray-300);
  border-radius: 3px;
  padding: 1px 5px;
  line-height: 1;
  color: var(--c-gray-400);
  font-family: inherit;
  flex-shrink: 0;
}

/* ══════════════════════════════════════════ */
/* Desktop toolbar                           */
/* ══════════════════════════════════════════ */

.header-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 2px;
}

.toolbar-sep {
  width: 1px;
  height: 18px;
  background: var(--c-gray-200);
  margin: 0 2px;
  flex-shrink: 0;
}

/* ══════════════════════════════════════════ */
/* Button styles                             */
/* ══════════════════════════════════════════ */

.header-right {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  flex-shrink: 0;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border: none;
  background: none;
  border-radius: var(--r-button);
  color: var(--c-gray-500);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: background 0.15s;
}
.icon-btn:hover:not(:disabled) { background: var(--c-gray-100); color: var(--c-gray-700); }
.icon-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.icon-btn.active { color: var(--c-brand-500); background: var(--c-brand-50); }

.today-btn { font-size: 14px; }
.today-btn.active {
  background: rgba(234, 88, 12, 0.1);
  color: var(--c-warning);
}

.new-task-btn {
  padding: 4px 12px;
  border: none;
  background: var(--c-brand-500);
  color: #fff;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}
.new-task-btn:hover { background: var(--c-brand-600); }

/* ══════════════════════════════════════════ */
/* Density icon                              */
/* ══════════════════════════════════════════ */

.density-icon-btn {
  display: flex;
  align-items: center;
  gap: 2px;
  justify-content: center;
}
.density-bar { width: 3px; background: var(--c-gray-400); border-radius: 1px; transition: background 0.15s, height 0.15s; }
.density-compact .d1 { height: 6px; }
.density-compact .d2 { height: 4px; }
.density-compact .d3 { height: 2px; }
.density-compact .density-bar { background: var(--c-gray-300); }
.density-standard .d1 { height: 10px; }
.density-standard .d2 { height: 7px; }
.density-standard .d3 { height: 4px; }
.density-detailed .d1 { height: 14px; }
.density-detailed .d2 { height: 10px; }
.density-detailed .d3 { height: 7px; }
.density-detailed .density-bar { background: var(--c-brand-500); }

/* ══════════════════════════════════════════ */
/* Notification bell + dropdown              */
/* ══════════════════════════════════════════ */

.notif-trigger { position: relative; }

.notif-dot {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 17px;
  height: 17px;
  border-radius: 8px;
  background: var(--c-danger);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
  line-height: 1;
  box-shadow: 0 0 0 2px var(--surface-primary);
}

/* Bell pulse when unread */
.notification-btn.has-unread {
  animation: bell-ring 3s ease-in-out infinite;
}

@keyframes bell-ring {
  0%, 100% { transform: rotate(0); }
  2%  { transform: rotate(12deg); }
  4%  { transform: rotate(-10deg); }
  6%  { transform: rotate(6deg); }
  8%  { transform: rotate(-4deg); }
  10% { transform: rotate(0); }
}

/* ── Dropdown ── */

.notif-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: -8px;
  width: 380px;
  max-height: 520px;
  background: var(--surface-primary);
  border: 1px solid var(--c-gray-200);
  border-radius: var(--r-modal);
  box-shadow: var(--sh-modal);
  display: flex;
  flex-direction: column;
  z-index: 150;
  overflow: hidden;
}

/* Transition */
.notif-drop-enter-active {
  transition: opacity 0.18s var(--ease-standard), transform 0.18s var(--ease-standard);
}
.notif-drop-leave-active {
  transition: opacity 0.12s var(--ease-standard), transform 0.12s var(--ease-standard);
}
.notif-drop-enter-from,
.notif-drop-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.97);
}

/* ── Header ── */

.notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 12px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-light);
}
.notif-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.notif-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--c-gray-900);
  letter-spacing: -0.01em;
}
.notif-count-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-brand-500);
  background: var(--c-brand-50);
  padding: 2px 8px;
  border-radius: 10px;
}
.notif-mark-all {
  font-size: 12px;
  font-weight: 500;
  border: none;
  background: none;
  color: var(--c-gray-400);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: color 0.15s, background 0.15s;
}
.notif-mark-all:hover {
  color: var(--c-brand-500);
  background: var(--c-brand-50);
}

/* ── Body ── */

.notif-body {
  flex: 1;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 6px;
}

/* ── Skeleton ── */

.notif-skeleton {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
}
.sk-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--c-gray-100);
  flex-shrink: 0;
  animation: sk-pulse 1.5s ease-in-out infinite;
}
.sk-lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 4px;
}
.sk-line {
  height: 10px;
  border-radius: 4px;
  background: var(--c-gray-100);
  animation: sk-pulse 1.5s ease-in-out infinite;
}
.sk-line.w-60 { width: 60%; }
.sk-line.w-80 { width: 80%; }
.sk-line.w-30 { width: 30%; }

@keyframes sk-pulse {
  0%, 100% { opacity: 0.5; }
  50%      { opacity: 1; }
}

/* ── Empty state ── */

.notif-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 16px;
  gap: 8px;
}
.notif-empty-icon {
  font-size: 36px;
  opacity: 0.6;
  margin-bottom: 4px;
}
.notif-empty-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-gray-500);
}
.notif-empty-sub {
  font-size: 12px;
  color: var(--c-gray-400);
}

/* ── Notification item ── */

.notif-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.12s;
  position: relative;
}
.notif-item:hover {
  background: var(--c-gray-50);
}
.notif-item.unread {
  background: var(--c-brand-50);
}
.notif-item.unread:hover {
  background: #E8EDFF;
}
:root.dark .notif-item.unread {
  background: rgba(46, 91, 255, 0.08);
}
:root.dark .notif-item.unread:hover {
  background: rgba(46, 91, 255, 0.13);
}

.notif-item-icon {
  font-size: 20px;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-gray-50);
  border-radius: 10px;
  margin-top: 1px;
}
:root.dark .notif-item-icon {
  background: var(--c-gray-100);
}

.notif-item-content {
  flex: 1;
  min-width: 0;
}

.notif-item-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
}

.notif-item-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-gray-900);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notif-kind-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 8px;
  flex-shrink: 0;
  line-height: 1.5;
}
.notif-kind-badge.system_announcement {
  color: var(--c-brand-500);
  background: var(--c-brand-50);
}
.notif-kind-badge.task_reminder {
  color: var(--c-warning);
  background: rgba(217, 119, 6, 0.08);
}

.notif-item-body {
  font-size: 12px;
  color: var(--c-gray-500);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 4px;
}

.notif-item-time {
  font-size: 11px;
  color: var(--c-gray-400);
}

/* Unread dot */
.notif-unread-dot {
  position: absolute;
  top: 16px;
  right: 12px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--c-brand-500);
  box-shadow: 0 0 0 2px var(--surface-primary);
}
:root.dark .notif-unread-dot {
  box-shadow: 0 0 0 2px var(--surface-primary);
}

/* Delete button */
.notif-delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  border: none;
  background: var(--c-gray-100);
  border-radius: 6px;
  color: var(--c-gray-400);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, background 0.15s;
  z-index: 2;
}
.notif-item:hover .notif-delete-btn {
  opacity: 1;
}
.notif-delete-btn:hover {
  color: var(--c-danger);
  background: rgba(220, 38, 38, 0.08);
}
/* Push unread dot left when delete btn is present */
.notif-item .notif-delete-btn ~ .notif-unread-dot {
  right: 30px;
}

/* Link indicator for task reminders */
.notif-item.is-link:hover .notif-item-title {
  color: var(--c-brand-500);
}

/* ── Footer ── */

.notif-footer {
  flex-shrink: 0;
  padding: 8px 14px 12px;
  border-top: 1px solid var(--border-light);
}
.notif-load-more {
  width: 100%;
  padding: 8px;
  border: none;
  background: var(--c-gray-50);
  color: var(--c-gray-500);
  font-size: 12px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.notif-load-more:hover:not(:disabled) {
  background: var(--c-gray-100);
  color: var(--c-gray-700);
}
.notif-load-more:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ══════════════════════════════════════════ */
/* User chip                                 */
/* ══════════════════════════════════════════ */

.user-chip { display: flex; align-items: center; cursor: pointer; }
.user-avatar {
  width: 30px; height: 30px;
  border-radius: 50%;
  background: var(--c-brand-500);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.text-btn {
  font-size: 14px;
  color: var(--c-brand-500);
  border: none;
  background: none;
  cursor: pointer;
  font-weight: 500;
}
.text-btn:hover { opacity: 0.8; }

/* ══════════════════════════════════════════ */
/* Mobile header                             */
/* ══════════════════════════════════════════ */

@media (max-width: 767px) {
  .app-header.is-mobile {
    padding: 0 var(--s-3);
    gap: var(--s-1);
  }

  .app-header.is-mobile .logo {
    width: auto;
    font-size: 15px;
    margin-right: auto;
  }
  .app-header.is-mobile .logo.logo-hide { display: none; }

  .app-header.is-mobile .icon-btn {
    width: 40px;
    height: 40px;
  }

  .app-header.is-mobile .new-task-btn {
    padding: 6px 14px;
    font-size: 14px;
    height: 36px;
    border-radius: 10px;
  }

  .app-header.is-mobile .hamburger-btn.active {
    background: var(--c-gray-100);
  }
}

/* ══════════════════════════════════════════ */
/* Mobile search overlay                     */
/* ══════════════════════════════════════════ */

.mobile-search-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 var(--s-3);
  background: var(--glass-bg-light);
  backdrop-filter: var(--glass-header);
  -webkit-backdrop-filter: var(--glass-header);
  z-index: 10;
}

.mobile-search-overlay input {
  flex: 1;
  height: 36px;
  border-radius: var(--r-input);
  border: 1px solid var(--c-gray-200);
  padding: 0 12px;
  font-size: 16px;
  background: var(--surface-primary);
  color: var(--c-gray-900);
  outline: none;
}

.mobile-search-overlay button {
  background: none;
  border: none;
  color: var(--c-brand-500);
  font-size: 15px;
  font-weight: 500;
  white-space: nowrap;
  cursor: pointer;
  padding: 6px 4px;
}
</style>

<!-- ══════════════════════════════════════════ -->
<!-- Mobile overflow menu (unscoped global)    -->
<!-- ══════════════════════════════════════════ -->

<style>
.mobile-menu-container {
  position: fixed;
  inset: 0;
  z-index: 250;
  display: flex;
  justify-content: flex-end;
}

.mobile-menu-scrim {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
}

.mobile-menu-panel {
  position: relative;
  width: min(300px, 80vw);
  height: 100%;
  background: var(--surface-primary);
  z-index: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.15);
}

.mobile-menu-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--border-light);
  font-weight: 600;
  font-size: 17px;
  color: var(--c-gray-900);
  flex-shrink: 0;
}
.mobile-menu-header button {
  width: 36px; height: 36px;
  font-size: 24px;
  border: none;
  background: none;
  cursor: pointer;
  border-radius: 8px;
  color: var(--c-gray-400);
  display: flex;
  align-items: center;
  justify-content: center;
}
.mobile-menu-header button:hover { background: var(--c-gray-100); }

.mobile-menu-items {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mobile-menu-items button {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 13px 16px;
  border: none;
  background: none;
  font-size: 15px;
  color: var(--c-gray-700);
  cursor: pointer;
  border-radius: 10px;
  text-align: left;
  transition: background 0.12s;
}
.mobile-menu-items button:hover { background: var(--c-gray-100); }
.mobile-menu-items button.is-disabled { opacity: 0.35; pointer-events: none; }

.mobile-menu-items .menu-row {
  display: flex;
  gap: 8px;
}
.mobile-menu-items .menu-row button {
  flex: 1;
  justify-content: center;
}

.menu-divider {
  height: 1px;
  background: var(--border-light);
  margin: 6px 12px;
}

.menu-badge-on {
  margin-left: auto;
  font-size: 11px;
  background: rgba(5, 150, 105, 0.1);
  color: var(--c-success);
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.menu-badge-off {
  margin-left: auto;
  font-size: 11px;
  background: var(--c-gray-100);
  color: var(--c-gray-400);
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

/* Menu transition */
.mobile-menu-enter-active,
.mobile-menu-leave-active {
  transition: opacity 0.25s ease;
}
.mobile-menu-enter-active .mobile-menu-panel,
.mobile-menu-leave-active .mobile-menu-panel {
  transition: transform 0.25s var(--ease-standard);
}
.mobile-menu-enter-from,
.mobile-menu-leave-to {
  opacity: 0;
}
.mobile-menu-enter-from .mobile-menu-panel,
.mobile-menu-leave-to .mobile-menu-panel {
  transform: translateX(100%);
}
</style>
