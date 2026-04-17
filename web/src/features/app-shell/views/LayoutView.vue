<template>
  <el-container class="layout-container">
    <AppSidebar />

    <el-container class="layout-shell">
      <div class="layout-shell-inner">
        <AppHeader />

        <el-main class="main-content">
          <div class="content-shell">
            <router-view v-slot="{ Component }">
              <transition name="fade" mode="out-in">
                <div v-if="Component" class="page-frame animate-slide-in-up">
                  <component :is="Component" />
                </div>
              </transition>
            </router-view>
          </div>
        </el-main>
      </div>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { AppHeader, AppSidebar } from '@/components/layout'
import { provideShellNavigation } from '@/features/app-shell/shell-navigation'

defineOptions({
  name: 'LayoutView'
})

provideShellNavigation()
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 0% 0%, rgba(116, 168, 255, 0.22), transparent 24%),
    radial-gradient(circle at 100% 0%, rgba(127, 113, 234, 0.14), transparent 22%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.18), transparent 18%),
    var(--bg-secondary);
}

.layout-shell {
  position: relative;
  min-width: 0;
  overflow: hidden;
  background: transparent;
}

.layout-shell::before,
.layout-shell::after {
  content: '';
  position: absolute;
  pointer-events: none;
  filter: blur(16px);
}

.layout-shell::before {
  top: 4%;
  right: 8%;
  width: 260px;
  height: 260px;
  background: radial-gradient(circle, rgba(79, 141, 246, 0.14), transparent 70%);
}

.layout-shell::after {
  bottom: 10%;
  left: 6%;
  width: 220px;
  height: 220px;
  background: radial-gradient(circle, rgba(127, 113, 234, 0.12), transparent 72%);
}

.layout-shell-inner {
  position: relative;
  z-index: 1;
  display: flex;
  min-height: 100vh;
  flex-direction: column;
}

.main-content {
  padding: 0 0 var(--space-6);
  overflow-y: auto;
  background: transparent;
}

.content-shell {
  width: min(100%, var(--page-max-width));
  margin: 0 auto;
  padding: 0 var(--page-gutter) var(--page-gutter);
}

.page-frame {
  min-height: calc(100vh - var(--header-height) - (var(--page-gutter) * 2));
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
  .main-content {
    padding-bottom: var(--space-4);
  }

  .content-shell {
    padding-inline: var(--page-gutter);
    padding-bottom: var(--space-4);
  }

  .page-frame {
    min-height: auto;
  }
}
</style>
