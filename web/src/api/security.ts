import api from './index'

// ==================== 类型定义 ====================

export interface SecurityEvent {
  id: number
  event_type: string
  severity: string
  status: string
  user_id?: number
  username?: string
  ip_address?: string
  user_agent?: string
  title: string
  description?: string
  details?: Record<string, unknown>
  request_path?: string
  request_method?: string
  acknowledged_by?: number
  acknowledged_at?: string
  resolved_by?: number
  resolved_at?: string
  resolution_note?: string
  created_at: string
  updated_at: string
}

export interface SecurityEventList {
  total: number
  events: SecurityEvent[]
}

export interface SecuritySummary {
  total_events: number
  by_type: Record<string, number>
  by_severity: Record<string, number>
  by_status: Record<string, number>
  suspicious_ips: Array<{
    id: number
    ip_address: string
    user_id?: number
    username?: string
    access_type: string
    success: number
    failed: number
    first_seen: string
    last_seen: string
    is_suspicious: boolean
    country?: string
    city?: string
  }>
  period_days: number
}

export interface EventType {
  value: string
  label: string
}

export interface Severity {
  value: string
  label: string
}

export interface Status {
  value: string
  label: string
}

// ==================== API 函数 ====================

/**
 * 获取安全事件列表
 */
export const getSecurityEvents = (params?: {
  limit?: number
  event_type?: string
  severity?: string
  status?: string
  user_id?: number
  ip_address?: string
}): Promise<SecurityEventList> => {
  return api.get('/security/events', { params })
}

/**
 * 获取单个安全事件详情
 */
export const getSecurityEvent = (eventId: number): Promise<SecurityEvent> => {
  return api.get(`/security/events/${eventId}`)
}

/**
 * 确认安全事件
 */
export const acknowledgeSecurityEvent = (
  eventId: number,
  note?: string
): Promise<SecurityEvent> => {
  return api.post(`/security/events/${eventId}/acknowledge`, { note })
}

/**
 * 解决安全事件
 */
export const resolveSecurityEvent = (
  eventId: number,
  note?: string
): Promise<SecurityEvent> => {
  return api.post(`/security/events/${eventId}/resolve`, { note })
}

/**
 * 标记为误报
 */
export const markFalsePositive = (
  eventId: number,
  note?: string
): Promise<SecurityEvent> => {
  return api.post(`/security/events/${eventId}/false-positive`, { note })
}

/**
 * 获取安全摘要统计
 */
export const getSecuritySummary = (days: number = 7): Promise<SecuritySummary> => {
  return api.get('/security/summary', { params: { days } })
}

/**
 * 获取所有事件类型
 */
export const getEventTypes = (): Promise<{ types: EventType[] }> => {
  return api.get('/security/event-types')
}

/**
 * 获取所有严重级别
 */
export const getSeverities = (): Promise<{ severities: Severity[] }> => {
  return api.get('/security/severities')
}

/**
 * 获取所有状态
 */
export const getStatuses = (): Promise<{ statuses: Status[] }> => {
  return api.get('/security/statuses')
}
