import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus from 'element-plus'

import SmartRenameView from './SmartRenameView.vue'

const smartRenameApiMocks = vi.hoisted(() => ({
  getAlgorithmsMock: vi.fn(),
  getNamingStandardsMock: vi.fn(),
  getSmartRenameStatusMock: vi.fn(),
  previewSmartRenameMock: vi.fn(),
  executeSmartRenameMock: vi.fn(),
  rollbackSmartRenameMock: vi.fn(),
  testSmartRenameAIConnectivityMock: vi.fn(),
  validateFilenameMock: vi.fn(),
  getRenameBatchesMock: vi.fn(),
  getBatchItemsMock: vi.fn(),
}))

const quarkApiMocks = vi.hoisted(() => ({
  createCloudRenameWorkflowTaskMock: vi.fn(),
  cancelCloudRenameWorkflowTaskMock: vi.fn(),
  getCloudRenameWorkflowTaskMock: vi.fn(),
  smartRenameCloudFilesMock: vi.fn(),
  executeCloudRenameMock: vi.fn(),
  testCloudRenameAIConnectivityMock: vi.fn(),
}))

const messageMocks = vi.hoisted(() => ({
  success: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
}))

const messageBoxMocks = vi.hoisted(() => ({
  confirm: vi.fn(),
}))

vi.mock('../api/smartRename', () => ({
  getAlgorithms: smartRenameApiMocks.getAlgorithmsMock,
  getNamingStandards: smartRenameApiMocks.getNamingStandardsMock,
  getSmartRenameStatus: smartRenameApiMocks.getSmartRenameStatusMock,
  previewSmartRename: smartRenameApiMocks.previewSmartRenameMock,
  executeSmartRename: smartRenameApiMocks.executeSmartRenameMock,
  rollbackSmartRename: smartRenameApiMocks.rollbackSmartRenameMock,
  testSmartRenameAIConnectivity: smartRenameApiMocks.testSmartRenameAIConnectivityMock,
  validateFilename: smartRenameApiMocks.validateFilenameMock,
  getRenameBatches: smartRenameApiMocks.getRenameBatchesMock,
  getBatchItems: smartRenameApiMocks.getBatchItemsMock,
}))

vi.mock('@/api/quark', () => ({
  createCloudRenameWorkflowTask: quarkApiMocks.createCloudRenameWorkflowTaskMock,
  cancelCloudRenameWorkflowTask: quarkApiMocks.cancelCloudRenameWorkflowTaskMock,
  getCloudRenameWorkflowTask: quarkApiMocks.getCloudRenameWorkflowTaskMock,
  smartRenameCloudFiles: quarkApiMocks.smartRenameCloudFilesMock,
  executeCloudRename: quarkApiMocks.executeCloudRenameMock,
  testCloudRenameAIConnectivity: quarkApiMocks.testCloudRenameAIConnectivityMock,
}))

vi.mock('@/components/QuarkFileBrowser.vue', () => ({
  default: {
    name: 'QuarkFileBrowser',
    template: '<div data-testid="quark-browser-stub" />',
  },
}))

vi.mock('../smart-rename-execution', () => ({
  applyCloudExecuteResponse: vi.fn(),
  applyCloudRollbackResponse: vi.fn(),
}))

vi.mock('@/components/icons', () => {
  const stub = { template: '<span />' }
  return {
    CircleCheck: stub,
    Collection: stub,
    Cpu: stub,
    Document: stub,
    Download: stub,
    FolderOpened: stub,
    InfoFilled: stub,
    Refresh: stub,
    RefreshRight: stub,
    Search: stub,
    VideoPlay: stub,
  }
})

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: messageMocks,
    ElMessageBox: messageBoxMocks,
  }
})

type PreviewRow = {
  original_path: string
  new_name: string
}

type SmartRenameViewVm = {
  localPath: string
  previewRows: PreviewRow[]
  editingItem: PreviewRow
  runPreview: () => Promise<void>
  openEditDialog: (row: PreviewRow) => void
  saveEdit: () => void
  executeSelected: () => Promise<void>
}

const asSmartRenameViewVm = (vm: unknown): SmartRenameViewVm => vm as SmartRenameViewVm

describe('SmartRenameView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    messageBoxMocks.confirm.mockResolvedValue('confirm')
    smartRenameApiMocks.getAlgorithmsMock.mockResolvedValue([
      {
        algorithm: 'ai_enhanced',
        name: 'AI 增强',
        description: '默认算法',
        features: ['TMDB 匹配'],
        recommended: true,
      },
    ])
    smartRenameApiMocks.getNamingStandardsMock.mockResolvedValue([
      {
        standard: 'emby',
        name: 'Emby',
        description: 'Emby 命名',
        movie_example: 'Movie (2024)',
        tv_example: 'Show - S01E01',
        specials_example: 'Season 00',
      },
    ])
    smartRenameApiMocks.getSmartRenameStatusMock.mockResolvedValue({
      available: true,
      smart_rename_service: true,
      tmdb_connected: true,
      ai_available: true,
      algorithms: ['ai_enhanced'],
      naming_standards: ['emby'],
    })
    smartRenameApiMocks.getRenameBatchesMock.mockResolvedValue([])
    smartRenameApiMocks.getBatchItemsMock.mockResolvedValue([])
    smartRenameApiMocks.previewSmartRenameMock.mockResolvedValue({
      batch_id: 'batch-local-1',
      target_path: 'D:/Media',
      total_items: 1,
      parsed_items: 1,
      matched_items: 1,
      skipped_items: 0,
      needs_confirmation: 0,
      algorithm_used: 'ai_enhanced',
      naming_standard: 'emby',
      items: [
        {
          original_path: 'D:/Media/Movie.mkv',
          original_name: 'Movie.mkv',
          new_name: 'Movie (2024).mkv',
          media_type: 'movie',
          tmdb_id: 100,
          tmdb_title: 'Movie',
          overall_confidence: 0.93,
          status: 'parsed',
          needs_confirmation: false,
        },
      ],
    })
    smartRenameApiMocks.executeSmartRenameMock.mockResolvedValue({
      batch_id: 'batch-local-1',
      total_items: 1,
      success_items: 1,
      failed_items: 0,
      skipped_items: 0,
    })
  })

  it('keeps only the local preview and execute flow visible', async () => {
    const wrapper = mount(SmartRenameView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('本地路径')
    expect(wrapper.text()).toContain('生成预览')
    expect(wrapper.text()).toContain('执行重命名')
    expect(wrapper.text()).not.toContain('夸克云盘')
    expect(wrapper.text()).not.toContain('AI 连通性测试')
    expect(wrapper.text()).not.toContain('批次记录')
    expect(wrapper.text()).not.toContain('回滚最近执行')
    expect(wrapper.text()).not.toContain('导出预览')
    expect(wrapper.text()).not.toContain('批量确认')
  })

  it('runs local preview and renders the simplified result list', async () => {
    const wrapper = mount(SmartRenameView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const vm = asSmartRenameViewVm(wrapper.vm)
    vm.localPath = 'D:/Media'
    await nextTick()
    await vm.runPreview()
    await flushPromises()

    expect(smartRenameApiMocks.previewSmartRenameMock).toHaveBeenCalledWith(
      expect.objectContaining({
        target_path: 'D:/Media',
        algorithm: 'ai_enhanced',
        naming_standard: 'emby',
        recursive: true,
      }),
    )
    expect(wrapper.text()).toContain('Movie.mkv')
    expect(wrapper.text()).toContain('Movie (2024).mkv')
    expect(wrapper.text()).not.toContain('按原文件名/新文件名搜索')
    expect(wrapper.text()).not.toContain('仅选待确认')
  })

  it('sends the edited filename in the execute request', async () => {
    const wrapper = mount(SmartRenameView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const vm = asSmartRenameViewVm(wrapper.vm)
    vm.localPath = 'D:/Media'
    await nextTick()
    await vm.runPreview()
    await flushPromises()

    const row = vm.previewRows[0]
    expect(row).toBeTruthy()
    if (!row) {
      throw new Error('preview row missing')
    }

    vm.openEditDialog(row)
    vm.editingItem.new_name = 'Movie - Edited (2024).mkv'
    vm.saveEdit()
    await flushPromises()

    await vm.executeSelected()
    await flushPromises()

    expect(smartRenameApiMocks.executeSmartRenameMock).toHaveBeenCalledWith({
      batch_id: 'batch-local-1',
      operations: [
        {
          original_path: 'D:/Media/Movie.mkv',
          new_name: 'Movie - Edited (2024).mkv',
        },
      ],
    })
  })
})
