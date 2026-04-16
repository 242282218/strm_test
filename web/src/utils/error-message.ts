/**
 * Pure error parsing helpers shared by stores and views.
 */

export interface ApiErrorResponse {
  detail?: string
  message?: string
  code?: string
}

export interface AxiosError {
  response?: {
    data?: ApiErrorResponse
    status?: number
    statusText?: string
  }
  message?: string
  code?: string
}

export function isAxiosError(error: unknown): error is AxiosError {
  if (!error || typeof error !== 'object') return false
  const value = error as Record<string, unknown>
  return 'response' in value || 'message' in value
}

export function getErrorMessage(error: unknown, defaultMessage: string = '操作失败'): string {
  if (isAxiosError(error)) {
    const serverDetail = error.response?.data?.detail
    if (serverDetail) return serverDetail

    const serverMessage = error.response?.data?.message
    if (serverMessage) return serverMessage

    if (error.response?.status) {
      const status = error.response.status
      const statusText = error.response.statusText || ''
      return `请求失败 (${status}${statusText ? ': ' + statusText : ''})`
    }

    if (error.message) return error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  if (typeof error === 'string') {
    return error
  }

  return defaultMessage
}
