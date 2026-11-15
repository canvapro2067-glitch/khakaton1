import { Navigation, Phone, Truck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Logo from '../Logo'
import { fmtKm, fmtTravel, naviTo } from '../driverFormat'
import { statusLabel } from '../statusLabels'
import { currentStop, flattenStops, useDriver } from './DriverContext'
import { ProblemModal, StopActions } from './StopActions'

export default function DriverHome() {
  const { pack, cfg, err, offline, pending } = useDriver()
  const nav = useNavigate()
  const driver = pack?.driver
  const depot = pack?.depot || cfg.depot
  const v = pack?.vehicle
  const stops = flattenStops(pack)
  const current = currentStop(stops)
  const done = stops.filter((s: any) => s.status === 'done').length
  const left = stops.filter((s: any) => s.status !== 'done' && s.status !== 'problem').length
  const weight = stops.reduce((a: number, s: any) => a + (s.order?.weight_kg || 0), 0)
  const remainW = v?.remaining_kg ?? stops.filter((s: any) => s.status !== 'done' && s.status !== 'problem').reduce((a: number, s: any) => a + (s.order?.weight_kg || 0), 0)
  const phone = pack?.dispatcher_phone || cfg.dispatcher_phone
  const date = new Date().toLocaleDateString('ru-BY', { timeZone: 'Europe/Minsk', weekday: 'short', day: 'numeric', month: 'long' })

  return (
    <div className="driver-page">
      <div className="hero">
        <div className="row-btns" style={{ justifyContent: 'space-between' }}>
          <Logo size={40} wide />
          <span className="small">{date}</span>
        </div>
        <h2 style={{ margin: '8px 0 4px' }}>{driver?.full_name || 'Водитель'}</h2>
        <div className="driver-vehicle">
          <Truck size={16} />{' '}
          {v
            ? `${v.plate} · ${v.brand} ${v.model}`
            : 'Автомобиль не назначен. Обратитесь к диспетчеру'}
        </div>
        {v && (
          <p className="small" style={{ margin: '8px 0 0', opacity: 0.92 }}>
            Грузоподъёмность: {v.capacity_kg} кг
            <br />
            Загружено: {v.load_kg ?? remainW} кг · осталось везти {remainW} кг
          </p>
        )}
        <p className="small" style={{ margin: '8px 0 0', opacity: 0.9 }}>
          Склад: {depot?.address || '—'}
        </p>
      </div>

      {offline && (
        <div className="alert">Офлайн. Показан сохранённый маршрут{pending ? ` · не отправлено: ${pending}` : ''}.</div>
      )}
      {err && <div className="alert bad">{err}</div>}
      {pack?.message && !v && <div className="alert">{pack.message}</div>}

      <div className="driver-home-grid" style={{ marginTop: 12 }}>
      <div className="card" style={{ padding: 16 }}>
        <b>Текущая смена</b>
        <p className="muted" style={{ margin: '6px 0 0' }}>
          {statusLabel(driver?.shift_status)} · старт {pack?.work_start || '09:00'} · план до {pack?.route?.finish_time || '—'}
        </p>
        <div className="driver-stats">
          <span>
            Заказы
            <b>{stops.length}</b>
          </span>
          <span>
            Выполнено
            <b>{done}</b>
          </span>
          <span>
            Осталось
            <b>{left}</b>
          </span>
          <span>
            Вес
            <b>{weight} кг</b>
          </span>
        </div>
        <div className="progress" style={{ marginTop: 12 }}>
          <i style={{ width: `${stops.length ? Math.round((100 * done) / stops.length) : 0}%` }} />
        </div>
      </div>

      {current ? (
        <div className="card driver-next" style={{ padding: 16 }}>
          <div className="muted small">Следующая точка</div>
          <h3 style={{ margin: '4px 0' }}>
            {current.seq}. {current.order?.name}
          </h3>
          <p className="muted" style={{ margin: 0 }}>
            {current.order?.address}
          </p>
          <p className="small" style={{ margin: '8px 0 0' }}>
            План {current.eta} · {current.order?.weight_kg} кг · {fmtKm(current.distance_from_prev_m)} · в пути {fmtTravel(current.travel_s)}
          </p>
          <div className="row-btns" style={{ marginTop: 12 }}>
            <button type="button" className="btn navi" onClick={() => naviTo(current.order?.lat, current.order?.lon, current.order?.address)}>
              <Navigation size={16} /> Навигатор
            </button>
            <button type="button" className="btn ghost" onClick={() => nav(`/driver/orders/${current.id}`)}>
              Подробнее
            </button>
          </div>
          <StopActions stop={current} hideNavi />
        </div>
      ) : stops.length ? (
        <div className="card" style={{ padding: 16 }}>
          <b>Доставки завершены</b>
          <p className="muted">Можно возвращаться на склад.</p>
          {depot && (
            <button type="button" className="btn navi" onClick={() => naviTo(depot.lat, depot.lon, depot.address)}>
              <Navigation size={16} /> Навигатор на склад
            </button>
          )}
        </div>
      ) : (
        <div className="card" style={{ padding: 16 }}>
          <p className="muted">Маршрут ещё не назначен.</p>
        </div>
      )}
      </div>

      {phone && (
        <a className="btn ghost" style={{ width: '100%', marginTop: 12, justifyContent: 'center' }} href={`tel:${phone}`}>
          <Phone size={16} /> Позвонить диспетчеру
        </a>
      )}
      <ProblemModal />
    </div>
  )
}
