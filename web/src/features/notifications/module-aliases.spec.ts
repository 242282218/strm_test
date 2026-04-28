import { describe, expect, it } from 'vitest'

import { convertFrontendToBackend as legacyConvertFrontendToBackend } from '@/api/notification'

import { convertFrontendToBackend as featureConvertFrontendToBackend } from './api/notification'
import legacyNotificationsViewSource from '../../views/NotificationsView.vue?raw'
import legacyNotificationHistoryViewSource from '../../views/NotificationHistoryView.vue?raw'

describe('notifications feature module aliases', () => {
  it('keeps legacy notification api exports mapped to the feature module', () => {
    expect(legacyConvertFrontendToBackend).toBe(featureConvertFrontendToBackend)
  })

  it('keeps legacy notification view paths mapped to the feature modules', () => {
    expect(legacyNotificationsViewSource).toContain('@/features/notifications/views/NotificationsView.vue')
    expect(legacyNotificationHistoryViewSource).toContain(
      '@/features/notifications/views/NotificationHistoryView.vue'
    )
  })
})
