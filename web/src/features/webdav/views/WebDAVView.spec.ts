import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus from 'element-plus'

import WebDAVView from './WebDAVView.vue'

const elMessageMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn()
}))

const systemConfigMocks = vi.hoisted(() => ({
  getSystemConfig: vi.fn(),
  updateSystemConfig: vi.fn()
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: elMessageMocks
  }
})

vi.mock('@/features/config/api/systemConfig', () => systemConfigMocks)

type WebDAVViewVm = {
  form: {
    enabled: boolean
    mount_path: string
    username: string
    password: string
  }
}

const asWebDAVViewVm = (value: unknown): WebDAVViewVm => value as WebDAVViewVm

async function flushUi(): Promise<void> {
  await flushPromises()
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await flushPromises()
}

describe('WebDAVView', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined)
      }
    })

    systemConfigMocks.getSystemConfig.mockResolvedValue({
      database: 'quark_strm.db',
      webdav: {
        enabled: true,
        fallback_enabled: true,
        url: 'http://localhost:5244/dav',
        username: 'dav-user',
        password: 'dav-password',
        mount_path: '/dav',
        read_only: true
      }
    })
    systemConfigMocks.updateSystemConfig.mockImplementation(async (payload) => payload)
  })

  it('loads the real webdav config on mount and renders the hero summary', async () => {
    const wrapper = mount(WebDAVView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()

    expect(systemConfigMocks.getSystemConfig).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('WebDAV 挂载、凭据状态与访问入口统一收口')
    expect(wrapper.text()).toContain('已启用')
    expect(wrapper.text()).toContain('开发环境访问地址')
    expect(wrapper.find('[data-testid="webdav-connection-panel"]').exists()).toBe(true)
  })

  it('shows proxy warning instead of development address card when mount path differs from fixed /dav entry', async () => {
    systemConfigMocks.getSystemConfig.mockResolvedValue({
      webdav: {
        enabled: true,
        fallback_enabled: true,
        url: 'http://localhost:5244/media-dav',
        username: 'dav-user',
        password: 'dav-password',
        mount_path: '/media-dav',
        read_only: true
      }
    })

    const wrapper = mount(WebDAVView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()

    expect(wrapper.text()).toContain('开发环境代理提示')
    expect(wrapper.text()).toContain('当前挂载路径为 /media-dav')
    expect(wrapper.text()).not.toContain('开发环境访问地址')
  })

  it('persists the current form back to system config through the save action', async () => {
    const wrapper = mount(WebDAVView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()

    await wrapper.get('[data-testid="webdav-save-button"]').trigger('click')
    await flushUi()

    expect(systemConfigMocks.updateSystemConfig).toHaveBeenCalledWith(expect.objectContaining({
      webdav: {
        enabled: true,
        fallback_enabled: true,
        url: 'http://localhost:5244/dav',
        username: 'dav-user',
        password: 'dav-password',
        mount_path: '/dav',
        read_only: true
      }
    }))
    expect(elMessageMocks.success).toHaveBeenCalledWith('配置已保存')
  })

  it('copies both external and development addresses when the copy buttons are clicked', async () => {
    const wrapper = mount(WebDAVView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()

    const copyButtons = wrapper.findAll('button').filter(button => button.text().includes('复制'))

    expect(copyButtons).toHaveLength(2)

    await copyButtons[0]!.trigger('click')
    await copyButtons[1]!.trigger('click')

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://localhost:5244/dav')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://localhost:3000/dav')
  })

  it('keeps the status in warning tone when the loaded config lacks credentials', async () => {
    systemConfigMocks.getSystemConfig.mockResolvedValue({
      webdav: {
        enabled: true,
        fallback_enabled: true,
        url: 'http://localhost:5244/dav',
        username: '',
        password: '',
        mount_path: '/dav',
        read_only: true
      }
    })

    const wrapper = mount(WebDAVView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()

    expect(asWebDAVViewVm(wrapper.vm).form.enabled).toBe(true)
    expect(wrapper.text()).toContain('配置不完整')
  })
})
