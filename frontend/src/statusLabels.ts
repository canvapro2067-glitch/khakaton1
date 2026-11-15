const LABELS: Record<string, string> = {
  pending: 'ожидает посещения',
  enroute: 'в пути',
  at_stop: 'на точке',
  unloading: 'разгрузка',
  done: 'выполнен',
  problem: 'проблема',
  unassigned: 'не назначен',
  waiting: 'ожидает начала смены',
  ready: 'готов к выезду',
  on_route: 'выполняет маршрут',
  break: 'перерыв',
  returning: 'возвращается на склад',
  finished: 'смена завершена',
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return 'не назначен'
  return LABELS[status] ?? status
}