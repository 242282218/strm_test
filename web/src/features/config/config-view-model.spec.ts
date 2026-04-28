import { describe, expect, it } from 'vitest'

import {
  CONFIG_GROUP_LABELS,
  createDefaultBasicForm,
  createDefaultConfigMetadata,
  createDefaultWebDAVForm,
  getConfiguredSensitiveFieldCount,
  getSchemaGroups,
  parseMultilineList,
  toMultilineText,
} from './config-view-model'

describe('config-view-model', () => {
  it('derives ordered groups and collapses basic settings while filtering legacy ai keys', () => {
    const groups = getSchemaGroups({
      properties: {
        database: { type: 'string' },
        log_level: { type: 'string' },
        exts: { type: 'array' },
        telegram: { type: 'object' },
        webdav: { type: 'object' },
        kimi: { type: 'object' },
        deepseek: { type: 'object' },
        unknown_group: { type: 'object' },
      },
    })

    expect(groups).toEqual([
      { key: 'profile', label: CONFIG_GROUP_LABELS.profile },
      { key: 'basic', label: CONFIG_GROUP_LABELS.basic },
      { key: 'webdav', label: CONFIG_GROUP_LABELS.webdav },
      { key: 'telegram', label: CONFIG_GROUP_LABELS.telegram },
      { key: 'unknown_group', label: 'unknown_group' },
    ])
  })

  it('provides stable defaults for config forms and metadata helpers', () => {
    expect(createDefaultWebDAVForm()).toEqual({
      enabled: false,
      fallback_enabled: true,
      url: 'http://localhost:5244/dav',
      username: '',
      password: '',
      mount_path: '/dav',
      read_only: true,
    })

    expect(createDefaultBasicForm()).toEqual({
      database: 'quark_strm.db',
      log_level: 'INFO',
      log_file: '',
      colored_log: true,
      timeout: 30,
      exts: '.mp4\n.mkv\n.avi\n.mov',
      alt_exts: '.srt\n.ass',
      create_sub_directory: false,
    })

    expect(createDefaultConfigMetadata()).toEqual({
      schema: {},
      sensitive_fields: [],
      sensitive_fields_status: {},
    })

    expect(getConfiguredSensitiveFieldCount({ a: true, b: false, c: true })).toBe(2)
  })

  it('converts multiline lists consistently in both directions', () => {
    expect(toMultilineText(['a', 'b', 'c'], 'fallback')).toBe('a\nb\nc')
    expect(toMultilineText('not-an-array', 'fallback')).toBe('fallback')
    expect(parseMultilineList('  a\n\n b \n')).toEqual(['a', 'b'])
  })
})
