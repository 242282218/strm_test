/**
 * 夸克云盘 API 客户端
 *
 * 用途: 提供夸克云盘相关的 API 调用，包括文件浏览和智能重命名功能
 */

import api from './index'

// ========== 类型定义 ==========

/**
 * 浏览目录请求参数
 */
export interface QuarkBrowseRequest {
  /** 父目录ID，默认为"0"（根目录） */
  pdir_fid: string
  /** 页码，从1开始 */
  page: number
  /** 每页数量 */
  size: number
  /** 文件类型过滤：video/folder/all */
  file_type?: 'video' | 'folder' | 'all'
}

/**
 * 夸克文件项
 */
export interface QuarkFileItem {
  /** 文件/文件夹唯一ID */
  fid: string
  /** 文件/文件夹名称 */
  file_name: string
  /** 父目录ID */
  pdir_fid: string
  /** 类型：0=文件夹, 1=文件 */
  file_type: number
  /** 文件大小（字节），文件夹为0 */
  size: number
  /** 创建时间（Unix时间戳） */
  created_at: number
  /** 更新时间（Unix时间戳） */
  updated_at: number
  /** 分类：folder/video/document等 */
  category?: string
}

/**
 * 浏览目录响应
 */
export interface QuarkBrowseResponse {
  status: number
  data: {
    items: QuarkFileItem[]
    total: number
    page: number
    size: number
  }
}

/**
 * 智能重命名选项
 */
export interface QuarkRenameOptions {
  /** 是否递归处理子目录 */
  recursive?: boolean
  /** 是否创建文件夹结构 */
  create_folders?: boolean
  /** 自动确认高置信度匹配 */
  auto_confirm_high_confidence?: boolean
  /** AI解析置信度阈值 */
  ai_confidence_threshold?: number
}

/**
 * 云盘智能重命名请求
 */
export interface QuarkSmartRenameRequest {
  /** 目标目录ID */
  pdir_fid: string
  /** 算法：standard/ai_enhanced/ai_only */
  algorithm: 'standard' | 'ai_enhanced' | 'ai_only'
  /** 命名标准：emby/plex/kodi */
  naming_standard: 'emby' | 'plex' | 'kodi'
  /** 是否强制使用AI解析 */
  force_ai_parse?: boolean
  /** 高级选项 */
  options?: QuarkRenameOptions
}

/**
 * 云盘重命名项目
 */
export interface QuarkRenameItem {
  /** 文件ID */
  fid: string
  /** 原文件名 */
  original_name: string
  /** 新文件名 */
  new_name: string
  /** TMDB ID */
  tmdb_id?: number
  /** TMDB标题 */
  tmdb_title?: string
  /** TMDB年份 */
  tmdb_year?: number
  /** 媒体类型：movie/tv/anime */
  media_type: string
  /** 季数 */
  season?: number
  /** 集数 */
  episode?: number
  /** 总体置信度 */
  overall_confidence: number
  /** 使用的算法 */
  used_algorithm: string
  /** 是否需要确认 */
  needs_confirmation: boolean
  /** 需要确认的原因 */
  confirmation_reason?: string
  /** 状态 */
  status: string
}

/**
 * 云盘智能重命名响应
 */
export interface QuarkSmartRenameResponse {
  status: number
  data: {
    /** 批次ID */
    batch_id: string
    /** 目标目录ID */
    pdir_fid: string
    /** 总文件数 */
    total_items: number
    /** 成功匹配的文件数 */
    matched_items: number
    /** 已解析的文件数 */
    parsed_items: number
    /** 需要确认的文件数 */
    needs_confirmation: number
    /** 平均置信度 */
    average_confidence: number
    /** 使用的算法 */
    algorithm_used: string
    /** 命名标准 */
    naming_standard: string
    /** 文件列表 */
    items: QuarkRenameItem[]
    /** 提示信息 */
    message?: string
  }
}

/**
 * 重命名操作
 */
export interface QuarkRenameOperation {
  /** 文件ID */
  fid: string
  /** 新文件名 */
  new_name: string
}

/**
 * 执行云盘重命名请求
 */
export interface QuarkRenameExecuteRequest {
  /** 批次ID */
  batch_id: string
  /** 重命名操作列表 */
  operations: QuarkRenameOperation[]
}

/**
 * 执行结果项
 */
export interface QuarkRenameResult {
  /** 文件ID */
  fid: string
  /** 状态：success/failed */
  status: string
  /** 新文件名（成功时） */
  new_name?: string
  /** 错误信息（失败时） */
  error?: string
}

/**
 * 执行云盘重命名响应
 */
export interface QuarkRenameExecuteResponse {
  status: number
  data: {
    /** 批次ID */
    batch_id: string
    /** 总操作数 */
    total: number
    /** 成功数量 */
    success: number
    /** 失败数量 */
    failed: number
    /** 每个操作的结果 */
    results: QuarkRenameResult[]
  }
}

// ========== API 函数 ==========

/**
 * 浏览夸克云盘目录
 *
 * 用途: 获取指定目录下的文件和文件夹列表
 * 输入: QuarkBrowseRequest 请求参数
 * 输出: QuarkBrowseResponse 响应数据
 * 副作用: 无
 *
 * @param params 浏览请求参数
 * @returns 文件列表响应
 */
export async function browseQuarkDirectory(
  params: QuarkBrowseRequest
): Promise<QuarkBrowseResponse['data']> {
  const response = await api.get<any>('/quark/browse', {
    params: {
      pdir_fid: params.pdir_fid,
      page: params.page,
      size: params.size,
      file_type: params.file_type || 'all'
    }
  })
  return response.data
}

/**
 * 智能重命名云盘文件（预览）
 *
 * 用途: 对夸克云盘中的文件进行智能重命名预览
 * 输入: QuarkSmartRenameRequest 请求参数
 * 输出: QuarkSmartRenameResponse 响应数据
 * 副作用: 无（仅预览，不修改云盘文件）
 *
 * @param params 智能重命名请求参数
 * @returns 预览结果
 */
export async function smartRenameCloudFiles(
  params: QuarkSmartRenameRequest
): Promise<QuarkSmartRenameResponse['data']> {
  const response = await api.post<any>('/quark/smart-rename-cloud', params)
  return response.data
}

/**
 * 执行云盘文件重命名
 *
 * 用途: 批量执行夸克云盘文件重命名操作
 * 输入: QuarkRenameExecuteRequest 请求参数
 * 输出: QuarkRenameExecuteResponse 响应数据
 * 副作用: 修改云盘中的文件名
 *
 * @param params 执行重命名请求参数
 * @returns 执行结果
 */
export async function executeCloudRename(
  params: QuarkRenameExecuteRequest
): Promise<QuarkRenameExecuteResponse['data']> {
  const response = await api.post<any>('/quark/execute-cloud-rename', params)
  return response.data
}
