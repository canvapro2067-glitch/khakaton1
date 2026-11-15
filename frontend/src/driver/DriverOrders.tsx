import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { fmtDriverTime, fmtKm, fmtMinutes, naviTo } from '../driverFormat'
import { statusLabel } from '../statusLabels'
import { flattenStops, useDriver } from './DriverContext'
import { ProblemModal, StopActions } from './StopActions'

const FILTERS = [
  ['all', 'Все'],
  ['pending', 'Ожидают'],
  ['enroute', 'В пути'],
  ['unload', 'На разгрузке'],
  ['done', 'Выполнены'],
  ['problem', 'Проблемные'],
] as const

function match(s: any, f: string, q: string) {
  const hay = `${s.order?.name || ''} ${s.order?.address || ''}`.toLowerCase()
  if (q && !hay.includes(q.toLowerCase())) return false
  if (f === 'all') return true
  if (f === 'pending') return s.status === 'pending'
  if (f === 'enroute') return s.status === 'enroute'
  if (f === 'unload') return s.status === 'at_stop' || s.status === 'unloading'
  if (f === 'done') return s.status === 'done'
  if (f === 'problem') return s.status === 'problem'
  return true
}

export default function DriverOrders() {
  const { pack } = useDriver()
  const loc = useLocation()
  const id = loc.pathname.match(/\/driver\/orders\/(\d+)/)?.[1]
  const nav = useNavigate()
  const [f, setF] = useState('all')
  const [q, setQ] = useState('')
  const stops = flattenStops(pack)
  const detail = id ? stops.find((s: any) => String(s.id) === id) : null
  const list = useMemo(() => stops.filter((s: any) => match(s, f, q)), [stops, f, q])

  if (detail) {
    const o = detail.order || {}
    return (
      <div className="driver-page">
        <button type="button" className="btn ghost" onClick={() => nav('/driver/orders')}>
          ← К списку
        </button>
        <div className="card" style={{ padding: 16, marginTop: 12 }}>
          <span className={`badge ${detail.status === 'done' ? 'ok' : detail.status === 'problem' ? 'bad' : 'info'}`}>{statusLabel(detail.status)}</span>
          <h2 style={{ margin: '8px 0 4px' }}>
            {detail.seq}. {o.name}
          </h2>
          <p>{o.address}</p>
          {o.contact_phone ? (
            <p>
              Телефон: <a href={`tel:${o.contact_phone}`}>{o.contact_phone}</a>
            </p>
          ) : (
            <p className="muted">Телефон в заявке не указан</p>
          )}
          <p>Вес: {o.weight_kg} кг{detail.actual_weight_kg != null ? ` · факт ${detail.actual_weight_kg} кг` : ''}</p>
          <p>План прибытия: {detail.eta}</p>
          {o.preferred_time || o.window_start ? <p>Окно: {o.preferred_time || `${o.window_start}–${o.window_end}`}</p> : null}
          {o.dispatcher_note || o.warning ? <p>Комментарий диспетчера: {o.dispatcher_note || o.warning}</p> : <p className="muted">Особых условий нет</p>}
          <div className="driver-stop-times">
            <span>Прибыл: {fmtDriverTime(detail.arrived_at)}</span>
            <span>Разгрузка: {fmtDriverTime(detail.unloading_started_at)}</span>
            <span>Завершено: {fmtDriverTime(detail.completed_at)}</span>
            <span>На точке: {fmtMinutes(detail.unload_duration_s)}</span>
          </div>
          {detail.driver_comment ? <p className="small">Ваш комментарий: {detail.driver_comment}</p> : null}
          {detail.status === 'problem' && (
            <div className="alert bad">
              {detail.problem_reason} {detail.problem_text}
              {detail.dispatcher_reply ? (
                <div style={{ marginTop: 6 }}>
                  <b>Диспетчер:</b> {detail.dispatcher_reply}
                </div>
              ) : null}
            </div>
          )}
          <button type="button" className="btn navi" style={{ width: '100%', marginTop: 12 }} onClick={() => naviTo(o.lat, o.lon, o.address)}>
            Маршрут до объекта
          </button>
          <StopActions stop={detail} />
        </div>
        <ProblemModal />
      </div>
    )
  }

  return (
    <div className="driver-page">
      <h2 style={{ margin: '0 0 8px' }}>Мои заказы</h2>
      <input className="driver-search" placeholder="Поиск по магазину или адресу" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="filters" style={{ marginTop: 8 }}>
        {FILTERS.map(([k, lab]) => (
          <button key={k} type="button" className={`chip ${f === k ? 'on' : ''}`} onClick={() => setF(k)}>
            {lab}
          </button>
        ))}
      </div>
      {list.map((s: any) => (
        <button key={s.id} type="button" className={`driver-stop ${s.status}`} style={{ width: '100%', textAlign: 'left', marginTop: 10 }} onClick={() => nav(`/driver/orders/${s.id}`)}>
          <div className="driver-stop-head">
            <span className="driver-seq">{s.seq}</span>
            <div className="driver-stop-meta">
              <b>{s.order?.name}</b>
              <div className="muted small">{s.order?.address}</div>
            </div>
            <span className={`badge ${s.status === 'done' ? 'ok' : s.status === 'problem' ? 'bad' : 'info'}`}>{statusLabel(s.status)}</span>
          </div>
          <div className="muted small" style={{ marginTop: 6 }}>
            {s.eta} · {s.order?.weight_kg} кг · {fmtKm(s.distance_from_prev_m)}
            {s.order?.contact_phone ? ` · ${s.order.contact_phone}` : ''}
          </div>
        </button>
      ))}
      {!list.length && <p className="muted">Нет заказов в этом фильтре</p>}
      <ProblemModal />
    </div>
  )
}
