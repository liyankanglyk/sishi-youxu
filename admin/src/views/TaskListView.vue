<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, type AdminTaskListItem, type AdminTaskDetail } from '@/api/admin'

const router = useRouter()

// ── State ──
const items = ref<AdminTaskListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// Filters
const userUuidFilter = ref('')
const userSearchOptions = ref<Array<{ label: string; value: string }>>([])
const userSearchLoading = ref(false)

const quadrantFilter = ref<number | null>(null)
const completedFilter = ref<boolean | null>(null)

const tagUuidFilter = ref('')
const tagSearchOptions = ref<Array<{ label: string; value: string }>>([])
const tagSearchLoading = ref(false)

const startTimeFilter = ref('')
const endTimeFilter = ref('')

async function searchUsers(query: string) {
  if (!query) { userSearchOptions.value = []; return }
  userSearchLoading.value = true
  try {
    const { data } = await adminApi.searchUsers(query)
    userSearchOptions.value = (data?.items ?? []).map((u: any) => ({ label: `${u.nickname} (${u.uuid.slice(0, 8)}…)`, value: u.uuid }))
  } catch { userSearchOptions.value = [] }
  finally { userSearchLoading.value = false }
}

async function searchTags(query: string) {
  if (!query) { tagSearchOptions.value = []; return }
  tagSearchLoading.value = true
  try {
    const { data } = await adminApi.searchTags(query)
    tagSearchOptions.value = (data?.items ?? []).map((t: any) => ({ label: `${t.name} (${t.uuid.slice(0, 8)}…)`, value: t.uuid }))
  } catch { tagSearchOptions.value = [] }
  finally { tagSearchLoading.value = false }
}

const quadrantOptions = [
  { label: '全部', value: null },
  { label: 'Q1 重要+紧急', value: 1 },
  { label: 'Q2 重要+不紧急', value: 2 },
  { label: 'Q3 不重要+紧急', value: 3 },
  { label: 'Q4 不重要+不紧急', value: 4 },
]
const statusOptions = [
  { label: '全部', value: null },
  { label: '已完成', value: true },
  { label: '未完成', value: false },
]

// Selection
const selectedUuids = ref<string[]>([])

// Detail dialog
const dialogVisible = ref(false)
const dialogLoading = ref(false)
const detail = ref<AdminTaskDetail | null>(null)

// Create / Edit dialog
const formDialogVisible = ref(false)
const formDialogMode = ref<'create' | 'edit'>('create')
const formSaving = ref(false)
const form = ref({
  uuid: '',
  title: '',
  userUuid: '',
  urgencyLevel: 0,
  importanceLevel: 0,
  dueDate: '',
  note: '',
  tagUuids: [] as string[],
  completed: false,
})
const formTagOptions = ref<Array<{ label: string; value: string }>>([])
const formTagSearch = ref('')

function resetForm() {
  form.value = {
    uuid: '',
    title: '',
    userUuid: '',
    urgencyLevel: 0,
    importanceLevel: 0,
    dueDate: '',
    note: '',
    tagUuids: [],
    completed: false,
  }
  formTagSearch.value = ''
  formTagOptions.value = []
}

function openCreateDialog() {
  resetForm()
  formDialogMode.value = 'create'
  formDialogVisible.value = true
}

async function openEditDialog(item: AdminTaskListItem) {
  try {
    const { data } = await adminApi.getAdminTask(item.uuid)
    resetForm()
    form.value = {
      uuid: data.uuid,
      title: data.title,
      userUuid: data.userUuid,
      urgencyLevel: data.urgencyLevel,
      importanceLevel: data.importanceLevel,
      dueDate: data.dueDate ?? '',
      note: data.note ?? '',
      tagUuids: (data.tags ?? []).map(t => t.uuid),
      completed: data.completed,
    }
    formTagOptions.value = (data.tags ?? []).map(t => ({ label: t.name, value: t.uuid }))
    formDialogMode.value = 'edit'
    formDialogVisible.value = true
  } catch (err: any) {
    ElMessage.error(err?.message || '加载任务详情失败')
  }
}

async function searchFormTags(query: string) {
  if (!query) { formTagOptions.value = []; return }
  try {
    const { data } = await adminApi.searchTags(query)
    formTagOptions.value = (data?.items ?? []).map((t: any) => ({ label: `${t.name} (${t.uuid.slice(0, 8)}…)`, value: t.uuid }))
  } catch { formTagOptions.value = [] }
}

async function submitForm() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写任务标题')
    return
  }
  if (formDialogMode.value === 'create' && !form.value.userUuid) {
    ElMessage.warning('请选择所属用户')
    return
  }
  if (
    form.value.urgencyLevel < -4 || form.value.urgencyLevel > 4 ||
    form.value.importanceLevel < -4 || form.value.importanceLevel > 4
  ) {
    ElMessage.warning('紧急度/重要度必须在 -4 到 4 之间')
    return
  }

  formSaving.value = true
  try {
    if (formDialogMode.value === 'create') {
      await adminApi.createAdminTask({
        title: form.value.title.trim(),
        userUuid: form.value.userUuid,
        urgencyLevel: form.value.urgencyLevel,
        importanceLevel: form.value.importanceLevel,
        dueDate: form.value.dueDate || undefined,
        note: form.value.note || undefined,
        tagUuids: form.value.tagUuids.length ? form.value.tagUuids : undefined,
      })
      ElMessage.success('任务已创建')
    } else {
      await adminApi.updateAdminTask(form.value.uuid, {
        title: form.value.title.trim(),
        urgencyLevel: form.value.urgencyLevel,
        importanceLevel: form.value.importanceLevel,
        dueDate: form.value.dueDate || undefined,
        note: form.value.note || undefined,
        completed: form.value.completed,
        tagUuids: form.value.tagUuids,
      })
      ElMessage.success('任务已更新')
    }
    formDialogVisible.value = false
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '保存失败')
  } finally {
    formSaving.value = false
  }
}

// ── Methods ──

async function fetch() {
  loading.value = true
  try {
    const { data } = await adminApi.listAdminTasks({
      page: page.value,
      pageSize: pageSize.value,
      userUuid: userUuidFilter.value || undefined,
      quadrant: quadrantFilter.value ?? undefined,
      completed: completedFilter.value ?? undefined,
      tagUuid: tagUuidFilter.value || undefined,
      startTime: startTimeFilter.value || undefined,
      endTime: endTimeFilter.value || undefined,
    })
    items.value = data?.items ?? []
    total.value = data?.meta?.total ?? 0
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { loading.value = false }
}

function handleSearch() {
  page.value = 1
  selectedUuids.value = []
  fetch()
}

function handleReset() {
  userUuidFilter.value = ''
  userSearchOptions.value = []
  quadrantFilter.value = null
  completedFilter.value = null
  tagUuidFilter.value = ''
  tagSearchOptions.value = []
  startTimeFilter.value = ''
  endTimeFilter.value = ''
  handleSearch()
}

function handleSelectChange(rows: AdminTaskListItem[]) {
  selectedUuids.value = rows.map(r => r.uuid)
}

async function viewDetail(uuid: string) {
  dialogVisible.value = true
  dialogLoading.value = true
  try {
    const { data } = await adminApi.getAdminTask(uuid)
    detail.value = data
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { dialogLoading.value = false }
}

async function deleteSingle(item: AdminTaskListItem) {
  try {
    await ElMessageBox.confirm(`确认删除任务「${item.title}」？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await adminApi.deleteAdminTask(item.uuid)
    ElMessage.success('已删除')
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '删除失败')
  }
}

async function batchDelete() {
  if (!selectedUuids.value.length) {
    ElMessage.warning('请先选择任务')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认删除已选的 ${selectedUuids.value.length} 个任务？`,
      '批量删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch { return }
  try {
    const { data } = await adminApi.batchAdminTasks({
      action: 'delete',
      taskUuids: selectedUuids.value,
    })
    ElMessage.success(`已删除 ${data?.affected ?? selectedUuids.value.length} 个任务`)
    selectedUuids.value = []
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '操作失败')
  }
}

function quadrantLabel(urgency: number, importance: number): string {
  if (importance > 0 && urgency > 0) return 'Q1'
  if (importance > 0 && urgency <= 0) return 'Q2'
  if (importance <= 0 && urgency > 0) return 'Q3'
  return 'Q4'
}
const quadrantTagType = (urgency: number, importance: number) => {
  const q = quadrantLabel(urgency, importance)
  return q === 'Q1' ? 'danger' : q === 'Q2' ? 'success' : q === 'Q3' ? 'warning' : 'info'
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN')
}

function goToUser(uuid: string) {
  router.push(`/admin/users/${uuid}`)
}

onMounted(fetch)
</script>

<template>
  <div class="task-list">
    <h2 class="page-title">任务管理</h2>

    <!-- Toolbar -->
    <div class="toolbar">
      <el-select
        v-model="userUuidFilter"
        placeholder="所属用户"
        style="width:220px"
        filterable
        remote
        reserve-keyword
        clearable
        :remote-method="searchUsers"
        :loading="userSearchLoading"
        @change="handleSearch"
        @clear="handleSearch"
      >
        <el-option
          v-for="o in userSearchOptions"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>
      <el-select
        v-model="quadrantFilter"
        placeholder="象限"
        clearable
        style="width:160px"
        @change="handleSearch"
      >
        <el-option v-for="o in quadrantOptions" :key="String(o.value)" :label="o.label" :value="o.value" />
      </el-select>
      <el-select
        v-model="completedFilter"
        placeholder="完成状态"
        clearable
        style="width:130px"
        @change="handleSearch"
      >
        <el-option v-for="o in statusOptions" :key="String(o.value)" :label="o.label" :value="o.value" />
      </el-select>
      <el-select
        v-model="tagUuidFilter"
        placeholder="标签筛选"
        style="width:200px"
        filterable
        remote
        reserve-keyword
        clearable
        :remote-method="searchTags"
        :loading="tagSearchLoading"
        @change="handleSearch"
        @clear="handleSearch"
      >
        <el-option
          v-for="o in tagSearchOptions"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>
      <el-date-picker
        v-model="startTimeFilter"
        type="date"
        placeholder="开始时间"
        value-format="YYYY-MM-DD"
        style="width:150px"
        @change="handleSearch"
      />
      <el-date-picker
        v-model="endTimeFilter"
        type="date"
        placeholder="结束时间"
        value-format="YYYY-MM-DD"
        style="width:150px"
        @change="handleSearch"
      />
      <el-button type="primary" @click="handleSearch">搜索</el-button>
      <el-button @click="handleReset">重置</el-button>
      <div style="flex:1" />
      <el-button type="primary" @click="openCreateDialog">+ 新建任务</el-button>
    </div>

    <!-- Batch toolbar -->
    <div v-if="selectedUuids.length" class="batch-bar">
      <span>已选 {{ selectedUuids.length }} 项</span>
      <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
    </div>

    <!-- Table -->
    <el-table
      :data="items"
      v-loading="loading"
      stripe
      @selection-change="handleSelectChange"
    >
      <el-table-column type="selection" width="45" />
      <el-table-column prop="title" label="任务标题" min-width="180" show-overflow-tooltip />
      <el-table-column label="所属用户" width="120">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="goToUser(row.userUuid)">
            {{ row.userNickname }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column label="象限" width="120">
        <template #default="{ row }">
          <el-tag :type="quadrantTagType(row.urgencyLevel, row.importanceLevel)" size="small">
            {{ quadrantLabel(row.urgencyLevel, row.importanceLevel) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.completed ? 'success' : 'info'" size="small">
            {{ row.completed ? '已完成' : '未完成' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="标签" min-width="160">
        <template #default="{ row }">
          <el-tag
            v-for="tag in row.tags"
            :key="tag.uuid"
            :color="tag.color"
            :style="{ borderColor: tag.color, color: '#fff' }"
            size="small"
            style="margin-right:4px"
          >
            {{ tag.name }}
          </el-tag>
          <span v-if="!row.tags?.length" style="color:#94a3b8">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="dueDate" label="截止日期" width="110">
        <template #default="{ row }">{{ row.dueDate ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="viewDetail(row.uuid)">详情</el-button>
          <el-button link type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="deleteSingle(row)">删除</el-button>
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

    <!-- Detail Dialog -->
    <el-dialog
      v-model="dialogVisible"
      title="任务详情"
      width="680px"
      :close-on-click-modal="false"
    >
      <div v-loading="dialogLoading" v-if="detail" class="task-detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="标题" :span="2">{{ detail.title }}</el-descriptions-item>
          <el-descriptions-item label="所属用户">
            <el-button link type="primary" @click="goToUser(detail.userUuid); dialogVisible = false">
              {{ detail.userNickname }}
            </el-button>
          </el-descriptions-item>
          <el-descriptions-item label="象限">
            <el-tag :type="quadrantTagType(detail.urgencyLevel, detail.importanceLevel)" size="small">
              {{ quadrantLabel(detail.urgencyLevel, detail.importanceLevel) }}
            </el-tag>
            (紧急度 {{ detail.urgencyLevel }}, 重要度 {{ detail.importanceLevel }})
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detail.completed ? 'success' : 'info'" size="small">
              {{ detail.completed ? '已完成' : '未完成' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ detail.completedAt ? formatTime(detail.completedAt) : '—' }}</el-descriptions-item>
          <el-descriptions-item label="截止日期">{{ detail.dueDate ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="重复规则">{{ detail.recurrence ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="排序值">{{ detail.sortOrder }}</el-descriptions-item>
          <el-descriptions-item label="标签" :span="2">
            <el-tag
              v-for="tag in detail.tags"
              :key="tag.uuid"
              :color="tag.color"
              :style="{ borderColor: tag.color, color: '#fff' }"
              size="small"
              style="margin-right:4px"
            >
              {{ tag.name }}
            </el-tag>
            <span v-if="!detail.tags?.length">无</span>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detail.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatTime(detail.updatedAt) }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">
            <pre v-if="detail.note" style="margin:0;white-space:pre-wrap;font-size:13px">{{ detail.note }}</pre>
            <span v-else>—</span>
          </el-descriptions-item>
        </el-descriptions>

        <!-- Checklist -->
        <div v-if="detail.checklist?.length" style="margin-top:1rem">
          <h4 style="margin-bottom:0.5rem">检查项 ({{ detail.checklist.filter(c => c.completed).length }}/{{ detail.checklist.length }})</h4>
          <el-table :data="detail.checklist" size="small" stripe>
            <el-table-column prop="title" label="内容" show-overflow-tooltip />
            <el-table-column label="完成" width="70">
              <template #default="{ row }">
                <el-tag :type="row.completed ? 'success' : 'info'" size="small">
                  {{ row.completed ? '✓' : '✗' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="sortOrder" label="排序" width="60" />
          </el-table>
        </div>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="formDialogVisible"
      :title="formDialogMode === 'create' ? '新建任务' : '编辑任务'"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="90px" label-position="right">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="200" show-word-limit placeholder="请输入任务标题" />
        </el-form-item>

        <el-form-item v-if="formDialogMode === 'create'" label="所属用户" required>
          <el-select
            v-model="form.userUuid"
            placeholder="搜索并选择用户"
            filterable
            remote
            reserve-keyword
            clearable
            :remote-method="searchUsers"
            :loading="userSearchLoading"
            style="width:100%"
          >
            <el-option
              v-for="o in userSearchOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="紧急度">
          <div style="display:flex;align-items:center;gap:0.75rem;width:100%">
            <el-slider
              v-model="form.urgencyLevel"
              :min="-4"
              :max="4"
              :step="1"
              show-stops
              style="flex:1"
            />
            <el-input-number
              v-model="form.urgencyLevel"
              :min="-4"
              :max="4"
              :step="1"
              size="small"
              controls-position="right"
              style="width:110px"
            />
          </div>
        </el-form-item>

        <el-form-item label="重要度">
          <div style="display:flex;align-items:center;gap:0.75rem;width:100%">
            <el-slider
              v-model="form.importanceLevel"
              :min="-4"
              :max="4"
              :step="1"
              show-stops
              style="flex:1"
            />
            <el-input-number
              v-model="form.importanceLevel"
              :min="-4"
              :max="4"
              :step="1"
              size="small"
              controls-position="right"
              style="width:110px"
            />
          </div>
        </el-form-item>

        <el-form-item label="象限预览">
          <el-tag :type="quadrantTagType(form.urgencyLevel, form.importanceLevel)" size="small">
            {{ quadrantLabel(form.urgencyLevel, form.importanceLevel) }}
          </el-tag>
          <span style="margin-left:0.5rem;color:#64748b;font-size:13px">
            横轴：紧急度 {{ form.urgencyLevel }} ｜ 纵轴：重要度 {{ form.importanceLevel }}
          </span>
        </el-form-item>

        <el-form-item label="截止日期">
          <el-date-picker
            v-model="form.dueDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="可选"
            style="width:100%"
          />
        </el-form-item>

        <el-form-item label="标签">
          <el-select
            v-model="form.tagUuids"
            multiple
            filterable
            remote
            :remote-method="searchFormTags"
            :loading="tagSearchLoading"
            reserve-keyword
            placeholder="搜索标签（可选）"
            style="width:100%"
          >
            <el-option
              v-for="o in formTagOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item v-if="formDialogMode === 'edit'" label="完成状态">
          <el-switch v-model="form.completed" />
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="form.note"
            type="textarea"
            :rows="3"
            placeholder="可选"
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formSaving" @click="submitForm">
          {{ formDialogMode === 'create' ? '创建' : '保存' }}
        </el-button>
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
  flex-wrap: wrap;
}
.batch-bar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  margin-bottom: 0.75rem;
  font-size: 13px;
  color: #991b1b;
}
.task-detail pre {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 0.75rem;
  font-family: 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
  font-size: 13px;
}
</style>
