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

  updateConfig(payload: EmbyConfigUpdate): Promise<{ success: boolean }> {
    return api.post('/emby/config', payload)
  }
}
