import api from './index'

export interface EmbyServerInfo {
  server_name: string
  version: string
  operating_system: string
}

export interface EmbyLibrary {
  id: string
  name: string
  collection_type?: string | null
}

export interface EmbyStatus {
  enabled: boolean
  connected: boolean
  server_info: EmbyServerInfo | null
  configuration: {
    enabled: boolean
    url: string
    api_key: string
    timeout: number
    notify_on_complete: boolean
    on_strm_generate: boolean
    on_rename: boolean
    cron: string | null
    library_ids: string[]
    episode_aggregate_window_seconds: number
    delete_execute_enabled: boolean
  }
}

export interface EmbyConfigUpdate {
  enabled: boolean
  url: string
  api_key: string
  timeout: number
  notify_on_complete: boolean
  on_strm_generate: boolean
  on_rename: boolean
  cron: string
  library_ids: string[]
  episode_aggregate_window_seconds: number
  delete_execute_enabled: boolean
}

export interface EmbyRefreshHistoryItem {
  success: boolean
  library_id: string | null
  message: string
  timestamp: string
}

export const embyApi = {
  getStatus(params?: { probe?: boolean; probe_timeout?: number }): Promise<EmbyStatus> {
    return api.get('/emby/status', { params: params || {} })
  },

  testConnection(payload?: { url?: string; api_key?: string; timeout?: number }): Promise<{
    success: boolean
    message: string
    server_info: EmbyServerInfo | null
  }> {
    return api.post('/emby/test-connection', payload || {})
  },

  getLibraries(): Promise<{ success: boolean; libraries: EmbyLibrary[] }> {
    return api.get('/emby/libraries')
  },

  refresh(payload?: { library_ids?: string[] }): Promise<{ success: boolean; message: string }> {
    return api.post('/emby/refresh', payload || {})
  },

  getRefreshHistory(params?: { limit?: number }): Promise<{ success: boolean; history: EmbyRefreshHistoryItem[] }> {
    return api.get('/emby/refresh/history', { params: params || {} })
  },

  triggerSync(): Promise<{ status: string; message: string }> {
    return api.post('/emby/sync')
  },

  updateConfig(payload: EmbyConfigUpdate): Promise<{ success: boolean }> {
    return api.post('/emby/config', payload)
  }
}
