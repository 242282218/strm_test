<template>
  <div class="smart-rename-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">
          <span class="gradient-text">智能重命名</span>
          <el-tag type="primary" effect="dark" class="version-tag">v2.0</el-tag>
        </h1>
        <p class="page-subtitle">基于多算法和 Emby 规范，智能识别并整理媒体文件</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" size="large" @click="showSettings = true">
          <el-icon><Setting /></el-icon>
          配置规则
        </el-button>
      </div>
    </div>

    <!-- Algorithm Selection Card -->
    <div class="algorithm-card glass-card">
      <div class="card-header">
        <h3>
          <el-icon><Cpu /></el-icon>
          选择重命名算法
        </h3>
        <el-tooltip content="选择适合您需求的解析算法">
          <el-icon><InfoFilled /></el-icon>
        </el-tooltip>
      </div>
      
      <div class="algorithm-options">
        <el-radio-group v-model="selectedAlgorithm" size="large">
          <el-radio-button 
            v-for="algo in algorithms" 
            :key="algo.algorithm" 
            :value="algo.algorithm"
            :class="{ 'recommended': algo.recommended }"
          >
            <div class="algorithm-option">
              <span class="algo-name">{{ algo.name }}</span>
              <el-tag v-if="algo.recommended" type="success" size="small">推荐</el-tag>
            </div>
          </el-radio-button>
        </el-radio-group>
        
        <div class="algorithm-description" v-if="currentAlgorithm">
          <p>{{ currentAlgorithm.description }}</p>
          <div class="algorithm-features">
            <el-tag 
              v-for="feature in currentAlgorithm.features" 
              :key="feature"
              type="info"
              size="small"
              effect="plain"
            >
              {{ feature }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- Naming Standard Card -->
    <div class="standard-card glass-card">
      <div class="card-header">
        <h3>
          <el-icon><Document /></el-icon>
          命名标准
        </h3>
      </div>
      
      <div class="standard-options">
        <el-radio-group v-model="selectedStandard" size="large">
          <el-radio-button 
            v-for="std in namingStandards" 
            :key="std.standard" 
            :value="std.standard"
          >
            {{ std.name }}
          </el-radio-button>
        </el-radio-group>
        
        <div class="standard-examples" v-if="currentStandard">
          <div class="example-item">
            <span class="example-label">电影:</span>
            <code class="example-code">{{ currentStandard.movie_example }}</code>
          </div>
          <div class="example-item">
            <span class="example-label">剧集:</span>
            <code class="example-code">{{ currentStandard.tv_example }}</code>
          </div>
          <div class="example-item">
            <span class="example-label">特别篇:</span>
            <code class="example-code">{{ currentStandard.specials_example }}</code>
          </div>
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
            <el-checkbox v-model="options.createFolders">
              创建文件夹结构
            </el-checkbox>
            <el-checkbox v-model="options.autoConfirm">
              自动确认高置信度匹配 (≥90%)
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
            <p>查看识别的媒体信息并确认</p>
          </div>
          <div class="step-stats" v-if="previewData">
            <el-tag type="info">共 {{ previewData.total_items }} 个文件</el-tag>
            <el-tag type="success">已匹配 {{ previewData.matched_items }}</el-tag>
            <el-tag type="warning" v-if="previewData.needs_confirmation > 0">
              {{ previewData.needs_confirmation }} 个待确认
            </el-tag>
          </div>
        </div>
        
        <div class="step-content" v-show="currentStep >= 2 && previewData">
          <!-- Algorithm Info Banner -->
          <el-alert
            v-if="previewData"
            :title="`使用算法: ${getAlgorithmName(previewData.algorithm_used)} | 命名标准: ${getStandardName(previewData.naming_standard)}`"
            type="info"
            :closable="false"
            class="algorithm-banner"
          />

          <!-- Task List -->
          <div class="task-list" v-if="previewData && previewData.items.length > 0">
            <div class="list-header">
              <el-checkbox v-model="selectAll" @change="handleSelectAll">
                全选
              </el-checkbox>
              <div class="header-filters">
                <el-radio-group v-model="filterType" size="small">
                  <el-radio-button value="all">全部</el-radio-button>
                  <el-radio-button value="pending">待确认</el-radio-button>
                  <el-radio-button value="confirmed">已确认</el-radio-button>
                  <el-radio-button value="matched">已匹配</el-radio-button>
                </el-radio-group>
              </div>
            </div>

            <div class="task-items">
              <div
                v-for="item in filteredItems"
                :key="item.original_path"
                class="task-item"
                :class="{
                  'needs-confirmation': item.needs_confirmation,
                  'selected': selectedItems.includes(item.original_path)
                }"
              >
                <el-checkbox
                  v-model="selectedItems"
                  :label="item.original_path"
                  class="task-checkbox"
                >
                  {{ '' }}
                </el-checkbox>

                <div class="task-preview">
                  <div class="file-info">
                    <div class="original-name">
                      <el-icon><Document /></el-icon>
                      <span class="name-text" :title="item.original_path">
                        {{ getFileName(item.original_path) }}
                      </span>
                    </div>
                    <el-icon class="arrow-icon"><ArrowRight /></el-icon>
                    <div class="new-name">
                      <el-icon><DocumentChecked /></el-icon>
                      <span class="name-text" :title="item.new_name">
                        {{ item.new_name }}
                      </span>
                    </div>
                  </div>

                  <div class="media-info">
                    <div class="info-tags">
                      <el-tag size="small" :type="getMediaTypeColor(item.media_type)">
                        {{ getMediaTypeLabel(item.media_type) }}
                      </el-tag>
                      <el-tag v-if="item.tmdb_year" size="small" type="info">
                        {{ item.tmdb_year }}
                      </el-tag>
                      <el-tag v-if="item.season !== undefined" size="small" type="warning">
                        S{{ String(item.season).padStart(2, '0') }}
                      </el-tag>
                      <el-tag v-if="item.episode !== undefined" size="small" type="warning">
                        E{{ String(item.episode).padStart(2, '0') }}
                      </el-tag>
                      <el-tag v-if="item.tmdb_id" size="small" type="success">
                        TMDB:{{ item.tmdb_id }}
                      </el-tag>
                      <el-tag size="small" type="info" effect="plain">
                        {{ getAlgorithmShortName(item.used_algorithm) }}
                      </el-tag>
                    </div>

                    <div class="confidence-indicator">
                      <el-tooltip :content="`置信度: ${Math.round(item.overall_confidence * 100)}%`">
                        <div class="confidence-bar">
                          <div
                            class="confidence-fill"
                            :style="{ width: `${item.overall_confidence * 100}%` }"
                            :class="getConfidenceClass(item.overall_confidence)"
                          />
                        </div>
                      </el-tooltip>
                      <span class="confidence-value">{{ Math.round(item.overall_confidence * 100) }}%</span>
                    </div>
                  </div>

                  <div class="task-status" v-if="item.needs_confirmation">
                    <el-tooltip :content="item.confirmation_reason">
                      <el-tag type="warning" size="small" effect="dark">
                        <el-icon><Warning /></el-icon>
                        需确认
                      </el-tag>
                    </el-tooltip>
                  </div>

                  <div class="task-status" v-else-if="item.tmdb_id">
                    <el-tag type="success" size="small" effect="dark">
                      <el-icon><Check /></el-icon>
                      已匹配
                    </el-tag>
                  </div>
                </div>

                <div class="task-actions">
                  <el-button
                    type="primary"
                    text
                    size="small"
                    @click="editItem(item)"
                  >
                    <el-icon><Edit /></el-icon>
                    编辑
                  </el-button>
                  <el-button
                    type="danger"
                    text
                    size="small"
                    @click="removeItem(item)"
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
              :disabled="selectedItems.length === 0"
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
                <div class="summary-value">{{ selectedItems.length }}</div>
                <div class="summary-label">待重命名文件</div>
              </div>
            </div>
            
            <div class="summary-card">
              <div class="summary-icon">
                <el-icon :size="48" color="var(--warning-500)"><Warning /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">
                  {{ selectedItems.filter(path => {
                    const item = previewData?.items.find(i => i.original_path === path)
                    return item?.needs_confirmation
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
                  {{ selectedItems.filter(path => {
                    const item = previewData?.items.find(i => i.original_path === path)
                    return !item?.needs_confirmation
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
              @click="executeRename"
            >
              <el-icon><CircleCheck /></el-icon>
              确认执行
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Item Dialog -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑重命名项目"
      width="600px"
      destroy-on-close
    >
      <el-form :model="editingItem" label-width="100px">
        <el-form-item label="原始文件">
          <el-input v-model="editingItem.original_path" disabled />
        </el-form-item>
        <el-form-item label="新文件名">
          <el-input v-model="editingItem.new_name" />
        </el-form-item>
        <el-form-item label="媒体类型">
          <el-radio-group v-model="editingItem.media_type">
            <el-radio-button value="movie">电影</el-radio-button>
            <el-radio-button value="tv">电视剧</el-radio-button>
            <el-radio-button value="anime">动漫</el-radio-button>
            <el-radio-button value="unknown">未知</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="TMDB标题">
          <el-input v-model="editingItem.tmdb_title" />
        </el-form-item>
        <el-form-item label="年份">
          <el-input-number v-model="editingItem.tmdb_year" :min="1900" :max="2100" />
        </el-form-item>
        <el-form-item label="季">
          <el-input-number v-model="editingItem.season" :min="0" :max="99" />
        </el-form-item>
        <el-form-item label="集">
          <el-input-number v-model="editingItem.episode" :min="0" :max="999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveItemEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- Settings Dialog -->
    <el-dialog
      v-model="showSettings"
      title="智能重命名配置"
      width="800px"
    >
      <el-tabs v-model="settingsTab">
        <el-tab-pane label="命名模板" name="template">
          <el-form label-width="140px">
            <el-form-item label="电影模板">
              <el-input v-model="namingConfig.movie_template" />
              <div class="template-hint">
                可用变量: {title}, {year}
              </div>
            </el-form-item>
            <el-form-item label="剧集模板">
              <el-input v-model="namingConfig.tv_episode_template" />
              <div class="template-hint">
                可用变量: {title}, {year}, {season}, {episode}
              </div>
            </el-form-item>
            <el-form-item label="特别篇文件夹">
              <el-input v-model="namingConfig.specials_folder" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
        
        <el-tab-pane label="高级选项" name="advanced">
          <el-form label-width="140px">
            <el-form-item label="包含质量信息">
              <el-switch v-model="namingConfig.include_quality" />
            </el-form-item>
            <el-form-item label="包含来源信息">
              <el-switch v-model="namingConfig.include_source" />
            </el-form-item>
            <el-form-item label="包含编码信息">
              <el-switch v-model="namingConfig.include_codec" />
            </el-form-item>
            <el-form-item label="包含TMDB ID">
              <el-switch v-model="namingConfig.include_tmdb_id" />
            </el-form-item>
            <el-form-item label="清理非法字符">
              <el-switch v-model="namingConfig.sanitize_filenames" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
        
        <el-tab-pane label="AI设置" name="ai">
          <el-form label-width="140px">
            <el-form-item label="AI API Key">
              <el-input v-model="aiSettings.apiKey" show-password placeholder="在 config.yaml 中配置" disabled />
              <div class="template-hint">
                请在服务器配置文件中的 ai.api_key 或 zhipu.api_key 设置
              </div>
            </el-form-item>
            <el-form-item label="置信度阈值">
              <el-slider v-model="options.aiThreshold" :max="100" show-stops />
              <div class="template-hint">
                低于此阈值的解析结果将触发 AI 解析
              </div>
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
          <span class="result-value">{{ executeResult?.success_items || 0 }}</span>
          <span class="result-label">成功</span>
        </div>
        <div class="result-item failed">
          <el-icon :size="32"><CircleClose /></el-icon>
          <span class="result-value">{{ executeResult?.failed_items || 0 }}</span>
          <span class="result-label">失败</span>
        </div>
        <div class="result-item skipped">
          <el-icon :size="32"><Remove /></el-icon>
          <span class="result-value">{{ executeResult?.skipped_items || 0 }}</span>
          <span class="result-label">跳过</span>
        </div>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Setting,
  Check,
  Folder,
  FolderOpened,
  VideoPlay,
  Document,
  DocumentChecked,
  ArrowRight,
  Edit,
  Delete,
  Warning,
  CircleCheck,
  CircleClose,
  Remove,
  Cpu,
  InfoFilled
} from '@element-plus/icons-vue'
import {
  previewSmartRename,
  executeSmartRename,
  getAlgorithms,
  getNamingStandards,
  getSmartRenameStatus,
  type SmartRenameItem,
  type AlgorithmInfo,
  type NamingStandardInfo
} from '@/api/smartRename'

// State
const currentStep = ref(1)
const selectedPath = ref('')
const analyzing = ref(false)
const executing = ref(false)
const selectAll = ref(false)
const filterType = ref<'all' | 'pending' | 'confirmed' | 'matched'>('all')

const selectedAlgorithm = ref('ai_enhanced')
const selectedStandard = ref('emby')

const algorithms = ref<AlgorithmInfo[]>([])
const namingStandards = ref<NamingStandardInfo[]>([])

const options = reactive({
  recursive: true,
  createFolders: true,
  autoConfirm: false,
  aiThreshold: 70
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

const aiSettings = reactive({
  apiKey: ''
})

const previewData = ref<{
  batch_id: string
  items: SmartRenameItem[]
  total_items: number
  matched_items: number
  needs_confirmation: number
  algorithm_used: string
  naming_standard: string
} | null>(null)

const selectedItems = ref<string[]>([])

// Edit dialog
const editDialogVisible = ref(false)
const editingItem = reactive<Partial<SmartRenameItem>>({})

// Settings
const showSettings = ref(false)
const settingsTab = ref('template')

// Result dialog
const resultDialogVisible = ref(false)
const executeResult = ref<{
  success_items: number
  failed_items: number
  skipped_items: number
} | null>(null)

// Computed
const currentAlgorithm = computed(() => {
  return algorithms.value.find(a => a.algorithm === selectedAlgorithm.value)
})

const currentStandard = computed(() => {
  return namingStandards.value.find(s => s.standard === selectedStandard.value)
})

const filteredItems = computed(() => {
  if (!previewData.value) return []

  let items = previewData.value.items

  if (filterType.value === 'pending') {
    items = items.filter(i => i.needs_confirmation)
  } else if (filterType.value === 'confirmed') {
    items = items.filter(i => !i.needs_confirmation)
  } else if (filterType.value === 'matched') {
    items = items.filter(i => i.tmdb_id)
  }

  return items
})

// Methods
const loadAlgorithms = async () => {
  try {
    algorithms.value = await getAlgorithms()
  } catch (error) {
    console.error('Failed to load algorithms:', error)
  }
}

const loadNamingStandards = async () => {
  try {
    namingStandards.value = await getNamingStandards()
  } catch (error) {
    console.error('Failed to load naming standards:', error)
  }
}

const loadStatus = async () => {
  try {
    const status = await getSmartRenameStatus()
    aiSettings.apiKey = status.ai_available ? '已配置' : '未配置'
  } catch (error) {
    console.error('Failed to load status:', error)
  }
}

const openPathSelector = () => {
  ElMessage.info('文件夹选择功能开发中')
  selectedPath.value = '/media/movies'
}

const startAnalysis = async () => {
  if (!selectedPath.value) {
    ElMessage.warning('请先选择文件夹')
    return
  }

  analyzing.value = true
  currentStep.value = 2

  try {
    const response = await previewSmartRename({
      target_path: selectedPath.value,
      algorithm: selectedAlgorithm.value as any,
      naming_standard: selectedStandard.value as any,
      recursive: options.recursive,
      create_folders: options.createFolders,
      auto_confirm_high_confidence: options.autoConfirm,
      ai_confidence_threshold: options.aiThreshold / 100,
      naming_config: namingConfig
    })

    previewData.value = response
    
    // Auto-select all items
    selectedItems.value = response.items.map(i => i.original_path)
    
    ElMessage.success(`分析完成，共发现 ${response.total_items} 个媒体文件`)
  } catch (error) {
    ElMessage.error('分析失败')
    currentStep.value = 1
  } finally {
    analyzing.value = false
  }
}

const handleSelectAll = (val: boolean) => {
  if (val && previewData.value) {
    selectedItems.value = filteredItems.value.map(i => i.original_path)
  } else {
    selectedItems.value = []
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

const getAlgorithmName = (algo: string) => {
  const map: Record<string, string> = {
    standard: '标准本地算法',
    ai_enhanced: 'AI 增强算法',
    ai_only: '纯 AI 算法'
  }
  return map[algo] || algo
}

const getAlgorithmShortName = (algo?: string) => {
  const map: Record<string, string> = {
    standard: '本地',
    ai_enhanced: 'AI+',
    ai_only: 'AI'
  }
  return map[algo || ''] || algo
}

const getStandardName = (std: string) => {
  const map: Record<string, string> = {
    emby: 'Emby',
    plex: 'Plex',
    kodi: 'Kodi',
    custom: '自定义'
  }
  return map[std] || std
}

const getConfidenceClass = (confidence: number) => {
  if (confidence >= 0.9) return 'high'
  if (confidence >= 0.7) return 'medium'
  return 'low'
}

const editItem = (item: SmartRenameItem) => {
  Object.assign(editingItem, { ...item })
  editDialogVisible.value = true
}

const saveItemEdit = () => {
  if (previewData.value && editingItem.original_path) {
    const index = previewData.value.items.findIndex(
      i => i.original_path === editingItem.original_path
    )
    if (index !== -1) {
      previewData.value.items[index] = { ...editingItem } as SmartRenameItem
      ElMessage.success('已保存修改')
    }
  }
  editDialogVisible.value = false
}

const removeItem = (item: SmartRenameItem) => {
  if (previewData.value) {
    previewData.value.items = previewData.value.items.filter(
      i => i.original_path !== item.original_path
    )
    selectedItems.value = selectedItems.value.filter(
      path => path !== item.original_path
    )
    previewData.value.total_items--
    ElMessage.success('已跳过该文件')
  }
}

const saveSettings = () => {
  ElMessage.success('配置已保存')
  showSettings.value = false
}

const executeRename = async () => {
  if (!previewData.value?.batch_id) return
  
  executing.value = true

  try {
    const response = await executeSmartRename({
      batch_id: previewData.value.batch_id
    })

    executeResult.value = response
    resultDialogVisible.value = true
    
    if (response.failed_items === 0) {
      ElMessage.success('所有文件重命名成功')
    } else {
      ElMessage.warning(`${response.failed_items} 个文件重命名失败`)
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
  selectedItems.value = []
  selectAll.value = false
}

// Lifecycle
onMounted(() => {
  loadAlgorithms()
  loadNamingStandards()
  loadStatus()
})
</script>

<style scoped>
.smart-rename-page {
  min-height: 100%;
}

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 0 8px;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.version-tag {
  font-size: 12px;
}

.page-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
}

/* Algorithm & Standard Cards */
.algorithm-card,
.standard-card {
  margin-bottom: 24px;
  padding: 24px;
  border-radius: var(--radius-xl);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.card-header h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.algorithm-options,
.standard-options {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.algorithm-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.algo-name {
  font-weight: 500;
}

.algorithm-description {
  padding: 16px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
}

.algorithm-description p {
  margin-bottom: 12px;
  color: var(--text-secondary);
}

.algorithm-features {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.standard-examples {
  padding: 16px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
}

.example-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.example-item:last-child {
  margin-bottom: 0;
}

.example-label {
  min-width: 60px;
  color: var(--text-secondary);
  font-size: 14px;
}

.example-code {
  font-family: monospace;
  font-size: 13px;
  color: var(--primary-600);
  background: var(--bg-primary);
  padding: 4px 8px;
  border-radius: var(--radius-md);
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

/* Algorithm Banner */
.algorithm-banner {
  margin-bottom: 16px;
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

.result-item.skipped {
  color: var(--warning-500);
}

.result-value {
  font-size: 36px;
  font-weight: 700;
}

.result-label {
  font-size: 14px;
  color: var(--text-secondary);
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
