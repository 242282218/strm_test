<template>
  <el-dialog
    v-model="visible"
    title="选择夸克云盘文件夹"
    width="800px"
    :close-on-click-modal="false"
    class="quark-file-browser"
  >
    <div class="breadcrumb-nav">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item
          v-for="item in breadcrumbs"
          :key="item.fid"
          @click="navigateTo(item.fid)"
          class="breadcrumb-item"
        >
          {{ item.name }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="file-list" v-loading="loading">
      <div class="list-header">
        <div class="header-col name">名称</div>
        <div class="header-col type">类型</div>
        <div class="header-col size">大小</div>
        <div class="header-col time">修改时间</div>
      </div>

      <div v-if="fileList.length > 0" class="list-body">
        <div
          v-for="item in fileList"
          :key="item.fid"
          class="file-item"
          :class="{
            selected: selectedFid === item.fid,
            folder: item.file_type === 0
          }"
          @click="handleItemClick(item)"
          @dblclick="handleItemDoubleClick(item)"
        >
          <div class="item-col name">
            <el-icon v-if="item.file_type === 0" class="file-icon folder-icon">
              <Folder />
            </el-icon>
            <el-icon v-else class="file-icon file-icon-document">
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

      <el-empty
        v-else-if="!loading"
        description="该文件夹为空"
        :image-size="100"
      />

      <div v-if="total > pageSize" class="pagination-wrapper">
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
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Folder, Document } from '@/components/icons'
import { browseQuarkDirectory, type QuarkFileItem } from '@/features/quark/api/quark'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'select', fid: string, path: string): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const fileList = ref<QuarkFileItem[]>([])
const selectedFid = ref<string>('')
const selectedItem = ref<QuarkFileItem | null>(null)
const currentPage = ref(1)
const pageSize = ref(50)
const total = ref(0)
const currentPdirFid = ref('0')
const breadcrumbs = ref<{ fid: string; name: string }[]>([
  { fid: '0', name: '根目录' }
])

const loadFiles = async () => {
  loading.value = true
  try {
    const response = await browseQuarkDirectory({
      pdir_fid: currentPdirFid.value,
      page: currentPage.value,
      size: pageSize.value,
      file_type: 'all'
    })

    fileList.value = response.items
    total.value = response.total
  } catch (error: unknown) {
    const err = error as { response?: unknown; message?: string }
    console.error('[QuarkBrowser] 加载失败:', error)
    console.error('[QuarkBrowser] 错误详情:', err.response || err.message)
    ElMessage.error('加载文件列表失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}

const handleItemClick = (item: QuarkFileItem) => {
  selectedFid.value = item.fid
  selectedItem.value = item
}

const handleItemDoubleClick = (item: QuarkFileItem) => {
  if (item.file_type === 0) {
    navigateTo(item.fid, item.file_name)
  }
}

const navigateTo = (fid: string, name?: string) => {
  if (name) {
    const index = breadcrumbs.value.findIndex(b => b.fid === fid)
    if (index >= 0) {
      breadcrumbs.value = breadcrumbs.value.slice(0, index + 1)
    } else {
      breadcrumbs.value.push({ fid, name })
    }
  } else {
    const index = breadcrumbs.value.findIndex(b => b.fid === fid)
    if (index >= 0) {
      breadcrumbs.value = breadcrumbs.value.slice(0, index + 1)
    }
  }

  currentPdirFid.value = fid
  currentPage.value = 1
  selectedFid.value = ''
  selectedItem.value = null
  loadFiles()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  loadFiles()
}

const confirmSelection = () => {
  if (!selectedItem.value || selectedItem.value.file_type !== 0) {
    ElMessage.warning('请选择一个文件夹')
    return
  }

  const path = breadcrumbs.value.map(b => b.name).join('/') + '/' + selectedItem.value.file_name
  emit('select', selectedFid.value, path)
  visible.value = false
}

const getFileType = (item: QuarkFileItem): string => {
  if (item.file_type === 0) return '文件夹'
  const ext = item.file_name.split('.').pop()?.toLowerCase()
  return ext ? ext.toUpperCase() : '文件'
}

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

watch(visible, (val) => {
  if (val) {
    currentPdirFid.value = '0'
    currentPage.value = 1
    selectedFid.value = ''
    selectedItem.value = null
    breadcrumbs.value = [{ fid: '0', name: '根目录' }]
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
  padding: 14px 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.42);
}

.breadcrumb-item {
  cursor: pointer;
}

.breadcrumb-item:hover {
  color: var(--primary-600);
}

.file-list {
  min-height: 320px;
  max-height: 520px;
  overflow-y: auto;
}

.list-header,
.file-item {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1.5fr;
  gap: 12px;
  padding: 14px 16px;
  align-items: center;
}

.list-header {
  position: sticky;
  top: 0;
  z-index: 1;
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: var(--font-semibold);
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  backdrop-filter: blur(12px);
}

.list-body {
  overflow: hidden;
  border: 1px solid var(--border-light);
  border-top: none;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  background: var(--surface-card);
}

.file-item {
  cursor: pointer;
  transition: background-color var(--transition-fast), transform var(--transition-fast);
}

.file-item + .file-item {
  border-top: 1px solid var(--border-light);
}

.file-item:hover {
  background: rgba(79, 141, 246, 0.08);
}

.file-item.selected {
  background: rgba(79, 141, 246, 0.12);
}

.file-item.folder {
  font-weight: var(--font-medium);
}

.file-item .name {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.folder-icon {
  color: var(--primary-600);
}

.file-icon-document {
  color: var(--text-tertiary);
}

.file-name {
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
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.selected-info {
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.no-selection {
  color: var(--text-tertiary);
}

.footer-actions {
  display: flex;
  gap: 12px;
}

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

  .dialog-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .footer-actions {
    justify-content: flex-end;
  }
}
</style>
