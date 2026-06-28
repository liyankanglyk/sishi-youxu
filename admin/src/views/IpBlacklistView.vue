<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, type IpBlacklistEntry } from '@/api/admin'

const items = ref<IpBlacklistEntry[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// Dialog
const dialogVisible = ref(false)
const dialogLoading = ref(false)
const formIp = ref('')
const formReason = ref('')
const formExpiresAt = ref('')

async function fetch() {
  loading.value = true
  try {
    const { data } = await adminApi.listIpBlacklist({ page: page.value, pageSize: pageSize.value })
    items.value = data?.items ?? []
    total.value = data?.meta?.total ?? 0
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { loading.value = false }
}

function openAdd() {
  formIp.value = ''
  formReason.value = ''
  formExpiresAt.value = ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formIp.value.trim()) {
    ElMessage.warning('请输入IP地址')
    return
  }
  // Simple IP validation
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/
  if (!ipRegex.test(formIp.value.trim())) {
    ElMessage.warning('请输入有效的IP地址')
    return
  }
  dialogLoading.value = true
  try {
    await adminApi.addIpBlacklist({
      ipAddress: formIp.value.trim(),
      reason: formReason.value.trim() || undefined,
      expiresAt: formExpiresAt.value || undefined,
    })
    ElMessage.success('添加成功')
    dialogVisible.value = false
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '添加失败')
  } finally { dialogLoading.value = false }
}

async function handleDelete(item: IpBlacklistEntry) {
  try {
    await ElMessageBox.confirm(`确认将 ${item.ipAddress} 移出黑名单？`, '确认', {
      type: 'warning',
      confirmButtonText: '移除',
      cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await adminApi.deleteIpBlacklist(item.uuid)
    ElMessage.success('已移除')
    fetch()
  } catch (err: any) {
    ElMessage.error(err?.message || '移除失败')
  }
}

function isExpired(expiresAt: string | null): boolean {
  if (!expiresAt) return false
  return new Date(expiresAt) < new Date()
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(fetch)
</script>

<template>
  <div class="ip-blacklist">
    <h2 class="page-title">IP黑名单</h2>

    <div class="toolbar">
      <el-button type="primary" @click="openAdd">+ 添加IP</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="ipAddress" label="IP地址" width="170" />
      <el-table-column prop="reason" label="拉黑原因" min-width="220" show-overflow-tooltip />
      <el-table-column prop="createdBy" label="操作人" min-width="180" show-overflow-tooltip />
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="过期时间" width="170">
        <template #default="{ row }">
          <template v-if="row.expiresAt">
            <el-tag :type="isExpired(row.expiresAt) ? 'danger' : 'info'" size="small">
              {{ isExpired(row.expiresAt) ? '已过期' : formatTime(row.expiresAt) }}
            </el-tag>
          </template>
          <el-tag v-else type="info" size="small">永久</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button type="danger" link size="small" @click="handleDelete(row)">移除</el-button>
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

    <!-- Add Dialog -->
    <el-dialog
      v-model="dialogVisible"
      title="添加IP黑名单"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px" @submit.prevent="handleSubmit">
        <el-form-item label="IP地址" required>
          <el-input v-model="formIp" placeholder="例: 192.168.1.100 或 10.0.0.0/24" />
        </el-form-item>
        <el-form-item label="拉黑原因">
          <el-input v-model="formReason" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
        <el-form-item label="过期时间">
          <el-date-picker
            v-model="formExpiresAt"
            type="datetime"
            placeholder="留空表示永久"
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
</style>
