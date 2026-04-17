import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus from 'element-plus'

import CategoryStrategyView from './CategoryStrategyView.vue'

const categoryStrategyApiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  update: vi.fn(),
  preview: vi.fn()
}))

const feedbackMocks = vi.hoisted(() => ({
  showError: vi.fn(),
  showSuccess: vi.fn()
}))

vi.mock('@/features/category-strategy/api/categoryStrategy', () => ({
  categoryStrategyApi: categoryStrategyApiMocks
}))

vi.mock('@/utils/error', () => feedbackMocks)

type CategoryStrategyVm = {
  preview: {
    file_name: string
    media_type: 'auto' | 'movie' | 'tv'
    result: {
      category_key: 'anime' | 'movie' | 'tv'
      category_folder: string
    } | null
  }
}

const asVm = (value: unknown): CategoryStrategyVm => value as CategoryStrategyVm

async function flushUi(): Promise<void> {
  await flushPromises()
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await flushPromises()
}

describe('CategoryStrategyView', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    categoryStrategyApiMocks.get.mockResolvedValue({
      enabled: true,
      anime_keywords: ['anime', 'animation', '动漫', '番剧'],
      folder_names: {
        anime: '动漫文件夹',
        movie: '电影',
        tv: '电视剧'
      }
    })
    categoryStrategyApiMocks.update.mockResolvedValue({
      enabled: true,
      anime_keywords: ['anime', 'animation', '动漫', '番剧'],
      folder_names: {
        anime: '动漫文件夹',
        movie: '电影',
        tv: '电视剧'
      }
    })
    categoryStrategyApiMocks.preview.mockResolvedValue({
      category_key: 'anime',
      category_folder: '动漫文件夹'
    })
  })

  it('renders the hero summary, mapping cards, and preview workbench after loading the strategy', async () => {
    const wrapper = mount(CategoryStrategyView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()

    expect(categoryStrategyApiMocks.get).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('二级分类策略、目录映射与样本预判集中收口')
    expect(wrapper.text()).toContain('动漫关键词')
    expect(wrapper.text()).toContain('4 个')
    expect(wrapper.text()).toContain('动漫文件夹')
    expect(wrapper.find('[data-testid="category-strategy-preview"]').exists()).toBe(true)
  })

  it('runs preview and updates the focus card with the resolved category result', async () => {
    const wrapper = mount(CategoryStrategyView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()

    const vm = asVm(wrapper.vm)
    vm.preview.file_name = 'Naruto.S01E01.1080p.mkv'
    await nextTick()

    await wrapper.get('[data-testid="category-strategy-preview-button"]').trigger('click')
    await flushUi()

    expect(categoryStrategyApiMocks.preview).toHaveBeenCalledWith({
      file_name: 'Naruto.S01E01.1080p.mkv',
      media_type: 'auto'
    })
    expect(wrapper.text()).toContain('最近一次预判')
    expect(wrapper.text()).toContain('anime')
    expect(wrapper.text()).toContain('动漫文件夹')
  })

  it('saves the current rule set through the existing update API', async () => {
    const wrapper = mount(CategoryStrategyView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()

    await wrapper.get('[data-testid="category-strategy-save-button"]').trigger('click')
    await flushUi()

    expect(categoryStrategyApiMocks.update).toHaveBeenCalledWith({
      enabled: true,
      anime_keywords: ['anime', 'animation', '动漫', '番剧'],
      folder_names: {
        anime: '动漫文件夹',
        movie: '电影',
        tv: '电视剧'
      }
    })
    expect(feedbackMocks.showSuccess).toHaveBeenCalledWith('分类策略已保存')
  })
})
