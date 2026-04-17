import { test, expect } from '@playwright/test'

test.describe('代理流契约', () => {
  test('无效 fileId 不应落成 500', async ({ request }) => {
    const resp = await request.get('/api/proxy/stream/test_nonexistent_id', {
      timeout: 10_000,
    })

    const body = (await resp.json()) as {
      code: number
      message: string
      detail: string | null
      error_code: string | null
    }

    expect(resp.status()).not.toBe(404)
    expect(resp.status()).toBe(502)
    expect(body.code).toBe(502)
    expect(body.message).toBe('上游服务异常')
    expect(body.detail).toBe('Failed to resolve stream URL')
    expect(body.error_code).toBe('ERR_BAD_GATEWAY')
  })
})
