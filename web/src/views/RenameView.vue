<template>
  <div class="rename-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">
          <span class="gradient-text">智能重命名</span>
        </h1>
        <p class="page-subtitle">基于TMDB和AI智能识别，自动整理媒体文件命名</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" size="large" @click="showSettings = true">
          <el-icon><Setting /></el-icon>
          配置规则
        </el-button>
      </div>
    </div>

    <!-- Configuration Section -->
    <div class="configuration-section">
      <!-- Algorithm Selection Card -->
      <div class="config-card glass-card">
        <div class="card-header">
          <div class="header-title">
            <el-icon class="header-icon"><Cpu /></el-icon>
            <h3>重命名算法</h3>
          </div>
          <el-tooltip content="选择适合您需求的解析算法" placement="top">
            <el-icon class="help-icon"><InfoFilled /></el-icon>
          </el-tooltip>
        </div>
        
        <div class="config-content">
          <el-radio-group v-model="selectedAlgorithm" size="large" class="algorithm-group">
            <el-radio-button 
              v-for="algo in algorithms" 
              :key="algo.value" 
              :value="algo.value"
            >
              <div class="algorithm-option">
                <div class="algo-header">
                  <span class="algo-name">{{ algo.label }}</span>
                  <el-tag v-if="algo.recommended" type="success" size="small" class="recommend-tag">推荐</el-tag>
                </div>
                <div class="algo-desc">{{ algo.description }}</div>
              </div>
            </el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <!-- Naming Standard Card -->
      <div class="config-card glass-card">
        <div class="card-header">
          <div class="header-title">
            <el-icon class="header-icon"><Document /></el-icon>
            <h3>命名标准</h3>
          </div>
          <el-tooltip content="选择媒体服务器兼容的命名规范" placement="top">
            <el-icon class="help-icon"><InfoFilled /></el-icon>
          </el-tooltip>
        </div>
        
        <div class="config-content">
          <el-radio-group v-model="selectedStandard" size="large" class="standard-group">
            <el-radio-button 
              v-for="std in namingStandards" 
              :key="std.value" 
              :value="std.value"
            >
              <div class="standard-option">
                <span class="std-name">{{ std.label }}</span>
                <span class="std-desc">{{ std.description }}</span>
              </div>
            </el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="rename-container">
      <!-- Step 1: Select Path -->
      <div class="step-section glass-card" :class="{ 'active': currentStep >= 1 }">
        <div class="step-header">
          <div class="step-number">1</div>
          <div class="step-info">
            <h3>选择文件夹</h3>
            <p>选择需要整理的媒体文件夹</p>
          </div>
          <el-tag v-if="selectedPath" type="success" effect="dark">
            <el-icon><Check /></el-icon>
            已选择
          </el-tag>
        </div>
        
        <div class="step-content" v-show="currentStep >= 1">
          <div class="path-selector">
            <el-input
              v-model="selectedPath"
              placeholder="点击选择文件夹..."
              readonly
              size="large"
              class="path-input"
            >
              <template #prefix>
                <el-icon><Folder /></el-icon>
              </template>
              <template #append>
                <el-button @click="openPathSelector">
                  <el-icon><FolderOpened /></el-icon>
                  浏览
                </el-button>
              </template>
            </el-input>
          </div>
          
          <div class="path-options">
            <el-checkbox v-model="options.recursive">
              包含子文件夹
            </el-checkbox>
            <el-checkbox v-model="options.autoConfirm">
              自动确认高置信度匹配 (>90%)
            </el-checkbox>
          </div>
          
          <div class="step-actions">
            <el-button
              type="primary"
              size="large"
              :disabled="!selectedPath"
              :loading="analyzing"
              @click="startAnalysis"
            >
              <el-icon><VideoPlay /></el-icon>
              开始分析
            </el-button>
          </div>
        </div>
      </div>

      <!-- Step 2: Preview Results -->
      <div class="step-section glass-card" :class="{ 'active': currentStep >= 2, 'disabled': currentStep < 2 }">
        <div class="step-header">
          <div class="step-number">2</div>
          <div class="step-info">
            <h3>预览重命名</h3>
            <p>查看AI识别的媒体信息并确认</p>
          </div>
          <div class="step-stats" v-if="previewData">
            <el-tag type="info">共 {{ previewData.total_tasks }} 个文件</el-tag>
            <el-tag type="warning" v-if="previewData.needs_confirmation > 0">
              {{ previewData.needs_confirmation }} 个待确认
            </el-tag>
          </div>
        </div>
        
        <div class="step-content" v-show="currentStep >= 2 && previewData">
          <!-- Progress Log -->
          <div class="progress-log" v-if="analysisProgress.length > 0">
            <div
              v-for="(log, index) in analysisProgress"
              :key="index"
              class="log-item"
              :class="{ 'latest': index === analysisProgress.length - 1 }"
            >
              <el-icon><InfoFilled /></el-icon>
              <span>{{ log.message }}</span>
              <el-progress
                v-if="log.total > 0"
                :percentage="Math.round((log.current / log.total) * 100)"
                :stroke-width="4"
                class="log-progress"
              />
            </div>
          </div>

          <!-- Task List -->
          <div class="task-list" v-if="previewData && previewData.tasks.length > 0">
            <div class="list-header">
              <el-checkbox v-model="selectAll" @change="handleSelectAll">
                全选
              </el-checkbox>
              <div class="header-filters">
                <el-radio-group v-model="filterType" size="small">
                  <el-radio-button value="all">全部</el-radio-button>
                  <el-radio-button value="pending">待确认</el-radio-button>
                  <el-radio-button value="confirmed">已确认</el-radio-button>
                </el-radio-group>
              </div>
            </div>

            <div class="task-items">
              <div
                v-for="task in filteredTasks"
                :key="task.source_path"
                class="task-item"
                :class="{
                  'needs-confirmation': task.needs_confirmation,
                  'selected': selectedTasks.includes(task.source_path)
                }"
              >
                <el-checkbox
                  v-model="selectedTasks"
                  :label="task.source_path"
                  class="task-checkbox"
                >
                  {{ '' }}
                </el-checkbox>

                <div class="task-preview">
                  <div class="file-info">
                    <div class="original-name">
                      <el-icon><Document /></el-icon>
                      <span class="name-text" :title="task.source_path">
                        {{ getFileName(task.source_path) }}
                      </span>
                    </div>
                    <el-icon class="arrow-icon"><ArrowRight /></el-icon>
                    <div class="new-name">
                      <el-icon><DocumentChecked /></el-icon>
                      <span class="name-text" :title="task.new_filename">
                        {{ task.new_filename }}
                      </span>
                    </div>
                  </div>

                  <div class="media-info">
                    <div class="info-tags">
                      <el-tag size="small" :type="getMediaTypeColor(task.media_type)">
                        {{ getMediaTypeLabel(task.media_type) }}
                      </el-tag>
                      <el-tag v-if="task.year" size="small" type="info">
                        {{ task.year }}
                      </el-tag>
                      <el-tag v-if="task.season" size="small" type="warning">
                        S{{ String(task.season).padStart(2, '0') }}
                      </el-tag>
                      <el-tag v-if="task.episode" size="small" type="warning">
                        E{{ String(task.episode).padStart(2, '0') }}
                      </el-tag>
                      <el-tag v-if="task.resolution" size="small" type="success">
                        {{ task.resolution }}
                      </el-tag>
                    </div>

                    <div class="confidence-indicator">
                      <el-tooltip :content="`置信度: ${Math.round(task.confidence * 100)}%`">
                        <div class="confidence-bar">
                          <div
                            class="confidence-fill"
                            :style="{ width: `${task.confidence * 100}%` }"
                            :class="getConfidenceClass(task.confidence)"
                          />
                        </div>
                      </el-tooltip>
                      <span class="confidence-value">{{ Math.round(task.confidence * 100) }}%</span>
                    </div>
                  </div>

                  <div class="task-status" v-if="task.needs_confirmation">
                    <el-tooltip :content="task.confirmation_reason">
                      <el-tag type="warning" size="small" effect="dark">
                        <el-icon><Warning /></el-icon>
                        需确认
                      </el-tag>
                    </el-tooltip>
                  </div>

                  <div class="task-status" v-else-if="task.tmdb_match">
                    <el-tag type="success" size="small" effect="dark">
                      <el-icon><Check /></el-icon>
                      TMDB匹配
                    </el-tag>
                  </div>
                </div>

                <div class="task-actions">
                  <el-button
                    type="primary"
                    text
                    size="small"
                    @click="editTask(task)"
                  >
                    <el-icon><Edit /></el-icon>
                    编辑
                  </el-button>
                  <el-button
                    type="danger"
                    text
                    size="small"
                    @click="removeTask(task)"
                  >
                    <el-icon><Delete /></el-icon>
                    跳过
                  </el-button>
                </div>
              </div>
            </div>
          </div>

          <div class="step-actions">
            <el-button size="large" @click="currentStep = 1">
              上一步
            </el-button>
            <el-button
              type="primary"
              size="large"
              :disabled="selectedTasks.length === 0"
              @click="currentStep = 3"
            >
              下一步
              <el-icon class="el-icon--right"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <!-- Step 3: Execute -->
      <div class="step-section glass-card" :class="{ 'active': currentStep >= 3, 'disabled': currentStep < 3 }">
        <div class="step-header">
          <div class="step-number">3</div>
          <div class="step-info">
            <h3>执行重命名</h3>
            <p>确认后将开始批量重命名文件</p>
          </div>
        </div>
        
        <div class="step-content" v-show="currentStep >= 3">
          <div class="execute-summary">
            <div class="summary-card">
              <div class="summary-icon">
                <el-icon :size="48" color="var(--primary-500)"><Document /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">{{ selectedTasks.length }}</div>
                <div class="summary-label">待重命名文件</div>
              </div>
            </div>
            
            <div class="summary-card">
              <div class="summary-icon">
                <el-icon :size="48" color="var(--warning-500)"><Warning /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">
                  {{ selectedTasks.filter(path => {
                    const task = previewData?.tasks.find(t => t.source_path === path)
                    return task?.needs_confirmation
                  }).length }}
                </div>
                <div class="summary-label">需确认项</div>
              </div>
            </div>
            
            <div class="summary-card">
              <div class="summary-icon">
                <el-icon :size="48" color="var(--success-500)"><Check /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">
                  {{ selectedTasks.filter(path => {
                    const task = previewData?.tasks.find(t => t.source_path === path)
                    return !task?.needs_confirmation
                  }).length }}
                </div>
                <div class="summary-label">高置信度匹配</div>
              </div>
            </div>
          </div>

          <el-alert
            title="操作提示"
            type="info"
            description="重命名操作不可撤销，建议在执行前备份重要文件。系统将创建日志记录所有变更。"
            show-icon
            :closable="false"
            class="execute-warning"
          />

          <div class="step-actions">
            <el-button size="large" @click="currentStep = 2">
              上一步
            </el-button>
            <el-button
              type="success"
              size="large"
              :loading="executing"
              @click="executeRenameOperation"
            >
              <el-icon><CircleCheck /></el-icon>
              确认执行
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Task Dialog -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑重命名任务"
      width="600px"
      destroy-on-close
    >
      <el-form :model="editingTask" label-width="100px">
        <el-form-item label="原始文件">
          <el-input v-model="editingTask.source_path" disabled />
        </el-form-item>
        <el-form-item label="新文件名">
          <el-input v-model="editingTask.new_filename" />
        </el-form-item>
        <el-form-item label="媒体类型">
          <el-radio-group v-model="editingTask.media_type">
            <el-radio-button value="movie">电影</el-radio-button>
            <el-radio-button value="tv">电视剧</el-radio-button>
            <el-radio-button value="anime">动漫</el-radio-button>
            <el-radio-button value="unknown">未知</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="editingTask.title" />
        </el-form-item>
        <el-form-item label="年份">
          <el-input-number v-model="editingTask.year" :min="1900" :max="2100" />
        </el-form-item>
        <el-form-item label="季">
          <el-input-number v-model="editingTask.season" :min="0" :max="99" />
        </el-form-item>
        <el-form-item label="集">
          <el-input-number v-model="editingTask.episode" :min="0" :max="999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTaskEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- Settings Dialog -->
    <el-dialog
      v-model="showSettings"
      title="重命名规则配置"
      width="700px"
    >
      <el-tabs v-model="settingsTab">
        <el-tab-pane label="命名模板" name="template">
          <el-form label-width="120px">
            <el-form-item label="电影模板">
              <el-input v-model="settings.movieTemplate" />
              <div class="template-hint">
                可用变量: {title}, {year}, {resolution}, {codec}, {source}
              </div>
            </el-form-item>
            <el-form-item label="电视剧模板">
              <el-input v-model="settings.tvTemplate" />
              <div class="template-hint">
                可用变量: {title}, {year}, {season}, {episode}, {resolution}, {codec}
              </div>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="匹配设置" name="matching">
          <el-form label-width="120px">
            <el-form-item label="TMDB API Key">
              <el-input v-model="settings.tmdbApiKey" show-password />
            </el-form-item>
            <el-form-item label="AI API Key">
              <el-input v-model="settings.aiApiKey" show-password />
            </el-form-item>
            <el-form-item label="最小置信度">
              <el-slider v-model="settings.minConfidence" :max="100" show-stops />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="showSettings = false">取消</el-button>
        <el-button type="primary" @click="saveSettings">保存配置</el-button>
      </template>
    </el-dialog>

    <!-- Execute Result Dialog -->
    <el-dialog
      v-model="resultDialogVisible"
      title="执行结果"
      width="600px"
      :close-on-click-modal="false"
    >
      <div class="result-summary">
        <div class="result-item success">
          <el-icon :size="32"><CircleCheck /></el-icon>
          <span class="result-value">{{ executeResult?.success_count || 0 }}</span>
          <span class="result-label">成功</span>
        </div>
        <div class="result-item failed">
          <el-icon :size="32"><CircleClose /></el-icon>
          <span class="result-value">{{ executeResult?.failed_count || 0 }}</span>
          <span class="result-label">失败</span>
        </div>
      </div>
      
      <el-divider />
      
      <div class="result-details" v-if="executeResult?.failed && executeResult.failed.length > 0">
        <h4>失败详情</h4>
        <el-alert
          v-for="(item, index) in executeResult.failed"
          :key="index"
          :title="getFileName(item.source_path)"
          :description="item.error"
          type="error"
          :closable="false"
          class="result-error"
        />
      </div>
      
      <template #footer>
        <el-button type="primary" @click="resultDialogVisible = false; resetWorkflow()">
          完成
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Setting,
  Check,
  Folder,
  FolderOpened,
  VideoPlay,
  InfoFilled,
  Document,
  DocumentChecked,
  ArrowRight,
  Edit,
  Delete,
  Warning,
  CircleCheck,
  CircleClose,
  Cpu
} from '@element-plus/icons-vue'
import { previewRename, executeRename, type RenameTask, type ProgressMessage } from '@/api/rename'

// State
const currentStep = ref(1)
const selectedPath = ref('')
const analyzing = ref(false)
const executing = ref(false)
const selectAll = ref(false)
const filterType = ref<'all' | 'pending' | 'confirmed'>('all')

// Algorithm and Naming Standard
const selectedAlgorithm = ref('ai_enhanced')
const selectedStandard = ref('emby')

const algorithms = ref([
  { value: 'standard', label: '标准本地算法', description: '使用正则表达式解析，速度快', recommended: false },
  { value: 'ai_enhanced', label: 'AI 增强算法', description: '正则+AI智能解析，准确性高', recommended: true },
  { value: 'ai_only', label: '纯 AI 算法', description: '完全AI解析，准确性最高', recommended: false }
])

const namingStandards = ref([
  { value: 'emby', label: 'Emby 标准', description: '兼容 Emby 媒体服务器' },
  { value: 'plex', label: 'Plex 标准', description: '兼容 Plex 媒体服务器' },
  { value: 'kodi', label: 'Kodi 标准', description: '兼容 Kodi 媒体中心' },
  { value: 'custom', label: '自定义', description: '使用自定义命名模板' }
])

const options = reactive({
  recursive: true,
  autoConfirm: false
})

const previewData = ref<{
  tasks: RenameTask[]
  progress: ProgressMessage[]
  total_tasks: number
  needs_confirmation: number
} | null>(null)

const analysisProgress = ref<ProgressMessage[]>([])
const selectedTasks = ref<string[]>([])

// Edit dialog
const editDialogVisible = ref(false)
const editingTask = reactive<Partial<RenameTask>>({})

// Settings
const showSettings = ref(false)
const settingsTab = ref('template')
const settings = reactive({
  movieTemplate: '{title} ({year}) [{resolution}]',
  tvTemplate: '{title} - S{season:02d}E{episode:02d} - [{resolution}]',
  tmdbApiKey: '',
  aiApiKey: '',
  minConfidence: 70
})

// Result dialog
const resultDialogVisible = ref(false)
const executeResult = ref<{
  success_count: number
  failed_count: number
  success: { source_path: string; target_path?: string; success: boolean }[]
  failed: { source_path: string; error?: string; success: boolean }[]
} | null>(null)

// Computed
const filteredTasks = computed((): RenameTask[] => {
  if (!previewData.value) return []

  let tasks = previewData.value.tasks

  if (filterType.value === 'pending') {
    tasks = tasks.filter((t: RenameTask) => t.needs_confirmation)
  } else if (filterType.value === 'confirmed') {
    tasks = tasks.filter((t: RenameTask) => !t.needs_confirmation)
  }

  return tasks
})

// Watch for select all
watch(selectAll, (val) => {
  if (val && previewData.value) {
    selectedTasks.value = filteredTasks.value.map(t => t.source_path)
  } else {
    selectedTasks.value = []
  }
})

// Methods
const openPathSelector = () => {
  ElMessage.info('文件夹选择功能开发中')
  // 实际项目中这里会打开文件选择器
  selectedPath.value = '/media/movies'
}

const startAnalysis = async () => {
  if (!selectedPath.value) {
    ElMessage.warning('请先选择文件夹')
    return
  }

  analyzing.value = true
  analysisProgress.value = []
  currentStep.value = 2

  try {
    const response = await previewRename({
      path: selectedPath.value,
      recursive: options.recursive
    })

    previewData.value = response
    analysisProgress.value = response.progress
    
    // Auto-select all tasks
    selectedTasks.value = response.tasks.map(t => t.source_path)
    
    ElMessage.success(`分析完成，共发现 ${response.total_tasks} 个媒体文件`)
  } catch {
    ElMessage.error('分析失败')
    currentStep.value = 1
  } finally {
    analyzing.value = false
  }
}

const handleSelectAll = (val: boolean) => {
  if (val && previewData.value) {
    selectedTasks.value = filteredTasks.value.map((t: RenameTask) => t.source_path)
  } else {
    selectedTasks.value = []
  }
}

const getFileName = (path: string) => {
  return path.split('/').pop() || path
}

const getMediaTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    movie: '电影',
    tv: '电视剧',
    anime: '动漫',
    unknown: '未知'
  }
  return map[type] || type
}

const getMediaTypeColor = (type: string) => {
  const map: Record<string, string> = {
    movie: 'primary',
    tv: 'success',
    anime: 'warning',
    unknown: 'info'
  }
  return map[type] || 'info'
}

const getConfidenceClass = (confidence: number) => {
  if (confidence >= 0.9) return 'high'
  if (confidence >= 0.7) return 'medium'
  return 'low'
}

const editTask = (task: RenameTask) => {
  Object.assign(editingTask, { ...task })
  editDialogVisible.value = true
}

const saveTaskEdit = () => {
  if (previewData.value && editingTask.source_path) {
    const index = previewData.value.tasks.findIndex(
      t => t.source_path === editingTask.source_path
    )
    if (index !== -1) {
      previewData.value.tasks[index] = { ...editingTask } as RenameTask
      ElMessage.success('已保存修改')
    }
  }
  editDialogVisible.value = false
}

const removeTask = (task: RenameTask) => {
  if (previewData.value) {
    previewData.value.tasks = previewData.value.tasks.filter(
      t => t.source_path !== task.source_path
    )
    selectedTasks.value = selectedTasks.value.filter(
      path => path !== task.source_path
    )
    previewData.value.total_tasks--
    ElMessage.success('已跳过该文件')
  }
}

const saveSettings = () => {
  ElMessage.success('配置已保存')
  showSettings.value = false
}

const executeRenameOperation = async () => {
  executing.value = true

  try {
    const response = await executeRename({
      path: selectedPath.value,
      selected_tasks: selectedTasks.value,
      recursive: options.recursive
    })

    executeResult.value = response
    resultDialogVisible.value = true
    
    if (response.failed_count === 0) {
      ElMessage.success('所有文件重命名成功')
    } else {
      ElMessage.warning(`${response.failed_count} 个文件重命名失败`)
    }
  } catch {
    ElMessage.error('执行失败')
  } finally {
    executing.value = false
  }
}

const resetWorkflow = () => {
  currentStep.value = 1
  selectedPath.value = ''
  previewData.value = null
  selectedTasks.value = []
  analysisProgress.value = []
  selectAll.value = false
}
</script>

<style scoped>
.rename-page {
  min-height: 100%;
}

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding: 0 8px;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 8px;
}

.page-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
}

/* Configuration Section */
.configuration-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
}

.config-card {
  padding: 24px;
  border-radius: 12px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  box-shadow: var(--el-box-shadow-light);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  color: var(--el-color-primary);
  font-size: 20px;
}

.help-icon {
  color: var(--el-text-color-secondary);
  cursor: help;
}

.config-content {
  padding: 8px 0;
}

.algorithm-group,
.standard-group {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  width: 100%;
}

.algorithm-option,
.standard-option {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  min-width: 180px;
}

.algo-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.algo-name,
.std-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.algo-desc,
.std-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.recommend-tag {
  margin-left: 4px;
}

/* Step Section */
.step-section {
  margin-bottom: 24px;
  border-radius: var(--radius-xl);
  overflow: hidden;
  transition: all var(--transition-normal);
}

.step-section.disabled {
  opacity: 0.6;
  pointer-events: none;
}

.step-section.active {
  box-shadow: var(--shadow-lg);
}

.step-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.step-number {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--primary-500);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
}

.step-section.disabled .step-number {
  background: var(--gray-300);
}

.step-info {
  flex: 1;
}

.step-info h3 {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--text-primary);
}

.step-info p {
  font-size: 14px;
  color: var(--text-secondary);
}

.step-stats {
  display: flex;
  gap: 8px;
}

.step-content {
  padding: 24px;
}

.step-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--border-color);
}

/* Path Selector */
.path-selector {
  margin-bottom: 20px;
}

.path-input {
  font-size: 16px;
}

.path-options {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
}

/* Progress Log */
.progress-log {
  max-height: 200px;
  overflow-y: auto;
  padding: 16px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
  margin-bottom: 24px;
}

.log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-size: 14px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
}

.log-item:last-child {
  border-bottom: none;
}

.log-item.latest {
  color: var(--primary-500);
  font-weight: 500;
}

.log-progress {
  width: 100px;
  margin-left: auto;
}

/* Task List */
.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
}

.task-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 500px;
  overflow-y: auto;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  border: 2px solid transparent;
  transition: all var(--transition-fast);
}

.task-item:hover {
  border-color: var(--primary-200);
}

.task-item.needs-confirmation {
  border-color: var(--warning-200);
  background: var(--warning-50);
}

.task-item.selected {
  border-color: var(--primary-500);
}

.task-checkbox {
  flex-shrink: 0;
}

.task-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.original-name,
.new-name {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  font-size: 14px;
  max-width: 300px;
}

.original-name {
  background: var(--gray-100);
  color: var(--text-secondary);
}

.new-name {
  background: var(--primary-50);
  color: var(--primary-700);
  font-weight: 500;
}

.name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arrow-icon {
  color: var(--text-tertiary);
}

.media-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.info-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.confidence-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.confidence-bar {
  width: 60px;
  height: 6px;
  background: var(--gray-200);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width var(--transition-normal);
}

.confidence-fill.high {
  background: var(--success-500);
}

.confidence-fill.medium {
  background: var(--warning-500);
}

.confidence-fill.low {
  background: var(--danger-500);
}

.confidence-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 36px;
}

.task-status {
  flex-shrink: 0;
}

.task-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

/* Execute Summary */
.execute-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-xl);
}

.summary-icon {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-xl);
  background: var(--bg-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.summary-info {
  flex: 1;
}

.summary-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
}

.summary-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.execute-warning {
  margin-bottom: 24px;
}

/* Result Summary */
.result-summary {
  display: flex;
  justify-content: center;
  gap: 48px;
  padding: 24px;
}

.result-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.result-item.success {
  color: var(--success-500);
}

.result-item.failed {
  color: var(--danger-500);
}

.result-value {
  font-size: 36px;
  font-weight: 700;
}

.result-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.result-details {
  max-height: 300px;
  overflow-y: auto;
}

.result-details h4 {
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 600;
}

.result-error {
  margin-bottom: 8px;
}

/* Template Hint */
.template-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
}

/* Responsive */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .step-header {
    flex-wrap: wrap;
  }

  .step-stats {
    width: 100%;
    justify-content: flex-end;
  }

  .file-info {
    flex-direction: column;
    align-items: flex-start;
  }

  .arrow-icon {
    transform: rotate(90deg);
  }

  .media-info {
    flex-direction: column;
    align-items: flex-start;
  }

  .confidence-indicator {
    margin-left: 0;
  }

  .task-item {
    flex-direction: column;
    align-items: flex-start;
  }

  .task-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .execute-summary {
    grid-template-columns: 1fr;
  }
}
</style>
