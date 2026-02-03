/**
 * 概览页面 Dashboard API 服务
 *
 * 提供首页概览所需的统计数据、任务趋势、服务状态等接口
 */
import api from './index'

/**
 * 统计数据接口
 */
export interface DashboardStats {
  strm_count: number
  task_count: number
  cache_entries: number
  cache_hit_rate: number
}

/**
 * 最近任务接口
 */
export interface RecentTask {
  name: string
  type: string
  status: string
  progress: number
  time: string
}

/**
 * 服务状态接口
 */
export interface ServiceStatus {
  name: string
  status: 'running' | 'stopped'
}

/**
 * 缓存详情接口
 */
export interface CacheDetail {
  size: number
  hit_rate: number
  ttl: number
}

/**
 * 文件类型分布接口
 */
export interface FileTypeDistribution {
  [key: string]: number
}

/**
 * 仪表盘数据响应接口
 */
export interface DashboardData {
  status: string
  stats: DashboardStats
  recent_tasks: RecentTask[]
  services: ServiceStatus[]
  cache_detail: CacheDetail
  file_types: FileTypeDistribution
}

/**
 * 任务趋势数据接口
 */
export interface TaskTrends {
  status: string
  dates: string[]
  success: number[]
  failed: number[]
}

/**
 * 获取仪表盘统计数据
 *
 * @returns 仪表盘完整数据
 */
export const getDashboardStats = async (): Promise<DashboardData> => {
  const response = await api.get('/dashboard/stats')
  return response as unknown as DashboardData
}

/**
 * 获取任务执行趋势
 *
 * @param days 查询天数，默认7天
 * @returns 任务趋势数据
 */
export const getTaskTrends = async (days: number = 7): Promise<TaskTrends> => {
  const response = await api.get('/dashboard/trends', { params: { days } })
  return response as unknown as TaskTrends
}
