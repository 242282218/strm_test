import { describe, expect, it } from 'vitest'

import {
  getAIProviders as legacyGetAIProviders,
  getSystemConfig as legacyGetSystemConfig,
  updateSystemConfig as legacyUpdateSystemConfig
} from '@/api/systemConfig'

import {
  getAIProviders as featureGetAIProviders,
  getSystemConfig as featureGetSystemConfig,
  updateSystemConfig as featureUpdateSystemConfig
} from './api/systemConfig'
import legacyConfigViewSource from '../../views/ConfigView.vue?raw'

describe('config feature module aliases', () => {
  it('keeps legacy config api exports mapped to the feature module', () => {
    expect(legacyGetAIProviders).toBe(featureGetAIProviders)
    expect(legacyGetSystemConfig).toBe(featureGetSystemConfig)
    expect(legacyUpdateSystemConfig).toBe(featureUpdateSystemConfig)
  })

  it('keeps the legacy config view path mapped to the feature module', () => {
    expect(legacyConfigViewSource).toContain('@/features/config/views/ConfigView.vue')
  })
})
