import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import EmbyConfigCard from '../features/emby/components/EmbyConfigCard.vue'

interface EmbyConfigCardVm {
  form: {
    proxy_base_url: string
  }
  saveConfig: () => Promise<void>
}

const apiMocks = vi.hoisted(() => ({
  getStatusMock: vi.fn(),
  getLibrariesMock: vi.fn(),
  updateConfigMock: vi.fn(),
  refreshMock: vi.fn(),
  testConnectionMock: vi.fn(),
}))

vi.mock('@/api/emby', () => ({
  embyApi: {
    getStatus: apiMocks.getStatusMock,
    getLibraries: apiMocks.getLibrariesMock,
    updateConfig: apiMocks.updateConfigMock,
    refresh: apiMocks.refreshMock,
    testConnection: apiMocks.testConnectionMock,
  },
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
    },
  }
})

const buildStatus = (proxyBaseUrl = 'http://proxy.example:18097') => ({
  enabled: true,
  connected: true,
  server_info: null,
  configuration: {
    enabled: true,
    url: 'http://emby.example:18096',
    proxy_base_url: proxyBaseUrl,
    api_key: '',
    timeout: 30,
    notify_on_complete: true,
    on_strm_generate: true,
    on_rename: true,
    cron: '',
    library_ids: [],
    episode_aggregate_window_seconds: 10,
    delete_execute_enabled: false,
  },
})

describe('EmbyConfigCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getStatusMock.mockResolvedValue(buildStatus())
    apiMocks.getLibrariesMock.mockResolvedValue({ success: true, libraries: [] })
    apiMocks.updateConfigMock.mockResolvedValue({ success: true })
    apiMocks.refreshMock.mockResolvedValue({ success: true, message: 'ok' })
    apiMocks.testConnectionMock.mockResolvedValue({ success: true, message: 'ok', server_info: null })
  })

  it('loads proxy_base_url from status into form state', async () => {
    const wrapper = mount(EmbyConfigCard, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as EmbyConfigCardVm
    expect(vm.form.proxy_base_url).toBe('http://proxy.example:18097')
  })

  it('renders a proxy_base_url input on the config card', async () => {
    const wrapper = mount(EmbyConfigCard, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.html()).toContain('http://localhost:18097')
  })

  it('submits proxy_base_url when saving config', async () => {
    const wrapper = mount(EmbyConfigCard, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as EmbyConfigCardVm
    vm.form.proxy_base_url = 'http://proxy.example:18097'
    await vm.saveConfig()

    expect(apiMocks.updateConfigMock).toHaveBeenCalledWith(
      expect.objectContaining({
        proxy_base_url: 'http://proxy.example:18097',
      }),
    )
  })
})
