import { describe, expect, it } from 'vitest'

import {
  clearProxyCache as legacyClearProxyCache,
  getProxyCacheStats as legacyGetProxyCacheStats,
  getProxyStreamUrl as legacyGetProxyStreamUrl
} from '@/api/proxy'

import {
  clearProxyCache as featureClearProxyCache,
  getProxyCacheStats as featureGetProxyCacheStats,
  getProxyStreamUrl as featureGetProxyStreamUrl
} from './api/proxy'
import legacyProxyServiceViewSource from '../../views/ProxyServiceView.vue?raw'

describe('proxy feature module aliases', () => {
  it('keeps legacy proxy api exports mapped to the feature module', () => {
    expect(legacyGetProxyCacheStats).toBe(featureGetProxyCacheStats)
    expect(legacyClearProxyCache).toBe(featureClearProxyCache)
    expect(legacyGetProxyStreamUrl).toBe(featureGetProxyStreamUrl)
  })

  it('keeps the legacy proxy service view path mapped to the feature module', () => {
    expect(legacyProxyServiceViewSource).toContain('@/features/proxy/views/ProxyServiceView.vue')
  })
})
