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

interface Movement {
  id: number
  cash_close_id: number
  amount: string
  description: string
  created_at: string
}

type ActiveTab = 'pos' | 'cash' | 'calendar' | 'admin'

const emptyCashState: CashState = {
  id: null, is_open: false, opened_at: null,
  opening_amount: '0.00', total_sales_cash: '0.00',
  total_sales_debit: '0.00', total_sales_transfer: '0.00',
  total_sales: '0.00', expected_cash: '0.00',
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
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

  // Modal: cierre de caja
  const [showCloseCash, setShowCloseCash] = useState(false)
  const [closingAmount, setClosingAmount] = useState('')
  const [movements, setMovements] = useState<Movement[]>([])
  const [salesCount, setSalesCount] = useState(0)
  const [profitData, setProfitData] = useState<{
    total_revenue: string; total_cost_estimate: string
    gross_profit: string; margin_percent: string; total_sales_count: number
  } | null>(null)

  const [cashMsg, setCashMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [cashSubmitting, setCashSubmitting] = useState(false)

  // Modal: PIN de administrador
  const [showAdminPin, setShowAdminPin] = useState(false)
  const [adminPin, setAdminPin] = useState('')
  const [adminPinError, setAdminPinError] = useState('')
  const [adminPinSubmitting, setAdminPinSubmitting] = useState(false)
  // const [adminUnlocked, setAdminUnlocked] = useState(false)
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

  // ── Modal: Cierre de caja ─────────────────────────────────────────────────
  const openCloseCashModal = async () => {
    const state = await reloadCashState()
    setClosingAmount('')
    setCashMsg(null)
    setMovements([])
    setSalesCount(0)
    setProfitData(null)

    // Cargar movimientos, ventas y ganancia en paralelo
    const [movs, sales, profit] = await Promise.allSettled([
      state.id ? api.get<Movement[]>(`/cash/movements/${state.id}`) : Promise.resolve([]),
      api.get<unknown[]>(`/sales?date=${todayStr()}`),
      api.get<typeof profitData>('/cash/profit'),
    ])
    if (movs.status === 'fulfilled') setMovements(movs.value as Movement[])
    if (sales.status === 'fulfilled') setSalesCount((sales.value as unknown[]).length)
    if (profit.status === 'fulfilled') setProfitData(profit.value)

    setShowCloseCash(true)
  }

  const handleCloseCash = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!closingAmount) return
    setCashSubmitting(true)
    setCashMsg(null)
    try {
      await api.post('/cash/close', { closing_amount: closingAmount })
      await reloadCashState()
      setCashMsg({ text: 'Caja cerrada correctamente', type: 'success' })
      setTimeout(() => { setShowCloseCash(false); setCashMsg(null); setClosingAmount('') }, 1500)
    } catch (err: unknown) {
      setCashMsg({ text: err instanceof Error ? err.message : 'Error al cerrar caja', type: 'error' })
    } finally {
      setCashSubmitting(false)
    }
  }

  // ── Modal: PIN de administrador ───────────────────────────────────────────
  const setAdminUnlockedSync = (val: boolean) => {
    adminUnlockedRef.current = val
  //   setAdminUnlocked(val)
  }

  const openAdminPanel = () => {
    if (adminUnlockedRef.current) {
      setActiveTab('admin')
      return
    }
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
        if (e.key === 'F2')  { e.preventDefault(); setAdminSection('sales_history'); openAdminPanel() }
        if (e.key === 'F5')  { e.preventDefault(); setAdminSection('inventory');    openAdminPanel() }
        if (e.key === 'F6')  { e.preventDefault(); setAdminSection('stock_edit');   openAdminPanel() }
        if (e.key === 'F7')  { e.preventDefault(); setAdminSection('stock_inject'); openAdminPanel() }
        if (e.key === 'F9')  { e.preventDefault(); setAdminSection('import');       openAdminPanel() }
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

  // Cálculos para el modal de cierre
  const netMovements = movements.reduce((acc, m) => acc + parseFloat(m.amount), 0)
  const expectedCash = parseFloat(cashState.expected_cash)          // apertura + ventas_efectivo
  const theoreticalCash = expectedCash + netMovements               // + movimientos manuales netos
  const countedAmount = parseFloat(closingAmount) || 0
  const difference = countedAmount - theoreticalCash
  const differenceLabel = difference >= 0 ? 'Sobrante' : 'Faltante'

  return (
    <>
      {/* Header con tabs */}
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
            <button className="btn btn-danger btn-sm" onClick={openCloseCashModal}>
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

      {/* ── Modal: Cierre de caja (Informe de Arqueo) ───────────────────── */}
      {showCloseCash && (
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowCloseCash(false) }}>
          <div className="modal-content" style={{ minWidth: 560, maxWidth: 700, maxHeight: '92vh' }}>

            {/* Encabezado del informe */}
            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <div className="modal-title" style={{ marginBottom: 2 }}>Informe de Cierre de Caja</div>
              {cashState.opened_at && (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  Apertura: {fmtDateTime(cashState.opened_at)}
                  {' '}· Operador: {user.user_name}
                </div>
              )}
            </div>

            {/* ── Rentabilidad ── */}
            <div className="arqueo-section">
              <div className="arqueo-section-title">Rentabilidad del Período <span style={{ fontWeight: 400, fontSize: 11 }}>(ganancia bruta estimada)</span></div>

              {/* Barra de progreso visual: ancho = margen% */}
              {profitData && (
                <div style={{ background: 'var(--success-light)', borderRadius: 4, height: 10, marginBottom: 10, overflow: 'hidden' }}>
                  <div style={{ background: 'var(--success)', height: '100%', width: `${Math.min(parseFloat(profitData.margin_percent), 100)}%`, borderRadius: 4, transition: 'width 0.4s ease' }} />
                </div>
              )}

              <div className="arqueo-row">
                <span>Total Facturado (Ventas)</span>
                <span className="font-mono">${profitData ? profitData.total_revenue : cashState.total_sales}</span>
              </div>
              <div className="arqueo-row text-secondary">
                <span>(-) Costo de Mercadería vendida *</span>
                <span className="font-mono">{profitData ? `$${profitData.total_cost_estimate}` : '…'}</span>
              </div>
              <div className="arqueo-row" style={{ fontWeight: 700, color: 'var(--success)' }}>
                <span>(=) Ganancia Bruta Estimada</span>
                <span className="font-mono">{profitData ? `$${profitData.gross_profit}` : '…'}</span>
              </div>
              <div className="arqueo-row text-secondary">
                <span>Margen sobre ventas</span>
                <span className="font-mono">{profitData ? `${profitData.margin_percent}%` : '—'}</span>
              </div>
              <div className="arqueo-row text-secondary">
                <span>Cantidad de ventas del período</span>
                <span className="font-mono">{profitData ? profitData.total_sales_count : salesCount}</span>
              </div>
            </div>

            {/* ── Ventas por método de pago ── */}
            <div className="arqueo-section">
              <div className="arqueo-section-title">Ventas del Período por Método de Pago</div>
              <div className="arqueo-row"><span>Efectivo</span><span className="font-mono">${cashState.total_sales_cash}</span></div>
              <div className="arqueo-row"><span>Débito</span><span className="font-mono">${cashState.total_sales_debit}</span></div>
              <div className="arqueo-row"><span>Transferencia</span><span className="font-mono">${cashState.total_sales_transfer}</span></div>
              <div className="arqueo-row arqueo-row-total"><span>TOTAL VENTAS</span><span className="font-mono">${cashState.total_sales}</span></div>
            </div>

            {/* ── Conciliación de efectivo ── */}
            <div className="arqueo-section">
              <div className="arqueo-section-title">Conciliación de Efectivo</div>
              <div className="arqueo-row"><span>Monto Inicial (Apertura)</span><span className="font-mono">${cashState.opening_amount}</span></div>
              <div className="arqueo-row"><span>(+) Ventas en Efectivo</span><span className="font-mono">${cashState.total_sales_cash}</span></div>
              <div className="arqueo-row">
                <span>(+/-) Movimientos Manuales (neto)</span>
                <span className={`font-mono ${netMovements < 0 ? 'text-danger' : ''}`}>
                  {netMovements >= 0 ? '+' : ''}${netMovements.toFixed(2)}
                </span>
              </div>
              <div className="arqueo-row">
                <span>(=) Saldo Teórico en Caja</span>
                <span className="font-mono">${theoreticalCash.toFixed(2)}</span>
              </div>

              {/* Input monto contado */}
              <form onSubmit={handleCloseCash}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', gap: 12 }}>
                  <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>Monto Contado (Real)</span>
                  <input
                    type="number" min="0" step="0.01"
                    className="input font-mono"
                    style={{ width: 140, textAlign: 'right' }}
                    value={closingAmount}
                    onChange={(e) => setClosingAmount(e.target.value)}
                    placeholder="0.00"
                    required
                    autoFocus
                  />
                </div>

                {closingAmount && (
                  <div className="arqueo-row arqueo-row-diff">
                    <span>Diferencia de Caja</span>
                    <span className={`font-mono font-bold ${difference >= 0 ? 'text-success' : 'text-danger'}`}>
                      ${Math.abs(difference).toFixed(2)} {differenceLabel}
                    </span>
                  </div>
                )}

                {/* ── Movimientos manuales ── */}
                {movements.length > 0 && (
                  <div className="arqueo-section" style={{ marginTop: 12 }}>
                    <div className="arqueo-section-title">Movimientos Manuales del Período</div>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                      <thead>
                        <tr>
                          <th style={{ textAlign: 'left', padding: '4px 6px', color: 'var(--text-hint)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>Hora</th>
                          <th style={{ textAlign: 'left', padding: '4px 6px', color: 'var(--text-hint)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>Descripción</th>
                          <th style={{ textAlign: 'right', padding: '4px 6px', color: 'var(--text-hint)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>Monto</th>
                        </tr>
                      </thead>
                      <tbody>
                        {movements.map((m) => (
                          <tr key={m.id}>
                            <td style={{ padding: '4px 6px', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{fmtTime(m.created_at)}</td>
                            <td style={{ padding: '4px 6px' }}>{m.description}</td>
                            <td style={{ padding: '4px 6px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: parseFloat(m.amount) >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                              {parseFloat(m.amount) >= 0 ? '+' : ''}${m.amount}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {movements.length === 0 && (
                  <div className="arqueo-section" style={{ marginTop: 12 }}>
                    <div className="arqueo-section-title">Movimientos Manuales del Período</div>
                    <p style={{ fontSize: 12, color: 'var(--text-hint)', fontStyle: 'italic' }}>Sin movimientos manuales en este período.</p>
                  </div>
                )}

                {cashMsg && <div className={`msg msg-${cashMsg.type}`} style={{ marginTop: 12 }}>{cashMsg.text}</div>}

                <div className="modal-footer" style={{ marginTop: 16 }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setShowCloseCash(false)}>Cancelar</button>
                  <button type="submit" className="btn btn-danger" disabled={cashSubmitting || !closingAmount}>
                    {cashSubmitting ? 'Cerrando…' : 'Confirmar y cerrar caja'}
                  </button>
                </div>
              </form>
            </div>

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
        {activeTab === 'pos'      && <POS />}
        {activeTab === 'cash'     && <CashView />}
        {activeTab === 'calendar' && <CalendarView />}
        {activeTab === 'admin' && isAdmin && (
          <AdminPanel section={adminSection} onSectionChange={setAdminSection} />
        )}
      </div>
    </>
  )
}
