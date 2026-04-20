import { beforeEach, describe, expect, it, vi } from 'vitest'

import { browseFiles, fileOperation } from './fileManager'

const fileManagerApiMocks = vi.hoisted(() => ({
  browse: vi.fn(),
  operation: vi.fn(),
}))

vi.mock('./file-manager', () => ({
  fileManagerApi: fileManagerApiMocks,
}))

describe('file manager legacy api wrapper', () => {
  beforeEach(() => {
    fileManagerApiMocks.browse.mockReset()
    fileManagerApiMocks.operation.mockReset()
  })

  it('unwraps browse responses from the canonical file manager api', async () => {
    const payload = {
      items: [
        {
          id: 'folder-1',
          name: 'Movies',
          path: '/Movies',
          parent_path: '/',
          file_type: 'folder',
          storage_type: 'quark',
          mime_type: null,
          extension: null,
          size: 0,
          updated_at: null,
          thumbnail: null,
          preview_url: null,
          is_readable: true,
          is_writable: true,
          extra: {},
        },
      ],
      total: 1,
      path: '/',
      parent_path: null,
      breadcrumb: [{ name: 'root', path: '/' }],
    }
    fileManagerApiMocks.browse.mockResolvedValue({
      code: 0,
      message: 'ok',
      data: payload,
      timestamp: '2026-04-20T00:00:00Z',
    })

    const result = await browseFiles('/media', 'webdav')

    expect(fileManagerApiMocks.browse).toHaveBeenCalledWith({ path: '/media', storage: 'webdav' })
    expect(result).toEqual(payload)
  })

  it('delegates legacy file operations to the canonical payload shape', async () => {
    fileManagerApiMocks.operation.mockResolvedValue({
      code: 0,
      message: 'ok',
      data: { affected: 1 },
      timestamp: '2026-04-20T00:00:00Z',
    })

    const result = await fileOperation('rename', {
      path: '/Movies/Alpha.mkv',
      new_name: 'Alpha (2024).mkv',
    })

    expect(fileManagerApiMocks.operation).toHaveBeenCalledWith({
      action: 'rename',
      storage: 'quark',
      paths: ['/Movies/Alpha.mkv'],
      target: undefined,
      new_name: 'Alpha (2024).mkv',
    })
    expect(result).toEqual({ affected: 1 })
  })
})
