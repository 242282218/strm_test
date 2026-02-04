<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Folder, ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { fileManagerApi, type FileItem } from '../../api/file-manager'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  storage: string
  visible: boolean
}>()

const emit = defineEmits(['update:visible', 'confirm'])

const loading = ref(false)
const items = ref<FileItem[]>([])
const currentPath = ref('0')
const parentPath = ref<string | null>(null)

// 加载目录
const loadDir = async (path: string = currentPath.value) => {
  loading.value = true
  try {
    const res = await fileManagerApi.browse({
      storage: props.storage,
      path,
      size: 500 // 列表选择展示全部文件夹
    })
    // 过滤出文件夹
    items.value = res.data.items.filter(i => i.file_type === 'folder')
    currentPath.value = res.data.path
    parentPath.value = res.data.parent_path
  } catch (err) {
    ElMessage.error('加载文件夹失败')
  } finally {
    loading.value = false
  }
}

const handleBack = () => {
  if (parentPath.value !== null) loadDir(parentPath.value)
}

const handleFolderClick = (item: FileItem) => {
  loadDir(item.id)
}

const handleConfirm = () => {
  emit('confirm', currentPath.value)
  emit('update:visible', false)
}

const handleClose = () => {
  emit('update:visible', false)
}

onMounted(() => {
  loadDir()
})
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="选择目标目录"
    width="480px"
    @update:model-value="handleClose"
    append-to-body
    destroy-on-close
  >
    <div class="selector-container">
      <!-- 导航栏 -->
      <div class="selector-nav">
        <el-button-group size="small">
          <el-button :disabled="!parentPath" @click="handleBack">
            <el-icon><ArrowLeft /></el-icon>
            上一级
          </el-button>
          <el-button @click="loadDir('0')">根目录</el-button>
          <el-button @click="loadDir()">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-button-group>
        <div class="current-path" :title="currentPath">
          当前: {{ currentPath === '0' ? '根目录' : currentPath }}
        </div>
      </div>

      <!-- 目录列表 -->
      <div class="folder-list-wrapper" v-loading="loading">
        <div 
          v-for="item in items" 
          :key="item.id"
          class="folder-item"
          @click="handleFolderClick(item)"
        >
          <el-icon :size="20" color="#3b82f6"><Folder /></el-icon>
          <span class="name">{{ item.name }}</span>
        </div>
        <div v-if="!loading && items.length === 0" class="empty-hint">
          此目录下没有子文件夹
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleConfirm">移动到此处</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.selector-container {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.selector-nav {
  padding: 10px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.current-path {
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-list-wrapper {
  height: 320px;
  overflow-y: auto;
  padding: 8px 0;
}

.folder-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.folder-item:hover {
  background: #f1f5f9;
}

.name {
  font-size: 14px;
  color: #334155;
}

.empty-hint {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
  font-size: 14px;
}
</style>
