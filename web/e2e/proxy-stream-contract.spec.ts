import { test, expect } from '@playwright/test'

test.describe('代理流契约', () => {
  test('无效 fileId 不应落成 500', async ({ request }) => {
    const resp = await request.get('/api/proxy/stream/test_nonexistent_id', {
      timeout: 10_000,
    })

    const body = await resp.text()

    expect(resp.status()).not.toBe(404)
    expect(resp.status()).toBe(502)
    console.log(`Proxy stream contract: ${resp.status()} - ${body.substring(0, 100)}`)
  })
})
