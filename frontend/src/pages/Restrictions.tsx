import { useEffect, useState } from 'react'
import { api } from '../api'
import { streetPatternLabel } from '../streetPatternLabel'

export default function Restrictions() {
  const [rows, setRows] = useState<any[]>([])
  const [st, setSt] = useState<any>({})
  const [feas, setFeas] = useState<any>(null)
  const [form, setForm] = useState({ name: '', street_pattern: '', max_capacity_kg: 1500, note: '' })
  const [msg, setMsg] = useState('')

  async function load() {
    setRows((await api('/api/restrictions')) as any[])
    setSt(await api('/api/settings'))
    setFeas(await api('/api/feasibility'))
  }
  useEffect(() => {
    load()
  }, [])

  async function saveParams() {
    await api('/api/settings', { method: 'PUT', body: JSON.stringify(st) })
    setMsg('Параметры сохранены. Уже рассчитанный план не меняется — запустите оптимизацию заново.')
    load()
  }

  return (
    <>
      <h2>Ограничения логистики</h2>
      <p className="muted">
        Исторический центр (Советская, Мостовая, Замковая) обслуживается только машиной 1,5 т. Это правило алгоритма, не Яндекса.
      </p>
      <div className="grid-dash">
        <div>
          <div className="card" style={{ padding: 16, marginBottom: 16 }}>
            <b>Основные параметры</b>
            <label className="field">
              Мин. загрузка (цель)
              <input value={st.min_fill || ''} onChange={(e) => setSt({ ...st, min_fill: e.target.value })} />
            </label>
            <label className="field">
              Макс. загрузка
              <input value={st.max_fill || '1.0'} onChange={(e) => setSt({ ...st, max_fill: e.target.value })} />
            </label>
            <label className="field">
              Рабочий день, ч
              <input value={st.max_hours || ''} onChange={(e) => setSt({ ...st, max_hours: e.target.value })} />
            </label>
            <label className="field">
              Макс. рейсов на машину за смену
              <input
                type="number"
                min={1}
                max={10}
                value={st.max_trips || '3'}
                onChange={(e) => setSt({ ...st, max_trips: e.target.value })}
              />
              <span className="muted small">
                Сколько раз машина может выехать со склада за 8 ч. Фактическое число рейсов в плане зависит от объёма заказов
                {feas ? ` (оценка сейчас: ~${feas.est_route_trips ?? '—'}, слотов в парке: ${feas.trip_slots ?? '—'})` : ''}
              </span>
            </label>
            <label className="field">
              Разгрузка, мин (20–30)
              <input value={st.unload_minutes || ''} onChange={(e) => setSt({ ...st, unload_minutes: e.target.value })} />
            </label>
            <label className="switch">
              <input
                type="checkbox"
                checked={st.historic_center_rule !== '0'}
                onChange={(e) => setSt({ ...st, historic_center_rule: e.target.checked ? '1' : '0' })}
              />
              Правило 1,5 т для Советской / Мостовой / Замковой
            </label>
            <button className="btn" style={{ marginTop: 10 }} onClick={saveParams}>
              Сохранить параметры
            </button>
          </div>
          <div className="card" style={{ padding: 16, marginBottom: 16 }}>
            <b>Новое правило улицы</b>
            <input placeholder="Название" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input
              placeholder="Например: советская или re:…"
              value={form.street_pattern}
              onChange={(e) => setForm({ ...form, street_pattern: e.target.value })}
            />
            <span className="muted small">Можно указать фрагмент адреса или шаблон re: для точного совпадения.</span>
            <input type="number" value={form.max_capacity_kg} onChange={(e) => setForm({ ...form, max_capacity_kg: +e.target.value })} />
            <button
              className="btn ghost"
              style={{ marginTop: 8 }}
              onClick={async () => {
                await api('/api/restrictions', { method: 'POST', body: JSON.stringify(form) })
                load()
              }}
            >
              Добавить
            </button>
          </div>
          <div className="table-scroll">
          <table className="stack">
            <thead>
              <tr>
                <th>Правило</th>
                <th>Улица</th>
                <th>кг</th>
                <th>Вкл</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td data-label="Правило">
                    {r.name}
                    <div className="muted">{r.note}</div>
                  </td>
                  <td data-label="Улица">
                    {(() => {
                      const lab = streetPatternLabel(r.street_pattern)
                      return (
                        <>
                          <span className="badge info">{lab.title}</span>
                          {lab.detail ? <div className="muted small" style={{ marginTop: 4 }}>{lab.detail}</div> : null}
                        </>
                      )
                    })()}
                  </td>
                  <td data-label="кг">{r.max_capacity_kg || '—'}</td>
                  <td data-label="Вкл">
                    <input
                      type="checkbox"
                      checked={r.is_active}
                      onChange={() => api(`/api/restrictions/${r.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: !r.is_active }) }).then(load)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
        <div className="card" style={{ padding: 16 }}>
          <b>Проверка выполнимости</b>
          {feas && (
            <>
              <p>Заказы: {feas.orders}</p>
              <p>Вес заказов: {feas.weight} кг</p>
              <p>Ёмкость парка: {feas.capacity} кг</p>
              <p>Автомобилей: {feas.vehicles}</p>
              <p>Резерв: {feas.reserve_kg} кг</p>
              <p>Активных ограничений: {feas.restrictions}</p>
              {feas.warnings?.length
                ? feas.warnings.map((w: string) => (
                    <div key={w} className="alert bad">
                      {w}
                    </div>
                  ))
                : <div className="alert ok">Условия выглядят выполнимыми. 90% — целевая загрузка, не скрывает заказы.</div>}
            </>
          )}
          {msg && <div className="alert">{msg}</div>}
        </div>
      </div>
    </>
  )
}
