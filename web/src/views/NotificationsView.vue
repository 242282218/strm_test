<template>
  <div class="notifications-page">
    <div class="page-header">
      <div class="header-left">
        <h2>通知配置</h2>
        <el-tag v-if="currentChannel?.is_enabled" type="success" effect="dark" class="config-status">
          <el-icon><CircleCheck /></el-icon>
          已配置通知服务
        </el-tag>
        <el-tag v-else type="info" class="config-status">
          <el-icon><Warning /></el-icon>
          未配置
        </el-tag>
      </div>
      <div class="header-right">
        <el-button v-if="currentChannel" type="danger" @click="deleteConfig">
          <el-icon><Delete /></el-icon>
          删除配置
        </el-button>
        <el-button type="primary" :loading="saving" @click="saveConfig">
          <el-icon><Check /></el-icon>
          保存配置
        </el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <!-- 通知渠道配置 -->
      <el-col :span="12">
        <el-card shadow="never" class="config-card">
          <template #header>
            <div class="card-header">
              <span>通知渠道</span>
              <el-switch 
                v-model="config.enabled" 
                active-text="启用通知"
                :disabled="!currentChannel"
              />
            </div>
          </template>

          <el-form label-width="120px" :model="config">
            <el-form-item label="通知方式">
              <el-select v-model="config.channel" style="width: 100%" @change="onChannelChange">
                <el-option label="企业微信" value="wecom" />
                <el-option label="钉钉" value="dingtalk" />
                <el-option label="飞书" value="feishu" />
                <el-option label="Telegram" value="telegram" />
                <el-option label="邮件" value="email" />
                <el-option label="Webhook" value="webhook" />
              </el-select>
            </el-form-item>

            <!-- 企业微信配置 -->
            <template v-if="config.channel === 'wecom'">
              <el-form-item label="企业ID">
                <el-input v-model="config.wecom.corp_id" placeholder="wwxxxxxxxxxxxxxxxx" />
              </el-form-item>
              <el-form-item label="应用ID">
                <el-input v-model="config.wecom.agent_id" placeholder="1000002" />
              </el-form-item>
              <el-form-item label="应用密钥">
                <el-input v-model="config.wecom.secret" type="password" placeholder="应用Secret" show-password />
              </el-form-item>
              <el-form-item label="接收用户">
                <el-input v-model="config.wecom.touser" placeholder="@all 或用户ID，多个用|分隔" />
              </el-form-item>
            </template>

            <!-- 钉钉配置 -->
            <template v-if="config.channel === 'dingtalk'">
              <el-form-item label="Webhook">
                <el-input v-model="config.dingtalk.webhook" placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxx" />
              </el-form-item>
              <el-form-item label="加签密钥">
                <el-input v-model="config.dingtalk.secret" type="password" placeholder="可选，如设置了加签则必填" show-password />
              </el-form-item>
              <el-form-item label="@手机号">
                <el-input v-model="config.dingtalk.at_mobiles" placeholder="需要@的手机号，多个用,分隔" />
              </el-form-item>
            </template>

            <!-- 飞书配置 -->
            <template v-if="config.channel === 'feishu'">
              <el-form-item label="Webhook">
                <el-input v-model="config.feishu.webhook" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" />
              </el-form-item>
              <el-form-item label="加签密钥">
                <el-input v-model="config.feishu.secret" type="password" placeholder="可选" show-password />
              </el-form-item>
            </template>

            <!-- Telegram配置 -->
            <template v-if="config.channel === 'telegram'">
              <el-form-item label="Bot Token">
                <el-input v-model="config.telegram.bot_token" placeholder="123456789:ABCdefGHIjklMNOpqrSTUvwxyz" />
              </el-form-item>
              <el-form-item label="Chat ID">
                <el-input v-model="config.telegram.chat_id" placeholder="-1001234567890" />
              </el-form-item>
            </template>

            <!-- 邮件配置 -->
            <template v-if="config.channel === 'email'">
              <el-form-item label="SMTP服务器">
                <el-input v-model="config.email.smtp_server" placeholder="smtp.gmail.com" />
              </el-form-item>
              <el-form-item label="SMTP端口">
                <el-input-number v-model="config.email.smtp_port" :min="1" :max="65535" />
              </el-form-item>
              <el-form-item label="发件邮箱">
                <el-input v-model="config.email.from_addr" placeholder="sender@example.com" />
              </el-form-item>
              <el-form-item label="邮箱密码">
                <el-input v-model="config.email.password" type="password" show-password />
              </el-form-item>
              <el-form-item label="收件邮箱">
                <el-input v-model="config.email.to_addrs" placeholder="多个用,分隔" />
              </el-form-item>
              <el-form-item label="启用SSL">
                <el-switch v-model="config.email.use_ssl" />
              </el-form-item>
            </template>

            <!-- Webhook配置 -->
            <template v-if="config.channel === 'webhook'">
              <el-form-item label="Webhook URL">
                <el-input v-model="config.webhook.url" placeholder="https://example.com/webhook" />
              </el-form-item>
              <el-form-item label="请求方法">
                <el-radio-group v-model="config.webhook.method">
                  <el-radio-button label="POST">POST</el-radio-button>
                  <el-radio-button label="GET">GET</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="请求头">
                <el-input v-model="config.webhook.headers" type="textarea" :rows="3" placeholder='{"Authorization": "Bearer xxx"}' />
              </el-form-item>
            </template>
          </el-form>
        </el-card>
      </el-col>

      <!-- 测试通知 -->
      <el-col :span="12">
        <el-card shadow="never" class="config-card">
          <template #header>
            <span>测试通知</span>
          </template>
          <el-form>
            <el-form-item label="测试消息">
              <el-input v-model="testMessage" type="textarea" :rows="2" placeholder="输入测试消息内容" />
            </el-form-item>
            <el-form-item>
              <el-button 
                type="primary" 
                :loading="testing" 
                :disabled="!currentChannel || !currentChannel.is_enabled"
                @click="sendTest"
              >
                <el-icon><Promotion /></el-icon>
                发送测试
              </el-button>
              <span v-if="!currentChannel" class="form-tip ml-2">请先保存配置</span>
              <span v-else-if="!currentChannel.is_enabled" class="form-tip ml-2">请先启用通知</span>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="never" class="config-card mt-4">
          <template #header>
            <span>使用说明</span>
          </template>
          <el-alert
            title="配置说明"
            type="info"
            :closable="false"
            description="
1. 选择通知方式并填写对应配置
2. 点击保存配置
3. 启用通知开关
4. 点击发送测试验证配置是否正确
            "
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Warning, InfoFilled, Promotion, CircleCheck, Delete } from '@element-plus/icons-vue'
import {
  getChannels,
  createChannel,
  updateChannel,
  deleteChannel,
  testChannel,
  convertFrontendToBackend,
  convertBackendToFrontend,
  type Channel
} from '@/api/notification'

const testing = ref(false)
const saving = ref(false)
const testMessage = ref('这是一条测试消息，来自 Quark STRM 通知服务。')
const currentChannel = ref<Channel | null>(null)

const config = reactive({
  enabled: false,
  channel: 'telegram' as 'wecom' | 'dingtalk' | 'feishu' | 'telegram' | 'email' | 'webhook',
  wecom: {
    corp_id: '',
    agent_id: '',
    secret: '',
    touser: '@all'
  },
  dingtalk: {
    webhook: '',
    secret: '',
    at_mobiles: ''
  },
  feishu: {
    webhook: '',
    secret: ''
  },
  telegram: {
    bot_token: '',
    chat_id: ''
  },
  email: {
    smtp_server: '',
    smtp_port: 587,
    from_addr: '',
    password: '',
    to_addrs: '',
    use_ssl: true
  },
  webhook: {
    url: '',
    method: 'POST',
    headers: ''
  }
})

const onChannelChange = () => {
  // 切换渠道时，检查是否已有该渠道的配置
  loadChannelConfig()
}

const loadChannelConfig = async () => {
  try {
    const channels = await getChannels()
    const channel = channels.find(c => c.channel_type === config.channel)
    if (channel) {
      currentChannel.value = channel
      const frontendConfig = convertBackendToFrontend(channel)
      // 更新表单
      config.enabled = frontendConfig.enabled
      Object.assign(config[config.channel], frontendConfig[config.channel])
    } else {
      currentChannel.value = null
      config.enabled = false
    }
  } catch {
    ElMessage.error('加载配置失败')
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    const backendData = convertFrontendToBackend(config)
    
    if (currentChannel.value) {
      // 更新现有配置
      await updateChannel(currentChannel.value.id, {
        config: backendData.config,
        is_enabled: config.enabled
      })
    } else {
      // 创建新配置
      const newChannel = await createChannel(backendData)
      currentChannel.value = newChannel
    }
    
    ElMessage.success('配置已保存')
    await loadChannelConfig()
  } catch (error: any) {
    ElMessage.error(error.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const deleteConfig = async () => {
  if (!currentChannel.value) return
  
  try {
    await ElMessageBox.confirm('确定要删除该通知配置吗？', '确认', {
      type: 'warning'
    })
    await deleteChannel(currentChannel.value.id)
    ElMessage.success('配置已删除')
    currentChannel.value = null
    config.enabled = false
    // 重置当前渠道的配置
    resetChannelConfig(config.channel)
  } catch {
    // 用户取消
  }
}

const resetChannelConfig = (channel: string) => {
  switch (channel) {
    case 'wecom':
      config.wecom = { corp_id: '', agent_id: '', secret: '', touser: '@all' }
      break
    case 'dingtalk':
      config.dingtalk = { webhook: '', secret: '', at_mobiles: '' }
      break
    case 'feishu':
      config.feishu = { webhook: '', secret: '' }
      break
    case 'telegram':
      config.telegram = { bot_token: '', chat_id: '' }
      break
    case 'email':
      config.email = { smtp_server: '', smtp_port: 587, from_addr: '', password: '', to_addrs: '', use_ssl: true }
      break
    case 'webhook':
      config.webhook = { url: '', method: 'POST', headers: '' }
      break
  }
}

const sendTest = async () => {
  if (!currentChannel.value) {
    ElMessage.warning('请先保存配置')
    return
  }
  if (!currentChannel.value.is_enabled) {
    ElMessage.warning('请先启用通知')
    return
  }
  
  testing.value = true
  try {
    await testChannel(currentChannel.value.id)
    ElMessage.success('测试消息已发送')
  } catch (error: any) {
    ElMessage.error(error.message || '发送失败')
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadChannelConfig()
})
</script>

<style scoped>
.notifications-page {
  padding: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  gap: 8px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.config-status {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 28px;
}

.config-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mt-4 {
  margin-top: 16px;
}

.form-tip {
  font-size: 12px;
  color: var(--text-secondary);
}

.ml-2 {
  margin-left: 8px;
}
</style>
