import { Bell, Route } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import MapBoard from '../MapBoard'
import { api } from '../api'
import { fmtDriverTime } from '../driverFormat'
import { statusLabel } from '../statusLabels'

export default function Dispatcher() {
  const [data, setData] = useState<any>(null)
  const [sel, setSel] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [cfg, setCfg] = useState<any>({})
  const [confirmSolve, setConfirmSolve] = useState(false)
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const roadGeomTried = useRef(false)
  const regeocodeTried = useRef(false)

  function ordersNeedAccurateGeo(orders: any[] | undefined) {
    if (!orders?.length) return false
    return orders.some(
      (o) => !o.geo_source || o.geo_source === 'approx' || String(o.geo_source).startsWith('street:'),
    )
  }

  function routesNeedRoadGeometry(routes: any[] | undefined) {
    if (!routes?.length) return false
    return routes.every((r) => !Array.isArray(r.geometry) || r.geometry.length < 2)
  }

  async function load() {
    let d: any = await api('/api/dashboard')
    if (ordersNeedAccurateGeo(d.orders) && !regeocodeTried.current) {
      regeocodeTried.current = true
      roadGeomTried.current = false
      setBusy(true)
      setMsg('Уточняем координаты адресов (Яндекс / OSM)…')
      try {
        await api('/api/orders/regeocode', { method: 'POST' })
        d = await api('/api/dashboard')
        setMsg('Адреса обновлены. При необходимости нажмите «Оптимизировать маршруты».')
      } catch (e: any) {
        setMsg(e.message || 'Не удалось обновить координаты адресов.')
      } finally {
        setBusy(false)
      }
    }
    if (routesNeedRoadGeometry(d.routes) && !roadGeomTried.current) {
      roadGeomTried.current = true
      setBusy(true)
      setMsg('На сервере нет линий по дорогам — пересчитываем…')
      try {
        await api('/api/routes/rebuild-geometries', { method: 'POST' })
        d = await api('/api/dashboard')
        setMsg('')
      } catch (e: any) {
        setMsg(e.message || 'Не удалось построить линии по дорогам. Нажмите «Оптимизировать маршруты».')
      } finally {
        setBusy(false)
      }
    }
    const c = await api('/api/config')
    setData(d)
    setCfg(c)
  }
  useEffect(() => {
    load().catch((e) => setMsg(e.message))
    const t = setInterval(() => load().catch(() => null), 10000)
    return () => clearInterval(t)
  }, [])

  async function solve() {
    setConfirmSolve(false)
    setBusy(true)
    setMsg('Идёт расчёт VRP и построение линий по дорогам…')
    try {
      const r: any = await api('/api/routes/solve', { method: 'POST' })
      setMsg(
        `Распределено по ${r.routes.length} авто, нераспределено: ${r.unassigned.length}. Пробег ${(r.total_distance_m / 1000).toFixed(1)} км за ${r.elapsed_s.toFixed(1)} с.`,
      )
      await load()
    } catch (e: any) {
      setMsg(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!data) return <p>Загрузка плана…</p>
  const k = data.kpis
  const c = data.costs || {}
  const km = c.fleet_km ?? (k.distance_m || 0) / 1000
  const hours = c.driver_hours ?? (k.duration_s || 0) / 3600
  const cost = c.cost_byn ?? 0
  const fuelL = c.fuel_l ?? 0
  const fuelPrice = c.fuel_price_byn ?? 2.89
  const fuelNorm = c.fuel_l_per_100km ?? 18

  return (
    <>
      <div className="topbar">
        <div>
          <h2 style={{ margin: 0 }}>План доставки</h2>
          <p className="muted">Склад {data.depot.address}</p>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div className="row-btns">
          <button className="btn ghost" title="Уведомления">
            <Bell size={16} /> {data.unassigned?.length || 0}
          </button>
          <button className="btn" disabled={busy} onClick={() => setConfirmSolve(true)}>
            <Route size={16} />
            {busy ? 'Расчёт…' : 'Оптимизировать маршруты'}
          </button>
        </div>
      </div>
      <div className="kpis">
        <div className="kpi">
          <span>Всего заказов</span>
          <b>{k.orders}</b>
        </div>
        <div className="kpi">
          <span>Общий вес</span>
          <b>{k.weight.toLocaleString('ru')} кг</b>
        </div>
        <div className="kpi">
          <span>Автомобилей</span>
          <b>
            {k.active_vehicles}/{k.vehicles}
          </b>
        </div>
        <div className="kpi">
          <span>Уникальных адресов</span>
          <b>{k.unique_addresses ?? '—'}</b>
        </div>
      </div>
      {msg && <div className="alert">{msg}</div>}
      {data.unassigned?.length > 0 && (
        <div className="alert bad">
          <b>Нераспределённые заказы — оптимизация неполная</b>
          {data.unassigned.map((u: any) => (
            <div key={u.id} className="small">
              {u.order?.name}: {u.reason}. {u.conflicts} → {u.suggestions}
            </div>
          ))}
        </div>
      )}
      {!k.orders && (
        <div className="alert">
          Нет заказов. Загрузите Excel на странице <Link to="/orders">Заказы</Link>.
        </div>
      )}
      <div className="grid-dash">
        <MapBoard
          data={{
            ...data,
            driver_positions: (data.driver_positions || []).map((p: any) => ({
              ...p,
              name: p.name,
            })),
          }}
          selectedVehicle={sel}
          yandexKey={cfg.yandex_maps_key}
        />
        <div className="card list">
          <div className="topbar" style={{ marginBottom: 4 }}>
            <b>Автопарк</b>
            <Link className="btn ghost" to="/vehicles">
              Все автомобили
            </Link>
          </div>
          {(data.routes || []).map((r: any) => (
            <div
              key={r.id}
              className={`vrow ${sel === r.vehicle.id ? 'on' : ''}`}
              onClick={() => setSel(sel === r.vehicle.id ? null : r.vehicle.id)}
            >
              <div className="dot" style={{ background: r.vehicle.color }} />
              <div>
                <b>{r.vehicle.plate}</b> · {r.vehicle.brand} {r.vehicle.model}
                <div className="muted">
                  {r.stops_count} заказов · {r.load_kg} / {r.vehicle.capacity_kg} кг · {(r.distance_m / 1000).toFixed(1)} км
                </div>
                <div className="progress" style={{ marginTop: 6 }}>
                  <i style={{ width: `${Math.min(100, Math.round(r.fill * 100))}%` }} />
                </div>
              </div>
              <span className={`badge ${r.fill >= 0.9 ? 'ok' : 'warn'}`}>{Math.round(r.fill * 100)}%</span>
            </div>
          ))}
        </div>
      </div>
      <div className="card" style={{ padding: 16, marginTop: 14 }}>
        <div className="topbar" style={{ marginBottom: 8 }}>
          <b>Водители на смене</b>
          <Link className="btn ghost" to="/drivers">
            Все водители
          </Link>
        </div>
        {(data.drivers || []).length === 0 ? (
          <p className="muted">Нет учётных записей водителей</p>
        ) : (
          (data.drivers || []).map((d: any) => (
            <div key={d.id} className="vrow" style={{ cursor: 'default' }}>
              <div className="dot" style={{ background: d.vehicle?.color || '#888' }} />
              <div>
                <b>{d.full_name || d.username}</b>
                <div className="muted">
                  {d.vehicle ? `${d.vehicle.plate} · ${d.vehicle.brand} ${d.vehicle.model}` : 'Автомобиль не назначен'}
                </div>
                <div className="muted">
                  {d.stops_total
                    ? `Выполнено ${d.stops_done} из ${d.stops_total}, осталось ${d.stops_left}`
                    : 'Маршрут не назначен'}
                  {d.current_stop ? ` · сейчас: ${d.current_stop.seq}. ${d.current_stop.name} (${statusLabel(d.current_stop.status)})` : ''}
                  {d.stops_problem ? ` · проблем: ${d.stops_problem}` : ''}
                  {d.current_stop?.arrived_at ? ` · прибыл ${fmtDriverTime(d.current_stop.arrived_at)}` : ''}
                </div>
              </div>
              <span
                className={`badge ${
                  !d.is_active ? 'bad' : d.route_status === 'on_route' ? 'info' : d.route_status === 'done' ? 'ok' : 'warn'
                }`}
              >
                {!d.is_active ? 'блок' : statusLabel(d.shift_status || d.route_status)}
              </span>
            </div>
          ))
        )}
      </div>
      <div className="bottom-kpis">
        <div className="kpi">
          <span>Часы работы водителей</span>
          <b>{hours.toFixed(1)} ч</b>
          <div className="muted small">сумма смен всех машин</div>
        </div>
        <div className="kpi">
          <span>Общий пробег</span>
          <b>{km.toFixed(1)} км</b>
          {c.fleet_km_roads != null && c.fleet_km_plan != null && c.fleet_km_roads > c.fleet_km_plan + 0.5 && (
            <div className="muted small">по дорогам, план {c.fleet_km_plan} км</div>
          )}
        </div>
        <div className="kpi">
          <span>Затраты на топливо</span>
          <b>{Math.round(cost).toLocaleString('ru')} BYN</b>
          <div className="muted small">
            ~{fuelL.toLocaleString('ru')} л × {fuelPrice} BYN/л (норма {fuelNorm} л/100 км). Без зарплаты водителей.
          </div>
        </div>
      </div>
      {confirmSolve && (
        <div className="modal" onClick={() => setConfirmSolve(false)}>
          <div className="card" onClick={(e) => e.stopPropagation()}>
            <h3>Сохранить новый план?</h3>
            <p className="muted">Текущие маршруты будут перезаписаны. Водители получат обновлённую последовательность точек.</p>
            <div className="row-btns">
              <button className="btn" onClick={solve}>
                Запустить оптимизацию
              </button>
              <button className="btn ghost" onClick={() => setConfirmSolve(false)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
