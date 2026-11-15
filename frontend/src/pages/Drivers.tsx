import { Pencil, Plus, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
const empty = {
  full_name: '',
  username: '',
  phone: '',
  password: '',
  vehicle_id: '',
}

function routeBadge(d: any) {
  if (!d.is_active) return { cls: 'bad', text: 'заблокирован' }
  if (!d.vehicle) return { cls: 'warn', text: 'без авто' }
  if (d.route_status === 'on_route') return { cls: 'info', text: 'на маршруте' }
  if (d.route_status === 'done') return { cls: 'ok', text: 'рейс завершён' }
  if (d.stops_total) return { cls: 'warn', text: 'ожидает выезда' }
  return { cls: 'warn', text: 'нет маршрута' }
}

export default function Drivers() {
  const [rows, setRows] = useState<any[]>([])
  const [vehicles, setVehicles] = useState<any[]>([])
  const [form, setForm] = useState<any>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function load() {
    const [d, v] = await Promise.all([api('/api/drivers'), api('/api/vehicles')])
    setRows(d as any[])
    setVehicles(v as any[])
  }
  useEffect(() => {
    load().catch((e) => setErr(e.message))
    const t = setInterval(() => load().catch(() => null), 8000)
    return () => clearInterval(t)
  }, [])

  function takenVehicleIds(exceptId?: number) {
    return new Set(rows.filter((d) => d.is_active && d.vehicle_id && d.id !== exceptId).map((d) => d.vehicle_id))
  }

  async function save() {
    setBusy(true)
    setErr('')
    try {
      const payload: any = {
        full_name: form.full_name,
        username: form.username,
        phone: form.phone,
        vehicle_id: form.vehicle_id ? +form.vehicle_id : null,
      }
      if (form.password) payload.password = form.password
      if (form.id) await api(`/api/drivers/${form.id}`, { method: 'PATCH', body: JSON.stringify(payload) })
      else {
        if (!form.password) throw new Error('Укажите пароль')
        await api('/api/drivers', { method: 'POST', body: JSON.stringify(payload) })
      }
      setForm(null)
      await load()
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function toggle(d: any) {
    await api(`/api/drivers/${d.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: !d.is_active }) })
    load()
  }

  async function remove(d: any) {
    if (!confirm(`Деактивировать аккаунт ${d.full_name || d.username}? История доставок сохранится.`)) return
    await api(`/api/drivers/${d.id}`, { method: 'DELETE' })
    load()
  }

  const taken = takenVehicleIds(form?.id)

  return (
    <>
      <div className="topbar">
        <div>
          <h2 style={{ margin: 0 }}>Водители</h2>
          <p className="muted">Учётные записи создаёт только диспетчер. Один активный водитель — один автомобиль.</p>
        </div>
        <button className="btn" onClick={() => setForm({ ...empty })}>
          <Plus size={16} /> Добавить водителя
        </button>
      </div>
      {err && <div className="alert bad">{err}</div>}
      {form && (
        <div className="card" style={{ padding: 16, marginBottom: 12 }}>
          <b>{form.id ? 'Редактирование' : 'Новый водитель'}</b>
          <div className="form-grid" style={{ marginTop: 8 }}>
            <label className="field">
              ФИО
              <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </label>
            <label className="field">
              Телефон
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+37529…" />
            </label>
            <label className="field">
              Логин
              <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            </label>
            <label className="field">
              {form.id ? 'Новый пароль (пусто — без смены)' : 'Пароль'}
              <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </label>
            <label className="field span-2">
              Автомобиль
              <select value={form.vehicle_id ?? ''} onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })}>
                <option value="">Не назначать</option>
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id} disabled={taken.has(v.id)}>
                    {v.plate} · {v.brand} {v.model} · {v.capacity_kg} кг
                    {taken.has(v.id) ? ' (занят)' : ''}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="row-btns">
            <button className="btn" disabled={busy} onClick={save}>
              Сохранить
            </button>
            <button className="btn ghost" onClick={() => setForm(null)}>
              Отмена
            </button>
          </div>
        </div>
      )}
      <div className="table-scroll">
        <table className="stack">
          <thead>
            <tr>
              <th>ФИО</th>
              <th>Логин</th>
              <th>Телефон</th>
              <th>Автомобиль</th>
              <th>Ёмкость</th>
              <th>Аккаунт</th>
              <th>Маршрут</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => {
              const b = routeBadge(d)
              return (
                <tr key={d.id}>
                  <td data-label="ФИО">
                    <b>{d.full_name || '—'}</b>
                  </td>
                  <td data-label="Логин">{d.username}</td>
                  <td data-label="Телефон">{d.phone || '—'}</td>
                  <td data-label="Автомобиль">
                    {d.vehicle ? (
                      <>
                        {d.vehicle.plate}
                        <div className="muted">
                          {d.vehicle.brand} {d.vehicle.model}
                        </div>
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td data-label="Ёмкость">{d.vehicle?.capacity_kg ? `${d.vehicle.capacity_kg} кг` : '—'}</td>
                  <td data-label="Аккаунт">
                    <span className={`badge ${d.is_active ? 'ok' : 'bad'}`}>{d.is_active ? 'активен' : 'заблокирован'}</span>
                  </td>
                  <td data-label="Маршрут">
                    <span className={`badge ${b.cls}`}>{b.text}</span>
                    {d.stops_total ? (
                      <div className="muted">
                        {d.stops_done}/{d.stops_total} · осталось {d.stops_left}
                        {d.current_stop ? ` · т. ${d.current_stop.seq} ${d.current_stop.name}` : ''}
                        {d.stops_problem ? ` · проблем ${d.stops_problem}` : ''}
                      </div>
                    ) : null}
                  </td>
                  <td data-label="">
                    <div className="row-btns">
                      <button className="btn ghost" onClick={() => setForm({ ...d, password: '', vehicle_id: d.vehicle_id || '' })}>
                        <Pencil size={14} />
                      </button>
                      <button className="btn ghost" onClick={() => toggle(d)}>
                        {d.is_active ? 'Блок' : 'Вкл'}
                      </button>
                      <button className="btn bad" onClick={() => remove(d)}>
                        Снять
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
            {!rows.length && (
              <tr>
                <td colSpan={8} className="muted">
                  <UserRound size={16} /> Пока нет водителей
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}
