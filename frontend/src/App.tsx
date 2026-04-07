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

import { useEffect, useState } from 'react'
import { api } from './api/client'
import { useCartStore } from './store/cartStore'
import Login from './pages/Login'
import POS from './pages/POS'
import CashView from './pages/CashView'
import AdminPanel, { type AdminSection } from './pages/AdminPanel'

interface SessionUser { user_id: number; user_name: string; user_role: string }
type ActiveTab = 'pos' | 'cash' | 'calendar' | 'admin'

export default function App() {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<ActiveTab>('pos')
  const [adminSection, setAdminSection] = useState<AdminSection>('inventory')

  useEffect(() => {
    api.get<SessionUser>('/auth/me')
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  // Atajos de teclado globales para navegación
  useEffect(() => {
    if (!user) return
    const isAdmin = user.user_role === 'admin'

    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName ?? ''
      // No interferir con F-keys de navegación cuando el usuario escribe
      // (excepto F1 y F10 que siempre aplican)
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'

      if (e.key === 'F1') {
        e.preventDefault()
        setActiveTab('pos')
        useCartStore.getState().clear()
      }
      if (e.key === 'F10') {
        e.preventDefault()
        setActiveTab('cash')
      }
      if (isAdmin && !typing) {
        if (e.key === 'F2')  { e.preventDefault(); setActiveTab('admin'); setAdminSection('sales_history') }
        if (e.key === 'F5')  { e.preventDefault(); setActiveTab('admin'); setAdminSection('inventory') }
        if (e.key === 'F6')  { e.preventDefault(); setActiveTab('admin'); setAdminSection('stock_edit') }
        if (e.key === 'F7')  { e.preventDefault(); setActiveTab('admin'); setAdminSection('stock_inject') }
        if (e.key === 'F9')  { e.preventDefault(); setActiveTab('admin'); setAdminSection('import') }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [user])

  const logout = async () => {
    await api.post('/auth/logout')
    setUser(null)
    useCartStore.getState().clear()
  }

  if (loading) return <div className="loading">Cargando…</div>
  if (!user) return <Login onLogin={setUser} />

  const isAdmin = user.user_role === 'admin'

  return (
    <>
      {/* Header con tabs */}
      <header className="app-header">
        <nav className="tab-nav">
          <button
            className={`tab-btn ${activeTab === 'pos' ? 'active' : ''}`}
            onClick={() => setActiveTab('pos')}
          >
            Venta
          </button>
          <button
            className={`tab-btn ${activeTab === 'cash' ? 'active' : ''}`}
            onClick={() => setActiveTab('cash')}
          >
            Movimientos de caja
          </button>
          <button
            className={`tab-btn ${activeTab === 'calendar' ? 'active' : ''}`}
            onClick={() => setActiveTab('calendar')}
          >
            Calendario
          </button>
        </nav>

        <div className="app-header-user">
          <button className="btn btn-warning-amber btn-sm" onClick={() => setActiveTab('cash')}>
            Abrir caja
          </button>
          <button className="btn btn-danger btn-sm" onClick={() => setActiveTab('cash')}>
            Cierre de caja
          </button>
          {isAdmin && (
            <button
              className="btn btn-success btn-sm"
              onClick={() => { setActiveTab('admin') }}
              title={user.user_name}
            >
              Administrador
            </button>
          )}
        </div>
      </header>

      {/* Área de contenido */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {activeTab === 'pos'      && <POS />}
        {activeTab === 'cash'     && <CashView />}
        {activeTab === 'calendar' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: 'var(--text-hint)', fontSize: 15 }}>
            Calendario — próximamente
          </div>
        )}
        {activeTab === 'admin' && isAdmin && (
          <AdminPanel section={adminSection} onSectionChange={setAdminSection} />
        )}
      </div>
    </>
  )
}
