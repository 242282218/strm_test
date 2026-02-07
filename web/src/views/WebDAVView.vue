<template>
  <div class="webdav-page">
    <div class="page-header">
      <h2>WebDAV 挂载</h2>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="loadConfig">刷新</el-button>
        <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="16">
        <el-card shadow="never" class="card">
          <template #header>WebDAV 配置</template>
          <el-form label-width="140px" :model="form" :rules="rules" ref="formRef">
            <el-form-item label="启用 WebDAV">
              <el-switch v-model="form.enabled" />
            </el-form-item>

            <template v-if="form.enabled">
              <el-form-item label="挂载路径" prop="mount_path">
                <el-input v-model="form.mount_path" placeholder="/dav" />
                <div class="form-tip">WebDAV 服务的 URL 路径</div>
              </el-form-item>

              <el-form-item label="用户名" prop="username">
                <el-input v-model="form.username" placeholder="admin" />
              </el-form-item>

              <el-form-item label="密码" prop="password">
                <el-input v-model="form.password" type="password" placeholder="password" show-password />
              </el-form-item>

              <el-form-item label="只读模式">
                <el-switch v-model="form.read_only" />
                <div class="form-tip">启用后禁止写入操作</div>
              </el-form-item>

              <el-form-item label="启用兜底">
                <el-switch v-model="form.fallback_enabled" />
                <div class="form-tip">直链获取失败时降级到 WebDAV 播放</div>
              </el-form-item>

              <el-form-item label="外部 URL" prop="url">
                <el-input v-model="form.url" placeholder="http://localhost:5244/dav" />
                <div class="form-tip">用于兜底机制的外部 WebDAV 地址</div>
              </el-form-item>
            </template>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never" class="card">
          <template #header>连接信息</template>
          <div v-if="form.enabled" class="connection-info">
            <div class="info-item">
              <div class="info-label">服务地址</div>
              <div class="info-value">
                <el-input v-model="webdavUrl" readonly>
                  <template #append>
                    <el-button @click="copyUrl">复制</el-button>
                  </template>
                </el-input>
              </div>
            </div>

            <div class="info-item">
              <div class="info-label">状态</div>
              <div class="info-value">
                <el-tag type="success">运行中</el-tag>
              </div>
            </div>

            <el-divider />

            <h4>使用说明</h4>
            <ol class="usage-list">
              <li>在文件管理器或播放器中添加 WebDAV 连接</li>
              <li>输入上述服务地址、用户名和密码</li>
              <li>连接成功后即可浏览夸克网盘文件</li>
              <li>播放视频时会自动 302 重定向到直链</li>
            </ol>
          </div>
          <el-empty v-else description="WebDAV 服务未启用" :image-size="84" />
        </el-card>

        <el-card shadow="never" class="card mt-4">
          <template #header>支持的客户端</template>
          <div class="client-list">
            <div class="client-item">
              <el-icon><VideoCamera /></el-icon>
              <span>Kodi</span>
            </div>
            <div class="client-item">
              <el-icon><VideoCamera /></el-icon>
              <span>Infuse</span>
            </div>
            <div class="client-item">
              <el-icon><VideoCamera /></el-icon>
              <span>VLC</span>
            </div>
            <div class="client-item">
              <el-icon><Folder /></el-icon>
              <span>RaiDrive</span>
            </div>
            <div class="client-item">
              <el-icon><Folder /></el-icon>
              <span>Mountain Duck</span>
            </div>
            <div class="client-item">
              <el-icon><Folder /></el-icon>
              <span>Windows 资源管理器</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt-4">
      <el-col :span="24">
        <el-card shadow="never" class="card">
          <template #header>功能说明</template>
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
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, VideoCamera, Folder } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

interface WebDAVConfig {
  enabled: boolean
  mount_path: string
  username: string
  password: string
  read_only: boolean
  fallback_enabled: boolean
  url: string
}

const formRef = ref<FormInstance>()
const saving = ref(false)
const loading = ref(false)

const form = reactive<WebDAVConfig>({
  enabled: true,
  mount_path: '/dav',
  username: 'admin',
  password: 'password',
  read_only: true,
  fallback_enabled: true,
  url: 'http://localhost:5244/dav'
})

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

const webdavUrl = computed(() => {
  const baseUrl = window.location.origin
  return `${baseUrl}${form.mount_path}`
})

const loadConfig = async () => {
  loading.value = true
  try {
    // TODO: 从后端加载配置
    // const config = await getWebDAVConfig()
    // Object.assign(form, config)
    ElMessage.success('配置已加载')
  } catch (error: unknown) {
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    saving.value = true
    try {
      // TODO: 保存到后端
      // await saveWebDAVConfig(form)
      ElMessage.success('配置已保存')
    } catch (error: unknown) {
      ElMessage.error('保存配置失败')
    } finally {
      saving.value = false
    }
  })
}

const copyUrl = () => {
  navigator.clipboard.writeText(webdavUrl.value)
  ElMessage.success('已复制到剪贴板')
}
</script>

<style scoped>
.webdav-page {
  padding: 8px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.card {
  margin-bottom: 16px;
}

.mt-4 {
  margin-top: 16px;
}

.form-tip {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.connection-info {
  padding: 8px 0;
}

.info-item {
  margin-bottom: 16px;
}

.info-label {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.info-value {
  font-size: 14px;
}

.usage-list {
  padding-left: 20px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.usage-list li {
  margin-bottom: 8px;
}

.client-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.client-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  font-size: 14px;
}

.client-item .el-icon {
  color: var(--primary-color);
}
</style>
