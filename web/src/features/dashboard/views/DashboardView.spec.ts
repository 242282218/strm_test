import { nextTick } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import DashboardView from './DashboardView.vue'

const dashboardApiMocks = vi.hoisted(() => ({
  getDashboardStats: vi.fn(),
  getTaskTrends: vi.fn(),
}))

const chartMocks = vi.hoisted(() => ({
  setOption: vi.fn(),
  resize: vi.fn(),
  initChart: vi.fn(),
}))

vi.mock('@/features/dashboard/api/dashboard', () => dashboardApiMocks)

vi.mock('@/composables', () => ({
  useDebounce: (fn: () => void) => ({
    run: fn,
    cancel: vi.fn()
  }),
  useECharts: () => ({
    chartRef: { __v_isRef: true, value: null },
    setOption: chartMocks.setOption,
    resize: chartMocks.resize,
    initChart: chartMocks.initChart,
    dispose: vi.fn(),
    clear: vi.fn(),
    showLoading: vi.fn(),
    hideLoading: vi.fn()
  })
}))

vi.mock('echarts/core', () => ({
  use: vi.fn(),
  graphic: {
    LinearGradient: vi.fn().mockImplementation(() => ({}))
  }
}))

vi.mock('echarts/charts', () => ({
  LineChart: {},
  PieChart: {}
}))

vi.mock('echarts/components', () => ({
  GridComponent: {},
  LegendComponent: {},
  TitleComponent: {},
  TooltipComponent: {}
}))

vi.mock('echarts/renderers', () => ({
  CanvasRenderer: {}
}))

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await nextTick()
}

describe('DashboardView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())

    dashboardApiMocks.getDashboardStats.mockResolvedValue({
      status: 'ok',
      stats: {
        strm_count: 1280,
        task_count: 24,
        cache_entries: 320,
        cache_hit_rate: 91.2
      },
      recent_tasks: [
        { name: '同步媒体库', type: 'sync', status: 'running', progress: 62, time: '2 分钟前' },
        { name: '补全 STRM', type: 'generate', status: 'pending', progress: 18, time: '10 分钟前' }
      ],
      services: [
        { name: '代理服务', status: 'running' },
        { name: 'WebDAV', status: 'running' }
      ],
      cache_detail: {
        size: 320,
        hit_rate: 91.2,
        ttl: 900
      },
      file_types: {
        mkv: 40,
        mp4: 28,
        strm: 22
      }
    })

    dashboardApiMocks.getTaskTrends.mockResolvedValue({
      status: 'ok',
      dates: ['04-11', '04-12'],
      success: [3, 4],
      failed: [0, 1]
    })
  })

  it('renders hero signals and latest task spotlight from dashboard data', async () => {
    const router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/tasks', component: { template: '<div />' } },
        { path: '/proxy-service', component: { template: '<div />' } },
        { path: '/config', component: { template: '<div />' } }
      ]
    })

    await router.push('/')
    await router.isReady()

    const wrapper = mount(DashboardView, {
      global: {
        plugins: [router, ElementPlus]
      }
    })

    await flushUi()

    expect(dashboardApiMocks.getDashboardStats).toHaveBeenCalledTimes(1)
    expect(dashboardApiMocks.getTaskTrends).toHaveBeenCalledTimes(1)
    expect(chartMocks.initChart).toHaveBeenCalledTimes(2)

    const signalValues = wrapper.findAll('.hero-signal-value').map(node => node.text())
    expect(signalValues).toContain('2 / 2')
    expect(signalValues).toContain('2 活跃')
    expect(signalValues).toContain('3 类')

    expect(wrapper.find('.page-header').exists()).toBe(false)
    expect(wrapper.find('.hero-header-actions').exists()).toBe(true)
    expect(wrapper.get('.spotlight-name').text()).toBe('同步媒体库')
    expect(wrapper.text()).toContain('MKV')
    expect(wrapper.text()).toContain('91.2%')
  })
})
