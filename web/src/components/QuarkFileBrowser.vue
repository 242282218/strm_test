<template>
  <el-dialog
    v-model="visible"
    title="选择夸克云盘文件夹"
    width="800px"
    :close-on-click-modal="false"
    class="quark-file-browser"
  >
    <!-- 面包屑导航 -->
    <div class="breadcrumb-nav">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item
          v-for="(item, index) in breadcrumbs"
          :key="item.fid"
          @click="navigateTo(item.fid)"
          class="breadcrumb-item"
        >
          {{ item.name }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <!-- 文件列表 -->
    <div class="file-list" v-loading="loading">
      <div class="list-header">
        <div class="header-col name">名称</div>
        <div class="header-col type">类型</div>
        <div class="header-col size">大小</div>
        <div class="header-col time">修改时间</div>
      </div>

      <div class="list-body" v-if="fileList.length > 0">
        <div
          v-for="item in fileList"
          :key="item.fid"
          class="file-item"
          :class="{
            'selected': selectedFid === item.fid,
            'folder': item.file_type === 0
          }"
          @click="handleItemClick(item)"
          @dblclick="handleItemDoubleClick(item)"
        >
          <div class="item-col name">
            <el-icon v-if="item.file_type === 0" class="file-icon folder-icon">
              <Folder />
            </el-icon>
            <el-icon v-else class="file-icon file-icon">
              <Document />
            </el-icon>
            <span class="file-name" :title="item.file_name">{{ item.file_name }}</span>
          </div>
          <div class="item-col type">
            {{ getFileType(item) }}
          </div>
          <div class="item-col size">
            {{ formatFileSize(item.size) }}
          </div>
          <div class="item-col time">
            {{ formatTime(item.updated_at) }}
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <el-empty
        v-else-if="!loading"
        description="该文件夹为空"
        :image-size="100"
      />

      <!-- 分页 -->
      <div class="pagination-wrapper" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <div class="selected-info">
          <span v-if="selectedItem">
            已选择: {{ selectedItem.file_name }}
          </span>
          <span v-else class="no-selection">请选择一个文件夹</span>
        </div>
        <div class="footer-actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button
            type="primary"
            @click="confirmSelection"
            :disabled="!selectedFid || selectedItem?.file_type !== 0"
          >
            确认选择
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Folder, Document } from '@element-plus/icons-vue'
import { browseQuarkDirectory, type QuarkFileItem } from '@/api/quark'

/**
 * 组件 Props
 */
const props = defineProps<{
  /** 控制对话框显示/隐藏 */
  modelValue: boolean
}>()

/**
 * 组件事件
 */
const emit = defineEmits<{
  /** 更新对话框显示状态 */
  (e: 'update:modelValue', value: boolean): void
  /** 选择文件夹事件 */
  (e: 'select', fid: string, path: string): void
}>()

/**
 * 对话框可见性（双向绑定）
 */
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

/**
 * 加载状态
 */
const loading = ref(false)

/**
 * 文件列表
 */
const fileList = ref<QuarkFileItem[]>([])

/**
 * 选中的文件ID
 */
const selectedFid = ref<string>('')

/**
 * 选中的文件项
 */
const selectedItem = ref<QuarkFileItem | null>(null)

/**
 * 当前页码
 */
const currentPage = ref(1)

/**
 * 每页数量
 */
const pageSize = ref(50)

/**
 * 总数量
 */
const total = ref(0)

/**
 * 当前目录ID
 */
const currentPdirFid = ref('0')

/**
 * 面包屑导航
 */
const breadcrumbs = ref<{ fid: string; name: string }[]>([
  { fid: '0', name: '根目录' }
])

/**
 * 加载文件列表
 *
 * 用途: 从夸克云盘加载指定目录的文件列表
 * 输入: 无（使用组件内部状态）
 * 输出: 无（更新 fileList 和 total）
 * 副作用: 调用 API，可能显示错误消息
 */
const loadFiles = async () => {
  loading.value = true
  try {
    console.log('[QuarkBrowser] 开始加载文件，参数:', {
      pdir_fid: currentPdirFid.value,
      page: currentPage.value,
      size: pageSize.value
    })
    
    const response = await browseQuarkDirectory({
      pdir_fid: currentPdirFid.value,
      page: currentPage.value,
      size: pageSize.value,
      file_type: 'all'
    })

    console.log('[QuarkBrowser] API 响应:', response)
    console.log('[QuarkBrowser] response.items:', response.items)
    console.log('[QuarkBrowser] response.total:', response.total)

    fileList.value = response.items
    total.value = response.total
    
    console.log('[QuarkBrowser] 文件列表已设置:', fileList.value.length, '个文件')
  } catch (error) {
    console.error('[QuarkBrowser] 加载失败:', error)
    console.error('[QuarkBrowser] 错误详情:', error.response || error.message)
    ElMessage.error('加载文件列表失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}

/**
 * 处理项目点击
 *
 * 用途: 选中文件或文件夹
 * 输入: item - 点击的文件项
 * 输出: 无
 * 副作用: 更新选中状态
 */
const handleItemClick = (item: QuarkFileItem) => {
  selectedFid.value = item.fid
  selectedItem.value = item
}

/**
 * 处理项目双击
 *
 * 用途: 双击文件夹时进入该目录
 * 输入: item - 双击的文件项
 * 输出: 无
 * 副作用: 如果是文件夹，则导航进入
 */
const handleItemDoubleClick = (item: QuarkFileItem) => {
  if (item.file_type === 0) {
    // 文件夹，进入
    navigateTo(item.fid, item.file_name)
  }
}

/**
 * 导航到指定目录
 *
 * 用途: 切换到指定目录并加载文件列表
 * 输入:
 *   - fid: 目标目录ID
 *   - name: 目录名称（可选，用于添加面包屑）
 * 输出: 无
 * 副作用: 更新面包屑、重置页码、加载新目录
 */
const navigateTo = (fid: string, name?: string) => {
  if (name) {
    // 进入子目录，添加到面包屑
    const index = breadcrumbs.value.findIndex(b => b.fid === fid)
    if (index >= 0) {
      // 已存在，截断后面的
      breadcrumbs.value = breadcrumbs.value.slice(0, index + 1)
    } else {
      // 新增
      breadcrumbs.value.push({ fid, name })
    }
  } else {
    // 点击面包屑，截断
    const index = breadcrumbs.value.findIndex(b => b.fid === fid)
    if (index >= 0) {
      breadcrumbs.value = breadcrumbs.value.slice(0, index + 1)
    }
  }

  // 更新当前目录
  currentPdirFid.value = fid
  currentPage.value = 1
  selectedFid.value = ''
  selectedItem.value = null

  // 加载新目录
  loadFiles()
}

/**
 * 处理分页变化
 *
 * 用途: 切换页码时重新加载文件列表
 * 输入: page - 新页码
 * 输出: 无
 * 副作用: 加载新页的数据
 */
const handlePageChange = (page: number) => {
  currentPage.value = page
  loadFiles()
}

/**
 * 确认选择
 *
 * 用途: 确认选中的文件夹，触发 select 事件
 * 输入: 无
 * 输出: 无
 * 副作用: 触发事件并关闭对话框
 */
const confirmSelection = () => {
  if (!selectedItem.value || selectedItem.value.file_type !== 0) {
    ElMessage.warning('请选择一个文件夹')
    return
  }

  // 构建路径字符串
  const path = breadcrumbs.value.map(b => b.name).join('/') + '/' + selectedItem.value.file_name
  emit('select', selectedFid.value, path)
  visible.value = false
}

/**
 * 获取文件类型显示文本
 *
 * 用途: 根据文件类型返回显示文本
 * 输入: item - 文件项
 * 输出: 文件类型字符串
 * 副作用: 无
 */
const getFileType = (item: QuarkFileItem): string => {
  if (item.file_type === 0) return '文件夹'
  const ext = item.file_name.split('.').pop()?.toLowerCase()
  return ext ? ext.toUpperCase() : '文件'
}

/**
 * 格式化文件大小
 *
 * 用途: 将字节数转换为可读格式
 * 输入: bytes - 字节数
 * 输出: 格式化后的字符串
 * 副作用: 无
 */
const formatFileSize = (bytes: number): string => {
  if (!bytes || bytes === 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(2)} ${units[unitIndex]}`
}

/**
 * 格式化时间戳
 *
 * 用途: 将 Unix 时间戳转换为本地时间字符串
 * 输入: timestamp - Unix 时间戳（秒）
 * 输出: 格式化后的时间字符串
 * 副作用: 无
 */
const formatTime = (timestamp: number): string => {
  if (!timestamp || timestamp === 0) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

/**
 * 监听对话框打开
 *
 * 用途: 对话框打开时重置状态并加载根目录
 */
watch(visible, (val) => {
  if (val) {
    // 重置状态
    currentPdirFid.value = '0'
    currentPage.value = 1
    selectedFid.value = ''
    selectedItem.value = null
    breadcrumbs.value = [{ fid: '0', name: '根目录' }]
    // 加载文件
    loadFiles()
  }
})
</script>

<style scoped>
.quark-file-browser :deep(.el-dialog__body) {
  padding: 0 20px 20px;
}

.breadcrumb-nav {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.breadcrumb-item {
  cursor: pointer;
  transition: color 0.2s;
}

.breadcrumb-item:hover {
  color: var(--el-color-primary);
}

.file-list {
  min-height: 300px;
  max-height: 500px;
  overflow-y: auto;
}

.list-header,
.file-item {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1.5fr;
  gap: 12px;
  padding: 12px 16px;
  align-items: center;
}

.list-header {
  font-weight: 600;
  color: var(--el-text-color-secondary);
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-fill-color-light);
  border-radius: 8px 8px 0 0;
}

.list-body {
  border: 1px solid var(--el-border-color);
  border-top: none;
  border-radius: 0 0 8px 8px;
}

.file-item {
  cursor: pointer;
  border-bottom: 1px solid var(--el-border-color-light);
  transition: all 0.2s;
}

.file-item:last-child {
  border-bottom: none;
}

.file-item:hover {
  background: var(--el-fill-color-light);
}

.file-item.selected {
  background: var(--el-color-primary-light-9);
  border-left: 3px solid var(--el-color-primary);
}

.file-item.folder {
  font-weight: 500;
}

.file-item .name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-item .name .file-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.file-item .name .file-icon.folder-icon {
  color: var(--el-color-warning);
}

.file-item .name .file-icon.file-icon {
  color: var(--el-color-info);
}

.file-item .name .file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-col,
.item-col {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-col.type,
.header-col.size,
.header-col.time,
.item-col.type,
.item-col.size,
.item-col.time {
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dialog-footer .selected-info {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.dialog-footer .selected-info .no-selection {
  color: var(--el-text-color-placeholder);
}

.dialog-footer .footer-actions {
  display: flex;
  gap: 12px;
}

/* 响应式适配 */
@media (max-width: 768px) {
  .file-list .list-header,
  .file-list .file-item {
    grid-template-columns: 2fr 1fr;
  }

  .file-list .list-header .size,
  .file-list .list-header .time,
  .file-list .file-item .size,
  .file-list .file-item .time {
    display: none;
  }
}
</style>
