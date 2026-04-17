import api from '../../../api/index'

export interface TaskOrchestrationMetadata {
  trace_id?: string
}

export interface TaskParams {
  source_dir?: string
  target_dir?: string
  media_type?: 'auto' | 'movie' | 'tv'
  recursive?: boolean
  remote_path?: string
  local_path?: string
  sync_mode?: 'download' | 'upload' | 'bidirectional'
  path?: string
  force_update?: boolean
  pattern?: 'standard' | 'plex' | 'emby'
  preview?: boolean
  orchestration?: TaskOrchestrationMetadata
  [key: string]: unknown
}

export interface TaskCreateRequest {
  task_type: 'strm_generation' | 'file_sync' | 'scrape' | 'rename'
  priority?: 'low' | 'normal' | 'high'
  params: TaskParams
}

export interface TaskLog {
  ts: number
  level: string
  message: string
  agent?: string
  stage?: string
  retry_in?: number
}

export interface TaskResponse {
  id: number
  task_type: string
  priority: string
  status: 'pending' | 'planning' | 'running' | 'reviewing' | 'completed' | 'partial_success' | 'failed' | 'cancelled'
  progress: number
  total_items: number
  processed_items: number
  error_message?: string
  params: TaskParams
  logs: TaskLog[]
  created_at: string
  started_at?: string
  completed_at?: string
}

/**
 * 创建任务
 */
export const createTask = (data: TaskCreateRequest): Promise<TaskResponse> => {
  return api.post('/v1/tasks', data)
}

/**
 * 获取任务列表
 */
export const getTasks = (params?: { 
  status?: string
  skip?: number
  limit?: number 
}): Promise<TaskResponse[]> => {
  return api.get('/v1/tasks', { params })
}

/**
 * 获取单个任务
 */
export const getTask = (id: number): Promise<TaskResponse> => {
  return api.get(`/v1/tasks/${id}`)
}

/**
 * 取消任务
 */
export const cancelTask = (id: number): Promise<{ status: string }> => {
  return api.post(`/v1/tasks/${id}/cancel`)
}

/**
 * 删除任务
 */
export const deleteTask = (id: number): Promise<{ status: string }> => {
  return api.delete(`/v1/tasks/${id}`)
}

/**
 * 获取任务日志
 */
export const getTaskLogs = (id: number): Promise<TaskLog[]> => {
  return api.get(`/v1/tasks/${id}/logs`)
}

/**
 * 获取任务类型标签
 */
export const getTaskTypeLabel = (type: string): string => {
  const labels: Record<string, string> = {
    strm_generation: 'STRM生成',
    file_sync: '文件同步',
    scrape: '媒体刮削',
    rename: '智能重命名'
  }
  return labels[type] || type
}

/**
 * 获取任务状态标签
 */
export const getTaskStatusLabel = (status: string): string => {
  const labels: Record<string, string> = {
    pending: '待处理',
    planning: '规划中',
    running: '运行中',
    reviewing: '审核中',
    completed: '已完成',
    partial_success: '部分完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return labels[status] || status
}

/**
 * 获取任务状态标签类型
 */
export const getTaskStatusType = (status: string): string => {
  const types: Record<string, string> = {
    pending: 'info',
    planning: 'info',
    running: 'primary',
    reviewing: 'warning',
    completed: 'success',
    partial_success: 'warning',
    failed: 'danger',
    cancelled: 'info'
  }
  return types[status] || 'info'
}
