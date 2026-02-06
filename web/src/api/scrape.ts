import api from './index'

export type MediaType = 'auto' | 'movie' | 'tv'
export type ScrapeMode = 'only_scrape' | 'scrape_and_rename' | 'only_rename'
export type RenameMode = 'move' | 'copy' | 'hardlink' | 'softlink'

export interface ScrapePath {
  id: number
  path_id: string
  source_path: string
  dest_path: string
  media_type: MediaType
  scrape_mode: ScrapeMode
  rename_mode: RenameMode
  max_threads: number
  cron: string | null
  enabled: boolean
  cron_enabled: boolean
  enable_secondary_category: boolean
  status: string
  last_job_id: string | null
  created_at: string
  updated_at: string
}

export interface ScrapePathListResponse {
  items: ScrapePath[]
  total: number
}

export interface ScrapePathCreatePayload {
  source_path: string
  dest_path: string
  media_type: MediaType
  scrape_mode: ScrapeMode
  rename_mode: RenameMode
  max_threads: number
  cron?: string | null
  enabled: boolean
  enable_secondary_category: boolean
}

export type ScrapePathUpdatePayload = Partial<ScrapePathCreatePayload>

export interface StartPathResponse {
  ok: boolean
  started: boolean
  already_running: boolean
  job_id: string
  path_id: string
}

export interface StopPathResponse {
  path_id: string
  stopped: boolean
  job_id: string | null
}

export interface ToggleCronResponse {
  path_id: string
  cron_enabled: boolean
}

export interface ScrapeRecord {
  id: number
  record_id: string
  job_id: string
  path_id: string | null
  item_id: number | null
  source_file: string
  target_file: string | null
  media_type: string | null
  tmdb_id: number | null
  title: string | null
  year: number | null
  status: string
  error_code: string | null
  error_message: string | null
  recognition_result: Record<string, unknown> | null
  created_at: string
  updated_at: string | null
}

export interface ScrapeRecordListResponse {
  items: ScrapeRecord[]
  total: number
}

export const scrapeApi = {
  listPaths(params?: {
    keyword?: string
    status?: string
    enabled?: boolean
    page?: number
    size?: number
  }): Promise<ScrapePathListResponse> {
    return api.get('/scrape/pathes', { params: params || {} })
  },

  createPath(payload: ScrapePathCreatePayload): Promise<ScrapePath> {
    return api.post('/scrape/pathes', payload)
  },

  getPath(pathId: string): Promise<ScrapePath> {
    return api.get(`/scrape/pathes/${pathId}`)
  },

  updatePath(pathId: string, payload: ScrapePathUpdatePayload): Promise<ScrapePath> {
    return api.put(`/scrape/pathes/${pathId}`, payload)
  },

  deletePath(pathId: string): Promise<{ deleted: boolean; path_id: string }> {
    return api.delete(`/scrape/pathes/${pathId}`)
  },

  startPath(pathId: string): Promise<StartPathResponse> {
    return api.post('/scrape/pathes/start', { path_id: pathId })
  },

  stopPath(pathId: string): Promise<StopPathResponse> {
    return api.post('/scrape/pathes/stop', { path_id: pathId })
  },

  toggleCron(pathId: string, enabled?: boolean): Promise<ToggleCronResponse> {
    return api.post('/scrape/pathes/toggle-cron', {
      path_id: pathId,
      enabled
    })
  },

  listRecords(params?: {
    keyword?: string
    status?: string
    page?: number
    size?: number
  }): Promise<ScrapeRecordListResponse> {
    return api.get('/scrape/records', { params: params || {} })
  },

  getRecord(recordId: string): Promise<ScrapeRecord> {
    return api.get(`/scrape/records/${recordId}`)
  },

  reScrape(recordIds: string[]): Promise<{ requested: number; updated: number; queued_jobs: number }> {
    return api.post('/scrape/re-scrape', { record_ids: recordIds })
  },

  clearFailed(): Promise<{ cleared: number }> {
    return api.post('/scrape/clear-failed', {})
  },

  truncateAll(): Promise<{ truncated: number }> {
    return api.post('/scrape/truncate-all', {})
  }
}
