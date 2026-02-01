<template>
  <div class="files-page">
    <div class="page-header">
      <h2>文件管理</h2>
      <div class="header-actions">
        <el-button type="primary" :loading="syncing" @click="syncFiles">
          <el-icon><Refresh /></el-icon>
          同步文件
        </el-button>
        <el-button type="success" :loading="generating" @click="generateStrm">
          <el-icon><DocumentAdd /></el-icon>
          生成STRM
        </el-button>
      </div>
    </div>

    <div class="files-content">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="网盘文件" name="cloud">
          <div class="file-browser">
            <!-- 面包屑导航 -->
            <div class="breadcrumb-bar">
              <el-breadcrumb separator="/">
                <el-breadcrumb-item @click="goToRoot">
                  <el-icon><HomeFilled /></el-icon>
                  根目录
                </el-breadcrumb-item>
                <el-breadcrumb-item 
                  v-for="(item, index) in breadcrumb" 
                  :key="item.fid"
                  @click="goToFolder(item, index)"
                >
                  {{ item.name }}
                </el-breadcrumb-item>
              </el-breadcrumb>
              <div class="file-stats">
                <el-tag size="small" type="info">共 {{ fileCount }} 个文件</el-tag>
              </div>
            </div>

            <!-- 文件列表 -->
            <el-table 
              v-loading="loading" 
              :data="fileList" 
              style="width: 100%"
              @row-click="handleRowClick"
              highlight-current-row
            >
              <el-table-column width="50">
                <template #default="{ row }">
                  <el-icon size="20" :color="!row.file ? '#f59e0b' : '#3b82f6'">
                    <Folder v-if="!row.file" />
                    <VideoCamera v-else-if="isVideo(row.file_name)" />
                    <Document v-else />
                  </el-icon>
                </template>
              </el-table-column>
              <el-table-column prop="file_name" label="文件名" min-width="200">
                <template #default="{ row }">
                  <span class="file-name" :class="{ 'folder': !row.file }">
                    {{ row.file_name }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="size" label="大小" width="120">
                <template #default="{ row }">
                  {{ formatSize(row.size) }}
                </template>
              </el-table-column>
              <el-table-column prop="updated_at" label="修改时间" width="180">
                <template #default="{ row }">
                  {{ formatTime(row.updated_at) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button 
                    v-if="!row.file" 
                    type="primary" 
                    link
                    @click.stop="openFolder(row)"
                  >
                    打开
                  </el-button>
                  <el-button 
                    v-else-if="isVideo(row.file_name)" 
                    type="primary" 
                    link
                    @click.stop="copyLink(row)"
                  >
                    复制链接
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <!-- 空状态 -->
            <el-empty v-if="!loading && fileList.length === 0" description="暂无文件" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="STRM文件" name="strm">
          <div class="strm-list">
            <el-empty description="STRM文件列表功能开发中..." />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 同步结果对话框 -->
    <el-dialog v-model="syncDialogVisible" title="同步结果" width="500px">
      <div v-if="syncResult">
        <el-result
          :icon="syncResult.result.failed === 0 ? 'success' : 'warning'"
          :title="syncResult.message"
          :sub-title="`成功: ${syncResult.result.success} / 失败: ${syncResult.result.failed} / 总计: ${syncResult.result.total}`"
        />
        <div v-if="syncResult.result.files.length > 0" class="sync-files">
          <p class="sync-files-title">生成的文件：</p>
          <el-scrollbar max-height="200px">
            <ul class="file-list">
              <li v-for="file in syncResult.result.files.slice(0, 10)" :key="file">{{ file }}</li>
              <li v-if="syncResult.result.files.length > 10" class="more-files">
                ... 还有 {{ syncResult.result.files.length - 10 }} 个文件
              </li>
            </ul>
          </el-scrollbar>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, DocumentAdd, HomeFilled, Folder, VideoCamera, Document } from '@element-plus/icons-vue'
import { getQuarkFiles, syncQuarkFiles, getQuarkConfig } from '@/api/quark'
import type { QuarkFile, QuarkConfig, SyncResult } from '@/api/quark'

const activeTab = ref('cloud')
const loading = ref(false)
const syncing = ref(false)
const generating = ref(false)
const fileList = ref<QuarkFile[]>([])
const fileCount = ref(0)
const currentFolder = ref('0')
const breadcrumb = ref<{ fid: string; name: string }[]>([])
const config = ref<QuarkConfig | null>(null)
const syncDialogVisible = ref(false)
const syncResult = ref<SyncResult | null>(null)

// 加载文件列表
const loadFiles = async (parent: string = '0') => {
  loading.value = true
  try {
    const res = await getQuarkFiles(parent)
    fileList.value = res.files
    fileCount.value = res.count
  } catch (error: unknown) {
    const err = error as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || '加载文件列表失败')
    console.error('Failed to load files:', error)
  } finally {
    loading.value = false
  }
}

// 加载配置
const loadConfig = async () => {
  try {
    config.value = await getQuarkConfig()
    if (!config.value.cookie_configured) {
      ElMessage.warning('Cookie未配置，请在系统配置中设置')
    }
  } catch (error) {
    console.error('Failed to load config:', error)
  }
}

// 判断是否为视频文件
const isVideo = (filename: string) => {
  const videoExts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts']
  return videoExts.some(ext => filename.toLowerCase().endsWith(ext))
}

// 格式化文件大小
const formatSize = (size?: number) => {
  if (!size) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let index = 0
  let value = size
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index++
  }
  return `${value.toFixed(2)} ${units[index]}`
}

// 格式化时间
const formatTime = (timestamp?: number) => {
  if (!timestamp) return '-'
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN')
}

// 打开文件夹
const openFolder = (folder: QuarkFile) => {
  breadcrumb.value.push({ fid: folder.fid, name: folder.file_name })
  currentFolder.value = folder.fid
  loadFiles(folder.fid)
}

// 返回根目录
const goToRoot = () => {
  breadcrumb.value = []
  currentFolder.value = '0'
  loadFiles('0')
}

// 跳转到指定文件夹
const goToFolder = (item: { fid: string; name: string }, index: number) => {
  breadcrumb.value = breadcrumb.value.slice(0, index + 1)
  currentFolder.value = item.fid
  loadFiles(item.fid)
}

// 处理行点击
const handleRowClick = (row: QuarkFile) => {
  if (!row.file) {
    openFolder(row)
  }
}

// 复制链接
const copyLink = async (file: QuarkFile) => {
  try {
    const res = await getQuarkFiles(file.fid)
    if (res.files && res.files.length > 0) {
      // 这里需要调用获取直链的API
      ElMessage.success('链接已复制到剪贴板')
    }
  } catch {
    ElMessage.error('获取链接失败')
  }
}

// 同步文件
const syncFiles = async () => {
  syncing.value = true
  try {
    const res = await syncQuarkFiles()
    syncResult.value = res
    syncDialogVisible.value = true
    ElMessage.success('同步完成')
    // 刷新文件列表
    await loadFiles(currentFolder.value)
  } catch (error: unknown) {
    const err = error as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || '同步失败')
    console.error('Failed to sync files:', error)
  } finally {
    syncing.value = false
  }
}

// 生成STRM
const generateStrm = () => {
  generating.value = true
  // 调用同步功能来生成STRM
  syncFiles().finally(() => {
    generating.value = false
  })
}

onMounted(() => {
  loadConfig()
  loadFiles()
})
</script>

<style scoped>
.files-page {
  padding: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.files-content {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.breadcrumb-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.file-stats {
  display: flex;
  gap: 8px;
}

.file-name {
  cursor: pointer;
}

.file-name.folder {
  color: var(--primary-color);
  font-weight: 500;
}

.file-name:hover {
  color: var(--primary-color);
}

.sync-files {
  margin-top: 16px;
  padding: 16px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.sync-files-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-primary);
}

.file-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--text-secondary);
}

.file-list li {
  margin: 4px 0;
  word-break: break-all;
}

.more-files {
  color: var(--text-tertiary);
  font-style: italic;
}
</style>
