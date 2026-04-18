import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import SearchView from './SearchView.vue'
import { useSearchStore } from '@/stores/search'
import type { SearchResponse, SearchResult } from '@/api/search'

const searchApiMocks = vi.hoisted(() => ({
  searchResources: vi.fn(),
}))

const transferApiMocks = vi.hoisted(() => ({
  listCloudDrives: vi.fn(),
  transferShare: vi.fn(),
}))

const notificationMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
  alert: vi.fn(),
  prompt: vi.fn(),
}))

vi.mock('@/api/search', () => ({
  searchResources: searchApiMocks.searchResources,
}))

vi.mock('@/api/cloudDrive', () => ({
  listCloudDrives: transferApiMocks.listCloudDrives,
}))

vi.mock('@/api/transfer', () => ({
  transferShare: transferApiMocks.transferShare,
}))

vi.mock('@/composables', () => ({
  useNotification: () => notificationMocks,
  useDebounce: <T extends unknown[], R>(fn: (...args: T) => R) => ({
    run: (...args: T) => fn(...args),
    cancel: vi.fn(),
    flush: vi.fn(),
    pending: { value: false },
  }),
}))

vi.mock('@/components/search/SearchHero.vue', () => ({
  default: {
    name: 'SearchHeroStub',
    template: '<section data-testid="search-hero-stub"><slot /></section>',
  },
}))

vi.mock('@/components/search/SearchBox.vue', () => ({
  default: {
    name: 'SearchBoxStub',
    props: ['modelValue', 'loading', 'hotTags'],
    emits: ['update:modelValue', 'search'],
    template: `
      <div data-testid="search-box-stub">
        <button type="button" data-testid="emit-search" @click="$emit('search', modelValue)">search</button>
      </div>
    `,
  },
}))

vi.mock('@/components/search/SearchFilters.vue', () => ({
  default: {
    name: 'SearchFiltersStub',
    props: ['visible'],
    template: '<div data-testid="search-filters-stub">{{ visible }}</div>',
  },
}))

vi.mock('@/components/search/SearchResults.vue', () => ({
  default: {
    name: 'SearchResultsStub',
    props: ['results', 'total', 'searchTime', 'viewMode', 'hasMore', 'loadingMore'],
    emits: ['update:view-mode', 'open-link', 'save', 'load-more'],
    template: `
      <section data-testid="search-results-stub">
        <span data-testid="search-results-total">{{ total }}</span>
        <article v-for="item in results" :key="item.id" class="result-row">{{ item.title }}</article>
      </section>
    `,
  },
}))

vi.mock('@/components/search/SearchEmpty.vue', () => ({
  default: {
    name: 'SearchEmptyStub',
    props: ['type'],
    template: '<div :data-testid="`search-empty-${type}`">{{ type }}</div>',
  },
}))

interface SearchViewVm {
  handleSearch: (keyword: string) => Promise<void>
  saveToCloud: (item: SearchResult) => Promise<void>
}

const asSearchViewVm = (vm: unknown): SearchViewVm => vm as SearchViewVm

const createSearchResult = (overrides: Partial<SearchResult> = {}): SearchResult => ({
  id: 'result-1',
  title: '三体',
  content: '找到高清资源',
  source: 'telegram',
  channel: '影视资源频道',
  pub_date: '2026-04-18T08:00:00Z',
  cloud_links: [
    {
      type: 'quark',
      url: 'https://pan.quark.cn/s/demo',
      password: '1234',
      title: '夸克链接',
    },
  ],
  score: 91,
  confidence: 0.95,
  quality: 88,
  popularity: 80,
  freshness: 77,
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

const mountView = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(SearchView, {
    global: {
      plugins: [pinia],
    },
  })
}

describe('SearchView', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  beforeEach(() => {
    vi.clearAllMocks()
    notificationMocks.prompt.mockResolvedValue('/媒体库')
    notificationMocks.alert.mockResolvedValue(undefined)
    transferApiMocks.listCloudDrives.mockResolvedValue([
      { id: 7, name: 'Quark', drive_type: 'quark' },
    ])
    transferApiMocks.transferShare.mockResolvedValue({
      message: '转存任务已提交',
    })
  })

  it('keeps the initial guidance visible and warns on blank searches', async () => {
    const wrapper = mountView()
    const vm = asSearchViewVm(wrapper.vm)

    expect(wrapper.find('[data-testid="search-empty-initial"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="search-filters-stub"]').text()).toBe('false')

    await vm.handleSearch('   ')

    expect(searchApiMocks.searchResources).not.toHaveBeenCalled()
    expect(notificationMocks.warning).toHaveBeenCalledWith('请输入搜索关键词')
  })

  it('runs the search flow and renders the result state on success', async () => {
    searchApiMocks.searchResources.mockResolvedValue(createSearchResponse())

    const wrapper = mountView()
    const vm = asSearchViewVm(wrapper.vm)
    const store = useSearchStore()

    await vm.handleSearch('三体')
    await flushPromises()

    expect(searchApiMocks.searchResources).toHaveBeenCalledWith({
      keyword: '三体',
      page: 1,
      page_size: 20,
    })
    expect(store.query).toBe('三体')
    expect(store.hasSearched).toBe(true)
    expect(store.isEmpty).toBe(false)
    expect(wrapper.find('[data-testid="search-results-stub"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('三体')
    expect(wrapper.find('[data-testid="search-filters-stub"]').text()).toBe('true')
    expect(notificationMocks.error).not.toHaveBeenCalled()
  })

  it('shows the empty result state and error notification when search response fails', async () => {
    searchApiMocks.searchResources.mockResolvedValue(
      createSearchResponse({
        results: [],
        total: 0,
        error: 'provider unavailable',
      }),
    )

    const wrapper = mountView()
    const vm = asSearchViewVm(wrapper.vm)
    const store = useSearchStore()

    await vm.handleSearch('错误关键词')
    await flushPromises()

    expect(store.hasSearched).toBe(true)
    expect(store.isEmpty).toBe(true)
    expect(wrapper.find('[data-testid="search-empty-empty"]').exists()).toBe(true)
    expect(notificationMocks.error).toHaveBeenCalledWith('搜索失败，请稍后重试')
  })

  it('rejects save requests that do not contain a quark link', async () => {
    const wrapper = mountView()
    const vm = asSearchViewVm(wrapper.vm)

    await vm.saveToCloud(
      createSearchResult({
        cloud_links: [
          {
            type: 'baidu',
            url: 'https://pan.baidu.com/s/demo',
          },
        ],
      }),
    )

    expect(notificationMocks.error).toHaveBeenCalledWith('该资源没有夸克网盘链接')
    expect(notificationMocks.prompt).not.toHaveBeenCalled()
    expect(transferApiMocks.transferShare).not.toHaveBeenCalled()
  })

  it('stops transfer cleanly when the target directory prompt is cancelled', async () => {
    notificationMocks.prompt.mockResolvedValue(null)

    const wrapper = mountView()
    const vm = asSearchViewVm(wrapper.vm)

    await vm.saveToCloud(createSearchResult())

    expect(notificationMocks.prompt).toHaveBeenCalledWith(
      '请输入转存目录，例如 /电影 或 /电视剧',
      '转存到夸克网盘',
      '/',
    )
    expect(transferApiMocks.listCloudDrives).not.toHaveBeenCalled()
    expect(transferApiMocks.transferShare).not.toHaveBeenCalled()
  })

  it('falls back to cookie mode when no quark drive exists and still submits transfer', async () => {
    transferApiMocks.listCloudDrives.mockResolvedValue([
      { id: 9, name: 'Aliyun', drive_type: 'aliyun' },
    ])
    notificationMocks.prompt.mockResolvedValue(' /电影 ')

    const wrapper = mountView()
    const vm = asSearchViewVm(wrapper.vm)

    await vm.saveToCloud(createSearchResult())

    expect(notificationMocks.info).toHaveBeenCalledWith(
      '未检测到夸克账号，将尝试使用系统配置的 quark.cookie 转存',
    )
    expect(transferApiMocks.transferShare).toHaveBeenCalledWith({
      drive_id: undefined,
      share_url: 'https://pan.quark.cn/s/demo',
      target_dir: '/电影',
      password: '1234',
      auto_organize: false,
    })
    expect(notificationMocks.success).toHaveBeenCalledWith('转存任务已提交')
  })

  it('surfaces backend transfer details when submit fails', async () => {
    transferApiMocks.transferShare.mockRejectedValue({
      response: {
        data: {
          detail: '目录无权限',
        },
      },
    })

    const wrapper = mountView()
    const vm = asSearchViewVm(wrapper.vm)

    await vm.saveToCloud(createSearchResult())

    expect(transferApiMocks.transferShare).toHaveBeenCalledTimes(1)
    expect(notificationMocks.error).toHaveBeenCalledWith('目录无权限')
  })
})
