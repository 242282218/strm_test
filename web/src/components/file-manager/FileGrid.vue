<script setup lang="ts">
import { useFileManagerStore } from '../../stores/file-manager'
import { Folder } from '@element-plus/icons-vue'

const store = useFileManagerStore()

const handleItemClick = (item: any) => {
  if (item.file_type === 'folder') {
    store.browse(item.id)
  } else {
    store.toggleSelection(item.id)
  }
}

const formatSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
</script>

<template>
  <div class="grid-container">
    <div 
      v-for="item in store.items" 
      :key="item.id"
      class="file-card"
      :class="{ 'is-selected': store.selectedIds.has(item.id) }"
      @click="handleItemClick(item)"
    >
      <!-- 选择勾选框 (平时隐藏，悬浮或选中时显示) -->
      <div class="checkbox-wrapper" @click.stop="store.toggleSelection(item.id)">
        <div class="custom-checkbox"></div>
      </div>

      <div class="card-content">
        <!-- 图标/缩略图 -->
        <div class="icon-wrapper">
          <template v-if="item.file_type === 'folder'">
            <div class="folder-icon">
              <el-icon :size="48" color="#3b82f6"><Folder /></el-icon>
            </div>
          </template>
          <template v-else-if="item.thumbnail">
            <img :src="item.thumbnail" class="thumbnail" />
          </template>
          <template v-else>
            <div class="file-icon-placeholder">
              <span class="ext-badge">{{ item.extension?.toUpperCase() || 'FILE' }}</span>
            </div>
          </template>
        </div>

        <!-- 名字 -->
        <div class="file-name" :title="item.name">
          {{ item.name }}
        </div>
        
        <!-- 大小/元数据 -->
        <div class="file-meta">
          {{ item.file_type === 'folder' ? '文件夹' : formatSize(item.size) }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 140px));
  gap: 16px;
  padding: 24px;
  justify-content: start;
}

.file-card {
  position: relative;
  width: 140px;
  height: 160px;
  padding: 12px;
  border-radius: 12px;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  cursor: pointer;
  user-select: none;
}

.file-card:hover {
  background: #f1f5f9;
}

.file-card.is-selected {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.card-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.icon-wrapper {
  width: 80px;
  height: 80px;
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 12px;
}

.thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 8px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.file-icon-placeholder {
  width: 60px;
  height: 72px;
  background: #f8fafc;
  border: 2px solid #e2e8f0;
  border-radius: 4px;
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 8px;
}

.ext-badge {
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  background: white;
  padding: 2px 4px;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
}

.file-name {
  width: 100%;
  font-size: 13px;
  color: #1e293b;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.4;
  height: 2.8em;
}

.file-meta {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}

/* 复选框逻辑 */
.checkbox-wrapper {
  position: absolute;
  top: 8px;
  left: 8px;
  opacity: 0;
  transition: opacity 0.2s;
  z-index: 10;
}

.file-card:hover .checkbox-wrapper,
.file-card.is-selected .checkbox-wrapper {
  opacity: 1;
}

.custom-checkbox {
  width: 18px;
  height: 18px;
  border: 2px solid #cbd5e1;
  background: white;
  border-radius: 4px;
}

.is-selected .custom-checkbox {
  background: #3b82f6;
  border-color: #3b82f6;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20' fill='white'%3E%3Cpath fill-rule='evenodd' d='M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z' clip-rule='evenodd' /%3E%3C/svg%3E");
  background-size: contain;
}
</style>
