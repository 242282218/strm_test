import { describe, expect, it } from 'vitest'

import {
  getDashboardStats as legacyGetDashboardStats,
  getTaskTrends as legacyGetTaskTrends
} from '@/api/dashboard'

import {
  getDashboardStats as featureGetDashboardStats,
  getTaskTrends as featureGetTaskTrends
} from './api/dashboard'
import legacyDashboardViewSource from '../../views/DashboardView.vue?raw'

describe('dashboard feature module aliases', () => {
  it('keeps legacy dashboard api exports mapped to the feature module', () => {
    expect(legacyGetDashboardStats).toBe(featureGetDashboardStats)
    expect(legacyGetTaskTrends).toBe(featureGetTaskTrends)
  })

  it('keeps the legacy dashboard view path mapped to the feature module', () => {
    expect(legacyDashboardViewSource).toContain('@/features/dashboard/views/DashboardView.vue')
  })
})
