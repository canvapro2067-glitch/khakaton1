export default function Logo({ size = 40, wide = false }: { size?: number; wide?: boolean }) {
  const h = size
  const w = wide ? Math.round(size * 2.4) : size
  return (
    <img
      src="/logo-moloko.png"
      alt="ОАО «Молочный мир» — сила молока"
      width={w}
      height={h}
      style={{ height: h, width: wide ? w : h, maxWidth: '100%', objectFit: 'contain', display: 'block' }}
    />
  )
}
