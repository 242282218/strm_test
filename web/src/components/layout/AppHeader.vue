<template>
  <el-header class="header">
    <div class="header-shell" :class="{ 'is-user-only': !hasBreadcrumbPanel }">
      <section class="header-context glass">
        <div class="context-copy">
          <div class="context-meta">
            <el-button
              v-if="isMobileViewport"
              class="header-menu-trigger"
              circle
              :icon="isMobileDrawerOpen ? Fold : Expand"
              :aria-expanded="String(isMobileDrawerOpen)"
              aria-controls="app-shell-sidebar-panel"
              aria-label="切换导航抽屉"
              @click="toggleMobileDrawer"
            />
            <span class="context-chip">Control Deck</span>
            <span class="context-note">媒体任务 · 数据观测 · 配置治理</span>
          </div>
          <h1 class="context-title">{{ pageTitle }}</h1>
          <p class="context-description">{{ pageDescription }}</p>
        </div>
      </section>

      <div class="header-rail" :class="{ 'is-user-only': !hasBreadcrumbPanel }">
        <div v-if="hasBreadcrumbPanel" class="header-breadcrumb-panel glass is-compact">
          <div class="header-breadcrumb">
            <Breadcrumb />
          </div>
        </div>
        <div class="header-user-panel">
          <UserDropdown :username="username" />
        </div>
      </div>
    </div>
  </el-header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Expand, Fold } from '@/components/icons'
import Breadcrumb from '@/components/Breadcrumb.vue'
import { useShellNavigation } from '@/features/app-shell/shell-navigation'
import UserDropdown from './UserDropdown.vue'

defineOptions({
  name: 'AppHeader'
})

interface Props {
  username?: string
}

const props = withDefaults(defineProps<Props>(), {
  username: '管理员'
})

const route = useRoute()
const { isMobileViewport, isMobileDrawerOpen, toggleMobileDrawer } = useShellNavigation()

const pageDescriptionMap: Record<string, string> = {
  Dashboard: '聚焦服务健康、任务趋势与缓存命中，让媒体管线状态保持一屏可读。',
  Tasks: '跟踪执行队列、进度与失败恢复，把批处理状态收敛到统一控制面。',
  Search: '快速定位网盘与媒体资源，缩短搜索、筛选与后续操作路径。',
  Rename: '保留基础重命名入口，适合快速批量修正文案与命名结构。',
  SmartRename: '围绕预览、执行与异常回看组织重命名流程，减少重复确认成本。',
  ScrapePaths: '梳理刮削目录与触发边界，避免来源路径和目标分类脱节。',
  ScrapeRecords: '回看刮削产出与失败轨迹，帮助快速定位元数据链路问题。',
  CategoryStrategy: '集中管理分类规则与目录映射，降低入库结构长期漂移。',
  EmbyMonitor: '查看播放监控、连接波动与异常信号，尽早暴露媒体服务风险。',
  ProxyService: '观察代理链路、流量入口与稳定性指标，降低播放回源的不确定性。',
  WebDAV: '集中查看挂载能力与连接入口，减少存储链路切换带来的上下文损耗。',
  Notifications: '统一配置通知通道与发送策略，避免跨渠道状态漂移。',
  NotificationHistory: '快速回看通知结果与失败记录，帮助定位消息链路问题。',
  Config: '集中管理认证、代理、通知与系统参数，保持配置改动可追踪。',
}

const pageTitle = computed(() => {
  const matchedTitles = route.matched
    .map(item => item.meta?.title)
    .filter((title): title is string => typeof title === 'string' && title.length > 0)

  return matchedTitles[matchedTitles.length - 1] || '控制台'
})

const pageDescription = computed(() => {
  const routeName = typeof route.name === 'string' ? route.name : ''
  return pageDescriptionMap[routeName] || '保持关键媒体链路、任务与配置状态可见，减少在视图之间来回切换。'
})

const hasBreadcrumbPanel = computed(() => {
  return route.matched.filter(item => typeof item.meta?.title === 'string' && item.meta.title.length > 0).length > 1
})

const username = computed(() => props.username)
</script>

<style scoped>
.header {
  height: auto;
  padding: 16px var(--page-gutter) 0;
  background: transparent;
}

.header-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 360px);
  gap: var(--space-4);
  align-items: stretch;
}

.header-shell.is-user-only {
  grid-template-columns: minmax(0, 1fr) auto;
}

.header-context {
  position: relative;
  overflow: hidden;
  min-height: var(--header-height);
  padding: 18px 22px;
  border-radius: calc(var(--radius-2xl) + 2px);
}

.header-context::before {
  content: '';
  position: absolute;
  inset: -40% auto auto 58%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79, 141, 246, 0.2), transparent 70%);
  pointer-events: none;
}

.context-copy {
  position: relative;
  z-index: 1;
  display: flex;
  min-height: 100%;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
}

.context-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.header-menu-trigger {
  display: inline-flex;
  flex-shrink: 0;
  border: 1px solid rgba(79, 141, 246, 0.16);
  background: rgba(79, 141, 246, 0.1);
  color: var(--primary-700);
}

.header-menu-trigger:hover {
  background: rgba(79, 141, 246, 0.16);
  color: var(--primary-800);
}

.context-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: var(--radius-full);
  background: rgba(79, 141, 246, 0.14);
  color: var(--primary-700);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.context-note {
  color: var(--text-tertiary);
  font-size: 0.82rem;
  line-height: 1.5;
}

.context-title {
  margin: 0;
  font-size: clamp(1.32rem, 1.05rem + 0.55vw, 1.85rem);
  line-height: 1.18;
  font-weight: var(--font-bold);
  letter-spacing: var(--letter-spacing-tight);
  color: var(--text-primary);
}

.context-description {
  max-width: 58ch;
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.92rem;
  line-height: 1.65;
}

.header-rail {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.header-rail.is-user-only {
  grid-template-columns: auto;
}

.header-breadcrumb-panel {
  min-width: 0;
  padding: 10px 14px;
  border-radius: calc(var(--radius-xl) + 2px);
}

.header-breadcrumb-panel.is-compact {
  backdrop-filter: blur(22px);
  -webkit-backdrop-filter: blur(22px);
}

.header-breadcrumb {
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: center;
}

.header-user-panel {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  flex-shrink: 0;
}

.header-user-panel :deep(.user-dropdown) {
  max-width: 100%;
}

.header-user-panel :deep(.user-dropdown .el-button:first-child) {
  padding-inline: 8px 12px;
}

.header-user-panel :deep(.user-trigger-content) {
  gap: 8px;
}

.header-user-panel :deep(.el-avatar) {
  --el-avatar-size: 28px;
}

.header-user-panel :deep(.el-dropdown__caret-button) {
  padding-inline: 8px;
}

.header-user-panel :deep(.username) {
  max-width: 10ch;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 0.84rem;
}

.header-breadcrumb :deep(.el-breadcrumb) {
  flex-wrap: wrap;
}

.header-breadcrumb :deep(.el-breadcrumb__inner),
.header-breadcrumb :deep(.el-breadcrumb__inner a) {
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}

.header-breadcrumb :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: var(--text-primary);
}

@media (max-width: 1024px) {
  .header-shell {
    grid-template-columns: 1fr;
  }

  .header-rail {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-rows: auto;
    align-items: center;
  }
}

@media (max-width: 768px) {
  .header {
    padding-top: 10px;
    padding-inline: var(--page-gutter);
  }

  .context-meta {
    gap: 8px;
  }

  .header-context,
  .header-breadcrumb-panel {
    padding-inline: 16px;
  }

  .header-context {
    min-height: auto;
    padding-block: 16px;
  }

  .context-title {
    font-size: 1.18rem;
  }

  .context-description {
    font-size: 0.86rem;
  }

  .context-note {
    display: none;
  }

  .header-rail {
    grid-template-columns: 1fr;
  }

  .header-user-panel {
    justify-content: flex-start;
  }
}
</style>
