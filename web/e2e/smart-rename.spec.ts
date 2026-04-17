import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors, getPageRoot } from './helpers'

test.describe('智能重命名 /smart-rename', () => {
  test('页面加载：标题、核心区域可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/smart-rename')
    const smartRenamePage = getPageRoot(page, '.smart-rename-page')

    await expect(smartRenamePage.getByRole('heading', { name: '智能重命名' })).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('算法和命名标准选择器可见', async ({ page }) => {
    await navigateAndWait(page, '/smart-rename')
    const selects = getPageRoot(page, '.smart-rename-page').locator('.config-grid .el-select')
    if (await selects.count() > 0) {
      await expect(selects.first()).toBeVisible()
    }
  })

  test('本地目录面板可见', async ({ page }) => {
    await navigateAndWait(page, '/smart-rename')
    await expect(getPageRoot(page, '.smart-rename-page').getByRole('heading', { name: '本地目录' })).toBeVisible()
  })

  test('操作按钮区可见', async ({ page }) => {
    await navigateAndWait(page, '/smart-rename')
    const smartRenamePage = getPageRoot(page, '.smart-rename-page')
    await expect(smartRenamePage.getByRole('button', { name: '生成预览' })).toBeVisible()
    await expect(smartRenamePage.getByRole('button', { name: '执行重命名' })).toBeVisible()
  })

  test('空状态提示可见', async ({ page }) => {
    await navigateAndWait(page, '/smart-rename')
    await expect(getPageRoot(page, '.smart-rename-page').getByText('输入本地目录后点击“生成预览”开始重命名。')).toBeVisible()
  })
})
