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
