<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useTaskStore } from '@/stores/task'
import { useNotification } from '@/composables/useNotification'
import { tagApi, type TagOut } from '@/api/tags'
import { useToast } from '@/composables/useToast'
import TagChip from '@/components/common/TagChip.vue'

const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const taskStore = useTaskStore()
const toast = useToast()
const notif = useNotification(() => taskStore.serverTasks)

// ── Tags ──
const tags = ref<TagOut[]>([])
const tagsLoading = ref(false)
const tagDialogVisible = ref(false)
const editingTag = ref<TagOut | null>(null)
const tagFormName = ref('')
const tagFormColor = ref('#6366f1')
const tagSaving = ref(false)

const presetColors = [
  '#007AFF', '#34C759', '#5856D6', '#FF9500',
  '#FFCC00', '#5AC8FA', '#FF2D55', '#AF52DE',
]

async function fetchTags() {
  tagsLoading.value = true
  try {
    const { data } = await tagApi.list()
    tags.value = data?.items ?? []
  } catch (e: any) {
    toast.error(e.message || '加载标签失败')
  } finally { tagsLoading.value = false }
}

function openCreateTag() {
  editingTag.value = null
  tagFormName.value = ''
  tagFormColor.value = '#6366f1'
  tagDialogVisible.value = true
}

function openEditTag(tag: TagOut) {
  editingTag.value = tag
  tagFormName.value = tag.name
  tagFormColor.value = tag.color
  tagDialogVisible.value = true
}

async function saveTag() {
  if (!tagFormName.value.trim()) {
    toast.warning('请输入标签名称')
    return
  }
  tagSaving.value = true
  try {
    if (editingTag.value) {
      await tagApi.update(editingTag.value.uuid, {
        name: tagFormName.value.trim(),
        color: tagFormColor.value,
      })
      toast.success('标签已更新')
    } else {
      await tagApi.create({
        name: tagFormName.value.trim(),
        color: tagFormColor.value,
      })
      toast.success('标签已创建')
    }
    tagDialogVisible.value = false
    fetchTags()
  } catch (e: any) {
    toast.error(e.message || '保存失败')
  } finally { tagSaving.value = false }
}

async function deleteTag(tag: TagOut) {
  if (!confirm(`删除标签「${tag.name}」？`)) return
  try {
    await tagApi.delete(tag.uuid)
    toast.success('已删除')
    fetchTags()
  } catch (e: any) {
    toast.error(e.message || '删除失败')
  }
}

// ── Password ──
const pwOld = ref('')
const pwNew = ref('')
const pwConfirm = ref('')
const pwSaving = ref(false)
const pwError = ref('')

async function handleChangePassword() {
  pwError.value = ''
  if (!pwOld.value || !pwNew.value || !pwConfirm.value) {
    pwError.value = '请填写所有密码字段'
    return
  }
  if (pwNew.value.length < 8) {
    pwError.value = '新密码至少 8 位'
    return
  }
  if (pwNew.value !== pwConfirm.value) {
    pwError.value = '两次新密码输入不一致'
    return
  }
  if (pwNew.value === pwOld.value) {
    pwError.value = '新密码不能与当前密码相同'
    return
  }
  pwSaving.value = true
  try {
    await auth.changePassword(pwOld.value, pwNew.value)
    toast.success('密码修改成功，请重新登录')
    router.push('/login')
  } catch (e: any) {
    pwError.value = e.message || '修改失败'
  } finally { pwSaving.value = false }
}

// ── Auth ──
async function handleLogout() {
  await auth.logout()
  router.push('/login')
}

onMounted(fetchTags)
</script>

<template>
  <div class="settings-page">
    <h1 class="page-title">设置</h1>

    <!-- Account -->
    <section class="card">
      <div class="card-header">
        <h2 class="section-title">账号信息</h2>
      </div>
      <div class="account-row">
        <div class="account-avatar">{{ auth.user?.nickname?.charAt(0) ?? '?' }}</div>
        <div class="account-meta">
          <span class="account-name">{{ auth.user?.nickname || '未设置昵称' }}</span>
          <span class="account-role">{{ auth.userRole === 'admin' ? '管理员' : '普通用户' }}
            · <span :style="{ color: auth.user?.status === 'active' ? 'var(--c-success)' : 'var(--c-warning)' }">
              {{ auth.user?.status === 'active' ? '正常' : auth.user?.status || '-' }}
            </span>
          </span>
        </div>
      </div>
    </section>

    <!-- Change Password -->
    <section class="card">
      <div class="card-header">
        <h2 class="section-title">修改密码</h2>
      </div>
      <form class="pw-form" @submit.prevent="handleChangePassword">
        <div class="field">
          <label for="pw-old">当前密码</label>
          <input id="pw-old" v-model="pwOld" type="password" autocomplete="current-password" placeholder="输入当前密码" class="field-input" />
        </div>
        <div class="field">
          <label for="pw-new">新密码</label>
          <input id="pw-new" v-model="pwNew" type="password" autocomplete="new-password" placeholder="至少 8 位" class="field-input" />
        </div>
        <div class="field">
          <label for="pw-confirm">确认新密码</label>
          <input id="pw-confirm" v-model="pwConfirm" type="password" autocomplete="new-password" placeholder="再次输入新密码" class="field-input" />
        </div>
        <p v-if="pwError" class="pw-error">{{ pwError }}</p>
        <button type="submit" :disabled="pwSaving" class="pw-save-btn">
          {{ pwSaving ? '保存中...' : '修改密码' }}
        </button>
      </form>
    </section>

    <!-- Tags -->
    <section class="card">
      <div class="card-header">
        <h2 class="section-title">我的标签</h2>
        <button class="add-btn" @click="openCreateTag">+ 新建</button>
      </div>
      <div v-if="tagsLoading" class="center-text">加载中...</div>
      <div v-else-if="tags.length" class="tag-list">
        <div v-for="tag in tags" :key="tag.uuid" class="tag-row">
          <TagChip :name="tag.name" :color="tag.color" />
          <span v-if="tag.isPreset" class="preset-badge">系统</span>
          <div class="tag-actions" v-if="!tag.isPreset">
            <button class="text-btn" @click="openEditTag(tag)">编辑</button>
            <button class="text-btn danger" @click="deleteTag(tag)">删除</button>
          </div>
        </div>
      </div>
      <p v-else class="center-text dim">暂无自定义标签，点击"+ 新建"创建</p>
    </section>

    <!-- Preferences -->
    <section class="card">
      <div class="card-header">
        <h2 class="section-title">偏好设置</h2>
      </div>
      <div class="pref-list">
        <!-- Theme -->
        <div class="pref-item">
          <span class="pref-label">主题</span>
          <div class="segmented">
            <button
              v-for="t in [['system', '跟随系统'], ['light', '浅色'], ['dark', '深色']]"
              :key="t[0]"
              :class="['seg-option', { active: ui.theme === t[0] }]"
              @click="ui.theme = t[0] as any"
            >{{ t[1] }}</button>
          </div>
        </div>

        <!-- Density -->
        <div class="pref-item">
          <span class="pref-label">视图密度</span>
          <div class="segmented">
            <button
              v-for="d in [['compact', '紧凑'], ['standard', '标准'], ['detailed', '详细']]"
              :key="d[0]"
              :class="['seg-option', { active: taskStore.viewDensity === d[0] }]"
              @click="taskStore.setViewDensity(d[0] as any)"
            >{{ d[1] }}</button>
          </div>
        </div>

        <!-- Notifications -->
        <div class="pref-item">
          <span class="pref-label">到期提醒</span>
          <div class="segmented">
            <button
              :class="['seg-option', { active: notif.enabled.value }]"
              @click="notif.setEnabled(true)"
            >开启</button>
            <button
              :class="['seg-option', { active: !notif.enabled.value }]"
              @click="notif.setEnabled(false)"
            >关闭</button>
          </div>
        </div>

        <!-- Shortcuts -->
        <div class="pref-item">
          <span class="pref-label">快捷键</span>
          <div class="shortcut-grid">
            <div class="shortcut"><kbd>N</kbd><span>新建任务</span></div>
            <div class="shortcut"><kbd>/</kbd><span>聚焦搜索</span></div>
            <div class="shortcut"><kbd>D</kbd><span>切换密度</span></div>
            <div class="shortcut"><kbd>Ctrl+Z</kbd><span>撤销</span></div>
            <div class="shortcut"><kbd>Ctrl+Shift+Z</kbd><span>重做</span></div>
            <div class="shortcut"><kbd>Esc</kbd><span>关闭弹窗</span></div>
          </div>
        </div>
      </div>
    </section>

    <!-- Logout -->
    <section class="card">
      <button class="logout-btn" @click="handleLogout">退出登录</button>
    </section>

    <!-- Tag Form Dialog -->
    <Teleport to="body">
      <Transition name="dialog-fade">
        <div v-if="tagDialogVisible" class="dialog-overlay" @click.self="tagDialogVisible = false">
          <div class="tag-dialog">
            <div class="tag-dialog-header">
              <h3>{{ editingTag ? '编辑标签' : '新建标签' }}</h3>
              <button class="dialog-close" @click="tagDialogVisible = false">&times;</button>
            </div>
            <div class="tag-dialog-body">
              <div class="field">
                <label>名称</label>
                <input
                  v-model="tagFormName"
                  type="text"
                  maxlength="50"
                  placeholder="输入标签名称"
                  class="field-input"
                  autofocus
                />
              </div>
              <div class="field">
                <label>颜色</label>
                <div class="color-row">
                  <button
                    v-for="c in presetColors"
                    :key="c"
                    class="color-swatch"
                    :class="{ active: tagFormColor === c }"
                    :style="{ backgroundColor: c }"
                    @click="tagFormColor = c"
                  />
                  <div class="color-custom">
                    <input type="color" v-model="tagFormColor" class="color-picker-native" />
                    <span class="color-custom-label">自定义</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="tag-dialog-footer">
              <button class="btn-cancel" @click="tagDialogVisible = false">取消</button>
              <button class="btn-save" :disabled="tagSaving" @click="saveTag">
                {{ tagSaving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 2rem 1rem 4rem;
}

.page-title {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--c-gray-900);
  margin: 0 0 1.5rem;
  padding: 0 4px;
}

/* ── Card ── */
.card {
  background: var(--surface-primary);
  border-radius: 14px;
  border: 1px solid var(--c-gray-200);
  margin-bottom: 12px;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-light);
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-gray-500);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0;
}

/* ── Account ── */
.account-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
}

.account-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--c-brand-500), #7C3AED);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.account-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.account-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--c-gray-900);
}

.account-role {
  font-size: 13px;
  color: var(--c-gray-400);
}

/* ── Tags ── */
.tag-list {
  display: flex;
  flex-direction: column;
  padding: 4px 0;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  transition: background 0.12s;
}
.tag-row:hover { background: var(--c-gray-50); }

.preset-badge {
  font-size: 10px;
  color: var(--c-gray-400);
  background: var(--c-gray-100);
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.tag-actions { margin-left: auto; display: flex; gap: 4px; }

.text-btn {
  font-size: 13px;
  border: none;
  background: none;
  color: var(--c-brand-500);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}
.text-btn:hover { background: var(--c-brand-50); }
.text-btn.danger { color: var(--c-danger); }
.text-btn.danger:hover { background: rgba(220, 38, 38, 0.06); }

.add-btn {
  font-size: 13px;
  font-weight: 500;
  color: var(--c-brand-500);
  border: none;
  background: var(--c-brand-50);
  padding: 5px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.add-btn:hover { background: rgba(46, 91, 255, 0.15); }

.center-text {
  text-align: center;
  padding: 24px;
  font-size: 13px;
  color: var(--c-gray-500);
}
.center-text.dim { color: var(--c-gray-400); font-size: 13px; }

/* ── Preferences ── */
.pref-list {
  display: flex;
  flex-direction: column;
}

.pref-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  gap: 12px;
}
.pref-item + .pref-item {
  border-top: 1px solid var(--border-light);
}

.pref-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--c-gray-700);
  flex-shrink: 0;
}

/* Segmented control */
.segmented {
  display: flex;
  background: var(--c-gray-100);
  border-radius: 8px;
  padding: 2px;
  gap: 0;
}

.seg-option {
  padding: 5px 12px;
  border: none;
  background: none;
  font-size: 12px;
  font-weight: 500;
  color: var(--c-gray-400);
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.15s;
  white-space: nowrap;
}
.seg-option.active {
  background: var(--surface-primary);
  color: var(--c-gray-800);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

/* Shortcut grid */
.shortcut-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 16px;
  font-size: 12px;
}

.shortcut {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--c-gray-500);
}
.shortcut span { white-space: nowrap; }

kbd {
  font-size: 11px;
  background: var(--c-gray-100);
  border: 1px solid var(--c-gray-300);
  border-radius: 4px;
  padding: 1px 6px;
  line-height: 1.5;
  color: var(--c-gray-600);
  font-family: inherit;
  min-width: 20px;
  text-align: center;
}

/* ── Password ── */
.pw-form {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pw-error {
  color: var(--c-danger);
  font-size: 13px;
  margin: 0;
}

.pw-save-btn {
  padding: 10px 20px;
  border: none;
  background: var(--c-brand-500);
  color: #fff;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
  align-self: flex-start;
}
.pw-save-btn:hover:not(:disabled) { background: var(--c-brand-600); }
.pw-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Logout ── */
.logout-btn {
  width: 100%;
  padding: 12px;
  background: none;
  color: var(--c-danger);
  border: none;
  font-size: 14px;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.12s;
  border-radius: 12px;
}
.logout-btn:hover { background: rgba(220, 38, 38, 0.06); }

/* ══════════════════════════════════════════ */
/* Tag Dialog                                */
/* ══════════════════════════════════════════ */

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.2s ease;
}
.dialog-fade-enter-active .tag-dialog,
.dialog-fade-leave-active .tag-dialog {
  transition: transform 0.2s var(--ease-standard);
}
.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}
.dialog-fade-enter-from .tag-dialog,
.dialog-fade-leave-to .tag-dialog {
  transform: scale(0.95) translateY(8px);
}

.tag-dialog {
  background: var(--surface-primary);
  border-radius: var(--r-modal);
  width: 100%;
  max-width: 380px;
  box-shadow: var(--sh-modal);
  overflow: hidden;
}

.tag-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 0;
}

.tag-dialog-header h3 {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
  color: var(--c-gray-900);
}

.dialog-close {
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  font-size: 22px;
  color: var(--c-gray-400);
  cursor: pointer;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dialog-close:hover { background: var(--c-gray-100); color: var(--c-gray-600); }

.tag-dialog-body {
  padding: 16px 20px;
}

.field { margin-bottom: 14px; }
.field:last-child { margin-bottom: 0; }

.field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-gray-500);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.field-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--c-gray-200);
  border-radius: 10px;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  background: var(--c-gray-50);
  color: var(--c-gray-900);
}
.field-input:focus {
  border-color: var(--c-brand-500);
  box-shadow: 0 0 0 3px var(--c-brand-50);
}

.color-row {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}

.color-swatch {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 2px solid transparent;
  cursor: pointer;
  transition: transform 0.12s, border-color 0.12s;
}
.color-swatch:hover { transform: scale(1.12); }
.color-swatch.active { border-color: var(--c-gray-900); transform: scale(1.12); }
:root.dark .color-swatch.active { border-color: #fff; }

.color-custom {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 6px;
}

.color-picker-native {
  width: 30px;
  height: 30px;
  border: 1px solid var(--c-gray-300);
  border-radius: 8px;
  cursor: pointer;
  padding: 2px;
  background: var(--surface-primary);
}

.color-custom-label {
  font-size: 11px;
  color: var(--c-gray-400);
}

.tag-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 0 20px 16px;
}

.btn-cancel {
  padding: 8px 18px;
  border: none;
  background: var(--c-gray-100);
  color: var(--c-gray-600);
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
.btn-cancel:hover { background: var(--c-gray-200); }

.btn-save {
  padding: 8px 22px;
  border: none;
  background: var(--c-brand-500);
  color: #fff;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-save:hover:not(:disabled) { background: var(--c-brand-600); }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }

/* ══════════════════════════════════════════ */
/* Mobile                                    */
/* ══════════════════════════════════════════ */

@media (max-width: 767px) {
  .settings-page {
    padding: 1rem 0.5rem 3rem;
  }

  .page-title {
    font-size: 22px;
    padding: 0 8px;
    margin-bottom: 1rem;
  }

  .card {
    border-radius: 12px;
    margin-bottom: 10px;
    border-left: none;
    border-right: none;
  }

  .card-header {
    padding: 12px 14px;
  }

  .account-row { padding: 14px; }
  .pref-item { padding: 12px 14px; flex-direction: column; align-items: flex-start; gap: 8px; }
  .tag-row { padding: 8px 14px; }

  .shortcut-grid {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  /* Mobile: dialog as bottom sheet */
  .dialog-overlay {
    align-items: flex-end;
    padding: 0;
  }

  .tag-dialog {
    max-width: 100%;
    border-radius: 16px 16px 0 0;
    max-height: 70vh;
    overflow-y: auto;
  }

  .tag-dialog-header { padding-top: 14px; }
}
</style>
