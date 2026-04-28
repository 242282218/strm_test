import { describe, expect, it } from 'vitest'

import legacyLayoutViewSource from '../../views/LayoutView.vue?raw'
import legacyNotFoundViewSource from '../../views/NotFoundView.vue?raw'

describe('app shell feature module aliases', () => {
  it('keeps legacy shell view paths mapped to the feature module', () => {
    expect(legacyLayoutViewSource).toContain('@/features/app-shell/views/LayoutView.vue')
    expect(legacyNotFoundViewSource).toContain('@/features/app-shell/views/NotFoundView.vue')
  })
})
