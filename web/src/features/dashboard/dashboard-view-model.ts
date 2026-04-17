import { computed, nextTick, onMounted, onUnmounted, ref, watch, type Component } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts/core'
import type { EChartsCoreOption } from 'echarts/core'
import { LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { Clock, Collection, Cpu } from '@/components/icons'
import { useDebounce, useECharts } from '@/composables'
import {
  clearDashboardCache,
  getDashboardStats,
  getTaskTrends,
  type CacheDetail,
  type DashboardData,
  type RecentTask,
  type ServiceStatus,
  type TaskTrends,
} from '@/features/dashboard/api/dashboard'
import { getTaskStatusLabel, getTaskStatusType } from '@/features/tasks'

echarts.use([
  LineChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
])

export type TimeRange = 'week' | 'month'
export type DashboardTone = 'primary' | 'success' | 'warning' | 'info'

export interface DashboardStat {
  title: string
  value: string
  icon: string
  type: DashboardTone
  support: string
}

interface HeroSignal {
  label: string
  value: string
  detail: string
  icon: Component
  tone: DashboardTone
}

interface TypeHighlight {
  name: string
  value: number
}

interface StatusBadge {
  badge: string
  type: 'success' | 'warning' | 'danger' | 'info'
}

const ACTIVE_TASK_STATUSES = new Set(['pending', 'planning', 'running', 'reviewing'])
const WARNING_PROGRESS_STATUSES = new Set(['partial_success'])
const EXCEPTION_PROGRESS_STATUSES = new Set(['failed', 'cancelled'])

const createEmptyStats = (): DashboardStat[] => ([
  { title: 'STRM文件', value: '0', icon: 'Document', type: 'primary', support: '等待索引同步' },
  { title: '任务数量', value: '0', icon: 'List', type: 'warning', support: '等待任务记录' },
  { title: '缓存条目', value: '0', icon: 'Refresh', type: 'info', support: 'TTL 600s' },
  { title: '缓存命中', value: '0.0%', icon: 'Check', type: 'success', support: '等待缓存采样' },
])

const createEmptyCacheStats = (): CacheDetail => ({
  size: 0,
  hit_rate: 0,
  ttl: 600,
})

const createEmptyTaskTrends = (): TaskTrends => ({
  status: 'ok',
  dates: [],
  success: [],
  failed: [],
})

const readCssVar = (name: string, fallback: string) => {
  if (typeof window === 'undefined') return fallback
  const value = window.getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

const formatNumber = (num: number): string => {
  if (num >= 10000) {
    return `${(num / 10000).toFixed(1)}万`
  }

  return num.toLocaleString()
}

const formatTaskTime = (value: string): string => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const normalizeTask = (task: RecentTask): RecentTask => ({
  ...task,
  time: formatTaskTime(task.time),
})

export const formatPercent = (value: number): string => `${Number(value || 0).toFixed(1)}%`

const buildStats = (data: DashboardData): DashboardStat[] => {
  const fileTypeCount = Object.keys(data.file_types).length

  return [
    {
      title: 'STRM文件',
      value: formatNumber(data.stats.strm_count),
      icon: 'Document',
      type: 'primary',
      support: fileTypeCount > 0 ? `${fileTypeCount} 类文件谱系` : '等待文件索引同步',
    },
    {
      title: '任务数量',
      value: formatNumber(data.stats.task_count),
      icon: 'List',
      type: 'warning',
      support: data.recent_tasks.length > 0 ? `${data.recent_tasks.length} 条最近任务` : '等待任务记录',
    },
    {
      title: '缓存条目',
      value: formatNumber(data.stats.cache_entries),
      icon: 'Refresh',
      type: 'info',
      support: `TTL ${data.cache_detail.ttl}s`,
    },
    {
      title: '缓存命中',
      value: formatPercent(data.stats.cache_hit_rate),
      icon: 'Check',
      type: 'success',
      support: `${formatNumber(data.cache_detail.size)} 条缓存样本`,
    },
  ]
}

const getTrendDays = (timeRange: TimeRange) => timeRange === 'week' ? 7 : 30

const getChartTheme = () => ({
  primary: readCssVar('--primary-500', '#4f8df6'),
  success: readCssVar('--success-600', '#33b07a'),
  danger: readCssVar('--danger-600', '#e4646c'),
  warning: readCssVar('--warning-600', '#e7a83d'),
  textPrimary: readCssVar('--text-primary', '#182235'),
  textSecondary: readCssVar('--text-secondary', '#5f6f86'),
  textTertiary: readCssVar('--text-tertiary', '#7d8da5'),
  border: readCssVar('--border-light', 'rgba(120, 138, 167, 0.2)'),
  panel: readCssVar('--bg-soft', 'rgba(248, 250, 253, 0.88)'),
})

const createTaskChartOption = (trends: TaskTrends): EChartsCoreOption => {
  const theme = getChartTheme()

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: theme.panel,
      borderColor: theme.border,
      textStyle: { color: theme.textSecondary },
    },
    legend: {
      data: ['成功', '失败'],
      bottom: 0,
      textStyle: { color: theme.textSecondary },
    },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trends.dates,
      axisLine: { lineStyle: { color: theme.border } },
      axisTick: { show: false },
      axisLabel: { color: theme.textTertiary },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: theme.textTertiary },
      splitLine: { lineStyle: { color: theme.border } },
    },
    series: [
      {
        name: '成功',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        data: trends.success,
        lineStyle: { color: theme.primary, width: 3 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(79, 141, 246, 0.24)' },
            { offset: 1, color: 'rgba(79, 141, 246, 0.04)' },
          ]),
        },
        itemStyle: { color: theme.primary },
      },
      {
        name: '失败',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        data: trends.failed,
        lineStyle: { color: theme.danger, width: 2 },
        itemStyle: { color: theme.danger },
      },
    ],
  }
}

const createEmptyFileTypeChartOption = (): EChartsCoreOption => {
  const theme = getChartTheme()

  return {
    title: {
      text: '暂无数据',
      left: 'center',
      top: 'center',
      textStyle: { color: theme.textTertiary, fontSize: 14, fontWeight: 600 },
    },
    series: [],
  }
}

const createFileTypeChartOption = (fileTypes: Record<string, number>): EChartsCoreOption => {
  const theme = getChartTheme()
  const colors = [
    theme.primary,
    readCssVar('--primary-400', '#73a4ff'),
    theme.success,
    theme.warning,
    readCssVar('--info-600', '#4b9fd8'),
    readCssVar('--primary-700', '#3569c8'),
    readCssVar('--text-tertiary', '#7d8da5'),
  ]

  const data = Object.entries(fileTypes).map(([name, value], index) => ({
    name: name.toUpperCase(),
    value,
    itemStyle: { color: colors[index % colors.length] },
  }))

  if (data.length === 0) {
    return createEmptyFileTypeChartOption()
  }

  return {
    title: { show: false },
    tooltip: {
      trigger: 'item',
      backgroundColor: theme.panel,
      borderColor: theme.border,
      textStyle: { color: theme.textSecondary },
    },
    legend: {
      bottom: '5%',
      left: 'center',
      textStyle: { color: theme.textSecondary },
    },
    series: [
      {
        name: '文件类型',
        type: 'pie',
        radius: ['42%', '72%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 12,
          borderColor: readCssVar('--bg-primary', '#ffffff'),
          borderWidth: 2,
        },
        label: { show: false, position: 'center' },
        emphasis: {
          label: {
            show: true,
            fontSize: 18,
            fontWeight: 700,
            color: theme.textPrimary,
          },
        },
        labelLine: { show: false },
        data,
      },
    ],
  }
}

const getTaskTypeTag = (type: string) => {
  const map: Record<string, string> = {
    file_sync: 'primary',
    strm_generation: 'success',
    scrape: 'warning',
    rename: 'info',
  }
  return map[type] || 'info'
}

const getStatusType = (status: string) => getTaskStatusType(status)

const getStatusLabel = (status: string) => getTaskStatusLabel(status)

const getProgressStatus = (status: string) => {
  if (status === 'completed') {
    return 'success'
  }

  if (WARNING_PROGRESS_STATUSES.has(status)) {
    return 'warning'
  }

  if (EXCEPTION_PROGRESS_STATUSES.has(status)) {
    return 'exception'
  }

  return ''
}

export function useDashboardViewModel() {
  const isInitialLoading = ref(true)
  const isRefreshing = ref(false)
  const isClearingCache = ref(false)
  const timeRange = ref<TimeRange>('week')

  const stats = ref<DashboardStat[]>(createEmptyStats())
  const recentTasks = ref<RecentTask[]>([])
  const services = ref<ServiceStatus[]>([])
  const cacheStats = ref<CacheDetail>(createEmptyCacheStats())
  const fileTypes = ref<Record<string, number>>({})
  const taskTrends = ref<TaskTrends>(createEmptyTaskTrends())

  const taskChartApi = useECharts({ lazy: true })
  const fileChartApi = useECharts({ lazy: true })
  const taskChartRef = taskChartApi.chartRef
  const fileChartRef = fileChartApi.chartRef

  const timeRangeLabel = computed(() => timeRange.value === 'week' ? '7 天' : '30 天')

  const topFileTypes = computed<TypeHighlight[]>(() => {
    return Object.entries(fileTypes.value)
      .sort((left, right) => right[1] - left[1])
      .slice(0, 3)
      .map(([name, value]) => ({
        name: name.toUpperCase(),
        value,
      }))
  })

  const totalFileCount = computed(() => {
    return Object.values(fileTypes.value).reduce((sum, value) => sum + value, 0)
  })

  const runningServiceCount = computed(() => {
    return services.value.filter(service => service.status === 'running').length
  })

  const latestTask = computed(() => recentTasks.value[0] ?? null)

  const activeTaskCount = computed(() => {
    return recentTasks.value.filter(task => ACTIVE_TASK_STATUSES.has(task.status)).length
  })

  const latestTaskStatus = computed(() => {
    if (!latestTask.value) {
      return {
        label: '等待中',
        type: 'info' as const,
      }
    }

    return {
      label: getStatusLabel(latestTask.value.status),
      type: getStatusType(latestTask.value.status),
    }
  })

  const serviceSummary = computed<StatusBadge>(() => {
    if (services.value.length === 0) {
      return {
        badge: '等待同步',
        type: 'info',
      }
    }

    if (runningServiceCount.value === services.value.length) {
      return {
        badge: '全部在线',
        type: 'success',
      }
    }

    return {
      badge: `${services.value.length - runningServiceCount.value} 项告警`,
      type: 'warning',
    }
  })

  const heroSignals = computed<HeroSignal[]>(() => {
    const fileMix = topFileTypes.value.map(fileType => fileType.name).join(' · ')
    const serviceDetail = services.value.length === 0
      ? '等待服务状态同步'
      : runningServiceCount.value === services.value.length
        ? '关键服务全部正常'
        : `${services.value.length - runningServiceCount.value} 项需要关注`
    const taskDetail = latestTask.value
      ? `最近：${latestTask.value.name}`
      : '等待最近任务记录'
    const typeDetail = fileMix || '等待文件索引同步'

    return [
      {
        label: '在线服务',
        value: services.value.length === 0 ? '待同步' : `${runningServiceCount.value} / ${services.value.length}`,
        detail: serviceDetail,
        icon: Cpu,
        tone: services.value.length === 0 ? 'primary' : runningServiceCount.value === services.value.length ? 'success' : 'warning',
      },
      {
        label: '任务队列',
        value: recentTasks.value.length === 0 ? '0' : `${activeTaskCount.value} 活跃`,
        detail: taskDetail,
        icon: Clock,
        tone: activeTaskCount.value > 0 ? 'warning' : 'primary',
      },
      {
        label: '文件谱系',
        value: `${Object.keys(fileTypes.value).length} 类`,
        detail: typeDetail,
        icon: Collection,
        tone: topFileTypes.value.length > 0 ? 'info' : 'primary',
      },
    ]
  })

  const formatTypeShare = (value: number): string => {
    if (totalFileCount.value === 0) {
      return '0%'
    }

    return `${Math.round((value / totalFileCount.value) * 100)}%`
  }

  const syncDashboardStats = (data: DashboardData) => {
    recentTasks.value = data.recent_tasks.map(normalizeTask)
    services.value = data.services
    cacheStats.value = data.cache_detail
    fileTypes.value = data.file_types
    stats.value = buildStats(data)
  }

  const updateTaskChart = () => {
    taskChartApi.setOption(createTaskChartOption(taskTrends.value))
  }

  const updateFileTypeChart = () => {
    fileChartApi.setOption(createFileTypeChartOption(fileTypes.value), true)
  }

  const renderDashboardCharts = () => {
    updateTaskChart()
    updateFileTypeChart()
  }

  const initDashboardCharts = async () => {
    await nextTick()
    taskChartApi.initChart()
    fileChartApi.initChart()
    renderDashboardCharts()
  }

  const fetchDashboardSnapshot = async () => {
    const [data, trends] = await Promise.all([
      getDashboardStats(),
      getTaskTrends(getTrendDays(timeRange.value)),
    ])

    syncDashboardStats(data)
    taskTrends.value = trends
  }

  const initializeDashboard = async () => {
    try {
      await fetchDashboardSnapshot()
    } catch (error) {
      console.error('获取仪表盘数据失败:', error)
      ElMessage.error('获取仪表盘数据失败')
    } finally {
      isInitialLoading.value = false
      await initDashboardCharts()
    }
  }

  const refreshDashboard = async () => {
    if (isRefreshing.value) {
      return
    }

    isRefreshing.value = true
    try {
      await fetchDashboardSnapshot()
      renderDashboardCharts()
    } catch (error) {
      console.error('刷新仪表盘数据失败:', error)
      ElMessage.error('刷新仪表盘数据失败')
    } finally {
      isRefreshing.value = false
    }
  }

  const fetchTaskTrendData = async () => {
    try {
      taskTrends.value = await getTaskTrends(getTrendDays(timeRange.value))
      updateTaskChart()
    } catch (error) {
      console.error('获取任务趋势失败:', error)
    }
  }

  const { run: debouncedFetchTaskTrends, cancel: cancelTaskTrendFetch } = useDebounce(() => {
    void fetchTaskTrendData()
  }, 160)

  const { run: debouncedResizeCharts, cancel: cancelResizeCharts } = useDebounce(() => {
    taskChartApi.resize()
    fileChartApi.resize()
  }, 150)

  watch(timeRange, () => {
    debouncedFetchTaskTrends()
  })

  const clearCache = async () => {
    if (isClearingCache.value) {
      return
    }

    try {
      await ElMessageBox.confirm('确定要清空全部缓存吗？', '确认', {
        type: 'warning',
      })

      isClearingCache.value = true
      await clearDashboardCache()
      ElMessage.success('缓存已清空')
      await refreshDashboard()
    } catch (error) {
      if (error === 'cancel' || error === 'close') {
        return
      }

      console.error('清空缓存失败:', error)
      ElMessage.error('清空缓存失败')
    } finally {
      isClearingCache.value = false
    }
  }

  const handleResize = () => {
    debouncedResizeCharts()
  }

  onMounted(async () => {
    await initializeDashboard()
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    cancelTaskTrendFetch()
    cancelResizeCharts()
  })

  return {
    cacheStats,
    clearCache,
    fileChartRef,
    formatPercent,
    formatTypeShare,
    getProgressStatus,
    getStatusLabel,
    getStatusType,
    getTaskTypeTag,
    heroSignals,
    isClearingCache,
    isInitialLoading,
    isRefreshing,
    latestTask,
    latestTaskStatus,
    recentTasks,
    refreshDashboard,
    serviceSummary,
    services,
    stats,
    taskChartRef,
    timeRange,
    timeRangeLabel,
    topFileTypes,
  }
}
