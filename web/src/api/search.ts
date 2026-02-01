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

export interface FilteredSearchResponse extends SearchResponse {
  filters: {
    min_score: number
    min_confidence: number
  }
}

export interface SearchStatus {
  available: boolean
  search_service: boolean
}

/**
 * 搜索资源
 * 
 * @param params 搜索参数
 * @returns 搜索结果
 */
export const searchResources = (params: {
  keyword: string
  cloud_types?: string[]
  sources?: string[]
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: string
}): Promise<SearchResponse> => {
  return api.get('/search', { params })
}

/**
 * 带过滤条件的资源搜索
 * 
 * @param params 搜索参数（含过滤条件）
 * @returns 过滤后的搜索结果
 */
export const searchResourcesFiltered = (params: {
  keyword: string
  min_score?: number
  min_confidence?: number
  cloud_types?: string[]
  page?: number
  page_size?: number
}): Promise<FilteredSearchResponse> => {
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
