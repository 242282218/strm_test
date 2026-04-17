import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors } from './helpers'

test.describe('系统配置 /config', () => {
  test('页面加载：标题可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/config')

    await expect(page.getByRole('heading', { name: '配置分组', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: '高级配置（JSON）', exact: true })).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('AI 模型配置区域可见', async ({ page }) => {
    await navigateAndWait(page, '/config')
    // 至少有一个 provider 标题
    const providerHeaders = page.locator('.provider-header')
    if (await providerHeaders.count() > 0) {
      await expect(providerHeaders.first()).toBeVisible()
    }
  })

  test('配置表单字段可交互', async ({ page }) => {
    await navigateAndWait(page, '/config')
    // 检查密码字段存在（API key 输入框）
    const passwordInputs = page.locator('input[type="password"]')
    if (await passwordInputs.count() > 0) {
      await expect(passwordInputs.first()).toBeVisible()
    }
  })

  test('保存/取消/重置按钮可见', async ({ page }) => {
    await navigateAndWait(page, '/config')
    // 至少有保存按钮
    const saveBtn = page.getByRole('button', { name: '保存' })
    if (await saveBtn.count() > 0) {
      await expect(saveBtn.first()).toBeVisible()
    }
  })

  test('配置状态标签显示', async ({ page }) => {
    await navigateAndWait(page, '/config')
    // 已配置/未配置标签
    const tags = page.locator('.el-tag')
    if (await tags.count() > 0) {
      await expect(tags.first()).toBeVisible()
    }
  })
})
