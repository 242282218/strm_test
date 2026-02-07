<template>
  <div class="emby-monitor-page">
    <div class="page-header">
      <h2>Emby 监控</h2>
      <div class="header-actions">
        <el-switch v-model="autoRefresh" active-text="自动刷新" inactive-text="手动刷新" @change="toggleAutoRefresh" />
        <el-button :loading="loading.refresh" @click="loadAll">刷新数据</el-button>
        <el-button type="primary" :loading="loading.triggerRefresh" @click="triggerRefresh">触发刷新</el-button>
        <el-button type="success" :loading="loading.sync" @click="triggerSync">触发同步</el-button>
      </div>
    </div>

    <el-row :gutter="16" class="status-row">
      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <template #header>连接状态</template>
          <el-tag :type="status?.enabled ? (status?.connected ? 'success' : 'warning') : 'info'">
            {{ statusTagText }}
          </el-tag>
          <div class="status-line">URL: {{ status?.configuration.url || '-' }}</div>
          <div class="status-line">聚合窗口: {{ status?.configuration.episode_aggregate_window_seconds || 10 }} 秒</div>
          <div class="status-line">删除执行: {{ status?.configuration.delete_execute_enabled ? '已开启' : '已关闭' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <template #header>最近刷新</template>
          <div v-if="latestRefresh">
            <div class="status-line">
              结果:
              <el-tag :type="latestRefresh.success ? 'success' : 'danger'" size="small">
                {{ latestRefresh.success ? '成功' : '失败' }}
              </el-tag>
            </div>
            <div class="status-line">{{ latestRefresh.message }}</div>
            <div class="status-line">{{ formatTime(latestRefresh.timestamp) }}</div>
          </div>
          <el-empty v-else description="暂无刷新记录" :image-size="50" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <template #header>事件概览</template>
          <div class="status-line">当前页事件数: {{ events.length }}</div>
          <div class="status-line">总事件数: {{ total }}</div>
          <div class="status-line">
            过滤条件:
            {{ filters.event_type || '全部事件' }} / {{ filters.item_type || '全部类型' }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-header">
          <span>Webhook 事件流</span>
          <span class="hint">按更新时间倒序</span>
        </div>
      </template>

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
    </el-card>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-header">
          <span>删除计划（Dry-run）</span>
          <el-tag type="warning" effect="plain">默认仅预演，不执行真实删除</el-tag>
        </div>
      </template>

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
    </el-card>

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

const statusTagText = computed(() => {
  if (!status.value?.enabled) return '未启用'
  return status.value.connected ? '已连接' : '未连接'
})

const latestRefresh = computed(() => {
  return refreshHistory.value.length > 0 ? refreshHistory.value[0] : null
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
  status.value = await embyApi.getStatus({ probe: true, probe_timeout: 3 })
}

const loadRefreshHistory = async (): Promise<void> => {
  const result = await embyApi.getRefreshHistory({ limit: 10 })
  refreshHistory.value = result.history || []
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
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载事件失败')
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
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载监控数据失败')
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
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '触发刷新失败')
  } finally {
    loading.triggerRefresh = false
  }
}

const triggerSync = async (): Promise<void> => {
  loading.sync = true
  try {
    await embyApi.triggerSync()
    ElMessage.success('同步任务已触发')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '触发同步失败')
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
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '生成计划失败')
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
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '执行计划失败')
  } finally {
    loading.execute = false
  }
}

const startAutoRefresh = (): void => {
  if (timer) return
  timer = window.setInterval(() => {
    if (!autoRefresh.value) return
    void loadAll()
  }, 10000)
}

const stopAutoRefresh = (): void => {
  if (!timer) return
  window.clearInterval(timer)
  timer = null
}

const toggleAutoRefresh = (enabled: boolean): void => {
  if (enabled) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

onMounted(async () => {
  await loadAll()
  startAutoRefresh()
})

onBeforeUnmount(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.emby-monitor-page {
  padding: 8px;
}

.page-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.page-header h2 {
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.status-row {
  margin-bottom: 16px;
}

.status-line {
  margin-top: 8px;
  color: #606266;
  font-size: 13px;
}

.card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hint {
  color: #909399;
  font-size: 12px;
}

.filters {
  margin-bottom: 12px;
}

.pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.delete-plan-form {
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
