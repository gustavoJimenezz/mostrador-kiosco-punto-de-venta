/**
 * Raíz de la aplicación.
 *
 * Atajos de teclado globales (válidos en cualquier pestaña):
 *   F1  — ir a Venta + limpiar carrito
 *   F10 — ir a Caja
 *   (Admin) F2  — ir a Admin > Historial de ventas
 *   (Admin) F5  — ir a Admin > Inventario
 *   (Admin) F6  — ir a Admin > Editar stock
 *   (Admin) F7  — ir a Admin > Inyectar stock
 *   (Admin) F9  — ir a Admin > Importar
 *
 * F4 y F12 (confirmar venta) son manejados por POS.tsx.
 */

import { useEffect, useRef, useState } from 'react'
import { api } from './api/client'
import { useCartStore } from './store/cartStore'
import Login from './pages/Login'
import POS from './pages/POS'
import CashView from './pages/CashView'
import CashCloseView from './pages/CashCloseView'
import AdminPanel, { type AdminSection } from './pages/AdminPanel'
import CalendarView from './pages/CalendarView'

interface SessionUser { user_id: number; user_name: string; user_role: string }

interface CashState {
  id: number | null
  is_open: boolean
  opened_at: string | null
  opening_amount: string
  total_sales_cash: string
  total_sales_debit: string
  total_sales_transfer: string
  total_sales: string
  expected_cash: string
}

type ActiveTab = 'pos' | 'cash' | 'calendar' | 'admin' | 'cash_close'

const emptyCashState: CashState = {
  id: null, is_open: false, opened_at: null,
  opening_amount: '0.00', total_sales_cash: '0.00',
  total_sales_debit: '0.00', total_sales_transfer: '0.00',
  total_sales: '0.00', expected_cash: '0.00',
}

export default function App() {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<ActiveTab>('pos')
  const [adminSection, setAdminSection] = useState<AdminSection>('inventory')
  const [cashState, setCashState] = useState<CashState>(emptyCashState)

  // Modal: abrir caja
  const [showOpenCash, setShowOpenCash] = useState(false)
  const [openingAmount, setOpeningAmount] = useState('0.00')
  const [cashMsg, setCashMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [cashSubmitting, setCashSubmitting] = useState(false)

  // Modal: PIN de administrador
  const [showAdminPin, setShowAdminPin] = useState(false)
  const [adminPin, setAdminPin] = useState('')
  const [adminPinError, setAdminPinError] = useState('')
  const [adminPinSubmitting, setAdminPinSubmitting] = useState(false)
  const adminUnlockedRef = useRef(false)

  useEffect(() => {
    api.get<SessionUser>('/auth/me')
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const reloadCashState = () =>
    api.get<CashState>('/cash/state').then(s => { setCashState(s); return s }).catch(() => emptyCashState)

  useEffect(() => {
    if (!user) return
    reloadCashState()
  }, [user])

  // ── Modal: Abrir caja ──────────────────────────────────────────────────────
  const handleOpenCash = async (e: React.FormEvent) => {
    e.preventDefault()
    setCashSubmitting(true)
    setCashMsg(null)
    try {
      const s = await api.post<CashState>('/cash/open', { opening_amount: openingAmount })
      setCashState(s)
      setCashMsg({ text: 'Caja abierta correctamente', type: 'success' })
      setTimeout(() => { setShowOpenCash(false); setCashMsg(null); setOpeningAmount('0.00') }, 1200)
    } catch (err: unknown) {
      setCashMsg({ text: err instanceof Error ? err.message : 'Error al abrir caja', type: 'error' })
    } finally {
      setCashSubmitting(false)
    }
  }

  // ── Cierre de caja — navega a la vista dedicada ───────────────────────────
  const handleCashClosed = async () => {
    await reloadCashState()
    setActiveTab('pos')
  }

  // ── Modal: PIN de administrador ───────────────────────────────────────────
  const setAdminUnlockedSync = (val: boolean) => { adminUnlockedRef.current = val }

  const openAdminPanel = () => {
    if (adminUnlockedRef.current) { setActiveTab('admin'); return }
    setAdminPin('')
    setAdminPinError('')
    setShowAdminPin(true)
  }

  const handleAdminPinSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setAdminPinSubmitting(true)
    setAdminPinError('')
    try {
      await api.post('/auth/verify-admin-pin', { pin: adminPin })
      setAdminUnlockedSync(true)
      setShowAdminPin(false)
      setActiveTab('admin')
    } catch {
      setAdminPinError('PIN incorrecto. Intentá de nuevo.')
      setAdminPin('')
    } finally {
      setAdminPinSubmitting(false)
    }
  }

  // ── Atajos de teclado globales ─────────────────────────────────────────────
  useEffect(() => {
    if (!user) return
    const isAdmin = user.user_role === 'admin'

    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName ?? ''
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'

      if (e.key === 'F1') { e.preventDefault(); setActiveTab('pos'); setAdminUnlockedSync(false); useCartStore.getState().clear() }
      if (e.key === 'F10') { e.preventDefault(); setActiveTab('cash'); setAdminUnlockedSync(false) }
      if (isAdmin && !typing) {
        if (e.key === 'F2') { e.preventDefault(); setAdminSection('sales_history'); openAdminPanel() }
        if (e.key === 'F5') { e.preventDefault(); setAdminSection('inventory');    openAdminPanel() }
        if (e.key === 'F6') { e.preventDefault(); setAdminSection('stock_edit');   openAdminPanel() }
        if (e.key === 'F7') { e.preventDefault(); setAdminSection('stock_inject'); openAdminPanel() }
        if (e.key === 'F9') { e.preventDefault(); setAdminSection('import');       openAdminPanel() }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [user])

  const logout = async () => {
    await api.post('/auth/logout')
    setUser(null)
    setAdminUnlockedSync(false)
    useCartStore.getState().clear()
  }

  if (loading) return <div className="loading">Cargando…</div>
  if (!user) return <Login onLogin={setUser} />

  const isAdmin = user.user_role === 'admin'

  return (
    <>
      {/* Header con tabs — oculto en la vista de cierre de caja */}
      {activeTab !== 'cash_close' && (
        <header className="app-header">
          <nav className="tab-nav">
            <button className={`tab-btn ${activeTab === 'pos' ? 'active' : ''}`} onClick={() => setActiveTab('pos')}>
              Venta
            </button>
            <button className={`tab-btn ${activeTab === 'cash' ? 'active' : ''}`} onClick={() => setActiveTab('cash')}>
              Movimientos de caja
            </button>
            <button className={`tab-btn ${activeTab === 'calendar' ? 'active' : ''}`} onClick={() => setActiveTab('calendar')}>
              Calendario
            </button>
          </nav>

          <div className="app-header-user">
            {!cashState.is_open && (
              <button className="btn btn-warning-amber btn-sm" onClick={() => { setShowOpenCash(true); setCashMsg(null) }}>
                Abrir caja
              </button>
            )}
            {cashState.is_open && (
              <button className="btn btn-danger btn-sm" onClick={() => setActiveTab('cash_close')}>
                Cierre de caja
              </button>
            )}
            {isAdmin && (
              <button className="btn btn-success btn-sm" onClick={openAdminPanel} title={user.user_name}>
                Administrador
              </button>
            )}
            {isAdmin && (
              <button className="btn btn-teal btn-sm" onClick={logout} title={user.user_name}>
                Salir
              </button>
            )}
          </div>
        </header>
      )}

      {/* ── Modal: Abrir caja ────────────────────────────────────────────── */}
      {showOpenCash && (
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowOpenCash(false) }}>
          <div className="modal-content" style={{ minWidth: 320, maxWidth: 400 }}>
            <div className="modal-title">Abrir caja</div>
            <form onSubmit={handleOpenCash}>
              <div className="form-group">
                <label className="form-label">Fondo inicial ($)</label>
                <input
                  type="number" min="0" step="0.01"
                  className="input"
                  value={openingAmount}
                  onChange={(e) => setOpeningAmount(e.target.value)}
                  autoFocus
                />
              </div>
              {cashMsg && <div className={`msg msg-${cashMsg.type}`} style={{ marginBottom: 12 }}>{cashMsg.text}</div>}
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowOpenCash(false)}>Cancelar</button>
                <button type="submit" className="btn btn-warning-amber" disabled={cashSubmitting}>
                  {cashSubmitting ? 'Abriendo…' : 'Abrir caja'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal: PIN de administrador ─────────────────────────────────── */}
      {showAdminPin && (
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowAdminPin(false) }}>
          <div className="modal-content" style={{ minWidth: 320, maxWidth: 380 }}>
            <div className="modal-title">Acceso al panel de administrador</div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Ingresá el PIN de administrador para continuar.
            </p>
            <form onSubmit={handleAdminPinSubmit}>
              <div className="form-group">
                <label className="form-label">PIN</label>
                <input
                  type="password"
                  className="input"
                  value={adminPin}
                  onChange={(e) => setAdminPin(e.target.value)}
                  placeholder="••••"
                  autoFocus
                  autoComplete="off"
                />
              </div>
              {adminPinError && (
                <div className="msg msg-error" style={{ marginBottom: 12 }}>{adminPinError}</div>
              )}
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowAdminPin(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-success" disabled={adminPinSubmitting || !adminPin}>
                  {adminPinSubmitting ? 'Verificando…' : 'Ingresar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Área de contenido */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {activeTab === 'pos'        && <POS cashCloseId={cashState.id} />}
        {activeTab === 'cash'       && <CashView />}
        {activeTab === 'calendar'   && <CalendarView />}
        {activeTab === 'cash_close' && (
          <CashCloseView
            userName={user.user_name}
            onBack={() => setActiveTab('pos')}
            onClosed={handleCashClosed}
          />
        )}
        {activeTab === 'admin' && isAdmin && (
          <AdminPanel section={adminSection} onSectionChange={setAdminSection} />
        )}
      </div>

    </>
  )
}
