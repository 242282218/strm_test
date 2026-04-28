<script setup lang="ts">
import { ref } from 'vue'
import { useFileManagerStore } from '@/features/file-manager/stores/file-manager'
import { Search, Refresh, Grid, List as ListIcon, FolderAdd, Upload, ArrowLeft } from '@/components/icons'

const store = useFileManagerStore()
const searchQuery = ref('')
defineEmits(['refresh', 'delete'])

const handleBack = () => {
  if (store.parentPath !== null) {
    store.browse(store.parentPath)
  }
}
</script>

<template>
  <div class="toolbar-container">
    <div class="left-group">
      <div class="path-nav">
        <el-button-group size="default">
          <el-button @click="handleBack" :disabled="!store.parentPath">
            <el-icon><ArrowLeft /></el-icon>
            返回上一级
          </el-button>
          <el-button @click="store.browse('0')">
            根目录
          </el-button>
          <el-button @click="store.browse()">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </el-button-group>
        <span class="current-path">/ {{ store.currentPath === '0' ? '' : store.currentPath }}</span>
      </div>
    </div>

    <div class="right-group">
      <el-input
        v-model="searchQuery"
        placeholder="搜索文件..."
        class="search-input"
        :prefix-icon="Search"
        clearable
      />

      <el-radio-group v-model="store.viewMode" size="default" class="view-toggle">
        <el-radio-button value="grid"><el-icon><Grid /></el-icon></el-radio-button>
        <el-radio-button value="list"><el-icon><ListIcon /></el-icon></el-radio-button>
      </el-radio-group>

      <el-button-group>
        <el-button type="primary" :icon="FolderAdd">新建文件夹</el-button>
        <el-button type="success" :icon="Upload">上传</el-button>
      </el-button-group>
    </div>
  </div>
</template>

<style scoped>
.toolbar-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
}

.left-group,
.right-group {
  display: flex;
  align-items: center;
  gap: 14px;
}

.right-group {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.path-nav {
  display: flex;
  align-items: center;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.28);
}

.current-path {
  margin-left: 12px;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.88rem;
  color: var(--text-secondary);
}

.search-input {
  width: 240px;
}

.view-toggle :deep(.el-radio-button__inner) {
  min-width: 44px;
  padding-inline: 12px;
}

@media (max-width: 1024px) {
  .toolbar-container {
    flex-direction: column;
    align-items: stretch;
  }

  .left-group,
  .right-group {
    width: 100%;
  }

  .right-group {
    justify-content: space-between;
  }

  .search-input {
    flex: 1;
    min-width: 220px;
  }
}

@media (max-width: 768px) {
  .path-nav,
  .right-group {
    flex-wrap: wrap;
  }

  .current-path {
    max-width: 100%;
    width: 100%;
    margin-left: 0;
    margin-top: 10px;
  }

  .search-input {
    width: 100%;
  }
}
</style>
