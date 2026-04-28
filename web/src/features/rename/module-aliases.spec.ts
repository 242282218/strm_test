import { describe, expect, it } from 'vitest'

import {
  executeRename as legacyExecuteRename,
  getRenameStatus as legacyGetRenameStatus,
  previewRename as legacyPreviewRename
} from '@/api/rename'

import {
  executeRename as featureExecuteRename,
  getRenameStatus as featureGetRenameStatus,
  previewRename as featurePreviewRename
} from './api/rename'
import legacyRenameViewSource from '../../views/RenameView.vue?raw'

describe('rename feature module aliases', () => {
  it('keeps legacy rename api exports mapped to the feature module', () => {
    expect(legacyPreviewRename).toBe(featurePreviewRename)
    expect(legacyExecuteRename).toBe(featureExecuteRename)
    expect(legacyGetRenameStatus).toBe(featureGetRenameStatus)
  })

  it('keeps the legacy rename view path mapped to the feature module', () => {
    expect(legacyRenameViewSource).toContain('@/features/rename/views/RenameView.vue')
  })
})
