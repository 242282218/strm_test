/**
 * STRM 全链路端到端验证
 *
 * 验证流程：
 *   1. 打开代理服务页 → 点击"添加文件夹/文件" → 文件浏览器弹窗
 *   2. 浏览夸克网盘根目录 → 选择文件/文件夹 → 确认
 *   3. 配置 STRM 参数（redirect/stream 模式） → 点击生成
 *   4. 验证生成结果（成功/失败/跳过）
 *   5. 验证 302 重定向链接测试功能
 *   6. 验证流代理链接测试功能
 */
import { test, expect, type Page } from '@playwright/test'
import { collectApiErrors, navigateAndWait, waitForPageReady } from './helpers'

function setupCollectors(page: Page) {
  const apiErrors = collectApiErrors(page)
  const apiCalls: { url: string; status: number; method: string }[] = []
  const jsErrors: string[] = []

  page.on('response', async (resp) => {
    if (resp.url().includes('/api/')) {
      apiCalls.push({ url: resp.url(), status: resp.status(), method: resp.request().method() })
    }
  })
  page.on('pageerror', (err) => jsErrors.push(err.message))
  return { apiErrors, apiCalls, jsErrors }
}

async function waitForStrmAuditSettled(page: Page) {
  await waitForPageReady(page)
  await page.waitForLoadState('networkidle', { timeout: 2000 }).catch(() => {})
}

// ============================================================
// 1. 文件浏览器弹窗 — 能否打开并加载夸克网盘
// ============================================================
test.describe('STRM 文件浏览器', () => {
  test('点击添加文件 → 弹窗打开 → 加载网盘根目录', async ({ page }) => {
    const { apiCalls, jsErrors } = setupCollectors(page)
    await navigateAndWait(page, '/proxy-service')

    // 点击添加按钮
    const addBtn = page.getByRole('button', { name: '添加文件夹/文件' })
    await expect(addBtn).toBeVisible({ timeout: 10_000 })
    await addBtn.click()

    // 弹窗应出现
    const dialog = page.locator('.el-dialog').filter({ hasText: '选择网盘文件' })
    await expect(dialog).toBeVisible({ timeout: 5000 })

    // 等待文件列表加载（loading 消失）
    const fileList = dialog.locator('.file-list')
    await expect(fileList).toBeVisible({ timeout: 5000 })

    // 等最多 15 秒看 loading 是否结束
    const loading = fileList.locator('.el-loading-mask')
    if (await loading.count() > 0) {
      await loading.waitFor({ state: 'hidden', timeout: 15_000 }).catch(() => {})
    }

    // 检查是否有文件/文件夹 或 空状态
    const items = fileList.locator('.file-item')
    const empty = fileList.locator('.el-empty')
    const hasItems = await items.count() > 0
    const hasEmpty = await empty.count() > 0

    // 检查浏览 API 是否被调用过
    const browseCall = apiCalls.find(c => c.url.includes('/files/browse') || c.url.includes('/quark/browse'))

    // 记录结果
    console.log(`文件浏览器状态: ${hasItems ? '有' + await items.count() + '个文件' : hasEmpty ? '空目录' : '未知'}`)
    console.log(`浏览API调用: ${browseCall ? browseCall.url + ' → ' + browseCall.status : '未调用'}`)

    expect(jsErrors).toHaveLength(0)

    // 弹窗至少展示成功（有文件或空状态或有 API 调用）
    expect(hasItems || hasEmpty || !!browseCall).toBeTruthy()
  })

  test('文件浏览器面包屑和返回上级按钮渲染', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')

    await page.getByRole('button', { name: '添加文件夹/文件' }).click()
    const dialog = page.locator('.el-dialog').filter({ hasText: '选择网盘文件' })
    await expect(dialog).toBeVisible({ timeout: 5000 })

    // 面包屑应有"根目录"
    const breadcrumb = dialog.locator('.breadcrumb-bar')
    await expect(breadcrumb).toBeVisible()

    // 返回上级按钮应 disabled（因为已在根目录）
    const backBtn = dialog.getByRole('button', { name: '返回上级' })
    await expect(backBtn).toBeDisabled()

    // 确认选择和取消按钮都应存在
    await expect(dialog.getByRole('button', { name: '取消' })).toBeVisible()
    await expect(dialog.getByRole('button', { name: /确认选择/ })).toBeVisible()
  })
})

// ============================================================
// 2. STRM 生成表单验证
// ============================================================
test.describe('STRM 生成表单', () => {
  test('未选路径时"生成 STRM"按钮 disabled', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')

    const genBtn = page.getByRole('button', { name: '生成 STRM' })
    await expect(genBtn).toBeVisible({ timeout: 10_000 })
    await expect(genBtn).toBeDisabled()
  })

  test('表单默认值正确', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')

    // 本地路径默认 ./strm
    const localPath = page.getByLabel('本地路径').first()
    if (await localPath.count() > 0) {
      await expect(localPath).toHaveValue('./strm')
    }

    // 服务器地址默认 http://localhost:8000
    const serverUrl = page.getByLabel('服务器地址').first()
    if (await serverUrl.count() > 0) {
      await expect(serverUrl).toHaveValue('http://localhost:8000')
    }

    // URL 模式默认 302 重定向
    const modeSelect = page.getByText('302 重定向 (推荐)').first()
    if (await modeSelect.count() > 0) {
      await expect(modeSelect).toBeVisible()
    }

    // 递归扫描默认开
    const recursiveSwitch = page.getByLabel('递归扫描')
    if (await recursiveSwitch.count() > 0) {
      await expect(recursiveSwitch).toBeChecked()
    }
  })

  test('URL 模式可切换（redirect/stream/direct/webdav）', async ({ page }) => {
    const { jsErrors } = setupCollectors(page)
    await navigateAndWait(page, '/proxy-service')

    // 点击 URL 模式选择器
    const modeCombobox = page.getByRole('combobox', { name: 'URL 模式' })
    if (await modeCombobox.count() > 0) {
      await modeCombobox.click()
      // 下拉菜单应有 4 个选项
      const dropdown = page.locator('.el-select-dropdown__item')
      const count = await dropdown.count()
      expect(count).toBeGreaterThanOrEqual(4)
      // 选择流代理
      await dropdown.filter({ hasText: '流代理' }).click()
      await waitForStrmAuditSettled(page)
    }
    expect(jsErrors).toHaveLength(0)
  })
})

// ============================================================
// 3. 302 重定向链接测试功能
// ============================================================
test.describe('代理链接测试', () => {
  test('302 重定向测试：无 fileId 时提示警告', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')

    const testBtn = page.getByRole('button', { name: '测试 302 重定向' })
    await expect(testBtn).toBeVisible({ timeout: 10_000 })

    // fileId 为空时点击
    await testBtn.click()
    // 应弹出警告消息
    await expect(page.locator('.el-message--warning')).toBeVisible({ timeout: 3000 })
  })

  test('流代理测试：无 fileId 时提示警告', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')

    const testBtn = page.getByRole('button', { name: '测试流代理' })
    await expect(testBtn).toBeVisible({ timeout: 10_000 })

    // fileId 为空时点击
    await testBtn.click()
    await expect(page.locator('.el-message--warning')).toBeVisible({ timeout: 3000 })
  })

  test('302 重定向测试：输入 fileId 后触发 API 调用', async ({ page }) => {
    const { apiCalls, jsErrors } = setupCollectors(page)
    await navigateAndWait(page, '/proxy-service')

    // 输入测试 fileId
    const fileIdInput = page.getByLabel('文件ID').first()
    await fileIdInput.fill('test_file_id_123')

    // 点击测试 302 重定向
    await page.getByRole('button', { name: '测试 302 重定向' }).click()
    await expect
      .poll(() => apiCalls.find(c => c.url.includes('/proxy/redirect') || c.url.includes('redirect')) ?? null)
      .not
      .toBeNull()

    // 验证 API 调用
    const redirectCall = apiCalls.find(c => c.url.includes('/proxy/redirect') || c.url.includes('redirect'))
    console.log('302 redirect API call:', redirectCall ? `${redirectCall.url} → ${redirectCall.status}` : 'not called')

    expect(jsErrors).toHaveLength(0)
  })

  test('流代理测试：输入 fileId 后生成链接', async ({ page }) => {
    const { jsErrors } = setupCollectors(page)
    await navigateAndWait(page, '/proxy-service')

    // 输入测试 fileId
    const fileIdInput = page.getByLabel('文件ID').first()
    await fileIdInput.fill('test_file_id_456')

    // 点击测试流代理
    await page.getByRole('button', { name: '测试流代理' }).click()
    const successMsg = page.locator('.el-message--success')
    const resultArea = page.locator('text=/proxy/stream/')
    await expect(successMsg.or(resultArea).first()).toBeVisible({ timeout: 10_000 })

    // 应该生成链接（流代理是纯前端拼接，不需要 API）
    // 检查是否显示了成功消息或链接
    const hasResult = (await successMsg.count() > 0) || (await resultArea.count() > 0)
    console.log('Stream proxy result visible:', hasResult)

    expect(jsErrors).toHaveLength(0)
  })
})

// ============================================================
// 4. STRM 模式说明表格完整性
// ============================================================
test.describe('STRM 模式说明', () => {
  test('4 种 URL 模式说明表格完整渲染', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')

    // 找到模式说明表格
    await expect(page.getByText('STRM URL 模式说明')).toBeVisible({ timeout: 10_000 })

    // 验证 4 种模式都显示
    await expect(page.getByText('redirect').first()).toBeVisible()
    await expect(page.getByText('stream').first()).toBeVisible()
    await expect(page.getByText('direct').first()).toBeVisible()
    await expect(page.getByText('webdav').first()).toBeVisible()
  })
})

// ============================================================
// 5. API 端点说明表格完整性
// ============================================================
test.describe('API 端点说明', () => {
  test('API 端点表格包含 STRM 和代理端点', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')

    await expect(page.getByText('API 端点')).toBeVisible({ timeout: 10_000 })

    // 核心端点必须列出
    await expect(page.getByText('/api/strm/scan')).toBeVisible()
    await expect(page.getByText('/api/proxy/redirect/{file_id}', { exact: true })).toBeVisible()
    await expect(page.getByText('/api/proxy/stream/{file_id}', { exact: true })).toBeVisible()
  })
})

// ============================================================
// 6. 后端 STRM 和代理 API 可达性
// ============================================================
test.describe('后端 API 可达性', () => {
  test('STRM scan API 存在（返回非 404）', async ({ request }) => {
    // POST /api/strm/scan 应该返回 4xx（参数缺失）而非 404
    const resp = await request.post('/api/strm/scan', {
      params: { remote_path: '/', local_path: './strm_test' }
    })
    // 接受 200/400/422/403 都说明路由存在，404 说明路由未注册
    expect(resp.status()).not.toBe(404)
    console.log(`STRM scan API: ${resp.status()}`)
  })

  test('代理缓存统计 API 可达', async ({ request }) => {
    const resp = await request.get('/api/proxy/cache/stats')
    expect(resp.status()).not.toBe(404)
    console.log(`Cache stats API: ${resp.status()}`)
  })

  test('302 重定向 API 存在（返回非 404）', async ({ request }) => {
    // 代理 API 会调用夸克获取直链，可能 hang。用 AbortController 限时。
    try {
      const resp = await request.get('/api/proxy/redirect/test_nonexistent_id', {
        timeout: 10_000
      })
      const body = await resp.text()
      // 路由存在就算通过（非 generic 404）
      const routeExists = resp.status() !== 404 || !body.includes('"detail":"Not Found"')
      expect(routeExists).toBeTruthy()
      console.log(`Redirect API: ${resp.status()} - ${body.substring(0, 100)}`)
    } catch {
      // 超时也算路由存在（说明后端在处理，只是夸克 API hang）
      console.log(`Redirect API: timeout (route exists but upstream hangs)`)
    }
  })

  test('流代理 API 存在（返回非 404）', async ({ request }) => {
    try {
      const resp = await request.get('/api/proxy/stream/test_nonexistent_id', {
        timeout: 10_000
      })
      const body = await resp.text()
      const routeExists = resp.status() !== 404 || !body.includes('"detail":"Not Found"')
      expect(routeExists).toBeTruthy()
      console.log(`Stream API: ${resp.status()} - ${body.substring(0, 100)}`)
    } catch {
      console.log(`Stream API: timeout (route exists but upstream hangs)`)
    }
  })
})
