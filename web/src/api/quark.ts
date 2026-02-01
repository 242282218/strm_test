import api from './index'

export interface QuarkFile {
  fid: string
  file_name: string
  category: number
  file: boolean
  size?: number
  created_at?: number
  updated_at?: number
  mime_type?: string
}

export interface QuarkConfig {
  referer: string
  root_id: string
  only_video: boolean
  cookie_configured: boolean
}

export interface SyncResult {
  message: string
  root_id: string
  output_dir: string
  result: {
    total: number
    success: number
    failed: number
    files: string[]
  }
}

// 获取文件列表
export const getQuarkFiles = (parent: string = '0', only_video: boolean = false): Promise<{ files: QuarkFile[]; count: number }> => {
  return api.get(`/quark/files/${parent}`, { params: { only_video } })
}

// 获取夸克配置
export const getQuarkConfig = (): Promise<QuarkConfig> => {
  return api.get('/quark/config')
}

// 同步夸克文件
export const syncQuarkFiles = (data?: {
  cookie?: string
  root_id?: string
  output_dir?: string
  only_video?: boolean
}): Promise<SyncResult> => {
  return api.post('/quark/sync', data)
}

// 获取下载链接
export const getDownloadLink = (fileId: string): Promise<{ url: string; headers: Record<string, string> }> => {
  return api.get(`/quark/link/${fileId}`)
}
