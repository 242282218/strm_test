<template>
  <Transition name="slide-fade">
    <div v-show="visible" class="results-info-bar page-surface">
      <div class="results-info">
        <div class="info-chip">
          <el-icon><Collection /></el-icon>
          <span>仅展示夸克资源</span>
        </div>
        <span class="info-note">优先查看评分与来源质量更高的结果。</span>
      </div>
      <div class="results-sort">
        <span class="sort-pill">默认按评分排序</span>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { Collection } from '@/components/icons'

defineProps<{
  visible: boolean
}>()
</script>

<style scoped>
.results-info-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: 16px 20px;
  margin-bottom: var(--page-section-gap);
}

.results-info {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.info-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 0 12px;
  border-radius: var(--radius-full);
  background: var(--surface-accent-soft);
  color: var(--primary-700);
  font-size: 0.82rem;
  font-weight: var(--font-semibold);
}

.info-note {
  font-size: 0.86rem;
  color: var(--text-secondary);
}

.sort-pill {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: var(--radius-full);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: var(--font-medium);
}

.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.2s ease-in;
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}

@media (max-width: 768px) {
  .results-info-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .results-sort {
    align-self: flex-start;
  }
}
</style>
