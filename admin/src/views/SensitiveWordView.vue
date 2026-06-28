<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, type SensitiveWord } from '@/api/admin'

const items = ref<SensitiveWord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// Dialog
const dialogVisible = ref(false)
const dialogLoading = ref(false)
const editingItem = ref<SensitiveWord | null>(null)
const formWord = ref('')
const formLevel = ref(1)

const levelOptions = [
  { label: '低 (1)', value: 1 },
  { label: '中 (2)', value: 2 },
  { label: '高 (3)', value: 3 },
]

const levelTagMap: Record<number, string> = { 1: 'success', 2: 'warning', 3: 'danger' }
const levelLabelMap: Record<number, string> = { 1: '低', 2: '中', 3: '高' }

async function fetch() {
  loading.value = true
  try {
    const { data } = await adminApi.listSensitiveWords({ page: page.value, pageSize: pageSize.value })
    items.value = data?.items ?? []
    total.value = data?.meta?.total ?? 0
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { loading.value = false }
}

function openAdd() {
  editingItem.value = null
  formWord.value = ''
  formLevel.value = 1
  dialogVisible.value = true
}

function openEdit(item: SensitiveWord) {
  editingItem.value = item
  formWord.value = item.word
  formLevel.value = item.level
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formWord.value.trim()) {
    ElMessage.warning('请输入敏感词')
    return
  }
  dialogLoading.value = true
  try {
    if (editingItem.value) {
      await adminApi.updateSensitiveWord(editingItem.value.uuid, {
        word: formWord.value.trim(),
        level: formLevel.value,
      })
      ElMessage.success('更新成功')
    } else {
      await adminApi.addSensitiveWord({
        word: formWord.value.trim(),
        level: formLevel.value,
      })
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '操作失败')
  } finally { dialogLoading.value = false }
}

async function handleDelete(item: SensitiveWord) {
  try {
    await ElMessageBox.confirm(`确认删除敏感词「${item.word}」？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await adminApi.deleteSensitiveWord(item.uuid)
    ElMessage.success('已删除')
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '删除失败')
  }
}

// File import
const fileInput = ref<HTMLInputElement>()

function handleImportClick() {
  fileInput.value?.click()
}

async function handleFileChange(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files?.length) return
  try {
    const text = await files[0].text()
    if (!text.trim()) {
      ElMessage.warning('文件内容为空')
      return
    }
    const formData = new FormData()
    formData.append('words', text)
    await adminApi.importSensitiveWords(formData)
    ElMessage.success('导入成功')
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '导入失败')
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}

function formatTime(iso?: string) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(fetch)
</script>

<template>
  <div class="sensitive-words">
    <h2 class="page-title">敏感词管理</h2>

    <div class="toolbar">
      <el-button type="primary" @click="openAdd">+ 添加敏感词</el-button>
      <el-button @click="handleImportClick">批量导入</el-button>
      <input ref="fileInput" type="file" accept=".csv,.txt" style="display:none" @change="handleFileChange" />
    </div>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="word" label="敏感词" min-width="200" />
      <el-table-column label="等级" width="80">
        <template #default="{ row }">
          <el-tag :type="levelTagMap[row.level] as any" size="small">
            {{ levelLabelMap[row.level] || row.level }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="openEdit(row)">编辑</el-button>
          <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      style="margin-top:1rem;justify-content:flex-end"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="fetch"
    />

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingItem ? '编辑敏感词' : '添加敏感词'"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px" @submit.prevent="handleSubmit">
        <el-form-item label="敏感词" required>
          <el-input v-model="formWord" placeholder="请输入敏感词" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="等级" required>
          <el-select v-model="formLevel" style="width:100%">
            <el-option
              v-for="o in levelOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-title { margin: 0 0 1rem; font-size: 1.25rem; color: #1e293b; }
.toolbar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1rem;
}
</style>
