<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useFileManagerStore } from '../stores/file-manager'
import FileToolbar from '../components/file-manager/FileToolbar.vue'
import FileGrid from '../components/file-manager/FileGrid.vue'
import FileList from '../components/file-manager/FileList.vue'
import FileSelectorDialog from '../components/file-manager/FileSelectorDialog.vue'
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
  } catch (err) {
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
  <div class="file-manager-container">
    <!-- 顶部工具栏 -->
    <FileToolbar 
      @refresh="handleRefresh"
      @delete="handleDelete"
    />

    <!-- 内容区域 -->
    <div class="file-content-wrapper" v-loading="store.loading">
      <transition name="fade" mode="out-in">
        <FileGrid v-if="store.viewMode === 'grid'" />
        <FileList v-else />
      </transition>

      <!-- 空状态 -->
      <div v-if="!store.loading && store.items.length === 0" class="empty-state">
        <el-empty description="此文件夹为空" />
      </div>
    </div>

    <!-- 批量操作浮层 (仅在有选中项时显示) -->
    <transition name="slide-up">
      <div v-if="store.selectedIds.size > 0" class="batch-action-bar">
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

    <!-- 移动目录选择弹窗 -->
    <FileSelectorDialog 
      v-if="moveDialogVisible"
      v-model:visible="moveDialogVisible"
      :storage="store.currentStorage"
      @confirm="handleMoveConfirm"
    />
  </div>
</template>

<style scoped>
.file-manager-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px;
  background: #f8fafc;
  overflow: hidden;
}

.file-content-wrapper {
  flex: 1;
  overflow-y: auto;
  margin-top: 16px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
  position: relative;
  min-height: 400px;
}

/* 玻璃拟态批量操作条 */
.batch-action-bar {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(0, 0, 0, 0.05);
  padding: 12px 24px;
  border-radius: 99px;
  display: flex;
  align-items: center;
  gap: 24px;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  z-index: 100;
}

.selection-info {
  font-size: 14px;
  color: #64748b;
}

.selection-info span {
  color: #3b82f6;
  font-weight: 600;
  margin: 0 4px;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

/* 动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translate(-50%, 40px);
  opacity: 0;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}
</style>
