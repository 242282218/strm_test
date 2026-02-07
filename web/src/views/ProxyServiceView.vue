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
          <el-form label-width="120px" :model="strmForm" :rules="strmRules" ref="strmFormRef">
            <el-form-item label="网盘路径" prop="remote_path">
              <el-input 
                v-model="strmForm.remote_path" 
                placeholder="/video" 
                :disabled="generating"
              />
              <div class="form-tip">要扫描的夸克网盘目录路径</div>
            </el-form-item>
            <el-form-item label="本地路径" prop="local_path">
              <el-input 
                v-model="strmForm.local_path" 
                placeholder="./strm" 
                :disabled="generating"
              />
              <div class="form-tip">STRM 文件保存的本地目录</div>
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
              <span class="form-tip ml-2">扫描子目录</span>
            </el-form-item>
            <el-form-item label="并发限制">
              <el-slider v-model="strmForm.concurrent_limit" :min="1" :max="10" :disabled="generating" show-stops />
            </el-form-item>
            <el-form-item>
              <el-button 
                type="primary" 
                :loading="generating" 
                :icon="VideoCamera"
                @click="generateStrm"
              >
                {{ generating ? '生成中...' : '生成 STRM' }}
              </el-button>
            </el-form-item>
          </el-form>

          <div v-if="strmResult" class="strm-result">
            <el-divider />
            <el-alert
              :type="strmResult.success ? 'success' : 'error'"
              :title="strmResult.message"
              :closable="false"
              show-icon
            />
            <div v-if="strmResult.count !== undefined" class="strm-stats">
              <el-statistic title="生成数量" :value="strmResult.count" />
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
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Delete, VideoCamera } from '@element-plus/icons-vue'
import { getProxyCacheStats, clearProxyCache, getRedirectUrl, getProxyStreamUrl, type ProxyCacheStats } from '@/api/proxy'
import { scanDirectory, type ScanResult } from '@/api/strm'
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

const strmFormRef = ref<FormInstance>()
const strmForm = reactive({
  remote_path: '/video',
  local_path: './strm',
  strm_url_mode: 'redirect',
  recursive: true,
  concurrent_limit: 5
})

const strmRules: FormRules = {
  remote_path: [
    { required: true, message: '请输入网盘路径', trigger: 'blur' }
  ],
  local_path: [
    { required: true, message: '请输入本地路径', trigger: 'blur' }
  ],
  strm_url_mode: [
    { required: true, message: '请选择 URL 模式', trigger: 'change' }
  ]
}

const strmResult = ref<{
  success: boolean
  message: string
  count?: number
} | null>(null)

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

const generateStrm = async () => {
  if (!strmFormRef.value) return

  await strmFormRef.value.validate(async (valid) => {
    if (!valid) return

    generating.value = true
    strmResult.value = null

    try {
      const result = await scanDirectory({
        remote_path: strmForm.remote_path,
        local_path: strmForm.local_path,
        recursive: strmForm.recursive,
        concurrent_limit: strmForm.concurrent_limit,
        strm_url_mode: strmForm.strm_url_mode as 'redirect' | 'stream' | 'direct' | 'webdav'
      })

      strmResult.value = {
        success: true,
        message: `STRM 生成成功`,
        count: result.count
      }

      ElMessage.success(`成功生成 ${result.count} 个 STRM 文件`)
    } catch (error: unknown) {
      strmResult.value = {
        success: false,
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
  text-align: center;
}
</style>
