// @vitest-environment node
import { describe, expect, it } from 'vitest'
import type { ConfigEnv, UserConfig } from 'vite'

import viteConfig from '../vite.config'

describe('vite development proxy', () => {
  it('proxies /dav to the backend webdav entry in development', () => {
    const config = (viteConfig as (env: ConfigEnv) => UserConfig)({
      command: 'serve',
      mode: 'development',
    })

    const proxy = config.server?.proxy
    const davProxy = proxy && !Array.isArray(proxy) ? proxy['/dav'] : undefined

    expect(davProxy).toMatchObject({
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    })
  })
})
