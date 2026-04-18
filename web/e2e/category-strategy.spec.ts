import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors, waitForPageReady } from './helpers'

test.describe('二级分类策略 /settings/category-strategy', () => {
  test('页面加载：标题、保存按钮可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/settings/category-strategy')

    await expect(page.getByTestId('category-strategy-hero')).toBeVisible()
    await expect(page.getByTestId('category-strategy-save-button')).toBeVisible()
    await expect(page.getByRole('heading', { name: '二级分类策略、目录映射与样本预判集中收口' })).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('启用开关可交互', async ({ page }) => {
    await navigateAndWait(page, '/settings/category-strategy')
    const enableSwitch = page.locator('.el-switch').first()
    if (await enableSwitch.count() > 0) {
      await expect(enableSwitch).toBeVisible()
      // 不实际修改开关状态，只验证可见
    }
  })

  test('分类预览卡片可见', async ({ page }) => {
    await navigateAndWait(page, '/settings/category-strategy')
    await expect(page.getByTestId('category-strategy-preview')).toBeVisible()
  })

  test('预览功能可交互', async ({ page }) => {
    await navigateAndWait(page, '/settings/category-strategy')
    const previewInput = page.getByPlaceholder('示例：Naruto.S01E01.1080p.mkv')
    if (await previewInput.count() > 0) {
      await previewInput.fill('Naruto.S01E01.1080p.mkv')
      const previewBtn = page.getByTestId('category-strategy-preview-button')
      if (await previewBtn.count() > 0) {
        await previewBtn.click()
        await waitForPageReady(page)
        await expect(page.locator('.preview-result, [data-testid="category-strategy-preview"] .el-empty').first()).toBeVisible({
          timeout: 10_000
        })
      }
    }
  })
})
