<template>
  <el-aside
    id="app-shell-sidebar-panel"
    :width="sidebarWidth"
    class="sidebar"
    :class="{
      'is-collapsed': isSidebarCollapsed,
      'is-mobile': isMobileViewport,
      'is-drawer-open': isMobileDrawerOpen
    }"
    :aria-hidden="String(isMobileViewport && !isMobileDrawerOpen)"
  >
    <transition name="fade">
      <button
        v-if="isMobileViewport && isMobileDrawerOpen"
        type="button"
        class="sidebar-backdrop"
        aria-label="关闭导航抽屉"
        @click="closeMobileDrawer"
      ></button>
    </transition>

    <div
      class="sidebar-shell glass"
      :class="{
        'is-collapsed': isSidebarCollapsed,
        'is-mobile': isMobileViewport,
        'is-drawer-open': isMobileDrawerOpen
      }"
    >
      <div class="logo-container" :class="{ collapsed: isSidebarCollapsed }">
        <div class="logo-mark">
          <el-icon size="22"><Cloudy /></el-icon>
        </div>
        <div v-show="!isSidebarCollapsed" class="logo-copy">
          <span class="logo-eyebrow">Smart Media</span>
          <span class="logo-text">Quark STRM</span>
          <span class="logo-caption">任务、刮削与播放链路的统一控制台</span>
        </div>
        <el-button
          v-if="isMobileViewport"
          class="mobile-close-button"
          link
          :icon="Fold"
          aria-label="关闭导航抽屉"
          @click="closeMobileDrawer"
        />
      </div>

      <section v-show="!isSidebarCollapsed" class="sidebar-overview card-subtle">
        <span class="sidebar-overview-label">Active Lane</span>
        <strong class="sidebar-overview-title">{{ currentSectionTitle }}</strong>
        <p class="sidebar-overview-copy">{{ navigationSummary }}</p>
      </section>

      <el-menu
        :default-active="currentPath"
        :default-openeds="defaultOpeneds"
        :collapse="isSidebarCollapsed"
        :collapse-transition="false"
        router
        class="sidebar-menu is-dense"
        :class="{ 'is-collapsed': isSidebarCollapsed }"
        @select="handleMenuSelect"
      >
        <template v-for="group in menuGroups" :key="group.title">
          <el-menu-item v-if="group.items.length === 1" :index="group.items[0]!.path">
            <el-icon>
              <component :is="getIconComponent(group.icon)" />
            </el-icon>
            <template #title>{{ group.items[0]!.title }}</template>
          </el-menu-item>

          <el-sub-menu v-else :index="group.title">
            <template #title>
              <el-icon>
                <component :is="getIconComponent(group.icon)" />
              </el-icon>
              <span>{{ group.title }}</span>
            </template>
            <el-menu-item
              v-for="item in group.items"
              :key="item.path"
              :index="item.path"
            >
              <el-icon>
                <component :is="getIconComponent(item.icon)" />
              </el-icon>
              <template #title>{{ item.title }}</template>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>

      <div class="sidebar-footer" :class="{ 'is-collapsed': isSidebarCollapsed }">
        <div class="sidebar-account" :class="{ 'is-collapsed': isSidebarCollapsed }">
          <UserDropdown :collapsed="isSidebarCollapsed" />
        </div>
        <el-button
          v-if="!isMobileViewport"
          class="collapse-button"
          link
          :icon="isSidebarCollapsed ? Expand : Fold"
          @click="toggleDesktopCollapse"
        />
      </div>
    </div>
  </el-aside>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Cloudy,
  Expand,
  Fold,
  getIconComponent
} from '@/components/icons'
import { useShellNavigation } from '@/features/app-shell/shell-navigation'
import UserDropdown from './UserDropdown.vue'

defineOptions({
  name: 'AppSidebar'
})

const route = useRoute()
const {
  isMobileViewport,
  isMobileDrawerOpen,
  isSidebarCollapsed,
  sidebarWidth,
  closeMobileDrawer,
  syncViewport,
  toggleDesktopCollapse
} = useShellNavigation()

interface MenuItem {
  path: string
  title: string
  icon: string
}

interface MenuGroup {
  title: string
  icon: string
  items: MenuItem[]
}

const menuGroups: MenuGroup[] = [
  {
    title: '概览',
    icon: 'Odometer',
    items: [
      { path: '/dashboard', title: '概览', icon: 'House' }
    ]
  },
  {
    title: '任务管理',
    icon: 'List',
    items: [
      { path: '/tasks', title: '任务管理', icon: 'List' }
    ]
  },
  {
    title: '资源管理',
    icon: 'Folder',
    items: [
      { path: '/search', title: '资源搜索', icon: 'Search' },
      { path: '/smart-rename', title: '智能重命名', icon: 'MagicStick' }
    ]
  },
  {
    title: '媒体刮削',
    icon: 'Film',
    items: [
      { path: '/scrape-pathes', title: '刮削目录', icon: 'FolderOpened' },
      { path: '/scrape-records', title: '刮削记录', icon: 'Document' },
      { path: '/settings/category-strategy', title: '分类策略', icon: 'CollectionTag' }
    ]
  },
  {
    title: '播放服务',
    icon: 'VideoPlay',
    items: [
      { path: '/proxy-service', title: '代理服务', icon: 'Link' },
      { path: '/webdav', title: 'WebDAV', icon: 'Folder' },
      { path: '/emby-monitor', title: 'Emby监控', icon: 'Monitor' }
    ]
  },
  {
    title: '通知服务',
    icon: 'Bell',
    items: [
      { path: '/notifications', title: '通知配置', icon: 'Message' },
      { path: '/notifications/history', title: '通知历史', icon: 'ChatDotSquare' }
    ]
  },
  {
    title: '系统管理',
    icon: 'Tools',
    items: [
      { path: '/config', title: '系统配置', icon: 'Setting' }
    ]
  }
]

const allMenuItems = menuGroups.flatMap(group => group.items)

const isRouteWithinItem = (routePath: string, itemPath: string) => {
  return routePath === itemPath || routePath.startsWith(`${itemPath}/`)
}

const matchedMenuItem = computed(() => {
  return [...allMenuItems]
    .filter(item => isRouteWithinItem(route.path, item.path))
    .sort((left, right) => right.path.length - left.path.length)[0] ?? null
})

const currentPath = computed(() => matchedMenuItem.value?.path || route.path)

const currentSectionTitle = computed(() => {
  return matchedMenuItem.value?.title || '控制台导航'
})

const navigationSummary = computed(() => {
  return `${menuGroups.length} 个业务区围绕任务、媒体与播放链路组织。`
})

const handleViewportChange = (event: MediaQueryListEvent) => {
  syncViewport(event.matches)
}

let mediaQuery: MediaQueryList | null = null

onMounted(() => {
  mediaQuery = window.matchMedia('(max-width: 768px)')
  syncViewport(mediaQuery.matches)
  mediaQuery.addEventListener('change', handleViewportChange)
})

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  mediaQuery?.removeEventListener('change', handleViewportChange)
})

const defaultOpeneds = computed(() => {
  const currentPathValue = route.path
  const openGroups: string[] = []

  menuGroups.forEach(group => {
    if (group.items.length > 1) {
      const isInGroup = group.items.some(item => isRouteWithinItem(currentPathValue, item.path))
      if (isInGroup) {
        openGroups.push(group.title)
      }
    }
  })

  return openGroups
})

const handleMenuSelect = () => {
  if (isMobileViewport.value) {
    closeMobileDrawer()
  }
}

watch(() => route.fullPath, () => {
  if (isMobileViewport.value) {
    closeMobileDrawer()
  }
})

watch([isMobileViewport, isMobileDrawerOpen], ([mobile, drawerOpen]) => {
  document.body.style.overflow = mobile && drawerOpen ? 'hidden' : ''
}, {
  immediate: true
})
</script>

<style scoped>
.sidebar {
  --sidebar-axis-size: 44px;
  --sidebar-item-height: 42px;
  --sidebar-menu-indent: 14px;
  --sidebar-submenu-indent: 42px;
  padding: var(--space-3);
  background: transparent;
  border-right: 0;
  transition: width var(--transition-normal);
}

.sidebar-backdrop {
  position: fixed;
  inset: 0;
  border: 0;
  background: var(--bg-overlay);
  cursor: pointer;
  z-index: calc(var(--z-modal) - 1);
}

.sidebar-shell {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 24px);
  padding: var(--space-3) 10px;
  border-radius: calc(var(--radius-2xl) + 2px);
  transition:
    transform var(--transition-normal),
    box-shadow var(--transition-normal);
}

.sidebar-shell.is-collapsed {
  padding-inline: 6px;
}

.logo-container {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 56px;
  padding: 6px 4px 10px;
}

.mobile-close-button {
  margin-left: auto;
  width: var(--sidebar-axis-size);
  height: var(--sidebar-axis-size);
  border-radius: 14px;
  color: var(--text-secondary);
}

.mobile-close-button:hover {
  background: rgba(79, 141, 246, 0.08);
  color: var(--text-primary);
}

.logo-container.collapsed {
  width: 100%;
  justify-content: center;
  padding: 4px 0 10px;
}

.logo-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--sidebar-axis-size);
  height: var(--sidebar-axis-size);
  border-radius: 14px;
  background: var(--gradient-primary);
  color: var(--text-inverse);
  box-shadow: 0 12px 28px rgba(79, 141, 246, 0.26);
  flex-shrink: 0;
}

.logo-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.logo-eyebrow {
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.logo-text {
  margin: 0;
  font-size: 0.96rem;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  white-space: nowrap;
}

.logo-caption {
  color: var(--text-tertiary);
  font-size: 0.75rem;
  line-height: 1.45;
}

.sidebar-overview {
  margin: 0 2px 14px;
}

.sidebar-overview-label {
  display: inline-flex;
  margin-bottom: 8px;
  color: var(--primary-700);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.sidebar-overview-title {
  display: block;
  color: var(--text-primary);
  font-size: 0.96rem;
  line-height: 1.35;
}

.sidebar-overview-copy {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
}

.sidebar-menu {
  width: 100%;
  flex: 1;
  border-right: none;
  padding: 4px 0;
  background: transparent;
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  min-height: var(--sidebar-item-height);
  height: var(--sidebar-item-height);
  margin: 4px 0;
  padding-left: var(--sidebar-menu-indent) !important;
  padding-right: var(--sidebar-menu-indent) !important;
  border-radius: 14px;
  color: var(--text-secondary);
}

.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(79, 141, 246, 0.08);
  color: var(--text-primary);
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: rgba(79, 141, 246, 0.12);
  color: var(--primary-700);
  box-shadow: inset 0 0 0 1px rgba(79, 141, 246, 0.14);
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item) {
  min-height: 40px;
  height: 40px;
  padding-left: var(--sidebar-submenu-indent) !important;
}

.sidebar-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: var(--text-primary);
}

.sidebar-menu :deep(.el-menu-item .el-icon),
.sidebar-menu :deep(.el-sub-menu__title .el-icon) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  min-width: 18px;
  margin-right: 10px;
  font-size: 18px;
}

.sidebar-menu :deep(.el-sub-menu__icon-arrow) {
  right: 14px;
  margin-top: 0;
}

.sidebar-menu.is-collapsed :deep(.el-menu-item),
.sidebar-menu.is-collapsed :deep(.el-sub-menu__title) {
  width: var(--sidebar-axis-size);
  margin-inline: auto;
  justify-content: center;
  padding-left: 0 !important;
  padding-right: 0 !important;
}

.sidebar-menu.is-collapsed :deep(.el-menu-item .el-menu-tooltip__trigger),
.sidebar-menu.is-collapsed :deep(.el-sub-menu__title .el-menu-tooltip__trigger) {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.sidebar-menu.is-collapsed :deep(.el-menu-item .el-icon),
.sidebar-menu.is-collapsed :deep(.el-sub-menu__title .el-icon) {
  margin-right: 0;
}

.sidebar-menu.is-collapsed :deep(.el-sub-menu__icon-arrow) {
  display: none;
}

.sidebar-menu.is-collapsed :deep(.el-sub-menu .el-menu-item) {
  padding-left: 0 !important;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}

.sidebar-footer.is-collapsed {
  align-items: center;
  padding-top: 8px;
}

.sidebar-account {
  width: 100%;
  display: flex;
}

.sidebar-account.is-collapsed {
  justify-content: center;
}

.sidebar-account :deep(.user-dropdown) {
  width: 100%;
}

.sidebar-account.is-collapsed :deep(.user-dropdown) {
  width: auto;
}

.collapse-button {
  width: var(--sidebar-axis-size);
  height: var(--sidebar-axis-size);
  align-self: center;
  border-radius: 14px;
  color: var(--text-secondary);
}

.collapse-button:hover {
  background: rgba(79, 141, 246, 0.08);
  color: var(--text-primary);
}

@media (max-width: 1024px) {
  .sidebar {
    padding: 10px;
  }

  .sidebar-shell {
    height: calc(100vh - 20px);
  }
}

@media (max-width: 768px) {
  .sidebar {
    padding: 0;
  }

  .sidebar.is-mobile {
    width: 0 !important;
    min-width: 0 !important;
    overflow: visible;
  }

  .sidebar-shell.is-mobile {
    position: fixed;
    inset: 0 auto 0 0;
    width: min(88vw, 320px);
    height: 100vh;
    padding: 18px 12px 16px;
    border-radius: 0 calc(var(--radius-2xl) + 2px) calc(var(--radius-2xl) + 2px) 0;
    transform: translate3d(-104%, 0, 0);
    z-index: var(--z-modal);
    overflow-y: auto;
  }

  .sidebar.is-drawer-open .sidebar-shell.is-mobile {
    transform: translate3d(0, 0, 0);
  }

  .logo-container {
    gap: 10px;
  }
}
</style>
