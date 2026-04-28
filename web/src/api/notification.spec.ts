import { describe, expect, it } from 'vitest'

import { convertFrontendToBackend } from './notification'

describe('notification api contract', () => {
  it('converts serverchan config to backend payload', () => {
    const payload = convertFrontendToBackend({
      channel: 'serverchan',
      serverchan: {
        send_key: 'SCT123',
      },
    })

    expect(payload).toEqual({
      channel_type: 'serverchan',
      channel_name: 'ServerChan',
      config: {
        send_key: 'SCT123',
      },
    })
  })
})
