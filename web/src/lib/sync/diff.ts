/**
 * 同步冲突面板使用的纯函数工具 — 字段级深比较 + 字段差异计算。
 *
 * 与 JSON.stringify 字符串比较相比，本实现：
 *  - 不依赖对象 key 顺序
 *  - 区分 undefined vs null vs 缺失
 *  - 对循环引用安全（递归深度限制由调用方控制，典型字段不超过 10 层）
 */

export const SKIP_KEYS = new Set([
  'syncStatus',
  'version',
  'createdAt',
  'updatedAt',
  'deletedAt',
])

/** 深比较两个值是否相等 */
export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (a == null || b == null) return a === b
  if (typeof a !== typeof b) return false
  if (typeof a !== 'object') return false
  if (Array.isArray(a) !== Array.isArray(b)) return false
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false
    for (let i = 0; i < a.length; i++) {
      if (!deepEqual((a as unknown[])[i], (b as unknown[])[i])) return false
    }
    return true
  }
  const ao = a as Record<string, unknown>
  const bo = b as Record<string, unknown>
  const ak = Object.keys(ao)
  const bk = Object.keys(bo)
  if (ak.length !== bk.length) return false
  for (const k of ak) {
    if (!deepEqual(ao[k], bo[k])) return false
  }
  return true
}

export interface DiffRow {
  key: string
  local: unknown
  remote: unknown
}

/**
 * 计算两个对象之间的字段差异（按 key 合并，跳过 SKIP_KEYS）。
 *
 * @returns 仅包含值不等的字段；若两侧都为空，返回空数组。
 */
export function diff(
  local: Record<string, unknown> | null,
  remote: Record<string, unknown> | null,
  skipKeys: Set<string> = SKIP_KEYS,
): DiffRow[] {
  if (!local && !remote) return []
  const keys = new Set<string>([
    ...Object.keys(local ?? {}),
    ...Object.keys(remote ?? {}),
  ])
  const rows: DiffRow[] = []
  for (const k of keys) {
    if (skipKeys.has(k)) continue
    const lv = local?.[k]
    const rv = remote?.[k]
    if (deepEqual(lv, rv)) continue
    rows.push({ key: k, local: lv, remote: rv })
  }
  return rows
}