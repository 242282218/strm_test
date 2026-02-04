<template>
  <el-card class="emby-config-card">
    <template #header>
      <div class="card-header">
        <span class="title">
          <el-icon><Monitor /></el-icon>
          Emby 集成
        </span>
        <el-tag :type="statusType" size="small">{{ statusText }}</el-tag>
      </div>
    </template>

    <el-form :model="form" label-width="140px" :disabled="loading">
      <el-form-item label="启用 Emby 集成">
        <el-switch v-model="form.enabled" />
      </el-form-item>

      <el-form-item label="服务器地址" required>
        <el-input v-model="form.url" placeholder="http://localhost:8096" :disabled="!form.enabled">
          <template #append>
            <el-button :loading="testing" @click="testConnection">测试连接</el-button>
          </template>
        </el-input>
      </el-form-item>

      <el-form-item label="API Key" required>
        <el-input
          v-model="form.api_key"
          type="password"
          show-password
          placeholder="Emby API Key"
          :disabled="!form.enabled"
        />
        <div class="form-tip">在 Emby 设置 → 高级 → API 密钥中获取</div>
      </el-form-item>

      <el-form-item label="请求超时(秒)">
        <el-input-number v-model="form.timeout" :min="1" :max="300" :disabled="!form.enabled" />
      </el-form-item>

      <el-divider>自动刷新设置</el-divider>

      <el-form-item label="STRM 生成后刷新">
        <el-switch v-model="form.on_strm_generate" :disabled="!form.enabled" />
      </el-form-item>

      <el-form-item label="重命名后刷新">
        <el-switch v-model="form.on_rename" :disabled="!form.enabled" />
      </el-form-item>

      <el-form-item label="定时刷新">
        <el-input v-model="form.cron" placeholder="0 */6 * * * (每6小时)" :disabled="!form.enabled" />
        <div class="form-tip">Cron 表达式，留空则不启用定时刷新</div>
      </el-form-item>

      <el-form-item label="刷新媒体库">
        <el-select
          v-model="form.library_ids"
          multiple
          placeholder="全部媒体库"
          :disabled="!form.enabled"
          style="width: 100%"
        >
          <el-option v-for="lib in libraries" :key="lib.id" :label="lib.name" :value="lib.id" />
        </el-select>
        <div class="form-tip">留空则刷新全部媒体库</div>
      </el-form-item>

      <el-form-item label="刷新完成通知">
        <el-switch v-model="form.notify_on_complete" :disabled="!form.enabled" />
      </el-form-item>
    </el-form>

    <div class="card-actions">
      <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
      <el-button :disabled="!form.enabled" @click="manualRefresh">立即刷新</el-button>
    </div>

    <div v-if="serverInfo" class="server-info">
      <el-descriptions title="服务器信息" :column="3" size="small" border>
        <el-descriptions-item label="名称">{{ serverInfo.server_name }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ serverInfo.version }}</el-descriptions-item>
        <el-descriptions-item label="系统">{{ serverInfo.operating_system }}</el-descriptions-item>
      </el-descriptions>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Monitor } from '@element-plus/icons-vue'
import { embyApi, type EmbyLibrary, type EmbyServerInfo } from '@/api/emby'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const connected = ref(false)
const serverInfo = ref<EmbyServerInfo | null>(null)
const libraries = ref<EmbyLibrary[]>([])

const form = reactive({
  enabled: false,
  url: '',
  api_key: '',
  timeout: 30,
  on_strm_generate: true,
  on_rename: true,
  cron: '',
  library_ids: [] as string[],
  notify_on_complete: true
})

const statusType = computed(() => {
  if (!form.enabled) return 'info'
  return connected.value ? 'success' : 'danger'
})

const statusText = computed(() => {
  if (!form.enabled) return '未启用'
  return connected.value ? '已连接' : '未连接'
})

const loadLibraries = async () => {
  try {
    const result = await embyApi.getLibraries()
    libraries.value = result.libraries || []
  } catch (e) {
    console.error('加载媒体库失败', e)
  }
}

const testConnection = async () => {
  testing.value = true
  try {
    const result = await embyApi.testConnection({ url: form.url, api_key: form.api_key, timeout: form.timeout })
    if (result.success) {
      ElMessage.success('连接成功')
      connected.value = true
      serverInfo.value = result.server_info
      await loadLibraries()
    } else {
      ElMessage.error(result.message || '连接失败')
      connected.value = false
      serverInfo.value = null
    }
  } catch (e) {
    ElMessage.error('连接测试失败')
  } finally {
    testing.value = false
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    await embyApi.updateConfig({
      ...form,
      cron: form.cron || ''
    })
    ElMessage.success('配置已保存')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const manualRefresh = async () => {
  try {
    await embyApi.refresh()
    ElMessage.success('刷新任务已触发')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '刷新失败')
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const status = await embyApi.getStatus({ probe: true, probe_timeout: 3 })
    form.enabled = status.configuration.enabled
    form.url = status.configuration.url || ''
    // 后端返回的是脱敏的 api_key；这里不回填，避免误覆盖
    form.api_key = ''
    form.timeout = status.configuration.timeout || 30
    form.on_strm_generate = status.configuration.on_strm_generate
    form.on_rename = status.configuration.on_rename
    form.cron = status.configuration.cron || ''
    form.library_ids = status.configuration.library_ids || []
    form.notify_on_complete = status.configuration.notify_on_complete

    connected.value = status.connected
    serverInfo.value = status.server_info

    if (status.enabled) {
      await loadLibraries()
    }
  } catch (e) {
    console.error('加载Emby配置失败', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.emby-config-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.card-actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.server-info {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}
</style>
