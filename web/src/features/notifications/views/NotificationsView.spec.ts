import { nextTick } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import NotificationsView from './NotificationsView.vue'

const notificationApiMocks = vi.hoisted(() => ({
  getChannels: vi.fn(),
  createChannel: vi.fn(),
  updateChannel: vi.fn(),
  deleteChannel: vi.fn(),
  testChannel: vi.fn(),
  convertFrontendToBackend: vi.fn(),
  convertBackendToFrontend: vi.fn(),
  SUPPORTED_NOTIFICATION_CHANNELS: [
    { label: 'Telegram', value: 'telegram' },
    { label: 'ServerChan', value: 'serverchan' }
  ]
}))

const notificationMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn()
}))

vi.mock('@/features/notifications/api/notification', () => notificationApiMocks)

vi.mock('@/composables', () => ({
  useLoadingStore: () => ({
    isLoading: () => false,
    withLoading: async (_key: string, fn: () => Promise<void>) => {
      await fn()
    }
  }),
  useNotification: () => notificationMocks,
  useAsyncNotify: () => ({
    withConfirm: async (fn: () => Promise<void>) => {
      await fn()
    }
  })
}))

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await nextTick()
}

describe('NotificationsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    notificationApiMocks.getChannels.mockResolvedValue([
      {
        id: 1,
        channel_type: 'telegram',
        channel_name: 'Telegram',
        is_enabled: true,
        config: {}
      }
    ])
    notificationApiMocks.convertBackendToFrontend.mockReturnValue({
      enabled: true,
      channel: 'telegram',
      telegram: {
        bot_token: 'token',
        chat_id: '123456'
      },
      serverchan: {
        send_key: ''
      }
    })
    notificationApiMocks.convertFrontendToBackend.mockReturnValue({
      channel_type: 'telegram',
      channel_name: 'Telegram',
      config: {
        bot_token: 'token',
        chat_id: '123456'
      }
    })
    notificationApiMocks.updateChannel.mockResolvedValue({})
    notificationApiMocks.createChannel.mockResolvedValue({})
    notificationApiMocks.testChannel.mockResolvedValue({ status: 'ok' })
  })

  it('renders the hero summary and fixed test preview for the saved channel', async () => {
    const wrapper = mount(NotificationsView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()

    expect(notificationApiMocks.getChannels).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('通知渠道、启用状态与联调反馈统一收口')
    expect(wrapper.text()).toContain('Telegram')
    expect(wrapper.text()).toContain('1 条')
    expect(wrapper.text()).toContain('2 / 2')
    expect(wrapper.text()).toContain('已启用')
    expect(wrapper.text()).toContain('固定预览文案')
    expect(wrapper.find('[data-testid="notification-delete-button"]').exists()).toBe(true)
  })

  it('persists the selected channel through the save action and reloads the view state', async () => {
    const wrapper = mount(NotificationsView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()
    notificationApiMocks.getChannels.mockClear()

    await wrapper.get('[data-testid="notification-save-button"]').trigger('click')
    await flushUi()

    expect(notificationApiMocks.updateChannel).toHaveBeenCalledWith(1, {
      config: {
        bot_token: 'token',
        chat_id: '123456'
      },
      is_enabled: true
    })
    expect(notificationMocks.success).toHaveBeenCalledWith('配置已保存')
    expect(notificationApiMocks.getChannels).toHaveBeenCalledTimes(1)
  })

  it('keeps the test action disabled while the channel is still a draft', async () => {
    notificationApiMocks.getChannels.mockResolvedValue([])

    const wrapper = mount(NotificationsView, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushUi()

    expect(wrapper.text()).toContain('未保存草稿')
    expect(wrapper.get('[data-testid="notification-test-button"]').attributes('disabled')).toBeDefined()
  })
})
