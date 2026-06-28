import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/admin/login',
      name: 'adminLogin',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/admin',
      redirect: '/admin/dashboard',
    },
    {
      path: '/admin/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { requiresAuth: true, title: '仪表盘' },
    },
    {
      path: '/admin/users',
      name: 'users',
      component: () => import('@/views/UserListView.vue'),
      meta: { requiresAuth: true, title: '用户管理' },
    },
    {
      path: '/admin/users/:uuid',
      name: 'userDetail',
      component: () => import('@/views/UserDetailView.vue'),
      meta: { requiresAuth: true, title: '用户详情' },
    },
    {
      path: '/admin/audit',
      name: 'audit',
      component: () => import('@/views/AuditView.vue'),
      meta: { requiresAuth: true, title: '审计日志' },
    },
    {
      path: '/admin/login-logs',
      name: 'loginLogs',
      component: () => import('@/views/LoginLogView.vue'),
      meta: { requiresAuth: true, title: '登录日志' },
    },
    {
      path: '/admin/ip-blacklist',
      name: 'ipBlacklist',
      component: () => import('@/views/IpBlacklistView.vue'),
      meta: { requiresAuth: true, title: 'IP 黑名单' },
    },
    {
      path: '/admin/feedback',
      name: 'feedback',
      component: () => import('@/views/FeedbackView.vue'),
      meta: { requiresAuth: true, title: '反馈管理' },
    },
    {
      path: '/admin/sensitive-words',
      name: 'sensitiveWords',
      component: () => import('@/views/SensitiveWordView.vue'),
      meta: { requiresAuth: true, title: '敏感词管理' },
    },
    {
      path: '/admin/announcements',
      name: 'announcements',
      component: () => import('@/views/AnnouncementView.vue'),
      meta: { requiresAuth: true, title: '公告管理' },
    },
    {
      path: '/admin/config',
      name: 'config',
      component: () => import('@/views/ConfigView.vue'),
      meta: { requiresAuth: true, title: '系统配置' },
    },
    {
      path: '/admin/tasks',
      name: 'adminTasks',
      component: () => import('@/views/TaskListView.vue'),
      meta: { requiresAuth: true, title: '任务管理' },
    },
    {
      path: '/admin/tags',
      name: 'adminTags',
      component: () => import('@/views/TagListView.vue'),
      meta: { requiresAuth: true, title: '标签管理' },
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('admin_access_token')
  if (to.meta.requiresAuth && !token) {
    next({ name: 'adminLogin' })
  } else if (to.meta.guest && token) {
    next({ name: 'dashboard' })
  } else {
    next()
  }
})

export default router
