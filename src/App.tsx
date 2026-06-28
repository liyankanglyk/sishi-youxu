import { useEffect, useState, useCallback, useRef } from 'react'
import { Capacitor } from '@capacitor/core'
import { LocalNotifications } from '@capacitor/local-notifications'
import confetti from 'canvas-confetti'
import { List, Plus, ArrowsOutCardinal, FileArrowDown, FileArrowUp, TagSimple, ChartBar, ArrowArcLeft, ArrowArcRight, Check, Trash, X, ArrowsClockwise } from '@phosphor-icons/react'
import { useStore } from './store/useStore'
import { QuadrantCanvas } from './components/QuadrantCanvas'
import { TaskList } from './components/TaskList'
import { TaskForm } from './components/TaskForm'
import { TagManager } from './components/TagManager'
import { StatsPanel } from './components/StatsPanel'
import { LoginPage } from './components/LoginPage'

type ImportStrategy = 'skip' | 'overwrite' | 'new'

function App() {
  const initialize = useStore((s) => s.initialize)
  const loading = useStore((s) => s.loading)
  const viewDensity = useStore((s) => s.viewDensity)
  const setViewDensity = useStore((s) => s.setViewDensity)
  const autoArrange = useStore((s) => s.autoArrange)
  const exportData = useStore((s) => s.exportData)
  const importData = useStore((s) => s.importData)
  const setCreating = useStore((s) => s.setCreating)
  const editingTaskId = useStore((s) => s.editingTaskId)
  const setEditingTaskId = useStore((s) => s.setEditingTaskId)
  const isListOpen = useStore((s) => s.isListOpen)
  const setListOpen = useStore((s) => s.setListOpen)
  const isCreating = useStore((s) => s.isCreating)
  const undo = useStore((s) => s.undo)
  const redo = useStore((s) => s.redo)
  const undoStack = useStore((s) => s.undoStack)
  const redoStack = useStore((s) => s.redoStack)
  const isSelectMode = useStore((s) => s.isSelectMode)
  const selectedTaskIds = useStore((s) => s.selectedTaskIds)
  const clearSelection = useStore((s) => s.clearSelection)
  const batchComplete = useStore((s) => s.batchComplete)
  const batchDelete = useStore((s) => s.batchDelete)
  const focusToday = useStore((s) => s.focusToday)
  const setFocusToday = useStore((s) => s.setFocusToday)
  const theme = useStore((s) => s.theme)
  const setTheme = useStore((s) => s.setTheme)
  const user = useStore((s) => s.user)
  const authLoading = useStore((s) => s.authLoading)
  const initAuth = useStore((s) => s.initAuth)
  const signOut = useStore((s) => s.signOut)
  const notificationsEnabled = useStore((s) => s.notificationsEnabled)
  const setNotificationsEnabled = useStore((s) => s.setNotificationsEnabled)
  const syncNow = useStore((s) => s.syncNow)
  const syncing = useStore((s) => s.syncing)
  const celebrationTitle = useStore((s) => s.celebrationTitle)
  const triggerCelebration = useStore((s) => s.triggerCelebration)
  const tasks = useStore((s) => s.tasks)

  // ===== 主题同步 =====
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  // 恢复主题偏好
  useEffect(() => {
    const saved = localStorage.getItem('sishi-theme') as 'light' | 'dark' | null
    if (saved === 'light' || saved === 'dark') setTheme(saved)
  }, [setTheme])

  // 恢复通知偏好
  useEffect(() => {
    const saved = localStorage.getItem('sishi-notifications')
    if (saved === 'true' && 'Notification' in window && Notification.permission === 'granted') {
      setNotificationsEnabled(true)
    }
  }, [setNotificationsEnabled])

  // ===== 到期通知系统 =====
  const isNative = Capacitor.isNativePlatform()

  useEffect(() => {
    if (!notificationsEnabled) return

    // 原生平台：请求 Capacitor 本地通知权限
    if (isNative) {
      LocalNotifications.requestPermissions().then((result) => {
        if (result.display !== 'granted') {
          setNotificationsEnabled(false)
        }
      })
    }

    // 记录当天已通知的任务 ID，避免重复弹窗
    const todayKey = new Date().toISOString().slice(0, 10)
    const notifiedKey = `sishi-notified-${todayKey}`
    const notifiedIds = new Set(JSON.parse(localStorage.getItem(notifiedKey) || '[]') as string[])

    const checkAndNotify = async () => {
      const now = new Date()
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
      const todayTime = today.getTime()

      const urgentTasks = tasks.filter((t) => {
        if (t.completed || !t.dueDate || notifiedIds.has(t.id)) return false
        const due = new Date(t.dueDate)
        const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate())
        return dueDay.getTime() <= todayTime
      })

      if (urgentTasks.length === 0) return

      if (isNative) {
        // Capacitor 原生通知（Android/iOS）
        await LocalNotifications.schedule({
          notifications: urgentTasks.map((task) => {
            const due = new Date(task.dueDate!)
            const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate())
            const isOverdue = dueDay.getTime() < todayTime
            return {
              title: `⏰ ${isOverdue ? '已过期' : '今天到期'}：${task.title}`,
              body: task.note || `截止日期：${due.toLocaleDateString('zh-CN')}`,
              id: parseInt(task.id.replace(/\D/g, '').slice(0, 8), 16) || Date.now() + Math.random() * 10000,
              schedule: { at: new Date(Date.now() + 1000) },
              sound: 'beep.wav',
              smallIcon: 'ic_stat_icon',
            }
          }),
        })
      } else {
        // Web Notification API
        for (const task of urgentTasks) {
          const due = new Date(task.dueDate!)
          const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate())
          const isOverdue = dueDay.getTime() < todayTime

          new Notification(`⏰ ${isOverdue ? '已过期' : '今天到期'}：${task.title}`, {
            body: task.note || `截止日期：${due.toLocaleDateString('zh-CN')}`,
            icon: '/favicon.svg',
            tag: `task-${task.id}-${todayKey}`,
          })
        }
      }

      urgentTasks.forEach((t) => notifiedIds.add(t.id))
      localStorage.setItem(notifiedKey, JSON.stringify([...notifiedIds]))
    }

    const initialTimer = setTimeout(checkAndNotify, 5000)
    const interval = setInterval(checkAndNotify, 10 * 60 * 1000)

    return () => {
      clearTimeout(initialTimer)
      clearInterval(interval)
    }
  }, [notificationsEnabled, tasks, isNative, setNotificationsEnabled])

  // ===== 庆祝动画 =====
  useEffect(() => {
    if (!celebrationTitle) return

    const duration = 1500
    const end = Date.now() + duration

    // 主 burst：屏幕中心向四周喷射
    const frame = () => {
      confetti({
        particleCount: 3,
        angle: 60 + Math.random() * 60,    // 向上扇形 60°-120°
        spread: 70,
        origin: { x: Math.random() * 0.6 + 0.2, y: 0.55 + Math.random() * 0.2 },
        colors: ['#A78BFA', '#F2A7B3', '#B5D9C4', '#FBE4A0', '#C5D5E8'],
        startVelocity: 50 + Math.random() * 30,
        gravity: 1.2,
        ticks: 80,
        shapes: ['circle', 'square'],
        scalar: 0.8 + Math.random() * 0.5,
        disableForReducedMotion: true,
      })

      if (Date.now() < end) {
        requestAnimationFrame(frame)
      }
    }

    // 初始 burst + 持续粒子
    confetti({
      particleCount: 50,
      spread: 100,
      origin: { x: 0.5, y: 0.5 },
      colors: ['#A78BFA', '#F2A7B3', '#B5D9C4', '#FBE4A0'],
      startVelocity: 60,
      gravity: 1,
      ticks: 60,
      shapes: ['circle'],
      scalar: 1.2,
      disableForReducedMotion: true,
    })

    frame()

    // 清除触发标记
    const timer = setTimeout(() => triggerCelebration(null), duration)
    return () => clearTimeout(timer)
  }, [celebrationTitle, triggerCelebration])

  // 请求通知权限
  const handleEnableNotifications = useCallback(async () => {
    if (isNative) {
      const result = await LocalNotifications.requestPermissions()
      setNotificationsEnabled(result.display === 'granted')
    } else {
      if (!('Notification' in window)) {
        alert('此浏览器不支持通知功能')
        return
      }
      if (Notification.permission === 'denied') {
        alert('通知权限已被拒绝，请在浏览器设置中手动开启')
        return
      }
      const permission = await Notification.requestPermission()
      setNotificationsEnabled(permission === 'granted')
    }
  }, [isNative, setNotificationsEnabled])

  // ===== 标签管理弹窗 =====
  const [isTagManagerOpen, setIsTagManagerOpen] = useState(false)
  const [isStatsOpen, setIsStatsOpen] = useState(false)

  // ===== 导入状态 =====
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importStrategy, setImportStrategy] = useState<ImportStrategy>('skip')
  const [importResult, setImportResult] = useState<{ importedTasks: number; importedTags: number; skippedTasks: number; skippedTags: number } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ===== 可拖拽调节侧边栏宽度 =====
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('sishi-sidebar-width')
    return saved ? Number(saved) : 288
  })
  const isResizing = useRef(false)
  const widthRef = useRef(sidebarWidth)
  widthRef.current = sidebarWidth

  const handleResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault()
    isResizing.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const onMove = (clientX: number) => {
      if (!isResizing.current) return
      const min = 200
      const max = window.innerWidth * 0.5
      setSidebarWidth(Math.max(min, Math.min(max, clientX)))
    }

    const onMouseMove = (e: MouseEvent) => onMove(e.clientX)
    const onTouchMove = (e: TouchEvent) => onMove(e.touches[0].clientX)

    const onEnd = () => {
      isResizing.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onEnd)
      document.removeEventListener('touchmove', onTouchMove)
      document.removeEventListener('touchend', onEnd)
      localStorage.setItem('sishi-sidebar-width', String(widthRef.current))
    }

    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onEnd)
    document.addEventListener('touchmove', onTouchMove)
    document.addEventListener('touchend', onEnd)
  }, [])

  // 初始化认证 + 数据库
  useEffect(() => {
    initAuth()
  }, [initAuth])

  useEffect(() => {
    if (user) initialize()
  }, [user, initialize])

  // 恢复视图密度偏好
  useEffect(() => {
    const saved = localStorage.getItem('sishi-view-density')
    if (saved === 'compact' || saved === 'standard' || saved === 'detailed') {
      setViewDensity(saved)
    }
  }, [setViewDensity])

  // ===== 导入处理 =====
  const handleImportClick = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setImportFile(file)
      setImportResult(null)
    }
    // 重置 input 以便重复选择同一文件
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [])

  const handleImportConfirm = useCallback(async () => {
    if (!importFile) return
    try {
      const result = await importData(importFile, importStrategy)
      setImportResult(result)
    } catch (err) {
      alert(err instanceof Error ? err.message : '导入失败')
      setImportFile(null)
    }
  }, [importFile, importStrategy, importData])

  const handleImportCancel = useCallback(() => {
    setImportFile(null)
    setImportResult(null)
  }, [])

  const showForm = isCreating || !!editingTaskId

  // ===== 键盘快捷键 =====
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 在输入框中不触发快捷键
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      const key = e.key.toLowerCase()

      // N — 新建任务
      if (key === 'n' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        setCreating(true)
        return
      }

      // Escape — 关闭弹窗 / 关闭侧边栏 / 取消选择
      if (key === 'escape') {
        if (showForm) {
          e.preventDefault()
          setCreating(false)
          setEditingTaskId(null)
          return
        }
        if (isSelectMode) {
          e.preventDefault()
          clearSelection()
          return
        }
        if (isListOpen) {
          e.preventDefault()
          setListOpen(false)
          return
        }
      }

      // / — 聚焦搜索框
      if (key === '/' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        const searchInput = document.querySelector<HTMLInputElement>('[data-search-input]')
        searchInput?.focus()
        return
      }

      // D — 循环切换视图密度
      if (key === 'd' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        const cycle: Record<string, 'compact' | 'standard' | 'detailed'> = {
          compact: 'standard',
          standard: 'detailed',
          detailed: 'compact',
        }
        setViewDensity(cycle[viewDensity])
        return
      }

      // Ctrl+Z — 撤销
      if (key === 'z' && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
        e.preventDefault()
        undo()
        return
      }

      // Ctrl+Y 或 Ctrl+Shift+Z — 重做
      if ((key === 'y' && (e.ctrlKey || e.metaKey)) || (key === 'z' && (e.ctrlKey || e.metaKey) && e.shiftKey)) {
        e.preventDefault()
        redo()
        return
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [showForm, isListOpen, isSelectMode, viewDensity, setCreating, setEditingTaskId, setListOpen, setViewDensity, undo, redo, clearSelection])

  // 认证加载中
  if (authLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-[var(--bg-page)]">
        <div className="text-center">
          <div className="text-4xl mb-3 animate-bounce">⏳</div>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>加载中…</p>
        </div>
      </div>
    )
  }

  // 未登录 → 登录页
  if (!user) {
    return <LoginPage />
  }

  // 数据加载中
  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-[var(--bg-page)]">
        <div className="text-center">
          <div className="text-4xl mb-3 animate-bounce">⏳</div>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>同步数据中…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col safe-top safe-bottom">
      {/* 隐藏的文件选择器（导入用） */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* ===== 顶部导航栏 ===== */}
      <header className="flex items-center justify-between px-5 py-3 bg-white/60 backdrop-blur-md
                         border-b border-gray-100/60 flex-shrink-0">
        <div className="flex items-center gap-3">
          <button
            className="lg:hidden p-1.5 rounded-xl hover:bg-gray-100/80 transition-colors"
            onClick={() => setListOpen(!isListOpen)}
            aria-label="打开任务列表"
          >
            <List weight="regular" className="w-5 h-5 text-gray-400" />
          </button>
          <h1 className="text-[15px] font-semibold text-gray-500 flex items-center gap-2 tracking-tight">
            <span className="text-base">⏳</span>
            <span className="hidden sm:inline">四时有序</span>
            <span className="sm:hidden">四时</span>
          </h1>

          {/* 用户信息 */}
          <button
            onClick={() => signOut()}
            className="text-[10px] text-gray-400 hover:text-red-400 transition-colors
                       hidden sm:block max-w-[120px] truncate"
            title="点击登出"
          >
            {user.email}
          </button>

          {/* 通知开关 */}
          <button
            onClick={notificationsEnabled ? () => setNotificationsEnabled(false) : handleEnableNotifications}
            className={`text-xs px-2.5 py-1.5 rounded-xl font-medium transition-all ${
              notificationsEnabled
                ? 'text-green-500 bg-green-50'
                : 'text-gray-400 hover:text-gray-500 hover:bg-gray-100/80'
            }`}
            title={notificationsEnabled ? '通知已开启' : '开启到期提醒'}
          >
            {notificationsEnabled ? '🔔' : '🔕'}
          </button>

          {/* 主题切换 */}
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="text-xs px-2.5 py-1.5 rounded-xl font-medium text-gray-400
                       hover:text-gray-500 hover:bg-gray-100/80 transition-all"
            title={theme === 'dark' ? '切换浅色模式' : '切换深色模式'}
          >
            {theme === 'dark' ? '🌙' : '☀️'}
          </button>

          <button
            onClick={() => setFocusToday(!focusToday)}
            className={`text-xs px-3 py-1.5 rounded-xl font-medium transition-all ${
              focusToday
                ? 'bg-orange-100 text-orange-500 shadow-sm'
                : 'text-gray-400 hover:text-gray-500 hover:bg-gray-100/80'
            }`}
            title="今日焦点"
          >
            📌 今日
          </button>
        </div>

        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-1.5 px-4 py-2 text-[13px] font-medium text-white
                     bg-purple-400 hover:bg-purple-500 rounded-2xl shadow-sm
                     hover:shadow-md transition-all active:scale-[0.97]"
        >
          <Plus weight="bold" className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">新建任务</span>
        </button>
      </header>

      {/* ===== 主体区域 ===== */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* 桌面端侧边栏 */}
        <aside
          className="hidden lg:block flex-shrink-0 h-full bg-white/60 backdrop-blur-sm"
          style={{ width: sidebarWidth }}
        >
          <TaskList />
        </aside>

        {/* 拖拽调节手柄 */}
        <div
          className="hidden lg:block w-1.5 flex-shrink-0 h-full cursor-col-resize
                     hover:bg-purple-200/50 active:bg-purple-300/50 transition-colors
                     relative group"
          onMouseDown={handleResizeStart}
          onTouchStart={handleResizeStart}
        >
          {/* 手柄中间的小圆点 */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
                          w-1 h-8 rounded-full bg-gray-300 group-hover:bg-purple-300
                          group-active:bg-purple-400 transition-colors" />
        </div>

        {/* 象限画布 */}
        <main className="flex-1 relative h-full">
          <QuadrantCanvas />
        </main>

        {/* 移动端底部 Sheet / 平板抽屉 */}
        {/* 遮罩 */}
        {isListOpen && (
          <div
            className="lg:hidden fixed inset-0 bg-black/25 z-40"
            onClick={() => setListOpen(false)}
          />
        )}

        {/* 列表面板 */}
        <div
          className={`
            lg:hidden fixed z-50 bg-white/97 transition-transform duration-300
            ${isListOpen ? 'translate-y-0' : 'translate-y-full'}
            max-md:bottom-0 max-md:left-0 max-md:right-0 max-md:h-[60vh] max-md:rounded-t-2xl max-md:shadow-2xl
            md:left-0 md:top-0 md:w-80 md:h-full md:translate-x-0
            ${isListOpen ? 'md:translate-x-0' : 'md:-translate-x-full'}
          `}
        >
          {/* 拖拽手柄（移动端） */}
          <div className="md:hidden flex justify-center pt-2 pb-0">
            <div className="w-10 h-1 rounded-full bg-gray-300" />
          </div>
          <TaskList />
        </div>
      </div>

      {/* ===== 底部工具栏 ===== */}
      <footer className="flex items-center justify-between px-5 py-2.5 bg-white/60 backdrop-blur-md
                         border-t border-gray-100/60 flex-shrink-0">
        {isSelectMode ? (
          /* ---- 批量操作模式 ---- */
          <div className="flex items-center gap-3 w-full justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={clearSelection}
                className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-500
                           hover:bg-gray-100/80 rounded-xl transition-colors font-medium"
              >
                <X weight="bold" className="w-3.5 h-3.5" />
                取消
              </button>
              <span className="text-xs font-medium text-purple-400">
                已选 {selectedTaskIds.length} 个
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={batchComplete}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white
                           bg-green-400 hover:bg-green-500 rounded-xl transition-colors shadow-sm"
              >
                <Check weight="bold" className="w-3.5 h-3.5" />
                批量完成
              </button>
              <button
                onClick={batchDelete}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white
                           bg-red-400 hover:bg-red-500 rounded-xl transition-colors shadow-sm"
              >
                <Trash weight="regular" className="w-3.5 h-3.5" />
                批量删除
              </button>
            </div>
          </div>
        ) : (
        /* ---- 正常模式 ---- */
        <div className="flex items-center gap-3">
          {/* 撤销 / 重做 */}
          <div className="flex items-center gap-0.5">
            <button
              onClick={undo}
              disabled={undoStack.length === 0}
              className="flex items-center justify-center w-8 h-8 text-gray-400 hover:text-purple-400
                         hover:bg-purple-50 rounded-xl transition-colors
                         disabled:opacity-25 disabled:cursor-not-allowed"
              title="撤销 (Ctrl+Z)"
            >
              <ArrowArcLeft weight="regular" className="w-4 h-4" />
            </button>
            <button
              onClick={redo}
              disabled={redoStack.length === 0}
              className="flex items-center justify-center w-8 h-8 text-gray-400 hover:text-purple-400
                         hover:bg-purple-50 rounded-xl transition-colors
                         disabled:opacity-25 disabled:cursor-not-allowed"
              title="重做 (Ctrl+Y)"
            >
              <ArrowArcRight weight="regular" className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-0.5 bg-gray-100/80 rounded-xl p-0.5">
            {(['compact', 'standard', 'detailed'] as const).map((density) => (
              <button
                key={density}
                onClick={() => setViewDensity(density)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-all duration-200 ${
                  viewDensity === density
                    ? 'bg-white text-purple-400 shadow-sm font-semibold'
                    : 'text-gray-400 hover:text-gray-500'
                }`}
              >
                {density === 'compact' ? '紧凑' : density === 'standard' ? '标准' : '详细'}
              </button>
            ))}
          </div>

          <button
            onClick={autoArrange}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-purple-400
                       hover:bg-purple-50 rounded-xl transition-colors font-medium"
            title="一键排列"
          >
            <ArrowsOutCardinal weight="regular" className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">排列</span>
          </button>

          <button
            onClick={exportData}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-500
                       hover:bg-gray-100/80 rounded-xl transition-colors font-medium"
          >
            <FileArrowDown weight="regular" className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">导出</span>
          </button>

          <button
            onClick={handleImportClick}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-500
                       hover:bg-gray-100/80 rounded-xl transition-colors font-medium"
          >
            <FileArrowUp weight="regular" className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">导入</span>
          </button>

          <button
            onClick={syncNow}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-purple-400
                       hover:bg-purple-50 rounded-xl transition-colors font-medium
                       disabled:opacity-50 disabled:cursor-wait"
            title="从云端同步数据"
          >
            <ArrowsClockwise weight="regular" className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">{syncing ? '同步中' : '同步'}</span>
          </button>

          <button
            onClick={() => setIsTagManagerOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-500
                       hover:bg-gray-100/80 rounded-xl transition-colors font-medium"
          >
            <TagSimple weight="regular" className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">标签</span>
          </button>

          <button
            onClick={() => setIsStatsOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-500
                       hover:bg-gray-100/80 rounded-xl transition-colors font-medium"
          >
            <ChartBar weight="regular" className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">统计</span>
          </button>
        </div>
        )}
      </footer>

      {/* ===== 移动端浮动创建按钮 ===== */}
      <button
        className="lg:hidden fixed right-4 w-12 h-12 bg-purple-400 hover:bg-purple-500
                   text-white rounded-full shadow-lg active:scale-95 transition-all z-30
                   flex items-center justify-center"
        style={{ bottom: `calc(1.25rem + max(env(safe-area-inset-bottom), 16px))` }}
        onClick={() => setCreating(true)}
      >
        <Plus weight="bold" className="w-6 h-6" />
      </button>

      {/* ===== 任务表单弹窗 ===== */}
      {showForm && <TaskForm onClose={() => { setCreating(false); setEditingTaskId(null) }} />}

      {/* ===== 标签管理弹窗 ===== */}
      {isTagManagerOpen && <TagManager onClose={() => setIsTagManagerOpen(false)} />}
      {isStatsOpen && <StatsPanel onClose={() => setIsStatsOpen(false)} />}

      {/* ===== 导入策略对话框 ===== */}
      {importFile && !importResult && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/15 backdrop-blur-sm px-4"
          onClick={handleImportCancel}
        >
          <div
            className="bg-white rounded-3xl shadow-xl shadow-purple-100/50 w-full max-w-sm p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-bold text-gray-600 mb-2">导入备份</h2>
            <p className="text-xs text-gray-400 mb-5 truncate">
              文件：{importFile.name}
            </p>

            <div className="space-y-2 mb-6">
              <label className="flex items-center gap-3 px-4 py-3 bg-gray-50 rounded-2xl cursor-pointer hover:bg-gray-100/80 transition-colors">
                <input
                  type="radio"
                  name="importStrategy"
                  value="skip"
                  checked={importStrategy === 'skip'}
                  onChange={() => setImportStrategy('skip')}
                  className="accent-purple-400"
                />
                <div>
                  <div className="text-sm font-medium text-gray-600">跳过已有任务</div>
                  <div className="text-[11px] text-gray-400">相同 ID 的任务不覆盖，保留现有数据</div>
                </div>
              </label>
              <label className="flex items-center gap-3 px-4 py-3 bg-gray-50 rounded-2xl cursor-pointer hover:bg-gray-100/80 transition-colors">
                <input
                  type="radio"
                  name="importStrategy"
                  value="overwrite"
                  checked={importStrategy === 'overwrite'}
                  onChange={() => setImportStrategy('overwrite')}
                  className="accent-purple-400"
                />
                <div>
                  <div className="text-sm font-medium text-gray-600">覆盖已有任务</div>
                  <div className="text-[11px] text-gray-400">相同 ID 的任务用导入数据替换</div>
                </div>
              </label>
              <label className="flex items-center gap-3 px-4 py-3 bg-gray-50 rounded-2xl cursor-pointer hover:bg-gray-100/80 transition-colors">
                <input
                  type="radio"
                  name="importStrategy"
                  value="new"
                  checked={importStrategy === 'new'}
                  onChange={() => setImportStrategy('new')}
                  className="accent-purple-400"
                />
                <div>
                  <div className="text-sm font-medium text-gray-600">全部作为新任务</div>
                  <div className="text-[11px] text-gray-400">为每个任务生成新 ID，不覆盖任何数据</div>
                </div>
              </label>
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleImportCancel}
                className="flex-1 px-4 py-2.5 text-xs font-medium text-gray-500 bg-gray-100
                           rounded-xl hover:bg-gray-200 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleImportConfirm}
                className="flex-1 px-4 py-2.5 text-xs font-medium text-white bg-purple-400
                           rounded-xl hover:bg-purple-500 transition-all shadow-sm shadow-purple-200/50"
              >
                确认导入
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 导入结果提示 ===== */}
      {importResult && importFile && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/15 backdrop-blur-sm px-4"
          onClick={() => { setImportFile(null); setImportResult(null) }}
        >
          <div
            className="bg-white rounded-3xl shadow-xl shadow-purple-100/50 w-full max-w-sm p-6 text-center"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-4xl mb-3">✅</div>
            <h2 className="text-lg font-bold text-gray-600 mb-3">导入完成</h2>
            <div className="text-sm text-gray-500 space-y-1 mb-5">
              <p>任务：导入 {importResult.importedTasks} 个，跳过 {importResult.skippedTasks} 个</p>
              <p>标签：导入 {importResult.importedTags} 个，跳过 {importResult.skippedTags} 个</p>
            </div>
            <button
              onClick={() => { setImportFile(null); setImportResult(null) }}
              className="px-6 py-2.5 text-xs font-medium text-white bg-purple-400
                         rounded-xl hover:bg-purple-500 transition-all shadow-sm shadow-purple-200/50"
            >
              知道了
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
