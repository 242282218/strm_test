import type { NavigationGuard, RouteRecordRaw, Router } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/features/auth/views/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/features/app-shell/views/LayoutView.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import('@/features/dashboard/views/DashboardView.vue'),
        meta: { title: '概览', icon: 'Odometer' }
      },
      {
        path: '/tasks',
        name: 'Tasks',
        component: () => import('@/features/tasks/views/TasksView.vue'),
        meta: { title: '任务管理', icon: 'List' }
      },
      {
        path: '/scrape-pathes',
        name: 'ScrapePaths',
        component: () => import('@/features/scrape/views/ScrapePathsView.vue'),
        meta: { title: '刮削目录', icon: 'FolderOpened' }
      },
      {
        path: '/scrape-records',
        name: 'ScrapeRecords',
        component: () => import('@/features/scrape/views/ScrapeRecordsView.vue'),
        meta: { title: '刮削记录', icon: 'Document' }
      },
      {
        path: '/settings/category-strategy',
        name: 'CategoryStrategy',
        component: () => import('@/features/category-strategy/views/CategoryStrategyView.vue'),
        meta: { title: '二级分类策略', icon: 'CollectionTag' }
      },
      {
        path: '/emby-monitor',
        name: 'EmbyMonitor',
        component: () => import('@/features/emby/views/EmbyMonitorView.vue'),
        meta: { title: 'Emby 监控', icon: 'Monitor' }
      },
      {
        path: '/config',
        name: 'Config',
        component: () => import('@/features/config/views/ConfigView.vue'),
        meta: { title: '系统配置', icon: 'Setting' }
      },
      {
        path: '/search',
        name: 'Search',
        component: () => import('@/features/search/views/SearchView.vue'),
        meta: { title: '资源搜索', icon: 'Search' }
      },
      {
        path: '/rename',
        name: 'Rename',
        component: () => import('@/features/rename/views/RenameView.vue'),
        meta: { title: '基础重命名', icon: 'EditPen' }
      },
      {
        path: '/smart-rename',
        name: 'SmartRename',
        component: () => import('@/features/smart-rename/views/SmartRenameView.vue'),
        meta: { title: '智能重命名', icon: 'MagicStick' }
      },
      {
        path: '/proxy-service',
        name: 'ProxyService',
        component: () => import('@/features/proxy/views/ProxyServiceView.vue'),
        meta: { title: '代理服务', icon: 'Link' }
      },
      {
        path: '/webdav',
        name: 'WebDAV',
        component: () => import('@/features/webdav/views/WebDAVView.vue'),
        meta: { title: 'WebDAV 挂载', icon: 'FolderOpened' }
      },
      {
        path: '/notifications',
        name: 'Notifications',
        component: () => import('@/features/notifications/views/NotificationsView.vue'),
        meta: { title: '通知配置', icon: 'Message' }
      },
      {
        path: '/notifications/history',
        name: 'NotificationHistory',
        component: () => import('@/features/notifications/views/NotificationHistoryView.vue'),
        meta: { title: '通知历史', icon: 'ChatDotSquare' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/features/app-shell/views/NotFoundView.vue')
  }
]

function createAuthGuard(): NavigationGuard {
  let tokenVerified = false
  let pendingAuthCheck: Promise<boolean> | null = null

  const ensureAuthenticated = async (): Promise<boolean> => {
    const authStore = useAuthStore()

    if (authStore.isAuthenticated && tokenVerified) {
      return true
    }

    if (!pendingAuthCheck) {
      pendingAuthCheck = authStore.checkAuth().finally(() => {
        pendingAuthCheck = null
      })
    }

    const isValid = await pendingAuthCheck
    tokenVerified = isValid
    return isValid
  }

  return async (to) => {
    const authStore = useAuthStore()

    if (to.meta.public) {
      if (to.path === '/login' && authStore.isAuthenticated) {
        return '/'
      }
      return true
    }

    if (!authStore.isAuthenticated && !(await ensureAuthenticated())) {
      return '/login'
    }

    if (!tokenVerified && authStore.isAuthenticated && !(await ensureAuthenticated())) {
      return '/login'
    }

    return true
  }
}

export function createAppRouter(): Router {
  const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes,
  })

  router.beforeEach(createAuthGuard())
  return router
}

const router = createAppRouter()

export default router
