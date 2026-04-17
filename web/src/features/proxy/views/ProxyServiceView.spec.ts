import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus from 'element-plus'

import ProxyServiceView from './ProxyServiceView.vue'

const proxyApiMocks = vi.hoisted(() => ({
  getProxyCacheStats: vi.fn(),
  clearProxyCache: vi.fn(),
  getRedirectUrl: vi.fn(),
  getProxyStreamUrl: vi.fn()
}))

const strmApiMocks = vi.hoisted(() => ({
  scanDirectory: vi.fn()
}))

const fileManagerMocks = vi.hoisted(() => ({
  browseFiles: vi.fn()
}))

vi.mock('@/features/proxy/api/proxy', () => proxyApiMocks)
vi.mock('@/api/strm', () => strmApiMocks)
vi.mock('@/api/fileManager', () => fileManagerMocks)

async function flushUi(): Promise<void> {
  await flushPromises()
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await flushPromises()
}

describe('ProxyServiceView', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    proxyApiMocks.getProxyCacheStats.mockResolvedValue({
      status: 'ok',
      stats: {
        size: 42,
        hit_count: 210,
        miss_count: 15,
        hit_rate: 93.3
      }
    })
    proxyApiMocks.clearProxyCache.mockResolvedValue({
      status: 'ok',
      message: 'cleared'
    })
    proxyApiMocks.getRedirectUrl.mockResolvedValue('https://example.com/redirect')
    proxyApiMocks.getProxyStreamUrl.mockReturnValue('http://localhost:8000/proxy/stream/fid-1')
    strmApiMocks.scanDirectory.mockResolvedValue({
      count: 1,
      skipped: 0,
      failed: 0,
      total: 1
    })
    fileManagerMocks.browseFiles.mockResolvedValue({
      items: [
        {
          id: 'folder-1',
          name: 'Movies',
          path: '/Movies',
          file_type: 'folder',
          size: 0
        }
      ]
    })
  })

  it('renders the proxy workbench hero with cache and mode metrics', async () => {
    const wrapper = mount(ProxyServiceView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    expect(proxyApiMocks.getProxyCacheStats).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('代理服务、STRM 生成与缓存命中统一收口')
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('93.3%')
    expect(wrapper.text()).toContain('302 重定向')
    expect(wrapper.find('[data-testid="proxy-cache-panel"]').exists()).toBe(true)
  })

  it('opens the file browser from the STRM workbench action and loads the root directory', async () => {
    const wrapper = mount(ProxyServiceView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    expect(wrapper.getComponent({ name: 'ElDialog' }).props('modelValue')).toBe(false)

    await wrapper.get('[data-testid="proxy-open-browser"]').trigger('click')
    await flushUi()

    expect(fileManagerMocks.browseFiles).toHaveBeenCalledWith('/')
    expect(wrapper.getComponent({ name: 'ElDialog' }).props('modelValue')).toBe(true)
  })
})
