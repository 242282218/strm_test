import { describe, expect, it } from 'vitest'

import { categoryStrategyApi as legacyCategoryStrategyApi } from '@/api/categoryStrategy'

import { categoryStrategyApi as featureCategoryStrategyApi } from './api/categoryStrategy'
import legacyCategoryStrategyViewSource from '../../views/CategoryStrategyView.vue?raw'

describe('category strategy feature module aliases', () => {
  it('keeps legacy category strategy api exports mapped to the feature module', () => {
    expect(legacyCategoryStrategyApi).toBe(featureCategoryStrategyApi)
  })

  it('keeps the legacy category strategy view path mapped to the feature module', () => {
    expect(legacyCategoryStrategyViewSource).toContain('@/features/category-strategy/views/CategoryStrategyView.vue')
  })
})
