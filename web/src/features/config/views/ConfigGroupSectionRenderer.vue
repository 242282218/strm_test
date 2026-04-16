<template>
  <el-card v-if="sectionKey === 'basic'" data-testid="config-section-basic" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>基础设置</span>
      </div>
    </template>

    <el-form label-width="130px" class="config-form" v-loading="configLoading">
      <el-form-item label="数据库文件">
        <el-input v-model="basicForm.database" />
      </el-form-item>

      <el-form-item label="日志级别">
        <el-select v-model="basicForm.log_level">
          <el-option label="DEBUG" value="DEBUG" />
          <el-option label="INFO" value="INFO" />
          <el-option label="WARNING" value="WARNING" />
          <el-option label="ERROR" value="ERROR" />
        </el-select>
      </el-form-item>

      <el-form-item label="日志文件">
        <el-input v-model="basicForm.log_file" placeholder="留空表示不写入文件" />
      </el-form-item>

      <el-form-item label="彩色日志">
        <el-switch v-model="basicForm.colored_log" />
      </el-form-item>

      <el-form-item label="请求超时（秒)">
        <el-input-number v-model="basicForm.timeout" :min="1" :max="120" />
      </el-form-item>

      <el-form-item label="视频扩展名">
        <el-input v-model="basicForm.exts" type="textarea" :rows="4" placeholder="每行一个扩展名" />
      </el-form-item>

      <el-form-item label="字幕扩展名">
        <el-input v-model="basicForm.alt_exts" type="textarea" :rows="3" placeholder="每行一个扩展名" />
      </el-form-item>

      <el-form-item label="自动创建子目录">
        <el-switch v-model="basicForm.create_sub_directory" />
      </el-form-item>
    </el-form>
  </el-card>

  <EmbyConfigCard v-else-if="sectionKey === 'emby'" />

  <el-card v-else-if="sectionKey === 'quark'" data-testid="config-section-quark" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>夸克配置</span>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="Cookie 字段支持脱敏保留；留空或保持脱敏值不变即可沿用当前 Cookie。"
      class="hint"
    />

    <el-form label-width="130px" class="config-form" v-loading="configLoading">
      <el-form-item label="Cookie">
        <el-input
          v-model="quarkForm.cookie"
          type="password"
          show-password
          placeholder="留空或保持脱敏值不变"
        />
      </el-form-item>

      <el-form-item label="Referer">
        <el-input v-model="quarkForm.referer" />
      </el-form-item>

      <el-form-item label="根目录 ID">
        <el-input v-model="quarkForm.root_id" />
      </el-form-item>

      <el-form-item label="仅处理视频">
        <el-switch v-model="quarkForm.only_video" />
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-else-if="sectionKey === 'security'" data-testid="config-section-security" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>安全设置</span>
      </div>
    </template>

    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="API Key 字段支持脱敏保留；留空或保持脱敏值不变即可沿用当前密钥。"
      class="hint"
    />

    <el-form label-width="130px" class="config-form" v-loading="configLoading">
      <el-form-item label="API Key">
        <el-input
          v-model="securityForm.api_key"
          type="password"
          show-password
          placeholder="留空或保持脱敏值不变"
        />
      </el-form-item>

      <el-form-item label="启用接口鉴权">
        <el-switch v-model="securityForm.require_api_key" />
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-else-if="sectionKey === 'alist'" data-testid="config-section-alist" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>AList 配置</span>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="Token 字段支持脱敏保留；留空或保持脱敏值不变即可沿用当前 Token。"
      class="hint"
    />

    <el-form label-width="130px" class="config-form" v-loading="configLoading">
      <el-form-item label="启用 AList">
        <el-switch v-model="alistForm.enabled" />
      </el-form-item>

      <el-form-item label="服务地址">
        <el-input v-model="alistForm.url" :disabled="!alistForm.enabled" />
      </el-form-item>

      <el-form-item label="Token">
        <el-input
          v-model="alistForm.token"
          type="password"
          show-password
          :disabled="!alistForm.enabled"
          placeholder="留空或保持脱敏值不变"
        />
      </el-form-item>

      <el-form-item label="挂载路径">
        <el-input v-model="alistForm.mount_path" :disabled="!alistForm.enabled" />
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-else-if="sectionKey === 'tmdb'" data-testid="config-section-tmdb" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>TMDB 配置</span>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="TMDB API Key 支持脱敏保留；留空或保持脱敏值不变即可沿用当前密钥。"
      class="hint"
    />

    <el-form label-width="130px" class="config-form" v-loading="configLoading">
      <el-form-item label="API Key">
        <el-input
          v-model="tmdbForm.api_key"
          type="password"
          show-password
          placeholder="留空或保持脱敏值不变"
        />
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-else-if="sectionKey === 'log'" data-testid="config-section-log" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>日志配置</span>
      </div>
    </template>

    <el-form label-width="130px" class="config-form" v-loading="configLoading">
      <el-form-item label="输出格式">
        <el-select v-model="logForm.format">
          <el-option label="text" value="text" />
          <el-option label="json" value="json" />
        </el-select>
      </el-form-item>

      <el-form-item label="包含时间戳">
        <el-switch v-model="logForm.include_timestamp" />
      </el-form-item>

      <el-form-item label="包含日志级别">
        <el-switch v-model="logForm.include_level" />
      </el-form-item>

      <el-form-item label="包含请求 ID">
        <el-switch v-model="logForm.include_request_id" />
      </el-form-item>

      <el-form-item label="包含源码位置">
        <el-switch v-model="logForm.include_source" />
      </el-form-item>

      <el-form-item label="JSON 缩进">
        <el-input v-model="logForm.json_indent" placeholder="留空表示紧凑输出" :disabled="logForm.format !== 'json'" />
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-else-if="sectionKey === 'cors'" data-testid="config-section-cors" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>跨域设置</span>
      </div>
    </template>

    <el-form label-width="130px" class="config-form" v-loading="configLoading">
      <el-form-item label="允许来源">
        <el-input v-model="corsForm.allow_origins" type="textarea" :rows="4" placeholder="每行一个来源" />
      </el-form-item>

      <el-form-item label="允许凭证">
        <el-switch v-model="corsForm.allow_credentials" />
      </el-form-item>

      <el-form-item label="允许方法">
        <el-input v-model="corsForm.allow_methods" type="textarea" :rows="3" placeholder="每行一个方法" />
      </el-form-item>

      <el-form-item label="允许请求头">
        <el-input v-model="corsForm.allow_headers" type="textarea" :rows="3" placeholder="每行一个请求头" />
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-else-if="sectionKey === 'telegram'" data-testid="config-section-telegram" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>Telegram 通知</span>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="Bot Token 字段支持脱敏保留；留空或保持脱敏值不变即可沿用当前 Token。"
      class="hint"
    />

    <el-form label-width="130px" class="config-form" v-loading="configLoading">
      <el-form-item label="启用通知">
        <el-switch v-model="telegramForm.enabled" />
      </el-form-item>

      <el-form-item label="Bot Token">
        <el-input
          v-model="telegramForm.bot_token"
          type="password"
          show-password
          :disabled="!telegramForm.enabled"
          placeholder="留空或保持脱敏值不变"
        />
      </el-form-item>

      <el-form-item label="Chat ID">
        <el-input v-model="telegramForm.chat_id" :disabled="!telegramForm.enabled" />
      </el-form-item>

      <el-form-item label="代理地址">
        <el-input v-model="telegramForm.proxy" :disabled="!telegramForm.enabled" />
      </el-form-item>

      <el-form-item label="通知事件">
        <el-input
          v-model="telegramForm.events"
          type="textarea"
          :rows="3"
          :disabled="!telegramForm.enabled"
          placeholder="每行一个事件"
        />
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-else-if="sectionKey === 'wechat'" data-testid="config-section-wechat" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>微信通知</span>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="SendKey 字段支持脱敏保留；留空或保持脱敏值不变即可沿用当前密钥。"
      class="hint"
    />

    <el-form label-width="130px" class="config-form" v-loading="configLoading">
      <el-form-item label="启用通知">
        <el-switch v-model="wechatForm.enabled" />
      </el-form-item>

      <el-form-item label="Provider">
        <el-input v-model="wechatForm.provider" :disabled="!wechatForm.enabled" />
      </el-form-item>

      <el-form-item label="SendKey">
        <el-input
          v-model="wechatForm.send_key"
          type="password"
          show-password
          :disabled="!wechatForm.enabled"
          placeholder="留空或保持脱敏值不变"
        />
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-else-if="sectionKey === 'endpoints'" data-testid="config-section-endpoints" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>端点映射</span>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="当前先提供端点列表 JSON 编辑视图，保存时会写回 endpoints 数组。"
      class="hint"
    />

    <el-input
      v-model="endpointsFormModel"
      type="textarea"
      :rows="14"
      class="config-json-editor"
      v-loading="configLoading"
    />
  </el-card>

  <el-card v-else-if="sectionKey === 'ai'" data-testid="config-section-ai" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>AI Providers 配置</span>
        <el-button type="primary" size="small" @click="addProvider">添加 Provider</el-button>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="支持任意 OpenAI 兼容的 AI 模型。密钥字段默认脱敏展示，留空表示保持原值。"
      class="hint"
    />

    <el-form label-width="130px" class="config-form" v-loading="loading">
      <div v-for="(provider, idx) in providers" :key="idx" class="provider-section">
        <div class="provider-header">
          <h3>{{ provider.name }}</h3>
          <div class="provider-actions">
            <el-tag :type="provider.configured ? 'success' : 'info'" size="small">
              {{ provider.configured ? '已配置' : '未配置' }}
            </el-tag>
            <el-switch v-model="provider.enabled" active-text="启用" inactive-text="禁用" />
            <el-button type="danger" size="small" text @click="removeProvider(idx)">删除</el-button>
          </div>
        </div>

        <el-form-item label="Provider 名称">
          <el-input v-model="provider.name" placeholder="如: deepseek, openai" />
        </el-form-item>

        <el-form-item label="当前密钥状态">
          <el-input :model-value="provider.api_key_masked || '未配置'" readonly />
        </el-form-item>

        <el-form-item label="新 API 密钥">
          <el-input
            v-model="provider.api_key"
            type="password"
            show-password
            clearable
            placeholder="留空保持当前密钥不变"
          />
        </el-form-item>

        <el-form-item label="Base URL">
          <el-input v-model="provider.base_url" placeholder="https://api.example.com/v1" />
        </el-form-item>

        <el-form-item label="Model">
          <el-input v-model="provider.model" placeholder="模型名称" />
        </el-form-item>

        <el-form-item label="Timeout (秒)">
          <el-input-number v-model="provider.timeout" :min="1" :max="120" />
        </el-form-item>

        <el-form-item label="优先级">
          <el-input-number v-model="provider.priority" :min="0" :max="1000" />
          <span class="hint-text">数值越大优先级越高</span>
        </el-form-item>
      </div>

      <div class="form-actions">
        <el-button type="primary" @click="saveProviders" :loading="saving">保存配置</el-button>
        <el-button @click="loadProviders">重置</el-button>
      </div>
    </el-form>
  </el-card>

  <el-card v-else-if="sectionKey === 'webdav'" data-testid="config-section-webdav" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>WebDAV 配置</span>
      </div>
    </template>

    <el-form label-width="130px" class="config-form" v-loading="configLoading">
      <el-form-item label="启用 WebDAV">
        <el-switch v-model="webdavForm.enabled" />
      </el-form-item>

      <el-form-item label="启用兜底">
        <el-switch v-model="webdavForm.fallback_enabled" :disabled="!webdavForm.enabled" />
      </el-form-item>

      <el-form-item label="外部 URL">
        <el-input v-model="webdavForm.url" :disabled="!webdavForm.enabled" />
      </el-form-item>

      <el-form-item label="挂载路径">
        <el-input v-model="webdavForm.mount_path" :disabled="!webdavForm.enabled" />
      </el-form-item>

      <el-form-item label="用户名">
        <el-input v-model="webdavForm.username" :disabled="!webdavForm.enabled" />
      </el-form-item>

      <el-form-item label="密码">
        <el-input
          v-model="webdavForm.password"
          type="password"
          show-password
          :disabled="!webdavForm.enabled"
          placeholder="留空保持当前密码不变"
        />
      </el-form-item>

      <el-form-item label="只读模式">
        <el-switch v-model="webdavForm.read_only" :disabled="!webdavForm.enabled" />
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-else data-testid="config-section-placeholder" class="config-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span>{{ selectedGroupLabel }}</span>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      :title="`${selectedGroupLabel}暂未提供独立表单`"
      description="当前可继续通过下方 JSON 配置区编辑该分组；后续会逐步替换为结构化表单。"
    />
  </el-card>
</template>

<script setup lang="ts">
import EmbyConfigCard from '@/components/EmbyConfigCard.vue'
import type {
  AListForm,
  BasicForm,
  CorsForm,
  LogForm,
  QuarkForm,
  SecurityForm,
  TelegramForm,
  TmdbForm,
  WeChatForm,
  WebDAVForm,
} from '@/features/config/config-view-model'

interface ProviderForm {
  name: string
  api_key: string
  api_key_masked: string
  configured: boolean
  base_url: string
  model: string
  timeout: number
  enabled: boolean
  priority: number
}

defineProps<{
  sectionKey: string
  selectedGroupLabel: string
  loading: boolean
  saving: boolean
  configLoading: boolean
  providers: ProviderForm[]
  addProvider: () => void
  removeProvider: (index: number) => void
  saveProviders: () => void
  loadProviders: () => void
}>()

const basicForm = defineModel<BasicForm>('basicForm', { required: true })
const quarkForm = defineModel<QuarkForm>('quarkForm', { required: true })
const securityForm = defineModel<SecurityForm>('securityForm', { required: true })
const alistForm = defineModel<AListForm>('alistForm', { required: true })
const tmdbForm = defineModel<TmdbForm>('tmdbForm', { required: true })
const logForm = defineModel<LogForm>('logForm', { required: true })
const corsForm = defineModel<CorsForm>('corsForm', { required: true })
const telegramForm = defineModel<TelegramForm>('telegramForm', { required: true })
const wechatForm = defineModel<WeChatForm>('wechatForm', { required: true })
const webdavForm = defineModel<WebDAVForm>('webdavForm', { required: true })
const endpointsFormModel = defineModel<string>('endpointsFormJson', { required: true })
</script>
