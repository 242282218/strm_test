import { describe, expect, it } from 'vitest'

import {
  browseQuarkDirectory as legacyBrowseQuarkDirectory,
  getQuarkConfig as legacyGetQuarkConfig,
  getQuarkFiles as legacyGetQuarkFiles,
  smartRenameCloudFiles as legacySmartRenameCloudFiles,
  syncQuarkFiles as legacySyncQuarkFiles
} from '@/api/quark'

import {
  browseQuarkDirectory as featureBrowseQuarkDirectory,
  getQuarkConfig as featureGetQuarkConfig,
  getQuarkFiles as featureGetQuarkFiles,
  smartRenameCloudFiles as featureSmartRenameCloudFiles,
  syncQuarkFiles as featureSyncQuarkFiles
} from './api/quark'
import legacyFilesViewSource from '../../views/FilesView.vue?raw'
import legacyQuarkFileBrowserSource from '../../components/QuarkFileBrowser.vue?raw'

describe('quark feature module aliases', () => {
  it('keeps legacy quark api exports mapped to the feature module', () => {
    expect(legacyBrowseQuarkDirectory).toBe(featureBrowseQuarkDirectory)
    expect(legacySmartRenameCloudFiles).toBe(featureSmartRenameCloudFiles)
    expect(legacyGetQuarkFiles).toBe(featureGetQuarkFiles)
    expect(legacyGetQuarkConfig).toBe(featureGetQuarkConfig)
    expect(legacySyncQuarkFiles).toBe(featureSyncQuarkFiles)
  })

  it('keeps legacy quark view and component paths mapped to the feature module', () => {
    expect(legacyFilesViewSource).toContain('@/features/quark/views/FilesView.vue')
    expect(legacyQuarkFileBrowserSource).toContain('@/features/quark/components/QuarkFileBrowser.vue')
  })
})
