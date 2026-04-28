<template>
  <div class="state-display" :class="[stateClass, sizeClass]">
    <div v-if="state === 'loading'" class="state-content">
      <div class="spinner-ring" aria-hidden="true">
        <div></div>
        <div></div>
        <div></div>
        <div></div>
      </div>
      <p v-if="message" class="state-message">{{ message }}</p>
    </div>

    <div v-else-if="state === 'error'" class="state-content error-content">
      <div class="state-icon error-icon">
        <el-icon><CircleClose /></el-icon>
      </div>
      <h3 class="state-title">{{ title || '加载失败' }}</h3>
      <p class="state-message">{{ message || '请求未成功完成，请重试。' }}</p>
      <el-button v-if="onRetry" type="danger" size="small" @click="onRetry">
        重试
      </el-button>
    </div>

    <div v-else-if="state === 'success'" class="state-content success-content">
      <div class="state-icon success-icon">
        <el-icon><CircleCheck /></el-icon>
      </div>
      <h3 v-if="title || message" class="state-title">{{ title || '处理完成' }}</h3>
      <p v-if="message" class="state-message">{{ message }}</p>
    </div>

    <div v-else-if="state === 'empty'" class="state-content empty-content">
      <div class="state-icon empty-icon">
        <el-icon :size="iconSize">
          <component :is="icon || FolderOpened" />
        </el-icon>
      </div>
      <h3 class="state-title">{{ title || '暂无数据' }}</h3>
      <p v-if="message" class="state-message">{{ message }}</p>
      <slot name="action">
        <el-button v-if="actionText" type="primary" @click="handleAction">
          {{ actionText }}
        </el-button>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue'
import { CircleClose, CircleCheck, FolderOpened } from '@element-plus/icons-vue'

interface Props {
  state: 'loading' | 'error' | 'success' | 'empty'
  message?: string
  title?: string
  size?: 'small' | 'medium' | 'large'
  icon?: Component
  iconSize?: number
  actionText?: string
  onRetry?: () => void
}

const props = withDefaults(defineProps<Props>(), {
  size: 'medium',
  iconSize: 52
})

const emit = defineEmits<{
  action: []
}>()

const stateClass = computed(() => `state-${props.state}`)
const sizeClass = computed(() => `size-${props.size}`)

const handleAction = () => {
  emit('action')
}
</script>

<style scoped>
.state-display {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 220px;
  padding: var(--space-8);
  border: 1px solid var(--border-light);
  border-radius: calc(var(--radius-xl) + 2px);
  background: var(--surface-card);
  box-shadow: var(--shadow-sm);
}

.state-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  width: min(100%, 440px);
  text-align: center;
}

.state-title {
  margin: 0;
  font-size: var(--text-h3);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.state-message {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.65;
  color: var(--text-secondary);
}

.state-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 24px;
  font-size: 28px;
}

.state-loading {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 253, 0.88));
}

.spinner-ring {
  position: relative;
  width: 52px;
  height: 52px;
}

.spinner-ring div {
  box-sizing: border-box;
  position: absolute;
  width: 52px;
  height: 52px;
  border: 3px solid var(--primary-500);
  border-color: var(--primary-500) transparent transparent transparent;
  border-radius: 50%;
  animation: spinner-ring 1.15s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

.spinner-ring div:nth-child(1) { animation-delay: -0.45s; }
.spinner-ring div:nth-child(2) { animation-delay: -0.3s; }
.spinner-ring div:nth-child(3) { animation-delay: -0.15s; }

.error-content .state-message,
.error-content .state-title {
  color: var(--danger-700);
}

.error-icon {
  color: var(--danger-700);
  background: rgba(228, 100, 108, 0.14);
}

.success-content .state-message,
.success-content .state-title {
  color: var(--success-700);
}

.success-icon {
  color: var(--success-700);
  background: rgba(51, 176, 122, 0.14);
}

.empty-icon {
  color: var(--text-tertiary);
  background: rgba(120, 138, 167, 0.12);
}

.size-small {
  min-height: 160px;
  padding: var(--space-5);
}

.size-small .state-content {
  gap: var(--space-2);
}

.size-small .state-icon {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  font-size: 22px;
}

.size-small .spinner-ring,
.size-small .spinner-ring div {
  width: 38px;
  height: 38px;
}

.size-small .state-message {
  font-size: 0.84rem;
}

.size-large {
  min-height: 320px;
  padding: var(--space-12);
}

.size-large .state-content {
  gap: var(--space-4);
}

.size-large .state-icon {
  width: 88px;
  height: 88px;
  border-radius: 28px;
  font-size: 34px;
}

.size-large .spinner-ring,
.size-large .spinner-ring div {
  width: 68px;
  height: 68px;
}

.size-large .spinner-ring div {
  border-width: 4px;
}

@keyframes spinner-ring {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
