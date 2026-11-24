import type {
  ItemsPayload,
  LoginState,
  NotifySettings,
  Overview,
  Project,
  Run,
  Site,
  SiteOptions,
  SystemInfo,
} from './types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    let detail = `请求失败 (${resp.status})`
    try {
      const data = await resp.json()
      if (data?.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      /* 保留默认错误信息 */
    }
    throw new Error(detail)
  }
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}

export const api = {
  sites: () => request<Site[]>('/sites'),
  siteOptions: (code: string) => request<SiteOptions>(`/sites/${code}/options`),
  overview: () => request<Overview>('/overview'),
  projects: () => request<Project[]>('/projects'),
  project: (id: number) => request<Project>(`/projects/${id}`),
  projectBySlug: async (slug: string) => {
    const list = await request<Project[]>('/projects')
    const found = list.find((item) => item.slug === slug)
    if (!found) throw new Error('项目不存在')
    return found
  },
  createProject: (body: Record<string, unknown>) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(body) }),
  updateProject: (id: number, body: Record<string, unknown>) =>
    request<Project>(`/projects/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteProject: (id: number) => request<void>(`/projects/${id}`, { method: 'DELETE' }),
  runProject: (id: number) =>
    request<{ runId: number; status: string }>(`/projects/${id}/run`, { method: 'POST' }),
  runs: (id: number, limit = 20) => request<Run[]>(`/projects/${id}/runs?limit=${limit}`),
  items: (
    id: number,
    params: { onlyNew?: boolean; q?: string; includeInactive?: boolean } = {},
  ) => {
    const query = new URLSearchParams()
    if (params.onlyNew) query.set('only_new', 'true')
    if (params.includeInactive) query.set('include_inactive', 'true')
    if (params.q) query.set('q', params.q)
    return request<ItemsPayload>(`/projects/${id}/items?${query.toString()}`)
  },
  login: (id: number) =>
    request<LoginState>(`/projects/${id}/login`, { method: 'POST' }),
  loginStatus: (id: number) => request<LoginState>(`/projects/${id}/login`),
  settings: () => request<NotifySettings>('/settings'),
  saveSettings: (body: Record<string, unknown>) =>
    request<NotifySettings>('/settings', { method: 'PUT', body: JSON.stringify(body) }),
  testNotify: (channel: string) =>
    request<{ ok: boolean; message: string }>('/settings/notify/test', {
      method: 'POST',
      body: JSON.stringify({ channel }),
    }),
  system: () => request<SystemInfo>('/settings/system'),
}
