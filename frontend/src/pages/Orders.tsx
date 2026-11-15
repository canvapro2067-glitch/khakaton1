import { Plus, Upload } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { statusLabel } from '../statusLabels'

export default function Orders() {
  const [rows, setRows] = useState<any[]>([])
  const [msg, setMsg] = useState('')
  const [edit, setEdit] = useState<any>(null)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(0)
  const [preview, setPreview] = useState<any>(null)
  const [file, setFile] = useState<File | null>(null)
  const pageSize = 20

  async function load() {
    setRows((await api('/api/orders')) as any[])
  }
  useEffect(() => {
    load()
  }, [])

  async function pick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    if (!/\.xlsx?$/i.test(f.name)) {
      setMsg('Нужен файл Excel (.xlsx)')
      return
    }
    const fd = new FormData()
    fd.append('file', f)
    setMsg('Проверка файла…')
    try {
      const r: any = await api('/api/import/excel?preview=true', { method: 'POST', body: fd })
      setFile(f)
      setPreview(r)
      setMsg('')
    } catch (ex: any) {
      setMsg(ex.message)
    }
  }

  async function confirmImport() {
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    setMsg('Импорт…')
    try {
      const r: any = await api('/api/import/excel?replace=true', { method: 'POST', body: fd })
      let text = `Загружено ${r.imported} заказов — список обновлён. Дублей ${r.duplicates}, ошибок ${r.errors?.length || 0}.`
      if (r.solve) {
        const s = r.solve
        text += ` Маршрут пересчитан: ${s.vehicles_used} маш. в рейсе`
        if (s.vehicles_idle > 0) text += `, ${s.vehicles_idle} в резерве (малый объём дня)`
        text += `, пробег ${(s.total_distance_m / 1000).toFixed(1)} км`
        if (s.unassigned > 0) text += `, нераспределено ${s.unassigned}`
        text += '. Откройте «Главную» или «Карту».'
      } else {
        text += ' Заказы есть — нажмите «Оптимизировать маршруты» на главной.'
      }
      setMsg(text)
      setPreview(null)
      setFile(null)
      await load()
    } catch (ex: any) {
      setMsg(ex.message)
    }
  }

  async function save() {
    if (edit.id) await api(`/api/orders/${edit.id}`, { method: 'PATCH', body: JSON.stringify(edit) })
    else await api('/api/orders', { method: 'POST', body: JSON.stringify(edit) })
    setEdit(null)
    load()
  }

  const filtered = useMemo(() => {
    return rows.filter((o) => {
      const text = `${o.name} ${o.address}`.toLowerCase()
      if (q && !text.includes(q.toLowerCase())) return false
      const st = o.assignment?.status || 'unassigned'
      if (status !== 'all' && st !== status) return false
      return true
    })
  }, [rows, q, status])

  const slice = filtered.slice(page * pageSize, page * pageSize + pageSize)
  const unique = new Set(rows.map((o) => o.address.toLowerCase())).size
  const windows = rows.filter((o) => o.preferred_time || o.window_start).length
  const weight = rows.reduce((s, o) => s + o.weight_kg, 0)

  return (
    <>
      <div className="topbar">
        <h2 style={{ margin: 0 }}>Заказы и торговые точки</h2>
        <div className="row-btns">
          <label className="btn ghost">
            <Upload size={16} /> Загрузить Excel
            <input type="file" accept=".xlsx,.xls" hidden onChange={pick} />
          </label>
          <button className="btn" onClick={() => setEdit({ name: '', address: '', weight_kg: 0 })}>
            <Plus size={16} /> Добавить заказ
          </button>
        </div>
      </div>
      <div className="kpis">
        <div className="kpi">
          <span>Заказов</span>
          <b>{rows.length}</b>
        </div>
        <div className="kpi">
          <span>Вес</span>
          <b>{weight.toLocaleString('ru')} кг</b>
        </div>
        <div className="kpi">
          <span>Уникальных адресов</span>
          <b>{unique}</b>
        </div>
        <div className="kpi">
          <span>С окнами</span>
          <b>{windows}</b>
        </div>
      </div>
      {msg && <div className="alert">{msg}</div>}
      <div className="filters">
        <input placeholder="Поиск магазина или адреса" value={q} onChange={(e) => { setQ(e.target.value); setPage(0) }} />
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0) }}>
          <option value="all">Все статусы</option>
          <option value="pending">Ожидает</option>
          <option value="enroute">В пути</option>
          <option value="done">Доставлен</option>
          <option value="problem">Проблема</option>
          <option value="unassigned">Не назначен</option>
        </select>
        <button className="chip" onClick={() => { setQ(''); setStatus('all') }}>Сброс</button>
      </div>
      {edit && (
        <div className="card form-grid" style={{ padding: 16, marginBottom: 12 }}>
          <b className="span-2">{edit.id ? `Правка #${edit.id}` : 'Новый заказ'}</b>
          <div className="field span-2">
            Магазин
            <input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
          </div>
          <div className="field span-2">
            Адрес
            <input value={edit.address} onChange={(e) => setEdit({ ...edit, address: e.target.value })} />
          </div>
          <label className="field">
            Вес, кг
            <input type="number" min={0} placeholder="например 500" value={edit.weight_kg || ''} onChange={(e) => setEdit({ ...edit, weight_kg: +e.target.value })} />
          </label>
          <label className="field">
            Окно / время
            <input placeholder="например 10:30" value={edit.preferred_time || ''} onChange={(e) => setEdit({ ...edit, preferred_time: e.target.value })} />
          </label>
          <div className="row-btns span-2" style={{ marginTop: 10 }}>
            <button className="btn" onClick={save}>Сохранить</button>
            <button className="btn ghost" onClick={() => setEdit(null)}>Отмена</button>
            {edit.id && (
              <button
                className="btn bad"
                onClick={async () => {
                  if (!confirm('Удалить заказ?')) return
                  await api(`/api/orders/${edit.id}`, { method: 'DELETE' })
                  setEdit(null)
                  load()
                }}
              >
                Удалить
              </button>
            )}
          </div>
        </div>
      )}
      <div className="table-scroll">
      <table className="stack">
        <thead>
          <tr>
            <th>№</th>
            <th>Магазин</th>
            <th>Адрес</th>
            <th>Груз</th>
            <th>Время</th>
            <th>Статус</th>
            <th>Машина</th>
          </tr>
        </thead>
        <tbody>
          {slice.map((o, i) => (
            <tr key={o.id} onClick={() => setEdit({ ...o })} style={{ cursor: 'pointer' }}>
              <td data-label="№">{page * pageSize + i + 1}</td>
              <td data-label="Магазин">{o.name}</td>
              <td data-label="Адрес">{o.address}</td>
              <td data-label="Груз">{o.weight_kg} кг</td>
              <td data-label="Время">{o.preferred_time || o.window_start || '—'}</td>
              <td data-label="Статус">
                <span className={`badge ${o.assignment?.status === 'done' ? 'ok' : o.assignment ? 'info' : 'warn'}`}>
                  {statusLabel(o.assignment?.status || 'unassigned')}
                </span>
                {o.restricted_historic && <span className="badge bad">центр 1,5т</span>}
              </td>
              <td data-label="Машина">{o.assignment?.vehicle?.plate || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      <div className="pager">
        <button className="btn ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>Назад</button>
        <span className="muted">
          {page + 1} / {Math.max(1, Math.ceil(filtered.length / pageSize))}
        </span>
        <button className="btn ghost" disabled={(page + 1) * pageSize >= filtered.length} onClick={() => setPage(page + 1)}>
          Далее
        </button>
      </div>
      {preview && (
        <div className="modal" onClick={() => setPreview(null)}>
          <div className="card" onClick={(e) => e.stopPropagation()}>
            <h3>Предпросмотр Excel</h3>
            <p>
              Строк: {preview.count}, вес {preview.total_weight} кг, дублей {preview.duplicates}, ошибок {preview.errors?.length || 0}.
              Сейчас в базе {preview.existing_orders} заказов — они будут заменены.
              После подтверждения заказы попадут в таблицу ниже и автоматически пересчитается маршрут (по возможности на меньшее число машин).
            </p>
            {preview.errors?.length > 0 && (
              <div className="alert bad">
                {preview.errors.slice(0, 8).map((er: any, i: number) => (
                  <div key={i}>{er.row}: {er.error}</div>
                ))}
              </div>
            )}
            <table className="stack">
              <thead>
                <tr>
                  <th>Клиент</th>
                  <th>Адрес</th>
                  <th>Вес</th>
                </tr>
              </thead>
              <tbody>
                {(preview.preview || []).slice(0, 12).map((r: any) => (
                  <tr key={r.row}>
                    <td data-label="Клиент">{r.name}</td>
                    <td data-label="Адрес">{r.address}</td>
                    <td data-label="Вес">{r.weight_kg}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="row-btns" style={{ marginTop: 12 }}>
              <button className="btn" onClick={confirmImport}>Подтвердить загрузку</button>
              <button className="btn ghost" onClick={() => setPreview(null)}>Отмена</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
