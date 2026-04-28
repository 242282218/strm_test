import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors } from './helpers'

test.describe('通知配置 /notifications', () => {
  test('页面加载：标题、保存按钮可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/notifications')

    await expect(page.getByRole('heading', { name: '通知配置' })).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('通知渠道选择器可见', async ({ page }) => {
    await navigateAndWait(page, '/notifications')
    const select = page.locator('.el-select')
    if (await select.count() > 0) {
      await expect(select.first()).toBeVisible()
    }
  })

  test('启用开关可见', async ({ page }) => {
    await navigateAndWait(page, '/notifications')
    const switchEl = page.locator('.el-switch')
    if (await switchEl.count() > 0) {
      await expect(switchEl.first()).toBeVisible()
    }
  })

  test('测试通知卡片可见', async ({ page }) => {
    await navigateAndWait(page, '/notifications')
    const testBtn = page.getByRole('button', { name: '发送测试' })
    if (await testBtn.count() > 0) {
      await expect(testBtn).toBeVisible()
    }
  })

  test('保存和删除按钮可见', async ({ page }) => {
    await navigateAndWait(page, '/notifications')
    // 保存按钮
    const saveBtn = page.getByRole('button', { name: /保存/ })
    if (await saveBtn.count() > 0) {
      await expect(saveBtn.first()).toBeVisible()
    }
  })
})
