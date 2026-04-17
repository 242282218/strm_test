<template>
  <div class="notifications-page">
    <section class="notifications-hero page-surface">
      <div class="hero-main">
        <div class="hero-toolbar">
          <div class="hero-copy">
            <span class="hero-chip">Signal Relay</span>
            <h2 class="hero-title">通知渠道、启用状态与联调反馈统一收口</h2>
            <p class="hero-description">
              把渠道保存状态、凭证完整度和测试入口收敛到同一屏，避免通知配置停留在“填表后再猜结果”的旧流程。
            </p>
          </div>

          <div class="hero-actions">
            <el-button
              v-if="currentChannel"
              type="danger"
              plain
              :icon="Delete"
              data-testid="notification-delete-button"
              @click="deleteConfig"
            >
              删除配置
            </el-button>
            <el-button
              type="primary"
              :loading="isLoading('saving')"
              data-testid="notification-save-button"
              @click="saveConfig"
            >
              <el-icon><Check /></el-icon>
              保存配置
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
        <article class="hero-side-card focus-card">
          <div class="hero-side-head">
            <div class="hero-side-heading">
              <span class="section-label">聚焦</span>
              <h3 class="hero-side-title">{{ spotlightTitle }}</h3>
            </div>
            <el-tag :type="deliveryState.tag" size="small">{{ deliveryState.label }}</el-tag>
          </div>

          <p class="spotlight-description">{{ spotlightDescription }}</p>

          <div class="credential-list">
            <div v-for="field in requiredFields" :key="field.label" class="credential-item">
              <span class="credential-label">{{ field.label }}</span>
              <el-tag :type="field.value ? 'success' : 'info'" size="small">
                {{ field.value ? '已填写' : '待填写' }}
              </el-tag>
            </div>
          </div>
        </article>

        <article class="hero-side-card test-card">
          <div class="hero-side-head">
            <div class="hero-side-heading">
              <span class="section-label">联调</span>
              <h3 class="hero-side-title">测试发送</h3>
            </div>
            <el-tag :type="hasReadyCredentials ? 'success' : 'warning'" size="small">
              {{ hasReadyCredentials ? '凭证已就绪' : '待补齐' }}
            </el-tag>
          </div>

          <p class="test-copy">
            当前测试接口发送固定预览文案，避免界面提供后端并不支持的自定义消息输入。
          </p>

          <div class="test-preview">
            {{ testMessagePreview }}
          </div>

          <div class="test-actions">
            <el-button
              type="primary"
              :loading="isLoading('testing')"
              :disabled="!currentChannel || !currentChannel.is_enabled"
              data-testid="notification-test-button"
              @click="sendTest"
            >
              <el-icon><Promotion /></el-icon>
              发送测试
            </el-button>
            <p class="test-hint">{{ testHint }}</p>
          </div>
        </article>
      </div>
    </section>

    <section class="notification-config-panel page-surface">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">配置</span>
          <h3 class="panel-title">通知渠道配置</h3>
          <p class="panel-description">
            先选择渠道模板，再保存并启用，最后通过测试发送验证链路是否可达。
          </p>
        </div>

        <div class="panel-toggle">
          <span class="panel-toggle-label">启用通知</span>
          <el-switch
            v-model="config.enabled"
            active-text="已启用"
            inactive-text="未启用"
            :disabled="!currentChannel"
          />
        </div>
      </div>

      <el-alert
        :title="configStatusTitle"
        :description="deliveryState.detail"
        :type="currentChannel?.is_enabled ? 'success' : currentChannel ? 'warning' : 'info'"
        :closable="false"
        show-icon
        class="config-status"
      />

      <el-form label-width="120px" :model="config" class="config-form">
        <el-form-item label="通知方式">
          <el-select v-model="config.channel" style="width: 100%" @change="onChannelChange">
            <el-option
              v-for="channel in SUPPORTED_NOTIFICATION_CHANNELS"
              :key="channel.value"
              :label="channel.label"
              :value="channel.value"
            />
          </el-select>
        </el-form-item>

        <template v-if="config.channel === 'telegram'">
          <el-form-item label="Bot Token">
            <el-input
              v-model="config.telegram.bot_token"
              placeholder="123456789:ABCdefGHIjklMNOpqrSTUvwxyz"
            />
          </el-form-item>
          <el-form-item label="Chat ID">
            <el-input v-model="config.telegram.chat_id" placeholder="-1001234567890" />
          </el-form-item>
        </template>

        <template v-if="config.channel === 'serverchan'">
          <el-form-item label="SendKey">
            <el-input v-model="config.serverchan.send_key" placeholder="SCTxxxxxxxxxxxxxxxxxxxxxx" />
          </el-form-item>
        </template>
      </el-form>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { Check, Delete, Promotion, Bell, Setting, Message, CircleCheck } from '@/components/icons'
import {
  getChannels,
  createChannel,
  updateChannel,
  deleteChannel,
  testChannel,
  convertFrontendToBackend,
  convertBackendToFrontend,
  SUPPORTED_NOTIFICATION_CHANNELS,
  type Channel,
  type FrontendNotificationConfig,
  type SupportedNotificationChannel
} from '@/features/notifications/api/notification'
import { useLoadingStore, useNotification, useAsyncNotify } from '@/composables'

type MetricTone = 'primary' | 'success' | 'warning' | 'info'

interface HeroMetric {
  label: string
  value: string
  detail: string
  icon: Component
  tone: MetricTone
}

const { isLoading, withLoading } = useLoadingStore(['saving', 'testing'])
const { success, error, warning } = useNotification()
const { withConfirm } = useAsyncNotify()

const testMessagePreview = '这是一条测试消息，来自 Quark STRM 通知服务。'
const currentChannel = ref<Channel | null>(null)

const createDefaultConfig = (): FrontendNotificationConfig => ({
  enabled: false,
  channel: 'telegram',
  telegram: {
    bot_token: '',
    chat_id: ''
  },
  serverchan: {
    send_key: ''
  }
})

const config = reactive<FrontendNotificationConfig>(createDefaultConfig())

const selectedChannelLabel = computed(() => {
  return SUPPORTED_NOTIFICATION_CHANNELS.find(channel => channel.value === config.channel)?.label ?? config.channel
})

const requiredFields = computed(() => {
  if (config.channel === 'telegram') {
    return [
      { label: 'Bot Token', value: config.telegram.bot_token.trim() },
      { label: 'Chat ID', value: config.telegram.chat_id.trim() }
    ]
  }

  return [{ label: 'SendKey', value: config.serverchan.send_key.trim() }]
})

const configuredFieldCount = computed(() => {
  return requiredFields.value.filter(field => field.value.length > 0).length
})

const hasReadyCredentials = computed(() => {
  return configuredFieldCount.value === requiredFields.value.length
})

const deliveryState = computed(() => {
  if (!currentChannel.value) {
    return {
      label: '未保存草稿',
      detail: `当前正在编辑 ${selectedChannelLabel.value} 模板，保存后才会进入真实通知链路。`,
      tag: 'info' as const,
      tone: 'info' as MetricTone
    }
  }

  if (!currentChannel.value.is_enabled) {
    return {
      label: '已保存待启用',
      detail: '渠道已经落库，但通知开关仍关闭，测试发送会继续被阻止。',
      tag: 'warning' as const,
      tone: 'warning' as MetricTone
    }
  }

  return {
    label: '已启用',
    detail: '当前渠道已进入通知链路，可直接发送测试消息验证到达情况。',
    tag: 'success' as const,
    tone: 'success' as MetricTone
  }
})

const spotlightTitle = computed(() => {
  return currentChannel.value?.channel_name || `${selectedChannelLabel.value} 草稿`
})

const spotlightDescription = computed(() => {
  if (!currentChannel.value) {
    return `先完成 ${selectedChannelLabel.value} 凭证并保存配置，再进行启用和联调。`
  }

  return currentChannel.value.is_enabled
    ? `${currentChannel.value.channel_name} 当前处于启用状态，后续发送会沿用这条配置。`
    : `${currentChannel.value.channel_name} 已保存，但仍处于停用状态，需要先打开通知开关。`
})

const testHint = computed(() => {
  if (!currentChannel.value) {
    return '请先保存配置，再创建真实通知渠道。'
  }

  if (!currentChannel.value.is_enabled) {
    return '请先启用通知开关，再发送测试消息。'
  }

  if (!hasReadyCredentials.value) {
    return '当前模板仍有必填凭证为空，测试前先补齐字段。'
  }

  return '当前链路已就绪，可以直接发送测试消息验证送达。'
})

const configStatusTitle = computed(() => {
  return `${selectedChannelLabel.value} · ${deliveryState.value.label}`
})

const heroMetrics = computed<HeroMetric[]>(() => {
  return [
    {
      label: '已保存渠道',
      value: currentChannel.value ? '1 条' : '0 条',
      detail: currentChannel.value ? '当前模板已落库，可继续启停或删除。' : '当前仍是草稿，尚未进入真实投递链路。',
      icon: Bell,
      tone: currentChannel.value ? 'success' : 'primary'
    },
    {
      label: '当前模板',
      value: selectedChannelLabel.value,
      detail: '切换渠道会自动尝试加载该模板的已有配置。',
      icon: Setting,
      tone: 'primary'
    },
    {
      label: '凭证完整度',
      value: `${configuredFieldCount.value} / ${requiredFields.value.length}`,
      detail: '这里统计当前模板的必填凭证是否已经补齐。',
      icon: CircleCheck,
      tone: hasReadyCredentials.value ? 'success' : 'warning'
    },
    {
      label: '发送状态',
      value: deliveryState.value.label,
      detail: deliveryState.value.detail,
      icon: Message,
      tone: deliveryState.value.tone
    }
  ]
})

const resetChannelConfig = (channel: SupportedNotificationChannel) => {
  if (channel === 'telegram') {
    config.telegram = createDefaultConfig().telegram
    return
  }

  config.serverchan = createDefaultConfig().serverchan
}

const onChannelChange = () => {
  void loadChannelConfig()
}

const loadChannelConfig = async () => {
  try {
    const channels = await getChannels()
    const channel = channels.find(item => item.channel_type === config.channel)
    if (channel) {
      currentChannel.value = channel
      const frontendConfig = convertBackendToFrontend(channel)
      config.enabled = frontendConfig.enabled
      resetChannelConfig(config.channel)
      Object.assign(config[config.channel], frontendConfig[config.channel] ?? {})
    } else {
      currentChannel.value = null
      config.enabled = false
      resetChannelConfig(config.channel)
    }
  } catch {
    error('加载配置失败')
  }
}

const saveConfig = async () => {
  await withLoading('saving', async () => {
    const backendData = convertFrontendToBackend(config)

    if (currentChannel.value) {
      await updateChannel(currentChannel.value.id, {
        config: backendData.config,
        is_enabled: config.enabled
      })
    } else {
      currentChannel.value = await createChannel(backendData)
    }

    success('配置已保存')
    await loadChannelConfig()
  })
}

const deleteConfig = async () => {
  if (!currentChannel.value) return

  await withConfirm(
    async () => {
      const channelId = currentChannel.value?.id
      if (!channelId) return

      await deleteChannel(channelId)
      success('配置已删除')
      currentChannel.value = null
      config.enabled = false
      resetChannelConfig(config.channel)
    },
    {
      confirmMessage: '确定要删除该通知配置吗？',
      confirmTitle: '确认',
    }
  )
}

const sendTest = async () => {
  if (!currentChannel.value) {
    warning('请先保存配置')
    return
  }

  if (!currentChannel.value.is_enabled) {
    warning('请先启用通知')
    return
  }

  await withLoading('testing', async () => {
    await testChannel(currentChannel.value!.id)
    success('测试消息已发送')
  })
}

onMounted(() => {
  void loadChannelConfig()
})
</script>

<style scoped>
.notifications-page {
  display: flex;
  flex-direction: column;
  gap: var(--page-section-gap);
}

.notifications-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 420px);
  gap: var(--space-5);
  overflow: hidden;
  padding: 24px;
}

.notifications-hero::before,
.notifications-hero::after {
  content: '';
  position: absolute;
  pointer-events: none;
}

.notifications-hero::before {
  inset: -20% auto auto 56%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79, 141, 246, 0.18), transparent 72%);
}

.notifications-hero::after {
  inset: auto auto -20% -8%;
  width: 190px;
  height: 190px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(51, 176, 122, 0.14), transparent 70%);
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
  max-width: 16ch;
  font-size: clamp(1.7rem, 1.32rem + 0.9vw, 2.35rem);
  line-height: 1.06;
  font-weight: var(--font-bold);
  letter-spacing: var(--letter-spacing-tight);
  color: var(--text-primary);
}

.hero-description,
.metric-detail,
.spotlight-description,
.test-copy,
.test-hint,
.panel-description {
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
  font-size: clamp(1.36rem, 1.1rem + 0.62vw, 1.9rem);
  line-height: 1.05;
}

.hero-side {
  display: grid;
  gap: 12px;
}

.hero-side-card,
.notification-config-panel {
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

.credential-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
}

.credential-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.24);
}

.credential-label {
  color: var(--text-primary);
  font-size: 0.86rem;
  font-weight: var(--font-medium);
}

.test-preview {
  margin: 14px 0;
  padding: 14px 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.24);
  color: var(--text-primary);
  font-size: 0.88rem;
  line-height: 1.6;
}

.test-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.notification-config-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.panel-toggle {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 12px;
}

.panel-toggle-label {
  color: var(--text-secondary);
  font-size: 0.84rem;
  font-weight: var(--font-semibold);
}

.config-status {
  margin-bottom: 0;
}

.config-form {
  margin-top: 4px;
}

@media (max-width: 1200px) {
  .notifications-hero {
    grid-template-columns: 1fr;
  }

  .hero-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 992px) {
  .hero-toolbar,
  .panel-head,
  .hero-side-head {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .notifications-hero,
  .notification-config-panel,
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

  .panel-toggle {
    justify-content: space-between;
  }
}
</style>
