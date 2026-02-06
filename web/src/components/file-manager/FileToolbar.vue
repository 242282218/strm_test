<script setup lang="ts">
import { ref } from 'vue'
import { useFileManagerStore } from '../../stores/file-manager'
import { Search, Refresh, Delete, Grid, List as ListIcon, FolderAdd, Upload, ArrowLeft } from '@element-plus/icons-vue'

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
      <!-- 路径导航 -->
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
      <!-- 搜索 -->
      <el-input
        v-model="searchQuery"
        placeholder="搜索文件..."
        class="search-input"
        :prefix-icon="Search"
        clearable
      />

      <!-- 视图切换 -->
      <el-radio-group v-model="store.viewMode" size="default" class="view-toggle">
        <el-radio-button value="grid"><el-icon><Grid /></el-icon></el-radio-button>
        <el-radio-button value="list"><el-icon><ListIcon /></el-icon></el-radio-button>
      </el-radio-group>

      <!-- 操作按钮 -->
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
  padding: 12px 0;
  gap: 20px;
}

.left-group, .right-group {
  display: flex;
  align-items: center;
  gap: 16px;
}

.path-nav {
  display: flex;
  align-items: center;
  background: white;
  padding: 4px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.current-path {
  margin-left: 12px;
  font-size: 14px;
  color: #64748b;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-input {
  width: 240px;
}

.view-toggle :deep(.el-radio-button__inner) {
  padding: 8px 12px;
}
</style>
