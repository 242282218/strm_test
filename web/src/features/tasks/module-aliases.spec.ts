import { describe, expect, it } from 'vitest'

import {
  createTask as legacyCreateTask,
  getTaskStatusLabel as legacyGetTaskStatusLabel,
  getTasks as legacyGetTasks
} from '@/api/tasks'

import {
  createTask as featureCreateTask,
  getTaskStatusLabel as featureGetTaskStatusLabel,
  getTasks as featureGetTasks
} from './api/tasks'
import legacyTasksViewSource from '../../views/TasksView.vue?raw'
import legacyCreateTaskDialogSource from '../../components/CreateTaskDialog.vue?raw'

describe('tasks feature module aliases', () => {
  it('keeps legacy tasks api exports mapped to the feature module', () => {
    expect(legacyCreateTask).toBe(featureCreateTask)
    expect(legacyGetTasks).toBe(featureGetTasks)
    expect(legacyGetTaskStatusLabel).toBe(featureGetTaskStatusLabel)
  })

  it('keeps legacy tasks view and component paths mapped to the feature module', () => {
    expect(legacyTasksViewSource).toContain('@/features/tasks/views/TasksView.vue')
    expect(legacyCreateTaskDialogSource).toContain('@/features/tasks/components/CreateTaskDialog.vue')
  })
})
