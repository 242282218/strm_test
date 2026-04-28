import { describe, expect, it } from 'vitest'

import { searchResources as legacySearchResources } from '@/api/search'
import { useSearchStore as legacyUseSearchStore } from '@/stores/search'

import { searchResources as featureSearchResources } from './api/search'
import { useSearchStore as featureUseSearchStore } from './store/search'
import legacySearchViewSource from '../../views/SearchView.vue?raw'
import legacySearchHeroSource from '../../components/search/SearchHero.vue?raw'

describe('search feature module aliases', () => {
  it('keeps legacy api and store exports mapped to the feature modules', () => {
    expect(legacySearchResources).toBe(featureSearchResources)
    expect(legacyUseSearchStore).toBe(featureUseSearchStore)
  })

  it('keeps legacy search view and component paths mapped to the feature modules', () => {
    expect(legacySearchViewSource).toContain('@/features/search/views/SearchView.vue')
    expect(legacySearchHeroSource).toContain('@/features/search/components/SearchHero.vue')
  })
})
