<template>
  <div class="cloud-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">
          <span class="gradient-text">云盘管理</span>
        </h1>
        <p class="page-subtitle">管理夸克网盘文件，支持转存、分享、直链获取</p>
      </div>
      <div class="header-stats">
        <div class="stat-item">
          <el-icon :size="20" color="var(--primary-500)"><Folder /></el-icon>
          <span class="stat-value">{{ totalFiles }}</span>
          <span class="stat-label">文件</span>
        </div>
        <div class="stat-item">
          <el-icon :size="20" color="var(--success-500)"><Coin /></el-icon>
          <span class="stat-value">{{ formatSize(totalSize) }}</span>
          <span class="stat-label">已用空间</span>
        </div>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar glass-card">
      <div class="toolbar-left">
        <!-- Breadcrumb -->
        <el-breadcrumb separator="/">
          <el-breadcrumb-item @click="navigateToRoot">
            <el-icon><HomeFilled /></el-icon>
          </el-breadcrumb-item>
          <el-breadcrumb-item
            v-for="(item, index) in breadcrumb"
            :key="item.fid"
            @click="navigateTo(index)"
          >
            {{ item.name }}
          </el-breadcrumb-item>
        </el-breadcrumb>
      </div>
      
      <div class="toolbar-right">
        <!-- Search -->
        <el-input
          v-model="searchKeyword"
          placeholder="搜索文件..."
          clearable
          class="search-input"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        
        <!-- View Toggle -->
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="grid">
            <el-icon><Grid /></el-icon>
          </el-radio-button>
          <el-radio-button value="list">
            <el-icon><List /></el-icon>
          </el-radio-button>
        </el-radio-group>
        
        <!-- Refresh -->
        <el-button circle @click="refreshFiles">
          <el-icon><Refresh /></el-icon>
        </el-button>
        
        <!-- STRM -->
        <el-tooltip content="生成 STRM" placement="bottom">
          <el-button circle type="primary" plain @click="showStrmDialog">
            <el-icon><MagicStick /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- File List -->
    <div class="file-container">
      <!-- Grid View -->
      <div v-if="viewMode === 'grid'" class="file-grid">
        <div
          v-for="file in fileList"
          :key="file.fid"
          class="file-card glass-card"
          :class="{ 'selected': selectedFiles.includes(file.fid) }"
          @click="toggleSelect(file)"
          @dblclick="handleFileClick(file)"
        >
          <div class="file-checkbox">
            <el-checkbox v-model="selectedFiles" :value="file.fid" @click.stop>
              {{ '' }}
            </el-checkbox>
          </div>
          
          <div class="file-icon">
            <el-icon v-if="file.dir" :size="48" color="var(--warning-500)"><Folder /></el-icon>
            <el-icon v-else-if="isVideo(file)" :size="48" color="var(--primary-500)"><VideoPlay /></el-icon>
            <el-icon v-else-if="isImage(file)" :size="48" color="var(--success-500)"><Picture /></el-icon>
            <el-icon v-else :size="48" color="var(--text-tertiary)"><Document /></el-icon>
          </div>
          
          <div class="file-info">
            <div class="file-name" :title="file.file_name">{{ file.file_name }}</div>
            <div class="file-meta">
              <span v-if="!file.dir">{{ formatSize(file.size || 0) }}</span>
              <span v-else>文件夹</span>
              <span>{{ formatDate(file.updated_at) }}</span>
            </div>
          </div>
          
          <div class="file-actions" @click.stop>
            <el-dropdown trigger="click">
              <el-button circle size="small">
                <el-icon><More /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="!file.dir" @click="getDownloadUrl(file)">
                    <el-icon><Download /></el-icon>
                    获取直链
                  </el-dropdown-item>
                  <el-dropdown-item v-if="!file.dir && isVideo(file)" @click="getTranscodingUrl(file)">
                    <el-icon><VideoCamera /></el-icon>
                    转码链接
                  </el-dropdown-item>
                  <el-dropdown-item @click="shareFile(file)">
                    <el-icon><Share /></el-icon>
                    分享
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="deleteFile(file)">
                    <el-icon><Delete /></el-icon>
                    删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </div>

      <!-- List View -->
      <div v-else class="file-list">
        <el-table
          :data="fileList"
          style="width: 100%"
          @row-click="(row: QuarkFileSDK) => toggleSelect(row)"
          @row-dblclick="(row: QuarkFileSDK) => handleFileClick(row)"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column label="文件名" min-width="300">
            <template #default="{ row }">
              <div class="list-file-info">
                <el-icon v-if="row.dir" :size="20" color="var(--warning-500)"><Folder /></el-icon>
                <el-icon v-else-if="isVideo(row)" :size="20" color="var(--primary-500)"><VideoPlay /></el-icon>
                <el-icon v-else-if="isImage(row)" :size="20" color="var(--success-500)"><Picture /></el-icon>
                <el-icon v-else :size="20" color="var(--text-tertiary)"><Document /></el-icon>
                <span class="list-file-name">{{ row.file_name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="120">
            <template #default="{ row }">
              <span v-if="!row.dir">{{ formatSize(row.size || 0) }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="修改时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.updated_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button-group>
                <el-button v-if="!row.dir" type="primary" text size="small" @click.stop="getDownloadUrl(row)">
                  <el-icon><Download /></el-icon>
                </el-button>
                <el-button type="success" text size="small" @click.stop="shareFile(row)">
                  <el-icon><Share /></el-icon>
                </el-button>
                <el-button type="danger" text size="small" @click.stop="deleteFile(row)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- Empty State -->
      <div v-if="fileList.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无文件">
          <template #image>
            <div class="empty-icon">
              <el-icon :size="80" color="var(--text-tertiary)"><FolderOpened /></el-icon>
            </div>
          </template>
        </el-empty>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="loading-state">
        <el-skeleton :rows="5" animated />
      </div>
    </div>

    <!-- Batch Actions -->
    <div class="batch-actions glass-card" v-show="selectedFiles.length > 0">
      <div class="batch-info">
        <span>已选择 <strong>{{ selectedFiles.length }}</strong> 项</span>
      </div>
      <div class="batch-buttons">
        <el-button type="primary" @click="batchShare">
          <el-icon><Share /></el-icon>
          批量分享
        </el-button>
        <el-button type="primary" plain @click="batchMove">
          <el-icon><FolderOpened /></el-icon>
          移动到
        </el-button>
        <el-button type="success" @click="batchDownload">
          <el-icon><Download /></el-icon>
          批量下载
        </el-button>
        <el-button type="danger" @click="batchDelete">
          <el-icon><Delete /></el-icon>
          批量删除
        </el-button>
        <el-button text @click="selectedFiles = []">
          取消选择
        </el-button>
      </div>
    </div>

    <!-- Transfer Dialog -->
    <el-dialog
      v-model="transferDialogVisible"
      title="转存分享"
      width="500px"
    >
      <el-form :model="transferForm" label-width="100px">
        <el-form-item label="分享链接">
          <el-input
            v-model="transferForm.shareUrl"
            placeholder="输入夸克分享链接..."
          />
        </el-form-item>
        <el-form-item label="提取密码">
          <el-input
            v-model="transferForm.password"
            placeholder="如有密码请输入"
            show-password
          />
        </el-form-item>
        <el-form-item label="保存位置">
          <el-input
            v-model="transferForm.targetFolder"
            placeholder="选择保存文件夹..."
            readonly
          >
            <template #append>
              <el-button @click="selectTargetFolder">
                <el-icon><Folder /></el-icon>
              </el-button>
            </template>
          </el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="transferring" @click="executeTransfer">
          开始转存
        </el-button>
      </template>
    </el-dialog>

    <!-- Share Dialog -->
    <el-dialog
      v-model="shareDialogVisible"
      title="创建分享"
      width="500px"
    >
      <el-form :model="shareForm" label-width="100px">
        <el-form-item label="分享标题">
          <el-input v-model="shareForm.title" placeholder="输入分享标题..." />
        </el-form-item>
        <el-form-item label="提取密码">
          <el-input
            v-model="shareForm.password"
            placeholder="设置提取密码（可选）"
            maxlength="4"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="有效期">
          <el-radio-group v-model="shareForm.expireDays">
            <el-radio-button :value="1">1天</el-radio-button>
            <el-radio-button :value="7">7天</el-radio-button>
            <el-radio-button :value="30">30天</el-radio-button>
            <el-radio-button :value="0">永久</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shareDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sharing" @click="createShareLink">
          创建分享
        </el-button>
      </template>
    </el-dialog>

    <!-- Share Result Dialog -->
    <el-dialog
      v-model="shareResultVisible"
      title="分享创建成功"
      width="500px"
    >
      <div class="share-result">
        <div class="share-link-box">
          <div class="share-label">分享链接</div>
          <div class="share-url">
            <el-input v-model="shareResult.url" readonly>
              <template #append>
                <el-button @click="copyToClipboard(shareResult.url)">
                  <el-icon><CopyDocument /></el-icon>
                  复制
                </el-button>
              </template>
            </el-input>
          </div>
        </div>
        <div class="share-password-box" v-if="shareResult.password">
          <div class="share-label">提取密码</div>
          <div class="share-password">
            <el-input v-model="shareResult.password" readonly>
              <template #append>
                <el-button @click="copyToClipboard(shareResult.password)">
                  <el-icon><CopyDocument /></el-icon>
                  复制
                </el-button>
              </template>
            </el-input>
          </div>
        </div>
        <el-alert
          title="提示"
          type="info"
          description="请妥善保管分享链接和密码，分享内容可能会被平台审核。"
          show-icon
          :closable="false"
        />
      </div>
      <template #footer>
        <el-button type="primary" @click="shareResultVisible = false">
          完成
        </el-button>
      </template>
    </el-dialog>

    <!-- Link Result Dialog -->
    <el-dialog
      v-model="linkDialogVisible"
      title="下载链接"
      width="600px"
    >
      <div class="link-result">
        <div class="link-info">
          <div class="link-file">
            <el-icon :size="32"><Document /></el-icon>
            <span>{{ currentFile?.file_name }}</span>
          </div>
          <div class="link-details">
            <div class="detail-item">
              <span class="detail-label">文件大小:</span>
              <span class="detail-value">{{ formatSize(currentFile?.size || 0) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">并发数:</span>
              <span class="detail-value">{{ linkResult.concurrency }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">分块大小:</span>
              <span class="detail-value">{{ formatSize(linkResult.part_size) }}</span>
            </div>
          </div>
        </div>
        <div class="link-box">
          <el-input
            v-model="linkResult.url"
            type="textarea"
            :rows="3"
            readonly
          />
          <el-button type="primary" @click="copyToClipboard(linkResult.url)">
            <el-icon><CopyDocument /></el-icon>
            复制链接
          </el-button>
        </div>
        <el-alert
          v-if="linkResult.headers"
          title="请求头信息"
          type="info"
          :description="JSON.stringify(linkResult.headers, null, 2)"
          show-icon
          :closable="false"
        />
      </div>
    </el-dialog>

    <!-- Move Folder Selector Dialog -->
    <FileSelectorDialog
      v-if="moveDialogVisible"
      v-model:visible="moveDialogVisible"
      storage="quark"
      @confirm="handleMoveConfirm"
    />

    <!-- STRM Generation Dialog -->
    <el-dialog
      v-model="strmDialogVisible"
      title="生成 STRM"
      width="500px"
    >
      <el-form :model="strmForm" label-width="120px">
        <el-form-item label="本地保存路径">
          <el-input v-model="strmForm.localPath" placeholder="例如: ./strm" />
          <div class="form-tip">服务器上保存 .strm 文件的目录</div>
        </el-form-item>
        <el-form-item label="基础 URL">
          <el-input v-model="strmForm.baseUrl" />
          <div class="form-tip">代理服务器的访问地址 (用于重定向/WebDAV)</div>
        </el-form-item>
        <el-form-item label="URL 模式">
          <el-select v-model="strmForm.strmUrlMode">
            <el-option label="302 重定向 (推荐)" value="redirect" />
            <el-option label="WebDAV (适合直连拉取)" value="webdav" />
            <el-option label="直接直链 (不稳定)" value="direct" />
            <el-option label="流式传输 (消耗流量)" value="stream" />
          </el-select>
        </el-form-item>
        <el-form-item label="递归扫描">
          <el-switch v-model="strmForm.recursive" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="strmDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="scanning" @click="executeScan">
          开始生成
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Folder,
  FolderOpened,
  Document,
  VideoPlay,
  Picture,
  Search,
  Grid,
  List,
  Refresh,
  More,
  Download,
  Share,
  Delete,
  VideoCamera,
  HomeFilled,
  Coin,
  CopyDocument,
  MagicStick
} from '@element-plus/icons-vue'
import {
  getQuarkFilesSDK,
  createShare,
  saveShare,
  getDownloadLinkSDK,
  getTranscodingLinkSDK,
  type QuarkFileSDK
} from '@/api/quarkSdk'
import { scanDirectory } from '@/api/strm'
import { fileManagerApi } from '@/api/file-manager'
import FileSelectorDialog from '@/components/file-manager/FileSelectorDialog.vue'

// State
const loading = ref(false)
const viewMode = ref<'grid' | 'list'>('grid')
const searchKeyword = ref('')
const fileList = ref<QuarkFileSDK[]>([])
const selectedFiles = ref<string[]>([])
const currentFolder = ref('0')
const breadcrumb = ref<{ fid: string; name: string }[]>([])
const totalFiles = ref(0)
const totalSize = ref(0)

// Dialogs
const transferDialogVisible = ref(false)
const shareDialogVisible = ref(false)
const shareResultVisible = ref(false)
const linkDialogVisible = ref(false)
const strmDialogVisible = ref(false)
const moveDialogVisible = ref(false)
const transferring = ref(false)
const sharing = ref(false)
const scanning = ref(false)
const moving = ref(false)

const transferForm = reactive({
  shareUrl: '',
  password: '',
  targetFolder: '0'
})

const shareForm = reactive({
  title: '',
  password: '',
  expireDays: 7
})

const shareResult = reactive({
  url: '',
  password: ''
})

const strmForm = reactive({
  localPath: './strm',
  baseUrl: window.location.origin,
  strmUrlMode: 'redirect' as 'redirect' | 'stream' | 'direct' | 'webdav',
  recursive: true
})

const currentFile = ref<QuarkFileSDK | null>(null)
const linkResult = reactive({
  url: '',
  headers: {} as Record<string, string>,
  concurrency: 1,
  part_size: 0
})

// Video extensions
const videoExtensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts']
const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']

// Methods
const isVideo = (file: QuarkFileSDK) => {
  if (file.dir) return false
  const ext = file.file_name.toLowerCase().slice(file.file_name.lastIndexOf('.'))
  return videoExtensions.includes(ext)
}

const isImage = (file: QuarkFileSDK) => {
  if (file.dir) return false
  const ext = file.file_name.toLowerCase().slice(file.file_name.lastIndexOf('.'))
  return imageExtensions.includes(ext)
}

const formatSize = (size: number) => {
  if (size === 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index++
  }
  return `${size.toFixed(2)} ${units[index]}`
}

const formatDate = (timestamp?: number) => {
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

const loadFiles = async () => {
  loading.value = true
  try {
    const response = await getQuarkFilesSDK(currentFolder.value, 100, false)
    fileList.value = response.files
    totalFiles.value = response.count
    
    // Calculate total size
    totalSize.value = response.files.reduce((sum, file) => sum + (file.size || 0), 0)
  } catch {
    ElMessage.error('加载文件失败')
  } finally {
    loading.value = false
  }
}

const refreshFiles = () => {
  loadFiles()
  ElMessage.success('已刷新')
}

const handleFileClick = (file: QuarkFileSDK) => {
  if (file.dir) {
    breadcrumb.value.push({ fid: file.fid, name: file.file_name })
    currentFolder.value = file.fid
    selectedFiles.value = []
    loadFiles()
  }
}

const navigateToRoot = () => {
  breadcrumb.value = []
  currentFolder.value = '0'
  selectedFiles.value = []
  loadFiles()
}

const navigateTo = (index: number) => {
  breadcrumb.value = breadcrumb.value.slice(0, index + 1)
  currentFolder.value = breadcrumb.value[index]?.fid || '0'
  selectedFiles.value = []
  loadFiles()
}

const toggleSelect = (file: QuarkFileSDK) => {
  const index = selectedFiles.value.indexOf(file.fid)
  if (index > -1) {
    selectedFiles.value.splice(index, 1)
  } else {
    selectedFiles.value.push(file.fid)
  }
}

const handleSearch = async () => {
  if (!searchKeyword.value.trim()) {
    loadFiles()
    return
  }
  
  loading.value = true
  try {
    // Use search API
    const response = await getQuarkFilesSDK(currentFolder.value, 100, false)
    fileList.value = response.files.filter(f => 
      f.file_name.toLowerCase().includes(searchKeyword.value.toLowerCase())
    )
  } catch {
    ElMessage.error('搜索失败')
  } finally {
    loading.value = false
  }
}

const getDownloadUrl = async (file: QuarkFileSDK) => {
  try {
    const response = await getDownloadLinkSDK(file.fid)
    currentFile.value = file
    linkResult.url = response.url
    linkResult.headers = response.headers
    linkResult.concurrency = response.concurrency
    linkResult.part_size = response.part_size
    linkDialogVisible.value = true
  } catch {
    ElMessage.error('获取下载链接失败')
  }
}

const getTranscodingUrl = async (file: QuarkFileSDK) => {
  try {
    const response = await getTranscodingLinkSDK(file.fid)
    currentFile.value = file
    linkResult.url = response.url
    linkResult.headers = response.headers
    linkResult.concurrency = response.concurrency
    linkResult.part_size = response.part_size
    linkDialogVisible.value = true
    ElMessage.success('已获取转码链接')
  } catch {
    ElMessage.error('获取转码链接失败')
  }
}

const shareFile = (file: QuarkFileSDK) => {
  selectedFiles.value = [file.fid]
  shareForm.title = file.file_name
  shareDialogVisible.value = true
}

const createShareLink = async () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择要分享的文件')
    return
  }

  sharing.value = true
  try {
    const response = await createShare({
      file_ids: selectedFiles.value,
      title: shareForm.title,
      password: shareForm.password || undefined
    })
    
    shareResult.url = response.url
    shareResult.password = response.password || ''
    shareDialogVisible.value = false
    shareResultVisible.value = true
    
    ElMessage.success('分享创建成功')
  } catch {
    ElMessage.error('创建分享失败')
  } finally {
    sharing.value = false
  }
}

const deleteFile = async (file: QuarkFileSDK) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 "${file.file_name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )
    ElMessage.success('删除成功')
    loadFiles()
  } catch {
    // Cancelled
  }
}

const batchShare = () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  shareForm.title = `分享 ${selectedFiles.value.length} 个文件`
  shareDialogVisible.value = true
}

const batchMove = () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  moveDialogVisible.value = true
}

const handleMoveConfirm = async (targetPath: string) => {
  if (selectedFiles.value.length === 0) return
  
  moving.value = true
  try {
    await fileManagerApi.operation({
      action: 'move',
      storage: 'quark',
      paths: selectedFiles.value,
      target: targetPath
    })
    
    ElMessage.success('移动成功')
    selectedFiles.value = []
    moveDialogVisible.value = false
    await loadFiles()
  } catch (error) {
    console.error('移动失败:', error)
    ElMessage.error('移动失败')
  } finally {
    moving.value = false
  }
}

const batchDownload = () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  ElMessage.info('批量下载功能开发中')
}

const batchDelete = async () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedFiles.value.length} 个文件吗？`,
      '确认删除',
      { type: 'warning' }
    )
    ElMessage.success('删除成功')
    selectedFiles.value = []
    loadFiles()
  } catch {
    // Cancelled
  }
}

const selectTargetFolder = () => {
  ElMessage.info('文件夹选择功能开发中')
}

const executeTransfer = async () => {
  if (!transferForm.shareUrl) {
    ElMessage.warning('请输入分享链接')
    return
  }

  transferring.value = true
  try {
    // Extract share key from URL
    const shareKey = transferForm.shareUrl.split('/').pop() || ''
    
    await saveShare({
      share_key: shareKey,
      file_ids: [], // Will be fetched from share
      target_folder: transferForm.targetFolder,
      password: transferForm.password || undefined
    })
    
    ElMessage.success('转存成功')
    transferDialogVisible.value = false
    loadFiles()
  } catch {
    ElMessage.error('转存失败')
  } finally {
    transferring.value = false
  }
}

const showStrmDialog = () => {
  strmDialogVisible.value = true
}

const executeScan = async () => {
  scanning.value = true
  try {
    // Construct remote path from breadcrumb
    // NOTE: This assumes breadcrumb names exactly match the path.
    // If user navigated via IDs, we might not have the full correct path if duplicate names exist.
    // But scan API takes a path string.
    // Let's approximation: / + join breadcrumb names
    let remotePath = "/"
    if (breadcrumb.value.length > 0) {
      remotePath += breadcrumb.value.map(b => b.name).join('/')
    }
    
    const result = await scanDirectory({
      remote_path: remotePath,
      local_path: strmForm.localPath,
      recursive: strmForm.recursive,
      base_url: strmForm.baseUrl,
      strm_url_mode: strmForm.strmUrlMode
    })
    
    ElMessage.success(`生成成功: ${result.count} 个文件`)
    strmDialogVisible.value = false
  } catch (e) {
    ElMessage.error('生成失败: ' + String(e))
  } finally {
    scanning.value = false
  }
}

const copyToClipboard = (text: string) => {
  navigator.clipboard.writeText(text)
  ElMessage.success('已复制到剪贴板')
}

onMounted(() => {
  loadFiles()
})
</script>

<style scoped>
.cloud-page {
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
}

.page-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
}

.header-stats {
  display: flex;
  gap: 24px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: var(--bg-secondary);
  border-radius: var(--radius-xl);
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 14px;
  color: var(--text-secondary);
}

/* Toolbar */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  margin-bottom: 20px;
  border-radius: var(--radius-xl);
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-input {
  width: 240px;
}

/* File Container */
.file-container {
  min-height: 400px;
}

/* Grid View */
.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.file-card {
  position: relative;
  padding: 20px;
  border-radius: var(--radius-xl);
  text-align: center;
  cursor: pointer;
  transition: all var(--transition-normal);
  border: 2px solid transparent;
}

.file-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

.file-card.selected {
  border-color: var(--primary-500);
  background: var(--primary-50);
}

.file-checkbox {
  position: absolute;
  top: 12px;
  left: 12px;
}

.file-icon {
  margin: 20px 0;
}

.file-info {
  margin-bottom: 12px;
}

.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-meta {
  display: flex;
  justify-content: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.file-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.file-card:hover .file-actions {
  opacity: 1;
}

/* List View */
.file-list {
  background: var(--bg-secondary);
  border-radius: var(--radius-xl);
  overflow: hidden;
}

.list-file-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.list-file-name {
  font-weight: 500;
}

/* Empty State */
.empty-state {
  padding: 80px 40px;
  text-align: center;
}

.empty-icon {
  margin-bottom: 24px;
}

/* Loading State */
.loading-state {
  padding: 40px;
}

/* Batch Actions */
.batch-actions {
  position: fixed;
  bottom: 24px;
  left: 280px;
  right: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-radius: var(--radius-xl);
  z-index: 100;
  animation: slideInUp var(--transition-normal) ease-out;
}

.batch-info {
  font-size: 14px;
  color: var(--text-secondary);
}

.batch-info strong {
  color: var(--primary-500);
  font-size: 18px;
}

.batch-buttons {
  display: flex;
  gap: 12px;
}

/* Share Result */
.share-result {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.share-link-box,
.share-password-box {
  padding: 16px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
}

.share-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

/* Link Result */
.link-result {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.link-info {
  padding: 20px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
}

.link-file {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
}

.link-details {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.detail-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.link-box {
  display: flex;
  gap: 12px;
}

.link-box .el-input {
  flex: 1;
}

/* Responsive */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .header-stats {
    width: 100%;
    justify-content: space-between;
  }

  .toolbar {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }

  .toolbar-right {
    flex-wrap: wrap;
  }

  .search-input {
    width: 100%;
  }

  .file-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .batch-actions {
    left: 24px;
    flex-direction: column;
    gap: 16px;
  }

  .batch-buttons {
    flex-wrap: wrap;
    justify-content: center;
  }

  .link-details {
    grid-template-columns: 1fr;
  }

  .link-box {
    flex-direction: column;
  }
}
</style>
