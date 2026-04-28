import type { TaskLog, TaskResponse } from '@/features/tasks/api/tasks'

export interface TaskStats {
  total: number
  running: number
  completed: number
  failed: number
}

export interface TaskViewFilters {
  status: string
  type: string
}

export interface TaskViewState {
  page: number
  filteredCount: number
  visibleTasks: TaskResponse[]
}

export interface TaskUpdatePayload {
  task_id: number | string
  status?: TaskResponse['status']
  progress?: number
  logs?: TaskLog[]
}

const RUNNING_STATUSES = new Set<TaskResponse['status']>(['planning', 'running', 'reviewing'])
const FAILED_STATUSES = new Set<TaskResponse['status']>(['failed', 'partial_success'])

export function buildTaskStats(tasks: TaskResponse[]): TaskStats {
  const stats: TaskStats = {
    total: tasks.length,
    running: 0,
    completed: 0,
    failed: 0,
  }

  for (const task of tasks) {
    if (RUNNING_STATUSES.has(task.status)) {
      stats.running += 1
      continue
    }

    if (task.status === 'completed') {
      stats.completed += 1
      continue
    }

    if (FAILED_STATUSES.has(task.status)) {
      stats.failed += 1
    }
  }

  return stats
}

export function buildTaskViewState(
  tasks: TaskResponse[],
  filters: TaskViewFilters,
  page: number,
  pageSize: number,
): TaskViewState {
  const filteredTasks: TaskResponse[] = []
  let filteredCount = 0

  for (const task of tasks) {
    const statusMatch = !filters.status || task.status === filters.status
    const typeMatch = !filters.type || task.task_type === filters.type
    if (!statusMatch || !typeMatch) {
      continue
    }

    filteredTasks.push(task)
    filteredCount += 1
  }

  const safePageSize = Math.max(1, pageSize)
  const lastPage = Math.max(1, Math.ceil(filteredCount / safePageSize))
  const normalizedPage = Math.min(Math.max(1, page), lastPage)
  const start = (normalizedPage - 1) * safePageSize
  const visibleTasks = filteredTasks.slice(start, start + safePageSize)

  return {
    page: normalizedPage,
    filteredCount,
    visibleTasks,
  }
}

export function mergeTaskUpdate(tasks: TaskResponse[], update: TaskUpdatePayload): TaskResponse[] {
  const targetId = String(update.task_id)
  const index = tasks.findIndex((task) => String(task.id) === targetId)

  if (index === -1) {
    return tasks
  }

  const current = tasks[index]
  if (!current) {
    return tasks
  }

  const nextLogs = update.logs?.length ? [...current.logs, ...update.logs] : current.logs
  const nextTask: TaskResponse = {
    ...current,
    ...(update.status ? { status: update.status } : {}),
    ...(typeof update.progress === 'number' ? { progress: update.progress } : {}),
    logs: nextLogs,
  }

  if (
    nextTask.status === current.status &&
    nextTask.progress === current.progress &&
    nextTask.logs === current.logs
  ) {
    return tasks
  }

  return [
    ...tasks.slice(0, index),
    nextTask,
    ...tasks.slice(index + 1),
  ]
}
