import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import FileGrid from './FileGrid.vue'

const fileManagerMocks = vi.hoisted(() => ({
  store: {
    items: [] as Array<Record<string, unknown>>,
    selectedIds: new Set<string>(),
    browse: vi.fn(),
    toggleSelection: vi.fn(),
  },
}))

vi.mock('@/features/file-manager/stores/file-manager', () => ({
  useFileManagerStore: () => fileManagerMocks.store,
}))

vi.mock('@/components/icons', () => {
  const createIcon = (name: string) => ({
    name,
    template: `<span data-icon="${name}" />`,
  })

  return {
    Folder: createIcon('Folder'),
  }
})

describe('FileGrid', () => {
  beforeEach(() => {
    fileManagerMocks.store.items = Array.from({ length: 120 }, (_, index) => ({
      id: `item-${index + 1}`,
      name: `item-${index + 1}`,
      file_type: 'file',
      size: 1024,
      extension: 'mkv',
      thumbnail: null,
    }))
    fileManagerMocks.store.selectedIds = new Set<string>()
    fileManagerMocks.store.browse = vi.fn()
    fileManagerMocks.store.toggleSelection = vi.fn()
  })

  it('renders large directories in chunks and appends more cards on demand', async () => {
    const wrapper = mount(FileGrid, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.findAll('.file-card')).toHaveLength(60)
    expect(wrapper.text()).toContain('已渲染 60 / 120 项')

    const loadMoreButton = wrapper.get('[data-testid="file-grid-load-more"]')
    await loadMoreButton.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.file-card')).toHaveLength(120)
    expect(wrapper.text()).toContain('已渲染 120 / 120 项')
    expect(wrapper.find('[data-testid="file-grid-load-more"]').exists()).toBe(false)
  })
})
