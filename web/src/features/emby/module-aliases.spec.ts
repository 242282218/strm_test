import { describe, expect, it } from 'vitest'

import { embyApi as legacyEmbyApi } from '@/api/emby'
import { embyMonitorApi as legacyEmbyMonitorApi } from '@/api/embyMonitor'

import { embyApi as featureEmbyApi } from './api/emby'
import { embyMonitorApi as featureEmbyMonitorApi } from './api/monitor'
import legacyComponentSource from '../../components/EmbyConfigCard.vue?raw'
import legacyViewSource from '../../views/EmbyMonitorView.vue?raw'

describe('emby feature module aliases', () => {
  it('keeps legacy api exports mapped to the feature modules', () => {
    expect(legacyEmbyApi).toBe(featureEmbyApi)
    expect(legacyEmbyMonitorApi).toBe(featureEmbyMonitorApi)
  })

  it('keeps legacy component and view paths mapped to the feature modules', () => {
    expect(legacyComponentSource).toContain('@/features/emby/components/EmbyConfigCard.vue')
    expect(legacyViewSource).toContain('@/features/emby/views/EmbyMonitorView.vue')
  })
})
