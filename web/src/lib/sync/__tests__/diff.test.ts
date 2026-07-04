/**
 * @fileoverview deepEqual / diff 单元测试 — ConflictDialog 字段差异核心逻辑。
 *
 * 设计要点：
 *  - 深比较不应依赖对象 key 顺序（这正是从 JSON.stringify 迁移过来的原因）
 *  - 跳过 sync 元数据字段（syncStatus/version/createdAt/updatedAt/deletedAt）
 *  - null vs undefined 区分（前者表示"显式置空"）
 */
import { describe, it, expect } from 'vitest'
import { deepEqual, diff, SKIP_KEYS } from '../diff'

describe('deepEqual', () => {
  it('同值标量返回 true', () => {
    expect(deepEqual(1, 1)).toBe(true)
    expect(deepEqual('a', 'a')).toBe(true)
    expect(deepEqual(true, true)).toBe(true)
    expect(deepEqual(null, null)).toBe(true)
    expect(deepEqual(undefined, undefined)).toBe(true)
  })

  it('不同类型返回 false', () => {
    expect(deepEqual(1, '1')).toBe(false)
    expect(deepEqual(0, false)).toBe(false)
    expect(deepEqual(null, 0)).toBe(false)
  })

  it('null 与 undefined 区分', () => {
    expect(deepEqual(null, undefined)).toBe(false)
    expect(deepEqual({ a: null }, { a: undefined })).toBe(false)
  })

  it('数组 vs 对象返回 false', () => {
    expect(deepEqual([], {})).toBe(false)
    expect(deepEqual([1, 2], { 0: 1, 1: 2 })).toBe(false)
  })

  it('key 顺序无关', () => {
    expect(deepEqual({ a: 1, b: 2 }, { b: 2, a: 1 })).toBe(true)
    expect(deepEqual({ x: { a: 1, b: 2 } }, { x: { b: 2, a: 1 } })).toBe(true)
  })

  it('key 数量不同返回 false', () => {
    expect(deepEqual({ a: 1 }, { a: 1, b: 2 })).toBe(false)
  })

  it('嵌套对象递归比较', () => {
    expect(
      deepEqual({ a: { b: { c: [1, 2, 3] } } }, { a: { b: { c: [1, 2, 3] } } }),
    ).toBe(true)
    expect(
      deepEqual({ a: { b: { c: [1, 2, 3] } } }, { a: { b: { c: [1, 2, 4] } } }),
    ).toBe(false)
  })

  it('数组按索引比较', () => {
    expect(deepEqual([1, 2, 3], [1, 2, 3])).toBe(true)
    expect(deepEqual([1, 2, 3], [1, 3, 2])).toBe(false)
    expect(deepEqual([1, 2], [1, 2, 3])).toBe(false)
  })
})

describe('diff', () => {
  it('两侧都为空 → 空数组', () => {
    expect(diff(null, null)).toEqual([])
    expect(diff({}, {})).toEqual([])
  })

  it('仅一侧有字段 → 全字段差异', () => {
    expect(diff(null, { title: 'remote' })).toEqual([
      { key: 'title', local: undefined, remote: 'remote' },
    ])
    expect(diff({ title: 'local' }, null)).toEqual([
      { key: 'title', local: 'local', remote: undefined },
    ])
  })

  it('相同对象 → 空数组', () => {
    expect(diff({ a: 1, b: 2 }, { a: 1, b: 2 })).toEqual([])
  })

  it('key 顺序不影响结果', () => {
    const a = { title: 'A', urgencyLevel: 1, importanceLevel: 0 }
    const b = { importanceLevel: 0, urgencyLevel: 1, title: 'A' }
    expect(diff(a, b)).toEqual([])
  })

  it('只列出差异字段', () => {
    const local = { uuid: 'u1', title: 'local-title', completed: false, note: 'same' }
    const remote = { uuid: 'u1', title: 'remote-title', completed: false, note: 'same' }
    const rows = diff(local, remote)
    expect(rows).toEqual([
      { key: 'title', local: 'local-title', remote: 'remote-title' },
    ])
  })

  it('默认跳过 sync 元数据字段', () => {
    expect(SKIP_KEYS.has('syncStatus')).toBe(true)
    expect(SKIP_KEYS.has('version')).toBe(true)
    expect(SKIP_KEYS.has('createdAt')).toBe(true)
    expect(SKIP_KEYS.has('updatedAt')).toBe(true)
    expect(SKIP_KEYS.has('deletedAt')).toBe(true)

    const local = { title: 'A', updatedAt: '2024-01-01', syncStatus: 'pending' }
    const remote = { title: 'B', updatedAt: '2024-01-02', syncStatus: 'synced' }
    expect(diff(local, remote)).toEqual([
      { key: 'title', local: 'A', remote: 'B' },
    ])
  })

  it('允许自定义 skipKeys', () => {
    const local = { title: 'A', note: 'different' }
    const remote = { title: 'A', note: 'note' }
    // 不跳过 title/note，应都进 rows
    expect(diff(local, remote, new Set())).toEqual([
      { key: 'note', local: 'different', remote: 'note' },
    ])
  })

  it('嵌套对象不等时整字段作为一个差异行', () => {
    const local = { meta: { color: 'red', priority: 1 } }
    const remote = { meta: { color: 'blue', priority: 1 } }
    const rows = diff(local, remote)
    expect(rows).toEqual([
      { key: 'meta', local: { color: 'red', priority: 1 }, remote: { color: 'blue', priority: 1 } },
    ])
  })

  it('数组不等时整数组作为一个差异行', () => {
    const local = { checklist: ['a', 'b'] }
    const remote = { checklist: ['a', 'c'] }
    expect(diff(local, remote)).toEqual([
      { key: 'checklist', local: ['a', 'b'], remote: ['a', 'c'] },
    ])
  })
})