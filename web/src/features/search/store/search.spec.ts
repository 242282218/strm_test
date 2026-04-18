import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useSearchStore } from './search'
import type { SearchResponse, SearchResult } from '@/api/search'

const searchApiMocks = vi.hoisted(() => ({
  searchResources: vi.fn(),
}))

vi.mock('@/api/search', () => ({
  searchResources: searchApiMocks.searchResources,
}))

const createSearchResult = (overrides: Partial<SearchResult> = {}): SearchResult => ({
  id: 'result-1',
  title: '三体',
  content: '高清片源',
  source: 'telegram',
  channel: '影视频道',
  pub_date: '2026-04-18T08:00:00Z',
  cloud_links: [
    {
      type: 'quark',
      url: 'https://pan.quark.cn/s/demo',
      password: '1234',
    },
  ],
  score: 90,
  confidence: 0.92,
  quality: 88,
  popularity: 81,
  freshness: 76,
  ...overrides,
})

const createSearchResponse = (
  overrides: Partial<SearchResponse> = {},
): SearchResponse => ({
  results: [createSearchResult()],
  total: 1,
  page: 1,
  page_size: 20,
  has_more: false,
  ...overrides,
})

describe('search store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('ignores blank keywords without mutating state', async () => {
    const store = useSearchStore()

    await expect(store.search('   ')).resolves.toBe(false)

    expect(searchApiMocks.searchResources).not.toHaveBeenCalled()
    expect(store.query).toBe('')
    expect(store.hasSearched).toBe(false)
    expect(store.results).toEqual([])
  })

  it('populates the first page and metadata on search success', async () => {
    const store = useSearchStore()
    const nowSpy = vi.spyOn(Date, 'now')

    nowSpy.mockReturnValueOnce(100).mockReturnValueOnce(260)
    searchApiMocks.searchResources.mockResolvedValue(
      createSearchResponse({
        total: 3,
        has_more: true,
      }),
    )

    await expect(store.search('三体')).resolves.toBe(true)

    expect(searchApiMocks.searchResources).toHaveBeenCalledWith({
      keyword: '三体',
      page: 1,
      page_size: 20,
    })
    expect(store.query).toBe('三体')
    expect(store.hasSearched).toBe(true)
    expect(store.results).toHaveLength(1)
    expect(store.totalResults).toBe(3)
    expect(store.hasMore).toBe(true)
    expect(store.searchTime).toBe(160)

    nowSpy.mockRestore()
  })

  it('marks the search as failed when the backend returns an error payload', async () => {
    const store = useSearchStore()

    searchApiMocks.searchResources.mockResolvedValue(
      createSearchResponse({
        results: [],
        total: 0,
        error: 'upstream unavailable',
      }),
    )

    await expect(store.search('异常关键词')).resolves.toBe(false)

    expect(store.hasSearched).toBe(true)
    expect(store.isEmpty).toBe(true)
    expect(store.loading).toBe(false)
    expect(store.hasMore).toBe(false)
  })

  it('appends the next page on loadMore success', async () => {
    const store = useSearchStore()

    searchApiMocks.searchResources
      .mockResolvedValueOnce(
        createSearchResponse({
          results: [createSearchResult({ id: 'result-1', title: '三体 第一集' })],
          total: 2,
          has_more: true,
        }),
      )
      .mockResolvedValueOnce(
        createSearchResponse({
          results: [createSearchResult({ id: 'result-2', title: '三体 第二集' })],
          total: 2,
          page: 2,
          has_more: false,
        }),
      )

    await store.search('三体')
    await expect(store.loadMore()).resolves.toBe(true)

    expect(searchApiMocks.searchResources).toHaveBeenNthCalledWith(2, {
      keyword: '三体',
      page: 2,
      page_size: 20,
    })
    expect(store.results.map(item => item.title)).toEqual(['三体 第一集', '三体 第二集'])
    expect(store.hasMore).toBe(false)
    expect(store.loadingMore).toBe(false)
  })

  it('rolls the page counter back when loadMore receives an error response', async () => {
    const store = useSearchStore()

    searchApiMocks.searchResources
      .mockResolvedValueOnce(
        createSearchResponse({
          results: [createSearchResult({ id: 'result-1', title: '第一页' })],
          total: 2,
          has_more: true,
        }),
      )
      .mockResolvedValueOnce(
        createSearchResponse({
          results: [],
          total: 2,
          page: 2,
          has_more: true,
          error: 'page failed',
        }),
      )

    await store.search('分页失败')
    await expect(store.loadMore()).resolves.toBe(false)

    expect(store.results.map(item => item.title)).toEqual(['第一页'])
    expect(store.loadingMore).toBe(false)
    expect(store.hasMore).toBe(true)

    searchApiMocks.searchResources.mockClear()
    searchApiMocks.searchResources.mockResolvedValueOnce(
      createSearchResponse({
        results: [createSearchResult({ id: 'result-2', title: '重试页' })],
        total: 2,
        page: 2,
        has_more: false,
      }),
    )

    await expect(store.loadMore()).resolves.toBe(true)
    expect(searchApiMocks.searchResources).toHaveBeenCalledWith({
      keyword: '分页失败',
      page: 2,
      page_size: 20,
    })
    expect(store.results.map(item => item.title)).toEqual(['第一页', '重试页'])
  })

  it('rolls back loading state and resets the store after thrown pagination failures', async () => {
    const store = useSearchStore()
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)

    searchApiMocks.searchResources
      .mockResolvedValueOnce(
        createSearchResponse({
          results: [createSearchResult({ id: 'result-1', title: '第一页' })],
          total: 2,
          has_more: true,
        }),
      )
      .mockRejectedValueOnce(new Error('network down'))

    await store.search('网络错误')
    await expect(store.loadMore()).resolves.toBe(false)

    expect(store.results.map(item => item.title)).toEqual(['第一页'])
    expect(store.loadingMore).toBe(false)
    expect(store.hasMore).toBe(true)

    store.setViewMode('list')
    expect(store.viewMode).toBe('list')

    store.reset()

    expect(store.query).toBe('')
    expect(store.results).toEqual([])
    expect(store.hasSearched).toBe(false)
    expect(store.hasMore).toBe(false)
    expect(store.totalResults).toBe(0)
    expect(store.viewMode).toBe('list')

    consoleErrorSpy.mockRestore()
  })
})
