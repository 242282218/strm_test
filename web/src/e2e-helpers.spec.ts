// @vitest-environment node
import type { Page } from '@playwright/test'
import { describe, expect, it } from 'vitest'

import { collectApiErrors } from '../e2e/helpers'

type ResponseListener = (response: { url(): string; status(): number }) => void

function createPageHarness(): {
  emitResponse: (url: string, status: number) => void
  page: Page
} {
  let responseListener: ResponseListener | null = null

  const page = {
    on(event: string, listener: ResponseListener) {
      if (event === 'response') {
        responseListener = listener
      }
    },
  } as Page

  return {
    page,
    emitResponse(url: string, status: number) {
      responseListener?.({
        status: () => status,
        url: () => url,
      })
    },
  }
}

describe('collectApiErrors', () => {
  it('collects 4xx and 5xx API responses but ignores non-api traffic', () => {
    const harness = createPageHarness()
    const errors = collectApiErrors(harness.page)

    harness.emitResponse('http://127.0.0.1:18000/api/search?q=demo', 404)
    harness.emitResponse('http://127.0.0.1:18000/api/tasks', 500)
    harness.emitResponse('http://127.0.0.1:18000/assets/logo.svg', 404)
    harness.emitResponse('http://127.0.0.1:18000/api/dashboard/stats', 200)

    expect(errors).toEqual([
      { url: 'http://127.0.0.1:18000/api/search?q=demo', status: 404 },
      { url: 'http://127.0.0.1:18000/api/tasks', status: 500 },
    ])
  })

  it('skips allowlisted statuses for expected API responses', () => {
    const harness = createPageHarness()
    const errors = collectApiErrors(harness.page, { allowStatuses: [404] })

    harness.emitResponse('http://127.0.0.1:18000/api/search?q=demo', 404)
    harness.emitResponse('http://127.0.0.1:18000/api/tasks', 409)

    expect(errors).toEqual([
      { url: 'http://127.0.0.1:18000/api/tasks', status: 409 },
    ])
  })
})
