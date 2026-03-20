import type { QuarkRenameItem } from '@/api/quark'

import type { SmartRenameItem } from './api/smartRename'

export type SourceMode = 'local' | 'cloud'
export type StatusFilter = 'all' | 'pending' | 'matched' | 'unmatched' | 'success' | 'failed'
export type ConfidenceFilter = 'all' | 'high' | 'medium' | 'low'
export type SortKey = 'confidence_desc' | 'confidence_asc' | 'name_asc' | 'name_desc' | 'new_name_asc' | 'new_name_desc' | 'status'

export interface ViewRenameItem extends Omit<SmartRenameItem, 'new_name'> {
  id: string
  new_name: string
  source_mode: SourceMode
}

export interface CloudExecutionSnapshot {
  fid: string
  original_name: string
  executed_name: string
}

export interface DisplayRowOptions {
  keyword: string
  statusFilter: StatusFilter
  confidenceFilter: ConfidenceFilter
  sortKey: SortKey
}

export const RECENT_PATH_KEY = 'smart_rename_recent_paths_v2'

export const statusFilterOptions = [
  { label: '全部状态', value: 'all' },
  { label: '待确认', value: 'pending' },
  { label: '已匹配', value: 'matched' },
  { label: '未匹配', value: 'unmatched' },
  { label: '执行成功', value: 'success' },
  { label: '执行失败', value: 'failed' },
] as const

export const confidenceFilterOptions = [
  { label: '全部置信度', value: 'all' },
  { label: '高 (≥ 90%)', value: 'high' },
  { label: '中 (60% - 89%)', value: 'medium' },
  { label: '低 (< 60%)', value: 'low' },
] as const

export const sortOptions = [
  { label: '置信度从高到低', value: 'confidence_desc' },
  { label: '置信度从低到高', value: 'confidence_asc' },
  { label: '原文件名 A-Z', value: 'name_asc' },
  { label: '原文件名 Z-A', value: 'name_desc' },
  { label: '建议名称 A-Z', value: 'new_name_asc' },
  { label: '建议名称 Z-A', value: 'new_name_desc' },
  { label: '按状态分组', value: 'status' },
] as const

export function parseRecentPaths(raw: string | null): string[] {
  if (!raw) return []

  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === 'string').slice(0, 6) : []
  } catch {
    return []
  }
}

export function mergeRecentPaths(path: string, currentPaths: string[]): string[] {
  const clean = path.trim()
  if (!clean) return currentPaths.slice(0, 6)
  return [clean, ...currentPaths.filter((item) => item !== clean)].slice(0, 6)
}

export function providerStateText(provider?: { configured: boolean; connected: boolean }): string {
  if (!provider) return '未知'
  if (provider.connected) return '已连接'
  if (provider.configured) return '连接失败'
  return '未配置'
}

export function providerLabel(provider?: string): string {
  if (provider === 'kimi') return 'Kimi2.5'
  if (provider === 'deepseek') return 'DeepSeek'
  if (provider === 'glm') return 'GLM'
  return provider || 'Unknown'
}

export function normalizeLocalItem(item: SmartRenameItem): ViewRenameItem {
  return {
    ...item,
    id: item.original_path,
    new_name: item.new_name || item.original_name || '',
    source_mode: 'local',
  }
}

export function normalizeCloudItem(item: Partial<QuarkRenameItem> & Pick<QuarkRenameItem, 'fid' | 'original_name'>): ViewRenameItem {
  return {
    id: item.fid,
    source_mode: 'cloud',
    original_path: item.fid,
    original_name: item.original_name,
    new_name: item.new_name || item.original_name,
    media_type: item.media_type || 'unknown',
    tmdb_id: item.tmdb_id,
    tmdb_title: item.tmdb_title,
    tmdb_year: item.tmdb_year,
    season: item.season,
    episode: item.episode,
    overall_confidence: item.overall_confidence || 0,
    status: item.status || (item.needs_confirmation ? 'needs_confirmation' : 'parsed'),
    needs_confirmation: !!item.needs_confirmation,
    confirmation_reason: item.confirmation_reason,
    used_algorithm: item.used_algorithm,
  }
}

export function statusText(row: ViewRenameItem): string {
  if (row.status === 'success') return '执行成功'
  if (row.status === 'skipped') return '已跳过'
  if (row.status === 'failed') return '执行失败'
  if (row.status === 'rolled_back') return '已回滚'
  if (row.needs_confirmation) return '待确认'
  if (row.tmdb_id) return '已匹配'
  return '已解析'
}

export function statusType(row: ViewRenameItem): 'success' | 'warning' | 'danger' | 'info' {
  if (row.status === 'success') return 'success'
  if (row.status === 'skipped') return 'info'
  if (row.status === 'failed') return 'danger'
  if (row.needs_confirmation) return 'warning'
  return 'info'
}

export function confidenceStatus(value: number): '' | 'success' | 'warning' | 'exception' {
  if (value >= 0.9) return 'success'
  if (value >= 0.6) return 'warning'
  return 'exception'
}

export function getMediaTypeText(type: string): string {
  const map: Record<string, string> = { movie: '电影', tv: '剧集', anime: '动漫', unknown: '未知' }
  return map[type] || type
}

export function buildDisplayRows(rows: ViewRenameItem[], options: DisplayRowOptions): ViewRenameItem[] {
  const { keyword, statusFilter, confidenceFilter, sortKey } = options
  let nextRows = [...rows]

  const q = keyword.trim().toLowerCase()
  if (q) {
    nextRows = nextRows.filter((row) => {
      const source = `${row.original_name} ${row.original_path}`.toLowerCase()
      const target = `${row.new_name} ${row.tmdb_title || ''}`.toLowerCase()
      return source.includes(q) || target.includes(q)
    })
  }

  if (statusFilter !== 'all') {
    nextRows = nextRows.filter((row) => {
      if (statusFilter === 'pending') return row.needs_confirmation
      if (statusFilter === 'matched') return !!row.tmdb_id
      if (statusFilter === 'unmatched') return !row.tmdb_id
      if (statusFilter === 'success') return row.status === 'success'
      if (statusFilter === 'failed') return row.status === 'failed'
      return true
    })
  }

  if (confidenceFilter !== 'all') {
    nextRows = nextRows.filter((row) => {
      const value = row.overall_confidence || 0
      if (confidenceFilter === 'high') return value >= 0.9
      if (confidenceFilter === 'medium') return value >= 0.6 && value < 0.9
      return value < 0.6
    })
  }

  nextRows.sort((a, b) => {
    const nameA = (a.original_name || '').toLowerCase()
    const nameB = (b.original_name || '').toLowerCase()
    const newA = (a.new_name || '').toLowerCase()
    const newB = (b.new_name || '').toLowerCase()
    const confA = a.overall_confidence || 0
    const confB = b.overall_confidence || 0

    if (sortKey === 'confidence_desc') return confB - confA
    if (sortKey === 'confidence_asc') return confA - confB
    if (sortKey === 'name_asc') return nameA.localeCompare(nameB)
    if (sortKey === 'name_desc') return nameB.localeCompare(nameA)
    if (sortKey === 'new_name_asc') return newA.localeCompare(newB)
    if (sortKey === 'new_name_desc') return newB.localeCompare(newA)
    return statusText(a).localeCompare(statusText(b))
  })

  return nextRows
}
