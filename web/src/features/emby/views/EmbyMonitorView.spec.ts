import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus from 'element-plus'

import EmbyMonitorView from './EmbyMonitorView.vue'

const embyApiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getRefreshHistory: vi.fn(),
  refresh: vi.fn(),
  triggerSync: vi.fn()
}))

const embyMonitorApiMocks = vi.hoisted(() => ({
  getEvents: vi.fn(),
  createDeletePlan: vi.fn(),
  executeDeletePlan: vi.fn()
}))

vi.mock('@/api/emby', () => ({
  embyApi: embyApiMocks
}))

vi.mock('@/api/embyMonitor', () => ({
  embyMonitorApi: embyMonitorApiMocks
}))

type EmbyMonitorVm = {
  planForm: {
    source: string
    eventIdsText: string
    itemIdsText: string
    reason: string
    executedBy: string
  }
}

const asVm = (value: unknown): EmbyMonitorVm => value as EmbyMonitorVm

async function flushUi(): Promise<void> {
  await flushPromises()
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await flushPromises()
}

describe('EmbyMonitorView', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    Object.defineProperty(document, 'hidden', {
      configurable: true,
      value: true
    })

    embyApiMocks.getStatus.mockResolvedValue({
      enabled: true,
      connected: true,
      server_info: null,
      configuration: {
        enabled: true,
        url: 'http://emby.local:8096',
        proxy_base_url: 'http://proxy.local',
        api_key: 'token',
        timeout: 10,
        notify_on_complete: false,
        on_strm_generate: true,
        on_rename: false,
        cron: null,
        library_ids: [],
        episode_aggregate_window_seconds: 12,
        delete_execute_enabled: false
      }
    })
    embyApiMocks.getRefreshHistory.mockResolvedValue({
      success: true,
      history: [
        {
          success: true,
          library_id: null,
          message: '增量刷新完成',
          timestamp: '2026-04-17T08:30:00'
        }
      ]
    })
    embyApiMocks.refresh.mockResolvedValue({
      success: true,
      message: 'ok'
    })
    embyApiMocks.triggerSync.mockResolvedValue({
      status: 'ok',
      message: 'ok'
    })
    embyMonitorApiMocks.getEvents.mockResolvedValue({
      items: [
        {
          id: 1,
          event_id: 'evt-1',
          event_type: 'library.new',
          item_id: 'item-1',
          item_name: 'Movie',
          item_type: 'Movie',
          aggregated_count: 1,
          payload: { ok: true },
          created_at: '2026-04-17T08:00:00',
          updated_at: '2026-04-17T08:20:00'
        }
      ],
      total: 1
    })
    embyMonitorApiMocks.createDeletePlan.mockResolvedValue({
      success: true,
      plan_id: 'plan-1',
      dry_run: true,
      total_items: 2,
      executable_items: 1,
      items: [
        {
          emby_item_id: 'item-1',
          item_name: 'Movie',
          item_type: 'Movie',
          risk_level: 'low',
          can_execute: true,
          action: 'delete'
        }
      ]
    })
    embyMonitorApiMocks.executeDeletePlan.mockResolvedValue({
      success: true,
      plan_id: 'plan-1',
      status: 'ok',
      executed_items: 1,
      skipped_items: 0
    })
  })

  it('renders the Emby workbench hero with connection and event metrics', async () => {
    const wrapper = mount(EmbyMonitorView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    expect(embyApiMocks.getStatus).toHaveBeenCalledTimes(1)
    expect(embyApiMocks.getRefreshHistory).toHaveBeenCalledTimes(1)
    expect(embyMonitorApiMocks.getEvents).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Emby 监控、事件流与删除计划统一收口')
    expect(wrapper.text()).toContain('已连接')
    expect(wrapper.text()).toContain('12 秒')
    expect(wrapper.text()).toContain('增量刷新完成')
    expect(wrapper.find('[data-testid="emby-events-panel"]').exists()).toBe(true)
  })

  it('creates a dry-run delete plan and updates the hero-side summary', async () => {
    const wrapper = mount(EmbyMonitorView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    const vm = asVm(wrapper.vm)
    vm.planForm.eventIdsText = 'evt-1\nevt-2'
    await nextTick()

    const createPlanButton = wrapper.findAll('button').find(button => button.text().includes('生成删除计划'))
    expect(createPlanButton).toBeDefined()

    await createPlanButton!.trigger('click')
    await flushUi()

    expect(embyMonitorApiMocks.createDeletePlan).toHaveBeenCalledWith({
      source: 'manual',
      event_ids: ['evt-1', 'evt-2'],
      item_ids: [],
      reason: undefined
    })
    expect(wrapper.text()).toContain('当前 dry-run 计划')
    expect(wrapper.text()).toContain('plan-1')
    expect(wrapper.text()).toContain('可执行 1 / 2')
  })
})
