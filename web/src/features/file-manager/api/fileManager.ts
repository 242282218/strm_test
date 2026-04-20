import {
  fileManagerApi,
  type BrowseResponse,
  type FileItem,
  type FileOperationRequest,
} from './file-manager'

type LegacyFileOperation = FileOperationRequest['action']
type LegacyFileOperationParams = Record<string, unknown>

function resolveLegacyPaths(params: LegacyFileOperationParams): string[] {
  const paths = params.paths
  if (Array.isArray(paths)) {
    return paths.filter((value): value is string => typeof value === 'string')
  }

  const path = params.path
  if (typeof path === 'string' && path.length > 0) {
    return [path]
  }

  return []
}

function resolveLegacyStorage(params: LegacyFileOperationParams): FileOperationRequest['storage'] {
  const storage = params.storage
  if (storage === 'local' || storage === 'quark' || storage === 'alist' || storage === 'webdav') {
    return storage
  }

  return 'quark'
}

function buildLegacyOperationPayload(
  operation: LegacyFileOperation,
  params: LegacyFileOperationParams,
): FileOperationRequest {
  return {
    action: operation,
    storage: resolveLegacyStorage(params),
    paths: resolveLegacyPaths(params),
    target: typeof params.target === 'string' ? params.target : undefined,
    new_name: typeof params.new_name === 'string' ? params.new_name : undefined,
  }
}

export const browseFiles = async (
  path: string = '/',
  storage: FileOperationRequest['storage'] = 'quark',
): Promise<BrowseResponse> => {
  const response = await fileManagerApi.browse({ path, storage })
  return response.data
}

export const fileOperation = async (
  operation: LegacyFileOperation,
  params: LegacyFileOperationParams,
): Promise<Record<string, unknown>> => {
  const response = await fileManagerApi.operation(buildLegacyOperationPayload(operation, params))
  return response.data
}

export type { BrowseResponse, FileItem }
