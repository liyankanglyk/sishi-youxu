import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

type Theme = 'light' | 'dark' | 'system'

export const useUiStore = defineStore('ui', () => {
  // ── Theme ──
  const theme = ref<Theme>((localStorage.getItem('sishi-theme') as Theme) || 'system')
  const systemDark = ref(window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false)

  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      systemDark.value = e.matches
      applyTheme()
    })
  }

  function applyTheme() {
    const isDark = theme.value === 'dark' || (theme.value === 'system' && systemDark.value)
    document.documentElement.classList.toggle('dark', isDark)
  }

  watch(theme, (t) => {
    localStorage.setItem('sishi-theme', t)
    applyTheme()
  })

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  // ── Mobile detection ──
  const isMobile = ref(window.matchMedia?.('(max-width: 767px)').matches ?? false)

  if (window.matchMedia) {
    window.matchMedia('(max-width: 767px)').addEventListener('change', (e) => {
      isMobile.value = e.matches
      if (!e.matches) {
        showMobileTaskList.value = false
        showMobileStatsPanel.value = false
        showMobileOverflowMenu.value = false
        showMobileSearch.value = false
      }
    })
  }

  // ── Desktop sidebar — left task list ──
  const leftSidebarWidth = ref(
    Number(localStorage.getItem('sishi-sidebar-width') || 260),
  )

  function toggleLeftSidebar() {
    leftSidebarWidth.value = leftSidebarWidth.value > 0 ? 0 : 260
  }

  watch(leftSidebarWidth, (w) => {
    localStorage.setItem('sishi-sidebar-width', String(w))
  })

  // ── Desktop sidebar — right stats panel ──
  const showStatsPanel = ref(
    localStorage.getItem('sishi-show-stats') !== 'false',
  )

  function toggleStatsPanel() {
    showStatsPanel.value = !showStatsPanel.value
  }

  watch(showStatsPanel, (v) => {
    localStorage.setItem('sishi-show-stats', String(v))
  })

  // ── Mobile drawers ──
  const showMobileTaskList = ref(false)
  const showMobileStatsPanel = ref(false)

  function openMobileTaskList() { showMobileTaskList.value = true }
  function closeMobileTaskList() { showMobileTaskList.value = false }
  function toggleMobileTaskList() { showMobileTaskList.value = !showMobileTaskList.value }

  function openMobileStatsPanel() { showMobileStatsPanel.value = true }
  function closeMobileStatsPanel() { showMobileStatsPanel.value = false }
  function toggleMobileStatsPanel() { showMobileStatsPanel.value = !showMobileStatsPanel.value }

  // ── Mobile overflow menu ──
  const showMobileOverflowMenu = ref(false)
  function toggleMobileOverflowMenu() { showMobileOverflowMenu.value = !showMobileOverflowMenu.value }
  function closeMobileOverflowMenu() { showMobileOverflowMenu.value = false }

  // ── Mobile search overlay ──
  const showMobileSearch = ref(false)

  // ── Import trigger ──
  const importTrigger = ref(0)
  function triggerImport() { importTrigger.value++ }

  // ── Notification preference ──
  const notificationsEnabled = ref(localStorage.getItem('sishi-notifications') === 'true')
  function setNotificationsEnabled(enabled: boolean) {
    notificationsEnabled.value = enabled
    localStorage.setItem('sishi-notifications', String(enabled))
  }

  // Initialize
  applyTheme()

  return {
    theme, systemDark, applyTheme, toggleTheme,
    isMobile,
    leftSidebarWidth, toggleLeftSidebar,
    showStatsPanel, toggleStatsPanel,
    showMobileTaskList, openMobileTaskList, closeMobileTaskList, toggleMobileTaskList,
    showMobileStatsPanel, openMobileStatsPanel, closeMobileStatsPanel, toggleMobileStatsPanel,
    showMobileOverflowMenu, toggleMobileOverflowMenu, closeMobileOverflowMenu,
    showMobileSearch,
    importTrigger, triggerImport,
    notificationsEnabled, setNotificationsEnabled,
  }
})
