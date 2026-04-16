/**
 * useRequest - 请求状态管理 Composable
 * 
 * 封装异步请求的状态管理，提供统一的请求处理模式
 * 支持：loading 状态、错误处理、数据缓存、请求取消
 */

import { ref, computed, type Ref, type ComputedRef } from 'vue'

export interface RequestState<T> {
  data: Ref<T | null>
  error: Ref<Error | null>
  loading: Ref<boolean>
  hasError: ComputedRef<boolean>
  hasData: ComputedRef<boolean>
}

export interface RequestOptions<T> {
  /** 初始数据 */
  initialData?: T
  /** 是否立即执行 */
  immediate?: boolean
  /** 成功回调 */
  onSuccess?: (data: T) => void
  /** 失败回调 */
  onError?: (error: Error) => void
  /** 完成回调（无论成功失败） */
  onFinally?: () => void
}

export interface RequestExecuteOptions {
  /** 是否重置错误 */
  resetError?: boolean
  /** 是否重置数据 */
  resetData?: boolean
}

/**
 * 请求状态管理 Composable
 * 
 * @example
 * ```ts
 * const { data, loading, error, execute } = useRequest(
 *   (id: number) => api.getUser(id),
 *   { immediate: false }
 * )
 * 
 * // 执行请求
 * await execute(1)
 * 
 * // 在模板中使用
 * <div v-if="loading">加载中...</div>
 * <div v-else-if="error">错误: {{ error.message }}</div>
 * <div v-else>{{ data }}</div>
 * ```
 */
export function useRequest<T, P extends unknown[] = []>(
  requestFn: (...args: P) => Promise<T>,
  options: RequestOptions<T> = {}
): RequestState<T> & {
  execute: (...args: P) => Promise<T | null>
  reset: () => void
  abort: () => void
} {
  const {
    initialData = null,
    immediate = false,
    onSuccess,
    onError,
    onFinally,
  } = options

  // 状态
  const data = ref<T | null>(initialData as T | null) as Ref<T | null>
  const error = ref<Error | null>(null)
  const loading = ref(false)

  // 计算属性
  const hasError = computed(() => error.value !== null)
  const hasData = computed(() => data.value !== null)

  // 用于取消请求的 AbortController
  let abortController: AbortController | null = null

  /**
   * 执行请求
   */
  async function execute(
    ...args: P
  ): Promise<T | null> {
    // 取消之前的请求
    if (abortController) {
      abortController.abort()
    }

    // 创建新的 AbortController
    abortController = new AbortController()

    loading.value = true
    error.value = null

    try {
      const result = await requestFn(...args)
      
      // 检查是否已被取消
      if (abortController?.signal.aborted) {
        return null
      }

      data.value = result
      onSuccess?.(result)
      return result
    } catch (err) {
      // 忽略取消错误
      if (err instanceof Error && err.name === 'AbortError') {
        return null
      }

      const errorInstance = err instanceof Error ? err : new Error(String(err))
      error.value = errorInstance
      onError?.(errorInstance)
      return null
    } finally {
      loading.value = false
      onFinally?.()
    }
  }

  /**
   * 重置状态
   */
  function reset(): void {
    data.value = initialData as T | null
    error.value = null
    loading.value = false
  }

  /**
   * 取消当前请求
   */
  function abort(): void {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    loading.value = false
  }

  // 立即执行
  if (immediate) {
    execute(...([] as unknown as P))
  }

  return {
    data,
    error,
    loading,
    hasError,
    hasData,
    execute,
    reset,
    abort,
  }
}

/**
 * 分页请求状态管理
 */
export interface PaginationState<T> {
  data: Ref<T[]>
  loading: Ref<boolean>
  loadingMore: Ref<boolean>
  error: Ref<Error | null>
  hasMore: Ref<boolean>
  page: Ref<number>
  pageSize: Ref<number>
  total: Ref<number>
}

export interface PaginationOptions<T> {
  /** 每页大小 */
  pageSize?: number
  /** 初始数据 */
  initialData?: T[]
}

/**
 * 分页请求 Composable
 * 
 * @example
 * ```ts
 * const { data, loading, loadMore, refresh } = usePagination(
 *   (page, pageSize) => api.getList({ page, pageSize })
 * )
 * ```
 */
export function usePagination<T, P extends unknown[] = []>(
  requestFn: (page: number, pageSize: number, ...args: P) => Promise<{
    items: T[]
    total: number
    hasMore?: boolean
  }>,
  options: PaginationOptions<T> = {}
): PaginationState<T> & {
  loadMore: (...args: P) => Promise<void>
  refresh: (...args: P) => Promise<void>
  reset: () => void
} {
  const { pageSize = 20, initialData = [] } = options

  // 状态
  const data = ref<T[]>(initialData) as Ref<T[]>
  const loading = ref(false)
  const loadingMore = ref(false)
  const error = ref<Error | null>(null)
  const hasMore = ref(true)
  const page = ref(1)
  const pageSizeRef = ref(pageSize)
  const total = ref(0)

  /**
   * 刷新数据（从第一页开始）
   */
  async function refresh(...args: P): Promise<void> {
    loading.value = true
    error.value = null
    page.value = 1

    try {
      const result = await requestFn(page.value, pageSizeRef.value, ...args)
      data.value = result.items
      total.value = result.total
      hasMore.value = result.hasMore ?? result.items.length >= pageSizeRef.value
    } catch (err) {
      const errorInstance = err instanceof Error ? err : new Error(String(err))
      error.value = errorInstance
      throw errorInstance
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载更多
   */
  async function loadMore(...args: P): Promise<void> {
    if (loadingMore.value || !hasMore.value) return

    loadingMore.value = true
    error.value = null

    try {
      page.value++
      const result = await requestFn(page.value, pageSizeRef.value, ...args)
      data.value.push(...result.items)
      hasMore.value = result.hasMore ?? result.items.length >= pageSizeRef.value
    } catch (err) {
      page.value--
      const errorInstance = err instanceof Error ? err : new Error(String(err))
      error.value = errorInstance
      throw errorInstance
    } finally {
      loadingMore.value = false
    }
  }

  /**
   * 重置状态
   */
  function reset(): void {
    data.value = initialData
    loading.value = false
    loadingMore.value = false
    error.value = null
    hasMore.value = true
    page.value = 1
    total.value = 0
  }

  return {
    data,
    loading,
    loadingMore,
    error,
    hasMore,
    page,
    pageSize: pageSizeRef,
    total,
    loadMore,
    refresh,
    reset,
  }
}

export default useRequest
