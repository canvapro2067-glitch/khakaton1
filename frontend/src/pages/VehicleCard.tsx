import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import MapBoard from '../MapBoard'
import { api } from '../api'

export default function VehicleCard() {
  const { id } = useParams()
  const [pack, setPack] = useState<any>(null)
  const [cfg, setCfg] = useState<any>({})

  useEffect(() => {
    api(`/api/vehicles/${id}`).then(setPack)
    api('/api/config').then(setCfg)
  }, [id])

  if (!pack) return <p>Загрузка карточки…</p>
  const v = pack.vehicle
  const r = pack.route
  const mapData = r
    ? {
        depot: pack.depot,
        routes: [r],
        orders: (r.stops || []).map((s: any) => ({ ...s.order, assignment: { vehicle: v, eta: s.eta, status: s.status, seq: s.seq } })),
        restrictions_geometry: [],
      }
    : null

  return (
    <>
      <Link to="/vehicles" className="muted">
        ← Автопарк
      </Link>
      <div className="topbar">
        <div>
          <h2 style={{ margin: 0 }}>{v.plate}</h2>
          <p className="muted">
            {v.brand} {v.model} · водитель {v.driver_name || '—'}
          </p>
        </div>
        <span className={`badge ${v.is_active ? 'ok' : 'bad'}`}>{v.is_active ? 'в работе' : 'простой'}</span>
      </div>
      <div className="kpis">
        <div className="kpi">
          <span>Грузоподъёмность</span>
          <b>{v.capacity_kg} кг</b>
        </div>
        <div className="kpi">
          <span>Загрузка</span>
          <b>{r ? `${r.load_kg} кг` : '—'}</b>
        </div>
        <div className="kpi">
          <span>Заказов</span>
          <b>{r?.stops_count || 0}</b>
        </div>
        <div className="kpi">
          <span>В пути</span>
          <b>{r ? `${(r.duration_s / 3600).toFixed(1)} ч` : '—'}</b>
        </div>
      </div>
      <div className="card" style={{ padding: 16, marginBottom: 12 }}>
        <b>Обязательные магазины (исторический центр)</b>
        {(pack.mandatory_stops || []).length === 0 ? (
          <p className="muted">Нет точек на Советской / Мостовой / Замковой в этом рейсе. Правило: только 1,5 т.</p>
        ) : (
          <ul>
            {pack.mandatory_stops.map((s: any) => (
              <li key={s.id}>
                {s.order?.name} — {s.order?.address}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="grid-dash">
        {mapData ? <MapBoard data={mapData} selectedVehicle={v.id} yandexKey={cfg.yandex_maps_key} /> : <div className="card" style={{ padding: 16 }}>Маршрут ещё не рассчитан</div>}
        <div className="card list">
          <ol>
            <li>Склад — {pack.depot?.address}</li>
            {(r?.stops || []).map((s: any) => (
              <li key={s.id}>
                {s.eta} {s.order?.name}
                <div className="muted">
                  {s.order?.address} · {s.order?.weight_kg} кг · окно {s.order?.preferred_time || 'рабочий день'}
                </div>
              </li>
            ))}
            <li>Возвращение на склад</li>
          </ol>
        </div>
      </div>
    </>
  )
}
