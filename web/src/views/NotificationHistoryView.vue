<template>
  <div class="notification-history-page">
    <div class="page-header">
      <h2>通知历史</h2>
      <el-button type="danger" @click="clearHistory">
        <el-icon><Delete /></el-icon>
        清空历史
      </el-button>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="状态">
          <el-select v-model="filterForm.status" placeholder="全部状态" clearable>
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filterForm.type" placeholder="全部类型" clearable>
            <el-option label="任务完成" value="task_completed" />
            <el-option label="任务失败" value="task_failed" />
            <el-option label="文件同步" value="file_synced" />
            <el-option label="刮削完成" value="scrape_completed" />
            <el-option label="系统警告" value="system_warning" />
            <el-option label="系统通知" value="system_notice" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
          />
        </el-form-item>
        <el-form-item>
          <el-button @click="resetFilter">重置</el-button>
          <el-button type="primary" @click="loadHistory">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 历史列表 -->
    <el-card shadow="never" class="history-card">
      <el-timeline>
        <el-timeline-item
          v-for="item in historyList"
          :key="item.id"
          :type="item.status === 'success' ? 'success' : 'danger'"
          :timestamp="formatTime(item.created_at)"
        >
          <div class="timeline-content">
            <div class="timeline-header">
              <el-tag :type="getTypeTag(item.type)">{{ getTypeLabel(item.type) }}</el-tag>
              <el-tag :type="item.status === 'success' ? 'success' : 'danger'" size="small">
                {{ item.status === 'success' ? '成功' : '失败' }}
              </el-tag>
            </div>
            <div class="timeline-body">
              <p class="message">{{ item.message }}</p>
              <p v-if="item.error" class="error">{{ item.error }}</p>
            </div>
            <div class="timeline-footer">
              <span class="channel">{{ getChannelLabel(item.channel) }}</span>
              <el-button link type="primary" size="small" @click="viewDetail(item)">
                查看详情
              </el-button>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>

      <el-empty v-if="!historyList.length" description="暂无通知记录" :image-size="100" />

      <!-- 分页 -->
      <div class="pagination" v-if="total > 0">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          v-model:current-page="page"
          v-model:page-size="pageSize"
          @current-change="loadHistory"
        />
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailDialog.visible" title="通知详情" width="600px">
      <el-descriptions :column="1" border v-if="detailDialog.item">
        <el-descriptions-item label="通知ID">{{ detailDialog.item.id }}</el-descriptions-item>
        <el-descriptions-item label="通知类型">
          <el-tag :type="getTypeTag(detailDialog.item.type)">
            {{ getTypeLabel(detailDialog.item.type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="发送状态">
          <el-tag :type="detailDialog.item.status === 'success' ? 'success' : 'danger'">
            {{ detailDialog.item.status === 'success' ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="通知渠道">
          {{ getChannelLabel(detailDialog.item.channel) }}
        </el-descriptions-item>
        <el-descriptions-item label="发送时间">
          {{ formatTime(detailDialog.item.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="消息内容">
          <pre class="message-content">{{ detailDialog.item.message }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="错误信息" v-if="detailDialog.item.error">
          <pre class="error-content">{{ detailDialog.item.error }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'

interface NotificationItem {
  id: number
  type: string
  status: 'success' | 'failed'
  channel: string
  message: string
  error?: string
  created_at: string
}

const loading = ref(false)
const historyList = ref<NotificationItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filterForm = reactive({
  status: '',
  type: '',
  dateRange: [] as Date[]
})

const detailDialog = reactive({
  visible: false,
  item: null as NotificationItem | null
})

const getTypeLabel = (type: string): string => {
  const labels: Record<string, string> = {
    task_completed: '任务完成',
    task_failed: '任务失败',
    file_synced: '文件同步',
    scrape_completed: '刮削完成',
    system_warning: '系统警告',
    system_notice: '系统通知'
  }
  return labels[type] || type
}

const getTypeTag = (type: string): string => {
  const tags: Record<string, string> = {
    task_completed: 'success',
    task_failed: 'danger',
    file_synced: 'primary',
    scrape_completed: 'warning',
    system_warning: 'danger',
    system_notice: 'info'
  }
  return tags[type] || 'info'
}

const getChannelLabel = (channel: string): string => {
  const labels: Record<string, string> = {
    wecom: '企业微信',
    dingtalk: '钉钉',
    feishu: '飞书',
    telegram: 'Telegram',
    email: '邮件',
    webhook: 'Webhook'
  }
  return labels[channel] || channel
}

const formatTime = (time: string): string => {
  const date = new Date(time)
  return date.toLocaleString('zh-CN')
}

const loadHistory = async () => {
  loading.value = true
  try {
    // TODO: 调用API获取历史记录
    // 模拟数据
    historyList.value = [
      {
        id: 1,
        type: 'task_completed',
        status: 'success',
        channel: 'wecom',
        message: 'STRM生成任务已完成\n生成数量: 150\n耗时: 2分30秒',
        created_at: new Date().toISOString()
      },
      {
        id: 2,
        type: 'task_failed',
        status: 'failed',
        channel: 'wecom',
        message: '文件同步任务失败',
        error: '网络连接超时',
        created_at: new Date(Date.now() - 3600000).toISOString()
      },
      {
        id: 3,
        type: 'scrape_completed',
        status: 'success',
        channel: 'dingtalk',
        message: '媒体刮削完成\n刮削数量: 50\n成功: 48\n失败: 2',
        created_at: new Date(Date.now() - 7200000).toISOString()
      }
    ]
    total.value = 3
  } catch {
    ElMessage.error('加载历史记录失败')
  } finally {
    loading.value = false
  }
}

const resetFilter = () => {
  filterForm.status = ''
  filterForm.type = ''
  filterForm.dateRange = []
  page.value = 1
  loadHistory()
}

const viewDetail = (item: NotificationItem) => {
  detailDialog.item = item
  detailDialog.visible = true
}

const clearHistory = async () => {
  try {
    await ElMessageBox.confirm('确定要清空所有通知历史吗？此操作不可恢复。', '确认', {
      type: 'warning'
    })
    // TODO: 调用API清空历史
    historyList.value = []
    total.value = 0
    ElMessage.success('历史记录已清空')
  } catch {
    // 用户取消
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.notification-history-page {
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

.history-card {
  margin-bottom: 16px;
}

.timeline-content {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 16px;
}

.timeline-header {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.timeline-body {
  margin-bottom: 12px;
}

.message {
  margin: 0;
  color: var(--text-primary);
  white-space: pre-line;
}

.error {
  margin: 8px 0 0;
  color: var(--danger-color);
  font-size: 13px;
}

.timeline-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--text-secondary);
}

.channel {
  background: var(--bg-primary);
  padding: 2px 8px;
  border-radius: 4px;
}

.pagination {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
}

.message-content,
.error-content {
  margin: 0;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 14px;
}

.error-content {
  color: var(--danger-color);
}
</style>
