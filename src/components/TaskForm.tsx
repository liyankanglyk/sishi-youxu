import { useState, useEffect, useMemo } from 'react'
import { useStore } from '../store/useStore'
import { createEmptyTask, posToLevel, RECURRENCE_OPTIONS } from '../types'
import type { Task, Recurrence } from '../types'
import { v4 as uuid } from 'uuid'
import { marked } from 'marked'

interface TaskFormProps {
  onClose: () => void
}

export function TaskForm({ onClose }: TaskFormProps) {
  const editingTaskId = useStore((s) => s.editingTaskId)
  const tasks = useStore((s) => s.tasks)
  const tags = useStore((s) => s.tags)
  const isCreating = useStore((s) => s.isCreating)
  const createPosX = useStore((s) => s.createPosX)
  const createPosY = useStore((s) => s.createPosY)
  const addTask = useStore((s) => s.addTask)
  const updateTask = useStore((s) => s.updateTask)
  const deleteTask = useStore((s) => s.deleteTask)
  const addTag = useStore((s) => s.addTag)

  const existingTask = editingTaskId ? tasks.find((t) => t.id === editingTaskId) : null
  const isEdit = !!existingTask

  const [title, setTitle] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [note, setNote] = useState('')
  const [posX, setPosX] = useState(0.5)
  const [posY, setPosY] = useState(0.5)
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [recurrence, setRecurrence] = useState<Recurrence>(null)
  const [isNewTagOpen, setIsNewTagOpen] = useState(false)
  const [newTagName, setNewTagName] = useState('')
  const [newTagColor, setNewTagColor] = useState('#A78BFA')
  const [notePreview, setNotePreview] = useState(false)

  const renderedNote = useMemo(() => {
    if (!note.trim()) return ''
    try {
      return marked.parse(note) as string
    } catch {
      return note
    }
  }, [note])

  useEffect(() => {
    if (existingTask) {
      setTitle(existingTask.title)
      setDueDate(existingTask.dueDate ?? '')
      setNote(existingTask.note)
      setPosX(existingTask.posX)
      setPosY(existingTask.posY)
      setSelectedTags(existingTask.tags)
      setRecurrence(existingTask.recurrence || null)
    } else if (isCreating) {
      setTitle('')
      setDueDate('')
      setNote('')
      setPosX(createPosX)
      setPosY(createPosY)
      setSelectedTags([])
      setRecurrence(null)
    }
  }, [existingTask, isCreating, createPosX, createPosY])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return

    if (isEdit && existingTask) {
      await updateTask(existingTask.id, {
        title: title.trim(),
        dueDate: dueDate || null,
        note: note.trim(),
        posX,
        posY,
        tags: selectedTags,
        urgencyLevel: posToLevel(posX),
        importanceLevel: posToLevel(posY),
        recurrence,
      })
    } else {
      const task: Task = {
        ...createEmptyTask(),
        id: uuid(),
        title: title.trim(),
        dueDate: dueDate || null,
        note: note.trim(),
        posX,
        posY,
        urgencyLevel: posToLevel(posX),
        importanceLevel: posToLevel(posY),
        tags: selectedTags,
        recurrence,
      }
      await addTask(task)
    }
    onClose()
  }

  const handleDelete = async () => {
    if (isEdit && existingTask && window.confirm('确定删除这个任务吗？')) {
      await deleteTask(existingTask.id)
      onClose()
    }
  }

  const handleAddTag = async () => {
    if (!newTagName.trim()) return
    await addTag(newTagName.trim(), newTagColor)
    setNewTagName('')
    setIsNewTagOpen(false)
  }

  const toggleTag = (tagId: string) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    )
  }

  const urgencyLevel = posToLevel(posX)
  const importanceLevel = posToLevel(posY)

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/15 backdrop-blur-sm px-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="bg-white rounded-3xl shadow-xl shadow-purple-100/50 w-full max-w-md p-6
                   max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-gray-600">
            {isEdit ? '编辑任务' : '新建任务'}
          </h2>
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

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* 标题 */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">任务标题</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="输入任务标题…"
              className="w-full px-4 py-2.5 text-sm border-0 bg-gray-50 rounded-2xl
                         focus:outline-none focus:ring-2 focus:ring-purple-200 focus:bg-white
                         placeholder:text-gray-300 transition-all"
              autoFocus
            />
          </div>

          {/* 截止日期 + 重复 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5">截止日期</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-4 py-2.5 text-sm border-0 bg-gray-50 rounded-2xl
                           focus:outline-none focus:ring-2 focus:ring-purple-200 focus:bg-white
                           transition-all"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5">重复</label>
              <div className="flex gap-1 bg-gray-50 rounded-2xl p-0.5">
                {RECURRENCE_OPTIONS.map((opt) => (
                  <button
                    key={String(opt.value)}
                    type="button"
                    onClick={() => setRecurrence(opt.value)}
                    className={`flex-1 text-[10px] py-1.5 rounded-xl font-medium transition-all ${
                      recurrence === opt.value
                        ? 'bg-white text-purple-400 shadow-sm'
                        : 'text-gray-400 hover:text-gray-500'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* 优先级 */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-50 rounded-2xl px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-gray-500">紧急性</span>
                <span className="text-xs font-bold text-purple-400">{urgencyLevel}</span>
              </div>
              <input
                type="range" min="0" max="1" step="0.01"
                value={posX}
                onChange={(e) => setPosX(parseFloat(e.target.value))}
                className="w-full accent-purple-400"
              />
            </div>
            <div className="bg-gray-50 rounded-2xl px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-gray-500">重要性</span>
                <span className="text-xs font-bold text-purple-400">{importanceLevel}</span>
              </div>
              <input
                type="range" min="0" max="1" step="0.01"
                value={posY}
                onChange={(e) => setPosY(parseFloat(e.target.value))}
                className="w-full accent-purple-400"
              />
            </div>
          </div>

          {/* 标签 */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-2">标签</label>
            <div className="flex flex-wrap gap-2">
              {tags.map((tag) => (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() => toggleTag(tag.id)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-150 ${
                    selectedTags.includes(tag.id)
                      ? 'text-white shadow-sm scale-105'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}
                  style={selectedTags.includes(tag.id) ? { backgroundColor: tag.color } : {}}
                >
                  {tag.name}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setIsNewTagOpen(!isNewTagOpen)}
                className="px-3 py-1.5 rounded-full text-xs border border-dashed border-gray-300
                           text-gray-400 hover:border-purple-300 hover:text-purple-400 transition-colors"
              >
                + 新建
              </button>
            </div>

            {isNewTagOpen && (
              <div className="flex items-center gap-2 mt-3 p-3 bg-gray-50 rounded-2xl">
                <input
                  type="color"
                  value={newTagColor}
                  onChange={(e) => setNewTagColor(e.target.value)}
                  className="w-8 h-8 rounded-full border-0 cursor-pointer bg-transparent"
                />
                <input
                  type="text"
                  value={newTagName}
                  onChange={(e) => setNewTagName(e.target.value)}
                  placeholder="标签名称"
                  className="flex-1 px-3 py-1.5 text-xs bg-white border-0 rounded-xl
                             focus:outline-none focus:ring-2 focus:ring-purple-200
                             placeholder:text-gray-300 transition-all"
                />
                <button
                  type="button"
                  onClick={handleAddTag}
                  className="px-3 py-1.5 text-xs font-medium text-white bg-purple-400
                             rounded-xl hover:bg-purple-500 transition-colors flex-shrink-0"
                >
                  添加
                </button>
              </div>
            )}
          </div>

          {/* 备注 */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-gray-500">
                备注
                <span className="text-[10px] text-gray-350 ml-1 font-normal">支持 Markdown</span>
              </label>
              <button
                type="button"
                onClick={() => setNotePreview(!notePreview)}
                className={`text-[10px] px-2 py-0.5 rounded-lg font-medium transition-all ${
                  notePreview
                    ? 'bg-purple-100 text-purple-500'
                    : 'text-gray-400 hover:text-gray-500 hover:bg-gray-100'
                }`}
              >
                {notePreview ? '编辑' : '预览'}
              </button>
            </div>
            {notePreview ? (
              note.trim() ? (
                <div
                  className="w-full px-4 py-2.5 text-sm bg-gray-50 rounded-2xl min-h-[80px]
                             prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ __html: renderedNote }}
                />
              ) : (
                <div className="w-full px-4 py-2.5 text-sm text-gray-300 bg-gray-50 rounded-2xl min-h-[80px]
                                flex items-center justify-center">
                  暂无内容
                </div>
              )
            ) : (
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="添加备注…（支持 Markdown 语法）"
                rows={3}
                className="w-full px-4 py-2.5 text-sm border-0 bg-gray-50 rounded-2xl resize-none
                           focus:outline-none focus:ring-2 focus:ring-purple-200 focus:bg-white
                           placeholder:text-gray-300 transition-all"
              />
            )}
          </div>

          {/* 按钮 */}
          <div className="flex items-center justify-between pt-2">
            {isEdit ? (
              <button
                type="button"
                onClick={handleDelete}
                className="px-3 py-2 text-xs text-red-400 hover:text-red-500 hover:bg-red-50
                           rounded-xl transition-colors font-medium"
              >
                删除任务
              </button>
            ) : (
              <div />
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-5 py-2 text-xs font-medium text-gray-500 bg-gray-100
                           rounded-xl hover:bg-gray-200 transition-colors"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={!title.trim()}
                className="px-5 py-2 text-xs font-medium text-white bg-purple-400
                           rounded-xl hover:bg-purple-500 disabled:opacity-30 disabled:cursor-not-allowed
                           transition-all shadow-sm shadow-purple-200/50"
              >
                {isEdit ? '保存' : '创建'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
