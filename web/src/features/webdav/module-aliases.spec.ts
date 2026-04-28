import { describe, expect, it } from 'vitest'

import legacyWebDavViewSource from '../../views/WebDAVView.vue?raw'

describe('webdav feature module aliases', () => {
  it('keeps the legacy webdav view path mapped to the feature module', () => {
    expect(legacyWebDavViewSource).toContain('@/features/webdav/views/WebDAVView.vue')
  })
})
