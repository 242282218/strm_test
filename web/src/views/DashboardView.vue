<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :xs="24" :sm="12" :lg="6" v-for="stat in stats" :key="stat.title">
        <div class="stat-card" :class="stat.type">
          <div class="stat-icon">
            <el-icon size="32">
              <component :is="stat.icon" />
            </el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stat.value }}</div>
            <div class="stat-title">{{ stat.title }}</div>
          </div>
          <div class="stat-trend" v-if="stat.trend">
            <el-tag :type="stat.trend > 0 ? 'success' : 'danger'" size="small">
              {{ stat.trend > 0 ? '+' : '' }}{{ stat.trend }}%
            </el-tag>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="charts-row">
      <el-col :xs="24" :lg="16">
        <div class="chart-card">
          <div class="chart-header">
            <h3>任务执行趋势</h3>
            <el-radio-group v-model="timeRange" size="small">
              <el-radio-button value="week">本周</el-radio-button>
              <el-radio-button value="month">本月</el-radio-button>
            </el-radio-group>
          </div>
          <div ref="taskChartRef" class="chart-container"></div>
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="chart-card">
          <div class="chart-header">
            <h3>文件类型分布</h3>
          </div>
          <div ref="fileChartRef" class="chart-container"></div>
        </div>
      </el-col>
    </el-row>

    <!-- 最近任务 -->
    <el-row class="tasks-row">
      <el-col :span="24">
        <div class="tasks-card">
          <div class="card-header">
            <h3>最近任务</h3>
            <el-button type="primary" text @click="$router.push('/tasks')">
              查看全部
              <el-icon class="el-icon--right"><ArrowRight /></el-icon>
            </el-button>
          </div>
          <el-table :data="recentTasks" style="width: 100%">
            <el-table-column prop="name" label="任务名称" min-width="200">
              <template #default="{ row }">
                <div class="task-name">
                  <el-icon :size="16"><Document /></el-icon>
                  <span>{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="120">
              <template #default="{ row }">
                <el-tag :type="getTaskTypeTag(row.type)" size="small">
                  {{ getTaskTypeLabel(row.type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small" effect="dark">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" width="200">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.progress"
                  :status="getProgressStatus(row.status)"
                  :stroke-width="8"
                />
              </template>
            </el-table-column>
            <el-table-column prop="time" label="执行时间" width="180" />
          </el-table>
        </div>
      </el-col>
    </el-row>

    <!-- 系统状态 -->
    <el-row :gutter="20" class="status-row">
      <el-col :xs="24" :sm="12" :lg="8">
        <div class="status-card">
          <div class="status-header">
            <h3>服务状态</h3>
            <el-tag type="success" effect="dark" size="small">运行中</el-tag>
          </div>
          <div class="status-list">
            <div v-for="service in services" :key="service.name" class="status-item">
              <div class="status-info">
                <el-icon :size="20" :color="service.status === 'running' ? '#67C23A' : '#F56C6C'">
                  <component :is="service.status === 'running' ? 'CircleCheck' : 'CircleClose'" />
                </el-icon>
                <span>{{ service.name }}</span>
              </div>
              <el-tag :type="service.status === 'running' ? 'success' : 'danger'" size="small">
                {{ service.status === 'running' ? '正常' : '异常' }}
              </el-tag>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="8">
        <div class="status-card">
          <div class="status-header">
            <h3>缓存统计</h3>
            <el-button type="primary" text size="small" @click="clearCache">
              清空缓存
            </el-button>
          </div>
          <div class="cache-stats">
            <div class="cache-item">
              <div class="cache-value">{{ cacheStats.size }}</div>
              <div class="cache-label">缓存条目</div>
            </div>
            <div class="cache-item">
              <div class="cache-value">{{ cacheStats.hit_rate }}%</div>
              <div class="cache-label">命中率</div>
            </div>
            <div class="cache-item">
              <div class="cache-value">{{ cacheStats.ttl }}s</div>
              <div class="cache-label">TTL</div>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="8">
        <div class="status-card">
          <div class="status-header">
            <h3>快捷操作</h3>
          </div>
          <div class="quick-actions">
            <el-button type="primary" class="action-btn" @click="syncFiles">
              <el-icon><Refresh /></el-icon>
              同步文件
            </el-button>
            <el-button type="success" class="action-btn" @click="generateStrm">
              <el-icon><DocumentAdd /></el-icon>
              生成STRM
            </el-button>
            <el-button type="warning" class="action-btn" @click="validateFiles">
              <el-icon><Check /></el-icon>
              验证文件
            </el-button>
            <el-button class="action-btn" @click="openSettings">
              <el-icon><Setting /></el-icon>
              系统设置
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  Document,
  Refresh,
  DocumentAdd,
  Check,
  Setting,
  ArrowRight,
  Folder,
  List
} from '@element-plus/icons-vue'
import { getDashboardStats, getTaskTrends } from '@/api/dashboard'
import type { DashboardData, TaskTrends, RecentTask, ServiceStatus, CacheDetail } from '@/api/dashboard'

const router = useRouter()
const taskChartRef = ref<HTMLElement>()
const fileChartRef = ref<HTMLElement>()
let taskChart: echarts.ECharts | null = null
let fileChart: echarts.ECharts | null = null

const timeRange = ref('week')
const loading = ref(false)

// 统计数据
const stats = ref([
  { title: 'STRM文件', value: '0', icon: 'Document', type: 'primary', trend: 0 },
  { title: '网盘文件', value: '0', icon: 'Folder', type: 'success', trend: 0 },
  { title: '任务数量', value: '0', icon: 'List', type: 'warning', trend: 0 },
  { title: '缓存命中', value: '0%', icon: 'Refresh', type: 'info', trend: 0 }
])

// 最近任务
const recentTasks = ref<RecentTask[]>([])

// 服务状态
const services = ref<ServiceStatus[]>([])

// 缓存统计
const cacheStats = ref<CacheDetail>({
  size: 0,
  hit_rate: 0,
  ttl: 600
})

// 文件类型分布
const fileTypes = ref<Record<string, number>>({})

// 任务类型标签
const getTaskTypeTag = (type: string) => {
  const map: Record<string, string> = {
    sync: 'primary',
    generate: 'success',
    validate: 'warning',
    cleanup: 'info'
  }
  return map[type] || 'info'
}

const getTaskTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    sync: '同步',
    generate: '生成',
    validate: '验证',
    cleanup: '清理'
  }
  return map[type] || type
}

// 状态标签
const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    running: 'primary',
    success: 'success',
    pending: 'info',
    failed: 'danger'
  }
  return map[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    running: '运行中',
    success: '完成',
    pending: '等待中',
    failed: '失败'
  }
  return map[status] || status
}

const getProgressStatus = (status: string) => {
  return status === 'success' ? 'success' : status === 'failed' ? 'exception' : ''
}

/**
 * 获取仪表盘数据
 */
const fetchDashboardData = async () => {
  loading.value = true
  try {
    const data = await getDashboardStats()

    // 更新统计数据
    stats.value = [
      {
        title: 'STRM文件',
        value: formatNumber(data.stats.strm_count),
        icon: 'Document',
        type: 'primary',
        trend: 0 // 后端暂未提供趋势数据
      },
      {
        title: '任务数量',
        value: formatNumber(data.stats.task_count),
        icon: 'List',
        type: 'warning',
        trend: 0
      },
      {
        title: '缓存条目',
        value: formatNumber(data.stats.cache_entries),
        icon: 'Refresh',
        type: 'info',
        trend: 0
      },
      {
        title: '缓存命中',
        value: data.stats.cache_hit_rate.toFixed(1) + '%',
        icon: 'Check',
        type: 'success',
        trend: 0
      }
    ]

    // 更新最近任务
    recentTasks.value = data.recent_tasks.map(task => ({
      ...task,
      // 转换状态值以匹配前端显示
      status: task.status === 'stopped' ? 'pending' : task.status
    }))

    // 更新服务状态
    services.value = data.services

    // 更新缓存统计
    cacheStats.value = data.cache_detail

    // 更新文件类型分布
    fileTypes.value = data.file_types

  } catch (error) {
    console.error('获取仪表盘数据失败:', error)
    ElMessage.error('获取仪表盘数据失败')
  } finally {
    loading.value = false
  }
}

/**
 * 获取任务趋势数据
 */
const fetchTaskTrends = async () => {
  try {
    const days = timeRange.value === 'week' ? 7 : 30
    const trends = await getTaskTrends(days)
    updateTaskChart(trends)
  } catch (error) {
    console.error('获取任务趋势失败:', error)
  }
}

/**
 * 格式化数字显示
 */
const formatNumber = (num: number): string => {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return num.toLocaleString()
}

/**
 * 更新任务趋势图表
 */
const updateTaskChart = (trends: TaskTrends) => {
  if (!taskChart) return

  taskChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['成功', '失败'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trends.dates
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: '成功',
        type: 'line',
        smooth: true,
        data: trends.success,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0.05)' }
          ])
        },
        itemStyle: { color: '#3b82f6' }
      },
      {
        name: '失败',
        type: 'line',
        smooth: true,
        data: trends.failed,
        itemStyle: { color: '#ef4444' }
      }
    ]
  })
}

/**
 * 更新文件类型图表
 */
const updateFileTypeChart = () => {
  if (!fileChart) return

  const colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#6b7280', '#ec4899', '#14b8a6']
  const data = Object.entries(fileTypes.value).map(([name, value], index) => ({
    name: name.toUpperCase(),
    value,
    itemStyle: { color: colors[index % colors.length] }
  }))

  // 如果没有数据，显示默认空状态
  if (data.length === 0) {
    fileChart.setOption({
      title: {
        text: '暂无数据',
        left: 'center',
        top: 'center',
        textStyle: { color: '#999', fontSize: 14 }
      },
      series: []
    })
    return
  }

  fileChart.setOption({
    title: { show: false },
    tooltip: { trigger: 'item' },
    legend: { bottom: '5%', left: 'center' },
    series: [
      {
        name: '文件类型',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: { show: false, position: 'center' },
        emphasis: {
          label: {
            show: true,
            fontSize: 20,
            fontWeight: 'bold'
          }
        },
        labelLine: { show: false },
        data
      }
    ]
  })
}

// 初始化图表
const initCharts = () => {
  if (taskChartRef.value) {
    taskChart = echarts.init(taskChartRef.value)
  }

  if (fileChartRef.value) {
    fileChart = echarts.init(fileChartRef.value)
  }
}

// 监听时间范围变化
watch(timeRange, () => {
  fetchTaskTrends()
})

// 操作函数
const clearCache = () => {
  ElMessage.success('缓存已清空')
  cacheStats.value.size = 0
}

const syncFiles = () => {
  ElMessage.info('开始同步文件...')
}

const generateStrm = () => {
  router.push('/files')
}

const validateFiles = () => {
  ElMessage.info('开始验证文件...')
}

const openSettings = () => {
  router.push('/config')
}

onMounted(async () => {
  initCharts()

  // 加载仪表盘数据
  await fetchDashboardData()

  // 加载任务趋势
  await fetchTaskTrends()

  // 更新文件类型图表
  updateFileTypeChart()

  window.addEventListener('resize', () => {
    taskChart?.resize()
    fileChart?.resize()
  })
})

onUnmounted(() => {
  taskChart?.dispose()
  fileChart?.dispose()
})
</script>

<style scoped>
.dashboard {
  padding: 8px;
}

/* 统计卡片 */
.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}

.stat-icon {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-card.primary .stat-icon {
  background: linear-gradient(135deg, #3b82f6, #60a5fa);
}

.stat-card.success .stat-icon {
  background: linear-gradient(135deg, #10b981, #34d399);
}

.stat-card.warning .stat-icon {
  background: linear-gradient(135deg, #f59e0b, #fbbf24);
}

.stat-card.info .stat-icon {
  background: linear-gradient(135deg, #06b6d4, #22d3ee);
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.stat-title {
  font-size: 14px;
  color: var(--text-secondary);
}

/* 图表区域 */
.charts-row {
  margin-bottom: 20px;
}

.chart-card {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  margin-bottom: 20px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.chart-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.chart-container {
  height: 300px;
}

/* 任务表格 */
.tasks-row {
  margin-bottom: 20px;
}

.tasks-card {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.card-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.task-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 状态卡片 */
.status-row {
  margin-bottom: 20px;
}

.status-card {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  height: 100%;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.status-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.status-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--bg-primary);
  border-radius: var(--radius-md);
}

.status-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 缓存统计 */
.cache-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  text-align: center;
}

.cache-item {
  padding: 16px;
  background: var(--bg-primary);
  border-radius: var(--radius-md);
}

.cache-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--primary-color);
  margin-bottom: 4px;
}

.cache-label {
  font-size: 12px;
  color: var(--text-secondary);
}

/* 快捷操作 */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.action-btn {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

/* 响应式 */
@media (max-width: 768px) {
  .stat-card {
    margin-bottom: 16px;
  }

  .quick-actions {
    grid-template-columns: 1fr;
  }
}
</style>
