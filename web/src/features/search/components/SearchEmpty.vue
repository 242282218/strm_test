<template>
  <div v-if="type === 'empty'" class="search-empty-shell page-surface">
    <EmptyState
      :icon="Search"
      title="暂无匹配结果"
      description="试试更具体的片名、年份或资源关键词，结果会更准确。"
    />
  </div>

  <section v-else class="search-guide-shell page-surface">
    <div class="guide-copy">
      <p class="guide-kicker">开始一次搜索</p>
      <h2 class="guide-title">先输入片名，再逐步收窄结果</h2>
      <p class="guide-description">
        保持搜索、筛选提示与结果区同一视觉节奏，减少旧样板页式展示噪音。
      </p>
    </div>

    <div class="search-guide-list">
      <article v-for="item in guideItems" :key="item.title" class="search-guide-item">
        <div class="guide-icon">
          <el-icon :size="18">
            <component :is="item.icon" />
          </el-icon>
        </div>
        <div class="guide-item-copy">
          <h3>{{ item.title }}</h3>
          <p>{{ item.description }}</p>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from '@/components/EmptyState.vue'
import { Search, Filter, Download } from '@/components/icons'

const guideItems = [
  {
    icon: Search,
    title: '输入片名或关键词',
    description: '优先使用明确片名、年份或主演信息，让结果更快收敛。',
  },
  {
    icon: Filter,
    title: '优先查看评分更高的结果',
    description: '结果区会保持紧凑排序信息，方便你快速判断资源质量。',
  },
  {
    icon: Download,
    title: '确认可用后再一键转存',
    description: '找到合适资源后再进入转存动作，避免无效操作打断浏览节奏。',
  },
]

defineProps<{
  type: 'empty' | 'initial'
}>()
</script>

<style scoped>
.search-empty-shell,
.search-guide-shell {
  overflow: hidden;
}

.search-guide-shell {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  padding: clamp(24px, 3vw, 32px);
}

.guide-copy {
  max-width: 680px;
}

.guide-kicker {
  margin: 0 0 var(--space-2);
  font-size: 0.75rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.guide-title {
  margin: 0;
  font-size: var(--text-h2);
  line-height: 1.2;
  color: var(--text-primary);
}

.guide-description {
  margin: var(--space-3) 0 0;
  font-size: 0.92rem;
  line-height: 1.65;
  color: var(--text-secondary);
}

.search-guide-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.search-guide-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: 18px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--bg-soft);
}

.guide-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 14px;
  background: var(--surface-accent-soft);
  color: var(--primary-600);
  flex-shrink: 0;
}

.guide-item-copy h3 {
  margin: 0;
  font-size: 0.92rem;
  color: var(--text-primary);
}

.guide-item-copy p {
  margin: 8px 0 0;
  font-size: 0.84rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

@media (max-width: 1024px) {
  .search-guide-list {
    grid-template-columns: 1fr;
  }
}
</style>
