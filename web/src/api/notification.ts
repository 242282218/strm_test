import api from './index'

export interface ChannelConfig {
  bot_token?: string
  chat_id?: string
  device_key?: string
  send_key?: string
  webhook_url?: string
  corp_id?: string
  agent_id?: string
  secret?: string
  touser?: string
  at_mobiles?: string
  smtp_server?: string
  smtp_port?: number
  from_addr?: string
  password?: string
  to_addrs?: string
  use_ssl?: boolean
  url?: string
  method?: string
  headers?: string
}

export interface Channel {
  id: number
  channel_type: string
  channel_name: string
  is_enabled: boolean
  config: ChannelConfig
}

export interface ChannelCreate {
  channel_type: string
  channel_name: string
  config: ChannelConfig
}

export interface ChannelUpdate {
  channel_name?: string
  config?: ChannelConfig
  is_enabled?: boolean
}

export interface Rule {
  id: number
  channel_id: number
  event_type: string
  keywords?: string
  is_enabled: boolean
}

export interface RuleCreate {
  channel_id: number
  event_type: string
  keywords?: string
}

export interface Log {
  id: number
  channel_id?: number
  channel_name?: string
  event_type: string
  title?: string
  status: string
  error_message?: string
  created_at: string
}

/**
 * 获取所有通知渠道
 */
export const getChannels = (): Promise<Channel[]> => {
  return api.get('/notification/channels')
}

/**
 * 创建通知渠道
 */
export const createChannel = (data: ChannelCreate): Promise<Channel> => {
  return api.post('/notification/channels', data)
}

/**
 * 更新通知渠道
 */
export const updateChannel = (id: number, data: ChannelUpdate): Promise<Channel> => {
  return api.put(`/notification/channels/${id}`, data)
}

/**
 * 删除通知渠道
 */
export const deleteChannel = (id: number): Promise<{ status: string }> => {
  return api.delete(`/notification/channels/${id}`)
}

/**
 * 测试通知渠道
 */
export const testChannel = (id: number): Promise<{ status: string }> => {
  return api.post(`/notification/channels/${id}/test`)
}

/**
 * 获取所有通知规则
 */
export const getRules = (): Promise<Rule[]> => {
  return api.get('/notification/rules')
}

/**
 * 创建通知规则
 */
export const createRule = (data: RuleCreate): Promise<Rule> => {
  return api.post('/notification/rules', data)
}

/**
 * 删除通知规则
 */
export const deleteRule = (id: number): Promise<{ status: string }> => {
  return api.delete(`/notification/rules/${id}`)
}

/**
 * 获取通知日志
 */
export const getLogs = (limit: number = 50): Promise<Log[]> => {
  return api.get('/notification/logs', { params: { limit } })
}

/**
 * 将前端配置格式转换为后端格式
 */
export const convertFrontendToBackend = (config: any): { channel_type: string; channel_name: string; config: ChannelConfig } => {
  const channelMap: Record<string, string> = {
    telegram: 'Telegram',
    wecom: '企业微信',
    dingtalk: '钉钉',
    feishu: '飞书',
    email: '邮件',
    webhook: 'Webhook'
  }

  const channelType = config.channel
  const channelName = channelMap[channelType] || channelType

  let backendConfig: ChannelConfig = {}

  switch (channelType) {
    case 'telegram':
      backendConfig = {
        bot_token: config.telegram?.bot_token,
        chat_id: config.telegram?.chat_id
      }
      break
    case 'wecom':
      backendConfig = {
        corp_id: config.wecom?.corp_id,
        agent_id: config.wecom?.agent_id,
        secret: config.wecom?.secret,
        touser: config.wecom?.touser
      }
      break
    case 'dingtalk':
      backendConfig = {
        webhook_url: config.dingtalk?.webhook,
        secret: config.dingtalk?.secret,
        at_mobiles: config.dingtalk?.at_mobiles
      }
      break
    case 'feishu':
      backendConfig = {
        webhook_url: config.feishu?.webhook,
        secret: config.feishu?.secret
      }
      break
    case 'email':
      backendConfig = {
        smtp_server: config.email?.smtp_server,
        smtp_port: config.email?.smtp_port,
        from_addr: config.email?.from_addr,
        password: config.email?.password,
        to_addrs: config.email?.to_addrs,
        use_ssl: config.email?.use_ssl
      }
      break
    case 'webhook':
      backendConfig = {
        webhook_url: config.webhook?.url,
        method: config.webhook?.method,
        headers: config.webhook?.headers
      }
      break
  }

  return {
    channel_type: channelType,
    channel_name: channelName,
    config: backendConfig
  }
}

/**
 * 将后端配置格式转换为前端格式
 */
export const convertBackendToFrontend = (channel: Channel): any => {
  const config: any = {
    enabled: channel.is_enabled,
    channel: channel.channel_type
  }

  switch (channel.channel_type) {
    case 'telegram':
      config.telegram = {
        bot_token: channel.config.bot_token || '',
        chat_id: channel.config.chat_id || ''
      }
      break
    case 'wecom':
      config.wecom = {
        corp_id: channel.config.corp_id || '',
        agent_id: channel.config.agent_id || '',
        secret: channel.config.secret || '',
        touser: channel.config.touser || '@all'
      }
      break
    case 'dingtalk':
      config.dingtalk = {
        webhook: channel.config.webhook_url || '',
        secret: channel.config.secret || '',
        at_mobiles: channel.config.at_mobiles || ''
      }
      break
    case 'feishu':
      config.feishu = {
        webhook: channel.config.webhook_url || '',
        secret: channel.config.secret || ''
      }
      break
    case 'email':
      config.email = {
        smtp_server: channel.config.smtp_server || '',
        smtp_port: channel.config.smtp_port || 587,
        from_addr: channel.config.from_addr || '',
        password: channel.config.password || '',
        to_addrs: channel.config.to_addrs || '',
        use_ssl: channel.config.use_ssl ?? true
      }
      break
    case 'webhook':
      config.webhook = {
        url: channel.config.webhook_url || '',
        method: channel.config.method || 'POST',
        headers: channel.config.headers || ''
      }
      break
  }

  return config
}
