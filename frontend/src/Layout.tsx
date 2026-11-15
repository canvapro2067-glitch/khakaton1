import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { BarChart3, Car, LogOut, Map, Menu, Package, Settings, ShieldAlert, LayoutDashboard, UserRound, X } from 'lucide-react'
import { clearToken } from './api'
import Logo from './Logo'

function MilkWaves() {
  return (
    <div className="side-milk" aria-hidden>
      <svg viewBox="0 0 180 280" preserveAspectRatio="none">
        <defs>
          <linearGradient id="milkA" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#9fd4ff" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#168CEB" stopOpacity="0.2" />
          </linearGradient>
          <linearGradient id="milkB" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#eaf6ff" stopOpacity="0.7" />
            <stop offset="55%" stopColor="#0875D1" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#003E80" stopOpacity="0.15" />
          </linearGradient>
          <linearGradient id="milkC" x1="0.2" y1="0" x2="0.8" y2="1">
            <stop offset="0%" stopColor="#c8e8ff" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#004A96" stopOpacity="0.25" />
          </linearGradient>
        </defs>
        <path className="milk-w milk-w1" d="M-20 90 C 20 50, 70 130, 110 80 C 145 40, 175 95, 210 70 L 210 280 L -20 280 Z" fill="url(#milkA)" />
        <path className="milk-w milk-w2" d="M-20 140 C 30 100, 80 180, 120 130 C 155 95, 180 160, 210 125 L 210 280 L -20 280 Z" fill="url(#milkB)" />
        <path className="milk-w milk-w3" d="M-20 190 C 40 155, 85 220, 130 185 C 160 160, 185 210, 210 180 L 210 280 L -20 280 Z" fill="url(#milkC)" />
      </svg>
    </div>
  )
}

export default function Layout({ children, user, onLogout }: { children: React.ReactNode; user: any; onLogout?: () => void }) {
  const nav = useNavigate()
  const loc = useLocation()
  const [navOpen, setNavOpen] = useState(false)
  useEffect(() => {
    setNavOpen(false)
  }, [loc.pathname])
  useEffect(() => {
    document.body.style.overflow = navOpen ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [navOpen])
  const items = [
    ['/', 'Главная', LayoutDashboard],
    ['/map', 'Карта', Map],
    ['/orders', 'Заказы', Package],
    ['/vehicles', 'Автопарк', Car],
    ['/drivers', 'Водители', UserRound],
    ['/restrictions', 'Ограничения', ShieldAlert],
    ['/analytics', 'Аналитика', BarChart3],
    ['/settings', 'Настройки', Settings],
  ] as const
  const handleLogout = () => {
    clearToken()
    onLogout?.()
    nav('/login')
  }
  return (
    <div className={`layout ${navOpen ? 'nav-open' : ''}`}>
      <header className="mob-bar">
        <button type="button" className="mob-menu" aria-expanded={navOpen} aria-label={navOpen ? 'Закрыть меню' : 'Открыть меню'} onClick={() => setNavOpen((v) => !v)}>
          {navOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        <Logo size={36} wide />
        <span className="mob-title">Молочный мир</span>
        <button type="button" className="mob-logout" title="Выйти" aria-label="Выйти" onClick={handleLogout}>
          <LogOut size={20} />
        </button>
      </header>
      {navOpen ? <button type="button" className="nav-scrim" aria-label="Закрыть меню" onClick={() => setNavOpen(false)} /> : null}
      <aside className={`side ${navOpen ? 'open' : ''}`}>
        <MilkWaves />
        <div className="side-inner">
          <button type="button" className="side-close" aria-label="Закрыть меню" onClick={() => setNavOpen(false)}>
            <X size={20} />
          </button>
          <div className="brand">
            <Logo size={64} wide />
            <h1>Молочный мир</h1>
            <p>Логистика | Гродно</p>
          </div>
          <nav className="nav">
            {items.map(([to, label, Icon]) => (
              <NavLink key={to} to={to} end={to === '/'} onClick={() => setNavOpen(false)}>
                <Icon size={20} strokeWidth={1.85} />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="grow" />
          <div className="side-user">
            <div className="avatar" title={user?.full_name || 'Диспетчер'}>ДП</div>
            <div className="side-user-meta">
              <b>{user?.full_name || 'Диспетчер'}</b>
              <span>{user?.username || 'Молочный мир'}</span>
            </div>
            <button className="side-logout" title="Выйти" onClick={handleLogout}>
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  )
}
