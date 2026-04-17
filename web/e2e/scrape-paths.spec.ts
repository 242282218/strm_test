import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors } from './helpers'

test.describe('刮削目录 /scrape-pathes', () => {
  test('页面加载：标题、新增按钮可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/scrape-pathes')

    await expect(page.getByRole('heading', { name: '刮削目录', exact: true })).toBeVisible()
    await expect(page.getByTestId('scrape-create-button')).toBeVisible()
    await expect(page.getByRole('button', { name: '刷新', exact: true })).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('目录表格或空状态可见', async ({ page }) => {
    await navigateAndWait(page, '/scrape-pathes')
    const table = page.locator('.el-table')
    const empty = page.locator('.empty-state')
    await expect(table.or(empty).first()).toBeVisible({ timeout: 10_000 })
  })

  test('筛选表单可交互', async ({ page }) => {
    await navigateAndWait(page, '/scrape-pathes')
    const keywordInput = page.getByPlaceholder('source/dest/path_id')
    if (await keywordInput.count() > 0) {
      await keywordInput.fill('test')
      await page.getByText('查询').first().click()
      // 查询后表格/空状态仍可见
      await expect(
        page.locator('.el-table').or(page.locator('.empty-state')).first()
      ).toBeVisible({ timeout: 10_000 })
    }
  })

  test('新增目录弹窗可打开', async ({ page }) => {
    await navigateAndWait(page, '/scrape-pathes')
    await page.getByTestId('scrape-create-button').click()
    await expect(page.locator('.el-dialog')).toBeVisible({ timeout: 5000 })
    // 弹窗标题
    await expect(page.getByText('新增刮削目录')).toBeVisible()
  })

  test('新增弹窗包含必要字段', async ({ page }) => {
    await navigateAndWait(page, '/scrape-pathes')
    await page.getByTestId('scrape-create-button').click()
    await expect(page.locator('.el-dialog')).toBeVisible({ timeout: 5000 })
    // 关键表单字段
    await expect(page.getByPlaceholder('例如: D:/media/raw')).toBeVisible()
    await expect(page.getByPlaceholder('例如: D:/media/library')).toBeVisible()
  })
})
