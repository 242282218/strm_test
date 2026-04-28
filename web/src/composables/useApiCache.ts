import { ref } from 'vue'

interface CacheItem<T> {
  data: T
  timestamp: number
  promise?: Promise<T>
}

/**
 * 轻量级 API 请求缓存 Hook - 支持 SWR 模式
 *
 * @example
 * const { cache, getCached, setCached, clearCache } = useApiCache()
 *
 * // 带缓存的请求
 * const fetchWithCache = async <T>(
 *   key: string,
 *   fetcher: () => Promise<T>,
 *   ttl = 5 * 60 * 1000
 * ): Promise<T> => {
 *   const cached = getCached<T>(key, ttl)
 *   if (cached) return cached
 *   const data = await fetcher()
 *   setCached(key, data)
 *   return data
 * }
 */
export function useApiCache(defaultTTL = 5 * 60 * 1000) {
  // 使用 Map 保持缓存数据
  const cache = new Map<string, CacheItem<unknown>>()
  const cacheKeys = ref<Set<string>>(new Set())

  /**
   * 获取缓存数据
   * @param key 缓存键
   * @param ttl 过期时间（毫秒），默认 5 分钟
   */
  const getCached = <T>(key: string, ttl: number = defaultTTL): T | null => {
    const item = cache.get(key)
    if (!item) return null

    const isExpired = Date.now() - item.timestamp > ttl
    if (isExpired) {
      cache.delete(key)
      cacheKeys.value.delete(key)
      return null
    }

    return item.data as T
  }

  /**
   * 设置缓存数据
   * @param key 缓存键
   * @param data 数据
   */
  const setCached = <T>(key: string, data: T): void => {
    cache.set(key, {
      data,
      timestamp: Date.now()
    })
    cacheKeys.value.add(key)
  }

  /**
   * 获取正在进行的请求 promise
   */
  const getPendingRequest = <T>(key: string): Promise<T> | undefined => {
    return cache.get(key)?.promise as Promise<T> | undefined
  }

  /**
   * 设置正在进行的请求 promise
   */
  const setPendingRequest = <T>(key: string, promise: Promise<T>): void => {
    const existing = cache.get(key)
    if (existing) {
      existing.promise = promise
    } else {
      cache.set(key, {
        data: null as unknown as T,
        timestamp: 0,
        promise
      })
      cacheKeys.value.add(key)
    }
  }

  /**
   * 清除请求 promise（请求完成后调用）
   */
  const clearPendingRequest = <T>(key: string, data: T): void => {
    const item = cache.get(key)
    if (item) {
      item.promise = undefined
      item.data = data
      item.timestamp = Date.now()
    }
  }

  /**
   * 清除指定缓存
   */
  const invalidate = (key: string): void => {
    cache.delete(key)
    cacheKeys.value.delete(key)
  }

  /**
   * 清除所有缓存
   */
  const clearCache = (): void => {
    cache.clear()
    cacheKeys.value.clear()
  }

  /**
   * 清除过期缓存
   */
  const clearExpired = (ttl: number = defaultTTL): void => {
    const now = Date.now()
    for (const key of cacheKeys.value) {
      const item = cache.get(key)
      if (item && now - item.timestamp > ttl) {
        cache.delete(key)
        cacheKeys.value.delete(key)
      }
    }
  }

  /**
   * 获取缓存统计信息
   */
  const getStats = () => ({
    size: cacheKeys.value.size,
    keys: Array.from(cacheKeys.value)
  })

  return {
    getCached,
    setCached,
    getPendingRequest,
    setPendingRequest,
    clearPendingRequest,
    invalidate,
    clearCache,
    clearExpired,
    getStats,
    cacheKeys
  }
}

// 全局缓存实例（可跨组件共享）
let globalCache: ReturnType<typeof useApiCache> | null = null

export function useGlobalApiCache(ttl: number = 5 * 60 * 1000) {
  if (!globalCache) {
    globalCache = useApiCache(ttl)
  }
  return globalCache
}

/**
 * 带缓存的请求函数
 * @example
 * const data = await requestWithCache('dashboard-stats', () => api.get('/dashboard'))
 */
export async function requestWithCache<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttl: number = 5 * 60 * 1000
): Promise<T> {
  const cache = useGlobalApiCache(ttl)

  // 检查是否有缓存
  const cached = cache.getCached<T>(key, ttl)
  if (cached) return cached

  // 检查是否有正在进行的请求
  const pending = cache.getPendingRequest<T>(key)
  if (pending) return pending

  // 发起新请求
  const promise = fetcher()
  cache.setPendingRequest(key, promise)

  try {
    const data = await promise
    cache.clearPendingRequest(key, data)
    return data
  } catch (error) {
    cache.invalidate(key)
    throw error
  }
}
