import { beforeEach, describe, expect, it, vi } from 'vitest'

import api from '@/api/index'
import { scrapeApi } from './scrape'

const apiClientMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/index', () => ({
  default: apiClientMocks,
}))

type MockedApi = {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

const mockedApi = api as unknown as MockedApi

describe('scrape api canonical routes', () => {
  beforeEach(() => {
    mockedApi.get.mockReset()
    mockedApi.post.mockReset()
    mockedApi.put.mockReset()
    mockedApi.delete.mockReset()
  })

  it('uses canonical v1 path endpoints', async () => {
    mockedApi.get.mockResolvedValue({ items: [], total: 0 })
    mockedApi.post.mockResolvedValue({})
    mockedApi.put.mockResolvedValue({})
    mockedApi.delete.mockResolvedValue({})

    await scrapeApi.listPaths({ page: 1, size: 20 })
    await scrapeApi.createPath({
      source_path: '/raw',
      dest_path: '/library',
      media_type: 'tv',
      scrape_mode: 'scrape_and_rename',
      rename_mode: 'move',
      max_threads: 2,
      enabled: true,
      enable_secondary_category: true,
    })
    await scrapeApi.getPath('path-1')
    await scrapeApi.updatePath('path-1', { enabled: false })
    await scrapeApi.deletePath('path-1')
    await scrapeApi.startPath('path-1')
    await scrapeApi.stopPath('path-1')
    await scrapeApi.toggleCron('path-1', true)

    expect(mockedApi.get).toHaveBeenCalledWith('/v1/scrape/paths', {
      params: { page: 1, size: 20 },
    })
    expect(mockedApi.post).toHaveBeenNthCalledWith(1, '/v1/scrape/paths', expect.any(Object))
    expect(mockedApi.get).toHaveBeenNthCalledWith(2, '/v1/scrape/paths/path-1')
    expect(mockedApi.put).toHaveBeenCalledWith('/v1/scrape/paths/path-1', { enabled: false })
    expect(mockedApi.delete).toHaveBeenCalledWith('/v1/scrape/paths/path-1')
    expect(mockedApi.post).toHaveBeenNthCalledWith(2, '/v1/scrape/paths/start', { path_id: 'path-1' })
    expect(mockedApi.post).toHaveBeenNthCalledWith(3, '/v1/scrape/paths/stop', { path_id: 'path-1' })
    expect(mockedApi.post).toHaveBeenNthCalledWith(4, '/v1/scrape/paths/toggle-cron', {
      path_id: 'path-1',
      enabled: true,
    })
  })

  it('uses canonical v1 record endpoints', async () => {
    mockedApi.get.mockResolvedValue({ items: [], total: 0 })
    mockedApi.post.mockResolvedValue({})

    await scrapeApi.listRecords({ status: 'scrape_failed' })
    await scrapeApi.getRecord('record-1')
    await scrapeApi.reScrape(['record-1'])
    await scrapeApi.clearFailed()
    await scrapeApi.truncateAll()

    expect(mockedApi.get).toHaveBeenNthCalledWith(1, '/v1/scrape/records', {
      params: { status: 'scrape_failed' },
    })
    expect(mockedApi.get).toHaveBeenNthCalledWith(2, '/v1/scrape/records/record-1')
    expect(mockedApi.post).toHaveBeenNthCalledWith(1, '/v1/scrape/re-scrape', { record_ids: ['record-1'] })
    expect(mockedApi.post).toHaveBeenNthCalledWith(2, '/v1/scrape/clear-failed', {})
    expect(mockedApi.post).toHaveBeenNthCalledWith(3, '/v1/scrape/truncate-all', {})
  })
})
