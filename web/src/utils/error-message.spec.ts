import { describe, expect, it } from 'vitest'

import { getErrorMessage, isAxiosError } from './error-message'

describe('error-message helpers', () => {
  it('prefers backend detail for axios-like errors', () => {
    expect(
      getErrorMessage({
        response: {
          data: {
            detail: 'backend detail',
            message: 'backend message',
          },
        },
      })
    ).toBe('backend detail')
  })

  it('falls back to backend message and status text when detail is missing', () => {
    expect(
      getErrorMessage({
        response: {
          data: {
            message: 'backend message',
          },
        },
      })
    ).toBe('backend message')

    expect(
      getErrorMessage({
        response: {
          status: 503,
          statusText: 'Service Unavailable',
        },
      })
    ).toBe('请求失败 (503: Service Unavailable)')
  })

  it('handles native errors, string values, and default fallback', () => {
    expect(getErrorMessage(new Error('native failure'))).toBe('native failure')
    expect(getErrorMessage('string failure')).toBe('string failure')
    expect(getErrorMessage(null, 'fallback message')).toBe('fallback message')
  })

  it('detects axios-like errors by response or message fields', () => {
    expect(isAxiosError({ response: {} })).toBe(true)
    expect(isAxiosError({ message: 'network failure' })).toBe(true)
    expect(isAxiosError({ code: 'E_FAIL' })).toBe(false)
    expect(isAxiosError(null)).toBe(false)
  })
})
