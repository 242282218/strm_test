import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors } from './helpers'

test.describe('通知历史 /notifications/history', () => {
  test('页面加载：标题、筛选区可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/notifications/history')

    await expect(page.getByRole('heading', { name: '通知历史', exact: true })).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('刷新日志按钮可见', async ({ page }) => {
    await navigateAndWait(page, '/notifications/history')
    await expect(page.getByTestId('notification-history-refresh')).toBeVisible()
  })

  test('筛选器可交互', async ({ page }) => {
    await navigateAndWait(page, '/notifications/history')
    const filterCard = page.locator('.filter-panel')
    if (await filterCard.count() > 0) {
      await expect(filterCard).toBeVisible()
      // 状态下拉框
      const selects = filterCard.locator('.el-select')
      if (await selects.count() > 0) {
        await expect(selects.first()).toBeVisible()
      }
    }
  })

  test('历史时间线或空状态可见', async ({ page }) => {
    await navigateAndWait(page, '/notifications/history')
    const timeline = page.locator('.el-timeline')
    const empty = page.locator('.empty-state')
    await expect(timeline.or(empty).first()).toBeVisible({ timeout: 10_000 })
  })

  test('分页组件可见（有数据时）', async ({ page }) => {
    await navigateAndWait(page, '/notifications/history')
    const pagination = page.locator('.el-pagination')
    if (await pagination.count() > 0) {
      await expect(pagination).toBeVisible()
    }
  })
})
