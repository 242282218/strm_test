import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import Breadcrumb from './Breadcrumb.vue'

const routeMocks = vi.hoisted(() => ({
  matched: [] as Array<{ path: string; meta?: Record<string, unknown> }>,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({
    matched: routeMocks.matched,
  }),
}))

describe('Breadcrumb', () => {
  beforeEach(() => {
    routeMocks.matched = []
  })

  it('renders only the current page crumb without a fixed home item', () => {
    routeMocks.matched = [
      { path: '/', meta: { title: '首页' } },
      { path: '/proxy-service', meta: { title: '代理服务' } },
    ]

    const wrapper = mount(Breadcrumb, {
      global: {
        plugins: [ElementPlus]
      }
    })

    expect(wrapper.text()).toContain('代理服务')
    expect(wrapper.text()).not.toContain('首页')
  })
})
