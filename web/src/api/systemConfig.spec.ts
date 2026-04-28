import { beforeEach, describe, expect, it, vi } from 'vitest'

import api from './index'
import { getSystemConfig, getSystemConfigMetadata, updateSystemConfig } from './systemConfig'

const apiClientMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn()
}))

vi.mock('./index', () => ({
  default: apiClientMocks
}))

vi.mock('@/api/index', () => ({
  default: apiClientMocks
}))

type MockedApi = {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
}

const mockedApi = api as unknown as MockedApi

describe('system config api', () => {
  beforeEach(() => {
    mockedApi.get.mockReset()
    mockedApi.post.mockReset()
  })

  it('loads full system config via generic endpoint', async () => {
    const payload = {
      log_level: 'INFO',
      security: { api_key: '****' }
    }
    mockedApi.get.mockResolvedValue(payload)

    const result = await getSystemConfig()

    expect(mockedApi.get).toHaveBeenCalledWith('/system-config/')
    expect(result).toEqual(payload)
  })

  it('loads system config metadata via metadata endpoint', async () => {
    const payload = {
      schema: { type: 'object', properties: { telegram: { type: 'object' } } },
      sensitive_fields: ['security.api_key'],
      sensitive_fields_status: { 'security.api_key': true }
    }
    mockedApi.get.mockResolvedValue(payload)

    const result = await getSystemConfigMetadata()

    expect(mockedApi.get).toHaveBeenCalledWith('/system-config/metadata')
    expect(result).toEqual(payload)
  })

  it('updates full system config via generic endpoint', async () => {
    const payload = {
      log_level: 'DEBUG'
    }
    mockedApi.post.mockResolvedValue(payload)

    const result = await updateSystemConfig(payload)

    expect(mockedApi.post).toHaveBeenCalledWith('/system-config/', payload)
    expect(result).toEqual(payload)
  })

  it('loads unified ai providers without legacy fallback', async () => {
    const payload = {
      providers: [
        {
          name: 'openai',
          api_key_masked: '***1234',
          configured: true,
          base_url: 'https://api.openai.com/v1',
          model: 'gpt-4o-mini',
          timeout: 30,
          enabled: true,
          priority: 100
        }
      ]
    }
    mockedApi.get.mockResolvedValue(payload)

    const { getAIProviders } = await import('./systemConfig')
    const result = await getAIProviders()

    expect(mockedApi.get).toHaveBeenCalledWith('/system-config/ai-providers')
    expect(result).toEqual(payload)
  })
})
