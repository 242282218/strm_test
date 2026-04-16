/**
 * 错误处理工具
 * 提供类型安全的错误处理和消息提取
 */

import { ElMessage } from 'element-plus'
import { getErrorMessage } from './error-message'

export { getErrorMessage, isAxiosError } from './error-message'
export type { ApiErrorResponse, AxiosError } from './error-message'

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
