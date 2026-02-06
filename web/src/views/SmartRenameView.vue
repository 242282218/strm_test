
<template>
  <div class="smart-rename-page">
    <div class="ambient ambient-a"></div>
    <div class="ambient ambient-b"></div>

    <header class="hero-card">
      <div>
        <p class="kicker">SMART RENAME STUDIO</p>
        <h1>智能重命名工作台</h1>
        <p class="subtitle">
          面向完整测试验证的重命名界面：本地与夸克云盘双流程，批量确认/编辑/执行/回滚全可测。
        </p>
      </div>
      <div class="hero-actions">
        <el-tag :type="statusTagType" effect="dark" round>{{ statusTagText }}</el-tag>
        <el-button plain @click="openHistory">
          <el-icon><Document /></el-icon>
          批次记录
        </el-button>
        <el-button plain @click="showHelpDialog = true">
          <el-icon><InfoFilled /></el-icon>
          测试指南
        </el-button>
      </div>
    </header>

    <section class="control-grid">
      <article class="panel">
        <div class="panel-head">
          <h2>1. 选择数据源</h2>
          <el-icon><FolderOpened /></el-icon>
        </div>

        <el-radio-group v-model="sourceMode" class="mode-switch">
          <el-radio-button label="local">本地目录</el-radio-button>
          <el-radio-button label="cloud">夸克云盘</el-radio-button>
        </el-radio-group>

        <template v-if="sourceMode === 'local'">
          <el-input
            v-model="localPath"
            placeholder="输入本地绝对路径，例如：D:/Media/Movies"
            clearable
            class="path-input"
          >
            <template #prepend>本地路径</template>
            <template #append>
              <el-button :disabled="recentPaths.length === 0" @click="useLatestPath">最近一次</el-button>
            </template>
          </el-input>
          <div v-if="recentPaths.length" class="recent-wrap">
            <span class="minor">最近路径</span>
            <el-tag v-for="path in recentPaths" :key="path" size="small" class="recent-tag" @click="localPath = path">
              {{ path }}
            </el-tag>
          </div>
        </template>

        <template v-else>
          <el-input :model-value="cloudFolderLabel || '未选择云盘目录'" readonly class="path-input">
            <template #prepend>云盘目录</template>
            <template #append>
              <el-button @click="showQuarkBrowser = true">浏览</el-button>
            </template>
          </el-input>
          <p class="minor">目录选择由 QuarkFileBrowser 提供，兼容现有接口参数结构。</p>
        </template>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h2>2. 配置策略</h2>
          <el-icon><Cpu /></el-icon>
        </div>

        <div class="row2">
          <div class="field">
            <label>解析算法</label>
            <el-select v-model="selectedAlgorithm">
              <el-option v-for="algo in algorithms" :key="algo.algorithm" :label="algo.name" :value="algo.algorithm" />
            </el-select>
          </div>
          <div class="field">
            <label>命名标准</label>
            <el-select v-model="selectedStandard">
              <el-option v-for="std in namingStandards" :key="std.standard" :label="std.name" :value="std.standard" />
            </el-select>
          </div>
        </div>

        <div v-if="currentAlgorithm" class="algo-box">
          <p class="algo-title">{{ currentAlgorithm.name }}</p>
          <p class="minor">{{ currentAlgorithm.description }}</p>
          <div class="tag-line">
            <el-tag v-for="feature in currentAlgorithm.features" :key="feature" size="small" effect="plain">{{ feature }}</el-tag>
          </div>
        </div>

        <div class="opt-grid">
          <el-checkbox v-model="options.recursive">递归扫描</el-checkbox>
          <el-checkbox v-model="options.createFolders">创建目录结构</el-checkbox>
          <el-checkbox v-model="options.autoConfirm">自动确认高置信度</el-checkbox>
          <el-checkbox v-model="options.forceAiParse">强制 AI 解析</el-checkbox>
        </div>

        <div class="threshold">
          <span class="minor">AI 置信度阈值</span>
          <el-slider v-model="options.aiThreshold" :min="0.4" :max="0.95" :step="0.01" />
          <strong>{{ Math.round(options.aiThreshold * 100) }}%</strong>
        </div>
      </article>
    </section>

    <section class="action-strip">
      <el-button type="primary" :loading="previewing" :disabled="!canPreview" @click="runPreview">
        <el-icon><Search /></el-icon>
        生成预览
      </el-button>
      <el-button type="success" :loading="previewing || executing" :disabled="!canStartWorkflow" @click="startRenameWorkflow">
        <el-icon><VideoPlay /></el-icon>
        {{ startWorkflowLabel }}
      </el-button>
      <el-button :disabled="!hasPreview || previewing" @click="refreshPreview">
        <el-icon><Refresh /></el-icon>
        重新扫描
      </el-button>
      <el-button :disabled="!hasPreview" @click="exportPreview">
        <el-icon><Download /></el-icon>
        导出预览
      </el-button>
      <el-button :disabled="!canRollback" :loading="rollingBack" @click="rollbackLatest">
        <el-icon><RefreshRight /></el-icon>
        回滚最近执行
      </el-button>
      <el-button :loading="testingAiConnectivity" @click="runAiConnectivityTest">
        <el-icon><Cpu /></el-icon>
        AI 连通性测试
      </el-button>
      <el-button :disabled="!hasPreview" @click="resetWorkspace">重置</el-button>
    </section>
    <p class="action-hint">{{ actionHint }}</p>

    <section v-if="cloudWorkflowTask && sourceMode === 'cloud'" class="workflow-task-card">
      <div class="workflow-task-head">
        <strong>任务中心执行</strong>
        <el-tag :type="cloudWorkflowStatusTag" round>{{ cloudWorkflowTask.status }}</el-tag>
      </div>
      <p class="minor">任务ID：{{ cloudWorkflowTask.task_id }}</p>
      <p class="minor">阶段：{{ cloudWorkflowTask.stage }} · {{ cloudWorkflowTask.message }}</p>
      <el-progress
        :percentage="Math.max(0, Math.min(100, Number(cloudWorkflowTask.progress || 0)))"
        :status="cloudWorkflowProgressStatus"
        :stroke-width="10"
      />
      <div class="workflow-task-actions">
        <el-button size="small" :disabled="!isCloudWorkflowRunning" @click="cancelCloudWorkflow">取消任务</el-button>
        <el-button size="small" @click="refreshCloudWorkflowTask(true)">刷新状态</el-button>
      </div>
    </section>

    <section v-if="aiConnectivityResult" class="ai-connectivity-strip">
      <div class="ai-connectivity-head">
        <strong>AI 连通性（{{ aiConnectivityResult.interface === 'smart_rename' ? '本地接口' : '云盘接口' }}）</strong>
        <el-tag :type="aiConnectivityResult.all_connected ? 'success' : 'warning'" round>
          {{ aiConnectivityResult.all_connected ? '全部可用' : '部分异常' }}
        </el-tag>
      </div>
      <div class="ai-connectivity-grid">
        <div
          v-for="provider in aiConnectivityResult.providers"
          :key="provider.provider"
          class="ai-connectivity-item"
        >
          <p class="strong">{{ provider.provider.toUpperCase() }}</p>
          <el-tag
            size="small"
            :type="provider.connected ? 'success' : (provider.configured ? 'danger' : 'info')"
          >
            {{ provider.connected ? '已连接' : (provider.configured ? '连接失败' : '未配置') }}
          </el-tag>
          <p class="minor">{{ provider.message }}</p>
        </div>
      </div>
    </section>

    <section v-if="hasPreview" ref="workspaceRef" class="workspace">
      <div class="summary-grid">
        <div class="summary"><span>批次 ID</span><strong>{{ previewBatchId }}</strong></div>
        <div class="summary"><span>总项目</span><strong>{{ totalItems }}</strong></div>
        <div class="summary"><span>待确认</span><strong>{{ pendingItems }}</strong></div>
        <div class="summary"><span>匹配成功</span><strong>{{ matchedItems }}</strong></div>
        <div class="summary"><span>平均置信度</span><strong>{{ Math.round(averageConfidence * 100) }}%</strong></div>
      </div>

      <div class="filter-row">
        <el-input v-model="keyword" placeholder="按原文件名/新文件名搜索" clearable>
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="statusFilter">
          <el-option v-for="opt in statusFilterOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-select v-model="confidenceFilter">
          <el-option v-for="opt in confidenceFilterOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-select v-model="sortKey">
          <el-option v-for="opt in sortOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </div>

      <div class="batch-tools">
        <el-button :disabled="selectedRows.length === 0" @click="markSelectedAsConfirmed">批量确认</el-button>
        <el-button :disabled="selectedRows.length !== 1" @click="editSingleSelected">编辑选中</el-button>
        <el-button :disabled="selectedRows.length === 0" @click="selectPendingOnly">仅选待确认</el-button>
        <el-button :disabled="selectedRows.length === 0" @click="clearSelection">清空勾选</el-button>
      </div>

      <el-table :data="displayRows" row-key="id" class="result-table" empty-text="暂无可展示数据">
        <el-table-column width="56" fixed="left">
          <template #header>
            <el-checkbox
              :model-value="allDisplayedSelected"
              :indeterminate="partiallyDisplayedSelected"
              @change="toggleSelectDisplayed"
            />
          </template>
          <template #default="{ row }">
            <el-checkbox :model-value="isRowSelected(row.id)" @change="onRowCheck(row.id, $event)" />
          </template>
        </el-table-column>

        <el-table-column label="原文件" min-width="240">
          <template #default="{ row }">
            <div class="name-cell">
              <p class="strong">{{ row.original_name }}</p>
              <p class="minor">{{ row.original_path }}</p>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="建议名称" min-width="250">
          <template #default="{ row }">
            <div class="name-cell">
              <p class="strong">{{ row.new_name }}</p>
              <p class="minor">
                {{ getMediaTypeText(row.media_type) }}
                <span v-if="row.season && row.episode"> · S{{ row.season }}E{{ row.episode }}</span>
              </p>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="匹配" min-width="170">
          <template #default="{ row }">
            <div class="name-cell">
              <p>{{ row.tmdb_title || '未匹配 TMDB' }}</p>
              <el-tag v-if="row.tmdb_id" size="small" effect="plain">TMDB {{ row.tmdb_id }}</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="置信度" width="160">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round((row.overall_confidence || 0) * 100)"
              :status="confidenceStatus(row.overall_confidence || 0)"
              :stroke-width="9"
            />
          </template>
        </el-table-column>

        <el-table-column label="状态" width="160">
          <template #default="{ row }">
            <div class="name-cell">
              <el-tag :type="statusType(row)" round>{{ statusText(row) }}</el-tag>
              <small class="minor" v-if="row.needs_confirmation || row.confirmation_reason">
                {{ row.confirmation_reason || '需要人工确认' }}
              </small>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <div class="ops-cell">
              <el-button text type="primary" @click="openEditDialog(row)">编辑</el-button>
              <el-button text type="danger" @click="removeFromSelection(row.id)">移出执行</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <footer class="execute-bar">
        <div class="execute-meta">
          <el-icon><Collection /></el-icon>
          <span>已勾选 {{ selectedRows.length }} / {{ totalItems }}</span>
          <span>来源：{{ previewSourceMode === 'local' ? '本地目录' : '夸克云盘' }}</span>
          <span>算法：{{ previewAlgorithmUsed }}</span>
          <span>标准：{{ previewNamingUsed }}</span>
        </div>
        <div class="execute-actions">
          <el-button :disabled="selectedRows.length !== 1" @click="validateSelectedName">校验命名</el-button>
          <el-button type="success" :loading="executing" :disabled="!canExecute" @click="executeSelected">
            <el-icon><CircleCheck /></el-icon>
            执行重命名
          </el-button>
        </div>
      </footer>
    </section>

    <el-empty v-else class="empty-block" description="先选择数据源并点击“生成预览”开始测试" />
    <el-dialog v-model="editDialogVisible" title="编辑重命名项" width="620px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="原文件名"><el-input :model-value="editingItem.original_name" disabled /></el-form-item>
        <el-form-item label="新文件名"><el-input v-model="editingItem.new_name" /></el-form-item>
        <el-form-item label="TMDB 标题"><el-input v-model="editingItem.tmdb_title" /></el-form-item>
        <el-form-item label="媒体类型">
          <el-select v-model="editingItem.media_type">
            <el-option label="电影" value="movie" />
            <el-option label="剧集" value="tv" />
            <el-option label="动漫" value="anime" />
            <el-option label="未知" value="unknown" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="nameValidation"
        :title="nameValidation.is_valid ? '命名校验通过' : '命名建议检查'"
        :type="nameValidation.is_valid ? 'success' : 'warning'"
        :description="validationDescription"
        :closable="false"
        show-icon
      />

      <template #footer>
        <el-button @click="validateEditedName" :loading="validatingName">校验命名</el-button>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showResultDialog" title="执行结果" width="500px" destroy-on-close>
      <div v-if="executeSummary" class="result-grid">
        <div class="result-card success"><span>成功</span><strong>{{ executeSummary.success_items }}</strong></div>
        <div class="result-card fail"><span>失败</span><strong>{{ executeSummary.failed_items }}</strong></div>
        <div class="result-card skip"><span>跳过</span><strong>{{ executeSummary.skipped_items }}</strong></div>
        <div class="result-card total"><span>总计</span><strong>{{ executeSummary.total_items }}</strong></div>
      </div>
      <template #footer><el-button type="primary" @click="showResultDialog = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="showHelpDialog" title="完整测试建议流程" width="620px" destroy-on-close>
      <ol class="help-list">
        <li>先生成预览，验证统计、筛选、排序、搜索可用。</li>
        <li>对低置信度项做批量确认、单项编辑与命名校验。</li>
        <li>执行重命名后核对执行结果与批次记录明细。</li>
        <li>本地模式使用回滚接口，云盘模式使用反向重命名回退。</li>
      </ol>
      <template #footer><el-button type="primary" @click="showHelpDialog = false">知道了</el-button></template>
    </el-dialog>

    <el-drawer v-model="showHistoryDrawer" title="重命名批次记录" size="72%" destroy-on-close>
      <div class="history-layout">
        <section class="history-panel">
          <div class="history-head">
            <h3>批次列表</h3>
            <el-button size="small" @click="loadBatchHistory" :loading="historyLoading">刷新</el-button>
          </div>
          <el-table :data="batchHistory" v-loading="historyLoading" height="480" row-key="batch_id" @row-click="onHistoryBatchClick">
            <el-table-column prop="batch_id" label="Batch ID" min-width="210" />
            <el-table-column prop="status" label="状态" width="130" />
            <el-table-column prop="total_items" label="总数" width="70" />
            <el-table-column prop="success_items" label="成功" width="70" />
            <el-table-column prop="failed_items" label="失败" width="70" />
          </el-table>
        </section>

        <section class="history-panel">
          <div class="history-head"><h3>批次明细 {{ activeHistoryBatchId ? `(${activeHistoryBatchId})` : '' }}</h3></div>
          <el-table :data="historyItems" v-loading="historyItemsLoading" height="480" row-key="id">
            <el-table-column prop="original_name" label="原文件" min-width="170" />
            <el-table-column prop="new_name" label="新文件名" min-width="170" />
            <el-table-column prop="status" label="状态" width="110" />
            <el-table-column prop="confidence" label="置信度" width="90" />
            <el-table-column prop="error_message" label="错误" min-width="160" />
          </el-table>
        </section>
      </div>
    </el-drawer>

    <QuarkFileBrowser v-model="showQuarkBrowser" @select="handleCloudFolderSelect" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CircleCheck,
  Collection,
  Cpu,
  Document,
  Download,
  FolderOpened,
  InfoFilled,
  Refresh,
  RefreshRight,
  Search,
  VideoPlay
} from '@element-plus/icons-vue'
import {
  executeSmartRename,
  getAlgorithms,
  getBatchItems,
  getNamingStandards,
  getRenameBatches,
  getSmartRenameStatus,
  previewSmartRename,
  rollbackSmartRename,
  testSmartRenameAIConnectivity,
  validateFilename,
  type AIConnectivityResponse,
  type AlgorithmInfo,
  type NamingStandardInfo,
  type SmartRenameExecuteResponse,
  type SmartRenameItem,
  type SmartRenameStatus,
  type ValidationResponse
} from '@/api/smartRename'
import {
  cancelCloudRenameWorkflowTask,
  createCloudRenameWorkflowTask,
  executeCloudRename,
  getCloudRenameWorkflowTask,
  smartRenameCloudFiles,
  testCloudRenameAIConnectivity,
  type QuarkRenameItem,
  type QuarkWorkflowTaskStatus
} from '@/api/quark'
import QuarkFileBrowser from '@/components/QuarkFileBrowser.vue'

type SourceMode = 'local' | 'cloud'
type StatusFilter = 'all' | 'pending' | 'matched' | 'unmatched' | 'success' | 'failed'
type ConfidenceFilter = 'all' | 'high' | 'medium' | 'low'
type SortKey = 'confidence_desc' | 'confidence_asc' | 'name_asc' | 'name_desc' | 'new_name_asc' | 'new_name_desc' | 'status'

interface ViewRenameItem extends Omit<SmartRenameItem, 'new_name'> {
  id: string
  new_name: string
  source_mode: SourceMode
}

interface CloudExecutionSnapshot {
  fid: string
  original_name: string
  executed_name: string
}

const RECENT_PATH_KEY = 'smart_rename_recent_paths_v2'

const sourceMode = ref<SourceMode>('local')
const localPath = ref('')
const cloudFolderFid = ref('')
const cloudFolderLabel = ref('')
const recentPaths = ref<string[]>([])
const showQuarkBrowser = ref(false)

const algorithms = ref<AlgorithmInfo[]>([])
const namingStandards = ref<NamingStandardInfo[]>([])
const serviceStatus = ref<SmartRenameStatus | null>(null)

const selectedAlgorithm = ref('ai_enhanced')
const selectedStandard = ref('emby')

const options = reactive({
  recursive: true,
  createFolders: true,
  autoConfirm: false,
  forceAiParse: false,
  aiThreshold: 0.7
})

const namingConfig = reactive({
  movie_template: '{title} ({year})',
  tv_episode_template: '{title} - S{season:02d}E{episode:02d}',
  specials_folder: 'Season 00',
  include_quality: false,
  include_source: false,
  include_codec: false,
  include_tmdb_id: false,
  sanitize_filenames: true
})

const previewing = ref(false)
const executing = ref(false)
const rollingBack = ref(false)
const validatingName = ref(false)
const testingAiConnectivity = ref(false)
const aiConnectivityResult = ref<AIConnectivityResponse | null>(null)

const previewBatchId = ref('')
const previewSourceMode = ref<SourceMode>('local')
const previewAlgorithmUsed = ref('')
const previewNamingUsed = ref('')
const previewTargetLabel = ref('')
const workspaceRef = ref<HTMLElement | null>(null)
const cloudWorkflowTask = ref<QuarkWorkflowTaskStatus | null>(null)
const cloudWorkflowNotified = ref(false)
let cloudWorkflowPollTimer: ReturnType<typeof setInterval> | null = null

const previewRows = ref<ViewRenameItem[]>([])
const selectedRowIds = ref<string[]>([])

const keyword = ref('')
const statusFilter = ref<StatusFilter>('all')
const confidenceFilter = ref<ConfidenceFilter>('all')
const sortKey = ref<SortKey>('confidence_desc')

const editDialogVisible = ref(false)
const editingItem = reactive<Partial<ViewRenameItem>>({})
const nameValidation = ref<ValidationResponse | null>(null)

const executeSummary = ref<SmartRenameExecuteResponse | null>(null)
const showResultDialog = ref(false)
const showHelpDialog = ref(false)
const lastCloudExecution = ref<CloudExecutionSnapshot[]>([])

const showHistoryDrawer = ref(false)
const historyLoading = ref(false)
const historyItemsLoading = ref(false)
const batchHistory = ref<any[]>([])
const historyItems = ref<any[]>([])
const activeHistoryBatchId = ref('')

const statusFilterOptions = [
  { label: '全部状态', value: 'all' },
  { label: '待确认', value: 'pending' },
  { label: '已匹配', value: 'matched' },
  { label: '未匹配', value: 'unmatched' },
  { label: '执行成功', value: 'success' },
  { label: '执行失败', value: 'failed' }
] as const

const confidenceFilterOptions = [
  { label: '全部置信度', value: 'all' },
  { label: '高 (≥ 90%)', value: 'high' },
  { label: '中 (60% - 89%)', value: 'medium' },
  { label: '低 (< 60%)', value: 'low' }
] as const

const sortOptions = [
  { label: '置信度从高到低', value: 'confidence_desc' },
  { label: '置信度从低到高', value: 'confidence_asc' },
  { label: '原文件名 A-Z', value: 'name_asc' },
  { label: '原文件名 Z-A', value: 'name_desc' },
  { label: '建议名称 A-Z', value: 'new_name_asc' },
  { label: '建议名称 Z-A', value: 'new_name_desc' },
  { label: '按状态分组', value: 'status' }
] as const

const hasPreview = computed(() => previewRows.value.length > 0)
const canPreview = computed(() => sourceMode.value === 'local' ? localPath.value.trim().length > 0 : !!cloudFolderFid.value)
const selectedRowSet = computed(() => new Set(selectedRowIds.value))
const selectedRows = computed(() => previewRows.value.filter((row) => selectedRowSet.value.has(row.id)))
const runnableRows = computed(() => previewRows.value.filter((row) => (row.new_name || '').trim().length > 0))
const selectedRunnableRows = computed(() => selectedRows.value.filter((row) => (row.new_name || '').trim().length > 0))

const totalItems = computed(() => previewRows.value.length)
const pendingItems = computed(() => previewRows.value.filter((row) => row.needs_confirmation).length)
const matchedItems = computed(() => previewRows.value.filter((row) => !!row.tmdb_id).length)
const averageConfidence = computed(() => {
  if (!previewRows.value.length) return 0
  return previewRows.value.reduce((sum, row) => sum + (row.overall_confidence || 0), 0) / previewRows.value.length
})

const currentAlgorithm = computed(() => algorithms.value.find((item) => item.algorithm === selectedAlgorithm.value))
const displayRows = computed(() => {
  let rows = [...previewRows.value]

  const q = keyword.value.trim().toLowerCase()
  if (q) {
    rows = rows.filter((row) => {
      const source = `${row.original_name} ${row.original_path}`.toLowerCase()
      const target = `${row.new_name} ${row.tmdb_title || ''}`.toLowerCase()
      return source.includes(q) || target.includes(q)
    })
  }

  if (statusFilter.value !== 'all') {
    rows = rows.filter((row) => {
      if (statusFilter.value === 'pending') return row.needs_confirmation
      if (statusFilter.value === 'matched') return !!row.tmdb_id
      if (statusFilter.value === 'unmatched') return !row.tmdb_id
      if (statusFilter.value === 'success') return row.status === 'success'
      if (statusFilter.value === 'failed') return row.status === 'failed'
      return true
    })
  }

  if (confidenceFilter.value !== 'all') {
    rows = rows.filter((row) => {
      const v = row.overall_confidence || 0
      if (confidenceFilter.value === 'high') return v >= 0.9
      if (confidenceFilter.value === 'medium') return v >= 0.6 && v < 0.9
      return v < 0.6
    })
  }

  rows.sort((a, b) => {
    const nameA = (a.original_name || '').toLowerCase()
    const nameB = (b.original_name || '').toLowerCase()
    const newA = (a.new_name || '').toLowerCase()
    const newB = (b.new_name || '').toLowerCase()
    const confA = a.overall_confidence || 0
    const confB = b.overall_confidence || 0

    if (sortKey.value === 'confidence_desc') return confB - confA
    if (sortKey.value === 'confidence_asc') return confA - confB
    if (sortKey.value === 'name_asc') return nameA.localeCompare(nameB)
    if (sortKey.value === 'name_desc') return nameB.localeCompare(nameA)
    if (sortKey.value === 'new_name_asc') return newA.localeCompare(newB)
    if (sortKey.value === 'new_name_desc') return newB.localeCompare(newA)
    return statusText(a).localeCompare(statusText(b))
  })

  return rows
})

const allDisplayedSelected = computed(() => displayRows.value.length > 0 && displayRows.value.every((row) => selectedRowSet.value.has(row.id)))
const partiallyDisplayedSelected = computed(() => displayRows.value.some((row) => selectedRowSet.value.has(row.id)) && !allDisplayedSelected.value)
const canExecute = computed(() => !!previewBatchId.value && selectedRunnableRows.value.length > 0)
const isCloudWorkflowRunning = computed(() => {
  if (sourceMode.value !== 'cloud') return false
  const status = cloudWorkflowTask.value?.status
  return status === 'pending' || status === 'running'
})
const canStartWorkflow = computed(() => {
  if (isCloudWorkflowRunning.value) return false
  if (previewing.value || executing.value) return false
  if (!hasPreview.value) return canPreview.value
  return !!previewBatchId.value && runnableRows.value.length > 0
})
const startWorkflowLabel = computed(() => {
  if (sourceMode.value === 'cloud') {
    return isCloudWorkflowRunning.value ? '任务执行中...' : '开始重命名（任务模式）'
  }
  return hasPreview.value ? '开始重命名' : '开始重命名（先生成预览）'
})
const actionHint = computed(() => {
  if (!canPreview.value && !hasPreview.value) {
    return sourceMode.value === 'local'
      ? '请先输入本地目录路径，再点击“生成预览”或“开始重命名”。'
      : '请先点击“浏览”选择云盘目录，再点击“生成预览”或“开始重命名”。'
  }
  if (sourceMode.value === 'cloud' && isCloudWorkflowRunning.value) {
    return `任务进行中：${cloudWorkflowTask.value?.message || '处理中'}`
  }
  if (!hasPreview.value) {
    return sourceMode.value === 'cloud'
      ? '云盘任务模式会在后台自动执行“预览 + 重命名”，可在下方任务卡片查看进度。'
      : '建议先生成预览核对结果，再执行重命名。也可直接点击“开始重命名”走一键流程。'
  }
  if (!selectedRows.value.length) {
    return '未勾选项目时，“开始重命名”会自动勾选可执行项并继续。'
  }
  return `已勾选 ${selectedRows.value.length} 项，可直接执行重命名。`
})
const cloudWorkflowStatusTag = computed<'info' | 'warning' | 'success' | 'danger'>(() => {
  const status = cloudWorkflowTask.value?.status
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'cancelled') return 'warning'
  return 'info'
})
const cloudWorkflowProgressStatus = computed<'success' | 'exception' | undefined>(() => {
  const status = cloudWorkflowTask.value?.status
  if (status === 'completed') return 'success'
  if (status === 'failed' || status === 'cancelled') return 'exception'
  return undefined
})
const canRollback = computed(() => {
  if (!previewBatchId.value) return false
  if (previewSourceMode.value === 'local') return true
  return lastCloudExecution.value.length > 0
})

const statusTagText = computed(() => {
  if (!serviceStatus.value) return '服务状态未知'
  if (!serviceStatus.value.available) return '服务不可用'
  if (!serviceStatus.value.ai_available) return 'AI 解析未配置'
  return '服务可用'
})

const statusTagType = computed(() => {
  if (!serviceStatus.value || !serviceStatus.value.available) return 'danger'
  if (!serviceStatus.value.ai_available) return 'warning'
  return 'success'
})

const validationDescription = computed(() => {
  if (!nameValidation.value) return ''
  const messages: string[] = []
  if (nameValidation.value.suggestions.length) messages.push(`建议：${nameValidation.value.suggestions.join('；')}`)
  if (nameValidation.value.warnings.length) messages.push(`警告：${nameValidation.value.warnings.join('；')}`)
  return messages.join(' | ') || '该文件名符合当前命名规范。'
})

function extractErrorMessage(error: unknown, fallback: string): string {
  const err = error as any
  return err?.response?.data?.detail || err?.message || fallback
}

function providerStateText(provider?: { configured: boolean; connected: boolean }): string {
  if (!provider) return '未知'
  if (provider.connected) return '已连接'
  if (provider.configured) return '连接失败'
  return '未配置'
}

function providerLabel(provider?: string): string {
  if (provider === 'kimi') return 'Kimi2.5'
  if (provider === 'deepseek') return 'DeepSeek'
  if (provider === 'glm') return 'GLM'
  return provider || 'Unknown'
}

function stopCloudWorkflowPolling() {
  if (cloudWorkflowPollTimer) {
    clearInterval(cloudWorkflowPollTimer)
    cloudWorkflowPollTimer = null
  }
}

function applyCloudWorkflowPreview(preview: NonNullable<QuarkWorkflowTaskStatus['preview']>) {
  if (previewBatchId.value === preview.batch_id && previewRows.value.length > 0) return
  previewBatchId.value = preview.batch_id
  previewSourceMode.value = 'cloud'
  previewAlgorithmUsed.value = preview.algorithm_used
  previewNamingUsed.value = preview.naming_standard
  previewTargetLabel.value = cloudFolderLabel.value
  previewRows.value = (preview.items || []).map(normalizeCloudItem)
  selectedRowIds.value = previewRows.value.map((item) => item.id)
  lastCloudExecution.value = []
}

function applyCloudWorkflowExecute(executeData: NonNullable<QuarkWorkflowTaskStatus['execute']>) {
  executeSummary.value = {
    batch_id: executeData.batch_id,
    total_items: executeData.total,
    success_items: executeData.success,
    failed_items: executeData.failed,
    skipped_items: executeData.skipped ?? Math.max(executeData.total - executeData.success - executeData.failed, 0)
  }

  const runnable = previewRows.value.filter((row) => (row.new_name || '').trim().length > 0)
  lastCloudExecution.value = runnable.map((row) => ({
    fid: row.id,
    original_name: row.original_name,
    executed_name: row.new_name
  }))

  const resultMap = new Map((executeData.results || []).map((item) => [item.fid, item]))
  previewRows.value = previewRows.value.map((row) => {
    const result = resultMap.get(row.id)
    if (!result) return row
    if (result.status === 'success') {
      return {
        ...row,
        original_name: row.new_name,
        status: 'success',
        needs_confirmation: false,
        confirmation_reason: undefined
      }
    }
    if (result.status === 'skipped') {
      return {
        ...row,
        status: 'skipped',
        confirmation_reason: '目标名称与原名称一致，已跳过'
      }
    }
    return {
      ...row,
      status: 'failed',
      confirmation_reason: result.error || '执行失败'
    }
  })
}

async function refreshCloudWorkflowTask(showError: boolean = false) {
  const taskId = cloudWorkflowTask.value?.task_id
  if (!taskId) return

  try {
    const latest = await getCloudRenameWorkflowTask(taskId)
    const previousStatus = cloudWorkflowTask.value?.status
    cloudWorkflowTask.value = latest

    if (latest.preview) applyCloudWorkflowPreview(latest.preview)
    if (latest.execute) applyCloudWorkflowExecute(latest.execute)

    if (latest.status === 'completed' || latest.status === 'failed' || latest.status === 'cancelled') {
      stopCloudWorkflowPolling()
      if (!cloudWorkflowNotified.value) {
        cloudWorkflowNotified.value = true
        if (latest.status === 'completed') {
          if (latest.execute) showResultDialog.value = true
          await loadBatchHistory()
          ElMessage.success(latest.message || '任务完成')
        } else if (latest.status === 'cancelled') {
          ElMessage.warning(latest.message || '任务已取消')
        } else {
          ElMessage.error(latest.error || latest.message || '任务执行失败')
        }
      }
    } else if (previousStatus !== latest.status) {
      ElMessage.info(latest.message || '任务状态已更新')
    }
  } catch (error) {
    if (showError) {
      ElMessage.error(extractErrorMessage(error, '获取任务状态失败'))
    }
  }
}

function startCloudWorkflowPolling() {
  stopCloudWorkflowPolling()
  cloudWorkflowPollTimer = setInterval(() => {
    void refreshCloudWorkflowTask(false)
  }, 2000)
}

async function cancelCloudWorkflow() {
  const taskId = cloudWorkflowTask.value?.task_id
  if (!taskId) return
  try {
    await cancelCloudRenameWorkflowTask(taskId)
    await refreshCloudWorkflowTask(false)
    ElMessage.warning('已请求取消任务')
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, '取消任务失败'))
  }
}

async function startCloudWorkflowTask() {
  if (!canPreview.value) {
    ElMessage.warning('请先选择云盘目录')
    return
  }
  if (isCloudWorkflowRunning.value) {
    ElMessage.warning('已有任务在执行，请等待完成或先取消')
    return
  }

  try {
    previewBatchId.value = ''
    previewRows.value = []
    selectedRowIds.value = []
    executeSummary.value = null
    showResultDialog.value = false
    lastCloudExecution.value = []

    const task = await createCloudRenameWorkflowTask({
      pdir_fid: cloudFolderFid.value,
      algorithm: selectedAlgorithm.value as any,
      naming_standard: selectedStandard.value as any,
      force_ai_parse: options.forceAiParse,
      auto_execute: true,
      options: {
        recursive: options.recursive,
        create_folders: options.createFolders,
        auto_confirm_high_confidence: options.autoConfirm,
        ai_confidence_threshold: options.aiThreshold,
        fast_mode: true,
        parse_concurrency: 3,
        ai_timeout_seconds: 6,
        tmdb_timeout_seconds: 6
      }
    })
    cloudWorkflowTask.value = task
    cloudWorkflowNotified.value = false
    startCloudWorkflowPolling()
    await refreshCloudWorkflowTask(false)
    ElMessage.success(`后台任务已创建：${task.task_id.slice(0, 8)}`)
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, '创建后台任务失败'))
  }
}

async function runAiConnectivityTest() {
  testingAiConnectivity.value = true
  try {
    const result = sourceMode.value === 'local'
      ? await testSmartRenameAIConnectivity()
      : await testCloudRenameAIConnectivity()

    aiConnectivityResult.value = result

    const summary = result.providers
      .map((item) => `${providerLabel(item.provider)}: ${providerStateText(item)}`)
      .join('，')
    if (result.all_connected) {
      ElMessage.success(`AI 连通性测试通过，${summary}`)
    } else {
      ElMessage.warning(`AI 连通性测试完成，${summary}`)
    }
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, 'AI 连通性测试失败'))
  } finally {
    testingAiConnectivity.value = false
  }
}

function loadRecentPaths() {
  try {
    const raw = localStorage.getItem(RECENT_PATH_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) recentPaths.value = parsed.filter((v) => typeof v === 'string').slice(0, 6)
  } catch {
    recentPaths.value = []
  }
}

function saveRecentPath(path: string) {
  const clean = path.trim()
  if (!clean) return
  const next = [clean, ...recentPaths.value.filter((p) => p !== clean)].slice(0, 6)
  recentPaths.value = next
  localStorage.setItem(RECENT_PATH_KEY, JSON.stringify(next))
}

function useLatestPath() {
  if (recentPaths.value.length) localPath.value = recentPaths.value[0] || ''
}

function handleCloudFolderSelect(fid: string, path: string) {
  cloudFolderFid.value = fid
  cloudFolderLabel.value = path
  sourceMode.value = 'cloud'
  ElMessage.success('已选择云盘目录')
}

function normalizeLocalItem(item: SmartRenameItem): ViewRenameItem {
  return {
    ...item,
    id: item.original_path,
    new_name: item.new_name || item.original_name || '',
    source_mode: 'local'
  }
}

function normalizeCloudItem(item: QuarkRenameItem): ViewRenameItem {
  return {
    id: item.fid,
    source_mode: 'cloud',
    original_path: item.fid,
    original_name: item.original_name,
    new_name: item.new_name || item.original_name,
    media_type: item.media_type || 'unknown',
    tmdb_id: item.tmdb_id,
    tmdb_title: item.tmdb_title,
    tmdb_year: item.tmdb_year,
    season: item.season,
    episode: item.episode,
    overall_confidence: item.overall_confidence || 0,
    status: item.status || (item.needs_confirmation ? 'needs_confirmation' : 'parsed'),
    needs_confirmation: !!item.needs_confirmation,
    confirmation_reason: item.confirmation_reason,
    used_algorithm: item.used_algorithm
  }
}
async function runPreview(): Promise<boolean> {
  if (!canPreview.value) {
    ElMessage.warning('请先选择有效的数据源路径')
    return false
  }

  previewing.value = true
  nameValidation.value = null
  try {
    if (sourceMode.value === 'local') {
      const targetPath = localPath.value.trim()
      const response = await previewSmartRename({
        target_path: targetPath,
        algorithm: selectedAlgorithm.value as any,
        naming_standard: selectedStandard.value as any,
        recursive: options.recursive,
        create_folders: options.createFolders,
        auto_confirm_high_confidence: options.autoConfirm,
        ai_confidence_threshold: options.aiThreshold,
        force_ai_parse: options.forceAiParse,
        naming_config: namingConfig
      })

      previewBatchId.value = response.batch_id
      previewSourceMode.value = 'local'
      previewAlgorithmUsed.value = response.algorithm_used
      previewNamingUsed.value = response.naming_standard
      previewTargetLabel.value = response.target_path
      previewRows.value = response.items.map(normalizeLocalItem)
      selectedRowIds.value = previewRows.value.map((item) => item.id)
      saveRecentPath(targetPath)
      lastCloudExecution.value = []
      ElMessage.success(`预览完成：共 ${response.total_items} 项`)
    } else {
      const response = await smartRenameCloudFiles({
        pdir_fid: cloudFolderFid.value,
        algorithm: selectedAlgorithm.value as any,
        naming_standard: selectedStandard.value as any,
        force_ai_parse: options.forceAiParse,
        options: {
          recursive: options.recursive,
          create_folders: options.createFolders,
          auto_confirm_high_confidence: options.autoConfirm,
          ai_confidence_threshold: options.aiThreshold,
          fast_mode: true,
          parse_concurrency: 3,
          ai_timeout_seconds: 6,
          tmdb_timeout_seconds: 6
        }
      })

      previewBatchId.value = response.batch_id
      previewSourceMode.value = 'cloud'
      previewAlgorithmUsed.value = response.algorithm_used
      previewNamingUsed.value = response.naming_standard
      previewTargetLabel.value = cloudFolderLabel.value
      previewRows.value = response.items.map(normalizeCloudItem)
      selectedRowIds.value = previewRows.value.map((item) => item.id)
      lastCloudExecution.value = []
      ElMessage.success(`云盘预览完成：共 ${response.total_items} 项`)
    }

    if (previewRows.value.length > 0) {
      await nextTick()
      workspaceRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    return true
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, '预览失败'))
    return false
  } finally {
    previewing.value = false
  }
}

function refreshPreview() {
  runPreview()
}

async function startRenameWorkflow() {
  if (sourceMode.value === 'cloud') {
    await startCloudWorkflowTask()
    return
  }

  if (!hasPreview.value) {
    const ok = await runPreview()
    if (!ok) return
    const fallbackIds = runnableRows.value.map((row) => row.id)
    if (!fallbackIds.length) {
      ElMessage.warning('预览完成，但当前没有可执行的重命名项目')
      return
    }
    selectedRowIds.value = fallbackIds
    ElMessage.info(`预览完成，已自动勾选 ${fallbackIds.length} 项并继续执行`)
    await nextTick()
  }

  if (!selectedRows.value.length) {
    const fallbackIds = runnableRows.value.map((row) => row.id)
    if (!fallbackIds.length) {
      ElMessage.warning('当前没有可执行的重命名项目')
      return
    }
    selectedRowIds.value = fallbackIds
    ElMessage.info(`已自动勾选 ${fallbackIds.length} 项可执行内容`)
    await nextTick()
  }

  await executeSelected()
}

function resetWorkspace() {
  stopCloudWorkflowPolling()
  previewBatchId.value = ''
  previewRows.value = []
  selectedRowIds.value = []
  aiConnectivityResult.value = null
  executeSummary.value = null
  showResultDialog.value = false
  activeHistoryBatchId.value = ''
  historyItems.value = []
  lastCloudExecution.value = []
  cloudWorkflowTask.value = null
  cloudWorkflowNotified.value = false
}

function exportPreview() {
  if (!previewRows.value.length) return
  const payload = {
    exported_at: new Date().toISOString(),
    batch_id: previewBatchId.value,
    source_mode: previewSourceMode.value,
    target: previewTargetLabel.value,
    algorithm: previewAlgorithmUsed.value,
    naming_standard: previewNamingUsed.value,
    options: { ...options },
    rows: previewRows.value
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `smart-rename-preview-${Date.now()}.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success('预览结果已导出')
}

function isRowSelected(id: string): boolean {
  return selectedRowSet.value.has(id)
}

function onRowCheck(id: string, checked: boolean) {
  const set = new Set(selectedRowIds.value)
  if (checked) set.add(id)
  else set.delete(id)
  selectedRowIds.value = Array.from(set)
}

function toggleSelectDisplayed(checked: boolean) {
  const displayIds = displayRows.value.map((row) => row.id)
  const set = new Set(selectedRowIds.value)
  if (checked) displayIds.forEach((id) => set.add(id))
  else displayIds.forEach((id) => set.delete(id))
  selectedRowIds.value = Array.from(set)
}

function clearSelection() {
  selectedRowIds.value = []
}

function removeFromSelection(rowId: string) {
  selectedRowIds.value = selectedRowIds.value.filter((id) => id !== rowId)
}

function selectPendingOnly() {
  selectedRowIds.value = previewRows.value.filter((row) => row.needs_confirmation).map((row) => row.id)
}

function markSelectedAsConfirmed() {
  if (!selectedRows.value.length) return
  const set = selectedRowSet.value
  previewRows.value = previewRows.value.map((row) => set.has(row.id)
    ? { ...row, needs_confirmation: false, confirmation_reason: undefined }
    : row)
  ElMessage.success(`已确认 ${selectedRows.value.length} 项`)
}

function editSingleSelected() {
  if (selectedRows.value.length !== 1) {
    ElMessage.warning('请选择且仅选择一个项目进行编辑')
    return
  }
  const target = selectedRows.value[0]
  if (target) openEditDialog(target)
}

function openEditDialog(row: ViewRenameItem) {
  Object.assign(editingItem, { ...row })
  nameValidation.value = null
  editDialogVisible.value = true
}

function saveEdit() {
  if (!editingItem.id) return
  const id = editingItem.id
  previewRows.value = previewRows.value.map((row) => row.id === id
    ? {
        ...row,
        new_name: (editingItem.new_name || '').trim() || row.new_name,
        tmdb_title: editingItem.tmdb_title || row.tmdb_title,
        media_type: editingItem.media_type || row.media_type,
        needs_confirmation: false
      }
    : row)
  editDialogVisible.value = false
  ElMessage.success('编辑已保存')
}
async function validateEditedName() {
  const value = (editingItem.new_name || '').trim()
  if (!value) {
    ElMessage.warning('请先输入新文件名')
    return
  }
  validatingName.value = true
  try {
    nameValidation.value = await validateFilename(value)
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, '命名校验失败'))
  } finally {
    validatingName.value = false
  }
}

async function validateSelectedName() {
  if (selectedRows.value.length !== 1) {
    ElMessage.warning('命名校验仅支持单项，请只选择一个项目')
    return
  }
  const target = selectedRows.value[0]
  if (!target) return
  openEditDialog(target)
  await validateEditedName()
}

async function executeSelected() {
  if (!previewBatchId.value) {
    ElMessage.warning('请先生成预览批次')
    return
  }

  if (!selectedRows.value.length && runnableRows.value.length) {
    selectedRowIds.value = runnableRows.value.map((row) => row.id)
    await nextTick()
    ElMessage.info(`未勾选项目，已自动选择 ${selectedRowIds.value.length} 项`)
  }

  const selected = selectedRows.value
  if (!selected.length) {
    ElMessage.warning('请先勾选待执行项目')
    return
  }

  const runnable = selected.filter((row) => (row.new_name || '').trim().length > 0)
  if (!runnable.length) {
    ElMessage.warning('勾选项中没有可执行的新文件名')
    return
  }

  const actionText = previewSourceMode.value === 'local' ? '本地重命名' : '云盘重命名'
  try {
    await ElMessageBox.confirm(`即将执行 ${runnable.length} 项 ${actionText}，是否继续？`, '执行确认', {
      type: 'warning',
      confirmButtonText: '继续执行',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  executing.value = true
  try {
    if (previewSourceMode.value === 'local') {
      const operations = runnable.map((row) => ({ original_path: row.original_path, new_name: row.new_name.trim() }))
      const response = await executeSmartRename({ batch_id: previewBatchId.value, operations })
      executeSummary.value = response
      showResultDialog.value = true

      const set = new Set(runnable.map((row) => row.id))
      previewRows.value = previewRows.value.map((row) => set.has(row.id) ? { ...row, status: 'success', needs_confirmation: false } : row)
    } else {
      const operations = runnable.map((row) => ({ fid: row.id, new_name: row.new_name.trim() }))
      const response = await executeCloudRename({ batch_id: previewBatchId.value, operations })
      executeSummary.value = {
        batch_id: previewBatchId.value,
        total_items: response.total,
        success_items: response.success,
        failed_items: response.failed,
        skipped_items: response.skipped ?? Math.max(response.total - response.success - response.failed, 0)
      }
      showResultDialog.value = true

      lastCloudExecution.value = runnable.map((row) => ({
        fid: row.id,
        original_name: row.original_name,
        executed_name: row.new_name
      }))

      const resultMap = new Map(response.results.map((item) => [item.fid, item]))
      previewRows.value = previewRows.value.map((row) => {
        const result = resultMap.get(row.id)
        if (!result) return row
        if (result.status === 'success') {
          return {
            ...row,
            original_name: row.new_name,
            status: 'success',
            needs_confirmation: false,
            confirmation_reason: undefined
          }
        }
        if (result.status === 'skipped') {
          return {
            ...row,
            status: 'skipped',
            confirmation_reason: '目标名称与原名称一致，已跳过'
          }
        }
        return {
          ...row,
          status: 'failed',
          confirmation_reason: result.error || '执行失败'
        }
      })
    }

    await loadBatchHistory()
    if (previewSourceMode.value === 'cloud') {
      ElMessage.success('执行完成：云盘模式仅重命名原文件，不会新增文件')
    } else {
      ElMessage.success('执行完成')
    }
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, '执行失败'))
  } finally {
    executing.value = false
  }
}

async function rollbackLatest() {
  if (!canRollback.value) {
    ElMessage.warning('当前没有可回滚的数据')
    return
  }

  rollingBack.value = true
  try {
    if (previewSourceMode.value === 'local') {
      const response = await rollbackSmartRename(previewBatchId.value)
      executeSummary.value = response
      showResultDialog.value = true
      previewRows.value = previewRows.value.map((row) => ({ ...row, status: 'rolled_back' }))
    } else {
      const operations = lastCloudExecution.value.map((item) => ({ fid: item.fid, new_name: item.original_name }))
      const response = await executeCloudRename({
        batch_id: `${previewBatchId.value}_rollback_${Date.now()}`,
        operations
      })

      executeSummary.value = {
        batch_id: previewBatchId.value,
        total_items: response.total,
        success_items: response.success,
        failed_items: response.failed,
        skipped_items: Math.max(response.total - response.success - response.failed, 0)
      }
      showResultDialog.value = true

      const successSet = new Set(response.results.filter((item) => item.status === 'success').map((item) => item.fid))
      previewRows.value = previewRows.value.map((row) => {
        const snapshot = lastCloudExecution.value.find((item) => item.fid === row.id)
        if (!snapshot || !successSet.has(row.id)) return row
        return {
          ...row,
          original_name: snapshot.original_name,
          new_name: snapshot.original_name,
          status: 'rolled_back',
          needs_confirmation: false,
          confirmation_reason: undefined
        }
      })

      lastCloudExecution.value = lastCloudExecution.value.filter((item) => !successSet.has(item.fid))
    }

    await loadBatchHistory()
    ElMessage.success('回滚完成')
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, '回滚失败'))
  } finally {
    rollingBack.value = false
  }
}
function statusText(row: ViewRenameItem): string {
  if (row.status === 'success') return '执行成功'
  if (row.status === 'skipped') return '已跳过'
  if (row.status === 'failed') return '执行失败'
  if (row.status === 'rolled_back') return '已回滚'
  if (row.needs_confirmation) return '待确认'
  if (row.tmdb_id) return '已匹配'
  return '已解析'
}

function statusType(row: ViewRenameItem): 'success' | 'warning' | 'danger' | 'info' {
  if (row.status === 'success') return 'success'
  if (row.status === 'skipped') return 'info'
  if (row.status === 'failed') return 'danger'
  if (row.needs_confirmation) return 'warning'
  return 'info'
}

function confidenceStatus(value: number): '' | 'success' | 'warning' | 'exception' {
  if (value >= 0.9) return 'success'
  if (value >= 0.6) return 'warning'
  return 'exception'
}

function getMediaTypeText(type: string): string {
  const map: Record<string, string> = { movie: '电影', tv: '剧集', anime: '动漫', unknown: '未知' }
  return map[type] || type
}

async function loadBatchHistory() {
  historyLoading.value = true
  try {
    batchHistory.value = await getRenameBatches(0, 50)
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, '加载批次记录失败'))
  } finally {
    historyLoading.value = false
  }
}

async function onHistoryBatchClick(row: any) {
  if (!row?.batch_id) return
  activeHistoryBatchId.value = row.batch_id
  historyItemsLoading.value = true
  try {
    historyItems.value = await getBatchItems(row.batch_id, undefined, 0, 200)
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, '加载批次明细失败'))
  } finally {
    historyItemsLoading.value = false
  }
}

async function openHistory() {
  showHistoryDrawer.value = true
  if (!batchHistory.value.length) await loadBatchHistory()
}

async function loadBootstrap() {
  try {
    const [algo, standards, status] = await Promise.all([getAlgorithms(), getNamingStandards(), getSmartRenameStatus()])
    algorithms.value = algo
    namingStandards.value = standards
    serviceStatus.value = status
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, '初始化配置加载失败'))
  }
}

watch(sourceMode, (mode) => {
  aiConnectivityResult.value = null
  if (mode === 'local') {
    cloudFolderFid.value = ''
    cloudFolderLabel.value = ''
  } else {
    localPath.value = ''
  }
})

watch(previewRows, () => {
  const idSet = new Set(previewRows.value.map((item) => item.id))
  selectedRowIds.value = selectedRowIds.value.filter((id) => idSet.has(id))
})

onMounted(async () => {
  loadRecentPaths()
  await Promise.all([loadBootstrap(), loadBatchHistory()])
})

onBeforeUnmount(() => {
  stopCloudWorkflowPolling()
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Noto+Sans+SC:wght@400;500;700&display=swap');

.smart-rename-page {
  --ink: #173042;
  --muted: #60788a;
  --teal: #0a8d76;
  --teal-soft: #ddf5ef;
  --sand: #fff7ea;
  --shadow: 0 14px 44px rgba(24, 55, 78, 0.12);

  min-height: 100%;
  padding: 24px;
  position: relative;
  overflow: hidden;
  color: var(--ink);
  font-family: 'Space Grotesk', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background:
    radial-gradient(circle at 10% 4%, rgba(10, 141, 118, 0.14) 0, transparent 40%),
    radial-gradient(circle at 88% 0%, rgba(230, 139, 31, 0.14) 0, transparent 36%),
    linear-gradient(180deg, #f6fbfa 0%, #fffefa 58%, #f4faf8 100%);
}

.ambient {
  position: absolute;
  border-radius: 999px;
  filter: blur(32px);
  pointer-events: none;
  animation: drift 10s ease-in-out infinite alternate;
}

.ambient-a {
  width: 200px;
  height: 200px;
  background: rgba(10, 141, 118, 0.2);
  top: -26px;
  right: -30px;
}

.ambient-b {
  width: 170px;
  height: 170px;
  background: rgba(230, 139, 31, 0.16);
  left: -28px;
  top: 220px;
  animation-delay: 1.2s;
}

.hero-card,
.control-grid,
.action-strip,
.workspace,
.empty-block {
  position: relative;
  z-index: 1;
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px;
  border: 1px solid rgba(10, 141, 118, 0.16);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow);
}
.kicker {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--teal);
  font-weight: 700;
}

.hero-card h1 {
  margin: 4px 0 10px;
  font-size: 31px;
  line-height: 1.2;
}

.subtitle {
  margin: 0;
  max-width: 760px;
  font-size: 14px;
  color: var(--muted);
}

.hero-actions {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.control-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.panel {
  padding: 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.93);
  border: 1px solid rgba(96, 120, 138, 0.2);
  box-shadow: 0 8px 26px rgba(23, 48, 66, 0.08);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-head h2 {
  margin: 0;
  font-size: 17px;
}

.mode-switch {
  margin-bottom: 12px;
}

.path-input {
  margin-bottom: 8px;
}

.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.field {
  display: grid;
  gap: 6px;
}

.field label,
.minor {
  font-size: 12px;
  color: var(--muted);
}

.recent-wrap {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.recent-tag {
  cursor: pointer;
}

.algo-box {
  margin-top: 10px;
  padding: 10px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--teal-soft), #edf8f3);
}

.algo-title {
  margin: 0 0 4px;
  font-weight: 700;
}

.tag-line {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.opt-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.threshold {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 120px 1fr 52px;
  align-items: center;
  gap: 10px;
}

.action-strip {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(230, 139, 31, 0.22);
  background: linear-gradient(135deg, var(--sand), #fffdf8);
}
.action-hint {
  margin: 8px 4px 0;
  color: var(--muted);
  font-size: 12px;
}

.workflow-task-card {
  margin-top: 10px;
  border: 1px solid rgba(10, 141, 118, 0.24);
  border-radius: 14px;
  background: linear-gradient(135deg, #f1fbf8, #fff);
  box-shadow: 0 8px 26px rgba(12, 56, 42, 0.08);
  padding: 14px 16px;
}

.workflow-task-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.workflow-task-actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}

.ai-connectivity-strip {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(10, 141, 118, 0.2);
  background: rgba(255, 255, 255, 0.9);
}

.ai-connectivity-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.ai-connectivity-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(2, minmax(180px, 1fr));
  gap: 8px;
}

.ai-connectivity-item {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(96, 120, 138, 0.18);
  background: #f8fbfa;
  display: grid;
  gap: 6px;
}

.workspace {
  margin-top: 14px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(10, 141, 118, 0.2);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: var(--shadow);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 8px;
}

.summary {
  padding: 10px;
  border-radius: 12px;
  background: #f5faf8;
  border: 1px solid rgba(96, 120, 138, 0.16);
  display: grid;
  gap: 4px;
}

.summary span {
  font-size: 12px;
  color: var(--muted);
}

.summary strong {
  font-size: 17px;
}

.filter-row {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  gap: 8px;
}

.batch-tools {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.result-table {
  margin-top: 10px;
}

.name-cell {
  display: grid;
  gap: 2px;
}

.strong {
  margin: 0;
  font-weight: 600;
}

.ops-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.1;
}

.execute-bar {
  margin-top: 12px;
  padding: 10px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(10, 141, 118, 0.1), rgba(230, 139, 31, 0.1));
  border: 1px solid rgba(96, 120, 138, 0.24);
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.execute-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.execute-actions {
  display: flex;
  gap: 8px;
}
.result-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.result-card {
  padding: 10px;
  border-radius: 12px;
  display: grid;
  gap: 4px;
}

.result-card span {
  font-size: 12px;
  color: #4f6878;
}

.result-card strong {
  font-size: 22px;
}

.result-card.success { background: #e5f7ee; }
.result-card.fail { background: #fde9e7; }
.result-card.skip { background: #fff2df; }
.result-card.total { background: #eaf3fb; }

.help-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
  color: #24475f;
}

.history-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.history-panel {
  border: 1px solid rgba(96, 120, 138, 0.18);
  border-radius: 12px;
  padding: 8px;
  background: #fff;
}

.history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.history-head h3 {
  margin: 0;
  font-size: 14px;
}

.empty-block {
  margin-top: 20px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px dashed rgba(96, 120, 138, 0.3);
}

@keyframes drift {
  from { transform: translate(0, 0); }
  to { transform: translate(-6px, 10px); }
}

@media (max-width: 1200px) {
  .control-grid,
  .row2,
  .opt-grid,
  .filter-row,
  .history-layout,
  .ai-connectivity-grid {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    grid-template-columns: repeat(3, minmax(120px, 1fr));
  }
}

@media (max-width: 900px) {
  .hero-card,
  .execute-bar {
    flex-direction: column;
  }

  .hero-actions,
  .execute-actions {
    flex-wrap: wrap;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }
}

@media (max-width: 640px) {
  .smart-rename-page {
    padding: 14px;
  }

  .summary-grid,
  .result-grid {
    grid-template-columns: 1fr;
  }
}
</style>
