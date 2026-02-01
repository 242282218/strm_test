/**
 * 媒体重命名API封装
 * 
 * 集成rename包的媒体重命名功能
 */

import api from './index'

export interface ParsedInfo {
  original_filename: string
  media_type: string
  title: string
  cleaned_title: string
  year?: number
  season?: number
  episode?: number
  resolution?: string
  codec?: string
  source?: string
  confidence: number
}

export interface TMDBMatch {
  title?: string
  year?: number
  confidence?: number
}

export interface RenameTask {
  source_path: string
  new_filename: string
  target_path?: string
  media_type: string
  title: string
  cleaned_title: string
  year?: number
  season?: number
  episode?: number
  resolution?: string
  codec?: string
  source?: string
  confidence: number
  needs_confirmation: boolean
  confirmation_reason?: string
  tmdb_match?: TMDBMatch
}

export interface ProgressMessage {
  message: string
  current: number
  total: number
}

export interface PreviewResponse {
  tasks: RenameTask[]
  progress: ProgressMessage[]
  total_tasks: number
  needs_confirmation: number
}

export interface RenameResultItem {
  source_path: string
  target_path?: string
  success: boolean
  error?: string
}

export interface ExecuteResponse {
  success_count: number
  failed_count: number
  success: RenameResultItem[]
  failed: RenameResultItem[]
}

export interface MediaInfo {
  original_filename: string
  media_type: string
  title: string
  cleaned_title: string
  year?: number
  season?: number
  episode?: number
  resolution?: string
  codec?: string
  source?: string
  confidence: number
}

export interface RenameStatus {
  available: boolean
  rename_service: boolean
}

/**
 * 预览重命名
 * 
 * @param data 预览参数
 * @returns 重命名任务列表
 */
export const previewRename = (data: {
  path: string
  recursive?: boolean
}): Promise<PreviewResponse> => {
  return api.post('/rename/preview', data)
}

/**
 * 执行重命名
 * 
 * @param data 执行参数
 * @returns 执行结果
 */
export const executeRename = (data: {
  path: string
  selected_tasks?: string[]
  recursive?: boolean
}): Promise<ExecuteResponse> => {
  return api.post('/rename/execute', data)
}

/**
 * 获取媒体文件信息
 * 
 * @param data 文件路径参数
 * @returns 媒体信息
 */
export const getMediaInfo = (data: {
  file_path: string
}): Promise<MediaInfo> => {
  return api.post('/rename/info', data)
}

/**
 * 获取重命名服务状态
 * 
 * @returns 重命名服务状态
 */
export const getRenameStatus = (): Promise<RenameStatus> => {
  return api.get('/rename/status')
}
