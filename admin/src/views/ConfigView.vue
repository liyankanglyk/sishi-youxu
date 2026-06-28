<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminApi } from '@/api/admin'
import { useAdminAuthStore } from '@/stores/adminAuth'

const router = useRouter()
const auth = useAdminAuthStore()

interface ConfigForm {
  siteName: string
  siteIcp: string
  registrationEnabled: boolean
  phoneLoginEnabled: boolean
  emailLoginEnabled: boolean
  wechatLoginEnabled: boolean
  maintenanceMode: boolean
  maintenanceMessage: string
}

const form = ref<ConfigForm>({
  siteName: '四时有序',
  siteIcp: '',
  registrationEnabled: true,
  phoneLoginEnabled: true,
  emailLoginEnabled: true,
  wechatLoginEnabled: true,
  maintenanceMode: false,
  maintenanceMessage: '系统升级中，请稍后再试',
})

const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await adminApi.getConfig()
    if (data) {
      form.value.siteName = (data['site.name'] as string) || form.value.siteName
      form.value.siteIcp = (data['site.icp'] as string) || ''
      form.value.registrationEnabled = data['registration.enabled'] !== 'false'
      form.value.phoneLoginEnabled = data['feature.phone_login'] !== 'false'
      form.value.emailLoginEnabled = data['feature.email_login'] !== 'false'
      form.value.wechatLoginEnabled = data['feature.wechat_login'] !== 'false'
      form.value.maintenanceMode = data['maintenance.enabled'] === 'true'
      form.value.maintenanceMessage = (data['maintenance.message'] as string) || form.value.maintenanceMessage
    }
  } catch (err: any) {
    ElMessage.error(err?.message || '加载失败')
  } finally { loading.value = false }
})

async function handleSave() {
  loading.value = true
  try {
    await adminApi.updateConfig({
      'site.name': form.value.siteName,
      'site.icp': form.value.siteIcp,
      'registration.enabled': String(form.value.registrationEnabled),
      'feature.phone_login': String(form.value.phoneLoginEnabled),
      'feature.email_login': String(form.value.emailLoginEnabled),
      'feature.wechat_login': String(form.value.wechatLoginEnabled),
      'maintenance.enabled': String(form.value.maintenanceMode),
      'maintenance.message': form.value.maintenanceMessage,
    })
    ElMessage.success('配置已保存')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    loading.value = false
  }
}

// ── 修改密码 ──
const pwOld = ref('')
const pwNew = ref('')
const pwConfirm = ref('')
const pwSaving = ref(false)

async function handleChangePassword() {
  if (!pwOld.value || !pwNew.value || !pwConfirm.value) {
    ElMessage.warning('请填写所有密码字段')
    return
  }
  if (pwNew.value.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (pwNew.value !== pwConfirm.value) {
    ElMessage.warning('两次新密码输入不一致')
    return
  }
  pwSaving.value = true
  try {
    await auth.changePassword(pwOld.value, pwNew.value)
    ElMessage.success('密码修改成功，请重新登录')
    router.push('/admin/login')
  } catch (e: any) {
    ElMessage.error(e.message || '修改失败')
  } finally { pwSaving.value = false }
}
</script>

<template>
  <div class="config" v-loading="loading">
    <h2 class="page-title">系统配置</h2>

    <el-card>
      <el-form :model="form" label-width="160px">
        <el-divider content-position="left">站点信息</el-divider>
        <el-form-item label="站点名称">
          <el-input v-model="form.siteName" />
        </el-form-item>
        <el-form-item label="备案号">
          <el-input v-model="form.siteIcp" placeholder="京ICP备xxxxxxxx号" />
        </el-form-item>

        <el-divider content-position="left">功能开关</el-divider>
        <el-form-item label="开放注册">
          <el-switch v-model="form.registrationEnabled" />
        </el-form-item>
        <el-form-item label="短信登录">
          <el-switch v-model="form.phoneLoginEnabled" />
        </el-form-item>
        <el-form-item label="邮箱登录">
          <el-switch v-model="form.emailLoginEnabled" />
        </el-form-item>
        <el-form-item label="微信登录">
          <el-switch v-model="form.wechatLoginEnabled" />
        </el-form-item>

        <el-divider content-position="left">维护模式</el-divider>
        <el-form-item label="维护模式">
          <el-switch v-model="form.maintenanceMode" />
        </el-form-item>
        <el-form-item label="维护公告">
          <el-input v-model="form.maintenanceMessage" type="textarea" :rows="2" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSave">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top:1rem">
      <template #header><span>修改管理员密码</span></template>
      <el-form label-width="120px" @submit.prevent="handleChangePassword">
        <el-form-item label="当前密码">
          <el-input v-model="pwOld" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwNew" type="password" show-password autocomplete="new-password" placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="pwConfirm" type="password" show-password autocomplete="new-password" placeholder="再次输入新密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="pwSaving" @click="handleChangePassword">修改密码</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.page-title { margin: 0 0 1rem; font-size: 1.25rem; color: #1e293b; }
</style>
