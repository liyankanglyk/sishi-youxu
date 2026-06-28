<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, type UserDetail, type AdminTaskListItem, type AdminTagListItem } from '@/api/admin'

const route = useRoute()
const router = useRouter()

// ── 用户信息 ──
const user = ref<UserDetail | null>(null)
const loading = ref(false)

// ── 标签页 ──
const activeTab = ref('info')

// 任务
const tasks = ref<AdminTaskListItem[]>([])
const taskTotal = ref(0)
const taskPage = ref(1)
const taskPageSize = ref(10)
const taskLoading = ref(false)
const taskQuadrant = ref<number | null>(null)
const taskCompleted = ref<boolean | null>(null)

// 标签
const tags = ref<AdminTagListItem[]>([])
const tagTotal = ref(0)
const tagPage = ref(1)
const tagPageSize = ref(10)
const tagLoading = ref(false)

const quadrantOptions = [
  { label: '全部', value: null },
  { label: 'Q1', value: 1 },
  { label: 'Q2', value: 2 },
  { label: 'Q3', value: 3 },
  { label: 'Q4', value: 4 },
]
const statusOptions = [
  { label: '全部', value: null },
  { label: '已完成', value: true },
  { label: '未完成', value: false },
]

// ── 用户操作 ──

onMounted(async () => {
  const uuid = route.params.uuid as string
  loading.value = true
  try {
    const { data } = await adminApi.getUser(uuid)
    user.value = data
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { loading.value = false }
})

async function handleDisable() {
  if (!user.value) return
  try {
    await adminApi.disableUser(user.value.uuid)
    ElMessage.success('已禁用')
  } catch (err: any) {
    ElMessage.error(err?.message || '操作失败')
  }
}
async function handleEnable() {
  if (!user.value) return
  try {
    await adminApi.enableUser(user.value.uuid)
    ElMessage.success('已启用')
  } catch (err: any) {
    ElMessage.error(err?.message || '操作失败')
  }
}

async function handleForceLogout() {
  if (!user.value) return
  try {
    await ElMessageBox.confirm(`确认强制下线用户「${user.value.nickname}」？`, '强制登出', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await adminApi.forceLogout(user.value.uuid)
    ElMessage.success('已强制登出')
  } catch (err: any) {
    ElMessage.error(err?.message || '操作失败')
  }
}

// ── 重置密码 ──
const resetPwDialogVisible = ref(false)
const resetPwNew = ref('')
const resetPwConfirm = ref('')
const resetPwSaving = ref(false)

const hasPasswordProvider = () =>
  user.value?.authIdentities?.some((i: any) => i.provider === 'password')

async function handleResetPassword() {
  if (!resetPwNew.value || !resetPwConfirm.value) {
    ElMessage.warning('请填写所有字段')
    return
  }
  if (resetPwNew.value.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (resetPwNew.value !== resetPwConfirm.value) {
    ElMessage.warning('两次密码输入不一致')
    return
  }
  resetPwSaving.value = true
  try {
    await adminApi.resetUserPassword(user.value!.uuid, resetPwNew.value)
    ElMessage.success('密码已重置')
    resetPwDialogVisible.value = false
    resetPwNew.value = ''
    resetPwConfirm.value = ''
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  } finally { resetPwSaving.value = false }
}

// ── 任务 ──

async function fetchTasks() {
  if (!user.value) return
  taskLoading.value = true
  try {
    const { data } = await adminApi.listUserTasks(user.value.uuid, {
      page: taskPage.value,
      pageSize: taskPageSize.value,
      quadrant: taskQuadrant.value ?? undefined,
      completed: taskCompleted.value ?? undefined,
    })
    tasks.value = data?.items ?? []
    taskTotal.value = data?.meta?.total ?? 0
  } catch (err: any) {
    ElMessage.error(err?.message || '加载任务失败')
  } finally { taskLoading.value = false }
}

function handleTaskSearch() {
  taskPage.value = 1
  fetchTasks()
}

// ── 标签 ──

async function fetchTags() {
  if (!user.value) return
  tagLoading.value = true
  try {
    const { data } = await adminApi.listUserTags(user.value.uuid, {
      page: tagPage.value,
      pageSize: tagPageSize.value,
    })
    tags.value = data?.items ?? []
    tagTotal.value = data?.meta?.total ?? 0
  } catch (err: any) {
    ElMessage.error(err?.message || '加载标签失败')
  } finally { tagLoading.value = false }
}

// ── 标签页切换处理（懒加载） ──

function onTabChange(name: string | number) {
  if (name === 'tasks' && !tasks.value.length) fetchTasks()
  else if (name === 'tags' && !tags.value.length) fetchTags()
}

// ── 辅助函数 ──

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
</script>

<template>
  <div class="user-detail" v-loading="loading">
    <el-page-header @back="router.back" title="返回">
      <template #content><h2 style="margin:0">用户详情</h2></template>
    </el-page-header>

    <template v-if="user">
      <el-tabs v-model="activeTab" style="margin-top:1rem" @tab-change="onTabChange">
        <!-- ================================================================ -->
        <!-- 标签页 1：基本信息 -->
        <!-- ================================================================ -->
        <el-tab-pane label="基本信息" name="info">
          <el-card header="基本信息">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="UUID">{{ user.uuid }}</el-descriptions-item>
              <el-descriptions-item label="昵称">{{ user.nickname }}</el-descriptions-item>
              <el-descriptions-item label="角色">
                <el-tag :type="user.role === 'super_admin' ? 'danger' : user.role === 'admin' ? 'warning' : 'info'" size="small">{{ user.role }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="user.status === 'active' ? 'success' : 'danger'" size="small">{{ user.status }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="注册时间">{{ formatTime(user.createdAt) }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ formatTime(user.updatedAt) }}</el-descriptions-item>
            </el-descriptions>
          </el-card>

          <el-card header="任务统计" style="margin-top:1rem">
            <el-row :gutter="16">
              <el-col :span="8"><el-statistic title="总任务" :value="user.taskCount" /></el-col>
              <el-col :span="8"><el-statistic title="已完成" :value="user.completedTaskCount" /></el-col>
              <el-col :span="8"><el-statistic title="完成率" :value="user.taskCount ? Math.round(user.completedTaskCount / user.taskCount * 100) + '%' : '0%'" /></el-col>
            </el-row>
          </el-card>

          <el-card header="认证方式" style="margin-top:1rem">
            <el-table :data="user.authIdentities" v-if="user.authIdentities?.length">
              <el-table-column prop="provider" label="Provider" />
              <el-table-column prop="identifier" label="标识" />
            </el-table>
            <el-empty v-else description="暂无数据" />
          </el-card>

          <div style="margin-top:1.5rem;display:flex;gap:0.75rem;">
            <el-button v-if="user.status === 'active'" type="warning" @click="handleDisable">禁用用户</el-button>
            <el-button v-else-if="user.status === 'disabled'" type="success" @click="handleEnable">启用用户</el-button>
            <el-button type="danger" plain @click="handleForceLogout">强制登出</el-button>
            <el-button v-if="hasPasswordProvider()" type="primary" plain @click="resetPwDialogVisible = true">重置密码</el-button>
          </div>
        </el-tab-pane>

        <!-- ================================================================ -->
        <!-- 标签页 2：任务 -->
        <!-- ================================================================ -->
        <el-tab-pane label="任务" name="tasks">
          <div class="tab-toolbar">
            <el-select v-model="taskQuadrant" placeholder="象限" clearable style="width:140px" @change="handleTaskSearch">
              <el-option v-for="o in quadrantOptions" :key="String(o.value)" :label="o.label" :value="o.value" />
            </el-select>
            <el-select v-model="taskCompleted" placeholder="完成状态" clearable style="width:130px" @change="handleTaskSearch">
              <el-option v-for="o in statusOptions" :key="String(o.value)" :label="o.label" :value="o.value" />
            </el-select>
            <el-button type="primary" size="small" @click="handleTaskSearch">筛选</el-button>
          </div>

          <el-table :data="tasks" v-loading="taskLoading" stripe size="small">
            <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
            <el-table-column label="象限" width="70">
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
            <el-table-column label="标签" min-width="120">
              <template #default="{ row }">
                <el-tag
                  v-for="tag in row.tags.slice(0, 3)"
                  :key="tag.uuid"
                  :color="tag.color"
                  :style="{ borderColor: tag.color, color: '#fff' }"
                  size="small"
                  style="margin-right:2px"
                >
                  {{ tag.name }}
                </el-tag>
                <span v-if="!row.tags?.length" style="color:#94a3b8">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="dueDate" label="截止" width="100" />
            <el-table-column label="创建时间" width="150">
              <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-if="taskTotal > taskPageSize"
            style="margin-top:0.75rem;justify-content:flex-end"
            v-model:current-page="taskPage"
            :page-size="taskPageSize"
            :total="taskTotal"
            layout="total, prev, pager, next"
            small
            @current-change="fetchTasks"
          />
        </el-tab-pane>

        <!-- ================================================================ -->
        <!-- 标签页 3：标签 -->
        <!-- ================================================================ -->
        <el-tab-pane label="标签" name="tags">
          <el-table :data="tags" v-loading="tagLoading" stripe size="small">
            <el-table-column label="颜色" width="60">
              <template #default="{ row }">
                <div class="color-dot" :style="{ backgroundColor: row.color }" />
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column label="类型" width="70">
              <template #default="{ row }">
                <el-tag :type="row.isPreset ? 'warning' : 'info'" size="small">
                  {{ row.isPreset ? '预设' : '自定义' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="taskCount" label="任务数" width="80" />
            <el-table-column label="创建时间" width="150">
              <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-if="tagTotal > tagPageSize"
            style="margin-top:0.75rem;justify-content:flex-end"
            v-model:current-page="tagPage"
            :page-size="tagPageSize"
            :total="tagTotal"
            layout="total, prev, pager, next"
            small
            @current-change="fetchTags"
          />
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- 重置密码弹窗 -->
    <el-dialog v-model="resetPwDialogVisible" title="重置用户密码" width="420px" :close-on-click-modal="false">
      <el-form label-width="100px" @submit.prevent="handleResetPassword">
        <el-form-item label="新密码">
          <el-input v-model="resetPwNew" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="resetPwConfirm" type="password" show-password placeholder="再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetPwSaving" @click="handleResetPassword">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-detail { max-width: 960px; }
.tab-toolbar {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.75rem;
}
.color-dot {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  border: 1px solid rgba(0,0,0,0.12);
  flex-shrink: 0;
}
</style>
