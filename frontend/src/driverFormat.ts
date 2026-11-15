export function fmtDriverTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('ru-BY', {
    timeZone: 'Europe/Minsk',
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function fmtMinutes(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0) return '—'
  const m = Math.max(1, Math.round(seconds / 60))
  return `${m} мин`
}

export function fmtKm(m: number | null | undefined): string {
  if (m == null || Number.isNaN(m)) return '—'
  return `${(m / 1000).toFixed(1)} км`
}

export function fmtTravel(s: number | null | undefined): string {
  if (s == null || s < 0) return '—'
  const min = Math.max(1, Math.round(s / 60))
  if (min < 60) return `${min} мин`
  return `${Math.floor(min / 60)} ч ${min % 60} мин`
}

export function naviTo(lat?: number | null, lon?: number | null, address?: string) {
  const addr = encodeURIComponent(address || '')
  if (lat != null && lon != null) {
    window.location.href = `yandexnavi://build_route_on_map?lat_to=${lat}&lon_to=${lon}`
    setTimeout(() => window.open(`https://yandex.ru/maps/?rtext=~${lat},${lon}&rtt=auto`, '_blank', 'noopener,noreferrer'), 600)
  } else if (addr) {
    window.open(`https://yandex.ru/maps/?text=${addr}`, '_blank', 'noopener,noreferrer')
  }
}

export const PROBLEM_REASONS = [
  'Магазин закрыт',
  'Не принимают товар',
  'Нет возможности подъехать',
  'Проблема с разгрузкой',
  'Поломка автомобиля',
  'ДТП',
  'Сильная пробка',
  'Недостаточное количество товара',
  'Другая проблема',
]

export function yandexDayRoute(depot: { lat: number; lon: number }, stops: { lat?: number; lon?: number }[]): string {
  const pts: string[] = []
  pts.push(`${depot.lat},${depot.lon}`)
  for (const s of stops) {
    if (s.lat != null && s.lon != null) pts.push(`${s.lat},${s.lon}`)
  }
  pts.push(`${depot.lat},${depot.lon}`)
  return `https://yandex.ru/maps/?rtext=${pts.join('~')}&rtt=auto`
}