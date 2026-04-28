/**
 * useLoading - 统一加载状态管理 Composable
 *
 * 提供全局和局部加载状态管理，支持多个加载状态组合
 */

import { ref, computed, type Ref, type ComputedRef } from 'vue'

/**
 * 加载状态项
 */
export interface LoadingItem {
  key: string
  loading: Ref<boolean>
  message?: string
}

/**
 * 单一加载状态 Composable
 *
 * @param initialState - 初始加载状态
 *
 * @example
 * ```ts
 * const { loading, start, stop, toggle, withLoading } = useLoading()
 *
 * // 使用 withLoading 自动管理加载状态
 * await withLoading(async () => {
 *   await fetchData()
 * })
 * ```
 */
export function useLoading(initialState: boolean = false): {
  loading: Ref<boolean>
  start: () => void
  stop: () => void
  toggle: () => void
  withLoading: <T>(fn: () => Promise<T>) => Promise<T>
} {
  const loading = ref(initialState)

  const start = () => {
    loading.value = true
  }

  const stop = () => {
    loading.value = false
  }

  const toggle = () => {
    loading.value = !loading.value
  }

  /**
   * 自动管理加载状态的包装函数
   */
  async function withLoading<T>(fn: () => Promise<T>): Promise<T> {
    try {
      start()
      return await fn()
    } finally {
      stop()
    }
  }

  return {
    loading,
    start,
    stop,
    toggle,
    withLoading,
  }
}

/**
 * 多加载状态管理 Composable
 *
 * @param keys - 加载状态的键名数组
 *
 * @example
 * ```ts
 * const { isLoading, start, stop, anyLoading, allLoading } = useLoadingStore(['fetch', 'save', 'delete'])
 *
 * // 使用
 * start('fetch')
 * await fetchData()
 * stop('fetch')
 *
 * // 检查状态
 * if (anyLoading.value) {
 *   console.log('有操作正在进行')
 * }
 * ```
 */
export function useLoadingStore<K extends string = string>(
  keys: K[] = []
): {
  /** 检查指定 key 是否正在加载 */
  isLoading: (key: K) => boolean
  /** 开始加载 */
  start: (key: K, message?: string) => void
  /** 停止加载 */
  stop: (key: K) => void
  /** 切换加载状态 */
  toggle: (key: K) => void
  /** 获取加载消息 */
  getMessage: (key: K) => string | undefined
  /** 设置加载消息 */
  setMessage: (key: K, message: string) => void
  /** 是否有任何加载中 */
  anyLoading: ComputedRef<boolean>
  /** 是否全部加载中 */
  allLoading: ComputedRef<boolean>
  /** 获取所有加载中的 keys */
  loadingKeys: ComputedRef<K[]>
  /** 停止所有加载 */
  stopAll: () => void
  /** 重置所有状态 */
  reset: () => void
  /** 包装函数自动管理加载状态 */
  withLoading: <T>(key: K, fn: () => Promise<T>) => Promise<T>
} {
  const loadingMap = ref(new Map<K, { loading: boolean; message?: string }>())

  // 初始化
  keys.forEach((key) => {
    loadingMap.value.set(key, { loading: false })
  })

  const isLoading = (key: K): boolean => {
    return loadingMap.value.get(key)?.loading ?? false
  }

  const start = (key: K, message?: string): void => {
    loadingMap.value.set(key, { loading: true, message })
  }

  const stop = (key: K): void => {
    const item = loadingMap.value.get(key)
    if (item) {
      loadingMap.value.set(key, { loading: false })
    }
  }

  const toggle = (key: K): void => {
    const item = loadingMap.value.get(key)
    if (item) {
      loadingMap.value.set(key, { loading: !item.loading })
    }
  }

  const getMessage = (key: K): string | undefined => {
    return loadingMap.value.get(key)?.message
  }

  const setMessage = (key: K, message: string): void => {
    const item = loadingMap.value.get(key)
    if (item) {
      loadingMap.value.set(key, { ...item, message })
    }
  }

  const anyLoading = computed(() => {
    return Array.from(loadingMap.value.values()).some((item) => item.loading)
  })

  const allLoading = computed(() => {
    const items = Array.from(loadingMap.value.values())
    return items.length > 0 && items.every((item) => item.loading)
  })

  const loadingKeys = computed(() => {
    return Array.from(loadingMap.value.entries())
      .filter(([, item]) => item.loading)
      .map(([key]) => key)
  })

  const stopAll = (): void => {
    loadingMap.value.forEach((item, key) => {
      loadingMap.value.set(key, { loading: false })
    })
  }

  const reset = (): void => {
    loadingMap.value.clear()
    keys.forEach((key) => {
      loadingMap.value.set(key, { loading: false })
    })
  }

  const withLoading = async <T>(key: K, fn: () => Promise<T>): Promise<T> => {
    try {
      start(key)
      return await fn()
    } finally {
      stop(key)
    }
  }

  return {
    isLoading,
    start,
    stop,
    toggle,
    getMessage,
    setMessage,
    anyLoading,
    allLoading,
    loadingKeys,
    stopAll,
    reset,
    withLoading,
  }
}

/**
 * 全局加载状态管理（单例模式）
 */
let globalLoadingInstance: ReturnType<typeof useLoadingStore<string>> | null = null

/**
 * 获取全局加载状态管理器
 *
 * @example
 * ```ts
 * // 在任何组件中使用
 * const globalLoading = useGlobalLoading()
 *
 * // 开始加载
 * globalLoading.start('fetchData', '正在加载数据...')
 *
 * // 停止加载
 * globalLoading.stop('fetchData')
 * ```
 */
export function useGlobalLoading(): ReturnType<typeof useLoadingStore<string>> {
  if (!globalLoadingInstance) {
    globalLoadingInstance = useLoadingStore<string>()
  }
  return globalLoadingInstance
}

/**
 * 带进度条的加载状态
 */
export interface ProgressLoadingOptions {
  /** 初始进度 */
  initialProgress?: number
  /** 自动递增间隔（毫秒） */
  autoIncrementInterval?: number
  /** 自动递增值 */
  autoIncrementValue?: number
  /** 最大进度 */
  maxProgress?: number
}

/**
 * 带进度的加载状态 Composable
 *
 * @example
 * ```ts
 * const { loading, progress, start, updateProgress, complete, withProgress } = useProgressLoading()
 *
 * await withProgress(async (update) => {
 *   update(10)
 *   await step1()
 *   update(40)
 *   await step2()
 *   update(100)
 * })
 * ```
 */
export function useProgressLoading(
  options: ProgressLoadingOptions = {}
): {
  loading: Ref<boolean>
  progress: Ref<number>
  message: Ref<string>
  start: (message?: string) => void
  updateProgress: (value: number) => void
  increment: (value?: number) => void
  setMessage: (message: string) => void
  complete: () => void
  reset: () => void
  withProgress: <T>(
    fn: (update: (value: number) => void) => Promise<T>,
    options?: { message?: string }
  ) => Promise<T>
} {
  const {
    initialProgress = 0,
    autoIncrementInterval = 200,
    autoIncrementValue = 5,
    maxProgress = 100,
  } = options

  const loading = ref(false)
  const progress = ref(initialProgress)
  const message = ref('')

  let autoIncrementTimer: ReturnType<typeof setInterval> | null = null

  const start = (msg?: string): void => {
    loading.value = true
    progress.value = initialProgress
    message.value = msg || ''
  }

  const updateProgress = (value: number): void => {
    progress.value = Math.min(Math.max(value, 0), maxProgress)
  }

  const increment = (value: number = autoIncrementValue): void => {
    updateProgress(progress.value + value)
  }

  const setMessage = (msg: string): void => {
    message.value = msg
  }

  const complete = (): void => {
    progress.value = maxProgress
    loading.value = false
    message.value = ''
    if (autoIncrementTimer) {
      clearInterval(autoIncrementTimer)
      autoIncrementTimer = null
    }
  }

  const reset = (): void => {
    loading.value = false
    progress.value = initialProgress
    message.value = ''
    if (autoIncrementTimer) {
      clearInterval(autoIncrementTimer)
      autoIncrementTimer = null
    }
  }

  /**
   * 自动递增进度
   */
  const startAutoIncrement = (): void => {
    if (autoIncrementTimer) return
    autoIncrementTimer = setInterval(() => {
      if (progress.value < maxProgress - 10) {
        increment()
      }
    }, autoIncrementInterval)
  }

  const withProgress = async <T>(
    fn: (update: (value: number) => void) => Promise<T>,
    options?: { message?: string }
  ): Promise<T> => {
    try {
      start(options?.message)
      startAutoIncrement()
      return await fn(updateProgress)
    } finally {
      complete()
    }
  }

  return {
    loading,
    progress,
    message,
    start,
    updateProgress,
    increment,
    setMessage,
    complete,
    reset,
    withProgress,
  }
}

export default useLoading
