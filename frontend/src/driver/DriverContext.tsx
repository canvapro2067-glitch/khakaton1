import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, cacheDriverPack, flushOfflineQueue, loadCachedDriverPack, pendingSyncCount } from '../api'

type Ctx = {
  pack: any
  cfg: any
  busy: boolean
  err: string
  offline: boolean
  pending: number
  tabNotes: any[]
  load: () => Promise<void>
  act: (path: string, body?: Record<string, unknown>) => Promise<any>
  setErr: (s: string) => void
  gps: { lat: number; lon: number } | null
}

const C = createContext<Ctx | null>(null)

export function useDriver() {
  const v = useContext(C)
  if (!v) throw new Error('useDriver')
  return v
}

export function flattenStops(pack: any) {
  const trips: any[] = pack?.routes?.length ? pack.routes : pack?.route ? [pack.route] : []
  return trips.flatMap((t: any) => (t.stops || []).map((s: any) => ({ ...s, tripId: t.id })))
}

export function currentStop(stops: any[]) {
  return stops.find((s) => s.status !== 'done' && s.status !== 'problem')
}

function withGeo(body: Record<string, unknown> | undefined, gps: { lat: number; lon: number } | null) {
  const b: Record<string, unknown> = { ...(body || {}), at: new Date().toISOString() }
  if (gps) {
    b.lat = gps.lat
    b.lon = gps.lon
  }
  return b
}

export function DriverProvider({ children }: { children: ReactNode }) {
  const [pack, setPack] = useState<any>(loadCachedDriverPack())
  const [cfg, setCfg] = useState<any>({})
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [offline, setOffline] = useState(!navigator.onLine)
  const [pending, setPending] = useState(pendingSyncCount())
  const [tabNotes, setTabNotes] = useState<any[]>([])
  const [gps, setGps] = useState<{ lat: number; lon: number } | null>(null)

  const load = useCallback(async () => {
    try {
      const left = await flushOfflineQueue()
      setPending(left)
      const p = await api('/api/driver/route')
      setPack(p)
      cacheDriverPack(p)
      setOffline(false)
      setErr('')
      const notes = (await api('/api/driver/notifications')) as any[]
      setTabNotes(notes)
    } catch (e: unknown) {
      setOffline(true)
      const cached = loadCachedDriverPack()
      if (cached) setPack(cached)
      else setErr(e instanceof Error ? e.message : 'Нет данных')
    }
  }, [])

  const act = useCallback(
    async (path: string, body?: Record<string, unknown>) => {
      setBusy(true)
      setErr('')
      try {
        const data = await api(path, { method: 'POST', body: JSON.stringify(withGeo(body, gps)) })
        await load()
        return data
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Ошибка'
        setErr(msg)
        setPending(pendingSyncCount())
        throw e
      } finally {
        setBusy(false)
      }
    },
    [gps, load],
  )

  useEffect(() => {
    load()
    api('/api/config').then(setCfg).catch(() => null)
    const t = setInterval(() => load().catch(() => null), 10000)
    const on = () => {
      setOffline(false)
      load()
    }
    const off = () => setOffline(true)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      clearInterval(t)
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [load])

  useEffect(() => {
    const geoOn = pack?.driver?.geo_enabled !== false
    const shift = pack?.driver?.shift_status
    if (!geoOn || shift === 'waiting' || shift === 'finished') return
    if (!navigator.geolocation) return
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const next = { lat: pos.coords.latitude, lon: pos.coords.longitude }
        setGps(next)
        api('/api/driver/geo', { method: 'POST', body: JSON.stringify(next) }).catch(() => null)
      },
      () => null,
      { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 },
    )
    return () => navigator.geolocation.clearWatch(id)
  }, [pack?.driver?.geo_enabled, pack?.driver?.shift_status])

  const value = useMemo(
    () => ({ pack, cfg, busy, err, offline, pending, tabNotes, load, act, setErr, gps }),
    [pack, cfg, busy, err, offline, pending, tabNotes, load, act, gps],
  )
  return <C.Provider value={value}>{children}</C.Provider>
}
