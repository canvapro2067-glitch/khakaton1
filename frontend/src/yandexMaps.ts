import { statusLabel } from './statusLabels'

let pending: Promise<any> | null = null
let loadedKey = ''

/** Load Yandex Maps JS API 2.1 once. Coordinates stay [lat, lon] like Leaflet. */
export function loadYandexMaps(apiKey: string): Promise<any> {
  if (typeof ymaps !== 'undefined' && loadedKey === apiKey) {
    return new Promise((resolve) => ymaps.ready(() => resolve(ymaps)))
  }
  if (pending && loadedKey === apiKey) return pending
  loadedKey = apiKey
  pending = new Promise((resolve, reject) => {
    const prev = document.getElementById('yandex-maps-sdk')
    if (prev) prev.remove()
    const script = document.createElement('script')
    script.id = 'yandex-maps-sdk'
    script.src = `https://api-maps.yandex.ru/2.1/?apikey=${encodeURIComponent(apiKey)}&lang=ru_RU&coordorder=latlong`
    script.async = true
    script.onload = () => {
      if (typeof ymaps === 'undefined') {
        pending = null
        reject(new Error('Яндекс.Карты не инициализировались'))
        return
      }
      ymaps.ready(() => resolve(ymaps))
    }
    script.onerror = () => {
      pending = null
      reject(new Error('Не удалось загрузить скрипт Яндекс.Карт'))
    }
    document.head.appendChild(script)
  })
  return pending
}

const GRODNO_BOUNDS: number[][] = [
  [53.58, 23.68],
  [53.78, 23.96],
]

export async function geocodeInGrodno(address: string): Promise<[number, number] | null> {
  if (typeof ymaps === 'undefined' || !address?.trim()) return null
  const query = /гродно/i.test(address) ? address.trim() : `Беларусь, Гродно, ${address.trim()}`
  try {
    const res = await ymaps.geocode(query, {
      boundedBy: GRODNO_BOUNDS,
      strictBounds: true,
      results: 1,
    })
    const obj = res.geoObjects.get(0)
    if (!obj) return null
    const c = obj.geometry.getCoordinates()
    const lat = Number(c[0])
    const lon = Number(c[1])
    if (lat < 53.58 || lat > 53.78 || lon < 23.68 || lon > 23.96) return null
    return [lat, lon]
  } catch {
    return null
  }
}

export async function geocodeAddresses(
  addresses: string[],
  onProgress?: (done: number, total: number) => void,
): Promise<Map<string, [number, number]>> {
  const out = new Map<string, [number, number]>()
  const unique = [...new Set(addresses.map((a) => a.trim()).filter(Boolean))]
  let done = 0
  for (const addr of unique) {
    const pt = await geocodeInGrodno(addr)
    if (pt) out.set(addr, pt)
    done += 1
    onProgress?.(done, unique.length)
  }
  return out
}

export function stopHtml(o: any, assigned: any) {
  return `<b>${o.name}</b><br/>${o.address}<br/>Вес: ${o.weight_kg} кг
    ${assigned ? `<br/>Авто: ${assigned.vehicle.plate}<br/>ETA: ${assigned.eta}<br/>Статус: ${statusLabel(assigned.status)}` : '<br/>Не назначен'}
    ${o.preferred_time ? `<br/>Окно (предпочт.): ${o.preferred_time}` : ''}`
}

export function routePoints(depot: any, route: any): number[][] {
  const pts: number[][] = [[depot.lat, depot.lon]]
  for (const s of route.stops || []) {
    if (s.order?.lat) pts.push([s.order.lat, s.order.lon])
  }
  pts.push([depot.lat, depot.lon])
  return pts
}

/** Линия маршрута: по дорогам (если посчитана на бэкенде), иначе прямые отрезки VRP. */
export function routeLine(depot: any, route: any): number[][] {
  const g = route?.geometry
  if (Array.isArray(g) && g.length >= 2) return g
  return routePoints(depot, route)
}
