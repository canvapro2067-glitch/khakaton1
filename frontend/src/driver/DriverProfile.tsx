import { Bell, LogOut, Phone, Send } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, clearToken } from '../api'
import { fmtDriverTime } from '../driverFormat'
import { statusLabel } from '../statusLabels'
import { useDriver } from './DriverContext'

export default function DriverProfile({ onLogout }: { onLogout?: () => void }) {
  const { pack, cfg, tabNotes, load } = useDriver()
  const nav = useNavigate()
  const d = pack?.driver
  const v = pack?.vehicle
  const phone = pack?.dispatcher_phone || cfg.dispatcher_phone
  const [history, setHistory] = useState<any[]>([])
  const [msgs, setMsgs] = useState<any[]>([])
  const [text, setText] = useState('')
  const [detail, setDetail] = useState<any>(null)

  useEffect(() => {
    api('/api/driver/history').then((x) => setHistory(x as any[])).catch(() => null)
    api('/api/driver/messages').then((x) => setMsgs(x as any[])).catch(() => null)
  }, [pack])

  async function send() {
    if (!text.trim()) return
    await api('/api/driver/messages', { method: 'POST', body: JSON.stringify({ text }) })
    setText('')
    setMsgs((await api('/api/driver/messages')) as any[])
  }

  return (
    <div className="driver-page">
      <h2 style={{ margin: '0 0 8px' }}>Профиль</h2>
      <div className="card" style={{ padding: 16 }}>
        <b>{d?.full_name}</b>
        <p className="muted" style={{ margin: '4px 0' }}>
          ID {d?.id} · {d?.username} · {d?.phone || 'телефон не указан'}
        </p>
        <p>
          Авто: {v ? `${v.plate} · ${v.brand} ${v.model} · ${v.capacity_kg} кг` : 'не назначен'}
        </p>
        <p>
          Статус: <span className="badge info">{statusLabel(d?.shift_status)}</span>
        </p>
        <label className="switch">
          <input
            type="checkbox"
            checked={d?.geo_enabled !== false}
            onChange={(e) =>
              api('/api/driver/geo', { method: 'POST', body: JSON.stringify({ enabled: e.target.checked }) }).then(load)
            }
          />
          Передавать GPS диспетчеру на смене
        </label>
        <div className="row-btns">
          <button type="button" className="btn ghost" onClick={() => api('/api/driver/shift', { method: 'PATCH', body: JSON.stringify({ status: 'ready' }) }).then(load)}>
            Готов к выезду
          </button>
          <button type="button" className="btn ghost" onClick={() => api('/api/driver/shift', { method: 'PATCH', body: JSON.stringify({ status: 'break' }) }).then(load)}>
            Перерыв
          </button>
          <button
            type="button"
            className="btn ghost"
            onClick={() =>
              api('/api/driver/shift', { method: 'PATCH', body: JSON.stringify({ status: 'finished' }) })
                .then(load)
                .catch((e) => alert(e.message))
            }
          >
            Завершить смену
          </button>
        </div>
      </div>

      <div className="card" style={{ padding: 16, marginTop: 12 }}>
        <div className="notes-head">
          <b>
            <Bell size={16} /> Уведомления
          </b>
          <button type="button" className="btn ghost" onClick={() => api('/api/driver/notifications/read', { method: 'POST' }).then(load)}>
            Прочитано
          </button>
        </div>
        {(tabNotes || []).slice(0, 8).map((n: any) => (
          <div key={n.id} className="muted small" style={{ marginTop: 8, opacity: n.read ? 0.6 : 1 }}>
            <b>{n.title}</b>
            <div>{n.body}</div>
            <div>{fmtDriverTime(n.created_at)}</div>
          </div>
        ))}
        {!tabNotes?.length && <p className="muted">Пока нет уведомлений</p>}
      </div>

      <div className="card" style={{ padding: 16, marginTop: 12 }}>
        <b>Связь с диспетчером</b>
        <p className="muted">{pack?.dispatcher_name || cfg.dispatcher_name}</p>
        {phone && (
          <a className="btn" href={`tel:${phone}`}>
            <Phone size={16} /> {phone}
          </a>
        )}
        <div className="driver-chat">
          {msgs.slice(-12).map((m: any) => (
            <div key={m.id} className={`chat-b ${m.mine ? 'mine' : ''}`}>
              <span className="muted small">{m.from_name}</span>
              <div>{m.text}</div>
            </div>
          ))}
        </div>
        <div className="chat-compose">
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Сообщение диспетчеру" />
          <button type="button" className="btn" onClick={send} aria-label="Отправить">
            <Send size={16} />
          </button>
        </div>
      </div>

      <div className="card" style={{ padding: 16, marginTop: 12 }}>
        <b>История рейсов</b>
        {!history.length && <p className="muted">Появится после пересчёта маршрута или прошлых смен</p>}
        {history.map((t) => (
          <button key={t.id} type="button" className="driver-stop" style={{ width: '100%', textAlign: 'left', marginTop: 8 }} onClick={() => setDetail(t)}>
            <b>{t.date}</b> · {t.plate}
            <div className="muted small">
              {t.done}/{t.orders} заказов · {t.weight_kg} кг · {(t.distance_m / 1000).toFixed(1)} км · проблем {t.problem}
            </div>
          </button>
        ))}
      </div>

      {detail && (
        <div className="modal" onClick={() => setDetail(null)}>
          <div className="card" onClick={(e) => e.stopPropagation()}>
            <h3>Рейс {detail.date}</h3>
            <p>
              {detail.plate} · {detail.done}/{detail.orders} · финиш {detail.finished || '—'}
            </p>
            {(detail.detail?.stops || []).map((s: any, i: number) => (
              <div key={i} className="muted small">
                {s.eta} {s.name} — {statusLabel(s.status)}
              </div>
            ))}
            <button className="btn ghost" onClick={() => setDetail(null)}>
              Закрыть
            </button>
          </div>
        </div>
      )}

      <button
        type="button"
        className="btn ghost"
        style={{ width: '100%', marginTop: 16 }}
        onClick={() => {
          clearToken()
          onLogout?.()
          nav('/login')
        }}
      >
        <LogOut size={16} /> Выйти
      </button>
    </div>
  )
}
