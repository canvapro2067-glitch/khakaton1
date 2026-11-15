import { RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import MapBoard from '../MapBoard'
import { api } from '../api'
import { statusLabel } from '../statusLabels'

const chips = [
  ['all', 'Все маршруты'],
  ['pending', 'Невыполненные'],
  ['done', 'Выполненные'],
  ['problem', 'Проблемные'],
  ['unassigned', 'Нераспределённые'],
]

export default function MapRoutes() {
  const [data, setData] = useState<any>(null)
  const [sel, setSel] = useState<number | null>(null)
  const [cfg, setCfg] = useState<any>({})
  const [filter, setFilter] = useState('all')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  async function load() {
    const [d, c] = await Promise.all([api('/api/dashboard'), api('/api/config')])
    setData(d)
    setCfg(c)
  }
  useEffect(() => {
    load()
  }, [])

  const route = (data?.routes || []).find((r: any) => r.vehicle?.id === sel)

  async function rebuild() {
    if (!route) return
    if (!confirm('Пересчитать геометрию выбранного рейса по дорогам и передать водителю?')) return
    setBusy(true)
    try {
      await api(`/api/routes/${route.id}/rebuild`, { method: 'POST' })
      setMsg('Маршрут по дорогам обновлён')
      await load()
    } catch (e: any) {
      setMsg(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!data) return <p>Загрузка карты…</p>
  return (
    <>
      <div className="topbar">
        <div>
          <h2 style={{ margin: 0 }}>Карта маршрутов</h2>
          <p className="muted">Гродно · линии по дорогам, не прямые отрезки</p>
        </div>
        <button className="btn ghost" disabled={busy || !route} onClick={rebuild}>
          <RefreshCw size={16} /> Пересчитать выбранный рейс
        </button>
      </div>
      {msg && <div className="alert">{msg}</div>}
      <div className="filters">
        {chips.map(([id, label]) => (
          <button key={id} className={`chip ${filter === id ? 'on' : ''}`} onClick={() => setFilter(id)}>
            {label}
          </button>
        ))}
        <select
          value={sel || ''}
          onChange={(e) => setSel(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Все автомобили</option>
          {(data.routes || []).map((r: any) => (
            <option key={r.id} value={r.vehicle.id}>
              {r.vehicle.plate}
            </option>
          ))}
        </select>
      </div>
      <div className="map-page">
        <MapBoard data={data} selectedVehicle={sel} yandexKey={cfg.yandex_maps_key} filter={filter} />
        <div className="card" style={{ padding: 14 }}>
          {route ? (
            <>
              <b>{route.vehicle.plate}</b>
              <div className="muted">
                {route.vehicle.brand} {route.vehicle.model}
              </div>
              <p>
                Грузоподъёмность {route.vehicle.capacity_kg} кг
                <br />
                Загрузка {route.load_kg} кг ({Math.round(route.fill * 100)}%)
                <br />
                Заказов: {route.stops_count}
                <br />
                Пробег {(route.distance_m / 1000).toFixed(1)} км
                <br />
                Время рейса {(route.duration_s / 3600).toFixed(2)} ч, финиш {route.finish_time}
              </p>
              <ol className="small" style={{ paddingLeft: 16 }}>
                <li>Склад</li>
                {route.stops.map((s: any) => (
                  <li key={s.id}>
                    {s.eta} {s.order?.name} — {statusLabel(s.status)}
                  </li>
                ))}
                <li>Возврат на склад</li>
              </ol>
            </>
          ) : (
            <p className="muted">Выберите автомобиль, чтобы подсветить его рейс. Остальные линии станут бледнее.</p>
          )}
        </div>
      </div>
    </>
  )
}
