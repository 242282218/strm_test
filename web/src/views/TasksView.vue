<template>
  <div class="tasks-page">
    <div class="page-header">
      <h2>任务管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        新建任务
      </el-button>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="状态">
          <el-select v-model="filterForm.status" placeholder="全部状态" clearable @change="loadTasks">
            <el-option label="待处理" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="已完成" value="completed" />
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
          <el-button type="primary" @click="loadTasks">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务列表 -->
    <el-card shadow="never" class="tasks-card">
      <el-table :data="tasks" v-loading="loading" stripe border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getTaskTypeTag(row.task_type)">
              {{ getTaskTypeLabel(row.task_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getTaskStatusType(row.status)">
              {{ getTaskStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="200">
          <template #default="{ row }">
            <el-progress 
              :percentage="row.progress" 
              :status="getProgressStatus(row.status)"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column label="处理进度" width="150">
          <template #default="{ row }">
            {{ row.processed_items }} / {{ row.total_items }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewTaskDetail(row)">详情</el-button>
            <el-button 
              v-if="canCancel(row.status)" 
              link 
              type="warning" 
              @click="handleCancel(row)"
            >
              取消
            </el-button>
            <el-button 
              v-if="canDelete(row.status)" 
              link 
              type="danger" 
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          v-model:current-page="page"
          v-model:page-size="pageSize"
          @current-change="loadTasks"
        />
      </div>
    </el-card>

    <!-- 创建任务弹窗 -->
    <CreateTaskDialog v-model="showCreateDialog" @success="onTaskCreated" />

    <!-- 任务详情抽屉 -->
    <el-drawer v-model="detailDrawer.visible" title="任务详情" size="50%">
      <div v-if="detailDrawer.task" class="task-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务ID">{{ detailDrawer.task.id }}</el-descriptions-item>
          <el-descriptions-item label="任务类型">
            {{ getTaskTypeLabel(detailDrawer.task.task_type) }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getTaskStatusType(detailDrawer.task.status)">
              {{ getTaskStatusLabel(detailDrawer.task.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">{{ detailDrawer.task.priority }}</el-descriptions-item>
          <el-descriptions-item label="进度">{{ detailDrawer.task.progress }}%</el-descriptions-item>
          <el-descriptions-item label="处理数量">
            {{ detailDrawer.task.processed_items }} / {{ detailDrawer.task.total_items }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detailDrawer.task.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">
            {{ detailDrawer.task.started_at ? formatTime(detailDrawer.task.started_at) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="完成时间">
            {{ detailDrawer.task.completed_at ? formatTime(detailDrawer.task.completed_at) : '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="detailDrawer.task.error_message" class="error-section">
          <el-divider />
          <h4>错误信息</h4>
          <el-alert type="error" :title="detailDrawer.task.error_message" :closable="false" />
        </div>

        <div class="logs-section">
          <el-divider />
          <h4>任务日志</h4>
          <div class="logs-container">
            <div 
              v-for="(log, index) in detailDrawer.task.logs" 
              :key="index" 
              class="log-item"
              :class="log.level.toLowerCase()"
            >
              <span class="log-time">{{ formatLogTime(log.ts) }}</span>
              <span class="log-level">[{{ log.level }}]</span>
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
import { reactive, ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '@/api'
import { 
  getTasks, 
  cancelTask, 
  deleteTask, 
  getTask,
  getTaskTypeLabel,
  getTaskStatusLabel,
  getTaskStatusType,
  type TaskResponse 
} from '@/api/tasks'
import CreateTaskDialog from '@/components/CreateTaskDialog.vue'

const loading = ref(false)
const tasks = ref<TaskResponse[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const showCreateDialog = ref(false)

const filterForm = reactive({
  status: '',
  type: ''
})

const detailDrawer = reactive({
  visible: false,
  task: null as TaskResponse | null
})

let ws: WebSocket | null = null

const getTaskTypeTag = (type: string): string => {
  const tags: Record<string, string> = {
    strm_generation: 'success',
    file_sync: 'primary',
    scrape: 'warning',
    rename: 'info'
  }
  return tags[type] || 'info'
}

const getProgressStatus = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return ''
}

const canCancel = (status: string) => {
  return status === 'pending' || status === 'running'
}

const canDelete = (status: string) => {
  return ['completed', 'failed', 'cancelled'].includes(status)
}

const formatTime = (time: string): string => {
  const date = new Date(time)
  return date.toLocaleString('zh-CN')
}

const formatLogTime = (ts: number): string => {
  const date = new Date(ts * 1000)
  return date.toLocaleTimeString('zh-CN')
}

const loadTasks = async () => {
  loading.value = true
  try {
    const data = await getTasks({
      status: filterForm.status || undefined,
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value
    })
    tasks.value = data
    total.value = data.length
  } catch (error: unknown) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
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
  } catch (error: unknown) {
    ElMessage.error('获取任务详情失败')
  }
}

const handleCancel = async (row: TaskResponse) => {
  try {
    await ElMessageBox.confirm('确定要取消该任务吗？', '确认', { type: 'warning' })
    await cancelTask(row.id)
    ElMessage.success('任务已取消')
    loadTasks()
  } catch {
    // 用户取消
  }
}

const handleDelete = async (row: TaskResponse) => {
  try {
    await ElMessageBox.confirm('确定要删除该任务记录吗？', '确认', { type: 'warning' })
    await deleteTask(row.id)
    ElMessage.success('任务已删除')
    loadTasks()
  } catch {
    // 用户取消
  }
}

const onTaskCreated = () => {
  showCreateDialog.value = false
  ElMessage.success('任务创建成功')
  loadTasks()
}

// WebSocket 连接
const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const wsUrl = `${protocol}//${host}/api/tasks/ws`
  ws = new WebSocket(wsUrl)
  
  ws.onopen = () => {
    console.log('WebSocket connected')
  }
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type === 'task_update') {
      // 更新任务列表中的任务状态
      const task = tasks.value.find(t => t.id === data.task_id)
      if (task) {
        task.status = data.status
        task.progress = data.progress
        if (data.logs) {
          task.logs = [...(task.logs || []), ...data.logs]
        }
      }
    }
  }
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
  }
  
  ws.onclose = () => {
    console.log('WebSocket disconnected')
    // 尝试重连
    setTimeout(connectWebSocket, 5000)
  }
}

onMounted(() => {
  loadTasks()
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
})
</script>

<style scoped>
.tasks-page {
  padding: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.filter-card {
  margin-bottom: 16px;
}

.tasks-card {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.task-detail {
  padding: 16px;
}

.error-section {
  margin-top: 16px;
}

.logs-section {
  margin-top: 16px;
}

.logs-container {
  max-height: 400px;
  overflow-y: auto;
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 12px;
  font-family: monospace;
  font-size: 13px;
}

.log-item {
  padding: 4px 0;
  border-bottom: 1px solid var(--border-color);
}

.log-item:last-child {
  border-bottom: none;
}

.log-time {
  color: var(--text-secondary);
  margin-right: 8px;
}

.log-level {
  font-weight: bold;
  margin-right: 8px;
}

.log-item.info .log-level {
  color: var(--primary-color);
}

.log-item.error .log-level {
  color: var(--danger-color);
}

.log-item.warning .log-level {
  color: var(--warning-color);
}

.log-message {
  color: var(--text-primary);
}
</style>
