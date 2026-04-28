<template>
  <div class="empty-state">
    <div class="empty-icon">
      <el-icon :size="iconSize">
        <component :is="icon" />
      </el-icon>
    </div>
    <h3 class="empty-title">{{ title }}</h3>
    <p class="empty-description">{{ description }}</p>
    <slot name="action">
      <el-button v-if="actionText" type="primary" @click="handleAction">
        {{ actionText }}
      </el-button>
    </slot>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

import { FolderOpened } from '@/components/icons'

interface Props {
  icon?: Component
  iconSize?: number
  title?: string
  description?: string
  actionText?: string
}

withDefaults(defineProps<Props>(), {
  icon: FolderOpened,
  iconSize: 72,
  title: '暂无数据',
  description: '当前没有可显示的内容'
})

const emit = defineEmits<{
  action: []
}>()

const handleAction = () => {
  emit('action')
}
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: clamp(48px, 6vw, 84px) 24px;
  text-align: center;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 112px;
  height: 112px;
  margin-bottom: var(--space-5);
  border-radius: 32px;
  background: rgba(120, 138, 167, 0.12);
  color: var(--text-tertiary);
}

.empty-title {
  margin: 0;
  font-size: var(--text-h3);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.empty-description {
  max-width: 420px;
  margin: var(--space-3) 0 var(--space-5);
  font-size: 0.92rem;
  line-height: 1.65;
  color: var(--text-secondary);
}
</style>
