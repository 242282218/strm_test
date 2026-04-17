<template>
  <div class="tasks-page">
    <section class="tasks-hero page-surface">
      <div class="hero-main">
        <div class="hero-toolbar">
          <div class="hero-copy">
            <span class="hero-chip">Task Control</span>
            <h2 class="hero-title">任务编排、执行轨迹与异常恢复集中收口</h2>
            <p class="hero-description">
              保持 Dashboard 快捷入口、实时队列和异常回看在同一套壳层语言里，减少切页后的上下文断裂。
            </p>
          </div>

          <div class="hero-actions">
            <el-button type="primary" size="large" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon>
              新建任务
            </el-button>
            <el-button plain :icon="Refresh" @click="loadTasks">刷新队列</el-button>
          </div>
        </div>

        <div class="hero-metrics">
          <article
            v-for="metric in heroMetrics"
            :key="metric.label"
            class="metric-card"
            :class="metric.tone"
          >
            <div class="metric-head">
              <span class="metric-label">{{ metric.label }}</span>
              <div class="metric-icon">
                <el-icon size="18">
                  <component :is="metric.icon" />
                </el-icon>
              </div>
            </div>
            <strong class="metric-value">{{ metric.value }}</strong>
            <p class="metric-detail">{{ metric.detail }}</p>
          </article>
        </div>
      </div>

      <div class="hero-side">
        <article class="hero-side-card">
          <div class="hero-side-head">
            <div class="hero-side-heading">
              <span class="section-label">聚焦</span>
              <h3 class="hero-side-title">{{ spotlightTitle }}</h3>
            </div>
            <el-tag :type="socketTone" size="small">{{ socketLabel }}</el-tag>
          </div>

          <template v-if="spotlightTask">
            <p class="spotlight-name">{{ getTaskTypeLabel(spotlightTask.task_type) }}</p>
            <p class="spotlight-description">
              {{ getTaskStatusLabel(spotlightTask.status) }} · {{ formatTaskMoment(spotlightTask) }}
            </p>
            <el-progress
              :percentage="spotlightTask.progress"
              :status="getProgressStatus(spotlightTask.status)"
              :stroke-width="8"
            />
          </template>

          <p v-else class="spotlight-empty">
            任务创建后，这里会优先显示当前活跃链路或最近一次执行记录。
          </p>
        </article>

        <article class="hero-side-card launch-card" :class="{ 'is-prefilled': Boolean(requestedTaskTypeLabel) }">
          <div class="hero-side-head">
            <div class="hero-side-heading">
              <span class="section-label">入口</span>
              <h3 class="hero-side-title">
                {{ requestedTaskTypeLabel ? '快捷入口已预填' : '统一创建入口' }}
              </h3>
            </div>
            <el-tag :type="requestedTaskTypeLabel ? 'primary' : 'info'" size="small">
              {{ requestedTaskTypeLabel || '手动发起' }}
            </el-tag>
          </div>

          <p class="launch-copy">
            {{
              requestedTaskTypeLabel
                ? `来自概览页的快捷入口，已准备好 ${requestedTaskTypeLabel} 模板。`
                : '从这里发起新任务，统一进入规划、执行与审核链路。'
            }}
          </p>

          <div class="launch-actions">
            <el-button type="primary" @click="showCreateDialog = true">
              {{ requestedTaskTypeLabel ? '继续创建' : '新建任务' }}
              <el-icon class="el-icon--right"><ArrowRight /></el-icon>
            </el-button>
            <el-button v-if="requestedTaskTypeLabel" text @click="clearPrefill">清除预填</el-button>
          </div>
        </article>
      </div>
    </section>

    <section class="filter-panel page-surface">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">筛选</span>
          <h3 class="panel-title">任务视图收束</h3>
          <p class="panel-description">{{ filterSummary }}</p>
        </div>
        <el-button v-if="activeFilterCount > 0" text @click="resetFilter">重置筛选</el-button>
      </div>

      <el-form :inline="true" :model="filterForm" class="filter-form">
        <el-form-item label="状态">
          <el-select v-model="filterForm.status" placeholder="全部状态" clearable @change="loadTasks">
            <el-option label="待处理" value="pending" />
            <el-option label="规划中" value="planning" />
            <el-option label="运行中" value="running" />
            <el-option label="审核中" value="reviewing" />
            <el-option label="已完成" value="completed" />
            <el-option label="部分完成" value="partial_success" />
            <el-option label="失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filterForm.type" placeholder="全部类型" clearable @change="loadTasks">
            <el-option label="STRM生成" value="strm_generation" />
            <el-option label="文件同步" value="file_sync" />
            <el-option label="媒体刮削" value="scrape" />
            <el-option label="智能重命名" value="rename" />
          </el-select>
        </el-form-item>
      </el-form>
    </section>

    <section class="tasks-panel page-surface" v-loading="loading">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">队列</span>
          <h3 class="panel-title">任务执行队列</h3>
          <p class="panel-description">按类型、状态、阶段和追踪信息查看当前执行窗口。</p>
        </div>
        <div class="queue-summary">
          <strong class="queue-count">{{ filteredTaskCount }}</strong>
          <span class="queue-count-label">条当前结果</span>
        </div>
      </div>

      <template v-if="visibleTasks.length > 0">
        <div class="tasks-table-shell">
          <el-table :data="visibleTasks" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column label="类型" width="130">
              <template #default="{ row }">
                <el-tag :type="getTaskTypeTag(row.task_type)">{{ getTaskTypeLabel(row.task_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="getTaskStatusType(row.status)">{{ getTaskStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="流程" min-width="220">
              <template #default="{ row }">
                <el-steps :active="stageIndex(row.status)" align-center finish-status="success" simple>
                  <el-step title="规划" />
                  <el-step title="执行" />
                  <el-step title="审核" />
                </el-steps>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="220">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.progress"
                  :status="getProgressStatus(row.status)"
                  :stroke-width="9"
                />
              </template>
            </el-table-column>
            <el-table-column label="追踪" width="170">
              <template #default="{ row }">
                <span class="trace-id">{{ getTraceId(row) || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="180">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="210" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="viewTaskDetail(row)">详情</el-button>
                <el-button v-if="canCancel(row.status)" link type="warning" @click="handleCancel(row)">
                  取消
                </el-button>
                <el-button v-if="canDelete(row.status)" link type="danger" @click="handleDelete(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pagination">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="filteredTaskCount"
            v-model:current-page="page"
            v-model:page-size="pageSize"
          />
        </div>
      </template>

      <EmptyState
        v-else-if="!loading"
        :title="emptyStateTitle"
        :description="emptyStateDescription"
        action-text="新建任务"
        @action="showCreateDialog = true"
      />
    </section>

    <CreateTaskDialog
      v-model="showCreateDialog"
      :initial-task-type="requestedTaskType || undefined"
      @success="onTaskCreated"
    />

    <el-drawer v-model="detailDrawer.visible" title="任务详情" size="54%">
      <div v-if="detailDrawer.task" class="task-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务ID">{{ detailDrawer.task.id }}</el-descriptions-item>
          <el-descriptions-item label="任务类型">{{ getTaskTypeLabel(detailDrawer.task.task_type) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getTaskStatusType(detailDrawer.task.status)">{{ getTaskStatusLabel(detailDrawer.task.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">{{ detailDrawer.task.priority }}</el-descriptions-item>
          <el-descriptions-item label="进度">{{ detailDrawer.task.progress }}%</el-descriptions-item>
          <el-descriptions-item label="处理数量">{{ detailDrawer.task.processed_items }} / {{ detailDrawer.task.total_items }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detailDrawer.task.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ detailDrawer.task.started_at ? formatTime(detailDrawer.task.started_at) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ detailDrawer.task.completed_at ? formatTime(detailDrawer.task.completed_at) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="Trace ID">{{ getTraceId(detailDrawer.task) || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="detailDrawer.task.error_message" class="error-section">
          <el-divider />
          <el-alert type="error" :title="detailDrawer.task.error_message" :closable="false" />
        </div>

        <div class="logs-section">
          <el-divider />
          <h4>Agent 时间线</h4>
          <div class="logs-container">
            <div
              v-for="(log, index) in detailDrawer.task.logs"
              :key="index"
              class="log-item"
              :class="(log.level || '').toLowerCase()"
            >
              <span class="log-time">{{ formatLogTime(log.ts) }}</span>
              <span class="log-agent">{{ log.agent || 'system' }}</span>
              <span class="log-stage">{{ log.stage || '-' }}</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
            <el-empty v-if="!detailDrawer.task.logs?.length" description="暂无日志" :image-size="60" />
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Check, Clock, List, Plus, Refresh, Warning } from '@/components/icons'
import EmptyState from '@/components/EmptyState.vue'
import {
  cancelTask,
  deleteTask,
  getTask,
  getTaskStatusLabel,
  getTaskStatusType,
  getTaskTypeLabel,
  getTasks,
  type TaskResponse,
} from '@/features/tasks/api/tasks'
import { resolveTaskLaunchType, TASK_LAUNCH_QUERY_KEY } from '@/features/tasks/task-launcher'
import { buildTaskStats, buildTaskViewState, mergeTaskUpdate } from '@/features/tasks/task-performance'
import { useAsyncNotify, useLoading, useNotification } from '@/composables'
import CreateTaskDialog from '@/features/tasks/components/CreateTaskDialog.vue'

type SocketState = 'connecting' | 'connected' | 'retrying'
type MetricTone = 'primary' | 'success' | 'warning' | 'danger'

const route = useRoute()
const router = useRouter()
const { loading, withLoading } = useLoading()
const { error } = useNotification()
const { withConfirm } = useAsyncNotify()

const tasks = ref<TaskResponse[]>([])
const page = ref(1)
const pageSize = ref(20)
const showCreateDialog = ref(false)

const filterForm = reactive({ status: '', type: '' })

const detailDrawer = reactive({
  visible: false,
  task: null as TaskResponse | null,
})

const socketState = ref<SocketState>('connecting')

let ws: WebSocket | null = null
let isUnmounted = false
let reconnectTimer: number | null = null

const taskViewState = computed(() => buildTaskViewState(tasks.value, filterForm, page.value, pageSize.value))
const filteredTaskCount = computed(() => taskViewState.value.filteredCount)
const visibleTasks = computed(() => taskViewState.value.visibleTasks)

const stats = computed(() => buildTaskStats(tasks.value))
const requestedTaskType = computed(() => resolveTaskLaunchType(route.query))
const requestedTaskTypeLabel = computed(() => {
  return requestedTaskType.value ? getTaskTypeLabel(requestedTaskType.value) : ''
})
const activeFilterCount = computed(() => {
  return Number(Boolean(filterForm.status)) + Number(Boolean(filterForm.type))
})

const getTaskTimestamp = (task: TaskResponse) => {
  const timestamp = Date.parse(task.started_at || task.created_at)
  return Number.isNaN(timestamp) ? 0 : timestamp
}

const selectLatestTask = (items: TaskResponse[]): TaskResponse | null => {
  let selected: TaskResponse | null = null

  items.forEach((task) => {
    if (!selected || getTaskTimestamp(task) > getTaskTimestamp(selected)) {
      selected = task
    }
  })

  return selected
}

const spotlightTask = computed<TaskResponse | null>(() => {
  const activeTasks = tasks.value.filter(task => canCancel(task.status))
  return selectLatestTask(activeTasks) ?? selectLatestTask(tasks.value)
})

const spotlightTitle = computed(() => {
  const task = spotlightTask.value

  if (!task) {
    return '当前任务焦点'
  }

  return canCancel(task.status) ? '当前活跃任务' : '最新任务'
})

const socketLabel = computed(() => {
  if (socketState.value === 'connected') {
    return '实时监听已连接'
  }

  if (socketState.value === 'retrying') {
    return '实时监听重连中'
  }

  return '正在建立连接'
})

const socketTone = computed(() => {
  if (socketState.value === 'connected') {
    return 'success'
  }

  if (socketState.value === 'retrying') {
    return 'warning'
  }

  return 'info'
})

const heroMetrics = computed(() => {
  return [
    {
      label: '总任务',
      value: String(stats.value.total),
      detail: '当前执行窗口中的任务记录总量',
      icon: List,
      tone: 'primary' as MetricTone,
    },
    {
      label: '活跃流程',
      value: String(stats.value.running),
      detail: '规划、执行与审核中的实时链路',
      icon: Clock,
      tone: 'warning' as MetricTone,
    },
    {
      label: '已完成',
      value: String(stats.value.completed),
      detail: '成功结束并完成收口的任务',
      icon: Check,
      tone: 'success' as MetricTone,
    },
    {
      label: '异常/失败',
      value: String(stats.value.failed),
      detail: '失败或部分完成，值得优先回看',
      icon: Warning,
      tone: 'danger' as MetricTone,
    },
  ]
})

const filterSummary = computed(() => {
  const segments: string[] = []

  if (filterForm.status) {
    segments.push(`状态 ${getTaskStatusLabel(filterForm.status)}`)
  }

  if (filterForm.type) {
    segments.push(`类型 ${getTaskTypeLabel(filterForm.type)}`)
  }

  return segments.length > 0
    ? `当前已收束到 ${segments.join(' · ')}。`
    : '当前展示完整任务队列，可按状态或类型快速聚焦。'
})

const emptyStateTitle = computed(() => {
  return activeFilterCount.value > 0 ? '没有匹配的任务' : '任务队列暂时为空'
})

const emptyStateDescription = computed(() => {
  return activeFilterCount.value > 0
    ? '调整筛选条件或重置筛选，继续查看当前执行窗口。'
    : '从概览快捷入口或这里手动创建任务，新的规划/执行/审核链路会出现在这里。'
})

const clearTaskLaunchQuery = async () => {
  if (!(TASK_LAUNCH_QUERY_KEY in route.query)) return

  const nextQuery = { ...route.query }
  delete nextQuery[TASK_LAUNCH_QUERY_KEY]

  await router.replace({ query: nextQuery })
}

const clearPrefill = () => {
  void clearTaskLaunchQuery()
}

const getTaskTypeTag = (type: string): string => {
  const tags: Record<string, string> = {
    strm_generation: 'success',
    file_sync: 'primary',
    scrape: 'warning',
    rename: 'info',
  }
  return tags[type] || 'info'
}

const getProgressStatus = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  if (status === 'partial_success') return 'warning'
  return ''
}

const stageIndex = (status: string) => {
  if (status === 'pending') return 0
  if (status === 'planning') return 1
  if (status === 'running') return 2
  if (status === 'reviewing') return 3
  return 3
}

const canCancel = (status: string) => ['pending', 'planning', 'running', 'reviewing'].includes(status)
const canDelete = (status: string) => ['completed', 'partial_success', 'failed', 'cancelled'].includes(status)

const formatTime = (time: string): string => new Date(time).toLocaleString('zh-CN')
const formatTaskMoment = (task: TaskResponse): string => formatTime(task.started_at || task.created_at)
const formatLogTime = (ts: number): string => new Date(ts * 1000).toLocaleTimeString('zh-CN')

const getTraceId = (task: TaskResponse): string | undefined => {
  return task.params.orchestration?.trace_id
}

const loadTasks = async () => {
  await withLoading(async () => {
    const data = await getTasks({ status: filterForm.status || undefined, skip: 0, limit: 200 })
    tasks.value = data
  })
}

const resetFilter = () => {
  filterForm.status = ''
  filterForm.type = ''
  page.value = 1
  void loadTasks()
}

const viewTaskDetail = async (row: TaskResponse) => {
  try {
    const task = await getTask(row.id)
    detailDrawer.task = task
    detailDrawer.visible = true
  } catch {
    error('获取任务详情失败')
  }
}

const handleCancel = async (row: TaskResponse) => {
  await withConfirm(
    async () => {
      await cancelTask(row.id)
      await loadTasks()
    },
    {
      confirmMessage: '确定要取消该任务吗？',
      confirmTitle: '确认',
      success: '任务已取消',
    },
  )
}

const handleDelete = async (row: TaskResponse) => {
  await withConfirm(
    async () => {
      await deleteTask(row.id)
      await loadTasks()
    },
    {
      confirmMessage: '确定要删除该任务记录吗？',
      confirmTitle: '确认',
      success: '任务已删除',
    },
  )
}

const onTaskCreated = () => {
  showCreateDialog.value = false
  void loadTasks()
}

const scheduleReconnect = () => {
  if (reconnectTimer !== null) return

  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    connectWebSocket()
  }, 5000)
}

const connectWebSocket = () => {
  if (isUnmounted) return

  socketState.value = 'connecting'
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const wsUrl = `${protocol}//${host}/api/v1/tasks/ws`
  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    socketState.value = 'connected'
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type !== 'task_update') return

    const nextTasks = mergeTaskUpdate(tasks.value, data)
    if (nextTasks === tasks.value) return

    tasks.value = nextTasks

    if (detailDrawer.task && String(detailDrawer.task.id) === String(data.task_id)) {
      const nextDetailTask = nextTasks.find((task) => String(task.id) === String(data.task_id))
      if (nextDetailTask && nextDetailTask !== detailDrawer.task) {
        detailDrawer.task = nextDetailTask
      }
    }
  }

  ws.onclose = () => {
    if (isUnmounted) return
    socketState.value = 'retrying'
    scheduleReconnect()
  }
}

onMounted(() => {
  isUnmounted = false
  void loadTasks()
  connectWebSocket()
})

watch(requestedTaskType, (taskType) => {
  if (taskType) {
    showCreateDialog.value = true
  }
}, {
  immediate: true
})

watch(showCreateDialog, (visible, previousVisible) => {
  if (!visible && previousVisible && requestedTaskType.value) {
    void clearTaskLaunchQuery()
  }
})

onUnmounted(() => {
  isUnmounted = true
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  ws?.close()
})
</script>

<style scoped>
.tasks-page {
  display: flex;
  flex-direction: column;
  gap: var(--page-section-gap);
}

.tasks-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 420px);
  gap: var(--space-5);
  overflow: hidden;
  padding: 24px;
}

.tasks-hero::before,
.tasks-hero::after {
  content: '';
  position: absolute;
  pointer-events: none;
}

.tasks-hero::before {
  inset: -18% auto auto 58%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79, 141, 246, 0.18), transparent 72%);
}

.tasks-hero::after {
  inset: auto auto -24% -6%;
  width: 190px;
  height: 190px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(231, 168, 61, 0.14), transparent 70%);
}

.hero-main,
.hero-side {
  position: relative;
  z-index: 1;
}

.hero-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 18px;
}

.hero-toolbar,
.panel-head,
.hero-side-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.hero-copy,
.panel-heading,
.hero-side-heading {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 10px;
}

.hero-actions {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.hero-chip {
  display: inline-flex;
  align-self: flex-start;
  padding: 7px 12px;
  border-radius: var(--radius-full);
  background: rgba(79, 141, 246, 0.14);
  color: var(--primary-700);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.hero-title {
  margin: 0;
  max-width: 15ch;
  font-size: clamp(1.7rem, 1.32rem + 0.9vw, 2.35rem);
  line-height: 1.06;
  font-weight: var(--font-bold);
  letter-spacing: var(--letter-spacing-tight);
  color: var(--text-primary);
}

.hero-description,
.panel-description,
.spotlight-description,
.spotlight-empty,
.launch-copy {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.65;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card,
.hero-side-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  background: rgba(255, 255, 255, 0.36);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.metric-card {
  display: flex;
  min-height: 150px;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
  padding: 16px;
}

.metric-card.primary {
  --metric-bg: rgba(79, 141, 246, 0.14);
  --metric-color: var(--primary-700);
}

.metric-card.success {
  --metric-bg: rgba(51, 176, 122, 0.14);
  --metric-color: var(--success-700);
}

.metric-card.warning {
  --metric-bg: rgba(231, 168, 61, 0.16);
  --metric-color: var(--warning-700);
}

.metric-card.danger {
  --metric-bg: rgba(228, 100, 108, 0.14);
  --metric-color: var(--danger-700);
}

.metric-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.metric-label {
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.04em;
}

.metric-icon {
  display: flex;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: var(--metric-bg);
  color: var(--metric-color);
}

.metric-value {
  color: var(--text-primary);
  font-size: clamp(1.5rem, 1.15rem + 0.7vw, 2rem);
  line-height: 1;
}

.metric-detail {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.55;
}

.hero-side {
  display: grid;
  gap: 12px;
}

.hero-side-card,
.filter-panel,
.tasks-panel {
  padding: 22px;
}

.hero-side-title,
.panel-title {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.02rem;
  line-height: 1.4;
  font-weight: var(--font-semibold);
}

.spotlight-name {
  margin: 0;
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: var(--font-semibold);
  line-height: 1.45;
}

.launch-card.is-prefilled {
  border-color: rgba(79, 141, 246, 0.2);
  box-shadow: inset 0 0 0 1px rgba(79, 141, 246, 0.08);
}

.launch-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.queue-summary {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  color: var(--text-secondary);
}

.queue-count {
  color: var(--text-primary);
  font-size: 1.6rem;
  line-height: 1;
  font-weight: var(--font-bold);
}

.queue-count-label {
  font-size: 0.8rem;
}

.trace-id {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.filter-form :deep(.el-form-item) {
  margin-right: 14px;
  margin-bottom: 0;
}

.tasks-table-shell {
  overflow-x: auto;
}

.pagination {
  margin-top: var(--space-5);
  display: flex;
  justify-content: flex-end;
}

.task-detail {
  padding: var(--space-3);
}

.logs-container {
  max-height: 420px;
  overflow-y: auto;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  border: 1px solid var(--border-light);
}

.log-item {
  display: grid;
  grid-template-columns: 90px 90px 90px 1fr;
  gap: var(--space-2);
  padding: 6px 0;
  border-bottom: 1px dashed var(--border-light);
  font-size: 13px;
}

.log-item:last-child { border-bottom: none; }
.log-time { color: var(--text-secondary); }
.log-agent { color: #2563eb; font-weight: 600; }
.log-stage { color: #7c3aed; }
.log-item.error .log-message { color: #dc2626; }
.log-item.warning .log-message { color: #d97706; }

@media (max-width: 1200px) {
  .tasks-hero {
    grid-template-columns: 1fr;
  }

  .hero-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 992px) {
  .hero-toolbar,
  .panel-head,
  .hero-side-head {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .tasks-hero,
  .filter-panel,
  .tasks-panel,
  .hero-side-card {
    padding: 18px;
  }

  .hero-title {
    max-width: none;
    font-size: 1.48rem;
  }

  .hero-metrics {
    grid-template-columns: 1fr;
  }

  .queue-summary {
    align-items: flex-start;
  }

  .pagination {
    justify-content: flex-start;
  }

  .log-item {
    grid-template-columns: 1fr;
  }
}
</style>
