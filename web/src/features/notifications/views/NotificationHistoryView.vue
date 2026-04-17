<template>
  <div class="notification-history-page">
    <section class="history-hero page-surface">
      <div class="hero-main">
        <div class="hero-toolbar">
          <div class="hero-copy">
            <span class="hero-chip">Delivery Log</span>
            <h2 class="hero-title">通知结果、失败线索与时间范围统一回看</h2>
            <p class="hero-description">
              直接读取通知日志接口，按状态、事件类型和时间范围回看投递结果，不再保留本地伪造数据和虚假的清空操作。
            </p>
          </div>

          <div class="hero-actions">
            <el-button :icon="Refresh" :loading="loading" data-testid="notification-history-refresh" @click="loadHistory">
              刷新日志
            </el-button>
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
              <h3 class="hero-side-title">{{ latestEntryTitle }}</h3>
            </div>
            <el-tag :type="latestEntryStatusType" size="small">{{ latestEntryStatusLabel }}</el-tag>
          </div>

          <template v-if="latestEntry">
            <p class="spotlight-main">{{ latestEntry.message }}</p>
            <p class="spotlight-description">
              {{ latestEntry.channel }} · {{ formatTime(latestEntry.created_at) }}
            </p>
          </template>

          <p v-else class="spotlight-description">
            日志接口返回后，这里会优先显示最近一条通知结果或失败记录。
          </p>
        </article>

        <article class="hero-side-card">
          <div class="hero-side-head">
            <div class="hero-side-heading">
              <span class="section-label">筛选</span>
              <h3 class="hero-side-title">当前视图范围</h3>
            </div>
            <el-tag :type="activeFilterCount > 0 ? 'primary' : 'info'" size="small">
              {{ activeFilterCount > 0 ? `${activeFilterCount} 条条件` : '全量日志' }}
            </el-tag>
          </div>

          <p class="spotlight-description">{{ filterSummary }}</p>

          <div v-if="activeFilterSegments.length > 0" class="filter-pill-list">
            <span v-for="segment in activeFilterSegments" :key="segment" class="filter-pill">
              {{ segment }}
            </span>
          </div>

          <div class="filter-actions">
            <el-button v-if="activeFilterCount > 0" text @click="resetFilter">重置筛选</el-button>
            <el-button plain @click="loadHistory">刷新结果</el-button>
          </div>
        </article>
      </div>
    </section>

    <section class="filter-panel page-surface">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">检索</span>
          <h3 class="panel-title">日志筛选</h3>
          <p class="panel-description">按状态、事件类型和时间范围收束通知日志，查询时自动回到第一页。</p>
        </div>
      </div>

      <el-form :inline="true" :model="filterForm" class="filter-form">
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
          <el-button type="primary" @click="applyFilters">查询</el-button>
        </el-form-item>
      </el-form>
    </section>

    <section class="history-panel page-surface" v-loading="loading">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">时间线</span>
          <h3 class="panel-title">日志时间线</h3>
          <p class="panel-description">按时间序回看各类通知事件、渠道和失败详情。</p>
        </div>

        <div class="queue-summary">
          <strong class="queue-count">{{ total }}</strong>
          <span class="queue-count-label">条匹配日志</span>
        </div>
      </div>

      <template v-if="visibleHistoryList.length > 0">
        <el-timeline class="history-timeline">
          <el-timeline-item
            v-for="item in visibleHistoryList"
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
                <span class="channel">{{ item.channel }}</span>
                <el-button link type="primary" size="small" @click="viewDetail(item)">
                  查看详情
                </el-button>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>

        <div class="pagination" v-if="total > pageSize">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="total"
            v-model:current-page="page"
            v-model:page-size="pageSize"
          />
        </div>
      </template>

      <EmptyState
        v-else-if="!loading"
        title="暂无通知记录"
        description="当前筛选范围内没有匹配日志，可以放宽条件或刷新日志后重试。"
        action-text="刷新日志"
        @action="loadHistory"
      />
    </section>

    <el-dialog v-model="detailDialog.visible" title="通知详情" width="600px">
      <el-descriptions v-if="detailDialog.item" :column="1" border>
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
          {{ detailDialog.item.channel }}
        </el-descriptions-item>
        <el-descriptions-item label="发送时间">
          {{ formatTime(detailDialog.item.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="消息内容">
          <pre class="message-content">{{ detailDialog.item.message }}</pre>
        </el-descriptions-item>
        <el-descriptions-item v-if="detailDialog.item.error" label="错误信息">
          <pre class="error-content">{{ detailDialog.item.error }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Bell, CircleCheck, CircleClose, Filter, Refresh } from '@/components/icons'
import EmptyState from '@/components/EmptyState.vue'
import { getLogs, type Log } from '@/features/notifications/api/notification'

type NotificationStatus = 'success' | 'failed'
type MetricTone = 'primary' | 'success' | 'warning' | 'info'

interface NotificationItem {
  id: number
  type: string
  status: NotificationStatus
  channel: string
  message: string
  error?: string
  created_at: string
}

interface HeroMetric {
  label: string
  value: string
  detail: string
  icon: Component
  tone: MetricTone
}

const loading = ref(false)
const rawHistoryList = ref<NotificationItem[]>([])
const page = ref(1)
const pageSize = ref(20)

const filterForm = reactive({
  status: '',
  type: '',
  dateRange: [] as [] | [Date, Date]
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

const formatTime = (time: string): string => {
  const date = new Date(time)
  return date.toLocaleString('zh-CN')
}

const activeFilterSegments = computed(() => {
  const segments: string[] = []

  if (filterForm.status) {
    segments.push(`状态 ${filterForm.status === 'success' ? '成功' : '失败'}`)
  }

  if (filterForm.type) {
    segments.push(`类型 ${getTypeLabel(filterForm.type)}`)
  }

  if (filterForm.dateRange.length === 2) {
    segments.push(`时间 ${formatTime(filterForm.dateRange[0].toISOString())} - ${formatTime(filterForm.dateRange[1].toISOString())}`)
  }

  return segments
})

const activeFilterCount = computed(() => activeFilterSegments.value.length)

const filterSummary = computed(() => {
  if (activeFilterSegments.value.length === 0) {
    return '当前展示完整通知日志，可按状态、事件类型和时间范围快速聚焦。'
  }

  return `当前已收束到 ${activeFilterSegments.value.join(' · ')}。`
})

const filteredHistoryList = computed(() => {
  return rawHistoryList.value.filter(item => {
    if (filterForm.status && item.status !== filterForm.status) {
      return false
    }

    if (filterForm.type && item.type !== filterForm.type) {
      return false
    }

    if (filterForm.dateRange.length === 2) {
      const [start, end] = filterForm.dateRange
      const timestamp = new Date(item.created_at).getTime()
      const startTime = new Date(start).setHours(0, 0, 0, 0)
      const endTime = new Date(end).setHours(23, 59, 59, 999)
      if (timestamp < startTime || timestamp > endTime) {
        return false
      }
    }

    return true
  })
})

const total = computed(() => filteredHistoryList.value.length)

const visibleHistoryList = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredHistoryList.value.slice(start, start + pageSize.value)
})

const latestEntry = computed(() => filteredHistoryList.value[0] ?? null)
const latestEntryTitle = computed(() => latestEntry.value ? getTypeLabel(latestEntry.value.type) : '最近一条日志')
const latestEntryStatusLabel = computed(() => latestEntry.value ? (latestEntry.value.status === 'success' ? '成功' : '失败') : '暂无数据')
const latestEntryStatusType = computed(() => latestEntry.value ? (latestEntry.value.status === 'success' ? 'success' : 'danger') : 'info')

const successCount = computed(() => rawHistoryList.value.filter(item => item.status === 'success').length)
const failedCount = computed(() => rawHistoryList.value.filter(item => item.status === 'failed').length)

const heroMetrics = computed<HeroMetric[]>(() => {
  return [
    {
      label: '日志总量',
      value: `${rawHistoryList.value.length}`,
      detail: '当前从通知日志接口拉取到的总记录数。',
      icon: Bell,
      tone: 'primary'
    },
    {
      label: '成功投递',
      value: `${successCount.value}`,
      detail: '已成功发送的通知数量。',
      icon: CircleCheck,
      tone: successCount.value > 0 ? 'success' : 'info'
    },
    {
      label: '失败记录',
      value: `${failedCount.value}`,
      detail: '需要优先回看的失败通知数量。',
      icon: CircleClose,
      tone: failedCount.value > 0 ? 'warning' : 'success'
    },
    {
      label: '筛选条件',
      value: `${activeFilterCount.value}`,
      detail: '当前激活的筛选条件数量。',
      icon: Filter,
      tone: activeFilterCount.value > 0 ? 'primary' : 'info'
    }
  ]
})

const normalizeStatus = (status: string): NotificationStatus => {
  return status === 'success' ? 'success' : 'failed'
}

const mapLogToNotificationItem = (log: Log): NotificationItem => {
  return {
    id: log.id,
    type: log.event_type,
    status: normalizeStatus(log.status),
    channel: log.channel_name || '系统',
    message: log.title || getTypeLabel(log.event_type),
    error: log.error_message || '',
    created_at: log.created_at
  }
}

const loadHistory = async () => {
  loading.value = true
  try {
    const logs = await getLogs(200)
    rawHistoryList.value = [...logs]
      .map(mapLogToNotificationItem)
      .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))
  } catch {
    ElMessage.error('加载历史记录失败')
    rawHistoryList.value = []
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  page.value = 1
}

const resetFilter = () => {
  filterForm.status = ''
  filterForm.type = ''
  filterForm.dateRange = []
  page.value = 1
}

const viewDetail = (item: NotificationItem) => {
  detailDialog.item = item
  detailDialog.visible = true
}

onMounted(() => {
  void loadHistory()
})
</script>

<style scoped>
.notification-history-page {
  display: flex;
  flex-direction: column;
  gap: var(--page-section-gap);
}

.history-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 420px);
  gap: var(--space-5);
  overflow: hidden;
  padding: 24px;
}

.history-hero::before,
.history-hero::after {
  content: '';
  position: absolute;
  pointer-events: none;
}

.history-hero::before {
  inset: -20% auto auto 56%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79, 141, 246, 0.18), transparent 72%);
}

.history-hero::after {
  inset: auto auto -24% -8%;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(228, 100, 108, 0.14), transparent 70%);
}

.hero-main,
.hero-side {
  position: relative;
  z-index: 1;
}

.hero-main {
  display: flex;
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
  max-width: 17ch;
  font-size: clamp(1.7rem, 1.32rem + 0.9vw, 2.35rem);
  line-height: 1.06;
  font-weight: var(--font-bold);
  letter-spacing: var(--letter-spacing-tight);
  color: var(--text-primary);
}

.hero-description,
.metric-detail,
.spotlight-description,
.panel-description {
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

.metric-card.info {
  --metric-bg: rgba(75, 159, 216, 0.14);
  --metric-color: var(--info-700);
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
  font-size: clamp(1.36rem, 1.08rem + 0.62vw, 1.9rem);
  line-height: 1.05;
}

.hero-side {
  display: grid;
  gap: 12px;
}

.hero-side-card,
.filter-panel,
.history-panel {
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

.spotlight-main {
  margin: 0 0 10px;
  color: var(--text-primary);
  font-size: 0.98rem;
  font-weight: var(--font-semibold);
  line-height: 1.5;
}

.filter-pill-list,
.filter-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.filter-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: var(--radius-full);
  background: rgba(79, 141, 246, 0.1);
  color: var(--primary-700);
  font-size: 0.78rem;
  font-weight: var(--font-medium);
}

.filter-form :deep(.el-form-item) {
  margin-right: 14px;
  margin-bottom: 0;
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

.history-timeline {
  margin-top: 0;
}

.timeline-content {
  padding: 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.24);
}

.timeline-header {
  display: flex;
  flex-wrap: wrap;
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
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.channel {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.45);
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

@media (max-width: 1200px) {
  .history-hero {
    grid-template-columns: 1fr;
  }

  .hero-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 992px) {
  .hero-toolbar,
  .panel-head,
  .hero-side-head,
  .timeline-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .queue-summary {
    align-items: flex-start;
  }
}

@media (max-width: 768px) {
  .history-hero,
  .filter-panel,
  .history-panel,
  .hero-side-card {
    padding: 18px;
  }

  .hero-title {
    max-width: none;
    font-size: 1.5rem;
  }

  .hero-metrics {
    grid-template-columns: 1fr;
  }

  .pagination {
    justify-content: flex-start;
  }
}
</style>
