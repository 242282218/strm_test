<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useFileManagerStore } from '@/features/file-manager/stores/file-manager'
import { Folder } from '@/components/icons'
import type { FileItem } from '@/features/file-manager/api/file-manager'

const INITIAL_RENDER_COUNT = 60
const RENDER_STEP = 60

const store = useFileManagerStore()
const renderCount = ref(INITIAL_RENDER_COUNT)

const visibleItems = computed(() => store.items.slice(0, renderCount.value))
const hasMoreItems = computed(() => visibleItems.value.length < store.items.length)

watch(
  () => store.items,
  () => {
    renderCount.value = INITIAL_RENDER_COUNT
  },
  { deep: false }
)

const handleItemClick = (item: FileItem) => {
  if (item.file_type === 'folder') {
    store.browse(item.id)
  } else {
    store.toggleSelection(item.id)
  }
}

const loadMoreItems = () => {
  renderCount.value += RENDER_STEP
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
  <div class="grid-shell">
    <div class="grid-container">
      <div
        v-for="item in visibleItems"
        :key="item.id"
        class="file-card"
        :class="{ 'is-selected': store.selectedIds.has(item.id) }"
        @click="handleItemClick(item)"
      >
        <div class="checkbox-wrapper" @click.stop="store.toggleSelection(item.id)">
          <div class="custom-checkbox"></div>
        </div>

        <div class="card-content">
          <div class="icon-wrapper">
            <template v-if="item.file_type === 'folder'">
              <div class="folder-icon">
                <el-icon :size="42"><Folder /></el-icon>
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

          <div class="file-name" :title="item.name">
            {{ item.name }}
          </div>

          <div class="file-meta">
            {{ item.file_type === 'folder' ? '文件夹' : formatSize(item.size) }}
          </div>
        </div>
      </div>
    </div>

    <div v-if="store.items.length > INITIAL_RENDER_COUNT" class="grid-footer">
      <span class="grid-progress">已渲染 {{ visibleItems.length }} / {{ store.items.length }} 项</span>
      <el-button
        v-if="hasMoreItems"
        data-testid="file-grid-load-more"
        plain
        @click="loadMoreItems"
      >
        加载更多
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.grid-shell {
  display: grid;
  gap: var(--space-4);
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(156px, 1fr));
  gap: var(--space-4);
  padding: var(--space-5);
}

.file-card {
  position: relative;
  min-height: 176px;
  padding: 14px;
  border: 1px solid transparent;
  border-radius: var(--radius-xl);
  background: var(--surface-card);
  box-shadow: var(--shadow-xs);
  cursor: pointer;
  user-select: none;
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast),
    border-color var(--transition-fast),
    background-color var(--transition-fast);
}

.file-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
  border-color: var(--border-light);
}

.file-card.is-selected {
  border-color: rgba(79, 141, 246, 0.28);
  background: linear-gradient(180deg, rgba(79, 141, 246, 0.12), rgba(255, 255, 255, 0.88));
  box-shadow: 0 14px 30px rgba(79, 141, 246, 0.16);
}

.card-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 88px;
  height: 88px;
  margin-bottom: 14px;
}

.folder-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 88px;
  height: 88px;
  border-radius: 26px;
  color: var(--primary-600);
  background: rgba(79, 141, 246, 0.12);
}

.thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 18px;
  box-shadow: var(--shadow-xs);
}

.file-icon-placeholder {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  width: 64px;
  height: 76px;
  padding-bottom: 10px;
  border: 1px solid var(--border-light);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.54);
}

.ext-badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  background: rgba(120, 138, 167, 0.12);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: var(--font-semibold);
}

.file-name {
  width: 100%;
  font-size: 0.86rem;
  line-height: 1.45;
  color: var(--text-primary);
  font-weight: var(--font-medium);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  min-height: 2.9em;
}

.file-meta {
  margin-top: 6px;
  font-size: 0.75rem;
  color: var(--text-tertiary);
}

.checkbox-wrapper {
  position: absolute;
  top: 10px;
  left: 10px;
  opacity: 0;
  transition: opacity var(--transition-fast);
  z-index: 1;
}

.file-card:hover .checkbox-wrapper,
.file-card.is-selected .checkbox-wrapper {
  opacity: 1;
}

.custom-checkbox {
  width: 20px;
  height: 20px;
  border: 1.5px solid var(--border-medium);
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: var(--shadow-xs);
}

.is-selected .custom-checkbox {
  border-color: var(--primary-500);
  background: var(--primary-500);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20' fill='white'%3E%3Cpath fill-rule='evenodd' d='M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z' clip-rule='evenodd' /%3E%3C/svg%3E");
  background-size: contain;
}

.grid-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 0 var(--space-5) var(--space-5);
}

.grid-progress {
  color: var(--text-secondary);
  font-size: 0.82rem;
}

@media (max-width: 768px) {
  .grid-footer {
    flex-direction: column;
  }
}
</style>
