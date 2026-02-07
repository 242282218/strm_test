/**
 * 错误处理工具
 * 提供类型安全的错误处理和消息提取
 */

import { ElMessage } from 'element-plus'

/**
 * API 错误响应结构
 */
export interface ApiErrorResponse {
  detail?: string
  message?: string
  code?: string
}

/**
 * Axios 错误结构
 */
export interface AxiosError {
  response?: {
    data?: ApiErrorResponse
    status?: number
    statusText?: string
  }
  message?: string
  code?: string
}

/**
 * 检查值是否为 Axios 错误
 */
export function isAxiosError(error: unknown): error is AxiosError {
  if (!error || typeof error !== 'object') return false
  const e = error as Record<string, unknown>
  return 'response' in e || 'message' in e
}

/**
 * 从错误中提取用户友好的消息
 */
export function getErrorMessage(error: unknown, defaultMessage: string = '操作失败'): string {
  // 如果是 Axios 错误
  if (isAxiosError(error)) {
    // 优先使用服务器返回的错误详情
    const serverDetail = error.response?.data?.detail
    if (serverDetail) return serverDetail

    // 其次使用服务器返回的消息
    const serverMessage = error.response?.data?.message
    if (serverMessage) return serverMessage

    // 使用 HTTP 状态信息
    if (error.response?.status) {
      const status = error.response.status
      const statusText = error.response.statusText || ''
      return `请求失败 (${status}${statusText ? ': ' + statusText : ''})`
    }

    // 使用错误消息
    if (error.message) return error.message
  }

  // 如果是普通 Error
  if (error instanceof Error) {
    return error.message
  }

  // 如果是字符串
  if (typeof error === 'string') {
    return error
  }

  // 返回默认消息
  return defaultMessage
}

/**
 * 显示错误消息
 */
export function showError(error: unknown, defaultMessage: string = '操作失败'): void {
  const message = getErrorMessage(error, defaultMessage)
  ElMessage.error(message)
}

/**
 * 显示成功消息
 */
export function showSuccess(message: string): void {
  ElMessage.success(message)
}

/**
 * 显示警告消息
 */
export function showWarning(message: string): void {
  ElMessage.warning(message)
}

/**
 * 显示信息消息
 */
export function showInfo(message: string): void {
  ElMessage.info(message)
}

/**
 * 包装异步函数，自动处理错误
 */
export function withErrorHandling<T extends (...args: unknown[]) => Promise<unknown>>(
  fn: T,
  options: {
    defaultMessage?: string
    showError?: boolean
    onError?: (error: unknown) => void
  } = {}
): (...args: Parameters<T>) => Promise<ReturnType<T> | undefined> {
  const { defaultMessage = '操作失败', showError: shouldShowError = true, onError } = options

  return async (...args: Parameters<T>): Promise<ReturnType<T> | undefined> => {
    try {
      return await fn(...args) as ReturnType<T>
    } catch (error) {
      if (shouldShowError) {
        showError(error, defaultMessage)
      }
      if (onError) {
        onError(error)
      }
      return undefined
    }
  }
}

/**
 * 创建 API 调用包装器
 */
export function createApiWrapper<T extends (...args: unknown[]) => Promise<unknown>>(
  fn: T,
  defaultMessage: string
): (...args: Parameters<T>) => Promise<ReturnType<T> | undefined> {
  return withErrorHandling(fn, {
    defaultMessage,
    showError: true
  })
}
