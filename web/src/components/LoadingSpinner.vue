<template>
  <div class="loading-spinner" :class="sizeClass">
    <div class="spinner-ring" aria-hidden="true">
      <div></div>
      <div></div>
      <div></div>
      <div></div>
    </div>
    <p v-if="text" class="loading-text">{{ text }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  size?: 'small' | 'medium' | 'large'
  text?: string
}

const props = withDefaults(defineProps<Props>(), {
  size: 'medium'
})

const sizeClass = computed(() => `size-${props.size}`)
</script>

<style scoped>
.loading-spinner {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
}

.spinner-ring {
  position: relative;
}

.spinner-ring div {
  box-sizing: border-box;
  position: absolute;
  border: 3px solid var(--primary-500);
  border-color: var(--primary-500) transparent transparent transparent;
  border-radius: 50%;
  animation: spinner-ring 1.15s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

.spinner-ring div:nth-child(1) { animation-delay: -0.45s; }
.spinner-ring div:nth-child(2) { animation-delay: -0.3s; }
.spinner-ring div:nth-child(3) { animation-delay: -0.15s; }

.size-small .spinner-ring,
.size-small .spinner-ring div {
  width: 24px;
  height: 24px;
}

.size-small .spinner-ring div {
  border-width: 2px;
}

.size-medium .spinner-ring,
.size-medium .spinner-ring div {
  width: 44px;
  height: 44px;
}

.size-large .spinner-ring,
.size-large .spinner-ring div {
  width: 64px;
  height: 64px;
}

.size-large .spinner-ring div {
  border-width: 4px;
}

.loading-text {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
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
