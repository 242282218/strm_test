import { test, expect } from '@playwright/test'

test.describe('404 页面', () => {
  test('访问不存在路径显示 404', async ({ page }) => {
    await page.goto('/this-page-does-not-exist-12345')
    await expect(page.getByRole('heading', { name: '页面未找到' })).toBeVisible({ timeout: 10_000 })
  })

  test('显示 404 错误码和提示', async ({ page }) => {
    await page.goto('/random-nonexistent-path')
    await expect(page.getByText('404')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('页面未找到')).toBeVisible()
  })

  test('返回首页按钮可用', async ({ page }) => {
    await page.goto('/random-nonexistent-path')
    const homeBtn = page.getByText('返回首页')
    await expect(homeBtn).toBeVisible({ timeout: 10_000 })
    await homeBtn.click()
    await page.waitForURL('**/dashboard', { timeout: 10_000 })
  })
})
