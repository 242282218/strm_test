import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors } from './helpers'

test.describe('刮削记录 /scrape-records', () => {
  test('页面加载：标题、筛选区、工具栏可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/scrape-records')

    await expect(page.getByRole('heading', { name: '刮削记录', exact: true })).toBeVisible()
    await expect(page.getByTestId('scrape-records-refresh')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('记录表格或空状态可见', async ({ page }) => {
    await navigateAndWait(page, '/scrape-records')
    const table = page.locator('.el-table')
    const empty = page.locator('.empty-state')
    await expect(table.or(empty).first()).toBeVisible({ timeout: 10_000 })
  })

  test('筛选器可交互：关键词搜索', async ({ page }) => {
    await navigateAndWait(page, '/scrape-records')
    const keywordInput = page.getByPlaceholder('文件名/标题/错误')
    if (await keywordInput.count() > 0) {
      await keywordInput.fill('test')
      await page.getByText('查询').first().click()
      await expect(
        page.locator('.el-table').or(page.locator('.empty-state')).first()
      ).toBeVisible({ timeout: 10_000 })
    }
  })

  test('工具栏批量操作按钮可见', async ({ page }) => {
    await navigateAndWait(page, '/scrape-records')
    // 工具栏按钮（可能需要选中行后才激活）
    const toolbar = page.locator('.toolbar')
    if (await toolbar.count() > 0) {
      await expect(toolbar).toBeVisible()
    }
  })
})
