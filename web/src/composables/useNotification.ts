/**
 * useNotification - 通知封装 Composable
 *
 * 封装 Element Plus 的消息通知功能，提供统一的通知接口
 */

import { ElMessage, ElMessageBox, ElNotification, type MessageParams, type NotificationParams } from 'element-plus'
import { ref, type Ref } from 'vue'

/**
 * 通知类型
 */
export type NotificationType = 'success' | 'warning' | 'info' | 'error'

/**
 * 通知选项
 */
export interface NotifyOptions {
  /** 通知类型 */
  type?: NotificationType
  /** 通知标题 */
  title?: string
  /** 通知内容 */
  message: string
  /** 显示时间（毫秒），0 表示不自动关闭 */
  duration?: number
  /** 是否显示关闭按钮 */
  showClose?: boolean
  /** 是否使用 HTML 解析 */
  dangerouslyUseHTMLString?: boolean
}

/**
 * 确认对话框选项
 */
export interface ConfirmOptions {
  /** 标题 */
  title?: string
  /** 确认按钮文字 */
  confirmButtonText?: string
  /** 取消按钮文字 */
  cancelButtonText?: string
  /** 确认按钮类型 */
  confirmButtonType?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  /** 取消按钮类型 */
  cancelButtonType?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'text'
  /** 图标类型 */
  type?: 'success' | 'warning' | 'info' | 'error'
  /** 是否显示遮罩层 */
  modal?: boolean
}

/**
 * 基础通知 Composable
 *
 * @example
 * ```ts
 * const { success, error, warning, info } = useNotification()
 *
 * success('操作成功')
 * error('操作失败')
 * ```
 */
export function useNotification(): {
  /** 成功通知 */
  success: (message: string, title?: string) => void
  /** 错误通知 */
  error: (message: string, title?: string) => void
  /** 警告通知 */
  warning: (message: string, title?: string) => void
  /** 信息通知 */
  info: (message: string, title?: string) => void
  /** 自定义通知 */
  notify: (options: NotifyOptions) => void
  /** 消息提示 */
  message: (message: string, type?: NotificationType) => void
  /** 确认对话框 */
  confirm: (message: string, options?: ConfirmOptions) => Promise<boolean>
  /** 提示对话框 */
  alert: (message: string, title?: string) => Promise<void>
  /** 输入对话框 */
  prompt: (message: string, title?: string, inputValue?: string) => Promise<string | null>
} {
  /**
   * 成功通知
   */
  const success = (message: string, title?: string): void => {
    if (title) {
      ElNotification({
        title,
        message,
        type: 'success',
        duration: 3000,
      })
    } else {
      ElMessage.success(message)
    }
  }

  /**
   * 错误通知
   */
  const error = (message: string, title?: string): void => {
    if (title) {
      ElNotification({
        title,
        message,
        type: 'error',
        duration: 5000,
      })
    } else {
      ElMessage.error(message)
    }
  }

  /**
   * 警告通知
   */
  const warning = (message: string, title?: string): void => {
    if (title) {
      ElNotification({
        title,
        message,
        type: 'warning',
        duration: 4000,
      })
    } else {
      ElMessage.warning(message)
    }
  }

  /**
   * 信息通知
   */
  const info = (message: string, title?: string): void => {
    if (title) {
      ElNotification({
        title,
        message,
        type: 'info',
        duration: 3000,
      })
    } else {
      ElMessage.info(message)
    }
  }

  /**
   * 自定义通知
   */
  const notify = (options: NotifyOptions): void => {
    const {
      type = 'info',
      title,
      message,
      duration = 3000,
      showClose = true,
      dangerouslyUseHTMLString = false,
    } = options

    if (title) {
      ElNotification({
        title,
        message,
        type,
        duration,
        showClose,
        dangerouslyUseHTMLString,
      } as NotificationParams)
    } else {
      ElMessage({
        message,
        type,
        duration,
        showClose,
        dangerouslyUseHTMLString,
      } as MessageParams)
    }
  }

  /**
   * 消息提示
   */
  const message = (msg: string, type: NotificationType = 'info'): void => {
    ElMessage({
      message: msg,
      type,
    } as MessageParams)
  }

  /**
   * 确认对话框
   */
  const confirm = async (
    message: string,
    options: ConfirmOptions = {}
  ): Promise<boolean> => {
    const {
      title = '确认',
      confirmButtonText = '确定',
      cancelButtonText = '取消',
      confirmButtonType = 'primary',
      type = 'warning',
      modal = true,
    } = options

    try {
      await ElMessageBox.confirm(message, title, {
        confirmButtonText,
        cancelButtonText,
        confirmButtonClass: `el-button--${confirmButtonType}`,
        type,
        modal,
      })
      return true
    } catch {
      return false
    }
  }

  /**
   * 提示对话框
   */
  const alert = async (message: string, title: string = '提示'): Promise<void> => {
    await ElMessageBox.alert(message, title, {
      confirmButtonText: '确定',
    })
  }

  /**
   * 输入对话框
   */
  const prompt = async (
    message: string,
    title: string = '请输入',
    inputValue: string = ''
  ): Promise<string | null> => {
    try {
      const result = await ElMessageBox.prompt(message, title, {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputValue,
      })
      if (typeof result === 'object' && result !== null && 'value' in result) {
        return result.value
      }
      return null
    } catch {
      return null
    }
  }

  return {
    success,
    error,
    warning,
    info,
    notify,
    message,
    confirm,
    alert,
    prompt,
  }
}

/**
 * 通知历史记录
 */
export interface NotificationRecord {
  id: string
  type: NotificationType
  title?: string
  message: string
  timestamp: number
  read: boolean
}

/**
 * 带历史记录的通知 Composable
 *
 * @param maxRecords - 最大记录数
 *
 * @example
 * ```ts
 * const { success, history, markAsRead, clearHistory } = useNotificationHistory(50)
 *
 * success('操作成功')
 * console.log(history.value) // 查看通知历史
 * ```
 */
export function useNotificationHistory(maxRecords: number = 100): {
  /** 成功通知 */
  success: (message: string, title?: string) => void
  /** 错误通知 */
  error: (message: string, title?: string) => void
  /** 警告通知 */
  warning: (message: string, title?: string) => void
  /** 信息通知 */
  info: (message: string, title?: string) => void
  /** 通知历史 */
  history: Ref<NotificationRecord[]>
  /** 未读数量 */
  unreadCount: Ref<number>
  /** 标记为已读 */
  markAsRead: (id: string) => void
  /** 全部标记为已读 */
  markAllAsRead: () => void
  /** 清除历史 */
  clearHistory: () => void
  /** 删除单条记录 */
  removeRecord: (id: string) => void
} {
  const history = ref<NotificationRecord[]>([])
  const unreadCount = ref(0)

  const baseNotification = useNotification()

  /**
   * 添加记录
   */
  const addRecord = (type: NotificationType, message: string, title?: string): void => {
    const record: NotificationRecord = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      type,
      title,
      message,
      timestamp: Date.now(),
      read: false,
    }

    history.value.unshift(record)
    unreadCount.value++

    // 限制最大记录数
    if (history.value.length > maxRecords) {
      history.value = history.value.slice(0, maxRecords)
    }
  }

  const success = (message: string, title?: string): void => {
    baseNotification.success(message, title)
    addRecord('success', message, title)
  }

  const error = (message: string, title?: string): void => {
    baseNotification.error(message, title)
    addRecord('error', message, title)
  }

  const warning = (message: string, title?: string): void => {
    baseNotification.warning(message, title)
    addRecord('warning', message, title)
  }

  const info = (message: string, title?: string): void => {
    baseNotification.info(message, title)
    addRecord('info', message, title)
  }

  const markAsRead = (id: string): void => {
    const record = history.value.find((r) => r.id === id)
    if (record && !record.read) {
      record.read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    }
  }

  const markAllAsRead = (): void => {
    history.value.forEach((record) => {
      record.read = true
    })
    unreadCount.value = 0
  }

  const clearHistory = (): void => {
    history.value = []
    unreadCount.value = 0
  }

  const removeRecord = (id: string): void => {
    const index = history.value.findIndex((r) => r.id === id)
    if (index !== -1) {
      const record = history.value[index]
      if (record && !record.read) {
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
      history.value.splice(index, 1)
    }
  }

  return {
    success,
    error,
    warning,
    info,
    history,
    unreadCount,
    markAsRead,
    markAllAsRead,
    clearHistory,
    removeRecord,
  }
}

/**
 * 异步操作通知 Composable
 *
 * 自动处理异步操作的成功/失败通知
 *
 * @example
 * ```ts
 * const { withNotify } = useAsyncNotify()
 *
 * await withNotify(
 *   async () => fetchData(),
 *   {
 *     success: '数据加载成功',
 *     error: '数据加载失败',
 *     loading: '正在加载...',
 *   }
 * )
 * ```
 */
export function useAsyncNotify(): {
  /** 带通知的异步操作 */
  withNotify: <T>(
    fn: () => Promise<T>,
    options: {
      success?: string
      error?: string | ((err: Error) => string)
      loading?: string
    }
  ) => Promise<T | null>
  /** 带确认的异步操作 */
  withConfirm: <T>(
    fn: () => Promise<T>,
    options: {
      confirmMessage: string
      confirmTitle?: string
      success?: string
      error?: string | ((err: Error) => string)
    }
  ) => Promise<T | null>
} {
  const notification = useNotification()

  const withNotify = async <T>(
    fn: () => Promise<T>,
    options: {
      success?: string
      error?: string | ((err: Error) => string)
      loading?: string
    }
  ): Promise<T | null> => {
    const { success, error, loading } = options

    if (loading) {
      notification.info(loading)
    }

    try {
      const result = await fn()
      if (success) {
        notification.success(success)
      }
      return result
    } catch (err) {
      const errorMessage = error
        ? typeof error === 'function'
          ? error(err as Error)
          : error
        : (err as Error).message || '操作失败'
      notification.error(errorMessage)
      return null
    }
  }

  const withConfirm = async <T>(
    fn: () => Promise<T>,
    options: {
      confirmMessage: string
      confirmTitle?: string
      success?: string
      error?: string | ((err: Error) => string)
    }
  ): Promise<T | null> => {
    const { confirmMessage, confirmTitle, success, error } = options

    const confirmed = await notification.confirm(confirmMessage, {
      title: confirmTitle,
    })

    if (!confirmed) {
      return null
    }

    return withNotify(fn, { success, error })
  }

  return {
    withNotify,
    withConfirm,
  }
}

export default useNotification
