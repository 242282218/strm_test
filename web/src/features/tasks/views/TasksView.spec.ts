import { nextTick } from 'vue'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import TasksView from './TasksView.vue'

const taskApiMocks = vi.hoisted(() => ({
  getTasks: vi.fn(),
  getTask: vi.fn(),
  cancelTask: vi.fn(),
  deleteTask: vi.fn(),
  getTaskStatusLabel: vi.fn((status: string) => status),
  getTaskStatusType: vi.fn(() => 'info'),
  getTaskTypeLabel: vi.fn((type: string) => type)
}))

const notificationMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn()
}))

vi.mock('@/features/tasks/api/tasks', () => taskApiMocks)

vi.mock('@/composables', () => ({
  useLoading: () => ({
    loading: { __v_isRef: true, value: false },
    withLoading: async (fn: () => Promise<void>) => {
      await fn()
    }
  }),
  useNotification: () => notificationMocks,
  useAsyncNotify: () => ({
    withConfirm: async (fn: () => Promise<void>) => {
      await fn()
    }
  })
}))

vi.mock('@/features/tasks/components/CreateTaskDialog.vue', () => ({
  default: {
    name: 'CreateTaskDialog',
    props: {
      modelValue: {
        type: Boolean,
        default: false
      },
      initialTaskType: {
        type: String,
        default: ''
      }
    },
    emits: ['update:modelValue', 'success'],
    template: `
      <div
        class="create-task-dialog-mock"
        :data-visible="String(modelValue)"
        :data-task-type="initialTaskType"
      />
    `
  }
}))

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await Promise.resolve()
  await nextTick()
}

describe('TasksView task launch routing', () => {
  const originalWebSocket = globalThis.WebSocket

  beforeEach(() => {
    vi.clearAllMocks()
    taskApiMocks.getTasks.mockResolvedValue([])
    globalThis.WebSocket = vi.fn().mockImplementation(() => ({
      close: vi.fn(),
      onmessage: null,
      onclose: null
    })) as unknown as typeof WebSocket
  })

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
  })

  it('opens the create dialog with the requested task type and clears the query on close', async () => {
    const router = createRouter({
      history: createWebHistory(),
      routes: [
        {
          path: '/tasks',
          name: 'Tasks',
          component: TasksView
        }
      ]
    })

    await router.push('/tasks?createTask=file_sync')
    await router.isReady()

    const wrapper = mount(TasksView, {
      global: {
        plugins: [router, ElementPlus]
      }
    })

    await flushUi()

    expect(taskApiMocks.getTasks).toHaveBeenCalledTimes(1)
    expect(globalThis.WebSocket).toHaveBeenCalled()
    expect(String((globalThis.WebSocket as unknown as { mock: { calls: Array<[string]> } }).mock.calls[0]?.[0])).toContain('/api/v1/tasks/ws')
    expect(wrapper.get('.create-task-dialog-mock').attributes('data-visible')).toBe('true')
    expect(wrapper.get('.create-task-dialog-mock').attributes('data-task-type')).toBe('file_sync')
    expect(wrapper.text()).toContain('快捷入口已预填')
    expect(wrapper.text()).toContain('来自概览页的快捷入口')

    wrapper.getComponent({ name: 'CreateTaskDialog' }).vm.$emit('update:modelValue', false)
    await flushUi()

    expect(router.currentRoute.value.fullPath).toBe('/tasks')
  })

  it('reloads tasks after dialog success without emitting a duplicate parent success toast', async () => {
    const router = createRouter({
      history: createWebHistory(),
      routes: [
        {
          path: '/tasks',
          name: 'Tasks',
          component: TasksView
        }
      ]
    })

    await router.push('/tasks?createTask=strm_generation')
    await router.isReady()

    const wrapper = mount(TasksView, {
      global: {
        plugins: [router, ElementPlus]
      }
    })

    await flushUi()
    taskApiMocks.getTasks.mockClear()

    wrapper.getComponent({ name: 'CreateTaskDialog' }).vm.$emit('success')
    await flushUi()

    expect(wrapper.get('.create-task-dialog-mock').attributes('data-visible')).toBe('false')
    expect(taskApiMocks.getTasks).toHaveBeenCalledTimes(1)
    expect(notificationMocks.success).not.toHaveBeenCalled()
    expect(router.currentRoute.value.fullPath).toBe('/tasks')
  })

  it('clamps the current page when filters shrink the visible task set', async () => {
    taskApiMocks.getTasks.mockResolvedValue([
      {
        id: 1,
        task_type: 'strm_generation',
        priority: 'normal',
        status: 'pending',
        progress: 0,
        total_items: 0,
        processed_items: 0,
        params: {},
        logs: [],
        created_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 2,
        task_type: 'rename',
        priority: 'normal',
        status: 'running',
        progress: 10,
        total_items: 0,
        processed_items: 0,
        params: {},
        logs: [],
        created_at: '2026-01-01T00:01:00Z',
      },
      {
        id: 3,
        task_type: 'rename',
        priority: 'normal',
        status: 'completed',
        progress: 100,
        total_items: 0,
        processed_items: 0,
        params: {},
        logs: [],
        created_at: '2026-01-01T00:02:00Z',
      },
      {
        id: 4,
        task_type: 'rename',
        priority: 'normal',
        status: 'failed',
        progress: 100,
        total_items: 0,
        processed_items: 0,
        params: {},
        logs: [],
        created_at: '2026-01-01T00:03:00Z',
      }
    ])

    const router = createRouter({
      history: createWebHistory(),
      routes: [
        {
          path: '/tasks',
          name: 'Tasks',
          component: TasksView
        }
      ]
    })

    await router.push('/tasks')
    await router.isReady()

    const wrapper = mount(TasksView, {
      global: {
        plugins: [router, ElementPlus]
      }
    })

    await flushUi()

    const vm = wrapper.vm as unknown as {
      page: number
      pageSize: number
      filterForm: {
        type: string
      }
    }

    vm.pageSize = 1
    vm.page = 5
    vm.filterForm.type = 'rename'
    await flushUi()

    expect(vm.page).toBe(3)
    expect(wrapper.text()).toContain('4')
  })
})
