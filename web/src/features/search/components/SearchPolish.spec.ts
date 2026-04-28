import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import SearchHero from './SearchHero.vue'
import SearchFilters from './SearchFilters.vue'
import SearchEmpty from './SearchEmpty.vue'

vi.mock('@/components/icons', () => {
  const createIcon = (name: string) => ({
    name,
    template: `<span data-icon="${name}" />`,
  })

  return {
    Collection: createIcon('Collection'),
    Search: createIcon('Search'),
    Filter: createIcon('Filter'),
    Download: createIcon('Download'),
    Star: createIcon('Star'),
    ArrowRight: createIcon('ArrowRight'),
    FolderOpened: createIcon('FolderOpened'),
  }
})

describe('SearchHero', () => {
  it('renders a compact page header shell with supporting copy and search slot', () => {
    const wrapper = mount(SearchHero, {
      slots: {
        default: '<div class="search-slot-probe">SearchBox</div>',
      },
      global: {
        plugins: [ElementPlus],
      },
    })

    expect(wrapper.classes()).toContain('page-surface')
    expect(wrapper.find('.hero-kicker').text()).toBe('搜索中心')
    expect(wrapper.find('.hero-title').text()).toBe('资源搜索')
    expect(wrapper.find('.hero-supporting').text()).toContain('夸克网盘')
    expect(wrapper.find('.hero-search-slot .search-slot-probe').exists()).toBe(true)
  })
})

describe('SearchFilters', () => {
  it('renders the results info bar as a compact page surface', () => {
    const wrapper = mount(SearchFilters, {
      props: {
        visible: true,
      },
      global: {
        plugins: [ElementPlus],
      },
    })

    expect(wrapper.find('.results-info-bar').classes()).toContain('page-surface')
    expect(wrapper.find('.info-chip').text()).toContain('夸克资源')
    expect(wrapper.find('.sort-pill').text()).toContain('默认按评分排序')
  })
})

describe('SearchEmpty', () => {
  it('renders the empty result state with shared empty-state copy', () => {
    const wrapper = mount(SearchEmpty, {
      props: {
        type: 'empty',
      },
      global: {
        plugins: [ElementPlus],
      },
    })

    expect(wrapper.find('.search-empty-shell').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无匹配结果')
    expect(wrapper.text()).toContain('试试更具体的片名')
  })

  it('renders the initial state as a compact guidance panel', () => {
    const wrapper = mount(SearchEmpty, {
      props: {
        type: 'initial',
      },
      global: {
        plugins: [ElementPlus],
      },
    })

    expect(wrapper.find('.search-guide-shell').exists()).toBe(true)
    expect(wrapper.findAll('.search-guide-item')).toHaveLength(3)
    expect(wrapper.text()).toContain('输入片名或关键词')
    expect(wrapper.text()).toContain('优先查看评分更高的结果')
  })
})
