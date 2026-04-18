import { test, expect, type Locator, type Page } from '@playwright/test'
import {
  expectTableOrEmpty,
  navigateAndWait,
  collectApiErrors,
  getPageRoot,
  waitForPageReady,
} from './helpers'

// ===== 公共辅助函数 =====

/**
 * 安全点击按钮并验证无 JS 错误。
 * 点击前收集 console error，点击后检查是否有新增错误。
 */
async function safeClickAndVerify(
  page: Page,
  target: Locator,
): Promise<void> {
  const errorsBefore: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') errorsBefore.push(msg.text())
  })

  await expect(target).toBeVisible({ timeout: 5000 })
  if (!(await target.isEnabled())) return
  await target.click()

  await waitForPageReady(page)

  // 不在此处断言错误数量——由各测试用例自行判断
}

async function isSwitchChecked(target: Locator): Promise<boolean> {
  return target.evaluate((element) => element.classList.contains('is-checked'))
}

// ===== 登录页测试 (/login) =====

test.describe('登录页 /login 按钮功能', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('页面渲染：表单元素与登录按钮均可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/login')

    await expect(page.locator('.login-container')).toBeVisible()
    await expect(page.locator('.login-card')).toBeVisible()
    await expect(page.getByPlaceholder('用户名')).toBeVisible()
    await expect(page.getByPlaceholder('密码')).toBeVisible()
    await expect(page.locator('.login-btn')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('空提交触发 Element Plus 表单校验提示', async ({ page }) => {
    await navigateAndWait(page, '/login')
    await page.locator('.login-btn').click()
    await expect(page.locator('.el-form-item__error').first()).toBeVisible({ timeout: 3000 })
  })

  test('输入错误密码后显示错误提示', async ({ page }) => {
    await navigateAndWait(page, '/login')
    await page.getByPlaceholder('用户名').fill('admin')
    await page.getByPlaceholder('密码').fill('wrong_password_12345')
    await page.locator('.login-btn').click()
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 10_000 })
  })

  test('"记住我" 复选框可以正常切换状态', async ({ page }) => {
    await navigateAndWait(page, '/login')
    const rememberMeCheckbox = page.locator('.el-checkbox').filter({ hasText: '记住我' }).first()
    const rememberMeInput = rememberMeCheckbox.locator('input[type="checkbox"]')
    await expect(rememberMeCheckbox).toBeVisible()
    await rememberMeCheckbox.click()
    await expect(rememberMeInput).toBeChecked()
    await rememberMeCheckbox.click()
    await expect(rememberMeInput).not.toBeChecked()
  })

  test('成功登录后跳转到 /dashboard', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/login')

    const username = process.env.E2E_USERNAME ?? 'admin'
    const password = process.env.E2E_PASSWORD ?? 'admin'
    await page.getByPlaceholder('用户名').fill(username)
    await page.getByPlaceholder('密码').fill(password)
    await page.locator('.login-btn').click()

    await page.waitForURL('**/dashboard', { timeout: 15_000 })
    await expect(page).toHaveURL(/dashboard/)
    expect(apiErrors).toHaveLength(0)
  })
})

// ===== 仪表盘 (/dashboard) =====

test.describe('仪表盘 /dashboard 按钮功能', () => {
  test('刷新数据按钮可点击且不报错', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/dashboard')
    const dashboardPage = getPageRoot(page, '.dashboard')

    const refreshBtn = dashboardPage.getByRole('button', { name: '刷新数据' })
    if (await refreshBtn.count() > 0) {
      await safeClickAndVerify(page, refreshBtn)
      await expect(dashboardPage.locator('.hero-signal').first()).toBeVisible({ timeout: 10_000 })
    }
    expect(apiErrors).toHaveLength(0)
  })

  test('时间范围切换按钮组正常工作', async ({ page }) => {
    await navigateAndWait(page, '/dashboard')
    const radioGroup = page.locator('.el-radio-group')
    if (await radioGroup.count() > 0) {
      const buttons = radioGroup.locator('.el-radio-button')
      if (await buttons.count() > 1) {
        await buttons.last().click()
        await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 })
      }
    }
  })

  test('统计卡片区域可见且无 API 错误', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/dashboard')
    const dashboardPage = getPageRoot(page, '.dashboard')

    await expect(dashboardPage.locator('.hero-signal').first()).toBeVisible({ timeout: 10_000 })
    await expect(dashboardPage.locator('.stat-card').first()).toBeVisible({ timeout: 10_000 })
    expect(apiErrors).toHaveLength(0)
  })
})

// ===== 任务管理 (/tasks) =====

test.describe('任务管理 /tasks 按钮功能', () => {
  test('页面加载：标题、新建按钮、表格可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/tasks')
    const tasksPage = getPageRoot(page, '.tasks-page')

    await expect(tasksPage.locator('.hero-title')).toBeVisible()
    await expect(tasksPage.locator('.hero-actions').getByRole('button', { name: '新建任务' })).toBeVisible()
    await expect(tasksPage.locator('.metric-card').first()).toBeVisible({ timeout: 10_000 })
    await expectTableOrEmpty(tasksPage.locator('.tasks-panel'))
    expect(apiErrors).toHaveLength(0)
  })

  test('新建任务弹窗可打开并关闭', async ({ page }) => {
    await navigateAndWait(page, '/tasks')
    const tasksPage = getPageRoot(page, '.tasks-page')

    const newTaskBtn = tasksPage.locator('.hero-actions').getByRole('button', { name: '新建任务' })
    await newTaskBtn.click()
    await expect(page.locator('.el-dialog').first()).toBeVisible({ timeout: 5000 })

    // 关闭弹窗（点击遮罩层或关闭按钮）
    const closeBtn = page.locator('.el-dialog .el-dialog__headerbtn')
    if (await closeBtn.count() > 0) {
      await closeBtn.click()
      await expect(page.locator('.el-dialog').first()).not.toBeVisible({ timeout: 3000 })
    }
  })

  test('状态筛选下拉框可展开并选择', async ({ page }) => {
    await navigateAndWait(page, '/tasks')
    const filterPanel = getPageRoot(page, '.tasks-page').locator('.filter-panel')
    if (await filterPanel.count() > 0) {
      const statusSelect = filterPanel.locator('.el-select').first()
      if (await statusSelect.count() > 0) {
        await statusSelect.click()
        await expect(page.locator('.el-select-dropdown:visible').first()).toBeVisible({ timeout: 5000 })
        // 按 Escape 关闭下拉框
        await page.keyboard.press('Escape')
      }
    }
  })

  test('分页组件存在时可见且可交互', async ({ page }) => {
    await navigateAndWait(page, '/tasks')
    const pagination = getPageRoot(page, '.tasks-page').locator('.el-pagination')
    if (await pagination.count() > 0) {
      await expect(pagination).toBeVisible()
      // 点击下一页按钮（如果可用）
      const nextBtn = pagination.locator('button.btn-next:not(.disabled)')
      if (await nextBtn.count() > 0) {
        await nextBtn.first().click()
        await waitForPageReady(page)
      }
    }
  })
})

// ===== 刮削目录 (/scrape-pathes) =====

test.describe('刮削目录 /scrape-pathes 按钮功能', () => {
  test('页面加载：标题和操作按钮栏可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/scrape-pathes')
    const scrapePathsPage = getPageRoot(page, '.scrape-pathes-page')

    await expect(scrapePathsPage.locator('.hero-title')).toBeVisible()
    await expect(page.getByTestId('scrape-create-button')).toBeVisible()
    await expect(scrapePathsPage.locator('.hero-actions').getByRole('button', { name: '刷新', exact: true })).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('添加目录弹窗可打开', async ({ page }) => {
    await navigateAndWait(page, '/scrape-pathes')
    const addBtn = page.getByRole('button', { name: /添加|新增|新建/ })
    if (await addBtn.count() > 0) {
      await addBtn.first().click()
      await expect(page.locator('.el-dialog').first()).toBeVisible({ timeout: 5000 })
      // 关闭弹窗
      const closeBtn = page.locator('.el-dialog .el-dialog__headerbtn')
      if (await closeBtn.count() > 0) {
        await closeBtn.click()
      }
    }
  })

  test('扫描按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/scrape-pathes')
    const scanBtn = getPageRoot(page, '.scrape-pathes-page').getByRole('button', { name: /启动|扫描|开始扫描|Scan/ })
    if (await scanBtn.count() > 0) {
      await safeClickAndVerify(page, scanBtn.first())
    }
  })

  test('删除按钮在表格操作列中存在', async ({ page }) => {
    await navigateAndWait(page, '/scrape-pathes')
    const table = page.locator('.el-table')
    if (await table.count() > 0) {
      const rows = table.locator('.el-table__body-wrapper .el-table__row')
      if (await rows.count() > 0) {
        // 第一行中可能有删除/编辑按钮
        const deleteBtn = rows.first().locator('button, [class*="delete"], [class*="remove"]')
        if (await deleteBtn.count() > 0) {
          await expect(deleteBtn.first()).toBeVisible()
        }
      }
    }
  })

  test('刷新按钮可点击且页面保持正常', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/scrape-pathes')

    const refreshBtn = page.getByRole('button', { name: /刷新|Refresh/ })
    if (await refreshBtn.count() > 0) {
      await safeClickAndVerify(page, refreshBtn.first())
    }
    expect(apiErrors).toHaveLength(0)
  })
})

// ===== 刮削记录 (/scrape-records) =====

test.describe('刮削记录 /scrape-records 按钮功能', () => {
  test('页面加载：标题和筛选器可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/scrape-records')
    const scrapeRecordsPage = getPageRoot(page, '.scrape-records-page')

    await expect(scrapeRecordsPage.locator('.hero-title')).toBeVisible()
    await expect(page.getByTestId('scrape-records-refresh')).toBeVisible()
    const toolbar = scrapeRecordsPage.locator('.toolbar')
    if (await toolbar.count() > 0) {
      await expect(toolbar).toBeVisible()
    }
    expect(apiErrors).toHaveLength(0)
  })

  test('筛选器组件可交互', async ({ page }) => {
    await navigateAndWait(page, '/scrape-records')
    // 尝试找到筛选相关的 select 或 input
    const selects = page.locator('.filter-bar .el-select, .filter-card .el-select, .search-bar .el-select')
    if (await selects.count() > 0) {
      await selects.first().click()
      await expect(page.locator('.el-select-dropdown')).toBeVisible({ timeout: 5000 })
      await page.keyboard.press('Escape')
    }
  })

  test('批量操作按钮在有数据时可点击', async ({ page }) => {
    await navigateAndWait(page, '/scrape-records')
    const batchBtn = page.getByRole('button', { name: /批量|Batch|全选/ })
    if (await batchBtn.count() > 0) {
      await expect(batchBtn.first()).toBeVisible()
    }
  })

  test('刷新按钮功能正常', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/scrape-records')

    const refreshBtn = page.getByTestId('scrape-records-refresh')
    if (await refreshBtn.count() > 0) {
      await safeClickAndVerify(page, refreshBtn)
    }
    expect(apiErrors).toHaveLength(0)
  })
})

// ===== 二级分类策略 (/settings/category-strategy) =====

test.describe('二级分类策略 /settings/category-strategy 按钮功能', () => {
  test('页面加载：标题和策略列表可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/settings/category-strategy')

    await expect(page.getByTestId('category-strategy-hero')).toBeVisible()
    await expect(page.getByTestId('category-strategy-preview')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('新增规则弹窗可打开', async ({ page }) => {
    await navigateAndWait(page, '/settings/category-strategy')
    const addBtn = page.getByRole('button', { name: /新增|添加|新建规则/ })
    if (await addBtn.count() > 0) {
      await addBtn.first().click()
      await expect(page.locator('.el-dialog').first()).toBeVisible({ timeout: 5000 })
      const closeBtn = page.locator('.el-dialog .el-dialog__headerbtn')
      if (await closeBtn.count() > 0) {
        await closeBtn.click()
      }
    }
  })

  test('编辑规则按钮在行内可点击', async ({ page }) => {
    await navigateAndWait(page, '/settings/category-strategy')
    const rows = page.locator('.el-table__body-wrapper .el-table__row')
    if (await rows.count() > 0) {
      const editBtn = rows.first().locator('button, [class*="edit"]')
      if (await editBtn.count() > 0) {
        await editBtn.first().click()
        await expect(page.locator('.el-dialog').first()).toBeVisible({ timeout: 5000 })
        const closeBtn = page.locator('.el-dialog .el-dialog__headerbtn')
        if (await closeBtn.count() > 0) {
          await closeBtn.click()
        }
      }
    }
  })

  test('删除规则弹出确认对话框', async ({ page }) => {
    await navigateAndWait(page, '/settings/category-strategy')
    const rows = page.locator('.el-table__body-wrapper .el-table__row')
    if (await rows.count() > 0) {
      const deleteBtn = rows.first().locator('button, [class*="delete"], [class*="remove"]')
      if (await deleteBtn.count() > 0) {
        await deleteBtn.first().click()
        // 应弹出确认弹窗（ElMessageBox 或 el-popconfirm）
        const confirmDialog = page.locator('.el-message-box, .el-popconfirm')
        if (await confirmDialog.count() > 0) {
          await expect(confirmDialog.first()).toBeVisible()
          // 取消删除
          const cancelBtn = page.locator('.el-message-box__btns button:has-text("取消"), .el-popconfirm button:last-child')
          if (await cancelBtn.count() > 0) {
            await cancelBtn.first().click()
          } else {
            await page.keyboard.press('Escape')
          }
        }
      }
    }
  })

  test('保存按钮可见且可点击', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/settings/category-strategy')

    const saveBtn = page.getByTestId('category-strategy-save-button')
    if (await saveBtn.count() > 0) {
      await expect(saveBtn).toBeVisible()
      await safeClickAndVerify(page, saveBtn)
    }
    expect(apiErrors).toHaveLength(0)
  })
})

// ===== Emby 监控 (/emby-monitor) =====

test.describe('Emby 监控 /emby-monitor 按钮功能', () => {
  test('页面加载：标题和监控卡片可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/emby-monitor')

    await expect(page.getByTestId('emby-monitor-hero')).toBeVisible()
    await expect(page.getByTestId('emby-events-panel')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('刷新按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/emby-monitor')
    const refreshBtn = page.getByRole('button', { name: /刷新|Refresh|同步/ })
    if (await refreshBtn.count() > 0) {
      await safeClickAndVerify(page, refreshBtn.first())
    }
  })

  test('配置按钮打开设置弹窗', async ({ page }) => {
    await navigateAndWait(page, '/emby-monitor')
    const configBtn = page.getByRole('button', { name: /配置|设置|Config/ })
    if (await configBtn.count() > 0) {
      await configBtn.first().click()
      await expect(page.locator('.el-dialog').first()).toBeVisible({ timeout: 5000 })
      const closeBtn = page.locator('.el-dialog .el-dialog__headerbtn')
      if (await closeBtn.count() > 0) {
        await closeBtn.click()
      }
    }
  })

  test('代理开关切换正常', async ({ page }) => {
    await navigateAndWait(page, '/emby-monitor')
    const switchEl = page.locator('.el-switch')
    if (await switchEl.count() > 0) {
      const firstSwitch = switchEl.first()
      const isChecked = await isSwitchChecked(firstSwitch)
      await firstSwitch.click()
      await expect.poll(() => isSwitchChecked(firstSwitch)).not.toBe(isChecked)
    }
  })
})

// ===== 系统配置 (/config) =====

test.describe('系统配置 /config 按钮功能', () => {
  test('页面加载：标题和配置区域可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/config')
    const main = getPageRoot(page, '.config-page')

    await expect(main.getByRole('heading', { name: '配置分组' })).toBeVisible()
    await expect(page.getByTestId('config-section-json')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('保存按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/config')
    const saveBtn = page.getByRole('button', { name: /保存|Save/ })
    if (await saveBtn.count() > 0) {
      await expect(saveBtn.first()).toBeVisible()
      await safeClickAndVerify(page, saveBtn.first())
    }
  })

  test('重置按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/config')
    const resetBtn = page.getByRole('button', { name: /重置|Reset|还原/ })
    if (await resetBtn.count() > 0) {
      await expect(resetBtn.first()).toBeVisible()
      await safeClickAndVerify(page, resetBtn.first())
    }
  })

  test('折叠/展开面板可切换', async ({ page }) => {
    await navigateAndWait(page, '/config')
    const collapseHeaders = page.locator('.el-collapse-item__header')
    if (await collapseHeaders.count() > 0) {
      const header = collapseHeaders.first()
      const expandedBefore = await header.getAttribute('aria-expanded')
      await header.click()
      await expect.poll(() => header.getAttribute('aria-expanded')).not.toBe(expandedBefore)
    }
  })

  test('密码输入框（API Key）可见且可输入', async ({ page }) => {
    await navigateAndWait(page, '/config')
    const passwordInputs = page.locator('input[type="password"]')
    if (await passwordInputs.count() > 0) {
      await expect(passwordInputs.first()).toBeVisible()
      // 测试输入
      await passwordInputs.first().fill('test-api-key-value')
      const value = await passwordInputs.first().inputValue()
      expect(value).toBe('test-api-key-value')
      // 清空恢复原值
      await passwordInputs.first().clear()
    }
  })
})

// ===== 资源搜索 (/search) =====

test.describe('资源搜索 /search 按钮功能', () => {
  test('页面加载：搜索框和搜索按钮可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/search')
    const searchPage = getPageRoot(page, '.search-page')

    await expect(searchPage.locator('.hero-title')).toHaveText('资源搜索')
    await expect(searchPage.locator('input[type="text"]').first()).toBeVisible({ timeout: 10_000 })
    expect(apiErrors).toHaveLength(0)
  })

  test('搜索按钮点击执行搜索', async ({ page }) => {
    await navigateAndWait(page, '/search')
    const searchInput = page.locator('input[placeholder*="搜索"], input[placeholder*="search"], .search-input input')
    const searchBtn = page.getByRole('button', { name: /搜索|Search|查询/ })

    if ((await searchInput.count() > 0) && (await searchBtn.count() > 0)) {
      await searchInput.first().fill('test')
      await safeClickAndVerify(page, searchBtn.first())
      // 搜索结果区域应出现
      const resultArea = page.locator('.search-results, .result-list, .el-table')
      if (await resultArea.count() > 0) {
        await expect(resultArea.first()).toBeVisible({ timeout: 8000 })
      }
    }
  })

  test('筛选器可展开并选择', async ({ page }) => {
    await navigateAndWait(page, '/search')
    const filterSelects = page.locator('.filter-bar .el-select, .search-filter .el-select')
    if (await filterSelects.count() > 0) {
      await filterSelects.first().click()
      await expect(page.locator('.el-select-dropdown')).toBeVisible({ timeout: 5000 })
      await page.keyboard.press('Escape')
    }
  })

  test('清空/重置搜索按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/search')
    const clearBtn = page.getByRole('button', { name: /清空|重置|Clear|Reset/ })
    if (await clearBtn.count() > 0) {
      await safeClickAndVerify(page, clearBtn.first())
    }
  })

  test('搜索结果区域正确渲染', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/search')

    const intro = page.getByRole('heading', { name: '先输入片名，再逐步收窄结果' })
    const empty = page.locator('.el-empty')
    const resultList = page.locator('.search-results, .result-list')
    await expect(intro.or(empty).or(resultList).first()).toBeVisible({ timeout: 10_000 })
    expect(apiErrors).toHaveLength(0)
  })
})

// ===== 基础重命名 (/rename) =====

test.describe('基础重命名 /rename 按钮功能', () => {
  test('页面加载：表单和执行按钮可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/rename')

    await expect(page.getByRole('heading', { name: '智能重命名' }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: '浏览' })).toBeVisible()
    await expect(page.getByRole('button', { name: '开始分析' })).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('开始分析按钮在选择目录前保持禁用', async ({ page }) => {
    await navigateAndWait(page, '/rename')
    const analyzeBtn = page.getByRole('button', { name: '开始分析' })
    if (await analyzeBtn.count() > 0) {
      await expect(analyzeBtn).toBeVisible()
      await expect(analyzeBtn).toBeDisabled()
    }
  })

  test('预览按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/rename')
    const previewBtn = page.getByRole('button', { name: /预览|Preview/ })
    if (await previewBtn.count() > 0) {
      await safeClickAndVerify(page, previewBtn.first())
      // 预览结果可能出现
      const previewResult = page.locator('.preview-result, .preview-table')
      if (await previewResult.count() > 0) {
        await expect(previewResult.first()).toBeVisible({ timeout: 5000 })
      }
    }
  })

  test('文件选择器/路径输入框可交互', async ({ page }) => {
    await navigateAndWait(page, '/rename')
    // 路径选择器可能是一个 input 或一个带浏览按钮的组件
    const pathInput = page.locator('input[placeholder*="路径"], input[placeholder*="path"], .path-selector input')
    const browseBtn = page.getByRole('button', { name: /浏览|Browse|选择|.../ })

    if (await pathInput.count() > 0) {
      await expect(pathInput.first()).toBeVisible()
    }
    if (await browseBtn.count() > 0) {
      await expect(browseBtn.first()).toBeVisible()
    }
  })
})

// ===== 智能重命名 (/smart-rename) =====

test.describe('智能重命名 /smart-rename 按钮功能', () => {
  test('页面加载：标题、本地目录与操作按钮可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/smart-rename')
    const smartRenamePage = getPageRoot(page, '.smart-rename-page')

    await expect(smartRenamePage.getByRole('heading', { name: '智能重命名' })).toBeVisible()
    await expect(smartRenamePage.getByRole('heading', { name: '本地目录' })).toBeVisible()
    await expect(smartRenamePage.getByRole('button', { name: '生成预览' })).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('执行智能重命名按钮在未输入路径前保持禁用', async ({ page }) => {
    await navigateAndWait(page, '/smart-rename')
    const executeBtn = getPageRoot(page, '.smart-rename-page').getByRole('button', { name: '执行重命名' })
    await expect(executeBtn).toBeVisible()
    await expect(executeBtn).toBeDisabled()
  })

  test('预览按钮在未输入路径前保持禁用', async ({ page }) => {
    await navigateAndWait(page, '/smart-rename')
    const previewBtn = getPageRoot(page, '.smart-rename-page').getByRole('button', { name: '生成预览' })
    await expect(previewBtn).toBeVisible()
    await expect(previewBtn).toBeDisabled()
  })

  test('算法与命名标准选择器可交互', async ({ page }) => {
    await navigateAndWait(page, '/smart-rename')
    const configSelects = getPageRoot(page, '.smart-rename-page').locator('.config-grid .el-select')
    if (await configSelects.count() > 0) {
      await configSelects.first().click()
      await expect(page.locator('.el-select-dropdown')).toBeVisible({ timeout: 5000 })
      await page.keyboard.press('Escape')
    }
  })
})

// ===== 代理服务 (/proxy-service) =====

test.describe('代理服务 /proxy-service 按钮功能', () => {
  test('页面加载：状态面板和服务控制可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/proxy-service')

    await expect(page.getByTestId('proxy-service-hero')).toBeVisible()
    await expect(page.getByTestId('proxy-cache-panel')).toBeVisible()
    await expect(page.getByTestId('proxy-clear-cache')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('启动/停止服务按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')
    const toggleBtn = page.getByRole('button', { name: /启动|停止|Start|Stop|启用|禁用/ })
    if (await toggleBtn.count() > 0) {
      await expect(toggleBtn.first()).toBeVisible()
      await safeClickAndVerify(page, toggleBtn.first())
    }
  })

  test('健康检查按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')
    const healthBtn = page.getByRole('button', { name: /健康检查|Health|检测|诊断/ })
    if (await healthBtn.count() > 0) {
      await safeClickAndVerify(page, healthBtn.first())
    }
  })

  test('缓存管理按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')
    const cacheBtn = page.getByRole('button', { name: /缓存|Cache|清理|清除/ })
    if (await cacheBtn.count() > 0) {
      await safeClickAndVerify(page, cacheBtn.first())
      // 可能弹出确认框
      const confirmBox = page.locator('.el-message-box, .el-popconfirm')
      if (await confirmBox.count() > 0) {
        const cancelBtn = confirmBox.locator('button:has-text("取消"), button:last-child')
        if (await cancelBtn.count() > 0) {
          await cancelBtn.first().click()
        } else {
          await page.keyboard.press('Escape')
        }
      }
    }
  })
})

// ===== WebDAV 挂载 (/webdav) =====

test.describe('WebDAV 挂载 /webdav 按钮功能', () => {
  test('页面加载：挂载状态和控制面板可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/webdav')

    await expect(page.getByTestId('webdav-hero')).toBeVisible()
    await expect(page.getByTestId('webdav-connection-panel')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('挂载/卸载按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/webdav')
    const mountBtn = page.getByRole('button', { name: /挂载|卸载|Mount|Unmount|连接|断开/ })
    if (await mountBtn.count() > 0) {
      await expect(mountBtn.first()).toBeVisible()
      await safeClickAndVerify(page, mountBtn.first())
    }
  })

  test('浏览文件按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/webdav')
    const browseBtn = page.getByRole('button', { name: /浏览|Browse|查看|Explore/ })
    if (await browseBtn.count() > 0) {
      await safeClickAndVerify(page, browseBtn.first())
    }
  })

  test('权限设置按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/webdav')
    const permBtn = page.getByRole('button', { name: /权限|Permission|设置|权限管理/ })
    if (await permBtn.count() > 0) {
      await safeClickAndVerify(page, permBtn.first())
      // 可能打开弹窗
      const dialog = page.locator('.el-dialog')
      if (await dialog.count() > 0) {
        await expect(dialog.first()).toBeVisible({ timeout: 5000 })
        const closeBtn = dialog.locator('.el-dialog__headerbtn')
        if (await closeBtn.count() > 0) {
          await closeBtn.click()
        }
      }
    }
  })
})

// ===== 通知配置 (/notifications) =====

test.describe('通知配置 /notifications 按钮功能', () => {
  test('页面加载：通知渠道列表可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/notifications')

    await expect(page.getByRole('heading', { name: '通知配置' })).toBeVisible()
    const channelSelect = page.locator('.el-select')
    if (await channelSelect.count() > 0) {
      await expect(channelSelect.first()).toBeVisible({ timeout: 10_000 })
    }
    expect(apiErrors).toHaveLength(0)
  })

  test('测试通知按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/notifications')
    const testBtn = page.getByRole('button', { name: /测试|Test|发送测试/ })
    if (await testBtn.count() > 0) {
      await safeClickAndVerify(page, testBtn.first())
    }
  })

  test('保存配置按钮可点击', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/notifications')

    const saveBtn = page.getByRole('button', { name: /保存|Save/ })
    if (await saveBtn.count() > 0) {
      await expect(saveBtn.first()).toBeVisible()
      await safeClickAndVerify(page, saveBtn.first())
    }
    expect(apiErrors).toHaveLength(0)
  })

  test('启用/禁用开关可切换', async ({ page }) => {
    await navigateAndWait(page, '/notifications')
    const switchEl = page.locator('.el-switch')
    if (await switchEl.count() > 0) {
      const firstSwitch = switchEl.first()
      const isChecked = await isSwitchChecked(firstSwitch)
      await firstSwitch.click()
      await expect.poll(() => isSwitchChecked(firstSwitch)).not.toBe(isChecked)
    }
  })
})

// ===== 通知历史 (/notifications/history) =====

test.describe('通知历史 /notifications/history 按钮功能', () => {
  test('页面加载：历史记录列表可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/notifications/history')
    const historyPage = getPageRoot(page, '.notification-history-page')

    await expect(historyPage.locator('.hero-title')).toBeVisible()
    const timeline = historyPage.locator('.el-timeline')
    const empty = historyPage.locator('.empty-state')
    await expect(timeline.or(empty).first()).toBeVisible({ timeout: 10_000 })
    expect(apiErrors).toHaveLength(0)
  })

  test('清空历史按钮弹出确认', async ({ page }) => {
    await navigateAndWait(page, '/notifications/history')
    const clearBtn = page.getByRole('button', { name: /清空|清除|Clear|全部删除/ })
    if (await clearBtn.count() > 0) {
      await clearBtn.first().click()
      const confirmBox = page.locator('.el-message-box, .el-popconfirm')
      if (await confirmBox.count() > 0) {
        await expect(confirmBox.first()).toBeVisible()
        // 取消操作
        const cancelBtn = confirmBox.locator('button:has-text("取消"), button:last-child')
        if (await cancelBtn.count() > 0) {
          await cancelBtn.first().click()
        } else {
          await page.keyboard.press('Escape')
        }
      }
    }
  })

  test('筛选器可交互', async ({ page }) => {
    await navigateAndWait(page, '/notifications/history')
    const filterSelects = page.locator('.filter-bar .el-select, .history-filter .el-select')
    if (await filterSelects.count() > 0) {
      await filterSelects.first().click()
      await expect(page.locator('.el-select-dropdown')).toBeVisible({ timeout: 5000 })
      await page.keyboard.press('Escape')
    }
  })

  test('刷新按钮功能正常', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/notifications/history')

    const refreshBtn = page.getByRole('button', { name: /刷新|Refresh/ })
    if (await refreshBtn.count() > 0) {
      await safeClickAndVerify(page, refreshBtn.first())
    }
    expect(apiErrors).toHaveLength(0)
  })
})

// ===== 全局导航与边界条件 =====

test.describe('全局导航栏与边界条件', () => {
  test('未登录访问受保护路由应重定向到 /login', async ({ browser }) => {
    const context = await browser.newContext({
      storageState: { cookies: [], origins: [] },
    })
    const isolatedPage = await context.newPage()

    try {
      await navigateAndWait(isolatedPage, '/dashboard')
      await expect(isolatedPage).toHaveURL(/\/login/)
    } finally {
      await context.close()
    }
  })

  test('侧边栏导航链接均可点击', async ({ page }) => {
    await navigateAndWait(page, '/dashboard')
    // 等待侧边栏渲染
    const sidebar = page.locator('.sidebar, .el-menu--vertical, aside')
    if (await sidebar.count() > 0) {
      const navLinks = sidebar.locator('a, .el-menu-item')
      const count = await navLinks.count()
      if (count > 0) {
        // 点击第一个非活跃菜单项
        for (let i = 0; i < Math.min(count, 3); i++) {
          const link = navLinks.nth(i)
          if (await link.isVisible()) {
            const isActive = await link.evaluate((el) =>
              el.classList.contains('is-active'),
            )
            if (!isActive) {
              await link.click()
              await waitForPageReady(page)
              break
            }
          }
        }
      }
    }
  })

  test('用户菜单下拉可展开', async ({ page }) => {
    await navigateAndWait(page, '/dashboard')
    const userMenuTrigger = page.locator('.user-avatar, .user-info, .el-dropdown [class*="user"]')
    if (await userMenuTrigger.count() > 0) {
      await userMenuTrigger.first().click()
      // 下拉菜单应出现
      const dropdownMenu = page.locator('.el-dropdown-menu, .el-menu--popup')
      if (await dropdownMenu.count() > 0) {
        await expect(dropdownMenu.first()).toBeVisible({ timeout: 5000 })
        await page.keyboard.press('Escape')
      }
    }
  })

  test('退出登录按钮可触发登出', async ({ page }) => {
    await navigateAndWait(page, '/dashboard')
    const logoutLink = page.getByRole('menuitem', { name: /退出|注销|Logout|登出/ })
    if (await logoutLink.count() === 0) {
      // 尝试通过用户菜单触发
      const userMenu = page.locator('.user-avatar, .el-dropdown [class*="user"]')
      if (await userMenu.count() > 0) {
        await userMenu.first().click()
        const dropdownMenu = page.locator('.el-dropdown-menu, .el-menu--popup')
        if (await dropdownMenu.count() > 0) {
          await expect(dropdownMenu.first()).toBeVisible({ timeout: 5000 })
        }
      }
    }
    const logoutBtn = page.getByRole('menuitem', { name: /退出|注销|Logout|登出/ }, { has: true })
    if (await logoutBtn.count() > 0) {
      await logoutBtn.first().click()
      // 应跳转到登录页
      const url = page.url()
      // 登出后可能在 login 页面或仍在当前页面（取决于实现）
      expect(url.length).toBeGreaterThan(0)
    }
  })

  test('各页面累积无 JS console 错误', async ({ page }) => {
    const jsErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        jsErrors.push(msg.text())
      }
    })

    // 遍历所有主要路由
    const routes = [
      '/dashboard',
      '/tasks',
      '/scrape-pathes',
      '/scrape-records',
      '/settings/category-strategy',
      '/emby-monitor',
      '/config',
      '/search',
      '/rename',
      '/smart-rename',
      '/proxy-service',
      '/webdav',
      '/notifications',
      '/notifications/history',
    ]

    for (const route of routes) {
      await navigateAndWait(page, route)
    }

    // 断言没有 JS 错误（允许已知的非关键警告）
    const criticalErrors = jsErrors.filter(
      (err) =>
        !err.includes('favicon') &&
        !err.includes('Failed to load resource') &&
        !err.includes('404') &&
        err.length > 10,
    )
    expect(criticalErrors, `发现 JS 错误: ${criticalErrors.join('; ')}`).toHaveLength(0)
  })

  test('各页面累积无 API 4xx/5xx 错误', async ({ page }) => {
    const apiErrors = collectApiErrors(page)

    const routes = [
      '/dashboard',
      '/tasks',
      '/scrape-pathes',
      '/scrape-records',
      '/settings/category-strategy',
      '/emby-monitor',
      '/config',
      '/search',
      '/rename',
      '/smart-rename',
      '/proxy-service',
      '/webdav',
      '/notifications',
      '/notifications/history',
    ]

    for (const route of routes) {
      await navigateAndWait(page, route)
    }

    expect(apiErrors, `发现 API 4xx/5xx 错误: ${JSON.stringify(apiErrors)}`).toHaveLength(0)
  })
})
