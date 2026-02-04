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
          path: '/files',
          name: 'Files',
          component: () => import('@/views/FileManagerView.vue'),
          meta: { title: '文件管理', icon: 'Folder' }
        },
        {
          path: '/tasks',
          name: 'Tasks',
          component: () => import('@/views/TasksView.vue'),
          meta: { title: '任务管理', icon: 'List' }
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
          meta: { title: '智能重命名', icon: 'Magic' }
        },
        {
          path: '/cloud',
          name: 'Cloud',
          component: () => import('@/views/CloudView.vue'),
          meta: { title: '云盘管理', icon: 'Cloudy' }
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

// 路由守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (!to.meta.public && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    next('/')
  } else {
    next()
  }
})

export default router
