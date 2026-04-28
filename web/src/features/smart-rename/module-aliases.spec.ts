import { describe, expect, it } from 'vitest'

import {
  executeSmartRename as legacyExecuteSmartRename,
  getSmartRenameStatus as legacyGetSmartRenameStatus,
  previewSmartRename as legacyPreviewSmartRename
} from '@/api/smartRename'

import {
  executeSmartRename as featureExecuteSmartRename,
  getSmartRenameStatus as featureGetSmartRenameStatus,
  previewSmartRename as featurePreviewSmartRename
} from './api/smartRename'
import legacySmartRenameViewSource from '../../views/SmartRenameView.vue?raw'

describe('smart rename feature module aliases', () => {
  it('keeps legacy smart rename api exports mapped to the feature module', () => {
    expect(legacyPreviewSmartRename).toBe(featurePreviewSmartRename)
    expect(legacyExecuteSmartRename).toBe(featureExecuteSmartRename)
    expect(legacyGetSmartRenameStatus).toBe(featureGetSmartRenameStatus)
  })

  it('keeps the legacy smart rename view path mapped to the feature module', () => {
    expect(legacySmartRenameViewSource).toContain('@/features/smart-rename/views/SmartRenameView.vue')
  })
})
