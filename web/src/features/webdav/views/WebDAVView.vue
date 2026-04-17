<template>
  <div class="workbench-page webdav-page">
    <section class="workbench-hero page-surface" data-testid="webdav-hero">
      <div class="workbench-main">
        <div class="workbench-toolbar">
          <div class="workbench-copy">
            <span class="workbench-chip">WebDAV Gateway</span>
            <h2 class="workbench-title">WebDAV 挂载、凭据状态与访问入口统一收口</h2>
            <p class="workbench-description">
              这个页面只处理 WebDAV 服务自身的启停、挂载路径与访问契约，保存后直接落到系统配置，避免继续停留在本地假动作。
            </p>
          </div>

          <div class="workbench-actions">
            <el-button :icon="Refresh" :loading="loading" @click="loadConfig()">刷新</el-button>
            <el-button
              type="primary"
              :loading="saving"
              data-testid="webdav-save-button"
              @click="saveConfig"
            >
              保存配置
            </el-button>
          </div>
        </div>

        <div class="workbench-metrics">
          <article
            v-for="metric in heroMetrics"
            :key="metric.label"
            class="workbench-metric"
          >
            <span class="workbench-metric-label">{{ metric.label }}</span>
            <strong class="workbench-metric-value">{{ metric.value }}</strong>
            <p class="workbench-metric-detail">{{ metric.detail }}</p>
          </article>
        </div>
      </div>

      <div class="workbench-side">
        <article class="workbench-side-card">
          <div class="workbench-side-head">
            <div class="workbench-side-heading">
              <span class="workbench-side-kicker">Access Summary</span>
              <h3 class="workbench-side-title">{{ form.enabled ? '当前访问入口' : '等待启用 WebDAV' }}</h3>
            </div>
          </div>

          <div class="hero-address-stack">
            <div class="hero-address-card">
              <span class="hero-address-label">外部访问地址</span>
              <strong class="hero-address-value">{{ externalWebdavUrl }}</strong>
            </div>
            <div v-if="showDevelopmentWebdavUrl" class="hero-address-card">
              <span class="hero-address-label">开发环境访问地址</span>
              <strong class="hero-address-value">{{ developmentWebdavUrl }}</strong>
            </div>
            <p v-else class="workbench-side-copy">
              当前挂载路径为 {{ normalizedMountPath }}，但前端开发代理固定为 /dav；若继续使用自定义路径，请同步调整 Vite 代理。
            </p>
          </div>
        </article>

        <article class="workbench-side-card">
          <div class="workbench-side-head">
            <div class="workbench-side-heading">
              <span class="workbench-side-kicker">Client Coverage</span>
              <h3 class="workbench-side-title">常用客户端</h3>
            </div>
          </div>

          <div class="hero-client-tags">
            <el-tag
              v-for="client in supportedClients"
              :key="client"
              effect="plain"
            >
              {{ client }}
            </el-tag>
          </div>
          <p class="workbench-side-copy">
            页面上方只保留入口和状态摘要，具体接入步骤与说明放在下方工作区，避免首屏重复堆砌。
          </p>
        </article>
      </div>
    </section>

    <div class="webdav-layout">
      <section class="workbench-section page-surface" data-testid="webdav-config-section">
        <div class="workbench-section-head">
          <div class="workbench-section-heading">
            <span class="workbench-section-kicker">Config</span>
            <h3 class="workbench-section-title">WebDAV 配置</h3>
            <p class="workbench-section-description">
              挂载路径、认证凭据和访问模式都在这里集中维护，保持与系统配置中的 `webdav` 契约一致。
            </p>
          </div>
        </div>

        <el-form label-width="140px" :model="form" :rules="rules" ref="formRef" class="webdav-form">
          <el-form-item label="启用 WebDAV">
            <el-switch v-model="form.enabled" />
          </el-form-item>

          <template v-if="form.enabled">
            <el-form-item label="挂载路径" prop="mount_path">
              <el-input v-model="form.mount_path" placeholder="/dav" />
              <p class="form-tip">后端 WebDAV 的挂载路径；当前前端开发代理固定使用 /dav，自定义路径时请同步调整代理配置。</p>
            </el-form-item>

            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" placeholder="请输入用户名" />
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
            </el-form-item>

            <el-form-item label="只读模式">
              <el-switch v-model="form.read_only" />
              <span class="form-tip inline-tip">启用后禁止写入操作。</span>
            </el-form-item>

            <el-form-item label="启用兜底">
              <el-switch v-model="form.fallback_enabled" />
              <span class="form-tip inline-tip">直链获取失败时降级到 WebDAV 播放。</span>
            </el-form-item>

            <el-form-item label="外部 URL" prop="url">
              <el-input v-model="form.url" placeholder="http://localhost:5244/dav" />
              <p class="form-tip">用于播放器和其它客户端访问的外部 WebDAV 地址。</p>
            </el-form-item>
          </template>
        </el-form>
      </section>

      <div class="webdav-side-stack">
        <section class="workbench-section page-surface" data-testid="webdav-connection-panel">
          <div class="workbench-section-head">
            <div class="workbench-section-heading">
              <span class="workbench-section-kicker">Connection</span>
              <h3 class="workbench-section-title">连接信息</h3>
              <p class="workbench-section-description">
                分开展示外部地址、开发地址和状态解释，避免把代理说明埋在表单提示里。
              </p>
            </div>
          </div>

          <div v-if="form.enabled" class="connection-info">
            <div class="info-item">
              <div class="info-label">外部访问地址</div>
              <div class="info-value">
                <el-input :model-value="externalWebdavUrl" readonly>
                  <template #append>
                    <el-button @click="copyExternalUrl">复制</el-button>
                  </template>
                </el-input>
              </div>
              <p class="form-tip">客户端可访问的地址；如果播放器或设备不在本机，请不要使用 localhost。</p>
            </div>

            <div v-if="showDevelopmentWebdavUrl" class="info-item">
              <div class="info-label">开发环境访问地址</div>
              <div class="info-value">
                <el-input :model-value="developmentWebdavUrl" readonly>
                  <template #append>
                    <el-button @click="copyDevelopmentUrl">复制</el-button>
                  </template>
                </el-input>
              </div>
              <p class="form-tip">仅用于本地前端开发环境，/dav 会由 Vite 代理到后端真实 WebDAV 服务。</p>
            </div>

            <div v-else class="info-item">
              <div class="info-label">开发环境代理提示</div>
              <p class="form-tip">
                当前挂载路径为 {{ normalizedMountPath }}，但开发代理固定为 /dav。若要通过前端开发服务器访问真实 WebDAV，请同步更新代理路径或恢复为 /dav。
              </p>
            </div>

            <div class="info-item">
              <div class="info-label">状态</div>
              <div class="info-value">
                <el-tag :type="webdavStatus.type">{{ webdavStatus.label }}</el-tag>
              </div>
              <p class="form-tip">{{ webdavStatus.description }}</p>
            </div>

            <div class="usage-card">
              <span class="info-label">使用说明</span>
              <ol class="usage-list">
                <li>在播放器或文件管理器中新增 WebDAV 连接。</li>
                <li>优先使用外部访问地址；本地联调时再使用开发环境地址。</li>
                <li>连接成功后即可浏览夸克网盘文件。</li>
                <li>播放视频时会自动 302 重定向到直链。</li>
              </ol>
            </div>
          </div>
          <el-empty v-else description="WebDAV 服务未启用" :image-size="84" />
        </section>

        <section class="workbench-section page-surface" data-testid="webdav-clients-panel">
          <div class="workbench-section-head">
            <div class="workbench-section-heading">
              <span class="workbench-section-kicker">Clients</span>
              <h3 class="workbench-section-title">支持的客户端</h3>
            </div>
          </div>

          <div class="client-list">
            <div
              v-for="client in supportedClients"
              :key="client"
              class="client-item"
            >
              <el-icon>
                <VideoCamera v-if="mediaClients.includes(client)" />
                <Folder v-else />
              </el-icon>
              <span>{{ client }}</span>
            </div>
          </div>
        </section>
      </div>
    </div>

    <section class="workbench-section page-surface" data-testid="webdav-capabilities-panel">
      <div class="workbench-section-head">
        <div class="workbench-section-heading">
          <span class="workbench-section-kicker">Capabilities</span>
          <h3 class="workbench-section-title">功能说明</h3>
          <p class="workbench-section-description">
            能力说明保留为只读契约卡片，避免表单和状态信息混在一起。
          </p>
        </div>
      </div>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="文件浏览">
          通过 WebDAV 协议浏览夸克网盘中的文件和目录
        </el-descriptions-item>
        <el-descriptions-item label="视频播放">
          播放视频时自动 302 重定向到夸克直链，实现流畅播放
        </el-descriptions-item>
        <el-descriptions-item label="缓存机制">
          文件列表缓存 5 分钟，减少 API 调用次数
        </el-descriptions-item>
        <el-descriptions-item label="兜底机制">
          直链获取失败时，自动生成 WebDAV URL 供播放器尝试
        </el-descriptions-item>
        <el-descriptions-item label="只读保护">
          默认只读模式，防止误操作修改网盘文件
        </el-descriptions-item>
        <el-descriptions-item label="认证安全">
          支持 Basic 和 Digest 认证，保护数据安全
        </el-descriptions-item>
      </el-descriptions>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, VideoCamera, Folder } from '@/components/icons'
import type { FormInstance, FormRules } from 'element-plus'
import { getSystemConfig, updateSystemConfig, type SystemConfigResponse } from '@/features/config/api/systemConfig'
import { createDefaultWebDAVForm, isRecord } from '@/features/config/config-view-model'

interface WebDAVConfig {
  enabled: boolean
  mount_path: string
  username: string
  password: string
  read_only: boolean
  fallback_enabled: boolean
  url: string
}

type HeroMetric = {
  label: string
  value: string
  detail: string
}

const supportedClients = ['Kodi', 'Infuse', 'VLC', 'RaiDrive', 'Mountain Duck', 'Windows 资源管理器']
const mediaClients = ['Kodi', 'Infuse', 'VLC']

const formRef = ref<FormInstance>()
const saving = ref(false)
const loading = ref(false)
const currentConfig = ref<SystemConfigResponse>({})

const form = reactive<WebDAVConfig>(createDefaultWebDAVForm())

const rules: FormRules = {
  mount_path: [
    { required: true, message: '请输入挂载路径', trigger: 'blur' },
    { pattern: /^\/.*/, message: '路径必须以 / 开头', trigger: 'blur' }
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  url: [
    { required: true, message: '请输入外部 URL', trigger: 'blur' },
    { type: 'url', message: '请输入有效的 URL', trigger: 'blur' }
  ]
}

const normalizedMountPath = computed(() => {
  const mountPath = form.mount_path.trim()
  return mountPath || '/dav'
})

const developmentProxyPath = '/dav'

const showDevelopmentWebdavUrl = computed(() => normalizedMountPath.value === developmentProxyPath)

const developmentWebdavUrl = computed(() => {
  return `${window.location.origin}${developmentProxyPath}`
})

const externalWebdavUrl = computed(() => form.url.trim() || developmentWebdavUrl.value)

const webdavStatus = computed(() => {
  if (!form.enabled) {
    return {
      type: 'info' as const,
      label: '未启用',
      description: '当前仅保存了预配置，后端不会挂载 WebDAV 服务。'
    }
  }

  const hasCredentials = form.username.trim().length > 0 && form.password.trim().length > 0
  if (!hasCredentials) {
    return {
      type: 'warning' as const,
      label: '配置不完整',
      description: '已开启 WebDAV，但缺少用户名或密码，后端初始化仍会失败。'
    }
  }

  return {
    type: 'success' as const,
    label: '已启用',
    description: showDevelopmentWebdavUrl.value
      ? '凭据已填写；开发环境中的 /dav 会代理到后端真实 WebDAV 入口。'
      : '凭据已填写；当前挂载路径已启用，但若使用了自定义路径，请同步调整前端开发代理配置。'
  }
})

const heroMetrics = computed<HeroMetric[]>(() => {
  return [
    {
      label: '服务状态',
      value: webdavStatus.value.label,
      detail: webdavStatus.value.description
    },
    {
      label: '挂载路径',
      value: normalizedMountPath.value,
      detail: showDevelopmentWebdavUrl.value ? '与开发代理路径保持一致。' : '已偏离默认 /dav，需要同步代理配置。'
    },
    {
      label: '访问模式',
      value: form.read_only ? '只读' : '可写',
      detail: form.read_only ? '更适合播放器和浏览场景。' : '允许写操作，需自行评估风险。'
    },
    {
      label: '兜底策略',
      value: form.fallback_enabled ? '已开启' : '已关闭',
      detail: form.fallback_enabled ? '直链失效时可回退到 WebDAV。' : '直链失败后不会自动回退。'
    }
  ]
})

const applyWebdavConfig = (config: SystemConfigResponse): void => {
  currentConfig.value = config
  Object.assign(form, createDefaultWebDAVForm())

  const webdav = config.webdav
  if (!isRecord(webdav)) {
    return
  }

  form.enabled = Boolean(webdav.enabled)
  form.fallback_enabled = webdav.fallback_enabled !== false
  form.url = typeof webdav.url === 'string' && webdav.url ? webdav.url : 'http://localhost:5244/dav'
  form.username = typeof webdav.username === 'string' ? webdav.username : ''
  form.password = typeof webdav.password === 'string' ? webdav.password : ''
  form.mount_path = typeof webdav.mount_path === 'string' && webdav.mount_path ? webdav.mount_path : '/dav'
  form.read_only = webdav.read_only !== false
}

const buildPayload = (): SystemConfigResponse => {
  return {
    ...currentConfig.value,
    webdav: {
      enabled: form.enabled,
      fallback_enabled: form.fallback_enabled,
      url: externalWebdavUrl.value,
      username: form.username.trim(),
      password: form.password,
      mount_path: normalizedMountPath.value,
      read_only: form.read_only
    }
  }
}

const loadConfig = async (notify = true): Promise<void> => {
  loading.value = true
  try {
    const config = await getSystemConfig()
    applyWebdavConfig(config)
    if (notify) {
      ElMessage.success('配置已加载')
    }
  } catch {
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

const saveConfig = async (): Promise<void> => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const updatedConfig = await updateSystemConfig(buildPayload())
    applyWebdavConfig(updatedConfig)
    ElMessage.success('配置已保存')
  } catch {
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

const copyExternalUrl = (): void => {
  navigator.clipboard.writeText(externalWebdavUrl.value)
  ElMessage.success('已复制外部访问地址')
}

const copyDevelopmentUrl = (): void => {
  navigator.clipboard.writeText(developmentWebdavUrl.value)
  ElMessage.success('已复制开发环境访问地址')
}

onMounted(() => {
  void loadConfig(false)
})
</script>

<style scoped>
.webdav-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(320px, 0.9fr);
  gap: var(--page-section-gap);
}

.webdav-side-stack {
  display: flex;
  flex-direction: column;
  gap: var(--page-section-gap);
}

.hero-address-stack,
.connection-info {
  display: grid;
  gap: 16px;
}

.hero-address-card,
.usage-card {
  padding: 16px 18px;
  border-radius: var(--radius-md);
  background: rgba(79, 141, 246, 0.08);
  border: 1px solid rgba(79, 141, 246, 0.16);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.hero-address-label,
.info-label,
.form-tip {
  color: var(--text-tertiary);
  font-size: 12px;
}

.hero-address-value {
  font-size: 0.96rem;
  font-weight: var(--font-semibold);
  word-break: break-all;
}

.webdav-form,
.usage-list {
  margin-top: 20px;
}

.inline-tip {
  margin-left: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-value {
  font-size: 14px;
}

.usage-list {
  padding-left: 18px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.client-list {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.client-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--bg-soft);
  border-radius: 10px;
  border: 1px solid var(--border-light);
}

.client-item .el-icon {
  color: var(--primary-color);
}

.hero-client-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 1080px) {
  .webdav-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .client-list {
    grid-template-columns: 1fr;
  }

  .inline-tip {
    display: block;
    margin: 8px 0 0;
  }
}
</style>
