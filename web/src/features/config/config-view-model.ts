import type { SystemConfigMetadataResponse } from '@/features/config/api/systemConfig'

export interface WebDAVForm {
  enabled: boolean
  fallback_enabled: boolean
  url: string
  username: string
  password: string
  mount_path: string
  read_only: boolean
}

export interface QuarkForm {
  cookie: string
  referer: string
  root_id: string
  only_video: boolean
}

export interface SecurityForm {
  api_key: string
  require_api_key: boolean
}

export interface AListForm {
  enabled: boolean
  url: string
  token: string
  mount_path: string
}

export interface TmdbForm {
  api_key: string
}

export interface LogForm {
  format: 'text' | 'json'
  include_timestamp: boolean
  include_level: boolean
  include_request_id: boolean
  include_source: boolean
  json_indent: string
}

export interface CorsForm {
  allow_origins: string
  allow_credentials: boolean
  allow_methods: string
  allow_headers: string
}

export interface TelegramForm {
  enabled: boolean
  bot_token: string
  chat_id: string
  proxy: string
  events: string
}

export interface BasicForm {
  database: string
  log_level: string
  log_file: string
  colored_log: boolean
  timeout: number
  exts: string
  alt_exts: string
  create_sub_directory: boolean
}

export interface WeChatForm {
  enabled: boolean
  provider: string
  send_key: string
}

export interface ConfigGroupItem {
  key: string
  label: string
}

export const DEFAULT_ENDPOINTS_FORM_JSON = '[]'
export const PROFILE_GROUP_KEY = 'profile'

export const CONFIG_GROUP_LABELS: Record<string, string> = {
  profile: '个人中心',
  basic: '基础设置',
  telegram: 'Telegram 通知',
  wechat: '微信通知',
  webdav: 'WebDAV 配置',
  security: '安全设置',
  alist: 'AList 配置',
  emby: 'Emby 配置',
  quark: '夸克配置',
  tmdb: 'TMDB 配置',
  cors: '跨域设置',
  log: '日志配置',
  ai: 'AI 配置',
  endpoints: '端点映射',
}

export const CONFIG_GROUP_ORDER: string[] = [
  'profile',
  'basic',
  'emby',
  'quark',
  'ai',
  'tmdb',
  'webdav',
  'alist',
  'telegram',
  'wechat',
  'security',
  'cors',
  'log',
  'endpoints',
]

const BASIC_GROUP_KEYS = ['database', 'log_level', 'log_file', 'colored_log', 'timeout', 'exts', 'alt_exts', 'create_sub_directory']
const LEGACY_AI_GROUP_KEYS = ['api_keys', 'zhipu', 'deepseek', 'glm', 'kimi']

export const isRecord = (value: unknown): value is Record<string, unknown> => {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

export const createDefaultWebDAVForm = (): WebDAVForm => ({
  enabled: false,
  fallback_enabled: true,
  url: 'http://localhost:5244/dav',
  username: '',
  password: '',
  mount_path: '/dav',
  read_only: true,
})

export const createDefaultQuarkForm = (): QuarkForm => ({
  cookie: '',
  referer: 'https://pan.quark.cn/',
  root_id: '0',
  only_video: true,
})

export const createDefaultSecurityForm = (): SecurityForm => ({
  api_key: '',
  require_api_key: true,
})

export const createDefaultAListForm = (): AListForm => ({
  enabled: false,
  url: 'http://localhost:5244',
  token: '',
  mount_path: '/',
})

export const createDefaultTmdbForm = (): TmdbForm => ({
  api_key: '',
})

export const createDefaultLogForm = (): LogForm => ({
  format: 'text',
  include_timestamp: true,
  include_level: true,
  include_request_id: true,
  include_source: true,
  json_indent: '',
})

export const createDefaultCorsForm = (): CorsForm => ({
  allow_origins: '*',
  allow_credentials: false,
  allow_methods: '*',
  allow_headers: '*',
})

export const createDefaultTelegramForm = (): TelegramForm => ({
  enabled: false,
  bot_token: '',
  chat_id: '',
  proxy: '',
  events: 'task_completed\ntask_failed',
})

export const createDefaultBasicForm = (): BasicForm => ({
  database: 'quark_strm.db',
  log_level: 'INFO',
  log_file: '',
  colored_log: true,
  timeout: 30,
  exts: '.mp4\n.mkv\n.avi\n.mov',
  alt_exts: '.srt\n.ass',
  create_sub_directory: false,
})

export const createDefaultWeChatForm = (): WeChatForm => ({
  enabled: false,
  provider: 'serverchan',
  send_key: '',
})

export const toMultilineText = (value: unknown, fallback: string): string => {
  if (Array.isArray(value) && value.every(item => typeof item === 'string')) {
    return value.join('\n')
  }
  return fallback
}

export const parseMultilineList = (value: string): string[] => {
  return value
    .split('\n')
    .map(item => item.trim())
    .filter(Boolean)
}

export const createDefaultConfigMetadata = (): SystemConfigMetadataResponse => ({
  schema: {},
  sensitive_fields: [],
  sensitive_fields_status: {},
})

export const getConfiguredSensitiveFieldCount = (status: Record<string, boolean>): number => {
  return Object.values(status).filter(Boolean).length
}

export const getSchemaGroups = (schema: Record<string, unknown>): ConfigGroupItem[] => {
  const keys = new Set<string>([PROFILE_GROUP_KEY])
  const properties = schema.properties

  if (isRecord(properties)) {
    Object.keys(properties).forEach(key => keys.add(key))
  }

  if (BASIC_GROUP_KEYS.some(key => keys.has(key))) {
    BASIC_GROUP_KEYS.forEach(key => keys.delete(key))
    keys.add('basic')
  }

  LEGACY_AI_GROUP_KEYS.forEach(key => keys.delete(key))

  const groupKeys = Array.from(keys)
  const knownGroups = CONFIG_GROUP_ORDER.filter(key => groupKeys.includes(key)).map(key => ({
    key,
    label: CONFIG_GROUP_LABELS[key] ?? key,
  }))
  const unknownGroups = groupKeys
    .filter(key => !CONFIG_GROUP_ORDER.includes(key))
    .sort((a, b) => a.localeCompare(b))
    .map(key => ({
      key,
      label: CONFIG_GROUP_LABELS[key] ?? key,
    }))

  return [...knownGroups, ...unknownGroups]
}

export interface ConfigFormState {
  webdavForm: WebDAVForm
  quarkForm: QuarkForm
  securityForm: SecurityForm
  alistForm: AListForm
  tmdbForm: TmdbForm
  logForm: LogForm
  corsForm: CorsForm
  telegramForm: TelegramForm
  basicForm: BasicForm
  wechatForm: WeChatForm
}

export const resetConfigForms = (forms: ConfigFormState): void => {
  Object.assign(forms.webdavForm, createDefaultWebDAVForm())
  Object.assign(forms.quarkForm, createDefaultQuarkForm())
  Object.assign(forms.securityForm, createDefaultSecurityForm())
  Object.assign(forms.alistForm, createDefaultAListForm())
  Object.assign(forms.tmdbForm, createDefaultTmdbForm())
  Object.assign(forms.logForm, createDefaultLogForm())
  Object.assign(forms.corsForm, createDefaultCorsForm())
  Object.assign(forms.telegramForm, createDefaultTelegramForm())
  Object.assign(forms.basicForm, createDefaultBasicForm())
  Object.assign(forms.wechatForm, createDefaultWeChatForm())
}

export const hydrateConfigForms = (config: Record<string, unknown>, forms: ConfigFormState): string => {
  resetConfigForms(forms)

  forms.basicForm.database = typeof config.database === 'string' && config.database ? config.database : 'quark_strm.db'
  forms.basicForm.log_level = typeof config.log_level === 'string' && config.log_level ? config.log_level : 'INFO'
  forms.basicForm.log_file = typeof config.log_file === 'string' ? config.log_file : ''
  forms.basicForm.colored_log = config.colored_log !== false
  forms.basicForm.timeout = typeof config.timeout === 'number' ? config.timeout : 30
  forms.basicForm.exts = toMultilineText(config.exts, '.mp4\n.mkv\n.avi\n.mov')
  forms.basicForm.alt_exts = toMultilineText(config.alt_exts, '.srt\n.ass')
  forms.basicForm.create_sub_directory = Boolean(config.create_sub_directory)

  const webdav = config.webdav
  if (isRecord(webdav)) {
    forms.webdavForm.enabled = Boolean(webdav.enabled)
    forms.webdavForm.fallback_enabled = webdav.fallback_enabled !== false
    forms.webdavForm.url = typeof webdav.url === 'string' && webdav.url ? webdav.url : 'http://localhost:5244/dav'
    forms.webdavForm.username = typeof webdav.username === 'string' ? webdav.username : ''
    forms.webdavForm.password = typeof webdav.password === 'string' ? webdav.password : ''
    forms.webdavForm.mount_path = typeof webdav.mount_path === 'string' && webdav.mount_path ? webdav.mount_path : '/dav'
    forms.webdavForm.read_only = webdav.read_only !== false
  }

  const quark = config.quark
  if (isRecord(quark)) {
    forms.quarkForm.cookie = typeof quark.cookie === 'string' ? quark.cookie : ''
    forms.quarkForm.referer = typeof quark.referer === 'string' && quark.referer ? quark.referer : 'https://pan.quark.cn/'
    forms.quarkForm.root_id = typeof quark.root_id === 'string' && quark.root_id ? quark.root_id : '0'
    forms.quarkForm.only_video = quark.only_video !== false
  }

  const security = config.security
  if (isRecord(security)) {
    forms.securityForm.api_key = typeof security.api_key === 'string' ? security.api_key : ''
    forms.securityForm.require_api_key = security.require_api_key !== false
  }

  const alist = config.alist
  if (isRecord(alist)) {
    forms.alistForm.enabled = Boolean(alist.enabled)
    forms.alistForm.url = typeof alist.url === 'string' && alist.url ? alist.url : 'http://localhost:5244'
    forms.alistForm.token = typeof alist.token === 'string' ? alist.token : ''
    forms.alistForm.mount_path = typeof alist.mount_path === 'string' && alist.mount_path ? alist.mount_path : '/'
  }

  const tmdb = config.tmdb
  if (isRecord(tmdb)) {
    forms.tmdbForm.api_key = typeof tmdb.api_key === 'string' ? tmdb.api_key : ''
  }

  const log = config.log
  if (isRecord(log)) {
    forms.logForm.format = log.format === 'json' ? 'json' : 'text'
    forms.logForm.include_timestamp = log.include_timestamp !== false
    forms.logForm.include_level = log.include_level !== false
    forms.logForm.include_request_id = log.include_request_id !== false
    forms.logForm.include_source = log.include_source !== false
    forms.logForm.json_indent = typeof log.json_indent === 'number' ? String(log.json_indent) : ''
  }

  const cors = config.cors
  if (isRecord(cors)) {
    forms.corsForm.allow_origins = toMultilineText(cors.allow_origins, '*')
    forms.corsForm.allow_credentials = Boolean(cors.allow_credentials)
    forms.corsForm.allow_methods = toMultilineText(cors.allow_methods, '*')
    forms.corsForm.allow_headers = toMultilineText(cors.allow_headers, '*')
  }

  const telegram = config.telegram
  if (isRecord(telegram)) {
    forms.telegramForm.enabled = Boolean(telegram.enabled)
    forms.telegramForm.bot_token = typeof telegram.bot_token === 'string' ? telegram.bot_token : ''
    forms.telegramForm.chat_id = typeof telegram.chat_id === 'string' ? telegram.chat_id : ''
    forms.telegramForm.proxy = typeof telegram.proxy === 'string' ? telegram.proxy : ''
    forms.telegramForm.events = toMultilineText(telegram.events, 'task_completed\ntask_failed')
  }

  const wechat = config.wechat
  if (isRecord(wechat)) {
    forms.wechatForm.enabled = Boolean(wechat.enabled)
    forms.wechatForm.provider = typeof wechat.provider === 'string' && wechat.provider ? wechat.provider : 'serverchan'
    forms.wechatForm.send_key = typeof wechat.send_key === 'string' ? wechat.send_key : ''
  }

  return JSON.stringify(Array.isArray(config.endpoints) ? config.endpoints : [], null, 2)
}

export const buildSystemConfigPayload = (
  basePayload: Record<string, unknown>,
  forms: ConfigFormState,
  parsedEndpoints: unknown[],
): Record<string, unknown> => {
  return {
    ...basePayload,
    database: forms.basicForm.database,
    log_level: forms.basicForm.log_level,
    log_file: forms.basicForm.log_file.trim() || null,
    colored_log: forms.basicForm.colored_log,
    timeout: forms.basicForm.timeout,
    exts: parseMultilineList(forms.basicForm.exts),
    alt_exts: parseMultilineList(forms.basicForm.alt_exts),
    create_sub_directory: forms.basicForm.create_sub_directory,
    webdav: {
      enabled: forms.webdavForm.enabled,
      fallback_enabled: forms.webdavForm.fallback_enabled,
      url: forms.webdavForm.url,
      username: forms.webdavForm.username,
      password: forms.webdavForm.password,
      mount_path: forms.webdavForm.mount_path,
      read_only: forms.webdavForm.read_only,
    },
    quark: {
      cookie: forms.quarkForm.cookie,
      referer: forms.quarkForm.referer,
      root_id: forms.quarkForm.root_id,
      only_video: forms.quarkForm.only_video,
    },
    security: {
      api_key: forms.securityForm.api_key,
      require_api_key: forms.securityForm.require_api_key,
    },
    alist: {
      enabled: forms.alistForm.enabled,
      url: forms.alistForm.url,
      token: forms.alistForm.token,
      mount_path: forms.alistForm.mount_path,
    },
    tmdb: {
      api_key: forms.tmdbForm.api_key,
    },
    log: {
      format: forms.logForm.format,
      include_timestamp: forms.logForm.include_timestamp,
      include_level: forms.logForm.include_level,
      include_request_id: forms.logForm.include_request_id,
      include_source: forms.logForm.include_source,
      json_indent: forms.logForm.json_indent.trim() ? Number(forms.logForm.json_indent.trim()) : null,
    },
    cors: {
      allow_origins: parseMultilineList(forms.corsForm.allow_origins),
      allow_credentials: forms.corsForm.allow_credentials,
      allow_methods: parseMultilineList(forms.corsForm.allow_methods),
      allow_headers: parseMultilineList(forms.corsForm.allow_headers),
    },
    telegram: {
      enabled: forms.telegramForm.enabled,
      bot_token: forms.telegramForm.bot_token,
      chat_id: forms.telegramForm.chat_id,
      proxy: forms.telegramForm.proxy,
      events: parseMultilineList(forms.telegramForm.events),
    },
    wechat: {
      enabled: forms.wechatForm.enabled,
      provider: forms.wechatForm.provider,
      send_key: forms.wechatForm.send_key,
    },
    endpoints: parsedEndpoints,
  }
}
