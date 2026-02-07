import api from './index'

export interface ProxyCacheStats {
  size: number
  hit_count: number
  miss_count: number
  hit_rate: number
}

export interface ProxyStreamResponse {
  status: string
  message: string
  url?: string
  test?: boolean
}

/**
 * 获取代理缓存统计
 */
export const getProxyCacheStats = (): Promise<{ status: string; stats: ProxyCacheStats }> => {
  return api.get('/proxy/cache/stats')
}

/**
 * 清除代理缓存
 */
export const clearProxyCache = (): Promise<{ status: string; message: string }> => {
  return api.post('/proxy/cache/clear')
}

/**
 * 获取 302 重定向链接
 * @param fileId 文件ID
 * @param path 可选文件路径
 */
export const getRedirectUrl = (fileId: string, path?: string): Promise<string> => {
  return api.get(`/proxy/redirect/${fileId}`, {
    params: path ? { path } : undefined,
    responseType: 'text'
  })
}

/**
 * 获取代理流链接
 * @param fileId 文件ID
 */
export const getProxyStreamUrl = (fileId: string): string => {
  return `${api.defaults.baseURL}/proxy/stream/${fileId}`
}

/**
 * 获取转码链接
 * @param fileId 文件ID
 */
export const getTranscodingUrl = (fileId: string): Promise<string> => {
  return api.get(`/proxy/transcoding/${fileId}`, {
    responseType: 'text'
  })
}

/**
 * 测试代理流端点
 */
export const testStreamEndpoint = (): Promise<ProxyStreamResponse> => {
  return api.get('/proxy/stream/test')
}
