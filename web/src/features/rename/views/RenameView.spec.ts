import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import RenameView from './RenameView.vue'
import type { ExecuteResponse, PreviewResponse, RenameTask } from '../api/rename'

const renameApiMocks = vi.hoisted(() => ({
  previewRename: vi.fn(),
  executeRename: vi.fn(),
}))

const messageMocks = vi.hoisted(() => ({
  info: vi.fn(),
  warning: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock('../api/rename', () => ({
  previewRename: renameApiMocks.previewRename,
  executeRename: renameApiMocks.executeRename,
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: messageMocks,
  }
})

interface RenameViewVm {
  currentStep: number
  selectedPath: string
  options: {
    recursive: boolean
    autoConfirm: boolean
  }
  filterType: 'all' | 'pending' | 'confirmed'
  previewData: PreviewResponse | null
  analysisProgress: PreviewResponse['progress']
  selectedTasks: string[]
  editDialogVisible: boolean
  editingTask: Partial<RenameTask>
  resultDialogVisible: boolean
  executeResult: ExecuteResponse | null
  openPathSelector: () => void
  startAnalysis: () => Promise<void>
  handleSelectAll: (value: boolean) => void
  editTask: (task: RenameTask) => void
  saveTaskEdit: () => void
  removeTask: (task: RenameTask) => void
  executeRenameOperation: () => Promise<void>
  resetWorkflow: () => void
}

const asRenameViewVm = (vm: unknown): RenameViewVm => vm as RenameViewVm

const createTask = (overrides: Partial<RenameTask> = {}): RenameTask => ({
  source_path: '/media/input/alpha.mkv',
  new_filename: 'Alpha (2024).mkv',
  media_type: 'movie',
  title: 'Alpha',
  cleaned_title: 'Alpha',
  confidence: 0.95,
  needs_confirmation: false,
  ...overrides,
})

const createPreviewResponse = (tasks: RenameTask[]): PreviewResponse => ({
  tasks,
  progress: [
    { message: '扫描目录', current: 1, total: tasks.length },
    { message: '生成预览', current: tasks.length, total: tasks.length },
  ],
  total_tasks: tasks.length,
  needs_confirmation: tasks.filter(task => task.needs_confirmation).length,
})

const createExecuteResponse = (overrides: Partial<ExecuteResponse> = {}): ExecuteResponse => ({
  success_count: 1,
  failed_count: 0,
  success: [
    {
      source_path: '/media/input/alpha.mkv',
      target_path: '/media/output/Alpha (2024).mkv',
      success: true,
    },
  ],
  failed: [],
  ...overrides,
})

describe('RenameView', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('opens the path selector and loads preview data into the workflow', async () => {
    const previewResponse = createPreviewResponse([
      createTask(),
      createTask({
        source_path: '/media/input/beta.mkv',
        new_filename: 'Beta S01E01.mkv',
        media_type: 'tv',
        title: 'Beta',
        cleaned_title: 'Beta',
        confidence: 0.63,
        needs_confirmation: true,
        confirmation_reason: 'low confidence',
      }),
    ])
    renameApiMocks.previewRename.mockResolvedValue(previewResponse)

    const wrapper = mount(RenameView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    })
    const vm = asRenameViewVm(wrapper.vm)

    vm.openPathSelector()
    await flushPromises()

    expect(vm.selectedPath).toBe('/media/movies')
    expect(messageMocks.info).toHaveBeenCalledWith('文件夹选择功能开发中')

    await vm.startAnalysis()
    await flushPromises()

    expect(renameApiMocks.previewRename).toHaveBeenCalledWith({
      path: '/media/movies',
      recursive: true,
    })
    expect(vm.currentStep).toBe(2)
    expect(vm.previewData).toEqual(previewResponse)
    expect(vm.analysisProgress).toEqual(previewResponse.progress)
    expect(vm.selectedTasks).toEqual(previewResponse.tasks.map(task => task.source_path))
    expect(messageMocks.success).toHaveBeenCalledWith('分析完成，共发现 2 个媒体文件')
  })

  it('guards missing paths and rolls the workflow back when preview loading fails', async () => {
    renameApiMocks.previewRename.mockRejectedValue(new Error('boom'))

    const wrapper = mount(RenameView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    })
    const vm = asRenameViewVm(wrapper.vm)

    await vm.startAnalysis()
    expect(renameApiMocks.previewRename).not.toHaveBeenCalled()
    expect(messageMocks.warning).toHaveBeenCalledWith('请先选择文件夹')

    vm.selectedPath = '/media/movies'
    await vm.startAnalysis()
    await flushPromises()

    expect(vm.currentStep).toBe(1)
    expect(vm.previewData).toBeNull()
    expect(messageMocks.error).toHaveBeenCalledWith('分析失败')
  })

  it('keeps filtered selection, edits, and skipped tasks in sync with preview state', async () => {
    const pendingTask = createTask({
      source_path: '/media/input/beta.mkv',
      new_filename: 'Beta S01E01.mkv',
      media_type: 'tv',
      title: 'Beta',
      cleaned_title: 'Beta',
      confidence: 0.63,
      needs_confirmation: true,
      confirmation_reason: 'low confidence',
    })

    const wrapper = mount(RenameView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    })
    const vm = asRenameViewVm(wrapper.vm)

    vm.previewData = createPreviewResponse([createTask(), pendingTask])
    vm.selectedTasks = vm.previewData.tasks.map(task => task.source_path)
    vm.filterType = 'pending'
    await flushPromises()

    vm.handleSelectAll(true)
    expect(vm.selectedTasks).toEqual([pendingTask.source_path])

    vm.editTask(pendingTask)
    vm.editingTask.new_filename = 'Beta S01E02.mkv'
    vm.saveTaskEdit()

    expect(vm.previewData.tasks[1]?.new_filename).toBe('Beta S01E02.mkv')
    expect(vm.editDialogVisible).toBe(false)
    expect(messageMocks.success).toHaveBeenCalledWith('已保存修改')

    vm.removeTask(pendingTask)

    expect(vm.previewData.tasks).toHaveLength(1)
    expect(vm.previewData.total_tasks).toBe(1)
    expect(vm.selectedTasks).toEqual([])
    expect(messageMocks.success).toHaveBeenCalledWith('已跳过该文件')
  })

  it('submits the current selection for execution and resets the workflow afterwards', async () => {
    const executeResponse = createExecuteResponse()
    renameApiMocks.executeRename.mockResolvedValue(executeResponse)

    const wrapper = mount(RenameView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    })
    const vm = asRenameViewVm(wrapper.vm)

    vm.selectedPath = '/media/movies'
    vm.previewData = createPreviewResponse([createTask()])
    vm.selectedTasks = ['/media/input/alpha.mkv']

    await vm.executeRenameOperation()
    await flushPromises()

    expect(renameApiMocks.executeRename).toHaveBeenCalledWith({
      path: '/media/movies',
      selected_tasks: ['/media/input/alpha.mkv'],
      recursive: true,
    })
    expect(vm.executeResult).toEqual(executeResponse)
    expect(vm.resultDialogVisible).toBe(true)
    expect(messageMocks.success).toHaveBeenCalledWith('所有文件重命名成功')

    vm.resetWorkflow()

    expect(vm.currentStep).toBe(1)
    expect(vm.selectedPath).toBe('')
    expect(vm.previewData).toBeNull()
    expect(vm.selectedTasks).toEqual([])
    expect(vm.analysisProgress).toEqual([])
  })
})
