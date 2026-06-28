<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, type Announcement } from '@/api/admin'

const items = ref<Announcement[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// 筛选条件
const typeFilter = ref('')

// 弹窗相关
const dialogVisible = ref(false)
const dialogLoading = ref(false)
const editingItem = ref<Announcement | null>(null)
const formTitle = ref('')
const formContent = ref('')
const formType = ref('info')
const formIsPinned = ref(false)
const formIsActive = ref(true)
const formStartTime = ref('')
const formEndTime = ref('')

const typeOptions = [
  { label: '信息', value: 'info' },
  { label: '警告', value: 'warning' },
  { label: '严重', value: 'critical' },
]

const typeTagMap: Record<string, string> = { info: 'info', warning: 'warning', critical: 'danger' }
const typeLabelMap: Record<string, string> = { info: '信息', warning: '警告', critical: '严重' }

async function fetch() {
  loading.value = true
  try {
    const { data } = await adminApi.listAnnouncements({
      page: page.value,
      pageSize: pageSize.value,
      type: typeFilter.value || undefined,
    })
    items.value = data?.items ?? []
    total.value = data?.meta?.total ?? 0
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { loading.value = false }
}

function openAdd() {
  editingItem.value = null
  formTitle.value = ''
  formContent.value = ''
  formType.value = 'info'
  formIsPinned.value = false
  formIsActive.value = true
  formStartTime.value = ''
  formEndTime.value = ''
  dialogVisible.value = true
}

function openEdit(item: Announcement) {
  editingItem.value = item
  formTitle.value = item.title
  formContent.value = item.content
  formType.value = item.type
  formIsPinned.value = item.isPinned
  formIsActive.value = item.isActive
  formStartTime.value = item.startTime || ''
  formEndTime.value = item.endTime || ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formTitle.value.trim()) {
    ElMessage.warning('请输入公告标题')
    return
  }
  if (!formContent.value.trim()) {
    ElMessage.warning('请输入公告内容')
    return
  }
  dialogLoading.value = true
  try {
    const payload = {
      title: formTitle.value.trim(),
      content: formContent.value.trim(),
      type: formType.value,
      isPinned: formIsPinned.value,
      isActive: formIsActive.value,
      startTime: formStartTime.value || undefined,
      endTime: formEndTime.value || undefined,
    }
    if (editingItem.value) {
      await adminApi.updateAnnouncement(editingItem.value.uuid, payload as Record<string, unknown>)
      ElMessage.success('更新成功')
    } else {
      await adminApi.createAnnouncement(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '操作失败')
  } finally { dialogLoading.value = false }
}

async function handleDelete(item: Announcement) {
  try {
    await ElMessageBox.confirm(`确认删除公告「${item.title}」？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await adminApi.deleteAnnouncement(item.uuid)
    ElMessage.success('已删除')
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '删除失败')
  }
}

function handleTypeChange() {
  page.value = 1
  fetch()
}

function formatTime(iso: string | null) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(fetch)
</script>

<template>
  <div class="announcements">
    <h2 class="page-title">公告管理</h2>

    <div class="toolbar">
      <el-select v-model="typeFilter" placeholder="公告类型" clearable style="width:130px" @change="handleTypeChange">
        <el-option label="全部" value="" />
        <el-option
          v-for="o in typeOptions"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>
      <el-button type="primary" style="margin-left:auto" @click="openAdd">+ 新建公告</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
      <el-table-column label="类型" width="80">
        <template #default="{ row }">
          <el-tag :type="typeTagMap[row.type] as any" size="small">
            {{ typeLabelMap[row.type] || row.type }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="置顶" width="65">
        <template #default="{ row }">
          <el-tag v-if="row.isPinned" type="warning" size="small">置顶</el-tag>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="75">
        <template #default="{ row }">
          <el-tag :type="row.isActive ? 'success' : 'info'" size="small">
            {{ row.isActive ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="开始时间" width="160">
        <template #default="{ row }">{{ formatTime(row.startTime) }}</template>
      </el-table-column>
      <el-table-column label="结束时间" width="160">
        <template #default="{ row }">{{ formatTime(row.endTime) }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
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

    <!-- 新建/编辑公告弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingItem ? '编辑公告' : '新建公告'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px" @submit.prevent="handleSubmit">
        <el-form-item label="标题" required>
          <el-input v-model="formTitle" placeholder="请输入公告标题" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="formContent" type="textarea" :rows="5" placeholder="请输入公告内容" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="formType" style="width:100%">
            <el-option
              v-for="o in typeOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="置顶">
          <el-switch v-model="formIsPinned" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="formIsActive" />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="formStartTime"
            type="datetime"
            placeholder="选填"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width:100%"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="formEndTime"
            type="datetime"
            placeholder="选填"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width:100%"
          />
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
.text-muted { color: #94a3b8; }
</style>
