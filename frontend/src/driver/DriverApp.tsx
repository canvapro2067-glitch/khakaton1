import { Home, Map, Package, UserRound } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'
import { DriverProvider, useDriver } from './DriverContext'
import DriverHome from './DriverHome'
import DriverMapTab from './DriverMapTab'
import DriverOrders from './DriverOrders'
import DriverProfile from './DriverProfile'

function Nav() {
  const { pack, pending, tabNotes } = useDriver()
  const unread = (tabNotes || []).filter((n: any) => !n.read).length || pack?.unread_notifications || 0
  const items = [
    ['/driver', 'Главная', Home, true],
    ['/driver/map', 'Маршрут', Map, false],
    ['/driver/orders', 'Заказы', Package, false],
    ['/driver/profile', 'Профиль', UserRound, false],
  ] as const
  return (
    <nav className="driver-tabbar">
      {items.map(([to, label, Icon, end]) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? 'on' : '')}>
          <Icon size={20} />
          {label}
          {to === '/driver/profile' && (unread || pending) ? <i className="tab-dot" /> : null}
        </NavLink>
      ))}
    </nav>
  )
}

function Inner({ onLogout }: { onLogout?: () => void }) {
  const { pack, err } = useDriver()
  const loc = useLocation()
  if (!pack) return <div className="driver">{err || 'Загрузка маршрута…'}</div>
  const p = loc.pathname
  let page = <DriverHome />
  if (p.startsWith('/driver/map')) page = <DriverMapTab />
  else if (p.startsWith('/driver/orders')) page = <DriverOrders />
  else if (p.startsWith('/driver/profile')) page = <DriverProfile onLogout={onLogout} />
  return (
    <div className="driver driver-app">
      {page}
      <Nav />
    </div>
  )
}

export default function DriverApp({ onLogout }: { onLogout?: () => void }) {
  return (
    <DriverProvider>
      <Inner onLogout={onLogout} />
    </DriverProvider>
  )
}
