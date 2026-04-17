<template>
  <div class="tasks-page">
    <section class="hero-panel">
      <div>
        <h2>任务编排中心</h2>
        <p>面向 NAS + Emby 的多 Agent 任务流，支持规划、执行、审核与异常恢复。</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" size="large" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新建任务
        </el-button>
        <el-button @click="loadTasks">刷新</el-button>
      </div>
    </section>

    <section class="stats-grid">
      <article class="stat-card">
        <span>总任务</span>
        <strong>{{ stats.total }}</strong>
      </article>
      <article class="stat-card running">
        <span>进行中</span>
        <strong>{{ stats.running }}</strong>
      </article>
      <article class="stat-card success">
        <span>已完成</span>
        <strong>{{ stats.completed }}</strong>
      </article>
      <article class="stat-card danger">
        <span>异常/失败</span>
        <strong>{{ stats.failed }}</strong>
      </article>
    </section>

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filterForm">
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
        <el-form-item>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="tasks-card">
      <el-table :data="visibleTasks" v-loading="loading" stripe>
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
            <el-progress :percentage="row.progress" :status="getProgressStatus(row.status)" :stroke-width="9" />
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
            <el-button v-if="canCancel(row.status)" link type="warning" @click="handleCancel(row)">取消</el-button>
            <el-button v-if="canDelete(row.status)" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="filteredTaskCount"
          v-model:current-page="page"
          v-model:page-size="pageSize"
        />
      </div>
    </el-card>

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
import { Plus } from '@/components/icons'
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

const route = useRoute()
const router = useRouter()
const { loading, withLoading } = useLoading()
const { success, error } = useNotification()
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

let ws: WebSocket | null = null
let isUnmounted = false

const taskViewState = computed(() => buildTaskViewState(tasks.value, filterForm, page.value, pageSize.value))
const filteredTaskCount = computed(() => taskViewState.value.filteredCount)
const visibleTasks = computed(() => taskViewState.value.visibleTasks)

const stats = computed(() => buildTaskStats(tasks.value))
const requestedTaskType = computed(() => resolveTaskLaunchType(route.query))

const clearTaskLaunchQuery = async () => {
  if (!(TASK_LAUNCH_QUERY_KEY in route.query)) return

  const nextQuery = { ...route.query }
  delete nextQuery[TASK_LAUNCH_QUERY_KEY]

  await router.replace({ query: nextQuery })
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
  loadTasks()
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
      loadTasks()
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
      loadTasks()
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
  success('任务创建成功')
  loadTasks()
}

const connectWebSocket = () => {
  if (isUnmounted) return

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const wsUrl = `${protocol}//${host}/api/tasks/ws`
  ws = new WebSocket(wsUrl)

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
    setTimeout(connectWebSocket, 5000)
  }
}

onMounted(() => {
  isUnmounted = false
  loadTasks()
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
  ws?.close()
})
</script>

<style scoped>
.tasks-page {
  padding: var(--space-2);
  display: grid;
  gap: var(--space-4);
}

.hero-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-5);
  border-radius: var(--radius-xl);
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #0ea5e9 100%);
  color: #fff;
  box-shadow: var(--shadow-lg);
}

.hero-panel h2 {
  margin: 0;
  font-size: 24px;
}

.hero-panel p {
  margin-top: var(--space-2);
  opacity: 0.9;
}

.hero-actions {
  display: flex;
  gap: var(--space-2);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.stat-card {
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-sm);
}

.stat-card span {
  color: var(--text-secondary);
}

.stat-card strong {
  display: block;
  margin-top: var(--space-1);
  font-size: 24px;
}

.stat-card.running strong { color: #2563eb; }
.stat-card.success strong { color: #059669; }
.stat-card.danger strong { color: #dc2626; }

.trace-id {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
}

.pagination {
  margin-top: var(--space-4);
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
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
