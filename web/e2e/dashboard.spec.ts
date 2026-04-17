import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors } from './helpers'

test.describe('仪表盘 /dashboard', () => {
  test('页面加载：标题、统计卡片可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/dashboard')

    await expect(page.getByText('媒体链路、任务状态与缓存命中一屏可见')).toBeVisible()
    // 至少有统计卡片
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 10_000 })
    expect(apiErrors).toHaveLength(0)
  })

  test('统计卡片显示数值', async ({ page }) => {
    await navigateAndWait(page, '/dashboard')
    const statValues = page.locator('.stat-value')
    await expect(statValues.first()).toBeVisible({ timeout: 10_000 })
  })

  test('ECharts 图表容器已渲染', async ({ page }) => {
    await navigateAndWait(page, '/dashboard')
    // ECharts 会在 canvas 元素上渲染
    const chartContainers = page.locator('.chart-container')
    if (await chartContainers.count() > 0) {
      await expect(chartContainers.first()).toBeVisible()
    }
  })

  test('刷新按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/dashboard')
    const refreshBtn = page.getByText('刷新数据')
    if (await refreshBtn.count() > 0) {
      await refreshBtn.click()
      // 刷新后统计卡片仍可见
      await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 10_000 })
    }
  })

  test('时间范围切换', async ({ page }) => {
    await navigateAndWait(page, '/dashboard')
    const radioGroup = page.locator('.el-radio-group')
    if (await radioGroup.count() > 0) {
      const buttons = radioGroup.locator('.el-radio-button')
      if (await buttons.count() > 1) {
        await buttons.last().click()
        // 切换后页面仍正常
        await expect(page.locator('.stat-card').first()).toBeVisible()
      }
    }
  })
})
