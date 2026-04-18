import { test, expect } from '@playwright/test'
import { collectApiErrors, navigateAndWait } from './helpers'

const createSearchPayload = (results: Array<Record<string, unknown>>) => ({
  results,
  total: results.length,
  page: 1,
  page_size: 20,
  has_more: false,
})

const isSearchApiRequest = (url: string) => {
  const parsed = new URL(url)
  return parsed.pathname === '/api/search'
}

test.describe('资源搜索 /search', () => {
  test('页面加载：搜索框和初始指引可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)

    await navigateAndWait(page, '/search')

    const searchInput = page.locator('.search-page .search-input')

    await expect(searchInput).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('开始一次搜索')).toBeVisible()
    await expect(page.getByText('先输入片名，再逐步收窄结果')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('输入关键词后会请求 /api/search 并渲染结果', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    const requestUrls: string[] = []

    await page.route(isSearchApiRequest, async route => {
      requestUrls.push(route.request().url())
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          createSearchPayload([
            {
              id: 'result-1',
              title: '三体 第1季',
              content: '夸克资源已收录',
              source: 'telegram',
              channel: '影视资源',
              pub_date: '2026-04-18T08:00:00Z',
              cloud_links: [
                {
                  type: 'quark',
                  url: 'https://pan.quark.cn/s/demo',
                  password: '1234',
                },
              ],
              score: 92,
            },
          ]),
        ),
      })
    })

    await navigateAndWait(page, '/search')

    const searchInput = page.locator('.search-page .search-input')
    const responsePromise = page.waitForResponse(response =>
      response.request().method() === 'GET' && isSearchApiRequest(response.url()),
    )

    await expect(searchInput).toBeVisible({ timeout: 10_000 })
    await searchInput.fill('三体')
    await searchInput.press('Enter')

    expect((await responsePromise).status()).toBe(200)
    expect(requestUrls).toHaveLength(1)
    expect(new URL(requestUrls[0] ?? '').searchParams.get('keyword')).toBe('三体')
    await expect(page.getByText('找到 1 个结果')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('三体 第1季')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('空结果时展示空状态而不是静默等待', async ({ page }) => {
    const apiErrors = collectApiErrors(page)

    await page.route(isSearchApiRequest, async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(createSearchPayload([])),
      })
    })

    await navigateAndWait(page, '/search')

    const searchInput = page.locator('.search-page .search-input')

    await expect(searchInput).toBeVisible({ timeout: 10_000 })
    await searchInput.fill('不存在的资源')
    await searchInput.press('Enter')

    await expect(page.getByText('暂无匹配结果')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('试试更具体的片名')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })
})
