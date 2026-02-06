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

export const getAIModelsConfig = (): Promise<AIModelsConfigResponse> => {
  return api.get('/system-config/ai-models')
}

export const updateAIModelsConfig = (
  data: AIModelsConfigUpdateRequest
): Promise<AIModelsConfigResponse> => {
  return api.post('/system-config/ai-models', data)
}
