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
          高级配置
        </el-button>
        <el-button type="info" size="large" @click="showHelp = true">
          <el-icon><QuestionFilled /></el-icon>
          使用帮助
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
              :key="algo.algorithm" 
              :value="algo.algorithm"
              :class="{ 'recommended': algo.recommended }"
            >
              <div class="algorithm-option">
                <div class="algo-header">
                  <span class="algo-name">{{ algo.name }}</span>
                  <el-tag v-if="algo.recommended" type="success" size="small" class="recommend-tag">推荐</el-tag>
                </div>
                <div class="algo-desc">{{ algo.description }}</div>
              </div>
            </el-radio-button>
          </el-radio-group>
          
          <div class="algorithm-details" v-if="currentAlgorithm">
            <div class="details-header">
              <span class="details-title">算法特性</span>
            </div>
            <div class="features-grid">
              <div 
                v-for="feature in currentAlgorithm.features" 
                :key="feature"
                class="feature-item"
              >
                <el-icon class="feature-icon"><Check /></el-icon>
                <span class="feature-text">{{ feature }}</span>
              </div>
            </div>
          </div>
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
              :key="std.standard" 
              :value="std.standard"
            >
              <div class="standard-option">
                <span class="std-name">{{ std.name }}</span>
                <span class="std-desc">{{ std.description }}</span>
              </div>
            </el-radio-button>
          </el-radio-group>
          
          <div class="standard-examples" v-if="currentStandard">
            <div class="examples-header">
              <span class="examples-title">命名示例</span>
            </div>
            <div class="examples-grid">
              <div class="example-card">
                <div class="example-type">
                  <el-icon><VideoCamera /></el-icon>
                  电影
                </div>
                <div class="example-path">{{ currentStandard.movie_example }}</div>
              </div>
              <div class="example-card">
                <div class="example-type">
                  <el-icon><Monitor /></el-icon>
                  剧集
                </div>
                <div class="example-path">{{ currentStandard.tv_example }}</div>
              </div>
              <div class="example-card">
                <div class="example-type">
                  <el-icon><Star /></el-icon>
                  特别篇
                </div>
                <div class="example-path">{{ currentStandard.specials_example }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Advanced Options Card -->
      <div class="config-card glass-card">
        <div class="card-header">
          <div class="header-title">
            <el-icon class="header-icon"><Tools /></el-icon>
            <h3>高级选项</h3>
          </div>
          <el-tooltip content="配置重命名的高级参数" placement="top">
            <el-icon class="help-icon"><InfoFilled /></el-icon>
          </el-tooltip>
        </div>
        
        <div class="config-content">
          <div class="options-grid">
            <div class="option-group">
              <label class="option-label">文件处理</label>
              <div class="option-items">
                <el-checkbox v-model="options.recursive" class="option-item">
                  包含子文件夹
                </el-checkbox>
                <el-checkbox v-model="options.createFolders" class="option-item">
                  创建文件夹结构
                </el-checkbox>
                <el-checkbox v-model="options.autoConfirm" class="option-item">
                  自动确认高置信度匹配 (≥90%)
                </el-checkbox>
              </div>
            </div>
            
            <div class="option-group">
              <label class="option-label">命名规则</label>
              <div class="option-items">
                <el-checkbox v-model="options.includeQuality" class="option-item">
                  包含质量信息
                </el-checkbox>
                <el-checkbox v-model="options.includeSource" class="option-item">
                  包含来源信息
                </el-checkbox>
                <el-checkbox v-model="options.includeTmdbId" class="option-item">
                  包含 TMDB ID
                </el-checkbox>
              </div>
            </div>
            
            <div class="option-group">
              <label class="option-label">安全设置</label>
              <div class="option-items">
                <el-checkbox v-model="options.backupBeforeRename" class="option-item">
                  重命名前备份
                </el-checkbox>
                <el-checkbox v-model="options.dryRun" class="option-item">
                  仅预览不执行
                </el-checkbox>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Operation Flow -->
    <div class="operation-flow">
      <!-- Step Progress -->
      <div class="step-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progressWidth }"></div>
        </div>
        <div class="step-indicators">
          <div class="step-indicator" :class="{ 'active': currentStep >= 1, 'completed': currentStep > 1 }">
            <div class="step-circle">1</div>
            <span class="step-label">选择路径</span>
          </div>
          <div class="step-indicator" :class="{ 'active': currentStep >= 2, 'completed': currentStep > 2 }">
            <div class="step-circle">2</div>
            <span class="step-label">预览结果</span>
          </div>
          <div class="step-indicator" :class="{ 'active': currentStep >= 3, 'completed': currentStep > 3 }">
            <div class="step-circle">3</div>
            <span class="step-label">执行重命名</span>
          </div>
        </div>
      </div>

      <!-- Step 1: Select Path -->
      <div class="step-section glass-card" :class="{ 'active': currentStep >= 1 }">
        <div class="step-header">
          <div class="step-info">
            <div class="step-title">
              <el-icon><FolderOpened /></el-icon>
              <h3>选择媒体文件夹</h3>
            </div>
            <p class="step-description">选择包含需要整理的媒体文件的文件夹路径</p>
          </div>
          <div class="step-status">
            <el-tag v-if="selectedPath" type="success" effect="dark" class="status-tag">
              <el-icon><Check /></el-icon>
              已选择
            </el-tag>
            <el-tag v-else type="info" effect="plain" class="status-tag">
              <el-icon><Clock /></el-icon>
              等待选择
            </el-tag>
          </div>
        </div>
        
        <div class="step-content" v-show="currentStep >= 1">
          <div class="path-selector">
            <div class="selector-header">
              <span class="selector-label">文件夹路径</span>
              <el-button 
                type="primary" 
                size="small" 
                @click="openPathSelector"
                class="browse-btn"
              >
                <el-icon><FolderOpened /></el-icon>
                浏览文件夹
              </el-button>
            </div>
            <el-input
              v-model="selectedPath"
              placeholder="请选择包含媒体文件的文件夹..."
              readonly
              size="large"
              class="path-input"
            >
              <template #prefix>
                <el-icon><Folder /></el-icon>
              </template>
            </el-input>
          </div>
          
          <div class="step-actions">
            <el-button
              type="primary"
              size="large"
              :disabled="!selectedPath"
              :loading="analyzing"
              @click="startAnalysis"
              class="action-btn"
            >
              <el-icon><Search /></el-icon>
              扫描媒体文件
            </el-button>
            <el-button
              type="info"
              size="large"
              @click="resetSelection"
              :disabled="!selectedPath"
              class="action-btn"
            >
              <el-icon><Refresh /></el-icon>
              重新选择
            </el-button>
          </div>
        </div>
      </div>

      <!-- Step 2: Preview Results -->
      <div class="step-section glass-card" :class="{ 'active': currentStep >= 2, 'disabled': currentStep < 2 }">
        <div class="step-header">
          <div class="step-info">
            <div class="step-title">
              <el-icon><View /></el-icon>
              <h3>预览重命名结果</h3>
            </div>
            <p class="step-description">查看识别的媒体信息，确认或修改重命名建议</p>
          </div>
          <div class="step-status" v-if="previewData">
            <div class="stats-panel">
              <div class="stat-item">
                <span class="stat-label">总文件数</span>
                <span class="stat-value">{{ previewData.total_items }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">已匹配</span>
                <span class="stat-value success">{{ previewData.matched_items }}</span>
              </div>
              <div class="stat-item" v-if="previewData.needs_confirmation > 0">
                <span class="stat-label">待确认</span>
                <span class="stat-value warning">{{ previewData.needs_confirmation }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">置信度</span>
                <span class="stat-value info">{{ Math.round((previewData.average_confidence ?? 0) * 100) }}%</span>
              </div>
            </div>
          </div>
        </div>
        
        <div class="step-content" v-if="currentStep >= 2 && previewData">
          <!-- Analysis Summary -->
          <div class="summary-banner">
            <div class="summary-info">
              <div class="info-item">
                <el-icon><Cpu /></el-icon>
                <span>解析算法: {{ getAlgorithmName(previewData.algorithm_used) }}</span>
              </div>
              <div class="info-item">
                <el-icon><Document /></el-icon>
                <span>命名标准: {{ getStandardName(previewData.naming_standard) }}</span>
              </div>
              <div class="info-item">
                <el-icon><Timer /></el-icon>
                <span>分析耗时: {{ previewData.analysis_time }}s</span>
              </div>
            </div>
            <div class="summary-actions">
              <el-button type="info" size="small" @click="exportPreview">
                <el-icon><Download /></el-icon>
                导出预览
              </el-button>
              <el-button type="warning" size="small" @click="refreshPreview">
                <el-icon><Refresh /></el-icon>
                重新分析
              </el-button>
            </div>
          </div>

          <!-- File List Controls -->
          <div class="list-controls">
            <div class="controls-left">
              <el-checkbox v-model="selectAll" @change="handleSelectAll">
                全选 ({{ selectedItems.length }}/{{ previewData.items.length }})
              </el-checkbox>
              <el-button 
                type="primary" 
                size="small" 
                @click="confirmSelected"
                :disabled="selectedItems.length === 0"
              >
                <el-icon><Check /></el-icon>
                批量确认
              </el-button>
              <el-button 
                type="warning" 
                size="small" 
                @click="editSelected"
                :disabled="selectedItems.length === 0"
              >
                <el-icon><Edit /></el-icon>
                批量编辑
              </el-button>
            </div>
            <div class="controls-right">
              <el-input
                v-model="searchKeyword"
                placeholder="搜索文件名..."
                size="small"
                style="width: 200px;"
                clearable
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
              <el-select v-model="filterType" size="small" style="width: 120px;">
                <el-option label="全部文件" value="all" />
                <el-option label="待确认" value="pending" />
                <el-option label="已确认" value="confirmed" />
                <el-option label="已匹配" value="matched" />
                <el-option label="高置信度" value="high_confidence" />
                <el-option label="低置信度" value="low_confidence" />
              </el-select>
              <el-select v-model="sortBy" size="small" style="width: 140px;">
                <el-option label="按文件名排序" value="filename" />
                <el-option label="按置信度排序" value="confidence" />
                <el-option label="按文件类型排序" value="type" />
                <el-option label="按状态排序" value="status" />
              </el-select>
            </div>
          </div>

          <!-- File List -->
          <div class="file-list" v-if="previewData && previewData.items.length > 0">
            <div class="list-container">
              <div
                v-for="item in filteredItems"
                :key="item.original_path"
                class="file-item"
                :class="{
                  'needs-confirmation': item.needs_confirmation,
                  'selected': selectedItems.includes(item.original_path),
                  'high-confidence': item.overall_confidence >= 0.9,
                  'medium-confidence': item.overall_confidence >= 0.6 && item.overall_confidence < 0.9,
                  'low-confidence': item.overall_confidence < 0.6
                }"
              >
                <div class="item-header">
                  <el-checkbox
                    v-model="selectedItems"
                    :label="item.original_path"
                    class="item-checkbox"
                  />
                  <div class="item-info">
                    <div class="file-type">
                      <el-tag size="small" :type="getMediaTypeColor(item.media_type)">
                        {{ getMediaTypeLabel(item.media_type) }}
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
                  <div class="item-status">
                    <el-tag 
                      v-if="item.needs_confirmation" 
                      type="warning" 
                      size="small" 
                      effect="dark"
                    >
                      <el-icon><Warning /></el-icon>
                      需确认
                    </el-tag>
                    <el-tag 
                      v-else-if="item.tmdb_id" 
                      type="success" 
                      size="small" 
                      effect="dark"
                    >
                      <el-icon><Check /></el-icon>
                      已匹配
                    </el-tag>
                    <el-tag v-else type="info" size="small" effect="plain">
                      未匹配
                    </el-tag>
                  </div>
                </div>

                <div class="item-content">
                  <div class="file-preview">
                    <div class="original-file">
                      <div class="file-label">
                        <el-icon><Document /></el-icon>
                        原文件名
                      </div>
                      <div class="file-path" :title="item.original_path">
                        {{ getFileName(item.original_path) }}
                      </div>
                    </div>
                    <el-icon class="arrow-icon"><ArrowRight /></el-icon>
                    <div class="new-file">
                      <div class="file-label">
                        <el-icon><DocumentChecked /></el-icon>
                        新文件名
                      </div>
                      <div class="file-path" :title="item.new_name">
                        {{ item.new_name }}
                      </div>
                    </div>
                  </div>

                  <div class="media-details">
                    <div class="details-grid">
                      <div class="detail-item" v-if="item.tmdb_title">
                        <span class="detail-label">标题:</span>
                        <span class="detail-value">{{ item.tmdb_title }}</span>
                      </div>
                      <div class="detail-item" v-if="item.tmdb_year">
                        <span class="detail-label">年份:</span>
                        <span class="detail-value">{{ item.tmdb_year }}</span>
                      </div>
                      <div class="detail-item" v-if="item.season !== undefined">
                        <span class="detail-label">季度:</span>
                        <span class="detail-value">S{{ String(item.season).padStart(2, '0') }}</span>
                      </div>
                      <div class="detail-item" v-if="item.episode !== undefined">
                        <span class="detail-label">集数:</span>
                        <span class="detail-value">E{{ String(item.episode).padStart(2, '0') }}</span>
                      </div>
                      <div class="detail-item" v-if="item.tmdb_id">
                        <span class="detail-label">TMDB ID:</span>
                        <span class="detail-value">{{ item.tmdb_id }}</span>
                      </div>
                      <div class="detail-item">
                        <span class="detail-label">解析算法:</span>
                        <span class="detail-value">{{ getAlgorithmShortName(item.used_algorithm) }}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="item-actions">
                  <el-button
                    type="primary"
                    size="small"
                    @click="editItem(item)"
                    class="action-btn"
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

    <!-- Quark File Browser -->
    <QuarkFileBrowser
      v-model="showQuarkBrowser"
      @select="handleCloudFolderSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
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
import {
  smartRenameCloudFiles,
  executeCloudRename,
  type QuarkRenameItem
} from '@/api/quark'
import QuarkFileBrowser from '@/components/QuarkFileBrowser.vue'

// State
const currentStep = ref(1)
const selectedPath = ref('')
const analyzing = ref(false)
const executing = ref(false)
const selectAll = ref(false)
const filterType = ref<'all' | 'pending' | 'confirmed' | 'matched' | 'high_confidence' | 'low_confidence'>('all')
const sortBy = ref<'filename' | 'confidence' | 'type' | 'status'>('filename')
const searchKeyword = ref('')

// 云盘模式状态
const isCloudMode = ref(false)
const selectedCloudFid = ref('')
const showQuarkBrowser = ref(false)

const selectedAlgorithm = ref('ai_enhanced')
const selectedStandard = ref('emby')

const algorithms = ref<AlgorithmInfo[]>([])
const namingStandards = ref<NamingStandardInfo[]>([])

const options = reactive({
  recursive: true,
  createFolders: true,
  autoConfirm: false,
  includeQuality: false,
  includeSource: false,
  includeTmdbId: false,
  backupBeforeRename: false,
  dryRun: false,
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
  average_confidence?: number
  algorithm_used: string
  naming_standard: string
  analysis_time?: number
} | null>(null)

const selectedItems = ref<string[]>([])

// Edit dialog
const editDialogVisible = ref(false)
const editingItem = reactive<Partial<SmartRenameItem>>({})

// Settings
const showSettings = ref(false)
const showHelp = ref(false)
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

  if (searchKeyword.value.trim()) {
    const keyword = searchKeyword.value.trim().toLowerCase()
    items = items.filter((item) => {
      const original = (item.original_name || item.original_path || '').toLowerCase()
      const renamed = (item.new_name || '').toLowerCase()
      return original.includes(keyword) || renamed.includes(keyword)
    })
  }

  if (filterType.value === 'pending') {
    items = items.filter(i => i.needs_confirmation)
  } else if (filterType.value === 'confirmed') {
    items = items.filter(i => !i.needs_confirmation)
  } else if (filterType.value === 'matched') {
    items = items.filter(i => i.tmdb_id)
  } else if (filterType.value === 'high_confidence') {
    items = items.filter(i => (i.overall_confidence || 0) >= 0.9)
  } else if (filterType.value === 'low_confidence') {
    items = items.filter(i => (i.overall_confidence || 0) < 0.6)
  }

  const sortedItems = [...items]
  if (sortBy.value === 'confidence') {
    sortedItems.sort((a, b) => (b.overall_confidence || 0) - (a.overall_confidence || 0))
  } else if (sortBy.value === 'type') {
    sortedItems.sort((a, b) => (a.media_type || '').localeCompare(b.media_type || ''))
  } else if (sortBy.value === 'status') {
    sortedItems.sort((a, b) => Number(Boolean(a.needs_confirmation)) - Number(Boolean(b.needs_confirmation)))
  } else {
    sortedItems.sort((a, b) => (a.original_name || a.original_path).localeCompare(b.original_name || b.original_path))
  }

  return sortedItems
})

/**
 * 进度条宽度
 *
 * 用途: 根据当前步骤计算进度条宽度百分比
 * 输入: 无
 * 输出: 宽度百分比字符串
 * 副作用: 无
 */
const progressWidth = computed(() => {
  const stepPercentages = ['0%', '50%', '100%']
  return stepPercentages[currentStep.value - 1] || '0%'
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

/**
 * 打开路径选择器
 *
 * 用途: 显示模式选择对话框，让用户选择夸克云盘或本地文件
 * 输入: 无
 * 输出: 无
 * 副作用: 根据用户选择显示文件浏览器或提示信息
 */
const openPathSelector = () => {
  // 显示模式选择
  ElMessageBox.confirm(
    '请选择文件来源',
    '选择模式',
    {
      distinguishCancelAndClose: true,
      confirmButtonText: '夸克云盘',
      cancelButtonText: '本地文件',
      type: 'info'
    }
  ).then(() => {
    // 选择夸克云盘
    isCloudMode.value = true
    showQuarkBrowser.value = true
  }).catch((action) => {
    if (action === 'cancel') {
      // 选择本地文件
      isCloudMode.value = false
      ElMessage.info('本地文件浏览功能开发中')
      // 临时设置一个测试路径
      selectedPath.value = '/media/movies'
    }
  })
}

/**
 * 处理云盘文件夹选择
 *
 * 用途: 当用户在 QuarkFileBrowser 中选择文件夹后调用
 * 输入:
 *   - fid: 选中的文件夹ID
 *   - path: 文件夹路径
 * 输出: 无
 * 副作用: 更新选中路径和云盘文件夹ID
 */
const handleCloudFolderSelect = (fid: string, path: string) => {
  selectedCloudFid.value = fid
  selectedPath.value = `夸克云盘: ${path}`
  ElMessage.success('已选择云盘文件夹')
}

/**
 * 重置选择
 *
 * 用途: 清除当前选择的路径和相关状态
 * 输入: 无
 * 输出: 无
 * 副作用: 重置路径、云盘文件夹ID和步骤状态
 */
const resetSelection = () => {
  selectedPath.value = ''
  selectedCloudFid.value = ''
  isCloudMode.value = false
  currentStep.value = 1
  previewData.value = null
  selectedItems.value = []
  ElMessage.info('已重置选择')
}

/**
 * 开始分析
 *
 * 用途: 根据选择的模式（本地/云盘）执行智能重命名预览
 * 输入: 无
 * 输出: 无
 * 副作用: 调用 API 获取预览结果
 */
const startAnalysis = async () => {
  if (!selectedPath.value) {
    ElMessage.warning('请先选择文件夹')
    return
  }

  analyzing.value = true
  currentStep.value = 2

  try {
    if (isCloudMode.value) {
      // 云盘模式
      const response = await smartRenameCloudFiles({
        pdir_fid: selectedCloudFid.value,
        algorithm: selectedAlgorithm.value as any,
        naming_standard: selectedStandard.value as any,
        force_ai_parse: false,
        options: {
          recursive: options.recursive,
          create_folders: options.createFolders,
          auto_confirm_high_confidence: options.autoConfirm,
          ai_confidence_threshold: options.aiThreshold / 100
        }
      })

      // 转换云盘响应格式为本地格式
      previewData.value = {
        batch_id: response.batch_id,
        items: response.items.map((item: QuarkRenameItem) => ({
          original_path: item.fid,
          original_name: item.original_name,
          new_name: item.new_name,
          tmdb_id: item.tmdb_id,
          tmdb_title: item.tmdb_title,
          tmdb_year: item.tmdb_year,
          media_type: item.media_type,
          season: item.season,
          episode: item.episode,
          overall_confidence: item.overall_confidence,
          used_algorithm: item.used_algorithm,
          needs_confirmation: item.needs_confirmation,
          status: item.status
        })),
        total_items: response.total_items,
        matched_items: response.matched_items,
        needs_confirmation: response.needs_confirmation,
        algorithm_used: response.algorithm_used,
        naming_standard: response.naming_standard,
        analysis_time: 0 // 云盘模式暂不返回分析时间
      }

      // Auto-select all items (使用 fid 作为标识)
      selectedItems.value = response.items.map((i: QuarkRenameItem) => i.fid)

      ElMessage.success(`分析完成，共发现 ${response.total_items} 个媒体文件`)
    } else {
      // 本地模式
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
    }
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

const confirmSelected = () => {
  if (!previewData.value || selectedItems.value.length === 0) return
  const selectedSet = new Set(selectedItems.value)
  previewData.value.items = previewData.value.items.map((item) =>
    selectedSet.has(item.original_path) ? { ...item, needs_confirmation: false } : item
  )
  ElMessage.success(`已确认 ${selectedItems.value.length} 个文件`)
}

const editSelected = () => {
  if (!previewData.value || selectedItems.value.length === 0) return
  if (selectedItems.value.length > 1) {
    ElMessage.info('批量编辑开发中，请先选择单个文件')
    return
  }
  const item = previewData.value.items.find((i) => i.original_path === selectedItems.value[0])
  if (item) {
    editItem(item)
  }
}

const refreshPreview = async () => {
  await startAnalysis()
}

const exportPreview = () => {
  if (!previewData.value) return

  const payload = {
    exported_at: new Date().toISOString(),
    batch_id: previewData.value.batch_id,
    total_items: previewData.value.total_items,
    matched_items: previewData.value.matched_items,
    needs_confirmation: previewData.value.needs_confirmation,
    items: previewData.value.items
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

/**
 * 执行重命名
 *
 * 用途: 根据选择的模式（本地/云盘）执行批量重命名
 * 输入: 无
 * 输出: 无
 * 副作用: 调用 API 执行重命名操作
 */
const executeRename = async () => {
  if (!previewData.value?.batch_id) return

  executing.value = true

  try {
    if (isCloudMode.value) {
      // 云盘模式 - 构建操作列表
      const operations = selectedItems.value.map(fid => {
        const item = previewData.value?.items.find(i => i.original_path === fid)
        return {
          fid: fid,
          new_name: item?.new_name || ''
        }
      }).filter(op => op.new_name)

      const response = await executeCloudRename({
        batch_id: previewData.value.batch_id,
        operations: operations
      })

      executeResult.value = {
        success_items: response.success,
        failed_items: response.failed,
        skipped_items: response.total - response.success - response.failed
      }
      resultDialogVisible.value = true

      if (response.failed === 0) {
        ElMessage.success('所有文件重命名成功')
      } else {
        ElMessage.warning(`${response.failed} 个文件重命名失败`)
      }
    } else {
      // 本地模式
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
  padding: 0 16px 32px;
}

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding: 0 8px;
}

.header-content {
  flex: 1;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.gradient-text {
  background: linear-gradient(135deg, var(--el-color-primary) 0%, var(--el-color-success) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.version-tag {
  font-size: 12px;
}

.page-subtitle {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.header-actions {
  display: flex;
  gap: 12px;
}

/* Configuration Section */
.configuration-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
}

.glass-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  box-shadow: var(--el-box-shadow-light);
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

.card-header h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.help-icon {
  color: var(--el-text-color-secondary);
  cursor: help;
}

.config-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Algorithm Group */
.algorithm-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.algorithm-option {
  padding: 16px;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.algorithm-option:hover {
  background: var(--el-fill-color-light);
}

.algo-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.algo-name {
  font-weight: 600;
  font-size: 14px;
}

.recommend-tag {
  font-size: 12px;
}

.algo-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

.algorithm-details {
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.details-header {
  margin-bottom: 12px;
}

.details-title {
  font-weight: 600;
  font-size: 14px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 8px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.feature-icon {
  color: var(--el-color-success);
  font-size: 12px;
}

/* Standard Group */
.standard-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.standard-option {
  padding: 16px;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.standard-option:hover {
  background: var(--el-fill-color-light);
}

.std-name {
  font-weight: 600;
  font-size: 14px;
  display: block;
  margin-bottom: 2px;
}

.std-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.standard-examples {
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.examples-header {
  margin-bottom: 12px;
}

.examples-title {
  font-weight: 600;
  font-size: 14px;
}

.examples-grid {
  display: grid;
  gap: 12px;
}

.example-card {
  padding: 12px;
  background: var(--el-bg-color);
  border-radius: 6px;
  border: 1px solid var(--el-border-color);
}

.example-type {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--el-text-color-secondary);
}

.example-path {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: var(--el-color-primary);
}

/* Advanced Options */
.options-grid {
  display: grid;
  gap: 20px;
}

.option-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-label {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.option-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-item {
  margin: 0;
}

/* Operation Flow */
.operation-flow {
  max-width: 1200px;
  margin: 0 auto;
}

.step-progress {
  margin-bottom: 32px;
  padding: 0 20px;
}

.progress-bar {
  height: 4px;
  background: var(--el-border-color);
  border-radius: 2px;
  position: relative;
  margin-bottom: 24px;
}

.progress-fill {
  height: 100%;
  background: var(--el-color-primary);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.step-indicators {
  display: flex;
  justify-content: space-between;
}

.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  transition: transform 0.3s ease;
}

.step-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--el-border-color);
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.step-indicator.active .step-circle {
  background: var(--el-color-primary);
  color: white;
}

.step-indicator.completed .step-circle {
  background: var(--el-color-success);
  color: white;
}

.step-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}

.step-indicator.active .step-label,
.step-indicator.completed .step-label {
  color: var(--el-text-color-primary);
}

.step-indicator.active {
  transform: translateY(-2px);
}

/* Step Section */
.step-section {
  margin-bottom: 24px;
  border-radius: 12px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  box-shadow: var(--el-box-shadow-light);
  overflow: hidden;
  transition: all 0.3s ease;
}

.step-section.disabled {
  opacity: 0.6;
  pointer-events: none;
}

.step-section.active {
  box-shadow: var(--el-box-shadow);
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
}

.step-info {
  flex: 1;
}

.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.step-title h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.step-description {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.step-status {
  display: flex;
  gap: 12px;
}

.status-tag {
  font-size: 11px;
  padding: 2px 8px;
}

.step-content {
  padding: 18px 20px 20px;
}

/* Path Selector */
.path-selector {
  margin-bottom: 16px;
}

.selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.selector-label {
  font-weight: 600;
  font-size: 14px;
}

.browse-btn {
  font-size: 13px;
  border-radius: 999px;
}

.path-input {
  font-size: 16px;
}

.step-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  justify-content: flex-end;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color);
}

.action-btn {
  min-width: 120px;
  border-radius: 12px;
  height: 36px;
  padding: 0 16px;
}

/* Preview Results */
.summary-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--el-color-info-light-9);
  border: 1px solid var(--el-color-info-light-8);
  border-radius: 8px;
  margin-bottom: 20px;
}

.summary-info {
  display: flex;
  gap: 24px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}

.summary-actions {
  display: flex;
  gap: 8px;
}

.stats-panel {
  display: flex;
  gap: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
}

.stat-value.success {
  color: var(--el-color-success);
}

.stat-value.warning {
  color: var(--el-color-warning);
}

.stat-value.info {
  color: var(--el-color-info);
}

/* List Controls */
.list-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  margin-bottom: 16px;
}

.controls-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.controls-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* File List */
.file-list {
  max-height: 600px;
  overflow-y: auto;
}

.list-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.file-item {
  padding: 16px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  transition: all 0.2s ease;
}

.file-item:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: var(--el-box-shadow-light);
}

.file-item.selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.file-item.needs-confirmation {
  border-color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
}

:deep(.el-input__wrapper) {
  border-radius: 12px;
  box-shadow: none;
}

.file-item.high-confidence {
  border-left: 4px solid var(--el-color-success);
}

.file-item.medium-confidence {
  border-left: 4px solid var(--el-color-warning);
}

.file-item.low-confidence {
  border-left: 4px solid var(--el-color-danger);
}

.item-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.item-checkbox {
  flex-shrink: 0;
}

.item-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16px;
}

.file-type {
  flex-shrink: 0;
}

.confidence-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-bar {
  width: 80px;
  height: 6px;
  background: var(--el-border-color);
  border-radius: 3px;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.confidence-fill.high {
  background: var(--el-color-success);
}

.confidence-fill.medium {
  background: var(--el-color-warning);
}

.confidence-fill.low {
  background: var(--el-color-danger);
}

.confidence-value {
  font-size: 12px;
  font-weight: 600;
  min-width: 30px;
}

.item-status {
  flex-shrink: 0;
}

.item-content {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 16px;
  align-items: start;
}

.file-preview {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 12px;
  align-items: start;
}

.original-file,
.new-file {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

.file-path {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  word-break: break-all;
}

.arrow-icon {
  color: var(--el-text-color-secondary);
  margin-top: 20px;
}

.media-details {
  grid-column: 1 / -1;
  margin-top: 12px;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 8px;
}

.detail-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.detail-label {
  font-weight: 600;
  color: var(--el-text-color-secondary);
  min-width: 60px;
}

.detail-value {
  color: var(--el-text-color-primary);
}

.item-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.action-btn {
  font-size: 12px;
}

/* Responsive Design */
@media (max-width: 768px) {
  .configuration-section {
    grid-template-columns: 1fr;
  }
  
  .item-content {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  
  .file-preview {
    grid-template-columns: 1fr;
  }
  
  .arrow-icon {
    display: none;
  }
  
  .list-controls {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }
  
  .controls-left,
  .controls-right {
    justify-content: center;
  }
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
