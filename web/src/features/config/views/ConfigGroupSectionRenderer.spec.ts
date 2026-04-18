import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import ElementPlus from 'element-plus'

import ConfigGroupSectionRenderer from './ConfigGroupSectionRenderer.vue'
import {
  createDefaultAListForm,
  createDefaultBasicForm,
  createDefaultCorsForm,
  createDefaultLogForm,
  createDefaultQuarkForm,
  createDefaultSecurityForm,
  createDefaultTelegramForm,
  createDefaultTmdbForm,
  createDefaultWeChatForm,
  createDefaultWebDAVForm,
} from '@/features/config/config-view-model'

vi.mock('@/components/EmbyConfigCard.vue', () => ({
  default: defineComponent({
    name: 'EmbyConfigCardStub',
    template: '<div data-testid="config-section-emby">Emby 配置</div>',
  }),
}))

interface ProviderForm {
  name: string
  api_key: string
  api_key_masked: string
  configured: boolean
  base_url: string
  model: string
  timeout: number
  enabled: boolean
  priority: number
}

interface RendererProps {
  sectionKey: string
  selectedGroupLabel: string
  loading: boolean
  saving: boolean
  configLoading: boolean
  providers: ProviderForm[]
  basicForm: ReturnType<typeof createDefaultBasicForm>
  quarkForm: ReturnType<typeof createDefaultQuarkForm>
  securityForm: ReturnType<typeof createDefaultSecurityForm>
  alistForm: ReturnType<typeof createDefaultAListForm>
  tmdbForm: ReturnType<typeof createDefaultTmdbForm>
  logForm: ReturnType<typeof createDefaultLogForm>
  corsForm: ReturnType<typeof createDefaultCorsForm>
  telegramForm: ReturnType<typeof createDefaultTelegramForm>
  wechatForm: ReturnType<typeof createDefaultWeChatForm>
  webdavForm: ReturnType<typeof createDefaultWebDAVForm>
  endpointsFormJson: string
  addProvider: () => void
  removeProvider: (index: number) => void
  saveProviders: () => void
  loadProviders: () => void
}

const createProvider = (): ProviderForm => ({
  name: 'openai',
  api_key: '',
  api_key_masked: '***',
  configured: true,
  base_url: 'https://api.example.com/v1',
  model: 'gpt-test',
  timeout: 30,
  enabled: true,
  priority: 100,
})

const createProps = (overrides: Partial<RendererProps> = {}): RendererProps => ({
  sectionKey: 'basic',
  selectedGroupLabel: '自定义分组',
  loading: false,
  saving: false,
  configLoading: false,
  providers: [createProvider()],
  basicForm: createDefaultBasicForm(),
  quarkForm: createDefaultQuarkForm(),
  securityForm: createDefaultSecurityForm(),
  alistForm: createDefaultAListForm(),
  tmdbForm: createDefaultTmdbForm(),
  logForm: createDefaultLogForm(),
  corsForm: createDefaultCorsForm(),
  telegramForm: createDefaultTelegramForm(),
  wechatForm: createDefaultWeChatForm(),
  webdavForm: createDefaultWebDAVForm(),
  endpointsFormJson: '[]',
  addProvider: vi.fn(),
  removeProvider: vi.fn(),
  saveProviders: vi.fn(),
  loadProviders: vi.fn(),
  ...overrides,
})

const mountRenderer = async (overrides: Partial<RendererProps> = {}) => {
  const wrapper = mount(ConfigGroupSectionRenderer, {
    props: createProps(overrides),
    global: {
      plugins: [ElementPlus],
      stubs: {
        teleport: true,
      },
    },
  })

  await flushPromises()
  return wrapper
}

const clickButton = async (wrapper: VueWrapper, label: string) => {
  const button = wrapper.findAll('button').find(candidate => candidate.text().includes(label))

  expect(button, `missing button: ${label}`).toBeDefined()
  await button!.trigger('click')
  await flushPromises()
}

describe('ConfigGroupSectionRenderer', () => {
  it.each([
    ['basic', '[data-testid="config-section-basic"]', '基础设置'],
    ['emby', '[data-testid="config-section-emby"]', 'Emby 配置'],
    ['quark', '[data-testid="config-section-quark"]', '夸克配置'],
    ['security', '[data-testid="config-section-security"]', '安全设置'],
    ['alist', '[data-testid="config-section-alist"]', 'AList 配置'],
    ['tmdb', '[data-testid="config-section-tmdb"]', 'TMDB 配置'],
    ['log', '[data-testid="config-section-log"]', '日志配置'],
    ['cors', '[data-testid="config-section-cors"]', '跨域设置'],
    ['telegram', '[data-testid="config-section-telegram"]', 'Telegram 通知'],
    ['wechat', '[data-testid="config-section-wechat"]', '微信通知'],
    ['endpoints', '[data-testid="config-section-endpoints"]', '端点映射'],
    ['ai', '[data-testid="config-section-ai"]', 'AI Providers 配置'],
    ['webdav', '[data-testid="config-section-webdav"]', 'WebDAV 配置'],
  ])('renders the %s section branch', async (sectionKey, selector, expectedText) => {
    const wrapper = await mountRenderer({ sectionKey })

    expect(wrapper.find(selector).exists()).toBe(true)
    expect(wrapper.text()).toContain(expectedText)
  })

  it('renders the placeholder branch for unknown sections', async () => {
    const wrapper = await mountRenderer({
      sectionKey: 'profile-extras',
      selectedGroupLabel: '扩展配置',
    })

    expect(wrapper.find('[data-testid="config-section-placeholder"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('扩展配置暂未提供独立表单')
    expect(wrapper.text()).toContain('当前可继续通过下方 JSON 配置区编辑该分组')
  })

  it('wires provider action buttons in the ai section', async () => {
    const addProvider = vi.fn()
    const removeProvider = vi.fn()
    const saveProviders = vi.fn()
    const loadProviders = vi.fn()
    const wrapper = await mountRenderer({
      sectionKey: 'ai',
      addProvider,
      removeProvider,
      saveProviders,
      loadProviders,
    })

    await clickButton(wrapper, '添加 Provider')
    await clickButton(wrapper, '删除')
    await clickButton(wrapper, '保存配置')
    await clickButton(wrapper, '重置')

    expect(addProvider).toHaveBeenCalledTimes(1)
    expect(removeProvider).toHaveBeenCalledWith(0)
    expect(saveProviders).toHaveBeenCalledTimes(1)
    expect(loadProviders).toHaveBeenCalledTimes(1)
  })

  it('disables the log JSON indent input unless json format is selected', async () => {
    const textWrapper = await mountRenderer({
      sectionKey: 'log',
      logForm: {
        ...createDefaultLogForm(),
        format: 'text',
      },
    })

    expect(textWrapper.get('input[placeholder="留空表示紧凑输出"]').attributes('disabled')).toBeDefined()

    const jsonWrapper = await mountRenderer({
      sectionKey: 'log',
      logForm: {
        ...createDefaultLogForm(),
        format: 'json',
      },
    })

    expect(jsonWrapper.get('input[placeholder="留空表示紧凑输出"]').attributes('disabled')).toBeUndefined()
  })
})
