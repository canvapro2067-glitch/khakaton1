import { useEffect, useRef, useState } from 'react'
import { loadYandexMaps, routeLine, stopHtml } from './yandexMaps'

type Props = {
  data: any
  selectedVehicle?: number | null
  yandexKey?: string
  filter?: string
  /** Меньше элементов управления — для кабинета водителя, не перекрывает кнопки. */
  variant?: 'default' | 'driver'
  showTraffic?: boolean
}

function destroyMap(engine: 'yandex' | 'osm' | null, map: any, el: HTMLDivElement | null) {
  if (!map) return
  try {
    if (engine === 'yandex') map.destroy()
    else map.remove()
  } catch {
    /* already gone */
  }
  if (el) el.innerHTML = ''
}

function matchFilter(_o: any, assigned: any, filter?: string) {
  if (!filter || filter === 'all') return true
  if (filter === 'unassigned') return !assigned
  const st = assigned?.status || 'pending'
  if (filter === 'done') return st === 'done'
  if (filter === 'pending') return st !== 'done'
  if (filter === 'problem') return st === 'problem'
  return true
}

function paintLeaflet(map: any, data: any, selectedVehicle?: number | null, filter?: string) {
  map.eachLayer((layer: any) => {
    if (layer instanceof L.TileLayer) return
    map.removeLayer(layer)
  })
  const depot = data.depot
  const depotIcon = L.divIcon({
    className: '',
    html: `<div style="background:#0b6e8f;color:#fff;border-radius:8px;padding:4px 8px;font:12px Manrope;box-shadow:0 2px 8px #0003">Склад</div>`,
    iconSize: [70, 24],
  })
  L.marker([depot.lat, depot.lon], { icon: depotIcon }).bindPopup(`<b>${depot.name}</b><br/>${depot.address}`).addTo(map)

  for (const g of data.restrictions_geometry || []) {
    L.polyline(g.path, { color: '#d94841', weight: 6, opacity: 0.45, dashArray: '6 8' })
      .bindPopup(`Запрет для машин > 1,5 т: ${g.street}`)
      .addTo(map)
  }

  for (const r of data.routes || []) {
    const dim = selectedVehicle && r.vehicle?.id !== selectedVehicle
    const color = r.vehicle?.color || '#228be6'
    L.polyline(routeLine(depot, r), { color, weight: dim ? 2 : 5, opacity: dim ? 0.18 : 0.9 }).addTo(map)
  }

  for (const o of data.orders || []) {
    if (!o.lat) continue
    const assigned = o.assignment
    if (selectedVehicle && assigned?.vehicle?.id !== selectedVehicle) continue
    if (!matchFilter(o, assigned, filter)) continue
    const color = assigned?.vehicle?.color || '#868e96'
    L.circleMarker([o.lat, o.lon], {
      radius: o.restricted_historic ? 8 : 6,
      color: o.restricted_historic ? '#d94841' : color,
      fillColor: color,
      fillOpacity: 0.9,
      weight: 2,
    })
      .bindPopup(stopHtml(o, assigned))
      .addTo(map)
  }
  for (const p of data.driver_positions || []) {
    if (p.lat == null || p.lon == null) continue
    L.circleMarker([p.lat, p.lon], { radius: 8, color: '#ff8b1f', fillColor: '#ff8b1f', fillOpacity: 0.95, weight: 2 })
      .bindPopup(`<b>${p.name || 'Авто'}</b>`)
      .addTo(map)
  }
}

function paintYandex(map: any, data: any, selectedVehicle?: number | null, filter?: string) {
  map.geoObjects.removeAll()
  const depot = data.depot
  map.geoObjects.add(
    new ymaps.Placemark(
      [depot.lat, depot.lon],
      { balloonContent: `<b>${depot.name}</b><br/>${depot.address}`, iconCaption: 'Склад' },
      { preset: 'islands#blueStretchyIcon', iconColor: '#0b6e8f' },
    ),
  )

  for (const g of data.restrictions_geometry || []) {
    map.geoObjects.add(
      new ymaps.Polyline(
        g.path,
        { balloonContent: `Запрет для машин > 1,5 т: ${g.street}` },
        { strokeColor: '#d94841', strokeWidth: 6, strokeOpacity: 0.45, strokeStyle: 'dash' },
      ),
    )
  }

  for (const r of data.routes || []) {
    const dim = selectedVehicle && r.vehicle?.id !== selectedVehicle
    const color = r.vehicle?.color || '#228be6'
    map.geoObjects.add(
      new ymaps.Polyline(routeLine(depot, r), {}, { strokeColor: color, strokeWidth: dim ? 2 : 5, strokeOpacity: dim ? 0.2 : 0.92 }),
    )
  }

  for (const o of data.orders || []) {
    if (!o.lat) continue
    const assigned = o.assignment
    if (selectedVehicle && assigned?.vehicle?.id !== selectedVehicle) continue
    if (!matchFilter(o, assigned, filter)) continue
    const color = assigned?.vehicle?.color || '#868e96'
    const seq = assigned?.seq
    map.geoObjects.add(
      new ymaps.Placemark(
        [o.lat, o.lon],
        { balloonContent: stopHtml(o, assigned), iconCaption: seq ? String(seq) : '' },
        {
          preset: o.restricted_historic ? 'islands#dotIcon' : 'islands#circleDotIcon',
          iconColor: color,
        },
      ),
    )
  }
  for (const p of data.driver_positions || []) {
    if (p.lat == null || p.lon == null) continue
    map.geoObjects.add(
      new ymaps.Placemark(
        [p.lat, p.lon],
        { balloonContent: `<b>${p.name || 'Авто'}</b>`, iconCaption: p.name || 'GPS' },
        { preset: 'islands#orangeAutoIcon' },
      ),
    )
  }
}

export default function MapBoard({ data, selectedVehicle, yandexKey, filter, variant = 'default', showTraffic = true }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const mapRef = useRef<any>(null)
  const engineRef = useRef<'yandex' | 'osm' | null>(null)
  const [engine, setEngine] = useState<'yandex' | 'osm' | null>(null)
  const lat = data?.depot?.lat
  const lon = data?.depot?.lon

  useEffect(() => {
    if (!ref.current || lat == null || lon == null) return
    const el = ref.current
    let cancelled = false

    destroyMap(engineRef.current, mapRef.current, el)
    mapRef.current = null
    engineRef.current = null
    setEngine(null)

    async function boot() {
      if (yandexKey) {
        try {
          await loadYandexMaps(yandexKey)
          if (cancelled || !ref.current) return
          const map = new ymaps.Map(
            ref.current,
            {
              center: [lat, lon],
              zoom: 12,
              controls:
                variant === 'driver'
                  ? ['zoomControl', ...(showTraffic ? ['trafficControl'] : [])]
                  : ['zoomControl', 'fullscreenControl', 'typeSelector', 'trafficControl'],
            },
            { yandexMapDisablePoiInteractivity: false },
          )
          if (showTraffic) {
            try {
              const traffic = new ymaps.traffic.provider.Actual({}, { infoLayerShown: true })
              traffic.setMap(map)
            } catch {
              const ctrl = map.controls.get('trafficControl')
              if (ctrl?.showTraffic) ctrl.showTraffic()
            }
          }
          mapRef.current = map
          engineRef.current = 'yandex'
          setEngine('yandex')
          return
        } catch {
          /* OSM fallback */
        }
      }
      if (cancelled || !ref.current) return
      const map = L.map(ref.current).setView([lat, lon], 12)
      map.attributionControl.setPrefix('<a href="https://leafletjs.com" title="Leaflet">Leaflet</a>')
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap · для Яндекс.Карт нужен ключ в .env',
      }).addTo(map)
      mapRef.current = map
      engineRef.current = 'osm'
      setEngine('osm')
    }

    boot()
    return () => {
      cancelled = true
      destroyMap(engineRef.current, mapRef.current, el)
      mapRef.current = null
      engineRef.current = null
    }
  }, [yandexKey, lat, lon, variant, showTraffic])

  useEffect(() => {
    if (!engine || !mapRef.current || !data) return
    if (engine === 'yandex') paintYandex(mapRef.current, data, selectedVehicle, filter)
    else paintLeaflet(mapRef.current, data, selectedVehicle, filter)
  }, [engine, data, selectedVehicle, filter])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !engine) return
    const tick = () => {
      try {
        if (engine === 'osm' && map.invalidateSize) map.invalidateSize()
        else if (engine === 'yandex' && map.container?.fitToViewport) map.container.fitToViewport()
      } catch {
        /* ignore */
      }
    }
    const t = window.setTimeout(tick, 200)
    window.addEventListener('resize', tick)
    window.addEventListener('orientationchange', tick)
    return () => {
      window.clearTimeout(t)
      window.removeEventListener('resize', tick)
      window.removeEventListener('orientationchange', tick)
    }
  }, [engine])

  const caption =
    engine === 'yandex'
      ? 'Яндекс.Карты · рейсы по дорогам (порядок точек из VRP)'
      : engine === 'osm'
        ? yandexKey
          ? 'OpenStreetMap · Яндекс.Карты не загрузились, проверьте ключ и домен localhost'
          : 'OpenStreetMap · добавьте YANDEX_MAPS_API_KEY в .env и перезапустите API'
        : yandexKey
          ? 'Загрузка Яндекс.Карт…'
          : 'Загрузка карты…'

  return (
    <div className={`map-wrap${variant === 'driver' ? ' map-wrap-driver' : ''}`}>
      <div className="map" ref={ref} />
      <p className="map-caption muted">{caption}</p>
    </div>
  )
}
