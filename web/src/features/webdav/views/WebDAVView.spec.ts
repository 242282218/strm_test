import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import WebDAVView from './WebDAVView.vue'

const elMessageMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: elMessageMocks,
  }
})

type WebDAVViewVm = {
  form: {
    enabled: boolean
    mount_path: string
    username: string
    password: string
  }
}

const asWebDAVViewVm = (vm: unknown): WebDAVViewVm => vm as WebDAVViewVm

describe('WebDAVView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  it('shows separate external and fixed development webdav addresses when enabled with valid credentials', async () => {
    const wrapper = mount(WebDAVView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    const vm = asWebDAVViewVm(wrapper.vm)
    vm.form.enabled = true
    vm.form.username = 'dav-user'
    vm.form.password = 'dav-password'
    await nextTick()

    expect(wrapper.text()).toContain('外部访问地址')
    expect(wrapper.text()).toContain('开发环境访问地址')
    expect(wrapper.text()).toContain('客户端可访问的地址')
    expect(wrapper.text()).toContain('已启用')
  })

  it('shows proxy warning instead of development address card when mount path differs from fixed /dav entry', async () => {
    const wrapper = mount(WebDAVView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    const vm = asWebDAVViewVm(wrapper.vm)
    vm.form.enabled = true
    vm.form.mount_path = '/media-dav'
    vm.form.username = 'dav-user'
    vm.form.password = 'dav-password'
    await nextTick()

    const infoLabels = wrapper.findAll('.info-label').map(node => node.text())

    expect(infoLabels).not.toContain('开发环境访问地址')
    expect(infoLabels).toContain('开发环境代理提示')
    expect(wrapper.text()).toContain('当前挂载路径为 /media-dav')
    expect(wrapper.text()).toContain('开发代理固定为 /dav')
    expect(wrapper.text()).toContain('请同步调整前端开发代理配置')
  })

  it('shows incomplete status when enabled without credentials', async () => {
    const wrapper = mount(WebDAVView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    asWebDAVViewVm(wrapper.vm).form.enabled = true
    await nextTick()

    expect(wrapper.text()).toContain('配置不完整')
  })

  it('copies configured external webdav url when external copy button is clicked', async () => {
    const wrapper = mount(WebDAVView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    asWebDAVViewVm(wrapper.vm).form.enabled = true
    await nextTick()

    const copyButtons = wrapper.findAll('button').filter(button => button.text().includes('复制'))

    expect(copyButtons).toHaveLength(2)

    const currentCopyButton = copyButtons[0]
    expect(currentCopyButton).toBeDefined()
    await currentCopyButton!.trigger('click')

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://localhost:5244/dav')
  })

  it('copies fixed /dav development url when development copy button is clicked', async () => {
    const wrapper = mount(WebDAVView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    asWebDAVViewVm(wrapper.vm).form.enabled = true
    await nextTick()

    const copyButtons = wrapper.findAll('button').filter(button => button.text().includes('复制'))

    expect(copyButtons).toHaveLength(2)

    const devCopyButton = copyButtons[1]
    expect(devCopyButton).toBeDefined()
    await devCopyButton!.trigger('click')

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://localhost:3000/dav')
  })
})
