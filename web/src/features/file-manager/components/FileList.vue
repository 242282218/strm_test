<script setup lang="ts">
import { useFileManagerStore } from '@/features/file-manager/stores/file-manager'
import type { FileItem } from '@/features/file-manager/api/file-manager'
import { Folder, Document } from '@/components/icons'

const store = useFileManagerStore()

const handleItemClick = (item: FileItem) => {
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

const getMetaLabel = (item: FileItem) => {
  if (item.file_type === 'folder') {
    return '文件夹'
  }

  return item.extension?.toUpperCase() || '文件'
}

const handleSelectionChange = (selection: FileItem[]) => {
  store.selectedIds.clear()
  selection.forEach((item) => store.selectedIds.add(item.id))
}

const getRowClassName = ({ row }: { row: FileItem }) => {
  return store.selectedIds.has(row.id) ? 'file-row is-selected' : 'file-row'
}

const handleActionClick = (item: FileItem) => {
  if (item.file_type === 'folder') {
    store.browse(item.id)
  }
}
</script>

<template>
  <div class="file-list-shell">
    <div class="file-list-table">
      <el-table
        :data="store.items"
        style="width: 100%"
        :row-class-name="getRowClassName"
        @selection-change="handleSelectionChange"
        @row-click="handleItemClick"
      >
        <el-table-column type="selection" width="56" />

        <el-table-column label="名称" min-width="320">
          <template #default="{ row }">
            <div class="name-cell">
              <div class="name-icon" :class="row.file_type === 'folder' ? 'is-folder' : 'is-file'">
                <el-icon :size="18">
                  <Folder v-if="row.file_type === 'folder'" />
                  <Document v-else />
                </el-icon>
              </div>
              <div class="name-copy">
                <span class="file-name">{{ row.name }}</span>
                <span class="item-meta-pill">{{ getMetaLabel(row) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="大小" width="130">
          <template #default="{ row }">
            <span class="meta-text">
              {{ row.file_type === 'folder' ? '-' : formatSize(row.size) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="修改日期" min-width="200">
          <template #default="{ row }">
            <span class="meta-text">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" align="right">
          <template #default="{ row }">
            <el-button
              v-if="row.file_type === 'folder'"
              link
              type="primary"
              @click.stop="handleActionClick(row)"
            >
              进入
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.file-list-shell {
  padding: var(--space-4);
}

.file-list-table {
  overflow: hidden;
  border: 1px solid var(--border-light);
  border-radius: calc(var(--radius-xl) - 2px);
  background: var(--bg-soft);
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.name-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  flex-shrink: 0;
}

.name-icon.is-folder {
  color: var(--primary-600);
  background: var(--surface-accent-soft);
}

.name-icon.is-file {
  color: var(--text-tertiary);
  background: var(--bg-soft);
}

.name-copy {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
  flex-wrap: wrap;
}

.file-name {
  min-width: 0;
  font-size: 0.92rem;
  font-weight: var(--font-medium);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-meta-pill {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: var(--font-medium);
}

.meta-text {
  color: var(--text-secondary);
  font-size: 0.84rem;
}

:deep(.file-row) {
  cursor: pointer;
  transition: background-color var(--transition-fast);
}

:deep(.file-row:hover td.el-table__cell) {
  background: var(--surface-accent-soft) !important;
}

:deep(.file-row.is-selected td.el-table__cell) {
  background: var(--surface-accent-soft) !important;
}

:deep(.el-table td.el-table__cell) {
  padding-top: 16px;
  padding-bottom: 16px;
}

:deep(.el-table th.el-table__cell) {
  padding-top: 14px;
  padding-bottom: 14px;
}

@media (max-width: 768px) {
  .file-list-shell {
    padding: 0;
  }

  .name-copy {
    gap: var(--space-2);
  }

  .file-name {
    width: 100%;
  }
}
</style>
