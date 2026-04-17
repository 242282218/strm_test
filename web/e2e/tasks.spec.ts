import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors, expectTableOrEmpty, getPageRoot } from './helpers'

test.describe('任务管理 /tasks', () => {
  test('页面加载：标题、新建按钮、统计卡片可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/tasks')
    const tasksPage = getPageRoot(page, '.tasks-page')

    await expect(tasksPage.locator('.hero-title')).toBeVisible()
    await expect(tasksPage.locator('.hero-actions').getByRole('button', { name: '新建任务' })).toBeVisible()
    await expect(tasksPage.locator('.metric-card').first()).toBeVisible({ timeout: 10_000 })
    expect(apiErrors).toHaveLength(0)
  })

  test('任务表格或空状态可见', async ({ page }) => {
    await navigateAndWait(page, '/tasks')
    await expectTableOrEmpty(getPageRoot(page, '.tasks-page').locator('.tasks-panel'))
  })

  test('状态筛选器可展开', async ({ page }) => {
    await navigateAndWait(page, '/tasks')
    const filterPanel = getPageRoot(page, '.tasks-page').locator('.filter-panel')
    if (await filterPanel.count() > 0) {
      // 点击状态下拉框
      const statusSelect = filterPanel.locator('.el-select').first()
      await statusSelect.click()
      // 等待下拉菜单出现
      await expect(page.locator('.el-select-dropdown')).toBeVisible({ timeout: 5000 })
    }
  })

  test('新建任务弹窗可打开', async ({ page }) => {
    await navigateAndWait(page, '/tasks')
    await getPageRoot(page, '.tasks-page')
      .locator('.hero-actions')
      .getByRole('button', { name: '新建任务' })
      .click()
    // 等待新建任务弹窗出现
    await expect(page.locator('.el-dialog').first()).toBeVisible({ timeout: 5000 })
  })

  test('分页组件可见（有数据时）', async ({ page }) => {
    await navigateAndWait(page, '/tasks')
    const pagination = page.locator('.el-pagination')
    // 分页可能不存在（数据量少），只在存在时检查
    if (await pagination.count() > 0) {
      await expect(pagination).toBeVisible()
    }
  })
})
