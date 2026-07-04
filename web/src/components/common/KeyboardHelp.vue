<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()

interface Shortcut {
  keys: string[]
  desc: string
  scope?: string
}

const shortcuts: Shortcut[] = [
  { keys: ['?'], desc: '打开 / 关闭此快捷键面板', scope: '全局' },
  { keys: ['/'], desc: '聚焦到顶部搜索框', scope: '全局' },
  { keys: ['N'], desc: '新建任务', scope: '全局' },
  { keys: ['D'], desc: '切换卡片密度（紧凑 / 标准 / 详细）', scope: '全局' },
  { keys: ['Ctrl', 'Z'], desc: '撤销', scope: '全局' },
  { keys: ['Ctrl', 'Shift', 'Z'], desc: '重做', scope: '全局' },
  { keys: ['Ctrl', 'N'], desc: '新建任务', scope: '全局' },
  { keys: ['Esc'], desc: '关闭弹窗 / 取消多选', scope: '弹窗' },
]

function isEditingTarget(e: KeyboardEvent): boolean {
  const tag = (e.target as HTMLElement).tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target as HTMLElement).isContentEditable
}

function onKey(e: KeyboardEvent) {
  if (e.key === '?' && !isEditingTarget(e)) {
    e.preventDefault()
    if (ui.showKeyboardHelp) ui.closeKeyboardHelp()
    else ui.openKeyboardHelp()
    return
  }
  if (e.key === 'Escape' && ui.showKeyboardHelp) {
    e.preventDefault()
    ui.closeKeyboardHelp()
  }
}

onMounted(() => document.addEventListener('keydown', onKey))
onUnmounted(() => document.removeEventListener('keydown', onKey))

function close() {
  ui.closeKeyboardHelp()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="help-fade">
      <div v-if="ui.showKeyboardHelp" class="help-scrim" @mousedown.self="close">
        <Transition name="help-pop" appear>
          <div v-if="ui.showKeyboardHelp" class="help-panel" role="dialog" aria-label="键盘快捷键">
            <header class="help-header">
              <div class="help-title-wrap">
                <span class="help-icon">⌨️</span>
                <h2 class="help-title">键盘快捷键</h2>
              </div>
              <button class="help-close" @click="close" aria-label="关闭">&times;</button>
            </header>

            <div class="help-body">
              <section v-for="(group, gi) in [
                { title: '全局', items: shortcuts.filter(s => s.scope !== '弹窗') },
                { title: '弹窗', items: shortcuts.filter(s => s.scope === '弹窗') },
              ]" :key="gi" class="help-section">
                <h3 class="help-section-title">{{ group.title }}</h3>
                <div class="help-grid">
                  <div v-for="(s, si) in group.items" :key="si" class="help-row">
                    <div class="help-keys">
                      <template v-for="(k, ki) in s.keys" :key="ki">
                        <kbd class="kbd">{{ k }}</kbd>
                        <span v-if="ki < s.keys.length - 1" class="kbd-plus">+</span>
                      </template>
                    </div>
                    <div class="help-desc">{{ s.desc }}</div>
                  </div>
                </div>
              </section>
            </div>

            <footer class="help-footer">
              <span>提示：在输入框中时大部分快捷键不会触发</span>
              <button class="help-got-it" @click="close">知道了</button>
            </footer>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.help-scrim {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.help-panel {
  width: 100%;
  max-width: 540px;
  background: var(--surface-primary);
  border-radius: var(--r-modal);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  max-height: 80vh;
  overflow: hidden;
}

/* ── 头部 ── */
.help-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.help-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.help-icon {
  font-size: 20px;
}

.help-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--c-gray-900);
  margin: 0;
  letter-spacing: -0.01em;
}

.help-close {
  width: 28px;
  height: 28px;
  border: none;
  background: var(--c-gray-100);
  border-radius: 6px;
  color: var(--c-gray-500);
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.12s, color 0.12s;
}

.help-close:hover {
  background: var(--c-gray-200);
  color: var(--c-gray-700);
}

/* ── 主体 ── */
.help-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 20px;
}

.help-section + .help-section {
  margin-top: 16px;
}

.help-section-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-gray-400);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 8px;
}

.help-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.help-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 7px 10px;
  border-radius: 8px;
  transition: background 0.12s;
}

.help-row:hover {
  background: var(--c-gray-50);
}

.help-keys {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  min-width: 130px;
}

.kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 7px;
  font-size: 12px;
  font-weight: 600;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  color: var(--c-gray-700);
  background: linear-gradient(to bottom, var(--surface-primary), var(--c-gray-50));
  border: 1px solid var(--c-gray-200);
  border-bottom-width: 2px;
  border-radius: 5px;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.04);
}

:root.dark .kbd {
  background: linear-gradient(to bottom, var(--c-gray-100), var(--c-gray-200));
  color: var(--c-gray-900);
}

.kbd-plus {
  font-size: 11px;
  color: var(--c-gray-400);
  font-weight: 500;
}

.help-desc {
  font-size: 13px;
  color: var(--c-gray-700);
  flex: 1;
}

/* ── 底部 ── */
.help-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-top: 1px solid var(--border-light);
  background: var(--c-gray-50);
  flex-shrink: 0;
}

.help-footer > span {
  font-size: 11px;
  color: var(--c-gray-400);
}

.help-got-it {
  padding: 6px 16px;
  border: none;
  background: var(--c-brand-500);
  color: #fff;
  border-radius: var(--r-button);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.12s;
}

.help-got-it:hover {
  background: var(--c-brand-600);
}

/* ── 过渡 ── */
.help-fade-enter-active,
.help-fade-leave-active {
  transition: opacity 0.2s var(--ease-standard);
}

.help-fade-enter-from,
.help-fade-leave-to {
  opacity: 0;
}

.help-pop-enter-active {
  transition: all 0.25s cubic-bezier(0.22, 0.98, 0.36, 1.02);
}

.help-pop-leave-active {
  transition: all 0.18s var(--ease-standard);
}

.help-pop-enter-from {
  opacity: 0;
  transform: scale(0.92) translateY(-8px);
}

.help-pop-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

/* ── 移动端 ── */
@media (max-width: 767px) {
  .help-panel {
    max-height: 90vh;
  }

  .help-row {
    gap: 10px;
    padding: 6px 8px;
  }

  .help-keys {
    min-width: 100px;
  }

  .help-desc {
    font-size: 12.5px;
  }
}
</style>