import api from './index'

export interface ScanResult {
    strms: string[]
    count: number
    skipped?: number
    failed?: number
    total?: number
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
    overwrite?: boolean
    strm_url_mode?: 'redirect' | 'stream' | 'direct' | 'webdav'
}): Promise<ScanResult> => {
    return api.post('/strm/scan', null, { params })
}
