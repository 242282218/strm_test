<template>
  <el-container class="layout-container">
    <el-aside :width="isCollapse ? '64px' : '240px'" class="sidebar">
      <div class="logo-container">
        <el-icon size="32" class="logo-icon"><Cloudy /></el-icon>
        <span v-show="!isCollapse" class="logo-text">Quark STRM</span>
      </div>

      <el-menu
        :default-active="$route.path"
        :default-openeds="defaultOpeneds"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
        class="sidebar-menu"
      >
        <template v-for="group in menuGroups" :key="group.title">
          <!-- 单一项（概览） -->
          <el-menu-item v-if="group.items.length === 1" :index="group.items[0].path">
            <el-icon>
              <component :is="group.icon" />
            </el-icon>
            <template #title>{{ group.items[0].title }}</template>
          </el-menu-item>
          
          <!-- 分组菜单 -->
          <el-sub-menu v-else :index="group.title">
            <template #title>
              <el-icon>
                <component :is="group.icon" />
              </el-icon>
              <span>{{ group.title }}</span>
            </template>
            <el-menu-item 
              v-for="item in group.items" 
              :key="item.path" 
              :index="item.path"
            >
              <el-icon>
                <component :is="item.icon" />
              </el-icon>
              <template #title>{{ item.title }}</template>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>

      <div class="sidebar-footer">
        <el-button link :icon="isCollapse ? Expand : Fold" @click="toggleCollapse" />
      </div>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <Breadcrumb />
        </div>
        <div class="header-right">
          <el-tooltip content="主题切换">
            <el-switch
              v-model="isDark"
              :active-icon="Moon"
              :inactive-icon="Sunny"
              inline-prompt
              @change="toggleTheme"
            />
          </el-tooltip>

          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" :icon="UserFilled" />
              <span class="username">管理员</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="settings">系统设置</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  ArrowDown, 
  Cloudy, 
  Expand, 
  Fold, 
  Moon, 
  Sunny, 
  UserFilled,
  Odometer,
  Search,
  MagicStick,
  FolderOpened,
  Document,
  CollectionTag,
  Monitor,
  Link,
  Folder,
  List,
  Setting,
  Film,
  VideoPlay,
  Tools,
  Bell,
  Message,
  ChatDotSquare,
  House
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import Breadcrumb from '@/components/Breadcrumb.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const isCollapse = ref(false)
const isDark = ref(false)

// 菜单分组配置
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

// 计算默认展开的菜单
const defaultOpeneds = computed(() => {
  const currentPath = route.path
  const openGroups: string[] = []
  
  menuGroups.forEach(group => {
    if (group.items.length > 1) {
      const isInGroup = group.items.some(item => currentPath.startsWith(item.path))
      if (isInGroup) {
        openGroups.push(group.title)
      }
    }
  })
  
  return openGroups
})

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

const toggleTheme = () => {
  document.documentElement.classList.toggle('dark', isDark.value)
}

const handleCommand = (command: string) => {
  switch (command) {
    case 'profile':
      router.push('/profile')
      break
    case 'settings':
      router.push('/config')
      break
    case 'logout':
      ElMessageBox.confirm('确定要退出登录吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        authStore.logout()
        router.push('/login')
        ElMessage.success('已退出登录')
      })
      break
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.sidebar {
  background: var(--bg-primary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
}

.logo-container {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-color);
}

.logo-icon {
  color: var(--primary-color);
  flex-shrink: 0;
}

.logo-text {
  margin-left: 12px;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  padding: 8px 0;
}

.sidebar-menu :deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: 6px;
}

.sidebar-menu :deep(.el-menu-item:hover) {
  background: var(--bg-secondary);
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--primary-color-light);
  color: var(--primary-color);
}

.sidebar-menu :deep(.el-sub-menu__title) {
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: 6px;
}

.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background: var(--bg-secondary);
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item) {
  height: 40px;
  line-height: 40px;
  padding-left: 48px !important;
}

.sidebar-footer {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-top: 1px solid var(--border-color);
}

.header {
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.user-info:hover {
  background: var(--bg-secondary);
}

.username {
  font-size: 14px;
  color: var(--text-primary);
}

.main-content {
  background: var(--bg-secondary);
  padding: 16px;
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
