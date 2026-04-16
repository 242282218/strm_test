import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import FileList from './FileList.vue'
import FileSelectorDialog from './FileSelectorDialog.vue'

const fileManagerMocks = vi.hoisted(() => ({
  store: {
    items: [] as Array<Record<string, unknown>>,
    selectedIds: new Set<string>(),
    browse: vi.fn(),
  },
  browseMock: vi.fn(),
}))

vi.mock('@/features/file-manager/stores/file-manager', () => ({
  useFileManagerStore: () => fileManagerMocks.store,
}))

vi.mock('@/features/file-manager/api/file-manager', () => ({
  fileManagerApi: {
    browse: fileManagerMocks.browseMock,
  },
}))

vi.mock('@/components/icons', () => {
  const createIcon = (name: string) => ({
    name,
    template: `<span data-icon="${name}" />`,
  })

  return {
    Folder: createIcon('Folder'),
    Document: createIcon('Document'),
    ArrowLeft: createIcon('ArrowLeft'),
    Refresh: createIcon('Refresh'),
    FolderOpened: createIcon('FolderOpened'),
  }
})

describe('FileList', () => {
  beforeEach(() => {
    fileManagerMocks.store.items = [
      {
        id: 'folder-1',
        name: '电影合集',
        file_type: 'folder',
        size: 0,
        updated_at: '2026-03-17T08:00:00.000Z',
      },
      {
        id: 'file-1',
        name: 'episode-01.mkv',
        file_type: 'file',
        size: 1024,
        updated_at: '2026-03-17T09:00:00.000Z',
      },
    ]
    fileManagerMocks.store.selectedIds = new Set<string>()
    fileManagerMocks.store.browse = vi.fn()
  })

  it('renders the table inside the new list shell with semantic meta pills', async () => {
    const wrapper = mount(FileList, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.find('.file-list-shell').exists()).toBe(true)
    expect(wrapper.find('.file-list-table').exists()).toBe(true)
    expect(wrapper.findAll('.item-meta-pill')).toHaveLength(2)
    expect(wrapper.text()).toContain('文件夹')
  })

  it('uses the action column to enter folders without leaving a dead details button for files', async () => {
    const wrapper = mount(FileList, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const actionButtons = wrapper.findAll('.el-button')
    expect(actionButtons).toHaveLength(1)
    const primaryActionButton = actionButtons[0]
    expect(primaryActionButton).toBeDefined()
    expect(primaryActionButton!.text()).toBe('进入')
    expect(wrapper.text()).not.toContain('详情')

    await primaryActionButton!.trigger('click')

    expect(fileManagerMocks.store.browse).toHaveBeenCalledWith('folder-1')
  })
})

describe('FileSelectorDialog', () => {
  beforeEach(() => {
    fileManagerMocks.browseMock.mockReset()
    fileManagerMocks.browseMock.mockResolvedValue({
      data: {
        items: [],
        path: '0',
        parent_path: null,
      },
    })
  })

  it('renders the selector as a surfaced shell and shows the shared empty state copy', async () => {
    const wrapper = mount(FileSelectorDialog, {
      props: {
        visible: true,
        storage: 'quark',
      },
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
          transition: false,
          'el-dialog': {
            props: ['modelValue', 'title'],
            template: `
              <div v-if="modelValue" class="el-dialog-stub">
                <div class="el-dialog-stub__title">{{ title }}</div>
                <slot />
                <slot name="footer" />
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    expect(fileManagerMocks.browseMock).toHaveBeenCalledWith({
      storage: 'quark',
      path: '0',
      size: 500,
    })
    expect(wrapper.find('.selector-shell').exists()).toBe(true)
    expect(wrapper.find('.selector-path-card').text()).toContain('根目录')
    expect(wrapper.text()).toContain('此目录暂无可选文件夹')
  })
})
