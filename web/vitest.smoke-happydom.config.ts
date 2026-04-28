import baseConfig from './vitest.config'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  ...baseConfig,
  test: {
    ...baseConfig.test,
    environment: 'happy-dom',
    include: ['src/smoke.spec.ts'],
  },
})
