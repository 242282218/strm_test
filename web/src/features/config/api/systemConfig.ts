import api from '@/api/index'

export type SystemConfigResponse = Record<string, unknown>

export const getSystemConfig = (): Promise<SystemConfigResponse> => {
  return api.get('/system-config/')
}

export interface SystemConfigMetadataResponse {
  schema: Record<string, unknown>
  sensitive_fields: string[]
  sensitive_fields_status: Record<string, boolean>
}

export const getSystemConfigMetadata = (): Promise<SystemConfigMetadataResponse> => {
  return api.get('/system-config/metadata')
}

export const updateSystemConfig = (data: SystemConfigResponse): Promise<SystemConfigResponse> => {
  return api.post('/system-config/', data)
}

// 新格式 AI Providers API
export interface AIProviderItem {
  name: string
  api_key_masked: string
  configured: boolean
  base_url: string
  model: string
  timeout: number
  enabled: boolean
  priority: number
}

export interface AIProvidersResponse {
  providers: AIProviderItem[]
}

export interface AIProviderUpdateItem {
  name: string
  api_key: string
  base_url: string
  model: string
  timeout: number
  enabled: boolean
  priority: number
}

export interface AIProvidersUpdateRequest {
  providers: AIProviderUpdateItem[]
}

export const getAIProviders = (): Promise<AIProvidersResponse> => {
  return api.get('/system-config/ai-providers')
}

export const updateAIProviders = (
  data: AIProvidersUpdateRequest
): Promise<AIProvidersResponse> => {
  return api.post('/system-config/ai-providers', data)
}
