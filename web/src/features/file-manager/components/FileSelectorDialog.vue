<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Folder, ArrowLeft, Refresh, FolderOpened } from '@/components/icons'
import { fileManagerApi, type FileItem } from '@/features/file-manager/api/file-manager'
import EmptyState from '@/components/EmptyState.vue'
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

const currentPathLabel = computed(() => (currentPath.value === '0' ? '根目录' : currentPath.value))

const loadDir = async (path: string = currentPath.value) => {
  loading.value = true
  try {
    const res = await fileManagerApi.browse({
      storage: props.storage,
      path,
      size: 500,
    })
    items.value = res.data.items.filter((item) => item.file_type === 'folder')
    currentPath.value = res.data.path
    parentPath.value = res.data.parent_path
  } catch {
    ElMessage.error('加载文件夹失败')
  } finally {
    loading.value = false
  }
}

const handleBack = () => {
  if (parentPath.value !== null) {
    loadDir(parentPath.value)
  }
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
    width="520px"
    @update:model-value="handleClose"
    append-to-body
    destroy-on-close
  >
    <div class="selector-shell">
      <div class="selector-toolbar">
        <el-button-group>
          <el-button :disabled="!parentPath" @click="handleBack">
            <el-icon><ArrowLeft /></el-icon>
            上一级
          </el-button>
          <el-button @click="loadDir('0')">根目录</el-button>
          <el-button @click="loadDir()">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </el-button-group>
      </div>

      <div class="selector-path-card" :title="currentPath">
        <span class="path-label">当前目录</span>
        <span class="path-value">{{ currentPathLabel }}</span>
      </div>

      <div class="folder-list-wrapper" v-loading="loading">
        <div v-if="items.length > 0" class="folder-list">
          <button
            v-for="item in items"
            :key="item.id"
            type="button"
            class="folder-item"
            @click="handleFolderClick(item)"
          >
            <div class="folder-icon">
              <el-icon :size="18"><Folder /></el-icon>
            </div>
            <div class="folder-copy">
              <span class="folder-name">{{ item.name }}</span>
              <span class="folder-hint">点击进入此目录</span>
            </div>
          </button>
        </div>
        <div v-else-if="!loading" class="selector-empty-state">
          <EmptyState
            :icon="FolderOpened"
            title="此目录暂无可选文件夹"
            description="可以返回上级目录，或直接将选中内容移动到当前目录。"
          />
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
.selector-shell {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.selector-toolbar {
  display: flex;
  justify-content: flex-start;
}

.selector-path-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--bg-soft);
}

.path-label {
  font-size: 0.74rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.path-value {
  font-size: 0.92rem;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-list-wrapper {
  min-height: 320px;
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid var(--border-light);
  border-radius: calc(var(--radius-xl) - 2px);
  background: var(--bg-soft);
}

.folder-list {
  display: flex;
  flex-direction: column;
  padding: 10px;
  gap: 10px;
}

.folder-item {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 14px 16px;
  border: 1px solid transparent;
  border-radius: var(--radius-lg);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background-color var(--transition-fast),
    transform var(--transition-fast);
}

.folder-item:hover {
  border-color: var(--border-light);
  background: var(--surface-accent-soft);
  transform: translateY(-1px);
}

.folder-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: var(--surface-accent-soft);
  color: var(--primary-600);
  flex-shrink: 0;
}

.folder-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.folder-name {
  font-size: 0.92rem;
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.folder-hint {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.selector-empty-state {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .selector-toolbar {
    overflow-x: auto;
  }

  .folder-list-wrapper,
  .selector-empty-state {
    min-height: 280px;
    max-height: 280px;
  }
}
</style>
