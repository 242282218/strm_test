<template>
  <el-container class="layout-container">
    <AppSidebar />

    <el-container class="layout-shell">
      <el-main class="main-content">
        <div class="content-shell">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <div v-if="Component" class="page-frame">
                <component :is="Component" />
              </div>
            </transition>
          </router-view>
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { AppSidebar } from '@/components/layout'

defineOptions({
  name: 'LayoutView'
})
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 0% 0%, rgba(116, 168, 255, 0.2), transparent 24%),
    radial-gradient(circle at 100% 0%, rgba(127, 113, 234, 0.12), transparent 18%),
    var(--bg-secondary);
}

.layout-shell {
  min-width: 0;
  background: transparent;
}

.main-content {
  padding: 0;
  overflow-y: auto;
  background: transparent;
}

.content-shell {
  width: min(100%, var(--page-max-width));
  margin: 0 auto;
  padding: var(--page-gutter);
}

.page-frame {
  min-height: calc(100vh - (var(--page-gutter) * 2));
}

.fade-enter-active,
.fade-leave-active {
  transition:
    opacity var(--transition-fast),
    transform var(--transition-fast);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translate3d(0, 10px, 0);
}

@media (max-width: 768px) {
  .content-shell {
    padding-inline: 0;
    padding-top: var(--space-2);
  }

  .page-frame {
    min-height: auto;
  }
}
</style>
