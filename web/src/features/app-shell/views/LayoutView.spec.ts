import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import LayoutView from './LayoutView.vue'

vi.mock('@/components/layout', () => ({
  AppHeader: {
    name: 'AppHeader',
    template: '<header class="app-header-mock">Header</header>'
  },
  AppSidebar: {
    name: 'AppSidebar',
    template: '<aside class="app-sidebar-mock">Sidebar</aside>'
  }
}))

describe('LayoutView', () => {
  let router: ReturnType<typeof createRouter>
  let pinia: ReturnType<typeof createPinia>

  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)

    router = createRouter({
      history: createWebHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div class="route-component">Route Content</div>' }
        }
      ]
    })

    await router.push('/')
    await router.isReady()
  })

  it('renders sidebar, header, and routed page inside the refreshed shell', () => {
    const wrapper = mount(LayoutView, {
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    expect(wrapper.find('.app-sidebar-mock').exists()).toBe(true)
    expect(wrapper.find('.app-header-mock').exists()).toBe(true)
    expect(wrapper.find('.layout-shell-inner').exists()).toBe(true)
    expect(wrapper.find('.main-content').exists()).toBe(true)
    expect(wrapper.find('.content-shell').exists()).toBe(true)
    expect(wrapper.find('.page-frame').exists()).toBe(true)
    expect(wrapper.find('.route-component').exists()).toBe(true)
  })
})
