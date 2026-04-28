<template>
  <header class="page-header page-surface">
    <div class="header-content">
      <div class="header-left">
        <p v-if="eyebrow" class="header-kicker">{{ eyebrow }}</p>
        <h1 class="page-title">{{ title }}</h1>
        <p v-if="description" class="page-description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="header-right">
        <slot name="actions"></slot>
      </div>
    </div>
    <div v-if="$slots.tabs" class="header-tabs">
      <slot name="tabs"></slot>
    </div>
  </header>
</template>

<script setup lang="ts">
interface Props {
  title: string
  description?: string
  eyebrow?: string
}

defineProps<Props>()
</script>

<style scoped>
.page-header {
  position: relative;
  overflow: hidden;
  padding: clamp(22px, 2.5vw, 32px);
  margin-bottom: var(--page-section-gap);
  border-radius: calc(var(--radius-xl) + 4px);
}

.page-header::before {
  content: '';
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, rgba(79, 141, 246, 0.3), rgba(79, 141, 246, 0));
}

.header-content {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-6);
}

.header-left {
  flex: 1;
  min-width: 0;
}

.header-kicker {
  margin: 0 0 var(--space-2);
  font-size: 0.75rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.page-title {
  margin: 0;
  font-size: var(--text-h1);
  line-height: var(--leading-tight);
  font-weight: var(--font-bold);
  letter-spacing: var(--letter-spacing-tight);
  color: var(--text-primary);
}

.page-description {
  max-width: 720px;
  margin: var(--space-3) 0 0;
  font-size: 0.95rem;
  line-height: 1.65;
  color: var(--text-secondary);
}

.header-right {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
}

.header-tabs {
  margin-top: var(--space-5);
  padding-top: var(--space-5);
  border-top: 1px solid var(--border-light);
}

@media (max-width: 768px) {
  .page-header {
    padding: var(--space-5);
  }

  .header-content {
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-4);
  }

  .header-right {
    justify-content: flex-start;
  }
}
</style>
