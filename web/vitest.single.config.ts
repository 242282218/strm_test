import baseConfig from './vitest.config'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  ...baseConfig,
  test: {
    ...baseConfig.test,
    isolate: false,
    fileParallelism: false,
    include: ['src/smoke.spec.ts'],
  },
})
