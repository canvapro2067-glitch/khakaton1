import { CheckCircle2, MapPin, Navigation } from 'lucide-react'
import { useEffect, useState } from 'react'
import { PROBLEM_REASONS, naviTo } from '../driverFormat'
import { flattenStops, useDriver } from './DriverContext'

export function StopActions({ stop, hideNavi }: { stop: any; hideNavi?: boolean }) {
  const { act, busy } = useDriver()
  const [openDone, setOpenDone] = useState(false)
  const [weight, setWeight] = useState(String(stop?.order?.weight_kg || ''))
  const [comment, setComment] = useState('')

  if (!stop) return null
  const st = stop.status
  if (st === 'done' || st === 'problem') return null

  return (
    <>
      <div className="driver-stop-actions" style={{ marginTop: 10 }}>
        {(st === 'pending' || st === 'enroute') && (
          <>
            {st === 'pending' && (
              <button type="button" className="btn ghost" disabled={busy} onClick={() => act(`/api/driver/stops/${stop.id}/start`)}>
                В пути к точке
              </button>
            )}
            {!hideNavi && (
            <button type="button" className="btn navi" disabled={busy} onClick={() => naviTo(stop.order?.lat, stop.order?.lon, stop.order?.address)}>
              <Navigation size={16} /> Навигатор
            </button>
            )}
            <button type="button" className="btn primary" disabled={busy} onClick={() => act(`/api/driver/stops/${stop.id}/arrive`)}>
              <MapPin size={16} /> Прибыл на точку
            </button>
          </>
        )}
        {st === 'at_stop' && (
          <button type="button" className="btn primary" disabled={busy} onClick={() => act(`/api/driver/stops/${stop.id}/unload`)}>
            Начать разгрузку
          </button>
        )}
        {(st === 'unloading' || st === 'at_stop') && (
          <button type="button" className="btn ok" disabled={busy} onClick={() => setOpenDone(true)}>
            <CheckCircle2 size={16} /> Завершить заказ
          </button>
        )}
        <button type="button" className="btn bad" disabled={busy} onClick={() => window.dispatchEvent(new CustomEvent('mm-problem', { detail: stop.id }))}>
          Проблема
        </button>
      </div>
      {openDone && (
        <div className="modal" onClick={() => setOpenDone(false)}>
          <div className="card" onClick={(e) => e.stopPropagation()}>
            <h3>Завершить заказ</h3>
            <label className="field">
              Фактически доставлено, кг
              <input value={weight} onChange={(e) => setWeight(e.target.value)} type="number" />
            </label>
            <label className="field">
              Комментарий
              <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
            </label>
            <div className="row-btns">
              <button
                className="btn ok"
                disabled={busy}
                onClick={async () => {
                  await act(`/api/driver/stops/${stop.id}/done`, {
                    actual_weight_kg: weight ? Number(weight) : undefined,
                    comment,
                  })
                  setOpenDone(false)
                }}
              >
                Подтвердить
              </button>
              <button className="btn ghost" onClick={() => setOpenDone(false)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export function ProblemModal() {
  const { act, busy, pack } = useDriver()
  const [stopId, setStopId] = useState<number | null>(null)
  const [reason, setReason] = useState(PROBLEM_REASONS[0])
  const [comment, setComment] = useState('')

  useEffect(() => {
    const fn = (e: Event) => setStopId((e as CustomEvent).detail)
    window.addEventListener('mm-problem', fn)
    return () => window.removeEventListener('mm-problem', fn)
  }, [])

  if (!stopId) return null
  const stop = flattenStops(pack).find((s: any) => s.id === stopId)
  return (
    <div className="modal" onClick={() => setStopId(null)}>
      <div className="card" onClick={(e) => e.stopPropagation()}>
        <h3>Сообщить о проблеме</h3>
        <p className="muted">{stop?.order?.name}</p>
        <label className="field">
          Причина
          <select value={reason} onChange={(e) => setReason(e.target.value)}>
            {PROBLEM_REASONS.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Комментарий диспетчеру
          <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
        </label>
        <div className="row-btns">
          <button
            className="btn bad"
            disabled={busy}
            onClick={async () => {
              await act(`/api/driver/stops/${stopId}/problem`, { reason, comment, text: comment })
              setStopId(null)
              setComment('')
            }}
          >
            Отправить
          </button>
          <button className="btn ghost" onClick={() => setStopId(null)}>
            Отмена
          </button>
        </div>
      </div>
    </div>
  )
}
