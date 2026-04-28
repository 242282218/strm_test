<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useFileManagerStore } from '@/features/file-manager/stores/file-manager'
import FileToolbar from '@/features/file-manager/components/FileToolbar.vue'
import FileGrid from '@/features/file-manager/components/FileGrid.vue'
import FileList from '@/features/file-manager/components/FileList.vue'
import FileSelectorDialog from '@/features/file-manager/components/FileSelectorDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import { FolderOpened } from '@/components/icons'
import { ElMessage, ElMessageBox } from 'element-plus'

const store = useFileManagerStore()
const moveDialogVisible = ref(false)

onMounted(() => {
  store.browse()
})

const handleRefresh = () => {
  store.browse()
}

const handleMoveConfirm = async (targetPath: string) => {
  try {
    await store.moveItems(targetPath)
    ElMessage.success('移动成功')
  } catch {
    ElMessage.error('移动失败')
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${store.selectedIds.size} 个项目吗？此操作不可撤销。`,
      '警告',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
    await store.deleteSelected()
    ElMessage.success('删除成功')
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}
</script>

<template>
  <section class="file-manager-container">
    <div class="toolbar-shell page-surface">
      <FileToolbar @refresh="handleRefresh" @delete="handleDelete" />
    </div>

    <div class="file-content-wrapper page-surface" v-loading="store.loading">
      <transition name="fade" mode="out-in">
        <FileGrid v-if="store.viewMode === 'grid' && store.items.length > 0" />
        <FileList v-else-if="store.items.length > 0" />
        <div v-else class="empty-shell">
          <EmptyState
            :icon="FolderOpened"
            title="此文件夹为空"
            description="当前目录下还没有文件或文件夹，可以返回上级目录或刷新后重试。"
          />
        </div>
      </transition>
    </div>

    <transition name="slide-up">
      <div v-if="store.selectedIds.size > 0" class="batch-action-bar glass">
        <div class="selection-info">
          已选择 <span>{{ store.selectedIds.size }}</span> 个项目
        </div>
        <div class="action-buttons">
          <el-button type="primary" plain size="small" @click="moveDialogVisible = true">移动到</el-button>
          <el-button type="danger" size="small" @click="handleDelete">删除</el-button>
          <el-button size="small" @click="store.clearSelection()">取消</el-button>
        </div>
      </div>
    </transition>

    <FileSelectorDialog
      v-if="moveDialogVisible"
      v-model:visible="moveDialogVisible"
      :storage="store.currentStorage"
      @confirm="handleMoveConfirm"
    />
  </section>
</template>

<style scoped>
.file-manager-container {
  display: flex;
  flex-direction: column;
  gap: var(--page-section-gap);
  min-height: 100%;
}

.toolbar-shell {
  padding: 14px 18px;
}

.file-content-wrapper {
  position: relative;
  min-height: 460px;
  overflow: hidden;
}

.empty-shell {
  min-height: 460px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.batch-action-bar {
  position: fixed;
  bottom: 32px;
  left: 50%;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 14px 18px;
  border-radius: calc(var(--radius-xl) + 8px);
  transform: translateX(-50%);
}

.selection-info {
  color: var(--text-secondary);
  font-size: 0.92rem;
}

.selection-info span {
  color: var(--primary-700);
  font-weight: var(--font-semibold);
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-fast);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all var(--transition-normal) cubic-bezier(0.22, 1, 0.36, 1);
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translate(-50%, 24px);
  opacity: 0;
}

@media (max-width: 768px) {
  .toolbar-shell {
    padding: 12px 14px;
  }

  .file-content-wrapper,
  .empty-shell {
    min-height: 360px;
  }

  .batch-action-bar {
    width: calc(100% - 32px);
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .selection-info {
    text-align: center;
  }

  .action-buttons {
    width: 100%;
    justify-content: stretch;
    flex-wrap: wrap;
  }

  .action-buttons > * {
    flex: 1 1 0;
  }
}
</style>
