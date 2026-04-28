import { describe, expect, it } from 'vitest'

import { scrapeApi as legacyScrapeApi } from '@/api/scrape'

import { scrapeApi as featureScrapeApi } from './api/scrape'
import legacyScrapePathsViewSource from '../../views/ScrapePathsView.vue?raw'
import legacyScrapeRecordsViewSource from '../../views/ScrapeRecordsView.vue?raw'

describe('scrape feature module aliases', () => {
  it('keeps legacy scrape api exports mapped to the feature module', () => {
    expect(legacyScrapeApi).toBe(featureScrapeApi)
  })

  it('keeps legacy scrape view paths mapped to the feature module', () => {
    expect(legacyScrapePathsViewSource).toContain('@/features/scrape/views/ScrapePathsView.vue')
    expect(legacyScrapeRecordsViewSource).toContain('@/features/scrape/views/ScrapeRecordsView.vue')
  })
})
