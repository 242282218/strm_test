import { nextTick } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import ScrapeRecordsView from './ScrapeRecordsView.vue'

const scrapeApiMocks = vi.hoisted(() => ({
  listRecords: vi.fn(),
  getRecord: vi.fn(),
  reScrape: vi.fn(),
  clearFailed: vi.fn(),
  truncateAll: vi.fn()
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

describe('ScrapeRecordsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    scrapeApiMocks.listRecords.mockResolvedValue({
      total: 2,
      items: [
        {
          id: 1,
          record_id: 'record-failed',
          job_id: 'job-1',
          path_id: 'path-1',
          item_id: 10,
          source_file: '/library/raw/show.mkv',
          target_file: '/library/final/show.mkv',
          media_type: 'tv',
          tmdb_id: 1,
          title: 'Show',
          year: 2026,
          status: 'scrape_failed',
          error_code: 'TMDB_TIMEOUT',
          error_message: 'timeout',
          recognition_result: null,
          created_at: '2026-04-17T09:00:00',
          updated_at: '2026-04-17T09:10:00'
        },
        {
          id: 2,
          record_id: 'record-ok',
          job_id: 'job-2',
          path_id: 'path-2',
          item_id: 11,
          source_file: '/movie/raw/movie.mkv',
          target_file: '/movie/final/movie.mkv',
          media_type: 'movie',
          tmdb_id: 2,
          title: 'Movie',
          year: 2025,
          status: 'renamed',
          error_code: null,
          error_message: null,
          recognition_result: null,
          created_at: '2026-04-17T08:00:00',
          updated_at: '2026-04-17T08:20:00'
        }
      ]
    })
    scrapeApiMocks.getRecord.mockResolvedValue({
      record_id: 'record-failed',
      status: 'scrape_failed',
      source_file: '/library/raw/show.mkv',
      target_file: '/library/final/show.mkv',
      title: 'Show',
      tmdb_id: 1,
      error_code: 'TMDB_TIMEOUT',
      error_message: 'timeout',
      recognition_result: { match: 'Show' }
    })
    scrapeApiMocks.clearFailed.mockResolvedValue({ cleared: 1 })
    scrapeApiMocks.truncateAll.mockResolvedValue({ truncated: 2 })
  })

  it('renders hero metrics and prioritizes the failed record in the spotlight', async () => {
    const wrapper = mount(ScrapeRecordsView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    expect(scrapeApiMocks.listRecords).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('刮削结果、失败线索与批量处理集中收口')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('最近失败记录')
    expect(wrapper.text()).toContain('/library/raw/show.mkv')
    expect(wrapper.text()).toContain('scrape_failed')
  })

  it('loads the record detail into the drawer', async () => {
    const wrapper = mount(ScrapeRecordsView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    await wrapper.findAll('.el-table .el-button')[0]!.trigger('click')
    await flushUi()

    expect(scrapeApiMocks.getRecord).toHaveBeenCalledWith('record-failed')
    expect(wrapper.getComponent({ name: 'ElDrawer' }).props('modelValue')).toBe(true)
    expect(wrapper.text()).toContain('TMDB_TIMEOUT')
  })

  it('confirms and clears failed records through the scrape api', async () => {
    const confirmSpy = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const successSpy = vi.spyOn(ElMessage, 'success').mockImplementation(() => undefined as never)
    const wrapper = mount(ScrapeRecordsView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    const clearButton = wrapper.findAll('button').find(button => button.text().includes('清理失败'))
    expect(clearButton).toBeTruthy()

    await clearButton!.trigger('click')
    await flushUi()

    expect(confirmSpy).toHaveBeenCalledTimes(1)
    expect(scrapeApiMocks.clearFailed).toHaveBeenCalledTimes(1)
    expect(scrapeApiMocks.listRecords).toHaveBeenCalledTimes(2)
    expect(successSpy).toHaveBeenCalledWith('已清理 1 条失败记录')
  })

  it('confirms and truncates all records through the scrape api', async () => {
    const confirmSpy = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const successSpy = vi.spyOn(ElMessage, 'success').mockImplementation(() => undefined as never)
    const wrapper = mount(ScrapeRecordsView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true
        }
      }
    })

    await flushUi()

    const truncateButton = wrapper.findAll('button').find(button => button.text().includes('清空记录'))
    expect(truncateButton).toBeTruthy()

    await truncateButton!.trigger('click')
    await flushUi()

    expect(confirmSpy).toHaveBeenCalledTimes(1)
    expect(scrapeApiMocks.truncateAll).toHaveBeenCalledTimes(1)
    expect(scrapeApiMocks.listRecords).toHaveBeenCalledTimes(2)
    expect(successSpy).toHaveBeenCalledWith('已清空 2 条记录')
  })
})
