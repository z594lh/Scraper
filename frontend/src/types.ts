export type FieldType =
  | 'text'
  | 'number'
  | 'switch'
  | 'range'
  | 'select'
  | 'tags'

export interface ConfigField {
  key: string
  label: string
  type: FieldType
  required?: boolean
  help?: string
  placeholder?: string
  options?: { label: string; value: string | number }[]
}

export interface ConfigGroup {
  group: string
  items: ConfigField[]
}

export type ColumnType = 'code' | 'price' | 'text' | 'tags' | 'datetime' | 'link'

export interface SiteColumn {
  key: string
  title: string
  width?: number
  type?: ColumnType
  ellipsis?: boolean
  sortable?: boolean
}

export interface Site {
  code: string
  label: string
  description: string
  table: string
  defaultConfig: Record<string, unknown>
  configSchema: ConfigGroup[]
  columns: SiteColumn[]
}

export interface SiteOptions {
  code: string
  categories: { category: string; options: string[] }[]
  updatedAt: string | null
}

export type ItemRow = Record<string, unknown> & {
  goodsNo: string
  isNew?: boolean
  active?: boolean
}

export interface ItemsPayload {
  site: string
  table: string
  columns: SiteColumn[]
  items: ItemRow[]
}

export interface Run {
  id: number
  status: 'running' | 'success' | 'failed'
  trigger: string
  startedAt: string
  finishedAt: string | null
  duration: number | null
  total: number
  newCount: number
  message: string
  filters: string[]
  log: string
}

export interface LoginState {
  state: 'idle' | 'running' | 'success' | 'failed'
  message: string
  startedAt?: string
  finishedAt?: string
}

export interface NotifyRules {
  newItems: { enabled: boolean; threshold: number }
  runFailed: { enabled: boolean }
  runFinished: { enabled: boolean }
}

export interface Project {
  id: number
  slug: string
  name: string
  site: string
  siteLabel: string
  table: string
  enabled: boolean
  config: Record<string, unknown>
  scheduleMinutes: number
  pauseUntil?: string | null
  notifyChannels: string[]
  notifyRules: NotifyRules
  createdAt: string
  updatedAt: string
  itemCount: number
  newCount: number
  running: boolean
  lastRun: Run | null
  login: LoginState
  siteSpec?: Site
}

export interface Overview {
  projects: Project[]
  recentItems: ItemRow[]
  totals: { projects: number; items: number; newItems: number }
}

export interface NotifySettings {
  envFile: string
  notifyEnabled: boolean
  schedulerEnabled: boolean
  dingtalk: { configured: boolean; masked: string }
  dingtalkSecret: { configured: boolean; masked: string }
  wecom: { configured: boolean; masked: string }
  pzdsChrome: string
}

export interface SystemInfo {
  python: string
  platform: string
  root: string
  projectsDir: string
  database: string
  chrome: string
  frontendBuilt: boolean
  envFile: string
}
