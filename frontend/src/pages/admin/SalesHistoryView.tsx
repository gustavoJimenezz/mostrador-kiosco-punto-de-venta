/**
 * Vista de historial de ventas (F2 en panel admin).
 * Muestra ventas del día seleccionado con detalle de ítems por venta.
 */

import { useEffect, useState } from 'react'
import { api } from '../../api/client'

interface SaleItem { product_name: string; quantity: number; price_at_sale: string; subtotal: string }
interface Sale {
  id: string; timestamp: string; total_amount: string; payment_method: string; items: SaleItem[]
}

const METHOD_LABEL: Record<string, string> = {
  EFECTIVO: 'Efectivo', DEBITO: 'Débito', TRANSFERENCIA: 'Transferencia',
}
const METHOD_BADGE: Record<string, string> = {
  EFECTIVO: 'badge-success', DEBITO: 'badge-info', TRANSFERENCIA: 'badge-warning',
}

function today() {
  return new Date().toISOString().split('T')[0]
}
function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function SalesHistoryView() {
  const [date, setDate] = useState(today())
  const [sales, setSales] = useState<Sale[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    setExpanded(null)
    try {
      const data = await api.get<Sale[]>(`/sales?date=${date}`)
      setSales(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al cargar ventas')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [date])

  const totalDay = sales.reduce((a, s) => a + parseFloat(s.total_amount), 0)
  const countByMethod = sales.reduce((acc, s) => {
    acc[s.payment_method] = (acc[s.payment_method] || 0) + parseFloat(s.total_amount)
    return acc
  }, {} as Record<string, number>)

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="admin-content-header">
        <span className="admin-content-title">Historial de ventas</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} style={{ width: 160 }} />
          <button className="btn btn-secondary" onClick={load} disabled={loading}>Actualizar</button>
        </div>
      </div>

      {error && <div className="msg msg-error">{error}</div>}

      {/* Resumen del día */}
      {sales.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          <div className="card" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Total ventas</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--success)' }}>${totalDay.toFixed(2)}</div>
            <div style={{ fontSize: 11, color: 'var(--text-hint)' }}>{sales.length} operacion{sales.length !== 1 ? 'es' : ''}</div>
          </div>
          {Object.entries(countByMethod).map(([method, total]) => (
            <div key={method} className="card" style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{METHOD_LABEL[method] ?? method}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--primary)' }}>${total.toFixed(2)}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabla de ventas */}
      <div className="scroll-y card" style={{ padding: 0, flex: 1 }}>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-hint)' }}>Cargando…</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Hora</th>
                <th>Método</th>
                <th>Ítems</th>
                <th className="td-right">Total</th>
                <th style={{ width: 80 }}></th>
              </tr>
            </thead>
            <tbody>
              {sales.length === 0 && (
                <tr><td colSpan={5} className="td-center" style={{ padding: '32px 0', color: 'var(--text-hint)' }}>Sin ventas para este día</td></tr>
              )}
              {sales.map((s) => (
                <>
                  <tr key={s.id} style={{ cursor: 'pointer' }} onClick={() => setExpanded(expanded === s.id ? null : s.id)}>
                    <td className="td-mono text-secondary">{fmtTime(s.timestamp)}</td>
                    <td><span className={`badge ${METHOD_BADGE[s.payment_method] ?? 'badge-secondary'}`}>{METHOD_LABEL[s.payment_method] ?? s.payment_method}</span></td>
                    <td className="text-secondary">{s.items.length} ítem{s.items.length !== 1 ? 's' : ''}</td>
                    <td className="td-right td-mono font-bold" style={{ color: 'var(--primary)' }}>${s.total_amount}</td>
                    <td className="td-center text-secondary" style={{ fontSize: 11 }}>{expanded === s.id ? '▲ ocultar' : '▼ detalle'}</td>
                  </tr>
                  {expanded === s.id && (
                    <tr key={`${s.id}-detail`}>
                      <td colSpan={5} style={{ padding: 0, background: 'var(--primary-light)' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                              <th style={{ padding: '4px 16px', textAlign: 'left', color: 'var(--text-secondary)' }}>Producto</th>
                              <th style={{ padding: '4px 8px', textAlign: 'center', color: 'var(--text-secondary)' }}>Cant.</th>
                              <th style={{ padding: '4px 8px', textAlign: 'right', color: 'var(--text-secondary)' }}>P.unit.</th>
                              <th style={{ padding: '4px 16px', textAlign: 'right', color: 'var(--text-secondary)' }}>Subtotal</th>
                            </tr>
                          </thead>
                          <tbody>
                            {s.items.map((item, i) => (
                              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                                <td style={{ padding: '4px 16px' }}>{item.product_name}</td>
                                <td style={{ padding: '4px 8px', textAlign: 'center' }}>{item.quantity}</td>
                                <td style={{ padding: '4px 8px', textAlign: 'right', fontFamily: 'monospace' }}>${item.price_at_sale}</td>
                                <td style={{ padding: '4px 16px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700 }}>${item.subtotal}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
