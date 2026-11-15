/** Human-readable label for restriction street_pattern (API keeps raw pattern). */
export function streetPatternLabel(pattern: string): { title: string; detail?: string } {
  const p = (pattern || '').trim()
  if (!p) return { title: '—' }

  if (p.startsWith('re:')) {
    const m = p.match(/re:\([^)]+\)([а-яёa-z\-]+)\(/i)
    if (m) {
      const word = m[1]
      const name = word.charAt(0).toUpperCase() + word.slice(1)
      return { title: `ул. ${name}`, detail: 'совпадение в адресе заказа' }
    }
    return { title: 'Сложное правило', detail: 'регулярное выражение' }
  }

  const plain = p.charAt(0).toUpperCase() + p.slice(1)
  return { title: plain, detail: 'вхождение в адрес' }
}