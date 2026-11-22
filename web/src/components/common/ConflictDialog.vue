<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { useSync } from '@/lib/sync'
import type { ConflictInfo } from '@/lib/sync'
import { diff as computeDiff, type DiffRow } from '@/lib/sync/diff'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const { state, resolveConflict } = useSync()

const conflicts = computed<ConflictInfo[]>(() => state.conflicts)

function close() { emit('update:open', false) }

// =========================================================================
// 字段元数据 —— 把后端 camelCase 字段映射成"用户可读"的中文标签 + 渲染器
// =========================================================================

type FieldKind = 'text' | 'number' | 'date' | 'datetime' | 'enum' | 'tags' | 'note' | 'boolean'

interface FieldMeta {
  label: string
  kind: FieldKind
  /** 枚举值映射（仅 kind === 'enum'） */
  enumMap?: Record<string, string>
  /** 是否为「低优先级」字段 —— 自动合并时优先丢弃（服务端为权威） */
  lowPriority?: boolean
}

const FIELD_META: Record<string, FieldMeta> = {
  title:              { label: '标题',          kind: 'text' },
  note:               { label: '备注',          kind: 'note', lowPriority: true },
  urgencyLevel:       { label: '紧急度',        kind: 'number' },
  importanceLevel:    { label: '重要度',        kind: 'number' },
  dueDate:            { label: '截止日期',      kind: 'date' },
  recurrence:         { label: '重复规则',      kind: 'enum', enumMap: { '': '不重复', daily: '每天', weekdays: '工作日', weekly: '每周', biweekly: '每两周', monthly: '每月' } },
  remindAt:           { label: '首次提醒时间',  kind: 'datetime' },
  remindOffsetMinutes:{ label: '提前提醒（分钟）', kind: 'number' },
  reminderState:      { label: '提醒状态',      kind: 'enum', enumMap: { idle: '空闲', scheduled: '已排程', sent: '已发送', dismissed: '已忽略' } },
  completed:          { label: '已完成',        kind: 'boolean' },
  completedAt:        { label: '完成时间',      kind: 'datetime' },
  sortOrder:          { label: '排序权重',      kind: 'number', lowPriority: true },
  // tag 是数组
  tags:               { label: '标签',          kind: 'tags' },
  // tag / checklist 实体字段
  name:               { label: '名称',          kind: 'text' },
  color:              { label: '颜色',          kind: 'text' },
}

const SKIP_KEYS_FOR_LABEL = new Set(['uuid', 'userUuid', 'version', 'syncStatus'])

// =========================================================================
// 字段值格式化 —— 对不同类型做可读化处理
// =========================================================================

function isHexColor(v: unknown): boolean {
  return typeof v === 'string' && /^#[0-9A-Fa-f]{6}$/.test(v)
}

function normalizeTags(value: unknown): string[] {
  if (value == null) return []
  if (Array.isArray(value)) {
    return value.map((t: any) => {
      if (typeof t === 'string') return t
      if (t && typeof t === 'object') return t.name || t.uuid || String(t)
      return String(t)
    })
  }
  return [String(value)]
}

function formatFieldValue(key: string, value: unknown): string {
  const meta = FIELD_META[key]
  const kind: FieldKind = meta?.kind ?? 'text'

  if (value == null) return '（空）'

  if (kind === 'tags') {
    const tags = normalizeTags(value)
    return tags.length ? tags.map(t => `#${t}`).join('  ') : '（空）'
  }
  if (kind === 'enum') {
    const map = meta?.enumMap ?? {}
    return map[String(value)] ?? String(value)
  }
  if (kind === 'boolean') {
    return value ? '✓ 是' : '✗ 否'
  }
  if (kind === 'date') {
    return String(value).slice(0, 10) || '（空）'
  }
  if (kind === 'datetime') {
    if (!value) return '（空）'
    const d = new Date(String(value))
    if (isNaN(d.getTime())) return String(value)
    return d.toLocaleString('zh-CN', { hour12: false })
  }
  if (kind === 'number') {
    return typeof value === 'number' ? String(value) : '（空）'
  }
  // text / note —— 颜色特殊处理
  if (key === 'color' && isHexColor(value)) return value as string
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function isEmpty(value: unknown): boolean {
  return value == null || value === '' || (Array.isArray(value) && value.length === 0)
}

// =========================================================================
// 字段粒度选择 —— 每行一个"用本地/用远程"小开关
// =========================================================================

interface PerFieldChoice { key: string; choice: 'local' | 'remote' }

const choices = reactive(new Map<string, PerFieldChoice[]>())

/** 当 conflicts 变化时，重置所有选择为默认：字段非空一侧优先（自动合并的雏形） */
watch(conflicts, (cs) => {
  choices.clear()
  for (const c of cs) {
    const rows = computeDiff(c.local, c.remote)
    const arr: PerFieldChoice[] = rows.map((row) => ({
      key: row.key,
      // 默认规则：本地有值则用本地，否则用远程（保留本地的实际修改）
      choice: !isEmpty(row.local) ? 'local' : 'remote',
    }))
    choices.set(c.opId, arr)
  }
}, { immediate: true, deep: true })

function getChoice(opId: string, key: string): 'local' | 'remote' | undefined {
  return choices.get(opId)?.find(c => c.key === key)?.choice
}

function setChoice(opId: string, key: string, choice: 'local' | 'remote') {
  const arr = choices.get(opId)
  if (!arr) return
  const found = arr.find(c => c.key === key)
  if (found) found.choice = choice
}

function allFieldRows(c: ConflictInfo): DiffRow[] {
  return computeDiff(c.local, c.remote)
}

function fieldLabel(key: string): string {
  if (FIELD_META[key]) return FIELD_META[key].label
  if (SKIP_KEYS_FOR_LABEL.has(key)) return key
  // 未知字段 —— 至少转成可读形式（如 createdAt → 创建时间）
  return key
}

// =========================================================================
// 时间显示
// =========================================================================

function timeAgo(iso?: string): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  const diff = Date.now() - t
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return new Date(iso).toLocaleString()
}

// =========================================================================
// 解决动作
// =========================================================================

/** 整条用本地 —— 走现有的保留本地逻辑 */
async function resolveLocal(opId: string) {
  await resolveConflict(opId, 'local')
}

/** 整条用远程 */
async function resolveRemote(opId: string) {
  await resolveConflict(opId, 'remote')
}

/** 智能合并 —— 按字段粒度合成新 record 后入队 upsert
 *
 * 算法：
 *  1. 以服务端 record 为基线
 *  2. 对每个有差异的字段，按用户的选择（local/remote）覆盖
 *  3. 把 merged 写回本地 → 入队 upsert → 触发重新推送
 */
async function mergeFields(c: ConflictInfo) {
  const fieldChoices = choices.get(c.opId) ?? []
  const merged: Record<string, unknown> = { ...(c.remote ?? {}) }
  for (const fc of fieldChoices) {
    const row = allFieldRows(c).find(r => r.key === fc.key)
    if (!row) continue
    merged[fc.key] = fc.choice === 'local' ? row.local : row.remote
  }
  // 1. 把原冲突 op 从队列移除，避免重复
  const idx = state.conflicts.findIndex((x) => x.opId === c.opId)
  if (idx >= 0) state.conflicts.splice(idx, 1)
  // 2. 写回本地（按 LocalTask 形态写入 db.tasks.put）
  await db.tasks.put({
    ...(c.local ?? {}),
    ...merged,
    syncStatus: 'pending',
    updatedAt: new Date().toISOString(),
  } as any)
  // 3. 入队 upsert（payload 仅含被合并的字段 + 标识）
  await enqueueOp(c.entityType, 'upsert', c.entityUuid, merged)
  // 4. 触发同步
  syncEngine.schedule()
}

import { syncEngine } from '@/lib/sync/engine'
import { db } from '@/db'
import { enqueueOp } from '@/lib/sync/repository'
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="props.open" class="conflict-scrim" @click.self="close">
        <div class="conflict-modal" role="dialog" aria-modal="true">
          <header class="conflict-header">
            <div class="conflict-header-text">
              <h3>同步冲突</h3>
              <p>本地与服务端版本不同。逐字段选择保留哪一侧，或整条采用其一。</p>
            </div>
            <button class="close-btn" aria-label="关闭" @click="close">×</button>
          </header>

          <div class="conflict-body">
            <div v-if="conflicts.length === 0" class="conflict-empty">
              没有待解决的冲突
            </div>
            <article v-for="c in conflicts" :key="c.opId" class="conflict-card">
              <div class="conflict-meta">
                <span class="conflict-kind">{{ c.entityType }}</span>
                <h4 class="conflict-title">{{ c.displayName }}</h4>
                <span class="conflict-time">本地：{{ timeAgo((c.local?.updatedAt as string) ?? (c.local?.createdAt as string)) }}</span>
              </div>

              <div class="conflict-rows">
                <div v-for="row in allFieldRows(c)" :key="row.key" class="conflict-row">
                  <span class="row-key">{{ fieldLabel(row.key) }}</span>
                  <span
                    class="row-cell row-local"
                    :class="{ selected: getChoice(c.opId, row.key) === 'local', empty: isEmpty(row.local) }"
                    @click="setChoice(c.opId, row.key, 'local')"
                    :title="'点击选择本地'"
                  >
                    <span v-if="row.key === 'color'" class="color-dot" :style="{ backgroundColor: formatFieldValue(row.key, row.local) }" />
                    <span v-else class="row-text">{{ formatFieldValue(row.key, row.local) }}</span>
                  </span>
                  <span class="row-vs" aria-hidden="true">⇄</span>
                  <span
                    class="row-cell row-remote"
                    :class="{ selected: getChoice(c.opId, row.key) === 'remote', empty: isEmpty(row.remote) }"
                    @click="setChoice(c.opId, row.key, 'remote')"
                    :title="'点击选择服务端'"
                  >
                    <span v-if="row.key === 'color'" class="color-dot" :style="{ backgroundColor: formatFieldValue(row.key, row.remote) }" />
                    <span v-else class="row-text">{{ formatFieldValue(row.key, row.remote) }}</span>
                  </span>
                </div>
                <div v-if="allFieldRows(c).length === 0" class="conflict-row single">
                  <span class="row-key">状态</span>
                  <span class="row-cell">{{ c.local ? '本地已修改' : '本地未修改' }}</span>
                  <span class="row-vs" aria-hidden="true"></span>
                  <span class="row-cell">{{ c.remote ? '服务端已变更' : '服务端已删除' }}</span>
                </div>
              </div>

              <div class="conflict-actions">
                <span class="conflict-hint">
                  <span class="legend-dot legend-local" />已选本地
                  <span class="legend-dot legend-remote" />已选远程
                </span>
                <button class="btn btn-ghost" @click="resolveRemote(c.opId)">整条用服务端</button>
                <button class="btn btn-ghost" @click="mergeFields(c)">字段合并</button>
                <button class="btn btn-primary" @click="resolveLocal(c.opId)">整条保留本地</button>
              </div>
            </article>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.conflict-scrim {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}

.conflict-modal {
  background: var(--surface-primary, #fff);
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
  max-width: 640px;
  width: 100%;
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.conflict-header {
  padding: 18px 20px 14px;
  position: relative;
  border-bottom: 1px solid var(--border-light, #F1F5F9);
}
.conflict-header-text { padding-right: 32px; }
.conflict-header h3 {
  font-size: 17px;
  margin: 0 0 4px;
}
.conflict-header p {
  font-size: 13px;
  color: var(--c-gray-500, #71717A);
  margin: 0;
  line-height: 1.5;
}
.close-btn {
  position: absolute;
  top: 12px;
  right: 14px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--c-gray-500, #71717A);
  cursor: pointer;
}
.close-btn:hover { background: var(--c-gray-100, #F4F4F5); }

.conflict-body {
  overflow-y: auto;
  padding: 16px 20px;
  flex: 1 1 auto;
}

.conflict-empty {
  text-align: center;
  color: var(--c-gray-500, #71717A);
  padding: 40px 0;
  font-size: 14px;
}

.conflict-card {
  border: 1px solid var(--border-light, #F1F5F9);
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 14px;
  background: var(--surface-primary, #fff);
}

.conflict-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.conflict-kind {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--c-brand-50, #EEF2FF);
  color: var(--c-brand-500, #2E5BFF);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.conflict-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  flex: 1 1 auto;
  word-break: break-word;
}

.conflict-time {
  font-size: 13px;
  color: var(--c-gray-500);
}

.conflict-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.conflict-row {
  display: grid;
  grid-template-columns: 110px 1fr 24px 1fr;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  background: var(--c-gray-50, #FAFAFA);
  font-size: 13px;
  align-items: center;
}

.conflict-row.single {
  grid-template-columns: 110px 1fr 0 1fr;
}

.row-key {
  color: var(--c-gray-700, #3F3F46);
  font-weight: 500;
  font-size: 13px;
}

.row-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1.5px solid transparent;
  background: var(--surface-primary, #fff);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.12s ease;
  min-height: 32px;
  overflow: hidden;
  word-break: break-word;
  user-select: none;
}
.row-cell:hover { border-color: var(--c-gray-300, #D4D4D8); }
.row-cell.selected {
  font-weight: 600;
  box-shadow: 0 0 0 1.5px currentColor;
}
.row-cell.row-local { color: var(--c-warning); }
.row-cell.row-local.selected { background: var(--week-soft); border-color: var(--c-warning); }
.row-cell.row-remote { color: var(--c-brand-500, #2E5BFF); }
.row-cell.row-remote.selected { background: var(--c-brand-50, #EEF2FF); border-color: var(--c-brand-500, #2E5BFF); }
.row-cell.empty { color: var(--c-gray-400, #A1A1AA); font-style: italic; }

.row-text { overflow: hidden; text-overflow: ellipsis; }

.color-dot {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1px solid var(--c-gray-300, #D4D4D8);
  flex-shrink: 0;
}

.row-vs {
  text-align: center;
  color: var(--c-gray-400, #A1A1AA);
  font-size: 13px;
}

.conflict-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  align-items: center;
  flex-wrap: wrap;
}

.conflict-hint {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--c-gray-500, #71717A);
  margin-right: auto;
}

.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 2px;
  vertical-align: middle;
}
.legend-local { background: var(--c-warning); }
.legend-remote { background: var(--c-brand-500, #2E5BFF); margin-left: 8px; }

.btn {
  padding: 7px 14px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.btn-ghost {
  background: transparent;
  border-color: var(--border-light, #E4E4E7);
  color: var(--c-gray-700, #3F3F46);
}
.btn-ghost:hover { background: var(--c-gray-100, #F4F4F5); }

.btn-primary {
  background: var(--c-brand-500, #2E5BFF);
  color: #fff;
}
.btn-primary:hover { background: var(--c-brand-600, #1E40D0); }

/* 过渡 */
.modal-fade-enter-active, .modal-fade-leave-active {
  transition: opacity 0.18s ease;
}
.modal-fade-enter-from, .modal-fade-leave-to {
  opacity: 0;
}
</style>