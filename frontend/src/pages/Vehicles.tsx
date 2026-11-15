import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

const empty = {
  brand: '',
  model: '',
  plate: '',
  capacity_kg: 4000,
  max_mass_kg: 8000,
  height_m: 2.8,
  width_m: 2.4,
  length_m: 7.5,
  is_active: true,
  color: '#0874D1',
  note: '',
}

export default function Vehicles() {
  const [rows, setRows] = useState<any[]>([])
  const [form, setForm] = useState<any>(null)
  const nav = useNavigate()

  async function load() {
    setRows((await api('/api/vehicles')) as any[])
  }
  useEffect(() => {
    load()
  }, [])

  async function save() {
    const payload = {
      ...form,
      capacity_kg: +form.capacity_kg,
      max_mass_kg: +form.max_mass_kg,
      height_m: +form.height_m,
      width_m: +form.width_m,
      length_m: +form.length_m,
    }
    if (form.id) await api(`/api/vehicles/${form.id}`, { method: 'PATCH', body: JSON.stringify(payload) })
    else await api('/api/vehicles', { method: 'POST', body: JSON.stringify(payload) })
    setForm(null)
    load()
  }

  return (
    <>
      <div className="topbar">
        <h2 style={{ margin: 0 }}>Автопарк</h2>
        <button className="btn" onClick={() => setForm({ ...empty })}>
          <Plus size={16} /> Добавить автомобиль
        </button>
      </div>
      {form && (
        <div className="card form-grid" style={{ padding: 16, marginBottom: 12 }}>
          {['brand', 'model', 'plate', 'capacity_kg', 'max_mass_kg', 'height_m', 'width_m', 'length_m', 'color', 'note'].map((k) => (
            <label key={k} className="field">
              {k}
              <input value={form[k] ?? ''} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
            </label>
          ))}
          <div className="row-btns span-2">
            <button className="btn" onClick={save}>Сохранить</button>
            <button className="btn ghost" onClick={() => setForm(null)}>Отмена</button>
          </div>
        </div>
      )}
      <div className="cards">
        {rows.map((v) => (
          <div key={v.id} className="card vc" onClick={() => nav(`/vehicles/${v.id}`)}>
            <div className="row-btns">
              <span className="dot" style={{ background: v.color }} />
              <b>{v.plate}</b>
              <span className={`badge ${v.is_active ? 'ok' : 'bad'}`}>{v.is_active ? 'в работе' : 'простой'}</span>
            </div>
            <div className="muted">
              {v.brand} {v.model}
            </div>
            <p>
              {v.capacity_kg} кг · заказов {v.orders_count || 0} · груз {v.load_kg || 0} кг
            </p>
            <div className="progress">
              <i style={{ width: `${Math.min(100, Math.round((v.fill || 0) * 100))}%` }} />
            </div>
            <div className="muted" style={{ marginTop: 8 }}>
              Водитель: {v.driver_name || 'не назначен'}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
