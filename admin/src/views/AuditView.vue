<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi, type AuditEntry } from '@/api/admin'

const items = ref<AuditEntry[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// 详情抽屉
const detailVisible = ref(false)
const detailEntry = ref<AuditEntry | null>(null)
const detailLoading = ref(false)

// 筛选条件
const userUuid = ref('')
const userSearchOptions = ref<Array<{ label: string; value: string }>>([])
const userSearchLoading = ref(false)
const action = ref('')
const resourceType = ref('')
const dateRange = ref<string[]>([])

async function searchUsers(query: string) {
  if (!query) { userSearchOptions.value = []; return }
  userSearchLoading.value = true
  try {
    const { data } = await adminApi.searchUsers(query)
    userSearchOptions.value = (data?.items ?? []).map((u: any) => ({ label: `${u.nickname} (${u.uuid.slice(0, 8)}…)`, value: u.uuid }))
  } catch { userSearchOptions.value = [] }
  finally { userSearchLoading.value = false }
}

async function fetch() {
  loading.value = true
  try {
    const { data } = await adminApi.listAudit({
      page: page.value,
      pageSize: pageSize.value,
      userUuid: userUuid.value || undefined,
      action: action.value || undefined,
      resourceType: resourceType.value || undefined,
      startTime: dateRange.value?.[0] || undefined,
      endTime: dateRange.value?.[1] || undefined,
    })
    items.value = data?.items ?? []
    total.value = data?.meta?.total ?? 0
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { loading.value = false }
}

async function showDetail(row: AuditEntry) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    const { data } = await adminApi.getAuditEntry(row.uuid)
    detailEntry.value = data
  } catch (err: any) {
    ElMessage.error(err?.message || '加载详情失败')
    detailEntry.value = row
  } finally { detailLoading.value = false }
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN')
}

function formatDetail(detail: Record<string, unknown> | null | undefined) {
  if (!detail || Object.keys(detail).length === 0) return '无'
  return JSON.stringify(detail, null, 2)
}

const resourceTypeLabels: Record<string, string> = {
  user: '用户',
  task: '任务',
  tag: '标签',
  feedback: '反馈',
  system_config: '系统配置',
  announcement: '公告',
}

function handleSearch() {
  page.value = 1
  fetch()
}

function handleReset() {
  userUuid.value = ''
  userSearchOptions.value = []
  action.value = ''
  resourceType.value = ''
  dateRange.value = []
  page.value = 1
  fetch()
}

onMounted(fetch)
</script>

<template>
  <div class="audit">
    <h2 class="page-title">审计日志</h2>

    <div class="toolbar">
      <el-select
        v-model="userUuid"
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
      <el-input v-model="action" placeholder="操作类型" style="width:160px" clearable @clear="handleSearch" />
      <el-select v-model="resourceType" placeholder="资源类型" clearable style="width:140px" @change="handleSearch">
        <el-option label="用户" value="user" />
        <el-option label="任务" value="task" />
        <el-option label="标签" value="tag" />
        <el-option label="反馈" value="feedback" />
        <el-option label="系统配置" value="system_config" />
        <el-option label="公告" value="announcement" />
      </el-select>
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        style="width:260px"
        @change="handleSearch"
      />
      <el-button type="primary" @click="handleSearch">搜索</el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe @row-click="showDetail" style="cursor:pointer">
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="130">
        <template #default="{ row }">{{ row.actionLabel || row.action }}</template>
      </el-table-column>
      <el-table-column label="资源类型" width="90">
        <template #default="{ row }">{{ resourceTypeLabels[row.resourceType] || row.resourceType }}</template>
      </el-table-column>
      <el-table-column prop="resourceUuid" label="资源 UUID" min-width="180" show-overflow-tooltip />
      <el-table-column label="操作人" min-width="120">
        <template #default="{ row }">
          <span v-if="row.userNickname" :title="row.userUuid">{{ row.userNickname }}</span>
          <span v-else-if="row.userUuid" class="uuid-text">{{ row.userUuid.slice(0, 8) }}…</span>
          <span v-else class="muted-text">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="ipAddress" label="IP" width="140">
        <template #default="{ row }">
          <span v-if="row.ipAddress">{{ row.ipAddress }}</span>
          <span v-else class="muted-text">-</span>
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

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="审计日志详情" size="480px">
      <template v-if="detailEntry">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="操作时间">{{ formatTime(detailEntry.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="操作类型">{{ detailEntry.actionLabel || detailEntry.action }}</el-descriptions-item>
          <el-descriptions-item label="原始 Action">{{ detailEntry.action }}</el-descriptions-item>
          <el-descriptions-item label="资源类型">{{ resourceTypeLabels[detailEntry.resourceType] || detailEntry.resourceType }}</el-descriptions-item>
          <el-descriptions-item label="资源 UUID">{{ detailEntry.resourceUuid || '-' }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ detailEntry.userNickname || detailEntry.userUuid || '-' }}</el-descriptions-item>
          <el-descriptions-item label="IP 地址">{{ detailEntry.ipAddress || '-' }}</el-descriptions-item>
          <el-descriptions-item label="User-Agent">{{ (detailEntry as any).userAgent || '-' }}</el-descriptions-item>
          <el-descriptions-item label="操作详情">
            <pre class="detail-json">{{ formatDetail(detailEntry.detail) }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <div v-else v-loading="detailLoading" style="min-height:200px" />
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
.uuid-text { color: #94a3b8; font-family: monospace; font-size: 12px; }
.muted-text { color: #cbd5e1; }
.detail-json {
  margin: 0;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
