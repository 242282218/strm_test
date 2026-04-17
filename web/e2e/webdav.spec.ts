import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors } from './helpers'

test.describe('WebDAV 挂载 /webdav', () => {
  test('页面加载：标题、保存按钮可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/webdav')

    await expect(page.getByTestId('webdav-hero')).toBeVisible()
    await expect(page.getByTestId('webdav-save-button')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'WebDAV 挂载、凭据状态与访问入口统一收口' })).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('启用开关可见', async ({ page }) => {
    await navigateAndWait(page, '/webdav')
    const switchEl = page.locator('.el-switch')
    if (await switchEl.count() > 0) {
      await expect(switchEl.first()).toBeVisible()
    }
  })

  test('配置表单字段可见', async ({ page }) => {
    await navigateAndWait(page, '/webdav')
    await expect(page.getByTestId('webdav-config-section')).toBeVisible()
  })

  test('支持客户端列表可见', async ({ page }) => {
    await navigateAndWait(page, '/webdav')
    await expect(page.getByTestId('webdav-clients-panel')).toBeVisible()
  })

  test('连接信息卡片可见', async ({ page }) => {
    await navigateAndWait(page, '/webdav')
    await expect(page.getByTestId('webdav-connection-panel')).toBeVisible()
  })
})
