import { ref } from 'vue'

export interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'info' | 'warning'
}

let nextId = 0
const toasts = ref<Toast[]>([])

export function useToast() {
  function show(message: string, type: Toast['type'] = 'info', duration = 2500) {
    const id = nextId++
    toasts.value.push({ id, message, type })
    setTimeout(() => {
      toasts.value = toasts.value.filter(t => t.id !== id)
    }, duration)
  }

  function success(msg: string) { show(msg, 'success') }
  function error(msg: string) { show(msg, 'error') }
  function info(msg: string) { show(msg, 'info') }
  function warning(msg: string) { show(msg, 'warning') }

  return { toasts, show, success, error, info, warning }
}
