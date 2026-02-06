<template>
  <div class="search-page">
    <!-- Hero Search Section -->
    <div class="search-hero">
      <div class="hero-content">
        <h1 class="hero-title">
          <span class="gradient-text">资源搜索</span>
        </h1>
        <p class="hero-subtitle">搜索全网优质影视资源，一键转存到夸克网盘</p>
        
        <!-- Search Box -->
        <div class="search-box-container">
          <div class="search-box" :class="{ 'focused': isSearchFocused }">
            <el-icon class="search-icon" :size="24"><Search /></el-icon>
            <input
              v-model="searchQuery"
              type="text"
              class="search-input"
              placeholder="搜索电影、电视剧、动漫..."
              @focus="isSearchFocused = true"
              @blur="isSearchFocused = false"
              @keyup.enter="handleSearch"
            />
            <el-button
              type="primary"
              size="large"
              class="search-btn"
              :loading="loading"
              @click="handleSearch"
            >
              搜索
            </el-button>
          </div>
          
          <!-- Quick Tags -->
          <div class="quick-tags">
            <span class="tags-label">热门搜索：</span>
            <el-tag
              v-for="tag in hotTags"
              :key="tag"
              class="quick-tag"
              effect="plain"
              size="small"
              @click="searchQuery = tag; handleSearch()"
            >
              {{ tag }}
            </el-tag>
          </div>
        </div>
      </div>
      
      <!-- Decorative Elements -->
      <div class="hero-decoration">
        <div class="decoration-circle circle-1"></div>
        <div class="decoration-circle circle-2"></div>
        <div class="decoration-circle circle-3"></div>
      </div>
    </div>

    <!-- Results Info Bar -->
    <div class="results-info-bar glass-card" v-show="hasSearched">
      <div class="results-info">
        <el-icon><Collection /></el-icon>
        <span>仅展示夸克网盘资源</span>
      </div>
      <div class="results-sort">
        <span class="sort-label">默认按评分排序</span>
      </div>
    </div>

    <!-- Search Results -->
    <div class="results-section" v-if="hasSearched">
      <div class="results-header">
        <div class="results-info">
          <span class="results-count">找到 <strong>{{ totalResults }}</strong> 个结果</span>
          <span class="results-time">耗时 {{ searchTime }}ms</span>
        </div>
        <div class="view-toggle">
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button value="grid">
              <el-icon><Grid /></el-icon>
            </el-radio-button>
            <el-radio-button value="list">
              <el-icon><List /></el-icon>
            </el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <!-- Grid View -->
      <div v-if="viewMode === 'grid'" class="results-grid">
        <div
          v-for="(item, index) in searchResults"
          :key="item.id"
          class="result-card glass-card"
          :class="{ 'animate-slide-in-up': true }"
          :style="{ animationDelay: `${index * 0.05}s` }"
        >
          <div class="card-header">
            <div class="source-badge" :class="item.source">
              {{ getSourceLabel(item.source) }}
            </div>
            <div class="quality-score" :class="getScoreClass(item.score)">
              {{ (item.score || 0).toFixed(2) }}
            </div>
          </div>
          
          <div class="card-body">
            <h3 class="result-title" :title="item.title">{{ item.title }}</h3>
            <p class="result-content">{{ item.content }}</p>
            
            <div class="result-meta">
              <span v-if="item.channel" class="meta-item">
                <el-icon><Collection /></el-icon>
                {{ item.channel }}
              </span>
              <span v-if="item.pub_date" class="meta-item">
                <el-icon><Calendar /></el-icon>
                {{ formatDate(item.pub_date) }}
              </span>
            </div>
          </div>
          
          <div class="card-footer">
            <div class="cloud-links">
              <el-tooltip
                v-for="link in item.cloud_links.slice(0, 2)"
                :key="link.url"
                :content="link.password ? `密码: ${link.password}` : '点击访问'"
                placement="top"
              >
                <el-button
                  type="primary"
                  size="small"
                  class="link-btn"
                  @click="openCloudLink(link)"
                >
                  <el-icon><Link /></el-icon>
                  {{ getCloudTypeLabel(link.type) }}
                </el-button>
              </el-tooltip>
              <el-dropdown v-if="item.cloud_links.length > 2" trigger="click">
                <el-button type="info" size="small">
                  +{{ item.cloud_links.length - 2 }}
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="link in item.cloud_links.slice(2)"
                      :key="link.url"
                      @click="openCloudLink(link)"
                    >
                      {{ getCloudTypeLabel(link.type) }}
                      <el-tag v-if="link.password" size="small" type="warning">
                        密码: {{ link.password }}
                      </el-tag>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            
            <el-button
              type="success"
              size="small"
              class="save-btn"
              @click="saveToCloud(item)"
            >
              <el-icon><Download /></el-icon>
              转存
            </el-button>
          </div>
        </div>
      </div>

      <!-- List View -->
      <div v-else class="results-list">
        <div
          v-for="(item, index) in searchResults"
          :key="item.id"
          class="result-list-item glass-card"
          :class="{ 'animate-slide-in-up': true }"
          :style="{ animationDelay: `${index * 0.05}s` }"
        >
          <div class="list-item-main">
            <div class="list-item-header">
              <h3 class="list-item-title">{{ item.title }}</h3>
              <div class="list-item-badges">
                <el-tag :type="getSourceType(item.source)" size="small">
                  {{ getSourceLabel(item.source) }}
                </el-tag>
                <el-tag :type="getScoreType(item.score)" size="small">
                  质量: {{ (item.score || 0).toFixed(2) }}
                </el-tag>
              </div>
            </div>
            <p class="list-item-content">{{ item.content }}</p>
            <div class="list-item-meta">
              <span v-if="item.channel"><el-icon><Collection /></el-icon> {{ item.channel }}</span>
              <span v-if="item.pub_date"><el-icon><Calendar /></el-icon> {{ formatDate(item.pub_date) }}</span>
            </div>
          </div>
          <div class="list-item-actions">
            <el-button-group>
              <el-button
                v-for="link in item.cloud_links.slice(0, 2)"
                :key="link.url"
                type="primary"
                @click="openCloudLink(link)"
              >
                <el-icon><Link /></el-icon>
                {{ getCloudTypeLabel(link.type) }}
              </el-button>
            </el-button-group>
            <el-button type="success" @click="saveToCloud(item)">
              <el-icon><Download /></el-icon>
              转存
            </el-button>
          </div>
        </div>
      </div>

      <!-- Load More -->
      <div class="load-more" v-if="hasMore">
        <el-button
          type="primary"
          plain
          size="large"
          :loading="loadingMore"
          @click="loadMore"
        >
          加载更多
        </el-button>
      </div>

      <!-- Empty State -->
      <div v-if="searchResults.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无搜索结果">
          <template #image>
            <div class="empty-icon">
              <el-icon :size="80" color="var(--text-tertiary)"><Search /></el-icon>
            </div>
          </template>
          <p class="empty-hint">尝试使用不同的关键词搜索</p>
        </el-empty>
      </div>
    </div>

    <!-- Initial State -->
    <div v-if="!hasSearched && !loading" class="initial-state">
      <div class="feature-grid">
        <div class="feature-card glass-card">
          <div class="feature-icon primary">
            <el-icon :size="32"><Search /></el-icon>
          </div>
          <h3>全网搜索</h3>
          <p>聚合多个资源站点，一站式搜索全网影视资源</p>
        </div>
        <div class="feature-card glass-card">
          <div class="feature-icon success">
            <el-icon :size="32"><Filter /></el-icon>
          </div>
          <h3>智能筛选</h3>
          <p>基于质量评分和来源可信度，智能过滤低质量资源</p>
        </div>
        <div class="feature-card glass-card">
          <div class="feature-icon warning">
            <el-icon :size="32"><Download /></el-icon>
          </div>
          <h3>一键转存</h3>
          <p>支持夸克、百度、阿里云盘，一键转存到个人网盘</p>
        </div>
        <div class="feature-card glass-card">
          <div class="feature-icon info">
            <el-icon :size="32"><Star /></el-icon>
          </div>
          <h3>收藏管理</h3>
          <p>收藏喜欢的资源，方便后续快速访问和整理</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { AxiosError } from 'axios'
import {
  Search,
  Filter,
  Grid,
  List,
  Collection,
  Calendar,
  Link,
  Download,
  Star
} from '@element-plus/icons-vue'
import { searchResources, type SearchResult } from '@/api/search'
import { listCloudDrives } from '@/api/cloudDrive'
import { transferShare } from '@/api/transfer'

// Search state
const searchQuery = ref('')
const isSearchFocused = ref(false)
const loading = ref(false)
const loadingMore = ref(false)
const hasSearched = ref(false)
const viewMode = ref<'grid' | 'list'>('grid')
const searchResults = ref<SearchResult[]>([])
const totalResults = ref(0)
const searchTime = ref(0)
const hasMore = ref(false)
const currentPage = ref(1)

// 筛选功能已移除，后端固定返回夸克网盘资源并按评分排序

// Hot tags
const hotTags = ['流浪地球', '三体', '狂飙', '奥本海默', '芭比', '封神']

// Handle search
const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }

  loading.value = true
  hasSearched.value = true
  currentPage.value = 1

  const startTime = Date.now()

  try {
    const response = await searchResources({
      keyword: searchQuery.value,
      page: currentPage.value,
      page_size: 20
    })

    searchResults.value = response.results
    totalResults.value = response.total
    hasMore.value = response.has_more
    searchTime.value = Date.now() - startTime
  } catch {
    ElMessage.error('搜索失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// Load more results
const loadMore = async () => {
  loadingMore.value = true
  currentPage.value++

  try {
    const response = await searchResources({
      keyword: searchQuery.value,
      page: currentPage.value,
      page_size: 20
    })

    searchResults.value.push(...response.results)
    hasMore.value = response.has_more
  } catch {
    ElMessage.error('加载更多失败')
  } finally {
    loadingMore.value = false
  }
}



// Open cloud link
const openCloudLink = (link: { url: string; password?: string }) => {
  if (link.password) {
    ElMessageBox.alert(
      `提取密码: ${link.password}`,
      '需要提取密码',
      {
        confirmButtonText: '复制密码并打开',
        callback: () => {
          navigator.clipboard.writeText(link.password || '')
          window.open(link.url, '_blank')
        }
      }
    )
  } else {
    window.open(link.url, '_blank')
  }
}

// Save to cloud
const saveToCloud = async (item: SearchResult) => {
  const quarkLink = item.cloud_links.find((link) => link.type === 'quark')
  if (!quarkLink) {
    ElMessage.error('该资源没有夸克网盘链接')
    return
  }

  try {
    const { value: targetDir } = await ElMessageBox.prompt(
      '请输入转存目录，例如 /电影 或 /电视剧',
      '转存到夸克网盘',
      {
        confirmButtonText: '开始转存',
        cancelButtonText: '取消',
        inputValue: '/',
        inputPlaceholder: '例如 /电影'
      }
    )

    let quarkDriveId: number | undefined
    try {
      const drives = await listCloudDrives()
      const quarkDrive = drives.find((drive) => drive.drive_type === 'quark')
      quarkDriveId = quarkDrive?.id
    } catch {
      quarkDriveId = undefined
    }

    if (!quarkDriveId) {
      ElMessage.info('未检测到夸克账号，将尝试使用系统配置的 quark.cookie 转存')
    }

    const result = await transferShare({
      drive_id: quarkDriveId,
      share_url: quarkLink.url,
      target_dir: (targetDir || '/').trim() || '/',
      password: quarkLink.password || '',
      auto_organize: false
    })

    ElMessage.success(result.message || '转存请求已提交')
  } catch (error: unknown) {
    const action = (error as { action?: string } | null)?.action
    if (action === 'cancel' || action === 'close' || String(error).includes('cancel')) {
      return
    }
    const detail = (error as AxiosError<{ detail?: string }> | null)?.response?.data?.detail
    ElMessage.error(detail || '转存失败，请稍后重试')
  }
}

// Helper functions
const getSourceLabel = (source: string) => {
  const map: Record<string, string> = {
    telegram: 'Telegram',
    wechat: '微信公众号',
    website: '网站',
    api: 'API'
  }
  return map[source] || source
}

const getSourceType = (source: string) => {
  const map: Record<string, string> = {
    telegram: 'primary',
    wechat: 'success',
    website: 'info',
    api: 'warning'
  }
  return map[source] || 'info'
}

const getCloudTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    quark: '夸克',
    baidu: '百度',
    aliyun: '阿里',
    other: '其他'
  }
  return map[type] || type
}

const getScoreClass = (score?: number) => {
  if (!score) return 'score-low'
  if (score >= 80) return 'score-high'
  if (score >= 50) return 'score-medium'
  return 'score-low'
}

const getScoreType = (score?: number) => {
  if (!score) return 'info'
  if (score >= 80) return 'success'
  if (score >= 50) return 'warning'
  return 'info'
}

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.search-page {
  min-height: 100%;
}

/* Hero Section */
.search-hero {
  position: relative;
  padding: 60px 40px;
  background: linear-gradient(135deg, var(--primary-50) 0%, var(--secondary-50) 100%);
  border-radius: var(--radius-2xl);
  margin-bottom: 32px;
  overflow: hidden;
}

:global(html.dark) .search-hero {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
}

.hero-content {
  position: relative;
  z-index: 1;
  max-width: 800px;
  margin: 0 auto;
  text-align: center;
}

.hero-title {
  font-size: 48px;
  font-weight: 800;
  margin-bottom: 16px;
  letter-spacing: -1px;
}

.hero-subtitle {
  font-size: 18px;
  color: var(--text-secondary);
  margin-bottom: 40px;
}

/* Search Box */
.search-box-container {
  max-width: 700px;
  margin: 0 auto;
}

.search-box {
  display: flex;
  align-items: center;
  background: var(--bg-primary);
  border-radius: var(--radius-2xl);
  padding: 8px;
  box-shadow: var(--shadow-lg), 0 0 0 1px var(--border-color);
  transition: all var(--transition-normal);
}

.search-box.focused {
  box-shadow: var(--shadow-xl), 0 0 0 2px var(--primary-500);
  transform: translateY(-2px);
}

.search-icon {
  margin: 0 16px;
  color: var(--text-tertiary);
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 16px;
  padding: 12px 0;
  outline: none;
  color: var(--text-primary);
}

.search-input::placeholder {
  color: var(--text-tertiary);
}

.search-btn {
  border-radius: var(--radius-xl) !important;
  padding: 0 32px !important;
  height: 48px !important;
  font-size: 16px !important;
  font-weight: 600;
}

/* Quick Tags */
.quick-tags {
  margin-top: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
}

.tags-label {
  color: var(--text-secondary);
  font-size: 14px;
}

.quick-tag {
  cursor: pointer;
  transition: all var(--transition-fast);
}

.quick-tag:hover {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

/* Decorative Elements */
.hero-decoration {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  overflow: hidden;
}

.decoration-circle {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary-400), var(--secondary-400));
  opacity: 0.1;
}

.circle-1 {
  width: 300px;
  height: 300px;
  top: -100px;
  right: -50px;
}

.circle-2 {
  width: 200px;
  height: 200px;
  bottom: -50px;
  left: -50px;
}

.circle-3 {
  width: 150px;
  height: 150px;
  top: 50%;
  right: 10%;
  opacity: 0.05;
}

/* Results Info Bar */
.results-info-bar {
  padding: 16px 24px;
  margin-bottom: 24px;
  border-radius: var(--radius-xl);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.results-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-secondary);
}

.results-sort {
  font-size: 14px;
  color: var(--text-tertiary);
}

.sort-label {
  font-weight: 500;
}

/* Results Section */
.results-section {
  animation: fadeIn var(--transition-normal) ease-out;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 0 8px;
}

.results-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.results-count {
  font-size: 16px;
  color: var(--text-secondary);
}

.results-count strong {
  color: var(--primary-500);
  font-size: 20px;
}

.results-time {
  font-size: 14px;
  color: var(--text-tertiary);
}

/* Grid View */
.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
}

.result-card {
  padding: 20px;
  border-radius: var(--radius-xl);
  display: flex;
  flex-direction: column;
  transition: all var(--transition-normal);
}

.result-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-xl);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.source-badge {
  padding: 4px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
}

.source-badge.telegram {
  background: var(--primary-100);
  color: var(--primary-600);
}

.source-badge.wechat {
  background: var(--success-100);
  color: var(--success-600);
}

.source-badge.website {
  background: var(--info-100);
  color: var(--info-600);
}

.source-badge.api {
  background: var(--warning-100);
  color: var(--warning-600);
}

.quality-score {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
}

.score-high {
  background: var(--success-500);
  color: white;
}

.score-medium {
  background: var(--warning-500);
  color: white;
}

.score-low {
  background: var(--gray-300);
  color: var(--gray-600);
}

.card-body {
  flex: 1;
  margin-bottom: 16px;
}

.result-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-content {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 12px;
}

.result-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--text-tertiary);
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.cloud-links {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.link-btn {
  display: flex;
  align-items: center;
  gap: 4px;
}

.save-btn {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* List View */
.results-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 32px;
}

.result-list-item {
  padding: 20px;
  border-radius: var(--radius-xl);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
}

.list-item-main {
  flex: 1;
}

.list-item-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.list-item-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.list-item-badges {
  display: flex;
  gap: 8px;
}

.list-item-content {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.list-item-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-tertiary);
}

.list-item-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.list-item-actions {
  display: flex;
  gap: 12px;
}

/* Load More */
.load-more {
  text-align: center;
  padding: 32px;
}

/* Empty State */
.empty-state {
  padding: 80px 40px;
  text-align: center;
}

.empty-icon {
  margin-bottom: 24px;
}

.empty-hint {
  color: var(--text-secondary);
  margin-top: 16px;
}

/* Initial State */
.initial-state {
  padding: 40px 0;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 24px;
}

.feature-card {
  padding: 32px 24px;
  text-align: center;
  border-radius: var(--radius-xl);
  transition: all var(--transition-normal);
}

.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-xl);
}

.feature-icon {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  color: white;
}

.feature-icon.primary {
  background: linear-gradient(135deg, var(--primary-500), var(--primary-600));
}

.feature-icon.success {
  background: linear-gradient(135deg, var(--success-500), var(--success-600));
}

.feature-icon.warning {
  background: linear-gradient(135deg, var(--warning-500), var(--warning-600));
}

.feature-icon.info {
  background: linear-gradient(135deg, var(--info-500), var(--info-600));
}

.feature-card h3 {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text-primary);
}

.feature-card p {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* Responsive */
@media (max-width: 768px) {
  .search-hero {
    padding: 40px 20px;
  }

  .hero-title {
    font-size: 32px;
  }

  .hero-subtitle {
    font-size: 16px;
  }

  .search-box {
    flex-direction: column;
    gap: 8px;
  }

  .search-input {
    width: 100%;
    text-align: center;
  }

  .search-btn {
    width: 100%;
  }

  .results-grid {
    grid-template-columns: 1fr;
  }

  .result-list-item {
    flex-direction: column;
    align-items: flex-start;
  }

  .list-item-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .results-info-bar {
    flex-direction: column;
    gap: 8px;
    text-align: center;
  }
}
</style>
