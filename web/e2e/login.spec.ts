import { test, expect } from '@playwright/test'

// 登录页是公开路由，不需要 storageState，使用独立 context
test.use({ storageState: { cookies: [], origins: [] } })

test.describe('登录页 /login', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
  })

  test('页面渲染：表单、按钮、版本号可见', async ({ page }) => {
    await expect(page.locator('.login-container')).toBeVisible()
    await expect(page.locator('.login-card')).toBeVisible()
    await expect(page.getByPlaceholder('用户名')).toBeVisible()
    await expect(page.getByPlaceholder('密码')).toBeVisible()
    await expect(page.locator('.login-btn')).toBeVisible()
    await expect(page.getByText('记住我')).toBeVisible()
  })

  test('空提交触发校验提示', async ({ page }) => {
    await page.locator('.login-btn').click()
    // Element Plus 表单校验会显示错误提示
    await expect(page.locator('.el-form-item__error').first()).toBeVisible({ timeout: 3000 })
  })

  test('错误密码显示错误提示', async ({ page }) => {
    await page.getByPlaceholder('用户名').fill('admin')
    await page.getByPlaceholder('密码').fill('wrong_password_12345')
    await page.locator('.login-btn').click()
    // 等待错误提示（alert 角色元素）
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 10_000 })
  })

  test('成功登录跳转到 /dashboard', async ({ page }) => {
    const username = process.env.E2E_USERNAME ?? 'admin'
    const password = process.env.E2E_PASSWORD ?? 'admin'
    await page.getByPlaceholder('用户名').fill(username)
    await page.getByPlaceholder('密码').fill(password)
    await page.locator('.login-btn').click()
    await page.waitForURL('**/dashboard', { timeout: 15_000 })
    await expect(page).toHaveURL(/dashboard/)
  })
})
