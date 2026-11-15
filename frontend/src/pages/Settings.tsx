import { useEffect, useState } from 'react'
import { api } from '../api'

const DEFAULTS: Record<string, string> = {
  min_fill: '0.9',
  max_fill: '1.0',
  max_hours: '8',
  max_trips: '3',
  use_windows: '1',
  historic_center_rule: '1',
  minimize_fleet: '1',
  unload_minutes: '25',
  fuel_l_per_100km: '18',
  fuel_price_byn: '2.45',
  work_start: '09:00',
  dispatcher_name: 'Диспетчер логистики',
  dispatcher_phone: '+375152000000',
}

export default function SettingsPage() {
  const [st, setSt] = useState<any>({})
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api('/api/settings').then(setSt)
  }, [])

  async function save() {
    await api('/api/settings', { method: 'PUT', body: JSON.stringify(st) })
    setMsg('Сохранено. Затраты на главной пересчитаются после обновления страницы.')
  }

  return (
    <>
      <h2>Настройки оптимизации</h2>
      <p className="muted">
        Параметры солвера и расчёта <b>затрат на топливо</b> (литры × цена за литр по пробегу плана). ФОТ водителей в
        сумму не входит.
      </p>
      <div className="card" style={{ padding: 16, maxWidth: 'min(640px, 100%)' }}>
        {[
          ['min_fill', 'Мин. загрузка (0.9 = 90%)'],
          ['max_fill', 'Макс. загрузка'],
          ['work_start', 'Начало смены'],
          ['max_hours', 'Рабочий день, ч'],
          ['max_trips', 'Макс. рейсов на машину за смену (факт — по загрузке)'],
          ['unload_minutes', 'Время разгрузки, мин (ориентир 20–30)'],
          ['fuel_l_per_100km', 'Средний расход, л/100 км'],
          ['fuel_price_byn', 'Цена топлива, BYN/л'],
          ['dispatcher_name', 'Диспетчер (имя для водителей)'],
          ['dispatcher_phone', 'Телефон диспетчера'],
        ].map(([k, label]) => (
          <label key={k} className="field">
            {label}
            <input value={st[k] ?? ''} onChange={(e) => setSt({ ...st, [k]: e.target.value })} />
          </label>
        ))}
        <label className="switch">
          <input type="checkbox" checked={st.use_windows !== '0'} onChange={(e) => setSt({ ...st, use_windows: e.target.checked ? '1' : '0' })} />
          Учитывать временные окна
        </label>
        <label className="switch">
          <input
            type="checkbox"
            checked={st.historic_center_rule !== '0'}
            onChange={(e) => setSt({ ...st, historic_center_rule: e.target.checked ? '1' : '0' })}
          />
          Учитывать спец. автомобили (1,5 т / центр)
        </label>
        <label className="switch">
          <input
            type="checkbox"
            checked={st.minimize_fleet !== '0'}
            onChange={(e) => setSt({ ...st, minimize_fleet: e.target.checked ? '1' : '0' })}
          />
          Минимум машин в день (не размазывать заказы по всему парку)
        </label>
        <div className="row-btns" style={{ marginTop: 16 }}>
          <button className="btn" onClick={save}>
            Сохранить
          </button>
          <button className="btn ghost" onClick={() => setSt({ ...st, ...DEFAULTS })}>
            Сбросить
          </button>
          <button className="btn primary" onClick={save}>
            Применить
          </button>
        </div>
        {msg && <div className="alert">{msg}</div>}
      </div>
    </>
  )
}