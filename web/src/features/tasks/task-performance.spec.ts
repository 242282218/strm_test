import { describe, expect, it } from 'vitest'

import type { TaskLog, TaskResponse } from '@/features/tasks/api/tasks'
import { buildTaskStats, buildTaskViewState, mergeTaskUpdate } from './task-performance'

const createTask = (overrides: Partial<TaskResponse> = {}): TaskResponse => ({
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
  ...overrides,
})

const createLog = (message: string, ts: number): TaskLog => ({
  ts,
  level: 'info',
  message,
})

describe('task-performance', () => {
  it('counts task stats in a single pass', () => {
    const tasks = [
      createTask({ id: 1, status: 'planning' }),
      createTask({ id: 2, status: 'running' }),
      createTask({ id: 3, status: 'completed' }),
      createTask({ id: 4, status: 'failed' }),
      createTask({ id: 5, status: 'partial_success' }),
    ]

    expect(buildTaskStats(tasks)).toEqual({
      total: 5,
      running: 2,
      completed: 1,
      failed: 2,
    })
  })

  it('builds paged view state in a single pass', () => {
    const tasks = [
      createTask({ id: 1, status: 'pending', task_type: 'strm_generation' }),
      createTask({ id: 2, status: 'running', task_type: 'file_sync' }),
      createTask({ id: 3, status: 'completed', task_type: 'rename' }),
      createTask({ id: 4, status: 'failed', task_type: 'rename' }),
    ]

    expect(buildTaskViewState(tasks, { status: 'running', type: '' }, 1, 20)).toEqual({
      page: 1,
      filteredCount: 1,
      visibleTasks: [tasks[1]],
    })

    expect(buildTaskViewState(tasks, { status: '', type: 'rename' }, 1, 1)).toEqual({
      page: 1,
      filteredCount: 2,
      visibleTasks: [tasks[2]],
    })
  })

  it('falls back to the last available page when filters shrink the result set', () => {
    const tasks = [
      createTask({ id: 1, status: 'pending', task_type: 'strm_generation' }),
      createTask({ id: 2, status: 'running', task_type: 'rename' }),
      createTask({ id: 3, status: 'completed', task_type: 'rename' }),
      createTask({ id: 4, status: 'failed', task_type: 'rename' }),
    ]

    expect(buildTaskViewState(tasks, { status: '', type: 'rename' }, 5, 2)).toEqual({
      page: 2,
      filteredCount: 3,
      visibleTasks: [tasks[3]],
    })
  })

  it('keeps the same detail task reference when websocket updates do not touch it', () => {
    const tasks = [
      createTask({ id: 1, status: 'pending', progress: 10, logs: [createLog('a', 1)] }),
      createTask({ id: 2, status: 'running', progress: 30, logs: [] }),
    ]

    const nextTasks = mergeTaskUpdate(tasks, {
      task_id: '2',
      status: 'reviewing',
      progress: 80,
      logs: [createLog('review', 3)],
    })

    const currentDetailTask = tasks[0]
    const nextDetailTask = nextTasks.find((task) => task.id === currentDetailTask?.id)

    expect(nextDetailTask).toBe(currentDetailTask)
  })
})
