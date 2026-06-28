<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, type AdminTagListItem, type AdminTagDetail } from '@/api/admin'

// ── State ──
const items = ref<AdminTagListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// Filters
const userUuidFilter = ref('')
const userSearchOptions = ref<Array<{ label: string; value: string }>>([])
const userSearchLoading = ref(false)
const qFilter = ref('')

async function searchUsers(query: string) {
  if (!query) { userSearchOptions.value = []; return }
  userSearchLoading.value = true
  try {
    const { data } = await adminApi.searchUsers(query)
    userSearchOptions.value = (data?.items ?? []).map((u: any) => ({ label: `${u.nickname} (${u.uuid.slice(0, 8)}…)`, value: u.uuid }))
  } catch { userSearchOptions.value = [] }
  finally { userSearchLoading.value = false }
}

// Dialog
const dialogVisible = ref(false)
const dialogLoading = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingUuid = ref<string | null>(null)
const formName = ref('')
const formColor = ref('#6366f1')

// Detail dialog
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<AdminTagDetail | null>(null)

// ── Methods ──

async function fetch() {
  loading.value = true
  try {
    const { data } = await adminApi.listAdminTags({
      page: page.value,
      pageSize: pageSize.value,
      userUuid: userUuidFilter.value || undefined,
      q: qFilter.value || undefined,
    })
    items.value = data?.items ?? []
    total.value = data?.meta?.total ?? 0
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { loading.value = false }
}

function handleSearch() {
  page.value = 1
  fetch()
}
function handleReset() {
  userUuidFilter.value = ''
  userSearchOptions.value = []
  qFilter.value = ''
  handleSearch()
}

function openCreate() {
  dialogMode.value = 'create'
  editingUuid.value = null
  formName.value = ''
  formColor.value = '#6366f1'
  dialogVisible.value = true
}

function openEdit(item: AdminTagListItem) {
  dialogMode.value = 'edit'
  editingUuid.value = item.uuid
  formName.value = item.name
  formColor.value = item.color
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formName.value.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  if (formName.value.trim().length > 50) {
    ElMessage.warning('标签名称不能超过 50 字符')
    return
  }
  dialogLoading.value = true
  try {
    if (dialogMode.value === 'create') {
      // Create via user-level API is not available in admin context,
      // but admin can list/update/delete. Redirect to user scoped api is not the right path.
      // Actually adminApi doesn't have create tag — admin can only edit/delete existing tags.
      // We should show editing dialog but skip create for now.
      ElMessage.info('管理员暂不支持创建标签，请使用编辑功能')
      dialogVisible.value = false
      return
    } else {
      await adminApi.patchAdminTag(editingUuid.value!, {
        name: formName.value.trim(),
        color: formColor.value,
      })
      ElMessage.success('已更新')
      dialogVisible.value = false
      fetch()
    }
  } catch (err: any) {
    ElMessage.error(err?.message || '操作失败')
  } finally { dialogLoading.value = false }
}

async function deleteTag(item: AdminTagListItem) {
  try {
    const msg = item.taskCount
      ? `确认删除标签「${item.name}」？与之关联的 ${item.taskCount} 个任务将解除关联。`
      : `确认删除标签「${item.name}」？`
    await ElMessageBox.confirm(msg, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await adminApi.deleteAdminTag(item.uuid)
    ElMessage.success('已删除')
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '删除失败')
  }
}

async function viewDetail(uuid: string) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    const { data } = await adminApi.getAdminTag(uuid)
    detail.value = data
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { detailLoading.value = false }
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(fetch)
</script>

<template>
  <div class="tag-list">
    <h2 class="page-title">标签管理</h2>

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
      <el-input
        v-model="qFilter"
        placeholder="标签名称搜索"
        style="width:200px"
        clearable
        @clear="handleSearch"
        @keyup.enter="handleSearch"
      />
      <el-button type="primary" @click="handleSearch">搜索</el-button>
      <el-button @click="handleReset">重置</el-button>
      <el-button type="success" @click="openCreate" style="margin-left:auto">+ 新增标签</el-button>
    </div>

    <!-- Table -->
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="颜色" width="70">
        <template #default="{ row }">
          <div
            class="color-dot"
            :style="{ backgroundColor: row.color }"
            :title="row.color"
          />
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="预设" width="70">
        <template #default="{ row }">
          <el-tag :type="row.isPreset ? 'warning' : 'info'" size="small">
            {{ row.isPreset ? '预设' : '自定义' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="taskCount" label="关联任务数" width="100" sortable />
      <el-table-column label="所属用户" min-width="140">
        <template #default="{ row }">
          <span v-if="row.userNickname === 'system' || !row.userNickname" style="color:#94a3b8">系统预设</span>
          <span v-else>{{ row.userNickname }}</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="viewDetail(row.uuid)">详情</el-button>
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="deleteTag(row)">删除</el-button>
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

    <!-- Create/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增标签' : '编辑标签'"
      width="440px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px" @submit.prevent="handleSubmit">
        <el-form-item label="名称" required>
          <el-input
            v-model="formName"
            placeholder="标签名称（1-50 字）"
            maxlength="50"
            :disabled="dialogMode === 'create'"
          />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="formColor" show-alpha />
          <span style="margin-left:0.5rem;font-size:13px;color:#64748b">{{ formColor }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- Detail Dialog -->
    <el-dialog
      v-model="detailVisible"
      title="标签详情"
      width="560px"
      :close-on-click-modal="false"
    >
      <div v-loading="detailLoading" v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="颜色">
            <div class="color-dot" :style="{ backgroundColor: detail.color, display: 'inline-block', verticalAlign: 'middle' }" />
            {{ detail.color }}
          </el-descriptions-item>
          <el-descriptions-item label="类型">
            <el-tag :type="detail.isPreset ? 'warning' : 'info'" size="small">
              {{ detail.isPreset ? '预设标签' : '自定义标签' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="关联任务">{{ detail.taskCount }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detail.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatTime(detail.updatedAt) }}</el-descriptions-item>
          <el-descriptions-item label="使用该标签的用户" :span="2">
            <template v-if="detail.users?.length">
              <el-tag
                v-for="u in detail.users"
                :key="u.uuid"
                size="small"
                style="margin-right:4px;margin-bottom:4px"
              >
                {{ u.nickname }}
              </el-tag>
            </template>
            <span v-else style="color:#94a3b8">暂无</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
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
.color-dot {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: 1px solid rgba(0,0,0,0.12);
  flex-shrink: 0;
}
</style>
