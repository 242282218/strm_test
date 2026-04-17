<template>
  <div class="scrape-records-page">
    <section class="records-hero page-surface">
      <div class="hero-main">
        <div class="hero-toolbar">
          <div class="hero-copy">
            <span class="hero-chip">Scrape Review</span>
            <h2 class="hero-title">刮削结果、失败线索与批量处理集中收口</h2>
            <p class="hero-description">
              把记录总量、失败记录、当前筛选范围和批量操作放到同一工作台，避免刮削记录继续停留在表单和表格直排。
            </p>
          </div>

          <div class="hero-actions">
            <el-button :icon="RefreshRight" data-testid="scrape-records-refresh" @click="loadRecords">刷新</el-button>
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
            <el-tag :type="spotlightBadgeType" size="small">{{ spotlightBadgeLabel }}</el-tag>
          </div>

          <template v-if="spotlightRecord">
            <p class="spotlight-main">{{ spotlightRecord.source_file }}</p>
            <p class="spotlight-description">
              {{ spotlightRecord.title || '未识别标题' }} · {{ formatTime(spotlightRecord.updated_at || spotlightRecord.created_at) }}
            </p>
          </template>

          <p v-else class="spotlight-description">
            记录加载完成后，这里会优先显示最近失败记录或最近更新的一条结果。
          </p>
        </article>

        <article class="hero-side-card">
          <div class="hero-side-head">
            <div class="hero-side-heading">
              <span class="section-label">筛选</span>
              <h3 class="hero-side-title">当前视图范围</h3>
            </div>
            <el-tag :type="activeFilterCount > 0 ? 'primary' : 'info'" size="small">
              {{ activeFilterCount > 0 ? `${activeFilterCount} 条条件` : '全量记录' }}
            </el-tag>
          </div>

          <p class="spotlight-description">{{ filterSummary }}</p>

          <div v-if="activeFilterSegments.length > 0" class="filter-pill-list">
            <span v-for="segment in activeFilterSegments" :key="segment" class="filter-pill">
              {{ segment }}
            </span>
          </div>

          <div class="filter-actions">
            <el-button v-if="activeFilterCount > 0" text @click="resetFilters">重置筛选</el-button>
            <el-button plain @click="loadRecords">刷新结果</el-button>
          </div>
        </article>
      </div>
    </section>

    <section class="filter-panel page-surface">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">检索</span>
          <h3 class="panel-title">记录筛选</h3>
          <p class="panel-description">按关键词和状态收束记录，查询时自动回到第一页。</p>
        </div>
      </div>

      <el-form :inline="true" class="filter-form">
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            placeholder="文件名/标题/错误"
            clearable
            @keyup.enter="applyFilters"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 170px">
            <el-option label="pending" value="pending" />
            <el-option label="scanned" value="scanned" />
            <el-option label="scraping" value="scraping" />
            <el-option label="scraped" value="scraped" />
            <el-option label="renaming" value="renaming" />
            <el-option label="renamed" value="renamed" />
            <el-option label="scrape_failed" value="scrape_failed" />
            <el-option label="rename_failed" value="rename_failed" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="applyFilters">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </section>

    <section class="records-panel page-surface" v-loading="loading">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">工作台</span>
          <h3 class="panel-title">记录工作台</h3>
          <p class="panel-description">在当前结果窗口中执行批量重刮、失败清理和详情回看。</p>
        </div>

        <div class="toolbar">
          <el-button type="primary" :disabled="selectedIds.length === 0" @click="reScrapeSelected">
            重新刮削 ({{ selectedIds.length }})
          </el-button>
          <el-button type="warning" @click="clearFailedRecords">清理失败</el-button>
          <el-button type="danger" @click="truncateAllRecords">清空记录</el-button>
        </div>
      </div>

      <template v-if="records.length > 0">
        <div class="table-shell">
          <el-table
            :data="records"
            stripe
            @selection-change="handleSelectionChange"
          >
            <el-table-column type="selection" width="45" />
            <el-table-column prop="source_file" label="源文件" min-width="220" show-overflow-tooltip />
            <el-table-column prop="target_file" label="目标文件" min-width="220" show-overflow-tooltip />
            <el-table-column prop="title" label="识别标题" min-width="150" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="130">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="error_code" label="错误码" width="130" />
            <el-table-column label="更新时间" width="180">
              <template #default="{ row }">{{ formatTime(row.updated_at || row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="110" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="openDetail(row.record_id)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pagination">
          <el-pagination
            background
            layout="total, prev, pager, next, sizes"
            :total="total"
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.size"
            @current-change="loadRecords"
            @size-change="loadRecords"
          />
        </div>
      </template>

      <EmptyState
        v-else-if="!loading"
        title="暂无刮削记录"
        description="当前筛选范围内没有匹配记录，可以放宽条件或等待新的刮削结果写入。"
        action-text="刷新记录"
        @action="loadRecords"
      />
    </section>

    <el-drawer v-model="detail.visible" title="记录详情" size="42%" destroy-on-close>
      <div v-if="detail.loading" class="detail-loading">
        <el-skeleton :rows="8" animated />
      </div>
      <div v-else-if="detail.record">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="Record ID">{{ detail.record.record_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.record.status }}</el-descriptions-item>
          <el-descriptions-item label="源文件">{{ detail.record.source_file }}</el-descriptions-item>
          <el-descriptions-item label="目标文件">{{ detail.record.target_file || '-' }}</el-descriptions-item>
          <el-descriptions-item label="识别标题">{{ detail.record.title || '-' }}</el-descriptions-item>
          <el-descriptions-item label="TMDB ID">{{ detail.record.tmdb_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="错误码">{{ detail.record.error_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="错误信息">
            <div class="error-message">{{ detail.record.error_message || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="处理建议">
            <el-tag type="info" effect="plain">{{ errorSuggestion(detail.record.error_code) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="识别信息">
            <pre class="recognition-json">{{ formatRecognition(detail.record.recognition_result) }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <el-empty v-else description="暂无详情" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Collection, Filter, RefreshRight, Warning, CircleCheck } from '@/components/icons'
import EmptyState from '@/components/EmptyState.vue'
import { scrapeApi, type ScrapeRecord } from '@/features/scrape/api/scrape'

type MetricTone = 'primary' | 'success' | 'warning' | 'info'

interface HeroMetric {
  label: string
  value: string
  detail: string
  icon: Component
  tone: MetricTone
}

const loading = ref(false)
const records = ref<ScrapeRecord[]>([])
const total = ref(0)
const selectedIds = ref<string[]>([])

const filters = reactive({
  keyword: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  size: 20
})

const detail = reactive<{
  visible: boolean
  loading: boolean
  record: ScrapeRecord | null
}>({
  visible: false,
  loading: false,
  record: null
})

type ApiDetailError = {
  response?: {
    data?: {
      detail?: string
    }
  }
}

const resolveErrorMessage = (error: unknown, fallback: string): string => {
  if (error && typeof error === 'object') {
    const detail = (error as ApiDetailError).response?.data?.detail
    if (typeof detail === 'string' && detail) {
      return detail
    }
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}

const statusTagType = (status: string): '' | 'success' | 'warning' | 'danger' | 'info' => {
  if (status === 'renamed') return 'success'
  if (status === 'scrape_failed' || status === 'rename_failed') return 'danger'
  if (status === 'pending' || status === 'scanned') return 'info'
  return 'warning'
}

const formatTime = (time: string): string => {
  const value = new Date(time)
  if (Number.isNaN(value.getTime())) return time
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(
    value.getDate()
  ).padStart(2, '0')} ${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}`
}

const activeFilterSegments = computed(() => {
  const segments: string[] = []

  if (filters.keyword.trim()) {
    segments.push(`关键词 ${filters.keyword.trim()}`)
  }

  if (filters.status) {
    segments.push(`状态 ${filters.status}`)
  }

  return segments
})

const activeFilterCount = computed(() => activeFilterSegments.value.length)

const filterSummary = computed(() => {
  if (activeFilterSegments.value.length === 0) {
    return '当前展示完整刮削记录，可按关键词和状态快速聚焦。'
  }

  return `当前已收束到 ${activeFilterSegments.value.join(' · ')}。`
})

const failedCount = computed(() => {
  return records.value.filter(record => record.status === 'scrape_failed' || record.status === 'rename_failed').length
})

const spotlightRecord = computed<ScrapeRecord | null>(() => {
  const failedRecord = records.value.find(record => record.status === 'scrape_failed' || record.status === 'rename_failed')
  if (failedRecord) {
    return failedRecord
  }

  return records.value[0] ?? null
})

const spotlightTitle = computed(() => {
  if (!spotlightRecord.value) {
    return '当前记录焦点'
  }

  return spotlightRecord.value.status === 'scrape_failed' || spotlightRecord.value.status === 'rename_failed'
    ? '最近失败记录'
    : '最近更新记录'
})

const spotlightBadgeLabel = computed(() => {
  if (!spotlightRecord.value) {
    return '暂无记录'
  }

  return spotlightRecord.value.status
})

const spotlightBadgeType = computed(() => {
  return spotlightRecord.value ? statusTagType(spotlightRecord.value.status) || 'info' : 'info'
})

const heroMetrics = computed<HeroMetric[]>(() => {
  return [
    {
      label: '记录总数',
      value: `${total.value}`,
      detail: '当前结果窗口中的刮削记录总量。',
      icon: Collection,
      tone: 'primary'
    },
    {
      label: '失败记录',
      value: `${failedCount.value}`,
      detail: '需要优先回看的失败记录数量。',
      icon: Warning,
      tone: failedCount.value > 0 ? 'warning' : 'success'
    },
    {
      label: '已选条目',
      value: `${selectedIds.value.length}`,
      detail: '当前用于批量重刮的已选记录数量。',
      icon: CircleCheck,
      tone: selectedIds.value.length > 0 ? 'success' : 'info'
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

const loadRecords = async (): Promise<void> => {
  loading.value = true
  try {
    const data = await scrapeApi.listRecords({
      keyword: filters.keyword || undefined,
      status: filters.status || undefined,
      page: pagination.page,
      size: pagination.size
    })
    records.value = data.items || []
    total.value = data.total || 0
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '加载记录失败'))
    records.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const applyFilters = (): void => {
  pagination.page = 1
  void loadRecords()
}

const resetFilters = (): void => {
  filters.keyword = ''
  filters.status = ''
  pagination.page = 1
  void loadRecords()
}

const handleSelectionChange = (selection: ScrapeRecord[]): void => {
  selectedIds.value = selection.map((item) => item.record_id)
}

const reScrapeSelected = async (): Promise<void> => {
  if (selectedIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确认重新刮削已选 ${selectedIds.value.length} 条记录吗？`, '重新刮削', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    const result = await scrapeApi.reScrape(selectedIds.value)
    ElMessage.success(`已提交 ${result.updated} 条记录重新处理`)
    selectedIds.value = []
    await loadRecords()
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '重新刮削失败'))
  }
}

const clearFailedRecords = async (): Promise<void> => {
  try {
    await ElMessageBox.confirm('确认清理所有失败记录吗？', '清理失败', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    const result = await scrapeApi.clearFailed()
    ElMessage.success(`已清理 ${result.cleared} 条失败记录`)
    await loadRecords()
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '清理失败记录失败'))
  }
}

const truncateAllRecords = async (): Promise<void> => {
  try {
    await ElMessageBox.confirm('确认清空全部刮削记录吗？该操作不可恢复。', '清空记录', {
      type: 'warning',
      confirmButtonText: '确认清空',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    const result = await scrapeApi.truncateAll()
    ElMessage.success(`已清空 ${result.truncated} 条记录`)
    selectedIds.value = []
    await loadRecords()
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '清空记录失败'))
  }
}

const openDetail = async (recordId: string): Promise<void> => {
  detail.visible = true
  detail.loading = true
  detail.record = null
  try {
    detail.record = await scrapeApi.getRecord(recordId)
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '加载详情失败'))
  } finally {
    detail.loading = false
  }
}

const formatRecognition = (value: Record<string, unknown> | null): string => {
  if (!value) return '-'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return '-'
  }
}

const errorSuggestion = (errorCode: string | null): string => {
  if (!errorCode) return '无错误，无需处理'
  if (errorCode.includes('TMDB') || errorCode.includes('SCRAPE')) return '检查 TMDB 参数或文件命名，再重试'
  if (errorCode.includes('RENAME')) return '检查目标目录权限与重名冲突'
  if (errorCode.includes('SOURCE')) return '确认源文件仍存在并可访问'
  return '查看错误详情后重试，必要时手工修复'
}

onMounted(() => {
  void loadRecords()
})
</script>

<style scoped>
.scrape-records-page {
  display: flex;
  flex-direction: column;
  gap: var(--page-section-gap);
}

.records-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 420px);
  gap: var(--space-5);
  overflow: hidden;
  padding: 24px;
}

.records-hero::before,
.records-hero::after {
  content: '';
  position: absolute;
  pointer-events: none;
}

.records-hero::before {
  inset: -20% auto auto 56%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79, 141, 246, 0.18), transparent 72%);
}

.records-hero::after {
  inset: auto auto -24% -8%;
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
.records-panel {
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

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.table-shell {
  overflow-x: auto;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.detail-loading {
  padding: 16px;
}

.error-message {
  white-space: pre-wrap;
  word-break: break-word;
}

.recognition-json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 1200px) {
  .records-hero {
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
  .records-hero,
  .filter-panel,
  .records-panel,
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
