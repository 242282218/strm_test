<template>
  <div class="smart-rename-page">
    <header class="hero-card">
      <div>
        <p class="kicker">SMART RENAME</p>
        <h1>智能重命名</h1>
        <p class="subtitle">输入本地目录，先生成预览，再执行重命名。页面只保留日常使用所需的核心流程。</p>
      </div>
    </header>

    <section class="panel">
      <div class="panel-head">
        <h2>本地目录</h2>
      </div>

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
        <el-tag
          v-for="path in recentPaths"
          :key="path"
          size="small"
          class="recent-tag"
          @click="localPath = path"
        >
          {{ path }}
        </el-tag>
      </div>

      <div class="config-grid">
        <div class="field">
          <label>解析算法</label>
          <el-select v-model="selectedAlgorithm">
            <el-option
              v-for="algo in algorithms"
              :key="algo.algorithm"
              :label="algo.name"
              :value="algo.algorithm"
            />
          </el-select>
        </div>

        <div class="field">
          <label>命名标准</label>
          <el-select v-model="selectedStandard">
            <el-option
              v-for="standard in namingStandards"
              :key="standard.standard"
              :label="standard.name"
              :value="standard.standard"
            />
          </el-select>
        </div>
      </div>

      <div class="option-row">
        <el-checkbox v-model="recursive">递归扫描</el-checkbox>
      </div>

      <div class="action-strip">
        <el-button type="primary" :loading="previewing" :disabled="!canPreview" @click="runPreview">
          生成预览
        </el-button>
        <el-button type="success" :loading="executing" :disabled="!canExecute" @click="executeSelected">
          执行重命名
        </el-button>
        <el-button :disabled="!hasPreview" @click="resetWorkspace">重置</el-button>
      </div>

      <p class="action-hint">{{ actionHint }}</p>
    </section>

    <section v-if="hasPreview" class="workspace">
      <div class="summary-grid">
        <div class="summary-card">
          <span>批次 ID</span>
          <strong>{{ previewBatchId }}</strong>
        </div>
        <div class="summary-card">
          <span>总项目</span>
          <strong>{{ totalItems }}</strong>
        </div>
        <div class="summary-card">
          <span>待确认</span>
          <strong>{{ pendingItems }}</strong>
        </div>
        <div class="summary-card">
          <span>匹配成功</span>
          <strong>{{ matchedItems }}</strong>
        </div>
        <div class="summary-card">
          <span>平均置信度</span>
          <strong>{{ Math.round(averageConfidence * 100) }}%</strong>
        </div>
      </div>

      <el-table :data="previewRows" row-key="id" class="result-table" empty-text="暂无预览结果">
        <el-table-column width="56">
          <template #header>
            <el-checkbox
              :model-value="allRowsSelected"
              :indeterminate="partiallySelected"
              @change="toggleSelectAll"
            />
          </template>
          <template #default="{ row }">
            <el-checkbox :model-value="isRowSelected(row.id)" @change="onRowCheck(row.id, $event)" />
          </template>
        </el-table-column>

        <el-table-column label="原文件" min-width="230">
          <template #default="{ row }">
            <div class="cell-stack">
              <strong>{{ row.original_name }}</strong>
              <span class="minor">{{ row.original_path }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="建议名称" min-width="240">
          <template #default="{ row }">
            <div class="cell-stack">
              <strong>{{ row.new_name }}</strong>
              <span class="minor">{{ getMediaTypeText(row.media_type) }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="匹配" min-width="160">
          <template #default="{ row }">
            <div class="cell-stack">
              <span>{{ row.tmdb_title || '未匹配 TMDB' }}</span>
              <el-tag v-if="row.tmdb_id" size="small" effect="plain">TMDB {{ row.tmdb_id }}</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="置信度" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round((row.overall_confidence || 0) * 100)"
              :status="confidenceStatus(row.overall_confidence || 0)"
              :stroke-width="8"
            />
          </template>
        </el-table-column>

        <el-table-column label="状态" width="140">
          <template #default="{ row }">
            <el-tag :type="statusType(row)" round>{{ statusText(row) }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEditDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="selection-summary">
        <span>已勾选 {{ selectedRows.length }} / {{ totalItems }} 项</span>
        <span>算法：{{ previewAlgorithmUsed }}</span>
        <span>标准：{{ previewNamingUsed }}</span>
      </div>
    </section>

    <el-empty v-else class="empty-state" description="输入本地目录后点击“生成预览”开始重命名。" />

    <el-dialog v-model="editDialogVisible" title="编辑建议名称" width="560px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="原文件名">
          <el-input :model-value="editingItem.original_name" disabled />
        </el-form-item>
        <el-form-item label="新文件名">
          <el-input v-model="editingItem.new_name" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showResultDialog" title="执行结果" width="460px" destroy-on-close>
      <div v-if="executeSummary" class="result-grid">
        <div class="result-card">
          <span>成功</span>
          <strong>{{ executeSummary.success_items }}</strong>
        </div>
        <div class="result-card">
          <span>失败</span>
          <strong>{{ executeSummary.failed_items }}</strong>
        </div>
        <div class="result-card">
          <span>跳过</span>
          <strong>{{ executeSummary.skipped_items }}</strong>
        </div>
        <div class="result-card">
          <span>总计</span>
          <strong>{{ executeSummary.total_items }}</strong>
        </div>
      </div>

      <template #footer>
        <el-button type="primary" @click="showResultDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  executeSmartRename,
  getAlgorithms,
  getNamingStandards,
  previewSmartRename,
  type AlgorithmInfo,
  type NamingStandardInfo,
  type SmartRenameAlgorithm,
  type SmartRenameExecuteResponse,
  type SmartRenameNamingStandard,
} from '../api/smartRename'
import {
  RECENT_PATH_KEY,
  confidenceStatus,
  getMediaTypeText,
  mergeRecentPaths,
  normalizeLocalItem,
  parseRecentPaths,
  statusText,
  statusType,
  type ViewRenameItem,
} from '../smart-rename-view-model'
import { getErrorMessage } from '@/utils/error-message'

defineOptions({
  name: 'SmartRenameView',
})

const algorithms = ref<AlgorithmInfo[]>([])
const namingStandards = ref<NamingStandardInfo[]>([])
const selectedAlgorithm = ref<SmartRenameAlgorithm>('ai_enhanced')
const selectedStandard = ref<SmartRenameNamingStandard>('emby')
const recursive = ref(true)

const localPath = ref('')
const recentPaths = ref<string[]>([])

const previewing = ref(false)
const executing = ref(false)
const previewBatchId = ref('')
const previewAlgorithmUsed = ref('')
const previewNamingUsed = ref('')
const previewRows = ref<ViewRenameItem[]>([])
const selectedRowIds = ref<string[]>([])

const editDialogVisible = ref(false)
const editingItem = reactive<Partial<ViewRenameItem>>({})
const executeSummary = ref<SmartRenameExecuteResponse | null>(null)
const showResultDialog = ref(false)

const hasPreview = computed(() => previewRows.value.length > 0)
const canPreview = computed(() => localPath.value.trim().length > 0 && !previewing.value)
const totalItems = computed(() => previewRows.value.length)
const pendingItems = computed(() => previewRows.value.filter((row) => row.needs_confirmation).length)
const matchedItems = computed(() => previewRows.value.filter((row) => !!row.tmdb_id).length)
const averageConfidence = computed(() => {
  if (!previewRows.value.length) return 0
  return previewRows.value.reduce((sum, row) => sum + (row.overall_confidence || 0), 0) / previewRows.value.length
})
const selectedIdSet = computed(() => new Set(selectedRowIds.value))
const selectedRows = computed(() => previewRows.value.filter((row) => selectedIdSet.value.has(row.id)))
const runnableRows = computed(() => previewRows.value.filter((row) => (row.new_name || '').trim().length > 0))
const allRowsSelected = computed(() => previewRows.value.length > 0 && previewRows.value.every((row) => selectedIdSet.value.has(row.id)))
const partiallySelected = computed(() => {
  return previewRows.value.some((row) => selectedIdSet.value.has(row.id)) && !allRowsSelected.value
})
const canExecute = computed(() => {
  return hasPreview.value && !!previewBatchId.value && !executing.value
})

const actionHint = computed(() => {
  if (!hasPreview.value) {
    return localPath.value.trim()
      ? '点击“生成预览”查看建议名称，再执行重命名。'
      : '请先输入本地目录路径。'
  }
  if (!selectedRows.value.length) {
    return '执行时会自动选择所有可执行项。'
  }
  return `已勾选 ${selectedRows.value.length} 项，可直接执行重命名。`
})

function loadRecentPaths() {
  recentPaths.value = parseRecentPaths(localStorage.getItem(RECENT_PATH_KEY))
}

function saveRecentPath(path: string) {
  const next = mergeRecentPaths(path, recentPaths.value)
  recentPaths.value = next
  localStorage.setItem(RECENT_PATH_KEY, JSON.stringify(next))
}

function useLatestPath() {
  if (recentPaths.value.length) {
    localPath.value = recentPaths.value[0] || ''
  }
}

function resetWorkspace() {
  previewBatchId.value = ''
  previewAlgorithmUsed.value = ''
  previewNamingUsed.value = ''
  previewRows.value = []
  selectedRowIds.value = []
  executeSummary.value = null
  showResultDialog.value = false
  editDialogVisible.value = false
}

function syncSelections() {
  selectedRowIds.value = runnableRows.value.map((row) => row.id)
}

async function loadBootstrap() {
  try {
    const [algo, standards] = await Promise.all([getAlgorithms(), getNamingStandards()])
    algorithms.value = algo
    namingStandards.value = standards

    if (!algo.some((item) => item.algorithm === selectedAlgorithm.value) && algo[0]) {
      selectedAlgorithm.value = algo[0].algorithm
    }
    if (!standards.some((item) => item.standard === selectedStandard.value) && standards[0]) {
      selectedStandard.value = standards[0].standard
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '初始化配置加载失败'))
  }
}

async function runPreview(): Promise<boolean> {
  const targetPath = localPath.value.trim()
  if (!targetPath) {
    ElMessage.warning('请先输入本地目录路径')
    return false
  }

  previewing.value = true
  try {
    const response = await previewSmartRename({
      target_path: targetPath,
      algorithm: selectedAlgorithm.value,
      naming_standard: selectedStandard.value,
      recursive: recursive.value,
    })

    previewBatchId.value = response.batch_id
    previewAlgorithmUsed.value = response.algorithm_used
    previewNamingUsed.value = response.naming_standard
    previewRows.value = response.items.map(normalizeLocalItem)
    syncSelections()
    saveRecentPath(targetPath)
    ElMessage.success(`预览完成：共 ${response.total_items} 项`)
    return true
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '预览失败'))
    return false
  } finally {
    previewing.value = false
  }
}

function isRowSelected(id: string): boolean {
  return selectedIdSet.value.has(id)
}

function onRowCheck(id: string, checked: boolean) {
  const next = new Set(selectedRowIds.value)
  if (checked) next.add(id)
  else next.delete(id)
  selectedRowIds.value = Array.from(next)
}

function toggleSelectAll(checked: boolean) {
  selectedRowIds.value = checked ? previewRows.value.map((row) => row.id) : []
}

function openEditDialog(row: ViewRenameItem) {
  Object.assign(editingItem, { ...row })
  editDialogVisible.value = true
}

function saveEdit() {
  if (!editingItem.id) return

  previewRows.value = previewRows.value.map((row) => {
    if (row.id !== editingItem.id) return row
    return {
      ...row,
      new_name: (editingItem.new_name || '').trim() || row.new_name,
      needs_confirmation: false,
      confirmation_reason: undefined,
    }
  })

  editDialogVisible.value = false
  syncSelections()
  ElMessage.success('编辑已保存')
}

async function executeSelected() {
  if (!previewBatchId.value) {
    ElMessage.warning('请先生成预览批次')
    return
  }

  if (!selectedRows.value.length) {
    syncSelections()
  }

  const runnable = previewRows.value
    .filter((row) => selectedIdSet.value.has(row.id))
    .filter((row) => (row.new_name || '').trim().length > 0)

  if (!runnable.length) {
    ElMessage.warning('当前没有可执行的重命名项目')
    return
  }

  try {
    await ElMessageBox.confirm(`即将执行 ${runnable.length} 项本地重命名，是否继续？`, '执行确认', {
      type: 'warning',
      confirmButtonText: '继续执行',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  executing.value = true
  try {
    const response = await executeSmartRename({
      batch_id: previewBatchId.value,
      operations: runnable.map((row) => ({
        original_path: row.original_path,
        new_name: row.new_name.trim(),
      })),
    })

    executeSummary.value = response
    showResultDialog.value = true
    const executedIds = new Set(runnable.map((row) => row.id))
    previewRows.value = previewRows.value.map((row) => {
      if (!executedIds.has(row.id)) return row
      return { ...row, status: 'success', needs_confirmation: false }
    })
    ElMessage.success('执行完成')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '执行失败'))
  } finally {
    executing.value = false
  }
}

onMounted(async () => {
  loadRecentPaths()
  await loadBootstrap()
})
</script>

<style scoped>
.smart-rename-page {
  min-height: 100%;
  padding: 24px;
  color: #173042;
  background: linear-gradient(180deg, #f6fbfa 0%, #fffdfa 100%);
}

.hero-card,
.panel,
.workspace,
.empty-state {
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(23, 48, 66, 0.08);
  box-shadow: 0 12px 30px rgba(23, 48, 66, 0.08);
}

.hero-card {
  padding: 22px 24px;
}

.kicker {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.14em;
  color: #0a8d76;
  font-weight: 700;
}

.hero-card h1 {
  margin: 6px 0 8px;
  font-size: 30px;
  line-height: 1.2;
}

.subtitle {
  margin: 0;
  max-width: 700px;
  color: #60788a;
  font-size: 14px;
}

.panel,
.workspace {
  margin-top: 16px;
  padding: 18px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-head h2 {
  margin: 0;
  font-size: 18px;
}

.path-input {
  margin-bottom: 10px;
}

.recent-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.recent-tag {
  cursor: pointer;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.field {
  display: grid;
  gap: 6px;
}

.field label,
.minor,
.action-hint,
.selection-summary span,
.summary-card span {
  color: #60788a;
  font-size: 12px;
}

.option-row {
  margin-top: 12px;
}

.action-strip {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 18px;
}

.action-hint {
  margin: 12px 0 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.summary-card {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 14px;
  background: #f6fbfa;
  border: 1px solid rgba(10, 141, 118, 0.08);
}

.summary-card strong {
  font-size: 18px;
}

.cell-stack {
  display: grid;
  gap: 4px;
}

.selection-summary {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.empty-state {
  margin-top: 16px;
  padding: 28px 0;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.result-card {
  display: grid;
  gap: 8px;
  padding: 14px;
  border-radius: 14px;
  background: #f6fbfa;
  text-align: center;
}

.result-card strong {
  font-size: 22px;
}

@media (max-width: 960px) {
  .smart-rename-page {
    padding: 16px;
  }

  .config-grid,
  .summary-grid,
  .result-grid {
    grid-template-columns: 1fr;
  }
}
</style>
