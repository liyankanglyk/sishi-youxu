import { useState, useMemo } from 'react'
import { useStore } from '../store/useStore'

interface TagManagerProps {
  onClose: () => void
}

export function TagManager({ onClose }: TagManagerProps) {
  const tags = useStore((s) => s.tags)
  const tasks = useStore((s) => s.tasks)
  const addTag = useStore((s) => s.addTag)
  const updateTag = useStore((s) => s.updateTag)
  const deleteTag = useStore((s) => s.deleteTag)

  // 每个标签被多少任务使用
  const tagUsage = useMemo(() => {
    const map: Record<string, number> = {}
    tags.forEach((t) => { map[t.id] = 0 })
    tasks.forEach((task) => {
      task.tags.forEach((tid) => {
        if (map[tid] !== undefined) map[tid]++
      })
    })
    return map
  }, [tags, tasks])

  // 新建标签
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState('#A78BFA')

  const handleAdd = async () => {
    if (!newName.trim()) return
    await addTag(newName.trim(), newColor)
    setNewName('')
  }

  // 编辑标签名
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editColor, setEditColor] = useState('')

  const startEdit = (id: string, name: string, color: string) => {
    setEditingId(id)
    setEditName(name)
    setEditColor(color)
  }

  const handleDelete = async (tagId: string) => {
    const count = tagUsage[tagId] || 0
    const tag = tags.find((t) => t.id === tagId)
    if (!tag) return
    if (tag.isPreset && count > 0) {
      alert(`预设标签「${tag.name}」被 ${count} 个任务使用，暂不可删除`)
      return
    }
    const msg = count > 0
      ? `确定删除标签「${tag.name}」？\n\n该标签被 ${count} 个任务使用，删除后这些任务将失去此标签。`
      : `确定删除标签「${tag.name}」？`
    if (!window.confirm(msg)) return
    await deleteTag(tagId)
  }

  // 快捷颜色预设
  const colorPresets = ['#6366F1', '#059669', '#EA580C', '#E8615C', '#A78BFA', '#D946EF', '#0EA5E9', '#84CC16', '#F59E0B']

  return (
    <div
      className="fixed inset-0 z-[110] flex items-center justify-center bg-black/15 backdrop-blur-sm px-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="bg-white rounded-3xl shadow-xl shadow-purple-100/50 w-full max-w-sm p-6 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题 */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold text-gray-600">管理标签</h2>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100
                       text-gray-300 hover:text-gray-500 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 标签列表 */}
        <div className="space-y-2 mb-5">
          {tags.map((tag) => {
            const isEditing = editingId === tag.id
            const count = tagUsage[tag.id] || 0
            return (
              <div
                key={tag.id}
                className="flex items-center gap-3 px-4 py-3 bg-gray-50 rounded-2xl group"
              >
                {/* 颜色 */}
                {isEditing ? (
                  <input
                    type="color"
                    value={editColor}
                    onChange={(e) => setEditColor(e.target.value)}
                    className="w-7 h-7 rounded-full border-0 cursor-pointer bg-transparent flex-shrink-0"
                  />
                ) : (
                  <div
                    className="w-4 h-4 rounded-full flex-shrink-0 ring-2 ring-white"
                    style={{ backgroundColor: tag.color }}
                  />
                )}

                {/* 名称 */}
                {isEditing ? (
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="flex-1 text-sm px-2 py-1 bg-white border-0 rounded-lg
                               focus:outline-none focus:ring-2 focus:ring-purple-200"
                    autoFocus
                    onBlur={async () => {
                      if (editName.trim() && (editName !== tag.name || editColor !== tag.color)) {
                        await updateTag(tag.id, { name: editName.trim(), color: editColor })
                      }
                      setEditingId(null)
                    }}
                    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }}
                  />
                ) : (
                  <span
                    className="flex-1 text-sm font-medium text-gray-600 cursor-pointer hover:text-purple-400 transition-colors"
                    onClick={() => startEdit(tag.id, tag.name, tag.color)}
                    title="点击编辑"
                  >
                    {tag.name}
                    {tag.isPreset && (
                      <span className="text-[10px] text-gray-350 ml-1.5">预设</span>
                    )}
                  </span>
                )}

                {/* 使用计数 */}
                <span className="text-[11px] text-gray-400 min-w-[20px] text-right">
                  {count}
                </span>

                {/* 删除 */}
                <button
                  onClick={() => handleDelete(tag.id)}
                  className="w-6 h-6 flex items-center justify-center rounded-full
                             text-gray-300 hover:text-red-400 hover:bg-red-50
                             opacity-0 group-hover:opacity-100 transition-all"
                  title="删除标签"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            )
          })}

          {tags.length === 0 && (
            <div className="text-center py-6 text-sm text-gray-400">暂无标签</div>
          )}
        </div>

        {/* 新建标签 */}
        <div className="border-t border-gray-100 pt-4">
          <h3 className="text-xs font-semibold text-gray-500 mb-3">新建标签</h3>
          <div className="flex items-center gap-2 mb-3">
            <input
              type="color"
              value={newColor}
              onChange={(e) => setNewColor(e.target.value)}
              className="w-8 h-8 rounded-full border-0 cursor-pointer bg-transparent flex-shrink-0"
            />
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="标签名称"
              className="flex-1 px-3 py-2 text-xs bg-gray-50 rounded-xl
                         focus:outline-none focus:ring-2 focus:ring-purple-200
                         placeholder:text-gray-300 transition-all"
              onKeyDown={(e) => { if (e.key === 'Enter') handleAdd() }}
            />
            <button
              onClick={handleAdd}
              disabled={!newName.trim()}
              className="px-4 py-2 text-xs font-medium text-white bg-purple-400
                         rounded-xl hover:bg-purple-500 disabled:opacity-30
                         disabled:cursor-not-allowed transition-all flex-shrink-0"
            >
              添加
            </button>
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {colorPresets.map((c) => (
              <button
                key={c}
                onClick={() => setNewColor(c)}
                className={`w-5 h-5 rounded-full transition-all ${
                  newColor === c ? 'ring-2 ring-offset-1 ring-purple-400 scale-110' : ''
                }`}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
