/**
 * 智能重命名 API 封装
 * 
 * 提供增强的媒体重命名功能:
 * - 多算法选择
 * - Emby 规范命名
 * - 命名规则自定义
 */

import api from './index'

export interface NamingConfig {
  movie_template: string
  tv_episode_template: string
  specials_folder: string
  include_quality: boolean
  include_source: boolean
  include_codec: boolean
  include_tmdb_id: boolean
  sanitize_filenames: boolean
}

export interface SmartRenamePreviewRequest {
  target_path: string
  algorithm?: 'standard' | 'ai_enhanced' | 'ai_only'
  naming_standard?: 'emby' | 'plex' | 'kodi' | 'custom'
  recursive?: boolean
  create_folders?: boolean
  auto_confirm_high_confidence?: boolean
  high_confidence_threshold?: number
  ai_confidence_threshold?: number
  force_ai_parse?: boolean
  naming_config?: NamingConfig
}

export interface SmartRenameItem {
  original_path: string
  original_name: string
  new_path?: string
  new_name?: string
  media_type: string
  tmdb_id?: number
  tmdb_title?: string
  tmdb_year?: number
  season?: number
  episode?: number
  overall_confidence: number
  status: string
  needs_confirmation: boolean
  confirmation_reason?: string
  used_algorithm?: string
}

export interface SmartRenamePreviewResponse {
  batch_id: string
  target_path: string
  total_items: number
  parsed_items: number
  matched_items: number
  skipped_items: number
  needs_confirmation: number
  items: SmartRenameItem[]
  algorithm_used: string
  naming_standard: string
}

export interface SmartRenameExecuteRequest {
  batch_id: string
  operations?: Array<{
    original_path: string
    new_name: string
  }>
}

export interface SmartRenameExecuteResponse {
  batch_id: string
  total_items: number
  success_items: number
  failed_items: number
  skipped_items: number
}

export interface AlgorithmInfo {
  algorithm: string
  name: string
  description: string
  features: string[]
  recommended: boolean
}

export interface NamingStandardInfo {
  standard: string
  name: string
  description: string
  movie_example: string
  tv_example: string
  specials_example: string
}

export interface ValidationResponse {
  filename: string
  is_valid: boolean
  suggestions: string[]
  warnings: string[]
}

export interface SmartRenameStatus {
  available: boolean
  smart_rename_service: boolean
  tmdb_connected: boolean
  ai_available: boolean
  algorithms: string[]
  naming_standards: string[]
}

export interface AIConnectivityProviderResult {
  provider: 'kimi' | 'deepseek' | 'glm'
  configured: boolean
  connected: boolean
  model: string
  base_url: string
  response_time_ms: number | null
  message: string
}

export interface AIConnectivityResponse {
  success: boolean
  interface: string
  all_connected: boolean
  providers: AIConnectivityProviderResult[]
}

/**
 * 智能重命名预览
 */
export const previewSmartRename = (
  data: SmartRenamePreviewRequest
): Promise<SmartRenamePreviewResponse> => {
  return api.post('/smart-rename/preview', data)
}

/**
 * 执行智能重命名
 */
export const executeSmartRename = (
  data: SmartRenameExecuteRequest
): Promise<SmartRenameExecuteResponse> => {
  return api.post('/smart-rename/execute', data)
}

/**
 * 回滚智能重命名
 */
export const rollbackSmartRename = (
  batchId: string
): Promise<SmartRenameExecuteResponse> => {
  return api.post(`/smart-rename/rollback/${batchId}`)
}

/**
 * 获取可用算法列表
 */
export const getAlgorithms = (): Promise<AlgorithmInfo[]> => {
  return api.get('/smart-rename/algorithms')
}

/**
 * 获取可用命名标准列表
 */
export const getNamingStandards = (): Promise<NamingStandardInfo[]> => {
  return api.get('/smart-rename/naming-standards')
}

/**
 * 验证文件名
 */
export const validateFilename = (filename: string): Promise<ValidationResponse> => {
  return api.post('/smart-rename/validate', { filename })
}

/**
 * 获取智能重命名服务状态
 */
export const getSmartRenameStatus = (): Promise<SmartRenameStatus> => {
  return api.get('/smart-rename/status')
}

/**
 * 测试智能重命名（本地接口）AI连通性，固定测试 deepseek + glm
 */
export const testSmartRenameAIConnectivity = (
  timeoutSeconds: number = 30
): Promise<AIConnectivityResponse> => {
  return api.get('/smart-rename/ai-connectivity', {
    params: { timeout_seconds: timeoutSeconds }
  })
}

/**
 * 获取重命名批次列表
 */
export const getRenameBatches = (
  skip: number = 0,
  limit: number = 20
): Promise<any[]> => {
  return api.get('/smart-rename/batches', { params: { skip, limit } })
}

/**
 * 获取批次项目列表
 */
export const getBatchItems = (
  batchId: string,
  status?: string,
  skip: number = 0,
  limit: number = 50
): Promise<any[]> => {
  return api.get(`/smart-rename/batches/${batchId}/items`, {
    params: { status, skip, limit }
  })
}
