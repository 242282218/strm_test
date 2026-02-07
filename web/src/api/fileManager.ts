import api from './index'

export interface FileItem {
  id: string
  name: string
  path: string
  type?: 'folder' | 'file'
  file_type?: 'folder' | 'file'
  size?: number
  selected?: boolean
}

export interface BrowseResponse {
  items: FileItem[]
  total: number
  path: string
}

/**
 * 浏览文件目录
 * @param path 目录路径
 * @param storage 存储类型，默认为夸克网盘
 */
export const browseFiles = async (
  path: string = '/',
  storage: string = 'quark'
): Promise<BrowseResponse> => {
  const res: any = await api.get('/files/browse', {
    params: { path, storage }
  })
  return res.data
}

/**
 * 执行文件操作
 * @param operation 操作类型
 * @param params 操作参数
 */
export const fileOperation = async (
  operation: 'rename' | 'move' | 'delete' | 'mkdir',
  params: Record<string, any>
): Promise<any> => {
  const res: any = await api.post('/files/operation', {
    operation,
    ...params
  })
  return res.data
}
