import Dexie, { type EntityTable } from 'dexie'
import type { Task, Tag } from '../types'
import { PRESET_TAGS } from '../types'
import { v4 as uuid, v5 as uuidV5 } from 'uuid'

/** 预设标签的确定性命名空间（保证跨设备同一标签 ID 一致） */
const PRESET_NAMESPACE = '6ba7b810-9dad-11d1-80b4-00c04fd430c8'

/** 辅助：将值钳制到 [min, max] 范围，无效值返回默认值 */
function clampNum(val: unknown, min: number, max: number, fallback: number): number {
  if (typeof val !== 'number' || isNaN(val)) return fallback
  return Math.max(min, Math.min(max, val))
}

// ===== 数据库定义 =====
// 注意：不索引 boolean 字段，IndexedDB 不支持 boolean 作为索引键
const db = new Dexie('SishiYouxuDB') as Dexie & {
  tasks: EntityTable<Task, 'id'>
  tags: EntityTable<Tag, 'id'>
}

db.version(3).stores({
  tasks: 'id, createdAt, updatedAt',
  tags: 'id',
}).upgrade((tx) => {
  // 清除旧数据（v1 boolean 索引 → v2 迁移 → v3 清理重复标签）
  return Promise.all([
    tx.table('tasks').clear(),
    tx.table('tags').clear(),
  ])
})

// ===== 预设标签（仅在云端创建，本地从云端拉取） =====
export async function createPresetTagsInCloud(userId: string): Promise<void> {
  const { supabase } = await import('../lib/supabase')
  const rows = PRESET_TAGS.map((t) => ({
    id: uuidV5(t.name, PRESET_NAMESPACE),
    user_id: userId,
    name: t.name,
    color: t.color,
    is_preset: true,
  }))
  const { error } = await supabase.from('sishi_tags').upsert(rows as any)
  if (error) console.error('[sync] 预设标签创建失败:', error.message)
}

// ===== 任务 CRUD =====
export const taskDB = {
  async getAll(): Promise<Task[]> {
    return db.tasks.orderBy('createdAt').toArray()
  },

  async getActive(): Promise<Task[]> {
    // 用 filter 而非 where，因为 IndexedDB 不支持 boolean 索引
    return db.tasks.filter((t) => !t.completed).toArray()
  },

  async getCompleted(): Promise<Task[]> {
    return db.tasks.filter((t) => t.completed).toArray()
  },

  async getById(id: string): Promise<Task | undefined> {
    return db.tasks.get(id)
  },

  async create(task: Task): Promise<string> {
    return db.tasks.add(task)
  },

  /** upsert：存在则更新，不存在则新增 */
  async createIfNotExists(task: Task): Promise<void> {
    const exists = !!(await db.tasks.get(task.id))
    if (exists) {
      await db.tasks.put(task)
    } else {
      await db.tasks.add(task)
    }
  },

  async update(id: string, changes: Partial<Task>): Promise<number> {
    return db.tasks.update(id, { ...changes, updatedAt: new Date().toISOString() })
  },

  async remove(id: string): Promise<void> {
    return db.tasks.delete(id)
  },

  /** 静默删除（不存在时不报错） */
  async removeSilent(id: string): Promise<void> {
    try { await db.tasks.delete(id) } catch { /* ignore */ }
  },

  async complete(id: string): Promise<number> {
    return db.tasks.update(id, {
      completed: true,
      completedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    })
  },

  async reopen(id: string): Promise<number> {
    return db.tasks.update(id, {
      completed: false,
      completedAt: null,
      updatedAt: new Date().toISOString(),
    })
  },

  async permanentRemove(id: string): Promise<void> {
    return db.tasks.delete(id)
  },

  async exportJSON(): Promise<string> {
    const tasks = await db.tasks.toArray()
    const tags = await db.tags.toArray()
    return JSON.stringify({ tasks, tags, exportedAt: new Date().toISOString() }, null, 2)
  },

  /** 批量导入任务和标签，返回导入统计 */
  async importJSON(
    jsonString: string,
    strategy: 'overwrite' | 'skip' | 'new',
  ): Promise<{ importedTasks: number; importedTags: number; skippedTasks: number; skippedTags: number }> {
    let data: { tasks?: unknown[]; tags?: unknown[] }
    try {
      data = JSON.parse(jsonString)
    } catch {
      throw new Error('JSON 格式无效，无法解析')
    }
    if (!data || typeof data !== 'object') throw new Error('数据格式不正确')
    if (!Array.isArray(data.tasks)) throw new Error('文件中没有有效的任务数据')

    const incomingTasks = data.tasks as Array<Partial<Task>>
    const incomingTags = Array.isArray(data.tags) ? (data.tags as Array<Partial<Tag>>) : []

    // ===== 标签导入（按名称去重合并） =====
    const existingTags = await db.tags.toArray()
    const existingTagNames = new Set(existingTags.map((t) => t.name))
    let importedTags = 0
    let skippedTags = 0

    for (const tag of incomingTags) {
      if (!tag.name || !tag.color) continue
      if (existingTagNames.has(tag.name)) {
        skippedTags++
        continue
      }
      await db.tags.add({
        id: uuid(),
        name: tag.name,
        color: tag.color,
        isPreset: false,
      })
      existingTagNames.add(tag.name)
      importedTags++
    }

    // ===== 任务导入 =====
    let importedTasks = 0
    let skippedTasks = 0

    // 构建标签名→ID 映射（用于将 JSON 中的标签名自动解析为本地 ID）
    const allTags = await db.tags.toArray()
    const tagNameToId = new Map<string, string>()
    for (const t of allTags) {
      tagNameToId.set(t.name, t.id)
    }

    for (const task of incomingTasks) {
      if (!task.id || !task.title) continue

      const exists = !!(await db.tasks.get(task.id))

      if (exists && strategy === 'skip') {
        skippedTasks++
        continue
      }

      // 解析标签：如果是标签名则转为 ID，已是 ID 则保留
      const resolvedTags = Array.isArray(task.tags)
        ? task.tags.map((tag: any) => (typeof tag === 'string' ? (tagNameToId.get(tag) || tag) : tag))
        : []

      const now = new Date().toISOString()
      const imported: Task = {
        id: task.id,
        title: task.title,
        posX: clampNum(task.posX, 0, 1, 0.5),
        posY: clampNum(task.posY, 0, 1, 0.5),
        urgencyLevel: clampNum(task.urgencyLevel, -4, 4, 0),
        importanceLevel: clampNum(task.importanceLevel, -4, 4, 0),
        dueDate: task.dueDate || null,
        tags: resolvedTags,
        note: task.note || '',
        recurrence: (task as any).recurrence || null,
        generatedNextId: (task as any).generatedNextId || undefined,
        completed: !!task.completed,
        completedAt: task.completedAt || null,
        createdAt: task.createdAt || now,
        updatedAt: now,
      }

      if (strategy === 'new') {
        imported.id = uuid()
      }

      if (exists && strategy === 'overwrite') {
        await db.tasks.put(imported, task.id!)
      } else {
        await db.tasks.put(imported)
      }
      importedTasks++
    }

    return { importedTasks, importedTags, skippedTasks, skippedTags }
  },
}

// ===== 标签 CRUD =====
export const tagDB = {
  async getAll(): Promise<Tag[]> {
    return db.tags.toArray()
  },

  async create(tag: Omit<Tag, 'id'>): Promise<string> {
    return db.tags.add({ ...tag, id: uuid() })
  },

  async createIfNotExists(tag: Tag): Promise<void> {
    const exists = !!(await db.tags.get(tag.id))
    if (exists) {
      await db.tags.update(tag.id, tag)
    } else {
      await db.tags.add(tag)
    }
  },

  async remove(id: string): Promise<void> {
    return db.tags.delete(id)
  },

  async removeSilent(id: string): Promise<void> {
    try { await db.tags.delete(id) } catch { /* ignore */ }
  },

  async getById(id: string): Promise<Tag | undefined> {
    return db.tags.get(id)
  },

  async update(id: string, changes: Partial<Tag>): Promise<number> {
    return db.tags.update(id, changes)
  },
}

export { db }
