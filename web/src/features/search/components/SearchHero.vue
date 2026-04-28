<template>
  <section class="search-hero page-surface">
    <div class="hero-content">
      <div class="hero-copy">
        <p class="hero-kicker">搜索中心</p>
        <h1 class="hero-title">资源搜索</h1>
        <p class="hero-supporting">
          聚焦夸克网盘资源检索，把搜索入口、状态说明与结果区收敛到同一套页面层级。
        </p>
      </div>
      <div class="hero-search-slot">
        <slot></slot>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
</script>

<style scoped>
.search-hero {
  padding: clamp(22px, 2.8vw, 34px);
  margin-bottom: var(--page-section-gap);
}

.hero-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.hero-copy {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-width: 720px;
}

.hero-kicker {
  margin: 0;
  font-size: 0.75rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.hero-title {
  margin: 0;
  font-size: var(--text-h1);
  line-height: var(--leading-tight);
  font-weight: var(--font-bold);
  letter-spacing: var(--letter-spacing-tight);
  color: var(--text-primary);
}

.hero-supporting {
  margin: 0;
  max-width: 640px;
  font-size: 0.95rem;
  line-height: 1.65;
  color: var(--text-secondary);
}

.hero-search-slot {
  width: 100%;
}

:deep(.hero-search-slot .search-box-container) {
  max-width: none;
  margin: 0;
}

@media (max-width: 768px) {
  .search-hero {
    padding: var(--space-5);
  }
}
</style>
