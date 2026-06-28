<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, type FeedbackEntry } from '@/api/admin'

const items = ref<FeedbackEntry[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const loading = ref(false)

async function fetch() {
  loading.value = true
  try {
    const { data } = await adminApi.listFeedback({
      page: page.value,
      pageSize: pageSize.value,
      status: statusFilter.value || undefined,
    })
    items.value = data?.items ?? []
    total.value = data?.meta?.total ?? 0
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { loading.value = false }
}

async function updateStatus(uuid: string, status: string) {
  try {
    await adminApi.updateFeedback(uuid, { status })
    ElMessage.success('状态已更新')
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '操作失败')
  }
}

async function handleDelete(item: FeedbackEntry) {
  try {
    await ElMessageBox.confirm('确认删除该反馈？', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await adminApi.deleteFeedback(item.uuid)
    ElMessage.success('已删除')
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '删除失败')
  }
}

const statusTagType = (s: string) => s === 'pending' ? 'warning' : s === 'processing' ? 'info' : 'success'
const statusLabel = (s: string) => s === 'pending' ? '待处理' : s === 'processing' ? '处理中' : '已解决'

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(fetch)
</script>

<template>
  <div class="feedback">
    <h2 class="page-title">反馈管理</h2>

    <div class="toolbar">
      <el-radio-group v-model="statusFilter" @change="fetch">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="pending">待处理</el-radio-button>
        <el-radio-button label="processing">处理中</el-radio-button>
        <el-radio-button label="resolved">已解决</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="items" v-loading="loading" stripe style="margin-top:1rem">
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip />
      <el-table-column prop="contact" label="联系方式" min-width="140" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" type="primary" size="small" @click="updateStatus(row.uuid, 'processing')">开始处理</el-button>
          <el-button v-if="row.status === 'processing'" type="success" size="small" @click="updateStatus(row.uuid, 'resolved')">标记解决</el-button>
          <el-button type="danger" link size="small" style="margin-left:0.5rem" @click="handleDelete(row)">删除</el-button>
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
  </div>
</template>

<style scoped>
.page-title { margin: 0 0 1rem; font-size: 1.25rem; color: #1e293b; }
.toolbar { display: flex; gap: 0.75rem; }
</style>
