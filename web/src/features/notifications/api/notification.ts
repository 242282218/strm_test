import api from '../../../api/index'

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

export type SupportedNotificationChannel = 'telegram' | 'serverchan'

export interface FrontendNotificationConfig {
  enabled: boolean
  channel: SupportedNotificationChannel
  telegram: {
    bot_token: string
    chat_id: string
  }
  serverchan: {
    send_key: string
  }
}

export type FrontendNotificationInput = Pick<FrontendNotificationConfig, 'channel'> & Partial<FrontendNotificationConfig>

export const SUPPORTED_NOTIFICATION_CHANNELS: Array<{
  label: string
  value: SupportedNotificationChannel
}> = [
  { label: 'Telegram', value: 'telegram' },
  { label: 'ServerChan', value: 'serverchan' },
]

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

// 安全事件类型常量
export const SECURITY_EVENT_TYPES = {
  SECURITY_LOGIN_FAILED: 'security_login_failed',
  SECURITY_ACCOUNT_LOCKED: 'security_account_locked',
  SECURITY_UNAUTHORIZED_ACCESS: 'security_unauthorized_access',
  SECURITY_CONFIG_CHANGE: 'security_config_change',
  SECURITY_INJECTION_ATTEMPT: 'security_injection_attempt',
  SECURITY_ALERT: 'security_alert',
} as const

const SECURITY_EVENT_TYPE_VALUES = Object.values(SECURITY_EVENT_TYPES)

// 判断是否为安全事件
export const isSecurityEvent = (eventType: string): boolean => {
  return SECURITY_EVENT_TYPE_VALUES.some((value) => value === eventType)
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
export const convertFrontendToBackend = (
  config: FrontendNotificationInput
): { channel_type: SupportedNotificationChannel; channel_name: string; config: ChannelConfig } => {
  const channelMap: Record<string, string> = {
    telegram: 'Telegram',
    serverchan: 'ServerChan'
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
    case 'serverchan':
      backendConfig = {
        send_key: config.serverchan?.send_key
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
export const convertBackendToFrontend = (channel: Channel): FrontendNotificationConfig => {
  const config: FrontendNotificationConfig = {
    enabled: channel.is_enabled,
    channel: channel.channel_type as SupportedNotificationChannel,
    telegram: {
      bot_token: '',
      chat_id: ''
    },
    serverchan: {
      send_key: ''
    }
  }

  switch (channel.channel_type) {
    case 'telegram':
      config.telegram = {
        bot_token: channel.config.bot_token || '',
        chat_id: channel.config.chat_id || ''
      }
      break
    case 'serverchan':
      config.serverchan = {
        send_key: channel.config.send_key || ''
      }
      break
  }

  return config
}
