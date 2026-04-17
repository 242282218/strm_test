<template>
  <div class="scrape-pathes-page">
    <section class="scrape-hero page-surface">
      <div class="hero-main">
        <div class="hero-toolbar">
          <div class="hero-copy">
            <span class="hero-chip">Scrape Control</span>
            <h2 class="hero-title">目录编排、运行状态与定时触发集中收口</h2>
            <p class="hero-description">
              把目录总量、运行中链路、筛选范围和操作入口放到首屏，避免刮削目录继续停留在表格先行的旧排布。
            </p>
          </div>

          <div class="hero-actions">
            <el-button :icon="RefreshRight" @click="loadPaths">刷新</el-button>
            <el-button
              type="primary"
              :icon="Plus"
              data-testid="scrape-create-button"
              @click="openCreateDialog"
            >
              新增目录
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
              <h3 class="hero-side-title">{{ spotlightTitle }}</h3>
            </div>
            <el-tag :type="spotlightBadgeType" size="small">{{ spotlightBadgeLabel }}</el-tag>
          </div>

          <template v-if="spotlightPath">
            <p class="spotlight-main">
              {{ spotlightPath.source_path }}
            </p>
            <p class="spotlight-description">
              输出到 {{ spotlightPath.dest_path }} · 最近更新 {{ formatTime(spotlightPath.updated_at) }}
            </p>

            <div class="spotlight-tags">
              <el-tag size="small">{{ spotlightPath.media_type }}</el-tag>
              <el-tag size="small" type="info">{{ spotlightPath.scrape_mode }}</el-tag>
              <el-tag size="small" type="warning">{{ spotlightPath.rename_mode }}</el-tag>
            </div>
          </template>

          <p v-else class="spotlight-description">
            目录配置建立后，这里会优先显示当前运行链路或最近更新的一条目录记录。
          </p>
        </article>

        <article class="hero-side-card">
          <div class="hero-side-head">
            <div class="hero-side-heading">
              <span class="section-label">筛选</span>
              <h3 class="hero-side-title">当前视图范围</h3>
            </div>
            <el-tag :type="activeFilterCount > 0 ? 'primary' : 'info'" size="small">
              {{ activeFilterCount > 0 ? `${activeFilterCount} 条条件` : '全量视图' }}
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
            <el-button plain @click="loadPaths">刷新结果</el-button>
          </div>
        </article>
      </div>
    </section>

    <section class="filter-panel page-surface">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">检索</span>
          <h3 class="panel-title">目录筛选</h3>
          <p class="panel-description">按关键词、运行状态和启用开关收束结果，查询时自动回到第一页。</p>
        </div>
      </div>

      <el-form :inline="true" class="filter-form">
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            placeholder="source/dest/path_id"
            clearable
            @keyup.enter="applyFilters"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 150px">
            <el-option label="idle" value="idle" />
            <el-option label="running" value="running" />
            <el-option label="stopped" value="stopped" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-select v-model="filters.enabled" placeholder="全部" clearable style="width: 120px">
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="applyFilters">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </section>

    <section class="queue-panel page-surface" v-loading="loading">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="section-label">队列</span>
          <h3 class="panel-title">目录执行窗口</h3>
          <p class="panel-description">查看当前结果页的目录配置、状态、定时开关和操作入口。</p>
        </div>

        <div class="queue-summary">
          <strong class="queue-count">{{ total }}</strong>
          <span class="queue-count-label">条目录配置</span>
        </div>
      </div>

      <template v-if="paths.length > 0">
        <div class="table-shell">
          <el-table :data="paths" stripe>
            <el-table-column prop="source_path" label="源目录" min-width="220" show-overflow-tooltip />
            <el-table-column prop="dest_path" label="目标目录" min-width="220" show-overflow-tooltip />
            <el-table-column label="媒体类型" width="90">
              <template #default="{ row }">
                <el-tag size="small">{{ row.media_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="模式" width="200">
              <template #default="{ row }">
                <div class="mode-cell">
                  <el-tag size="small" type="info">{{ row.scrape_mode }}</el-tag>
                  <el-tag size="small" type="warning">{{ row.rename_mode }}</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="max_threads" label="并发" width="70" />
            <el-table-column label="定时" width="170">
              <template #default="{ row }">
                <div class="cron-cell">
                  <span class="cron-text">{{ row.cron || '-' }}</span>
                  <el-switch
                    :model-value="row.cron_enabled"
                    :disabled="!row.cron || actionLoadingMap[row.path_id]"
                    @change="toggleCron(row, $event)"
                  />
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="更新时间" width="180">
              <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="300" fixed="right">
              <template #default="{ row }">
                <el-space>
                  <el-button
                    type="primary"
                    link
                    :icon="VideoPlay"
                    :loading="actionLoadingMap[row.path_id]"
                    @click="startPath(row)"
                  >
                    启动
                  </el-button>
                  <el-button
                    type="warning"
                    link
                    :icon="VideoPause"
                    :loading="actionLoadingMap[row.path_id]"
                    @click="stopPath(row)"
                  >
                    停止
                  </el-button>
                  <el-button type="info" link :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
                  <el-button type="danger" link :icon="Delete" @click="deletePath(row)">删除</el-button>
                </el-space>
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
            @current-change="loadPaths"
            @size-change="loadPaths"
          />
        </div>
      </template>

      <EmptyState
        v-else-if="!loading"
        title="暂时没有刮削目录"
        description="新增目录后，这里会展示路径状态、定时计划和对应的运行入口。"
        action-text="新增目录"
        @action="openCreateDialog"
      />
    </section>

    <el-dialog
      v-model="dialog.visible"
      :title="dialog.mode === 'create' ? '新增刮削目录' : '编辑刮削目录'"
      width="760px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="150px">
        <el-form-item label="源目录" prop="source_path">
          <el-input v-model="form.source_path" placeholder="例如: D:/media/raw" />
        </el-form-item>
        <el-form-item label="目标目录" prop="dest_path">
          <el-input v-model="form.dest_path" placeholder="例如: D:/media/library" />
        </el-form-item>
        <el-form-item label="媒体类型" prop="media_type">
          <el-select v-model="form.media_type" style="width: 220px">
            <el-option label="auto" value="auto" />
            <el-option label="movie" value="movie" />
            <el-option label="tv" value="tv" />
          </el-select>
        </el-form-item>
        <el-form-item label="刮削模式" prop="scrape_mode">
          <el-select v-model="form.scrape_mode" style="width: 260px">
            <el-option label="only_scrape" value="only_scrape" />
            <el-option label="scrape_and_rename" value="scrape_and_rename" />
            <el-option label="only_rename" value="only_rename" />
          </el-select>
        </el-form-item>
        <el-form-item label="整理方式" prop="rename_mode">
          <el-select v-model="form.rename_mode" style="width: 260px">
            <el-option label="move" value="move" />
            <el-option label="copy" value="copy" />
            <el-option label="hardlink" value="hardlink" />
            <el-option label="softlink" value="softlink" />
          </el-select>
        </el-form-item>
        <el-form-item label="并发线程" prop="max_threads">
          <el-input-number v-model="form.max_threads" :min="1" :max="32" />
        </el-form-item>
        <el-form-item label="Cron 表达式" prop="cron">
          <el-input v-model="form.cron" placeholder="可空。支持 5 或 6 段 cron" />
        </el-form-item>
        <el-form-item label="启用目录">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="启用二级分类">
          <el-switch v-model="form.enable_secondary_category" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Edit, Plus, RefreshRight, VideoPause, VideoPlay, Collection, Check, Clock } from '@/components/icons'
import EmptyState from '@/components/EmptyState.vue'
import { scrapeApi, type ScrapePath, type ScrapePathCreatePayload } from '@/features/scrape/api/scrape'

type DialogMode = 'create' | 'edit'
type MetricTone = 'primary' | 'success' | 'warning' | 'info'

interface Filters {
  keyword: string
  status: string
  enabled: boolean | undefined
}

interface DialogState {
  visible: boolean
  mode: DialogMode
  editingId: string
}

interface HeroMetric {
  label: string
  value: string
  detail: string
  icon: Component
  tone: MetricTone
}

const loading = ref(false)
const submitting = ref(false)
const paths = ref<ScrapePath[]>([])
const total = ref(0)
const formRef = ref<FormInstance>()
const actionLoadingMap = reactive<Record<string, boolean>>({})

const filters = reactive<Filters>({
  keyword: '',
  status: '',
  enabled: undefined
})

const pagination = reactive({
  page: 1,
  size: 20
})

const dialog = reactive<DialogState>({
  visible: false,
  mode: 'create',
  editingId: ''
})

const form = reactive<ScrapePathCreatePayload>({
  source_path: '',
  dest_path: '',
  media_type: 'auto',
  scrape_mode: 'scrape_and_rename',
  rename_mode: 'move',
  max_threads: 2,
  cron: '',
  enabled: true,
  enable_secondary_category: true
})

const cronValidator = (_rule: unknown, value: string, callback: (error?: Error) => void): void => {
  if (!value) {
    callback()
    return
  }
  const parts = value.trim().split(/\s+/)
  if (parts.length !== 5 && parts.length !== 6) {
    callback(new Error('cron 需为 5 或 6 段'))
    return
  }
  callback()
}

const rules = reactive<FormRules<typeof form>>({
  source_path: [{ required: true, message: '请输入源目录', trigger: 'blur' }],
  dest_path: [{ required: true, message: '请输入目标目录', trigger: 'blur' }],
  cron: [{ validator: cronValidator, trigger: 'blur' }]
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

const statusTagType = (status: string): '' | 'success' | 'warning' | 'info' | 'danger' => {
  if (status === 'running') return 'success'
  if (status === 'stopped') return 'warning'
  if (status === 'idle') return 'info'
  return ''
}

const formatTime = (time?: string | null): string => {
  if (!time) return '-'
  const value = new Date(time)
  if (Number.isNaN(value.getTime())) return String(time)
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

  if (typeof filters.enabled === 'boolean') {
    segments.push(filters.enabled ? '仅看已启用' : '仅看未启用')
  }

  return segments
})

const activeFilterCount = computed(() => activeFilterSegments.value.length)

const filterSummary = computed(() => {
  if (activeFilterSegments.value.length === 0) {
    return '当前展示完整目录列表，可按关键词、状态和启用开关快速聚焦。'
  }

  return `当前已收束到 ${activeFilterSegments.value.join(' · ')}。`
})

const totalPathCount = computed(() => total.value)
const runningCount = computed(() => paths.value.filter(path => path.status === 'running').length)
const enabledCount = computed(() => paths.value.filter(path => path.enabled).length)
const cronEnabledCount = computed(() => paths.value.filter(path => Boolean(path.cron) && path.cron_enabled).length)

const getPathTimestamp = (path: ScrapePath) => {
  const timestamp = Date.parse(path.updated_at || path.created_at)
  return Number.isNaN(timestamp) ? 0 : timestamp
}

const spotlightPath = computed<ScrapePath | null>(() => {
  const runningPath = [...paths.value]
    .filter(path => path.status === 'running')
    .sort((left, right) => getPathTimestamp(right) - getPathTimestamp(left))[0]

  if (runningPath) {
    return runningPath
  }

  return [...paths.value].sort((left, right) => getPathTimestamp(right) - getPathTimestamp(left))[0] ?? null
})

const spotlightTitle = computed(() => {
  if (!spotlightPath.value) {
    return '当前目录焦点'
  }

  return spotlightPath.value.status === 'running' ? '当前运行目录' : '最近更新目录'
})

const spotlightBadgeLabel = computed(() => {
  if (!spotlightPath.value) {
    return '待配置'
  }

  if (spotlightPath.value.status === 'running') {
    return '运行中'
  }

  return spotlightPath.value.enabled ? '已启用' : '未启用'
})

const spotlightBadgeType = computed(() => {
  if (!spotlightPath.value) {
    return 'info'
  }

  if (spotlightPath.value.status === 'running') {
    return 'success'
  }

  return spotlightPath.value.enabled ? 'primary' : 'warning'
})

const heroMetrics = computed<HeroMetric[]>(() => {
  return [
    {
      label: '目录总数',
      value: `${totalPathCount.value}`,
      detail: '当前目录配置总量，覆盖完整分页结果。',
      icon: Collection,
      tone: 'primary'
    },
    {
      label: '运行中',
      value: `${runningCount.value} 条`,
      detail: '基于当前结果页统计，优先暴露活跃执行链路。',
      icon: VideoPlay,
      tone: runningCount.value > 0 ? 'success' : 'info'
    },
    {
      label: '已启用',
      value: `${enabledCount.value} 条`,
      detail: '当前结果页中会参与自动处理的目录数量。',
      icon: Check,
      tone: enabledCount.value > 0 ? 'success' : 'warning'
    },
    {
      label: 'Cron 已开',
      value: `${cronEnabledCount.value} 条`,
      detail: '已配置且打开定时触发的目录数量。',
      icon: Clock,
      tone: cronEnabledCount.value > 0 ? 'primary' : 'info'
    }
  ]
})

const normalizeForm = (row?: ScrapePath): void => {
  form.source_path = row?.source_path ?? ''
  form.dest_path = row?.dest_path ?? ''
  form.media_type = row?.media_type ?? 'auto'
  form.scrape_mode = row?.scrape_mode ?? 'scrape_and_rename'
  form.rename_mode = row?.rename_mode ?? 'move'
  form.max_threads = row?.max_threads ?? 2
  form.cron = row?.cron ?? ''
  form.enabled = row?.enabled ?? true
  form.enable_secondary_category = row?.enable_secondary_category ?? true
}

const loadPaths = async (): Promise<void> => {
  loading.value = true
  try {
    const data = await scrapeApi.listPaths({
      keyword: filters.keyword || undefined,
      status: filters.status || undefined,
      enabled: typeof filters.enabled === 'boolean' ? filters.enabled : undefined,
      page: pagination.page,
      size: pagination.size
    })
    paths.value = data.items || []
    total.value = data.total || 0
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '加载刮削目录失败'))
    paths.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const applyFilters = (): void => {
  pagination.page = 1
  void loadPaths()
}

const resetFilters = (): void => {
  filters.keyword = ''
  filters.status = ''
  filters.enabled = undefined
  pagination.page = 1
  void loadPaths()
}

const openCreateDialog = (): void => {
  dialog.visible = true
  dialog.mode = 'create'
  dialog.editingId = ''
  normalizeForm()
}

const openEditDialog = (row: ScrapePath): void => {
  dialog.visible = true
  dialog.mode = 'edit'
  dialog.editingId = row.path_id
  normalizeForm(row)
}

const submitForm = async (): Promise<void> => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    const payload = {
      ...form,
      cron: form.cron?.trim() ? form.cron.trim() : null
    }
    if (dialog.mode === 'create') {
      await scrapeApi.createPath(payload)
      ElMessage.success('刮削目录已创建')
    } else {
      await scrapeApi.updatePath(dialog.editingId, payload)
      ElMessage.success('刮削目录已更新')
    }
    dialog.visible = false
    await loadPaths()
  } catch (error: unknown) {
    ElMessage.error(resolveErrorMessage(error, '保存失败'))
  } finally {
    submitting.value = false
  }
}

const withRowAction = async (row: ScrapePath, action: () => Promise<void>): Promise<void> => {
  actionLoadingMap[row.path_id] = true
  try {
    await action()
  } finally {
    actionLoadingMap[row.path_id] = false
  }
}

const startPath = async (row: ScrapePath): Promise<void> => {
  await withRowAction(row, async () => {
    try {
      const result = await scrapeApi.startPath(row.path_id)
      if (result.already_running) {
        ElMessage.info('目录任务已在运行，未重复启动')
      } else {
        ElMessage.success('目录任务已启动')
      }
      await loadPaths()
    } catch (error: unknown) {
      ElMessage.error(resolveErrorMessage(error, '启动失败'))
    }
  })
}

const stopPath = async (row: ScrapePath): Promise<void> => {
  await withRowAction(row, async () => {
    try {
      await scrapeApi.stopPath(row.path_id)
      ElMessage.success('目录任务已停止')
      await loadPaths()
    } catch (error: unknown) {
      ElMessage.error(resolveErrorMessage(error, '停止失败'))
    }
  })
}

const toggleCron = async (row: ScrapePath, enabled: boolean): Promise<void> => {
  await withRowAction(row, async () => {
    try {
      await scrapeApi.toggleCron(row.path_id, enabled)
      ElMessage.success(enabled ? '定时任务已开启' : '定时任务已关闭')
      await loadPaths()
    } catch (error: unknown) {
      ElMessage.error(resolveErrorMessage(error, '定时切换失败'))
      await loadPaths()
    }
  })
}

const deletePath = async (row: ScrapePath): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除目录配置 ${row.path_id} 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  await withRowAction(row, async () => {
    try {
      await scrapeApi.deletePath(row.path_id)
      ElMessage.success('目录已删除')
      await loadPaths()
    } catch (error: unknown) {
      ElMessage.error(resolveErrorMessage(error, '删除失败'))
    }
  })
}

onMounted(() => {
  void loadPaths()
})
</script>

<style scoped>
.scrape-pathes-page {
  display: flex;
  flex-direction: column;
  gap: var(--page-section-gap);
}

.scrape-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 420px);
  gap: var(--space-5);
  overflow: hidden;
  padding: 24px;
}

.scrape-hero::before,
.scrape-hero::after {
  content: '';
  position: absolute;
  pointer-events: none;
}

.scrape-hero::before {
  inset: -20% auto auto 56%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79, 141, 246, 0.18), transparent 72%);
}

.scrape-hero::after {
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
.queue-panel {
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

.spotlight-tags,
.filter-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.filter-pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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

.table-shell {
  overflow-x: auto;
}

.mode-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cron-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cron-text {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}

.pagination {
  margin-top: var(--space-5);
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 1200px) {
  .scrape-hero {
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

  .queue-summary {
    align-items: flex-start;
  }
}

@media (max-width: 768px) {
  .scrape-hero,
  .filter-panel,
  .queue-panel,
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
