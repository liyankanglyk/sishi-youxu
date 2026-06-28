import { onMounted, onUnmounted } from 'vue'
import { useTaskStore } from '@/stores/task'

export function useKeyboard() {
  const store = useTaskStore()

  function handler(e: KeyboardEvent) {
    const tag = (e.target as HTMLElement).tagName
    const isEditing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target as HTMLElement).isContentEditable

    // Ctrl+Z / Ctrl+Shift+Z work even inside inputs for undo/redo
    if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
      e.preventDefault()
      store.undo().catch(() => {})
      return
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'z' && e.shiftKey) {
      e.preventDefault()
      store.redo().catch(() => {})
      return
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
      e.preventDefault()
      store.setCreating(true)
      return
    }

    if (isEditing) return

    if (e.key === 'n' || e.key === 'N') {
      e.preventDefault()
      store.setCreating(true)
    } else if (e.key === 'd' || e.key === 'D') {
      e.preventDefault()
      store.cycleViewDensity()
    } else if (e.key === '/') {
      e.preventDefault()
      const el = document.getElementById('header-search-input')
      el?.focus()
    } else if (e.key === 'Escape') {
      if (store.isCreating || store.editingTaskUuid) {
        store.setCreating(false)
        store.setEditingUuid(null)
      } else if (store.isSelectMode) {
        store.clearSelection()
      }
    }
  }

  onMounted(() => document.addEventListener('keydown', handler))
  onUnmounted(() => document.removeEventListener('keydown', handler))
}
