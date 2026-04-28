/**
 * Composables 统一导出
 *
 * 提供可复用的组合式函数
 */

// 请求状态管理
export {
  useRequest,
  usePagination,
  type RequestState,
  type RequestOptions,
  type PaginationState,
  type PaginationOptions,
} from './useRequest'

// 防抖/节流
export {
  useDebounce,
  useThrottle,
  useDebouncedRef,
  useThrottledRef,
  type DebounceFunction,
  type ThrottleFunction,
} from './useDebounce'

// 加载状态管理
export {
  useLoading,
  useLoadingStore,
  useGlobalLoading,
  useProgressLoading,
  type LoadingItem,
  type ProgressLoadingOptions,
} from './useLoading'

// 通知封装
export {
  useNotification,
  useNotificationHistory,
  useAsyncNotify,
  type NotificationType,
  type NotifyOptions,
  type ConfirmOptions,
  type NotificationRecord,
} from './useNotification'

// 主题管理
export {
  useTheme,
  initTheme,
  type ThemeMode,
} from './useTheme'

// ECharts 封装
export {
  useECharts,
  type UseEChartsOptions,
} from './useECharts'

// API 请求缓存
export {
  useApiCache,
  useGlobalApiCache,
  requestWithCache,
} from './useApiCache'
