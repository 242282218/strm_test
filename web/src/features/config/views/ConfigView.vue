<template>
  <div class="config-page">
    <div class="config-content">
      <el-alert
        type="success"
        :closable="false"
        show-icon
        class="contract-status"
        :title="`配置契约已加载 · 敏感字段 ${configMetadata.sensitive_fields.length} 项`"
        :description="`已配置 ${getConfiguredSensitiveFieldCount(configMetadata.sensitive_fields_status)} 项敏感字段`"
      />

      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>配置分组</span>
          </div>
        </template>

        <el-alert
          v-if="selectedGroupLabel"
          type="info"
          :closable="false"
          show-icon
          class="group-selection-status"
          :title="`当前分组：${selectedGroupLabel}`"
        />

        <div class="group-skeleton-list">
          <button
            v-for="group in schemaGroups"
            :key="group.key"
            type="button"
            class="group-skeleton-tag"
            :class="{ 'is-active': selectedGroupKey === group.key }"
            :data-testid="`config-group-${group.key}`"
            @click="selectedGroupKey = group.key"
          >
            <el-tag size="small" :effect="selectedGroupKey === group.key ? 'dark' : 'plain'">
              {{ group.label }}
            </el-tag>
          </button>
        </div>
      </el-card>

      <el-card v-if="showProfileSection" data-testid="config-section-profile" class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>个人中心</span>
          </div>
        </template>

        <div class="profile-panel-list">
          <section class="profile-panel">
            <span class="profile-panel-label">当前账号</span>
            <span class="profile-panel-value">{{ currentUsername }}</span>
            <span class="profile-panel-hint">角色：{{ currentRoleLabel }}</span>
          </section>

          <section class="profile-panel">
            <div class="profile-action-row">
              <div>
                <span class="profile-panel-label">外观设置</span>
                <span class="profile-panel-hint">切换深色模式会立即同步到当前浏览器。</span>
              </div>
              <div data-testid="profile-theme-switch">
                <el-switch v-model="isDark" inline-prompt active-text="暗" inactive-text="亮" />
              </div>
            </div>
          </section>

          <section class="profile-panel">
            <div class="profile-action-row">
              <div>
                <span class="profile-panel-label">安全操作</span>
                <span class="profile-panel-hint">如需更新登录凭据，可在这里修改当前账号密码。</span>
              </div>
              <el-button type="primary" @click="openProfileChangePasswordDialog">修改密码</el-button>
            </div>
          </section>
        </div>
      </el-card>

      <el-dialog
        v-model="profileChangePasswordDialogVisible"
        title="修改密码"
        width="420px"
        append-to-body
        destroy-on-close
      >
        <el-form label-width="90px">
          <el-form-item label="原密码">
            <el-input v-model="profilePasswordForm.oldPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="profilePasswordForm.newPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="确认密码">
            <el-input v-model="profilePasswordForm.confirmPassword" type="password" show-password />
          </el-form-item>
        </el-form>
        <template #footer>
          <span class="dialog-footer">
            <el-button @click="closeProfileChangePasswordDialog">取消</el-button>
            <el-button type="primary" @click="submitProfileChangePassword">确认</el-button>
          </span>
        </template>
      </el-dialog>

      <AsyncConfigGroupSectionRenderer
        v-if="activeStructuredSectionKey"
        :section-key="activeStructuredSectionKey"
        :selected-group-label="selectedGroupLabel"
        :loading="loading"
        :saving="saving"
        :config-loading="configLoading"
        :providers="providers"
        :basic-form="basicForm"
        :quark-form="quarkForm"
        :security-form="securityForm"
        :alist-form="alistForm"
        :tmdb-form="tmdbForm"
        :log-form="logForm"
        :cors-form="corsForm"
        :telegram-form="telegramForm"
        :wechat-form="wechatForm"
        :webdav-form="webdavForm"
        v-model:endpoints-form-json="endpointsFormJson"
        :add-provider="addProvider"
        :remove-provider="removeProvider"
        :save-providers="saveProviders"
        :load-providers="loadProviders"
      />

      <el-card data-testid="config-section-json" class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>高级配置（JSON）</span>
          </div>
        </template>

        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="该区域可编辑全部配置。敏感字段会脱敏显示；保持脱敏值不改动即可保留原密钥。"
          class="hint"
        />

        <el-input
          v-model="rawConfigJson"
          type="textarea"
          :rows="18"
          class="config-json-editor"
          v-loading="configLoading"
        />

        <div class="form-actions">
          <el-button @click="formatSystemConfig">格式化 JSON</el-button>
          <el-button @click="loadSystemConfig" :loading="configLoading">重新加载</el-button>
          <el-button type="primary" @click="saveSystemConfig" :loading="configSaving">保存全部配置</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, defineComponent, h, reactive, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useTheme } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import {
  getAIProviders,
  getSystemConfig,
  getSystemConfigMetadata,
  updateAIProviders,
  updateSystemConfig,
  type AIProviderItem,
  type SystemConfigMetadataResponse
} from '@/features/config/api/systemConfig'
import {
  DEFAULT_ENDPOINTS_FORM_JSON,
  PROFILE_GROUP_KEY,
  buildSystemConfigPayload,
  createDefaultAListForm,
  createDefaultBasicForm,
  createDefaultConfigMetadata,
  createDefaultCorsForm,
  createDefaultLogForm,
  createDefaultQuarkForm,
  createDefaultSecurityForm,
  createDefaultTelegramForm,
  createDefaultTmdbForm,
  createDefaultWeChatForm,
  createDefaultWebDAVForm,
  getConfiguredSensitiveFieldCount,
  getSchemaGroups,
  hydrateConfigForms,
  type AListForm,
  type BasicForm,
  type ConfigFormState,
  type CorsForm,
  type LogForm,
  type QuarkForm,
  type SecurityForm,
  type TelegramForm,
  type TmdbForm,
  type WeChatForm,
  type WebDAVForm,
} from '@/features/config/config-view-model'

const ConfigSectionLoading = defineComponent({
  name: 'ConfigSectionLoading',
  setup() {
    return () =>
      h(
        'div',
        {
          class: 'config-card config-section-loading',
          'data-testid': 'config-section-loading',
        },
        '配置分组加载中...'
      )
  },
})

const AsyncConfigGroupSectionRenderer = defineAsyncComponent({
  loader: async () => {
    await Promise.resolve()
    return (await import('./ConfigGroupSectionRenderer.vue')).default
  },
  loadingComponent: ConfigSectionLoading,
  delay: 0,
})

interface ProviderForm extends AIProviderItem {
  api_key: string
}

const route = useRoute()
const authStore = useAuthStore()
const { isDark } = useTheme()

const loading = ref(false)
const saving = ref(false)
const providers = ref<ProviderForm[]>([])
const configLoading = ref(false)
const configSaving = ref(false)
const rawConfigJson = ref('{}')
const configMetadata = ref<SystemConfigMetadataResponse>(createDefaultConfigMetadata())
const selectedGroupKey = ref(typeof route.query.group === 'string' ? route.query.group : '')
const activeStructuredSectionKey = computed(() => {
  return selectedGroupKey.value === 'profile' ? '' : selectedGroupKey.value
})
const profileChangePasswordDialogVisible = ref(false)
const profilePasswordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})
const schemaGroups = computed(() => getSchemaGroups(configMetadata.value.schema))
const selectedGroupLabel = computed(() => {
  return schemaGroups.value.find(group => group.key === selectedGroupKey.value)?.label ?? ''
})
const currentUsername = computed(() => authStore.user?.username || '管理员')
const currentRoleLabel = computed(() => authStore.user?.role || '未知')
const showProfileSection = computed(() => selectedGroupKey.value === 'profile')
const webdavForm = reactive<WebDAVForm>(createDefaultWebDAVForm())
const quarkForm = reactive<QuarkForm>(createDefaultQuarkForm())
const securityForm = reactive<SecurityForm>(createDefaultSecurityForm())
const alistForm = reactive<AListForm>(createDefaultAListForm())
const tmdbForm = reactive<TmdbForm>(createDefaultTmdbForm())
const logForm = reactive<LogForm>(createDefaultLogForm())
const corsForm = reactive<CorsForm>(createDefaultCorsForm())
const telegramForm = reactive<TelegramForm>(createDefaultTelegramForm())
const basicForm = reactive<BasicForm>(createDefaultBasicForm())
const wechatForm = reactive<WeChatForm>(createDefaultWeChatForm())
const endpointsFormJson = ref(DEFAULT_ENDPOINTS_FORM_JSON)
const configForms: ConfigFormState = {
  webdavForm,
  quarkForm,
  securityForm,
  alistForm,
  tmdbForm,
  logForm,
  corsForm,
  telegramForm,
  basicForm,
  wechatForm,
}

const resolveErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof Error && typeof error.message === 'string' && error.message) {
    return error.message
  }
  return fallback
}

const resetProfilePasswordForm = () => {
  profilePasswordForm.oldPassword = ''
  profilePasswordForm.newPassword = ''
  profilePasswordForm.confirmPassword = ''
}

const closeProfileChangePasswordDialog = () => {
  profileChangePasswordDialogVisible.value = false
  resetProfilePasswordForm()
}

const openProfileChangePasswordDialog = () => {
  profileChangePasswordDialogVisible.value = true
}

const submitProfileChangePassword = async () => {
  if (!profilePasswordForm.oldPassword || !profilePasswordForm.newPassword || !profilePasswordForm.confirmPassword) {
    ElMessage.error('请填写完整密码信息')
    return
  }
  if (profilePasswordForm.newPassword !== profilePasswordForm.confirmPassword) {
    ElMessage.error('两次输入的新密码不一致')
    return
  }

  await authStore.changePassword(profilePasswordForm.oldPassword, profilePasswordForm.newPassword)
  ElMessage.success('密码修改成功')
  closeProfileChangePasswordDialog()
}

const loadProviders = async () => {
  loading.value = true
  try {
    const res = await getAIProviders()
    providers.value = res.providers.map(p => ({
      ...p,
      api_key: ''
    }))
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '加载配置失败'))
  } finally {
    loading.value = false
  }
}

const saveProviders = async () => {
  saving.value = true
  try {
    await updateAIProviders({
      providers: providers.value.map(p => ({
        name: p.name,
        api_key: p.api_key,
        base_url: p.base_url,
        model: p.model,
        timeout: p.timeout,
        enabled: p.enabled,
        priority: p.priority
      }))
    })
    ElMessage.success('保存成功')
    await loadProviders()
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

const addProvider = () => {
  providers.value.push({
    name: '',
    api_key: '',
    api_key_masked: '',
    configured: false,
    base_url: '',
    model: '',
    timeout: 30,
    enabled: true,
    priority: 100
  })
}

const removeProvider = (idx: number) => {
  providers.value.splice(idx, 1)
}

const resolveInitialGroupKey = () => {
  const routeGroup = typeof route.query.group === 'string' ? route.query.group : ''
  const availableGroups = getSchemaGroups(configMetadata.value.schema)

  if (routeGroup && availableGroups.some(group => group.key === routeGroup)) {
    return routeGroup
  }

  return availableGroups.find(group => group.key !== PROFILE_GROUP_KEY)?.key ?? availableGroups[0]?.key ?? ''
}

const loadSystemConfigMetadata = async () => {
  try {
    configMetadata.value = await getSystemConfigMetadata()
    selectedGroupKey.value = resolveInitialGroupKey()
  } catch (error: unknown) {
    configMetadata.value = createDefaultConfigMetadata()
    selectedGroupKey.value = ''
    ElMessage.error(resolveErrorMessage(error, '加载配置元数据失败'))
  }
}

const loadSystemConfig = async () => {
  configLoading.value = true
  try {
    const config = await getSystemConfig()
    rawConfigJson.value = JSON.stringify(config, null, 2)
    endpointsFormJson.value = hydrateConfigForms(config, configForms)
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '加载系统配置失败'))
  } finally {
    configLoading.value = false
  }
}

const parseSystemConfigInput = (): Record<string, unknown> | null => {
  try {
    const parsed = JSON.parse(rawConfigJson.value)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      ElMessage.error('配置必须是 JSON 对象')
      return null
    }
    return parsed as Record<string, unknown>
  } catch {
    ElMessage.error('JSON 格式错误，请先修正')
    return null
  }
}

const formatSystemConfig = () => {
  const parsed = parseSystemConfigInput()
  if (!parsed) {
    return
  }
  rawConfigJson.value = JSON.stringify(parsed, null, 2)
}

const parseEndpointsInput = (): unknown[] | null => {
  try {
    const parsedEndpoints = JSON.parse(endpointsFormJson.value)
    if (!Array.isArray(parsedEndpoints)) {
      ElMessage.error('端点映射必须是 JSON 数组')
      return null
    }
    return parsedEndpoints
  } catch {
    ElMessage.error('端点映射 JSON 格式错误，请先修正')
    return null
  }
}

const saveSystemConfig = async () => {
  const payload = parseSystemConfigInput()
  if (!payload) {
    return
  }

  const parsedEndpoints = parseEndpointsInput()
  if (!parsedEndpoints) {
    return
  }

  const nextPayload = buildSystemConfigPayload(payload, configForms, parsedEndpoints)

  configSaving.value = true
  try {
    await updateSystemConfig(nextPayload)
    ElMessage.success('系统配置保存成功')
    await Promise.all([loadProviders(), loadSystemConfig()])
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '系统配置保存失败'))
  } finally {
    configSaving.value = false
  }
}

onMounted(() => {
  void Promise.all([loadProviders(), loadSystemConfig(), loadSystemConfigMetadata()])
})
</script>

<style scoped>
.config-page {
  padding: 8px 0 0;
}

.config-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.config-card {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hint {
  margin-bottom: var(--space-4);
}

.contract-status {
  margin-bottom: 0;
}

.group-selection-status {
  margin-bottom: var(--space-3);
}

.group-skeleton-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.group-skeleton-tag {
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.group-skeleton-tag.is-active {
  outline: none;
}

.profile-panel-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.profile-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: var(--space-4);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.24);
}

.profile-panel-label {
  font-size: 0.88rem;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.profile-panel-value {
  font-size: 1rem;
  color: var(--text-primary);
}

.profile-panel-hint {
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.profile-action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.provider-section {
  padding: var(--space-5);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-4);
}

.provider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.provider-header h3 {
  margin: 0;
}

.provider-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.hint-text {
  margin-left: 10px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: var(--space-4);
}

.config-json-editor :deep(textarea) {
  font-family: Consolas, "Courier New", monospace;
  line-height: 1.45;
}
</style>
