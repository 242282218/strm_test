<template>
  <div class="state-indicator" :class="[stateClass, sizeClass]">
    <div v-if="state === 'loading'" class="state-content">
      <div class="loading-dots" aria-hidden="true">
        <span></span>
        <span></span>
        <span></span>
      </div>
      <p v-if="message" class="state-message">{{ message }}</p>
    </div>

    <div v-else-if="state === 'error'" class="state-content">
      <div class="state-icon error-icon">!</div>
      <p class="state-message">{{ message || '加载失败' }}</p>
      <button v-if="onRetry" class="retry-btn" @click="onRetry">重试</button>
    </div>

    <div v-else-if="state === 'success'" class="state-content">
      <div class="state-icon success-icon">✓</div>
      <p v-if="message" class="state-message">{{ message }}</p>
    </div>

    <div v-else-if="state === 'empty'" class="state-content">
      <div class="state-icon empty-icon">⌕</div>
      <p class="state-message">{{ message || '暂无数据' }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  state: 'loading' | 'error' | 'success' | 'empty'
  message?: string
  size?: 'small' | 'medium' | 'large'
  onRetry?: () => void
}

const props = withDefaults(defineProps<Props>(), {
  size: 'medium'
})

const stateClass = computed(() => `state-${props.state}`)
const sizeClass = computed(() => `size-${props.size}`)
</script>

<style scoped>
.state-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 180px;
  padding: var(--space-4) var(--space-5);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  background: var(--bg-soft);
}

.state-content {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  text-align: left;
}

.loading-dots {
  display: inline-flex;
  gap: 6px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary-500);
  animation: pulse-dot 1.4s infinite;
}

.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

.state-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  font-size: 0.9rem;
  font-weight: var(--font-bold);
}

.error-icon {
  background: rgba(228, 100, 108, 0.14);
  color: var(--danger-700);
}

.success-icon {
  background: rgba(51, 176, 122, 0.14);
  color: var(--success-700);
}

.empty-icon {
  background: rgba(120, 138, 167, 0.12);
  color: var(--text-tertiary);
}

.state-message {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.retry-btn {
  padding: 6px 12px;
  border: 0;
  border-radius: var(--radius-full);
  background: rgba(228, 100, 108, 0.14);
  color: var(--danger-700);
  cursor: pointer;
}

.size-small {
  min-width: 0;
  padding: var(--space-3) var(--space-4);
}

.size-small .state-message {
  font-size: 0.82rem;
}

.size-large {
  padding: var(--space-5) var(--space-6);
}

.size-large .state-icon {
  width: 34px;
  height: 34px;
}

@keyframes pulse-dot {
  0%, 60%, 100% {
    opacity: 0.35;
    transform: scale(0.8);
  }
  30% {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
