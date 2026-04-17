<template>
  <div class="workbench-page emby-monitor-page">
    <section class="workbench-hero page-surface" data-testid="emby-monitor-hero">
      <div class="workbench-main">
        <div class="workbench-toolbar">
          <div class="workbench-copy">
            <span class="workbench-chip">Emby Watch</span>
            <h2 class="workbench-title">Emby 监控、事件流与删除计划统一收口</h2>
            <p class="workbench-description">
              首屏先给出 Emby 连接、最近刷新和当前过滤范围，再进入事件流与 dry-run 删除计划，方便判断链路是否健康。
            </p>
          </div>

          <div class="workbench-actions">
            <el-switch
              v-model="autoRefresh"
              active-text="自动刷新"
              inactive-text="手动刷新"
              @change="toggleAutoRefresh"
            />
            <el-button :loading="loading.refresh" data-testid="emby-refresh-button" @click="loadAll">刷新数据</el-button>
            <el-button type="primary" :loading="loading.triggerRefresh" @click="triggerRefresh">触发刷新</el-button>
            <el-button type="success" :loading="loading.sync" @click="triggerSync">触发同步</el-button>
          </div>
        </div>

        <div class="workbench-metrics">
          <article
            v-for="metric in heroMetrics"
            :key="metric.label"
            class="workbench-metric"
          >
            <span class="workbench-metric-label">{{ metric.label }}</span>
            <strong class="workbench-metric-value">{{ metric.value }}</strong>
            <p class="workbench-metric-detail">{{ metric.detail }}</p>
          </article>
        </div>
      </div>

      <div class="workbench-side">
        <article class="workbench-side-card">
          <div class="workbench-side-head">
            <div class="workbench-side-heading">
              <span class="workbench-side-kicker">Latest Refresh</span>
              <h3 class="workbench-side-title">{{ latestRefresh ? '最近一次刷新' : '暂无刷新记录' }}</h3>
            </div>
          </div>

          <template v-if="latestRefresh">
            <div class="refresh-state">
              <el-tag :type="latestRefresh.success ? 'success' : 'danger'" size="small">
                {{ latestRefresh.success ? '成功' : '失败' }}
              </el-tag>
              <span>{{ formatTime(latestRefresh.timestamp) }}</span>
            </div>
            <p class="workbench-side-copy">{{ latestRefresh.message }}</p>
          </template>
          <p v-else class="workbench-side-copy">还没有读取到最近刷新记录，可手动触发一次刷新或等待自动轮询。</p>
        </article>

        <article class="workbench-side-card">
          <div class="workbench-side-head">
            <div class="workbench-side-heading">
              <span class="workbench-side-kicker">Delete Plan</span>
              <h3 class="workbench-side-title">{{ currentPlan ? '当前 dry-run 计划' : '等待生成删除计划' }}</h3>
            </div>
          </div>

          <p class="workbench-side-copy">{{ currentPlanSummary }}</p>
          <div v-if="currentPlan" class="plan-focus">
            <span>计划 ID</span>
            <strong>{{ currentPlan.plan_id }}</strong>
            <span>可执行 {{ currentPlan.executable_items }} / {{ currentPlan.total_items }}</span>
          </div>
        </article>
      </div>
    </section>

    <section class="workbench-section page-surface" data-testid="emby-events-panel">
      <div class="workbench-section-head">
        <div class="workbench-section-heading">
          <span class="workbench-section-kicker">Webhook Stream</span>
          <h3 class="workbench-section-title">Webhook 事件流</h3>
          <p class="workbench-section-description">按更新时间倒序查看事件，支持类型和关键词过滤。</p>
        </div>
      </div>

      <el-form :inline="true" class="filters">
        <el-form-item label="事件类型">
          <el-select v-model="filters.event_type" clearable placeholder="全部" style="width: 180px">
            <el-option label="library.new" value="library.new" />
            <el-option label="library.deleted" value="library.deleted" />
          </el-select>
        </el-form-item>
        <el-form-item label="条目类型">
          <el-select v-model="filters.item_type" clearable placeholder="全部" style="width: 160px">
            <el-option label="Movie" value="Movie" />
            <el-option label="Episode" value="Episode" />
            <el-option label="Series" value="Series" />
            <el-option label="Season" value="Season" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            clearable
            placeholder="event_id / item_id / item_name"
            @keyup.enter="loadEvents"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadEvents">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading.events" :data="events" stripe border>
        <el-table-column prop="event_type" label="事件类型" width="150" />
        <el-table-column prop="item_type" label="条目类型" width="120" />
        <el-table-column prop="item_name" label="条目名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="item_id" label="条目ID" min-width="220" show-overflow-tooltip />
        <el-table-column label="聚合数" width="100">
          <template #default="{ row }">
            <el-tag :type="row.aggregated_count > 1 ? 'warning' : 'info'" size="small">
              {{ row.aggregated_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="180">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewPayload(row)">Payload</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          background
          layout="total, prev, pager, next, sizes"
          :total="total"
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          @current-change="loadEvents"
          @size-change="loadEvents"
        />
      </div>
    </section>

    <section class="workbench-section page-surface" data-testid="emby-delete-plan-panel">
      <div class="workbench-section-head">
        <div class="workbench-section-heading">
          <span class="workbench-section-kicker">Dry Run</span>
          <h3 class="workbench-section-title">删除计划（Dry-run）</h3>
          <p class="workbench-section-description">默认只做计划预演；真实执行仍受后端 feature flag 控制。</p>
        </div>
        <div class="workbench-section-actions">
          <el-tag type="warning" effect="plain">默认仅预演，不执行真实删除</el-tag>
        </div>
      </div>

      <el-form label-width="140px" class="delete-plan-form">
        <el-form-item label="来源">
          <el-input v-model="planForm.source" placeholder="manual" />
        </el-form-item>
        <el-form-item label="事件ID列表">
          <el-input
            v-model="planForm.eventIdsText"
            type="textarea"
            :rows="3"
            placeholder="逗号或换行分隔，可为空"
          />
        </el-form-item>
        <el-form-item label="条目ID列表">
          <el-input
            v-model="planForm.itemIdsText"
            type="textarea"
            :rows="3"
            placeholder="逗号或换行分隔，可为空"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="planForm.reason" placeholder="可选" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading.plan" @click="createPlan">生成删除计划</el-button>
          <el-button
            type="danger"
            :loading="loading.execute"
            :disabled="!currentPlan?.plan_id"
            @click="executePlan"
          >
            执行计划
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="currentPlan"
        type="info"
        :closable="false"
        show-icon
        :title="`计划ID: ${currentPlan.plan_id}，总项: ${currentPlan.total_items}，可执行: ${currentPlan.executable_items}`"
        class="plan-summary"
      />

      <el-table v-if="currentPlan" :data="currentPlan.items" stripe border size="small">
        <el-table-column prop="emby_item_id" label="Emby Item ID" min-width="180" />
        <el-table-column prop="item_name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="item_type" label="类型" width="100" />
        <el-table-column prop="risk_level" label="风险等级" width="100" />
        <el-table-column label="可执行" width="100">
          <template #default="{ row }">
            <el-tag :type="row.can_execute ? 'success' : 'info'" size="small">
              {{ row.can_execute ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column prop="execution_status" label="执行状态" width="120" />
      </el-table>
    </section>

    <el-drawer v-model="payloadDrawer.visible" title="Webhook Payload" size="42%" destroy-on-close>
      <pre class="payload-json">{{ payloadDrawer.content }}</pre>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { embyApi, type EmbyRefreshHistoryItem, type EmbyStatus } from '@/api/emby'
import { embyMonitorApi, type EmbyDeletePlanResponse, type EmbyEventLog } from '@/api/embyMonitor'

type HeroMetric = {
  label: string
  value: string
  detail: string
}

const status = ref<EmbyStatus | null>(null)
const refreshHistory = ref<EmbyRefreshHistoryItem[]>([])
const events = ref<EmbyEventLog[]>([])
const total = ref(0)
const autoRefresh = ref(true)
const currentPlan = ref<EmbyDeletePlanResponse | null>(null)
let timer: number | null = null

const loading = reactive({
  refresh: false,
  events: false,
  triggerRefresh: false,
  sync: false,
  plan: false,
  execute: false
})

const filters = reactive({
  event_type: '',
  item_type: '',
  keyword: ''
})

const pagination = reactive({
  page: 1,
  size: 20
})

const planForm = reactive({
  source: 'manual',
  eventIdsText: '',
  itemIdsText: '',
  reason: '',
  executedBy: 'web-ui'
})

const payloadDrawer = reactive({
  visible: false,
  content: ''
})

interface ErrorResponseWithDetail {
  response?: {
    data?: {
      detail?: string
    }
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null
}

const hasErrorResponseDetail = (value: unknown): value is ErrorResponseWithDetail => {
  if (!isRecord(value)) return false
  const response = value.response
  if (!isRecord(response)) return false
  const data = response.data
  if (!isRecord(data)) return false
  return typeof data.detail === 'string'
}

const getErrorDetail = (error: unknown, fallback: string): string => {
  return hasErrorResponseDetail(error) ? error.response?.data?.detail || fallback : fallback
}

const statusTagText = computed(() => {
  if (!status.value?.enabled) return '未启用'
  return status.value.connected ? '已连接' : '未连接'
})

const latestRefresh = computed(() => {
  return refreshHistory.value.length > 0 ? refreshHistory.value[0] : null
})

const heroMetrics = computed<HeroMetric[]>(() => {
  return [
    {
      label: '连接状态',
      value: statusTagText.value,
      detail: status.value?.configuration.url ? `URL: ${status.value.configuration.url}` : '尚未读取到 Emby 地址。'
    },
    {
      label: '聚合窗口',
      value: `${status.value?.configuration.episode_aggregate_window_seconds || 10} 秒`,
      detail: '用于合并短时间内的重复事件。'
    },
    {
      label: '事件总数',
      value: `${total.value}`,
      detail: `当前页 ${events.value.length} 条；过滤条件 ${filters.event_type || '全部事件'} / ${filters.item_type || '全部类型'}`
    },
    {
      label: '自动刷新',
      value: autoRefresh.value ? '已开启' : '已暂停',
      detail: autoRefresh.value ? '页面可见时每 10 秒轮询一次。' : '仅在手动点击时刷新。'
    }
  ]
})

const currentPlanSummary = computed(() => {
  if (!currentPlan.value) {
    return status.value?.configuration.delete_execute_enabled
      ? '删除执行能力已开启，但当前还没有生成 dry-run 计划。'
      : '当前实例默认只允许 dry-run 预演，执行能力未开启。'
  }

  return `计划包含 ${currentPlan.value.total_items} 项，其中 ${currentPlan.value.executable_items} 项可执行。生成新计划后会覆盖这里的摘要。`
})

const splitIds = (text: string): string[] => {
  return text
    .split(/[\n,，]/g)
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

const formatTime = (time: string): string => {
  const value = new Date(time)
  if (Number.isNaN(value.getTime())) return time
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(
    value.getDate()
  ).padStart(2, '0')} ${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}:${String(
    value.getSeconds()
  ).padStart(2, '0')}`
}

const loadStatus = async (): Promise<void> => {
  try {
    status.value = await embyApi.getStatus({ probe: true, probe_timeout: 3 })
  } catch {
    status.value = null
  }
}

const loadRefreshHistory = async (): Promise<void> => {
  try {
    const result = await embyApi.getRefreshHistory({ limit: 10 })
    refreshHistory.value = result.history || []
  } catch {
    refreshHistory.value = []
  }
}

const loadEvents = async (): Promise<void> => {
  loading.events = true
  try {
    const data = await embyMonitorApi.getEvents({
      event_type: filters.event_type || undefined,
      item_type: filters.item_type || undefined,
      keyword: filters.keyword || undefined,
      page: pagination.page,
      size: pagination.size
    })
    events.value = data.items || []
    total.value = data.total || 0
  } catch (error: unknown) {
    ElMessage.error(getErrorDetail(error, '加载事件失败'))
    events.value = []
    total.value = 0
  } finally {
    loading.events = false
  }
}

const loadAll = async (): Promise<void> => {
  loading.refresh = true
  try {
    await Promise.all([loadStatus(), loadRefreshHistory(), loadEvents()])
  } catch (error: unknown) {
    ElMessage.error(getErrorDetail(error, '加载监控数据失败'))
  } finally {
    loading.refresh = false
  }
}

const resetFilters = (): void => {
  filters.event_type = ''
  filters.item_type = ''
  filters.keyword = ''
  pagination.page = 1
  void loadEvents()
}

const viewPayload = (event: EmbyEventLog): void => {
  payloadDrawer.visible = true
  payloadDrawer.content = JSON.stringify(event.payload || {}, null, 2)
}

const triggerRefresh = async (): Promise<void> => {
  loading.triggerRefresh = true
  try {
    await embyApi.refresh()
    ElMessage.success('刷新任务已触发')
    await loadRefreshHistory()
  } catch (error: unknown) {
    ElMessage.error(getErrorDetail(error, '触发刷新失败'))
  } finally {
    loading.triggerRefresh = false
  }
}

const triggerSync = async (): Promise<void> => {
  loading.sync = true
  try {
    await embyApi.triggerSync()
    ElMessage.success('同步任务已触发')
  } catch (error: unknown) {
    ElMessage.error(getErrorDetail(error, '触发同步失败'))
  } finally {
    loading.sync = false
  }
}

const createPlan = async (): Promise<void> => {
  const eventIds = splitIds(planForm.eventIdsText)
  const itemIds = splitIds(planForm.itemIdsText)
  if (eventIds.length === 0 && itemIds.length === 0) {
    ElMessage.warning('请至少填写事件ID或条目ID')
    return
  }

  loading.plan = true
  try {
    const plan = await embyMonitorApi.createDeletePlan({
      source: planForm.source || 'manual',
      event_ids: eventIds,
      item_ids: itemIds,
      reason: planForm.reason || undefined
    })
    currentPlan.value = plan
    ElMessage.success('删除计划已生成（dry-run）')
  } catch (error: unknown) {
    ElMessage.error(getErrorDetail(error, '生成计划失败'))
  } finally {
    loading.plan = false
  }
}

const executePlan = async (): Promise<void> => {
  if (!currentPlan.value?.plan_id) return

  try {
    await ElMessageBox.confirm(
      '该操作将尝试执行删除计划（受后端 feature flag 保护），是否继续？',
      '执行确认',
      {
        type: 'warning',
        confirmButtonText: '确认执行',
        cancelButtonText: '取消'
      }
    )
  } catch {
    return
  }

  loading.execute = true
  try {
    const result = await embyMonitorApi.executeDeletePlan({
      plan_id: currentPlan.value.plan_id,
      executed_by: planForm.executedBy || 'web-ui'
    })
    ElMessage.success(`执行完成：成功 ${result.executed_items}，跳过 ${result.skipped_items}`)
    await createPlan()
  } catch (error: unknown) {
    ElMessage.error(getErrorDetail(error, '执行计划失败'))
  } finally {
    loading.execute = false
  }
}

const refreshWhenVisible = (): void => {
  if (!autoRefresh.value || document.hidden || loading.refresh) return
  void loadAll()
}

const startAutoRefresh = (): void => {
  if (timer) return
  timer = window.setInterval(refreshWhenVisible, 10000)
}

const stopAutoRefresh = (): void => {
  if (!timer) return
  window.clearInterval(timer)
  timer = null
}

const handleVisibilityChange = (): void => {
  if (!autoRefresh.value) return
  if (document.hidden) {
    stopAutoRefresh()
    return
  }
  void loadAll()
  startAutoRefresh()
}

const toggleAutoRefresh = (enabled: boolean): void => {
  if (enabled) {
    if (!document.hidden) {
      void loadAll()
      startAutoRefresh()
    }
    return
  }
  stopAutoRefresh()
}

onMounted(async () => {
  await loadAll()
  if (!document.hidden) {
    startAutoRefresh()
  }
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  stopAutoRefresh()
})
</script>

<style scoped>
.refresh-state {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 0.88rem;
}

.plan-focus {
  padding: 16px 18px;
  border-radius: var(--radius-md);
  background: rgba(79, 141, 246, 0.08);
  border: 1px solid rgba(79, 141, 246, 0.16);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.plan-focus span {
  color: var(--text-secondary);
  font-size: 0.88rem;
}

.plan-focus strong {
  font-size: 1rem;
  font-weight: var(--font-semibold);
}

.filters {
  margin-top: 20px;
  margin-bottom: 12px;
}

.pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.delete-plan-form {
  margin-top: 20px;
  max-width: 920px;
}

.plan-summary {
  margin-bottom: 12px;
}

.payload-json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Consolas', 'SFMono-Regular', monospace;
  font-size: 12px;
  line-height: 1.6;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px;
}
</style>
