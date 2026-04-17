import { beforeEach, describe, expect, it, vi } from 'vitest'

import api from '@/api/index'
import { cancelTask, createTask, deleteTask, getTask, getTaskLogs, getTasks } from './tasks'

const apiClientMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/index', () => ({
  default: apiClientMocks,
}))

type MockedApi = {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

const mockedApi = api as unknown as MockedApi

describe('tasks api canonical routes', () => {
  beforeEach(() => {
    mockedApi.get.mockReset()
    mockedApi.post.mockReset()
    mockedApi.delete.mockReset()
  })

  it('uses the canonical v1 task collection routes', async () => {
    mockedApi.post.mockResolvedValue({ id: 1 })
    mockedApi.get.mockResolvedValue([{ id: 1 }])

    await createTask({ task_type: 'file_sync', params: {} })
    await getTasks({ status: 'running', skip: 0, limit: 20 })

    expect(mockedApi.post).toHaveBeenCalledWith('/v1/tasks', {
      task_type: 'file_sync',
      params: {},
    })
    expect(mockedApi.get).toHaveBeenCalledWith('/v1/tasks', {
      params: { status: 'running', skip: 0, limit: 20 },
    })
  })

  it('uses the canonical v1 task detail routes', async () => {
    mockedApi.get.mockResolvedValue({ id: 7 })
    mockedApi.post.mockResolvedValue({ status: 'success' })
    mockedApi.delete.mockResolvedValue({ status: 'success' })

    await getTask(7)
    await cancelTask(7)
    await deleteTask(7)
    await getTaskLogs(7)

    expect(mockedApi.get).toHaveBeenNthCalledWith(1, '/v1/tasks/7')
    expect(mockedApi.post).toHaveBeenCalledWith('/v1/tasks/7/cancel')
    expect(mockedApi.delete).toHaveBeenCalledWith('/v1/tasks/7')
    expect(mockedApi.get).toHaveBeenNthCalledWith(2, '/v1/tasks/7/logs')
  })
})
