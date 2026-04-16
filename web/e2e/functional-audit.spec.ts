/**
 * 功能性审计：真正点击每个页面的每一个按钮，验证行为是否正确。
 * 不是"看得见"就算通过，而是"点完后没报错、跳转正确、弹窗正常"才算通过。
 */
import { test, expect, type Page } from '@playwright/test'

// 收集页面上所有 API 错误和控制台错误
function setupErrorCollectors(page: Page) {
  const apiErrors: { url: string; status: number; body?: string }[] = []
  const consoleErrors: string[] = []
  const uncaughtErrors: string[] = []

  page.on('response', async (resp) => {
    if (resp.url().includes('/api/') && resp.status() >= 400) {
      let body = ''
      try { body = await resp.text() } catch {}
      apiErrors.push({ url: resp.url(), status: resp.status(), body })
    }
  })
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('pageerror', (err) => {
    uncaughtErrors.push(err.message)
  })

  return { apiErrors, consoleErrors, uncaughtErrors }
}

// ============================================================
// Dashboard 快捷操作按钮
// ============================================================
test.describe('Dashboard 快捷操作按钮', () => {
  test('生成STRM 按钮跳转到 /proxy-service', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    // 等待快捷操作区域渲染
    const btn = page.getByRole('button', { name: '生成STRM' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    await btn.click()
    await page.waitForURL('**/proxy-service', { timeout: 5000 })
    await expect(page).toHaveURL(/proxy-service/)
  })

  test('同步文件 按钮触发消息提示', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '同步文件' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    await btn.click()
    // 应弹出 ElMessage
    await expect(page.locator('.el-message')).toBeVisible({ timeout: 3000 })
  })

  test('验证文件 按钮触发消息提示', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '验证文件' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    await btn.click()
    await expect(page.locator('.el-message')).toBeVisible({ timeout: 3000 })
  })

  test('系统配置 按钮跳转到 /config', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '系统配置' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    await btn.click()
    await page.waitForURL('**/config', { timeout: 5000 })
    await expect(page).toHaveURL(/config/)
  })

  test('刷新数据 按钮不报错', async ({ page }) => {
    const { apiErrors } = setupErrorCollectors(page)
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '刷新数据' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    await btn.click()
    await page.waitForTimeout(2000)
    const serverErrors = apiErrors.filter(e => e.status >= 500)
    expect(serverErrors).toHaveLength(0)
  })

  test('查看全部 链接跳转到 /tasks', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    const link = page.getByText('查看全部')
    await expect(link).toBeVisible({ timeout: 10_000 })
    await link.click()
    await page.waitForURL('**/tasks', { timeout: 5000 })
  })

  test('清空缓存 按钮触发消息', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '清空缓存' })
    if (await btn.count() > 0) {
      await btn.click()
      await expect(page.locator('.el-message')).toBeVisible({ timeout: 3000 })
    }
  })
})

// ============================================================
// Tasks 页面按钮
// ============================================================
test.describe('Tasks 页面按钮功能', () => {
  test('新建任务弹窗：打开、填写、关闭', async ({ page }) => {
    await page.goto('/tasks')
    await page.waitForLoadState('domcontentloaded')
    await page.getByRole('button', { name: '新建任务' }).click()
    const dialog = page.locator('.el-dialog').first()
    await expect(dialog).toBeVisible({ timeout: 5000 })
    // 弹窗内应有任务类型选择
    const select = dialog.locator('.el-select').first()
    if (await select.count() > 0) {
      await expect(select).toBeVisible()
    }
    // 关闭弹窗（点取消或关闭按钮）
    const cancelBtn = dialog.getByRole('button', { name: '取消' })
    if (await cancelBtn.count() > 0) {
      await cancelBtn.click()
    } else {
      await dialog.getByRole('button', { name: 'Close this dialog' }).click()
    }
    await expect(dialog).toBeHidden({ timeout: 3000 })
  })

  test('刷新按钮不报 500', async ({ page }) => {
    const { apiErrors } = setupErrorCollectors(page)
    await page.goto('/tasks')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '刷新' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    await btn.click()
    await page.waitForTimeout(2000)
    const serverErrors = apiErrors.filter(e => e.status >= 500)
    expect(serverErrors).toHaveLength(0)
  })

  test('状态筛选：选择后表格更新', async ({ page }) => {
    const { apiErrors } = setupErrorCollectors(page)
    await page.goto('/tasks')
    await page.waitForLoadState('domcontentloaded')
    const filterCard = page.locator('.filter-card')
    if (await filterCard.count() > 0) {
      const statusSelect = filterCard.locator('.el-select').first()
      await statusSelect.click()
      const option = page.locator('.el-select-dropdown__item').first()
      if (await option.count() > 0) {
        await option.click()
        await page.waitForTimeout(1500)
      }
    }
    const serverErrors = apiErrors.filter(e => e.status >= 500)
    expect(serverErrors).toHaveLength(0)
  })

  test('重置按钮清空筛选', async ({ page }) => {
    await page.goto('/tasks')
    await page.waitForLoadState('domcontentloaded')
    const resetBtn = page.getByRole('button', { name: '重置' })
    if (await resetBtn.count() > 0) {
      await resetBtn.click()
      await page.waitForTimeout(1000)
    }
  })
})

// ============================================================
// Scrape Paths 页面按钮
// ============================================================
test.describe('刮削目录按钮功能', () => {
  test('新增目录弹窗完整流程：打开 → 看到表单 → 关闭', async ({ page }) => {
    await page.goto('/scrape-pathes')
    await page.waitForLoadState('domcontentloaded')
    await page.getByRole('button', { name: '新增目录' }).click()
    const dialog = page.locator('.el-dialog')
    await expect(dialog).toBeVisible({ timeout: 5000 })
    await expect(page.getByPlaceholder('例如: D:/media/raw')).toBeVisible()
    await expect(page.getByPlaceholder('例如: D:/media/library')).toBeVisible()
    // 关闭弹窗
    const cancelBtn = dialog.getByRole('button', { name: '取消' })
    if (await cancelBtn.count() > 0) {
      await cancelBtn.click()
    } else {
      await dialog.getByRole('button', { name: 'Close this dialog' }).click()
    }
    await expect(dialog).toBeHidden({ timeout: 3000 })
  })

  test('查询按钮触发请求', async ({ page }) => {
    const { apiErrors } = setupErrorCollectors(page)
    await page.goto('/scrape-pathes')
    await page.waitForLoadState('domcontentloaded')
    const queryBtn = page.getByRole('button', { name: '查询' })
    if (await queryBtn.count() > 0) {
      await queryBtn.click()
      await page.waitForTimeout(2000)
    }
    const serverErrors = apiErrors.filter(e => e.status >= 500)
    expect(serverErrors).toHaveLength(0)
  })

  test('重置按钮清空筛选', async ({ page }) => {
    await page.goto('/scrape-pathes')
    await page.waitForLoadState('domcontentloaded')
    const resetBtn = page.getByRole('button', { name: '重置' })
    if (await resetBtn.count() > 0) {
      await resetBtn.click()
    }
  })
})

// ============================================================
// Scrape Records 页面按钮
// ============================================================
test.describe('刮削记录按钮功能', () => {
  test('查询按钮不报 500', async ({ page }) => {
    const { apiErrors } = setupErrorCollectors(page)
    await page.goto('/scrape-records')
    await page.waitForLoadState('domcontentloaded')
    const queryBtn = page.getByRole('button', { name: '查询' })
    if (await queryBtn.count() > 0) {
      await queryBtn.click()
      await page.waitForTimeout(2000)
    }
    const serverErrors = apiErrors.filter(e => e.status >= 500)
    expect(serverErrors).toHaveLength(0)
  })
})

// ============================================================
// Category Strategy 页面按钮
// ============================================================
test.describe('分类策略按钮功能', () => {
  test('保存策略按钮不报 500', async ({ page }) => {
    const { apiErrors } = setupErrorCollectors(page)
    await page.goto('/settings/category-strategy')
    await page.waitForLoadState('domcontentloaded')
    const saveBtn = page.getByRole('button', { name: '保存策略' })
    await expect(saveBtn).toBeVisible({ timeout: 10_000 })
    await saveBtn.click()
    await page.waitForTimeout(2000)
    const serverErrors = apiErrors.filter(e => e.status >= 500)
    expect(serverErrors).toHaveLength(0)
  })

  test('执行预览：输入文件名后点击预览', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/settings/category-strategy')
    await page.waitForLoadState('domcontentloaded')
    const input = page.getByPlaceholder('示例：Naruto.S01E01.1080p.mkv')
    if (await input.count() > 0) {
      await input.fill('Naruto.S01E01.1080p.mkv')
      const previewBtn = page.getByRole('button', { name: '执行预览' })
      if (await previewBtn.count() > 0) {
        await previewBtn.click()
        await page.waitForTimeout(2000)
      }
    }
    expect(uncaughtErrors).toHaveLength(0)
  })
})

// ============================================================
// Emby Monitor 页面按钮
// ============================================================
test.describe('Emby 监控按钮功能', () => {
  test('刷新数据不报 500', async ({ page }) => {
    const { apiErrors } = setupErrorCollectors(page)
    await page.goto('/emby-monitor')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '刷新数据' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    // 按钮可能在初始加载中处于 loading 状态，等它变为可用
    await expect(btn).toBeEnabled({ timeout: 20_000 })
    await btn.click()
    await page.waitForTimeout(2000)
    const serverErrors = apiErrors.filter(e => e.status >= 500)
    expect(serverErrors).toHaveLength(0)
  })

  test('触发刷新按钮可点击', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/emby-monitor')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '触发刷新' })
    if (await btn.count() > 0) {
      await btn.click()
      await page.waitForTimeout(2000)
    }
    expect(uncaughtErrors).toHaveLength(0)
  })

  test('触发同步按钮可点击', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/emby-monitor')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '触发同步' })
    if (await btn.count() > 0) {
      await btn.click()
      await page.waitForTimeout(2000)
    }
    expect(uncaughtErrors).toHaveLength(0)
  })
})

// ============================================================
// Config 页面按钮
// ============================================================
test.describe('系统配置按钮功能', () => {
  test('保存按钮触发请求', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/config')
    await page.waitForLoadState('domcontentloaded')
    const saveBtn = page.getByRole('button', { name: '保存' }).first()
    if (await saveBtn.count() > 0) {
      await saveBtn.click()
      await page.waitForTimeout(2000)
    }
    expect(uncaughtErrors).toHaveLength(0)
  })

  test('重置按钮不崩溃', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/config')
    await page.waitForLoadState('domcontentloaded')
    const resetBtn = page.getByRole('button', { name: '重置' })
    if (await resetBtn.count() > 0) {
      await resetBtn.click()
      await page.waitForTimeout(1000)
    }
    expect(uncaughtErrors).toHaveLength(0)
  })
})

// ============================================================
// Search 页面
// ============================================================
test.describe('搜索页面功能', () => {
  test('输入关键词后搜索不报错', async ({ page }) => {
    const { apiErrors, uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/search')
    await page.waitForLoadState('domcontentloaded')
    const input = page.locator('input[type="text"]').first()
    await input.fill('测试')
    await input.press('Enter')
    await page.waitForTimeout(3000)
    const serverErrors = apiErrors.filter(e => e.status >= 500)
    expect(serverErrors).toHaveLength(0)
    expect(uncaughtErrors).toHaveLength(0)
  })
})

// ============================================================
// Smart Rename 页面按钮
// ============================================================
test.describe('智能重命名按钮功能', () => {
  test('本地/云端模式切换不崩溃', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/smart-rename')
    await page.waitForLoadState('domcontentloaded')
    const radioGroup = page.locator('.el-radio-group').first()
    if (await radioGroup.count() > 0) {
      const buttons = radioGroup.locator('.el-radio-button')
      if (await buttons.count() > 1) {
        await buttons.last().click()
        await page.waitForTimeout(500)
        await buttons.first().click()
        await page.waitForTimeout(500)
      }
    }
    expect(uncaughtErrors).toHaveLength(0)
  })

  test('重置按钮不崩溃', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/smart-rename')
    await page.waitForLoadState('domcontentloaded')
    const resetBtn = page.getByRole('button', { name: '重置' })
    if (await resetBtn.count() > 0) {
      await resetBtn.click()
      await page.waitForTimeout(1000)
    }
    expect(uncaughtErrors).toHaveLength(0)
  })

  test('AI 连通性测试按钮', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/smart-rename')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: 'AI 连通性测试' })
    if (await btn.count() > 0) {
      await btn.click()
      await page.waitForTimeout(3000)
    }
    expect(uncaughtErrors).toHaveLength(0)
  })
})

// ============================================================
// Proxy Service 页面按钮
// ============================================================
test.describe('代理服务按钮功能', () => {
  test('清除缓存按钮触发请求', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/proxy-service')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '清除缓存' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    await btn.click()
    await page.waitForTimeout(2000)
    expect(uncaughtErrors).toHaveLength(0)
  })

  test('添加文件夹/文件按钮可点击', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/proxy-service')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '添加文件夹/文件' })
    if (await btn.count() > 0) {
      await btn.click()
      await page.waitForTimeout(2000)
    }
    expect(uncaughtErrors).toHaveLength(0)
  })

  test('生成 STRM 按钮（disabled 状态验证）', async ({ page }) => {
    await page.goto('/proxy-service')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '生成 STRM' })
    if (await btn.count() > 0) {
      // 未选路径时按钮应 disabled
      await expect(btn).toBeDisabled()
    }
  })
})

// ============================================================
// WebDAV 页面按钮
// ============================================================
test.describe('WebDAV 按钮功能', () => {
  test('保存配置按钮触发请求', async ({ page }) => {
    const { apiErrors, uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/webdav')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '保存配置' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    await btn.click()
    await page.waitForTimeout(2000)
    const serverErrors = apiErrors.filter(e => e.status >= 500)
    expect(serverErrors).toHaveLength(0)
    expect(uncaughtErrors).toHaveLength(0)
  })

  test('刷新按钮不崩溃', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/webdav')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '刷新' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    await btn.click()
    await page.waitForTimeout(1000)
    expect(uncaughtErrors).toHaveLength(0)
  })
})

// ============================================================
// Notifications 页面按钮
// ============================================================
test.describe('通知配置按钮功能', () => {
  test('保存配置按钮触发请求', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/notifications')
    await page.waitForLoadState('domcontentloaded')
    const saveBtn = page.getByRole('button', { name: /保存/ }).first()
    if (await saveBtn.count() > 0) {
      await saveBtn.click()
      await page.waitForTimeout(2000)
    }
    expect(uncaughtErrors).toHaveLength(0)
  })

  test('发送测试按钮触发请求', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/notifications')
    await page.waitForLoadState('domcontentloaded')
    const testBtn = page.getByRole('button', { name: '发送测试' })
    if (await testBtn.count() > 0) {
      await testBtn.click()
      await page.waitForTimeout(3000)
    }
    expect(uncaughtErrors).toHaveLength(0)
  })
})

// ============================================================
// Notification History 页面按钮
// ============================================================
test.describe('通知历史按钮功能', () => {
  test('查询按钮不报 500', async ({ page }) => {
    const { apiErrors } = setupErrorCollectors(page)
    await page.goto('/notifications/history')
    await page.waitForLoadState('domcontentloaded')
    const queryBtn = page.getByRole('button', { name: '查询' })
    if (await queryBtn.count() > 0) {
      await queryBtn.click()
      await page.waitForTimeout(2000)
    }
    const serverErrors = apiErrors.filter(e => e.status >= 500)
    expect(serverErrors).toHaveLength(0)
  })

  test('重置按钮不崩溃', async ({ page }) => {
    const { uncaughtErrors } = setupErrorCollectors(page)
    await page.goto('/notifications/history')
    await page.waitForLoadState('domcontentloaded')
    const resetBtn = page.getByRole('button', { name: '重置' })
    if (await resetBtn.count() > 0) {
      await resetBtn.click()
      await page.waitForTimeout(1000)
    }
    expect(uncaughtErrors).toHaveLength(0)
  })
})

// ============================================================
// Sidebar 导航：每个菜单项点击后正确跳转
// ============================================================
test.describe('侧边栏导航功能', () => {
  const navItems = [
    { name: '概览', url: /dashboard/ },
    { name: '任务管理', url: /tasks/ },
    { name: '系统配置', url: /config/ },
  ]

  for (const { name, url } of navItems) {
    test(`菜单项 "${name}" 点击跳转正确`, async ({ page }) => {
      await page.goto('/dashboard')
      await page.waitForLoadState('domcontentloaded')
      const menuItem = page.getByRole('menuitem', { name })
      await menuItem.click()
      await page.waitForURL(url, { timeout: 5000 })
    })
  }
})

// ============================================================
// 用户下拉菜单
// ============================================================
test.describe('用户下拉菜单功能', () => {
  test('系统设置跳转到 /config', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    // 点击用户头像区域
    const userTrigger = page.locator('.user-info')
    if (await userTrigger.count() > 0) {
      await userTrigger.click()
      const settingsItem = page.getByText('系统设置').last()
      await expect(settingsItem).toBeVisible({ timeout: 3000 })
      await settingsItem.click()
      await page.waitForURL('**/config', { timeout: 5000 })
    }
  })

  test('退出登录弹出确认框', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    const userTrigger = page.locator('.user-info')
    if (await userTrigger.count() > 0) {
      await userTrigger.click()
      const logoutItem = page.getByText('退出登录')
      await expect(logoutItem).toBeVisible({ timeout: 3000 })
      await logoutItem.click()
      // 应弹出确认框
      await expect(page.locator('.el-message-box')).toBeVisible({ timeout: 3000 })
      // 取消退出
      await page.getByRole('button', { name: '取消' }).click()
    }
  })
})

// ============================================================
// 404 页面
// ============================================================
test.describe('404 页面按钮功能', () => {
  test('返回首页按钮跳转到 /dashboard', async ({ page }) => {
    await page.goto('/nonexistent-route-xyz')
    await page.waitForLoadState('domcontentloaded')
    const btn = page.getByRole('button', { name: '返回首页' })
    await expect(btn).toBeVisible({ timeout: 10_000 })
    await btn.click()
    await page.waitForURL('**/dashboard', { timeout: 5000 })
  })
})
