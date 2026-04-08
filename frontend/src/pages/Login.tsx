/**
 * Pantalla de inicio de sesión.
 * El operador selecciona su nombre y escribe su PIN numérico.
 */

import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

interface UserListItem { id: number; name: string; role: string }
interface Session { user_id: number; user_name: string; user_role: string }
interface Props { onLogin: (user: Session) => void }

export default function Login({ onLogin }: Props) {
  const [users, setUsers] = useState<UserListItem[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const pinRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.get<UserListItem[]>('/auth/users').then(setUsers).catch(() => {})
  }, [])

  useEffect(() => {
    if (selectedId) pinRef.current?.focus()
  }, [selectedId])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedId) return
    setError('')
    setLoading(true)
    try {
      const session = await api.post<Session>('/auth/login', { user_id: selectedId, pin })
      onLogin(session)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'PIN incorrecto o usuario inactivo')
      setPin('')
      pinRef.current?.focus()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', background: 'var(--surface)',
    }}>
      <div style={{ width: 380 }}>
        {/* Logo / Título */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--primary)', letterSpacing: '-0.5px' }}>
            Kiosco POS
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Sistema de punto de venta
          </div>
        </div>

        <div className="card" style={{ boxShadow: '0 4px 24px rgba(79,70,229,0.08)', borderColor: 'var(--border)' }}>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label className="form-label">Operador</label>
              <select
                className="input input-lg"
                value={selectedId ?? ''}
                onChange={(e) => { setSelectedId(Number(e.target.value)); setPin('') }}
                required
              >
                <option value="">Seleccionar operador…</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} — {u.role === 'admin' ? 'Administrador' : 'Operador'}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">PIN</label>
              <input
                ref={pinRef}
                type="password"
                inputMode="numeric"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                placeholder="••••"
                maxLength={8}
                className="input"
                style={{ fontSize: 24, letterSpacing: 10, textAlign: 'center' }}
                required
                disabled={!selectedId}
              />
            </div>

            {error && (
              <div className="msg msg-error" style={{ marginBottom: 12 }}>{error}</div>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-full btn-lg"
              disabled={!selectedId || !pin || loading}
            >
              {loading ? 'Ingresando…' : 'Ingresar'}
            </button>
          </form>
        </div>

        <div style={{ textAlign: 'center', marginTop: 16, fontSize: 11, color: 'var(--text-hint)' }}>
          v2.0 — FastAPI + React + SQLite
        </div>
      </div>
    </div>
  )
}
