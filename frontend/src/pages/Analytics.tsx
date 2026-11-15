import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'

export default function Analytics() {
  const [a, setA] = useState<any>(null)
  useEffect(() => {
    api('/api/analytics').then(setA)
  }, [])
  if (!a) return <p>Считаем показатели…</p>
  const cost = a.cost_byn ?? 0
  return (
    <>
      <h2>Аналитика эффективности</h2>
      <p className="muted">Только текущий рассчитанный план. Истории периодов в базе нет — проценты «роста» не показываем.</p>
      <div className="kpis">
        <div className="kpi">
          <span>Пробег</span>
          <b>{a.fleet_km} км</b>
        </div>
        <div className="kpi">
          <span>Топливо</span>
          <b>{cost.toLocaleString('ru')} BYN</b>
        </div>
        <div className="kpi">
          <span>Расход</span>
          <b>{a.fuel_l} л</b>
        </div>
        <div className="kpi">
          <span>Время</span>
          <b>{a.hours} ч</b>
        </div>
        <div className="kpi">
          <span>Выполнение</span>
          <b>{a.done_pct}%</b>
        </div>
      </div>
      <div className="kpis">
        <div className="kpi">
          <span>Средняя загрузка</span>
          <b>{a.avg_fill}%</b>
        </div>
        <div className="kpi">
          <span>Доставки</span>
          <b>
            {a.deliveries_done}/{a.deliveries_total}
          </b>
        </div>
        <div className="kpi">
          <span>Опоздания</span>
          <b>{a.late}</b>
        </div>
        <div className="kpi">
          <span>Авто в рейсе</span>
          <b>{a.vehicles_used}</b>
        </div>
        <div className="kpi">
          <span>Рейсов в плане</span>
          <b>{a.route_trips ?? a.vehicles_used}</b>
        </div>
      </div>
      <div className="card" style={{ padding: 16, marginBottom: 16 }}>
        <div>
          Затраты считаются <b>только по топливу</b>: (пробег ÷ 100) × {a.fuel_l_per_100km} л/100 км ×{' '}
          {a.fuel_price_byn} BYN/л.
        </div>
        <div className="muted small" style={{ marginTop: 6 }}>
          Пробег {a.fleet_km} км → {a.fuel_l} л → {a.fuel_cost_byn?.toLocaleString('ru')} BYN. Зарплата и прочие
          расходы не входят. Время рейсов ({a.hours} ч) — справочно.
          {a.fleet_km_roads != null ? ` Пробег по дорожным линиям на карте.` : ''}
        </div>
      </div>
      <div className="card chart-card" style={{ padding: 16, marginBottom: 16 }}>
        <b>Распределение пробега по автомобилям</b>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={a.per_vehicle}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="plate" hide />
            <YAxis />
            <Tooltip />
            <Bar dataKey="km" fill="#0874D1" radius={6} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="table-scroll">
      <table className="stack">
        <thead>
          <tr>
            <th>Авто</th>
            <th>км</th>
            <th>загрузка</th>
            <th>часы</th>
            <th>л</th>
            <th>BYN</th>
            <th>факт / план</th>
          </tr>
        </thead>
        <tbody>
          {a.per_vehicle.map((v: any) => (
            <tr key={v.plate}>
              <td data-label="Авто">{v.plate}</td>
              <td data-label="км">{v.km}</td>
              <td data-label="загрузка">{v.fill}%</td>
              <td data-label="часы">{v.hours}</td>
              <td data-label="л">{v.fuel_l}</td>
              <td data-label="BYN">{v.cost}</td>
              <td data-label="факт / план">
                {v.done}/{v.stops}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </>
  )
}
