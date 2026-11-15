const TOKEN = 'mm_token'
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || ''

function url(path: string) {
  return API_BASE ? `${API_BASE}${path}` : path
}

export function loginPath() {
  return import.meta.env.VITE_STATIC_HOST === 'tiiny' ? '/#/login' : '/login'
}

export function getToken() {
  return localStorage.getItem(TOKEN) || ''
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN, t)
}
export function clearToken() {
  localStorage.removeItem(TOKEN)
}

const QUEUE = 'mm_offline_q'
const PACK = 'mm_driver_pack'

type Queued = { id: string; path: string; method: string; body?: string; at: string }

export function cacheDriverPack(pack: unknown) {
  try {
    localStorage.setItem(PACK, JSON.stringify({ t: Date.now(), pack }))
  } catch {
    /* quota */
  }
}

export function loadCachedDriverPack(): any | null {
  try {
    const raw = localStorage.getItem(PACK)
    if (!raw) return null
    return JSON.parse(raw).pack
  } catch {
    return null
  }
}

export function pendingSyncCount() {
  return loadQueue().length
}

function loadQueue(): Queued[] {
  try {
    return JSON.parse(localStorage.getItem(QUEUE) || '[]')
  } catch {
    return []
  }
}

function saveQueue(q: Queued[]) {
  localStorage.setItem(QUEUE, JSON.stringify(q))
}

function enqueue(item: Queued) {
  const q = loadQueue()
  if (q.some((x) => x.path === item.path && x.method === item.method && x.body === item.body)) return
  q.push(item)
  saveQueue(q)
}

export async function flushOfflineQueue() {
  const q = loadQueue()
  const left: Queued[] = []
  for (const item of q) {
    try {
      await api(item.path, { method: item.method, body: item.body, headers: { 'X-Offline': '1' } })
    } catch {
      left.push(item)
    }
  }
  saveQueue(left)
  return left.length
}

export async function api(path: string, opts: RequestInit = {}) {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (opts.body && !(opts.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  let res: Response
  try {
    res = await fetch(url(path), { ...opts, headers })
  } catch {
    const method = (opts.method || 'GET').toUpperCase()
    if (method !== 'GET' && method !== 'HEAD') {
      enqueue({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        path,
        method,
        body: typeof opts.body === 'string' ? opts.body : undefined,
        at: new Date().toISOString(),
      })
      throw new Error('Нет сети. Действие сохранено и отправится при появлении связи')
    }
    throw new Error('Нет соединения с сервером')
  }
  if (res.status === 401) {
    clearToken()
    if (!path.includes('/auth/login')) window.location.href = loginPath()
  }
  const text = await res.text()
  let data: unknown = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text }
  }
  if (!res.ok) {
    const d = data as { detail?: string }
    throw new Error(typeof d?.detail === 'string' ? d.detail : res.statusText)
  }
  return data
}
