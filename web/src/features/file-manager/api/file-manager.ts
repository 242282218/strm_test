import api from '@/api/index'

interface ApiEnvelope<T> {
    code: number
    message: string
    data: T
    request_id?: string | null
    timestamp: string
}

export interface FileItem {
    id: string
    name: string
    path: string
    parent_path: string | null
    file_type: 'file' | 'folder' | 'link'
    storage_type: 'local' | 'quark' | 'alist' | 'webdav'
    mime_type: string | null
    extension: string | null
    size: number
    updated_at: string | null
    thumbnail: string | null
    preview_url: string | null
    is_readable: boolean
    is_writable: boolean
    extra: Record<string, unknown>
}

export interface BrowseResponse {
    items: FileItem[]
    total: number
    path: string
    parent_path: string | null
    breadcrumb: { name: string; path: string }[]
}

export interface FileOperationRequest {
    action: 'rename' | 'move' | 'delete' | 'mkdir'
    storage: 'local' | 'quark' | 'alist' | 'webdav'
    paths: string[]
    target?: string
    new_name?: string
}

export const fileManagerApi = {
    /**
     * 浏览目录
     */
    browse(params: { storage: string; path?: string; page?: number; size?: number }) {
        return api.get<ApiEnvelope<BrowseResponse>>('/files/browse', { params })
    },

    /**
     * 统一文件操作
     */
    operation(data: FileOperationRequest) {
        return api.post<ApiEnvelope<Record<string, unknown>>, FileOperationRequest>('/files/operation', data)
    }
}
