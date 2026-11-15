import { Navigation } from 'lucide-react'
import { useMemo, useState } from 'react'
import MapBoard from '../MapBoard'
import { naviTo, yandexDayRoute } from '../driverFormat'
import { currentStop, flattenStops, useDriver } from './DriverContext'

function distM(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const dy = (a.lat - b.lat) * 111000
  const dx = (a.lon - b.lon) * 67000
  return Math.hypot(dx, dy)
}

export default function DriverMapTab() {
  const { pack, cfg, gps } = useDriver()
  const [traffic, setTraffic] = useState(true)
  const depot = pack?.depot || cfg.depot
  const v = pack?.vehicle
  const trips: any[] = pack?.routes?.length ? pack.routes : pack?.route ? [pack.route] : []
  const r = pack?.route || trips[0]
  const stops = flattenStops(pack)
  const current = currentStop(stops)

  const mapData = useMemo(() => {
    if (!r || !depot) return null
    return {
      depot,
      routes: trips.length ? trips : [r],
      orders: stops.map((s: any) => ({
        ...s.order,
        assignment: { vehicle: v, eta: s.eta, status: s.status, seq: s.seq },
      })),
      restrictions_geometry: [],
      driver_positions: gps ? [{ lat: gps.lat, lon: gps.lon, name: 'Вы', fresh: true }] : [],
    }
  }, [r, depot, stops, v, trips, gps])

  const offRoute =
    gps && current?.order?.lat != null
      ? distM(gps, { lat: current.order.lat, lon: current.order.lon }) > (current.distance_from_prev_m || 800) * 1.35 + 400
      : false

  function openDay() {
    if (!depot) return
    const pending = stops.filter((s: any) => s.status !== 'done' && s.status !== 'problem')
    window.open(yandexDayRoute(depot, pending.map((s: any) => s.order)), '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="driver-page">
      <h2 style={{ margin: '0 0 8px' }}>Маршрут</h2>
      {!r && <p className="muted">Нет назначенного рейса</p>}
      {offRoute && current && (
        <div className="alert">
          Похоже, вы отклонились от точки. Порядок заказов не меняется.
          <button type="button" className="btn navi" style={{ marginTop: 8 }} onClick={() => naviTo(current.order.lat, current.order.lon, current.order.address)}>
            Построить маршрут в навигаторе
          </button>
        </div>
      )}
      {mapData && (
        <MapBoard data={mapData} yandexKey={cfg.yandex_maps_key} selectedVehicle={v?.id} variant="driver" showTraffic={traffic} />
      )}
      <label className="switch" style={{ marginTop: 10 }}>
        <input type="checkbox" checked={traffic} onChange={(e) => setTraffic(e.target.checked)} />
        Слой пробок (Яндекс)
      </label>
      <p className="muted small">Линия — по дорогам. Карта требует интернет. GPS передаётся при активной смене.</p>
      <div className="row-btns" style={{ marginTop: 10 }}>
        {current && (
          <button type="button" className="btn navi" onClick={() => naviTo(current.order?.lat, current.order?.lon, current.order?.address)}>
            <Navigation size={16} /> К следующей точке
          </button>
        )}
        <button type="button" className="btn ghost" onClick={openDay}>
          Весь день в Яндекс.Картах
        </button>
      </div>
    </div>
  )
}
