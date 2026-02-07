<template>
  <div class="config-page">
    <div class="page-header">
      <h2>系统配置</h2>
    </div>

    <div class="config-content">
      <EmbyConfigCard />

      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>AI 模型配置</span>
          </div>
        </template>

        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="支持配置 Kimi 2.5、DeepSeek、GLM。密钥字段默认脱敏展示，留空表示保持原值。"
          class="hint"
        />

        <el-form label-width="130px" class="config-form" v-loading="loading">
          <section v-for="(provider, idx) in providerOrder" :key="provider" class="provider-section">
            <div class="provider-header">
              <h3>{{ providerTitle(provider) }}</h3>
              <el-tag :type="form[provider].configured ? 'success' : 'info'" size="small" round>
                {{ form[provider].configured ? '已配置' : '未配置' }}
              </el-tag>
            </div>

            <el-form-item label="当前密钥状态">
              <el-input :model-value="form[provider].api_key_masked || '未配置'" readonly />
            </el-form-item>

            <el-form-item label="新 API 密钥">
              <el-input
                v-model="form[provider].api_key"
                type="password"
                show-password
                clearable
                placeholder="留空保持当前密钥不变"
              />
            </el-form-item>

            <el-form-item label="Base URL">
              <el-input v-model="form[provider].base_url" clearable />
            </el-form-item>

            <el-form-item label="模型 ID">
              <el-input v-model="form[provider].model" clearable />
            </el-form-item>

            <el-form-item label="超时时间(秒)">
              <el-input-number v-model="form[provider].timeout" :min="1" :max="120" />
            </el-form-item>

            <el-divider v-if="idx < providerOrder.length - 1" />
          </section>

          <div class="form-actions">
            <el-button type="primary" :loading="saving" @click="saveConfig">保存</el-button>
            <el-button :disabled="saving" @click="cancelChanges">取消</el-button>
            <el-button :disabled="saving" @click="resetToDefaults">重置</el-button>
          </div>
        </el-form>
      </el-card>

      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>全量系统配置</span>
          </div>
        </template>

        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="此区域可直接编辑全部配置变量。敏感字段显示为脱敏值，保留星号表示不变，填写新值可覆盖。"
          class="hint"
        />

        <div class="raw-editor" v-loading="fullConfigLoading">
          <el-input
            v-model="fullConfigText"
            type="textarea"
            :rows="22"
            resize="vertical"
            placeholder="请输入完整 JSON 配置"
          />
        </div>

        <div class="form-actions">
          <el-button type="primary" :loading="fullConfigSaving" @click="saveFullConfig">保存全量配置</el-button>
          <el-button :disabled="fullConfigSaving || fullConfigLoading" @click="reloadFullConfig">重新加载</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import EmbyConfigCard from '@/components/EmbyConfigCard.vue'
import {
  getAIModelsConfig,
  getSystemConfig,
  updateSystemConfig,
  updateAIModelsConfig,
  type AIModelsConfigResponse,
  type AIProvider,
  type SystemConfigResponse
} from '@/api/systemConfig'

interface AIFormState {
  api_key: string
  api_key_masked: string
  configured: boolean
  base_url: string
  model: string
  timeout: number
}

type AIFormMap = Record<AIProvider, AIFormState>

const providerOrder: AIProvider[] = ['kimi', 'deepseek', 'glm']

const defaults: Record<AIProvider, { base_url: string; model: string; timeout: number }> = {
  kimi: {
    base_url: 'https://integrate.api.nvidia.com/v1',
    model: 'moonshotai/kimi-k2.5',
    timeout: 15
  },
  deepseek: {
    base_url: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
    timeout: 20
  },
  glm: {
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    model: 'glm-4.7-flash',
    timeout: 8
  }
}

const loading = ref(false)
const saving = ref(false)
const snapshot = ref<AIModelsConfigResponse | null>(null)
const fullConfigLoading = ref(false)
const fullConfigSaving = ref(false)
const fullConfigText = ref('')

const form = reactive<AIFormMap>({
  kimi: { api_key: '', api_key_masked: '', configured: false, ...defaults.kimi },
  deepseek: { api_key: '', api_key_masked: '', configured: false, ...defaults.deepseek },
  glm: { api_key: '', api_key_masked: '', configured: false, ...defaults.glm }
})

const providerTitle = (provider: AIProvider): string => {
  if (provider === 'kimi') return 'Kimi 2.5'
  if (provider === 'deepseek') return 'DeepSeek'
  return 'GLM 4.7 Flash'
}

const applyResponseToForm = (data: AIModelsConfigResponse): void => {
  for (const provider of providerOrder) {
    form[provider].configured = !!data[provider].configured
    form[provider].api_key_masked = data[provider].api_key_masked || ''
    form[provider].base_url = data[provider].base_url
    form[provider].model = data[provider].model
    form[provider].timeout = data[provider].timeout
    form[provider].api_key = ''
  }
}

const loadConfig = async (): Promise<void> => {
  loading.value = true
  try {
    const data = await getAIModelsConfig()
    snapshot.value = data
    applyResponseToForm(data)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载 AI 配置失败')
  } finally {
    loading.value = false
  }
}

const formatConfigText = (data: SystemConfigResponse): string => {
  return JSON.stringify(data, null, 2)
}

const loadFullConfig = async (): Promise<void> => {
  fullConfigLoading.value = true
  try {
    const data = await getSystemConfig()
    fullConfigText.value = formatConfigText(data)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载全量系统配置失败')
  } finally {
    fullConfigLoading.value = false
  }
}

const saveFullConfig = async (): Promise<void> => {
  fullConfigSaving.value = true
  try {
    const payload = JSON.parse(fullConfigText.value || '{}') as SystemConfigResponse
    const updated = await updateSystemConfig(payload)
    fullConfigText.value = formatConfigText(updated)
    ElMessage.success('全量系统配置已保存')
  } catch (error: any) {
    if (error instanceof SyntaxError) {
      ElMessage.error('配置 JSON 格式错误，请修正后重试')
    } else {
      ElMessage.error(error?.response?.data?.detail || '保存全量系统配置失败')
    }
  } finally {
    fullConfigSaving.value = false
  }
}

const reloadFullConfig = async (): Promise<void> => {
  await loadFullConfig()
}

const buildPayload = () => {
  return {
    kimi: {
      api_key: form.kimi.api_key,
      base_url: form.kimi.base_url.trim(),
      model: form.kimi.model.trim(),
      timeout: Number(form.kimi.timeout)
    },
    deepseek: {
      api_key: form.deepseek.api_key,
      base_url: form.deepseek.base_url.trim(),
      model: form.deepseek.model.trim(),
      timeout: Number(form.deepseek.timeout)
    },
    glm: {
      api_key: form.glm.api_key,
      base_url: form.glm.base_url.trim(),
      model: form.glm.model.trim(),
      timeout: Number(form.glm.timeout)
    }
  }
}

const saveConfig = async (): Promise<void> => {
  saving.value = true
  try {
    const updated = await updateAIModelsConfig(buildPayload())
    snapshot.value = updated
    applyResponseToForm(updated)
    ElMessage.success('AI 配置已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存 AI 配置失败')
  } finally {
    saving.value = false
  }
}

const cancelChanges = (): void => {
  if (!snapshot.value) return
  applyResponseToForm(snapshot.value)
  ElMessage.info('已取消未保存的更改')
}

const resetToDefaults = async (): Promise<void> => {
  try {
    await ElMessageBox.confirm('将本地表单重置为默认模型参数（不会立即保存），是否继续？', '重置确认', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })

    for (const provider of providerOrder) {
      form[provider].base_url = defaults[provider].base_url
      form[provider].model = defaults[provider].model
      form[provider].timeout = defaults[provider].timeout
      form[provider].api_key = ''
    }
    ElMessage.success('已重置为默认参数，点击“保存”后生效')
  } catch {
    // cancelled by user
  }
}

onMounted(async () => {
  await Promise.all([loadConfig(), loadFullConfig()])
})
</script>

<style scoped>
.config-page {
  padding: 8px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.config-content {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  max-width: 960px;
}

.config-card {
  margin-top: 20px;
  border: 1px solid var(--border-color);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hint {
  margin-bottom: 16px;
}

.config-form {
  margin-top: 8px;
}

.provider-section {
  padding: 4px 0;
}

.provider-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.provider-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.form-actions {
  margin-top: 8px;
  display: flex;
  gap: 10px;
}

.raw-editor {
  margin-top: 8px;
}
</style>
