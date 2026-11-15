import { Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { api, setToken } from '../api'
import Logo from '../Logo'

export default function Login({ onAuth, user }: { onAuth: (u: any) => void; user?: any }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()

  if (user?.role === 'driver') return <Navigate to="/driver" replace />
  if (user?.role === 'dispatcher') return <Navigate to="/" replace />

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      const data: any = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: username.trim(), password }),
      })
      setToken(data.token)
      onAuth(data.user)
      nav(data.user.role === 'driver' ? '/driver' : '/', { replace: true })
    } catch (ex: any) {
      setErr(ex.message || 'Неверный логин или пароль')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login" onSubmit={submit}>
        <div className="brand" style={{ flexDirection: 'row', textAlign: 'left' }}>
          <Logo size={56} wide />
          <div>
            <h2>Молочный мир</h2>
            <p className="muted">Интеллектуальная логистика, Гродно</p>
          </div>
        </div>
        <label className="field">
          Логин или номер телефона
          <input
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="driver1 или +37529…"
          />
        </label>
        <label className="field">
          Пароль
          <div className="password-wrap">
            <input
              type={show ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button type="button" className="password-toggle" onClick={() => setShow((v) => !v)} aria-label={show ? 'Скрыть пароль' : 'Показать пароль'}>
              {show ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </label>
        {err && <div className="alert bad">{err}</div>}
        <button className="btn" type="submit" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Вход…' : 'Войти'}
        </button>
        <p className="muted" style={{ marginTop: 14 }}>
          Аккаунт выдаёт диспетчер. Самостоятельная регистрация недоступна.
        </p>
      </form>
    </div>
  )
}
