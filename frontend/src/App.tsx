import { useEffect, useState, type ReactElement } from 'react'
import { BrowserRouter, HashRouter, Navigate, Route, Routes } from 'react-router-dom'

const Router = import.meta.env.VITE_STATIC_HOST === 'tiiny' ? HashRouter : BrowserRouter
import { api, getToken } from './api'
import Layout from './Layout'
import Analytics from './pages/Analytics'
import Dispatcher from './pages/Dispatcher'
import Driver from './pages/Driver'
import Drivers from './pages/Drivers'
import Login from './pages/Login'
import MapRoutes from './pages/MapRoutes'
import Orders from './pages/Orders'
import Restrictions from './pages/Restrictions'
import SettingsPage from './pages/Settings'
import Vehicles from './pages/Vehicles'
import VehicleCard from './pages/VehicleCard'

export default function App() {
  const [user, setUser] = useState<any>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!getToken()) {
      setReady(true)
      return
    }
    api('/api/me')
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setReady(true))
  }, [])

  if (!ready) return <p className="muted" style={{ padding: 24 }}>Загрузка…</p>

  const gate = (el: ReactElement, role: string) => {
    if (!user) return <Navigate to="/login" />
    if (user.role !== role) return <Navigate to={user.role === 'driver' ? '/driver' : '/'} />
    return el
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login onAuth={setUser} user={user} />} />
        <Route path="/driver/*" element={gate(<Driver onLogout={() => setUser(null)} />, 'driver')} />
        <Route path="/" element={gate(<Layout user={user} onLogout={() => setUser(null)}><Dispatcher /></Layout>, 'dispatcher')} />
        <Route path="/map" element={gate(<Layout user={user} onLogout={() => setUser(null)}><MapRoutes /></Layout>, 'dispatcher')} />
        <Route path="/orders" element={gate(<Layout user={user} onLogout={() => setUser(null)}><Orders /></Layout>, 'dispatcher')} />
        <Route path="/vehicles" element={gate(<Layout user={user} onLogout={() => setUser(null)}><Vehicles /></Layout>, 'dispatcher')} />
        <Route path="/vehicles/:id" element={gate(<Layout user={user} onLogout={() => setUser(null)}><VehicleCard /></Layout>, 'dispatcher')} />
        <Route path="/drivers" element={gate(<Layout user={user} onLogout={() => setUser(null)}><Drivers /></Layout>, 'dispatcher')} />
        <Route path="/restrictions" element={gate(<Layout user={user} onLogout={() => setUser(null)}><Restrictions /></Layout>, 'dispatcher')} />
        <Route path="/settings" element={gate(<Layout user={user} onLogout={() => setUser(null)}><SettingsPage /></Layout>, 'dispatcher')} />
        <Route path="/analytics" element={gate(<Layout user={user} onLogout={() => setUser(null)}><Analytics /></Layout>, 'dispatcher')} />
      </Routes>
    </Router>
  )
}
