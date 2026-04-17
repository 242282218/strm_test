import { nextTick } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import NotificationHistoryView from './NotificationHistoryView.vue'

const notificationApiMocks = vi.hoisted(() => ({
  getLogs: vi.fn()
}))

vi.mock('@/features/notifications/api/notification', () => notificationApiMocks)

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await nextTick()
}

describe('NotificationHistoryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    notificationApiMocks.getLogs.mockResolvedValue([
      {
        id: 1,
        channel_name: 'Telegram',
        event_type: 'task_failed',
        title: '文件同步失败',
        status: 'failed',
        error_message: 'network timeout',
        created_at: '2026-04-17T09:00:00'
      },
      {
        id: 2,
        channel_name: 'ServerChan',
        event_type: 'task_completed',
        title: 'STRM 生成完成',
        status: 'success',
        error_message: '',
        created_at: '2026-04-17T08:00:00'
      }
    ])
  })

  it('renders hero metrics from the real log payload and removes the fake clear action', async () => {
    const wrapper = mount(NotificationHistoryView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    expect(notificationApiMocks.getLogs).toHaveBeenCalledWith(200)
    expect(wrapper.text()).toContain('通知结果、失败线索与时间范围统一回看')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('1')
    expect(wrapper.text()).toContain('文件同步失败')
    expect(wrapper.text()).toContain('Telegram')
    expect(wrapper.text()).not.toContain('清空历史')
  })

  it('opens the detail dialog for the selected timeline item', async () => {
    const wrapper = mount(NotificationHistoryView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()
    expect(wrapper.getComponent({ name: 'ElDialog' }).props('modelValue')).toBe(false)

    await wrapper.findAll('.timeline-footer .el-button')[0]!.trigger('click')
    await flushUi()

    expect(wrapper.getComponent({ name: 'ElDialog' }).props('modelValue')).toBe(true)
    expect(wrapper.text()).toContain('network timeout')
  })
})
