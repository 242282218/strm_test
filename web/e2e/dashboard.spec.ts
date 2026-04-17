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
    await expect(page.locator('.chart-container canvas').first()).toBeVisible({ timeout: 10_000 })
  })

  test('刷新按钮会同时刷新统计与趋势', async ({ page }) => {
    await navigateAndWait(page, '/dashboard')
    const refreshBtn = page.getByText('刷新数据')
    const statsResponse = page.waitForResponse(response =>
      response.request().method() === 'GET' && response.url().includes('/api/dashboard/stats'),
    )
    const trendsResponse = page.waitForResponse(response =>
      response.request().method() === 'GET' && response.url().includes('/api/dashboard/trends'),
    )

    await refreshBtn.click()

    expect((await statsResponse).status()).toBe(200)
    expect((await trendsResponse).status()).toBe(200)
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('.chart-container canvas').first()).toBeVisible({ timeout: 10_000 })
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

  test('快捷入口会打开预填任务弹窗并在关闭后清理查询参数', async ({ page }) => {
    await navigateAndWait(page, '/dashboard')

    const syncButton = page.getByRole('button', { name: '同步文件' })
    if (await syncButton.count() > 0) {
      await syncButton.click()
      await expect(page).toHaveURL(/\/tasks\?createTask=file_sync$/)
      await expect(page.getByText('新建任务')).toBeVisible({ timeout: 10_000 })

      const cancelButton = page.getByRole('button', { name: '取消' }).last()
      await cancelButton.click()
      await expect(page).toHaveURL(/\/tasks$/)
    }
  })
})
