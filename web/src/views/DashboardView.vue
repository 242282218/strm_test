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
              <div class="cache-value">{{ cacheStats.hitRate }}%</div>
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
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  Document,
  Refresh,
  DocumentAdd,
  Check,
  Setting,
  ArrowRight
} from '@element-plus/icons-vue'

const router = useRouter()
const taskChartRef = ref<HTMLElement>()
const fileChartRef = ref<HTMLElement>()
let taskChart: echarts.ECharts | null = null
let fileChart: echarts.ECharts | null = null

const timeRange = ref('week')

// 统计数据
const stats = ref([
  { title: 'STRM文件', value: '1,234', icon: 'Document', type: 'primary', trend: 12 },
  { title: '网盘文件', value: '5,678', icon: 'Folder', type: 'success', trend: 8 },
  { title: '任务数量', value: '42', icon: 'List', type: 'warning', trend: -3 },
  { title: '缓存命中', value: '98.5%', icon: 'Refresh', type: 'info', trend: 5 }
])

// 最近任务
const recentTasks = ref([
  { name: '同步电影目录', type: 'sync', status: 'running', progress: 65, time: '2024-01-31 14:30' },
  { name: '生成STRM文件', type: 'generate', status: 'success', progress: 100, time: '2024-01-31 13:15' },
  { name: '验证文件有效性', type: 'validate', status: 'success', progress: 100, time: '2024-01-31 12:00' },
  { name: '清理过期缓存', type: 'cleanup', status: 'pending', progress: 0, time: '2024-01-31 11:30' }
])

// 服务状态
const services = ref([
  { name: 'API服务', status: 'running' },
  { name: '任务调度器', status: 'running' },
  { name: '缓存服务', status: 'running' },
  { name: 'Emby代理', status: 'running' }
])

// 缓存统计
const cacheStats = ref({
  size: 156,
  hitRate: 94.2,
  ttl: 600
})

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

// 初始化图表
const initCharts = () => {
  if (taskChartRef.value) {
    taskChart = echarts.init(taskChartRef.value)
    taskChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
      },
      yAxis: { type: 'value' },
      series: [
        {
          name: '成功',
          type: 'line',
          smooth: true,
          data: [12, 15, 8, 20, 18, 25, 22],
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
          data: [2, 1, 3, 1, 2, 1, 0],
          itemStyle: { color: '#ef4444' }
        }
      ]
    })
  }

  if (fileChartRef.value) {
    fileChart = echarts.init(fileChartRef.value)
    fileChart.setOption({
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
          data: [
            { value: 1048, name: '电影', itemStyle: { color: '#3b82f6' } },
            { value: 735, name: '电视剧', itemStyle: { color: '#8b5cf6' } },
            { value: 580, name: '动漫', itemStyle: { color: '#10b981' } },
            { value: 484, name: '纪录片', itemStyle: { color: '#f59e0b' } },
            { value: 300, name: '其他', itemStyle: { color: '#6b7280' } }
          ]
        }
      ]
    })
  }
}

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

onMounted(() => {
  initCharts()
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
