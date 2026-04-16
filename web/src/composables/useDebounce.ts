/**
 * useDebounce - 防抖/节流 Composable
 * 
 * 提供防抖和节流功能，用于优化高频事件处理
 */

import { ref, watch, type Ref, type WatchSource, onUnmounted } from 'vue'

/**
 * 防抖函数类型
 */
export type DebounceFunction<T extends unknown[], R> = (...args: T) => R | undefined

/**
 * 节流函数类型
 */
export type ThrottleFunction<T extends unknown[], R> = (...args: T) => R | undefined

/**
 * 防抖 Composable
 * 
 * @param fn - 需要防抖的函数
 * @param delay - 延迟时间（毫秒）
 * @param options - 配置选项
 * 
 * @example
 * ```ts
 * const debouncedSearch = useDebounce(
 *   (keyword: string) => searchApi(keyword),
 *   300
 * )
 * 
 * // 在输入框中使用
 * <input @input="debouncedSearch($event.target.value)" />
 * ```
 */
export function useDebounce<T extends unknown[], R>(
  fn: (...args: T) => R,
  delay: number = 300,
  options: {
    /** 是否在延迟开始前立即执行 */
    leading?: boolean
    /** 是否在延迟结束后执行 */
    trailing?: boolean
    /** 最大等待时间 */
    maxWait?: number
  } = {}
): {
  run: DebounceFunction<T, R>
  cancel: () => void
  flush: () => R | undefined
  pending: Ref<boolean>
} {
  const { leading = false, trailing = true, maxWait } = options

  let timeoutId: ReturnType<typeof setTimeout> | null = null
  let lastArgs: T | null = null
  let lastCallTime = 0
  let result: R | undefined

  const pending = ref(false)

  /**
   * 调用原函数
   */
  function invokeFunc(): R | undefined {
    if (lastArgs === null) return undefined

    const args = lastArgs

    lastArgs = null
    pending.value = false

    result = fn(...args)
    return result
  }

  /**
   * 启动定时器
   */
  function startTimer(): void {
    pending.value = true
    const wait = maxWait !== undefined 
      ? Math.min(delay, maxWait - (Date.now() - lastCallTime))
      : delay

    timeoutId = setTimeout(() => {
      if (trailing && lastArgs) {
        invokeFunc()
      }
      timeoutId = null
      pending.value = false
    }, wait)
  }

  /**
   * 取消定时器
   */
  function cancel(): void {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
    lastArgs = null
    pending.value = false
  }

  /**
   * 立即执行
   */
  function flush(): R | undefined {
    if (timeoutId && lastArgs) {
      cancel()
      return invokeFunc()
    }
    return result
  }

  /**
   * 防抖函数
   */
  function debounced(...args: T): R | undefined {
    const time = Date.now()
    const isInvoking = time - lastCallTime >= delay

    lastArgs = args
    lastCallTime = time

    if (isInvoking && leading) {
      return invokeFunc()
    }

    if (!timeoutId) {
      startTimer()
    }

    return result
  }

  // 组件卸载时清理
  onUnmounted(cancel)

  return {
    run: debounced,
    cancel,
    flush,
    pending,
  }
}

/**
 * 节流 Composable
 * 
 * @param fn - 需要节流的函数
 * @param interval - 间隔时间（毫秒）
 * @param options - 配置选项
 * 
 * @example
 * ```ts
 * const throttledScroll = useThrottle(
 *   () => console.log('scroll'),
 *   100
 * )
 * 
 * // 在滚动事件中使用
 * window.addEventListener('scroll', throttledScroll)
 * ```
 */
export function useThrottle<T extends unknown[], R>(
  fn: (...args: T) => R,
  interval: number = 100,
  options: {
    /** 是否在间隔开始时执行 */
    leading?: boolean
    /** 是否在间隔结束时执行 */
    trailing?: boolean
  } = {}
): {
  run: ThrottleFunction<T, R>
  cancel: () => void
  flush: () => R | undefined
  pending: Ref<boolean>
} {
  const { leading = true, trailing = true } = options

  let timeoutId: ReturnType<typeof setTimeout> | null = null
  let lastArgs: T | null = null
  let lastInvokeTime = 0
  let result: R | undefined

  const pending = ref(false)

  /**
   * 调用原函数
   */
  function invokeFunc(): R | undefined {
    if (lastArgs === null) return undefined

    const args = lastArgs

    lastArgs = null
    lastInvokeTime = Date.now()
    pending.value = false

    result = fn(...args)
    return result
  }

  /**
   * 启动定时器
   */
  function startTimer(): void {
    const remaining = interval - (Date.now() - lastInvokeTime)
    pending.value = true

    timeoutId = setTimeout(() => {
      if (trailing && lastArgs) {
        invokeFunc()
      }
      timeoutId = null
      pending.value = false
    }, remaining)
  }

  /**
   * 取消定时器
   */
  function cancel(): void {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
    lastArgs = null
    pending.value = false
  }

  /**
   * 立即执行
   */
  function flush(): R | undefined {
    if (timeoutId && lastArgs) {
      cancel()
      return invokeFunc()
    }
    return result
  }

  /**
   * 节流函数
   */
  function throttled(...args: T): R | undefined {
    const time = Date.now()
    const isInvoking = time - lastInvokeTime >= interval

    lastArgs = args

    if (isInvoking) {
      if (timeoutId) {
        cancel()
      }
      if (leading) {
        return invokeFunc()
      }
    }

    if (!timeoutId) {
      startTimer()
    }

    return result
  }

  // 组件卸载时清理
  onUnmounted(cancel)

  return {
    run: throttled,
    cancel,
    flush,
    pending,
  }
}

/**
 * 防抖值 Composable
 * 
 * @param value - 需要防抖的值
 * @param delay - 延迟时间（毫秒）
 * 
 * @example
 * ```ts
 * const keyword = ref('')
 * const debouncedKeyword = useDebouncedRef(keyword, 300)
 * 
 * // 监听防抖后的值
 * watch(debouncedKeyword, (val) => {
 *   search(val)
 * })
 * ```
 */
export function useDebouncedRef<T>(
  value: WatchSource<T>,
  delay: number = 300
): Ref<T> {
  const debouncedValue = ref<T>(
    typeof value === 'function' ? value() : value.value
  ) as Ref<T>

  const { run } = useDebounce((val: T) => {
    debouncedValue.value = val
  }, delay)

  watch(value, (val) => {
    run(val)
  })

  return debouncedValue
}

/**
 * 节流值 Composable
 * 
 * @param value - 需要节流的值
 * @param interval - 间隔时间（毫秒）
 * 
 * @example
 * ```ts
 * const scrollY = ref(0)
 * const throttledScrollY = useThrottledRef(scrollY, 100)
 * ```
 */
export function useThrottledRef<T>(
  value: WatchSource<T>,
  interval: number = 100
): Ref<T> {
  const throttledValue = ref<T>(
    typeof value === 'function' ? value() : value.value
  ) as Ref<T>

  const { run } = useThrottle((val: T) => {
    throttledValue.value = val
  }, interval)

  watch(value, (val) => {
    run(val)
  })

  return throttledValue
}

export default useDebounce
