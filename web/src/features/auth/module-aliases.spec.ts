import { describe, expect, it } from 'vitest'

import legacyLoginViewSource from '../../views/LoginView.vue?raw'

describe('auth feature module aliases', () => {
  it('keeps the legacy login view path mapped to the feature module', () => {
    expect(legacyLoginViewSource).toContain('@/features/auth/views/LoginView.vue')
  })
})
