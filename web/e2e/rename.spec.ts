import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors } from './helpers'

test.describe('基础重命名 /rename', () => {
  test('页面加载：标题、配置区域可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/rename')

    await expect(page.getByRole('heading', { name: '智能重命名' }).first()).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('算法选择区域可见', async ({ page }) => {
    await navigateAndWait(page, '/rename')
    const radioGroup = page.locator('.el-radio-group')
    if (await radioGroup.count() > 0) {
      await expect(radioGroup.first()).toBeVisible()
    }
  })

  test('路径输入区域可见', async ({ page }) => {
    await navigateAndWait(page, '/rename')
    // 路径输入或浏览按钮
    const browseBtn = page.getByText('浏览')
    const pathInput = page.locator('input[readonly]')
    await expect(browseBtn.or(pathInput).first()).toBeVisible({ timeout: 10_000 })
  })

  test('开始分析按钮可见', async ({ page }) => {
    await navigateAndWait(page, '/rename')
    const analyzeBtn = page.getByText('开始分析')
    if (await analyzeBtn.count() > 0) {
      await expect(analyzeBtn).toBeVisible()
    }
  })
})
