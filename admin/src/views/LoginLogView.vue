<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi, type LoginLogEntry } from '@/api/admin'

const items = ref<LoginLogEntry[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// Filters
const statusFilter = ref('')
const providerFilter = ref('')
const userUuidFilter = ref('')
const userSearchOptions = ref<Array<{ label: string; value: string }>>([])
const userSearchLoading = ref(false)

async function searchUsers(query: string) {
  if (!query) { userSearchOptions.value = []; return }
  userSearchLoading.value = true
  try {
    const { data } = await adminApi.searchUsers(query)
    userSearchOptions.value = (data?.items ?? []).map((u: any) => ({ label: `${u.nickname} (${u.uuid.slice(0, 8)}…)`, value: u.uuid }))
  } catch { userSearchOptions.value = [] }
  finally { userSearchLoading.value = false }
}

const statusOptions = [
  { label: '全部', value: '' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
]

const providerOptions = [
  { label: '全部', value: '' },
  { label: '密码登录', value: 'password' },
  { label: '短信登录', value: 'phone_sms' },
  { label: '邮箱登录', value: 'email_code' },
  { label: '微信登录', value: 'wechat' },
]

const providerLabels: Record<string, string> = {
  password: '密码登录',
  phone_sms: '短信登录',
  email_code: '邮箱登录',
  wechat: '微信登录',
}

async function fetch() {
  loading.value = true
  try {
    const { data } = await adminApi.listLoginLogs({
      page: page.value,
      pageSize: pageSize.value,
      status: statusFilter.value || undefined,
      provider: providerFilter.value || undefined,
      userUuid: userUuidFilter.value || undefined,
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
  statusFilter.value = ''
  providerFilter.value = ''
  userUuidFilter.value = ''
  page.value = 1
  fetch()
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(fetch)
</script>

<template>
  <div class="login-logs">
    <h2 class="page-title">登录日志</h2>

    <div class="toolbar">
      <el-select v-model="statusFilter" placeholder="登录状态" clearable style="width:130px" @change="handleSearch">
        <el-option
          v-for="o in statusOptions"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>
      <el-select v-model="providerFilter" placeholder="登录方式" clearable style="width:130px" @change="handleSearch">
        <el-option
          v-for="o in providerOptions"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>
      <el-select
        v-model="userUuidFilter"
        placeholder="用户"
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
      <el-button type="primary" @click="handleSearch">搜索</el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="用户" min-width="130">
        <template #default="{ row }">
          <span v-if="row.userUuid" class="uuid-text">{{ row.userUuid.slice(0, 8) }}…</span>
          <span v-else class="muted-text">-</span>
        </template>
      </el-table-column>
      <el-table-column label="登录方式" width="100">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ providerLabels[row.provider] || row.provider }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="ipAddress" label="IP地址" width="140" />
      <el-table-column prop="userAgent" label="User-Agent" min-width="220" show-overflow-tooltip />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.loginStatus === 'success' ? 'success' : 'danger'" size="small">
            {{ row.loginStatus === 'success' ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="failReason" label="失败原因" min-width="120" show-overflow-tooltip />
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
.uuid-text { color: #94a3b8; font-family: monospace; font-size: 12px; }
.muted-text { color: #cbd5e1; }
</style>
