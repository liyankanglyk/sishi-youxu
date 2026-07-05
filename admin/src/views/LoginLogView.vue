<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi, type LoginLogEntry } from '@/api/admin'

const items = ref<LoginLogEntry[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// 详情抽屉
const detailVisible = ref(false)
const detailEntry = ref<LoginLogEntry | null>(null)

// 筛选条件
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

function showDetail(row: LoginLogEntry) {
  detailEntry.value = row
  detailVisible.value = true
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

    <el-table :data="items" v-loading="loading" stripe @row-click="showDetail" style="cursor:pointer">
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="用户" min-width="130">
        <template #default="{ row }">
          <span v-if="row.userNickname" :title="row.userUuid">{{ row.userNickname }}</span>
          <span v-else-if="row.userUuid" class="uuid-text" :title="row.userUuid">{{ row.userUuid.slice(0, 8) }}…</span>
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

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="登录日志详情" size="480px">
      <template v-if="detailEntry">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="登录时间">{{ formatTime(detailEntry.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="用户">
            <span v-if="detailEntry.userNickname" :title="detailEntry.userUuid ?? undefined">{{ detailEntry.userNickname }}</span>
            <span v-else-if="detailEntry.userUuid" class="uuid-text">{{ detailEntry.userUuid }}</span>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="登录方式">{{ providerLabels[detailEntry.provider] || detailEntry.provider }}（{{ detailEntry.provider }}）</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detailEntry.loginStatus === 'success' ? 'success' : 'danger'" size="small">
              {{ detailEntry.loginStatus === 'success' ? '成功' : '失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="detailEntry.loginStatus === 'failed'" label="失败原因">{{ detailEntry.failReason || '-' }}</el-descriptions-item>
          <el-descriptions-item label="IP 地址">{{ detailEntry.ipAddress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="User-Agent" class-name="ua-cell">
            <div class="ua-text">{{ detailEntry.userAgent || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="请求方法">{{ detailEntry.requestMethod || '-' }}</el-descriptions-item>
          <el-descriptions-item label="请求路径" class-name="ua-cell">
            <div class="path-text">{{ detailEntry.requestPath || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="请求体（已脱敏）" class-name="body-cell">
            <pre class="body-pre">{{ detailEntry.requestBody || '（空）' }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="日志 UUID" class-name="uuid-cell">
            <span class="uuid-text-full">{{ detailEntry.uuid }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
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
.uuid-text { color: #64748b; font-family: monospace; font-size: 12px; }
.uuid-text-full { color: #64748b; font-family: monospace; font-size: 12px; word-break: break-all; }
.muted-text { color: #94a3b8; }
.ua-text { font-family: monospace; font-size: 12px; word-break: break-all; line-height: 1.6; }
.path-text { font-family: monospace; font-size: 12px; word-break: break-all; line-height: 1.6; }
.body-pre {
  margin: 0;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-family: monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 240px;
  overflow-y: auto;
  max-width: 380px;
}
:deep(.ua-cell .el-descriptions__content) { max-width: 380px; }
:deep(.uuid-cell .el-descriptions__content) { max-width: 380px; }
</style>
