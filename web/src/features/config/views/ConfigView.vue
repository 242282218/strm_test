<template>
  <div class="config-page">
    <section class="config-hero page-surface">
      <div class="hero-main">
        <div class="hero-toolbar">
          <div class="hero-copy">
            <span class="hero-chip">Config Workbench</span>
            <h2 class="hero-title">配置契约、当前分组与敏感字段状态集中收口</h2>
            <p class="hero-description">
              先看配置契约和当前工作区，再进入结构化表单或 JSON 编辑，避免系统配置继续停留在多块卡片直排的旧工作流。
            </p>
          </div>

          <div class="hero-actions">
            <el-button :loading="loading || configLoading" :icon="Refresh" @click="reloadConfigWorkbench">
              重新加载
            </el-button>
            <el-button type="primary" :loading="configSaving" @click="saveSystemConfig">
              保存全部配置
            </el-button>
          </div>
        </div>

        <div class="hero-metrics">
          <article
            v-for="metric in heroMetrics"
            :key="metric.label"
            class="metric-card"
            :class="metric.tone"
          >
            <div class="metric-head">
              <span class="metric-label">{{ metric.label }}</span>
              <div class="metric-icon">
                <el-icon size="18">
                  <component :is="metric.icon" />
                </el-icon>
              </div>
            </div>
            <strong class="metric-value">{{ metric.value }}</strong>
            <p class="metric-detail">{{ metric.detail }}</p>
          </article>
        </div>
      </div>

      <div class="hero-side">
        <article class="hero-side-card">
          <div class="hero-side-head">
            <div class="hero-side-heading">
              <span class="section-label">聚焦</span>
              <h3 class="hero-side-title">{{ selectedGroupLabel || '等待配置元数据' }}</h3>
            </div>
            <el-tag :type="showProfileSection ? 'warning' : 'primary'" size="small">
              {{ showProfileSection ? '个人中心' : '结构化表单' }}
            </el-tag>
          </div>

          <p class="spotlight-description">{{ selectedGroupDescription }}</p>

          <div class="group-pill-list">
            <span
              v-for="group in schemaGroups.slice(0, 5)"
              :key="group.key"
              class="group-pill"
            >
              {{ group.label }}
            </span>
          </div>
        </article>

        <article class="hero-side-card">
          <div class="hero-side-head">
            <div class="hero-side-heading">
              <span class="section-label">账号</span>
              <h3 class="hero-side-title">{{ currentUsername }}</h3>
            </div>
            <el-tag type="info" size="small">{{ currentRoleLabel }}</el-tag>
          </div>

          <p class="spotlight-description">
            主题切换和密码修改保留在当前工作台，不需要先切到个人中心再完成常用安全动作。
          </p>

          <div class="account-actions">
            <div data-testid="profile-theme-switch">
              <el-switch v-model="isDark" inline-prompt active-text="暗" inactive-text="亮" />
            </div>
            <el-button type="primary" plain @click="openProfileChangePasswordDialog">修改密码</el-button>
          </div>
        </article>
      </div>
    </section>

    <section class="config-group-panel page-surface">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">分组</span>
          <h3 class="panel-title">配置分组</h3>
          <p class="panel-description">分组切换会同步写回 URL，刷新或分享当前工作区时不会丢失上下文。</p>
        </div>
        <el-tag v-if="selectedGroupLabel" type="primary" size="small">当前分组：{{ selectedGroupLabel }}</el-tag>
      </div>

      <el-alert
        type="success"
        :closable="false"
        show-icon
        class="contract-status"
        :title="`配置契约已加载 · 敏感字段 ${configMetadata.sensitive_fields.length} 项`"
        :description="`已配置 ${configuredSensitiveFieldCount} 项敏感字段`"
      />

      <div class="group-skeleton-list">
        <button
          v-for="group in schemaGroups"
          :key="group.key"
          type="button"
          class="group-skeleton-tag"
          :class="{ 'is-active': selectedGroupKey === group.key }"
          :data-testid="`config-group-${group.key}`"
          :aria-pressed="selectedGroupKey === group.key"
          @click="selectedGroupKey = group.key"
        >
          <el-tag size="small" :effect="selectedGroupKey === group.key ? 'dark' : 'plain'">
            {{ group.label }}
          </el-tag>
        </button>
      </div>
    </section>

    <section
      v-if="showProfileSection"
      data-testid="config-section-profile"
      class="profile-workbench page-surface"
    >
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">个人中心</span>
          <h3 class="panel-title">账号与外观设置</h3>
          <p class="panel-description">管理当前账号、主题偏好和密码修改入口。</p>
        </div>
      </div>

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
    </section>

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

    <section data-testid="config-section-json" class="config-json-panel page-surface">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">JSON</span>
          <h3 class="panel-title">高级配置（JSON）</h3>
          <p class="panel-description">在结构化分组之外，保留完整配置的直接编辑入口。</p>
        </div>
      </div>

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
    </section>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed, defineAsyncComponent, defineComponent, h, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Collection, Lock, Refresh, Setting, User } from '@/components/icons'
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

type MetricTone = 'primary' | 'success' | 'warning' | 'info'

interface HeroMetric {
  label: string
  value: string
  detail: string
  icon: Component
  tone: MetricTone
}

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
const router = useRouter()
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

const configuredSensitiveFieldCount = computed(() => {
  return getConfiguredSensitiveFieldCount(configMetadata.value.sensitive_fields_status)
})

const selectedGroupDescription = computed(() => {
  if (!selectedGroupLabel.value) {
    return '配置元数据加载完成后，这里会显示当前工作区与对应的编辑方式。'
  }

  if (showProfileSection.value) {
    return '当前工作区聚焦账号、外观和密码更新。其余系统参数仍可通过分组或 JSON 工作台编辑。'
  }

  return `${selectedGroupLabel.value} 当前作为主工作区，结构化表单和 JSON 配置会围绕这组参数保持同步。`
})

const heroMetrics = computed<HeroMetric[]>(() => {
  const totalSensitiveFields = configMetadata.value.sensitive_fields.length
  return [
    {
      label: '敏感字段',
      value: `${configuredSensitiveFieldCount.value} / ${totalSensitiveFields}`,
      detail: '已配置的敏感字段数量，直接反映当前契约完成度。',
      icon: Lock,
      tone: configuredSensitiveFieldCount.value > 0 ? 'success' : 'warning'
    },
    {
      label: '配置分组',
      value: `${schemaGroups.value.length} 组`,
      detail: '系统配置分组数量，包含个人中心与结构化工作台。',
      icon: Collection,
      tone: 'primary'
    },
    {
      label: '当前工作区',
      value: selectedGroupLabel.value || '未选择',
      detail: '当前正在查看的配置分组，会同步写回 URL。',
      icon: Setting,
      tone: selectedGroupLabel.value ? 'primary' : 'info'
    },
    {
      label: 'AI 提供商',
      value: `${providers.value.length} 个`,
      detail: '已加载的提供商数量，供 AI 配置分组直接复用。',
      icon: User,
      tone: providers.value.length > 0 ? 'success' : 'info'
    }
  ]
})

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

const reloadConfigWorkbench = async () => {
  await Promise.all([loadProviders(), loadSystemConfig(), loadSystemConfigMetadata()])
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

watch(selectedGroupKey, (nextGroupKey) => {
  const currentRouteGroup = typeof route.query.group === 'string' ? route.query.group : ''
  if (nextGroupKey === currentRouteGroup) {
    return
  }

  const nextQuery = { ...route.query }
  if (nextGroupKey) {
    nextQuery.group = nextGroupKey
  } else {
    delete nextQuery.group
  }

  void router.replace({ query: nextQuery })
})

onMounted(() => {
  void reloadConfigWorkbench()
})
</script>

<style scoped>
.config-page {
  display: flex;
  flex-direction: column;
  gap: var(--page-section-gap);
}

.config-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 420px);
  gap: var(--space-5);
  overflow: hidden;
  padding: 24px;
}

.config-hero::before,
.config-hero::after {
  content: '';
  position: absolute;
  pointer-events: none;
}

.config-hero::before {
  inset: -20% auto auto 56%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79, 141, 246, 0.18), transparent 72%);
}

.config-hero::after {
  inset: auto auto -24% -8%;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(127, 113, 234, 0.14), transparent 70%);
}

.hero-main,
.hero-side {
  position: relative;
  z-index: 1;
}

.hero-main {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-toolbar,
.panel-head,
.hero-side-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.hero-copy,
.panel-heading,
.hero-side-heading {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 10px;
}

.hero-actions {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.hero-chip {
  display: inline-flex;
  align-self: flex-start;
  padding: 7px 12px;
  border-radius: var(--radius-full);
  background: rgba(79, 141, 246, 0.14);
  color: var(--primary-700);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.hero-title {
  margin: 0;
  max-width: 17ch;
  font-size: clamp(1.7rem, 1.32rem + 0.9vw, 2.35rem);
  line-height: 1.06;
  font-weight: var(--font-bold);
  letter-spacing: var(--letter-spacing-tight);
  color: var(--text-primary);
}

.hero-description,
.metric-detail,
.spotlight-description,
.panel-description,
.profile-panel-hint {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.65;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card,
.hero-side-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  background: rgba(255, 255, 255, 0.36);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.metric-card {
  display: flex;
  min-height: 150px;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
  padding: 16px;
}

.metric-card.primary {
  --metric-bg: rgba(79, 141, 246, 0.14);
  --metric-color: var(--primary-700);
}

.metric-card.success {
  --metric-bg: rgba(51, 176, 122, 0.14);
  --metric-color: var(--success-700);
}

.metric-card.warning {
  --metric-bg: rgba(231, 168, 61, 0.16);
  --metric-color: var(--warning-700);
}

.metric-card.info {
  --metric-bg: rgba(75, 159, 216, 0.14);
  --metric-color: var(--info-700);
}

.metric-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.metric-label {
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.04em;
}

.metric-icon {
  display: flex;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: var(--metric-bg);
  color: var(--metric-color);
}

.metric-value {
  color: var(--text-primary);
  font-size: clamp(1.36rem, 1.08rem + 0.62vw, 1.9rem);
  line-height: 1.05;
}

.hero-side {
  display: grid;
  gap: 12px;
}

.hero-side-card,
.config-group-panel,
.profile-workbench,
.config-json-panel {
  padding: 22px;
}

.hero-side-title,
.panel-title {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.02rem;
  line-height: 1.4;
  font-weight: var(--font-semibold);
}

.group-pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.group-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: var(--radius-full);
  background: rgba(79, 141, 246, 0.1);
  color: var(--primary-700);
  font-size: 0.78rem;
  font-weight: var(--font-medium);
}

.account-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
}

.contract-status,
.hint {
  margin-bottom: 0;
}

.group-skeleton-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
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

.profile-action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-top: var(--space-4);
}

.config-json-editor :deep(textarea) {
  font-family: Consolas, "Courier New", monospace;
  line-height: 1.45;
}

@media (max-width: 1200px) {
  .config-hero {
    grid-template-columns: 1fr;
  }

  .hero-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 992px) {
  .hero-toolbar,
  .panel-head,
  .hero-side-head,
  .profile-action-row {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .config-hero,
  .config-group-panel,
  .profile-workbench,
  .config-json-panel,
  .hero-side-card {
    padding: 18px;
  }

  .hero-title {
    max-width: none;
    font-size: 1.5rem;
  }

  .hero-metrics {
    grid-template-columns: 1fr;
  }

  .form-actions {
    justify-content: flex-start;
  }
}
</style>
