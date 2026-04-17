import type { LocationQuery, LocationQueryValue } from 'vue-router'
import type { TaskCreateRequest } from './api/tasks'

export type LaunchableTaskType = TaskCreateRequest['task_type']

export const TASK_LAUNCH_QUERY_KEY = 'createTask'

const launchableTaskTypes: LaunchableTaskType[] = [
  'strm_generation',
  'file_sync',
  'scrape',
  'rename'
]

const getQueryValue = (value: LocationQueryValue | LocationQueryValue[] | undefined) => {
  return Array.isArray(value) ? value[0] : value
}

export const isLaunchableTaskType = (value: unknown): value is LaunchableTaskType => {
  return typeof value === 'string' && launchableTaskTypes.includes(value as LaunchableTaskType)
}

export const resolveTaskLaunchType = (query: LocationQuery): LaunchableTaskType | null => {
  const value = getQueryValue(query[TASK_LAUNCH_QUERY_KEY])
  return isLaunchableTaskType(value) ? value : null
}

export const buildTaskLaunchQuery = (taskType: LaunchableTaskType) => ({
  [TASK_LAUNCH_QUERY_KEY]: taskType
})
