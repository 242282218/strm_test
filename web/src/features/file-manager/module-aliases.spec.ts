import { describe, expect, it } from 'vitest'

import { fileManagerApi as legacyFileManagerApi } from '@/api/file-manager'
import { browseFiles as legacyBrowseFiles, fileOperation as legacyFileOperation } from '@/api/fileManager'
import { useFileManagerStore as legacyUseFileManagerStore } from '@/stores/file-manager'

import { fileManagerApi as featureFileManagerApi } from './api/file-manager'
import { browseFiles as featureBrowseFiles, fileOperation as featureFileOperation } from './api/fileManager'
import { useFileManagerStore as featureUseFileManagerStore } from './stores/file-manager'
import legacyFileManagerViewSource from '../../views/FileManagerView.vue?raw'
import legacyFileToolbarSource from '../../components/file-manager/FileToolbar.vue?raw'
import legacyFileGridSource from '../../components/file-manager/FileGrid.vue?raw'
import legacyFileListSource from '../../components/file-manager/FileList.vue?raw'
import legacyFileSelectorDialogSource from '../../components/file-manager/FileSelectorDialog.vue?raw'

describe('file manager feature module aliases', () => {
  it('keeps legacy file manager api and store exports mapped to the feature module', () => {
    expect(legacyFileManagerApi).toBe(featureFileManagerApi)
    expect(legacyBrowseFiles).toBe(featureBrowseFiles)
    expect(legacyFileOperation).toBe(featureFileOperation)
    expect(legacyUseFileManagerStore).toBe(featureUseFileManagerStore)
  })

  it('keeps legacy file manager view and component paths mapped to the feature module', () => {
    expect(legacyFileManagerViewSource).toContain('@/features/file-manager/views/FileManagerView.vue')
    expect(legacyFileToolbarSource).toContain('@/features/file-manager/components/FileToolbar.vue')
    expect(legacyFileGridSource).toContain('@/features/file-manager/components/FileGrid.vue')
    expect(legacyFileListSource).toContain('@/features/file-manager/components/FileList.vue')
    expect(legacyFileSelectorDialogSource).toContain('@/features/file-manager/components/FileSelectorDialog.vue')
  })
})
