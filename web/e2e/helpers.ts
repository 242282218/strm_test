import { type Locator, type Page, expect } from '@playwright/test'

type Scope = Page | Locator

/**
 * 等待页面就绪：Element Plus 骨架屏和全局 loading 消失。
 */
export async function waitForPageReady(page: Page) {
  // 等待可能的 el-skeleton 消失
  const skeleton = page.locator('.el-skeleton')
  if (await skeleton.count() > 0) {
    await skeleton.first().waitFor({ state: 'hidden', timeout: 10_000 }).catch(() => {})
  }
  // 等待全局 loading 消失
  const loading = page.locator('.el-loading-mask')
  if (await loading.count() > 0) {
    await loading.first().waitFor({ state: 'hidden', timeout: 10_000 }).catch(() => {})
  }
}

/**
 * 导航到指定路由并等待页面就绪。
 */
export async function navigateAndWait(page: Page, path: string) {
  await page.goto(path)
  await page.waitForLoadState('domcontentloaded')
  await waitForPageReady(page)
}

/**
 * 返回主内容区域，避免命中壳层头部的重复标题或按钮。
 */
export function getMainContent(page: Page): Locator {
  return page.getByRole('main')
}

/**
 * 将查询收敛到当前页面内容根节点。
 */
export function getPageRoot(page: Page, selector: string): Locator {
  return getMainContent(page).locator(selector)
}

/**
 * 收集页面控制台错误。返回错误信息数组。
 * 用法：在测试开头调用，测试结束后检查是否有非预期错误。
 */
export function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      errors.push(msg.text())
    }
  })
  return errors
}

/**
 * 断言页面没有请求返回 5xx 状态码。
 */
export function collectApiErrors(page: Page): { url: string; status: number }[] {
  const errors: { url: string; status: number }[] = []
  page.on('response', (resp) => {
    if (resp.url().includes('/api/') && resp.status() >= 500) {
      errors.push({ url: resp.url(), status: resp.status() })
    }
  })
  return errors
}

/**
 * 断言 el-table 至少有 N 行数据（或为空状态）。
 */
export async function expectTableOrEmpty(scope: Scope, minRows = 0) {
  const table = scope.locator('.el-table')
  const empty = scope.locator('.el-empty, .empty-state')
  // 表格或空状态至少出现一个
  await expect(table.or(empty).first()).toBeVisible({ timeout: 10_000 })
  if (minRows > 0 && await table.count() > 0) {
    const rows = table.locator('.el-table__body-wrapper .el-table__row')
    await expect(rows).toHaveCount(minRows)
  }
}
