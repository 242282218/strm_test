import api from './index'

export interface ScanResult {
    strms: string[]
    count: number
}

/**
 * 扫描目录并生成STRM
 * 
 * @param params 扫描参数
 */
export const scanDirectory = (params: {
    remote_path: string
    local_path: string
    recursive?: boolean
    concurrent_limit?: number
    base_url?: string
    strm_url_mode?: 'redirect' | 'stream' | 'direct' | 'webdav'
}): Promise<ScanResult> => {
    return api.post('/strm/scan', null, { params })
}
