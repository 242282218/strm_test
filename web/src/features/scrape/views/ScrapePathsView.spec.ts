import { nextTick } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ScrapePathsView from './ScrapePathsView.vue'

const scrapeApiMocks = vi.hoisted(() => ({
  listPaths: vi.fn(),
  createPath: vi.fn(),
  updatePath: vi.fn(),
  startPath: vi.fn(),
  stopPath: vi.fn(),
  toggleCron: vi.fn(),
  deletePath: vi.fn()
}))

vi.mock('@/features/scrape/api/scrape', () => ({
  scrapeApi: scrapeApiMocks
}))

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await nextTick()
}

describe('ScrapePathsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    scrapeApiMocks.listPaths.mockResolvedValue({
      total: 2,
      items: [
        {
          id: 1,
          path_id: 'path-running',
          source_path: '/library/raw',
          dest_path: '/library/final',
          media_type: 'tv',
          scrape_mode: 'scrape_and_rename',
          rename_mode: 'move',
          max_threads: 4,
          cron: '0 0 * * *',
          enabled: true,
          cron_enabled: true,
          enable_secondary_category: true,
          status: 'running',
          last_job_id: 'job-1',
          created_at: '2026-04-17T08:00:00',
          updated_at: '2026-04-17T10:00:00'
        },
        {
          id: 2,
          path_id: 'path-idle',
          source_path: '/movie/raw',
          dest_path: '/movie/final',
          media_type: 'movie',
          scrape_mode: 'only_scrape',
          rename_mode: 'copy',
          max_threads: 2,
          cron: null,
          enabled: false,
          cron_enabled: false,
          enable_secondary_category: false,
          status: 'idle',
          last_job_id: null,
          created_at: '2026-04-17T08:30:00',
          updated_at: '2026-04-17T09:00:00'
        }
      ]
    })
  })

  it('renders hero metrics and the running path spotlight', async () => {
    const wrapper = mount(ScrapePathsView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    expect(scrapeApiMocks.listPaths).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('目录编排、运行状态与定时触发集中收口')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('1 条')
    expect(wrapper.text()).toContain('当前运行目录')
    expect(wrapper.text()).toContain('/library/raw')
    expect(wrapper.text()).toContain('scrape_and_rename')
  })

  it('opens the create dialog from the hero action', async () => {
    const wrapper = mount(ScrapePathsView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()
    expect(wrapper.getComponent({ name: 'ElDialog' }).props('modelValue')).toBe(false)

    await wrapper.get('[data-testid="scrape-create-button"]').trigger('click')
    await flushUi()

    expect(wrapper.getComponent({ name: 'ElDialog' }).props('modelValue')).toBe(true)
  })

  it('shows the empty state when there are no configured paths', async () => {
    scrapeApiMocks.listPaths.mockResolvedValue({
      total: 0,
      items: []
    })

    const wrapper = mount(ScrapePathsView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    expect(wrapper.text()).toContain('暂时没有刮削目录')
    expect(wrapper.text()).toContain('新增目录')
  })
})
