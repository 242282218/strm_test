import api from './index'

export type AIProvider = 'kimi' | 'deepseek' | 'glm'

export interface AIModelConfigItem {
  configured: boolean
  api_key_masked: string
  base_url: string
  model: string
  timeout: number
}

export interface AIModelsConfigResponse {
  kimi: AIModelConfigItem
  deepseek: AIModelConfigItem
  glm: AIModelConfigItem
}

export interface AIModelConfigUpdateItem {
  api_key: string
  base_url: string
  model: string
  timeout: number
}

export interface AIModelsConfigUpdateRequest {
  kimi: AIModelConfigUpdateItem
  deepseek: AIModelConfigUpdateItem
  glm: AIModelConfigUpdateItem
}

export interface QuarkConfigResponse {
  configured: boolean
  cookie_masked: string
  referer: string
  root_id: string
  only_video: boolean
}

export interface QuarkConfigUpdateRequest {
  cookie: string
  referer: string
  root_id: string
  only_video: boolean
}

export const getAIModelsConfig = (): Promise<AIModelsConfigResponse> => {
  return api.get('/system-config/ai-models')
}

export const updateAIModelsConfig = (
  data: AIModelsConfigUpdateRequest
): Promise<AIModelsConfigResponse> => {
  return api.post('/system-config/ai-models', data)
}

export const getQuarkConfig = (): Promise<QuarkConfigResponse> => {
  return api.get('/system-config/quark')
}

export const updateQuarkConfig = (data: QuarkConfigUpdateRequest): Promise<QuarkConfigResponse> => {
  return api.post('/system-config/quark', data)
}
