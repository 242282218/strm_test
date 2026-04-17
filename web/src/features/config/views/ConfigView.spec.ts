import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import ElementPlus from 'element-plus'

import ConfigView from './ConfigView.vue'

const changePassword = vi.fn()
const themeDark = ref(false)
const replaceMock = vi.fn()

const systemConfigMocks = vi.hoisted(() => ({
  getAIProviders: vi.fn(),
  getSystemConfig: vi.fn(),
  getSystemConfigMetadata: vi.fn(),
  updateAIProviders: vi.fn(),
  updateSystemConfig: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: {
      group: 'basic',
    },
  }),
  useRouter: () => ({
    replace: replaceMock,
  }),
}))

vi.mock('@/composables', () => ({
  useTheme: () => ({
    isDark: themeDark,
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: {
      username: 'tester',
      role: 'admin',
    },
    changePassword,
  }),
}))

vi.mock('@/components/EmbyConfigCard.vue', () => ({
  default: defineComponent({
    name: 'EmbyConfigCardStub',
    template: '<div data-testid="config-section-emby" />',
  }),
}))

vi.mock('@/features/config/api/systemConfig', () => systemConfigMocks)

const waitForSelectorToDisappear = async (wrapper: ReturnType<typeof mount>, selector: string, attempts = 20) => {
  for (let index = 0; index < attempts; index += 1) {
    await flushPromises()
    await vi.dynamicImportSettled()
    if (!wrapper.find(selector).exists()) {
      return
    }
    await new Promise(resolve => setTimeout(resolve, 0))
  }

  throw new Error(`selector still present: ${selector}`)
}

describe('ConfigView', () => {
  beforeEach(() => {
    themeDark.value = false
    changePassword.mockReset()
    replaceMock.mockReset()
    systemConfigMocks.getAIProviders.mockResolvedValue({ providers: [] })
    systemConfigMocks.getSystemConfig.mockResolvedValue({
      database: 'quark_strm.db',
      log_level: 'INFO',
      exts: ['.mp4'],
      alt_exts: ['.srt'],
      create_sub_directory: false,
      endpoints: [],
    })
    systemConfigMocks.getSystemConfigMetadata.mockResolvedValue({
      schema: {
        properties: {
          database: { type: 'string' },
          emby: { type: 'object' },
        },
      },
      sensitive_fields: [],
      sensitive_fields_status: {},
    })
    systemConfigMocks.updateAIProviders.mockResolvedValue({ providers: [] })
    systemConfigMocks.updateSystemConfig.mockResolvedValue({})
  })

  it('shows a loading state before mounting the selected async config section', async () => {
    const wrapper = mount(ConfigView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    })

    expect(wrapper.find('[data-testid="config-section-loading"]').exists()).toBe(true)

    await waitForSelectorToDisappear(wrapper, '[data-testid="config-section-loading"]')

    expect(wrapper.find('[data-testid="config-section-loading"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="config-section-basic"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="config-section-json"]').exists()).toBe(true)
  })

  it('renders hero metrics and syncs the selected group back to the route query', async () => {
    const wrapper = mount(ConfigView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    })

    await waitForSelectorToDisappear(wrapper, '[data-testid="config-section-loading"]')

    expect(wrapper.text()).toContain('配置契约、当前分组与敏感字段状态集中收口')
    expect(wrapper.text()).toContain('配置分组')
    expect(wrapper.text()).toContain('AI 提供商')

    await wrapper.get('[data-testid="config-group-profile"]').trigger('click')
    await flushPromises()

    expect(replaceMock).toHaveBeenCalledWith({
      query: {
        group: 'profile',
      },
    })
    expect(wrapper.find('[data-testid="config-section-profile"]').exists()).toBe(true)
  })
})
