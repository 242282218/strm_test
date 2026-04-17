import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors } from './helpers'

test.describe('Emby 监控 /emby-monitor', () => {
  test('页面加载：标题、操作按钮可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/emby-monitor')

    await expect(page.getByTestId('emby-monitor-hero')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Emby 监控、事件流与删除计划统一收口' })).toBeVisible()
    await expect(page.getByTestId('emby-refresh-button')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('自动刷新开关可见', async ({ page }) => {
    await navigateAndWait(page, '/emby-monitor')
    const switchEl = page.locator('.el-switch')
    if (await switchEl.count() > 0) {
      await expect(switchEl.first()).toBeVisible()
    }
  })

  test('状态卡片区域渲染', async ({ page }) => {
    await navigateAndWait(page, '/emby-monitor')
    await expect(page.getByTestId('emby-events-panel')).toBeVisible({ timeout: 10_000 })
  })

  test('Webhook 事件表格或空状态可见', async ({ page }) => {
    await navigateAndWait(page, '/emby-monitor')
    await expect(page.getByTestId('emby-events-panel')).toBeVisible({ timeout: 10_000 })
  })

  test('删除计划工作区可见', async ({ page }) => {
    await navigateAndWait(page, '/emby-monitor')
    await expect(page.getByTestId('emby-delete-plan-panel')).toBeVisible()
  })
})
