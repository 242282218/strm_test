import { test as setup, expect, type APIRequestContext } from '@playwright/test'

interface AuthStatusResponse {
  auth_required: boolean
  has_admin_user: boolean
  can_init_admin: boolean
}

interface InitAdminResponse {
  success: boolean
  username: string
}

async function getAuthStatus(request: APIRequestContext): Promise<AuthStatusResponse> {
  const response = await request.get('/api/auth/status')
  expect(response.ok()).toBeTruthy()
  return await response.json() as AuthStatusResponse
}

async function initAdminIfNeeded(request: APIRequestContext, authStatus: AuthStatusResponse): Promise<string | null> {
  if (!authStatus.auth_required || authStatus.has_admin_user) {
    return null
  }

  if (!authStatus.can_init_admin) {
    throw new Error('auth required but bootstrap init-admin is unavailable')
  }

  const response = await request.post('/api/auth/init-admin')
  if (!response.ok()) {
    throw new Error(`init-admin failed (${response.status()}): ${await response.text()}`)
  }

  const payload = await response.json() as InitAdminResponse
  return payload.username || null
}

/**
 * 全局登录 setup：登录一次并保存 storageState，后续所有测试复用。
 *
 * 默认情况下，`npm run test:e2e` 会通过 Playwright `webServer`
 * 自动拉起或复用前后端，再执行下面的登录初始化逻辑。
 *
 * 如果你的 admin 密码不是 admin，或你要跑自定义端口，请通过环境变量覆盖：
 *   E2E_USERNAME=admin E2E_PASSWORD=yourpass npx playwright test
 */
setup('authenticate', async ({ page, request }) => {
  const authStatus = await getAuthStatus(request)

  await page.goto('/login')
  await expect(page.locator('.login-container')).toBeVisible()

  if (!authStatus.auth_required) {
    await page.context().storageState({ path: 'e2e/.auth/state.json' })
    return
  }

  const bootstrappedUsername = await initAdminIfNeeded(request, authStatus)
  const username = process.env.E2E_USERNAME ?? bootstrappedUsername ?? process.env.ADMIN_USERNAME ?? 'admin'
  const password = process.env.E2E_PASSWORD ?? process.env.ADMIN_PASSWORD ?? 'admin'

  if (bootstrappedUsername) {
    await page.reload()
  }

  // 填写凭据
  await page.getByPlaceholder('用户名').fill(username)
  await page.getByPlaceholder('密码').fill(password)

  // 点击登录
  await page.locator('.login-btn').click()

  // 等待跳转到 dashboard（最多 15 秒，含网络请求）
  await page.waitForURL('**/dashboard', { timeout: 15_000 })

  // 保存登录态
  await page.context().storageState({ path: 'e2e/.auth/state.json' })
})
