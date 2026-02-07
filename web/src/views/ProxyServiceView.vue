<template>
  <div class="proxy-service-page">
    <div class="page-header">
      <h2>代理服务</h2>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="loadStats">刷新</el-button>
        <el-button type="danger" :icon="Delete" @click="clearCache">清除缓存</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="24">
        <el-card shadow="never" class="card">
          <template #header>服务说明</template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="302 重定向">
              直接重定向到夸克网盘直链，适合支持 302 跳转的播放器
            </el-descriptions-item>
            <el-descriptions-item label="流代理">
              服务器中转流量，适合不支持 302 的播放器或浏览器播放
            </el-descriptions-item>
            <el-descriptions-item label="转码播放">
              获取夸克转码后的直链，适合网络环境较差的场景
            </el-descriptions-item>
            <el-descriptions-item label="Emby 反代">
              拦截 Emby 请求，修改 PlaybackInfo 响应，强制 DirectPlay
            </el-descriptions-item>
            <el-descriptions-item label="STRM 生成" :span="2">
              扫描夸克网盘目录，生成 STRM 文件，支持多种 URL 模式
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt-4">
      <el-col :span="12">
        <el-card shadow="never" class="card">
          <template #header>
            <div class="card-header-with-tag">
              <span>STRM 生成</span>
              <el-tag type="warning" size="small">批量生成</el-tag>
            </div>
          </template>
          
          <!-- 已选路径列表 -->
          <div class="selected-paths-section">
            <div class="section-header">
              <span class="section-title">已选网盘路径</span>
              <el-button type="primary" size="small" :icon="FolderOpened" @click="openFileBrowser">
                添加文件夹/文件
              </el-button>
            </div>
            
            <div v-if="selectedPaths.length === 0" class="empty-paths">
              <el-empty description="请点击上方按钮选择网盘文件夹或文件" :image-size="80" />
            </div>
            
            <el-table v-else :data="selectedPaths" size="small" border>
              <el-table-column type="index" width="50" />
              <el-table-column label="路径" min-width="200">
                <template #default="{ row }">
                  <div class="path-item">
                    <el-icon v-if="row.type === 'folder'" class="path-icon folder"><Folder /></el-icon>
                    <el-icon v-else class="path-icon file"><Document /></el-icon>
                    <span class="path-text" :title="row.path">{{ row.path }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="80">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.type === 'folder' ? 'primary' : 'info'">
                    {{ row.type === 'folder' ? '文件夹' : '文件' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" fixed="right">
                <template #default="{ $index }">
                  <el-button link type="danger" size="small" @click="removePath($index)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <el-divider />

          <el-form label-width="120px" :model="strmForm" :rules="strmRules" ref="strmFormRef">
            <el-form-item label="本地路径" prop="local_path">
              <el-input 
                v-model="strmForm.local_path" 
                placeholder="./strm" 
                :disabled="generating"
              />
              <div class="form-tip">STRM 文件保存的本地目录</div>
            </el-form-item>
            <el-form-item label="服务器地址">
              <el-input 
                v-model="strmForm.base_url" 
                placeholder="http://localhost:8000" 
                :disabled="generating"
              />
              <div class="form-tip">Emby 访问代理服务的地址（如 http://192.168.1.100:8000）</div>
            </el-form-item>
            <el-form-item label="URL 模式" prop="strm_url_mode">
              <el-select v-model="strmForm.strm_url_mode" style="width: 100%" :disabled="generating">
                <el-option label="302 重定向 (推荐)" value="redirect" />
                <el-option label="流代理" value="stream" />
                <el-option label="直接直链" value="direct" />
                <el-option label="WebDAV" value="webdav" />
              </el-select>
              <div class="form-tip">STRM 文件中使用的 URL 模式</div>
            </el-form-item>
            <el-form-item label="递归扫描">
              <el-switch v-model="strmForm.recursive" :disabled="generating" />
              <span class="form-tip ml-2">扫描子目录（仅对文件夹有效）</span>
            </el-form-item>
            <el-form-item label="覆盖已存在">
              <el-switch v-model="strmForm.overwrite" :disabled="generating" />
              <span class="form-tip ml-2">开启后会重写已有 STRM 文件</span>
            </el-form-item>
            <el-form-item label="并发限制">
              <el-slider v-model="strmForm.concurrent_limit" :min="1" :max="10" :disabled="generating" show-stops />
            </el-form-item>
            <el-form-item>
              <el-button 
                type="primary" 
                :loading="generating" 
                :icon="VideoCamera"
                :disabled="selectedPaths.length === 0"
                @click="generateStrm"
              >
                {{ generating ? '生成中...' : '生成 STRM' }}
              </el-button>
              <span v-if="selectedPaths.length === 0" class="form-tip ml-2">请先选择网盘路径</span>
            </el-form-item>
          </el-form>

          <div v-if="strmResult" class="strm-result">
            <el-divider />
            <el-alert
              :type="strmResult.alertType"
              :title="strmResult.message"
              :closable="false"
              show-icon
            />
            <div v-if="strmResult.count !== undefined" class="strm-stats">
              <el-statistic title="生成数量" :value="strmResult.count" />
              <el-statistic title="跳过数量" :value="strmResult.skipped || 0" />
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never" class="card">
          <template #header>缓存统计</template>
          <div v-if="stats" class="stats-grid">
            <div class="stat-item">
              <div class="stat-value">{{ stats.size }}</div>
              <div class="stat-label">缓存条目</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.hit_count }}</div>
              <div class="stat-label">命中次数</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.miss_count }}</div>
              <div class="stat-label">未命中次数</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ (stats.hit_rate || 0).toFixed(1) }}%</div>
              <div class="stat-label">命中率</div>
            </div>
          </div>
          <el-empty v-else description="暂无数据" :image-size="84" />
        </el-card>

        <el-card shadow="never" class="card mt-4">
          <template #header>链接测试</template>
          <el-form label-width="100px">
            <el-form-item label="文件ID">
              <el-input v-model="testForm.fileId" placeholder="输入夸克文件ID" />
            </el-form-item>
            <el-form-item label="文件路径">
              <el-input v-model="testForm.path" placeholder="可选：输入文件路径用于WebDAV兜底" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="testRedirect">测试 302 重定向</el-button>
              <el-button @click="testStream">测试流代理</el-button>
            </el-form-item>
          </el-form>

          <div v-if="testResult" class="test-result">
            <el-divider />
            <h4>测试结果</h4>
            <el-alert
              :type="testResult.success ? 'success' : 'error'"
              :title="testResult.message"
              :closable="false"
              show-icon
            />
            <div v-if="testResult.url" class="url-display">
              <el-input v-model="testResult.url" readonly>
                <template #append>
                  <el-button @click="copyUrl">复制</el-button>
                </template>
              </el-input>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt-4">
      <el-col :span="24">
        <el-card shadow="never" class="card">
          <template #header>API 端点</template>
          <el-table :data="apiEndpoints" stripe border>
            <el-table-column prop="name" label="名称" width="180" />
            <el-table-column prop="method" label="方法" width="100">
              <template #default="{ row }">
                <el-tag :type="getMethodType(row.method)">{{ row.method }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="path" label="路径" min-width="250" />
            <el-table-column prop="description" label="说明" min-width="300" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt-4">
      <el-col :span="24">
        <el-card shadow="never" class="card">
          <template #header>STRM URL 模式说明</template>
          <el-table :data="strmModes" stripe border>
            <el-table-column prop="mode" label="模式" width="120" />
            <el-table-column prop="name" label="名称" width="150" />
            <el-table-column prop="description" label="说明" min-width="300" />
            <el-table-column prop="useCase" label="适用场景" min-width="250" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 文件浏览器弹窗 -->
    <el-dialog
      v-model="fileBrowserVisible"
      title="选择网盘文件/文件夹"
      width="700px"
      :close-on-click-modal="false"
    >
      <div class="file-browser">
        <!-- 面包屑导航 -->
        <div class="breadcrumb-bar">
          <el-button link :icon="ArrowLeft" @click="goBack" :disabled="currentPath === '/'">
            返回上级
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item 
              v-for="(item, index) in breadcrumbItems" 
              :key="index"
              @click="jumpToPath(index)"
              class="breadcrumb-clickable"
            >
              {{ item.name || '根目录' }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <!-- 文件列表 -->
        <div class="file-list" v-loading="browsing">
          <div 
            v-for="item in fileList" 
            :key="item.id"
            class="file-item"
            :class="{ 
              'is-folder': item.type === 'folder',
              'is-selected': item.selected
            }"
            @click.self="handleItemClick(item)"
          >
            <div class="file-checkbox-wrapper" @click.stop>
              <el-checkbox 
                v-model="item.selected" 
                @change="(val: boolean) => toggleSelection(item, val)"
              />
            </div>
            <div class="file-content" @click="handleContentClick(item)">
              <el-icon class="file-icon" :size="40" :class="item.type === 'folder' ? 'folder-icon' : 'file-icon'">
                <Folder v-if="item.type === 'folder'" />
                <Document v-else />
              </el-icon>
              <div class="file-info">
                <div class="file-name">{{ item.name }}</div>
                <div class="file-meta">{{ item.type === 'folder' ? '文件夹' : formatSize(item.size) }}</div>
              </div>
            </div>
          </div>
          <el-empty v-if="fileList.length === 0" description="空文件夹" :image-size="80" />
        </div>

        <!-- 已选文件预览 -->
        <div class="selection-preview" v-if="browserSelection.length > 0">
          <div class="selection-header">
            <span>已选择 {{ browserSelection.length }} 项</span>
            <el-button link type="danger" size="small" @click="clearBrowserSelection">
              清空
            </el-button>
          </div>
          <el-scrollbar max-height="100px">
            <div class="selection-tags">
              <el-tag
                v-for="(item, index) in browserSelection"
                :key="item.id"
                closable
                size="small"
                @close="removeBrowserSelection(index)"
              >
                {{ item.name }}
              </el-tag>
            </div>
          </el-scrollbar>
        </div>
      </div>

      <template #footer>
        <el-button @click="fileBrowserVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmSelection">
          确认选择 ({{ browserSelection.length }})
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Delete, VideoCamera, FolderOpened, Folder, Document, ArrowLeft } from '@element-plus/icons-vue'
import { getProxyCacheStats, clearProxyCache, getRedirectUrl, getProxyStreamUrl, type ProxyCacheStats } from '@/api/proxy'
import { scanDirectory, type ScanResult } from '@/api/strm'
import { browseFiles, type FileItem } from '@/api/fileManager'
import type { FormInstance, FormRules } from 'element-plus'

const stats = ref<ProxyCacheStats | null>(null)
const loading = ref(false)
const generating = ref(false)

const testForm = reactive({
  fileId: '',
  path: ''
})

const testResult = ref<{
  success: boolean
  message: string
  url?: string
} | null>(null)

// 已选路径列表
interface SelectedPath {
  path: string
  type: 'folder' | 'file'
  id?: string
}

const selectedPaths = ref<SelectedPath[]>([])

const strmFormRef = ref<FormInstance>()
const strmForm = reactive({
  local_path: './strm',
  strm_url_mode: 'redirect',
  recursive: true,
  overwrite: false,
  concurrent_limit: 5,
  base_url: 'http://localhost:8000'
})

const strmRules: FormRules = {
  local_path: [
    { required: true, message: '请输入本地路径', trigger: 'blur' }
  ],
  strm_url_mode: [
    { required: true, message: '请选择 URL 模式', trigger: 'change' }
  ]
}

const strmResult = ref<{
  success: boolean
  alertType: 'success' | 'warning' | 'error'
  message: string
  count?: number
  skipped?: number
} | null>(null)

// 文件浏览器相关
const fileBrowserVisible = ref(false)
const currentPath = ref('/')
const fileList = ref<FileItem[]>([])
const browsing = ref(false)
const browserSelection = ref<FileItem[]>([])

const breadcrumbItems = computed(() => {
  const paths = currentPath.value.split('/').filter(Boolean)
  return [{ name: '', path: '/' }, ...paths.map((name, index) => ({
    name,
    path: '/' + paths.slice(0, index + 1).join('/')
  }))]
})

const apiEndpoints = [
  { name: 'STRM 生成', method: 'POST', path: '/api/strm/scan', description: '扫描目录生成 STRM 文件' },
  { name: '流代理', method: 'GET', path: '/api/proxy/stream/{file_id}', description: '代理视频流，服务器中转流量' },
  { name: '302 重定向', method: 'GET', path: '/api/proxy/redirect/{file_id}', description: '302 重定向到夸克直链' },
  { name: '转码链接', method: 'GET', path: '/api/proxy/transcoding/{file_id}', description: '获取转码后的直链' },
  { name: 'Emby 反代', method: 'GET', path: '/api/proxy/emby/{path}', description: 'Emby 请求反代' },
  { name: '清除缓存', method: 'POST', path: '/api/proxy/cache/clear', description: '清除代理缓存' },
  { name: '缓存统计', method: 'GET', path: '/api/proxy/cache/stats', description: '获取缓存统计信息' }
]

const strmModes = [
  { mode: 'redirect', name: '302 重定向', description: 'STRM 文件中包含 /api/proxy/redirect/{file_id} 链接，播放时 302 跳转到夸克直链', useCase: '推荐，兼容性好，支持直链缓存' },
  { mode: 'stream', name: '流代理', description: 'STRM 文件中包含 /api/proxy/stream/{file_id} 链接，服务器中转流量', useCase: '适合不支持 302 的播放器或需要统一出口的场景' },
  { mode: 'direct', name: '直接直链', description: 'STRM 文件中直接存储夸克直链 URL', useCase: '直链有效期短（约4小时），适合即下即播' },
  { mode: 'webdav', name: 'WebDAV', description: 'STRM 文件中包含 WebDAV 路径，播放时通过 WebDAV 协议获取', useCase: '适合 WebDAV 客户端或需要统一协议的场景' }
]

const getMethodType = (method: string) => {
  const types: Record<string, string> = {
    GET: 'success',
    POST: 'primary',
    PUT: 'warning',
    DELETE: 'danger'
  }
  return types[method] || 'info'
}

const loadStats = async () => {
  loading.value = true
  try {
    const data = await getProxyCacheStats()
    stats.value = data.stats
  } catch (error: unknown) {
    ElMessage.error('加载缓存统计失败')
  } finally {
    loading.value = false
  }
}

const clearCache = async () => {
  try {
    await ElMessageBox.confirm('确定要清除代理缓存吗？', '确认', {
      type: 'warning'
    })
    await clearProxyCache()
    ElMessage.success('缓存已清除')
    loadStats()
  } catch {
    // 用户取消
  }
}

const testRedirect = async () => {
  if (!testForm.fileId) {
    ElMessage.warning('请输入文件ID')
    return
  }
  try {
    const url = await getRedirectUrl(testForm.fileId, testForm.path || undefined)
    testResult.value = {
      success: true,
      message: '获取重定向链接成功',
      url
    }
  } catch (error: unknown) {
    testResult.value = {
      success: false,
      message: '获取重定向链接失败'
    }
  }
}

const testStream = () => {
  if (!testForm.fileId) {
    ElMessage.warning('请输入文件ID')
    return
  }
  const url = getProxyStreamUrl(testForm.fileId)
  testResult.value = {
    success: true,
    message: '流代理链接已生成（可直接在播放器中使用）',
    url
  }
}

const copyUrl = () => {
  if (testResult.value?.url) {
    navigator.clipboard.writeText(testResult.value.url)
    ElMessage.success('已复制到剪贴板')
  }
}

// 文件浏览器方法
const openFileBrowser = () => {
  fileBrowserVisible.value = true
  currentPath.value = '/'
  browserSelection.value = []
  loadFileList()
}

const loadFileList = async () => {
  browsing.value = true
  try {
    const res = await browseFiles(currentPath.value)
    fileList.value = res.items.map(item => ({
      id: item.id,
      name: item.name,
      path: item.path,
      // 后端返回 file_type，前端使用 type
      type: (item as any).file_type || item.type,
      size: item.size,
      selected: browserSelection.value.some(s => s.id === item.id)
    }))
    console.log('Loaded files:', fileList.value)
  } catch (error) {
    console.error('Load file list error:', error)
    ElMessage.error('加载文件列表失败')
  } finally {
    browsing.value = false
  }
}

const goBack = () => {
  const paths = currentPath.value.split('/').filter(Boolean)
  if (paths.length > 0) {
    paths.pop()
    currentPath.value = '/' + paths.join('/')
    loadFileList()
  }
}

const jumpToPath = (index: number) => {
  if (index === 0) {
    currentPath.value = '/'
  } else {
    const paths = currentPath.value.split('/').filter(Boolean)
    currentPath.value = '/' + paths.slice(0, index).join('/')
  }
  loadFileList()
}

// 处理整个卡片的点击（点击空白区域）
const handleItemClick = (item: FileItem) => {
  console.log('Card clicked:', item.name, 'type:', item.type)
  if (item.type === 'folder') {
    currentPath.value = item.path
    loadFileList()
  }
}

// 处理内容区域的点击
const handleContentClick = (item: FileItem) => {
  console.log('Content clicked:', item.name, 'type:', item.type)
  if (item.type === 'folder') {
    // 文件夹：进入目录
    currentPath.value = item.path
    loadFileList()
  } else {
    // 文件：切换选中状态
    item.selected = !item.selected
    toggleSelection(item, item.selected)
  }
}

const isSelected = (item: FileItem) => {
  return browserSelection.value.some(s => s.id === item.id)
}

const toggleSelection = (item: FileItem, selected: boolean) => {
  const index = browserSelection.value.findIndex(s => s.id === item.id)
  if (selected && index === -1) {
    browserSelection.value.push(item)
  } else if (!selected && index > -1) {
    browserSelection.value.splice(index, 1)
  }
}

const removeBrowserSelection = (index: number) => {
  const item = browserSelection.value[index]
  if (!item) return
  const fileItem = fileList.value.find(f => f.id === item.id)
  if (fileItem) {
    fileItem.selected = false
  }
  browserSelection.value.splice(index, 1)
}

const clearBrowserSelection = () => {
  fileList.value.forEach(item => item.selected = false)
  browserSelection.value = []
}

const confirmSelection = () => {
  browserSelection.value.forEach(item => {
    selectedPaths.value.push({
      path: item.path,
      type: item.type as 'folder' | 'file',
      id: item.id
    })
  })
  fileBrowserVisible.value = false
  ElMessage.success(`已添加 ${browserSelection.value.length} 个路径`)
}

const removePath = (index: number) => {
  selectedPaths.value.splice(index, 1)
}

const formatSize = (size?: number) => {
  if (!size) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return size.toFixed(2) + ' ' + units[i]
}

const generateStrm = async () => {
  if (!strmFormRef.value) return
  if (selectedPaths.value.length === 0) {
    ElMessage.warning('请先选择网盘路径')
    return
  }

  await strmFormRef.value.validate(async (valid) => {
    if (!valid) return

    generating.value = true
    strmResult.value = null

    try {
      // 修复 base_url 格式（确保 http:// 有双斜杠）
      let baseUrl = strmForm.base_url.trim()
      if (baseUrl.match(/^http:\/[^/]/)) {
        baseUrl = baseUrl.replace('http:/', 'http://')
      }
      if (baseUrl.match(/^https:\/[^/]/)) {
        baseUrl = baseUrl.replace('https:/', 'https://')
      }
      
      let totalCount = 0
      let totalSkipped = 0
      let totalFailed = 0
      let totalCandidates = 0
      
      // 逐个处理选中的路径
      for (const pathItem of selectedPaths.value) {
        const result = await scanDirectory({
          remote_path: pathItem.path,
          local_path: strmForm.local_path,
          recursive: pathItem.type === 'folder' ? strmForm.recursive : false,
          concurrent_limit: strmForm.concurrent_limit,
          overwrite: strmForm.overwrite,
          strm_url_mode: strmForm.strm_url_mode as 'redirect' | 'stream' | 'direct' | 'webdav',
          base_url: baseUrl
        })
        totalCount += result.count
        totalSkipped += result.skipped || 0
        totalFailed += result.failed || 0
        totalCandidates += result.total || 0
      }

      let message = ''
      let alertType: 'success' | 'warning' | 'error' = 'success'
      if (totalCount > 0) {
        message = `生成完成：新增 ${totalCount} 个，跳过 ${totalSkipped} 个`
        alertType = 'success'
      } else if (totalSkipped > 0) {
        message = `未生成新文件：跳过 ${totalSkipped} 个（已存在）`
        alertType = 'warning'
      } else if (totalCandidates === 0) {
        message = '未找到可生成的媒体文件'
        alertType = 'warning'
      } else {
        message = `生成失败：失败 ${totalFailed} 个`
        alertType = 'error'
      }

      strmResult.value = {
        success: alertType !== 'error',
        alertType,
        message,
        count: totalCount,
        skipped: totalSkipped,
      }

      if (alertType === 'success') {
        ElMessage.success(message)
      } else if (alertType === 'warning') {
        ElMessage.warning(message)
      } else {
        ElMessage.error(message)
      }
    } catch (error: unknown) {
      strmResult.value = {
        success: false,
        alertType: 'error',
        message: 'STRM 生成失败'
      }
      ElMessage.error('STRM 生成失败')
    } finally {
      generating.value = false
    }
  })
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.proxy-service-page {
  padding: 8px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.card {
  margin-bottom: 16px;
}

.mt-4 {
  margin-top: 16px;
}

.card-header-with-tag {
  display: flex;
  align-items: center;
  gap: 8px;
}

.form-tip {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.ml-2 {
  margin-left: 8px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--primary-color);
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.test-result {
  margin-top: 16px;
}

.url-display {
  margin-top: 12px;
}

.strm-result {
  margin-top: 16px;
}

.strm-stats {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  gap: 24px;
}

/* 已选路径区域 */
.selected-paths-section {
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  font-weight: 600;
  font-size: 14px;
}

.empty-paths {
  padding: 20px 0;
}

.path-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.path-icon {
  flex-shrink: 0;
}

.path-icon.folder {
  color: #e6a23c;
}

.path-icon.file {
  color: #909399;
}

.path-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 文件浏览器 */
.file-browser {
  min-height: 400px;
}

.breadcrumb-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.breadcrumb-clickable {
  cursor: pointer;
  color: var(--primary-color);
}

.breadcrumb-clickable:hover {
  text-decoration: underline;
}

.file-list {
  min-height: 300px;
  max-height: 400px;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 16px;
  padding: 8px;
}

.file-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  border: 2px solid transparent;
}

.file-item:hover {
  background: var(--bg-secondary);
}

.file-item.is-selected {
  background: var(--primary-color-light);
  border-color: var(--primary-color);
}

.file-checkbox-wrapper {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
  padding: 4px;
}

.file-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding-top: 24px;
  cursor: pointer;
}

.folder-icon {
  color: #e6a23c;
  margin-bottom: 8px;
}

.file-icon {
  color: #909399;
  margin-bottom: 8px;
}

.file-info {
  text-align: center;
  width: 100%;
}

.file-name {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

.file-meta {
  font-size: 11px;
  color: var(--text-secondary);
}

.selection-preview {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.selection-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.selection-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
