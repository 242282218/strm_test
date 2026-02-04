<script setup lang="ts">
import { useFileManagerStore } from '../../stores/file-manager'
import { Folder, Document } from '@element-plus/icons-vue'

const store = useFileManagerStore()

const handleItemClick = (item: any) => {
  if (item.file_type === 'folder') {
    store.browse(item.id)
  }
}

const formatSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const handleSelectionChange = (selection: any[]) => {
  store.selectedIds.clear()
  selection.forEach(item => store.selectedIds.add(item.id))
}
</script>

<template>
  <div class="list-container">
    <el-table
      :data="store.items"
      style="width: 100%"
      @selection-change="handleSelectionChange"
      @row-click="handleItemClick"
      row-class-name="file-row"
    >
      <el-table-column type="selection" width="55" />
      
      <el-table-column label="名称">
        <template #default="{ row }">
          <div class="name-cell">
            <el-icon v-if="row.file_type === 'folder'" :size="20" color="#3b82f6"><Folder /></el-icon>
            <el-icon v-else :size="20" color="#94a3b8"><Document /></el-icon>
            <span class="file-name">{{ row.name }}</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="大小" width="120">
        <template #default="{ row }">
          {{ row.file_type === 'folder' ? '-' : formatSize(row.size) }}
        </template>
      </el-table-column>

      <el-table-column label="修改日期" width="200">
        <template #default="{ row }">
          {{ formatDate(row.updated_at) }}
        </template>
      </el-table-column>
      
      <el-table-column label="操作" width="120" align="right">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.list-container {
  padding: 0;
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-name {
  font-size: 14px;
  color: #1e293b;
}

:deep(.file-row) {
  cursor: pointer;
  transition: background 0.2s;
}

:deep(.file-row:hover) {
  background: #f8fafc !important;
}
</style>
