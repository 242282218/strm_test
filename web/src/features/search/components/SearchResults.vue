<template>
  <section class="results-section">
    <div class="results-header page-surface">
      <div class="results-info">
        <span class="results-count">找到 <strong>{{ total }}</strong> 个结果</span>
        <span class="results-time">耗时 {{ searchTime }}ms</span>
      </div>
      <div class="view-toggle">
        <el-radio-group :model-value="viewMode" size="small" @update:model-value="$emit('update:viewMode', $event)">
          <el-radio-button value="grid">
            <el-icon><Grid /></el-icon>
          </el-radio-button>
          <el-radio-button value="list">
            <el-icon><List /></el-icon>
          </el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <TransitionGroup
      v-if="viewMode === 'grid'"
      name="grid"
      tag="div"
      class="results-grid"
    >
      <SearchResultCard
        v-for="(item, index) in results"
        :key="item.id"
        :item="item"
        :animation-delay="index * 0.05"
        @open-link="$emit('open-link', $event)"
        @save="$emit('save', $event)"
      />
    </TransitionGroup>

    <TransitionGroup
      v-else
      name="list"
      tag="div"
      class="results-list"
    >
      <SearchResultItem
        v-for="(item, index) in results"
        :key="item.id"
        :item="item"
        :animation-delay="index * 0.05"
        @open-link="$emit('open-link', $event)"
        @save="$emit('save', $event)"
      />
    </TransitionGroup>

    <div v-if="hasMore" class="load-more">
      <el-button
        type="primary"
        plain
        size="large"
        :loading="loadingMore"
        @click="$emit('load-more')"
      >
        加载更多
      </el-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { Grid, List } from '@/components/icons'
import SearchResultCard from './SearchResultCard.vue'
import SearchResultItem from './SearchResultItem.vue'
import type { CloudLink, SearchResult } from '@/api/search'
import type { ViewMode } from '@/stores/search'

defineProps<{
  results: SearchResult[]
  total: number
  searchTime: number
  viewMode: ViewMode
  hasMore: boolean
  loadingMore: boolean
}>()

defineEmits<{
  'update:viewMode': [mode: ViewMode]
  'open-link': [link: CloudLink]
  'save': [item: SearchResult]
  'load-more': []
}>()
</script>

<style scoped>
.results-section {
  display: flex;
  flex-direction: column;
  gap: var(--page-section-gap);
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: 18px 20px;
}

.results-info {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.results-count {
  font-size: 0.96rem;
  color: var(--text-secondary);
}

.results-count strong {
  color: var(--text-primary);
  font-size: 1.15rem;
  font-weight: var(--font-semibold);
}

.results-time {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: var(--radius-full);
  background: rgba(120, 138, 167, 0.12);
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-5);
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.load-more {
  display: flex;
  justify-content: center;
  padding: var(--space-3) 0 var(--space-6);
}

@media (max-width: 768px) {
  .results-header {
    flex-direction: column;
    align-items: stretch;
  }

  .view-toggle {
    align-self: flex-start;
  }

  .results-grid {
    grid-template-columns: 1fr;
  }
}
</style>
