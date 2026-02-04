<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '240px'" class="sidebar">
      <div class="logo-container">
        <el-icon size="32" class="logo-icon"><Cloudy /></el-icon>
        <span v-show="!isCollapse" class="logo-text">Quark STRM</span>
      </div>

      <el-menu
        :default-active="$route.path"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
        class="sidebar-menu"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <el-button
          link
          :icon="isCollapse ? Expand : Fold"
          @click="toggleCollapse"
        />
      </div>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部导航 -->
      <el-header class="header">
        <div class="header-left">
          <breadcrumb />
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

      <!-- 内容区 -->
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
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Cloudy,
  Expand,
  Fold,
  Moon,
  Sunny,
  UserFilled,
  ArrowDown
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import Breadcrumb from '@/components/Breadcrumb.vue'

const router = useRouter()
const authStore = useAuthStore()

const isCollapse = ref(false)
const isDark = ref(false)

const menuItems = [
  { path: '/dashboard', title: '概览', icon: 'Odometer' },
  { path: '/search', title: '资源搜索', icon: 'Search' },
  { path: '/smart-rename', title: '智能重命名', icon: 'EditPen' },
  { path: '/cloud', title: '云盘管理', icon: 'Cloudy' },
  { path: '/files', title: '文件管理', icon: 'Folder' },
  { path: '/tasks', title: '任务管理', icon: 'List' },
  { path: '/config', title: '系统配置', icon: 'Setting' }
]

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

const toggleTheme = (val: boolean) => {
  if (val) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

const handleCommand = (command: string) => {
  switch (command) {
    case 'profile':
      ElMessage.info('个人中心功能开发中')
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
  background: var(--bg-primary);
}

/* 侧边栏 */
.sidebar {
  background: var(--bg-secondary);
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
}

.logo-text {
  margin-left: 12px;
  font-size: 18px;
  font-weight: 600;
  background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  padding: 16px 0;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: center;
}

/* 顶部导航 */
.header {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  transition: background 0.2s;
}

.user-info:hover {
  background: var(--bg-tertiary);
}

.username {
  font-size: 14px;
  color: var(--text-primary);
}

/* 主内容区 */
.main-content {
  padding: 24px;
  overflow-y: auto;
  background: var(--bg-primary);
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 响应式 */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 1000;
    transform: translateX(-100%);
  }

  .sidebar.is-open {
    transform: translateX(0);
  }

  .username {
    display: none;
  }
}
</style>
