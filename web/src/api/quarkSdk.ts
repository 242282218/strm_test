/**
 * 基于SDK的夸克API封装
 * 
 * 提供与现有API兼容的接口，同时支持SDK新功能
 */

import api from './index'

export interface QuarkFileSDK {
  fid: string
  file_name: string
  category: number
  file: boolean
  dir?: boolean
  size?: number
  created_at?: number
  updated_at?: number
  mime_type?: string
}

export interface DownloadLink {
  url: string
  headers: Record<string, string>
  concurrency: number
  part_size: number
}

export interface TranscodingLink {
  url: string
  content_length: number
  headers: Record<string, string>
  concurrency: number
  part_size: number
}

export interface ShareInfo {
  share_id: string
  share_key: string
  url: string
  password?: string
  title?: string
  expires_at?: string
}

export interface TransferResult {
  task_id: string
  status: string
  message?: string
}

export interface SDKStatus {
  available: boolean
  sdk_path: string
}

/**
 * 获取文件列表（SDK版本）
 */
export const getQuarkFilesSDK = (
  parent: string = '0',
  pageSize: number = 100,
  onlyVideo: boolean = false
): Promise<{ files: QuarkFileSDK[]; count: number }> => {
  return api.get(`/quark-sdk/files/${parent}`, {
    params: { page_size: pageSize, only_video: onlyVideo }
  })
}

/**
 * 获取下载直链（SDK版本）
 */
export const getDownloadLinkSDK = (fileId: string): Promise<DownloadLink> => {
  return api.get(`/quark-sdk/link/${fileId}`)
}

/**
 * 获取转码直链（SDK版本）
 */
export const getTranscodingLinkSDK = (fileId: string): Promise<TranscodingLink> => {
  return api.get(`/quark-sdk/transcoding/${fileId}`)
}

/**
 * 创建分享（新功能）
 */
export const createShare = (data: {
  file_ids: string[]
  title?: string
  password?: string
}): Promise<ShareInfo> => {
  return api.post('/quark-sdk/share', data)
}

/**
 * 转存分享文件（新功能）
 */
export const saveShare = (data: {
  share_key: string
  file_ids: string[]
  target_folder?: string
  password?: string
}): Promise<TransferResult> => {
  return api.post('/quark-sdk/transfer', data)
}

/**
 * 搜索文件（新功能）
 */
export const searchFiles = (
  keyword: string,
  parent: string = '0',
  pageSize: number = 50
): Promise<{ files: QuarkFileSDK[]; count: number }> => {
  return api.get('/quark-sdk/search', {
    params: { keyword, parent, page_size: pageSize }
  })
}

/**
 * 获取SDK状态
 */
export const getSDKStatus = (): Promise<SDKStatus> => {
  return api.get('/quark-sdk/status')
}
