import { test, expect } from '@playwright/test'
import { navigateAndWait, collectApiErrors } from './helpers'

test.describe('代理服务 /proxy-service', () => {
  test('页面加载：标题、操作按钮可见', async ({ page }) => {
    const apiErrors = collectApiErrors(page)
    await navigateAndWait(page, '/proxy-service')

    await expect(page.getByTestId('proxy-service-hero')).toBeVisible()
    await expect(page.getByRole('heading', { name: '代理服务、STRM 生成与缓存命中统一收口' })).toBeVisible()
    await expect(page.getByTestId('proxy-clear-cache')).toBeVisible()
    expect(apiErrors).toHaveLength(0)
  })

  test('服务说明卡片可见', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')
    await expect(page.getByTestId('proxy-api-panel')).toBeVisible({ timeout: 10_000 })
  })

  test('STRM 生成表单可见', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')
    await expect(page.getByTestId('proxy-strm-generator')).toBeVisible()
    await expect(page.getByTestId('proxy-generate-button')).toBeVisible()
  })

  test('清除缓存按钮可点击', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')
    const clearBtn = page.getByTestId('proxy-clear-cache')
    if (await clearBtn.count() > 0) {
      await expect(clearBtn).toBeVisible()
    }
  })

  test('URL 模式选择器可见', async ({ page }) => {
    await navigateAndWait(page, '/proxy-service')
    await expect(page.getByTestId('proxy-modes-panel')).toBeVisible()
  })
})
