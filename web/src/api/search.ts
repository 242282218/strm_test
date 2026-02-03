/**
 * 资源搜索API封装
 * 
 * 集成search包的资源搜索功能
 */

import api from './index'

export interface CloudLink {
  type: string
  url: string
  password?: string
  title?: string
}

export interface SearchResult {
  id: string
  title: string
  content: string
  source: string
  channel?: string
  pub_date?: string
  cloud_links: CloudLink[]
  score?: number
  confidence?: number
  quality?: number
  popularity?: number
  freshness?: number
}

export interface SearchResponse {
  results: SearchResult[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

// FilteredSearchResponse 已简化，使用 SearchResponse 替代
export type FilteredSearchResponse = SearchResponse

export interface SearchStatus {
  available: boolean
  search_service: boolean
}

/**
 * 搜索资源
 * 
 * 仅返回夸克网盘资源，按评分降序排序
 * 
 * @param params 搜索参数
 * @returns 搜索结果
 */
export const searchResources = (params: {
  keyword: string
  page?: number
  page_size?: number
}): Promise<SearchResponse> => {
  return api.get('/search', { params })
}

/**
 * 带过滤条件的资源搜索（已简化）
 * 
 * 仅返回夸克网盘资源，按评分降序排序
 * 
 * @param params 搜索参数
 * @returns 搜索结果
 */
export const searchResourcesFiltered = (params: {
  keyword: string
  page?: number
  page_size?: number
}): Promise<SearchResponse> => {
  return api.get('/search/filtered', { params })
}

/**
 * 获取搜索服务状态
 * 
 * @returns 搜索服务状态
 */
export const getSearchStatus = (): Promise<SearchStatus> => {
  return api.get('/search/status')
}
