<template>
  <el-breadcrumb separator="/" class="app-breadcrumb">
    <el-breadcrumb-item v-for="(item, index) in visibleBreadcrumbs" :key="index">
      <span class="breadcrumb-text">{{ item.title }}</span>
    </el-breadcrumb-item>
  </el-breadcrumb>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

defineOptions({
  name: 'AppBreadcrumb'
})

const route = useRoute()

const breadcrumbs = computed(() => {
  const matched = route.matched.filter(item => item.meta?.title)
  return matched.map(item => ({
    title: item.meta.title as string,
    path: item.path
  }))
})

const visibleBreadcrumbs = computed(() => {
  if (breadcrumbs.value.length <= 1) {
    return breadcrumbs.value
  }

  return breadcrumbs.value.slice(-1)
})
</script>

<style scoped>
.app-breadcrumb {
  display: flex;
  align-items: center;
  gap: 2px;
  min-width: 0;
  font-size: 0.82rem;
  line-height: 1.35;
}

.app-breadcrumb :deep(.el-breadcrumb__item) {
  max-width: 100%;
}

.app-breadcrumb :deep(.el-breadcrumb__separator) {
  margin-inline: 8px;
  color: var(--text-tertiary);
  opacity: 0.72;
}

.app-breadcrumb :deep(.el-breadcrumb__inner),
.app-breadcrumb :deep(.el-breadcrumb__inner a) {
  display: inline-flex;
  min-width: 0;
  align-items: center;
}

.breadcrumb-text {
  display: inline-block;
  max-width: min(32vw, 260px);
  overflow-wrap: anywhere;
}

@media (max-width: 768px) {
  .app-breadcrumb {
    font-size: 0.78rem;
    row-gap: 4px;
  }

  .breadcrumb-text {
    max-width: min(56vw, 220px);
  }
}
</style>
