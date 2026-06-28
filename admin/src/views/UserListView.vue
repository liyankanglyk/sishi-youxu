<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminApi, type AdminUser } from '@/api/admin'

defineOptions({ name: 'UserListView' })

const router = useRouter()
const users = ref<AdminUser[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const statusFilter = ref('')
const loading = ref(false)

async function fetchUsers() {
  loading.value = true
  try {
    const { data } = await adminApi.listUsers({
      page: page.value,
      pageSize: pageSize.value,
      keyword: keyword.value || undefined,
      status: statusFilter.value || undefined,
    })
    users.value = data?.items ?? []
    total.value = data?.meta?.total ?? 0
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { loading.value = false }
}

function handleSearch() {
  page.value = 1
  fetchUsers()
}

function handlePageChange(p: number) {
  page.value = p
  fetchUsers()
}

function viewUser(uuid: string) {
  router.push(`/admin/users/${uuid}`)
}

async function handleDisable(uuid: string) {
  try { await adminApi.disableUser(uuid); ElMessage.success('已禁用'); fetchUsers() } catch (err: any) { ElMessage.error(err?.message || '操作失败') }
}
async function handleEnable(uuid: string) {
  try { await adminApi.enableUser(uuid); ElMessage.success('已启用'); fetchUsers() } catch (err: any) { ElMessage.error(err?.message || '操作失败') }
}

const statusTagType = (s: string) => s === 'active' ? 'success' : s === 'disabled' ? 'warning' : 'danger'

onMounted(fetchUsers)
</script>

<template>
  <div class="user-list">
    <h2 class="page-title">用户管理</h2>

    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索昵称/邮箱" style="width:240px" clearable @clear="handleSearch" @keyup.enter="handleSearch" />
      <el-select v-model="statusFilter" placeholder="状态筛选" clearable style="width:140px" @change="handleSearch">
        <el-option label="活跃" value="active" />
        <el-option label="禁用" value="disabled" />
      </el-select>
      <el-button type="primary" @click="handleSearch">搜索</el-button>
    </div>

    <el-table :data="users" v-loading="loading" stripe style="margin-top:1rem">
      <el-table-column prop="uuid" label="UUID" min-width="200" show-overflow-tooltip />
      <el-table-column prop="nickname" label="昵称" min-width="120" />
      <el-table-column prop="role" label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'super_admin' ? 'danger' : row.role === 'admin' ? 'warning' : 'info'" size="small">
            {{ row.role }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" width="170">
        <template #default="{ row }">{{ new Date(row.createdAt).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="viewUser(row.uuid)">查看</el-button>
          <el-button v-if="row.status === 'active'" type="warning" link size="small" @click="handleDisable(row.uuid)">禁用</el-button>
          <el-button v-else-if="row.status === 'disabled'" type="success" link size="small" @click="handleEnable(row.uuid)">启用</el-button>
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
      @current-change="handlePageChange"
    />
  </div>
</template>

<style scoped>
.page-title { margin: 0 0 1rem; font-size: 1.25rem; color: #1e293b; }
.toolbar { display: flex; gap: 0.75rem; align-items: center; }
</style>
