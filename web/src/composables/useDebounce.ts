import { ref, watch } from 'vue'

export function useDebounce<T>(source: () => T, delay = 300) {
  const debounced = ref<T>(source())

  let timer: ReturnType<typeof setTimeout> | null = null

  watch(source, (val) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      debounced.value = val
    }, delay)
  })

  return { debounced }
}
