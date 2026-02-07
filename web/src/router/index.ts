import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true }
    },
    {
      path: '/',
      name: 'Layout',
      component: () => import('@/views/LayoutView.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: '/dashboard',
          name: 'Dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '概览', icon: 'Odometer' }
        },
        {
          path: '/tasks',
          name: 'Tasks',
          component: () => import('@/views/TasksView.vue'),
          meta: { title: '任务管理', icon: 'List' }
        },
        {
          path: '/scrape-pathes',
          name: 'ScrapePaths',
          component: () => import('@/views/ScrapePathsView.vue'),
          meta: { title: '刮削目录', icon: 'FolderOpened' }
        },
        {
          path: '/scrape-records',
          name: 'ScrapeRecords',
          component: () => import('@/views/ScrapeRecordsView.vue'),
          meta: { title: '刮削记录', icon: 'Document' }
        },
        {
          path: '/settings/category-strategy',
          name: 'CategoryStrategy',
          component: () => import('@/views/CategoryStrategyView.vue'),
          meta: { title: '二级分类策略', icon: 'CollectionTag' }
        },
        {
          path: '/emby-monitor',
          name: 'EmbyMonitor',
          component: () => import('@/views/EmbyMonitorView.vue'),
          meta: { title: 'Emby 监控', icon: 'Monitor' }
        },
        {
          path: '/config',
          name: 'Config',
          component: () => import('@/views/ConfigView.vue'),
          meta: { title: '系统配置', icon: 'Setting' }
        },
        {
          path: '/search',
          name: 'Search',
          component: () => import('@/views/SearchView.vue'),
          meta: { title: '资源搜索', icon: 'Search' }
        },
        {
          path: '/rename',
          name: 'Rename',
          component: () => import('@/views/RenameView.vue'),
          meta: { title: '基础重命名', icon: 'EditPen' }
        },
        {
          path: '/smart-rename',
          name: 'SmartRename',
          component: () => import('@/views/SmartRenameView.vue'),
          meta: { title: '智能重命名', icon: 'MagicStick' }
        },
        {
          path: '/proxy-service',
          name: 'ProxyService',
          component: () => import('@/views/ProxyServiceView.vue'),
          meta: { title: '代理服务', icon: 'Link' }
        },
        {
          path: '/webdav',
          name: 'WebDAV',
          component: () => import('@/views/WebDAVView.vue'),
          meta: { title: 'WebDAV 挂载', icon: 'FolderOpened' }
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFoundView.vue')
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  if (!to.meta.public && !authStore.isAuthenticated) {
    next('/login')
    return
  }
  if (to.path === '/login' && authStore.isAuthenticated) {
    next('/')
    return
  }
  next()
})

export default router
